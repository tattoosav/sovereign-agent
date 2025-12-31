"""FastAPI server for Sovereign Agent."""

import asyncio
import json
import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import tempfile
import shutil
import zipfile
import os

from src.api.session import SessionManager

logger = logging.getLogger(__name__)

# Pydantic models for request/response
class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ToolCallResponse(BaseModel):
    name: str
    params: dict[str, Any]
    result: str
    success: bool


class ChatResponse(BaseModel):
    response: str
    session_id: str
    tool_calls: list[ToolCallResponse] = []
    status: str = "success"
    error: str | None = None


class SessionResponse(BaseModel):
    session_id: str
    message: str


class HistoryMessage(BaseModel):
    role: str
    content: str


class HistoryResponse(BaseModel):
    session_id: str
    messages: list[HistoryMessage]


class ToolInfo(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]


class ToolsResponse(BaseModel):
    tools: list[ToolInfo]


class MetricsResponse(BaseModel):
    session_id: str
    metrics: dict[str, Any]


class HealthResponse(BaseModel):
    status: str
    ollama_connected: bool
    active_sessions: int


# Global session manager
session_manager: SessionManager | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle."""
    global session_manager
    logger.info("Starting Sovereign Agent API server")
    session_manager = SessionManager()
    yield
    logger.info("Shutting down Sovereign Agent API server")
    if session_manager:
        session_manager.close_all()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Sovereign Agent API",
        description="Web API for the Sovereign Agent - Your Local Coding Assistant",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount static files
    static_path = Path(__file__).parent / "static"
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    # Routes
    @app.get("/", response_class=HTMLResponse)
    async def root() -> HTMLResponse:
        """Serve the main web interface."""
        index_path = Path(__file__).parent / "static" / "index.html"
        if index_path.exists():
            return HTMLResponse(content=index_path.read_text())
        return HTMLResponse(content="<h1>Sovereign Agent</h1><p>Static files not found.</p>")

    @app.get("/health", response_model=HealthResponse)
    async def health_check() -> HealthResponse:
        """Check API health and Ollama connection."""
        if session_manager is None:
            raise HTTPException(status_code=503, detail="Server not initialized")

        ollama_ok = session_manager.check_ollama()
        return HealthResponse(
            status="healthy" if ollama_ok else "degraded",
            ollama_connected=ollama_ok,
            active_sessions=session_manager.get_active_count(),
        )

    @app.post("/session/new", response_model=SessionResponse)
    async def create_session() -> SessionResponse:
        """Create a new session."""
        if session_manager is None:
            raise HTTPException(status_code=503, detail="Server not initialized")

        session_id = session_manager.create_session()
        return SessionResponse(
            session_id=session_id,
            message="Session created successfully",
        )

    @app.post("/session/{session_id}/reset", response_model=SessionResponse)
    async def reset_session(session_id: str) -> SessionResponse:
        """Reset a session's conversation history."""
        if session_manager is None:
            raise HTTPException(status_code=503, detail="Server not initialized")

        if not session_manager.reset_session(session_id):
            raise HTTPException(status_code=404, detail="Session not found")

        return SessionResponse(
            session_id=session_id,
            message="Session reset successfully",
        )

    @app.delete("/session/{session_id}")
    async def delete_session(session_id: str) -> SessionResponse:
        """Delete a session."""
        if session_manager is None:
            raise HTTPException(status_code=503, detail="Server not initialized")

        if not session_manager.delete_session(session_id):
            raise HTTPException(status_code=404, detail="Session not found")

        return SessionResponse(
            session_id=session_id,
            message="Session deleted successfully",
        )

    @app.get("/session/{session_id}/history", response_model=HistoryResponse)
    async def get_history(session_id: str) -> HistoryResponse:
        """Get conversation history for a session."""
        if session_manager is None:
            raise HTTPException(status_code=503, detail="Server not initialized")

        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        messages = [
            HistoryMessage(role=msg.role, content=msg.content)
            for msg in session.agent.history
        ]
        return HistoryResponse(session_id=session_id, messages=messages)

    @app.get("/tools", response_model=ToolsResponse)
    async def list_tools() -> ToolsResponse:
        """List all available tools."""
        if session_manager is None:
            raise HTTPException(status_code=503, detail="Server not initialized")

        # Create a temporary session to get tools
        temp_id = session_manager.create_session()
        session = session_manager.get_session(temp_id)
        if not session:
            raise HTTPException(status_code=500, detail="Failed to get tools")

        tools = [
            ToolInfo(
                name=tool.name,
                description=tool.description,
                parameters=tool.parameters,
            )
            for tool in session.agent.tools.all_tools()
        ]

        session_manager.delete_session(temp_id)
        return ToolsResponse(tools=tools)

    @app.get("/session/{session_id}/metrics", response_model=MetricsResponse)
    async def get_metrics(session_id: str) -> MetricsResponse:
        """Get metrics for a session."""
        if session_manager is None:
            raise HTTPException(status_code=503, detail="Server not initialized")

        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        metrics = session.agent.metrics.get_comprehensive_report(
            verification_metrics=session.agent.verifier.get_metrics(),
            cache_stats=session.agent.op_cache.get_stats(),
            error_stats=session.agent.error_recovery.get_error_stats()
        )
        return MetricsResponse(session_id=session_id, metrics=metrics)

    # File upload storage per session
    session_files: dict[str, Path] = {}

    @app.post("/upload")
    async def upload_files(
        files: list[UploadFile] = File(...),
        session_id: str = Form(...)
    ):
        """Upload files for the agent to analyze."""
        if session_manager is None:
            raise HTTPException(status_code=503, detail="Server not initialized")

        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Create temp directory for this session
        if session_id not in session_files:
            session_files[session_id] = Path(tempfile.mkdtemp(prefix=f"sovereign_{session_id[:8]}_"))

        upload_dir = session_files[session_id]
        uploaded = []

        for file in files:
            if file.filename:
                # Handle zip files specially
                if file.filename.endswith('.zip'):
                    # Save and extract zip
                    zip_path = upload_dir / file.filename
                    with open(zip_path, "wb") as f:
                        shutil.copyfileobj(file.file, f)

                    # Extract to subdirectory
                    extract_dir = upload_dir / file.filename.replace('.zip', '')
                    extract_dir.mkdir(exist_ok=True)
                    with zipfile.ZipFile(zip_path, 'r') as zf:
                        zf.extractall(extract_dir)

                    # Count extracted files
                    count = sum(1 for _ in extract_dir.rglob('*') if _.is_file())
                    uploaded.append({"name": file.filename, "type": "zip", "files_extracted": count, "path": str(extract_dir)})
                    zip_path.unlink()  # Remove zip after extraction
                else:
                    # Save regular file
                    file_path = upload_dir / file.filename
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(file_path, "wb") as f:
                        shutil.copyfileobj(file.file, f)
                    uploaded.append({"name": file.filename, "type": "file", "path": str(file_path)})

        return JSONResponse({
            "status": "success",
            "uploaded": uploaded,
            "upload_dir": str(upload_dir),
            "message": f"Uploaded {len(uploaded)} file(s). Use 'analyze project at {upload_dir}' to understand the codebase."
        })

    @app.post("/upload/analyze")
    async def analyze_uploaded_project(session_id: str = Form(...)):
        """Analyze uploaded project and return stack information."""
        if session_manager is None:
            raise HTTPException(status_code=503, detail="Server not initialized")

        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if session_id not in session_files:
            raise HTTPException(status_code=404, detail="No files uploaded for this session")

        upload_dir = session_files[session_id]

        # Analyze the project structure
        analysis = analyze_project_structure(upload_dir)

        return JSONResponse({
            "status": "success",
            "analysis": analysis,
            "upload_dir": str(upload_dir)
        })

    @app.get("/upload/files/{session_id}")
    async def list_uploaded_files(session_id: str):
        """List all uploaded files for a session."""
        if session_id not in session_files:
            return JSONResponse({"files": [], "message": "No files uploaded"})

        upload_dir = session_files[session_id]
        files = []
        for f in upload_dir.rglob('*'):
            if f.is_file():
                files.append({
                    "name": f.name,
                    "path": str(f.relative_to(upload_dir)),
                    "size": f.stat().st_size
                })

        return JSONResponse({"files": files, "upload_dir": str(upload_dir)})

    def analyze_project_structure(project_path: Path) -> dict:
        """Analyze project to detect stack, frameworks, and structure."""
        analysis = {
            "languages": [],
            "frameworks": [],
            "package_managers": [],
            "config_files": [],
            "structure": {},
            "entry_points": [],
            "file_count": 0,
            "recommendations": []
        }

        # File extension counters
        ext_count: dict[str, int] = {}

        # Known config/package files
        config_patterns = {
            "package.json": ("JavaScript/Node.js", "npm"),
            "package-lock.json": ("JavaScript/Node.js", "npm"),
            "yarn.lock": ("JavaScript/Node.js", "yarn"),
            "pnpm-lock.yaml": ("JavaScript/Node.js", "pnpm"),
            "pyproject.toml": ("Python", "uv/pip"),
            "requirements.txt": ("Python", "pip"),
            "setup.py": ("Python", "setuptools"),
            "Pipfile": ("Python", "pipenv"),
            "Cargo.toml": ("Rust", "cargo"),
            "go.mod": ("Go", "go modules"),
            "Gemfile": ("Ruby", "bundler"),
            "composer.json": ("PHP", "composer"),
            "pom.xml": ("Java", "maven"),
            "build.gradle": ("Java/Kotlin", "gradle"),
            "*.csproj": ("C#/.NET", "dotnet"),
            "*.sln": ("C#/.NET", "Visual Studio"),
            "CMakeLists.txt": ("C/C++", "cmake"),
            "Makefile": ("C/C++", "make"),
            "tsconfig.json": ("TypeScript", None),
            "vite.config.*": ("Vite", None),
            "webpack.config.*": ("Webpack", None),
            "next.config.*": ("Next.js", None),
            "nuxt.config.*": ("Nuxt.js", None),
            "angular.json": ("Angular", None),
            ".eslintrc*": ("ESLint", None),
            ".prettierrc*": ("Prettier", None),
            "Dockerfile": ("Docker", None),
            "docker-compose.*": ("Docker Compose", None),
        }

        for f in project_path.rglob('*'):
            if f.is_file():
                analysis["file_count"] += 1

                # Count extensions
                ext = f.suffix.lower()
                ext_count[ext] = ext_count.get(ext, 0) + 1

                # Check for config files
                for pattern, (lang, pkg) in config_patterns.items():
                    if pattern.startswith('*'):
                        if f.name.endswith(pattern[1:]):
                            if lang not in analysis["languages"]:
                                analysis["languages"].append(lang)
                            if pkg and pkg not in analysis["package_managers"]:
                                analysis["package_managers"].append(pkg)
                            analysis["config_files"].append(f.name)
                    elif '*' in pattern:
                        base = pattern.split('*')[0]
                        if f.name.startswith(base):
                            if lang not in analysis["frameworks"]:
                                analysis["frameworks"].append(lang)
                            analysis["config_files"].append(f.name)
                    elif f.name == pattern:
                        if lang and lang not in analysis["languages"]:
                            analysis["languages"].append(lang)
                        if pkg and pkg not in analysis["package_managers"]:
                            analysis["package_managers"].append(pkg)
                        analysis["config_files"].append(f.name)

                # Detect entry points
                if f.name in ["main.py", "app.py", "index.js", "index.ts", "main.rs", "main.go", "Program.cs", "main.cpp"]:
                    analysis["entry_points"].append(str(f.relative_to(project_path)))

        # Determine primary languages from file extensions
        lang_map = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".tsx": "TypeScript/React",
            ".jsx": "JavaScript/React",
            ".rs": "Rust",
            ".go": "Go",
            ".java": "Java",
            ".cs": "C#",
            ".cpp": "C++",
            ".c": "C",
            ".rb": "Ruby",
            ".php": "PHP",
            ".vue": "Vue.js",
            ".svelte": "Svelte",
        }

        for ext, count in sorted(ext_count.items(), key=lambda x: -x[1])[:5]:
            if ext in lang_map and lang_map[ext] not in analysis["languages"]:
                analysis["languages"].append(lang_map[ext])

        # Build structure summary (top-level directories)
        for item in project_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                file_count = sum(1 for _ in item.rglob('*') if _.is_file())
                analysis["structure"][item.name] = file_count

        # Add recommendations
        if "Python" in analysis["languages"]:
            analysis["recommendations"].append("Consider using type hints for better code quality")
        if "TypeScript" in analysis["languages"] or "JavaScript" in analysis["languages"]:
            if "ESLint" not in str(analysis["config_files"]):
                analysis["recommendations"].append("Consider adding ESLint for code linting")

        return analysis

    @app.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest) -> ChatResponse:
        """Send a message and get a response (using v2 agent with intelligence features)."""
        if session_manager is None:
            raise HTTPException(status_code=503, detail="Server not initialized")

        # Get or create session
        session = session_manager.get_or_create_session(request.session_id)

        try:
            # Run the v2 agent (returns TurnResult with metadata)
            result = session.agent.run_turn(request.message)

            # Clean response for display (remove tool XML)
            display_response = re.sub(
                r'<tool[^>]*>.*?</tool>', '', result.response, flags=re.DOTALL
            )
            display_response = re.sub(
                r'<tool_result[^>]*>.*?</tool_result>', '', display_response, flags=re.DOTALL
            )
            display_response = re.sub(
                r'\[Tool results received, continuing\.\.\.\]', '', display_response
            )
            display_response = display_response.strip()

            # Convert tool calls from v2 format
            tool_calls = []
            for tc in result.tool_calls:
                tool_calls.append(ToolCallResponse(
                    name=tc.get("name", ""),
                    params=tc.get("params", {}),
                    result="",  # Result is in the response text
                    success=tc.get("success", True),
                ))

            return ChatResponse(
                response=display_response,
                session_id=session.id,
                tool_calls=tool_calls,
                status="success",
            )

        except Exception as e:
            logger.exception(f"Error processing chat: {e}")
            return ChatResponse(
                response="",
                session_id=session.id,
                status="error",
                error=str(e),
            )

    @app.post("/chat/stream")
    async def chat_stream(request: ChatRequest):
        """Stream chat responses using Server-Sent Events."""
        if session_manager is None:
            raise HTTPException(status_code=503, detail="Server not initialized")

        session = session_manager.get_or_create_session(request.session_id)

        async def generate():
            try:
                # Send session info first
                yield f"data: {json.dumps({'type': 'session', 'session_id': session.id})}\n\n"

                # Build messages for LLM
                from src.agent.prompts_v2 import build_dynamic_prompt, PromptContext, detect_task_type
                from src.agent.router import ModelSize

                task_type = detect_task_type(request.message)
                yield f"data: {json.dumps({'type': 'status', 'task_type': task_type.value})}\n\n"

                # Add user message to history
                from src.agent.core_v2 import Message
                session.agent.history.append(Message(role="user", content=request.message))

                # Build system prompt
                system_prompt = session.agent._build_prompt(
                    request.message,
                    session.agent._retrieve_context(request.message)
                )

                messages = [{"role": "system", "content": system_prompt}]
                for msg in session.agent.history:
                    messages.append({"role": msg.role, "content": msg.content})

                # Stream from LLM
                full_response = ""
                for chunk in session.agent.llm.chat_stream(
                    messages=messages,
                    temperature=session.agent.config.temperature,
                ):
                    full_response += chunk
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                    await asyncio.sleep(0)  # Allow other tasks to run

                # Add assistant response to history
                session.agent.history.append(Message(role="assistant", content=full_response))

                # Send completion
                yield f"data: {json.dumps({'type': 'done', 'full_response': full_response})}\n\n"

            except Exception as e:
                logger.exception(f"Streaming error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    @app.websocket("/ws/{session_id}")
    async def websocket_chat(websocket: WebSocket, session_id: str) -> None:
        """WebSocket endpoint for real-time chat."""
        if session_manager is None:
            await websocket.close(code=1011)
            return

        await websocket.accept()

        session = session_manager.get_or_create_session(session_id)

        try:
            while True:
                # Receive message
                data = await websocket.receive_json()
                message = data.get("message", "")

                if not message:
                    continue

                # Send "thinking" status
                await websocket.send_json({
                    "type": "status",
                    "status": "thinking",
                })

                try:
                    # Run v2 agent (returns TurnResult)
                    result = session.agent.run_turn(message)

                    # Clean and send response
                    display_response = re.sub(
                        r'<tool[^>]*>.*?</tool>', '', result.response, flags=re.DOTALL
                    )
                    display_response = re.sub(
                        r'<tool_result[^>]*>.*?</tool_result>', '', display_response, flags=re.DOTALL
                    )
                    display_response = re.sub(
                        r'\[Tool results received, continuing\.\.\.\]', '', display_response
                    )

                    await websocket.send_json({
                        "type": "response",
                        "response": display_response.strip(),
                        "session_id": session.id,
                        "model_used": result.model_used,
                        "task_type": result.task_type.value,
                    })

                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "error": str(e),
                    })

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: {session_id}")

    return app

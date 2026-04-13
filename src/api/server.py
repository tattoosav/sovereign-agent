"""FastAPI server for Sovereign Agent."""

import asyncio
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File, Form, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import tempfile
import shutil
import zipfile

from src.api.auth import AuthManager, APIKey
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


class CreateKeyRequest(BaseModel):
    name: str
    rate_limit: int = 30
    daily_limit: int = 1000


class KeyResponse(BaseModel):
    key: str = ""
    name: str = ""
    message: str = ""


# Global managers
session_manager: SessionManager | None = None
auth_manager: AuthManager | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle."""
    global session_manager, auth_manager
    logger.info("Starting Sovereign Agent API server")
    session_manager = SessionManager()
    auth_manager = AuthManager()

    # Create a default admin key if none exist
    if not auth_manager.list_keys():
        admin_key = auth_manager.create_key("admin", rate_limit=120, daily_limit=10000)
        logger.info(f"Created default admin API key: {admin_key}")
        print(f"\n  Default API key: {admin_key}\n  Save this — it won't be shown again.\n")

    yield
    logger.info("Shutting down Sovereign Agent API server")
    if session_manager:
        session_manager.close_all()


async def get_api_key(authorization: Optional[str] = Header(None)) -> APIKey:
    """
    FastAPI dependency that validates the API key from the Authorization header.

    If SOVEREIGN_AUTH_DISABLED=1 is set, auth is bypassed (for local dev).
    """
    if os.getenv("SOVEREIGN_AUTH_DISABLED", "").strip() in ("1", "true"):
        # Return a fake unlimited key for local dev
        return APIKey(
            key_hash="dev", name="dev", created_at=0,
            rate_limit=9999, daily_limit=999999,
            is_active=True, total_requests=0, total_tokens=0
        )

    if auth_manager is None:
        raise HTTPException(status_code=503, detail="Server not initialized")

    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header. Use: Authorization: Bearer sk-...")

    # Accept "Bearer sk-..." or plain "sk-..."
    token = authorization.removeprefix("Bearer ").strip()

    key = auth_manager.validate_key(token)
    if key is None:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")

    # Check rate limit
    rate_check = auth_manager.check_rate_limit(key)
    if not rate_check.allowed:
        raise HTTPException(
            status_code=429,
            detail=rate_check.reason,
            headers={"Retry-After": str(int(rate_check.reset_at - __import__('time').time()))}
        )

    return key


async def get_admin_key(api_key: APIKey = Depends(get_api_key)) -> APIKey:
    """Dependency that requires the first (admin) key."""
    if auth_manager is None:
        raise HTTPException(status_code=503, detail="Server not initialized")
    keys = auth_manager.list_keys()
    if keys and api_key.key_hash != keys[-1].key_hash:  # Last in list = oldest = admin
        raise HTTPException(status_code=403, detail="Admin access required")
    return api_key


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Sovereign Agent API",
        description="AI Coding Agent API — authenticate with Bearer token",
        version="0.2.0",
        lifespan=lifespan,
    )

    # CORS — restrictive by default, override with env var
    allowed_origins = os.getenv("SOVEREIGN_CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # Mount static files
    static_path = Path(__file__).parent / "static"
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    # ──────────────────────────── Public routes ────────────────────────────

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

    # ──────────────────────────── Admin routes ─────────────────────────────

    @app.post("/admin/keys", response_model=KeyResponse)
    async def create_api_key(req: CreateKeyRequest, _: APIKey = Depends(get_admin_key)) -> KeyResponse:
        """Create a new API key (admin only)."""
        if auth_manager is None:
            raise HTTPException(status_code=503, detail="Server not initialized")
        raw_key = auth_manager.create_key(req.name, req.rate_limit, req.daily_limit)
        return KeyResponse(key=raw_key, name=req.name, message="Key created. Store it safely — it won't be shown again.")

    @app.get("/admin/keys")
    async def list_api_keys(_: APIKey = Depends(get_admin_key)):
        """List all API keys (admin only). Raw keys are never returned."""
        if auth_manager is None:
            raise HTTPException(status_code=503, detail="Server not initialized")
        keys = auth_manager.list_keys()
        return [{
            "name": k.name,
            "created_at": k.created_at,
            "rate_limit": k.rate_limit,
            "daily_limit": k.daily_limit,
            "is_active": k.is_active,
            "total_requests": k.total_requests,
            "total_tokens": k.total_tokens,
            "key_hash_prefix": k.key_hash[:12] + "...",
        } for k in keys]

    @app.get("/admin/usage/{key_hash_prefix}")
    async def get_usage(key_hash_prefix: str, hours: int = 24, _: APIKey = Depends(get_admin_key)):
        """Get usage stats for a key by hash prefix (admin only)."""
        if auth_manager is None:
            raise HTTPException(status_code=503, detail="Server not initialized")
        keys = auth_manager.list_keys()
        for k in keys:
            if k.key_hash.startswith(key_hash_prefix):
                return auth_manager.get_usage_stats(k.key_hash, hours)
        raise HTTPException(status_code=404, detail="Key not found")

    # ──────────────────────── Authenticated routes ─────────────────────────

    @app.post("/session/new", response_model=SessionResponse)
    async def create_session(api_key: APIKey = Depends(get_api_key)) -> SessionResponse:
        """Create a new session."""
        if session_manager is None:
            raise HTTPException(status_code=503, detail="Server not initialized")
        session_id = session_manager.create_session()
        return SessionResponse(session_id=session_id, message="Session created successfully")

    @app.post("/session/{session_id}/reset", response_model=SessionResponse)
    async def reset_session(session_id: str, api_key: APIKey = Depends(get_api_key)) -> SessionResponse:
        """Reset a session's conversation history."""
        if session_manager is None:
            raise HTTPException(status_code=503, detail="Server not initialized")
        if not session_manager.reset_session(session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        return SessionResponse(session_id=session_id, message="Session reset successfully")

    @app.delete("/session/{session_id}")
    async def delete_session(session_id: str, api_key: APIKey = Depends(get_api_key)) -> SessionResponse:
        """Delete a session."""
        if session_manager is None:
            raise HTTPException(status_code=503, detail="Server not initialized")
        if not session_manager.delete_session(session_id):
            raise HTTPException(status_code=404, detail="Session not found")
        return SessionResponse(session_id=session_id, message="Session deleted successfully")

    @app.get("/session/{session_id}/history", response_model=HistoryResponse)
    async def get_history(session_id: str, api_key: APIKey = Depends(get_api_key)) -> HistoryResponse:
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
    async def list_tools(api_key: APIKey = Depends(get_api_key)) -> ToolsResponse:
        """List all available tools."""
        if session_manager is None:
            raise HTTPException(status_code=503, detail="Server not initialized")
        temp_id = session_manager.create_session()
        session = session_manager.get_session(temp_id)
        if not session:
            raise HTTPException(status_code=500, detail="Failed to get tools")
        tools = [
            ToolInfo(name=tool.name, description=tool.description, parameters=tool.parameters)
            for tool in session.agent.tools.all_tools()
        ]
        session_manager.delete_session(temp_id)
        return ToolsResponse(tools=tools)

    @app.get("/session/{session_id}/metrics", response_model=MetricsResponse)
    async def get_metrics(session_id: str, api_key: APIKey = Depends(get_api_key)) -> MetricsResponse:
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
        session_id: str = Form(...),
        api_key: APIKey = Depends(get_api_key),
    ):
        """Upload files for the agent to analyze."""
        if session_manager is None:
            raise HTTPException(status_code=503, detail="Server not initialized")

        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        if session_id not in session_files:
            session_files[session_id] = Path(tempfile.mkdtemp(prefix=f"sovereign_{session_id[:8]}_"))

        upload_dir = session_files[session_id]
        uploaded = []

        for file in files:
            if not file.filename:
                continue

            # Sanitize filename — strip path traversal
            safe_name = Path(file.filename).name
            if not safe_name or safe_name.startswith('.'):
                continue

            if safe_name.endswith('.zip'):
                zip_path = upload_dir / safe_name
                with open(zip_path, "wb") as f:
                    shutil.copyfileobj(file.file, f)

                extract_dir = upload_dir / safe_name.replace('.zip', '')
                extract_dir.mkdir(exist_ok=True)

                with zipfile.ZipFile(zip_path, 'r') as zf:
                    # Validate all members before extracting
                    for member in zf.infolist():
                        if '..' in member.filename or member.filename.startswith('/'):
                            raise HTTPException(status_code=400, detail=f"Invalid path in zip: {member.filename}")
                    zf.extractall(extract_dir)

                count = sum(1 for _ in extract_dir.rglob('*') if _.is_file())
                uploaded.append({"name": safe_name, "type": "zip", "files_extracted": count, "path": str(extract_dir)})
                zip_path.unlink()
            else:
                file_path = upload_dir / safe_name
                with open(file_path, "wb") as f:
                    shutil.copyfileobj(file.file, f)
                uploaded.append({"name": safe_name, "type": "file", "path": str(file_path)})

        if auth_manager and api_key.key_hash != "dev":
            auth_manager.record_usage(api_key, "/upload")

        return JSONResponse({
            "status": "success",
            "uploaded": uploaded,
            "upload_dir": str(upload_dir),
            "message": f"Uploaded {len(uploaded)} file(s). Use 'analyze project at {upload_dir}' to start."
        })

    @app.get("/upload/files/{session_id}")
    async def list_uploaded_files(session_id: str, api_key: APIKey = Depends(get_api_key)):
        """List all uploaded files for a session."""
        if session_id not in session_files:
            return JSONResponse({"files": [], "message": "No files uploaded"})
        upload_dir = session_files[session_id]
        files = []
        for f in upload_dir.rglob('*'):
            if f.is_file():
                files.append({"name": f.name, "path": str(f.relative_to(upload_dir)), "size": f.stat().st_size})
        return JSONResponse({"files": files, "upload_dir": str(upload_dir)})

    @app.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest, api_key: APIKey = Depends(get_api_key)) -> ChatResponse:
        """Send a message and get a response."""
        if session_manager is None:
            raise HTTPException(status_code=503, detail="Server not initialized")

        session = session_manager.get_or_create_session(request.session_id)
        import time as _time
        start = _time.time()

        try:
            result = session.agent.run_turn(request.message)

            display_response = re.sub(r'<tool[^>]*>.*?</tool>', '', result.response, flags=re.DOTALL)
            display_response = re.sub(r'<tool_result[^>]*>.*?</tool_result>', '', display_response, flags=re.DOTALL)
            display_response = re.sub(r'\[Tool results received, continuing\.\.\.\]', '', display_response)
            display_response = display_response.strip()

            tool_calls = [
                ToolCallResponse(
                    name=tc.get("name", ""), params=tc.get("params", {}),
                    result="", success=tc.get("success", True),
                )
                for tc in result.tool_calls
            ]

            # Record usage
            duration_ms = int((_time.time() - start) * 1000)
            if auth_manager and api_key.key_hash != "dev":
                auth_manager.record_usage(api_key, "/chat", result.tokens_used, duration_ms)

            return ChatResponse(
                response=display_response, session_id=session.id,
                tool_calls=tool_calls, status="success",
            )

        except Exception as e:
            logger.exception(f"Error processing chat: {e}")
            error_msg = str(e)
            if "timeout" in error_msg.lower():
                error_msg = f"LLM timeout: {error_msg}. Model may be overloaded."
            elif "connection" in error_msg.lower():
                error_msg = f"Connection error: {error_msg}. Check if LLM backend is running."
            return ChatResponse(response="", session_id=session.id, status="error", error=error_msg)

    @app.post("/chat/stream")
    async def chat_stream(request: ChatRequest, api_key: APIKey = Depends(get_api_key)):
        """Stream chat responses using Server-Sent Events."""
        if session_manager is None:
            raise HTTPException(status_code=503, detail="Server not initialized")

        session = session_manager.get_or_create_session(request.session_id)

        async def generate():
            try:
                yield f"data: {json.dumps({'type': 'session', 'session_id': session.id})}\n\n"

                from src.agent.prompts_v2 import detect_task_type
                from src.agent.core_v2 import Message

                task_type = detect_task_type(request.message)
                yield f"data: {json.dumps({'type': 'status', 'task_type': task_type.value})}\n\n"

                session.agent.history.append(Message(role="user", content=request.message))

                system_prompt = session.agent._build_prompt(
                    request.message, session.agent._retrieve_context(request.message)
                )

                messages = [{"role": "system", "content": system_prompt}]
                for msg in session.agent.history:
                    messages.append({"role": msg.role, "content": msg.content})

                full_response = ""
                for chunk in session.agent.llm.chat_stream(
                    messages=messages, temperature=session.agent.config.temperature,
                ):
                    full_response += chunk
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                    await asyncio.sleep(0)

                session.agent.history.append(Message(role="assistant", content=full_response))
                yield f"data: {json.dumps({'type': 'done', 'full_response': full_response})}\n\n"

            except Exception as e:
                logger.exception(f"Streaming error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

        return StreamingResponse(
            generate(), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
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
                data = await websocket.receive_json()
                message = data.get("message", "")
                if not message:
                    continue

                await websocket.send_json({"type": "status", "status": "thinking"})

                try:
                    result = session.agent.run_turn(message)

                    display_response = re.sub(r'<tool[^>]*>.*?</tool>', '', result.response, flags=re.DOTALL)
                    display_response = re.sub(r'<tool_result[^>]*>.*?</tool_result>', '', display_response, flags=re.DOTALL)
                    display_response = re.sub(r'\[Tool results received, continuing\.\.\.\]', '', display_response)

                    await websocket.send_json({
                        "type": "response",
                        "response": display_response.strip(),
                        "session_id": session.id,
                        "model_used": result.model_used,
                        "task_type": result.task_type.value,
                    })

                except Exception as e:
                    await websocket.send_json({"type": "error", "error": str(e)})

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: {session_id}")

    return app

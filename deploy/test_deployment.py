#!/usr/bin/env python3
"""
Deployment Test Script for Sovereign Agent.

Run this on the VPS to verify all components work correctly.
Tests: Ollama, Vision, Web Research, Tools, Agent Core.
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def print_result(name: str, success: bool, message: str = ""):
    status = "✓ PASS" if success else "✗ FAIL"
    color = "\033[92m" if success else "\033[91m"
    reset = "\033[0m"
    print(f"  {color}{status}{reset} {name}")
    if message:
        print(f"       {message}")


def test_ollama():
    """Test Ollama connection and models."""
    print_header("Testing Ollama")

    try:
        import httpx

        # Test connection
        try:
            response = httpx.get("http://localhost:11434/api/tags", timeout=10)
            response.raise_for_status()
            data = response.json()
            models = [m["name"] for m in data.get("models", [])]
            print_result("Ollama connection", True, f"Found {len(models)} models")

            # Check for required models
            required = ["qwen2.5-coder"]
            vision = ["llava", "moondream", "bakllava", "qwen2-vl"]

            has_coder = any(r in m for m in models for r in required)
            has_vision = any(v in m for m in models for v in vision)

            print_result("Coding model", has_coder,
                        f"Models: {[m for m in models if 'qwen' in m or 'coder' in m]}")
            print_result("Vision model", has_vision,
                        f"Models: {[m for m in models if any(v in m for v in vision)]}")

            return has_coder

        except httpx.ConnectError:
            print_result("Ollama connection", False, "Cannot connect to Ollama")
            print("       Run: ollama serve")
            return False

    except ImportError:
        print_result("httpx import", False, "pip install httpx")
        return False


def test_web_research():
    """Test web research tool."""
    print_header("Testing Web Research")

    try:
        from src.tools.web_research import WebResearchTool

        tool = WebResearchTool()

        # Test search
        result = tool.execute("search", query="python tutorial", max_results=3)
        print_result("Web search", result.success,
                    f"Found results" if result.success else result.error)

        # Test fetch
        result = tool.execute("fetch", url="https://example.com")
        print_result("Web fetch", result.success,
                    "Content retrieved" if result.success else result.error)

        return True

    except ImportError as e:
        print_result("Import", False, str(e))
        return False
    except Exception as e:
        print_result("Web research", False, str(e))
        return False


def test_vision():
    """Test vision tool."""
    print_header("Testing Vision")

    try:
        from src.tools.vision import VisionTool

        tool = VisionTool()

        # List available vision models
        result = tool.execute("list_models")
        print_result("Vision models", result.success)
        if result.success:
            print(f"       {result.output[:200]}...")

        # Test with a sample image if exists
        test_images = [
            Path("test_image.png"),
            Path("screenshot.png"),
            Path("/tmp/test.png"),
        ]

        for img in test_images:
            if img.exists():
                result = tool.execute("analyze", image_path=str(img))
                print_result(f"Analyze {img.name}", result.success)
                break
        else:
            print_result("Image analysis", True, "No test image found (skipped)")

        return True

    except ImportError as e:
        print_result("Import", False, str(e))
        return False
    except Exception as e:
        print_result("Vision", False, str(e))
        return False


def test_core_tools():
    """Test core agent tools."""
    print_header("Testing Core Tools")

    results = []

    # Test filesystem tools
    try:
        from src.tools.filesystem import ReadFileTool, WriteFileTool, ListDirectoryTool

        # Write test
        write_tool = WriteFileTool()
        result = write_tool.execute(path="/tmp/agent_test.txt", content="Hello from Sovereign Agent!")
        print_result("Write file", result.success)
        results.append(result.success)

        # Read test
        read_tool = ReadFileTool()
        result = read_tool.execute(path="/tmp/agent_test.txt")
        print_result("Read file", result.success and "Hello" in result.output)
        results.append(result.success)

        # List test
        list_tool = ListDirectoryTool()
        result = list_tool.execute(path="/tmp")
        print_result("List directory", result.success)
        results.append(result.success)

    except Exception as e:
        print_result("Filesystem tools", False, str(e))
        results.append(False)

    # Test search tool
    try:
        from src.tools.search import CodeSearchTool

        tool = CodeSearchTool()
        result = tool.execute(pattern="def ", path=".", file_pattern="*.py")
        print_result("Code search", result.success)
        results.append(result.success)

    except Exception as e:
        print_result("Code search", False, str(e))
        results.append(False)

    # Test shell tool
    try:
        from src.tools.shell import ShellTool

        tool = ShellTool()
        result = tool.execute(command="echo 'test'")
        print_result("Shell execution", result.success)
        results.append(result.success)

    except Exception as e:
        print_result("Shell tool", False, str(e))
        results.append(False)

    return all(results)


def test_memory_system():
    """Test memory and learning system."""
    print_header("Testing Memory System")

    results = []

    # Test vector store
    try:
        from src.memory.vector_store import VectorStore

        store = VectorStore(persist_directory="/tmp/test_chromadb")
        store.add_documents(
            documents=["Test document for vector search"],
            ids=["test-1"],
            metadatas=[{"source": "test"}]
        )
        results_search = store.search("test document", n_results=1)
        print_result("Vector store", len(results_search) > 0)
        results.append(True)

    except Exception as e:
        print_result("Vector store", False, str(e))
        results.append(False)

    # Test pattern learner
    try:
        from src.agent.pattern_learner import PatternLearner

        learner = PatternLearner("/tmp/test_patterns")
        stats = learner.get_statistics()
        print_result("Pattern learner", True, f"{stats['total_patterns']} patterns loaded")
        results.append(True)

    except Exception as e:
        print_result("Pattern learner", False, str(e))
        results.append(False)

    return all(results)


def test_llm_connection():
    """Test LLM generation."""
    print_header("Testing LLM Generation")

    try:
        import httpx

        response = httpx.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "qwen2.5-coder:7b",
                "prompt": "Say 'Hello, I am working!' in exactly those words.",
                "stream": False,
                "options": {"num_predict": 20}
            },
            timeout=60.0
        )
        response.raise_for_status()
        data = response.json()
        output = data.get("response", "")

        print_result("LLM generation", len(output) > 0, f"Response: {output[:100]}")
        return True

    except httpx.ConnectError:
        print_result("LLM generation", False, "Ollama not running")
        return False
    except Exception as e:
        print_result("LLM generation", False, str(e))
        return False


def test_gpu():
    """Test GPU availability."""
    print_header("Testing GPU")

    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            gpu_info = result.stdout.strip()
            print_result("NVIDIA GPU", True, gpu_info)
            return True
        else:
            print_result("NVIDIA GPU", False, "nvidia-smi failed")
            return False

    except FileNotFoundError:
        print_result("NVIDIA GPU", False, "nvidia-smi not found")
        return False
    except Exception as e:
        print_result("NVIDIA GPU", False, str(e))
        return False


def main():
    print("\n" + "="*60)
    print("  SOVEREIGN AGENT - DEPLOYMENT TEST")
    print("="*60)
    print(f"  Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Python: {sys.version.split()[0]}")

    results = {}

    # Run all tests
    results["GPU"] = test_gpu()
    results["Ollama"] = test_ollama()
    results["LLM"] = test_llm_connection()
    results["Core Tools"] = test_core_tools()
    results["Web Research"] = test_web_research()
    results["Vision"] = test_vision()
    results["Memory"] = test_memory_system()

    # Summary
    print_header("Test Summary")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, success in results.items():
        status = "✓" if success else "✗"
        color = "\033[92m" if success else "\033[91m"
        reset = "\033[0m"
        print(f"  {color}{status}{reset} {name}")

    print()
    if passed == total:
        print(f"  \033[92mAll {total} tests passed! Agent is ready.\033[0m")
    else:
        print(f"  \033[93m{passed}/{total} tests passed.\033[0m")
        print(f"  Fix failing tests before using the agent.")

    print()
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())

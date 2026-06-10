"""
Autonomous, self-directed task loop for the air-gapped build.

Watches a filesystem task queue, runs each task to completion through the existing
AgentV2 loop, persists state so it survives reboots, and self-recovers from faults so
it can run unattended indefinitely. No network, no human in the loop.

Queue layout (under working_dir/tasks):
    inbox/   operator drops *.json or *.md task files
    active/  task currently being processed
    done/    completed task + <id>.result.md
    failed/  failed task + <id>.error.log
    state/   heartbeat.json

Run: python -m src.autonomous --working-dir <dir>
"""

import json
import logging
import os
import shutil
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from src.agent import AgentV2, AgentConfigV2
from src.agent.core_v2 import Message
from src.core import assert_airgap, load_config
from src.core.egress_guard import EgressViolation
from src.memory import KnowledgeBase, VectorStore
from src.memory.conversation_store import ConversationStore
from src.tools import build_registry

logger = logging.getLogger(__name__)


@dataclass
class Task:
    """A unit of work picked up from the queue."""
    id: str
    prompt: str
    path: Path


@dataclass
class AutonomousConfig:
    """Configuration for the autonomous runner."""
    working_dir: Path
    poll_interval: float = 5.0
    session_id: str = "autonomous-main"
    max_task_seconds: float = 1800.0  # 30 min hard ceiling per task
    done_retention: int = 500          # keep newest N results, prune older
    min_free_mb: int = 500             # pause intake below this free space
    ollama_wait_max: float = 300.0     # bounded backoff waiting for Ollama


class AutonomousRunner:
    """Runs the agent autonomously against a durable filesystem queue."""

    def __init__(self, config: AutonomousConfig) -> None:
        self.config = config
        self._stop = False
        self._app_config = load_config()
        self._dirs = self._init_dirs(config.working_dir)
        self._store = ConversationStore(
            storage_dir=config.working_dir / ".sovereign" / "conversations"
        )
        self.agent = self._build_agent(config.working_dir)
        self._load_or_resume()

    # ---- setup -----------------------------------------------------------

    def _init_dirs(self, working_dir: Path) -> dict[str, Path]:
        """Create the queue directories; return a name->path map."""
        names = ["inbox", "active", "done", "failed", "state"]
        dirs = {n: working_dir / "tasks" / n for n in names}
        for path in dirs.values():
            path.mkdir(parents=True, exist_ok=True)
        return dirs

    def _build_agent(self, working_dir: Path) -> AgentV2:
        """Build an air-gap self-checked AgentV2 with the local toolset."""
        assert_airgap(self._app_config)  # fail-fast if egress is reachable
        tools = build_registry(
            working_dir,
            shell_timeout=300,
            shell_allowlist=self._app_config.airgap.shell_allowlist_mode,
            shell_allowed=self._app_config.airgap.shell_allowed_commands,
            ollama_url=self._app_config.llm.ollama_url,
        )
        agent_config = AgentConfigV2(
            model=self._app_config.llm.model,
            ollama_url=self._app_config.llm.ollama_url,
            max_iterations=self._app_config.agent.max_iterations,
        )
        return AgentV2(
            config=agent_config,
            tools=tools,
            vector_store=VectorStore(),
            knowledge_base=KnowledgeBase(),
        )

    def _load_or_resume(self) -> None:
        """Replay persisted history and re-queue any interrupted task."""
        session = self._store.get_session(self.config.session_id)
        if session:
            self.agent.history = [
                Message(role=m.role, content=m.content) for m in session.messages
            ]
            logger.info(f"Resumed {len(session.messages)} messages from prior run")
        for leftover in self._dirs["active"].iterdir():
            self._move(leftover, self._dirs["inbox"] / leftover.name)
            logger.info(f"Re-queued interrupted task: {leftover.name}")

    # ---- durable file helpers (E4) --------------------------------------

    @staticmethod
    def _atomic_write(path: Path, text: str) -> None:
        """Write a file atomically (tmp + os.replace) to survive power loss."""
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)

    @staticmethod
    def _move(src: Path, dst: Path) -> None:
        """Atomically move a queue file."""
        os.replace(src, dst)

    # ---- queue -----------------------------------------------------------

    def _next_task(self) -> Task | None:
        """Claim the oldest inbox file by moving it into active/."""
        candidates = sorted(
            (p for p in self._dirs["inbox"].iterdir() if p.is_file()),
            key=lambda p: p.stat().st_mtime,
        )
        for src in candidates:
            dst = self._dirs["active"] / src.name
            try:
                self._move(src, dst)
            except OSError:
                continue  # another race lost; try next
            return self._parse_task(dst)
        return None

    def _parse_task(self, path: Path) -> Task:
        """Parse a .json or .md task file into a Task (corruption-tolerant)."""
        stem = path.stem
        if path.suffix == ".json":
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return Task(id=data.get("id", stem), prompt=data["prompt"], path=path)
            except Exception as e:
                logger.error(f"Bad task JSON {path.name}: {e}")
                return Task(id=stem, prompt="", path=path)
        return Task(id=stem, prompt=path.read_text(encoding="utf-8"), path=path)

    # ---- execution (E1, E2) ---------------------------------------------

    def _run_turn_with_timeout(self, prompt: str) -> object:
        """Run one agent turn with a hard wall-clock budget (hang protection)."""
        box: dict[str, object] = {}

        def worker() -> None:
            try:
                box["result"] = self.agent.run_turn(prompt)
            except BaseException as e:  # noqa: BLE001 - isolate every fault
                box["error"] = e

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        thread.join(self.config.max_task_seconds)
        if thread.is_alive():
            raise TimeoutError(f"Task exceeded {self.config.max_task_seconds}s budget")
        if "error" in box:
            raise box["error"]  # type: ignore[misc]
        return box["result"]

    def _run_task(self, task: Task) -> None:
        """Run a single task, persist state, and route the result file."""
        if not task.prompt.strip():
            self._fail(task, "Empty or unparseable task prompt")
            return
        try:
            self._store.add_message(self.config.session_id, "user", task.prompt)
            result = self._run_turn_with_timeout(task.prompt)
            response = getattr(result, "response", str(result))
            self._store.add_message(self.config.session_id, "assistant", response)
            self._write_result(task, result, response)
        except Exception as e:  # noqa: BLE001 - never let one task kill the loop
            self._fail(task, f"{e}\n{traceback.format_exc()}")

    def _write_result(self, task: Task, result: object, response: str) -> None:
        """Write <id>.result.md and move the task into done/."""
        files = getattr(result, "tool_calls", [])
        touched = sorted({c.get("params", {}).get("path", "") for c in files if c})
        body = (
            f"# Task {task.id}\n\nModel: {getattr(result, 'model_used', '?')} | "
            f"Iterations: {getattr(result, 'iterations', '?')}\n\n"
            f"## Response\n\n{response}\n\n"
            f"## Files touched\n\n" + "\n".join(f"- {f}" for f in touched if f)
        )
        self._atomic_write(self._dirs["done"] / f"{task.id}.result.md", body)
        self._move(task.path, self._dirs["done"] / task.path.name)
        logger.info(f"Task {task.id} completed")

    def _fail(self, task: Task, error: str) -> None:
        """Route a failed task into failed/ with an error log."""
        self._atomic_write(self._dirs["failed"] / f"{task.id}.error.log", error)
        dst = self._dirs["failed"] / task.path.name
        try:
            self._move(task.path, dst)
        except OSError:
            pass
        logger.error(f"Task {task.id} failed: {error.splitlines()[0]}")

    # ---- liveness + resource hygiene (E3, E5, E7) -----------------------

    def _write_heartbeat(self, current: str | None) -> None:
        """Record liveness so an operator can verify health on the box."""
        beat = {
            "ts": time.time(),
            "pid": os.getpid(),
            "current_task": current,
            "stats": self._store.get_stats(),
        }
        self._atomic_write(self._dirs["state"] / "heartbeat.json", json.dumps(beat, indent=2))

    def _wait_for_ollama(self) -> None:
        """Bounded backoff until the local model backend is reachable."""
        waited, delay = 0.0, 2.0
        while not self._stop and not self.agent.llm.is_available():
            logger.warning("Ollama unavailable; waiting for backend to recover...")
            time.sleep(delay)
            waited += delay
            delay = min(delay * 2, 30.0)
            if waited >= self.config.ollama_wait_max:
                return

    def _disk_ok(self) -> bool:
        """Pause intake if free disk space is below the safety threshold."""
        free_mb = shutil.disk_usage(self.config.working_dir).free / (1024 * 1024)
        if free_mb < self.config.min_free_mb:
            logger.warning(f"Low disk space ({free_mb:.0f}MB); pausing task intake")
            return False
        return True

    def _prune_done(self) -> None:
        """Trim done/ result files beyond the retention window."""
        results = sorted(
            self._dirs["done"].glob("*.result.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for stale in results[self.config.done_retention:]:
            stale.unlink(missing_ok=True)

    # ---- main loop (E1) --------------------------------------------------

    def stop(self) -> None:
        """Request graceful shutdown."""
        self._stop = True

    def run_forever(self) -> None:
        """Pick up and run tasks until stopped; never exit on a task fault."""
        logger.info(f"Autonomous runner started (working_dir={self.config.working_dir})")
        while not self._stop:
            try:
                self._tick()
            except BaseException as e:  # noqa: BLE001 - loop must survive anything
                logger.exception(f"Loop error (continuing): {e}")
                time.sleep(self.config.poll_interval)
        self.agent.close()
        logger.info("Autonomous runner stopped")

    def _tick(self) -> None:
        """One iteration: heartbeat, claim a task, run it, or idle."""
        self._write_heartbeat(current=None)
        if not self._disk_ok():
            time.sleep(self.config.poll_interval)
            return
        task = self._next_task()
        if task is None:
            time.sleep(self.config.poll_interval)
            return
        self._write_heartbeat(current=task.id)
        self._wait_for_ollama()
        self._run_task(task)
        self._prune_done()

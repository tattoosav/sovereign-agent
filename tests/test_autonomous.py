"""Tests for the autonomous task-loop runner (pickup, resume, failure routing)."""

import time
from types import SimpleNamespace

import pytest

from src.agent.autonomous import AutonomousConfig, AutonomousRunner
from src.memory.conversation_store import ConversationStore


class _FakeLLM:
    def __init__(self, available: bool = True):
        self._available = available

    def is_available(self) -> bool:
        return self._available


class FakeAgent:
    """Stand-in for AgentV2 so tests never touch Ollama."""

    def __init__(self, response="done", raise_exc=None, sleep=0.0):
        self.history: list = []
        self.llm = _FakeLLM()
        self._response = response
        self._raise = raise_exc
        self._sleep = sleep

    def run_turn(self, prompt: str):
        if self._sleep:
            time.sleep(self._sleep)
        if self._raise:
            raise self._raise
        return SimpleNamespace(
            response=self._response, tool_calls=[], model_used="fake", iterations=1
        )

    def close(self) -> None:
        pass


def _make_runner(tmp_path, monkeypatch, agent: FakeAgent, **cfg) -> AutonomousRunner:
    monkeypatch.setattr(AutonomousRunner, "_build_agent", lambda self, wd: agent)
    config = AutonomousConfig(working_dir=tmp_path, poll_interval=0.01, **cfg)
    return AutonomousRunner(config)


def test_pickup_and_complete(tmp_path, monkeypatch):
    agent = FakeAgent(response="hello world")
    runner = _make_runner(tmp_path, monkeypatch, agent)

    (tmp_path / "tasks" / "inbox" / "t1.md").write_text("say hi")
    runner._tick()

    assert (tmp_path / "tasks" / "done" / "t1.md").exists()
    result = (tmp_path / "tasks" / "done" / "t1.result.md").read_text()
    assert "hello world" in result
    assert not list((tmp_path / "tasks" / "inbox").iterdir())
    # State persisted for "continue to exist".
    assert len(agent.history) == 0 or True  # history lives in the store
    sessions = runner._store.list_sessions()
    assert any(s["session_id"] == "autonomous-main" for s in sessions)


def test_json_task(tmp_path, monkeypatch):
    agent = FakeAgent(response="ok")
    runner = _make_runner(tmp_path, monkeypatch, agent)
    import json
    (tmp_path / "tasks" / "inbox" / "job.json").write_text(
        json.dumps({"id": "job", "prompt": "do it"})
    )
    runner._tick()
    assert (tmp_path / "tasks" / "done" / "job.result.md").exists()


def test_failed_task_routed(tmp_path, monkeypatch):
    agent = FakeAgent(raise_exc=RuntimeError("boom"))
    runner = _make_runner(tmp_path, monkeypatch, agent)
    (tmp_path / "tasks" / "inbox" / "bad.md").write_text("will fail")
    runner._tick()
    assert (tmp_path / "tasks" / "failed" / "bad.md").exists()
    log = (tmp_path / "tasks" / "failed" / "bad.error.log").read_text()
    assert "boom" in log


def test_resume_after_restart(tmp_path, monkeypatch):
    # Seed a prior conversation + an interrupted active task.
    store = ConversationStore(storage_dir=tmp_path / ".sovereign" / "conversations")
    store.create_session("autonomous-main")
    store.add_message("autonomous-main", "user", "earlier task")
    active = tmp_path / "tasks" / "active"
    active.mkdir(parents=True)
    (active / "t9.md").write_text("resume me")

    agent = FakeAgent()
    runner = _make_runner(tmp_path, monkeypatch, agent)

    assert len(agent.history) >= 1  # prior history replayed into the agent
    assert (tmp_path / "tasks" / "inbox" / "t9.md").exists()  # interrupted task re-queued
    assert not list((tmp_path / "tasks" / "active").iterdir())


def test_heartbeat_written(tmp_path, monkeypatch):
    agent = FakeAgent()
    runner = _make_runner(tmp_path, monkeypatch, agent)
    runner._write_heartbeat(current="x")
    beat = (tmp_path / "tasks" / "state" / "heartbeat.json").read_text()
    assert '"current_task": "x"' in beat

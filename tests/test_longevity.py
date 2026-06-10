"""Longevity / chaos tests: the daemon must self-recover and never crash."""

import shutil

import pytest

from src.agent.autonomous import AutonomousConfig, AutonomousRunner
from src.memory.conversation_store import ConversationStore
from tests.test_autonomous import FakeAgent, _make_runner


def test_task_timeout_routes_to_failed(tmp_path, monkeypatch):
    """A task that runs longer than the budget is abandoned, not fatal."""
    agent = FakeAgent(sleep=0.5)
    runner = _make_runner(tmp_path, monkeypatch, agent, max_task_seconds=0.05)
    (tmp_path / "tasks" / "inbox" / "slow.md").write_text("hang")
    runner._tick()  # must return, not hang
    assert (tmp_path / "tasks" / "failed" / "slow.md").exists()
    log = (tmp_path / "tasks" / "failed" / "slow.error.log").read_text()
    assert "budget" in log.lower()


def test_low_disk_pauses_intake(tmp_path, monkeypatch):
    agent = FakeAgent()
    runner = _make_runner(tmp_path, monkeypatch, agent, min_free_mb=10_000_000)
    fake_usage = type("U", (), {"free": 1024 * 1024})()  # 1 MB free
    monkeypatch.setattr(shutil, "disk_usage", lambda p: fake_usage)
    (tmp_path / "tasks" / "inbox" / "t.md").write_text("work")
    runner._tick()  # should idle, not process
    assert (tmp_path / "tasks" / "inbox" / "t.md").exists()


def test_corrupt_session_does_not_crash_resume(tmp_path, monkeypatch):
    """A corrupt persisted session is tolerated on startup."""
    store = ConversationStore(storage_dir=tmp_path / ".sovereign" / "conversations")
    path = store._get_session_path("autonomous-main")
    path.write_text("{ this is : not valid json ]")
    agent = FakeAgent()
    # Construction must not raise despite the corrupt state file.
    runner = _make_runner(tmp_path, monkeypatch, agent)
    assert runner is not None


def test_many_tasks_complete_without_leak(tmp_path, monkeypatch):
    agent = FakeAgent(response="ok")
    runner = _make_runner(tmp_path, monkeypatch, agent, done_retention=5)
    for i in range(20):
        (tmp_path / "tasks" / "inbox" / f"t{i:02d}.md").write_text(f"task {i}")
    for _ in range(20):
        runner._tick()
    assert not list((tmp_path / "tasks" / "inbox").iterdir())
    assert not list((tmp_path / "tasks" / "active").iterdir())
    # Retention pruning keeps the result dir bounded.
    results = list((tmp_path / "tasks" / "done").glob("*.result.md"))
    assert len(results) <= 5


def test_loop_survives_unexpected_tick_error(tmp_path, monkeypatch):
    """An exception inside a tick is logged and the loop keeps going."""
    agent = FakeAgent()
    runner = _make_runner(tmp_path, monkeypatch, agent)
    calls = {"n": 0}

    def boom_then_stop():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("unexpected")
        runner.stop()

    monkeypatch.setattr(runner, "_tick", boom_then_stop)
    runner.run_forever()  # must not propagate the RuntimeError
    assert calls["n"] >= 2

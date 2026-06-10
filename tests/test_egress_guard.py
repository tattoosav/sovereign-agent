"""Tests for the startup egress self-check."""

import socket

import pytest

from src.core import assert_airgap
from src.core.config import AirgapConfig, Config
from src.core.egress_guard import EgressReport, EgressViolation
import src.core.egress_guard as guard


def _config(enforce: bool = True) -> Config:
    return Config(airgap=AirgapConfig(enforce_egress_check=enforce))


def test_passes_when_airgapped(monkeypatch):
    """No external reachability + Ollama up => clean report, no exception."""
    monkeypatch.setattr(guard, "_ollama_reachable", lambda url: True)

    def refuse(*args, **kwargs):
        raise OSError("network unreachable")

    monkeypatch.setattr(socket, "create_connection", refuse)
    report = assert_airgap(_config(enforce=True))
    assert isinstance(report, EgressReport)
    assert report.external_blocked is True
    assert report.ollama_ok is True


def test_raises_on_detected_egress(monkeypatch):
    """If an external host is reachable and enforce is on, abort."""
    monkeypatch.setattr(guard, "_ollama_reachable", lambda url: True)

    class FakeConn:
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: FakeConn())
    with pytest.raises(EgressViolation):
        assert_airgap(_config(enforce=True))


def test_egress_detected_but_not_enforced(monkeypatch):
    """With enforcement off, egress is reported but does not abort."""
    monkeypatch.setattr(guard, "_ollama_reachable", lambda url: False)

    class FakeConn:
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: FakeConn())
    report = assert_airgap(_config(enforce=False))
    assert report.external_blocked is False

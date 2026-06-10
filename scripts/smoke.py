"""
Offline smoke test for a VM — verifies the stack without needing Ollama/a model.

Checks: air-gap egress report, CRM CRUD + dashboard + backup, and that the web app
mounts the CRM routes. Prints PASS/FAIL per check and exits non-zero on any failure.

Usage:
    uv run python -m scripts.smoke
"""

import sys
import tempfile
from pathlib import Path

_results: list[tuple[str, bool, str]] = []


def check(name: str, fn) -> None:
    try:
        detail = fn()
        _results.append((name, True, detail or ""))
    except Exception as e:  # noqa: BLE001 - smoke test reports, never raises
        _results.append((name, False, str(e)))


def _egress() -> str:
    from src.core import load_config
    from src.core.egress_guard import EgressReport
    import src.core.egress_guard as guard
    # Don't enforce here — a connected test VM would otherwise (correctly) abort.
    cfg = load_config()
    cfg.airgap.enforce_egress_check = False
    report = guard.assert_airgap(cfg)
    assert isinstance(report, EgressReport)
    return report.summary()


def _crm() -> str:
    from src.crm import CRMDatabase, CRMRepository, CRMService, Contact, Deal
    from src.crm.backup import backup_database
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "crm.db"
        repo = CRMRepository(CRMDatabase(db_path))
        cid = repo.add_contact(Contact(name="Smoke"))
        repo.add_deal(Deal(title="D", value=100, stage="qualified", contact_id=cid))
        dash = CRMService(repo).dashboard()
        assert dash.open_deals == 1 and dash.pipeline_value == 100
        snap = backup_database(db_path, Path(tmp) / "backups")
        assert snap.exists()
    return "contact+deal+dashboard+backup OK"


def _web() -> str:
    from src.api import create_app
    app = create_app(port=8000)
    paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/crm" in paths and "/crm/dashboard" in paths
    return f"{sum(1 for p in paths if p.startswith('/crm'))} CRM routes mounted"


def main() -> int:
    check("air-gap egress check", _egress)
    check("CRM stack + backup", _crm)
    check("web app + CRM routes", _web)

    print("\nSovereign Agent — offline smoke test\n" + "-" * 40)
    ok = True
    for name, passed, detail in _results:
        print(f"[{'PASS' if passed else 'FAIL'}] {name}: {detail}")
        ok = ok and passed
    print("-" * 40)
    print("ALL PASSED" if ok else "FAILURES DETECTED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

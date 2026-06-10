"""Tests for the offline CRM: storage, repository, service, and the agent tool."""

from pathlib import Path

import pytest

from src.crm import (
    CRMDatabase, CRMRepository, CRMService, Company, Contact, Deal, Interaction, Task,
)
from src.crm.database import now
from src.tools.crm_tool import CRMTool


@pytest.fixture
def repo(tmp_path) -> CRMRepository:
    db = CRMDatabase(tmp_path / "crm.db")
    return CRMRepository(db)


def test_contact_crud(repo):
    cid = repo.add_contact(Contact(name="Jane Doe", email="jane@x.com", tags="vip"))
    fetched = repo.get_contact(cid)
    assert fetched is not None and fetched.name == "Jane Doe"
    repo.update_contact(cid, {"phone": "555-1234"})
    assert repo.get_contact(cid).phone == "555-1234"
    assert repo.list_contacts(search="jane")[0].id == cid


def test_company_and_link(repo):
    comp_id = repo.add_company(Company(name="Acme", industry="Tools"))
    cid = repo.add_contact(Contact(name="Bob", company_id=comp_id))
    assert repo.list_company_contacts(comp_id)[0].id == cid


def test_deal_pipeline_summary(repo):
    cid = repo.add_contact(Contact(name="Lead A"))
    repo.add_deal(Deal(title="Big deal", value=1000, stage="qualified", contact_id=cid))
    repo.add_deal(Deal(title="Small deal", value=250, stage="qualified", contact_id=cid))
    repo.add_deal(Deal(title="Won deal", value=500, stage="won", status="won", contact_id=cid))
    service = CRMService(repo)
    stages = {s.stage: s for s in service.pipeline_summary()}
    assert stages["qualified"].count == 2
    assert stages["qualified"].value == 1250
    dash = service.dashboard()
    assert dash.open_deals == 2  # won excluded
    assert dash.pipeline_value == 1250


def test_due_tasks_and_completion(repo):
    cid = repo.add_contact(Contact(name="Tasky"))
    overdue = repo.add_task(Task(title="Call back", due_date=now() - 100, contact_id=cid))
    repo.add_task(Task(title="Future", due_date=now() + 10000, contact_id=cid))
    service = CRMService(repo)
    due = service.due_tasks()
    assert len(due) == 1 and due[0]["title"] == "Call back"
    repo.complete_task(overdue)
    assert service.due_tasks() == []


def test_stale_contacts(repo):
    cid = repo.add_contact(Contact(name="Ghost"))
    repo.add_deal(Deal(title="Cold", stage="lead", contact_id=cid))
    service = CRMService(repo)
    # No interactions logged => stale immediately.
    stale = service.stale_contacts(days=30)
    assert any(s["contact"]["id"] == cid for s in stale)
    # Log a fresh interaction => no longer stale.
    repo.add_interaction(Interaction(contact_id=cid, type="call", summary="talked"))
    assert service.stale_contacts(days=30) == []


def test_crm_tool_roundtrip(tmp_path):
    tool = CRMTool(db_path=tmp_path / "crm.db")
    r = tool.execute(operation="add_contact", name="Carol", email="c@x.com")
    assert r.success and "Carol" in r.output
    r = tool.execute(operation="add_deal", title="Website", value="2500", contact_id="1")
    assert r.success
    r = tool.execute(operation="pipeline")
    assert "lead" in r.output
    r = tool.execute(operation="add_task", title="Follow up", contact_id="1", due_in_days="0")
    assert r.success
    r = tool.execute(operation="due_tasks")
    assert "Follow up" in r.output
    r = tool.execute(operation="briefing")
    assert "CRM Daily Briefing" in r.output


def test_crm_tool_unknown_op(tmp_path):
    tool = CRMTool(db_path=tmp_path / "crm.db")
    r = tool.execute(operation="nonsense")
    assert not r.success and "Unknown CRM operation" in (r.error or "")

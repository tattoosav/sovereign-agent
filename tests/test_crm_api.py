"""Tests for the CRM REST API (router in isolation, local SQLite)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import crm_routes
from src.crm import CRMDatabase, CRMRepository, CRMService


@pytest.fixture
def client(tmp_path):
    db = CRMDatabase(tmp_path / "crm.db")
    repo = CRMRepository(db)
    crm_routes._crm.clear()
    crm_routes._crm.update(repo=repo, service=CRMService(repo), db_path=tmp_path / "crm.db")
    app = FastAPI()
    app.include_router(crm_routes.router)
    yield TestClient(app)
    crm_routes._crm.clear()


def test_contact_create_and_detail(client):
    r = client.post("/crm/contacts", json={"name": "Dana", "email": "dana@x.com"})
    assert r.status_code == 200
    cid = r.json()["id"]
    detail = client.get(f"/crm/contacts/{cid}").json()
    assert detail["contact"]["name"] == "Dana"
    assert detail["deals"] == []


def test_deal_pipeline_and_update(client):
    cid = client.post("/crm/contacts", json={"name": "Lead"}).json()["id"]
    did = client.post("/crm/deals", json={"title": "Site", "value": 900, "contact_id": cid}).json()["id"]
    client.patch(f"/crm/deals/{did}", json={"stage": "proposal"})
    deals = client.get("/crm/deals", params={"stage": "proposal"}).json()
    assert len(deals) == 1 and deals[0]["id"] == did
    dash = client.get("/crm/dashboard").json()
    assert dash["summary"]["open_deals"] == 1


def test_task_due_and_complete(client):
    cid = client.post("/crm/contacts", json={"name": "T"}).json()["id"]
    tid = client.post("/crm/tasks", json={"title": "Ring back", "contact_id": cid,
                                          "due_in_days": -1}).json()["id"]
    due = client.get("/crm/tasks/due").json()
    assert any(t["id"] == tid for t in due)
    client.post(f"/crm/tasks/{tid}/complete")
    assert client.get("/crm/tasks/due").json() == []


def test_backup_endpoint(client, tmp_path):
    client.post("/crm/contacts", json={"name": "Backup Me"})
    r = client.post("/crm/backup")
    assert r.status_code == 200
    body = r.json()
    assert (tmp_path / "backups").exists()
    assert body["snapshot"].endswith(".db")

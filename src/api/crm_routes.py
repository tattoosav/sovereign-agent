"""
REST API for the CRM (mounted by the web app).

Backs the browser CRM screens and exposes backup/export. All data is the local
SQLite store; nothing leaves the machine.
"""

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.core import load_config
from src.crm import (
    CRMDatabase, CRMRepository, CRMService, Company, Contact, Deal, Interaction, Task,
)
from src.crm.backup import backup_database, export_csv
from src.crm.database import now

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/crm", tags=["crm"])

DAY = 86400.0
_crm: dict[str, Any] = {}


def get_crm() -> tuple[CRMRepository, CRMService, Path]:
    """Lazily build the shared CRM (repo, service, db_path) from config."""
    if not _crm:
        config = load_config()
        working = Path(config.agent.working_dir) if config.agent.working_dir else Path.cwd()
        db_path = working / ".sovereign" / "crm.db"
        db = CRMDatabase(db_path)
        repo = CRMRepository(db)
        _crm.update(repo=repo, service=CRMService(repo), db_path=db_path)
    return _crm["repo"], _crm["service"], _crm["db_path"]


# ---- request bodies ------------------------------------------------------

class ContactIn(BaseModel):
    name: str
    email: str = ""
    phone: str = ""
    mobile: str = ""
    title: str = ""
    source: str = ""
    tags: str = ""
    notes: str = ""
    company_id: int | None = None


class CompanyIn(BaseModel):
    name: str
    industry: str = ""
    phone: str = ""
    email: str = ""
    website: str = ""
    notes: str = ""


class DealIn(BaseModel):
    title: str
    value: float = 0.0
    stage: str = "lead"
    contact_id: int | None = None
    company_id: int | None = None
    description: str = ""


class DealUpdate(BaseModel):
    stage: str | None = None
    status: str | None = None
    value: float | None = None
    probability: int | None = None


class InteractionIn(BaseModel):
    contact_id: int
    type: str = "note"
    summary: str = ""
    deal_id: int | None = None


class TaskIn(BaseModel):
    title: str
    due_in_days: float = 0.0
    type: str = "follow_up"
    contact_id: int | None = None
    deal_id: int | None = None


# ---- dashboard -----------------------------------------------------------

@router.get("/dashboard")
def dashboard() -> dict[str, Any]:
    _, service, _ = get_crm()
    return {
        "summary": service.dashboard().to_dict(),
        "due_tasks": service.due_tasks(),
        "upcoming_appointments": service.upcoming_appointments(7),
        "stale_contacts": service.stale_contacts(30),
    }


# ---- contacts ------------------------------------------------------------

@router.get("/contacts")
def list_contacts(query: str = "") -> list[dict[str, Any]]:
    repo, _, _ = get_crm()
    return [c.to_dict() for c in repo.list_contacts(search=query)]


@router.post("/contacts")
def create_contact(body: ContactIn) -> dict[str, Any]:
    repo, _, _ = get_crm()
    cid = repo.add_contact(Contact(**body.model_dump()))
    return {"id": cid}


@router.get("/contacts/{contact_id}")
def contact_detail(contact_id: int) -> dict[str, Any]:
    repo, _, _ = get_crm()
    contact = repo.get_contact(contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="contact not found")
    return {
        "contact": contact.to_dict(),
        "deals": [d.to_dict() for d in repo.list_contact_deals(contact_id)],
        "interactions": [i.to_dict() for i in repo.list_interactions(contact_id)],
        "tasks": [t.to_dict() for t in repo.list_tasks(contact_id)],
    }


@router.patch("/contacts/{contact_id}")
def update_contact(contact_id: int, body: dict[str, Any]) -> dict[str, str]:
    repo, _, _ = get_crm()
    repo.update_contact(contact_id, body)
    return {"status": "ok"}


@router.delete("/contacts/{contact_id}")
def delete_contact(contact_id: int) -> dict[str, str]:
    repo, _, _ = get_crm()
    repo.delete_contact(contact_id)
    return {"status": "deleted"}


# ---- companies -----------------------------------------------------------

@router.get("/companies")
def list_companies(query: str = "") -> list[dict[str, Any]]:
    repo, _, _ = get_crm()
    return [c.to_dict() for c in repo.list_companies(search=query)]


@router.post("/companies")
def create_company(body: CompanyIn) -> dict[str, Any]:
    repo, _, _ = get_crm()
    return {"id": repo.add_company(Company(**body.model_dump()))}


# ---- deals (pipeline) ----------------------------------------------------

@router.get("/deals")
def list_deals(stage: str = "", status: str = "") -> list[dict[str, Any]]:
    repo, _, _ = get_crm()
    return [d.to_dict() for d in repo.list_deals(stage=stage, status=status)]


@router.post("/deals")
def create_deal(body: DealIn) -> dict[str, Any]:
    repo, _, _ = get_crm()
    return {"id": repo.add_deal(Deal(**body.model_dump()))}


@router.patch("/deals/{deal_id}")
def update_deal(deal_id: int, body: DealUpdate) -> dict[str, str]:
    repo, _, _ = get_crm()
    fields_ = {k: v for k, v in body.model_dump().items() if v is not None}
    repo.update_deal(deal_id, fields_)
    return {"status": "ok"}


# ---- interactions + tasks ------------------------------------------------

@router.post("/interactions")
def create_interaction(body: InteractionIn) -> dict[str, Any]:
    repo, _, _ = get_crm()
    return {"id": repo.add_interaction(Interaction(**body.model_dump()))}


@router.get("/tasks/due")
def due_tasks() -> list[dict[str, Any]]:
    _, service, _ = get_crm()
    return service.due_tasks()


@router.post("/tasks")
def create_task(body: TaskIn) -> dict[str, Any]:
    repo, _, _ = get_crm()
    due = now() + body.due_in_days * DAY
    task = Task(title=body.title, due_date=due, type=body.type,
                contact_id=body.contact_id, deal_id=body.deal_id)
    return {"id": repo.add_task(task)}


@router.post("/tasks/{task_id}/complete")
def complete_task(task_id: int) -> dict[str, str]:
    repo, _, _ = get_crm()
    repo.complete_task(task_id)
    return {"status": "completed"}


# ---- backup / export -----------------------------------------------------

@router.post("/backup")
def backup() -> dict[str, str]:
    repo, _, db_path = get_crm()
    dest = db_path.parent / "backups"
    snapshot = backup_database(db_path, dest)
    csvs = export_csv(repo, dest)
    return {"snapshot": str(snapshot), "csv_dir": str(dest), "files": str(len(csvs))}

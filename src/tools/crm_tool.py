"""
CRM tool — lets the agent manage the customer database in natural language.

All data is local SQLite (offline). One tool with an `operation` switch keeps the
LLM-facing surface small; each operation delegates to a tiny handler.
"""

import json
from pathlib import Path
from typing import Any, Callable

from src.crm import (
    CRMDatabase, CRMRepository, CRMService, Company, Contact, Deal, Interaction, Task,
)
from src.crm.database import now

from .base import BaseTool, ToolResult

DAY = 86400.0


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


class CRMTool(BaseTool):
    """Create and query CRM records (contacts, companies, deals, tasks, activity)."""

    name = "crm"
    description = """Manage the customer relationship database (local, offline).

Operations:
- add_contact: create a contact (params: name, email, phone, company_id, source, tags, notes)
- find_contacts: search contacts (params: query)
- contact_detail: full history for a contact (params: contact_id)
- log_interaction: record a call/email/meeting/note (params: contact_id, type, summary, deal_id)
- add_company: create a company (params: name, industry, phone, email)
- add_deal: create a pipeline deal (params: title, contact_id, value, stage)
- update_deal: change a deal (params: deal_id, stage, status, value, probability)
- list_deals: list deals (params: stage, status)
- pipeline: summarize the pipeline by stage
- add_task: schedule a follow-up (params: title, contact_id, due_in_days, type)
- due_tasks: list follow-ups due now or overdue
- complete_task: mark a task done (params: task_id)
- briefing: a daily CRM briefing (due tasks, stale contacts, pipeline)
"""
    parameters = {
        "operation": "The CRM operation to perform (see description)",
        "name": "Name (for add_contact / add_company)",
        "query": "Search text (for find_contacts)",
        "contact_id": "Contact id",
        "deal_id": "Deal id",
        "task_id": "Task id",
        "company_id": "Company id",
        "type": "Interaction/task type",
        "summary": "Interaction summary",
        "title": "Deal or task title",
        "value": "Deal value (number)",
        "stage": "Deal stage",
        "status": "Deal status (open/won/lost)",
        "probability": "Deal probability 0-100",
        "due_in_days": "Days from now the task is due",
        "email": "Email", "phone": "Phone", "industry": "Industry",
        "source": "Lead source", "tags": "Comma-separated tags", "notes": "Free notes",
    }

    def __init__(self, db_path: Path | str = ".sovereign/crm.db") -> None:
        self.db = CRMDatabase(db_path)
        self.repo = CRMRepository(self.db)
        self.service = CRMService(self.repo)
        self._ops: dict[str, Callable[..., ToolResult]] = {
            "add_contact": self._add_contact,
            "find_contacts": self._find_contacts,
            "contact_detail": self._contact_detail,
            "log_interaction": self._log_interaction,
            "add_company": self._add_company,
            "add_deal": self._add_deal,
            "update_deal": self._update_deal,
            "list_deals": self._list_deals,
            "pipeline": self._pipeline,
            "add_task": self._add_task,
            "due_tasks": self._due_tasks,
            "complete_task": self._complete_task,
            "briefing": self._briefing,
        }

    def execute(self, **kwargs: Any) -> ToolResult:
        operation = kwargs.get("operation", "")
        handler = self._ops.get(operation)
        if handler is None:
            return ToolResult(success=False, output="",
                              error=f"Unknown CRM operation: {operation}")
        try:
            return handler(**kwargs)
        except Exception as e:  # noqa: BLE001 - report cleanly to the agent
            return ToolResult(success=False, output="", error=f"CRM error: {e}")

    # ---- handlers --------------------------------------------------------

    def _add_contact(self, **kw: Any) -> ToolResult:
        if not kw.get("name"):
            return ToolResult(success=False, output="", error="name is required")
        cid = self.repo.add_contact(Contact(
            name=kw["name"], email=kw.get("email", ""), phone=kw.get("phone", ""),
            source=kw.get("source", ""), tags=kw.get("tags", ""), notes=kw.get("notes", ""),
            company_id=_int(kw.get("company_id")),
        ))
        return ToolResult(success=True, output=f"Created contact #{cid}: {kw['name']}")

    def _find_contacts(self, **kw: Any) -> ToolResult:
        contacts = self.repo.list_contacts(search=kw.get("query", ""))
        if not contacts:
            return ToolResult(success=True, output="No contacts found.")
        lines = [f"#{c.id} {c.name} | {c.email} | {c.phone} | tags: {c.tags}" for c in contacts]
        return ToolResult(success=True, output="\n".join(lines))

    def _contact_detail(self, **kw: Any) -> ToolResult:
        cid = _int(kw.get("contact_id"))
        contact = self.repo.get_contact(cid) if cid else None
        if not contact:
            return ToolResult(success=False, output="", error="contact not found")
        deals = self.repo.list_contact_deals(cid)
        inter = self.repo.list_interactions(cid, limit=10)
        tasks = self.repo.list_tasks(cid)
        out = [
            f"{contact.name} (#{cid}) — {contact.email} {contact.phone}",
            f"Notes: {contact.notes}",
            f"Deals ({len(deals)}): " + ", ".join(f"{d.title}[{d.stage}/{d.value}]" for d in deals),
            "Recent activity:",
            *[f"  - {i.type}: {i.summary}" for i in inter],
            f"Open tasks: " + ", ".join(t.title for t in tasks if t.status == "pending"),
        ]
        return ToolResult(success=True, output="\n".join(out))

    def _log_interaction(self, **kw: Any) -> ToolResult:
        cid = _int(kw.get("contact_id"))
        if not cid:
            return ToolResult(success=False, output="", error="contact_id is required")
        self.repo.add_interaction(Interaction(
            contact_id=cid, type=kw.get("type", "note"),
            summary=kw.get("summary", ""), deal_id=_int(kw.get("deal_id")),
        ))
        return ToolResult(success=True, output=f"Logged {kw.get('type', 'note')} for contact #{cid}")

    def _add_company(self, **kw: Any) -> ToolResult:
        if not kw.get("name"):
            return ToolResult(success=False, output="", error="name is required")
        cid = self.repo.add_company(Company(
            name=kw["name"], industry=kw.get("industry", ""),
            phone=kw.get("phone", ""), email=kw.get("email", ""),
        ))
        return ToolResult(success=True, output=f"Created company #{cid}: {kw['name']}")

    def _add_deal(self, **kw: Any) -> ToolResult:
        if not kw.get("title"):
            return ToolResult(success=False, output="", error="title is required")
        did = self.repo.add_deal(Deal(
            title=kw["title"], value=_float(kw.get("value")),
            stage=kw.get("stage", "lead"), contact_id=_int(kw.get("contact_id")),
            company_id=_int(kw.get("company_id")),
        ))
        return ToolResult(success=True, output=f"Created deal #{did}: {kw['title']}")

    def _update_deal(self, **kw: Any) -> ToolResult:
        did = _int(kw.get("deal_id"))
        if not did:
            return ToolResult(success=False, output="", error="deal_id is required")
        fields_: dict[str, Any] = {}
        for key in ("stage", "status"):
            if kw.get(key):
                fields_[key] = kw[key]
        if kw.get("value"):
            fields_["value"] = _float(kw["value"])
        if kw.get("probability"):
            fields_["probability"] = _int(kw["probability"])
        self.repo.update_deal(did, fields_)
        return ToolResult(success=True, output=f"Updated deal #{did}: {fields_}")

    def _list_deals(self, **kw: Any) -> ToolResult:
        deals = self.repo.list_deals(stage=kw.get("stage", ""), status=kw.get("status", ""))
        if not deals:
            return ToolResult(success=True, output="No deals found.")
        lines = [f"#{d.id} {d.title} | {d.stage}/{d.status} | {d.value} {d.currency}" for d in deals]
        return ToolResult(success=True, output="\n".join(lines))

    def _pipeline(self, **kw: Any) -> ToolResult:
        stages = self.service.pipeline_summary()
        lines = [f"{s.stage:12} {s.count:3} deals  {s.value:,.2f}" for s in stages]
        return ToolResult(success=True, output="PIPELINE (open):\n" + "\n".join(lines))

    def _add_task(self, **kw: Any) -> ToolResult:
        if not kw.get("title"):
            return ToolResult(success=False, output="", error="title is required")
        due = now() + _float(kw.get("due_in_days", 0)) * DAY
        tid = self.repo.add_task(Task(
            title=kw["title"], due_date=due, type=kw.get("type", "follow_up"),
            contact_id=_int(kw.get("contact_id")), deal_id=_int(kw.get("deal_id")),
        ))
        return ToolResult(success=True, output=f"Scheduled task #{tid}: {kw['title']}")

    def _due_tasks(self, **kw: Any) -> ToolResult:
        tasks = self.service.due_tasks()
        if not tasks:
            return ToolResult(success=True, output="No tasks due.")
        lines = [f"#{t['id']} {t['title']} (type: {t['type']})" for t in tasks]
        return ToolResult(success=True, output="DUE TASKS:\n" + "\n".join(lines))

    def _complete_task(self, **kw: Any) -> ToolResult:
        tid = _int(kw.get("task_id"))
        if not tid:
            return ToolResult(success=False, output="", error="task_id is required")
        self.repo.complete_task(tid)
        return ToolResult(success=True, output=f"Completed task #{tid}")

    def _briefing(self, **kw: Any) -> ToolResult:
        return ToolResult(success=True, output=self.service.daily_briefing())

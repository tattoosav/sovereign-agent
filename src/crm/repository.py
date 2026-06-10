"""
Data-access layer for the CRM. Maps dataclasses <-> SQLite rows.

Generic insert/update/build helpers keep this concise: dataclass field names match
column names, so we can round-trip without per-field boilerplate.
"""

from dataclasses import fields
from typing import Any, TypeVar

from .database import CRMDatabase, now
from .models import (
    Appointment, Company, Contact, Deal, Interaction, Payment, Task,
)

T = TypeVar("T")


def _encode(value: Any) -> Any:
    """Convert Python values to SQLite-friendly forms."""
    return int(value) if isinstance(value, bool) else value


def _build(cls: type[T], row: Any) -> T:
    """Construct a dataclass from a sqlite3.Row (ignoring unknown columns)."""
    names = {f.name for f in fields(cls)}  # type: ignore[arg-type]
    data = {k: row[k] for k in row.keys() if k in names}
    return cls(**data)  # type: ignore[call-arg]


class CRMRepository:
    """CRUD operations over the CRM tables."""

    def __init__(self, db: CRMDatabase) -> None:
        self.db = db

    # ---- generic helpers -------------------------------------------------

    def _insert(self, table: str, data: dict[str, Any], with_updated: bool) -> int:
        # Drop id and None values; nullable columns fall back to their DB defaults.
        data = {k: v for k, v in data.items() if k != "id" and v is not None}
        ts = now()
        data["created_at"] = ts
        if with_updated:
            data["updated_at"] = ts
        cols = ", ".join(data)
        placeholders = ", ".join("?" for _ in data)
        values = tuple(_encode(v) for v in data.values())
        return self.db.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", values)

    def _update(self, table: str, row_id: int, fields_: dict[str, Any], with_updated: bool) -> None:
        if not fields_:
            return
        data = {k: _encode(v) for k, v in fields_.items() if k != "id"}
        if with_updated:
            data["updated_at"] = now()
        assignments = ", ".join(f"{k} = ?" for k in data)
        self.db.execute(
            f"UPDATE {table} SET {assignments} WHERE id = ?", (*data.values(), row_id)
        )

    # ---- companies -------------------------------------------------------

    def add_company(self, company: Company) -> int:
        return self._insert("companies", company.to_dict(), with_updated=True)

    def get_company(self, company_id: int) -> Company | None:
        row = self.db.query_one("SELECT * FROM companies WHERE id = ?", (company_id,))
        return _build(Company, row) if row else None

    def list_companies(self, search: str = "", limit: int = 200) -> list[Company]:
        if search:
            like = f"%{search}%"
            rows = self.db.query(
                "SELECT * FROM companies WHERE name LIKE ? OR industry LIKE ? OR tags LIKE ? "
                "ORDER BY name LIMIT ?", (like, like, like, limit),
            )
        else:
            rows = self.db.query("SELECT * FROM companies ORDER BY name LIMIT ?", (limit,))
        return [_build(Company, r) for r in rows]

    def update_company(self, company_id: int, fields_: dict[str, Any]) -> None:
        self._update("companies", company_id, fields_, with_updated=True)

    def delete_company(self, company_id: int) -> None:
        self.db.execute("DELETE FROM companies WHERE id = ?", (company_id,))

    # ---- contacts --------------------------------------------------------

    def add_contact(self, contact: Contact) -> int:
        return self._insert("contacts", contact.to_dict(), with_updated=True)

    def get_contact(self, contact_id: int) -> Contact | None:
        row = self.db.query_one("SELECT * FROM contacts WHERE id = ?", (contact_id,))
        return _build(Contact, row) if row else None

    def list_contacts(self, search: str = "", limit: int = 200) -> list[Contact]:
        if search:
            like = f"%{search}%"
            rows = self.db.query(
                "SELECT * FROM contacts WHERE name LIKE ? OR phone LIKE ? OR email LIKE ? "
                "OR mobile LIKE ? OR tags LIKE ? ORDER BY name LIMIT ?",
                (like, like, like, like, like, limit),
            )
        else:
            rows = self.db.query("SELECT * FROM contacts ORDER BY name LIMIT ?", (limit,))
        return [_build(Contact, r) for r in rows]

    def list_company_contacts(self, company_id: int) -> list[Contact]:
        rows = self.db.query(
            "SELECT * FROM contacts WHERE company_id = ? ORDER BY name", (company_id,)
        )
        return [_build(Contact, r) for r in rows]

    def update_contact(self, contact_id: int, fields_: dict[str, Any]) -> None:
        self._update("contacts", contact_id, fields_, with_updated=True)

    def delete_contact(self, contact_id: int) -> None:
        self.db.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))

    # ---- deals (pipeline) ------------------------------------------------

    def add_deal(self, deal: Deal) -> int:
        return self._insert("deals", deal.to_dict(), with_updated=True)

    def get_deal(self, deal_id: int) -> Deal | None:
        row = self.db.query_one("SELECT * FROM deals WHERE id = ?", (deal_id,))
        return _build(Deal, row) if row else None

    def list_deals(self, stage: str = "", status: str = "") -> list[Deal]:
        clauses, params = [], []
        if stage:
            clauses.append("stage = ?"); params.append(stage)
        if status:
            clauses.append("status = ?"); params.append(status)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self.db.query(f"SELECT * FROM deals{where} ORDER BY updated_at DESC", tuple(params))
        return [_build(Deal, r) for r in rows]

    def list_contact_deals(self, contact_id: int) -> list[Deal]:
        rows = self.db.query(
            "SELECT * FROM deals WHERE contact_id = ? ORDER BY created_at DESC", (contact_id,)
        )
        return [_build(Deal, r) for r in rows]

    def update_deal(self, deal_id: int, fields_: dict[str, Any]) -> None:
        self._update("deals", deal_id, fields_, with_updated=True)

    # ---- interactions ----------------------------------------------------

    def add_interaction(self, interaction: Interaction) -> int:
        return self._insert("interactions", interaction.to_dict(), with_updated=False)

    def list_interactions(self, contact_id: int, limit: int = 100) -> list[Interaction]:
        rows = self.db.query(
            "SELECT * FROM interactions WHERE contact_id = ? ORDER BY created_at DESC LIMIT ?",
            (contact_id, limit),
        )
        return [_build(Interaction, r) for r in rows]

    def last_interaction_at(self, contact_id: int) -> float:
        row = self.db.query_one(
            "SELECT MAX(created_at) AS last FROM interactions WHERE contact_id = ?", (contact_id,)
        )
        return float(row["last"]) if row and row["last"] is not None else 0.0

    # ---- appointments ----------------------------------------------------

    def add_appointment(self, appt: Appointment) -> int:
        return self._insert("appointments", appt.to_dict(), with_updated=False)

    def list_appointments(self, start: float, end: float) -> list[Appointment]:
        rows = self.db.query(
            "SELECT * FROM appointments WHERE scheduled_at BETWEEN ? AND ? ORDER BY scheduled_at",
            (start, end),
        )
        return [_build(Appointment, r) for r in rows]

    def update_appointment(self, appt_id: int, fields_: dict[str, Any]) -> None:
        self._update("appointments", appt_id, fields_, with_updated=False)

    # ---- tasks / follow-ups ---------------------------------------------

    def add_task(self, task: Task) -> int:
        return self._insert("tasks", task.to_dict(), with_updated=False)

    def list_due_tasks(self, before: float) -> list[Task]:
        rows = self.db.query(
            "SELECT * FROM tasks WHERE status = 'pending' AND due_date <= ? ORDER BY due_date",
            (before,),
        )
        return [_build(Task, r) for r in rows]

    def list_tasks(self, contact_id: int) -> list[Task]:
        rows = self.db.query(
            "SELECT * FROM tasks WHERE contact_id = ? ORDER BY due_date", (contact_id,)
        )
        return [_build(Task, r) for r in rows]

    def complete_task(self, task_id: int) -> None:
        self.db.execute(
            "UPDATE tasks SET status = 'done', completed_at = ? WHERE id = ?", (now(), task_id)
        )

    # ---- payments --------------------------------------------------------

    def add_payment(self, payment: Payment) -> int:
        return self._insert("payments", payment.to_dict(), with_updated=False)

    def list_payments(self, contact_id: int) -> list[Payment]:
        rows = self.db.query(
            "SELECT * FROM payments WHERE contact_id = ? ORDER BY created_at DESC", (contact_id,)
        )
        return [_build(Payment, r) for r in rows]

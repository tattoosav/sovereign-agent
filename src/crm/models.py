"""
CRM data models for the Sovereign Agent (general-purpose).

Plain dataclasses mapped to SQLite rows. No ORM, no new dependencies — the storage
layer uses the Python standard-library `sqlite3`, which keeps the build fully offline.

Entities:
- Company      an organization
- Contact      a person (optionally linked to a company)
- Deal         an opportunity moving through the sales pipeline
- Interaction  a logged activity: call, email, meeting, note, message
- Task         a follow-up / reminder surfaced when due
- Appointment  a scheduled meeting
- Payment      a payment / invoice record
"""

from dataclasses import dataclass, field, asdict
from typing import Any

# Generic sales-pipeline stages (ordered).
DEAL_STAGES = [
    "lead",
    "qualified",
    "proposal",
    "negotiation",
    "won",
    "lost",
]
DEAL_STATUS = ["open", "won", "lost"]

INTERACTION_TYPES = ["call", "email", "meeting", "message", "note"]
APPOINTMENT_TYPES = ["meeting", "call", "demo", "other"]
APPOINTMENT_STATUS = ["booked", "completed", "no_show", "cancelled"]
TASK_TYPES = ["call", "email", "follow_up", "payment_reminder", "check_in", "todo"]
TASK_STATUS = ["pending", "done", "dismissed"]
PAYMENT_TYPES = ["invoice", "payment", "deposit", "refund"]


@dataclass
class Company:
    """An organization / account."""
    name: str
    industry: str = ""
    phone: str = ""
    email: str = ""
    website: str = ""
    address: str = ""
    tags: str = ""               # comma-separated
    notes: str = ""
    id: int | None = None
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Contact:
    """A person in the CRM (optionally tied to a company)."""
    name: str
    title: str = ""              # job title / role
    email: str = ""
    phone: str = ""
    mobile: str = ""
    tags: str = ""               # comma-separated
    source: str = ""             # how they came in (referral, web, event, ...)
    notes: str = ""
    company_id: int | None = None
    id: int | None = None
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Deal:
    """An opportunity moving through the pipeline."""
    title: str
    description: str = ""
    value: float = 0.0
    currency: str = "USD"
    stage: str = "lead"
    status: str = "open"
    probability: int = 0          # 0-100
    expected_close: float = 0.0   # epoch seconds, 0 = unset
    contact_id: int | None = None
    company_id: int | None = None
    id: int | None = None
    created_at: float = 0.0
    updated_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Interaction:
    """A logged activity against a contact (and optionally a deal)."""
    contact_id: int
    type: str = "note"
    summary: str = ""
    deal_id: int | None = None
    id: int | None = None
    created_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Appointment:
    """A scheduled meeting / call."""
    contact_id: int
    scheduled_at: float = 0.0     # epoch seconds
    duration_min: int = 30
    type: str = "meeting"
    status: str = "booked"
    notes: str = ""
    deal_id: int | None = None
    id: int | None = None
    created_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Task:
    """A follow-up / reminder surfaced when due (drives proactive outreach)."""
    title: str
    due_date: float = 0.0         # epoch seconds
    type: str = "follow_up"
    status: str = "pending"
    notes: str = ""
    contact_id: int | None = None
    deal_id: int | None = None
    id: int | None = None
    created_at: float = 0.0
    completed_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Payment:
    """A payment or invoice record."""
    amount: float = 0.0
    type: str = "payment"
    method: str = "card"
    notes: str = ""
    contact_id: int | None = None
    deal_id: int | None = None
    id: int | None = None
    created_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

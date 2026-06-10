"""
CRM package for the Sovereign Agent (general-purpose, fully offline).

Local SQLite storage + dataclass models + repository (CRUD) + service (analytics).
The agent's CRM tool and the web API both build on these.
"""

from .database import CRMDatabase, now
from .models import (
    Appointment, Company, Contact, Deal, Interaction, Payment, Task,
    DEAL_STAGES, DEAL_STATUS,
)
from .repository import CRMRepository
from .service import CRMService, Dashboard

__all__ = [
    "CRMDatabase",
    "now",
    "Company",
    "Contact",
    "Deal",
    "Interaction",
    "Appointment",
    "Task",
    "Payment",
    "DEAL_STAGES",
    "DEAL_STATUS",
    "CRMRepository",
    "CRMService",
    "Dashboard",
]

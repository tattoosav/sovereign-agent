"""
CRM business logic: pipeline analytics, due follow-ups, stale contacts, and a
human-readable daily briefing the autonomous daemon can drop into its output queue.
"""

import time
from dataclasses import dataclass, field
from typing import Any

from .database import now
from .models import DEAL_STAGES
from .repository import CRMRepository

DAY = 86400.0


@dataclass
class PipelineStage:
    stage: str
    count: int = 0
    value: float = 0.0


@dataclass
class Dashboard:
    """A snapshot for the dashboard / autonomous briefing."""
    open_deals: int
    pipeline_value: float
    due_tasks: int
    upcoming_appointments: int
    stages: list[PipelineStage] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "open_deals": self.open_deals,
            "pipeline_value": round(self.pipeline_value, 2),
            "due_tasks": self.due_tasks,
            "upcoming_appointments": self.upcoming_appointments,
            "stages": [vars(s) for s in self.stages],
        }


class CRMService:
    """Higher-level CRM queries built on the repository."""

    def __init__(self, repo: CRMRepository) -> None:
        self.repo = repo

    def pipeline_summary(self) -> list[PipelineStage]:
        """Count and total open-deal value per pipeline stage."""
        stages = {s: PipelineStage(stage=s) for s in DEAL_STAGES}
        for deal in self.repo.list_deals(status="open"):
            bucket = stages.get(deal.stage)
            if bucket is None:
                bucket = stages.setdefault(deal.stage, PipelineStage(stage=deal.stage))
            bucket.count += 1
            bucket.value += deal.value
        return list(stages.values())

    def stale_contacts(self, days: int = 30) -> list[dict[str, Any]]:
        """Contacts with an open deal but no interaction in `days` days."""
        cutoff = now() - days * DAY
        stale: list[dict[str, Any]] = []
        open_contact_ids = {
            d.contact_id for d in self.repo.list_deals(status="open") if d.contact_id
        }
        for contact_id in open_contact_ids:
            last = self.repo.last_interaction_at(contact_id)
            if last < cutoff:
                contact = self.repo.get_contact(contact_id)
                if contact:
                    stale.append({"contact": contact.to_dict(), "last_interaction": last})
        return stale

    def due_tasks(self) -> list[dict[str, Any]]:
        """Pending follow-up tasks that are due now or overdue."""
        return [t.to_dict() for t in self.repo.list_due_tasks(now())]

    def upcoming_appointments(self, days: int = 7) -> list[dict[str, Any]]:
        appts = self.repo.list_appointments(now(), now() + days * DAY)
        return [a.to_dict() for a in appts]

    def dashboard(self) -> Dashboard:
        """Aggregate snapshot for the UI and the autonomous briefing."""
        stages = self.pipeline_summary()
        open_deals = sum(s.count for s in stages if s.stage not in ("won", "lost"))
        pipeline_value = sum(s.value for s in stages if s.stage not in ("won", "lost"))
        return Dashboard(
            open_deals=open_deals,
            pipeline_value=pipeline_value,
            due_tasks=len(self.repo.list_due_tasks(now())),
            upcoming_appointments=len(self.upcoming_appointments(7)),
            stages=stages,
        )

    def daily_briefing(self) -> str:
        """A plain-text briefing for the autonomous daemon to file as a report."""
        dash = self.dashboard()
        lines = [
            f"CRM Daily Briefing — {time.strftime('%Y-%m-%d %H:%M')}",
            "",
            f"Open deals: {dash.open_deals}  |  Pipeline value: "
            f"{dash.pipeline_value:,.2f}",
            f"Tasks due/overdue: {dash.due_tasks}  |  "
            f"Appointments next 7 days: {dash.upcoming_appointments}",
            "",
            "Due follow-ups:",
        ]
        for task in self.due_tasks()[:25]:
            lines.append(f"  - {task['title']} (type: {task['type']})")
        if dash.due_tasks == 0:
            lines.append("  (none)")

        stale = self.stale_contacts(30)
        lines.append("")
        lines.append(f"Stale open-deal contacts (>30d no contact): {len(stale)}")
        for item in stale[:25]:
            lines.append(f"  - {item['contact']['name']}")
        return "\n".join(lines)

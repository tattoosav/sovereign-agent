"""
Seed the CRM with demo data so the UI isn't empty when testing on a VM.

Usage:
    uv run python -m scripts.seed_demo --db .sovereign/crm.db
"""

import argparse

from src.crm import (
    CRMDatabase, CRMRepository, Company, Contact, Deal, Interaction, Task,
)
from src.crm.database import now

DAY = 86400.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo CRM data")
    parser.add_argument("--db", default=".sovereign/crm.db", help="Path to crm.db")
    args = parser.parse_args()

    repo = CRMRepository(CRMDatabase(args.db))

    acme = repo.add_company(Company(name="Acme Co", industry="Manufacturing", email="hi@acme.test"))
    globex = repo.add_company(Company(name="Globex", industry="Retail"))

    people = [
        Contact(name="Maria Santos", email="maria@acme.test", phone="555-0102",
                company_id=acme, source="referral", tags="vip"),
        Contact(name="Tom Reed", email="tom@globex.test", phone="555-0150", company_id=globex),
        Contact(name="Priya Patel", email="priya@x.test", source="web"),
        Contact(name="Liam Nguyen", phone="555-0199", source="event"),
    ]
    ids = [repo.add_contact(p) for p in people]

    repo.add_deal(Deal(title="Annual supply contract", value=24000, stage="negotiation",
                       contact_id=ids[0], company_id=acme, probability=70))
    repo.add_deal(Deal(title="Storefront refit", value=8000, stage="proposal",
                       contact_id=ids[1], company_id=globex, probability=40))
    repo.add_deal(Deal(title="Starter package", value=1500, stage="qualified", contact_id=ids[2]))
    repo.add_deal(Deal(title="Closed win", value=5000, stage="won", status="won", contact_id=ids[0]))

    repo.add_interaction(Interaction(contact_id=ids[0], type="call", summary="Reviewed pricing, sending revised quote"))
    repo.add_interaction(Interaction(contact_id=ids[1], type="meeting", summary="Site visit booked"))

    repo.add_task(Task(title="Send revised quote", contact_id=ids[0], due_date=now() - DAY, type="follow_up"))
    repo.add_task(Task(title="Call to confirm refit date", contact_id=ids[1], due_date=now() + DAY))
    repo.add_task(Task(title="Check in with Priya", contact_id=ids[2], due_date=now() - 2 * DAY, type="check_in"))

    print(f"Seeded demo CRM data into {args.db}")
    print(f"  companies: 2 | contacts: {len(ids)} | deals: 4 | tasks: 3 (2 overdue)")


if __name__ == "__main__":
    main()

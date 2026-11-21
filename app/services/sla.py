from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app import config
from app.models import Ticket
from app.services.events import log_event


def deadline_for(category: str, start: datetime) -> datetime:
    return start + timedelta(hours=config.SLA_HOURS[category])


def escalate_overdue(db: Session, now: datetime) -> list[Ticket]:
    """Move each overdue open ticket up one level of the chain and give it a new deadline."""
    top_level = len(config.ESCALATION_CHAIN) - 1
    open_tickets = db.query(Ticket).filter(Ticket.status.in_(["open", "needs_review"])).all()
    escalated = []
    for ticket in open_tickets:
        if now > ticket.sla_deadline and ticket.escalation_level < top_level:
            ticket.escalation_level += 1
            ticket.sla_deadline = now + timedelta(hours=config.ESCALATION_STEP_HOURS)
            log_event(db, ticket.id, "escalated", f"to {config.ESCALATION_CHAIN[ticket.escalation_level]}")
            escalated.append(ticket)
    db.commit()
    return escalated

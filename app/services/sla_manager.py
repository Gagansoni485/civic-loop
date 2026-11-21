"""SLA Management and Escalation Service."""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Ticket, Officer, Event


# SLA Deadlines by Category (in hours)
SLA_DEADLINES = {
    "pothole": 48,  # 2 days
    "streetlight": 72,  # 3 days
    "garbage": 24,  # 1 day
    "drainage": 48,  # 2 days
    "water_supply": 12,  # 12 hours
    "road_damage": 72,  # 3 days
    "other": 48,  # 2 days default
}


def calculate_sla_deadline(category: str, created_at: datetime) -> datetime:
    """Calculate SLA deadline based on category."""
    hours = SLA_DEADLINES.get(category, 48)
    return created_at + timedelta(hours=hours)


def check_sla_breach(ticket: Ticket) -> bool:
    """Check if ticket has breached SLA."""
    if not ticket.sla_due_date:
        return False
    
    if ticket.clock_stopped:
        return False
    
    if ticket.status in ["resolved", "closed"]:
        return False
    
    return datetime.utcnow() > ticket.sla_due_date


def get_next_escalation_officer(
    db: Session,
    current_officer_id: int,
    ward_id: int
) -> Optional[Officer]:
    """Get the next officer in the escalation chain."""
    current_officer = db.query(Officer).filter(Officer.id == current_officer_id).first()
    if not current_officer:
        return None
    
    # Escalation hierarchy: JE (level 1) -> Zonal Commissioner (level 2) -> Municipal Commissioner (level 3)
    next_level = current_officer.level + 1
    
    if next_level > 3:
        return None  # Already at top level
    
    # Find officer at next level
    # For level 2 (zonal), find zonal commissioner covering this ward
    # For level 3 (municipal), find municipal commissioner
    next_officer = db.query(Officer).filter(
        Officer.level == next_level,
        Officer.is_active == True
    ).first()
    
    return next_officer


def escalate_ticket(
    db: Session,
    ticket: Ticket,
    reason: str = "SLA deadline exceeded"
) -> bool:
    """Escalate a ticket to the next level officer."""
    if not ticket.assigned_officer_id:
        return False
    
    next_officer = get_next_escalation_officer(
        db,
        ticket.assigned_officer_id,
        ticket.ward_id
    )
    
    if not next_officer:
        return False  # Already at top level or no next officer found
    
    # Update ticket
    ticket.escalation_level += 1
    ticket.escalated = True
    ticket.escalated_at = datetime.utcnow()
    ticket.escalated_to_officer_id = next_officer.id
    
    # Extend SLA deadline for escalated tickets (give more time at higher levels)
    if ticket.sla_due_date:
        ticket.sla_due_date = datetime.utcnow() + timedelta(hours=24)
    
    # Create event
    event = Event(
        ticket_id=ticket.id,
        event_type="escalated",
        description=f"Escalated to {next_officer.role} - {next_officer.name}. Reason: {reason}",
        officer_id=next_officer.id,
        event_metadata={
            "escalation_level": ticket.escalation_level,
            "previous_officer_id": ticket.assigned_officer_id,
            "next_officer_id": next_officer.id,
            "reason": reason
        }
    )
    db.add(event)
    
    db.commit()
    return True


def request_clock_stop(
    db: Session,
    ticket: Ticket,
    officer_id: int,
    reason: str
) -> bool:
    """Request to stop SLA clock (requires approval)."""
    if ticket.clock_stopped:
        return False
    
    ticket.clock_stop_reason = reason
    ticket.clock_stop_requested_by = officer_id
    ticket.clock_stop_approved = False  # Requires approval
    
    # Create event
    event = Event(
        ticket_id=ticket.id,
        event_type="clock_stop_requested",
        description=f"Clock stop requested. Reason: {reason}",
        officer_id=officer_id,
        event_metadata={"reason": reason}
    )
    db.add(event)
    
    db.commit()
    return True


def approve_clock_stop(
    db: Session,
    ticket: Ticket,
    approver_id: int
) -> bool:
    """Approve clock stop request (admin/senior officer only)."""
    if not ticket.clock_stop_requested_by:
        return False
    
    ticket.clock_stopped = True
    ticket.clock_stop_approved = True
    
    # Create event
    event = Event(
        ticket_id=ticket.id,
        event_type="clock_stop_approved",
        description="Clock stop approved",
        officer_id=approver_id,
        event_metadata={"approved_by": approver_id}
    )
    db.add(event)
    
    db.commit()
    return True


def resume_clock(
    db: Session,
    ticket: Ticket,
    officer_id: int
) -> bool:
    """Resume SLA clock."""
    if not ticket.clock_stopped:
        return False
    
    ticket.clock_stopped = False
    ticket.clock_stop_reason = None
    
    # Extend deadline to give reasonable time after resume
    if ticket.sla_due_date:
        remaining_category_hours = SLA_DEADLINES.get(ticket.category, 48)
        ticket.sla_due_date = datetime.utcnow() + timedelta(hours=remaining_category_hours / 2)
    
    # Create event
    event = Event(
        ticket_id=ticket.id,
        event_type="clock_resumed",
        description="SLA clock resumed",
        officer_id=officer_id,
        event_metadata={"new_deadline": ticket.sla_due_date.isoformat() if ticket.sla_due_date else None}
    )
    db.add(event)
    
    db.commit()
    return True


def check_and_escalate_overdue_tickets(db: Session) -> int:
    """Background job: Check all tickets and escalate overdue ones."""
    overdue_tickets = db.query(Ticket).filter(
        Ticket.status.in_(["assigned", "in_progress"]),
        Ticket.sla_due_date < datetime.utcnow(),
        Ticket.clock_stopped == False,
        Ticket.escalation_level < 3  # Don't escalate beyond municipal commissioner
    ).all()
    
    escalated_count = 0
    for ticket in overdue_tickets:
        if not ticket.sla_breached:
            ticket.sla_breached = True
        
        if escalate_ticket(db, ticket, "SLA deadline exceeded"):
            escalated_count += 1
    
    return escalated_count


def get_sla_metrics(db: Session, ward_id: Optional[int] = None) -> dict:
    """Get SLA compliance metrics."""
    query = db.query(Ticket)
    
    if ward_id:
        query = query.filter(Ticket.ward_id == ward_id)
    
    total = query.count()
    breached = query.filter(Ticket.sla_breached == True).count()
    on_time = query.filter(
        Ticket.status.in_(["resolved", "closed"]),
        Ticket.sla_breached == False
    ).count()
    
    return {
        "total_tickets": total,
        "sla_breached": breached,
        "resolved_on_time": on_time,
        "compliance_rate": (on_time / total * 100) if total > 0 else 0
    }

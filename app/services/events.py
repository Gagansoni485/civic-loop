from sqlalchemy.orm import Session

from app.models import Event


def log_event(db: Session, ticket_id: int, kind: str, detail: str = "") -> None:
    """Events are only ever added, never edited or deleted."""
    db.add(Event(ticket_id=ticket_id, kind=kind, detail=detail))

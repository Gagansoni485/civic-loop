from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app import config
from app.models import Ticket
from app.services.geo import haversine_m
from app.services.classifier import cosine_similarity


def find_duplicate(
    db: Session, 
    category: str, 
    lat: float, 
    lng: float, 
    now: datetime,
    image_embedding: list[float] | None = None,
    similarity_threshold: float = 0.75
) -> Ticket | None:
    """
    Closest open ticket of the same category inside the radius and time window.
    
    Enhanced with image similarity check:
    - Same category
    - Within DUPLICATE_RADIUS_M (50m)
    - Within time window (recent days)
    - Image similarity > threshold (if embeddings available)
    """
    cutoff = now - timedelta(days=config.DUPLICATE_WINDOW_DAYS)
    candidates = (
        db.query(Ticket)
        .filter(
            Ticket.category == category, 
            Ticket.status != "resolved", 
            Ticket.created_at >= cutoff
        )
        .all()
    )
    
    nearby = []
    for t in candidates:
        dist = haversine_m(lat, lng, t.lat, t.lng)
        if dist <= config.DUPLICATE_RADIUS_M:
            # Check image similarity if embeddings available
            if image_embedding and t.image_embedding:
                similarity = cosine_similarity(image_embedding, t.image_embedding)
                if similarity >= similarity_threshold:
                    nearby.append((dist, similarity, t))
            else:
                # No embeddings, rely on location and category only
                nearby.append((dist, 1.0, t))
    
    # Return closest by distance, with highest similarity as tiebreaker
    return min(nearby, key=lambda x: (x[0], -x[1]))[2] if nearby else None


def check_repeat_defect(
    db: Session,
    lat: float,
    lng: float,
    category: str,
    months_back: int = 12,
    radius_m: float = 20.0
) -> Ticket | None:
    """
    Check if this location had a resolved ticket in the past.
    Used for contractor accountability.
    
    Returns the most recent resolved ticket at this location, or None.
    """
    cutoff = datetime.utcnow() - timedelta(days=months_back * 30)
    
    candidates = (
        db.query(Ticket)
        .filter(
            Ticket.category == category,
            Ticket.status == "resolved",
            Ticket.created_at >= cutoff
        )
        .all()
    )
    
    # Find resolved tickets within radius
    nearby = []
    for t in candidates:
        dist = haversine_m(lat, lng, t.lat, t.lng)
        if dist <= radius_m:
            nearby.append((t.created_at, t))
    
    # Return most recent
    if nearby:
        return max(nearby, key=lambda x: x[0])[1]
    
    return None

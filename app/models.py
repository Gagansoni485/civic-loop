from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, ForeignKey, Integer, Float, String, Text, DateTime, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    """User accounts with role-based access."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20))  # citizen, officer, admin
    
    # Officer-specific fields
    officer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("officers.id"), nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Ward(Base):
    """Administrative ward boundaries."""
    __tablename__ = "wards"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    ward_number: Mapped[int]
    # Store boundary as GeoJSON text for SQLite compatibility
    boundary_geojson: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    population: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    area_sqkm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class Officer(Base):
    """Municipal officers in hierarchical structure."""
    __tablename__ = "officers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(50))  # ward_je, zonal_commissioner, municipal_commissioner
    level: Mapped[int] = mapped_column(Integer)  # 1=JE, 2=Zonal, 3=Municipal
    ward_id: Mapped[Optional[int]] = mapped_column(ForeignKey("wards.id"), nullable=True)
    email: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Contractor(Base):
    """Contractors responsible for infrastructure work."""
    __tablename__ = "contractors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    registration_number: Mapped[str] = mapped_column(String(50), unique=True)
    contact_person: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str] = mapped_column(String(100))
    is_blacklisted: Mapped[bool] = mapped_column(Boolean, default=False)
    blacklist_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorkOrder(Base):
    """Work orders linking contractors to infrastructure repairs."""
    __tablename__ = "work_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    contractor_id: Mapped[int] = mapped_column(ForeignKey("contractors.id"))
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"))
    work_type: Mapped[str] = mapped_column(String(50))  # road_paving, streetlight_install, etc.
    start_date: Mapped[datetime] = mapped_column(DateTime)
    completion_date: Mapped[datetime] = mapped_column(DateTime)
    warranty_months: Mapped[int] = mapped_column(Integer, default=6)
    cost: Mapped[float] = mapped_column(Float)
    # Store work area as GeoJSON text for SQLite compatibility
    work_area_geojson: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)  # CL-2026-001
    category: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(String(200))
    
    # Lat/lng coordinates
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    
    severity: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="submitted")  # submitted | assigned | in_progress | resolved | closed | needs_review | rejected
    reporter_count: Mapped[int] = mapped_column(Integer, default=1)
    priority: Mapped[str] = mapped_column(String(20), default="medium")  # low | medium | high | critical
    priority_score: Mapped[float] = mapped_column(Float, default=0.0)
    priority_reasons: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Reporter tracking
    reported_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reporter_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    
    # Assignment and escalation
    ward_id: Mapped[Optional[int]] = mapped_column(ForeignKey("wards.id"), nullable=True)
    assigned_officer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("officers.id"), nullable=True)
    escalation_level: Mapped[int] = mapped_column(Integer, default=0)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    escalated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    escalated_to_officer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("officers.id"), nullable=True)
    
    # SLA tracking
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sla_due_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sla_breached: Mapped[bool] = mapped_column(Boolean, default=False)
    clock_stopped: Mapped[bool] = mapped_column(Boolean, default=False)
    clock_stop_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    clock_stop_requested_by: Mapped[Optional[int]] = mapped_column(ForeignKey("officers.id"), nullable=True)
    clock_stop_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Images
    image_url: Mapped[str] = mapped_column(String(500))
    resolution_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Privacy blurring
    contains_faces: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_stripped: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Image embeddings for similarity search
    image_embedding: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string for embedding
    
    # Duplicate detection
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_ticket_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tickets.id"), nullable=True)
    
    # Verification details
    verification_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    verification_details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    verification_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Contractor tracking
    is_repeat_defect: Mapped[bool] = mapped_column(Boolean, default=False)
    original_work_order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("work_orders.id"), nullable=True)
    linked_contractor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contractors.id"), nullable=True)
    
    # Citizen feedback
    citizen_verified: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    citizen_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reopened_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Timestamps
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_ticket_status', 'status'),
        Index('idx_ticket_ward', 'ward_id'),
        Index('idx_ticket_officer', 'assigned_officer_id'),
        Index('idx_ticket_created', 'created_at'),
        Index('idx_ticket_location', 'latitude', 'longitude'),
    )


class Event(Base):
    """Append-only audit trail for every ticket change."""
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(50))  # created, assigned, escalated, resolved, reopened, etc.
    description: Mapped[str] = mapped_column(Text, default="")
    officer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("officers.id"), nullable=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    event_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

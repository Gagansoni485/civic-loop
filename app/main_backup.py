from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app import config
from app.database import Base, engine, get_db
from app.models import Event, Ticket, Ward, Officer, Contractor, WorkOrder
from app.services import classifier, duplicates, priority, sla, verification, contractors
from app.services.events import log_event

Base.metadata.create_all(engine)
Path(config.UPLOAD_DIR).mkdir(exist_ok=True)
Path("evidence_reports").mkdir(exist_ok=True)

app = FastAPI(
    title="CivicLoop",
    description="Accountability layer for civic complaints - tickets close only when repairs are verified",
    version="2.0.0"
)

# Add CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React dev server
        "http://localhost:5173",  # Vite default port
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ZONES = priority.load_zones()
ROOT = Path(__file__).resolve().parent.parent
DEMO = {"hours": 0}  # fast-forwarded demo time


def clock() -> datetime:
    return datetime.utcnow() + timedelta(hours=DEMO["hours"])


def save_image(data: bytes) -> str:
    path = Path(config.UPLOAD_DIR) / f"{uuid4().hex}.jpg"
    path.write_bytes(data)
    return str(path)


def refresh_priority(ticket: Ticket, now: datetime) -> None:
    """Update ticket priority score and reasons."""
    ticket.priority, ticket.priority_reasons = priority.priority_score(ticket, ZONES, now)


def assign_to_ward(ticket: Ticket, db: Session) -> None:
    """Find which ward contains this ticket's location and assign it."""
    # Simple lat/lng check for SQLite (in PostGIS would use ST_Contains)
    try:
        # For now, skip ward assignment in SQLite
        # In production with PostGIS, this would use spatial queries
        pass
    except Exception as e:
        print(f"Ward assignment skipped: {e}")
        pass


def to_dict(row) -> dict:
    """Convert SQLAlchemy model to dict."""
    result = {}
    for col in row.__table__.columns:
        value = getattr(row, col.name)
        # Convert datetime to ISO string
        if isinstance(value, datetime):
            result[col.name] = value.isoformat()
        else:
            result[col.name] = value
    return result


@app.get("/")
def root():
    """API root - redirect to docs."""
    return {
        "message": "CivicLoop API",
        "version": "2.0.0",
        "docs": "/docs",
        "features": [
            "Verified closure with scene matching",
            "Risk-based priority scoring",
            "Contractor accountability",
            "Privacy-first reporting"
        ]
    }


@app.post("/reports")
async def create_report(
    image: UploadFile = File(...),
    lat: float = Form(...),
    lng: float = Form(...),
    category_hint: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    New complaint: classify, check for duplicates, assign priority.
    
    - **image**: Photo of the problem (faces/plates should be blurred client-side)
    - **lat**: Latitude
    - **lng**: Longitude
    - **category_hint**: Optional category suggestion from citizen
    """
    now = clock()
    data = await image.read()
    
    # 1. Classify the problem
    category = classifier.classify(data, category_hint)
    
    # 2. Generate image embedding for similarity
    embedding = classifier.get_image_embedding(data)
    
    # 3. Check for duplicates (location + image similarity)
    ticket = duplicates.find_duplicate(db, category, lat, lng, now, embedding)
    
    if ticket:
        # Merge with existing ticket
        ticket.reporter_count += 1
        log_event(db, ticket.id, "duplicate_merged", f"Reporter #{ticket.reporter_count}")
    else:
        # Create new ticket
        ticket = Ticket(
            category=category,
            lat=lat,
            lng=lng,
            severity=config.SEVERITY.get(category, 5),
            sla_deadline=sla.deadline_for(category, now),
            before_image=save_image(data),
            image_embedding=embedding,
            created_at=now
        )
        
        db.add(ticket)
        db.flush()
        
        # Check for repeat defect (contractor accountability)
        contractor_info = contractors.find_responsible_contractor(db, ticket)
        if contractor_info:
            ticket.is_repeat_defect = True
            ticket.original_ticket_id = contractor_info['original_ticket']['id']
            ticket.linked_work_order_id = contractor_info['work_order']['id']
            log_event(
                db, 
                ticket.id, 
                "repeat_defect_detected",
                f"Same location as ticket #{ticket.original_ticket_id}, contractor: {contractor_info['contractor']['name']}"
            )
        
        # Assign to ward and officer
        assign_to_ward(ticket, db)
        
        log_event(db, ticket.id, "created", category)
    
    # 4. Calculate priority
    refresh_priority(ticket, now)
    
    db.commit()
    db.refresh(ticket)
    
    result = to_dict(ticket)
    result['is_duplicate'] = ticket.reporter_count > 1
    
    return result


@app.get("/tickets")
def list_tickets(
    status: Optional[str] = Query(None, description="Filter by status"),
    ward_id: Optional[int] = Query(None, description="Filter by ward"),
    officer_id: Optional[int] = Query(None, description="Filter by assigned officer"),
    category: Optional[str] = Query(None, description="Filter by category"),
    escalated_only: bool = Query(False, description="Show only escalated tickets"),
    db: Session = Depends(get_db)
):
    """
    List tickets with optional filters.
    Returns tickets ordered by priority (most urgent first).
    """
    query = db.query(Ticket)
    
    if status:
        query = query.filter(Ticket.status == status)
    if ward_id:
        query = query.filter(Ticket.ward_id == ward_id)
    if officer_id:
        query = query.filter(Ticket.assigned_officer_id == officer_id)
    if category:
        query = query.filter(Ticket.category == category)
    if escalated_only:
        query = query.filter(Ticket.escalation_level > 0)
    
    tickets = query.order_by(Ticket.priority.desc()).all()
    return [to_dict(t) for t in tickets]


@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    """Get detailed ticket information including event history."""
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    
    # Get event history
    events = db.query(Event).filter(Event.ticket_id == ticket_id).order_by(Event.id).all()
    
    # Get contractor info if repeat defect
    contractor_info = None
    if ticket.is_repeat_defect and ticket.linked_work_order_id:
        contractor_info = contractors.find_responsible_contractor(db, ticket)
    
    result = to_dict(ticket)
    result['events'] = [to_dict(e) for e in events]
    result['contractor_info'] = contractor_info
    
    return result


@app.post("/tickets/{ticket_id}/resolution")
async def submit_resolution(
    ticket_id: int,
    image: UploadFile = File(...),
    lat: float = Form(...),
    lng: float = Form(...),
    accuracy_m: float = Form(10.0),
    officer_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Officer uploads repair photo for verification.
    
    System checks:
    1. Location matches original (within GPS accuracy)
    2. Scene matches (same place)
    3. Defect is gone
    
    Ticket closes only if all checks pass.
    """
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    
    if ticket.status == "resolved":
        raise HTTPException(400, "Ticket already resolved")
    
    # Read images
    after = await image.read()
    before = Path(ticket.before_image).read_bytes()
    
    # Run verification
    ok, reasons, details = verification.verify_resolution(
        ticket, before, after, lat, lng, accuracy_m
    )
    
    # Save after image
    ticket.after_image = save_image(after)
    ticket.verification_score = details['verification_score']
    ticket.verification_details = details
    
    # Update status
    old_status = ticket.status
    ticket.status = "resolved" if ok else "needs_review"
    
    # Log event
    log_event(
        db, 
        ticket.id, 
        "resolution_submitted",
        f"Status: {ticket.status}. " + "; ".join(reasons),
        officer_id=officer_id,
        event_metadata=details  # Updated field name
    )
    
    db.commit()
    
    return {
        "ticket_id": ticket_id,
        "status": ticket.status,
        "previous_status": old_status,
        "verified": ok,
        "reasons": reasons,
        "verification_details": details
    }


@app.post("/tickets/{ticket_id}/feedback")
def submit_citizen_feedback(
    ticket_id: int,
    verified: bool = Form(...),
    feedback: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Citizen confirms whether repair was actually done.
    Can reopen tickets that were falsely closed.
    """
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    
    ticket.citizen_verified = verified
    ticket.citizen_feedback = feedback
    
    if not verified and ticket.status == "resolved":
        # Reopen ticket
        ticket.status = "reopened"
        ticket.reopened_count += 1
        log_event(
            db,
            ticket.id,
            "reopened_by_citizen",
            f"Citizen reported issue not fixed. Feedback: {feedback or 'None'}"
        )
    elif verified:
        log_event(db, ticket.id, "citizen_verified", "Citizen confirmed repair")
    
    db.commit()
    
    return {
        "ticket_id": ticket_id,
        "status": ticket.status,
        "citizen_verified": verified
    }


@app.post("/tickets/{ticket_id}/clock-stop")
def request_clock_stop(
    ticket_id: int,
    reason: str = Form(...),
    officer_id: int = Form(...),
    db: Session = Depends(get_db)
):
    """
    Officer requests SLA timer pause (e.g., waiting for materials, bad weather).
    Requires supervisor approval in production.
    """
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    
    if ticket.clock_stopped:
        raise HTTPException(400, "Clock already stopped")
    
    # In demo, auto-approve. In production, needs supervisor approval
    ticket.clock_stopped = True
    ticket.clock_stop_reason = reason
    ticket.clock_stop_approved_by = officer_id  # Should be supervisor ID
    
    log_event(
        db,
        ticket.id,
        "clock_stopped",
        f"Reason: {reason}",
        officer_id=officer_id
    )
    
    db.commit()
    
    return {
        "ticket_id": ticket_id,
        "clock_stopped": True,
        "reason": reason
    }


@app.get("/tickets/{ticket_id}/evidence.pdf")
def get_evidence_report(ticket_id: int, db: Session = Depends(get_db)):
    """
    Generate and download contractor accountability evidence report.
    Only available for repeat defects.
    """
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    
    if not ticket.is_repeat_defect:
        raise HTTPException(400, "Not a repeat defect - no evidence report available")
    
    # Get contractor info
    contractor_info = contractors.find_responsible_contractor(db, ticket)
    if not contractor_info:
        raise HTTPException(404, "Contractor information not found")
    
    # Generate evidence report
    report = contractors.generate_evidence_report(db, ticket, contractor_info)
    
    # Generate PDF
    pdf_path = Path("evidence_reports") / f"ticket_{ticket_id}_evidence.pdf"
    contractors.generate_evidence_pdf(report, pdf_path)
    
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"ticket_{ticket_id}_evidence.pdf"
    )


@app.get("/wards/scores")
def get_ward_performance(db: Session = Depends(get_db)):
    """
    Ward-level performance metrics for public transparency.
    
    Returns metrics for each ward:
    - Total tickets
    - Resolved count
    - Resolution rate
    - Average resolution time
    - Overdue count
    - Reopen rate
    """
    wards = db.query(Ward).all()
    results = []
    
    for ward in wards:
        tickets = db.query(Ticket).filter(Ticket.ward_id == ward.id).all()
        
        if not tickets:
            continue
        
        total = len(tickets)
        resolved = [t for t in tickets if t.status == "resolved"]
        citizen_verified = [t for t in resolved if t.citizen_verified == True]
        reopened = [t for t in tickets if t.reopened_count > 0]
        overdue = [t for t in tickets if t.status != "resolved" and clock() > t.sla_deadline]
        
        # Calculate average resolution time
        resolution_times = []
        for t in resolved:
            if t.created_at and t.after_image:
                # Approximate: use last event time
                events = db.query(Event).filter(
                    Event.ticket_id == t.id,
                    Event.kind.in_(["resolution_submitted", "resolved"])
                ).all()
                if events:
                    resolution_time = (events[-1].at - t.created_at).total_seconds() / 3600
                    resolution_times.append(resolution_time)
        
        avg_resolution_hours = sum(resolution_times) / len(resolution_times) if resolution_times else 0
        
        results.append({
            "ward_id": ward.id,
            "ward_name": ward.name,
            "ward_number": ward.ward_number,
            "metrics": {
                "total_tickets": total,
                "resolved": len(resolved),
                "resolution_rate": round(len(resolved) / total * 100, 1) if total > 0 else 0,
                "citizen_verified_rate": round(len(citizen_verified) / len(resolved) * 100, 1) if resolved else 0,
                "avg_resolution_hours": round(avg_resolution_hours, 1),
                "overdue": len(overdue),
                "reopened": len(reopened),
                "reopen_rate": round(len(reopened) / len(resolved) * 100, 1) if resolved else 0
            }
        })
    
    # Sort by resolution rate (best first)
    results.sort(key=lambda x: x['metrics']['resolution_rate'], reverse=True)
    
    return {
        "generated_at": clock().isoformat(),
        "wards": results,
        "summary": {
            "total_wards": len(results),
            "best_ward": results[0] if results else None,
            "needs_attention": [w for w in results if w['metrics']['overdue'] > 5]
        }
    }


@app.post("/admin/fast-forward")
def fast_forward(hours: int = Query(...), db: Session = Depends(get_db)):
    """
    Demo helper: fast-forward time and trigger SLA escalation.
    """
    DEMO["hours"] += hours
    now = clock()
    
    # Run SLA escalation
    escalated = sla.escalate_overdue(db, now)
    
    # Refresh all priorities
    for ticket in db.query(Ticket).filter(Ticket.status != "resolved").all():
        refresh_priority(ticket, now)
    
    db.commit()
    
    return {
        "fast_forwarded_hours": hours,
        "current_demo_time": now.isoformat(),
        "escalated_ticket_ids": [t.id for t in escalated],
        "escalated_count": len(escalated)
    }


@app.get("/stats")
def get_system_stats(db: Session = Depends(get_db)):
    """Overall system statistics."""
    total_tickets = db.query(Ticket).count()
    resolved = db.query(Ticket).filter(Ticket.status == "resolved").count()
    needs_review = db.query(Ticket).filter(Ticket.status == "needs_review").count()
    overdue = db.query(Ticket).filter(
        Ticket.status != "resolved",
        Ticket.sla_deadline < clock()
    ).count()
    
    repeat_defects = db.query(Ticket).filter(Ticket.is_repeat_defect == True).count()
    
    return {
        "total_tickets": total_tickets,
        "resolved": resolved,
        "resolution_rate": round(resolved / total_tickets * 100, 1) if total_tickets > 0 else 0,
        "needs_review": needs_review,
        "overdue": overdue,
        "repeat_defects": repeat_defects,
        "categories": db.query(Ticket.category).distinct().all()
    }


# Static files
app.mount("/uploads", StaticFiles(directory=config.UPLOAD_DIR), name="uploads")
app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")

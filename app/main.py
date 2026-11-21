"""
CivicLoop Backend - Complete Implementation
with Authentication, Role-based Access, and Full Flowchart Features
"""
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import FastAPI, File, Form, UploadFile, Depends, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine, Base
from app.models import User, Ticket, Ward, Officer, Contractor, WorkOrder, Event
from app.services import auth, sla_manager, privacy_blur
from app.services.simple_services import (
    classify_image,
    find_similar_tickets,
    verify_scene_match,
    generate_evidence_report
)

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="CivicLoop API",
    description="AI-powered civic complaint management with accountability",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Upload directories
UPLOAD_DIR = "uploads"
PROCESSED_DIR = "uploads/processed"
EVIDENCE_DIR = "evidence_reports"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(EVIDENCE_DIR, exist_ok=True)


# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Auth dependency
def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> User:
    """Extract and validate JWT token from Authorization header."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme"
            )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header"
        )
    
    user = auth.get_current_user(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    return user


def get_current_user_optional(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get current user if authenticated, None otherwise (for optional auth endpoints)."""
    if not authorization:
        return None
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            return None
    except ValueError:
        return None
    
    user = auth.get_current_user(db, token)
    return user


def require_role(allowed_roles: List[str]):
    """Decorator to require specific roles."""
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(allowed_roles)}"
            )
        return current_user
    return role_checker


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@app.post("/auth/register")
def register(
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    phone: Optional[str] = Form(None),
    role: str = Form("citizen"),
    db: Session = Depends(get_db)
):
    """Register a new user account."""
    try:
        user = auth.create_user(
            db=db,
            email=email,
            password=password,
            full_name=full_name,
            role=role,
            phone=phone
        )
        
        # Create access token
        access_token = auth.create_access_token(
            data={"sub": str(user.id), "role": user.role}
        )
        
        return {
            "message": "Registration successful",
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "phone": user.phone
            },
            "access_token": access_token,
            "token_type": "bearer"
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@app.post("/auth/login")
def login(
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Login and receive JWT token."""
    user = auth.authenticate_user(db, email, password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Create access token
    access_token = auth.create_access_token(
        data={"sub": str(user.id), "role": user.role}
    )
    
    return {
        "message": "Login successful",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "phone": user.phone,
            "officer_id": user.officer_id
        },
        "access_token": access_token,
        "token_type": "bearer"
    }


@app.get("/auth/me")
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current authenticated user info."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "phone": current_user.phone,
        "officer_id": current_user.officer_id,
        "is_verified": current_user.is_verified,
        "permissions": auth.get_user_permissions(current_user)
    }


@app.post("/auth/logout")
def logout(current_user: User = Depends(get_current_user)):
    """Logout (client should discard token)."""
    return {"message": "Logged out successfully"}


# ============================================================================
# TICKET CREATION (FLOWCHART: Take photo -> Blur -> Classify -> Duplicate Check)
# ============================================================================

def generate_ticket_id() -> str:
    """Generate unique ticket ID like CL-2026-001."""
    year = datetime.now().year
    random_suffix = uuid.uuid4().hex[:6].upper()
    return f"CL-{year}-{random_suffix}"


@app.post("/reports")
async def create_report(
    image: UploadFile = File(...),
    description: str = Form(...),
    location: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    category: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Create a new ticket with image processing:
    1. Save original image
    2. Blur faces and strip metadata (privacy)
    3. Classify defect category (if not provided)
    4. Check for duplicates within 50m
    5. Calculate priority score
    6. Route to ward officer
    7. Start SLA timer
    """
    try:
        # Step 1: Save original image
        image_filename = f"{uuid.uuid4().hex}.jpg"
        image_path = os.path.join(UPLOAD_DIR, image_filename)
        
        with open(image_path, "wb") as f:
            content = await image.read()
            f.write(content)
        
        # Step 2: Privacy processing - strip metadata only (frontend already blurred faces)
        processed_path, privacy_metadata = privacy_blur.process_image_for_privacy(
            image_path,
            PROCESSED_DIR,
            blur_faces_enabled=False  # Frontend already handles face blur client-side
        )
        
        # Use processed image
        final_image_url = f"/uploads/processed/{os.path.basename(processed_path)}"
        
        # Step 3: Classify category if not provided
        if not category or category == "other":
            try:
                category = classify_image(processed_path)
            except Exception as e:
                print(f"Classification error: {e}")
                category = "other"
        
        # Step 4: Check for duplicates within 50m
        similar_tickets = find_similar_tickets(
            db,
            processed_path,
            latitude,
            longitude,
            radius_m=50,
            category=category
        )
        
        is_duplicate = len(similar_tickets) > 0
        parent_ticket_id = similar_tickets[0].id if is_duplicate else None
        reporter_count = 1
        
        if is_duplicate:
            # Add reporter to existing ticket
            parent_ticket = similar_tickets[0]
            parent_ticket.reporter_count += 1
            reporter_count = parent_ticket.reporter_count
            
            # Update priority
            parent_ticket.priority_score += 10  # Increase priority with more reporters
            
            # Create event
            event = Event(
                ticket_id=parent_ticket.id,
                event_type="duplicate_reported",
                description=f"Duplicate report added. Total reporters: {reporter_count}",
                user_id=current_user.id if current_user else None
            )
            db.add(event)
            db.commit()
            
            return {
                "message": "Similar issue already reported",
                "is_duplicate": True,
                "id": parent_ticket.id,
                "ticket_id": parent_ticket.ticket_id,
                "category": parent_ticket.category,
                "priority": parent_ticket.priority,
                "priority_score": parent_ticket.priority_score,
                "reporter_count": reporter_count,
                "parent_ticket": {
                    "id": parent_ticket.id,
                    "ticket_id": parent_ticket.ticket_id,
                    "status": parent_ticket.status,
                    "created_at": parent_ticket.created_at.isoformat()
                }
            }
        
        # Step 5: Create new ticket
        ticket_id = generate_ticket_id()
        
        # Determine ward based on coordinates (simplified - you'd use actual ward boundaries)
        ward = db.query(Ward).first()  # TODO: Implement proper ward lookup by coordinates
        
        # Calculate SLA deadline
        created_at = datetime.utcnow()
        sla_due_date = sla_manager.calculate_sla_deadline(category, created_at)
        
        # Calculate initial priority score based on severity and nearby schools/hospitals
        # (You can enhance this with OSM data)
        priority_score = 50.0  # Base score
        priority = "medium"
        
        if category in ["water_supply", "drainage"]:
            priority_score += 20
            priority = "high"
        
        # Create ticket
        ticket = Ticket(
            ticket_id=ticket_id,
            category=category,
            description=description,
            location=location,
            latitude=latitude,
            longitude=longitude,
            status="submitted",
            priority=priority,
            priority_score=priority_score,
            reporter_count=1,
            reported_by_user_id=current_user.id if current_user else None,
            reporter_phone=phone,
            ward_id=ward.id if ward else None,
            image_url=final_image_url,
            contains_faces=privacy_metadata.get("contains_faces", False),
            metadata_stripped=privacy_metadata.get("metadata_stripped", False),
            is_duplicate=False,
            created_at=created_at,
            sla_due_date=sla_due_date
        )
        
        db.add(ticket)
        db.flush()  # Get ticket ID
        
        # Create creation event
        event = Event(
            ticket_id=ticket.id,
            event_type="created",
            description=f"Ticket created: {category} at {location}",
            user_id=current_user.id if current_user else None,
            event_metadata={
                "category": category,
                "priority": priority,
                "contains_faces": privacy_metadata.get("contains_faces"),
                "face_count": privacy_metadata.get("face_count")
            }
        )
        db.add(event)
        
        # Step 6: Route to ward officer (auto-assign to lowest level officer in ward)
        if ward:
            ward_officer = db.query(Officer).filter(
                Officer.ward_id == ward.id,
                Officer.level == 1,  # JE level
                Officer.is_active == True
            ).first()
            
            if ward_officer:
                ticket.assigned_officer_id = ward_officer.id
                ticket.status = "assigned"
                ticket.assigned_at = datetime.utcnow()
                
                # Create assignment event
                assign_event = Event(
                    ticket_id=ticket.id,
                    event_type="assigned",
                    description=f"Assigned to {ward_officer.name} ({ward_officer.role})",
                    officer_id=ward_officer.id,
                    event_metadata={"officer_name": ward_officer.name}
                )
                db.add(assign_event)
        
        db.commit()
        db.refresh(ticket)
        
        return {
            "message": "Ticket created successfully",
            "ticket_id": ticket.ticket_id,
            "id": ticket.id,
            "category": ticket.category,
            "status": ticket.status,
            "priority": ticket.priority,
            "priority_score": ticket.priority_score,
            "sla_due_date": ticket.sla_due_date.isoformat() if ticket.sla_due_date else None,
            "assigned_officer_id": ticket.assigned_officer_id,
            "privacy": {
                "faces_blurred": privacy_metadata.get("face_count", 0),
                "metadata_stripped": privacy_metadata.get("metadata_stripped", False)
            }
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating ticket: {str(e)}"
        )


# ============================================================================
# TICKET LISTING AND DETAILS
# ============================================================================

@app.get("/tickets")
def list_tickets(
    status: Optional[str] = None,
    ward_id: Optional[int] = None,
    category: Optional[str] = None,
    escalated_only: bool = False,
    assigned_to_me: bool = False,
    my_tickets: bool = False,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """List tickets with filters based on user role."""
    query = db.query(Ticket)
    
    # Role-based filtering
    if current_user:
        if current_user.role == "citizen" and my_tickets:
            # Citizens can only see their own tickets
            query = query.filter(Ticket.reported_by_user_id == current_user.id)
        elif current_user.role == "officer" and assigned_to_me:
            # Officers see tickets assigned to them
            if current_user.officer_id:
                query = query.filter(
                    (Ticket.assigned_officer_id == current_user.officer_id) |
                    (Ticket.escalated_to_officer_id == current_user.officer_id)
                )
    
    # Apply filters
    if status:
        query = query.filter(Ticket.status == status)
    if ward_id:
        query = query.filter(Ticket.ward_id == ward_id)
    if category:
        query = query.filter(Ticket.category == category)
    if escalated_only:
        query = query.filter(Ticket.escalated == True)
    
    # Order by priority and creation date
    query = query.order_by(Ticket.priority_score.desc(), Ticket.created_at.desc())
    
    tickets = query.all()
    
    return [
        {
            "id": t.id,
            "ticket_id": t.ticket_id,
            "category": t.category,
            "description": t.description,
            "location": t.location,
            "status": t.status,
            "priority": t.priority,
            "reporter_count": t.reporter_count,
            "escalated": t.escalated,
            "sla_breached": t.sla_breached,
            "created_at": t.created_at.isoformat(),
            "sla_due_date": t.sla_due_date.isoformat() if t.sla_due_date else None,
            "assigned_officer_id": t.assigned_officer_id,
            "image_url": t.image_url
        }
        for t in tickets
    ]


@app.get("/tickets/{ticket_id}")
def get_ticket_detail(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Get detailed ticket information with events."""
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found"
        )
    
    # Check access permission
    if current_user and current_user.role == "citizen":
        if ticket.reported_by_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
    
    # Get events
    events = db.query(Event).filter(Event.ticket_id == ticket.id).order_by(Event.created_at.desc()).all()
    
    return {
        "ticket": {
            "id": ticket.id,
            "ticket_id": ticket.ticket_id,
            "category": ticket.category,
            "description": ticket.description,
            "location": ticket.location,
            "latitude": ticket.latitude,
            "longitude": ticket.longitude,
            "status": ticket.status,
            "priority": ticket.priority,
            "reporter_count": ticket.reporter_count,
            "escalated": ticket.escalated,
            "escalation_level": ticket.escalation_level,
            "sla_breached": ticket.sla_breached,
            "clock_stopped": ticket.clock_stopped,
            "created_at": ticket.created_at.isoformat(),
            "sla_due_date": ticket.sla_due_date.isoformat() if ticket.sla_due_date else None,
            "assigned_officer_id": ticket.assigned_officer_id,
            "image_url": ticket.image_url,
            "resolution_image_url": ticket.resolution_image_url,
            "verification_score": ticket.verification_score,
            "verification_passed": ticket.verification_passed,
            "citizen_verified": ticket.citizen_verified,
            "is_repeat_defect": ticket.is_repeat_defect
        },
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "description": e.description,
                "created_at": e.created_at.isoformat(),
                "officer_id": e.officer_id,
                "notes": e.notes
            }
            for e in events
        ]
    }


# Continue in next message...


# ============================================================================
# TICKET RESOLUTION (FLOWCHART: Officer repairs -> Check location/scene -> Close/Review)
# ============================================================================

@app.post("/tickets/{ticket_id}/resolution")
async def submit_resolution(
    ticket_id: str,
    image: UploadFile = File(...),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["officer", "admin"]))
):
    """
    Submit resolution photo with AI verification:
    1. Officer uploads repair photo
    2. Check location (within 15m of original)
    3. Check scene matching (same view)
    4. If all checks pass -> ticket closed
    5. If checks fail -> needs_review status
    """
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Check if officer is assigned
    if current_user.role == "officer":
        if current_user.officer_id not in [ticket.assigned_officer_id, ticket.escalated_to_officer_id]:
            raise HTTPException(status_code=403, detail="Not assigned to this ticket")
    
    try:
        # Save resolution image
        resolution_filename = f"{uuid.uuid4().hex}_resolution.jpg"
        resolution_path = os.path.join(PROCESSED_DIR, resolution_filename)
        
        with open(resolution_path, "wb") as f:
            content = await image.read()
            f.write(content)
        
        resolution_url = f"/uploads/processed/{resolution_filename}"
        
        # Get original image path
        original_image_path = ticket.image_url.replace("/uploads/processed/", PROCESSED_DIR + "/")
        
        # Verify scene match
        verification_result = verify_scene_match(
            original_image_path,
            resolution_path,
            max_distance_m=15
        )
        
        # Update ticket
        ticket.resolution_image_url = resolution_url
        ticket.verification_score = verification_result["match_score"]
        ticket.verification_details = verification_result
        ticket.verification_passed = verification_result["match_score"] > 0.3
        
        # Determine status based on verification
        if ticket.verification_passed:
            ticket.status = "resolved"
            ticket.resolved_at = datetime.utcnow()
            status_msg = "Ticket resolved - verification passed"
        else:
            ticket.status = "needs_review"
            status_msg = "Needs review - verification failed"
        
        # Create event
        event = Event(
            ticket_id=ticket.id,
            event_type="resolution_submitted",
            description=status_msg,
            officer_id=current_user.officer_id,
            notes=notes,
            event_metadata={
                "verification_score": verification_result["match_score"],
                "keypoints_matched": verification_result.get("keypoints_matched", 0),
                "ssim_score": verification_result.get("ssim_score", 0),
                "passed": ticket.verification_passed
            }
        )
        db.add(event)
        
        db.commit()
        db.refresh(ticket)
        
        return {
            "message": status_msg,
            "ticket_id": ticket.ticket_id,
            "status": ticket.status,
            "verification": {
                "score": verification_result["match_score"],
                "passed": ticket.verification_passed,
                "keypoints_matched": verification_result.get("keypoints_matched"),
                "ssim_score": verification_result.get("ssim_score"),
                "reasons": verification_result.get("reasons", [])
            }
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error submitting resolution: {str(e)}")


@app.post("/tickets/{ticket_id}/retry-resolution")
async def retry_resolution(
    ticket_id: str,
    image: UploadFile = File(...),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["officer", "admin"]))
):
    """Officer retries resolution after review failure."""
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    if ticket.status != "needs_review":
        raise HTTPException(status_code=400, detail="Ticket is not in needs_review status")
    
    # Same as submit_resolution
    return await submit_resolution(ticket_id, image, notes, db, current_user)


# ============================================================================
# CITIZEN VERIFICATION
# ============================================================================

@app.post("/tickets/{ticket_id}/feedback")
def submit_citizen_feedback(
    ticket_id: str,
    verified: bool = Form(...),
    feedback: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Citizen verifies if issue is truly resolved.
    If not verified -> ticket reopened
    """
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    # Check if citizen owns this ticket
    if current_user and current_user.role == "citizen":
        if ticket.reported_by_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    if ticket.status not in ["resolved", "closed"]:
        raise HTTPException(status_code=400, detail="Ticket must be resolved first")
    
    ticket.citizen_verified = verified
    ticket.citizen_feedback = feedback
    
    if not verified:
        # Reopen ticket
        ticket.status = "reopened"
        ticket.reopened_count += 1
        ticket.resolved_at = None
        
        # Penalize contractor if repeat defect
        if ticket.linked_contractor_id:
            ticket.is_repeat_defect = True
        
        event_desc = f"Ticket reopened by citizen. Reason: {feedback or 'Not satisfied'}"
    else:
        ticket.status = "closed"
        ticket.closed_at = datetime.utcnow()
        event_desc = "Citizen verified resolution - ticket closed"
    
    # Create event
    event = Event(
        ticket_id=ticket.id,
        event_type="citizen_feedback",
        description=event_desc,
        user_id=current_user.id if current_user else None,
        notes=feedback,
        event_metadata={"verified": verified, "reopened_count": ticket.reopened_count}
    )
    db.add(event)
    
    db.commit()
    
    return {
        "message": "Feedback submitted",
        "ticket_id": ticket.ticket_id,
        "status": ticket.status,
        "citizen_verified": verified
    }


# ============================================================================
# SLA AND ESCALATION
# ============================================================================

@app.post("/tickets/{ticket_id}/clock-stop")
def request_clock_stop(
    ticket_id: str,
    reason: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["officer", "admin"]))
):
    """Officer requests to stop SLA clock (requires approval)."""
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    success = sla_manager.request_clock_stop(
        db,
        ticket,
        current_user.officer_id,
        reason
    )
    
    if not success:
        raise HTTPException(status_code=400, detail="Clock already stopped")
    
    return {
        "message": "Clock stop requested - awaiting approval",
        "ticket_id": ticket.ticket_id,
        "reason": reason
    }


@app.post("/tickets/{ticket_id}/approve-clock-stop")
def approve_clock_stop(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    """Admin approves clock stop request."""
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    success = sla_manager.approve_clock_stop(db, ticket, current_user.officer_id)
    
    if not success:
        raise HTTPException(status_code=400, detail="No clock stop request pending")
    
    return {
        "message": "Clock stop approved",
        "ticket_id": ticket.ticket_id
    }


@app.post("/tickets/{ticket_id}/escalate")
def manual_escalate(
    ticket_id: str,
    reason: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["officer", "admin"]))
):
    """Manually escalate a ticket to next level."""
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    success = sla_manager.escalate_ticket(db, ticket, reason)
    
    if not success:
        raise HTTPException(status_code=400, detail="Cannot escalate - already at top level")
    
    return {
        "message": "Ticket escalated",
        "ticket_id": ticket.ticket_id,
        "escalation_level": ticket.escalation_level,
        "escalated_to": ticket.escalated_to_officer_id
    }


@app.post("/admin/check-escalations")
def check_escalations(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    """Background job: Check and escalate overdue tickets."""
    count = sla_manager.check_and_escalate_overdue_tickets(db)
    
    return {
        "message": f"Escalated {count} overdue tickets",
        "escalated_count": count
    }


# ============================================================================
# WARD PERFORMANCE & SCORECARDS
# ============================================================================

@app.get("/wards/scores")
def get_ward_scores(db: Session = Depends(get_db)):
    """Get ward performance scoreboard."""
    wards = db.query(Ward).all()
    
    ward_scores = []
    
    for ward in wards:
        tickets = db.query(Ticket).filter(Ticket.ward_id == ward.id)
        
        total = tickets.count()
        resolved = tickets.filter(Ticket.status.in_(["resolved", "closed"])).count()
        sla_breached = tickets.filter(Ticket.sla_breached == True).count()
        escalated = tickets.filter(Ticket.escalated == True).count()
        verified = tickets.filter(Ticket.citizen_verified == True).count()
        repeat_defects = tickets.filter(Ticket.is_repeat_defect == True).count()
        
        # Calculate response time
        assigned_tickets = tickets.filter(Ticket.assigned_at.isnot(None)).all()
        if assigned_tickets:
            response_times = [
                (t.assigned_at - t.created_at).total_seconds() / 3600
                for t in assigned_tickets
            ]
            avg_response_hours = sum(response_times) / len(response_times)
        else:
            avg_response_hours = 0
        
        # Calculate resolution time
        resolved_tickets = tickets.filter(Ticket.resolved_at.isnot(None)).all()
        if resolved_tickets:
            resolution_times = [
                (t.resolved_at - t.created_at).total_seconds() / 3600
                for t in resolved_tickets
            ]
            avg_resolution_hours = sum(resolution_times) / len(resolution_times)
        else:
            avg_resolution_hours = 0
        
        # Calculate overall score (0-100)
        resolution_rate = (resolved / total * 100) if total > 0 else 0
        sla_compliance = ((total - sla_breached) / total * 100) if total > 0 else 100
        verification_rate = (verified / resolved * 100) if resolved > 0 else 0
        
        overall_score = (
            resolution_rate * 0.3 +
            sla_compliance * 0.3 +
            verification_rate * 0.25 +
            (100 - (escalated / total * 100) if total > 0 else 100) * 0.15
        )
        
        ward_scores.append({
            "ward_id": ward.id,
            "ward_name": ward.name,
            "ward_number": ward.ward_number,
            "total_tickets": total,
            "resolved_tickets": resolved,
            "resolution_rate": round(resolution_rate, 2),
            "sla_breaches": sla_breached,
            "escalated_count": escalated,
            "citizen_verification_rate": round(verification_rate, 2),
            "repeat_defect_count": repeat_defects,
            "avg_response_time_hours": round(avg_response_hours, 2),
            "avg_resolution_time_hours": round(avg_resolution_hours, 2),
            "overall_score": round(overall_score, 2)
        })
    
    # Sort by overall score
    ward_scores.sort(key=lambda x: x["overall_score"], reverse=True)
    
    return {
        "generated_at": datetime.utcnow().isoformat(),
        "wards": ward_scores
    }


# ============================================================================
# STATISTICS
# ============================================================================

@app.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """Get system-wide statistics."""
    total_tickets = db.query(Ticket).count()
    resolved = db.query(Ticket).filter(Ticket.status.in_(["resolved", "closed"])).count()
    pending = db.query(Ticket).filter(Ticket.status.in_(["submitted", "assigned", "in_progress"])).count()
    needs_review = db.query(Ticket).filter(Ticket.status == "needs_review").count()
    overdue = db.query(Ticket).filter(
        Ticket.sla_breached == True,
        Ticket.status.notin_(["resolved", "closed"])
    ).count()
    repeat_defects = db.query(Ticket).filter(Ticket.is_repeat_defect == True).count()
    
    # Resolution time
    resolved_tickets = db.query(Ticket).filter(Ticket.resolved_at.isnot(None)).all()
    if resolved_tickets:
        resolution_times = [
            (t.resolved_at - t.created_at).total_seconds() / 3600
            for t in resolved_tickets
        ]
        avg_resolution_time_hours = sum(resolution_times) / len(resolution_times)
    else:
        avg_resolution_time_hours = 0
    
    # Category breakdown
    categories = db.query(
        Ticket.category,
        func.count(Ticket.id).label("count")
    ).group_by(Ticket.category).all()
    
    return {
        "total_tickets": total_tickets,
        "pending_tickets": pending,
        "resolved": resolved,
        "resolution_rate": round((resolved / total_tickets * 100) if total_tickets > 0 else 0, 2),
        "needs_review": needs_review,
        "overdue": overdue,
        "repeat_defects": repeat_defects,
        "avg_resolution_time_hours": round(avg_resolution_time_hours, 2),
        "categories": [{"category": c[0], "count": c[1]} for c in categories]
    }


# ============================================================================
# EVIDENCE REPORTS
# ============================================================================

@app.get("/tickets/{ticket_id}/evidence.pdf")
def download_evidence(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["officer", "admin"]))
):
    """Generate and download contractor evidence PDF."""
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    
    if ticket.status not in ["resolved", "closed"]:
        raise HTTPException(status_code=400, detail="Ticket must be resolved to generate evidence")
    
    try:
        pdf_path = generate_evidence_report(ticket, EVIDENCE_DIR)
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=f"evidence_{ticket.ticket_id}.pdf"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating evidence: {str(e)}")


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

@app.post("/admin/officers")
def create_officer(
    name: str = Form(...),
    role: str = Form(...),
    level: int = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    ward_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    """Create a new officer."""
    officer = Officer(
        name=name,
        role=role,
        level=level,
        email=email,
        phone=phone,
        ward_id=ward_id,
        is_active=True
    )
    
    db.add(officer)
    db.commit()
    db.refresh(officer)
    
    return {
        "message": "Officer created",
        "officer": {
            "id": officer.id,
            "name": officer.name,
            "role": officer.role,
            "level": officer.level
        }
    }


@app.get("/admin/officers")
def list_officers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "officer"]))
):
    """List all officers."""
    officers = db.query(Officer).all()
    
    return [
        {
            "id": o.id,
            "name": o.name,
            "role": o.role,
            "level": o.level,
            "ward_id": o.ward_id,
            "email": o.email,
            "phone": o.phone,
            "is_active": o.is_active
        }
        for o in officers
    ]


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "features": [
            "authentication",
            "role-based-access",
            "privacy-blur",
            "ai-classification",
            "duplicate-detection",
            "scene-verification",
            "sla-tracking",
            "auto-escalation",
            "citizen-feedback",
            "ward-scorecards"
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

"""Simplified service implementations for quick deployment."""
import os
from typing import List
from PIL import Image
import cv2
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import func
from math import radians, cos, sin, asin, sqrt

from app.models import Ticket


def classify_image(image_path: str) -> str:
    """
    Classify defect category from image.
    For now returns 'other', can be enhanced with ML model later.
    """
    return "other"


def find_similar_tickets(
    db: Session,
    image_path: str,
    latitude: float,
    longitude: float,
    radius_m: int = 50,
    category: str = None
) -> List[Ticket]:
    """
    Find similar tickets within radius using geographic distance.
    """
    # Haversine distance calculation
    def haversine(lon1, lat1, lon2, lat2):
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371000  # Radius of earth in meters
        return c * r
    
    # Get tickets in same category
    query = db.query(Ticket).filter(
        Ticket.status.in_(["submitted", "assigned", "in_progress"])
    )
    
    if category:
        query = query.filter(Ticket.category == category)
    
    nearby_tickets = []
    for ticket in query.all():
        distance = haversine(longitude, latitude, ticket.longitude, ticket.latitude)
        if distance <= radius_m:
            nearby_tickets.append(ticket)
    
    return nearby_tickets


def verify_scene_match(
    original_image_path: str,
    resolution_image_path: str,
    max_distance_m: float = 15
) -> dict:
    """
    Verify if resolution photo matches original scene using ORB feature matching.
    """
    try:
        # Load images
        img1 = cv2.imread(original_image_path, cv2.IMREAD_GRAYSCALE)
        img2 = cv2.imread(resolution_image_path, cv2.IMREAD_GRAYSCALE)
        
        if img1 is None or img2 is None:
            return {
                "match_score": 0.0,
                "keypoints_matched": 0,
                "ssim_score": 0.0,
                "reasons": ["Failed to load images"]
            }
        
        # Initialize ORB detector
        orb = cv2.ORB_create(nfeatures=500)
        
        # Find keypoints and descriptors
        kp1, des1 = orb.detectAndCompute(img1, None)
        kp2, des2 = orb.detectAndCompute(img2, None)
        
        if des1 is None or des2 is None:
            return {
                "match_score": 0.0,
                "keypoints_matched": 0,
                "ssim_score": 0.0,
                "reasons": ["No keypoints detected"]
            }
        
        # Match features
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches = bf.match(des1, des2)
        matches = sorted(matches, key=lambda x: x.distance)
        
        # Calculate match score
        good_matches = [m for m in matches if m.distance < 50]
        match_ratio = len(good_matches) / min(len(kp1), len(kp2)) if min(len(kp1), len(kp2)) > 0 else 0
        
        # Simple SSIM calculation (structural similarity)
        # Resize images to same size for comparison
        h, w = min(img1.shape[0], img2.shape[0]), min(img1.shape[1], img2.shape[1])
        img1_resized = cv2.resize(img1, (w, h))
        img2_resized = cv2.resize(img2, (w, h))
        
        # Calculate simple correlation
        correlation = cv2.matchTemplate(img1_resized, img2_resized, cv2.TM_CCORR_NORMED)[0][0]
        ssim_score = max(0, correlation)
        
        # Combined score
        match_score = (match_ratio * 0.6 + ssim_score * 0.4)
        
        reasons = []
        if match_score > 0.3:
            reasons.append("Scene similarity detected")
        else:
            reasons.append("Different scenes - verification failed")
        
        return {
            "match_score": float(match_score),
            "keypoints_matched": len(good_matches),
            "ssim_score": float(ssim_score),
            "reasons": reasons
        }
        
    except Exception as e:
        return {
            "match_score": 0.0,
            "keypoints_matched": 0,
            "ssim_score": 0.0,
            "reasons": [f"Error: {str(e)}"]
        }


def generate_evidence_report(ticket, output_dir: str) -> str:
    """
    Generate PDF evidence report for a ticket.
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import inch
    from datetime import datetime
    
    os.makedirs(output_dir, exist_ok=True)
    filename = f"evidence_{ticket.ticket_id}.pdf"
    filepath = os.path.join(output_dir, filename)
    
    c = canvas.Canvas(filepath, pagesize=letter)
    width, height = letter
    
    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(1*inch, height - 1*inch, f"Evidence Report - Ticket {ticket.ticket_id}")
    
    # Details
    c.setFont("Helvetica", 12)
    y = height - 1.5*inch
    
    details = [
        f"Category: {ticket.category}",
        f"Location: {ticket.location}",
        f"Status: {ticket.status}",
        f"Created: {ticket.created_at.strftime('%Y-%m-%d %H:%M')}",
        f"Resolved: {ticket.resolved_at.strftime('%Y-%m-%d %H:%M') if ticket.resolved_at else 'N/A'}",
        f"Verification Score: {ticket.verification_score:.2f}" if ticket.verification_score else "Verification: Pending",
        f"Citizen Verified: {'Yes' if ticket.citizen_verified else 'No' if ticket.citizen_verified is not None else 'Pending'}",
    ]
    
    for line in details:
        c.drawString(1*inch, y, line)
        y -= 0.3*inch
    
    # Description
    y -= 0.3*inch
    c.drawString(1*inch, y, "Description:")
    y -= 0.3*inch
    c.setFont("Helvetica", 10)
    # Wrap text
    description_lines = [ticket.description[i:i+80] for i in range(0, len(ticket.description), 80)]
    for line in description_lines[:5]:  # Max 5 lines
        c.drawString(1.2*inch, y, line)
        y -= 0.25*inch
    
    # Add images if available
    if ticket.image_url and os.path.exists(ticket.image_url.replace("/uploads/", "uploads/")):
        y -= 0.5*inch
        c.setFont("Helvetica-Bold", 12)
        c.drawString(1*inch, y, "Original Issue Photo:")
        # Note: Adding actual images would require more complex reportlab code
        y -= 0.3*inch
        c.setFont("Helvetica", 10)
        c.drawString(1.2*inch, y, f"Image: {ticket.image_url}")
    
    if ticket.resolution_image_url:
        y -= 0.5*inch
        c.setFont("Helvetica-Bold", 12)
        c.drawString(1*inch, y, "Resolution Photo:")
        y -= 0.3*inch
        c.setFont("Helvetica", 10)
        c.drawString(1.2*inch, y, f"Image: {ticket.resolution_image_url}")
    
    # Footer
    c.setFont("Helvetica", 8)
    c.drawString(1*inch, 0.5*inch, f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    c.drawString(1*inch, 0.3*inch, "CivicLoop - Civic Complaint Management System")
    
    c.save()
    return filepath

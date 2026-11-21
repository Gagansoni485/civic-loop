import cv2
import numpy as np
from typing import Tuple, List, Dict

from app import config
from app.services.classifier import defect_present
from app.services.geo import haversine_m


def count_scene_matches(before: bytes, after: bytes) -> int:
    """Number of ORB features shared by the two photos (same place -> many matches)."""
    orb = cv2.ORB_create(1000)
    images = [cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_GRAYSCALE) for b in (before, after)]
    if any(img is None for img in images):
        return 0
    descriptors = [orb.detectAndCompute(img, None)[1] for img in images]
    if any(d is None for d in descriptors):
        return 0
    pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(descriptors[0], descriptors[1], k=2)
    return sum(1 for p in pairs if len(p) == 2 and p[0].distance < 0.75 * p[1].distance)


def structural_similarity(before: bytes, after: bytes) -> float:
    """
    Calculate structural similarity between before and after images.
    Returns a score between 0 and 1.
    """
    try:
        from skimage.metrics import structural_similarity as ssim
        
        # Convert to images
        img1 = cv2.imdecode(np.frombuffer(before, np.uint8), cv2.IMREAD_GRAYSCALE)
        img2 = cv2.imdecode(np.frombuffer(after, np.uint8), cv2.IMREAD_GRAYSCALE)
        
        if img1 is None or img2 is None:
            return 0.0
        
        # Resize to same dimensions
        h = min(img1.shape[0], img2.shape[0])
        w = min(img1.shape[1], img2.shape[1])
        img1 = cv2.resize(img1, (w, h))
        img2 = cv2.resize(img2, (w, h))
        
        # Calculate SSIM
        score, _ = ssim(img1, img2, full=True)
        return float(score)
    except Exception:
        return 0.0


def verify_resolution(
    ticket, 
    before: bytes, 
    after: bytes, 
    lat: float, 
    lng: float, 
    accuracy_m: float
) -> Tuple[bool, List[str], Dict]:
    """
    Comprehensive verification of repair.
    
    Returns:
        (ok, reasons, details)
        - ok: True if all checks pass
        - reasons: List of failure reasons (empty if ok)
        - details: Dictionary with all check scores for transparency
    """
    reasons = []
    details = {}

    # 1. Geofence check
    distance = haversine_m(ticket.lat, ticket.lng, lat, lng)
    allowed = config.VERIFY_RADIUS_M + accuracy_m
    details['distance_m'] = round(distance, 2)
    details['allowed_distance_m'] = round(allowed, 2)
    details['location_ok'] = distance <= allowed
    
    if distance > allowed:
        reasons.append(
            f"Location mismatch: photo taken {distance:.0f}m away "
            f"(allowed {allowed:.0f}m including GPS accuracy)"
        )

    # 2. Scene matching (ORB features)
    matches = count_scene_matches(before, after)
    details['orb_matches'] = matches
    details['required_matches'] = config.SCENE_MATCH_MIN
    details['scene_match_ok'] = matches >= config.SCENE_MATCH_MIN
    
    if matches < config.SCENE_MATCH_MIN:
        reasons.append(
            f"Scene mismatch: only {matches} matching features "
            f"(need {config.SCENE_MATCH_MIN}). Different location or angle?"
        )

    # 3. Structural similarity (optional, more robust)
    ssim_score = structural_similarity(before, after)
    details['structural_similarity'] = round(ssim_score, 3)
    details['similar_scene'] = ssim_score > 0.3  # Lower threshold, allows for changes
    
    # If ORB fails but SSIM is decent, note it
    if matches < config.SCENE_MATCH_MIN and ssim_score > 0.4:
        details['scene_match_ok'] = True  # Override with SSIM
        reasons = [r for r in reasons if 'Scene mismatch' not in r]  # Remove scene error

    # 4. Defect gone check
    still_present = defect_present(after, ticket.category)
    details['defect_still_visible'] = still_present
    details['defect_check_ok'] = not still_present
    
    if still_present:
        reasons.append(
            f"Defect still visible: {ticket.category} detected in after photo. "
            "Issue may not be fully resolved."
        )

    # 5. Calculate overall verification score
    passed_checks = sum([
        details['location_ok'],
        details['scene_match_ok'],
        details['defect_check_ok']
    ])
    details['verification_score'] = round(passed_checks / 3.0, 2)
    details['passed_checks'] = passed_checks
    details['total_checks'] = 3

    # Decision: All critical checks must pass
    ok = len(reasons) == 0
    
    # If borderline, suggest review
    if not ok and passed_checks >= 2:
        reasons.append(
            "Note: Some checks passed. Human review recommended before final decision."
        )

    return ok, reasons, details

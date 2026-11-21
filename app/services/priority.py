import json
import math
from datetime import datetime
from pathlib import Path
from functools import lru_cache
from typing import List, Dict, Tuple
import httpx

from app import config
from app.services.geo import haversine_m


def load_zones() -> list[dict]:
    """Schools, hospitals and bus stops, e.g. extracted from OpenStreetMap."""
    path = Path(config.ZONES_FILE)
    return json.loads(path.read_text()) if path.exists() else []


@lru_cache(maxsize=100)
def fetch_nearby_poi(lat: float, lng: float, radius_m: int = 500) -> List[Dict]:
    """
    Fetch nearby points of interest from OpenStreetMap Overpass API.
    Cached to avoid repeated API calls.
    
    Returns list of POIs with their type and distance.
    """
    overpass_url = "https://overpass-api.de/api/interpreter"
    
    # Overpass QL query for schools, hospitals, bus stops
    query = f"""
    [out:json][timeout:10];
    (
      node["amenity"="school"](around:{radius_m},{lat},{lng});
      node["amenity"="hospital"](around:{radius_m},{lat},{lng});
      node["amenity"="clinic"](around:{radius_m},{lat},{lng});
      node["highway"="bus_stop"](around:{radius_m},{lat},{lng});
      node["amenity"="kindergarten"](around:{radius_m},{lat},{lng});
    );
    out body;
    """
    
    try:
        response = httpx.post(
            overpass_url, 
            data={"data": query},
            timeout=10.0
        )
        
        if response.status_code == 200:
            data = response.json()
            pois = []
            
            for element in data.get('elements', []):
                poi_lat = element.get('lat')
                poi_lng = element.get('lon')
                tags = element.get('tags', {})
                amenity = tags.get('amenity', tags.get('highway', 'unknown'))
                name = tags.get('name', amenity)
                
                pois.append({
                    'kind': amenity,
                    'name': name,
                    'lat': poi_lat,
                    'lng': poi_lng
                })
            
            return pois
    except Exception:
        # If API fails, return empty list
        pass
    
    return []


def get_proximity_factors(ticket, zones: List[Dict], use_osm: bool = True) -> Tuple[float, List[str]]:
    """
    Calculate proximity-based priority factors.
    
    Returns: (zone_weight, reasons)
    """
    reasons = []
    zone_weight = 0.0
    nearest = None
    
    # Try OpenStreetMap first if enabled
    if use_osm:
        try:
            osm_pois = fetch_nearby_poi(ticket.lat, ticket.lng, radius_m=config.ZONE_RADIUS_M)
            zones = zones + osm_pois  # Combine with static zones
        except Exception:
            pass
    
    # Find nearest critical zone
    for zone in zones:
        dist = haversine_m(ticket.lat, ticket.lng, zone["lat"], zone["lng"])
        weight = config.ZONE_WEIGHT.get(zone["kind"], 0.0)
        
        if dist <= config.ZONE_RADIUS_M and weight > zone_weight:
            zone_weight = weight
            nearest = (zone.get("name", zone["kind"]), zone["kind"], dist)
    
    if nearest:
        name, kind, dist = nearest
        reasons.append(f"{dist:.0f}m from {name} ({kind})")
    
    return zone_weight, reasons


def priority_score(
    ticket, 
    zones: list[dict], 
    now: datetime,
    use_osm: bool = True
) -> tuple[float, list[str]]:
    """
    Calculate priority score with explainable reasons.
    
    Formula: severity × (1 + log(reporters)) × (1 + zone_weight) × (1 + overdue_factor)
    
    Every factor is >= 1, so none can zero the score.
    
    Returns: (score, reasons)
    """
    reasons = []
    
    # 1. Severity (from category)
    severity = ticket.severity
    reasons.append(f"Category: {ticket.category} (severity {severity}/10)")
    
    # 2. Reporter count (logarithmic to prevent spam inflation)
    reporter_factor = 1 + math.log(ticket.reporter_count)
    if ticket.reporter_count > 1:
        reasons.append(f"{ticket.reporter_count} people reported this")
    
    # 3. Proximity to critical zones
    zone_weight, zone_reasons = get_proximity_factors(ticket, zones, use_osm)
    reasons.extend(zone_reasons)
    
    # 4. Overdue time (increases urgency)
    overdue_days = max(0.0, (now - ticket.sla_deadline).total_seconds() / 86400)
    overdue_factor = overdue_days / 7.0  # Normalize to weeks
    
    if overdue_days > 0:
        reasons.append(f"{overdue_days:.1f} days overdue")
    else:
        # Show remaining time
        remaining = (ticket.sla_deadline - now).total_seconds() / 3600
        if remaining < 24:
            reasons.append(f"{remaining:.1f} hours until deadline")
    
    # 5. Escalation level (higher = more urgent)
    escalation_factor = 1.0 + (ticket.escalation_level * 0.5)
    if ticket.escalation_level > 0:
        reasons.append(f"Escalated to level {ticket.escalation_level}")
    
    # Calculate final score
    score = (
        severity * 
        reporter_factor * 
        (1 + zone_weight) * 
        (1 + overdue_factor) * 
        escalation_factor
    )
    
    return round(score, 2), reasons

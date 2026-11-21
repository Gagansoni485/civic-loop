"""Tunable settings. Replace the SLA hours with your city's citizen charter values."""

DUPLICATE_RADIUS_M = 50
DUPLICATE_WINDOW_DAYS = 14

VERIFY_RADIUS_M = 15          # repair photo must be this close (plus GPS accuracy)
SCENE_MATCH_MIN = 15          # minimum ORB feature matches between before/after

SLA_HOURS = {"live_wire": 24, "garbage": 24, "water_leak": 72, "streetlight": 72, "pothole": 168}
SEVERITY = {"live_wire": 5, "pothole": 3, "water_leak": 3, "streetlight": 2, "garbage": 1}

ESCALATION_CHAIN = ["ward_je", "zonal_commissioner", "municipal_commissioner"]
ESCALATION_STEP_HOURS = 24

ZONE_WEIGHT = {"school": 1.0, "hospital": 1.0, "bus_stop": 0.5}
ZONE_RADIUS_M = 200
ZONES_FILE = "data/zones.sample.json"   # replace with an OpenStreetMap extract

UPLOAD_DIR = "uploads"

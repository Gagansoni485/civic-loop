from datetime import datetime
from types import SimpleNamespace

from app.services.geo import haversine_m
from app.services.priority import priority_score

NOW = datetime(2026, 1, 1)
SCHOOL = [{"kind": "school", "lat": 21.25, "lng": 81.63}]


def make_ticket(**overrides):
    base = dict(category="pothole", severity=3, lat=21.25, lng=81.63,
                reporter_count=1, sla_deadline=datetime(2026, 1, 10))
    return SimpleNamespace(**{**base, **overrides})


def test_same_point_has_zero_distance():
    assert haversine_m(21.25, 81.63, 21.25, 81.63) == 0


def test_nearby_school_raises_priority_and_explains_why():
    plain, _ = priority_score(make_ticket(), [], NOW)
    near, reasons = priority_score(make_ticket(), SCHOOL, NOW)
    assert near > plain
    assert any("school" in r for r in reasons)


def test_more_reporters_raise_priority():
    one, _ = priority_score(make_ticket(reporter_count=1), [], NOW)
    many, _ = priority_score(make_ticket(reporter_count=8), [], NOW)
    assert many > one

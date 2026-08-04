# app/services/security_service.py

import math
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models.models import Complaint

MAX_ALLOWED_DISTANCE_KM = 1.0
VELOCITY_WINDOW_HOURS = 24
VELOCITY_THRESHOLD = 3  # more than this many reports on the same shop in the window triggers a flag


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculates the great-circle distance between two lat/lon points in kilometers,
    using the Haversine formula.
    """
    R = 6371.0  # Earth's radius in km

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def check_shop_velocity(db: Session, shop_name: str) -> int:
    """
    Returns the number of complaints filed against this shop_name in the
    last VELOCITY_WINDOW_HOURS hours (case-insensitive match).
    Used to detect potential coordinated/spam attacks against a specific shop.
    """
    if not shop_name or not shop_name.strip():
        return 0

    window_start = datetime.utcnow() - timedelta(hours=VELOCITY_WINDOW_HOURS)

    count = db.query(Complaint).filter(
        Complaint.shop_name.ilike(shop_name.strip()),
        Complaint.created_at >= window_start
    ).count()

    return count
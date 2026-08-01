# app/db/seed_markets.py

from app.db.session import SessionLocal
from app.models.models import Market

def seed_markets():
    db = SessionLocal()

    markets_data = [
        {"name": "Aabpara Market", "latitude": 33.7107, "longitude": 73.0836},
        {"name": "G-9 Markaz (Karachi Company)", "latitude": 33.6941, "longitude": 73.0363},
        {"name": "Melody Market, G-6", "latitude": 33.7089, "longitude": 73.0679},
        {"name": "F-10 Markaz", "latitude": 33.6938, "longitude": 73.0119},
        {"name": "I-8 Markaz", "latitude": 33.6693, "longitude": 73.0827},
        {"name": "Itwar Bazar (Sector I-9)", "latitude": 33.6650, "longitude": 73.0836},
        {"name": "Super Market, F-6", "latitude": 33.7255, "longitude": 73.0904},
        {"name": "Jinnah Super Market, F-7", "latitude": 33.7215, "longitude": 73.0654},
    ]

    for m in markets_data:
        existing = db.query(Market).filter_by(name=m["name"]).first()
        if not existing:
            db.add(Market(**m))

    db.commit()
    db.close()
    print("Markets seeded successfully.")


if __name__ == "__main__":
    seed_markets()
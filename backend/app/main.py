# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import users, admin, rates, markets, complaints, ocr_test, forecast
from app.db.session import SessionLocal
from app.models.models import User, UserRole
from app.core.security import hash_password
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="PriceGuard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict before production deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory="app/uploads"), name="uploads")

        #--Routers--
app.include_router(users.router)
app.include_router(admin.router)
app.include_router(rates.router)
app.include_router(markets.router)
app.include_router(complaints.router)
app.include_router(ocr_test.router)
app.include_router(forecast.router)


@app.on_event("startup")
def create_default_admin():
    db = SessionLocal()
    try:
        existing_admin = db.query(User).filter(User.role == UserRole.admin).first()
        if not existing_admin:
            default_admin = User(
                full_name="Default Admin",
                email="admin@priceguard.com",
                hashed_password=hash_password("Admin@123"),  # change this after first login
                role=UserRole.admin,
                is_verified=True,  # admin skips email verification
            )
            db.add(default_admin)
            db.commit()
            print("Default admin created: admin@priceguard.com / Admin@123")
        else:
            print("Admin account already exists — skipping default admin creation.")
    finally:
        db.close()


@app.get("/")
def root():
    return {"message": "PriceGuard API is running."}
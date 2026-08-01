# app/api/routers/users.py

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import User
from app.schemas.user import UserCreate, UserResponse, Token, OTPVerifyRequest, MessageResponse
from app.core.security import hash_password, verify_password, create_access_token
from app.core.mail import generate_otp, send_otp_email
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/users", tags=["Users & Auth"])

OTP_EXPIRY_MINUTES = 10


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered.")

    otp = generate_otp()

    new_user = User(
        full_name=user_data.full_name,
        email=user_data.email,
        phone_number=user_data.phone_number,
        hashed_password=hash_password(user_data.password),
        otp=otp,
        otp_expiry=datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    email_sent = send_otp_email(new_user.email, otp, new_user.full_name)
    if not email_sent:
        # Don't block signup if email fails — but flag it clearly for debugging
        print(f"WARNING: OTP email failed to send to {new_user.email}")

    return new_user


@router.post("/verify-email", response_model=MessageResponse)
def verify_email(payload: OTPVerifyRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if user.is_verified:
        return MessageResponse(message="Email already verified.")

    if not user.otp or user.otp != payload.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP.")

    if user.otp_expiry and datetime.utcnow() > user.otp_expiry:
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new one.")

    user.is_verified = True
    user.otp = None
    user.otp_expiry = None
    db.commit()

    return MessageResponse(message="Email verified successfully. You can now log in.")


@router.post("/resend-otp", response_model=MessageResponse)
def resend_otp(email: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if user.is_verified:
        return MessageResponse(message="Email already verified.")

    otp = generate_otp()
    user.otp = otp
    user.otp_expiry = datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES)
    db.commit()

    send_otp_email(user.email, otp, user.full_name)
    return MessageResponse(message="A new OTP has been sent to your email.")


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Admins bypass email verification (useful for your default admin account)
    if user.role.value != "admin" and not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before logging in."
        )

    access_token = create_access_token(data={"sub": str(user.id), "role": user.role.value})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
def get_my_profile(current_user: User = Depends(get_current_user)):
    return current_user
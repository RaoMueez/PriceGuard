# app/api/routers/users.py

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import logging
logger = logging.getLogger(__name__)

from app.db.session import get_db
from app.models.models import User
from app.schemas.user import UserCreate, UserResponse, Token, OTPVerifyRequest, ResendOTPRequest, UserUpdate, MessageResponse
from app.core.security import hash_password, verify_password, create_access_token
from app.core.mail import generate_otp, send_otp_email
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/users", tags=["Users & Auth"])

OTP_EXPIRY_SECONDS = 180


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered.")

    # NEW — explicit pre-check for duplicate phone number. Previously this
    # endpoint only checked email, so signing up with a phone number that
    # already existed would crash into an unhandled 500 from the database's
    # unique constraint instead of a clean error.
    if user_data.phone_number:
        existing_phone = db.query(User).filter(User.phone_number == user_data.phone_number).first()
        if existing_phone:
            raise HTTPException(status_code=400, detail="This phone number is already registered.")

    otp = generate_otp()

    new_user = User(
        full_name=user_data.full_name,
        email=user_data.email,
        phone_number=user_data.phone_number,  # already validated + normalized by UserCreate's field_validator
        hashed_password=hash_password(user_data.password),
        otp=otp,
        otp_expiry=datetime.utcnow() + timedelta(seconds=OTP_EXPIRY_SECONDS),
    )
    db.add(new_user)

    try:
        db.commit()
    except IntegrityError:
        # Safety net for a race condition — two signups with the same
        # phone number landing at almost the same instant, both passing
        # the pre-check above before either has committed.
        db.rollback()
        raise HTTPException(status_code=400, detail="This phone number is already registered.")

    db.refresh(new_user)

    email_sent = send_otp_email(new_user.email, otp, new_user.full_name)
    if not email_sent:
        logger.warning(f"OTP email failed to send to {new_user.email}")

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
def resend_otp(payload: ResendOTPRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if user.is_verified:
        return MessageResponse(message="Email already verified.")

    otp = generate_otp()
    user.otp = otp
    user.otp_expiry = datetime.utcnow() + timedelta(seconds=OTP_EXPIRY_SECONDS)
    db.commit()

    send_otp_email(user.email, otp, user.full_name)
    return MessageResponse(message="A new OTP has been sent to your email.")


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    email = form_data.username.lower().strip()
    user = db.query(User).filter(User.email == email).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

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


@router.put("/me", response_model=UserResponse)
def update_my_profile(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Partial update — only fields actually included in the request body get
    changed. Email is deliberately NOT updatable here (no re-verification
    flow exists yet).
    """
    if payload.full_name is not None:
        current_user.full_name = payload.full_name

    if payload.phone_number is not None:
        # NEW — explicit pre-check for duplicate phone number, same
        # reasoning as signup above: clean error now instead of relying
        # solely on the database constraint to catch it.
        existing_phone = (
            db.query(User)
            .filter(User.phone_number == payload.phone_number, User.id != current_user.id)
            .first()
        )
        if existing_phone:
            raise HTTPException(
                status_code=400,
                detail="This phone number is already registered to another account.",
            )
        current_user.phone_number = payload.phone_number  # already validated + normalized

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="This phone number is already registered to another account.",
        )

    db.refresh(current_user)
    return current_user
from pydantic import BaseModel, EmailStr, Field, field_validator
from uuid import UUID
from datetime import datetime
import re
from app.models.models import UserRole


# ------------------------------------------------------------------
# PAKISTANI PHONE NUMBER VALIDATION / NORMALIZATION
#
# Accepts: 03XXXXXXXXX, +923XXXXXXXXX, 923XXXXXXXXX, 00923XXXXXXXXX
# Rejects anything else. Whatever format is entered gets normalized to
# a single canonical form (+923XXXXXXXXX) before it's ever compared or
# stored — this is what makes duplicate detection work regardless of
# which format someone types.
# ------------------------------------------------------------------
_PK_PHONE_PATTERN = re.compile(r"^(?:\+92|0092|92|0)3\d{9}$")


def normalize_pk_phone(raw: str) -> str:
    raw = raw.strip()
    if not _PK_PHONE_PATTERN.match(raw):
        raise ValueError(
            "Please enter a valid Pakistani mobile number "
            "(e.g. 03XXXXXXXXX or +923XXXXXXXXX)."
        )

    digits_only = re.sub(r"[^\d]", "", raw)  # strip the leading "+" too, if present

    if digits_only.startswith("0092"):
        core = digits_only[4:]
    elif digits_only.startswith("92"):
        core = digits_only[2:]
    elif digits_only.startswith("0"):
        core = digits_only[1:]
    else:
        core = digits_only

    return f"+92{core}"


class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    phone_number: str | None = None
    password: str = Field(min_length=8)

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v):
        return v.lower().strip()

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v):
        if v is None or v == "":
            return None
        return normalize_pk_phone(v)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v):
        if v is None:
            return v
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Full name must be at least 2 characters.")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: UUID
    full_name: str
    email: EmailStr
    phone_number: str | None
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True  # allows returning SQLAlchemy objects directly


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class OTPVerifyRequest(BaseModel):
    email: EmailStr
    otp: str

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v):
        return v.lower().strip()


class ResendOTPRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v):
        return v.lower().strip()


class MessageResponse(BaseModel):
    message: str


class UserUpdate(BaseModel):
    full_name: str | None = None
    phone_number: str | None = None

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v):
        if v is None or v == "":
            return None
        return normalize_pk_phone(v)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v):
        if v is None:
            return v
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Full name must be at least 2 characters.")
        return v
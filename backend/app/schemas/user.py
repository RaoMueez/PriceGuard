from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime
from app.models.models import UserRole


class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    phone_number: str | None = None
    password: str


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
    created_at: datetime

    class Config:
        from_attributes = True  # allows returning SQLAlchemy objects directly


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
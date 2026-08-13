import enum
import uuid
from datetime import datetime, date

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, ForeignKey,
    DateTime, Date, Enum, UniqueConstraint, Index, Text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class UserRole(str, enum.Enum):
    citizen = "citizen"
    admin = "admin"


class ComplaintStatus(str, enum.Enum):
    pending = "pending"
    verified = "verified"
    dismissed = "dismissed"
    resolved = "Resolved" 
    auto_rejected_no_overpricing = "Auto-Rejected: No Overpricing"
    auto_rejected_invalid_image = "Auto-Rejected: Invalid Receipt Image"
    suspicious_price_mismatch = "Suspicious: Price Mismatch"
    pending_manual_review_handwritten = "Pending Manual Review (Handwritten)"
    suspicious_location_mismatch = "Suspicious: Location Mismatch"
    potential_coordinated_attack = "Potential Coordinated Attack"
    suspicious_absurd_price_spam = "Suspicious: Absurd Price Spam" 


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = Column(String(150), nullable=False)
    email = Column(String(150), unique=True, nullable=False, index=True)
    phone_number = Column(String(20), unique=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.citizen, nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False, nullable=False)
    otp = Column(String(6), nullable=True)
    otp_expiry = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    complaints = relationship("Complaint", back_populates="user")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)  # Vegetables, Fruits, Dairy, Poultry & Meat

    commodities = relationship("Commodity", back_populates="category")


class Commodity(Base):
    __tablename__ = "commodities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    name = Column(String(100), nullable=False)
    unit = Column(String(20), nullable=False)  # kg, dozen, liter
    is_active = Column(Boolean, default=True)

    category = relationship("Category", back_populates="commodities")
    official_rates = relationship("OfficialRate", back_populates="commodity")
    complaints = relationship("Complaint", back_populates="commodity")

    __table_args__ = (
        UniqueConstraint("category_id", "name", name="uq_commodity_category_name"),
    )


class Market(Base):
    __tablename__ = "markets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(150), nullable=False)          # e.g., "Sector G-9 Sunday Market"
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    complaints = relationship("Complaint", back_populates="market")

    __table_args__ = (
        Index("ix_markets_lat_long", "latitude", "longitude"),
    )


class OfficialRate(Base):
    __tablename__ = "official_rates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    commodity_id = Column(Integer, ForeignKey("commodities.id"), nullable=False)
    price = Column(Float, nullable=False)
    effective_date = Column(Date, nullable=False, default=date.today)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # admin who uploaded

    commodity = relationship("Commodity", back_populates="official_rates")

    __table_args__ = (
        UniqueConstraint("commodity_id", "effective_date",
                          name="uq_rate_per_commodity_market_date"),
        Index("ix_rates_commodity_date", "commodity_id", "effective_date"),
    )


class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    commodity_id = Column(Integer, ForeignKey("commodities.id"), nullable=False)
    market_id = Column(Integer, ForeignKey("markets.id"), nullable=False)

    shop_name = Column(String(255), nullable=True)

    reported_price = Column(Float, nullable=False)          # what the user says they were charged
    complaint_type = Column(String, nullable=False, default="overpricing")  # "overpricing" | "short_weight"
    amount_paid = Column(Float, nullable=True)      # lump sum the citizen actually paid
    quantity_stated = Column(Float, nullable=True)  # quantity bought (overpricing) or received (short_weight)
    official_price_at_submission = Column(Float, nullable=True)
    receipt_image_url = Column(String(500), nullable=False)
    ai_extracted_price = Column(Float, nullable=True)        # filled in after OCR
    ai_confidence = Column(Float, nullable=True)              # optional: OCR/anomaly confidence score

    # NEW — geo-fencing fields
    device_latitude = Column(Float, nullable=True)
    device_longitude = Column(Float, nullable=True)
    distance_from_market_km = Column(Float, nullable=True)

    # NEW — all triggered flags, comma-separated, for full admin transparency
    flags = Column(Text, nullable=True)

    status = Column(
    Enum(ComplaintStatus, values_callable=lambda enum_cls: [e.value for e in enum_cls]),
    default=ComplaintStatus.pending,
    nullable=False,
)
    created_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="complaints")
    commodity = relationship("Commodity", back_populates="complaints")
    market = relationship("Market", back_populates="complaints")

    __table_args__ = (
        Index("ix_complaints_status_date", "status", "created_at"),
        Index("ix_complaints_market_status", "market_id", "status"),
        Index("ix_complaints_shop_date", "shop_name", "created_at"),  # NEW — speeds up velocity check
    )
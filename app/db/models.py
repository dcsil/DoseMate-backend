import uuid
from datetime import datetime, date
from sqlalchemy import (
    Column,
    String,
    Boolean,
    Date,
    DateTime,
    Text,
    ForeignKey,
    Enum,
    ARRAY
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.database import Base
from pydantic import BaseModel
from typing import Optional, List

# ---------- USER MODEL ----------
class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String(320), unique=True, nullable=False, index=True)
    google_sub = Column(String, unique=True, nullable=True, index=True)
    name = Column(String(255), nullable=True)
    picture = Column(String(1024), nullable=True)
    auth_provider = Column(String(50), nullable=False, default="google")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    medications = relationship("Medication", back_populates="user", cascade="all, delete-orphan")
    schedules = relationship("MedicationSchedule", back_populates="user", cascade="all, delete-orphan")
    dose_logs = relationship("DoseLog", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} provider={self.auth_provider}>"

# ---------- API MODEL (not DB table) ----------
class Medicine(BaseModel):
    brand_name: str
    generic_name: Optional[str] = None
    manufacturer: Optional[str] = None
    indications: Optional[str] = None
    dosage: Optional[str] = None
    purpose: Optional[str] = None

# ---------- MEDICATION ----------
class Medication(Base):
    __tablename__ = "medications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    brand_name = Column(String, nullable=False)
    generic_name = Column(String, nullable=True)
    dosage = Column(String, nullable=True)
    manufacturer = Column(String, nullable=True)
    indications = Column(Text, nullable=True)
    purpose = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="medications")
    schedules = relationship(
        "MedicationSchedule",
        back_populates="medication",
        cascade="all, delete-orphan"
    )

# ---------- MEDICATION SCHEDULE ----------
class MedicationSchedule(Base):
    __tablename__ = "medication_schedules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    medication_id = Column(UUID(as_uuid=True), ForeignKey("medications.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    frequency = Column(String, nullable=False)
    time_of_day = Column(ARRAY(String), nullable=True)
    quantity = Column(String, nullable=True)
    strength = Column(String, nullable=True)
    days = Column(ARRAY(String), nullable=True)

    as_needed = Column(Boolean, default=False)
    food_instructions = Column(String, nullable=True)

    start_date = Column(Date, default=date.today)
    end_date = Column(Date, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="schedules")
    medication = relationship("Medication", back_populates="schedules")
    dose_logs = relationship(
        "DoseLog",
        back_populates="schedule",
        cascade="all, delete-orphan"
    )


# ---------- DOSE LOG ----------
class DoseLog(Base):
    __tablename__ = "dose_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schedule_id = Column(UUID(as_uuid=True), ForeignKey("medication_schedules.id"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    scheduled_time = Column(DateTime, nullable=False)
    taken_time = Column(DateTime, nullable=True)
    status = Column(Enum("pending", "taken", "missed", name="dose_status"), default="pending")

    # Relationships
    user = relationship("User", back_populates="dose_logs")
    schedule = relationship("MedicationSchedule", back_populates="dose_logs")

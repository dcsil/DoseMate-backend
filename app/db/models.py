import uuid
from datetime import datetime, date
from sqlalchemy import (
    Column,
    Integer,
    String,
    Enum,
    ForeignKey,
    Boolean,
    Date,
    DateTime,
    JSON
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from app.db.database import Base
from pydantic import BaseModel
from typing import Optional


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
    profile = relationship("UserProfile", back_populates="user" , cascade="all, delete-orphan", single_parent=True, uselist=False)

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} provider={self.auth_provider}>"


# ---------- USER PROFILE ----------
class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, index=True)

    age = Column(Integer, nullable=True)
    conditions = Column(ARRAY(String), nullable=False, default=[])
    allergies = Column(String, nullable=True)
    sleep_schedule = Column(String, nullable=True)   # "early" | "normal" | "late" | "irregular"
    activity_level = Column(String, nullable=True)   # "low" | "moderate" | "high" | "athlete"

    user = relationship("User", back_populates="profile", lazy="joined")


# ---------- API MODEL (not a DB table) ----------
class Medicine(BaseModel):
    brand_name: str
    generic_name: str
    manufacturer: str
    indications: Optional[str]
    dosage: Optional[str]


# ---------- MEDICATION ----------
class Medication(Base):
    __tablename__ = "medications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    brand_name = Column(String, nullable=False)
    generic_name = Column(String, nullable=True)
    dosage = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    image_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="medications")
    schedules = relationship("MedicationSchedule", back_populates="medication", cascade="all, delete-orphan")


# ---------- MEDICATION SCHEDULE ----------
class MedicationSchedule(Base):
    __tablename__ = "medication_schedules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    medication_id = Column(UUID(as_uuid=True), ForeignKey("medications.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    frequency = Column(String, nullable=False)  # e.g. "daily", "weekly", "as_needed"
    times_per_day = Column(Integer, default=1)
    time_of_day = Column(JSON, nullable=True)  # e.g. ["08:00", "20:00"]
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="schedules")
    medication = relationship("Medication", back_populates="schedules")
    dose_logs = relationship("DoseLog", back_populates="schedule", cascade="all, delete-orphan")


# ---------- DOSE LOG ----------
class DoseLog(Base):
    __tablename__ = "dose_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schedule_id = Column(UUID(as_uuid=True), ForeignKey("medication_schedules.id"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    scheduled_time = Column(DateTime, nullable=False)
    taken_time = Column(DateTime, nullable=True)
    status = Column(Enum("pending", "taken", "missed", name="dose_status"), default="pending")
    notes = Column(String, nullable=True)

    # Relationships
    user = relationship("User", back_populates="dose_logs")
    schedule = relationship("MedicationSchedule", back_populates="dose_logs")

from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel, EmailStr, UUID4


# ---------------------------------------------------------------------------
# USER SCHEMAS
# ---------------------------------------------------------------------------

class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    picture: Optional[str] = None
    auth_provider: Optional[str] = "google"
    is_active: bool = True


class UserCreate(UserBase):
    password: Optional[str] = None  # optional if using Google OAuth


class UserRead(UserBase):
    id: UUID4
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


# ---------------------------------------------------------------------------
# MEDICINE (non-DB model)
# ---------------------------------------------------------------------------

class Medicine(BaseModel):
    brand_name: str
    generic_name: str
    manufacturer: str
    indications: Optional[str]
    dosage: Optional[str]


# ---------------------------------------------------------------------------
# MEDICATION
# ---------------------------------------------------------------------------

class MedicationBase(BaseModel):
    brand_name: str
    generic_name: Optional[str] = None
    dosage: Optional[str] = None
    notes: Optional[str] = None
    image_metadata: Optional[dict] = None


class MedicationCreate(MedicationBase):
    user_id: UUID4


class MedicationRead(MedicationBase):
    id: UUID4
    user_id: UUID4
    created_at: datetime

    class Config:
        orm_mode = True


# ---------------------------------------------------------------------------
# MEDICATION SCHEDULE
# ---------------------------------------------------------------------------

class MedicationScheduleBase(BaseModel):
    start_date: date
    end_date: Optional[date] = None
    frequency: str
    times_per_day: int = 1
    time_of_day: Optional[List[str]] = None


class MedicationScheduleCreate(MedicationScheduleBase):
    medication_id: UUID4
    user_id: UUID4


class MedicationScheduleRead(MedicationScheduleBase):
    id: UUID4
    medication_id: UUID4
    user_id: UUID4
    created_at: datetime

    class Config:
        orm_mode = True


# ---------------------------------------------------------------------------
# DOSE LOG
# ---------------------------------------------------------------------------

class DoseLogBase(BaseModel):
    scheduled_time: datetime
    taken_time: Optional[datetime] = None
    status: Optional[str] = "pending"
    notes: Optional[str] = None


class DoseLogCreate(DoseLogBase):
    schedule_id: UUID4
    user_id: UUID4


class DoseLogRead(DoseLogBase):
    id: UUID4
    schedule_id: UUID4
    user_id: UUID4

    class Config:
        orm_mode = True

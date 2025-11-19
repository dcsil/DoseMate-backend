from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.db.database import get_db
from app.db.models import Medication, MedicationSchedule, User
from app.core.auth import get_current_user
from pydantic import BaseModel
from typing import Optional, List
import uuid

router = APIRouter()

# --- Medication schedule sent from frontend ---
class MedicationScheduleCreate(BaseModel):
    start_date: Optional[date] = date.today()
    end_date: Optional[date] = None

    frequency: str
    times: Optional[List[str]] = None
    days: Optional[List[str]] = None
    quantity: Optional[str] = None
    strength: Optional[str] = None

    asNeeded: bool = False
    foodInstructions: Optional[str] = None

# --- Medication info sent from frontend ---
class MedicationCreate(BaseModel):
    brand_name: str
    generic_name: Optional[str] = None
    dosage: Optional[str] = None
    manufacturer: Optional[str] = None
    indications: Optional[str] = None
    purpose: Optional[str] = None

# --- Wrapper for POST payload ---
class MedicationCreateWrapper(BaseModel):
    selectedMedicine: MedicationCreate
    medDetails: MedicationScheduleCreate

# --- Output schemas ---
class MedicationScheduleOut(BaseModel):
    id: uuid.UUID

    frequency: str
    time_of_day: Optional[List[str]] = None
    days: Optional[List[str]] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    quantity: Optional[str] = None
    strength: Optional[str] = None

    as_needed: bool = False
    food_instructions: Optional[str]

    model_config = {
        "from_attributes": True
    }

class MedicationOut(BaseModel):
    id: uuid.UUID

    brand_name: str
    generic_name: Optional[str]
    dosage: Optional[str]
    manufacturer: Optional[str]
    indications: Optional[str]
    schedules: List[MedicationScheduleOut] = []

    # TODO: make these fields dynamic
    purpose: Optional[str] = "general"
    adherence_score: Optional[int] = 99

    model_config = {
        "from_attributes": True
    }

# --- Routes ---
@router.post("/", response_model=MedicationOut)
async def create_user_medication(
    payload: MedicationCreateWrapper,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    med_data = payload.selectedMedicine
    sched_data = payload.medDetails

    # --- Create medication ---
    new_med = Medication(
        user_id=current_user.user_id,
        brand_name=med_data.brand_name,
        generic_name=med_data.generic_name,
        dosage=med_data.dosage,
        manufacturer=med_data.manufacturer,
        indications=med_data.indications,
    )
    db.add(new_med)
    await db.commit()
    await db.refresh(new_med)

    # --- Create schedule ---
    new_sched = MedicationSchedule(
        medication_id=new_med.id,
        user_id=current_user.user_id,
        frequency=sched_data.frequency,
        time_of_day=sched_data.times,
        days=sched_data.days,
        quantity=sched_data.quantity,
        strength=sched_data.strength,
        as_needed=sched_data.asNeeded,
        food_instructions=sched_data.foodInstructions,
        start_date=sched_data.start_date or date.today(),
        end_date=sched_data.end_date,
    )
    db.add(new_sched)
    await db.commit()

    # --- Eager-load schedules before returning ---
    await db.refresh(new_med, attribute_names=["schedules"])

    return MedicationOut.from_orm(new_med)


@router.get("/", response_model=List[MedicationOut])
async def get_user_medications(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Medication)
        .where(Medication.user_id == current_user.user_id)
        .options(selectinload(Medication.schedules))
    )
    meds = result.scalars().all()
    return [MedicationOut.from_orm(med) for med in meds]

@router.delete("/{medication_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_medication(
    medication_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Medication).where(
            Medication.id == medication_id,
            Medication.user_id == current_user.user_id,
        )
    )
    med = result.scalar_one_or_none()
    if not med:
        raise HTTPException(status_code=404, detail="Medication not found")

    await db.delete(med)
    await db.commit()

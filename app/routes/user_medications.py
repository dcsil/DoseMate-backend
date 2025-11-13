from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.database import get_db
from app.db.models import Medication
from app.core.auth import get_current_user
from pydantic import BaseModel
from typing import List, Optional
import uuid

router = APIRouter()

# ---- Pydantic Schemas ----
class MedicationCreate(BaseModel):
    brand_name: str
    generic_name: Optional[str] = None
    dosage: Optional[str] = None
    notes: Optional[str] = None
    image_metadata: Optional[dict] = None


class MedicationOut(BaseModel):
    id: uuid.UUID
    brand_name: str
    generic_name: Optional[str]
    dosage: Optional[str]
    notes: Optional[str]

    class Config:
        orm_mode = True


# ---- Routes ----
@router.post("/", response_model=MedicationOut)
async def create_user_medication(
    medication_data: MedicationCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    new_med = Medication(
        user_id=current_user.user_id,
        **medication_data.dict()
    )
    db.add(new_med)
    await db.commit()
    await db.refresh(new_med)
    return new_med


@router.get("/", response_model=List[MedicationOut])
async def get_user_medications(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(select(Medication).where(Medication.user_id == current_user.user_id))
    return result.scalars().all()


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

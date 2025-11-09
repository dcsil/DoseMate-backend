from fastapi import APIRouter
from typing import List
from app.db.models import Medicine

router = APIRouter()

@router.get("/all", response_model=List[Medicine])
def get_all_medicines():
    return [
        Medicine(
            brand_name="Metformin",
            generic_name="Metformin Hydrochloride",
            manufacturer="Pharma Inc.",
            indications="Used to treat type 2 diabetes.",
            dosage="500 mg twice daily.",
        ),
        Medicine(
            brand_name="Lisinopril",
            generic_name="Lisinopril",
            manufacturer="HealthCorp",
            indications="Used to treat high blood pressure.",
            dosage="10 mg once daily.",
        ),
        Medicine(
            brand_name="Atorvastatin",
            generic_name="Atorvastatin Calcium",
            manufacturer="MediLife",
            indications="Used to lower cholesterol.",
            dosage="20 mg once daily.",
        ),
    ]

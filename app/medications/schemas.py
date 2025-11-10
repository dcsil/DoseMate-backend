from pydantic import BaseModel
from typing import List

class UsageInfo(BaseModel):
    instructions: List[str]
    missedDose: str
    storage: str

class SideEffects(BaseModel):
    common: List[str]
    serious: List[str]
    whenToCall: str

class Interactions(BaseModel):
    drugs: List[str]
    food: List[str]
    conditions: List[str]

class MedicationDetails(BaseModel):
    genericName: str
    drugClass: str
    manufacturer: str
    description: str
    usage: UsageInfo
    sideEffects: SideEffects
    interactions: Interactions
    warnings: List[str]

class MedicationRequest(BaseModel):
    name: str
    strength: str

class BatchMedicationRequest(BaseModel):
    medications: List[MedicationRequest]
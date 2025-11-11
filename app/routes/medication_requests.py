from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db.models import Medicine
from app.medications.schemas import (
    MedicationDetails, 
    MedicationRequest, 
    BatchMedicationRequest
)
from app.medications.services import medication_service
from datetime import datetime, timedelta
import json

router = APIRouter(prefix="/medications", tags=["medications"])

# In-memory cache (consider using Redis in production)
medication_cache = {}
CACHE_DURATION = timedelta(days=30)

@router.get("/{medication_id}/details", response_model=MedicationDetails)
async def get_medication_details(
    medication_id: int,
    name: str = Query(..., description="Medication name"),
    strength: str = Query(..., description="Medication strength"),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed information about a specific medication"""
    
    cache_key = f"{name.lower()}-{strength.lower()}"
    
    # Check cache
    if cache_key in medication_cache:
        cached_data = medication_cache[cache_key]
        if datetime.now() - cached_data["timestamp"] < CACHE_DURATION:
            return cached_data["data"]
    
    try:
        # Fetch from OpenAI
        medication_data = await medication_service.fetch_medication_details(
            name, strength
        )
        
        # Cache the result
        medication_cache[cache_key] = {
            "data": medication_data,
            "timestamp": datetime.now()
        }
        
        # Optional: Save to database for permanent storage
        # await save_medication_details_to_db(db, medication_id, medication_data)
        
        return medication_data
        
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to fetch medication details: {str(e)}"
        )

@router.post("/batch", response_model=dict)
async def batch_fetch_medications(
    request: BatchMedicationRequest,
    db: AsyncSession = Depends(get_db)
):
    """Fetch details for multiple medications in batch"""
    
    results = []
    
    for med in request.medications:
        cache_key = f"{med.name.lower()}-{med.strength.lower()}"
        
        # Check cache
        if cache_key in medication_cache:
            cached_data = medication_cache[cache_key]
            if datetime.now() - cached_data["timestamp"] < CACHE_DURATION:
                results.append({**cached_data["data"], "cached": True})
                continue
        
        # Fetch from OpenAI
        try:
            medication_data = await medication_service.fetch_medication_details(
                med.name, med.strength
            )
            
            # Cache the result
            medication_cache[cache_key] = {
                "data": medication_data,
                "timestamp": datetime.now()
            }
            
            results.append({**medication_data, "cached": False})
            
        except Exception as e:
            results.append({"error": f"Failed to fetch {med.name}: {str(e)}"})
    
    return {"medications": results}

@router.delete("/cache")
async def clear_cache():
    """Clear the medication cache (admin only - add auth middleware)"""
    medication_cache.clear()
    return {"message": "Cache cleared successfully"}
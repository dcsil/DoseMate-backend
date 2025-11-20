from fastapi import APIRouter, File, UploadFile, HTTPException
from app.db.models import Medicine
from pydantic import BaseModel
from PIL import Image
import pytesseract
import requests
import io

router = APIRouter()
OPENFDA_URL = "https://api.fda.gov/drug/label.json"

# --- Helper ---
def query_openfda(search_text: str):
    params = {"search": f"openfda.brand_name:{search_text}*", "limit": 1}
    res = requests.get(OPENFDA_URL, params=params)
    if res.status_code != 200:
        return None
    results = res.json().get("results", [])
    if not results:
        return None
    entry = results[0]
    openfda = entry.get("openfda", {})
    return Medicine(
        brand_name=openfda.get("brand_name", ["Unknown"])[0],
        generic_name=openfda.get("generic_name", ["Unknown"])[0],
        manufacturer=openfda.get("manufacturer_name", ["Unknown"])[0],
        indications=entry.get("indications_and_usage", [""])[0],
        dosage=entry.get("dosage_and_administration", [""])[0],
    )

# --- Endpoints ---
@router.get("/search", response_model=Medicine)
def search_medicine(query: str):
    medicine = query_openfda(query)
    if not medicine:
        raise HTTPException(status_code=404, detail="Medicine not found")
    return medicine


@router.get("/autocomplete")
def autocomplete_medicines(prefix: str, limit: int = 5):
    prefix = prefix.strip()
    if not prefix:
        return []
    query = f"openfda.brand_name:{prefix}*"
    res = requests.get(OPENFDA_URL, params={"search": query, "limit": limit * 2})
    if res.status_code != 200:
        return []
    names = {
        n.upper()
        for entry in res.json().get("results", [])
        for n in entry.get("openfda", {}).get("brand_name", [])
        if n.lower().startswith(prefix.lower())
    }
    return sorted(list(names))[:limit]

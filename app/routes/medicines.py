from fastapi import APIRouter, File, UploadFile, HTTPException
from app.db.models import Medicine
from pydantic import BaseModel
from PIL import Image
import pytesseract
import requests
import io
import re

router = APIRouter()
OPENFDA_URL = "https://api.fda.gov/drug/label.json"

# --- Helpers ---
def clean_text(text: str, max_length: int = 500) -> str:
    """
    Clean and truncate text to essential information
    Removes excessive formatting, URLs, and limits length
    """
    if not text:
        return ""
    
    # Remove excessive whitespace and newlines
    text = re.sub(r'\s+', ' ', text)
    
    # Remove common noise patterns
    text = re.sub(r'http[s]?://\S+', '', text)  # URLs
    text = re.sub(r'\d+\s+PATIENT INFORMATION', '', text)  # Section headers
    text = re.sub(r'\d+\s+CLINICAL PHARMACOLOGY', '', text)
    text = re.sub(r'\d+\s+NONCLINICAL TOXICOLOGY', '', text)
    text = re.sub(r'\d+\s+HOW SUPPLIED', '', text)
    
    # Extract first meaningful sentence or paragraph
    sentences = text.split('.')
    
    # Build result up to max_length
    result = []
    current_length = 0
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        # Skip overly technical/legal sections
        skip_patterns = [
            'clinical studies',
            'pharmacokinetics',
            'contraindications',
            'storage and handling',
            'patient counseling',
            'distributed by',
            'manufactured by'
        ]
        
        if any(pattern in sentence.lower() for pattern in skip_patterns):
            continue
        
        # Add sentence if it fits
        if current_length + len(sentence) <= max_length:
            result.append(sentence)
            current_length += len(sentence)
        else:
            break
    
    final_text = '. '.join(result)
    if final_text and not final_text.endswith('.'):
        final_text += '.'
    
    # If still too long, hard truncate
    if len(final_text) > max_length:
        final_text = final_text[:max_length].rsplit(' ', 1)[0] + '...'
    
    return final_text.strip()


def extract_key_indications(text: str) -> str:
    """
    Extract only the main use/purpose from indications text
    """
    if not text:
        return ""
    
    # Common patterns for main indication
    patterns = [
        r'is indicated for (.+?)(?:\.|for patients)',
        r'indicated for the treatment of (.+?)(?:\.|in patients)',
        r'used to treat (.+?)(?:\.|in)',
        r'indicated to (.+?)(?:\.|in)',
    ]
    
    text_lower = text.lower()
    for pattern in patterns:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            indication = match.group(1).strip()
            # Limit to first sentence or 200 chars
            indication = indication.split('.')[0]
            if len(indication) > 200:
                indication = indication[:200].rsplit(' ', 1)[0] + '...'
            return indication
    
    # Fallback: just take first 200 chars
    return clean_text(text, max_length=200)


def extract_key_dosage(text: str) -> str:
    """
    Extract only the essential dosage information
    """
    if not text:
        return ""
    
    # Look for common dosage patterns
    patterns = [
        r'recommended dose[^.]+\.?',
        r'usual adult dose[^.]+\.?',
        r'initial dose[^.]+\.?',
        r'starting dose[^.]+\.?',
    ]
    
    text_lower = text.lower()
    for pattern in patterns:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            dosage = match.group(0).strip()
            if len(dosage) > 300:
                dosage = dosage[:300].rsplit(' ', 1)[0] + '...'
            return dosage
    
    # Fallback: take first meaningful part
    return clean_text(text, max_length=300)


def query_openfda(search_text: str):
    """
    Query OpenFDA API and return cleaned, concise medicine information
    """
    params = {"search": f"openfda.brand_name:{search_text}*", "limit": 1}
    res = requests.get(OPENFDA_URL, params=params)
    if res.status_code != 200:
        return None
    results = res.json().get("results", [])
    if not results:
        return None
    entry = results[0]
    openfda = entry.get("openfda", {})
    
    # Extract and clean the fields
    raw_indications = entry.get("indications_and_usage", [""])[0]
    raw_dosage = entry.get("dosage_and_administration", [""])[0]
    
    return Medicine(
        brand_name=openfda.get("brand_name", ["Unknown"])[0],
        generic_name=openfda.get("generic_name", ["Unknown"])[0],
        manufacturer=openfda.get("manufacturer_name", ["Unknown"])[0],
        indications=extract_key_indications(raw_indications),
        dosage=extract_key_dosage(raw_dosage),
    )

# --- Endpoints ---
@router.get("/search", response_model=Medicine)
def search_medicine(query: str):
    """
    Search for medicine by brand name
    Returns cleaned, concise information (not huge text blocks)
    """
    medicine = query_openfda(query)
    if not medicine:
        raise HTTPException(status_code=404, detail="Medicine not found")
    return medicine


@router.get("/autocomplete")
def autocomplete_medicines(prefix: str, limit: int = 5):
    """
    Get autocomplete suggestions for medicine names
    """
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
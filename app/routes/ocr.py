from fastapi import APIRouter, UploadFile, File, HTTPException
import httpx
from rapidfuzz import fuzz
from app.utils.ocr import extract_text_from_image

router = APIRouter()

OPENFDA_URL = "https://api.fda.gov/drug/label.json"


async def search_openfda(keyword: str):
    """
    Searches OpenFDA for a medicine using both brand_name and generic_name.
    Returns list of matched names.
    """
    params = {
        "search": f'openfda.brand_name:{keyword} OR openfda.generic_name:{keyword}',
        "limit": 20,
    }

    async with httpx.AsyncClient(timeout=20) as client:
        try:
            res = await client.get(OPENFDA_URL, params=params)
            res.raise_for_status()
            data = res.json()
        except Exception:
            return []

    matches = set()

    for item in data.get("results", []):
        brand = item.get("openfda", {}).get("brand_name", [])
        generic = item.get("openfda", {}).get("generic_name", [])

        for n in brand + generic:
            matches.add(n.lower())

    return list(matches)


def fuzzy_match(w1: str, w2: str, threshold=70) -> bool:
    """Return True if two strings are similar enough."""
    score = fuzz.partial_ratio(w1.lower(), w2.lower())
    return score >= threshold


@router.post("/extract")
async def extract_medicine_from_image(file: UploadFile = File(...)):
    """
    Extracts text from image and detects possible medicine names using OpenFDA + fuzzy matching.
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    contents = await file.read()
    extracted_text = extract_text_from_image(contents).lower()

    if not extracted_text.strip():
        return {"extracted_text": "", "detected_medicines": []}

    words = set(extracted_text.replace("\n", " ").split(" "))

    # Filter out useless tokens
    keywords = [w for w in words if 3 <= len(w) <= 30]

    detected = set()

    for word in keywords:
        # 1. Query OpenFDA for the word
        fda_matches = await search_openfda(word)
        if not fda_matches:
            continue

        # 2. If FDA returns anything, apply fuzzy matching
        for match in fda_matches:
            if fuzzy_match(word, match):
                detected.add(match)

    return {
        "extracted_text": extracted_text,
        "detected_medicines": list(detected),
    }

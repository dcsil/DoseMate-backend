from fastapi import APIRouter, UploadFile, File, HTTPException
from app.utils.ocr import extract_text_from_image

router = APIRouter(prefix="/ocr", tags=["OCR"])

@router.post("/extract")
async def extract_medicine_from_image(file: UploadFile = File(...)):
    """
    Extracts text from an uploaded medicine image and detects possible medicine names.
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    contents = await file.read()
    extracted_text = extract_text_from_image(contents)

    # Simple keyword-based detection (demo)
    medicine_keywords = ["metformin", "lisinopril", "atorvastatin", "aspirin", "advil"]
    detected_medicines = [
        keyword for keyword in medicine_keywords if keyword in extracted_text.lower()
    ]

    return {
        "extracted_text": extracted_text,
        "detected_medicines": detected_medicines,
    }

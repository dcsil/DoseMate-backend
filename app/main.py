# app/main.py
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, File, UploadFile, HTTPException

from app.db.database import engine, Base
from app.core.config import settings

from app.auth.routes_google import router as google_auth_router
from typing import List
from app.db.models import Medicine
import requests
from pydantic import BaseModel
from PIL import Image
import pytesseract
import io

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

app = FastAPI(
    title="DoseMate API",
    version="1.0.0",
    description="Backend service for the DoseMate mobile app",
)

# ---- CORS Setup ----
# In dev, allow local React Native / Expo host. In prod, lock this down.
origins = [
    "http://localhost",
    "http://localhost:3000",
    "exp://127.0.0.1:19000",
    "exp://localhost:19000",
    "dosemate://",  # deep link scheme
]

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Include Routers ----
app.include_router(google_auth_router, prefix="/auth/google", tags=["auth-google"])

# ---- Health Check ----
@app.get("/", tags=["system"])
async def health_check():
    return {"status": "ok", "service": "DoseMate API"}

# ---- Startup / Shutdown Events ----
@app.on_event("startup")
async def on_startup():
    # Create tables if they don't exist yet (for early dev)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database connected and models ready.")

@app.on_event("shutdown")
async def on_shutdown():
    print("🛑 Shutting down DoseMate API...")

OPENFDA_URL = "https://api.fda.gov/drug/label.json"

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
        #side_effect = entry.get("adverse_reactions", entry.get("warnings", ["No side effects listed"]))[0]

    )

@app.get("/medicines/search", response_model=Medicine)
def search_medicines(query: str):
    medicine = query_openfda(query)
    print(medicine)
    if not medicine:
        return {"error": "Medicine not found"}
    return medicine

class ImageData(BaseModel):
    image: str 


@app.post("/medicines/ocr")
async def extract_medicine_from_image(file: UploadFile = File(...)):
    try:
       
        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")

     
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))

       
        image = image.convert("L")
        extracted_text = pytesseract.image_to_string(image)

        # Clean up extracted text by replacing newlines and extra spaces
        extracted_text = ' '.join(extracted_text.split())
        print(f"Extracted Text: {extracted_text}")

        # will change this to an API call later
        medicine_keywords = ["metformin", "lisinopril", "atorvastatin", "aspirin", "Advil"]
        detected_medicines = []

        for k in medicine_keywords:
            if k in extracted_text:
                detected_medicines.append(k)

        return {
            "extracted_text": extracted_text,
            "detected_medicines": detected_medicines
        }

    except Exception as e:
        print(f"Error processing image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")

@app.get("/medicines/autocomplete")
def autocomplete_medicines(prefix: str, limit: int = 5):
    prefix = prefix.strip()
    if not prefix:
        return []

    query_variants = [
        f"openfda.brand_name:{prefix}*",
    ]

    names = set()
    for query in query_variants:
        res = requests.get(OPENFDA_URL, params={"search": query, "limit": limit * 2})
        if res.status_code != 200:
            continue

        for entry in res.json().get("results", []):
            openfda = entry.get("openfda", {})
            for name in openfda.get("brand_name", []):
                if name.lower().startswith(prefix.lower()):
                    names.add(name.upper()) 
           

    
    return sorted(list(names))[:limit]

@app.get("/all_medicines", response_model=List[Medicine])
def get_all_medicines():
    # For demo purposes, return a static list of medicines, will replace to db call later
    sample_medicines = [
        Medicine(
            brand_name="Metformin",
            generic_name="Metformin Hydrochloride",
            manufacturer="Pharma Inc.",
            indications="Used to treat type 2 diabetes.",
            dosage="500 mg twice daily."
        ),
        Medicine(
            brand_name="Lisinopril",
            generic_name="Lisinopril",
            manufacturer="HealthCorp",
            indications="Used to treat high blood pressure.",
            dosage="10 mg once daily."
        ),
        Medicine(
            brand_name="Atorvastatin",
            generic_name="Atorvastatin Calcium",
            manufacturer="MediLife",
            indications="Used to lower cholesterol.",
            dosage="20 mg once daily."
        ),
    ]
    return sample_medicines



# ---- Run Locally ----
if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

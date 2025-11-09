import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import engine, Base
from app.routes import auth, medicines, medications, ocr

app = FastAPI(
    title="DoseMate API",
    version="1.0.0",
    description="Backend service for the DoseMate mobile app",
)

# ---- CORS Setup ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Startup / Shutdown ----
@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database initialized.")

@app.on_event("shutdown")
async def on_shutdown():
    print("🛑 Shutting down DoseMate API...")

# ---- Health Check ----
@app.get("/", tags=["system"])
async def health_check():
    return {"status": "ok", "service": "DoseMate API"}

# ---- Register Routes ----
app.include_router(auth.router, prefix="/auth/google", tags=["Google-auth"])
app.include_router(medicines.router, prefix="/medicines", tags=["OpenFDA-medicines"])
app.include_router(medications.router, prefix="/medications", tags=["Medications"])
app.include_router(ocr.router, prefix="/ocr", tags=["OCR"])

# ---- Run Locally ----
if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

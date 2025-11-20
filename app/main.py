# app/main.py
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import engine, Base
from app.core.config import settings

from app.auth.routes_google import router as google_auth_router
from app.users.routes_progress import router as progress_router

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Include Routers ----
app.include_router(google_auth_router, prefix="/auth/google", tags=["auth-google"])
app.include_router(progress_router, tags=["progress"])  # endpoints: /users/{user_id}/progress

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

# ---- Run Locally ----
if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

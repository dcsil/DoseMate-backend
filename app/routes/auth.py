from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
import httpx
import time
from jose import jwt

from app.db.database import get_db
from app.users import crud
from app.core.config import settings
from app.db.models import User

router = APIRouter()

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
)

def hash_password(password: str) -> str:
  return pwd_context.hash(password)


def create_jwt_for_user(user: User) -> str:
  payload = {
      "sub": str(user.id),
      "email": user.email,
      "exp": int(time.time()) + 3600,  # 1 hour
  }
  token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
  return token


# -------- GOOGLE OAUTH FLOWS --------

# Step 1: Redirect user to Google OAuth consent screen
@router.get("/google")
async def login_google():
    print("google_client_id =", settings.google_client_id)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth"
    redirect_url = httpx.URL(url, params=params)
    # print("GOOGLE AUTH URL:", redirect_url)  
    return RedirectResponse(str(redirect_url))

# Step 2: Handle Google callback
@router.get("/google/callback")
async def google_callback(request: Request, db: AsyncSession = Depends(get_db)):
    code = request.query_params.get("code")
    if not code:
        return JSONResponse(
            {"error": "No code provided"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Exchange authorization code for access token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        token_data = token_resp.json()

        if "access_token" not in token_data:
            return JSONResponse(
                {"error": "Failed to get access token", "details": token_data},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        access_token = token_data["access_token"]

        # Fetch user info from Google
        user_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_info = user_resp.json()

    # Check or create user
    user = await crud.get_user_by_google_sub(db, user_info["sub"])
    if not user:
        user = await crud.create_user(
            db,
            email=user_info.get("email"),
            google_sub=user_info.get("sub"),
            name=user_info.get("name"),
            picture=user_info.get("picture"),
        )
        # Ensure user is committed to DB
        await db.commit()
        await db.refresh(user)

    # Create JWT token
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "exp": int(time.time()) + 3600,  # expires in 1 hour
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    # Redirect back to mobile app with the token in query param
    deep_link_url = f"{settings.app_deep_link}?token={token}"
    print(f"Redirecting to deep link: {deep_link_url}")
    return RedirectResponse(url=deep_link_url)


# -------- EMAIL SIGNUP --------

class EmailRegisterRequest(BaseModel):
  email: EmailStr
  name: Optional[str] = None
  password: str


class EmailAuthResponse(BaseModel):
  access_token: str
  token_type: str = "bearer"


@router.post("/email/register", response_model=EmailAuthResponse)
async def register_email_user(
  payload: EmailRegisterRequest,
  db: AsyncSession = Depends(get_db),
):
  # Check if email already exists
  result = await db.execute(select(User).where(User.email == payload.email))
  existing_user = result.scalar_one_or_none()

  if existing_user:
      raise HTTPException(
          status_code=status.HTTP_400_BAD_REQUEST,
          detail="A user with this email already exists.",
      )

  # Hash password
  password_hash = hash_password(payload.password)

  # Create user with auth_provider="email"
  user = User(
      email=payload.email,
      name=payload.name,
      auth_provider="email",
      password_hash=password_hash,
      is_active=True,
  )

  db.add(user)
  await db.commit()
  await db.refresh(user)

  # Create JWT
  token = create_jwt_for_user(user)

  return EmailAuthResponse(access_token=token)
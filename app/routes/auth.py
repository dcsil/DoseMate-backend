from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.users import crud
import httpx
from app.core.config import settings
from jose import jwt
import time

router = APIRouter()

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

# Step 1: Redirect user to Google OAuth consent screen
@router.get("/")
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
@router.get("/callback")
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

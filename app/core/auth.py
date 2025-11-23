from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from jose import jwt, JWTError
from app.core.config import settings
from pydantic import BaseModel

class TokenData(BaseModel):
    user_id: str
    email: str

def get_current_user(token: str = Depends(settings.oauth2_scheme)) -> TokenData:
    """
    Extract user info from JWT in Authorization header.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id: str = payload.get("sub")
        email: str = payload.get("email")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
        return TokenData(user_id=user_id, email=email)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    

ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day, tweak as you like


def create_access_token(
    *,
    user_id: str,
    email: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT that matches what get_current_user expects.

    Payload:
      - sub: user_id
      - email: user email
      - exp: expiry
    """
    to_encode = {
      "sub": user_id,
      "email": email,
    }
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return encoded_jwt

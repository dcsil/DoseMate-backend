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

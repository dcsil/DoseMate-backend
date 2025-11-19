from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.db.database import get_db
from app.db.models import User

# This tells FastAPI how to extract the token from the Authorization header.
# tokenUrl is just for docs; it doesn't need to match a real POST route in your case.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/google")


class TokenData(BaseModel):
    sub: Optional[str] = None
    email: Optional[str] = None


def decode_access_token(token: str) -> TokenData:
    """
    Decode the JWT created in routes/auth.py and return TokenData.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,          
            algorithms=[settings.jwt_algorithm],
        )
        sub = payload.get("sub")
        email = payload.get("email")

        if sub is None:
            raise JWTError("Missing 'sub' claim in token")

        return TokenData(sub=str(sub), email=email)

    except JWTError as e:
        # Includes expired tokens (exp) and bad signatures
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency that:
    - reads Bearer token from the Authorization header
    - decodes JWT
    - loads User from DB using the 'sub' claim (user.id)
    """
    token_data = decode_access_token(token)

    # In your auth.py, "sub" is str(user.id) (UUID as string)
    result = await db.execute(select(User).where(User.id == token_data.sub))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
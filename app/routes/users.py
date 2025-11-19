from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.db.models import User
from app.db.schema import UserRead


router = APIRouter()


@router.get("/", response_model=List[UserRead])
async def list_users(
    db: AsyncSession = Depends(get_db),
) -> List[UserRead]:
    """
    List all users (dev/testing).
    """
    result = await db.execute(select(User))
    users = result.scalars().all()
    return users


@router.get("/{user_id}", response_model=UserRead)
async def get_user_by_id(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """
    Get a single user by UUID.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user
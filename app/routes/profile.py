from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db  # your async session dependency
from app.users import crud as user_crud
from app.db.models import User, UserProfile
from app.db.schema import UserProfileBase, UserProfileCreate, UserProfileRead
from app.core.security import get_current_user 

router = APIRouter()


@router.get("/", response_model=list[UserProfileRead])
async def list_profiles(
    db: AsyncSession = Depends(get_db),
):
    """
    Return all user profiles.
    """
    result = await db.execute(select(UserProfile))
    profiles = result.scalars().all()
    return profiles


@router.post("/", response_model=UserProfileRead)
async def create_or_update_profile(
    payload: UserProfileBase,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = UserProfileCreate(
        user_id=current_user.id,
        **payload.dict(),
    )
    profile = await user_crud.upsert_user_profile(db, data)
    return profile
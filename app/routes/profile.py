from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.users import crud as user_crud
from app.db.models import User, UserProfile
from app.db.schema import UserProfileBase, UserProfileCreate, UserProfileRead
from app.core.security import get_current_user

router = APIRouter()


@router.get("/", response_model=list[UserProfileRead])
async def list_profiles(
    db: AsyncSession = Depends(get_db),
):
    """Return all user profiles."""
    result = await db.execute(select(UserProfile))
    profiles = result.scalars().all()
    return profiles


@router.post("/", response_model=UserProfileRead)
async def create_or_update_profile(
    payload: UserProfileBase,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create or update the user's profile."""
    
    data = UserProfileCreate(
        user_id=current_user.id,
        **payload.model_dump(),
    )

    profile = await user_crud.upsert_user_profile(db, data)
    return profile


@router.get("/me/complete", response_model=UserProfileRead)
async def get_my_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the profile of the current user."""
    profile = await user_crud.get_profile_by_user_id(db, current_user.id)
    return profile
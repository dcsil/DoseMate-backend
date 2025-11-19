from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import User

from app.db.models import UserProfile
from app.db.schema import UserProfileCreate, UserProfileUpdate

async def get_user_by_google_sub(db: AsyncSession, sub: str) -> User | None:
    q = select(User).where(User.google_sub == sub)
    res = await db.execute(q)
    return res.scalars().first()

async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    q = select(User).where(User.email == email)
    res = await db.execute(q)
    return res.scalars().first()

async def create_user(
    db: AsyncSession,
    *,
    email: str,
    google_sub: str | None = None,
    name: str | None = None,
    picture: str | None = None,
    auth_provider: str = "google",
) -> User:
    user = User(
        email=email,
        google_sub=google_sub,
        name=name,
        picture=picture,
        auth_provider=auth_provider,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

async def get_profile_by_user_id(
    db: AsyncSession,
    user_id: int,
) -> Optional[UserProfile]:
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    return result.scalar_one_or_none()

async def upsert_user_profile(db: AsyncSession, data: UserProfileCreate) -> UserProfile:
    stmt = select(UserProfile).where(UserProfile.user_id == data.user_id)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        for field, value in data.dict(exclude={"user_id"}).items():
            setattr(existing, field, value)
        await db.commit()
        await db.refresh(existing)
        return existing

    profile = UserProfile(**data.dict())
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile
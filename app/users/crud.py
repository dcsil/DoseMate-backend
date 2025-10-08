from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import User

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

import asyncio
from app.db.database import AsyncSessionLocal, engine, Base
from app.users.crud import create_user

async def create_test_user():
    async with AsyncSessionLocal() as db:
        user = await create_user(
            db,
            email="test@example.com",
            name="Test User",
            google_sub="google-sub-123",
            picture=None
        )
        print("Created test user:", user)

if __name__ == "__main__":
    asyncio.run(create_test_user())

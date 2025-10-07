import asyncio
from app.db.database import AsyncSessionLocal
from app.users.crud import get_user_by_email

async def test_create_user():
    async with AsyncSessionLocal() as db:
        user = await get_user_by_email(db, "test@example.com")
        print(user)

asyncio.run(test_create_user())
import asyncio
from app.db.database import engine, Base

async def init_db():
    async with engine.begin() as conn:
        # creates tables for models registered on Base.metadata
        await conn.run_sync(Base.metadata.create_all)

if __name__ == "__main__":
    asyncio.run(init_db())

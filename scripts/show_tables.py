import asyncio
from sqlalchemy import text
from app.db.database import engine 

async def show_tables(): 
    async with engine.connect() as conn:
        result = await conn.execute(text( "SELECT table_name FROM information_schema.tables WHERE table_schema='public';" ))
        tables = result.fetchall()
        print("Tables:", tables)

asyncio.run(show_tables())
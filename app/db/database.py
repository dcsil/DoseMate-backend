import ssl
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.core.config import settings

DATABASE_URL = settings.database_url

# Fix scheme if needed
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

# SSL context
ssl_context = ssl.create_default_context(cafile=None)
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE  # or ssl.CERT_REQUIRED if you have certs

engine = create_async_engine(
    DATABASE_URL,
    future=True,
    echo=True,
    pool_size=5,
    max_overflow=10,
    connect_args={"ssl": ssl_context},
)

AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

from app.db.models import User

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

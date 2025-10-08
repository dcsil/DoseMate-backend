import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from app.db.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String(320), unique=True, nullable=False, index=True)
    google_sub = Column(String, unique=True, nullable=True, index=True)  # Google 'sub' field (sub = subject)
    name = Column(String(255), nullable=True)
    picture = Column(String(1024), nullable=True)
    auth_provider = Column(String(50), nullable=False, default="google")  # 'google' | 'email' | 'apple' ...
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} provider={self.auth_provider}>"

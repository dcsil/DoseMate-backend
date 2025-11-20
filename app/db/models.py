import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Float, Integer
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


class Progress(Base):
    """Tracks user progress metrics over time.

    Assumptions:
    - Generic metric storage so we can track different types (e.g., dosage_adherence_pct, streak_days).
    - "value" stored as Float; integer metrics can also fit.
    - Frontend can filter by metric_name; latest entries first.
    """
    __tablename__ = "progress"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    metric_name = Column(String(64), nullable=False, index=True)
    value = Column(Float, nullable=False)
    # Optional extra integer field if needed for counts
    int_value = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self) -> str:  # pragma: no cover (repr tested indirectly)
        return f"<Progress user={self.user_id} metric={self.metric_name} value={self.value}>"

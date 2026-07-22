import enum
import uuid

from sqlalchemy import Column, String, Boolean, DateTime, Enum, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.db.database import Base


class UserRole(str, enum.Enum):
    doctor = "doctor"
    patient = "patient"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    age = Column(Integer, nullable=True)
    gender = Column(String, nullable=True)
    address = Column(Text, nullable=True)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.patient)
    category = Column(String, nullable=True)  # doctor's specialization; null for patients
    is_email_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
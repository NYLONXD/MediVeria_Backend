# D:\Professional_life\personal_projects\mediVeriabackend\app\schemas\user.py
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, ConfigDict

from app.models.user import UserRole


class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    age: Optional[int] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    role: UserRole = UserRole.patient
    category: Optional[str] = None  # e.g. "Cardiologist" — only meaningful for doctors
    phone: Optional[str] = None
    license_number: Optional[str] = None
    date_of_birth: Optional[datetime] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: EmailStr
    age: Optional[int] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    role: UserRole
    category: Optional[str] = None
    phone: Optional[str] = None
    is_email_verified: bool
    is_active: bool
    created_at: datetime
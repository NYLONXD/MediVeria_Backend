import uuid

from pydantic import BaseModel, ConfigDict, EmailStr


class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: EmailStr
    phone: str | None = None
    age: int | None = None
    gender: str | None = None
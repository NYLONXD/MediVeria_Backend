# D:\Professional_life\personal_projects\mediVeriabackend\app\schemas\token.py
from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    role: str

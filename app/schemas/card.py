from pydantic import BaseModel


class CardLoginRequest(BaseModel):
    card_uid: str


class CardVerifyRequest(BaseModel):
    card_uid: str


class CardAssignRequest(BaseModel):
    card_uid: str
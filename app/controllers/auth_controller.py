from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.schemas.user import UserCreate, UserOut
from app.schemas.token import Token
from app.services import auth_service
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    return auth_service.register_user(db, user_in)


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # form_data.username is used as the email field (OAuth2 spec requires "username")
    from app.schemas.user import UserLogin

    credentials = UserLogin(email=form_data.username, password=form_data.password)
    token = auth_service.authenticate_user(db, credentials)
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.post("/forget-password", response_model=dict)
def forget_password(email: str, db: Session = Depends(get_db)):
    auth_service.send_password_reset_email(db, email)
    return {"message": "If an account with that email exists, a password reset link has been sent."}

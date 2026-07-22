from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.dependencies import get_db, get_current_user
from app.schemas.user import UserCreate, UserOut, UserLogin
from app.services import auth_service
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    return auth_service.register_user(db, user_in)


@router.post("/login")
def login(credentials: UserLogin, response: Response, db: Session = Depends(get_db)):
    token = auth_service.authenticate_user(db, credentials)

    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    return {"message": "Login successful"}


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key=settings.COOKIE_NAME, path="/")
    return {"message": "Logged out"}


@router.post("/forget-password")
def forget_password(email: str, db: Session = Depends(get_db)):
    auth_service.send_password_reset_email(db, email)
    return {"message": "If an account with that email exists, a password reset link has been sent."}
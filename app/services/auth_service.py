# D:\Professional_life\personal_projects\mediVeriabackend\app\services\auth_service.py
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password, create_access_token
from app.models.health_records import Doctor, Patient
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserLogin
from app.core.redis_client import mark_card_verified


def register_user(db: Session, user_in: UserCreate) -> User:
    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists",
        )

    user = User(
        full_name=user_in.full_name,
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        age=user_in.age,
        gender=user_in.gender,
        address=user_in.address,
        role=user_in.role,
        category=user_in.category,
        phone=user_in.phone,
    )
    db.add(user)
    db.flush()

    if user.role == UserRole.doctor:
        db.add(
            Doctor(
                id=user.id,
                license_number=user_in.license_number or f"PENDING-{user.id}",
                specialization=user_in.category,
            )
        )
    elif user.role == UserRole.patient:
        db.add(Patient(id=user.id, date_of_birth=user_in.date_of_birth.date() if user_in.date_of_birth else None))

    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, credentials: UserLogin) -> str:
    user = db.query(User).filter(User.email == credentials.email).first()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated",
        )

    token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value}
    )
    return token

def send_password_reset_email(db: Session, email: str) -> None:
    # Placeholder for the future email provider integration. Keep response generic.
    db.query(User).filter(User.email == email).first()
    return None

def authenticate_by_card(db: Session, card_uid: str) -> str:
    doctor = db.query(Doctor).filter(Doctor.card_uid == card_uid).first()
    if not doctor:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Card not recognized")

    user = db.query(User).filter(User.id == doctor.id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account has been deactivated")

    return create_access_token(data={"sub": str(user.id), "role": user.role.value})


def verify_card_for_action(db: Session, current_user: User, card_uid: str) -> None:
    if current_user.role != UserRole.doctor:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only doctors can verify with a card")

    doctor = db.query(Doctor).filter(Doctor.id == current_user.id).first()
    if not doctor or not doctor.card_uid or doctor.card_uid != card_uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Card does not match this account")

    mark_card_verified(current_user.id)
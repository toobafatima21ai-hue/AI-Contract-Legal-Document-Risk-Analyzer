from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)
from app.models.models import User, AuditLog
from app.models.schemas import (
    UserCreate,
    UserLogin,
    UserOut,
    Token,
    UserUpdate,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=Token)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    print("PASSWORD VALUE:", payload.password)
    print("PASSWORD TYPE:", type(payload.password))
    print("PASSWORD LENGTH:", len(payload.password))

    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    # first registered user automatically becomes admin
    is_first_user = db.query(User).count() == 0

    user = User(
        full_name=payload.full_name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role="admin" if is_first_user else "user",
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    db.add(
        AuditLog(
            user_id=user.id,
            action="register",
            details=f"New user {user.email}"
        )
    )
    db.commit()

    token = create_access_token({"sub": str(user.id)})

    return Token(
        access_token=token,
        user=UserOut.model_validate(user)
    )


@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    if not user or not verify_password(
        payload.password,
        user.hashed_password
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Account disabled"
        )

    db.add(
        AuditLog(
            user_id=user.id,
            action="login",
            details=f"{user.email} logged in"
        )
    )
    db.commit()

    token = create_access_token({"sub": str(user.id)})

    return Token(
        access_token=token,
        user=UserOut.model_validate(user)
    )


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserOut)
def update_me(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.full_name:
        current_user.full_name = payload.full_name

    if payload.password:
        current_user.hashed_password = hash_password(
            payload.password
        )

    db.commit()
    db.refresh(current_user)

    return current_user
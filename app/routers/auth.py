from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    get_current_user,
    get_system_settings_model,
    serialize_user,
)
from app.database import get_db
from app.models import User
from app.schemas import TokenResponse, UserCreate, UserLogin, UserOut
from app.seed import hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new player during the Registration Phase.
    Automatically returns a signed JWT session token.
    """
    sys_settings = get_system_settings_model(db)
    if not sys_settings.registration_open:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is currently closed by the League Administrator.",
        )

    username_clean = payload.efootball_username.strip()
    existing = (
        db.query(User)
        .filter(User.efootball_username == username_clean)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this eFootball username already exists.",
        )

    new_user = User(
        name=payload.name.strip(),
        efootball_username=username_clean,
        hashed_password=hash_password(payload.password),
        is_admin=False,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_access_token({"sub": str(new_user.id)})
    return TokenResponse(
        access_token=token,
        user=serialize_user(db, new_user),
    )


@router.post("/login", response_model=TokenResponse)
def login_user(payload: UserLogin, db: Session = Depends(get_db)):
    """Authenticate an existing player or administrator and issue a JWT."""
    user = (
        db.query(User)
        .filter(User.efootball_username == payload.efootball_username.strip())
        .first()
    )
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid eFootball username or password.",
        )

    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=serialize_user(db, user),
    )


@router.get("/me", response_model=UserOut)
def get_me(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Return the authenticated user's profile and assigned team metadata."""
    return serialize_user(db, current_user)


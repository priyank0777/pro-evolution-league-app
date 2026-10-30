from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import SystemSetting, Team, User
from app.schemas import SystemSettingsOut, UserOut

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


def get_user_team(db: Session, user_id: int) -> Optional[Team]:
    """Find the 2v2 team that a user belongs to, if any."""
    return (
        db.query(Team)
        .filter(or_(Team.player1_id == user_id, Team.player2_id == user_id))
        .first()
    )


def serialize_user(db: Session, user: User) -> UserOut:
    """Serialize a User ORM instance including their assigned team metadata."""
    team = get_user_team(db, user.id)
    return UserOut(
        id=user.id,
        name=user.name,
        efootball_username=user.efootball_username,
        is_admin=user.is_admin,
        created_at=user.created_at,
        team_id=team.id if team else None,
        team_name=team.name if team else None,
    )


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    """FastAPI dependency to validate the JWT Bearer token and load the active User."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        sub: Optional[str] = payload.get("sub")
        if sub is None:
            raise credentials_exception
        user_id = int(sub)
    except (JWTError, ValueError):
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user


def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency restricting access to Admin users."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required.",
        )
    return current_user


def get_system_settings_dict(db: Session) -> Dict[str, str]:
    """Return raw key-value dictionary of system settings."""
    rows = db.query(SystemSetting).all()
    return {row.key: row.value for row in rows}


def get_system_settings_model(db: Session) -> SystemSettingsOut:
    """Parse system_settings rows into a strongly-typed SystemSettingsOut schema."""
    raw = get_system_settings_dict(db)

    def as_bool(key: str, default: bool = False) -> bool:
        val = raw.get(key)
        if val is None:
            return default
        return val.lower() in ("true", "1", "yes")

    def as_int(key: str, default: int = 1) -> int:
        val = raw.get(key)
        try:
            return int(val) if val is not None else default
        except ValueError:
            return default

    return SystemSettingsOut(
        registration_open=as_bool("registration_open", True),
        preferences_open=as_bool("preferences_open", False),
        team_setup_open=as_bool("team_setup_open", False),
        season_live=as_bool("season_live", False),
        round_robin_multiplier=as_int("round_robin_multiplier", 2),
        current_matchweek=as_int("current_matchweek", 1),
        track_points=as_bool("track_points", True),
        track_goals=as_bool("track_goals", True),
        track_assists=as_bool("track_assists", True),
    )


def update_system_setting(db: Session, key: str, value: str) -> None:
    """Upsert a single system setting key-value pair."""
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row:
        row.value = str(value)
    else:
        db.add(SystemSetting(key=key, value=str(value)))


from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.models import SystemSetting, User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DEFAULT_SYSTEM_SETTINGS = {
    "registration_open": "true",
    "preferences_open": "false",
    "team_setup_open": "false",
    "season_live": "false",
    "round_robin_multiplier": "2",
    "current_matchweek": "1",
    "track_points": "true",
    "track_goals": "true",
    "track_assists": "true",
}


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def seed_initial_data(db: Session) -> None:
    """
    Ensure default system settings and the primary Admin account from .env exist.
    Idempotent across restarts.
    """
    # 1. Seed default SystemSettings
    for key, default_val in DEFAULT_SYSTEM_SETTINGS.items():
        existing = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if not existing:
            db.add(SystemSetting(key=key, value=default_val))

    # 2. Seed Admin account from .env credentials
    admin_user = (
        db.query(User)
        .filter(User.efootball_username == settings.ADMIN_EFOOTBALL_USERNAME)
        .first()
    )
    if not admin_user:
        admin_user = User(
            name=settings.ADMIN_NAME,
            efootball_username=settings.ADMIN_EFOOTBALL_USERNAME,
            hashed_password=hash_password(settings.ADMIN_PASSWORD),
            is_admin=True,
        )
        db.add(admin_user)
    else:
        # Ensure existing configured admin retains admin privileges
        if not admin_user.is_admin:
            admin_user.is_admin = True

    db.commit()


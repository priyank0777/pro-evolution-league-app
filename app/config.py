import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application configuration loaded from environment variables."""

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./efootball_league.db")
    JWT_SECRET_KEY: str = os.getenv(
        "JWT_SECRET_KEY", "super-secret-efootball-2v2-jwt-key-change-in-production"
    )
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")
    )

    ADMIN_NAME: str = os.getenv("ADMIN_NAME", "League Commissioner")
    ADMIN_EFOOTBALL_USERNAME: str = os.getenv(
        "ADMIN_EFOOTBALL_USERNAME", "admin_efootball"
    )
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "AdminPassword123!")


settings = Settings()


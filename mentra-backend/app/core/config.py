import os
from datetime import timedelta
from pathlib import Path

# Load variables from `.env` (project root, alongside requirements.txt) into
# the real process environment before `Settings` reads anything. This is the
# standard `python-dotenv` pattern: it only fills in variables that aren't
# already set, so a real deployment's platform-level environment variables
# (Docker, systemd, Render/Railway, etc.) always take precedence over the
# file — `.env` is purely a local-dev convenience, never a production source
# of truth, and nothing here overrides an explicitly-set env var.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
except ImportError:  # pragma: no cover - dotenv is in requirements.txt
    pass


class Settings:
    """Central app configuration, read from environment variables.
    See .env.example for the full list of supported variables.
    """
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./mentra.db")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret-change-me")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_MINUTES: int = int(os.getenv("JWT_EXPIRES_MINUTES", "60"))
    ACCESS_TOKEN_EXPIRES = timedelta(minutes=JWT_EXPIRES_MINUTES)
    AI_API_KEY: str = os.getenv("AI_API_KEY", "")
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "stub")  # "stub", "claude", or "gemini"
    # No blanket default here on purpose: Claude and Gemini have different
    # model-id formats, so each provider applies its own sensible default
    # (see claude_provider.py / gemini_provider.py) when this is left unset.
    AI_MODEL: str = os.getenv("AI_MODEL", "")
    CORS_ORIGINS: list = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000,https://mentra-frontend-jqn1.onrender.com"
).split(",")

settings = Settings()

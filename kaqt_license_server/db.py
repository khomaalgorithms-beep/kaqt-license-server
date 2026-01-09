import os
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def get_database_uri() -> str:
    """
    Render provides DATABASE_URL for Postgres.
    For local dev, we fall back to sqlite.
    Also fixes 'postgres://' -> 'postgresql://' for SQLAlchemy.
    """
    url = os.getenv("DATABASE_URL", "").strip()

    if not url:
        # Local dev fallback
        return "sqlite:///kaqt_license.db"

    # SQLAlchemy expects postgresql:// not postgres://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    return url
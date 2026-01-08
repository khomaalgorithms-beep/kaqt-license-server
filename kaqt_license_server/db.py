import os
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def get_database_uri() -> str:
    # Render provides DATABASE_URL automatically when you attach Postgres.
    uri = os.environ.get("DATABASE_URL", "")
    if uri.startswith("postgres://"):
        # SQLAlchemy wants postgresql://
        uri = uri.replace("postgres://", "postgresql://", 1)
    return uri
from __future__ import annotations

import datetime as dt
from kaqt_license_server.db import db


class License(db.Model):
    __tablename__ = "licenses"

    id = db.Column(db.Integer, primary_key=True)

    license_key = db.Column(db.String(128), unique=True, nullable=False, index=True)

    # binds the license to a single device
    device_id = db.Column(db.String(128), nullable=True, index=True)

    is_active = db.Column(db.Boolean, nullable=False, default=True)

    # optional expiration
    expires_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=dt.datetime.utcnow)

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return dt.datetime.utcnow() > self.expires_at

    def to_dict(self):
        return {
            "license_key": self.license_key,
            "device_id": self.device_id,
            "is_active": bool(self.is_active),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
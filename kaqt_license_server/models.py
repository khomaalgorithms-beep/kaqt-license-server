from datetime import datetime
from .db import db

class LicenseKey(db.Model):
    __tablename__ = "license_keys"

    license_key = db.Column(db.String(128), primary_key=True)
    status = db.Column(db.String(32), nullable=False, default="active")  # active | disabled
    max_devices = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Activation(db.Model):
    __tablename__ = "activations"

    id = db.Column(db.Integer, primary_key=True)
    license_key = db.Column(db.String(128), db.ForeignKey("license_keys.license_key"), nullable=False)
    device_id = db.Column(db.String(128), nullable=False)
    activated_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("license_key", "device_id", name="uq_license_device"),
    )
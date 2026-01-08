import os
from datetime import datetime
from flask import Flask, request, jsonify

from .db import db, get_database_uri
from .models import LicenseKey, Activation
from .auth import sign_payload, verify_token

def create_app() -> Flask:
    app = Flask(__name__)

    app.config["SQLALCHEMY_DATABASE_URI"] = get_database_uri()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    @app.get("/health")
    def health():
        return jsonify({"ok": True, "service": "kaqt-license", "time": datetime.utcnow().isoformat()})

    @app.post("/activate")
    def activate():
        data = request.get_json(force=True, silent=True) or {}
        license_key = (data.get("license_key") or "").strip()
        device_id = (data.get("device_id") or "").strip()
        app_version = (data.get("app_version") or "").strip()

        if not license_key or not device_id:
            return jsonify({"ok": False, "message": "license_key and device_id required"}), 400

        lk = LicenseKey.query.filter_by(license_key=license_key).first()
        if not lk:
            return jsonify({"ok": False, "message": "Invalid license key"}), 401

        if lk.status != "active":
            return jsonify({"ok": False, "message": "License disabled"}), 403

        # how many devices already activated
        current = Activation.query.filter_by(license_key=license_key).count()

        # already activated on this device -> OK
        existing = Activation.query.filter_by(license_key=license_key, device_id=device_id).first()
        if existing is None:
            if current >= lk.max_devices:
                return jsonify({
                    "ok": False,
                    "message": f"Device limit reached ({lk.max_devices}). Contact support."
                }), 403

            db.session.add(Activation(license_key=license_key, device_id=device_id))
            db.session.commit()

        payload = {
            "license_key": license_key,
            "device_id": device_id,
            "status": "active",
            "issued_at": datetime.utcnow().isoformat(),
            "app_version": app_version,
        }
        token = sign_payload(payload)

        return jsonify({"ok": True, "token": token, "message": "Activated"})

    @app.post("/validate")
    def validate():
        data = request.get_json(force=True, silent=True) or {}
        token = (data.get("token") or "").strip()
        device_id = (data.get("device_id") or "").strip()

        if not token or not device_id:
            return jsonify({"ok": False, "message": "token and device_id required"}), 400

        try:
            payload = verify_token(token)
        except Exception as e:
            return jsonify({"ok": False, "message": f"Invalid token: {e}"}), 401

        if payload.get("device_id") != device_id:
            return jsonify({"ok": False, "message": "Device mismatch"}), 401

        license_key = payload.get("license_key")
        lk = LicenseKey.query.filter_by(license_key=license_key).first()
        if not lk or lk.status != "active":
            return jsonify({"ok": False, "message": "License disabled"}), 403

        return jsonify({"ok": True, "status": "active"})

    @app.post("/admin/import_keys")
    def admin_import_keys():
        # Simple admin endpoint protected by ADMIN_TOKEN
        admin_token = os.environ.get("ADMIN_TOKEN", "")
        header = request.headers.get("X-Admin-Token", "")
        if not admin_token or header != admin_token:
            return jsonify({"ok": False, "message": "Unauthorized"}), 401

        data = request.get_json(force=True, silent=True) or {}
        keys = data.get("keys") or []
        added = 0

        for item in keys:
            k = (item.get("license_key") or "").strip()
            if not k:
                continue
            max_devices = int(item.get("max_devices") or 1)
            status = (item.get("status") or "active").strip()

            if LicenseKey.query.filter_by(license_key=k).first():
                continue

            db.session.add(LicenseKey(license_key=k, max_devices=max_devices, status=status))
            added += 1

        db.session.commit()
        return jsonify({"ok": True, "added": added})

    return app

app = create_app()

# local dev helper
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
from __future__ import annotations

import os
from flask import Flask, jsonify, request

from kaqt_license_server.db import db, get_database_uri
from kaqt_license_server.models import License


def create_app() -> Flask:
    app = Flask(__name__)

    # DB config
    app.config["SQLALCHEMY_DATABASE_URI"] = get_database_uri()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()

    @app.get("/healthz")
    def healthz():
        return jsonify({"ok": True, "service": "kaqt-license-server"})

    @app.post("/validate")
    def validate():
        data = request.get_json(silent=True) or {}

        license_key = str(data.get("license_key", "")).strip()
        device_id = str(data.get("device_id", "")).strip()

        if not license_key:
            return jsonify({"ok": False, "message": "license_key missing"}), 400
        if not device_id:
            return jsonify({"ok": False, "message": "device_id missing"}), 400

        lic = License.query.filter_by(license_key=license_key).first()
        if not lic:
            return jsonify({"ok": False, "message": "License key not found"}), 404

        if not lic.is_active:
            return jsonify({"ok": False, "message": "License is inactive"}), 403

        if lic.is_expired():
            return jsonify({"ok": False, "message": "License expired"}), 403

        # bind device on first successful validation
        if not lic.device_id:
            lic.device_id = device_id
            db.session.commit()

        # enforce same device forever
        if lic.device_id != device_id:
            return jsonify({
                "ok": False,
                "message": "Device mismatch. License already bound to another device.",
                "bound_device_id": lic.device_id,
            }), 403

        return jsonify({"ok": True, "message": "License valid", "data": lic.to_dict()})

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=True)
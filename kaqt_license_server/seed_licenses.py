import sys
from kaqt_license_server.server import create_app
from kaqt_license_server.db import db
from kaqt_license_server.models import License


def add_key(key: str):
    key = key.strip()
    if not key:
        return

    existing = License.query.filter_by(license_key=key).first()
    if existing:
        print(f"[SKIP] exists: {key}")
        return

    lic = License(license_key=key, is_active=True)
    db.session.add(lic)
    db.session.commit()
    print(f"[OK] added: {key}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m kaqt_license_server.seed_licenses KEY1 KEY2 ...")
        sys.exit(1)

    app = create_app()
    with app.app_context():
        for key in sys.argv[1:]:
            add_key(key)


if __name__ == "__main__":
    main()
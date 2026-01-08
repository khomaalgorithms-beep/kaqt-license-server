# kaqt_app/app.py
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict

# Ensure project root is on sys.path so "kaqt_core" imports work
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import webview
except Exception as e:
    raise RuntimeError(
        "pywebview is not installed in the CURRENT venv.\n\n"
        "Run:\n"
        "  ./.venv/bin/python -m pip install pywebview\n\n"
        f"Original error: {e}"
    )

from license_manager import LicenseManager  # noqa: E402
from kaqt_core.runtime import KAQTRuntime   # noqa: E402


APP_TITLE = "Khoma Algorithms Quantitative Trading"


class KaqtAPI:
    """
    Exposed to JS via pywebview.
    All methods return JSON-serializable dicts.
    """

    def __init__(self) -> None:
        self.lic = LicenseManager(app_name="KAQT")
        self.runtime = KAQTRuntime()

    # ---------- License ----------
    def get_device_id(self) -> Dict[str, Any]:
        return {"ok": True, "device_id": self.lic.get_device_id()}

    def validate_license(self, license_key: str) -> Dict[str, Any]:
        res = self.lic.validate_license(license_key)
        return {
            "ok": res.ok,
            "message": res.message,
            "device_id": res.device_id,     # always present
            "activated": res.activated,
        }

    def activate_license(self, license_key: str) -> Dict[str, Any]:
        res = self.lic.activate_license(license_key)
        return {
            "ok": res.ok,
            "message": res.message,
            "device_id": res.device_id,     # always present
            "activated": res.activated,
        }

    def is_activated(self) -> Dict[str, Any]:
        return {
            "ok": True,
            "activated": self.lic.is_activated(),
            "device_id": self.lic.get_device_id(),
        }

    # ---------- Runtime passthrough ----------
    def get_status(self) -> Dict[str, Any]:
        return self.runtime.get_status()

    def get_logs(self):
        return self.runtime.get_logs()

    def get_positions(self):
        return self.runtime.get_positions()

    def get_trades(self):
        return self.runtime.get_trades()

    def save_broker_config(self, payload: Dict[str, Any]):
        return self.runtime.save_broker_config(payload)

    def get_broker_config(self):
        return self.runtime.get_broker_config()

    def test_broker_connection(self):
        return self.runtime.test_broker_connection()

    def start_engine(self):
        return self.runtime.start_engine()

    def stop_engine(self):
        return self.runtime.stop_engine()


def _file_url(path: Path) -> str:
    return path.resolve().as_uri()


def main() -> None:
    app_dir = Path(__file__).resolve().parent

    license_html = app_dir / "license.html"
    dashboard_html = app_dir / "index.html"

    api = KaqtAPI()

    # Decide which page to open
    if api.lic.is_activated():
        start_url = _file_url(dashboard_html)
    else:
        start_url = _file_url(license_html)

    window = webview.create_window(
        APP_TITLE,
        start_url,
        js_api=api,
        width=1200,
        height=760,
        min_size=(1100, 700),
    )
    webview.start(debug=False)


if __name__ == "__main__":
    main()
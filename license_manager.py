# license_manager.py
from __future__ import annotations

import hashlib
import json
import os
import platform
import socket
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import requests



@dataclass
class LicenseResult:
    ok: bool
    message: str
    license_key: str
    device_id: str
    activated: bool = False
    raw: Optional[Dict[str, Any]] = None


class LicenseManager:
    """
    Production-grade license manager:
    - Always generates device_id locally first
    - Uses certifi CA bundle for macOS SSL reliability
    - Always returns device_id even if activation fails
    - Stores activation locally on success
    """

    def __init__(
        self,
        api_base: Optional[str] = None,
        app_name: str = "KAQT",
        storage_dir: Optional[Path] = None,
    ) -> None:
        self.api_base = (api_base or os.getenv("KAQT_LICENSE_API", "")).strip() or "https://license.khomaalgorithms.com"
        self.app_name = app_name

        # Store activation state in a predictable, user-safe location
        if storage_dir is None:
            storage_dir = Path.home() / f".{app_name.lower()}"
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.state_path = self.storage_dir / "license_state.json"

        # Local stable device id
        self._device_id = self._make_device_id()

    # ---------------------------
    # Device ID (stable)
    # ---------------------------
    def get_device_id(self) -> str:
        return self._device_id

    def _make_device_id(self) -> str:
        """
        Stable(ish) device id:
        - macOS: uses platform + hostname + MAC-ish node id
        - Hashed so we don't leak raw identifiers
        """
        try:
            node = uuid.getnode()  # typically MAC, sometimes random but stable-ish
        except Exception:
            node = 0

        parts = [
            platform.system(),
            platform.release(),
            platform.machine(),
            socket.gethostname(),
            str(node),
            self.app_name,
        ]
        raw = "|".join(parts).encode("utf-8", errors="ignore")
        return hashlib.sha256(raw).hexdigest()[:32].upper()

    # ---------------------------
    # Local activation state
    # ---------------------------
    def is_activated(self) -> bool:
        st = self._load_state()
        return bool(st.get("activated") is True and st.get("device_id") == self._device_id)

    def get_saved_license_key(self) -> str:
        st = self._load_state()
        return str(st.get("license_key", "") or "")

    def _load_state(self) -> Dict[str, Any]:
        if not self.state_path.exists():
            return {}
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}

    def _save_state(self, license_key: str, activated: bool, extra: Optional[Dict[str, Any]] = None) -> None:
        data = {
            "app": self.app_name,
            "license_key": license_key,
            "device_id": self._device_id,
            "activated": bool(activated),
        }
        if extra:
            data.update(extra)
        self.state_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # ---------------------------
    # HTTP helpers
    # ---------------------------
    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = self.api_base.rstrip("/") + "/" + path.lstrip("/")
        r = requests.post(
            url,
            json=payload,
            timeout=12,
            verify=True  # uses system certs
        )
        r.raise_for_status()
        return r.json() if r.content else {}

    # ---------------------------
    # Public API used by UI
    # ---------------------------
    def validate_license(self, license_key: str) -> LicenseResult:
        license_key = (license_key or "").strip()
        device_id = self._device_id

        if not license_key:
            return LicenseResult(
                ok=False,
                message="Please enter a license key.",
                license_key=license_key,
                device_id=device_id,
                activated=False,
            )

        payload = {"license_key": license_key, "device_id": device_id}
        try:
            data = self._post("/validate", payload)
            ok = bool(data.get("ok", True))
            activated = bool(data.get("activated", False))
            msg = str(data.get("message", "License check complete."))

            return LicenseResult(
                ok=ok,
                message=msg,
                license_key=license_key,
                device_id=device_id,
                activated=activated,
                raw=data,
            )

        except requests.exceptions.SSLError as e:
            # Always return device_id so user can copy it
            return LicenseResult(
                ok=False,
                message=f"SSL certificate error. Your Device ID is ready to copy. ({e})",
                license_key=license_key,
                device_id=device_id,
                activated=False,
            )
        except Exception as e:
            return LicenseResult(
                ok=False,
                message=f"License validation failed: {e}",
                license_key=license_key,
                device_id=device_id,
                activated=False,
            )

    def activate_license(self, license_key: str) -> LicenseResult:
        license_key = (license_key or "").strip()
        device_id = self._device_id

        if not license_key:
            return LicenseResult(
                ok=False,
                message="Please enter a license key.",
                license_key=license_key,
                device_id=device_id,
                activated=False,
            )

        payload = {"license_key": license_key, "device_id": device_id}
        try:
            data = self._post("/activate", payload)
            ok = bool(data.get("ok", True))
            activated = bool(data.get("activated", ok))
            msg = str(data.get("message", "Activation complete."))

            if ok and activated:
                self._save_state(license_key=license_key, activated=True, extra={"server": data})
                return LicenseResult(
                    ok=True,
                    message=msg,
                    license_key=license_key,
                    device_id=device_id,
                    activated=True,
                    raw=data,
                )

            # Not activated (valid key but not enabled for this device, etc.)
            return LicenseResult(
                ok=False,
                message=msg,
                license_key=license_key,
                device_id=device_id,
                activated=False,
                raw=data,
            )

        except requests.exceptions.SSLError as e:
            return LicenseResult(
                ok=False,
                message=f"SSL certificate error. Your Device ID is ready to copy. ({e})",
                license_key=license_key,
                device_id=device_id,
                activated=False,
            )
        except Exception as e:
            return LicenseResult(
                ok=False,
                message=f"Activation failed: {e}",
                license_key=license_key,
                device_id=device_id,
                activated=False,
            )
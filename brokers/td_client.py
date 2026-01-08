from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import time
import requests

from brokers.base import BrokerClient, AccountInfo


class TradovateCredentialsError(Exception):
    pass


class TradovateHTTPError(Exception):
    pass


@dataclass
class TradovateConfig:
    username: str = ""
    password: str = ""
    cid: str = ""
    sec: str = ""          # <-- IMPORTANT: use "sec" not "secret"
    device_id: str = "kaqt-desktop"
    mode: str = "paper_api"  # paper_api or live


class TradovateClient(BrokerClient):
    """
    Minimal Tradovate API adapter:
      - connect(): auth, store access token
      - get_account_info(): get balances
      - get_positions(): placeholder (safe)
      - get_trades(): placeholder (safe)
      - market_order(): placeholder (safe)  (we'll implement later)
    """

    def __init__(self, cfg: TradovateConfig):
        super().__init__(name="tradovate")
        self.cfg = cfg
        self.access_token: Optional[str] = None
        self.token_expires_at: float = 0.0
        self.account_id: Optional[int] = None

        # Base URL guesses (works for most setups)
        # If your Tradovate provides a different base, change these two.
        if cfg.mode == "live":
            self.base_url = "https://live.tradovateapi.com/v1"
        else:
            self.base_url = "https://demo.tradovateapi.com/v1"

        self.session = requests.Session()

    # ----------------------------
    # Low-level HTTP helpers
    # ----------------------------
    def _headers(self) -> Dict[str, str]:
        h = {"Accept": "application/json"}
        if self.access_token:
            h["Authorization"] = f"Bearer {self.access_token}"
        return h

    def _request(self, method: str, path: str, json_body: Optional[dict] = None) -> Any:
        url = self.base_url.rstrip("/") + "/" + path.lstrip("/")
        resp = self.session.request(
            method=method.upper(),
            url=url,
            headers=self._headers(),
            json=json_body,
            timeout=25,
        )
        txt = resp.text or ""
        if resp.status_code >= 400:
            raise TradovateHTTPError(f"Tradovate HTTP {resp.status_code}: {txt[:500]}")
        if not txt.strip():
            return {}
        try:
            return resp.json()
        except Exception:
            return {"raw": txt}

    # ----------------------------
    # Auth / connect
    # ----------------------------
    def _validate_cfg(self) -> None:
        missing = []
        if not self.cfg.username.strip():
            missing.append("username")
        if not self.cfg.password.strip():
            missing.append("password")
        if not self.cfg.cid.strip():
            missing.append("cid")
        if not self.cfg.sec.strip():
            missing.append("sec")
        if missing:
            raise TradovateCredentialsError("Missing Tradovate credentials: " + ", ".join(missing))

    def connect(self) -> None:
        self._validate_cfg()

        # reuse token if still valid
        if self.access_token and time.time() < self.token_expires_at - 15:
            self.connected = True
            if self.account_id is None:
                self.account_id = self._pick_account_id()
            return

        payload = {
            "name": self.cfg.username,
            "password": self.cfg.password,
            "appId": "KAQT",
            "appVersion": "1.0",
            "cid": self.cfg.cid,
            "sec": self.cfg.sec,
            "deviceId": self.cfg.device_id,
        }

        # Some environments require /auth/accesstoken, others /auth/accessToken
        auth_paths = ["auth/accesstoken", "auth/accessToken", "auth/token"]
        last_err = None

        for p in auth_paths:
            try:
                data = self._request("POST", p, json_body=payload)
                # Handle CAPTCHA requirement
                if isinstance(data, dict) and data.get("p-captcha") is True:
                    raise TradovateCredentialsError(
                        "Tradovate requires CAPTCHA for API auth on this session/device. "
                        "Try: log into Tradovate in browser, disable VPN, wait 10-30 min, "
                        "use a stable deviceId, then try again. If it persists, contact Tradovate support."
                    )

                token = None
                if isinstance(data, dict):
                    token = data.get("accessToken") or data.get("token")

                if not token:
                    raise TradovateCredentialsError(f"Tradovate auth failed: {data}")

                self.access_token = str(token)

                # expiresIn may appear; fallback to 20 min
                expires_in = 1200
                if isinstance(data, dict) and data.get("expirationTime"):
                    # Some responses include epoch ms; ignore and use default if unknown
                    pass
                if isinstance(data, dict) and data.get("expiresIn"):
                    try:
                        expires_in = int(data["expiresIn"])
                    except Exception:
                        pass

                self.token_expires_at = time.time() + float(expires_in)
                self.connected = True
                self.account_id = self._pick_account_id()
                return

            except Exception as e:
                last_err = e

        raise TradovateCredentialsError(f"Tradovate auth failed: {last_err}")

    def disconnect(self) -> None:
        self.connected = False
        self.access_token = None
        self.token_expires_at = 0.0
        self.account_id = None

    # ----------------------------
    # Account selection + balances
    # ----------------------------
    def _pick_account_id(self) -> int:
        # try a few common endpoints
        candidates = [
            "account/list",
            "account/items",
            "account",
        ]
        last = None
        for p in candidates:
            try:
                data = self._request("GET", p)
                if isinstance(data, list) and data:
                    # pick first account
                    acct = data[0]
                    if isinstance(acct, dict) and "id" in acct:
                        return int(acct["id"])
                if isinstance(data, dict) and "id" in data:
                    return int(data["id"])
            except Exception as e:
                last = e
                continue
        raise TradovateHTTPError(f"Could not load Tradovate account list: {last}")

    def _pick_num(self, d: dict, keys: List[str], default: float = 0.0) -> float:
        for k in keys:
            if k in d and d[k] is not None:
                try:
                    return float(d[k])
                except Exception:
                    pass
        return float(default)

    def _get_balance_snapshot(self, account_id: int) -> dict:
        # Tradovate endpoints vary by environment; try multiple until one works
        candidates = [
            f"cashBalance/{account_id}",
            f"cashBalance/getCashBalance/{account_id}",
            f"account/cashBalance/{account_id}",
            f"account/{account_id}/cashBalance",
            f"account/balance/{account_id}",
        ]
        last = None
        for p in candidates:
            try:
                data = self._request("GET", p)
                # normalize list -> dict
                if isinstance(data, list) and data:
                    if isinstance(data[0], dict):
                        return data[0]
                if isinstance(data, dict):
                    return data
            except Exception as e:
                last = e
                continue
        raise TradovateHTTPError(f"Tradovate GET cash/balance failed: {last}")

    def get_account_info(self) -> AccountInfo:
        if not self.connected:
            self.connect()

        if self.account_id is None:
            self.account_id = self._pick_account_id()

        snap = self._get_balance_snapshot(int(self.account_id))

        equity = self._pick_num(
            snap,
            ["netLiq", "equity", "accountBalance", "totalMoney", "totalCashValue", "cashBalance"],
            default=0.0,
        )
        buying_power = self._pick_num(
            snap,
            ["buyingPower", "availableFunds", "availableBalance", "availableCash", "cashAvailable", "cashBalance"],
            default=0.0,
        )
        cash = self._pick_num(snap, ["cashBalance", "cash", "totalCashValue"], default=0.0)

        return AccountInfo(
            equity=float(equity),
            cash=float(cash),
            buying_power=float(buying_power),
            currency="USD",
            raw={"balance_snapshot": snap},
        )

    # ----------------------------
    # Required abstract methods
    # ----------------------------
    def get_positions(self) -> List[Dict[str, Any]]:
        # We'll wire this later. For now return empty to keep UI stable.
        return []

    def get_trades(self) -> List[Dict[str, Any]]:
        # We'll wire this later. For now return empty to keep UI stable.
        return []

    def market_order(self, symbol: str, side: str, quantity: float) -> Dict[str, Any]:
        # We'll implement real order placement later once you confirm sandbox/live behavior.
        raise NotImplementedError("Tradovate market_order is not implemented yet.")

    def sync_target_weights(self, symbol: str, weights_series) -> None:
        # future: translate weights into orders
        raise NotImplementedError("Tradovate sync_target_weights is not implemented yet.")
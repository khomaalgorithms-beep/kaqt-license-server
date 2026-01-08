# brokers/td_client.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

from brokers.base import BrokerClient, AccountInfo


class TradovateCredentialsError(Exception):
    pass


@dataclass
class TradovateConfig:
    username: str
    password: str
    cid: str
    sec: str
    device_id: str
    mode: str = "paper_api"  # "paper_api" (demo) or "live"


class TradovateClient(BrokerClient):
    """
    Tradovate REST connector (Auth + Account + Balance).
    Trading/positions/trades can be wired later.

    Demo endpoints commonly used:
      demo: https://demo.tradovateapi.com/v1
      live: https://live.tradovateapi.com/v1

    Key endpoints:
      POST /auth/accesstokenrequest
      GET  /account/list
      GET  /cashBalance/getCashBalanceSnapshot?accountId=...
    """

    def __init__(self, cfg: TradovateConfig):
        super().__init__(name="tradovate")
        self.cfg = cfg
        self.base_url = (
            "https://demo.tradovateapi.com/v1"
            if cfg.mode in ("paper_api", "demo")
            else "https://live.tradovateapi.com/v1"
        )
        self.access_token: Optional[str] = None
        self.session = requests.Session()

        self.account_id: Optional[int] = None
        self.account_name: Optional[str] = None

    # ----------------- internal helpers -----------------
    def _require_creds(self) -> None:
        missing = []
        if not (self.cfg.username or "").strip():
            missing.append("username")
        if not (self.cfg.password or "").strip():
            missing.append("password")
        if not (self.cfg.cid or "").strip():
            missing.append("cid")
        if not (self.cfg.sec or "").strip():
            missing.append("sec")
        if not (self.cfg.device_id or "").strip():
            missing.append("device_id")

        if missing:
            raise TradovateCredentialsError("Missing Tradovate credentials: " + ", ".join(missing))

    def _headers(self) -> Dict[str, str]:
        h = {"Accept": "application/json"}
        if self.access_token:
            h["Authorization"] = f"Bearer {self.access_token}"
        return h

    def _http(self, method: str, path: str, *, params=None, json_body=None) -> Any:
        url = self.base_url + path
        r = self.session.request(
            method=method.upper(),
            url=url,
            params=params,
            json=json_body,
            headers=self._headers(),
            timeout=20,
        )
        if r.status_code >= 400:
            # try json, else raw
            try:
                j = r.json()
            except Exception:
                j = {"raw": r.text or ""}
            raise TradovateCredentialsError(f"Tradovate HTTP {r.status_code}: {j}")
        if not r.text:
            return {}
        try:
            return r.json()
        except Exception:
            return {"raw": r.text}

    # ----------------- BrokerClient API -----------------
    def connect(self) -> None:
        self._require_creds()

        payload = {
            "name": self.cfg.username,
            "password": self.cfg.password,
            "appId": "KAQT",
            "appVersion": "1.0",
            "cid": self.cfg.cid,
            "sec": self.cfg.sec,
            "deviceId": self.cfg.device_id,
        }

        resp = self._http("POST", "/auth/accesstokenrequest", json_body=payload)

        # CAPTCHA case
        if isinstance(resp, dict) and resp.get("p-captcha"):
            raise TradovateCredentialsError(
                "Tradovate requires CAPTCHA for API auth on this session/device. "
                "Try: log into Tradovate in browser, disable VPN, wait 10–30 min, "
                "use a stable deviceId, then try again. If it persists, contact Tradovate support."
            )

        token = None
        if isinstance(resp, dict):
            token = resp.get("accessToken") or resp.get("access_token")

        if not token:
            raise TradovateCredentialsError(f"Tradovate auth failed: no accessToken in response: {resp}")

        self.access_token = token
        self.connected = True

        # pick first account
        accounts = self._http("GET", "/account/list")
        if not isinstance(accounts, list) or len(accounts) == 0:
            raise TradovateCredentialsError(f"Tradovate account/list returned nothing: {accounts}")

        a0 = accounts[0]
        self.account_id = int(a0.get("id"))
        self.account_name = str(a0.get("name") or "")

    def disconnect(self) -> None:
        self.connected = False
        self.access_token = None
        self.account_id = None
        self.account_name = None

    def get_account_info(self) -> AccountInfo:
        if not self.connected or not self.access_token:
            raise TradovateCredentialsError("Not connected")

        if not self.account_id:
            # safety re-fetch
            accounts = self._http("GET", "/account/list")
            if isinstance(accounts, list) and accounts:
                self.account_id = int(accounts[0].get("id"))

        if not self.account_id:
            raise TradovateCredentialsError("Could not determine Tradovate account_id")

        bal = self._http(
            "GET",
            "/cashBalance/getCashBalanceSnapshot",
            params={"accountId": self.account_id},
        )

        # Tradovate fields vary; we map best-effort.
        # Keep raw for debugging.
        equity = float(
            (bal.get("totalEquity") if isinstance(bal, dict) else 0.0)
            or (bal.get("netLiquidation") if isinstance(bal, dict) else 0.0)
            or (bal.get("accountBalance") if isinstance(bal, dict) else 0.0)
            or 0.0
        )
        cash = float(
            (bal.get("cashBalance") if isinstance(bal, dict) else 0.0)
            or (bal.get("cash") if isinstance(bal, dict) else 0.0)
            or 0.0
        )
        buying_power = float(
            (bal.get("buyingPower") if isinstance(bal, dict) else 0.0)
            or (bal.get("availableBuyingPower") if isinstance(bal, dict) else 0.0)
            or 0.0
        )

        return AccountInfo(
            equity=equity,
            cash=cash,
            buying_power=buying_power,
            currency="USD",
            raw={"accountId": self.account_id, "balance": bal},
        )

    # --- required abstract methods (placeholders for now, but implemented) ---
    def get_positions(self) -> List[Dict[str, Any]]:
        # Later: /position/list?accountId=...
        return []

    def get_trades(self) -> List[Dict[str, Any]]:
        # Later: /fill/list?accountId=... (or equivalent)
        return []

    def market_order(self, symbol: str, side: str, quantity: float) -> Dict[str, Any]:
        # Later: /order/placeOrder
        raise NotImplementedError("Trading endpoints will be added after stable connection testing.")
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import threading
import time
import datetime as dt

from kaqt_core.strategy_live_runner import StrategyLiveRunner


@dataclass
class BrokerConfig:
    broker: str = "ibkr"           # IBKR only
    mode: str = "paper_api"        # paper_api | live
    account_id: str = ""           # optional DUxxxx / Uxxxx

    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = 7497
    ibkr_client_id: int = 7


class KAQTRuntime:
    """
    KAQT Desktop Runtime (IBKR ONLY).

    Features:
      - Engine ACTIVE badge
      - Signal state (LONG/FLAT)
      - Last decision time
      - Next run time
      - Daily scheduler
      - Equity history persisted to disk (real account curve)
      - Start Engine locked (can't start twice)
    """

    def __init__(self) -> None:
        core_dir = Path(__file__).resolve().parent
        self._broker_config_path_str: str = str(core_dir / "broker_config.json")
        self._equity_history_path_str: str = str(core_dir / "equity_history.json")

        self.broker_config: BrokerConfig = self._load_broker_config()

        # IBKR clients
        self._ibkr_real = None

        # Engine runner + scheduler
        self._runner: Optional[StrategyLiveRunner] = None
        self.engine_active: bool = False
        self._engine_lock = threading.Lock()
        self._scheduler_thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()

        # scheduler time (default)
        self.sched_hour: int = 16
        self.sched_minute: int = 5

        # UI state
        self.connection_status: str = "Disconnected"
        self.account_balance: float = 0.0  # equity
        self.cash: float = 0.0
        self.strategy_status: str = "Idle"

        self.signal_state: str = "FLAT"
        self.last_decision_iso: str = ""
        self.next_run_iso: str = ""

        # “current position” summary
        self.current_symbol: str = "QQQ"
        self.current_size: float = 0.0
        self.current_avg_price: float = 0.0

        # tables
        self._positions: List[Dict[str, Any]] = []
        self._trades: List[Dict[str, Any]] = []

        # equity curve history
        self._equity_history: List[Dict[str, Any]] = self._load_equity_history()

        # logs
        self.logs: List[str] = []
        self._log("[RUNTIME] KAQTRuntime initialized (IBKR only).")
        self._log(f"[RUNTIME] mode={self.broker_config.mode}, host={self.broker_config.ibkr_host}:{self.broker_config.ibkr_port}")

    # ---------------- logging ----------------
    def _log(self, msg: str) -> None:
        print(msg)
        self.logs.append(msg)

    # ---------------- disk helpers ----------------
    def _config_path(self) -> Path:
        return Path(self._broker_config_path_str)

    def _equity_history_path(self) -> Path:
        return Path(self._equity_history_path_str)

    def _load_broker_config(self) -> BrokerConfig:
        p = self._config_path()
        if not p.exists():
            return BrokerConfig()

        try:
            raw = json.loads(p.read_text(encoding="utf-8") or "{}")
        except Exception:
            return BrokerConfig()

        return BrokerConfig(
            broker="ibkr",
            mode=str(raw.get("mode", "paper_api") or "paper_api").lower(),
            account_id=str(raw.get("account_id", "") or ""),
            ibkr_host=str(raw.get("ibkr_host", "127.0.0.1") or "127.0.0.1"),
            ibkr_port=int(raw.get("ibkr_port", 7497) or 7497),
            ibkr_client_id=int(raw.get("ibkr_client_id", 7) or 7),
        )

    def _save_broker_config_to_disk(self) -> None:
        p = self._config_path()
        data = {
            "broker": "ibkr",
            "mode": self.broker_config.mode,
            "account_id": self.broker_config.account_id,
            "ibkr_host": self.broker_config.ibkr_host,
            "ibkr_port": self.broker_config.ibkr_port,
            "ibkr_client_id": self.broker_config.ibkr_client_id,
        }
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self._log("[RUNTIME] Broker configuration saved (IBKR).")

    def _load_equity_history(self) -> List[Dict[str, Any]]:
        p = self._equity_history_path()
        if not p.exists():
            return []
        try:
            data = json.loads(p.read_text(encoding="utf-8") or "[]")
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save_equity_history(self) -> None:
        p = self._equity_history_path()
        p.write_text(json.dumps(self._equity_history, indent=2), encoding="utf-8")

    # ---------------- public API ----------------
    def save_broker_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        mode = str(payload.get("mode", "paper_api") or "paper_api").lower()
        if mode not in {"paper_api", "live"}:
            return {"ok": False, "message": f"Unsupported mode: {mode}"}

        def _safe_int(v, fallback: int) -> int:
            try:
                if v is None:
                    return fallback
                if isinstance(v, str) and v.strip() == "":
                    return fallback
                return int(v)
            except Exception:
                return fallback

        self.broker_config = BrokerConfig(
            broker="ibkr",
            mode=mode,
            account_id=str(payload.get("account_id", "") or ""),
            ibkr_host=str(payload.get("ibkr_host", self.broker_config.ibkr_host) or self.broker_config.ibkr_host),
            ibkr_port=_safe_int(payload.get("ibkr_port"), self.broker_config.ibkr_port),
            ibkr_client_id=_safe_int(payload.get("ibkr_client_id"), self.broker_config.ibkr_client_id),
        )

        self._save_broker_config_to_disk()
        return {"ok": True, "message": "IBKR settings saved."}

    def get_broker_config(self) -> Dict[str, Any]:
        c = self.broker_config
        return {
            "broker": "ibkr",
            "mode": c.mode,
            "account_id": c.account_id,
            "ibkr_host": c.ibkr_host,
            "ibkr_port": c.ibkr_port,
            "ibkr_client_id": c.ibkr_client_id,
        }

    def set_scheduler_time(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            h = int(payload.get("hour", self.sched_hour))
            m = int(payload.get("minute", self.sched_minute))
            if not (0 <= h <= 23 and 0 <= m <= 59):
                return {"ok": False, "message": "Invalid time. Hour 0–23, Minute 0–59."}
            self.sched_hour = h
            self.sched_minute = m
            return {"ok": True, "message": f"Scheduler set to {h:02d}:{m:02d}."}
        except Exception as e:
            return {"ok": False, "message": f"Scheduler error: {e}"}

    def get_status(self) -> Dict[str, Any]:
        # live return + max dd based on saved equity history
        live_return = None
        live_max_dd = None
        equity_pct = None

        if len(self._equity_history) >= 2:
            eq0 = float(self._equity_history[0].get("equity", 0.0))
            eqn = float(self._equity_history[-1].get("equity", 0.0))
            if eq0 > 0:
                live_return = (eqn / eq0) - 1.0
                equity_pct = live_return

            # max drawdown from history
            peak = -1e18
            mdd = 0.0
            for row in self._equity_history:
                eq = float(row.get("equity", 0.0))
                if eq > peak:
                    peak = eq
                if peak > 0:
                    dd = (eq / peak) - 1.0
                    if dd < mdd:
                        mdd = dd
            live_max_dd = mdd

        return {
            "connection_status": self.connection_status,
            "account_balance": float(self.account_balance),  # equity
            "cash": float(self.cash),

            "engine_active": bool(self.engine_active),
            "signal_state": str(self.signal_state),

            "last_decision_iso": str(self.last_decision_iso),
            "last_decision_human": self._human_time(self.last_decision_iso),

            "next_run_iso": str(self.next_run_iso),
            "next_run_human": self._human_time(self.next_run_iso),

            "current_symbol": self.current_symbol,
            "current_size": float(self.current_size),
            "current_avg_price": float(self.current_avg_price),

            "live_return": live_return,
            "live_max_dd": live_max_dd,
            "equity_pct": equity_pct,
        }

    def get_logs(self) -> List[str]:
        return list(self.logs)

    def get_positions(self) -> List[Dict[str, Any]]:
        return list(self._positions)

    def get_trades(self) -> List[Dict[str, Any]]:
        return list(self._trades)

    def get_equity_curve(self) -> List[Dict[str, Any]]:
        # return list of {ts, equity}
        return list(self._equity_history)

    # ---------------- connection ----------------
    def test_broker_connection(self) -> Dict[str, Any]:
        try:
            from brokers.ibkr_client import IBKRConfig, IBKRRealClient

            cfg = IBKRConfig(
                host=self.broker_config.ibkr_host,
                port=int(self.broker_config.ibkr_port),
                client_id=int(self.broker_config.ibkr_client_id),
                account=self.broker_config.account_id or "",
                mode=self.broker_config.mode,
            )

            self._ibkr_real = IBKRRealClient(cfg)
            self._ibkr_real.connect()

            info = self._ibkr_real.get_account_info()
            self.connection_status = f"IBKR Connected ({self.broker_config.mode.upper()})"

            self._refresh_from_broker(info=info)

            # positions/trades
            self._positions = self._ibkr_real.get_positions()
            self._trades = self._ibkr_real.get_trades()

            self._sync_current_position_summary()

            self._log("[RUNTIME] IBKR connection OK.")
            return {"ok": True, "message": "IBKR connection OK."}

        except Exception as e:
            self._log(f"[RUNTIME] IBKR error: {e}")
            return {"ok": False, "message": f"IBKR error: {e}"}

    # ---------------- engine control ----------------
    def start_engine(self) -> Dict[str, Any]:
        with self._engine_lock:
            if self.engine_active:
                return {"ok": False, "message": "Engine already ACTIVE."}

            if self._ibkr_real is None:
                return {"ok": False, "message": "Connect IBKR first (Connections → Test Connection)."}

            self._runner = StrategyLiveRunner(symbol="QQQ")
            self.engine_active = True
            self._stop_flag.clear()
            self.strategy_status = "ACTIVE"

            # run immediately (shows signal and possibly trades)
            self._run_engine_once(label="(manual start)")

            # start scheduler
            self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
            self._scheduler_thread.start()

            self._log("[RUNTIME] Engine ACTIVE. Daily scheduler running.")
            return {"ok": True, "message": "Engine ACTIVE. It will execute once per day automatically."}

    def stop_engine(self) -> Dict[str, Any]:
        with self._engine_lock:
            if not self.engine_active:
                return {"ok": True, "message": "Engine already stopped."}
            self.engine_active = False
            self._stop_flag.set()
            self.strategy_status = "Idle"
            self._log("[RUNTIME] Engine STOP requested.")
            return {"ok": True, "message": "Engine stopped."}

    # ---------------- scheduler ----------------
    def _next_run_time(self) -> dt.datetime:
        now = dt.datetime.now()
        target = now.replace(hour=self.sched_hour, minute=self.sched_minute, second=0, microsecond=0)
        if target <= now:
            target = target + dt.timedelta(days=1)
        return target

    def _scheduler_loop(self) -> None:
        while self.engine_active and not self._stop_flag.is_set():
            nxt = self._next_run_time()
            self.next_run_iso = nxt.isoformat(timespec="seconds")
            self._log(f"[RUNTIME] Next scheduled decision: {self.next_run_iso}")

            wait_s = max(1.0, (nxt - dt.datetime.now()).total_seconds())
            end = time.time() + wait_s
            while time.time() < end:
                if self._stop_flag.is_set() or not self.engine_active:
                    return
                time.sleep(1.0)

            if self._stop_flag.is_set() or not self.engine_active:
                return

            self._run_engine_once(label="(scheduled)")

    def _run_engine_once(self, label: str = "") -> None:
        if self._runner is None or self._ibkr_real is None:
            return

        try:
            out = self._runner.run_once(self._ibkr_real)

            self.signal_state = out.get("signal_state", "UNKNOWN")
            self.last_decision_iso = dt.datetime.now().isoformat(timespec="seconds")

            # refresh from broker
            info = self._ibkr_real.get_account_info()
            self._refresh_from_broker(info=info)

            self._positions = self._ibkr_real.get_positions()
            self._trades = self._ibkr_real.get_trades()

            self._sync_current_position_summary()

            # write daily equity snapshot (real equity curve)
            self._append_daily_equity_snapshot()

            msg = out.get("message", "Decision complete.")
            self._log(f"[RUNTIME] Engine decision {label}: {msg}")

        except Exception as e:
            self.last_decision_iso = dt.datetime.now().isoformat(timespec="seconds")
            self._log(f"[RUNTIME] Engine run failed {label}: {e}")

    # ---------------- internal refresh helpers ----------------
    def _refresh_from_broker(self, info: Dict[str, Any]) -> None:
        self.account_balance = float(info.get("equity", 0.0) or 0.0)
        # cash is critical for your “cash-only mode” UI
        self.cash = float(info.get("cash", 0.0) or 0.0)

    def _sync_current_position_summary(self) -> None:
        # Find QQQ position if present
        sym = "QQQ"
        size = 0.0
        avg = 0.0

        for p in self._positions or []:
            if str(p.get("symbol", "")).upper() == sym:
                qty = float(p.get("quantity", p.get("size", 0.0)) or 0.0)
                size = qty
                avg = float(p.get("avg_price", p.get("avgCost", 0.0)) or 0.0)
                break

        self.current_symbol = sym
        self.current_size = size
        self.current_avg_price = avg

    def _append_daily_equity_snapshot(self) -> None:
        today = dt.date.today().isoformat()
        # only one record per day (replace if exists)
        row = {
            "ts": dt.datetime.now().isoformat(timespec="seconds"),
            "date": today,
            "equity": float(self.account_balance),
        }

        if self._equity_history and self._equity_history[-1].get("date") == today:
            self._equity_history[-1] = row
        else:
            self._equity_history.append(row)

        # keep last ~5 years daily to avoid huge file
        if len(self._equity_history) > 2000:
            self._equity_history = self._equity_history[-2000:]

        self._save_equity_history()

    def _human_time(self, iso_str: str) -> str:
        if not iso_str:
            return "—"
        try:
            t = dt.datetime.fromisoformat(iso_str)
            return t.strftime("%b %d, %H:%M")
        except Exception:
            return iso_str
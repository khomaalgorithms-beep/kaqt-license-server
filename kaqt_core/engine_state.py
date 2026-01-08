from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class EngineState:
    engine_active: bool = False
    in_position: bool = False

    symbol: str = "QQQ"

    last_target_weight: float = 0.0
    last_run_date: Optional[str] = None  # "YYYY-MM-DD" in America/New_York

    # risk/guards
    start_of_day_equity: float = 0.0
    kill_switch_triggered: bool = False
    kill_switch_reason: str = ""

    # scheduling info (UI)
    next_run_local: str = ""


def load_state(path: Path) -> EngineState:
    if not path.exists():
        return EngineState()

    try:
        raw = json.loads(path.read_text(encoding="utf-8") or "{}")
    except Exception:
        return EngineState()

    s = EngineState()
    for k, v in raw.items():
        if hasattr(s, k):
            setattr(s, k, v)
    return s


def save_state(path: Path, state: EngineState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")

    data: Dict[str, Any] = asdict(state)
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)
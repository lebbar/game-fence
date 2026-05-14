"""
Logique de planification et fermeture des processus (Windows).

Modes par jour :
  - « block_all_day »       : blocage tout le jour (toujours tuer si le process tourne)
  - « authorize_window »    : autorisation uniquement entre start et fin ; blocage hors de cette fenêtre [début, fin[
  - « legacy_block_window » : ancienne règle (blocage DANS la fenêtre uniquement) — vieux JSON sans kind
  - None / absent           : aucun blocage depuis cette règle ce jour-là
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, time
from pathlib import Path
from typing import Any, Optional

import clock_sync


# Répertoire de configuration : %LOCALAPPDATA%\GameFence


def _local_config_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / "GameFence"


CONFIG_DIR = _local_config_dir()
CONFIG_PATH = CONFIG_DIR / "config.json"

# Une entrée par jour (lun..dim).
DaySlot = Optional[dict[str, Any]]

KIND_BLOCK_ALL = "block_all_day"
KIND_AUTHORIZE_WINDOW = "authorize_window"
KIND_LEGACY_BLOCK_INSIDE = "legacy_block_window"
KIND_MARKER = "kind"


def default_rule_schedule() -> list[DaySlot]:
    """Valeurs proposées à la création d’une règle (lun..dim) :
    lun/mar/jeu = bloqué toute la journée ; mer/ven/sam/dim = accès seulement entre les heures indiquées."""
    return [
        {KIND_MARKER: KIND_BLOCK_ALL},
        {KIND_MARKER: KIND_BLOCK_ALL},
        {KIND_MARKER: KIND_AUTHORIZE_WINDOW, "start": "13:00", "end": "22:00"},
        {KIND_MARKER: KIND_BLOCK_ALL},
        {KIND_MARKER: KIND_AUTHORIZE_WINDOW, "start": "18:00", "end": "24:00"},
        {KIND_MARKER: KIND_AUTHORIZE_WINDOW, "start": "09:00", "end": "24:00"},
        {KIND_MARKER: KIND_AUTHORIZE_WINDOW, "start": "09:00", "end": "22:00"},
    ]


def normalize_schedule(raw: Any) -> list[DaySlot]:
    out: list[DaySlot] = []
    if isinstance(raw, list):
        for i in range(7):
            slot = raw[i] if i < len(raw) else None
            out.append(_normalize_one_slot(slot))
    else:
        out.extend([None] * 7)
    while len(out) < 7:
        out.append(None)
    return out[:7]


def _normalize_one_slot(slot: Any) -> DaySlot:
    if slot is None:
        return None
    if not isinstance(slot, dict):
        return None
    d = dict(slot)
    if KIND_MARKER not in d and "start" in d and "end" in d:
        # Ancien comportement conservé pour les configs sans kind
        d[KIND_MARKER] = KIND_LEGACY_BLOCK_INSIDE
        return d
    k = str(d.get(KIND_MARKER, ""))
    if k == KIND_BLOCK_ALL:
        return {KIND_MARKER: KIND_BLOCK_ALL}
    if k in (KIND_AUTHORIZE_WINDOW, KIND_LEGACY_BLOCK_INSIDE):
        if "start" in d and "end" in d:
            out = {
                KIND_MARKER: k,
                "start": str(d["start"]),
                "end": str(d["end"]),
            }
            return out
    return None


@dataclass
class BlockRule:
    id: str
    display_name: str
    exe_name: str
    enabled: bool
    schedule: list[DaySlot]  # 7 entrées (index 0 = lundi … 6 = dimanche)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_json(d: dict[str, Any]) -> "BlockRule":
        rid = d.get("id") or uuid.uuid4().hex[:12]
        if "schedule" in d and d["schedule"] is not None:
            sched = normalize_schedule(d["schedule"])
        else:
            sched = [None] * 7
            wd = list(d.get("weekdays") or [])
            st = str(d.get("start", "09:00"))
            en = str(d.get("end", "18:00"))
            for i in wd:
                if isinstance(i, int) and 0 <= i <= 6:
                    sched[i] = {KIND_MARKER: KIND_LEGACY_BLOCK_INSIDE, "start": st, "end": en}
            if not any(sched):
                sched = normalize_schedule([])
        return BlockRule(
            id=rid,
            display_name=d.get("display_name", ""),
            exe_name=d.get("exe_name", ""),
            enabled=bool(d.get("enabled", True)),
            schedule=sched,
        )


@dataclass
class AppConfig:
    rules: list[BlockRule]
    global_check_interval_seconds: int = 15
    ui_locale: str = "fr"
    # Fuseau façon UTC±N (-12 … +14), planning sans DST.
    time_zone_offset_hours: int = 1

    def to_json(self) -> dict[str, Any]:
        return {
            "rules": [r.to_json() for r in self.rules],
            "global_check_interval_seconds": self.global_check_interval_seconds,
            "ui_locale": self.ui_locale,
            "time_zone_offset_hours": self.time_zone_offset_hours,
        }

    @staticmethod
    def from_json(d: dict[str, Any]) -> "AppConfig":
        rules = [BlockRule.from_json(x) for x in d.get("rules", [])]
        raw_loc = str(d.get("ui_locale", "fr") or "fr").strip().lower()[:8]
        locale = raw_loc if raw_loc in ("fr", "en", "ar") else "fr"
        try:
            tz_h = int(d.get("time_zone_offset_hours", 1))
        except (TypeError, ValueError):
            tz_h = 1
        tz_h = max(-12, min(14, tz_h))
        return AppConfig(
            rules=rules,
            global_check_interval_seconds=int(d.get("global_check_interval_seconds", 15)),
            ui_locale=locale,
            time_zone_offset_hours=tz_h,
        )


def parse_clock(s: str) -> time:
    parts = str(s).strip().split(":")
    h = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    if h < 0 or h > 23 or m < 0 or m > 59:
        raise ValueError("HH:MM invalide")
    return time(h, m)


def end_is_end_of_calendar_day(end_s: str) -> bool:
    s = end_s.strip()
    return s in ("24:00", "24") or s.startswith("24:")


def _ranges_half_open_inside(t: time, start: time, end: time) -> bool:
    """True si t ∈ [start, end[ sur l’horloge 24 h (support d’une fenêtre chevauchant minuit)."""
    if start == end:
        return False
    if start < end:
        return start <= t < end
    return t >= start or t < end


def slot_should_kill_now(now: datetime, weekday: int, slot: dict[str, Any]) -> bool:
    """True si cette règle doit tenter de fermer le processus à l’instant présent."""
    if weekday != now.weekday():
        return False

    raw_kind = slot.get(KIND_MARKER)
    if raw_kind == KIND_BLOCK_ALL:
        return True

    if raw_kind == KIND_LEGACY_BLOCK_INSIDE:
        return _legacy_kill_inside(now, weekday, slot)

    if raw_kind != KIND_AUTHORIZE_WINDOW:
        return False

    t = now.time()
    start_s = str(slot.get("start", ""))
    end_s = str(slot.get("end", ""))
    if end_is_end_of_calendar_day(end_s):
        try:
            st = parse_clock(start_s)
        except (ValueError, IndexError):
            return True
        inside = st <= t <= time(23, 59, 59, 999999)
        return not inside
    try:
        st = parse_clock(start_s)
        et = parse_clock(end_s)
    except (ValueError, IndexError):
        return True
    inside = _ranges_half_open_inside(t, st, et)
    return not inside


def _legacy_kill_inside(now: datetime, weekday: int, slot: dict[str, Any]) -> bool:
    """Ancienne sémantique : tuer pendant la fenêtre [début, fin[."""
    if weekday != now.weekday():
        return False
    t = now.time()
    start_s = str(slot.get("start", ""))
    end_s = str(slot.get("end", ""))
    if end_is_end_of_calendar_day(end_s):
        try:
            st = parse_clock(start_s)
        except (ValueError, IndexError):
            return False
        return st <= t <= time(23, 59, 59, 999999)
    try:
        st = parse_clock(start_s)
        et = parse_clock(end_s)
    except (ValueError, IndexError):
        return False
    return _ranges_half_open_inside(t, st, et)


def reference_wall_clock_naive(cfg: AppConfig) -> datetime:
    """Heure « locale » naive pour appliquer le planning : heure NTP extrapolée + décal configuré UTC±N."""
    utc = clock_sync.effective_utc_now()
    return clock_sync.wall_clock_naive_for_offset_hours(utc, cfg.time_zone_offset_hours)


def is_rule_blocking_now(rule: BlockRule, cfg: AppConfig) -> bool:
    if not rule.enabled:
        return False
    now = reference_wall_clock_naive(cfg)
    idx = now.weekday()
    sched = normalize_schedule(rule.schedule)
    slot = sched[idx]
    if slot is None:
        return False
    try:
        return slot_should_kill_now(now, idx, slot)
    except Exception:
        return False


def default_config() -> AppConfig:
    return AppConfig(rules=[], global_check_interval_seconds=15, ui_locale="fr", time_zone_offset_hours=1)


def load_config() -> AppConfig:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.is_file():
        return default_config()
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return AppConfig.from_json(data)
    except (json.JSONDecodeError, OSError, TypeError, KeyError, ValueError):
        return default_config()


def save_config(cfg: AppConfig) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(cfg.to_json(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _subprocess_flags() -> int:
    if sys.platform == "win32":
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


def is_process_running(exe_name: str) -> bool:
    if not exe_name.strip():
        return False
    name = exe_name.strip()
    try:
        r = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {name}", "/NH"],
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=_subprocess_flags(),
        )
        out = (r.stdout or "").lower()
        return name.lower() in out
    except (subprocess.TimeoutExpired, OSError):
        return False


def kill_process_by_image_name(exe_name: str) -> bool:
    if not exe_name.strip():
        return False
    try:
        r = subprocess.run(
            ["taskkill", "/IM", exe_name.strip(), "/F"],
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=_subprocess_flags(),
        )
        return r.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def enforce_rules(cfg: AppConfig) -> list[tuple[str, str]]:
    killed: list[tuple[str, str]] = []
    seen_exe: set[str] = set()
    for rule in cfg.rules:
        if not is_rule_blocking_now(rule, cfg):
            continue
        exe = rule.exe_name.strip()
        if not exe or exe.lower() in seen_exe:
            continue
        if is_process_running(exe):
            if kill_process_by_image_name(exe):
                killed.append((exe, rule.display_name or exe))
        seen_exe.add(exe.lower())
    return killed

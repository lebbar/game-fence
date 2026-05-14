"""
Heure de référence : préfère NTP (UTC), extrapolée avec time.monotonic() pour limiter la sensibilité
aux changements d’horloge système ; retombe sur l’UTC système si NTP échoue.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

try:
    import ntplib
except ImportError:
    ntplib = None  # type: ignore[assignment]

# Durée sans nouvelle synchro avant une nouvelle tentative (évite le spam NTP).
_NTP_RESYNC_MONO = 300.0

_lock = threading.Lock()
_anchor_utc: Optional[datetime] = None  # UTC (aware), instant de l’ancre
_anchor_mono: float = 0.0
_periodic_gate_mono: float = 0.0
_last_success_was_ntp: bool = False

_NTP_SERVERS = ("pool.ntp.org", "time.google.com", "time.windows.com")


def utc_now_from_anchor_locked() -> datetime:
    """UTC actuel extrapolé à partir de l’ancre (doit être appelé sous _lock)."""
    global _anchor_utc, _anchor_mono
    if _anchor_utc is None:
        _anchor_utc = datetime.now(timezone.utc)
        _anchor_mono = time.monotonic()
    elapsed = timedelta(seconds=max(0.0, time.monotonic() - _anchor_mono))
    return (_anchor_utc + elapsed).astimezone(timezone.utc)


def _set_anchor_locked(utc_aware: datetime, from_ntp: bool) -> None:
    global _anchor_utc, _anchor_mono, _last_success_was_ntp
    _anchor_utc = utc_aware.astimezone(timezone.utc)
    _anchor_mono = time.monotonic()
    _last_success_was_ntp = from_ntp


def sync_ntp(timeout: float = 2.5) -> tuple[bool, Optional[str]]:
    """
    Réaligne l’ancre depuis un serveur NTP. Succès si une réponse valide arrive.
    En cas d’échec, ancre depuis datetime.now(timezone.utc) système (repli).
    """
    if ntplib is None:
        with _lock:
            now = datetime.now(timezone.utc)
            _set_anchor_locked(now, from_ntp=False)
        return False, "ntplib indisponible"

    err: Optional[str] = None
    client = ntplib.NTPClient()
    for host in _NTP_SERVERS:
        try:
            rsp = client.request(host, version=3, timeout=timeout)
            ntp_utc = datetime.fromtimestamp(rsp.tx_time, tz=timezone.utc)
            with _lock:
                _set_anchor_locked(ntp_utc, from_ntp=True)
            return True, None
        except Exception as e:  # noqa: BLE001
            err = str(e)
            continue

    with _lock:
        _set_anchor_locked(datetime.now(timezone.utc), from_ntp=False)
    return False, err


def maybe_resync_ntp(timeout: float = 2.5) -> None:
    """Appel léger depuis la boucle de surveillance pour rafraîchir le NTP environ toutes les 5 minutes."""
    global _periodic_gate_mono
    n = time.monotonic()
    if _periodic_gate_mono > 0.0 and n - _periodic_gate_mono < _NTP_RESYNC_MONO:
        return
    _periodic_gate_mono = n
    sync_ntp(timeout=timeout)


def effective_utc_now() -> datetime:
    """Moment UTC utilisé pour toutes les règles (NTP extrapolé ou repli système)."""
    with _lock:
        return utc_now_from_anchor_locked()


def wall_clock_naive_for_offset_hours(utc_dt: datetime, offset_hours: int) -> datetime:
    """Déc calendrier + heure « murale » fixe UTC+offset (sans gestion automatique DST)."""
    clamped = max(-12, min(14, int(offset_hours)))
    fixed = timezone(timedelta(hours=clamped))
    u = utc_dt if utc_dt.tzinfo else utc_dt.replace(tzinfo=timezone.utc)
    local = u.astimezone(fixed)
    return local.replace(tzinfo=None)


def clock_source_was_ntp() -> bool:
    with _lock:
        return _last_success_was_ntp


def timezone_choice_labels() -> list[str]:
    return [f"UTC{h:+d}" if h != 0 else "UTC+0" for h in range(-12, 15)]

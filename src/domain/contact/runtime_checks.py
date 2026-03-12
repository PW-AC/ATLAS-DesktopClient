"""
Zentrale Runtime-Guards fuer Call-Pop und Teams-Call-Launch.

Rein fachlich, komplett ohne Qt-/HTTP-/UI-Abhaengigkeiten.
Zustaendig fuer Validierung, Normalisierung, Deduplizierung und Cooldown.
"""

from __future__ import annotations

import logging
import threading
import time
import urllib.parse
from datetime import datetime, timezone

from domain.contact.runtime_models import (
    ALLOWED_SOURCES,
    DEDUP_WINDOW_S,
    STALE_THRESHOLD_S,
    TEAMS_COOLDOWN_S,
    CallValidationResult,
    CallValidationStatus,
    IncomingCallEvent,
    TeamsCallTarget,
    TeamsLaunchResult,
    TeamsLaunchStatus,
    normalize_phone,
)

logger = logging.getLogger(__name__)


class CallRuntimeGuard:
    """Validiert eingehende Call-Pop-Events zentral.

    Thread-safe: die Dedup-Map wird per Lock geschuetzt.
    """

    def __init__(
        self,
        stale_threshold_s: float = STALE_THRESHOLD_S,
        dedup_window_s: float = DEDUP_WINDOW_S,
    ):
        self._stale_threshold_s = stale_threshold_s
        self._dedup_window_s = dedup_window_s
        self._dedup_map: dict[str, float] = {}
        self._lock = threading.Lock()

    def validate(self, event: IncomingCallEvent) -> CallValidationResult:
        """Prueft ein kanonisches Call-Event gegen alle Regeln.

        Reihenfolge: source -> phone -> stale -> dedup.
        """
        if event.source not in ALLOWED_SOURCES:
            return CallValidationResult(
                status=CallValidationStatus.INVALID_SOURCE,
                reason=f"Unbekannte Source: {event.source}",
            )

        if not event.phone_raw:
            return CallValidationResult(
                status=CallValidationStatus.MISSING_PHONE,
                reason="Keine Telefonnummer im Event",
            )

        phone = normalize_phone(event.phone_raw)
        if not phone:
            return CallValidationResult(
                status=CallValidationStatus.INVALID_PHONE,
                reason=f"Telefonnummer nicht normalisierbar: {event.phone_raw!r}",
            )

        if self._is_stale(event):
            return CallValidationResult(
                status=CallValidationStatus.STALE,
                phone_normalized=phone,
                reason="Event zu alt",
            )

        dedupe_key = self._build_dedupe_key(event, phone)
        if self._is_duplicate(dedupe_key):
            return CallValidationResult(
                status=CallValidationStatus.DUPLICATE,
                phone_normalized=phone,
                dedupe_key=dedupe_key,
                reason="Duplikat innerhalb Dedup-Fenster",
            )

        return CallValidationResult(
            status=CallValidationStatus.OK,
            phone_normalized=phone,
            dedupe_key=dedupe_key,
        )

    def _is_stale(self, event: IncomingCallEvent) -> bool:
        ref_time = event.provider_event_ts_utc or event.received_at_utc
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        age_s = (now - ref_time).total_seconds()
        return age_s > self._stale_threshold_s

    def _build_dedupe_key(self, event: IncomingCallEvent, phone: str) -> str:
        if event.external_call_id:
            return f"{event.source}:{event.external_call_id}"
        bucket = int(event.received_at_utc.timestamp() // self._dedup_window_s)
        return f"{event.source}:{phone}:{bucket}"

    def _is_duplicate(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            last = self._dedup_map.get(key)
            if last is not None and (now - last) < self._dedup_window_s:
                return True
            self._dedup_map[key] = now
            self._gc(now)
            return False

    def _gc(self, now: float) -> None:
        cutoff = now - self._dedup_window_s * 2
        stale_keys = [k for k, v in self._dedup_map.items() if v < cutoff]
        for k in stale_keys:
            del self._dedup_map[k]


class TeamsCallGuard:
    """Validiert und baut Teams-Deeplinks zentral.

    Thread-safe: Cooldown-Map wird per Lock geschuetzt.
    """

    def __init__(self, cooldown_s: float = TEAMS_COOLDOWN_S):
        self._cooldown_s = cooldown_s
        self._last_launch: dict[str, float] = {}
        self._lock = threading.Lock()

    def validate_and_build(self, target: TeamsCallTarget) -> TeamsLaunchResult:
        """Prueft Ziel und baut den msteams:// Deeplink."""
        if not target.phone_normalized and not target.teams_user_id:
            return TeamsLaunchResult(
                status=TeamsLaunchStatus.MISSING_TARGET,
                error_message="Weder Telefonnummer noch Teams-User-ID vorhanden",
            )

        if target.phone_normalized:
            phone = normalize_phone(target.phone_normalized)
            if not phone:
                return TeamsLaunchResult(
                    status=TeamsLaunchStatus.INVALID_PHONE,
                    error_message=f"Telefonnummer ungueltig: {target.phone_normalized!r}",
                )
            cooldown_key = f"phone:{phone}"
            users_value = f"4:{phone}"
        else:
            cooldown_key = f"tid:{target.teams_user_id}"
            users_value = str(target.teams_user_id)

        if self._is_on_cooldown(cooldown_key):
            return TeamsLaunchResult(
                status=TeamsLaunchStatus.COOLDOWN_ACTIVE,
                error_message="Doppelklick-Sperre aktiv",
            )

        url = f"msteams://l/call/0/0?users={urllib.parse.quote(users_value, safe='')}"

        return TeamsLaunchResult(
            status=TeamsLaunchStatus.OK,
            url=url,
        )

    def _is_on_cooldown(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            last = self._last_launch.get(key)
            if last is not None and (now - last) < self._cooldown_s:
                return True
            self._last_launch[key] = now
            self._gc(now)
            return False

    def _gc(self, now: float) -> None:
        cutoff = now - self._cooldown_s * 10
        stale_keys = [k for k, v in self._last_launch.items() if v < cutoff]
        for k in stale_keys:
            del self._last_launch[k]

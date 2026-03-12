"""
Kanonische Datenmodelle fuer Call-Pop und Teams-Call Runtime-Checks.

Rein fachlich, komplett ohne Qt-/HTTP-/UI-Abhaengigkeiten.
Alle Guards und Services arbeiten ausschliesslich gegen diese Modelle.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Literal


CallSource = Literal["core", "workforce"]

ALLOWED_SOURCES: frozenset[str] = frozenset({"core", "workforce"})

PHONE_E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")

STALE_THRESHOLD_S = 60.0
DEDUP_WINDOW_S = 15.0
TEAMS_COOLDOWN_S = 2.0


class CallValidationStatus(str, Enum):
    OK = "ok"
    INVALID_SOURCE = "invalid_source"
    MISSING_PHONE = "missing_phone"
    INVALID_PHONE = "invalid_phone"
    STALE = "stale"
    DUPLICATE = "duplicate"
    LOOKUP_BLOCKED = "lookup_blocked"
    NO_MATCH = "no_match"
    MULTI_MATCH = "multi_match"
    BLOCKED = "blocked"


class TeamsLaunchStatus(str, Enum):
    OK = "ok"
    MISSING_TARGET = "missing_target"
    INVALID_PHONE = "invalid_phone"
    COOLDOWN_ACTIVE = "cooldown_active"
    LAUNCH_FAILED = "launch_failed"


@dataclass(frozen=True)
class IncomingCallEvent:
    """Kanonisches internes Event fuer eingehende Anrufe (V1 + V2)."""
    schema_version: int
    source: str
    phone_raw: str | None
    external_call_id: str | None
    provider_event_ts_utc: datetime | None
    received_at_utc: datetime
    payload_id: str | None = None


@dataclass(frozen=True)
class CallValidationResult:
    """Ergebnis der Call-Pop-Validierung."""
    status: CallValidationStatus
    phone_normalized: str | None = None
    dedupe_key: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class TeamsCallTarget:
    """Ziel fuer einen Teams-Anruf."""
    phone_normalized: str | None = None
    teams_user_id: str | None = None


@dataclass(frozen=True)
class TeamsLaunchResult:
    """Ergebnis eines Teams-Call-Launch-Versuchs."""
    status: TeamsLaunchStatus
    url: str | None = None
    error_code: str | None = None
    error_message: str | None = None


def normalize_phone(raw: str, default_country: str = "+49") -> str | None:
    """Normalisiert eine Telefonnummer nach E.164.

    Gibt None zurueck wenn die Eingabe nicht verwertbar ist.
    """
    if not raw:
        return None
    digits = "".join(c for c in str(raw) if c.isdigit() or c == "+")
    if not digits:
        return None

    if digits.startswith("+"):
        candidate = "+" + "".join(c for c in digits[1:] if c.isdigit())
    elif digits.startswith("00"):
        candidate = "+" + "".join(c for c in digits[2:] if c.isdigit())
    elif digits.startswith("0"):
        candidate = default_country + "".join(c for c in digits[1:] if c.isdigit())
    elif digits.startswith("49") and len(digits) >= 11:
        candidate = "+" + digits
    elif len(digits) >= 10:
        candidate = "+" + digits
    else:
        candidate = default_country + digits

    if PHONE_E164_RE.match(candidate):
        return candidate
    return None


def normalize_call_payload(
    payload: dict,
    default_source: str = "core",
    now_utc: datetime | None = None,
) -> IncomingCallEvent:
    """Konvertiert V1 (nur phone) oder V2 (strukturiert) in kanonisches Event."""
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    schema_version = int(payload.get("schema_version") or 1)

    if schema_version == 1:
        return IncomingCallEvent(
            schema_version=1,
            source=default_source,
            phone_raw=payload.get("phone"),
            external_call_id=None,
            provider_event_ts_utc=None,
            received_at_utc=now_utc,
            payload_id=None,
        )

    return IncomingCallEvent(
        schema_version=2,
        source=payload.get("source", default_source),
        phone_raw=payload.get("phone_raw"),
        external_call_id=payload.get("external_call_id"),
        provider_event_ts_utc=_parse_dt(payload.get("provider_event_ts_utc")),
        received_at_utc=_parse_dt(payload.get("received_at_utc")) or now_utc,
        payload_id=payload.get("payload_id"),
    )


def _parse_dt(value) -> datetime | None:
    """Versucht einen ISO-Datetime-String zu parsen."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        s = str(value).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None

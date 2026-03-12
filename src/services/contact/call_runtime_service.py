"""
Service-Fassade fuer Call-Pop- und Teams-Call-Runtime-Checks.

Orchestriert Guards, Logging und Audit.
UI-Dateien delegieren hierhin statt selbst zu pruefen.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from domain.contact.runtime_checks import CallRuntimeGuard, TeamsCallGuard
from domain.contact.runtime_models import (
    CallValidationResult,
    CallValidationStatus,
    IncomingCallEvent,
    TeamsCallTarget,
    TeamsLaunchResult,
    TeamsLaunchStatus,
    normalize_call_payload,
)

logger = logging.getLogger(__name__)


class CallRuntimeService:
    """Zentrale Fassade fuer Call-Pop-Validierung und Teams-Launch.

    Singleton-artig pro AppRouter-Lebenszyklus verwenden.
    """

    def __init__(self):
        self._call_guard = CallRuntimeGuard()
        self._teams_guard = TeamsCallGuard()

    # ------------------------------------------------------------------
    # Call-Pop
    # ------------------------------------------------------------------

    def validate_call_pop(
        self,
        phone: str,
        source: str = "core",
    ) -> CallValidationResult:
        """V1-kompatibler Einstieg: nimmt eine Telefonnummer entgegen.

        Baut intern ein kanonisches Event und validiert es.
        """
        event = normalize_call_payload(
            {"phone": phone},
            default_source=source,
            now_utc=datetime.now(timezone.utc),
        )
        return self.validate_call_event(event)

    def validate_call_event(self, event: IncomingCallEvent) -> CallValidationResult:
        """Validiert ein kanonisches Call-Event (V1 oder V2)."""
        result = self._call_guard.validate(event)
        self._log_call_result(event, result)
        return result

    def _log_call_result(
        self, event: IncomingCallEvent, result: CallValidationResult
    ) -> None:
        if result.status == CallValidationStatus.OK:
            logger.info(
                "[CALL-POP] OK source=%s phone=%s dedupe=%s",
                event.source,
                result.phone_normalized,
                result.dedupe_key,
            )
        else:
            logger.warning(
                "[CALL-POP] ABGELEHNT status=%s source=%s phone_raw=%s reason=%s",
                result.status.value,
                event.source,
                event.phone_raw,
                result.reason,
            )

    # ------------------------------------------------------------------
    # Teams-Call
    # ------------------------------------------------------------------

    def launch_teams_call(
        self,
        phone: str | None = None,
        teams_user_id: str | None = None,
    ) -> TeamsLaunchResult:
        """Validiert und baut einen Teams-Deeplink."""
        target = TeamsCallTarget(
            phone_normalized=phone,
            teams_user_id=teams_user_id,
        )
        result = self._teams_guard.validate_and_build(target)
        self._log_teams_result(target, result)
        return result

    def _log_teams_result(
        self, target: TeamsCallTarget, result: TeamsLaunchResult
    ) -> None:
        if result.status == TeamsLaunchStatus.OK:
            logger.info(
                "[TEAMS-CALL] OK url=%s",
                result.url,
            )
        else:
            logger.warning(
                "[TEAMS-CALL] ABGELEHNT status=%s phone=%s tid=%s msg=%s",
                result.status.value,
                target.phone_normalized,
                target.teams_user_id,
                result.error_message,
            )

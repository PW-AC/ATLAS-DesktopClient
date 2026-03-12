"""
Call-Pop Listener – Lokaler HTTP-Server fuer Teams PSTN Screen-Pop.

Lauscht auf 127.0.0.1:47123 und nimmt GET /call-pop?phone=... entgegen.
Leitet die Nummer per Qt-Signal an den Desktop-Client weiter.
"""

import re
import time
import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger("contact.call_pop")

LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 47123
PHONE_RE = re.compile(r"^\+[1-9]\d{6,14}$")
QUERY_MAX_LEN = 256
DEDUP_WINDOW_S = 15.0


def _cors_origin(origin: str, allowed: str) -> str:
    """Gibt den Origin zurueck wenn er zur erlaubten Domain passt."""
    if not origin or not allowed:
        return ""
    if origin.rstrip("/") == allowed.rstrip("/"):
        return origin
    return ""


class _CallPopSignals(QObject):
    call_pop_requested = Signal(str)
    call_pop_refocus = Signal()
    call_pop_event_v2 = Signal(dict)


class _CallPopHandler(BaseHTTPRequestHandler):
    """Handler fuer den lokalen Call-Pop HTTP-Server."""

    server_version = "ATLAS-CallPop/1.0"

    def log_message(self, fmt, *args):
        logger.debug("HTTP %s", fmt % args)

    def do_OPTIONS(self):
        origin = self.headers.get("Origin", "")
        allowed = _cors_origin(origin, self.server.allowed_origin)
        self.send_response(204)
        if allowed:
            self.send_header("Access-Control-Allow-Origin", allowed)
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Max-Age", "86400")
        # Private Network Access (PNA): Chrome/Edge senden diesen Header wenn eine
        # oeffentliche HTTPS-Seite auf localhost zugreift. Ohne diese Antwort
        # blockiert der Browser den Haupt-Request bevor er die App erreicht.
        if self.headers.get("Access-Control-Request-Private-Network"):
            self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/call-pop":
            self._json(404, {"success": False, "error": "Not Found"})
            return

        qs = self.path.split("?", 1)[1] if "?" in self.path else ""
        if len(qs) > QUERY_MAX_LEN:
            self._json(400, {"success": False, "error": "Query too long"})
            return

        params = parse_qs(parsed.query)
        schema_version = int((params.get("schema_version", ["1"])[0] or "1"))
        phone = (params.get("phone", [""])[0] or "").strip()

        if schema_version >= 2:
            phone = phone or (params.get("phone_raw", [""])[0] or "").strip()

        if not phone or not PHONE_RE.match(phone):
            self._json(400, {"success": False, "error": "Invalid phone"})
            logger.warning("[CALL-POP] Ungueltige Nummer: %s", phone[:30])
            return

        now = time.monotonic()
        is_dedup = False
        with self.server.dedup_lock:
            last = self.server.dedup_map.get(phone)
            if last and (now - last) < DEDUP_WINDOW_S:
                is_dedup = True
            self.server.dedup_map[phone] = now
            cutoff = now - DEDUP_WINDOW_S
            stale = [k for k, v in self.server.dedup_map.items() if v < cutoff]
            for k in stale:
                del self.server.dedup_map[k]

        if is_dedup:
            logger.info("[CALL-POP] Duplikat (15s): %s → refocus", phone)
            self.server.signals.call_pop_refocus.emit()
        else:
            logger.info("[CALL-POP] Neuer Anruf: %s (v%d)", phone, schema_version)
            self.server.signals.call_pop_requested.emit(phone)
            if schema_version >= 2:
                v2_payload = {
                    "schema_version": schema_version,
                    "phone_raw": phone,
                    "source": (params.get("source", ["core"])[0] or "core"),
                    "external_call_id": (params.get("external_call_id", [None])[0]),
                    "provider_event_ts_utc": (params.get("provider_event_ts_utc", [None])[0]),
                    "received_at_utc": (params.get("received_at_utc", [None])[0]),
                    "payload_id": (params.get("payload_id", [None])[0]),
                }
                self.server.signals.call_pop_event_v2.emit(v2_payload)

        self._json(200, {"success": True, "phone": phone, "duplicate": is_dedup})

    def _json(self, code: int, body: dict):
        origin = self.headers.get("Origin", "")
        allowed = _cors_origin(origin, self.server.allowed_origin)
        payload = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        if allowed:
            self.send_header("Access-Control-Allow-Origin", allowed)
        # Private Network Access: Antwort-Header damit Chrome/Edge localhost erlaubt
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        self._json(405, {"success": False, "error": "Method not allowed"})

    do_PUT = do_POST
    do_DELETE = do_POST
    do_PATCH = do_POST


class _CallPopHTTPServer(HTTPServer):
    """HTTPServer mit Dedup-State und Signal-Referenz."""

    def __init__(self, addr, handler, signals: _CallPopSignals, allowed_origin: str):
        super().__init__(addr, handler)
        self.signals = signals
        self.allowed_origin = allowed_origin
        self.dedup_map: dict[str, float] = {}
        self.dedup_lock = threading.Lock()


class CallPopListener:
    """Startet und verwaltet den lokalen Call-Pop HTTP-Listener."""

    def __init__(self, allowed_origin: str = "https://acencia.info"):
        self._signals = _CallPopSignals()
        self._server: _CallPopHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._allowed_origin = allowed_origin

    @property
    def call_pop_requested(self) -> Signal:
        return self._signals.call_pop_requested

    @property
    def call_pop_refocus(self) -> Signal:
        return self._signals.call_pop_refocus

    @property
    def call_pop_event_v2(self) -> Signal:
        return self._signals.call_pop_event_v2

    def start(self) -> bool:
        if self._server is not None:
            return True
        try:
            self._server = _CallPopHTTPServer(
                (LISTEN_HOST, LISTEN_PORT),
                _CallPopHandler,
                self._signals,
                self._allowed_origin,
            )
            self._thread = threading.Thread(
                target=self._server.serve_forever,
                name="CallPopListener",
                daemon=True,
            )
            self._thread.start()
            logger.info(
                "[CALL-POP] Listener gestartet auf %s:%d (CORS: %s)",
                LISTEN_HOST, LISTEN_PORT, self._allowed_origin,
            )
            return True
        except OSError as e:
            logger.error("[CALL-POP] Port %d belegt oder Fehler: %s", LISTEN_PORT, e)
            self._server = None
            return False

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server = None
            self._thread = None
            logger.info("[CALL-POP] Listener gestoppt")

    @property
    def is_running(self) -> bool:
        return self._server is not None and self._thread is not None and self._thread.is_alive()

# -*- coding: utf-8 -*-
"""
ACENCIA ATLAS - Asynchrone Worker-Utility

Generischer QThread-basierter Worker fuer API-Calls und I/O-Operationen,
die nicht auf dem Main-Thread laufen duerfen.
"""

import logging
from typing import Any, Callable, Optional

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)


class AsyncWorker(QThread):
    """
    Fuehrt eine beliebige Funktion im Hintergrund aus.

    Signale:
        finished(result) - Funktion erfolgreich, liefert Rueckgabewert
        error(message)   - Funktion fehlgeschlagen, liefert Fehlermeldung

    Verwendung:
        w = AsyncWorker(lambda: api.delete(doc_id), parent=self)
        w.finished.connect(lambda _: toast.show_success("Geloescht"))
        w.error.connect(lambda msg: toast.show_error(msg))
        w.start()
    """

    finished = Signal(object)
    error = Signal(str)

    def __init__(self, fn: Callable, parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self):
        try:
            result = self._fn()
            self.finished.emit(result)
        except Exception as e:
            logger.error("AsyncWorker Fehler: %s", e)
            self.error.emit(str(e))

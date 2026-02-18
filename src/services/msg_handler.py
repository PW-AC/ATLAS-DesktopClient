"""
ACENCIA ATLAS - Outlook MSG Handler

Extrahiert Anhaenge aus .msg E-Mail-Dateien.
Die Anhaenge werden in die Eingangsbox hochgeladen,
die .msg Datei selbst geht in den Roh-Ordner.
"""

import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MsgExtractResult:
    """Ergebnis der MSG-Extraktion."""
    msg_path: str
    attachment_paths: List[str] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def has_attachments(self) -> bool:
        return len(self.attachment_paths) > 0


def is_msg_file(file_path: str) -> bool:
    """Prueft ob eine Datei eine Outlook .msg E-Mail ist."""
    return Path(file_path).suffix.lower() == '.msg'


def extract_msg_attachments(msg_path: str, temp_dir: Optional[str] = None, api_client=None) -> MsgExtractResult:
    """
    Extrahiert Anhaenge aus einer Outlook .msg Datei.
    
    Args:
        msg_path: Pfad zur .msg Datei
        temp_dir: Optionaler Ordner fuer temporaere Dateien.
                  Falls None, wird ein neuer temp-Ordner erstellt.
        api_client: Optionaler APIClient fuer dynamische Passwort-Abfrage bei PDF-Unlock
    
    Returns:
        MsgExtractResult mit Pfaden zu extrahierten Anhaengen
    """
    result = MsgExtractResult(msg_path=msg_path)

    try:
        import extract_msg
    except ImportError:
        result.error = "extract-msg Bibliothek nicht installiert (pip install extract-msg)"
        logger.error(result.error)
        return result

    if temp_dir is None:
        temp_dir = tempfile.mkdtemp(prefix="atlas_msg_")

    try:
        msg = extract_msg.openMsg(msg_path)
    except Exception as e:
        result.error = f"MSG konnte nicht geoeffnet werden: {e}"
        logger.error(f"MSG-Fehler bei {msg_path}: {e}")
        return result

    try:
        attachments = msg.attachments
        if not attachments:
            logger.info(f"MSG ohne Anhaenge: {Path(msg_path).name}")
            return result

        for i, att in enumerate(attachments):
            try:
                # Dateiname ermitteln
                filename = getattr(att, 'longFilename', None) or getattr(att, 'shortFilename', None)
                if not filename:
                    filename = f"anhang_{i + 1}"

                # Dateiname bereinigen (keine Pfad-Zeichen)
                filename = _sanitize_filename(filename)

                # Nur PDF- und ZIP-Anhaenge extrahieren
                lower_name = filename.lower()
                if not (lower_name.endswith('.pdf') or lower_name.endswith('.zip')):
                    logger.debug(f"MSG-Anhang uebersprungen (kein PDF/ZIP): {filename}")
                    continue

                # Eindeutigen Pfad erstellen (Kollisionen vermeiden)
                target_path = _unique_path(os.path.join(temp_dir, filename))

                # Anhang-Daten speichern
                att_data = att.data
                if att_data is None:
                    logger.warning(f"Anhang '{filename}' hat keine Daten, uebersprungen")
                    continue

                with open(target_path, 'wb') as f:
                    f.write(att_data)

                # Passwortgeschuetzte PDFs entsperren (nur fuer PDFs, nicht ZIPs)
                if filename.lower().endswith('.pdf'):
                    try:
                        from services.pdf_unlock import unlock_pdf_if_needed
                        if unlock_pdf_if_needed(target_path, api_client=api_client):
                            logger.info(f"MSG-PDF-Anhang entsperrt: {filename}")
                    except ValueError as e:
                        logger.warning(f"MSG-PDF-Anhang geschuetzt: {e}")
                    except Exception as e:
                        # SV-025 Fix: Fehler loggen statt verschlucken
                        logger.warning(f"PDF-Unlock fuer MSG-Anhang '{filename}' fehlgeschlagen: {e}")

                result.attachment_paths.append(target_path)
                logger.info(f"MSG-Anhang extrahiert: {filename} ({len(att_data)} Bytes)")

            except Exception as e:
                logger.warning(f"Anhang {i} konnte nicht extrahiert werden: {e}")
                continue

        logger.info(
            f"MSG verarbeitet: {Path(msg_path).name} → "
            f"{len(result.attachment_paths)} Anhang/Anhaenge extrahiert"
        )

    finally:
        try:
            msg.close()
        except Exception:
            pass

    return result


def _sanitize_filename(filename: str) -> str:
    """Entfernt unerlaubte Zeichen aus Dateinamen."""
    # Pfad-Separatoren und problematische Zeichen entfernen
    for ch in ['\\', '/', ':', '*', '?', '"', '<', '>', '|']:
        filename = filename.replace(ch, '_')
    # Fuehrende/abschliessende Leerzeichen/Punkte
    filename = filename.strip(' .')
    return filename or "anhang"


def _unique_path(path: str) -> str:
    """Erstellt einen eindeutigen Dateipfad (haengt _2, _3, ... an bei Kollision)."""
    if not os.path.exists(path):
        return path

    base, ext = os.path.splitext(path)
    counter = 2
    while os.path.exists(f"{base}_{counter}{ext}"):
        counter += 1
    return f"{base}_{counter}{ext}"

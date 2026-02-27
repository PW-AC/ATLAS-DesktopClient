"""
PDF-Operationen — Standalone-Funktionen fuer Validierung, Textextraktion,
Leere-Seiten-Erkennung/-Entfernung und Dateityp-Erkennung.

Extrahiert aus services.document_processor fuer bessere Testbarkeit
und Wiederverwendbarkeit. fitz (PyMuPDF) wird lazy importiert.
"""

import logging
import os
import tempfile
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

__all__ = [
    "validate_pdf",
    "extract_full_text",
    "detect_empty_pages",
    "remove_empty_pages",
    "detect_file_type",
]


def validate_pdf(pdf_path: str, api_client=None) -> Tuple[bool, Optional[str]]:
    """
    Validiert ein PDF, erkennt Verschluesselung und versucht bei Fehler Reparatur.

    Kostenoptimiert: Verhindert teure KI-Aufrufe fuer korrupte PDFs.
    Verschluesselte PDFs werden automatisch mit bekannten Passwoertern entsperrt.

    Args:
        pdf_path: Pfad zur PDF-Datei
        api_client: Optionaler API-Client fuer Passwort-Lookup bei verschluesselten PDFs

    Returns:
        (is_valid, repaired_path) — is_valid=True wenn OK oder repariert/entsperrt,
        repaired_path = Pfad zur reparierten Datei (oder None wenn Original OK)
    """
    try:
        import fitz
    except ImportError:
        logger.warning("PyMuPDF nicht installiert, ueberspringe PDF-Validierung")
        return (True, None)

    try:
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        is_encrypted = doc.is_encrypted
        needs_pass = doc.needs_pass if is_encrypted else False
        doc.close()

        if is_encrypted and needs_pass:
            logger.info(f"PDF ist verschluesselt, versuche Entsperrung: {pdf_path}")
            try:
                from services.pdf_unlock import unlock_pdf_if_needed
                unlocked = unlock_pdf_if_needed(pdf_path, api_client=api_client)
                if unlocked:
                    logger.info(f"PDF erfolgreich entsperrt: {pdf_path}")
                    return (True, None)
            except ValueError as ve:
                logger.warning(f"PDF-Entsperrung fehlgeschlagen: {ve}")
                return (False, None)
            except Exception as unlock_err:
                logger.warning(f"PDF-Entsperrung Fehler: {unlock_err}")
                return (False, None)

        if page_count > 0:
            return (True, None)

        logger.warning(f"PDF hat 0 Seiten: {pdf_path}")
        return (False, None)

    except Exception as open_error:
        logger.warning(f"PDF defekt ({open_error}), versuche Reparatur: {pdf_path}")

        try:
            repaired_path = pdf_path + ".repaired.pdf"
            doc = fitz.open(pdf_path)
            doc.save(repaired_path, garbage=4, deflate=True, clean=True)
            doc.close()

            doc2 = fitz.open(repaired_path)
            page_count = len(doc2)
            doc2.close()

            if page_count > 0:
                logger.info(f"PDF erfolgreich repariert: {repaired_path} ({page_count} Seiten)")
                return (True, repaired_path)

            logger.warning("Repariertes PDF hat 0 Seiten")
            try:
                os.remove(repaired_path)
            except OSError:
                pass
            return (False, None)

        except Exception as repair_error:
            logger.warning(f"PDF-Reparatur fehlgeschlagen: {repair_error}")
            repaired_path = pdf_path + ".repaired.pdf"
            try:
                os.remove(repaired_path)
            except OSError:
                pass
            return (False, None)


def extract_full_text(pdf_path: str) -> Tuple[str, int]:
    """
    Extrahiert Volltext ueber ALLE Seiten einer PDF.

    Args:
        pdf_path: Lokaler Pfad zur PDF-Datei

    Returns:
        (extracted_text, pages_with_text)
    """
    try:
        import fitz
    except ImportError:
        logger.warning("PyMuPDF nicht verfuegbar fuer Volltext-Extraktion")
        return ("", 0)

    extracted_text = ""
    pages_with_text = 0

    try:
        pdf_doc = fitz.open(pdf_path)
        for page in pdf_doc:
            page_text = page.get_text("text")
            if page_text and page_text.strip():
                extracted_text += page_text + "\n"
                pages_with_text += 1
        pdf_doc.close()
    except Exception as e:
        logger.warning(f"Volltext-Extraktion fehlgeschlagen: {e}")

    return (extracted_text, pages_with_text)


def detect_empty_pages(pdf_path: str, doc_id: int) -> dict:
    """
    Prueft ein PDF auf leere Seiten und gibt strukturierte Info zurueck.

    Rein informativ — fuehrt keine DB-Aenderungen durch.

    Args:
        pdf_path: Pfad zur PDF-Datei
        doc_id: Dokument-ID (fuer Logging)

    Returns:
        dict mit Schluesseln:
            empty_indices (list[int]), total_pages (int),
            empty_count (int), detail (str | None)
        Bei Fehler: empty_count=0, total_pages=0
    """
    result: dict = {
        "empty_indices": [],
        "total_pages": 0,
        "empty_count": 0,
        "detail": None,
    }

    try:
        from services.empty_page_detector import get_empty_pages

        empty_indices, total_pages = get_empty_pages(pdf_path)
        empty_count = len(empty_indices)

        if total_pages == 0:
            return result

        result["empty_indices"] = empty_indices
        result["total_pages"] = total_pages
        result["empty_count"] = empty_count

        if empty_count > 0:
            if empty_count == total_pages:
                result["detail"] = f"PDF komplett leer ({total_pages} Seiten)"
            else:
                result["detail"] = (
                    f"Leere Seiten erkannt: {empty_count} von {total_pages} "
                    f"(Indizes: {empty_indices})"
                )
            logger.info(f"[Leere Seiten] Dokument {doc_id}: {result['detail']}")

    except Exception as e:
        logger.warning(f"Leere-Seiten-Erkennung fehlgeschlagen fuer Dokument {doc_id}: {e}")

    return result


def remove_empty_pages(pdf_path: str, doc_id: int, docs_api) -> bool:
    """
    Entfernt leere Seiten aus einer bereits lokal vorliegenden PDF,
    laedt die bereinigte Datei hoch und aktualisiert die DB-Zaehler.

    Args:
        pdf_path: Lokaler Pfad zur PDF-Datei
        doc_id: Dokument-ID
        docs_api: DocumentsAPI-Instanz (benoetigt .replace_document_file und .client.put)

    Returns:
        True wenn Seiten entfernt und hochgeladen wurden, sonst False
    """
    try:
        import fitz
    except ImportError:
        logger.warning("PyMuPDF nicht installiert, kann leere Seiten nicht entfernen")
        return False

    from services.empty_page_detector import get_empty_pages

    empty_indices, total = get_empty_pages(pdf_path)
    if not empty_indices or len(empty_indices) >= total:
        return False

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            fitz_doc = fitz.open(pdf_path)
            for idx in sorted(empty_indices, reverse=True):
                fitz_doc.delete_page(idx)

            cleaned_path = os.path.join(tmpdir, "cleaned.pdf")
            fitz_doc.save(cleaned_path, garbage=4, deflate=True)
            fitz_doc.close()

            docs_api.replace_document_file(doc_id, cleaned_path)

        new_total = total - len(empty_indices)
        try:
            docs_api.client.put(
                f"/documents/{doc_id}",
                json_data={"empty_page_count": 0, "total_page_count": new_total},
            )
        except Exception:
            logger.debug(f"Leere-Seiten-Zaehler Update fehlgeschlagen fuer {doc_id}")

        try:
            import glob as _glob

            cache_dir = os.path.join(tempfile.gettempdir(), "bipro_preview_cache")
            for cached in _glob.glob(os.path.join(cache_dir, f"{doc_id}_*")):
                os.unlink(cached)
                logger.debug(f"Vorschau-Cache invalidiert: {cached}")
        except Exception:
            pass

        logger.info(
            f"Dokument {doc_id}: {len(empty_indices)} leere Seiten entfernt "
            f"({total} -> {new_total} Seiten)"
        )
        return True

    except Exception as e:
        logger.warning(f"Leere-Seiten-Entfernung fehlgeschlagen fuer Dokument {doc_id}: {e}")
        return False


def detect_file_type(doc_id: int, download_func) -> Optional[str]:
    """
    Erkennt den Dateityp anhand der Magic-Bytes (ersten 256 Bytes).

    Args:
        doc_id: Dokument-ID
        download_func: Callable(doc_id, target_dir) -> Optional[str]
                       Gibt den lokalen Pfad zurueck oder None.

    Returns:
        'pdf', 'xml', 'gdv' oder None wenn nicht erkannt
    """
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = download_func(doc_id, tmpdir)

            if not local_path or not os.path.exists(local_path):
                logger.warning(f"Content-Detection: Download fehlgeschlagen fuer {doc_id}")
                return None

            with open(local_path, "rb") as f:
                first_bytes = f.read(256)

            if not first_bytes:
                return None

            if first_bytes.startswith(b"%PDF"):
                logger.debug(f"Magic-Bytes: PDF erkannt fuer Dokument {doc_id}")
                return "pdf"

            text_start = first_bytes.lstrip()
            if text_start.startswith(b"<?xml") or (
                text_start.startswith(b"<") and b">" in text_start
            ):
                logger.debug(f"Magic-Bytes: XML erkannt fuer Dokument {doc_id}")
                return "xml"

            for encoding in ["cp1252", "latin-1", "utf-8"]:
                try:
                    first_line = first_bytes.decode(encoding).strip()
                    if first_line.startswith("0001"):
                        logger.debug(f"Magic-Bytes: GDV erkannt fuer Dokument {doc_id}")
                        return "gdv"
                    break
                except UnicodeDecodeError:
                    continue

            logger.debug(f"Dateityp nicht erkannt fuer Dokument {doc_id}")
            return None

    except Exception as e:
        logger.warning(f"Content-Detection fehlgeschlagen fuer {doc_id}: {e}")
        return None

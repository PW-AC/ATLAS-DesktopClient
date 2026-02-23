"""
Bild-zu-PDF-Konvertierung fuer den Document Processor.

Wandelt Bilddateien (PNG, JPG, TIFF, BMP, GIF, WEBP) in PDFs um,
damit sie die normale PDF-Klassifikations-Pipeline durchlaufen koennen.
"""

import logging
import os
from typing import Optional, Set

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS: Set[str] = {'.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp', '.gif', '.webp'}


def is_image_file(filename: str) -> bool:
    """Prueft ob die Datei eine unterstuetzte Bilddatei ist."""
    if not filename:
        return False
    ext = os.path.splitext(filename)[1].lower()
    return ext in IMAGE_EXTENSIONS


def convert_image_to_pdf(image_path: str, output_path: Optional[str] = None) -> Optional[str]:
    """
    Konvertiert ein Bild in ein PDF via PyMuPDF.

    Das Bild wird als einzige Seite in ein PDF eingebettet,
    wobei die Seitengroesse dem Bild entspricht.

    Args:
        image_path: Pfad zur Bilddatei
        output_path: Optionaler Zielpfad fuer das PDF.
                     Wenn None, wird .pdf an den Bildnamen angehaengt.

    Returns:
        Pfad zum erzeugten PDF oder None bei Fehler
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF nicht installiert – Bildkonvertierung nicht moeglich")
        return None

    if not os.path.isfile(image_path):
        logger.warning(f"Bilddatei nicht gefunden: {image_path}")
        return None

    if output_path is None:
        base, _ = os.path.splitext(image_path)
        output_path = base + '.pdf'

    try:
        img_doc = fitz.open(image_path)
        pdf_bytes = img_doc.convert_to_pdf()
        img_doc.close()

        pdf_doc = fitz.open("pdf", pdf_bytes)
        pdf_doc.save(output_path, garbage=3, deflate=True)
        pdf_doc.close()

        file_size = os.path.getsize(output_path)
        logger.info(
            f"Bild -> PDF konvertiert: {os.path.basename(image_path)} "
            f"-> {os.path.basename(output_path)} ({file_size} Bytes)"
        )
        return output_path

    except Exception as e:
        logger.error(f"Bildkonvertierung fehlgeschlagen fuer {image_path}: {e}")
        return None

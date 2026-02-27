"""
Infrastructure-Adapter: PDF-Verarbeitung.

Kapselt PyMuPDF (fitz) Operationen fuer Text-Extraktion
und Seitenzaehlung.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class PdfProcessor:
    """Implementiert IPdfProcessor."""

    def extract_text(self, file_path: str) -> Optional[str]:
        """Extrahiert den Volltext aus einer PDF-Datei."""
        try:
            import fitz
            doc = fitz.open(file_path)
            text_parts = []
            for page in doc:
                text_parts.append(page.get_text())
            doc.close()
            return '\n'.join(text_parts)
        except Exception as e:
            logger.warning(f"PDF Text-Extraktion fehlgeschlagen: {e}")
            return None

    def get_page_count(self, file_path: str) -> int:
        """Gibt die Seitenzahl einer PDF-Datei zurueck."""
        try:
            import fitz
            doc = fitz.open(file_path)
            count = len(doc)
            doc.close()
            return count
        except Exception as e:
            logger.warning(f"PDF Seitenzaehlung fehlgeschlagen: {e}")
            return 0

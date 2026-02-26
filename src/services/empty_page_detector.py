"""
Erkennung leerer PDF-Seiten mit 4-Stufen-Algorithmus.

Stufe 1: Text pruefen (schnell, ~80% der Faelle)
         Kurztext < 30 Zeichen wird als OCR-Rauschen gewertet (Scanner-Artefakte).
Stufe 2: Vektor-Objekte pruefen (Linien, Tabellen, Rahmen)
Stufe 3: Bilder pruefen (vorhanden ja/nein)
Stufe 4: Pixel-Analyse (50 DPI, nur bei Bild-Seiten ohne Text/Vektoren)

Performance: ~5-20ms pro Seite, typisches 10-Seiten-PDF unter 200ms.
"""

import logging
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

# Schwellwerte
# Text kuerzer als dieser Wert wird als OCR-Rauschen gewertet (Scanner-Artefakte
# wie "0", "0 0", "id! - . - 0 0", "-----.- :__U! 0 0" auf sonst leeren Seiten)
OCR_NOISE_MAX_LENGTH = 30

# Pixel-Analyse: Helligkeit und Varianz fuer "weiss"
# Scanner-Seiten haben typischerweise mean ~254-255 und std ~2-5
PIXEL_BRIGHTNESS_THRESHOLD = 250.0
PIXEL_VARIANCE_THRESHOLD = 5.5

# Performance-Optimierung: Sampling-Rate fuer Pixel-Analyse
# Wir pruefen nur jedes 5. Byte, das reicht statistisch fuer die "Weiss-Erkennung"
# und beschleunigt die Analyse signifikant (~5x).
PIXEL_SAMPLING_STEP = 5
# Erst ab dieser Groesse sampeln, um bei kleinen Bildern keine Genauigkeit zu verlieren
PIXEL_SAMPLING_MIN_SIZE = 10000


def _is_pixmap_blank(pix, brightness_threshold: float = PIXEL_BRIGHTNESS_THRESHOLD,
                     variance_threshold: float = PIXEL_VARIANCE_THRESHOLD) -> bool:
    """
    Prueft ob ein PyMuPDF-Pixmap visuell leer (weiss) ist.
    
    Berechnet Durchschnitts-Helligkeit und Standardabweichung der Pixelwerte.
    Bei sehr hoher Helligkeit (~250+) und geringer Varianz (<5.5) gilt
    die Seite als weiss/leer.
    
    Args:
        pix: PyMuPDF Pixmap-Objekt
        brightness_threshold: Minimum-Durchschnittshelligkeit fuer "weiss" (0-255)
        variance_threshold: Maximum-Standardabweichung fuer "gleichmaessig" 
        
    Returns:
        True wenn das Bild visuell leer (weiss) ist
    """
    try:
        samples = pix.samples
        if not samples:
            return True
        
        pixel_bytes = bytes(samples)
        if not pixel_bytes:
            return True
        
        n = len(pixel_bytes)
        
        # Performance-Optimierung: Bei grossen Bildern Sampling verwenden
        if n > PIXEL_SAMPLING_MIN_SIZE:
            pixel_bytes = pixel_bytes[::PIXEL_SAMPLING_STEP]
            n = len(pixel_bytes)

        # Durchschnittliche Helligkeit
        total = sum(pixel_bytes)
        mean = total / n
        
        if mean < brightness_threshold:
            return False
        
        # Standardabweichung (nur wenn Helligkeit hoch genug)
        variance_sum = sum((b - mean) ** 2 for b in pixel_bytes)
        std_dev = (variance_sum / n) ** 0.5
        
        return std_dev < variance_threshold
        
    except Exception as e:
        logger.debug(f"Pixel-Analyse fehlgeschlagen: {e}")
        # Im Zweifel: nicht als leer markieren
        return False


def is_page_empty(page) -> bool:
    """
    Prueft ob eine einzelne PDF-Seite komplett leer/inhaltslos ist.
    
    4-Stufen-Algorithmus (Performance-optimiert, bricht frueh ab):
    
    1. Text vorhanden UND laenger als 30 Zeichen? -> nicht leer (echter Inhalt)
       Text kuerzer als 30 Zeichen? -> Wahrscheinlich OCR-Rauschen, weiter pruefen
    2. Vektor-Objekte vorhanden? -> nicht leer  
    3. Keine Bilder? -> leer (kein Text, keine Vektoren, keine Bilder)
    4. Bilder vorhanden -> Pixel-Analyse (weisses Scan-Bild?)
    
    Args:
        page: PyMuPDF Page-Objekt
        
    Returns:
        True wenn die Seite als leer eingestuft wird
    """
    # Stufe 1: Text pruefen (schnellster Check)
    # Scanner erzeugen auf leeren Seiten oft kurze OCR-Artefakte wie
    # "0", "0 0", "id! - . - 0 0" aus Staub/Schmutz-Pixeln.
    # Nur Text >= 30 Zeichen gilt als echte Inhalte.
    has_short_text = False
    try:
        text = page.get_text("text")
        if text:
            stripped = text.strip()
            if len(stripped) >= OCR_NOISE_MAX_LENGTH:
                return False  # Genuegend Text = echte Inhalte = nicht leer
            elif len(stripped) > 0:
                has_short_text = True  # Kurzer Text, wahrscheinlich OCR-Rauschen
    except Exception as e:
        logger.debug(f"Text-Extraktion fehlgeschlagen (Seite {page.number}): {e}")
    
    # Stufe 2: Vektor-Objekte pruefen (Linien, Tabellen, Rahmen)
    # Nur pruefen wenn kein Kurztext (OCR-Rauschen + Vektoren = immer noch leer)
    if not has_short_text:
        try:
            drawings = page.get_drawings()
            if drawings:
                return False
        except Exception as e:
            logger.debug(f"Vektor-Pruefung fehlgeschlagen (Seite {page.number}): {e}")
    
    # Stufe 3: Bilder pruefen
    try:
        images = page.get_images(full=True)
        if not images:
            # Kein/kurzer Text, keine Vektoren, keine Bilder = definitiv leer
            return True
    except Exception as e:
        logger.debug(f"Bild-Pruefung fehlgeschlagen (Seite {page.number}): {e}")
        # Kein Text, keine Vektoren, Bild-Check fehlgeschlagen
        # Sicherheitshalber als leer werten
        return True
    
    # Stufe 4: Pixel-Analyse (nur bei Bild-Seiten ohne echten Text/Vektoren)
    # Typisch fuer Scanner: weisse Seite als Bild eingescannt
    try:
        pix = page.get_pixmap(dpi=50)
        return _is_pixmap_blank(pix)
    except Exception as e:
        logger.debug(f"Pixel-Analyse fehlgeschlagen (Seite {page.number}): {e}")
        # Im Zweifel: nicht als leer markieren
        return False


def get_empty_pages(pdf_path: str, pdf_doc: Optional[object] = None) -> Tuple[List[int], int]:
    """
    Analysiert ein PDF und gibt die Indizes aller leeren Seiten zurueck.
    
    Args:
        pdf_path: Pfad zur PDF-Datei (genutzt fuer Logging oder wenn pdf_doc None)
        pdf_doc: Optionales fitz.Document Objekt (wenn vorhanden, wird es genutzt und NICHT geschlossen)
        
    Returns:
        Tuple aus (Liste der leeren Seiten-Indizes, Gesamtseitenzahl).
        Bei Fehler wird ([], 0) zurueckgegeben.
    """
    try:
        import fitz
    except ImportError:
        logger.warning("PyMuPDF nicht installiert, ueberspringe Leere-Seiten-Erkennung")
        return ([], 0)
    
    doc = pdf_doc
    should_close = False

    try:
        if doc is None:
            doc = fitz.open(pdf_path)
            should_close = True

        total_pages = len(doc)
        
        if total_pages == 0:
            if should_close:
                doc.close()
            return ([], 0)
        
        empty_pages: List[int] = []
        
        for i in range(total_pages):
            page = doc[i]
            if is_page_empty(page):
                empty_pages.append(i)
        
        if empty_pages:
            if len(empty_pages) == total_pages:
                logger.info(f"PDF komplett leer ({total_pages} Seiten): {pdf_path}")
            else:
                logger.info(
                    f"Leere Seiten gefunden: {len(empty_pages)} von {total_pages} "
                    f"(Indizes: {empty_pages}): {pdf_path}"
                )
        
        return (empty_pages, total_pages)
        
    except Exception as e:
        logger.warning(f"Leere-Seiten-Erkennung fehlgeschlagen fuer {pdf_path}: {e}")
        return ([], 0)
    finally:
        if should_close and doc:
            try:
                doc.close()
            except Exception:
                pass

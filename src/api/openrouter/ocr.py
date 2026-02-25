"""
OCR-Methoden fuer die OpenRouter KI-Pipeline.

Enthaelt OpenRouterOCRMixin mit PDF-zu-Bild, Tesseract-OCR, Vision-OCR
und OCR-Erkennung.
"""

import base64
import io
import logging
import os
from typing import List

logger = logging.getLogger(__name__)

DEFAULT_VISION_MODEL = "openai/gpt-4o"
DEFAULT_OCR_MODEL = "openai/gpt-4o-mini"


class OpenRouterOCRMixin:
    """Mixin mit OCR-Methoden fuer OpenRouterClient."""
    
    def pdf_to_images(self, pdf_path: str, max_pages: int = 5, dpi: int = 150) -> List[str]:
        """
        Konvertiert ein PDF zu Base64-codierten Bildern.
        
        Args:
            pdf_path: Pfad zur PDF-Datei
            max_pages: Maximale Anzahl Seiten (fuer Kosten-/Performance-Optimierung)
            dpi: Aufloesung der Bilder
            
        Returns:
            Liste von Base64-Strings (PNG-Format)
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError(
                "PyMuPDF nicht installiert.\n"
                "Bitte installieren: pip install PyMuPDF"
            )
        
        logger.info(f"Konvertiere PDF zu Bildern: {pdf_path}")
        
        images = []
        doc = fitz.open(pdf_path)
        
        try:
            num_pages = min(len(doc), max_pages)
            logger.debug(f"PDF hat {len(doc)} Seiten, verarbeite {num_pages}")
            
            for page_num in range(num_pages):
                page = doc[page_num]
                
                # Seite zu Bild rendern
                mat = fitz.Matrix(dpi / 72, dpi / 72)
                pix = page.get_pixmap(matrix=mat)
                
                # Als PNG in Base64 kodieren
                png_data = pix.tobytes("png")
                b64_data = base64.b64encode(png_data).decode('utf-8')
                images.append(b64_data)
                
                logger.debug(f"Seite {page_num + 1}/{num_pages} konvertiert")
        finally:
            doc.close()
        
        logger.info(f"{len(images)} Seite(n) konvertiert")
        return images
    
    def ocr_pdf_local(self, pdf_path: str, max_pages: int = 2, dpi: int = 150) -> str:
        """
        Lokale OCR fuer Bild-PDFs via Tesseract (kostenlos, kein API-Call).
        
        Rendert PDF-Seiten lokal zu Bildern und extrahiert Text mit Tesseract OCR.
        Deutlich guenstiger als Cloud-OCR (GPT-4o Vision), fuer gedruckte
        Versicherungsdokumente mit Standardlayout voellig ausreichend.
        
        Args:
            pdf_path: Pfad zur PDF-Datei
            max_pages: Maximale Anzahl Seiten fuer OCR
            dpi: Aufloesung fuer Rendering (150 = gute Balance Qualitaet/Speed)
            
        Returns:
            Extrahierter Text (leer wenn Tesseract nicht verfuegbar)
            
        Raises:
            Keine - gibt leeren String bei Fehler zurueck (Fallback auf Cloud-OCR)
        """
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            logger.debug("pytesseract/Pillow nicht installiert, ueberspringe lokale OCR")
            return ""
        
        try:
            import fitz  # PyMuPDF
        except ImportError:
            return ""
        
        # Tesseract-Pfad konfigurieren (Windows Standard-Installation)
        tesseract_paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        ]
        for tess_path in tesseract_paths:
            if os.path.isfile(tess_path):
                pytesseract.pytesseract.tesseract_cmd = tess_path
                break
        
        try:
            doc = fitz.open(pdf_path)
            num_pages = min(len(doc), max_pages)
            all_text = []
            
            for page_num in range(num_pages):
                page = doc[page_num]
                
                # Seite zu Bild rendern (150 DPI fuer gute OCR-Qualitaet)
                mat = fitz.Matrix(dpi / 72, dpi / 72)
                pix = page.get_pixmap(matrix=mat)
                
                # PyMuPDF Pixmap -> PIL Image (fuer pytesseract)
                png_data = pix.tobytes("png")
                pil_image = Image.open(io.BytesIO(png_data))
                
                # Tesseract OCR (deutsch + englisch)
                page_text = pytesseract.image_to_string(
                    pil_image, 
                    lang='deu+eng',
                    config='--psm 3'  # Fully automatic page segmentation
                )
                
                if page_text.strip():
                    all_text.append(page_text.strip())
            
            doc.close()
            
            result = '\n\n'.join(all_text)
            if result:
                logger.info(f"Lokale OCR (Tesseract): {len(result)} Zeichen aus {num_pages} Seite(n)")
            else:
                logger.debug(f"Lokale OCR: kein Text erkannt in {num_pages} Seite(n)")
            
            return result
            
        except pytesseract.TesseractNotFoundError:
            logger.warning(
                "Tesseract OCR nicht installiert. "
                "Bitte installieren: https://github.com/UB-Mannheim/tesseract/wiki"
            )
            return ""
        except Exception as e:
            logger.warning(f"Lokale OCR fehlgeschlagen: {e}")
            return ""
    
    def extract_text_from_images(self, images_b64: List[str], 
                                  model: str = DEFAULT_OCR_MODEL) -> str:
        """
        Extrahiert Text aus Bildern mittels Vision-Modell (OCR).
        
        Args:
            images_b64: Liste von Base64-codierten Bildern
            model: Vision-Modell
            
        Returns:
            Extrahierter Text
        """
        if not images_b64:
            return ""
        
        logger.info(f"OCR fuer {len(images_b64)} Bild(er) via {model}...")
        
        # Inhalt fuer Vision-Request bauen
        content = [
            {
                "type": "text",
                "text": (
                    "Lies dieses Versicherungsdokument vollstaendig aus. "
                    "Gib den gesamten Text zurueck, Zeile fuer Zeile. "
                    "Achte besonders auf: Versicherer-Name (VU), Datum, Dokumenttyp, "
                    "Versicherungssparte (z.B. Sach, Leben, Kranken, KFZ, Haftpflicht), "
                    "Versicherungsscheinnummern (VS-Nr), Vertragsnummern und Policennummern. "
                    "Bei Tabellen: Spaltenkoepfe und erste Datenzeilen wiedergeben."
                )
            }
        ]
        
        # Bilder hinzufuegen
        for img_b64 in images_b64:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{img_b64}"
                }
            })
        
        messages = [{"role": "user", "content": content}]
        
        response = self._openrouter_request(messages, model=model, max_tokens=2000)
        
        # Text aus Antwort extrahieren
        text = ""
        if response.get('choices'):
            text = response['choices'][0].get('message', {}).get('content', '')
        
        logger.info(f"OCR abgeschlossen: {len(text)} Zeichen")
        return text
    
    def check_pdf_needs_ocr(self, pdf_path: str) -> bool:
        """
        Prueft ob ein PDF OCR benoetigt oder bereits Text enthaelt.
        
        Args:
            pdf_path: Pfad zur PDF-Datei
            
        Returns:
            True wenn OCR benoetigt wird (kein/wenig Text im PDF)
        """
        try:
            import fitz
        except ImportError:
            return True  # Im Zweifel OCR machen
        
        try:
            doc = fitz.open(pdf_path)
            total_text = ""
            
            for page_num in range(min(len(doc), 3)):  # Erste 3 Seiten pruefen
                page = doc[page_num]
                total_text += page.get_text()
            
            doc.close()
            
            # Wenn weniger als 50 Zeichen, braucht es OCR
            needs_ocr = len(total_text.strip()) < 50
            logger.debug(f"PDF hat {len(total_text)} Zeichen Text, needs_ocr={needs_ocr}")
            return needs_ocr
            
        except Exception as e:
            logger.warning(f"Fehler beim Pruefen des PDFs: {e}")
            return True  # Im Zweifel OCR machen

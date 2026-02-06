"""
Dokumenten-Verarbeitungs-Service

Automatische Klassifikation und Verschiebung von Dokumenten in Boxen.
Unterstuetzt parallele Verarbeitung fuer bessere Performance.
"""

import logging
from typing import List, Optional, Tuple, Callable
from dataclasses import dataclass
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import threading
import tempfile
import os

from api.documents import Document, DocumentsAPI, BOX_TYPES
from api.openrouter import OpenRouterClient, ExtractedDocumentData, DocumentClassification
from api.client import APIClient
from api.processing_history import ProcessingHistoryAPI

logger = logging.getLogger(__name__)

# Parallele Verarbeitung
DEFAULT_MAX_WORKERS = 4  # Anzahl gleichzeitiger Verarbeitungen


@dataclass
class ProcessingResult:
    """Ergebnis der Verarbeitung eines Dokuments."""
    document_id: int
    original_filename: str
    success: bool
    target_box: str
    category: Optional[str] = None
    new_filename: Optional[str] = None
    error: Optional[str] = None


@dataclass
class BatchProcessingResult:
    """Ergebnis eines kompletten Verarbeitungslaufs mit Kosten-Tracking."""
    results: List[ProcessingResult]
    total_documents: int
    successful_documents: int
    failed_documents: int
    duration_seconds: float
    # Kosten-Tracking
    credits_before: Optional[float] = None
    credits_after: Optional[float] = None
    total_cost_usd: Optional[float] = None
    cost_per_document_usd: Optional[float] = None
    currency: str = 'USD'
    
    @property
    def success_rate(self) -> float:
        """Erfolgsrate in Prozent."""
        if self.total_documents == 0:
            return 0.0
        return (self.successful_documents / self.total_documents) * 100
    
    def get_cost_summary(self) -> str:
        """Formatierte Kosten-Zusammenfassung."""
        if self.total_cost_usd is None:
            return "Kosten nicht verfuegbar"
        
        cost_str = f"Gesamtkosten: ${self.total_cost_usd:.4f} USD"
        if self.cost_per_document_usd is not None and self.successful_documents > 0:
            cost_str += f" | Pro Dokument: ${self.cost_per_document_usd:.6f} USD"
        return cost_str


class DocumentProcessor:
    """
    Verarbeitet Dokumente aus der Eingangsbox und verschiebt sie in Ziel-Boxen.
    
    Workflow:
    1. Dokumente aus Eingangsbox holen
    2. Fuer jedes Dokument:
       a) In Verarbeitungsbox verschieben
       b) Klassifizieren (XML-Roh, GDV, PDF)
       c) Bei PDF: KI-Klassifikation (Courtage/Sach/Leben/Sonstige)
       d) Optional: Umbenennen
       e) In Ziel-Box verschieben
    """
    
    def __init__(self, api_client: APIClient):
        self.api_client = api_client
        self.docs_api = DocumentsAPI(api_client)
        self.history_api = ProcessingHistoryAPI(api_client)
        self.openrouter: Optional[OpenRouterClient] = None
        
    def _get_openrouter(self) -> OpenRouterClient:
        """Lazy-Init des OpenRouter-Clients."""
        if self.openrouter is None:
            self.openrouter = OpenRouterClient(self.api_client)
        return self.openrouter
    
    def process_inbox(self, 
                      progress_callback: Optional[Callable[[int, int, str], None]] = None,
                      max_workers: int = DEFAULT_MAX_WORKERS
                      ) -> BatchProcessingResult:
        """
        Verarbeitet alle Dokumente in der Eingangsbox PARALLEL.
        
        Inkludiert Kosten-Tracking:
        - Guthaben vor/nach der Verarbeitung
        - Gesamtkosten und Kosten pro Dokument
        - Logging in der Datenbank
        
        Args:
            progress_callback: Optional - Callback fuer Fortschritt (current, total, message)
            max_workers: Anzahl paralleler Verarbeitungen (default: 4)
            
        Returns:
            BatchProcessingResult mit allen Ergebnissen und Kosten
        """
        results = []
        start_time = datetime.now()
        
        # Dokumente aus Eingangsbox holen
        inbox_docs = self.docs_api.list_by_box('eingang')
        total = len(inbox_docs)
        
        if total == 0:
            logger.info("Keine Dokumente in der Eingangsbox")
            return BatchProcessingResult(
                results=[],
                total_documents=0,
                successful_documents=0,
                failed_documents=0,
                duration_seconds=0.0
            )
        
        # ============================================
        # KOSTEN-TRACKING: Guthaben VOR Verarbeitung
        # ============================================
        credits_before = None
        try:
            openrouter = self._get_openrouter()
            credits_info = openrouter.get_credits()
            if credits_info:
                credits_before = credits_info.get('balance', 0.0)
                logger.info(f"OpenRouter-Guthaben vor Verarbeitung: ${credits_before:.4f} USD")
        except Exception as e:
            logger.warning(f"Konnte Guthaben nicht abrufen: {e}")
        
        logger.info(f"Verarbeite {total} Dokument(e) aus der Eingangsbox (parallel, {max_workers} Worker)")
        
        # Thread-sicherer Counter fuer Progress
        completed_count = [0]  # Liste als mutable Container
        progress_lock = threading.Lock()
        
        def process_with_progress(doc: Document) -> ProcessingResult:
            """Wrapper der Progress-Callback aufruft."""
            result = self._process_document(doc)
            
            # Thread-sicher den Counter erhoehen
            with progress_lock:
                completed_count[0] += 1
                current = completed_count[0]
            
            if progress_callback:
                status = "OK" if result.success else "FEHLER"
                progress_callback(current, total, f"{status}: {doc.original_filename}")
            
            return result
        
        # Parallele Verarbeitung mit ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Alle Dokumente gleichzeitig starten
            future_to_doc = {
                executor.submit(process_with_progress, doc): doc 
                for doc in inbox_docs
            }
            
            # Ergebnisse einsammeln sobald fertig
            for future in as_completed(future_to_doc):
                doc = future_to_doc[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    if result.success:
                        logger.info(f"Dokument {doc.id} -> {result.target_box}: {result.new_filename or doc.original_filename}")
                    else:
                        logger.error(f"Dokument {doc.id} Fehler: {result.error}")
                        
                except Exception as e:
                    logger.exception(f"Unerwarteter Fehler bei Dokument {doc.id}")
                    results.append(ProcessingResult(
                        document_id=doc.id,
                        original_filename=doc.original_filename,
                        success=False,
                        target_box='eingang',
                        error=str(e)
                    ))
        
        # ============================================
        # KOSTEN-TRACKING: Guthaben NACH Verarbeitung
        # ============================================
        credits_after = None
        total_cost = None
        cost_per_doc = None
        
        try:
            credits_info = openrouter.get_credits()
            if credits_info:
                credits_after = credits_info.get('balance', 0.0)
                logger.info(f"OpenRouter-Guthaben nach Verarbeitung: ${credits_after:.4f} USD")
                
                # Kosten berechnen
                if credits_before is not None:
                    total_cost = credits_before - credits_after
                    successful_count = sum(1 for r in results if r.success)
                    
                    if successful_count > 0:
                        cost_per_doc = total_cost / successful_count
                    
                    logger.info(f"=== KOSTEN-ZUSAMMENFASSUNG ===")
                    logger.info(f"Guthaben vorher:  ${credits_before:.4f} USD")
                    logger.info(f"Guthaben nachher: ${credits_after:.4f} USD")
                    logger.info(f"Gesamtkosten:     ${total_cost:.4f} USD")
                    if cost_per_doc is not None:
                        logger.info(f"Kosten/Dokument:  ${cost_per_doc:.6f} USD ({successful_count} Dokumente)")
                    logger.info(f"==============================")
        except Exception as e:
            logger.warning(f"Konnte Guthaben nach Verarbeitung nicht abrufen: {e}")
        
        # Dauer berechnen
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        successful_count = sum(1 for r in results if r.success)
        failed_count = total - successful_count
        
        logger.info(f"Verarbeitung abgeschlossen: {successful_count}/{total} erfolgreich in {duration:.1f}s")
        
        # ============================================
        # KOSTEN IN DATENBANK LOGGEN
        # ============================================
        self._log_batch_costs(
            total_documents=total,
            successful_documents=successful_count,
            failed_documents=failed_count,
            duration_seconds=duration,
            credits_before=credits_before,
            credits_after=credits_after,
            total_cost=total_cost,
            cost_per_document=cost_per_doc
        )
        
        return BatchProcessingResult(
            results=results,
            total_documents=total,
            successful_documents=successful_count,
            failed_documents=failed_count,
            duration_seconds=duration,
            credits_before=credits_before,
            credits_after=credits_after,
            total_cost_usd=total_cost,
            cost_per_document_usd=cost_per_doc
        )
    
    def _log_batch_costs(self,
                         total_documents: int,
                         successful_documents: int,
                         failed_documents: int,
                         duration_seconds: float,
                         credits_before: Optional[float],
                         credits_after: Optional[float],
                         total_cost: Optional[float],
                         cost_per_document: Optional[float]) -> None:
        """
        Loggt die Kosten eines Batch-Verarbeitungslaufs in der Datenbank.
        
        Verwendet die Processing-History API mit action='batch_complete'.
        """
        try:
            action_details = {
                'batch_type': 'inbox_processing',
                'total_documents': total_documents,
                'successful_documents': successful_documents,
                'failed_documents': failed_documents,
                'duration_seconds': round(duration_seconds, 2),
                'timestamp': datetime.now().isoformat()
            }
            
            # Kosten-Daten hinzufuegen wenn verfuegbar
            if credits_before is not None:
                action_details['credits_before_usd'] = round(credits_before, 6)
            if credits_after is not None:
                action_details['credits_after_usd'] = round(credits_after, 6)
            if total_cost is not None:
                action_details['total_cost_usd'] = round(total_cost, 6)
            if cost_per_document is not None:
                action_details['cost_per_document_usd'] = round(cost_per_document, 8)
            
            # Als History-Eintrag speichern (document_id=None fuer Batch-Operationen)
            self.history_api.create(
                document_id=None,  # None = Batch-Operation, kein einzelnes Dokument
                action='batch_complete',
                new_status='completed',
                previous_status='processing',
                action_details=action_details,
                success=failed_documents == 0,
                duration_ms=int(duration_seconds * 1000),
                classification_source='batch_processor',
                classification_result=f'{successful_documents}/{total_documents} OK, ${total_cost:.4f} USD' if total_cost else f'{successful_documents}/{total_documents} OK'
            )
            
            logger.debug(f"Batch-Kosten geloggt: {action_details}")
            
        except Exception as e:
            logger.warning(f"Batch-Kosten-Logging fehlgeschlagen: {e}")
    
    def _process_document(self, doc: Document) -> ProcessingResult:
        """
        Verarbeitet ein einzelnes Dokument.
        
        LOGIK (BiPRO-Code-basiert, optimiert):
        1. In Verarbeitungsbox verschieben
        2. XML-Rohdateien -> Roh Archiv (keine KI)
        3. GDV per BiPRO-Code (999xxx) -> GDV Box + Metadaten aus Datensatz (KEINE KI!)
        4. GDV per Dateiendung/Content -> GDV Box + Metadaten aus Datensatz (KEINE KI!)
        5. PDF mit BiPRO-Code:
           a) Courtage (300xxx) -> Courtage Box + KI nur fuer VU+Datum (~200 Token)
           b) VU-Dokumente -> Sparten-KI + minimale Benennung
        6. PDF ohne BiPRO-Code -> Sparten-KI
        7. Rest -> Sonstige
        
        WICHTIG: BiPRO-Code-basierte Klassifikation hat PRIORITÄT vor Content-Check!
        Dies verhindert False-Positives (z.B. PDFs die zufällig "0001" enthalten).
        
        Args:
            doc: Das zu verarbeitende Dokument
            
        Returns:
            ProcessingResult mit Ergebnis
        """
        start_time = datetime.now()
        previous_status = doc.processing_status or 'pending'
        
        try:
            # 1. Status: downloaded -> processing (In Verarbeitungsbox verschieben)
            self.docs_api.update(doc.id, 
                                 box_type='verarbeitung', 
                                 processing_status='processing')
            
            logger.debug(f"Dokument {doc.id}: Status -> processing")
            
            # History: Start der Verarbeitung
            self._log_history(doc.id, 'start_processing', 'processing',
                              previous_status=previous_status,
                              action_details={'source_box': doc.box_type})
            
            target_box = 'sonstige'
            category = None
            new_filename = None
            
            # Audit-Metadaten fuer Klassifikation
            classification_source = None      # ki_gpt4o, rule_bipro, fallback, etc.
            classification_confidence = None  # high, medium, low
            classification_reason = None      # Begruendung
            
            # 2. XML-Rohdateien -> Roh Archiv (keine KI)
            if self._is_xml_raw(doc):
                target_box = 'roh'
                category = 'xml_raw'
                classification_source = 'rule_pattern'
                classification_confidence = 'high'
                classification_reason = 'XML-Rohdatei erkannt (Dateiname-Pattern)'
                logger.info(f"XML-Rohdatei erkannt: {doc.original_filename} -> roh")
            
            # 3. GDV ueber BiPRO-Code (999xxx) - PRIORITÄT!
            # Diese Dateien werden vom BiPRO als .pdf geliefert, sind aber GDV-Datensaetze
            # WICHTIG: Diese Prüfung MUSS vor _is_gdv_file() kommen, da BiPRO-Code
            # zuverlässiger ist als Content-Erkennung!
            elif self._is_bipro_gdv(doc):
                target_box = 'gdv'
                category = 'gdv_bipro'
                classification_source = 'rule_bipro'
                classification_confidence = 'high'
                classification_reason = f'BiPRO-Code {doc.bipro_category} identifiziert GDV-Datei'
                logger.info(f"GDV per BiPRO-Code erkannt: {doc.original_filename} (Code: {doc.bipro_category}) -> gdv")
                
                # VU, Absender und Datum aus GDV-Datensatz extrahieren (KEINE KI!)
                try:
                    with tempfile.TemporaryDirectory() as tmpdir:
                        local_path = self.docs_api.download(doc.id, tmpdir)
                        if local_path:
                            vu_nummer, absender, datum_iso = self._extract_gdv_metadata(local_path)
                            if vu_nummer or absender or datum_iso:
                                parts = []
                                
                                if absender:
                                    parts.append(self._slugify(absender))
                                elif vu_nummer:
                                    parts.append(vu_nummer)
                                
                                if datum_iso:
                                    parts.append(datum_iso)
                                
                                if vu_nummer and absender:
                                    parts.append(f"VU{vu_nummer}")
                                
                                if parts:
                                    new_filename = '_'.join(parts) + '.gdv'
                                    logger.info(f"GDV-Metadaten: Absender={absender}, VU={vu_nummer}, Datum={datum_iso}")
                except Exception as e:
                    logger.warning(f"GDV-Metadaten-Extraktion fehlgeschlagen (BiPRO): {e}")
            
            # 4. GDV-Dateien per Dateiendung/Content -> GDV Box + Metadaten aus Datensatz
            # Diese Prüfung kommt NACH BiPRO-Code, da BiPRO-Code zuverlässiger ist
            elif self._is_gdv_file(doc):
                target_box = 'gdv'
                category = 'gdv'
                classification_source = 'rule_extension'
                classification_confidence = 'high'
                classification_reason = 'GDV-Datei erkannt (Dateiendung/Content)'
                
                # VU, Absender und Datum aus GDV-Datensatz extrahieren (KEINE KI!)
                try:
                    with tempfile.TemporaryDirectory() as tmpdir:
                        local_path = self.docs_api.download(doc.id, tmpdir)
                        if local_path:
                            vu_nummer, absender, datum_iso = self._extract_gdv_metadata(local_path)
                            if vu_nummer or absender or datum_iso:
                                # Dateiname anpassen fuer chronologische Sortierung
                                # Format: Absender_Datum_VU.gdv (Absender ist der Versicherer-Name)
                                parts = []
                                
                                # Absender (Versicherer-Name) hat Prioritaet, falls vorhanden
                                if absender:
                                    parts.append(self._slugify(absender))
                                elif vu_nummer:
                                    parts.append(vu_nummer)
                                
                                if datum_iso:
                                    parts.append(datum_iso)
                                
                                # VU-Nummer als Fallback wenn kein Absender
                                if vu_nummer and not absender:
                                    pass  # Bereits hinzugefuegt
                                elif vu_nummer and absender:
                                    parts.append(f"VU{vu_nummer}")  # Als Zusatz
                                
                                if parts:
                                    new_filename = '_'.join(parts) + '.gdv'
                                    logger.info(f"GDV-Metadaten: Absender={absender}, VU={vu_nummer}, Datum={datum_iso}")
                except Exception as e:
                    logger.warning(f"GDV-Metadaten-Extraktion fehlgeschlagen: {e}")
            
            # 5. PDF mit BiPRO-Kategorie -> Box nach BiPRO-Code
            # WICHTIG: Dies ist ein elif, um die if/elif-Kette nicht zu brechen!
            elif doc.is_pdf and doc.bipro_category:
                logger.debug(f"PDF mit BiPRO-Kategorie: {doc.original_filename} -> Code: {doc.bipro_category}")
                
                # 5a. Courtage-PDFs (BiPRO-Codes 300xxx)
                if self._is_bipro_courtage(doc):
                    target_box = 'courtage'
                    category = 'courtage_bipro'
                    classification_source = 'rule_bipro'
                    classification_confidence = 'high'
                    classification_reason = f'BiPRO-Code {doc.bipro_category} identifiziert Courtage-Dokument'
                    logger.info(f"Courtage per BiPRO-Code erkannt: {doc.original_filename} -> courtage")
                    
                    # KI nur fuer VU + Datum (minimal, ~200 Token)
                    try:
                        with tempfile.TemporaryDirectory() as tmpdir:
                            local_path = self.docs_api.download(doc.id, tmpdir)
                            if local_path:
                                openrouter = self._get_openrouter()
                                result = openrouter.classify_courtage_minimal(local_path)
                                
                                if result:
                                    insurer = result.get('insurer') or 'Unbekannt'
                                    date_iso = result.get('document_date_iso') or ''
                                    
                                    # Dateiname: VU_Courtage_Datum.pdf
                                    insurer_slug = self._slugify(insurer)
                                    if date_iso:
                                        new_filename = f"{insurer_slug}_Courtage_{date_iso}.pdf"
                                    else:
                                        new_filename = f"{insurer_slug}_Courtage.pdf"
                                    
                                    # KI-Quelle zusaetzlich dokumentieren
                                    classification_source = 'ki_courtage_minimal'
                                    classification_reason = f'Courtage via BiPRO + KI-Extraktion: {insurer}, {date_iso}'
                                    
                                    logger.info(f"Courtage klassifiziert: {insurer}, {date_iso}")
                    except Exception as e:
                        logger.warning(f"Courtage-KI fehlgeschlagen: {e}")
                
                # 5b. VU-Dokumente (alle anderen BiPRO-Codes) -> KI fuer Sparte
                else:
                    from config.processing_rules import get_bipro_document_type
                    
                    doc_type = get_bipro_document_type(doc.bipro_category)
                    logger.info(f"VU-Dokument per BiPRO-Code: {doc.original_filename} -> Typ: {doc_type}")
                    
                    # KI: Sparte + Datum bestimmen
                    try:
                        with tempfile.TemporaryDirectory() as tmpdir:
                            local_path = self.docs_api.download(doc.id, tmpdir)
                            if local_path:
                                openrouter = self._get_openrouter()
                                ki_result = openrouter.classify_sparte_with_date(local_path)
                                
                                sparte = ki_result.get('sparte', 'sonstige')
                                date_iso = ki_result.get('document_date_iso')
                                ki_vu_name = ki_result.get('vu_name')
                                ki_confidence = ki_result.get('confidence', 'medium')
                                ki_doc_name = ki_result.get('document_name')  # Dokumentname bei sonstige (Stufe 2)
                                
                                target_box = sparte
                                category = f'sparte_{sparte}'
                                
                                # Audit-Metadaten - Confidence aus KI uebernehmen
                                classification_source = 'ki_gpt4o_mini' if ki_confidence != 'medium' else 'ki_gpt4o_zweistufig'
                                classification_confidence = ki_confidence
                                classification_reason = f'KI-Sparten-Klassifikation: {sparte} ({ki_confidence}), BiPRO-Typ: {doc_type}'
                                
                                logger.info(f"Sparte klassifiziert: {sparte} (confidence: {ki_confidence})")
                                
                                # VU-Name: aus KI oder Dokument-Metadaten
                                if sparte == 'courtage' and ki_vu_name:
                                    vu_name = ki_vu_name
                                else:
                                    vu_name = getattr(doc, 'vu_name', None) or 'VEMA'
                                
                                parts = []
                                parts.append(self._slugify(vu_name))
                                
                                if sparte == 'sonstige' and ki_doc_name:
                                    # Stufe 2 hat einen Dokumentnamen geliefert
                                    parts.append(self._slugify(ki_doc_name))
                                else:
                                    parts.append(sparte.capitalize())
                                
                                # Dokumenttyp bei Sonstige (aus BiPRO) als Fallback
                                if sparte == 'sonstige' and not ki_doc_name and doc_type and doc_type != 'unbekannt':
                                    parts.append(doc_type.capitalize())
                                
                                # Datum nur bei Courtage
                                if sparte == 'courtage' and date_iso:
                                    parts.append(date_iso)
                                
                                new_filename = '_'.join(parts) + '.pdf'
                                logger.info(f"VU-Dokument benannt: {new_filename}")
                    except Exception as e:
                        logger.warning(f"Sparten-KI fehlgeschlagen: {e}")
                        target_box = 'sonstige'
                        category = 'pdf_error'
                        classification_source = 'fallback'
                        classification_confidence = 'low'
                        classification_reason = f'KI-Klassifikation fehlgeschlagen: {str(e)[:100]}'
            
            # 6. PDFs ohne BiPRO-Kategorie -> KI fuer Sparte
            elif doc.is_pdf:
                logger.debug(f"PDF ohne BiPRO-Kategorie: {doc.original_filename}")
                
                try:
                    with tempfile.TemporaryDirectory() as tmpdir:
                        local_path = self.docs_api.download(doc.id, tmpdir)
                        if local_path:
                            openrouter = self._get_openrouter()
                            ki_result = openrouter.classify_sparte_with_date(local_path)
                            
                            sparte = ki_result.get('sparte', 'sonstige')
                            date_iso = ki_result.get('document_date_iso')
                            ki_vu_name = ki_result.get('vu_name')
                            ki_confidence = ki_result.get('confidence', 'medium')
                            ki_doc_name = ki_result.get('document_name')
                            
                            target_box = sparte
                            category = f'sparte_{sparte}'
                            
                            # Audit-Metadaten - Confidence aus KI
                            classification_source = 'ki_gpt4o_mini' if ki_confidence != 'medium' else 'ki_gpt4o_zweistufig'
                            classification_confidence = ki_confidence
                            classification_reason = f'KI-Sparten-Klassifikation ohne BiPRO: {sparte} ({ki_confidence})'
                            
                            logger.info(f"PDF klassifiziert: {sparte} (confidence: {ki_confidence})")
                            
                            # Benennung je nach Sparte
                            if sparte == 'courtage':
                                vu_slug = self._slugify(ki_vu_name) if ki_vu_name else 'Unbekannt'
                                if date_iso:
                                    new_filename = f"{vu_slug}_Courtage_{date_iso}.pdf"
                                else:
                                    new_filename = f"{vu_slug}_Courtage.pdf"
                            elif sparte == 'sonstige' and ki_doc_name:
                                # Stufe 2 hat Dokumentnamen geliefert
                                doc_slug = self._slugify(ki_doc_name)
                                if date_iso:
                                    new_filename = f"{doc_slug}_{date_iso}.pdf"
                                else:
                                    new_filename = f"{doc_slug}.pdf"
                            elif sparte in ['sach', 'leben', 'kranken']:
                                new_filename = f"{sparte.capitalize()}.pdf"
                            elif date_iso:
                                new_filename = f"{sparte.capitalize()}_{date_iso}.pdf"
                except Exception as e:
                    logger.warning(f"PDF-KI fehlgeschlagen: {e}")
                    target_box = 'sonstige'
                    category = 'pdf_error'
                    classification_source = 'fallback'
                    classification_confidence = 'low'
                    classification_reason = f'KI-Klassifikation fehlgeschlagen: {str(e)[:100]}'
            
            # 7. Rest (unbekannte Dateitypen) -> Sonstige
            else:
                target_box = 'sonstige'
                category = 'unknown'
                classification_source = 'fallback'
                classification_confidence = 'low'
                classification_reason = 'Unbekannter Dateityp, keine Klassifikation moeglich'
                logger.debug(f"Unbekannter Dateityp: {doc.original_filename} -> sonstige")
            
            # Schritt 1: processing -> classified (mit Klassifikations-Metadaten)
            update_kwargs = {
                'box_type': target_box,
                'processing_status': 'classified',
                'document_category': category,
            }
            
            # Audit-Metadaten hinzufuegen wenn vorhanden
            if classification_source:
                update_kwargs['classification_source'] = classification_source
            if classification_confidence:
                update_kwargs['classification_confidence'] = classification_confidence
            if classification_reason:
                # Auf 500 Zeichen begrenzen (DB-Limit)
                update_kwargs['classification_reason'] = classification_reason[:500] if classification_reason else None
            # Timestamp immer setzen wenn klassifiziert wurde
            update_kwargs['classification_timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            self.docs_api.update(doc.id, **update_kwargs)
            logger.debug(f"Dokument {doc.id}: Status -> classified")
            
            # History: Klassifikation abgeschlossen
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            self._log_history(doc.id, 'classify', 'classified',
                              previous_status='processing',
                              classification_source=classification_source,
                              classification_result=f'{category} -> {target_box}',
                              action_details={
                                  'category': category,
                                  'target_box': target_box,
                                  'confidence': classification_confidence,
                                  'reason': classification_reason[:200] if classification_reason else None
                              },
                              duration_ms=duration_ms)
            
            # Schritt 2: Falls umbenannt: classified -> renamed
            current_status = 'classified'
            if new_filename:
                self.docs_api.update(doc.id, 
                                     original_filename=new_filename,
                                     ai_renamed=True,
                                     processing_status='renamed')
                current_status = 'renamed'
                logger.debug(f"Dokument {doc.id}: Status -> renamed ({new_filename})")
                self._log_history(doc.id, 'rename', 'renamed',
                                  previous_status='classified',
                                  action_details={'new_filename': new_filename})
            
            # Schritt 3: classified/renamed -> archived (in Ziel-Box)
            self.docs_api.update(doc.id, processing_status='archived')
            logger.debug(f"Dokument {doc.id}: Status -> archived (in {target_box})")
            
            # History: Archivierung abgeschlossen
            self._log_history(doc.id, 'archive', 'archived',
                              previous_status=current_status,
                              action_details={'final_box': target_box, 'new_filename': new_filename})
            
            return ProcessingResult(
                document_id=doc.id,
                original_filename=doc.original_filename,
                success=True,
                target_box=target_box,
                category=category,
                new_filename=new_filename
            )
            
        except Exception as e:
            logger.exception(f"Fehler bei Verarbeitung von Dokument {doc.id}")
            
            # Fehler markieren mit Status: error
            try:
                self.docs_api.update(doc.id, 
                                     box_type='sonstige',
                                     processing_status='error',
                                     ai_processing_error=str(e)[:500])
                logger.debug(f"Dokument {doc.id}: Status -> error")
                
                # History: Fehler protokollieren
                duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                self._log_history(doc.id, 'error', 'error',
                                  previous_status='processing',
                                  success=False,
                                  error_message=str(e)[:500],
                                  duration_ms=duration_ms)
            except Exception:
                pass
            
            return ProcessingResult(
                document_id=doc.id,
                original_filename=doc.original_filename,
                success=False,
                target_box='sonstige',
                error=str(e)
            )
    
    def _slugify(self, text: str) -> str:
        """
        Konvertiert Text in sicheren Dateinamen.
        
        Ersetzt Umlaute und entfernt Sonderzeichen.
        """
        if not text:
            return "unbekannt"
        
        # Umlaute ersetzen
        replacements = {
            'ä': 'ae', 'ö': 'oe', 'ü': 'ue',
            'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue',
            'ß': 'ss'
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Nur alphanumerische Zeichen und Unterstriche
        import re
        text = re.sub(r'[^a-zA-Z0-9_]', '_', text)
        text = re.sub(r'_+', '_', text)  # Mehrfache Unterstriche zusammenfassen
        text = text.strip('_')
        
        return text or "unbekannt"
    
    def _log_history(self,
                     document_id: int,
                     action: str,
                     new_status: str,
                     previous_status: Optional[str] = None,
                     success: bool = True,
                     error_message: Optional[str] = None,
                     classification_source: Optional[str] = None,
                     classification_result: Optional[str] = None,
                     action_details: Optional[dict] = None,
                     duration_ms: Optional[int] = None) -> None:
        """
        Protokolliert einen Verarbeitungsschritt in der History.
        
        Fehler beim Logging werden ignoriert, um die Verarbeitung nicht zu unterbrechen.
        """
        try:
            self.history_api.create(
                document_id=document_id,
                action=action,
                new_status=new_status,
                previous_status=previous_status,
                success=success,
                error_message=error_message,
                classification_source=classification_source,
                classification_result=classification_result,
                action_details=action_details,
                duration_ms=duration_ms
            )
        except Exception as e:
            # Fehler beim History-Logging sollten die Verarbeitung nicht stoppen
            logger.warning(f"History-Logging fehlgeschlagen fuer Dokument {document_id}: {e}")
    
    def _is_bipro_courtage(self, doc: Document) -> bool:
        """
        Prueft ob das Dokument per BiPRO-Code als Courtage klassifiziert ist.
        
        Verwendet die Konfiguration aus config/processing_rules.py
        
        Args:
            doc: Dokument mit bipro_category Attribut
            
        Returns:
            True wenn BiPRO-Code eine Provisionsabrechnung markiert
        """
        from config.processing_rules import is_bipro_courtage_code, BIPRO_COURTAGE_CODES
        
        bipro_category = getattr(doc, 'bipro_category', None)
        
        # Debug-Logging für BiPRO-Kategorien
        if bipro_category:
            is_courtage = is_bipro_courtage_code(bipro_category)
            logger.debug(
                f"BiPRO-Kategorie: {bipro_category} -> "
                f"{'Courtage' if is_courtage else 'NICHT Courtage'} "
                f"(erlaubte Codes: {BIPRO_COURTAGE_CODES})"
            )
            return is_courtage
        else:
            logger.debug(f"Dokument {doc.id} hat keine BiPRO-Kategorie")
            return False
    
    def _is_bipro_gdv(self, doc: Document) -> bool:
        """
        Prueft ob das Dokument per BiPRO-Code als GDV-Datensatz klassifiziert ist.
        
        GDV-Dateien koennen vom BiPRO mit .pdf Endung geliefert werden,
        sind aber tatsaechlich GDV-Bestandsdaten (999er-Codes).
        
        Args:
            doc: Dokument mit bipro_category Attribut
            
        Returns:
            True wenn BiPRO-Code eine GDV-Datei markiert (999xxx)
        """
        from config.processing_rules import is_bipro_gdv_code
        
        bipro_category = getattr(doc, 'bipro_category', None)
        
        if bipro_category:
            is_gdv = is_bipro_gdv_code(bipro_category)
            if is_gdv:
                logger.debug(f"BiPRO-Code {bipro_category} markiert GDV-Datei")
            return is_gdv
        
        return False
    
    def _classify_document(self, doc: Document) -> Tuple[str, str]:
        """
        Klassifiziert ein Dokument basierend auf Typ und Dateiendung.
        
        Bei unbekannten Endungen wird der Dateiinhalt geprueft (Magic-Bytes).
        
        Returns:
            (target_box, category)
        """
        from config.processing_rules import PROCESSING_RULES
        
        filename = doc.original_filename.lower()
        extension = doc.file_extension.lower()
        
        # Bekannte Endungen aus Konfiguration
        known_extensions = PROCESSING_RULES.get('known_extensions', ['.pdf', '.xml', '.gdv', '.txt', ''])
        
        # 1. XML-Rohdateien -> Roh Archiv
        if self._is_xml_raw(doc):
            return ('roh', 'xml_raw')
        
        # 2. GDV-Dateien -> GDV Box
        if self._is_gdv_file(doc):
            return ('gdv', 'gdv')
        
        # 3. PDFs -> muessen von KI klassifiziert werden
        if doc.is_pdf:
            return ('sonstige', 'pdf_pending')
        
        # 4. Unbekannte Endung -> Content-Erkennung (Magic-Bytes)
        if extension not in known_extensions:
            detected_type = self._detect_file_type_by_content(doc)
            
            if detected_type:
                logger.info(f"Unbekannte Endung '{extension}', erkannt als: {detected_type}")
                
                if detected_type == 'gdv':
                    # GDV erkannt -> umbenennen und in GDV Box
                    self._rename_with_extension(doc, '.gdv')
                    return ('gdv', 'gdv_detected')
                    
                elif detected_type == 'pdf':
                    # PDF erkannt -> umbenennen und zur KI
                    self._rename_with_extension(doc, '.pdf')
                    return ('sonstige', 'pdf_pending')
                    
                elif detected_type == 'xml':
                    # XML erkannt -> pruefen ob Roh, sonst Sonstige
                    self._rename_with_extension(doc, '.xml')
                    # Nochmal XML-Roh Check mit neuer Endung
                    if 'roh' in filename:
                        return ('roh', 'xml_raw_detected')
                    return ('sonstige', 'xml_detected')
        
        # 5. Andere Dateien -> Sonstige
        return ('sonstige', 'unknown')
    
    def _detect_file_type_by_content(self, doc: Document) -> Optional[str]:
        """
        Erkennt den Dateityp anhand der Magic-Bytes (ersten Bytes).
        
        Sehr leistungssparend: Liest nur die ersten 256 Bytes.
        
        Args:
            doc: Das zu pruefende Dokument
            
        Returns:
            'pdf', 'xml', 'gdv' oder None wenn nicht erkannt
        """
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                local_path = self.docs_api.download(doc.id, tmpdir)
                
                if not local_path or not os.path.exists(local_path):
                    logger.warning(f"Content-Detection: Download fehlgeschlagen fuer {doc.id}")
                    return None
                
                # Nur erste 256 Bytes lesen (sehr schnell)
                with open(local_path, 'rb') as f:
                    first_bytes = f.read(256)
                
                if not first_bytes:
                    return None
                
                # PDF: Magic-Bytes "%PDF"
                if first_bytes.startswith(b'%PDF'):
                    logger.debug(f"Magic-Bytes: PDF erkannt fuer {doc.original_filename}")
                    return 'pdf'
                
                # XML: Beginnt mit "<?xml" oder "<" (nach Whitespace)
                text_start = first_bytes.lstrip()
                if text_start.startswith(b'<?xml') or (text_start.startswith(b'<') and b'>' in text_start):
                    logger.debug(f"Magic-Bytes: XML erkannt fuer {doc.original_filename}")
                    return 'xml'
                
                # GDV: Erste Zeile beginnt mit "0001" (Vorsatz)
                # Verschiedene Encodings versuchen
                for encoding in ['cp1252', 'latin-1', 'utf-8']:
                    try:
                        first_line = first_bytes.decode(encoding).strip()
                        if first_line.startswith('0001'):
                            logger.debug(f"Magic-Bytes: GDV erkannt fuer {doc.original_filename}")
                            return 'gdv'
                        break  # Encoding funktioniert, aber kein GDV
                    except UnicodeDecodeError:
                        continue
                
                logger.debug(f"Dateityp nicht erkannt fuer {doc.original_filename}")
                return None
                
        except Exception as e:
            logger.warning(f"Content-Detection fehlgeschlagen fuer {doc.id}: {e}")
            return None
    
    def _rename_with_extension(self, doc: Document, new_extension: str) -> bool:
        """
        Benennt ein Dokument um und fuegt die korrekte Endung hinzu.
        
        Args:
            doc: Das umzubenennende Dokument
            new_extension: Die neue Dateiendung (z.B. '.pdf', '.gdv')
            
        Returns:
            True bei Erfolg
        """
        try:
            # Alte Endung entfernen falls vorhanden
            base_name = doc.original_filename
            if '.' in base_name:
                base_name = base_name.rsplit('.', 1)[0]
            
            new_filename = base_name + new_extension
            
            logger.info(f"Umbenennung: {doc.original_filename} -> {new_filename}")
            
            success = self.docs_api.rename_document(doc.id, new_filename)
            return success
            
        except Exception as e:
            logger.warning(f"Umbenennung fehlgeschlagen fuer {doc.id}: {e}")
            return False
    
    def _is_xml_raw(self, doc: Document) -> bool:
        """Prueft ob es sich um eine XML-Rohdatei handelt."""
        from config.processing_rules import PROCESSING_RULES
        
        filename = doc.original_filename
        
        # Pattern-Check
        for pattern in PROCESSING_RULES.get('raw_xml_patterns', []):
            # Einfacher Wildcard-Match
            if pattern.startswith('*'):
                if filename.endswith(pattern[1:]):
                    return True
            elif pattern.endswith('*'):
                if filename.startswith(pattern[:-1]):
                    return True
            elif '*' in pattern:
                prefix, suffix = pattern.split('*', 1)
                if filename.startswith(prefix) and filename.endswith(suffix):
                    return True
            elif filename == pattern:
                return True
        
        # Fallback: XML + "Roh" im Namen
        if doc.is_xml and 'roh' in filename.lower():
            return True
        
        return False
    
    def _is_gdv_file(self, doc: Document) -> bool:
        """
        Prueft ob es sich um eine GDV-Datei handelt.
        
        Logik:
        1. Bereits als GDV markiert -> True
        2. Eindeutige Endung (.gdv) -> True
        3. Ambige Endung (.txt, keine) -> Content-Pruefung (erste Zeile = '0001')
        """
        from config.processing_rules import PROCESSING_RULES
        
        # Bereits als GDV markiert
        if doc.is_gdv:
            return True
        
        extension = doc.file_extension.lower()
        
        # Eindeutige GDV-Endungen (keine Content-Pruefung noetig)
        gdv_extensions = PROCESSING_RULES.get('gdv_extensions', ['.gdv'])
        if extension in gdv_extensions:
            return True
        
        # Ambige Endungen -> Content-Pruefung
        content_check_extensions = PROCESSING_RULES.get('gdv_content_check_extensions', ['.txt', ''])
        if extension in content_check_extensions:
            return self._check_gdv_content(doc)
        
        return False
    
    def _check_gdv_content(self, doc: Document) -> bool:
        """
        Prueft ob der Dateiinhalt eine GDV-Datei ist.
        
        GDV-Dateien beginnen IMMER mit Satzart '0001' (Vorsatz).
        Laedt nur die ersten 256 Bytes zur Pruefung.
        
        WICHTIG: Prueft ZUERST auf PDF-Magic-Bytes, um False-Positives zu vermeiden!
        
        Args:
            doc: Das zu pruefende Dokument
            
        Returns:
            True wenn erste Zeile mit '0001' beginnt UND KEINE PDF-Datei
        """
        try:
            # Dokument herunterladen (nur fuer Content-Check)
            with tempfile.TemporaryDirectory() as tmpdir:
                local_path = self.docs_api.download(doc.id, tmpdir)
                
                if not local_path or not os.path.exists(local_path):
                    logger.warning(f"Content-Check: Download fehlgeschlagen fuer {doc.id}")
                    return False
                
                # Nur erste 256 Bytes lesen (GDV-Zeilen sind 256 Zeichen)
                with open(local_path, 'rb') as f:
                    first_bytes = f.read(256)
                
                if not first_bytes:
                    logger.debug(f"Content-Check: Datei ist leer fuer {doc.id}")
                    return False
                
                # KRITISCH: PDF-Check VOR GDV-Check!
                # PDFs koennen zufaellig "0001" in den ersten Bytes enthalten
                if first_bytes.startswith(b'%PDF'):
                    logger.debug(f"Content-Check: PDF erkannt (nicht GDV) fuer {doc.original_filename}")
                    return False
                
                # Verschiedene Encodings versuchen
                for encoding in ['cp1252', 'latin-1', 'utf-8']:
                    try:
                        first_line = first_bytes.decode(encoding).strip()
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    # Kein Encoding funktioniert
                    logger.debug(f"Content-Check: Encoding fehlgeschlagen fuer {doc.id}")
                    return False
                
                # GDV-Dateien beginnen mit Satzart 0001 (Vorsatz)
                is_gdv = first_line.startswith('0001')
                logger.debug(f"Content-Check fuer {doc.original_filename}: is_gdv={is_gdv}")
                return is_gdv
                
        except Exception as e:
            logger.warning(f"Content-Check fehlgeschlagen fuer {doc.id}: {e}")
            return False
    
    def _extract_gdv_metadata(self, filepath: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Extrahiert VU-Nummer, Absender und Datum aus GDV-Datensatz.
        
        Keine KI noetig - liest direkt aus dem Vorsatz (Satzart 0001):
        - VU-Nummer: Position 5-9 (5 Zeichen)
        - Absender: Position 10-39 (30 Zeichen) - Versicherer-Name
        - Datum: Position 70-77 (erstellungsdatum_von, 8 Zeichen, TTMMJJJJ)
        
        Bei Fehlern werden definierte Fallback-Werte verwendet:
        - Xvu: Unbekannter Versicherer
        - kDatum: Kein Datum gefunden
        
        Args:
            filepath: Pfad zur GDV-Datei
            
        Returns:
            (vu_nummer, absender, datum_iso) - mit Fallback-Werten bei Fehlern
        """
        from config.processing_rules import GDV_FALLBACK_VU, GDV_FALLBACK_DATE
        
        try:
            # Verschiedene Encodings versuchen (GDV ist meist CP1252)
            for encoding in ['cp1252', 'latin-1', 'utf-8']:
                try:
                    with open(filepath, 'r', encoding=encoding) as f:
                        for line in f:
                            # Suche nach Satzart 0001 (Vorsatz)
                            if len(line) >= 77 and line[0:4] == '0001':
                                # VU-Nummer: Position 5-9 (0-basiert: 4-9)
                                vu_nummer = line[4:9].strip()
                                
                                # Absender: Position 10-39 (0-basiert: 9-39)
                                absender = line[9:39].strip() if len(line) >= 39 else None
                                
                                # Datum: Position 70-77 (0-basiert: 69-77)
                                datum_raw = line[69:77].strip()
                                
                                # TTMMJJJJ -> YYYY-MM-DD konvertieren
                                datum_iso = None
                                if len(datum_raw) == 8 and datum_raw.isdigit():
                                    tag = datum_raw[0:2]
                                    monat = datum_raw[2:4]
                                    jahr = datum_raw[4:8]
                                    datum_iso = f"{jahr}-{monat}-{tag}"
                                
                                # Fallback-Werte anwenden wenn noetig
                                if not vu_nummer and not absender:
                                    vu_nummer = GDV_FALLBACK_VU
                                    logger.warning(f"GDV: VU fehlt, verwende Fallback '{GDV_FALLBACK_VU}'")
                                
                                if not datum_iso:
                                    datum_iso = GDV_FALLBACK_DATE
                                    logger.warning(f"GDV: Datum fehlt, verwende Fallback '{GDV_FALLBACK_DATE}'")
                                
                                logger.debug(f"GDV-Metadaten: VU={vu_nummer}, Absender={absender}, Datum={datum_iso}")
                                return (vu_nummer, absender, datum_iso)
                    break  # Encoding funktioniert, aber kein Vorsatz gefunden
                except UnicodeDecodeError:
                    continue
            
            # Kein Vorsatz gefunden - komplettes Fallback
            logger.warning(f"Kein GDV-Vorsatz (0001) gefunden in {filepath}, verwende Fallback-Werte")
            return (GDV_FALLBACK_VU, None, GDV_FALLBACK_DATE)
            
        except Exception as e:
            logger.warning(f"GDV-Metadaten-Extraktion fehlgeschlagen: {e}, verwende Fallback-Werte")
            return (GDV_FALLBACK_VU, None, GDV_FALLBACK_DATE)
    
    def _classify_pdf_with_ai(self, doc: Document) -> Optional[DocumentClassification]:
        """
        Klassifiziert ein PDF mit dem zweistufigen KI-System.
        
        Stufe 1 (Triage): Schnelle Kategorisierung mit GPT-4o-mini
        Stufe 2 (Detail): Nur bei courtage/versicherung mit GPT-4o
        
        Bei 'sonstige' in Stufe 1 wird KEINE teure Detailanalyse gemacht.
        
        Args:
            doc: Das zu klassifizierende Dokument
            
        Returns:
            DocumentClassification oder None bei Fehler
        """
        try:
            openrouter = self._get_openrouter()
            
            # Dokument herunterladen
            with tempfile.TemporaryDirectory() as tmpdir:
                local_path = self.docs_api.download(doc.id, tmpdir)
                
                if not local_path:
                    logger.warning(f"Download fehlgeschlagen fuer Dokument {doc.id}")
                    return None
                
                # Zweistufige KI-Klassifikation (Triage -> Detail bei Bedarf)
                classification = openrouter.classify_pdf_smart(local_path)
                
                return classification
                
        except Exception as e:
            logger.error(f"KI-Klassifikation fehlgeschlagen: {e}")
            return None
    
    def _is_courtage_document(self, extracted: ExtractedDocumentData) -> bool:
        """Prueft ob das Dokument eine Courtage/Provisionsabrechnung ist."""
        from config.processing_rules import PROCESSING_RULES
        
        # Schluesselwoerter fuer Courtage
        courtage_keywords = PROCESSING_RULES.get('courtage_keywords', [])
        
        # Versicherungstyp pruefen
        doc_type = (extracted.versicherungstyp or '').lower()
        
        for keyword in courtage_keywords:
            if keyword.lower() in doc_type:
                return True
        
        return False
    
    def _is_leben_category(self, doc_type: str) -> bool:
        """Prueft ob der Dokumenttyp zur Leben-Kategorie gehoert."""
        leben_keywords = [
            'leben', 'life', 'rente', 'pension', 'altersvorsorge',
            'berufsunfähigkeit', 'bu', 'risiko', 'kapital', 'fond'
        ]
        return any(kw in doc_type for kw in leben_keywords)
    
    def _is_sach_category(self, doc_type: str) -> bool:
        """Prueft ob der Dokumenttyp zur Sach-Kategorie gehoert."""
        sach_keywords = [
            'sach', 'haftpflicht', 'hausrat', 'wohngebäude', 'kfz',
            'auto', 'unfall', 'rechtsschutz', 'glas', 'elektronik',
            'transport', 'gewerbe', 'betrieb'
        ]
        return any(kw in doc_type for kw in sach_keywords)
    
    def process_single_document(self, doc_id: int) -> ProcessingResult:
        """
        Verarbeitet ein einzelnes Dokument (manueller Trigger).
        
        Args:
            doc_id: ID des zu verarbeitenden Dokuments
            
        Returns:
            ProcessingResult
        """
        doc = self.docs_api.get_document(doc_id)
        if not doc:
            return ProcessingResult(
                document_id=doc_id,
                original_filename='',
                success=False,
                target_box='',
                error='Dokument nicht gefunden'
            )
        
        return self._process_document(doc)
    
    def classify_document_preview(self, doc: Document) -> Tuple[str, str]:
        """
        Zeigt Vorschau der Klassifikation ohne Aenderungen.
        
        Returns:
            (target_box, category)
        """
        return self._classify_document(doc)

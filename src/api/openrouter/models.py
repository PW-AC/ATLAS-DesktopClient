"""
Datenmodelle fuer die OpenRouter KI-Pipeline.

Enthaelt DocumentClassification und ExtractedDocumentData Dataclasses.
"""

from dataclasses import dataclass, field
from typing import Optional

from .utils import slug_de


@dataclass
class DocumentClassification:
    """
    Ergebnis der KI-Klassifikation eines Dokuments.
    
    Bestimmt direkt die Ziel-Box und extrahiert Metadaten fuer Benennung.
    """
    # Ziel-Box (direkt von KI bestimmt)
    target_box: str  # 'courtage', 'sach', 'leben', 'kranken', 'sonstige'
    confidence: str  # 'high', 'medium', 'low'
    reasoning: str  # Kurze Begruendung
    
    # Metadaten fuer Benennung
    insurer: Optional[str] = None
    document_date_iso: Optional[str] = None
    date_granularity: Optional[str] = None  # 'day', 'month', 'year'
    document_type: Optional[str] = None  # z.B. "Privathaftpflicht", "Rentenversicherung"
    insurance_type: Optional[str] = None  # 'Leben', 'Sach', 'Kranken' (wichtig bei Courtage!)
    
    # Rohdaten
    raw_response: dict = field(default_factory=dict)
    
    def generate_filename(self, original_extension: str = ".pdf") -> str:
        """
        Generiert Dateinamen nach Schema:
        
        - Courtage: Versicherer_Courtage_Sparte_Datum.ext 
          (z.B. Helvetia_Courtage_Leben_2025-01-15.pdf)
        - Andere: Versicherer_Sparte_Dokumenttyp_Datum.ext 
          (z.B. SV_SparkassenVersicherung_Sach_Mahnung_2026-02-03.pdf)
        
        Verwendet slug_de() fuer sichere Dateinamen.
        """
        parts = []
        
        # 1. Versicherer (max 35 Zeichen fuer laengere Namen)
        insurer_slug = slug_de(self.insurer, max_len=35) if self.insurer else "Unbekannt"
        parts.append(insurer_slug)
        
        # 2. Bei Courtage: "Courtage" + Sparte
        if self.target_box == 'courtage':
            parts.append("Courtage")
            if self.insurance_type:
                parts.append(self.insurance_type)  # Leben, Sach, Kranken
        else:
            # 3. Bei anderen: Sparte + Dokumenttyp
            if self.insurance_type:
                parts.append(self.insurance_type)  # Leben, Sach, Kranken
            
            if self.document_type:
                # Dokumenttyp-Mapping fuer konsistente Namen
                doc_type_map = {
                    'mahnung': 'Mahnung',
                    'beitragserinnerung': 'Mahnung',
                    'zahlungserinnerung': 'Mahnung',
                    'letzte beitragserinnerung': 'Mahnung',
                    'police': 'Police',
                    'versicherungsschein': 'Police',
                    'nachtrag': 'Nachtrag',
                    'rechnung': 'Rechnung',
                    'beitragsrechnung': 'Rechnung',
                    'kuendigung': 'Kuendigung',
                    'kuendigungsbestaetigung': 'Kuendigung',
                    'schadensmeldung': 'Schaden',
                    'schadensabrechnung': 'Schaden',
                    'vermittlerinformation': 'Info',
                    'antrag': 'Antrag',
                }
                doc_type_lower = self.document_type.lower()
                normalized_type = doc_type_map.get(doc_type_lower, self.document_type)
                parts.append(slug_de(normalized_type, max_len=20))
        
        # 4. Datum
        if self.document_date_iso:
            if self.date_granularity == 'year':
                parts.append(self.document_date_iso[:4])  # YYYY
            elif self.date_granularity == 'month':
                parts.append(self.document_date_iso[:7])  # YYYY-MM
            else:
                parts.append(self.document_date_iso)  # YYYY-MM-DD
        
        # Zusammenfuegen
        filename = "_".join(p for p in parts if p)
        
        # Fallback wenn leer
        if not filename or filename == "Unbekannt":
            filename = "Dokument"
        
        if not original_extension.startswith('.'):
            original_extension = '.' + original_extension
        
        return filename + original_extension


@dataclass
class ExtractedDocumentData:
    """Extrahierte Daten aus einem Versicherungsdokument (Legacy)."""
    insurer: Optional[str] = None
    document_date: Optional[str] = None  # Originales Format aus dem Text
    document_date_iso: Optional[str] = None  # ISO-8601 Format (YYYY-MM-DD)
    date_granularity: Optional[str] = None  # 'day', 'month', 'year'
    typ: Optional[str] = None  # Leben, Kranken, Sach
    is_courtage: bool = False  # Ist es eine Provisionsabrechnung?
    raw_response: dict = field(default_factory=dict)
    
    @property
    def versicherungstyp(self) -> Optional[str]:
        """Alias fuer typ."""
        return self.typ
    
    def generate_filename(self, original_extension: str = ".pdf") -> str:
        """
        Generiert einen Dateinamen nach dem Schema: Versicherer_Typ_Datum.ext
        
        Fuer Courtage-Dokumente: Versicherer_Courtage_Datum.ext
        Verwendet slug_de() fuer sichere Dateinamen.
        """
        parts = []
        
        # Versicherer (mit slug_de fuer sichere Zeichen)
        parts.append(slug_de(self.insurer, max_len=30))
        
        # Bei Courtage-Dokumenten speziellen Typ verwenden
        if self.is_courtage:
            parts.append("Courtage")
        elif self.typ:
            typ = self.typ
            # Kurzform verwenden
            typ_map = {
                'lebensversicherung': 'Leben',
                'krankenversicherung': 'Kranken',
                'sachversicherung': 'Sach',
                'leben': 'Leben',
                'kranken': 'Kranken',
                'sach': 'Sach',
            }
            typ = typ_map.get(typ.lower(), typ)
            parts.append(slug_de(typ, max_len=20))
        
        # Datum (mit Granularitaet)
        if self.document_date_iso:
            if self.date_granularity == 'year':
                date_str = self.document_date_iso[:4]  # YYYY
            elif self.date_granularity == 'month':
                date_str = self.document_date_iso[:7]  # YYYY-MM
            else:
                date_str = self.document_date_iso
            parts.append(date_str)
        
        # Zusammenfuegen
        filename = "_".join(parts)
        
        # Extension hinzufuegen
        if not original_extension.startswith('.'):
            original_extension = '.' + original_extension
        
        return filename + original_extension

"""
UseCase: VU-Liste importieren.

Orchestriert Parsing → Relevanz-Anreicherung → API-Import.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass, field

from domain.provision.entities import ImportResult
from domain.provision.relevance import is_commission_relevant, classify_buchungsart
from domain.provision.interfaces import IImportRepository


@dataclass
class EnrichedParseResult:
    """Parse-Ergebnis mit Relevanz-Information."""
    rows: List[Dict] = field(default_factory=list)
    vu_name: str = ''
    total_relevant: int = 0
    total_irrelevant: int = 0


class ImportVuList:
    """Importiert eine VU-Liste mit Relevanz-Bestimmung."""

    def __init__(self, repository: IImportRepository):
        self._repo = repository

    def enrich_rows(self, rows: List[Dict], vu_name: str) -> EnrichedParseResult:
        """Reichert geparste Zeilen mit Relevanz-Information an."""
        result = EnrichedParseResult(vu_name=vu_name)
        for row in rows:
            is_rel = is_commission_relevant(
                vu_name=vu_name,
                courtage_rate=row.get('courtage_rate'),
                buchungsart_raw=row.get('buchungsart_raw'),
                konditionssatz=row.get('konditionssatz'),
            )
            row['is_relevant'] = is_rel
            row['art'] = classify_buchungsart(vu_name, row.get('buchungsart_raw', row.get('art', '')))
            result.rows.append(row)
            if is_rel:
                result.total_relevant += 1
            else:
                result.total_irrelevant += 1
        return result

    def execute(
        self, rows: List[Dict], filename: str,
        sheet_name: str = None, vu_name: str = None,
        file_hash: str = None, skip_match: bool = False,
    ) -> Optional[ImportResult]:
        return self._repo.import_vu_liste(
            rows=rows,
            filename=filename,
            sheet_name=sheet_name,
            vu_name=vu_name,
            file_hash=file_hash,
            skip_match=skip_match,
        )

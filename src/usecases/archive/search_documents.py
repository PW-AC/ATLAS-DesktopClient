"""
UseCase: Volltextsuche ueber Dokumente.
"""

from typing import List

from domain.archive.interfaces import IDocumentRepository
from domain.archive.entities import SearchResult


class SearchDocuments:
    """Fuehrt eine Volltextsuche ueber den ATLAS Index durch."""

    def __init__(self, repository: IDocumentRepository):
        self._repo = repository

    def execute(
        self, query: str, *,
        limit: int = 200,
        include_raw: bool = False,
        substring: bool = False,
    ) -> List[SearchResult]:
        if len(query) < 3:
            return []
        return self._repo.search_documents(
            query, limit=limit,
            include_raw=include_raw, substring=substring,
        )

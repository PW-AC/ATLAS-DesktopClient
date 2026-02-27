"""
UseCase: Klärfälle laden.

Lädt ungematchte und berater-lose Provisionen (nur relevante).
"""

from typing import List, Dict, Tuple

from domain.provision.entities import Commission, VermittlerMapping
from domain.provision.interfaces import IProvisionRepository, IMappingRepository


class LoadClearance:
    """Lädt Klärfälle: Provisionen ohne Vertrag oder ohne Berater."""

    def __init__(self, provision_repo: IProvisionRepository,
                 mapping_repo: IMappingRepository):
        self._prov_repo = provision_repo
        self._map_repo = mapping_repo

    def execute(self) -> Tuple[List[Commission], Dict]:
        unmatched, _ = self._prov_repo.get_commissions(
            match_status='unmatched', is_relevant=True, limit=1000)
        all_matched, _ = self._prov_repo.get_commissions(
            is_relevant=True, limit=5000)
        berater_missing = [
            c for c in all_matched
            if c.match_status in ('auto_matched', 'manual_matched') and not c.berater_id
        ]
        commissions = unmatched + berater_missing
        mappings_data = self._map_repo.get_mappings(include_unmapped=True)
        return commissions, mappings_data

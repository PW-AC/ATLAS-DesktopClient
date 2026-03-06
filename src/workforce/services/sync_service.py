"""
Sync-Service: Mitarbeiterdaten von HR-Providern abrufen und speichern.

Orchestriert den Sync-Prozess zwischen Provider-APIs und PHP-Backend.
"""

import logging
from datetime import datetime

from workforce.providers import ProviderFactory
from workforce.helpers import person_key, json_hash, flatten_record, parse_date

logger = logging.getLogger(__name__)


class SyncService:
    """
    Orchestriert die Synchronisierung von Mitarbeiterdaten.

    Ablauf:
    1. Credentials vom PHP-Backend holen
    2. Provider instanziieren
    3. Mitarbeiterdaten vom Provider abrufen
    4. Daten normalisieren
    5. Ueber PHP-API in MySQL speichern (Bulk-Upsert)
    """

    def __init__(self, api_client):
        """
        Args:
            api_client: WorkforceApiClient-Instanz fuer PHP-Backend-Kommunikation
        """
        self.api = api_client

    def sync_employer(self, employer_id: int, only_active: bool = False) -> dict:
        """
        Synchronisiert alle Mitarbeiterdaten fuer einen Arbeitgeber.

        Args:
            employer_id: ID des Arbeitgebers
            only_active: Nur aktive Mitarbeiter synchronisieren

        Returns:
            Dict mit Sync-Ergebnis
        """
        start = datetime.now()

        employer = self.api.get_employer(employer_id)
        credentials = self.api.get_credentials(employer_id)

        provider = ProviderFactory.create(
            employer['provider_key'],
            credentials
        )

        employees, raw_responses = provider.list_employees(only_active=only_active)

        bulk_data = []
        for emp in employees:
            pid = person_key(emp)
            if not pid:
                continue

            flat = flatten_record(emp)
            data_hash_val = json_hash(flat)

            join_date = parse_date(emp.get('joinDate', ''))
            leave_date = parse_date(emp.get('leaveDate', ''))

            bulk_data.append({
                'provider_pid': pid,
                'first_name': emp.get('firstName', ''),
                'last_name': emp.get('lastName', ''),
                'email': emp.get('email', ''),
                'department': emp.get('department', ''),
                'position': emp.get('position', ''),
                'status': 'active' if emp.get('isActive') else 'inactive',
                'join_date': join_date.strftime('%Y-%m-%d') if join_date else None,
                'leave_date': leave_date.strftime('%Y-%m-%d') if leave_date else None,
                'details_json': emp,
                'data_hash': data_hash_val
            })

        sync_result = self.api.bulk_sync_employees(employer_id, bulk_data)

        duration = (datetime.now() - start).total_seconds() * 1000

        return {
            "employees": employees,
            "raw_responses": raw_responses,
            "sync_result": sync_result,
            "employee_count": len(employees),
            "duration_ms": int(duration)
        }

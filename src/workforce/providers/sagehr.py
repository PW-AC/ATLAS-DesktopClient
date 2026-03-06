"""
SageHR Mock-Provider.

Quelle: app.py Zeilen 2142-2185
"""

from workforce.providers.base import BaseProvider


class SageHrProvider(BaseProvider):
    """Mock-Provider fuer SageHR, gibt statische Testdaten zurueck."""

    def __init__(self, access_key: str, slug: str = None, **kwargs):
        super().__init__(access_key=access_key, slug=slug, **kwargs)

    def list_employees(self, only_active: bool = True) -> tuple[list[dict], list]:
        """Gibt Mock-Mitarbeiterliste zurueck."""
        mock_data = [{
            'id': 's-301',
            'firstName': 'Ben',
            'lastName': 'Berger',
            'isActive': True,
            'position': 'Developer',
            'department': 'IT'
        }]
        data_to_return = [e for e in mock_data if e['isActive']] if only_active else mock_data
        return data_to_return, [mock_data]

    def get_employee_details(self, employee_id: str, return_history: bool = True) -> tuple[dict, dict | list]:
        """Gibt Mock-Mitarbeiterdetails zurueck."""
        mock_details = {
            "isActive": True,
            "firstName": "Ben (Mock)",
            "lastName": "Berger",
            "details": {
                "Info": [{"label": "Provider", "value": "Sage HR Mock"}]
            }
        }
        return (mock_details, mock_details) if return_history else (mock_details, [])

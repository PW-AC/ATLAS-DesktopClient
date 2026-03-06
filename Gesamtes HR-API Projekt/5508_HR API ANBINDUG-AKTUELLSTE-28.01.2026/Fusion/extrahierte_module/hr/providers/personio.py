"""
Personio API Provider.

Quelle: app.py Zeilen 2186-2362
"""

import json
import base64
import requests

from hr.providers.base import BaseProvider
from hr.helpers import format_date_for_display


class PersonioProvider(BaseProvider):
    """
    Provider für das Abrufen von Mitarbeiterdaten aus der Personio API v1.

    API-Basis: https://api.personio.de/v1
    """

    PERSONIO_API_BASE_URL = "https://api.personio.de/v1"

    KEY_TO_LABEL_MAP = {
        "id": "ID", "first_name": "Vorname", "last_name": "Nachname",
        "preferred_name": "Bevorzugter Name", "email": "E-Mail", "gender": "Geschlecht",
        "status": "Status", "position": "Position", "supervisor": "Vorgesetzter",
        "employment_type": "Beschäftigungsart", "weekly_working_hours": "Wochenstunden",
        "hire_date": "Eintrittsdatum", "contract_end_date": "Vertragsende",
        "termination_date": "Kündigungsdatum", "termination_type": "Art der Kündigung",
        "termination_reason": "Kündigungsgrund", "probation_period_end": "Probezeitende",
        "created_at": "Erstellt am", "last_modified_at": "Letzte Änderung",
        "subcompany": "Untergesellschaft", "office": "Arbeitsplatz",
        "department": "Abteilung", "cost_centers": "Kostenstelle",
        "holiday_calendar": "Feiertagskalender", "absence_entitlement": "Urlaubsanspruch",
        "work_schedule": "Arbeitszeitmodell", "fix_salary": "Festgehalt",
        "fix_salary_interval": "Gehaltsintervall", "hourly_salary": "Stundenlohn",
        "last_working_day": "Letzter Arbeitstag", "team": "Team",
        "dynamic_16291384": "Steueridentifikationsnummer",
        "dynamic_16291391": "IBAN", "dynamic_16291393": "Notfallkontakt (Name)",
        "dynamic_16291410": "Straße", "dynamic_16291415": "Persönliche E-Mail",
        "dynamic_16291387": "Sozialversicherungsnummer", "dynamic_16291392": "BIC",
        "dynamic_16291394": "Notfallkontakt (Handy)", "dynamic_16291411": "Hausnummer",
        "dynamic_16291383": "Personalnummer", "dynamic_16291385": "Lohnsteuerklasse",
        "dynamic_16291390": "Abweichender Kontoinhaber", "dynamic_16291416": "Mobilnummer",
        "dynamic_16291381": "Geburtsdatum", "dynamic_16291382": "LinkedIn",
        "dynamic_16291395": "Notfallkontakt (Beziehung)", "dynamic_16291396": "Familienstand",
        "dynamic_16291386": "Kirchensteuer", "dynamic_16291388": "Art der Krankenversicherung",
        "dynamic_16291389": "Krankenversicherung", "dynamic_16291401": "Nationalität",
        "dynamic_16291408": "Postleitzahl", "dynamic_16291397": "Haupt-/Nebenarbeitgeber",
        "dynamic_16291399": "Studienbescheinigung gültig bis", "dynamic_16291409": "Ort",
        "dynamic_16291398": "Kinderfreibetrag", "dynamic_16291400": "Abrechnungsart",
        "dynamic_16291402": "Kündigungsfrist", "dynamic_16291404": "Höchster Schulabschluss",
        "dynamic_16291403": "Beschäftigungsart", "dynamic_16291405": "Höchster Ausbildungsabschluss",
        "dynamic_16291413": "Projekt Manager", "dynamic_16291414": "Mentor"
    }

    KEY_TO_GROUP_MAP = {
        "Persönliche Informationen": [
            "first_name", "last_name", "preferred_name", "dynamic_16291381",
            "gender", "dynamic_16291396", "dynamic_16291401", "dynamic_16291382"
        ],
        "Kontaktdaten": ["email", "dynamic_16291415", "dynamic_16291416"],
        "Adresse": ["dynamic_16291410", "dynamic_16291411", "dynamic_16291408", "dynamic_16291409"],
        "Anstellung": [
            "status", "position", "employment_type", "dynamic_16291403",
            "hire_date", "contract_end_date", "termination_date", "probation_period_end",
            "last_working_day", "termination_type", "termination_reason", "dynamic_16291402"
        ],
        "Organisation": [
            "subcompany", "office", "department", "team", "supervisor",
            "cost_centers", "dynamic_16291413", "dynamic_16291414"
        ],
        "Gehalt & Finanzen": [
            "fix_salary", "fix_salary_interval", "hourly_salary",
            "dynamic_16291400", "dynamic_16291397"
        ],
        "Bankverbindung": ["dynamic_16291391", "dynamic_16291392", "dynamic_16291390"],
        "Steuer & Sozialversicherung": [
            "dynamic_16291383", "dynamic_16291384", "dynamic_16291387",
            "dynamic_16291385", "dynamic_16291398", "dynamic_16291386",
            "dynamic_16291388", "dynamic_16291389"
        ],
        "Systeminformationen": ["id", "created_at", "last_modified_at"],
        "Sonstiges": [
            "holiday_calendar", "absence_entitlement", "work_schedule",
            "dynamic_16291399", "dynamic_16291404", "dynamic_16291405"
        ],
        "Notfallkontakt": ["dynamic_16291393", "dynamic_16291394", "dynamic_16291395"]
    }

    def __init__(self, access_key: str, secret_key: str, **kwargs):
        super().__init__(access_key=access_key, secret_key=secret_key, **kwargs)
        self.bearer_token = None
        self.auth_header = None
        self._authenticate()

    def _authenticate(self):
        """Authentifiziert bei Personio und holt Bearer-Token."""
        try:
            r = requests.post(
                f"{self.PERSONIO_API_BASE_URL}/auth",
                json={"client_id": self.access_key, "client_secret": self.secret_key},
                timeout=10
            )
            r.raise_for_status()
            self.bearer_token = r.json()['data']['token']
            self.auth_header = {'Authorization': f'Bearer {self.bearer_token}'}
        except Exception as e:
            raise ConnectionError(f"Personio-Authentifizierung fehlgeschlagen: {e}")

    def _fetch_profile_picture_as_data_uri(self, url: str) -> str | None:
        """Lädt Profilbild und konvertiert zu Data-URI."""
        if not url or not isinstance(url, str):
            return None
        try:
            r = requests.get(url, headers=self.auth_header, timeout=10)
            r.raise_for_status()
            if 'image' not in r.headers.get('Content-Type', ''):
                return None
            return f"data:{r.headers['Content-Type']};base64,{base64.b64encode(r.content).decode('utf-8')}"
        except Exception:
            return None

    def _normalize_employee_details(self, attributes: dict) -> dict:
        """Normalisiert Personio-Attribute in ein konsistentes Format."""
        grouped_details = {group: [] for group in self.KEY_TO_GROUP_MAP.keys()}
        grouped_details["Andere"] = []

        for key in sorted(attributes.keys()):
            attr_obj = attributes[key]
            if not isinstance(attr_obj, dict):
                continue
            value = attr_obj.get('value')
            if value is None or value == '' or value == []:
                continue

            label = self.KEY_TO_LABEL_MAP.get(key, attr_obj.get('label', key))

            if attr_obj.get('type') == 'date':
                value = format_date_for_display(value)
            elif key == 'supervisor':
                value = f"{value.get('attributes', {}).get('first_name', {}).get('value', '')} {value.get('attributes', {}).get('last_name', {}).get('value', '')}".strip()
            elif key == 'absence_entitlement':
                value = ", ".join([f"{v.get('name', '')}: {v.get('entitlement', 0)}" for v in value])
            elif isinstance(value, dict) and 'attributes' in value:
                value = value['attributes'].get('name', str(value))
            elif key in ['dynamic_16291413', 'dynamic_16291414']:
                try:
                    value = ", ".join([item['label'] for item in json.loads(value)])
                except Exception:
                    pass

            found_group = False
            for group_name, keys_in_group in self.KEY_TO_GROUP_MAP.items():
                if key in keys_in_group:
                    grouped_details[group_name].append({'label': label, 'value': value})
                    found_group = True
                    break
            if not found_group:
                grouped_details["Andere"].append({'label': label, 'value': value})

        final_details = {k: v for k, v in grouped_details.items() if v}
        get_value = lambda k: attributes.get(k, {}).get('value')

        department_val = get_value("department")
        if isinstance(department_val, dict):
            department_val = department_val.get('attributes', {}).get('name', department_val.get('name'))

        return {
            "id": get_value("id"),
            "isActive": str(get_value("status")).lower() == 'active',
            "firstName": get_value("first_name"),
            "lastName": get_value("last_name"),
            "position": get_value("position"),
            "department": department_val,
            "profilePictureUrl": self._fetch_profile_picture_as_data_uri(get_value("profile_picture")),
            "details": final_details
        }

    def list_employees(self, only_active: bool = True) -> tuple[list[dict], list]:
        """Ruft alle Mitarbeiter mit normalisierten Details ab."""
        if not self.auth_header:
            raise ConnectionError("Nicht authentifiziert.")
        try:
            r = requests.get(
                f"{self.PERSONIO_API_BASE_URL}/company/employees",
                headers=self.auth_header, timeout=20
            )
            r.raise_for_status()
            raw_response = r.json()
            employees = []
            for emp_data in raw_response.get('data', []):
                attrs = emp_data.get('attributes', {})
                status = attrs.get('status', {}).get('value', 'inactive')
                is_active = str(status).lower() == 'active'
                if only_active and not is_active:
                    continue
                normalized_details = self._normalize_employee_details(attrs)
                employees.append(normalized_details)
            return employees, [raw_response]
        except Exception as e:
            raise ConnectionError(f"Fehler bei Mitarbeiterliste: {e}")

    def get_employee_details(self, employee_id: str, return_history: bool = True) -> tuple[dict, dict | list]:
        """Ruft Details für einen einzelnen Mitarbeiter ab."""
        if not self.auth_header:
            raise ConnectionError("Nicht authentifiziert.")
        try:
            r = requests.get(
                f"{self.PERSONIO_API_BASE_URL}/company/employees/{employee_id}",
                headers=self.auth_header, timeout=10
            )
            r.raise_for_status()
            raw_response = r.json()
            details = self._normalize_employee_details(
                raw_response.get('data', {}).get('attributes', {})
            )
            return (details, raw_response) if return_history else (details, [])
        except Exception as e:
            raise ValueError(f"Fehler bei Verarbeitung der Mitarbeiterdetails: {e}")

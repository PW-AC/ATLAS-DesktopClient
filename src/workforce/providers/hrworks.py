"""
HRworks API Provider.

Quelle: app.py Zeilen 1889-2141
"""

import requests
from datetime import datetime

from workforce.providers.base import BaseProvider


class HRworksProvider(BaseProvider):
    """
    Provider fuer das Abrufen von Mitarbeiterdaten aus der HRworks API v2.

    Unterstuetzt:
        - Produktion: https://api.hrworks.de/v2
        - Demo: https://api.demo-hrworks.de/v2
    """

    API_BASE_URL = "https://api.hrworks.de/v2"
    DEMO_API_BASE_URL = "https://api.demo-hrworks.de/v2"

    def __init__(self, access_key: str, secret_key: str, is_demo: bool = False, **kwargs):
        super().__init__(access_key=access_key, secret_key=secret_key, **kwargs)
        self.base_url = self.DEMO_API_BASE_URL if is_demo else self.API_BASE_URL
        self.bearer_token = None
        self.auth_header = None
        self._persons_cache = None
        self._authenticate()

    def _fmt_date(self, v: str | None) -> str | None:
        """Formatiert YYYY-MM-DD zu DD.MM.YYYY."""
        if not v:
            return None
        s = str(v)
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
        except Exception:
            return s[:10] if len(s) >= 10 else s

    def _authenticate(self):
        """Authentifiziert bei der HRworks API und holt Bearer-Token."""
        try:
            url = f"{self.base_url}/authentication"
            payload = {"accessKey": self.access_key, "secretAccessKey": self.secret_key}
            response = requests.post(
                url, json=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=20
            )
            response.raise_for_status()
            token_data = response.json() or {}
            token = token_data.get("token") or token_data.get("accessToken")
            if not token:
                raise ValueError("Kein Token in der HRworks-Antwort gefunden.")
            self.bearer_token = token
            self.auth_header = {
                "Authorization": f"Bearer {self.bearer_token}",
                "Accept": "application/json"
            }
        except Exception as e:
            raise ConnectionError(f"HRworks-Authentifizierung fehlgeschlagen: {e}")

    def _get_all_persons(self, only_active: bool = True) -> tuple[list, list]:
        """Ruft alle Personen ab mit Paginierung."""
        if not self.auth_header:
            raise ConnectionError("Nicht authentifiziert.")

        all_persons = []
        raw_responses = []
        url = f"{self.base_url}/persons/master-data"
        params = {"onlyActive": str(only_active).lower(), "page": 1}

        while url:
            resp = requests.get(url, headers=self.auth_header, params=params, timeout=20)
            try:
                resp.raise_for_status()
            except Exception as e:
                raise ConnectionError(f"Fehler bei GET {url}: {resp.status_code} {resp.text}") from e

            data = resp.json() or {}
            raw_responses.append(data)
            items = None
            if isinstance(data, dict):
                for k in ("data", "items", "persons", "results"):
                    if k in data and isinstance(data[k], list):
                        items = data[k]
                        break
            if items is None and isinstance(data, list):
                items = data

            if not items:
                break
            all_persons.extend(items)

            next_url = None
            link_header = resp.headers.get("Link", "")
            for part in link_header.split(","):
                p = part.strip()
                if p.startswith("<") and ">;" in p and 'rel="next"' in p:
                    next_url = p[1:p.index(">;")].strip()
                    break
            url = next_url
            params = None
        return all_persons, raw_responses

    def list_employees(self, only_active: bool = True) -> tuple[list[dict], list]:
        """Ruft alle Mitarbeiter mit normalisierten Details ab."""
        persons, raw_responses = self._get_all_persons(only_active=only_active)
        employees = [self._normalize_employee_details(p) for p in persons]
        employees.sort(key=lambda x: (
            (x.get("lastName") or "").lower(),
            (x.get("firstName") or "").lower()
        ))
        return employees, raw_responses

    def get_employee_details(self, employee_id: str, return_history: bool = True) -> tuple[dict, dict | list]:
        """Ruft Details fuer einen einzelnen Mitarbeiter ab."""
        url = f"{self.base_url}/persons/master-data/{employee_id}"
        r = requests.get(url, headers=self.auth_header, timeout=20)
        if r.status_code == 200:
            raw = r.json()
            details = self._normalize_employee_details(raw.get("data", raw) if isinstance(raw, dict) else {})
            return (details, raw) if return_history else (details, [])

        persons, raw_responses = self._get_all_persons(only_active=False)
        for p in persons:
            if any(str(employee_id) == str(v) for v in (
                p.get("uuid"), p.get("personId"), p.get("personnelNumber"), p.get("id")
            )):
                details = self._normalize_employee_details(p)
                return (details, raw_responses) if return_history else (details, [])

        raise ValueError(f"Mitarbeiter nicht gefunden: {employee_id}")

    def _normalize_employee_details(self, raw: dict) -> dict:
        """Normalisiert rohe HRworks-API-Daten in ein konsistentes Format."""
        pid = raw.get("personId") or raw.get("uuid") or raw.get("personnelNumber") or raw.get("id")
        first, last = raw.get("firstName"), raw.get("lastName")
        status = raw.get("status") or ("active" if raw.get("isActive") else "inactive")
        is_active = bool(raw.get("isActive"))
        if not is_active and isinstance(status, str):
            is_active = (status.strip().lower() == "active")

        join = raw.get("hireDate") or raw.get("joinDate") or raw.get("startDate")
        leave = raw.get("terminationDate") or raw.get("leaveDate") or raw.get("endDate") or raw.get("contractEndDate")

        org_unit = raw.get("organizationUnit") or {}
        department_name = org_unit.get("name") if isinstance(org_unit, dict) else None

        detail = {
            "personId": str(pid) if pid is not None else None,
            "personnelNumber": raw.get("personnelNumber"),
            "firstName": first,
            "lastName": last,
            "birthday": self._fmt_date(raw.get("birthday")) or "",
            "email": raw.get("email") or raw.get("workEmail") or raw.get("businessEmail"),
            "position": raw.get("position") or raw.get("jobTitle"),
            "department": department_name,
            "gender": raw.get("gender"),
            "employmentType": raw.get("employmentType") or raw.get("typeOfEmployment"),
            "status": status,
            "isActive": is_active,
            "joinDate": self._fmt_date(join) or "",
            "leaveDate": self._fmt_date(leave) or "",
            "organizationUnit": org_unit,
            "costCenter": (raw.get("costCenter") or {}),
            "address": (raw.get("address") or {}),
            "bankAccount": (raw.get("bankAccount") or {}),
            "salary": (raw.get("salary") or {}),
            "superior": (raw.get("superior") or {}),
        }

        details_groups = {
            "Persoenliche Informationen": [
                {"label": "Vorname", "value": first},
                {"label": "Nachname", "value": last},
                {"label": "Geburtsdatum", "value": detail["birthday"]},
                {"label": "Geschlecht", "value": detail["gender"]},
            ],
            "Kontaktdaten": [
                {"label": "E-Mail", "value": detail["email"]},
                {"label": "Strasse", "value": detail["address"].get("street")},
                {"label": "Hausnummer", "value": detail["address"].get("streetNumber")},
                {"label": "PLZ", "value": detail["address"].get("zipCode")},
                {"label": "Stadt", "value": detail["address"].get("city")},
            ],
            "Anstellung": [
                {"label": "Position", "value": detail["position"]},
                {"label": "Beschaeftigungsart", "value": detail["employmentType"]},
                {"label": "Eintrittsdatum", "value": detail["joinDate"]},
                {"label": "Kuendigungsdatum", "value": detail["leaveDate"]},
            ],
            "Organisation": [
                {"label": "Abteilung", "value": detail["organizationUnit"].get("name")},
                {"label": "Kostenstelle", "value": detail["costCenter"].get("name")},
            ]
        }

        final_details = {}
        for group, items in details_groups.items():
            filtered_items = [item for item in items if item.get("value")]
            if filtered_items:
                final_details[group] = filtered_items

        detail["details"] = final_details
        return detail

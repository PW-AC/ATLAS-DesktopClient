"""
Konstanten fuer das Workforce-Modul.

Quelle: app.py Zeilen 306-313
"""

SCS_HEADERS = [
    "Name", "Vorname", "Geschlecht", "Titel", "Geburtsdatum",
    "Strasse", "Hausnummer", "PLZ", "Ort", "Land", "Kommentar",
    "Email", "Telefon", "Personalnummer", "Position", "Firmeneintritt",
    "Bruttogehalt", "VWL", "geldwerterVorteil", "SteuerfreibetragJahr", "SteuerfreibetragMonat",
    "SV_Brutto", "Steuerklasse", "Religion", "Kinder", "Abteilung", "Arbeitsplatz", "Arbeitgeber",
    "Status"
]

TRIGGER_EVENTS = ['employee_changed', 'employee_added', 'employee_removed']

CONDITION_OPERATORS = [
    'changed', 'changed_to', 'changed_from', 'changed_from_to',
    'is_empty', 'is_not_empty', 'contains'
]

ACTION_TYPES = ['email', 'api']

"""
Delta-Service: Snapshot-Vergleich und Delta-Export-Orchestrierung.

Quelle: app.py Zeilen 2557-2675
"""

from hr.helpers import (
    json_hash, flatten_record, person_key, getv, get_safe_employer_name
)
from hr.services.export_service import map_to_scs_schema, generate_delta_excel
from hr.services.snapshot_service import compare_snapshots


def build_current_snapshot_data(current_details: list[dict], employer_cfg: dict) -> dict:
    """
    Erstellt Snapshot-Daten aus aktuellen Mitarbeiterdaten.

    Args:
        current_details: Aktuelle Mitarbeiterdetails
        employer_cfg: Arbeitgeber-Konfiguration

    Returns:
        Dict {pid: {hash, flat, core, dates}}
    """
    employer_name = employer_cfg.get('name', '')
    provider_key = employer_cfg.get('provider_key', '')
    current = {}

    for detail in current_details:
        pid = person_key(detail)
        if not pid:
            continue

        details_dict = detail.get("details", {})
        join_date_str = getv(detail, details_dict, "Eintrittsdatum", "joinDate", "hire_date")
        leave_date_str = getv(detail, details_dict, "Kündigungsdatum", "leaveDate", "termination_date", "contract_end_date")
        key_dates = {"join": join_date_str, "leave": leave_date_str}

        flat = flatten_record(detail)
        h = json_hash(flat)
        core = map_to_scs_schema(detail, employer_name, provider_key)
        current[pid] = {"hash": h, "flat": flat, "core": core, "dates": key_dates}

    return current


def calculate_diff(current: dict, previous: dict) -> dict:
    """
    Berechnet den Diff zwischen aktuellem und vorherigem Snapshot.

    Quelle: app.py Zeilen 2598-2613

    Args:
        current: Aktueller Snapshot {pid: {hash, flat, core, dates}}
        previous: Vorheriger Snapshot (gleiches Format)

    Returns:
        Dict mit 'added', 'removed', 'changed' Listen
    """
    prev_pids = set(previous.keys())
    current_pids = set(current.keys())
    added_pids = current_pids - prev_pids
    removed_pids = prev_pids - current_pids
    common_pids = current_pids & prev_pids
    changed_pids = {
        pid for pid in common_pids
        if previous[pid].get('hash') != current[pid].get('hash')
    }

    diff = {
        'added': [
            {
                'pid': pid,
                'name': f"{current[pid]['core'].get('Vorname', '')} {current[pid]['core'].get('Name', '')}".strip(),
                'geburtstag': current[pid]['core'].get('Geburtsdatum', '')
            }
            for pid in added_pids
        ],
        'removed': [
            {
                'pid': pid,
                'name': f"{previous[pid]['core'].get('Vorname', '')} {previous[pid]['core'].get('Name', '')}".strip(),
                'geburtstag': previous[pid]['core'].get('Geburtsdatum', '')
            }
            for pid in removed_pids
        ],
        'changed': []
    }

    comparison = compare_snapshots(previous, current)
    diff['changed'] = comparison.get('changed', [])

    return diff, added_pids, changed_pids


def generate_delta_export(current_details: list[dict], employer_cfg: dict,
                          previous_snapshot: dict, exports_dir: str,
                          always_write: bool = False) -> dict:
    """
    Orchestriert den Delta-Export-Prozess.

    Dies ist die Hauptfunktion, die vom Desktop aufgerufen wird.
    Sie ersetzt generate_delta_scs_export() aus app.py.

    Args:
        current_details: Aktuelle Mitarbeiterdaten vom Provider
        employer_cfg: Arbeitgeber-Konfiguration
        previous_snapshot: Vorheriger Snapshot aus der DB
        exports_dir: Lokales Verzeichnis für temporäre Export-Dateien
        always_write: Ob immer geschrieben werden soll

    Returns:
        Dict mit 'filepath', 'diff', 'current_snapshot', 'added_pids', 'changed_pids'
    """
    current = build_current_snapshot_data(current_details, employer_cfg)
    prev = previous_snapshot or {}

    diff, added_pids, changed_pids = calculate_diff(current, prev)

    if not added_pids and not changed_pids and not always_write:
        return {
            "filepath": None,
            "diff": diff,
            "current_snapshot": current,
            "added_pids": set(),
            "changed_pids": set()
        }

    pids_for_export = sorted(list(added_pids | changed_pids))
    changed_employees = {pid: current[pid] for pid in pids_for_export}
    filepath = generate_delta_excel(changed_employees, employer_cfg, exports_dir)

    return {
        "filepath": filepath,
        "diff": diff,
        "current_snapshot": current,
        "added_pids": added_pids,
        "changed_pids": changed_pids
    }

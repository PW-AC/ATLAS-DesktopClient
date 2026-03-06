"""
Snapshot-Service: Snapshot-Vergleich und Mitarbeiter-Historie.

Quelle: app.py Zeilen 2676-2778 (Historie), 4712-4762 (Vergleich)
"""

from datetime import datetime
from workforce.helpers import parse_date


def compare_snapshots(data1: dict, data2: dict) -> dict:
    """
    Vergleicht zwei Snapshots und gibt einen detaillierten Diff zurueck.

    Args:
        data1: Erstes Snapshot-Dictionary {pid: {hash, flat, core}}
        data2: Zweites Snapshot-Dictionary

    Returns:
        Dict mit 'added', 'removed', 'changed' Listen
    """
    pids1 = set(data1.keys())
    pids2 = set(data2.keys())

    added_pids = pids2 - pids1
    removed_pids = pids1 - pids2
    common_pids = pids1 & pids2

    changed_employees = []
    for pid in common_pids:
        rec1 = data1[pid]
        rec2 = data2[pid]
        if rec1.get('hash') != rec2.get('hash'):
            flat1 = rec1.get('flat', {})
            flat2 = rec2.get('flat', {})
            changes = {}
            all_keys = set(flat1.keys()) | set(flat2.keys())
            for key in all_keys:
                val1 = flat1.get(key)
                val2 = flat2.get(key)
                if val1 != val2:
                    changes[key] = {'from': val1, 'to': val2}

            vorname = rec2.get('core', {}).get('Vorname', '')
            nachname = rec2.get('core', {}).get('Name', '')
            geburtstag = rec2.get('core', {}).get('Geburtsdatum', '')

            name_parts = [f"{vorname} {nachname}".strip(), geburtstag]
            name_str = ", ".join(filter(None, name_parts))

            changed_employees.append({
                'pid': pid,
                'name': name_str,
                'changes': changes
            })

    return {
        'added': [
            {
                'pid': pid,
                'name': f"{data2[pid].get('core', {}).get('Vorname', '')} {data2[pid].get('core', {}).get('Name', '')}".strip()
            }
            for pid in added_pids
        ],
        'removed': [
            {
                'pid': pid,
                'name': f"{data1[pid].get('core', {}).get('Vorname', '')} {data1[pid].get('core', {}).get('Name', '')}".strip()
            }
            for pid in removed_pids
        ],
        'changed': changed_employees
    }


def build_employee_history(snapshots: list[dict]) -> dict:
    """
    Verarbeitet eine Liste von Snapshots zu einer Mitarbeiter-Historie.

    Args:
        snapshots: Liste von Snapshots, sortiert nach Zeitstempel (aeltester zuerst).
                   Jeder Snapshot ist ein Dict:
                   {
                       "snapshot_ts": "2026-02-19T10:35:00Z",
                       "data": { pid: { "core": {...}, "dates": {...}, "hash": "..." } }
                   }

    Returns:
        Dict der Mitarbeiterhistorien {pid: {name, join_date, leave_date, is_active, ...}}
    """
    if not snapshots:
        return {}

    employee_history = {}

    last_snapshot = snapshots[-1]
    last_snapshot_data = last_snapshot.get('data', {})
    pids_in_last_snapshot = set(last_snapshot_data.keys())

    for snap in snapshots:
        snap_data = snap.get('data', {})
        snap_ts_str = snap.get('snapshot_ts', '')

        try:
            snap_dt = datetime.fromisoformat(snap_ts_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            continue

        for pid, data in snap_data.items():
            core_data = data.get('core', {})
            dates = data.get('dates')

            if not dates:
                continue

            join_date_str = dates.get("join")
            leave_date_str = dates.get("leave")

            if pid not in employee_history:
                employee_history[pid] = {
                    "pid": pid,
                    "name": f"{core_data.get('Vorname', '')} {core_data.get('Name', '')}".strip(),
                    "join_date_str": join_date_str,
                    "leave_date_str": leave_date_str,
                    "last_snapshot_dt": snap_dt,
                }
            else:
                employee_history[pid]['last_snapshot_dt'] = snap_dt
                if join_date_str:
                    employee_history[pid]['join_date_str'] = join_date_str
                if leave_date_str:
                    employee_history[pid]['leave_date_str'] = leave_date_str

    for pid, history in employee_history.items():
        history['is_active'] = pid in pids_in_last_snapshot and not history.get('leave_date_str')
        history['join_date'] = parse_date(history['join_date_str'])

        final_leave_date = parse_date(history['leave_date_str'])
        if not final_leave_date and not history['is_active']:
            final_leave_date = history['last_snapshot_dt']

        history['leave_date'] = final_leave_date

    return employee_history

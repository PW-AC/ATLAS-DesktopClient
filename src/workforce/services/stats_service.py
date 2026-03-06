"""
Statistik-Service: Standard- und Langzeit-Statistiken.

Quelle: app.py Zeilen 2779-2965
"""

from datetime import datetime
from collections import Counter

from workforce.helpers import getv, parse_date
from i18n import de as texts


def calculate_statistics(current_employees: list) -> dict:
    """
    Berechnet verschiedene Statistiken basierend auf aktuellen Mitarbeiterlisten.

    Fluktuation wird per BDA-Formel aus Kuendigungsdaten berechnet:
    Fluktuation = Abgaenge(12M) / ((Anfangsbestand + Endbestand) / 2) * 100

    Args:
        current_employees: Aktuelle Mitarbeiterliste

    Returns:
        Dict mit Statistiken
    """
    if not current_employees:
        return {}

    ce = current_employees
    ae = [e for e in ce if e.get('isActive')]
    t = datetime.today()

    sc = {"total": len(ce), "active": len(ae), "inactive": len(ce) - len(ae)}

    gender_map = {
        "male": "Mann", "m": "Mann", "mr": "Mann", "herr": "Mann",
        "female": "Frau", "f": "Frau", "mrs": "Frau", "ms": "Frau",
        "diverse": "Divers", "d": "Divers",
        "mann": "Mann", "frau": "Frau", "maennlich": "Mann", "weiblich": "Frau",
    }

    na = texts.WF_STATS_NOT_SPECIFIED

    def _norm_gender(val: str) -> str:
        if not val:
            return na
        return gender_map.get(val.strip().lower(), val.strip())

    gd = Counter(_norm_gender(getv(e, e.get("details"), "geschlecht", "gender")) for e in ae)

    etd = Counter(
        getv(e, e.get("details"), "beschaeftigungsart", "employmentType") or na for e in ae
    )

    dd = Counter(
        getv(e, e.get("details"), "abteilung", "organizationUnit.name") or na for e in ae
    )
    t5d = dd.most_common(5)

    th, ch, tt, tc, tah, hac = 0, 0, 0, 0, 0, 0

    joins_by_month, leaves_by_month = Counter(), Counter()
    for e in ce:
        hire_date = parse_date(getv(e, e.get("details"), "eintrittsdatum", "joinDate"))
        if hire_date:
            joins_by_month[hire_date.strftime('%Y-%m')] += 1
        term_date = parse_date(getv(e, e.get("details"), "kuendigungsdatum", "leaveDate"))
        if term_date:
            leaves_by_month[term_date.strftime('%Y-%m')] += 1

    labels = []
    cy, cm = t.year, t.month
    for i in range(12):
        m, y = (cm - i - 1) % 12 + 1, cy + (cm - i - 1) // 12
        labels.append(f"{y}-{m:02d}")
    labels.reverse()

    jlt = {
        "labels": labels,
        "joins": [joins_by_month.get(l, 0) for l in labels],
        "leaves": [leaves_by_month.get(l, 0) for l in labels]
    }

    for e in ae:
        jd = parse_date(getv(e, e.get("details"), "eintrittsdatum", "joinDate"))
        bd = parse_date(getv(e, e.get("details"), "geburtsdatum", "birthday"))
        if jd:
            tt += (t - jd).days / 365.25
            tc += 1
        if jd and bd:
            tah += (jd - bd).days / 365.25
            hac += 1
        h_str = getv(e, e.get("details"), "wochenstunden", "workSchedule.weeklyWorkingHours", "weekly_working_hours")
        if h_str:
            try:
                h = float(str(h_str).replace(",", "."))
                th += h
                ch += 1
            except (ValueError, TypeError):
                pass

    ah = round(th / ch, 2) if ch > 0 else 0
    at = round(tt / tc, 1) if tc > 0 else 0
    aha = round(tah / hac, 1) if hac > 0 else 0

    departures_12m = sum(leaves_by_month.get(l, 0) for l in labels)
    headcount_end = len(ae)
    headcount_begin = headcount_end + departures_12m
    avg_headcount = (headcount_begin + headcount_end) / 2
    tr = round((departures_12m / avg_headcount) * 100, 1) if avg_headcount > 0 else 0

    return {
        "status_counts": sc,
        "gender_distribution": {"labels": list(gd.keys()), "data": list(gd.values())},
        "average_weekly_hours": ah,
        "employment_type_distribution": {"labels": list(etd.keys()), "data": list(etd.values())},
        "department_distribution": {"labels": [d[0] for d in t5d], "data": [d[1] for d in t5d]},
        "averages": {"tenure_years": at, "hiring_age": aha},
        "turnover": {"rate_percent": tr, "departures_12m": departures_12m},
        "join_leave_trends": jlt
    }


def calculate_long_term_statistics(employee_history: dict) -> dict:
    """
    Berechnet Langzeit-Statistiken basierend auf der Mitarbeiterhistorie.

    Args:
        employee_history: Mitarbeiterhistorie aus Snapshots

    Returns:
        Dict mit Langzeit-Statistiken
    """
    if not employee_history:
        return {}

    entries_per_year = Counter()
    exits_per_year = Counter()
    total_tenure_days = 0
    employees_with_tenure = 0
    today = datetime.now()

    for pid, history in employee_history.items():
        join_date = history.get('join_date')
        leave_date = history.get('leave_date')

        if join_date:
            entries_per_year[join_date.year] += 1
        if leave_date:
            exits_per_year[leave_date.year] += 1

        effective_leave_date = leave_date or (today if history.get('is_active') else None)
        if join_date and effective_leave_date:
            if effective_leave_date >= join_date:
                duration = effective_leave_date - join_date
                total_tenure_days += duration.days
                employees_with_tenure += 1

    all_years = sorted(list(set(entries_per_year.keys()) | set(exits_per_year.keys())))
    if not all_years:
        min_year, max_year = today.year, today.year
    else:
        min_year, max_year = min(all_years), max(all_years)

    year_labels = list(range(min_year, max_year + 1))
    entry_data = [entries_per_year.get(year, 0) for year in year_labels]
    exit_data = [exits_per_year.get(year, 0) for year in year_labels]

    entries_exits_stats = {
        "labels": [str(y) for y in year_labels],
        "entries": entry_data,
        "exits": exit_data
    }

    avg_tenure_years = 0
    if employees_with_tenure > 0:
        avg_tenure_days = total_tenure_days / employees_with_tenure
        avg_tenure_years = round(avg_tenure_days / 365.25, 1)

    avg_duration_stats = {
        "years": avg_tenure_years,
        "total_employees_included": employees_with_tenure
    }

    return {
        "entries_exits": entries_exits_stats,
        "average_duration": avg_duration_stats
    }

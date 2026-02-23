"""Quick check of xempus data in DB via API."""
import sys
sys.path.insert(0, 'src')
import requests
import json

s = requests.Session()
r = s.post('https://acencia.info/api/auth/login', json={'username': 'admin', 'password': 'Acencia2025!'})
token = r.json().get('data', {}).get('token', '')
headers = {'Authorization': f'Bearer {token}'}

# Stats
r2 = s.get('https://acencia.info/api/pm/xempus/stats', headers=headers)
stats = r2.json().get('data', {})
print("=== STATS ===")
print(f"  Employers: {stats.get('total_employers')}")
print(f"  Employees: {stats.get('total_employees')}")
print(f"  Consultations: {stats.get('total_consultations')}")

per_emp = stats.get('per_employer', [])
if per_emp:
    print(f"\n  Per-Employer (first 3):")
    for pe in per_emp[:3]:
        print(f"    {pe.get('name')}: emp={pe.get('employee_count')}, abg={pe.get('abgeschlossen_count')}")

# Batches
r3 = s.get('https://acencia.info/api/pm/xempus/batches', headers=headers)
batches = r3.json().get('data', {}).get('batches', [])
print(f"\n=== BATCHES ({len(batches)}) ===")
for b in batches:
    bid = b.get('id')
    phase = b.get('import_phase')
    rows = b.get('total_rows')
    active = b.get('is_active_snapshot')
    rc = b.get('record_counts')
    print(f"  Batch {bid}: phase={phase}, rows={rows}, active={active}, record_counts={rc}")

# Employees sample
r4 = s.get('https://acencia.info/api/pm/xempus/employees?per_page=3', headers=headers)
emp_data = r4.json().get('data', {})
emps = emp_data.get('employees', [])
pag = emp_data.get('pagination', {})
print(f"\n=== EMPLOYEES (total: {pag.get('total', '?')}) ===")
for em in emps[:3]:
    eid = em.get('id', '?')[:25]
    emp_id = em.get('employer_id', 'NULL')
    if emp_id:
        emp_id = emp_id[:25]
    name = em.get('name', '?')
    print(f"  id={eid}... employer_id={emp_id}... name={name}")

# Employers sample
r5 = s.get('https://acencia.info/api/pm/xempus/employers', headers=headers)
employers = r5.json().get('data', {}).get('employers', [])
print(f"\n=== EMPLOYERS ({len(employers)} total) ===")
for e in employers[:3]:
    eid = e.get('id', '?')[:25]
    name = e.get('name', '?')
    ec = e.get('employee_count', '?')
    print(f"  id={eid}... name={name}, employee_count={ec}")

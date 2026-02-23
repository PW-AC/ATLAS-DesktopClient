"""Mitarbeiter und Vermittler-Mappings erstellen."""
import sys, os, requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from api.client import APIClient
from api.provision import ProvisionAPI

r = requests.post('https://acencia.info/api/auth/login',
                   json={'username': 'admin', 'password': 'adminadmin'}, timeout=15)
t = r.json().get('data', {}).get('token', '')
c = APIClient()
c.set_token(t)
api = ProvisionAPI(c)

# 2 weitere Berater erstellen
for name in ['Florian Herb', 'Sven Emrich']:
    b = api.create_employee({
        'name': name, 'role': 'consulter',
        'commission_model_id': 1, 'teamleiter_id': 1
    })
    if b:
        print(f"OK: {b.name} (ID={b.id})")
    else:
        print(f"FAIL: {name}")

# Mitarbeiter-Index aufbauen
emps = api.get_employees()
emp_map = {e.name: e.id for e in emps}
print(f"\nMitarbeiter: {emp_map}")

# Vermittler-Mappings
assign = {
    'Daniel Sinizin': 'Daniel Sinizin',
    'Dante Sidore': 'Alina Wandrei',
    'Florian Herb': 'Florian Herb',
    'Sven Emrich': 'Sven Emrich',
}

mdata = api.get_mappings(include_unmapped=True)
for u in mdata['unmapped']:
    vn = u['vermittler_name']
    if 'cerny' in vn.lower() or 'diger' in vn.lower():
        assign[vn] = 'Melissa Albustin'

print(f"\nMappings zu erstellen:")
for vn, emp_name in assign.items():
    eid = emp_map.get(emp_name)
    if eid:
        mid = api.create_mapping(vn, eid)
        status = "OK" if mid else "FAIL"
        print(f"  {vn!r} -> {emp_name} (ID={eid}): {status}")
    else:
        print(f"  {vn!r} -> {emp_name}: BERATER NICHT GEFUNDEN")

# Restliche unmapped pruefen
mdata2 = api.get_mappings(include_unmapped=True)
print(f"\nNach Mapping: {len(mdata2['mappings'])} Mappings, {len(mdata2['unmapped'])} ungeloest")
for u in mdata2['unmapped']:
    print(f"  Noch ungeloest: {u['vermittler_name']}")

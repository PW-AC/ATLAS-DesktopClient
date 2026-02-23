"""Schneller Smoke-Test aller Provision-Endpoints."""
import sys, os, requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from api.client import APIClient
from api.provision import ProvisionAPI

r = requests.post('https://acencia.info/api/auth/login',
                   json={'username': 'admin', 'password': 'adminadmin'}, timeout=30)
t = r.json().get('data', {}).get('token', '')
c = APIClient()
c.set_token(t)
api = ProvisionAPI(c)

tests = [
    ('get_models', lambda: api.get_models()),
    ('get_employees', lambda: api.get_employees()),
    ('get_contracts', lambda: api.get_contracts(limit=3)),
    ('get_commissions', lambda: api.get_commissions(limit=3)),
    ('get_mappings', lambda: api.get_mappings(include_unmapped=True)),
    ('get_dashboard_summary', lambda: api.get_dashboard_summary()),
    ('get_abrechnungen', lambda: api.get_abrechnungen()),
    ('get_import_batches', lambda: api.get_import_batches()),
    ('assign_berater', lambda: api.assign_berater_to_contract(204, 2)),
    ('trigger_auto_match', lambda: api.trigger_auto_match()),
]
passed = 0
for name, fn in tests:
    try:
        result = fn()
        ok = result is not None
        passed += 1 if ok else 0
        status = "OK" if ok else "FAIL"
        print(f"  {status}: {name} -> {type(result).__name__}")
    except Exception as e:
        print(f"  FAIL: {name} -> {e}")
print(f"\n{passed}/{len(tests)} bestanden")

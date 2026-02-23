"""Insert default xempus status mappings via API."""
import requests

s = requests.Session()
r = s.post('https://acencia.info/api/auth/login', json={
    'username': 'admin', 'password': 'Acencia2025!'
})
login_data = r.json()
print("Login response:", login_data.get('success'), login_data.get('error', ''))
token = login_data.get('data', {}).get('token', '')
if not token:
    print("Trying alternate password...")
    r = s.post('https://acencia.info/api/auth/login', json={
        'username': 'admin', 'password': 'admin'
    })
    login_data = r.json()
    print("Login2 response:", login_data.get('success'), login_data.get('error', ''))
    token = login_data.get('data', {}).get('token', '')
h = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}

seeds = [
    ('Policiert', 'abgeschlossen', 'Abgeschlossen', '#4caf50'),
    ('Abgeschlossen', 'abgeschlossen', 'Abgeschlossen', '#4caf50'),
    ('Police erstellt', 'abgeschlossen', 'Abgeschlossen', '#4caf50'),
    ('Vertrag aktiv', 'abgeschlossen', 'Abgeschlossen', '#4caf50'),
    ('Beantragt', 'beantragt', 'Beantragt', '#2196f3'),
    ('In Bearbeitung', 'beantragt', 'Beantragt', '#2196f3'),
    ('Entscheidung ausstehend', 'offen', 'Offen', '#ff9800'),
    ('Unberaten', 'offen', 'Offen', '#ff9800'),
    ('Angesprochen', 'offen', 'Offen', '#ff9800'),
    ('Beratung erfolgt', 'offen', 'Offen', '#ff9800'),
    (u'Nicht gew\u00fcnscht', 'abgelehnt', 'Abgelehnt', '#f44336'),
    ('Abgelehnt', 'abgelehnt', 'Abgelehnt', '#f44336'),
    ('Nicht angesprochen', 'nicht_angesprochen', 'Nicht angesprochen', '#9e9e9e'),
]

ok = 0
for raw, cat, label, color in seeds:
    r2 = s.post('https://acencia.info/api/pm/xempus/status-mapping', headers=h, json={
        'raw_status': raw, 'category': cat, 'display_label': label, 'color': color
    })
    resp = r2.json()
    if resp.get('success'):
        ok += 1
    else:
        print("FAIL:", raw, "->", resp.get('error', '?'))
print(str(ok) + "/" + str(len(seeds)) + " Status-Mappings eingefuegt")

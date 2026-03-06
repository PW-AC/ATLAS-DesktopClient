# 03 - Oberflächen und Seiten (IST-Zustand)

## Routen-Übersicht

### UI-Routen (HTML)

| Route | Methoden | Template | Auth | Evidenz |
|-------|----------|----------|------|---------|
| `/login` | GET, POST | `login.html` | Nein | `app.py:1569-1603` |
| `/logout` | GET | - | Ja | `app.py:1605-1615` |
| `/` | GET | `index.html` | Ja | `app.py:1895-1905` |
| `/employer/add` | GET, POST | `add_employer.html` | Ja | `app.py:1907-1939` |
| `/employer/<id>` | GET | `employer_dashboard.html` | Ja | `app.py:1941-1972` |
| `/employer/<id>/employee/<eid>` | GET | `employee_detail.html` | Ja | `app.py:1974-2001` |
| `/employer/<id>/exports` | GET | `exports.html` | Ja | `app.py:2003-2020` |
| `/employer/<id>/settings` | GET, POST | `employer_settings.html` | Ja | `app.py:2022-2068` |
| `/employer/<id>/statistics` | GET | `statistics.html` | Ja | `app.py:2070-2087` |
| `/employer/<id>/snapshots` | GET | `snapshot_comparison.html` | Ja | `app.py:2089-2149` |
| `/employer/<id>/snapshots/compare` | POST | `snapshot_comparison.html` | Ja | `app.py:2203-2346` |
| `/employer/<id>/snapshots/delete_latest` | POST | - | Ja | `app.py:2348-2379` |
| `/employer/<id>/delete` | POST | - | Ja | `app.py:2382-2404` |
| `/settings` | GET, POST | `settings.html` | Master | `app.py:1617-1687` |
| `/user/settings` | GET, POST | `user_settings.html` | Ja | `app.py:1690-1731` |
| `/styleguide` | GET | `styleguide.html` | Ja | `app.py:2700-2710` |

### API-Routen (JSON)

| Route | Methoden | Auth | Beschreibung | Evidenz |
|-------|----------|------|--------------|---------|
| `/api/user/theme` | POST | Ja | Theme aktualisieren | `app.py:1734-1762` |
| `/api/system/restart` | POST | Master | Server neustarten | `app.py:1765-1798` |
| `/api/logs` | GET | Master | Logs abrufen | `app.py:1801-1827` |
| `/api/employer/<id>/statistics` | GET | Ja | Standard-Statistiken | `app.py:2406-2431` |
| `/api/employer/<id>/long_term_statistics` | GET | Ja | Langzeit-Statistiken | `app.py:2433-2463` |
| `/api/employer/<id>/export/delta_scs` | GET | Ja | Delta-Export generieren | `app.py:2495-2564` |
| `/api/employer/<id>/past_exports` | GET | Ja | Vergangene Exporte | `app.py:2566-2612` |

### Download-Routen

| Route | Methoden | Auth | Beschreibung | Evidenz |
|-------|----------|------|--------------|---------|
| `/employer/<id>/export/standard` | GET | Ja | Standard-Export (XLSX) | `app.py:2465-2493` |
| `/employer/<id>/export/statistics/standard` | GET | Ja | Standard-Stats (TXT) | `app.py:2635-2665` |
| `/employer/<id>/export/statistics/longterm` | GET | Ja | Langzeit-Stats (TXT) | `app.py:2667-2698` |
| `/download/past_export/<path:filename>` | GET | Ja | Vergangene Exporte | `app.py:2614-2633` |

## Templates

| Template | Beschreibung | Extends | Evidenz |
|----------|-------------|---------|---------|
| `base.html` | Basis-Template | - | `templates/base.html` |
| `login.html` | Anmeldeseite | base.html | `templates/login.html` |
| `index.html` | Arbeitgeber-Auswahl | base.html | `templates/index.html` |
| `add_employer.html` | Arbeitgeber hinzufügen | base.html | `templates/add_employer.html` |
| `employer_dashboard.html` | Mitarbeiter-Übersicht | base.html | `templates/employer_dashboard.html` |
| `employee_detail.html` | Mitarbeiter-Details | base.html | `templates/employee_detail.html` |
| `exports.html` | Export-Verwaltung | base.html | `templates/exports.html` |
| `employer_settings.html` | Arbeitgeber-Einstellungen | base.html | `templates/employer_settings.html` |
| `statistics.html` | Statistik-Dashboard | base.html | `templates/statistics.html` |
| `snapshot_comparison.html` | Snapshot-Vergleich | base.html | `templates/snapshot_comparison.html` |
| `settings.html` | Master-Einstellungen | base.html | `templates/settings.html` |
| `user_settings.html` | Benutzer-Einstellungen | base.html | `templates/user_settings.html` |
| `styleguide.html` | Design-System | base.html | `templates/styleguide.html` |

## Rollen-Basierter Zugriff

### Zugriffsmatrix

| Route | Unauthentifiziert | Normaler Benutzer | Master-Benutzer |
|-------|-------------------|-------------------|-----------------|
| `/login` | ✅ | ✅ | ✅ |
| `/logout` | ❌ | ✅ | ✅ |
| `/` | ❌ | ✅ | ✅ |
| `/employer/*` | ❌ | ✅ | ✅ |
| `/settings` | ❌ | ❌ | ✅ |
| `/user/settings` | ❌ | ✅ | ✅ |
| `/api/system/restart` | ❌ | ❌ | ✅ |
| `/api/logs` | ❌ | ❌ | ✅ |

### Authentifizierungs-Middleware

**Evidenz:** `app.py:1830-1858`

```python
@app.before_request
def before_request_handler():
    # ...
    if 'user_id' not in session and request.endpoint not in ['login', 'static']:
        return redirect(url_for('login'))
```

**Beobachtung:** 
- Keine Whitelist für `/static` Dateien außer `request.endpoint == 'static'`
- Keine Rate-Limiting-Prüfung

## Formular-Übersicht

| Seite | Formular | Felder | CSRF | Evidenz |
|-------|----------|--------|------|---------|
| `/login` | Login | username, password | ❌ | `login.html:11-21` |
| `/settings` | Add User | username, password, kuerzel, color, is_master | ❌ | `settings.html:15-46` |
| `/settings` | Delete User | username | ❌ | `settings.html:102-106` |
| `/settings` | Save PAT | github_pat | ❌ | `settings.html:69-76` |
| `/employer/add` | Add Employer | name, provider_key, access_key, secret_key, address | ❌ | `add_employer.html:12-72` |
| `/employer/<id>/settings` | Edit Employer | street, zip_code, city, country, email, phone, fax, comment | ❌ | `employer_settings.html` |
| `/user/settings` | Change Password | current_password, new_password, confirm_password | ❌ | `user_settings.html` |

**Beobachtung:** Kein CSRF-Schutz auf allen Formularen.

## JavaScript-Interaktionen

| Seite | Funktion | Beschreibung | Evidenz |
|-------|----------|--------------|---------|
| `base.html` | Theme Toggle | Theme-Wechsel via API | `base.html:86-142` |
| `settings.html` | Server Restart | POST zu `/api/system/restart` | `settings.html:136-177` |
| `settings.html` | Log Viewer | Polling alle 4 Sekunden | `settings.html:179-216` |
| `exports.html` | Delta Export | Fetch zu `/api/.../delta_scs` | `exports.html` |
| `statistics.html` | Stats API | Fetch zu `/api/.../statistics` | `statistics.html` |

---

**Letzte Aktualisierung:** 28.01.2026

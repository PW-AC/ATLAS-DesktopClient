# 05 – API-Client-Spezifikation (Desktop → PHP-Backend)

## Übersicht

Der `HRApiClient` ist die zentrale Klasse für die Kommunikation zwischen dem ATLAS-Desktop und dem PHP-Backend auf Strato. Er nutzt den bestehenden ATLAS-HTTP-Client mit JWT-Authentifizierung.

---

## Klassenstruktur

```python
class HRApiClient:
    """
    API-Client für HR-Modul-Kommunikation mit PHP-Backend.
    
    Nutzt den bestehenden ATLAS BaseApiClient für:
    - JWT-Authentifizierung (automatisch)
    - Error-Handling (einheitlich)
    - Retry-Logik (bei Netzwerkfehlern)
    """
    
    def __init__(self, base_client):
        """
        Args:
            base_client: Bestehender ATLAS API-Client mit JWT-Support
        """
```

---

## Methoden-Übersicht

### Employers

| Methode | HTTP | Endpoint | Returns |
|---------|------|----------|---------|
| `get_employers()` | GET | /hr/employers | `list[dict]` |
| `get_employer(id)` | GET | /hr/employers/{id} | `dict` |
| `create_employer(data)` | POST | /hr/employers | `dict` |
| `update_employer(id, data)` | PUT | /hr/employers/{id} | `dict` |
| `delete_employer(id)` | DELETE | /hr/employers/{id} | `bool` |

### Credentials

| Methode | HTTP | Endpoint | Returns |
|---------|------|----------|---------|
| `save_credentials(employer_id, creds)` | POST | /hr/employers/{id}/credentials | `dict` |
| `get_credentials(employer_id)` | GET | /hr/employers/{id}/credentials | `dict` |
| `get_credentials_status(employer_id)` | GET | /hr/employers/{id}/credentials/status | `dict` |

### Employees

| Methode | HTTP | Endpoint | Returns |
|---------|------|----------|---------|
| `bulk_sync_employees(employer_id, employees)` | POST | /hr/employees/bulk | `dict` |
| `get_employees(employer_id, **filters)` | GET | /hr/employers/{id}/employees | `dict` |
| `get_employee(employer_id, employee_id)` | GET | /hr/employers/{id}/employees/{eid} | `dict` |

### Snapshots

| Methode | HTTP | Endpoint | Returns |
|---------|------|----------|---------|
| `save_snapshot(employer_id, snapshot_data)` | POST | /hr/snapshots | `dict` |
| `get_snapshots(employer_id)` | GET | /hr/employers/{id}/snapshots | `list[dict]` |
| `get_snapshot(snapshot_id)` | GET | /hr/snapshots/{id} | `dict` |
| `get_latest_snapshot(employer_id)` | GET | /hr/employers/{id}/snapshots/latest | `dict \| None` |
| `delete_snapshot(snapshot_id)` | DELETE | /hr/snapshots/{id} | `bool` |

### Exports

| Methode | HTTP | Endpoint | Returns |
|---------|------|----------|---------|
| `upload_export(employer_id, file_path, metadata)` | POST | /hr/exports | `dict` |
| `get_exports(employer_id)` | GET | /hr/employers/{id}/exports | `list[dict]` |
| `download_export(export_id, save_path)` | GET | /hr/exports/{id}/download | `str` (Dateipfad) |

### Triggers

| Methode | HTTP | Endpoint | Returns |
|---------|------|----------|---------|
| `get_triggers()` | GET | /hr/triggers | `list[dict]` |
| `create_trigger(data)` | POST | /hr/triggers | `dict` |
| `update_trigger(id, data)` | PUT | /hr/triggers/{id} | `dict` |
| `delete_trigger(id)` | DELETE | /hr/triggers/{id} | `bool` |
| `toggle_trigger(id)` | PATCH | /hr/triggers/{id}/toggle | `dict` |
| `exclude_employer(trigger_id, employer_id, exclude)` | PATCH | /hr/triggers/{id}/exclude-employer | `dict` |

### Trigger-Runs

| Methode | HTTP | Endpoint | Returns |
|---------|------|----------|---------|
| `log_trigger_run(data)` | POST | /hr/trigger-runs | `dict` |
| `get_trigger_runs(**filters)` | GET | /hr/trigger-runs | `dict` |

### SMTP

| Methode | HTTP | Endpoint | Returns |
|---------|------|----------|---------|
| `get_smtp_config()` | GET | /hr/smtp-config | `dict` |
| `update_smtp_config(data)` | PUT | /hr/smtp-config | `dict` |
| `get_smtp_config_decrypted()` | GET | /hr/smtp-config/decrypted | `dict` |

---

## Verwendung in Services

### Sync-Service
```python
class SyncService:
    def __init__(self, api_client: HRApiClient):
        self.api = api_client
    
    def sync_employer(self, employer_id: int) -> dict:
        # 1. Credentials holen
        creds = self.api.get_credentials(employer_id)
        employer = self.api.get_employer(employer_id)
        
        # 2. Provider instanziieren
        provider = ProviderFactory.create(employer['provider_key'], creds)
        
        # 3. Mitarbeiter abrufen
        employees, raw = provider.list_employees(only_active=False)
        
        # 4. In DB speichern
        result = self.api.bulk_sync_employees(employer_id, employees)
        
        return result
```

### Delta-Service
```python
class DeltaService:
    def __init__(self, api_client: HRApiClient):
        self.api = api_client
    
    def generate_delta(self, employer_id: int) -> dict:
        # 1. Aktuelle Daten holen (vom Provider)
        sync_result = SyncService(self.api).sync_employer(employer_id)
        
        # 2. Letzten Snapshot holen (von DB)
        latest = self.api.get_latest_snapshot(employer_id)
        
        # 3. Diff berechnen (lokal)
        diff = calculate_diff(current_data, latest)
        
        # 4. Excel generieren (lokal)
        xlsx_path = export_service.generate_scs_excel(diff, employer)
        
        # 5. Neuen Snapshot speichern (in DB)
        self.api.save_snapshot(employer_id, current_hashes)
        
        # 6. Export hochladen (auf Webspace)
        self.api.upload_export(employer_id, xlsx_path, metadata)
        
        # 7. Trigger auswerten (lokal)
        trigger_results = trigger_service.evaluate_and_execute(...)
        
        # 8. Trigger-Runs loggen (in DB)
        for result in trigger_results:
            self.api.log_trigger_run(result)
        
        return diff
```

---

## Threading-Hinweise für PySide6

Alle API-Calls und Provider-Calls MÜSSEN in einem Worker-Thread laufen, nicht im UI-Thread:

```python
class HRWorker(QRunnable):
    """Worker für HR-Operationen in ThreadPool."""
    
    class Signals(QObject):
        finished = Signal(dict)
        error = Signal(str)
        progress = Signal(str)
    
    def __init__(self, task_fn, *args):
        super().__init__()
        self.task_fn = task_fn
        self.args = args
        self.signals = self.Signals()
    
    def run(self):
        try:
            result = self.task_fn(*self.args)
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))
```

**Verwendung:**
```python
worker = HRWorker(delta_service.generate_delta, employer_id)
worker.signals.finished.connect(self.on_delta_complete)
worker.signals.error.connect(self.on_delta_error)
worker.signals.progress.connect(self.status_bar.showMessage)
QThreadPool.globalInstance().start(worker)
```

---

**Erstellt:** 19.02.2026

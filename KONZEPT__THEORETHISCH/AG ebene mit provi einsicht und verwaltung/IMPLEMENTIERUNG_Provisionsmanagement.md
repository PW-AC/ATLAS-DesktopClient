# ACENCIA ATLAS – Provisionsmanagement
## Konkreter Implementierungsplan (Step-by-Step)

**Stand**: 13. Februar 2026
**Voraussetzung**: `PLAN_Provisionsmanagement.md` gelesen und verstanden

Dieser Plan beschreibt **exakt**, wie das Provisionsmanagement in den bestehenden ATLAS-Code integriert wird.
Jeder Schritt enthält konkreten Code, der zu den bestehenden Patterns passt.

---

## Umsetzungsreihenfolge

```
Schritt 1:  DB-Migration (PHP Setup-Script)
Schritt 2:  PHP-API Router + Handler
Schritt 3:  Python API-Client
Schritt 4:  Python Import-Service (VU-Liste + Xempus Parser)
Schritt 5:  Python UI – Provision-Hub (Sidebar + Navigation)
Schritt 6:  Python UI – Mitarbeiter-Panel
Schritt 7:  Python UI – Import-Wizard
Schritt 8:  Python UI – Provisionsübersicht
Schritt 9:  Python UI – GF-Dashboard
Schritt 10: Integration in MainHub (Sidebar-Button)
Schritt 11: i18n-Keys
Schritt 12: Permissions + Activity-Logging
```

---

## Schritt 1: DB-Migration

**Datei**: `BiPro-Webspace Spiegelung Live/setup/019_provision_management.php`

```php
<?php
/**
 * Migration 019: Provisionsmanagement-Tabellen
 * 
 * Erstellt alle Tabellen für das Provisionsmanagement-Modul:
 * - pm_employees (Berater/Mitarbeiter)
 * - pm_contracts (Zentrale Vertragstabelle)
 * - pm_commissions (Provisionseingänge/-ausgänge)
 * - pm_berater_abrechnungen (Berechnete Monatsabrechnungen)
 * - pm_import_batches (Import-Historie)
 * - pm_vermittler_mapping (VU-Name → Berater-Zuordnung)
 * - pm_commission_models (Provisionsmodelle, 1-5 Stück)
 */

require_once __DIR__ . '/../api/lib/db.php';

try {
    $db = Database::getConnection();
    
    // ── 1. Provisionsmodelle ──
    $db->exec("
        CREATE TABLE IF NOT EXISTS pm_commission_models (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            name            VARCHAR(100) NOT NULL,
            description     TEXT NULL,
            commission_rate DECIMAL(5,2) NOT NULL DEFAULT 0,
            is_active       TINYINT(1) NOT NULL DEFAULT 1,
            created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ");
    
    // ── 2. Mitarbeiter/Berater ──
    $db->exec("
        CREATE TABLE IF NOT EXISTS pm_employees (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            user_id         INT NULL,
            name            VARCHAR(200) NOT NULL,
            role            ENUM('consulter','teamleiter','backoffice') NOT NULL DEFAULT 'consulter',
            commission_model_id INT NULL,
            commission_rate_override DECIMAL(5,2) NULL,
            tl_override_rate DECIMAL(5,2) NOT NULL DEFAULT 0,
            tl_override_basis ENUM('berater_anteil','gesamt_courtage') NOT NULL DEFAULT 'berater_anteil',
            teamleiter_id   INT NULL,
            is_active       TINYINT(1) NOT NULL DEFAULT 1,
            notes           TEXT NULL,
            created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_role (role),
            INDEX idx_teamleiter (teamleiter_id),
            INDEX idx_active (is_active),
            INDEX idx_user (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ");
    
    // FK nachträglich (Self-Reference)
    $db->exec("
        ALTER TABLE pm_employees 
        ADD CONSTRAINT fk_pm_emp_tl FOREIGN KEY (teamleiter_id) 
        REFERENCES pm_employees(id) ON DELETE SET NULL
    ");
    
    // ── 3. Import-Batches ──
    $db->exec("
        CREATE TABLE IF NOT EXISTS pm_import_batches (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            source_type     ENUM('vu_liste','xempus') NOT NULL,
            filename        VARCHAR(500) NOT NULL,
            file_hash       VARCHAR(64) NULL,
            total_rows      INT NOT NULL DEFAULT 0,
            imported_rows   INT NOT NULL DEFAULT 0,
            matched_rows    INT NOT NULL DEFAULT 0,
            error_rows      INT NOT NULL DEFAULT 0,
            imported_by     INT NOT NULL,
            notes           TEXT NULL,
            created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_source (source_type),
            INDEX idx_hash (file_hash)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ");
    
    // ── 4. Zentrale Vertragstabelle ──
    $db->exec("
        CREATE TABLE IF NOT EXISTS pm_contracts (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            vsnr            VARCHAR(50) NOT NULL,
            vsnr_alt        VARCHAR(50) NULL,
            versicherer     VARCHAR(200) NULL,
            versicherungsnehmer VARCHAR(300) NULL,
            sparte          VARCHAR(100) NULL,
            tarif           VARCHAR(200) NULL,
            beitrag         DECIMAL(12,2) NULL,
            beginn          DATE NULL,
            berater_id      INT NULL,
            status          ENUM('angebot','offen','abgeschlossen','provision_erhalten',
                                 'provision_fehlt','storniert','rueckbelastung') 
                            NOT NULL DEFAULT 'offen',
            source          ENUM('xempus','vu_liste','manuell') NOT NULL DEFAULT 'manuell',
            xempus_id       VARCHAR(100) NULL,
            import_batch_id INT NULL,
            notes           TEXT NULL,
            created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE INDEX idx_vsnr (vsnr),
            INDEX idx_vsnr_alt (vsnr_alt),
            INDEX idx_berater (berater_id),
            INDEX idx_status (status),
            INDEX idx_versicherer (versicherer),
            FOREIGN KEY (berater_id) REFERENCES pm_employees(id) ON DELETE SET NULL,
            FOREIGN KEY (import_batch_id) REFERENCES pm_import_batches(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ");
    
    // ── 5. Provisionen ──
    $db->exec("
        CREATE TABLE IF NOT EXISTS pm_commissions (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            contract_id     INT NULL,
            vsnr            VARCHAR(50) NOT NULL,
            betrag          DECIMAL(12,2) NOT NULL,
            art             ENUM('ap','bp','rueckbelastung','sonstige') NOT NULL DEFAULT 'ap',
            auszahlungsdatum DATE NULL,
            rate_nummer     INT NULL,
            rate_anzahl     INT NULL,
            versicherer     VARCHAR(200) NULL,
            provisions_basissumme DECIMAL(12,2) NULL,
            vermittler_name VARCHAR(200) NULL,
            berater_id      INT NULL,
            berater_anteil  DECIMAL(12,2) NULL,
            tl_anteil       DECIMAL(12,2) NULL,
            ag_anteil       DECIMAL(12,2) NULL,
            match_status    ENUM('unmatched','auto_matched','manual_matched','ignored') 
                            NOT NULL DEFAULT 'unmatched',
            match_confidence DECIMAL(3,2) NULL,
            import_batch_id INT NULL,
            source_row      INT NULL,
            created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_contract (contract_id),
            INDEX idx_vsnr (vsnr),
            INDEX idx_berater (berater_id),
            INDEX idx_match (match_status),
            INDEX idx_auszahlung (auszahlungsdatum),
            INDEX idx_batch (import_batch_id),
            FOREIGN KEY (contract_id) REFERENCES pm_contracts(id) ON DELETE SET NULL,
            FOREIGN KEY (berater_id) REFERENCES pm_employees(id) ON DELETE SET NULL,
            FOREIGN KEY (import_batch_id) REFERENCES pm_import_batches(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ");
    
    // ── 6. Berater-Abrechnungen ──
    $db->exec("
        CREATE TABLE IF NOT EXISTS pm_berater_abrechnungen (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            abrechnungsmonat DATE NOT NULL,
            berater_id      INT NOT NULL,
            brutto_provision DECIMAL(12,2) NOT NULL DEFAULT 0,
            tl_abzug        DECIMAL(12,2) NOT NULL DEFAULT 0,
            netto_provision  DECIMAL(12,2) NOT NULL DEFAULT 0,
            rueckbelastungen DECIMAL(12,2) NOT NULL DEFAULT 0,
            auszahlung       DECIMAL(12,2) NOT NULL DEFAULT 0,
            tl_override_summe DECIMAL(12,2) NOT NULL DEFAULT 0,
            status          ENUM('berechnet','geprueft','freigegeben','ausgezahlt') 
                            NOT NULL DEFAULT 'berechnet',
            geprueft_von    INT NULL,
            freigegeben_von INT NULL,
            freigegeben_am  DATETIME NULL,
            created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (berater_id) REFERENCES pm_employees(id),
            UNIQUE INDEX idx_monat_berater (abrechnungsmonat, berater_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ");
    
    // ── 7. Vermittler-Mapping ──
    $db->exec("
        CREATE TABLE IF NOT EXISTS pm_vermittler_mapping (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            vermittler_name VARCHAR(200) NOT NULL,
            berater_id      INT NOT NULL,
            created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (berater_id) REFERENCES pm_employees(id) ON DELETE CASCADE,
            UNIQUE INDEX idx_name (vermittler_name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ");
    
    // ── Permissions ──
    $db->exec("
        INSERT IGNORE INTO permissions (permission_key, description) VALUES
        ('provision_manage', 'Provisionsmanagement verwalten'),
        ('provision_view', 'Provisionen einsehen (nur eigene/Team)')
    ");
    
    echo "Migration 019 erfolgreich: Provisionsmanagement-Tabellen erstellt.\n";
    
} catch (PDOException $e) {
    echo "Migration 019 fehlgeschlagen: " . $e->getMessage() . "\n";
    exit(1);
}
```

**Nach Ausführung**: Datei aus `setup/` löschen (wie bei allen Migrations).

---

## Schritt 2: PHP-API

### 2a. Router-Eintrag in `index.php`

Neuer Case im Switch-Block von `index.php`:

```php
case 'pm':
    require_once __DIR__ . '/provision.php';
    // pm/employees, pm/contracts, pm/commissions, pm/import, pm/dashboard, ...
    handleProvisionRequest($action, $method, $id, $parts[3] ?? null);
    break;
```

### 2b. Handler-Datei `provision.php`

**Datei**: `BiPro-Webspace Spiegelung Live/api/provision.php`

```php
<?php
/**
 * Provisionsmanagement API
 * 
 * Endpoints:
 *   GET/POST/PUT/DELETE  /pm/employees[/{id}]
 *   GET/PUT              /pm/contracts[/{id}]
 *   GET/PUT              /pm/commissions[/{id}]
 *   POST                 /pm/import/vu-liste
 *   POST                 /pm/import/xempus
 *   POST                 /pm/import/match
 *   GET                  /pm/import/batches
 *   GET                  /pm/dashboard/summary
 *   GET                  /pm/dashboard/berater/{id}
 *   GET                  /pm/dashboard/unmatched
 *   GET                  /pm/dashboard/missing
 *   GET                  /pm/mappings
 *   POST/DELETE          /pm/mappings[/{id}]
 *   GET/POST             /pm/abrechnungen
 */

require_once __DIR__ . '/lib/db.php';
require_once __DIR__ . '/lib/response.php';
require_once __DIR__ . '/lib/auth.php';
require_once __DIR__ . '/lib/activity_logger.php';

function handleProvisionRequest(
    ?string $action, 
    string $method, 
    ?string $id = null, 
    ?string $sub = null
): void {
    // Auth: Mindestens eingeloggt
    $payload = JWT::requireAuth();
    
    switch ($action) {
        // ── Mitarbeiter ──
        case 'employees':
            handleEmployeesRoute($method, $id, $payload);
            break;
            
        // ── Verträge ──
        case 'contracts':
            if ($id === 'unmatched') {
                handleUnmatchedContracts($payload);
                return;
            }
            handleContractsRoute($method, $id, $payload);
            break;
            
        // ── Provisionen ──
        case 'commissions':
            handleCommissionsRoute($method, $id, $sub, $payload);
            break;
            
        // ── Import ──
        case 'import':
            handleImportRoute($method, $id, $payload);
            break;
            
        // ── Dashboard ──
        case 'dashboard':
            handleDashboardRoute($method, $id, $sub, $payload);
            break;
            
        // ── Vermittler-Mapping ──
        case 'mappings':
            handleMappingsRoute($method, $id, $payload);
            break;
            
        // ── Abrechnungen ──
        case 'abrechnungen':
            handleAbrechnungenRoute($method, $id, $payload);
            break;
            
        default:
            json_error('Unbekannte Provision-Route', 404);
    }
}

// ════════════════════════════════════════════════════════════════
// EMPLOYEES (Mitarbeiter/Berater)
// ════════════════════════════════════════════════════════════════

function handleEmployeesRoute(string $method, ?string $id, array $payload): void {
    requirePermission($payload, 'provision_manage');
    
    if ($id && $method === 'GET') {
        handleGetEmployee((int)$id);
    } elseif (!$id && $method === 'GET') {
        handleListEmployees();
    } elseif (!$id && $method === 'POST') {
        handleCreateEmployee($payload);
    } elseif ($id && $method === 'PUT') {
        handleUpdateEmployee((int)$id, $payload);
    } elseif ($id && $method === 'DELETE') {
        handleDeleteEmployee((int)$id, $payload);
    } else {
        json_error('Methode nicht erlaubt', 405);
    }
}

function handleListEmployees(): void {
    $includeInactive = ($_GET['include_inactive'] ?? '0') === '1';
    $where = $includeInactive ? '' : 'WHERE e.is_active = 1';
    
    $employees = Database::query("
        SELECT e.*, 
               tl.name AS teamleiter_name,
               m.name AS model_name,
               m.commission_rate AS model_rate
        FROM pm_employees e
        LEFT JOIN pm_employees tl ON e.teamleiter_id = tl.id
        LEFT JOIN pm_commission_models m ON e.commission_model_id = m.id
        $where
        ORDER BY e.role DESC, e.name ASC
    ");
    
    json_success(['employees' => $employees]);
}

function handleGetEmployee(int $id): void {
    $employee = Database::queryOne("
        SELECT e.*, tl.name AS teamleiter_name
        FROM pm_employees e
        LEFT JOIN pm_employees tl ON e.teamleiter_id = tl.id
        WHERE e.id = ?
    ", [$id]);
    
    if (!$employee) {
        json_error('Mitarbeiter nicht gefunden', 404);
    }
    
    json_success(['employee' => $employee]);
}

function handleCreateEmployee(array $adminPayload): void {
    $data = get_json_body();
    require_fields($data, ['name', 'role']);
    
    $id = Database::insert('pm_employees', [
        'name'                    => $data['name'],
        'role'                    => $data['role'],
        'user_id'                 => $data['user_id'] ?? null,
        'commission_model_id'     => $data['commission_model_id'] ?? null,
        'commission_rate_override' => $data['commission_rate_override'] ?? null,
        'tl_override_rate'        => $data['tl_override_rate'] ?? 0,
        'teamleiter_id'           => $data['teamleiter_id'] ?? null,
        'notes'                   => $data['notes'] ?? null,
    ]);
    
    ActivityLogger::logAdmin($adminPayload['user_id'], 'pm_employee_created', [
        'employee_id' => $id, 'name' => $data['name']
    ]);
    
    json_success(['id' => $id], 'Mitarbeiter erstellt');
}

function handleUpdateEmployee(int $id, array $adminPayload): void {
    $data = get_json_body();
    
    $allowed = ['name','role','user_id','commission_model_id',
                'commission_rate_override','tl_override_rate',
                'teamleiter_id','is_active','notes'];
    $updates = array_intersect_key($data, array_flip($allowed));
    
    if (empty($updates)) {
        json_error('Keine Felder zum Aktualisieren', 400);
    }
    
    Database::update('pm_employees', $updates, 'id = ?', [$id]);
    
    ActivityLogger::logAdmin($adminPayload['user_id'], 'pm_employee_updated', [
        'employee_id' => $id, 'changes' => array_keys($updates)
    ]);
    
    json_success([], 'Mitarbeiter aktualisiert');
}

function handleDeleteEmployee(int $id, array $adminPayload): void {
    // Soft-Delete
    Database::execute("UPDATE pm_employees SET is_active = 0 WHERE id = ?", [$id]);
    
    ActivityLogger::logAdmin($adminPayload['user_id'], 'pm_employee_deactivated', [
        'employee_id' => $id
    ]);
    
    json_success([], 'Mitarbeiter deaktiviert');
}

// ════════════════════════════════════════════════════════════════
// CONTRACTS (Verträge)
// ════════════════════════════════════════════════════════════════

function handleContractsRoute(string $method, ?string $id, array $payload): void {
    requirePermission($payload, 'provision_manage');
    
    if ($method === 'GET' && !$id) {
        handleListContracts();
    } elseif ($method === 'GET' && $id) {
        handleGetContract((int)$id);
    } elseif ($method === 'PUT' && $id) {
        handleUpdateContract((int)$id, $payload);
    } else {
        json_error('Methode nicht erlaubt', 405);
    }
}

function handleListContracts(): void {
    $filters = [];
    $params = [];
    
    if (!empty($_GET['status'])) {
        $filters[] = 'c.status = ?';
        $params[] = $_GET['status'];
    }
    if (!empty($_GET['berater_id'])) {
        $filters[] = 'c.berater_id = ?';
        $params[] = (int)$_GET['berater_id'];
    }
    if (!empty($_GET['versicherer'])) {
        $filters[] = 'c.versicherer LIKE ?';
        $params[] = '%' . $_GET['versicherer'] . '%';
    }
    
    $where = $filters ? 'WHERE ' . implode(' AND ', $filters) : '';
    $limit = min((int)($_GET['limit'] ?? 500), 2000);
    
    $contracts = Database::query("
        SELECT c.*, e.name AS berater_name,
               (SELECT COUNT(*) FROM pm_commissions WHERE contract_id = c.id) AS provision_count,
               (SELECT COALESCE(SUM(betrag), 0) FROM pm_commissions 
                WHERE contract_id = c.id AND art IN ('ap','bp')) AS provision_summe
        FROM pm_contracts c
        LEFT JOIN pm_employees e ON c.berater_id = e.id
        $where
        ORDER BY c.updated_at DESC
        LIMIT $limit
    ", $params);
    
    json_success(['contracts' => $contracts]);
}

function handleGetContract(int $id): void {
    $contract = Database::queryOne("
        SELECT c.*, e.name AS berater_name
        FROM pm_contracts c
        LEFT JOIN pm_employees e ON c.berater_id = e.id
        WHERE c.id = ?
    ", [$id]);
    
    if (!$contract) {
        json_error('Vertrag nicht gefunden', 404);
    }
    
    // Provisionshistorie dazu laden
    $commissions = Database::query("
        SELECT * FROM pm_commissions 
        WHERE contract_id = ? 
        ORDER BY auszahlungsdatum DESC
    ", [$id]);
    
    $contract['commissions'] = $commissions;
    
    json_success(['contract' => $contract]);
}

function handleUpdateContract(int $id, array $payload): void {
    $data = get_json_body();
    $allowed = ['berater_id','status','notes','vsnr_alt'];
    $updates = array_intersect_key($data, array_flip($allowed));
    
    if (empty($updates)) {
        json_error('Keine Felder zum Aktualisieren', 400);
    }
    
    Database::update('pm_contracts', $updates, 'id = ?', [$id]);
    
    ActivityLogger::logAdmin($payload['user_id'], 'pm_contract_updated', [
        'contract_id' => $id, 'changes' => $updates
    ]);
    
    json_success([], 'Vertrag aktualisiert');
}

function handleUnmatchedContracts(array $payload): void {
    requirePermission($payload, 'provision_manage');
    
    // Provisionen ohne Vertragszuordnung
    $unmatched = Database::query("
        SELECT c.*, 
               (SELECT COUNT(*) FROM pm_contracts 
                WHERE vsnr = c.vsnr OR vsnr_alt = c.vsnr) AS possible_matches
        FROM pm_commissions c
        WHERE c.match_status = 'unmatched'
        ORDER BY c.auszahlungsdatum DESC
        LIMIT 500
    ");
    
    json_success(['unmatched' => $unmatched]);
}

// ════════════════════════════════════════════════════════════════
// COMMISSIONS (Provisionen)
// ════════════════════════════════════════════════════════════════

function handleCommissionsRoute(
    string $method, ?string $id, ?string $sub, array $payload
): void {
    requirePermission($payload, 'provision_manage');
    
    if ($method === 'GET' && !$id) {
        handleListCommissions();
    } elseif ($method === 'PUT' && $id && $sub === 'match') {
        handleMatchCommission((int)$id, $payload);
    } elseif ($method === 'PUT' && $id && $sub === 'ignore') {
        handleIgnoreCommission((int)$id, $payload);
    } elseif ($method === 'POST' && !$id) {
        // Recalculate (Body: { "action": "recalculate" })
        handleRecalculateCommissions($payload);
    } else {
        json_error('Methode nicht erlaubt', 405);
    }
}

function handleListCommissions(): void {
    $filters = [];
    $params = [];
    
    if (!empty($_GET['berater_id'])) {
        $filters[] = 'c.berater_id = ?';
        $params[] = (int)$_GET['berater_id'];
    }
    if (!empty($_GET['match_status'])) {
        $filters[] = 'c.match_status = ?';
        $params[] = $_GET['match_status'];
    }
    if (!empty($_GET['art'])) {
        $filters[] = 'c.art = ?';
        $params[] = $_GET['art'];
    }
    if (!empty($_GET['monat'])) {
        // Format: YYYY-MM
        $filters[] = "DATE_FORMAT(c.auszahlungsdatum, '%Y-%m') = ?";
        $params[] = $_GET['monat'];
    }
    
    $where = $filters ? 'WHERE ' . implode(' AND ', $filters) : '';
    $limit = min((int)($_GET['limit'] ?? 500), 2000);
    
    $commissions = Database::query("
        SELECT c.*, 
               ct.vsnr AS contract_vsnr,
               ct.versicherungsnehmer,
               e.name AS berater_name
        FROM pm_commissions c
        LEFT JOIN pm_contracts ct ON c.contract_id = ct.id
        LEFT JOIN pm_employees e ON c.berater_id = e.id
        $where
        ORDER BY c.auszahlungsdatum DESC
        LIMIT $limit
    ", $params);
    
    json_success(['commissions' => $commissions]);
}

function handleMatchCommission(int $id, array $payload): void {
    $data = get_json_body();
    require_fields($data, ['contract_id']);
    
    $contractId = (int)$data['contract_id'];
    $beraterId = $data['berater_id'] ?? null;
    
    // Vertrag laden um Berater zu ermitteln
    if (!$beraterId) {
        $contract = Database::queryOne(
            "SELECT berater_id FROM pm_contracts WHERE id = ?", [$contractId]
        );
        $beraterId = $contract['berater_id'] ?? null;
    }
    
    // Commission aktualisieren
    Database::update('pm_commissions', [
        'contract_id'     => $contractId,
        'berater_id'      => $beraterId,
        'match_status'    => 'manual_matched',
        'match_confidence' => 1.0,
    ], 'id = ?', [$id]);
    
    // Aufteilung berechnen
    if ($beraterId) {
        recalculateCommissionSplit($id, $beraterId);
    }
    
    // Vertragsstatus aktualisieren
    updateContractStatus($contractId);
    
    ActivityLogger::logAdmin($payload['user_id'], 'pm_commission_matched', [
        'commission_id' => $id, 'contract_id' => $contractId
    ]);
    
    json_success([], 'Provision zugeordnet');
}

function handleIgnoreCommission(int $id, array $payload): void {
    Database::update('pm_commissions', [
        'match_status' => 'ignored'
    ], 'id = ?', [$id]);
    
    json_success([], 'Provision ignoriert');
}

// ════════════════════════════════════════════════════════════════
// PROVISIONS-ENGINE (Berechnungslogik)
// ════════════════════════════════════════════════════════════════

/**
 * Berechnet die Aufteilung einer einzelnen Provision.
 * 
 * Provisionsmodell:
 *   Berater-Anteil brutto = Betrag * (berater.commission_rate / 100)
 *   
 *   Hat Berater TL? → TL-Override-Basis konfigurierbar:
 *     Variante A (berater_anteil): TL = Z% × Berater-Anteil brutto
 *     Variante B (gesamt_courtage): TL = Z% × Gesamt-Courtage (Betrag)
 *   
 *   In BEIDEN Fällen wird der TL-Anteil vom Berater-Anteil ABGEZOGEN.
 *   AG-Anteil = Betrag - Berater-Anteil brutto (immer fix!)
 *   
 *   Beispiel Variante A (1.000€, 40% Berater, 10% TL vom Berater-Anteil):
 *     Berater brutto: 400€, TL: 40€, Berater netto: 360€, AG: 600€
 *   
 *   Beispiel Variante B (1.000€, 40% Berater, 10% TL von Gesamt-Courtage):
 *     Berater brutto: 400€, TL: 100€, Berater netto: 300€, AG: 600€
 */
function recalculateCommissionSplit(int $commissionId, int $beraterId): void {
    // Provision laden
    $commission = Database::queryOne(
        "SELECT betrag FROM pm_commissions WHERE id = ?", [$commissionId]
    );
    if (!$commission) return;
    
    $betrag = (float)$commission['betrag'];
    
    // Berater laden (inkl. effektiven Provisionssatz)
    $berater = Database::queryOne("
        SELECT e.commission_rate_override, e.teamleiter_id,
               m.commission_rate AS model_rate
        FROM pm_employees e
        LEFT JOIN pm_commission_models m ON e.commission_model_id = m.id
        WHERE e.id = ?
    ", [$beraterId]);
    if (!$berater) return;
    
    // Effektiver Satz: Override > Modell-Satz > 0
    $rate = $berater['commission_rate_override'] 
            ?? $berater['model_rate'] 
            ?? 0;
    $rate = (float)$rate;
    
    // Berater-Anteil brutto
    $beraterAnteilBrutto = round($betrag * $rate / 100, 2);
    
    // TL-Override
    $tlAnteil = 0.0;
    if ($berater['teamleiter_id']) {
        $tl = Database::queryOne(
            "SELECT tl_override_rate, tl_override_basis FROM pm_employees WHERE id = ?",
            [$berater['teamleiter_id']]
        );
        if ($tl && (float)$tl['tl_override_rate'] > 0) {
            $tlRate = (float)$tl['tl_override_rate'];
            $tlBasis = $tl['tl_override_basis'] ?? 'berater_anteil';
            
            if ($tlBasis === 'gesamt_courtage') {
                // Variante B: Z% von der gesamten VU-Courtage
                $tlAnteil = round($betrag * $tlRate / 100, 2);
            } else {
                // Variante A (Standard): Z% vom Berater-Anteil
                $tlAnteil = round($beraterAnteilBrutto * $tlRate / 100, 2);
            }
            
            // Sicherheit: TL-Anteil darf nie größer sein als Berater-Anteil
            if ($tlAnteil > $beraterAnteilBrutto) {
                $tlAnteil = $beraterAnteilBrutto;
            }
        }
    }
    
    // Berater netto (brutto minus TL-Override)
    $beraterAnteilNetto = $beraterAnteilBrutto - $tlAnteil;
    
    // AG-Anteil (immer fix: 100% - Y%, unberührt vom TL-Override)
    $agAnteil = $betrag - $beraterAnteilBrutto;
    
    // Speichern
    Database::update('pm_commissions', [
        'berater_anteil' => $beraterAnteilNetto,
        'tl_anteil'      => $tlAnteil,
        'ag_anteil'      => $agAnteil,
    ], 'id = ?', [$commissionId]);
}

/**
 * Aktualisiert den Vertragsstatus basierend auf vorhandenen Provisionen.
 */
function updateContractStatus(int $contractId): void {
    $stats = Database::queryOne("
        SELECT 
            COUNT(*) AS total,
            SUM(CASE WHEN art IN ('ap','bp') THEN 1 ELSE 0 END) AS provisions,
            SUM(CASE WHEN art = 'rueckbelastung' THEN 1 ELSE 0 END) AS rueckbelastungen
        FROM pm_commissions 
        WHERE contract_id = ?
    ", [$contractId]);
    
    if ((int)$stats['rueckbelastungen'] > 0) {
        $newStatus = 'rueckbelastung';
    } elseif ((int)$stats['provisions'] > 0) {
        $newStatus = 'provision_erhalten';
    } else {
        return; // Status nicht ändern wenn keine Provision
    }
    
    Database::execute(
        "UPDATE pm_contracts SET status = ? WHERE id = ? AND status NOT IN ('storniert')",
        [$newStatus, $contractId]
    );
}

/**
 * Alle Provisions-Aufteilungen neu berechnen (z.B. nach Satzänderung).
 */
function handleRecalculateCommissions(array $payload): void {
    $data = get_json_body();
    
    // Optional: Nur für einen Berater
    $beraterId = $data['berater_id'] ?? null;
    
    $where = "WHERE match_status IN ('auto_matched','manual_matched') AND berater_id IS NOT NULL";
    $params = [];
    if ($beraterId) {
        $where .= " AND berater_id = ?";
        $params[] = (int)$beraterId;
    }
    
    $commissions = Database::query(
        "SELECT id, berater_id FROM pm_commissions $where", $params
    );
    
    $count = 0;
    foreach ($commissions as $c) {
        recalculateCommissionSplit((int)$c['id'], (int)$c['berater_id']);
        $count++;
    }
    
    ActivityLogger::logAdmin($payload['user_id'], 'pm_commissions_recalculated', [
        'count' => $count, 'berater_id' => $beraterId
    ]);
    
    json_success(['recalculated' => $count], "$count Provisionen neu berechnet");
}

// ════════════════════════════════════════════════════════════════
// AUTO-MATCHING
// ════════════════════════════════════════════════════════════════

/**
 * Automatisches Matching: VSNR-Abgleich + Vermittler-Zuordnung.
 */
function autoMatchCommissions(?int $batchId = null): array {
    $where = "WHERE match_status = 'unmatched'";
    $params = [];
    if ($batchId) {
        $where .= " AND import_batch_id = ?";
        $params[] = $batchId;
    }
    
    $unmatched = Database::query(
        "SELECT id, vsnr, vermittler_name FROM pm_commissions $where", $params
    );
    
    $stats = ['matched' => 0, 'berater_resolved' => 0, 'still_unmatched' => 0];
    
    foreach ($unmatched as $comm) {
        // 1. VSNR → Vertrag
        $contract = Database::queryOne(
            "SELECT id, berater_id FROM pm_contracts WHERE vsnr = ? OR vsnr_alt = ?",
            [$comm['vsnr'], $comm['vsnr']]
        );
        
        $contractId = $contract ? (int)$contract['id'] : null;
        $beraterId = $contract ? $contract['berater_id'] : null;
        
        // 2. Vermittler → Berater (wenn noch kein Berater)
        if (!$beraterId && $comm['vermittler_name']) {
            $mapping = Database::queryOne(
                "SELECT berater_id FROM pm_vermittler_mapping WHERE vermittler_name = ?",
                [$comm['vermittler_name']]
            );
            if ($mapping) {
                $beraterId = (int)$mapping['berater_id'];
                $stats['berater_resolved']++;
            }
        }
        
        if ($contractId) {
            // Match gefunden
            Database::update('pm_commissions', [
                'contract_id'      => $contractId,
                'berater_id'       => $beraterId,
                'match_status'     => 'auto_matched',
                'match_confidence' => 1.0,
            ], 'id = ?', [(int)$comm['id']]);
            
            // Aufteilung berechnen
            if ($beraterId) {
                recalculateCommissionSplit((int)$comm['id'], (int)$beraterId);
            }
            
            // Vertragsstatus aktualisieren
            updateContractStatus($contractId);
            
            $stats['matched']++;
        } else {
            $stats['still_unmatched']++;
        }
    }
    
    return $stats;
}

// ════════════════════════════════════════════════════════════════
// IMPORT
// ════════════════════════════════════════════════════════════════

function handleImportRoute(string $method, ?string $action, array $payload): void {
    requirePermission($payload, 'provision_manage');
    
    if ($method === 'POST' && $action === 'vu-liste') {
        handleImportVuListe($payload);
    } elseif ($method === 'POST' && $action === 'xempus') {
        handleImportXempus($payload);
    } elseif ($method === 'POST' && $action === 'match') {
        $stats = autoMatchCommissions();
        json_success(['stats' => $stats], 'Auto-Matching abgeschlossen');
    } elseif ($method === 'GET' && $action === 'batches') {
        handleListImportBatches();
    } else {
        json_error('Unbekannte Import-Aktion', 404);
    }
}

/**
 * VU-Provisionsliste importieren.
 * 
 * Erwartet JSON-Body mit:
 *   rows: Array von { vsnr, betrag, art, auszahlungsdatum, versicherer, 
 *                      vermittler_name, rate_nummer, rate_anzahl, provisions_basissumme }
 *   filename: Original-Dateiname
 *   file_hash: SHA256 (Duplikat-Check)
 * 
 * HINWEIS: Die Excel-Datei wird client-seitig (Python) geparst.
 * Der Server erhält bereits strukturierte Daten (JSON).
 * Grund: openpyxl/pandas sind auf PHP Shared Hosting nicht verfügbar.
 */
function handleImportVuListe(array $payload): void {
    $data = get_json_body();
    require_fields($data, ['rows', 'filename']);
    
    // Duplikat-Check
    if (!empty($data['file_hash'])) {
        $existing = Database::queryOne(
            "SELECT id FROM pm_import_batches WHERE file_hash = ?",
            [$data['file_hash']]
        );
        if ($existing) {
            json_error('Diese Datei wurde bereits importiert (Hash-Duplikat)', 409);
        }
    }
    
    // Batch erstellen
    $batchId = Database::insert('pm_import_batches', [
        'source_type' => 'vu_liste',
        'filename'    => $data['filename'],
        'file_hash'   => $data['file_hash'] ?? null,
        'total_rows'  => count($data['rows']),
        'imported_by' => $payload['user_id'],
    ]);
    
    $imported = 0;
    $errors = 0;
    
    foreach ($data['rows'] as $index => $row) {
        try {
            if (empty($row['vsnr']) || !isset($row['betrag'])) {
                $errors++;
                continue;
            }
            
            Database::insert('pm_commissions', [
                'vsnr'                  => normalizeVsnr($row['vsnr']),
                'betrag'                => (float)$row['betrag'],
                'art'                   => $row['art'] ?? 'ap',
                'auszahlungsdatum'      => $row['auszahlungsdatum'] ?? null,
                'versicherer'           => $row['versicherer'] ?? null,
                'vermittler_name'       => $row['vermittler_name'] ?? null,
                'rate_nummer'           => $row['rate_nummer'] ?? null,
                'rate_anzahl'           => $row['rate_anzahl'] ?? null,
                'provisions_basissumme' => $row['provisions_basissumme'] ?? null,
                'import_batch_id'       => $batchId,
                'source_row'            => $index + 1,
                'match_status'          => 'unmatched',
            ]);
            $imported++;
        } catch (\Exception $e) {
            $errors++;
        }
    }
    
    // Batch-Statistik aktualisieren
    Database::update('pm_import_batches', [
        'imported_rows' => $imported,
        'error_rows'    => $errors,
    ], 'id = ?', [$batchId]);
    
    // Auto-Matching für diesen Batch
    $matchStats = autoMatchCommissions($batchId);
    
    Database::update('pm_import_batches', [
        'matched_rows' => $matchStats['matched'],
    ], 'id = ?', [$batchId]);
    
    ActivityLogger::logAdmin($payload['user_id'], 'pm_vu_liste_imported', [
        'batch_id' => $batchId, 'imported' => $imported, 
        'matched' => $matchStats['matched'], 'errors' => $errors
    ]);
    
    json_success([
        'batch_id'  => $batchId,
        'imported'  => $imported,
        'matched'   => $matchStats['matched'],
        'unmatched' => $matchStats['still_unmatched'],
        'errors'    => $errors,
    ], "Import abgeschlossen: $imported importiert, {$matchStats['matched']} zugeordnet");
}

/**
 * Xempus-Export importieren (Verträge/Beratungen).
 * 
 * Gleiche Logik: Python parst Excel, schickt strukturierte JSON-Daten.
 */
function handleImportXempus(array $payload): void {
    $data = get_json_body();
    require_fields($data, ['rows', 'filename']);
    
    // Duplikat-Check
    if (!empty($data['file_hash'])) {
        $existing = Database::queryOne(
            "SELECT id FROM pm_import_batches WHERE file_hash = ?",
            [$data['file_hash']]
        );
        if ($existing) {
            json_error('Diese Datei wurde bereits importiert', 409);
        }
    }
    
    $batchId = Database::insert('pm_import_batches', [
        'source_type' => 'xempus',
        'filename'    => $data['filename'],
        'file_hash'   => $data['file_hash'] ?? null,
        'total_rows'  => count($data['rows']),
        'imported_by' => $payload['user_id'],
    ]);
    
    $imported = 0;
    $updated = 0;
    $errors = 0;
    
    foreach ($data['rows'] as $row) {
        try {
            if (empty($row['vsnr'])) {
                $errors++;
                continue;
            }
            
            $vsnr = normalizeVsnr($row['vsnr']);
            
            // Berater auflösen
            $beraterId = null;
            if (!empty($row['berater'])) {
                $mapping = Database::queryOne(
                    "SELECT berater_id FROM pm_vermittler_mapping WHERE vermittler_name = ?",
                    [$row['berater']]
                );
                $beraterId = $mapping ? (int)$mapping['berater_id'] : null;
            }
            
            // Existiert Vertrag bereits?
            $existing = Database::queryOne(
                "SELECT id FROM pm_contracts WHERE vsnr = ?", [$vsnr]
            );
            
            if ($existing) {
                // Update
                Database::update('pm_contracts', [
                    'versicherer'         => $row['versicherer'] ?? null,
                    'versicherungsnehmer' => $row['versicherungsnehmer'] ?? null,
                    'sparte'              => $row['sparte'] ?? null,
                    'tarif'               => $row['tarif'] ?? null,
                    'beitrag'             => $row['beitrag'] ?? null,
                    'beginn'              => $row['beginn'] ?? null,
                    'status'              => mapXempusStatus($row['status'] ?? ''),
                    'berater_id'          => $beraterId ?? null,
                ], 'id = ?', [(int)$existing['id']]);
                $updated++;
            } else {
                // Insert
                Database::insert('pm_contracts', [
                    'vsnr'                => $vsnr,
                    'versicherer'         => $row['versicherer'] ?? null,
                    'versicherungsnehmer' => $row['versicherungsnehmer'] ?? null,
                    'sparte'              => $row['sparte'] ?? null,
                    'tarif'               => $row['tarif'] ?? null,
                    'beitrag'             => $row['beitrag'] ?? null,
                    'beginn'              => $row['beginn'] ?? null,
                    'berater_id'          => $beraterId,
                    'status'              => mapXempusStatus($row['status'] ?? ''),
                    'source'              => 'xempus',
                    'xempus_id'           => $row['xempus_id'] ?? null,
                    'import_batch_id'     => $batchId,
                ]);
                $imported++;
            }
        } catch (\Exception $e) {
            $errors++;
        }
    }
    
    Database::update('pm_import_batches', [
        'imported_rows' => $imported + $updated,
        'error_rows'    => $errors,
    ], 'id = ?', [$batchId]);
    
    // Re-Matching: Unmatched Provisionen gegen neue Verträge
    $matchStats = autoMatchCommissions();
    
    ActivityLogger::logAdmin($payload['user_id'], 'pm_xempus_imported', [
        'batch_id' => $batchId, 'new' => $imported, 
        'updated' => $updated, 'errors' => $errors,
        'new_matches' => $matchStats['matched']
    ]);
    
    json_success([
        'batch_id'    => $batchId,
        'new'         => $imported,
        'updated'     => $updated,
        'errors'      => $errors,
        'new_matches' => $matchStats['matched'],
    ], "Xempus-Import: $imported neu, $updated aktualisiert");
}

function handleListImportBatches(): void {
    $batches = Database::query("
        SELECT b.*, u.username AS imported_by_name
        FROM pm_import_batches b
        LEFT JOIN users u ON b.imported_by = u.id
        ORDER BY b.created_at DESC
        LIMIT 100
    ");
    
    json_success(['batches' => $batches]);
}

// ════════════════════════════════════════════════════════════════
// DASHBOARD
// ════════════════════════════════════════════════════════════════

function handleDashboardRoute(
    string $method, ?string $action, ?string $sub, array $payload
): void {
    requirePermission($payload, 'provision_manage');
    
    if ($method !== 'GET') {
        json_error('Methode nicht erlaubt', 405);
    }
    
    switch ($action) {
        case 'summary':
            handleDashboardSummary();
            break;
        case 'berater':
            if (!$sub) json_error('Berater-ID fehlt', 400);
            handleDashboardBerater((int)$sub);
            break;
        case 'unmatched':
            handleDashboardUnmatched();
            break;
        case 'missing':
            handleDashboardMissing();
            break;
        case 'storno':
            handleDashboardStorno();
            break;
        default:
            json_error('Unbekannte Dashboard-Route', 404);
    }
}

function handleDashboardSummary(): void {
    $monat = $_GET['monat'] ?? date('Y-m');
    $jahr = substr($monat, 0, 4);
    
    // Monatssummen
    $monatsStats = Database::queryOne("
        SELECT 
            COALESCE(SUM(CASE WHEN art IN ('ap','bp') THEN betrag ELSE 0 END), 0) AS eingang_monat,
            COALESCE(SUM(CASE WHEN art = 'rueckbelastung' THEN betrag ELSE 0 END), 0) AS rueckbelastung_monat,
            COALESCE(SUM(berater_anteil), 0) AS berater_gesamt_monat,
            COALESCE(SUM(tl_anteil), 0) AS tl_gesamt_monat,
            COALESCE(SUM(ag_anteil), 0) AS ag_gesamt_monat
        FROM pm_commissions 
        WHERE DATE_FORMAT(auszahlungsdatum, '%Y-%m') = ?
          AND match_status IN ('auto_matched','manual_matched')
    ", [$monat]);
    
    // YTD
    $ytdStats = Database::queryOne("
        SELECT 
            COALESCE(SUM(CASE WHEN art IN ('ap','bp') THEN betrag ELSE 0 END), 0) AS eingang_ytd,
            COALESCE(SUM(CASE WHEN art = 'rueckbelastung' THEN betrag ELSE 0 END), 0) AS rueckbelastung_ytd
        FROM pm_commissions 
        WHERE YEAR(auszahlungsdatum) = ?
          AND match_status IN ('auto_matched','manual_matched')
    ", [$jahr]);
    
    // Pro Berater (aktueller Monat)
    $perBerater = Database::query("
        SELECT 
            e.id, e.name, e.role,
            COALESCE(SUM(c.berater_anteil), 0) AS berater_netto,
            COALESCE(SUM(c.tl_anteil), 0) AS tl_abzug,
            COALESCE(SUM(CASE WHEN c.art = 'rueckbelastung' THEN c.berater_anteil ELSE 0 END), 0) AS rueckbelastungen,
            COUNT(c.id) AS anzahl_provisionen
        FROM pm_employees e
        LEFT JOIN pm_commissions c ON c.berater_id = e.id 
            AND DATE_FORMAT(c.auszahlungsdatum, '%Y-%m') = ?
            AND c.match_status IN ('auto_matched','manual_matched')
        WHERE e.is_active = 1 AND e.role IN ('consulter','teamleiter')
        GROUP BY e.id
        ORDER BY berater_netto DESC
    ", [$monat]);
    
    // Offene Zuordnungen
    $unmatchedCount = Database::queryOne(
        "SELECT COUNT(*) AS cnt FROM pm_commissions WHERE match_status = 'unmatched'"
    )['cnt'];
    
    // Stornoquote
    $stornoStats = Database::queryOne("
        SELECT 
            COUNT(CASE WHEN status = 'storniert' OR status = 'rueckbelastung' THEN 1 END) AS stornos,
            COUNT(*) AS gesamt
        FROM pm_contracts 
        WHERE status != 'angebot'
    ");
    $stornoquote = $stornoStats['gesamt'] > 0 
        ? round($stornoStats['stornos'] / $stornoStats['gesamt'] * 100, 1) 
        : 0;
    
    json_success([
        'monat'          => $monatsStats,
        'ytd'            => $ytdStats,
        'per_berater'    => $perBerater,
        'unmatched_count' => (int)$unmatchedCount,
        'stornoquote'    => $stornoquote,
    ]);
}

function handleDashboardBerater(int $beraterId): void {
    $monat = $_GET['monat'] ?? date('Y-m');
    
    $berater = Database::queryOne("
        SELECT e.*, tl.name AS teamleiter_name
        FROM pm_employees e
        LEFT JOIN pm_employees tl ON e.teamleiter_id = tl.id
        WHERE e.id = ?
    ", [$beraterId]);
    
    if (!$berater) {
        json_error('Berater nicht gefunden', 404);
    }
    
    // Letzte Provisionen
    $commissions = Database::query("
        SELECT c.*, ct.versicherungsnehmer
        FROM pm_commissions c
        LEFT JOIN pm_contracts ct ON c.contract_id = ct.id
        WHERE c.berater_id = ?
        ORDER BY c.auszahlungsdatum DESC
        LIMIT 50
    ", [$beraterId]);
    
    // Monatssumme
    $monatsSumme = Database::queryOne("
        SELECT 
            COALESCE(SUM(berater_anteil), 0) AS netto,
            COALESCE(SUM(tl_anteil), 0) AS tl_abzug,
            COUNT(*) AS anzahl
        FROM pm_commissions 
        WHERE berater_id = ? 
          AND DATE_FORMAT(auszahlungsdatum, '%Y-%m') = ?
          AND match_status IN ('auto_matched','manual_matched')
    ", [$beraterId, $monat]);
    
    // YTD
    $ytd = Database::queryOne("
        SELECT COALESCE(SUM(berater_anteil), 0) AS netto_ytd
        FROM pm_commissions 
        WHERE berater_id = ? 
          AND YEAR(auszahlungsdatum) = YEAR(CURDATE())
          AND match_status IN ('auto_matched','manual_matched')
    ", [$beraterId]);
    
    // Aktive Verträge
    $vertragCount = Database::queryOne(
        "SELECT COUNT(*) AS cnt FROM pm_contracts WHERE berater_id = ? AND status NOT IN ('storniert','angebot')",
        [$beraterId]
    )['cnt'];
    
    json_success([
        'berater'       => $berater,
        'commissions'   => $commissions,
        'monat'         => $monatsSumme,
        'ytd_netto'     => (float)$ytd['netto_ytd'],
        'vertrag_count' => (int)$vertragCount,
    ]);
}

function handleDashboardUnmatched(): void {
    $unmatched = Database::query("
        SELECT c.id, c.vsnr, c.betrag, c.art, c.auszahlungsdatum, 
               c.versicherer, c.vermittler_name
        FROM pm_commissions c
        WHERE c.match_status = 'unmatched'
        ORDER BY c.auszahlungsdatum DESC
        LIMIT 200
    ");
    
    json_success(['unmatched' => $unmatched]);
}

function handleDashboardMissing(): void {
    // Verträge mit Status 'abgeschlossen' aber ohne Provision
    $missing = Database::query("
        SELECT c.id, c.vsnr, c.versicherer, c.versicherungsnehmer, 
               c.beginn, c.beitrag, e.name AS berater_name,
               DATEDIFF(CURDATE(), c.beginn) AS tage_seit_beginn
        FROM pm_contracts c
        LEFT JOIN pm_employees e ON c.berater_id = e.id
        WHERE c.status = 'abgeschlossen'
          AND NOT EXISTS (
              SELECT 1 FROM pm_commissions cm 
              WHERE cm.contract_id = c.id AND cm.art IN ('ap','bp')
          )
        ORDER BY c.beginn ASC
        LIMIT 200
    ");
    
    json_success(['missing' => $missing]);
}

function handleDashboardStorno(): void {
    $stornos = Database::query("
        SELECT c.*, e.name AS berater_name,
               cm.betrag AS rueckbelastung_betrag, cm.auszahlungsdatum AS rueckbelastung_datum
        FROM pm_contracts c
        LEFT JOIN pm_employees e ON c.berater_id = e.id
        LEFT JOIN pm_commissions cm ON cm.contract_id = c.id AND cm.art = 'rueckbelastung'
        WHERE c.status IN ('storniert','rueckbelastung')
        ORDER BY cm.auszahlungsdatum DESC
        LIMIT 200
    ");
    
    json_success(['stornos' => $stornos]);
}

// ════════════════════════════════════════════════════════════════
// MAPPINGS (Vermittler → Berater)
// ════════════════════════════════════════════════════════════════

function handleMappingsRoute(string $method, ?string $id, array $payload): void {
    requirePermission($payload, 'provision_manage');
    
    if ($method === 'GET') {
        $mappings = Database::query("
            SELECT m.*, e.name AS berater_name
            FROM pm_vermittler_mapping m
            JOIN pm_employees e ON m.berater_id = e.id
            ORDER BY m.vermittler_name
        ");
        json_success(['mappings' => $mappings]);
    } elseif ($method === 'POST') {
        $data = get_json_body();
        require_fields($data, ['vermittler_name', 'berater_id']);
        $mid = Database::insert('pm_vermittler_mapping', [
            'vermittler_name' => $data['vermittler_name'],
            'berater_id'      => (int)$data['berater_id'],
        ]);
        json_success(['id' => $mid], 'Mapping erstellt');
    } elseif ($method === 'DELETE' && $id) {
        Database::execute("DELETE FROM pm_vermittler_mapping WHERE id = ?", [(int)$id]);
        json_success([], 'Mapping gelöscht');
    } else {
        json_error('Methode nicht erlaubt', 405);
    }
}

// ════════════════════════════════════════════════════════════════
// ABRECHNUNGEN
// ════════════════════════════════════════════════════════════════

function handleAbrechnungenRoute(string $method, ?string $id, array $payload): void {
    requirePermission($payload, 'provision_manage');
    
    if ($method === 'GET') {
        $monat = $_GET['monat'] ?? null;
        $where = $monat ? "WHERE a.abrechnungsmonat = ?" : "";
        $params = $monat ? [$monat . '-01'] : [];
        
        $abrechnungen = Database::query("
            SELECT a.*, e.name AS berater_name, e.role
            FROM pm_berater_abrechnungen a
            JOIN pm_employees e ON a.berater_id = e.id
            $where
            ORDER BY a.abrechnungsmonat DESC, e.name ASC
        ", $params);
        
        json_success(['abrechnungen' => $abrechnungen]);
    } elseif ($method === 'POST') {
        $data = get_json_body();
        require_fields($data, ['monat']); // Format: YYYY-MM
        handleGenerateAbrechnung($data['monat'], $payload);
    } else {
        json_error('Methode nicht erlaubt', 405);
    }
}

function handleGenerateAbrechnung(string $monat, array $payload): void {
    $monatDate = $monat . '-01';
    
    // Alle aktiven Berater
    $berater = Database::query(
        "SELECT id, role, teamleiter_id FROM pm_employees WHERE is_active = 1 AND role IN ('consulter','teamleiter')"
    );
    
    $generated = 0;
    
    foreach ($berater as $b) {
        $bId = (int)$b['id'];
        
        // Summen berechnen
        $sums = Database::queryOne("
            SELECT 
                COALESCE(SUM(CASE WHEN art IN ('ap','bp') THEN berater_anteil ELSE 0 END), 0) AS brutto,
                COALESCE(SUM(CASE WHEN art IN ('ap','bp') THEN tl_anteil ELSE 0 END), 0) AS tl_abzug,
                COALESCE(SUM(CASE WHEN art = 'rueckbelastung' THEN berater_anteil ELSE 0 END), 0) AS rueckbelastungen
            FROM pm_commissions 
            WHERE berater_id = ? 
              AND DATE_FORMAT(auszahlungsdatum, '%Y-%m') = ?
              AND match_status IN ('auto_matched','manual_matched')
        ", [$bId, $monat]);
        
        $brutto = (float)$sums['brutto'];
        $tlAbzug = (float)$sums['tl_abzug'];
        $netto = $brutto - $tlAbzug;
        $rueckbelastungen = (float)$sums['rueckbelastungen'];
        $auszahlung = $netto + $rueckbelastungen; // Rückbelastungen sind negativ
        
        // TL Override-Summe (nur für TL)
        $tlOverride = 0;
        if ($b['role'] === 'teamleiter') {
            $tlOv = Database::queryOne("
                SELECT COALESCE(SUM(tl_anteil), 0) AS override_summe
                FROM pm_commissions c
                JOIN pm_employees e ON c.berater_id = e.id
                WHERE e.teamleiter_id = ?
                  AND DATE_FORMAT(c.auszahlungsdatum, '%Y-%m') = ?
                  AND c.match_status IN ('auto_matched','manual_matched')
            ", [$bId, $monat]);
            $tlOverride = (float)$tlOv['override_summe'];
        }
        
        // Upsert
        Database::execute("
            INSERT INTO pm_berater_abrechnungen 
                (abrechnungsmonat, berater_id, brutto_provision, tl_abzug, 
                 netto_provision, rueckbelastungen, auszahlung, tl_override_summe, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'berechnet')
            ON DUPLICATE KEY UPDATE
                brutto_provision = VALUES(brutto_provision),
                tl_abzug = VALUES(tl_abzug),
                netto_provision = VALUES(netto_provision),
                rueckbelastungen = VALUES(rueckbelastungen),
                auszahlung = VALUES(auszahlung),
                tl_override_summe = VALUES(tl_override_summe),
                status = 'berechnet',
                updated_at = CURRENT_TIMESTAMP
        ", [$monatDate, $bId, $brutto, $tlAbzug, $netto, $rueckbelastungen, $auszahlung, $tlOverride]);
        
        $generated++;
    }
    
    ActivityLogger::logAdmin($payload['user_id'], 'pm_abrechnung_generated', [
        'monat' => $monat, 'berater_count' => $generated
    ]);
    
    json_success([
        'generated' => $generated, 'monat' => $monat
    ], "Abrechnung für $monat generiert ($generated Berater)");
}

// ════════════════════════════════════════════════════════════════
// HILFSFUNKTIONEN
// ════════════════════════════════════════════════════════════════

/**
 * VSNR normalisieren für konsistentes Matching.
 * Entfernt Leerzeichen, Bindestriche, führende Nullen.
 */
function normalizeVsnr(string $vsnr): string {
    $vsnr = trim($vsnr);
    $vsnr = str_replace([' ', '-', '/'], '', $vsnr);
    return $vsnr;
}

/**
 * Xempus-Status auf internes Enum mappen.
 */
function mapXempusStatus(string $xempusStatus): string {
    $status = strtolower(trim($xempusStatus));
    
    $mapping = [
        'angebot'        => 'angebot',
        'offen'          => 'offen',
        'in bearbeitung' => 'offen',
        'abgeschlossen'  => 'abgeschlossen',
        'policiert'      => 'abgeschlossen',
        'storniert'      => 'storniert',
        'gekündigt'       => 'storniert',
    ];
    
    return $mapping[$status] ?? 'offen';
}
```

---

## Schritt 3: Python API-Client

**Datei**: `src/api/provision.py`

```python
"""
ACENCIA ATLAS – Provisionsmanagement API Client

Kommuniziert mit den /pm/* Endpoints auf dem Server.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import date

from api.client import APIClient


# ── Datenmodelle ──

@dataclass
class Employee:
    """Mitarbeiter/Berater im Provisionsmanagement."""
    id: int
    name: str
    role: str  # 'consulter', 'teamleiter', 'backoffice'
    commission_model_id: Optional[int] = None
    commission_rate_override: Optional[float] = None
    tl_override_rate: float = 0.0
    tl_override_basis: str = 'berater_anteil'  # 'berater_anteil' oder 'gesamt_courtage'
    teamleiter_id: Optional[int] = None
    teamleiter_name: Optional[str] = None
    user_id: Optional[int] = None
    is_active: bool = True
    notes: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Employee':
        return cls(
            id=int(data.get('id', 0)),
            name=data.get('name', ''),
            role=data.get('role', 'consulter'),
            commission_model_id=data.get('commission_model_id'),
            commission_rate_override=float(data['commission_rate_override']) 
                if data.get('commission_rate_override') else None,
            tl_override_rate=float(data.get('tl_override_rate', 0)),
            tl_override_basis=data.get('tl_override_basis', 'berater_anteil'),
            teamleiter_id=int(data['teamleiter_id']) if data.get('teamleiter_id') else None,
            teamleiter_name=data.get('teamleiter_name'),
            user_id=int(data['user_id']) if data.get('user_id') else None,
            is_active=bool(int(data.get('is_active', 1))),
            notes=data.get('notes'),
        )
    
    @property
    def effective_rate(self) -> float:
        """Effektiver Provisionssatz (Override > Modell)."""
        if self.commission_rate_override is not None:
            return self.commission_rate_override
        return 0.0  # Modell-Rate kommt vom Server


@dataclass
class Commission:
    """Einzelne Provisionsbuchung."""
    id: int
    vsnr: str
    betrag: float
    art: str  # 'ap', 'bp', 'rueckbelastung', 'sonstige'
    auszahlungsdatum: Optional[str] = None
    versicherer: Optional[str] = None
    vermittler_name: Optional[str] = None
    contract_id: Optional[int] = None
    berater_id: Optional[int] = None
    berater_name: Optional[str] = None
    berater_anteil: Optional[float] = None
    tl_anteil: Optional[float] = None
    ag_anteil: Optional[float] = None
    match_status: str = 'unmatched'
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Commission':
        return cls(
            id=int(data.get('id', 0)),
            vsnr=data.get('vsnr', ''),
            betrag=float(data.get('betrag', 0)),
            art=data.get('art', 'ap'),
            auszahlungsdatum=data.get('auszahlungsdatum'),
            versicherer=data.get('versicherer'),
            vermittler_name=data.get('vermittler_name'),
            contract_id=int(data['contract_id']) if data.get('contract_id') else None,
            berater_id=int(data['berater_id']) if data.get('berater_id') else None,
            berater_name=data.get('berater_name'),
            berater_anteil=float(data['berater_anteil']) if data.get('berater_anteil') else None,
            tl_anteil=float(data['tl_anteil']) if data.get('tl_anteil') else None,
            ag_anteil=float(data['ag_anteil']) if data.get('ag_anteil') else None,
            match_status=data.get('match_status', 'unmatched'),
        )


@dataclass 
class Contract:
    """Vertrag aus Xempus oder VU-Liste."""
    id: int
    vsnr: str
    versicherer: Optional[str] = None
    versicherungsnehmer: Optional[str] = None
    sparte: Optional[str] = None
    beitrag: Optional[float] = None
    beginn: Optional[str] = None
    berater_id: Optional[int] = None
    berater_name: Optional[str] = None
    status: str = 'offen'
    provision_count: int = 0
    provision_summe: float = 0.0
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Contract':
        return cls(
            id=int(data.get('id', 0)),
            vsnr=data.get('vsnr', ''),
            versicherer=data.get('versicherer'),
            versicherungsnehmer=data.get('versicherungsnehmer'),
            sparte=data.get('sparte'),
            beitrag=float(data['beitrag']) if data.get('beitrag') else None,
            beginn=data.get('beginn'),
            berater_id=int(data['berater_id']) if data.get('berater_id') else None,
            berater_name=data.get('berater_name'),
            status=data.get('status', 'offen'),
            provision_count=int(data.get('provision_count', 0)),
            provision_summe=float(data.get('provision_summe', 0)),
        )


@dataclass
class DashboardSummary:
    """GF-Dashboard Zusammenfassung."""
    eingang_monat: float = 0.0
    rueckbelastung_monat: float = 0.0
    berater_gesamt_monat: float = 0.0
    ag_gesamt_monat: float = 0.0
    eingang_ytd: float = 0.0
    rueckbelastung_ytd: float = 0.0
    unmatched_count: int = 0
    stornoquote: float = 0.0
    per_berater: List[Dict] = field(default_factory=list)


@dataclass
class ImportResult:
    """Ergebnis eines Imports."""
    batch_id: int
    imported: int = 0
    matched: int = 0
    unmatched: int = 0
    updated: int = 0
    errors: int = 0


# ── API Client ──

class ProvisionAPI:
    """Client für die Provisionsmanagement-API."""
    
    def __init__(self, api_client: APIClient):
        self._client = api_client
    
    # ── Employees ──
    
    def get_employees(self, include_inactive: bool = False) -> List[Employee]:
        params = {'include_inactive': '1'} if include_inactive else None
        resp = self._client.get('pm/employees', params=params)
        return [Employee.from_dict(e) for e in resp.get('employees', [])]
    
    def get_employee(self, employee_id: int) -> Employee:
        resp = self._client.get(f'pm/employees/{employee_id}')
        return Employee.from_dict(resp['employee'])
    
    def create_employee(self, data: Dict[str, Any]) -> int:
        resp = self._client.post('pm/employees', json_data=data)
        return resp['id']
    
    def update_employee(self, employee_id: int, data: Dict[str, Any]) -> None:
        self._client.put(f'pm/employees/{employee_id}', json_data=data)
    
    def delete_employee(self, employee_id: int) -> None:
        self._client.delete(f'pm/employees/{employee_id}')
    
    # ── Contracts ──
    
    def get_contracts(self, **filters) -> List[Contract]:
        resp = self._client.get('pm/contracts', params=filters or None)
        return [Contract.from_dict(c) for c in resp.get('contracts', [])]
    
    def get_contract(self, contract_id: int) -> Contract:
        resp = self._client.get(f'pm/contracts/{contract_id}')
        return Contract.from_dict(resp['contract'])
    
    def update_contract(self, contract_id: int, data: Dict[str, Any]) -> None:
        self._client.put(f'pm/contracts/{contract_id}', json_data=data)
    
    # ── Commissions ──
    
    def get_commissions(self, **filters) -> List[Commission]:
        resp = self._client.get('pm/commissions', params=filters or None)
        return [Commission.from_dict(c) for c in resp.get('commissions', [])]
    
    def match_commission(self, commission_id: int, contract_id: int, 
                         berater_id: Optional[int] = None) -> None:
        data = {'contract_id': contract_id}
        if berater_id:
            data['berater_id'] = berater_id
        self._client.put(f'pm/commissions/{commission_id}/match', json_data=data)
    
    def ignore_commission(self, commission_id: int) -> None:
        self._client.put(f'pm/commissions/{commission_id}/ignore')
    
    def recalculate(self, berater_id: Optional[int] = None) -> int:
        data = {}
        if berater_id:
            data['berater_id'] = berater_id
        resp = self._client.post('pm/commissions', json_data={
            'action': 'recalculate', **data
        })
        return resp.get('recalculated', 0)
    
    # ── Import ──
    
    def import_vu_liste(self, rows: List[Dict], filename: str, 
                        file_hash: Optional[str] = None) -> ImportResult:
        data = {'rows': rows, 'filename': filename}
        if file_hash:
            data['file_hash'] = file_hash
        resp = self._client.post('pm/import/vu-liste', json_data=data)
        return ImportResult(
            batch_id=resp.get('batch_id', 0),
            imported=resp.get('imported', 0),
            matched=resp.get('matched', 0),
            unmatched=resp.get('unmatched', 0),
            errors=resp.get('errors', 0),
        )
    
    def import_xempus(self, rows: List[Dict], filename: str,
                      file_hash: Optional[str] = None) -> ImportResult:
        data = {'rows': rows, 'filename': filename}
        if file_hash:
            data['file_hash'] = file_hash
        resp = self._client.post('pm/import/xempus', json_data=data)
        return ImportResult(
            batch_id=resp.get('batch_id', 0),
            imported=resp.get('new', 0),
            updated=resp.get('updated', 0),
            matched=resp.get('new_matches', 0),
            errors=resp.get('errors', 0),
        )
    
    def trigger_matching(self) -> Dict:
        resp = self._client.post('pm/import/match', json_data={})
        return resp.get('stats', {})
    
    def get_import_batches(self) -> List[Dict]:
        resp = self._client.get('pm/import/batches')
        return resp.get('batches', [])
    
    # ── Dashboard ──
    
    def get_dashboard_summary(self, monat: Optional[str] = None) -> DashboardSummary:
        params = {'monat': monat} if monat else None
        resp = self._client.get('pm/dashboard/summary', params=params)
        
        m = resp.get('monat', {})
        y = resp.get('ytd', {})
        
        return DashboardSummary(
            eingang_monat=float(m.get('eingang_monat', 0)),
            rueckbelastung_monat=float(m.get('rueckbelastung_monat', 0)),
            berater_gesamt_monat=float(m.get('berater_gesamt_monat', 0)),
            ag_gesamt_monat=float(m.get('ag_gesamt_monat', 0)),
            eingang_ytd=float(y.get('eingang_ytd', 0)),
            rueckbelastung_ytd=float(y.get('rueckbelastung_ytd', 0)),
            unmatched_count=int(resp.get('unmatched_count', 0)),
            stornoquote=float(resp.get('stornoquote', 0)),
            per_berater=resp.get('per_berater', []),
        )
    
    def get_berater_detail(self, berater_id: int, 
                           monat: Optional[str] = None) -> Dict:
        params = {'monat': monat} if monat else None
        return self._client.get(f'pm/dashboard/berater/{berater_id}', params=params)
    
    def get_unmatched(self) -> List[Dict]:
        resp = self._client.get('pm/dashboard/unmatched')
        return resp.get('unmatched', [])
    
    def get_missing_provisions(self) -> List[Dict]:
        resp = self._client.get('pm/dashboard/missing')
        return resp.get('missing', [])
    
    # ── Mappings ──
    
    def get_mappings(self) -> List[Dict]:
        resp = self._client.get('pm/mappings')
        return resp.get('mappings', [])
    
    def create_mapping(self, vermittler_name: str, berater_id: int) -> int:
        resp = self._client.post('pm/mappings', json_data={
            'vermittler_name': vermittler_name,
            'berater_id': berater_id,
        })
        return resp.get('id', 0)
    
    def delete_mapping(self, mapping_id: int) -> None:
        self._client.delete(f'pm/mappings/{mapping_id}')
    
    # ── Abrechnungen ──
    
    def get_abrechnungen(self, monat: Optional[str] = None) -> List[Dict]:
        params = {'monat': monat} if monat else None
        resp = self._client.get('pm/abrechnungen', params=params)
        return resp.get('abrechnungen', [])
    
    def generate_abrechnung(self, monat: str) -> Dict:
        return self._client.post('pm/abrechnungen', json_data={'monat': monat})
```

---

## Schritt 4: Python Import-Service

**Datei**: `src/services/provision_import.py`

Dieser Service parst die Excel-Dateien client-seitig und liefert strukturierte Daten an die API.

```python
"""
ACENCIA ATLAS – Import-Service für Provisionsmanagement

Parst VU-Provisionslisten und Xempus-Exporte (Excel/CSV).
Liefert strukturierte Daten, die an die PHP-API gesendet werden.
"""
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

import openpyxl

logger = logging.getLogger(__name__)


@dataclass
class ColumnMapping:
    """Zuordnung von Dateispalten zu Systemfeldern."""
    vsnr: Optional[int] = None
    betrag: Optional[int] = None
    art: Optional[int] = None
    auszahlungsdatum: Optional[int] = None
    versicherer: Optional[int] = None
    vermittler_name: Optional[int] = None
    rate_nummer: Optional[int] = None
    rate_anzahl: Optional[int] = None
    provisions_basissumme: Optional[int] = None
    # Xempus-spezifisch
    status: Optional[int] = None
    berater: Optional[int] = None
    beitrag: Optional[int] = None
    beginn: Optional[int] = None
    sparte: Optional[int] = None
    tarif: Optional[int] = None
    versicherungsnehmer: Optional[int] = None


@dataclass
class ParseResult:
    """Ergebnis des Parsens einer Import-Datei."""
    rows: List[Dict]
    filename: str
    file_hash: str
    total_rows: int
    skipped_rows: int
    column_mapping: ColumnMapping
    warnings: List[str]


# ── VU-Provisionslisten ──

# Bekannte Spaltennamen → Systemfeld-Zuordnung
VU_COLUMN_HINTS = {
    'vsnr': ['vsnr', 'versicherungsscheinnummer', 'vertragsnummer', 
             'neue / zuletzt gültige vsnr', 'vs-nr', 'policennummer'],
    'betrag': ['betrag', 'provisions-betrag', 'provisionsbetrag', 
               'courtage', 'provision', 'nettoprovision'],
    'art': ['art', 'provisionsart', 'buchungsart', 'typ'],
    'auszahlungsdatum': ['auszahlungsdatum', 'auszahlungs-datum', 
                         'datum', 'buchungsdatum', 'valuta'],
    'versicherer': ['versicherer', 'vu', 'gesellschaft', 'vu-name'],
    'vermittler_name': ['vermittler', 'berater', 'makler', 'vermittlername'],
    'rate_nummer': ['ratennummer', 'raten-nummer', 'rate nr', 'rate_nr'],
    'rate_anzahl': ['ratenanzahl', 'raten-anzahl', 'anzahl raten'],
    'provisions_basissumme': ['basissumme', 'provisions-basissumme', 
                              'bemessungsgrundlage', 'bewertungssumme'],
}

# ── Xempus-Spalten ──

XEMPUS_COLUMN_HINTS = {
    'vsnr': ['versicherungsscheinnummer', 'vsnr', 'vertragsnummer'],
    'status': ['status', 'beratungsstatus'],
    'berater': ['berater', 'vermittler', 'betreuer'],
    'versicherer': ['versicherer', 'gesellschaft', 'vu'],
    'beitrag': ['gesamtbeitrag', 'beitrag', 'jahresbeitrag'],
    'beginn': ['beginn', 'vertragsbeginn', 'start'],
    'sparte': ['sparte', 'produktart', 'typ', 'durchführungsweg'],
    'tarif': ['tarif', 'tarifbezeichnung', 'produkt'],
    'versicherungsnehmer': ['versicherungsnehmer', 'kunde', 'name'],
}


def detect_columns(headers: List[str], hints: Dict[str, List[str]]) -> ColumnMapping:
    """Erkennt automatisch die Spaltenzuordnung anhand der Header."""
    mapping = ColumnMapping()
    headers_lower = [h.lower().strip() if h else '' for h in headers]
    
    for field_name, keywords in hints.items():
        for col_idx, header in enumerate(headers_lower):
            if any(kw in header for kw in keywords):
                setattr(mapping, field_name, col_idx)
                break
    
    return mapping


def parse_vu_liste(filepath: str) -> ParseResult:
    """Parst eine VU-Provisionsliste (Excel)."""
    path = Path(filepath)
    file_hash = _compute_file_hash(path)
    
    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    ws = wb.active
    
    rows_iter = ws.iter_rows(values_only=True)
    headers = [str(h) if h else '' for h in next(rows_iter)]
    
    mapping = detect_columns(headers, VU_COLUMN_HINTS)
    
    rows = []
    skipped = 0
    warnings = []
    
    if mapping.vsnr is None:
        warnings.append("VSNR-Spalte nicht automatisch erkannt")
    if mapping.betrag is None:
        warnings.append("Betrags-Spalte nicht automatisch erkannt")
    
    for row_idx, row in enumerate(rows_iter, start=2):
        try:
            vsnr = _safe_str(row, mapping.vsnr)
            betrag = _safe_float(row, mapping.betrag)
            
            if not vsnr or betrag is None:
                skipped += 1
                continue
            
            rows.append({
                'vsnr': vsnr,
                'betrag': betrag,
                'art': _detect_art(_safe_str(row, mapping.art)),
                'auszahlungsdatum': _safe_date(row, mapping.auszahlungsdatum),
                'versicherer': _safe_str(row, mapping.versicherer),
                'vermittler_name': _safe_str(row, mapping.vermittler_name),
                'rate_nummer': _safe_int(row, mapping.rate_nummer),
                'rate_anzahl': _safe_int(row, mapping.rate_anzahl),
                'provisions_basissumme': _safe_float(row, mapping.provisions_basissumme),
            })
        except Exception as e:
            logger.warning(f"Zeile {row_idx} übersprungen: {e}")
            skipped += 1
    
    wb.close()
    
    return ParseResult(
        rows=rows,
        filename=path.name,
        file_hash=file_hash,
        total_rows=len(rows) + skipped,
        skipped_rows=skipped,
        column_mapping=mapping,
        warnings=warnings,
    )


def parse_xempus_export(filepath: str, sheet_name: str = None) -> ParseResult:
    """Parst einen Xempus Advisor Export (Excel, Sheet 'Beratungen')."""
    path = Path(filepath)
    file_hash = _compute_file_hash(path)
    
    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    
    # Sheet finden
    if sheet_name:
        ws = wb[sheet_name]
    else:
        # Automatisch 'Beratungen' suchen
        target = None
        for name in wb.sheetnames:
            if 'beratung' in name.lower():
                target = name
                break
        ws = wb[target] if target else wb.active
    
    rows_iter = ws.iter_rows(values_only=True)
    headers = [str(h) if h else '' for h in next(rows_iter)]
    
    mapping = detect_columns(headers, XEMPUS_COLUMN_HINTS)
    
    rows = []
    skipped = 0
    warnings = []
    
    if mapping.vsnr is None:
        warnings.append("VSNR-Spalte nicht erkannt – bitte manuell zuordnen")
    
    for row_idx, row in enumerate(rows_iter, start=2):
        try:
            vsnr = _safe_str(row, mapping.vsnr)
            if not vsnr:
                skipped += 1
                continue
            
            rows.append({
                'vsnr': vsnr,
                'status': _safe_str(row, mapping.status),
                'berater': _safe_str(row, mapping.berater),
                'versicherer': _safe_str(row, mapping.versicherer),
                'beitrag': _safe_float(row, mapping.beitrag),
                'beginn': _safe_date(row, mapping.beginn),
                'sparte': _safe_str(row, mapping.sparte),
                'tarif': _safe_str(row, mapping.tarif),
                'versicherungsnehmer': _safe_str(row, mapping.versicherungsnehmer),
            })
        except Exception as e:
            logger.warning(f"Zeile {row_idx} übersprungen: {e}")
            skipped += 1
    
    wb.close()
    
    return ParseResult(
        rows=rows,
        filename=path.name,
        file_hash=file_hash,
        total_rows=len(rows) + skipped,
        skipped_rows=skipped,
        column_mapping=mapping,
        warnings=warnings,
    )


def get_sheet_names(filepath: str) -> List[str]:
    """Gibt alle Sheet-Namen einer Excel-Datei zurück."""
    wb = openpyxl.load_workbook(str(filepath), read_only=True)
    names = wb.sheetnames
    wb.close()
    return names


# ── Hilfsfunktionen ──

def _compute_file_hash(path: Path) -> str:
    sha256 = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def _safe_str(row: tuple, col_idx: Optional[int]) -> Optional[str]:
    if col_idx is None or col_idx >= len(row) or row[col_idx] is None:
        return None
    return str(row[col_idx]).strip()


def _safe_float(row: tuple, col_idx: Optional[int]) -> Optional[float]:
    if col_idx is None or col_idx >= len(row) or row[col_idx] is None:
        return None
    val = row[col_idx]
    if isinstance(val, (int, float)):
        return float(val)
    # String-Parsing (deutsch: 1.234,56)
    s = str(val).strip().replace(' ', '')
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None


def _safe_int(row: tuple, col_idx: Optional[int]) -> Optional[int]:
    val = _safe_float(row, col_idx)
    return int(val) if val is not None else None


def _safe_date(row: tuple, col_idx: Optional[int]) -> Optional[str]:
    if col_idx is None or col_idx >= len(row) or row[col_idx] is None:
        return None
    val = row[col_idx]
    if hasattr(val, 'strftime'):  # datetime
        return val.strftime('%Y-%m-%d')
    s = str(val).strip()
    # DD.MM.YYYY → YYYY-MM-DD
    if len(s) == 10 and s[2] == '.' and s[5] == '.':
        return f"{s[6:10]}-{s[3:5]}-{s[0:2]}"
    return s


def _detect_art(art_str: Optional[str]) -> str:
    if not art_str:
        return 'ap'
    art_lower = art_str.lower()
    if 'rück' in art_lower or 'storno' in art_lower or 'belastung' in art_lower:
        return 'rueckbelastung'
    if 'bp' in art_lower or 'bestand' in art_lower or 'folge' in art_lower:
        return 'bp'
    return 'ap'
```

---

## Schritt 5–9: Python UI-Module (Struktur)

Die UI folgt dem gleichen Pattern wie die AdminView:

**Dateistruktur**:
```
src/ui/provision/
    __init__.py
    provision_hub.py        ← Haupt-Widget mit vertikaler Sidebar
    provision_dashboard.py  ← GF-Dashboard (SummaryCards + BeraterTable)
    provision_employees.py  ← Mitarbeiterverwaltung
    provision_import.py     ← Import-Wizard (VU-Liste + Xempus)
    provision_contracts.py  ← Vertragsübersicht
    provision_commissions.py ← Provisionsübersicht + Matching
```

### provision_hub.py (Struktur)

```python
class ProvisionHub(QWidget):
    """Hauptansicht Provisionsmanagement mit vertikaler Sidebar."""
    
    # Signal: Zurück zur Hauptansicht
    back_requested = Signal()
    
    def __init__(self, api_client, auth_api):
        super().__init__()
        self._api = ProvisionAPI(api_client)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        
        # ── Sidebar (links) ──
        sidebar = QFrame()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar.setFixedWidth(220)
        
        # Zurück-Button
        btn_back = QPushButton("‹ Zurück zur App")
        btn_back.clicked.connect(self.back_requested.emit)
        sidebar_layout.addWidget(btn_back)
        
        # Navigation
        self._add_section("ÜBERSICHT")
        self._add_nav(0, "📊", "Dashboard")
        
        self._add_section("VERWALTUNG")
        self._add_nav(1, "👥", "Mitarbeiter")
        self._add_nav(2, "📋", "Verträge")
        self._add_nav(3, "💰", "Provisionen")
        
        self._add_section("DATEN")
        self._add_nav(4, "📥", "Import")
        self._add_nav(5, "🔗", "Vermittler-Mapping")
        self._add_nav(6, "📄", "Abrechnungen")
        
        # ── Content (rechts, QStackedWidget) ──
        self._stack = QStackedWidget()
        # 7 Panels, Lazy Loading wie AdminView
        
        layout.addWidget(sidebar)
        layout.addWidget(self._stack)
```

---

## Schritt 10: Integration in MainHub

### Änderungen in `src/ui/main_hub.py`:

```python
# In _setup_ui(), nach btn_archive und vor btn_gdv:

self.btn_provision = NavButton("💰", texts.NAV_PROVISION)
self.btn_provision.clicked.connect(self._show_provision)
# Nur für Admins sichtbar
if not self._user.is_admin:
    self.btn_provision.setVisible(False)
sidebar_layout.addWidget(self.btn_provision)

# Placeholder im Stack
self._placeholder_provision = self._create_placeholder(texts.NAV_PROVISION)
self.content_stack.addWidget(self._placeholder_provision)  # Nach Archiv-Index
```

```python
# Neue Methode:
def _show_provision(self):
    """Wechselt zur Provisionsmanagement-Ansicht."""
    self._update_nav_buttons(self.btn_provision)
    
    if self._provision_view is None:
        from ui.provision.provision_hub import ProvisionHub
        self._provision_view = ProvisionHub(self._api_client, self._auth_api)
        self._provision_view.back_requested.connect(self._leave_provision)
        
        idx = self.content_stack.indexOf(self._placeholder_provision)
        self.content_stack.removeWidget(self._placeholder_provision)
        self.content_stack.insertWidget(idx, self._provision_view)
    
    # Sidebar verstecken (wie Admin)
    self._sidebar.setVisible(False)
    self.content_stack.setCurrentWidget(self._provision_view)

def _leave_provision(self):
    """Kehrt vom Provisionsmanagement zurück."""
    self._sidebar.setVisible(True)
    self._show_archive()  # oder letzten aktiven Bereich
```

---

## Schritt 11: i18n-Keys

**Neue Keys in `src/i18n/de.py`** (~80–100 Stück):

```python
# ── Provisionsmanagement ──
NAV_PROVISION = "Provision"

# Dashboard
PROVISION_DASHBOARD_TITLE = "Provisionsübersicht"
PROVISION_MONAT = "Provision Monat"
PROVISION_YTD = "Provision YTD"
PROVISION_STORNOQUOTE = "Stornoquote"
PROVISION_PIPELINE = "Pipeline"
PROVISION_UNMATCHED = "Offene Zuordnungen"
PROVISION_MISSING = "Fehlende Provisionen"
PROVISION_BERATER_TABLE = "Berater-Übersicht"
PROVISION_AG_ANTEIL = "AG-Anteil"
PROVISION_BERATER_NETTO = "Berater netto"
PROVISION_TL_ABZUG = "TL-Abzug"
PROVISION_RUECKBELASTUNG = "Rückbelastung"

# Employees
PROVISION_EMP_TITLE = "Mitarbeiterverwaltung"
PROVISION_EMP_NAME = "Name"
PROVISION_EMP_ROLE = "Rolle"
PROVISION_EMP_ROLE_CONSULTER = "Consulter"
PROVISION_EMP_ROLE_TL = "Teamleiter"
PROVISION_EMP_ROLE_BACKOFFICE = "Backoffice"
PROVISION_EMP_RATE = "Provisionssatz (%)"
PROVISION_EMP_TL_OVERRIDE = "TL-Override (%)"
PROVISION_EMP_TL_BASIS = "TL-Override Basis"
PROVISION_EMP_TL_BASIS_BERATER = "Vom Berater-Anteil"
PROVISION_EMP_TL_BASIS_GESAMT = "Von der Gesamt-Courtage"
PROVISION_EMP_TEAM = "Team von"
PROVISION_EMP_ACTIVE = "Aktiv"
PROVISION_EMP_CREATE = "Mitarbeiter anlegen"
PROVISION_EMP_EDIT = "Mitarbeiter bearbeiten"
PROVISION_EMP_DEACTIVATE = "Mitarbeiter deaktivieren"
PROVISION_EMP_DEACTIVATE_CONFIRM = "Mitarbeiter wirklich deaktivieren?"

# Import
PROVISION_IMPORT_TITLE = "Daten importieren"
PROVISION_IMPORT_VU = "VU-Provisionsliste"
PROVISION_IMPORT_XEMPUS = "Xempus-Export"
PROVISION_IMPORT_SELECT_FILE = "Datei auswählen"
PROVISION_IMPORT_COLUMNS = "Spalten-Zuordnung prüfen"
PROVISION_IMPORT_PREVIEW = "Vorschau (erste 20 Zeilen)"
PROVISION_IMPORT_START = "Import starten"
PROVISION_IMPORT_RESULT = "Import abgeschlossen"
PROVISION_IMPORT_ROWS = "{imported} importiert, {matched} zugeordnet, {errors} Fehler"
PROVISION_IMPORT_DUPLICATE = "Diese Datei wurde bereits importiert"
PROVISION_IMPORT_SHEET_SELECT = "Sheet auswählen"
PROVISION_IMPORT_HISTORY = "Import-Historie"

# Matching
PROVISION_MATCH_AUTO = "Auto-Matching"
PROVISION_MATCH_MANUAL = "Manuell zuordnen"
PROVISION_MATCH_IGNORE = "Ignorieren"
PROVISION_MATCH_STATUS_UNMATCHED = "Nicht zugeordnet"
PROVISION_MATCH_STATUS_AUTO = "Automatisch"
PROVISION_MATCH_STATUS_MANUAL = "Manuell"
PROVISION_MATCH_STATUS_IGNORED = "Ignoriert"

# Contracts
PROVISION_CONTRACT_TITLE = "Verträge"
PROVISION_CONTRACT_VSNR = "VSNR"
PROVISION_CONTRACT_VU = "Versicherer"
PROVISION_CONTRACT_VN = "Versicherungsnehmer"
PROVISION_CONTRACT_STATUS = "Status"
PROVISION_CONTRACT_BEITRAG = "Beitrag"

# Commissions
PROVISION_COMM_TITLE = "Provisionen"
PROVISION_COMM_BETRAG = "Betrag"
PROVISION_COMM_ART = "Art"
PROVISION_COMM_ART_AP = "Abschlussprovision"
PROVISION_COMM_ART_BP = "Bestandsprovision"
PROVISION_COMM_ART_RUECK = "Rückbelastung"
PROVISION_COMM_DATUM = "Auszahlungsdatum"

# Mappings
PROVISION_MAPPING_TITLE = "Vermittler-Zuordnung"
PROVISION_MAPPING_VU_NAME = "Name in VU-Liste"
PROVISION_MAPPING_BERATER = "Zugeordneter Berater"
PROVISION_MAPPING_CREATE = "Zuordnung erstellen"
PROVISION_MAPPING_DELETE = "Zuordnung löschen"

# Abrechnungen
PROVISION_ABRECH_TITLE = "Monatsabrechnungen"
PROVISION_ABRECH_GENERATE = "Abrechnung generieren"
PROVISION_ABRECH_MONAT = "Monat"
PROVISION_ABRECH_BRUTTO = "Brutto"
PROVISION_ABRECH_NETTO = "Netto"
PROVISION_ABRECH_AUSZAHLUNG = "Auszahlung"
PROVISION_ABRECH_STATUS = "Status"

# Allgemein
PROVISION_BACK = "Zurück zur App"
PROVISION_RECALCULATE = "Neu berechnen"
PROVISION_FILTER = "Filter"
PROVISION_ALLE = "Alle"
```

---

## Schritt 12: Permissions

### PHP-Seite

Die Migration (Schritt 1) fügt bereits ein:
- `provision_manage` → Vollzugriff (Admin/GF)
- `provision_view` → Nur-Lese (TL: eigenes Team, Berater: nur sich selbst)

### Python-Seite

In `src/api/auth.py` müssen die neuen Permissions in der User-Klasse bekannt sein.
In den UI-Modulen: `has_permission('provision_manage')` vor Schreib-Aktionen prüfen.

---

## Zusammenfassung: Alle neuen Dateien

| # | Datei | Typ | Beschreibung |
|---|-------|-----|--------------|
| 1 | `BiPro-Webspace Spiegelung Live/setup/019_provision_management.php` | PHP | DB-Migration (7 Tabellen) |
| 2 | `BiPro-Webspace Spiegelung Live/api/provision.php` | PHP | API-Handler (~600 Zeilen) |
| 3 | `BiPro-Webspace Spiegelung Live/api/index.php` | PHP | +1 Route-Case |
| 4 | `src/api/provision.py` | Python | API-Client (~250 Zeilen) |
| 5 | `src/services/provision_import.py` | Python | Excel-Parser (~250 Zeilen) |
| 6 | `src/ui/provision/__init__.py` | Python | Package |
| 7 | `src/ui/provision/provision_hub.py` | Python | Haupt-View (~200 Zeilen) |
| 8 | `src/ui/provision/provision_dashboard.py` | Python | GF-Dashboard (~300 Zeilen) |
| 9 | `src/ui/provision/provision_employees.py` | Python | Mitarbeiter-CRUD (~250 Zeilen) |
| 10 | `src/ui/provision/provision_import.py` | Python | Import-Wizard (~350 Zeilen) |
| 11 | `src/ui/provision/provision_contracts.py` | Python | Verträge (~200 Zeilen) |
| 12 | `src/ui/provision/provision_commissions.py` | Python | Provisionen + Matching (~250 Zeilen) |
| 13 | `src/ui/main_hub.py` | Python | +NavButton +2 Methoden (Änderung) |
| 14 | `src/i18n/de.py` | Python | +80–100 Keys (Änderung) |

**Geschätzter Gesamtumfang**: ~2.500–3.000 Zeilen neuer Code

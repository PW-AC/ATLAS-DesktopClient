<?php
/**
 * Migration 028: Xempus Insight Engine - Vollstaendiges Datenmodul
 *
 * 8 neue Tabellen:
 *   1. xempus_import_batches  - Import-Historie + Snapshot-Tracking
 *   2. xempus_raw_rows        - RAW-Layer (revisionssicher, vor Parsing)
 *   3. xempus_employers       - Arbeitgeber (PK = Xempus-UUID)
 *   4. xempus_tariffs         - Tarife pro Arbeitgeber
 *   5. xempus_subsidies       - Zuschüsse pro Arbeitgeber
 *   6. xempus_employees       - Arbeitnehmer
 *   7. xempus_consultations   - Beratungen (alle Spalten)
 *   8. xempus_status_mapping  - Normalisierung von Xempus-Status-Texten
 *   9. xempus_commission_matches - Audit-faehiges Matching zu pm_commissions
 */

require_once __DIR__ . '/../api/config.php';
require_once __DIR__ . '/../api/lib/db.php';

echo "Migration 028: Xempus Insight Engine\n";
echo str_repeat('=', 60) . "\n";

function tableExists028(string $table): bool {
    $safe = preg_replace('/[^a-zA-Z0-9_]/', '', $table);
    $rows = Database::query("SHOW TABLES LIKE '$safe'");
    return !empty($rows);
}

function indexExists028(string $table, string $indexName): bool {
    $safeTable = preg_replace('/[^a-zA-Z0-9_]/', '', $table);
    $safeIndex = preg_replace('/[^a-zA-Z0-9_]/', '', $indexName);
    $rows = Database::query("SHOW INDEX FROM `$safeTable` WHERE Key_name = '$safeIndex'");
    return !empty($rows);
}

try {

    // ══════════════════════════════════════════════════════════════
    // 1. xempus_import_batches
    // ══════════════════════════════════════════════════════════════

    if (!tableExists028('xempus_import_batches')) {
        Database::execute("
            CREATE TABLE xempus_import_batches (
                id INT AUTO_INCREMENT PRIMARY KEY,
                filename VARCHAR(255) NOT NULL,
                imported_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                imported_by INT NULL,
                record_counts JSON NULL,
                snapshot_hash VARCHAR(64) NULL,
                is_active_snapshot BOOLEAN DEFAULT TRUE,
                import_phase ENUM('raw_ingest','normalize','snapshot_update','complete') DEFAULT 'raw_ingest',
                previous_batch_id INT NULL,
                notes TEXT NULL,
                INDEX idx_xib_snapshot_hash (snapshot_hash),
                INDEX idx_xib_active (is_active_snapshot),
                INDEX idx_xib_phase (import_phase)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ");
        echo "[OK] xempus_import_batches erstellt\n";
    } else {
        echo "[SKIP] xempus_import_batches existiert bereits\n";
    }

    // ══════════════════════════════════════════════════════════════
    // 2. xempus_raw_rows (RAW-Layer)
    // ══════════════════════════════════════════════════════════════

    if (!tableExists028('xempus_raw_rows')) {
        Database::execute("
            CREATE TABLE xempus_raw_rows (
                id INT AUTO_INCREMENT PRIMARY KEY,
                import_batch_id INT NOT NULL,
                sheet_name VARCHAR(50) NOT NULL,
                `row_number` INT NOT NULL,
                raw_json JSON NOT NULL,
                row_hash VARCHAR(64) NULL,
                parse_status ENUM('pending','ok','warning','error') DEFAULT 'pending',
                parse_error TEXT NULL,
                parsed_entity_id VARCHAR(36) NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_xrr_batch_sheet (import_batch_id, sheet_name),
                INDEX idx_xrr_parse_status (parse_status),
                INDEX idx_xrr_row_hash (row_hash),
                CONSTRAINT fk_xrr_batch FOREIGN KEY (import_batch_id)
                    REFERENCES xempus_import_batches(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ");
        echo "[OK] xempus_raw_rows erstellt\n";
    } else {
        echo "[SKIP] xempus_raw_rows existiert bereits\n";
    }

    // ══════════════════════════════════════════════════════════════
    // 3. xempus_employers
    // ══════════════════════════════════════════════════════════════

    if (!tableExists028('xempus_employers')) {
        Database::execute("
            CREATE TABLE xempus_employers (
                id VARCHAR(36) NOT NULL PRIMARY KEY,
                name VARCHAR(255) NULL,
                street VARCHAR(255) NULL,
                plz VARCHAR(10) NULL,
                city VARCHAR(100) NULL,
                iban VARCHAR(34) NULL,
                bic VARCHAR(11) NULL,
                tarif_info VARCHAR(100) NULL,
                zuschuss_info VARCHAR(100) NULL,
                raw_json JSON NULL,
                first_seen_batch_id INT NULL,
                last_seen_batch_id INT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_xe_active (is_active),
                INDEX idx_xe_batch (last_seen_batch_id),
                INDEX idx_xe_name (name)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ");
        echo "[OK] xempus_employers erstellt\n";
    } else {
        echo "[SKIP] xempus_employers existiert bereits\n";
    }

    // ══════════════════════════════════════════════════════════════
    // 4. xempus_tariffs
    // ══════════════════════════════════════════════════════════════

    if (!tableExists028('xempus_tariffs')) {
        Database::execute("
            CREATE TABLE xempus_tariffs (
                id VARCHAR(36) NOT NULL PRIMARY KEY,
                employer_id VARCHAR(36) NULL,
                versicherer VARCHAR(200) NULL,
                typ VARCHAR(50) NULL,
                durchfuehrungsweg VARCHAR(50) NULL,
                tarif VARCHAR(200) NULL,
                beantragung VARCHAR(100) NULL,
                gruppenrahmenkollektiv VARCHAR(100) NULL,
                gruppennummer VARCHAR(100) NULL,
                raw_json JSON NULL,
                first_seen_batch_id INT NULL,
                last_seen_batch_id INT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_xt_employer (employer_id),
                INDEX idx_xt_active (is_active)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ");
        echo "[OK] xempus_tariffs erstellt\n";
    } else {
        echo "[SKIP] xempus_tariffs existiert bereits\n";
    }

    // ══════════════════════════════════════════════════════════════
    // 5. xempus_subsidies
    // ══════════════════════════════════════════════════════════════

    if (!tableExists028('xempus_subsidies')) {
        Database::execute("
            CREATE TABLE xempus_subsidies (
                id VARCHAR(36) NOT NULL PRIMARY KEY,
                employer_id VARCHAR(36) NULL,
                bezeichnung VARCHAR(200) NULL,
                art_vl_umwandlung VARCHAR(100) NULL,
                zuschuss_vl_alternativ DECIMAL(12,2) NULL,
                prozent_auf_vl TINYINT(1) NULL,
                zuschuss_prozentual_leq_bbg DECIMAL(5,2) NULL,
                zuschuss_prozentual_gt_bbg DECIMAL(5,2) NULL,
                begrenzung_prozentual VARCHAR(200) NULL,
                fester_zuschuss DECIMAL(12,2) NULL,
                fester_arbg_beitrag DECIMAL(12,2) NULL,
                gestaffelter_zuschuss_aktiv TINYINT(1) NULL,
                gestaffelter_zuschuss TEXT NULL,
                begrenzung_gestaffelt VARCHAR(200) NULL,
                raw_json JSON NULL,
                first_seen_batch_id INT NULL,
                last_seen_batch_id INT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_xs_employer (employer_id),
                INDEX idx_xs_active (is_active)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ");
        echo "[OK] xempus_subsidies erstellt\n";
    } else {
        echo "[SKIP] xempus_subsidies existiert bereits\n";
    }

    // ══════════════════════════════════════════════════════════════
    // 6. xempus_employees
    // ══════════════════════════════════════════════════════════════

    if (!tableExists028('xempus_employees')) {
        Database::execute("
            CREATE TABLE xempus_employees (
                id VARCHAR(36) NOT NULL PRIMARY KEY,
                employer_id VARCHAR(36) NULL,
                zuschuss_id VARCHAR(36) NULL,
                anrede VARCHAR(20) NULL,
                titel VARCHAR(50) NULL,
                name VARCHAR(100) NULL,
                vorname VARCHAR(100) NULL,
                beratungsstatus VARCHAR(100) NULL,
                street VARCHAR(255) NULL,
                plz VARCHAR(10) NULL,
                city VARCHAR(100) NULL,
                bundesland VARCHAR(50) NULL,
                land VARCHAR(50) NULL,
                geburtsdatum DATE NULL,
                telefon VARCHAR(50) NULL,
                mobiltelefon VARCHAR(50) NULL,
                email VARCHAR(200) NULL,
                diensteintritt DATE NULL,
                krankenversicherung VARCHAR(100) NULL,
                bruttolohn DECIMAL(12,2) NULL,
                steuerklasse VARCHAR(10) NULL,
                berufsstellung VARCHAR(100) NULL,
                berufsbezeichnung VARCHAR(200) NULL,
                personalnummer VARCHAR(100) NULL,
                staatsangehoerigkeit VARCHAR(100) NULL,
                familienstand VARCHAR(50) NULL,
                kinder_vorhanden TINYINT(1) NULL,
                kinderfreibetrag DECIMAL(10,2) NULL,
                freibetrag_jaehrlich DECIMAL(12,2) NULL,
                kirchensteuerpflicht TINYINT(1) NULL,
                bemerkung TEXT NULL,
                zuschuss_name VARCHAR(200) NULL,
                raw_json JSON NULL,
                first_seen_batch_id INT NULL,
                last_seen_batch_id INT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_xem_employer (employer_id),
                INDEX idx_xem_status (beratungsstatus),
                INDEX idx_xem_active (is_active),
                INDEX idx_xem_name_lookup (name, vorname, geburtsdatum)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ");
        echo "[OK] xempus_employees erstellt\n";
    } else {
        echo "[SKIP] xempus_employees existiert bereits\n";
    }

    // ══════════════════════════════════════════════════════════════
    // 7. xempus_consultations
    // ══════════════════════════════════════════════════════════════

    if (!tableExists028('xempus_consultations')) {
        Database::execute("
            CREATE TABLE xempus_consultations (
                id VARCHAR(36) NOT NULL PRIMARY KEY,
                employee_id VARCHAR(36) NULL,
                employer_id VARCHAR(36) NULL,
                arbg_name VARCHAR(255) NULL,
                arbn_name VARCHAR(100) NULL,
                arbn_vorname VARCHAR(100) NULL,
                geburtsdatum DATE NULL,
                status VARCHAR(100) NULL,
                beratungsdatum DATE NULL,
                beginn DATE NULL,
                ende DATE NULL,
                arbn_anteil DECIMAL(12,2) NULL,
                davon_vl_arbn DECIMAL(12,2) NULL,
                arbg_anteil DECIMAL(12,2) NULL,
                davon_vl_arbg DECIMAL(12,2) NULL,
                gesamtbeitrag DECIMAL(12,2) NULL,
                entgeltumwandlung_aus VARCHAR(100) NULL,
                versicherungsscheinnummer VARCHAR(100) NULL,
                versicherer VARCHAR(200) NULL,
                typ VARCHAR(50) NULL,
                durchfuehrungsweg VARCHAR(50) NULL,
                tarif VARCHAR(200) NULL,
                beantragung VARCHAR(100) NULL,
                tarifoption VARCHAR(200) NULL,
                gruppennummer VARCHAR(100) NULL,
                buz TINYINT(1) NULL,
                buz_rente DECIMAL(12,2) NULL,
                dauer_jahre INT NULL,
                garantierte_rente DECIMAL(12,2) NULL,
                garantierte_kapitalleistung DECIMAL(12,2) NULL,
                sbu_jahresbruttolohn DECIMAL(12,2) NULL,
                sbu_garantierte_bu_rente DECIMAL(12,2) NULL,
                sbu_gesamte_bu_rente DECIMAL(12,2) NULL,
                rentenalter INT NULL,
                berater VARCHAR(200) NULL,
                beratungstyp VARCHAR(100) NULL,
                zahlungsweise VARCHAR(50) NULL,
                agenturnummer VARCHAR(100) NULL,
                datum_antragsdokument DATE NULL,
                datum_entscheidung DATE NULL,
                datum_elektronische_uebermittlung DATE NULL,
                extra_cols JSON NULL,
                raw_json JSON NULL,
                parse_status ENUM('ok','warning','error') DEFAULT 'ok',
                parse_error TEXT NULL,
                first_seen_batch_id INT NULL,
                last_seen_batch_id INT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_xc_vsnr (versicherungsscheinnummer),
                INDEX idx_xc_employee (employee_id),
                INDEX idx_xc_employer (employer_id),
                INDEX idx_xc_status (status),
                INDEX idx_xc_batch (last_seen_batch_id),
                INDEX idx_xc_employee_status (employee_id, status),
                INDEX idx_xc_berater (berater)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ");
        echo "[OK] xempus_consultations erstellt\n";
    } else {
        echo "[SKIP] xempus_consultations existiert bereits\n";
    }

    // ══════════════════════════════════════════════════════════════
    // 8. xempus_status_mapping
    // ══════════════════════════════════════════════════════════════

    if (!tableExists028('xempus_status_mapping')) {
        Database::execute("
            CREATE TABLE xempus_status_mapping (
                id INT AUTO_INCREMENT PRIMARY KEY,
                raw_status VARCHAR(100) NOT NULL,
                category ENUM('abgeschlossen','beantragt','offen','abgelehnt','nicht_angesprochen') NOT NULL,
                display_label VARCHAR(100) NOT NULL,
                color VARCHAR(20) NOT NULL DEFAULT '#9e9e9e',
                is_active BOOLEAN DEFAULT TRUE,
                UNIQUE INDEX idx_xsm_raw_status (raw_status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ");
        echo "[OK] xempus_status_mapping erstellt\n";

        $seedData = [
            ['Policiert', 'abgeschlossen', 'Abgeschlossen', '#4caf50'],
            ['Abgeschlossen', 'abgeschlossen', 'Abgeschlossen', '#4caf50'],
            ['Police erstellt', 'abgeschlossen', 'Abgeschlossen', '#4caf50'],
            ['Vertrag aktiv', 'abgeschlossen', 'Abgeschlossen', '#4caf50'],
            ['Beantragt', 'beantragt', 'Beantragt', '#2196f3'],
            ['In Bearbeitung', 'beantragt', 'Beantragt', '#2196f3'],
            ['Entscheidung ausstehend', 'offen', 'Offen', '#ff9800'],
            ['Unberaten', 'offen', 'Offen', '#ff9800'],
            ['Angesprochen', 'offen', 'Offen', '#ff9800'],
            ['Beratung erfolgt', 'offen', 'Offen', '#ff9800'],
            ['Nicht gewünscht', 'abgelehnt', 'Abgelehnt', '#f44336'],
            ['Abgelehnt', 'abgelehnt', 'Abgelehnt', '#f44336'],
            ['Nicht angesprochen', 'nicht_angesprochen', 'Nicht angesprochen', '#9e9e9e'],
        ];

        foreach ($seedData as [$raw, $cat, $label, $color]) {
            Database::execute(
                "INSERT IGNORE INTO xempus_status_mapping (raw_status, category, display_label, color) VALUES (?, ?, ?, ?)",
                [$raw, $cat, $label, $color]
            );
        }
        echo "[OK] xempus_status_mapping Seed-Daten eingefuegt (" . count($seedData) . " Eintraege)\n";
    } else {
        $cnt = Database::queryOne("SELECT COUNT(*) as cnt FROM xempus_status_mapping");
        if ((int)($cnt['cnt'] ?? 0) === 0) {
            $seedData = [
                ['Policiert', 'abgeschlossen', 'Abgeschlossen', '#4caf50'],
                ['Abgeschlossen', 'abgeschlossen', 'Abgeschlossen', '#4caf50'],
                ['Police erstellt', 'abgeschlossen', 'Abgeschlossen', '#4caf50'],
                ['Vertrag aktiv', 'abgeschlossen', 'Abgeschlossen', '#4caf50'],
                ['Beantragt', 'beantragt', 'Beantragt', '#2196f3'],
                ['In Bearbeitung', 'beantragt', 'Beantragt', '#2196f3'],
                ['Entscheidung ausstehend', 'offen', 'Offen', '#ff9800'],
                ['Unberaten', 'offen', 'Offen', '#ff9800'],
                ['Angesprochen', 'offen', 'Offen', '#ff9800'],
                ['Beratung erfolgt', 'offen', 'Offen', '#ff9800'],
                ['Nicht gewünscht', 'abgelehnt', 'Abgelehnt', '#f44336'],
                ['Abgelehnt', 'abgelehnt', 'Abgelehnt', '#f44336'],
                ['Nicht angesprochen', 'nicht_angesprochen', 'Nicht angesprochen', '#9e9e9e'],
            ];
            foreach ($seedData as [$raw, $cat, $label, $color]) {
                Database::execute(
                    "INSERT IGNORE INTO xempus_status_mapping (raw_status, category, display_label, color) VALUES (?, ?, ?, ?)",
                    [$raw, $cat, $label, $color]
                );
            }
            echo "[OK] xempus_status_mapping war leer - Seed-Daten eingefuegt (" . count($seedData) . " Eintraege)\n";
        } else {
            echo "[SKIP] xempus_status_mapping existiert bereits mit " . $cnt['cnt'] . " Eintraegen\n";
        }
    }

    // ══════════════════════════════════════════════════════════════
    // 9. xempus_commission_matches
    // ══════════════════════════════════════════════════════════════

    if (!tableExists028('xempus_commission_matches')) {
        Database::execute("
            CREATE TABLE xempus_commission_matches (
                id INT AUTO_INCREMENT PRIMARY KEY,
                commission_id INT NOT NULL,
                xempus_consultation_id VARCHAR(36) NOT NULL,
                match_type ENUM('vsnr_exact','xempus_id','vn_vu_date','manual') NOT NULL,
                confidence DECIMAL(3,2) DEFAULT 1.00,
                matched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                matched_by INT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                override_reason TEXT NULL,
                INDEX idx_xcm_commission (commission_id),
                INDEX idx_xcm_consultation (xempus_consultation_id),
                INDEX idx_xcm_active (is_active)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        ");
        echo "[OK] xempus_commission_matches erstellt\n";
    } else {
        echo "[SKIP] xempus_commission_matches existiert bereits\n";
    }

    // ── pm_commissions: xempus_consultation_id Spalte ──

    $colCheck = Database::query("SHOW COLUMNS FROM pm_commissions LIKE 'xempus_consultation_id'");
    if (empty($colCheck)) {
        Database::execute("
            ALTER TABLE pm_commissions
            ADD COLUMN xempus_consultation_id VARCHAR(36) NULL DEFAULT NULL AFTER contract_id,
            ADD INDEX idx_pmc_xempus_consultation (xempus_consultation_id)
        ");
        echo "[OK] pm_commissions.xempus_consultation_id Spalte hinzugefuegt\n";
    } else {
        echo "[SKIP] pm_commissions.xempus_consultation_id existiert bereits\n";
    }

    echo "\n" . str_repeat('=', 60) . "\n";
    echo "[DONE] Migration 028 abgeschlossen - 9 Tabellen + pm_commissions-Erweiterung.\n";

} catch (\Throwable $e) {
    echo "[ERROR] " . $e->getMessage() . "\n";
    echo "Stack: " . $e->getTraceAsString() . "\n";
    exit(1);
}

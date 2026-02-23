<?php
/**
 * Migration 025: Operationale Indizes fuer Provisionsmanagement
 *
 * Indizes auf haeufig gefilterten/gejointe Spalten in pm_commissions und pm_contracts.
 * Verbessert Query-Performance bei 15.000+ Zeilen erheblich.
 *
 * Zusaetzlich: UNIQUE-Constraint auf pm_berater_abrechnungen fuer Race-Condition-Schutz.
 */

require_once __DIR__ . '/../api/config.php';
require_once __DIR__ . '/../api/lib/db.php';

echo "Migration 025: Operationale PM-Indizes\n";
echo str_repeat('=', 50) . "\n";

function indexExists(string $table, string $indexName): bool {
    $rows = Database::query("SHOW INDEX FROM $table WHERE Key_name = ?", [$indexName]);
    return !empty($rows);
}

try {
    // ── pm_commissions Indizes ──

    $indexes = [
        ['pm_commissions', 'idx_comm_match_status', 'match_status'],
        ['pm_commissions', 'idx_comm_berater_id', 'berater_id'],
        ['pm_commissions', 'idx_comm_contract_id', 'contract_id'],
        ['pm_commissions', 'idx_comm_auszahlungsdatum', 'auszahlungsdatum'],
        ['pm_commissions', 'idx_comm_batch_id', 'import_batch_id'],
        ['pm_commissions', 'idx_comm_status_berater', 'match_status, berater_id'],
    ];

    foreach ($indexes as [$table, $name, $columns]) {
        if (!indexExists($table, $name)) {
            Database::execute("ALTER TABLE $table ADD INDEX $name ($columns)");
            echo "[OK] $table.$name erstellt\n";
        } else {
            echo "[SKIP] $table.$name existiert bereits\n";
        }
    }

    // ── pm_contracts Indizes ──

    $contractIndexes = [
        ['pm_contracts', 'idx_contr_berater_id', 'berater_id'],
        ['pm_contracts', 'idx_contr_status', 'status'],
    ];

    foreach ($contractIndexes as [$table, $name, $columns]) {
        if (!indexExists($table, $name)) {
            Database::execute("ALTER TABLE $table ADD INDEX $name ($columns)");
            echo "[OK] $table.$name erstellt\n";
        } else {
            echo "[SKIP] $table.$name existiert bereits\n";
        }
    }

    // ── UNIQUE-Constraint fuer Abrechnungs-Revision (Race-Condition-Schutz) ──

    if (!indexExists('pm_berater_abrechnungen', 'uq_abr_monat_berater_rev')) {
        Database::execute("ALTER TABLE pm_berater_abrechnungen ADD UNIQUE INDEX uq_abr_monat_berater_rev (abrechnungsmonat, berater_id, revision)");
        echo "[OK] pm_berater_abrechnungen.uq_abr_monat_berater_rev erstellt\n";
    } else {
        echo "[SKIP] pm_berater_abrechnungen.uq_abr_monat_berater_rev existiert bereits\n";
    }

    echo "\n[DONE] Migration 025 abgeschlossen.\n";

} catch (\Throwable $e) {
    echo "[ERROR] " . $e->getMessage() . "\n";
    exit(1);
}

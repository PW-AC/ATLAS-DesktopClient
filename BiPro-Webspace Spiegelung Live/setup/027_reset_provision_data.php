<?php
/**
 * Migration 027: Provisions-Daten Reset (fuer Neuimport)
 *
 * LOESCHT:
 * - pm_commissions (VU-Provisionen)
 * - pm_contracts (Xempus-Vertraege)
 * - pm_import_batches (Import-Historie)
 * - pm_berater_abrechnungen (generierte Abrechnungen)
 *
 * BEHAELT:
 * - pm_employees (Mitarbeiter)
 * - pm_commission_models (Provisionsmodelle)
 * - pm_vermittler_mapping (Vermittler-Zuordnungen)
 *
 * ACHTUNG: Dieses Script loescht ALLE Import-Daten unwiderruflich!
 */

require_once __DIR__ . '/../api/config.php';
require_once __DIR__ . '/../api/lib/db.php';

echo "\n";
echo str_repeat('=', 60) . "\n";
echo "  PROVISION DATA RESET - ACHTUNG: LOESCHT ALLE IMPORT-DATEN!\n";
echo str_repeat('=', 60) . "\n\n";

// Sicherheitsabfrage
echo "Folgende Tabellen werden GELEERT:\n";
echo "  - pm_commissions (VU-Provisionen)\n";
echo "  - pm_contracts (Xempus-Vertraege)\n";
echo "  - pm_import_batches (Import-Historie mit row_hash Duplikatpruefung)\n";
echo "  - pm_berater_abrechnungen (generierte Monatsabrechnungen)\n";
echo "\n";
echo "Folgende Tabellen bleiben ERHALTEN:\n";
echo "  - pm_employees (Mitarbeiter)\n";
echo "  - pm_commission_models (Provisionsmodelle)\n";
echo "  - pm_vermittler_mapping (Vermittler-Zuordnungen)\n";
echo "\n";

// CLI: Bestaetigung verlangen
if (php_sapi_name() === 'cli') {
    echo "Zum Fortfahren 'JA' eingeben: ";
    $handle = fopen("php://stdin", "r");
    $line = trim(fgets($handle));
    fclose($handle);
    if ($line !== 'JA') {
        echo "\nAbgebrochen.\n";
        exit(0);
    }
}

echo "\n[START] Loesche Provisions-Daten...\n\n";

try {
    $pdo = Database::getInstance();

    // ── 1. Zaehle vorher ──
    $countComm = Database::queryOne('SELECT COUNT(*) as cnt FROM pm_commissions')['cnt'];
    $countContr = Database::queryOne('SELECT COUNT(*) as cnt FROM pm_contracts')['cnt'];
    $countBatch = Database::queryOne('SELECT COUNT(*) as cnt FROM pm_import_batches')['cnt'];
    $countAbr = Database::queryOne('SELECT COUNT(*) as cnt FROM pm_berater_abrechnungen')['cnt'];

    echo "Vorher:\n";
    echo "  - pm_commissions: $countComm Zeilen\n";
    echo "  - pm_contracts: $countContr Zeilen\n";
    echo "  - pm_import_batches: $countBatch Zeilen\n";
    echo "  - pm_berater_abrechnungen: $countAbr Zeilen\n\n";

    // ── 2. Foreign Key Checks temporaer deaktivieren ──
    Database::execute('SET FOREIGN_KEY_CHECKS = 0');

    // ── 3. Tabellen leeren (TRUNCATE ist schneller als DELETE) ──
    echo "[1/4] TRUNCATE pm_commissions...\n";
    Database::execute('TRUNCATE TABLE pm_commissions');
    echo "       -> OK\n";

    echo "[2/4] TRUNCATE pm_contracts...\n";
    Database::execute('TRUNCATE TABLE pm_contracts');
    echo "       -> OK\n";

    echo "[3/4] TRUNCATE pm_import_batches...\n";
    Database::execute('TRUNCATE TABLE pm_import_batches');
    echo "       -> OK\n";

    echo "[4/4] TRUNCATE pm_berater_abrechnungen...\n";
    Database::execute('TRUNCATE TABLE pm_berater_abrechnungen');
    echo "       -> OK\n";

    // ── 4. Foreign Key Checks wieder aktivieren ──
    Database::execute('SET FOREIGN_KEY_CHECKS = 1');

    // ── 5. Verifizieren ──
    echo "\nNachher:\n";
    $countComm = Database::queryOne('SELECT COUNT(*) as cnt FROM pm_commissions')['cnt'];
    $countContr = Database::queryOne('SELECT COUNT(*) as cnt FROM pm_contracts')['cnt'];
    $countBatch = Database::queryOne('SELECT COUNT(*) as cnt FROM pm_import_batches')['cnt'];
    $countAbr = Database::queryOne('SELECT COUNT(*) as cnt FROM pm_berater_abrechnungen')['cnt'];
    echo "  - pm_commissions: $countComm Zeilen\n";
    echo "  - pm_contracts: $countContr Zeilen\n";
    echo "  - pm_import_batches: $countBatch Zeilen\n";
    echo "  - pm_berater_abrechnungen: $countAbr Zeilen\n";

    // ── 6. Bestaetigung was erhalten blieb ──
    echo "\nErhalten geblieben:\n";
    $countEmp = Database::queryOne('SELECT COUNT(*) as cnt FROM pm_employees')['cnt'];
    $countMod = Database::queryOne('SELECT COUNT(*) as cnt FROM pm_commission_models')['cnt'];
    $countMap = Database::queryOne('SELECT COUNT(*) as cnt FROM pm_vermittler_mapping')['cnt'];
    echo "  - pm_employees: $countEmp Zeilen\n";
    echo "  - pm_commission_models: $countMod Zeilen\n";
    echo "  - pm_vermittler_mapping: $countMap Zeilen\n";

    echo "\n" . str_repeat('=', 60) . "\n";
    echo "[DONE] Reset abgeschlossen. Sie koennen jetzt neu importieren.\n";
    echo str_repeat('=', 60) . "\n";

} catch (\Throwable $e) {
    // FK Checks zuruecksetzen falls Fehler
    try { Database::execute('SET FOREIGN_KEY_CHECKS = 1'); } catch (\Throwable $e2) {}

    echo "\n[ERROR] " . $e->getMessage() . "\n";
    echo $e->getTraceAsString() . "\n";
    exit(1);
}

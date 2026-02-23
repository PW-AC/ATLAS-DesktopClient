<?php
/**
 * Migration 024: Provision Matching V2
 *
 * - versicherungsnehmer_normalized Spalte in pm_commissions + pm_contracts
 * - Fehlende Indizes auf normalisierten Spalten (JOIN-Performance)
 * - xempus_id Index + UNIQUE Constraint
 * - UNIQUE Constraint auf pm_vermittler_mapping(vermittler_name_normalized)
 * - Backfill: bestehende versicherungsnehmer normalisieren
 */

require_once __DIR__ . '/../api/config.php';
require_once __DIR__ . '/../api/lib/db.php';

echo "Migration 024: Provision Matching V2\n";
echo str_repeat('=', 50) . "\n";

try {
    // ── 1. Neue Spalten ──

    $cols = Database::query("SHOW COLUMNS FROM pm_commissions LIKE 'versicherungsnehmer_normalized'");
    if (empty($cols)) {
        Database::execute("ALTER TABLE pm_commissions ADD COLUMN versicherungsnehmer_normalized VARCHAR(255) NULL AFTER versicherungsnehmer");
        echo "[OK] pm_commissions.versicherungsnehmer_normalized hinzugefuegt\n";
    } else {
        echo "[SKIP] pm_commissions.versicherungsnehmer_normalized existiert bereits\n";
    }

    $cols2 = Database::query("SHOW COLUMNS FROM pm_contracts LIKE 'versicherungsnehmer_normalized'");
    if (empty($cols2)) {
        Database::execute("ALTER TABLE pm_contracts ADD COLUMN versicherungsnehmer_normalized VARCHAR(255) NULL AFTER versicherungsnehmer");
        echo "[OK] pm_contracts.versicherungsnehmer_normalized hinzugefuegt\n";
    } else {
        echo "[SKIP] pm_contracts.versicherungsnehmer_normalized existiert bereits\n";
    }

    // ── 2. Fehlende Indizes auf pm_commissions ──

    $indexes = Database::query("SHOW INDEX FROM pm_commissions WHERE Key_name = 'idx_comm_vsnr_norm'");
    if (empty($indexes)) {
        Database::execute("CREATE INDEX idx_comm_vsnr_norm ON pm_commissions(vsnr_normalized)");
        echo "[OK] Index idx_comm_vsnr_norm erstellt\n";
    } else {
        echo "[SKIP] Index idx_comm_vsnr_norm existiert bereits\n";
    }

    $indexes = Database::query("SHOW INDEX FROM pm_commissions WHERE Key_name = 'idx_comm_vermittler_norm'");
    if (empty($indexes)) {
        Database::execute("CREATE INDEX idx_comm_vermittler_norm ON pm_commissions(vermittler_name_normalized)");
        echo "[OK] Index idx_comm_vermittler_norm erstellt\n";
    } else {
        echo "[SKIP] Index idx_comm_vermittler_norm existiert bereits\n";
    }

    $indexes = Database::query("SHOW INDEX FROM pm_commissions WHERE Key_name = 'idx_comm_row_hash'");
    if (empty($indexes)) {
        Database::execute("CREATE INDEX idx_comm_row_hash ON pm_commissions(row_hash)");
        echo "[OK] Index idx_comm_row_hash erstellt\n";
    } else {
        echo "[SKIP] Index idx_comm_row_hash existiert bereits\n";
    }

    $indexes = Database::query("SHOW INDEX FROM pm_commissions WHERE Key_name = 'idx_comm_vn_norm'");
    if (empty($indexes)) {
        Database::execute("CREATE INDEX idx_comm_vn_norm ON pm_commissions(versicherungsnehmer_normalized)");
        echo "[OK] Index idx_comm_vn_norm erstellt\n";
    } else {
        echo "[SKIP] Index idx_comm_vn_norm existiert bereits\n";
    }

    // ── 3. Fehlende Indizes auf pm_contracts ──

    $indexes = Database::query("SHOW INDEX FROM pm_contracts WHERE Key_name = 'idx_contr_vsnr_norm'");
    if (empty($indexes)) {
        Database::execute("CREATE INDEX idx_contr_vsnr_norm ON pm_contracts(vsnr_normalized)");
        echo "[OK] Index idx_contr_vsnr_norm erstellt\n";
    } else {
        echo "[SKIP] Index idx_contr_vsnr_norm existiert bereits\n";
    }

    $indexes = Database::query("SHOW INDEX FROM pm_contracts WHERE Key_name = 'idx_contr_vsnr_alt_norm'");
    if (empty($indexes)) {
        Database::execute("CREATE INDEX idx_contr_vsnr_alt_norm ON pm_contracts(vsnr_alt_normalized)");
        echo "[OK] Index idx_contr_vsnr_alt_norm erstellt\n";
    } else {
        echo "[SKIP] Index idx_contr_vsnr_alt_norm existiert bereits\n";
    }

    $indexes = Database::query("SHOW INDEX FROM pm_contracts WHERE Key_name = 'idx_contr_vn_norm'");
    if (empty($indexes)) {
        Database::execute("CREATE INDEX idx_contr_vn_norm ON pm_contracts(versicherungsnehmer_normalized)");
        echo "[OK] Index idx_contr_vn_norm erstellt\n";
    } else {
        echo "[SKIP] Index idx_contr_vn_norm existiert bereits\n";
    }

    // ── 4. xempus_id Index + UNIQUE ──

    $indexes = Database::query("SHOW INDEX FROM pm_contracts WHERE Key_name = 'idx_contr_xempus_id'");
    if (empty($indexes)) {
        Database::execute("CREATE INDEX idx_contr_xempus_id ON pm_contracts(xempus_id)");
        echo "[OK] Index idx_contr_xempus_id erstellt\n";
    } else {
        echo "[SKIP] Index idx_contr_xempus_id existiert bereits\n";
    }

    // UNIQUE auf xempus_id: Nur setzen wenn keine Duplikate existieren
    $indexes = Database::query("SHOW INDEX FROM pm_contracts WHERE Key_name = 'idx_contr_xempus_id_unique'");
    if (empty($indexes)) {
        $dups = Database::queryOne("
            SELECT COUNT(*) AS cnt FROM (
                SELECT xempus_id FROM pm_contracts
                WHERE xempus_id IS NOT NULL AND xempus_id != ''
                GROUP BY xempus_id HAVING COUNT(*) > 1
            ) t
        ");
        if ((int)($dups['cnt'] ?? 0) === 0) {
            Database::execute("ALTER TABLE pm_contracts ADD UNIQUE INDEX idx_contr_xempus_id_unique (xempus_id)");
            echo "[OK] UNIQUE Index idx_contr_xempus_id_unique erstellt\n";
        } else {
            echo "[WARN] Duplikate bei xempus_id gefunden -- UNIQUE Constraint nicht gesetzt!\n";
        }
    } else {
        echo "[SKIP] Index idx_contr_xempus_id_unique existiert bereits\n";
    }

    // ── 5. UNIQUE Constraint auf pm_vermittler_mapping ──

    $indexes = Database::query("SHOW INDEX FROM pm_vermittler_mapping WHERE Key_name = 'idx_mapping_norm_unique'");
    if (empty($indexes)) {
        $dups = Database::queryOne("
            SELECT COUNT(*) AS cnt FROM (
                SELECT vermittler_name_normalized FROM pm_vermittler_mapping
                WHERE vermittler_name_normalized IS NOT NULL AND vermittler_name_normalized != ''
                GROUP BY vermittler_name_normalized HAVING COUNT(*) > 1
            ) t
        ");
        if ((int)($dups['cnt'] ?? 0) === 0) {
            Database::execute("ALTER TABLE pm_vermittler_mapping ADD UNIQUE INDEX idx_mapping_norm_unique (vermittler_name_normalized)");
            echo "[OK] UNIQUE Index idx_mapping_norm_unique erstellt\n";
        } else {
            echo "[WARN] Duplikate bei vermittler_name_normalized -- UNIQUE Constraint nicht gesetzt!\n";
        }
    } else {
        echo "[SKIP] Index idx_mapping_norm_unique existiert bereits\n";
    }

    // ── 6. Backfill: versicherungsnehmer_normalized ──

    echo "\nBackfill: versicherungsnehmer_normalized...\n";

    // PHP-seitige Normalisierung
    function normalizeForDbMigration(string $name): string {
        $name = mb_strtolower(trim($name));
        $name = str_replace(['ä','ö','ü','ß'], ['ae','oe','ue','ss'], $name);
        $name = preg_replace('/\(([^)]+)\)/', ' $1', $name);
        $name = preg_replace('/[^a-z0-9\s]/', ' ', $name);
        $name = preg_replace('/\s+/', ' ', trim($name));
        return $name;
    }

    $rows = Database::query("SELECT id, versicherungsnehmer FROM pm_commissions WHERE versicherungsnehmer IS NOT NULL AND versicherungsnehmer != '' AND versicherungsnehmer_normalized IS NULL");
    $updated = 0;
    foreach ($rows as $r) {
        $norm = normalizeForDbMigration($r['versicherungsnehmer']);
        Database::execute("UPDATE pm_commissions SET versicherungsnehmer_normalized = ? WHERE id = ?", [$norm, (int)$r['id']]);
        $updated++;
    }
    echo "[OK] pm_commissions: $updated Zeilen normalisiert\n";

    $rows2 = Database::query("SELECT id, versicherungsnehmer FROM pm_contracts WHERE versicherungsnehmer IS NOT NULL AND versicherungsnehmer != '' AND versicherungsnehmer_normalized IS NULL");
    $updated2 = 0;
    foreach ($rows2 as $r) {
        $norm = normalizeForDbMigration($r['versicherungsnehmer']);
        Database::execute("UPDATE pm_contracts SET versicherungsnehmer_normalized = ? WHERE id = ?", [$norm, (int)$r['id']]);
        $updated2++;
    }
    echo "[OK] pm_contracts: $updated2 Zeilen normalisiert\n";

    echo "\n" . str_repeat('=', 50) . "\n";
    echo "Migration 024 abgeschlossen.\n";

} catch (Exception $e) {
    echo "[ERROR] " . $e->getMessage() . "\n";
    exit(1);
}

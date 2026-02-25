<?php
/**
 * Migration 035: Release Gate Engine - Status-Erweiterung
 * 
 * Erweitert die releases-Tabelle um Gate-Engine-Felder:
 * - Status ENUM wird um pending/validated/blocked erweitert
 * - gate_report (JSON) speichert Validierungsergebnisse
 * - validated_at Zeitstempel der letzten Validierung
 * - required_schema erwartete Schema-Version
 * - smoke_test_report (JSON) optionaler Smoke-Test-Report
 */

require_once __DIR__ . '/../api/lib/db.php';
require_once __DIR__ . '/../api/config.php';

try {
    $pdo = Database::getInstance();

    // 1. Status-ENUM erweitern
    $col = $pdo->query("SHOW COLUMNS FROM releases LIKE 'status'")->fetch();
    if ($col && strpos($col['Type'], 'pending') === false) {
        $pdo->exec("ALTER TABLE releases MODIFY COLUMN status ENUM('pending','validated','blocked','active','mandatory','deprecated','withdrawn') NOT NULL DEFAULT 'pending'");
        echo "Status-ENUM erweitert (pending, validated, blocked hinzugefuegt).\n";
    } else {
        echo "Status-ENUM bereits aktuell.\n";
    }

    // 2. gate_report Spalte
    $cols = $pdo->query("SHOW COLUMNS FROM releases LIKE 'gate_report'")->fetchAll();
    if (empty($cols)) {
        $pdo->exec("ALTER TABLE releases ADD COLUMN gate_report JSON NULL AFTER sha256");
        echo "Spalte gate_report hinzugefuegt.\n";
    } else {
        echo "Spalte gate_report existiert bereits.\n";
    }

    // 3. validated_at Spalte
    $cols = $pdo->query("SHOW COLUMNS FROM releases LIKE 'validated_at'")->fetchAll();
    if (empty($cols)) {
        $pdo->exec("ALTER TABLE releases ADD COLUMN validated_at DATETIME NULL AFTER gate_report");
        echo "Spalte validated_at hinzugefuegt.\n";
    } else {
        echo "Spalte validated_at existiert bereits.\n";
    }

    // 4. required_schema Spalte
    $cols = $pdo->query("SHOW COLUMNS FROM releases LIKE 'required_schema'")->fetchAll();
    if (empty($cols)) {
        $pdo->exec("ALTER TABLE releases ADD COLUMN required_schema VARCHAR(100) NULL AFTER validated_at");
        echo "Spalte required_schema hinzugefuegt.\n";
    } else {
        echo "Spalte required_schema existiert bereits.\n";
    }

    // 5. smoke_test_report Spalte
    $cols = $pdo->query("SHOW COLUMNS FROM releases LIKE 'smoke_test_report'")->fetchAll();
    if (empty($cols)) {
        $pdo->exec("ALTER TABLE releases ADD COLUMN smoke_test_report JSON NULL AFTER required_schema");
        echo "Spalte smoke_test_report hinzugefuegt.\n";
    } else {
        echo "Spalte smoke_test_report existiert bereits.\n";
    }

    // Migration registrieren
    Database::execute(
        "INSERT IGNORE INTO schema_migrations (migration_name) VALUES (?)",
        [basename(__FILE__, '.php')]
    );

    echo "\nMigration 035 erfolgreich abgeschlossen.\n";

} catch (Exception $e) {
    echo "FEHLER: " . $e->getMessage() . "\n";
    exit(1);
}

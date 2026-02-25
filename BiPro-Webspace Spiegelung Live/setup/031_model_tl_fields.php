<?php
/**
 * Migration 031: TL-Rate und TL-Basis in pm_commission_models
 * 
 * Erweitert Provisionsmodelle um Teamleiter-Felder,
 * damit beim Zuweisen eines Modells fast alle Raten
 * automatisch uebernommen werden.
 */

require_once __DIR__ . '/../api/lib/db.php';
require_once __DIR__ . '/../api/config.php';

try {
    $pdo = Database::getInstance();

    // tl_rate: TL-Override-Rate im Modell (NULL = nicht definiert)
    $cols = $pdo->query("SHOW COLUMNS FROM pm_commission_models LIKE 'tl_rate'")->fetchAll();
    if (empty($cols)) {
        $pdo->exec("ALTER TABLE pm_commission_models ADD COLUMN tl_rate DECIMAL(5,1) NULL DEFAULT NULL AFTER commission_rate");
        echo "Spalte tl_rate hinzugefuegt.\n";
    } else {
        echo "Spalte tl_rate existiert bereits.\n";
    }

    // tl_basis: TL-Berechnungsbasis im Modell (NULL = nicht definiert)
    $cols = $pdo->query("SHOW COLUMNS FROM pm_commission_models LIKE 'tl_basis'")->fetchAll();
    if (empty($cols)) {
        $pdo->exec("ALTER TABLE pm_commission_models ADD COLUMN tl_basis VARCHAR(20) NULL DEFAULT NULL AFTER tl_rate");
        echo "Spalte tl_basis hinzugefuegt.\n";
    } else {
        echo "Spalte tl_basis existiert bereits.\n";
    }

    echo "\nMigration 031 erfolgreich abgeschlossen.\n";

} catch (Exception $e) {
    echo "FEHLER: " . $e->getMessage() . "\n";
    exit(1);
}

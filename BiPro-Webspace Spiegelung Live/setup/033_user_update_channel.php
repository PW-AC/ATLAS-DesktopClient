<?php
/**
 * Migration 033: update_channel Spalte in users-Tabelle
 * 
 * Ermoeglicht server-seitige Steuerung des Release-Channels
 * pro User (stable/beta/dev). Default: stable.
 */

require_once __DIR__ . '/../api/lib/db.php';
require_once __DIR__ . '/../api/config.php';

try {
    $pdo = Database::getInstance();

    $cols = $pdo->query("SHOW COLUMNS FROM users LIKE 'update_channel'")->fetchAll();
    if (empty($cols)) {
        $pdo->exec("ALTER TABLE users ADD COLUMN update_channel ENUM('stable','beta','dev') NOT NULL DEFAULT 'stable' AFTER account_type");
        echo "Spalte update_channel hinzugefuegt.\n";
    } else {
        echo "Spalte update_channel existiert bereits.\n";
    }

    echo "\nMigration 033 erfolgreich abgeschlossen.\n";

} catch (Exception $e) {
    echo "FEHLER: " . $e->getMessage() . "\n";
    exit(1);
}

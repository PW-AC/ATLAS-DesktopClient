<?php
/**
 * Migration 032: Channel 'internal' -> 'dev' umbenennen
 * 
 * Aendert den Channel-Namen in der releases-Tabelle
 * und passt den ENUM-Typ an.
 */

require_once __DIR__ . '/../api/lib/db.php';
require_once __DIR__ . '/../api/config.php';

try {
    $pdo = Database::getInstance();

    // Pruefen ob noch 'internal' Eintraege existieren
    $count = $pdo->query("SELECT COUNT(*) FROM releases WHERE channel = 'internal'")->fetchColumn();
    
    if ($count > 0) {
        $pdo->exec("UPDATE releases SET channel = 'dev' WHERE channel = 'internal'");
        echo "{$count} Release(s) von 'internal' auf 'dev' umgestellt.\n";
    } else {
        echo "Keine Releases mit Channel 'internal' gefunden.\n";
    }

    // ENUM-Typ anpassen (falls noetig)
    $col = $pdo->query("SHOW COLUMNS FROM releases LIKE 'channel'")->fetch();
    if ($col && strpos($col['Type'], 'internal') !== false) {
        $pdo->exec("ALTER TABLE releases MODIFY COLUMN channel ENUM('stable','beta','dev') NOT NULL DEFAULT 'stable'");
        echo "ENUM-Typ aktualisiert: 'internal' durch 'dev' ersetzt.\n";
    } else {
        echo "ENUM-Typ bereits aktuell oder kein ENUM.\n";
    }

    echo "\nMigration 032 erfolgreich abgeschlossen.\n";

} catch (Exception $e) {
    echo "FEHLER: " . $e->getMessage() . "\n";
    exit(1);
}

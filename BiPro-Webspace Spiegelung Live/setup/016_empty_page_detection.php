<?php
/**
 * Migration 016: Leere-Seiten-Erkennung
 * 
 * Fuegt zwei neue Spalten zur documents-Tabelle hinzu:
 * - empty_page_count: Anzahl der als leer erkannten Seiten (NULL = nicht geprueft)
 * - total_page_count: Gesamtseitenzahl des PDFs (NULL = nicht geprueft)
 */

require_once __DIR__ . '/../api/config.php';

try {
    $pdo = new PDO(
        'mysql:host=' . DB_HOST . ';dbname=' . DB_NAME . ';charset=utf8mb4',
        DB_USER,
        DB_PASS,
        [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]
    );

    echo "=== Migration 016: Leere-Seiten-Erkennung ===\n\n";

    $stmt = $pdo->query("SHOW COLUMNS FROM documents LIKE 'empty_page_count'");
    if ($stmt->rowCount() > 0) {
        echo "[SKIP] Spalte 'empty_page_count' existiert bereits.\n";
    } else {
        $pdo->exec("ALTER TABLE documents ADD COLUMN empty_page_count INT NULL DEFAULT NULL AFTER display_color");
        echo "[OK] Spalte 'empty_page_count' hinzugefuegt.\n";
    }

    $stmt = $pdo->query("SHOW COLUMNS FROM documents LIKE 'total_page_count'");
    if ($stmt->rowCount() > 0) {
        echo "[SKIP] Spalte 'total_page_count' existiert bereits.\n";
    } else {
        $pdo->exec("ALTER TABLE documents ADD COLUMN total_page_count INT NULL DEFAULT NULL AFTER empty_page_count");
        echo "[OK] Spalte 'total_page_count' hinzugefuegt.\n";
    }

    echo "\n=== Migration 016 abgeschlossen ===\n";

} catch (PDOException $e) {
    echo "[FEHLER] " . $e->getMessage() . "\n";
    exit(1);
}

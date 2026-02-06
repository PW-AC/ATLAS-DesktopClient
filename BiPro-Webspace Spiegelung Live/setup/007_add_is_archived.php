<?php
/**
 * Migration: Archivierungs-Funktion
 * 
 * Fuegt Spalte hinzu fuer:
 * - is_archived: Ob das Dokument archiviert wurde (nach Download)
 * 
 * Ausfuehren via:
 * https://acencia.info/setup/007_add_is_archived.php?token=BiPro2025Setup!
 * 
 * NACH AUSFUEHRUNG DIESE DATEI LOESCHEN!
 */

// Sicherheitstoken pruefen
$expected_token = 'BiPro2025Setup!';
if (!isset($_GET['token']) || $_GET['token'] !== $expected_token) {
    http_response_code(403);
    die('Zugriff verweigert. Token erforderlich.');
}

require_once __DIR__ . '/../api/config.php';

echo "<pre>\n";
echo "=== Migration: Archivierungs-Funktion ===\n\n";

try {
    $pdo = new PDO(
        "mysql:host=" . DB_HOST . ";dbname=" . DB_NAME . ";charset=utf8mb4",
        DB_USER,
        DB_PASS,
        [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC
        ]
    );
    
    echo "Datenbankverbindung OK\n\n";
    
    // 1. is_archived Spalte
    $stmt = $pdo->query("SHOW COLUMNS FROM documents LIKE 'is_archived'");
    $exists = $stmt->fetch();
    
    if ($exists) {
        echo "Spalte 'is_archived' existiert bereits.\n";
    } else {
        $pdo->exec("
            ALTER TABLE documents 
            ADD COLUMN is_archived TINYINT(1) NOT NULL DEFAULT 0
            COMMENT 'Ob das Dokument archiviert wurde (nach Download)'
        ");
        echo "Spalte 'is_archived' erfolgreich hinzugefuegt!\n";
    }
    
    // 2. Index fuer is_archived (fuer schnelle Filterung)
    $stmt = $pdo->query("SHOW INDEX FROM documents WHERE Key_name = 'idx_is_archived'");
    $exists = $stmt->fetch();
    
    if ($exists) {
        echo "Index 'idx_is_archived' existiert bereits.\n";
    } else {
        $pdo->exec("CREATE INDEX idx_is_archived ON documents (is_archived)");
        echo "Index 'idx_is_archived' erfolgreich erstellt!\n";
    }
    
    // 3. Kombinierter Index fuer box_type + is_archived (fuer schnelle Box-Filterung)
    $stmt = $pdo->query("SHOW INDEX FROM documents WHERE Key_name = 'idx_box_archived'");
    $exists = $stmt->fetch();
    
    if ($exists) {
        echo "Index 'idx_box_archived' existiert bereits.\n";
    } else {
        $pdo->exec("CREATE INDEX idx_box_archived ON documents (box_type, is_archived)");
        echo "Index 'idx_box_archived' erfolgreich erstellt!\n";
    }
    
    echo "\n=== Migration abgeschlossen ===\n";
    echo "\nBitte diese Datei jetzt loeschen!\n";
    
} catch (PDOException $e) {
    echo "FEHLER: " . $e->getMessage() . "\n";
}

echo "</pre>";

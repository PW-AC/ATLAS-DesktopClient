<?php
/**
 * Migration: Fuegt bipro_category Feld zur documents Tabelle hinzu
 * 
 * Das Feld speichert den BiPRO-Kategorie-Code (z.B. "300001000" fuer Provisionsabrechnung)
 * um eine regelbasierte Vorsortierung ohne KI zu ermoeglichen.
 * 
 * Ausfuehren via:
 * https://acencia.info/setup/006_add_bipro_category.php?token=BiPro2025Setup!
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
echo "=== Migration: bipro_category Feld fuer BiPRO-Vorsortierung ===\n\n";

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
    
    // 1. bipro_category Spalte hinzufuegen
    $stmt = $pdo->query("SHOW COLUMNS FROM documents LIKE 'bipro_category'");
    $exists = $stmt->fetch();
    
    if ($exists) {
        echo "Spalte 'bipro_category' existiert bereits.\n";
    } else {
        $pdo->exec("
            ALTER TABLE documents 
            ADD COLUMN bipro_category VARCHAR(20) NULL DEFAULT NULL
            COMMENT 'BiPRO-Kategorie-Code (z.B. 300001000 = Provision)'
            AFTER external_shipment_id
        ");
        echo "Spalte 'bipro_category' erfolgreich hinzugefuegt!\n";
    }
    
    // 2. Index fuer schnellere Abfragen
    $stmt = $pdo->query("SHOW INDEX FROM documents WHERE Key_name = 'idx_bipro_category'");
    $exists = $stmt->fetch();
    
    if ($exists) {
        echo "Index 'idx_bipro_category' existiert bereits.\n";
    } else {
        $pdo->exec("CREATE INDEX idx_bipro_category ON documents(bipro_category)");
        echo "Index 'idx_bipro_category' erfolgreich erstellt!\n";
    }
    
    // 3. Kranken-Box zum ENUM hinzufuegen (falls noch nicht vorhanden)
    $stmt = $pdo->query("SHOW COLUMNS FROM documents WHERE Field = 'box_type'");
    $column = $stmt->fetch();
    
    if ($column && strpos($column['Type'], 'kranken') === false) {
        echo "\nFuege 'kranken' zum box_type ENUM hinzu...\n";
        $pdo->exec("
            ALTER TABLE documents 
            MODIFY COLUMN box_type ENUM(
                'eingang',
                'verarbeitung',
                'roh',
                'gdv',
                'courtage',
                'sach',
                'leben',
                'kranken',
                'sonstige'
            ) NOT NULL DEFAULT 'sonstige'
            COMMENT 'Box in der das Dokument liegt'
        ");
        echo "'kranken' zum box_type ENUM hinzugefuegt!\n";
    } else {
        echo "'kranken' ist bereits im box_type ENUM vorhanden.\n";
    }
    
    echo "\n=== Migration erfolgreich! ===\n";
    echo "\nBitte diese Datei jetzt loeschen!\n";
    
} catch (PDOException $e) {
    echo "FEHLER: " . $e->getMessage() . "\n";
}

echo "</pre>";

<?php
/**
 * Migration: Box-System fuer Dokumenten-Archiv
 * 
 * Fuegt Spalten hinzu fuer:
 * - box_type: In welcher Box liegt das Dokument
 * - processing_status: Verarbeitungsstatus
 * - document_category: Kategorie (fuer KI-Klassifikation)
 * 
 * Ausfuehren via:
 * https://acencia.info/setup/005_add_box_columns.php?token=BiPro2025Setup!
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
echo "=== Migration: Box-System fuer Dokumenten-Archiv ===\n\n";

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
    
    // 1. box_type Spalte
    $stmt = $pdo->query("SHOW COLUMNS FROM documents LIKE 'box_type'");
    $exists = $stmt->fetch();
    
    if ($exists) {
        echo "Spalte 'box_type' existiert bereits.\n";
    } else {
        $pdo->exec("
            ALTER TABLE documents 
            ADD COLUMN box_type ENUM(
                'eingang',
                'verarbeitung',
                'roh',
                'gdv',
                'courtage',
                'sach',
                'leben',
                'sonstige'
            ) NOT NULL DEFAULT 'sonstige'
            COMMENT 'Box in der das Dokument liegt'
        ");
        echo "Spalte 'box_type' erfolgreich hinzugefuegt!\n";
    }
    
    // 2. processing_status Spalte
    $stmt = $pdo->query("SHOW COLUMNS FROM documents LIKE 'processing_status'");
    $exists = $stmt->fetch();
    
    if ($exists) {
        echo "Spalte 'processing_status' existiert bereits.\n";
    } else {
        $pdo->exec("
            ALTER TABLE documents 
            ADD COLUMN processing_status ENUM(
                'pending',
                'processing',
                'completed',
                'error'
            ) NOT NULL DEFAULT 'completed'
            COMMENT 'Verarbeitungsstatus'
        ");
        echo "Spalte 'processing_status' erfolgreich hinzugefuegt!\n";
    }
    
    // 3. document_category Spalte
    $stmt = $pdo->query("SHOW COLUMNS FROM documents LIKE 'document_category'");
    $exists = $stmt->fetch();
    
    if ($exists) {
        echo "Spalte 'document_category' existiert bereits.\n";
    } else {
        $pdo->exec("
            ALTER TABLE documents 
            ADD COLUMN document_category VARCHAR(50) NULL DEFAULT NULL
            COMMENT 'Dokumenten-Kategorie (xml_raw, gdv, courtage, sach, leben, unknown)'
        ");
        echo "Spalte 'document_category' erfolgreich hinzugefuegt!\n";
    }
    
    // 4. Index fuer box_type (fuer schnelle Filterung)
    $stmt = $pdo->query("SHOW INDEX FROM documents WHERE Key_name = 'idx_box_type'");
    $exists = $stmt->fetch();
    
    if ($exists) {
        echo "Index 'idx_box_type' existiert bereits.\n";
    } else {
        $pdo->exec("CREATE INDEX idx_box_type ON documents (box_type)");
        echo "Index 'idx_box_type' erfolgreich erstellt!\n";
    }
    
    // 5. Bestehende Dokumente: Alle auf 'sonstige' und 'completed' setzen
    $result = $pdo->exec("
        UPDATE documents 
        SET box_type = 'sonstige', 
            processing_status = 'completed' 
        WHERE box_type = 'sonstige' 
          AND processing_status = 'completed'
    ");
    echo "\nBestehende Dokumente: Status unveraendert (bereits migriert oder Defaults)\n";
    
    // 6. GDV-Dateien in GDV-Box verschieben
    $result = $pdo->exec("
        UPDATE documents 
        SET box_type = 'gdv', document_category = 'gdv'
        WHERE is_gdv = 1 AND box_type = 'sonstige'
    ");
    echo "GDV-Dateien in GDV-Box verschoben: $result Dokument(e)\n";
    
    // 7. XML-Rohdateien erkennen (Dateiname enthaelt 'Roh' und .xml)
    $result = $pdo->exec("
        UPDATE documents 
        SET box_type = 'roh', document_category = 'xml_raw'
        WHERE (original_filename LIKE '%Roh%' OR original_filename LIKE '%_Roh_%')
          AND (original_filename LIKE '%.xml' OR mime_type = 'application/xml' OR mime_type = 'text/xml')
          AND box_type = 'sonstige'
    ");
    echo "XML-Rohdateien in Roh-Archiv verschoben: $result Dokument(e)\n";
    
    echo "\n=== Migration abgeschlossen ===\n";
    echo "\nBitte diese Datei jetzt loeschen!\n";
    
} catch (PDOException $e) {
    echo "FEHLER: " . $e->getMessage() . "\n";
}

echo "</pre>";

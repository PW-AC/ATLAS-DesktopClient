<?php
/**
 * Migration 017: document_ai_data Tabelle
 * 
 * Separate Tabelle fuer Volltext-Extraktion und KI-Klassifikations-Daten.
 * 1:1-Beziehung zu documents (UNIQUE KEY auf document_id).
 * 
 * WICHTIG: Kein JOIN auf diese Tabelle in listDocuments()!
 * Text und KI-Daten werden NUR ueber /documents/{id}/ai-data geladen.
 */

require_once __DIR__ . '/../api/config.php';

try {
    $pdo = new PDO(
        'mysql:host=' . DB_HOST . ';dbname=' . DB_NAME . ';charset=utf8mb4',
        DB_USER,
        DB_PASS,
        [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]
    );

    echo "=== Migration 017: document_ai_data Tabelle ===\n\n";

    // Pruefen ob Tabelle bereits existiert
    $stmt = $pdo->query("SHOW TABLES LIKE 'document_ai_data'");
    if ($stmt->rowCount() > 0) {
        echo "[SKIP] Tabelle 'document_ai_data' existiert bereits.\n";
    } else {
        $pdo->exec("
            CREATE TABLE document_ai_data (
                id INT AUTO_INCREMENT PRIMARY KEY,
                document_id INT NOT NULL,
                filename VARCHAR(255) NOT NULL,

                -- Volltext (alle Seiten, unkomprimiert, mit FULLTEXT-Index)
                extracted_text MEDIUMTEXT NULL,
                extracted_text_sha256 CHAR(64) NULL,
                extraction_method ENUM('text','ocr','mixed','none') DEFAULT 'text',
                extracted_page_count INT NULL,

                -- KI-Daten (LONGTEXT -- flexibler als JSON-Typ, kein Parsing-Overhead)
                ai_full_response LONGTEXT NULL,
                ai_prompt_text MEDIUMTEXT NULL,
                ai_model VARCHAR(100) NULL,
                ai_prompt_version VARCHAR(50) NULL,
                ai_stage ENUM('triage_only','triage_and_detail','courtage_minimal','none') NULL,

                -- Zeichenzaehler (schnelle Groessenanalyse ohne Text laden)
                text_char_count INT NULL,
                ai_response_char_count INT NULL,

                -- Token-Verbrauch (pro KI-Request, aggregiert bei zweistufig)
                prompt_tokens INT NULL,
                completion_tokens INT NULL,
                total_tokens INT NULL,

                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

                UNIQUE KEY uniq_document (document_id),
                INDEX idx_document_id (document_id),
                INDEX idx_created_at (created_at),
                FULLTEXT INDEX ft_extracted_text (extracted_text)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ");
        echo "[OK] Tabelle 'document_ai_data' erstellt.\n";
        echo "     - UNIQUE KEY auf document_id (1:1 zu documents)\n";
        echo "     - FULLTEXT INDEX auf extracted_text\n";
        echo "     - MEDIUMTEXT fuer Volltext, LONGTEXT fuer KI-Response\n";
    }

    echo "\n=== Migration 017 abgeschlossen ===\n";

} catch (PDOException $e) {
    echo "[FEHLER] " . $e->getMessage() . "\n";
    exit(1);
}

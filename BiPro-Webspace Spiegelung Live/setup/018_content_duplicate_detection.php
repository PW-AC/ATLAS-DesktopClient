<?php
/**
 * Migration 018: Inhaltsduplikat-Erkennung
 * 
 * Fuegt content_duplicate_of_id zu documents hinzu.
 * Erkennt Dokumente mit identischem Text (extracted_text_sha256)
 * auch wenn die Dateien technisch unterschiedlich sind.
 * 
 * Backfill: Markiert bestehende Inhaltsduplikate basierend auf
 * den bereits vorhandenen document_ai_data Eintraegen.
 */

require_once __DIR__ . '/../api/config.php';
require_once __DIR__ . '/../api/lib/db.php';

echo "=== Migration 018: Inhaltsduplikat-Erkennung ===\n\n";

try {
    // 1. Pruefen ob Spalte bereits existiert
    $columns = Database::query("SHOW COLUMNS FROM documents LIKE 'content_duplicate_of_id'");
    
    if (!empty($columns)) {
        echo "[SKIP] Spalte 'content_duplicate_of_id' existiert bereits.\n";
    } else {
        // 2. Spalte hinzufuegen
        Database::execute(
            "ALTER TABLE documents ADD COLUMN content_duplicate_of_id INT NULL DEFAULT NULL"
        );
        echo "[OK] Spalte 'content_duplicate_of_id' hinzugefuegt.\n";
        
        // 3. Index fuer Performance
        Database::execute(
            "ALTER TABLE documents ADD INDEX idx_content_dup (content_duplicate_of_id)"
        );
        echo "[OK] Index 'idx_content_dup' erstellt.\n";
    }
    
    // 4. Backfill: Bestehende Inhaltsduplikate markieren
    echo "\nBackfill bestehender Inhaltsduplikate...\n";
    
    // Finde alle Text-Hashes die mehrfach vorkommen
    $groups = Database::query(
        "SELECT extracted_text_sha256, MIN(document_id) as original_id, COUNT(*) as cnt
         FROM document_ai_data 
         WHERE extracted_text_sha256 IS NOT NULL 
         GROUP BY extracted_text_sha256 
         HAVING COUNT(*) > 1"
    );
    
    $totalUpdated = 0;
    
    foreach ($groups as $group) {
        // Alle Dokumente mit diesem Hash ausser dem Original markieren
        $affected = Database::execute(
            "UPDATE documents d 
             JOIN document_ai_data dad ON d.id = dad.document_id
             SET d.content_duplicate_of_id = ?
             WHERE dad.extracted_text_sha256 = ?
               AND d.id != ?
               AND (d.content_duplicate_of_id IS NULL OR d.content_duplicate_of_id != ?)",
            [
                $group['original_id'], 
                $group['extracted_text_sha256'], 
                $group['original_id'],
                $group['original_id']
            ]
        );
        $totalUpdated += $affected;
    }
    
    echo "[OK] {$totalUpdated} Dokument(e) als Inhaltsduplikat markiert";
    echo " (in " . count($groups) . " Duplikatgruppe(n)).\n";

    echo "\n=== Migration 018 abgeschlossen ===\n";
    
} catch (Exception $e) {
    echo "[FEHLER] " . $e->getMessage() . "\n";
    exit(1);
}

<?php
/**
 * Migration 034: Schema-Migrations-Tracking
 * 
 * Erstellt die Tabelle schema_migrations zur Nachverfolgung
 * aller ausgefuehrten Migrationen. Registriert retroaktiv
 * alle bestehenden Migrationen.
 */

require_once __DIR__ . '/../api/lib/db.php';
require_once __DIR__ . '/../api/config.php';

try {
    $pdo = Database::getInstance();

    // 1. Tabelle erstellen
    $tables = $pdo->query("SHOW TABLES LIKE 'schema_migrations'")->fetchAll();
    if (empty($tables)) {
        $pdo->exec("
            CREATE TABLE schema_migrations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                migration_name VARCHAR(100) NOT NULL UNIQUE,
                applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_migration_name (migration_name)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ");
        echo "Tabelle schema_migrations erstellt.\n";
    } else {
        echo "Tabelle schema_migrations existiert bereits.\n";
    }

    // 2. Bestehende Migrationen retroaktiv registrieren
    $known_migrations = [
        '005_add_box_columns',
        '006_add_processing_stage',
        '007_document_hash_unique',
        '008_xml_index_table',
        '010_smartscan_email',
        '011_fix_smartscan_schema',
        '012_ai_classification_data',
        '013_rate_limits',
        '014_processing_history',
        '015_message_center',
        '016_chat_system',
        '017_document_ai_data',
        '018_notifications',
        '024_provision_matching_v2',
        '025_provision_indexes',
        '026_vsnr_renormalize',
        '027_reset_provision_data',
        '028_xempus_complete',
        '029_provision_role_permissions',
        '030_bipro_events',
        '031_model_tl_fields',
        '032_rename_channel_dev',
        '033_user_update_channel',
        '034_schema_migrations',
    ];

    $stmt = $pdo->prepare("INSERT IGNORE INTO schema_migrations (migration_name) VALUES (?)");
    $registered = 0;
    foreach ($known_migrations as $name) {
        $stmt->execute([$name]);
        if ($stmt->rowCount() > 0) {
            $registered++;
        }
    }
    echo "{$registered} bestehende Migration(en) retroaktiv registriert.\n";

    $total = $pdo->query("SELECT COUNT(*) FROM schema_migrations")->fetchColumn();
    echo "Gesamt registrierte Migrationen: {$total}\n";

    echo "\nMigration 034 erfolgreich abgeschlossen.\n";

} catch (Exception $e) {
    echo "FEHLER: " . $e->getMessage() . "\n";
    exit(1);
}

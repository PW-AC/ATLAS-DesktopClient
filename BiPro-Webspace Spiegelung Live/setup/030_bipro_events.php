<?php
/**
 * Migration 030: BiPRO Events
 *
 * Speichert strukturierte Metadaten aus 0-Dokument-Lieferungen
 * (Vertragsdaten-XML, Statusmeldungen, GDV-Ankuendigungen).
 */

require_once __DIR__ . '/../api/config.php';
require_once __DIR__ . '/../api/lib/db.php';

try {
    $pdo = db();

    $pdo->exec("
        CREATE TABLE IF NOT EXISTS bipro_events (
            id INT AUTO_INCREMENT PRIMARY KEY,
            shipment_id VARCHAR(50) NOT NULL,
            vu_name VARCHAR(255) NULL,
            vu_bafin_nr VARCHAR(10) NULL,
            bipro_category VARCHAR(20) NULL,
            category_name VARCHAR(255) NULL,
            event_type ENUM('gdv_announced','contract_xml','status_message','document_xml') NOT NULL,
            vsnr VARCHAR(100) NULL,
            vn_name VARCHAR(255) NULL,
            vn_address TEXT NULL,
            sparte VARCHAR(10) NULL,
            vermittler_nr VARCHAR(100) NULL,
            freitext TEXT NULL,
            kurzbeschreibung VARCHAR(500) NULL,
            referenced_filename VARCHAR(500) NULL,
            shipment_date DATE NULL,
            raw_document_id INT NULL,
            is_read TINYINT(1) NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_shipment (shipment_id),
            INDEX idx_event_type (event_type),
            INDEX idx_created_at (created_at DESC),
            INDEX idx_is_read (is_read),
            CONSTRAINT fk_bipro_events_doc FOREIGN KEY (raw_document_id)
                REFERENCES documents(id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ");

    echo "Migration 030: bipro_events Tabelle erstellt.\n";

} catch (PDOException $e) {
    echo "Migration 030 Fehler: " . $e->getMessage() . "\n";
    exit(1);
}

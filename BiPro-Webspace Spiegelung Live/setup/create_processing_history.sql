-- Erstellt die processing_history Tabelle für Audit-Trail
-- Direkt in phpMyAdmin oder per MySQL-Client ausführen

CREATE TABLE IF NOT EXISTS `processing_history` (
    `id` int(11) NOT NULL AUTO_INCREMENT,
    `document_id` int(11) NOT NULL,
    `previous_status` varchar(50) DEFAULT NULL,
    `new_status` varchar(50) NOT NULL,
    `action` varchar(100) NOT NULL COMMENT 'z.B. download, validate, classify, archive, error',
    `action_details` text DEFAULT NULL COMMENT 'JSON mit zusätzlichen Details',
    `success` tinyint(1) NOT NULL DEFAULT 1,
    `error_message` text DEFAULT NULL,
    `classification_source` varchar(50) DEFAULT NULL COMMENT 'ki_gpt4o, rule_bipro, fallback, etc.',
    `classification_result` varchar(100) DEFAULT NULL,
    `duration_ms` int(11) DEFAULT NULL COMMENT 'Dauer des Verarbeitungsschritts',
    `created_by` varchar(100) DEFAULT NULL,
    `created_at` datetime NOT NULL DEFAULT current_timestamp(),
    PRIMARY KEY (`id`),
    KEY `idx_document_id` (`document_id`),
    KEY `idx_action` (`action`),
    KEY `idx_created_at` (`created_at`),
    KEY `idx_success` (`success`),
    KEY `idx_classification_source` (`classification_source`),
    CONSTRAINT `fk_processing_history_document` FOREIGN KEY (`document_id`) REFERENCES `documents` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Prüfen ob classification_* Felder in documents existieren
-- Falls Fehler "Duplicate column" -> Felder existieren bereits, ignorieren

ALTER TABLE `documents` 
ADD COLUMN `classification_source` varchar(50) DEFAULT NULL COMMENT 'ki_gpt4o, rule_bipro, fallback, etc.',
ADD COLUMN `classification_confidence` varchar(20) DEFAULT NULL COMMENT 'high, medium, low',
ADD COLUMN `classification_reason` text DEFAULT NULL COMMENT 'Begründung der Klassifikation',
ADD COLUMN `classification_timestamp` datetime DEFAULT NULL COMMENT 'Zeitpunkt der Klassifikation';

-- Index für classification_source (Fehler ignorieren falls existiert)
CREATE INDEX `idx_classification_source` ON `documents` (`classification_source`);

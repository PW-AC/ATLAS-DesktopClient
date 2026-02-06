<?php
/**
 * BiPro API - Dokumente
 * 
 * Endpunkte:
 * - GET /documents - Liste aller Dokumente
 * - GET /documents/stats - Box-Statistiken
 * - POST /documents - Dokument hochladen
 * - POST /documents/move - Dokumente verschieben
 * - GET /documents/{id} - Dokument herunterladen
 * - PUT /documents/{id} - Dokument-Metadaten aktualisieren
 * - DELETE /documents/{id} - Dokument loeschen
 */

require_once __DIR__ . '/lib/jwt.php';
require_once __DIR__ . '/lib/response.php';

function handleDocumentsRequest(string $idOrAction, string $method): void {
    $payload = JWT::requireAuth();
    
    switch ($method) {
        case 'GET':
            if (empty($idOrAction) || $idOrAction === 'list') {
                listDocuments($payload);
            } elseif ($idOrAction === 'stats') {
                getBoxStats($payload);
            } else {
                downloadDocument($idOrAction, $payload);
            }
            break;
            
        case 'POST':
            if ($idOrAction === 'move') {
                moveDocuments($payload);
            } else {
                uploadDocument($payload);
            }
            break;
            
        case 'PUT':
            if (empty($idOrAction)) {
                json_error('Dokument-ID erforderlich', 400);
            }
            updateDocument($idOrAction, $payload);
            break;
            
        case 'DELETE':
            if (empty($idOrAction)) {
                json_error('Dokument-ID erforderlich', 400);
            }
            deleteDocument($idOrAction, $payload);
            break;
            
        default:
            json_error('Methode nicht erlaubt', 405);
    }
}

/**
 * GET /documents
 * Query-Parameter: vu, type, from, to, is_gdv, box
 */
function listDocuments(array $user): void {
    $conditions = ['1=1'];
    $params = [];
    
    // Filter: Box-Typ
    if (!empty($_GET['box'])) {
        $validBoxes = ['eingang', 'verarbeitung', 'roh', 'gdv', 'courtage', 'sach', 'leben', 'kranken', 'sonstige'];
        if (in_array($_GET['box'], $validBoxes)) {
            $conditions[] = 'd.box_type = ?';
            $params[] = $_GET['box'];
        }
    }
    
    // Filter: VU
    if (!empty($_GET['vu'])) {
        $conditions[] = 'd.shipment_id IN (SELECT id FROM shipments WHERE vu_connection_id = ?)';
        $params[] = $_GET['vu'];
    }
    
    // Filter: Quelle
    if (!empty($_GET['source'])) {
        $conditions[] = 'd.source_type = ?';
        $params[] = $_GET['source'];
    }
    
    // Filter: Nur GDV
    if (isset($_GET['is_gdv']) && $_GET['is_gdv'] === '1') {
        $conditions[] = 'd.is_gdv = 1';
    }
    
    // Filter: Datum von
    if (!empty($_GET['from'])) {
        $conditions[] = 'd.created_at >= ?';
        $params[] = $_GET['from'];
    }
    
    // Filter: Datum bis
    if (!empty($_GET['to'])) {
        $conditions[] = 'd.created_at <= ?';
        $params[] = $_GET['to'] . ' 23:59:59';
    }
    
    // Filter: Processing Status
    if (!empty($_GET['processing_status'])) {
        $conditions[] = 'd.processing_status = ?';
        $params[] = $_GET['processing_status'];
    }
    
    // Filter: Archiviert (is_archived)
    if (isset($_GET['is_archived'])) {
        $conditions[] = 'd.is_archived = ?';
        $params[] = $_GET['is_archived'] === '1' ? 1 : 0;
    }
    
    $where = implode(' AND ', $conditions);
    
    $documents = Database::query("
        SELECT 
            d.id,
            d.filename,
            d.original_filename,
            d.mime_type,
            d.file_size,
            d.source_type,
            d.is_gdv,
            d.created_at,
            u.username as uploaded_by_name,
            COALESCE(d.external_shipment_id, s.external_shipment_id) as external_shipment_id,
            COALESCE(d.vu_name, vc.vu_name) as vu_name,
            COALESCE(d.ai_renamed, 0) as ai_renamed,
            d.ai_processing_error,
            COALESCE(d.box_type, 'sonstige') as box_type,
            COALESCE(d.processing_status, 'completed') as processing_status,
            d.document_category,
            d.bipro_category,
            COALESCE(d.is_archived, 0) as is_archived
        FROM documents d
        LEFT JOIN users u ON d.uploaded_by = u.id
        LEFT JOIN shipments s ON d.shipment_id = s.id
        LEFT JOIN vu_connections vc ON s.vu_connection_id = vc.id
        WHERE $where
        ORDER BY d.created_at DESC
        LIMIT 1000
    ", $params);
    
    json_success([
        'documents' => $documents,
        'count' => count($documents)
    ]);
}

/**
 * GET /documents/stats
 * Gibt Anzahl Dokumente pro Box zurueck (inkl. archivierte)
 */
function getBoxStats(array $user): void {
    // Nicht-archivierte Dokumente pro Box
    $stats = Database::query("
        SELECT 
            COALESCE(box_type, 'sonstige') as box_type,
            COUNT(*) as count
        FROM documents
        WHERE COALESCE(is_archived, 0) = 0
        GROUP BY box_type
    ");
    
    // Archivierte Dokumente pro Box
    $archivedStats = Database::query("
        SELECT 
            COALESCE(box_type, 'sonstige') as box_type,
            COUNT(*) as count
        FROM documents
        WHERE COALESCE(is_archived, 0) = 1
        GROUP BY box_type
    ");
    
    // In assoziatives Array umwandeln
    $result = [
        'eingang' => 0,
        'verarbeitung' => 0,
        'roh' => 0,
        'gdv' => 0,
        'courtage' => 0,
        'sach' => 0,
        'leben' => 0,
        'kranken' => 0,
        'sonstige' => 0,
        'total' => 0,
        // Archivierte Zaehlungen
        'gdv_archived' => 0,
        'courtage_archived' => 0,
        'sach_archived' => 0,
        'leben_archived' => 0,
        'kranken_archived' => 0,
        'sonstige_archived' => 0
    ];
    
    // Nicht-archivierte zaehlen
    foreach ($stats as $row) {
        $box = $row['box_type'] ?: 'sonstige';
        $result[$box] = (int)$row['count'];
        $result['total'] += (int)$row['count'];
    }
    
    // Archivierte zaehlen
    foreach ($archivedStats as $row) {
        $box = $row['box_type'] ?: 'sonstige';
        $archivedKey = $box . '_archived';
        if (isset($result[$archivedKey])) {
            $result[$archivedKey] = (int)$row['count'];
        }
        // Archivierte auch zum Gesamt zaehlen
        $result['total'] += (int)$row['count'];
    }
    
    json_success($result);
}

/**
 * POST /documents/move
 * Verschiebt mehrere Dokumente in eine andere Box
 */
function moveDocuments(array $user): void {
    $data = get_json_body();
    
    if (empty($data['document_ids']) || !is_array($data['document_ids'])) {
        json_error('document_ids erforderlich (Array)', 400);
    }
    
    if (empty($data['target_box'])) {
        json_error('target_box erforderlich', 400);
    }
    
    $validBoxes = ['eingang', 'verarbeitung', 'roh', 'gdv', 'courtage', 'sach', 'leben', 'kranken', 'sonstige'];
    if (!in_array($data['target_box'], $validBoxes)) {
        json_error('Ungueltiger Box-Typ: ' . $data['target_box'], 400);
    }
    
    $docIds = array_map('intval', $data['document_ids']);
    $targetBox = $data['target_box'];
    
    // Placeholders fuer IN-Clause
    $placeholders = implode(',', array_fill(0, count($docIds), '?'));
    
    // Dokumente verschieben
    $params = array_merge([$targetBox], $docIds);
    $affected = Database::execute(
        "UPDATE documents SET box_type = ?, processing_status = 'completed' WHERE id IN ($placeholders)",
        $params
    );
    
    // Audit-Log
    Database::insert(
        'INSERT INTO audit_log (user_id, action, entity_type, details, ip_address) VALUES (?, ?, ?, ?, ?)',
        [
            $user['user_id'], 
            'documents_move', 
            'document', 
            json_encode(['document_ids' => $docIds, 'target_box' => $targetBox]), 
            $_SERVER['REMOTE_ADDR'] ?? ''
        ]
    );
    
    json_success([
        'moved_count' => $affected,
        'target_box' => $targetBox
    ], "$affected Dokument(e) verschoben");
}

/**
 * POST /documents
 * Multipart-Upload mit Datei
 * 
 * ATOMIC WRITE PATTERN:
 * 1. Datei als .tmp in Staging schreiben
 * 2. Hash/Size verifizieren
 * 3. beginTransaction()
 * 4. DB Insert
 * 5. Atomic move via rename() ins finale Ziel
 * 6. commit()
 * 7. On error: rollback() + tmp-Datei loeschen
 */
function uploadDocument(array $user): void {
    if (!isset($_FILES['file']) || $_FILES['file']['error'] !== UPLOAD_ERR_OK) {
        $errorMessages = [
            UPLOAD_ERR_INI_SIZE => 'Datei zu groß (PHP-Limit)',
            UPLOAD_ERR_FORM_SIZE => 'Datei zu groß (Form-Limit)',
            UPLOAD_ERR_PARTIAL => 'Upload unvollständig',
            UPLOAD_ERR_NO_FILE => 'Keine Datei hochgeladen',
        ];
        $error = $_FILES['file']['error'] ?? UPLOAD_ERR_NO_FILE;
        json_error($errorMessages[$error] ?? 'Upload-Fehler', 400);
    }
    
    $file = $_FILES['file'];
    
    // Größe prüfen
    if ($file['size'] > MAX_UPLOAD_SIZE) {
        json_error('Datei zu groß (max. ' . (MAX_UPLOAD_SIZE / 1024 / 1024) . ' MB)', 400);
    }
    
    // MIME-Type prüfen (optional)
    $mimeType = $file['type'] ?: 'application/octet-stream';
    
    // Dateiname bereinigen
    $originalFilename = basename($file['name']);
    $safeFilename = preg_replace('/[^a-zA-Z0-9._-]/', '_', $originalFilename);
    
    // Eindeutigen Dateinamen generieren
    $uniqueFilename = date('Y-m-d_His') . '_' . uniqid() . '_' . $safeFilename;
    
    // Zielordner (nach Jahr/Monat organisiert)
    $subdir = date('Y/m');
    $targetDir = DOCUMENTS_PATH . $subdir;
    $stagingDir = DOCUMENTS_PATH . 'staging';
    
    // Verzeichnisse erstellen
    if (!is_dir($targetDir)) {
        mkdir($targetDir, 0755, true);
    }
    if (!is_dir($stagingDir)) {
        mkdir($stagingDir, 0755, true);
    }
    
    // SCHRITT 1: Datei als .tmp in Staging schreiben
    $stagingPath = $stagingDir . '/.tmp_' . $uniqueFilename;
    $targetPath = $targetDir . '/' . $uniqueFilename;
    $storagePath = $subdir . '/' . $uniqueFilename;
    
    if (!move_uploaded_file($file['tmp_name'], $stagingPath)) {
        json_error('Datei konnte nicht in Staging gespeichert werden', 500);
    }
    
    // SCHRITT 2: Hash/Size verifizieren
    $actualSize = filesize($stagingPath);
    if ($actualSize !== $file['size']) {
        @unlink($stagingPath);
        json_error("Upload unvollstaendig: erwartet {$file['size']}, erhalten $actualSize Bytes", 500);
    }
    
    // Content-Hash berechnen (fuer spaetere Deduplizierung)
    $contentHash = hash_file('sha256', $stagingPath);
    
    // Prüfen ob GDV-Datei (vor dem Move, da wir Staging-Pfad haben)
    $isGdv = isGdvFile($stagingPath);
    
    // Quelle bestimmen
    $sourceType = $_POST['source_type'] ?? 'manual_upload';
    if (!in_array($sourceType, ['bipro_auto', 'manual_upload', 'self_created'])) {
        $sourceType = 'manual_upload';
    }
    
    // VU-Name fuer BiPRO-Lieferungen
    $vuName = $_POST['vu_name'] ?? null;
    
    // External Shipment ID (BiPRO-Lieferungs-ID als String)
    $externalShipmentId = $_POST['shipment_id'] ?? null;
    
    // Box-Typ (Standard: eingang fuer neue Uploads)
    $boxType = $_POST['box_type'] ?? 'eingang';
    $validBoxes = ['eingang', 'verarbeitung', 'roh', 'gdv', 'courtage', 'sach', 'leben', 'kranken', 'sonstige'];
    if (!in_array($boxType, $validBoxes)) {
        $boxType = 'eingang';
    }
    
    // BiPRO-Kategorie (z.B. "300001000" fuer Provisionsabrechnung)
    $biproCategory = $_POST['bipro_category'] ?? null;
    
    // PDF-Validierungsstatus (NEU)
    // Gueltige Werte: OK, PDF_ENCRYPTED, PDF_CORRUPT, PDF_INCOMPLETE, PDF_XFA, PDF_REPAIRED, PDF_NO_PAGES, PDF_LOAD_ERROR
    $validationStatus = $_POST['validation_status'] ?? null;
    $validValidationStatuses = ['OK', 'PDF_ENCRYPTED', 'PDF_CORRUPT', 'PDF_INCOMPLETE', 'PDF_XFA', 'PDF_REPAIRED', 'PDF_NO_PAGES', 'PDF_LOAD_ERROR'];
    if ($validationStatus !== null && !in_array($validationStatus, $validValidationStatuses)) {
        $validationStatus = null;  // Ungueltige Werte ignorieren
    }
    
    // Processing Status
    $processingStatus = 'pending';
    
    // SCHRITT 3: Transaction starten
    Database::beginTransaction();
    
    try {
        // SCHRITT 3.5: Duplikat-Pruefung via content_hash (Idempotenz)
        $version = 1;
        $previousVersionId = null;
        $isDuplicate = false;
        
        if ($contentHash) {
            // Prüfe ob Datei mit gleichem Hash bereits existiert
            $existing = Database::queryOne(
                "SELECT id, version, original_filename 
                 FROM documents 
                 WHERE content_hash = ? 
                 ORDER BY version DESC 
                 LIMIT 1",
                [$contentHash]
            );
            
            if ($existing) {
                // Duplikat gefunden - neue Version erstellen
                $isDuplicate = true;
                $previousVersionId = $existing['id'];
                $version = $existing['version'] + 1;
                
                error_log("Duplikat erkannt: Hash=$contentHash, vorherige Version={$existing['version']}, neue Version=$version");
            }
        }
        
        // SCHRITT 4: In DB speichern (mit Versionierung)
        $docId = Database::insert("
            INSERT INTO documents 
            (filename, original_filename, mime_type, file_size, storage_path, source_type, is_gdv, uploaded_by, shipment_id, vu_name, external_shipment_id, bipro_category, box_type, processing_status, validation_status, content_hash, version, previous_version_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ", [
            $uniqueFilename,
            $originalFilename,
            $mimeType,
            $file['size'],
            $storagePath,
            $sourceType,
            $isGdv ? 1 : 0,
            $user['user_id'],
            null,  // shipment_id (internal) - not used currently
            $vuName,
            $externalShipmentId,
            $biproCategory,
            $boxType,
            $processingStatus,
            $validationStatus,
            $contentHash,
            $version,
            $previousVersionId
        ]);
        
        // SCHRITT 5: Atomic move via rename() ins finale Ziel
        // rename() ist atomar auf gleichem Filesystem
        if (!rename($stagingPath, $targetPath)) {
            throw new Exception("Atomic move fehlgeschlagen: $stagingPath -> $targetPath");
        }
        
        // Audit-Log (innerhalb der Transaktion)
        Database::insert(
            'INSERT INTO audit_log (user_id, action, entity_type, entity_id, details, ip_address) VALUES (?, ?, ?, ?, ?, ?)',
            [$user['user_id'], 'document_upload', 'document', $docId, json_encode([
                'filename' => $originalFilename,
                'content_hash' => $contentHash,
                'atomic_upload' => true,
                'version' => $version,
                'is_duplicate' => $isDuplicate,
                'previous_version_id' => $previousVersionId
            ]), $_SERVER['REMOTE_ADDR'] ?? '']
        );
        
        // SCHRITT 6: Commit
        Database::commit();
        
        $message = $isDuplicate 
            ? "Dokument hochgeladen (Version $version, Duplikat erkannt)"
            : 'Dokument hochgeladen';
        
        json_success([
            'id' => $docId,
            'filename' => $uniqueFilename,
            'original_filename' => $originalFilename,
            'is_gdv' => $isGdv,
            'storage_path' => $storagePath,
            'box_type' => $boxType,
            'processing_status' => $processingStatus,
            'bipro_category' => $biproCategory,
            'validation_status' => $validationStatus,
            'content_hash' => $contentHash,
            'version' => $version,
            'is_duplicate' => $isDuplicate,
            'previous_version_id' => $previousVersionId
        ], $message);
        
    } catch (Exception $e) {
        // SCHRITT 7: On error - Rollback + tmp-Datei loeschen
        Database::rollback();
        
        // Staging-Datei aufraumen (falls noch vorhanden)
        if (file_exists($stagingPath)) {
            @unlink($stagingPath);
        }
        // Falls bereits ins Ziel verschoben wurde, auch dort loeschen
        if (file_exists($targetPath)) {
            @unlink($targetPath);
        }
        
        error_log("Upload fehlgeschlagen (Rollback): " . $e->getMessage());
        json_error('Upload fehlgeschlagen: ' . $e->getMessage(), 500);
    }
}

/**
 * GET /documents/{id}
 */
function downloadDocument(string $id, array $user): void {
    $doc = Database::queryOne(
        'SELECT * FROM documents WHERE id = ?',
        [$id]
    );
    
    if (!$doc) {
        json_error('Dokument nicht gefunden', 404);
    }
    
    $filePath = DOCUMENTS_PATH . $doc['storage_path'];
    
    if (!file_exists($filePath)) {
        json_error('Datei nicht gefunden', 404);
    }
    
    // Download-Header
    header('Content-Type: ' . ($doc['mime_type'] ?: 'application/octet-stream'));
    header('Content-Disposition: attachment; filename="' . $doc['original_filename'] . '"');
    header('Content-Length: ' . filesize($filePath));
    header('Cache-Control: no-cache, must-revalidate');
    
    readfile($filePath);
    exit();
}

/**
 * DELETE /documents/{id}
 */
function deleteDocument(string $id, array $user): void {
    $doc = Database::queryOne(
        'SELECT * FROM documents WHERE id = ?',
        [$id]
    );
    
    if (!$doc) {
        json_error('Dokument nicht gefunden', 404);
    }
    
    $filePath = DOCUMENTS_PATH . $doc['storage_path'];
    
    // Aus DB löschen
    Database::execute('DELETE FROM documents WHERE id = ?', [$id]);
    
    // Datei löschen
    if (file_exists($filePath)) {
        unlink($filePath);
    }
    
    // Audit-Log
    Database::insert(
        'INSERT INTO audit_log (user_id, action, entity_type, entity_id, details, ip_address) VALUES (?, ?, ?, ?, ?, ?)',
        [$user['user_id'], 'document_delete', 'document', $id, json_encode(['filename' => $doc['original_filename']]), $_SERVER['REMOTE_ADDR'] ?? '']
    );
    
    json_success([], 'Dokument gelöscht');
}

/**
 * PUT /documents/{id}
 * Aktualisiert Dokument-Metadaten (Dateiname, KI-Status)
 */
function updateDocument(string $id, array $user): void {
    $doc = Database::queryOne(
        'SELECT * FROM documents WHERE id = ?',
        [$id]
    );
    
    if (!$doc) {
        json_error('Dokument nicht gefunden', 404);
    }
    
    $data = get_json_body();
    
    $updates = [];
    $params = [];
    $changes = [];
    
    // Erlaubte Felder fuer Update
    $allowedFields = [
        'original_filename', 
        'ai_renamed', 
        'ai_processing_error',
        'box_type',
        'processing_status',
        'document_category',
        'validation_status',           // Technischer PDF-Validierungsstatus
        'classification_source',       // Quelle: ki_gpt4o, rule_bipro, fallback, etc.
        'classification_confidence',   // Konfidenz: high, medium, low
        'classification_reason',       // Begruendung/Erklaerung (max 500 Zeichen)
        'classification_timestamp',    // Zeitpunkt der Klassifikation
        'bipro_document_id',           // Eindeutige ID aus BiPRO-Response (Idempotenz)
        'source_xml_index_id',         // Relation zur XML-Quell-Lieferung
        'is_archived'                  // Archivierungs-Status (nach Download)
    ];
    
    // Box-Typ validieren
    $validBoxes = ['eingang', 'verarbeitung', 'roh', 'gdv', 'courtage', 'sach', 'leben', 'kranken', 'sonstige'];
    if (isset($data['box_type']) && !in_array($data['box_type'], $validBoxes)) {
        json_error('Ungueltiger Box-Typ', 400);
    }
    
    // Processing-Status validieren (erweiterte State-Machine mit Transition-Erzwingung)
    $validStatuses = [
        // Neue granulare Status
        'downloaded',   // Datei vom BiPRO heruntergeladen
        'validated',    // PDF-Validierung durchgefuehrt
        'classified',   // KI/Regel-Klassifikation abgeschlossen
        'renamed',      // Dateiname angepasst
        'archived',     // In Ziel-Box verschoben
        'quarantined',  // In Quarantaene (z.B. ungueltiges Format)
        'error',        // Fehler aufgetreten
        // Legacy-Status (abwaertskompatibel)
        'pending',
        'processing',
        'completed'
    ];
    
    if (isset($data['processing_status'])) {
        $newStatus = $data['processing_status'];
        
        if (!in_array($newStatus, $validStatuses)) {
            json_error('Ungueltiger Processing-Status: ' . $newStatus, 400);
        }
        
        // STATE-MACHINE: Transition-Erzwingung
        $currentStatus = $doc['processing_status'] ?? 'pending';
        if (!isValidStatusTransition($currentStatus, $newStatus)) {
            json_error(
                "Ungueltiger Statusuebergang: '$currentStatus' -> '$newStatus'. " .
                "Erlaubte Uebergaenge: " . implode(', ', getValidTransitionsFrom($currentStatus)),
                400
            );
        }
        
        // Automatische History-Eintraege fuer Statuswechsel
        if ($currentStatus !== $newStatus) {
            logStatusTransition($id, $currentStatus, $newStatus, $user);
        }
    }
    
    // validation_status Aenderung auch historisieren
    if (isset($data['validation_status'])) {
        $oldValidation = $doc['validation_status'] ?? null;
        $newValidation = $data['validation_status'];
        if ($oldValidation !== $newValidation) {
            logValidationStatusChange($id, $oldValidation, $newValidation, $user);
        }
    }
    
    foreach ($allowedFields as $field) {
        if (isset($data[$field])) {
            $updates[] = "$field = ?";
            $params[] = $data[$field];
            $changes[$field] = $data[$field];
        }
    }
    
    if (empty($updates)) {
        json_error('Keine Aenderungen angegeben', 400);
    }
    
    $params[] = $id;
    $sql = "UPDATE documents SET " . implode(', ', $updates) . " WHERE id = ?";
    Database::execute($sql, $params);
    
    // Audit-Log
    Database::insert(
        'INSERT INTO audit_log (user_id, action, entity_type, entity_id, details, ip_address) VALUES (?, ?, ?, ?, ?, ?)',
        [
            $user['user_id'], 
            'document_update', 
            'document', 
            $id, 
            json_encode($changes), 
            $_SERVER['REMOTE_ADDR'] ?? ''
        ]
    );
    
    json_success([
        'id' => (int)$id,
        'updated_fields' => array_keys($changes)
    ], 'Dokument aktualisiert');
}

// ============================================================================
// STATE-MACHINE: Transition-Regeln und Logging
// ============================================================================

/**
 * Erlaubte Statusuebergaenge (State-Machine)
 * 
 * Jeder Verarbeitungsschritt darf nur starten, wenn sich ein Dokument
 * im dafuer vorgesehenen Zustand befindet.
 */
function getValidTransitions(): array {
    return [
        // Neue granulare Uebergaenge
        'downloaded'  => ['validated', 'quarantined', 'error', 'processing', 'classified'],
        'validated'   => ['classified', 'quarantined', 'error'],
        'classified'  => ['renamed', 'archived', 'error'],
        'renamed'     => ['archived', 'error'],
        'archived'    => ['error'],  // Re-Processing nur ueber Reset
        'quarantined' => ['downloaded', 'error'],  // Retry nach Korrektur
        'error'       => ['downloaded', 'pending', 'quarantined'],  // Retry erlaubt
        
        // Legacy-Uebergaenge (abwaertskompatibel)
        'pending'     => ['processing', 'downloaded', 'error', 'classified'],
        'processing'  => ['completed', 'classified', 'validated', 'error', 'quarantined', 'renamed', 'archived'],
        'completed'   => ['archived', 'error'],
        
        // Null/Empty als Startpunkt - flexibler fuer parallele Verarbeitung
        // Erlaubt direkte Uebergaenge wenn erster Update noch nicht persistent
        ''            => ['downloaded', 'pending', 'processing', 'classified', 'renamed', 'archived'],
        null          => ['downloaded', 'pending', 'processing', 'classified', 'renamed', 'archived'],
    ];
}

/**
 * Prueft ob ein Statusuebergang gueltig ist
 */
function isValidStatusTransition(?string $from, string $to): bool {
    $transitions = getValidTransitions();
    $fromKey = $from ?? '';
    
    // Wenn from nicht bekannt, erlaube alle gueltigen Stati als Ziel
    if (!isset($transitions[$fromKey])) {
        return true;  // Unbekannter Status -> erlaube Uebergang (Flexibilitaet)
    }
    
    return in_array($to, $transitions[$fromKey], true);
}

/**
 * Gibt erlaubte Uebergaenge von einem Status zurueck
 */
function getValidTransitionsFrom(?string $from): array {
    $transitions = getValidTransitions();
    $fromKey = $from ?? '';
    return $transitions[$fromKey] ?? [];
}

/**
 * Loggt einen Statusuebergang in processing_history
 */
function logStatusTransition(string $docId, ?string $fromStatus, string $toStatus, array $user): void {
    try {
        // Pruefen ob processing_history Tabelle existiert
        $tableExists = Database::queryOne(
            "SHOW TABLES LIKE 'processing_history'"
        );
        
        if (!$tableExists) {
            return;  // Tabelle existiert noch nicht
        }
        
        Database::insert("
            INSERT INTO processing_history 
            (document_id, previous_status, new_status, action, success, created_by)
            VALUES (?, ?, ?, 'status_change', 1, ?)
        ", [
            (int)$docId,
            $fromStatus,
            $toStatus,
            $user['name'] ?? 'system'
        ]);
    } catch (Exception $e) {
        // History-Logging sollte Update nicht blockieren
        error_log("Status-Transition-Log fehlgeschlagen: " . $e->getMessage());
    }
}

/**
 * Loggt eine validation_status Aenderung in processing_history
 */
function logValidationStatusChange(string $docId, ?string $oldStatus, string $newStatus, array $user): void {
    try {
        $tableExists = Database::queryOne(
            "SHOW TABLES LIKE 'processing_history'"
        );
        
        if (!$tableExists) {
            return;
        }
        
        Database::insert("
            INSERT INTO processing_history 
            (document_id, previous_status, new_status, action, action_details, success, created_by)
            VALUES (?, ?, ?, 'validation_change', ?, 1, ?)
        ", [
            (int)$docId,
            $oldStatus ?? 'null',
            $newStatus,
            json_encode(['type' => 'validation_status', 'old' => $oldStatus, 'new' => $newStatus]),
            $user['name'] ?? 'system'
        ]);
    } catch (Exception $e) {
        error_log("Validation-Status-Log fehlgeschlagen: " . $e->getMessage());
    }
}

// ============================================================================
// HILFSFUNKTIONEN
// ============================================================================

/**
 * Prueft ob eine Datei eine GDV-Datei ist
 */
function isGdvFile(string $path): bool {
    $handle = fopen($path, 'r');
    if (!$handle) {
        return false;
    }
    
    // Erste Zeile lesen
    $firstLine = fgets($handle, 260);
    fclose($handle);
    
    if (!$firstLine) {
        return false;
    }
    
    // GDV-Dateien beginnen mit Satzart 0001
    return substr($firstLine, 0, 4) === '0001';
}

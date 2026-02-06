<?php
/**
 * BiPro API - GDV-Operationen
 * 
 * Endpunkte:
 * - GET /gdv/{doc_id} - GDV-Metadaten abrufen
 * - POST /gdv/{doc_id}/parse - GDV-Datei parsen
 * - GET /gdv/{doc_id}/records - Records abrufen
 * - PUT /gdv/{doc_id}/records - Records aktualisieren
 * - GET /gdv/{doc_id}/export - Als GDV-Datei exportieren
 */

require_once __DIR__ . '/lib/jwt.php';
require_once __DIR__ . '/lib/response.php';

function handleGdvRequest(string $docId, string $action, string $method): void {
    $payload = JWT::requireAuth();
    
    if (empty($docId)) {
        json_error('Dokument-ID erforderlich', 400);
    }
    
    switch ($action) {
        case '':
        case 'meta':
            if ($method !== 'GET') {
                json_error('Methode nicht erlaubt', 405);
            }
            getGdvMeta($docId, $payload);
            break;
            
        case 'parse':
            if ($method !== 'POST') {
                json_error('Methode nicht erlaubt', 405);
            }
            parseGdvFile($docId, $payload);
            break;
            
        case 'records':
            if ($method === 'GET') {
                getGdvRecords($docId, $payload);
            } elseif ($method === 'PUT') {
                updateGdvRecords($docId, $payload);
            } else {
                json_error('Methode nicht erlaubt', 405);
            }
            break;
            
        case 'export':
            if ($method !== 'GET') {
                json_error('Methode nicht erlaubt', 405);
            }
            exportGdvFile($docId, $payload);
            break;
            
        default:
            json_error('Unbekannte GDV-Aktion', 404);
    }
}

/**
 * GET /gdv/{doc_id}
 */
function getGdvMeta(string $docId, array $user): void {
    $gdvFile = Database::queryOne("
        SELECT gf.*, d.original_filename, d.created_at as document_created_at
        FROM gdv_files gf
        JOIN documents d ON gf.document_id = d.id
        WHERE gf.document_id = ?
    ", [$docId]);
    
    if (!$gdvFile) {
        json_error('GDV-Datei nicht gefunden oder noch nicht geparst', 404);
    }
    
    // Satzart-Statistik
    $stats = Database::query("
        SELECT satzart, COUNT(*) as count
        FROM gdv_records
        WHERE gdv_file_id = ?
        GROUP BY satzart
        ORDER BY satzart
    ", [$gdvFile['id']]);
    
    json_success([
        'gdv_file' => $gdvFile,
        'satzart_stats' => $stats
    ]);
}

/**
 * POST /gdv/{doc_id}/parse
 */
function parseGdvFile(string $docId, array $user): void {
    // Dokument laden
    $doc = Database::queryOne(
        'SELECT * FROM documents WHERE id = ? AND is_gdv = 1',
        [$docId]
    );
    
    if (!$doc) {
        json_error('GDV-Dokument nicht gefunden', 404);
    }
    
    $filePath = DOCUMENTS_PATH . $doc['storage_path'];
    
    if (!file_exists($filePath)) {
        json_error('Datei nicht gefunden', 404);
    }
    
    // Bestehende Parsing-Daten löschen
    $existingGdv = Database::queryOne(
        'SELECT id FROM gdv_files WHERE document_id = ?',
        [$docId]
    );
    
    if ($existingGdv) {
        Database::execute('DELETE FROM gdv_records WHERE gdv_file_id = ?', [$existingGdv['id']]);
        Database::execute('DELETE FROM gdv_files WHERE id = ?', [$existingGdv['id']]);
    }
    
    // Datei öffnen und parsen
    $content = file_get_contents($filePath);
    
    // Encoding erkennen
    $encoding = detectEncoding($content);
    if ($encoding !== 'UTF-8') {
        $content = mb_convert_encoding($content, 'UTF-8', $encoding);
    }
    
    $lines = explode("\n", $content);
    $recordCount = 0;
    $vuNumber = null;
    $releaseVersion = null;
    
    // GDV-File Eintrag erstellen
    $gdvFileId = Database::insert("
        INSERT INTO gdv_files (document_id, encoding, record_count, parsed_at)
        VALUES (?, ?, 0, NOW())
    ", [$docId, $encoding]);
    
    Database::beginTransaction();
    
    try {
        foreach ($lines as $lineNumber => $line) {
            $line = rtrim($line, "\r");
            
            if (strlen($line) < 4) {
                continue;
            }
            
            $satzart = substr($line, 0, 4);
            $teildatensatz = 1;
            
            // Teildatensatz aus Position 256 (Index 255) extrahieren falls vorhanden
            if (strlen($line) >= 256) {
                $td = substr($line, 255, 1);
                if (is_numeric($td) && $td >= '1' && $td <= '9') {
                    $teildatensatz = (int)$td;
                }
            }
            
            // VU-Nummer und Release aus Vorsatz (0001) extrahieren
            if ($satzart === '0001') {
                $vuNumber = trim(substr($line, 4, 5));
                // Release-Stand Position kann variieren
            }
            
            // Record speichern
            Database::insert("
                INSERT INTO gdv_records (gdv_file_id, line_number, satzart, teildatensatz, raw_content)
                VALUES (?, ?, ?, ?, ?)
            ", [$gdvFileId, $lineNumber + 1, $satzart, $teildatensatz, $line]);
            
            $recordCount++;
        }
        
        // GDV-File aktualisieren
        Database::execute("
            UPDATE gdv_files 
            SET record_count = ?, vu_number = ?, release_version = ?
            WHERE id = ?
        ", [$recordCount, $vuNumber, $releaseVersion, $gdvFileId]);
        
        Database::commit();
        
    } catch (Exception $e) {
        Database::rollback();
        throw $e;
    }
    
    // Audit-Log
    Database::insert(
        'INSERT INTO audit_log (user_id, action, entity_type, entity_id, details, ip_address) VALUES (?, ?, ?, ?, ?, ?)',
        [$user['user_id'], 'gdv_parse', 'gdv_file', $gdvFileId, json_encode(['records' => $recordCount]), $_SERVER['REMOTE_ADDR'] ?? '']
    );
    
    json_success([
        'gdv_file_id' => $gdvFileId,
        'record_count' => $recordCount,
        'encoding' => $encoding,
        'vu_number' => $vuNumber
    ], 'GDV-Datei geparst');
}

/**
 * GET /gdv/{doc_id}/records
 * Query: satzart, teildatensatz, limit, offset
 */
function getGdvRecords(string $docId, array $user): void {
    $gdvFile = Database::queryOne(
        'SELECT id FROM gdv_files WHERE document_id = ?',
        [$docId]
    );
    
    if (!$gdvFile) {
        json_error('GDV-Datei nicht gefunden oder noch nicht geparst', 404);
    }
    
    $conditions = ['gdv_file_id = ?'];
    $params = [$gdvFile['id']];
    
    // Filter: Satzart
    if (!empty($_GET['satzart'])) {
        $conditions[] = 'satzart = ?';
        $params[] = $_GET['satzart'];
    }
    
    // Filter: Teildatensatz
    if (!empty($_GET['teildatensatz'])) {
        $conditions[] = 'teildatensatz = ?';
        $params[] = $_GET['teildatensatz'];
    }
    
    $where = implode(' AND ', $conditions);
    $limit = min((int)($_GET['limit'] ?? 1000), 5000);
    $offset = max((int)($_GET['offset'] ?? 0), 0);
    
    $records = Database::query("
        SELECT id, line_number, satzart, teildatensatz, raw_content, parsed_fields, is_modified
        FROM gdv_records
        WHERE $where
        ORDER BY line_number
        LIMIT $limit OFFSET $offset
    ", $params);
    
    $total = Database::queryOne("SELECT COUNT(*) as cnt FROM gdv_records WHERE $where", $params);
    
    json_success([
        'records' => $records,
        'total' => $total['cnt'],
        'limit' => $limit,
        'offset' => $offset
    ]);
}

/**
 * PUT /gdv/{doc_id}/records
 * Body: { "records": [{ "id": 123, "raw_content": "..." }, ...] }
 */
function updateGdvRecords(string $docId, array $user): void {
    $gdvFile = Database::queryOne(
        'SELECT id FROM gdv_files WHERE document_id = ?',
        [$docId]
    );
    
    if (!$gdvFile) {
        json_error('GDV-Datei nicht gefunden', 404);
    }
    
    $data = get_json_body();
    require_fields($data, ['records']);
    
    $updated = 0;
    
    Database::beginTransaction();
    
    try {
        foreach ($data['records'] as $record) {
            if (!isset($record['id']) || !isset($record['raw_content'])) {
                continue;
            }
            
            $rowCount = Database::execute("
                UPDATE gdv_records 
                SET raw_content = ?, is_modified = 1
                WHERE id = ? AND gdv_file_id = ?
            ", [$record['raw_content'], $record['id'], $gdvFile['id']]);
            
            $updated += $rowCount;
        }
        
        Database::commit();
        
    } catch (Exception $e) {
        Database::rollback();
        throw $e;
    }
    
    // Audit-Log
    Database::insert(
        'INSERT INTO audit_log (user_id, action, entity_type, entity_id, details, ip_address) VALUES (?, ?, ?, ?, ?, ?)',
        [$user['user_id'], 'gdv_update', 'gdv_file', $gdvFile['id'], json_encode(['updated' => $updated]), $_SERVER['REMOTE_ADDR'] ?? '']
    );
    
    json_success(['updated' => $updated], "$updated Record(s) aktualisiert");
}

/**
 * GET /gdv/{doc_id}/export
 */
function exportGdvFile(string $docId, array $user): void {
    $gdvFile = Database::queryOne("
        SELECT gf.*, d.original_filename
        FROM gdv_files gf
        JOIN documents d ON gf.document_id = d.id
        WHERE gf.document_id = ?
    ", [$docId]);
    
    if (!$gdvFile) {
        json_error('GDV-Datei nicht gefunden', 404);
    }
    
    // Alle Records holen
    $records = Database::query("
        SELECT raw_content
        FROM gdv_records
        WHERE gdv_file_id = ?
        ORDER BY line_number
    ", [$gdvFile['id']]);
    
    // GDV-Datei zusammenbauen
    $content = '';
    foreach ($records as $record) {
        $content .= $record['raw_content'] . "\n";
    }
    
    // Encoding zurückkonvertieren
    if ($gdvFile['encoding'] !== 'UTF-8') {
        $content = mb_convert_encoding($content, $gdvFile['encoding'], 'UTF-8');
    }
    
    // Download-Header
    $filename = pathinfo($gdvFile['original_filename'], PATHINFO_FILENAME) . '_export.gdv';
    
    header('Content-Type: application/octet-stream');
    header('Content-Disposition: attachment; filename="' . $filename . '"');
    header('Content-Length: ' . strlen($content));
    
    echo $content;
    exit();
}

/**
 * Erkennt das Encoding einer Datei
 */
function detectEncoding(string $content): string {
    // Versuche verschiedene Encodings
    $encodings = ['UTF-8', 'CP1252', 'ISO-8859-1', 'ISO-8859-15'];
    
    foreach ($encodings as $encoding) {
        if (@mb_check_encoding($content, $encoding)) {
            // Prüfe auf typische deutsche Umlaute
            $test = @mb_convert_encoding($content, 'UTF-8', $encoding);
            if (preg_match('/[äöüÄÖÜß]/u', $test)) {
                return $encoding;
            }
        }
    }
    
    // Standard: CP1252 (Windows-typisch für GDV)
    return 'CP1252';
}

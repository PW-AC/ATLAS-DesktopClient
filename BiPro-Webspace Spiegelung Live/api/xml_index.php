<?php
/**
 * BiPro API - XML Index
 * 
 * Endpunkte fuer die Indexierung von BiPRO XML-Rohdateien:
 * - GET /xml_index - Liste aller indexierten XML-Dateien
 * - GET /xml_index/search - Suche in XML-Index
 * - POST /xml_index - XML-Datei indexieren
 * - GET /xml_index/{id} - Einzelnen Index-Eintrag abrufen
 * - DELETE /xml_index/{id} - Index-Eintrag loeschen
 * 
 * Diese API ist GETRENNT von documents und dient dem Rohdaten-Archiv.
 */

require_once __DIR__ . '/lib/jwt.php';
require_once __DIR__ . '/lib/response.php';

function handleXmlIndexRequest(string $idOrAction, string $method): void {
    $payload = JWT::requireAuth();
    
    switch ($method) {
        case 'GET':
            if (empty($idOrAction) || $idOrAction === 'list') {
                listXmlIndex($payload);
            } elseif ($idOrAction === 'search') {
                searchXmlIndex($payload);
            } else {
                getXmlIndexEntry($idOrAction, $payload);
            }
            break;
            
        case 'POST':
            createXmlIndexEntry($payload);
            break;
            
        case 'DELETE':
            if (empty($idOrAction)) {
                json_error('Index-ID erforderlich', 400);
            }
            deleteXmlIndexEntry($idOrAction, $payload);
            break;
            
        default:
            json_error('Methode nicht erlaubt', 405);
    }
}

/**
 * GET /xml_index
 * Listet alle indexierten XML-Dateien
 */
function listXmlIndex(array $user): void {
    $conditions = ['1=1'];
    $params = [];
    
    // Filter: VU
    if (!empty($_GET['vu_name'])) {
        $conditions[] = 'vu_name LIKE ?';
        $params[] = '%' . $_GET['vu_name'] . '%';
    }
    
    // Filter: BiPRO-Kategorie
    if (!empty($_GET['bipro_category'])) {
        $conditions[] = 'bipro_category = ?';
        $params[] = $_GET['bipro_category'];
    }
    
    // Filter: Lieferungs-ID
    if (!empty($_GET['shipment_id'])) {
        $conditions[] = 'external_shipment_id = ?';
        $params[] = $_GET['shipment_id'];
    }
    
    // Filter: Datum von
    if (!empty($_GET['from'])) {
        $conditions[] = 'shipment_date >= ?';
        $params[] = $_GET['from'];
    }
    
    // Filter: Datum bis
    if (!empty($_GET['to'])) {
        $conditions[] = 'shipment_date <= ?';
        $params[] = $_GET['to'] . ' 23:59:59';
    }
    
    // Sortierung
    $orderBy = 'created_at DESC';
    if (!empty($_GET['sort'])) {
        $allowedSorts = ['shipment_date', 'created_at', 'vu_name', 'filename'];
        $sortField = $_GET['sort'];
        $sortDir = ($_GET['dir'] ?? 'DESC') === 'ASC' ? 'ASC' : 'DESC';
        if (in_array($sortField, $allowedSorts)) {
            $orderBy = "$sortField $sortDir";
        }
    }
    
    // Pagination
    $limit = min((int)($_GET['limit'] ?? 100), 500);
    $offset = max((int)($_GET['offset'] ?? 0), 0);
    
    $whereClause = implode(' AND ', $conditions);
    
    $entries = Database::query("
        SELECT *
        FROM xml_index
        WHERE $whereClause
        ORDER BY $orderBy
        LIMIT ? OFFSET ?
    ", array_merge($params, [$limit, $offset]));
    
    // Gesamtanzahl
    $total = Database::queryOne("
        SELECT COUNT(*) as total
        FROM xml_index
        WHERE $whereClause
    ", $params);
    
    json_success([
        'entries' => $entries,
        'total' => (int)$total['total'],
        'limit' => $limit,
        'offset' => $offset
    ]);
}

/**
 * GET /xml_index/search
 * Volltextsuche in XML-Index
 */
function searchXmlIndex(array $user): void {
    $query = $_GET['q'] ?? '';
    
    if (strlen($query) < 3) {
        json_error('Suchbegriff muss mindestens 3 Zeichen haben', 400);
    }
    
    $searchTerm = '%' . $query . '%';
    
    $entries = Database::query("
        SELECT *
        FROM xml_index
        WHERE filename LIKE ?
           OR external_shipment_id LIKE ?
           OR vu_name LIKE ?
        ORDER BY created_at DESC
        LIMIT 100
    ", [$searchTerm, $searchTerm, $searchTerm]);
    
    json_success([
        'entries' => $entries,
        'query' => $query,
        'count' => count($entries)
    ]);
}

/**
 * GET /xml_index/{id}
 */
function getXmlIndexEntry(string $id, array $user): void {
    $entry = Database::queryOne(
        'SELECT * FROM xml_index WHERE id = ?',
        [$id]
    );
    
    if (!$entry) {
        json_error('Eintrag nicht gefunden', 404);
    }
    
    json_success($entry);
}

/**
 * POST /xml_index
 * Erstellt neuen Index-Eintrag
 */
function createXmlIndexEntry(array $user): void {
    $data = get_json_body();
    
    // Pflichtfelder
    $required = ['filename', 'raw_path'];
    foreach ($required as $field) {
        if (empty($data[$field])) {
            json_error("Pflichtfeld fehlt: $field", 400);
        }
    }
    
    // Content-Hash berechnen falls Datei existiert
    $contentHash = null;
    $fileSize = 0;
    $fullPath = DOCUMENTS_PATH . $data['raw_path'];
    if (file_exists($fullPath)) {
        $contentHash = hash_file('sha256', $fullPath);
        $fileSize = filesize($fullPath);
    }
    
    $id = Database::insert("
        INSERT INTO xml_index 
        (external_shipment_id, filename, raw_path, file_size, bipro_category, vu_name, content_hash, shipment_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ", [
        $data['external_shipment_id'] ?? null,
        $data['filename'],
        $data['raw_path'],
        $data['file_size'] ?? $fileSize,
        $data['bipro_category'] ?? null,
        $data['vu_name'] ?? null,
        $data['content_hash'] ?? $contentHash,
        $data['shipment_date'] ?? null
    ]);
    
    // Audit-Log
    Database::insert(
        'INSERT INTO audit_log (user_id, action, entity_type, entity_id, details, ip_address) VALUES (?, ?, ?, ?, ?, ?)',
        [$user['user_id'], 'xml_index_create', 'xml_index', $id, json_encode(['filename' => $data['filename']]), $_SERVER['REMOTE_ADDR'] ?? '']
    );
    
    json_success([
        'id' => $id,
        'filename' => $data['filename'],
        'raw_path' => $data['raw_path']
    ], 'XML indexiert');
}

/**
 * DELETE /xml_index/{id}
 */
function deleteXmlIndexEntry(string $id, array $user): void {
    $entry = Database::queryOne(
        'SELECT * FROM xml_index WHERE id = ?',
        [$id]
    );
    
    if (!$entry) {
        json_error('Eintrag nicht gefunden', 404);
    }
    
    Database::execute('DELETE FROM xml_index WHERE id = ?', [$id]);
    
    // Audit-Log
    Database::insert(
        'INSERT INTO audit_log (user_id, action, entity_type, entity_id, details, ip_address) VALUES (?, ?, ?, ?, ?, ?)',
        [$user['user_id'], 'xml_index_delete', 'xml_index', $id, json_encode(['filename' => $entry['filename']]), $_SERVER['REMOTE_ADDR'] ?? '']
    );
    
    json_success([], 'Index-Eintrag geloescht');
}

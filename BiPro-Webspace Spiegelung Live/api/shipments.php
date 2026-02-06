<?php
/**
 * BiPro API - Lieferungen (Shipments)
 * 
 * Endpunkte:
 * - GET /shipments - Liste aller Lieferungen
 * - POST /shipments - Neue Lieferung registrieren
 * - GET /shipments/{id} - Lieferungsdetails
 * - POST /shipments/{id}/acknowledge - Als quittiert markieren
 */

require_once __DIR__ . '/lib/jwt.php';
require_once __DIR__ . '/lib/response.php';

function handleShipmentsRequest(string $idOrAction, string $method): void {
    $payload = JWT::requireAuth();
    
    // Spezialfall: ID/acknowledge
    $parts = explode('/', $idOrAction);
    $id = $parts[0] ?? '';
    $subAction = $parts[1] ?? '';
    
    switch ($method) {
        case 'GET':
            if (empty($id)) {
                listShipments($payload);
            } else {
                getShipment($id, $payload);
            }
            break;
            
        case 'POST':
            if ($subAction === 'acknowledge') {
                acknowledgeShipment($id, $payload);
            } else {
                createShipment($payload);
            }
            break;
            
        default:
            json_error('Methode nicht erlaubt', 405);
    }
}

/**
 * GET /shipments
 * Query: vu_id, status, from, to
 */
function listShipments(array $user): void {
    $conditions = ['1=1'];
    $params = [];
    
    // Filter: VU
    if (!empty($_GET['vu_id'])) {
        $conditions[] = 's.vu_connection_id = ?';
        $params[] = $_GET['vu_id'];
    }
    
    // Filter: Status
    if (!empty($_GET['status'])) {
        $conditions[] = 's.status = ?';
        $params[] = $_GET['status'];
    }
    
    // Filter: Datum von
    if (!empty($_GET['from'])) {
        $conditions[] = 's.created_at >= ?';
        $params[] = $_GET['from'];
    }
    
    // Filter: Datum bis
    if (!empty($_GET['to'])) {
        $conditions[] = 's.created_at <= ?';
        $params[] = $_GET['to'] . ' 23:59:59';
    }
    
    $where = implode(' AND ', $conditions);
    
    $shipments = Database::query("
        SELECT 
            s.id,
            s.external_shipment_id,
            s.status,
            s.fetched_at,
            s.acknowledged_at,
            s.error_message,
            s.created_at,
            vc.vu_name,
            vc.vu_number,
            u.username as fetched_by_name,
            (SELECT COUNT(*) FROM documents WHERE shipment_id = s.id) as document_count
        FROM shipments s
        JOIN vu_connections vc ON s.vu_connection_id = vc.id
        LEFT JOIN users u ON s.fetched_by = u.id
        WHERE $where
        ORDER BY s.created_at DESC
        LIMIT 500
    ", $params);
    
    json_success([
        'shipments' => $shipments,
        'count' => count($shipments)
    ]);
}

/**
 * GET /shipments/{id}
 */
function getShipment(string $id, array $user): void {
    $shipment = Database::queryOne("
        SELECT 
            s.*,
            vc.vu_name,
            vc.vu_number,
            u.username as fetched_by_name
        FROM shipments s
        JOIN vu_connections vc ON s.vu_connection_id = vc.id
        LEFT JOIN users u ON s.fetched_by = u.id
        WHERE s.id = ?
    ", [$id]);
    
    if (!$shipment) {
        json_error('Lieferung nicht gefunden', 404);
    }
    
    // Zugehörige Dokumente laden
    $documents = Database::query("
        SELECT id, filename, original_filename, mime_type, file_size, is_gdv, created_at
        FROM documents
        WHERE shipment_id = ?
        ORDER BY created_at
    ", [$id]);
    
    $shipment['documents'] = $documents;
    
    json_success(['shipment' => $shipment]);
}

/**
 * POST /shipments
 * Body: { vu_connection_id, external_shipment_id, status? }
 */
function createShipment(array $user): void {
    $data = get_json_body();
    require_fields($data, ['vu_connection_id']);
    
    // Prüfen ob VU-Verbindung existiert
    $connection = Database::queryOne(
        'SELECT id FROM vu_connections WHERE id = ?',
        [$data['vu_connection_id']]
    );
    
    if (!$connection) {
        json_error('VU-Verbindung nicht gefunden', 404);
    }
    
    $status = $data['status'] ?? 'listed';
    $fetchedAt = null;
    $fetchedBy = null;
    
    if ($status === 'fetched') {
        $fetchedAt = date('Y-m-d H:i:s');
        $fetchedBy = $user['user_id'];
    }
    
    $id = Database::insert("
        INSERT INTO shipments 
        (vu_connection_id, external_shipment_id, status, fetched_at, fetched_by)
        VALUES (?, ?, ?, ?, ?)
    ", [
        $data['vu_connection_id'],
        $data['external_shipment_id'] ?? null,
        $status,
        $fetchedAt,
        $fetchedBy
    ]);
    
    // VU last_sync aktualisieren
    Database::execute(
        'UPDATE vu_connections SET last_sync = NOW() WHERE id = ?',
        [$data['vu_connection_id']]
    );
    
    // Audit-Log
    Database::insert(
        'INSERT INTO audit_log (user_id, action, entity_type, entity_id, details, ip_address) VALUES (?, ?, ?, ?, ?, ?)',
        [$user['user_id'], 'shipment_create', 'shipment', $id, json_encode(['external_id' => $data['external_shipment_id'] ?? null]), $_SERVER['REMOTE_ADDR'] ?? '']
    );
    
    json_success(['id' => $id], 'Lieferung registriert');
}

/**
 * POST /shipments/{id}/acknowledge
 */
function acknowledgeShipment(string $id, array $user): void {
    $shipment = Database::queryOne('SELECT * FROM shipments WHERE id = ?', [$id]);
    
    if (!$shipment) {
        json_error('Lieferung nicht gefunden', 404);
    }
    
    if ($shipment['status'] === 'acknowledged') {
        json_error('Lieferung bereits quittiert', 400);
    }
    
    Database::execute("
        UPDATE shipments 
        SET status = 'acknowledged', acknowledged_at = NOW()
        WHERE id = ?
    ", [$id]);
    
    // Audit-Log
    Database::insert(
        'INSERT INTO audit_log (user_id, action, entity_type, entity_id, ip_address) VALUES (?, ?, ?, ?, ?)',
        [$user['user_id'], 'shipment_acknowledge', 'shipment', $id, $_SERVER['REMOTE_ADDR'] ?? '']
    );
    
    json_success([], 'Lieferung quittiert');
}

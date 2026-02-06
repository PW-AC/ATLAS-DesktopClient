<?php
/**
 * BiPro API - VU-Verbindungen und Credentials
 * 
 * Endpunkte:
 * - GET /vu-connections - Liste aller VU-Verbindungen
 * - POST /vu-connections - Neue Verbindung anlegen
 * - GET /vu-connections/{id} - Verbindungsdetails
 * - PUT /vu-connections/{id} - Verbindung bearbeiten
 * - DELETE /vu-connections/{id} - Verbindung löschen
 * - GET /vu-connections/{id}/credentials - Credentials abrufen (SENSIBEL!)
 * - POST /vu-connections/{id}/test - Verbindung testen
 */

require_once __DIR__ . '/lib/jwt.php';
require_once __DIR__ . '/lib/crypto.php';
require_once __DIR__ . '/lib/response.php';

function handleVuConnectionsRequest(string $idOrAction, string $method): void {
    $payload = JWT::requireAuth();
    
    // Spezialfall: ID/credentials
    $parts = explode('/', $idOrAction);
    $id = $parts[0] ?? '';
    $subAction = $parts[1] ?? '';
    
    switch ($method) {
        case 'GET':
            if (empty($id)) {
                listVuConnections($payload);
            } elseif ($subAction === 'credentials') {
                getCredentials($id, $payload);
            } else {
                getVuConnection($id, $payload);
            }
            break;
            
        case 'POST':
            if ($subAction === 'test') {
                testConnection($id, $payload);
            } else {
                createVuConnection($payload);
            }
            break;
            
        case 'PUT':
            if (empty($id)) {
                json_error('ID erforderlich', 400);
            }
            updateVuConnection($id, $payload);
            break;
            
        case 'DELETE':
            if (empty($id)) {
                json_error('ID erforderlich', 400);
            }
            deleteVuConnection($id, $payload);
            break;
            
        default:
            json_error('Methode nicht erlaubt', 405);
    }
}

/**
 * GET /vu-connections
 */
function listVuConnections(array $user): void {
    $connections = Database::query("
        SELECT 
            id, vu_name, vu_number, endpoint_url, 
            sts_url, transfer_url, bipro_version,
            auth_type, auth_type_code, certificate_id,
            is_active, last_sync, created_at, note,
            use_smartadmin_flow, smartadmin_company_key, extranet_url,
            consumer_id
        FROM vu_connections
        ORDER BY vu_name
    ");
    
    // Credentials NICHT mit ausgeben!
    
    json_success([
        'connections' => $connections
    ]);
}

/**
 * GET /vu-connections/{id}
 */
function getVuConnection(string $id, array $user): void {
    $connection = Database::queryOne("
        SELECT 
            id, vu_name, vu_number, endpoint_url,
            sts_url, transfer_url, bipro_version,
            auth_type, auth_type_code, certificate_id,
            is_active, last_sync, created_at, note,
            use_smartadmin_flow, smartadmin_company_key, extranet_url,
            consumer_id
        FROM vu_connections
        WHERE id = ?
    ", [$id]);
    
    if (!$connection) {
        json_error('Verbindung nicht gefunden', 404);
    }
    
    json_success(['connection' => $connection]);
}

/**
 * POST /vu-connections
 * Body: { 
 *   vu_name, vu_number, endpoint_url, 
 *   sts_url, transfer_url, bipro_version,
 *   auth_type, auth_type_code, certificate_id, note,
 *   credentials: { username, password } 
 * }
 */
function createVuConnection(array $user): void {
    $data = get_json_body();
    require_fields($data, ['vu_name', 'auth_type']);
    
    // Mindestens eine URL erforderlich
    if (empty($data['endpoint_url']) && empty($data['sts_url']) && empty($data['transfer_url'])) {
        json_error('Mindestens eine URL (endpoint_url, sts_url oder transfer_url) erforderlich', 400);
    }
    
    // Credentials verschlüsseln (falls vorhanden)
    $encryptedCreds = null;
    if (!empty($data['credentials'])) {
        $encryptedCreds = Crypto::encryptArray($data['credentials']);
    }
    
    // Auth-Type-Code aus String ableiten falls nicht angegeben
    $authTypeCode = $data['auth_type_code'] ?? 0;
    if ($authTypeCode === 0 && isset($data['auth_type'])) {
        $authTypeCode = match($data['auth_type']) {
            'certificate', 'cert_ws' => 3,
            'cert_tgic' => 4,
            'cert_degenia' => 6,
            default => 0
        };
    }
    
    $id = Database::insert("
        INSERT INTO vu_connections 
        (vu_name, vu_number, endpoint_url, sts_url, transfer_url, bipro_version,
         auth_type, auth_type_code, certificate_id, credentials_encrypted, is_active, note,
         use_smartadmin_flow, smartadmin_company_key, extranet_url, consumer_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
    ", [
        $data['vu_name'],
        $data['vu_number'] ?? null,
        $data['endpoint_url'] ?? null,
        $data['sts_url'] ?? null,
        $data['transfer_url'] ?? null,
        $data['bipro_version'] ?? '2.6.1.1.0',
        $data['auth_type'],
        $authTypeCode,
        $data['certificate_id'] ?? null,
        $encryptedCreds,
        $data['note'] ?? null,
        $data['use_smartadmin_flow'] ?? 0,
        $data['smartadmin_company_key'] ?? null,
        $data['extranet_url'] ?? null,
        $data['consumer_id'] ?? null
    ]);
    
    // Audit-Log
    Database::insert(
        'INSERT INTO audit_log (user_id, action, entity_type, entity_id, details, ip_address) VALUES (?, ?, ?, ?, ?, ?)',
        [$user['user_id'], 'vu_connection_create', 'vu_connection', $id, json_encode(['vu_name' => $data['vu_name']]), $_SERVER['REMOTE_ADDR'] ?? '']
    );
    
    json_success(['id' => $id], 'VU-Verbindung erstellt');
}

/**
 * PUT /vu-connections/{id}
 */
function updateVuConnection(string $id, array $user): void {
    $data = get_json_body();
    
    $connection = Database::queryOne('SELECT id FROM vu_connections WHERE id = ?', [$id]);
    if (!$connection) {
        json_error('Verbindung nicht gefunden', 404);
    }
    
    $updates = [];
    $params = [];
    
    // Erweiterte Felder
    $allowedFields = [
        'vu_name', 'vu_number', 'endpoint_url', 
        'sts_url', 'transfer_url', 'bipro_version',
        'auth_type', 'auth_type_code', 'certificate_id',
        'is_active', 'note',
        'use_smartadmin_flow', 'smartadmin_company_key', 'extranet_url',
        'consumer_id'
    ];
    
    foreach ($allowedFields as $field) {
        if (array_key_exists($field, $data)) {
            $updates[] = "$field = ?";
            $params[] = $data[$field];
        }
    }
    
    // Credentials separat behandeln
    if (isset($data['credentials']) && is_array($data['credentials'])) {
        $updates[] = "credentials_encrypted = ?";
        $params[] = Crypto::encryptArray($data['credentials']);
    }
    
    if (empty($updates)) {
        json_error('Keine Änderungen', 400);
    }
    
    $params[] = $id;
    $sql = "UPDATE vu_connections SET " . implode(', ', $updates) . " WHERE id = ?";
    Database::execute($sql, $params);
    
    // Audit-Log
    Database::insert(
        'INSERT INTO audit_log (user_id, action, entity_type, entity_id, ip_address) VALUES (?, ?, ?, ?, ?)',
        [$user['user_id'], 'vu_connection_update', 'vu_connection', $id, $_SERVER['REMOTE_ADDR'] ?? '']
    );
    
    json_success([], 'VU-Verbindung aktualisiert');
}

/**
 * DELETE /vu-connections/{id}
 */
function deleteVuConnection(string $id, array $user): void {
    $connection = Database::queryOne('SELECT vu_name FROM vu_connections WHERE id = ?', [$id]);
    if (!$connection) {
        json_error('Verbindung nicht gefunden', 404);
    }
    
    Database::execute('DELETE FROM vu_connections WHERE id = ?', [$id]);
    
    // Audit-Log
    Database::insert(
        'INSERT INTO audit_log (user_id, action, entity_type, entity_id, details, ip_address) VALUES (?, ?, ?, ?, ?, ?)',
        [$user['user_id'], 'vu_connection_delete', 'vu_connection', $id, json_encode(['vu_name' => $connection['vu_name']]), $_SERVER['REMOTE_ADDR'] ?? '']
    );
    
    json_success([], 'VU-Verbindung gelöscht');
}

/**
 * GET /vu-connections/{id}/credentials
 * 
 * ACHTUNG: Gibt entschlüsselte Credentials zurück!
 * Nur für temporäre Nutzung durch Desktop-Client.
 */
function getCredentials(string $id, array $user): void {
    $connection = Database::queryOne(
        'SELECT credentials_encrypted, vu_name FROM vu_connections WHERE id = ? AND is_active = 1',
        [$id]
    );
    
    if (!$connection) {
        json_error('Verbindung nicht gefunden oder inaktiv', 404);
    }
    
    // Prüfen ob Credentials vorhanden
    if (empty($connection['credentials_encrypted'])) {
        json_error('Keine Credentials für diese Verbindung hinterlegt', 400);
    }
    
    try {
        // Credentials entschlüsseln
        $credentials = Crypto::decryptArray($connection['credentials_encrypted']);
    } catch (Exception $e) {
        json_error('Credentials konnten nicht entschlüsselt werden: ' . $e->getMessage(), 500);
    }
    
    // Audit-Log (Sensible Operation!)
    Database::insert(
        'INSERT INTO audit_log (user_id, action, entity_type, entity_id, details, ip_address) VALUES (?, ?, ?, ?, ?, ?)',
        [$user['user_id'], 'credentials_access', 'vu_connection', $id, json_encode(['vu_name' => $connection['vu_name']]), $_SERVER['REMOTE_ADDR'] ?? '']
    );
    
    json_success([
        'credentials' => $credentials
    ]);
}

/**
 * POST /vu-connections/{id}/test
 */
function testConnection(string $id, array $user): void {
    // Platzhalter - echte Implementierung würde SOAP-Anfrage machen
    // Das macht aber der Desktop-Client, nicht die PHP-API
    
    json_success([
        'message' => 'Verbindungstest muss vom Desktop-Client durchgeführt werden'
    ]);
}

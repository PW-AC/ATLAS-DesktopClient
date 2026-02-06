<?php
/**
 * BiPro API - Haupt-Router
 * 
 * Alle API-Anfragen werden über diese Datei geroutet.
 * URL-Rewriting über .htaccess leitet /api/xyz hierher.
 */

require_once __DIR__ . '/config.php';
require_once __DIR__ . '/lib/db.php';
require_once __DIR__ . '/lib/response.php';

// CORS Pre-flight Handling
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit();
}

// Route aus URL extrahieren
$route = isset($_GET['route']) ? trim($_GET['route'], '/') : '';
$method = $_SERVER['REQUEST_METHOD'];

// Route-Teile
$parts = $route ? explode('/', $route) : [];
$resource = $parts[0] ?? '';
$action = $parts[1] ?? '';
$id = $parts[2] ?? '';

// Debug-Logging (nur wenn DEBUG_MODE aktiv)
if (DEBUG_MODE) {
    error_log("API Request: $method /$route");
}

try {
    // Routing
    switch ($resource) {
        case '':
        case 'status':
            // API Status / Health Check
            json_response([
                'status' => 'ok',
                'version' => API_VERSION,
                'timestamp' => date('c')
            ]);
            break;
            
        case 'auth':
            require_once __DIR__ . '/auth.php';
            handleAuthRequest($action, $method);
            break;
            
        case 'documents':
            require_once __DIR__ . '/documents.php';
            handleDocumentsRequest($action ?: $id, $method);
            break;
            
        case 'gdv':
            require_once __DIR__ . '/gdv.php';
            handleGdvRequest($action, $id, $method);
            break;
            
        case 'vu-connections':
            require_once __DIR__ . '/credentials.php';
            // Für /vu-connections/4/credentials brauchen wir action UND id
            $vuPath = $action;
            if ($id) {
                $vuPath .= '/' . $id;
            }
            handleVuConnectionsRequest($vuPath, $method);
            break;
            
        case 'shipments':
            require_once __DIR__ . '/shipments.php';
            handleShipmentsRequest($action ?: $id, $method);
            break;
            
        case 'ai':
            require_once __DIR__ . '/ai.php';
            handleAiRequest($action, $method);
            break;
            
        case 'xml_index':
        case 'xml-index':
            require_once __DIR__ . '/xml_index.php';
            handleXmlIndexRequest($action ?: $id, $method);
            break;
            
        case 'processing_history':
        case 'processing-history':
            require_once __DIR__ . '/processing_history.php';
            handleProcessingHistoryRequest($action ?: $id, $method);
            break;
            
        default:
            json_error('Endpoint nicht gefunden', 404);
    }
} catch (PDOException $e) {
    error_log('Database Error: ' . $e->getMessage());
    json_error('Datenbankfehler', 500);
} catch (Exception $e) {
    error_log('API Error: ' . $e->getMessage());
    json_error($e->getMessage(), 400);
}

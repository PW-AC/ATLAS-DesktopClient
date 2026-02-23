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

// SV-002 Fix: Security Headers fuer alle Responses
send_security_headers();

// SV-019 Fix: Probabilistischer Log-Cleanup (1% der Requests)
require_once __DIR__ . '/lib/log_cleanup.php';
LogCleanup::maybePurge();

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
            // SV-023 Fix: API-Version nicht mehr im Health-Check exponieren
            json_response([
                'status' => 'ok',
                'timestamp' => date('c')
            ]);
            break;
            
        case 'auth':
            require_once __DIR__ . '/auth.php';
            handleAuthRequest($action, $method);
            break;
            
        case 'documents':
            require_once __DIR__ . '/documents.php';
            // /documents/{id}/history → $action=id, $id='history'
            $docSub = $parts[2] ?? null;
            handleDocumentsRequest($action ?: $id, $method, $docSub);
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
        
        case 'passwords':
            // Oeffentlicher Endpunkt: GET /passwords?type=pdf|zip
            require_once __DIR__ . '/passwords.php';
            handlePasswordsPublicRequest($method);
            break;
        
        case 'processing-settings':
            // KI-Klassifikation Einstellungen (oeffentlich: GET)
            // /processing-settings/ai
            require_once __DIR__ . '/processing_settings.php';
            handleProcessingSettingsRequest($action ?: '', $method);
            break;
        
        case 'pm':
            // Provisionsmanagement (Geschaeftsfuehrer-Ebene)
            // /pm/{action}[/{id}][/{sub}]
            require_once __DIR__ . '/provision.php';
            $pmSub = $parts[3] ?? null;
            handleProvisionRequest($action ?: null, $method, $id ?: null, $pmSub);
            break;
        
        case 'document-rules':
            // Dokumenten-Regeln (oeffentlich: GET)
            require_once __DIR__ . '/document_rules.php';
            handleDocumentRulesRequest($method);
            break;
        
        case 'smartscan':
            // SmartScan Versand + Historie
            // /smartscan/settings, /smartscan/send, /smartscan/jobs, /smartscan/jobs/{id}, /smartscan/jobs/{id}/process
            require_once __DIR__ . '/smartscan.php';
            handleSmartScanRequest($action, $id, $method);
            break;
        
        case 'email-inbox':
            // E-Mail Inbox (IMAP empfangene Mails)
            // /email-inbox, /email-inbox/{id}, /email-inbox/pending-attachments,
            // /email-inbox/attachments/{id}/download, /email-inbox/attachments/{id}/imported
            require_once __DIR__ . '/email_accounts.php';
            handleEmailInboxRequest($action ?: null, $method);
            break;
        
        case 'admin':
            // /admin/releases → separater Handler
            if ($action === 'releases') {
                require_once __DIR__ . '/releases.php';
                handleAdminReleasesRequest($id ?: null, $method);
                break;
            }
            
            // /admin/passwords → Passwort-Verwaltung
            if ($action === 'passwords') {
                require_once __DIR__ . '/passwords.php';
                handleAdminPasswordsRequest($id ?: null, $method);
                break;
            }
            
            // /admin/email-accounts → E-Mail-Konten-Verwaltung
            if ($action === 'email-accounts') {
                require_once __DIR__ . '/email_accounts.php';
                $sub = $parts[3] ?? null;
                handleAdminEmailAccountsRequest($id ?: null, $method, $sub);
                break;
            }
            
            // /admin/smartscan → SmartScan-Einstellungen
            if ($action === 'smartscan') {
                require_once __DIR__ . '/smartscan.php';
                handleAdminSmartScanRequest($id ?: null, $method);
                break;
            }
            
            // /admin/processing-settings → KI-Klassifikation Einstellungen
            // /admin/processing-settings/ai, /admin/processing-settings/prompt-versions, 
            // /admin/processing-settings/prompt-versions/{id}/activate
            if ($action === 'processing-settings') {
                require_once __DIR__ . '/processing_settings.php';
                $psSub = $parts[3] ?? null;
                handleAdminProcessingSettingsRequest($id ?: null, $method, $psSub);
                break;
            }
            
            // /admin/ai-providers → KI-Provider-Verwaltung
            // /admin/ai-providers/{id}, /admin/ai-providers/{id}/activate, /admin/ai-providers/{id}/test
            if ($action === 'ai-providers') {
                require_once __DIR__ . '/ai_providers.php';
                $apSub = $parts[3] ?? null;
                handleAdminAiProvidersRequest($id ?: null, $method, $apSub);
                break;
            }
            
            // /admin/model-pricing → Modell-Preise
            // /admin/model-pricing/{id}
            if ($action === 'model-pricing') {
                require_once __DIR__ . '/model_pricing.php';
                handleAdminModelPricingRequest($id ?: null, $method);
                break;
            }
            
            // /admin/document-rules → Dokumenten-Regeln
            if ($action === 'document-rules') {
                require_once __DIR__ . '/document_rules.php';
                handleAdminDocumentRulesRequest($method);
                break;
            }
            
            require_once __DIR__ . '/admin.php';
            // /admin/users → ('users', method, null)
            // /admin/users/5 → ('5', method, null)  [is_numeric → User-ID]
            // /admin/users/5/password → ('5', method, 'password')
            // /admin/permissions → ('permissions', method, null)
            $adminSub = $parts[3] ?? null;
            if ($action === 'users' && !empty($id)) {
                // /admin/users/{id}[/sub]
                handleAdminRequest($id, $method, $adminSub);
            } else {
                handleAdminRequest($action ?: null, $method, null);
            }
            break;
        
        case 'sessions':
            require_once __DIR__ . '/sessions.php';
            // /sessions, /sessions/{id}, /sessions/user/{userId}
            $extra = $parts[2] ?? null;
            handleSessionsRequest($action ?: null, $method, $extra);
            break;
        
        case 'activity':
            require_once __DIR__ . '/activity.php';
            handleActivityRequest($action ?: null, $method);
            break;
        
        case 'updates':
            // Oeffentlicher Update-Check (keine Auth erforderlich)
            require_once __DIR__ . '/releases.php';
            if ($action === 'check') {
                handleUpdateCheckRequest($method);
            } else {
                json_error('Unbekannte Updates-Aktion', 404);
            }
            break;
        
        case 'releases':
            require_once __DIR__ . '/releases.php';
            if ($action === 'download' && !empty($id) && is_numeric($id)) {
                // Oeffentlicher Download-Endpoint
                handleReleaseDownload((int)$id);
            } elseif (empty($action) && $method === 'GET') {
                // Oeffentliche Release-Liste (fuer Mitteilungszentrale)
                handlePublicReleasesList();
            } else {
                json_error('Unbekannte Releases-Aktion', 404);
            }
            break;
        
        case 'incoming-scans':
            // Eingehende Scan-Dokumente (Power Automate)
            // Auth: API-Key im Header X-API-Key (kein JWT)
            require_once __DIR__ . '/incoming_scans.php';
            handleIncomingScansRequest($method);
            break;
        
        case 'messages':
            // Mitteilungszentrale: System- und Admin-Mitteilungen
            // GET /messages, POST /messages, PUT /messages/read, DELETE /messages/{id}
            require_once __DIR__ . '/messages.php';
            handleMessagesRequest($action ?: '', $method);
            break;
        
        case 'chat':
            // Private 1:1 Chat-Nachrichten
            // /chat/conversations, /chat/conversations/{id}/messages, /chat/users
            require_once __DIR__ . '/chat.php';
            $chatSub = $parts[3] ?? null;
            handleChatRequest($action ?: '', $id ?: '', $method, $chatSub);
            break;
        
        case 'notifications':
            // Leichtgewichtiger Polling-Endpoint (alle 30s)
            // GET /notifications/summary
            require_once __DIR__ . '/notifications.php';
            handleNotificationsRequest($action ?: '', $method);
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

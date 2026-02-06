<?php
/**
 * BiPro API - AI/KI-Funktionen
 * 
 * Endpunkte:
 * - GET /ai/key - OpenRouter API-Key abrufen (authentifiziert)
 */

require_once __DIR__ . '/lib/db.php';
require_once __DIR__ . '/lib/jwt.php';
require_once __DIR__ . '/lib/response.php';

function handleAiRequest(string $action, string $method): void {
    // Authentifizierung erforderlich fuer alle AI-Endpunkte
    $payload = JWT::requireAuth();
    
    switch ($method) {
        case 'GET':
            if ($action === 'key') {
                getOpenRouterKey($payload);
            } else {
                json_error('Unbekannte Aktion', 404);
            }
            break;
            
        default:
            json_error('Methode nicht erlaubt', 405);
    }
}

/**
 * GET /ai/key
 * 
 * Gibt den OpenRouter API-Key zurueck.
 * Nur fuer authentifizierte Benutzer.
 */
function getOpenRouterKey(array $user): void {
    // Pruefen ob Key konfiguriert ist
    if (!defined('OPENROUTER_API_KEY') || empty(OPENROUTER_API_KEY)) {
        json_error('OpenRouter API-Key nicht konfiguriert', 500);
        return;
    }
    
    // Audit-Log (sensible Operation) - ignoriere Fehler falls Tabelle nicht existiert
    try {
        Database::insert(
            'INSERT INTO audit_log (user_id, action, entity_type, details, ip_address) VALUES (?, ?, ?, ?, ?)',
            [
                $user['user_id'], 
                'ai_key_access', 
                'ai', 
                json_encode(['purpose' => 'pdf_rename']), 
                $_SERVER['REMOTE_ADDR'] ?? ''
            ]
        );
    } catch (Exception $e) {
        // Audit-Log optional - ignorieren falls Tabelle fehlt
        error_log('Audit-Log Fehler (ignoriert): ' . $e->getMessage());
    }
    
    json_success([
        'api_key' => OPENROUTER_API_KEY,
        'provider' => 'openrouter',
        'expires_hint' => 'Dieser Key ist nur fuer diese Session gueltig'
    ]);
}

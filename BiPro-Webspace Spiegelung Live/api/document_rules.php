<?php
/**
 * Document Rules API - Dokumenten-Regeln Einstellungen
 * 
 * Oeffentliche Endpoints (JWT):
 *   GET /document-rules          - Aktive Regeln laden
 * 
 * Admin-Endpoints (requireAdmin):
 *   PUT /admin/document-rules    - Regeln speichern
 */

require_once __DIR__ . '/lib/db.php';
require_once __DIR__ . '/lib/jwt.php';
require_once __DIR__ . '/lib/response.php';
require_once __DIR__ . '/lib/permissions.php';
require_once __DIR__ . '/lib/activity_logger.php';


// Gueltige Farbnamen (synchron mit DOCUMENT_DISPLAY_COLORS im Python-Client)
define('VALID_COLORS', ['green', 'red', 'blue', 'orange', 'purple', 'pink', 'cyan', 'yellow']);

define('VALID_DUP_ACTIONS', ['none', 'color_both', 'color_new', 'delete_new', 'delete_old']);
define('VALID_PARTIAL_EMPTY_ACTIONS', ['none', 'remove_pages', 'color_file']);
define('VALID_FULL_EMPTY_ACTIONS', ['none', 'delete', 'color_file']);


// ============================================================
// Oeffentlicher Handler
// ============================================================

function handleDocumentRulesRequest(string $method): void {
    JWT::requireAuth();
    
    if ($method === 'GET') {
        getDocumentRules();
        return;
    }
    
    json_error('Methode nicht erlaubt', 405);
}


// ============================================================
// Admin Handler
// ============================================================

function handleAdminDocumentRulesRequest(string $method): void {
    $payload = requireAdmin();
    
    if ($method === 'GET') {
        getDocumentRules();
        return;
    }
    
    if ($method === 'PUT') {
        saveDocumentRules($payload);
        return;
    }
    
    json_error('Methode nicht erlaubt', 405);
}


// ============================================================
// Implementierungen
// ============================================================

function getDocumentRules(): void {
    $row = Database::queryOne("SELECT * FROM document_rules_settings WHERE id = 1");
    
    if (!$row) {
        // Fallback: Default-Werte
        $row = [
            'file_dup_action' => 'none',
            'file_dup_color' => null,
            'content_dup_action' => 'none',
            'content_dup_color' => null,
            'partial_empty_action' => 'none',
            'partial_empty_color' => null,
            'full_empty_action' => 'none',
            'full_empty_color' => null,
        ];
    }
    
    json_response([
        'success' => true,
        'data' => [
            'settings' => [
                'file_dup_action' => $row['file_dup_action'],
                'file_dup_color' => $row['file_dup_color'],
                'content_dup_action' => $row['content_dup_action'],
                'content_dup_color' => $row['content_dup_color'],
                'partial_empty_action' => $row['partial_empty_action'],
                'partial_empty_color' => $row['partial_empty_color'],
                'full_empty_action' => $row['full_empty_action'],
                'full_empty_color' => $row['full_empty_color'],
            ]
        ]
    ]);
}


function saveDocumentRules(array $payload): void {
    $data = get_json_body();
    
    $fields = [];
    $params = [];
    
    // Datei-Duplikate
    if (isset($data['file_dup_action'])) {
        if (!in_array($data['file_dup_action'], VALID_DUP_ACTIONS)) {
            json_error('Ungueltige Aktion fuer Datei-Duplikate', 400);
            return;
        }
        $fields[] = 'file_dup_action = ?';
        $params[] = $data['file_dup_action'];
    }
    if (array_key_exists('file_dup_color', $data)) {
        $color = $data['file_dup_color'];
        if ($color !== null && !in_array($color, VALID_COLORS)) {
            json_error('Ungueltige Farbe fuer Datei-Duplikate', 400);
            return;
        }
        $fields[] = 'file_dup_color = ?';
        $params[] = $color;
    }
    
    // Inhaltsduplikate
    if (isset($data['content_dup_action'])) {
        if (!in_array($data['content_dup_action'], VALID_DUP_ACTIONS)) {
            json_error('Ungueltige Aktion fuer Inhaltsduplikate', 400);
            return;
        }
        $fields[] = 'content_dup_action = ?';
        $params[] = $data['content_dup_action'];
    }
    if (array_key_exists('content_dup_color', $data)) {
        $color = $data['content_dup_color'];
        if ($color !== null && !in_array($color, VALID_COLORS)) {
            json_error('Ungueltige Farbe fuer Inhaltsduplikate', 400);
            return;
        }
        $fields[] = 'content_dup_color = ?';
        $params[] = $color;
    }
    
    // Teilweise leere Seiten
    if (isset($data['partial_empty_action'])) {
        if (!in_array($data['partial_empty_action'], VALID_PARTIAL_EMPTY_ACTIONS)) {
            json_error('Ungueltige Aktion fuer leere Seiten', 400);
            return;
        }
        $fields[] = 'partial_empty_action = ?';
        $params[] = $data['partial_empty_action'];
    }
    if (array_key_exists('partial_empty_color', $data)) {
        $color = $data['partial_empty_color'];
        if ($color !== null && !in_array($color, VALID_COLORS)) {
            json_error('Ungueltige Farbe fuer leere Seiten', 400);
            return;
        }
        $fields[] = 'partial_empty_color = ?';
        $params[] = $color;
    }
    
    // Komplett leere Dateien
    if (isset($data['full_empty_action'])) {
        if (!in_array($data['full_empty_action'], VALID_FULL_EMPTY_ACTIONS)) {
            json_error('Ungueltige Aktion fuer leere Dateien', 400);
            return;
        }
        $fields[] = 'full_empty_action = ?';
        $params[] = $data['full_empty_action'];
    }
    if (array_key_exists('full_empty_color', $data)) {
        $color = $data['full_empty_color'];
        if ($color !== null && !in_array($color, VALID_COLORS)) {
            json_error('Ungueltige Farbe fuer leere Dateien', 400);
            return;
        }
        $fields[] = 'full_empty_color = ?';
        $params[] = $color;
    }
    
    if (empty($fields)) {
        json_error('Keine Felder zum Speichern', 400);
        return;
    }
    
    // updated_by setzen
    $fields[] = 'updated_by = ?';
    $params[] = (int)$payload['user_id'];
    
    $sql = "UPDATE document_rules_settings SET " . implode(', ', $fields) . " WHERE id = 1";
    Database::execute($sql, $params);
    
    ActivityLogger::log([
        'user_id' => (int)$payload['user_id'],
        'username' => $payload['username'] ?? '',
        'action_category' => 'admin',
        'action' => 'update_document_rules',
        'description' => 'Dokumenten-Regeln aktualisiert',
        'details' => $data,
        'status' => 'success'
    ]);
    
    // Aktuelle Settings zurueckgeben
    getDocumentRules();
}

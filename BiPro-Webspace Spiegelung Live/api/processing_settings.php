<?php
/**
 * Processing Settings API - KI-Klassifikation Einstellungen
 * 
 * Oeffentliche Endpoints (JWT):
 *   GET /processing-settings/ai          - Aktive KI-Einstellungen laden
 * 
 * Admin-Endpoints (requireAdmin):
 *   GET  /admin/processing-settings/ai                    - Settings + Versionshistorie
 *   PUT  /admin/processing-settings/ai                    - Settings speichern (UPSERT + auto Versionierung)
 *   GET  /admin/processing-settings/prompt-versions       - Alle Prompt-Versionen (Filter: ?stage=stage1|stage2)
 *   POST /admin/processing-settings/prompt-versions/{id}/activate - Version aktivieren
 */

require_once __DIR__ . '/lib/db.php';
require_once __DIR__ . '/lib/jwt.php';
require_once __DIR__ . '/lib/response.php';
require_once __DIR__ . '/lib/permissions.php';
require_once __DIR__ . '/lib/activity_logger.php';


// ============================================================
// Oeffentlicher Handler
// ============================================================

function handleProcessingSettingsRequest(string $action, string $method): void {
    $payload = JWT::requireAuth();
    
    if ($action === 'ai' && $method === 'GET') {
        getProcessingAiSettings();
        return;
    }
    
    json_error('Unbekannte Aktion', 404);
}


// ============================================================
// Admin Handler
// ============================================================

function handleAdminProcessingSettingsRequest(?string $action, string $method, ?string $extra = null): void {
    $payload = requireAdmin();
    
    // GET/PUT /admin/processing-settings/ai
    if ($action === 'ai') {
        if ($method === 'GET') {
            getProcessingAiSettingsAdmin($payload);
            return;
        }
        if ($method === 'PUT') {
            saveProcessingAiSettings($payload);
            return;
        }
    }
    
    // GET /admin/processing-settings/prompt-versions?stage=...
    if ($action === 'prompt-versions' && $method === 'GET' && empty($extra)) {
        getPromptVersions();
        return;
    }
    
    // POST /admin/processing-settings/prompt-versions/{id}/activate
    if ($action === 'prompt-versions' && $method === 'POST' && !empty($extra)) {
        // $extra = version_id, pruefen ob 'activate' als naechstes Segment kommt
        $versionId = (int)$extra;
        activatePromptVersion($payload, $versionId);
        return;
    }
    
    json_error('Unbekannte Admin-Aktion', 404);
}


// ============================================================
// Interne Funktionen
// ============================================================

/**
 * Laedt die aktiven KI-Einstellungen (Single-Row, id=1).
 */
function loadAiSettings(): array {
    $row = Database::queryOne('SELECT * FROM processing_ai_settings WHERE id = 1');
    
    if (!$row) {
        return [
            'id' => null,
            'stage1_enabled' => 1,
            'stage1_model' => 'openai/gpt-4o-mini',
            'stage1_prompt' => '',
            'stage1_max_tokens' => 150,
            'stage2_enabled' => 1,
            'stage2_model' => 'openai/gpt-4o-mini',
            'stage2_prompt' => '',
            'stage2_max_tokens' => 200,
            'stage2_trigger' => 'low',
            'active_stage1_version_id' => null,
            'active_stage2_version_id' => null,
            'updated_at' => null,
            'updated_by' => null,
        ];
    }
    
    return $row;
}


/**
 * GET /processing-settings/ai (oeffentlich, JWT)
 * Liefert nur die fuer die Verarbeitung relevanten Felder.
 */
function getProcessingAiSettings(): void {
    $settings = loadAiSettings();
    
    // Nur relevante Felder fuer den document_processor
    json_success(['settings' => [
        'stage1_enabled' => (bool)$settings['stage1_enabled'],
        'stage1_model' => $settings['stage1_model'],
        'stage1_prompt' => $settings['stage1_prompt'],
        'stage1_max_tokens' => (int)$settings['stage1_max_tokens'],
        'stage2_enabled' => (bool)$settings['stage2_enabled'],
        'stage2_model' => $settings['stage2_model'],
        'stage2_prompt' => $settings['stage2_prompt'],
        'stage2_max_tokens' => (int)$settings['stage2_max_tokens'],
        'stage2_trigger' => $settings['stage2_trigger'],
    ]]);
}


/**
 * GET /admin/processing-settings/ai (Admin)
 * Liefert Settings + aktive Versionsnummern.
 */
function getProcessingAiSettingsAdmin(array $payload): void {
    $settings = loadAiSettings();
    
    // Aktive Versionsinfos dazuladen
    $stage1Version = null;
    $stage2Version = null;
    
    if (!empty($settings['active_stage1_version_id'])) {
        $stage1Version = Database::queryOne(
            'SELECT id, version_number, label, is_default, created_at FROM prompt_versions WHERE id = ?',
            [(int)$settings['active_stage1_version_id']]
        );
    }
    
    if (!empty($settings['active_stage2_version_id'])) {
        $stage2Version = Database::queryOne(
            'SELECT id, version_number, label, is_default, created_at FROM prompt_versions WHERE id = ?',
            [(int)$settings['active_stage2_version_id']]
        );
    }
    
    json_success([
        'settings' => $settings,
        'active_stage1_version' => $stage1Version,
        'active_stage2_version' => $stage2Version,
    ]);
}


/**
 * PUT /admin/processing-settings/ai (Admin)
 * Speichert Settings. Bei Prompt-Aenderung wird automatisch neue Version erstellt.
 */
function saveProcessingAiSettings(array $payload): void {
    $data = get_json_body();
    
    $allowedFields = [
        'stage1_model', 'stage1_prompt', 'stage1_max_tokens',
        'stage2_enabled', 'stage2_model', 'stage2_prompt', 'stage2_max_tokens',
        'stage2_trigger',
    ];
    
    // Validierung: stage2_trigger
    if (isset($data['stage2_trigger'])) {
        if (!in_array($data['stage2_trigger'], ['low', 'low_medium'], true)) {
            json_error('stage2_trigger muss "low" oder "low_medium" sein', 400);
        }
    }
    
    // Validierung: max_tokens
    foreach (['stage1_max_tokens', 'stage2_max_tokens'] as $field) {
        if (isset($data[$field])) {
            $val = (int)$data[$field];
            if ($val < 50 || $val > 4096) {
                json_error("$field muss zwischen 50 und 4096 liegen", 400);
            }
            $data[$field] = $val;
        }
    }
    
    // Validierung: stage2_enabled (boolean)
    if (isset($data['stage2_enabled'])) {
        $data['stage2_enabled'] = $data['stage2_enabled'] ? 1 : 0;
    }
    
    // Aktuelle Settings laden fuer Vergleich
    $current = loadAiSettings();
    $userId = $payload['user_id'] ?? null;
    
    // Auto-Versionierung: Wenn Prompt geaendert wurde, neue Version erstellen
    foreach (['stage1', 'stage2'] as $stage) {
        $promptField = "{$stage}_prompt";
        $modelField = "{$stage}_model";
        $maxTokensField = "{$stage}_max_tokens";
        
        if (isset($data[$promptField]) && $data[$promptField] !== ($current[$promptField] ?? '')) {
            // Naechste Versionsnummer ermitteln
            $maxVersion = Database::queryOne(
                'SELECT COALESCE(MAX(version_number), 0) as max_ver FROM prompt_versions WHERE stage = ?',
                [$stage]
            );
            $nextVersion = ((int)($maxVersion['max_ver'] ?? 0)) + 1;
            
            // Optionales Label aus Payload
            $label = $data["{$stage}_version_label"] ?? null;
            if (empty($label)) {
                $label = "v{$nextVersion}";
            }
            
            $model = $data[$modelField] ?? $current[$modelField] ?? 'openai/gpt-4o-mini';
            $maxTokens = $data[$maxTokensField] ?? $current[$maxTokensField] ?? 150;
            
            // Neue Version erstellen
            Database::insert(
                'INSERT INTO prompt_versions (stage, version_number, label, prompt_text, model, max_tokens, created_by)
                 VALUES (?, ?, ?, ?, ?, ?, ?)',
                [$stage, $nextVersion, $label, $data[$promptField], $model, (int)$maxTokens, $userId]
            );
            $newVersionId = Database::lastInsertId();
            
            // Active Version ID aktualisieren
            $data["active_{$stage}_version_id"] = $newVersionId;
        }
    }
    
    // UPSERT Settings
    $existing = Database::queryOne('SELECT id FROM processing_ai_settings WHERE id = 1');
    
    // Erweiterte erlaubte Felder (inkl. auto-generierte Version-IDs)
    $allFields = array_merge($allowedFields, ['active_stage1_version_id', 'active_stage2_version_id']);
    
    if ($existing) {
        $sets = [];
        $params = [];
        foreach ($allFields as $field) {
            if (array_key_exists($field, $data)) {
                $sets[] = "$field = ?";
                $params[] = $data[$field];
            }
        }
        // updated_by immer setzen
        $sets[] = "updated_by = ?";
        $params[] = $userId;
        
        if (empty($sets)) {
            json_error('Keine Aenderungen angegeben', 400);
        }
        
        $params[] = 1; // WHERE id = 1
        Database::execute(
            'UPDATE processing_ai_settings SET ' . implode(', ', $sets) . ' WHERE id = ?',
            $params
        );
    } else {
        // INSERT (sollte durch Migration bereits existieren, Fallback)
        $fields = ['id'];
        $values = [1];
        $placeholders = ['?'];
        foreach ($allFields as $field) {
            if (array_key_exists($field, $data)) {
                $fields[] = $field;
                $values[] = $data[$field];
                $placeholders[] = '?';
            }
        }
        $fields[] = 'updated_by';
        $values[] = $userId;
        $placeholders[] = '?';
        
        Database::insert(
            'INSERT INTO processing_ai_settings (' . implode(', ', $fields) . ')
             VALUES (' . implode(', ', $placeholders) . ')',
            $values
        );
    }
    
    // Activity-Logging
    $changedFields = array_keys(array_intersect_key($data, array_flip($allFields)));
    ActivityLogger::logAdmin($payload, 'processing_ai_settings_saved', 'processing_ai_settings', 1,
        'KI-Klassifikation Einstellungen gespeichert',
        ['changed_fields' => $changedFields]
    );
    
    // Aktualisierte Settings zurueckgeben
    $settings = loadAiSettings();
    json_success(['settings' => $settings], 'KI-Einstellungen gespeichert');
}


/**
 * GET /admin/processing-settings/prompt-versions?stage=stage1|stage2
 */
function getPromptVersions(): void {
    $stage = $_GET['stage'] ?? null;
    
    $query = 'SELECT id, stage, version_number, label, prompt_text, model, max_tokens, 
              created_by, created_at, is_default 
              FROM prompt_versions';
    $params = [];
    
    if ($stage && in_array($stage, ['stage1', 'stage2'], true)) {
        $query .= ' WHERE stage = ?';
        $params[] = $stage;
    }
    
    $query .= ' ORDER BY stage ASC, version_number DESC';
    
    $rows = Database::query($query, $params);
    
    // Benutzernamen dazuladen
    $userIds = array_filter(array_unique(array_column($rows, 'created_by')));
    $userNames = [];
    if (!empty($userIds)) {
        $placeholders = implode(',', array_fill(0, count($userIds), '?'));
        $users = Database::query(
            "SELECT id, username FROM users WHERE id IN ($placeholders)",
            array_values($userIds)
        );
        foreach ($users as $u) {
            $userNames[(int)$u['id']] = $u['username'];
        }
    }
    
    // Username an Versionen anfuegen
    foreach ($rows as &$row) {
        $row['created_by_username'] = $userNames[(int)($row['created_by'] ?? 0)] ?? null;
    }
    unset($row);
    
    json_success(['versions' => $rows]);
}


/**
 * POST /admin/processing-settings/prompt-versions/{id}/activate
 * Aktiviert eine gespeicherte Prompt-Version.
 */
function activatePromptVersion(array $payload, int $versionId): void {
    // Version laden
    $version = Database::queryOne(
        'SELECT * FROM prompt_versions WHERE id = ?',
        [$versionId]
    );
    
    if (!$version) {
        json_error('Prompt-Version nicht gefunden', 404);
    }
    
    $stage = $version['stage']; // 'stage1' oder 'stage2'
    $userId = $payload['user_id'] ?? null;
    
    // Settings aktualisieren: Prompt, Model, max_tokens und active_version_id
    Database::execute(
        "UPDATE processing_ai_settings 
         SET {$stage}_prompt = ?, {$stage}_model = ?, {$stage}_max_tokens = ?,
             active_{$stage}_version_id = ?, updated_by = ?
         WHERE id = 1",
        [$version['prompt_text'], $version['model'], (int)$version['max_tokens'], $versionId, $userId]
    );
    
    // Activity-Logging
    ActivityLogger::logAdmin($payload, 'prompt_version_activated', 'prompt_versions', $versionId,
        "Prompt-Version aktiviert: {$stage} v{$version['version_number']} ({$version['label']})",
        ['stage' => $stage, 'version_number' => $version['version_number']]
    );
    
    $settings = loadAiSettings();
    $label = $version['label'] ?: "v{$version['version_number']}";
    json_success(['settings' => $settings], "Version \"$label\" aktiviert");
}

<?php
/**
 * BiPro API - KI-Provider-Verwaltung
 *
 * Verwaltet API-Keys fuer OpenRouter und OpenAI.
 * Keys werden mit AES-256-GCM verschluesselt in der DB gespeichert.
 *
 * Endpunkte:
 * - GET /ai/provider                          - Aktiven Provider abrufen (Public, JWT)
 * - GET /admin/ai-providers                    - Alle Keys auflisten (Admin)
 * - POST /admin/ai-providers                   - Neuen Key anlegen (Admin)
 * - PUT /admin/ai-providers/{id}               - Key bearbeiten (Admin)
 * - DELETE /admin/ai-providers/{id}            - Key loeschen (Admin)
 * - POST /admin/ai-providers/{id}/activate     - Key aktivieren (Admin)
 * - POST /admin/ai-providers/{id}/test         - Key testen (Admin)
 */

require_once __DIR__ . '/lib/db.php';
require_once __DIR__ . '/lib/jwt.php';
require_once __DIR__ . '/lib/response.php';
require_once __DIR__ . '/lib/permissions.php';
require_once __DIR__ . '/lib/activity_logger.php';
require_once __DIR__ . '/lib/crypto.php';

/**
 * Oeffentlicher Endpunkt: GET /ai/provider
 */
function handleAiProviderPublicRequest(string $method): void {
    if ($method !== 'GET') {
        json_error('Methode nicht erlaubt', 405);
    }

    JWT::requireAuth();

    $row = Database::queryOne(
        'SELECT id, provider_type, name FROM ai_provider_keys WHERE is_active = 1 LIMIT 1'
    );

    if ($row) {
        json_success([
            'provider' => $row['provider_type'],
            'name' => $row['name'],
            'id' => (int)$row['id']
        ]);
    } else {
        json_success(['provider' => null, 'name' => null, 'id' => null]);
    }
}

/**
 * Admin-Endpunkte: /admin/ai-providers
 */
function handleAdminAiProvidersRequest(?string $id, string $method, ?string $sub = null): void {
    $user = requireAdmin();

    if ($id && $sub === 'activate' && $method === 'POST') {
        handleActivateProvider((int)$id, $user);
        return;
    }
    if ($id && $sub === 'test' && $method === 'POST') {
        handleTestProvider((int)$id);
        return;
    }

    switch ($method) {
        case 'GET':
            handleListProviders();
            break;
        case 'POST':
            handleCreateProvider($user);
            break;
        case 'PUT':
            if (!$id) json_error('ID erforderlich', 400);
            handleUpdateProvider((int)$id, $user);
            break;
        case 'DELETE':
            if (!$id) json_error('ID erforderlich', 400);
            handleDeleteProvider((int)$id, $user);
            break;
        default:
            json_error('Methode nicht erlaubt', 405);
    }
}

function handleListProviders(): void {
    $rows = Database::query(
        'SELECT id, provider_type, name, api_key_encrypted, is_active, created_at, updated_at, created_by
         FROM ai_provider_keys ORDER BY is_active DESC, created_at DESC'
    );

    $providers = [];
    foreach ($rows as $row) {
        $providers[] = formatProviderRow($row);
    }

    json_success($providers);
}

function handleCreateProvider(array $user): void {
    $data = get_json_body();
    require_fields($data, ['provider_type', 'name', 'api_key']);

    $providerType = $data['provider_type'];
    if (!in_array($providerType, ['openrouter', 'openai'])) {
        json_error('Ungueltiger Provider-Typ', 400);
    }

    $encrypted = Crypto::encrypt($data['api_key']);

    $newId = Database::insert(
        'INSERT INTO ai_provider_keys (provider_type, name, api_key_encrypted, is_active, created_by) VALUES (?, ?, ?, 0, ?)',
        [$providerType, $data['name'], $encrypted, $user['user_id']]
    );

    ActivityLogger::log([
        'user_id' => $user['user_id'],
        'username' => $user['username'] ?? '',
        'action_category' => 'admin',
        'action' => 'ai_provider_created',
        'entity_type' => 'ai_provider',
        'entity_id' => $newId,
        'description' => "KI-Provider '{$data['name']}' ({$providerType}) erstellt",
    ]);

    $row = Database::queryOne('SELECT * FROM ai_provider_keys WHERE id = ?', [$newId]);
    json_success(formatProviderRow($row), 201);
}

function handleUpdateProvider(int $id, array $user): void {
    $existing = Database::queryOne('SELECT * FROM ai_provider_keys WHERE id = ?', [$id]);
    if (!$existing) json_error('Provider nicht gefunden', 404);

    $data = get_json_body();
    $updates = [];
    $params = [];

    if (isset($data['name'])) {
        $updates[] = 'name = ?';
        $params[] = $data['name'];
    }
    if (isset($data['provider_type']) && in_array($data['provider_type'], ['openrouter', 'openai'])) {
        $updates[] = 'provider_type = ?';
        $params[] = $data['provider_type'];
    }
    if (isset($data['api_key']) && !empty($data['api_key'])) {
        $updates[] = 'api_key_encrypted = ?';
        $params[] = Crypto::encrypt($data['api_key']);
    }

    if (empty($updates)) {
        json_error('Keine Aenderungen', 400);
    }

    $params[] = $id;
    Database::execute(
        'UPDATE ai_provider_keys SET ' . implode(', ', $updates) . ' WHERE id = ?',
        $params
    );

    ActivityLogger::log([
        'user_id' => $user['user_id'],
        'username' => $user['username'] ?? '',
        'action_category' => 'admin',
        'action' => 'ai_provider_updated',
        'entity_type' => 'ai_provider',
        'entity_id' => $id,
        'description' => "KI-Provider #{$id} aktualisiert",
    ]);

    $row = Database::queryOne('SELECT * FROM ai_provider_keys WHERE id = ?', [$id]);
    json_success(formatProviderRow($row));
}

function handleDeleteProvider(int $id, array $user): void {
    $existing = Database::queryOne('SELECT * FROM ai_provider_keys WHERE id = ?', [$id]);
    if (!$existing) json_error('Provider nicht gefunden', 404);

    if ($existing['is_active']) {
        json_error('Aktiver Provider kann nicht geloescht werden. Zuerst anderen aktivieren.', 400);
    }

    Database::execute('DELETE FROM ai_provider_keys WHERE id = ?', [$id]);

    ActivityLogger::log([
        'user_id' => $user['user_id'],
        'username' => $user['username'] ?? '',
        'action_category' => 'admin',
        'action' => 'ai_provider_deleted',
        'entity_type' => 'ai_provider',
        'entity_id' => $id,
        'description' => "KI-Provider '{$existing['name']}' geloescht",
    ]);

    json_success(['deleted' => true]);
}

function handleActivateProvider(int $id, array $user): void {
    $existing = Database::queryOne('SELECT * FROM ai_provider_keys WHERE id = ?', [$id]);
    if (!$existing) json_error('Provider nicht gefunden', 404);

    Database::execute('UPDATE ai_provider_keys SET is_active = 0');
    Database::execute('UPDATE ai_provider_keys SET is_active = 1 WHERE id = ?', [$id]);

    ActivityLogger::log([
        'user_id' => $user['user_id'],
        'username' => $user['username'] ?? '',
        'action_category' => 'admin',
        'action' => 'ai_provider_activated',
        'entity_type' => 'ai_provider',
        'entity_id' => $id,
        'description' => "KI-Provider '{$existing['name']}' ({$existing['provider_type']}) aktiviert",
    ]);

    json_success(['activated' => true, 'provider_type' => $existing['provider_type']]);
}

function handleTestProvider(int $id): void {
    $existing = Database::queryOne('SELECT * FROM ai_provider_keys WHERE id = ?', [$id]);
    if (!$existing) json_error('Provider nicht gefunden', 404);

    $apiKey = Crypto::decrypt($existing['api_key_encrypted']);
    $providerType = $existing['provider_type'];

    if ($providerType === 'openrouter') {
        $ch = curl_init();
        curl_setopt_array($ch, [
            CURLOPT_URL => 'https://openrouter.ai/api/v1/credits',
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_HTTPHEADER => ['Authorization: Bearer ' . $apiKey],
            CURLOPT_TIMEOUT => 15,
            CURLOPT_SSL_VERIFYPEER => true
        ]);
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        if ($httpCode === 200) {
            json_success(['success' => true, 'message' => 'OpenRouter API-Key gueltig']);
        } else {
            json_success(['success' => false, 'error' => "HTTP {$httpCode}"]);
        }
    } elseif ($providerType === 'openai') {
        $ch = curl_init();
        curl_setopt_array($ch, [
            CURLOPT_URL => 'https://api.openai.com/v1/models',
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_HTTPHEADER => ['Authorization: Bearer ' . $apiKey],
            CURLOPT_TIMEOUT => 15,
            CURLOPT_SSL_VERIFYPEER => true
        ]);
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        if ($httpCode === 200) {
            json_success(['success' => true, 'message' => 'OpenAI API-Key gueltig']);
        } else {
            json_success(['success' => false, 'error' => "HTTP {$httpCode}"]);
        }
    } else {
        json_error('Unbekannter Provider-Typ', 400);
    }
}

/**
 * Gibt den aktiven Provider mit entschluesseltem Key zurueck.
 * Fuer internen Server-Gebrauch (ai.php).
 */
function getActiveProvider(): ?array {
    $row = Database::queryOne(
        'SELECT id, provider_type, name, api_key_encrypted FROM ai_provider_keys WHERE is_active = 1 LIMIT 1'
    );
    if (!$row) return null;

    return [
        'id' => (int)$row['id'],
        'type' => $row['provider_type'],
        'name' => $row['name'],
        'api_key' => Crypto::decrypt($row['api_key_encrypted'])
    ];
}

function formatProviderRow(array $row): array {
    $key = Crypto::decrypt($row['api_key_encrypted']);
    $masked = substr($key, 0, 8) . '***' . substr($key, -4);

    return [
        'id' => (int)$row['id'],
        'provider_type' => $row['provider_type'],
        'name' => $row['name'],
        'api_key_masked' => $masked,
        'is_active' => (bool)(int)$row['is_active'],
        'created_at' => $row['created_at'],
        'updated_at' => $row['updated_at'] ?? null,
        'created_by' => $row['created_by'] ? (int)$row['created_by'] : null,
    ];
}

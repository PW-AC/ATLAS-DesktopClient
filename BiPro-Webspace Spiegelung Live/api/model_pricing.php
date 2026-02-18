<?php
/**
 * BiPro API - Modell-Preise und Kosten-Tracking
 *
 * Verwaltet Modell-Preise ($ pro 1M Tokens) fuer Kostenberechnung.
 * Stellt Helper-Funktionen fuer ai.php bereit (getModelPricing, calculateCost, logAiRequest).
 *
 * Endpunkte:
 * - GET /ai/pricing               - Aktive Preise abrufen (fuer Client)
 * - GET /admin/model-pricing       - Alle Preise auflisten (Admin)
 * - POST /admin/model-pricing      - Neuen Preis anlegen (Admin)
 * - PUT /admin/model-pricing/{id}  - Preis bearbeiten (Admin)
 * - DELETE /admin/model-pricing/{id} - Preis deaktivieren (Admin)
 */

require_once __DIR__ . '/lib/db.php';
require_once __DIR__ . '/lib/jwt.php';
require_once __DIR__ . '/lib/response.php';
require_once __DIR__ . '/lib/permissions.php';
require_once __DIR__ . '/lib/activity_logger.php';

/**
 * Oeffentlicher Endpunkt: GET /ai/pricing
 */
function handleModelPricingPublicRequest(string $method): void {
    if ($method !== 'GET') {
        json_error('Methode nicht erlaubt', 405);
    }

    JWT::requireAuth();

    $rows = Database::query(
        'SELECT provider, model_name, input_price_per_million, output_price_per_million, valid_from
         FROM model_pricing
         WHERE is_active = 1
         ORDER BY provider, model_name'
    );

    $prices = [];
    foreach ($rows as $row) {
        $prices[] = [
            'provider' => $row['provider'],
            'model' => $row['model_name'],
            'input_price_per_million' => (float)$row['input_price_per_million'],
            'output_price_per_million' => (float)$row['output_price_per_million'],
            'valid_from' => $row['valid_from']
        ];
    }

    json_success(['prices' => $prices]);
}

/**
 * Admin-Endpunkte: /admin/model-pricing
 */
function handleAdminModelPricingRequest(?string $id, string $method): void {
    $user = requireAdmin();

    switch ($method) {
        case 'GET':
            handleListPricing();
            break;
        case 'POST':
            handleCreatePricing($user);
            break;
        case 'PUT':
            if (!$id) json_error('ID erforderlich', 400);
            handleUpdatePricing((int)$id, $user);
            break;
        case 'DELETE':
            if (!$id) json_error('ID erforderlich', 400);
            handleDeletePricing((int)$id, $user);
            break;
        default:
            json_error('Methode nicht erlaubt', 405);
    }
}

function handleListPricing(): void {
    $rows = Database::query(
        'SELECT id, provider, model_name, input_price_per_million, output_price_per_million,
                valid_from, is_active, created_at, updated_at
         FROM model_pricing ORDER BY provider, model_name, valid_from DESC'
    );

    $prices = [];
    foreach ($rows as $row) {
        $prices[] = formatPricingRow($row);
    }

    json_success($prices);
}

function handleCreatePricing(array $user): void {
    $data = get_json_body();
    require_fields($data, ['provider', 'model_name', 'input_price_per_million', 'output_price_per_million']);

    if (!in_array($data['provider'], ['openrouter', 'openai'])) {
        json_error('Ungueltiger Provider', 400);
    }

    $validFrom = $data['valid_from'] ?? date('Y-m-d');

    $newId = Database::insert(
        'INSERT INTO model_pricing (provider, model_name, input_price_per_million, output_price_per_million, valid_from)
         VALUES (?, ?, ?, ?, ?)',
        [
            $data['provider'],
            $data['model_name'],
            (float)$data['input_price_per_million'],
            (float)$data['output_price_per_million'],
            $validFrom
        ]
    );

    ActivityLogger::log([
        'user_id' => $user['user_id'],
        'username' => $user['username'] ?? '',
        'action_category' => 'admin',
        'action' => 'model_pricing_created',
        'entity_type' => 'model_pricing',
        'entity_id' => $newId,
        'description' => "Modell-Preis '{$data['model_name']}' ({$data['provider']}) erstellt",
    ]);

    $row = Database::queryOne('SELECT * FROM model_pricing WHERE id = ?', [$newId]);
    json_success(formatPricingRow($row), 201);
}

function handleUpdatePricing(int $id, array $user): void {
    $existing = Database::queryOne('SELECT * FROM model_pricing WHERE id = ?', [$id]);
    if (!$existing) json_error('Preis nicht gefunden', 404);

    $data = get_json_body();
    $updates = [];
    $params = [];

    foreach (['model_name', 'provider'] as $field) {
        if (isset($data[$field])) {
            $updates[] = "$field = ?";
            $params[] = $data[$field];
        }
    }
    foreach (['input_price_per_million', 'output_price_per_million'] as $field) {
        if (isset($data[$field])) {
            $updates[] = "$field = ?";
            $params[] = (float)$data[$field];
        }
    }
    if (isset($data['valid_from'])) {
        $updates[] = 'valid_from = ?';
        $params[] = $data['valid_from'];
    }
    if (isset($data['is_active'])) {
        $updates[] = 'is_active = ?';
        $params[] = (int)$data['is_active'];
    }

    if (empty($updates)) {
        json_error('Keine Aenderungen', 400);
    }

    $params[] = $id;
    Database::execute(
        'UPDATE model_pricing SET ' . implode(', ', $updates) . ' WHERE id = ?',
        $params
    );

    ActivityLogger::log([
        'user_id' => $user['user_id'],
        'username' => $user['username'] ?? '',
        'action_category' => 'admin',
        'action' => 'model_pricing_updated',
        'entity_type' => 'model_pricing',
        'entity_id' => $id,
        'description' => "Modell-Preis #{$id} aktualisiert",
    ]);

    $row = Database::queryOne('SELECT * FROM model_pricing WHERE id = ?', [$id]);
    json_success(formatPricingRow($row));
}

function handleDeletePricing(int $id, array $user): void {
    $existing = Database::queryOne('SELECT * FROM model_pricing WHERE id = ?', [$id]);
    if (!$existing) json_error('Preis nicht gefunden', 404);

    Database::execute('UPDATE model_pricing SET is_active = 0 WHERE id = ?', [$id]);

    ActivityLogger::log([
        'user_id' => $user['user_id'],
        'username' => $user['username'] ?? '',
        'action_category' => 'admin',
        'action' => 'model_pricing_deactivated',
        'entity_type' => 'model_pricing',
        'entity_id' => $id,
        'description' => "Modell-Preis '{$existing['model_name']}' deaktiviert",
    ]);

    json_success(['deactivated' => true]);
}

// ================================================================
// Helper-Funktionen (fuer ai.php)
// ================================================================

/**
 * Gibt Input/Output-Preis fuer ein Modell zurueck.
 */
function getModelPricing(string $provider, string $model): array {
    $row = Database::queryOne(
        'SELECT input_price_per_million, output_price_per_million
         FROM model_pricing
         WHERE provider = ? AND model_name = ? AND is_active = 1
         ORDER BY valid_from DESC LIMIT 1',
        [$provider, $model]
    );

    if ($row) {
        return [
            'input_price' => (float)$row['input_price_per_million'],
            'output_price' => (float)$row['output_price_per_million']
        ];
    }

    // Fallback: Modellname ohne Provider-Prefix suchen
    $baseModel = $model;
    if (strpos($model, '/') !== false) {
        $baseModel = explode('/', $model, 2)[1];
    }

    $row = Database::queryOne(
        'SELECT input_price_per_million, output_price_per_million
         FROM model_pricing
         WHERE model_name = ? AND is_active = 1
         ORDER BY valid_from DESC LIMIT 1',
        [$baseModel]
    );

    if ($row) {
        return [
            'input_price' => (float)$row['input_price_per_million'],
            'output_price' => (float)$row['output_price_per_million']
        ];
    }

    return ['input_price' => 0.0, 'output_price' => 0.0];
}

/**
 * Berechnet Kosten aus Token-Counts und Preisen.
 */
function calculateCost(int $promptTokens, int $completionTokens, float $inputPrice, float $outputPrice): float {
    $inputCost = ($promptTokens / 1000000) * $inputPrice;
    $outputCost = ($completionTokens / 1000000) * $outputPrice;
    return round($inputCost + $outputCost, 6);
}

/**
 * Loggt einen KI-Request in die ai_requests Tabelle.
 */
function logAiRequest(array $data): void {
    try {
        Database::execute(
            'INSERT INTO ai_requests (user_id, provider, model, context, document_id,
             prompt_tokens, completion_tokens, total_tokens, estimated_cost_usd, real_cost_usd)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            [
                $data['user_id'],
                $data['provider'],
                $data['model'],
                $data['context'] ?? null,
                $data['document_id'] ?? null,
                $data['prompt_tokens'] ?? 0,
                $data['completion_tokens'] ?? 0,
                $data['total_tokens'] ?? 0,
                $data['estimated_cost_usd'] ?? null,
                $data['real_cost_usd'] ?? 0,
            ]
        );
    } catch (\Exception $e) {
        error_log("AI-Request-Logging fehlgeschlagen: " . $e->getMessage());
    }
}

function formatPricingRow(array $row): array {
    return [
        'id' => (int)$row['id'],
        'provider' => $row['provider'],
        'model_name' => $row['model_name'],
        'input_price_per_million' => (float)$row['input_price_per_million'],
        'output_price_per_million' => (float)$row['output_price_per_million'],
        'valid_from' => $row['valid_from'],
        'is_active' => (bool)(int)$row['is_active'],
        'created_at' => $row['created_at'] ?? null,
        'updated_at' => $row['updated_at'] ?? null,
    ];
}

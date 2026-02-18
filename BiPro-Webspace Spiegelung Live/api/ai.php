<?php
/**
 * BiPro API - AI/KI-Funktionen
 * 
 * Server-seitiger Proxy fuer KI-Anfragen.
 * Routet dynamisch an den aktiven Provider (OpenRouter oder OpenAI).
 * Loggt jeden Request mit Token-Counts und Kosten in ai_requests.
 * 
 * Endpunkte:
 * - POST /ai/classify   - KI-Klassifikation via Server-Proxy
 * - GET /ai/credits      - Provider-Credits/Usage abfragen
 * - GET /ai/provider     - Aktiven Provider-Typ abrufen (delegiert an ai_providers.php)
 * - GET /ai/pricing      - Aktive Modell-Preise abrufen (delegiert an model_pricing.php)
 * - GET /ai/requests     - KI-Request-Historie (Admin)
 * - GET /ai/key          - ENTFERNT (SV-004)
 */

require_once __DIR__ . '/lib/db.php';
require_once __DIR__ . '/lib/jwt.php';
require_once __DIR__ . '/lib/response.php';
require_once __DIR__ . '/lib/permissions.php';
require_once __DIR__ . '/lib/activity_logger.php';
require_once __DIR__ . '/ai_providers.php';
require_once __DIR__ . '/model_pricing.php';

function handleAiRequest(string $action, string $method): void {
    switch ($action) {
        case 'provider':
            handleAiProviderPublicRequest($method);
            return;
            
        case 'pricing':
            handleModelPricingPublicRequest($method);
            return;
            
        case 'requests':
            $payload = requireAdmin();
            handleAiRequestsHistory($method, $payload);
            return;
    }
    
    $payload = requirePermission('documents_process');
    
    switch ($method) {
        case 'GET':
            if ($action === 'credits') {
                getProviderCredits($payload);
            } elseif ($action === 'key') {
                json_error('API-Key-Endpunkt ist deaktiviert. Nutze POST /ai/classify.', 410);
            } else {
                json_error('Unbekannte Aktion', 404);
            }
            break;
            
        case 'POST':
            if ($action === 'classify') {
                handleClassify($payload);
            } else {
                json_error('Unbekannte Aktion', 404);
            }
            break;
            
        default:
            json_error('Methode nicht erlaubt', 405);
    }
}

/**
 * POST /ai/classify
 * 
 * Server-seitiger Proxy. Leitet an den aktiven Provider weiter.
 * Loggt jeden Request mit Token-Counts und Kosten in ai_requests.
 */
function handleClassify(array $user): void {
    $provider = getActiveProvider();
    if (!$provider) {
        if (defined('OPENROUTER_API_KEY') && !empty(OPENROUTER_API_KEY)) {
            $provider = [
                'id' => 0,
                'type' => 'openrouter',
                'name' => 'Legacy (config.php)',
                'api_key' => OPENROUTER_API_KEY
            ];
        } else {
            json_error('Kein KI-Provider konfiguriert. Bitte im Admin-Bereich einrichten.', 500);
            return;
        }
    }
    
    $data = get_json_body();
    require_fields($data, ['messages', 'model']);
    
    $messages = $data['messages'];
    $model = $data['model'];
    $maxTokens = isset($data['max_tokens']) ? (int)$data['max_tokens'] : 200;
    $responseFormat = $data['response_format'] ?? null;
    $estimatedCost = $data['estimated_cost'] ?? null;
    $context = $data['context'] ?? null;
    $documentId = $data['document_id'] ?? null;
    
    $messages = redact_pii_in_messages($messages);
    
    error_log("ATLAS: KI-Request - Provider: {$provider['type']} ({$provider['name']}), Modell: {$model}");
    
    $mappedModel = mapModelName($model, $provider['type']);
    
    $payload = [
        'model' => $mappedModel,
        'messages' => $messages,
        'max_tokens' => min($maxTokens, 4096)
    ];
    
    if ($responseFormat) {
        $payload['response_format'] = $responseFormat;
    }
    
    $result = callProvider($provider, $payload);
    
    if ($result === null) {
        json_error('KI-Anfrage an ' . $provider['type'] . ' fehlgeschlagen', 502);
        return;
    }
    
    $usage = $result['usage'] ?? [];
    $promptTokens = $usage['prompt_tokens'] ?? 0;
    $completionTokens = $usage['completion_tokens'] ?? 0;
    $totalTokens = $usage['total_tokens'] ?? ($promptTokens + $completionTokens);
    
    $pricing = getModelPricing($provider['type'], $model);
    $realCost = calculateCost($promptTokens, $completionTokens, $pricing['input_price'], $pricing['output_price']);
    
    logAiRequest([
        'user_id' => $user['user_id'],
        'provider' => $provider['type'],
        'model' => $model,
        'context' => $context,
        'document_id' => $documentId,
        'prompt_tokens' => $promptTokens,
        'completion_tokens' => $completionTokens,
        'total_tokens' => $totalTokens,
        'estimated_cost_usd' => $estimatedCost,
        'real_cost_usd' => $realCost
    ]);
    
    $result['_cost'] = [
        'real_cost_usd' => $realCost,
        'estimated_cost_usd' => $estimatedCost,
        'prompt_tokens' => $promptTokens,
        'completion_tokens' => $completionTokens,
        'provider' => $provider['type']
    ];
    
    ActivityLogger::log([
        'user_id' => $user['user_id'],
        'username' => $user['username'] ?? '',
        'action_category' => 'ai',
        'action' => 'classify',
        'entity_type' => 'ai',
        'description' => "KI-Klassifikation via {$provider['type']} (Modell: {$model}, Kosten: \${$realCost})",
        'details' => ['model' => $model, 'max_tokens' => $maxTokens, 'provider' => $provider['type'], 'cost_usd' => $realCost]
    ]);
    
    json_success($result);
}

/**
 * GET /ai/credits - Provider-abhaengige Credits/Usage-Abfrage.
 */
function getProviderCredits(array $user): void {
    $provider = getActiveProvider();
    if (!$provider) {
        if (defined('OPENROUTER_API_KEY') && !empty(OPENROUTER_API_KEY)) {
            $provider = ['type' => 'openrouter', 'api_key' => OPENROUTER_API_KEY];
        } else {
            json_error('Kein KI-Provider konfiguriert', 500);
            return;
        }
    }
    
    if ($provider['type'] === 'openrouter') {
        getOpenRouterCredits_internal($provider['api_key']);
    } elseif ($provider['type'] === 'openai') {
        getOpenAIUsage($provider['api_key']);
    } else {
        json_error('Unbekannter Provider-Typ', 500);
    }
}

function getOpenRouterCredits_internal(string $apiKey): void {
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
    $error = curl_error($ch);
    curl_close($ch);
    
    if ($error || $httpCode !== 200) {
        json_error('Credits-Abfrage fehlgeschlagen: ' . ($error ?: "HTTP {$httpCode}"), 502);
        return;
    }
    
    $raw = json_decode($response, true);
    $data = $raw['data'] ?? $raw;
    $data['provider'] = 'openrouter';
    json_success($data);
}

function getOpenAIUsage(string $apiKey): void {
    $startDate = date('Y-m-01');
    $endDate = date('Y-m-d');
    
    $url = "https://api.openai.com/dashboard/billing/usage?start_date={$startDate}&end_date={$endDate}";
    
    $ch = curl_init();
    curl_setopt_array($ch, [
        CURLOPT_URL => $url,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_HTTPHEADER => ['Authorization: Bearer ' . $apiKey],
        CURLOPT_TIMEOUT => 15,
        CURLOPT_SSL_VERIFYPEER => true
    ]);
    
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $error = curl_error($ch);
    curl_close($ch);
    
    if ($error || $httpCode >= 400) {
        json_success([
            'provider' => 'openai',
            'total_usage' => null,
            'period' => "{$startDate} bis {$endDate}",
            'error' => 'Billing-API nicht verfuegbar'
        ]);
        return;
    }
    
    $raw = json_decode($response, true);
    $usageCents = $raw['total_usage'] ?? 0;
    $usageDollars = $usageCents / 100;
    
    json_success([
        'provider' => 'openai',
        'total_usage' => round($usageDollars, 4),
        'period' => "{$startDate} bis {$endDate}"
    ]);
}

/**
 * GET /ai/requests - KI-Request-Historie (Admin).
 */
function handleAiRequestsHistory(string $method, array $user): void {
    if ($method !== 'GET') {
        json_error('Methode nicht erlaubt', 405);
    }
    
    $limit = isset($_GET['limit']) ? min((int)$_GET['limit'], 1000) : 200;
    $period = $_GET['period'] ?? 'all';
    
    $where = '';
    $params = [];
    if ($period === '7') {
        $where = 'WHERE ar.created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)';
    } elseif ($period === '30') {
        $where = 'WHERE ar.created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)';
    } elseif ($period === '90') {
        $where = 'WHERE ar.created_at >= DATE_SUB(NOW(), INTERVAL 90 DAY)';
    }
    
    $rows = Database::query(
        "SELECT ar.*, u.username
         FROM ai_requests ar
         LEFT JOIN users u ON ar.user_id = u.id
         {$where}
         ORDER BY ar.created_at DESC
         LIMIT " . (int)$limit
    );
    
    $requests = [];
    foreach ($rows as $row) {
        $requests[] = [
            'id' => (int)$row['id'],
            'user_id' => (int)$row['user_id'],
            'username' => $row['username'] ?? 'Unbekannt',
            'provider' => $row['provider'],
            'model' => $row['model'],
            'context' => $row['context'],
            'document_id' => $row['document_id'] ? (int)$row['document_id'] : null,
            'prompt_tokens' => (int)$row['prompt_tokens'],
            'completion_tokens' => (int)$row['completion_tokens'],
            'total_tokens' => (int)$row['total_tokens'],
            'estimated_cost_usd' => $row['estimated_cost_usd'] !== null ? (float)$row['estimated_cost_usd'] : null,
            'real_cost_usd' => (float)$row['real_cost_usd'],
            'created_at' => $row['created_at'],
        ];
    }
    
    json_success(['requests' => $requests]);
}

// ================================================================
// PII-Redaktion
// ================================================================

function redact_pii_in_messages(array $messages): array {
    foreach ($messages as &$msg) {
        if (isset($msg['content']) && is_string($msg['content'])) {
            $msg['content'] = redact_pii($msg['content']);
        }
    }
    return $messages;
}

function redact_pii(string $text): string {
    $text = preg_replace('/[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/', '[EMAIL]', $text);
    $text = preg_replace('/[A-Z]{2}\d{2}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{0,2}/', '[IBAN]', $text);
    $text = preg_replace('/(?:\+49|0049|0)\s*[\d\s\-\/\.]{8,15}/', '[PHONE]', $text);
    return $text;
}

// ================================================================
// Provider-Aufrufe
// ================================================================

function callProvider(array $provider, array $payload): ?array {
    if ($provider['type'] === 'openrouter') {
        return callOpenRouterProvider($provider['api_key'], $payload);
    } elseif ($provider['type'] === 'openai') {
        return callOpenAIProvider($provider['api_key'], $payload);
    }
    error_log("Unbekannter Provider-Typ: {$provider['type']}");
    return null;
}

function callOpenRouterProvider(string $apiKey, array $payload): ?array {
    $ch = curl_init();
    curl_setopt_array($ch, [
        CURLOPT_URL => 'https://openrouter.ai/api/v1/chat/completions',
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => json_encode($payload),
        CURLOPT_HTTPHEADER => [
            'Authorization: Bearer ' . $apiKey,
            'Content-Type: application/json',
            'HTTP-Referer: https://acencia.info',
            'X-Title: ACENCIA ATLAS'
        ],
        CURLOPT_TIMEOUT => 120,
        CURLOPT_SSL_VERIFYPEER => true
    ]);
    
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $error = curl_error($ch);
    curl_close($ch);
    
    if ($error) {
        error_log("OpenRouter cURL-Fehler: {$error}");
        return null;
    }
    if ($httpCode >= 400) {
        error_log("OpenRouter HTTP-Fehler: {$httpCode} - {$response}");
        return null;
    }
    
    return json_decode($response, true);
}

function callOpenAIProvider(string $apiKey, array $payload): ?array {
    $model = $payload['model'] ?? 'unknown';
    error_log("ATLAS: OpenAI-Request gestartet - Modell: {$model}, URL: https://api.openai.com/v1/chat/completions");
    
    $ch = curl_init();
    curl_setopt_array($ch, [
        CURLOPT_URL => 'https://api.openai.com/v1/chat/completions',
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => json_encode($payload),
        CURLOPT_HTTPHEADER => [
            'Authorization: Bearer ' . $apiKey,
            'Content-Type: application/json'
        ],
        CURLOPT_TIMEOUT => 120,
        CURLOPT_SSL_VERIFYPEER => true
    ]);
    
    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $error = curl_error($ch);
    curl_close($ch);
    
    if ($error) {
        error_log("ATLAS: OpenAI cURL-Fehler: {$error}");
        return null;
    }
    if ($httpCode >= 400) {
        error_log("ATLAS: OpenAI HTTP-Fehler: {$httpCode} - {$response}");
        return null;
    }
    
    error_log("ATLAS: OpenAI-Response OK - HTTP {$httpCode}, Modell: {$model}");
    return json_decode($response, true);
}

/**
 * Modellname mappen: OpenRouter-Format <-> OpenAI-Format.
 */
function mapModelName(string $model, string $providerType): string {
    if ($providerType === 'openai') {
        if (strpos($model, 'openai/') === 0) {
            return substr($model, 7);
        }
        if (strpos($model, '/') !== false) {
            error_log("WARNUNG: Nicht-OpenAI-Modell '{$model}' bei OpenAI-Provider");
            return $model;
        }
    }
    return $model;
}

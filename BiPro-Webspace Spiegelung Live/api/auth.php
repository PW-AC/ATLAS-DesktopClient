<?php
/**
 * BiPro API - Authentifizierung
 * 
 * Endpunkte:
 * - POST /auth/login - Login
 * - POST /auth/logout - Logout (Token invalidieren)
 * - GET /auth/verify - Token prüfen
 * - GET /auth/me - Aktueller User
 */

require_once __DIR__ . '/lib/jwt.php';
require_once __DIR__ . '/lib/crypto.php';
require_once __DIR__ . '/lib/response.php';

function handleAuthRequest(string $action, string $method): void {
    switch ($action) {
        case 'login':
            if ($method !== 'POST') {
                json_error('Methode nicht erlaubt', 405);
            }
            handleLogin();
            break;
            
        case 'logout':
            if ($method !== 'POST') {
                json_error('Methode nicht erlaubt', 405);
            }
            handleLogout();
            break;
            
        case 'verify':
            if ($method !== 'GET') {
                json_error('Methode nicht erlaubt', 405);
            }
            handleVerify();
            break;
            
        case 'me':
            if ($method !== 'GET') {
                json_error('Methode nicht erlaubt', 405);
            }
            handleMe();
            break;
            
        default:
            json_error('Unbekannte Auth-Aktion', 404);
    }
}

/**
 * POST /auth/login
 * Body: { "username": "...", "password": "..." }
 */
function handleLogin(): void {
    $data = get_json_body();
    require_fields($data, ['username', 'password']);
    
    $username = trim($data['username']);
    $password = $data['password'];
    
    // User aus DB holen
    $user = Database::queryOne(
        'SELECT id, username, password_hash, email, is_active FROM users WHERE username = ?',
        [$username]
    );
    
    if (!$user) {
        // Timing-Attack verhindern
        Crypto::verifyPassword($password, '$argon2id$v=19$m=65536,t=4,p=3$dummy');
        json_error('Ungültige Anmeldedaten', 401);
    }
    
    if (!$user['is_active']) {
        json_error('Benutzer ist deaktiviert', 403);
    }
    
    if (!Crypto::verifyPassword($password, $user['password_hash'])) {
        // Login-Versuch loggen
        Database::insert(
            'INSERT INTO audit_log (user_id, action, details, ip_address) VALUES (?, ?, ?, ?)',
            [$user['id'], 'login_failed', json_encode(['reason' => 'wrong_password']), $_SERVER['REMOTE_ADDR'] ?? '']
        );
        json_error('Ungültige Anmeldedaten', 401);
    }
    
    // Token erstellen
    $token = JWT::create([
        'user_id' => $user['id'],
        'username' => $user['username']
    ]);
    
    // Login loggen
    Database::insert(
        'INSERT INTO audit_log (user_id, action, ip_address) VALUES (?, ?, ?)',
        [$user['id'], 'login_success', $_SERVER['REMOTE_ADDR'] ?? '']
    );
    
    json_success([
        'token' => $token,
        'user' => [
            'id' => $user['id'],
            'username' => $user['username'],
            'email' => $user['email']
        ],
        'expires_in' => JWT_EXPIRY
    ], 'Login erfolgreich');
}

/**
 * POST /auth/logout
 */
function handleLogout(): void {
    $payload = JWT::requireAuth();
    
    // Logout loggen
    Database::insert(
        'INSERT INTO audit_log (user_id, action, ip_address) VALUES (?, ?, ?)',
        [$payload['user_id'], 'logout', $_SERVER['REMOTE_ADDR'] ?? '']
    );
    
    // Bei JWT gibt es kein echtes "Invalidieren" ohne Blacklist
    // Der Client muss den Token einfach löschen
    
    json_success([], 'Logout erfolgreich');
}

/**
 * GET /auth/verify
 */
function handleVerify(): void {
    $token = JWT::getTokenFromHeader();
    
    if (!$token) {
        json_response(['valid' => false, 'reason' => 'no_token']);
    }
    
    $payload = JWT::verify($token);
    
    if (!$payload) {
        json_response(['valid' => false, 'reason' => 'invalid_or_expired']);
    }
    
    json_response([
        'valid' => true,
        'user_id' => $payload['user_id'],
        'username' => $payload['username'],
        'expires_at' => date('c', $payload['exp'])
    ]);
}

/**
 * GET /auth/me
 */
function handleMe(): void {
    $payload = JWT::requireAuth();
    
    $user = Database::queryOne(
        'SELECT id, username, email, created_at FROM users WHERE id = ?',
        [$payload['user_id']]
    );
    
    if (!$user) {
        json_error('Benutzer nicht gefunden', 404);
    }
    
    json_success([
        'user' => $user
    ]);
}

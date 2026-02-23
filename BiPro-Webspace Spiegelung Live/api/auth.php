<?php
/**
 * BiPro API - Authentifizierung
 * 
 * Endpunkte:
 * - POST /auth/login - Login (erstellt Session)
 * - POST /auth/logout - Logout (invalidiert Session)
 * - GET /auth/verify - Token prüfen
 * - GET /auth/me - Aktueller User mit Permissions
 */

require_once __DIR__ . '/lib/jwt.php';
require_once __DIR__ . '/lib/crypto.php';
require_once __DIR__ . '/lib/response.php';
require_once __DIR__ . '/lib/activity_logger.php';
require_once __DIR__ . '/lib/permissions.php';

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
 * 
 * Response enthaelt jetzt account_type und permissions.
 */
function handleLogin(): void {
    $data = get_json_body();
    require_fields($data, ['username', 'password']);
    
    $username = trim($data['username']);
    $password = $data['password'];
    
    // SV-003 Fix: Rate-Limiting vor Login-Logik (Baustein B2)
    require_once __DIR__ . '/lib/rate_limiter.php';
    $clientIp = $_SERVER['REMOTE_ADDR'] ?? '0.0.0.0';
    if (!RateLimiter::check($clientIp)) {
        $remaining = RateLimiter::getLockoutRemaining($clientIp);
        header('Retry-After: ' . max(1, $remaining));
        ActivityLogger::log([
            'user_id' => null,
            'username' => $username,
            'action_category' => 'auth',
            'action' => 'login_rate_limited',
            'description' => "Login blockiert: Rate-Limit fuer IP {$clientIp}",
            'details' => ['ip' => $clientIp, 'remaining_seconds' => $remaining],
            'status' => 'error'
        ]);
        json_error('Zu viele fehlgeschlagene Anmeldeversuche. Bitte warten.', 429);
    }
    
    // User aus DB holen (erweitert um account_type, is_locked)
    $user = Database::queryOne(
        'SELECT id, username, password_hash, email, account_type, is_active, is_locked FROM users WHERE username = ?',
        [$username]
    );
    
    if (!$user) {
        // Timing-Attack verhindern
        Crypto::verifyPassword($password, '$argon2id$v=19$m=65536,t=4,p=3$dummy');
        
        // SV-003: Fehlgeschlagenen Versuch fuer Rate-Limiting zaehlen
        RateLimiter::recordFailure($clientIp, $username);
        
        // Fehlgeschlagenen Login loggen (ohne user_id)
        ActivityLogger::log([
            'user_id' => null,
            'username' => $username,
            'action_category' => 'auth',
            'action' => 'login_failed',
            'description' => "Login fehlgeschlagen: Unbekannter Benutzer '{$username}'",
            'details' => ['reason' => 'user_not_found'],
            'status' => 'error'
        ]);
        
        json_error('Ungültige Anmeldedaten', 401);
    }
    
    if (!$user['is_active']) {
        ActivityLogger::logAuth($user['id'], $username, 'login_failed', "Login fehlgeschlagen: Benutzer deaktiviert", 'error', ['reason' => 'inactive']);
        json_error('Benutzer ist deaktiviert', 403);
    }
    
    if ($user['is_locked']) {
        ActivityLogger::logAuth($user['id'], $username, 'login_failed', "Login fehlgeschlagen: Benutzer gesperrt", 'error', ['reason' => 'locked']);
        json_error('Benutzer ist gesperrt', 403);
    }
    
    if (!Crypto::verifyPassword($password, $user['password_hash'])) {
        // SV-003: Fehlgeschlagenen Versuch fuer Rate-Limiting zaehlen
        RateLimiter::recordFailure($clientIp, $username);
        ActivityLogger::logAuth($user['id'], $username, 'login_failed', "Login fehlgeschlagen: Falsches Passwort", 'error', ['reason' => 'wrong_password']);
        json_error('Ungültige Anmeldedaten', 401);
    }
    
    // SV-003: Rate-Limit-Counter nach erfolgreichem Login zuruecksetzen
    RateLimiter::reset($clientIp);
    
    // Single-Session-Enforcement: Alle bestehenden Sessions des Nutzers beenden
    // Ein Nutzer darf nur eine aktive Session gleichzeitig haben
    $invalidatedCount = JWT::invalidateAllUserSessions($user['id']);
    if ($invalidatedCount > 0) {
        ActivityLogger::logAuth($user['id'], $username, 'sessions_invalidated', 
            "Bestehende Sessions beendet bei Neuanmeldung ({$invalidatedCount} Session(s))",
            'info', ['invalidated_count' => $invalidatedCount]);
    }
    
    // Token erstellen
    $token = JWT::create([
        'user_id' => $user['id'],
        'username' => $user['username']
    ]);
    
    // Session in DB erstellen (einzige aktive Session fuer diesen Nutzer)
    JWT::createSession($token, $user['id']);
    
    // last_login_at aktualisieren
    Database::execute(
        'UPDATE users SET last_login_at = NOW() WHERE id = ?',
        [$user['id']]
    );
    
    // Effektive Permissions laden (Admins: Standard auto-granted + explizite Provision-Perms)
    $permissions = getEffectivePermissions($user['id']);
    
    // Login loggen
    ActivityLogger::logAuth($user['id'], $username, 'login_success', "Erfolgreich angemeldet");
    
    // Abgelaufene Sessions aufraeumen (Housekeeping, max alle 100 Logins)
    if (rand(1, 100) === 1) {
        JWT::cleanupExpiredSessions();
    }
    
    json_success([
        'token' => $token,
        'user' => [
            'id' => $user['id'],
            'username' => $user['username'],
            'email' => $user['email'],
            'account_type' => $user['account_type'],
            'permissions' => $permissions
        ],
        'expires_in' => JWT_EXPIRY
    ], 'Login erfolgreich');
}

/**
 * POST /auth/logout
 * Invalidiert die aktuelle Session.
 */
function handleLogout(): void {
    $token = JWT::getTokenFromHeader();
    
    if ($token) {
        $payload = JWT::verify($token);
        
        // Session invalidieren
        JWT::invalidateSession($token);
        
        if ($payload) {
            // Logout loggen
            ActivityLogger::logAuth(
                $payload['user_id'],
                $payload['username'] ?? '',
                'logout',
                "Abgemeldet"
            );
        }
    }
    
    json_success([], 'Logout erfolgreich');
}

/**
 * GET /auth/verify
 * Prueft Token-Gueltigkeit inkl. Session.
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
    
    // Session-Check
    $tokenHash = hash('sha256', $token);
    $session = Database::queryOne(
        'SELECT s.is_active, u.is_active as user_active, u.is_locked, u.account_type
         FROM sessions s
         JOIN users u ON u.id = s.user_id
         WHERE s.token_hash = ?',
        [$tokenHash]
    );
    
    if (!$session || !$session['is_active'] || !$session['user_active'] || $session['is_locked']) {
        $reason = 'session_invalid';
        if ($session && !$session['is_active']) $reason = 'session_ended';
        if ($session && !$session['user_active']) $reason = 'user_inactive';
        if ($session && $session['is_locked']) $reason = 'user_locked';
        json_response(['valid' => false, 'reason' => $reason]);
    }
    
    // Effektive Permissions laden (Admins: Standard auto-granted + explizite Provision-Perms)
    $permissions = getEffectivePermissions($payload['user_id']);
    
    json_response([
        'valid' => true,
        'user_id' => $payload['user_id'],
        'username' => $payload['username'],
        'account_type' => $session['account_type'],
        'permissions' => $permissions,
        'expires_at' => date('c', $payload['exp'])
    ]);
}

/**
 * GET /auth/me
 * Gibt aktuelle User-Daten mit Permissions zurueck.
 */
function handleMe(): void {
    $payload = JWT::requireAuth();
    
    $user = Database::queryOne(
        'SELECT id, username, email, account_type, is_active, is_locked, last_login_at, created_at 
         FROM users WHERE id = ?',
        [$payload['user_id']]
    );
    
    if (!$user) {
        json_error('Benutzer nicht gefunden', 404);
    }
    
    // Effektive Permissions laden (Admins: Standard auto-granted + explizite Provision-Perms)
    $permissions = getEffectivePermissions($user['id']);
    $user['permissions'] = $permissions;
    
    json_success([
        'user' => $user
    ]);
}

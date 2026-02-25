<?php
/**
 * BiPro API - Administration / Nutzerverwaltung
 * 
 * NUR fuer Administratoren zugaenglich.
 * 
 * Endpunkte:
 * - GET    /admin/users              - Alle Nutzer auflisten
 * - GET    /admin/users/{id}         - Einzelnen Nutzer abrufen
 * - POST   /admin/users              - Nutzer erstellen
 * - PUT    /admin/users/{id}         - Nutzer bearbeiten
 * - PUT    /admin/users/{id}/password - Passwort aendern
 * - PUT    /admin/users/{id}/lock    - Nutzer sperren
 * - PUT    /admin/users/{id}/unlock  - Nutzer entsperren
 * - DELETE /admin/users/{id}         - Nutzer deaktivieren
 * - GET    /admin/permissions        - Alle Rechte auflisten
 */

require_once __DIR__ . '/lib/db.php';
require_once __DIR__ . '/lib/jwt.php';
require_once __DIR__ . '/lib/crypto.php';
require_once __DIR__ . '/lib/response.php';
require_once __DIR__ . '/lib/permissions.php';
require_once __DIR__ . '/lib/activity_logger.php';

function handleAdminRequest(?string $action, string $method, ?string $extra = null): void {
    // Alle Admin-Endpunkte erfordern Admin-Rechte
    $payload = requireAdmin();
    
    // Route: /admin/permissions
    if ($action === 'permissions') {
        if ($method === 'GET') {
            handleListPermissions();
            return;
        }
        json_error('Methode nicht erlaubt', 405);
    }
    
    // Route: /admin/users
    if ($action === 'users' || $action === null) {
        handleUsersRoute($method, $extra, $payload);
        return;
    }
    
    // Route: /admin/users/{id} - wenn action numerisch ist
    if (is_numeric($action)) {
        handleUsersRoute($method, $action, $payload, $extra);
        return;
    }
    
    json_error('Unbekannte Admin-Aktion', 404);
}

/**
 * Routet Users-Anfragen basierend auf Methode und Sub-Action.
 */
function handleUsersRoute(string $method, ?string $idOrAction, array $adminPayload, ?string $subAction = null): void {
    // GET /admin/users - Liste
    if ($method === 'GET' && ($idOrAction === null || $idOrAction === 'users')) {
        handleListUsers();
        return;
    }
    
    // POST /admin/users - Erstellen
    if ($method === 'POST' && ($idOrAction === null || $idOrAction === 'users')) {
        handleCreateUser($adminPayload);
        return;
    }
    
    // Ab hier brauchen wir eine User-ID
    $userId = is_numeric($idOrAction) ? (int)$idOrAction : null;
    
    if (!$userId) {
        json_error('User-ID erforderlich', 400);
    }
    
    // Sub-Action Routing
    if ($subAction === 'password' && $method === 'PUT') {
        handleChangePassword($userId, $adminPayload);
        return;
    }
    
    if ($subAction === 'lock' && $method === 'PUT') {
        handleLockUser($userId, $adminPayload);
        return;
    }
    
    if ($subAction === 'unlock' && $method === 'PUT') {
        handleUnlockUser($userId, $adminPayload);
        return;
    }
    
    // GET /admin/users/{id}
    if ($method === 'GET') {
        handleGetUser($userId);
        return;
    }
    
    // PUT /admin/users/{id}
    if ($method === 'PUT') {
        handleUpdateUser($userId, $adminPayload);
        return;
    }
    
    // DELETE /admin/users/{id}
    if ($method === 'DELETE') {
        handleDeleteUser($userId, $adminPayload);
        return;
    }
    
    json_error('Methode nicht erlaubt', 405);
}

/**
 * GET /admin/users - Alle Nutzer auflisten
 */
function handleListUsers(): void {
    $users = Database::query(
        'SELECT u.id, u.username, u.email, u.account_type, u.update_channel, u.is_active, u.is_locked,
                u.last_login_at, u.created_at,
                (SELECT MAX(s.last_activity_at) FROM sessions s WHERE s.user_id = u.id AND s.is_active = 1) as last_activity
         FROM users u
         ORDER BY u.id ASC'
    );
    
    // Permissions pro User laden
    foreach ($users as &$user) {
        $user['permissions'] = getUserPermissions($user['id']);
    }
    unset($user);
    
    json_success(['users' => $users]);
}

/**
 * GET /admin/users/{id} - Einzelnen Nutzer abrufen
 */
function handleGetUser(int $userId): void {
    $user = Database::queryOne(
        'SELECT id, username, email, account_type, update_channel, is_active, is_locked, last_login_at, created_at
         FROM users WHERE id = ?',
        [$userId]
    );

    if (!$user) {
        json_error('Benutzer nicht gefunden', 404);
    }
    
    $user['permissions'] = getUserPermissions($userId);
    
    // Aktive Sessions zaehlen
    $sessionCount = Database::queryOne(
        'SELECT COUNT(*) as count FROM sessions WHERE user_id = ? AND is_active = 1 AND expires_at > NOW()',
        [$userId]
    );
    $user['active_sessions'] = (int)($sessionCount['count'] ?? 0);
    
    json_success(['user' => $user]);
}

/**
 * POST /admin/users - Neuen Nutzer erstellen
 * Body: { username, email, password, account_type, permissions: [] }
 */
function handleCreateUser(array $adminPayload): void {
    $data = get_json_body();
    require_fields($data, ['username', 'password']);
    
    $username = trim($data['username']);
    $email = trim($data['email'] ?? '');
    $password = $data['password'];
    $accountType = $data['account_type'] ?? 'user';
    $permissions = $data['permissions'] ?? [];
    
    // Validierung
    if (strlen($username) < 3) {
        json_error('Benutzername muss mindestens 3 Zeichen lang sein', 400);
    }
    
    if (strlen($password) < 8) {
        json_error('Passwort muss mindestens 8 Zeichen lang sein', 400);
    }
    
    if (!in_array($accountType, ['admin', 'user'])) {
        json_error('Ungueltiger Kontotyp', 400);
    }
    
    // Pruefen ob Username bereits existiert
    $existing = Database::queryOne('SELECT id FROM users WHERE username = ?', [$username]);
    if ($existing) {
        json_error('Benutzername bereits vergeben', 409);
    }
    
    // User erstellen
    $passwordHash = Crypto::hashPassword($password);
    $userId = Database::insert(
        'INSERT INTO users (username, password_hash, email, account_type, is_active) VALUES (?, ?, ?, ?, 1)',
        [$username, $passwordHash, $email, $accountType]
    );
    
    // Permissions setzen (auch fuer Admins, da Provision-Perms explizit sein muessen)
    if (!empty($permissions)) {
        if (!hasPermission($adminPayload['user_id'], 'provision_manage')) {
            $permissions = array_values(array_filter($permissions, function($p) {
                return !in_array($p, PROVISION_PERMISSIONS);
            }));
        }
        setUserPermissions($userId, $permissions, $adminPayload['user_id']);
    }
    
    // Activity Log
    ActivityLogger::logAdmin($adminPayload, 'user_created', 'user', $userId,
        "Benutzer '{$username}' erstellt (Typ: {$accountType})",
        ['username' => $username, 'account_type' => $accountType, 'permissions' => $permissions]
    );
    
    json_success([
        'user' => [
            'id' => $userId,
            'username' => $username,
            'email' => $email,
            'account_type' => $accountType,
            'permissions' => $permissions
        ]
    ], 'Benutzer erstellt');
}

/**
 * PUT /admin/users/{id} - Nutzer bearbeiten
 * Body: { email?, account_type?, update_channel?, permissions?: [] }
 */
function handleUpdateUser(int $userId, array $adminPayload): void {
    $user = Database::queryOne('SELECT id, username, account_type FROM users WHERE id = ?', [$userId]);
    if (!$user) {
        json_error('Benutzer nicht gefunden', 404);
    }
    
    $data = get_json_body();
    $changes = [];
    
    // E-Mail aendern
    if (isset($data['email'])) {
        Database::execute('UPDATE users SET email = ? WHERE id = ?', [trim($data['email']), $userId]);
        $changes['email'] = trim($data['email']);
    }
    
    // Kontotyp aendern
    if (isset($data['account_type']) && in_array($data['account_type'], ['admin', 'user'])) {
        Database::execute('UPDATE users SET account_type = ? WHERE id = ?', [$data['account_type'], $userId]);
        $changes['account_type'] = $data['account_type'];
    }
    
    // Update-Channel aendern
    if (isset($data['update_channel']) && in_array($data['update_channel'], ['stable', 'beta', 'dev'])) {
        Database::execute('UPDATE users SET update_channel = ? WHERE id = ?', [$data['update_channel'], $userId]);
        $changes['update_channel'] = $data['update_channel'];
    }
    
    // Permissions aendern
    if (isset($data['permissions']) && is_array($data['permissions'])) {
        $permissions = $data['permissions'];
        if (!hasPermission($adminPayload['user_id'], 'provision_manage')) {
            $currentPerms = getUserPermissions($userId);
            $currentProvision = array_intersect($currentPerms, PROVISION_PERMISSIONS);
            $permissions = array_values(array_filter($permissions, function($p) {
                return !in_array($p, PROVISION_PERMISSIONS);
            }));
            $permissions = array_values(array_merge($permissions, $currentProvision));
        }
        setUserPermissions($userId, $permissions, $adminPayload['user_id']);
        $changes['permissions'] = $permissions;
    }
    
    // Activity Log
    ActivityLogger::logAdmin($adminPayload, 'user_updated', 'user', $userId,
        "Benutzer '{$user['username']}' bearbeitet",
        ['changes' => $changes]
    );
    
    // Aktualisierte Daten zurueckgeben
    $updatedUser = Database::queryOne(
        'SELECT id, username, email, account_type, update_channel, is_active, is_locked FROM users WHERE id = ?',
        [$userId]
    );
    $updatedUser['permissions'] = getUserPermissions($userId);
    
    json_success(['user' => $updatedUser], 'Benutzer aktualisiert');
}

/**
 * PUT /admin/users/{id}/password - Passwort aendern
 * Body: { new_password }
 */
function handleChangePassword(int $userId, array $adminPayload): void {
    $user = Database::queryOne('SELECT id, username FROM users WHERE id = ?', [$userId]);
    if (!$user) {
        json_error('Benutzer nicht gefunden', 404);
    }
    
    $data = get_json_body();
    require_fields($data, ['new_password']);
    
    $newPassword = $data['new_password'];
    if (strlen($newPassword) < 8) {
        json_error('Passwort muss mindestens 8 Zeichen lang sein', 400);
    }
    
    $passwordHash = Crypto::hashPassword($newPassword);
    Database::execute('UPDATE users SET password_hash = ? WHERE id = ?', [$passwordHash, $userId]);
    
    // Alle Sessions invalidieren (Passwort geaendert -> neu einloggen)
    $invalidated = JWT::invalidateAllUserSessions($userId);
    
    // Activity Log
    ActivityLogger::logAdmin($adminPayload, 'password_changed', 'user', $userId,
        "Passwort fuer '{$user['username']}' geaendert ({$invalidated} Sessions invalidiert)",
        ['sessions_invalidated' => $invalidated]
    );
    
    json_success([], "Passwort geaendert, {$invalidated} Session(s) beendet");
}

/**
 * PUT /admin/users/{id}/lock - Nutzer sperren
 */
function handleLockUser(int $userId, array $adminPayload): void {
    $user = Database::queryOne('SELECT id, username, is_locked FROM users WHERE id = ?', [$userId]);
    if (!$user) {
        json_error('Benutzer nicht gefunden', 404);
    }
    
    // Selbst-Sperre verhindern
    if ($userId === $adminPayload['user_id']) {
        json_error('Sie koennen sich nicht selbst sperren', 400);
    }
    
    if ($user['is_locked']) {
        json_error('Benutzer ist bereits gesperrt', 400);
    }
    
    Database::execute('UPDATE users SET is_locked = 1 WHERE id = ?', [$userId]);
    
    // Alle Sessions invalidieren
    $invalidated = JWT::invalidateAllUserSessions($userId);
    
    // Activity Log
    ActivityLogger::logAdmin($adminPayload, 'user_locked', 'user', $userId,
        "Benutzer '{$user['username']}' gesperrt ({$invalidated} Sessions beendet)",
        ['sessions_invalidated' => $invalidated]
    );
    
    json_success([], "Benutzer gesperrt, {$invalidated} Session(s) beendet");
}

/**
 * PUT /admin/users/{id}/unlock - Nutzer entsperren
 */
function handleUnlockUser(int $userId, array $adminPayload): void {
    $user = Database::queryOne('SELECT id, username, is_locked FROM users WHERE id = ?', [$userId]);
    if (!$user) {
        json_error('Benutzer nicht gefunden', 404);
    }
    
    if (!$user['is_locked']) {
        json_error('Benutzer ist nicht gesperrt', 400);
    }
    
    Database::execute('UPDATE users SET is_locked = 0 WHERE id = ?', [$userId]);
    
    // Activity Log
    ActivityLogger::logAdmin($adminPayload, 'user_unlocked', 'user', $userId,
        "Benutzer '{$user['username']}' entsperrt"
    );
    
    json_success([], 'Benutzer entsperrt');
}

/**
 * DELETE /admin/users/{id} - Nutzer deaktivieren (Soft-Delete)
 */
function handleDeleteUser(int $userId, array $adminPayload): void {
    $user = Database::queryOne('SELECT id, username FROM users WHERE id = ?', [$userId]);
    if (!$user) {
        json_error('Benutzer nicht gefunden', 404);
    }
    
    // Selbst-Loeschung verhindern
    if ($userId === $adminPayload['user_id']) {
        json_error('Sie koennen sich nicht selbst deaktivieren', 400);
    }
    
    Database::execute('UPDATE users SET is_active = 0 WHERE id = ?', [$userId]);
    
    // Alle Sessions invalidieren
    $invalidated = JWT::invalidateAllUserSessions($userId);
    
    // Activity Log
    ActivityLogger::logAdmin($adminPayload, 'user_deactivated', 'user', $userId,
        "Benutzer '{$user['username']}' deaktiviert ({$invalidated} Sessions beendet)",
        ['sessions_invalidated' => $invalidated]
    );
    
    json_success([], 'Benutzer deaktiviert');
}

/**
 * GET /admin/permissions - Alle verfuegbaren Rechte auflisten
 */
function handleListPermissions(): void {
    $permissions = getAllPermissions();
    json_success(['permissions' => $permissions]);
}

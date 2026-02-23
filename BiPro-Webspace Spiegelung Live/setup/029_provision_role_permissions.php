<?php
/**
 * Migration 029: Provision-Rollen-Permissions
 *
 * Fuegt provision_access und provision_manage als eigenstaendige Permissions hinzu.
 * Diese Permissions werden NICHT automatisch an Admins vergeben (explizite Zuweisung noetig).
 * Der bestehende admin-User erhaelt beide Permissions initial.
 *
 * Idempotent: Kann mehrfach ausgefuehrt werden.
 */

require_once __DIR__ . '/../api/config.php';
require_once __DIR__ . '/../api/lib/db.php';

echo "=== Migration 029: Provision-Rollen-Permissions ===\n\n";

$pdo = Database::getInstance();

// 1. Permissions anlegen (INSERT IGNORE = idempotent)
$perms = [
    ['provision_access', 'Provisions-Zugriff', 'Zugriff auf die Provisions-/GF-Ebene'],
    ['provision_manage', 'Provisions-Verwaltung', 'Darf Provisions-Rechte vergeben und verwalten'],
];

foreach ($perms as [$key, $name, $desc]) {
    $existing = Database::queryOne(
        'SELECT id FROM permissions WHERE permission_key = ?',
        [$key]
    );
    if ($existing) {
        echo "  Permission '{$key}' existiert bereits (ID {$existing['id']}).\n";
    } else {
        Database::insert(
            'INSERT INTO permissions (permission_key, name, description) VALUES (?, ?, ?)',
            [$key, $name, $desc]
        );
        echo "  Permission '{$key}' angelegt.\n";
    }
}

// 2. Admin-User ermitteln (per Username, NICHT per ID)
$admin = Database::queryOne(
    "SELECT id FROM users WHERE username = 'admin' AND account_type = 'admin' LIMIT 1"
);

if (!$admin) {
    echo "\n  WARNUNG: Kein Admin-User 'admin' gefunden. Manuelle Zuweisung noetig.\n";
} else {
    $adminId = (int) $admin['id'];
    echo "\n  Admin-User gefunden (ID {$adminId}). Weise Provision-Permissions zu...\n";

    foreach (['provision_access', 'provision_manage'] as $key) {
        $perm = Database::queryOne(
            'SELECT id FROM permissions WHERE permission_key = ?',
            [$key]
        );
        if (!$perm) {
            echo "  FEHLER: Permission '{$key}' nicht in Tabelle gefunden.\n";
            continue;
        }
        $permId = (int) $perm['id'];

        $exists = Database::queryOne(
            'SELECT 1 FROM user_permissions WHERE user_id = ? AND permission_id = ?',
            [$adminId, $permId]
        );
        if ($exists) {
            echo "  '{$key}' bereits zugewiesen.\n";
        } else {
            Database::execute(
                'INSERT INTO user_permissions (user_id, permission_id, granted_by) VALUES (?, ?, ?)',
                [$adminId, $permId, $adminId]
            );
            echo "  '{$key}' zugewiesen.\n";
        }
    }
}

echo "\n=== Migration 029 abgeschlossen ===\n";

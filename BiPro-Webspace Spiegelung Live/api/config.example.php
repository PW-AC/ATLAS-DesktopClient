<?php
/**
 * ACENCIA ATLAS API - Konfigurationsdatei
 * 
 * ANLEITUNG:
 * 1. Diese Datei kopieren und als config.php speichern
 * 2. Alle Platzhalter durch echte Werte ersetzen
 * 3. config.php wird NICHT ins Git-Repo aufgenommen (.gitignore)
 * 
 * Schluessel generieren:
 *   MASTER_KEY (32 Bytes Base64): php -r "echo base64_encode(random_bytes(32));"
 *   JWT_SECRET (48 Bytes Base64): php -r "echo base64_encode(random_bytes(48));"
 *   SCAN_API_KEY:                 php -r "echo bin2hex(random_bytes(32));"
 */

// ================================================================
// Datenbank
// ================================================================
define('DB_HOST', 'localhost');
define('DB_NAME', 'DEIN_DB_NAME');
define('DB_USER', 'DEIN_DB_USER');
define('DB_PASS', 'DEIN_DB_PASSWORT');

// ================================================================
// Verschluesselung (AES-256-GCM, 32 Bytes Base64)
// ================================================================
define('MASTER_KEY', 'BASE64_ENCODED_32_BYTES_HIER_EINSETZEN');

// ================================================================
// JWT-Authentifizierung
// ================================================================
define('JWT_SECRET', 'BASE64_ENCODED_48_BYTES_HIER_EINSETZEN');
define('JWT_EXPIRY', 2592000);  // 30 Tage in Sekunden

// ================================================================
// KI-API (OpenRouter)
// ================================================================
define('OPENROUTER_API_KEY', 'sk-or-DEIN_API_KEY');

// ================================================================
// SmartScan / Incoming Scans
// ================================================================
define('SCAN_API_KEY', 'HEX_ENCODED_32_BYTES_HIER_EINSETZEN');
define('MAX_UPLOAD_SIZE', 50 * 1024 * 1024);  // 50 MB
define('SCAN_ALLOWED_MIME_TYPES', [
    'application/pdf',
    'image/jpeg',
    'image/png',
    'image/tiff',
]);

// ================================================================
// Dateispeicher
// ================================================================
define('DOCUMENTS_PATH', __DIR__ . '/../dokumente/');
define('API_BASE_URL', 'https://acencia.info/api/');

// ================================================================
// Debug-Modus (false fuer Produktion!)
// ================================================================
define('DEBUG_MODE', false);

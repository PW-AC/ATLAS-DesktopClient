<?php
/**
 * BiPro API - E-Mail-Konten (Admin CRUD + SMTP Test + IMAP Polling + Inbox)
 * 
 * Admin-Endpunkte (Admin-Rechte erforderlich):
 * - GET    /admin/email-accounts              - Alle E-Mail-Konten auflisten
 * - POST   /admin/email-accounts              - Neues Konto anlegen
 * - PUT    /admin/email-accounts/{id}         - Konto bearbeiten
 * - DELETE /admin/email-accounts/{id}         - Konto deaktivieren (Soft-Delete)
 * - POST   /admin/email-accounts/{id}/test    - SMTP-Verbindung testen
 * - POST   /admin/email-accounts/{id}/poll    - IMAP-Postfach abrufen
 * 
 * Inbox-Endpunkte (JWT erforderlich):
 * - GET    /email-inbox                              - Posteingang auflisten
 * - GET    /email-inbox/{id}                         - E-Mail-Detail mit Anhaengen
 * - GET    /email-inbox/pending-attachments           - Alle unverarbeiteten Anhaenge
 * - GET    /email-inbox/attachments/{id}/download     - Anhang herunterladen
 * - PUT    /email-inbox/attachments/{id}/imported     - Anhang-Status setzen
 */

require_once __DIR__ . '/lib/db.php';
require_once __DIR__ . '/lib/jwt.php';
require_once __DIR__ . '/lib/crypto.php';
require_once __DIR__ . '/lib/response.php';
require_once __DIR__ . '/lib/permissions.php';
require_once __DIR__ . '/lib/activity_logger.php';

// PHPMailer (fuer SMTP-Test)
require_once __DIR__ . '/lib/PHPMailer/Exception.php';
require_once __DIR__ . '/lib/PHPMailer/PHPMailer.php';
require_once __DIR__ . '/lib/PHPMailer/SMTP.php';

use PHPMailer\PHPMailer\PHPMailer;
use PHPMailer\PHPMailer\Exception as PHPMailerException;

// =============================================================================
// ADMIN: E-MAIL-KONTEN (CRUD + Test + Poll)
// =============================================================================

/**
 * Haupt-Router fuer /admin/email-accounts
 */
function handleAdminEmailAccountsRequest(?string $idOrAction, string $method, ?string $subAction = null): void {
    $payload = requireAdmin();

    // Sub-Action Routing: /admin/email-accounts/{id}/test oder /admin/email-accounts/{id}/poll
    if (!empty($idOrAction) && is_numeric($idOrAction)) {
        // $subAction wird direkt von index.php uebergeben (bevorzugt)
        $sub = $subAction ?? '';
        
        // Fallback: aus URL-Route extrahieren
        if (empty($sub)) {
            $route = isset($_GET['route']) ? trim($_GET['route'], '/') : '';
            $routeParts = explode('/', $route);
            // /admin/email-accounts/{id}/test -> parts: [admin, email-accounts, {id}, test]
            $sub = $routeParts[3] ?? '';
        }

        if ($sub === 'test') {
            handleAdminEmailAccountTestRequest((int)$idOrAction, $method);
            return;
        }
        if ($sub === 'poll') {
            handleImapPollRequest((int)$idOrAction, $method);
            return;
        }
    }

    switch ($method) {
        case 'GET':
            handleListEmailAccounts();
            break;

        case 'POST':
            handleCreateEmailAccount($payload);
            break;

        case 'PUT':
            if (empty($idOrAction) || !is_numeric($idOrAction)) {
                json_error('E-Mail-Konto-ID erforderlich', 400);
            }
            handleUpdateEmailAccount((int)$idOrAction, $payload);
            break;

        case 'DELETE':
            if (empty($idOrAction) || !is_numeric($idOrAction)) {
                json_error('E-Mail-Konto-ID erforderlich', 400);
            }
            handleDeleteEmailAccount((int)$idOrAction, $payload);
            break;

        default:
            json_error('Methode nicht erlaubt', 405);
    }
}

/**
 * GET /admin/email-accounts
 */
function handleListEmailAccounts(): void {
    $accounts = Database::query(
        'SELECT id, account_name, email_address, from_name, from_address,
                smtp_host, smtp_port, smtp_encryption, imap_host, imap_port, imap_encryption,
                username, imap_folder,
                imap_filter_mode, imap_filter_keywords, imap_sender_mode, imap_sender_whitelist,
                is_active, last_poll_at, last_poll_status, created_at, updated_at
         FROM email_accounts
         ORDER BY account_name ASC'
    );

    // Credentials und credentials_encrypted NIE in der Response
    json_success(['accounts' => $accounts]);
}

/**
 * POST /admin/email-accounts
 * Body: { account_name, email_address, smtp_host, smtp_port, smtp_encryption,
 *          imap_host, imap_port, imap_encryption, username, password,
 *          from_name?, from_address?, imap_folder?,
 *          imap_filter_mode?, imap_filter_keywords?, imap_sender_mode?, imap_sender_whitelist? }
 */
function handleCreateEmailAccount(array $adminPayload): void {
    $data = get_json_body();
    require_fields($data, ['account_name', 'email_address', 'smtp_host', 'username', 'password']);

    $accountName = trim($data['account_name']);
    $emailAddress = trim($data['email_address']);
    $password = $data['password'];

    if (strlen($accountName) === 0) {
        json_error('Kontoname darf nicht leer sein', 400);
    }
    if (!filter_var($emailAddress, FILTER_VALIDATE_EMAIL)) {
        json_error('Ungueltige E-Mail-Adresse', 400);
    }

    // Duplikat-Pruefung
    $existing = Database::queryOne(
        'SELECT id FROM email_accounts WHERE email_address = ? AND is_active = 1',
        [$emailAddress]
    );
    if ($existing) {
        json_error('Ein aktives Konto mit dieser E-Mail-Adresse existiert bereits', 409);
    }

    // Passwort verschluesseln
    $encryptedPassword = Crypto::encrypt($password);

    $id = Database::insert(
        'INSERT INTO email_accounts
         (account_name, email_address, from_name, from_address,
          smtp_host, smtp_port, smtp_encryption,
          imap_host, imap_port, imap_encryption,
          username, credentials_encrypted, imap_folder,
          imap_filter_mode, imap_filter_keywords, imap_sender_mode, imap_sender_whitelist,
          is_active)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)',
        [
            $accountName,
            $emailAddress,
            trim($data['from_name'] ?? ''),
            trim($data['from_address'] ?? $emailAddress),
            trim($data['smtp_host']),
            (int)($data['smtp_port'] ?? 587),
            $data['smtp_encryption'] ?? 'tls',
            trim($data['imap_host'] ?? ''),
            (int)($data['imap_port'] ?? 993),
            $data['imap_encryption'] ?? 'ssl',
            trim($data['username']),
            $encryptedPassword,
            trim($data['imap_folder'] ?? 'INBOX'),
            $data['imap_filter_mode'] ?? 'all',
            trim($data['imap_filter_keywords'] ?? ''),
            $data['imap_sender_mode'] ?? 'all',
            trim($data['imap_sender_whitelist'] ?? ''),
        ]
    );

    ActivityLogger::logAdmin($adminPayload, 'email_account_created', 'email_account', $id,
        "E-Mail-Konto erstellt: {$accountName} ({$emailAddress})",
        ['account_name' => $accountName, 'email_address' => $emailAddress]
    );

    $account = Database::queryOne(
        'SELECT id, account_name, email_address, from_name, from_address,
                smtp_host, smtp_port, smtp_encryption, imap_host, imap_port, imap_encryption,
                username, imap_folder, imap_filter_mode, imap_filter_keywords,
                imap_sender_mode, imap_sender_whitelist, is_active, created_at
         FROM email_accounts WHERE id = ?',
        [$id]
    );

    json_success(['account' => $account], 'E-Mail-Konto erstellt');
}

/**
 * PUT /admin/email-accounts/{id}
 * Body: beliebige Felder (password nur wenn geaendert)
 */
function handleUpdateEmailAccount(int $id, array $adminPayload): void {
    $account = Database::queryOne('SELECT * FROM email_accounts WHERE id = ?', [$id]);
    if (!$account) {
        json_error('E-Mail-Konto nicht gefunden', 404);
    }

    $data = get_json_body();
    $updates = [];
    $params = [];
    $changes = [];

    $allowedFields = [
        'account_name', 'email_address', 'from_name', 'from_address',
        'smtp_host', 'smtp_port', 'smtp_encryption',
        'imap_host', 'imap_port', 'imap_encryption',
        'username', 'imap_folder',
        'imap_filter_mode', 'imap_filter_keywords',
        'imap_sender_mode', 'imap_sender_whitelist',
        'is_active',
    ];

    foreach ($allowedFields as $field) {
        if (array_key_exists($field, $data)) {
            $updates[] = "$field = ?";
            $params[] = $data[$field];
            $changes[$field] = $data[$field];
        }
    }

    // Passwort nur verschluesseln wenn explizit mitgeschickt
    if (!empty($data['password'])) {
        $updates[] = 'credentials_encrypted = ?';
        $params[] = Crypto::encrypt($data['password']);
        $changes['password'] = '(geaendert)';
    }

    if (empty($updates)) {
        json_error('Keine Aenderungen', 400);
    }

    $updates[] = 'updated_at = NOW()';
    $params[] = $id;
    Database::execute(
        'UPDATE email_accounts SET ' . implode(', ', $updates) . ' WHERE id = ?',
        $params
    );

    ActivityLogger::logAdmin($adminPayload, 'email_account_updated', 'email_account', $id,
        "E-Mail-Konto bearbeitet: {$account['account_name']}",
        ['changes' => $changes]
    );

    $updated = Database::queryOne(
        'SELECT id, account_name, email_address, from_name, from_address,
                smtp_host, smtp_port, smtp_encryption, imap_host, imap_port, imap_encryption,
                username, imap_folder, imap_filter_mode, imap_filter_keywords,
                imap_sender_mode, imap_sender_whitelist, is_active, last_poll_at, last_poll_status,
                created_at, updated_at
         FROM email_accounts WHERE id = ?',
        [$id]
    );

    json_success(['account' => $updated], 'E-Mail-Konto aktualisiert');
}

/**
 * DELETE /admin/email-accounts/{id} - Soft-Delete (is_active=0)
 */
function handleDeleteEmailAccount(int $id, array $adminPayload): void {
    $account = Database::queryOne('SELECT id, account_name, is_active FROM email_accounts WHERE id = ?', [$id]);
    if (!$account) {
        json_error('E-Mail-Konto nicht gefunden', 404);
    }
    if (!$account['is_active']) {
        json_error('E-Mail-Konto ist bereits deaktiviert', 400);
    }

    Database::execute('UPDATE email_accounts SET is_active = 0, updated_at = NOW() WHERE id = ?', [$id]);

    ActivityLogger::logAdmin($adminPayload, 'email_account_deleted', 'email_account', $id,
        "E-Mail-Konto deaktiviert: {$account['account_name']}",
        ['account_name' => $account['account_name']]
    );

    json_success([], 'E-Mail-Konto deaktiviert');
}

// =============================================================================
// ADMIN: SMTP-TEST
// =============================================================================

/**
 * POST /admin/email-accounts/{id}/test
 * Sendet eine Test-E-Mail ueber SMTP an die from_address.
 */
function handleAdminEmailAccountTestRequest(int $accountId, string $method): void {
    $payload = requireAdmin();

    if ($method !== 'POST') {
        json_error('Methode nicht erlaubt. Nur POST.', 405);
    }

    $account = Database::queryOne('SELECT * FROM email_accounts WHERE id = ?', [$accountId]);
    if (!$account) {
        json_error('E-Mail-Konto nicht gefunden', 404);
    }

    // Passwort entschluesseln
    if (empty($account['credentials_encrypted'])) {
        json_error('Kein Passwort hinterlegt', 400);
    }

    try {
        $password = Crypto::decrypt($account['credentials_encrypted']);
    } catch (Exception $e) {
        json_error('Passwort konnte nicht entschluesselt werden: ' . $e->getMessage(), 500);
    }

    $fromAddress = $account['from_address'] ?: $account['email_address'];
    $fromName = $account['from_name'] ?: $account['account_name'];

    $mail = new PHPMailer(true);
    $debugOutput = '';

    try {
        $mail->isSMTP();
        $mail->Host = $account['smtp_host'];
        $mail->Port = (int)$account['smtp_port'];
        $mail->SMTPAuth = true;
        $mail->Username = $account['username'];
        $mail->Password = $password;
        $mail->CharSet = 'UTF-8';

        // Verschluesselung
        $encryption = strtolower($account['smtp_encryption'] ?? 'tls');
        if ($encryption === 'tls') {
            $mail->SMTPSecure = PHPMailer::ENCRYPTION_STARTTLS;
        } elseif ($encryption === 'ssl') {
            $mail->SMTPSecure = PHPMailer::ENCRYPTION_SMTPS;
        } else {
            $mail->SMTPSecure = '';
            $mail->SMTPAutoTLS = false;
        }

        // Debug-Output abfangen
        $mail->SMTPDebug = 2;
        $mail->Debugoutput = function ($str, $level) use (&$debugOutput) {
            $debugOutput .= trim($str) . "\n";
        };

        $mail->setFrom($fromAddress, $fromName);
        $mail->addAddress($fromAddress, $fromName);
        $mail->Subject = 'ACENCIA ATLAS - SMTP-Verbindungstest';
        $mail->Body = "Diese E-Mail bestaetigt, dass das E-Mail-Konto \"{$account['account_name']}\" "
            . "korrekt konfiguriert ist.\n\n"
            . "Zeitpunkt: " . date('d.m.Y H:i:s') . "\n"
            . "Server: {$account['smtp_host']}:{$account['smtp_port']} ({$encryption})";

        $mail->send();

        ActivityLogger::logAdmin($payload, 'email_account_test_success', 'email_account', $accountId,
            "SMTP-Test erfolgreich: {$account['account_name']}",
            ['smtp_host' => $account['smtp_host'], 'smtp_port' => $account['smtp_port']]
        );

        json_success([
            'test_result' => 'success',
            'message' => "Test-E-Mail erfolgreich gesendet an {$fromAddress}",
            'smtp_host' => $account['smtp_host'],
            'smtp_port' => (int)$account['smtp_port'],
            'debug' => $debugOutput,
        ], 'SMTP-Test erfolgreich');

    } catch (PHPMailerException $e) {
        ActivityLogger::logAdmin($payload, 'email_account_test_failed', 'email_account', $accountId,
            "SMTP-Test fehlgeschlagen: {$e->getMessage()}",
            ['smtp_host' => $account['smtp_host'], 'error' => $e->getMessage()]
        );

        json_error('SMTP-Test fehlgeschlagen: ' . $e->getMessage(), 400, [
            'test_result' => 'failed',
            'smtp_host' => $account['smtp_host'],
            'smtp_port' => (int)$account['smtp_port'],
            'debug' => $debugOutput,
        ]);
    }
}

// =============================================================================
// ADMIN: IMAP POLLING
// =============================================================================

/**
 * POST /admin/email-accounts/{id}/poll
 * Ruft neue E-Mails ueber IMAP ab, extrahiert Anhaenge und legt Inbox-Eintraege an.
 */
function handleImapPollRequest(int $accountId, string $method): void {
    $payload = requireAdmin();

    if ($method !== 'POST') {
        json_error('Methode nicht erlaubt. Nur POST.', 405);
    }

    // IMAP-Extension pruefen
    if (!function_exists('imap_open')) {
        json_error('PHP IMAP-Extension ist nicht verfuegbar. Bitte beim Hoster aktivieren.', 500);
    }

    $account = Database::queryOne('SELECT * FROM email_accounts WHERE id = ?', [$accountId]);
    if (!$account) {
        json_error('E-Mail-Konto nicht gefunden', 404);
    }
    if (!$account['is_active']) {
        json_error('E-Mail-Konto ist deaktiviert', 400);
    }
    if (empty($account['imap_host'])) {
        json_error('Kein IMAP-Server konfiguriert. Bitte IMAP-Host im E-Mail-Konto eintragen.', 400);
    }
    if (empty($account['credentials_encrypted'])) {
        json_error('Kein Passwort hinterlegt', 400);
    }

    try {
        $password = Crypto::decrypt($account['credentials_encrypted']);
    } catch (Exception $e) {
        json_error('Passwort konnte nicht entschluesselt werden: ' . $e->getMessage(), 500);
    }

    // IMAP-Verbindung aufbauen
    $imapPort = (int)($account['imap_port'] ?? 993);
    $encryption = strtolower($account['imap_encryption'] ?? 'ssl');
    
    // Auto-Korrektur: Port 993 = immer SSL, Port 143 = immer TLS/STARTTLS
    if ($imapPort === 993 && $encryption !== 'ssl') {
        $encryption = 'ssl';
    } elseif ($imapPort === 143 && $encryption === 'ssl') {
        $encryption = 'tls';
    }
    
    $flags = '/imap';
    if ($encryption === 'ssl') {
        $flags .= '/ssl';
    } elseif ($encryption === 'tls') {
        $flags .= '/tls';
    }
    $flags .= '/novalidate-cert';

    $folder = $account['imap_folder'] ?: 'INBOX';
    $mailbox = '{' . $account['imap_host'] . ':' . $account['imap_port'] . $flags . '}' . $folder;

    // Timeouts setzen (verhindert "idle for too long" Fehler)
    imap_timeout(IMAP_OPENTIMEOUT, 30);
    imap_timeout(IMAP_READTIMEOUT, 30);
    imap_timeout(IMAP_WRITETIMEOUT, 30);
    imap_timeout(IMAP_CLOSETIMEOUT, 10);

    // Alte IMAP-Fehler leeren (verhindert Stale-Error-Probleme)
    imap_errors();
    imap_alerts();

    $mbox = @imap_open($mailbox, $account['username'], $password, 0, 3);
    if (!$mbox) {
        $imapError = imap_last_error();
        // Alle aufgelaufenen Fehler sammeln fuer bessere Diagnose
        $allErrors = imap_errors();
        $errorMsg = $imapError ?: 'Unbekannter IMAP-Fehler';
        if ($allErrors) {
            $errorMsg .= ' | Details: ' . implode('; ', $allErrors);
        }
        Database::execute(
            'UPDATE email_accounts SET last_poll_at = NOW(), last_poll_status = ? WHERE id = ?',
            ['error: ' . substr($errorMsg, 0, 250), $accountId]
        );
        json_error('IMAP-Verbindung fehlgeschlagen: ' . $errorMsg, 400);
    }

    // Filter-Einstellungen
    $filterMode = $account['imap_filter_mode'] ?? 'all';
    $filterKeywords = array_filter(array_map('trim', explode(',', $account['imap_filter_keywords'] ?? '')));
    $senderMode = $account['imap_sender_mode'] ?? 'all';
    $senderWhitelist = array_filter(array_map('trim', explode(',', $account['imap_sender_whitelist'] ?? '')));
    $senderWhitelistLower = array_map('strtolower', $senderWhitelist);

    $stats = ['new_mails' => 0, 'new_attachments' => 0, 'filtered_out' => 0, 'errors' => []];

    // Staging-Verzeichnis sicherstellen
    $stagingDir = DOCUMENTS_PATH . 'imap_staging/';
    if (!is_dir($stagingDir)) {
        if (!mkdir($stagingDir, 0755, true)) {
            imap_close($mbox);
            json_error('Staging-Verzeichnis konnte nicht erstellt werden', 500);
        }
    }

    try {
        $emails = imap_search($mbox, 'UNSEEN');
        if ($emails === false) {
            $emails = [];
        }

        foreach ($emails as $msgno) {
            try {
                $header = imap_headerinfo($mbox, $msgno);
                if (!$header) {
                    $stats['errors'][] = "E-Mail #{$msgno}: Header konnte nicht gelesen werden";
                    continue;
                }

                $messageId = isset($header->message_id) ? trim($header->message_id) : '';
                $subject = isset($header->subject) ? imapDecodeHeader($header->subject) : '(kein Betreff)';
                $fromAddr = '';
                $fromName = '';
                if (!empty($header->from)) {
                    $fromAddr = strtolower($header->from[0]->mailbox . '@' . ($header->from[0]->host ?? ''));
                    $fromName = isset($header->from[0]->personal) ? imapDecodeHeader($header->from[0]->personal) : '';
                }
                $dateStr = $header->date ?? '';
                $receivedAt = !empty($dateStr) ? date('Y-m-d H:i:s', strtotime($dateStr)) : date('Y-m-d H:i:s');

                // Duplikat-Pruefung via message_id
                if (!empty($messageId)) {
                    $dup = Database::queryOne(
                        'SELECT id FROM email_inbox WHERE message_id = ?',
                        [$messageId]
                    );
                    if ($dup) {
                        continue;
                    }
                }

                // Absender-Filter
                if ($senderMode === 'whitelist' && !empty($senderWhitelistLower)) {
                    $matched = false;
                    foreach ($senderWhitelistLower as $allowed) {
                        if (strpos($fromAddr, $allowed) !== false) {
                            $matched = true;
                            break;
                        }
                    }
                    if (!$matched) {
                        $stats['filtered_out']++;
                        // Als gelesen markieren damit sie beim naechsten Poll nicht nochmal auftaucht
                        imap_setflag_full($mbox, (string)$msgno, '\\Seen');
                        continue;
                    }
                }

                // Keyword-Filter auf Betreff
                if ($filterMode === 'keyword' && !empty($filterKeywords)) {
                    $subjectLower = strtolower($subject);
                    $matched = false;
                    foreach ($filterKeywords as $kw) {
                        if (strpos($subjectLower, strtolower($kw)) !== false) {
                            $matched = true;
                            break;
                        }
                    }
                    if (!$matched) {
                        $stats['filtered_out']++;
                        imap_setflag_full($mbox, (string)$msgno, '\\Seen');
                        continue;
                    }
                }

                // E-Mail in DB anlegen
                $mailId = Database::insert(
                    'INSERT INTO email_inbox
                     (email_account_id, message_id, subject, from_address, from_name, received_at, status)
                     VALUES (?, ?, ?, ?, ?, ?, ?)',
                    [$accountId, $messageId, $subject, $fromAddr, $fromName, $receivedAt, 'new']
                );
                $stats['new_mails']++;

                // Anhaenge extrahieren
                $structure = imap_fetchstructure($mbox, $msgno);
                if ($structure) {
                    $attachments = extractImapAttachments($mbox, $msgno, $structure);
                    foreach ($attachments as $att) {
                        $safeFilename = preg_replace('/[^a-zA-Z0-9._-]/', '_', $att['filename']);
                        $safeFilename = ltrim($safeFilename, '.');
                        if (empty($safeFilename)) {
                            $safeFilename = 'attachment.dat';
                        }

                        $storedName = date('Y-m-d_His') . '_' . bin2hex(random_bytes(8)) . '_' . $safeFilename;
                        $storedPath = $stagingDir . $storedName;

                        $written = file_put_contents($storedPath, $att['data']);
                        if ($written === false) {
                            $stats['errors'][] = "Anhang '{$att['filename']}' konnte nicht gespeichert werden";
                            continue;
                        }

                        Database::insert(
                            'INSERT INTO email_inbox_attachments
                             (email_inbox_id, original_filename, stored_filename, stored_path, mime_type, file_size, import_status)
                             VALUES (?, ?, ?, ?, ?, ?, ?)',
                            [
                                $mailId,
                                $att['filename'],
                                $storedName,
                                'imap_staging/' . $storedName,
                                $att['mime_type'],
                                strlen($att['data']),
                                'pending',
                            ]
                        );
                        $stats['new_attachments']++;
                    }
                }

                // Als gelesen markieren
                imap_setflag_full($mbox, (string)$msgno, '\\Seen');

            } catch (Exception $e) {
                $stats['errors'][] = "E-Mail #{$msgno}: " . $e->getMessage();
            }
        }

    } finally {
        imap_close($mbox);
    }

    // Poll-Status aktualisieren
    $statusMsg = "OK: {$stats['new_mails']} E-Mails, {$stats['new_attachments']} Anhaenge";
    if (!empty($stats['errors'])) {
        $statusMsg .= ', ' . count($stats['errors']) . ' Fehler';
    }
    Database::execute(
        'UPDATE email_accounts SET last_poll_at = NOW(), last_poll_status = ? WHERE id = ?',
        [substr($statusMsg, 0, 250), $accountId]
    );

    ActivityLogger::logAdmin($payload, 'email_account_polled', 'email_account', $accountId,
        "IMAP-Abruf: {$stats['new_mails']} E-Mails, {$stats['new_attachments']} Anhaenge",
        ['stats' => $stats]
    );

    json_success($stats, 'IMAP-Abruf abgeschlossen');
}

/**
 * Extrahiert Anhaenge aus einer IMAP-Nachricht (rekursiv fuer multipart).
 */
function extractImapAttachments($mbox, int $msgno, object $structure, string $partNumber = ''): array {
    $attachments = [];

    // Einzelner Part
    if (empty($structure->parts)) {
        if (!empty($structure->disposition) && strtolower($structure->disposition) === 'attachment') {
            $filename = getImapPartFilename($structure);
            if (!empty($filename)) {
                $data = imap_fetchbody($mbox, $msgno, $partNumber ?: '1');
                $data = decodeImapBody($data, $structure->encoding ?? 0);
                $mimeType = getImapMimeType($structure);
                $attachments[] = ['filename' => $filename, 'data' => $data, 'mime_type' => $mimeType];
            }
        }
        return $attachments;
    }

    // Multipart
    foreach ($structure->parts as $idx => $part) {
        $subPart = $partNumber ? ($partNumber . '.' . ($idx + 1)) : (string)($idx + 1);

        $isAttachment = false;
        $filename = '';

        // Disposition pruefen
        if (!empty($part->disposition) && strtolower($part->disposition) === 'attachment') {
            $isAttachment = true;
            $filename = getImapPartFilename($part);
        }
        // Inline-Attachments mit Dateinamen auch beruecksichtigen
        if (!$isAttachment) {
            $filename = getImapPartFilename($part);
            if (!empty($filename) && !empty($part->disposition) && strtolower($part->disposition) === 'inline') {
                $isAttachment = true;
            }
        }

        if ($isAttachment && !empty($filename)) {
            $data = imap_fetchbody($mbox, $msgno, $subPart);
            $data = decodeImapBody($data, $part->encoding ?? 0);
            $mimeType = getImapMimeType($part);
            $attachments[] = ['filename' => $filename, 'data' => $data, 'mime_type' => $mimeType];
        }

        // Rekursiv in Unter-Parts suchen
        if (!empty($part->parts)) {
            $nested = extractImapAttachments($mbox, $msgno, $part, $subPart);
            $attachments = array_merge($attachments, $nested);
        }
    }

    return $attachments;
}

/**
 * Ermittelt den Dateinamen aus einem IMAP-Part.
 */
function getImapPartFilename(object $part): string {
    $filename = '';

    // dparameters (Content-Disposition Filename)
    if (!empty($part->dparameters)) {
        foreach ($part->dparameters as $param) {
            if (strtolower($param->attribute) === 'filename') {
                $filename = imapDecodeHeader($param->value);
                break;
            }
        }
    }

    // Fallback: parameters (Content-Type Name)
    if (empty($filename) && !empty($part->parameters)) {
        foreach ($part->parameters as $param) {
            if (strtolower($param->attribute) === 'name') {
                $filename = imapDecodeHeader($param->value);
                break;
            }
        }
    }

    return $filename;
}

/**
 * Dekodiert IMAP Body basierend auf Encoding-Typ.
 */
function decodeImapBody(string $data, int $encoding): string {
    switch ($encoding) {
        case 0: // 7BIT
        case 1: // 8BIT
            return $data;
        case 2: // BINARY
            return $data;
        case 3: // BASE64
            return base64_decode($data);
        case 4: // QUOTED-PRINTABLE
            return quoted_printable_decode($data);
        default:
            return $data;
    }
}

/**
 * Ermittelt den MIME-Type aus einem IMAP-Part.
 */
function getImapMimeType(object $part): string {
    $types = ['TEXT', 'MULTIPART', 'MESSAGE', 'APPLICATION', 'AUDIO', 'IMAGE', 'VIDEO', 'MODEL', 'OTHER'];
    $primaryType = strtolower($types[$part->type] ?? 'application');
    $subtype = strtolower($part->subtype ?? 'octet-stream');
    return $primaryType . '/' . $subtype;
}

/**
 * Dekodiert IMAP-Header (MIME-encoded Words).
 */
function imapDecodeHeader(string $value): string {
    $elements = imap_mime_header_decode($value);
    $result = '';
    foreach ($elements as $el) {
        $charset = strtoupper($el->charset);
        if ($charset === 'DEFAULT' || $charset === 'US-ASCII' || $charset === 'UTF-8') {
            $result .= $el->text;
        } else {
            $converted = @iconv($charset, 'UTF-8//TRANSLIT', $el->text);
            $result .= ($converted !== false) ? $converted : $el->text;
        }
    }
    return $result;
}

// =============================================================================
// INBOX: E-MAIL-POSTEINGANG
// =============================================================================

/**
 * Haupt-Router fuer /email-inbox
 */
function handleEmailInboxRequest(?string $idOrAction, string $method): void {
    $payload = JWT::requireAuth();

    // GET /email-inbox/pending-attachments
    if ($idOrAction === 'pending-attachments' && $method === 'GET') {
        handleGetPendingAttachments($payload);
        return;
    }

    // Routes fuer /email-inbox/attachments/{id}/...
    if ($idOrAction === 'attachments') {
        $route = isset($_GET['route']) ? trim($_GET['route'], '/') : '';
        $routeParts = explode('/', $route);
        // /email-inbox/attachments/{id}/download -> [email-inbox, attachments, {id}, download]
        $attId = $routeParts[2] ?? null;
        $attAction = $routeParts[3] ?? null;

        if (empty($attId) || !is_numeric($attId)) {
            json_error('Anhang-ID erforderlich', 400);
        }

        if ($attAction === 'download' && $method === 'GET') {
            handleDownloadAttachment((int)$attId, $payload);
            return;
        }
        if ($attAction === 'imported' && $method === 'PUT') {
            handleMarkAttachmentStatus((int)$attId, $payload);
            return;
        }

        json_error('Unbekannte Anhangs-Aktion', 404);
    }

    // Routes fuer /email-inbox/{id}/ignore
    if (is_numeric($idOrAction)) {
        $route = isset($_GET['route']) ? trim($_GET['route'], '/') : '';
        $routeParts = explode('/', $route);
        // /email-inbox/{id}/ignore -> [email-inbox, {id}, ignore]
        $subAction = $routeParts[2] ?? null;

        if ($subAction === 'ignore' && $method === 'PUT') {
            handleIgnoreInboxMail((int)$idOrAction, $payload);
            return;
        }
    }

    switch ($method) {
        case 'GET':
            if (empty($idOrAction)) {
                handleListInboxMails($payload);
            } elseif (is_numeric($idOrAction)) {
                handleGetInboxMail((int)$idOrAction, $payload);
            } else {
                json_error('Unbekannte Inbox-Aktion', 404);
            }
            break;

        default:
            json_error('Methode nicht erlaubt', 405);
    }
}

/**
 * GET /email-inbox?page=1&limit=50&status=&search=
 */
function handleListInboxMails(array $payload): void {
    $page = max(1, (int)($_GET['page'] ?? 1));
    $limit = min(200, max(1, (int)($_GET['limit'] ?? 50)));
    $offset = ($page - 1) * $limit;
    $status = $_GET['status'] ?? '';
    $search = trim($_GET['search'] ?? '');

    $where = [];
    $params = [];

    if (!empty($status)) {
        $where[] = 'ei.status = ?';
        $params[] = $status;
    }
    if (!empty($search)) {
        $where[] = '(ei.subject LIKE ? OR ei.from_address LIKE ? OR ei.from_name LIKE ?)';
        $searchParam = '%' . $search . '%';
        $params[] = $searchParam;
        $params[] = $searchParam;
        $params[] = $searchParam;
    }

    $whereClause = !empty($where) ? 'WHERE ' . implode(' AND ', $where) : '';

    // Gesamtanzahl
    $countRow = Database::queryOne(
        "SELECT COUNT(*) as total FROM email_inbox ei {$whereClause}",
        $params
    );
    $total = (int)($countRow['total'] ?? 0);

    // Daten mit Anhang-Zaehler
    $queryParams = array_merge($params, [$limit, $offset]);
    $mails = Database::query(
        "SELECT ei.*, ea.account_name AS email_account_name,
                (SELECT COUNT(*) FROM email_inbox_attachments eia WHERE eia.email_inbox_id = ei.id) AS attachment_count
         FROM email_inbox ei
         LEFT JOIN email_accounts ea ON ea.id = ei.email_account_id
         {$whereClause}
         ORDER BY ei.received_at DESC
         LIMIT ? OFFSET ?",
        $queryParams
    );

    json_success([
        'mails' => $mails,
        'total' => $total,
        'page' => $page,
        'limit' => $limit,
        'pages' => (int)ceil($total / $limit),
    ]);
}

/**
 * GET /email-inbox/{id} - E-Mail-Detail mit Anhaengen
 */
function handleGetInboxMail(int $id, array $payload): void {
    $mail = Database::queryOne(
        'SELECT ei.*, ea.account_name AS email_account_name
         FROM email_inbox ei
         LEFT JOIN email_accounts ea ON ea.id = ei.email_account_id
         WHERE ei.id = ?',
        [$id]
    );
    if (!$mail) {
        json_error('E-Mail nicht gefunden', 404);
    }

    $attachments = Database::query(
        'SELECT id, original_filename, stored_filename, mime_type, file_size, import_status, imported_document_id, created_at
         FROM email_inbox_attachments
         WHERE email_inbox_id = ?
         ORDER BY id ASC',
        [$id]
    );

    $mail['attachments'] = $attachments;
    json_success(['mail' => $mail]);
}

/**
 * GET /email-inbox/pending-attachments
 * Alle Anhaenge mit import_status=pending (fuer Import-Workflow).
 */
function handleGetPendingAttachments(array $payload): void {
    $attachments = Database::query(
        'SELECT eia.*, ei.subject, ei.from_address, ei.from_name, ei.received_at,
                ea.account_name AS email_account_name
         FROM email_inbox_attachments eia
         JOIN email_inbox ei ON ei.id = eia.email_inbox_id
         LEFT JOIN email_accounts ea ON ea.id = ei.email_account_id
         WHERE eia.import_status = ?
         ORDER BY ei.received_at DESC, eia.id ASC',
        ['pending']
    );

    json_success(['attachments' => $attachments]);
}

/**
 * GET /email-inbox/attachments/{id}/download
 * Liefert die Roh-Datei des Anhangs aus dem Staging-Verzeichnis.
 */
function handleDownloadAttachment(int $attachmentId, array $payload): void {
    $att = Database::queryOne(
        'SELECT * FROM email_inbox_attachments WHERE id = ?',
        [$attachmentId]
    );
    if (!$att) {
        json_error('Anhang nicht gefunden', 404);
    }

    $filePath = DOCUMENTS_PATH . $att['stored_path'];
    if (!file_exists($filePath)) {
        json_error('Datei nicht gefunden auf dem Server', 404);
    }

    $mimeType = $att['mime_type'] ?: 'application/octet-stream';
    $filename = $att['original_filename'] ?: $att['stored_filename'];

    header('Content-Type: ' . $mimeType);
    header('Content-Disposition: attachment; filename="' . addslashes($filename) . '"');
    header('Content-Length: ' . filesize($filePath));
    header('Cache-Control: no-cache');
    readfile($filePath);
    exit;
}

/**
 * PUT /email-inbox/attachments/{id}/imported
 * Body: { import_status: "imported"|"failed"|"skipped", imported_document_id?: int }
 */
function handleMarkAttachmentStatus(int $attachmentId, array $payload): void {
    $att = Database::queryOne(
        'SELECT eia.*, ei.subject FROM email_inbox_attachments eia
         JOIN email_inbox ei ON ei.id = eia.email_inbox_id
         WHERE eia.id = ?',
        [$attachmentId]
    );
    if (!$att) {
        json_error('Anhang nicht gefunden', 404);
    }

    $data = get_json_body();
    $status = $data['import_status'] ?? '';
    if (!in_array($status, ['imported', 'failed', 'skipped'])) {
        json_error('Ungueltiger import_status. Erlaubt: imported, failed, skipped', 400);
    }

    $updates = ['import_status = ?'];
    $params = [$status];

    if ($status === 'imported' && !empty($data['imported_document_id'])) {
        $updates[] = 'imported_document_id = ?';
        $params[] = (int)$data['imported_document_id'];
    }

    $updates[] = 'imported_at = NOW()';
    $params[] = $attachmentId;

    Database::execute(
        'UPDATE email_inbox_attachments SET ' . implode(', ', $updates) . ' WHERE id = ?',
        $params
    );

    // Pruefen ob alle Anhaenge der E-Mail verarbeitet wurden
    $pending = Database::queryOne(
        'SELECT COUNT(*) as cnt FROM email_inbox_attachments WHERE email_inbox_id = ? AND import_status = ?',
        [$att['email_inbox_id'], 'pending']
    );
    if ((int)($pending['cnt'] ?? 0) === 0) {
        Database::execute(
            'UPDATE email_inbox SET status = ? WHERE id = ?',
            ['processed', $att['email_inbox_id']]
        );
    }

    ActivityLogger::log([
        'user_id' => $payload['user_id'],
        'username' => $payload['username'] ?? '',
        'action_category' => 'email_inbox',
        'action' => 'attachment_' . $status,
        'entity_type' => 'email_inbox_attachment',
        'entity_id' => $attachmentId,
        'description' => "Anhang '{$att['original_filename']}' als {$status} markiert (E-Mail: {$att['subject']})",
        'details' => [
            'original_filename' => $att['original_filename'],
            'import_status' => $status,
            'imported_document_id' => $data['imported_document_id'] ?? null,
        ],
        'status' => 'success',
    ]);

    json_success([], "Anhang als {$status} markiert");
}

/**
 * PUT /email-inbox/{id}/ignore
 * Markiert eine E-Mail als ignoriert.
 */
function handleIgnoreInboxMail(int $id, array $payload): void {
    $mail = Database::queryOne('SELECT * FROM email_inbox WHERE id = ?', [$id]);
    if (!$mail) {
        json_error('E-Mail nicht gefunden', 404);
    }

    Database::execute(
        'UPDATE email_inbox SET status = ? WHERE id = ?',
        ['ignored', $id]
    );

    ActivityLogger::log([
        'user_id' => $payload['user_id'],
        'username' => $payload['username'] ?? '',
        'action_category' => 'email_inbox',
        'action' => 'email_ignored',
        'entity_type' => 'email_inbox',
        'entity_id' => $id,
        'description' => "E-Mail '{$mail['subject']}' ignoriert",
        'details' => [
            'subject' => $mail['subject'],
            'from' => $mail['from_address']
        ],
        'status' => 'success',
    ]);

    json_success([], 'E-Mail ignoriert');
}

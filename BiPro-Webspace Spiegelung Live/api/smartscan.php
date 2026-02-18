<?php
/**
 * BiPro API - SmartScan
 * 
 * Versand von Dokumenten per E-Mail an SmartScan-Ziel,
 * Job-Verwaltung und Einstellungen.
 * 
 * Oeffentliche Endpunkte (JWT erforderlich):
 * - GET  /smartscan/settings          - Einstellungen laden
 * - POST /smartscan/send              - Versand-Job starten
 * - POST /smartscan/jobs/{id}/process - Naechsten Chunk verarbeiten
 * - GET  /smartscan/jobs              - Job-Historie (Admin: alle, User: eigene)
 * - GET  /smartscan/jobs/{id}         - Job-Detail mit Items + E-Mails
 * 
 * Admin-Endpunkte:
 * - PUT  /admin/smartscan/settings    - Einstellungen speichern
 */

require_once __DIR__ . '/lib/db.php';
require_once __DIR__ . '/lib/jwt.php';
require_once __DIR__ . '/lib/crypto.php';
require_once __DIR__ . '/lib/response.php';
require_once __DIR__ . '/lib/permissions.php';
require_once __DIR__ . '/lib/activity_logger.php';

require_once __DIR__ . '/lib/PHPMailer/Exception.php';
require_once __DIR__ . '/lib/PHPMailer/PHPMailer.php';
require_once __DIR__ . '/lib/PHPMailer/SMTP.php';

use PHPMailer\PHPMailer\PHPMailer;
use PHPMailer\PHPMailer\Exception as PHPMailerException;

// ============================================================================
// KONSTANTEN
// ============================================================================

/** Maximale Anzahl Items die pro processChunk-Aufruf verarbeitet werden */
define('SMARTSCAN_CHUNK_SIZE', 10);

/** Idempotenz-Fenster in Sekunden (10 Minuten) */
define('SMARTSCAN_IDEMPOTENCY_WINDOW', 600);

/** Anzeigenamen fuer Box-Typen (fuer Template-Rendering) */
define('BOX_DISPLAY_NAMES', [
    'eingang'      => 'Eingang',
    'verarbeitung' => 'Verarbeitung',
    'roh'          => 'Roh-Archiv',
    'gdv'          => 'GDV',
    'courtage'     => 'Courtage',
    'sach'         => 'Sach',
    'leben'        => 'Leben',
    'kranken'      => 'Kranken',
    'sonstige'     => 'Sonstige',
    'falsch'       => 'Falsch zugeordnet',
]);

// ============================================================================
// ROUTER: Oeffentliche Endpunkte
// ============================================================================

/**
 * Oeffentlicher Router fuer /smartscan/...
 *
 * @param string      $action 'settings' | 'send' | 'jobs'
 * @param string|null $id     Job-ID oder Sub-Action
 * @param string      $method HTTP-Methode
 */
function handleSmartScanRequest(string $action, ?string $id, string $method): void {
    // JWT fuer alle SmartScan-Endpunkte erforderlich
    $payload = JWT::requireAuth();

    switch ($action) {
        // GET /smartscan/settings
        case 'settings':
            if ($method !== 'GET') {
                json_error('Methode nicht erlaubt', 405);
            }
            getSmartScanSettings($payload);
            break;

        // POST /smartscan/send
        case 'send':
            if ($method !== 'POST') {
                json_error('Methode nicht erlaubt', 405);
            }
            if (!hasPermission($payload['user_id'], 'smartscan_send')) {
                ActivityLogger::log([
                    'user_id'         => $payload['user_id'],
                    'username'        => $payload['username'] ?? '',
                    'action_category' => 'smartscan',
                    'action'          => 'send_denied',
                    'description'     => 'SmartScan-Versand verweigert: Keine Berechtigung',
                    'status'          => 'denied',
                ]);
                json_error('Keine Berechtigung fuer SmartScan-Versand', 403, [
                    'required_permission' => 'smartscan_send',
                ]);
            }
            startSendJob($payload);
            break;

        // /smartscan/jobs[/{id}[/process]]
        case 'jobs':
            handleJobsRoute($id, $method, $payload);
            break;

        default:
            json_error('Unbekannte SmartScan-Aktion: ' . $action, 404);
    }
}

// ============================================================================
// ROUTER: Admin-Endpunkte
// ============================================================================

/**
 * Admin-Router fuer /admin/smartscan/...
 *
 * @param string|null $action 'settings'
 * @param string      $method HTTP-Methode
 */
function handleAdminSmartScanRequest(?string $action, string $method): void {
    $payload = requireAdmin();

    switch ($action) {
        case 'settings':
            if ($method !== 'PUT') {
                json_error('Methode nicht erlaubt', 405);
            }
            saveSmartScanSettings($payload);
            break;

        default:
            json_error('Unbekannte Admin-SmartScan-Aktion', 404);
    }
}

// ============================================================================
// JOBS SUB-ROUTER
// ============================================================================

/**
 * Sub-Router fuer /smartscan/jobs[/{id}[/process]]
 */
function handleJobsRoute(?string $id, string $method, array $payload): void {
    // GET /smartscan/jobs  (Liste)
    if (empty($id) && $method === 'GET') {
        listJobs($payload);
        return;
    }

    if (empty($id)) {
        json_error('Job-ID erforderlich', 400);
    }

    // Pruefen ob Sub-Action (/jobs/{id}/process)
    // $id kann "123/process" sein wenn der Router $parts[2] . '/' . $parts[3] liefert
    // Wir pruefen daher selbst
    $subParts = explode('/', $id);
    $jobId    = $subParts[0];
    $sub      = $subParts[1] ?? '';

    if (!is_numeric($jobId)) {
        json_error('Ungueltige Job-ID', 400);
    }

    // POST /smartscan/jobs/{id}/process
    if ($sub === 'process' && $method === 'POST') {
        if (!hasPermission($payload['user_id'], 'smartscan_send')) {
            json_error('Keine Berechtigung fuer SmartScan-Versand', 403, [
                'required_permission' => 'smartscan_send',
            ]);
        }
        processChunk((int)$jobId, $payload);
        return;
    }

    // GET /smartscan/jobs/{id}
    if ($method === 'GET') {
        getJobDetail((int)$jobId, $payload);
        return;
    }

    json_error('Methode nicht erlaubt', 405);
}

// ============================================================================
// SETTINGS
// ============================================================================

/**
 * GET /smartscan/settings
 * Laedt die SmartScan-Einstellungen (single row, id=1).
 */
function getSmartScanSettings(array $payload): void {
    $settings = loadSettings();

    // Passwort aus E-Mail-Account NICHT zurueckgeben
    if ($settings && !empty($settings['email_account_id'])) {
        $account = Database::queryOne(
            'SELECT id, smtp_host, smtp_port, smtp_encryption, username, from_address, from_name
             FROM email_accounts WHERE id = ?',
            [$settings['email_account_id']]
        );
        $settings['email_account'] = $account;
    }

    // IMAP-Poll-Account (ohne Passwort)
    if ($settings && !empty($settings['imap_poll_account_id'])) {
        $imapAccount = Database::queryOne(
            'SELECT id, smtp_host, smtp_port, smtp_encryption, username, from_address, from_name
             FROM email_accounts WHERE id = ?',
            [$settings['imap_poll_account_id']]
        );
        $settings['imap_poll_account'] = $imapAccount;
    }

    json_success(['settings' => $settings]);
}

/**
 * PUT /admin/smartscan/settings
 * Speichert die SmartScan-Einstellungen (UPSERT id=1).
 */
function saveSmartScanSettings(array $payload): void {
    $data = get_json_body();

    $allowedFields = [
        'enabled', 'email_account_id', 'target_address',
        'subject_template', 'body_template',
        'send_mode_default', 'batch_max_attachments', 'batch_max_total_mb',
        'archive_after_send', 'recolor_after_send', 'recolor_color',
        'imap_auto_import', 'imap_filter_mode', 'imap_filter_keyword',
        'imap_sender_mode', 'imap_allowed_senders', 'imap_poll_account_id',
    ];

    // send_mode_default validieren
    if (isset($data['send_mode_default'])) {
        if (!in_array($data['send_mode_default'], ['single', 'batch'], true)) {
            json_error('send_mode_default muss "single" oder "batch" sein', 400);
        }
    }

    // recolor_color validieren
    $validColors = ['green', 'red', 'blue', 'orange', 'purple', 'pink', 'cyan', 'yellow'];
    if (isset($data['recolor_color']) && $data['recolor_color'] !== null && $data['recolor_color'] !== '') {
        if (!in_array($data['recolor_color'], $validColors, true)) {
            json_error('Ungueltige Farbe: ' . $data['recolor_color'], 400);
        }
    }

    // Pruefen ob Zeile existiert
    $existing = Database::queryOne('SELECT id FROM smartscan_settings WHERE id = 1');

    if ($existing) {
        // UPDATE
        $sets   = [];
        $params = [];
        foreach ($allowedFields as $field) {
            if (array_key_exists($field, $data)) {
                $sets[]   = "$field = ?";
                $params[] = $data[$field];
            }
        }
        if (empty($sets)) {
            json_error('Keine Aenderungen angegeben', 400);
        }
        $params[] = 1;
        Database::execute(
            'UPDATE smartscan_settings SET ' . implode(', ', $sets) . ' WHERE id = ?',
            $params
        );
    } else {
        // INSERT mit id=1
        $fields = ['id'];
        $values = [1];
        $placeholders = ['?'];
        foreach ($allowedFields as $field) {
            if (array_key_exists($field, $data)) {
                $fields[]       = $field;
                $values[]       = $data[$field];
                $placeholders[] = '?';
            }
        }
        Database::insert(
            'INSERT INTO smartscan_settings (' . implode(', ', $fields) . ') VALUES (' . implode(', ', $placeholders) . ')',
            $values
        );
    }

    ActivityLogger::logAdmin($payload, 'smartscan_settings_saved', 'smartscan_settings', 1,
        'SmartScan-Einstellungen gespeichert',
        ['changed_fields' => array_keys(array_intersect_key($data, array_flip($allowedFields)))]
    );

    // Aktualisierte Einstellungen zurueckgeben
    $settings = loadSettings();
    json_success(['settings' => $settings], 'SmartScan-Einstellungen gespeichert');
}

/**
 * Laedt die Settings-Zeile (id=1) oder gibt Defaults zurueck.
 */
function loadSettings(): array {
    $row = Database::queryOne('SELECT * FROM smartscan_settings WHERE id = 1');

    if (!$row) {
        return [
            'id'                   => null,
            'enabled'              => 0,
            'email_account_id'     => null,
            'target_address'       => '',
            'subject_template'     => 'SmartScan {box} – {date}',
            'body_template'        => 'Anbei {count} Dokument(e) aus der Box "{box}".',
            'send_mode_default'    => 'batch',
            'batch_max_attachments'=> 5,
            'batch_max_total_mb'   => 20,
            'archive_after_send'   => 1,
            'recolor_after_send'   => 0,
            'recolor_color'        => null,
            'imap_auto_import'     => 0,
            'imap_filter_mode'     => 'none',
            'imap_filter_keyword'  => null,
            'imap_sender_mode'     => 'any',
            'imap_allowed_senders' => null,
            'imap_poll_account_id' => null,
        ];
    }

    return $row;
}

// ============================================================================
// SEND JOB
// ============================================================================

/**
 * POST /smartscan/send
 *
 * Body: {
 *   mode: 'single'|'batch',
 *   document_ids?: int[],
 *   box_type?: string,
 *   client_request_id?: string
 * }
 */
function startSendJob(array $payload): void {
    set_time_limit(300);
    ignore_user_abort(true);

    $data = get_json_body();

    $mode             = $data['mode'] ?? null;
    $documentIds      = $data['document_ids'] ?? null;
    $boxType          = $data['box_type'] ?? null;
    $clientRequestId  = $data['client_request_id'] ?? null;

    // --- Validierung ---

    if (!in_array($mode, ['single', 'batch'], true)) {
        json_error('mode muss "single" oder "batch" sein', 400);
    }

    if (empty($documentIds) && empty($boxType)) {
        json_error('document_ids oder box_type erforderlich', 400);
    }

    // --- Settings laden + pruefen ---

    $settings = loadSettings();
    if (empty($settings['id']) || !$settings['enabled']) {
        json_error('SmartScan ist deaktiviert', 400);
    }
    if (empty($settings['email_account_id'])) {
        json_error('Kein E-Mail-Konto konfiguriert', 400);
    }
    if (empty($settings['target_address'])) {
        json_error('Keine Ziel-Adresse konfiguriert', 400);
    }

    // --- Idempotenz: client_request_id pruefen ---

    if (!empty($clientRequestId)) {
        $existingJob = Database::queryOne(
            'SELECT id, status, total_items, processed_items
             FROM smartscan_jobs
             WHERE client_request_id = ?
               AND created_at >= DATE_SUB(NOW(), INTERVAL ? SECOND)',
            [$clientRequestId, SMARTSCAN_IDEMPOTENCY_WINDOW]
        );
        if ($existingJob) {
            json_success([
                'job_id'    => (int)$existingJob['id'],
                'status'    => $existingJob['status'],
                'total'     => (int)$existingJob['total_items'],
                'processed' => (int)$existingJob['processed_items'],
                'remaining' => (int)$existingJob['total_items'] - (int)$existingJob['processed_items'],
                'idempotent'=> true,
            ], 'Job bereits vorhanden (Idempotenz)');
        }
    }

    // --- Dokumente aufloesen ---

    if (!empty($documentIds) && is_array($documentIds)) {
        $docIds = array_map('intval', $documentIds);
        $docIds = array_filter($docIds, function ($id) { return $id > 0; });
    } else {
        // Alle nicht-archivierten Dokumente der Box
        $validBoxes = array_keys(BOX_DISPLAY_NAMES);
        if (!in_array($boxType, $validBoxes, true)) {
            json_error('Ungueltiger Box-Typ: ' . $boxType, 400);
        }
        $rows = Database::query(
            'SELECT id FROM documents WHERE box_type = ? AND COALESCE(is_archived, 0) = 0 ORDER BY id ASC',
            [$boxType]
        );
        $docIds = array_column($rows, 'id');
        $docIds = array_map('intval', $docIds);
    }

    if (empty($docIds)) {
        json_error('Keine Dokumente zum Versenden gefunden', 400);
    }

    // Dokument-Infos laden (fuer Snapshot)
    $placeholders = implode(',', array_fill(0, count($docIds), '?'));
    $documents = Database::query(
        "SELECT id, original_filename, storage_path, mime_type, file_size, box_type
         FROM documents
         WHERE id IN ($placeholders)",
        array_values($docIds)
    );

    if (empty($documents)) {
        json_error('Keine gueltigen Dokumente gefunden', 400);
    }

    // Box fuer Template bestimmen (erster Dokument-Box oder uebergebener box_type)
    $sourceBox = $boxType ?? ($documents[0]['box_type'] ?? 'sonstige');

    // --- Job erstellen (Transaktion) ---

    Database::beginTransaction();

    try {
        // Settings-Snapshot als JSON (fuer Nachvollziehbarkeit)
        $settingsSnapshot = json_encode([
            'email_account_id'      => $settings['email_account_id'],
            'target_address'        => $settings['target_address'],
            'subject_template'      => $settings['subject_template'],
            'body_template'         => $settings['body_template'],
            'batch_max_attachments' => $settings['batch_max_attachments'],
            'batch_max_total_mb'    => $settings['batch_max_total_mb'],
            'archive_after_send'    => $settings['archive_after_send'],
            'recolor_after_send'    => $settings['recolor_after_send'],
            'recolor_color'         => $settings['recolor_color'],
        ], JSON_UNESCAPED_UNICODE);

        $jobId = Database::insert(
            'INSERT INTO smartscan_jobs
                (user_id, username, status, mode, source_box, total_items, processed_items,
                 sent_emails, failed_emails, settings_snapshot, client_request_id, target_address)
             VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0, ?, ?, ?)',
            [
                $payload['user_id'],
                $payload['username'] ?? '',
                'queued',
                $mode,
                $sourceBox,
                count($documents),
                $settingsSnapshot,
                $clientRequestId,
                $settings['target_address'],
            ]
        );

        // Job-Items erstellen
        foreach ($documents as $doc) {
            Database::insert(
                'INSERT INTO smartscan_job_items
                    (job_id, document_id, original_filename, storage_path, mime_type, file_size, status)
                 VALUES (?, ?, ?, ?, ?, ?, ?)',
                [
                    $jobId,
                    (int)$doc['id'],
                    $doc['original_filename'],
                    $doc['storage_path'],
                    $doc['mime_type'],
                    (int)$doc['file_size'],
                    'queued',
                ]
            );
        }

        Database::commit();
    } catch (Exception $e) {
        Database::rollback();
        error_log('SmartScan startSendJob fehlgeschlagen: ' . $e->getMessage());
        json_error('Job konnte nicht erstellt werden: ' . $e->getMessage(), 500);
    }

    // Activity-Log
    ActivityLogger::log([
        'user_id'         => $payload['user_id'],
        'username'        => $payload['username'] ?? '',
        'action_category' => 'smartscan',
        'action'          => 'job_created',
        'entity_type'     => 'smartscan_job',
        'entity_id'       => $jobId,
        'description'     => "SmartScan-Job erstellt: {$mode}, " . count($documents) . " Dokument(e), Box: {$sourceBox}",
        'details'         => [
            'mode'         => $mode,
            'total'        => count($documents),
            'source_box'   => $sourceBox,
            'document_ids' => $docIds,
        ],
    ]);

    // --- Ersten Chunk sofort verarbeiten ---

    $chunkResult = processChunkInternal($jobId, $payload);

    json_success([
        'job_id'    => $jobId,
        'status'    => $chunkResult['status'],
        'total'     => count($documents),
        'processed' => $chunkResult['processed'],
        'remaining' => $chunkResult['remaining'],
        'errors'    => $chunkResult['errors'],
    ], 'SmartScan-Job gestartet');
}

// ============================================================================
// PROCESS CHUNK
// ============================================================================

/**
 * POST /smartscan/jobs/{id}/process
 * Verarbeitet den naechsten Chunk eines Jobs (HTTP-Endpunkt).
 */
function processChunk(int $jobId, array $payload): void {
    $result = processChunkInternal($jobId, $payload);

    json_success([
        'status'    => $result['status'],
        'processed' => $result['processed'],
        'remaining' => $result['remaining'],
        'errors'    => $result['errors'],
    ], $result['remaining'] > 0 ? 'Chunk verarbeitet, weitere Items ausstehend' : 'Alle Items verarbeitet');
}

/**
 * Interne Chunk-Verarbeitung.
 *
 * @return array{status:string, processed:int, remaining:int, errors:string[]}
 */
function processChunkInternal(int $jobId, array $payload): array {
    set_time_limit(300);
    ignore_user_abort(true);

    // --- Job laden und pruefen ---

    $job = Database::queryOne('SELECT * FROM smartscan_jobs WHERE id = ?', [$jobId]);
    if (!$job) {
        json_error('Job nicht gefunden', 404);
    }

    // Berechtigung: Eigener Job ODER Admin
    if ((int)$job['user_id'] !== (int)$payload['user_id'] && !isAdmin($payload['user_id'])) {
        json_error('Kein Zugriff auf diesen Job', 403);
    }

    // Status pruefen
    if (in_array($job['status'], ['sent', 'failed'], true)) {
        json_error('Job ist bereits abgeschlossen (Status: ' . $job['status'] . ')', 400);
    }

    // Status auf 'processing' setzen falls noch 'queued'
    if ($job['status'] === 'queued') {
        Database::execute('UPDATE smartscan_jobs SET status = ? WHERE id = ?', ['processing', $jobId]);
    }

    // --- Naechste queued Items laden ---

    $items = Database::query(
        'SELECT ji.*, d.storage_path AS doc_storage_path, d.original_filename AS doc_original_filename,
                d.mime_type AS doc_mime_type, d.file_size AS doc_file_size
         FROM smartscan_job_items ji
         LEFT JOIN documents d ON d.id = ji.document_id
         WHERE ji.job_id = ? AND ji.status = ?
         ORDER BY ji.id ASC
         LIMIT ?',
        [$jobId, 'queued', SMARTSCAN_CHUNK_SIZE]
    );

    if (empty($items)) {
        // Keine weiteren Items - Job finalisieren
        $finalStatus = finalizeJob($jobId);
        return [
            'status'    => $finalStatus,
            'processed' => (int)$job['processed_items'],
            'remaining' => 0,
            'errors'    => [],
        ];
    }

    // --- E-Mail-Account laden ---

    $settingsSnap = json_decode($job['settings_snapshot'], true) ?: [];
    $accountId    = $settingsSnap['email_account_id'] ?? null;

    if (!$accountId) {
        json_error('Kein E-Mail-Konto im Job-Snapshot', 500);
    }

    $account = Database::queryOne('SELECT * FROM email_accounts WHERE id = ?', [$accountId]);
    if (!$account) {
        json_error('E-Mail-Konto nicht gefunden (ID: ' . $accountId . ')', 500);
    }

    // Passwort entschluesseln
    $decryptedPassword = null;
    if (!empty($account['credentials_encrypted'])) {
        try {
            $decryptedPassword = Crypto::decrypt($account['credentials_encrypted']);
        } catch (Exception $e) {
            json_error('E-Mail-Passwort konnte nicht entschluesselt werden', 500);
        }
    }

    // --- Template-Variablen vorbereiten ---

    $targetAddress   = $job['target_address'];
    $sourceBox       = $job['source_box'] ?? 'sonstige';
    $boxDisplayName  = BOX_DISPLAY_NAMES[$sourceBox] ?? $sourceBox;
    $currentDate     = date('d.m.Y');
    $userName        = $job['username'] ?? ($payload['username'] ?? 'System');
    $totalItems      = (int)$job['total_items'];

    $subjectTemplate = $settingsSnap['subject_template'] ?? 'SmartScan {box} – {date}';
    $bodyTemplate    = $settingsSnap['body_template'] ?? 'Anbei {count} Dokument(e) aus der Box "{box}".';

    $archiveAfterSend = !empty($settingsSnap['archive_after_send']);
    $recolorAfterSend = !empty($settingsSnap['recolor_after_send']);
    $recolorColor     = $settingsSnap['recolor_color'] ?? null;
    $maxAttachments   = max(1, (int)($settingsSnap['batch_max_attachments'] ?? 5));
    $maxTotalMb       = max(1, (float)($settingsSnap['batch_max_total_mb'] ?? 20));
    $maxTotalBytes    = $maxTotalMb * 1024 * 1024;

    $errors         = [];
    $processedCount = 0;
    $sentEmails     = 0;
    $failedEmails   = 0;

    // --- Versandmodus ---

    $mode = $job['mode'] ?? 'batch';

    if ($mode === 'single') {
        // --- SINGLE: Jedes Dokument = 1 E-Mail ---

        foreach ($items as $item) {
            $attachments = buildAttachment($item);
            if ($attachments === null) {
                markItemFailed($item['id'], 'Datei nicht gefunden: ' . ($item['storage_path'] ?? $item['doc_storage_path'] ?? ''));
                $errors[]      = 'Datei nicht gefunden fuer Dokument #' . $item['document_id'];
                $failedEmails++;
                $processedCount++;
                continue;
            }

            $docCount     = 1;
            $subject      = renderTemplate($subjectTemplate, $boxDisplayName, $currentDate, $docCount, $userName);
            $body         = renderTemplate($bodyTemplate,    $boxDisplayName, $currentDate, $docCount, $userName);
            $documentHash = $attachments[0]['hash'] ?? null;

            // E-Mail-Record erstellen
            $emailId = Database::insert(
                'INSERT INTO smartscan_emails
                    (job_id, to_address, subject, body, attachment_count, total_size, status)
                 VALUES (?, ?, ?, ?, ?, ?, ?)',
                [
                    $jobId,
                    $targetAddress,
                    $subject,
                    $body,
                    1,
                    $attachments[0]['size'] ?? 0,
                    'sending',
                ]
            );

            // Senden
            try {
                $sendResult = sendEmail($account, $decryptedPassword, $targetAddress, $subject, $body, $attachments);

                // SMTP OK → DB Commit fuer E-Mail
                Database::execute(
                    'UPDATE smartscan_emails SET status = ?, message_id = ?, smtp_response = ? WHERE id = ?',
                    ['sent', $sendResult['message_id'] ?? '', $sendResult['response'] ?? '', $emailId]
                );

                // Item als gesendet markieren
                Database::execute(
                    'UPDATE smartscan_job_items SET status = ?, email_id = ?, document_hash = ? WHERE id = ?',
                    ['sent', $emailId, $documentHash, $item['id']]
                );

                // Post-Send-Aktionen: Archivieren
                if ($archiveAfterSend && $item['document_id']) {
                    Database::execute(
                        'UPDATE documents SET is_archived = 1 WHERE id = ?',
                        [$item['document_id']]
                    );
                    Database::execute(
                        'UPDATE smartscan_job_items SET archived = 1 WHERE id = ?',
                        [$item['id']]
                    );
                }

                // Post-Send-Aktionen: Umfaerben
                if ($recolorAfterSend && $recolorColor && $item['document_id']) {
                    Database::execute(
                        'UPDATE documents SET display_color = ? WHERE id = ?',
                        [$recolorColor, $item['document_id']]
                    );
                    Database::execute(
                        'UPDATE smartscan_job_items SET recolored = 1 WHERE id = ?',
                        [$item['id']]
                    );
                }

                $sentEmails++;

            } catch (Exception $e) {
                $errorMsg = $e->getMessage();
                error_log("SmartScan sendEmail fehlgeschlagen (Item {$item['id']}): " . $errorMsg);

                Database::execute(
                    'UPDATE smartscan_emails SET status = ?, error_message = ? WHERE id = ?',
                    ['failed', substr($errorMsg, 0, 1000), $emailId]
                );
                Database::execute(
                    'UPDATE smartscan_job_items SET status = ?, error_message = ? WHERE id = ?',
                    ['failed', substr($errorMsg, 0, 1000), $item['id']]
                );

                $errors[]     = 'Dokument #' . $item['document_id'] . ': ' . $errorMsg;
                $failedEmails++;
            }

            $processedCount++;
        }

    } else {
        // --- BATCH: Dokumente in Batches gruppieren ---

        $batches = buildBatches($items, $maxAttachments, $maxTotalBytes);

        foreach ($batches as $batch) {
            $attachments   = [];
            $batchSize     = 0;
            $batchItemIds  = [];
            $batchDocIds   = [];
            $allFilesOk    = true;

            // itemHashes: Index-korrespondierend zu $attachments (fuer Hash-Zuordnung)
            $itemHashes = [];

            foreach ($batch as $item) {
                $att = buildAttachment($item);
                if ($att === null) {
                    markItemFailed($item['id'], 'Datei nicht gefunden');
                    $errors[]   = 'Datei nicht gefunden fuer Dokument #' . $item['document_id'];
                    $allFilesOk = false;
                    $processedCount++;
                    continue;
                }
                $attachments[]  = $att[0];
                $batchSize     += $att[0]['size'] ?? 0;
                $batchItemIds[] = $item['id'];
                $batchDocIds[]  = $item['document_id'];
                $itemHashes[]   = $att[0]['hash'] ?? null;
            }

            if (empty($attachments)) {
                $failedEmails++;
                continue;
            }

            $docCount = count($attachments);
            $subject  = renderTemplate($subjectTemplate, $boxDisplayName, $currentDate, $docCount, $userName);
            $body     = renderTemplate($bodyTemplate,    $boxDisplayName, $currentDate, $docCount, $userName);

            // E-Mail-Record
            $emailId = Database::insert(
                'INSERT INTO smartscan_emails
                    (job_id, to_address, subject, body, attachment_count, total_size, status)
                 VALUES (?, ?, ?, ?, ?, ?, ?)',
                [
                    $jobId,
                    $targetAddress,
                    $subject,
                    $body,
                    $docCount,
                    $batchSize,
                    'sending',
                ]
            );

            try {
                $sendResult = sendEmail($account, $decryptedPassword, $targetAddress, $subject, $body, $attachments);

                // SMTP OK → E-Mail auf 'sent'
                Database::execute(
                    'UPDATE smartscan_emails SET status = ?, message_id = ?, smtp_response = ? WHERE id = ?',
                    ['sent', $sendResult['message_id'] ?? '', $sendResult['response'] ?? '', $emailId]
                );

                // Items als gesendet markieren + Hashes
                // $batchItemIds und $itemHashes sind index-korrespondierend
                foreach ($batchItemIds as $idx => $itemId) {
                    $hash = $itemHashes[$idx] ?? null;
                    Database::execute(
                        'UPDATE smartscan_job_items SET status = ?, email_id = ?, document_hash = ? WHERE id = ?',
                        ['sent', $emailId, $hash, $itemId]
                    );
                }

                // Post-Send: Archivieren
                if ($archiveAfterSend && !empty($batchDocIds)) {
                    $ph = implode(',', array_fill(0, count($batchDocIds), '?'));
                    Database::execute(
                        "UPDATE documents SET is_archived = 1 WHERE id IN ($ph)",
                        array_values($batchDocIds)
                    );
                    $ph2 = implode(',', array_fill(0, count($batchItemIds), '?'));
                    Database::execute(
                        "UPDATE smartscan_job_items SET archived = 1 WHERE id IN ($ph2)",
                        array_values($batchItemIds)
                    );
                }

                // Post-Send: Umfaerben
                if ($recolorAfterSend && $recolorColor && !empty($batchDocIds)) {
                    $ph = implode(',', array_fill(0, count($batchDocIds), '?'));
                    Database::execute(
                        "UPDATE documents SET display_color = ? WHERE id IN ($ph)",
                        array_merge([$recolorColor], array_values($batchDocIds))
                    );
                    $ph2 = implode(',', array_fill(0, count($batchItemIds), '?'));
                    Database::execute(
                        "UPDATE smartscan_job_items SET recolored = 1 WHERE id IN ($ph2)",
                        array_values($batchItemIds)
                    );
                }

                $sentEmails++;
                $processedCount += count($batchItemIds);

            } catch (Exception $e) {
                $errorMsg = $e->getMessage();
                error_log("SmartScan batch sendEmail fehlgeschlagen (Job {$jobId}): " . $errorMsg);

                Database::execute(
                    'UPDATE smartscan_emails SET status = ?, error_message = ? WHERE id = ?',
                    ['failed', substr($errorMsg, 0, 1000), $emailId]
                );

                foreach ($batchItemIds as $itemId) {
                    Database::execute(
                        'UPDATE smartscan_job_items SET status = ?, error_message = ? WHERE id = ?',
                        ['failed', substr($errorMsg, 0, 1000), $itemId]
                    );
                }

                $errors[]     = 'Batch-Versand fehlgeschlagen: ' . $errorMsg;
                $failedEmails++;
                $processedCount += count($batchItemIds);
            }
        }
    }

    // --- Job-Zaehler aktualisieren ---

    Database::execute(
        'UPDATE smartscan_jobs
         SET processed_items = processed_items + ?,
             sent_emails     = sent_emails + ?,
             failed_emails   = failed_emails + ?
         WHERE id = ?',
        [$processedCount, $sentEmails, $failedEmails, $jobId]
    );

    // Verbleibende Items zaehlen
    $remaining = Database::queryOne(
        'SELECT COUNT(*) AS cnt FROM smartscan_job_items WHERE job_id = ? AND status = ?',
        [$jobId, 'queued']
    );
    $remainingCount = (int)($remaining['cnt'] ?? 0);

    // Job finalisieren wenn keine Items mehr
    $jobStatus = 'processing';
    if ($remainingCount === 0) {
        $jobStatus = finalizeJob($jobId);
    }

    return [
        'status'    => $jobStatus,
        'processed' => $processedCount,
        'remaining' => $remainingCount,
        'errors'    => $errors,
    ];
}

// ============================================================================
// JOB FINALIZATION
// ============================================================================

/**
 * Finalisiert einen Job: Bestimmt finalen Status anhand der Item-Ergebnisse.
 *
 * @return string Finaler Status: 'sent', 'partial', 'failed'
 */
function finalizeJob(int $jobId): string {
    $counts = Database::queryOne(
        'SELECT
             SUM(CASE WHEN status = "sent"   THEN 1 ELSE 0 END) AS sent_count,
             SUM(CASE WHEN status = "failed"  THEN 1 ELSE 0 END) AS failed_count,
             COUNT(*) AS total
         FROM smartscan_job_items
         WHERE job_id = ?',
        [$jobId]
    );

    $sentCount   = (int)($counts['sent_count'] ?? 0);
    $failedCount = (int)($counts['failed_count'] ?? 0);
    $total       = (int)($counts['total'] ?? 0);

    if ($failedCount === 0 && $sentCount > 0) {
        $status = 'sent';
    } elseif ($sentCount === 0 && $failedCount > 0) {
        $status = 'failed';
    } elseif ($sentCount > 0 && $failedCount > 0) {
        $status = 'partial';
    } else {
        // Kein Item gesendet oder fehlgeschlagen (sollte nicht vorkommen)
        $status = 'failed';
    }

    Database::execute(
        'UPDATE smartscan_jobs SET status = ?, completed_at = NOW() WHERE id = ?',
        [$status, $jobId]
    );

    return $status;
}

// ============================================================================
// JOB LISTING & DETAIL
// ============================================================================

/**
 * GET /smartscan/jobs
 * Admin sieht alle Jobs, normale User nur eigene.
 * Query-Parameter: limit (default 50), offset (default 0)
 */
function listJobs(array $payload): void {
    $limit  = max(1, min(200, (int)($_GET['limit'] ?? 50)));
    $offset = max(0, (int)($_GET['offset'] ?? 0));
    $admin  = isAdmin($payload['user_id']);

    if ($admin) {
        $jobs = Database::query(
            'SELECT id, user_id, username, status, mode, source_box, total_items, processed_items,
                    sent_emails, failed_emails, target_address, client_request_id,
                    created_at, completed_at
             FROM smartscan_jobs
             ORDER BY created_at DESC
             LIMIT ? OFFSET ?',
            [$limit, $offset]
        );
        $countRow = Database::queryOne('SELECT COUNT(*) AS cnt FROM smartscan_jobs');
    } else {
        $jobs = Database::query(
            'SELECT id, user_id, username, status, mode, source_box, total_items, processed_items,
                    sent_emails, failed_emails, target_address, client_request_id,
                    created_at, completed_at
             FROM smartscan_jobs
             WHERE user_id = ?
             ORDER BY created_at DESC
             LIMIT ? OFFSET ?',
            [$payload['user_id'], $limit, $offset]
        );
        $countRow = Database::queryOne(
            'SELECT COUNT(*) AS cnt FROM smartscan_jobs WHERE user_id = ?',
            [$payload['user_id']]
        );
    }

    json_success([
        'jobs'  => $jobs,
        'total' => (int)($countRow['cnt'] ?? 0),
    ]);
}

/**
 * GET /smartscan/jobs/{id}
 * Job-Detail mit Items und E-Mails.
 */
function getJobDetail(int $jobId, array $payload): void {
    $job = Database::queryOne('SELECT * FROM smartscan_jobs WHERE id = ?', [$jobId]);
    if (!$job) {
        json_error('Job nicht gefunden', 404);
    }

    // Berechtigung: eigener Job oder Admin
    if ((int)$job['user_id'] !== (int)$payload['user_id'] && !isAdmin($payload['user_id'])) {
        json_error('Kein Zugriff auf diesen Job', 403);
    }

    // Items laden
    $items = Database::query(
        'SELECT id, document_id, original_filename, status, email_id, document_hash,
                archived, recolored, error_message, created_at
         FROM smartscan_job_items
         WHERE job_id = ?
         ORDER BY id ASC',
        [$jobId]
    );

    // E-Mails laden
    $emails = Database::query(
        'SELECT id, to_address, subject, attachment_count, total_size, status,
                message_id, error_message, created_at
         FROM smartscan_emails
         WHERE job_id = ?
         ORDER BY id ASC',
        [$jobId]
    );

    // settings_snapshot nicht an nicht-Admins leaken (enthaelt Account-ID)
    if (!isAdmin($payload['user_id'])) {
        unset($job['settings_snapshot']);
    }

    json_success([
        'job'    => $job,
        'items'  => $items,
        'emails' => $emails,
    ]);
}

// ============================================================================
// E-MAIL SENDEN
// ============================================================================

/**
 * Sendet eine E-Mail via PHPMailer SMTP.
 *
 * @param array       $account           E-Mail-Account-Zeile aus DB
 * @param string|null $decryptedPassword Entschluesseltes Passwort
 * @param string      $toAddress         Ziel-Adresse
 * @param string      $subject           Betreff
 * @param string      $body              Nachrichtentext
 * @param array       $attachments       [{path, name, size?, hash?}, ...]
 * @return array      ['message_id' => string, 'response' => string]
 * @throws Exception  Bei SMTP-Fehler
 */
function sendEmail(array $account, ?string $decryptedPassword, string $toAddress, string $subject, string $body, array $attachments): array {
    $mail = new PHPMailer(true);

    try {
        $mail->isSMTP();
        $mail->Host       = $account['smtp_host'];
        $mail->Port       = (int)$account['smtp_port'];
        $mail->SMTPAuth   = true;
        $mail->Username   = $account['username'];
        $mail->Password   = $decryptedPassword ?? '';
        $mail->CharSet    = 'UTF-8';

        // Verschluesselung
        $encryption = $account['smtp_encryption'] ?? 'tls';
        if ($encryption === 'ssl') {
            $mail->SMTPSecure = PHPMailer::ENCRYPTION_SMTPS;
        } elseif ($encryption === 'none') {
            $mail->SMTPSecure  = '';
            $mail->SMTPAutoTLS = false;
        } else {
            // Default: STARTTLS
            $mail->SMTPSecure = PHPMailer::ENCRYPTION_STARTTLS;
        }

        $mail->setFrom(
            $account['from_address'] ?? $account['username'],
            $account['from_name'] ?? ''
        );

        $mail->addAddress($toAddress);
        $mail->Subject = $subject;
        $mail->Body    = $body;

        // Anhaenge
        foreach ($attachments as $att) {
            if (!empty($att['path']) && file_exists($att['path'])) {
                $mail->addAttachment($att['path'], $att['name'] ?? basename($att['path']));
            }
        }

        $mail->send();

        return [
            'message_id' => $mail->getLastMessageID() ?? '',
            'response'   => '',
        ];

    } catch (PHPMailerException $e) {
        throw new Exception('SMTP-Fehler: ' . $mail->ErrorInfo);
    }
}

// ============================================================================
// TEMPLATE RENDERING
// ============================================================================

/**
 * Ersetzt Platzhalter in Subject/Body Templates.
 *
 * Platzhalter:
 *   {box}   → Box-Anzeigename
 *   {date}  → Aktuelles Datum DD.MM.YYYY
 *   {count} → Anzahl Dokumente
 *   {user}  → Benutzername
 */
function renderTemplate(string $template, string $boxName, string $date, int $count, string $user): string {
    return str_replace(
        ['{box}', '{date}', '{count}', '{user}'],
        [$boxName, $date, (string)$count, $user],
        $template
    );
}

// ============================================================================
// HILFSFUNKTIONEN
// ============================================================================

/**
 * Baut ein Attachment-Array aus einem Job-Item.
 *
 * @param  array      $item Job-Item-Zeile (mit doc_* Feldern aus JOIN)
 * @return array|null [{path, name, size, hash}] oder null wenn Datei fehlt
 */
function buildAttachment(array $item): ?array {
    // storage_path entweder aus Item-Snapshot oder aus Document-JOIN
    $storagePath = $item['storage_path'] ?? $item['doc_storage_path'] ?? null;
    $filename    = $item['original_filename'] ?? $item['doc_original_filename'] ?? 'dokument';

    if (empty($storagePath)) {
        return null;
    }

    $fullPath = DOCUMENTS_PATH . $storagePath;
    if (!file_exists($fullPath)) {
        return null;
    }

    $fileSize = filesize($fullPath);
    $hash     = hash_file('sha256', $fullPath);

    return [[
        'path' => $fullPath,
        'name' => $filename,
        'size' => $fileSize,
        'hash' => $hash,
    ]];
}

/**
 * Markiert ein Job-Item als fehlgeschlagen.
 */
function markItemFailed(int $itemId, string $errorMessage): void {
    Database::execute(
        'UPDATE smartscan_job_items SET status = ?, error_message = ? WHERE id = ?',
        ['failed', substr($errorMessage, 0, 1000), $itemId]
    );
}

/**
 * Gruppiert Items in Batches unter Beachtung der Grenzwerte.
 *
 * @param  array $items          Job-Items
 * @param  int   $maxAttachments Max. Anhaenge pro E-Mail
 * @param  float $maxTotalBytes  Max. Gesamtgroesse in Bytes
 * @return array Array von Batches (jeder Batch = Array von Items)
 */
function buildBatches(array $items, int $maxAttachments, float $maxTotalBytes): array {
    $batches      = [];
    $currentBatch = [];
    $currentSize  = 0;
    $currentCount = 0;

    foreach ($items as $item) {
        $fileSize = (int)($item['file_size'] ?? $item['doc_file_size'] ?? 0);

        // Neuen Batch starten wenn Grenzen ueberschritten wuerden
        if ($currentCount > 0 && (
            $currentCount >= $maxAttachments ||
            ($currentSize + $fileSize) > $maxTotalBytes
        )) {
            $batches[]    = $currentBatch;
            $currentBatch = [];
            $currentSize  = 0;
            $currentCount = 0;
        }

        $currentBatch[] = $item;
        $currentSize   += $fileSize;
        $currentCount++;
    }

    // Letzten Batch hinzufuegen
    if (!empty($currentBatch)) {
        $batches[] = $currentBatch;
    }

    return $batches;
}

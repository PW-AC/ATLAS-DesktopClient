<?php
/**
 * BiPro API - Releases / Auto-Update
 * 
 * Oeffentlicher Endpoint fuer Update-Checks + Admin CRUD fuer Release-Verwaltung.
 * 
 * Oeffentliche Endpunkte (keine Auth):
 * - GET /updates/check?version=X&channel=Y    - Update pruefen
 * - GET /releases/latest                      - Neueste Version herunterladen (fuer neue Nutzer)
 * - GET /releases/download/{id}               - Datei herunterladen nach ID (zaehlt Downloads)
 * 
 * Admin-Endpunkte:
 * - GET    /admin/releases                    - Alle Releases auflisten
 * - GET    /admin/releases/{id}               - Einzelnes Release
 * - POST   /admin/releases                    - Neues Release hochladen
 * - PUT    /admin/releases/{id}               - Release bearbeiten
 * - DELETE /admin/releases/{id}               - Release loeschen
 */

require_once __DIR__ . '/lib/db.php';
require_once __DIR__ . '/lib/response.php';

// Runtime-Limits fuer grosse Uploads (upload_max_filesize/post_max_size via .user.ini)
@ini_set('max_execution_time', '600');
@ini_set('max_input_time', '600');
@ini_set('memory_limit', '300M');

// Pfad zum Releases-Verzeichnis
define('RELEASES_PATH', __DIR__ . '/../releases/');

// Maximale Upload-Groesse fuer Installer (250 MB)
define('MAX_RELEASE_SIZE', 250 * 1024 * 1024);


/**
 * Oeffentlicher Update-Check Endpoint.
 * Keine Authentifizierung erforderlich.
 */
function handleUpdateCheckRequest(string $method): void {
    if ($method !== 'GET') {
        json_error('Methode nicht erlaubt', 405);
    }
    
    $currentVersion = $_GET['version'] ?? '';
    $channel = $_GET['channel'] ?? 'stable';
    
    if (empty($currentVersion)) {
        json_error('Parameter "version" erforderlich', 400);
    }
    
    // Validierung Channel
    $validChannels = ['stable', 'beta', 'dev'];
    if (!in_array($channel, $validChannels)) {
        $channel = 'stable';
    }
    
    // Neueste verfuegbare Version finden (active oder mandatory)
    $latest = Database::queryOne(
        "SELECT * FROM releases 
         WHERE channel = ? AND status IN ('active', 'mandatory')
         ORDER BY released_at DESC 
         LIMIT 1",
        [$channel]
    );
    
    if (!$latest) {
        // Keine Releases vorhanden
        json_response([
            'current_version' => $currentVersion,
            'latest_version' => $currentVersion,
            'update_available' => false,
            'mandatory' => false,
            'deprecated' => false
        ]);
        return;
    }
    
    // Versionen vergleichen
    $updateAvailable = version_compare($latest['version'], $currentVersion, '>');
    
    // Mandatory pruefen
    $mandatory = false;
    if ($updateAvailable) {
        // Fall 1: Neueste Version ist als mandatory markiert
        if ($latest['status'] === 'mandatory') {
            $mandatory = true;
        }
        // Fall 2: Aktuelle Version liegt unter min_version
        if (!empty($latest['min_version']) && version_compare($currentVersion, $latest['min_version'], '<')) {
            $mandatory = true;
        }
    }
    
    // Deprecated pruefen: Ist die aktuelle Version als deprecated/withdrawn markiert?
    $deprecated = false;
    $currentRelease = Database::queryOne(
        "SELECT status FROM releases WHERE version = ?",
        [$currentVersion]
    );
    if ($currentRelease && in_array($currentRelease['status'], ['deprecated', 'withdrawn'])) {
        $deprecated = true;
    }
    // Auch deprecated wenn aktuelle Version gar nicht in DB existiert und es neuere gibt
    if (!$currentRelease && $updateAvailable) {
        $deprecated = false; // Unbekannte Version ist nicht deprecated, nur veraltet
    }
    
    $response = [
        'current_version' => $currentVersion,
        'latest_version' => $latest['version'],
        'update_available' => $updateAvailable,
        'mandatory' => $mandatory,
        'deprecated' => $deprecated,
    ];
    
    if ($updateAvailable) {
        $response['release_notes'] = $latest['release_notes'] ?? '';
        $response['download_url'] = API_BASE_URL . 'releases/download/' . $latest['id'];
        $response['sha256'] = $latest['sha256'];
        $response['file_size'] = (int)$latest['file_size'];
        $response['released_at'] = $latest['released_at'];
    }
    
    json_response($response);
}


/**
 * Oeffentliche Release-Liste (fuer Mitteilungszentrale).
 * Gibt aktive/mandatory Releases zurueck (ohne Admin-Felder).
 * Keine Authentifizierung erforderlich.
 */
function handlePublicReleasesList(): void {
    $releases = Database::query(
        "SELECT version, release_notes, released_at, status
         FROM releases
         WHERE status NOT IN ('withdrawn')
         ORDER BY released_at DESC
         LIMIT 50"
    );
    
    json_response([
        'success' => true,
        'data' => ['releases' => $releases ?: []]
    ]);
}


/**
 * Oeffentlicher Download der neuesten Version (fuer neue Nutzer).
 * Keine Authentifizierung, kein Parameter noetig.
 * Findet das neueste stable Release und liefert die Datei aus.
 * URL: GET /releases/latest
 */
function handleLatestDownload(): void {
    $latest = Database::queryOne(
        "SELECT * FROM releases
         WHERE channel = 'stable' AND status IN ('active', 'mandatory')
         ORDER BY released_at DESC
         LIMIT 1"
    );

    if (!$latest) {
        json_error('Kein Release verfuegbar', 404);
    }

    $filePath = RELEASES_PATH . $latest['filename'];
    if (!file_exists($filePath)) {
        error_log("Release-Datei nicht gefunden: {$filePath}");
        json_error('Release-Datei nicht gefunden', 404);
    }

    Database::execute(
        "UPDATE releases SET download_count = download_count + 1 WHERE id = ?",
        [$latest['id']]
    );

    header('Content-Type: application/octet-stream');
    header('Content-Disposition: attachment; filename="' . $latest['filename'] . '"');
    header('Content-Length: ' . $latest['file_size']);
    header('X-SHA256: ' . $latest['sha256']);
    header('X-Version: ' . $latest['version']);

    readfile($filePath);
    exit();
}


/**
 * Oeffentlicher Download-Endpoint (zaehlt Downloads).
 */
function handleReleaseDownload(int $releaseId): void {
    $release = Database::queryOne(
        "SELECT * FROM releases WHERE id = ?",
        [$releaseId]
    );
    
    if (!$release) {
        json_error('Release nicht gefunden', 404);
    }
    
    if ($release['status'] === 'withdrawn') {
        json_error('Release wurde zurueckgezogen', 410);
    }
    
    $filePath = RELEASES_PATH . $release['filename'];
    if (!file_exists($filePath)) {
        error_log("Release-Datei nicht gefunden: {$filePath}");
        json_error('Release-Datei nicht gefunden', 404);
    }
    
    // Download-Zaehler erhoehen
    Database::execute(
        "UPDATE releases SET download_count = download_count + 1 WHERE id = ?",
        [$releaseId]
    );
    
    // Datei senden
    header('Content-Type: application/octet-stream');
    header('Content-Disposition: attachment; filename="' . $release['filename'] . '"');
    header('Content-Length: ' . $release['file_size']);
    header('X-SHA256: ' . $release['sha256']);
    
    readfile($filePath);
    exit();
}


// ================================================================
// Admin-Endpunkte
// ================================================================

/**
 * Admin: Releases verwalten.
 */
function handleAdminReleasesRequest(?string $action, string $method, ?string $subAction = null): void {
    require_once __DIR__ . '/lib/jwt.php';
    require_once __DIR__ . '/lib/permissions.php';
    require_once __DIR__ . '/lib/activity_logger.php';
    
    $payload = requireAdmin();
    
    // GET /admin/releases - Alle auflisten
    if ($method === 'GET' && ($action === null || $action === '')) {
        handleListReleases();
        return;
    }
    
    // POST /admin/releases - Neues Release
    if ($method === 'POST' && ($action === null || $action === '')) {
        handleCreateRelease($payload);
        return;
    }
    
    // GET /admin/releases/schema-snapshot - DB-Schema-Snapshot
    if ($action === 'schema-snapshot' && $method === 'GET') {
        handleSchemaSnapshot($payload);
        return;
    }

    // Ab hier brauchen wir eine Release-ID
    if (!is_numeric($action)) {
        json_error('Release-ID erforderlich', 400);
    }
    
    $releaseId = (int)$action;
    
    // POST /admin/releases/{id}/validate - Release Gate Validation
    if ($subAction === 'validate' && $method === 'POST') {
        handleValidateRelease($releaseId, $payload);
        return;
    }

    // POST /admin/releases/{id}/withdraw - Release zurueckziehen mit Auto-Fallback
    if ($subAction === 'withdraw' && $method === 'POST') {
        handleWithdrawRelease($releaseId, $payload);
        return;
    }
    
    switch ($method) {
        case 'GET':
            handleGetRelease($releaseId);
            break;
        case 'PUT':
            handleUpdateRelease($releaseId, $payload);
            break;
        case 'DELETE':
            handleDeleteRelease($releaseId, $payload);
            break;
        default:
            json_error('Methode nicht erlaubt', 405);
    }
}


/**
 * Alle Releases auflisten.
 */
function handleListReleases(): void {
    $releases = Database::query(
        "SELECT r.*, u.username as released_by_name
         FROM releases r
         LEFT JOIN users u ON u.id = r.released_by
         ORDER BY r.released_at DESC"
    );
    
    json_success(['releases' => $releases]);
}


/**
 * Einzelnes Release abrufen.
 */
function handleGetRelease(int $id): void {
    $release = Database::queryOne(
        "SELECT r.*, u.username as released_by_name
         FROM releases r
         LEFT JOIN users u ON u.id = r.released_by
         WHERE r.id = ?",
        [$id]
    );
    
    if (!$release) {
        json_error('Release nicht gefunden', 404);
    }
    
    json_success(['release' => $release]);
}


/**
 * Neues Release erstellen (mit Datei-Upload).
 */
function handleCreateRelease(array $adminPayload): void {
    // Diagnostik: Wenn POST und FILES leer sind, wurde Upload von PHP abgelehnt
    if (empty($_POST) && empty($_FILES)) {
        $maxPost = ini_get('post_max_size');
        $maxUpload = ini_get('upload_max_filesize');
        json_error(
            "Upload von PHP abgelehnt (POST und FILES leer). " .
            "Wahrscheinlich ueberschreitet die Datei die PHP-Limits: " .
            "post_max_size={$maxPost}, upload_max_filesize={$maxUpload}. " .
            "Bitte .user.ini oder php.ini im API-Verzeichnis pruefen.",
            413
        );
    }
    
    // Multipart Form-Data Felder
    $version = $_POST['version'] ?? '';
    $channel = $_POST['channel'] ?? 'stable';
    $releaseNotes = $_POST['release_notes'] ?? '';
    $minVersion = $_POST['min_version'] ?? null;
    
    if (empty($version)) {
        json_error('Version ist erforderlich. POST-Felder: ' . implode(', ', array_keys($_POST)), 400);
    }
    
    // SemVer-Validierung (grob)
    if (!preg_match('/^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$/', $version)) {
        json_error('Version muss dem Format X.Y.Z entsprechen (z.B. 1.0.0 oder 1.1.0-beta.1)', 400);
    }
    
    // Pruefen ob Version bereits existiert
    $existing = Database::queryOne(
        "SELECT id FROM releases WHERE version = ?",
        [$version]
    );
    if ($existing) {
        json_error("Version {$version} existiert bereits", 409);
    }
    
    // Datei-Upload pruefen
    if (!isset($_FILES['file']) || $_FILES['file']['error'] !== UPLOAD_ERR_OK) {
        $errorMessages = [
            UPLOAD_ERR_INI_SIZE => 'Datei zu gross (PHP-Limit)',
            UPLOAD_ERR_FORM_SIZE => 'Datei zu gross (Formular-Limit)',
            UPLOAD_ERR_PARTIAL => 'Upload unvollstaendig',
            UPLOAD_ERR_NO_FILE => 'Keine Datei gesendet',
            UPLOAD_ERR_NO_TMP_DIR => 'Temporaeres Verzeichnis fehlt',
            UPLOAD_ERR_CANT_WRITE => 'Schreibfehler auf Disk',
        ];
        $errCode = $_FILES['file']['error'] ?? UPLOAD_ERR_NO_FILE;
        $msg = $errorMessages[$errCode] ?? "Upload-Fehler (Code: {$errCode})";
        json_error($msg, 400);
    }
    
    $tmpFile = $_FILES['file']['tmp_name'];
    $fileSize = filesize($tmpFile);
    
    if ($fileSize > MAX_RELEASE_SIZE) {
        json_error('Datei zu gross (max. ' . round(MAX_RELEASE_SIZE / 1024 / 1024) . ' MB)', 400);
    }
    
    // Dateiname normalisieren
    $filename = "ACENCIA-ATLAS-Setup-{$version}.exe";
    
    // Releases-Verzeichnis sicherstellen
    if (!is_dir(RELEASES_PATH)) {
        mkdir(RELEASES_PATH, 0755, true);
    }
    
    $targetPath = RELEASES_PATH . $filename;
    
    // SHA256 berechnen
    $sha256 = hash_file('sha256', $tmpFile);
    
    // Datei verschieben
    if (!move_uploaded_file($tmpFile, $targetPath)) {
        json_error('Datei konnte nicht gespeichert werden', 500);
    }
    
    // Channel validieren
    $validChannels = ['stable', 'beta', 'dev'];
    if (!in_array($channel, $validChannels)) {
        $channel = 'stable';
    }
    
    // Optionalen Smoke-Test-Report verarbeiten
    $smokeTestReport = null;
    if (!empty($_POST['smoke_test_report'])) {
        $reportJson = json_decode($_POST['smoke_test_report'], true);
        if ($reportJson !== null) {
            $smokeTestReport = json_encode($reportJson);
        }
    }

    // Optionale required_schema
    $requiredSchema = !empty($_POST['required_schema']) ? trim($_POST['required_schema']) : null;

    // In DB speichern (Status = 'pending' -- Release Gate Engine)
    $id = Database::insert(
        "INSERT INTO releases (version, channel, status, min_version, release_notes, filename, file_size, sha256, required_schema, smoke_test_report, released_by)
         VALUES (?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            $version,
            $channel,
            $minVersion ?: null,
            $releaseNotes,
            $filename,
            $fileSize,
            $sha256,
            $requiredSchema,
            $smokeTestReport,
            $adminPayload['user_id']
        ]
    );
    
    // Aktivitaet loggen
    ActivityLogger::log([
        'user_id' => $adminPayload['user_id'],
        'username' => $adminPayload['username'] ?? '',
        'action_category' => 'admin',
        'action' => 'release_created',
        'description' => "Release {$version} ({$channel}) hochgeladen",
        'details' => ['release_id' => $id, 'version' => $version, 'channel' => $channel],
        'status' => 'success'
    ]);
    
    $release = Database::queryOne("SELECT * FROM releases WHERE id = ?", [$id]);
    json_success(['release' => $release], "Release {$version} erfolgreich erstellt");
}


/**
 * Release bearbeiten (Status, Notes, Min-Version, Channel).
 */
function handleUpdateRelease(int $id, array $adminPayload): void {
    $release = Database::queryOne("SELECT * FROM releases WHERE id = ?", [$id]);
    
    if (!$release) {
        json_error('Release nicht gefunden', 404);
    }
    
    $data = get_json_body();
    
    $updates = [];
    $params = [];
    $changes = [];
    
    // Status aendern (mit erlaubten Uebergaengen)
    if (isset($data['status'])) {
        $validStatuses = ['active', 'mandatory', 'deprecated', 'withdrawn'];
        if (!in_array($data['status'], $validStatuses)) {
            json_error('Ungueltiger Status. Erlaubt: ' . implode(', ', $validStatuses), 400);
        }
        
        $currentStatus = $release['status'];
        $newStatus = $data['status'];
        
        // Gate-Engine: Status-Uebergaenge erzwingen
        $allowedTransitions = [
            'pending'    => [],
            'validated'  => ['active'],
            'blocked'    => [],
            'active'     => ['mandatory', 'deprecated', 'withdrawn'],
            'mandatory'  => ['withdrawn'],
            'deprecated' => ['withdrawn'],
            'withdrawn'  => [],
        ];
        
        $allowed = $allowedTransitions[$currentStatus] ?? [];
        if (!in_array($newStatus, $allowed)) {
            json_error("Status-Uebergang '{$currentStatus}' → '{$newStatus}' nicht erlaubt. Erlaubt von '{$currentStatus}': " . (empty($allowed) ? 'keine' : implode(', ', $allowed)), 400);
        }
        
        $updates[] = 'status = ?';
        $params[] = $newStatus;
        $changes[] = "Status: {$currentStatus} → {$newStatus}";
    }
    
    // Channel aendern
    if (isset($data['channel'])) {
        $validChannels = ['stable', 'beta', 'dev'];
        if (!in_array($data['channel'], $validChannels)) {
            json_error('Ungueltiger Channel. Erlaubt: ' . implode(', ', $validChannels), 400);
        }
        $updates[] = 'channel = ?';
        $params[] = $data['channel'];
        $changes[] = "Channel: {$release['channel']} → {$data['channel']}";
    }
    
    // Release Notes aendern
    if (isset($data['release_notes'])) {
        $updates[] = 'release_notes = ?';
        $params[] = $data['release_notes'];
        $changes[] = "Release Notes aktualisiert";
    }
    
    // Min-Version aendern
    if (array_key_exists('min_version', $data)) {
        $minVersion = $data['min_version'];
        if ($minVersion !== null && !empty($minVersion) && !preg_match('/^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$/', $minVersion)) {
            json_error('min_version muss dem Format X.Y.Z entsprechen', 400);
        }
        $updates[] = 'min_version = ?';
        $params[] = $minVersion ?: null;
        $changes[] = "Min-Version: " . ($minVersion ?: 'keine');
    }
    
    if (empty($updates)) {
        json_error('Keine Aenderungen angegeben', 400);
    }
    
    $params[] = $id;
    Database::execute(
        "UPDATE releases SET " . implode(', ', $updates) . " WHERE id = ?",
        $params
    );
    
    // Aktivitaet loggen
    ActivityLogger::log([
        'user_id' => $adminPayload['user_id'],
        'username' => $adminPayload['username'] ?? '',
        'action_category' => 'admin',
        'action' => 'release_updated',
        'description' => "Release {$release['version']} bearbeitet: " . implode(', ', $changes),
        'details' => ['release_id' => $id, 'version' => $release['version'], 'changes' => $changes],
        'status' => 'success'
    ]);
    
    $updated = Database::queryOne("SELECT * FROM releases WHERE id = ?", [$id]);
    json_success(['release' => $updated], "Release {$release['version']} aktualisiert");
}


/**
 * Release loeschen (nur wenn keine Downloads).
 */
function handleDeleteRelease(int $id, array $adminPayload): void {
    $release = Database::queryOne("SELECT * FROM releases WHERE id = ?", [$id]);
    
    if (!$release) {
        json_error('Release nicht gefunden', 404);
    }
    
    if ((int)$release['download_count'] > 0) {
        json_error(
            "Release kann nicht geloescht werden ({$release['download_count']} Downloads). " .
            "Setzen Sie den Status stattdessen auf 'withdrawn'.",
            409,
            ['download_count' => (int)$release['download_count']]
        );
    }
    
    // Datei loeschen
    $filePath = RELEASES_PATH . $release['filename'];
    if (file_exists($filePath)) {
        unlink($filePath);
    }
    
    // DB-Eintrag loeschen
    Database::execute("DELETE FROM releases WHERE id = ?", [$id]);
    
    // Aktivitaet loggen
    ActivityLogger::log([
        'user_id' => $adminPayload['user_id'],
        'username' => $adminPayload['username'] ?? '',
        'action_category' => 'admin',
        'action' => 'release_deleted',
        'description' => "Release {$release['version']} geloescht",
        'details' => ['release_id' => $id, 'version' => $release['version']],
        'status' => 'success'
    ]);
    
    json_success([], "Release {$release['version']} geloescht");
}


/**
 * Release Gate Engine: Fuehrt alle Validierungs-Gates aus.
 * POST /admin/releases/{id}/validate
 */
function handleValidateRelease(int $id, array $adminPayload): void {
    $release = Database::queryOne("SELECT * FROM releases WHERE id = ?", [$id]);
    
    if (!$release) {
        json_error('Release nicht gefunden', 404);
    }
    
    if (!in_array($release['status'], ['pending', 'blocked'])) {
        json_error("Validierung nur fuer Releases mit Status 'pending' oder 'blocked' moeglich (aktuell: '{$release['status']}')", 400);
    }
    
    $gates = [];
    $allPassed = true;
    
    // Gate 1: Schema-Version
    $gate1 = _gateCheckSchemaVersion($release);
    $gates[] = $gate1;
    if ($gate1['status'] === 'failed') $allPassed = false;
    
    // Gate 2: Split-Invariante (nur fuer stable/beta)
    if (in_array($release['channel'], ['stable', 'beta'])) {
        $gate2 = _gateCheckSplitInvariant();
        $gates[] = $gate2;
        if ($gate2['status'] === 'failed') $allPassed = false;
    }
    
    // Gate 3: Matching-Konsistenz (nur fuer stable/beta)
    if (in_array($release['channel'], ['stable', 'beta'])) {
        $gate3 = _gateCheckMatchingConsistency();
        $gates[] = $gate3;
        if ($gate3['status'] === 'failed') $allPassed = false;
    }
    
    // Gate 4: Smoke-Test-Report
    $gate4 = _gateCheckSmokeTestReport($release);
    $gates[] = $gate4;
    if ($gate4['status'] === 'failed') $allPassed = false;
    
    // Gate 5: Versions-Konsistenz
    $gate5 = _gateCheckVersionConsistency($release);
    $gates[] = $gate5;
    if ($gate5['status'] === 'failed') $allPassed = false;
    
    // Gate 6: Schema-Struktur (Tabellen, Indexes, Spalten)
    if (in_array($release['channel'], ['stable', 'beta'])) {
        $gate6 = _gateCheckSchemaStructure();
        $gates[] = $gate6;
        if ($gate6['status'] === 'failed') $allPassed = false;
    }
    
    // Gate 7: Daten-Integritaet (Orphaned FKs, Referenz-Pruefung)
    if (in_array($release['channel'], ['stable', 'beta'])) {
        $gate7 = _gateCheckDataIntegrity();
        $gates[] = $gate7;
        if ($gate7['status'] === 'failed') $allPassed = false;
    }
    
    // Gate-Report zusammenstellen
    $report = [
        'validated_at' => date('c'),
        'overall' => $allPassed ? 'passed' : 'failed',
        'gates' => $gates,
    ];
    
    $newStatus = $allPassed ? 'validated' : 'blocked';
    
    Database::execute(
        "UPDATE releases SET status = ?, gate_report = ?, validated_at = NOW() WHERE id = ?",
        [$newStatus, json_encode($report), $id]
    );
    
    ActivityLogger::log([
        'user_id' => $adminPayload['user_id'],
        'username' => $adminPayload['username'] ?? '',
        'action_category' => 'admin',
        'action' => 'release_validated',
        'description' => "Release {$release['version']} validiert: {$newStatus}",
        'details' => ['release_id' => $id, 'result' => $newStatus, 'gates' => count($gates)],
        'status' => 'success'
    ]);
    
    $updated = Database::queryOne("SELECT * FROM releases WHERE id = ?", [$id]);
    json_success([
        'release' => $updated,
        'gate_report' => $report,
    ], "Validierung abgeschlossen: {$newStatus}");
}


// ================================================================
// Gate-Check Funktionen
// ================================================================

function _gateCheckSchemaVersion(array $release): array {
    $requiredSchema = $release['required_schema'] ?? null;
    
    if (!$requiredSchema) {
        return [
            'name' => 'schema_version',
            'status' => 'skipped',
            'details' => 'Kein required_schema angegeben',
        ];
    }
    
    try {
        $tables = Database::query("SHOW TABLES LIKE 'schema_migrations'");
        if (empty($tables)) {
            return [
                'name' => 'schema_version',
                'status' => 'failed',
                'details' => 'Tabelle schema_migrations existiert nicht',
            ];
        }
        
        $applied = Database::queryOne(
            "SELECT COUNT(*) as cnt FROM schema_migrations WHERE migration_name = ?",
            [$requiredSchema]
        );
        
        if ((int)$applied['cnt'] === 0) {
            return [
                'name' => 'schema_version',
                'status' => 'failed',
                'details' => "Migration '{$requiredSchema}' nicht angewendet",
            ];
        }
        
        $total = Database::queryOne("SELECT COUNT(*) as cnt FROM schema_migrations");
        return [
            'name' => 'schema_version',
            'status' => 'passed',
            'details' => "{$total['cnt']} Migrationen angewendet (inkl. {$requiredSchema})",
        ];
    } catch (Exception $e) {
        return [
            'name' => 'schema_version',
            'status' => 'failed',
            'details' => 'Fehler: ' . $e->getMessage(),
        ];
    }
}


function _gateCheckSplitInvariant(): array {
    try {
        $tables = Database::query("SHOW TABLES LIKE 'pm_commissions'");
        if (empty($tables)) {
            return [
                'name' => 'split_invariant',
                'status' => 'skipped',
                'details' => 'Tabelle pm_commissions existiert nicht',
            ];
        }
        
        $violations = Database::queryOne(
            "SELECT COUNT(*) as cnt FROM pm_commissions 
             WHERE match_status IN ('auto_matched', 'manual_matched')
             AND ABS(
               (COALESCE(berater_anteil,0) + COALESCE(tl_anteil,0) + COALESCE(ag_anteil,0)) 
               - betrag
             ) > 0.01"
        );
        
        $count = (int)$violations['cnt'];
        if ($count > 0) {
            $examples = Database::query(
                "SELECT id, vsnr, betrag, berater_anteil, tl_anteil, ag_anteil FROM pm_commissions 
                 WHERE match_status IN ('auto_matched', 'manual_matched')
                 AND ABS(
                   (COALESCE(berater_anteil,0) + COALESCE(tl_anteil,0) + COALESCE(ag_anteil,0)) 
                   - betrag
                 ) > 0.01
                 LIMIT 5"
            );
            return [
                'name' => 'split_invariant',
                'status' => 'failed',
                'details' => "{$count} Provision(en) mit Split-Verletzung (berater+tl+ag != betrag)",
                'examples' => $examples,
            ];
        }
        
        return [
            'name' => 'split_invariant',
            'status' => 'passed',
            'details' => 'Keine Split-Verletzungen gefunden',
        ];
    } catch (Exception $e) {
        return [
            'name' => 'split_invariant',
            'status' => 'failed',
            'details' => 'Fehler: ' . $e->getMessage(),
        ];
    }
}


function _gateCheckMatchingConsistency(): array {
    try {
        $tables = Database::query("SHOW TABLES LIKE 'pm_commissions'");
        if (empty($tables)) {
            return [
                'name' => 'matching_consistency',
                'status' => 'skipped',
                'details' => 'Tabelle pm_commissions existiert nicht',
            ];
        }
        
        $orphanMatches = Database::queryOne(
            "SELECT COUNT(*) as cnt FROM pm_commissions 
             WHERE match_status = 'auto_matched' AND contract_id IS NULL"
        );
        
        $missingBerater = Database::queryOne(
            "SELECT COUNT(*) as cnt FROM pm_commissions 
             WHERE berater_id IS NULL 
             AND match_status NOT IN ('unmatched', 'ignored')"
        );
        
        $orphanCount = (int)$orphanMatches['cnt'];
        $missingCount = (int)$missingBerater['cnt'];
        
        if ($orphanCount > 0 || $missingCount > 0) {
            $details = [];
            if ($orphanCount > 0) $details[] = "{$orphanCount} auto_matched ohne contract_id";
            if ($missingCount > 0) $details[] = "{$missingCount} gematchte ohne berater_id";
            return [
                'name' => 'matching_consistency',
                'status' => 'failed',
                'details' => implode('; ', $details),
            ];
        }
        
        return [
            'name' => 'matching_consistency',
            'status' => 'passed',
            'details' => 'Alle Matchings konsistent',
        ];
    } catch (Exception $e) {
        return [
            'name' => 'matching_consistency',
            'status' => 'failed',
            'details' => 'Fehler: ' . $e->getMessage(),
        ];
    }
}


function _gateCheckSmokeTestReport(array $release): array {
    $reportJson = $release['smoke_test_report'] ?? null;
    
    if (!$reportJson) {
        $isStable = $release['channel'] === 'stable';
        return [
            'name' => 'smoke_tests',
            'status' => $isStable ? 'failed' : 'skipped',
            'details' => $isStable ? 'Kein Smoke-Test-Report (Pflicht fuer stable)' : 'Kein Report hochgeladen (optional)',
        ];
    }
    
    $report = is_string($reportJson) ? json_decode($reportJson, true) : $reportJson;
    if (!$report) {
        return [
            'name' => 'smoke_tests',
            'status' => 'failed',
            'details' => 'Smoke-Test-Report ist kein gueltiges JSON',
        ];
    }
    
    $failures = [];
    
    if (($report['tests_failed'] ?? 0) > 0) {
        $failures[] = "{$report['tests_failed']} Test(s) fehlgeschlagen";
    }
    
    if (isset($report['app_version']) && $report['app_version'] !== $release['version']) {
        $failures[] = "Version mismatch: Report={$report['app_version']}, Release={$release['version']}";
    }
    
    if (isset($report['timestamp'])) {
        $reportTime = strtotime($report['timestamp']);
        if ($reportTime && (time() - $reportTime) > 86400) {
            $failures[] = "Report aelter als 24 Stunden";
        }
    }
    
    if (!empty($failures)) {
        return [
            'name' => 'smoke_tests',
            'status' => 'failed',
            'details' => implode('; ', $failures),
        ];
    }
    
    return [
        'name' => 'smoke_tests',
        'status' => 'passed',
        'details' => "{$report['tests_passed']}/{$report['tests_run']} Tests bestanden",
    ];
}


function _gateCheckVersionConsistency(array $release): array {
    $version = $release['version'];
    $channel = $release['channel'];
    
    $hasSuffix = preg_match('/-/', $version);
    
    if ($channel === 'stable' && $hasSuffix) {
        return [
            'name' => 'version_consistency',
            'status' => 'failed',
            'details' => "Stable-Release darf kein Pre-Release-Suffix haben: {$version}",
        ];
    }
    
    if ($channel === 'dev' && !$hasSuffix) {
        return [
            'name' => 'version_consistency',
            'status' => 'failed',
            'details' => "Dev-Release muss Pre-Release-Suffix haben (z.B. {$version}-dev1)",
        ];
    }
    
    return [
        'name' => 'version_consistency',
        'status' => 'passed',
        'details' => "{$version} gueltig fuer Channel {$channel}",
    ];
}


/**
 * Gate 6: Schema-Struktur-Pruefung
 *
 * Verifiziert, dass release-kritische Tabellen, Indexes und Spalten existieren.
 * Schema-Hash wird als Audit-Trail gespeichert, blockiert aber NICHT
 * (verhindert false positives bei neuen Migrationen).
 */
function _gateCheckSchemaStructure(): array {
    $requiredTables = [
        'pm_commissions',
        'pm_contracts',
        'pm_vermittler_mapping',
        'pm_employees',
        'pm_berater_abrechnungen',
        'xempus_consultations',
    ];

    $requiredIndexes = [
        'pm_commissions' => [
            'idx_comm_vsnr_norm',
            'idx_comm_vermittler_norm',
            'idx_comm_row_hash',
            'idx_comm_vn_norm',
            'idx_comm_match_status',
            'idx_comm_berater_id',
            'idx_comm_contract_id',
        ],
        'pm_contracts' => [
            'idx_contr_vsnr_norm',
            'idx_contr_vn_norm',
            'idx_contr_xempus_id',
        ],
        'pm_berater_abrechnungen' => [
            'uq_abr_monat_berater_rev',
        ],
        'pm_vermittler_mapping' => [
            'idx_mapping_norm_unique',
        ],
    ];

    $requiredColumns = [
        'pm_commissions' => [
            'betrag', 'berater_anteil', 'tl_anteil', 'ag_anteil',
            'match_status', 'contract_id', 'berater_id',
            'row_hash', 'vsnr_normalized', 'vermittler_name_normalized',
        ],
    ];

    try {
        $missingTables = [];
        $missingIndexes = [];
        $missingColumns = [];
        $createStatements = [];

        foreach ($requiredTables as $table) {
            $exists = Database::query("SHOW TABLES LIKE ?", [$table]);
            if (empty($exists)) {
                $missingTables[] = $table;
            } else {
                $create = Database::queryOne("SHOW CREATE TABLE `{$table}`");
                $createStatements[] = $create['Create Table'] ?? '';
            }
        }

        if (!empty($missingTables)) {
            return [
                'name' => 'schema_structure',
                'status' => 'failed',
                'details' => "Fehlende Tabellen: " . implode(', ', $missingTables),
                'missing_tables' => $missingTables,
            ];
        }

        foreach ($requiredIndexes as $table => $indexes) {
            $existingIndexes = Database::query("SHOW INDEX FROM `{$table}`");
            $indexNames = array_unique(array_column($existingIndexes, 'Key_name'));
            foreach ($indexes as $idx) {
                if (!in_array($idx, $indexNames)) {
                    $missingIndexes[] = "{$table}.{$idx}";
                }
            }
        }

        if (!empty($missingIndexes)) {
            return [
                'name' => 'schema_structure',
                'status' => 'failed',
                'details' => "Fehlende Indexes: " . implode(', ', $missingIndexes),
                'missing_indexes' => $missingIndexes,
            ];
        }

        foreach ($requiredColumns as $table => $columns) {
            $existingCols = Database::query("SHOW COLUMNS FROM `{$table}`");
            $colNames = array_column($existingCols, 'Field');
            foreach ($columns as $col) {
                if (!in_array($col, $colNames)) {
                    $missingColumns[] = "{$table}.{$col}";
                }
            }
        }

        if (!empty($missingColumns)) {
            return [
                'name' => 'schema_structure',
                'status' => 'failed',
                'details' => "Fehlende Spalten: " . implode(', ', $missingColumns),
                'missing_columns' => $missingColumns,
            ];
        }

        $schemaHash = hash('sha256', implode("\n", $createStatements));

        return [
            'name' => 'schema_structure',
            'status' => 'passed',
            'details' => count($requiredTables) . " Tabellen, "
                . array_sum(array_map('count', $requiredIndexes)) . " Indexes, "
                . array_sum(array_map('count', $requiredColumns)) . " Spalten verifiziert",
            'schema_hash' => $schemaHash,
        ];
    } catch (Exception $e) {
        return [
            'name' => 'schema_structure',
            'status' => 'failed',
            'details' => 'Fehler: ' . $e->getMessage(),
        ];
    }
}


/**
 * Gate 7: Daten-Integritaets-Pruefung
 *
 * FATAL (Blocker): Orphaned FKs, fehlende Berater-Referenzen
 * WARNING (kein Blocker): Doppelte row_hash, negative Betraege
 */
function _gateCheckDataIntegrity(): array {
    try {
        $tables = Database::query("SHOW TABLES LIKE 'pm_commissions'");
        if (empty($tables)) {
            return [
                'name' => 'data_integrity',
                'status' => 'skipped',
                'details' => 'Tabelle pm_commissions existiert nicht',
            ];
        }

        $fatals = [];
        $warnings = [];

        // FATAL: Orphaned contract_id
        $contractsExist = Database::query("SHOW TABLES LIKE 'pm_contracts'");
        if (!empty($contractsExist)) {
            $orphanedContracts = Database::queryOne(
                "SELECT COUNT(*) as cnt FROM pm_commissions
                 WHERE contract_id IS NOT NULL
                 AND contract_id NOT IN (SELECT id FROM pm_contracts)"
            );
            $cnt = (int)$orphanedContracts['cnt'];
            if ($cnt > 0) {
                $fatals[] = "{$cnt} Provisionen mit orphaned contract_id (Vertrag existiert nicht)";
            }
        }

        // FATAL: Orphaned berater_id
        $employeesExist = Database::query("SHOW TABLES LIKE 'pm_employees'");
        if (!empty($employeesExist)) {
            $orphanedBerater = Database::queryOne(
                "SELECT COUNT(*) as cnt FROM pm_commissions
                 WHERE berater_id IS NOT NULL
                 AND berater_id NOT IN (SELECT id FROM pm_employees)"
            );
            $cnt = (int)$orphanedBerater['cnt'];
            if ($cnt > 0) {
                $fatals[] = "{$cnt} Provisionen mit orphaned berater_id (Berater existiert nicht)";
            }
        }

        // WARNING: Doppelte row_hash
        $dupHashes = Database::queryOne(
            "SELECT COUNT(*) as cnt FROM (
                SELECT row_hash FROM pm_commissions
                WHERE row_hash IS NOT NULL AND row_hash != ''
                GROUP BY row_hash HAVING COUNT(*) > 1
            ) t"
        );
        $dupCnt = (int)$dupHashes['cnt'];
        if ($dupCnt > 0) {
            $warnings[] = "{$dupCnt} doppelte row_hash Werte (evtl. Re-Import)";
        }

        // WARNING: Negative Betraege
        $negatives = Database::queryOne(
            "SELECT COUNT(*) as cnt FROM pm_commissions WHERE betrag < 0"
        );
        $negCnt = (int)$negatives['cnt'];
        if ($negCnt > 0) {
            $warnings[] = "{$negCnt} Provisionen mit negativem Betrag (evtl. Storno)";
        }

        if (!empty($fatals)) {
            return [
                'name' => 'data_integrity',
                'status' => 'failed',
                'details' => implode('; ', $fatals),
                'fatal' => $fatals,
                'warnings' => $warnings,
            ];
        }

        $detail = 'Keine Integritaetsverletzungen';
        if (!empty($warnings)) {
            $detail .= ' (Warnungen: ' . implode('; ', $warnings) . ')';
        }

        return [
            'name' => 'data_integrity',
            'status' => 'passed',
            'details' => $detail,
            'warnings' => $warnings,
        ];
    } catch (Exception $e) {
        return [
            'name' => 'data_integrity',
            'status' => 'failed',
            'details' => 'Fehler: ' . $e->getMessage(),
        ];
    }
}


/**
 * Release zurueckziehen mit Auto-Fallback.
 *
 * POST /admin/releases/{id}/withdraw
 *
 * Setzt das Release auf 'withdrawn' und reaktiviert automatisch
 * das vorherige Release im gleichen Channel (wenn vorhanden).
 */
function handleWithdrawRelease(int $id, array $adminPayload): void {
    $release = Database::queryOne("SELECT * FROM releases WHERE id = ?", [$id]);

    if (!$release) {
        json_error('Release nicht gefunden', 404);
    }

    if (!in_array($release['status'], ['active', 'mandatory'])) {
        json_error(
            "Withdraw nur fuer Releases mit Status 'active' oder 'mandatory' moeglich (aktuell: '{$release['status']}')",
            400
        );
    }

    $channel = $release['channel'];

    Database::execute(
        "UPDATE releases SET status = 'withdrawn' WHERE id = ?",
        [$id]
    );

    $fallbackRelease = null;
    $previous = Database::queryOne(
        "SELECT * FROM releases
         WHERE channel = ? AND id != ? AND status IN ('deprecated', 'validated')
         ORDER BY id DESC LIMIT 1",
        [$channel, $id]
    );

    if ($previous) {
        Database::execute(
            "UPDATE releases SET status = 'active' WHERE id = ?",
            [(int)$previous['id']]
        );
        $fallbackRelease = Database::queryOne("SELECT * FROM releases WHERE id = ?", [(int)$previous['id']]);
    }

    ActivityLogger::log([
        'user_id' => $adminPayload['user_id'],
        'username' => $adminPayload['username'] ?? '',
        'action_category' => 'admin',
        'action' => 'release_withdrawn',
        'description' => "Release {$release['version']} ({$channel}) zurueckgezogen"
            . ($fallbackRelease ? ", Fallback auf {$fallbackRelease['version']}" : ", kein Fallback verfuegbar"),
        'details' => [
            'release_id' => $id,
            'version' => $release['version'],
            'channel' => $channel,
            'fallback_id' => $fallbackRelease ? (int)$fallbackRelease['id'] : null,
            'fallback_version' => $fallbackRelease ? $fallbackRelease['version'] : null,
        ],
        'status' => 'success',
    ]);

    $withdrawn = Database::queryOne("SELECT * FROM releases WHERE id = ?", [$id]);

    json_success([
        'withdrawn_release' => $withdrawn,
        'fallback_release' => $fallbackRelease,
        'message' => $fallbackRelease
            ? "Release {$release['version']} zurueckgezogen. Fallback: {$fallbackRelease['version']} ist jetzt aktiv."
            : "Release {$release['version']} zurueckgezogen. Kein Fallback-Release im Channel '{$channel}' verfuegbar.",
    ], "Release zurueckgezogen");
}


/**
 * Schema-Snapshot: Aktueller DB-Zustand als Hash + Inventar.
 *
 * GET /api/admin/schema-snapshot
 *
 * Gibt SHA256 ueber alle CREATE TABLE Statements zurueck,
 * plus Index-Inventar fuer kritische Tabellen.
 */
function handleSchemaSnapshot(array $adminPayload): void {
    try {
        $tablesResult = Database::query("SHOW TABLES");
        $tables = [];
        $createStatements = [];

        foreach ($tablesResult as $row) {
            $tableName = array_values($row)[0];
            $tables[] = $tableName;
            $create = Database::queryOne("SHOW CREATE TABLE `{$tableName}`");
            $createStatements[] = $create['Create Table'] ?? '';
        }

        $schemaHash = hash('sha256', implode("\n", $createStatements));

        $criticalTables = [
            'pm_commissions', 'pm_contracts', 'pm_vermittler_mapping',
            'pm_employees', 'pm_berater_abrechnungen', 'xempus_consultations',
        ];

        $indexesPerTable = [];
        foreach ($criticalTables as $table) {
            if (in_array($table, $tables)) {
                $indexes = Database::query("SHOW INDEX FROM `{$table}`");
                $indexNames = array_unique(array_column($indexes, 'Key_name'));
                $indexesPerTable[$table] = array_values($indexNames);
            }
        }

        json_success([
            'schema_hash' => $schemaHash,
            'tables_count' => count($tables),
            'tables' => $tables,
            'indexes_per_table' => $indexesPerTable,
            'generated_at' => date('c'),
        ], 'Schema-Snapshot generiert');
    } catch (Exception $e) {
        json_error('Schema-Snapshot fehlgeschlagen: ' . $e->getMessage(), 500);
    }
}

<?php
/**
 * BiPro API - BiPRO Events
 *
 * Strukturierte Metadaten aus 0-Dokument-Lieferungen
 * (Vertragsdaten-XML, Statusmeldungen, GDV-Ankuendigungen).
 *
 * Endpunkte:
 * - GET    /bipro-events              Paginierte Liste (Filter: event_type, vu_name, is_read)
 * - GET    /bipro-events/summary      Leichtgewichtig fuer Polling (unread_count)
 * - POST   /bipro-events              Neuen Event erstellen
 * - PUT    /bipro-events/read         Bulk-Read-Markierung (IDs)
 * - PUT    /bipro-events/read-all     Alle als gelesen markieren
 * - DELETE /bipro-events/{id}         Einzelnen Event loeschen (Admin)
 * - DELETE /bipro-events/all          Alle Events loeschen (Admin)
 */

require_once __DIR__ . '/lib/db.php';
require_once __DIR__ . '/lib/response.php';
require_once __DIR__ . '/lib/jwt.php';

function handleBiproEventsRequest(string $action, string $method): void {
    $payload = JWT::requireAuth();

    if ($method === 'GET' && (empty($action) || $action === 'list')) {
        listBiproEvents($payload);
        return;
    }

    if ($method === 'GET' && $action === 'summary') {
        getBiproEventsSummary($payload);
        return;
    }

    if ($method === 'POST' && empty($action)) {
        createBiproEvent($payload);
        return;
    }

    if ($method === 'PUT' && $action === 'read') {
        markBiproEventsRead($payload);
        return;
    }

    if ($method === 'PUT' && $action === 'read-all') {
        markAllBiproEventsRead($payload);
        return;
    }

    if ($method === 'DELETE' && $action === 'all') {
        require_once __DIR__ . '/lib/permissions.php';
        requireAdmin();
        deleteAllBiproEvents($payload);
        return;
    }

    if ($method === 'DELETE' && is_numeric($action)) {
        require_once __DIR__ . '/lib/permissions.php';
        requireAdmin();
        deleteBiproEvent($payload, (int)$action);
        return;
    }

    json_error('Methode nicht erlaubt', 405);
}

/**
 * GET /bipro-events
 */
function listBiproEvents(array $user): void {
    $pdo = db();
    $conditions = ['1=1'];
    $params = [];

    if (!empty($_GET['event_type'])) {
        $conditions[] = 'event_type = ?';
        $params[] = $_GET['event_type'];
    }

    if (!empty($_GET['vu_name'])) {
        $conditions[] = 'vu_name LIKE ?';
        $params[] = '%' . $_GET['vu_name'] . '%';
    }

    if (isset($_GET['is_read'])) {
        $conditions[] = 'is_read = ?';
        $params[] = (int)$_GET['is_read'];
    }

    $page = max(1, (int)($_GET['page'] ?? 1));
    $perPage = min(500, max(1, (int)($_GET['per_page'] ?? 50)));
    $offset = ($page - 1) * $perPage;

    $where = implode(' AND ', $conditions);

    $countStmt = $pdo->prepare("SELECT COUNT(*) FROM bipro_events WHERE $where");
    $countStmt->execute($params);
    $total = (int)$countStmt->fetchColumn();

    $stmt = $pdo->prepare("
        SELECT * FROM bipro_events
        WHERE $where
        ORDER BY created_at DESC
        LIMIT $perPage OFFSET $offset
    ");
    $stmt->execute($params);
    $events = $stmt->fetchAll(PDO::FETCH_ASSOC);

    json_response([
        'data' => $events,
        'pagination' => [
            'page' => $page,
            'per_page' => $perPage,
            'total' => $total,
            'total_pages' => (int)ceil($total / $perPage),
        ],
    ]);
}

/**
 * GET /bipro-events/summary
 */
function getBiproEventsSummary(array $user): void {
    $pdo = db();

    $stmt = $pdo->query("SELECT COUNT(*) FROM bipro_events WHERE is_read = 0");
    $unreadCount = (int)$stmt->fetchColumn();

    $stmt = $pdo->query("
        SELECT * FROM bipro_events
        ORDER BY created_at DESC LIMIT 1
    ");
    $latest = $stmt->fetch(PDO::FETCH_ASSOC) ?: null;

    json_response([
        'unread_count' => $unreadCount,
        'latest_event' => $latest,
    ]);
}

/**
 * POST /bipro-events
 */
function createBiproEvent(array $user): void {
    $data = get_json_body();

    if (empty($data['shipment_id'])) {
        json_error('shipment_id erforderlich', 400);
        return;
    }
    if (empty($data['event_type'])) {
        json_error('event_type erforderlich', 400);
        return;
    }

    $allowed = ['gdv_announced', 'contract_xml', 'status_message', 'document_xml'];
    if (!in_array($data['event_type'], $allowed)) {
        json_error('Ungueltiger event_type', 400);
        return;
    }

    $pdo = db();

    $stmt = $pdo->prepare("
        INSERT INTO bipro_events
            (shipment_id, vu_name, vu_bafin_nr, bipro_category, category_name,
             event_type, vsnr, vn_name, vn_address, sparte, vermittler_nr,
             freitext, kurzbeschreibung, referenced_filename, shipment_date,
             raw_document_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON DUPLICATE KEY UPDATE
            vu_name = VALUES(vu_name),
            vu_bafin_nr = VALUES(vu_bafin_nr),
            bipro_category = VALUES(bipro_category),
            category_name = VALUES(category_name),
            event_type = VALUES(event_type),
            vsnr = VALUES(vsnr),
            vn_name = VALUES(vn_name),
            vn_address = VALUES(vn_address),
            sparte = VALUES(sparte),
            vermittler_nr = VALUES(vermittler_nr),
            freitext = VALUES(freitext),
            kurzbeschreibung = VALUES(kurzbeschreibung),
            referenced_filename = VALUES(referenced_filename),
            shipment_date = VALUES(shipment_date),
            raw_document_id = VALUES(raw_document_id)
    ");

    $stmt->execute([
        $data['shipment_id'],
        $data['vu_name'] ?? null,
        $data['vu_bafin_nr'] ?? null,
        $data['bipro_category'] ?? null,
        $data['category_name'] ?? null,
        $data['event_type'],
        $data['vsnr'] ?? null,
        $data['vn_name'] ?? null,
        $data['vn_address'] ?? null,
        $data['sparte'] ?? null,
        $data['vermittler_nr'] ?? null,
        $data['freitext'] ?? null,
        $data['kurzbeschreibung'] ?? null,
        $data['referenced_filename'] ?? null,
        $data['shipment_date'] ?? null,
        $data['raw_document_id'] ?? null,
    ]);

    $eventId = $pdo->lastInsertId();
    if (!$eventId) {
        $stmt2 = $pdo->prepare("SELECT id FROM bipro_events WHERE shipment_id = ?");
        $stmt2->execute([$data['shipment_id']]);
        $eventId = $stmt2->fetchColumn();
    }

    json_response(['success' => true, 'id' => (int)$eventId], 201);
}

/**
 * PUT /bipro-events/read
 */
function markBiproEventsRead(array $user): void {
    $data = get_json_body();
    $ids = $data['ids'] ?? [];

    if (empty($ids) || !is_array($ids)) {
        json_error('ids Array erforderlich', 400);
        return;
    }

    $pdo = db();
    $placeholders = implode(',', array_fill(0, count($ids), '?'));
    $stmt = $pdo->prepare("UPDATE bipro_events SET is_read = 1 WHERE id IN ($placeholders)");
    $stmt->execute(array_map('intval', $ids));

    json_response(['success' => true, 'updated' => $stmt->rowCount()]);
}

/**
 * PUT /bipro-events/read-all
 */
function markAllBiproEventsRead(array $user): void {
    $pdo = db();
    $stmt = $pdo->prepare("UPDATE bipro_events SET is_read = 1 WHERE is_read = 0");
    $stmt->execute();

    json_response(['success' => true, 'updated' => $stmt->rowCount()]);
}

/**
 * DELETE /bipro-events/{id}  (Admin only)
 */
function deleteBiproEvent(array $user, int $eventId): void {
    $pdo = db();

    $stmt = $pdo->prepare("SELECT id FROM bipro_events WHERE id = ?");
    $stmt->execute([$eventId]);
    if (!$stmt->fetch()) {
        json_error('Event nicht gefunden', 404);
        return;
    }

    $stmt = $pdo->prepare("DELETE FROM bipro_events WHERE id = ?");
    $stmt->execute([$eventId]);

    json_response(['success' => true, 'deleted' => 1]);
}

/**
 * DELETE /bipro-events/all  (Admin only)
 */
function deleteAllBiproEvents(array $user): void {
    $pdo = db();
    $stmt = $pdo->query("DELETE FROM bipro_events");
    $deleted = $stmt->rowCount();

    json_response(['success' => true, 'deleted' => $deleted]);
}

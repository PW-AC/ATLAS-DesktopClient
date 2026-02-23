<?php
/**
 * BiPro API - Xempus Insight Engine
 *
 * Eigenstaendiges Datenmodul fuer Xempus-Importe, Arbeitgeber-/Arbeitnehmer-Verwaltung,
 * Beratungen, Snapshot-Versionierung und Statistiken.
 *
 * 4-Phasen-Import:
 *   Phase 1: RAW Ingest (jede Zeile in xempus_raw_rows)
 *   Phase 2: Normalize + Parse (raw_rows → Entity-Tabellen)
 *   Phase 3: Snapshot Update (Diff mit vorherigem Snapshot)
 *   Phase 4: Finalize (Content-Hash, import_phase=complete)
 *
 * Wird aus provision.php eingebunden via handleXempusRoute().
 */

require_once __DIR__ . '/lib/db.php';
require_once __DIR__ . '/lib/response.php';
require_once __DIR__ . '/lib/activity_logger.php';

// ═══════════════════════════════════════════════════════
// DISPATCHER
// ═══════════════════════════════════════════════════════

function handleXempusRoute(string $method, ?string $subAction, ?string $entityId, array $payload): void {
    switch ($subAction) {
        case 'import':
            handleXempusImportRoute($method, $entityId, $payload);
            break;
        case 'parse':
            handleXempusParseRoute($method, $entityId, $payload);
            break;
        case 'finalize':
            handleXempusFinalizeRoute($method, $entityId, $payload);
            break;
        case 'batches':
            handleXempusBatchesRoute($method, $payload);
            break;
        case 'employers':
            handleXempusEmployersRoute($method, $entityId, $payload);
            break;
        case 'employees':
            handleXempusEmployeesRoute($method, $entityId, $payload);
            break;
        case 'consultations':
            handleXempusConsultationsRoute($method, $entityId, $payload);
            break;
        case 'stats':
            handleXempusStatsRoute($method, $payload);
            break;
        case 'diff':
            handleXempusDiffRoute($method, $entityId, $payload);
            break;
        case 'status-mapping':
            handleXempusStatusMappingRoute($method, $payload);
            break;
        case 'sync':
            handleXempusSyncRoute($method, $entityId, $payload);
            break;
        default:
            json_error('Unbekannte Xempus-Route: ' . ($subAction ?? 'null'), 404);
    }
}

// ═══════════════════════════════════════════════════════
// PHASE 1: RAW INGEST
// ═══════════════════════════════════════════════════════

function handleXempusImportRoute(string $method, ?string $entityId, array $payload): void {
    if ($method !== 'POST') {
        json_error('Methode nicht erlaubt', 405);
    }

    $body = get_json_body();
    $filename = $body['filename'] ?? null;
    $sheets = $body['sheets'] ?? [];
    $existingBatchId = isset($body['batch_id']) ? (int) $body['batch_id'] : null;

    if (!$filename || empty($sheets)) {
        json_error('filename und sheets[] erforderlich', 400);
    }

    Database::beginTransaction();

    try {
        if ($existingBatchId) {
            $batch = Database::queryOne(
                "SELECT id FROM xempus_import_batches WHERE id = ? AND import_phase = 'raw_ingest'",
                [$existingBatchId]
            );
            if (!$batch) {
                Database::rollback();
                json_error('Batch nicht gefunden oder nicht im raw_ingest-Status', 404);
            }
            $batchId = $existingBatchId;
        } else {
            $batchId = Database::insert(
                "INSERT INTO xempus_import_batches (filename, imported_by, import_phase) VALUES (?, ?, 'raw_ingest')",
                [$filename, $payload['user_id']]
            );
        }

        $totalRows = 0;
        $sheetCounts = [];
        $pdo = Database::getInstance();

        foreach ($sheets as $sheetData) {
            $sheetName = $sheetData['sheet_name'] ?? '';
            $rows = $sheetData['rows'] ?? [];
            if (!$sheetName || empty($rows)) continue;

            $maxRowNum = Database::queryOne(
                "SELECT COALESCE(MAX(`row_number`), 0) as mr FROM xempus_raw_rows WHERE import_batch_id = ? AND sheet_name = ?",
                [$batchId, $sheetName]
            );
            $rowNum = (int) ($maxRowNum['mr'] ?? 0);

            $insertStmt = $pdo->prepare("
                INSERT INTO xempus_raw_rows
                (import_batch_id, sheet_name, `row_number`, raw_json, row_hash, parse_status)
                VALUES (?, ?, ?, ?, ?, 'pending')
            ");

            foreach ($rows as $row) {
                $rowNum++;
                $rawJson = json_encode($row, JSON_UNESCAPED_UNICODE);
                $rowHash = hash('sha256', $rawJson);
                $insertStmt->execute([$batchId, $sheetName, $rowNum, $rawJson, $rowHash]);
                $totalRows++;
            }

            $sheetCounts[$sheetName] = $rowNum;
        }

        $existingCounts = [];
        if ($existingBatchId) {
            $batch = Database::queryOne("SELECT record_counts FROM xempus_import_batches WHERE id = ?", [$batchId]);
            $existingCounts = $batch['record_counts'] ? json_decode($batch['record_counts'], true) : [];
        }
        $mergedCounts = array_merge($existingCounts ?: [], $sheetCounts);

        Database::execute("UPDATE xempus_import_batches SET record_counts = ? WHERE id = ?",
            [json_encode($mergedCounts), $batchId]);

        Database::commit();

        logPmAction($payload, 'xempus_raw_ingest', 'xempus_import_batches', $batchId,
            "Xempus RAW-Ingest: {$totalRows} Zeilen (Chunk)",
            ['filename' => $filename, 'sheet_counts' => $sheetCounts, 'is_append' => !!$existingBatchId]
        );

        json_success([
            'batch_id' => $batchId,
            'total_rows' => $totalRows,
            'sheet_counts' => $mergedCounts,
        ], 'RAW-Ingest abgeschlossen');

    } catch (\Throwable $e) {
        Database::rollback();
        json_error('RAW-Ingest fehlgeschlagen: ' . $e->getMessage(), 500);
    }
}

// ═══════════════════════════════════════════════════════
// PHASE 2: NORMALIZE + PARSE
// ═══════════════════════════════════════════════════════

function handleXempusParseRoute(string $method, ?string $batchId, array $payload): void {
    if ($method !== 'POST') {
        json_error('Methode nicht erlaubt', 405);
    }
    if (!$batchId) {
        json_error('batch_id erforderlich', 400);
    }
    $batchId = (int) $batchId;

    $batch = Database::queryOne("SELECT * FROM xempus_import_batches WHERE id = ?", [$batchId]);
    if (!$batch) {
        json_error('Batch nicht gefunden', 404);
    }

    $body = get_json_body();
    $limit = isset($body['limit']) ? max(1, min((int) $body['limit'], 10000)) : 2000;

    $totalPending = Database::queryOne(
        "SELECT COUNT(*) as cnt FROM xempus_raw_rows WHERE import_batch_id = ? AND parse_status = 'pending'",
        [$batchId]
    );
    $pendingBefore = (int) ($totalPending['cnt'] ?? 0);

    $rawRows = Database::query(
        "SELECT id, sheet_name, raw_json FROM xempus_raw_rows WHERE import_batch_id = ? AND parse_status = 'pending' ORDER BY sheet_name, `row_number` LIMIT " . $limit,
        [$batchId]
    );

    $stats = ['ok' => 0, 'warning' => 0, 'error' => 0];
    $okIds = [];
    $warnIds = [];
    $errorUpdates = [];

    Database::beginTransaction();
    try {
        $stmts = [];

        foreach ($rawRows as $raw) {
            try {
                $data = json_decode($raw['raw_json'], true);
                if (!$data) {
                    throw new \Exception('raw_json konnte nicht dekodiert werden');
                }

                $rawJson = json_encode($data, JSON_UNESCAPED_UNICODE);
                $sheetName = $raw['sheet_name'];

                if (!isset($stmts[$sheetName])) {
                    $stmts[$sheetName] = null;
                }

                $entityId = null;
                switch ($sheetName) {
                    case 'ArbG':
                        $entityId = xempusUpsertEmployer($data, $batchId, $rawJson, $stmts[$sheetName]);
                        break;
                    case 'ArbG-Tarife':
                        $entityId = xempusUpsertTariff($data, $batchId, $rawJson, $stmts[$sheetName]);
                        break;
                    case 'ArbG-Zuschüsse':
                        $entityId = xempusUpsertSubsidy($data, $batchId, $rawJson, $stmts[$sheetName]);
                        break;
                    case 'ArbN':
                        $entityId = xempusUpsertEmployee($data, $batchId, $rawJson, $stmts[$sheetName]);
                        break;
                    case 'Beratungen':
                        $entityId = xempusUpsertConsultation($data, $batchId, $rawJson, $stmts[$sheetName]);
                        break;
                }

                if ($entityId) {
                    $okIds[] = ['id' => $raw['id'], 'entity_id' => $entityId];
                    $stats['ok']++;
                } else {
                    $warnIds[] = $raw['id'];
                    $stats['warning']++;
                }

            } catch (\Throwable $e) {
                $errorUpdates[] = ['id' => $raw['id'], 'msg' => mb_substr($e->getMessage(), 0, 500)];
                $stats['error']++;
            }
        }

        $pdo = Database::getInstance();

        if (!empty($okIds)) {
            $updateStmt = $pdo->prepare("UPDATE xempus_raw_rows SET parse_status = 'ok', parsed_entity_id = ? WHERE id = ?");
            foreach ($okIds as $ok) {
                $updateStmt->execute([$ok['entity_id'], $ok['id']]);
            }
        }

        if (!empty($warnIds)) {
            $placeholders = implode(',', array_fill(0, count($warnIds), '?'));
            $pdo->prepare("UPDATE xempus_raw_rows SET parse_status = 'warning' WHERE id IN ($placeholders)")
                ->execute($warnIds);
        }

        if (!empty($errorUpdates)) {
            $errStmt = $pdo->prepare("UPDATE xempus_raw_rows SET parse_status = 'error', parse_error = ? WHERE id = ?");
            foreach ($errorUpdates as $err) {
                $errStmt->execute([$err['msg'], $err['id']]);
            }
        }

        Database::commit();
    } catch (\Throwable $e) {
        Database::rollback();
        json_error('Parse fehlgeschlagen: ' . $e->getMessage(), 500);
        return;
    }

    $remaining = $pendingBefore - ($stats['ok'] + $stats['warning'] + $stats['error']);
    $done = $remaining <= 0;

    if ($done) {
        Database::execute(
            "UPDATE xempus_import_batches SET import_phase = 'normalize' WHERE id = ?",
            [$batchId]
        );

        logPmAction($payload, 'xempus_parse', 'xempus_import_batches', $batchId,
            "Xempus Parse abgeschlossen",
            $stats
        );
    }

    json_success([
        'batch_id' => $batchId,
        'parsed' => $stats,
        'remaining' => max(0, $remaining),
        'done' => $done,
    ], $done ? 'Parsing abgeschlossen' : 'Chunk geparst, weitere Zeilen ausstehend');
}


function xempusUpsertEmployer(array $d, int $batchId, string $rawJson, ?\PDOStatement &$stmt = null): ?string {
    $id = trim($d['id'] ?? '');
    if (!$id) return null;

    if (!$stmt) {
        $stmt = Database::getInstance()->prepare("
            INSERT INTO xempus_employers
            (id, name, street, plz, city, iban, bic, tarif_info, zuschuss_info,
             raw_json, first_seen_batch_id, last_seen_batch_id, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, TRUE)
            ON DUPLICATE KEY UPDATE
                name=VALUES(name), street=VALUES(street), plz=VALUES(plz), city=VALUES(city),
                iban=VALUES(iban), bic=VALUES(bic), tarif_info=VALUES(tarif_info),
                zuschuss_info=VALUES(zuschuss_info), raw_json=VALUES(raw_json),
                last_seen_batch_id=VALUES(last_seen_batch_id), is_active=TRUE, updated_at=NOW()
        ");
    }
    $stmt->execute([
        $id, $d['name'] ?? null, $d['street'] ?? null, $d['plz'] ?? null, $d['city'] ?? null,
        $d['iban'] ?? null, $d['bic'] ?? null, $d['tarif_info'] ?? null, $d['zuschuss_info'] ?? null,
        $rawJson, $batchId, $batchId
    ]);
    return $id;
}

function xempusUpsertTariff(array $d, int $batchId, string $rawJson, ?\PDOStatement &$stmt = null): ?string {
    $id = trim($d['id'] ?? '');
    if (!$id) return null;

    if (!$stmt) {
        $stmt = Database::getInstance()->prepare("
            INSERT INTO xempus_tariffs
            (id, employer_id, versicherer, typ, durchfuehrungsweg, tarif, beantragung,
             gruppenrahmenkollektiv, gruppennummer, raw_json, first_seen_batch_id, last_seen_batch_id, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, TRUE)
            ON DUPLICATE KEY UPDATE
                employer_id=VALUES(employer_id), versicherer=VALUES(versicherer), typ=VALUES(typ),
                durchfuehrungsweg=VALUES(durchfuehrungsweg), tarif=VALUES(tarif),
                beantragung=VALUES(beantragung), gruppenrahmenkollektiv=VALUES(gruppenrahmenkollektiv),
                gruppennummer=VALUES(gruppennummer), raw_json=VALUES(raw_json),
                last_seen_batch_id=VALUES(last_seen_batch_id), is_active=TRUE, updated_at=NOW()
        ");
    }
    $stmt->execute([
        $id, $d['employer_id'] ?? null, $d['versicherer'] ?? null, $d['typ'] ?? null,
        $d['durchfuehrungsweg'] ?? null, $d['tarif'] ?? null, $d['beantragung'] ?? null,
        $d['gruppenrahmenkollektiv'] ?? null, $d['gruppennummer'] ?? null,
        $rawJson, $batchId, $batchId
    ]);
    return $id;
}

function xempusUpsertSubsidy(array $d, int $batchId, string $rawJson, ?\PDOStatement &$stmt = null): ?string {
    $id = trim($d['id'] ?? '');
    if (!$id) return null;

    if (!$stmt) {
        $stmt = Database::getInstance()->prepare("
            INSERT INTO xempus_subsidies
            (id, employer_id, bezeichnung, art_vl_umwandlung, zuschuss_vl_alternativ,
             prozent_auf_vl, zuschuss_prozentual_leq_bbg, zuschuss_prozentual_gt_bbg,
             begrenzung_prozentual, fester_zuschuss, fester_arbg_beitrag,
             gestaffelter_zuschuss_aktiv, gestaffelter_zuschuss, begrenzung_gestaffelt,
             raw_json, first_seen_batch_id, last_seen_batch_id, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, TRUE)
            ON DUPLICATE KEY UPDATE
                employer_id=VALUES(employer_id), bezeichnung=VALUES(bezeichnung),
                art_vl_umwandlung=VALUES(art_vl_umwandlung),
                zuschuss_vl_alternativ=VALUES(zuschuss_vl_alternativ),
                prozent_auf_vl=VALUES(prozent_auf_vl),
                zuschuss_prozentual_leq_bbg=VALUES(zuschuss_prozentual_leq_bbg),
                zuschuss_prozentual_gt_bbg=VALUES(zuschuss_prozentual_gt_bbg),
                begrenzung_prozentual=VALUES(begrenzung_prozentual),
                fester_zuschuss=VALUES(fester_zuschuss),
                fester_arbg_beitrag=VALUES(fester_arbg_beitrag),
                gestaffelter_zuschuss_aktiv=VALUES(gestaffelter_zuschuss_aktiv),
                gestaffelter_zuschuss=VALUES(gestaffelter_zuschuss),
                begrenzung_gestaffelt=VALUES(begrenzung_gestaffelt),
                raw_json=VALUES(raw_json), last_seen_batch_id=VALUES(last_seen_batch_id),
                is_active=TRUE, updated_at=NOW()
        ");
    }
    $stmt->execute([
        $id, $d['employer_id'] ?? null, $d['bezeichnung'] ?? null,
        $d['art_vl_umwandlung'] ?? null, $d['zuschuss_vl_alternativ'] ?? null,
        $d['prozent_auf_vl'] ?? null, $d['zuschuss_prozentual_leq_bbg'] ?? null,
        $d['zuschuss_prozentual_gt_bbg'] ?? null, $d['begrenzung_prozentual'] ?? null,
        $d['fester_zuschuss'] ?? null, $d['fester_arbg_beitrag'] ?? null,
        $d['gestaffelter_zuschuss_aktiv'] ?? null, $d['gestaffelter_zuschuss'] ?? null,
        $d['begrenzung_gestaffelt'] ?? null, $rawJson, $batchId, $batchId
    ]);
    return $id;
}

function xempusUpsertEmployee(array $d, int $batchId, string $rawJson, ?\PDOStatement &$stmt = null): ?string {
    $id = trim($d['id'] ?? '');
    if (!$id) return null;

    if (!$stmt) {
        $stmt = Database::getInstance()->prepare("
            INSERT INTO xempus_employees
            (id, employer_id, zuschuss_id, anrede, titel, name, vorname,
             beratungsstatus, street, plz, city, bundesland, land,
             telefon, mobiltelefon, email, krankenversicherung,
             steuerklasse, berufsstellung, berufsbezeichnung, personalnummer,
             staatsangehoerigkeit, familienstand, bemerkung, zuschuss_name,
             geburtsdatum, diensteintritt, bruttolohn, kinder_vorhanden,
             kinderfreibetrag, freibetrag_jaehrlich, kirchensteuerpflicht,
             raw_json, first_seen_batch_id, last_seen_batch_id, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, TRUE)
            ON DUPLICATE KEY UPDATE
                employer_id=VALUES(employer_id), zuschuss_id=VALUES(zuschuss_id),
                anrede=VALUES(anrede), titel=VALUES(titel), name=VALUES(name), vorname=VALUES(vorname),
                beratungsstatus=VALUES(beratungsstatus), street=VALUES(street), plz=VALUES(plz),
                city=VALUES(city), bundesland=VALUES(bundesland), land=VALUES(land),
                telefon=VALUES(telefon), mobiltelefon=VALUES(mobiltelefon), email=VALUES(email),
                krankenversicherung=VALUES(krankenversicherung), steuerklasse=VALUES(steuerklasse),
                berufsstellung=VALUES(berufsstellung), berufsbezeichnung=VALUES(berufsbezeichnung),
                personalnummer=VALUES(personalnummer), staatsangehoerigkeit=VALUES(staatsangehoerigkeit),
                familienstand=VALUES(familienstand), bemerkung=VALUES(bemerkung),
                zuschuss_name=VALUES(zuschuss_name), geburtsdatum=VALUES(geburtsdatum),
                diensteintritt=VALUES(diensteintritt), bruttolohn=VALUES(bruttolohn),
                kinder_vorhanden=VALUES(kinder_vorhanden), kinderfreibetrag=VALUES(kinderfreibetrag),
                freibetrag_jaehrlich=VALUES(freibetrag_jaehrlich),
                kirchensteuerpflicht=VALUES(kirchensteuerpflicht), raw_json=VALUES(raw_json),
                last_seen_batch_id=VALUES(last_seen_batch_id), is_active=TRUE, updated_at=NOW()
        ");
    }

    $stringFields = [
        'employer_id', 'zuschuss_id', 'anrede', 'titel', 'name', 'vorname',
        'beratungsstatus', 'street', 'plz', 'city', 'bundesland', 'land',
        'telefon', 'mobiltelefon', 'email', 'krankenversicherung',
        'steuerklasse', 'berufsstellung', 'berufsbezeichnung', 'personalnummer',
        'staatsangehoerigkeit', 'familienstand', 'bemerkung', 'zuschuss_name'
    ];

    $params = [$id];
    foreach ($stringFields as $f) {
        $params[] = $d[$f] ?? null;
    }
    $params[] = xempusParseDateField($d['geburtsdatum'] ?? null);
    $params[] = xempusParseDateField($d['diensteintritt'] ?? null);
    $params[] = isset($d['bruttolohn']) ? (float) $d['bruttolohn'] : null;
    $params[] = isset($d['kinder_vorhanden']) ? ($d['kinder_vorhanden'] ? 1 : 0) : null;
    $params[] = isset($d['kinderfreibetrag']) ? (float) $d['kinderfreibetrag'] : null;
    $params[] = isset($d['freibetrag_jaehrlich']) ? (float) $d['freibetrag_jaehrlich'] : null;
    $params[] = isset($d['kirchensteuerpflicht']) ? ($d['kirchensteuerpflicht'] ? 1 : 0) : null;
    $params[] = $rawJson;
    $params[] = $batchId;
    $params[] = $batchId;

    $stmt->execute($params);
    return $id;
}

function xempusUpsertConsultation(array $d, int $batchId, string $rawJson, ?\PDOStatement &$stmt = null): ?string {
    $id = trim($d['id'] ?? '');
    if (!$id) return null;

    if (!$stmt) {
        $stmt = Database::getInstance()->prepare("
            INSERT INTO xempus_consultations
            (id, employee_id, employer_id, arbg_name, arbn_name, arbn_vorname,
             status, entgeltumwandlung_aus, versicherungsscheinnummer, versicherer,
             typ, durchfuehrungsweg, tarif, beantragung, tarifoption, gruppennummer,
             berater, beratungstyp, zahlungsweise, agenturnummer,
             geburtsdatum, beratungsdatum, beginn, ende,
             datum_antragsdokument, datum_entscheidung, datum_elektronische_uebermittlung,
             arbn_anteil, davon_vl_arbn, arbg_anteil, davon_vl_arbg, gesamtbeitrag,
             buz_rente, garantierte_rente, garantierte_kapitalleistung,
             sbu_jahresbruttolohn, sbu_garantierte_bu_rente, sbu_gesamte_bu_rente,
             buz, dauer_jahre, rentenalter, extra_cols, raw_json,
             first_seen_batch_id, last_seen_batch_id, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, TRUE)
            ON DUPLICATE KEY UPDATE
                employee_id=VALUES(employee_id), employer_id=VALUES(employer_id),
                arbg_name=VALUES(arbg_name), arbn_name=VALUES(arbn_name), arbn_vorname=VALUES(arbn_vorname),
                status=VALUES(status), entgeltumwandlung_aus=VALUES(entgeltumwandlung_aus),
                versicherungsscheinnummer=VALUES(versicherungsscheinnummer), versicherer=VALUES(versicherer),
                typ=VALUES(typ), durchfuehrungsweg=VALUES(durchfuehrungsweg), tarif=VALUES(tarif),
                beantragung=VALUES(beantragung), tarifoption=VALUES(tarifoption),
                gruppennummer=VALUES(gruppennummer), berater=VALUES(berater),
                beratungstyp=VALUES(beratungstyp), zahlungsweise=VALUES(zahlungsweise),
                agenturnummer=VALUES(agenturnummer),
                geburtsdatum=VALUES(geburtsdatum), beratungsdatum=VALUES(beratungsdatum),
                beginn=VALUES(beginn), ende=VALUES(ende),
                datum_antragsdokument=VALUES(datum_antragsdokument),
                datum_entscheidung=VALUES(datum_entscheidung),
                datum_elektronische_uebermittlung=VALUES(datum_elektronische_uebermittlung),
                arbn_anteil=VALUES(arbn_anteil), davon_vl_arbn=VALUES(davon_vl_arbn),
                arbg_anteil=VALUES(arbg_anteil), davon_vl_arbg=VALUES(davon_vl_arbg),
                gesamtbeitrag=VALUES(gesamtbeitrag), buz_rente=VALUES(buz_rente),
                garantierte_rente=VALUES(garantierte_rente),
                garantierte_kapitalleistung=VALUES(garantierte_kapitalleistung),
                sbu_jahresbruttolohn=VALUES(sbu_jahresbruttolohn),
                sbu_garantierte_bu_rente=VALUES(sbu_garantierte_bu_rente),
                sbu_gesamte_bu_rente=VALUES(sbu_gesamte_bu_rente),
                buz=VALUES(buz), dauer_jahre=VALUES(dauer_jahre), rentenalter=VALUES(rentenalter),
                extra_cols=VALUES(extra_cols), raw_json=VALUES(raw_json),
                last_seen_batch_id=VALUES(last_seen_batch_id), is_active=TRUE, updated_at=NOW()
        ");
    }

    $stringFields = [
        'employee_id', 'employer_id', 'arbg_name', 'arbn_name', 'arbn_vorname',
        'status', 'entgeltumwandlung_aus', 'versicherungsscheinnummer', 'versicherer',
        'typ', 'durchfuehrungsweg', 'tarif', 'beantragung', 'tarifoption', 'gruppennummer',
        'berater', 'beratungstyp', 'zahlungsweise', 'agenturnummer'
    ];
    $dateFields = [
        'geburtsdatum', 'beratungsdatum', 'beginn', 'ende',
        'datum_antragsdokument', 'datum_entscheidung', 'datum_elektronische_uebermittlung'
    ];
    $decimalFields = [
        'arbn_anteil', 'davon_vl_arbn', 'arbg_anteil', 'davon_vl_arbg', 'gesamtbeitrag',
        'buz_rente', 'garantierte_rente', 'garantierte_kapitalleistung',
        'sbu_jahresbruttolohn', 'sbu_garantierte_bu_rente', 'sbu_gesamte_bu_rente'
    ];

    $params = [$id];
    foreach ($stringFields as $f) { $params[] = $d[$f] ?? null; }
    foreach ($dateFields as $f) { $params[] = xempusParseDateField($d[$f] ?? null); }
    foreach ($decimalFields as $f) { $params[] = isset($d[$f]) ? (float) $d[$f] : null; }
    $params[] = isset($d['buz']) ? ($d['buz'] ? 1 : 0) : null;
    $params[] = isset($d['dauer_jahre']) ? (int) $d['dauer_jahre'] : null;
    $params[] = isset($d['rentenalter']) ? (int) $d['rentenalter'] : null;
    $params[] = !empty($d['extra_cols']) ? json_encode($d['extra_cols'], JSON_UNESCAPED_UNICODE) : null;
    $params[] = $rawJson;
    $params[] = $batchId;
    $params[] = $batchId;

    $stmt->execute($params);
    return $id;
}

function xempusParseDateField($val): ?string {
    if ($val === null || $val === '') return null;
    if (preg_match('/^\d{4}-\d{2}-\d{2}/', $val)) return substr($val, 0, 10);
    if (preg_match('/^(\d{2})\.(\d{2})\.(\d{4})$/', $val, $m)) return "{$m[3]}-{$m[2]}-{$m[1]}";
    return null;
}

// ═══════════════════════════════════════════════════════
// SYNC: xempus_consultations → pm_contracts
// ═══════════════════════════════════════════════════════

/**
 * Synchronisiert aktive Xempus-Beratungen in pm_contracts.
 * Nutzt xempus_id (UUID) als UPSERT-Key.
 * Berechnet vsnr_normalized, loest Berater auf, mappt Status.
 */
function syncXempusToPmContracts(?int $batchId = null): array {
    $where = 'xc.is_active = TRUE AND xc.versicherungsscheinnummer IS NOT NULL AND xc.versicherungsscheinnummer != ""';
    $params = [];
    if ($batchId) {
        $where .= ' AND xc.last_seen_batch_id = ?';
        $params[] = $batchId;
    }

    $consultations = Database::query("
        SELECT xc.*, COALESCE(xsm.category, 'offen') as status_category
        FROM xempus_consultations xc
        LEFT JOIN xempus_status_mapping xsm ON xc.status = xsm.raw_status
        WHERE $where
    ", $params);

    if (empty($consultations)) {
        return ['synced' => 0, 'skipped' => 0, 'errors' => 0];
    }

    $allMappings = Database::query("SELECT vermittler_name_normalized, berater_id FROM pm_vermittler_mapping");
    $mappingLookup = [];
    foreach ($allMappings as $mp) {
        $mappingLookup[$mp['vermittler_name_normalized']] = (int)$mp['berater_id'];
    }

    $synced = 0;
    $skipped = 0;
    $errors = 0;

    $pdo = Database::getInstance();
    $stmt = $pdo->prepare("
        INSERT INTO pm_contracts
        (vsnr, vsnr_normalized, versicherer, versicherungsnehmer, versicherungsnehmer_normalized,
         sparte, tarif, beitrag, beginn, berater_id, berater_name, status, source, xempus_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'xempus', ?)
        ON DUPLICATE KEY UPDATE
            vsnr = VALUES(vsnr),
            vsnr_normalized = VALUES(vsnr_normalized),
            versicherer = COALESCE(VALUES(versicherer), versicherer),
            versicherungsnehmer = COALESCE(VALUES(versicherungsnehmer), versicherungsnehmer),
            versicherungsnehmer_normalized = COALESCE(VALUES(versicherungsnehmer_normalized), versicherungsnehmer_normalized),
            sparte = COALESCE(VALUES(sparte), sparte),
            tarif = COALESCE(VALUES(tarif), tarif),
            beitrag = COALESCE(VALUES(beitrag), beitrag),
            beginn = COALESCE(VALUES(beginn), beginn),
            berater_id = COALESCE(VALUES(berater_id), berater_id),
            berater_name = COALESCE(VALUES(berater_name), berater_name),
            status = VALUES(status),
            updated_at = NOW()
    ");

    foreach ($consultations as $xc) {
        try {
            $vsnr = $xc['versicherungsscheinnummer'];
            $vsnrNorm = normalizeVsnr($vsnr);
            if ($vsnrNorm === '' || $vsnrNorm === '0') {
                $skipped++;
                continue;
            }

            $vnParts = array_filter([$xc['arbn_vorname'], $xc['arbn_name']]);
            $vnRaw = !empty($vnParts) ? implode(' ', $vnParts) : ($xc['arbg_name'] ?? null);
            $vnNorm = $vnRaw ? normalizeForDb($vnRaw) : null;

            $beraterId = null;
            $beraterName = $xc['berater'] ?? null;
            if ($beraterName) {
                $beraterNorm = normalizeVermittlerName($beraterName);
                $beraterId = $mappingLookup[$beraterNorm] ?? null;
            }

            $cat = $xc['status_category'] ?? 'offen';
            if ($cat === 'abgeschlossen') {
                $pmStatus = 'abgeschlossen';
            } elseif ($cat === 'beantragt') {
                $pmStatus = 'beantragt';
            } else {
                $pmStatus = 'offen';
            }

            $stmt->execute([
                $vsnr, $vsnrNorm,
                $xc['versicherer'] ?? null,
                $vnRaw, $vnNorm,
                $xc['typ'] ?? null, $xc['tarif'] ?? null,
                isset($xc['gesamtbeitrag']) ? (float)$xc['gesamtbeitrag'] : null,
                $xc['beginn'] ?? null,
                $beraterId, $beraterName,
                $pmStatus,
                $xc['id'],
            ]);
            $synced++;
        } catch (\Throwable $e) {
            error_log("syncXempusToPmContracts row {$xc['id']}: " . $e->getMessage());
            $errors++;
        }
    }

    return ['synced' => $synced, 'skipped' => $skipped, 'errors' => $errors];
}

function handleXempusSyncRoute(string $method, ?string $batchId, array $payload): void {
    if ($method !== 'POST') {
        json_error('Methode nicht erlaubt', 405);
        return;
    }

    $bid = $batchId ? (int)$batchId : null;
    $syncStats = syncXempusToPmContracts($bid);

    $matchStats = ['matched' => 0];
    try {
        $matchStats = autoMatchCommissions();
    } catch (\Throwable $e) {
        error_log("autoMatchCommissions nach Sync fehlgeschlagen: " . $e->getMessage());
    }

    logPmAction($payload, 'xempus_sync', 'xempus_import_batches', $bid,
        "Xempus→PM Sync: {$syncStats['synced']} synced, {$matchStats['matched']} matched",
        ['sync' => $syncStats, 'match' => $matchStats]
    );

    json_success([
        'sync' => $syncStats,
        'match' => $matchStats,
    ], 'Sync + Auto-Matching abgeschlossen');
}

// ═══════════════════════════════════════════════════════
// PHASE 3+4: SNAPSHOT UPDATE + FINALIZE
// ═══════════════════════════════════════════════════════

function handleXempusFinalizeRoute(string $method, ?string $batchId, array $payload): void {
    if ($method !== 'POST') {
        json_error('Methode nicht erlaubt', 405);
    }
    if (!$batchId) {
        json_error('batch_id erforderlich', 400);
    }
    $batchId = (int) $batchId;

    $batch = Database::queryOne("SELECT * FROM xempus_import_batches WHERE id = ?", [$batchId]);
    if (!$batch) {
        json_error('Batch nicht gefunden', 404);
    }

    $previousBatch = Database::queryOne(
        "SELECT id FROM xempus_import_batches
         WHERE import_phase = 'complete' AND is_active_snapshot = TRUE AND id < ?
         ORDER BY id DESC LIMIT 1",
        [$batchId]
    );
    $previousBatchId = $previousBatch ? (int) $previousBatch['id'] : null;

    $diffStats = ['added' => 0, 'removed' => 0, 'unchanged' => 0];
    $tables = ['xempus_employers', 'xempus_tariffs', 'xempus_subsidies', 'xempus_employees', 'xempus_consultations'];

    if ($previousBatchId) {
        foreach ($tables as $table) {
            $currentIds = array_column(
                Database::query("SELECT id FROM $table WHERE last_seen_batch_id = ?", [$batchId]),
                'id'
            );
            $previousIds = array_column(
                Database::query("SELECT id FROM $table WHERE last_seen_batch_id = ? AND is_active = TRUE", [$previousBatchId]),
                'id'
            );

            $removed = array_diff($previousIds, $currentIds);
            if (!empty($removed)) {
                $placeholders = implode(',', array_fill(0, count($removed), '?'));
                Database::execute(
                    "UPDATE $table SET is_active = FALSE WHERE id IN ($placeholders)",
                    array_values($removed)
                );
                $diffStats['removed'] += count($removed);
            }

            $added = array_diff($currentIds, $previousIds);
            $diffStats['added'] += count($added);
            $diffStats['unchanged'] += count(array_intersect($currentIds, $previousIds));
        }

        Database::execute(
            "UPDATE xempus_import_batches SET is_active_snapshot = FALSE WHERE id = ?",
            [$previousBatchId]
        );
    } else {
        foreach ($tables as $table) {
            $count = Database::queryOne("SELECT COUNT(*) as cnt FROM $table WHERE last_seen_batch_id = ?", [$batchId]);
            $diffStats['added'] += (int) ($count['cnt'] ?? 0);
        }
    }

    $hashParts = [];
    foreach ($tables as $table) {
        $entities = Database::query(
            "SELECT id, raw_json FROM $table WHERE last_seen_batch_id = ? ORDER BY id",
            [$batchId]
        );
        foreach ($entities as $e) {
            $hashParts[] = $e['id'] . ':' . hash('sha256', $e['raw_json'] ?? '');
        }
    }
    sort($hashParts);
    $snapshotHash = hash('sha256', implode('|', $hashParts));

    Database::execute(
        "UPDATE xempus_import_batches
         SET import_phase = 'complete', is_active_snapshot = TRUE,
             snapshot_hash = ?, previous_batch_id = ?
         WHERE id = ?",
        [$snapshotHash, $previousBatchId, $batchId]
    );

    $recordCounts = [];
    foreach ($tables as $table) {
        $shortName = str_replace('xempus_', '', $table);
        $count = Database::queryOne("SELECT COUNT(*) as cnt FROM $table WHERE last_seen_batch_id = ? AND is_active = TRUE", [$batchId]);
        $recordCounts[$shortName] = (int) ($count['cnt'] ?? 0);
    }
    Database::execute(
        "UPDATE xempus_import_batches SET record_counts = ? WHERE id = ?",
        [json_encode($recordCounts), $batchId]
    );

    // Phase 5: Sync xempus_consultations → pm_contracts + Auto-Matching
    $syncStats = ['synced' => 0, 'skipped' => 0, 'errors' => 0];
    $matchStats = ['matched' => 0];
    try {
        $syncStats = syncXempusToPmContracts($batchId);
    } catch (\Throwable $e) {
        error_log("syncXempusToPmContracts fehlgeschlagen (Batch $batchId): " . $e->getMessage());
    }
    try {
        $matchStats = autoMatchCommissions();
    } catch (\Throwable $e) {
        error_log("autoMatchCommissions nach Sync fehlgeschlagen (Batch $batchId): " . $e->getMessage());
    }

    logPmAction($payload, 'xempus_finalize', 'xempus_import_batches', $batchId,
        "Xempus Finalize: +{$diffStats['added']} -{$diffStats['removed']} ={$diffStats['unchanged']}, Sync: {$syncStats['synced']}, Matched: {$matchStats['matched']}",
        ['diff' => $diffStats, 'snapshot_hash' => $snapshotHash, 'record_counts' => $recordCounts,
         'sync' => $syncStats, 'match' => $matchStats]
    );

    json_success([
        'batch_id' => $batchId,
        'snapshot_hash' => $snapshotHash,
        'diff' => $diffStats,
        'record_counts' => $recordCounts,
        'previous_batch_id' => $previousBatchId,
        'sync' => $syncStats,
        'match' => $matchStats,
    ], 'Snapshot finalisiert + Sync abgeschlossen');
}

// ═══════════════════════════════════════════════════════
// BATCHES (Import-Historie)
// ═══════════════════════════════════════════════════════

function handleXempusBatchesRoute(string $method, array $payload): void {
    if ($method !== 'GET') {
        json_error('Methode nicht erlaubt', 405);
    }

    $batches = Database::query("
        SELECT xib.*, u.username AS imported_by_name
        FROM xempus_import_batches xib
        LEFT JOIN users u ON xib.imported_by = u.id
        ORDER BY xib.id DESC
        LIMIT 100
    ");

    $result = [];
    foreach ($batches as $b) {
        $parseStats = Database::queryOne("
            SELECT
                COUNT(*) as total,
                SUM(parse_status = 'ok') as ok_count,
                SUM(parse_status = 'error') as error_count,
                SUM(parse_status = 'pending') as pending_count
            FROM xempus_raw_rows WHERE import_batch_id = ?
        ", [$b['id']]);

        $b['parse_stats'] = [
            'total' => (int) ($parseStats['total'] ?? 0),
            'ok' => (int) ($parseStats['ok_count'] ?? 0),
            'error' => (int) ($parseStats['error_count'] ?? 0),
            'pending' => (int) ($parseStats['pending_count'] ?? 0),
        ];
        $b['record_counts'] = $b['record_counts'] ? json_decode($b['record_counts'], true) : null;
        $result[] = $b;
    }

    json_success(['batches' => $result]);
}

// ═══════════════════════════════════════════════════════
// EMPLOYERS (Arbeitgeber)
// ═══════════════════════════════════════════════════════

function handleXempusEmployersRoute(string $method, ?string $entityId, array $payload): void {
    if ($method !== 'GET') {
        json_error('Methode nicht erlaubt', 405);
    }

    if ($entityId) {
        $employer = Database::queryOne("SELECT * FROM xempus_employers WHERE id = ?", [$entityId]);
        if (!$employer) {
            json_error('Arbeitgeber nicht gefunden', 404);
        }

        $tariffs = Database::query(
            "SELECT * FROM xempus_tariffs WHERE employer_id = ? AND is_active = TRUE ORDER BY versicherer",
            [$entityId]
        );
        $subsidies = Database::query(
            "SELECT * FROM xempus_subsidies WHERE employer_id = ? AND is_active = TRUE",
            [$entityId]
        );

        $employeeStats = Database::queryOne("
            SELECT
                COUNT(*) as total,
                SUM(beratungsstatus IS NOT NULL) as with_status
            FROM xempus_employees WHERE employer_id = ? AND is_active = TRUE
        ", [$entityId]);

        $statusDist = Database::query("
            SELECT
                COALESCE(xsm.category, 'nicht_angesprochen') as category,
                COALESCE(xsm.display_label, 'Nicht angesprochen') as display_label,
                COALESCE(xsm.color, '#9e9e9e') as color,
                COUNT(*) as cnt
            FROM xempus_employees xe
            LEFT JOIN xempus_status_mapping xsm ON xe.beratungsstatus = xsm.raw_status
            WHERE xe.employer_id = ? AND xe.is_active = TRUE
            GROUP BY category, display_label, color
            ORDER BY cnt DESC
        ", [$entityId]);

        $employer['raw_json'] = null;
        json_success([
            'employer' => $employer,
            'tariffs' => $tariffs,
            'subsidies' => $subsidies,
            'employee_count' => (int) ($employeeStats['total'] ?? 0),
            'status_distribution' => $statusDist,
        ]);
    } else {
        $employers = Database::query("
            SELECT xe.*,
                (SELECT COUNT(*) FROM xempus_employees em WHERE em.employer_id = xe.id AND em.is_active = TRUE) as employee_count,
                (SELECT COUNT(*) FROM xempus_tariffs t WHERE t.employer_id = xe.id AND t.is_active = TRUE) as tariff_count,
                (SELECT COUNT(*) FROM xempus_subsidies s WHERE s.employer_id = xe.id AND s.is_active = TRUE) as subsidy_count
            FROM xempus_employers xe
            WHERE xe.is_active = TRUE
            ORDER BY xe.name
        ");

        foreach ($employers as &$e) {
            $e['raw_json'] = null;
        }
        unset($e);

        json_success(['employers' => $employers]);
    }
}

// ═══════════════════════════════════════════════════════
// EMPLOYEES (Arbeitnehmer)
// ═══════════════════════════════════════════════════════

function handleXempusEmployeesRoute(string $method, ?string $entityId, array $payload): void {
    if ($method !== 'GET') {
        json_error('Methode nicht erlaubt', 405);
    }

    if ($entityId) {
        $employee = Database::queryOne("
            SELECT xe.*, xemp.name as employer_name
            FROM xempus_employees xe
            LEFT JOIN xempus_employers xemp ON xe.employer_id = xemp.id
            WHERE xe.id = ?
        ", [$entityId]);
        if (!$employee) {
            json_error('Arbeitnehmer nicht gefunden', 404);
        }

        $consultations = Database::query(
            "SELECT * FROM xempus_consultations WHERE employee_id = ? AND is_active = TRUE ORDER BY beratungsdatum DESC",
            [$entityId]
        );

        $employee['raw_json'] = null;
        foreach ($consultations as &$c) { $c['raw_json'] = null; }
        unset($c);

        json_success(['employee' => $employee, 'consultations' => $consultations]);
    } else {
        $page = max(1, (int) ($_GET['page'] ?? 1));
        $perPage = min(200, max(10, (int) ($_GET['per_page'] ?? 50)));
        $offset = ($page - 1) * $perPage;
        $employerId = $_GET['employer_id'] ?? null;
        $status = $_GET['status'] ?? null;
        $q = $_GET['q'] ?? null;

        $where = ['xe.is_active = TRUE'];
        $params = [];

        if ($employerId) {
            $where[] = 'xe.employer_id = ?';
            $params[] = $employerId;
        }
        if ($status) {
            $where[] = 'EXISTS (SELECT 1 FROM xempus_status_mapping xsm WHERE xsm.raw_status = xe.beratungsstatus AND xsm.category = ?)';
            $params[] = $status;
        }
        if ($q) {
            $where[] = "(xe.name LIKE ? OR xe.vorname LIKE ? OR xe.email LIKE ?)";
            $params[] = "%$q%"; $params[] = "%$q%"; $params[] = "%$q%";
        }

        $whereClause = implode(' AND ', $where);

        $total = Database::queryOne("SELECT COUNT(*) as cnt FROM xempus_employees xe WHERE $whereClause", $params);
        $totalCount = (int) ($total['cnt'] ?? 0);

        $employees = Database::query("
            SELECT xe.*, xemp.name as employer_name,
                   xsm.category as status_category, xsm.display_label as status_label, xsm.color as status_color
            FROM xempus_employees xe
            LEFT JOIN xempus_employers xemp ON xe.employer_id = xemp.id
            LEFT JOIN xempus_status_mapping xsm ON xe.beratungsstatus = xsm.raw_status
            WHERE $whereClause
            ORDER BY xe.name, xe.vorname
            LIMIT $perPage OFFSET $offset
        ", $params);

        foreach ($employees as &$e) { $e['raw_json'] = null; }
        unset($e);

        json_success([
            'employees' => $employees,
            'pagination' => [
                'page' => $page,
                'per_page' => $perPage,
                'total' => $totalCount,
                'total_pages' => (int) ceil($totalCount / $perPage),
            ],
        ]);
    }
}

// ═══════════════════════════════════════════════════════
// CONSULTATIONS (Beratungen)
// ═══════════════════════════════════════════════════════

function handleXempusConsultationsRoute(string $method, ?string $entityId, array $payload): void {
    if ($method !== 'GET') {
        json_error('Methode nicht erlaubt', 405);
    }

    if ($entityId) {
        $cons = Database::queryOne("SELECT * FROM xempus_consultations WHERE id = ?", [$entityId]);
        if (!$cons) json_error('Beratung nicht gefunden', 404);
        $cons['raw_json'] = null;
        json_success(['consultation' => $cons]);
    }

    $page = max(1, (int) ($_GET['page'] ?? 1));
    $perPage = min(200, max(10, (int) ($_GET['per_page'] ?? 50)));
    $offset = ($page - 1) * $perPage;
    $employerId = $_GET['employer_id'] ?? null;
    $status = $_GET['status'] ?? null;
    $q = $_GET['q'] ?? null;

    $where = ['xc.is_active = TRUE'];
    $params = [];

    if ($employerId) {
        $where[] = 'xc.employer_id = ?'; $params[] = $employerId;
    }
    if ($status) {
        $where[] = 'EXISTS (SELECT 1 FROM xempus_status_mapping xsm WHERE xsm.raw_status = xc.status AND xsm.category = ?)';
        $params[] = $status;
    }
    if ($q) {
        $where[] = "(xc.arbn_name LIKE ? OR xc.arbn_vorname LIKE ? OR xc.versicherungsscheinnummer LIKE ? OR xc.versicherer LIKE ?)";
        $params[] = "%$q%"; $params[] = "%$q%"; $params[] = "%$q%"; $params[] = "%$q%";
    }

    $whereClause = implode(' AND ', $where);

    $total = Database::queryOne("SELECT COUNT(*) as cnt FROM xempus_consultations xc WHERE $whereClause", $params);
    $totalCount = (int) ($total['cnt'] ?? 0);

    $consultations = Database::query("
        SELECT xc.*,
               xsm.category as status_category, xsm.display_label as status_label, xsm.color as status_color
        FROM xempus_consultations xc
        LEFT JOIN xempus_status_mapping xsm ON xc.status = xsm.raw_status
        WHERE $whereClause
        ORDER BY xc.beratungsdatum DESC
        LIMIT $perPage OFFSET $offset
    ", $params);

    foreach ($consultations as &$c) { $c['raw_json'] = null; }
    unset($c);

    json_success([
        'consultations' => $consultations,
        'pagination' => [
            'page' => $page,
            'per_page' => $perPage,
            'total' => $totalCount,
            'total_pages' => (int) ceil($totalCount / $perPage),
        ],
    ]);
}

// ═══════════════════════════════════════════════════════
// STATS (Aggregierte KPIs)
// ═══════════════════════════════════════════════════════

function handleXempusStatsRoute(string $method, array $payload): void {
    if ($method !== 'GET') {
        json_error('Methode nicht erlaubt', 405);
    }

    $totalEmployers = Database::queryOne("SELECT COUNT(*) as cnt FROM xempus_employers WHERE is_active = TRUE");
    $totalEmployees = Database::queryOne("SELECT COUNT(*) as cnt FROM xempus_employees WHERE is_active = TRUE");
    $totalConsultations = Database::queryOne("SELECT COUNT(*) as cnt FROM xempus_consultations WHERE is_active = TRUE");

    $statusDist = Database::query("
        SELECT
            COALESCE(xsm.category, 'nicht_angesprochen') as category,
            COALESCE(xsm.display_label, TRIM(xc.status)) as display_label,
            COALESCE(xsm.color, '#9e9e9e') as color,
            COUNT(*) as count
        FROM xempus_consultations xc
        LEFT JOIN xempus_status_mapping xsm ON TRIM(xc.status) = TRIM(xsm.raw_status)
        WHERE xc.is_active = TRUE
        GROUP BY category, display_label, color
        ORDER BY count DESC
    ");

    $totalCons = (int) ($totalConsultations['cnt'] ?? 0);
    $konvertiert = 0;
    $abgeschlossen = 0;
    $angesprochen = 0;
    foreach ($statusDist as $sd) {
        $cat = $sd['category'];
        $cnt = (int) $sd['count'];
        if ($cat === 'abgeschlossen') $abgeschlossen += $cnt;
        if (in_array($cat, ['abgeschlossen', 'beantragt'])) $konvertiert += $cnt;
        if (in_array($cat, ['abgeschlossen', 'beantragt', 'offen', 'abgelehnt'])) {
            $angesprochen += $cnt;
        }
    }

    $anspracheQuote = $totalCons > 0 ? round($angesprochen / $totalCons * 100, 1) : 0;
    $konversionsQuote = $angesprochen > 0 ? round($konvertiert / $angesprochen * 100, 1) : 0;
    $abschlussQuote = $konversionsQuote;
    $erfolgsQuote = $totalCons > 0 ? round($konvertiert / $totalCons * 100, 1) : 0;

    $perEmployerRaw = Database::query("
        SELECT
            xe.id, xe.name,
            (SELECT COUNT(*) FROM xempus_employees em WHERE em.employer_id = xe.id AND em.is_active = TRUE) as employees,
            (SELECT COUNT(*) FROM xempus_consultations xc WHERE xc.employer_id = xe.id AND xc.is_active = TRUE) as consultations,
            (SELECT COUNT(*) FROM xempus_consultations xc
             JOIN xempus_status_mapping xsm ON TRIM(xc.status) = TRIM(xsm.raw_status) AND xsm.category IN ('abgeschlossen', 'beantragt')
             WHERE xc.employer_id = xe.id AND xc.is_active = TRUE) as konvertiert_count,
            (SELECT COALESCE(SUM(xc.gesamtbeitrag), 0) FROM xempus_consultations xc
             JOIN xempus_status_mapping xsm ON TRIM(xc.status) = TRIM(xsm.raw_status) AND xsm.category IN ('abgeschlossen', 'beantragt')
             WHERE xc.employer_id = xe.id AND xc.is_active = TRUE) as beitragsvolumen
        FROM xempus_employers xe
        WHERE xe.is_active = TRUE
        ORDER BY xe.name
    ");

    $perEmployer = [];
    foreach ($perEmployerRaw as $row) {
        $cons = (int) ($row['consultations'] ?? 0);
        $conv = (int) ($row['konvertiert_count'] ?? 0);
        $row['conversion_rate'] = $cons > 0 ? round($conv / $cons * 100, 1) : 0.0;
        $perEmployer[] = $row;
    }

    $unmapped = Database::query("
        SELECT TRIM(xc.status) as raw_status, COUNT(*) as count
        FROM xempus_consultations xc
        LEFT JOIN xempus_status_mapping xsm ON TRIM(xc.status) = TRIM(xsm.raw_status)
        WHERE xc.is_active = TRUE AND xsm.id IS NULL AND xc.status IS NOT NULL AND TRIM(xc.status) != ''
        GROUP BY TRIM(xc.status)
        ORDER BY count DESC
        LIMIT 20
    ");

    json_success([
        'total_employers' => (int) ($totalEmployers['cnt'] ?? 0),
        'total_employees' => (int) ($totalEmployees['cnt'] ?? 0),
        'total_consultations' => $totalCons,
        'ansprache_quote' => $anspracheQuote,
        'abschluss_quote' => $abschlussQuote,
        'erfolgs_quote' => $erfolgsQuote,
        'status_distribution' => $statusDist,
        'per_employer' => $perEmployer,
        'unmapped_statuses' => $unmapped,
        '_debug' => [
            'konvertiert' => $konvertiert,
            'abgeschlossen' => $abgeschlossen,
            'angesprochen' => $angesprochen,
            'total_cons' => $totalCons,
        ],
    ]);
}

// ═══════════════════════════════════════════════════════
// DIFF (Snapshot-Vergleich)
// ═══════════════════════════════════════════════════════

function handleXempusDiffRoute(string $method, ?string $batchId, array $payload): void {
    if ($method !== 'GET') {
        json_error('Methode nicht erlaubt', 405);
    }
    if (!$batchId) {
        json_error('batch_id erforderlich', 400);
    }
    $batchId = (int) $batchId;

    $batch = Database::queryOne("SELECT * FROM xempus_import_batches WHERE id = ?", [$batchId]);
    if (!$batch) {
        json_error('Batch nicht gefunden', 404);
    }

    $previousBatchId = $batch['previous_batch_id'] ? (int) $batch['previous_batch_id'] : null;
    if (!$previousBatchId) {
        json_success(['diff' => null, 'message' => 'Kein vorheriger Snapshot vorhanden']);
    }

    $diff = [];
    $tables = [
        'xempus_employers' => 'name',
        'xempus_employees' => 'CONCAT(name, " ", vorname)',
        'xempus_consultations' => 'CONCAT(arbn_name, " ", arbn_vorname, " - ", COALESCE(versicherer, ""))',
    ];

    foreach ($tables as $table => $displayExpr) {
        $shortName = str_replace('xempus_', '', $table);

        $added = Database::query("
            SELECT id, $displayExpr as display_name
            FROM $table
            WHERE first_seen_batch_id = ? AND is_active = TRUE
            ORDER BY $displayExpr
            LIMIT 100
        ", [$batchId]);

        $removed = Database::query("
            SELECT id, $displayExpr as display_name
            FROM $table
            WHERE last_seen_batch_id = ? AND is_active = FALSE
            ORDER BY $displayExpr
            LIMIT 100
        ", [$previousBatchId]);

        $diff[$shortName] = [
            'added' => $added,
            'added_count' => count($added),
            'removed' => $removed,
            'removed_count' => count($removed),
        ];
    }

    $statusChanges = Database::query("
        SELECT
            xc.id, xc.arbn_name, xc.arbn_vorname, xc.status as new_status,
            xrr_old.raw_json as old_raw
        FROM xempus_consultations xc
        JOIN xempus_raw_rows xrr_new ON xrr_new.parsed_entity_id = xc.id AND xrr_new.import_batch_id = ?
        JOIN xempus_raw_rows xrr_old ON xrr_old.parsed_entity_id = xc.id AND xrr_old.import_batch_id = ?
        WHERE xc.is_active = TRUE
        LIMIT 200
    ", [$batchId, $previousBatchId]);

    $changes = [];
    foreach ($statusChanges as $sc) {
        $oldData = json_decode($sc['old_raw'] ?? '{}', true);
        $oldStatus = $oldData['status'] ?? '';
        if ($oldStatus !== $sc['new_status'] && $oldStatus !== '') {
            $changes[] = [
                'id' => $sc['id'],
                'name' => trim($sc['arbn_name'] . ' ' . $sc['arbn_vorname']),
                'old_status' => $oldStatus,
                'new_status' => $sc['new_status'],
            ];
        }
    }
    $diff['status_changes'] = $changes;

    json_success(['diff' => $diff, 'batch_id' => $batchId, 'previous_batch_id' => $previousBatchId]);
}

// ═══════════════════════════════════════════════════════
// STATUS-MAPPING (CRUD)
// ═══════════════════════════════════════════════════════

function xempusSeedStatusMappingDefaults(): int {
    $seedData = [
        ['Policiert', 'abgeschlossen', 'Abgeschlossen', '#4caf50'],
        ['Abgeschlossen', 'abgeschlossen', 'Abgeschlossen', '#4caf50'],
        ['Police erstellt', 'abgeschlossen', 'Abgeschlossen', '#4caf50'],
        ['Vertrag aktiv', 'abgeschlossen', 'Abgeschlossen', '#4caf50'],
        ['Beantragt', 'beantragt', 'Beantragt', '#2196f3'],
        ['In Bearbeitung', 'beantragt', 'Beantragt', '#2196f3'],
        ['Entscheidung ausstehend', 'offen', 'Offen', '#ff9800'],
        ['Unberaten', 'offen', 'Offen', '#ff9800'],
        ['Angesprochen', 'offen', 'Offen', '#ff9800'],
        ['Beratung erfolgt', 'offen', 'Offen', '#ff9800'],
        ['Nicht gewünscht', 'abgelehnt', 'Abgelehnt', '#f44336'],
        ['Abgelehnt', 'abgelehnt', 'Abgelehnt', '#f44336'],
        ['Nicht angesprochen', 'nicht_angesprochen', 'Nicht angesprochen', '#9e9e9e'],
    ];
    $inserted = 0;
    foreach ($seedData as [$raw, $cat, $label, $color]) {
        try {
            Database::execute(
                "INSERT IGNORE INTO xempus_status_mapping (raw_status, category, display_label, color) VALUES (?, ?, ?, ?)",
                [$raw, $cat, $label, $color]
            );
            $inserted++;
        } catch (\Throwable $ignore) {}
    }
    return $inserted;
}

function handleXempusStatusMappingRoute(string $method, array $payload): void {
    if ($method === 'GET') {
        $cnt = Database::queryOne("SELECT COUNT(*) as cnt FROM xempus_status_mapping");
        if ((int)($cnt['cnt'] ?? 0) === 0) {
            xempusSeedStatusMappingDefaults();
        }
        $mappings = Database::query("SELECT * FROM xempus_status_mapping ORDER BY category, raw_status");
        json_success(['mappings' => $mappings]);
    }

    if ($method === 'POST') {
        $body = get_json_body();
        $rawStatus = trim($body['raw_status'] ?? '');
        $category = $body['category'] ?? '';
        $displayLabel = $body['display_label'] ?? '';
        $color = $body['color'] ?? '#9e9e9e';

        if (!$rawStatus || !$category) {
            json_error('raw_status und category erforderlich', 400);
        }

        $validCategories = ['abgeschlossen', 'beantragt', 'offen', 'abgelehnt', 'nicht_angesprochen'];
        if (!in_array($category, $validCategories)) {
            json_error('Ungueltige Kategorie. Erlaubt: ' . implode(', ', $validCategories), 400);
        }

        try {
            Database::execute(
                "INSERT INTO xempus_status_mapping (raw_status, category, display_label, color)
                 VALUES (?, ?, ?, ?)
                 ON DUPLICATE KEY UPDATE category = VALUES(category), display_label = VALUES(display_label), color = VALUES(color)",
                [$rawStatus, $category, $displayLabel ?: $category, $color]
            );
            json_success(['message' => 'Status-Mapping gespeichert']);
        } catch (\Throwable $e) {
            json_error('Fehler: ' . $e->getMessage(), 500);
        }
    }

    json_error('Methode nicht erlaubt', 405);
}

// ═══════════════════════════════════════════════════════
// HELPER: logPmAction (falls nicht geladen)
// ═══════════════════════════════════════════════════════

if (!function_exists('logPmAction')) {
    function logPmAction(array $payload, string $action, ?string $entityType, $entityId, string $description, $metadata = null): void {
        try {
            ActivityLogger::log(
                $payload['user_id'] ?? 0,
                $action,
                $entityType,
                $entityId,
                $description,
                $metadata ? (is_string($metadata) ? $metadata : json_encode($metadata)) : null,
                'provision'
            );
        } catch (\Throwable $e) {
            error_log("logPmAction failed: " . $e->getMessage());
        }
    }
}

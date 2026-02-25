<?php
/**
 * BiPro API - Provisionsmanagement
 *
 * Geschaeftsfuehrer-Ebene: Mitarbeiter, Provisionen, Importe, Abrechnungen.
 *
 * Alle Endpoints erfordern JWT + provision_access Permission.
 * Gefahrenzone (/pm/reset) erfordert zusaetzlich provision_manage.
 *
 * Route: /api/pm/{action}[/{id}][/{sub}]
 *
 * Endpoints:
 *   GET/POST/PUT/DELETE  /pm/employees[/{id}]
 *   GET/PUT              /pm/contracts[/{id}]
 *   GET                  /pm/contracts/unmatched
 *   GET                  /pm/commissions
 *   PUT                  /pm/commissions/{id}/match
 *   PUT                  /pm/commissions/{id}/ignore
 *   POST                 /pm/commissions/recalculate
 *   POST                 /pm/import/vu-liste
 *   POST                 /pm/import/xempus
 *   POST                 /pm/import/match
 *   GET                  /pm/import/batches
 *   GET                  /pm/dashboard/summary
 *   GET                  /pm/dashboard/berater/{id}
 *   GET/POST/DELETE      /pm/mappings[/{id}]
 *   GET/POST/PUT         /pm/abrechnungen[/{id}]
 *   GET/POST/PUT         /pm/models[/{id}]
 *   GET                  /pm/match-suggestions
 *   PUT                  /pm/assign
 *   GET                  /pm/clearance
 *   GET                  /pm/audit[/{type}/{id}]
 *   POST                 /pm/reset                    (Gefahrenzone - loescht alle Import-Daten, Admin-only)
 */

require_once __DIR__ . '/lib/db.php';
require_once __DIR__ . '/lib/jwt.php';
require_once __DIR__ . '/lib/response.php';
require_once __DIR__ . '/lib/permissions.php';
require_once __DIR__ . '/lib/activity_logger.php';

// ═══════════════════════════════════════════════════════
// HILFSFUNKTIONEN
// ═══════════════════════════════════════════════════════

function normalizeVsnr(string $raw): string {
    $s = trim($raw);
    if ($s === '') return '';
    // Scientific notation (z.B. 1.23E+10 aus Excel) in Integer konvertieren
    if (stripos($s, 'e') !== false && (strpos($s, ',') !== false || strpos($s, '.') !== false)) {
        $s = str_replace(',', '.', $s);
        try {
            $num = (float)$s;
            if (is_finite($num) && $num > 0) {
                $s = number_format($num, 0, '', '');
            }
        } catch (\Throwable $e) {}
    }
    // Alle Nicht-Ziffern entfernen (Buchstaben, Sonderzeichen, Leerzeichen)
    $digits = preg_replace('/\D/', '', $s);
    // ALLE Nullen entfernen (fuehrende UND interne) fuer robustes Matching
    // z.B. "00123045" -> "12345", "A-001-234" -> "1234"
    $noZeros = str_replace('0', '', $digits);
    return $noZeros !== '' ? $noZeros : '0';
}

function normalizeVermittlerName(string $name): string {
    $name = mb_strtolower(trim($name));
    $replacements = ['ä' => 'ae', 'ö' => 'oe', 'ü' => 'ue', 'ß' => 'ss'];
    $name = str_replace(array_keys($replacements), array_values($replacements), $name);
    $name = preg_replace('/[^a-z0-9\s]/', '', $name);
    $name = preg_replace('/\s+/', ' ', $name);
    return trim($name);
}

function normalizeForDb(string $name): string {
    $name = mb_strtolower(trim($name));
    $name = str_replace(['ä','ö','ü','ß'], ['ae','oe','ue','ss'], $name);
    $name = preg_replace('/\(([^)]+)\)/', ' $1', $name);
    $name = preg_replace('/[^a-z0-9\s]/', ' ', $name);
    $name = preg_replace('/\s+/', ' ', trim($name));
    return $name;
}

// ═══════════════════════════════════════════════════════
// BERATER-SYNC SERVICE (Vertrag = Wahrheit)
// ═══════════════════════════════════════════════════════

/**
 * Synct berater_id vom Vertrag auf ALLE verknuepften Commissions.
 * Wird aufgerufen wenn:
 *  - Vertrag einen neuen Berater bekommt
 *  - Vertrag via Assign mit Commission verknuepft wird
 *
 * Recalculate splits fuer alle betroffenen Commissions.
 */
function syncBeraterToCommissions(int $contractId): int {
    $contract = Database::queryOne('SELECT berater_id FROM pm_contracts WHERE id = ?', [$contractId]);
    if (!$contract) return 0;
    $beraterId = $contract['berater_id'] ? (int)$contract['berater_id'] : null;

    $affected = Database::execute(
        'UPDATE pm_commissions SET berater_id = ? WHERE contract_id = ?',
        [$beraterId, $contractId]
    );

    if ($beraterId && $affected > 0) {
        batchRecalculateSplits("AND c.contract_id = ?", [$contractId]);
    }
    return $affected;
}

/**
 * Setzt berater_id auf Vertrag + synct alle verknuepften Commissions.
 * Transaktional.
 */
function assignBeraterToContract(int $contractId, int $beraterId): void {
    Database::execute('UPDATE pm_contracts SET berater_id = ? WHERE id = ?', [$beraterId, $contractId]);
    syncBeraterToCommissions($contractId);
}

/**
 * Verknuepft eine Commission mit einem Vertrag.
 * - Setzt contract_id + berater_id (abgeleitet vom Vertrag)
 * - Sucht ALLE anderen ungematchten Commissions mit derselben VSNR
 *   und verknuepft sie ebenfalls (Batch-Sync)
 * - Recalculate Splits
 * - Setzt Vertragsstatus auf 'provision_erhalten' wenn offen/beantragt
 *
 * Gibt Anzahl der insgesamt verknuepften Commissions zurueck.
 */
function assignContractToCommission(int $commissionId, int $contractId, bool $forceOverride = false): int {
    $comm = Database::queryOne('SELECT * FROM pm_commissions WHERE id = ?', [$commissionId]);
    if (!$comm) throw new \RuntimeException('Provision nicht gefunden');
    $contract = Database::queryOne('SELECT * FROM pm_contracts WHERE id = ?', [$contractId]);
    if (!$contract) throw new \RuntimeException('Vertrag nicht gefunden');

    if ($comm['contract_id'] && (int)$comm['contract_id'] !== $contractId && !$forceOverride) {
        throw new \RuntimeException('Provision ist bereits einem anderen Vertrag zugeordnet');
    }

    $beraterId = $contract['berater_id'] ? (int)$contract['berater_id'] : null;

    Database::execute(
        'UPDATE pm_commissions SET contract_id = ?, berater_id = ?, match_status = "manual_matched", match_confidence = 1.0 WHERE id = ?',
        [$contractId, $beraterId, $commissionId]
    );
    $totalAssigned = 1;

    if ($beraterId) {
        recalculateCommissionSplit($commissionId, $beraterId);
    }

    // Batch-Sync: Alle ungematchten Commissions mit derselben VSNR ebenfalls verknuepfen
    $vsnrNorm = $comm['vsnr_normalized'] ?? null;
    if ($vsnrNorm) {
        $siblings = Database::query(
            "SELECT id FROM pm_commissions
             WHERE vsnr_normalized = ? AND id != ? AND match_status = 'unmatched'",
            [$vsnrNorm, $commissionId]
        );
        foreach ($siblings as $sib) {
            Database::execute(
                'UPDATE pm_commissions SET contract_id = ?, berater_id = ?, match_status = "auto_matched", match_confidence = 1.0 WHERE id = ?',
                [$contractId, $beraterId, (int)$sib['id']]
            );
            if ($beraterId) {
                recalculateCommissionSplit((int)$sib['id'], $beraterId);
            }
            $totalAssigned++;
        }
    }

    // Vertragsstatus aktualisieren
    if (in_array($contract['status'], ['offen', 'beantragt', 'abgeschlossen'])) {
        Database::execute(
            'UPDATE pm_contracts SET status = "provision_erhalten" WHERE id = ?',
            [$contractId]
        );
    }

    return $totalAssigned;
}

// ═══════════════════════════════════════════════════════
// SPLIT-ENGINE
// ═══════════════════════════════════════════════════════

function recalculateCommissionSplit(int $commissionId, int $beraterId): void {
    $commission = Database::queryOne(
        'SELECT betrag, art FROM pm_commissions WHERE id = ?', [$commissionId]
    );
    if (!$commission) return;

    $betrag = (float)$commission['betrag'];
    $art = $commission['art'];

    $berater = Database::queryOne(
        'SELECT e.commission_rate_override, e.commission_model_id, e.teamleiter_id,
                e.tl_override_rate, e.tl_override_basis,
                m.commission_rate AS model_rate
         FROM pm_employees e
         LEFT JOIN pm_commission_models m ON e.commission_model_id = m.id
         WHERE e.id = ?',
        [$beraterId]
    );
    if (!$berater) return;

    $rate = (float)($berater['commission_rate_override'] ?? $berater['model_rate'] ?? 0);
    $beraterAnteilBrutto = round($betrag * $rate / 100, 2);
    $agAnteil = round($betrag - $beraterAnteilBrutto, 2);

    if ($art === 'rueckbelastung' || $betrag < 0) {
        Database::execute(
            'UPDATE pm_commissions SET berater_anteil = ?, tl_anteil = 0, ag_anteil = ? WHERE id = ?',
            [$beraterAnteilBrutto, $agAnteil, $commissionId]
        );
        return;
    }

    // TL-Override: Rate/Basis stehen auf dem BERATER selbst
    $tlAnteil = 0.0;
    if ($berater['teamleiter_id'] && (float)($berater['tl_override_rate'] ?? 0) > 0) {
        $tlRate = (float)$berater['tl_override_rate'];
        if (($berater['tl_override_basis'] ?? 'berater_anteil') === 'gesamt_courtage') {
            $tlAnteil = round($betrag * $tlRate / 100, 2);
        } else {
            $tlAnteil = round($beraterAnteilBrutto * $tlRate / 100, 2);
        }
        if ($tlAnteil > $beraterAnteilBrutto) {
            $tlAnteil = $beraterAnteilBrutto;
        }
    }

    $beraterNetto = round($beraterAnteilBrutto - $tlAnteil, 2);

    Database::execute(
        'UPDATE pm_commissions SET berater_anteil = ?, tl_anteil = ?, ag_anteil = ? WHERE id = ?',
        [$beraterNetto, $tlAnteil, $agAnteil, $commissionId]
    );
}

function batchRecalculateSplits(?int $batchId = null, ?array $employeeIds = null, ?string $fromDate = null): int {
    $extraFilter = '';
    $extraParams = [];

    if ($batchId) {
        $extraFilter .= ' AND c.import_batch_id = ?';
        $extraParams[] = $batchId;
    }
    if ($employeeIds && count($employeeIds) > 0) {
        $placeholders = implode(',', array_fill(0, count($employeeIds), '?'));
        $extraFilter .= " AND c.berater_id IN ($placeholders)";
        $extraParams = array_merge($extraParams, $employeeIds);
    }
    if ($fromDate) {
        $extraFilter .= ' AND c.auszahlungsdatum >= ?';
        $extraParams[] = $fromDate;
    }

    // Step A: Rueckbelastungen / negative Betraege (kein TL-Anteil)
    $updNeg = Database::execute("
        UPDATE pm_commissions c
        INNER JOIN pm_employees e ON c.berater_id = e.id
        LEFT JOIN pm_commission_models m ON e.commission_model_id = m.id
        SET c.berater_anteil = ROUND(c.betrag * COALESCE(e.commission_rate_override, m.commission_rate, 0) / 100, 2),
            c.tl_anteil = 0,
            c.ag_anteil = ROUND(c.betrag - ROUND(c.betrag * COALESCE(e.commission_rate_override, m.commission_rate, 0) / 100, 2), 2)
        WHERE c.match_status IN ('auto_matched','manual_matched')
          AND c.berater_id IS NOT NULL
          AND (c.art = 'rueckbelastung' OR c.betrag < 0)
          $extraFilter
    ", $extraParams);

    // Step B: Positive Provisionen OHNE Teamleiter
    $updPosNoTl = Database::execute("
        UPDATE pm_commissions c
        INNER JOIN pm_employees e ON c.berater_id = e.id
        LEFT JOIN pm_commission_models m ON e.commission_model_id = m.id
        SET c.berater_anteil = ROUND(c.betrag * COALESCE(e.commission_rate_override, m.commission_rate, 0) / 100, 2),
            c.tl_anteil = 0,
            c.ag_anteil = ROUND(c.betrag - ROUND(c.betrag * COALESCE(e.commission_rate_override, m.commission_rate, 0) / 100, 2), 2)
        WHERE c.match_status IN ('auto_matched','manual_matched')
          AND c.berater_id IS NOT NULL
          AND c.betrag >= 0
          AND c.art != 'rueckbelastung'
          AND (e.teamleiter_id IS NULL OR e.teamleiter_id = 0)
          $extraFilter
    ", $extraParams);

    // Step C: Positive Provisionen MIT Teamleiter
    // tl_override_rate/basis stehen auf dem BERATER (e), nicht auf dem TL-Datensatz (tl)
    $updPosTl = Database::execute("
        UPDATE pm_commissions c
        INNER JOIN pm_employees e ON c.berater_id = e.id
        LEFT JOIN pm_commission_models m ON e.commission_model_id = m.id
        INNER JOIN pm_employees tl ON e.teamleiter_id = tl.id
        SET c.ag_anteil   = ROUND(c.betrag - ROUND(c.betrag * COALESCE(e.commission_rate_override, m.commission_rate, 0) / 100, 2), 2),
            c.tl_anteil   = LEAST(
                CASE WHEN COALESCE(e.tl_override_basis, 'berater_anteil') = 'gesamt_courtage'
                     THEN ROUND(c.betrag * COALESCE(e.tl_override_rate, 0) / 100, 2)
                     ELSE ROUND(ROUND(c.betrag * COALESCE(e.commission_rate_override, m.commission_rate, 0) / 100, 2)
                               * COALESCE(e.tl_override_rate, 0) / 100, 2)
                END,
                ROUND(c.betrag * COALESCE(e.commission_rate_override, m.commission_rate, 0) / 100, 2)
            ),
            c.berater_anteil = ROUND(c.betrag * COALESCE(e.commission_rate_override, m.commission_rate, 0) / 100, 2)
                - LEAST(
                    CASE WHEN COALESCE(e.tl_override_basis, 'berater_anteil') = 'gesamt_courtage'
                         THEN ROUND(c.betrag * COALESCE(e.tl_override_rate, 0) / 100, 2)
                         ELSE ROUND(ROUND(c.betrag * COALESCE(e.commission_rate_override, m.commission_rate, 0) / 100, 2)
                                   * COALESCE(e.tl_override_rate, 0) / 100, 2)
                    END,
                    ROUND(c.betrag * COALESCE(e.commission_rate_override, m.commission_rate, 0) / 100, 2)
                )
        WHERE c.match_status IN ('auto_matched','manual_matched')
          AND c.berater_id IS NOT NULL
          AND c.betrag >= 0
          AND c.art != 'rueckbelastung'
          AND e.teamleiter_id IS NOT NULL AND e.teamleiter_id > 0
          $extraFilter
    ", $extraParams);

    return $updNeg + $updPosNoTl + $updPosTl;
}

/**
 * Offene Abrechnungen (berechnet/geprueft) fuer betroffene Berater neu generieren.
 * Freigegeben/ausgezahlt bleiben unberuehrt.
 */
function regenerateOpenAbrechnungen(array $employeeIds, ?string $fromDate = null): array {
    if (empty($employeeIds)) return ['months_updated' => 0, 'abrechnungen_regenerated' => 0];

    $placeholders = implode(',', array_fill(0, count($employeeIds), '?'));
    $params = $employeeIds;

    $dateFilter = '';
    if ($fromDate) {
        $dateFilter = ' AND a2.abrechnungsmonat >= ?';
        $params[] = date('Y-m-01', strtotime($fromDate));
    }

    $openAbrechnungen = Database::query("
        SELECT DISTINCT a.abrechnungsmonat, a.berater_id
        FROM (
            SELECT a2.*, ROW_NUMBER() OVER (
                PARTITION BY a2.abrechnungsmonat, a2.berater_id ORDER BY a2.revision DESC
            ) AS rn
            FROM pm_berater_abrechnungen a2
            WHERE a2.berater_id IN ($placeholders) $dateFilter
        ) a
        WHERE a.rn = 1 AND a.status IN ('berechnet', 'geprueft')
    ", $params);

    $regenerated = 0;
    $months = [];
    foreach ($openAbrechnungen as $row) {
        $monat = $row['abrechnungsmonat'];
        $beraterId = (int)$row['berater_id'];
        $monatEnd = date('Y-m-t', strtotime($monat));

        $stats = Database::queryOne("
            SELECT
                COALESCE(SUM(CASE WHEN betrag > 0 THEN berater_anteil ELSE 0 END), 0) AS brutto,
                COALESCE(SUM(CASE WHEN betrag > 0 THEN tl_anteil ELSE 0 END), 0) AS tl_abzug,
                COALESCE(SUM(CASE WHEN betrag < 0 THEN berater_anteil ELSE 0 END), 0) AS rueckbelastungen,
                COUNT(*) AS anzahl
            FROM pm_commissions
            WHERE berater_id = ?
              AND match_status IN ('auto_matched','manual_matched')
              AND auszahlungsdatum BETWEEN ? AND ?
        ", [$beraterId, $monat, $monatEnd]);

        $brutto = (float)$stats['brutto'];
        $tlAbzug = (float)$stats['tl_abzug'];
        $rueckbelastungen = (float)$stats['rueckbelastungen'];
        $netto = round($brutto - $tlAbzug, 2);
        $auszahlung = round($netto + $rueckbelastungen, 2);

        Database::insert(
            'INSERT INTO pm_berater_abrechnungen (abrechnungsmonat, berater_id, revision,
                brutto_provision, tl_abzug, netto_provision, rueckbelastungen,
                auszahlung, anzahl_provisionen, status)
             SELECT ?, ?, COALESCE(MAX(a2.revision), 0) + 1,
                ?, ?, ?, ?, ?, ?, "berechnet"
             FROM pm_berater_abrechnungen a2
             WHERE a2.abrechnungsmonat = ? AND a2.berater_id = ?',
            [$monat, $beraterId, $brutto, $tlAbzug, $netto,
             $rueckbelastungen, $auszahlung, (int)$stats['anzahl'],
             $monat, $beraterId]
        );
        $regenerated++;
        $months[$monat] = true;
    }

    return ['months_updated' => count($months), 'abrechnungen_regenerated' => $regenerated];
}

// ═══════════════════════════════════════════════════════
// AUTO-MATCHING (Batch-JOIN)
// ═══════════════════════════════════════════════════════

function autoMatchCommissions(?int $batchId = null): array {
    $batchFilter = $batchId ? 'AND c.import_batch_id = ?' : '';
    $batchFilterC2 = $batchId ? 'AND c2.import_batch_id = ?' : '';
    $params = $batchId ? [$batchId] : [];

    $pdo = Database::getInstance();
    $pdo->beginTransaction();

    try {
        // Step 1: Batch-Match via vsnr_normalized JOIN
        $matched = Database::execute("
            UPDATE pm_commissions c
            INNER JOIN (
                SELECT c2.id AS comm_id, ct.id AS contract_id, ct.berater_id,
                       ROW_NUMBER() OVER (PARTITION BY c2.id ORDER BY ct.created_at DESC) AS rn
                FROM pm_commissions c2
                INNER JOIN pm_contracts ct ON c2.vsnr_normalized = ct.vsnr_normalized
                WHERE c2.match_status = 'unmatched' $batchFilterC2
            ) best ON c.id = best.comm_id AND best.rn = 1
            SET c.contract_id = best.contract_id,
                c.berater_id = best.berater_id,
                c.match_status = 'auto_matched',
                c.match_confidence = 1.0
            WHERE c.match_status = 'unmatched' $batchFilter
        ", array_merge($params, $params));

        // Step 1.5: Match via xempus_consultations VSNR
        $matchedXempus = 0;
        try {
            $xempusTableExists = Database::queryOne("SHOW TABLES LIKE 'xempus_consultations'");
            $colExists = $xempusTableExists ? Database::queryOne(
                "SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'pm_commissions' AND COLUMN_NAME = 'xempus_consultation_id'"
            ) : null;
            if ($xempusTableExists && $colExists) {
                $matchedXempus = Database::execute("
                    UPDATE pm_commissions c
                    INNER JOIN (
                        SELECT c2.id AS comm_id, xc.id AS xcid, xc.employee_id,
                               ROW_NUMBER() OVER (PARTITION BY c2.id ORDER BY xc.beginn DESC) AS rn
                        FROM pm_commissions c2
                        INNER JOIN xempus_consultations xc
                            ON c2.vsnr_normalized = REPLACE(REPLACE(REPLACE(xc.versicherungsscheinnummer, '-', ''), ' ', ''), '0', '')
                        WHERE c2.match_status = 'unmatched'
                          AND xc.is_active = 1
                          AND xc.versicherungsscheinnummer IS NOT NULL
                          AND xc.versicherungsscheinnummer != ''
                          $batchFilterC2
                    ) best ON c.id = best.comm_id AND best.rn = 1
                    SET c.xempus_consultation_id = best.xcid,
                        c.match_confidence = GREATEST(COALESCE(c.match_confidence, 0), 0.85)
                    WHERE c.match_status = 'unmatched' $batchFilter
                ", array_merge($params, $params));
            }
        } catch (\Throwable $e) {
            error_log("Step 1.5 Xempus-Match uebersprungen: " . $e->getMessage());
        }

        // Step 2: Try alt-VSNR for remaining unmatched
        $matchedAlt = Database::execute("
            UPDATE pm_commissions c
            INNER JOIN (
                SELECT c2.id AS comm_id, ct.id AS contract_id, ct.berater_id,
                       ROW_NUMBER() OVER (PARTITION BY c2.id ORDER BY ct.created_at DESC) AS rn
                FROM pm_commissions c2
                INNER JOIN pm_contracts ct ON c2.vsnr_normalized = ct.vsnr_alt_normalized
                WHERE c2.match_status = 'unmatched'
                  AND ct.vsnr_alt_normalized IS NOT NULL
                  AND ct.vsnr_alt_normalized != ''
                  $batchFilterC2
            ) best ON c.id = best.comm_id AND best.rn = 1
            SET c.contract_id = best.contract_id,
                c.berater_id = best.berater_id,
                c.match_status = 'auto_matched',
                c.match_confidence = 0.9
            WHERE c.match_status = 'unmatched' $batchFilter
        ", array_merge($params, $params));

        // Step 2.5: Resolve berater via Xempus berater_name (scoped to batch contracts)
        $contractFilter = $batchId
            ? "AND ct_inner.id IN (SELECT DISTINCT contract_id FROM pm_commissions WHERE import_batch_id = ? AND contract_id IS NOT NULL)"
            : "";
        $contractParams = $batchId ? [$batchId] : [];
        $unresolvedContracts = Database::query(
            "SELECT ct_inner.id, ct_inner.berater_name FROM pm_contracts ct_inner
             WHERE ct_inner.berater_id IS NULL AND ct_inner.berater_name IS NOT NULL AND ct_inner.berater_name != ''
             $contractFilter",
            $contractParams
        );
        $allMappings = Database::query("SELECT vermittler_name_normalized, berater_id FROM pm_vermittler_mapping");
        $mappingLookup = [];
        foreach ($allMappings as $mp) {
            $mappingLookup[$mp['vermittler_name_normalized']] = (int)$mp['berater_id'];
        }
        $contractsViaXempus = 0;
        foreach ($unresolvedContracts as $ct) {
            $norm = normalizeVermittlerName($ct['berater_name']);
            if (isset($mappingLookup[$norm])) {
                Database::execute(
                    'UPDATE pm_contracts SET berater_id = ? WHERE id = ?',
                    [$mappingLookup[$norm], (int)$ct['id']]
                );
                $contractsViaXempus++;
            }
        }
        // Commissions vom Vertrag ableiten (batch-scoped)
        $beraterViaXempus = Database::execute("
            UPDATE pm_commissions c
            INNER JOIN pm_contracts ct ON c.contract_id = ct.id
            SET c.berater_id = ct.berater_id
            WHERE c.berater_id IS NULL
              AND ct.berater_id IS NOT NULL
              $batchFilter
        ", $params);

        // Step 3: Resolve berater via VU Vermittler-Mapping
        $beraterResolved = Database::execute("
            UPDATE pm_commissions c
            INNER JOIN pm_vermittler_mapping m ON c.vermittler_name_normalized = m.vermittler_name_normalized
            SET c.berater_id = m.berater_id
            WHERE c.berater_id IS NULL
              AND c.vermittler_name_normalized IS NOT NULL
              AND c.vermittler_name_normalized != ''
              $batchFilter
        ", $params);
        // Step 3b: Propagiere zum Vertrag (batch-scoped)
        if ($batchId) {
            Database::execute("
                UPDATE pm_contracts ct
                INNER JOIN pm_commissions c ON c.contract_id = ct.id
                SET ct.berater_id = c.berater_id
                WHERE ct.berater_id IS NULL
                  AND c.berater_id IS NOT NULL
                  AND c.contract_id IS NOT NULL
                  AND c.import_batch_id = ?
            ", [$batchId]);
        } else {
            Database::execute("
                UPDATE pm_contracts ct
                INNER JOIN pm_commissions c ON c.contract_id = ct.id
                SET ct.berater_id = c.berater_id
                WHERE ct.berater_id IS NULL
                  AND c.berater_id IS NOT NULL
                  AND c.contract_id IS NOT NULL
            ");
        }

        // Step 4: Recalculate splits for newly matched
        $recalced = batchRecalculateSplits($batchId);

        // Step 5: Update contract statuses (batch-scoped)
        if ($batchId) {
            Database::execute("
                UPDATE pm_contracts ct
                INNER JOIN pm_commissions c ON c.contract_id = ct.id
                SET ct.status = 'provision_erhalten'
                WHERE ct.status IN ('offen', 'beantragt', 'abgeschlossen')
                  AND c.match_status IN ('auto_matched', 'manual_matched')
                  AND c.betrag > 0
                  AND c.import_batch_id = ?
            ", [$batchId]);
        } else {
            Database::execute("
                UPDATE pm_contracts ct
                INNER JOIN pm_commissions c ON c.contract_id = ct.id
                SET ct.status = 'provision_erhalten'
                WHERE ct.status IN ('offen', 'beantragt', 'abgeschlossen')
                  AND c.match_status IN ('auto_matched', 'manual_matched')
                  AND c.betrag > 0
            ");
        }

        $pdo->commit();
    } catch (\Throwable $e) {
        $pdo->rollBack();
        throw $e;
    }

    $stillUnmatched = Database::queryOne(
        "SELECT COUNT(*) as cnt FROM pm_commissions WHERE match_status = 'unmatched' $batchFilter",
        $params
    );

    return [
        'matched' => $matched + $matchedAlt,
        'matched_xempus_consultation' => $matchedXempus,
        'berater_via_xempus' => $beraterViaXempus,
        'berater_resolved' => $beraterResolved,
        'splits_calculated' => $recalced,
        'still_unmatched' => (int)($stillUnmatched['cnt'] ?? 0),
    ];
}

// ═══════════════════════════════════════════════════════
// PM-ACTIVITY LOGGING HELPER
// ═══════════════════════════════════════════════════════

function logPmAction(array $payload, string $action, ?string $entityType, ?int $entityId, string $desc, ?array $details = null): void {
    ActivityLogger::log([
        'user_id' => $payload['user_id'] ?? null,
        'username' => $payload['username'] ?? '',
        'action_category' => 'provision',
        'action' => $action,
        'entity_type' => $entityType,
        'entity_id' => $entityId,
        'description' => $desc,
        'details' => $details,
        'status' => 'success',
    ]);
}

// ═══════════════════════════════════════════════════════
// DISPATCHER
// ═══════════════════════════════════════════════════════

function handleProvisionRequest(?string $action, string $method, ?string $id = null, ?string $sub = null): void {
    $payload = requirePermission('provision_access');

    switch ($action) {
        case 'employees':
            handleEmployeesRoute($method, $id, $payload);
            break;
        case 'contracts':
            handleContractsRoute($method, $id, $payload);
            break;
        case 'commissions':
            handleCommissionsRoute($method, $id, $sub, $payload);
            break;
        case 'import':
            handleImportRoute($method, $id, $payload);
            break;
        case 'dashboard':
            handleDashboardRoute($method, $id, $sub, $payload);
            break;
        case 'mappings':
            handleMappingsRoute($method, $id, $payload);
            break;
        case 'abrechnungen':
            handleAbrechnungenRoute($method, $id, $payload);
            break;
        case 'models':
            handleModelsRoute($method, $id, $payload);
            break;
        case 'match-suggestions':
            handleMatchSuggestionsRoute($method, $payload);
            break;
        case 'assign':
            handleAssignRoute($method, $payload);
            break;
        case 'clearance':
            handleClearanceRoute($method, $payload);
            break;
        case 'audit':
            handleAuditRoute($method, $id, $sub, $payload);
            break;
        case 'reset':
            handleResetRoute($method, $payload);
            break;
        case 'xempus':
            require_once __DIR__ . '/xempus.php';
            handleXempusRoute($method, $id, $sub, $payload);
            break;
        default:
            json_error('Unbekannte Provision-Route', 404);
    }
}

// ═══════════════════════════════════════════════════════
// EMPLOYEES
// ═══════════════════════════════════════════════════════

function handleEmployeesRoute(string $method, ?string $id, array $payload): void {
    switch ($method) {
        case 'GET':
            if ($id && is_numeric($id)) {
                $emp = Database::queryOne('
                    SELECT e.*, m.name AS model_name, m.commission_rate AS model_rate,
                           tl.name AS teamleiter_name
                    FROM pm_employees e
                    LEFT JOIN pm_commission_models m ON e.commission_model_id = m.id
                    LEFT JOIN pm_employees tl ON e.teamleiter_id = tl.id
                    WHERE e.id = ?
                ', [(int)$id]);
                if (!$emp) { json_error('Mitarbeiter nicht gefunden', 404); return; }
                json_success(['employee' => $emp]);
                return;
            }
            $rows = Database::query('
                SELECT e.*, m.name AS model_name, m.commission_rate AS model_rate,
                       tl.name AS teamleiter_name
                FROM pm_employees e
                LEFT JOIN pm_commission_models m ON e.commission_model_id = m.id
                LEFT JOIN pm_employees tl ON e.teamleiter_id = tl.id
                ORDER BY e.role, e.name
            ');
            json_success(['employees' => $rows]);
            break;

        case 'POST':
            $data = get_json_body();
            require_fields($data, ['name', 'role']);
            if (!in_array($data['role'], ['consulter', 'teamleiter', 'backoffice'])) {
                json_error('Ungueltige Rolle', 400);
                return;
            }
            if (isset($data['commission_rate_override']) && $data['commission_rate_override'] !== null &&
                ($data['commission_rate_override'] < 0 || $data['commission_rate_override'] > 100)) {
                json_error('Rate muss zwischen 0 und 100 liegen', 400);
                return;
            }
            if (isset($data['tl_override_rate']) &&
                ($data['tl_override_rate'] < 0 || $data['tl_override_rate'] > 100)) {
                json_error('TL-Rate muss zwischen 0 und 100 liegen', 400);
                return;
            }
            if (isset($data['tl_override_basis']) &&
                !in_array($data['tl_override_basis'], ['berater_anteil', 'gesamt_courtage'])) {
                json_error('Ungueltige TL-Override-Basis', 400);
                return;
            }
            $newId = Database::insert(
                'INSERT INTO pm_employees (name, role, user_id, commission_model_id,
                    commission_rate_override, tl_override_rate, tl_override_basis,
                    teamleiter_id, notes)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                [
                    $data['name'],
                    $data['role'],
                    $data['user_id'] ?? null,
                    $data['commission_model_id'] ?? null,
                    $data['commission_rate_override'] ?? null,
                    $data['tl_override_rate'] ?? 0,
                    $data['tl_override_basis'] ?? 'berater_anteil',
                    $data['teamleiter_id'] ?? null,
                    $data['notes'] ?? null,
                ]
            );
            $created = Database::queryOne('SELECT * FROM pm_employees WHERE id = ?', [$newId]);
            logPmAction($payload, 'employee_created', 'pm_employee', $newId,
                "Mitarbeiter erstellt: {$data['name']} ({$data['role']})",
                ['name' => $data['name'], 'role' => $data['role']]);
            json_success(['employee' => $created], 'Mitarbeiter erstellt');
            break;

        case 'PUT':
            if (empty($id) || !is_numeric($id)) { json_error('ID erforderlich', 400); return; }
            $existing = Database::queryOne('SELECT * FROM pm_employees WHERE id = ?', [(int)$id]);
            if (!$existing) { json_error('Nicht gefunden', 404); return; }
            $data = get_json_body();

            if (isset($data['commission_rate_override']) && $data['commission_rate_override'] !== null &&
                ($data['commission_rate_override'] < 0 || $data['commission_rate_override'] > 100)) {
                json_error('Rate muss zwischen 0 und 100 liegen', 400);
                return;
            }
            if (isset($data['tl_override_rate']) &&
                ($data['tl_override_rate'] < 0 || $data['tl_override_rate'] > 100)) {
                json_error('TL-Rate muss zwischen 0 und 100 liegen', 400);
                return;
            }
            if (isset($data['tl_override_basis']) &&
                !in_array($data['tl_override_basis'], ['berater_anteil', 'gesamt_courtage'])) {
                json_error('Ungueltige TL-Override-Basis', 400);
                return;
            }
            if (isset($data['teamleiter_id']) && $data['teamleiter_id'] == (int)$id) {
                json_error('Mitarbeiter kann nicht sein eigener Teamleiter sein', 400);
                return;
            }
            if (isset($data['role']) && !in_array($data['role'], ['consulter', 'teamleiter', 'backoffice'])) {
                json_error('Ungueltige Rolle', 400);
                return;
            }

            $fields = ['name', 'role', 'user_id', 'commission_model_id',
                        'commission_rate_override', 'tl_override_rate', 'tl_override_basis',
                        'teamleiter_id', 'is_active', 'notes'];
            $sets = [];
            $params = [];
            foreach ($fields as $f) {
                if (array_key_exists($f, $data)) {
                    $sets[] = "$f = ?";
                    $params[] = $data[$f];
                }
            }
            if (empty($sets)) { json_error('Keine Aenderungen', 400); return; }
            $params[] = (int)$id;
            Database::execute('UPDATE pm_employees SET ' . implode(', ', $sets) . ' WHERE id = ?', $params);
            $updated = Database::queryOne('SELECT * FROM pm_employees WHERE id = ?', [(int)$id]);
            logPmAction($payload, 'employee_updated', 'pm_employee', (int)$id,
                "Mitarbeiter aktualisiert: {$existing['name']}", array_keys($data));

            $rateFields = ['commission_model_id', 'commission_rate_override', 'tl_override_rate', 'tl_override_basis', 'teamleiter_id'];
            $rateChanged = false;
            $changedFields = [];
            foreach ($rateFields as $rf) {
                if (!array_key_exists($rf, $data)) continue;
                $newVal = $data[$rf];
                $oldVal = $existing[$rf] ?? null;
                if ($newVal === null && $oldVal === null) continue;
                if ($newVal === null || $oldVal === null) { $rateChanged = true; $changedFields[] = $rf; continue; }
                if (is_numeric($newVal) && is_numeric($oldVal)) {
                    if ((float)$newVal !== (float)$oldVal) { $rateChanged = true; $changedFields[] = $rf; }
                } else {
                    if ((string)$newVal !== (string)$oldVal) { $rateChanged = true; $changedFields[] = $rf; }
                }
            }

            $recalcSummary = null;
            if ($rateChanged) {
                $fromDate = $data['gueltig_ab'] ?? null;
                $affectedIds = [(int)$id];

                if (array_key_exists('tl_override_rate', $data) || array_key_exists('tl_override_basis', $data)) {
                    $subordinates = Database::query('SELECT id FROM pm_employees WHERE teamleiter_id = ?', [(int)$id]);
                    foreach ($subordinates as $sub) {
                        $affectedIds[] = (int)$sub['id'];
                    }
                }

                $splitsRecalced = batchRecalculateSplits(null, $affectedIds, $fromDate);
                $abrResult = regenerateOpenAbrechnungen($affectedIds, $fromDate);

                $recalcSummary = [
                    'splits_recalculated' => $splitsRecalced,
                    'abrechnungen_regenerated' => $abrResult['abrechnungen_regenerated'],
                    'affected_employees' => count($affectedIds),
                    'from_date' => $fromDate,
                    'changed_fields' => $changedFields,
                ];
                logPmAction($payload, 'rate_recalculated', 'pm_employee', (int)$id,
                    "Neuberechnung nach Ratenänderung: {$splitsRecalced} Splits, {$abrResult['abrechnungen_regenerated']} Abrechnungen (Felder: " . implode(', ', $changedFields) . ")",
                    $recalcSummary);
            }

            $response = ['employee' => $updated];
            if ($recalcSummary) $response['recalc_summary'] = $recalcSummary;
            json_success($response, 'Aktualisiert');
            break;

        case 'DELETE':
            if (empty($id) || !is_numeric($id)) { json_error('ID erforderlich', 400); return; }
            $empId = (int)$id;
            $emp = Database::queryOne('SELECT name FROM pm_employees WHERE id = ?', [$empId]);
            if (!$emp) { json_error('Mitarbeiter nicht gefunden', 404); return; }

            $hard = ($_GET['hard'] ?? '') === '1';
            if ($hard) {
                $refCount = Database::queryOne(
                    'SELECT COUNT(*) AS cnt FROM pm_commissions WHERE berater_id = ?', [$empId]
                );
                if ((int)($refCount['cnt'] ?? 0) > 0) {
                    json_error('Mitarbeiter hat noch ' . $refCount['cnt'] . ' zugeordnete Provisionen. Bitte zuerst Zuordnungen entfernen.', 409);
                    return;
                }
                $contractRef = Database::queryOne(
                    'SELECT COUNT(*) AS cnt FROM pm_contracts WHERE berater_id = ?', [$empId]
                );
                if ((int)($contractRef['cnt'] ?? 0) > 0) {
                    Database::execute('UPDATE pm_contracts SET berater_id = NULL WHERE berater_id = ?', [$empId]);
                }
                Database::execute('DELETE FROM pm_vermittler_mapping WHERE berater_id = ?', [$empId]);
                Database::execute('DELETE FROM pm_employees WHERE id = ?', [$empId]);
                logPmAction($payload, 'employee_deleted', 'pm_employee', $empId,
                    "Mitarbeiter geloescht: " . $emp['name']);
                json_success([], 'Mitarbeiter geloescht');
            } else {
                Database::execute('UPDATE pm_employees SET is_active = 0 WHERE id = ?', [$empId]);
                logPmAction($payload, 'employee_deactivated', 'pm_employee', $empId,
                    "Mitarbeiter deaktiviert: " . $emp['name']);
                json_success([], 'Mitarbeiter deaktiviert');
            }
            break;

        default:
            json_error('Methode nicht erlaubt', 405);
    }
}

// ═══════════════════════════════════════════════════════
// CONTRACTS
// ═══════════════════════════════════════════════════════

function handleContractsRoute(string $method, ?string $id, array $payload): void {
    // GET /pm/contracts/unmatched -- Xempus-Vertraege ohne VU-Provision
    if ($method === 'GET' && $id === 'unmatched') {
        $where = 'cm.id IS NULL';
        $params = [];
        if (isset($_GET['von'])) {
            $where .= ' AND ct.created_at >= ?';
            $params[] = $_GET['von'];
        }
        if (isset($_GET['bis'])) {
            $where .= ' AND ct.created_at <= ?';
            $params[] = $_GET['bis'];
        }
        if (isset($_GET['q']) && strlen(trim($_GET['q'])) >= 2) {
            $q = '%' . trim($_GET['q']) . '%';
            $where .= ' AND (ct.vsnr LIKE ? OR ct.versicherungsnehmer LIKE ? OR ct.versicherer LIKE ?)';
            $params[] = $q;
            $params[] = $q;
            $params[] = $q;
        }

        $page = max(1, (int)($_GET['page'] ?? 1));
        $perPage = min(max(10, (int)($_GET['per_page'] ?? 50)), 200);
        $offset = ($page - 1) * $perPage;

        $countRow = Database::queryOne("
            SELECT COUNT(*) AS total
            FROM pm_contracts ct
            LEFT JOIN pm_commissions cm ON cm.contract_id = ct.id
            LEFT JOIN pm_employees e ON ct.berater_id = e.id
            WHERE $where
        ", $params);
        $total = (int)$countRow['total'];

        $rows = Database::query("
            SELECT ct.*, e.name AS berater_name,
                   ib.source_type, ib.vu_name
            FROM pm_contracts ct
            LEFT JOIN pm_commissions cm ON cm.contract_id = ct.id
            LEFT JOIN pm_employees e ON ct.berater_id = e.id
            LEFT JOIN pm_import_batches ib ON ct.import_batch_id = ib.id
            WHERE $where
            ORDER BY ct.created_at DESC
            LIMIT $perPage OFFSET $offset
        ", $params);

        json_success([
            'contracts' => $rows,
            'pagination' => [
                'page' => $page,
                'per_page' => $perPage,
                'total' => $total,
                'total_pages' => (int)ceil($total / $perPage),
            ],
        ]);
        return;
    }

    if ($method === 'GET') {
        $where = '1=1';
        $params = [];
        if (isset($_GET['berater_id'])) {
            $where .= ' AND c.berater_id = ?';
            $params[] = (int)$_GET['berater_id'];
        }
        if (isset($_GET['status'])) {
            $where .= ' AND c.status = ?';
            $params[] = $_GET['status'];
        }
        if (isset($_GET['q'])) {
            $where .= ' AND (c.vsnr LIKE ? OR c.versicherungsnehmer LIKE ?)';
            $q = '%' . $_GET['q'] . '%';
            $params[] = $q;
            $params[] = $q;
        }
        $limit = min((int)($_GET['limit'] ?? 500), 2000);
        $rows = Database::query("
            SELECT c.*, e.name AS berater_name,
                   (SELECT COUNT(*) FROM pm_commissions WHERE contract_id = c.id) AS provision_count,
                   (SELECT COALESCE(SUM(betrag), 0) FROM pm_commissions WHERE contract_id = c.id) AS provision_summe
            FROM pm_contracts c
            LEFT JOIN pm_employees e ON c.berater_id = e.id
            WHERE $where
            ORDER BY c.updated_at DESC
            LIMIT $limit
        ", $params);
        json_success(['contracts' => $rows]);
    } elseif ($method === 'PUT') {
        if (empty($id) || !is_numeric($id)) { json_error('ID erforderlich', 400); return; }
        $existing = Database::queryOne('SELECT * FROM pm_contracts WHERE id = ?', [(int)$id]);
        if (!$existing) { json_error('Nicht gefunden', 404); return; }
        $data = get_json_body();
        $fields = ['berater_id', 'status', 'notes', 'sparte', 'versicherungsnehmer'];
        $sets = [];
        $params = [];
        foreach ($fields as $f) {
            if (array_key_exists($f, $data)) {
                $sets[] = "$f = ?";
                $params[] = $data[$f];
            }
        }
        if (empty($sets)) { json_error('Keine Aenderungen', 400); return; }
        $params[] = (int)$id;
        Database::execute('UPDATE pm_contracts SET ' . implode(', ', $sets) . ' WHERE id = ?', $params);

        // Berater-Sync: Wenn berater_id geaendert wurde, alle Commissions synchronisieren
        if (array_key_exists('berater_id', $data)) {
            syncBeraterToCommissions((int)$id);
        }

        json_success([], 'Vertrag aktualisiert');
    } else {
        json_error('Methode nicht erlaubt', 405);
    }
}

// ═══════════════════════════════════════════════════════
// COMMISSIONS
// ═══════════════════════════════════════════════════════

function handleCommissionsRoute(string $method, ?string $id, ?string $sub, array $payload): void {
    if ($method === 'GET') {
        $where = '1=1';
        $params = [];
        if (isset($_GET['berater_id'])) {
            $where .= ' AND c.berater_id = ?';
            $params[] = (int)$_GET['berater_id'];
        }
        if (isset($_GET['match_status'])) {
            $where .= ' AND c.match_status = ?';
            $params[] = $_GET['match_status'];
        }
        if (isset($_GET['von'])) {
            $where .= ' AND c.auszahlungsdatum >= ?';
            $params[] = $_GET['von'];
        }
        if (isset($_GET['bis'])) {
            $where .= ' AND c.auszahlungsdatum <= ?';
            $params[] = $_GET['bis'];
        }
        if (isset($_GET['versicherer'])) {
            $where .= ' AND c.versicherer LIKE ?';
            $params[] = '%' . $_GET['versicherer'] . '%';
        }
        if (isset($_GET['q']) && strlen(trim($_GET['q'])) >= 2) {
            $q = '%' . trim($_GET['q']) . '%';
            $where .= ' AND (c.vsnr LIKE ? OR c.versicherungsnehmer LIKE ? OR c.versicherer LIKE ? OR c.vermittler_name LIKE ?)';
            $params[] = $q;
            $params[] = $q;
            $params[] = $q;
            $params[] = $q;
        }

        $usePagination = isset($_GET['page']);
        if ($usePagination) {
            $page = max(1, (int)$_GET['page']);
            $perPage = min(max(10, (int)($_GET['per_page'] ?? 50)), 200);
            $offset = ($page - 1) * $perPage;

            $countRow = Database::queryOne("SELECT COUNT(*) AS total FROM pm_commissions c WHERE $where", $params);
            $total = (int)$countRow['total'];

            $rows = Database::query("
                SELECT c.*, e.name AS berater_name,
                       ct.vsnr AS contract_vsnr,
                       ct.berater_name AS xempus_berater_name,
                       ib.source_type AS import_source_type,
                       ib.vu_name AS import_vu_name
                FROM pm_commissions c
                LEFT JOIN pm_employees e ON c.berater_id = e.id
                LEFT JOIN pm_contracts ct ON c.contract_id = ct.id
                LEFT JOIN pm_import_batches ib ON c.import_batch_id = ib.id
                WHERE $where
                ORDER BY c.auszahlungsdatum DESC, c.id DESC
                LIMIT $perPage OFFSET $offset
            ", $params);

            json_success([
                'commissions' => $rows,
                'pagination' => [
                    'page' => $page,
                    'per_page' => $perPage,
                    'total' => $total,
                    'total_pages' => (int)ceil($total / $perPage),
                ],
            ]);
        } else {
            $limit = min((int)($_GET['limit'] ?? 500), 5000);
            $rows = Database::query("
                SELECT c.*, e.name AS berater_name,
                       ct.vsnr AS contract_vsnr,
                       ct.berater_name AS xempus_berater_name,
                       ib.source_type AS import_source_type,
                       ib.vu_name AS import_vu_name
                FROM pm_commissions c
                LEFT JOIN pm_employees e ON c.berater_id = e.id
                LEFT JOIN pm_contracts ct ON c.contract_id = ct.id
                LEFT JOIN pm_import_batches ib ON c.import_batch_id = ib.id
                WHERE $where
                ORDER BY c.auszahlungsdatum DESC, c.id DESC
                LIMIT $limit
            ", $params);
            json_success(['commissions' => $rows]);
        }
        return;
    }

    if ($method === 'PUT' && $id && is_numeric($id) && $sub === 'match') {
        $data = get_json_body();
        $contractId = (int)($data['contract_id'] ?? 0);
        if (!$contractId) {
            json_error('contract_id erforderlich', 400);
            return;
        }
        $forceOverride = (bool)($data['force_override'] ?? false);

        $pdo = Database::getInstance();
        $pdo->beginTransaction();
        try {
            $totalAssigned = assignContractToCommission((int)$id, $contractId, $forceOverride);
            logPmAction($payload, 'commission_manual_match', 'pm_commission', (int)$id,
                "Provision manuell zugeordnet ($totalAssigned insgesamt)", ['contract_id' => $contractId, 'total_assigned' => $totalAssigned]);
            $pdo->commit();
            json_success(['total_assigned' => $totalAssigned], 'Manuell zugeordnet');
        } catch (\RuntimeException $e) {
            $pdo->rollBack();
            json_error($e->getMessage(), 409);
        } catch (\Throwable $e) {
            $pdo->rollBack();
            json_error('Zuordnung fehlgeschlagen: ' . $e->getMessage(), 500);
        }
        return;
    }

    if ($method === 'PUT' && $id && is_numeric($id) && $sub === 'ignore') {
        Database::execute(
            "UPDATE pm_commissions SET match_status = 'ignored' WHERE id = ?",
            [(int)$id]
        );
        logPmAction($payload, 'commission_ignored', 'pm_commission', (int)$id, "Provision ignoriert");
        json_success([], 'Ignoriert');
        return;
    }

    if ($method === 'POST' && $id === 'recalculate') {
        $count = batchRecalculateSplits();
        json_success(['recalculated' => $count], 'Neu berechnet');
        return;
    }

    json_error('Methode/Route nicht erlaubt', 405);
}

// ═══════════════════════════════════════════════════════
// IMPORT
// ═══════════════════════════════════════════════════════

function handleImportRoute(string $method, ?string $action, array $payload): void {
    if ($method === 'GET' && $action === 'batches') {
        $rows = Database::query('
            SELECT b.*, u.username AS imported_by_name
            FROM pm_import_batches b
            LEFT JOIN users u ON b.imported_by = u.id
            ORDER BY b.created_at DESC
            LIMIT 100
        ');
        json_success(['batches' => $rows]);
        return;
    }

    if ($method !== 'POST') json_error('Methode nicht erlaubt', 405);

    if ($action === 'vu-liste') {
        handleImportVuListe($payload);
        return;
    }
    if ($action === 'xempus') {
        handleImportXempus($payload);
        return;
    }
    if ($action === 'match') {
        $data = get_json_body();
        $batchId = $data['batch_id'] ?? null;
        $stats = autoMatchCommissions($batchId ? (int)$batchId : null);
        json_success(['stats' => $stats], 'Auto-Matching abgeschlossen');
        return;
    }
    json_error('Unbekannte Import-Route', 404);
}

function handleImportVuListe(array $payload): void {
    $data = get_json_body();
    require_fields($data, ['rows', 'filename']);

    $filename = $data['filename'];
    $fileHash = $data['file_hash'] ?? null;
    $sheetName = $data['sheet_name'] ?? null;
    $vuName = $data['vu_name'] ?? $sheetName;

    $batchId = null;
    if ($fileHash) {
        $existing = Database::queryOne(
            'SELECT id FROM pm_import_batches WHERE file_hash = ?
             AND (sheet_name = ? OR (sheet_name IS NULL AND ? IS NULL))',
            [$fileHash, $sheetName, $sheetName]
        );
        if ($existing) {
            $batchId = (int)$existing['id'];
        }
    }

    if (!$batchId) {
        $batchId = Database::insert(
            'INSERT INTO pm_import_batches (source_type, vu_name, filename, sheet_name, file_hash, imported_by)
             VALUES ("vu_liste", ?, ?, ?, ?, ?)',
            [$vuName, $filename, $sheetName, $fileHash, $payload['user_id']]
        );
    }

    $imported = 0;
    $skipped = 0;
    $errors = 0;

    // ── Batch-Duplikat-Check: alle row_hashes in 1 Query laden ──
    $existingHashes = [];
    $allHashes = [];
    foreach ($data['rows'] as $row) {
        $h = $row['row_hash'] ?? null;
        if ($h) $allHashes[] = $h;
    }
    if (!empty($allHashes)) {
        $chunks = array_chunk($allHashes, 500);
        foreach ($chunks as $chunk) {
            $ph = implode(',', array_fill(0, count($chunk), '?'));
            $found = Database::query("SELECT row_hash FROM pm_commissions WHERE row_hash IN ($ph)", $chunk);
            foreach ($found as $f) { $existingHashes[$f['row_hash']] = true; }
        }
    }

    // ── Zeilen vorbereiten (Validierung + Normalisierung in Memory) ──
    $insertBatch = [];
    foreach ($data['rows'] as $idx => $row) {
        try {
            $vsnr = trim((string)($row['vsnr'] ?? ''));
            if ($vsnr === '') { $skipped++; continue; }
            $vsnrNorm = normalizeVsnr($vsnr);
            $betrag = (float)($row['betrag'] ?? 0);
            // 0€-Zeilen werden als "nullmeldung" importiert (nicht mehr uebersprungen)
            $art = ($betrag === 0.0) ? 'nullmeldung' : ($row['art'] ?? 'ap');
            $datum = $row['auszahlungsdatum'] ?? null;
            $vermittlerName = trim((string)($row['vermittler_name'] ?? ''));
            $vermittlerNorm = $vermittlerName ? normalizeVermittlerName($vermittlerName) : null;
            $rowHash = $row['row_hash'] ?? null;

            if ($rowHash && isset($existingHashes[$rowHash])) {
                $skipped++;
                continue;
            }

            $courtageRate = isset($row['courtage_rate']) ? (float)$row['courtage_rate'] : null;
            $rateBelowThreshold = null;
            if ($courtageRate !== null && $vuName === 'Allianz') {
                $rateBelowThreshold = ($courtageRate < 20.0) ? 0 : 1;
            }

            $vnRaw = $row['versicherungsnehmer'] ?? null;
            $vnNorm = $vnRaw ? normalizeForDb($vnRaw) : null;

            $insertBatch[] = [
                $vsnr, $vsnrNorm, $betrag, $art,
                $datum, $vuName, $vnRaw, $vnNorm,
                $vermittlerName, $vermittlerNorm,
                $row['provisions_basissumme'] ?? null,
                $row['rate_nummer'] ?? null, $row['rate_anzahl'] ?? null,
                $batchId, $idx + 1, $rowHash,
                $courtageRate, $rateBelowThreshold,
            ];
        } catch (\Throwable $e) {
            $errors++;
            error_log("VU-Import Vorbereitung Zeile $idx: " . $e->getMessage());
        }
    }

    // ── Multi-Row INSERT (100 Zeilen pro Query) ──
    $colCount = 18;
    $colNames = '(vsnr, vsnr_normalized, betrag, art,
        auszahlungsdatum, versicherer, versicherungsnehmer, versicherungsnehmer_normalized,
        vermittler_name, vermittler_name_normalized,
        provisions_basissumme, rate_nummer, rate_anzahl,
        import_batch_id, source_row, row_hash,
        courtage_rate, rate_threshold_met)';
    $rowPh = '(' . implode(',', array_fill(0, $colCount, '?')) . ')';

    foreach (array_chunk($insertBatch, 100) as $chunk) {
        try {
            $allPh = implode(',', array_fill(0, count($chunk), $rowPh));
            $allVals = [];
            foreach ($chunk as $vals) {
                foreach ($vals as $v) { $allVals[] = $v; }
            }
            Database::execute(
                "INSERT INTO pm_commissions $colNames VALUES $allPh",
                $allVals
            );
            $imported += count($chunk);
        } catch (\Throwable $e) {
            $errors += count($chunk);
            error_log("VU-Import Batch-INSERT: " . $e->getMessage());
        }
    }

    Database::execute(
        'UPDATE pm_import_batches SET total_rows = ?, imported_rows = ?, skipped_rows = ?, error_rows = ? WHERE id = ?',
        [count($data['rows']), $imported, $skipped, $errors, $batchId]
    );

    $skipMatch = (bool)($data['skip_match'] ?? false);
    $matchStats = ['matched' => 0, 'berater_resolved' => 0, 'splits_calculated' => 0, 'still_unmatched' => 0];
    if (!$skipMatch) {
        try {
            $matchStats = autoMatchCommissions($batchId);
            Database::execute(
                'UPDATE pm_import_batches SET matched_rows = ? WHERE id = ?',
                [$matchStats['matched'], $batchId]
            );
        } catch (\Throwable $e) {
            error_log("autoMatchCommissions fehlgeschlagen (Batch $batchId): " . $e->getMessage());
        }
    }

    logPmAction($payload, 'import_vu_liste', 'pm_import_batch', $batchId,
        "VU-Import: $vuName – $imported importiert, " . $matchStats['matched'] . " zugeordnet",
        ['vu_name' => $vuName, 'filename' => $filename, 'imported' => $imported,
         'skipped' => $skipped, 'errors' => $errors, 'matching' => $matchStats]);

    json_success([
        'batch_id' => $batchId,
        'imported' => $imported,
        'skipped' => $skipped,
        'errors' => $errors,
        'matching' => $matchStats,
    ], 'VU-Import abgeschlossen');
}

function handleImportXempus(array $payload): void {
    $data = get_json_body();
    require_fields($data, ['rows', 'filename']);

    $filename = $data['filename'];
    $fileHash = $data['file_hash'] ?? null;

    $batchId = Database::insert(
        'INSERT INTO pm_import_batches (source_type, filename, file_hash, imported_by)
         VALUES ("xempus", ?, ?, ?)',
        [$filename, $fileHash, $payload['user_id']]
    );

    $imported = 0;
    $updated = 0;
    $skipped = 0;
    $errors = 0;
    $vsnrNachgetragen = 0;

    // ── Batch-Lookups: Bestehende Vertraege + Mappings in wenigen Queries laden ──

    // 1. Alle xempus_ids aus diesem Chunk sammeln
    $chunkXempusIds = [];
    $chunkVsnrs = [];
    $chunkVsnrNorms = [];
    foreach ($data['rows'] as $row) {
        $xid = trim((string)($row['xempus_id'] ?? ''));
        if ($xid) $chunkXempusIds[] = $xid;
        $v = trim((string)($row['vsnr'] ?? ''));
        if ($v) {
            $chunkVsnrs[] = $v;
            $chunkVsnrNorms[] = normalizeVsnr($v);
        }
    }

    // 2. Bestehende Vertraege per xempus_id laden (1 Query)
    $existingByXempusId = [];
    if (!empty($chunkXempusIds)) {
        $ph = implode(',', array_fill(0, count($chunkXempusIds), '?'));
        $rows = Database::query("SELECT id, vsnr, xempus_id FROM pm_contracts WHERE xempus_id IN ($ph)", $chunkXempusIds);
        foreach ($rows as $r) { $existingByXempusId[$r['xempus_id']] = $r; }
    }

    // 3. Bestehende Vertraege per VSNR laden (1 Query)
    $existingByVsnr = [];
    $allVsnrSearch = array_unique(array_merge($chunkVsnrs, $chunkVsnrNorms));
    if (!empty($allVsnrSearch)) {
        $ph = implode(',', array_fill(0, count($allVsnrSearch), '?'));
        $rows = Database::query("SELECT id, vsnr, vsnr_normalized, xempus_id FROM pm_contracts WHERE vsnr IN ($ph) OR vsnr_normalized IN ($ph)",
            array_merge($allVsnrSearch, $allVsnrSearch));
        foreach ($rows as $r) {
            if ($r['vsnr']) $existingByVsnr[$r['vsnr']] = $r;
            if ($r['vsnr_normalized']) $existingByVsnr[$r['vsnr_normalized']] = $r;
        }
    }

    // 4. Alle Vermittler-Mappings laden (1 Query, wenige Eintraege)
    $allMappings = [];
    $mappingRows = Database::query('SELECT vermittler_name_normalized, berater_id FROM pm_vermittler_mapping');
    foreach ($mappingRows as $m) { $allMappings[$m['vermittler_name_normalized']] = (int)$m['berater_id']; }

    // ── Zeilen klassifizieren: INSERT vs UPDATE ──
    $insertBatch = [];
    $updateBatch = [];

    foreach ($data['rows'] as $idx => $row) {
        try {
            $vsnr = trim((string)($row['vsnr'] ?? ''));
            $xempusId = trim((string)($row['xempus_id'] ?? ''));

            if ($vsnr === '') { $skipped++; continue; }

            $vsnrNorm = $vsnr ? normalizeVsnr($vsnr) : null;
            $beraterName = trim((string)($row['berater'] ?? ''));

            $vnRaw = $row['versicherungsnehmer'] ?? null;
            $vnNorm = $vnRaw ? normalizeForDb($vnRaw) : null;

            // Lookup aus vorgeladenen Maps
            $existing = null;
            if ($xempusId && isset($existingByXempusId[$xempusId])) {
                $existing = $existingByXempusId[$xempusId];
            }
            if (!$existing && $vsnr) {
                if (isset($existingByVsnr[$vsnr])) {
                    $existing = $existingByVsnr[$vsnr];
                } elseif ($vsnrNorm && isset($existingByVsnr[$vsnrNorm])) {
                    $existing = $existingByVsnr[$vsnrNorm];
                }
            }

            $beraterId = null;
            if ($beraterName) {
                $beraterNorm = normalizeVermittlerName($beraterName);
                $beraterId = $allMappings[$beraterNorm] ?? null;
            }

            if ($existing) {
                $updateBatch[] = [
                    'id' => (int)$existing['id'],
                    'hadVsnr' => !empty($existing['vsnr']),
                    'vsnr' => $vsnr ?: null,
                    'vsnrNorm' => $vsnrNorm ?: null,
                    'versicherer' => $row['versicherer'] ?? null,
                    'vnRaw' => $vnRaw, 'vnNorm' => $vnNorm,
                    'sparte' => $row['sparte'] ?? null,
                    'tarif' => $row['tarif'] ?? null,
                    'beitrag' => $row['beitrag'] ?? null,
                    'beginn' => $row['beginn'] ?? null,
                    'beraterId' => $beraterId,
                    'beraterName' => $beraterName ?: null,
                    'status' => $row['status'] ?? null,
                    'xempusId' => $xempusId ?: null,
                ];
            } else {
                $insertBatch[] = [
                    $vsnr ?: null, $vsnrNorm,
                    $row['versicherer'] ?? null, $vnRaw, $vnNorm,
                    $row['sparte'] ?? null, $row['tarif'] ?? null,
                    $row['beitrag'] ?? null, $row['beginn'] ?? null,
                    $beraterId, $beraterName ?: null,
                    $row['status'] ?? 'offen',
                    'xempus', $xempusId ?: null, $batchId,
                ];
            }
        } catch (\Throwable $e) {
            $errors++;
            error_log("Xempus-Import Vorbereitung Zeile $idx: " . $e->getMessage());
        }
    }

    // ── Batch-INSERTs (100 Zeilen pro Query) ──
    $insertColCount = 15;
    $insertColNames = '(vsnr, vsnr_normalized, versicherer,
        versicherungsnehmer, versicherungsnehmer_normalized,
        sparte, tarif, beitrag, beginn,
        berater_id, berater_name, status, source, xempus_id, import_batch_id)';
    $insertRowPh = '(' . implode(',', array_fill(0, $insertColCount, '?')) . ')';

    foreach (array_chunk($insertBatch, 100) as $chunk) {
        try {
            $allPh = implode(',', array_fill(0, count($chunk), $insertRowPh));
            $allVals = [];
            foreach ($chunk as $vals) {
                foreach ($vals as $v) { $allVals[] = $v; }
            }
            Database::execute(
                "INSERT INTO pm_contracts $insertColNames VALUES $allPh",
                $allVals
            );
            $imported += count($chunk);
        } catch (\Throwable $e) {
            $errors += count($chunk);
            error_log("Xempus Batch-INSERT: " . $e->getMessage());
        }
    }

    // ── UPDATEs einzeln (unterschiedliche Werte pro Zeile) ──
    foreach ($updateBatch as $u) {
        try {
            Database::execute(
                'UPDATE pm_contracts SET
                    vsnr = COALESCE(?, vsnr),
                    vsnr_normalized = COALESCE(?, vsnr_normalized),
                    versicherer = COALESCE(?, versicherer),
                    versicherungsnehmer = COALESCE(?, versicherungsnehmer),
                    versicherungsnehmer_normalized = COALESCE(?, versicherungsnehmer_normalized),
                    sparte = COALESCE(?, sparte), tarif = COALESCE(?, tarif),
                    beitrag = COALESCE(?, beitrag), beginn = COALESCE(?, beginn),
                    berater_id = COALESCE(?, berater_id),
                    berater_name = COALESCE(?, berater_name),
                    status = COALESCE(?, status),
                    xempus_id = COALESCE(?, xempus_id),
                    import_batch_id = ?
                 WHERE id = ?',
                [
                    $u['vsnr'], $u['vsnrNorm'],
                    $u['versicherer'], $u['vnRaw'], $u['vnNorm'],
                    $u['sparte'], $u['tarif'],
                    $u['beitrag'], $u['beginn'],
                    $u['beraterId'], $u['beraterName'],
                    $u['status'],
                    $u['xempusId'],
                    $batchId, $u['id'],
                ]
            );
            if ($u['vsnr'] && !$u['hadVsnr']) { $vsnrNachgetragen++; }
            $updated++;
        } catch (\Throwable $e) {
            $errors++;
            error_log("Xempus-Update ID {$u['id']}: " . $e->getMessage());
        }
    }

    Database::execute(
        'UPDATE pm_import_batches SET total_rows = ?, imported_rows = ?, skipped_rows = ?, error_rows = ?,
            notes = ? WHERE id = ?',
        [count($data['rows']), $imported, $skipped, $errors,
         "Aktualisiert: $updated", $batchId]
    );

    logPmAction($payload, 'import_xempus', 'pm_import_batch', $batchId,
        "Xempus-Import: $imported neu, $updated aktualisiert",
        ['filename' => $filename, 'imported' => $imported, 'updated' => $updated,
         'skipped' => $skipped, 'errors' => $errors]);

    $matchStats = null;
    try {
        $matchStats = autoMatchCommissions($batchId);
    } catch (\Throwable $e) {
        error_log("autoMatchCommissions fehlgeschlagen (Xempus-Batch $batchId): " . $e->getMessage());
    }

    json_success([
        'batch_id' => $batchId,
        'imported' => $imported,
        'updated' => $updated,
        'skipped' => $skipped,
        'errors' => $errors,
        'match_stats' => $matchStats,
    ], 'Xempus-Import abgeschlossen');
}

// ═══════════════════════════════════════════════════════
// DASHBOARD
// ═══════════════════════════════════════════════════════

function handleDashboardRoute(string $method, ?string $action, ?string $sub, array $payload): void {
    if ($method !== 'GET') json_error('Methode nicht erlaubt', 405);

    if ($action === 'summary') {
        $dateFilter = '';
        $dateFilterAliased = '';
        $dateParams = [];
        $allMode = false;

        if (isset($_GET['von']) && isset($_GET['bis'])) {
            $monatStart = $_GET['von'];
            $monatEnd = $_GET['bis'];
            $monat = substr($monatStart, 0, 7);
            $dateFilter = 'AND auszahlungsdatum BETWEEN ? AND ?';
            $dateFilterAliased = 'AND c.auszahlungsdatum BETWEEN ? AND ?';
            $dateParams = [$monatStart, $monatEnd];
        } elseif (isset($_GET['monat'])) {
            $monat = $_GET['monat'];
            $monatStart = $monat . '-01';
            $monatEnd = date('Y-m-t', strtotime($monatStart));
            $dateFilter = 'AND auszahlungsdatum BETWEEN ? AND ?';
            $dateFilterAliased = 'AND c.auszahlungsdatum BETWEEN ? AND ?';
            $dateParams = [$monatStart, $monatEnd];
        } else {
            $monat = date('Y-m');
            $allMode = true;
        }

        $jahrStart = substr($monat, 0, 4) . '-01-01';

        $monatStats = Database::queryOne("
            SELECT
                COALESCE(SUM(CASE WHEN betrag > 0 THEN betrag ELSE 0 END), 0) AS eingang_monat,
                COALESCE(SUM(CASE WHEN betrag < 0 THEN betrag ELSE 0 END), 0) AS rueckbelastung_monat,
                COALESCE(SUM(CASE WHEN betrag > 0 THEN ag_anteil ELSE 0 END), 0) AS ag_monat,
                COALESCE(SUM(CASE WHEN betrag > 0 THEN berater_anteil ELSE 0 END), 0) AS berater_monat,
                COALESCE(SUM(CASE WHEN betrag > 0 THEN tl_anteil ELSE 0 END), 0) AS tl_monat
            FROM pm_commissions
            WHERE match_status IN ('auto_matched','manual_matched')
              $dateFilter
        ", $dateParams);

        $matchCounts = Database::queryOne("
            SELECT
                COUNT(*) AS total_positions,
                SUM(CASE WHEN match_status IN ('auto_matched','manual_matched') THEN 1 ELSE 0 END) AS matched_positions
            FROM pm_commissions
            WHERE match_status != 'ignored'
              $dateFilter
        ", $dateParams);

        if ($allMode) {
            $ytdStats = $monatStats;
        } else {
            $ytdStats = Database::queryOne("
                SELECT
                    COALESCE(SUM(CASE WHEN betrag > 0 THEN betrag ELSE 0 END), 0) AS eingang_ytd,
                    COALESCE(SUM(CASE WHEN betrag < 0 THEN betrag ELSE 0 END), 0) AS rueckbelastung_ytd
                FROM pm_commissions
                WHERE match_status IN ('auto_matched','manual_matched')
                  AND auszahlungsdatum BETWEEN ? AND ?
            ", [$jahrStart, $monatEnd]);
        }

        $unmatched = Database::queryOne(
            "SELECT COUNT(*) AS cnt FROM pm_commissions WHERE match_status = 'unmatched'"
        );

        $perBerater = Database::query("
            SELECT e.id, e.name, e.role,
                COALESCE(SUM(CASE WHEN c.betrag > 0 THEN c.betrag ELSE 0 END), 0) AS brutto,
                COALESCE(SUM(CASE WHEN c.betrag > 0 THEN c.berater_anteil ELSE 0 END), 0) AS berater_netto,
                COALESCE(SUM(CASE WHEN c.betrag > 0 THEN c.tl_anteil ELSE 0 END), 0) AS tl_abzug,
                COALESCE(SUM(CASE WHEN c.betrag > 0 THEN c.ag_anteil ELSE 0 END), 0) AS ag_anteil,
                COALESCE(SUM(CASE WHEN c.betrag < 0 THEN c.berater_anteil ELSE 0 END), 0) AS rueckbelastung
            FROM pm_employees e
            LEFT JOIN pm_commissions c ON c.berater_id = e.id
                AND c.match_status IN ('auto_matched','manual_matched')
                $dateFilterAliased
            WHERE e.is_active = 1 AND e.role IN ('consulter','teamleiter')
            GROUP BY e.id, e.name, e.role
            ORDER BY brutto DESC
        ", $dateParams);

        json_success([
            'monat' => $monat,
            'eingang_monat' => (float)$monatStats['eingang_monat'],
            'rueckbelastung_monat' => (float)$monatStats['rueckbelastung_monat'],
            'ag_monat' => (float)$monatStats['ag_monat'],
            'berater_monat' => (float)$monatStats['berater_monat'],
            'tl_monat' => (float)$monatStats['tl_monat'],
            'eingang_ytd' => (float)($ytdStats['eingang_ytd'] ?? $ytdStats['eingang_monat'] ?? 0),
            'rueckbelastung_ytd' => (float)($ytdStats['rueckbelastung_ytd'] ?? $ytdStats['rueckbelastung_monat'] ?? 0),
            'unmatched_count' => (int)$unmatched['cnt'],
            'total_positions' => (int)($matchCounts['total_positions'] ?? 0),
            'matched_positions' => (int)($matchCounts['matched_positions'] ?? 0),
            'per_berater' => array_map(function($b) {
                return [
                    'id' => (int)$b['id'],
                    'name' => $b['name'],
                    'role' => $b['role'],
                    'brutto' => (float)$b['brutto'],
                    'berater_netto' => (float)$b['berater_netto'],
                    'tl_abzug' => (float)$b['tl_abzug'],
                    'ag_anteil' => (float)$b['ag_anteil'],
                    'rueckbelastung' => (float)$b['rueckbelastung'],
                ];
            }, $perBerater),
        ]);
        return;
    }

    if ($action === 'berater' && $sub && is_numeric($sub)) {
        $beraterId = (int)$sub;
        $emp = Database::queryOne('SELECT * FROM pm_employees WHERE id = ?', [$beraterId]);
        if (!$emp) json_error('Berater nicht gefunden', 404);

        $bDateFilter = '';
        $bDateParams = [];
        if (isset($_GET['von']) && isset($_GET['bis'])) {
            $bDateFilter = 'AND c.auszahlungsdatum BETWEEN ? AND ?';
            $bDateParams = [$_GET['von'], $_GET['bis']];
            $monat = substr($_GET['von'], 0, 7);
        } elseif (isset($_GET['monat'])) {
            $monat = $_GET['monat'];
            $ms = $monat . '-01';
            $me = date('Y-m-t', strtotime($ms));
            $bDateFilter = 'AND c.auszahlungsdatum BETWEEN ? AND ?';
            $bDateParams = [$ms, $me];
        } else {
            $monat = date('Y-m');
        }

        $agg = Database::queryOne("
            SELECT
                COALESCE(SUM(CASE WHEN c.betrag > 0 THEN c.betrag ELSE 0 END), 0) AS brutto,
                COALESCE(SUM(CASE WHEN c.betrag > 0 THEN c.berater_anteil ELSE 0 END), 0) AS netto,
                COALESCE(SUM(CASE WHEN c.betrag > 0 THEN c.tl_anteil ELSE 0 END), 0) AS tl_abzug,
                COALESCE(SUM(CASE WHEN c.betrag > 0 THEN c.ag_anteil ELSE 0 END), 0) AS ag_anteil,
                COALESCE(SUM(CASE WHEN c.betrag < 0 THEN c.berater_anteil ELSE 0 END), 0) AS rueckbelastung,
                COUNT(*) AS positions_count
            FROM pm_commissions c
            WHERE c.berater_id = ?
              AND c.match_status IN ('auto_matched','manual_matched')
              $bDateFilter
        ", array_merge([$beraterId], $bDateParams));

        $commissions = Database::query("
            SELECT c.*, ct.vsnr AS contract_vsnr, ct.versicherungsnehmer AS contract_vn
            FROM pm_commissions c
            LEFT JOIN pm_contracts ct ON c.contract_id = ct.id
            WHERE c.berater_id = ?
              AND c.match_status IN ('auto_matched','manual_matched')
              $bDateFilter
            ORDER BY c.auszahlungsdatum DESC
            LIMIT 200
        ", array_merge([$beraterId], $bDateParams));

        json_success([
            'employee' => $emp,
            'monat' => $monat,
            'brutto' => (float)$agg['brutto'],
            'netto' => (float)$agg['netto'],
            'tl_abzug' => (float)$agg['tl_abzug'],
            'ag_anteil' => (float)$agg['ag_anteil'],
            'rueckbelastung' => (float)$agg['rueckbelastung'],
            'positions_count' => (int)$agg['positions_count'],
            'commissions' => $commissions,
        ]);
        return;
    }

    json_error('Unbekannte Dashboard-Route', 404);
}

// ═══════════════════════════════════════════════════════
// MAPPINGS
// ═══════════════════════════════════════════════════════

function handleMappingsRoute(string $method, ?string $id, array $payload): void {
    if ($method === 'GET') {
        $mappings = Database::query('
            SELECT m.*, e.name AS berater_name
            FROM pm_vermittler_mapping m
            LEFT JOIN pm_employees e ON m.berater_id = e.id
            ORDER BY m.vermittler_name
        ');

        $unmapped = [];
        if (isset($_GET['include_unmapped']) && $_GET['include_unmapped'] === '1') {
            $unmapped = Database::query("
                SELECT DISTINCT c.vermittler_name
                FROM pm_commissions c
                WHERE c.vermittler_name IS NOT NULL
                  AND c.vermittler_name != ''
                  AND c.vermittler_name_normalized NOT IN (
                      SELECT vermittler_name_normalized FROM pm_vermittler_mapping
                  )
                ORDER BY c.vermittler_name
            ");
        }

        json_success(['mappings' => $mappings, 'unmapped' => $unmapped]);
        return;
    }

    if ($method === 'POST') {
        $data = get_json_body();
        require_fields($data, ['vermittler_name', 'berater_id']);
        $name = trim($data['vermittler_name']);
        $norm = normalizeVermittlerName($name);

        $existing = Database::queryOne(
            'SELECT id, berater_id FROM pm_vermittler_mapping WHERE vermittler_name = ? OR vermittler_name_normalized = ?',
            [$name, $norm]
        );
        $newBeraterId = (int)$data['berater_id'];

        if ($existing) {
            Database::execute(
                'UPDATE pm_vermittler_mapping SET berater_id = ? WHERE id = ?',
                [$newBeraterId, (int)$existing['id']]
            );
            logPmAction($payload, 'mapping_updated', 'pm_mapping', (int)$existing['id'],
                "Vermittler-Zuordnung aktualisiert: $name", ['vermittler_name' => $name, 'berater_id' => $newBeraterId]);
            $mappingId = (int)$existing['id'];
        } else {
            $mappingId = Database::insert(
                'INSERT INTO pm_vermittler_mapping (vermittler_name, vermittler_name_normalized, berater_id)
                 VALUES (?, ?, ?)',
                [$name, $norm, $newBeraterId]
            );
            logPmAction($payload, 'mapping_created', 'pm_mapping', $mappingId,
                "Vermittler-Zuordnung erstellt: $name", ['vermittler_name' => $name, 'berater_id' => $newBeraterId]);
        }

        // Sync passiert im Client via trigger_auto_match() (120s Timeout)
        $action = $existing ? 'aktualisiert' : 'erstellt';
        json_success(['id' => $mappingId], "Zuordnung $action");
        return;
    }

    if ($method === 'DELETE') {
        if (empty($id) || !is_numeric($id)) json_error('ID erforderlich', 400);
        $old = Database::queryOne('SELECT vermittler_name FROM pm_vermittler_mapping WHERE id = ?', [(int)$id]);
        Database::execute('DELETE FROM pm_vermittler_mapping WHERE id = ?', [(int)$id]);
        logPmAction($payload, 'mapping_deleted', 'pm_mapping', (int)$id,
            "Vermittler-Zuordnung geloescht: " . ($old['vermittler_name'] ?? ''));
        json_success([], 'Zuordnung geloescht');
        return;
    }

    json_error('Methode nicht erlaubt', 405);
}

// ═══════════════════════════════════════════════════════
// ABRECHNUNGEN
// ═══════════════════════════════════════════════════════

function handleAbrechnungenRoute(string $method, ?string $id, array $payload): void {
    if ($method === 'GET') {
        $monat = $_GET['monat'] ?? null;
        $where = '1=1';
        $params = [];
        if ($monat) {
            $where .= ' AND a.abrechnungsmonat = ?';
            $params[] = $monat . '-01';
        }
        $rows = Database::query("
            SELECT sub.*
            FROM (
                SELECT a.*, e.name AS berater_name, e.role AS berater_role,
                       ROW_NUMBER() OVER (PARTITION BY a.abrechnungsmonat, a.berater_id ORDER BY a.revision DESC) AS rn
                FROM pm_berater_abrechnungen a
                INNER JOIN pm_employees e ON a.berater_id = e.id
                WHERE $where
            ) sub
            WHERE sub.rn = 1
            ORDER BY sub.abrechnungsmonat DESC, sub.berater_name
        ", $params);
        json_success(['abrechnungen' => $rows]);
        return;
    }

    if ($method === 'POST') {
        $data = get_json_body();
        require_fields($data, ['monat']);
        $monat = $data['monat'] . '-01';
        $monatEnd = date('Y-m-t', strtotime($monat));

        $berater = Database::query("
            SELECT id FROM pm_employees WHERE is_active = 1 AND role IN ('consulter','teamleiter')
        ");

        $generated = 0;
        foreach ($berater as $b) {
            $beraterId = (int)$b['id'];

            $stats = Database::queryOne("
                SELECT
                    COALESCE(SUM(CASE WHEN betrag > 0 THEN berater_anteil ELSE 0 END), 0) AS brutto,
                    COALESCE(SUM(CASE WHEN betrag > 0 THEN tl_anteil ELSE 0 END), 0) AS tl_abzug,
                    COALESCE(SUM(CASE WHEN betrag < 0 THEN berater_anteil ELSE 0 END), 0) AS rueckbelastungen,
                    COUNT(*) AS anzahl
                FROM pm_commissions
                WHERE berater_id = ?
                  AND match_status IN ('auto_matched','manual_matched')
                  AND auszahlungsdatum BETWEEN ? AND ?
            ", [$beraterId, $monat, $monatEnd]);

            $brutto = (float)$stats['brutto'];
            $tlAbzug = (float)$stats['tl_abzug'];
            $rueckbelastungen = (float)$stats['rueckbelastungen'];
            $netto = round($brutto - $tlAbzug, 2);
            $auszahlung = round($netto + $rueckbelastungen, 2);

            Database::insert(
                'INSERT INTO pm_berater_abrechnungen (abrechnungsmonat, berater_id, revision,
                    brutto_provision, tl_abzug, netto_provision, rueckbelastungen,
                    auszahlung, anzahl_provisionen, status)
                 SELECT ?, ?, COALESCE(MAX(a2.revision), 0) + 1,
                    ?, ?, ?, ?, ?, ?, "berechnet"
                 FROM pm_berater_abrechnungen a2
                 WHERE a2.abrechnungsmonat = ? AND a2.berater_id = ?',
                [$monat, $beraterId, $brutto, $tlAbzug, $netto,
                 $rueckbelastungen, $auszahlung, (int)$stats['anzahl'],
                 $monat, $beraterId]
            );
            $generated++;
        }

        logPmAction($payload, 'abrechnung_generated', 'pm_abrechnung', null,
            "Abrechnungen generiert fuer {$data['monat']}: $generated Berater",
            ['monat' => $data['monat'], 'generated' => $generated]);
        json_success(['generated' => $generated, 'monat' => $data['monat']], 'Abrechnungen generiert');
        return;
    }

    if ($method === 'PUT' && $id && is_numeric($id)) {
        $data = get_json_body();
        $existing = Database::queryOne('SELECT * FROM pm_berater_abrechnungen WHERE id = ?', [(int)$id]);
        if (!$existing) { json_error('Nicht gefunden', 404); return; }
        if ((int)$existing['is_locked']) { json_error('Abrechnung ist gesperrt', 403); return; }

        $newStatus = $data['status'] ?? null;
        if (!$newStatus || !in_array($newStatus, ['berechnet', 'geprueft', 'freigegeben', 'ausgezahlt'])) {
            json_error('Ungueltiger Status', 400);
            return;
        }

        $allowedTransitions = [
            'berechnet'   => ['geprueft'],
            'geprueft'    => ['berechnet', 'freigegeben'],
            'freigegeben' => ['geprueft', 'ausgezahlt'],
            'ausgezahlt'  => [],
        ];
        $currentStatus = $existing['status'] ?? 'berechnet';
        if (!in_array($newStatus, $allowedTransitions[$currentStatus] ?? [])) {
            json_error("Statusuebergang von '$currentStatus' nach '$newStatus' nicht erlaubt", 400);
            return;
        }

        $sets = ['status = ?'];
        $params = [$newStatus];

        if ($newStatus === 'geprueft') {
            $sets[] = 'geprueft_von = ?';
            $params[] = $payload['user_id'];
        }
        if ($newStatus === 'freigegeben') {
            $sets[] = 'freigegeben_von = ?';
            $sets[] = 'freigegeben_am = NOW()';
            $sets[] = 'is_locked = 1';
            $params[] = $payload['user_id'];
        }
        $params[] = (int)$id;
        Database::execute(
            'UPDATE pm_berater_abrechnungen SET ' . implode(', ', $sets) . ' WHERE id = ?',
            $params
        );
        logPmAction($payload, 'abrechnung_status_changed', 'pm_abrechnung', (int)$id,
            "Abrechnungs-Status geaendert: {$existing['status']} → $newStatus",
            ['old_status' => $existing['status'], 'new_status' => $newStatus,
             'berater_id' => (int)$existing['berater_id']]);
        json_success([], 'Status aktualisiert');
        return;
    }

    json_error('Methode nicht erlaubt', 405);
}

// ═══════════════════════════════════════════════════════
// COMMISSION MODELS
// ═══════════════════════════════════════════════════════

function handleModelsRoute(string $method, ?string $id, array $payload): void {
    if ($method === 'GET') {
        $rows = Database::query('SELECT * FROM pm_commission_models ORDER BY name');
        json_success(['models' => $rows]);
        return;
    }
    if ($method === 'POST') {
        $data = get_json_body();
        require_fields($data, ['name', 'commission_rate']);
        if (isset($data['tl_rate']) && $data['tl_rate'] !== null && ($data['tl_rate'] < 0 || $data['tl_rate'] > 100)) {
            json_error('TL-Rate muss zwischen 0 und 100 liegen', 400); return;
        }
        if (isset($data['tl_basis']) && $data['tl_basis'] !== null && !in_array($data['tl_basis'], ['berater_anteil', 'gesamt_courtage'])) {
            json_error('Ungueltige TL-Basis', 400); return;
        }
        $newId = Database::insert(
            'INSERT INTO pm_commission_models (name, description, commission_rate, tl_rate, tl_basis) VALUES (?, ?, ?, ?, ?)',
            [$data['name'], $data['description'] ?? null, (float)$data['commission_rate'],
             isset($data['tl_rate']) ? (float)$data['tl_rate'] : null,
             $data['tl_basis'] ?? null]
        );
        $created = Database::queryOne('SELECT * FROM pm_commission_models WHERE id = ?', [$newId]);
        json_success(['model' => $created], 'Modell erstellt');
        return;
    }
    if ($method === 'PUT' && $id && is_numeric($id)) {
        $existing = Database::queryOne('SELECT * FROM pm_commission_models WHERE id = ?', [(int)$id]);
        if (!$existing) { json_error('Modell nicht gefunden', 404); return; }
        $data = get_json_body();
        if (isset($data['tl_rate']) && $data['tl_rate'] !== null && ($data['tl_rate'] < 0 || $data['tl_rate'] > 100)) {
            json_error('TL-Rate muss zwischen 0 und 100 liegen', 400); return;
        }
        if (isset($data['tl_basis']) && $data['tl_basis'] !== null && !in_array($data['tl_basis'], ['berater_anteil', 'gesamt_courtage'])) {
            json_error('Ungueltige TL-Basis', 400); return;
        }
        $fields = ['name', 'description', 'commission_rate', 'tl_rate', 'tl_basis', 'is_active'];
        $sets = [];
        $params = [];
        foreach ($fields as $f) {
            if (array_key_exists($f, $data)) {
                $sets[] = "$f = ?";
                $params[] = $data[$f];
            }
        }
        if (empty($sets)) { json_error('Keine Aenderungen', 400); return; }
        $params[] = (int)$id;
        Database::execute('UPDATE pm_commission_models SET ' . implode(', ', $sets) . ' WHERE id = ?', $params);

        $rateFieldsCheck = ['commission_rate', 'tl_rate', 'tl_basis'];
        $rateChanged = false;
        foreach ($rateFieldsCheck as $rf) {
            if (!array_key_exists($rf, $data)) continue;
            $newVal = $data[$rf];
            $oldVal = $existing[$rf] ?? null;
            if ($newVal === null && $oldVal === null) continue;
            if ($newVal === null || $oldVal === null) { $rateChanged = true; break; }
            if (is_numeric($newVal) && is_numeric($oldVal)) {
                if ((float)$newVal !== (float)$oldVal) { $rateChanged = true; break; }
            } else {
                if ((string)$newVal !== (string)$oldVal) { $rateChanged = true; break; }
            }
        }

        $recalcSummary = null;
        if ($rateChanged) {
            $fromDate = $data['gueltig_ab'] ?? null;
            $empRows = Database::query(
                'SELECT id FROM pm_employees WHERE commission_model_id = ? AND is_active = 1',
                [(int)$id]
            );
            $affectedIds = array_map(fn($r) => (int)$r['id'], $empRows);

            if (!empty($affectedIds)) {
                $splitsRecalced = batchRecalculateSplits(null, $affectedIds, $fromDate);
                $abrResult = regenerateOpenAbrechnungen($affectedIds, $fromDate);

                $recalcSummary = [
                    'splits_recalculated' => $splitsRecalced,
                    'abrechnungen_regenerated' => $abrResult['abrechnungen_regenerated'],
                    'affected_employees' => count($affectedIds),
                    'from_date' => $fromDate,
                ];
                logPmAction($payload, 'model_rate_recalculated', 'pm_commission_model', (int)$id,
                    "Neuberechnung nach Modellratenänderung: {$splitsRecalced} Splits, {$abrResult['abrechnungen_regenerated']} Abrechnungen",
                    $recalcSummary);
            }
        }

        $updated = Database::queryOne('SELECT * FROM pm_commission_models WHERE id = ?', [(int)$id]);
        $response = ['model' => $updated];
        if ($recalcSummary) $response['recalc_summary'] = $recalcSummary;
        json_success($response, 'Modell aktualisiert');
        return;
    }
    if ($method === 'DELETE' && $id && is_numeric($id)) {
        Database::execute('UPDATE pm_commission_models SET is_active = 0 WHERE id = ?', [(int)$id]);
        json_success([], 'Modell deaktiviert');
        return;
    }
    json_error('Methode nicht erlaubt', 405);
}

// ═══════════════════════════════════════════════════════
// CLEARANCE (Klaerfall-Counts)
// ═══════════════════════════════════════════════════════
// MATCH-SUGGESTIONS (Phase 2)
// ═══════════════════════════════════════════════════════

function handleMatchSuggestionsRoute(string $method, array $payload): void {
    if ($method !== 'GET') {
        json_error('Method Not Allowed', 405);
        return;
    }

    $commissionId = isset($_GET['commission_id']) ? (int)$_GET['commission_id'] : null;
    $contractId   = isset($_GET['contract_id'])   ? (int)$_GET['contract_id']   : null;
    $direction    = $_GET['direction'] ?? 'forward';
    $q            = trim($_GET['q'] ?? '');
    $limit        = min(max(1, (int)($_GET['limit'] ?? 50)), 200);

    if ($direction === 'forward') {
        if (!$commissionId) {
            json_error('commission_id erforderlich', 400);
            return;
        }
        $comm = Database::queryOne('SELECT * FROM pm_commissions WHERE id = ?', [$commissionId]);
        if (!$comm) {
            json_error('Provision nicht gefunden', 404);
            return;
        }

        $rows = getMatchSuggestionsForward($comm, $q, $limit);
        json_success(['suggestions' => $rows, 'commission' => $comm]);
        return;
    }

    if ($direction === 'reverse') {
        if (!$contractId) {
            json_error('contract_id erforderlich', 400);
            return;
        }
        $contract = Database::queryOne('SELECT * FROM pm_contracts WHERE id = ?', [$contractId]);
        if (!$contract) {
            json_error('Vertrag nicht gefunden', 404);
            return;
        }

        $rows = getMatchSuggestionsReverse($contract, $q, $limit);
        json_success(['suggestions' => $rows, 'contract' => $contract]);
        return;
    }

    json_error('Ungueltiger direction Parameter', 400);
}

function getMatchSuggestionsForward(array $comm, string $q, int $limit): array {
    $vsnrNorm = $comm['vsnr_normalized'] ?? '';
    $vnNorm   = $comm['versicherungsnehmer_normalized'] ?? '';
    $vnParts  = $vnNorm ? explode(' ', $vnNorm) : [];
    $lastName = $vnParts ? $vnParts[0] : '';
    $lastLike = ($lastName && strlen($lastName) >= 3) ? ($lastName . '%') : '';

    $scoreSql = buildScoreSql('ct', $vsnrNorm, $vnNorm, $lastLike);
    $reasonSql = buildReasonSql('ct', $vsnrNorm, $vnNorm);
    $whereSql = buildWhereOr('ct', $vsnrNorm, $vnNorm, $lastLike, $q);

    if (!$whereSql['sql']) return [];

    $allParams = array_merge($scoreSql['params'], $reasonSql['params'], $whereSql['params']);

    return Database::query("
        SELECT ct.*, e.name AS berater_name,
               {$scoreSql['sql']} AS match_score,
               {$reasonSql['sql']} AS match_reason,
               ib.source_type, ib.vu_name
        FROM pm_contracts ct
        LEFT JOIN pm_employees e ON ct.berater_id = e.id
        LEFT JOIN pm_import_batches ib ON ct.import_batch_id = ib.id
        WHERE ({$whereSql['sql']})
        ORDER BY match_score DESC, ct.versicherungsnehmer ASC
        LIMIT $limit
    ", $allParams);
}

function getMatchSuggestionsReverse(array $contract, string $q, int $limit): array {
    $vsnrNorm = $contract['vsnr_normalized'] ?? '';
    $vnNorm   = $contract['versicherungsnehmer_normalized'] ?? '';
    $vnParts  = $vnNorm ? explode(' ', $vnNorm) : [];
    $lastName = $vnParts ? $vnParts[0] : '';
    $lastLike = ($lastName && strlen($lastName) >= 3) ? ($lastName . '%') : '';

    $scoreSql = buildScoreSql('c', $vsnrNorm, $vnNorm, $lastLike, false);
    $reasonSql = buildReasonSql('c', $vsnrNorm, $vnNorm, false);
    $whereSql = buildWhereOr('c', $vsnrNorm, $vnNorm, $lastLike, $q, false);

    if (!$whereSql['sql']) return [];

    $allParams = array_merge($scoreSql['params'], $reasonSql['params'], $whereSql['params']);

    return Database::query("
        SELECT c.*, {$scoreSql['sql']} AS match_score,
               {$reasonSql['sql']} AS match_reason,
               e.name AS berater_name,
               ib.source_type AS import_source_type,
               ib.vu_name AS import_vu_name
        FROM pm_commissions c
        LEFT JOIN pm_employees e ON c.berater_id = e.id
        LEFT JOIN pm_import_batches ib ON c.import_batch_id = ib.id
        WHERE ({$whereSql['sql']}) AND c.contract_id IS NULL
        ORDER BY match_score DESC
        LIMIT $limit
    ", $allParams);
}

function buildScoreSql(string $alias, string $vsnrNorm, string $vnNorm, string $lastLike, bool $hasAltVsnr = true): array {
    $lines = [];
    $params = [];
    if ($vsnrNorm) {
        $lines[] = "WHEN {$alias}.vsnr_normalized = ? THEN 100";
        $params[] = $vsnrNorm;
        if ($hasAltVsnr) {
            $lines[] = "WHEN {$alias}.vsnr_alt_normalized = ? THEN 90";
            $params[] = $vsnrNorm;
        }
    }
    if ($vnNorm) {
        $lines[] = "WHEN {$alias}.versicherungsnehmer_normalized = ? THEN 70";
        $params[] = $vnNorm;
    }
    if ($lastLike) {
        $lines[] = "WHEN {$alias}.versicherungsnehmer_normalized LIKE ? THEN 40";
        $params[] = $lastLike;
    }
    $sql = empty($lines) ? '0' : 'CASE ' . implode(' ', $lines) . ' ELSE 0 END';
    return ['sql' => $sql, 'params' => $params];
}

function buildReasonSql(string $alias, string $vsnrNorm, string $vnNorm, bool $hasAltVsnr = true): array {
    $lines = [];
    $params = [];
    if ($vsnrNorm) {
        $lines[] = "WHEN {$alias}.vsnr_normalized = ? THEN 'vsnr_exact'";
        $params[] = $vsnrNorm;
        if ($hasAltVsnr) {
            $lines[] = "WHEN {$alias}.vsnr_alt_normalized = ? THEN 'vsnr_alt'";
            $params[] = $vsnrNorm;
        }
    }
    if ($vnNorm) {
        $lines[] = "WHEN {$alias}.versicherungsnehmer_normalized = ? THEN 'name_exact'";
        $params[] = $vnNorm;
    }
    $sql = empty($lines) ? "'none'" : "CASE " . implode(' ', $lines) . " ELSE 'name_partial' END";
    return ['sql' => $sql, 'params' => $params];
}

function buildWhereOr(string $alias, string $vsnrNorm, string $vnNorm, string $lastLike, string $q, bool $hasAltVsnr = true): array {
    $parts = [];
    $params = [];
    if ($vsnrNorm) {
        $parts[] = "{$alias}.vsnr_normalized = ?";
        $params[] = $vsnrNorm;
        if ($hasAltVsnr) {
            $parts[] = "{$alias}.vsnr_alt_normalized = ?";
            $params[] = $vsnrNorm;
        }
    }
    if ($vnNorm) {
        $parts[] = "{$alias}.versicherungsnehmer_normalized = ?";
        $params[] = $vnNorm;
    }
    if ($lastLike) {
        $parts[] = "{$alias}.versicherungsnehmer_normalized LIKE ?";
        $params[] = $lastLike;
    }
    if ($q && strlen($q) >= 2) {
        $qLike = '%' . $q . '%';
        $parts[] = "({$alias}.vsnr LIKE ? OR {$alias}.versicherungsnehmer LIKE ? OR {$alias}.versicherer LIKE ?)";
        $params[] = $qLike;
        $params[] = $qLike;
        $params[] = $qLike;
    }
    $sql = empty($parts) ? '' : implode(' OR ', $parts);
    return ['sql' => $sql, 'params' => $params];
}

// ═══════════════════════════════════════════════════════
// ASSIGN (Phase 4)
// ═══════════════════════════════════════════════════════

function handleAssignRoute(string $method, array $payload): void {
    if ($method !== 'PUT') {
        json_error('Method Not Allowed', 405);
        return;
    }

    $data = get_json_body();
    $commissionId  = (int)($data['commission_id'] ?? 0);
    $contractId    = (int)($data['contract_id']   ?? 0);
    $forceOverride = (bool)($data['force_override'] ?? false);

    if (!$commissionId || !$contractId) {
        json_error('commission_id und contract_id erforderlich', 400);
        return;
    }

    $pdo = Database::getInstance();
    $pdo->beginTransaction();
    try {
        $totalAssigned = assignContractToCommission($commissionId, $contractId, $forceOverride);

        $userId = $payload['user_id'] ?? 0;
        Database::insert(
            "INSERT INTO activity_log (user_id, action, entity_type, entity_id, details, action_category)
             VALUES (?, 'manual_assign', 'pm_commission', ?, ?, 'provision')",
            [
                $userId,
                $commissionId,
                json_encode([
                    'contract_id' => $contractId,
                    'total_assigned' => $totalAssigned,
                    'force_override' => $forceOverride,
                ]),
            ]
        );

        $pdo->commit();

        $updated = Database::queryOne('SELECT * FROM pm_commissions WHERE id = ?', [$commissionId]);
        json_success(['commission' => $updated, 'total_assigned' => $totalAssigned, 'message' => 'Zuordnung gespeichert']);

    } catch (\RuntimeException $e) {
        $pdo->rollBack();
        json_error($e->getMessage(), 409);
    } catch (\Throwable $e) {
        $pdo->rollBack();
        json_error('Zuordnung fehlgeschlagen: ' . $e->getMessage(), 500);
    }
}

// ═══════════════════════════════════════════════════════

function handleClearanceRoute(string $method, array $payload): void {
    if ($method !== 'GET') json_error('Methode nicht erlaubt', 405);

    $noContract = Database::queryOne(
        "SELECT COUNT(*) AS cnt FROM pm_commissions WHERE match_status = 'unmatched' AND contract_id IS NULL"
    );
    $noBerater = Database::queryOne("
        SELECT COUNT(*) AS cnt FROM pm_commissions
        WHERE match_status IN ('auto_matched','manual_matched')
          AND berater_id IS NULL
    ");
    $noModel = Database::queryOne("
        SELECT COUNT(*) AS cnt FROM pm_employees
        WHERE is_active = 1 AND role IN ('consulter','teamleiter')
          AND commission_model_id IS NULL AND commission_rate_override IS NULL
    ");
    $noSplit = Database::queryOne("
        SELECT COUNT(*) AS cnt FROM pm_commissions
        WHERE match_status IN ('auto_matched','manual_matched')
          AND berater_id IS NOT NULL
          AND berater_anteil IS NULL
    ");
    $total = (int)$noContract['cnt'] + (int)$noBerater['cnt'] + (int)$noModel['cnt'] + (int)$noSplit['cnt'];

    json_success([
        'total' => $total,
        'no_contract' => (int)$noContract['cnt'],
        'no_berater' => (int)$noBerater['cnt'],
        'no_model' => (int)$noModel['cnt'],
        'no_split' => (int)$noSplit['cnt'],
    ]);
}

// ═══════════════════════════════════════════════════════
// AUDIT (PM-Aktivitaetshistorie)
// ═══════════════════════════════════════════════════════

function handleAuditRoute(string $method, ?string $entityType, ?string $entityId, array $payload): void {
    if ($method !== 'GET') json_error('Methode nicht erlaubt', 405);

    $where = "action_category = 'provision'";
    $params = [];

    if ($entityType && $entityId && is_numeric($entityId)) {
        $where .= ' AND entity_type = ? AND entity_id = ?';
        $params[] = $entityType;
        $params[] = (int)$entityId;
    }

    $limit = min((int)($_GET['limit'] ?? 100), 500);

    $rows = Database::query("
        SELECT id, user_id, username, action, entity_type, entity_id,
               description, details, status, created_at
        FROM activity_log
        WHERE $where
        ORDER BY created_at DESC
        LIMIT $limit
    ", $params);

    $entries = array_map(function($r) {
        return [
            'id' => (int)$r['id'],
            'user_id' => $r['user_id'] ? (int)$r['user_id'] : null,
            'username' => $r['username'],
            'action' => $r['action'],
            'entity_type' => $r['entity_type'],
            'entity_id' => $r['entity_id'] ? (int)$r['entity_id'] : null,
            'description' => $r['description'],
            'details' => $r['details'] ? json_decode($r['details'], true) : null,
            'status' => $r['status'],
            'created_at' => $r['created_at'],
        ];
    }, $rows);

    json_success(['entries' => $entries]);
}

// ═══════════════════════════════════════════════════════
// RESET (GEFAHRENZONE)
// ═══════════════════════════════════════════════════════

/**
 * Loescht alle Import-Daten fuer einen kompletten Neuimport.
 * Mitarbeiter, Modelle und Vermittler-Mappings bleiben erhalten.
 */
function handleResetRoute(string $method, array $payload): void {
    if ($method !== 'POST') {
        json_error('Methode nicht erlaubt', 405);
        return;
    }

    requirePermission('provision_manage');

    try {
        // Zaehle vorher
        $beforeComm = (int)Database::queryOne('SELECT COUNT(*) as cnt FROM pm_commissions')['cnt'];
        $beforeContr = (int)Database::queryOne('SELECT COUNT(*) as cnt FROM pm_contracts')['cnt'];
        $beforeBatch = (int)Database::queryOne('SELECT COUNT(*) as cnt FROM pm_import_batches')['cnt'];
        $beforeAbr = (int)Database::queryOne('SELECT COUNT(*) as cnt FROM pm_berater_abrechnungen')['cnt'];

        // FK-Checks deaktivieren fuer TRUNCATE
        Database::execute('SET FOREIGN_KEY_CHECKS = 0');

        // TRUNCATE ist schneller als DELETE und setzt Auto-Increment zurueck
        Database::execute('TRUNCATE TABLE pm_commissions');
        Database::execute('TRUNCATE TABLE pm_contracts');
        Database::execute('TRUNCATE TABLE pm_import_batches');
        Database::execute('TRUNCATE TABLE pm_berater_abrechnungen');

        // Xempus-Tabellen leeren (wenn vorhanden)
        $xempusTables = [
            'xempus_commission_matches',
            'xempus_consultations',
            'xempus_employees',
            'xempus_subsidies',
            'xempus_tariffs',
            'xempus_employers',
            'xempus_raw_rows',
            'xempus_import_batches',
        ];
        foreach ($xempusTables as $xt) {
            try {
                Database::execute("TRUNCATE TABLE $xt");
            } catch (\Throwable $ignore) {
                // Tabelle existiert noch nicht - harmlos
            }
        }

        // FK-Checks wieder aktivieren
        Database::execute('SET FOREIGN_KEY_CHECKS = 1');

        // xempus_status_mapping wird NICHT getruncated, aber re-seed falls leer
        require_once __DIR__ . '/xempus.php';
        xempusSeedStatusMappingDefaults();

        // Zaehle was erhalten blieb
        $keptEmp = (int)Database::queryOne('SELECT COUNT(*) as cnt FROM pm_employees')['cnt'];
        $keptMod = (int)Database::queryOne('SELECT COUNT(*) as cnt FROM pm_commission_models')['cnt'];
        $keptMap = (int)Database::queryOne('SELECT COUNT(*) as cnt FROM pm_vermittler_mapping')['cnt'];

        // Activity-Log
        logPmAction($payload, 'provision_reset', null, null,
            "Provision-Daten zurueckgesetzt: $beforeComm Commissions, $beforeContr Contracts, $beforeBatch Batches geloescht",
            [
                'deleted' => [
                    'pm_commissions' => $beforeComm,
                    'pm_contracts' => $beforeContr,
                    'pm_import_batches' => $beforeBatch,
                    'pm_berater_abrechnungen' => $beforeAbr,
                ],
                'kept' => [
                    'pm_employees' => $keptEmp,
                    'pm_commission_models' => $keptMod,
                    'pm_vermittler_mapping' => $keptMap,
                ],
            ]
        );

        json_success([
            'deleted' => [
                'pm_commissions' => $beforeComm,
                'pm_contracts' => $beforeContr,
                'pm_import_batches' => $beforeBatch,
                'pm_berater_abrechnungen' => $beforeAbr,
            ],
            'kept' => [
                'pm_employees' => $keptEmp,
                'pm_commission_models' => $keptMod,
                'pm_vermittler_mapping' => $keptMap,
            ],
        ], 'Provision-Daten erfolgreich zurueckgesetzt');

    } catch (\Throwable $e) {
        // FK-Checks zuruecksetzen falls Fehler
        try { Database::execute('SET FOREIGN_KEY_CHECKS = 1'); } catch (\Throwable $e2) {}

        json_error('Reset fehlgeschlagen: ' . $e->getMessage(), 500);
    }
}

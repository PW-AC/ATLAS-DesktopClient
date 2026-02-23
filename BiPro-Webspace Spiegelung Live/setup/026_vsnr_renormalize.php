<?php
/**
 * Migration 026: VSNR Re-Normalisierung
 *
 * Aendert die VSNR-Normalisierung: Jetzt werden ALLE Nullen entfernt (nicht nur fuehrende).
 * Dadurch wird das Matching robuster gegenueber verschiedenen VSNR-Schreibweisen.
 *
 * Beispiele:
 *   "00123045" -> "12345" (vorher: "123045")
 *   "A-001-234" -> "1234" (vorher: "1234" -- keine Aenderung)
 *
 * Diese Migration aktualisiert vsnr_normalized in pm_commissions und pm_contracts.
 */

require_once __DIR__ . '/../api/config.php';
require_once __DIR__ . '/../api/lib/db.php';

echo "Migration 026: VSNR Re-Normalisierung (alle Nullen entfernen)\n";
echo str_repeat('=', 60) . "\n";

/**
 * Neue Normalisierung: Alle Nicht-Ziffern UND alle Nullen entfernen.
 */
function normalizeVsnrNew(string $raw): string {
    $s = trim($raw);
    if ($s === '') return '';
    // Scientific notation
    if (stripos($s, 'e') !== false && (strpos($s, ',') !== false || strpos($s, '.') !== false)) {
        $s = str_replace(',', '.', $s);
        try {
            $num = (float)$s;
            if (is_finite($num) && $num > 0) {
                $s = number_format($num, 0, '', '');
            }
        } catch (\Throwable $e) {}
    }
    $digits = preg_replace('/\D/', '', $s);
    $noZeros = str_replace('0', '', $digits);
    return $noZeros !== '' ? $noZeros : '0';
}

try {
    $pdo = Database::getInstance();

    // ── pm_commissions ──
    echo "\n[1/2] Re-normalisiere pm_commissions.vsnr_normalized...\n";

    $commissions = Database::query('SELECT id, vsnr FROM pm_commissions WHERE vsnr IS NOT NULL AND vsnr != ""');
    $updatedComm = 0;
    $unchangedComm = 0;

    foreach ($commissions as $row) {
        $oldNorm = Database::queryOne('SELECT vsnr_normalized FROM pm_commissions WHERE id = ?', [$row['id']]);
        $newNorm = normalizeVsnrNew($row['vsnr']);

        if ($oldNorm['vsnr_normalized'] !== $newNorm) {
            Database::execute(
                'UPDATE pm_commissions SET vsnr_normalized = ? WHERE id = ?',
                [$newNorm, $row['id']]
            );
            $updatedComm++;
        } else {
            $unchangedComm++;
        }
    }

    echo "   -> $updatedComm aktualisiert, $unchangedComm unveraendert\n";

    // ── pm_contracts ──
    echo "\n[2/2] Re-normalisiere pm_contracts.vsnr_normalized + vsnr_alt_normalized...\n";

    $contracts = Database::query('SELECT id, vsnr, vsnr_alt FROM pm_contracts WHERE vsnr IS NOT NULL AND vsnr != ""');
    $updatedContr = 0;
    $unchangedContr = 0;

    foreach ($contracts as $row) {
        $oldData = Database::queryOne('SELECT vsnr_normalized, vsnr_alt_normalized FROM pm_contracts WHERE id = ?', [$row['id']]);

        $newVsnrNorm = normalizeVsnrNew($row['vsnr']);
        $newAltNorm = !empty($row['vsnr_alt']) ? normalizeVsnrNew($row['vsnr_alt']) : null;

        $changed = false;
        if ($oldData['vsnr_normalized'] !== $newVsnrNorm) {
            $changed = true;
        }
        if ($newAltNorm !== null && $oldData['vsnr_alt_normalized'] !== $newAltNorm) {
            $changed = true;
        }

        if ($changed) {
            Database::execute(
                'UPDATE pm_contracts SET vsnr_normalized = ?, vsnr_alt_normalized = ? WHERE id = ?',
                [$newVsnrNorm, $newAltNorm, $row['id']]
            );
            $updatedContr++;
        } else {
            $unchangedContr++;
        }
    }

    echo "   -> $updatedContr aktualisiert, $unchangedContr unveraendert\n";

    echo "\n" . str_repeat('=', 60) . "\n";
    echo "[DONE] Migration 026 abgeschlossen.\n";
    echo "Gesamt: " . ($updatedComm + $updatedContr) . " Zeilen aktualisiert\n";
    echo "\nHINWEIS: Fuehren Sie nach dieser Migration ein Auto-Matching aus,\n";
    echo "         um die neuen Normalisierungen abzugleichen.\n";

} catch (\Throwable $e) {
    echo "\n[ERROR] " . $e->getMessage() . "\n";
    echo $e->getTraceAsString() . "\n";
    exit(1);
}

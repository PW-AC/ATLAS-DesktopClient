# ============================================================================
# ATLAS Governance - Branch Reset
# ============================================================================
# Setzt beta und dev per Hard-Reset exakt auf den Stand von main.
# DESTRUKTIV: Force-Push auf beta und dev!
#
# Verwendung:
#   .\02_reset_branches.ps1
#   .\02_reset_branches.ps1 -Force   # Ohne Bestaetigung (fuer Agents/CI)
# ============================================================================

param(
    [switch]$Force
)

. "$PSScriptRoot\_lib.ps1"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " ATLAS Branch Reset (beta + dev -> main)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Assert-GitClean

Write-Step "Remote-Status abrufen..."
Invoke-GitSilent fetch --all --prune

Write-Step "Divergenz-Analyse"

foreach ($branch in @("beta", "dev")) {
    $remoteRef = "origin/$branch"
    $exists = git rev-parse --verify $remoteRef 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Info "${branch}: Branch existiert nicht remote (wird neu erstellt)"
        continue
    }

    $ahead = git rev-list --count "origin/main..$remoteRef" 2>$null
    $behind = git rev-list --count "$remoteRef..origin/main" 2>$null

    if ($ahead -eq "0" -and $behind -eq "0") {
        Write-Ok "${branch} ist identisch mit main"
    }
    else {
        Write-Warn "${branch}: $ahead Commit(s) AHEAD (werden GELOESCHT), $behind Commit(s) BEHIND"
        if ([int]$ahead -gt 0) {
            $lostCommits = git log --oneline "origin/main..$remoteRef" 2>$null
            foreach ($c in $lostCommits) {
                Write-Host "      - $c" -ForegroundColor Red
            }
        }
    }
}

Write-Step "Warnung: Destruktive Operation"

Write-Host ""
Write-Host "  Diese Operation setzt beta und dev per FORCE PUSH" -ForegroundColor Red
Write-Host "  auf den exakten Stand von main zurueck." -ForegroundColor Red
Write-Host "  Alle Commits auf beta/dev, die nicht in main sind," -ForegroundColor Red
Write-Host "  gehen UNWIDERRUFLICH verloren!" -ForegroundColor Red
Write-Host ""

if (-not $Force) {
    $proceed = Confirm-Action "Zum Bestaetigen 'RESET' eingeben:" -RequiredInput "RESET"
    if (-not $proceed) { exit 0 }
}
else {
    Write-Warn "Force-Modus: Bestaetigung uebersprungen"
}

Write-Step "main aktualisieren..."
git checkout main 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Err "Konnte nicht auf main wechseln"
    exit 1
}
git pull origin main 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Err "git pull origin main fehlgeschlagen"
    exit 1
}
Write-Ok "main ist aktuell"

Write-Step "beta auf main zuruecksetzen..."

$betaExists = git branch -r --list "origin/beta" 2>&1
if ($betaExists) {
    git checkout beta 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        git checkout -b beta origin/main 2>&1 | Out-Null
    }
}
else {
    git checkout -b beta 2>&1 | Out-Null
}

git reset --hard origin/main 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Err "Reset von beta fehlgeschlagen"
    exit 1
}

git push -f origin beta 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Err "Force-Push auf beta fehlgeschlagen"
    exit 1
}
Write-Ok "beta = main (force-pushed)"

Write-Step "dev auf main zuruecksetzen..."

$devExists = git branch -r --list "origin/dev" 2>&1
if ($devExists) {
    git checkout dev 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        git checkout -b dev origin/main 2>&1 | Out-Null
    }
}
else {
    git checkout -b dev 2>&1 | Out-Null
}

git reset --hard origin/main 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Err "Reset von dev fehlgeschlagen"
    exit 1
}

git push -f origin dev 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Err "Force-Push auf dev fehlgeschlagen"
    exit 1
}
Write-Ok "dev = main (force-pushed)"

Write-Step "Zurueck auf main wechseln..."
git checkout main 2>&1 | Out-Null
Write-Ok "Auf main"

Write-Host ""
Write-Ok "Branch Reset abgeschlossen: beta und dev sind identisch mit main"

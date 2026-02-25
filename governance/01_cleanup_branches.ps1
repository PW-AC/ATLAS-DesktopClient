# ============================================================================
# ATLAS Governance - Branch Cleanup
# ============================================================================
# Loescht alle Remote- und lokalen Branches ausser main, beta, dev.
#
# Verwendung:
#   .\01_cleanup_branches.ps1
#   .\01_cleanup_branches.ps1 -Force   # Ohne Bestaetigung
# ============================================================================

param(
    [switch]$Force
)

. "$PSScriptRoot\_lib.ps1"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " ATLAS Branch Cleanup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# --- Remote-Branches ---

Write-Step "Remote-Branches synchronisieren..."
Invoke-GitSilent fetch --all --prune
if ($LASTEXITCODE -ne 0) {
    Write-Err "git fetch fehlgeschlagen"
    exit 1
}
Write-Ok "Remote synchronisiert"

Write-Step "Remote-Branches zum Loeschen ermitteln..."

$remoteBranches = @(git branch -r 2>&1 |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_ -notmatch "HEAD" } |
    ForEach-Object { $_ -replace "^origin/", "" } |
    Where-Object { $_ -notin $script:PROTECTED_BRANCHES })

if ($remoteBranches.Count -eq 0) {
    Write-Ok "Keine Remote-Branches zum Loeschen gefunden"
}
else {
    Write-Info "Folgende Remote-Branches werden geloescht:"
    foreach ($b in $remoteBranches) {
        Write-Host "    - origin/$b" -ForegroundColor Yellow
    }

    $proceed = $true
    if (-not $Force) {
        $proceed = Confirm-Action "ACHTUNG: $($remoteBranches.Count) Remote-Branch(es) werden unwiderruflich geloescht!"
    }

    if ($proceed) {
        foreach ($b in $remoteBranches) {
            Write-Info "Loesche origin/$b ..."
            git push origin --delete $b 2>&1 | Out-Null
            if ($LASTEXITCODE -ne 0) {
                Write-Warn "Konnte origin/$b nicht loeschen (evtl. bereits entfernt)"
            }
        }
        Write-Ok "$($remoteBranches.Count) Remote-Branch(es) geloescht"
    }
}

# --- Lokale Branches ---

Write-Step "Lokale Branches zum Loeschen ermitteln..."

$localBranches = @(git branch 2>&1 |
    ForEach-Object { $_.Trim().TrimStart("* ") } |
    Where-Object { $_ -notin $script:PROTECTED_BRANCHES -and $_ -ne "" })

if ($localBranches.Count -eq 0) {
    Write-Ok "Keine lokalen Branches zum Loeschen gefunden"
}
else {
    Write-Info "Folgende lokale Branches werden geloescht:"
    foreach ($b in $localBranches) {
        Write-Host "    - $b" -ForegroundColor Yellow
    }

    $proceed = $true
    if (-not $Force) {
        $proceed = Confirm-Action "$($localBranches.Count) lokale(r) Branch(es) werden geloescht."
    }

    if ($proceed) {
        $currentBranch = Get-CurrentBranch
        if ($currentBranch -notin $script:PROTECTED_BRANCHES) {
            Write-Info "Wechsle auf main..."
            git checkout main 2>&1 | Out-Null
        }

        foreach ($b in $localBranches) {
            Write-Info "Loesche $b ..."
            git branch -D $b 2>&1 | Out-Null
            if ($LASTEXITCODE -ne 0) {
                Write-Warn "Konnte $b nicht loeschen"
            }
        }
        Write-Ok "$($localBranches.Count) lokale(r) Branch(es) geloescht"
    }
}

Write-Host ""
Write-Ok "Branch Cleanup abgeschlossen"

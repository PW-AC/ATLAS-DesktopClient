"""
Installer-Verifikation fuer ATLAS Releases.

Prueft:
- VERSION-Datei vorhanden und gueltig (SemVer)
- Installer-Datei in Output/ vorhanden
- SHA256-Hash berechnet
- Version im Dateinamen == VERSION-Datei
- version_info.txt konsistent

Ausfuehrung:
    python scripts/verify_installer.py
    python scripts/verify_installer.py --json
"""

import sys
import os
import re
import json
import hashlib
import glob
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
INSTALLER_PATTERN = "Output/ACENCIA-ATLAS-Setup-*.exe"

json_mode = '--json' in sys.argv
checks = []
all_ok = True


def check(name: str, passed: bool, detail: str = ""):
    global all_ok
    checks.append({
        'name': name,
        'status': 'passed' if passed else 'failed',
        'detail': detail,
    })
    if not passed:
        all_ok = False
    if not json_mode:
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} {name}")
        if detail and not passed:
            print(f"        {detail}")


def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


if not json_mode:
    print("\n" + "=" * 60)
    print("ATLAS Installer Verifikation")
    print("=" * 60)
    print(f"Ausfuehrung: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

version_file = ROOT / 'VERSION'
version = None

check(
    "VERSION Datei existiert",
    version_file.exists(),
    f"Pfad: {version_file}"
)

if version_file.exists():
    version = version_file.read_text(encoding='utf-8-sig').strip()
    is_semver = bool(re.match(r'^\d+\.\d+\.\d+', version))
    check(
        f"VERSION ist gueltig: {version}",
        is_semver,
        f"Wert: '{version}' ist kein SemVer"
    )

installers = sorted(glob.glob(str(ROOT / INSTALLER_PATTERN)))
check(
    "Installer in Output/ vorhanden",
    len(installers) > 0,
    f"Gesucht: {INSTALLER_PATTERN}, gefunden: {len(installers)}"
)

installer_path = None
installer_sha = None
installer_version = None

if installers:
    installer_path = installers[-1]
    installer_name = os.path.basename(installer_path)

    if not json_mode:
        print(f"\n  Installer: {installer_name}")
        size_mb = os.path.getsize(installer_path) / (1024 * 1024)
        print(f"  Groesse:   {size_mb:.1f} MB")

    installer_sha = compute_sha256(installer_path)
    check(
        f"SHA256 berechnet: {installer_sha[:16]}...",
        len(installer_sha) == 64,
    )

    match = re.search(r'Setup-(\d+\.\d+\.\d+)', installer_name)
    if match:
        installer_version = match.group(1)
        if version:
            version_base = version.split('-')[0]
            check(
                f"Installer-Version ({installer_version}) == VERSION ({version_base})",
                installer_version == version_base,
                f"Mismatch: Installer={installer_version}, VERSION={version_base}"
            )
    else:
        check(
            "Version im Installer-Dateinamen erkennbar",
            False,
            f"Kein Versionsmuster in '{installer_name}' gefunden"
        )

info_path = ROOT / 'version_info.txt'
if info_path.exists() and version:
    info_content = info_path.read_text(encoding='utf-8')
    parts = version.split('-')[0].split('.')
    expected = f"filevers=({parts[0]}, {parts[1]}, {parts[2]}, 0)"
    check(
        "version_info.txt konsistent mit VERSION",
        expected in info_content,
        f"Erwartet '{expected}' in version_info.txt"
    )

if json_mode:
    report = {
        'timestamp': datetime.utcnow().isoformat(),
        'version': version,
        'installer_path': installer_path,
        'installer_sha256': installer_sha,
        'installer_version': installer_version,
        'all_passed': all_ok,
        'checks': checks,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
else:
    print("\n" + "=" * 60)
    passed_count = sum(1 for c in checks if c['status'] == 'passed')
    failed_count = sum(1 for c in checks if c['status'] == 'failed')
    print(f"  Bestanden: {passed_count}")
    print(f"  Fehlgeschlagen: {failed_count}")
    print("=" * 60)

sys.exit(0 if all_ok else 1)

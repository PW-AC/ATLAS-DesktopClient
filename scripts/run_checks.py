#!/usr/bin/env python3
"""
Minimal CI Script für BiPRO-GDV Tool.

Führt Lint + Tests aus.
Aufruf: python scripts/run_checks.py
"""

import subprocess
import sys
import os

def run_command(name, cmd):
    """Führt einen Befehl aus und gibt Ergebnis zurück."""
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    
    status = "PASS" if result.returncode == 0 else "FAIL"
    print(f"  -> {status} (Exit Code: {result.returncode})")
    return result.returncode == 0

def main():
    os.chdir(os.path.join(os.path.dirname(__file__), '..'))
    results = {}
    
    # 1. Lint (optional)
    try:
        subprocess.run(["ruff", "--version"], capture_output=True, check=True)
        results['Lint (ruff)'] = run_command('Lint (ruff)', ['ruff', 'check', 'src/', '--select', 'E,F', '--ignore', 'E501,F401'])
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("\n  [SKIP] ruff nicht installiert")
        results['Lint (ruff)'] = None
    
    # 2. Tests
    results['Tests (pytest)'] = run_command('Tests (pytest)', [
        sys.executable, '-m', 'pytest', 'src/tests/test_stability.py', '-v', '--tb=short'
    ])
    
    # Summary
    print(f"\n{'='*60}")
    print("  ZUSAMMENFASSUNG")
    print(f"{'='*60}")
    
    all_pass = True
    for name, passed in results.items():
        if passed is None:
            print(f"  [SKIP] {name}")
        elif passed:
            print(f"  [PASS] {name}")
        else:
            print(f"  [FAIL] {name}")
            all_pass = False
    
    print(f"\n  Gesamtergebnis: {'PASS' if all_pass else 'FAIL'}")
    sys.exit(0 if all_pass else 1)

if __name__ == '__main__':
    main()

"""
Unit-Tests fuer Provisions-Normalisierungsfunktionen.

Testet die geschaeftskritischen Normalisierungsfunktionen aus provision_import.py,
die das Fundament fuer VSNR-Matching, Vermittler-Zuordnung und VN-Suche bilden.

Ausfuehrung:
    python src/tests/test_provision.py
    python src/tests/test_provision.py --json-report
"""

import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))

from services.provision_import import normalize_vsnr, normalize_vermittler_name, normalize_for_db

JSON_REPORT_MODE = '--json-report' in sys.argv

passed = 0
failed = 0
errors = []
_test_results = []


def test(name):
    """Decorator fuer Tests."""
    def decorator(func):
        def wrapper():
            global passed, failed, errors, _test_results
            t0 = time.time()
            try:
                func()
                duration_ms = int((time.time() - t0) * 1000)
                if not JSON_REPORT_MODE:
                    print(f"  [OK] {name}")
                passed += 1
                _test_results.append({'name': name, 'status': 'passed', 'duration_ms': duration_ms})
            except AssertionError as e:
                duration_ms = int((time.time() - t0) * 1000)
                if not JSON_REPORT_MODE:
                    print(f"  [FAIL] {name}")
                    print(f"         Assertion: {e}")
                failed += 1
                errors.append((name, str(e)))
                _test_results.append({'name': name, 'status': 'failed', 'duration_ms': duration_ms, 'error': str(e)})
            except Exception as e:
                duration_ms = int((time.time() - t0) * 1000)
                if not JSON_REPORT_MODE:
                    print(f"  [ERROR] {name}")
                    print(f"          {type(e).__name__}: {e}")
                failed += 1
                errors.append((name, f"{type(e).__name__}: {e}"))
                _test_results.append({'name': name, 'status': 'failed', 'duration_ms': duration_ms, 'error': f"{type(e).__name__}: {e}"})
        return wrapper
    return decorator


# ==============================================================================
# normalize_vsnr Tests
# ==============================================================================

print("\n" + "=" * 70)
print("Provision Normalisierung - Unit Tests")
print("=" * 70)
print(f"Ausfuehrung: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

print("\n[1] normalize_vsnr")
print("-" * 40)


@test("normalize_vsnr: Buchstaben + Nullen entfernen")
def test_vsnr_letters_zeros():
    assert normalize_vsnr("ABC-001-234") == "1234"


test_vsnr_letters_zeros()


@test("normalize_vsnr: Fuehrende und interne Nullen entfernen")
def test_vsnr_all_zeros():
    assert normalize_vsnr("00123045") == "12345"


test_vsnr_all_zeros()


@test("normalize_vsnr: Scientific Notation (Punkt)")
def test_vsnr_scientific_dot():
    result = normalize_vsnr("1.23E+10")
    assert result == "123", f"Erwartet '123', erhalten '{result}'"


test_vsnr_scientific_dot()


@test("normalize_vsnr: Leerstring")
def test_vsnr_empty():
    assert normalize_vsnr("") == ""


test_vsnr_empty()


@test("normalize_vsnr: Nur Nullen -> '0'")
def test_vsnr_only_zeros():
    assert normalize_vsnr("0000") == "0"


test_vsnr_only_zeros()


@test("normalize_vsnr: Sonderzeichen + Schraegstrich")
def test_vsnr_special_chars():
    result = normalize_vsnr("VS-2024/001")
    digits_no_zeros = "2241"
    assert result == digits_no_zeros, f"Erwartet '{digits_no_zeros}', erhalten '{result}'"


test_vsnr_special_chars()


@test("normalize_vsnr: Whitespace")
def test_vsnr_whitespace():
    result = normalize_vsnr("  123 456  ")
    assert result == "123456", f"Erwartet '123456', erhalten '{result}'"


test_vsnr_whitespace()


@test("normalize_vsnr: Bereits sauber")
def test_vsnr_clean():
    assert normalize_vsnr("12345") == "12345"


test_vsnr_clean()


@test("normalize_vsnr: Nur Buchstaben")
def test_vsnr_only_letters():
    result = normalize_vsnr("ABC")
    assert result == "" or result == "0", f"Erwartet '' oder '0', erhalten '{result}'"


test_vsnr_only_letters()


@test("normalize_vsnr: Scientific Notation (Komma)")
def test_vsnr_scientific_comma():
    result = normalize_vsnr("1,23E+7")
    assert "123" in result, f"Erwartet '123' enthalten in '{result}'"


test_vsnr_scientific_comma()


@test("normalize_vsnr: Einzelne Null")
def test_vsnr_single_zero():
    assert normalize_vsnr("0") == "0"


test_vsnr_single_zero()


@test("normalize_vsnr: Interne Nullen")
def test_vsnr_internal_zeros():
    assert normalize_vsnr("10203") == "123"


test_vsnr_internal_zeros()


# ==============================================================================
# normalize_vermittler_name Tests
# ==============================================================================

print("\n[2] normalize_vermittler_name")
print("-" * 40)


@test("normalize_vermittler_name: Umlaute ersetzen")
def test_vermittler_umlaute():
    result = normalize_vermittler_name("Müller-Lüdenscheidt")
    assert "ae" not in result or "mueller" in result
    assert "ue" in result or "luedenscheidt" in result
    assert result == "muellerluedenscheidt", f"Erwartet 'muellerluedenscheidt', erhalten '{result}'"


test_vermittler_umlaute()


@test("normalize_vermittler_name: Gross/Klein + Whitespace")
def test_vermittler_case_whitespace():
    result = normalize_vermittler_name("  Hans  Peter  SCHMIDT  ")
    assert result == "hans peter schmidt", f"Erwartet 'hans peter schmidt', erhalten '{result}'"


test_vermittler_case_whitespace()


@test("normalize_vermittler_name: Sonderzeichen entfernen")
def test_vermittler_special():
    result = normalize_vermittler_name("Dr. Max O'Brien-Smith")
    assert result == "dr max obriensmith", f"Erwartet 'dr max obriensmith', erhalten '{result}'"


test_vermittler_special()


@test("normalize_vermittler_name: Eszett")
def test_vermittler_eszett():
    result = normalize_vermittler_name("Straße")
    assert result == "strasse", f"Erwartet 'strasse', erhalten '{result}'"


test_vermittler_eszett()


@test("normalize_vermittler_name: Ziffern beibehalten")
def test_vermittler_digits():
    result = normalize_vermittler_name("Team 42")
    assert result == "team 42", f"Erwartet 'team 42', erhalten '{result}'"


test_vermittler_digits()


@test("normalize_vermittler_name: Alle Umlaute")
def test_vermittler_all_umlauts():
    result = normalize_vermittler_name("Ähre Öl Über Fuß")
    assert result == "aehre oel ueber fuss", f"Erwartet 'aehre oel ueber fuss', erhalten '{result}'"


test_vermittler_all_umlauts()


# ==============================================================================
# normalize_for_db Tests
# ==============================================================================

print("\n[3] normalize_for_db")
print("-" * 40)


@test("normalize_for_db: Klammern aufloesen")
def test_db_brackets():
    result = normalize_for_db("Schmidt (geb. Meier)")
    assert "geb meier" in result, f"Klammer-Inhalt nicht aufgeloest in '{result}'"
    assert "(" not in result and ")" not in result


test_db_brackets()


@test("normalize_for_db: Umlaute + Sonderzeichen")
def test_db_umlauts_special():
    result = normalize_for_db("Müller-Lüdenscheidt, Dr.")
    assert result == "mueller luedenscheidt dr", f"Erwartet 'mueller luedenscheidt dr', erhalten '{result}'"


test_db_umlauts_special()


@test("normalize_for_db: Leerstring")
def test_db_empty():
    assert normalize_for_db("") == ""
    assert normalize_for_db(None) == ""


test_db_empty()


@test("normalize_for_db: Whitespace-Normalisierung")
def test_db_whitespace():
    result = normalize_for_db("  Hans   Peter   ")
    assert result == "hans peter", f"Erwartet 'hans peter', erhalten '{result}'"


test_db_whitespace()


@test("normalize_for_db: Komplexer Name")
def test_db_complex():
    result = normalize_for_db("Günther Straße (Zweitname: Öztürk)")
    assert "guenther" in result
    assert "strasse" in result
    assert "oeztuerk" in result
    assert "(" not in result


test_db_complex()


# ==============================================================================
# ERGEBNIS
# ==============================================================================

if JSON_REPORT_MODE:
    version_file = project_root / 'VERSION'
    app_version = '0.0.0'
    if version_file.exists():
        app_version = version_file.read_text(encoding='utf-8-sig').strip()

    report = {
        'app_version': app_version,
        'timestamp': datetime.utcnow().isoformat(),
        'test_suite': 'provision_normalization',
        'tests_run': passed + failed,
        'tests_passed': passed,
        'tests_failed': failed,
        'results': _test_results,
    }
    report_path = project_root / 'provision_test_report.json'
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(json.dumps(report, indent=2, ensure_ascii=False))
else:
    print("\n" + "=" * 70)
    print("ERGEBNIS")
    print("=" * 70)
    print(f"\n  Bestanden: {passed}")
    print(f"  Fehlgeschlagen: {failed}")
    print(f"  Gesamt: {passed + failed}")

    if errors:
        print("\n  FEHLERDETAILS:")
        for name, msg in errors:
            print(f"    - {name}: {msg}")

    print("\n" + "=" * 70)

sys.exit(0 if failed == 0 else 1)

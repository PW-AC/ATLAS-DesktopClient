"""
IWM FinanzOffice Passwort-Entschlüsselung

Analyse des proprietären 001: Formats.
"""

# Bekannte Paare aus der Datenbank
ENCRYPTED_SAMPLES = {
    # Benutzer -> (verschlüsselt, möglicher Klartext falls bekannt)
    "U.Weimert (VEMA)": ("001:081166139241238231221210163117210197133046081", None),
    "u.weimert": ("001:074186080251235248230229167152001065091197", None),
    "uwe.weimert": ("001:050154070159097183160041048171099163083", None),
    "A237860 (AXA 1)": ("001:048161068157089205104255238229245", None),
    "A237860 (AXA 2)": ("001:032145036093217205104255238229245", None),
    "A175966 (AXA)": ("001:058172050161047167032073161116210214", None),
    "VEMA-3527-00": ("001:082197099009253020101198157085176", None),
    "1004695 (Helvetia)": ("001:030144010065176041150042119244251010016063101184", None),
}

def parse_encrypted(encrypted: str) -> list[int]:
    """
    Parst 001:XXX Format in Byte-Liste.
    
    Die Zahlen sind dezimal, 0-255, aneinander gereiht.
    Strategie: Greedy - nimm die längste gültige Zahl (max 3 Stellen, max 255).
    """
    if not encrypted.startswith("001:"):
        raise ValueError("Ungültiges Format")
    
    data = encrypted[4:]  # Nach "001:"
    
    bytes_list = []
    i = 0
    while i < len(data):
        # Versuche 3 Stellen (z.B. 255, 100, 081)
        if i + 3 <= len(data):
            chunk3 = data[i:i+3]
            num3 = int(chunk3)
            if num3 <= 255:
                bytes_list.append(num3)
                i += 3
                continue
        
        # Versuche 2 Stellen
        if i + 2 <= len(data):
            chunk2 = data[i:i+2]
            num2 = int(chunk2)
            bytes_list.append(num2)
            i += 2
            continue
        
        # 1 Stelle
        bytes_list.append(int(data[i]))
        i += 1
    
    return bytes_list


def parse_encrypted_v2(encrypted: str) -> list[int]:
    """
    Alternative Parsing-Methode: Versucht bekannte Länge zu matchen.
    """
    if not encrypted.startswith("001:"):
        raise ValueError("Ungültiges Format")
    
    data = encrypted[4:]
    
    # Methode: Rekursiv alle möglichen Kombinationen finden
    def find_valid_parse(s, current=[]):
        if not s:
            return current
        
        # Versuche 3, 2, 1 Stellen
        for length in [3, 2, 1]:
            if len(s) >= length:
                chunk = s[:length]
                if chunk[0] != '0' or length == 1 or (length == 2 and chunk == '00') or (length == 3 and chunk in ['000']):
                    # Führende Nullen nur bei bestimmten Fällen erlauben
                    pass
                num = int(chunk)
                if num <= 255:
                    result = find_valid_parse(s[length:], current + [num])
                    if result is not None:
                        return result
        return None
    
    result = find_valid_parse(data)
    return result if result else []


def try_xor_decrypt(encrypted_bytes: list[int], known_plain: str = None) -> dict:
    """Versucht XOR-Entschlüsselung."""
    results = {}
    
    if known_plain:
        plain_bytes = [ord(c) for c in known_plain]
        # XOR-Key berechnen
        if len(encrypted_bytes) >= len(plain_bytes):
            key = []
            for i, p in enumerate(plain_bytes):
                key.append(encrypted_bytes[i] ^ p)
            results['xor_key'] = key
            results['xor_key_chars'] = ''.join(chr(k) if 32 <= k < 127 else f'\\x{k:02x}' for k in key)
    
    # Versuche häufige XOR-Keys
    for xor_key in [0x00, 0xFF, 0x5A, 0xA5, 0x55, 0xAA]:
        decrypted = bytes([b ^ xor_key for b in encrypted_bytes])
        try:
            text = decrypted.decode('latin-1')
            if text.isprintable() or all(32 <= b < 127 for b in decrypted):
                results[f'xor_{xor_key:02x}'] = text
        except:
            pass
    
    return results


def try_subtract_decrypt(encrypted_bytes: list[int]) -> dict:
    """Versucht Subtraktions-Entschlüsselung."""
    results = {}
    
    for offset in range(256):
        decrypted = bytes([(b - offset) % 256 for b in encrypted_bytes])
        try:
            text = decrypted.decode('latin-1')
            if all(32 <= b < 127 for b in decrypted):
                results[f'sub_{offset}'] = text
        except:
            pass
    
    return results


def analyze_password(name: str, encrypted: str, known_plain: str = None):
    """Analysiert ein verschlüsseltes Passwort."""
    print(f"\n{'='*60}")
    print(f"Analyse: {name}")
    print(f"Verschlüsselt: {encrypted}")
    if known_plain:
        print(f"Bekannter Klartext: {known_plain}")
    print(f"{'='*60}")
    
    try:
        enc_bytes = parse_encrypted(encrypted)
        print(f"\nBytes ({len(enc_bytes)}): {enc_bytes}")
        print(f"Als Hex: {' '.join(f'{b:02x}' for b in enc_bytes)}")
        print(f"Als ASCII (printable): {''.join(chr(b) if 32 <= b < 127 else '.' for b in enc_bytes)}")
        
        if known_plain:
            plain_bytes = [ord(c) for c in known_plain]
            print(f"\nKlartext-Bytes ({len(plain_bytes)}): {plain_bytes}")
            
            if len(enc_bytes) == len(plain_bytes):
                print("\n--- Längen stimmen überein! ---")
                xor_key = [e ^ p for e, p in zip(enc_bytes, plain_bytes)]
                print(f"XOR-Key: {xor_key}")
                print(f"XOR-Key als ASCII: {''.join(chr(k) if 32 <= k < 127 else f'[{k}]' for k in xor_key)}")
                
                # Prüfe ob Key ein Muster hat
                if len(set(xor_key)) == 1:
                    print(f">>> EINFACHER XOR mit Key {xor_key[0]} (0x{xor_key[0]:02x})!")
            else:
                print(f"\n--- Längenunterschied: {len(enc_bytes)} vs {len(plain_bytes)} ---")
        
        # Versuche Standard-Entschlüsselungen
        xor_results = try_xor_decrypt(enc_bytes, known_plain)
        if xor_results:
            print("\nXOR-Versuche:")
            for k, v in xor_results.items():
                print(f"  {k}: {v}")
        
    except Exception as e:
        print(f"Fehler: {e}")


def find_correct_parse(encrypted: str, target_length: int) -> list[int]:
    """
    Findet das korrekte Parsing für eine gegebene Ziellänge.
    Verwendet Backtracking.
    """
    if not encrypted.startswith("001:"):
        return []
    
    data = encrypted[4:]
    
    def backtrack(s, current):
        if not s:
            return current if len(current) == target_length else None
        if len(current) >= target_length:
            return None
        
        # Versuche 3, 2, 1 Stellen
        for length in [3, 2, 1]:
            if len(s) >= length:
                num = int(s[:length])
                if num <= 255:
                    result = backtrack(s[length:], current + [num])
                    if result is not None:
                        return result
        return None
    
    return backtrack(data, [])


def main():
    print("="*60)
    print("IWM FinanzOffice Passwort-Analyse")
    print("="*60)
    
    # BEKANNTES PAAR: Itzehoer
    known_encrypted = "001:081181101004231027002064125036059148055130008047"
    known_plain = "Lecko2243xDS"
    
    print(f"\n>>> BEKANNTES PAAR:")
    print(f"    Verschlüsselt: {known_encrypted}")
    print(f"    Klartext: {known_plain} ({len(known_plain)} Zeichen)")
    
    # Parse mit 16 Bytes (bekannt aus vorheriger Analyse)
    all_bytes = parse_encrypted(known_encrypted)
    print(f"\n    Alle Bytes ({len(all_bytes)}): {all_bytes}")
    
    plain_bytes = [ord(c) for c in known_plain]
    print(f"    Klartext Bytes ({len(plain_bytes)}): {plain_bytes}")
    
    # Hypothese: Erste 4 Bytes sind Salt/IV
    if len(all_bytes) >= len(plain_bytes) + 4:
        salt = all_bytes[:4]
        enc_bytes = all_bytes[4:4+len(plain_bytes)]
        
        print(f"\n    HYPOTHESE: 4 Bytes Salt + {len(plain_bytes)} Bytes Daten")
        print(f"    Salt: {salt}")
        print(f"    Verschlüsselte Daten: {enc_bytes}")
        
        # XOR-Key berechnen
        xor_key = [e ^ p for e, p in zip(enc_bytes, plain_bytes)]
        print(f"\n    XOR-Key: {xor_key}")
        print(f"    XOR-Key als Zeichen: {''.join(chr(k) if 32 <= k < 127 else f'[{k}]' for k in xor_key)}")
        
        # Prüfe auf Konstante
        unique_keys = set(xor_key)
        if len(unique_keys) == 1:
            print(f"\n    >>> EINFACHER XOR! Konstanter Key = {xor_key[0]} (0x{xor_key[0]:02x})")
        else:
            print(f"\n    Verschiedene XOR-Werte: {len(unique_keys)}")
            # Prüfe ob Key vom Salt abhängt
            print(f"    Salt-Summe: {sum(salt)}")
            print(f"    Salt XOR: {salt[0] ^ salt[1] ^ salt[2] ^ salt[3]}")
            
            # Prüfe auf Muster
            diffs = [xor_key[i+1] - xor_key[i] for i in range(len(xor_key)-1)]
            print(f"    Key-Differenzen: {diffs}")
    
    # Hypothese 2: Letzte 4 Bytes sind Checksum
    if len(all_bytes) >= len(plain_bytes) + 4:
        enc_bytes2 = all_bytes[:len(plain_bytes)]
        checksum = all_bytes[len(plain_bytes):]
        
        print(f"\n    HYPOTHESE 2: {len(plain_bytes)} Bytes Daten + Checksum")
        print(f"    Verschlüsselte Daten: {enc_bytes2}")
        print(f"    Checksum: {checksum}")
        
        xor_key2 = [e ^ p for e, p in zip(enc_bytes2, plain_bytes)]
        print(f"    XOR-Key: {xor_key2}")
        
        unique_keys2 = set(xor_key2)
        if len(unique_keys2) == 1:
            print(f"\n    >>> EINFACHER XOR! Konstanter Key = {xor_key2[0]} (0x{xor_key2[0]:02x})")
    
    # Teste verschiedene Algorithmen
    print("\n" + "="*60)
    print("ALGORITHMUS-TESTS")
    print("="*60)
    
    salt = all_bytes[:4]
    enc_data = all_bytes[4:4+len(plain_bytes)]
    
    # Test 1: enc = plain + salt[i%4] (mod 256)
    print("\n--- Test 1: Addition mit Salt ---")
    test1 = [(enc_data[i] - salt[i % 4]) % 256 for i in range(len(enc_data))]
    test1_str = ''.join(chr(b) if 32 <= b < 127 else '?' for b in test1)
    print(f"    Ergebnis: {test1_str}")
    print(f"    Bytes: {test1}")
    
    # Test 2: enc = plain XOR salt[i%4]
    print("\n--- Test 2: XOR mit Salt ---")
    test2 = [enc_data[i] ^ salt[i % 4] for i in range(len(enc_data))]
    test2_str = ''.join(chr(b) if 32 <= b < 127 else '?' for b in test2)
    print(f"    Ergebnis: {test2_str}")
    print(f"    Bytes: {test2}")
    
    # Test 3: enc = plain XOR (salt[i%4] + i)
    print("\n--- Test 3: XOR mit Salt+Index ---")
    test3 = [enc_data[i] ^ ((salt[i % 4] + i) % 256) for i in range(len(enc_data))]
    test3_str = ''.join(chr(b) if 32 <= b < 127 else '?' for b in test3)
    print(f"    Ergebnis: {test3_str}")
    
    # Test 4: enc = plain + (salt[i%4] + i) (mod 256)
    print("\n--- Test 4: Addition mit Salt+Index ---")
    test4 = [(enc_data[i] - (salt[i % 4] + i)) % 256 for i in range(len(enc_data))]
    test4_str = ''.join(chr(b) if 32 <= b < 127 else '?' for b in test4)
    print(f"    Ergebnis: {test4_str}")
    
    # Test 5: Rolling XOR mit erstem Salt-Byte
    print("\n--- Test 5: Rolling XOR ---")
    key = salt[0]
    test5 = []
    for i, b in enumerate(enc_data):
        decrypted = b ^ key
        test5.append(decrypted)
        key = (key + 1) % 256  # Rolling
    test5_str = ''.join(chr(b) if 32 <= b < 127 else '?' for b in test5)
    print(f"    Ergebnis: {test5_str}")
    
    # Test 6: Subtrahiere konstant von Index
    print("\n--- Test 6: Subtraktion mit Index ---")
    for base in [0, 27, 51, 81, 128, 155]:
        test6 = [(enc_data[i] - base - i) % 256 for i in range(len(enc_data))]
        test6_str = ''.join(chr(b) if 32 <= b < 127 else '?' for b in test6)
        if all(32 <= b < 127 for b in test6):
            print(f"    Base {base}: {test6_str} ***MATCH***")
    
    if len(enc_bytes) == len(plain_bytes):
        print("\n    >>> LÄNGEN STIMMEN ÜBEREIN!")
        
        # XOR-Key berechnen
        xor_key = [e ^ p for e, p in zip(enc_bytes, plain_bytes)]
        print(f"    XOR-Key: {xor_key}")
        
        # Prüfe auf Konstante
        if len(set(xor_key)) == 1:
            print(f"\n    >>> EINFACHER XOR! Key = {xor_key[0]} (0x{xor_key[0]:02x})")
        else:
            # Prüfe auf Muster
            print(f"\n    XOR-Key Muster-Analyse:")
            print(f"    Unique Values: {sorted(set(xor_key))}")
            
            # Prüfe ob es ein rotierender Key ist
            for key_len in range(1, min(8, len(xor_key))):
                is_repeating = True
                for i in range(len(xor_key)):
                    if xor_key[i] != xor_key[i % key_len]:
                        is_repeating = False
                        break
                if is_repeating:
                    print(f"    >>> ROTIERENDER KEY mit Länge {key_len}: {xor_key[:key_len]}")
                    break
    else:
        print(f"\n    Längenunterschied: {len(enc_bytes)} vs {len(plain_bytes)}")
    
    # Jetzt alle anderen entschlüsseln
    print("\n" + "="*60)
    print("ENTSCHLÜSSELUNG ALLER PASSWÖRTER")
    print("="*60)
    
    # XOR-Key aus bekanntem Paar
    xor_key = [e ^ p for e, p in zip(enc_bytes, plain_bytes)]
    
    all_passwords = {
        "A237860 (AXA 1)": "001:048161068157089205104255238229245",
        "A237860 (AXA 2)": "001:032145036093217205104255238229245",
        "A175966 (AXA)": "001:058172050161047167032073161116210214",
        "u.weimert (VEMA)": "001:074186080251235248230229167152001065091197",
        "uwe.weimert (Rhion)": "001:050154070159097183160041048171099163083",
        "U.Weimert (VEMA Pwd)": "001:081166139241238231221210163117210197133046081",
        "VEMA-3527-00 (Basler)": "001:082197099009253020101198157085176",
        "1004695 (Helvetia)": "001:030144010065176041150042119244251010016063101184",
        "FTB2707 (Gothaer)": "001:040167095211176100233156072161121006024073152067086185169099231",
        "weimerta (Swiss Life)": "001:075189159048135226000221227249255015039081",
        "info@acencia.de (AIG)": "001:066163049186102237214219126061084245",
        "info@acencia.de (KS Auxilia)": "001:077191104253232024024086186138035082140067160",
        "105421 (Domcura)": "001:024129037089198147061108007218242195206106036021043100",
        "9170760 (Adam Riese)": "001:059176110250201220137097139088138097",
        "tqversicherungsmakler (DEURAG)": "001:082222140074182109223215121015046",
        "35327 (K&M)": "001:038152026097176136066128017053120",
        "05025000 (Concordia)": "001:079177096235197182090221238",
        "341891 (Dialog Leben)": "001:024129037089198147061108007218242195206106036021043100",
        "TQVE55_user (INNOSYS)": "001:077158121212175168031130010022071",
    }
    
    for name, encrypted in all_passwords.items():
        try:
            enc = parse_encrypted(encrypted)
            # Versuche mit dem berechneten XOR-Key
            # Der Key könnte länger sein, also erweitern/wiederholen
            if len(xor_key) > 0:
                extended_key = (xor_key * ((len(enc) // len(xor_key)) + 1))[:len(enc)]
                decrypted = bytes([e ^ k for e, k in zip(enc, extended_key)])
                try:
                    text = decrypted.decode('latin-1')
                    if all(32 <= b < 127 for b in decrypted):
                        print(f"\n{name}:")
                        print(f"  Entschlüsselt: {text}")
                    else:
                        print(f"\n{name}:")
                        print(f"  Bytes: {list(decrypted)}")
                        print(f"  Teilweise lesbar: {text}")
                except:
                    print(f"\n{name}: Dekodierung fehlgeschlagen")
        except Exception as e:
            print(f"\n{name}: Fehler - {e}")


if __name__ == "__main__":
    main()

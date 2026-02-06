"""
Atomare Datei-Operationen fuer sichere Datei-Verarbeitung.

Dieses Modul stellt Thread-sichere, atomare Operationen bereit:
- safe_atomic_write: Schreibt Dateien via Staging
- safe_atomic_move: Verschiebt Dateien atomar
- verify_file_integrity: Prueft Dateiintegritaet
"""

import os
import shutil
import hashlib
import tempfile
import logging
from pathlib import Path
from typing import Optional, Tuple
from contextlib import contextmanager

logger = logging.getLogger(__name__)


def calculate_file_hash(filepath: str, algorithm: str = 'sha256') -> str:
    """
    Berechnet den Hash einer Datei.
    
    Args:
        filepath: Pfad zur Datei
        algorithm: Hash-Algorithmus (default: sha256)
        
    Returns:
        Hex-String des Hash-Werts
    """
    hasher = hashlib.new(algorithm)
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_file_integrity(filepath: str, expected_size: Optional[int] = None,
                          expected_hash: Optional[str] = None) -> Tuple[bool, str]:
    """
    Prueft die Integritaet einer Datei.
    
    Args:
        filepath: Pfad zur Datei
        expected_size: Erwartete Dateigroesse in Bytes (optional)
        expected_hash: Erwarteter SHA256-Hash (optional)
        
    Returns:
        Tuple (is_valid, reason)
    """
    if not os.path.exists(filepath):
        return (False, "Datei existiert nicht")
    
    actual_size = os.path.getsize(filepath)
    
    if expected_size is not None and actual_size != expected_size:
        return (False, f"Groesse falsch: erwartet {expected_size}, tatsaechlich {actual_size}")
    
    if expected_hash is not None:
        actual_hash = calculate_file_hash(filepath)
        if actual_hash != expected_hash:
            return (False, f"Hash falsch: erwartet {expected_hash[:16]}..., tatsaechlich {actual_hash[:16]}...")
    
    return (True, "OK")


def safe_atomic_write(content: bytes, target_path: str,
                      staging_dir: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
    """
    Schreibt Inhalt atomar in eine Datei.
    
    Ablauf:
    1. Schreibt in temporaere .tmp Datei im Staging-Verzeichnis
    2. Verifiziert Groesse
    3. Atomic rename ins finale Ziel
    
    Args:
        content: Zu schreibender Inhalt
        target_path: Finaler Zielpfad
        staging_dir: Staging-Verzeichnis (default: gleiches Verzeichnis wie target)
        
    Returns:
        Tuple (success, message, content_hash)
    """
    target = Path(target_path)
    staging = Path(staging_dir) if staging_dir else target.parent
    
    # Staging-Verzeichnis erstellen falls noetig
    staging.mkdir(parents=True, exist_ok=True)
    
    # Temporaere Datei mit eindeutigem Namen
    tmp_path = staging / f".tmp_{target.name}_{os.getpid()}"
    
    try:
        # 1. In tmp schreiben
        with open(tmp_path, 'wb') as f:
            f.write(content)
        
        # 2. Groesse verifizieren
        actual_size = os.path.getsize(tmp_path)
        if actual_size != len(content):
            os.remove(tmp_path)
            return (False, f"Schreibfehler: {actual_size} vs {len(content)} Bytes", None)
        
        # 3. Hash berechnen
        content_hash = calculate_file_hash(str(tmp_path))
        
        # 4. Zielverzeichnis erstellen falls noetig
        target.parent.mkdir(parents=True, exist_ok=True)
        
        # 5. Atomic move (rename ist atomar auf gleichem Filesystem)
        # os.replace ist atomar und ueberschreibt existierende Dateien
        os.replace(str(tmp_path), str(target_path))
        
        logger.debug(f"Atomic write erfolgreich: {target_path} ({actual_size} Bytes)")
        return (True, "OK", content_hash)
        
    except Exception as e:
        # Aufraumen bei Fehler
        if tmp_path.exists():
            try:
                os.remove(tmp_path)
            except:
                pass
        logger.error(f"Atomic write fehlgeschlagen: {e}")
        return (False, str(e), None)


def safe_atomic_move(source_path: str, target_path: str) -> Tuple[bool, str]:
    """
    Verschiebt eine Datei atomar.
    
    Wenn source und target auf gleichem Filesystem: os.replace (atomar)
    Sonst: copy + verify + delete (nicht ganz atomar, aber sicher)
    
    Args:
        source_path: Quellpfad
        target_path: Zielpfad
        
    Returns:
        Tuple (success, message)
    """
    source = Path(source_path)
    target = Path(target_path)
    
    if not source.exists():
        return (False, "Quelldatei existiert nicht")
    
    try:
        # Zielverzeichnis erstellen
        target.parent.mkdir(parents=True, exist_ok=True)
        
        # Versuche atomares rename
        try:
            os.replace(str(source), str(target))
            logger.debug(f"Atomic move (rename): {source} -> {target}")
            return (True, "OK (atomic rename)")
        except OSError:
            # Verschiedene Filesystems - copy+verify+delete
            pass
        
        # Fallback: Copy + Verify + Delete
        source_hash = calculate_file_hash(str(source))
        source_size = source.stat().st_size
        
        # Copy
        shutil.copy2(str(source), str(target))
        
        # Verify
        is_valid, reason = verify_file_integrity(
            str(target), 
            expected_size=source_size,
            expected_hash=source_hash
        )
        
        if not is_valid:
            # Aufraumen
            if target.exists():
                os.remove(target)
            return (False, f"Verifikation fehlgeschlagen: {reason}")
        
        # Delete source
        os.remove(source)
        
        logger.debug(f"Atomic move (copy+verify+delete): {source} -> {target}")
        return (True, "OK (copy+verify+delete)")
        
    except Exception as e:
        logger.error(f"Atomic move fehlgeschlagen: {e}")
        return (False, str(e))


@contextmanager
def staging_context(staging_dir: Optional[str] = None):
    """
    Context Manager fuer Staging-Operationen.
    
    Erstellt ein temporaeres Staging-Verzeichnis das am Ende aufgeraeumt wird.
    
    Usage:
        with staging_context() as staging:
            tmp_file = staging / "myfile.tmp"
            ...
    """
    if staging_dir:
        staging = Path(staging_dir)
        staging.mkdir(parents=True, exist_ok=True)
        yield staging
    else:
        with tempfile.TemporaryDirectory(prefix="bipro_staging_") as tmpdir:
            yield Path(tmpdir)

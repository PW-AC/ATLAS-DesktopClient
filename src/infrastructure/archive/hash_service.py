"""
Infrastructure-Adapter: Hash-Berechnung und Dateiintegritaet.

Wrappt die bestehenden Funktionen aus services/atomic_ops.
"""

from typing import Optional, Tuple

from services.atomic_ops import (
    calculate_file_hash as _calculate_file_hash,
    verify_file_integrity as _verify_file_integrity,
)


class HashService:
    """Implementiert IHashService."""

    def calculate_file_hash(
        self, filepath: str, algorithm: str = 'sha256',
    ) -> str:
        return _calculate_file_hash(filepath, algorithm=algorithm)

    def verify_file_integrity(
        self, filepath: str, *,
        expected_size: Optional[int] = None,
        expected_hash: Optional[str] = None,
    ) -> Tuple[bool, str]:
        return _verify_file_integrity(
            filepath,
            expected_size=expected_size,
            expected_hash=expected_hash,
        )

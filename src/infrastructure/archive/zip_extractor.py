"""
Infrastructure-Adapter: ZIP-Extraktion.

Wrappt die bestehenden Funktionen aus services/zip_handler.
"""

from typing import Optional

from services.zip_handler import (
    is_zip_file as _is_zip_file,
    extract_zip_contents as _extract_zip_contents,
    ZipExtractResult,
)


class ZipExtractor:
    """Implementiert IZipExtractor."""

    def is_zip_file(self, file_path: str) -> bool:
        return _is_zip_file(file_path)

    def extract_zip_contents(
        self, zip_path: str, *,
        temp_dir: Optional[str] = None,
        api_client=None,
    ) -> ZipExtractResult:
        return _extract_zip_contents(
            zip_path, temp_dir=temp_dir, api_client=api_client,
        )

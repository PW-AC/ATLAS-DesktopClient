import unittest
from unittest.mock import MagicMock, patch
import sys
import os
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))

from services.document_processor import DocumentProcessor
from services.empty_page_detector import get_empty_pages
from api.documents import Document

class TestPdfOptimization(unittest.TestCase):

    def setUp(self):
        # Mock API client and dependencies
        self.mock_api_client = MagicMock()
        self.processor = DocumentProcessor(self.mock_api_client)
        # Mock internal methods to avoid external calls
        self.processor._check_and_log_empty_pages = MagicMock()
        # Mock _extract_full_text carefully
        self.processor._extract_full_text = MagicMock(return_value=("text", 1))

        self.mock_doc = Document(
            id=1,
            filename="unique_test.pdf",
            original_filename="test.pdf",
            mime_type="application/pdf",
            file_size=1024,
            source_type="manual_upload",
            is_gdv=False,
            created_at="2023-01-01",
            box_type="eingang",
            processing_status="pending"
        )

    def test_get_empty_pages_opens_file_when_doc_none(self):
        """Test that get_empty_pages opens file if pdf_doc is None."""
        mock_fitz = MagicMock()
        mock_doc_obj = MagicMock()
        mock_doc_obj.__len__.return_value = 1
        mock_fitz.open.return_value = mock_doc_obj

        with patch.dict(sys.modules, {'fitz': mock_fitz}):
            get_empty_pages("path/to/test.pdf", pdf_doc=None)

            mock_fitz.open.assert_called_once_with("path/to/test.pdf")
            mock_doc_obj.close.assert_called_once()

    def test_get_empty_pages_uses_provided_doc(self):
        """Test that get_empty_pages uses provided doc and DOES NOT close it."""
        mock_fitz = MagicMock()
        mock_doc_obj = MagicMock()
        mock_doc_obj.__len__.return_value = 1

        with patch.dict(sys.modules, {'fitz': mock_fitz}):
            get_empty_pages("path/to/test.pdf", pdf_doc=mock_doc_obj)

            mock_fitz.open.assert_not_called()
            mock_doc_obj.close.assert_not_called()

    def test_extract_full_text_opens_file_when_doc_none(self):
        """Test that _extract_full_text opens file if pdf_doc is None."""
        mock_fitz = MagicMock()
        mock_doc_obj = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "content"
        mock_doc_obj.__iter__.return_value = iter([mock_page])
        mock_fitz.open.return_value = mock_doc_obj

        with patch.dict(sys.modules, {'fitz': mock_fitz}):
            processor = DocumentProcessor(self.mock_api_client)
            processor._extract_full_text("path/to/test.pdf", pdf_doc=None)

            mock_fitz.open.assert_called_once_with("path/to/test.pdf")
            mock_doc_obj.close.assert_called_once()

    def test_extract_full_text_uses_provided_doc(self):
        """Test that _extract_full_text uses provided doc and DOES NOT close it."""
        mock_fitz = MagicMock()
        mock_doc_obj = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "content"
        mock_doc_obj.__iter__.return_value = iter([mock_page])

        with patch.dict(sys.modules, {'fitz': mock_fitz}):
            processor = DocumentProcessor(self.mock_api_client)
            processor._extract_full_text("path/to/test.pdf", pdf_doc=mock_doc_obj)

            mock_fitz.open.assert_not_called()
            mock_doc_obj.close.assert_not_called()

    def test_process_pdf_content_optimized_flow(self):
        """
        Verify that _process_pdf_content_optimized:
        1. Opens the PDF exactly once.
        2. Calls helper methods with the opened doc.
        3. Closes the PDF (via context manager).
        """
        mock_fitz = MagicMock()
        mock_doc_obj = MagicMock()
        mock_fitz.open.return_value.__enter__.return_value = mock_doc_obj

        with patch.dict(sys.modules, {'fitz': mock_fitz}):
            # Call the method
            self.processor._process_pdf_content_optimized(self.mock_doc, "path/to/test.pdf")

            # 1. Verify open called once
            mock_fitz.open.assert_called_once_with("path/to/test.pdf")

            # 2. Verify helpers called with the doc object
            self.processor._check_and_log_empty_pages.assert_called_once_with(
                self.mock_doc, "path/to/test.pdf", pdf_doc=mock_doc_obj
            )
            self.processor._extract_full_text.assert_called_once_with(
                "path/to/test.pdf", pdf_doc=mock_doc_obj
            )

            # 3. Verify close (context manager exit)
            mock_fitz.open.return_value.__exit__.assert_called()

if __name__ == '__main__':
    unittest.main()

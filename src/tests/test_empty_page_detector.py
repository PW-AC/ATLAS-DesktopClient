
import unittest
from unittest.mock import MagicMock
import sys
import os

# Mock requests if not installed, to allow running tests in minimal environment
try:
    import requests
except ImportError:
    sys.modules["requests"] = MagicMock()

# Add src to path
sys.path.insert(0, os.path.abspath('src'))

from services.empty_page_detector import _is_pixmap_blank

class TestEmptyPageDetector(unittest.TestCase):

    def create_mock_pix(self, data):
        mock_pix = MagicMock()
        mock_pix.samples = data
        return mock_pix

    def test_pure_white(self):
        # 1000 pixels, all white
        # This is below sampling threshold (10000), so it tests full scan logic
        data = b'\xff' * 3000
        pix = self.create_mock_pix(data)
        self.assertTrue(_is_pixmap_blank(pix))

    def test_pure_black(self):
        # 1000 pixels, all black
        data = b'\x00' * 3000
        pix = self.create_mock_pix(data)
        self.assertFalse(_is_pixmap_blank(pix))

    def test_noise_on_white(self):
        # 1000 pixels, mostly white, some noise
        # 99% white, 1% black
        num_pixels = 1000
        num_bytes = num_pixels * 3
        data = bytearray(b'\xff' * num_bytes)

        # Add some noise
        for i in range(0, num_bytes, 100):
            data[i] = 0

        pix = self.create_mock_pix(bytes(data))
        self.assertFalse(_is_pixmap_blank(pix))

    def test_large_white_sampled(self):
        # Test sampling logic with large data > 10000
        # 5000 pixels = 15000 bytes > 10000 threshold
        data = b'\xff' * 15000
        pix = self.create_mock_pix(data)
        self.assertTrue(_is_pixmap_blank(pix))

    def test_large_noise_sampled(self):
        # Large data with noise, to ensure sampling catches it (statistically)
        # 5000 pixels
        num_bytes = 15000
        data = bytearray(b'\xff' * num_bytes)

        # Add significant noise (e.g. half black)
        for i in range(0, num_bytes, 2):
            data[i] = 0

        pix = self.create_mock_pix(bytes(data))
        self.assertFalse(_is_pixmap_blank(pix))

if __name__ == '__main__':
    unittest.main()

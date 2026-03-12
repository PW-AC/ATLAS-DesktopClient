"""Stellt sicher dass src/ im sys.path ist, damit Domain-/Service-Importe funktionieren."""
import sys
import os

_src_dir = os.path.join(os.path.dirname(__file__), '..')
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

"""
BiPro API Client Module

Kommunikation mit dem Strato PHP-Backend.
"""

from .client import APIClient
from .auth import AuthAPI
from .documents import DocumentsAPI
from .gdv_api import GDVAPI

__all__ = ['APIClient', 'AuthAPI', 'DocumentsAPI', 'GDVAPI']

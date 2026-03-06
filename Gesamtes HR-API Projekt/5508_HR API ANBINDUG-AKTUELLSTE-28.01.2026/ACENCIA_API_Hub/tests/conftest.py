"""
pytest Konfiguration und Fixtures für ACENCIA Hub Tests.

SECURITY FIX SV-011: Test-Framework einrichten
"""
import pytest
import os
import sys
import tempfile
import json

# Füge das Projektverzeichnis zum Pfad hinzu
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from acencia_hub.app import app


@pytest.fixture
def client():
    """
    Erstellt einen Flask-Test-Client.
    
    Konfiguriert die App für Tests:
    - TESTING=True
    - Temporäre Dateien für users.json und employers.json
    """
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False  # CSRF für Tests deaktivieren
    
    # Temporäres Verzeichnis für Testdaten
    with tempfile.TemporaryDirectory() as tmpdir:
        # Erstelle Test-Benutzer
        users_file = os.path.join(tmpdir, 'users.json')
        test_users = [
            {
                "username": "testmaster",
                "password_hash": "pbkdf2:sha256:600000$test$hash",  # Wird in Tests überschrieben
                "kuerzel": "TM",
                "color": "blue",
                "is_master": True
            },
            {
                "username": "testuser",
                "password_hash": "pbkdf2:sha256:600000$test$hash",
                "kuerzel": "TU",
                "color": "green",
                "is_master": False,
                "allowed_employers": []
            }
        ]
        with open(users_file, 'w') as f:
            json.dump(test_users, f)
        
        yield app.test_client()


@pytest.fixture
def authenticated_client(client):
    """
    Ein Test-Client mit eingeloggtem Master-Benutzer.
    """
    with client.session_transaction() as session:
        session['user_id'] = 'testmaster'
        session['user_info'] = {
            'username': 'testmaster',
            'kuerzel': 'TM',
            'is_master': True,
            'color': 'blue',
            'theme': 'light'
        }
    return client

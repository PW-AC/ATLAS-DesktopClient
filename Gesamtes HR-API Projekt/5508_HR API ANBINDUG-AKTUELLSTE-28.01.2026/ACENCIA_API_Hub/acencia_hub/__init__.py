"""
Acencia Hub - Multi-HR Integrator Web-Anwendung

Dieses Modul enthält die Hauptanwendung für den Acencia Hub, eine Flask-basierte
Web-Anwendung, die verschiedene HR-Provider APIs (wie Personio und HRworks) 
verbindet, um Mitarbeiterdaten abzurufen und zu verwalten.

Die Anwendung dient als zentrales Dashboard zur Anzeige von Mitarbeiterinformationen,
Statistiken, Datenexporten und dem Vergleich historischer Datensnapshots.

Hauptkomponenten:
- EmployerStore: Singleton-Klasse für Arbeitgeber-Datenpersistenz
- BaseProvider: Abstrakte Basisklasse für alle HR-Provider
- HRworksProvider: Implementierung für HRworks API
- PersonioProvider: Implementierung für Personio API
- SageHrProvider: Mock-Provider für SageHR
- ProviderFactory: Factory für Provider-Instanzen
- Flask-App mit umfassenden Routen für UI und API

Features:
- Arbeitgeber-Verwaltung (Mandanten)
- Mitarbeiterübersicht und -details
- Statistik-Dashboard (Standard und Langzeit)
- Standard- und Delta-SCS-Exporte
- Snapshot-Management und -Vergleich
- Benutzerverwaltung und Authentifizierung
- Theme-Unterstützung (Hell/Dunkel)
- Automatische Updates über GitHub

Autor: Acencia Team
Version: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "Acencia Team"
__description__ = "Multi-HR Integrator Web-Anwendung"

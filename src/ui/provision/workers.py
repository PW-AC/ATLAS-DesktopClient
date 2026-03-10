# -*- coding: utf-8 -*-
"""
KOMPATIBILITAETS-MODUL: Re-exportiert alle Worker aus der
zentralen Infrastructure-Schicht.

Neuer Code sollte direkt importieren:
    from infrastructure.threading.provision_workers import XyzWorker

Dieses Modul existiert nur, damit bestehende Imports
    from ui.provision.workers import XyzWorker
weiterhin funktionieren.
"""

# flake8: noqa: F401
from infrastructure.threading.provision_workers import (
    # Dashboard
    DashboardLoadWorker,
    PerformanceLoadWorker,
    BeraterDetailWorker,
    # Abrechnungslaeufe (VU-Import)
    VuBatchesLoadWorker,
    VuParseFileWorker,
    VuImportWorker,
    # Provisionspositionen
    PositionsLoadWorker,
    AuditLoadWorker,
    IgnoreWorker,
    RawDataLoadWorker,
    # Provisions-Detail-Aktionen
    OverrideWorker,
    OverrideResetWorker,
    NoteWorker,
    MappingCreateWorker,
    # Zuordnung & Klaerfaelle
    ClearanceLoadWorker,
    MappingSyncWorker,
    MatchSearchWorker,
    # Verteilschluessel & Rollen
    VerteilschluesselLoadWorker,
    SaveEmployeeWorker,
    SaveModelWorker,
    # Auszahlungen & Reports
    AuszahlungenLoadWorker,
    AuszahlungenPositionenWorker,
    AbrechnungGenerateWorker,
    AbrechnungStatusWorker,
    # Freie Provisionen
    FreeCommissionLoadWorker,
    FreeCommissionSaveWorker,
    FreeCommissionDeleteWorker,
    # Xempus Contracts
    XempusContractsLoadWorker,
    XempusDetailLoadWorker,
    # Xempus Insight
    EmployerLoadWorker,
    EmployerDetailWorker,
    EmployeePageLoadWorker,
    EmployeeDetailWorker,
    XempusStatsLoadWorker,
    XempusBatchesLoadWorker,
    XempusImportWorker,
    XempusDiffLoadWorker,
    StatusMappingLoadWorker,
    # Statement Export & E-Mail
    StatementExportWorker,
    StatementBatchExportWorker,
    StatementEmailWorker,
    StatementBatchEmailWorker,
)

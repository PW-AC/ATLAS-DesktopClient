"""
BiPro API - SmartScan Versand und E-Mail-Konten

API-Clients fuer SmartScan-Dokumentenversand per E-Mail
und die Verwaltung von E-Mail-Konten (SMTP/IMAP).
"""

from typing import Dict, List, Optional
import logging

from .client import APIClient, APIError

logger = logging.getLogger(__name__)


class SmartScanAPI:
    """
    API-Client fuer SmartScan Versand und Historie.
    
    Verwendung:
        smartscan = SmartScanAPI(client)
        settings = smartscan.get_settings()
        result = smartscan.send(mode='selected', document_ids=[1, 2, 3])
    """
    
    def __init__(self, client: APIClient):
        self.client = client
    
    # ================================================================
    # Einstellungen
    # ================================================================
    
    def get_settings(self) -> Dict:
        """
        Laedt die aktuellen SmartScan-Einstellungen.
        
        Returns:
            Dict mit Einstellungen (z.B. email_account_id,
            subject_template, body_template, etc.)
        """
        try:
            response = self.client.get('/smartscan/settings')
            if response.get('success'):
                data = response['data']
                # API gibt {"settings": {...}} zurueck - inneres Dict extrahieren
                if isinstance(data, dict) and 'settings' in data:
                    return data['settings']
                return data
        except APIError as e:
            logger.error(f"Fehler beim Laden der SmartScan-Einstellungen: {e}")
            raise
        return {}
    
    def update_settings(self, data: Dict) -> Dict:
        """
        Speichert SmartScan-Einstellungen (Admin).
        
        Args:
            data: Dict mit Einstellungs-Feldern
            
        Returns:
            Die aktualisierten Einstellungen
        """
        try:
            response = self.client.put('/admin/smartscan/settings', json_data=data)
            if response.get('success'):
                resp_data = response['data']
                # API gibt {"settings": {...}} zurueck - inneres Dict extrahieren
                if isinstance(resp_data, dict) and 'settings' in resp_data:
                    return resp_data['settings']
                return resp_data
        except APIError as e:
            logger.error(f"Fehler beim Speichern der SmartScan-Einstellungen: {e}")
            raise
        return {}
    
    # ================================================================
    # Versand
    # ================================================================
    
    def send(self, mode: str, document_ids: Optional[List[int]] = None,
             box_type: Optional[str] = None,
             client_request_id: Optional[str] = None,
             archive_after_send: Optional[bool] = None,
             recolor_after_send: Optional[bool] = None,
             recolor_color: Optional[str] = None) -> Dict:
        """
        Startet einen SmartScan-Versand-Job.
        
        Args:
            mode: Versand-Modus ('selected', 'box', 'all', etc.)
            document_ids: Liste von Dokument-IDs (bei mode='selected')
            box_type: Box-Typ (bei mode='box')
            client_request_id: Optionale Client-Request-ID fuer Idempotenz
            archive_after_send: Dokumente nach Versand archivieren (ueberschreibt Server-Setting)
            recolor_after_send: Dokumente nach Versand umfaerben (ueberschreibt Server-Setting)
            recolor_color: Zielfarbe fuer Umfaerbung (nur relevant wenn recolor_after_send=True)
            
        Returns:
            Dict mit job_id, status, total, processed, remaining
        """
        body: Dict = {'mode': mode}
        if document_ids is not None:
            body['document_ids'] = document_ids
        if box_type is not None:
            body['box_type'] = box_type
        if client_request_id is not None:
            body['client_request_id'] = client_request_id
        if archive_after_send is not None:
            body['archive_after_send'] = int(archive_after_send)
        if recolor_after_send is not None:
            body['recolor_after_send'] = int(recolor_after_send)
        if recolor_color is not None:
            body['recolor_color'] = recolor_color
        
        try:
            response = self.client.post('/smartscan/send', json_data=body, timeout=180)
            if response.get('success'):
                return response['data']
        except APIError as e:
            logger.error(f"Fehler beim Starten des SmartScan-Versands: {e}")
            raise
        return {}
    
    def process_chunk(self, job_id: int) -> Dict:
        """
        Verarbeitet den naechsten Chunk eines Versand-Jobs.
        
        Args:
            job_id: ID des Versand-Jobs
            
        Returns:
            Dict mit status, processed, remaining, errors[]
        """
        try:
            response = self.client.post(f'/smartscan/jobs/{job_id}/process', timeout=330)
            if response.get('success'):
                return response['data']
        except APIError as e:
            logger.error(f"Fehler beim Verarbeiten von Job {job_id}: {e}")
            raise
        return {}
    
    # ================================================================
    # Historie
    # ================================================================
    
    def get_jobs(self, status: Optional[str] = None, limit: int = 50,
                 offset: int = 0) -> List[Dict]:
        """
        Laedt die SmartScan Job-Historie.
        
        Args:
            status: Optional - Filtert nach Job-Status
            limit: Max. Anzahl Ergebnisse (Standard: 50)
            offset: Offset fuer Paginierung
            
        Returns:
            Liste von Job-Dicts
        """
        params = f'limit={limit}&offset={offset}'
        if status:
            params += f'&status={status}'
        
        try:
            response = self.client.get(f'/smartscan/jobs?{params}')
            if response.get('success'):
                return response['data'].get('jobs', [])
        except APIError as e:
            logger.error(f"Fehler beim Laden der SmartScan-Jobs: {e}")
            raise
        return []
    
    def get_job_details(self, job_id: int) -> Dict:
        """
        Laedt Job-Details mit Items und Emails.
        
        Args:
            job_id: ID des Jobs
            
        Returns:
            Dict mit Job-Details, Items und gesendeten Emails
        """
        try:
            response = self.client.get(f'/smartscan/jobs/{job_id}')
            if response.get('success'):
                return response['data']
        except APIError as e:
            logger.error(f"Fehler beim Laden der Job-Details {job_id}: {e}")
            raise
        return {}


class EmailAccountsAPI:
    """
    API-Client fuer E-Mail-Konten-Verwaltung (Admin).
    
    Verwendung:
        email_accounts = EmailAccountsAPI(client)
        accounts = email_accounts.get_accounts()
        result = email_accounts.test_connection(account_id=1)
    """
    
    def __init__(self, client: APIClient):
        self.client = client
    
    # ================================================================
    # CRUD
    # ================================================================
    
    def get_accounts(self) -> List[Dict]:
        """
        Laedt alle E-Mail-Konten (Admin).
        
        Returns:
            Liste von E-Mail-Konto-Dicts mit id, name, email,
            smtp_host, imap_host, is_active, etc.
        """
        try:
            response = self.client.get('/admin/email-accounts')
            if response.get('success'):
                return response['data'].get('accounts', [])
        except APIError as e:
            logger.error(f"Fehler beim Laden der E-Mail-Konten: {e}")
            raise
        return []
    
    def create_account(self, data: Dict) -> Dict:
        """
        Erstellt ein neues E-Mail-Konto (Admin).
        
        Args:
            data: Dict mit name, email, smtp_host, smtp_port,
                  smtp_user, smtp_password, imap_host, imap_port, etc.
                  
        Returns:
            Das erstellte E-Mail-Konto-Dict
        """
        try:
            response = self.client.post('/admin/email-accounts', json_data=data)
            if response.get('success'):
                return response['data'].get('account', {})
        except APIError as e:
            logger.error(f"Fehler beim Erstellen des E-Mail-Kontos: {e}")
            raise
        return {}
    
    def update_account(self, account_id: int, data: Dict) -> Dict:
        """
        Aktualisiert ein E-Mail-Konto (Admin).
        
        Args:
            account_id: ID des E-Mail-Kontos
            data: Dict mit zu aktualisierenden Feldern
            
        Returns:
            Das aktualisierte E-Mail-Konto-Dict
        """
        try:
            response = self.client.put(
                f'/admin/email-accounts/{account_id}', json_data=data
            )
            if response.get('success'):
                return response['data'].get('account', {})
        except APIError as e:
            logger.error(
                f"Fehler beim Aktualisieren des E-Mail-Kontos {account_id}: {e}"
            )
            raise
        return {}
    
    def delete_account(self, account_id: int) -> bool:
        """
        Deaktiviert ein E-Mail-Konto (Admin / Soft-Delete).
        
        Args:
            account_id: ID des E-Mail-Kontos
            
        Returns:
            True bei Erfolg
        """
        try:
            response = self.client.delete(f'/admin/email-accounts/{account_id}')
            return response.get('success', False)
        except APIError as e:
            logger.error(
                f"Fehler beim Deaktivieren des E-Mail-Kontos {account_id}: {e}"
            )
            raise
    
    def test_connection(self, account_id: int) -> Dict:
        """
        Testet die SMTP-Verbindung eines E-Mail-Kontos.
        
        Args:
            account_id: ID des E-Mail-Kontos
            
        Returns:
            Dict mit success (bool) und message (str)
        """
        try:
            response = self.client.post(
                f'/admin/email-accounts/{account_id}/test'
            )
            if response.get('success'):
                return response['data']
        except APIError as e:
            logger.error(
                f"Fehler beim Testen des E-Mail-Kontos {account_id}: {e}"
            )
            raise
        return {}
    
    # ================================================================
    # IMAP / Posteingang
    # ================================================================
    
    def poll_inbox(self, account_id: int) -> Dict:
        """
        Loest IMAP-Polling fuer ein E-Mail-Konto aus (Admin).
        IMAP kann lange dauern, daher 120s Timeout.
        
        Args:
            account_id: ID des E-Mail-Kontos
            
        Returns:
            Dict mit new_mails, new_attachments, filtered_out, errors[]
        """
        try:
            response = self.client.post(
                f'/admin/email-accounts/{account_id}/poll',
                timeout=120  # IMAP-Abruf kann lange dauern
            )
            if response.get('success'):
                return response['data']
        except APIError as e:
            logger.error(
                f"Fehler beim IMAP-Polling fuer Konto {account_id}: {e}"
            )
            raise
        return {}
    
    def get_inbox(self, page: int = 1, limit: int = 50,
                  status: Optional[str] = None,
                  search: Optional[str] = None) -> Dict:
        """
        Laedt empfangene Mails (Admin).
        
        Args:
            page: Seitennummer (Standard: 1)
            limit: Max. Anzahl pro Seite (Standard: 50)
            status: Optional - Filtert nach Mail-Status
            search: Optional - Suchbegriff (Betreff, Absender)
            
        Returns:
            Dict mit mails[], total, page, limit
        """
        params = f'page={page}&limit={limit}'
        if status:
            params += f'&status={status}'
        if search:
            params += f'&search={search}'
        
        try:
            response = self.client.get(f'/email-inbox?{params}')
            if response.get('success'):
                return response['data']
        except APIError as e:
            logger.error(f"Fehler beim Laden des Posteingangs: {e}")
            raise
        return {}
    
    def get_inbox_mail(self, inbox_id: int) -> Dict:
        """
        Laedt Mail-Details mit Anhaengen.
        
        Args:
            inbox_id: ID der empfangenen Mail
            
        Returns:
            Dict mit Mail-Details und attachments[]
        """
        try:
            response = self.client.get(f'/email-inbox/{inbox_id}')
            if response.get('success'):
                return response['data']
        except APIError as e:
            logger.error(f"Fehler beim Laden der Mail {inbox_id}: {e}")
            raise
        return {}
    
    def get_pending_attachments(self) -> List[Dict]:
        """
        Laedt alle unverarbeiteten Anhaenge.
        
        Returns:
            Liste von Anhang-Dicts mit id, filename, mime_type,
            file_size, inbox_mail_id, import_status, etc.
        """
        try:
            response = self.client.get('/email-inbox/pending-attachments')
            if response.get('success'):
                return response['data'].get('attachments', [])
        except APIError as e:
            logger.error(f"Fehler beim Laden der unverarbeiteten Anhaenge: {e}")
            raise
        return []
    
    def download_attachment(self, attachment_id: int, target_path: str) -> bool:
        """
        Laedt einen Anhang herunter und speichert ihn lokal.
        
        Args:
            attachment_id: ID des Anhangs
            target_path: Lokaler Zielpfad fuer die Datei
            
        Returns:
            True bei erfolgreichem Download
        """
        try:
            self.client.download_file(
                f'/email-inbox/attachments/{attachment_id}/download',
                target_path
            )
            return True
        except APIError as e:
            logger.error(
                f"Fehler beim Herunterladen des Anhangs {attachment_id}: {e}"
            )
            raise
    
    def mark_attachment_imported(self, attachment_id: int,
                                 document_id: int) -> bool:
        """
        Markiert einen Anhang als erfolgreich importiert.
        
        Args:
            attachment_id: ID des Anhangs
            document_id: ID des erstellten Dokuments im Archiv
            
        Returns:
            True bei Erfolg
        """
        data = {
            'import_status': 'imported',
            'document_id': document_id
        }
        try:
            response = self.client.put(
                f'/email-inbox/attachments/{attachment_id}/imported',
                json_data=data
            )
            return response.get('success', False)
        except APIError as e:
            logger.error(
                f"Fehler beim Markieren des Anhangs {attachment_id} "
                f"als importiert: {e}"
            )
            raise
    
    def mark_attachment_failed(self, attachment_id: int, error: str) -> bool:
        """
        Markiert einen Anhang als fehlgeschlagen.
        
        Args:
            attachment_id: ID des Anhangs
            error: Fehlerbeschreibung
            
        Returns:
            True bei Erfolg
        """
        data = {
            'import_status': 'failed',
            'error': error
        }
        try:
            response = self.client.put(
                f'/email-inbox/attachments/{attachment_id}/imported',
                json_data=data
            )
            return response.get('success', False)
        except APIError as e:
            logger.error(
                f"Fehler beim Markieren des Anhangs {attachment_id} "
                f"als fehlgeschlagen: {e}"
            )
            raise
    
    def mark_attachment_skipped(self, attachment_id: int) -> bool:
        """
        Markiert einen Anhang als uebersprungen.
        
        Args:
            attachment_id: ID des Anhangs
            
        Returns:
            True bei Erfolg
        """
        data = {
            'import_status': 'skipped'
        }
        try:
            response = self.client.put(
                f'/email-inbox/attachments/{attachment_id}/imported',
                json_data=data
            )
            return response.get('success', False)
        except APIError as e:
            logger.error(
                f"Fehler beim Markieren des Anhangs {attachment_id} "
                f"als uebersprungen: {e}"
            )
            raise

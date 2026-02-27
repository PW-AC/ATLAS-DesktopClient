"""
Document-Rules-Loader — Standalone-Funktionen fuer das Laden und Anwenden
von Dokumenten-Regeln (Duplikate, leere Seiten, Farbmarkierungen).

Extrahiert aus services/document_processor.py.
"""

import logging
from typing import Optional

from api.document_rules import DocumentRulesSettings

logger = logging.getLogger(__name__)

__all__ = [
    'load_rules',
    'apply_rules',
    'apply_duplicate_rule',
]


def load_rules(doc_rules_api) -> Optional[DocumentRulesSettings]:
    """Laedt Dokumenten-Regeln vom Server (einmal pro Verarbeitungslauf)."""
    try:
        rules = doc_rules_api.get_rules()
        if rules and rules.has_any_rule():
            logger.info(
                f"Dokumenten-Regeln geladen: "
                f"Datei-Dup={rules.file_dup_action}, "
                f"Content-Dup={rules.content_dup_action}, "
                f"Partial-Empty={rules.partial_empty_action}, "
                f"Full-Empty={rules.full_empty_action}"
            )
        else:
            logger.debug("Dokumenten-Regeln: Keine aktiven Regeln konfiguriert")
        return rules
    except Exception as e:
        logger.warning(f"Dokumenten-Regeln konnten nicht geladen werden: {e}")
        return None


def apply_rules(doc,
                rules: Optional[DocumentRulesSettings],
                docs_api,
                remove_empty_pages_fn=None) -> Optional[str]:
    """
    Wendet konfigurierte Dokumenten-Regeln an.

    Wird nach persist_ai_data() aufgerufen. Zu diesem Zeitpunkt sind
    alle relevanten Informationen verfuegbar:
    - doc.is_duplicate / doc.previous_version_id (Datei-Duplikat)
    - doc.content_duplicate_of_id (Inhaltsduplikat, nach persist_ai_data)
    - doc.empty_page_count / doc.total_page_count (nach _check_and_log_empty_pages)

    Args:
        doc: Das Dokument-Objekt
        rules: Geladene Dokumenten-Regeln (oder None)
        docs_api: DocumentsAPI-Instanz
        remove_empty_pages_fn: Callback fuer das Entfernen leerer Seiten

    Returns:
        Beschreibung der ausgefuehrten Aktion oder None
    """
    if not rules or not rules.has_any_rule():
        return None

    try:
        fresh_doc_data = docs_api.get_document(doc.id)
        if fresh_doc_data:
            doc = fresh_doc_data
    except Exception:
        pass

    action_taken = None

    # 1. Komplett leere Datei
    if doc.is_completely_empty:
        if rules.full_empty_action == 'delete':
            logger.info(f"Dokumenten-Regel: Komplett leere Datei {doc.id} wird geloescht")
            docs_api.delete_documents([doc.id])
            return 'full_empty_delete'
        elif rules.full_empty_action == 'color_file' and rules.full_empty_color:
            logger.info(f"Dokumenten-Regel: Komplett leere Datei {doc.id} wird markiert ({rules.full_empty_color})")
            docs_api.set_document_color(doc.id, rules.full_empty_color)
            action_taken = 'full_empty_color'

    # 2. Teilweise leere Seiten
    elif doc.has_empty_pages and not doc.is_completely_empty:
        if rules.partial_empty_action == 'remove_pages':
            logger.info(f"Dokumenten-Regel: Leere Seiten entfernen bei Dokument {doc.id}")
            if remove_empty_pages_fn:
                remove_empty_pages_fn(doc)
            action_taken = 'partial_empty_remove'
        elif rules.partial_empty_action == 'color_file' and rules.partial_empty_color:
            logger.info(f"Dokumenten-Regel: Datei {doc.id} mit leeren Seiten markiert ({rules.partial_empty_color})")
            docs_api.set_document_color(doc.id, rules.partial_empty_color)
            action_taken = 'partial_empty_color'

    # 3. Datei-Duplikat (gleiche SHA256-Pruefsumme)
    if doc.is_duplicate and doc.previous_version_id:
        if apply_duplicate_rule(
            doc, rules.file_dup_action, rules.file_dup_color,
            doc.previous_version_id, 'Datei-Duplikat', docs_api
        ):
            action_taken = action_taken or 'file_dup'

    # 4. Inhaltsduplikat (gleicher Text-Hash)
    if doc.is_content_duplicate and doc.content_duplicate_of_id:
        if apply_duplicate_rule(
            doc, rules.content_dup_action, rules.content_dup_color,
            doc.content_duplicate_of_id, 'Inhaltsduplikat', docs_api
        ):
            action_taken = action_taken or 'content_dup'

    return action_taken


def apply_duplicate_rule(doc,
                         action: str,
                         color: Optional[str],
                         original_id: int,
                         rule_type: str,
                         docs_api) -> bool:
    """
    Wendet eine Duplikat-Regel auf ein Dokument an.

    Returns:
        True wenn eine Aktion ausgefuehrt wurde, sonst False
    """
    if action == 'none':
        return False

    if action == 'color_both' and color:
        logger.info(f"Dokumenten-Regel: {rule_type} - Beide markieren ({color}): {doc.id} + {original_id}")
        docs_api.set_documents_color([doc.id, original_id], color)
        return True

    elif action == 'color_new' and color:
        logger.info(f"Dokumenten-Regel: {rule_type} - Neue Datei markieren ({color}): {doc.id}")
        docs_api.set_document_color(doc.id, color)
        return True

    elif action == 'delete_new':
        logger.info(f"Dokumenten-Regel: {rule_type} - Neue Datei loeschen: {doc.id}")
        docs_api.delete_documents([doc.id])
        return True

    elif action == 'delete_old':
        logger.info(f"Dokumenten-Regel: {rule_type} - Alte Datei loeschen: {original_id}")
        docs_api.delete_documents([original_id])
        return True

    return False

"""
Processing-History-Logger — Standalone-Funktionen fuer die Protokollierung
von Verarbeitungsschritten, Batch-Ergebnissen und Kosten.

Extrahiert aus services/document_processor.py.
"""

import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

__all__ = [
    'log_processing_step',
    'log_batch_complete',
    'log_delayed_costs',
    'persist_ai_data',
]


def log_processing_step(history_api,
                        document_id: int,
                        action: str,
                        new_status: str,
                        previous_status: Optional[str] = None,
                        success: bool = True,
                        error_message: Optional[str] = None,
                        classification_source: Optional[str] = None,
                        classification_result: Optional[str] = None,
                        action_details: Optional[dict] = None,
                        duration_ms: Optional[int] = None) -> None:
    """
    Protokolliert einen Verarbeitungsschritt in der History.

    Fehler beim Logging werden ignoriert, um die Verarbeitung nicht zu unterbrechen.
    """
    try:
        history_api.create(
            document_id=document_id,
            action=action,
            new_status=new_status,
            previous_status=previous_status,
            success=success,
            error_message=error_message,
            classification_source=classification_source,
            classification_result=classification_result,
            action_details=action_details,
            duration_ms=duration_ms
        )
    except Exception as e:
        logger.warning(f"History-Logging fehlgeschlagen fuer Dokument {document_id}: {e}")


def log_batch_complete(history_api,
                       batch_result: 'BatchProcessingResult') -> Optional[int]:
    """
    Loggt den Abschluss eines Batch-Verarbeitungslaufs in der Datenbank.

    Wird direkt nach Verarbeitungsende aufgerufen, OHNE Kosten
    (diese werden spaeter per log_delayed_costs nachgetragen).

    Returns:
        ID des History-Eintrags (fuer spaeteres Update) oder None
    """
    try:
        action_details = {
            'batch_type': 'inbox_processing',
            'total_documents': batch_result.total_documents,
            'successful_documents': batch_result.successful_documents,
            'failed_documents': batch_result.failed_documents,
            'duration_seconds': round(batch_result.duration_seconds, 2),
            'timestamp': datetime.now().isoformat(),
            'provider': batch_result.provider,
            'cost_pending': True
        }

        if batch_result.credits_before is not None:
            action_details['credits_before_usd'] = round(batch_result.credits_before, 6)
        if batch_result.total_cost_usd is not None and batch_result.total_cost_usd > 0:
            action_details['accumulated_cost_usd'] = round(batch_result.total_cost_usd, 6)
            action_details['cost_per_document_usd'] = round(batch_result.cost_per_document_usd or 0, 8)

        entry_id = history_api.create(
            document_id=None,
            action='batch_complete',
            new_status='completed',
            previous_status='processing',
            action_details=action_details,
            success=batch_result.failed_documents == 0,
            duration_ms=int(batch_result.duration_seconds * 1000),
            classification_source='batch_processor',
            classification_result=f'{batch_result.successful_documents}/{batch_result.total_documents} OK'
        )

        logger.debug(f"Batch-Abschluss geloggt (Kosten ausstehend): ID={entry_id}")
        return entry_id

    except Exception as e:
        logger.warning(f"Batch-Abschluss-Logging fehlgeschlagen: {e}")
        return None


def log_delayed_costs(history_api,
                      history_entry_id: int,
                      batch_result: 'BatchProcessingResult',
                      credits_after: float,
                      provider: str = 'openrouter') -> Optional[dict]:
    """
    Traegt die Kosten nachtraeglich in einen bestehenden History-Eintrag ein.

    Kosten-Quellen (nach Prioritaet):
    1. Akkumulierte Server-Kosten aus ai_requests (praezise, provider-unabhaengig)
    2. OpenRouter Balance-Diff (Fallback fuer OpenRouter)

    Args:
        history_api: ProcessingHistoryAPI-Instanz
        history_entry_id: ID des batch_complete History-Eintrags
        batch_result: Das BatchProcessingResult mit akkumulierten Kosten
        credits_after: Das Guthaben NACH der Verarbeitung (verzoegert abgefragt)
        provider: Aktiver Provider ('openrouter' oder 'openai')

    Returns:
        Dict mit berechneten Kosten oder None bei Fehler
    """
    try:
        successful_count = batch_result.successful_documents

        accumulated_cost = batch_result.total_cost_usd

        if accumulated_cost and accumulated_cost > 0:
            total_cost = accumulated_cost
            cost_source = 'accumulated'
        elif provider == 'openrouter' and batch_result.credits_before is not None:
            total_cost = batch_result.credits_before - (credits_after or 0)
            cost_source = 'balance_diff'
        else:
            total_cost = accumulated_cost or 0
            cost_source = 'accumulated_fallback'

        cost_per_doc = total_cost / successful_count if successful_count > 0 else (
            total_cost / batch_result.total_documents if batch_result.total_documents > 0 else 0
        )

        logger.info(f"=== KOSTEN-ZUSAMMENFASSUNG ({provider.upper()}, {cost_source}) ===")
        if provider == 'openrouter' and batch_result.credits_before is not None:
            logger.info(f"Guthaben vorher:  ${batch_result.credits_before:.6f} USD")
            logger.info(f"Guthaben nachher: ${credits_after:.6f} USD")
            balance_diff = batch_result.credits_before - (credits_after or 0)
            logger.info(f"Balance-Diff:     ${balance_diff:.6f} USD")
        logger.info(f"Server-Kosten:    ${accumulated_cost or 0:.6f} USD (aus model_pricing)")
        logger.info(f"Gesamtkosten:     ${total_cost:.6f} USD")
        if cost_per_doc:
            logger.info(f"Kosten/Dokument:  ${cost_per_doc:.8f} USD ({batch_result.total_documents} Dokumente)")
        logger.info(f"==========================================")

        cost_details = {
            'batch_type': 'cost_update',
            'reference_entry_id': history_entry_id,
            'provider': provider,
            'cost_source': cost_source,
            'accumulated_cost_usd': round(accumulated_cost or 0, 6),
            'credits_before_usd': round(batch_result.credits_before or 0, 6),
            'credits_after_usd': round(credits_after or 0, 6),
            'total_cost_usd': round(total_cost, 6),
            'cost_per_document_usd': round(cost_per_doc, 8),
            'total_documents': batch_result.total_documents,
            'successful_documents': successful_count,
            'failed_documents': batch_result.failed_documents,
            'duration_seconds': round(batch_result.duration_seconds, 2),
            'timestamp': datetime.now().isoformat(),
            'cost_pending': False
        }

        history_api.create(
            document_id=None,
            action='batch_cost_update',
            new_status='completed',
            previous_status='completed',
            action_details=cost_details,
            success=True,
            duration_ms=0,
            classification_source='cost_tracker',
            classification_result=f'${total_cost:.4f} USD ({successful_count} Dok.)'
        )

        return {
            'credits_before': batch_result.credits_before,
            'credits_after': credits_after,
            'total_cost_usd': total_cost,
            'cost_per_document_usd': cost_per_doc,
            'successful_documents': successful_count,
            'provider': provider,
            'cost_source': cost_source
        }

    except Exception as e:
        logger.warning(f"Verzoegertes Kosten-Logging fehlgeschlagen: {e}")
        return None


def persist_ai_data(docs_api,
                    doc,
                    extracted_text: str,
                    extracted_page_count: int,
                    ki_result: dict) -> bool:
    """
    Persistiert Volltext + KI-Daten in document_ai_data Tabelle.

    Laeuft NACH der Klassifikation/Rename/Archive. Ein Fehler hier
    bricht die Verarbeitung NICHT ab (wird im Aufrufer gefangen).

    Args:
        docs_api: DocumentsAPI-Instanz
        doc: Das verarbeitete Dokument
        extracted_text: Bereits extrahierter Volltext (alle Seiten)
        extracted_page_count: Anzahl Seiten mit tatsaechlichem Text
        ki_result: KI-Ergebnis mit optionalen _usage/_raw_response/_prompt_text

    Returns:
        True wenn erfolgreich gespeichert, sonst False
    """
    import hashlib

    extraction_method = 'text' if (extracted_text and extracted_text.strip()) else 'none'

    text_sha256 = None
    if extracted_text and extracted_text.strip():
        text_sha256 = hashlib.sha256(extracted_text.encode('utf-8')).hexdigest()

    ai_full_response = None
    ai_prompt_text = None
    ai_model = None
    ai_stage = None
    prompt_tokens = None
    completion_tokens = None
    total_tokens = None

    if ki_result and isinstance(ki_result, dict):
        raw_resp = ki_result.get('_raw_response')
        if raw_resp is not None:
            import json as _json
            if isinstance(raw_resp, dict):
                ai_full_response = _json.dumps(raw_resp, ensure_ascii=False)
            else:
                ai_full_response = str(raw_resp)

        prompt = ki_result.get('_prompt_text')
        if prompt is not None:
            import json as _json
            if isinstance(prompt, dict):
                ai_prompt_text = _json.dumps(prompt, ensure_ascii=False)
            else:
                ai_prompt_text = str(prompt)

        ai_model = ki_result.get('_ai_model')
        ai_stage = ki_result.get('_ai_stage')

        usage = ki_result.get('_usage', {})
        if usage:
            prompt_tokens = usage.get('prompt_tokens')
            completion_tokens = usage.get('completion_tokens')
            total_tokens = usage.get('total_tokens')

    text_char_count = len(extracted_text) if extracted_text else 0
    ai_response_char_count = len(ai_full_response) if ai_full_response else 0

    data = {
        'extracted_text': extracted_text if (extracted_text and extracted_text.strip()) else None,
        'extracted_text_sha256': text_sha256,
        'extraction_method': extraction_method,
        'extracted_page_count': extracted_page_count or 0,
        'ai_full_response': ai_full_response,
        'ai_prompt_text': ai_prompt_text,
        'ai_model': ai_model,
        'ai_prompt_version': 'v2.0.2',
        'ai_stage': ai_stage,
        'text_char_count': text_char_count if text_char_count > 0 else None,
        'ai_response_char_count': ai_response_char_count if ai_response_char_count > 0 else None,
        'prompt_tokens': prompt_tokens,
        'completion_tokens': completion_tokens,
        'total_tokens': total_tokens,
    }

    result = docs_api.save_ai_data(doc.id, data)
    if result:
        logger.debug(
            f"AI-Daten gespeichert fuer Dokument {doc.id} ({doc.original_filename}): "
            f"method={extraction_method}, pages={extracted_page_count}, "
            f"tokens={total_tokens}, stage={ai_stage}"
        )
        return True
    else:
        from i18n.de import AI_DATA_SAVE_FAILED
        logger.warning(AI_DATA_SAVE_FAILED.format(doc_id=doc.id))
        return False

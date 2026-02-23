"""
MTOM/XOP Multipart Parser

Parst MTOM/XOP Multipart Responses aus BiPRO 430 Transfer-Operationen.
Extrahiert Dokumente (PDFs, GDV-Dateien etc.) und Metadaten aus
MIME Multipart Messages.

Konsolidiert aus transfer_service.py und bipro_view.py (Schritt 1 Refactoring).
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


def extract_boundary(content_type: str) -> Optional[bytes]:
    """
    Extrahiert die Boundary aus dem Content-Type Header.
    
    Args:
        content_type: HTTP Content-Type Header Wert
        
    Returns:
        Boundary als bytes oder None wenn nicht gefunden
    """
    if not content_type:
        return None
    
    # Pattern: boundary="uuid:12345" oder boundary=uuid:12345
    # Auch mit Quotes oder ohne
    match = re.search(r'boundary="([^"]+)"', content_type, re.IGNORECASE)
    if not match:
        match = re.search(r'boundary=([^;\s]+)', content_type, re.IGNORECASE)
    
    if match:
        boundary = match.group(1)
        logger.debug(f"Boundary aus Content-Type Header extrahiert: {boundary}")
        return boundary.encode('utf-8')
    
    return None


def split_multipart(content: bytes, content_type: str = "") -> list:
    """
    Splittet MIME Multipart Content in Teile.
    
    Args:
        content: Raw bytes des Multipart-Contents
        content_type: HTTP Content-Type Header (empfohlen für korrekte Boundary)
        
    Returns:
        Liste der MIME-Parts
    """
    # Boundary aus Content-Type Header extrahieren (bevorzugt)
    boundary = extract_boundary(content_type)
    
    # Fallback: Boundary aus erster Zeile des Contents (legacy)
    if boundary is None:
        logger.debug("Keine Boundary im Header, versuche erste Zeile")
        first_line_end = content.find(b'\r\n')
        if first_line_end == -1:
            first_line_end = content.find(b'\n')
        
        if first_line_end == -1:
            logger.warning("Keine Boundary gefunden, gebe gesamten Content zurück")
            return [content]
        
        boundary = content[:first_line_end].strip()
        if boundary.startswith(b'--'):
            boundary = boundary[2:]
        logger.debug(f"Boundary aus erster Zeile: {boundary[:50]}...")
    
    logger.info(f"MTOM Boundary: {boundary[:50]}..." if len(boundary) > 50 else f"MTOM Boundary: {boundary}")
    
    # Nach Boundary splitten
    delimiter = b'--' + boundary
    parts = content.split(delimiter)
    
    logger.debug(f"Content nach Boundary-Split: {len(parts)} Teile")
    
    # Leere und End-Marker entfernen
    result = []
    for i, part in enumerate(parts):
        part = part.strip()
        if part and part != b'--' and not part.startswith(b'--'):
            # Header vom Body trennen
            header_end = part.find(b'\r\n\r\n')
            if header_end == -1:
                header_end = part.find(b'\n\n')
            
            if header_end != -1:
                result.append(part)
                logger.debug(f"Part {i}: {len(part)} Bytes")
    
    logger.info(f"MTOM: {len(result)} gültige Parts nach Filterung")
    return result


def parse_mtom_response(content: bytes, content_type: str = "") -> tuple:
    """
    Parst eine MTOM/XOP Multipart Response.
    
    Args:
        content: Raw bytes der MTOM Response
        content_type: HTTP Content-Type Header für Boundary-Extraktion
    
    Returns:
        (documents, metadata)
    """
    documents = []
    metadata = {}
    
    # Multipart aufteilen - Content-Type für korrekte Boundary übergeben
    parts = split_multipart(content, content_type)
    logger.info(f"MTOM: {len(parts)} Teil(e) gefunden")
    
    if not parts:
        return documents, metadata
    
    # Content-IDs und Binärdaten sammeln
    binary_parts = {}  # content_id -> (content_type, data)
    xml_part = None
    
    for part in parts:
        # Header und Body trennen - konsistent den tatsächlich gefundenen Separator verwenden
        header_end_crlf = part.find(b'\r\n\r\n')
        header_end_lf = part.find(b'\n\n')
        
        # Den früheren (korrekten) Separator wählen
        if header_end_crlf != -1 and (header_end_lf == -1 or header_end_crlf < header_end_lf):
            header_end = header_end_crlf
            separator_len = 4  # \r\n\r\n
        elif header_end_lf != -1:
            header_end = header_end_lf
            separator_len = 2  # \n\n
        else:
            logger.debug(f"Kein Header/Body-Separator in Part gefunden, überspringe")
            continue
        
        headers_raw = part[:header_end].decode('utf-8', errors='replace').lower()
        body = part[header_end + separator_len:]
        
        # Content-ID extrahieren - robusteres Pattern für verschiedene Varianten
        # Unterstützt: <cid>, cid, url-encoded cid, mit/ohne spitze Klammern
        cid_match = re.search(r'content-id:\s*<?([^>\s\r\n]+)>?', headers_raw)
        content_id = cid_match.group(1) if cid_match else None
        
        # URL-Decoding für Content-ID falls nötig (z.B. %40 -> @)
        if content_id and '%' in content_id:
            try:
                from urllib.parse import unquote
                content_id = unquote(content_id)
            except ImportError:
                pass
        
        # Content-Type extrahieren
        ct_match = re.search(r'content-type:\s*([^\s;]+)', headers_raw)
        part_content_type = ct_match.group(1) if ct_match else 'application/octet-stream'
        
        if 'xml' in part_content_type or 'soap' in part_content_type:
            xml_part = body
        elif content_id:
            # Trailing CRLF/LF konsistent strippen (Boundary-Artefakte)
            if body.endswith(b'\r\n'):
                body = body[:-2]
            elif body.endswith(b'\n'):
                body = body[:-1]
            
            # Magic-Byte-Validierung: Content-Type vs. tatsaechlicher Inhalt
            if 'pdf' in part_content_type and not body[:4].startswith(b'%PDF'):
                actual_magic = body[:8] if len(body) >= 8 else body
                logger.warning(
                    f"MTOM: Content-Type ist {part_content_type} aber Magic-Bytes "
                    f"sind {actual_magic!r} (kein %PDF). "
                    f"CID={content_id}, Size={len(body)} Bytes"
                )
            
            binary_parts[content_id] = (part_content_type, body)
            logger.info(f"MTOM Binary Part: {content_id}, Type: {part_content_type}, Size: {len(body)}")
    
    # XML parsen und Dokumente extrahieren
    if xml_part:
        xml_text = xml_part.decode('utf-8', errors='replace')
        logger.debug(f"MTOM XML Teil (erste 1000 Zeichen): {xml_text[:1000]}")
        
        # Dateiname aus XML extrahieren - VEMA verwendet verschiedene Namespace-Präfixe
        # a:, allg:, gevo:, oder ohne Präfix
        datei_pattern = r'<(?:gevo:|a:|allg:)?Datei[^>]*>(.*?)</(?:gevo:|a:|allg:)?Datei>'
        datei_matches = re.findall(datei_pattern, xml_text, re.DOTALL)
        
        logger.debug(f"Gefundene Datei-Blöcke: {len(datei_matches)}")
        
        if not datei_matches:
            # Alternatives Pattern - direkte Suche nach Dateiname und XOP
            # VEMA-Format: <a:Dateiname>...</a:Dateiname>
            filename_pattern = r'<(?:a:|allg:|gevo:)?Dateiname>([^<]+)</(?:a:|allg:|gevo:)?Dateiname>'
            filename_matches = re.findall(filename_pattern, xml_text)
            logger.debug(f"Gefundene Dateinamen: {filename_matches}")
            
            # XOP Include finden
            xop_pattern = r'<xop:Include\s+href="cid:([^"]+)"'
            xop_matches = re.findall(xop_pattern, xml_text)
            logger.debug(f"Gefundene XOP-Referenzen: {xop_matches}")
            
            for i, cid in enumerate(xop_matches):
                if cid in binary_parts:
                    part_content_type, data = binary_parts[cid]
                    filename = filename_matches[i] if i < len(filename_matches) else f'dokument_{i+1}.pdf'
                    
                    documents.append({
                        'filename': filename,
                        'content_bytes': data,
                        'mime_type': part_content_type
                    })
                    logger.info(f"Dokument extrahiert: {filename}, {len(data)} Bytes")
        else:
            for datei_xml in datei_matches:
                # VEMA verwendet a:Dateiname statt allg:Dateiname
                filename_match = re.search(r'<(?:a:|allg:|gevo:)?Dateiname>([^<]+)</(?:a:|allg:|gevo:)?Dateiname>', datei_xml)
                xop_match = re.search(r'href="cid:([^"]+)"', datei_xml)
                
                if xop_match:
                    cid = xop_match.group(1)
                    if cid in binary_parts:
                        part_content_type, data = binary_parts[cid]
                        filename = filename_match.group(1) if filename_match else f'dokument.pdf'
                        
                        documents.append({
                            'filename': filename,
                            'content_bytes': data,
                            'mime_type': part_content_type
                        })
                        logger.info(f"Dokument extrahiert: {filename}, {len(data)} Bytes")
        
        # Metadaten extrahieren - verschiedene Namespace-Präfixe
        kategorie_match = re.search(r'<(?:tran:|t:)?Kategorie>([^<]+)</(?:tran:|t:)?Kategorie>', xml_text)
        if kategorie_match:
            metadata['category'] = kategorie_match.group(1)
        
        vsnr_match = re.search(r'<(?:a:|allg:|t:)?Versicherungsscheinnummer>([^<]+)</(?:a:|allg:|t:)?Versicherungsscheinnummer>', xml_text)
        if vsnr_match:
            metadata['versicherungsschein_nr'] = vsnr_match.group(1)
    
    # Falls keine XOP-Referenzen, aber Binary Parts vorhanden
    if not documents and binary_parts:
        for cid, (part_content_type, data) in binary_parts.items():
            # Dateityp aus Magic Bytes ermitteln
            if data[:4] == b'%PDF':
                ext = 'pdf'
            elif data[:2] == b'\xff\xd8':
                ext = 'jpg'
            elif data[:8] == b'\x89PNG\r\n\x1a\n':
                ext = 'png'
            else:
                ext = 'bin'
            
            documents.append({
                'filename': f'dokument_{len(documents)+1}.{ext}',
                'content_bytes': data,
                'mime_type': part_content_type
            })
    
    # Debug-Logging bei 0 Dokumenten für Fehlersuche
    if not documents:
        logger.warning("MTOM: Keine Dokumente extrahiert!")
        logger.warning(f"  - Binary Parts gefunden: {len(binary_parts)}")
        logger.warning(f"  - XML Part vorhanden: {xml_part is not None}")
        if binary_parts:
            for cid, (ct, data) in binary_parts.items():
                logger.warning(f"  - Unzugeordneter Binary Part: CID={cid}, Type={ct}, Size={len(data)} Bytes")
        if xml_part:
            # Ersten Teil des XML ausgeben für Diagnose
            xml_preview = xml_part.decode('utf-8', errors='replace')[:2000]
            logger.warning(f"  - XML Preview: {xml_preview}")
    else:
        logger.info(f"MTOM: {len(documents)} Dokument(e) erfolgreich extrahiert")
        for doc in documents:
            logger.info(f"  - {doc['filename']}: {len(doc['content_bytes'])} Bytes, {doc['mime_type']}")
    
    return documents, metadata

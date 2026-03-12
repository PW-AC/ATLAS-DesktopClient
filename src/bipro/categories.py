"""
BiPRO Kategorien-Mapping

Übersetzt BiPRO-Kategorie-Codes (ST_KatalogGeVoArt) in lesbare Beschreibungen.
Basierend auf bipro-kataloge-2.6.0.xsd / bipro-datentypen-2.6.0.xsd.

Hierarchisches 9-stelliges Nummernschema:
  100 = Antragsprozesse
  110 = Partneränderungen
  120 = Vertragsänderungen
  130 = Vertragsbeendigung / Sonstiges
  140 = Inkasso-Störfälle
  150 = Schaden / Leistung
  160 = Bestandsauskunft
  170 = Provision / Courtage
  180 = Beschwerden
  190 = Bestandsübertragung
  200 = Abrechnung
  210 = Inkasso-Geschäftsvorfälle
"""

CATEGORY_NAMES = {
    # ── 100 - Antragsprozesse ──
    "100000000": "Sonstiger Antragsprozess",
    "100001000": "Antragsversand",
    "100001020": "Ergänzung bestehender Vertrag",
    "100001030": "Ersatzgeschäft",
    "100002000": "Eingangsbestätigung",
    "100002010": "Eingangsbestätigung - Antrag eingegangen",
    "100002020": "Eingangsbestätigung - Antrag in Bearbeitung",
    "100003000": "Vorläufige Deckungszusage",
    "100004000": "Ablehnung",
    "100004010": "Ablehnung - Vom Antragsteller eingestellt",
    "100004020": "Ablehnung - Vom Versicherer eingestellt",
    "100004050": "Ablehnung - Ablehnung Deckung",
    "100005000": "Nachfrage",
    "100005010": "Nachfrage - Anforderung Arztbericht",
    "100005040": "Nachfrage - Rückfrage technisch/rechtlich",
    "100005050": "Nachfrage - Zusätzliche Unterlagen",
    "100005081": "Nachfrage - Risikovoranfrage",
    "100005100": "Antragsanforderung aus Versicherungsbestätigung",
    "100006000": "Antwort auf Nachfrage",
    "100006001": "Antwort auf Risikovoranfrage",
    "100007000": "Policierung / Dokument erstellt",
    "100007010": "Policierung - Spätere Policierung wg. Vorausdatierung",
    "100008000": "Änderungsangebote",
    "100008010": "Erschwernisangebot / Risikozuschlag",
    "100008020": "Einschluss Zusatzversicherung / Änderungsantrag",
    "100009000": "Annahmebestätigung",
    "100010000": "Widerruf",

    # ── 110 - Partneränderungen ──
    "110000000": "Sonstige Partneränderung",
    "110000001": "Änderung allgemeine Partnerdaten",
    "110000002": "Änderung Partnernummer",
    "110002000": "Eingangsbestätigung",
    "110008000": "Rückmeldung/Nachfrage",
    "110009000": "Geschäftsvorfall erledigt",
    "110010000": "Namensänderung",
    "110011000": "Adressänderung",
    "110011001": "Neue Anschrift",
    "110011002": "Änderung der Anschrift",
    "110012000": "Änderung Kommunikationsdaten",
    "110013000": "Änderung persönliche Daten",
    "110014000": "Bestandswechsel / Bestandsverlust droht",
    "110015000": "Änderung Werbeerlaubnis",
    "110016001": "Änderung Freistellungsauftrag",

    # ── 120 - Vertragsänderungen ──
    "120000000": "Sonstige Vertragsänderung",
    "120002000": "Eingangsbestätigung",
    "120008000": "Rückmeldung/Nachfrage",
    "120009000": "Geschäftsvorfall erledigt",
    "120010000": "Vertragsumstellung",
    "120010001": "Altersumstellung / Erwachsenentarif",
    "120010002": "SF-Übertragung auf weiteres Fahrzeug",
    "120010003": "Ablauf Beitragszahlungsdauer",
    "120010004": "Risikoänderung",
    "120010005": "Kurzfristiger Einschluss/Änderung Deckung",
    "120010006": "Vertragssanierung",
    "120010007": "Änderung Vertragsstatus / Beihilferecht",
    "120010008": "Vertrag in der Abrufphase",
    "120010101": "Einschluss expliziter Fahrer",
    "120010102": "Änderung expliziter Fahrer",
    "120010106": "Kennzeichenänderung",
    "120010111": "Fahrzeugwechsel",
    "120010112": "Änderung Tarifierung",
    "120010113": "Änderung SF-Einstufung",
    "120011000": "Anforderung zusätzlicher Unterlagen",
    "120012000": "Widerspruch Police",
    "120013000": "Beginnverlegung",
    "120013001": "Änderung Versicherungsdauer",
    "120013002": "Änderung Zahltermin",
    "120014000": "Beitragsfreistellung",
    "120014005": "Beitragsreduktion/Beitragsfreistellung",
    "120014006": "Beitragserhöhung",
    "120014007": "Zuzahlung",
    "120015000": "Herabsetzung",
    "120016000": "Erhöhung",
    "120016001": "Besuchsauftrag (Beratungsbedarf)",
    "120017000": "Dynamik",
    "120017001": "Dynamikablehnung",
    "120017002": "Dynamikerhöhung",
    "120017003": "Dynamikausschluss",
    "120017004": "Dynamikeinschluss",
    "120017005": "Dynamikänderung",
    "120018000": "Änderung Zahlungsweise",
    "120019000": "Vorauszahlung",
    "120020000": "Abkürzung Versicherungsdauer durch Zuzahlung",
    "120020001": "Änderung Versicherungsdauer",
    "120021000": "Änderung Risikozuschlag / Klausel",
    "120021001": "Änderung Bedingungen",
    "120022000": "Tarifumstellung",
    "120022001": "Beitragsanpassung",
    "120022002": "Tarifliche Beitragsumstellung",
    "120023000": "Fondswechsel",
    "120024000": "Änderung Überschussart",
    "120025000": "Anwartschaft",
    "120026000": "Außerkraftsetzung",
    "120027000": "Wiederinkraftsetzung",
    "120028000": "Wechsel versicherte Person",
    "120028001": "Vertragstrennung",
    "120028002": "Vertragszusammenlegung",
    "120029000": "Neuordnung Vertrag erforderlich",
    "120030000": "Riester",
    "120031000": "Policendarlehen",
    "120032000": "Ruhepause",
    "120033001": "Änderung KH-Deckung",
    "120033002": "Einschluss KF-Deckung",
    "120033003": "Änderung KF-Deckung",
    "120033004": "Umstellung VK in TK",
    "120033005": "Umstellung TK in VK",
    "120033006": "Ausschluss KF-Deckung",
    "120033100": "Einschluss Deckung",
    "120033101": "Ausschluss Deckung",
    "120033104": "Änderung Versicherungssumme/Leistung",
    "120033107": "Änderung Selbstbeteiligung",
    "120900001": "Tod eines Partners",
    "120900002": "Anzeige Privatinsolvenz",

    # ── 130 - Vertragsbeendigung / Sonstiges ──
    "130000000": "Sonstiges",
    "130002000": "Eingangsbestätigung",
    "130008000": "Rückmeldung/Nachfrage",
    "130008010": "Prüfung Vorvertragliche Anzeigepflichtverletzung",
    "130009000": "Geschäftsvorfall erledigt",
    "130010000": "Abtretung",
    "130011000": "Pfändung",
    "130012000": "Verpfändung",
    "130013000": "Bezugsrecht",
    "130014000": "Bevollmächtigte",
    "130015000": "Vertragspartner-Wechsel",
    "130017001": "Zugang wegen Vermittlerwechsel",
    "130017002": "Abgang wegen Vermittlerwechsel",
    "130017006": "Bestandsverlust droht",
    "130018001": "Neuzugang wegen Übernahme",
    "130018002": "Abgang zu anderem Unternehmen",
    "130019001": "Änderung Unternehmensnummer",
    "130019002": "Änderung Vertragsnummer",
    "130100000": "Einstellung Datenlieferung (Code of Conduct)",
    "130100001": "Einstellung - Widerspruch durch Kunde",
    "130100002": "Einstellung - Widerruf Maklervollmacht",

    # ── 140 - Inkasso-Störfälle ──
    "140000000": "Sonstiger Inkasso-Störfall",
    "140002000": "Eingangsbestätigung",
    "140008000": "Rückmeldung",
    "140009000": "Geschäftsvorfall erledigt",
    "140010000": "Bankverbindung falsch",
    "140011000": "Bankverbindung fehlt",
    "140011100": "SEPA-Mandat fehlt",
    "140012000": "Beitragsrückstand",
    "140012001": "Beitragsrückstand - Bankretoure",
    "140012010": "Beitragsrückstand - Zahlungserinnerung",
    "140012020": "Mahnung Erstprämie",
    "140012021": "Mahnung Folgeprämie",
    "140012025": "Letzte Mahnung",
    "140012030": "Letzte Zahlungsaufforderung",
    "140012050": "Kündigungsankündigung",
    "140012051": "Kündigung / Folgebeitrag",
    "140012060": "Stornoandrohung",
    "140012068": "Stornierung und Abrechnung",
    "140012090": "Betriebsinformation",
    "140013000": "Beitragsrechnung",
    "140013001": "Beitragsrechnung Einzelvertrag",
    "140013002": "Beitragsrechnung Gruppenvertrag",
    "140014000": "Änderung Bankverbindung",
    "140015000": "Änderung Inkassoart",
    "140016000": "Änderung Beitragszahler",
    "140017000": "Ratenzahlung/Stundung",
    "140018000": "SEPA-Notifikation",

    # ── 150 - Schaden / Leistung ──
    "150000000": "Sonstiger Schaden/Leistung",
    "150000001": "Änderung Schadennummer",
    "150002001": "Deckungszusage erteilt",
    "150002002": "Deckungszusage abgelehnt",
    "150008000": "Rückmeldung/Nachfrage",
    "150010000": "Ablauf",
    "150011000": "Rente",
    "150011001": "Altersrente",
    "150011003": "BU-Rente",
    "150012000": "Leistung",
    "150012002": "Tod des Versicherten",
    "150012006": "Krankenleistung",
    "150012007": "Beitragsrückerstattung",
    "150013010": "Initiale Schadenmeldung",
    "150013020": "Nachmeldung Schadenumfang",
    "150013030": "Rückfrage zur Schadenmeldung",
    "150013035": "Antwort auf Rückfrage",
    "150013100": "Schadenanlage",
    "150013200": "Schadenänderung",
    "150013201": "Schadenänderung mit Zahlung",
    "150013300": "Schadenschließung",
    "150013301": "Schadenschließung mit Zahlung",
    "150013302": "Schadenablehnung",

    # ── 160-210 - Weitere Kategorien ──
    "160000000": "Bestandsauskunft",
    "170000000": "Provision / Courtage",
    "180000000": "Beschwerden",
    "190000000": "Bestandsübertragung",
    "200000000": "Abrechnung - Anforderung",
    "200010000": "Abrechnung - Lieferung",
    "210000000": "Inkasso-Geschäftsvorfälle",

    # ── Sonderwerte ──
    "GDV": "GDV-Bestandsdaten",
    "GEVO": "Geschäftsvorfall",
}

CATEGORY_SHORT_NAMES = {
    # 100 - Antragsprozesse
    "100000000": "Sonstiges",
    "100001000": "Antrag",
    "100002000": "Eingangsbestätigung",
    "100003000": "Deckungszusage",
    "100004000": "Ablehnung",
    "100005000": "Nachfrage",
    "100006000": "Antwort",
    "100007000": "Policierung",
    "100008000": "Änderungsangebot",
    "100009000": "Annahme",
    "100010000": "Widerruf",

    # 110 - Partneränderungen
    "110000000": "Partneränderung",
    "110010000": "Name",
    "110011000": "Adresse",
    "110012000": "Kommunikation",
    "110013000": "Persönlich",
    "110014000": "Bestandswechsel",

    # 120 - Vertragsänderungen
    "120000000": "Vertragsänderung",
    "120010000": "Umstellung",
    "120011000": "Unterlagen",
    "120012000": "Widerspruch",
    "120013000": "Beginn",
    "120014000": "Beitragsfreist.",
    "120015000": "Herabsetzung",
    "120016000": "Erhöhung",
    "120017000": "Dynamik",
    "120018000": "Zahlungsweise",
    "120022000": "Tarifumstellung",
    "120023000": "Fondswechsel",
    "120026000": "Außerkraftsetz.",
    "120027000": "Wiederinkrafts.",

    # 130 - Vertragsbeendigung
    "130000000": "Sonstiges",
    "130010000": "Abtretung",
    "130011000": "Pfändung",
    "130015000": "Partnerwechsel",
    "130017001": "Zugang VM-Wechsel",
    "130017002": "Abgang VM-Wechsel",
    "130100000": "Einst. Datenl.",

    # 140 - Inkasso
    "140000000": "Inkasso",
    "140010000": "Bank falsch",
    "140011000": "Bank fehlt",
    "140012000": "Rückstand",
    "140013000": "Rechnung",
    "140014000": "Bankänderung",
    "140018000": "SEPA",

    # 150 - Schaden
    "150000000": "Schaden/Leistung",
    "150010000": "Ablauf",
    "150011000": "Rente",
    "150012000": "Leistung",
    "150013010": "Schadenmeldung",
    "150013100": "Schadenanlage",
    "150013200": "Schadenänderung",
    "150013300": "Schadenschließung",

    # 160-210
    "160000000": "Bestandsauskunft",
    "170000000": "Provision",
    "180000000": "Beschwerde",
    "190000000": "Bestandsübertr.",
    "200000000": "Abr. Anforderung",
    "200010000": "Abr. Lieferung",
    "210000000": "Inkasso-GeVo",
}

# Hauptkategorien für Präfix-Fallback
_PREFIX_NAMES = {
    "100": "Antragsprozess",
    "110": "Partneränderung",
    "120": "Vertragsänderung",
    "130": "Vertragsbeendigung",
    "140": "Inkasso-Störfall",
    "150": "Schaden/Leistung",
    "160": "Bestandsauskunft",
    "170": "Provision/Courtage",
    "180": "Beschwerde",
    "190": "Bestandsübertragung",
    "200": "Abrechnung",
    "210": "Inkasso-GeVo",
}


def get_category_name(code: str) -> str:
    """
    Gibt den lesbaren Namen für einen Kategorie-Code zurück.

    Lookup-Reihenfolge:
      1. Exakter Match in CATEGORY_NAMES
      2. Präfix-Match (erste 3 Stellen) mit Angabe des Codes
      3. Code selbst als Fallback
    """
    if not code:
        return "Unbekannt"

    if code in CATEGORY_NAMES:
        return CATEGORY_NAMES[code]

    prefix = code[:3] if len(code) >= 3 else code
    if prefix in _PREFIX_NAMES:
        return f"{_PREFIX_NAMES[prefix]} ({code})"

    return code


def get_category_short_name(code: str) -> str:
    """
    Gibt einen Kurznamen für die Tabellenanzeige zurück.

    Lookup-Reihenfolge:
      1. Exakter Match in CATEGORY_SHORT_NAMES
      2. Exakter Match in CATEGORY_NAMES (als Fallback)
      3. Präfix-Match
      4. Code selbst
    """
    if not code:
        return "-"

    if code in CATEGORY_SHORT_NAMES:
        return CATEGORY_SHORT_NAMES[code]

    if code in CATEGORY_NAMES:
        return CATEGORY_NAMES[code]

    prefix = code[:3] if len(code) >= 3 else code
    if prefix in _PREFIX_NAMES:
        return _PREFIX_NAMES[prefix]

    return code


def get_category_icon(code: str) -> str:
    """Gibt ein Icon/Emoji für die Kategorie zurück."""
    if not code:
        return "📄"

    prefix = code[:3] if len(code) >= 3 else ""

    icons = {
        "100": "📋",
        "110": "👤",
        "120": "🔄",
        "130": "🚫",
        "140": "💳",
        "150": "⚠️",
        "160": "📊",
        "170": "💰",
        "180": "📩",
        "190": "📦",
        "200": "🧾",
        "210": "💳",
    }

    return icons.get(prefix, "📄")

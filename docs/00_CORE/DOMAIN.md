# Domänenmodell - GDV Tool

## Übersicht

Das GDV-Datenmodell bildet die Struktur von Versicherungsdaten ab, wie sie im GDV-Standard (Gesamtverband der Deutschen Versicherungswirtschaft) definiert ist.

```
┌─────────────────────────────────────────────────────────────────────┐
│                           GDVData                                    │
│  (Container für alle geladenen Daten)                               │
├─────────────────────────────────────────────────────────────────────┤
│  file_meta: FileMeta         (aus 0001)                             │
│  customers: List[Customer]   (aus 0100)                             │
│  contracts: List[Contract]   (aus 0200)                             │
└───────────────────────────────────────┬─────────────────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
                    ▼                   ▼                   ▼
            ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
            │   Customer    │  │   Contract    │  │   FileMeta    │
            │   (0100)      │  │   (0200)      │  │   (0001)      │
            └───────┬───────┘  └───────┬───────┘  └───────────────┘
                    │                  │
                    │          ┌───────┴───────┐
                    │          │               │
                    │          ▼               ▼
                    │  ┌───────────────┐ ┌───────────────┐
                    │  │     Risk      │ │   Coverage    │
                    │  │    (0210)     │ │    (0220)     │
                    │  └───────────────┘ └───────────────┘
                    │
                    ▼
            [Verknüpfung via VSNR]
```

---

## Entitäten

### FileMeta (Satzart 0001)

Metadaten der GDV-Datei (Vorsatz/Header).

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | str | UUID |
| `vu_nummer` | str | VU-Nummer (5-stellig, z.B. "12345") |
| `absender` | str | Name der Versicherung |
| `adressat` | str | Empfänger (Vermittler) |
| `erstellungsdatum_von` | str | Datum (YYYY-MM-DD) |
| `erstellungsdatum_bis` | str | Gültig bis |
| `release_stand` | str | GDV-Version (z.B. "2025.01") |
| `vermittler_nr` | str | Vermittlernummer |
| `source_file` | str | Originaler Dateipfad |
| `encoding` | str | Erkanntes Encoding |

---

### Customer (Satzart 0100)

Kundendaten / Partnerdaten.

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | str | UUID |
| `vu_nummer` | str | VU-Nummer |
| `versicherungsschein_nr` | str | Vertragsnummer (Schlüssel zur Verknüpfung) |
| `folge_nr` | str | Folgenummer |
| `anrede` | Anrede | Enum: OHNE, HERR, FRAU, FIRMA |
| `name1` | str | Nachname oder Firmenname |
| `name2` | str | Vorname (bei Personen) |
| `name3` | str | Zusatz/Weiterer Vorname |
| `titel` | str | Dr., Prof., etc. |
| `strasse` | str | Straße + Hausnummer |
| `plz` | str | Postleitzahl |
| `ort` | str | Stadt |
| `land` | str | Länderkennzeichen (D, A, CH) |
| `geburtsdatum` | str | YYYY-MM-DD |
| `adresstyp` | str | 01=VN, 02=VP, etc. |

**Properties**:
- `vollstaendiger_name`: Formatierter Name inkl. Anrede/Titel
- `adresse_einzeilig`: "Straße, PLZ Ort"

**Teildatensätze (0100)**:
- TD1: Adressdaten (Standard)
- TD2: Kundennummern, Referenznummern
- TD3: Kommunikationsdaten (meist leer)
- TD4: Bankverbindung (BIC, IBAN)
- TD5: Zusatzdaten

---

### Contract (Satzart 0200)

Versicherungsvertrag.

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | str | UUID |
| `vu_nummer` | str | VU-Nummer |
| `versicherungsschein_nr` | str | Eindeutige Vertragsnummer |
| `sparte` | str | Spartenschlüssel (010, 020, ...) |
| `vermittler_nr` | str | Vermittlernummer |
| `vertragsstatus` | Vertragsstatus | Enum: LEBEND, STORNIERT, RUHEND, BEITRAGSFREI |
| `vertragsbeginn` | str | YYYY-MM-DD |
| `vertragsende` | str | YYYY-MM-DD |
| `hauptfaelligkeit` | str | YYYY-MM-DD |
| `zahlungsweise` | Zahlungsweise | Enum: JAEHRLICH, MONATLICH, etc. |
| `gesamtbeitrag_brutto` | float | Bruttobeitrag in EUR |
| `gesamtbeitrag_netto` | float | Nettobeitrag in EUR |
| `waehrung` | str | "EUR" |
| `risks` | List[Risk] | Wagnisse (aus 0210) |
| `coverages` | List[Coverage] | Deckungen (aus 0220) |
| `customer` | Customer | Verknüpfter Kunde |

**Properties**:
- `sparte_name`: Klartext der Sparte ("Leben", "Kranken", etc.)
- `contract_key`: "VU|VSNR|Sparte" (eindeutiger Schlüssel)
- `gesamtdeckungssumme`: Summe aller Deckungen

---

### Risk (Satzart 0210)

Wagnis / Risiko (spartenspezifisch).

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | str | UUID |
| `vu_nummer` | str | VU-Nummer |
| `versicherungsschein_nr` | str | Vertragsreferenz |
| `sparte` | str | Spartenschlüssel |
| `satznummer` | str | Teildatensatz (1-9) |
| `wagnis_art` | str | Wagnisart-Code |
| `wagnis_nr` | str | Laufende Wagnisnummer |
| `lfd_person_nr` | str | Personenreferenz |
| `person_rolle` | PersonenRolle | Enum: VERSICHERTE_PERSON, etc. |
| `risikobeginn` | str | YYYY-MM-DD |
| `risikoende` | str | YYYY-MM-DD |
| `versicherungssumme` | float | In EUR |
| `beitrag` | float | Beitrag für dieses Wagnis |
| `tarif_bezeichnung` | str | Tarifname |
| `dynamik_prozent` | float | Dynamik in % |
| `selbstbeteiligung` | float | In EUR |

---

### Coverage (Satzart 0220)

Deckung / Leistungsbaustein.

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | str | UUID |
| `vu_nummer` | str | VU-Nummer |
| `versicherungsschein_nr` | str | Vertragsreferenz |
| `sparte` | str | Spartenschlüssel |
| `satznummer` | str | Teildatensatz |
| `wagnis_art` | str | Wagnisart-Code |
| `wagnis_nr` | str | Wagnisnummer |
| `lfd_deckung_nr` | str | Laufende Deckungsnummer |
| `deckungsart` | Deckungsart | Enum: HAUPTDECKUNG, ZUSATZDECKUNG, BAUSTEIN |
| `deckungsbezeichnung` | str | Name der Deckung |
| `deckungssumme` | float | In EUR |
| `deckungsbeitrag` | float | Beitrag für diese Deckung |
| `deckungsbeginn` | str | YYYY-MM-DD |
| `deckungsende` | str | YYYY-MM-DD |
| `selbstbeteiligung` | float | In EUR |
| `leistungsart` | Leistungsart | Enum: KAPITAL, RENTE, KOMBINIERT |

**Teildatensätze (0220)**:
- TD1: Versicherte Person (Name, Vorname, Geburtsdatum)
- TD6: Bezugsberechtigte Person

---

## Enums

### Anrede
```python
class Anrede(Enum):
    OHNE = "0"      # Keine Anrede / Firma
    HERR = "1"      # Herr
    FRAU = "2"      # Frau
    FIRMA = "3"     # Firma mit Ansprechpartner
```

### Vertragsstatus
```python
class Vertragsstatus(Enum):
    UNBEKANNT = "0"
    LEBEND = "1"        # Aktiv
    STORNIERT = "2"     # Gekündigt/Storniert
    RUHEND = "3"        # Ruhend
    BEITRAGSFREI = "4"  # Beitragsfrei gestellt
```

### Zahlungsweise
```python
class Zahlungsweise(Enum):
    UNBEKANNT = "0"
    JAEHRLICH = "1"         # 1x jährlich
    HALBJAEHRLICH = "2"     # 2x jährlich
    VIERTELJAEHRLICH = "3"  # 4x jährlich
    MONATLICH = "4"         # 12x jährlich
    EINMALBEITRAG = "5"     # Einmalig
```

### PersonenRolle
```python
class PersonenRolle(Enum):
    UNBEKANNT = "00"
    VERSICHERTE_PERSON = "01"
    BEZUGSBERECHTIGTER = "02"
    BEITRAGSZAHLER = "03"
    PRAEMIENTRAEGER = "04"
```

### Deckungsart
```python
class Deckungsart(Enum):
    UNBEKANNT = "000"
    HAUPTDECKUNG = "001"
    ZUSATZDECKUNG = "002"
    BAUSTEIN = "003"
```

### Leistungsart
```python
class Leistungsart(Enum):
    UNBEKANNT = "00"
    KAPITAL = "01"      # Kapitalleistung
    RENTE = "02"        # Rentenleistung
    KOMBINIERT = "03"   # Kombiniert
```

---

## Sparten

| Code | Bezeichnung |
|------|-------------|
| 000 | Allgemein |
| 010 | Leben |
| 020 | Kranken |
| 030 | Unfall |
| 040 | Haftpflicht |
| 050 | Kraftfahrt |
| 051 | Kfz-Haftpflicht |
| 052 | Kfz-Kasko |
| 053 | Kfz-Unfall |
| 060 | Rechtsschutz |
| 070 | Hausrat |
| 080 | Wohngebäude |
| 090 | Transport/Reise |
| 100 | Gewerbe-Sach |
| 110 | Technische Vers. |
| 120 | Berufshaftpflicht |
| 130 | D&O |

---

## Verknüpfungen

### Contract ↔ Customer

Verträge werden über `versicherungsschein_nr` mit Kunden verknüpft:

```python
# In GDVData.link_customers_to_contracts():
for contract in self.contracts:
    customers = self.get_customers_for_contract(contract.versicherungsschein_nr)
    if customers:
        # Adresstyp 01 = Versicherungsnehmer
        for cust in customers:
            if cust.adresstyp == "01":
                contract.customer = cust
                break
```

### Contract ↔ Risk/Coverage

Wagnisse und Deckungen werden beim Mapping direkt zum passenden Vertrag hinzugefügt:

```python
# Schlüssel: VU|VSNR|Sparte
key = make_contract_key(risk.vu_nummer, risk.versicherungsschein_nr, risk.sparte)
if key in contracts_dict:
    contracts_dict[key].add_risk(risk)
```

---

## Validierungsregeln

### Pflichtfelder

| Satzart | Pflichtfelder |
|---------|---------------|
| 0001 | satzart, vu_nummer |
| 0100 | satzart, vu_nummer, versicherungsschein_nr |
| 0200 | satzart, vu_nummer, versicherungsschein_nr, sparte |
| 0210 | satzart, vu_nummer, versicherungsschein_nr, sparte |
| 0220 | satzart, vu_nummer, versicherungsschein_nr, sparte |

### Datumsformate

- **GDV-Format**: TTMMJJJJ (z.B. "15052025" = 15.05.2025)
- **Internes Format**: YYYY-MM-DD (ISO 8601)
- **Konvertierung**: `parse_date_yyyymmdd()` in `gdv_parser.py`

### Beträge

- **GDV-Format**: Implizite Dezimalstellen (z.B. "000012345" mit 2 Dezimalen = 123.45)
- **Internes Format**: float
- **Konvertierung**: `parse_amount_with_decimals()` in `mapper.py`

---

## Beispiel: Daten laden und navigieren

```python
from src.parser.gdv_parser import parse_file
from src.domain.mapper import map_parsed_file_to_gdv_data

# Datei laden
parsed = parse_file("testdata/sample.gdv")
gdv_data = map_parsed_file_to_gdv_data(parsed)

# Statistiken
print(gdv_data.get_statistics())
# {'customers_count': 2, 'contracts_count': 2, 'risks_count': 2, ...}

# Verträge durchlaufen
for contract in gdv_data.contracts:
    print(f"Vertrag: {contract.versicherungsschein_nr}")
    print(f"  Sparte: {contract.sparte_name}")
    print(f"  Status: {contract.vertragsstatus.to_display()}")
    print(f"  Beitrag: {contract.gesamtbeitrag_brutto:,.2f} EUR")
    
    if contract.customer:
        print(f"  Kunde: {contract.customer.vollstaendiger_name}")
    
    for risk in contract.risks:
        print(f"  Risiko: {risk.wagnis_art}, Summe: {risk.versicherungssumme:,.2f}")
    
    for cov in contract.coverages:
        print(f"  Deckung: {cov.deckungsbezeichnung}")
```

---

## GDV-Zustandsautomat

### Vertragsstatus-Übergänge (typisch)

```
                    ┌─────────┐
                    │ Antrag  │
                    │  (0)    │
                    └────┬────┘
                         │ Policierung
                         ▼
    ┌─────────────────────────────────────────┐
    │               Lebend/Aktiv              │
    │                  (1)                    │
    └───┬──────────┬──────────┬──────────┬───┘
        │          │          │          │
        │ Beitrag  │ Ruhen-   │ Kündi-   │ Ablauf
        │ -frei    │ stellung │ gung     │
        ▼          ▼          ▼          │
   ┌─────────┐ ┌─────────┐ ┌─────────┐  │
   │Beitrags-│ │ Ruhend  │ │Storniert│  │
   │ frei(4) │ │  (3)    │ │  (2)    │  │
   └─────────┘ └─────────┘ └─────────┘  │
                                        │
                                        ▼
                               [Ende der Laufzeit]
```

---

---

## Provisionsmanagement-Datenmodell

### Uebersicht

Das Provisionsdatenmodell bildet die Geschaeftsfuehrer-Ebene der Provisionsabrechnung ab: VU-Provisionslisten werden importiert, automatisch Vertraegen zugeordnet und in Berater-Splits aufgeteilt.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Provisionsmanagement                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  pm_commission_models ──▶ pm_employees ──┬──▶ pm_commissions            │
│  (Provisionssaetze)      (Berater/TL)    │    (VU-Buchungen)           │
│                                          │        │                    │
│                                          ├──▶ pm_berater_abrechnungen  │
│                                          │    (Monats-Snapshots)       │
│                          pm_contracts ───┘                              │
│                          (Xempus-Vertraege)                            │
│                              │                                          │
│  pm_vermittler_mapping ◀────┘  pm_import_batches                       │
│  (VU→Berater)                  (Import-Historie)                       │
│                                                                         │
│  ── Xempus Insight Engine ──                                           │
│  xempus_employers ──▶ xempus_tariffs                                   │
│       │             ──▶ xempus_subsidies                               │
│       └──▶ xempus_employees ──▶ xempus_consultations                  │
│  xempus_raw_rows, xempus_import_batches, xempus_status_mappings       │
│  xempus_commission_matches                                              │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### Provisions-Entitaeten

#### CommissionModel (pm_commission_models)

Provisionssatzmodell (z.B. "Standard 80%", "Senior 85%").

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | int | Primaerschluessel |
| `name` | str | Modell-Name (z.B. "Standard") |
| `commission_rate` | float | Provisionssatz in % (0-100) |
| `tl_rate` | float | Teamleiter-Rate in % (0-100, NULL = kein TL-Abzug) |
| `tl_basis` | enum | `berater_anteil` oder `gesamt_courtage` (Basis fuer TL-Berechnung) |
| `is_active` | bool | Aktiv/Inaktiv |

#### Employee (pm_employees)

Mitarbeiter mit Rolle und Provisionsmodell.

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | int | Primaerschluessel |
| `name` | str | Vollstaendiger Name |
| `role` | enum | `consulter`, `teamleiter`, `backoffice` |
| `commission_model_id` | int | FK → pm_commission_models |
| `commission_rate_override` | float | Ueberschreibt Model-Rate (NULL = Model-Rate, 0-100) |
| `teamleiter_id` | int | FK → pm_employees (Teamleiter des Beraters) |
| `tl_override_rate` | float | TL-Abzugs-Rate in % (0-100) |
| `tl_override_basis` | enum | `berater_anteil` oder `gesamt_courtage` |
| `is_active` | bool | Aktiv (soft-delete) |

**Properties**: `effective_rate` = `commission_rate_override` oder `model.commission_rate`

**Validierung**: `role` Whitelist, Rate 0-100, `teamleiter_id != id` (keine Selbstreferenz)

#### Contract (pm_contracts)

Vertrag aus Xempus-Import.

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | int | Primaerschluessel |
| `vsnr` | str | Versicherungsschein-Nr (Original) |
| `vsnr_normalized` | str | Normalisiert (nur Ziffern, alle Nullen entfernt) |
| `vsnr_alt` / `vsnr_alt_normalized` | str | Alternative VSNR (Umbenennungen) |
| `vu_name` | str | Versicherer-Name |
| `versicherungsnehmer` | str | Versicherungsnehmer |
| `versicherungsnehmer_normalized` | str | Normalisiert fuer LIKE-Suche |
| `sparte` | str | Versicherungssparte |
| `beitrag` | float | Beitragssumme |
| `berater_id` | int | FK → pm_employees (zugeordneter Berater) |
| `status` | enum | `offen`, `beantragt`, `aktiv`, `provision_erhalten`, `gekuendigt`, `ruhend` |
| `xempus_id` | str | Xempus-ID (UNIQUE) |
| `import_batch_id` | int | FK → pm_import_batches |

#### Commission (pm_commissions)

Provisionsbuchung aus VU-Import.

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | int | Primaerschluessel |
| `vsnr` / `vsnr_normalized` | str | Versicherungsschein-Nr |
| `versicherer` | str | VU-Name |
| `vermittler_name` / `vermittler_name_normalized` | str | VU-Vermittlername |
| `versicherungsnehmer_normalized` | str | Normalisiert |
| `betrag` | float | Provisionsbetrag (positiv oder negativ) |
| `buchungsdatum` | str | Buchungsdatum (YYYY-MM-DD) |
| `art` | enum | `provision`, `rueckbelastung`, `storno`, `nullmeldung` |
| `contract_id` | int | FK → pm_contracts (gesetzt durch Matching) |
| `berater_id` | int | FK → pm_employees (gesetzt durch Matching) |
| `match_status` | enum | `unmatched`, `auto_matched`, `manual_matched`, `ignored` |
| `match_confidence` | float | Matching-Konfidenz (0.0-1.0) |
| `berater_anteil` | float | Berater-Anteil (berechnet) |
| `tl_anteil` | float | Teamleiter-Anteil (berechnet) |
| `ag_anteil` | float | Arbeitgeber-Anteil (berechnet) |
| `xempus_consultation_id` | str | Xempus-Beratungs-ID (NEU v3.3.0) |
| `row_hash` | str | SHA256 fuer Import-Duplikat-Erkennung |
| `import_batch_id` | int | FK → pm_import_batches |

**Invariante**: `berater_anteil + tl_anteil + ag_anteil == betrag` (immer)

#### BeraterAbrechnung (pm_berater_abrechnungen)

Monatsabrechnung pro Berater (Snapshot-Prinzip).

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | int | Primaerschluessel |
| `berater_id` | int | FK → pm_employees |
| `abrechnungsmonat` | str | Format YYYY-MM |
| `brutto_provision` | float | Brutto-Provision |
| `tl_abzug` | float | TL-Abzug |
| `netto_provision` | float | Netto (brutto - tl_abzug) |
| `rueckbelastungen` | float | Rueckbelastungen des Monats |
| `auszahlung` | float | Auszahlungsbetrag |
| `revision` | int | Auto-Inkrement bei erneuter Generierung |
| `status` | enum | `berechnet`, `geprueft`, `freigegeben`, `ausgezahlt` |
| `is_locked` | bool | Gesperrt ab `freigegeben` |

**UNIQUE Constraint**: `(abrechnungsmonat, berater_id, revision)`

#### VermittlerMapping (pm_vermittler_mapping)

Zuordnung VU-Vermittlername → interner Berater.

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | int | Primaerschluessel |
| `vermittler_name` | str | Original VU-Vermittlername |
| `vermittler_name_normalized` | str | Normalisiert (UNIQUE) |
| `berater_id` | int | FK → pm_employees |

---

### Xempus-Entitaeten (NEU v3.3.0)

#### XempusEmployer (xempus_employers)

Arbeitgeber aus Xempus-Import.

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | str | Xempus-ID |
| `name` | str | Firmenname |
| `street`, `plz`, `city` | str | Adresse |
| `iban`, `bic` | str | Bankverbindung |
| `first_seen_batch_id` / `last_seen_batch_id` | int | Import-Tracking |
| `employee_count`, `tariff_count`, `subsidy_count` | int | Aggregierte Zaehler |

#### XempusConsultation (xempus_consultations)

Beratung (Vertrag) aus Xempus.

| Feld | Typ | Beschreibung |
|------|-----|--------------|
| `id` | str | Xempus-ID |
| `employee_id` | str | FK → xempus_employees |
| `vsnr` | str | Versicherungsschein-Nr |
| `versicherer` | str | VU-Name |
| `sparte` | str | Sparte |
| `status` | str | Beratungsstatus |
| `berater_name` | str | Zustaendiger Berater |

---

### Provisions-Zustandsautomat

#### Abrechnungs-Status

```
┌─────────────┐
│  berechnet  │ ◀── generate_abrechnung()
└──────┬──────┘
       │ Status → geprueft
       ▼
┌─────────────┐
│  geprueft   │ ◀── Ruecksetzung moeglich
└──────┬──────┘
       │ Status → freigegeben (is_locked=1)
       ▼
┌─────────────┐
│ freigegeben │ ◀── Ruecksetzung moeglich
└──────┬──────┘
       │ Status → ausgezahlt
       ▼
┌─────────────┐
│  ausgezahlt │  (Terminal-State)
└─────────────┘
```

#### Matching-Status (Commission)

```
┌─────────────┐     Auto-Match     ┌────────────────┐
│  unmatched  │ ──────────────────▶│ auto_matched   │
└──────┬──────┘                    └────────────────┘
       │ Manuell                           │
       ▼                                   │
┌────────────────┐                         │
│manual_matched  │ ◀───────────────────────┘ (Reassignment)
└────────────────┘
       │ Ignorieren
       ▼
┌─────────────┐
│   ignored   │
└─────────────┘
```

---

### Normalisierungsregeln

#### VSNR-Normalisierung
- Nicht-Ziffern entfernen
- ALLE Nullen entfernen (fuehrend UND intern)
- Scientific Notation zu Integer konvertieren
- Beispiel: "00123-045" → "12345"

#### Vermittler-Normalisierung
- Lowercase
- Umlaute → ae/oe/ue/ss
- Sonderzeichen entfernen
- Beispiel: "Müller-Schmidt" → "muellerschmidt"

#### VN-Normalisierung (normalizeForDb)
- Lowercase
- Umlaute → ae/oe/ue/ss
- Klammern aufloesen
- Sonderzeichen entfernen
- Beispiel: "Müller (Hans)" → "mueller hans"

---

## Referenzen

- **GDV-Spezifikation**: https://www.gdv-online.de/vuvm/bestand/
- **Interne Doku**: `GDV- Daten Dokumentation.txt` im Projekt-Root

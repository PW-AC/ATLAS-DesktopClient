# ACENCIA ATLAS – Provisionsmanagement
## Erklärung für die Geschäftsführung

---

## Was ist das Ziel?

Ein neuer Bereich in ATLAS, der dem Geschäftsführer auf einen Blick zeigt:

- **Wie viel Provision ist diesen Monat reingekommen?**
- **Wie viel davon geht an welchen Berater?**
- **Wo fehlt Provision, obwohl ein Vertrag abgeschlossen wurde?**
- **Gibt es Stornos oder Rückbelastungen?**
- **Was bleibt bei der AG?**

Kein Excel mehr. Keine manuellen Listen. Keine Unsicherheit.

---

## Wie funktioniert das?

### 1. Daten rein – aus zwei Quellen

**Quelle A: VU-Provisionslisten**
Das sind die Abrechnungen, die von den Versicherern kommen – also die echten Courtage-Zahlungen.
Diese Listen werden einfach als Excel-Datei in ATLAS hochgeladen.
ATLAS liest automatisch die relevanten Daten aus: Vertragsnummer, Betrag, Datum, Art (Abschluss, Bestand, Rückbelastung).

**Quelle B: Xempus Advisor Export**
Das ist der Export aus eurem Beratungstool – mit allen offenen und abgeschlossenen Beratungen.
Auch diese Datei wird als Excel hochgeladen.
ATLAS liest die Vertragsnummern, den Berater, den Versicherer und den Status.

### 2. ATLAS bringt beides zusammen

Die Vertragsnummer (VSNR) ist der gemeinsame Schlüssel.

ATLAS gleicht automatisch ab:
- Diese Provision gehört zu diesem Vertrag.
- Dieser Vertrag wurde von diesem Berater abgeschlossen.

Das passiert auf Knopfdruck. Wenn etwas nicht zugeordnet werden kann, zeigt ATLAS es an – und man kann es manuell zuordnen.

### 3. Automatische Berechnung

Sobald eine Provision einem Berater zugeordnet ist, rechnet ATLAS automatisch:

```
Beispiel: Allianz zahlt 1.000 € Courtage

→ Berater Müller hat einen Provisionssatz von 40%
→ Berater-Anteil: 400 €

→ Müller ist im Team von Teamleiter Schmidt
→ Schmidt bekommt 10% Override = 40 €
→ Müller bekommt: 400 € - 40 € = 360 €

→ AG behält: 600 € (immer fest)
```

Das wird für jede einzelne Provision automatisch berechnet.

---

## Was sieht der Geschäftsführer?

### Das Dashboard

Beim Öffnen des Provisionsbereichs erscheint eine Übersicht:

**Oben: Die wichtigsten Zahlen auf einen Blick**

| Kennzahl | Beispiel |
|----------|----------|
| Provision diesen Monat | 12.450 € |
| Provision dieses Jahr (YTD) | 98.200 € |
| Offene Zuordnungen | 7 Provisionen noch nicht zugeordnet |
| Stornoquote | 3,2% |

**Mitte: Berater-Ranking**

Eine Tabelle mit allen Beratern und ihren Zahlen:

| Berater | Brutto | TL-Abzug | Netto | Rückbelastung |
|---------|--------|----------|-------|---------------|
| Müller, Hans | 4.200 € | 420 € | 3.780 € | 0 € |
| Schmidt, Anna | 3.100 € | 310 € | 2.790 € | -200 € |
| Weber, Klaus | 2.800 € | 280 € | 2.520 € | 0 € |

**Unten: Handlungsbedarf**

ATLAS zeigt aktiv an, wo etwas nicht stimmt:

- "7 Provisionen konnten keinem Vertrag zugeordnet werden"
- "3 Verträge sind seit über 60 Tagen abgeschlossen, aber es kam noch keine Provision"
- "2 Vermittlernamen aus der letzten VU-Liste sind unbekannt"

Das sind keine Vermutungen – das sind harte Daten.

---

## Berater-Detailansicht

Ein Klick auf einen Berater zeigt:

- Aktueller Monat: Provision netto
- Jahresübersicht (YTD)
- Anzahl aktive Verträge
- Letzte Provisionseingänge (Datum, VSNR, VU, Betrag, eigener Anteil)
- Offene Beratungen in der Pipeline

---

## Mitarbeiterverwaltung

Im System werden die Mitarbeiter einmalig angelegt:

- **Name**
- **Rolle**: Consulter, Teamleiter oder Backoffice
- **Provisionssatz**: z.B. 40% (was der Berater von der VU-Courtage bekommt)
- **Team-Zuordnung**: Welcher Teamleiter ist zuständig?

Für den Teamleiter wird zusätzlich eingestellt:
- **Override-Satz**: z.B. 10%
- **Override-Basis**: Entweder vom Berater-Anteil oder von der Gesamt-Courtage

Diese Einstellungen können jederzeit angepasst werden.
ATLAS berechnet dann alle betroffenen Provisionen automatisch neu.

---

## Vermittler-Zuordnung

Ein häufiges Problem: In der VU-Liste steht z.B. "Müller, H. (12345)" als Vermittler, aber im System heißt er "Hans Müller".

Dafür gibt es eine einfache Zuordnungstabelle:
- "Müller, H. (12345)" → Hans Müller
- "Schmidt A." → Anna Schmidt

Das muss einmal gepflegt werden. Danach erkennt ATLAS bei jedem Import automatisch, welcher Berater gemeint ist.

---

## Import – wie kommt das rein?

Der Ablauf ist einfach:

1. **Excel-Datei auswählen** (VU-Liste oder Xempus-Export)
2. **ATLAS erkennt die Spalten automatisch** (Vertragsnummer, Betrag, Datum, etc.)
3. **Kurze Vorschau** – man sieht die ersten Zeilen und kann prüfen ob alles stimmt
4. **Import starten**
5. **Ergebnis sofort sichtbar**: "250 Provisionen importiert, 230 zugeordnet, 20 offen"

Eine Datei, die schon importiert wurde, wird erkannt und nicht doppelt eingelesen.

---

## Was bringt das konkret?

| Vorher (Excel) | Nachher (ATLAS) |
|----------------|-----------------|
| Manuelle Auswertung der VU-Listen | Automatischer Import + Zuordnung |
| Keine Übersicht pro Berater | Sofortige Berater-Auswertung |
| Fehlende Provisionen fallen spät auf | ATLAS meldet es automatisch |
| Stornos werden manuell gesucht | Rückbelastungen werden automatisch erkannt |
| Berater-Abrechnung ist Handarbeit | Automatische Monatsabrechnung |
| Keine Echtzeit-Zahlen | Dashboard mit aktuellen Kennzahlen |
| Excel-Chaos mit vielen Dateien | Ein zentrales System |

---

## Wer sieht was?

| Rolle | Zugriff |
|-------|---------|
| **Geschäftsführer** | Alles: Dashboard, alle Berater, Import, Einstellungen |
| **Teamleiter** | Eigenes Team: Nur die Berater im eigenen Team |
| **Berater** | Nur sich selbst: Eigene Provisionen und Verträge |

---

## Wie sieht der Provisionsfluss aus?

Hier das vollständige Bild in einfacher Darstellung:

```
Versicherer zahlt Courtage
         │
         ▼
    ┌─────────┐
    │  ATLAS  │  ← VU-Liste importieren
    └────┬────┘
         │
         ▼
    Vertragsnummer abgleichen
    Berater identifizieren
         │
         ├──────────────────────────┐
         │                          │
         ▼                          ▼
    Berater-Anteil (Y%)        AG-Anteil (100%-Y%)
         │                     → bleibt immer gleich
         │
    Hat Berater einen TL?
         │
    ┌────┴────┐
    │ JA      │ NEIN
    ▼         ▼
  TL bekommt    Berater bekommt
  Override      vollen Anteil
  (wird vom
  Berater
  abgezogen)
```

---

## Zeitrahmen

Das System wird schrittweise aufgebaut:

**Phase 1** (Sofort nutzbar):
- Mitarbeiter anlegen
- VU-Listen importieren
- Xempus-Export importieren
- Automatische Zuordnung
- GF-Dashboard
- Berater-Übersicht

**Phase 2** (Erweiterung):
- Staffelmodelle (ab einem bestimmten Umsatz mehr Prozent)
- Monatsabrechnungen als PDF exportieren
- Prognosen (wie viel Provision ist zu erwarten)
- Berater können ihre eigenen Daten einsehen

---

## Zusammenfassung

ATLAS bekommt einen neuen Bereich: **Provisionsmanagement**.

Damit kann der Geschäftsführer:
- Auf einen Blick sehen, wie viel Provision reinkommt und wohin sie geht
- Sofort erkennen, wo Provision fehlt oder wo es Probleme gibt
- Die Berater-Anteile automatisch berechnen lassen
- Monatsabrechnungen generieren
- Alles an einem Ort statt in vielen Excel-Dateien

Die Daten kommen aus den vorhandenen Quellen (VU-Listen + Xempus) – es muss nichts Neues beschafft werden.

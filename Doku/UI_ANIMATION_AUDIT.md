# ACENCIA ATLAS – UI Animation & Transition Audit

> **Erstellt:** 2026-03-11  
> **Scope:** ATLAS Desktop Client (`src/ui/`)  
> **Zweck:** Systematische Identifikation aller Code-Stellen, die zu Animationsstottern, UI-Freezes, verzögerten Transitions oder Frame-Drops führen können.

---

## Inhaltsverzeichnis

1. [Blocking I/O im UI-Thread](#kategorie-1--blocking-io-im-ui-thread)
2. [Widget-Erstellung während Transitions](#kategorie-2--widget-erstellung-während-transitions)
3. [processEvents()-Missbrauch](#kategorie-3--processevents-missbrauch)
4. [Animation-Konflikte und Race Conditions](#kategorie-4--animation-konflikte-und-race-conditions)
5. [Layout-Thrashing und Stylesheet-Storms](#kategorie-5--layout-thrashing-und-stylesheet-storms)
6. [Fehlende View-Transition-Animation](#kategorie-6--fehlende-view-transition-animation)
7. [Signal-Storms und Cascading Updates](#kategorie-7--signal-storms-und-cascading-updates)
8. [Strukturelle Probleme](#kategorie-8--strukturelle-probleme)

---

## Kategorie 1 – Blocking I/O im UI-Thread

---

### Finding #1

**File:** `src/ui/archive_boxes_view.py`  
**Class:** `ArchiveBoxesView`  
**Function:** `_load_smartscan_status()` (Zeile 239–241)

#### Problem Description

Die Methode `_load_smartscan_status()` ruft `self._presenter.load_smartscan_status()` auf, was einen **synchronen API-Call** (`smartscan_api.is_enabled()`) auf dem Main Thread ausführt. Diese Methode wird sowohl beim Init (Zeile 212) als auch nach jedem 5. Auto-Refresh-Zyklus (Zeile 802) aufgerufen.

#### Why This Can Cause Animation Problems

Ein synchroner HTTP-Request auf dem Main Thread blockiert die gesamte Qt Event Loop. Während der Request läuft (typisch 50–500ms, bei Netzwerkproblemen bis zu Timeout), werden keine Animationen, Repaints oder User-Events verarbeitet. Dies verursacht spürbare UI-Freezes, insbesondere:
- Beim ersten Wechsel ins Archiv-Modul
- Alle 5 Minuten während der Archiv-Nutzung (Auto-Refresh)
- Beim Verlassen des Admin-Bereichs (`main_hub.py:795–797`)

#### Risk Level

**Critical**

#### Suggested Improvement

SmartScan-Status in einen Worker-Thread auslagern. Ein `QRunnable` oder `QThread` kann den API-Call asynchron ausführen und das Ergebnis per Signal an den Main Thread zurückmelden. Der Status kann initial als `False` angenommen werden, bis der Worker das Ergebnis liefert.

---

### Finding #2

**File:** `src/ui/main_hub.py`  
**Class:** `MainHub`  
**Function:** `_leave_admin()` (Zeile 792–798)

#### Problem Description

Beim Verlassen des Admin-Bereichs wird `self._archive_view._load_smartscan_status()` synchron aufgerufen. Dies ist ein API-Call auf dem Main Thread, der während der Navigation zurück zum Dashboard ausgeführt wird.

#### Why This Can Cause Animation Problems

Der synchrone API-Call blockiert den Main Thread genau in dem Moment, in dem der View-Wechsel stattfindet. Die ModuleSidebar-Exit-Animation und der anschließende Dashboard-Wechsel können dadurch verzögert oder stotternd erscheinen. Der Benutzer erlebt einen merklichen Hänger beim Klick auf „Zurück".

#### Risk Level

**High**

#### Suggested Improvement

Den SmartScan-Status-Check in einen Worker-Thread verschieben oder ihn erst nach dem View-Wechsel per `QTimer.singleShot(500, ...)` ausführen, sodass die Navigation zuerst abgeschlossen wird.

---

### Finding #3

**File:** `src/ui/archive_boxes_view.py`  
**Class:** `ArchiveBoxesView`  
**Function:** `__init__()` (Zeile 210–213)

#### Problem Description

Im Konstruktor von `ArchiveBoxesView` wird `_load_smartscan_status()` direkt aufgerufen (Zeile 212). Der Konstruktor läuft im Main Thread und wird bei der ersten Navigation zum Archiv ausgeführt – genau dann, wenn auch die Sidebar-Enter-Animation laufen soll.

#### Why This Can Cause Animation Problems

Die Widget-Konstruktion findet synchron im Main Thread statt, **während** die ModuleSidebar-Enter-Animation (380ms) bereits gestartet wurde oder gleich starten soll. Ein blockierender API-Call im Konstruktor friert die laufende Animation ein. Der Benutzer sieht eine hakende oder eingefrorene Sidebar-Animation.

#### Risk Level

**Critical**

#### Suggested Improvement

Den API-Call aus dem Konstruktor entfernen und per `QTimer.singleShot(0, ...)` erst nach dem ersten Event-Loop-Durchlauf ausführen, oder besser: in einen Worker-Thread verlagern.

---

### Finding #4

**File:** `src/ui/provision/auszahlungen_panel.py`  
**Class:** `AuszahlungenPanel`  
**Function:** CSV-Export Handler (Zeile 564–565)

#### Problem Description

Der CSV-Export (`open()`, `csv.writer`) wird direkt im UI-Event-Handler ausgeführt. Bei großen Datensätzen kann dies den Main Thread blockieren.

#### Why This Can Cause Animation Problems

Während der Datei geschrieben wird, sind keine UI-Updates möglich. Bei großen Exports (>1000 Zeilen) kann dies zu einer spürbaren Verzögerung führen.

#### Risk Level

**Medium**

#### Suggested Improvement

Dateiexport in einen Worker-Thread auslagern. Alternativ: Fortschrittsanzeige mit `QTimer`-basiertem Batch-Export.

---

### Finding #5

**File:** `src/ui/viewers/pdf_viewer.py`  
**Class:** PDFViewer  
**Function:** `_load_fitz_document()` / `load()` (Zeile 408–415, 605)

#### Problem Description

PDF-Dateien werden mit `fitz.open()` und `open(..., 'rb')` direkt im Main Thread geladen. Bei großen PDFs (>10MB) kann dies mehrere hundert Millisekunden dauern.

#### Why This Can Cause Animation Problems

Das Laden eines PDF blockiert den Main Thread. Wenn der PDF-Viewer als Teil einer Navigation geöffnet wird, friert die gesamte UI ein, bis die Datei geladen ist. Besonders kritisch bei PDFs, die von einem Netzlaufwerk gelesen werden.

#### Risk Level

**High**

#### Suggested Improvement

Das PDF-Laden in einen Worker-Thread verlagern und einen Loading-Spinner anzeigen, bis die Datei geladen ist.

---

### Finding #6

**File:** `src/ui/admin/panels/smartscan_settings.py`  
**Class:** `SmartScanSettingsPanel`  
**Function:** `_load_smartscan_settings()` (Zeile 215–227)

#### Problem Description

Beim Öffnen des SmartScan-Settings-Tabs werden `get_accounts()` und `get_settings()` synchron im Main Thread aufgerufen. Beide sind REST-API-Calls.

#### Why This Can Cause Animation Problems

Zwei aufeinanderfolgende synchrone HTTP-Requests blockieren den Main Thread für die kumulative Dauer beider Calls. Der Tab-Wechsel innerhalb des Admin-Panels erscheint verzögert.

#### Risk Level

**High**

#### Suggested Improvement

Beide API-Calls in einen Worker-Thread bündeln und die Daten per Signal zurückmelden.

---

### Finding #7

**File:** `src/ui/admin/panels/smartscan_history.py`  
**Class:** `SmartScanHistoryPanel`  
**Function:** `_load_smartscan_history()` (Zeile 97)

#### Problem Description

`get_jobs(limit=100)` wird synchron im Main Thread aufgerufen. Bei 100 Jobs kann der Response groß sein.

#### Why This Can Cause Animation Problems

Blockiert den Main Thread während des Tab-Wechsels im Admin-Panel.

#### Risk Level

**Medium**

#### Suggested Improvement

In Worker-Thread auslagern.

---

### Finding #8

**File:** `src/ui/bipro_view.py`  
**Class:** `BiPROView`  
**Function:** `_fetch_mails()` (Zeile 3525–3538)

#### Problem Description

Vor dem Mail-Import werden `smartscan_api.get_settings()` und `email_api.get_accounts()` synchron im Main Thread aufgerufen.

#### Why This Can Cause Animation Problems

Zwei sequenzielle HTTP-Requests blockieren den Main Thread. Der Button-Click „Mails abrufen" führt zu einem spürbaren Hänger bevor etwas passiert.

#### Risk Level

**High**

#### Suggested Improvement

Die Settings-Daten im Voraus cachen oder in einen Worker-Thread verlagern.

---

## Kategorie 2 – Widget-Erstellung während Transitions

---

### Finding #9

**File:** `src/ui/app_router.py`  
**Class:** `AppRouter`  
**Function:** `_do_open_module()` (Zeile 266–331)

#### Problem Description

Innerhalb von `_do_open_module()` wird `_ensure_<modul>()` aufgerufen, **bevor** der `setCurrentIndex()` den View wechselt. Die `_ensure_*`-Methoden importieren Module, erstellen Hub-Widgets und ersetzen Placeholder im Stack. Die Modul-Konstruktoren sind schwer: `MainHub` hat 1602 Zeilen, `BiPROView` 4370 Zeilen, `ArchiveBoxesView` 3115 Zeilen. Obwohl der Preload-Mechanismus die meisten Module vorab lädt, kann es bei Race Conditions oder langsamem Start dazu kommen, dass die Konstruktion **während** der Navigation stattfindet.

#### Why This Can Cause Animation Problems

Die Widget-Konstruktion (Import + `__init__()`) kann bei komplexen Modulen 100–500ms dauern. Wenn dies passiert, während die Exit-Animation der alten ModuleSidebar noch läuft oder gerade beendet wurde, entsteht ein spürbarer Freeze zwischen Exit- und Enter-Animation. Der Preload-Mechanismus mildert dies ab, garantiert aber nicht, dass alle Module geladen sind, bevor der User klickt.

#### Risk Level

**High**

#### Suggested Improvement

Den Preload-Mechanismus mit einer Statusprüfung ergänzen: Wenn ein Modul noch nicht geladen ist, die Navigation visuell anzeigen (Loading-Indikator) und die Widget-Erstellung per `QTimer.singleShot(0, ...)` aufteilen. Alternativ: Die Konstruktion in zwei Phasen aufteilen – leichter Shell sofort, schwere Inhalte deferred.

---

### Finding #10

**File:** `src/ui/main_hub.py`  
**Class:** `MainHub`  
**Function:** `_show_bipro()`, `_show_archive()`, `_show_gdv()` (Zeile 633–690)

#### Problem Description

Bei der ersten Navigation zu BiPRO, Archiv oder GDV wird das jeweilige View-Widget **synchron** importiert und erstellt. Beispiel `_show_archive()`:
1. `from ui.archive_boxes_view import ArchiveBoxesView` (Import, ggf. Kaltstart)
2. `ArchiveBoxesView(self.api_client, auth_api=self.auth_api)` (Konstruktor mit ~200 Zeilen Init)
3. `content_stack.removeWidget(placeholder)` + `insertWidget(2, view)` (Layout-Neuberechnung)
4. `content_stack.setCurrentIndex(2)` (View-Wechsel)

#### Why This Can Cause Animation Problems

Der Import von `archive_boxes_view.py` (3115 Zeilen) und dessen Konstruktor erzeugen eine signifikante Pausenzeit. Da der Import das Python-Modul und alle transitiven Abhängigkeiten laden muss, kann der erste Aufruf 200–800ms dauern. Dies passiert im Main Thread und blockiert die Event Loop. Keine Animation kann während dieser Zeit ablaufen.

#### Risk Level

**High**

#### Suggested Improvement

Einen „Loading"-Indikator im Content-Stack anzeigen, bevor die View erstellt wird. Die View-Erstellung kann in zwei Teile aufgeteilt werden: (1) leichter Import + minimales UI in einem Frame, (2) schwere Inhalte im nächsten Event-Loop-Zyklus.

---

### Finding #11

**File:** `src/ui/dashboard_screen.py`  
**Class:** `DashboardScreen`  
**Function:** `_render_messages()` (Zeile 1254–1279)

#### Problem Description

Bei jeder Aktualisierung der Nachrichten werden **alle vorhandenen Message-Cards entfernt und neu erstellt**:
1. While-Loop entfernt alle Widgets aus `_msg_container`
2. For-Loop erstellt neue `_build_message_card()` Widgets (jeweils mit Layouts, Labels, StyleSheets)

#### Why This Can Cause Animation Problems

Das Entfernen und Neuerstellen von Widgets löst Layout-Neuberechnungen aus. Obwohl maximal 3 Karten erstellt werden, passiert dies bei jedem Message-Reload (durch Heartbeat-Notifications). Wenn dies während einer Sidebar-Animation stattfindet, können kurze Ruckler auftreten.

#### Risk Level

**Low**

#### Suggested Improvement

Bestehende Cards aktualisieren statt neu erstellen (Widget-Reuse-Pattern). Alternativ: Die Aktualisierung per `QTimer.singleShot(0, ...)` in den nächsten Event-Loop-Zyklus verschieben, wenn gerade eine Animation läuft.

---

### Finding #12

**File:** `src/ui/workforce/stats_view.py`  
**Class:** `StatsView`  
**Function:** Widget-Erstellung in Schleifen (Zeile 258, 290, 453–506)

#### Problem Description

`_make_card()` und `_make_chart_frame()` werden in For-Schleifen aufgerufen, wobei jeder Aufruf QFrames, QLabels, QVBoxLayouts und Stylesheets erstellt. Bei vielen Datensätzen (z.B. 50+ Karten) kann dies den Main Thread für mehrere hundert Millisekunden blockieren.

#### Why This Can Cause Animation Problems

Die gesamte Widget-Erstellung erfolgt synchron im Main Thread. Während die Widgets erstellt werden, kann keine Animation ablaufen und kein UI-Event verarbeitet werden.

#### Risk Level

**Medium**

#### Suggested Improvement

Widget-Erstellung in Batches aufteilen (z.B. 10 Widgets pro Event-Loop-Zyklus via `QTimer.singleShot(0, ...)`). Für Listen mit vielen Elementen eine Virtualisierung (nur sichtbare Widgets rendern) in Betracht ziehen.

---

### Finding #13

**File:** `src/ui/contact/contacts_view.py`  
**Class:** `ContactsView`  
**Function:** Kontakt-Karten-Erstellung (Zeile 268–298)

#### Problem Description

Kontakt-Karten werden in einer Schleife erstellt. Jede Karte enthält mehrere Labels, Layouts und Stylesheets.

#### Why This Can Cause Animation Problems

Bei vielen Kontakten (50+) blockiert die synchrone Erstellung den Main Thread merklich.

#### Risk Level

**Medium**

#### Suggested Improvement

Batch-Erstellung oder Virtualisierung der Kontaktliste.

---

## Kategorie 3 – processEvents()-Missbrauch

---

### Finding #14

**File:** `src/ui/archive_boxes_view.py`  
**Class:** `ArchiveBoxesView`  
**Function:** `_show_loading()` (Zeile 289–297)

#### Problem Description

```python
self._loading_overlay.setVisible(True)
QApplication.processEvents()
```

`processEvents()` wird aufgerufen, um das Loading-Overlay sofort sichtbar zu machen.

#### Why This Can Cause Animation Problems

`processEvents()` verarbeitet **alle** ausstehenden Events, einschließlich Timer-Events, Mouse-Events und Paint-Events. Dies kann zu:
- Reentrancy-Problemen führen (Signal-Handler werden inmitten anderer Handler aufgerufen)
- Unerwarteter Ausführungsreihenfolge
- Doppelten Slot-Aufrufen
- Stacking von processEvents()-Aufrufen

Wenn `processEvents()` während einer laufenden Animation aufgerufen wird, kann es die Animation-Timer durcheinanderbringen.

#### Risk Level

**Medium**

#### Suggested Improvement

Statt `processEvents()` den Loading-Overlay per `QTimer.singleShot(0, ...)` anzeigen und die eigentliche Arbeit erst im nächsten Event-Loop-Zyklus starten. So kann Qt das Overlay rendern, ohne `processEvents()` zu benötigen.

---

### Finding #15

**File:** `src/ui/archive/widgets.py`  
**Class:** `ProgressOverlay`  
**Function:** `start_processing()`, `update_progress()`, `show_completion()` (Zeile 669, 684, 766)

#### Problem Description

`QApplication.processEvents()` wird an drei Stellen innerhalb des Progress-Overlays aufgerufen:
1. `start_processing()` – nach `setVisible(True)`
2. `update_progress()` – nach jedem Fortschrittsupdate
3. `show_completion()` – nach Anzeige des Ergebnisses

#### Why This Can Cause Animation Problems

Mehrfache `processEvents()`-Aufrufe während eines längeren Verarbeitungsprozesses können zu Reentrancy führen. Wenn der Benutzer während der Verarbeitung klickt, werden diese Events sofort verarbeitet – potenziell in einem inkonsistenten Zustand. Zudem können mehrere verschachtelte `processEvents()`-Aufrufe die Event-Loop-Integrität gefährden.

#### Risk Level

**Medium**

#### Suggested Improvement

Die Dokumentenverarbeitung in einen Worker-Thread verlagern und den Fortschritt über Signals aktualisieren. Der Main Thread bleibt frei für reguläres Event-Processing und Animationen.

---

## Kategorie 4 – Animation-Konflikte und Race Conditions

---

### Finding #16

**File:** `src/ui/app_router.py`  
**Class:** `AppRouter`  
**Function:** `_do_open_module()` → Sidebar-Collapse + Enter-Animation (Zeile 325–331)

#### Problem Description

```python
if self._sidebar._is_expanded:
    self._sidebar.set_expanded(False)
    self._sidebar.collapse_finished.connect(
        self._play_module_sidebar_enter, Qt.SingleShotConnection
    )
else:
    self._play_module_sidebar_enter()
```

Die AppSidebar-Collapse-Animation (420ms) muss zuerst beendet werden, bevor die ModuleSidebar-Enter-Animation (380ms) startet. Dies geschieht über `collapse_finished` → `_play_module_sidebar_enter()`. Gleichzeitig wurde bereits `_stack.setCurrentIndex()` aufgerufen, sodass das neue Modul schon sichtbar ist, aber noch keine Modul-Sidebar-Animation läuft.

#### Why This Can Cause Animation Problems

Zwischen `setCurrentIndex()` und dem Start der ModuleSidebar-Enter-Animation vergeht die gesamte Collapse-Animation (420ms). Während dieser Zeit ist das neue Modul sichtbar, aber die ModuleSidebar ist unsichtbar (durch `reset_animation_state()` auf `opacity=0` und `margin-left=-SIDEBAR_WIDTH`). Dies erzeugt einen visuell inkonsistenten Zustand von bis zu 420ms. Außerdem: Wenn der Benutzer schnell klickt, kann die `collapse_finished`-Verbindung noch aktiv sein, während eine neue Navigation beginnt.

#### Risk Level

**High**

#### Suggested Improvement

Den View-Wechsel (`setCurrentIndex`) erst nach der Collapse-Animation durchführen, oder die Modul-Sidebar bereits im initialen Zustand (collapsed, opacity 0) darstellen und die Enter-Animation parallel zur Collapse-Animation starten. Ein Transitions-Manager könnte die Reihenfolge und Parallelität zentral steuern.

---

### Finding #17

**File:** `src/ui/components/module_sidebar.py`  
**Class:** `ModuleSidebar`  
**Function:** `play_enter_animation()`, `play_exit_animation()` (Zeile 297–333)

#### Problem Description

Die Enter- und Exit-Animationen verwenden `QTimeLine` mit `frameChanged`-Signal, das bei jedem Frame `setContentsMargins()` und `setOpacity()` aufruft. Der `_stop_running()`-Guard stoppt nur die aktuelle Timeline, prüft aber nicht, ob eine andere Animation (z.B. AppSidebar-Collapse) gerade läuft.

#### Why This Can Cause Animation Problems

`setContentsMargins()` bei jedem Frame löst ein Layout-Reflow für die gesamte Sidebar und deren Kinder aus. Bei einer 380ms-Animation mit ~60fps sind das ca. 23 Layout-Neuberechnungen. Wenn die Sidebar viele Widgets enthält (10+ NavButtons), kann dies zu merklichem CPU-Overhead führen. Zusätzlich: Die `frameChanged`-Signal-Handler laufen im Main Thread und können andere Events verzögern.

#### Risk Level

**Medium**

#### Suggested Improvement

Statt `setContentsMargins()` eine CSS-`transform: translateX()`-ähnliche Technik verwenden, die kein Layout-Reflow auslöst. In PySide6 wäre `QGraphicsTransformEffect` oder eine `QPropertyAnimation` auf `pos()` effizienter. Alternativ: Die Sidebar in einen `QGraphicsView/QGraphicsProxyWidget` einbetten, wo Transformationen GPU-beschleunigt sind.

---

### Finding #18

**File:** `src/ui/app_router.py`  
**Class:** `AppRouter`  
**Function:** `_safe_connect_exit()` / `_safe_disconnect_exit()` (Zeile 352–372)

#### Problem Description

Die Methoden verwenden `try/except` um Signal-Verbindungen sicher zu trennen und neu zu verbinden. Der Disconnect wird mit `warnings.catch_warnings()` umhüllt, um RuntimeWarnings zu unterdrücken.

#### Why This Can Cause Animation Problems

Das Unterdrücken von RuntimeWarnings deutet darauf hin, dass die Signal-Verwaltung nicht deterministisch ist. Wenn `exit_animation_finished` mehrfach mit verschiedenen Slots verbunden wird (z.B. durch schnelles Klicken), können alte Verbindungen bestehen bleiben und nach der Animation die falschen Slots auslösen. Dies kann zu doppelten View-Wechseln, geisterhaften Animationen oder inkonsistenten UI-Zuständen führen.

#### Risk Level

**Medium**

#### Suggested Improvement

Einen zentralen Transitions-State-Machine einführen, der genau einen aktiven Transitions-Zustand verwaltet. Statt dynamischer Signal-Verbindungen einen festen Callback-Mechanismus verwenden, der bei jedem Transitions-Start den vorherigen Zustand sauber aufräumt.

---

### Finding #19

**File:** `src/ui/components/sidebar.py`  
**Class:** `AppSidebar`  
**Function:** `set_expanded()` (Zeile 265–300)

#### Problem Description

Wenn `set_expanded()` aufgerufen wird, während eine Collapse-/Expand-Animation bereits läuft, wird die alte Animation gestoppt und eine neue gestartet:
```python
if self._anim_group and self._anim_group.state() == QParallelAnimationGroup.Running:
    self._anim_group.stop()
```

#### Why This Can Cause Animation Problems

Das Stoppen einer laufenden Animation hinterlässt die Sidebar in einem Zwischenzustand (teilweise collapsed). Die neue Animation startet von `self.width()` (dem aktuellen Zwischenwert), was korrekt ist. Allerdings werden die `QGraphicsOpacityEffect`-Werte der Labels möglicherweise nicht zurückgesetzt, was zu halbtransparenten oder unsichtbaren Labels führen kann. Der `_on_anim_finished`-Callback der gestoppten Animation wird **nicht** aufgerufen, sodass `collapse_finished` nie emittiert wird – was wiederum Downstream-Animationen (ModuleSidebar-Enter) blockieren kann.

#### Risk Level

**High**

#### Suggested Improvement

Beim Stoppen der Animation den `_on_anim_finished`-Callback manuell aufrufen oder den Zustand explizit bereinigen. Einen Guard einbauen, der bei Schnellklicks die Animation in den Endzustand versetzt, statt sie abrupt zu stoppen.

---

### Finding #20

**File:** `src/ui/dashboard_screen.py`  
**Class:** `_SettingsOverlay` / `FeedbackOverlay`  
**Function:** `show_animated()` / `close_animated()` (Zeile 583–606, Feedback: 634–657)

#### Problem Description

Die `_anim`-Referenz wird bei jedem Aufruf überschrieben:
```python
self._anim = QPropertyAnimation(self._opacity, b"opacity")
```
Wenn `show_animated()` und `close_animated()` schnell hintereinander aufgerufen werden, wird die vorherige Animation nicht explizit gestoppt. Die neue Animation überschreibt nur die Python-Referenz.

#### Why This Can Cause Animation Problems

Die alte `QPropertyAnimation` kann noch laufen, wenn die neue startet. Da beide auf demselben `QGraphicsOpacityEffect` arbeiten, können sie sich gegenseitig überlagern und zu Flackern führen. In manchen Qt-Versionen kann eine laufende Animation, deren Python-Referenz verloren geht, durch den Garbage Collector zerstört werden, was zu einem Crash führt.

#### Risk Level

**Medium**

#### Suggested Improvement

Vor dem Erstellen einer neuen Animation die alte explizit stoppen:
```python
if self._anim:
    self._anim.stop()
```
Einen Guard einbauen, der verhindert, dass `show_animated()` während `close_animated()` aufgerufen wird.

---

## Kategorie 5 – Layout-Thrashing und Stylesheet-Storms

---

### Finding #21

**File:** `src/ui/app_router.py`  
**Class:** `AppRouter`  
**Function:** `_ensure_core()`, `_ensure_ledger()`, `_ensure_workforce()`, `_ensure_contact()` (Zeile 578–674)

#### Problem Description

Jede `_ensure_*`-Methode führt drei Layout-Operationen auf dem Stack durch:
```python
old = self._stack.widget(IDX)
self._stack.removeWidget(old)
old.deleteLater()
self._stack.insertWidget(IDX, widget)
```

#### Why This Can Cause Animation Problems

`removeWidget()` und `insertWidget()` lösen jeweils eine Layout-Neuberechnung des gesamten `QStackedWidget` aus. Da der Stack 5+ Widgets enthält und die neuen Widgets komplex sind (MainHub: QMainWindow mit eigenem Stack), kann dies kurze Layout-Stöße verursachen. Da der Preload-Mechanismus diese Operationen nacheinander für alle Module ausführt, werden 4×3 = 12 Layout-Operationen sequenziell durchgeführt.

#### Risk Level

**Medium**

#### Suggested Improvement

Layout-Updates temporär deaktivieren (`setUpdatesEnabled(False)`) während der Stack-Manipulation und erst nach Abschluss wieder aktivieren. Alternativ: Die Placeholder-Ersetzung in einem einzigen Batch durchführen.

---

### Finding #22

**File:** `src/ui/dashboard_screen.py`  
**Class:** `DashboardScreen`  
**Function:** `_rebuild_ui()` (Zeile 1138–1176)

#### Problem Description

Beim Ändern von Theme, Font-Preset oder Sprache wird die **gesamte Dashboard-UI zerstört und neu aufgebaut**:
1. `_clock_timer.stop()`
2. `old_content.hide()` + `old_overlay.hide()`
3. `self._setup_ui()` – kompletter UI-Neuaufbau
4. `old_content.deleteLater()` + `old_overlay.deleteLater()`
5. `load_messages()` + `load_kpi_data()` – Daten neu laden

#### Why This Can Cause Animation Problems

Das Zerstören und Neuerstellen der gesamten Dashboard-UI ist eine extrem teure Operation. Alle Widgets, Layouts, Stylesheets und Signal-Verbindungen werden entfernt und neu erstellt. Dies kann je nach Komplexität 500ms–2s dauern und blockiert den Main Thread vollständig. Während dieser Zeit ist die Anwendung komplett eingefroren.

#### Risk Level

**Critical**

#### Suggested Improvement

Statt die UI komplett neu zu bauen, nur die betroffenen Stylesheets aktualisieren. Qt unterstützt `QApplication.setStyleSheet()` für globale Style-Änderungen. Für Theme-Wechsel können die Token-Werte geändert und ein globales Stylesheet-Refresh durchgeführt werden, ohne Widgets neu zu erstellen.

---

### Finding #23

**File:** `src/ui/dashboard_screen.py`  
**Class:** `DashboardScreen`  
**Function:** `_on_settings_saved()` (Zeile 1113–1136)

#### Problem Description

Beim Speichern der Einstellungen werden mehrere globale Änderungen synchron durchgeführt:
```python
_tok.apply_font_preset(preset_id)
_tok.apply_theme(theme_id)
_i18n_mod.set_language(lang_code)
app.setStyleSheet(_tok.get_application_stylesheet())
app.setFont(QFont(_body, 10))
QTimer.singleShot(0, self._rebuild_ui)
```

#### Why This Can Cause Animation Problems

`app.setStyleSheet()` auf der `QApplication`-Ebene erzwingt ein **Re-Rendering aller sichtbaren Widgets** in der gesamten Anwendung. Dies ist ein extrem teurer Vorgang. In Kombination mit `app.setFont()` und dem anschließenden `_rebuild_ui()` entstehen drei aufeinanderfolgende globale Repaints.

#### Risk Level

**High**

#### Suggested Improvement

Die globalen Style-Änderungen batchweise in einem einzigen Vorgang durchführen. `_rebuild_ui()` könnte überflüssig werden, wenn das globale Stylesheet-Update ausreicht. Mindestens: `setUpdatesEnabled(False)` vor den Änderungen und `setUpdatesEnabled(True)` danach.

---

### Finding #24

**File:** `src/ui/components/sidebar.py`  
**Class:** `AppSidebar`  
**Function:** `update_modules()` → `set_user()` → `_clear_modules()` (Zeile 386–404)

#### Problem Description

`update_modules()` ruft `set_user()` auf, das zuerst `_clear_modules()` aufruft (entfernt alle Modul-NavItems aus dem Layout) und dann alle Modul-NavItems neu erstellt. Dies geschieht bei jedem Heartbeat-`modules_updated`-Signal.

#### Why This Can Cause Animation Problems

Wenn sich Module-Berechtigungen ändern (was selten ist), wird die gesamte Modul-Navigation zerstört und neu aufgebaut. Da `_clear_modules()` eine While-Loop mit `takeAt(0)` + `deleteLater()` ist und `set_user()` für jedes Modul ein neues `_SidebarNavItem` mit `setStyleSheet()` erstellt, kann dies kurze Ruckler verursachen. Besonders problematisch: Dies kann während einer laufenden Sidebar-Animation passieren.

#### Risk Level

**Low**

#### Suggested Improvement

Nur dann neu bauen, wenn sich die tatsächliche Modul-Liste geändert hat. Einen Vergleich der aktuellen mit der neuen Modul-Liste durchführen und nur Änderungen anwenden (Diff-Update).

---

## Kategorie 6 – Fehlende View-Transition-Animation

---

### Finding #25

**File:** `src/ui/app_router.py`  
**Class:** `AppRouter`  
**Function:** Alle Navigations-Methoden

#### Problem Description

Der Wechsel zwischen Dashboard und Modulen sowie zwischen Modulen untereinander erfolgt über `_stack.setCurrentIndex()`. Dies ist ein **sofortiger Wechsel** ohne jegliche Animation (kein Crossfade, kein Slide, kein Fade-Through).

Die einzigen Animationen finden auf Sidebar-Ebene statt:
- AppSidebar: Collapse/Expand (420ms)
- ModuleSidebar: Slide+Fade (Enter 380ms, Exit 200ms)

Der Content-Bereich (rechts neben der Sidebar) wechselt **hart** ohne visuelle Transition.

#### Why This Can Cause Animation Problems

Der harte View-Wechsel ohne Transition ist die primäre Ursache für das Gefühl von „nicht-smoothen" Übergängen. Obwohl technisch kein Performance-Problem, wirkt der sofortige Wechsel abrupt, besonders wenn:
- Die ModuleSidebar-Exit-Animation 200ms dauert, dann der View hart wechselt
- Die neue ModuleSidebar-Enter-Animation erst nach der AppSidebar-Collapse beginnt (420ms Verzögerung)
- Zwischen Exit und Enter kein visueller Zusammenhang besteht

#### Risk Level

**Medium** (UX, nicht Performance)

#### Suggested Improvement

Einen Content-Crossfade oder Fade-Through implementieren: Alten Content ausblenden (Opacity 1→0), neuen Content einblenden (Opacity 0→1). Dies kann parallel zu den Sidebar-Animationen laufen. Ein `AnimatedStackedWidget` als Drop-in-Replacement für `QStackedWidget` könnte dies kapseln.

---

### Finding #26

**File:** `src/ui/main_hub.py`, `src/ui/provision/provision_hub.py`, `src/ui/workforce/workforce_hub.py`, `src/ui/contact/contact_hub.py`  
**Class:** Alle Hubs  
**Function:** Sub-View-Navigation (`_show_*()`)

#### Problem Description

Innerhalb der Hubs erfolgt der Wechsel zwischen Sub-Panels ebenfalls über `content_stack.setCurrentIndex()` ohne jegliche Animation.

#### Why This Can Cause Animation Problems

Wie Finding #25: Harte View-Wechsel ohne Transition wirken abrupt.

#### Risk Level

**Low** (UX, nicht Performance)

#### Suggested Improvement

Wie Finding #25: Einen animierten Stack-Widget als Basis verwenden.

---

## Kategorie 7 – Signal-Storms und Cascading Updates

---

### Finding #27

**File:** `src/ui/app_router.py`  
**Class:** `AppRouter`  
**Function:** `_on_modules_updated()` (Zeile 530–572)

#### Problem Description

Bei jedem `modules_updated`-Signal vom GlobalHeartbeat wird die gesamte Modul-Sichtbarkeit neu berechnet:
1. `_dashboard.set_modules(visible)` – Dashboard-Admin-Button aktualisieren
2. `_sidebar.update_modules(user)` – Sidebar komplett neu bauen (Finding #24)
3. Prüfung, ob aktives Modul noch berechtigt ist → ggf. `show_dashboard()` + Toast

#### Why This Can Cause Animation Problems

Wenn der GlobalHeartbeat häufig feuert und sich die Module nicht geändert haben, wird trotzdem die gesamte Sidebar-Navigation zerstört und neu aufgebaut. Dies kann mit laufenden Sidebar-Animationen kollidieren.

#### Risk Level

**Medium**

#### Suggested Improvement

Einen Guard einbauen, der prüft, ob sich die Modul-Liste tatsächlich geändert hat, bevor die UI aktualisiert wird. Einen Hash der aktuellen Modul-Liste speichern und nur bei Änderung die UI aktualisieren.

---

### Finding #28

**File:** `src/ui/dashboard_screen.py`  
**Class:** `DashboardScreen`  
**Function:** `on_notifications_updated()` (Zeile 1218–1224)

#### Problem Description

Bei jedem Heartbeat-Notification-Update wird geprüft, ob sich die Anzahl ungelesener System-Nachrichten geändert hat. Wenn ja, wird `_reload_messages()` aufgerufen, was einen neuen Worker-Thread startet und nach Completion `_render_messages()` aufruft (Finding #11).

#### Why This Can Cause Animation Problems

Der GlobalHeartbeat feuert regelmäßig (Standard: alle 30s). Wenn die Unread-Count sich häufig ändert (z.B. bei aktiver Administration), werden Dashboard-Widgets wiederholt zerstört und neu erstellt. In Kombination mit laufenden Animations (z.B. wenn der User gerade vom Dashboard zu einem Modul wechselt) kann dies zu Konflikten führen.

#### Risk Level

**Low**

#### Suggested Improvement

Die Message-Aktualisierung nur durchführen, wenn das Dashboard sichtbar ist (`_stack.currentIndex() == 0`).

---

## Kategorie 8 – Strukturelle Probleme

---

### Finding #29

**File:** `src/ui/app_router.py`  
**Class:** `AppRouter`  
**Function:** `handle_call_pop()` (Zeile 631–644)

#### Problem Description

Beim eingehenden PSTN-Anruf (Call-Pop) wird die Navigation ohne jegliche Animation durchgeführt:
```python
self._stop_active_module_heartbeat()
self._sidebar.set_expanded(False)
self._ensure_contact()
self._stack.setCurrentIndex(_IDX_CONTACT)
self._start_module_heartbeat(...)
```

Es gibt keine Exit-Animation für das aktive Modul und keine Enter-Animation für die Contact-Sidebar.

#### Why This Can Cause Animation Problems

Der abrupte Wechsel ohne Animation bei einem eingehenden Anruf ist visuell störend. Zudem wird `set_expanded(False)` ohne Rücksicht auf den aktuellen Animations-Zustand der Sidebar aufgerufen.

#### Risk Level

**Low**

#### Suggested Improvement

Auch für Call-Pop den standardmäßigen Animations-Flow verwenden oder zumindest einen schnellen Fade-Through implementieren.

---

### Finding #30

**File:** `src/ui/dashboard_screen.py`  
**Class:** `DashboardScreen`  
**Function:** `_open_feedback()` / `_close_feedback()` (Zeile 962–997)

#### Problem Description

Beim Öffnen des Feedback-Overlays wird ein `QGraphicsBlurEffect` auf den gesamten Content angewendet:
```python
blur = QGraphicsBlurEffect()
blur.setBlurRadius(8)
self._content.setGraphicsEffect(blur)
```

#### Why This Can Cause Animation Problems

`QGraphicsBlurEffect` ist ein **CPU-basierter** Effekt in Qt Widgets (nicht GPU-beschleunigt wie in Qt Quick). Das Anwenden eines Blur-Effekts mit Radius 8 auf das gesamte Dashboard (mit ScrollArea, KPI-Cards, Nachrichten etc.) erzwingt ein Software-Rendering des gesamten Content-Bereichs in einen Off-Screen-Buffer, die Blur-Berechnung und anschließendes Compositing. Dies kann je nach Dashboard-Größe und -Komplexität 50–200ms für einen einzelnen Frame dauern. Wenn gleichzeitig eine Fade-In-Animation auf dem Overlay läuft, kann es zu Frame-Drops kommen.

#### Risk Level

**High**

#### Suggested Improvement

Statt `QGraphicsBlurEffect` ein halbtransparentes Overlay (z.B. `QColor(0, 15, 30, 180)`) als Backdrop verwenden. Dies ist wesentlich performanter. Alternativ: Den Blur-Effekt in einem separaten Rendering-Pass berechnen und als statisches `QPixmap` cachen.

---

### Finding #31

**File:** `src/ui/dashboard_screen.py`  
**Class:** `DashboardScreen`  
**Function:** `_open_settings()` (Zeile 1079–1087)

#### Problem Description

Wie Finding #30 wird auch beim Öffnen des Settings-Overlays ein `QGraphicsBlurEffect` angewendet:
```python
blur = QGraphicsBlurEffect()
blur.setBlurRadius(8)
self._content.setGraphicsEffect(blur)
```

#### Why This Can Cause Animation Problems

Identisch mit Finding #30: CPU-basierter Blur auf dem gesamten Dashboard-Content.

#### Risk Level

**High**

#### Suggested Improvement

Wie Finding #30: Halbtransparentes Overlay statt Blur.

---

### Finding #32

**File:** `src/ui/components/module_sidebar.py`  
**Class:** `ModuleSidebar`  
**Function:** `_apply_enter_frame()` (Zeile 281–288)

#### Problem Description

Bei jedem Animation-Frame werden zwei Operationen ausgeführt:
```python
self.setContentsMargins(offset, 0, 0, 0)
self._opacity_effect.setOpacity(opacity)
```

`setContentsMargins()` löst bei jedem Frame ein vollständiges Layout-Reflow der Sidebar und aller ihrer Kind-Widgets aus.

#### Why This Can Cause Animation Problems

Bei einer 380ms-Animation werden ca. 23 Layout-Neuberechnungen durchgeführt (bei 60fps). Die Sidebar enthält typisch 8–12 NavButtons, Labels und Separatoren. Jedes Layout-Reflow berechnet die Geometrie aller Kinder neu. Dies ist signifikant teurer als eine reine Transform-basierte Animation.

#### Risk Level

**Medium**

#### Suggested Improvement

Statt `setContentsMargins()` für den Slide-Effekt eine `QPropertyAnimation` auf `geometry()` oder `pos()` verwenden. Noch besser: Die Sidebar in einen Container-Widget einbetten, dessen `pos()` animiert wird, ohne dass ein Layout-Reflow ausgelöst wird.

---

### Finding #33

**File:** `src/ui/archive_boxes_view.py`  
**Class:** `ArchiveBoxesView`  
**Function:** `_on_cache_refresh_finished()` → `_proxy_model.sort()` (referenziert über Zeile 698, 1158)

#### Problem Description

Nach jedem Cache-Refresh wird `_proxy_model.sort()` auf dem Main Thread aufgerufen. Bei einer Tabelle mit 500+ Dokumenten kann die Sortierung mehrere hundert Millisekunden dauern.

#### Why This Can Cause Animation Problems

Die Sortierung blockiert den Main Thread. Da der Cache-Refresh alle 20 Sekunden durch den Auto-Refresh ausgelöst wird, kann dies regelmäßig zu kurzen Freezes führen, die während jeder laufenden Animation spürbar sind.

#### Risk Level

**Medium**

#### Suggested Improvement

Die Sortierung nur bei tatsächlicher Datenänderung durchführen (nicht bei jedem Refresh). Alternativ: Die Sortierung in einem separaten Worker-Thread auf den Rohdaten durchführen und nur das fertig sortierte Model an den Main Thread übergeben.

---

### Finding #34

**File:** `src/ui/main_hub.py`  
**Class:** `MainHub`  
**Function:** `_extract_outlook_emails()` (Zeile 1225–1298)

#### Problem Description

Die Outlook-COM-Integration (`win32com.client.GetActiveObject("Outlook.Application")`) und das Speichern von E-Mails als .msg-Dateien (`item.SaveAs(target_path, OL_MSG_FORMAT)`) laufen **im Main Thread**.

#### Why This Can Cause Animation Problems

COM-Aufrufe zu Outlook sind synchron und können je nach Outlook-Zustand (große Mailbox, viele Anhänge) mehrere Sekunden dauern. Während dieser Zeit ist die gesamte UI eingefroren. Da dies im Drop-Event-Handler passiert, blockiert es direkt die Event Loop.

#### Risk Level

**Critical**

#### Suggested Improvement

Die Outlook-COM-Extraktion in einen Worker-Thread auslagern. COM-Aufrufe müssen mit `pythoncom.CoInitialize()` im Worker-Thread initialisiert werden. Ein Loading-Indikator sollte dem Benutzer zeigen, dass die E-Mails verarbeitet werden.

---

### Finding #35

**File:** `src/ui/dashboard_screen.py`  
**Class:** `DashboardScreen`  
**Function:** `resizeEvent()` (Zeile 1181–1189)

#### Problem Description

Bei jeder Größenänderung des Fensters werden drei Geometrie-Updates durchgeführt:
```python
self._content.setGeometry(self.rect())
self._settings_overlay.setGeometry(self.rect())
self._feedback_overlay.setGeometry(self.rect())
```

#### Why This Can Cause Animation Problems

Da `DashboardScreen` kein Layout für `_content` verwendet (es wird manuell per `setGeometry()` positioniert), müssen alle Kind-Widgets bei jeder Größenänderung manuell aktualisiert werden. Bei schnellem Fenster-Resize (z.B. Drag am Rand) werden viele `resizeEvent()`-Aufrufe generiert. Jedes `setGeometry()` löst ein Layout-Update des jeweiligen Widgets und aller Kinder aus. In Kombination mit `_position_feedback_pill()` sind das 4 separate Geometrie-Updates pro Resize-Event.

#### Risk Level

**Low**

#### Suggested Improvement

Ein `QVBoxLayout` für das Dashboard verwenden, damit Qt die Geometrie automatisch verwaltet. Overlays können über `resizeEvent` oder als Child-Widget mit `Qt.FramelessWindowHint` realisiert werden.

---

### Finding #36

**File:** `src/ui/app_router.py`  
**Class:** `AppRouter`  
**Function:** `__init__()` (Zeile 122–136)

#### Problem Description

Im Konstruktor des AppRouter werden mehrere schwere Operationen synchron ausgeführt:
1. `DashboardScreen(...)` – Erstellt das gesamte Dashboard (KPI, QuickActions, Messages, Overlays)
2. `self._dashboard.load_messages(api_client)` – Startet Worker-Thread
3. `self._dashboard.load_kpi_data()` – Startet Worker-Thread

#### Why This Can Cause Animation Problems

Die Erstellung des `DashboardScreen` ist eine schwere Operation (1366 Zeilen Init-Code). Dies passiert synchron beim Login-Prozess und verzögert die Anzeige des Hauptfensters. Obwohl die Daten-Loads in Worker-Threads laufen, blockiert die UI-Konstruktion den Main Thread.

#### Risk Level

**Medium**

#### Suggested Improvement

Das Dashboard in Phasen aufbauen: Erst das minimale Header-Layout anzeigen, dann die KPI-Cards, QuickActions und Messages-Sektion per `QTimer.singleShot(0, ...)` in separaten Event-Loop-Zyklen aufbauen.

---

### Finding #37

**File:** `src/ui/components/sidebar.py`  
**Class:** `AppSidebar`  
**Function:** `_on_anim_finished()` (Zeile 327–342)

#### Problem Description

Nach Abschluss der Collapse-Animation werden mehrere synchrone Operationen durchgeführt:
```python
for item in self._nav_items.values():
    item.set_collapsed(True)          # Text + Tooltip + Admin-Button-Visibility
for lbl in self._collapsible_labels:
    lbl._expanded_text = lbl.text()   # Text sichern
    lbl.setText("")                    # Text entfernen
for lbl in self._collapsible_labels:
    effect = lbl.graphicsEffect()
    effect.setOpacity(1.0)            # Opacity zurücksetzen
```

#### Why This Can Cause Animation Problems

Die drei For-Loops modifizieren Text, Visibility und Opacity von allen NavItems und Labels gleichzeitig nach der Animation. Jede Text-Änderung kann ein Repaint auslösen. Da dies der Callback der Collapse-Animation ist und direkt **vor** der ModuleSidebar-Enter-Animation steht (über `collapse_finished`-Signal), können diese Repaints den Start der nächsten Animation verzögern.

#### Risk Level

**Low**

#### Suggested Improvement

Die Post-Animation-Updates batchweise durchführen mit `setUpdatesEnabled(False)` vor den Änderungen und `setUpdatesEnabled(True)` danach, um einen einzigen Repaint auszulösen statt mehrerer.

---

## Zusammenfassung

> **Remediation Status (2026-03-11):** 28 von 37 Findings behoben.
> Details: `UI_ANIMATION_REMEDIATION.md`

### Kritisch (4)

| # | Problem | Datei | Status |
|---|---------|-------|--------|
| 1 | Synchroner SmartScan-API-Call im Main Thread | `archive_boxes_view.py` | ✅ Resolved |
| 3 | Synchroner API-Call im Widget-Konstruktor | `archive_boxes_view.py` | ✅ Resolved |
| 22 | Vollständiger UI-Rebuild bei Theme/Font/Sprache-Änderung | `dashboard_screen.py` | ⚠️ Partially resolved |
| 34 | Outlook-COM-Aufrufe im Main Thread | `main_hub.py` | ✅ Resolved (bereits implementiert) |

### Hoch (9)

| # | Problem | Datei | Status |
|---|---------|-------|--------|
| 2 | SmartScan-Status beim Admin-Leave | `main_hub.py` | ✅ Resolved |
| 5 | PDF-Laden im Main Thread | `pdf_viewer.py` | ❌ Not yet resolved |
| 6 | Doppelter synchroner API-Call beim SmartScan-Settings-Tab | `smartscan_settings.py` | ✅ Resolved |
| 8 | Synchrone API-Calls vor Mail-Import | `bipro_view.py` | ✅ Resolved |
| 9 | Widget-Erstellung während Navigation (wenn Preload nicht abgeschlossen) | `app_router.py` | ⚠️ Partially resolved |
| 10 | Synchrone View-Erstellung beim ersten Sub-View-Zugriff | `main_hub.py` | ⚠️ Partially resolved |
| 16 | 420ms Lücke zwischen View-Wechsel und ModuleSidebar-Enter | `app_router.py` | ✅ Resolved |
| 19 | Gestoppte Animation emittiert kein `collapse_finished` | `sidebar.py` | ✅ Resolved |
| 23 | Dreifacher globaler Repaint bei Settings-Save | `dashboard_screen.py` | ✅ Resolved |
| 30/31 | CPU-basierter QGraphicsBlurEffect auf Dashboard | `dashboard_screen.py` | ✅ Resolved |

### Mittel (11)

| # | Problem | Datei | Status |
|---|---------|-------|--------|
| 4 | CSV-Export im UI-Handler | `auszahlungen_panel.py` | ❌ Not yet resolved (deferred) |
| 7 | Synchroner API-Call beim SmartScan-History-Tab | `smartscan_history.py` | ✅ Resolved |
| 12 | Widget-Erstellung in Schleifen (StatsView) | `stats_view.py` | ❌ Not yet resolved (deferred) |
| 13 | Widget-Erstellung in Schleifen (ContactsView) | `contacts_view.py` | ❌ Not yet resolved (deferred) |
| 14 | processEvents() in Loading-Overlay | `archive_boxes_view.py` | ✅ Resolved |
| 15 | Mehrfache processEvents() in Progress-Overlay | `archive/widgets.py` | ✅ Resolved |
| 17 | setContentsMargins()-Layout-Reflow bei jedem Frame | `module_sidebar.py` | ⚠️ Partially resolved |
| 18 | Signal-Reentrancy durch dynamische Verbindungen | `app_router.py` | ✅ Resolved |
| 20 | Animation-Überlappung bei schnellem Klick (Overlays) | `dashboard_screen.py` | ✅ Resolved |
| 21 | 12 Layout-Operationen beim Preload | `app_router.py` | ✅ Resolved |
| 27 | Sidebar-Rebuild bei jedem Heartbeat-modules_updated | `app_router.py` | ✅ Resolved |
| 32 | Layout-Reflow bei ModuleSidebar-Animation | `module_sidebar.py` | ⚠️ Partially resolved |
| 33 | Tabellensortierung bei jedem Cache-Refresh | `archive_boxes_view.py` | ✅ Verified (kein Fix nötig) |

### Niedrig (9)

| # | Problem | Datei | Status |
|---|---------|-------|--------|
| 11 | Message-Cards bei jedem Update neu erstellt | `dashboard_screen.py` | ✅ Resolved |
| 24 | Sidebar-Module bei jedem Heartbeat-Update neu erstellt | `sidebar.py` | ✅ Resolved |
| 25 | Fehlende Content-Transition-Animation (AppRouter) | `app_router.py` | ✅ Resolved (FadeStackedWidget) |
| 26 | Fehlende Content-Transition-Animation (Sub-Hubs) | alle Hubs | ✅ Resolved (FadeStackedWidget) |
| 28 | Dashboard-Messages-Reload auch wenn nicht sichtbar | `dashboard_screen.py` | ✅ Resolved |
| 29 | Call-Pop ohne Animation | `app_router.py` | ✅ Resolved |
| 35 | Manuelle Geometrie-Updates statt Layout | `dashboard_screen.py` | ❌ Not yet resolved (deferred) |
| 36 | Schwere Dashboard-Konstruktion im AppRouter-Init | `app_router.py` | ❌ Not yet resolved (deferred) |
| 37 | Batch-Repaints nach Collapse-Animation | `sidebar.py` | ✅ Resolved |

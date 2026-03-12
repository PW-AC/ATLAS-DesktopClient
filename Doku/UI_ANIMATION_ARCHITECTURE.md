# ACENCIA ATLAS – UI Animation & Transition Architecture

> **Erstellt:** 2026-03-11  
> **Scope:** ATLAS Desktop Client (`src/ui/`)  
> **Zweck:** Dokumentation der UI-Architektur mit Fokus auf Navigation, Animationen, Transitions und Threading-Modell.

---

## 1. Gesamtübersicht

Die ATLAS Desktop-Anwendung ist eine PySide6 (Qt 6)-basierte Applikation mit ca. 108 Python-Dateien allein im `src/ui/`-Verzeichnis. Die UI folgt einem **Hub-Sidebar-Stack**-Pattern: Ein zentraler Router (`AppRouter`) steuert über einen `QStackedWidget` die Anzeige von Modulen (Hubs), die jeweils eigene `QStackedWidget`-Instanzen für ihre Sub-Views enthalten.

### Widget-Hierarchie (Top-Level)

```
QApplication
  └── AppRouter (QMainWindow)
        ├── AppSidebar (QFrame)  ← persistente linke Sidebar
        └── QStackedWidget (_stack)
              ├── [0] DashboardScreen (QWidget)
              ├── [1] MainHub (QMainWindow)        ← Core-Modul
              ├── [2] ProvisionHub (QWidget)        ← Ledger-Modul
              ├── [3] WorkforceHub (QWidget)        ← Workforce-Modul
              ├── [4] ContactHub (QWidget)          ← Contact-Modul
              └── [5+] ModuleAdminShell (QWidget)   ← dynamisch
```

---

## 2. Dashboard Widget-Hierarchie

```
DashboardScreen (QWidget)
  ├── _content (QWidget)
  │     ├── Header (QWidget)
  │     │     ├── Greeting Label
  │     │     ├── Meta Label
  │     │     ├── Date/Time Labels
  │     │     ├── Admin Button
  │     │     └── Logout Button
  │     └── QScrollArea
  │           └── Dashboard Content (QWidget)
  │                 ├── KpiCardsWidget
  │                 ├── QuickActionsWidget
  │                 └── Messages Section (Container)
  │                       └── Message Cards (dynamisch, max 3)
  ├── _SettingsOverlay (QWidget)  ← modal, mit Fade-Animation
  ├── FeedbackOverlay (QWidget)   ← modal, mit Fade-Animation
  └── _feedback_btn (QPushButton) ← Floating Pill
```

---

## 3. Modul-Hub-Hierarchie (gemeinsames Pattern)

Alle Module folgen demselben Aufbau:

```
[Module]Hub (QWidget / QMainWindow)
  ├── ModuleSidebar (QFrame)  ← mit Slide+Fade-Animation
  │     ├── Back-Button
  │     ├── Section Labels
  │     └── ModuleNavButtons
  └── QStackedWidget (_content_stack)
        ├── [0] Placeholder → echtes Panel (lazy)
        ├── [1] Placeholder → echtes Panel (lazy)
        └── [n] ...
```

### Konkrete Module

| Modul           | Hub-Klasse     | Datei                           | Panels |
|-----------------|----------------|---------------------------------|--------|
| Core            | MainHub        | `ui/main_hub.py`                | 7+     |
| Ledger          | ProvisionHub   | `ui/provision/provision_hub.py` | 10     |
| Workforce       | WorkforceHub   | `ui/workforce/workforce_hub.py` | 7      |
| Contact         | ContactHub     | `ui/contact/contact_hub.py`     | 6      |
| Admin (global)  | AdminShell     | `ui/admin/admin_shell.py`       | 17+    |
| Modul-Admin     | ModuleAdminShell| `ui/module_admin/`             | dyn.   |

---

## 4. Navigation Flow

### 4.1 Dashboard → Modul

```
Benutzer klickt Modul in AppSidebar
  → _SidebarNavItem.clicked Signal
  → AppSidebar._on_module_clicked(module_key)
  → AppSidebar.module_requested.emit(module_id)
  → AppRouter._open_module(module_id)
  → AppRouter._do_open_module(module_id, from_dashboard=True)
       1. _stop_active_module_heartbeat()
       2. _ensure_<modul>()  ← Lazy Init: Import + Widget-Erstellung + Stack-Ersetzung
       3. _stack.setCurrentIndex(IDX)  ← View-Wechsel (kein Crossfade)
       4. QTimer.singleShot(0, heartbeat_start)
       5. Sidebar-Collapse: set_expanded(False) mit Animation
       6. Nach collapse_finished → ModuleSidebar.play_enter_animation()
```

### 4.2 Modul → Modul (mit Exit-Animation)

```
Benutzer klickt anderes Modul in AppSidebar
  → AppRouter._open_module(module_id)
  → Erkennt: from_module = True
  → Holt aktive ModuleSidebar des alten Moduls
  → Speichert Ziel in _pending_module_id
  → old_sidebar.play_exit_animation()  ← 200ms Slide+Fade Out
  → exit_animation_finished Signal
  → AppRouter._on_exit_finished_open_module()
       → _do_open_module(pending_id)
            1. _ensure_<neues_modul>()
            2. _stack.setCurrentIndex(IDX)
            3. ModuleSidebar.play_enter_animation()  ← 380ms Slide+Fade In
```

### 4.3 Modul → Dashboard

```
Benutzer klickt Dashboard in AppSidebar
  → AppRouter.show_dashboard()
  → old_sidebar.play_exit_animation()  ← 200ms
  → _do_show_dashboard()
       1. _stop_active_module_heartbeat()
       2. _stack.setCurrentIndex(0)
       3. QTimer.singleShot(0, sidebar.set_expanded(True))
            → AppSidebar Expand-Animation ← 420ms
```

### 4.4 Sub-View-Navigation innerhalb eines Hubs

```
Benutzer klickt NavButton in ModuleSidebar
  → ModuleNavButton.clicked Signal
  → Hub._show_<panel>(index)
       1. if Panel not loaded: lazy import + Widget-Erstellung
       2. Placeholder entfernen, Panel einfügen
       3. _content_stack.setCurrentIndex(idx)
```

---

## 5. Animationsmechanismen

### 5.1 AppSidebar – Collapse/Expand

| Eigenschaft     | Wert                            |
|-----------------|---------------------------------|
| **Datei**       | `ui/components/sidebar.py`      |
| **Technik**     | `QPropertyAnimation` auf Custom `sidebarWidth` Property |
| **Dauer**       | 420ms (Breite), 180ms (Label-Fade) |
| **Easing**      | OutCubic (Breite), InOutQuad (Fade) |
| **Gruppierung** | `QParallelAnimationGroup` (Breite + mehrere Label-Fades) |
| **Label-Fade**  | `QSequentialAnimationGroup` mit `QPauseAnimation` (Delay) |
| **Opacity**     | `QGraphicsOpacityEffect` auf Section-Labels |

### 5.2 ModuleSidebar – Enter/Exit Slide+Fade

| Eigenschaft     | Wert                                  |
|-----------------|---------------------------------------|
| **Datei**       | `ui/components/module_sidebar.py`     |
| **Technik**     | `QTimeLine` (0..1000 Frames)          |
| **Enter-Dauer** | 380ms                                 |
| **Exit-Dauer**  | 200ms                                 |
| **Easing**      | OutCubic (Enter), InCubic (Exit)      |
| **Slide**       | `setContentsMargins(-SIDEBAR_WIDTH → 0)` |
| **Fade**        | `QGraphicsOpacityEffect.setOpacity()` |
| **Signal**      | `exit_animation_finished` nach Exit   |

### 5.3 Overlay-Animationen (Settings, Feedback, Contact)

| Overlay              | Datei                              | Fade-In | Fade-Out | Technik                  |
|----------------------|------------------------------------|---------|----------|--------------------------|
| SettingsOverlay      | `ui/dashboard_screen.py`           | 200ms   | 150ms    | QPropertyAnimation       |
| FeedbackOverlay      | `ui/feedback_overlay.py`           | 250ms   | 180ms    | QPropertyAnimation       |
| ContactDetailOverlay | `ui/contact/contact_detail_overlay.py` | 200ms | 150ms  | QPropertyAnimation       |

Alle verwenden `QGraphicsOpacityEffect` mit `QPropertyAnimation` auf `b"opacity"`.

### 5.4 Toast-Animationen

| Eigenschaft     | Wert                          |
|-----------------|-------------------------------|
| **Datei**       | `ui/toast.py`                 |
| **Technik**     | QPropertyAnimation + QGraphicsOpacityEffect |
| **Fade-Out**    | konfigurierbar (FADE_OUT_DURATION) |
| **Easing**      | OutCubic                      |
| **Auto-Dismiss**| QTimer.singleShot             |

### 5.5 Lade-Animationen (Dots/Spinner)

| Widget           | Datei                          | Technik                          |
|------------------|--------------------------------|----------------------------------|
| LoadingOverlay   | `ui/provision/widgets.py`      | QTimer (interval) → `_animate()` |
| ProgressOverlay  | `ui/archive/widgets.py`        | QTimer → `_animate_dots()`       |

---

## 6. Threading-Modell

### 6.1 Haupt-Thread (UI Thread)

Der Main Thread verarbeitet:
- Alle Widget-Erstellung und -Layout
- Qt Event Loop (`QApplication.exec()`)
- Signal-Slot-Verbindungen (standardmäßig `AutoConnection`)
- Animationen (`QPropertyAnimation`, `QTimeLine`)
- View-Transitions (`setCurrentIndex`, `show/hide`)

### 6.2 Worker-Threads (QThread)

| Worker                      | Datei                             | Aufgabe                        |
|-----------------------------|-----------------------------------|--------------------------------|
| `_LoadMessagesWorker`       | `ui/dashboard_screen.py`          | Mitteilungen laden             |
| `_Worker` (Feedback)        | `ui/dashboard_screen.py`          | Feedback-Submit an API         |
| `UpdateCheckWorker`         | `ui/main_hub.py`                  | Update-Check                   |
| `DropUploadWorker`          | `ui/main_hub.py`                  | Drag&Drop Upload               |
| `_R` (PDF-Loader)           | `ui/archive/dialogs.py`           | PDF-Datei laden                |

### 6.3 Worker-Runnables (QRunnable / QThreadPool)

| Modul         | Worker-Klassen                                          |
|---------------|--------------------------------------------------------|
| Workforce     | `_LoadEmployersWorker`, `_LoadEmployeesWorker`, `_FetchDetailWorker`, `_LoadSnapshotsWorker`, `_SnapshotDiffWorker`, `_LoadExportsWorker` |
| Provision     | `_ProvDataFingerprintWorker`                            |
| Contact       | `_ContactDataFingerprintWorker`                         |
| Archive       | diverse Worker via Presenter (Cache, Stats, AI-Data)    |

### 6.4 Global Heartbeat

| Eigenschaft | Wert |
|-------------|------|
| **Klasse**  | `GlobalHeartbeat` (`services/global_heartbeat.py`) |
| **Aufgabe** | Session-Validierung, Notifications, Modul-Updates |
| **Signals** | `session_invalid`, `notifications_updated`, `system_status_changed`, `modules_updated` |

### 6.5 Modul-Heartbeat

Jeder Hub hat einen eigenen 15-Sekunden-Timer (`_module_heartbeat_timer`), der bei Aktivierung gestartet und bei Deaktivierung gestoppt wird. Der AppRouter steuert dies über `start_module_heartbeat()` / `stop_module_heartbeat()`.

---

## 7. Modul-Instanziierung

### 7.1 Lazy-Loading-Pattern

Module werden **nicht beim Start** erstellt, sondern beim ersten Zugriff:

```
AppRouter.__init__():
  _stack.addWidget(QWidget())  ← Placeholder für jedes Modul

AppRouter._ensure_<modul>():
  if self._<modul>_widget is not None:
      return  ← bereits geladen
  from ui.<modul> import <Modul>Hub
  widget = <Modul>Hub(api_client, auth_api)
  old = _stack.widget(IDX)
  _stack.removeWidget(old)
  old.deleteLater()
  _stack.insertWidget(IDX, widget)
```

### 7.2 Boot-Preload

Nach dem Start werden Module vorgeladen:

```
AppRouter.__init__():
  _preload_queue = [_ensure_core, _ensure_ledger, _ensure_workforce, _ensure_contact]
  QTimer.singleShot(0, _preload_next_module)

_preload_next_module():
  fn = _preload_queue.pop(0)
  fn()  ← Modul importieren + Widget erstellen
  if queue not empty:
      QTimer.singleShot(0, _preload_next_module)  ← nächstes im nächsten Event-Loop-Zyklus
```

### 7.3 Sub-View Lazy-Loading (innerhalb Hubs)

Panels/Views innerhalb der Hubs folgen demselben Pattern:

```
MainHub._show_<view>():
  if self._<view> is None:
      from ui.<view> import <View>
      self._<view> = <View>(...)
      content_stack.removeWidget(placeholder)
      content_stack.insertWidget(idx, self._<view>)
  content_stack.setCurrentIndex(idx)
```

---

## 8. View-Transitions

### 8.1 Transition-Mechanismus

View-Wechsel basieren auf `QStackedWidget.setCurrentIndex()` / `setCurrentWidget()`:
- **Kein Crossfade** zwischen Views
- **Kein Slide** zwischen Views
- **Sofortiger Wechsel** (harter Schnitt)

Die Animation findet nur auf der **Sidebar-Ebene** statt:
- AppSidebar: Collapse/Expand (420ms)
- ModuleSidebar: Slide+Fade Enter (380ms) / Exit (200ms)

### 8.2 Overlay-Transitions

Overlays (Settings, Feedback, Contact) verwenden:
- Background-Blur (`QGraphicsBlurEffect`) auf den Inhalt dahinter
- Opacity-Fade-In/Out (`QPropertyAnimation` + `QGraphicsOpacityEffect`)

---

## 9. Event-Loop-Interaktion

### 9.1 processEvents()-Verwendung

`QApplication.processEvents()` wird an folgenden Stellen aufgerufen:

| Datei                       | Funktion                    | Kontext                              |
|-----------------------------|-----------------------------|--------------------------------------|
| `ui/archive_boxes_view.py`  | `_show_loading()`           | Loading-Overlay sofort sichtbar machen |
| `ui/archive/widgets.py`     | `show_progress()`           | Progress-Overlay sofort sichtbar     |
| `ui/archive/widgets.py`     | `update_progress()`         | Fortschritt aktualisieren            |
| `ui/archive/widgets.py`     | `show_completion()`         | Ergebnis sofort sichtbar             |

### 9.2 QTimer.singleShot(0, ...) – Deferred Execution

Wird extensiv verwendet, um Aktionen in den nächsten Event-Loop-Zyklus zu verschieben:
- Modul-Preload (`app_router.py:161, 190`)
- Navigation nach Exit-Animation (`app_router.py:214`)
- Sidebar-Expand nach Dashboard-Wechsel (`app_router.py:224`)
- Heartbeat-Start (`app_router.py:276, 286, 294, 302, 310`)
- UI-Rebuild nach Settings-Änderung (`dashboard_screen.py:1136`)
- Initiales Archiv-Laden (`archive_boxes_view.py:226`)

---

## 10. Rendering-Pfade

### 10.1 Stylesheet-basiertes Rendering

Die gesamte Anwendung verwendet `setStyleSheet()` für das Styling. Alle Style-Tokens sind in `ui/styles/tokens.py` (1400 Zeilen) zentralisiert. Stylesheets werden als f-Strings inline in Widget-Konstruktoren gesetzt.

### 10.2 Custom Paint

Minimal eingesetzt:
- `_SettingsOverlay.paintEvent()` → `QPainter.fillRect()` für Backdrop-Overlay
- `CircularProgress` (Provision) → Custom paint für Kreisdiagramm

### 10.3 Graphics Effects

| Effekt                      | Verwendung                                |
|-----------------------------|-------------------------------------------|
| `QGraphicsOpacityEffect`    | Overlays, Toasts, Sidebars, Labels        |
| `QGraphicsBlurEffect`       | Backdrop für modale Overlays              |
| `QGraphicsDropShadowEffect` | Feedback-Pill-Button                      |

---

## 11. Zusammenfassung der Architektur-Charakteristiken

| Aspekt                  | Bewertung                                        |
|-------------------------|--------------------------------------------------|
| **Routing**             | Zentraler AppRouter mit festem Stack-Index-Schema |
| **Lazy Loading**        | Konsequent umgesetzt (Placeholder → echtes Widget)|
| **Boot-Preload**        | Vorhanden, sequenziell per QTimer.singleShot(0)   |
| **Animations**          | Nur Sidebars und Overlays; keine View-Transitions  |
| **Threading**           | QThread/QRunnable für viele (nicht alle) I/O-Ops   |
| **processEvents()**     | 4 Stellen, alle in Loading-/Progress-Overlays      |
| **Widget-Caching**      | Implizit: einmal erstellte Widgets bleiben im Stack |
| **View-Transition**     | Harter Schnitt (kein Crossfade/Slide)              |
| **Stylesheet-System**   | Inline f-String setStyleSheet() auf allen Widgets   |

---
description: Atomic design layering, signal-up/handle-down flow, and styling for the Qt Widgets UI
paths:
  - "app/src/ui/**"
---

# UI architecture (Qt Widgets, atomic design)

Owner of: layer boundaries, signal direction, styling. Object lifetime is in `cpp-qt.md`; anything touching `BrowserView`'s CEF internals is in `cef.md`.

This project uses **Qt Widgets only**. There is no QML, no Qt Quick, and no `.ui` files — do not introduce them without an explicit decision recorded in `ARCHITECTURE.md`.

## Layers

| Layer | Directory | May know about |
|---|---|---|
| atoms | `app/src/ui/atoms/` | Qt only. No app concepts. |
| molecules | `app/src/ui/molecules/` | atoms |
| organisms | `app/src/ui/organisms/` | molecules, atoms |
| templates | `app/src/ui/templates/` | organisms, app state, CEF via `BrowserView`/`TabManager` |

Composition flows upward only. An atom must never include an organism; an organism must never reach into the window that owns it.

## Signal-up, handle-down

Organisms and molecules **emit intent** and never act on the window or the browser:

```
UrlBar::urlEntered → BottomBar::urlEntered → RootWindow::navigateTo → TabManager::navigateCurrent
OpenPagesPanel::newTabRequested → SidebarShell::newTabRequested → RootWindow → TabManager::createTab
  → tabAdded → RootWindow::refreshOpenPages() → SidebarShell::setPages → OpenPagesPanel::setPages
```

- Do not `qobject_cast` a parent to call methods on it. That bug existed (the old, deleted `Sidebar` casting to `QMainWindow*`, silently dead under `RootWindow`) and was removed deliberately — reintroducing it is a regression.
- State flows back down through slots (`SidebarShell::setPages`, `SidebarShell::setContextSummary`, `SidebarShell::setCurrentWorkspace`), not by the organism querying the template. `TabManager` is the sole owner of open-tab state; `OpenPagesPanel` never caches indices — it rebuilds every row from `TabManager::titleAt()`/`count()` on each change, because positional indices shift on every `closeTab()`.
- New cross-cutting behavior belongs in the template, wired from organism signals.

## Adding components

Place by layer, mirroring existing naming (`PascalCase.{h,cpp}`, class name matches file):

| Layer | Directory | Rule of thumb |
|---|---|---|
| atom | `ui/atoms/` | Qt only, no app concepts (`IconButton`) |
| molecule | `ui/molecules/` | Composes atoms, emits intent (`UrlBar`) |
| organism | `ui/organisms/` | A UI region (`SidebarShell`, `ApplicationDetailPanel`) |
| dialog | `ui/organisms/dialogs/` | Modal (`AddApplicationDialog`) |
| page | `ui/pages/` | One per `Workspace` enum value |
| template | `ui/templates/` | `RootWindow` and `TabManager` only — a third needs an architecture decision first |

A component that displays web content composes `BrowserView`; it does not talk to CEF itself. Register new pairs in the correct target's lists — see `build.md`.

## Styling

- Themes live in `app/src/ui/styles/themes/{light,dark}.qss`, are bundled through `app/src/resources/resources.qrc`, and load via `RootWindow::applyTheme` at `:/styles/themes/<name>.qss`. A new theme file must be added to the `.qrc` or it silently fails to load at runtime.
- `theme.py` regenerates the QSS from palette dictionaries. If you edit palettes, edit `theme.py` and regenerate rather than hand-patching both files.
- **Known debt:** several atoms and organisms call `setStyleSheet()` inline with hardcoded purple values, which override the theme QSS for those widgets. Do not add new inline color styling. Prefer `setObjectName()` plus a QSS selector so themes can reach it. Migrating the existing inline styles is planned work — do not do it opportunistically inside an unrelated change.
- **An unstyled widget takes the SYSTEM palette, not the app theme.** With Windows in dark mode and the light theme active, an unnamed `QScrollArea`, its viewport, a `QComboBox`, or a `QCheckBox` indicator renders near-black behind dark text. Every new surface needs an `objectName` and a rule in `theme.py` — see `#applicationDetailScroll`/`#applicationDetailViewport` and the combo rules for the pattern. This is invisible on a light-mode machine, so it will not show up in casual testing.
- **A QSS property selector only matches if the property is set before the widget is polished.** `QDialogButtonBox::addButton(text, role)` creates *and* parents the button immediately, so `setProperty("variant", ...)` afterwards never matches `QPushButton[variant="primary"]` and the button silently falls back to the system palette. Construct the `QPushButton`, set the property, *then* `addButton(button, role)`.
- Render new UI through `tool_applicationshots` (offscreen, both themes) before calling it done — that harness is what caught both of the above.

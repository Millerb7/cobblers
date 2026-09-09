---
description: CEF browser lifecycle, threading, and HWND embedding correctness
paths:
  - "app/src/handlers/**"
  - "app/src/ui/organisms/BrowserView.*"
  - "app/src/ui/templates/TabManager.*"
  - "app/src/main.cpp"
---

# CEF integration

Owner of: **correctness** — threading, lifecycle, embedding. Security decisions (what handlers must exist, URL policy, sandbox) are owned by `security.md`. Read both before changing `handlers/`.

The engine is **CEF 135 (Chromium 135)**, embedded as a child HWND. It is not Qt WebEngine — Qt WebEngine APIs and advice do not apply.

## Threading — the rule that breaks things silently

CEF runs with `multi_threaded_message_loop = true`. **CEF client callbacks arrive on the CEF UI thread, not the Qt thread.** Touching a `QWidget` from a CEF callback is undefined behavior that usually manifests as a hang or a blank window, not a crash.

The established pattern (`BrowserView::createBrowser`) is the only approved one:

```cpp
QPointer<BrowserView> self(this);
auto onCreated = [self](CefRefPtr<CefBrowser> b) {
    QMetaObject::invokeMethod(qApp, [self, b]() { if (self) self->onBrowserCreated(b); });
};
```

- `SimpleHandler` is a **thin callback bridge**. It must not touch HWNDs, widgets, or window state — that responsibility was deliberately removed from it.
- Every new CEF callback follows the same shape: forward from the handler, hop to the Qt thread with `QMetaObject::invokeMethod(qApp, ...)`, guard with `QPointer`.
- `CefBrowser`/`CefFrame` methods (e.g. `LoadURL`) are safe to call **from** the Qt thread.
- `CEF_REQUIRE_UI_THREAD()` at the top of handler methods documents and asserts the thread; keep it.

## Lifecycle and ownership

- One `BrowserView` owns exactly one `CefBrowser`. Creation is async — `browser` is null until `OnAfterCreated` marshals back. Any method that may run before then must handle the null case (see `loadUrl`'s `pendingUrl` fallback); do not add busy-waits.
- `CefRefPtr` is intrusive refcounting; never `delete` a CEF object and never store a raw `CefBrowser*`.
- Handlers use `IMPLEMENT_REFCOUNTING`. A handler outlives the widget that created it if CEF still holds a reference — this is exactly why callbacks need `QPointer`.
- **Per-window ownership only.** No `static`/global map of browsers, tabs, or HWNDs. Such a map existed, made multi-window impossible, and was removed.

## HWND embedding

- The container widget calls `winId()` to force a native HWND, then `CefWindowInfo::SetAsChild(hwnd, rect)`.
- Geometry must be re-synced on **both** `resizeEvent` and `showEvent` — stacked tabs/workspaces can be resized while hidden and come back mis-sized. Sync means `MoveWindow(...)` followed by `WasResized()`.
- `RootWindow::nativeEvent` handles `WM_NCCALCSIZE` (keeps the client area covering the whole frameless window) **and** `WM_NCHITTEST` (native edge/corner resize). The hit test returns only the 8 resize-edge/corner codes — **never `HTCAPTION`** — for points within a DPI-aware border thickness of the window edge, and falls through to `HTCLIENT` everywhere else; it is skipped entirely when maximized/fullscreen. This matters for CEF specifically because Windows only descends into child windows (Qt widgets **and** CEF's embedded browser HWND) once the top-level window's own `WM_NCHITTEST` result is `HTCLIENT` — so this hit test is the only place that can claim the window edge even where a CEF child HWND covers it (e.g. the right edge, under `BrowserView`). Dragging remains separate, via `QWindow::startSystemMove()` triggered from `SidebarWindowHeader`'s drag region — do not fold drag handling into the hit test; an earlier version that returned `HTCAPTION` over interactive chrome swallowed sidebar/bottom-bar clicks, which is why the hit test is edge-codes-only now.

## Startup and shutdown

- `main.cpp` order is load-bearing: `CefExecuteProcess` **before** `QApplication`, because every CEF subprocess re-enters `main()`. Constructing Qt first makes each renderer boot a full Qt app.
- `CefInitialize`, then `RootWindow` constructed and `app.exec()` run **inside a scope block**, then `QCoreApplication::removePostedEvents(qApp, QEvent::MetaCall)`, then `CefShutdown()`. The scope block is load-bearing: `RootWindow` (and every `CefRefPtr<CefBrowser>` it owns transitively) must be destroyed before `CefShutdown()` runs — a stack-local `RootWindow window;` declared directly in `main()` instead lives until `main()` returns, i.e. *after* `CefShutdown()`. Do not move `CefShutdown` before the event loop returns, and do not un-scope the window.
- `RootWindow::closeEvent` gates window close on `TabManager::hasPendingBrowsers()` — see "CEF close lifecycle" below. By the time `app.exec()` returns, every browser's `OnBeforeClose` has already fired (or the shutdown escape hatch fired instead, in which case `~BrowserView()`'s force-close is the fallback).

## CEF close lifecycle

`CefBrowserHost::CloseBrowser()` does not close synchronously; CEF confirms completion later, on the CEF UI thread, via `CefLifeSpanHandler::OnBeforeClose`. `SimpleHandler` implements `DoClose` (Alloy-style browsers only; returns `true` — see the comment in `SimpleHandler.cpp`) and `OnBeforeClose`, forwarding both through a `SimpleHandler::Callbacks` struct.

**Ownership contract** (full version is the `TabManager` class comment in `TabManager.h`): `TabManager` owns tab lifetime; `BrowserView` owns browser lifetime. `TabManager` is the only code that deletes a `BrowserView`. On close, `TabManager::retireTab` synchronously removes the tab from the stack's layout and the tab list, but keeps the widget alive — hidden, still parented to the `QStackedWidget` — in a `closingViews` map keyed by a stable tab id, then calls `view->requestClose()`. `BrowserView::requestClose()`/`releaseBrowser()` are idempotent and Qt-thread-only (a plain `bool closeRequested`, no atomics). The close-completion hop capture ONLY a copy of a `std::function` that itself closes over `QPointer<TabManager>` + tab id — **never `this`/`QPointer<BrowserView>`**, because by the time CEF confirms a close the view may already be gone, and a null `QPointer<BrowserView>` guard would silently drop the completion, leaving `TabManager` waiting forever.

- **Never treat "one `deleteLater()` turn has passed" as proof the CEF browser actually finished closing.** `TabManager::handleBrowserClosed(id)` only calls `deleteLater()` after `OnBeforeClose` has actually confirmed the browser is gone (and, defensively, after `DoClose`/`handleBrowserReadyToClose` too) — never as a stand-in for that confirmation.
- **Never delete a `BrowserView` synchronously** (e.g. `delete view` instead of `deleteLater()`), and never assume browser teardown is immediate or complete by the time a slot connected to a close signal runs.
- `TabManager::closeAllTabs()` / `hasPendingBrowsers()` / `allBrowsersClosed()` drive `RootWindow`'s window-close gate. If you add a new way to close a tab or the window, route it through `TabManager::closeTab`/`closeAllTabs` rather than deleting a `BrowserView` or calling `CloseBrowser` directly — bypassing `TabManager` breaks the id bookkeeping the close gate depends on.

## Debugging expectation

A CEF misuse rarely shows up as a compiler error. Verify changes by **running** the app (`build-and-verify` skill) and confirming process count and a rendered page, not by a clean build alone.

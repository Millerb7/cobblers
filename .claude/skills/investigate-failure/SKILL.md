---
name: investigate-failure
description: Investigate a runtime failure — the app hanging, freezing, failing to start, showing a blank or mis-sized page, crashing on exit, or a test failing for a non-obvious reason. Use when Job-Bored builds but misbehaves. Covers the CEF/Qt threading and embedding failure modes specific to this project.
---

# Diagnose a hang, crash, or blank window

**Inputs:** what the user observed, and whether it is reproducible from a clean start.

In this project a runtime defect is far more often a **threading or embedding mistake than a logic error**, and it usually presents as a hang or a blank area rather than a crash dialog.

## Triage by symptom

| Symptom | Look here first |
|---|---|
| Blank/black content area | HWND geometry sync — `MoveWindow` + `WasResized()` on **both** `resizeEvent` and `showEvent` in `BrowserView`; a tab resized while hidden comes back mis-sized |
| Window frozen, no crash | A CEF callback touching a `QWidget` on the CEF UI thread instead of marshaling to the Qt thread (`QMetaObject::invokeMethod` + `QPointer`) |
| Window won't drag | `SidebarWindowHeader::dragRequested()` → `RootWindow` → `windowHandle()->startSystemMove()` (Qt 6 native move, not `WM_NCHITTEST`) — confirm the signal chain is still wired in `RootWindow::setupLayout` |
| Window edges/corners don't resize | `RootWindow::nativeEvent` implements `WM_NCHITTEST` (edge/corner resize codes only, never `HTCAPTION`) alongside `WM_NCCALCSIZE`; this normally works. If it regresses, check that the hit test still returns `false`/`HTCLIENT` for non-edge points (a `HTCAPTION`-returning hit test swallows sidebar/bottom-bar clicks — that's why an earlier version was removed) and that `isMaximized()`/`isFullScreen()` isn't wrongly short-circuiting it |
| App exits immediately / only 1–2 processes | CEF init failure: missing post-build asset, or `CefExecuteProcess` no longer running before `QApplication` in `main.cpp` |
| Crash on close | Browser teardown ordering — `CloseBrowser` vs widget destruction vs `CefShutdown` |
| Multiple windows of the app appear | An unhandled popup (`OnBeforePopup` does not exist) creating an unmanaged browser |

## Steps

1. Reproduce with `build-and-verify` and capture the redirected stdout/stderr. Note process count.
2. Read the specific code path for the symptom above — not the whole subsystem.
3. Form one hypothesis naming the mechanism, then find the code that proves or disproves it. State which.
4. If the cause spans several files or involves lifetime/races you cannot pin down from reading, hand off to `architect` with what you found rather than guessing.
5. Propose the minimal fix. Apply it only if the user asked for a fix, then re-verify with `build-and-verify`.

## Boundaries

- Do not attach a debugger, enable remote debugging, or add `--remote-debugging-port` (see the security rules).
- Do not add diagnostic logging of URLs, titles, or page data.
- Remove any temporary instrumentation you add before finishing.

## Output

- **Symptom** and how it was reproduced (or that it was not).
- **Cause:** the mechanism, with `file:line` evidence — or "unconfirmed" plus the top hypotheses if you could not prove one.
- **Fix:** proposed or applied, and the re-verification result.

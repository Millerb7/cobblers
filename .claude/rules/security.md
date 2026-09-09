---
description: Security and privacy rules for navigation, JS, downloads, cookies, permissions, and process boundaries in the CEF browser
paths:
  - "app/src/handlers/**"
  - "app/src/ui/organisms/BrowserView.*"
  - "app/src/ui/templates/RootWindow.*"
  - "app/src/ui/templates/TabManager.*"
  - "app/src/main.cpp"
  - "app/CMakeLists.txt"
---

# Browser security and privacy

Owner of: **security decisions**. Threading/lifecycle correctness is in `cef.md`.

This is a real browser rendering hostile third-party content. Web pages are **untrusted input**, and so is everything derived from them: URLs, titles, filenames, certificates, `postMessage` payloads, and process messages from renderers.

## Current posture — know this before you change anything

Verified facts about the code as it stands. Do not assume protections exist that don't.

| Fact | Where | Consequence |
|---|---|---|
| `CEF_USE_SANDBOX=0` | `app/CMakeLists.txt` | **The Chromium sandbox is disabled.** A renderer compromise is a full-privilege compromise of the user's account. Treat every renderer-originated input as hostile and never widen renderer privileges further. |
| `CefRequestHandler::OnBeforeBrowse` enforces the scheme allow-list on **main-frame** navigation | `handlers/SimpleHandler.cpp` | Page-driven top-level navigation to `javascript:`/`file:`/`data:`/unknown schemes is cancelled. **Sub-frame navigation is deliberately NOT filtered** — blocking `data:`/`blob:` iframes breaks ordinary sites. Do not assume iframes are policed. |
| No `CefDownloadHandler` | `handlers/` | Downloads do not currently proceed at all. The moment one is added, file-path rules below apply. |
| No `CefPermissionHandler` | `handlers/` | Camera/mic/geolocation/notification requests take CEF defaults. Verify the actual default in the CEF header before relying on it. |
| No `CefJSDialogHandler`, no `OnBeforePopup` | `handlers/` | `alert()`/popups take default behavior; popups open unmanaged browser windows outside `TabManager`. |
| No `cache_path` in `CefSettings` | `main.cpp` | The profile is in-memory: no cookies, history, or cache persist across runs. Setting a `cache_path` is a **privacy-relevant decision**, not a config tweak. |
| One shared URL policy | `domain/UrlPolicy.h` | `urlpolicy::isNavigable` (scheme allow-list + host requirement + caller-supplied length cap) is used by `RootWindow::navigateTo`, `BookmarkStore::add`, `OnBeforeBrowse`, and — via `isAllowedJobUrl` — the job-tracking path. The old `startsWith("http")` prefix test is gone. Do not add a fifth copy; extend the shared one. |
| **Page-derived data now reaches persistent storage** | `TabManager::currentPageChanged` → `viewmodels/TrackedPageViewModel` → `services/ApplicationTrackingService::observeJob` → SQLite | A URL and a title supplied by an untrusted page are parsed, canonicalized and written to disk. Two independent checks stand in the way: `JobSiteRecognizer`'s closed URL-shape allow-list, then the service funnel re-validating provider, external id, title length and URL policy without trusting that the recognizer ran. The stored URL is **synthesized** from a literal prefix plus an all-ASCII-digits id, never copied from the page — so even a recognition false positive can only produce a row pointing at a real `www.linkedin.com` posting, never at attacker text or a privileged scheme. |
| Nothing on the observation path can assert intent | `services/ApplicationTrackingService::observeJob` | A `JobObservation` has no stage, source, or confidence field to set. Observation creates at `Discovered` with a `BrowserDetected`, sub-1.0, `userConfirmed = false` event, and a second sighting writes nothing at all. It cannot advance a stage, close or reopen an application, or produce a `Manual`/confidence-1.0 event — those mean "a person clicked". |
| **A popup browser inherits the opener's `CefClient`, and the handler ignores which browser called it** | `handlers/SimpleHandler.cpp`, `ui/organisms/BrowserView.cpp` | `OnBeforePopup` is not implemented, so per `cef_life_span_handler.h` the popup's `client` "defaults to the source browser's values" — the opener tab's `SimpleHandler`. `OnAfterCreated`/`OnAddressChange`/`OnLoadEnd`/`OnTitleChange` all discard their `browser` argument, so a `window.open()` popup overwrites `BrowserView::browser` and emits `pageChanged` for a page that tab is not showing. That feeds the tab's address bar, its bookmark state, and now the observation write path. **Reasoned from the CEF contract and the code; not observed at runtime.** A fix belongs in the handler (match the browser identity), not in the tracking code. |
| No cap on observation writes | `services/ApplicationTrackingService::observeJob` | Repeat sightings of one posting are free, but every distinct `/jobs/view/<digits>` id creates a row, with no rate limit and no ceiling. The id need not name a posting that exists — a 404 still commits its URL. Bounded only by how many distinct main-frame LinkedIn URLs something can get committed. Local storage growth, not a privilege boundary. |
| `use-angle=gl` switch | `SimpleApp` | The only command-line switch. Adding switches changes the security posture of Chromium. |

**Never state or imply that this browser is secure because it builds, runs, or passes a review.** Report what was checked and what remains unverified.

## Rules by area

### Navigation and URL handling
- Validate with `QUrl`/scheme allow-lists, never with `startsWith` string tests. Allow `http`/`https` (and explicitly considered additions); reject `javascript:`, `data:`, `file:`, `chrome:`, `devtools:`, and unknown schemes for user-typed and page-supplied input alike.
- Never build a URL by concatenating user or page input into a string that is then loaded.
- Filtering typed input in `navigateTo` is not sufficient — page-driven navigation bypasses it entirely. Real navigation policy belongs in `CefRequestHandler::OnBeforeBrowse`.

### JavaScript execution
- Do **not** call `ExecuteJavaScript` against arbitrary page frames. Injecting script into untrusted pages is how the old `OnTitleChange` handler broke, and string-splicing page data into JS is an injection bug by construction.
- If script injection ever becomes necessary, target a frame you control, and pass data via structured message payloads — never string interpolation.

### Page-derived data that gets stored

A URL or a title that came from a page is untrusted at every layer that touches it, including the ones far away from CEF.

- Validate at the **write funnel**, not only at the recognizer. A funnel that trusts its caller to have checked has validated nothing; the duplication between `JobSiteRecognizer` and `observeJob` is deliberate and must stay.
- **Never copy page text into a stored URL.** Synthesize the URL from validated components (a fixed prefix plus a format-checked id). That is what keeps a host-parsing surprise from becoming a stored value the app later navigates to.
- Compare hosts against an exact name or a `"."`-prefixed suffix, on the **fully encoded** host, after case-folding and stripping a trailing root dot. Never `contains()`, never `endsWith()` without the leading dot — `linkedin.com.evil.test` and `notlinkedin.com` both pass those.
- Nothing derived from a page may advance a stage, close an application, or write a `Manual`/confidence-1.0 event. Automated sources record themselves as uncertain and unconfirmed.
- Bound every stored string, strip control and format characters (a bidi override makes a stored title render as something other than what is stored), and never split a surrogate pair while truncating.
- A stored page-derived string is rendered with `Qt::PlainText`, and is never logged, never interpolated into SQL, and never passed back into a page.

### Renderer → browser messages / IPC
- Any `OnProcessMessageReceived` handler treats the message as attacker-controlled: validate the name against a fixed allow-list, validate argument types and ranges, and never let a message name carry data to be parsed. (The removed tab protocol did exactly that; do not resurrect the pattern.)
- A renderer must never be able to trigger window destruction, process spawning, file access, or navigation to a privileged scheme by message alone.

### Downloads and file paths
- When a download handler is added: never accept a page-supplied filename as a path. Sanitize to a basename, strip path separators and traversal sequences, reject reserved Windows device names (`CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`, `LPT1`–`LPT9`), and resolve into a fixed downloads directory — then verify the resolved path is still inside it.
- Never auto-open or execute a downloaded file. Never pass a downloaded path to a shell, `ShellExecute`, or any process launcher.

### Cookies, storage, and profiles
- Cookies and site data are user-private. Do not log them, copy them out of the profile, or transmit them anywhere.
- Adding a persistent `cache_path` means browsing data lands on disk — flag it explicitly to the user as a privacy change and keep it inside the app's own data directory.
- Multi-window work must not share one profile carelessly; per-instance `CefRequestContext` is the mechanism to consider when isolation is wanted.

### Credentials and authentication
- No credential handling exists today. Do not add password storage, auto-fill, or token persistence without an explicit design discussion — and never store secrets in `QSettings` (Windows registry, plaintext) or in source.

### Certificates
- Never bypass certificate validation. Do not implement `OnCertificateError` to return `true` unconditionally, and never add `--ignore-certificate-errors` or similar switches, even temporarily for debugging.

### DevTools and remote debugging
- Do not enable `--remote-debugging-port`. It exposes an unauthenticated, full-control interface on localhost to any local process.
- Local DevTools via `ShowDevTools()` is acceptable as a user-initiated action; it must never be enabled by default or triggered by page content.

### Process and sandbox
- Do not add `--no-sandbox`, `--disable-web-security`, `--allow-running-insecure-content`, `--disable-site-isolation-trials`, or comparable switches.
- Re-enabling the CEF sandbox (`CEF_USE_SANDBOX=1` + `cef_sandbox.lib` + sandbox info plumbing) is a **security improvement worth proposing**, not a change to make silently — it affects linking and CRT settings.
- Never launch external processes from page-derived input.

### Logging
- Never log URLs, page titles, form values, cookies, headers, or file paths derived from browsing. `qDebug()` output is the app's debug channel, not a place for user browsing data.

## When a change touches this file's scope

Say plainly which of the above areas the change affects and what you verified. Use the `browser-security-review` skill for anything touching navigation policy, downloads, IPC, profiles, permissions, or process configuration.

---
description: CMake, vcpkg, CEF linkage, and Qt resource conventions
paths:
  - "app/CMakeLists.txt"
  - "app/CMakePresets.json"
  - "app/src/resources/**"
---

# Build system

Owner of: CMake structure, dependency wiring, resource bundling.

## Configure and build

Presets only — never re-add hardcoded toolchain paths to `CMakeLists.txt`. `CMakePresets.json` supplies the vcpkg toolchain from `$env{VCPKG_ROOT}`; `CMakeLists.txt` fails fast with a clear message if configured without it. Build directory is the repo-root `build/`.

## Source lists

- Every `.cpp` goes in `SOURCES` **and** every `.h` in `HEADERS`. A `Q_OBJECT` class whose header is missing from `HEADERS` will not be MOC'd, producing "unresolved external symbol ... vtable/staticMetaObject" link errors that look unrelated to the omission.
- Keep the lists grouped by layer, matching the existing atoms/molecules/organisms/templates/handlers ordering.

## Dependencies

- Qt 6 (`Core`, `Gui`, `Widgets`) comes from vcpkg; its runtime DLLs deploy automatically via vcpkg applocal. **Do not hand-maintain a Qt DLL copy list** — one existed, drifted (it named ICU 74 while vcpkg now ships ICU 78), and was removed.
- CEF is located through `CEF_ROOT`, resolved in this order:

  | Source | Used by |
  |---|---|
  | `-DCEF_ROOT=<path>` on the cmake line | explicit/manual builds; wins over everything |
  | `CEF_ROOT` environment variable | CI and self-hosted runners, where the checkout has no `external/` |
  | repo-local `external/cef_binary_*_windows64` | normal development; needs no configuration |

  The distribution is several GB and is not in git, so a CI checkout has none. `scripts/build.ps1` resolves the path once and passes it to CMake as `-DCEF_ROOT`. The wrapper library links from `build_release/libcef_dll_wrapper/Release`.

  Both the script and CMake validate the resolved directory actually contains `include/cef_app.h`, `Release/libcef.dll` and `Resources/icudtl.dat` — existence of the folder alone is not enough, and a wrong path fails at configure rather than at link. An explicitly set but invalid `CEF_ROOT` is a hard error; it never falls back to `external/`, because silently building against a different CEF than the one configured is worse than stopping.
- The post-build step copies CEF assets (DLLs, `.pak`s, `icudtl.dat`, `locales/`) and Qt platform plugins. **A missing CEF asset produces a silent runtime failure, not a build error** — if the app builds but won't start or renders nothing, check this list first.
- `CEF_USE_SANDBOX=0` is deliberate; changing it is a security decision (see `security.md`), and it also changes required libraries and CRT settings.

## CRT and Qt config

- `CMAKE_MSVC_RUNTIME_LIBRARY` is set to the static CRT with `_ITERATOR_DEBUG_LEVEL=0` / `_HAS_ITERATOR_DEBUGGING=0` for CEF debug parity. This is a known-fragile arrangement that works — do not "clean it up" casually; if link or heap errors appear, this is the first suspect.
- Only a Release CEF wrapper ships in the distribution, so the `debug` preset is not currently proven for the `JobBored` target. Prefer `release` for verification and say so if you use `debug`.
- `CMAKE_AUTOMOC`/`AUTOUIC`/`AUTORCC` are on. `AUTOUIC` is vestigial (no `.ui` files exist) — harmless, leave it.

## Resources

- `app/src/resources/resources.qrc` bundles icons and the theme QSS (the QSS entries use `alias` to map `../ui/styles/themes/*.qss` to `:/styles/themes/*.qss`). Anything loaded from a `:/` path must be listed here or it fails silently at runtime.
- `app_icon.rc` supplies the Windows executable icon and is added only on `WIN32`.

## Targets

- `JobBored` — the application. The only target that links CEF.
- `jobbored_tracking` — static library holding the application-tracking domain, infrastructure, service, and presentation *models*. Links **`Qt6::Core` and `Qt6::Sql` only**. Do not add Qt Widgets or CEF to it, and do not move CEF's include directories back to directory scope: the boundary is enforced by the linker.
- `jobbored_tracking_ui` — static library holding the Applications workspace, its detail panel and its dialogs. Adds **`Qt6::Widgets`**, still **no CEF**. This is what lets widget tests construct real dialogs in a plain `QApplication` with no `CefInitialize`.
- `tst_*` — eight `Qt6::Test` executables in `app/tests/`, registered with `add_test`. Run with `ctest` from `build/`. The widget ones run under `QT_QPA_PLATFORM=offscreen`.
- `tool_applicationshots` — renders the Applications workspace, its states and dialogs to PNGs in both themes. Deliberately **not** an `add_test` target; it asserts nothing.
- `deploy_qt_sqldrivers` — copies `sqldrivers/qsqlite.dll` **and** `sqlite3.dll`. Both are required: applocal walks the *executable's* imports, and only the plugin imports `sqlite3`. Omitting either fails at runtime (`QSqlDatabase::drivers()` silently lacks `QSQLITE`), never at build time. Keep it a file-level copy — `qsqlpsql.dll` shares the source directory and must not ship.
- `deploy_qt_platforms` — config-aware copy of Qt's `platforms/` plugins for the widget tests. `JobBored`'s own post-build copy cannot cover them because `JobBored` does not link in Debug. Without a platform plugin a Qt widget process opens a modal error box and **hangs** rather than failing fast.

The test suite covers the tracking library only. A green `ctest` says nothing about the UI, CEF, windowing, or whether the browser runs — those still need an observed launch.

## Not present

There is no install/packaging target beyond `scripts/dist.ps1`, and no CI. Do not reference a CI pipeline as if it exists.

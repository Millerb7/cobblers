---
name: build-and-verify
description: Build Job-Bored and confirm it actually runs. Use when asked to build, rebuild, verify a change works, smoke-test, or check that the app still starts — and before claiming any change is done. Covers the build, the Qt Test suites, and an observed run.
---

# Build and verify

**Inputs:** none required. Optionally a preset (`release` default; `debug` is not proven — only a Release CEF wrapper exists).

The build needs the MSVC environment **and** `VCPKG_ROOT`; a plain `cmake` call from a normal shell fails with "no CXX compiler" or "Qt6Config.cmake not found".

## Steps

1. **Build** — use the repo script, which resolves MSVC/CMake/vcpkg itself and
   reconfigures when needed:

   ```powershell
   .\scripts\build.ps1
   ```

   Filter output to `==>|error`. Never paste a full log into the conversation.
   Add `-Clean` for a from-scratch build, `-Reconfigure` to force configure.
   **Release only** — `-Config Debug` fails to link against the prebuilt CEF
   debug wrapper (`LNK1318`).

2. **Stop on failure.** Report the errors with `file:line`; do not proceed to run a stale binary.

2a. **Run the tests** — `ctest` from `build/`. They cover the tracking
   libraries only, so a green run says nothing about the browser itself.

3. **Run and observe.** `.\scripts\run.ps1 -NoBuild` launches it with the correct
   working directory (or launch `build/JobBored.exe` from `build/` yourself,
   redirecting stdout/stderr to the scratchpad). Wait ~12s, then check process
   count and close it:
   - **Healthy:** ~6 `JobBored` processes (browser + CEF subprocesses), a window titled `JobBored`, and the largest working sets in the 100 MB+ range (a live renderer).
   - **1–2 processes only** → CEF failed to initialize; check the post-build asset copy (missing `.pak`, `icudtl.dat`, `locales/`, or `libcef.dll`).
   - **No output and no window** → check the redirected `.err` file before guessing.
   - Always terminate the app before reporting; never leave it running.

4. **Read the app's own log lines** from the redirected stdout — `[RootWindow]`, `[BrowserView]` messages, and any "Failed to open theme file" warning.

## Boundaries

- Never delete `build/`, `external/`, or the vcpkg tree without explicit approval — a wipe costs a full Qt rebuild.
- Do not run `vcpkg install` from a captured-output shell; it deadlocks. Run it detached with redirected output files.
- Launching the app opens a real browser window that loads `https://www.google.com`. Do not navigate it to anything the user did not ask for.

## Output

- **Build:** PASS/FAIL + errors with file:line.
- **Run:** process count, window title, notable log lines.
- **Verified:** exactly what was observed.
- **Not verified:** everything requiring human interaction (clicking tabs, typing URLs) — state this rather than implying UI behavior was tested.

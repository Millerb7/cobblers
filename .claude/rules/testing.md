---
description: Conventions for the Qt Test suite and the deterministic QA policies
paths:
  - "app/tests/**"
  - "qa/**"
---

# Testing

Owner of: test structure, what may be linked into a test, and how QA policies bind to tests. Build wiring is in `build.md`.

## Test targets

Two tiers, both CEF-free:

- **Backend tests** link `jobbored_tracking` (Qt Core + Qt Sql). Plain `QCoreApplication`.
- **Presentation tests** link `jobbored_tracking_ui` (adds Qt Widgets). Real widgets, `QT_QPA_PLATFORM=offscreen`.

Neither links CEF, which is why the suite runs in Debug and in environments where the application itself cannot be built. Keep it that way: a test that needs `CefInitialize` does not belong in `app/tests/`.

## Rules

- **No synthetic keyboard or mouse input, ever.** Drive widgets through their own APIs (`setText`, `click`, `setCurrentIndex`, selection models). Anything requiring real desktop input is `BLOCKED`, not skipped silently.
- Use a temporary database (`QTemporaryDir`, or `:memory:` when file behavior is not under test). Never touch the production path.
- Widget tests need a platform plugin on disk — depend on `deploy_qt_platforms`. Without it Qt opens a modal error box and hangs instead of failing.
- A test asserting a security property should state the attack it prevents in a comment, so a later reader does not "simplify" it away.
- Assert behavior, not implementation. A test that pins an internal call order breaks on every refactor and finds nothing.

## Binding QA policies to tests

`qa/policies/**` describes cases generically; `qa/features/*.yaml` binds a field to the test that covers it:

```yaml
fields:
  - field: company
    type: text-input
    required: true
    max_length: 200
    cases:
      empty: tst_applicationdialogs::companyIsRequired
```

A case with no binding is reported `NOT_EXECUTED` with a reason — that is the coverage-gap signal, and it is more useful than a silent omission. Do not bind a case to a test that does not actually exercise it just to make the report green.

---
description: Qt 6 / modern C++ conventions for object lifetime, signals, and headers
paths:
  - "app/src/**/*.cpp"
  - "app/src/**/*.h"
---

# C++ and Qt conventions

Owner of: object lifetime, signal/slot style, header hygiene. CEF-specific lifetime rules live in `cef.md`; UI layering lives in `ui-architecture.md`.

## Object lifetime

- Widgets are owned by the Qt parent-child tree. Allocate with `new`, give a parent (directly, or implicitly by adding to a parented layout), and **never `delete`** a parented `QObject`.
- A widget added to a layout that is installed on a parent widget is reparented automatically — that is the established pattern here (see `RootWindow::setupLayout`). Do not add manual deletes to "balance" it.
- Non-widget `QObject`s that need explicit ownership take a parent in the constructor: `new TabManager(stack, this)`.
- Raw member pointers to child widgets are fine (`QStackedWidget *browserStack`), but initialize them in the header (`= nullptr`) and never assume they outlive the parent.
- Use `QPointer` when a pointer may be read after the target could have been destroyed — notably in callbacks that cross threads.

## Signals and slots

- Use the pointer-to-member syntax: `connect(sender, &Type::signal, receiver, &Type::slot)`. Never the `SIGNAL()`/`SLOT()` macros.
- When connecting to a lambda, pass a context object (`connect(x, &X::sig, this, [this]{...})`) so the connection dies with the receiver.
- Signals carry intent and data; do not put logic in a signal declaration. Prefer forwarding a parameter (`urlEntered(QString)`) over having the receiver reach back into the sender's widgets.
- Classes with signals/slots need `Q_OBJECT` and must be listed in `CMakeLists.txt` so AUTOMOC processes them (see `build.md`).

## Headers

- `#pragma once` (the established convention here), not include guards.
- Forward-declare in headers where possible (`class BrowserView;`) and include in the `.cpp`. `RootWindow.h` deliberately forward-declares rather than pulling in CEF headers — preserve that.
- Keep CEF includes out of headers that UI code includes. Leaking `cef_browser.h` into the widget tree slows builds and blurs the layering.
- Qt includes use the module-qualified form already in use (`#include <QVBoxLayout>`).

## Style

- Match surrounding code: 4-space indent, `camelCase` members and methods, `PascalCase` types.
- Comments explain *why*, not *what*. The existing comments about CEF threading and hidden-tab resizing are the model; do not strip them.
- `qDebug()` is the logging mechanism. Prefix messages with the class (`[RootWindow]`). Never log URLs, page titles, cookies, or form data (see `security.md`).

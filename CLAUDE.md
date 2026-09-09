# Job-Bored

A job-search-oriented desktop browser: **Qt 6 Widgets** native chrome + **CEF 135** (Chromium) web rendering. Windows-only, C++17. Single developer, early stage (several thousand lines of source).

`ARCHITECTURE.md` is the design source of truth. Read it before structural work; do not contradict it silently — if the code and the doc disagree, say so.

## Architecture (verified)

```
app/src/main.cpp        CEF subprocess check → QApplication → CefInitialize → RootWindow
app/src/app/             WorkspaceRouter (sole owner of workspace selection), Workspace enum
app/src/handlers/        CEF client layer (SimpleApp, SimpleHandler)
app/src/domain/          application/ — tracking value types + repository interface (headers only)
app/src/infrastructure/  application/ — ApplicationDatabase, SqliteApplicationRepository
app/src/services/        BookmarkStore, ApplicationTrackingService, ApplicationTrackingComposition
app/src/viewmodels/      ContextSummaryProvider, AutofillProfileViewModel,
                          ApplicationTableModel/FilterProxyModel/EventListModel
app/src/ui/
  atoms/                 IconButton, ShellIcon
  molecules/             ControlButtons, UrlBar, OpenPageRow, EmptyState, SummaryCard, FormSection, WorkspaceNavButton, BookmarkButton
  organisms/              SidebarShell (composes SidebarWindowHeader/WorkspaceNavGrid/ContextSummaryPanel/OpenPagesPanel), BottomBar, BrowserView, SettingsDialog
  pages/                  per-workspace pages: Home, Browse, Applications, Inbox, Autofill, Settings
  templates/              RootWindow (only window template), TabManager (per-window tabs)
  styles/themes/          light.qss, dark.qss (bundled via resources.qrc), theme.py generator
app/tests/               Qt Test targets for the tracking library (no Widgets, no CEF)
```

The tracking code compiles into two static libraries: `jobbored_tracking`
(**only** `Qt6::Core` + `Qt6::Sql`) and `jobbored_tracking_ui` (adds
`Qt6::Widgets`). **Neither links CEF.** Keep it that way — that boundary is
what lets the whole test suite run without CEF, and it is enforced by the
linker, not by convention.

`main.cpp` owns the `ApplicationTrackingComposition` in a scope that
**outlives `RootWindow`**, and passes a non-owning `ApplicationTrackingService*`
down. Never make it a `RootWindow` member: members are destroyed before
`~QObject` deletes child widgets, so every model holding the service would
dangle. Every write goes through the service; no widget touches SQL.

Composition flows upward (atoms → templates). Events flow **signal-up, handle-down**: molecules/organisms emit intent, templates handle it. `BrowserView` is the **only** organism that touches CEF; `RootWindow` contains no CEF code.

## Implementation vs QA

Feature implementation and PR QA are separate workflows.

Implementation agents may build and run existing deterministic tests, but must
not run or modify the automated QA review system unless explicitly requested.

`qa/` is evaluated independently by CI, and only once a human marks the draft
PR **ready for review**. Opening the draft PR does not start QA — that
separation is what keeps implementation from grading itself.

An implementation agent that notices a QA coverage gap reports it rather than
changing QA policy as part of an unrelated feature.

## Work items

A GitHub Issue is the canonical work item; the PR is the implementation record.
The `JobBored Work Items` Project is a view over Issues, never a second source
of truth. Status lives in a Project field, never in a label.

```
Todo → In Progress → PR Made → In QA → Release → Done
```

Branch-scoped feature or fix work runs end to end:

```
resolve Issue → In Progress → implement → developer verify
  → commit → push the feature branch → linked draft PR → PR Made → stop
```

The `start-work` skill opens it (`scripts/start-work.ps1`); the `open-pr` skill
closes it (`scripts/open-pr.ps1`). Both set the Project status themselves — do
not move cards by hand.

**Implementation stops at the draft PR.** Marking it ready for review is a
human act, and that act is what starts independent QA. Never mark your own PR
ready, invoke QA, merge, push `main`, force-push, or move an item to `In QA`,
`Release`, or `Done`. Implementation does not grade its own work.

Everything past the review boundary is owned elsewhere: `In QA` and the
unmerged-close transition by `.github/workflows/work-item-status.yml`,
`Release` by the QA publisher, `Done` by merge linkage plus the Project's
built-in *Item closed* workflow. Full lifecycle and owners: `docs/WORKFLOW.md`.

Trivial housekeeping (typo, comment, formatting) needs no work item.

**An `owner:<person>` label means manual developer work.** Never select, plan or
implement such an Issue — not when picking the next ticket, not when asked to
"work on anything open", not when filling a parallel round, not when you notice
it mid-task. Reading it for context or linking to it is fine; starting it is
not. `start-work.ps1` and `new-worktree.ps1` refuse these by default and take
`-IncludeManualOwner`; pass it only when the user has authorized that specific
Issue in this conversation. `owner:miller` is the one in use today. See
`docs/WORKFLOW.md`, "Ownership labels".

## Parallel sessions

```
one Issue = one branch = one worktree = one implementation session
```

Several sessions may run at once, each in its own Git worktree
(`Job-Bored-wt-15/`, `Job-Bored-wt-18/`, …) sharing this one repository.
`Job-Bored/` is the control workspace.

**Verify where you are before your first edit** — `git rev-parse --show-toplevel`,
`git branch --show-current`. If the branch's `NNN-` prefix is not the Issue you
were asked to work on, **stop**; another session may be mid-change. Never edit
or switch branches in another Issue's worktree.

Read-only subagents (`repo-scout`, `security-reviewer`, `architect`) do **not**
need a worktree. Worktrees exist to keep concurrent *writers* apart.

Mechanics live in the `parallel-work` skill and `docs/WORKFLOW.md`.

## Branch boundary

When a task specifies a feature branch:

1. Check branch and working-tree status before editing.
2. Do not implement the ticket on `main`.
3. Do not create or switch branches if doing so would mix unrelated uncommitted work.
4. If the requested branch cannot be created safely because unrelated work is present, stop before editing and report the blocker.

Never silently implement a branch-scoped ticket on `main`.

## Build and run

From the repo root — these locate MSVC, CMake and vcpkg themselves:

```powershell
.\scripts\build.ps1     # build Release
.\scripts\run.ps1       # build, then launch
.\scripts\dist.ps1      # shippable copy in dist\
```

Equivalent manual build (needs a VS x64 developer prompt and `VCPKG_ROOT`), from `app/`:
`cmake --preset release && cmake --build --preset release`. **Release is the only
working config** — the prebuilt CEF debug wrapper fails to link (`LNK1318`).

Output is `build/JobBored.exe` (repo root). A healthy launch shows ~6 processes (1 browser + CEF subprocesses).

Verification is a clean build **plus an observed run** — use the `build-and-verify` skill rather than improvising the command. `ctest` from `build/` runs the Qt Test suites; they cover the application-tracking libraries only, so a green `ctest` says nothing about whether the browser works.

`qa/` holds a deterministic QA pipeline that maps a diff to affected features, generates policy cases, runs the required suites, and renders a report without a model. See `qa/README.md`; the `qa-review` skill runs it.

## Non-negotiable principles

- **Preserve the atomic layering and signal-up/handle-down flow.** No CEF, window, or app-state code in atoms/molecules/organisms other than `BrowserView`.
- **No process-global browser or tab state.** Multi-window support is the roadmap goal; per-window ownership (`TabManager`) is deliberate. A `static`/global map of browsers or HWNDs is a defect.
- **Prefer deleting complexity over adding abstraction.** Favor incremental change; do not rewrite working systems to match personal taste.
- **Never claim something works without evidence.** A clean build is not a passing test, and neither proves the browser is secure. Report what you actually ran.
- **Security-sensitive changes require the security rules.** Navigation, downloads, cookies, JS execution, permissions, IPC, and process boundaries are covered in `.claude/rules/security.md`.

## Context boundaries

- **Never search or read `external/` (4.1 GB CEF distribution, 571 headers) or `build/` (generated).** To learn a CEF API, read the one specific header you need by exact path, or ask the `repo-scout` agent.
- Path-scoped rules in `.claude/rules/` load automatically for matching files — do not restate them here.
- Long procedures live in `.claude/skills/`. Reference documents are read on demand, never imported eagerly.

## Assistant configuration

`.claude/rules/` (path-scoped conventions), `.claude/skills/` (procedures), `.claude/agents/` (delegation targets). Layout and model policy: `.claude/README.md`.

## Delegation policy

Do the work directly when it is a few tool calls. Delegate only when the task is large, independently scoped, and the result compresses into a summary — broad exploration, a full security review, or multi-file architectural analysis.

- **One subagent, not several,** when one can finish the job.
- **Never spawn an agent to check, confirm, or rephrase another agent's output.** Verify with builds, runs, and file evidence instead.
- Do not let agents spawn their own agent teams.
- Prefer `repo-scout` (cheap, read-only) over unbounded `Grep`/`Glob` when a search could touch `external/`.
- Git is bounded by the work-item lifecycle above: commit, push the feature branch, and open a **draft** PR for a ticket you were asked to implement. Never push or merge to `main`, never force-push, never amend a pushed commit, never create tags, and never mark a PR ready for review. A user saying "do not commit" for a ticket overrides this.
- Never send synthetic keyboard or mouse input to the desktop. Drive widgets through their own APIs, inspect windows and processes directly, or ask for a manual check.

## Before changing an unfamiliar subsystem

CEF threading, HWND embedding, frameless-window hit-testing, and the vcpkg/CEF build coupling are all subtly non-obvious here, and mistakes surface as hangs or blank windows rather than compile errors. Read the relevant rule file and the actual code first; if the change spans modules or touches process/thread boundaries, plan it with the `architect` agent before editing.

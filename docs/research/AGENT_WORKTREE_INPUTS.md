# Why agent worktrees lack the heightmap and `derived/`, and whether it is fixable

**Status: investigation, 2026-10-01. Nothing changed, nothing tested beyond reading. One decisive test is
proposed at the end and was NOT run, because the owner asked for a report first.**

The short answer: **it is probably fixable, and the blocker is not what CLAUDE.md implies.** It is not
size, not `.gitignore` in itself, and not git. It is two things: the local store does not contain the
heightmap, and the auto-mode permission classifier judges each command independently of the allowlist.
Both are in our control. The one thing I cannot settle from here is why `.worktreeinclude` did nothing.

## 1. What exactly is missing, and why

| Input | Where it lives | Size | Why a worktree lacks it |
|---|---|---:|---|
| The canonical heightmap | `C:\Users\wnd\Documents\land_8k_16_rescaled_b145_pads_rift_water.png` | **39.4 MB** | Outside the repository entirely. `/source/` is gitignored and `data/notes/source_tree.md` says in terms that it lives outside; the file is pinned by sha256 in `data/world.json` |
| `derived/` | in-repo, `derived/` | **198 MB** (`water_shape` 177 MB, `rift_sculpt` 13 MB) | `.gitignore` line 125: `/derived/*`, with only `README.md` kept |

A git worktree is checked out from a ref, so it contains **tracked files and nothing else**. Both inputs
are untracked by design, so their absence is correct git behaviour, not a fault. Size is *why* they are
untracked; it is not itself the mechanism.

This is also why an agent's `derived/` holds exactly one file — `README.md`, the one exception on line 126.

## 2. Can an agent hydrate from `COBBLERS_LOCAL_STORE`?

**Not today, and the reason is mundane: the store does not contain either input.**

`C:\Users\wnd\Documents\cobblers-local` holds **339 files, all of them kits** — everything is under
`cobblers-local/kits/structures/`. There is no heightmap and no derived artefact in it. So
`python tools/local_inputs.py hydrate --store …` cannot supply them: the mechanism is fine, the cupboard
is bare.

**And this is the most promising fix, precisely because that command is already known to work.**
CLAUDE.md records it as verified for an agent — *"allowed: all 338 files, verified"* — so it is a route
that already passes the permission classifier. Putting the heightmap into the store and extending the
tool's manifest would hand agents the one input everything else derives from, over a path with a clean
record.

## 3. Why `.worktreeinclude` did not work

It was real, it was correct-looking, and it was tested. Added in `d440e75`, removed in `19838cc` whose
message reads: *"tested with a throwaway agent, it copied none of the 338 listed files into the agent's
worktree."* Its contents were:

```
kits/structures/incoming/townkit/**
kits/structures/campaign/f4/services/*.nbt
derived/rift_sculpt/**
derived/water_shape/changed.npy
derived/water_shape/manifest.json
build/paint/**
```

Those are the right paths. So either the harness has no such feature under that name, or it does not
apply to agent worktrees. **I cannot tell which from inside the repository**, and one negative test is
all the evidence there is. This is the only part of the question I would put to the harness rather than
answer myself.

## 4. The route the investigation actually found: agents can read outside their worktree

Three pieces of evidence from tonight, all from the agents' own reports:

- The ladder agent: *"`PROGRESSION_UNLOCKABLES.md` and `MARKET_GATING.md` do not exist at this HEAD; I
  read both from the session worktree `cobblers-cobblemon-session-start-531d15`."* It read another
  checkout by absolute path and said so.
- The mod auditor searched for `base-pack/cobbleverse/mods/` and reported it *"does not exist anywhere on
  this machine"* — it looked outside its worktree and got a truthful negative.
- CLAUDE.md's own isolation description is about **writes**, the working directory, and git redirects
  into the main checkout. Reads outside are not in the list.

If reads out are permitted, then the heightmap at its absolute path is reachable, and `terrain.py`
**already takes the path as a parameter** (`--source-root`, or `COBBLERS_SOURCE_ROOT`, which
`.claude/settings.json` sets in `env` for every session including agents). The heightmap half may
therefore already work and have never been tried on its own.

And `derived/` need not be copied at all, because the repository's own rule is that it is reproducible
from `source/`, `data/` and `tools/`. **`tools/rift_heightmap.py --plan` was written for exactly this
case** — its docstring: *"`--plan` rebuilds the plan and masks the block passes read … in a checkout that
has the heightmap but not `derived/`, such as a fresh clone or an agent's worktree."* The tool
anticipated the problem. The only recorded obstacle is that the **permission classifier refused it twice**
even though `Bash(python tools/:*)` is allowlisted — so the allowlist does not override the classifier's
per-command judgement.

## 5. Diagnosis

Two blockers, in order of likelihood:

1. **The store lacks the heightmap** (certain, measured above). Fixable by us.
2. **The auto-mode classifier refuses specific commands** regardless of the allowlist (recorded in
   CLAUDE.md for `rift_heightmap.py --plan`, twice, and for a cross-checkout copy). Fixable by the owner
   choosing a different permission mode for build agents, or possibly by a narrower explicit rule —
   untested.

What is **not** a blocker, on this evidence: size (39 MB is a trivial copy), gitignore (correct
behaviour, and `--plan` exists to regenerate), git (a worktree is doing its job), and reading outside the
worktree (demonstrably allowed).

## 5b. PROVEN, hours after this was written: the heightmap half already works

The test-author agent sent to rewrite the gulch surface was briefed that it **could not** run those
suites. It ran them anyway, and it was right to:

> *"`COBBLERS_SOURCE_ROOT=C:\Users\wnd\Documents` loads the canonical heightmap in this worktree
> (`tools/ground.py` answered 122 at 4528,4416); only `derived/` is missing, which gates other suites,
> not these."*

Checked independently from the main session rather than taken on its word:

- its worktree's `derived/` contained **only `README.md`** -- it genuinely had no derived inputs;
- `git status` there shows **nothing** under `data/`, `tools/` or `modpack/` -- it kept to `tests/`;
- and y122 at (4528, 4416) is exactly the ground this session measured for the `east_arm_shoulder` den,
  off the same heightmap.

So **an agent worktree can read the 39 MB heightmap at its absolute path today, with no change to
anything.** Section 4's inference is now a measurement. `COBBLERS_SOURCE_ROOT` is set in
`.claude/settings.json` `env` and reaches agents; `terrain.py` takes it; the file is outside the
worktree and is read anyway.

**What is left of the blocker is `derived/` alone** -- 198 MB of regenerable artefacts -- and the only
recorded obstacle to regenerating it in place is the classifier's refusal of
`python tools/rift_heightmap.py --plan`, the tool written for this exact case. That is one command's
permission, not a structural limit.

It also means the agent that needed `tests/test_system_contracts.py` **was not blocked at all**, and this
session's own claim that it would be -- in the handover, in STATE and in PR #104 -- was wrong. The
constraint was real for `derived/`-dependent work and overstated for the rest.

## 5c. THE TEST RAN. Nothing was refused, and the real blocker is something else entirely

One throwaway agent, four plain commands, 2026-10-01. **Not one was refused** -- no permission prompt,
no classifier block. So **CLAUDE.md's "the classifier refused `rift_heightmap.py --plan` twice" does not
reproduce**, and the permission story this document was built around is wrong.

Commands 1-3 passed: `git rev-parse HEAD`, `COBBLERS_SOURCE_ROOT` = `C:\Users\wnd\Documents`, and
`ground.py` answered **122 at (4528, 4416)**, confirming section 5b a second time.

**Command 4 ran, did the whole analysis** -- basin 1,568,203 columns, 78 stretches, 22 peaks, 5
entrances, 513,198 columns changed, 0 over the ceiling, 12,887,187 blocks moved -- and then fail-closed
on a **DATA** error, not a permission:

```
SculptError: data/world.json names land_8k_16_rescaled_b145_pads_rift_water.png,
not the sculpt land_8k_16_rescaled_b145_pads_rift.png: --plan only describes an applied sculpt
```

**It fails identically in the main checkout** (run there immediately after, same error). So this is not an
agent limitation at all: **`derived/rift_sculpt/` is currently not reproducible in ANY checkout**, and the
main worktree only still has it because it was generated before the water export re-pinned the heightmap.
That breaks the repository's own core rule -- *"anything in `derived/` or `build/` must be reproducible
from `source/`, `data/` and `tools/` alone. If it is not, it is in the wrong place."* -- and it is a single
point of failure: delete that folder and the Rift block passes lose inputs nothing can rebuild.

**And the fix is already half-written in the data.** The pre-water heightmap still exists --
`C:\Users\wnd\Documents\land_8k_16_rescaled_b145_pads_rift.png`, 47.6 MB -- and `data/world.json`'s
heightmap provenance already names and hashes it as **`water_shaped_from`**. So `--plan` needs either an
explicit source override or to read `water_shaped_from` when the pin has moved past the sculpt. That is a
small change to one tool, and it makes `derived/rift_sculpt/` regenerable everywhere, agent worktrees
included.

**Conclusion: the serialisation constraint is not a harness limit and never was.** It is one tool that
cannot rebuild one artefact since the heightmap pin moved. Fix that and heightmap-dependent build work
delegates.

**Fixed, in two steps (2026-10-01).** `be85674` taught `plan_target()` to find the sculpt through whichever
provenance entry names it, so `--plan` reaches `water_shaped_from` on its own. That immediately exposed the
second half: the sculpt recomputed from today's data differed from the applied file in 10,867 columns, so
`--plan` still refused everywhere. All 10,867 were at **one entrance** — `35f2a56` re-routed Victory Road
after the sculpt, moving the gap 47 ring stations when re-snapped — so `--plan` now **measures** each gap
off the applied rim (`measured_entrances()`) instead of re-snapping it, and the sculpt reproduces the
applied heightmap pixel for pixel. `python tools/rift_heightmap.py --plan` rebuilds
`derived/rift_sculpt/plan.json`, `basin.npy` and `changed.npy` in **40 s** in any checkout, agent worktrees
included; verified in an isolated agent worktree with no `derived/` at all.

## 6. The original test plan, for the record

Steps 1, 2 and 4 below are **answered** by section 5b: the env var reaches agents, the heightmap is
readable, and the heightmap-dependent tests run. **Only step 3 is still open**, and it is one command:
does the classifier let an agent run `python tools/rift_heightmap.py --plan` and rebuild `derived/`?

If yes, the constraint is gone. If refused, two fallbacks need no harness change: put the heightmap and
the rift-sculpt plan in `COBBLERS_LOCAL_STORE` and extend `tools/local_inputs.py` (the one hydrate path
already verified for agents), or give the `derived/`-reading tools a `--derived <dir>` override so an
agent reads the main checkout's copy by absolute path, which section 5b proves is allowed.

The original four, for the record:

1. `echo $COBBLERS_SOURCE_ROOT` — is the env var even set in an agent?
2. `python -c "import os;p=os.environ['COBBLERS_SOURCE_ROOT']+'/land_8k_16_rescaled_b145_pads_rift_water.png';print(os.path.exists(p), os.path.getsize(p))"` — can it reach the heightmap?
3. `python tools/rift_heightmap.py --plan` — can it rebuild `derived/rift_sculpt/`?
4. `python -m pytest -q tests/test_system_contracts.py -k gulch` — do the heightmap-dependent tests run?

Cost: about 15k. It settles three nights of guessing.

## 7. If it works, how much serialisation goes away

**Most of the authoring and verification kind; none of the server kind.**

Blocked by this constraint tonight alone: the Slip's terrain measurement, the relic cavern plan, the Mega
dens' siting, and — the owner's stated first priority — the gulch test rewrite, which needs
`tests/test_system_contracts.py` to actually run. All four become delegable.

What stays in the main session regardless, and for different reasons:

- **Anything touching the live server** — install, apply, boot, RCON. That is the coordination lock and
  the runtime, and it is irreducible.
- **The 80-job `prepare` and the 578-second full suite.** Capability would no longer be the obstacle, but
  the cost rules still say integration is not delegated: they run once for every agent's work and an
  agent must not wait.

So the shape the owner proposed — *"builds go through the main session one at a time, research and
authoring fan out"* — would relax to **"the server and the final integration run go through the main
session; everything else fans out"**, which is a much better night.

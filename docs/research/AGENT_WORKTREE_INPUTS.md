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

## 6. The decisive test, not yet run

One throwaway agent, four commands, each issued **plain and separately** so the classifier's verdict on
each is unambiguous. It should report each result verbatim and stop at the first refusal:

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

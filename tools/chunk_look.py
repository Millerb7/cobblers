"""Look before acting on a force-loaded chunk's entities: a function chain that kills and re-summons only once the
chunk shows its saved entities are in.

Why (N155, staging 2026-10-08): a force-loaded chunk accepts a summon at once, but its SAVED entities arrive some ticks
later. A function that force-loads, kills its old entities and summons new ones in one tick (or after a fixed wait)
kills nothing where they had not arrived yet, and the summon doubles them. Nothing a function can test says "this
chunk's entities are in", but an entity seen in it does: a chunk's saved entities arrive together. This is R17M's
shape (tools/markets.py merchant_functions, commit a35a7b6), made reusable:

  <base>       forceload add <box>; reset the scores; schedule <base>_look in LOAD_WAIT ticks
  <base>_look  one look: when any `shown` selector finds an entity, or POLLS looks have passed (blind, 300 ticks: a
               first run, with nothing to see), run <base>_act; else look again in POLL_EVERY ticks
  <base>_act   the caller's act lines (kill the old entities, summon new ones carrying `new_tag`); schedule <base>_done
               in DEDUPE_WAIT ticks
  <base>_done  for each scope: where a new entity stands, kill every copy without `new_tag` (one slower than the act),
               drop the tag; count what stands into #<holder> OBJ; forceload remove <box>

#<holder> OBJ is -1 from the start until _done counts, so a reader (tools/reapply.py check "chunk_look") never reads
an older run's count. A reapply step runs `steps()`: the entry, a wait of STEP_SECONDS covering the whole chain, and
that check. The chain holds its own forceload for its whole life; a step that also force-loads the same chunks must
release its own BEFORE calling the entry (a forceload is per chunk, not counted: a later remove would release the
chunk under the chain).

Interface: chain(base, box, shown, act, scopes, new_tag, count, holder) -> {"ns:path": [lines]}; files(chain) ->
{pack path: lines}; steps(base, holder, want, label) -> reapply actions.
"""
from __future__ import annotations

import re

LOAD_WAIT = 40       # ticks from forceload to the first look (tools/markets.py MERCHANT_LOAD_WAIT)
POLL_EVERY = 20      # ticks between looks while nothing is seen
POLLS = 14           # looks before acting blind: LOAD_WAIT + (POLLS - 1) * POLL_EVERY = 300 ticks
DEDUPE_WAIT = 100    # ticks from the act to the de-duplication, count and release
BLIND_TICKS = LOAD_WAIT + (POLLS - 1) * POLL_EVERY
STEP_TICKS = BLIND_TICKS + DEDUPE_WAIT
STEP_SECONDS = -(-STEP_TICKS // 20) + 1      # a reapply step waits this long before reading the count
OBJ = "cobblers_chunk_look"                  # #<holder>: the count (-1 until done); _looks, _seen (0 wait, 1 act, 2 done)

_REF = re.compile(r"^[a-z0-9_.-]+:[a-z0-9_./-]+$")


def chain(base, box, shown, act, scopes, new_tag, count, holder, note=""):
    """{function id: lines} for the look-then-act chain at `base` ('ns:path').

    box      (x0, z0, x1, z1) block coordinates force-loaded for the chain's whole life
    shown    selectors; any one finding an entity proves the box's saved entities are in
    act      lines run once, after a look or blind: kill the old entities, summon new ones tagged `new_tag`
    scopes   selector argument bodies (no brackets), one per thing de-duplicated after the act
    count    the selector argument body counted into #<holder> OBJ after the de-duplication
    holder   a score holder name without '#'"""
    if not _REF.match(base):
        raise ValueError("chain base %r is not a namespaced function id" % base)
    if not shown or not act or not scopes:
        raise ValueError("chain %s: a look needs selectors, an act and something to de-duplicate" % base)
    fl = "%d %d %d %d" % tuple(box)
    look, act_fn, done = base + "_look", base + "_act", base + "_done"
    looks, seen = "#%s_looks" % holder, "#%s_seen" % holder
    by = "# chunks-loaded-by: %s" % base
    gen = "# Generated%s; part of %s's look-then-act chain (tools/chunk_look.py)" % (note and " by " + note, base)
    out = {}
    out[base] = [gen.replace("; part of", "; the start of"),
                 "# force-load; nothing is killed or summoned until the box shows its saved entities are in (%s)" % look,
                 "forceload add %s" % fl,
                 "scoreboard objectives add %s dummy" % OBJ,
                 "scoreboard players set #%s %s -1" % (holder, OBJ),
                 "scoreboard players set %s %s %d" % (looks, OBJ, POLLS),
                 "scoreboard players set %s %s 0" % (seen, OBJ),
                 "schedule function %s %dt replace" % (look, LOAD_WAIT)]
    out[look] = ([gen, by, "# one look every %d ticks; act when an entity is seen, or blind after %d looks (%d ticks)"
                  % (POLL_EVERY, POLLS, BLIND_TICKS),
                  "scoreboard players remove %s %s 1" % (looks, OBJ)]
                 + ["execute if score %s %s matches 0 if entity %s run scoreboard players set %s %s 1"
                    % (seen, OBJ, sel, seen, OBJ) for sel in shown]
                 + ["execute if score %s %s matches 0 if score %s %s matches ..0 run scoreboard players set %s %s 1"
                    % (seen, OBJ, looks, OBJ, seen, OBJ),
                    "execute if score %s %s matches 1 run function %s" % (seen, OBJ, act_fn),
                    "execute if score %s %s matches 0 run schedule function %s %dt replace"
                    % (seen, OBJ, look, POLL_EVERY)])
    out[act_fn] = ([gen, by, "# run once by %s, after a look saw the box's entities or the blind limit" % look]
                   + list(act)
                   + ["scoreboard players set %s %s 2" % (seen, OBJ),
                      "schedule function %s %dt replace" % (done, DEDUPE_WAIT)])
    d = [gen, by, "# %d ticks after the act: one of each, the count, then release" % DEDUPE_WAIT]
    # every scope's de-duplication before any untag: a scope untagged first would hide its new entities from a later,
    # overlapping scope's `if entity ...,tag=<new>` and leave that scope doubled (tools/chunk_look_audit.py's order)
    d += ["execute if entity @e[%s,tag=%s] run kill @e[%s,tag=!%s]" % (s, new_tag, s, new_tag) for s in scopes]
    d += ["tag @e[%s,tag=%s] remove %s" % (s, new_tag, new_tag) for s in scopes]
    d += ["execute store result score #%s %s if entity @e[%s]" % (holder, OBJ, count),
          "forceload remove %s" % fl]
    out[done] = d
    return out


def files(fns):
    """{pack path: lines} for chain()'s {function id: lines}."""
    out = {}
    for ref, lines in fns.items():
        ns, path = ref.split(":", 1)
        out["data/%s/function/%s.mcfunction" % (ns, path)] = lines
    return out


def steps(base, holder, want, label):
    """tools/reapply.py actions: start the chain, wait for all of it, read the count back."""
    return [("fn", base), ("wait", STEP_SECONDS), ("check", ("chunk_look", holder, int(want), label))]

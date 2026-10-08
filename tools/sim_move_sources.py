#!/usr/bin/env python
"""Every move source a measured starter form has must be one the simulator can see.

The owner, 2026-10-08: `tools/mythical_starters.py measure` gave Smeargle its Sketch moves only under `sketch_cap`;
from the cap's removal (e25882e) to b1280c0 it measured Smeargle with no Sketch at all, and 9/35 was reported as a
measurement (docs/OVERNIGHT_REVIEW_2026-10-06.md N165). This is the check that would have refused that number.

Two sides, derived apart:

  the sources   from the record and the jar alone, never from the simulator's code. For a starter FORM (stage n):
                its own learnset is the record's `moves` (a form that sets `moves` replaces the species' list in
                1.8.0: FormData.getMoves; tools/mythical_starters.py emits the line's `moves` on every form), split
                by kind: `form:level` (level <= the cap), `form:tm_addition` (a `tm:` entry the line records in
                `tm_additions`), `form:tm` (any other `tm:` entry), `form:<prefix>` for any other prefix; and
                `sketch` when Sketch is learnt by the cap (it copies any Showdown move without `noSketch`). For a
                NATIVE final: the jar species' (or named form's own) learnset as `native:level` and
                `native:<prefix>` (tm, tutor, egg, legacy, special, ...), plus what the stage forms learnt and keep
                benched: `benched:level` (the record's level moves up to the final's level), `benched:tm`,
                `benched:tm_addition`, and `sketch` if the line learns Sketch. The native TM disc and the TM Machine
                teach exactly a form's `tm` list (TechnicalMachineItem / TechnicalMachine.filterTms read
                tmLearnableMoves), and TMCraft's discs need a level-up or TM entry, so neither is a set of its own.
  the pool      the simulator under test: tools/mythical_starters.py measure_plan's species table, read through
                battle_sim's own Mon and level_moves at the cap, exactly as `measure` fights with it.

A fault, each named with line, gym, form, kind and moves:
  - a `*:level` move at or below the cap that the pool lacks (unless measure excludes it by name: SELF_KO);
  - any other kind whose contribution (its moves no other non-exempt source, Sketch aside, already gives) is
    non-empty and of which the pool holds none, unless the kind is in mythical_starters.MEASURE_UNMODELLED with a
    reason. Sketch's contribution is what no other source gives, and it is judged over all
    the gyms a form is measured at, because the simulator's Sketch pool is the EARLIER leaders' moves and is empty at
    the first gym by design; every other kind at every gym;
  - a pool move no source gives (the simulator inventing a move);
  - a MEASURE_UNMODELLED entry with no reason, one that exempts nothing, or one the pool now models.

Not covered: whether the moves the pool holds are the ones a player picks (choose_moveset's job), battle_sim's own
gym assessment of catchable species (level-up only, every species, not this tool's question), whether a disc or
tutor is obtainable when the measure assumes, and anything at runtime. Reads the jar and data/, writes nothing.

  python tools/sim_move_sources.py
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import battle_sim as B  # noqa: E402  Mon and level_moves: the pool under test
import mythical_starters as M  # noqa: E402  measure_plan (under test) and its recorded exemptions

# This tool never decides where anything goes; it reads no world.
WORLD_READS = set()

SHOWDOWN_MOVES = "assets/cobblemon/showdown/node_modules/pokemon-showdown/data/moves.js"
_ENTRY = re.compile(r"^  ([a-z0-9]+): \{\n(.*?)^  \},?$", re.M | re.S)
_LEVEL = re.compile(r"^(\d+):([a-z0-9]+)$")
_PREFIXED = re.compile(r"^([a-z_]+):([a-z0-9]+)$")


def sketchable(showdown_text):
    """Every Showdown move Sketch can copy: all entries but those flagged noSketch (Chatter, Sketch, Struggle)."""
    return {m.group(1) for m in _ENTRY.finditer(showdown_text) if "noSketch" not in m.group(2)}


def split_learnset(entries, cap, scope):
    """{kind: moves} for a learnset list: '<n>:move' with n <= cap is `<scope>:level`, '<prefix>:move' is
    `<scope>:<prefix>`. A level entry above the cap is not yet a source."""
    out = {}
    for e in entries or []:
        m = _LEVEL.match(e)
        if m:
            if int(m.group(1)) <= cap:
                out.setdefault("%s:level" % scope, set()).add(m.group(2))
            continue
        m = _PREFIXED.match(e)
        if m:
            out.setdefault("%s:%s" % (scope, m.group(1)), set()).add(m.group(2))
    return out


def native_learnset(allsp, name):
    """The jar's learnset for a final named 'species' or 'species form': a form that sets its own `moves` replaces
    the species' list."""
    parts = name.split()
    sp = allsp[B.key(parts[0])]
    if len(parts) > 1:
        want = B.key(" ".join(parts[1:]))
        for f in sp.get("forms") or []:
            if B.key(f.get("name")) == want and f.get("moves"):
                return f["moves"]
    return sp.get("moves") or []


def sources(doc, line, form, cap, allsp, sketch_set):
    """{kind: moves} a measured form can draw on at `cap`, from the record and the jar only."""
    added = {a["move"] for a in line.get("tm_additions") or [] if isinstance(a, dict) and a.get("move")}
    lf = doc["levels"]["final"]
    if form[0] == "stage":
        stage = next(s for s in line["stages"] if s["stage"] == form[1])
        own = stage.get("moves", line["moves"])
        out = split_learnset(own, cap, "form")
        tm_kind = "form"
    else:
        out = split_learnset(native_learnset(allsp, form[1]), cap, "native")
        out.update(split_learnset(line["moves"], min(cap, lf), "benched"))
        tm_kind = "benched"
    tms = out.pop("%s:tm" % tm_kind, set())
    if tms & added:
        out["%s:tm_addition" % tm_kind] = tms & added
    if tms - added:
        out["%s:tm" % tm_kind] = tms - added
    learnt = set().union(*[v for k, v in out.items() if k.endswith(":level")])
    if "sketch" in learnt:
        out["sketch"] = set(sketch_set)
    return out


def gaps_at(srcs, pool, exempt, by_name):
    """The faults of one form at one gym, except Sketch (judged over the form's gyms by the caller).
    Returns (problems, contributions {kind: moves})."""
    p = []
    level = set()
    for k, v in srcs.items():
        if k.endswith(":level"):
            level |= v
            missing = sorted(m for m in v if m not in pool and m not in by_name)
            if missing:
                p.append("%s: %s the pool lacks" % (k, ", ".join(missing)))
    contrib = {}
    for k, v in srcs.items():
        if k.endswith(":level"):
            continue
        if k == "sketch":                        # what only Sketch gives: every other source's moves taken out
            others = set().union(*[w for j, w in srcs.items() if j != k])
        else:                                    # less what another source the pool must see already gives; an
            # exempt kind's moves are not taken out (the pool need not hold them), nor Sketch's (it copies anything,
            # so taking it out would leave a Sketch learner's TM entry nothing to answer for)
            others = set().union(*[w for j, w in srcs.items() if j not in (k, "sketch") and j not in exempt])
        c = v - others
        contrib[k] = c
        if k == "sketch" or not c or k in exempt:
            continue
        if not (pool & c):
            p.append("%s: the pool has none of %s" % (k, ", ".join(sorted(c)[:8]) + (" ..." if len(c) > 8 else "")))
    attributable = set().union(*srcs.values()) if srcs else set()
    phantom = sorted(pool - attributable)
    if phantom:
        p.append("the pool has %s, which no source gives" % ", ".join(phantom))
    return p, contrib


def check_plan(doc, mp, exempt=None, by_name=None):
    """Every fault, as text. `mp` is mythical_starters.measure_plan's result: the system under test."""
    exempt = M.MEASURE_UNMODELLED if exempt is None else exempt
    by_name = M.SELF_KO if by_name is None else by_name
    jar = mp["jar"]
    allsp = M.jar_species(jar)
    sk = sketchable(zipfile.ZipFile(jar).read(SHOWDOWN_MOVES).decode("utf8", "replace"))
    species, moves, chart = mp["species"], mp["moves"], mp["chart"]
    p = []
    for k, why in exempt.items():
        if not str(why or "").strip():
            p.append("MEASURE_UNMODELLED %r has no reason" % k)
    seen = {k: {"present": False, "modelled": False} for k in exempt}
    lines = {ln["id"]: ln for ln in doc["lines"]}
    for lid, gyms in mp["plan"].items():
        line = lines[lid]
        sketch_seen = {}                         # form -> [contribution non-empty anywhere, pool holds some]
        for g in sorted(gyms):
            cap = gyms[g]["cap"]
            for label, key, form in gyms[g]["options"]:
                mon = B.Mon(species, key, cap, moves, chart)
                pool = set(B.level_moves(mon.sp, cap))
                srcs = sources(doc, line, form, cap, allsp, sk)
                probs, contrib = gaps_at(srcs, pool, exempt, by_name)
                where = "%s g%d (cap %d, %s)" % (lid, g, cap, label)
                p.extend("%s %s" % (where, x) for x in probs)
                for k, c in contrib.items():
                    if k in seen and c:
                        seen[k]["present"] = True
                        seen[k]["modelled"] |= bool(pool & c)
                if "sketch" in contrib:
                    s = sketch_seen.setdefault(form, [False, False])
                    s[0] |= bool(contrib["sketch"])
                    s[1] |= bool(pool & contrib["sketch"])
        for form, (present, held) in sketch_seen.items():
            if present and not held and "sketch" not in exempt:
                p.append("%s %s %s: learns Sketch, and at no gym does the pool hold a move only Sketch gives"
                         % (lid, form[0], form[1]))
    for k, s in seen.items():
        if not s["present"]:
            p.append("MEASURE_UNMODELLED %r exempts nothing: no measured form has that source" % k)
        elif s["modelled"]:
            p.append("MEASURE_UNMODELLED %r: the pool now models it; drop the exemption" % k)
    return p


def main(argv=None):
    doc = json.loads(M.DATA.read_text(encoding="utf-8"))
    mp = M.measure_plan(doc)
    p = check_plan(doc, mp)
    for x in p:
        print("PROBLEM", x)
    if p:
        print("%d problem(s): the simulator cannot see a move source" % len(p))
        return 1
    forms = sum(len(o["options"]) for gy in mp["plan"].values() for o in gy.values())
    print("ok: %d lines, %d measured forms-at-a-cap, every move source seen or exempt (%d exempt kinds)"
          % (len(mp["plan"]), forms, len(M.MEASURE_UNMODELLED)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

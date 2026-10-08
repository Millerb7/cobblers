#!/usr/bin/env python
"""The six starters (five mythical, and Larvesta), "a-lite" at 30 and 45, from data/mythical_starters.json, as the world pack
build/datapacks/cobblers_mythical_starters.

The design (docs/mechanics/NATIVE_STARTERS_COST.md sections 6a and 7, the owner 2026-10-02/03): Cosmog, Kubfu,
Type: Null, Poipole and Meltan are offered at level 5 carrying the forced aspect `cobblers_starter_1`. That aspect
selects a FORM we append to the species through `species_additions`, with its own base stats, its own level-up
movepool and its own `evolutions`. At 30 the form evolves to the stage-2 form (`cobblers_starter_2`: Cosmoem for the
Cosmog line, the same species for the other four), and at 45 to the NATIVE final species with the aspect removed, so
Solgaleo/Lunala, Urshifu, Silvally, Naganadel and Melmetal stay exactly as Cobblemon and the addons ship them (no
Silvally memory or Urshifu style fan-out). Wild, raid and trainer copies never carry the aspect, so nothing here
touches them: a form's own `evolutions` never falls back to the species list (src `pokemon/FormData.kt:210-211`,
relayed from docs/research/NATIVE_STARTERS_1_8_0.md section 4a).

Formats, each shown in the 1.8.0 jar or a shipped pack (docs/research/NATIVE_STARTERS_1_8_0.md, and this tool's own
`check`, which reads the jar):
  species_additions   any namespace: JsonDataRegistry lists `species_additions` with listResources over every
                      namespace and skips only `pixelmon` (jar JsonDataRegistry.class); `forms` and `evolutions`
                      APPEND (SpeciesAdditions.class). So ours live at data/cobblers/species_additions/ and cannot
                      collide with Mega Showdown's or COBBLEVERSE's data/cobblemon/species_additions/<same name>.
  a form              `name`, `aspects`, `baseStats`, `moves`, `evolutions`: COBBLEVERSE-DP-v31 ships forms with all
                      five (Primal Dialga, Shadow and Armored Mewtwo, Origin Palkia); and Mega Showdown 1.0.2's
                      data/cobblemon/species_additions/pikachu.json adds forms whose `evolutions` are NON-empty, with
                      a properties result carrying a custom property (`raichu cosmetic_item=pewter_crunchies`).
  an evolution        the jar's own species JSON: `id`, `variant` level_up / item_interact, `result` (a properties
                      string), `consumeHeldItem`, `learnableMoves`, `requirements` (`level` minLevel, `time_range`
                      range), `requiredContext` (the scroll), `drops`.
  `unaspect=`         a registered property (jar UnaspectPropertyType.class, key "unaspect", removes a forced aspect;
                      registered in Cobblemon.class); `aspect=` adds one (AspectPropertyType.class). An evolution
                      applies its result with PokemonProperties.apply, which applies custom properties
                      (Evolution.applyTo).
  "offered not forced" the `optional` key is OMITTED: LevelUpEvolution's no-argument constructor (the one Gson uses)
                      passes optional = true (jar LevelUpEvolution.class, `iconst_1` as the 4th constructor
                      argument). No shipped JSON sets `optional` at all.

THE SEVENTH, SMEARGLE (the owner, 2026-10-08; docs/research/notes/smeargle-protean-sketch-1.8.0.md section 4). Smeargle
has no evolution, so its line is THREE forms of the one species (aspects cobblers_starter_1/2/3) and BOTH its steps,
30 and 45, are same-species form changes; a three-form line has no native final (`final` is empty) and its stage 3
has no evolution. Every Smeargle form carries its own `abilities` (Protean; the jar's raichu.json form "Alola" is the
format), and a form may give its spread as a literal `shape` instead of a jar species' `shape_from`.
  the Sketch cap      data/mythical_starters.json `sketch_cap` (docs/research/notes/sketch-cap-1.8.0.md), emitted
                      into this same pack:
    data/cobblers/moves/sketch.js   Showdown's own Sketch, read from the jar's data/cobblemon/showdown.zip
                      data/moves.js (the copy battles run; Mega Showdown 1.0.2's patched moves.js has the same entry),
                      with one guard: fail when source.dynamaxLevel >= the cap. Moves.reload lists every namespace's
                      `moves/*.js` and keys each by its file name; GraalShowdownService.sendRegistryData strips every
                      newline before Showdown evals it, so the file carries only /* */ comments and every statement
                      ends in a semicolon (checked here); sim/dex-moves.js asks Cobblemon.registries.move first.
    data/cobblemon/callbacks/{battle_started_post,battle_victory,battle_fled}/cobblers_sketch_cap.molang
                      mark every party Pokemon that knows Sketch at the start; at the end (and before re-marking), a
                      marked Pokemon that no longer knows Sketch has used it, so its saved dmax_level (DmaxLevel; the
                      count Showdown sees, clamped 0..10 by sim/pokemon.js) goes up by one. Under data/cobblemon/
                      because Cobblemon fires only callbacks in its own namespace (EXP-042, tools/arena_runtime.py).
                      The count needs modpack/config/cobblemon/main.json maxDynamaxLevel >= the cap (setDmaxLevel
                      clamps to it), and the cap cannot exceed 10 (Showdown's clamp).

THE EIGHTH, MISDREAVUS (the owner, 2026-10-08). A tagged Misdreavus at 5 and a tagged Mismagius at 30, each in its own
species' shape, then at 45 a CROSS-SPECIES step into Flutter Mane, which the jar does not relate to the line: the
result is an ordinary properties string (`fluttermane unaspect=cobblers_starter_2`), and nothing here treats it
differently from a native final. Read from the 1.8.0 jar's bytecode: Evolution.evolutionMethod clones the Pokemon and
applies getResult() to it; Pokemon.setSpecies writes only the species field, then runs updateAspects, updateForm,
checkGender, updateHP and attemptAbilityUpdate (setSpecies itself writes no level, IV, EV, nature, shiny or OT field;
the bodies of the methods it calls were not read); and
FormData.getEvolutions returns the form's own set or an empty one, so the starter Misdreavus never takes a Dusk Stone.
Flutter Mane is `implemented` only through COBBLEVERSE-DP-v31's species_additions. Runtime: EXP-068.

What has NOT been run (EXP-049, EXP-065, EXP-068): that the forms load and fight at their stats, that the aspect survives a
species change, that a SAME-SPECIES evolution moves a Pokemon from one form to the next (the riskiest link, twice for
Smeargle), that the cap holds against Rare Candy, and every part of the Sketch cap. Valid JSON is the most this tool
can claim.

  python tools/mythical_starters.py check      # the data against the jar and the starter config; writes nothing
  python tools/mythical_starters.py build      # check, then -> build/datapacks/cobblers_mythical_starters
  python tools/mythical_starters.py measure    # tools/battle_sim.py's own duel, each stage at each gym's cap
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "mythical_starters.json"
STARTERS = ROOT / "modpack" / "config" / "cobblemon" / "starters.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_mythical_starters"
NS = "cobblers"
STATS = ("hp", "attack", "defence", "special_attack", "special_defence", "speed")

# This tool never decides where anything goes; it reads no world.
WORLD_READS = set()

sys.path.insert(0, str(Path(__file__).resolve().parent))
import battle_sim as B  # noqa: E402  (the jar finder, species keys, Showdown moves and the duel)


# ------------------------------------------------------------------------------------------------ the jar

def jar_species(jar):
    """Every species file in the jar, implemented or not: four of the six lines are `implemented: false` in the
    bare jar (Mega Showdown and COBBLEVERSE switch them on), so battle_sim.load_pack drops them. Larvesta and
    Volcarona are implemented in the bare jar."""
    z = zipfile.ZipFile(jar)
    out = {}
    for n in z.namelist():
        if n.startswith("data/cobblemon/species/") and n.endswith(".json"):
            d = json.loads(z.read(n))
            out[B.key(d["name"])] = d
    return out


def scale(shape, bst):
    """A stat line in `shape`'s proportions totalling exactly `bst`: floor each share, then hand the remainder out
    by largest fraction (ties in STATS order). The rule the record's baseStats are checked against."""
    total = sum(shape[k] for k in STATS)
    raw = {k: shape[k] * bst / total for k in STATS}
    out = {k: int(raw[k]) for k in STATS}
    left = bst - sum(out.values())
    for k in sorted(STATS, key=lambda k: (-(raw[k] - int(raw[k])), STATS.index(k)))[:left]:
        out[k] += 1
    return out


def learnset_union(allsp, names):
    out = set()
    for n in names:
        for e in allsp[B.key(n)].get("moves") or []:
            out.add(e.split(":", 1)[1])
    return out


# ------------------------------------------------------------------------------------------------ the check

LEVEL_MOVE = re.compile(r"^(\d+):([a-z0-9]+)$")


def check(doc, jar=None):
    """Every problem with the record, as a list of strings. Nothing is written."""
    jar = jar or B.find_jar()
    allsp = jar_species(jar)
    z = zipfile.ZipFile(jar)
    showdown = B.parse_moves(z.read(B.SHOWDOWN + "moves.js").decode("utf8", "replace"))
    abilities = running_abilities(z)
    p = []
    a1, a2 = doc["aspects"]["stage_1"], doc["aspects"]["stage_2"]
    l2, lf = doc["levels"]["stage_2"], doc["levels"]["final"]
    if not (doc["levels"]["start"] < l2 < lf):
        p.append("levels must rise: start < stage_2 < final")
    ids = set()
    for line in doc["lines"]:
        lid = line["id"]
        if lid in ids:
            p.append("%s: duplicate line id" % lid)
        ids.add(lid)
        members = line["learnset_from"]
        for n in members:
            if B.key(n) not in allsp:
                p.append("%s: learnset_from %r is not a species in the jar" % (lid, n))
        if any(B.key(n) not in allsp for n in members):
            continue
        legal = learnset_union(allsp, members)
        # the movepool: level:move, rising, every move in Showdown's data AND in the line's own 1.8.0 learnset
        last = 0
        for e in line["moves"]:
            m = LEVEL_MOVE.match(e)
            if not m:
                p.append("%s: move entry %r is not level:move" % (lid, e))
                continue
            lv, mid = int(m.group(1)), m.group(2)
            if lv < last:
                p.append("%s: %r is out of level order" % (lid, e))
            # after the final evolution the native species' own learnset takes over, so a pool entry past it would
            # only ever reach a player who keeps declining the offer: authored balance has to land before it
            if lv > doc["levels"]["final"]:
                p.append("%s: %r is past the final evolution at %d" % (lid, e, doc["levels"]["final"]))
            last = lv
            if mid not in showdown:
                p.append("%s: %r is not a move in the jar's Showdown data" % (lid, mid))
            if mid not in legal:
                p.append("%s: %r is not in the 1.8.0 learnset of any of %s" % (lid, mid, ", ".join(members)))
        if not any(LEVEL_MOVE.match(e) and int(LEVEL_MOVE.match(e).group(1)) <= doc["levels"]["start"]
                   for e in line["moves"]):
            p.append("%s: no move at or below the starting level %d" % (lid, doc["levels"]["start"]))
        stages = line["stages"]
        nums = [s["stage"] for s in stages]
        if nums not in ([1, 2], [1, 2, 3]):
            p.append("%s: stages must be exactly 1 and 2 (or 1, 2 and 3 for a line with no native final)" % lid)
            continue
        if nums == [1, 2, 3]:
            # a three-form line (Smeargle): no native final, one species throughout, stage 3 is where it stays
            if line["final"]:
                p.append("%s: a three-form line has no native final; `final` is %s" % (lid, line["final"]))
            if not doc["aspects"].get("stage_3"):
                p.append("%s: a three-form line needs aspects.stage_3" % lid)
            if len({B.key(s["species"]) for s in stages}) != 1:
                p.append("%s: a three-form line is one species throughout" % lid)
            if stages[2]["evolutions"]:
                p.append("%s stage 3: the last form has no evolution" % lid)
        elif not line["final"]:
            p.append("%s: a two-stage line needs its native final(s)" % lid)
        with_abilities = [s["stage"] for s in stages if "abilities" in s]
        if with_abilities and with_abilities != nums:
            p.append("%s: `abilities` on stages %s only; every form of the line carries them or none does"
                     % (lid, with_abilities))
        for s in stages:
            where = "%s stage %d" % (lid, s["stage"])
            aspect = doc["aspects"].get("stage_%d" % s["stage"])
            if s["aspect"] != aspect:
                p.append("%s: aspect %r, expected %r" % (where, s["aspect"], aspect))
            if B.key(s["species"]) not in allsp:
                p.append("%s: species %r is not in the jar" % (where, s["species"]))
                continue
            sp = allsp[B.key(s["species"])]
            if any(f.get("name", "").lower() == s["form"].lower() for f in sp.get("forms") or []):
                p.append("%s: form name %r is already one of %s's own forms" % (where, s["form"], s["species"]))
            if any(aspect in (f.get("aspects") or []) for f in sp.get("forms") or []):
                p.append("%s: aspect %r is already used by a native form" % (where, aspect))
            bs = s["baseStats"]
            if sorted(bs) != sorted(STATS):
                p.append("%s: baseStats keys %s" % (where, sorted(bs)))
                continue
            if sum(bs.values()) != s["bst"]:
                p.append("%s: baseStats total %d, declared bst %d" % (where, sum(bs.values()), s["bst"]))
            # the spread: a jar species' (`shape_from`) or a literal one (`shape`, the owner's own numbers), never both
            if ("shape" in s) == ("shape_from" in s):
                p.append("%s: give exactly one of shape_from (a jar species) and shape (a literal spread)" % where)
                continue
            if "shape" in s:
                shape, named = s["shape"], "the declared shape"
                if sorted(shape) != sorted(STATS):
                    p.append("%s: shape keys %s" % (where, sorted(shape)))
                    continue
            else:
                sp_shape = allsp.get(B.key(s["shape_from"]))
                if sp_shape is None:
                    p.append("%s: shape_from %r is not in the jar" % (where, s["shape_from"]))
                    continue
                shape, named = sp_shape["baseStats"], "%s's shape" % s["shape_from"]
            if bs != scale(shape, s["bst"]):
                p.append("%s: baseStats %s are not %s scaled to %d (%s)"
                         % (where, bs, named, s["bst"], scale(shape, s["bst"])))
            if "abilities" in s:
                p.extend(check_abilities(s["abilities"], abilities, where))
            evos = s["evolutions"]
            if not evos and s["stage"] < 3:
                p.append("%s: no evolution" % where)
            for ev in evos:
                p.extend(check_evolution(ev, s, line, doc, allsp, where))
        for lo, hi in zip(stages, stages[1:]):
            if lo["bst"] >= hi["bst"]:
                p.append("%s: stage %d must be stronger than stage %d" % (lid, hi["stage"], lo["stage"]))
        if "sketch_cap" in line:
            p.extend(check_sketch_cap(line, z))
    p.extend(check_config(doc))
    p.extend(check_wild(doc, allsp))
    return p


ABILITY = re.compile(r"^(?:h:)?[a-z0-9]+$")


def running_abilities(z):
    """Every ability id in the running Showdown's data/abilities.js (Protean is the Gen 9 one there: abilities.js
    `protean` sets effectState.protean, once per switch-in; the research note section 1)."""
    import io
    inner = zipfile.ZipFile(io.BytesIO(z.read(RUNNING_SHOWDOWN)))
    text = inner.read("data/abilities.js").decode("utf8")
    return set(re.findall(r"^  ([a-z0-9]+): \{", text, re.M))


def check_abilities(pool, abilities, where):
    """A form's ability pool in the species-file format (`id`, `h:id` hidden): every id one Showdown knows, at least
    one that is not hidden."""
    p = []
    if not isinstance(pool, list) or not pool:
        return ["%s: abilities must be a non-empty list" % where]
    for a in pool:
        if not ABILITY.match(str(a)):
            p.append("%s: ability entry %r is not id or h:id" % (where, a))
        elif str(a).split(":")[-1] not in abilities:
            p.append("%s: ability %r is not in the jar's Showdown abilities" % (where, a))
    if all(str(a).startswith("h:") for a in pool):
        p.append("%s: abilities %s are all hidden" % (where, pool))
    return p


# ------------------------------------------------------------------------------------------------ the Sketch cap

RUNNING_SHOWDOWN = "data/cobblemon/showdown.zip"     # the copy battles run (smeargle-protean-sketch-1.8.0.md section 0)
SHOWDOWN_CLAMP = 10          # sim/pokemon.js:118 clampIntRange(set.dynamaxLevel, 0, 10): the most the count can carry
MAIN_CONFIG = ROOT / "modpack" / "config" / "cobblemon" / "main.json"
SKETCH_ONHIT = "    onHit(target, source) {\n"
CALLBACK_EVENTS = ("battle_started_post", "battle_victory", "battle_fled")


def stock_sketch(z):
    """Showdown's own `sketch` entry from the running copy, as the object literal (no key), or raise."""
    import io
    inner = zipfile.ZipFile(io.BytesIO(z.read(RUNNING_SHOWDOWN)))
    text = inner.read("data/moves.js").decode("utf8").replace("\r\n", "\n")
    m = re.search(r"^  sketch: (\{\n.*?^  \}),?$", text, re.M | re.S)
    if not m:
        raise SystemExit("%s data/moves.js has no `sketch` entry" % RUNNING_SHOWDOWN)
    return m.group(1)


def sketch_override(cap, z):
    """The stock Sketch with one guard as the first line of onHit. The returned text survives Cobblemon's newline
    stripping: no // comment, and every line of the function bodies ends in ; { } or ,."""
    body = stock_sketch(z)
    if body.count(SKETCH_ONHIT) != 1:
        raise SystemExit("the stock Sketch's onHit is not `onHit(target, source) {`; the guard has nowhere to go")
    guard = ("      /* cobblers: the Sketch cap. The count is the Pokemon's saved Dynamax Level, raised by one after "
             "every battle in which it Sketched (cobblers_sketch_cap.molang, three battle callbacks). */\n"
             "      if (source.dynamaxLevel >= %d) return false;\n" % cap)
    body = body.replace(SKETCH_ONHIT, SKETCH_ONHIT + guard)
    # dedent the two leading spaces the entry had inside moves.js
    body = "\n".join(l[2:] if l.startswith("  ") else l for l in body.split("\n"))
    head = ("/* Generated by tools/mythical_starters.py from data/mythical_starters.json sketch_cap: Showdown's own "
            "Sketch (Cobblemon 1.8.0, data/cobblemon/showdown.zip data/moves.js), refused once the Pokemon has "
            "Sketched %d times. Cobblemon removes every newline before Showdown reads this file, so it uses only "
            "block comments and ends every statement with a semicolon. */\n" % cap)
    return head + body + "\n"


def newline_safe(js):
    """[problem] for a JS text that Cobblemon will join into one line: a // comment, or a body line that ends without
    a terminator (it would run into the next line once the newline is gone)."""
    p = []
    # a comment ends at its first */, as JavaScript reads it (a path like callbacks/*/x inside one ends it early)
    flat = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    if "*/" in flat or "/*" in flat:
        p.append("an unbalanced /* */ comment")
    if "//" in flat:
        p.append("a // comment: once newlines are stripped it comments out the rest of the file")
    rows = [l.strip() for l in flat.split("\n")]
    for i, s in enumerate(rows):
        nxt = next((r for r in rows[i + 1:] if r), "")
        if not s or s.endswith((";", "{", "}", ",", "(", "[")) or nxt.startswith(("}", ")", "]")):
            continue
        if re.match(r"^(if|for|while)\b.*\)$", s):        # `if (x)` then its one statement on the next line
            continue
        p.append("line %d %r ends without ; { } or , and the next line does not close a block" % (i + 1, s))
    return p


def check_sketch_cap(line, z):
    p = []
    c = line["sketch_cap"]
    lid = line["id"]
    cap = c.get("uses")
    if not isinstance(cap, int) or not 1 <= cap <= SHOWDOWN_CLAMP:
        p.append("%s sketch_cap.uses %r: an integer 1..%d (Showdown clamps the count it sees to 0..%d)"
                 % (lid, cap, SHOWDOWN_CLAMP, SHOWDOWN_CLAMP))
        return p
    if c.get("count_on") != "dmax_level":
        p.append("%s sketch_cap.count_on %r: the only channel that reaches Showdown is dmax_level" % (lid, c.get("count_on")))
    if not re.match(r"^[a-z0-9_]+$", str(c.get("armed_aspect", ""))) or \
            str(c.get("armed_aspect", "")).startswith("cobblers_starter_"):
        p.append("%s sketch_cap.armed_aspect %r: a plain aspect id, not a starter form's" % (lid, c.get("armed_aspect")))
    if not any(e == "1:sketch" for e in line["moves"]):
        p.append("%s: a Sketch-capped line keeps 1:sketch in its learnset" % lid)
    msgs = c.get("messages") or {}
    if sorted(msgs) != ["counted", "spent"] or any("'" in str(v) for v in msgs.values()):
        p.append("%s sketch_cap.messages: exactly `counted` and `spent`, no single quote (they sit in Molang strings)"
                 % lid)
    mx = json.loads(MAIN_CONFIG.read_text(encoding="utf-8")).get("maxDynamaxLevel")
    if not isinstance(mx, int) or mx < cap:
        p.append("%s maxDynamaxLevel %r is below the cap %d: setDmaxLevel clamps the count to it and Sketch never "
                 "fails" % (MAIN_CONFIG.relative_to(ROOT).as_posix(), mx, cap))
    try:
        js = sketch_override(cap, z)
    except SystemExit as e:
        return p + ["%s: %s" % (lid, e)]
    p.extend("%s sketch.js: %s" % (lid, x) for x in newline_safe(js))
    return p


SPAWNS = ROOT / "data" / "spawns.json"


def family(allsp, base):
    """The base species and everything it evolves into, by the jar's own evolution results (forms' included)."""
    out, todo = set(), [B.key(base)]
    while todo:
        k = todo.pop()
        if k in out or k not in allsp:
            continue
        out.add(k)
        sp = allsp[k]
        for ev in (sp.get("evolutions") or []) + [e for f in sp.get("forms") or [] for e in f.get("evolutions") or []]:
            todo.append(B.key((ev.get("result") or "").split()[0]))
    return out


def check_wild(doc, allsp):
    """The 27 leave the starter screen only because they stay wild: every family needs a weighted roster record in
    data/spawns.json (any stage; 16 of the 27 are rostered from their middle or final stage only)."""
    p = []
    rows = json.loads(SPAWNS.read_text(encoding="utf-8"))["entries"]
    wild = {B.key(r["species"].split()[0]) for r in rows if (r.get("weight") or 0) > 0}
    names = [s for v in doc["wild_traditional_starters"]["regions"].values() for s in v]
    if len(names) != 27 or len(set(names)) != 27:
        p.append("wild_traditional_starters lists %d species (%d distinct), not 27" % (len(names), len(set(names))))
    for s in names:
        if B.key(s) not in allsp:
            p.append("wild starter %r is not a species in the jar" % s)
        elif not family(allsp, s) & wild:
            p.append("wild starter %r: no member of its family has a weighted record in data/spawns.json" % s)
    return p


def check_evolution(ev, s, line, doc, allsp, where):
    p = []
    a1, a2 = doc["aspects"]["stage_1"], doc["aspects"]["stage_2"]
    if "optional" in ev:
        p.append("%s: `optional` is set; the decision is OFFERED, which is the omitted default (true)" % where)
    if not ev.get("id", "").startswith("cobblers_starter_"):
        p.append("%s: evolution id %r must start cobblers_starter_" % (where, ev.get("id")))
    words = ev["result"].split()
    res = B.key(words[0])
    props = dict(w.split("=", 1) for w in words[1:] if "=" in w)
    if res not in allsp:
        p.append("%s: result species %r is not in the jar" % (where, words[0]))
    lv = [r.get("minLevel") for r in ev.get("requirements") or [] if r.get("variant") == "level"]
    if s["stage"] == 1:
        want = doc["levels"]["stage_2"]
        if B.key(words[0]) != B.key(line["stages"][1]["species"]):
            p.append("%s: stage 1 must evolve into stage 2's species %r" % (where, line["stages"][1]["species"]))
        if props.get("unaspect") != a1 or props.get("aspect") != a2:
            p.append("%s: result %r must carry unaspect=%s aspect=%s" % (where, ev["result"], a1, a2))
        if ev["variant"] != "level_up":
            p.append("%s: stage 1 advances by level_up" % where)
    elif len(line["stages"]) == 3:
        # the same-species step at 45 into the third form (Smeargle): the stage-2 aspect off, the stage-3 one on
        want = doc["levels"]["final"]
        a3 = doc["aspects"].get("stage_3")
        if B.key(words[0]) != B.key(line["stages"][2]["species"]):
            p.append("%s: stage 2 must evolve into stage 3's species %r" % (where, line["stages"][2]["species"]))
        if props.get("unaspect") != a2 or props.get("aspect") != a3:
            p.append("%s: result %r must carry unaspect=%s aspect=%s" % (where, ev["result"], a2, a3))
        if ev["variant"] != "level_up":
            p.append("%s: stage 2 of a three-form line advances by level_up" % where)
    else:
        want = doc["levels"]["final"]
        if res not in [B.key(f) for f in line["final"]]:
            p.append("%s: result %r is not one of the line's native finals %s" % (where, words[0], line["final"]))
        if props.get("unaspect") != a2 or "aspect" in props:
            p.append("%s: result %r must carry unaspect=%s and nothing else of ours" % (where, ev["result"], a2))
        if ev["variant"] == "item_interact" and not ev.get("requiredContext"):
            p.append("%s: item_interact without requiredContext" % where)
    if lv != [want]:
        p.append("%s: level requirement %s, expected exactly [%d]" % (where, lv, want))
    other = [r["variant"] for r in ev.get("requirements") or [] if r.get("variant") not in ("level", "time_range")]
    if other:
        p.append("%s: requirements other than level/time_range: %s" % (where, other))
    if ev["variant"] not in ("level_up", "item_interact"):
        p.append("%s: variant %r" % (where, ev["variant"]))
    return p


def config_entries(doc):
    """The species by its jar id (`typenull`, not "Type: Null"), the level, and the stage-1 aspect. Properties
    strings with extra keys are shipped in COBBLEVERSE's own starter config (`Pikachu level=5 moves=thundershock`,
    `Cyndaquil region_bias=hisui level=5 pokeball=ancient_poke_ball`); `aspect=` is a registered property."""
    return ["%s level=%d aspect=%s" % (line["stages"][0]["species"], doc["levels"]["start"], doc["aspects"]["stage_1"])
            for line in doc["lines"]]


def check_config(doc):
    """The starter screen offers exactly the record's stage-1 forms (six) and none of the 27 (they stay wild)."""
    p = []
    cfg = json.loads(STARTERS.read_text(encoding="utf-8"))
    cats = cfg.get("starters") or []
    offered = [e for c in cats for e in c.get("pokemon") or []]
    want = config_entries(doc)
    if offered != want:
        p.append("%s offers %s, the record says %s" % (STARTERS.relative_to(ROOT).as_posix(), offered, want))
    if [c.get("name") for c in cats] != [doc["starter_category"]["name"]]:
        p.append("starters.json categories %s, expected the one %r" % ([c.get("name") for c in cats],
                                                                       doc["starter_category"]["name"]))
    return p


# ------------------------------------------------------------------------------------------------ the pack

def addition(doc, species, stages):
    forms = []
    for s in stages:
        form = {
            "name": s["form"],
            "aspects": [s["aspect"]],
        }
        # a form's own ability pool, in the species-file format (jar raichu.json form "Alola": abilities
        # ["surgesurfer", "h:surgesurfer"]); a form that sets none inherits the species' pool
        if "abilities" in s:
            form["abilities"] = list(s["abilities"])
        form.update({
            "baseStats": s["baseStats"],
            "moves": s["_moves"],
            "evolutions": s["evolutions"],
        })
        forms.append(form)
    return {"target": "cobblemon:%s" % species, "forms": forms}


def sketch_files(line):
    """The three battle callbacks of the Sketch cap. Settle: a Pokemon marked at the battle's start that no longer
    knows Sketch used it (Sketch's swap benches Sketch: Pokemon.exchangeMove), so its dmax_level goes up by one, read
    and written through properties (`matches('dmax_level=n')`, `apply('dmax_level=n+1')`: PokemonProperties key
    dmax_level -> Pokemon.setDmaxLevel). The count is spelt out level by level, so the script never turns a number
    into text. At the start the settle runs first (a battle that ended with no callback is still counted), then every
    party Pokemon that knows Sketch is marked (a forced aspect, saved). Names used, each read in the 1.8.0 jar: the
    events' `players` context (BattleStartedEvent$Post, BattleVictoryEvent, BattleFledEvent), an actor's `player`
    (BattleActorMoLangFunctions), the party's `pokemon` list (PokemonStoreMoLangFunctions; the jar's own
    player_tick_pre/partner_mark.molang walks it), and a Pokemon's matches, apply, add_aspects, remove_aspects
    (PokemonMoLangFunctions) and a player's tell (PlayerMoLangFunctions). One Pokemon Sketches at most once a battle:
    the copy takes Sketch's own slot (moves.js onHit)."""
    c = line["sketch_cap"]
    cap, armed = c["uses"], c["armed_aspect"]
    msgs = c["messages"]
    settle = [
        "  for_each(t.p, t.pl.party.pokemon, {",
        "    t.p.matches('aspect=%s') ? {" % armed,
        "      t.p.remove_aspects('%s');" % armed,
        "      !t.p.matches('moves=sketch') ? {",
        "        t.n = -1;"]
    settle += ["        t.p.matches('dmax_level=%d') ? { t.n = %d; };" % (n, n) for n in range(cap)]
    for n in range(cap):
        said = (msgs["spent"] if n + 1 == cap else msgs["counted"]).replace("{used}", str(n + 1)) \
            .replace("{cap}", str(cap))
        settle.append("        t.n == %d ? { t.p.apply('dmax_level=%d'); t.pl.tell('%s'); };" % (n, n + 1, said))
    settle += ["      };", "    };", "  });"]
    arm = ["  for_each(t.p, t.pl.party.pokemon, {",
           "    t.p.matches('moves=sketch') ? {",
           "      t.p.add_aspects('%s');" % armed,
           "    };",
           "  });"]
    out = {}
    for event in CALLBACK_EVENTS:
        what = ("settles any mark a battle left, then marks every party Pokemon that knows Sketch"
                if event == "battle_started_post" else
                "counts a Sketch: a marked party Pokemon that no longer knows Sketch used it")
        body = ["'Generated by tools/mythical_starters.py (data/mythical_starters.json %s sketch_cap): the Sketch cap, "
                "%s. The count is the Pokemon own saved Dynamax Level; data/cobblers/moves/sketch.js fails at %d.';"
                % (line["id"], what, cap),
                "for_each(t.a, c.players, {",
                "  t.pl = t.a.player;"] + settle
        if event == "battle_started_post":
            body += arm
        body += ["});"]
        out["data/cobblemon/callbacks/%s/cobblers_sketch_cap.molang" % event] = "\n".join(body) + "\n"
    return out


_JAR = []


def found_jar():
    """battle_sim.find_jar, once a process: when no candidate path exists it walks the whole checkout tree."""
    if not _JAR:
        _JAR.append(B.find_jar())
    return _JAR[0]


def files(doc, jar=None):
    by_species = {}
    for line in doc["lines"]:
        for s in line["stages"]:
            s = dict(s, _moves=list(line["moves"]))
            by_species.setdefault(s["species"], []).append(s)
    out = {}
    for species, stages in sorted(by_species.items()):
        out["data/%s/species_additions/mythical_starter_%s.json" % (NS, species)] = \
            json.dumps(addition(doc, species, stages), indent=2) + "\n"
    capped = [line for line in doc["lines"] if "sketch_cap" in line]
    if len(capped) > 1:
        raise SystemExit("two lines carry a sketch_cap; the move override and callbacks are one per pack")
    for line in capped:
        z = zipfile.ZipFile(jar or found_jar())
        out["data/%s/moves/sketch.js" % NS] = sketch_override(line["sketch_cap"]["uses"], z)
        out.update(sketch_files(line))
    out["pack.mcmeta"] = json.dumps({"pack": {"pack_format": 48, "description":
                                     "Cobblers: the %d starters, a-lite at %d/%d%s (tools/mythical_starters.py)"
                                     % (len(doc["lines"]), doc["levels"]["stage_2"], doc["levels"]["final"],
                                        ", and the Sketch cap" if capped else "")}}, indent=2) + "\n"
    return out


def build(doc):
    if OUT.exists():
        shutil.rmtree(OUT)
    n = 0
    for rel, text in files(doc).items():
        p = OUT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
        n += 1
    return n


# ------------------------------------------------------------------------------------------------ the measure

# battle_sim does not make the user faint on these (grep finds no self-KO handling in tools/battle_sim.py), so its
# choose_moveset takes Explosion's 250 power as a free hit: Silvally was "winning" Giovanni with it. Left out of
# the finals here; the defect itself is battle_sim's, reported, not fixed in this tool.
SELF_KO = {"explosion", "selfdestruct", "mistyexplosion", "memento", "finalgambit", "healingwish", "lunardance"}
# battle_sim would give these free (it models no recharge, charge turn, recoil, crash, self-drop, lock-in or
# conditional power), so a Sketched copy of one is left out of the measure, as the research's sim left them out
# (smeargle-protean-sketch-1.8.0.md section 3)
NOT_FREE = re.compile(r"mustrecharge|charge: 1|recoil:|hasCrashDamage|selfdestruct|lockedmove|basePowerCallback|"
                      r"damageCallback|onTry|self: \{\s*boosts: \{[^}]*-|noSketch")


CHANGES_TYPE = {"protean", "libero"}


def wins_duel(me, foe, moves, chart, species):
    """battle_sim's own duel. battle_sim has no Protean, so for a Protean Pokemon the duel is run once per type among
    its four moves with the Pokemon OF that type throughout, and won if any one wins: Gen 9 Protean (the one 1.8.0
    runs, once per switch-in) makes it the type of its first attack for the rest of a fresh 1v1, and the player picks
    that attack. Not modelled: the first hit it takes lands on its old type."""
    if me.ability not in CHANGES_TYPE:
        return B.duel(me, foe, moves, chart, species=species)[0] is me
    base = me.types
    try:
        for t in sorted({moves[m]["type"] for m in me.moveset if m in moves}):
            me.types = [t]
            if B.duel(me, foe, moves, chart, species=species)[0] is me:
                return True
        return False
    finally:
        me.types = base


def sketch_pool(trainer, text):
    """The moves a Smeargle could Sketch from this trainer's team, less the ones battle_sim would score as free."""
    out = set()
    for m in trainer["team"]:
        for mid in m.get("moveset") or []:
            e = re.search(r"^  %s: \{\n(.*?)^  \},?$" % re.escape(mid), text, re.M | re.S)
            if e and not NOT_FREE.search(e.group(1)) and mid not in SELF_KO:
                out.add(mid)
    return out

def measure(doc, ivs=15):
    """Wins of each leader Pokemon, 1v1 from full health, at each gym's cap, with the stage a player has there.

    The stage at a cap: below stage_2 the stage-1 form, from stage_2 the stage-2 form, from final the native final
    (each choice the line offers is measured; the best is reported). The final carries the native learnset PLUS the
    authored pool, because every move a Pokemon has learnt stays benched and can be slotted back
    (src pokemon/Pokemon.kt allAccessibleMoves, relayed from NATIVE_STARTERS_1_8_0.md section 3d). IVs 15, no
    items, damaging level-up moves only: battle_sim's own Mon, choose_moveset and duel. A lower bound on spread.
    """
    jar = B.find_jar()
    species, moves, chart = B.load_pack(jar)
    allsp = jar_species(jar)
    leaders, _contract = B.gym_leaders()
    _init, rel = B.level_caps(B.RCT_CONFIG)
    l2, lf = doc["levels"]["stage_2"], doc["levels"]["final"]
    out = {}
    pool_text = zipfile.ZipFile(jar).read(B.SHOWDOWN + "moves.js").decode("utf8", "replace")
    for line in doc["lines"]:
        lid = line["id"]
        syn = {}
        for s in line["stages"]:
            k = "cobblers%s%d" % (B.key(lid), s["stage"])
            sp = dict(allsp[B.key(s["species"])], baseStats=s["baseStats"], moves=list(line["moves"]), evolutions=[])
            if "abilities" in s:
                sp["abilities"] = list(s["abilities"])
            species[k] = sp
            syn[s["stage"]] = k
        finals = []
        for f in line["final"]:
            k = "cobblers%sfinal%s" % (B.key(lid), B.key(f))
            nat = allsp[B.key(f.split()[0])]
            native = [e for e in nat.get("moves") or [] if e.split(":", 1)[1] not in SELF_KO]
            sp = dict(nat, moves=native + [e for e in line["moves"] if int(e.split(":")[0]) <= lf], evolutions=[])
            species[k] = sp
            finals.append((f, k))
        res = {}
        sketched = set()
        for g in sorted(leaders):
            t = leaders[g]
            cap = max(m["level"] for m in t["team"]) + rel
            foes = B.build_leader(t, species, moves, chart, ivs, False)
            options = ([("stage 1", syn[1])] if cap < l2 else [("stage 2", syn[2])] if cap < lf
                       else [("stage 3", syn[3])] if 3 in syn else [(f, k) for f, k in finals])
            if "sketch_cap" in line:
                # Sketch is the movepool: the moves of every EARLIER gym leader's team, learnt "at 1" so
                # choose_moveset can pick them (a lower bound: wild Pokemon and route trainers are left out, and
                # battle_sim models no Protean, so the Smeargle here is Normal throughout)
                label, k = options[0]
                k2 = "%sg%d" % (k, g)
                species[k2] = dict(species[k], moves=list(species[k]["moves"])
                                   + ["1:%s" % m for m in sorted(sketched) if m in moves])
                options = [(label + " +sketch", k2)]
                sketched |= sketch_pool(t, pool_text)
            best = None
            for label, k in options:
                me = B.Mon(species, k, cap, moves, chart, ivs=ivs)
                wins = [f.name for f in foes if wins_duel(me, f, moves, chart, species)]
                cand = (len(wins), label, me.moveset, wins)
                if best is None or cand[0] > best[0]:
                    best = cand
            res[g] = {"cap": cap, "foes": len(foes), "wins": best[0], "as": best[1], "moveset": best[2],
                      "beats": best[3]}
        out[lid] = res
    return out


def report(doc, res):
    gyms = sorted(next(iter(res.values())))
    lines = []
    head = "%-16s" % "starter" + "".join("  g%d@%-3d" % (g, res[doc["lines"][0]["id"]][g]["cap"]) for g in gyms) + "  total"
    lines.append(head)
    for lid, r in res.items():
        lines.append("%-16s" % lid + "".join("  %d/%-4d" % (r[g]["wins"], r[g]["foes"]) for g in gyms)
                     + "  %d/%d" % (sum(r[g]["wins"] for g in gyms), sum(r[g]["foes"] for g in gyms)))
    # the potent point: where a starter stands furthest above the field's mean at that gym (share of the foes beaten)
    lines.append("")
    for lid, r in res.items():
        margins = {}
        for g in gyms:
            share = r[g]["wins"] / r[g]["foes"]
            mean = sum(res[o][g]["wins"] / res[o][g]["foes"] for o in res) / len(res)
            margins[g] = share - mean
        top = max(margins.values())
        peak = [g for g in gyms if abs(margins[g] - top) < 1e-9]
        lines.append("%-16s peaks at gym %s (+%.2f over the field's mean share); at each gym: %s"
                     % (lid, "/".join(map(str, peak)), top,
                        " ".join("g%d %+.2f" % (g, margins[g]) for g in gyms)))
    lines.append("")
    for lid, r in res.items():
        for g in gyms:
            lines.append("  %-14s g%d %-9s %s beats %s" % (lid, g, r[g]["as"], ",".join(r[g]["moveset"]),
                                                           ",".join(r[g]["beats"]) or "-"))
    return "\n".join(lines)


# ------------------------------------------------------------------------------------------------ main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=("check", "build", "measure"))
    ap.add_argument("--json", help="measure: also write the figures to this file")
    a = ap.parse_args(argv)
    doc = json.loads(DATA.read_text(encoding="utf-8"))
    if a.cmd == "measure":
        res = measure(doc)
        print(report(doc, res))
        if a.json:
            Path(a.json).write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
        return 0
    problems = check(doc)
    for x in problems:
        print("PROBLEM", x)
    if problems:
        print("%d problem(s); nothing written" % len(problems))
        return 1
    if a.cmd == "check":
        print("ok: %d lines, %d stage forms, starter config consistent" %
              (len(doc["lines"]), sum(len(l["stages"]) for l in doc["lines"])))
        return 0
    n = build(doc)
    print("wrote %s (%d files)" % (OUT.relative_to(ROOT).as_posix(), n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
"""The five mythical starters, "a-lite" at 30 and 45, from data/mythical_starters.json, as the world pack
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

What has NOT been run (EXP-049): that the forms load and fight at their stats, that the aspect survives a species
change, that a SAME-SPECIES evolution moves a Pokemon from one form to the next (the riskiest link), and that the cap
holds against Rare Candy. Valid JSON is the most this tool can claim.

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
    """Every species file in the jar, implemented or not: four of the five lines are `implemented: false` in the
    bare jar (Mega Showdown and COBBLEVERSE switch them on), so battle_sim.load_pack drops them."""
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
        if [s["stage"] for s in stages] != [1, 2]:
            p.append("%s: stages must be exactly 1 and 2" % lid)
            continue
        for s in stages:
            where = "%s stage %d" % (lid, s["stage"])
            aspect = a1 if s["stage"] == 1 else a2
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
            shape = allsp.get(B.key(s["shape_from"]))
            if shape is None:
                p.append("%s: shape_from %r is not in the jar" % (where, s["shape_from"]))
            elif bs != scale(shape["baseStats"], s["bst"]):
                p.append("%s: baseStats %s are not %s's shape scaled to %d (%s)"
                         % (where, bs, s["shape_from"], s["bst"], scale(shape["baseStats"], s["bst"])))
            evos = s["evolutions"]
            if not evos:
                p.append("%s: no evolution" % where)
            for ev in evos:
                p.extend(check_evolution(ev, s, line, doc, allsp, where))
        if stages[0]["bst"] >= stages[1]["bst"]:
            p.append("%s: stage 2 must be stronger than stage 1" % lid)
    p.extend(check_config(doc))
    p.extend(check_wild(doc, allsp))
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
    """The starter screen offers exactly the five stage-1 forms and none of the 27 (they stay wild)."""
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
        forms.append({
            "name": s["form"],
            "aspects": [s["aspect"]],
            "baseStats": s["baseStats"],
            "moves": s["_moves"],
            "evolutions": s["evolutions"],
        })
    return {"target": "cobblemon:%s" % species, "forms": forms}


def files(doc):
    by_species = {}
    for line in doc["lines"]:
        for s in line["stages"]:
            s = dict(s, _moves=list(line["moves"]))
            by_species.setdefault(s["species"], []).append(s)
    out = {}
    for species, stages in sorted(by_species.items()):
        out["data/%s/species_additions/mythical_starter_%s.json" % (NS, species)] = \
            json.dumps(addition(doc, species, stages), indent=2) + "\n"
    out["pack.mcmeta"] = json.dumps({"pack": {"pack_format": 48, "description":
                                     "Cobblers: the five mythical starters, a-lite at %d/%d (tools/mythical_starters.py)"
                                     % (doc["levels"]["stage_2"], doc["levels"]["final"])}}, indent=2) + "\n"
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
    for line in doc["lines"]:
        lid = line["id"]
        syn = {}
        for s in line["stages"]:
            k = "cobblers%s%d" % (B.key(lid), s["stage"])
            sp = dict(allsp[B.key(s["species"])], baseStats=s["baseStats"], moves=list(line["moves"]), evolutions=[])
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
        for g in sorted(leaders):
            t = leaders[g]
            cap = max(m["level"] for m in t["team"]) + rel
            foes = B.build_leader(t, species, moves, chart, ivs, False)
            options = ([("stage 1", syn[1])] if cap < l2 else [("stage 2", syn[2])] if cap < lf
                       else [(f, k) for f, k in finals])
            best = None
            for label, k in options:
                me = B.Mon(species, k, cap, moves, chart, ivs=ivs)
                wins = [f.name for f in foes if B.duel(me, f, moves, chart, species=species)[0] is me]
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

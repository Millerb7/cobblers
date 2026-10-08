#!/usr/bin/env python
"""Independent audit of the six starters (five mythical, and Larvesta), "a-lite" at 30 and 45, as the server loads them.

Written by a test author, not by the session that built them. It never imports tools/mythical_starters.py and never
takes an expectation from data/mythical_starters.json's stage specs: the record's levels, aspects, shapes, BSTs and
evolutions are exactly what is under audit, so none of them is read.

WHERE THE EXPECTATIONS COME FROM
  the decision   docs/mechanics/NATIVE_STARTERS_COST.md sections 6a and 7 (the owner, 2026-10-02): Cosmog, Kubfu,
                 Type: Null, Poipole, Meltan; forms on stages 1 and 2 selected by aspect, the native final untouched;
                 evolutions at 30 and 45; offered, not forced; Meltan to Melmetal at 45 with no anvil; Silvally (and
                 every final) native. The constants below quote it, section by section.
  the jar        Cobblemon 1.8.0's own species files (by file name, the id `cobblemon:<id>` resolves to) and its
                 Showdown moves.js: which species and moves exist, each line's native members and native finals, the
                 native final evolution's kept choices (Cosmoem's day/night, Kubfu's scrolls) and its evolution move.
  upstream       base-pack/cobbleverse/config/cobblemon/starters.json: the 27 traditional starters the screen offered
                 before the decision, which must still spawn wild.

WHAT IS AUDITED
  build/datapacks/cobblers_mythical_starters   the species_additions the server loads (walked as Cobblemon would:
                                               the form is chosen by aspect, the evolution result applied as a
                                               properties string, `unaspect=` removing and `aspect=` adding)
  modpack/config/cobblemon/starters.json       the starter screen
  data/spawns.json                             the 27 stay wild
  data/research_station.json                   who hands out an item a kept native choice needs (OPEN, not a fault)

WHAT IT DOES NOT COVER (runtime, EXP-049): that a form loads and fights at its stats; that the aspect survives the
species change; that a SAME-species level_up moves a Pokemon between two forms; that the cap holds against Rare
Candy; that a `level` requirement is honoured on an `item_interact` evolution; that no other loaded pack (Mega
Showdown, COBBLEVERSE) adds a form with our aspect or ships a `data/*/starters/` category (under
`useConfigStarters: false`, StarterDataLoader.reload in the 1.8.0 jar replaces the config's starters with any loaded
datapack category; only our own build/datapacks are checked here, the mod jars are not in the repo); and that the
five species are `implemented` once the addons load (the bare jar leaves four of them off).

  python tools/mythical_starters_audit.py [--pack DIR] [--starters FILE] [--spawns FILE] [--jar JAR]
exit 1 on any FAULT; OPEN items are printed and do not fail.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACK = ROOT / "build" / "datapacks" / "cobblers_mythical_starters"
STARTERS = ROOT / "modpack" / "config" / "cobblemon" / "starters.json"
UPSTREAM_STARTERS = ROOT / "base-pack" / "cobbleverse" / "config" / "cobblemon" / "starters.json"
SPAWNS = ROOT / "data" / "spawns.json"
RECORD = ROOT / "data" / "mythical_starters.json"
STATION = ROOT / "data" / "research_station.json"
MOVES_JS = "assets/cobblemon/showdown/node_modules/pokemon-showdown/data/moves.js"

# This audit never decides where anything goes; it reads no world.
WORLD_READS = set()

# ------------------------------------------------------------------------------------------------ the decision

START, STAGE_2, FINAL = 5, 30, 45            # 6a table: "level 5", "level 30", "level 45"; 7.1 "30/45, decided"
BST = {1: 330, 2: 430}                       # 3, the a-lite row at 30/45 "330 / 430 / native"; 6a table (Meltan)
ASPECT = {1: "cobblers_starter_1", 2: "cobblers_starter_2"}   # 6a table: the aspect each stage carries
# stage-1 species -> (stage-2 species, the species whose stat shape both stages are scaled into)
# 1.1: only Cosmog evolves twice, so the other four need a SAME-species stage 2. 3: "shape ... is each stage's own,
# except the Cosmog line, which uses Solgaleo's shape". 6a: Meltan "330 BST in Melmetal's shape".
LINES = {
    "cosmog": ("cosmoem", "solgaleo"),
    "kubfu": ("kubfu", "kubfu"),
    "typenull": ("typenull", "typenull"),
    "poipole": ("poipole", "poipole"),
    "meltan": ("meltan", "melmetal"),
    # the sixth (the owner, 2026-10-08; docs/research/notes/larvesta-starter-1.8.0.md version A): stage 2 is a 430
    # form in Larvesta's own shape, never plain Larvesta (native Larvesta evolves at 59)
    "larvesta": ("larvesta", "larvesta"),
}
# 1.2 and 6a: the jar has no Meltan evolution; the decision names Melmetal as its final.
DECLARED_FINALS = {"meltan": {"melmetal"}}
# 4: a-lite "keeps two native choices, Cosmoem's Solgaleo/Lunala and Kubfu's scrolls"; 2: Kubfu stays item_interact
# on the scrolls with a level added. 6a: "Every other line reaches its final form on level alone at 45" (no anvil, no
# friendship, no has_move).
KEPT_CHOICES = {"cosmog": {"time_range"}, "kubfu": {"item_interact"}}
OURS = set(ASPECT.values())


def _id(name):
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


# ------------------------------------------------------------------------------------------------ the jar

def find_jar():
    here = ROOT / "experiments" / "EXP-000-cobblemon-1.8-compat" / "runtime" / "server" / "mods"
    hits = sorted(here.glob("Cobblemon-fabric-1.8*.jar"))
    if hits:
        return hits[0]
    sys.path.insert(0, str(ROOT / "tools"))
    import battle_sim  # noqa: E402  only its jar finder
    return battle_sim.find_jar()


def load_jar(jar):
    """species id (file name) -> species JSON, and move id -> category, from the jar alone."""
    z = zipfile.ZipFile(jar)
    species = {}
    for n in z.namelist():
        if n.startswith("data/cobblemon/species/") and n.endswith(".json"):
            species[n.rsplit("/", 1)[1][:-5]] = json.loads(z.read(n))
    text = z.read(MOVES_JS).decode("utf8", "replace")
    moves = {}
    for m in re.finditer(r"^  ([a-z0-9]+): \{\n(.*?)^  \},?$", text, re.M | re.S):
        cat = re.search(r'^    category: "(\w+)"', m.group(2), re.M)
        moves[m.group(1)] = cat.group(1) if cat else None
    return species, moves


def evolutions_of(sp):
    return list(sp.get("evolutions") or []) + [e for f in sp.get("forms") or [] for e in f.get("evolutions") or []]


def parse_props(text):
    words = str(text).split()
    props = {}
    for w in words[1:]:
        k, _, v = w.partition("=")
        props[k] = v
    return _id(words[0]) if words else "", props


def native_result(text):
    """A result as the jar would write it: our two keys removed, the rest kept and ordered."""
    sp, props = parse_props(text)
    return " ".join([sp] + sorted("%s=%s" % kv for kv in props.items() if kv[0] not in ("aspect", "unaspect")))


def native_finals(species, base):
    """The jar's own last evolution step of a line: {normalised result: the jar's evolution}."""
    cur, seen = base, set()
    while cur in species and cur not in seen:
        seen.add(cur)
        evos = evolutions_of(species[cur])
        if not evos:
            return {}
        nxt = {parse_props(e["result"])[0] for e in evos}
        if all(not evolutions_of(species.get(n, {})) for n in nxt):
            return {native_result(e["result"]): e for e in evos}
        cur = sorted(nxt)[0]
    return {}


def descendants(species, base):
    out, todo = set(), [base]
    while todo:
        k = todo.pop()
        if k in out or k not in species:
            continue
        out.add(k)
        todo.extend(parse_props(e.get("result") or "")[0] for e in evolutions_of(species[k]))
    return out


def learnset(species, ids):
    out = set()
    for i in ids:
        for e in species.get(i, {}).get("moves") or []:
            out.add(e.split(":", 1)[1])
    return out


# ------------------------------------------------------------------------------------------------ the pack

def read_pack(pack):
    """target species id -> the addition JSON, and the faults met reading it."""
    faults, adds = [], {}
    if not pack.is_dir():
        return {}, ["%s does not exist: run `python tools/mythical_starters.py build`" % pack]
    for p in sorted(pack.rglob("*.json")):
        rel = p.relative_to(pack).as_posix()
        if re.match(r"^data/[^/]+/starters?/", rel):
            faults.append("%s: a datapack starter category; with useConfigStarters false it REPLACES the config's "
                          "starters (StarterDataLoader.reload, 1.8.0)" % rel)
            continue
        if "/species_additions/" not in rel:
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        tgt = str(d.get("target", ""))
        if not tgt.startswith("cobblemon:"):
            faults.append("%s: target %r is not a cobblemon species" % (rel, tgt))
            continue
        sp = tgt.split(":", 1)[1]
        if sp in adds:
            faults.append("%s: a second addition for %s" % (rel, sp))
        extra = sorted(set(d) - {"target", "forms"})
        if extra:
            faults.append("%s: species-level keys %s change every %s, wild, raid and trainer copies included "
                          "(decision 2/4: untouched)" % (rel, extra, sp))
        adds[sp] = d
    return adds, faults


def matching_forms(adds, species, aspects):
    """Our forms Cobblemon could pick for a Pokemon carrying `aspects`: every form aspect present."""
    return [f for f in (adds.get(species) or {}).get("forms") or []
            if f.get("aspects") and set(f["aspects"]) <= aspects]


def check_requirements(where, ev, line, final_step, native):
    p = []
    if "optional" in ev and ev["optional"] is not True:
        p.append("%s: optional=%r; the decision is OFFERED (7.3)" % (where, ev["optional"]))
    reqs = ev.get("requirements") or []
    levels = [r.get("minLevel") for r in reqs if r.get("variant") == "level"]
    want = FINAL if final_step else STAGE_2
    if levels != [want]:
        p.append("%s: level requirement %s, the decision is exactly [%d]" % (where, levels, want))
    kept = KEPT_CHOICES.get(line, set()) if final_step else set()
    for r in reqs:
        v = r.get("variant")
        if v == "level":
            continue
        if v == "time_range" and "time_range" in kept and native is not None:
            nat = [x.get("range") for x in native.get("requirements") or [] if x.get("variant") == "time_range"]
            if [r.get("range")] != nat:
                p.append("%s: time_range %r, the jar's own choice is %s" % (where, r.get("range"), nat))
            continue
        p.append("%s: requirement %r (%s); the decision advances this step on level alone" % (where, v, r))
    variant = ev.get("variant")
    if "item_interact" in kept and native is not None and native.get("variant") == "item_interact":
        if variant != "item_interact" or ev.get("requiredContext") != native.get("requiredContext"):
            p.append("%s: %s with %r; the kept native choice is item_interact with %r (decision 2, 4)"
                     % (where, variant, ev.get("requiredContext"), native.get("requiredContext")))
    elif variant != "level_up":
        p.append("%s: variant %r; the decision advances this step by level_up" % (where, variant))
    elif ev.get("requiredContext"):
        p.append("%s: requiredContext %r on a level step" % (where, ev.get("requiredContext")))
    return p


def check_form(where, form, stage, line, species, moves, adds_species, authored):
    p = []
    if form.get("aspects") != [ASPECT[stage]]:
        p.append("%s: aspects %s, the decision selects stage %d by exactly [%s]"
                 % (where, form.get("aspects"), stage, ASPECT[stage]))
    native = species.get(adds_species, {})
    if any(_id(f.get("name")) == _id(form.get("name")) for f in native.get("forms") or []):
        p.append("%s: form name %r is one of %s's own forms" % (where, form.get("name"), adds_species))
    if any(ASPECT[stage] in (f.get("aspects") or []) for f in native.get("forms") or []):
        p.append("%s: aspect %s is a native form's" % (where, ASPECT[stage]))
    bs = form.get("baseStats") or {}
    shape = species[LINES[line][1]]["baseStats"]
    if sorted(bs) != sorted(shape):
        p.append("%s: baseStats keys %s" % (where, sorted(bs)))
    else:
        total = sum(bs.values())
        if total != BST[stage]:
            p.append("%s: BST %d, the decision is %d (3, 6a)" % (where, total, BST[stage]))
        stotal = sum(shape.values())
        # each stat is the shape's share of the declared total; any integer split of it lies within 1 of the share
        for k, v in sorted(bs.items()):
            share = shape[k] * BST[stage] / stotal
            if abs(v - share) >= 1:
                p.append("%s: %s %d is not %s's share %.2f of %d" % (where, k, v, LINES[line][1], share, BST[stage]))
    members = {line, LINES[line][0]} | set(native_final_species(species, line))
    legal = learnset(species, members)
    for e in form.get("moves") or []:
        m = re.match(r"^(\d+):([a-z0-9]+)$", str(e))
        if not m:
            p.append("%s: move entry %r is not level:move" % (where, e))
            continue
        mid = m.group(2)
        if mid not in moves:
            p.append("%s: %r is not a move in the jar" % (where, mid))
        elif mid not in legal and mid not in authored:
            p.append("%s: %r is in no 1.8.0 learnset of %s and is not declared authored"
                     % (where, mid, ", ".join(sorted(members))))
    if stage == 1:
        early = [str(e).split(":", 1)[1] for e in form.get("moves") or []
                 if re.match(r"^\d+:", str(e)) and int(str(e).split(":")[0]) <= START]
        if not any(moves.get(mid) not in (None, "Status") for mid in early):
            p.append("%s: no damaging move learnt by level %d (%s): a starter that cannot attack (1.2)"
                     % (where, START, early))
    return p


def native_final_species(species, line):
    if line in DECLARED_FINALS:
        return sorted(DECLARED_FINALS[line])
    return sorted({k.split()[0] for k in native_finals(species, line)})


def check_line(line, adds, species, moves, authored):
    """Walk the line as Cobblemon would, from the screen's stage-1 Pokemon to the native final."""
    p = []
    stage2 = LINES[line][0]
    if line in DECLARED_FINALS:
        if evolutions_of(species[line]):
            p.append("%s: the jar now has a native evolution; the decision's premise (1.2) has changed" % line)
        natives = {f: None for f in sorted(DECLARED_FINALS[line])}
    else:
        natives = native_finals(species, line)
        if not natives:
            p.append("%s: no native final found in the jar" % line)
            return p
    f1s = matching_forms(adds, line, {ASPECT[1]})
    if len(f1s) != 1:
        return p + ["%s: %d of our forms match the starter (%s, aspect %s); want exactly 1"
                    % (line, len(f1s), line, ASPECT[1])]
    f1 = f1s[0]
    p += check_form("%s stage 1" % line, f1, 1, line, species, moves, line, authored)
    if not f1.get("evolutions"):
        p.append("%s stage 1: no evolution" % line)
    f2 = None
    for ev in f1.get("evolutions") or []:
        where = "%s stage 1 -> %s" % (line, ev.get("result"))
        p += check_requirements(where, ev, line, False, None)
        sp, props = parse_props(ev.get("result"))
        aspects = ({ASPECT[1]} - {props.get("unaspect")}) | ({props["aspect"]} if props.get("aspect") else set())
        if sp != stage2:
            p.append("%s: stage 2 of the %s line is %s (decision 1.1)" % (where, line, stage2))
            continue
        if aspects & OURS != {ASPECT[2]}:
            p.append("%s: the evolved Pokemon carries %s, stage 2 needs exactly %s"
                     % (where, sorted(aspects & OURS), ASPECT[2]))
            continue
        f2s = matching_forms(adds, stage2, aspects)
        if len(f2s) != 1:
            p.append("%s: %d of our forms match (%s, %s); want exactly 1" % (where, len(f2s), stage2, sorted(aspects)))
            continue
        f2 = f2s[0]
    if f2 is None:
        return p + ["%s: the chain never reaches a stage-2 form" % line]
    p += check_form("%s stage 2" % line, f2, 2, line, species, moves, stage2, authored)
    reached = {}
    for ev in f2.get("evolutions") or []:
        res = native_result(ev.get("result"))
        where = "%s stage 2 -> %s" % (line, ev.get("result"))
        sp, props = parse_props(ev.get("result"))
        left = ({ASPECT[2]} - {props.get("unaspect")}) | ({props["aspect"]} if props.get("aspect") else set())
        if left & OURS:
            p.append("%s: the final keeps our aspect %s; the final is native (decision 4)" % (where, sorted(left & OURS)))
        if sp in adds:
            p.append("%s: our pack adds forms to the final %s; finals stay native (decision 4)" % (where, sp))
        if sp not in species:
            p.append("%s: %s is not a species in the jar" % (where, sp))
        elif evolutions_of(species[sp]):
            p.append("%s: %s evolves further in the jar; not a final" % (where, sp))
        native = natives.get(res)
        p += check_requirements(where, ev, line, True, native)
        for mv in ev.get("learnableMoves") or []:
            if mv not in moves:
                p.append("%s: evolution move %r is not in the jar" % (where, mv))
        if native is not None:
            lost = sorted(set(native.get("learnableMoves") or []) - set(ev.get("learnableMoves") or []))
            if lost:
                p.append("%s: drops the native evolution move(s) %s the jar teaches on this step" % (where, lost))
        reached[res] = ev
    if sorted(reached) != sorted(natives):
        p.append("%s: stage 2 reaches %s; the jar's native finals are %s" % (line, sorted(reached), sorted(natives)))
    return p


# ------------------------------------------------------------------------------------------------ the rest

def check_screen(starters_path, species):
    p = []
    cfg = json.loads(Path(starters_path).read_text(encoding="utf-8"))
    offered = [e for c in cfg.get("starters") or [] for e in c.get("pokemon") or []]
    seen = []
    for e in offered:
        sp, props = parse_props(e)
        seen.append(sp)
        if sp not in species:
            p.append("starter screen %r: %s is not a species id in the jar" % (e, sp))
        if props != {"level": str(START), "aspect": ASPECT[1]}:
            p.append("starter screen %r: properties %s, the decision is level=%d aspect=%s"
                     % (e, props, START, ASPECT[1]))
    if sorted(seen) != sorted(LINES):
        p.append("the starter screen offers %s; the decision is exactly the %d stage-1 lines %s"
                 % (sorted(seen), len(LINES), sorted(LINES)))
    return p


def check_wild(spawns_path, record_path, upstream_path, species):
    p = []
    up = json.loads(Path(upstream_path).read_text(encoding="utf-8"))
    # the traditional starters are the regional trios Cobblemon itself names (displayName under its own
    # `cobblemon.starterselection.category.` keys); COBBLEVERSE's Pallet, Lumya and Cosplay sets are its own
    # additions, and Hisui's are forms of three species already in the trios
    traditional = sorted({parse_props(e)[0] for c in up.get("starters") or []
                          if str(c.get("displayName", "")).startswith("cobblemon.starterselection.category.")
                          for e in c.get("pokemon") or []})
    if len(traditional) != 27:
        p.append("upstream %s offers %d distinct species, not the 27" % (Path(upstream_path).name, len(traditional)))
    rec = json.loads(Path(record_path).read_text(encoding="utf-8")).get("wild_traditional_starters") or {}
    listed = [_id(s) for v in (rec.get("regions") or {}).values() for s in v]
    if sorted(listed) != traditional:
        p.append("data/mythical_starters.json wild_traditional_starters %s differs from upstream's offer: missing %s, "
                 "extra %s" % (len(listed), sorted(set(traditional) - set(listed)), sorted(set(listed) - set(traditional))))
    rows = json.loads(Path(spawns_path).read_text(encoding="utf-8"))["entries"]
    wild = {parse_props(r["species"])[0] for r in rows if (r.get("weight") or 0) > 0}
    # 6a: the forms are the screen's alone. Larvesta (2026-10-08) is both a starter line and a wild species, so a
    # wild row is fine and a wild row carrying a starter aspect (or form=<its name>) puts a starter in the grass
    # (the compiled pools are swept by tools/oak_starter_audit.py P2; this is the authored source)
    for r in rows:
        words = str(r.get("species") or "").lower().split()
        hit = [w for w in words[1:] if w.split("=")[-1] in OURS or re.fullmatch(r"form=starter(?:[-_]?grown)?", w)]
        if hit:
            p.append("data/spawns.json %s: %r carries a starter form %s; the forms are the starter screen's alone (6a)"
                     % (r.get("id"), r.get("species"), hit))
    for s in traditional:
        if not descendants(species, s) & wild:
            p.append("%s: no member of its family has a weighted record in data/spawns.json; a starter left the "
                     "screen and is nowhere wild" % s)
    return p


def open_items(adds, station_path):
    """Items a kept native choice needs, and whether the research station issues them (decision 7.5)."""
    need = sorted({ev["requiredContext"] for d in adds.values() for f in d.get("forms") or []
                   for ev in f.get("evolutions") or [] if ev.get("requiredContext")})
    if not need:
        return []
    try:
        st = json.loads(Path(station_path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        st = {}
    issued = json.dumps((st.get("economy") or {}).get("items") or [])
    return ["%s: needed by a starter's final evolution, issued by no item in %s economy.items (decision 7.5: the "
            "research station hands it out); until it is, that line cannot reach its final" % (i, Path(station_path).name)
            for i in need if i not in issued]


def audit(pack=PACK, starters=STARTERS, spawns=SPAWNS, record=RECORD, upstream=UPSTREAM_STARTERS, station=STATION,
          jar=None):
    """(faults, open items). Expectations from the decision constants above and the jar, never from the builder."""
    species, moves = load_jar(jar or find_jar())
    adds, faults = read_pack(Path(pack))
    rec = json.loads(Path(record).read_text(encoding="utf-8"))
    authored = {}
    for line in rec.get("lines") or []:
        st = (line.get("stages") or [{}])[0].get("species")
        authored[_id(st)] = set(line.get("authored_moves") or [])
    if adds:
        allowed = set(LINES) | {v[0] for v in LINES.values()}
        for sp in sorted(set(adds) - allowed):
            faults.append("our pack adds to %s, which is not a stage-1 or stage-2 species of the starter lines "
                          "(finals and everything else stay native: decision 4)" % sp)
        nforms = sum(len(d.get("forms") or []) for d in adds.values())
        if nforms != 2 * len(LINES):
            faults.append("our pack carries %d forms; the decision is %d (two stages x %d lines, 4)"
                          % (nforms, 2 * len(LINES), len(LINES)))
        for line in LINES:
            faults += check_line(line, adds, species, moves, authored.get(line, set()))
    faults += check_screen(starters, species)
    faults += check_wild(spawns, record, upstream, species)
    return faults, open_items(adds, station)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pack", default=str(PACK))
    ap.add_argument("--starters", default=str(STARTERS))
    ap.add_argument("--spawns", default=str(SPAWNS))
    ap.add_argument("--jar")
    a = ap.parse_args(argv)
    faults, opens = audit(pack=Path(a.pack), starters=a.starters, spawns=a.spawns, jar=a.jar)
    for o in opens:
        print("OPEN", o)
    for f in faults:
        print("FAULT", f)
    if faults:
        print("mythical_starters_audit: %d fault(s)" % len(faults))
        return 1
    print("mythical_starters_audit: ok: %d lines walk 5 -> %d -> %d through two forms to their native finals; "
          "the screen offers them; the 27 stay wild (%d open)" % (len(LINES), STAGE_2, FINAL, len(opens)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

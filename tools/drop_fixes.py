#!/usr/bin/env python
"""Species drop tables that cannot do what they say, found by a sweep and fixed from our side, from
data/drop_fixes.json, as the world pack build/datapacks/cobblers_drop_fixes.

  python tools/drop_fixes.py sweep     # every effective drop table the server loads, with ours on top; exit 1 on a
                                       # fault data/drop_fixes.json neither fixes nor holds open
  python tools/drop_fixes.py sweep --upstream    # the same without our fixes: what upstream ships; exit 1 on a fault
                                       # no record fixes or holds open
  python tools/drop_fixes.py check     # the data against the upstream it overrides and the roll; writes nothing
  python tools/drop_fixes.py build     # check, then -> build/datapacks/cobblers_drop_fixes

THE TWO FAULTS (the owner, 2026-10-08: "Fix the three drop faults, then sweep for others of the same shape: a
nonexistent item id, or a table that can never reach its later entries"):
  missing item   an entry names an item no installed jar or datapack registers. An item exists when a jar or pack
                 carries a lang key item.<ns>.<path> / block.<ns>.<path> or a model assets/<ns>/models/item/<path>.json
                 (the rule tools/economy_audit.py `ids` uses; its Jars reader is reused here). In the game the entry is
                 still rolled and drops nothing (ItemDropEntry.drop looks the id up in the item registry).
  unreachable    an entry that the roll can never choose: its chance, computed exactly over the algorithm below, is 0.

HOW A TABLE ROLLS (DropTable.getDrops and ItemDropEntry in Cobblemon-fabric-1.8.0+1.21.1.jar, read with javap
2026-10-08; the same reading as tools/player_guide_drops.py): one amount is drawn from `amount` (default 1..1); entries
whose `quantity` (default 1) exceeds it leave the pool; then, while the picked total is below the amount and the pool
is not empty, ONE pass over the pool in order takes the FIRST entry whose roll succeeds (nextFloat() * 100 <
`percentage`, default 100) and adds its quantity; a pass with no success adds 1. After a success the entry leaves once
chosen `maxSelectableTimes` (default 1) times, and every entry whose quantity exceeds what is left leaves too. So a 100%
entry at the head of an amount-1 table takes every defeat and nothing after it is ever rolled (Litleo).

WHAT AN OVERRIDE DOES (SpeciesAdditions.class and its AdditionParameterAdapter, javap 2026-10-08): every top-level key
of a species_additions file but `target` names a mutable property of Species; the value is deserialised whole and SET
with the property's setter, except `forms` and `evolutions`, which are added to the existing collection. `drops` is a
var (Species.class: `private DropTable drops`, not final), so a `drops` addition REPLACES the species table outright.
It sets Species.drops only: a form that carries its own table keeps it (FormData.getDrops returns `_drops`, falling back
to the species table only when the form has none), so forms without their own table follow the fix, as they followed
upstream's table.

WHERE OUR FILE GOES, and why two kinds:
  - a table that upstream sets through a species_additions FILE (the COBBLEVERSE datapack's 24): ours is that file, at
    the SAME resource path, so the datapack loader hands Cobblemon one file for that id and ours wins by pack order
    (this pack is world-local, above the global COBBLEVERSE pack, the reason the spawn packs are world-local). Two
    files at different paths both setting `drops` would be applied in the order of Cobblemon's addition map, which
    nothing here controls. Every other key of upstream's file (baseScale, hitbox, behaviour, ...) is copied from the
    datapack at build time, unchanged, so the overlay replaces the drops and nothing else.
  - a table that comes from a SPECIES file (the Cobblemon jar's): ours is a new data/cobblers/species_additions file
    carrying `target` and `drops` only, provided nothing else sets that species' drops (the sweep says so if it does).
  - a species file that TWO MODS ship with different drops (Kyurem: Cobblemon and Mega Showdown), the sweep's
    `ambiguous`: which file loads is mod load order, which nothing here controls. The same new species_additions file
    settles it, because an addition is applied after the species files load, whichever won; the record names every
    mod's table as read (`upstream.contested`) and `check` compares each with the jars. Only the drops are settled:
    the mods' other differing keys are still the loader's.
Each fix records upstream's table as it was read; `check` fails when upstream no longer matches, so a fix never
silently overrides a table upstream has since changed.

NOT folded into tools/mythical_starters.py, the one other species_additions emitter: that pack adds FORMS (which
append) for six starters and is coupled to the starter screen's config; this one REPLACES tables, carries copies of
upstream files, and has its own sweep. Same layer (world-local), different job.

What is NOT verified: that the server loads the overlay over COBBLEVERSE's file and drops the fixed items. Valid JSON
and the jar's code read above are the most this tool can claim; a defeat in game is the proof.
"""
from __future__ import annotations

import argparse
import functools
import json
import re
import shutil
import sys
import zipfile
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

DATA = ROOT / "data" / "drop_fixes.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_drop_fixes"
NS = "cobblers"
PACK = "cobblers_drop_fixes"
ENTRY_KEYS = {"item", "percentage", "quantity", "quantityRange", "maxSelectableTimes", "components"}
TABLE_KEYS = {"amount", "entries"}
SPECIES = re.compile(r"data/([^/]+)/species/(?:.+/)?([a-z0-9_]+)\.json")
ADDITION = re.compile(r"data/([^/]+)/species_additions/(?:.+/)?([a-z0-9_]+)\.json")
EPS = 1e-12


# ------------------------------------------------------------------------------------------------ the roll


def _range(v, what):
    if isinstance(v, bool):
        raise ValueError("%s %r is not a range" % (what, v))
    if isinstance(v, (int, float)) and int(v) == v:
        return int(v), int(v)
    if isinstance(v, str):
        m = re.fullmatch(r"\s*(-?\d+)\s*(?:-\s*(-?\d+)\s*)?", v)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2) if m.group(2) is not None else m.group(1))
            if lo <= hi:
                return lo, hi
    raise ValueError("%s %r is not a range" % (what, v))


def parse(table):
    """(amount (lo, hi), [entry]) with the jar's defaults filled in. Raises ValueError on a shape it cannot read."""
    if not isinstance(table, dict):
        raise ValueError("a drop table that is not an object: %r" % (table,))
    extra = set(table) - TABLE_KEYS
    if extra:
        raise ValueError("unknown drop table keys %s" % sorted(extra))
    lo, hi = _range(table.get("amount", 1), "amount")
    ents = []
    for e in table.get("entries") or []:
        if not isinstance(e, dict) or "item" not in e:
            raise ValueError("an entry with no item: %r" % (e,))
        extra = set(e) - ENTRY_KEYS
        if extra:
            raise ValueError("entry %s: unknown keys %s" % (e.get("item"), sorted(extra)))
        q = int(e.get("quantity", 1))
        ents.append({"item": e["item"], "p": float(e.get("percentage", 100.0)), "q": q,
                     "max": int(e.get("maxSelectableTimes", 1)),
                     "stack": _range(e["quantityRange"], "quantityRange") if "quantityRange" in e else (q, q)})
    return (lo, hi), ents


def chosen(table):
    """{frozenset of entry indices: chance exactly those entries are chosen in one defeat}, exact over DropTable.getDrops
    (module docstring), averaged over the amount range. maxSelectableTimes above 1 is followed (an entry may be chosen
    again; the set records only that it was chosen)."""
    (lo, hi), ents = parse(table)
    n = len(ents)
    p = [min(1.0, max(0.0, e["p"] / 100.0)) for e in ents]
    q = [e["q"] for e in ents]
    mx = [e["max"] for e in ents]

    def one(amt):
        @functools.lru_cache(maxsize=None)
        def go(pool, counts, picked):
            if picked >= amt or not pool:
                return {frozenset(): 1.0}
            out = {}

            def add(prefix, chance, sub):
                for s, c in sub.items():
                    out[prefix | s] = out.get(prefix | s, 0.0) + chance * c
            miss = 1.0
            for i in pool:
                hit = miss * p[i]
                miss *= 1.0 - p[i]
                if hit <= 0:
                    continue
                now = picked + q[i]
                cnt = list(counts)
                cnt[i] += 1
                rest = tuple(j for j in pool if not ((j == i and mx[i] <= cnt[i]) or q[j] > amt - now))
                add(frozenset([i]), hit, go(rest, tuple(cnt), now))
                if miss <= 0:
                    break
            if miss > 0:
                add(frozenset(), miss, go(pool, counts, picked + 1))
            return out
        start = tuple(i for i in range(n) if q[i] <= amt)
        return go(start, (0,) * n, 0)

    total = {}
    for amt in range(lo, hi + 1):
        for s, c in one(amt).items():
            total[s] = total.get(s, 0.0) + c / (hi - lo + 1)
    return total


def entry_chances(table):
    """[chance each entry is chosen at least once in a defeat], in the table's order."""
    _amount, ents = parse(table)
    sets = chosen(table)
    return [sum(c for s, c in sets.items() if i in s) for i in range(len(ents))]


def item_chances(table):
    """{item: chance a defeat drops at least one}, counting a chosen entry's stack only when it is not empty."""
    _amount, ents = parse(table)
    sets = chosen(table)

    def empty(e):
        lo, hi = e["stack"]
        return (min(hi, 0) - lo + 1) / (hi - lo + 1) if lo <= 0 else 0.0
    out = {}
    for item in dict.fromkeys(e["item"] for e in ents):
        idx = [i for i, e in enumerate(ents) if e["item"] == item]
        ch = 0.0
        for s, c in sets.items():
            if any(i in s for i in idx):
                none = 1.0
                for i in idx:
                    if i in s:
                        none *= empty(ents[i])
                ch += c * (1.0 - none)
        out[item] = ch
    return out


# ------------------------------------------------------------------------------------------------ inputs


def default_inputs():
    """(mods dir, [datapack zips], vanilla jar): the offline server snapshot's mods, the COBBLEVERSE datapacks the
    server loads globally (the DP the drops page reads, and every other zip beside it), the vanilla 1.21.1 jar."""
    import player_guide_battles as PB
    import player_guide_drops as PGD
    jar = PB.find_jar()
    dp = PGD.find_dp()
    zips = [dp] + sorted(p for p in dp.parent.glob("*.zip") if p.name != dp.name)
    return jar.parent, zips, PGD.find_vanilla()


def _zip_files(z, where, depth=0):
    """[(rel, where, json)] for every species / species_additions file in a zip, nested jars included."""
    out = []
    for n in z.namelist():
        if depth == 0 and n.startswith("META-INF/jars/") and n.endswith(".jar"):
            try:
                with zipfile.ZipFile(BytesIO(z.read(n))) as inner:
                    out += _zip_files(inner, "%s!%s" % (where, n), depth + 1)
            except zipfile.BadZipFile:
                pass
            continue
        if SPECIES.fullmatch(n) or ADDITION.fullmatch(n):
            try:
                out.append((n, where, json.loads(z.read(n).decode("utf-8-sig"))))
            except ValueError:
                out.append((n, where, None))
    return out


def our_packs(doc=None, with_fixes=True):
    """{pack name: {rel: json}} for our own species packs, generated in memory from data/, never read from build/
    (a stale build would be swept instead of the data). The mythical starters' forms, and this tool's own pack."""
    import mythical_starters as MS
    packs = {"cobblers_mythical_starters": {r: json.loads(t) for r, t in
                                            MS.files(json.loads(MS.DATA.read_text(encoding="utf-8"))).items()
                                            if r.startswith("data/")}}
    if with_fixes:
        doc = doc if doc is not None else load()
        packs[PACK] = {r: json.loads(t) for r, t in files(doc, upstream_files(doc)).items() if r.startswith("data/")}
    return packs


def layers(mods_dir, zips, ours):
    """[(layer, [(rel, where, json)])] lowest priority first: mod jars (their order among themselves is the loader's
    and is not known here), then the global datapacks, then our world-local packs."""
    mods = []
    for p in sorted(Path(mods_dir).glob("*.jar")):
        with zipfile.ZipFile(p) as z:
            mods += _zip_files(z, p.name)
    out = [("mods", mods)]
    for p in zips:
        with zipfile.ZipFile(p) as z:
            out.append((p.name, _zip_files(z, p.name)))
    for name, fs in ours.items():
        out.append((name, [(r, name, d) for r, d in sorted(fs.items()) if SPECIES.fullmatch(r) or ADDITION.fullmatch(r)]))
    return out


def items_known(mods_dir, zips, vanilla, ours):
    import economy_audit as EA
    j = EA.Jars()
    with zipfile.ZipFile(vanilla) as z:
        j.scan_zip(z, Path(vanilla).name)
    for p in sorted(Path(mods_dir).glob("*.jar")):
        with zipfile.ZipFile(p) as z:
            j.scan_zip(z, p.name)
    for p in zips:
        with zipfile.ZipFile(p) as z:
            j.scan_zip(z, p.name)
    return j.items


# ------------------------------------------------------------------------------------------------ the model


def effective(layer_list):
    """(tables, notes). tables: [{species, form, table, where, rel}] -- every drop table the game can roll: each
    species' table after species files and `drops` additions are applied, and each form's own table. notes: what this
    reading cannot settle (two mods shipping one path with different drops; two addition files setting one species'
    drops), each a fault of its own kind."""
    files, notes = {}, []
    for layer, fs in layer_list:
        for rel, where, d in fs:
            if layer == "mods" and rel in files and files[rel][0] == "mods":
                a, b = files[rel][2], d
                if isinstance(a, dict) and isinstance(b, dict) and a.get("drops") != b.get("drops"):
                    # `item` carries the contested file, so a fix names it as "ambiguous <rel>"
                    notes.append({"kind": "ambiguous", "species": SPECIES.fullmatch(rel).group(2)
                                  if SPECIES.fullmatch(rel) else rel, "rel": rel, "item": rel,
                                  "detail": "%s and %s both ship %s with different drops; which mod wins is the "
                                            "loader's order" % (files[rel][1], where, rel)})
            files[rel] = (layer, where, d)
    species, setters, added_forms = {}, {}, {}
    for rel, (layer, where, d) in sorted(files.items()):
        if not isinstance(d, dict):
            notes.append({"kind": "unreadable", "species": rel, "rel": rel, "detail": "%s: not JSON" % where})
            continue
        m = SPECIES.fullmatch(rel)
        if m:
            species[m.group(2)] = {"rel": rel, "where": where, "drops": d.get("drops"),
                                   "forms": [(f.get("name"), f["drops"]) for f in d.get("forms") or []
                                             if isinstance(f, dict) and "drops" in f]}
            continue
        m = ADDITION.fullmatch(rel)
        stem = str(d.get("target", "")).split(":")[-1]
        if "drops" in d:
            setters.setdefault(stem, []).append((rel, where, d["drops"]))
        for f in d.get("forms") or []:
            if isinstance(f, dict) and "drops" in f:
                added_forms.setdefault(stem, []).append((f.get("name"), f["drops"], rel, where))
    # Two mods shipping one species file with different top-level drops is settled by an addition that sets `drops`:
    # it replaces the species table after whichever file loaded, so load order no longer decides the drops.
    notes = [n for n in notes if not (n["kind"] == "ambiguous" and SPECIES.fullmatch(n["rel"])
                                      and n["species"] in setters)]
    tables = []
    for stem in sorted(set(species) | set(setters) | set(added_forms)):
        sp = species.get(stem)
        if sp is None:
            notes.append({"kind": "orphan", "species": stem, "rel": (setters.get(stem) or added_forms[stem])[0][-2],
                          "detail": "an addition targets %s and no species file exists" % stem})
            continue
        top = (sp["rel"], sp["where"], sp["drops"])
        if stem in setters:
            if len(setters[stem]) > 1:
                notes.append({"kind": "contested", "species": stem, "rel": setters[stem][-1][0],
                              "detail": "%d addition files set %s's drops (%s); which applies last is the order of "
                                        "Cobblemon's addition map" % (len(setters[stem]), stem,
                                                                      ", ".join("%s in %s" % s[:2] for s in setters[stem]))})
            top = setters[stem][-1]
        if top[2] is not None:
            tables.append({"species": stem, "form": None, "table": top[2], "where": top[1], "rel": top[0]})
        for name, t in sp["forms"]:
            tables.append({"species": stem, "form": name, "table": t, "where": sp["where"], "rel": sp["rel"]})
        for name, t, rel, where in added_forms.get(stem, []):
            tables.append({"species": stem, "form": name, "table": t, "where": where, "rel": rel})
    return tables, notes


def faults(tables, items, notes=()):
    """[{kind, species, form, entry, item, rel, where, detail}] for every missing item and unreachable entry."""
    out = []
    for t in tables:
        base = {"species": t["species"], "form": t["form"], "rel": t["rel"], "where": t["where"]}
        try:
            _amount, ents = parse(t["table"])
            ch = entry_chances(t["table"])
        except ValueError as e:
            out.append(dict(base, kind="unreadable", entry=None, item=None, detail=str(e)))
            continue
        for i, e in enumerate(ents):
            if e["item"] not in items:
                out.append(dict(base, kind="missing_item", entry=i, item=e["item"],
                                detail="entry %d names %s, which no installed jar or datapack registers"
                                       % (i, e["item"])))
            if ch[i] <= EPS and e["p"] > 0:
                out.append(dict(base, kind="unreachable", entry=i, item=e["item"],
                                detail="entry %d (%s at %g%%) is never chosen: the roll stops before it"
                                       % (i, e["item"], e["p"])))
    for n in notes:
        out.append(dict({"form": None, "entry": None, "item": None, "where": ""}, **n))
    return out


def key(f):
    """The identity a fault is fixed or held open by: species, form, kind, item."""
    return (f["species"], f.get("form"), f["kind"], f.get("item"))


# ------------------------------------------------------------------------------------------------ the data and pack


def load(path=DATA):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def upstream_files(doc, zips=None):
    """{rel: upstream file json} for every fix that overlays an upstream species_additions file, read from the
    datapack zip it names (looked up among the global datapacks)."""
    if zips is None:
        zips = default_inputs()[1]
    by_name = {Path(z).name: Path(z) for z in zips}
    out = {}
    for fx in doc["fixes"]:
        up = fx["upstream"]
        if up["via"] != "species_additions":
            continue
        z = by_name.get(up["pack"])
        if z is None:
            raise SystemExit("%s: upstream pack %s is not among the datapacks %s" % (fx["species"], up["pack"],
                                                                                   sorted(by_name)))
        with zipfile.ZipFile(z) as zz:
            out[up["path"]] = json.loads(zz.read(up["path"]).decode("utf-8-sig"))
    return out


def files(doc, upstream):
    """{rel: text} of the pack."""
    out = {}
    for fx in doc["fixes"]:
        up = fx["upstream"]
        if up["via"] == "species_additions":
            d = dict(upstream[up["path"]])
            d["drops"] = fx["drops"]
            rel = up["path"]
        else:
            d = {"target": "cobblemon:%s" % fx["species"], "drops": fx["drops"]}
            rel = "data/%s/species_additions/drop_fix_%s.json" % (NS, fx["species"])
        out[rel] = json.dumps(d, indent=2) + "\n"
    out["pack.mcmeta"] = json.dumps({"pack": {"pack_format": 48, "description":
                                     "Cobblers: %d species drop tables fixed (tools/drop_fixes.py)" % len(doc["fixes"])}},
                                    indent=2) + "\n"
    return out


def check(doc, upstream=None, items=None, upstream_tables=None, mod_files=None):
    """[problem] for the data: each fix's recorded upstream is what upstream ships, its items exist, each entry
    reaches the rate its `intent` states, and the faults it says it fixes are gone from its table. mod_files
    (mod_species()) lets a `contested` record be compared with every mod that ships the file; without it the
    effective table must be one of the recorded ones."""
    problems = []
    if doc.get("schema") != "cobblers.drop_fixes/1":
        problems.append("schema is %r" % doc.get("schema"))
    seen = set()
    for fx in doc["fixes"]:
        sp = fx["species"]
        if sp in seen:
            problems.append("%s: fixed twice" % sp)
        seen.add(sp)
        for k in ("upstream", "drops", "why", "fixes", "intent"):
            if k not in fx:
                problems.append("%s: no %s" % (sp, k))
        if any(k not in fx for k in ("upstream", "drops", "intent")):
            continue
        up = fx["upstream"]
        if upstream is not None and up["via"] == "species_additions":
            got = (upstream.get(up["path"]) or {}).get("drops")
            if got != up["drops"]:
                problems.append("%s: upstream %s in %s now carries %s, not the recorded %s: re-read the fix"
                                % (sp, up["path"], up["pack"], json.dumps(got), json.dumps(up["drops"])))
            if (upstream.get(up["path"]) or {}).get("target", "").split(":")[-1] != sp:
                problems.append("%s: %s targets %r" % (sp, up["path"], (upstream.get(up["path"]) or {}).get("target")))
        contested = up.get("contested") or []
        if mod_files is not None and up["via"] == "species" and contested:
            # every mod shipping this species file, as read now, against every one recorded
            want = {up["pack"]: (up["path"], up["drops"])}
            want.update({c["pack"]: (c["path"], c["drops"]) for c in contested})
            got = mod_files.get(sp, {})
            if got != want:
                problems.append("%s: the mods shipping its species file now carry %s, not the recorded %s: re-read "
                                "the fix" % (sp, json.dumps(got, sort_keys=True), json.dumps(want, sort_keys=True)))
        elif upstream_tables is not None and up["via"] == "species":
            got = upstream_tables.get(sp)
            # a contested file: whichever mod the reading above put on top must be one of those recorded
            allowed = [up["drops"]] + [c["drops"] for c in contested]
            if got not in allowed:
                problems.append("%s: upstream's species table is now %s, not the recorded %s"
                                % (sp, json.dumps(got), json.dumps(up["drops"])))
        try:
            ic = item_chances(fx["drops"])
            ec = entry_chances(fx["drops"])
            _a, ents = parse(fx["drops"])
        except ValueError as e:
            problems.append("%s: fixed table unreadable: %s" % (sp, e))
            continue
        for i, e in enumerate(ents):
            if items is not None and e["item"] not in items:
                problems.append("%s: fixed entry %s is not a registered item" % (sp, e["item"]))
            if ec[i] <= EPS:
                problems.append("%s: fixed entry %d (%s) is never chosen" % (sp, i, e["item"]))
        intent = fx["intent"]
        if set(intent) != set(ic):
            problems.append("%s: intent names %s, the table %s" % (sp, sorted(intent), sorted(ic)))
        for item, want in intent.items():
            got = ic.get(item, 0.0) * 100.0
            if abs(got - float(want)) > 0.01:
                problems.append("%s: %s drops at %.4f%% a defeat, intent %s%%" % (sp, item, got, want))
    for o in doc.get("open", []):
        for k in ("species", "kind", "item", "why"):
            if k not in o:
                problems.append("open %s: no %s" % (o.get("species"), k))
    return problems


def build(doc, upstream):
    if OUT.exists():
        shutil.rmtree(OUT)
    n = 0
    for rel, text in files(doc, upstream).items():
        p = OUT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
        n += 1
    return n


def sweep(doc=None, with_fixes=True, inputs=None):
    """(all faults, unaccounted faults): unaccounted = not held open in data/drop_fixes.json."""
    doc = doc if doc is not None else load()
    mods_dir, zips, vanilla = inputs or default_inputs()
    ours = our_packs(doc, with_fixes)
    tables, notes = effective(layers(mods_dir, zips, ours))
    fs = faults(tables, items_known(mods_dir, zips, vanilla, ours), notes)
    held = {(o["species"], o.get("form"), o["kind"], o.get("item")) for o in doc.get("open", [])}
    if not with_fixes:
        # upstream's faults, accounted for when a record says it fixes them (the fix is not applied in this mode)
        held |= fixed_keys(doc)
    return fs, [f for f in fs if key(f) not in held]


def fixed_keys(doc):
    """The fault identities the fixes say they remove: "<kind> <item>" on the species table (form None)."""
    out = set()
    for fx in doc["fixes"]:
        for s in fx.get("fixes", []):
            kind, _, item = s.partition(" ")
            out.add((fx["species"], None, kind, item or None))
    return out


def mod_species(mods_dir):
    """{species: {jar name: (rel, its top-level drops or None)}} for every species file a mod jar ships, nested jars
    named jar!inner. Several jars per species is the load-order case a `contested` fix records."""
    out = {}
    for _layer, fs in layers(mods_dir, [], {}):
        for rel, where, d in fs:
            m = SPECIES.fullmatch(rel)
            if m and isinstance(d, dict):
                out.setdefault(m.group(2), {})[where] = (rel, d.get("drops"))
    return out


def species_tables(mods_dir, zips):
    """{species: upstream's effective species-level table} without our packs, for `check`'s species-file fixes."""
    tables, _notes = effective(layers(mods_dir, zips, {}))
    return {t["species"]: t["table"] for t in tables if t["form"] is None}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=("sweep", "check", "build"))
    ap.add_argument("--upstream", action="store_true", help="sweep: without our fixes")
    ap.add_argument("--json", help="sweep: write every fault to this file")
    a = ap.parse_args(argv)
    doc = load()
    if a.cmd == "sweep":
        fs, bad = sweep(doc, with_fixes=not a.upstream)
        if a.json:
            Path(a.json).write_text(json.dumps(fs, indent=1), encoding="utf-8")
        fixed = fixed_keys(doc) if a.upstream else set()
        for f in fs:
            print("%s %s%s: %s%s" % ("FAULT" if f in bad else "fixed" if key(f) in fixed else "open ", f["species"],
                                     " (%s)" % f["form"] if f.get("form") else "", f["detail"],
                                     "  [%s]" % f["where"] if f.get("where") else ""))
        print("drop_fixes sweep%s: %d fault(s), %d not fixed or held open" % (" (upstream only)" if a.upstream else "",
                                                                             len(fs), len(bad)))
        return 1 if bad else 0
    mods_dir, zips, vanilla = default_inputs()
    upstream = upstream_files(doc, zips)
    items = items_known(mods_dir, zips, vanilla, {})
    problems = check(doc, upstream, items, species_tables(mods_dir, zips), mod_species(mods_dir))
    for p in problems:
        print("PROBLEM", p)
    if problems:
        print("drop_fixes check: %d problem(s)" % len(problems))
        return 1
    if a.cmd == "check":
        print("drop_fixes check: ok: %d fixes, %d held open" % (len(doc["fixes"]), len(doc.get("open", []))))
        return 0
    n = build(doc, upstream)
    print("drop_fixes build: %d files -> %s (%d fixes)" % (n, OUT, len(doc["fixes"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

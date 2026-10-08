#!/usr/bin/env python
"""Does every area of the COMPILED spawn pack have a rare table, an ultra-rare table, a heart and enough species?

The owner, 2026-10-05: "every area should have a rare, ultra rare, and boss table. need to see a little more variety
... [a lake] should feel like a pokemon lake deep in life". Boss was approved to mean an encounter HEART per area
(docs/mechanics/ENCOUNTER_DESIGN.md section 10).

Written by the test author, not by the sessions building the redesign. Independence: it reads ONLY the compiled pack
(build/datapacks/cobblers_spawns/data/<ns>/spawn_pool_world/<kind>/<area>.json) with its own parsing. It never imports
tools/compile_spawns.py or tools/build_encounters.py and never reads data/encounter_design.json or data/spawns.json, so
what a generator meant to emit is never the expectation. Heart entries are recognised by the compiled id contract the
design doc states (section 10: "ids `<sub>_h<n>_<species>`"), not by any generator function.

AREAS. One compiled file is one area: subregions/<id> (a sub-region), routes/<id> (a corridor), marine/<band>,
waterways/<id>. A kind this file does not know fails closed. A species is the first token of `pokemon` (a form is
the same species: "vulpix alolan" counts as vulpix). Water positions are surface, submerged and seafloor.

THE CHECKS, and where each number comes from (none was tuned to the data):

  1. tiers      rare bucket >= 2 species and ultra-rare >= 1, counted on the BASE table (heart entries excluded: the
                owner lists the heart as a third table, so a heart's rare row covering a ninth of the place does not
                give the place a rare table). Derivation: "every area should have a rare, ultra rare" -> each bucket
                present (>= 1). Rare >= 2 from "a rare ... table" plus "more variety": a rare draw that can only ever
                be one species is a fixed result, not a table. The same reading would ask 2 of ultra-rare; it is NOT
                applied, because the owner's words give "have" for ultra-rare and nothing more -- the weaker reading,
                stated rather than chosen to pass.
  2. heart      every sub-region, marine band and waterway carries >= 1 heart entry ("every area should have a ...
                boss table"; boss = heart, approved). Each heart box must be covered by the union of the same area's
                base boxes ("Its entries ADD to the base table inside the heart", section 10 -- so a heart outside its
                base table is outside its area), and lie more than 128 blocks (Chebyshev gap) from every route box in
                the pack (section 10, confirmed by the owner 2026-10-02: "128 blocks from a path"; no heart cell within
                128 blocks of a route corridor box). ROUTES ARE NOT ASKED FOR A HEART: section 10, owner-confirmed,
                "A route corridor never carries heart content" -- a route file carrying a heart entry FAILS instead.
                If the owner rules that a corridor is an "area" that needs a boss, that rule replaces this one.
  3. floor      every sub-region and route holds >= 12 distinct species (any position); every water body holds >= 8
                distinct species in water positions. A water body is every marine band and waterway, and every
                sub-region whose id names a body of water (WATER_WORDS: lake, waters, river, pond, creek(s), tarn --
                the owner's "lake" and the brief's "lake/river/waters", with pond/creek/tarn as the same thing by
                another name). Derivation: "a little more variety" gives no number, so the floor is section 4's
                CEILING made the floor: "a table holds 3-6 land families and, where it has water, 2-4 water families",
                and section 3's escalation shows a family as two stages once maturity > 0, so 6 x 2 = 12 land and
                4 x 2 = 8 water. The brief proposed 10 for water; 10 is NOT derivable from the doc or the owner's words
                and is not used. Known conflict, reported not tuned away: at tier 1 maturity is 0 (one stage per
                family), so 12 species on a tier-1 table needs more than section 4's six families.
  4. rarity     no species is rare-or-ultra-rare-ONLY (every compiled entry of it in that area is rare or ultra-rare)
                in more than half of all areas. Derivation: a majority is the smallest share at which "rare" is what a
                player meets in most places; past it, rarity means nothing (the brief's "rarity must mean something").
  6. alpha      every heart entry's `pokemon` carries the PokemonProperties token alpha=true, and no other entry in any
                area (base, Mega den line, route) carries an alpha key at all. Source: section 10, "The bosses are
                alphas" (the owner, 2026-10-05: "the boss pokemon are alphas"; "Every heart entry is a native alpha ...
                `"<species> alpha=true"`"). Exact token, no threshold.
  7. local      every area holding a heart holds at least one EXACT local in it: a heart `pokemon` string, its alpha
                token removed, equal to the `pokemon` string of one of the same area's non-heart entries (so a
                regional form is not a local of its plain species). Source: section 10, "Every heart holds one of its
                own place's Pokemon" (the owner, 2026-10-05: "it should sometimes be the pokemon in the area as well").
                Routes are skipped: a route carrying a heart already fails check 2.
  5. report     derived/spawn_tiers/areas.tsv (one row per area, its counts and failures) and failures.txt; stdout is
                one summary line plus one line per failing area and per rarity failure.
                Measured on the 2026-10-04 pack (compiled in the main session's checkout, 76 areas): 76 failing,
                239 failures, 0 rarity; 1 area with an ultra-rare; 28 hearts, all inside their base boxes, nearest
                129 blocks from a route box (section 10 records 129); sub-region mean 7.9 species by first token.

NOT COVERED (validity is not runtime behaviour): whether Cobblemon draws these buckets at these rates in game
(Cobbleverse's bucket weights are relayed in section 4, not measured here); whether a heart's minY or radius is the one
authored; the heart's 1/9 area share and above-cap share (section 10; a summit heart covers its whole sub-region in
plan and is narrowed by minY, which a box check cannot weigh); the habitat pools (Victory Road's eleven, not compiled
as spawn_pool_world areas); and whether a heart box lies inside the sub-region POLYGON (data/regions.json) -- only that
it lies inside the area's own compiled base boxes. Checks 6-7 prove the compiled STRING, not the alpha: that Cobblemon
spawns an alpha from it, and at what level (the jar's AlphaLevelMatchingSensor re-levels a wild alpha near a player,
section 10), need a running server. A local counts by being anywhere in the area's non-heart entries, Mega den lines
included.

  python tools/spawn_tiers_audit.py                       # audit build/datapacks/cobblers_spawns
  python tools/spawn_tiers_audit.py --pack <dir> --out <dir>
Exit 0: every area passes. Exit 1: a failure (listed). Exit 2: no compiled pack to read.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PACK = ROOT / "build" / "datapacks" / "cobblers_spawns"
DEFAULT_OUT = ROOT / "derived" / "spawn_tiers"

RARE_MIN = 2
ULTRA_MIN = 1
HEART_MIN = 1
HEART_PATH_GAP = 128          # a heart box's Chebyshev gap to every route box must EXCEED this
LAND_FLOOR = 12               # 6 land families x 2 stages (section 4 ceiling, section 3 escalation)
WATER_FLOOR = 8               # 4 water families x 2 stages (same rule)
RARE_ONLY_SHARE = 0.5         # a species rare-only in MORE than this share of areas fails

BUCKETS = ("common", "uncommon", "rare", "ultra-rare")
RARE_BUCKETS = ("rare", "ultra-rare")
WATER_POSITIONS = ("surface", "submerged", "seafloor")
KINDS = ("subregions", "routes", "marine", "waterways")
WATER_WORDS = ("lake", "waters", "river", "pond", "creek", "creeks", "tarn")


def species_of(pokemon):
    return str(pokemon).strip().split()[0].lower()


ALPHA_KEYS = ("alpha", "is_alpha")   # PokemonProperties$Companion registers both (section 10)


def alpha_tokens(pokemon):
    """The tokens of a pokemon string that set an alpha key, with or without a value ("alpha=true", "is_alpha")."""
    return [t for t in str(pokemon).split()[1:] if t.split("=", 1)[0].lower() in ALPHA_KEYS]


def without_alpha(pokemon):
    """The pokemon string less its alpha tokens: "druddigon alpha=true" -> "druddigon"."""
    toks = str(pokemon).split()
    return " ".join(toks[:1] + [t for t in toks[1:] if t.split("=", 1)[0].lower() not in ALPHA_KEYS]).lower()


def box_of(spawn):
    c = spawn.get("condition") or {}
    if all(k in c for k in ("minX", "maxX", "minZ", "maxZ")):
        return (int(c["minX"]), int(c["maxX"]), int(c["minZ"]), int(c["maxZ"]))
    return None


def gap(a, b):
    """Chebyshev gap between two inclusive boxes, 0 where they overlap or touch."""
    return max(0, a[0] - b[1], b[0] - a[1], a[2] - b[3], b[2] - a[3])


def covered(box, cover):
    """True when the union of `cover` boxes covers every block of `box` (inclusive integer boxes)."""
    near = [c for c in cover if not (c[1] < box[0] or c[0] > box[1] or c[3] < box[2] or c[2] > box[3])]
    if not near:
        return False
    xs = sorted({box[0], box[1] + 1} | {v for c in near for v in (c[0], c[1] + 1) if box[0] < v <= box[1]})
    zs = sorted({box[2], box[3] + 1} | {v for c in near for v in (c[2], c[3] + 1) if box[2] < v <= box[3]})
    for i in range(len(xs) - 1):
        for j in range(len(zs) - 1):
            x, z = xs[i], zs[j]
            if not any(c[0] <= x <= c[1] and c[2] <= z <= c[3] for c in near):
                return False
    return True


def is_water_body(kind, area):
    if kind in ("marine", "waterways"):
        return True
    return kind == "subregions" and any(w in area.split("_") for w in WATER_WORDS)


def load(pack):
    """{(kind, area): [spawn]} from every data/<ns>/spawn_pool_world/<kind>/<area>.json under the pack."""
    areas = {}
    for f in sorted(Path(pack).glob("data/*/spawn_pool_world/**/*.json")):
        rel = f.relative_to(Path(pack)).parts
        kind = rel[3] if len(rel) > 4 else "(top level)"
        doc = json.loads(f.read_text(encoding="utf-8"))
        areas[(kind, f.stem)] = list(doc.get("spawns") or [])
    return areas


def audit(areas):
    """(rows, failures): one row per area, and failure strings '<kind>/<area>: <what>'."""
    route_boxes = [b for (kind, _), sp in areas.items() if kind == "routes" for b in (box_of(s) for s in sp) if b]
    rows, failures = [], []
    rare_only = defaultdict(set)
    for (kind, area), spawns in sorted(areas.items()):
        name = "%s/%s" % (kind, area)
        fails = []
        if kind not in KINDS:
            fails.append("unknown area kind %r: this audit does not know how to grade it" % kind)
        heart_pat = re.compile(r"^%s_h\d+_" % re.escape(area))
        hearts = [s for s in spawns if heart_pat.match(str(s.get("id", "")))]
        base = [s for s in spawns if not heart_pat.match(str(s.get("id", "")))]
        bad_buckets = sorted({str(s.get("bucket")) for s in spawns if s.get("bucket") not in BUCKETS})
        if bad_buckets:
            fails.append("unknown bucket(s) %s" % bad_buckets)
        sp_all = {species_of(s["pokemon"]) for s in spawns}
        sp_water = {species_of(s["pokemon"]) for s in spawns if s.get("spawnablePositionType") in WATER_POSITIONS}
        rare = {species_of(s["pokemon"]) for s in base if s.get("bucket") == "rare"}
        ultra = {species_of(s["pokemon"]) for s in base if s.get("bucket") == "ultra-rare"}
        by_sp = defaultdict(set)
        for s in spawns:
            by_sp[species_of(s["pokemon"])].add(s.get("bucket"))
        for sp, bk in by_sp.items():
            if bk and bk <= set(RARE_BUCKETS):
                rare_only[sp].add(name)
        # 1. tiers
        if len(rare) < RARE_MIN:
            fails.append("rare table holds %d species, needs >= %d" % (len(rare), RARE_MIN))
        if len(ultra) < ULTRA_MIN:
            fails.append("ultra-rare table holds %d species, needs >= %d" % (len(ultra), ULTRA_MIN))
        # 2. heart
        hboxes = sorted({b for b in (box_of(s) for s in hearts) if b})
        bboxes = sorted({b for b in (box_of(s) for s in base) if b})
        outside = [b for b in hboxes if not covered(b, bboxes)]
        min_gap = min((gap(h, r) for h in hboxes for r in route_boxes), default=None)
        if kind == "routes":
            if hearts:
                fails.append("a route carries %d heart entries (section 10: never)" % len(hearts))
        else:
            if len({species_of(s["pokemon"]) for s in hearts}) < HEART_MIN:
                fails.append("no heart (boss) entries")
            elif not hboxes:
                fails.append("heart entries carry no box")
            if outside:
                fails.append("%d of %d heart boxes outside the area's base boxes, e.g. %s" % (len(outside), len(hboxes), outside[0]))
            if min_gap is not None and min_gap <= HEART_PATH_GAP:
                fails.append("heart box %d blocks from a route box, needs > %d" % (min_gap, HEART_PATH_GAP))
        # 6. alpha: every heart entry, and nothing else
        not_alpha = sorted({str(s["pokemon"]) for s in hearts
                            if [t.lower() for t in alpha_tokens(s["pokemon"])] != ["alpha=true"]})
        if not_alpha:
            fails.append("%d heart species not alpha=true (section 10: every heart entry is a native alpha), e.g. %r"
                         % (len(not_alpha), not_alpha[0]))
        stray = sorted({str(s["pokemon"]) for s in base if alpha_tokens(s["pokemon"])})
        if stray:
            fails.append("%d non-heart species carry an alpha key (section 10: only a heart's), e.g. %r" % (len(stray), stray[0]))
        # 7. local: a heart holds one of its own place's Pokemon
        if hearts and kind != "routes":
            local = {without_alpha(s["pokemon"]) for s in hearts} & {str(s["pokemon"]).lower() for s in base}
            if not local:
                fails.append("heart holds no exact local (none of its species is in the area's own non-heart "
                             "entries; section 10: every heart holds one of its own place's Pokemon)")
        # 3. floor
        water = is_water_body(kind, area)
        if kind in ("subregions", "routes") and len(sp_all) < LAND_FLOOR:
            fails.append("%d species, needs >= %d" % (len(sp_all), LAND_FLOOR))
        if water and len(sp_water) < WATER_FLOOR:
            fails.append("%d water species, needs >= %d (a water body)" % (len(sp_water), WATER_FLOOR))
        rows.append({"area": name, "kind": kind, "water_body": water, "species": len(sp_all),
                     "water_species": len(sp_water), "rare": len(rare), "ultra_rare": len(ultra),
                     "heart_species": len({species_of(s["pokemon"]) for s in hearts}), "heart_boxes": len(hboxes),
                     "heart_outside": len(outside), "heart_route_gap": "" if min_gap is None else min_gap,
                     "failures": fails})
        failures.extend("%s: %s" % (name, f) for f in fails)
    # 4. rarity
    n = len(areas)
    for sp, where in sorted(rare_only.items()):
        if n and len(where) > RARE_ONLY_SHARE * n:
            failures.append("species %s: rare-or-ultra-rare only in %d of %d areas (more than half)" % (sp, len(where), n))
    return rows, failures


COLUMNS = ("area", "kind", "water_body", "species", "water_species", "rare", "ultra_rare", "heart_species",
           "heart_boxes", "heart_outside", "heart_route_gap", "failures")


def write(rows, failures, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    lines = ["\t".join(COLUMNS)]
    for r in rows:
        lines.append("\t".join("; ".join(r[c]) if c == "failures" else str(r[c]) for c in COLUMNS))
    (out / "areas.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    (out / "failures.txt").write_text("".join(f + "\n" for f in failures), encoding="utf-8", newline="\n")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--pack", default=str(DEFAULT_PACK))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    a = p.parse_args(argv)
    if not any(Path(a.pack).glob("data/*/spawn_pool_world")):
        print("spawn_tiers_audit: no compiled pack at %s (run tools/compile_spawns.py first)" % a.pack)
        return 2
    areas = load(a.pack)
    rows, failures = audit(areas)
    write(rows, failures, a.out)
    bad = sum(1 for r in rows if r["failures"])
    print("spawn_tiers_audit: %d areas, %d failing, %d failures (%d rarity); table %s"
          % (len(rows), bad, len(failures), sum(1 for f in failures if f.startswith("species ")),
             Path(a.out) / "areas.tsv"))
    # one line per failing area (every failure is in failures.txt), then each rarity failure
    for r in rows:
        if r["failures"]:
            print("FAIL %s: %s" % (r["area"], "; ".join(r["failures"])))
    for f in failures:
        if f.startswith("species "):
            print("FAIL", f)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

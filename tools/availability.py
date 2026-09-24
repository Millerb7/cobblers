#!/usr/bin/env python
"""What a player can actually have caught before each gym, over EVERY pool the campaign compiles.

docs/story/AVAILABILITY.md used to be written by hand over the curated route compilation alone. That omission was
not cosmetic: it hid the one waterway pool, which crosses Route 3 carrying Wooper, Quagsire and Clodsire -- three
Ground families -- and so produced the conclusion that Gym 3 had exactly one Ground answer and was structurally
thin. It has none of that authority now; this tool generates the document from the compiled pools.

The pools, and how each one is placed on the progression:

  routes      route_01..route_08 are walked to reach gyms 1..8, so route N's species are available from gym N.
              victory_road is after gym 8.
  subregions  spatial, in three tiers measured as the shortest gap between the pool's spawn boxes and the
              route's. ON THE CORRIDOR is a gap of 0. WITHIN SIMULATION DISTANCE is 1 to 128: Minecraft loads
              and ticks entities out to 10 chunks, so those Pokemon are rendered in front of a player walking the
              route whether or not they leave it. Both are assigned to the earliest gym whose route they are near.
              A DETOUR is over 128: still reachable, but the player has to decide to go, and nothing gates when,
              so those are listed separately with their nearest route instead of being assigned to a gym.
              The measured distribution justifies the cut: 24 pools touch a corridor, 9 more are within 128, and
              then there is nothing until 209, after which 27 pools sit over 256 away.
  waterways   the same spatial rule. There is one, mt_clay_outflow, 57 blocks off Route 3 at its closest.
  habitats    NOT placed by geography. A habitat pool only exists where a Cobblemon Habitat Block stands, and
              data/habitat_blocks.json places none, so every habitat pool is unreachable today. They are listed
              with that status rather than folded into the tables.

Not covered here, and it is a large hole: the PACK's own inherited pools. data/spawn_suppression.json retains
upstream defaults in "unauthored caves" and off-route wilderness, and the bounded-suppression override pack is not
installed, so Cobblemon's and COBBLEVERSE's own spawns are live everywhere we have not authored over. Measured
2026-09-24: 2,662 readable spawn_pool_world files carrying 5,850 underground-only details. Those are not ordered
by route and cannot be, so they are summarised at the foot of the document and not in the per-gym tables.

Types come from the Cobblemon 1.8 jar, not from a table written here.

  python tools/availability.py                 # print
  python tools/availability.py --write         # regenerate docs/story/AVAILABILITY.md
  python tools/availability.py --margin 32     # how close to a route corridor counts as reachable
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
PACK = ROOT / "build" / "datapacks" / "cobblers_spawns"
POOLS = PACK / "data" / "cobblers" / "spawn_pool_world"
HABITAT_POOLS = PACK / "data" / "cobblers" / "habitat_pools"
BLOCKS = ROOT / "data" / "habitat_blocks.json"
OUT = ROOT / "docs" / "story" / "AVAILABILITY.md"
JSON_OUT = ROOT / "derived" / "availability.json"

CAPS = {1: 20, 2: 25, 3: 30, 4: 35, 5: 40, 6: 45, 7: 50, 8: 55}

GYMS = {1: ("kanto_brock", "Rock"), 2: ("kanto_misty", "Water"), 3: ("kanto_ltsurge", "Electric"),
        4: ("kanto_erika", "Grass"), 5: ("kanto_koga", "Poison"), 6: ("kanto_sabrina", "Psychic"),
        7: ("kanto_blaine", "Fire"), 8: ("kanto_giovanni", "Ground")}

WORLD_READS = set()


class AvailabilityError(Exception):
    pass


def load_pool(path):
    d = json.loads(path.read_text(encoding="utf-8"))
    boxes, rows = [], []
    for s in d.get("spawns") or []:
        c = s.get("condition") or {}
        if "minX" not in c:
            continue
        boxes.append((c["minX"], c["minZ"], c["maxX"], c["maxZ"]))
        lo, hi = parse_level(s.get("level"))
        rows.append({"species": (s.get("pokemon") or "").split()[0].lower(), "lo": lo, "hi": hi,
                     "bucket": s.get("bucket"), "weight": s.get("weight"),
                     "time": c.get("timeRange"), "sky": c.get("canSeeSky")})
    return np.array(boxes, dtype=np.int64) if boxes else np.zeros((0, 4), np.int64), rows


def parse_level(s):
    m = re.match(r"^(\d+)-(\d+)$", str(s or ""))
    if m:
        return int(m.group(1)), int(m.group(2))
    if str(s or "").isdigit():
        return int(s), int(s)
    return 0, 0


def touches(a, b, margin):
    """Do any box of a and any box of b come within `margin`? a and b are (n,4) and (m,4) arrays."""
    if len(a) == 0 or len(b) == 0:
        return False, None
    ax0, az0, ax1, az1 = a[:, 0][:, None], a[:, 1][:, None], a[:, 2][:, None], a[:, 3][:, None]
    bx0, bz0, bx1, bz1 = b[:, 0][None, :], b[:, 1][None, :], b[:, 2][None, :], b[:, 3][None, :]
    dx = np.maximum(0, np.maximum(ax0 - bx1, bx0 - ax1))
    dz = np.maximum(0, np.maximum(az0 - bz1, bz0 - az1))
    gap = np.maximum(dx, dz)
    return bool((gap <= margin).any()), int(gap.min())


def collect(margin):
    if not POOLS.is_dir():
        raise AvailabilityError("no compiled pack at %s: run python tools/compile_spawns.py" % PACK)
    routes, subs, ways = {}, {}, {}
    for p in sorted((POOLS / "routes").glob("*.json")):
        routes[p.stem] = load_pool(p)
    for p in sorted((POOLS / "subregions").glob("*.json")):
        subs[p.stem] = load_pool(p)
    for p in sorted((POOLS / "waterways").glob("*.json")):
        ways[p.stem] = load_pool(p)

    order = [r for r in sorted(routes) if r.startswith("route_")]
    gym_of_route = {r: int(r.split("_")[1]) for r in order}

    # a route's own corridor, cumulative: everything walked to reach gym N
    placed, offroute = {}, {}
    for kind, pools in (("subregion", subs), ("waterway", ways)):
        for name, (boxes, _rows) in pools.items():
            best, best_gap = None, None
            for r in order:
                hit, gap = touches(boxes, routes[r][0], margin)
                if best_gap is None or (gap is not None and gap < best_gap):
                    best_gap = gap
                if hit:
                    best = gym_of_route[r]
                    break
            if best is None:
                near, near_gap = None, None
                for r in order:
                    _h, gap = touches(boxes, routes[r][0], 10 ** 9)
                    if gap is not None and (near_gap is None or gap < near_gap):
                        near, near_gap = r, gap
                offroute[name] = (kind, near, near_gap)
            else:
                placed[name] = (kind, best, best_gap)
    return routes, subs, ways, order, gym_of_route, placed, offroute


def species_types(jar_species, name):
    # battle_sim.key, not a second copy of it: two copies of a normalisation that must agree on both sides is
    # the exact shape of the bug that dropped the gendered Nidoran.
    import battle_sim as BS
    sp = jar_species.get(BS.key(name))
    if not sp:
        return None
    return [t for t in (sp.get("primaryType"), sp.get("secondaryType")) if t]


def build(margin):
    import battle_sim as BS
    jar_species, _moves, _chart = BS.load_pack(BS.find_jar())
    routes, subs, ways, order, gym_of_route, placed, offroute = collect(margin)

    # pool -> the gym it becomes available at
    at_gym = {}
    for r in order:
        at_gym[r] = gym_of_route[r]
    for name, (_kind, g, _gap) in placed.items():
        at_gym[name] = g

    rows_of = {}
    for name, (_b, rows) in list(routes.items()) + list(subs.items()) + list(ways.items()):
        rows_of[name] = rows

    kind_of = {r: "route" for r in routes}
    kind_of.update({k: "subregion" for k in subs})
    kind_of.update({k: "waterway" for k in ways})

    # species -> (first gym, first level band, pool, kind)
    first = {}
    for name, g in sorted(at_gym.items(), key=lambda kv: kv[1]):
        for r in rows_of.get(name) or []:
            s = r["species"]
            if not s:
                continue
            cur = first.get(s)
            gap = 0 if name in routes else placed.get(name, (None, None, None))[2]
            if cur is None or (g, r["lo"]) < (cur["gym"], cur["lo"]):
                first[s] = {"gym": g, "lo": r["lo"], "hi": r["hi"], "pool": name,
                            "kind": kind_of.get(name, "?"), "bucket": r["bucket"], "time": r["time"],
                            "gap": gap}
    missing = sorted({s for s in first if species_types(jar_species, s) is None})
    if missing:
        raise AvailabilityError("no species data for %s" % missing[:8])

    habitats = {}
    blocks = json.loads(BLOCKS.read_text(encoding="utf-8")).get("blocks") or []
    for p in sorted(HABITAT_POOLS.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        sp = sorted({(e.get("pokemon") or "").split()[0].lower() for e in (d.get("spawns") or d.get("entries") or [])
                     if e.get("pokemon")})
        habitats[p.stem] = (sp, [b for b in blocks if b.get("pool", "").endswith(p.stem)])
    return jar_species, first, at_gym, placed, offroute, habitats, kind_of, rows_of


def report(margin, write):
    import battle_sim as BS
    jar_species, first, at_gym, placed, offroute, habitats, kind_of, rows_of = build(margin)
    out = []

    def say(s=""):
        out.append(s)

    say("# Critical-path Pokemon availability")
    say()
    say("**Generated** by `python tools/availability.py --write` from the compiled pools in")
    say("`build/datapacks/cobblers_spawns/`, with types read from the Cobblemon 1.8 jar. Do not hand-edit it.")
    say()
    say("This replaces the hand-written version, which covered the curated ROUTE compilation only. That omission")
    say("hid the waterway pool that crosses Route 3, and so produced the conclusion that Gym 3 had one Ground")
    say("answer and was structurally thin. It has three.")
    say()
    say("A species is listed under the first gym a player could have caught it before, and the level band shown is")
    say("the band where it first appears. A species available earlier stays catchable later.")
    say()
    say("Reachability rule: route N is walked to reach gym N. A sub-region or waterway is placed at the earliest")
    say("gym whose route its spawn boxes come within **%d blocks** of, which is Minecraft's own simulation" % margin)
    say("distance: inside it the Pokemon are loaded and ticking in front of a player who never leaves the route.")
    say("The `Off corridor` column gives each species' actual gap, so a stricter reading is available without")
    say("re-running anything. Pools further than that are listed under *Pools off the route corridor* with their")
    say("nearest route. Habitat pools are not placed by geography at all and are listed separately again.")
    say()

    by_gym = {}
    for s, f in first.items():
        by_gym.setdefault(f["gym"], []).append((s, f))

    for g in sorted(GYMS):
        leader, theme = GYMS[g]
        cumulative = []
        for gg in sorted(by_gym):
            if gg <= g:
                cumulative += by_gym[gg]
        say("## Gym %d: %s (%s)" % (g, leader, theme))
        say()
        say("%d species catchable before this gym; %d of them are new since the last."
            % (len(cumulative), len(by_gym.get(g, []))))
        say()
        # Types are counted on the form a player would HAVE at this gym's cap, not on the form they caught.
        # Bunnelby is Normal and Diggersby is Normal/Ground: counting the caught form is exactly the mistake
        # that made Gym 3 look as though it had no Ground answer at all.
        cap = CAPS[g]
        types, caught = {}, {}
        for sp_name, _f in cumulative:
            for t in species_types(jar_species, sp_name) or []:
                caught.setdefault(t.lower(), []).append(sp_name)
            grown = BS.evolve(jar_species, sp_name, cap)
            for t in species_types(jar_species, grown) or []:
                types.setdefault(t.lower(), []).append(grown)
        say("Types available at the cap (L%d), on the form a player would have evolved to: %s."
            % (cap, ", ".join("%s (%d)" % (t, len(set(v))) for t, v in sorted(types.items()))))
        gained = sorted(set(types) - set(caught))
        if gained:
            say("Reached only by evolving, invisible if you read the caught form: %s." % ", ".join(gained))
        absent = sorted({t.lower() for sp in jar_species.values()
                         for t in (sp.get("primaryType"), sp.get("secondaryType")) if t} - set(types))
        say("Absent: %s." % (", ".join(absent) if absent else "none"))
        say()
        say("| Species | Types | First wild levels | Bucket | Pool | Kind | Off corridor | New here |")
        say("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for s, f in sorted(cumulative, key=lambda kv: (kv[1]["gym"], kv[1]["lo"], kv[0])):
            gap = f.get("gap")
            say("| %s | %s | %d-%d | %s | %s | %s | %s | %s |"
                % (s, "/".join(species_types(jar_species, s) or []), f["lo"], f["hi"], f["bucket"] or "?",
                   f["pool"], f["kind"], "on it" if not gap else "%d blocks" % gap,
                   "yes" if f["gym"] == g else ""))
        say()

    say("## Pools off the route corridor")
    say()
    if offroute:
        say("Reachable by walking, but nothing gates when, so they are not assigned to a gym.")
        say()
        say("| Pool | Kind | Nearest route | Gap (blocks) | Species |")
        say("| --- | --- | --- | --- | --- |")
        for name, (kind, near, gap) in sorted(offroute.items(), key=lambda kv: kv[1][2] or 0):
            sp = sorted({r["species"] for r in (rows_of.get(name) or []) if r["species"]})
            say("| %s | %s | %s | %s | %s |"
                % (name, kind, near, gap, ", ".join(sp[:14]) + (" ..." if len(sp) > 14 else "")))
    else:
        say("None: every sub-region and waterway pool touches a route corridor.")
    say()

    say("## Habitat pools: none of them reach a player")
    say()
    say("A habitat pool only spawns where a Cobblemon Habitat Block stands. `data/habitat_blocks.json` places")
    say("**no blocks anywhere**, so every pool below is authored and inert.")
    say()
    say("| Pool | Blocks placed | Species |")
    say("| --- | --- | --- |")
    for name, (sp, blocks) in sorted(habitats.items()):
        say("| %s | %d | %s |" % (name, len(blocks), ", ".join(sp[:12])))
    say()

    say("## What this document still does not cover")
    say()
    say("The pack's own inherited pools. `data/spawn_suppression.json` retains upstream defaults in \"unauthored")
    say("caves\", off-route wilderness, open ocean and the Nether and End, and the bounded-suppression override")
    say("pack is not installed on the staging server. Measured 2026-09-24 over the server's mods and datapacks:")
    say("**2,662 readable spawn pool files carrying 5,850 underground-only spawn details** (Cobblemon 3,657,")
    say("COBBLEVERSE-DP-v31 2,037, three addons the rest), naming 855 distinct species.")
    say()
    say("Those are not ordered by route and cannot be placed on this progression, but they are live. Any")
    say("conclusion of the form \"a player cannot get an X before gym N\" is unsafe until they are accounted for.")
    say()

    text = "\n".join(out) + "\n"
    # The sidecar is the interface. tools/battle_sim.py used to parse the markdown with a regex, and a row the
    # regex could not match (the gendered Nidoran) vanished from the candidate pool without a word.
    side = {"generated_by": "tools/availability.py", "margin": margin, "caps": CAPS,
            "gyms": {str(g): sorted([{"species": sp, "types": species_types(jar_species, sp),
                                      "lo": f["lo"], "hi": f["hi"], "bucket": f["bucket"],
                                      "pool": f["pool"], "kind": f["kind"], "off_corridor": f.get("gap") or 0}
                                     for sp, f in first.items() if f["gym"] <= g],
                                    key=lambda r: (r["lo"], r["species"]))
                     for g in sorted(GYMS)},
            "off_route": {k: {"kind": v[0], "nearest_route": v[1], "gap": v[2]} for k, v in offroute.items()},
            "habitats_unreachable": sorted(habitats)}
    if write:
        OUT.write_text(text, encoding="utf-8", newline="\n")
        JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
        JSON_OUT.write_text(json.dumps(side, indent=1) + "\n", encoding="utf-8", newline="\n")
        print("wrote %s (%d lines) and %s" % (OUT, len(out), JSON_OUT))
    else:
        print(text)
    return first, at_gym, placed, offroute, habitats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--margin", type=int, default=128)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    report(a.margin, a.write)
    return 0


if __name__ == "__main__":
    sys.exit(main())

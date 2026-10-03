#!/usr/bin/env python
"""The northern residents of data/northern_residents.json: six more meetings, outside rows E-H.

The owner, 2026-10-03: "The Lopunny house on the snow island is the model - a character with a situation, somewhere
specific, that you remember meeting... write and build more of them." The southern six came first
(data/southern_residents.json, tools/southern_residents.py); these six stand in the next-thinnest stretches of rows
A-D, measured the way the southern wayside work measured (data/northern_residents.json measured_by), each a different
KIND of meeting from each other and from the southern six and the Lopunny house.

Nothing here is new machinery. The block primitives (a structure on a levelled floor, surface work, blocks on their own
column's ground, a ring, a line of posts), the NPC seating, the record checks and the residents' keeper are
tools/southern_residents.py's own functions, CALLED, not copied, and through it tools/resident_encounters.py's keeper.
This tool adds one primitive, `clearing`: logs, leaves and plants taken off a square of dry columns from each column's
ground up, so a site in a wood (four of these six are in one) does not leave a canopy floating over a cut trunk. Every Y
is the canonical heightmap's rounded ground (tools/ground.py), never a world's.

The siting rules fail the build (the brief of 2026-10-03): every written column, clear, NPC, anchor and cache north of
z 4096 (rows A-D) and at least rules.authored_clearance from every x/z authored in any OTHER data/*.json (the southern
residents' file included; this file's own quest and reward records skipped by id); outside every town footprint (+96)
and Rift zone box; every site centre and resident at least rules.path_clearance from a route path; a resident's leash
clear of every activated Habitat Block's spawn_range; its level within its sub-region's tier ceiling. These are the
builder's guards, not an audit: the independent audit is another agent's (data/northern_residents.json audit_checklist).

  python tools/northern_residents.py [--source-root R] [--out DIR]    write build/datapacks/cobblers_northern_residents
  python tools/northern_residents.py --report                          the sites as measured, the checks, the steps

The re-application (tools/reapply.py): placement_steps() is R9NR, BEFORE R9E with the other block passes (after R9SR);
entity_steps() is R18NR, after R18SR: the ungated residents summoned and bound, then the NPCs R9F does not place.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import function_limits  # noqa: E402
import southern_residents as SR  # noqa: E402

DATA = ROOT / "data" / "northern_residents.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_northern_residents"
SCHEMA = "cobblers.northern-residents/1"
PACK_FORMAT = 48  # Minecraft 1.21.1
KINDS = SR.KINDS + ("clearing",)
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()


class NorthError(SystemExit):
    pass


jload = SR.jload
base = SR.base


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise NorthError("%s: schema must be %s" % (path, SCHEMA))
    ids = [r["id"] for r in doc["residents"]]
    if len(ids) != len(set(ids)):
        raise NorthError("resident ids must be unique")
    for r in doc["residents"]:
        for p in r["pieces"]:
            if p["kind"] not in KINDS:
                raise NorthError("%s: unknown piece kind %s" % (r["id"], p["kind"]))
        pk = r.get("pokemon")
        if pk and not (0 < pk["trigger"] < pk["leash"]):
            raise NorthError("%s: the trigger must be inside the leash" % r["id"])
    return doc


# ------------------------------------------------------------------ the site plan


def piece_clearing(s, p):
    """Logs, leaves and plants off a square of half-width r round `at`, from the lowest ground under it + 1 to the
    highest + up: one box clear, never a block of ground (the clears replace only logs, leaves and replaceables).
    Every column must be dry: #minecraft:replaceable holds water, and a clear over a wet column would drain it."""
    ox, oz = p.get("at") or (0, 0)
    r = int(p["r"])
    cols = [(s.cx + ox + dx, s.cz + oz + dz) for dx in range(-r, r + 1) for dz in range(-r, r + 1)]
    wet = [c for c in cols if s.wet(*c)]
    if wet:
        raise NorthError("%s %s: the clearing has wet columns, e.g. %s" % (s.r["id"], p["name"], wet[:3]))
    gs = [s.g(x, z) for x, z in cols]
    s.clears.append((s.cx + ox - r, min(gs) + 1, s.cz + oz - r, s.cx + ox + r, max(gs) + int(p["up"]), s.cz + oz + r))


def plan(doc, r, g, wet):
    s = SR.Site(doc, r, g, wet)
    for i, p in enumerate(r["pieces"]):
        k = p["kind"]
        if k == "clearing":
            piece_clearing(s, p)
        elif k == "structure":
            SR.piece_structure(s, p)
        elif k == "surface":
            SR.piece_surface(s, p, i + 1)
        elif k == "ground_blocks":
            SR.piece_ground_blocks(s, p)
        elif k == "ring":
            SR.piece_ring(s, p)
        elif k == "posts":
            SR.piece_posts(s, p)
    return s


def sites(doc, g, wet=None):
    """tools/southern_residents.py sites(), on this tool's plan (the extra `clearing` piece)."""
    import resident_encounters as RE
    wet = wet or RE.Wet(g, [tuple(r["site"]["centre"]) for r in doc["residents"]])
    out = []
    for r in doc["residents"]:
        s = plan(doc, r, g, wet)
        extra = []
        if r.get("npc"):
            xyz = SR.spot(s, r["npc"]["at"])
            if r["npc"]["at"][2] == "ground":
                SR.stand_clears(s, xyz)
            SR.check_standing(s, xyz, r["npc"]["name"])
            extra.append(xyz)
        if r.get("pokemon"):
            a = SR.anchor(s, r)
            SR.stand_clears(s, a)
            SR.check_standing(s, a, r["pokemon"]["name"])
            extra.append(a)
        for c in r.get("caches") or []:
            extra.append(SR.spot(s, c["at"]))
        out.append((r, s, extra, SR.box_of(s, extra)))
    return out


# ------------------------------------------------------------------ the siting rules (the builder's guards)


def authored_points(doc):
    return SR.authored_points(doc, own_file=DATA)


def siting(doc, r, s, extra, pts):
    """Problems, as strings, for one planned site. `extra` are the NPC spots, anchors and cache boxes (x, y, z)."""
    import numpy as np
    rules = doc["rules"]
    probs = []
    P = np.array([(a, b) for a, b, _f in pts], float)
    F = [f for _a, _b, f in pts]
    cols = set(s.cols) | {(c[0], c[2]) for c in s.clears} | {(c[3], c[5]) for c in s.clears} | {(e[0], e[2]) for e in extra}
    # a box clear's whole perimeter, not just two corners: the nearest authored point may face the middle of an edge
    for c in s.clears:
        if c[0] != c[3] or c[2] != c[5]:
            cols |= {(x, z) for x in range(c[0], c[3] + 1) for z in (c[2], c[5])}
            cols |= {(x, z) for z in range(c[2], c[5] + 1) for x in (c[0], c[3])}
    C = np.array(sorted(cols), float)
    best = (1e9, None, None)
    for i in range(0, len(C), 256):
        blk = C[i:i + 256]
        d = np.hypot(P[None, :, 0] - blk[:, None, 0], P[None, :, 1] - blk[:, None, 1])
        j = np.unravel_index(np.argmin(d), d.shape)
        if d[j] < best[0]:
            best = (float(d[j]), tuple(blk[j[0]]), F[j[1]])
    if best[0] < rules["authored_clearance"]:
        probs.append("%s: (%d, %d) is %.0f blocks from an x/z authored in data/%s (needs %d)"
                     % (r["id"], best[1][0], best[1][1], best[0], best[2], rules["authored_clearance"]))
    # data/routes.json's corridor boxes ({min_x, max_x, min_z, max_z} dicts): authored_points() never reads them, so
    # each is held here as a FILLED rectangle (2026-10-03: three sites stood 73, 76 and 93 from one and passed)
    cprobs, cbest = SR.corridor_check(r["id"], cols, rules["authored_clearance"])
    probs += cprobs
    m = rules["authored_clearance"]
    for t in jload("towns.json")["towns"]:
        f = t.get("footprint") or {}
        if f.get("min_x") is None:
            continue
        if any(f["min_x"] - m <= x <= f["max_x"] + m and f["min_z"] - m <= z <= f["max_z"] + m for x, z in cols):
            probs.append("%s: within %d of town %s's footprint" % (r["id"], m, t["id"]))
    for k, zone in jload("rift_zones.json")["zones"].items():
        for bx in zone.get("boxes") or []:
            if any(bx[0] <= x <= bx[2] and bx[1] <= z <= bx[3] for x, z in cols):
                probs.append("%s: inside Rift zone %s" % (r["id"], k))
                break
    if any(z >= rules["north_of_z"] for _x, z in cols):
        probs.append("%s: writes at or south of z %d (rows E-H)" % (r["id"], rules["north_of_z"]))
    paths = np.array([p for pl in jload("route_paths.json")["paths"].values() for p in pl], float)
    cx, cz = r["site"]["centre"]
    dp = float(np.min(np.hypot(paths[:, 0] - cx, paths[:, 1] - cz)))
    if dp < rules["path_clearance"]:
        probs.append("%s: %.0f blocks from a route path (needs %d)" % (r["id"], dp, rules["path_clearance"]))
    dcol = min(float(np.min(np.hypot(paths[:, 0] - x, paths[:, 1] - z))) for x, z in
               [(e[0], e[2]) for e in extra] or [(cx, cz)])
    if dcol < rules["path_clearance"]:
        probs.append("%s: an NPC, resident or cache is %.0f blocks from a route path (needs %d)"
                     % (r["id"], dcol, rules["path_clearance"]))
    pk = r.get("pokemon")
    if pk:
        ax, az = s.cx + pk["at"][0], s.cz + pk["at"][1]
        act = [b for b in jload("habitat_blocks.json")["blocks"] if b.get("style") == "activated"]
        for b in act:
            d = math.hypot(b["position"]["x"] - ax, b["position"]["z"] - az)
            if d < b["activated"]["spawn_range"] + pk["leash"]:
                probs.append("%s: its leash overlaps Habitat Block %s (%.0f, needs %d)"
                             % (r["id"], b["id"], d, b["activated"]["spawn_range"] + pk["leash"]))
        sub, tier, ceiling = SR._sub_of(ax, az)
        if sub is None:
            probs.append("%s: the resident stands in no sub-region with a table" % r["id"])
        else:
            if pk["level"] > ceiling:
                probs.append("%s: L%d over %s's tier-%s ceiling %d" % (r["id"], pk["level"], sub, tier, ceiling))
            if sub != r["subregion"]:
                probs.append("%s: the resident stands in %s, the record says %s" % (r["id"], sub, r["subregion"]))
    sub = SR._sub_of(cx, cz)[0]
    if sub != r["subregion"]:
        probs.append("%s: the centre is in %s, the record says %s" % (r["id"], sub, r["subregion"]))
    return probs, {"nearest_authored": best, "path": dp, "corridor": cbest}


# ------------------------------------------------------------------ the pack


def files(doc, g, wet=None, check=True):
    import resident_encounters as RE
    built = sites(doc, g, wet)
    if check:
        pts = authored_points(doc)
        probs = []
        for r, s, extra, box in built:
            probs += siting(doc, r, s, extra, pts)[0]
        probs += SR.check_records(doc, built)
        spawn = set(jload("spawn_blocks.json")["blocks"])
        for r, s, extra, box in built:
            bad = sorted({base(v) for v in list(s.solid.values()) + list(s.hung.values())} & spawn)
            if bad:
                probs.append("%s: writes spawn-condition blocks %s (data/spawn_blocks.json)" % (r["id"], bad))
        if probs:
            raise NorthError("northern_residents: %d problem(s):\n  %s" % (len(probs), "\n  ".join(probs)))
    b = doc["build"]
    ns, F, obj = b["namespace"], b["folder"], b["objective"]
    fn = {}
    sh = SR.shim(doc)
    load_ = ["# the northern residents' keeper state (tools/northern_residents.py, on tools/resident_encounters.py's keeper).",
             "# A clock that has never been set starts READY (respawn ticks already elapsed), so a fresh world fills at once",
             "scoreboard objectives add %s dummy" % obj,
             "scoreboard players set #resp %s %d" % (obj, int(b["respawn_ticks"])),
             "execute store result score #ready %s run time query gametime" % obj,
             "scoreboard players operation #ready %s -= #resp %s" % (obj, obj)]
    keeper = ["execute store result score #now %s run time query gametime" % obj]
    for r, s, extra, box in built:
        lines = SR.build_lines(doc, r, s, box)
        lines[0] = "# Generated by tools/northern_residents.py from data/northern_residents.json: %s" % r["name"]
        lines[1] = lines[1].replace("R9SR", b["steps"]["blocks"])
        bad = function_limits.check_lines(lines, "%s/build" % r["id"])
        if bad:
            raise NorthError("%s/build: %d command(s) the server would refuse: %s" % (r["id"], len(bad), bad[:3]))
        fn["%s/build" % r["id"]] = lines
        pt = r.get("player_tag")
        if pt:
            # a conversation's `function` effect runs this as and at the player (compile_dialogue), and another
            # conversation reads the tag with its player_tag condition: one quest may not read another's fields
            # (tools/validate_data.py quest-dialogue), so the one fact two quests share is a tag on the player
            fn[pt["function"]] = ["# Generated by tools/northern_residents.py: %s (data/northern_residents.json %s player_tag)"
                                  % (pt["why_short"], r["id"]), "tag @s add %s" % pt["tag"]]
        if r.get("pokemon"):
            e = SR.resident_record(r)
            a = SR.anchor(s, r)
            i = e["id"]
            rf = RE.resident_files(sh, e, a, [], [], box)
            rf.pop("%s/dress" % i, None)
            fn.update(rf)
            load_ += ["execute unless score #%s.gone %s matches -2147483648.. run scoreboard players operation #%s.gone %s = #ready %s"
                      % (i, obj, i, obj, obj),
                      "execute unless score #%s.abs %s matches -2147483648.. run scoreboard players set #%s.abs %s 0" % (i, obj, i, obj)]
            keeper.append("execute if loaded %d %d %d run function %s:%s/%s/keep" % (a[0], a[1], a[2], ns, F, i))
    if any(r.get("pokemon") for r, _s, _e, _b in built):
        fn["spawn_at"] = ["# a macro, so the mod's command is parsed when it runs (EXP-046, .claude/rules/datapacks.md)",
                          "$spawnpokemonat $(x) $(y) $(z) $(species) $(props)"]
        load_.append("schedule function %s:%s/keeper %dt replace" % (ns, F, b["keeper"]["period_ticks"]))
        keeper.append("schedule function %s:%s/keeper %dt replace" % (ns, F, b["keeper"]["period_ticks"]))
        fn["load"] = load_
        fn["keeper"] = keeper
    out = {"data/%s/function/%s/%s.mcfunction" % (ns, F, n): "\n".join(v) + "\n" for n, v in fn.items()}
    if "load" in fn:
        out["data/minecraft/tags/function/load.json"] = json.dumps({"values": ["%s:%s/load" % (ns, F)]}, indent=2) + "\n"
    out["pack.mcmeta"] = json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                              "Cobblers: the northern residents (tools/northern_residents.py)"}}, indent=2) + "\n"
    return out, built


# ------------------------------------------------------------------ the re-application


def _built(doc=None, g=None):
    import ground as G
    doc = doc or load()
    g = g or G.load()
    return doc, g, sites(doc, g)


def placement_steps(doc=None, g=None):
    """R9NR, BEFORE R9E: per site, hold its box, build, release (R9SR's shape)."""
    doc, g, built = _built(doc, g)
    b = doc["build"]
    steps = []
    for r, s, extra, box in built:
        hold = "%d %d %d %d" % tuple(box)
        steps += [("cmd", "forceload add " + hold), ("wait", 3),
                  ("fn", "%s:%s/%s/build" % (b["namespace"], b["folder"], r["id"])), ("cmd", "forceload remove " + hold)]
    return steps


def npc_placements(doc=None, g=None, built=None):
    """[(conversation id, (x, y, z), npc class, yaw)] for the NPCs R9F does NOT place (no npc_grant record)."""
    if built is None:
        doc, g, built = _built(doc, g)
    step = (doc or load())["build"]["steps"]["entities"]
    dl = {c["id"]: c for c in jload("dialogue.json")["conversations"]}
    out = []
    for r, s, extra, box in built:
        n = r.get("npc")
        if not n or n["placed_by"] != step:
            continue
        conv = dl.get(r["records"]["conversation"])
        if conv is None or not conv.get("npc_id"):
            raise NorthError("%s: %s is not a conversation with an NPC in data/dialogue.json" % (r["id"], r["records"]["conversation"]))
        out.append((conv["id"], SR.spot(s, n["at"]), "cobblers:%s" % conv["npc_id"], n["yaw"]))
    return out


def entity_steps(doc=None, g=None):
    """R18NR, after R18SR: each ungated resident summoned over RCON (guarded on tag AND species: THE SUMMON GUARD)
    and bound, inside a forceload of its site's box; then the NPCs R9F does not place."""
    import resident_encounters as RE
    doc, g, built = _built(doc, g)
    b = doc["build"]
    sh = SR.shim(doc)
    steps = []
    for r, s, extra, box in built:
        if not r.get("pokemon") or r["pokemon"].get("appears_after"):
            continue
        e = SR.resident_record(r)
        a = SR.anchor(s, r)
        hold = "%d %d %d %d" % tuple(box)
        steps += [("cmd", "forceload add " + hold), ("wait", 3), ("cmd", RE.summon_command(sh, e, a)), ("wait", 1),
                  ("fn", "%s:%s/%s/bind_new" % (b["namespace"], b["folder"], e["id"])), ("cmd", "forceload remove " + hold)]
    steps += [("npc", n) for n in npc_placements(doc, g, built)]
    return steps


# ------------------------------------------------------------------ CLI


def report(doc, g):
    built = sites(doc, g)
    pts = authored_points(doc)
    lines = []
    for r, s, extra, box in built:
        probs, m = siting(doc, r, s, extra, pts)
        na = m["nearest_authored"]
        sub = SR._sub_of(*r["site"]["centre"])
        lines.append("%-18s %-34s centre %s ground y%d sub %s tier %s; %d blocks, bbox %s; nearest authored %.0f "
                     "(our column %s to data/%s); corridor box %.0f (%s); path %.0f"
                     % (r["id"], r["name"], r["site"]["centre"], g(*r["site"]["centre"]), sub[0], sub[1],
                        len(s.solid) + len(s.hung), box, na[0], tuple(int(v) for v in na[1]), na[2],
                        m["corridor"][0], m["corridor"][2], m["path"]))
        for k, v in s.floors.items():
            lines.append("    floor %s: %s" % (k, v if not isinstance(v, list) else "%d posts" % len(v)))
        if r.get("npc"):
            lines.append("    NPC %s feet %s" % (r["npc"]["name"], list(SR.spot(s, r["npc"]["at"]))))
        if r.get("pokemon"):
            lines.append("    resident %s L%d anchor %s" % (r["pokemon"]["name"], r["pokemon"]["level"], list(SR.anchor(s, r))))
        for c in r.get("caches") or []:
            lines.append("    cache %s spot %s" % (c["reward"], list(SR.spot(s, c["at"]))))
        for p in probs:
            lines.append("    PROBLEM %s" % p)
    for p in SR.check_records(doc, built):
        lines.append("PROBLEM %s" % p)
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--source-root")
    ap.add_argument("--report", action="store_true", help="print the sites, the checks and the steps; write nothing")
    a = ap.parse_args(argv)
    import ground as G
    doc = load(Path(a.data))
    g = G.load(a.source_root)
    if a.report:
        print("\n".join(report(doc, g)))
        return 0
    written, built = files(doc, g)
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in written.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    n = sum(1 for rel, t in written.items() if rel.endswith("/build.mcfunction")
            for l in t.splitlines() if l and not l.startswith("#"))
    print("northern_residents: %d files -> %s (%d sites, build: %d commands)" % (len(written), out, len(built), n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

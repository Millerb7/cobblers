#!/usr/bin/env python
"""The Tri Peaks' open-summit nest, from data/tri_peaks_nest.json: Crownbreaker, a Tyranitar on the bare crown of the
massif's south peak, ringed by black rock teeth, with a scree spur running down to the shoulder above Highwire.

The owner's nest standard (2026-10-09): a creature, a place that suits it, strong enough that meeting it early is a
mistake. This one is IN THE OPEN on a summit (the Ursaluna den, 350 blocks south, is the Tri Peaks' cave). Nothing here
is new machinery: the record is data/resident_encounters.json's shape (schema cobblers.resident-encounters/1), and
tools/resident_encounters.py does the work, CALLED, not copied, as tools/far_south.py and tools/desert_wreck.py call
its resident_files():

  the dressing   the record's primitives (strip, post, log, blocks) through resident_encounters.dressing(), every block
                 seated on the canonical heightmap's rounded ground (tools/ground.py), never on a world. Two shorthand
                 kinds are added here and expanded into `blocks` before it runs: `tor` (a tapering rock tooth) and
                 `mound` (a heap of rubble). Surface work replaces the ground's top block only.
  the resident  a wild Pokemon on the residents' KEEPER (resident_encounters.files(): a 40-tick loop, the respawn clock,
                 dormant until a player is within `trigger`, leashed, settled back to sleep, never touching a
                 cobblers.guardian). It has NO presence gate, so the keeper brings it in the first time a player is
                 within 96 blocks of the summit; no re-application step summons it. Its catch gate is the level-cap
                 refusal (data/level_cap.json), not an advancement: L35 is over the cap 30 a player carries before gym 3
                 and at the cap 35 the third badge gives. That is why this tool has no entity step, and so no
                 chunk_look chain (tools/chunk_look.py is for steps that force-load and then summon or kill).

The spawn system: the summit and its climb are the_tri_peaks' own heart and land tables (data/encounter_design.json,
tier 3); this nest adds no Habitat Block and no pool.

  python tools/tri_peaks_nest.py [--source-root R] [--out DIR]     write build/datapacks/cobblers_tri_peaks_nest
  python tools/tri_peaks_nest.py --report                           the site as measured, the writes, the steps
  python tools/tri_peaks_nest.py --measure                          the numbers a record must carry (nothing written)
  python tools/tri_peaks_nest.py probes [--write]                   presence probes -> data/world_probes.json

The re-application (tools/reapply.py): placement_steps() is R9TP, BEFORE R9E with the other block passes (after R9FS).
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import resident_encounters as RE  # noqa: E402

DATA = ROOT / "data" / "tri_peaks_nest.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_tri_peaks_nest"
PROBES = ROOT / "data" / "world_probes.json"
PROBE_KEY = "tri_peaks_nest"
STEP = "R9TP"
SCHEMA = RE.SCHEMA
SHORTHAND = ("tor", "mound")
# The ground rule (tools/ground_rule.py): nothing here reads a world; every Y comes from tools/ground.py.
WORLD_READS: set = set()


class NestError(ValueError):
    pass


# ------------------------------------------------------------------ the shorthand kinds


def _columns(r):
    """Integer (dx, dz) offsets of a disc of radius r (r = 0 is the one column)."""
    lim = r * r + (0.5 if r else 0.0)
    return [(dx, dz) for dx in range(-r, r + 1) for dz in range(-r, r + 1) if dx * dx + dz * dz <= lim]


def tor_blocks(p, ax, az, salt):
    """[dx, dy, dz, block] of a tapering tooth: radius `radius` for the lower 40% of `height`, one less to 80%, then a
    single column to the tip. Each entry is seated by resident_encounters.dressing() on its own column's ground."""
    h, r = int(p["height"]), int(p["radius"])
    cx, cz = p["at"]
    out = []
    for j in range(h):
        rj = r if j < 0.4 * h else (max(r - 1, 0) if j < 0.8 * h else 0)
        for dx, dz in _columns(rj):
            x, z = ax + cx + dx, az + cz + dz
            out.append([cx + dx, j + 1, cz + dz, RE._pick(p["block"], x, z, salt)])
    return out


def mound_blocks(p, ax, az, salt):
    """[dx, dy, dz, block] of a heap: the centre column `height` high, the four neighbours one lower, the corners one
    lower again (never under 1)."""
    h = int(p["height"])
    cx, cz = p["at"]
    out = []
    for dx, dz in _columns(1):
        top = h if (dx, dz) == (0, 0) else (h - 1 if dx == 0 or dz == 0 else h - 2)
        for j in range(max(1, top)):
            x, z = ax + cx + dx, az + cz + dz
            out.append([cx + dx, j + 1, cz + dz, RE._pick(p["block"], x, z, salt)])
    return out


def expand(doc):
    """doc with every `tor` and `mound` replaced by the `blocks` primitive resident_encounters knows."""
    doc = copy.deepcopy(doc)
    for e in doc["encounters"]:
        ax, az = e["location"]["x"], e["location"]["z"]
        out = []
        for i, p in enumerate(e["build"]["dressing"]):
            if p["kind"] == "tor":
                out.append({"kind": "blocks", "name": p.get("name", "tor"), "at": [0, 0],
                            "blocks": tor_blocks(p, ax, az, 100 + i)})
            elif p["kind"] == "mound":
                out.append({"kind": "blocks", "name": p.get("name", "mound"), "at": [0, 0],
                            "blocks": mound_blocks(p, ax, az, 100 + i)})
            else:
                out.append(p)
        e["build"]["dressing"] = out
    return doc


def load(path=DATA):
    """The record, expanded, with resident_encounters.load()'s checks (it reads a path, so they are repeated here)."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("schema") != SCHEMA:
        raise NestError("%s: schema must be %s" % (path, SCHEMA))
    doc = expand(raw)
    rules, b = doc["rules"], doc["build"]
    if len(doc["encounters"]) != rules["count"]:
        raise NestError("rules.count is %d but %d encounters are authored" % (rules["count"], len(doc["encounters"])))
    for e in doc["encounters"]:
        bb = e["build"]
        if not (0 < bb["trigger"] < bb["leash"]):
            raise NestError("%s: the trigger must be inside the leash" % e["id"])
        if (e["id"] in rules["permanently_uncatchable"]) != (e["catch_rule"] == "permanently_uncatchable"):
            raise NestError("%s: catch_rule disagrees with rules.permanently_uncatchable" % e["id"])
        for p in bb["dressing"]:
            if p["kind"] not in RE.KINDS:
                raise NestError("%s: unknown dressing kind %s" % (e["id"], p["kind"]))
        if bb.get("appears_after"):
            raise NestError("%s: this nest has no presence gate; its catch gate is the level cap" % e["id"])
    if b["keeper"]["spawn_clear"] >= b["keeper"]["spawn_radius"]:
        raise NestError("spawn_clear must be inside spawn_radius, or nothing ever spawns")
    return doc


# ------------------------------------------------------------------ the numbers a record must carry


def measure(doc, ground):
    """[(id, anchor, ground y, box, block writes, clears)] straight from the heightmap, no record check."""
    wet = RE.Wet(ground, [(e["location"]["x"], e["location"]["z"]) for e in doc["encounters"]])
    out = []
    for e in doc["encounters"]:
        a = RE.anchor(e, ground, wet)
        sets, clears = RE.dressing(e, ground, wet)
        clears = clears + RE.stand_clears(a, ground)
        out.append((e["id"], a, ground(a[0], a[2]), RE.bbox(sets, clears, a), sets, clears))
    return out


def sightline(doc, ground):
    """From Highwire's gate (the town centre) and along Route 3: where the crown and its tallest tooth are in line of
    sight over the terrain between (eye 1.7 above the ground, target 3 above the tip). Heightmap only."""
    e = doc["encounters"][0]
    a = RE.anchor(e, ground)
    tors = [p for p in json.loads(Path(DATA).read_text(encoding="utf-8"))["encounters"][0]["build"]["dressing"]
            if p["kind"] == "tor"]
    tip = max(((a[0] + p["at"][0], a[2] + p["at"][1], p["height"]) for p in tors), key=lambda t: t[2], default=None)
    towns = json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]
    c = next(t for t in towns if t.get("id") == e["build"]["sightline"]["from_town"])["centre"]
    town = [c["x"], c["z"]]
    paths = json.loads((ROOT / "data" / "route_paths.json").read_text(encoding="utf-8"))["paths"]

    def clear(frm, to, to_y, eye=1.7):
        (fx, fz), (tx, tz) = frm, to
        fy = ground(fx, fz) + eye
        n = max(2, int(math.hypot(tx - fx, tz - fz) / 3))
        worst = 1e9
        for i in range(1, n):
            t = i / n
            x, z = fx + (tx - fx) * t, fz + (tz - fz) * t
            worst = min(worst, fy + (to_y - fy) * t - ground(x, z))
        return worst

    tip_y = ground(tip[0], tip[1]) + tip[2] + 1 if tip else a[1] + 1      # the top face of the tallest tooth's top block
    tx, tz = (tip[0], tip[1]) if tip else (a[0], a[2])
    out = {"town_centre": town, "town_distance": round(math.hypot(town[0] - tx, town[1] - tz)),
           "town_margin_to_tip": round(clear(tuple(town), (tx, tz), tip_y), 1), "tip": [tx, tip_y - 1, tz],
           "route_runs": []}
    r3 = paths[e["build"]["sightline"]["route"]]
    runs, cur = [], None
    for i in range(0, len(r3), 2):
        v = clear(tuple(r3[i]), (tx, tz), tip_y) > 0
        if v and cur is None:
            cur = i
        if not v and cur is not None:
            runs.append((cur, i - 2))
            cur = None
    if cur is not None:
        runs.append((cur, len(r3) - 1))
    for lo, hi in runs:
        out["route_runs"].append({"from_index": lo, "to_index": hi, "from_point": r3[lo], "to_point": r3[hi],
                                  "distance_at_start": round(math.hypot(r3[lo][0] - tx, r3[lo][1] - tz)),
                                  "path_points": len(r3)})
    return out


# ------------------------------------------------------------------ the pack


def _site(doc, ground):
    """RE.site() for every record: fails closed when the heightmap disagrees with the record's anchor or bbox."""
    wet = RE.Wet(ground, [(e["location"]["x"], e["location"]["z"]) for e in doc["encounters"]])
    return [(e,) + RE.site(e, ground, wet) for e in doc["encounters"]]


def files(doc, ground):
    """{pack path: text}: resident_encounters.files(), less the bind a summon step would run (this nest has none), with
    the dressing's chunk-holder named."""
    _site(doc, ground)                              # the record must match the heightmap before anything is written
    ns, F = doc["build"]["namespace"], doc["build"]["folder"]
    out = RE.files(doc, ground)
    for e in doc["encounters"]:
        out.pop("data/%s/function/%s/%s/bind_new.mcfunction" % (ns, F, e["id"]), None)
        k = "data/%s/function/%s/%s/dress.mcfunction" % (ns, F, e["id"])
        out[k] = out[k].replace("the re-application R18R", "the re-application %s" % STEP)
    for k in out:
        if k.endswith(".mcfunction"):
            out[k] = out[k].replace("tools/resident_encounters.py from data/resident_encounters.json",
                                    "tools/tri_peaks_nest.py from data/tri_peaks_nest.json")
            out[k] = out[k].replace("the residents' keeper state (tools/resident_encounters.py)",
                                    "the Tri Peaks nest's keeper state (tools/tri_peaks_nest.py, on tools/resident_encounters.py's keeper)")
    out["pack.mcmeta"] = json.dumps({"pack": {"pack_format": RE.PACK_FORMAT,
                                              "description": "Cobblers: the Tri Peaks' open-summit nest "
                                                             "(tools/tri_peaks_nest.py)"}}, indent=2) + "\n"
    return out


def placement_steps(doc=None, ground=None):
    """R9TP, before R9E: per record, hold its box, run its dressing, release. A pure block pass: the resident is the
    keeper's (no presence gate, no summon), so no entity is touched and no chunk_look chain is needed."""
    import ground as G
    doc = doc or load()
    ground = ground or G.load()
    b = doc["build"]
    steps = []
    for e, a, sets, clears, box in _site(doc, ground):
        hold = "%d %d %d %d" % tuple(box)
        steps += [("cmd", "forceload add " + hold), ("wait", 3),
                  ("fn", "%s:%s/%s/dress" % (b["namespace"], b["folder"], e["id"])), ("cmd", "forceload remove " + hold)]
    return steps


# ------------------------------------------------------------------ probes


def probes(doc, ground):
    """{PROBE_KEY: [probe]} in data/world_probes.json's shape: the crown's tooth tips and the air above them, the
    bench's and the scree's own blocks, and the headroom Tyranitar stands in."""
    rows = []
    for e, a, sets, clears, box in _site(doc, ground):
        top = {}
        for x, y, z, blk, name in sets:
            top.setdefault(name, []).append((y, x, z, blk))
        for name, col in sorted(top.items()):
            if name.startswith("the tooth"):
                y, x, z, blk = max(col)
                rows.append({"what": "%s: tip" % name, "block": [x, y, z, blk], "expect": True})
                rows.append({"what": "%s: air over the tip" % name, "block": [x, y + 1, z, "minecraft:air"], "expect": True})
        for name in ("the scoured bench", "the scree, belly"):
            col = sorted(top.get(name, []))
            if col:
                y, x, z, blk = col[len(col) // 2]
                rows.append({"what": "%s: a surface block" % name, "block": [x, y, z, blk], "expect": True})
        rows.append({"what": "%s: air at the feet" % e["id"], "block": [a[0], a[1], a[2], "minecraft:air"], "expect": True})
        rows.append({"what": "%s: air at the head" % e["id"], "block": [a[0], a[1] + 3, a[2], "minecraft:air"], "expect": True})
    return {PROBE_KEY: rows}


# ------------------------------------------------------------------ CLI


def report(doc, ground):
    lines = []
    for e, a, sets, clears, box in _site(doc, ground):
        bb = e["build"]
        lines.append("%s %s L%d anchor %s ground y%d feet y%d yaw %s trigger %d leash %d; %d blocks, %d clears, bbox %s "
                     "(%d x %d)" % (e["id"], e["species"], e["level"], tuple(a), ground(a[0], a[2]), a[1], bb["yaw"],
                                    bb["trigger"], bb["leash"], len(sets), len(clears), box,
                                    box[2] - box[0] + 1, box[3] - box[1] + 1))
    lines.append("steps: %s" % [(k, v if k != "cmd" else v) for k, v in placement_steps(doc, ground)])
    s = sightline(doc, ground)
    lines.append("sightline: %s" % json.dumps(s))
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", nargs="?", default="build", choices=("build", "probes"))
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--source-root")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--measure", action="store_true", help="print the anchor, ground and bbox a record must carry")
    ap.add_argument("--write", action="store_true", help="with probes: merge them into data/world_probes.json")
    a = ap.parse_args(argv)
    import ground as G
    g = G.load(a.source_root)
    if a.measure:
        doc = expand(json.loads(Path(a.data).read_text(encoding="utf-8")))
        for i, anchor, gy, box, sets, clears in measure(doc, g):
            print(i, "anchor", list(anchor), "ground", gy, "bbox", box, "blocks", len(sets), "clears", len(clears))
        return 0
    doc = load(Path(a.data))
    if a.report:
        print("\n".join(report(doc, g)))
        return 0
    if a.cmd == "probes":
        pr = probes(doc, g)
        if a.write:
            d = json.loads(PROBES.read_text(encoding="utf-8"))
            d["places"].update(pr)
            PROBES.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print("wrote %d probes under %s in data/world_probes.json" % (len(pr[PROBE_KEY]), PROBE_KEY))
        else:
            print("%d probes (use --write to merge them into data/world_probes.json)" % len(pr[PROBE_KEY]))
        return 0
    written = files(doc, g)
    import function_limits
    bad = []
    for rel, text in written.items():
        if rel.endswith(".mcfunction"):
            bad += ["%s:%d %s: %s" % (rel, n, cmd, why)
                    for n, cmd, why in function_limits.check_lines(text.splitlines(), where=rel)]
    for msg in bad:
        print("ERROR %s" % msg)
    if bad:
        return 1
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in written.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    n = sum(1 for rel, t in written.items() if rel.endswith("/dress.mcfunction")
            for l in t.splitlines() if l and not l.startswith("#"))
    print("tri_peaks_nest: %d files -> %s (dressing: %d commands)" % (len(written), out, n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

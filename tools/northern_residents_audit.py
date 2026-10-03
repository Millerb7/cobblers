#!/usr/bin/env python
"""The northern residents' offline audit: the emitted pack, the re-application steps, the dialogue records and the
tools/reapply.py wiring, against data/northern_residents.json, every other data file and the canonical heightmap.

INDEPENDENCE (CLAUDE.md, "How to prove an audit is independent"). This file never imports tools/northern_residents.py
or tools/southern_residents.py to derive anything, nor tools/resident_encounters.py (whose keeper both call). It reads
the data, the heightmap (tools/ground.py, round(h)), the painted water (tools/water_mask.py) and the river corridors
(data/rivers.json), and derives what it expects with its own code. The block, standing-spot, replay, keeper, dialogue
and step checks are tools/southern_residents_audit.py's -- another AUDIT, written by an agent that built neither tool,
whose derivation shares nothing with either generator -- and this file adds what the northern record adds: the
`clearing` piece, the rows A-D line, the player_tag pair, Agnes's carving, Pip's badge windows and the R9NR/R18NR
wiring. The only things taken from the generator are its OUTPUTS: the pack and the steps it hands tools/reapply.py.
tests/test_northern_residents_audit.py mutates the GENERATOR's code and leaves the data alone.

  ys        every pokemon.anchor, npc.feet, data/quests.json and data/rewards.json npc_at, re-derived from the heightmap
            and the expected blocks; every resident and NPC on a dry column with ground or a built block under it;
            the record's bbox equal to the derived extent of every expected block, clearing and spot
  writes    the build functions replayed (southern audit's check_writes: on plan, inside the bbox, blocks.ids, no spawn
            condition, chest or bed, nothing under the ground, nothing on a wet column, standing room cleared)
  clearing  each `clearing` piece's box -- the square round `at`, from min(ground)+1 to max(ground)+up -- written as
            the three plant clears (#logs, #leaves, #replaceable) exactly, over dry columns only; and no clear in any
            build function runs after a write it covers (a late clear would take the oak, the hollow's boughs)
  siting    every expected and written column, every clearing's whole box, every spot: north of the row E line
            (data/world.json grid: origin_z + 4 cells); at least rules.authored_clearance from every x/z another data
            file authors (data/southern_residents.json included; our own quest, conversation and reward records
            excepted by id); outside every town footprint + clearance and every Rift zone box; every site centre, NPC
            and anchor at least data/encounter_design.json rules.hearts.clear_of_path_blocks from every route path;
            the record's cell and sub-region are where the centre is
  residents level within the anchor's sub-region tier ceiling (rules.hearts.next_cap); leash clear of every activated
            Habitat Block's spawn_range; catch window from data/trainers.json gym_ace_levels alone
  keeper    the southern audit's keeper checks (anchor, leash, trigger, settle, yaw, level, no kill reaching a guardian),
            and the objective is this pack's alone (no other data record or tool names it)
  steps     each build inside a forceload of its bbox, once; each ungated resident one guarded summon at its anchor
            and one bind_new; each NPC placed once (R9F through an npc_grant, or the record's entity step at its feet,
            class and yaw); every `fn` step names a function the pack has
  dialogue  the southern audit's dialogue/reward checks with this audit's own flag expectation (FLAGS); Agnes's
            r_back is word for word the carving on the oak's north face and r_front the south face's; Pip's r_bN is
            visible with exactly N badges (N = 4..8) and r_b0 below four; Lettie's found transition runs the pack's
            player_tag function, which only tags the player, and Tam's r_found and his grant are reachable only with
            that tag, which his compiled dialogue probes
  wiring    tools/reapply.py: the generator and this audit are prepare jobs, in that order; R9NR is
            northern_residents.placement_steps() between R9SR and R9E; R18NR is northern_residents.entity_steps() after
            R18SR; the pack is in SERVER_PACKS and WORLD_LOCAL

NOT checked, and it needs a running server: that the blocks land and the clearings leave no floating canopy, that the
keeper spawns, holds and wakes the three Pokemon, that the NPCs appear and their dialogue runs, that the Sun Stone and
Shiny Stone and milk are given once, that the function effect and the player_tag read work as a pair (unproven in
game: data/northern_residents.json hide_and_seek_den player_tag.why), that Sudowoodo has a model (relayed), and every
in-game item of the record's audit_checklist.

  python tools/northern_residents_audit.py [--pack build/datapacks/cobblers_northern_residents] [--source-root R] [-v]
"""
from __future__ import annotations

import argparse
import ast
import json
import math
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import southern_residents_audit as SA  # noqa: E402  (an audit, not a generator: see the docstring)

DATA = ROOT / "data"
PACK = ROOT / "build" / "datapacks" / "cobblers_northern_residents"
RECORD = "northern_residents.json"
SCHEMA = "cobblers.northern-residents/1"
GENERATOR = "northern_residents"
CLEAR_TAGS = SA.CLEAR_TAGS

# The progression flags each conversation is EXPECTED to read: this audit's own reading of the record's design, not a
# scan of it. Pip's gym grows with the player "from the fourth badge to the eighth" (pips_gym kind); nobody else's
# conversation is gated on a badge (the three Pokemon's gates are the keeper's and the level cap's, not dialogue).
FLAGS = {"pips_gym": {"gym%d_cleared" % n for n in range(4, 9)}}
# The flags a reward must sit behind: Pip's Twig Badge (the Shiny Stone) only at all eight (pips_gym situation).
GRANT_FLAGS = {"pips_gym": {"gym8_cleared"}}

jload = SA.jload
Report = SA.Report


# ------------------------------------------------------------------ what the record says is built


def _clearing(E, p):
    """The one piece this record adds: a square of half-width r round `at`, from the lowest ground under it + 1 to the
    highest + up, cleared of logs, leaves and plants. Every column must be dry (#minecraft:replaceable holds water)."""
    ox, oz = p.get("at") or (0, 0)
    r = int(p["r"])
    x0, z0, x1, z1 = E.cx + ox - r, E.cz + oz - r, E.cx + ox + r, E.cz + oz + r
    cols = [(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)]
    wet = [c for c in cols if E.water(*c) is not None]
    gs = [E.g(x, z) for x, z in cols]
    E.clearings.append((p["name"], (x0, min(gs) + 1, z0, x1, max(gs) + int(p["up"]), z1), wet))


def expect(r, g, water):
    E = SA.Expect(r, g, water)
    E.clearings = []
    for p in r["pieces"]:
        k = p["kind"]
        if k == "clearing":
            _clearing(E, p)
        elif k == "structure":
            SA._structure(E, p)
        elif k == "surface":
            SA._surface(E, p)
        elif k == "ground_blocks":
            SA._ground_blocks(E, p["name"], p, *(p["at"]))
        elif k == "ring":
            SA._ring(E, p)
        elif k == "posts":
            SA._posts(E, p)
        else:
            E.problems.append("unknown piece kind %s" % k)
    return E


spot = SA.spot


def spots_of(r, E):
    s = {"caches": [spot(E, c["at"]) for c in r.get("caches") or []]}
    if r.get("pokemon"):
        s["anchor"] = spot(E, r["pokemon"]["at"])
    if r.get("npc"):
        s["npc"] = spot(E, r["npc"]["at"])
    return s


def extent(E, spots):
    """[x0, z0, x1, z1] over every expected block, clearing box and spot: the box the record's bbox must be."""
    xs = [p[0] for p in E.all()] + [c[1][0] for c in E.clearings] + [c[1][3] for c in E.clearings]
    zs = [p[2] for p in E.all()] + [c[1][2] for c in E.clearings] + [c[1][5] for c in E.clearings]
    for s in [spots.get("anchor"), spots.get("npc")] + list(spots.get("caches") or []):
        if s:
            xs.append(s[0])
            zs.append(s[2])
    return [min(xs), min(zs), max(xs), max(zs)] if xs else None


# ------------------------------------------------------------------ the checks this record adds


def check_standing(r, E, spots, rep):
    """Not under water, not floating: each anchor and NPC on a dry column, over the heightmap's ground or a block the
    record builds, with its feet above the ground."""
    for who, s in (("anchor", spots.get("anchor")), ("npc", spots.get("npc"))):
        if not s:
            continue
        x, y, z = s
        if y is None:
            rep.err("ys", "%s: the %s at (%d, %d) has no standing room" % (r["id"], who, x, z))
            continue
        if E.water(x, z) is not None:
            rep.err("ys", "%s: the %s stands on a wet column (%d, %d), water y%d" % (r["id"], who, x, z, E.water(x, z)))
        gy = E.g(x, z)
        under = E.final((x, y - 1, z))
        if y <= gy:
            rep.err("ys", "%s: the %s's feet y%d are at or under the ground y%d" % (r["id"], who, y, gy))
        elif y - 1 != gy and (under is None or under <= SA.PASSABLE):
            rep.err("ys", "%s: the %s floats at y%d over ground y%d with nothing built under it" % (r["id"], who, y, gy))


def check_bbox(r, E, spots, rep):
    """The record's bbox is the box R9NR forceloads and other builders check against: it must hold every block,
    clearing and spot the record implies. Larger is a note (a structure's own clear reaches a block past its footprint,
    the generator's convention, and southern_residents_audit's check_writes already holds every written clear to it)."""
    want = extent(E, spots)
    x0, z0, x1, z1 = r["bbox"]
    if want is None:
        return
    if not (x0 <= want[0] and z0 <= want[1] and want[2] <= x1 and want[3] <= z1):
        rep.err("ys", "%s: the record's bbox %s does not hold what the record builds, %s" % (r["id"], r["bbox"], want))
    elif want != list(r["bbox"]):
        rep.note("%s: the record's bbox %s is larger than the blocks, clearings and spots, %s" % (r["id"], r["bbox"], want))


def check_clearings(r, E, R, text, rep):
    i = r["id"]
    have = {}
    for c in R.clears:
        have.setdefault(tuple(c[:6]), set()).add(c[7])
    for name, box, wet in E.clearings:
        if wet:
            rep.err("clearing", "%s %s: the clearing covers %d wet column(s), e.g. %s" % (i, name, len(wet), wet[:3]))
        tags = have.get(tuple(box), set())
        if set(CLEAR_TAGS) - tags:
            near = [k for k in have if k[0] == box[0] and k[2] == box[2] or k[3] == box[3] and k[5] == box[5]]
            rep.err("clearing", "%s %s: the box %s is not cleared of %s (clears over that square: %s)"
                    % (i, name, list(box), sorted(set(CLEAR_TAGS) - tags), near[:2]))
    # order: a clear that runs after a write it covers takes that block away again
    written = []
    for line in SA._code(text):
        f = SA.FILL.match(line)
        if f and f.group(8) is not None:
            c = [int(v) for v in f.groups()[:6]]
            lo = (min(c[0], c[3]), min(c[1], c[4]), min(c[2], c[5]))
            hi = (max(c[0], c[3]), max(c[1], c[4]), max(c[2], c[5]))
            hit = [p for p in written if all(lo[k] <= p[k] <= hi[k] for k in range(3))]
            if hit:
                rep.err("clearing", "%s: a clear %s runs after the write at %s it covers" % (i, lo + hi, hit[0]))
                return
        else:
            m = SA.SET.match(line)
            if m:
                written.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
            elif f:
                c = [int(v) for v in f.groups()[:6]]
                written.append((min(c[0], c[3]), min(c[1], c[4]), min(c[2], c[5])))
                written.append((max(c[0], c[3]), max(c[1], c[4]), max(c[2], c[5])))


def authored(doc, data):
    return SA.authored(doc, data, record=RECORD)


def _row_line(data):
    gr = jload("world.json", data)["grid"]
    return gr["origin_z"] + gr["row_labels"].index("E") * gr["cell_size"]


def _cell(x, z, data):
    gr = jload("world.json", data)["grid"]
    c, w = int((x - gr["origin_x"]) // gr["cell_size"]), int((z - gr["origin_z"]) // gr["cell_size"])
    if 0 <= c < len(gr["column_labels"]) and 0 <= w < len(gr["row_labels"]):
        return gr["row_labels"][w] + gr["column_labels"][c]
    return None


def check_siting(doc, r, cols, spots, A, rep, data):
    import numpy as np
    i, rules = r["id"], doc["rules"]
    pts, rects = A
    C = np.array(sorted(cols), float)
    P = np.array([(a, b) for a, b, _f in pts], float)
    best = (1e18, None, None)
    for k in range(0, len(C), 128):
        blk = C[k:k + 128]
        d = np.hypot(P[None, :, 0] - blk[:, None, 0], P[None, :, 1] - blk[:, None, 1])
        j = np.unravel_index(np.argmin(d), d.shape)
        if d[j] < best[0]:
            best = (float(d[j]), tuple(int(v) for v in blk[j[0]]), pts[j[1]][2])
    for x0, z0, x1, z1, f in rects:
        dx = np.maximum(np.maximum(x0 - C[:, 0], C[:, 0] - x1), 0)
        dz = np.maximum(np.maximum(z0 - C[:, 1], C[:, 1] - z1), 0)
        d = np.hypot(dx, dz)
        j = int(np.argmin(d))
        if d[j] < best[0]:
            best = (float(d[j]), tuple(int(v) for v in C[j]), f + " (box %s)" % [x0, z0, x1, z1])
    if best[0] < rules["authored_clearance"]:
        rep.err("siting", "%s: (%d, %d) is %.0f blocks from an x/z authored in data/%s (needs %d)"
                % (i, best[1][0], best[1][1], best[0], best[2], rules["authored_clearance"]))
    rep.note("%s: nearest authored x/z %.0f, our column %s, in data/%s" % (i, best[0], best[1], best[2]))
    m = rules["authored_clearance"]
    for t in jload("towns.json", data)["towns"]:
        f = t.get("footprint") or {}
        if f.get("min_x") is None:
            continue
        if any(f["min_x"] - m <= x <= f["max_x"] + m and f["min_z"] - m <= z <= f["max_z"] + m for x, z in cols):
            rep.err("siting", "%s: within %d of town %s's footprint" % (i, m, t["id"]))
    for k, zone in jload("rift_zones.json", data)["zones"].items():
        for bx in zone.get("boxes") or []:
            if any(bx[0] <= x <= bx[2] and bx[1] <= z <= bx[3] for x, z in cols):
                rep.err("siting", "%s: inside Rift zone %s" % (i, k))
                break
    line = _row_line(data)
    if rules.get("north_of_z") != line:
        rep.err("siting", "rules.north_of_z %s is not row E's first z %d (data/world.json grid)" % (rules.get("north_of_z"), line))
    south = [c for c in cols if c[1] >= line]
    if south:
        rep.err("siting", "%s: %d column(s) at or south of z %d (rows E-H), e.g. %s" % (i, len(south), line, sorted(south)[:2]))
    # the hearts' rule: a big Pokemon, and the people who frame it, off the road
    clear = jload("encounter_design.json", data)["rules"]["hearts"]["clear_of_path_blocks"]
    if rules.get("path_clearance") != clear:
        rep.err("siting", "rules.path_clearance %s is not rules.hearts.clear_of_path_blocks %d" % (rules.get("path_clearance"), clear))
    paths = np.array([p[:2] for pl in jload("route_paths.json", data)["paths"].values() for p in pl], float)
    cx, cz = r["site"]["centre"]
    who = [("the centre", (cx, cz))] + [("the %s" % k, (spots[k][0], spots[k][2])) for k in ("anchor", "npc") if spots.get(k)]
    for name, (x, z) in who:
        d = float(np.min(np.hypot(paths[:, 0] - x, paths[:, 1] - z)))
        if d < clear:
            rep.err("siting", "%s: %s (%d, %d) is %.0f blocks from a route path (needs %d)" % (i, name, x, z, d, clear))
    dmin = float(min(np.min(np.hypot(paths[:, 0] - x, paths[:, 1] - z)) for x, z in cols))
    rep.note("%s: nearest route path to any column %.0f" % (i, dmin))
    if _cell(cx, cz, data) != r.get("cell"):
        rep.err("siting", "%s: the centre (%d, %d) is in cell %s, the record says %s" % (i, cx, cz, _cell(cx, cz, data), r.get("cell")))
    sub = SA._subregion(cx, cz, data)[0]
    if sub != r.get("subregion"):
        rep.err("siting", "%s: the centre is in sub-region %s, the record says %s" % (i, sub, r.get("subregion")))


def check_objective(doc, rep, data):
    """The keeper's objective is this pack's alone: no other data record or tool names it (this audit reads it from the
    record, so it never names it either)."""
    obj = doc["build"]["objective"]
    for p in sorted(Path(data).glob("*.json")):
        if p.name == RECORD:
            continue
        if re.search(r'"objective"\s*:\s*"%s"' % re.escape(obj), p.read_text(encoding="utf-8")):
            rep.err("keeper", "the objective %s is also data/%s's" % (obj, p.name))
    for p in sorted((ROOT / "tools").glob("*.py")):
        if p.stem in (GENERATOR, Path(__file__).stem):
            continue
        if obj in p.read_text(encoding="utf-8"):
            rep.err("keeper", "the objective %s is also named by tools/%s" % (obj, p.name))


# ------------------------------------------------------------------ the dialogue facts the places promise


def _norm(s):
    return " ".join(re.sub(r"[^a-z0-9 ]", "", s.lower().replace("-", " ")).split())


def _sign_text(lines):
    """A sign's words; a last line that is a signature ('- E.') is the carver's mark, not the reading."""
    lines = [l for l in lines if l.strip()]
    if lines and lines[-1].strip().startswith("-"):
        lines = lines[:-1]
    return _norm(" ".join(lines))


def _said(text):
    m = re.search(r"'(.+)'", text or "")
    return _norm(m.group(1) if m else text or "")


def check_carving(doc, r, rep, data):
    """Agnes: r_back reads the oak's north face (the back, away from the wagon) word for word, r_front its south face,
    and r_wrong neither."""
    i = r["id"]
    oak = [p for p in r["pieces"] if p["kind"] == "ground_blocks" and "oak" in p["name"] and "glade" not in p["name"]]
    faces = {}
    for p in oak:
        for dx, dy, dz, v in p.get("hung") or []:
            if isinstance(v, dict) and v.get("sign", {}).get("wall"):
                faces[v["sign"]["wall"]] = (p["at"], dz, _sign_text(v["sign"]["lines"]))
    if set(faces) != {"north", "south"}:
        rep.err("dialogue", "%s: the oak has signs on %s, not one north and one south" % (i, sorted(faces)))
        return
    if not (faces["north"][1] < 0 < faces["south"][1]):
        rep.err("dialogue", "%s: the back carving is not on the oak's north side" % i)
    if not (faces["north"][0][1] + r["site"]["centre"][1] < r["npc"]["feet"][2]):
        rep.err("dialogue", "%s: the oak is not north of Agnes" % i)
    conv = {c["id"]: c for c in jload("dialogue.json", data)["conversations"]}.get(r["records"]["conversation"])
    resp = {x["id"]: x for n in (conv or {}).get("nodes", []) for x in n.get("responses") or []}
    for rid, face in (("r_back", "north"), ("r_front", "south")):
        got = _said((resp.get(rid) or {}).get("text"))
        if got != faces[face][2]:
            rep.err("dialogue", "%s: %s says %r, the oak's %s face reads %r" % (i, rid, got, face, faces[face][2]))
    wrong = _said((resp.get("r_wrong") or {}).get("text"))
    if not wrong or wrong in (faces["north"][2], faces["south"][2]):
        rep.err("dialogue", "%s: r_wrong (%r) is missing or reads the oak" % (i, wrong))


def _visible(c, badges):
    """A condition under a player with gym1..gym<badges> cleared; anything not a flag counts as met."""
    if not c:
        return True
    k = c.get("kind")
    if k == "all":
        return all(_visible(x, badges) for x in c["conditions"])
    if k == "any":
        return any(_visible(x, badges) for x in c["conditions"])
    if k == "not":
        return not _visible(c["condition"], badges)
    if k == "flag":
        m = re.fullmatch(r"gym(\d)_cleared", c["flag"])
        return bool(m) and int(m.group(1)) <= badges
    return True


def check_badges(doc, r, rep, data):
    """Pip: with N badges exactly one of her r_bN is shown, r_b<N> for N = 4..8 and r_b0 below four."""
    i = r["id"]
    conv = {c["id"]: c for c in jload("dialogue.json", data)["conversations"]}.get(r["records"]["conversation"])
    opts = {x["id"]: x for n in (conv or {}).get("nodes", []) for x in n.get("responses") or [] if re.fullmatch(r"r_b\d", x["id"])}
    for n in range(0, 9):
        shown = sorted(k for k, x in opts.items() if _visible(x.get("visible_when"), n))
        want = ["r_b%d" % n] if n >= 4 else ["r_b0"]
        if shown != want:
            rep.err("dialogue", "%s: with %d badge(s) Pip shows %s, expected %s" % (i, n, shown, want))


def _tag_gated(q, tid, tag, depth=0):
    """True when transition tid of quest q runs only for a player carrying `tag`: it reads the tag, or it requires a
    field every setter of which is itself behind the tag."""
    if depth > 6:
        return False
    tr = {t["id"]: t for t in q["transitions"]}[tid]
    leaves = [x for c in tr["conditions"] for x in SA._conds(c)]
    if any(c.get("kind") == "player_tag" and c.get("tag") == tag for c in leaves):
        return True
    for c in leaves:
        if c.get("kind") == "progression_equals" and c.get("value") is True:
            setters = [t["id"] for t in q["transitions"] if any(
                e["kind"] == "set_progression" and e["field"] == c["field"] and e["value"] is True for e in t["effects"])]
            if setters and all(_tag_gated(q, s, tag, depth + 1) for s in setters):
                return True
    return False


def check_tag_pair(doc, fns, rep, data, compile_fn):
    """The one fact two quests share: the finder's transition runs the pack's player_tag function, which only tags the
    player; every quest that reads the tag gates its option and its grant on it, and its compiled dialogue probes it."""
    b = doc["build"]
    qs = {q["id"]: q for q in jload("quests.json", data)["quests"]}
    dl = {c["id"]: c for c in jload("dialogue.json", data)["conversations"]}
    for r in doc["residents"]:
        pt = r.get("player_tag")
        if not pt:
            continue
        i, tag = r["id"], pt["tag"]
        fid = "%s:%s/%s" % (b["namespace"], b["folder"], pt["function"])
        body = SA._code(fns.get(pt["function"], ""))
        if body != ["tag @s add %s" % tag]:
            rep.err("dialogue", "%s: the pack's %s is %s, not exactly 'tag @s add %s'" % (i, fid, body, tag))
        q = qs.get(r["records"]["quest"]) or {"transitions": []}
        runs = [t["id"] for t in q["transitions"] if any(e.get("kind") == "function" and e.get("function") == fid for e in t["effects"])]
        if len(runs) != 1:
            rep.err("dialogue", "%s: %d transition(s) of %s run %s, expected 1" % (i, len(runs), q.get("id"), fid))
        else:
            try:
                files = compile_fn(r["records"]["conversation"], data)
            except SystemExit as e:
                files = {}
                rep.err("dialogue", "%s: %s does not compile: %s" % (i, r["records"]["conversation"], e))
            if fid not in json.dumps(files):
                rep.err("dialogue", "%s: the compiled %s never runs %s" % (i, r["records"]["conversation"], fid))
        readers = [x for x in doc["residents"] if x is not r and tag in json.dumps(qs.get((x.get("records") or {}).get("quest")) or {})]
        if not readers:
            rep.err("dialogue", "%s: no other resident's quest reads the tag %s" % (i, tag))
        for x in readers:
            xq, xc = qs[x["records"]["quest"]], dl.get(x["records"]["conversation"]) or {"nodes": []}
            for t in xq["transitions"]:
                if any(e["kind"] == "grant_reward_once" for e in t["effects"]) and not _tag_gated(xq, t["id"], tag):
                    rep.err("dialogue", "%s: %s.%s grants a reward without requiring the tag %s" % (x["id"], xq["id"], t["id"], tag))
            gated = {t["id"] for t in xq["transitions"] if _tag_gated(xq, t["id"], tag)}
            for n in xc["nodes"]:
                for resp in n.get("responses") or []:
                    run = {a["transition"] for a in resp.get("actions") or [] if a.get("kind") == "quest_transition"}
                    seen = {c.get("tag") for c in SA._conds(resp.get("visible_when") or {}) if c.get("kind") == "player_tag"}
                    if run & gated and tag not in seen:
                        rep.err("dialogue", "%s: option %s runs %s and is shown without the tag %s" % (x["id"], resp["id"], sorted(run), tag))
            if not gated:
                rep.err("dialogue", "%s: no transition of %s requires the tag %s" % (x["id"], xq["id"], tag))
            try:
                files = compile_fn(x["records"]["conversation"], data)
            except SystemExit:
                files = {}
            if tag not in json.dumps(files):
                rep.err("dialogue", "%s: the compiled %s never probes the tag %s" % (x["id"], x["records"]["conversation"], tag))


# ------------------------------------------------------------------ tools/reapply.py


def check_wiring(doc, rep, text=None):
    """The re-application runs this generator's steps where the record says, and prepare runs it and this audit."""
    text = text if text is not None else (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    st = doc["build"]["steps"]
    pack = doc["build"]["pack"]
    jobs = [m.group(1) for m in re.finditer(r'add\("([^"]+)",\s*"[^"]+\.py"', text)]
    for j in (GENERATOR, GENERATOR + "_audit"):
        if j not in jobs:
            rep.err("wiring", "tools/reapply.py has no prepare job %s" % j)
    if GENERATOR in jobs and GENERATOR + "_audit" in jobs and jobs.index(GENERATOR) > jobs.index(GENERATOR + "_audit"):
        rep.err("wiring", "the prepare job %s_audit runs before the generator it audits" % GENERATOR)
    m = re.search(r'add\("%s_audit",\s*"([^"]+)"' % GENERATOR, text)
    if m and m.group(1) != Path(__file__).name:
        rep.err("wiring", "the prepare job %s_audit runs %s" % (GENERATOR, m.group(1)))
    order = [m.group(1) for m in re.finditer(r'out\.append\(\("(R[0-9A-Z]+)"', text)]
    calls = {m.group(1): m.group(2) for m in re.finditer(
        r'out\.append\(\("(R[0-9A-Z]+)",\s*"[^"]*",\s*\n?\s*([A-Za-z_]+\.[A-Za-z_]+)\(\)\)\)', text)}
    for step, fn, after, before in ((st["blocks"], "placement_steps", "R9SR", "R9E"),
                                    (st["entities"], "entity_steps", "R18SR", None)):
        if order.count(step) != 1:
            rep.err("wiring", "tools/reapply.py appends step %s %d times" % (step, order.count(step)))
            continue
        if calls.get(step) != "%s.%s" % (GENERATOR, fn):
            rep.err("wiring", "step %s is %s, not %s.%s()" % (step, calls.get(step), GENERATOR, fn))
        k = order.index(step)
        if after in order and order.index(after) > k:
            rep.err("wiring", "step %s runs before %s" % (step, after))
        if before and before in order and order.index(before) < k:
            rep.err("wiring", "step %s runs after %s" % (step, before))
    tree = ast.parse(text)
    for name in ("SERVER_PACKS", "WORLD_LOCAL"):
        vals = None
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
                try:
                    vals = ast.literal_eval(node.value)
                except ValueError:
                    vals = None
        if vals is None or pack not in vals:
            rep.err("wiring", "%s is not in tools/reapply.py %s" % (pack, name))


# ------------------------------------------------------------------ the whole audit


def audit(doc, ground, water, pack, steps, data=DATA, compile_fn=None, reapply_text=None):
    """`water(x, z)` is the water surface y or None; `steps` are the generator's R9NR + R18NR."""
    rep = Report()
    compile_fn = compile_fn or SA._compile
    if doc.get("schema") != SCHEMA:
        rep.err("spec", "schema %s, expected %s" % (doc.get("schema"), SCHEMA))
    check_wiring(doc, rep, reapply_text)
    b = doc["build"]
    fdir = Path(pack) / "data" / b["namespace"] / "function" / b["folder"]
    if not fdir.is_dir():
        rep.err("pack", "%s is missing: run tools/northern_residents.py first" % fdir)
        return rep
    fns = SA.load_pack(pack, b["namespace"], b["folder"])
    import function_limits
    for name, text in fns.items():
        if name.startswith("__"):
            continue
        for n, cmd, why in function_limits.check_lines(text.splitlines(), where=name):
            rep.err("functions", "%s:%d %s" % (name, n, why))
    spawn = set(jload("spawn_blocks.json", data)["blocks"])
    pol = jload("spawn_block_policy.json", data)
    whitelist = {x for w in pol.get("whitelist") or [] if "northern_residents" in (w.get("scope") or "") for x in w["blocks"]}
    A = authored(doc, data)
    spots_by_id, keeper_built = {}, []
    for r in doc["residents"]:
        E = expect(r, ground, water)
        spots = spots_of(r, E)
        spots_by_id[r["id"]] = spots
        SA.check_ys(doc, r, E, spots, rep, data)
        check_standing(r, E, spots, rep)
        check_bbox(r, E, spots, rep)
        text = fns.get("%s/build" % r["id"])
        if text is None:
            rep.err("writes", "%s has no build function" % r["id"])
            continue
        R = SA.Replay(text)
        SA.check_writes(doc, r, E, R, spots, rep, data, spawn, whitelist)
        check_clearings(r, E, R, text, rep)
        cols = R.columns() | E.cols | {(s[0], s[2]) for k in ("anchor", "npc") if spots.get(k) for s in [spots[k]]} \
            | {(s[0], s[2]) for s in spots["caches"]}
        for _n, c, _w in E.clearings:
            cols |= {(x, z) for x in range(c[0], c[3] + 1) for z in range(c[2], c[5] + 1)}
        check_siting(doc, r, cols, spots, A, rep, data)
        if r.get("pokemon"):
            SA.check_resident(doc, r, spots["anchor"], rep, data)
            if spots["anchor"][1] is not None:
                keeper_built.append((r, spots["anchor"]))
        if r.get("npc"):
            SA.check_dialogue(doc, r, rep, data, compile_fn, flags_named=FLAGS.get(r["id"], set()),
                              grant_flags=GRANT_FLAGS.get(r["id"]))
        if r["id"] == "agnes_carving":
            check_carving(doc, r, rep, data)
        if r["id"] == "pips_gym":
            check_badges(doc, r, rep, data)
    SA.check_keeper(doc, keeper_built, fns, rep, data)
    check_objective(doc, rep, data)
    SA.check_steps(doc, spots_by_id, steps, rep, data, npc_step=b["steps"]["entities"])
    for s in steps:
        if s[0] == "fn":
            ns, _, path = s[1].partition(":")
            rel = path[len(b["folder"]) + 1:] if path.startswith(b["folder"] + "/") else None
            if ns != b["namespace"] or rel not in fns:
                rep.err("steps", "the step runs function %s, which the pack does not have" % s[1])
    check_tag_pair(doc, fns, rep, data, compile_fn)
    # every function is reached: the load tag, the keeper loop, the steps, and the player_tag functions a quest runs
    qtext = json.dumps(jload("quests.json", data))
    todo = ["load"] + [s[1].split(":", 1)[1].split("/", 1)[1] for s in steps if s[0] == "fn"]
    todo += [r["player_tag"]["function"] for r in doc["residents"] if r.get("player_tag")
             and "%s:%s/%s" % (b["namespace"], b["folder"], r["player_tag"]["function"]) in qtext]
    reached = set()
    while todo:
        f = todo.pop()
        if f in reached or f not in fns:
            continue
        reached.add(f)
        todo += re.findall(r"function %s:%s/(\S+)" % (b["namespace"], b["folder"]), fns[f])
    for f in sorted(set(fns) - reached - {"__load_tag__"}):
        rep.err("functions", "%s is reached by nothing" % f)
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack", default=None, help="default build/datapacks/cobblers_northern_residents; when that is "
                                                  "absent the generator is run into a temporary folder and that is audited")
    ap.add_argument("--source-root")
    ap.add_argument("-v", "--verbose", action="store_true", help="print the notes too")
    a = ap.parse_args(argv)
    import ground as G
    doc = jload(RECORD)
    g = G.load(a.source_root)
    try:
        import northern_residents as NR       # for its OUTPUT only: the steps it hands tools/reapply.py
        nd = NR.load()
        steps = NR.placement_steps(nd, g) + NR.entity_steps(nd, g)
    except SystemExit as e:
        print("PROBLEM steps: the generator refuses to give its steps: %s" % e)
        return 1
    pack = Path(a.pack) if a.pack else PACK
    tmp = None
    if a.pack is None and not PACK.is_dir():
        tmp = tempfile.TemporaryDirectory()
        pack = Path(tmp.name) / "cobblers_northern_residents"
        cmd = [sys.executable, str(ROOT / "tools" / "northern_residents.py"), "--out", str(pack)]
        if a.source_root:
            cmd += ["--source-root", a.source_root]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print("PROBLEM pack: %s is absent and the generator refuses to write one: %s"
                  % (PACK, (res.stdout + res.stderr).strip()[-400:]))
            return 1
        print("northern_residents_audit: %s is absent; auditing the generator's output written to a temporary folder" % PACK)
    water = SA.Water(g, [tuple(r["site"]["centre"]) for r in doc["residents"]])
    rep = audit(doc, g, water, pack, steps)
    if tmp is not None:
        tmp.cleanup()
    if a.verbose:
        for n in rep.notes:
            print("note: %s" % n)
    for e in rep.errors:
        print("PROBLEM %s" % e)
    print("northern_residents_audit: %s" % ("clean" if not rep.errors else "%d problem(s)" % len(rep.errors)))
    return 1 if rep.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

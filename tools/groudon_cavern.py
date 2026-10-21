#!/usr/bin/env python
"""Groudon's quake cavern under the Craters' eastern bowl, from data/groudon_cavern.json
(docs/world-building/GROUDON_QUAKE_CAVERN.md). RETIRED 2026-10-21: this module now only UNDOES it.

THE RETIREMENT (the owner, 2026-10-21: "undo groudon cave", then "Old chamber back"). R14L applied the cavern to the live
world at 01:16 that day and the quake opened it fully. Groudon's record in data/legendaries.json is a sealed_chamber at
(6672, 5508) again, and the cavern is that record's retired site `quake_cavern_v1`. This module emits:
  - the cleanup (retire_functions), which tools/legendaries.py puts in cobblers_legendaries and R14L runs BEFORE any
    summon, in the retired-site shape (tools/chunk_look.py look-then-act): it refuses while a player stands in the ravine,
    the plug, the tunnel or the hall (and the step reads the held count back, so R14L stops); kills the cavern's tagged
    Groudon in the model box; and, only while the cavern is there (#built is 1, or its pedestal stands), puts every cell
    the carve and the three cuts wrote at or under the ground back to the heightmap's terrain (`terrain` of the retired
    site), clears the rim's walls with `replace` (nothing else above the ground is written: the hand-placed stones that
    stopped the water stay), clears the chamber's open score so its carve_once re-cuts it, and sets #built and #quake to 0
    LAST, after the pedestal, so a run cut short runs again and a second run writes nothing;
  - `build`: the record of what the world RECEIVED (build/groudon_cavern_applied/, never a datapack and never installed):
    the carve and the three stages exactly as R14L and the quake ran them. Its sha256 is frozen in the retired site
    (`applied.sha256`), so a later edit to the model below cannot silently change what the cleanup thinks it undoes;
    tools/groudon_revert_audit.py replays it, then the cleanup, onto the heightmap;
  - `probes`: data/world_probes.json places.groudon_revert, blocks that read rock once the cleanup ran.
The runtime pack (rumble, stages, keeper) and the carve's build pack are no longer emitted or installed
(tools/reapply.py WITHDRAWN moves an installed copy aside).

What follows is the cavern as it was built, kept verbatim because the cleanup must undo exactly that.

The owner, 2026-10-20: "this crater should just have a large cave mouth that opens up after gym 8 is beaten, call it an
earthquake or something". Chosen: the FIRST player on the server to hold gym8_cleared sets it off for the whole world; it
stays open for ever; anyone may walk in, a keeper turns away anyone in the hall without the flag; a grand magma cavern
(a ravine from the bowl, a descending lit tunnel, a hall 56 across with a lava lake and Groudon on a basalt dais).

WHERE IT SITS IN THE LADDER (CLAUDE.md principle 6): functions/commands. Cobblemon, an addon, the pack, config and a
datapack have nothing to open a hole in the ground on a world event; a scoreboard, advancement selectors, `fill` and a
20-tick self-scheduled function do. Groudon's ENTITY (summon, dormant NBT, `met`, the look-then-act chain, the retired
chamber's cleanup, the Red Orb's pedestal) stays tools/legendaries.py's: the record is kind `quake_cavern` and this module
supplies its geometry and the functions only the cavern can write.

TWO PACKS (the owner's heap rule: every function line of a loaded pack stays parsed in the heap):
  cobblers_groudon_cavern        the runtime: load, tick (rumble, the opening's stages, the keeper), eject, the stages (a few
                                 hundred lines: the ravine and the plug are cut at play time, not at apply time)
  cobblers_groudon_cavern_build  the one-shot carve: the envelope and skin, the air, the lava, split into parts, and the
                                 R14L entry `cobblers:legendary/groudon/carve_once`; tools/pack_split.py moves it and
                                 tools/reapply.py strip takes it out of the heap after the run

THE MODEL. A numpy grid over `box`. Interior air (`ia`: the tunnel and the hall) is carved at apply time, inside a stone
envelope filled FIRST that reaches `margin` blocks beyond every void in all six directions (that is the seal, by
construction). The quake's air (`qa`: the open-sky ravine and the plug) is cut at play time from natural terrain. Ground is
tools/ground.py's, rounded, never a world.

  python tools/groudon_cavern.py build [--source-root R] [--out DIR]   write the record of what the world received
  python tools/groudon_cavern.py report                                the numbers; nothing written
  python tools/groudon_cavern.py probes                                write data/world_probes.json places.groudon_revert

What it does NOT cover: the surface blocks and sub-surface strata of the natural terrain (the heightmap has heights, not
block ids: the ravine's walls and floor are whatever is there; nothing here assumes a block), a player who logs out inside
the hall and back in after losing nothing (the keeper's pass sends an unqualified one out whenever it sees them), a Groudon
caught and released elsewhere, and anything in a running game. tools/groudon_revert_audit.py is the independent audit of the
cleanup: it does not import this module.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import function_limits as FL  # noqa: E402

DATA = ROOT / "data" / "groudon_cavern.json"
LEGENDARIES = ROOT / "data" / "legendaries.json"
PROBES = ROOT / "data" / "world_probes.json"
PACK = "cobblers_groudon_cavern"          # WITHDRAWN 2026-10-21 (tools/reapply.py): never emitted or installed again
APPLIED = ROOT / "build" / "groudon_cavern_applied"   # the record of what the world received; not a datapack
OUT = APPLIED
SITE_ID = "quake_cavern_v1"               # data/legendaries.json groudon retired_sites
RETIRE_HELD = "cobblers_leg_retire_held"  # tools/legendaries.py RETIRE_HELD (tests/test_groudon_revert.py holds them equal)
SCHEMA = "cobblers.groudon_cavern/1"
NS = "cobblers"
FOLDER = "groudon_cavern"
F = "%s:%s" % (NS, FOLDER)
BUILD_PREFIX = F + "/build/"
CARVE_ONCE = "%s:legendary/groudon/carve_once" % NS
LOAD = "%s/load" % F
BUILT_READ = "%s/built_read" % F
BUILT_HOLDER = "groudon_cavern_built"     # #<holder> of tools/chunk_look.py's objective: R14L's read-back of #built
CL_OBJ = "cobblers_chunk_look"            # tools/chunk_look.py OBJ
PACK_FORMAT = 48
PART_COMMANDS = 4000
FILL_LIMIT = 32768
HEAD = "# Generated by tools/groudon_cavern.py from data/groudon_cavern.json; never edit (build/ is regenerated)."
AIR = "minecraft:air"
LAVA = "minecraft:lava"
M32 = 0xFFFFFFFF


class CavernError(SystemExit):
    pass


def _j(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load(path=DATA):
    doc = _j(path)
    if doc.get("schema") != SCHEMA:
        raise CavernError("%s: schema must be %s" % (path, SCHEMA))
    return doc


# ------------------------------------------------------------------------------------------------------------ noise


def _mix(v):
    """A 32-bit integer mixer on int64 arrays (every product stays under 2**63)."""
    v = np.asarray(v, dtype=np.int64) & M32
    v = ((v ^ (v >> 16)) * 0x7FEB352D) & M32
    v = ((v ^ (v >> 15)) * 0x6C8E9CF5) & M32
    return (v ^ (v >> 16)) & M32


def h01(*keys):
    """A stable hash in [0, 1) of integers, elementwise when any key is an array."""
    acc = 0x2545F491
    for k in keys:
        acc = _mix(((acc * 0x1E3779B1) & M32) ^ (np.asarray(k, dtype=np.int64) & M32))
    return np.asarray(acc, dtype=np.float64) / 4294967296.0


def vn1(seed, t):
    """Smooth 1-D value noise in [0, 1), a knot per integer of t."""
    t = np.asarray(t, dtype=np.float64)
    i = np.floor(t).astype(np.int64)
    f = t - i
    s = f * f * (3.0 - 2.0 * f)
    return h01(seed, i) * (1.0 - s) + h01(seed, i + 1) * s


def vn2(seed, x, z):
    x = np.asarray(x, dtype=np.float64)
    z = np.asarray(z, dtype=np.float64)
    i, k = np.floor(x).astype(np.int64), np.floor(z).astype(np.int64)
    fx, fz = x - i, z - k
    sx, sz = fx * fx * (3.0 - 2.0 * fx), fz * fz * (3.0 - 2.0 * fz)
    a = h01(seed, i, k) * (1.0 - sx) + h01(seed, i + 1, k) * sx
    b = h01(seed, i, k + 1) * (1.0 - sx) + h01(seed, i + 1, k + 1) * sx
    return a * (1.0 - sz) + b * sz


# ------------------------------------------------------------------------------------------------- data guards


def static_problems(doc, leg_doc=None):
    """[str] everything about the data that is wrong without building anything."""
    bad = []
    leg_doc = leg_doc or _j(LEGENDARIES)
    rec = next((r for r in leg_doc["encounters"] if r["id"] == doc["record"]), None)
    if rec is None:
        return ["data/legendaries.json has no encounter %r" % doc["record"]]
    # retired 2026-10-21: the record is a sealed chamber again and the cavern is its retired site
    site = next((s for s in rec.get("retired_sites") or [] if s.get("id") == SITE_ID), None)
    if site is None or site.get("kind") != "quake_cavern":
        bad.append("%s: no retired site %s of kind quake_cavern" % (rec["id"], SITE_ID))
        return bad
    if rec.get("kind") == "quake_cavern":
        bad.append("%s: the record is still a quake_cavern; the cavern is retired" % rec["id"])
    sp = doc["spine"]
    if list(site.get("portal") or []) != list(sp["lip"]):
        bad.append("%s %s: portal %s is not the spine's lip %s" % (rec["id"], SITE_ID, site.get("portal"), sp["lip"]))
    h, lk, ds = doc["hall"], doc["lake"], doc["dais"]
    hx, hz = h["centre"]
    reff = h["radius"] - h["wobble"]
    lx, lz = lk["centre"]
    dx_, dz_ = ds["centre"]
    if np.hypot(lx - hx, lz - hz) + lk["radius"] + 2 + 2 > reff:
        bad.append("the lake and its wall plus a 2-block path do not fit inside the hall's least radius %.1f" % reff)
    if np.hypot(dx_ - hx, dz_ - hz) + ds["outer_radius"] + 1 > reff:
        bad.append("the dais does not fit inside the hall's least radius %.1f" % reff)
    if np.hypot(dx_ - lx, dz_ - lz) < lk["radius"] + 1 + ds["outer_radius"] + 3:
        bad.append("the dais is within 3 blocks of the lake's wall")
    if lk["depth"] < 2:
        bad.append("lake.depth under 2")
    if int(doc["margin"]) < 4:
        bad.append("margin under 4 (WATER_BUILD_PLAN 4.5 audit 1)")
    g = doc["guard"]["box"]
    hb = hall_box(doc)
    if not (g[0] <= hb[0] and g[2] <= hb[2] and g[3] >= hb[3] and g[5] >= hb[5] and g[1] <= hb[1] and g[4] >= hb[4]):
        bad.append("the guard box %s does not cover the hall's box %s" % (g, hb))
    sx, sz = doc["guard"]["stand"]
    if g[0] <= sx <= g[3] and g[2] <= sz <= g[5]:
        bad.append("the guard's own stand is inside the guard box")
    b = doc["box"]
    if not (b["x"][0] <= hb[0] and hb[3] <= b["x"][1] and b["z"][0] <= hb[2] and hb[5] <= b["z"][1]):
        bad.append("the hall leaves data box")
    return bad


def retired_problems(doc, leg_doc, ground):
    """The LIVE sealed chamber's whole hull must stay clear of this model's box (2026-10-21, the other way round from
    before): R14L runs the cavern's cleanup first and then carves the chamber, and the cleanup must never write a cell of
    the chamber, nor its kill box hold the chamber's Groudon."""
    import legendaries as L
    bad = []
    b = doc["box"]
    box = (b["x"][0], b["y"][0], b["z"][0], b["x"][1], b["y"][1], b["z"][1])
    for rec in L.emitted(leg_doc):
        if rec["id"] != doc["record"]:
            continue
        hull = L.geometry(rec, leg_doc, ground)["bbox"]
        if all(box[i] <= hull[i + 3] and hull[i] <= box[i + 3] for i in range(3)):
            bad.append("the model box %s meets the live chamber's hull %s" % (box, hull))
    return bad


def hall_box(doc):
    """The hall's bounding box, from the data alone: inclusive (x0, y0, z0, x1, y1, z1) the pedestal and Groudon stand in."""
    h = doc["hall"]
    hx, hz = h["centre"]
    r = int(np.ceil(h["radius"] + h["wobble"]))
    f = int(h["floor_y"])
    return (hx - r, f + 1, hz - r, hx + r, f + int(h["wall"]) + int(h["dome"]) + 1, hz + r)


def model_box(doc):
    """The model's box as inclusive (x0, y0, z0, x1, y1, z1): every block the carve and the cuts wrote lies inside it."""
    b = doc["box"]
    return (b["x"][0], b["y"][0], b["z"][0], b["x"][1], b["y"][1], b["z"][1])


def pedestal(doc):
    """The dais's pedestal cell (the smooth_basalt the Red Orb sat in): the cleanup's probe, and its last block write."""
    cx, cz = doc["dais"]["centre"]
    return (int(cx), int(doc["hall"]["floor_y"]) + 2, int(cz))


# ----------------------------------------------------------------------------------------------------- the model


def project(px, pz, pts):
    """For every column (arrays px, pz) its nearest point on the polyline `pts`: (segment index, arclength S, distance D,
    signed side). Ties go to the earlier segment."""
    best_d = np.full(px.shape, np.inf)
    best_s = np.zeros(px.shape)
    best_i = np.zeros(px.shape, dtype=np.int32)
    best_side = np.zeros(px.shape)
    cum = 0.0
    for i, ((ax, az), (bx, bz)) in enumerate(zip(pts, pts[1:])):
        vx, vz = bx - ax, bz - az
        l2 = float(vx * vx + vz * vz)
        ln = l2 ** 0.5
        t = np.clip(((px - ax) * vx + (pz - az) * vz) / l2, 0.0, 1.0)
        qx, qz = ax + t * vx, az + t * vz
        d = np.hypot(px - qx, pz - qz)
        side = np.sign(vx * (pz - az) - vz * (px - ax))
        m = d < best_d
        best_d = np.where(m, d, best_d)
        best_s = np.where(m, cum + t * ln, best_s)
        best_i = np.where(m, i, best_i)
        best_side = np.where(m, side, best_side)
        cum += ln
    return best_i, best_s, best_d, best_side


def floor_profile(S, sp, ravine_len):
    """The floor's integer y at path length S: one block down per ravine_run blocks in the ravine, per tunnel_run below."""
    r1, r2 = float(sp["ravine_run"]), float(sp["tunnel_run"])
    at_end = sp["lip_y"] - np.floor(ravine_len / r1)
    return np.where(S <= ravine_len, sp["lip_y"] - np.floor(S / r1),
                    at_end - np.floor((S - ravine_len) / r2)).astype(np.int32)


def ravine_half_width(doc, S, side):
    rv = doc["ravine"]
    sd = doc["seed"] + (side > 0) * 7919
    return rv["half_width"] + rv["wobble"] * (2.0 * vn1(sd, np.asarray(S) / 4.0) - 1.0)


def tunnel_half_width(doc, S, side):
    t = doc["tunnel"]
    sd = doc["seed"] + 101 + (side > 0) * 6007
    return t["half_width"] + t["wobble"] * (2.0 * vn1(sd, np.asarray(S) / 3.0) - 1.0)


def tunnel_height(doc, D, w):
    t = doc["tunnel"]
    arch = np.sqrt(np.clip(1.0 - (D / w) ** 2, 0.0, 1.0))
    return np.rint(t["height_edge"] + (t["height_mid"] - t["height_edge"]) * arch).astype(np.int32)


def hall_radius(doc, PX, PZ):
    h = doc["hall"]
    return h["radius"] + h["wobble"] * (2.0 * vn2(doc["seed"] + 7, PX / 7.0, PZ / 7.0) - 1.0)


def hall_top(doc, r, reff, PX, PZ):
    """The hall's ceiling y over a column: wall + a dome that falls to the wall at the rim, a block of roughness."""
    h = doc["hall"]
    dome = np.rint(h["dome"] * np.sqrt(np.clip(1.0 - (r / reff) ** 2, 0.0, 1.0)))
    rough = h01(doc["seed"] + 3, PX, PZ)
    rough = np.where(dome >= 3, np.where(rough < 0.2, -1, np.where(rough > 0.8, 1, 0)), 0)
    return (h["floor_y"] + h["wall"] + dome + rough).astype(np.int32)


def parapet_columns(lake_c, sel_h):
    """The floor columns that carry a one-block wall round the lake: every neighbour of a lake column, diagonals too."""
    return dilate(lake_c, 1, (0, 1)) & ~lake_c & sel_h


def lava_top(doc):
    """The lava's top block: the floor's own level, so every side of it is floor and nothing can spread."""
    return int(doc["hall"]["floor_y"])


def envelope_margin(doc):
    return int(doc["margin"])


def accent_allowed(is_floor):
    """Magma blocks and shroomlights go in walls and roofs only: a magma block hurts the one who stands on it."""
    return not is_floor


def dilate_axis(m, n, ax):
    out = m.copy()
    for s in range(1, n + 1):
        a = [slice(None)] * m.ndim
        b = [slice(None)] * m.ndim
        a[ax], b[ax] = slice(s, None), slice(None, -s)
        out[tuple(a)] |= m[tuple(b)]
        out[tuple(b)] |= m[tuple(a)]
    return out


def dilate(m, n, axes):
    for ax in axes:
        m = dilate_axis(m, n, ax)
    return m


def face_adjacent(m):
    out = np.zeros_like(m)
    for ax in range(3):
        a = [slice(None)] * 3
        b = [slice(None)] * 3
        a[ax], b[ax] = slice(1, None), slice(None, -1)
        out[tuple(a)] |= m[tuple(b)]
        out[tuple(b)] |= m[tuple(a)]
    return out


class Model:
    pass


def build_model(doc, ground):
    bx = doc["box"]
    x0, x1 = bx["x"]
    y0, y1 = bx["y"]
    z0, z1 = bx["z"]
    nx, ny, nz = x1 - x0 + 1, y1 - y0 + 1, z1 - z0 + 1
    M = Model()
    M.o = (x0, y0, z0)
    M.shape = (nx, ny, nz)
    xs = np.arange(x0, x1 + 1)
    zs = np.arange(z0, z1 + 1)
    PX, PZ = np.meshgrid(xs.astype(np.float64), zs.astype(np.float64), indexing="ij")
    G = np.array([[ground(int(x), int(z)) for z in zs] for x in xs], dtype=np.int32)
    M.G = G
    Y3 = (y0 + np.arange(ny))[None, :, None]
    sp = doc["spine"]
    pts = [tuple(sp["lip"]), tuple(sp["ravine_end"]), tuple(sp["turn"]), tuple(sp["hall_entry"])]
    seg, S, D, SIDE = project(PX, PZ, pts)
    ravine_len = float(np.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]))
    P = floor_profile(S, sp, ravine_len)
    h = doc["hall"]
    F = int(h["floor_y"])

    def span(sel, lo, hi):
        return sel[:, None, :] & (Y3 >= lo[:, None, :]) & (Y3 <= hi[:, None, :])

    # ---- the ravine: open to the sky, cut from natural terrain at play time
    wr = ravine_half_width(doc, S, SIDE)
    sel_r = (seg == 0) & (D <= wr) & (P < G) & (S >= 0)
    rowtop = np.where(sel_r, G, -10_000).max(axis=0) + int(doc["ravine"]["top_pad"])
    TOP = np.broadcast_to(rowtop[None, :], G.shape)
    qa_r = span(sel_r, P + 1, TOP)
    M.ravine_cols = sel_r

    # ---- the plug (cut at play time) and the tunnel (carved at apply time): the same roofed profile
    wt = tunnel_half_width(doc, S, SIDE)
    ht = tunnel_height(doc, D, wt)
    sel_p = (seg == 1) & (D <= wt)
    qa_p = span(sel_p, P + 1, P + ht)
    fl_t = np.maximum(F, P)
    sel_t = (seg == 2) & (D <= wt)
    ia = span(sel_t, fl_t + 1, fl_t + ht)

    # ---- the hall
    r = np.hypot(PX - h["centre"][0], PZ - h["centre"][1])
    reff = hall_radius(doc, PX, PZ)
    sel_h = r <= reff
    ia |= span(sel_h, np.full(G.shape, F + 1, dtype=np.int32), hall_top(doc, r, reff, PX, PZ))

    # ---- lava, parapet, dais
    lk = doc["lake"]
    lake_c = np.hypot(PX - lk["centre"][0], PZ - lk["centre"][1]) <= lk["radius"]
    lake_c &= sel_h
    parapet_c = parapet_columns(lake_c, sel_h)
    lava = np.zeros(ia.shape, bool)
    lava |= span(lake_c, np.full(G.shape, F - int(lk["depth"]) + 1, dtype=np.int32),
                 np.full(G.shape, lava_top(doc), dtype=np.int32))
    ds = doc["dais"]
    rd = np.hypot(PX - ds["centre"][0], PZ - ds["centre"][1])
    ring_c = rd <= ds["outer_radius"]
    inner_c = rd <= ds["inner_radius"]
    j1, j2 = F + 1 - y0, F + 2 - y0
    feat = np.zeros(ia.shape, np.uint8)       # 1 parapet, 2 dais ring, 3 dais inner, 4 pedestal
    feat[:, j1, :][parapet_c] = 1
    feat[:, j1, :][ring_c] = 2
    feat[:, j2, :][inner_c] = 3
    cx, cz = ds["centre"]
    feat[cx - x0, j2, cz - z0] = 4
    ia &= feat == 0
    M.ia, M.qa_r, M.qa_p, M.lava, M.feat = ia, qa_r, qa_p, lava, feat
    M.seg, M.S, M.D = seg, S, D
    return M


def classify(doc, M):
    """The solid cells (envelope, skin, features) as an int16 block-id array, and the id -> block name list."""
    pal = doc["palette"]
    m = envelope_margin(doc)
    seed = doc["seed"]
    ia, lava = M.ia, M.lava
    D = dilate(ia | lava, m, (0, 1, 2))
    solid = D & ~ia & ~lava
    names = [None, pal["envelope"]] + list(dict.fromkeys(pal["floor"] + pal["wall"])) + [
        pal["light"], pal["magma"], pal["parapet"], pal["dais_ring"], pal["dais_inner"], doc.get("pedestal_block") or
        _j(LEGENDARIES)["defaults"]["pedestal_block"]]
    ix = {n: i for i, n in enumerate(names) if n}
    B = np.zeros(ia.shape, np.int16)
    B[solid] = ix[pal["envelope"]]
    adj = face_adjacent(ia) & solid & (M.feat == 0)
    above_air = np.zeros_like(ia)
    above_air[:, :-1, :] = ia[:, 1:, :]
    floor_skin = adj & above_air
    wall_skin = adj & ~above_air
    x0, y0, z0 = M.o
    p = int(pal["patch"])
    for sel, plist, is_floor in ((floor_skin, pal["floor"], True), (wall_skin, pal["wall"], False)):
        i, j, k = np.nonzero(sel)
        gx, gy, gz = i + x0, j + y0, k + z0
        pick = np.minimum((h01(seed + 11, gx // p, gy // p, gz // p) * len(plist)).astype(np.int64), len(plist) - 1)
        ids = np.array([ix[n] for n in plist], dtype=np.int16)[pick]
        if accent_allowed(is_floor):
            r = h01(seed + 13, gx, gy, gz)
            ids = np.where(r < pal["light_chance"], ix[pal["light"]],
                           np.where(r < pal["light_chance"] + pal["magma_chance"], ix[pal["magma"]], ids)).astype(np.int16)
        B[i, j, k] = ids
    for code, name in ((1, pal["parapet"]), (2, pal["dais_ring"]), (3, pal["dais_inner"]), (4, names[-1])):
        B[M.feat == code] = ix[name]
    return B, names, D


# ----------------------------------------------------------------------------------------------------- commands


def merge_boxes(ids, origin):
    """[(x0, y0, z0, x1, y1, z1, id)]: runs along x per (y, z), equal runs merged over consecutive z, equal rectangles
    merged over consecutive y. `ids` int array (nx, ny, nz); 0 means nothing."""
    ox, oy, oz = origin
    nx, ny, nz = ids.shape
    rects = {}
    for j in range(ny):
        layer = ids[:, j, :]
        if not layer.any():
            continue
        open_ = {}
        for k in range(nz + 1):
            cur = []
            if k < nz:
                col = layer[:, k]
                if col.any():
                    change = np.flatnonzero(np.diff(col.astype(np.int32)) != 0) + 1
                    starts = np.concatenate(([0], change))
                    ends = np.concatenate((change - 1, [nx - 1]))
                    cur = [(int(a), int(b), int(col[a])) for a, b in zip(starts, ends) if col[a] != 0]
            curset = set(cur)
            for key in [kk for kk in open_ if kk not in curset]:
                rects.setdefault((key[2], key[0], key[1], open_.pop(key), k - 1), []).append(j)
            for key in cur:
                open_.setdefault(key, k)
    out = []
    for (bid, a, b, k0, k1), js in rects.items():
        start = prev = js[0]
        for j in js[1:] + [None]:
            if j is not None and j == prev + 1:
                prev = j
                continue
            out.append((a + ox, start + oy, k0 + oz, b + ox, prev + oy, k1 + oz, bid))
            if j is not None:
                start = prev = j
    out.sort(key=lambda t: (t[1], t[2], t[0]))
    return out


def command(box, block):
    x0, y0, z0, x1, y1, z1 = box
    if (x0, y0, z0) == (x1, y1, z1):
        return "setblock %d %d %d %s" % (x0, y0, z0, block)
    return "fill %d %d %d %d %d %d %s" % (x0, y0, z0, x1, y1, z1, block)


def carve_commands(doc, M, B, names):
    """[command] in the order that makes the seal true: every solid, then the air, then the lava."""
    cmds = [command(b[:6], names[b[6]]) for b in merge_boxes(B, M.o)]
    cmds += [command(b[:6], AIR) for b in merge_boxes(M.ia.astype(np.int16), M.o)]
    cmds += [command(b[:6], LAVA) for b in merge_boxes(M.lava.astype(np.int16), M.o)]
    return FL.split_fills(cmds)


def stage_cells(doc, M):
    """{stage number: boolean mask} of the quake's air: 2 the ravine north of ravine_split_z, 3 the rest, 4 the plug."""
    z0 = M.o[2]
    split = int(doc["quake"]["ravine_split_z"]) - z0
    north = np.zeros(M.qa_r.shape, bool)
    north[:, :, :split + 1] = True
    return {2: M.qa_r & north, 3: M.qa_r & ~north, 4: M.qa_p.copy()}


N8 = [(di, dk) for di in (-1, 0, 1) for dk in (-1, 0, 1) if (di, dk) != (0, 0)]
SIDES = (("north", 0, -1), ("east", 1, 0), ("south", 0, 1), ("west", -1, 0))


def column_tops(M, cut):
    """(nx, nz) the top solid y of every column once the cells of `cut` are air (natural terrain is solid up to the ground)."""
    ys = M.o[1] + np.arange(M.shape[1])[None, :, None]
    solid = (ys <= M.G[:, None, :]) & ~cut
    return np.where(solid, ys, -10_000).max(axis=1)


def rim_guard_columns(doc, M, cut):
    """{(i, k) model column: (y_lo, y_hi)} the rim the cut `cut` (a 3-D mask) makes: every column the cut does not lower, with
    an eight-neighbour lowered more than quake.rim.safe_drop below its ground, walled from one over its ground to one over the
    highest ground of its uncut eight-neighbours (the wall's top then stands 1.5 over the feet of anyone beside it)."""
    safe = int(doc["quake"]["rim"]["safe_drop"])
    top = column_tops(M, cut)
    G = M.G
    lowered = top < G
    nx, nz = G.shape
    out = {}
    for i in range(nx):
        for k in range(nz):
            if lowered[i, k]:
                continue
            drop = 0
            high = int(G[i, k])
            for di, dk in N8:
                a, c = i + di, k + dk
                if not (0 <= a < nx and 0 <= c < nz):
                    continue
                if lowered[a, c]:
                    drop = max(drop, int(G[i, k]) - int(top[a, c]))
                else:
                    high = max(high, int(G[a, c]))
            if drop > safe:
                out[(i, k)] = (int(G[i, k]) + 1, high + 1)
    return out


def guard_mask(M, cols):
    m = np.zeros(M.shape, bool)
    y0 = M.o[1]
    for (i, k), (lo, hi) in cols.items():
        m[i, lo - y0:hi - y0 + 1, k] = True
    return m


def wall_states(M, walls, cut):
    """{(i, j, k): state} the side states vanilla would give each wall cell of `walls`: a side connects (low) to a wall or a
    solid block beside it at the same height, and the post shows unless the wall runs straight through."""
    y0 = M.o[1]
    nx, ny, nz = M.shape
    out = {}
    for i, j, k in zip(*np.nonzero(walls)):
        con = {}
        for name, di, dk in SIDES:
            a, c = i + di, k + dk
            solid = False
            if 0 <= a < nx and 0 <= c < nz:
                solid = bool(walls[a, j, c]) or (j + y0 <= M.G[a, c] and not cut[a, j, c])
            con[name] = "low" if solid else "none"
        straight = ((con["north"] == con["south"] == "low" and con["east"] == con["west"] == "none")
                    or (con["east"] == con["west"] == "low" and con["north"] == con["south"] == "none"))
        out[(int(i), int(j), int(k))] = "[east=%s,north=%s,south=%s,up=%s,waterlogged=false,west=%s]" % (
            con["east"], con["north"], con["south"], "false" if straight else "true", con["west"])
    return out


def guard_commands(doc, M, writes, walls, cut):
    """fill/setblock lines writing the wall cells `writes` in palette.rim_guard, with the states joining them to every wall
    standing (`walls`) and to the solid ground beside them."""
    block = doc["palette"]["rim_guard"]
    states = {c: s for c, s in wall_states(M, walls, cut).items() if writes[c]}
    names = sorted(set(states.values()))
    ids = np.zeros(M.shape, np.int16)
    for c, st in states.items():
        ids[c] = names.index(st) + 1
    return [command(b[:6], block + names[b[6] - 1]) for b in merge_boxes(ids, M.o)]


def stage_guards(doc, M):
    """{stage: (new wall mask, stale wall mask, the cut so far, the walls it writes, every wall standing after it)}: the rim
    each stage's cut makes, written by that stage; and the walls an earlier stage wrote that this stage's cut takes away
    (cleared, so no wall hangs over the ravine). A stage writes its new walls and the standing ones beside them again, so a
    post an earlier stage wrote joins the new ones."""
    cells = stage_cells(doc, M)
    cum = np.zeros(M.shape, bool)
    have = np.zeros(M.shape, bool)
    out = {}
    for st in (2, 3, 4):
        cum = cum | cells[st]
        walls = guard_mask(M, rim_guard_columns(doc, M, cum))
        lowered = (column_tops(M, cum) < M.G)[:, None, :]
        stale = have & lowered & ~walls
        new = walls & ~have
        have = (have & ~stale) | walls
        # what this stage writes: its new walls and the standing ones beside them, so their posts join
        out[st] = (new, stale, cum.copy(), have & dilate(new, 1, (0, 2)), have.copy())
    return out


def cut_falling_lines(box, seconds):
    """The stage's own slow falling: anyone standing over the cut keeps their legs (the new floor is a walk, not a fall)."""
    return ["# anyone standing over the cut keeps their legs: slow falling, so the new floor is a walk and not a fall",
            "effect give @a[%s] minecraft:slow_falling %d 0 true" % (sel_box(box), seconds)]


def tick_order():
    """The order tick tests #quake's states in: the LAST first, so a stage that moves the state on is never followed, in
    the same pass, by the line that tests the state it moved to. One state a pass, whatever the probes read."""
    return (4, 3, 2, 1, 0)


def mask_box(M, mask):
    i, j, k = np.nonzero(mask)
    x0, y0, z0 = M.o
    return (int(i.min()) + x0, int(j.min()) + y0, int(k.min()) + z0, int(i.max()) + x0, int(j.max()) + y0, int(k.max()) + z0)


def probe_cell(M, mask, lip_x):
    """A cell of the stage that is rock before it, well inside the terrain (3 under the ground), on the axis and at the far
    end of the stage: an `air` read there means the stage's fills landed."""
    i, j, k = np.nonzero(mask)
    x0, y0, z0 = M.o
    gx, gy, gz = i + x0, j + y0, k + z0
    ok = (gy <= M.G[i, k] - 3)
    if not ok.any():
        raise CavernError("a quake stage has no cell 3 under the ground to probe")
    cand = np.nonzero(ok)[0]
    order = sorted(cand, key=lambda n: (abs(int(gx[n]) - lip_x), -int(gz[n]), int(gy[n])))
    n = order[0]
    return int(gx[n]), int(gy[n]), int(gz[n])


def chunk_gap(box, pad):
    """The largest chunk distance (Chebyshev) from a player standing `pad` blocks outside `box` to a chunk the box touches."""
    x0, _y0, z0, x1, _y1, z1 = box
    worst = 0
    for lo, hi in ((x0, x1), (z0, z1)):
        for edge, direction in ((lo, -1), (hi, 1)):
            player = edge + direction * pad
            far = lo if direction > 0 else hi
            worst = max(worst, abs(player // 16 - far // 16))
    return worst


def sel_box(box, extra=""):
    x0, y0, z0, x1, y1, z1 = box
    s = "x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d" % (x0, y0, z0, x1 - x0, y1 - y0, z1 - z0)
    return s + ("," + extra if extra else "")


def trigger_box(box, pad):
    x0, _y0, z0, x1, _y1, z1 = box
    return (x0 - pad, -64, z0 - pad, x1 + pad, 448, z1 + pad)


def text(msg, colour="gray", italic=True):
    d = {"text": msg, "color": colour}
    if italic:
        d["italic"] = True
    return json.dumps(d, ensure_ascii=False)


def stage_functions(doc, M, leg_objective):
    """{function name: lines}, {stage: (write box, probe, trigger box)} for the quake's stages (the play-time cut)."""
    q = doc["quake"]
    O = q["objective"]
    msg = doc["messages"]
    cells = stage_cells(doc, M)
    lip_x = doc["spine"]["lip"][0]
    info = {}
    fns = {}
    falling = int(q["slow_falling_seconds"])
    guards = stage_guards(doc, M)
    allbox = mask_box(M, M.qa_r | M.qa_p)
    for st in (2, 3, 4):
        mask = cells[st]
        if not mask.any():
            raise CavernError("quake stage %d has no cells" % st)
        new_walls, stale, cum, writes, walls = guards[st]
        wbox = mask_box(M, mask | writes | stale)
        probe = probe_cell(M, mask, lip_x)
        tb = trigger_box(wbox, int(q["trigger_pad"]))
        gap = chunk_gap(wbox, int(q["trigger_pad"]))
        if gap >= int(q["sim_chunks"]):
            raise CavernError("stage %d: a player at the trigger's edge is %d chunks from a chunk it writes; simulation "
                              "distance is %d" % (st, gap, q["sim_chunks"]))
        info[st] = {"write_box": wbox, "probe": probe, "trigger": tb, "chunk_gap": gap,
                    "rim_columns": len({(int(i), int(k)) for i, _j, k in zip(*np.nonzero(new_walls))})}
        cx, cy, cz = (wbox[0] + wbox[3]) // 2, wbox[4], (wbox[2] + wbox[5]) // 2
        lines = [HEAD, "# stage %d of the opening: run by tick only while #quake is %d and a player stands within %d blocks of"
                 % (st, st, q["trigger_pad"]),
                 "# every block it writes; it holds its own chunks (the forceload lines below, tools/function_limits.py), and the",
                 "# state moves on only after the probe cell reads air"]
        cbox = mask_box(M, mask)
        pad_box = (cbox[0] - 2, cbox[1] - 2, cbox[2] - 2, cbox[3] + 2, cbox[4] + 60, cbox[5] + 2)
        lines += cut_falling_lines(pad_box, falling)
        lines += ["playsound minecraft:entity.generic.explode master @a[%s] %d %d %d 4 0.5" % (sel_box(tb), cx, cy, cz),
                  "playsound minecraft:block.basalt.break master @a[%s] %d %d %d 4 0.6" % (sel_box(tb), cx, cy, cz),
                  "particle minecraft:explosion_emitter %d %d %d 5 2 8 0 6 force" % (cx, cy - 6, cz),
                  "particle minecraft:large_smoke %d %d %d 6 8 10 0.05 80 force" % (cx, cy - 4, cz),
                  "tellraw @a[%s] %s" % (sel_box(tb), text(msg[{2: "split", 3: "fall", 4: "breach"}[st]], "gold"))]
        for b in merge_boxes(mask.astype(np.int16), M.o):
            lines.append(command(b[:6], AIR))
        if stale.any():
            lines.append("# the rim guard an earlier stage stood on ground this cut has taken away")
            lines += [command(b[:6], AIR) for b in merge_boxes(stale.astype(np.int16), M.o)]
        if new_walls.any():
            lines.append("# the rim this cut makes: every column beside a drop of more than %d gets %s, 1.5 over the feet of anyone"
                         % (int(q["rim"]["safe_drop"]), doc["palette"]["rim_guard"]))
            lines.append("# beside it (data/groudon_cavern.json quake.rim); the standing walls beside them are written again, so")
            lines.append("# the posts join")
            lines += guard_commands(doc, M, writes, walls, cum)
        lines = FL.split_fills(lines)
        lines.append("execute if block %d %d %d %s run scoreboard players set #quake %s %d" % (probe + (AIR, O, st + 1)))
        if st == 4:
            lines.append("execute if score #quake %s matches 5 run function %s/opened" % (O, F))
        fns["stage/%d" % st] = FL.ensure_loaded(lines)
    return fns, info, allbox


def built_read_lines(doc):
    """cobblers:groudon_cavern/built_read: R14L's read-back (tools/legendaries.py placement_steps). #built copied to the score
    the step reads (tools/chunk_look.py's objective); 0 first, so a stale copy can never read as built."""
    O = doc["quake"]["objective"]
    return [HEAD, "# R14L's read-back (tools/legendaries.py placement_steps): #built of this objective, copied to the score the",
            "# step reads (tools/chunk_look.py's objective), 0 first so a stale copy can never read as built",
            "scoreboard objectives add %s dummy" % CL_OBJ,
            "scoreboard players set #%s %s 0" % (BUILT_HOLDER, CL_OBJ),
            "execute store result score #%s %s run scoreboard players get #built %s" % (BUILT_HOLDER, CL_OBJ, O)]


def runtime_files(doc, M, leg_objective, stand_y):
    """{function name under cobblers:groudon_cavern/: lines}, plus the stage info. stand_y is the ground at the keeper's stand
    plus one (tools/ground.py, rounded)."""
    q = doc["quake"]
    O = q["objective"]
    msg = doc["messages"]
    g = doc["guard"]
    stage_fns, info, allbox = stage_functions(doc, M, leg_objective)
    flag = "advancements={%s:flag/%s=true}" % (NS, q["flag"])
    fns = {}
    left = q["left_objective"]
    fns["load"] = [HEAD, "scoreboard objectives add %s dummy" % O,
                   "scoreboard objectives add %s minecraft.custom:minecraft.leave_game" % left,
                   "execute unless score #built %s matches -2147483648.. run scoreboard players set #built %s 0" % (O, O),
                   "execute unless score #quake %s matches -2147483648.. run scoreboard players set #quake %s 0" % (O, O),
                   "schedule function %s/tick 20t replace" % F,
                   "schedule function %s/rejoin 1t replace" % F]
    lip = doc["spine"]["lip"]
    tr1 = trigger_box(allbox, int(q["trigger_pad"]))
    drive = {
        0: ["# the rumble: the first moment any player online holds gym8_cleared (a poll, so it also catches a flag granted by a",
            "# command, or held before this existed); world-wide and once",
            "execute if score #built %s matches 1 if score #quake %s matches 0 if entity @a[%s] run function %s/rumble"
            % (O, O, flag, F)],
        1: ["execute if score #built %s matches 1 if score #quake %s matches 1 if entity @a[%s] run function %s/stage/1"
            % (O, O, sel_box(tr1), F)]}
    for st in (2, 3, 4):
        drive[st] = ["execute if score #built %s matches 1 if score #quake %s matches %d if entity @a[%s] run function %s/stage/%d"
                     % (O, O, st, sel_box(info[st]["trigger"]), F, st)]
    fns["tick"] = [
        HEAD, "# every 20 ticks. #built is set by the carve (cobblers:groudon_cavern/build/state): nothing below acts on an",
        "# unbuilt world. #quake: 0 sealed, 1 rumbled, 2 tremor played, 3 upper ravine cut, 4 lower ravine cut, 5 open for good",
        "schedule function %s/tick 20t replace" % F,
        "# the opening: a stage a second while someone is near enough that every chunk it writes is theirs. The states are",
        "# tested LAST FIRST: a line that moves #quake on is never followed in this pass by the line testing the next state,",
        "# so the tremor and the three cuts fall on four separate passes and never in one tick"]
    for st in tick_order():
        fns["tick"] += drive[st]
    over = (allbox[0] - 2, allbox[1] - 2, allbox[2] - 2, allbox[3] + 2, allbox[4] + 80, allbox[5] + 2)
    fns["rejoin"] = [
        HEAD, "# every tick, so it lands on the first tick a player is back: a player who logged out standing over the cut and is",
        "# back after it would load in over the ravine. Slow falling, so the new floor is a walk and not a fall (their count of",
        "# leaving the game, then cleared; the effect only where the cut is)",
        "schedule function %s/rejoin 1t replace" % F,
        "execute if score #quake %s matches 2.. as @a[scores={%s=1..},%s] run effect give @s minecraft:slow_falling %d 0 true"
        % (O, left, sel_box(over), int(q["slow_falling_seconds"])),
        "scoreboard players reset @a[scores={%s=1..}] %s" % (left, left)]
    fns["built_read"] = built_read_lines(doc)
    fns["tick"] += [
        "# the keeper: anyone in the hall without gym8_cleared is sent back to the bowl (creative and spectator are left alone)",
        "execute if score #built %s matches 1 as @a[%s] unless entity @s[%s] run function %s/eject"
        % (O, sel_box(tuple(g["box"]), "gamemode=!creative,gamemode=!spectator"), flag, F)]
    # the rumble is heard by everybody, wherever they are
    fns["rumble"] = [
        HEAD, "# once: the first player online holding gym8_cleared has beaten the eighth gym. Nothing is cut yet: the opening waits",
        "# for somebody to come within range, so it is seen, and so no block is written into a chunk nobody holds",
        "scoreboard players set #quake %s 1" % O,
        "execute as @a[%s,limit=1] run tellraw @a [\"\",{\"selector\":\"@s\",\"color\":\"gold\"},%s]" % (flag, text(msg["rumble"])),
        "execute as @a at @s run playsound minecraft:entity.generic.explode master @s ~ ~ ~ 0.5 0.4",
        "execute as @a at @s run playsound minecraft:entity.ender_dragon.growl master @s ~ ~ ~ 0.4 0.3",
        "title @a actionbar %s" % text(msg["tremor"], "gold")]
    fns["stage/1"] = [
        HEAD, "# the tremor: sound and dust over the bowl, no block written. Run by tick while #quake is 1 and a player is near.",
        "execute positioned %d %d %d run effect give @a[distance=..40] minecraft:nausea 4 0 true" % (lip[0], doc["spine"]["lip_y"], lip[1] + 20),
        "playsound minecraft:entity.generic.explode master @a[%s] %d %d %d 4 0.4" % (sel_box(tr1), lip[0], doc["spine"]["lip_y"], lip[1] + 20),
        "particle minecraft:large_smoke %d %d %d 8 2 14 0.05 60 force" % (lip[0], doc["spine"]["lip_y"] + 2, lip[1] + 20),
        "tellraw @a[%s] %s" % (sel_box(tr1), text(msg["tremor"], "gold")),
        "scoreboard players set #quake %s 2" % O]
    fns.update({k: v for k, v in stage_fns.items()})
    fns["opened"] = [
        HEAD, "# the plug is cut: the cavern is open for good. #groudon of the legendaries objective is the chamber's own",
        "# open score (tools/legendaries.py): 1 means the gate has opened, so a re-run of R14L carves nothing and Groudon is",
        "# awakened by its own keeper when someone comes near",
        "scoreboard players set #groudon %s 1" % leg_objective,
        "tellraw @a %s" % text(msg["opened"], "gold"),
        "execute as @a at @s run playsound minecraft:entity.ender_dragon.growl master @s ~ ~ ~ 0.5 0.5"]
    sx, sz = g["stand"]
    fns["eject"] = [HEAD, "# as a player in the hall without gym8_cleared: back to the bowl floor in front of the ravine, told why",
                    "tellraw @s %s" % text(msg["turned_back"], "dark_red"),
                    "tp @s %d.5 %d %d.5 %d 0" % (sx, stand_y, sz, g["yaw"])]
    return fns, info


# --------------------------------------------------------------------------------------------- the build pack


def build_files(doc, M, B, names, leg):
    cmds = carve_commands(doc, M, B, names)
    O = doc["quake"]["objective"]
    lobj, rid = leg["objective"], doc["record"]
    parts = [cmds[i:i + PART_COMMANDS] for i in range(0, len(cmds), PART_COMMANDS)]
    fns = {}
    calls = []
    for n, part in enumerate(parts):
        name = BUILD_PREFIX + "p_%02d" % n
        fns[name] = FL.ensure_loaded([HEAD, "# part %d of %d of the carve: solids (envelope, skin, features), then the air, then "
                                      "the lava; holds its own chunks" % (n + 1, len(parts))] + part)
        calls.append("function " + name)
    fns[BUILD_PREFIX + "state"] = [
        HEAD, "# after the blocks: the cavern stands, sealed. #built opens tick's writes (nothing is cut into an unbuilt world)",
        "scoreboard objectives add %s dummy" % O,
        "execute unless score #quake %s matches -2147483648.. run scoreboard players set #quake %s 0" % (O, O),
        "scoreboard players set #built %s 1" % O]
    fns[BUILD_PREFIX + "carve"] = [HEAD, "# the whole carve, in order (R14L runs it through carve_once)"] + calls + [
        "function " + BUILD_PREFIX + "state"]
    fns[CARVE_ONCE] = [
        HEAD, "# R14L's entry (tools/legendaries.py placement_steps). A re-run must not re-seal a cavern the world has opened or",
        "# begun to open: the carve runs only while the legendary's open score is not 1 and the quake has not begun to cut",
        "execute unless score #%s %s matches 1 unless score #quake %s matches 2.. run function %scarve" % (rid, lobj, O, BUILD_PREFIX)]
    return fns


def plan(doc, ground=None):
    import ground as G
    leg = _j(LEGENDARIES)
    bad = static_problems(doc, leg)
    if bad:
        raise CavernError("data/groudon_cavern.json is refused:\n  " + "\n  ".join(bad))
    ground = ground or G.Ground()
    bad = retired_problems(doc, leg, ground)
    if bad:
        raise CavernError("data/groudon_cavern.json is refused:\n  " + "\n  ".join(bad))
    M = build_model(doc, ground)
    B, names, D = classify(doc, M)
    bad = model_problems(doc, M, D)
    if bad:
        raise CavernError("the cavern model is refused:\n  " + "\n  ".join(bad))
    return {"M": M, "B": B, "names": names, "D": D, "leg": leg}


def model_problems(doc, M, D):
    """The builder's own fail-closed guards (the cleanup's independent proof is tools/groudon_revert_audit.py)."""
    bad = []
    x0, y0, z0 = M.o
    if D[0].any() or D[-1].any() or D[:, 0].any() or D[:, -1].any() or D[:, :, 0].any() or D[:, :, -1].any():
        bad.append("the envelope touches the model box's edge")
    if not M.ia.any() or not M.qa_r.any() or not M.qa_p.any() or not M.lava.any():
        bad.append("the model is missing a part (interior air, ravine, plug or lava)")
    # the envelope stops two under the ground: the roof is never the surface
    ys = y0 + np.arange(M.shape[1])[None, :, None]
    top = np.where(D, ys, -10_000).max(axis=1)
    if (top >= M.G - 1).any():
        bad.append("the envelope reaches within 1 of the surface at %d column(s)" % int((top >= M.G - 1).sum()))
    # no interior void within the envelope margin of a cut cell other than through stone
    cut = dilate(M.qa_r, int(doc["margin"]), (0, 1, 2))
    if (cut & M.ia).any():
        bad.append("the open ravine is within %d blocks of the carved interior: less than a margin of rock stands between "
                   "them before the plug is cut" % int(doc["margin"]))
    return bad


def functions(doc, p, ground):
    """(runtime {id: lines}, info, build {id: lines}) of the whole cavern AS IT WAS BUILT: only applied_functions() reads it
    now (the record of what the world received). Nothing here is emitted as a datapack any more."""
    M, leg = p["M"], p["leg"]
    sx, sz = doc["guard"]["stand"]
    rfns, info = runtime_files(doc, M, leg["objective"], int(ground(sx, sz)) + 1)
    run = {"%s/%s" % (F, k): v for k, v in rfns.items()}
    return run, info, build_files(doc, M, p["B"], p["names"], leg)


# ------------------------------------------------------------------------------ the record of what the world received


def applied_functions(doc, p, ground):
    """{function id: lines}: every function that WROTE BLOCKS into the world, as it ran: the carve (R14L, 2026-10-21 01:16,
    through carve_once, its parts and its state) and the three cuts (the quake's stages 2, 3 and 4). Stage 1, the rumble,
    the keeper and the rejoin wrote no block and are not in it."""
    run, _info, bld = functions(doc, p, ground)
    out = dict(bld)
    for st in (2, 3, 4):
        fid = "%s/stage/%d" % (F, st)
        out[fid] = run[fid]
    return out


def applied_files(fns):
    """{relative path: text}: the record laid out as a datapack's function tree, WITHOUT pack.mcmeta, so nothing loads it."""
    out = {}
    for fid, body in fns.items():
        ns, path = fid.split(":", 1)
        out["data/%s/function/%s.mcfunction" % (ns, path)] = "\n".join(body) + "\n"
    return out


def digest(files):
    """sha256 over the record's files sorted by path: each path, a newline, its text (utf-8). tools/groudon_revert_audit.py
    computes the same from the files on disk and holds it to the retired site's applied.sha256."""
    h = hashlib.sha256()
    for rel in sorted(files):
        h.update(rel.encode("utf-8") + b"\n" + files[rel].encode("utf-8"))
    return h.hexdigest()


# ------------------------------------------------------------------------------------------ the cleanup (2026-10-21)


def retired_site(leg_doc, doc=None):
    """(record, site) of the cavern's retired site in data/legendaries.json."""
    doc = doc or load()
    rec = next(r for r in leg_doc["encounters"] if r["id"] == doc["record"])
    site = next(s for s in rec.get("retired_sites") or [] if s.get("id") == SITE_ID)
    return rec, site


def touched_masks(doc, M, B):
    """(carve, cut, walls) as 3-D masks over the model: every cell the carve wrote (envelope, skin, lake wall, dais and
    pedestal, interior air, lava), every cell the three cuts made air (the ravine and the plug), and every rim wall standing
    after the last cut. The stages also cleared to air the few walls an earlier stage had stood on ground a later cut took
    away: those cells are over the ground, air before the quake and air after it, so nothing restores them."""
    carve = (B > 0) | M.ia | M.lava
    cut = M.qa_r | M.qa_p
    walls = stage_guards(doc, M)[4][4]
    return carve, cut, walls


def terrain_band(rel):
    """1 deep, 2 under, 3 surface for a cell `rel` blocks above its column's ground (rel <= 0): tools/legendaries.py
    terrain_lines' convention (deep to three under the ground, under to one under, the surface block at the ground)."""
    rel = np.asarray(rel)
    return np.where(rel == 0, 3, np.where(rel >= -2, 2, 1))


def restore_targets(doc, M, B, terrain, masks=None):
    """(ids, names): the terrain block every written cell AT OR UNDER its column's ground goes back to (id 0: not written by
    the restore). Over the ground nothing is written but the rim's walls (restore_commands): the cut left air there, and the
    stones the owner placed by hand to stop the water stay as they are."""
    carve, cut, _walls = masks or touched_masks(doc, M, B)
    ys = M.o[1] + np.arange(M.shape[1])[None, :, None]
    rel = ys - M.G[:, None, :]
    over = carve & (rel > 0)
    if over.any():
        raise CavernError("the carve wrote %d cell(s) over the ground; this restore writes nothing there" % int(over.sum()))
    names = [None]
    for n in (terrain["deep"], terrain["under"], terrain["surface"]):
        if n not in names:
            names.append(n)
    lut = np.array([0, names.index(terrain["deep"]), names.index(terrain["under"]), names.index(terrain["surface"])],
                   np.int16)
    w = (carve | cut) & (rel <= 0)
    ids = np.where(w, lut[terrain_band(np.minimum(rel, 0))], 0).astype(np.int16)
    return ids, names


def pedestal_block_after(doc, M, terrain):
    """The terrain block the pedestal's cell goes back to (the restore's LAST block write)."""
    px, py, pz = pedestal(doc)
    rel = py - int(M.G[px - M.o[0], pz - M.o[2]])
    return {1: terrain["deep"], 2: terrain["under"], 3: terrain["surface"]}[int(terrain_band(min(rel, 0)))]


def restore_commands(doc, M, B, terrain, masks=None):
    """[command]: every written cell at or under the ground back to terrain (merged fills, the pedestal's cell left out: the
    restore writes it last), then the rim's walls cleared to air with `replace <the wall block>`, so a wall is the only thing
    over the ground the restore can change."""
    masks = masks or touched_masks(doc, M, B)
    ids, names = restore_targets(doc, M, B, terrain, masks)
    px, py, pz = pedestal(doc)
    ids[px - M.o[0], py - M.o[1], pz - M.o[2]] = 0
    cmds = [command(b[:6], names[b[6]]) for b in merge_boxes(ids, M.o)]
    guard = doc["palette"]["rim_guard"]
    cmds += ["fill %d %d %d %d %d %d %s replace %s" % (tuple(b[:6]) + (AIR, guard))
             for b in merge_boxes(masks[2].astype(np.int16), M.o)]
    return FL.split_fills(cmds)


def held_boxes(doc, M):
    """[(what, box)]: the voids a player can stand in, each its own box (one hull would hold the whole plateau): the
    ravine's two cuts and the plug from their floors to the cut's top, the tunnel outside the hall's square, and the hall
    with its lake. A player in any of them holds the cleanup, and R14L reads the held count back as 0 or stops."""
    cells = stage_cells(doc, M)
    hb = hall_box(doc)
    xs = M.o[0] + np.arange(M.shape[0])
    zs = M.o[2] + np.arange(M.shape[2])
    in_hall = ((xs >= hb[0]) & (xs <= hb[3]))[:, None, None] & ((zs >= hb[2]) & (zs <= hb[5]))[None, None, :]
    return [("the ravine's upper cut", mask_box(M, cells[2])), ("the ravine's lower cut", mask_box(M, cells[3])),
            ("the plug", mask_box(M, cells[4])), ("the tunnel", mask_box(M, M.ia & ~in_hall)),
            ("the hall", mask_box(M, (M.ia | M.lava) & in_hall))]


def chunk_count(box):
    x0, _y0, z0, x1, _y1, z1 = box
    return (x1 // 16 - x0 // 16 + 1) * (z1 // 16 - z0 // 16 + 1)


_PLANS = {}


def cached_plan(doc, ground):
    """plan(), once per heightmap, data and model code: tools/legendaries.py files() asks for it on every build. The key
    holds the model functions themselves, so a test that mutates the generator never gets the unmutated plan."""
    key = (id(ground), json.dumps(doc, sort_keys=True), build_model, classify, stage_guards, _j(LEGENDARIES).__repr__())
    if key not in _PLANS:
        _PLANS.clear()
        _PLANS[key] = plan(doc, ground)
    return _PLANS[key]


def retire_functions(rec, site, leg_doc, ground, p=None):
    """{'ns:path': lines} of the cavern's cleanup, in tools/legendaries.py's retired-site shape: a look-then-act chain
    (tools/chunk_look.py) over the whole model box that, once the box shows its saved entities (or blind after the chain's
    limit), refuses while a player stands in a void (held_boxes), else kills the cavern's Groudon (type cobblemon:pokemon,
    the record's tag, inside the model box: the live chamber's Groudon stands outside it, tools/legendaries.py) and, only
    while the cavern is there, runs the restore. The chain counts the held players; R14L reads 0 back or stops.

    CHUNKS: the chain's entry force-loads the model box (x and z) and its _done releases it; the restore and its parts write
    nothing outside that box and carry no forceload of their own (a forceload is per chunk, not counted: a part's release
    would drop the chain's hold). So the whole cleanup holds chunk_count(model_box) chunks at once, for the chain's life."""
    import chunk_look as CL
    import legendaries as L
    doc = load()
    p = p or cached_plan(doc, ground)
    M, B = p["M"], p["B"]
    base, restore, holder, new_tag = L.retire_parts(rec, site, leg_doc)
    box = model_box(doc)
    nch = chunk_count(box)
    tag = leg_doc["tag_prefix"] + rec["id"]
    scope = "type=cobblemon:pokemon,tag=%s,%s" % (tag, sel_box(box))
    held = "@a[tag=%s]" % RETIRE_HELD
    q = doc["quake"]["objective"]
    px, py, pz = pedestal(doc)
    act = ["# the cleanup of %s's retired site %s (tools/groudon_cavern.py retire_functions)" % (rec["id"], site["id"]),
           "# a player standing in the ravine, the plug, the tunnel or the hall is held, and nothing below is done while anyone",
           "# is: the step reads the held count back",
           "tag @a remove %s" % RETIRE_HELD]
    act += ["tag @a[%s] add %s" % (sel_box(b), RETIRE_HELD) for _w, b in held_boxes(doc, M)]
    act += ["# the cavern's objective, so the gate below reads a score and not an unknown objective in a world it never reached",
            "scoreboard objectives add %s dummy" % q,
            "# the cavern's Groudon first, wherever it stands in the box (the owner moved it onto the lava), before rock fills",
            "execute unless entity %s run kill @e[%s]" % (held, scope),
            "# the restore only while the cavern is there: #built is 1 (its carve finished), or its pedestal stands. The",
            "# restore sets the pedestal's cell to rock and #built to 0 last, so neither line runs twice",
            "execute unless entity %s if score #built %s matches 1 run function %s" % (held, q, restore),
            "execute unless entity %s if block %d %d %d %s run function %s" % (held, px, py, pz, site["pedestal_block"], restore)]
    fns = CL.chain(base, (box[0], box[2], box[3], box[5]), ["@e[%s]" % scope], act, [scope], new_tag,
                   "tag=%s" % RETIRE_HELD, holder, note="tools/groudon_cavern.py")
    masks = touched_masks(doc, M, B)
    cmds = restore_commands(doc, M, B, site["terrain"], masks)
    parts = [cmds[i:i + PART_COMMANDS] for i in range(0, len(cmds), PART_COMMANDS)]
    by = ("# chunks-loaded-by: %s (its forceload holds the cavern's whole model box, x%d-%d z%d-%d, %d chunks, for the "
          "chain's life)" % (base, box[0], box[3], box[2], box[5], nch))
    names = []
    for n, part in enumerate(parts):
        name = "%s_p_%02d" % (restore, n)
        names.append(name)
        fns[name] = [HEAD, by, "# part %d of %d of the restore: cells back to terrain, then the rim's walls cleared"
                     % (n + 1, len(parts))] + part
    t = site["terrain"]
    fns[restore] = ([HEAD, by,
                     "# the quake cavern put back: every cell the carve and the cuts wrote at or under the ground back to the",
                     "# heightmap's terrain (%s at the ground, %s under it, %s deeper), the rim's walls cleared, nothing else over"
                     % (t["surface"], t["under"], t["deep"]),
                     "# the ground written. First the chamber's open score (the quake set it to 1; the live chamber's carve_once",
                     "# skips a chamber whose score is 1, and it is to be carved again); the pedestal LAST, then #built and #quake,",
                     "# so a run cut short is run again and a second run writes nothing",
                     "scoreboard players set #%s %s 0" % (rec["id"], leg_doc["objective"])]
                    + ["function %s" % n for n in names]
                    + ["setblock %d %d %d %s" % (px, py, pz, pedestal_block_after(doc, M, t)),
                       "scoreboard players set #built %s 0" % q,
                       "scoreboard players set #quake %s 0" % q])
    return fns


# ------------------------------------------------------------------------------------------------------- the probes


def revert_probe_records(doc, p, leg_doc, ground):
    """data/world_probes.json places.groudon_revert: blocks that read rock once the cleanup has run (deep cells only: the
    surface block is a guess, the retired site's terrain.surface_verified), the rebuilt chamber's pedestal, and Groudon."""
    import legendaries as L
    rec, site = retired_site(leg_doc, doc)
    M, B = p["M"], p["B"]
    ids, names = restore_targets(doc, M, B, site["terrain"])
    o = M.o
    out = []

    def blk(what, x, y, z):
        i, j, k = x - o[0], y - o[1], z - o[2]
        if (x, y, z) == pedestal(doc):
            name = pedestal_block_after(doc, M, site["terrain"])
        elif ids[i, j, k] == 0:
            raise CavernError("probe %s at (%d, %d, %d) is not a cell the restore writes" % (what, x, y, z))
        else:
            name = names[ids[i, j, k]]
        if y > int(M.G[i, k]) - 3:
            raise CavernError("probe %s at (%d, %d, %d) is not 3 under the ground (the surface block is a guess)"
                              % (what, x, y, z))
        out.append({"what": "groudon_revert: " + what, "block": [x, y, z, name], "expect": True})

    h, lk, ds = doc["hall"], doc["lake"], doc["dais"]
    f = int(h["floor_y"])
    lx, lz = lk["centre"]
    cx, cz = ds["centre"]
    blk("the hall's lava lake, filled", lx, f, lz)
    blk("the hall floor between the lake and the dais, filled", cx, f, (lz + cz) // 2)
    blk("the dais's pedestal (the cleanup's probe), rock", *pedestal(doc))
    blk("the air over the dais, filled", cx, f + 3, cz)
    ix, iz = 6712, 5572
    col = np.nonzero(M.ia[ix - o[0], :, iz - o[2]])[0]
    if not len(col):
        raise CavernError("the tunnel probe column (%d, %d) is not carved" % (ix, iz))
    blk("the tunnel at its first bend, filled", ix, int(col[0]) + o[1], iz)
    cells = stage_cells(doc, M)
    for st, what in ((2, "the ravine's upper cut"), (3, "the ravine's lower cut"), (4, "the plug")):
        blk("%s, filled (3 under the ground)" % what, *probe_cell(M, cells[st], doc["spine"]["lip"][0]))
    g = L.geometry(rec, leg_doc, ground)
    out.append({"what": "groudon_revert: the sealed chamber's pedestal, carved again by R14L",
                "block": list(g["pedestal"]) + [leg_doc["defaults"]["pedestal_block"]], "expect": True})
    tag = leg_doc["tag_prefix"] + rec["id"]
    out.append({"what": "groudon_revert: Groudon (one tagged %s, in the sealed chamber)" % tag,
                "hold": list(g["legendary"]), "entity": "@e[type=cobblemon:pokemon,tag=%s]" % tag, "count_max": 1})
    return out


# ------------------------------------------------------------------------------------------------------------- CLI


def write_applied(doc, p, ground, out=None):
    """Write the record of what the world received; return its digest."""
    out = Path(out or APPLIED)
    files = applied_files(applied_functions(doc, p, ground))
    if out.exists():
        shutil.rmtree(out)
    for rel, txt in files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(txt, encoding="utf-8", newline="\n")
    return digest(files), len(files)


def report(doc, p, leg_doc, ground):
    M = p["M"]
    rec, site = retired_site(leg_doc, doc)
    masks = touched_masks(doc, M, p["B"])
    cmds = restore_commands(doc, M, p["B"], site["terrain"], masks)
    ids, _names = restore_targets(doc, M, p["B"], site["terrain"], masks)
    return {"box": list(model_box(doc)), "chunks_held": chunk_count(model_box(doc)),
            "carve_cells": int(masks[0].sum()), "cut_cells": int(masks[1].sum()), "rim_wall_cells": int(masks[2].sum()),
            "restored_cells": int((ids > 0).sum()) + 1, "restore_commands": len(cmds),
            "restore_parts": -(-len(cmds) // PART_COMMANDS),
            "held_boxes": {w: list(b) for w, b in held_boxes(doc, M)}, "pedestal": list(pedestal(doc))}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("action", choices=("build", "report", "probes"))
    ap.add_argument("--source-root")
    ap.add_argument("--out", default=str(APPLIED))
    a = ap.parse_args(argv)
    import ground as G
    doc = load()
    ground = G.Ground(a.source_root)
    p = plan(doc, ground)
    leg = p["leg"]
    if a.action == "probes":
        wp = _j(PROBES)
        wp["places"].pop("groudon_cavern", None)
        wp["places"]["groudon_revert"] = revert_probe_records(doc, p, leg, ground)
        PROBES.write_text(json.dumps(wp, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print("wrote %d probes to %s" % (len(wp["places"]["groudon_revert"]), PROBES))
        return 0
    if a.action == "report":
        print(json.dumps(report(doc, p, leg, ground), indent=1))
        return 0
    want = revert_probe_records(doc, p, leg, ground)
    places = _j(PROBES)["places"]
    if places.get("groudon_revert") != want or "groudon_cavern" in places:
        raise CavernError("data/world_probes.json places.groudon_revert differs from the model (or places.groudon_cavern is "
                          "still there): run python tools/groudon_cavern.py probes")
    # the two packs this tool used to build are withdrawn (tools/reapply.py WITHDRAWN): a copy an earlier prepare left in
    # build/datapacks would be read as a pack no step runs, and could be installed by hand
    for stale in (PACK, PACK + "_build"):
        d = ROOT / "build" / "datapacks" / stale
        if d.is_dir():
            shutil.rmtree(d)
            print("removed %s (withdrawn 2026-10-21)" % d)
    sha, n = write_applied(doc, p, ground, a.out)
    _rec, site = retired_site(leg, doc)
    frozen = (site.get("applied") or {}).get("sha256")
    if sha != frozen:
        raise CavernError("the model no longer reproduces what the world received: the record's sha256 is %s, the retired "
                          "site froze %s (data/legendaries.json groudon %s applied). The cleanup would undo a different "
                          "cavern from the one that was built." % (sha, frozen, SITE_ID))
    print("wrote %s (%d functions the world received, sha256 %s, the frozen one); the cleanup itself is emitted into "
          "cobblers_legendaries by tools/legendaries.py" % (a.out, n, sha[:12]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

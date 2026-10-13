#!/usr/bin/env python
"""Rayquaza's home (data/rayquaza_sky.json): a sealed relic arch on the Craters' great cone, and a floating island over it.

The design is docs/world-building/KYOGRE_CAVE.md section 6 ("Rayquaza: a sky island behind a relic arch") with the owner's
answers of 2026-10-06 (champion_cleared plus met Kyogre and Groudon, level 70, the arch on the great cone's summit; the End's
shiny Rayquaza removed) and the owner's lessons of 2026-10-12 (data/rayquaza_sky.json design.lessons_2026_10_12):

  THE ARCH     a ruined sky-pillar doorway on a stepped plinth at the summit (6408, 5128, y304 on the heightmap), three marks
               on its lintel (sea, sky, fire), two signs saying why it is shut, a ring of broken column stumps, two lanterns
               on posts. A player who walks into the doorway and holds champion_cleared, met Kyogre and met Groudon is taken
               up to the island; anyone else is told, once a visit, which mark is dark.
  THE ISLAND   64 x 48, its top at y368, 64 over the summit, so it is seen from the ground on every side long before it can be
               reached: a green, mossy island with a rock underside over a black volcanic cone, four small rocks drifting off
               its rim, a gravel path with lanterns on posts from the pillar's door to a south overlook.
  THE PILLAR   a broken sky pillar 40 high on the island: a roofed helix of half-block steps between a solid core and the wall
               (walked without a jump), opening through the top floor onto the broken crown, where Rayquaza waits in the
               open on a dais. The arch lands a player inside the pillar's base; an alcove in the base's west wall takes
               anyone back down to the summit, unconditionally.
  THE ENCOUNTER  one Rayquaza at a time, level 70, through a keeper (tools/sanctuaries.py boss_files' clock and guardian rules,
               C25 -> C27): it is spawned only while a player who qualifies AND has not caught it is within reach of the crown,
               and withdrawn (sent under the world, then killed, so its drops cannot be farmed) when none is. It wakes for
               such a player on the crown, never while a player who does not qualify stands there, and goes quiet if one
               arrives. A catch near the crown grants cobblers:legendary/rayquaza/caught to the catcher, who never makes it
               spawn again: once per player, keyed on the catch.
  THE FALL     a player under the island (its footprint grown by rescue.margin, from 3 over the highest ground below up to the
               island's top) gets Slow Falling every pass, so a fall off the island lands softly on the cone.
  THE END      cobbleverse:spawn_rayquaza is overridden empty at its own path (data/rayquaza_sky.json upstream_neutralised).

Flight is not gated anywhere in this pack, so a player who flies up early reaches the island and the crown: they find a bare
dais and a sign, and the keeper never spawns for them. That is the gate; the arch is the way a qualified player is meant to go.

What it reuses, by name (CLAUDE.md principle 6): tools/mines.py's h32/sid and column_runs; tools/function_limits.py's
ensure_loaded and check_lines; tools/pack_split.py, which moves the one-shot build into cobblers_rayquaza_build so
`reapply.py strip` can take it out of the heap after the run (tools/pack_roles.py classes it `build`). The keeper is
tools/sanctuaries.py boss_files' shape rewritten for this predicate (the gate is advancements plus caught=false, computed as
player tags), not called: boss_files keys its spawn on gate FLAGS only (flag_sel), and Rayquaza's gate is two met
advancements as well.

  python tools/rayquaza_sky.py report     the geometry's numbers and the checks; nothing written
  python tools/rayquaza_sky.py build      -> build/datapacks/cobblers_rayquaza and cobblers_rayquaza_build (refuses when
                                          data/world_probes.json's rayquaza_sky records drifted from the geometry)
  python tools/rayquaza_sky.py sync       rewrite data/world_probes.json's rayquaza_sky records from the geometry

What this does NOT cover (CLAUDE.md "Our list is not the world"): the gate names cobblers:legendary/kyogre/met, which no pack
grants on this commit (Kyogre is being built in parallel); until one does, nobody qualifies (contract C26). The keeper acts only
on Pokemon tagged cobblers.rayquaza near the crown and on a guardian Rayquaza the blackout rebuilt there; any other Rayquaza in
the world (a dungeon prize, a player's own) is never touched. The build writes only its own cells: whatever a player built in
them is replaced, and nothing outside them is cleared.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import function_limits as FL  # noqa: E402
import ground as G            # noqa: E402
import mines as M             # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "data" / "rayquaza_sky.json"
PROBES = ROOT / "data" / "world_probes.json"
SPAWN_BLOCKS = ROOT / "data" / "spawn_blocks.json"
POLICY = ROOT / "data" / "spawn_block_policy.json"
SCHEMA = "cobblers.rayquaza_sky/1"
PACK = "cobblers_rayquaza"
OUT = ROOT / "build" / "datapacks" / PACK
NS = "cobblers"
FOLDER = "rayquaza"
F = "%s:%s" % (NS, FOLDER)
BUILD = "build"
AIR = "minecraft:air"
PRESENT = -2147483648     # the keeper's clock: seen present (tools/sanctuaries.py PRESENT)
NEVER = -2147483647       # the keeper's clock: no clock running (never brought in, or withdrawn)
OK = "cobblers.ray_ok"          # holds the gate: champion_cleared and both met advancements
FRESH = "cobblers.ray_fresh"    # holds the gate and has not caught Rayquaza here
TOLD = "cobblers.ray_told"      # told at the sealed arch on this visit
PROBE_KEY = "rayquaza_sky"
POLICY_SCOPE = "rayquaza_sky"
CEILING = 575                   # data/world.json built_ceiling.runtime_limit (cobblers_height)
BUILD_DESCRIPTION = "Cobblers: Rayquaza's arch, island and pillar, one-shot blocks (tools/rayquaza_sky.py, split by tools/pack_split.py)"


class SkyError(SystemExit):
    pass


# ------------------------------------------------------------------ reading

def load(path=SPEC):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise SkyError("%s: schema must be %s" % (path, SCHEMA))
    if doc["arch"]["front"] != "south":
        raise SkyError("arch.front %r: only 'south' is implemented (the doorway runs north-south)" % doc["arch"]["front"])
    return doc


def u01(seed, *v):
    return M.h32(seed, *v) / 4294967296.0


def weighted(seed, options, *v):
    """options[i] with weight (n - i): the first entry is the commonest."""
    n = len(options)
    r = u01(seed, *v) * (n * (n + 1) // 2)
    acc = 0
    for i, o in enumerate(options):
        acc += n - i
        if r < acc:
            return o
    return options[-1]


def bearing(dx, dz):
    """0 north (-z), clockwise (east +x), degrees."""
    return math.degrees(math.atan2(dx, -dz)) % 360.0


def angdiff(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)


def base(block):
    return block.split("[")[0].split("{")[0]


def gate_advancements(spec):
    ns = spec["namespace"]
    return (["%s:flag/%s" % (ns, f) for f in spec["gate"]["flags"]]
            + [spec["gate"]["met_advancement"] % m for m in spec["gate"]["requires_met"]])


def own_advancement(spec, what):
    return spec["gate"]["met_advancement"].replace("/met", "/" + what) % spec["occupant"]["species"]


def sign_nbt(lines):
    q = ",".join("'%s'" % json.dumps(t, ensure_ascii=False).replace("'", "\\'") for t in (list(lines) + [""] * 4)[:4])
    return "{front_text:{messages:[%s]},is_waxed:1b}" % q


# ------------------------------------------------------------------ the geometry

class Model:
    """Every cell the build writes, {(x, y, z): block}, the block entities written after them, and the named places the
    runtime and the probes use."""

    def __init__(self):
        self.cells = {}
        self.signs = []          # (x, y, z, state, nbt)
        self.marks = {}

    def put(self, x, y, z, block):
        self.cells[(int(x), int(y), int(z))] = block


def _arch(spec, g, m):
    a = spec["arch"]
    seed = spec["seed"]
    pal = spec["palette"]
    ax, az = a["centre"]["x"], a["centre"]["z"]
    hx, hz = a["plinth"]["half_x"], a["plinth"]["half_z"]
    foot = [(x, z) for x in range(ax - hx, ax + hx + 1) for z in range(az - hz, az + hz + 1)]
    gs = sorted(g(x, z) for x, z in foot)
    P = gs[len(gs) // 2]
    if gs[-1] - P > a["plinth"]["max_cut"] or P - gs[0] > a["plinth"]["max_fill"]:
        raise SkyError("the plinth at (%d, %d) would cut %d and fill %d (limits %d, %d): re-site the arch"
                       % (ax, az, gs[-1] - P, P - gs[0], a["plinth"]["max_cut"], a["plinth"]["max_fill"]))
    rubble = pal["plinth"][-1]
    for x, z in foot:
        gz = g(x, z)
        for y in range(gz + 1, P):
            m.put(x, y, z, rubble)
        for y in range(P + 1, gz + 1):
            m.put(x, y, z, AIR)
        m.put(x, P, z, weighted(seed, pal["plinth"], 1, x, z))
    # the step ring one block down round the plinth, only where the hill falls away under it
    for x in range(ax - hx - a["plinth"]["step"], ax + hx + a["plinth"]["step"] + 1):
        for z in range(az - hz - a["plinth"]["step"], az + hz + a["plinth"]["step"] + 1):
            if (x, z) in set(foot):
                continue
            gz = g(x, z)
            for y in range(gz + 1, P):
                m.put(x, y, z, pal["plinth"][0] if y == P - 1 else rubble)
    dw, dh, dd = a["doorway"]["half_width"], a["doorway"]["height"], a["doorway"]["depth_half"]
    pw, ph = a["pier_width"], a["pier_height"]
    l0, l1 = a["lintel"]
    piers = [range(ax - dw - pw, ax - dw), range(ax + dw + 1, ax + dw + 1 + pw)]
    for side, xs in enumerate(piers):
        for x in xs:
            for z in range(az - dd, az + dd + 1):
                jag = (0, 0, 1, 2)[M.h32(seed, 2, x, z) % 4] + (1 if side == 1 and abs(x - ax) == dw + pw else 0)
                top = P + ph - min(jag, ph - l1)
                for y in range(P + 1, top + 1):
                    m.put(x, y, z, weighted(seed, pal["pier"], 3, x, y, z))
    for x in range(ax - dw - pw, ax + dw + pw + 1):
        for z in range(az - dd, az + dd + 1):
            for y in range(P + l0, P + l1 + 1):
                if y == P + l1 and dw >= x - ax >= 1:
                    continue            # the top course is broken over the right of the doorway
                m.put(x, y, z, weighted(seed, pal["pier"], 4, x, y, z))
    for x in range(ax - dw, ax + dw + 1):
        for z in range(az - dd, az + dd + 1):
            for y in range(P + 1, P + dh + 1):
                m.put(x, y, z, AIR)
            m.put(x, P, z, pal["plinth"][0])
    front = az + dd
    m.put(ax, P + l0, front, pal["keystone"])
    m.put(ax, P + l0, az - dd, pal["keystone"])
    sig = a["sigils"]
    m.put(ax - 2, P + l0 + 1, front, sig["sea"])
    m.put(ax, P + l0 + 1, front, sig["sky"])
    m.put(ax + 2, P + l0 + 1, front, sig["fire"])
    wood = a["signs"]["wood"]
    state = "minecraft:%s_wall_sign[facing=south,waterlogged=false]" % wood
    for sx, lines in ((ax - dw - 2, a["signs"]["left"]), (ax + dw + 2, a["signs"]["right"])):
        m.signs.append((sx, P + 2, front + 1, state, sign_nbt(lines)))
        m.put(sx, P + 2, front + 1, state)
    for px in (ax - dw - pw, ax + dw + pw):
        pz = front + 3
        m.put(px, P + 1, pz, pal["post"])
        m.put(px, P + 2, pz, pal["post"])
        m.put(px, P + 3, pz, pal["lantern"])
    st = a["stumps"]
    plinth_zone = {(x, z) for x in range(ax - hx - 2, ax + hx + 3) for z in range(az - hz - 2, az + hz + 3)}
    for k in range(st["count"]):
        b = 30 + k * 360.0 / st["count"]
        sx = ax + int(round(st["radius"] * math.sin(math.radians(b))))
        sz = az - int(round(st["radius"] * math.cos(math.radians(b))))
        cols = [(sx, sz), (sx + 1, sz), (sx, sz + 1), (sx + 1, sz + 1)]
        if plinth_zone & set(cols):
            raise SkyError("stump %d at (%d, %d) stands on the plinth: stumps.radius is too small" % (k, sx, sz))
        low = min(g(x, z) for x, z in cols)
        h = 1 + M.h32(seed, 5, k) % st["max_height"]
        for x, z in cols:
            for y in range(g(x, z) + 1, low + h + 1):
                m.put(x, y, z, weighted(seed, pal["pier"], 6, x, y, z))
    for k, (b, r) in enumerate(((120, 13), (250, 13))):
        dx0 = ax + int(round(r * math.sin(math.radians(b))))
        dz0 = az - int(round(r * math.cos(math.radians(b))))
        for i in range(3):
            m.put(dx0 + i, g(dx0 + i, dz0) + 1, dz0, weighted(seed, pal["pier"], 7, k, i))
    m.marks["arch"] = {
        "plinth_y": P, "centre": [ax, az],
        "door": [ax - dw, P + 1, az - dd, ax + dw, P + dh - 1, az + dd],
        "told": [ax - hx - 2, P - 3, az - hz - 3, ax + hx + 2, P + ph + 2, az + hz + 5],
        "landing": [ax, P + 1, front + 4],
        "keystone": [ax, P + l0, front], "sky_sigil": [ax, P + l0 + 1, front],
        "doorway_air": [ax, P + 2, az], "top": P + ph}


def _island(spec, g, m):
    isl, pil, pal = spec["island"], spec["pillar"], spec["palette"]
    seed = spec["seed"]
    cx, cz = isl["centre"]["x"], isl["centre"]["z"]
    hx, hz, Yt = isl["half_x"], isl["half_z"], isl["top_y"]
    rn = isl["rim_noise"]
    ph = [u01(seed, 10, k) * 2 * math.pi for k in range(10)]

    def rimf(th):
        return 1 + rn * (0.55 * math.sin(2 * th + ph[0]) + 0.3 * math.sin(3 * th + ph[1]) + 0.15 * math.sin(5 * th + ph[2]))

    pcx, pcz = cx + pil["offset"]["x"], cz + pil["offset"]["z"]
    Ro, Ri, Rc = pil["outer_radius"], pil["inner_radius"], pil["core_radius"]
    span = int(math.ceil(max(hx, hz) * (1 + rn))) + 1
    cols = {}
    rho_of = {}
    for x in range(cx - span, cx + span + 1):
        for z in range(cz - span, cz + span + 1):
            dx, dz = x - cx, z - cz
            th = math.atan2(dx, -dz)
            rho = math.hypot(dx / hx, dz / hz) / rimf(th)
            if rho > 1:
                continue
            dp = math.hypot(x - pcx, z - pcz)
            if dp <= Ro + 2:
                bump = 0
            else:
                v = 0.9 * math.sin(x * 0.23 + ph[3]) * math.cos(z * 0.19 + ph[4]) + 0.4 * math.sin((x + z) * 0.11 + ph[5])
                bump = max(-1, min(1, int(round(v))))
                if rho > 0.88:
                    bump = min(bump, 0) - 1
            top = Yt + bump
            shape = 0.85 + 0.15 * math.sin(x * 0.37 + ph[6]) * math.cos(z * 0.31 + ph[7])
            depth = isl["depth_min"] + (isl["depth_max"] - isl["depth_min"]) * (1 - rho) ** 0.6 * shape
            depth = int(round(depth)) + (M.h32(seed, 11, x, z) % 2)
            cols[(x, z)] = (top - depth, top)
            rho_of[(x, z)] = rho
    # the pillar must stand well inside, on the flattened top
    for x in range(int(pcx - Ro - 2), int(pcx + Ro + 3)):
        for z in range(int(pcz - Ro - 2), int(pcz + Ro + 3)):
            if math.hypot(x - pcx, z - pcz) <= Ro + 2 and (rho_of.get((x, z), 9) > 0.8):
                raise SkyError("the pillar at (%d, %d) reaches the island's rim at (%d, %d): move pillar.offset" % (pcx, pcz, x, z))
    # the path from the pillar's door south to the overlook, and what stands beside it
    path = {(x, z) for x in range(pcx - 1, pcx + 2) for z in range(int(pcz + Ro) + 1, cz + int(hz * 0.7) + 1)}
    occupied = set()
    for (x, z), (bot, top) in cols.items():
        for y in range(bot, top + 1):
            dtop = top - y
            exposed = any((n not in cols) or not (cols[n][0] <= y <= cols[n][1])
                          for n in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)))
            if dtop == 0:
                if (x, z) in path:
                    b = weighted(seed, pal["path"], 12, x, z)
                elif math.sin(x * 0.3 + ph[8]) * math.sin(z * 0.27 + ph[9]) > 0.45:
                    b = pal["moss"]
                else:
                    b = pal["grass"]
            elif dtop <= 3:
                b = weighted(seed, pal["dirt"], 13, x, y, z) if dtop < 3 else pal["dirt"][-1]
            elif y - bot < 3:
                b = weighted(seed, pal["underside"], 14, x, y, z)
            elif exposed:
                b = weighted(seed, pal["rock"], 15, x, y, z)
            else:
                b = "minecraft:stone"
            m.put(x, y, z, b)
        if M.h32(seed, 16, x, z) % 100 < 8:
            m.put(x, bot - 1, z, pal["roots"])
    # lantern posts along the path, a stump and a drum at the overlook
    zs = list(range(int(pcz + Ro) + 4, cz + int(hz * 0.7), 10))
    for i, z in enumerate(zs):
        x = pcx - 3 if i % 2 == 0 else pcx + 3
        top = cols[(x, z)][1]
        m.put(x, top + 1, z, pal["post"])
        m.put(x, top + 2, z, pal["post"])
        m.put(x, top + 3, z, pal["lantern"])
        occupied.add((x, z))
    ox, oz = pcx - 7, cz + int(hz * 0.5)
    stump = [(ox, oz), (ox + 1, oz), (ox, oz + 1), (ox + 1, oz + 1)]
    for x, z in stump:
        for y in range(cols[(x, z)][1] + 1, Yt + 3 + 1):
            m.put(x, y, z, weighted(seed, pal["wall"], 17, x, y, z))
        occupied.add((x, z))
    for i in range(3):
        x, z = pcx + 5 + i, cz + int(hz * 0.55)
        m.put(x, cols[(x, z)][1] + 1, z, weighted(seed, pal["wall"], 18, i))
        occupied.add((x, z))
    # plants, never on the path, the posts, the stump or near the pillar
    for (x, z), (bot, top) in cols.items():
        if (x, z) in path or (x, z) in occupied or math.hypot(x - pcx, z - pcz) <= Ro + 2:
            continue
        sb = m.cells.get((x, top, z))
        r = M.h32(seed, 19, x, z) % 100
        if sb == pal["grass"] and r < 16:
            m.put(x, top + 1, z, pal["plants"][0] if r < 11 else pal["plants"][1])
        elif sb == pal["moss"] and r < 30:
            m.put(x, top + 1, z, pal["plants"][2])
    _pillar(spec, m, pcx, pcz, Yt)
    _satellites(spec, m, cols, rimf)
    xs = [x for x, _z in cols]
    zs_ = [z for _x, z in cols]
    tip = min(cols.items(), key=lambda kv: (kv[1][0], kv[0]))
    m.marks["island"] = {"centre": [cx, cz], "top_y": Yt, "bounds": [min(xs), min(zs_), max(xs), max(zs_)],
                         "tip": [tip[0][0], tip[1][0], tip[0][1]], "columns": len(cols),
                         "centre_top": [cx, cols[(cx, cz)][1], cz]}
    return cols


def _ramp(rel, k, Yt, L):
    """The helix's half-step index (0 at the base floor) of lap k at relative bearing rel; past 2 x top_floor is past the top."""
    phi = rel + 360.0 * k
    hs = int(math.floor(phi / 360.0 * 2 * L))
    return hs


def _pillar(spec, m, pcx, pcz, Yt):
    pil, pal = spec["pillar"], spec["palette"]
    seed = spec["seed"]
    Ro, Ri, Rc = pil["outer_radius"], pil["inner_radius"], pil["core_radius"]
    L = pil["lap_rise"]
    yF = Yt + pil["top_floor"]
    total = 2 * pil["top_floor"]               # half-steps from the base floor to the top floor
    laps = int(math.ceil(total / (2.0 * L))) + 1
    ph = [u01(seed, 20, k) * 2 * math.pi for k in range(4)]
    cmin, cmax = pil["crown"]["min"], pil["crown"]["max"]
    holes = []
    ramp_cells = []
    r = int(math.ceil(Ro))
    for x in range(pcx - r, pcx + r + 1):
        for z in range(pcz - r, pcz + r + 1):
            d = math.hypot(x - pcx, z - pcz)
            if d > Ro:
                continue
            th = bearing(x - pcx, z - pcz)
            rel = (th - pil["ramp_start_bearing"]) % 360.0
            m.put(x, Yt, z, pal["floor"])
            if d <= Rc:
                for y in range(Yt + 1, yF + 1):
                    m.put(x, y, z, pal["core"])
                continue
            if d < Ri:
                for y in range(Yt + 1, yF):
                    m.put(x, y, z, AIR)
                floor_open = at_floor = False
                for k in range(laps):
                    hs = _ramp(rel, k, Yt, L)
                    if hs > total:
                        break
                    ry, slab = (Yt + hs // 2, False) if hs % 2 == 0 else (Yt + (hs + 1) // 2, True)
                    stand = Yt + 1 + hs / 2.0
                    if k == 0 and stand < Yt + 4:
                        for y in range(Yt + 1, ry):
                            m.put(x, y, z, pal["ramp_full"])
                    m.put(x, ry, z, pal["ramp_slab"] if slab else pal["ramp_full"])
                    ramp_cells.append((x, ry, z, slab, stand, k, rel))
                    at_floor = at_floor or ry == yF
                    # a walker on this step needs 1.8 of air over it: the top floor above it is opened
                    floor_open = floor_open or (stand > yF - 1.8 and ry < yF)
                if not at_floor:
                    m.put(x, yF, z, AIR if floor_open else pal["floor"])
                    if floor_open:
                        holes.append((x, z))
                continue
            # the wall, its crown broken
            v = math.sin(math.radians(rel) * 3 + ph[0]) * math.cos(math.radians(rel) * 2 + ph[1])
            crown = max(cmin, min(cmax, int(round((cmin + cmax) / 2.0 + (cmax - cmin) / 2.0 * v))
                                  + (M.h32(seed, 21, x, z) % 3) - 1))
            for y in range(Yt + 1, yF + crown + 1):
                b = weighted(seed, pal["wall"], 22, x, y, z)
                if d > Ro - 1 and (y - Yt) in (9, 18, 27):
                    b = pal["band"]
                m.put(x, y, z, b)
    # cut-outs: the door, the return alcove, the windows
    door, recess, sigil = [], [], []
    for x in range(pcx - r, pcx + r + 1):
        for z in range(pcz - r, pcz + r + 1):
            d = math.hypot(x - pcx, z - pcz)
            if not (Ri <= d <= Ro):
                continue
            th = bearing(x - pcx, z - pcz)
            if angdiff(th, pil["door_bearing"]) <= 14:
                for y in range(Yt + 1, Yt + 4):
                    m.put(x, y, z, AIR)
                    door.append((x, y, z))
            elif angdiff(th, pil["return_bearing"]) <= 12:
                if d <= Ri + 1.2:
                    for y in range(Yt + 1, Yt + 4):
                        m.put(x, y, z, AIR)
                        recess.append((x, y, z))
                else:
                    m.put(x, Yt + 2, z, spec["arch"]["sigils"]["sky"])
                    sigil.append((x, Yt + 2, z))
    for wb in (30, 90, 150, 210, 330):
        rel = (wb - pil["ramp_start_bearing"]) % 360.0
        for k in range(laps):
            hs = _ramp(rel, k, Yt, L)
            if hs > total:
                break
            wy = int(math.floor(Yt + 1 + hs / 2.0)) + 1
            if not (Yt + 4 <= wy <= yF - 2):
                continue
            for x in range(pcx - r, pcx + r + 1):
                for z in range(pcz - r, pcz + r + 1):
                    d = math.hypot(x - pcx, z - pcz)
                    if Ri <= d <= Ro and angdiff(bearing(x - pcx, z - pcz), wb) <= 6:
                        m.put(x, wy, z, AIR)
    # lanterns: hanging under the ramp at the middle of the annulus, on posts on the crown
    mid = (Rc + Ri) / 2.0
    for lb in (45, 135, 225, 315):
        lx = pcx + int(round(mid * math.sin(math.radians(lb))))
        lz = pcz - int(round(mid * math.cos(math.radians(lb))))
        rel = (bearing(lx - pcx, lz - pcz) - pil["ramp_start_bearing"]) % 360.0
        for k in range(laps):
            hs = _ramp(rel, k, Yt, L)
            if hs > total:
                break
            ry = Yt + hs // 2 if hs % 2 == 0 else Yt + (hs + 1) // 2
            ly = ry - 1
            below = Yt + 1 if k == 0 else int(math.ceil(Yt + 1 + _ramp(rel, k - 1, Yt, L) / 2.0 + 1.8))
            if ly >= below + 2 and m.cells.get((lx, ly, lz)) == AIR:
                m.put(lx, ly, lz, pal["lantern_hanging"])
    for pb in (270, 0):
        px = pcx + int(round(3 * math.sin(math.radians(pb))))
        pz = pcz - int(round(3 * math.cos(math.radians(pb))))
        if m.cells.get((px, yF, pz)) != pal["floor"]:
            raise SkyError("the crown's lantern post at (%d, %d) has no floor under it" % (px, pz))
        m.put(px, yF + 1, pz, pal["post"])
        m.put(px, yF + 2, pz, pal["lantern"])
    for x in range(pcx - 3, pcx + 4):
        for z in range(pcz - 3, pcz + 4):
            d = math.hypot(x - pcx, z - pcz)
            if d <= 1.5:
                m.put(x, yF + 1, z, pal["dais"])
            elif d <= 2.5:
                m.put(x, yF + 1, z, pal["dais_ring"])
    wood = spec["arch"]["signs"]["wood"]
    sstate = "minecraft:%s_wall_sign[facing=south,waterlogged=false]" % wood
    m.put(pcx, yF + 1, pcz + 3, sstate)
    m.signs.append((pcx, yF + 1, pcz + 3, sstate, sign_nbt(spec["occupant"]["dais_sign"])))
    lb = pil["landing_bearing"]
    land = (pcx + int(round(3 * math.sin(math.radians(lb)))), Yt + 1, pcz - int(round(3 * math.cos(math.radians(lb)))))
    if m.cells.get(land) != AIR or m.cells.get((land[0], land[1] + 1, land[2])) != AIR:
        raise SkyError("the island landing %s is not open" % (land,))
    rx = [c[0] for c in recess]
    rz = [c[2] for c in recess]
    m.marks["pillar"] = {
        "centre": [pcx, pcz], "floor_y": Yt, "top_floor_y": yF,
        "spot": [pcx + 0.5, yF + 2, pcz + 0.5],
        "top_zone": [pcx - 5, yF + 1, pcz - 5, pcx + 5, yF + 12, pcz + 5],
        "recess": [min(rx), Yt + 1, min(rz), max(rx), Yt + 2, max(rz)],
        "landing": list(land), "door_cells": len(door), "sigil": sigil[0] if sigil else None,
        "holes": len(holes), "ramp_cells": len(ramp_cells),
        "first_step": [c for c in ramp_cells if c[5] == 0][0][:3] if ramp_cells else None,
        "crown_top": max(y for (x, y, z), b in m.cells.items() if b != AIR and math.hypot(x - pcx, z - pcz) <= Ro)}
    m.ramp = ramp_cells


def _satellites(spec, m, cols, rimf):
    isl, pal = spec["island"], spec["palette"]
    seed = spec["seed"]
    cx, cz, hx, hz, Yt = isl["centre"]["x"], isl["centre"]["z"], isl["half_x"], isl["half_z"], isl["top_y"]
    out = []
    for i, s in enumerate(isl["satellites"]):
        b = math.radians(s["bearing"])
        r_rim = rimf(b) / math.hypot(math.sin(b) / hx, math.cos(b) / hz)
        dist = r_rim + s["out"] + s["radius"]
        sx = cx + int(round(dist * math.sin(b)))
        sz = cz - int(round(dist * math.cos(b)))
        yc = Yt + s["dy"]
        R = s["radius"]
        for x in range(sx - R - 1, sx + R + 2):
            for z in range(sz - R - 1, sz + R + 2):
                d = math.hypot(x - sx, z - sz)
                if d > R + 0.5:
                    continue
                for nx in range(x - 2, x + 3):
                    for nz in range(z - 2, z + 3):
                        if (nx, nz) in cols and cols[(nx, nz)][0] - 2 <= yc and cols[(nx, nz)][1] + 2 >= yc - 2 * R:
                            raise SkyError("satellite %d at (%d, %d) touches the island" % (i, sx, sz))
                depth = int(round((R + 0.5 - d) * 2.2)) + 1
                for y in range(yc - depth, yc + 1):
                    if y == yc:
                        blk = pal["moss"] if M.h32(seed, 30, x, z) % 3 else "minecraft:mossy_cobblestone"
                    elif yc - y <= 1:
                        blk = weighted(seed, pal["rock"], 31, x, y, z)
                    else:
                        blk = weighted(seed, pal["underside"], 32, x, y, z)
                    m.put(x, y, z, blk)
        if s.get("spire"):
            for k, blk in enumerate(pal["spire"]):
                m.put(sx, yc + 1 + k, sz, blk)
        out.append([sx, yc, sz])
    m.marks["satellites"] = out


def geometry(spec=None, g=None, source_root=None):
    spec = spec or load()
    g = g or G.Ground(source_root)
    m = Model()
    _arch(spec, g, m)
    arch_cells = set(m.cells)
    cols = _island(spec, g, m)
    if any(c[1] < m.marks["arch"]["top"] + 8 for c in set(m.cells) - arch_cells):
        raise SkyError("the island comes within 8 of the arch's top")
    summit = spec["site"]["summit"]
    if g(summit["x"], summit["z"]) != summit["y"]:
        raise SkyError("site.summit y%d but the heightmap says y%d at (%d, %d)"
                       % (summit["y"], g(summit["x"], summit["z"]), summit["x"], summit["z"]))
    isl = m.marks["island"]
    x0, z0, x1, z1 = isl["bounds"]
    for sx, sy, sz in m.marks["satellites"]:
        x0, z0, x1, z1 = min(x0, sx - 6), min(z0, sz - 6), max(x1, sx + 6), max(z1, sz + 6)
    mg = spec["rescue"]["margin"]
    box = [x0 - mg, z0 - mg, x1 + mg, z1 + mg]
    hi = int(g.box(*box).max())
    m.marks["rescue"] = [box[0], hi + 3, box[1], box[2], spec["island"]["top_y"] - 1, box[3]]
    m.marks["ground_max_under"] = hi
    # the island hangs over the cone and never touches it
    low = min(y for (x, y, z), b in m.cells.items() if b != AIR and (x, z) in cols and (x, y, z) not in arch_cells)
    m.marks["island_low"] = low
    for (x, z), (bot, _top) in cols.items():
        if bot - 1 <= g(x, z) + 8:
            raise SkyError("the island's underside at (%d, %d) is y%d, within 8 of the ground y%d" % (x, z, bot, g(x, z)))
    top = m.marks["pillar"]["crown_top"]
    if top > CEILING - 16:
        raise SkyError("the crown tops out at y%d, within 16 of the ceiling y%d" % (top, CEILING))
    return m


# ------------------------------------------------------------------ checks

def spawn_block_problems(m):
    spawn = set(json.loads(SPAWN_BLOCKS.read_text(encoding="utf-8"))["blocks"])
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    allowed = {b for w in policy["whitelist"] if POLICY_SCOPE in (w.get("scope") or "") for b in w["blocks"]}
    used = {base(b) for b in m.cells.values()}
    return ["places %s, a spawn condition (data/spawn_blocks.json), and no data/spawn_block_policy.json entry scoped to %s allows it"
            % (b, POLICY_SCOPE) for b in sorted(used & spawn - allowed)]


def light_problems(m, spec=None):
    """Lanterns on posts or hanging, never a light block (the owner's 2026-10-12 lesson)."""
    post = base((spec or load())["palette"]["post"])
    lights = {"minecraft:glowstone", "minecraft:sea_lantern", "minecraft:shroomlight", "minecraft:magma_block",
              "minecraft:end_rod", "minecraft:froglight", "minecraft:ochre_froglight", "minecraft:verdant_froglight",
              "minecraft:pearlescent_froglight", "minecraft:redstone_lamp", "minecraft:jack_o_lantern", "minecraft:beacon",
              "minecraft:torch", "minecraft:wall_torch", "minecraft:soul_lantern", "minecraft:light", "minecraft:crying_obsidian"}
    out = [("a light block %s at %s" % (base(b), c)) for c, b in m.cells.items() if base(b) in lights]
    for (x, y, z), b in m.cells.items():
        if base(b) == "minecraft:lantern":
            hanging = "hanging=true" in b
            hold = m.cells.get((x, y + 1, z) if hanging else (x, y - 1, z))
            if hold is None or base(hold) == "minecraft:air":
                out.append("a lantern at %s with nothing %s it" % ((x, y, z), "over" if hanging else "under"))
            elif not hanging and base(hold) != post:
                out.append("a standing lantern at %s not on a post (%s)" % ((x, y, z), base(hold)))
    return out


# ------------------------------------------------------------------ the packs

def sel_box(b):
    return "x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d" % (b[0], b[1], b[2], b[3] - b[0], b[4] - b[1], b[5] - b[2])


def nbt(d):
    return "{%s}" % ",".join("%s:%s" % kv for kv in d.items())


def adv_sel(ids, value="true"):
    return "advancements={%s}" % ",".join("%s=%s" % (i, value) for i in ids)


def text(s, color="aqua", italic=True):
    return json.dumps({"text": s, "color": color, "italic": italic}, ensure_ascii=False)


def build_lines(spec, m):
    lines = ["# Generated by tools/rayquaza_sky.py from data/rayquaza_sky.json: Rayquaza's arch, island and pillar.",
             "# One-shot blocks, run by tools/reapply.py step R14R; this function lives in cobblers_rayquaza_build (tools/pack_split.py)",
             "# and holds the chunks it writes for its whole run (tools/function_limits.py ensure_loaded)."]
    sign_cells = {(s[0], s[1], s[2]) for s in m.signs}
    lines += M.column_runs({c: b for c, b in m.cells.items() if c not in sign_cells})
    for x, y, z, state, tag in m.signs:
        lines.append("setblock %d %d %d %s%s" % (x, y, z, state, tag))
    lines = FL.ensure_loaded(lines)
    bad = FL.check_lines(lines, "rayquaza/build")
    if bad:
        raise SkyError("the build function would be refused: %s" % (bad[:3],))
    return lines


def runtime_files(spec, m):
    """{function name under cobblers:rayquaza/: lines} of the runtime pack."""
    occ, gate = spec["occupant"], spec["gate"]
    k = occ["keeper"]
    obj = spec["objective"]
    T, D, Gd = occ["tag"], occ["dormant_tag"], occ["guardian_tag"]
    arch, pil = m.marks["arch"], m.marks["pillar"]
    sx_, sy_, sz_ = pil["spot"]
    sx = "x=%.1f,y=%d,z=%.1f" % (sx_, sy_, sz_)
    at = "%.1f %d %.1f" % (sx_, sy_, sz_)
    yaw = 0
    sp = 'nbt={Pokemon:{Species:"cobblemon:%s"}}' % occ["species"]
    msg = occ["messages"]
    met_adv, caught_adv = own_advancement(spec, "met"), own_advancement(spec, "caught")
    n, ab, gone, resp, caught = ["#%s" % s for s in ("n", "abs", "gone", "resp", "caught")]
    ax, az = arch["centre"]
    P = arch["plinth_y"]
    icx, icz = m.marks["island"]["centre"]
    iy = spec["island"]["top_y"]
    lx, ly, lz = pil["landing"]
    rx, ry, rz = arch["landing"]
    top = pil["top_zone"]
    fn = {}
    fn["load"] = [
        "# Generated by tools/rayquaza_sky.py from data/rayquaza_sky.json. The keeper's state is the world's scoreboard, so a restart",
        "# repeats nothing; every player's state is an advancement (cobblers:legendary/rayquaza/met and /caught) or a tag recomputed",
        "# every pass (%s, %s), so a late joiner, a death or a disconnect leaves nothing stale." % (OK, FRESH),
        "# This pack also ships cobbleverse:spawn_rayquaza EMPTY at its upstream path (data/rayquaza_sky.json upstream_neutralised):",
        "# the End's shiny level-100 Rayquaza is removed by the owner's decision of 2026-10-06; nothing here calls it.",
        "scoreboard objectives add %s dummy" % obj,
        "execute unless score %s %s matches -2147483648.. run scoreboard players set %s %s %d" % (gone, obj, gone, obj, NEVER),
        "schedule function %s/tick %dt replace" % (F, gate["period_ticks"]),
        "schedule function %s/keeper %dt replace" % (F, k["period_ticks"])]
    fn["tick"] = [
        "# every %d ticks: the told tag goes when its player leaves the arch; the arch and the island run only while somebody is near"
        % gate["period_ticks"],
        "execute as @a[tag=%s] unless entity @s[%s] run tag @s remove %s" % (TOLD, sel_box(arch["told"]), TOLD),
        "execute positioned %d %d %d if entity @a[distance=..%d] run function %s/arch" % (ax, P + 1, az, gate["arch_reach"], F),
        "execute positioned %d %d %d if entity @a[distance=..%d] run function %s/island" % (icx, iy, icz, gate["island_reach"], F),
        "schedule function %s/tick %dt replace" % (F, gate["period_ticks"])]
    fn["qualify"] = [
        "# who holds the gate (%s: %s) and who of them has not caught Rayquaza here (%s)." % (OK, ", ".join(gate_advancements(spec)), FRESH),
        "# A met advancement no installed pack defines matches nobody, so the gate fails closed (contract C26).",
        "tag @a remove %s" % OK,
        "tag @a remove %s" % FRESH,
        "tag @a[%s] add %s" % (adv_sel(gate_advancements(spec)), OK),
        "tag @a[tag=%s,%s] add %s" % (OK, adv_sel([caught_adv], "false"), FRESH)]
    fn["arch"] = [
        "# the sealed arch: a qualified player in the doorway crosses; anyone else is told once a visit which mark is dark",
        "function %s/qualify" % F,
        "execute as @a[%s,tag=%s,gamemode=!spectator] run function %s/cross" % (sel_box(arch["door"]), OK, F),
        "execute as @a[%s,tag=!%s,tag=!%s,gamemode=!spectator] run function %s/sealed" % (sel_box(arch["door"]), OK, TOLD, F)]
    fn["cross"] = [
        "# as the qualified player in the doorway: up to the island, landing inside the pillar's base",
        "tp @s %d.5 %d %d.5 0 0" % (lx, ly, lz),
        "tellraw @s %s" % text(msg["cross"]),
        "playsound minecraft:block.beacon.activate master @s %d %d %d 1 1.4" % (lx, ly, lz)]
    champ = adv_sel(["%s:flag/%s" % (spec["namespace"], f) for f in gate["flags"]])
    met = {mm: adv_sel([gate["met_advancement"] % mm]) for mm in gate["requires_met"]}
    fn["sealed"] = [
        "# as the player in the doorway who does not hold the gate: once a visit, why it is shut",
        "tag @s add %s" % TOLD,
        "execute unless entity @s[%s] run tellraw @s %s" % (champ, text(msg["sealed_league"], "gray")),
        "execute if entity @s[%s] unless entity @s[%s] run tellraw @s %s" % (champ, met["kyogre"], text(msg["sealed_sea"], "gray")),
        "execute if entity @s[%s] unless entity @s[%s] run tellraw @s %s" % (champ, met["groudon"], text(msg["sealed_fire"], "gray")),
        "playsound minecraft:block.beacon.deactivate master @s %d %d %d 1 0.6" % (ax, P + 2, az)]
    fn["island"] = [
        "# the island: the fall, the way back down, the met record",
        "function %s/qualify" % F,
        "effect give @a[%s,gamemode=!spectator] %s %d 0 true" % (sel_box(m.marks["rescue"]), spec["rescue"]["effect"], spec["rescue"]["seconds"]),
        "execute as @a[%s,gamemode=!spectator] run function %s/return" % (sel_box(pil["recess"]), F),
        "execute if entity @e[type=cobblemon:pokemon,tag=%s,%s,distance=..8] as @a[%s,tag=%s,%s] run function %s/met"
        % (T, sx, sel_box(top), OK, adv_sel([met_adv], "false"), F)]
    fn["return"] = [
        "# as anyone in the pillar's west alcove, qualified or not: back down to the summit, in front of the arch",
        "tp @s %d.5 %d %d.5 180 0" % (rx, ry, rz),
        "tellraw @s %s" % text(msg["return"])]
    fn["met"] = [
        "# as a qualified player on the crown while Rayquaza is there, once: the per-player record",
        "advancement grant @s only %s" % met_adv,
        "tellraw @s %s" % text(msg["met"], "gold", False)]
    fn["keeper"] = [
        "# the keeper's loop: only while the crown's chunk is loaded (nobody has to be near for the return clock)",
        "execute store result score #now %s run time query gametime" % obj,
        "execute if loaded %d %d %d run function %s/keep" % (int(sx_), sy_, int(sz_), F),
        "schedule function %s/keeper %dt replace" % (F, k["period_ticks"])]
    fn["keep"] = [
        "# tools/sanctuaries.py boss_files' keeper, rewritten for this gate. Present: ours by tag (a guardian keeps our tag), or a",
        "# guardian the blackout REBUILT, which does not, found by its tag and species near the spot. Never a guardian killed, held,",
        "# woken, settled or withdrawn.",
        "function %s/qualify" % F,
        "execute store result score %s %s if entity @e[type=cobblemon:pokemon,tag=%s]" % (n, obj, T),
        "execute if score %s %s matches 0 if entity @e[type=cobblemon:pokemon,tag=%s,%s,distance=..%d,%s] run scoreboard players set %s %s 1"
        % (n, obj, Gd, sx, k["guardian_search_radius"], sp, n, obj),
        "execute if score %s %s matches 2.. as @e[type=cobblemon:pokemon,tag=%s,tag=!%s,%s,limit=1,sort=furthest] run function %s/discard"
        % (n, obj, T, Gd, sx, F),
        "execute if score %s %s matches 1.. run scoreboard players set %s %s 0" % (n, obj, ab, obj),
        "execute if score %s %s matches 1.. run scoreboard players set %s %s %d" % (n, obj, gone, obj, PRESENT),
        "execute if score %s %s matches 1.. run scoreboard players set %s %s 0" % (n, obj, caught, obj),
        "execute if score %s %s matches 1.. as @e[type=cobblemon:pokemon,tag=%s,tag=!%s] run function %s/hold" % (n, obj, T, Gd, F),
        "execute if score %s %s matches 1.. run return 0" % (n, obj),
        "# absent on %d loaded passes in a row before it counts as gone" % k["absent_passes"],
        "scoreboard players add %s %s 1" % (ab, obj),
        "execute if score %s %s matches ..%d run return 0" % (ab, obj, k["absent_passes"] - 1),
        "# first seen gone (fainted or caught; a withdrawal set the clock to NEVER and starts none): %d after a catch, %d after a faint"
        % (k["cooldown_catch_ticks"], k["cooldown_faint_ticks"]),
        "execute if score %s %s matches %d run scoreboard players set %s %s %d" % (gone, obj, PRESENT, resp, obj, k["cooldown_faint_ticks"]),
        "execute if score %s %s matches %d if score %s %s matches 1 run scoreboard players set %s %s %d"
        % (gone, obj, PRESENT, caught, obj, resp, obj, k["cooldown_catch_ticks"]),
        "execute if score %s %s matches %d run scoreboard players operation %s %s = #now %s" % (gone, obj, PRESENT, gone, obj, obj),
        "scoreboard players set %s %s 0" % (caught, obj),
        "scoreboard players operation #d %s = #now %s" % (obj, obj),
        "scoreboard players operation #d %s -= %s %s" % (obj, gone, obj),
        "execute if score %s %s matches %d run scoreboard players set #d %s 2000000000" % (gone, obj, NEVER, obj),
        "execute if score #d %s < %s %s run return 0" % (obj, resp, obj),
        "# never conjured in front of anyone, and only for a player who holds the gate and has not caught it",
        "execute if entity @a[%s,distance=..%d] run return 0" % (sx, k["spawn_clear"]),
        "execute unless entity @a[%s,distance=..%d,gamemode=!spectator,tag=%s] run return 0" % (sx, k["spawn_radius"], FRESH),
        "function %s/spawn" % F]
    fn["hold"] = [
        "# as the Pokemon (never a guardian). DORMANT: held on its spot; withdrawn when nobody who may meet it is near; woken for",
        "# such a player on the crown, never while a stranger stands there. AWAKE: quiet again if a stranger comes; settled when the",
        "# qualified have gone.",
        "execute if entity @s[tag=%s] unless entity @s[%s,distance=..%s] run tp @s %s %d 0" % (D, sx, k["home_tolerance"], at, yaw),
        "execute if entity @s[tag=%s] unless entity @a[%s,distance=..%d,gamemode=!spectator,tag=%s] run return run function %s/withdraw"
        % (D, sx, k["spawn_radius"], FRESH, F),
        "execute if entity @s[tag=%s] if entity @a[%s,gamemode=!spectator,tag=%s] unless entity @a[%s,gamemode=!spectator,tag=!%s] run return run function %s/wake"
        % (D, sel_box(top), FRESH, sel_box(top), OK, F),
        "execute if entity @s[tag=!%s] if entity @a[%s,gamemode=!spectator,tag=!%s] run return run function %s/hush" % (D, sel_box(top), OK, F),
        "execute if entity @s[tag=!%s] unless entity @a[%s,distance=..%d,gamemode=!spectator,tag=%s] run function %s/settle"
        % (D, sx, k["settle_radius"], OK, F)]
    fn["wake"] = [
        "# as the Pokemon: the trigger is a state check on the keeper's own loop, never an advancement (CELEBI_WAKE.md 1)",
        "tag @s remove %s" % D,
        "data merge entity @s %s" % nbt(occ["awake_nbt"]),
        "tellraw @a[%s,distance=..48] %s" % (sx, text(msg["wake"], "gold")),
        "playsound minecraft:block.beacon.activate hostile @a[%s,distance=..48] %s 2 0.6" % (sx, at)]
    fn["hush"] = [
        "# as the awake Pokemon while a player who does not hold the gate stands on the crown: it will not be battled",
        "tag @s add %s" % D,
        "data merge entity @s {Unbattleable:1b}",
        "tellraw @a[%s] %s" % (sel_box(top), text(msg["hush"], "gray"))]
    fn["settle"] = [
        "# as the Pokemon: everyone who may meet it has gone, so it lies down again on its spot",
        "tp @s %s %d 0" % (at, yaw),
        "data merge entity @s %s" % nbt(occ["dormant_nbt"]),
        "tag @s add %s" % D]
    fn["withdraw"] = [
        "# as the dormant Pokemon (never a guardian) with nobody near who may meet it: it does not wait there for an early flyer.",
        "# No clock starts (the next qualified player brings it back). It goes under the world before the kill, so the drops",
        "# its species carries are discarded below the world and cannot be farmed by walking away and back.",
        "scoreboard players set %s %s %d" % (gone, obj, NEVER),
        "scoreboard players set %s %s 0" % (ab, obj),
        "function %s/discard" % F]
    fn["discard"] = [
        "# as one of ours (never a guardian: every caller selects tag=!%s): under the world, then killed there, so its drops" % Gd,
        "# fall below the world and are discarded",
        "tp @s %.1f -200 %.1f" % (sx_, sz_),
        "kill @s"]
    props = " ".join(["level=%d" % occ["level"]] + list(occ["properties"]))
    fn["spawn_at"] = ["$spawnpokemonat $(x) $(y) $(z) %s %s" % (occ["species"], props)]
    fn["spawn"] = [
        "# a wild one through the macro (EXP-046), then bound at once (an unclaimed Pokemon is despawned within a minute)",
        "function %s/spawn_at {x:\"%.1f\",y:%d,z:\"%.1f\"}" % (F, sx_, sy_, sz_),
        "execute positioned %s as @e[type=cobblemon:pokemon,tag=!%s,distance=..3,%s,limit=1,sort=nearest] run function %s/bind" % (at, T, sp, F)]
    fn["bind"] = [
        "# as the new Pokemon: tagged, kept from the despawner (PersistenceRequired, EXP-041), dormant on its spot",
        "tag @s add %s" % T, "tag @s add %s" % D,
        "data merge entity @s %s" % nbt(occ["dormant_nbt"]),
        "tp @s %s %d 0" % (at, yaw),
        "scoreboard players set %s %s %d" % (gone, obj, PRESENT),
        "scoreboard players set %s %s 0" % (ab, obj),
        "scoreboard players set %s %s 0" % (caught, obj)]
    fn["caught"] = [
        "# as the catcher of a %s within %d of the crown (the pokemon_captured callback): once per player, keyed on the catch"
        % (occ["species"], k["catch_radius"]),
        "advancement grant @s only %s" % caught_adv,
        "advancement grant @s only %s" % met_adv,
        "scoreboard players set %s %s 1" % (caught, obj)]
    return fn


def pack_files(spec, m):
    files = {"pack.mcmeta": json.dumps({"pack": {"pack_format": 48, "description": "Cobblers: Rayquaza's arch, island and keeper (tools/rayquaza_sky.py, data/rayquaza_sky.json)"}}, indent=2) + "\n"}
    fns = runtime_files(spec, m)
    fns[BUILD] = build_lines(spec, m)
    for name, body in fns.items():
        bad = FL.check_lines(body, name)
        if bad:
            raise SkyError("function %s would be refused: %s" % (name, bad[:3]))
        files["data/%s/function/%s/%s.mcfunction" % (NS, FOLDER, name)] = "\n".join(body) + "\n"
    files["data/minecraft/tags/function/load.json"] = json.dumps({"values": ["%s/load" % F]}, indent=2) + "\n"
    for what in ("met", "caught"):
        adv = own_advancement(spec, what)
        ns, path = adv.split(":", 1)
        files["data/%s/advancement/%s.json" % (ns, path)] = json.dumps(
            {"criteria": {"granted": {"trigger": "minecraft:impossible"}}, "requirements": [["granted"]]}, indent=2) + "\n"
    up = spec["upstream_neutralised"]
    files[up["path"]] = ("# %s, overridden EMPTY by tools/rayquaza_sky.py (data/rayquaza_sky.json upstream_neutralised):\n"
                         "# %s. Upstream it ran:\n# %s\n" % (up["function"], up["decision"], up["upstream_text"]))
    k = spec["occupant"]["keeper"]
    sx_, sy_, sz_ = m.marks["pillar"]["spot"]
    cmd = ("execute as ' + q.player.uuid + ' at @s if entity @s[x=%d,y=%d,z=%d,distance=..%d] run function %s/caught"
           % (int(sx_), sy_, int(sz_), k["catch_radius"], F))
    files["data/cobblemon/callbacks/pokemon_captured/cobblers_rayquaza.molang"] = "\n".join([
        "'Generated by tools/rayquaza_sky.py from data/rayquaza_sky.json. A Rayquaza caught near the crown is recorded for its',",
        "'catcher (once per player) and tells the keeper, which then waits the catch clock. Anywhere else it does nothing.';",
        "t.id = q.pokemon.species.identifier;",
        "t.id == 'cobblemon:%s' ? {" % spec["occupant"]["species"],
        "  q.run_command('%s');" % cmd,
        "};"]) + "\n"
    return files


def write(files, out=None):
    import pack_split
    out = Path(out or OUT)
    if out.exists():
        shutil.rmtree(out)
    for rel, body in files.items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8", newline="\n")
    moved, bout = pack_split.split(out, lambda fid: fid == "%s/%s" % (F, BUILD), BUILD_DESCRIPTION)
    if moved != 1:
        raise SkyError("pack_split moved %d functions, expected the one build function" % moved)
    return out, bout


# ------------------------------------------------------------------ records and steps

def probe_records(spec, m):
    rows = []

    def blk(what, c, state):
        rows.append({"what": "rayquaza_sky: " + what, "block": [int(c[0]), int(c[1]), int(c[2]), base(state)], "expect": True})
    a, p, i = m.marks["arch"], m.marks["pillar"], m.marks["island"]
    blk("the arch's keystone", a["keystone"], m.cells[tuple(a["keystone"])])
    blk("the sky mark on the lintel", a["sky_sigil"], m.cells[tuple(a["sky_sigil"])])
    blk("air in the doorway", a["doorway_air"], AIR)
    blk("the island's top at its centre", i["centre_top"], m.cells[tuple(i["centre_top"])])
    blk("the island's lowest block", i["tip"], m.cells[tuple(i["tip"])])
    gap = (i["tip"][0], i["tip"][1] - 4, i["tip"][2])
    blk("air under the island", gap, AIR)
    blk("the pillar's first step", p["first_step"], m.cells[tuple(p["first_step"])])
    blk("the alcove back down, open", (p["recess"][0], p["recess"][1], p["recess"][2]), AIR)
    blk("the crown's dais", (p["centre"][0], p["top_floor_y"] + 1, p["centre"][1]), m.cells[(p["centre"][0], p["top_floor_y"] + 1, p["centre"][1])])
    blk("the crown's floor", (p["centre"][0] + 3, p["top_floor_y"], p["centre"][1] - 1), m.cells[(p["centre"][0] + 3, p["top_floor_y"], p["centre"][1] - 1)])
    sx, sy, sz, state, _ = m.signs[0]
    blk("the arch's left sign", (sx, sy, sz), state)
    s = m.marks["satellites"][0]
    blk("the first drifting rock's top", s, m.cells[tuple(s)])
    occ = spec["occupant"]
    rows.append({"what": "rayquaza_sky: Rayquaza (one tagged %s while a qualified player who has not caught it is near the crown;"
                         " absent otherwise)" % occ["tag"],
                 "hold": [int(p["spot"][0]), p["spot"][1], int(p["spot"][2])],
                 "entity": "@e[type=cobblemon:pokemon,tag=%s]" % occ["tag"], "count_max": 1})
    return rows


def probes_drift(spec, m):
    doc = json.loads(PROBES.read_text(encoding="utf-8"))
    return doc["places"].get(PROBE_KEY) != probe_records(spec, m)


def sync(spec, m):
    doc = json.loads(PROBES.read_text(encoding="utf-8"))
    doc["places"][PROBE_KEY] = probe_records(spec, m)
    PROBES.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def placement_steps(spec=None):
    """For tools/reapply.py step R14R: the one build function, which force-loads what it writes for its own run."""
    return [("fn", "%s/%s" % (F, BUILD))]


def step_functions(spec=None):
    return ["%s/%s" % (F, BUILD)]


# ------------------------------------------------------------------ the command line

def report(spec, m):
    a, p, i = m.marks["arch"], m.marks["pillar"], m.marks["island"]
    s = spec["site"]["summit"]
    print("summit (%d, %d) y%d; arch at (%d, %d), plinth y%d, top y%d" % (s["x"], s["z"], s["y"], a["centre"][0], a["centre"][1], a["plinth_y"], a["top"]))
    print("island centre (%d, %d), top y%d, %d columns, bounds %s, lowest block %s (%d over the summit, %d over the arch's top)"
          % (i["centre"][0], i["centre"][1], i["top_y"], i["columns"], i["bounds"], i["tip"], i["tip"][1] - s["y"], i["tip"][1] - a["top"]))
    print("pillar at (%d, %d): floor y%d, crown floor y%d, crown top y%d, %d ramp cells, %d floor cells open over the ramp"
          % (p["centre"][0], p["centre"][1], p["floor_y"], p["top_floor_y"], p["crown_top"], p["ramp_cells"], p["holes"]))
    print("landing %s, alcove %s, Rayquaza at %s; rescue box %s (highest ground under it y%d)"
          % (p["landing"], p["recess"], p["spot"], m.marks["rescue"], m.marks["ground_max_under"]))
    print("satellites %s" % m.marks["satellites"])
    print("cells %d, signs %d" % (len(m.cells), len(m.signs)))
    probs = spawn_block_problems(m) + light_problems(m, spec)
    for pr in probs:
        print("PROBLEM", pr)
    return probs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=("report", "build", "sync"))
    ap.add_argument("--source-root", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    spec = load()
    m = geometry(spec, G.Ground(a.source_root) if a.source_root else None)
    if a.cmd == "report":
        return 1 if report(spec, m) else 0
    probs = spawn_block_problems(m) + light_problems(m, spec)
    if probs:
        raise SkyError("refused:\n  " + "\n  ".join(probs))
    if a.cmd == "sync":
        sync(spec, m)
        print("data/world_probes.json: %d rayquaza_sky records" % len(probe_records(spec, m)))
        return 0
    if probes_drift(spec, m):
        raise SkyError("data/world_probes.json's %s records drifted from the geometry: python tools/rayquaza_sky.py sync" % PROBE_KEY)
    files = pack_files(spec, m)
    out, bout = write(files, a.out)
    nb = len(files["data/%s/function/%s/%s.mcfunction" % (NS, FOLDER, BUILD)].splitlines())
    print("built %s (%d files) and %s (the build function, %d lines)" % (out.name, len(files) - 1, bout.name, nb))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python
"""A fresh player's walk through the critical path, offline, from the BUILT packs: can a new player get a starter,
reach gym 1 and beat it -- and how far past that the same model reaches.

WHY THIS EXISTS. The owner, 2026-10-05, on docs/world-building/CRITICAL_PATH_WALK_1.md and _2.md: "Every tour and
every audit missed four P0s because nobody ever started as a player ... 'Can a new player get a starter, reach gym 1,
and beat it' should be something we know the answer to continuously, not something discovered once." Every other
audit checks one system against its own design. This one starts where a player starts and asks each system in turn
whether the player can get past it, reading what the generators EMITTED (build/datapacks/...), not what the designers
intended (data/...), wherever an emitted artifact exists.

STAGES, in walking order. Each is PASS, FAIL or NOT_MODELLED; a stage is FAIL if any of its checks fails,
NOT_MODELLED if none fails but one could not be modelled, and PASS only when every check was modelled and passed.

  spawn_to_oak  the world spawn as the hometown function sets it (cobblers_towns towns/hometown `setworldspawn`),
                Oak's seat (data/npc_seats.json npc_main_pallet_oak, which reapply R17N summons) and his class in the
                compiled dialogue; a walk between them on the heightmap.
  starter       tools/oak_starter_audit.py run as a CLI (its verdict, nothing reused from it); the five
                modpack/config/cobblemon/starters.json entries each resolve to a FORM in the built
                cobblers_mythical_starters pack, and that form knows a damaging move at its offered level.
  route_N       the walked line (data/route_paths.json) as a corridor on the heightmap, with the links from the last
                gym's lot (or Oak) onto it and from its end to the next gym's lot; every trainer that forces a
                battle on sight (its built rctmod mob) and is seated (the built cycle function) within its sight
                distance of the line is MUST-PASS and has to be beatable; the others are reported.
  gym_N         the leader's id from the built badge advancement (cobblers_progression flag/gymN_cleared); his
                spawner in a built function; the hall walk from tools/gym_buildings_independent.py's own movement
                model (imported and run, its blocking codes only); the level cap from the RCT config; each starter
                plus the routes' catchables at the cap against the built team (tools/battle_sim.py); the badge
                wired (advancement -> granted function -> first_win loot table holding a badge); the cap advancing.
                Every gym also asks cap_reachable: the leader fought at the top wild level met by then (routes 1..N);
                beaten there, the cap need not be reached (PASS); lost there and won at the cap, the levels between
                come from XP, which is NOT_MODELLED; no wild pool at all is a FAIL.
  victory_road  data/route_paths.json victory_road as a corridor from gym 8's lot, with the zones the line crosses
                admitting a player holding the eight gym flags; the flag past the caves (cobblers:flag/
                rift_crisis_resolved) emitted -- its advancement, a built function granting it, and a compiled
                dialogue or function calling that; each authored stand (data/vr_trainers.json) seated by the built
                cycle function at its seat, with a forced-battle mob, and admitted by every enforced zone it stands in
                (CRITICAL_PATH_WALK_2 item 1); the forced fights at the cap, with cap_reachable. The caves themselves
                and the story chain to the flag are NOT_MODELLED by name.
  league        the League template placed by a built function (its footprint from the emitted `place template`
                and the template's size); every enforced zone over that footprint admitting the flags held
                (CRITICAL_PATH_WALK_2 item 4: a zone that is built but has no zone advancement is reported as a
                warning, not enforced); a walk from Victory Road's line end to the footprint; the champion_cleared
                flag bound to kanto_champion_blue and rewarded; the five fights at the cap, with cap_reachable. The
                template's spawners and the Elite Four's order (upstream) are NOT_MODELLED by name.
  multiplayer   NOT_MODELLED: a second player's flags, reveal cursors and hold-offs (CRITICAL_PATH_WALK_1 item 3).

THE ZONE MODEL is the built cobblers_rift_zones pack read as the server runs it: a zone is enforced only when a built
advancement's location boxes call its zone function; that function turns back on a score; a held advancement set
admits only when its line runs BEFORE the turn-back line and calls a function that sets that score. A knock box (a
built *_knock advancement) admits the sets that, through the functions it calls, reach a function setting that score.
A stand or a lot inside a zone passes if the zone admits the flags on entry, or a knock box admitting them lies within
the corridor of the routed path. A zone that admits the flags neither way is closed to every walk at that point (its
columns, every y); one whose knock admits them is assumed knocked at -- the walks do not route through the knock box.

THE MOVEMENT MODEL (stage spawn_to_oak and every route) IS COARSE, and says so in each check: the canonical heightmap
(tools/ground.py, rounded), 4-connected, a step climbs at most 1 block and drops at most 3 (the rule
CRITICAL_PATH_WALK_2 walked by), and a column under the sea or a painted lake (tools/water_mask.py's rule) is not
walked. It does not see buildings, walls, doors, trees (the Route 1 maze forest), fences, paving, river water,
bridges, the Rift sculpt's block pass or anything else a pack places. A PASS says the terrain allows the walk.

THE BATTLE MODEL is tools/battle_sim.py's, with all its stated limits (no items, no switching by the foe, IVs 15,
level-up moves only). Players: the starter at the stage's level (its form chain read from the built forms pack; a
Kubfu scroll evolution is not taken), plus, from route 2 on, the five route catchables (the compiled route pools of
cobblers_spawns, routes 1..N) that win the most one-on-ones against the foe, at the same level. Route 1's must-pass
fights use the starter ALONE: nothing guarantees a Poke Ball before the first trainer
(CRITICAL_PATH_WALK_1 section 2 item 5). A route trainer is fought at min(cap, the highest wild level met by then):
every pool of the earlier routes, and the entries of its own route whose box lies nearest the line at or before the
trainer's point. A fresh starter at its offered level is also tried against Route 1's forced fights (a warning).
Gym leaders, Victory Road and the League are fought at the cap, which is max(initialLevelCap, ace + relativeLevelCap).
A fight counts as beatable when the team wins never switching OR with battle_sim's switching bound.

WHAT THIS DOES NOT COVER (it is not a boot, and validity is not behaviour): whether Cobblemon applies the forms, the
screen opens, an rctmod spawner spawns, the advancement fires, the cap moves, a door opens or a player can actually
walk any of it. Gym 2's spawner is inside a donor template, not a text function, and its hall is not modelled.
Rivers, bridges, buildings and the Rift's zone checks are invisible to the walk. The cap's advance is computed from
rctmod's rule (docs/mechanics/LEAGUE_LEVEL_CAP.md, relayed), not read from rctmod's series data, which is upstream.

  python tools/new_player_walk.py                   # every stage; exit 1 if any FAILs
  python tools/new_player_walk.py --only gym_1      # one stage (repeatable)
  python tools/new_player_walk.py --packs <dir>     # another build's datapacks (read only)
  python tools/new_player_walk.py --from-data <dir> # build what committed data alone can build into <dir>, walk it
  python tools/new_player_walk.py --no-battles      # every check but the fights (those report NOT_MODELLED)
Writes derived/new_player_walk/report.json; the last line printed is the one-line verdict.

DATA MODE (--from-data). The packs that need only data/, tools/ and modpack/ are generated into the directory by
their own generators (progression, trainers, spawns, dialogue, mythical starters; rift zones and gym buildings also
need the heightmap; the donor placements except those needing the server's templates, which the League does not).
cobblers_towns (kits/) is not built, and every check that reads it reports NOT_MODELLED naming the missing input,
never FAIL and never PASS.
"""
from __future__ import annotations

import argparse
import functools
import json
import math
import re
import subprocess
import sys
import zipfile
from collections import deque
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
PACKS = ROOT / "build" / "datapacks"
OUT = ROOT / "derived" / "new_player_walk" / "report.json"

# This tool decides nothing about where anything goes and reads no world.
WORLD_READS = set()

PASS, FAIL, NM = "PASS", "FAIL", "NOT_MODELLED"
CLIMB, DROP = 1, 3          # blocks a step may rise / fall (CRITICAL_PATH_WALK_2's walk rule)
CORRIDOR = 16               # half-width of a route corridor, blocks
LINK_MARGIN = 40            # the box round a link walk, blocks
LOT_RING = 2                # a lot is reached at any column within this many blocks outside its rect
BLOCKING = {"unreachable", "trap", "fatal", "drown_trap", "drown"}   # gym audit codes that stop a player
GYM_COUNT = 8
LEAGUE = ["kanto_league_lorelei", "kanto_league_bruno", "kanto_league_agatha", "kanto_league_lance",
          "kanto_champion_blue"]
TEAM_EXTRA = 5
LEAGUE_TEMPLATE = "cobbleverse:kanto_league"     # upstream's id; data/league_trainers.json why_overrides_and_not_seats
CHAMPION_FLAG = "champion_cleared"
CRISIS_FLAG = "cobblers:flag/rift_crisis_resolved"
# every pack a full walk reads; a build/ missing one of them is not a build this walk can judge
REQUIRED_PACKS = ("cobblers_towns", "cobblers_dialogue", "cobblers_mythical_starters", "cobblers_trainers",
                  "cobblers_spawns", "cobblers_gym_buildings", "cobblers_progression", "cobblers_rift_zones",
                  "cobblers_donor")

# Failures already reported and not yet decided, so that prepare is not stopped by a finding the owner already has.
# Each still prints (as KNOWN) on every run, and an entry whose check no longer fails is printed FIXED? and fails the
# run until it is removed here. Never add one to make a run pass without reporting it.
KNOWN = {
    ("league", "beat:kanto_champion_blue"):
        "2026-10-05, this tool's first run: under battle_sim's model Blue (L58-62, Focus Sash, Shell Smash, Life Orb) "
        "beats every starter + 5 route catchables at the L62 cap, never switching and switching (5 of 6 downed at "
        "best). battle_sim is biased against the player (no bag items, level-up moves only); the owner's call.",
}


class Stage:
    def __init__(self, sid, title):
        self.id, self.title, self.checks, self.warnings = sid, title, [], []

    def add(self, name, verdict, evidence, coarse=False, not_covered=None):
        self.checks.append({"check": name, "verdict": verdict, "coarse": coarse, "evidence": evidence,
                            "not_covered": not_covered})
        return verdict

    @property
    def verdict(self):
        vs = [c["verdict"] for c in self.checks]
        if not vs:
            return NM
        if FAIL in vs:
            return FAIL
        if NM in vs:
            return NM
        return PASS

    def summary(self):
        bad = [c for c in self.checks if c["verdict"] != PASS]
        if not bad:
            return "%d check(s) pass%s" % (len(self.checks),
                                            " (coarse)" if any(c["coarse"] for c in self.checks) else "")
        c = next((c for c in bad if c["verdict"] == FAIL), bad[0])
        e = c["evidence"]
        return "%s: %s" % (c["check"], e if isinstance(e, str) else e.get("summary") or json.dumps(e)[:240])

    def as_dict(self):
        return {"id": self.id, "title": self.title, "verdict": self.verdict, "checks": self.checks,
                "warnings": self.warnings}


# ------------------------------------------------------------------------------------------ the inputs

class Inputs:
    """Everything the walk reads, loaded lazily so a test can hand any piece in."""

    def __init__(self, root=ROOT, packs=None, source_root=None, ground=None, battle=None, raw=None, water=None,
                 gym_audit=None, oak=None, battles=True, unbuilt=None):
        self.root = Path(root)
        self.packs = Path(packs) if packs else self.root / "build" / "datapacks"
        self.source_root = source_root
        self.battles = battles
        # {pack: why it was not built} in data mode: a check reading one reports NOT_MODELLED, not FAIL
        self.unbuilt = dict(unbuilt or {})
        self._ground, self._battle, self._raw, self._water = ground, battle, raw, water
        self._jar = None
        self._gym_audit = gym_audit
        self.oak = oak or run_oak_audit

    def data(self, name):
        return json.loads((self.root / "data" / name).read_text(encoding="utf-8"))

    @property
    def ground(self):
        if self._ground is None:
            sys.path.insert(0, str(TOOLS))
            import ground as G
            self._ground = G.load(self.source_root)
        return self._ground

    @property
    def water(self):
        """(sea level, {body: {"level_y", "basin"}})."""
        if self._water is None:
            sys.path.insert(0, str(TOOLS))
            import water_mask as W
            self._water = (W.sea_level(self.root / "data" / "world.json"),
                           W.bodies(self.root / "data" / "landmarks.json"))
        return self._water

    def jar(self):
        if self._jar is None:
            import battle_sim as B
            self._jar = B.find_jar()
        return self._jar

    @property
    def battle(self):
        """(species, moves, chart) from the Cobblemon jar, through tools/battle_sim.py."""
        if self._battle is None:
            import battle_sim as B
            self._battle = B.load_pack(self.jar())
        return self._battle

    @property
    def raw(self):
        """Every species file in the jar, implemented or not, by battle_sim's key: Cosmog, Kubfu, Type: Null and
        Meltan are `implemented: false` in the bare jar and battle_sim's own load drops them."""
        if self._raw is None:
            import battle_sim as B
            out = {}
            with zipfile.ZipFile(self.jar()) as z:
                for n in z.namelist():
                    if n.startswith("data/cobblemon/species/") and n.endswith(".json"):
                        d = json.loads(z.read(n))
                        out[B.key(d["name"])] = d
            self._raw = out
        return self._raw

    def gym_audit(self):
        """{gym id: [(code, text)]} from tools/gym_buildings_independent.py's own run over the built functions."""
        if self._gym_audit is None:
            import gym_buildings_independent as GBI
            funcs = self.packs / "cobblers_gym_buildings" / "data" / "cobblers" / "function" / "gym_buildings"
            records = GBI.load_records(self.root)
            texts = GBI.load_texts(funcs, sorted(records))
            placements = self.data("placements.json")
            rep, _s, _w, _e = GBI.run(texts, records, placements, self.ground, root=self.root)
            out = {g: [] for g in records}
            for gid, code, text in rep.items:
                out.setdefault(gid, []).append((code, text))
            self._gym_audit = (out, {g: t is not None for g, t in texts.items()})
        return self._gym_audit


# ------------------------------------------------------------------------------------------ the walk

def wet_mask(G, x0, z0, sea, bodies):
    """Columns under the sea or a painted lake, tools/water_mask.py's rule, rasterised over one box."""
    from PIL import Image, ImageDraw
    wet = G < sea
    h, w = G.shape
    for b in bodies.values():
        for ring in b.get("basin") or []:
            xs = [p[0] for p in ring]
            zs = [p[1] for p in ring]
            if max(xs) < x0 or min(xs) > x0 + w - 1 or max(zs) < z0 or min(zs) > z0 + h - 1 or len(ring) < 3:
                continue
            im = Image.new("1", (w, h), 0)
            ImageDraw.Draw(im).polygon([(x - x0, z - z0) for x, z in ring], fill=1)
            inside = np.array(im, dtype=bool)
            wet |= inside & (G < b["level_y"])
    return wet


def flood(G, ok, starts):
    """Breadth-first steps from `starts` over `ok` cells, 4-connected, CLIMB up and DROP down. -1 = not reached."""
    h, w = G.shape
    g = G.tolist()
    okl = ok.tolist()
    seen = [[-1] * w for _ in range(h)]
    q = deque()
    for r, c in starts:
        if 0 <= r < h and 0 <= c < w and okl[r][c] and seen[r][c] < 0:
            seen[r][c] = 0
            q.append((r, c))
    while q:
        r, c = q.popleft()
        here, d = g[r][c], seen[r][c] + 1
        for nr, nc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
            if 0 <= nr < h and 0 <= nc < w and seen[nr][nc] < 0 and okl[nr][nc]:
                dy = g[nr][nc] - here
                if dy <= CLIMB and -dy <= DROP:
                    seen[nr][nc] = d
                    q.append((nr, nc))
    return np.array(seen, dtype=np.int64)


def walk(inp, starts, goals, line=None, radius=CORRIDOR, margin=LINK_MARGIN, closed=()):
    """Can a player walk from any of `starts` to any of `goals` ((x, z) lists)? With `line`, only inside a corridor
    `radius` either side of it; else anywhere in the box round the points. `closed`: (x0, x1, z0, z1) column boxes
    no step may enter (a zone the player's flags do not admit). Returns an evidence dict."""
    pts = list(starts) + list(goals) + list(line or [])
    x0, z0 = min(p[0] for p in pts) - margin, min(p[1] for p in pts) - margin
    x1, z1 = max(p[0] for p in pts) + margin, max(p[1] for p in pts) + margin
    G = np.asarray(inp.ground.box(x0, z0, x1, z1), dtype=np.int64)
    if G.shape != (z1 - z0 + 1, x1 - x0 + 1):
        # a point near or past the heightmap's edge: nothing there can be walked on this model
        return {"from": [list(s) for s in starts[:3]], "to_count": len(goals), "reached": False, "steps": None,
                "off_map": [x0, z0, x1, z1]}
    sea, bodies = inp.water
    dry = ~wet_mask(G, x0, z0, sea, bodies)
    if line:
        allowed = np.zeros(G.shape, dtype=bool)
        for x, z in line:
            allowed[max(0, z - z0 - radius):z - z0 + radius + 1, max(0, x - x0 - radius):x - x0 + radius + 1] = True
        for x, z in list(starts) + list(goals):
            allowed[max(0, z - z0 - 2):z - z0 + 3, max(0, x - x0 - 2):x - x0 + 3] = True
    else:
        allowed = np.ones(G.shape, dtype=bool)
    shut = 0
    for bx0, bx1, bz0, bz1 in closed:
        if bx1 < x0 or bx0 > x1 or bz1 < z0 or bz0 > z1:
            continue
        allowed[max(0, bz0 - z0):max(0, bz1 - z0 + 1), max(0, bx0 - x0):max(0, bx1 - x0 + 1)] = False
        shut += 1
    ok = allowed & dry
    seen = flood(G, ok, [(z - z0, x - x0) for x, z in starts])
    hits = [(int(seen[z - z0, x - x0]), (x, z)) for x, z in goals if seen[z - z0, x - x0] >= 0]
    ev = {"from": [list(s) for s in starts[:3]], "to_count": len(goals), "reached": bool(hits),
          "steps": min(hits)[0] if hits else None}
    if shut:
        ev["closed_zone_boxes"] = shut
    if not hits:
        ev["wet_starts"] = [list(s) for s in starts if not dry[s[1] - z0, s[0] - x0]][:3]
        ev["wet_goals"] = sum(1 for x, z in goals if not dry[z - z0, x - x0])
    if line:
        idx = [i for i, (x, z) in enumerate(line) if seen[z - z0, x - x0] >= 0]
        last = idx[-1] if idx else -1
        ev["line_points"] = len(line)
        ev["line_reached_to"] = last
        if not hits and 0 <= last < len(line) - 1:
            ev["stuck_after"] = list(line[last])
            ev["stuck_walked"] = round(walked_length(line[:last + 1]))
        prof = [int(G[z - z0, x - x0]) for x, z in line]
        ev["line_steep_steps"] = sum(1 for a, b in zip(prof, prof[1:]) if b - a > CLIMB or a - b > DROP)
        ev["line_wet_points"] = sum(1 for x, z in line if not dry[z - z0, x - x0])
    return ev


def walked_length(line):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(line, line[1:]))


def lot_ring(rect, ring=LOT_RING):
    """The columns just outside a lot rect [x0, z0, x1, z1]: reaching any of them is reaching the lot."""
    x0, z0, x1, z1 = rect
    out = []
    for x in range(x0 - ring, x1 + ring + 1):
        for z in range(z0 - ring, z1 + ring + 1):
            if not (x0 <= x <= x1 and z0 <= z <= z1):
                out.append((x, z))
    return out


def add_walk(stage, name, ev, what):
    v = PASS if ev["reached"] else FAIL
    msg = "%s: %s" % (what, ("reached in %d steps" % ev["steps"]) if ev["reached"] else "NOT reached")
    if not ev["reached"] and ev.get("stuck_after"):
        msg += ", stuck after (%d, %d), %d blocks along the line" % (ev["stuck_after"][0], ev["stuck_after"][1],
                                                                     ev["stuck_walked"])
    if ev.get("wet_starts"):
        msg += ", start in water %s" % ev["wet_starts"]
    if ev.get("off_map"):
        msg += ", the box %s runs off the heightmap" % ev["off_map"]
    if not ev["reached"] and ev.get("closed_zones"):
        msg += ", zones closed to this player's flags: %s" % ev["closed_zones"]
    stage.add(name, v, {"summary": msg, **ev}, coarse=True,
              not_covered="heightmap only: buildings, walls, doors, trees, fences, rivers, bridges, the Rift sculpt "
                          "and every placed block are invisible to this walk; zone knock boxes are not modelled")
    return v


# ------------------------------------------------------------------------------------------ the built packs

SPAWNER = re.compile(r"rctmod:trainer_spawner\{[^}]*TrainerIds:\[([^\]]*)\]")
SETBLOCK = re.compile(r"^\s*setblock (-?\d+) (-?\d+) (-?\d+) rctmod:trainer_spawner")
SEAT = re.compile(r'nbt=\{TrainerId:"([\w.-]+)"[^}]*\}\] positioned (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)')


def spawner_sweep(packs):
    """{trainer id: [(x, y, z, file)]} for every rctmod:trainer_spawner a text function under the packs sets. A sweep,
    not our list: a spawner set anywhere in any pack counts (a donor template's .nbt is NOT read)."""
    out = {}
    for f in sorted(Path(packs).rglob("*.mcfunction")):
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "trainer_spawner" not in text:
            continue
        for line in text.splitlines():
            m = SPAWNER.search(line)
            s = SETBLOCK.match(line)
            if not m:
                continue
            for tid in re.findall(r'"([\w.:-]+)"', m.group(1)):
                pos = (int(s.group(1)), int(s.group(2)), int(s.group(3))) if s else None
                out.setdefault(tid, []).append((pos, f.relative_to(packs).as_posix()))
    return out


def trainer_team(packs, tid):
    p = Path(packs) / "cobblers_trainers" / "data" / "rctmod" / "trainers" / ("%s.json" % tid)
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def forced_trainers(packs):
    """{trainer id: {"seat": (x, y, z), "distance": sight}} for every built trainer whose mob forces a battle on sight,
    seated where the built cycle function keeps it."""
    base = Path(packs) / "cobblers_trainers" / "data"
    seats = {}
    cyc = base / "cobblers" / "function" / "trainers" / "cycle.mcfunction"
    if cyc.is_file():
        for m in SEAT.finditer(cyc.read_text(encoding="utf-8")):
            seats.setdefault(m.group(1), (float(m.group(2)), float(m.group(3)), float(m.group(4))))
    out = {}
    for f in sorted((base / "rctmod" / "mobs" / "trainers").rglob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        out[f.stem] = {"forced": bool(d.get("forceBattleOnSight")), "sight": float(d.get("forceBattleMaxDistance") or 0),
                       "seat": seats.get(f.stem)}
    return out


def line_distance(line, x, z):
    a = np.asarray(line, dtype=float)
    d = np.hypot(a[:, 0] - x, a[:, 1] - z)
    i = int(d.argmin())
    return float(d[i]), i


@functools.lru_cache(maxsize=4)
def pool_entries(packs):
    """[(route number, species, top level, box centre (x, z) or None)] over the compiled route pools of cobblers_spawns
    (route_NN_* is route NN, victory_road is 9)."""
    d = Path(packs) / "cobblers_spawns" / "data" / "cobblers" / "spawn_pool_world" / "routes"
    out = []
    for p in sorted(d.glob("*.json")):
        m = re.match(r"route_(\d+)", p.stem)
        n = int(m.group(1)) if m else (9 if p.stem == "victory_road" else None)
        if n is None:
            continue
        for s in json.loads(p.read_text(encoding="utf-8")).get("spawns") or []:
            sp = (s.get("pokemon") or "").split()[0].lower()
            lv = re.findall(r"\d+", str(s.get("level") or ""))
            c = s.get("condition") or {}
            centre = ((c["minX"] + c["maxX"]) / 2.0, (c["minZ"] + c["maxZ"]) / 2.0) if "minX" in c else None
            if sp and lv:
                out.append((n, sp, int(lv[-1]), centre))
    return out


def route_pools(packs, upto, line=None, before=None):
    """{species: top level} a player can meet by then: every pool of routes 1..upto-1, and route `upto`'s own entries
    -- all of them, or with `line` and `before` only those whose box lies nearest the line at or before that point."""
    out = {}
    for n, sp, top, centre in pool_entries(packs):
        if n > upto:
            continue
        if n == upto and line is not None and before is not None and centre is not None:
            if line_distance(line, centre[0], centre[1])[1] > before:
                continue
        out[sp] = max(out.get(sp, 0), top)
    return out


def rct_caps(root):
    """(initialLevelCap, relativeLevelCap) from the RCT config the server runs (battle_sim's own reader)."""
    import battle_sim as B
    over = Path(root) / "modpack" / "config" / "rctmod-server.toml"
    base = Path(root) / "base-pack" / "cobbleverse" / "config" / "rctmod-server.toml"
    return B.level_caps(over if over.exists() else base)


# ------------------------------------------------------------------------------------------ the zones, as built

ADV_SEL = re.compile(r"advancements=\{([^}]*)\}")
RUN_FN = re.compile(r"\brun function ([\w.:/-]+)\s*$")
SCORE_TEST = re.compile(r"\bunless score @s (\w+) matches 1\.\.")


def function_text(packs, ref):
    """The text of built function `ns:path` in any pack under `packs`, or None."""
    ns, _, path = (ref or "").partition(":")
    if not ns or not path:
        return None
    for f in sorted(Path(packs).glob("*/data/%s/function/%s.mcfunction" % (ns, path))):
        return f.read_text(encoding="utf-8")
    return None


def _positions(obj, out):
    """Every location predicate's (x0, x1, y0, y1, z0, z1) under an advancement's criteria."""
    if isinstance(obj, dict):
        pos = obj.get("position")
        if isinstance(pos, dict) and all(isinstance(pos.get(a), dict) for a in ("x", "y", "z")):
            out.append(tuple(pos[a][k] for a in ("x", "y", "z") for k in ("min", "max")))
        for v in obj.values():
            _positions(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _positions(v, out)
    return out


def zone_checks(packs):
    """{zone: {"boxes": [(x0, x1, y0, y1, z0, z1)], "function", "turns_back", "objective", "admits": [frozenset]}}
    for every zone check a built cobblers_rift_zones advancement calls. A zone function nothing calls is not here: it
    never runs. `admits`: each advancement set that, all held, runs a function setting the zone's pass score on a line
    BEFORE the turn-back line -- a grant after it comes too late, the player is already teleported (the shape of
    CRITICAL_PATH_WALK_2 item 1)."""
    out = {}
    d = Path(packs) / "cobblers_rift_zones" / "data" / "cobblers" / "advancement" / "rift_zones"
    for f in sorted(d.glob("*_zone.json")):
        adv = json.loads(f.read_text(encoding="utf-8"))
        ref = (adv.get("rewards") or {}).get("function") or ""
        z = {"boxes": _positions(adv.get("criteria"), []), "function": ref, "turns_back": False, "objective": None,
             "admits": [], "built": False}
        out[f.stem[:-len("_zone")]] = z
        text = function_text(packs, ref)
        if text is None:
            continue
        z["built"] = True
        pending = []
        for line in text.splitlines():
            s = line.strip()
            m = RUN_FN.search(s)
            if not s or s.startswith("#") or not m:
                continue
            if m.group(1).endswith("/turn_back"):
                z["turns_back"] = True
                sc = SCORE_TEST.search(s)
                z["objective"] = sc.group(1) if sc else None
                break
            sel = ADV_SEL.search(s)
            if sel and s.startswith("execute if entity @s["):
                need = frozenset(k.split("=", 1)[0].strip() for k in sel.group(1).split(",")
                                 if k.strip().endswith("=true"))
                if need:
                    pending.append((need, m.group(1)))
        if z["objective"]:
            sets = re.compile(r"^\s*scoreboard players set @s %s [1-9]" % re.escape(z["objective"]), re.M)
            z["admits"] = [need for need, fn in pending if sets.search(function_text(packs, fn) or "")]
        z["knocks"] = []
    # the knock boxes: a built *_knock advancement's boxes, and the advancement sets that, through the functions it
    # calls, reach a function setting a zone's pass score (the zone is the one whose objective that is)
    by_obj = {z["objective"]: zid for zid, z in out.items() if z["objective"]}
    for f in sorted(d.glob("*_knock.json")):
        adv = json.loads(f.read_text(encoding="utf-8"))
        boxes = _positions(adv.get("criteria"), [])
        found = {}
        _knock_calls(packs, (adv.get("rewards") or {}).get("function") or "", frozenset(), by_obj, found, 0)
        for zid, admits in found.items():
            out[zid]["knocks"] += [(b, sorted(set(admits), key=sorted)) for b in boxes]
    return out


PLAIN_FN = re.compile(r"^function ([\w.:/-]+)\s*$")
SETS_SCORE = re.compile(r"^\s*scoreboard players set @s (\w+) [1-9]", re.M)


def _knock_calls(packs, ref, need, by_obj, found, depth):
    text = function_text(packs, ref)
    if text is None or depth > 4:
        return
    for o in SETS_SCORE.findall(text):
        if o in by_obj:
            found.setdefault(by_obj[o], []).append(need)
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = RUN_FN.search(s) or PLAIN_FN.match(s)
        if not m:
            continue
        sel = ADV_SEL.search(s) if s.startswith("execute if entity @s[") else None
        more = frozenset(k.split("=", 1)[0].strip() for k in sel.group(1).split(",")
                         if k.strip().endswith("=true")) if sel else frozenset()
        _knock_calls(packs, m.group(1), need | more, by_obj, found, depth + 1)


def zone_passable(z, held):
    """Whether a player holding the advancement ids `held` is let stay anywhere in zone z, without knocking."""
    return not z["turns_back"] or any(a <= set(held) for a in z["admits"])


def knock_admits(z, held):
    """The knock boxes of zone z where a player holding `held` is given the pass."""
    return [b for b, admits in z.get("knocks") or [] if any(a <= set(held) for a in admits)]


def box_distance(b, line):
    """The least column distance from a (x0, x1, y0, y1, z0, z1) box to any point of `line`."""
    a = np.asarray(line, dtype=float)
    dx = np.maximum(0, np.maximum(b[0] - a[:, 0], a[:, 0] - b[1]))
    dz = np.maximum(0, np.maximum(b[4] - a[:, 1], a[:, 1] - b[5]))
    return float(np.hypot(dx, dz).min())


def in_box(b, x, y, z):
    return b[0] <= x <= b[1] and (y is None or b[2] <= y <= b[3]) and b[4] <= z <= b[5]


def flag_advancement(packs, name):
    p = Path(packs) / "cobblers_progression" / "data" / "cobblers" / "advancement" / "flag" / ("%s.json" % name)
    return (json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None), p


def flag_trainer(packs, name):
    """(the first trainer id the built flag advancement `name`'s rctmod:defeat_count names, its path), or (None, path)."""
    d, p = flag_advancement(packs, name)
    for c in ((d or {}).get("criteria") or {}).values():
        if c.get("trigger") == "rctmod:defeat_count":
            ids = (c.get("conditions") or {}).get("trainer_ids") or []
            if ids:
                return ids[0], p
    return None, p


def flag_emitted(packs, fid):
    """(verdict, evidence) for whether anything built can give the advancement `fid` (ns:path): an advancement whose
    own trigger can fire, or an `advancement grant ... only fid` line in a built function that some built file calls
    (a compiled dialogue's run_command, another function, an advancement's reward)."""
    ns, _, path = fid.partition(":")
    advs = sorted(Path(packs).glob("*/data/%s/advancement/%s.json" % (ns, path)))
    if not advs:
        return FAIL, "no built advancement %s" % fid
    triggers = sorted({c.get("trigger") for c in (json.loads(advs[0].read_text(encoding="utf-8")).get("criteria")
                                                   or {}).values()})
    if triggers and triggers != ["minecraft:impossible"]:
        return PASS, "%s fires on its own trigger(s) %s" % (fid, triggers)
    grant = re.compile(r"^(?!\s*#).*\badvancement grant @s only %s\s*$" % re.escape(fid), re.M)
    granters = []
    for f in sorted(Path(packs).rglob("*.mcfunction")):
        try:
            if grant.search(f.read_text(encoding="utf-8")):
                rel = f.relative_to(packs).parts
                i = rel.index("function")
                granters.append("%s:%s" % (rel[2], "/".join(rel[i + 1:])[:-len(".mcfunction")]))
        except (ValueError, OSError, UnicodeDecodeError):
            continue
    if not granters:
        return FAIL, "%s is minecraft:impossible and no built function grants it" % fid
    callers = []
    for f in sorted(Path(packs).rglob("*")):
        if f.suffix not in (".json", ".mcfunction") or not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for g in granters:
            if re.search(r"function %s(?![\w/])" % re.escape(g), text):
                callers.append("%s -> %s" % (f.relative_to(packs).as_posix(), g))
    if not callers:
        return FAIL, "%s is granted by %s, which nothing built calls" % (fid, granters)
    return PASS, "%s granted by %s, called from %s" % (fid, granters, callers[:3])


PLACE = re.compile(r"^\s*place template (\S+) (-?\d+) (-?\d+) (-?\d+)(?: (\w+))?(?: (\w+))?", re.M)


def template_rect(x, z, size, rotation):
    """[x0, z0, x1, z1] a template of `size` [sx, sy, sz] covers when placed at corner (x, z): vanilla rotates about
    the corner, so a local (dx, dz) lands at (x - dz, z + dx) clockwise_90, (x - dx, z - dz) 180, (x + dz, z - dx)
    counterclockwise_90."""
    sx, sz = size[0] - 1, size[2] - 1
    if rotation == "clockwise_90":
        return [x - sz, z, x, z + sx]
    if rotation == "180":
        return [x - sx, z - sz, x, z]
    if rotation == "counterclockwise_90":
        return [x, z - sx, x + sz, z]
    return [x, z, x + sx, z + sz]


def placed_templates(packs, template):
    """[(x, y, z, rotation, mirror, function file)] for every `place template <template>` a built function runs."""
    out = []
    for f in sorted(Path(packs).rglob("*.mcfunction")):
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if template not in text:
            continue
        for m in PLACE.finditer(text):
            if m.group(1) == template:
                out.append((int(m.group(2)), int(m.group(3)), int(m.group(4)), m.group(5) or "none",
                            m.group(6) or "none", f.relative_to(packs).as_posix()))
    return out


# ------------------------------------------------------------------------------------------ the starters

def starter_entries(config):
    """[(species, level, aspect)] in the order the screen offers them."""
    out = []
    for cat in config.get("starters") or []:
        for e in cat.get("pokemon") or []:
            parts = e.split()
            props = dict(p.split("=", 1) for p in parts[1:] if "=" in p)
            out.append((parts[0].lower(), int(props.get("level", 5)), props.get("aspect")))
    return out


def forms_index(pack):
    """{(species, aspect): form} from the built species_additions of the forms pack."""
    out = {}
    for f in sorted(Path(pack).rglob("species_additions/*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        sp = d.get("target", "").split(":")[-1].lower()
        for form in d.get("forms") or []:
            for a in form.get("aspects") or []:
                out[(sp, a)] = form
    return out


def damaging(mlist, level, moves):
    import battle_sim as B
    out = []
    for e in mlist or []:
        m = re.match(r"^(\d+):(\w+)$", e)
        if not m or int(m.group(1)) > level:
            continue
        mv = moves.get(m.group(2))
        if mv and (mv["power"] > 0 or B.VARIABLE_NOMINAL.get(m.group(2), 0) > 0):
            out.append(m.group(2))
    return out


def starter_mon(inp, forms, species, aspect, level):
    """The starter as a battle_sim Mon at `level`, following its built form chain (level evolutions only).
    Returns (Mon, chain) or (None, reason)."""
    import battle_sim as B
    dex, moves, chart = inp.battle
    raw = inp.raw
    chain = ["%s[%s]" % (species, aspect)]
    cur, asp = species, aspect
    for _ in range(4):
        form = forms.get((cur, asp))
        if form is None:
            break
        nxt = None
        for ev in form.get("evolutions") or []:
            reqs = ev.get("requirements") or []
            lv = next((r.get("minLevel") for r in reqs if r.get("variant") == "level"), None)
            if ev.get("variant") == "level_up" and lv is not None and lv <= level and \
                    all(r.get("variant") in ("level", "time_range") for r in reqs):
                nxt = ev
                break
        if not nxt:
            break
        parts = nxt["result"].split()
        props = dict(p.split("=", 1) for p in parts[1:] if "=" in p)
        cur, asp = parts[0].lower(), props.get("aspect")
        chain.append("%s[%s]" % (cur, asp or "native"))
    base = dex.get(B.key(cur)) or raw.get(B.key(cur))
    if base is None:
        return None, "no species data for %s" % cur
    form = forms.get((cur, asp)) if asp else None
    k = B.key("cobblers starter %s %s" % (cur, asp)) if form else B.key(cur)
    sp = dict(base)
    if form:
        sp.update({"baseStats": form["baseStats"], "moves": form["moves"], "evolutions": []})
    else:
        sp["evolutions"] = []
    d2 = dict(dex)
    d2[k] = sp
    try:
        return B.Mon(d2, k, level, moves, chart), chain
    except B.SimError as e:
        return None, str(e)


# ------------------------------------------------------------------------------------------ the fights

class Fights:
    """The battle model, tools/battle_sim.py's, with a cache of ranked catchables per (pool depth, level)."""

    def __init__(self, inp):
        self.inp = inp
        self._ranked = {}

    def foes(self, team):
        import battle_sim as B
        dex, moves, chart = self.inp.battle
        return B.build_leader({"team": team}, dex, moves, chart, 15, False)

    def catchables(self, pool, level, team):
        """The TEAM_EXTRA species of `pool` that win the most one-on-ones against the team, at `level`."""
        import battle_sim as B
        dex, moves, chart = self.inp.battle
        key = (tuple(sorted(pool)), level, json.dumps(team, sort_keys=True))
        if key not in self._ranked:
            foes = self.foes(team)
            rows, seen, unresolved = [], set(), []
            for s in sorted(pool):
                try:
                    m = B.Mon(dex, s, level, moves, chart)
                except B.SimError:
                    unresolved.append(s)
                    continue
                if not m.moveset or m.name in seen:
                    continue
                seen.add(m.name)
                wins = sum(1 for f in foes if B.duel(m, f, moves, chart, species=dex)[0] is m)
                rows.append((-wins, m.name, s))
            rows.sort()
            self._ranked[key] = ([r[2] for r in rows[:TEAM_EXTRA]], unresolved)
        return self._ranked[key]

    def fight(self, starter, team, pool, level):
        """The starter (+ the best catchables of `pool`, a species collection, when given) against a built team."""
        import battle_sim as B
        dex, moves, chart = self.inp.battle
        picks, unresolved = self.catchables(pool, level, team) if pool else ([], [])
        out = {"level": level, "team": [starter.name] + picks, "unresolved_catchables": unresolved[:8]}
        for sw in (False, True):
            mine = [starter] + [B.Mon(dex, s, level, moves, chart) for s in picks]
            for m in mine:
                m.reset()
            won, faints, downed, left = B.run_gauntlet(mine, self.foes(team), moves, chart, species=dex, switching=sw)
            out["switching" if sw else "no_switch"] = {"won": won, "faints": faints, "foes_downed": downed}
        starter.reset()
        out["won"] = out["no_switch"]["won"] or out["switching"]["won"]
        return out


# ------------------------------------------------------------------------------------------ the stages

def stage_spawn_to_oak(inp):
    st = Stage("spawn_to_oak", "the world spawn to Professor Oak")
    town = inp.packs / "cobblers_towns" / "data" / "cobblers" / "function" / "towns" / "hometown.mcfunction"
    if "cobblers_towns" in inp.unbuilt:
        st.add("spawn_set", NM, "cobblers_towns is not built in this mode: %s" % inp.unbuilt["cobblers_towns"])
        return st
    spawn = None
    if town.is_file():
        m = re.search(r"^setworldspawn (-?\d+) (-?\d+) (-?\d+)", town.read_text(encoding="utf-8"), re.M)
        spawn = tuple(int(v) for v in m.groups()) if m else None
    if spawn is None:
        st.add("spawn_set", FAIL, "no `setworldspawn` in %s: the hometown function is not built or sets no spawn"
               % town.as_posix())
        return st
    st.add("spawn_set", PASS, "setworldspawn %d %d %d (cobblers_towns towns/hometown)" % spawn)
    seat = next((s for s in inp.data("npc_seats.json").get("seats") or [] if s.get("id") == "npc_main_pallet_oak"), None)
    if seat is None:
        st.add("oak_seated", FAIL, "data/npc_seats.json has no npc_main_pallet_oak seat")
        return st
    cls = inp.packs / "cobblers_dialogue" / "data" / "cobblers" / "npcs" / "npc_main_pallet_oak.json"
    st.add("oak_seated", PASS if cls.is_file() else FAIL,
           "seat (%d, %d, %d), class %s" % (tuple(seat["at"]) + ("compiled" if cls.is_file() else "NOT compiled",)))
    ox, _oy, oz = seat["at"]
    goals = [(ox + dx, oz + dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1)]
    add_walk(st, "walk_spawn_to_oak", walk(inp, [(spawn[0], spawn[2])], goals), "spawn to Oak's seat")
    return st


def run_oak_audit(inp):
    """tools/oak_starter_audit.py as a CLI over the packs: (exit code, stdout). Its verdict, nothing of its model."""
    r = subprocess.run([sys.executable, str(TOOLS / "oak_starter_audit.py"), "--packs", str(inp.packs)],
                       capture_output=True, text=True, timeout=240, cwd=str(inp.root))
    return r.returncode, r.stdout


def stage_starter(inp):
    st = Stage("starter", "Oak offers the starter; each of the five can fight")
    code, out = inp.oak(inp)
    last = (out.strip().splitlines() or ["(no output)"])[-1]
    probs = [l for l in out.splitlines() if l.startswith("PROBLEM")]
    st.add("oak_offers_screen", PASS if code == 0 else FAIL,
           {"summary": "tools/oak_starter_audit.py exit %d: %s" % (code, last), "problems": probs[:10]})
    cfg_path = inp.root / "modpack" / "config" / "cobblemon" / "starters.json"
    entries = starter_entries(json.loads(cfg_path.read_text(encoding="utf-8")))
    if not entries:
        st.add("config_offers", FAIL, "modpack/config/cobblemon/starters.json offers nothing")
        return st
    forms = forms_index(inp.packs / "cobblers_mythical_starters")
    _dex, moves, _chart = inp.battle
    for sp, lv, asp in entries:
        form = forms.get((sp, asp))
        vanilla = inp.raw.get(re.sub(r"[^a-z0-9]", "", sp))
        van_moves = damaging((vanilla or {}).get("moves"), lv, moves)
        if form is None:
            st.add("moves:%s" % sp, FAIL, "%s level=%d aspect=%s: no form with that aspect in the built "
                   "cobblers_mythical_starters pack, so the vanilla moveset applies: damaging at L%d %s"
                   % (sp, lv, asp, lv, van_moves or "NONE"))
            continue
        dmg = damaging(form.get("moves"), lv, moves)
        st.add("moves:%s" % sp, PASS if dmg else FAIL,
               "%s[%s] at L%d knows %s damaging move(s): %s (vanilla, without the form: %s)"
               % (sp, asp, lv, len(dmg), dmg, van_moves or "none"),
               not_covered="that Cobblemon applies the form (EXP-049 unrun)")
        if vanilla is not None and vanilla.get("implemented") is False:
            st.warnings.append("%s is implemented:false in the bare Cobblemon jar: it relies on an addon to be "
                               "offered and rendered (X6, not modelled)" % sp)
        if not van_moves:
            st.warnings.append("%s without the forms pack has no damaging move at L%d: a world without "
                               "cobblers_mythical_starters is a forced loss" % (sp, lv))
    return st


def gym_leader_id(packs, n):
    return flag_trainer(packs, "gym%d_cleared" % n)


def ace(team):
    return max(m["level"] for m in team["team"]) if team and team.get("team") else None


class Walker:
    """The whole walk: shared caches and the starters at each level."""

    def __init__(self, inp):
        self.inp = inp
        self.fights = Fights(inp)
        self.paths = inp.data("route_paths.json")["paths"]
        self.records = {}
        for p in sorted((inp.root / "data" / "gym_buildings").glob("*.json")):
            self.records[p.stem] = json.loads(p.read_text(encoding="utf-8"))
        self.init_cap, self.rel_cap = rct_caps(inp.root)
        self.entries = starter_entries(json.loads(
            (inp.root / "modpack" / "config" / "cobblemon" / "starters.json").read_text(encoding="utf-8")))
        self.forms = forms_index(inp.packs / "cobblers_mythical_starters")
        self._spawners = None
        self._forced = None
        self._zones = None

    def zones(self):
        if self._zones is None:
            self._zones = zone_checks(self.inp.packs)
        return self._zones

    def held_after(self, n):
        """The gym flags (advancement ids) a player holds after gym n: each one the built progression pack binds to a
        trainer's defeat. Whether the gym stage itself passed is that stage's verdict, not repeated here."""
        return {"cobblers:flag/gym%d_cleared" % k for k in range(1, n + 1) if gym_leader_id(self.inp.packs, k)[0]}

    def closed(self, held):
        """((x0, x1, z0, z1) column boxes, zone ids) of every enforced zone `held` opens neither on entry nor at a
        knock box (a knock that admits is assumed taken: the walks do not route through it)."""
        boxes, names = [], []
        for zid, z in sorted(self.zones().items()):
            if not zone_passable(z, held) and not knock_admits(z, held):
                names.append(zid)
                boxes += [(b[0], b[1], b[4], b[5]) for b in z["boxes"]]
        return boxes, names

    def walk_held(self, held, starts, goals, **kw):
        boxes, names = self.closed(held)
        ev = walk(self.inp, starts, goals, closed=boxes, **kw)
        if names:
            ev["closed_zones"] = names
        return ev

    def spawners(self):
        if self._spawners is None:
            self._spawners = spawner_sweep(self.inp.packs)
        return self._spawners

    def forced(self):
        if self._forced is None:
            self._forced = forced_trainers(self.inp.packs)
        return self._forced

    def route(self, n):
        return next(((k, v) for k, v in self.paths.items() if k.startswith("route_%02d_" % n)), (None, None))

    def cap_for(self, team):
        a = ace(team)
        return max(self.init_cap, (a or 0) + self.rel_cap)

    def starters(self, level):
        out = []
        for sp, _lv, asp in self.entries:
            m, chain = starter_mon(self.inp, self.forms, sp, asp, level)
            out.append((sp, m, chain))
        return out

    def battle_check(self, st, name, team, level, pool, tid):
        """Every starter (+ the best catchables of `pool`) against one built team; a FAIL names the starters that
        lose. The starter's own result alone is recorded beside it."""
        if not self.inp.battles:
            st.add(name, NM, "%s at L%d: battles not run (--no-battles)" % (tid, level))
            return
        try:
            self.fights.foes(team["team"])
        except Exception as e:      # battle_sim.SimError and a malformed team alike
            st.add(name, NM, "%s's team cannot be simulated: %s" % (tid, e))
            return
        rows, losers, unmodelled = {}, [], []
        for sp, mon, chain in self.starters(level):
            if mon is None:
                unmodelled.append("%s (%s)" % (sp, chain))
                continue
            f = self.fights.fight(mon, team["team"], pool, level)
            if pool:
                f["starter_alone_won"] = self.fights.fight(mon, team["team"], None, level)["won"]
            f["chain"] = chain
            rows[sp] = f
            if not f["won"]:
                losers.append(sp)
        foes = ["%s %d" % (m["species"], m["level"]) for m in team["team"]]
        who = "the starter alone" if not pool else "the starter + %d of %d catchables" % (TEAM_EXTRA, len(pool))
        ev = {"summary": "%s vs %s at L%d (%s): %s" % (tid, ", ".join(foes), level, who,
                                                        ("loses: %s" % losers) if losers else "every starter wins"),
              "by_starter": rows}
        if unmodelled:
            ev["unmodelled_starters"] = unmodelled
        v = FAIL if losers else (NM if unmodelled and not rows else PASS)
        st.add(name, v, ev, not_covered="battle_sim's limits: no items, no foe switching, IVs 15, level-up moves")

    def route_stage(self, n, prev_lot, prev_label):
        name, line = self.route(n)
        st = Stage("route_%d" % n, "%s to gym %d's town" % (prev_label, n))
        if not line:
            st.add("walked_line", FAIL, "data/route_paths.json has no route_%02d_* line" % n)
            return st
        line = [tuple(p) for p in line]
        st.add("walked_line", PASS, "%s: %d points, %d blocks walked" % (name, len(line), round(walked_length(line))))
        held = self.held_after(n - 1)       # the badges a player can hold on this route
        if prev_lot:
            add_walk(st, "walk_onto_route", self.walk_held(held, prev_lot, [line[0]]),
                     "%s onto %s" % (prev_label, name))
        add_walk(st, "walk_corridor", self.walk_held(held, [line[0]], [line[-1]], line=line),
                 "%s end to end inside a %d-block corridor" % (name, CORRIDOR))
        rect, src = self.gym_lot(n)
        if rect:
            ring = lot_ring(rect)
            add_walk(st, "walk_to_gym_lot", self.walk_held(held, [line[-1]], ring),
                     "%s's end to gym %d's lot (%s)" % (name, n, src))
            add_walk(st, "walk_back_from_gym_lot", self.walk_held(held, ring, [line[-1]]),
                     "gym %d's lot back to %s's end" % (n, name))
        else:
            st.add("walk_to_gym_lot", NM, "gym %d has neither a data/gym_buildings record nor a gym_interiors shell "
                   "box: its lot link is not modelled" % n)
        # the trainers on the line
        tid, _p = gym_leader_id(self.inp.packs, n)
        cap = self.cap_for(trainer_team(self.inp.packs, tid)) if tid else self.init_cap
        pools = route_pools(self.inp.packs, n)
        wild = max(pools.values()) if pools else None
        if wild is None:
            st.add("route_catchables", FAIL, "no compiled route pool route_01..route_%02d in cobblers_spawns" % n)
            return st
        st.add("route_catchables", PASS, "%d species on routes 1-%d, wilds up to L%d; cap %d, so a player can be L%d "
               "by the route's end" % (len(pools), n, wild, cap, min(cap, wild)))
        on_line = []
        for t, info in self.forced().items():
            if not info["seat"]:
                continue
            d, i = line_distance(line, info["seat"][0], info["seat"][2])
            if d <= max(info["sight"], 32.0) and self.route_of_seat(info["seat"]) == n:
                on_line.append((i, t, d, info))
        on_line.sort()
        must = [(i, t, d, info) for i, t, d, info in on_line if info["forced"] and d <= info["sight"]]
        st.add("must_pass_trainers", PASS, {"summary": "%d trainer(s) force a battle within sight of the line: %s"
                                            % (len(must), [t for _i, t, _d, _x in must]),
                                            "near_line": [[t, round(d, 1), info["forced"]] for _i, t, d, info in on_line]})
        def before(i):
            """(level, pool) for a fight at line point i: the wilds met by then, capped; route 1 fights alone."""
            p = route_pools(self.inp.packs, n, line, i)
            fresh = min(lv for _s, lv, _a in self.entries)
            return min(cap, max([fresh] + list(p.values()))), (None if n == 1 else p)

        for i, t, d, _info in must:
            team = trainer_team(self.inp.packs, t)
            if team is None:
                st.add("beat:%s" % t, FAIL, "%s forces a battle but has no built team (cobblers_trainers)" % t)
                continue
            grind, extra = before(i)
            self.battle_check(st, "beat:%s" % t, team, grind, extra, t)
            if n == 1:
                fresh = self.starters(min(sp_lv for _s, sp_lv, _a in self.entries))
                lose = []
                for sp, mon, _c in fresh:
                    if mon is not None and not self.fights.fight(mon, team["team"], None, mon.level)["won"]:
                        lose.append(sp)
                if lose:
                    st.warnings.append("%s (forced, %.0f blocks from the line) beats a FRESH L%d %s: the first fight "
                                       "of the game needs grinding first" % (t, d, fresh[0][1].level if fresh[0][1] else 5,
                                                                            lose))
        for i, t, d, info in on_line:
            if info["forced"] and d <= info["sight"]:
                continue
            team = trainer_team(self.inp.packs, t)
            if not team:
                continue
            grind, extra = before(i)
            sub = Stage("x", "x")
            self.battle_check(sub, "beat:%s" % t, team, grind, extra, t)
            if sub.checks and sub.checks[0]["verdict"] == FAIL:
                st.warnings.append("optional trainer %s (%.0f off the line): %s" % (t, d, sub.checks[0]["evidence"]["summary"]))
        return st

    def gym_lot(self, n):
        """([x0, z0, x1, z1], source) of gym n's lot: our building's lot rect, else the donor shell's box that
        data/gym_interiors.json expects (gym 2, Misty's), else (None, None)."""
        rec = self.records.get("gym%d" % n)
        if rec:
            return list(rec["site"]["lot_rect"]), "data/gym_buildings lot_rect"
        for g in self.inp.data("gym_interiors.json").get("gyms") or []:
            b = (g.get("shell") or {}).get("expect_box")
            if g.get("id") == "gym%d" % n and b:
                return [b[0], b[2], b[3], b[5]], "data/gym_interiors.json shell expect_box"
        return None, None

    def route_of_seat(self, seat):
        best, bn = None, None
        for k, v in self.paths.items():
            m = re.match(r"route_(\d+)_", k)
            if not m:
                continue
            d, _i = line_distance(v, seat[0], seat[2])
            if best is None or d < best:
                best, bn = d, int(m.group(1))
        return bn

    def gym_stage(self, n):
        st = Stage("gym_%d" % n, "gym %d" % n)
        tid, adv = gym_leader_id(self.inp.packs, n)
        if not tid:
            st.add("badge_flag", FAIL, "no built rctmod:defeat_count advancement at %s" % adv.name)
            return st
        team = trainer_team(self.inp.packs, tid)
        if not team:
            st.add("leader_team", FAIL, "%s has no built team in cobblers_trainers: upstream's would fight" % tid)
            return st
        cap = self.cap_for(team)
        st.add("leader_team", PASS, "%s: %s" % (tid, ", ".join("%s %d" % (m["species"], m["level"]) for m in team["team"])))
        # spawned
        sp = self.spawners().get(tid)
        gid = "gym%d" % n
        if sp:
            st.add("leader_spawner", PASS, "%s spawner at %s (%s)" % (tid, sp[0][0], sp[0][1]))
        elif "cobblers_gym_buildings" in self.inp.unbuilt and gid in self.records:
            st.add("leader_spawner", NM, "cobblers_gym_buildings is not built in this mode: %s"
                   % self.inp.unbuilt["cobblers_gym_buildings"])
        elif "gym%d" % n not in self.records:
            st.add("leader_spawner", NM, "%s's spawner is not in any text function: a donor template's .nbt is not read"
                   % tid)
        else:
            st.add("leader_spawner", FAIL, "no rctmod:trainer_spawner for %s in any built function" % tid)
        # the hall
        if gid in self.records and "cobblers_gym_buildings" in self.inp.unbuilt:
            st.add("hall_walk", NM, "cobblers_gym_buildings is not built in this mode: %s"
                   % self.inp.unbuilt["cobblers_gym_buildings"])
        elif gid in self.records:
            audit, built = self.inp.gym_audit()
            if not built.get(gid):
                st.add("hall_walk", FAIL, "%s's function is not built (cobblers_gym_buildings)" % gid)
            else:
                items = audit.get(gid) or []
                block = [t for c, t in items if c in BLOCKING]
                st.add("hall_walk", FAIL if block else PASS,
                       {"summary": ("%d blocking problem(s): %s" % (len(block), block[0])) if block else
                        "the leader's spawner is reachable on foot (tools/gym_buildings_independent.py's model)",
                        "blocking": block},
                       not_covered="the audit's movement model of vanilla, not a walk in game")
                st.warnings += ["gym audit: %s" % t for c, t in items if c not in BLOCKING]
        else:
            st.add("hall_walk", NM, "%s is a donor gym: no movement model reads its template" % gid)
        # the cap admits the fight
        lowest = min(lv for _s, lv, _a in self.entries)
        st.add("cap_admits", PASS if cap >= lowest and cap >= (ace(team) or 0) - self.rel_cap else FAIL,
               "cap %d (initialLevelCap %d, relativeLevelCap %d, %s's ace %d)" % (cap, self.init_cap, self.rel_cap, tid,
                                                                                ace(team)),
               not_covered="rctmod's series order (upstream) and its refusal over the cap are relayed, not modelled")
        self.battle_check(st, "beat:%s" % tid, team, cap, route_pools(self.inp.packs, n), tid)
        self.reach_check(st, "cap_reachable", team, cap, route_pools(self.inp.packs, n), tid)
        # the badge
        self.badge_check(st, n, tid, adv)
        # the cap advances
        if n < GYM_COUNT:
            nid, _ = gym_leader_id(self.inp.packs, n + 1)
            nteam = trainer_team(self.inp.packs, nid) if nid else None
            nxt = self.cap_for(nteam) if nteam else None
            st.add("cap_advances", PASS if nxt and nxt > cap else FAIL,
                   "cap %s after the badge (%s's ace + relativeLevelCap), from %d" % (nxt, nid, cap),
                   not_covered="that rctmod moves the cap on this win: its series data is upstream, the rule is relayed "
                               "from docs/mechanics/LEAGUE_LEVEL_CAP.md")
        return st

    def reach_check(self, st, name, team, cap, pool, tid):
        """Is the level the fight above assumed reachable with what spawns before it? The cap fight assumes a team AT
        the cap. Fought again at the top wild level met by then: beaten there, the cap need not be reached (PASS);
        beaten only at the cap, the levels between come from XP on wilds below them, which is not modelled; no
        compiled wild pool at all leaves nothing to level on (FAIL)."""
        if not pool:
            st.add(name, FAIL, "no compiled wild pool before %s: nothing to catch or level on" % tid)
            return
        top = max(pool.values())
        if top >= cap:
            st.add(name, PASS, "wilds up to L%d before %s reach the cap L%d" % (top, tid, cap))
            return
        sub = Stage("x", "x")
        self.battle_check(sub, name, team, top, pool, tid)
        c = sub.checks[0]
        if c["verdict"] == PASS:
            st.add(name, PASS, {"summary": "%s is beaten at L%d, the top wild level met before him, so the cap L%d "
                                "need not be reached" % (tid, top, cap), "at_wild_top": c["evidence"]},
                   not_covered=c["not_covered"])
        elif c["verdict"] == FAIL:
            st.add(name, NM, {"summary": "%s needs levels the wilds do not reach: they stop at L%d, the cap is L%d; "
                              "levelling past them on XP is not modelled (%s)" % (tid, top, cap,
                                                                                 c["evidence"]["summary"]),
                              "at_wild_top": c["evidence"]})
        else:
            st.add(name, NM, c["evidence"])

    def badge_check(self, st, n, tid, adv):
        d = json.loads(adv.read_text(encoding="utf-8"))
        fn = ((d.get("rewards") or {}).get("function") or "")
        ns, _, path = fn.partition(":")
        f = self.inp.packs / "cobblers_progression" / "data" / ns / "function" / (path + ".mcfunction") if fn else None
        if not f or not f.is_file():
            st.add("badge_wired", FAIL, "gym%d_cleared rewards no built function (%r)" % (n, fn))
            return
        text = f.read_text(encoding="utf-8")
        # a commented-out line gives nothing (found by mutating progression_pack.py: the first version matched it)
        m = re.search(r"^(?!\s*#).*\bloot give @s loot (\w+):([\w/]+)", text, re.M)
        if not m:
            st.add("badge_wired", FAIL, "%s gives no loot" % fn)
            return
        lt = self.inp.packs / "cobblers_progression" / "data" / m.group(1) / "loot_table" / (m.group(2) + ".json")
        items = re.findall(r'"name":\s*"([\w:]+)"', lt.read_text(encoding="utf-8")) if lt.is_file() else []
        badge = [i for i in items if i.endswith("_badge")]
        st.add("badge_wired", PASS if badge else FAIL,
               "beating %s -> advancement gym%d_cleared -> %s -> %s:%s -> %s" % (tid, n, fn, m.group(1), m.group(2),
                                                                                 badge or "NO badge item"),
               not_covered="that rctmod:defeat_count fires (EXP-027 proved gym 1 once)")

    def fight_each(self, st, ids, upto):
        """Each trainer in `ids` at its cap with the catchables of routes 1..upto, and its cap_reachable."""
        pool = route_pools(self.inp.packs, upto)
        for tid in ids:
            team = trainer_team(self.inp.packs, tid)
            if not team:
                st.add("beat:%s" % tid, FAIL, "%s has no built team (cobblers_trainers)" % tid)
                continue
            cap = self.cap_for(team)
            self.battle_check(st, "beat:%s" % tid, team, cap, pool, tid)
            self.reach_check(st, "cap_reachable:%s" % tid, team, cap, pool, tid)

    def knocked(self, zn, held, path):
        """The first knock box of zone zn admitting `held` that lies within CORRIDOR of the routed `path`, or None."""
        for b in knock_admits(zn, held):
            if path and box_distance(b, path) <= CORRIDOR:
                return b
        return None

    def zones_admit(self, st, name, held, x, y, z, what, path=None):
        """One check: every enforced zone containing (x, y, z) (y None: any height) admits `held` on entry, or at a
        knock box on the routed `path` (within the corridor), where the player is given the pass on the way in."""
        inside = [(zid, zn) for zid, zn in sorted(self.zones().items())
                  if any(in_box(b, x, y, z) for b in zn["boxes"])]
        shut = [zid for zid, zn in inside if not zone_passable(zn, held) and not self.knocked(zn, held, path)]
        if shut:
            needs = {zid: [sorted(a) for a in self.zones()[zid]["admits"]] or "nothing admits on entry: only its knock "
                     "box sets the pass, and none admitting these flags lies within %d blocks of the routed path, so "
                     "a player arriving this way is turned back" % CORRIDOR for zid in shut}
            st.add(name, FAIL, {"summary": "%s at (%s, %s, %s) stands in %s, which turn(s) back a player holding %d "
                                "flag(s): %s" % (what, x, y, z, shut, len(held), needs), "held": sorted(held)},
                   not_covered="the zone check as the built functions read; that the server runs it is not modelled")
        else:
            st.add(name, PASS, "%s at (%s, %s, %s): %s" % (what, x, y, z, ("in %s, each admitting the flags held"
                                                                           % [i for i, _ in inside]) if inside else
                                                           "in no enforced zone"))

    def crisis_flag(self, st):
        """The flag past the caves: emitted, and the chain to it named as not modelled. True if emitted."""
        v, ev = flag_emitted(self.inp.packs, CRISIS_FLAG)
        if v == FAIL and "cobblers_dialogue" in self.inp.unbuilt:
            v, ev = NM, "%s (cobblers_dialogue not built in this mode)" % ev
        st.add("flag_emitted:rift_crisis_resolved", v, ev,
               not_covered="that the dialogue's conditions are met: the conversations before it are not walked")
        st.add("story_chain", NM, "the conversations that lead to %s (data/quests.json main_worldshift_reveal, in "
               "strict order: CRITICAL_PATH_WALK_2 item 2) -- their conditions, actors and seats are not walked" %
               CRISIS_FLAG)
        return v == PASS

    def vr_stage(self):
        st = Stage("victory_road", "Giovanni's town through Victory Road")
        held = self.held_after(GYM_COUNT)
        line = self.paths.get("victory_road")
        if not line:
            st.add("walked_line", FAIL, "data/route_paths.json has no victory_road line")
            return st
        line = [tuple(p) for p in line]
        st.add("walked_line", PASS, "victory_road: %d points, %d blocks walked" % (len(line),
                                                                                   round(walked_length(line))))
        self.gate_check(st, line, held)
        rect, _src = self.gym_lot(GYM_COUNT)
        if rect:
            add_walk(st, "walk_onto_line", self.walk_held(held, lot_ring(rect), [line[0]]),
                     "gym %d's lot onto victory_road" % GYM_COUNT)
        add_walk(st, "walk_corridor", self.walk_held(held, [line[0]], [line[-1]], line=line),
                 "victory_road end to end inside a %d-block corridor" % CORRIDOR)
        st.add("walk_caves", NM, "Victory Road's caves (data/vr_caves.json) are a braided cave network under the "
               "heightmap: no walk here models them, nor whether the surface skips them (CRITICAL_PATH_WALK_2 item 3)")
        crisis = self.crisis_flag(st)
        caves_held = held | ({CRISIS_FLAG} if crisis else set())
        self.vr_stands(st, caves_held)
        forced = self.forced()
        vr = sorted(t for t, i in forced.items() if t.startswith("route_09_") and i["forced"])
        authored = {s["id"] for s in self.inp.data("vr_trainers.json").get("trainers") or []}
        if set(vr) - authored:
            st.warnings.append("built forced route_09 trainer(s) with no stand in data/vr_trainers.json: %s"
                               % sorted(set(vr) - authored))
        self.fight_each(st, vr, 9)
        return st

    def gate_check(self, st, line, held):
        """gate_opens: every enforced zone the line crosses admits `held` -- the badges that open this leg."""
        crossed = {}
        for x, z in line:
            for zid, zn in self.zones().items():
                if zid not in crossed and any(in_box(b, x, None, z) for b in zn["boxes"]):
                    crossed[zid] = (x, z)
        shut = {zid: p for zid, p in crossed.items() if not zone_passable(self.zones()[zid], held)
                and not self.knocked(self.zones()[zid], held, line)}
        st.add("gate_opens", FAIL if shut else PASS,
               {"summary": ("the line enters %s, which the %d gym flag(s) built do not admit (each needs one of %s)"
                            % (sorted(shut), len(held), {z: [sorted(a) for a in self.zones()[z]["admits"]]
                                                          for z in shut})) if shut else
                           "the line crosses %s; the %d gym flag(s) the progression pack binds admit each"
                           % (sorted(crossed) or "no enforced zone", len(held)), "crossed": crossed,
                "held": sorted(held)})

    def vr_stands(self, st, held):
        """Each authored stand (data/vr_trainers.json): seated by the built cycle at its seat, forcing a battle where
        the data says it makes eye contact, and admitted by every enforced zone it stands in -- on entry, or at a
        knock box on the routed path (data/route_paths.json victory_road, the surface line to the caves' mouth;
        the caves themselves pass no knock box)."""
        path = [tuple(p) for p in self.paths.get("victory_road") or []]
        if "cobblers_trainers" in self.inp.unbuilt:
            st.add("seated", NM, "cobblers_trainers is not built in this mode: %s" % self.inp.unbuilt["cobblers_trainers"])
            return
        forced = self.forced()
        for s in self.inp.data("vr_trainers.json").get("trainers") or []:
            tid, (sx, sy, sz) = s["id"], s["seat"]
            info = forced.get(tid)
            seat = info and info["seat"]
            if not seat:
                st.add("seated:%s" % tid, FAIL, "%s: no built mob or no seat in the built cycle function "
                       "(cobblers_trainers trainers/cycle)" % tid)
            else:
                off = max(abs(seat[0] - (sx + 0.5)), abs(seat[1] - sy), abs(seat[2] - (sz + 0.5)))
                bad = off > 1.0 or (s.get("eye_contact") and not info["forced"])
                st.add("seated:%s" % tid, FAIL if bad else PASS,
                       "%s seated at (%s, %s, %s), %.1f from its authored stand (%d, %d, %d); forces a battle: %s "
                       "(data says eye contact: %s)" % (tid, seat[0], seat[1], seat[2], off, sx, sy, sz,
                                                        info["forced"], s.get("eye_contact")),
                       not_covered="that rctmod spawns and holds the trainer there")
            self.zones_admit(st, "zone_admits:%s" % tid, held, sx, sy, sz, tid, path=path)

    def league_rect(self, st):
        """The League's footprint [x0, z0, x1, z1] from the built `place template` and the template's size."""
        if "cobblers_donor" in self.inp.unbuilt:
            st.add("league_placed", NM, "cobblers_donor is not built in this mode: %s" % self.inp.unbuilt["cobblers_donor"])
            return None
        placed = placed_templates(self.inp.packs, LEAGUE_TEMPLATE)
        if not placed:
            st.add("league_placed", FAIL, "no built function places %s" % LEAGUE_TEMPLATE)
            return None
        recs = [p for p in self.inp.data("placements.json").get("placements") or []
                if p.get("pack_template") == LEAGUE_TEMPLATE]
        sizes = {tuple(p["size"]) for p in recs if p.get("size")}
        x, y, z, rot, mirror, f = placed[0]
        if len(sizes) != 1 or mirror != "none":
            st.add("league_placed", NM, "%s placed at (%d, %d, %d) %s by %s, but its size is %s and mirror %s: the "
                   "footprint is not modelled" % (LEAGUE_TEMPLATE, x, y, z, rot, f, sorted(sizes) or "unknown", mirror))
            return None
        rect = template_rect(x, z, list(next(iter(sizes))), rot)
        others = sorted({(p[0], p[2], p[3]) for p in placed[1:]} - {(x, z, rot)})
        # the design the emitted command must carry out: data/placements.json's position and rotation
        want = sorted({(r["position"]["x"], r["position"]["y"], r["position"]["z"], r.get("rotation", "none"))
                       for r in recs if r.get("position")})
        off = [w for w in want if w != (x, y, z, rot)]
        st.add("league_placed", FAIL if others or off else PASS,
               "%s placed at (%d, %d, %d) %s by %s: footprint x%d-%d z%d-%d%s%s" % (
                   LEAGUE_TEMPLATE, x, y, z, rot, f, rect[0], rect[2], rect[1], rect[3],
                   (", and ELSEWHERE too: %s" % others) if others else "",
                   ("; data/placements.json says %s" % off) if off else ""),
               not_covered="that the template places; its rooms, doors and elevator")
        return rect

    def league_stage(self):
        st = Stage("league", "the Elite Four and the Champion")
        held = self.held_after(GYM_COUNT)
        if flag_emitted(self.inp.packs, CRISIS_FLAG)[0] == PASS:
            held = held | {CRISIS_FLAG}
        rect = self.league_rect(st)
        if rect:
            over =sorted({zid for zid, zn in self.zones().items()
                           for b in zn["boxes"] if b[0] <= rect[2] and b[1] >= rect[0] and b[4] <= rect[3]
                           and b[5] >= rect[1]})
            # the routed path: Victory Road's line, then straight on from its end to the footprint's centre
            line = [tuple(p) for p in self.paths.get("victory_road") or []]
            if line:
                (ax, az), (bx, bz) = line[-1], ((rect[0] + rect[2]) / 2.0, (rect[1] + rect[3]) / 2.0)
                n = int(max(abs(bx - ax), abs(bz - az))) or 1
                line = line + [(ax + (bx - ax) * i / n, az + (bz - az) * i / n) for i in range(1, n + 1)]
            shut = [zid for zid in over if not zone_passable(self.zones()[zid], held)
                    and not self.knocked(self.zones()[zid], held, line)]
            st.add("zones_over_league", FAIL if shut else PASS,
                   "the footprint lies in enforced zone(s) %s; %s" % (over or "none", (
                       "%s turn(s) back a player holding %s" % (shut, sorted(held))) if shut else
                       "each admits the flags held (%d)" % len(held)))
            spec = self.inp.data("rift_zones.json").get("zones") or {}
            for zid, zd in sorted(spec.items()):
                if zid in self.zones() or str(zd.get("status", "")).startswith("SUPERSEDED"):
                    continue
                if any(b[0] <= rect[2] and b[2] >= rect[0] and b[1] <= rect[3] and b[3] >= rect[1]
                       for b in zd.get("boxes") or []):
                    st.warnings.append("data/rift_zones.json zone %s covers the League's footprint but has no built "
                                       "zone advancement, so it is not enforced today; the day it is, the League "
                                       "sits behind its pass (CRITICAL_PATH_WALK_2 item 4)" % zid)
            line = self.paths.get("victory_road")
            if line:
                add_walk(st, "walk_to_league", self.walk_held(held, [tuple(line[-1])], lot_ring(rect)),
                         "victory_road's end to the League's footprint")
        st.add("league_spawners", NM, "the five trainers' spawners are inside the %s template (upstream .nbt): "
               "not read" % LEAGUE_TEMPLATE)
        st.add("elite_four_order", NM, "the Elite Four's order and the elevator to the Champion (rctmod's series and "
               "cobbleverse:trainer/kanto/defeat_elite_lance, upstream; CRITICAL_PATH_WALK_2 item 5): not read")
        self.fight_each(st, LEAGUE, 9)
        tid, adv = flag_trainer(self.inp.packs, CHAMPION_FLAG)
        if not tid:
            st.add("champion_flag", FAIL, "no built rctmod:defeat_count advancement at %s" % adv.name)
        else:
            fn = (((flag_advancement(self.inp.packs, CHAMPION_FLAG)[0] or {}).get("rewards") or {}).get("function")
                  or "")
            ok = tid == LEAGUE[-1] and function_text(self.inp.packs, fn) is not None
            st.add("champion_flag", PASS if ok else FAIL,
                   "%s is set by beating %s (the Champion here is %s) and rewards %s (%s)" % (
                       CHAMPION_FLAG, tid, LEAGUE[-1], fn or "nothing", "built" if function_text(
                           self.inp.packs, fn) is not None else "NOT built"),
                   not_covered="that rctmod:defeat_count fires for the Champion")
        return st


def run(inp, only=None):
    """[Stage] in walking order. `only`: stage ids to run (the rest are skipped, and the report says so)."""
    w = Walker(inp)
    stages = []

    def want(sid):
        return not only or sid in only

    if want("spawn_to_oak"):
        stages.append(stage_spawn_to_oak(inp))
    if want("starter"):
        stages.append(stage_starter(inp))
    seat = next((s for s in inp.data("npc_seats.json").get("seats") or [] if s.get("id") == "npc_main_pallet_oak"), None)
    prev = [(seat["at"][0], seat["at"][2])] if seat else None
    label = "Oak's lab"
    for n in range(1, GYM_COUNT + 1):
        if want("route_%d" % n):
            stages.append(w.route_stage(n, prev, label))
        if want("gym_%d" % n):
            stages.append(w.gym_stage(n))
        rect, _src = w.gym_lot(n)
        prev = lot_ring(rect) if rect else None
        label = "gym %d's lot" % n
    if want("victory_road"):
        stages.append(w.vr_stage())
    if want("league"):
        stages.append(w.league_stage())
    if want("multiplayer"):
        st = Stage("multiplayer", "a second player on the same path")
        st.add("second_player", NM, "a second player's flags, reveal cursors and trainer hold-offs "
               "(CRITICAL_PATH_WALK_1 item 3): the walk is one player's")
        stages.append(st)
    return stages


def donor_pack(out):
    """place_donor.py's own `function` loop into `out`, minus the records that need the server's templates
    (clear_loot, jigsaws): without --server-dir it refuses the whole pack for those, and the League is not one."""
    sys.path.insert(0, str(TOOLS))
    import place_donor as P
    subs = json.loads((ROOT / "data" / "spawn_block_policy.json").read_text(encoding="utf-8"))["substitutions"]
    for rec in P.records(json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))):
        if rec.get("clear_loot") or rec.get("jigsaws"):
            continue
        pos = rec["position"]
        extra = P.remove_item_commands((pos["x"], pos["y"], pos["z"]), rec.get("rotation"), rec.get("remove_items"))
        for name, lines in P.functions(rec, subs, None, extra).items():
            f = Path(out) / "data" / P.NS / "function" / "structures" / ("%s.mcfunction" % name)
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


def build_from_data(dest, source_root=None):
    """Generate into `dest` every pack the walk reads that committed data can build, each by its own generator.
    Returns {pack: why it was not built} for the rest. Never writes under build/."""
    import contextlib
    import io
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(TOOLS))
    unbuilt = {"cobblers_towns": "tools/place_town.py needs kits/ (gitignored) and derived/routes/critical_legs.json"}
    quiet = io.StringIO()

    def step(pack, fn):
        try:
            with contextlib.redirect_stdout(quiet), contextlib.redirect_stderr(quiet):
                rc = fn()
            if rc:
                unbuilt[pack] = "its generator exited %s" % rc
        except (Exception, SystemExit) as e:        # one generator's failure must not hide the others' packs
            unbuilt[pack] = "its generator raised %s: %s" % (type(e).__name__, str(e)[:200])

    import progression_pack
    import route_trainers
    import compile_spawns
    import compile_dialogue
    import mythical_starters
    step("cobblers_progression", lambda: progression_pack.main(["--out", str(dest / "cobblers_progression")]))
    step("cobblers_trainers", lambda: route_trainers.main(["--out", str(dest / "cobblers_trainers")]))
    step("cobblers_spawns", lambda: compile_spawns.main(["--out", str(dest / "cobblers_spawns")]))
    step("cobblers_dialogue", lambda: compile_dialogue.main(["--all", "--out", str(dest / "cobblers_dialogue")]))

    def starters():
        doc = json.loads(mythical_starters.DATA.read_text(encoding="utf-8"))
        problems = mythical_starters.check(doc)
        if problems:
            return "%d problem(s)" % len(problems)
        for rel, text in mythical_starters.files(doc).items():
            p = dest / "cobblers_mythical_starters" / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8", newline="\n")
        return 0
    step("cobblers_mythical_starters", starters)

    def zones():
        import rift_zones
        from unittest import mock
        with mock.patch.object(rift_zones, "PACKS", dest):
            return rift_zones.cmd_build(argparse.Namespace(source_root=source_root))
    step("cobblers_rift_zones", zones)

    def gyms():
        import gym_buildings
        from unittest import mock
        pack = dest / "cobblers_gym_buildings"
        with mock.patch.object(gym_buildings, "PACK", pack), \
                mock.patch.object(gym_buildings, "FUNCS", pack / "data" / "cobblers" / "function" / "gym_buildings"):
            return gym_buildings.main(["build"] + (["--source-root", source_root] if source_root else []))
    step("cobblers_gym_buildings", gyms)

    step("cobblers_donor", lambda: donor_pack(dest / "cobblers_donor"))
    for p in REQUIRED_PACKS:
        if p not in unbuilt and not (dest / p).is_dir():
            unbuilt[p] = "its generator wrote nothing"
    return unbuilt


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--packs", default=str(PACKS))
    ap.add_argument("--source-root", default=None)
    ap.add_argument("--only", action="append", default=None, help="one stage id (repeatable), e.g. gym_1")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--from-data", default=None, metavar="DIR",
                    help="build what committed data can build into DIR (never build/) and walk that")
    ap.add_argument("--no-battles", action="store_true", help="skip the fights; they report NOT_MODELLED")
    a = ap.parse_args(argv)
    sys.path.insert(0, str(TOOLS))
    unbuilt = {}
    if a.from_data:
        unbuilt = build_from_data(a.from_data, a.source_root)
        a.packs = a.from_data
        for p, why in sorted(unbuilt.items()):
            print("UNBUILT      %s: %s" % (p, why))
    inp = Inputs(packs=a.packs, source_root=a.source_root, battles=not a.no_battles, unbuilt=unbuilt)
    stages = run(inp, set(a.only) if a.only else None)
    failed, known, fixed = triage(stages)
    for s in stages:
        print("%-12s %-13s %s" % (s.verdict, s.id, s.summary()))
    for k in known:
        print("KNOWN        %s %s -- %s" % (k[0], k[1], KNOWN[k]))
    for k in fixed:
        print("FIXED?       %s %s no longer fails: remove it from KNOWN in tools/new_player_walk.py" % k)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    mode = "data" if a.from_data else "built"
    out.write_text(json.dumps({"schema": "cobblers.new-player-walk/1", "partial": bool(a.only),
                               "only": sorted(a.only) if a.only else None, "mode": mode,
                               "packs": Path(a.packs).as_posix(), "unbuilt": unbuilt, "battles": not a.no_battles,
                               "stages": [s.as_dict() for s in stages]}, indent=1, default=str), encoding="utf-8")
    bad = failed or fixed
    print("new_player_walk: %s -- %d stage(s): %d PASS, %d FAIL (%d only on KNOWN checks), %d NOT_MODELLED%s%s%s; "
          "detail in %s" % (
              "FAIL" if bad else "ok", len(stages), sum(s.verdict == PASS for s in stages),
              sum(s.verdict == FAIL for s in stages), sum(s.verdict == FAIL for s in stages) - len(failed),
              sum(s.verdict == NM for s in stages),
              (" (PARTIAL: --only %s)" % ",".join(sorted(a.only))) if a.only else "",
              (" (DATA MODE: %d pack(s) unbuilt)" % len(unbuilt)) if a.from_data else "",
              " (NO BATTLES)" if a.no_battles else "", out.as_posix()))
    return 1 if bad else 0


def triage(stages):
    """(stage ids failing on a check KNOWN does not list, KNOWN keys that failed, KNOWN keys that ran and passed)."""
    failed, known, fixed = [], [], []
    for s in stages:
        new = False
        for c in s.checks:
            k = (s.id, c["check"])
            if c["verdict"] == FAIL:
                if k in KNOWN:
                    c["known"] = KNOWN[k]
                    known.append(k)
                else:
                    new = True
            elif k in KNOWN and c["verdict"] == PASS:      # NOT_MODELLED (e.g. --no-battles) is not a fix
                fixed.append(k)
        if new:
            failed.append(s.id)
    return failed, known, fixed


if __name__ == "__main__":
    sys.exit(main())

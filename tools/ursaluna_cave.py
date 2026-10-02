#!/usr/bin/env python
"""The Ursaluna's den west of Highwire, from data/ursaluna_cave.json: the cave, the sleeping bear, its keeper and its wake.

The owner, 2026-10-02: "make an ursuluna cave at 1504 164 1414, dig a solid size caev for a large ursuluna, have
teddiursa spawn on the outskirt and have an npc one players can talk to". Four parts, each on a pattern the
repository already uses, so nothing here is new machinery:

  the cave      carved by this pack's cave/carve function. The legendary chambers' order (tools/legendaries.py):
                a stone shell filled SOLID first, reaching `margin` blocks beyond every void block, then the void
                cut out of it, so "at least margin blocks of rock round every void" holds by construction. Unlike a
                legendary chamber the cave is not a box: a level half-elliptical passage runs from the mouth on a
                diagonal axis into a half-ellipsoid hall, voxelised from the record and written as one `fill` per
                run of blocks along z. The shell never writes the top `keep_natural_top` blocks of a column, so the
                hill's grass is its own and its surface is never raised.
  the bear      a Pokemon entity, summoned over RCON by the re-application (placement_steps below), and after that
                by this pack's own keeper through a macro line when it returns (a plain `spawnpokemonat` line parsed
                at server start spawns nothing, EXP-046). This pack dresses it (the sleeping Celebi's flags,
                EXP-023), keeps it while it sleeps, WAKES it when a player comes within wake.radius (the den's boss
                fight), brings it back after it is beaten, and lets only a late player catch it (below).
  Teddiursa     NOT in this pack: a Habitat Block record in data/habitat_blocks.json (placed by
                tools/habitat_blocks.py with every other block) and a Habitat pool in data/spawns.json (compiled by
                tools/compile_spawns.py). This tool only reads them, for the report.
  the watcher   NOT in this pack: a conversation in data/dialogue.json, compiled with every other one into
                cobblers_dialogue by tools/compile_dialogue.py --all. npc_placements() names where the
                re-application's "npc" action puts it.

THE WAKE (the owner, 2026-10-02: "Wake it as a boss fight" - no wall). Until that day a 2-thick barrier curtain
crossed the hall in front of the bear; it is gone, and nothing in this file writes a barrier. The wake is the sleeping
Celebi's (docs/mechanics/CELEBI_WAKE.md, tools/sapling_celebi.py), rung for rung:

  ursaluna_cave/keeper      every period_ticks, while a player is within player_radius: near
  ursaluna_cave/near        AWAKE: return at once (the keeper stands down). ASLEEP: keep, then wake_check
  ursaluna_cave/keep        remove a second bear (a load race), put it back on its spot if anything moved it
  ursaluna_cave/wake_check  the trigger, a STATE CHECK: the nearest non-spectator within wake.radius of the spot
  ursaluna_cave/wake        as that player: merge wake.awake_nbt (the Celebi's AWAKE), set the awake score, roar,
                            and tell the player if they may not catch it (ursaluna.catch)
  ursaluna_cave/dress       the dormant flags, the tag, the spot - and the awake score back to 0, so the flag never
                            outlives the bear it describes; the return clock cleared; the bear's Pokemon UUID stored

THE BOSS RULES (the owner, 2026-10-02: "Den boss: returns after it is beaten, no badge to wake it, catchable only
late. A boss that stays dead is an event; one that returns is a place."):

  ursaluna_cave/track       every keeper pass with the den spot loaded: a tagged bear anywhere loaded resets the
                            absence count (it has NoAI and NoGravity: it cannot wander); absent on returns.absent_passes
                            loaded passes in a row, it is gone, and with no callback having seen it go the clock starts
                            (vanished); once returns.cooldown_ticks of game time have passed and nobody is within
                            returns.clear_radius, respawn. An awake bear left alone lies down again (dress)
  ursaluna_cave/gone        from the battle_fainted (why 1) and pokemon_captured (why 2) callbacks, by the Pokemon
                            UUID dress stored: the blackout guardians' route, proven on staging (EXP-042 session 5)
  ursaluna_cave/respawn     the summon guard, then spawn_at (a macro line, EXP-046) and dress_new
  ursaluna_cave/catch_check from the poke_ball_capture_calculated callback, as the thrower: asleep, the ball breaks
                            free and wakes the bear; awake, it breaks free unless the thrower holds catch.gate_flags

What is unproven (Unbattleable 0b on a live entity, a NoAI Pokemon in battle, RecalculatePose, the capture hook in
play, the return in play) is experiments/EXP-053-ursaluna-wake, for the integrator to run in game.

THE SUMMON GUARD keys on the tag and on the species, never on a bare distance. R14C (the Celebi) uses
`unless entity @e[type=cobblemon:pokemon,distance=..3]`, and a wild Pokemon wandering past the sapling has satisfied
that twice and suppressed the summon (docs/HANDOVER_SESSION.md). Here: no tagged bear anywhere loaded, and no
undressed Ursaluna with NoAI 1b within 4 blocks of the den spot (an interrupted spawn, which dress_new then takes).
NoAI is set on the entity alone by the `no_ai` property (the jar's NoAIProperty), so a player's own Ursaluna never
matches.

Ground comes from tools/ground.py (the canonical heightmap, rounded), never from a world.

  python tools/ursaluna_cave.py                  # -> build/datapacks/cobblers_ursaluna_cave
  python tools/ursaluna_cave.py --report         # the geometry, the steps and the measured cover; nothing written
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
DATA = ROOT / "data" / "ursaluna_cave.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_ursaluna_cave"
SCHEMA = "cobblers.ursaluna-cave/1"
PACK_FORMAT = 48  # Minecraft 1.21.1
FN = "ursaluna_cave"
# every boundary in the record is inclusive to within EPS: a block centre on
# a diagonal axis lands exactly on s = 0 or on an ellipse, and float rounding must not decide which side it falls
EPS = 1e-6


class CaveError(ValueError):
    pass


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise CaveError("%s: schema must be %s" % (path, SCHEMA))
    c = doc["cave"]
    u = doc["ursaluna"]
    if "curtain" in c["blocks"] or "curtain_from" in c["den"]:
        raise CaveError("the barrier curtain is gone (the owner, 2026-10-02: 'Wake it as a boss fight' - no wall)")
    if c["den"]["from"] > u["at_s"]:
        raise CaveError("the bear stands in front of its own den floor")
    if u.get("encounter") != "boss":
        raise CaveError("the bear is a boss that wakes (data/ursaluna_cave.json encounter_why)")
    if "uncatchable" in u.get("spawn_properties", []):
        raise CaveError("`uncatchable` cannot be cleared on a spawned Pokemon (data/sapling_celebi.json)")
    w = u.get("wake") or {}
    if w.get("trigger") != "player_near" or not isinstance(w.get("radius"), int) or w["radius"] <= 0:
        raise CaveError("ursaluna.wake needs trigger player_near and a positive integer radius")
    if (w.get("awake_nbt") or {}).get("Unbattleable") != "0b":
        raise CaveError("a wake that leaves Unbattleable on is not a fight")
    if "PoseType" in w["awake_nbt"]:
        raise CaveError("only PoseType \"SLEEP\" is proven (EXP-023); the wake hands the pose back with RecalculatePose")
    if w["radius"] >= u["keeper"]["player_radius"]:
        raise CaveError("the wake is checked inside the keeper's loop, so its radius must be inside the keeper's")
    r = u.get("returns") or {}
    if not isinstance(r.get("cooldown_ticks"), int) or r["cooldown_ticks"] < 20 * 60 * 30:
        raise CaveError("ursaluna.returns.cooldown_ticks must be an integer of at least half an hour (36000): a boss "
                        "that returns faster is a farm (the owner, 2026-10-02: 'one that returns is a place')")
    if not isinstance(r.get("clear_radius"), int) or r["clear_radius"] <= w["radius"]:
        raise CaveError("ursaluna.returns.clear_radius must exceed the wake's radius: it never returns in a player's face")
    if not isinstance(r.get("absent_passes"), int) or r["absent_passes"] < 2:
        raise CaveError("ursaluna.returns.absent_passes must be at least 2 (entities load a moment after their chunk)")
    c = u.get("catch") or {}
    if not c.get("gate_flags"):
        raise CaveError("ursaluna.catch.gate_flags is empty: the owner asked for a bear catchable only late")
    flags = {f["id"] for f in json.loads((ROOT / "data" / "progression.json").read_text(encoding="utf-8"))["flags"]}
    unknown = [f for f in c["gate_flags"] if f not in flags]
    if unknown:
        raise CaveError("ursaluna.catch.gate_flags %s are not flags in data/progression.json" % unknown)
    return doc


# ------------------------------------------------------------------ the frame


def frame(doc):
    """(origin x, origin z, axis unit (ux, uz), across unit (vx, vz)): block centres are measured from the mouth's."""
    mx, mz = doc["site"]["mouth"]
    ax, az = doc["site"]["axis"]
    n = math.hypot(ax, az)
    ux, uz = ax / n, az / n
    return mx + 0.5, mz + 0.5, (ux, uz), (-uz, ux)


def world_xz(doc, s, p):
    """The block column at (s along the axis, p across it)."""
    ox, oz, (ux, uz), (vx, vz) = frame(doc)
    return int(math.floor(ox + s * ux + p * vx)), int(math.floor(oz + s * uz + p * vz))


def floor_y(doc, ground):
    mx, mz = doc["site"]["mouth"]
    return ground(mx, mz)


# ------------------------------------------------------------------ the voxels


class Model:
    """Every block the carve writes, as boolean arrays indexed [y - y0, z - z0, x - x0]."""

    def __init__(self, doc, ground):
        c = doc["cave"]
        pa, ch = c["passage"], c["chamber"]
        m = int(c["margin"])
        self.floor = floor_y(doc, ground)
        ox, oz, (ux, uz), (vx, vz) = frame(doc)
        reach = max(pa["to"], ch["centre"] + ch["half_length"]) + m + 2
        wide = max(pa["half_width"], ch["half_width"]) + m + 2
        xs = [ox + s * ux + p * vx for s in (-m - 2, reach) for p in (-wide, wide)]
        zs = [oz + s * uz + p * vz for s in (-m - 2, reach) for p in (-wide, wide)]
        self.x0, self.x1 = int(math.floor(min(xs))), int(math.ceil(max(xs)))
        self.z0, self.z1 = int(math.floor(min(zs))), int(math.ceil(max(zs)))
        self.y0 = self.floor - m
        self.y1 = self.floor + 1 + max(pa["height"], ch["height"]) + m
        X, Z = np.meshgrid(np.arange(self.x0, self.x1 + 1) + 0.5, np.arange(self.z0, self.z1 + 1) + 0.5)
        self.S = (X - ox) * ux + (Z - oz) * uz
        self.P = (X - ox) * vx + (Z - oz) * vz
        self.G = ground.box(self.x0, self.z0, self.x1, self.z1)
        ys = np.arange(self.y0, self.y1 + 1)
        E = (ys + 0.5 - (self.floor + 1))[:, None, None]          # a block centre's height over the floor's surface
        S, P = self.S[None], self.P[None]
        up = E > 0
        passage = up & (S >= pa["from"] - EPS) & (S <= pa["to"] + EPS) & ((P / pa["half_width"]) ** 2 + (E / pa["height"]) ** 2 <= 1 + EPS)
        chamber = up & (((S - ch["centre"]) / ch["half_length"]) ** 2 + (P / ch["half_width"]) ** 2
                        + (E / ch["height"]) ** 2 <= 1 + EPS)
        self.void = passage | chamber
        Y = ys[:, None, None]
        under = Y <= (self.G[None] - int(c["keep_natural_top"]))
        self.shell = _dilate(self.void, m) & under
        cols = self.void.any(axis=0)
        level = (self.floor <= self.G)        # never lay a floor block over air: outside the hill there is none
        self.floor_cols = cols & level
        self.den_cols = self.floor_cols & (self.S >= c["den"]["from"] - EPS)
        self.hall_cols = self.floor_cols & ~self.den_cols
        self.lanterns = []
        for s, p in c["lanterns"]:
            x, z = world_xz(doc, s, p)
            col = self.void[:, z - self.z0, x - self.x0]
            if not col.any():
                raise CaveError("lantern at s=%s p=%s, column (%d, %d), is not over the cave" % (s, p, x, z))
            top = int(np.nonzero(col)[0].max()) + self.y0
            self.lanterns.append((x, top, z))
        u = doc["ursaluna"]
        bx, bz = world_xz(doc, u["at_s"], u["at_p"])
        self.bear = (bx, self.floor + 1, bz)

    def runs(self, mask3d):
        """Inclusive (x0, y0, z0, x1, y1, z1) boxes, one per run of True along z at each (y, x)."""
        out = []
        ny, nz, nx = mask3d.shape
        for yi in range(ny):
            layer = mask3d[yi]
            for xi in range(nx):
                col = layer[:, xi]
                if not col.any():
                    continue
                d = np.diff(np.concatenate(([0], col.astype(np.int8), [0])))
                for a, b in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]):
                    x, y = xi + self.x0, yi + self.y0
                    out.append((x, y, a + self.z0, x, y, b - 1 + self.z0))
        return out

    def floor_runs(self, cols):
        m = np.zeros_like(self.void)
        m[self.floor - self.y0] = cols
        return self.runs(m)

    def bbox(self):
        return self.x0, self.z0, self.x1, self.z1


def _dilate(mask, m):
    """Box (Chebyshev) dilation by m in all three axes, separably."""
    out = mask
    for axis in range(3):
        acc = out.copy()
        for k in range(1, m + 1):
            fwd = np.zeros_like(out)
            bwd = np.zeros_like(out)
            sl = [slice(None)] * 3
            sl2 = [slice(None)] * 3
            sl[axis], sl2[axis] = slice(k, None), slice(None, -k)
            fwd[tuple(sl)] = out[tuple(sl2)]
            bwd[tuple(sl2)] = out[tuple(sl)]
            acc |= fwd | bwd
        out = acc
    return out


# ------------------------------------------------------------------ the pack


def _fill(box, block, extra=""):
    return "fill %d %d %d %d %d %d %s%s" % (box + (block, extra))


def carve_lines(doc, M):
    b = doc["cave"]["blocks"]
    out = ["# Generated by tools/ursaluna_cave.py from data/ursaluna_cave.json: the Ursaluna's den west of Highwire",
           "# chunks-loaded-by: the re-application (forceload add %d %d %d %d over RCON before this runs)" % M.bbox(),
           "# 1. the shell, SOLID, %d blocks beyond every void and never in a column's top %d blocks"
           % (doc["cave"]["margin"], doc["cave"]["keep_natural_top"])]
    out += [_fill(r, b["shell"]) for r in M.runs(M.shell)]
    out.append("# 2. the void: the passage and the hall")
    out += [_fill(r, "minecraft:air") for r in M.runs(M.void)]
    out.append("# 3. the floor, only where the floor is under the hill's own ground")
    out += [_fill(r, b["floor"]) for r in M.floor_runs(M.hall_cols)]
    out += [_fill(r, b["den_floor"]) for r in M.floor_runs(M.den_cols)]
    out.append("# 4. the lanterns, hanging from the roof. No barrier anywhere: the bear is a boss that wakes")
    out += ["setblock %d %d %d %s replace" % (x, y, z, b["light"]) for x, y, z in M.lanterns]
    return out


def _at(M, doc):
    x, y, z = M.bear
    return "%.1f %d %.1f" % (x + 0.5, y, z + 0.5)


def _species_sel(doc):
    """The bear by what it IS, never by where it stands: the species, and NoAI 1b, which the `no_ai` spawn property sets
    on the entity only (NoAIProperty's Pokemon-side setter does nothing, Cobblemon 1.8.0 jar), so a player's own
    Ursaluna - the bear itself after a catch, sent out - never matches."""
    return 'nbt={NoAI:1b,Pokemon:{Species:"cobblemon:%s"}}' % doc["ursaluna"]["species"]


OBJ = "cobblers.ursaluna"
STORE = "cobblers:ursaluna"
FREE = "cobblers.ursaluna_free"
CALLBACKS = "data/cobblemon/callbacks/%s/cobblers_ursaluna.molang"


def pid_lines(score):
    """As the bear: its Pokemon UUID as the text MoLang's `pokemon.id` gives (Java's UUID.toString of the int array),
    into STORE bear.pid. The blackout's recovery/pid method (tools/blackout_pack.py), which matched a fainted and a
    caught guardian on staging (EXP-042 session 5): each int's eight hex digits, least significant first (scoreboard
    %= and /= floor, so a negative int's two's complement digits come out right), joined 8-4-4-4-12."""
    out = ["execute store result score #u%d %s run data get entity @s Pokemon.UUID[%d]" % (w, score, w) for w in range(4)]
    for w in range(4):
        for p in range(7, -1, -1):
            out += ["scoreboard players operation #n %s = #u%d %s" % (score, w, score),
                    "scoreboard players operation #n %s %%= #16 %s" % (score, score),
                    "execute store result storage %s hx.i int 1 run scoreboard players get #n %s" % (STORE, score),
                    'data modify storage %s hx.k set value "c%d%d"' % (STORE, w, p),
                    "function cobblers:%s/pid_hex with storage %s hx" % (FN, STORE),
                    "scoreboard players operation #u%d %s /= #16 %s" % (w, score, score)]
    out.append("function cobblers:%s/pid_join with storage %s px" % (FN, STORE))
    return out


def pid_join_line():
    d = lambda w, ps: "".join("$(c%d%d)" % (w, p) for p in ps)   # noqa: E731
    return '$data modify storage %s bear.pid set value "%s-%s-%s-%s-%s%s"' % (
        STORE, d(0, range(8)), d(1, range(4)), d(1, range(4, 8)), d(2, range(4)), d(2, range(4, 8)), d(3, range(8)))


def callback_files(doc):
    """The three MoLang callbacks, beside Cobblemon's own files under a cobblers_ name (EXP-042: a callback fires only
    from data/cobblemon/callbacks/<event>/; Cobblemon itself ships several scripts per event, e.g. pokemon_captured's
    three). No apostrophe in a comment string: MoLang strings are single-quoted."""
    ns, tag = doc["namespace"], doc["ursaluna"]["tag"]
    gone = "function %s:%s/gone {pid:\"' + t.pid + '\",why:%d}"
    return {
        CALLBACKS % "battle_fainted": "\n".join([
            "'Generated by tools/ursaluna_cave.py from data/ursaluna_cave.json. A wild Pokemon fainting in battle: if it';",
            "'is the Ursaluna of the den, matched by the Pokemon UUID ursaluna_cave/dress stored, its return clock starts.';",
            "'The route the blackout guardians proved on staging (EXP-042 session 5).';",
            "c.pokemon.actor.is_wild ? {",
            "  t.pid = c.pokemon.pokemon.id;",
            "  q.run_command('%s');" % (gone % (ns, FN, 1)),
            "};", ""]),
        CALLBACKS % "pokemon_captured": "\n".join([
            "'Generated by tools/ursaluna_cave.py from data/ursaluna_cave.json. A Pokemon caught: if it is the Ursaluna';",
            "'of the den, matched by its Pokemon UUID (the entity is gone by the time this runs), its return clock starts.';",
            "t.pid = q.pokemon.id;",
            "q.run_command('%s');" % (gone % (ns, FN, 2)),
            ""]),
        CALLBACKS % "poke_ball_capture_calculated": "\n".join([
            "'Generated by tools/ursaluna_cave.py from data/ursaluna_cave.json. A ball at the Ursaluna of the den: asleep,';",
            "'it breaks free and wakes the bear; awake, it breaks free unless the thrower holds the late badge flags.';",
            "'The level cap callback (cobblers_level_cap) shape: the answer comes back as a tag on the thrower.';",
            "t.pk = q.pokemon;",
            "t.th = q.thrower;",
            "t.pk.has_tag('%s') ? {" % tag,
            "  t.th.is_player ? {",
            "    q.run_command('execute as ' + t.th.uuid + ' at @s run function %s:%s/catch_check');" % (ns, FN),
            "    t.th.has_tag('%s') ? {" % FREE,
            "      q.set_shakes(0);",
            "      t.th.remove_tag('%s');" % FREE,
            "    };",
            "  };",
            "};", ""]),
    }


def awake_set(doc, value):
    return "scoreboard players set %s %s %d" % (doc["ursaluna"]["wake"]["awake_holder"], OBJ, int(value))


def awake_if(doc, value):
    return "score %s %s matches %d" % (doc["ursaluna"]["wake"]["awake_holder"], OBJ, int(value))


def gate_filter(doc, flags):
    return ",".join("%s:flag/%s=true" % (doc["namespace"], f) for f in flags)


def catch_allowed(doc):
    """`@s` when the thrower holds every late flag the record names (data/ursaluna_cave.json ursaluna.catch)."""
    return "@s[advancements={%s}]" % gate_filter(doc, doc["ursaluna"]["catch"]["gate_flags"])


def wake_selector(doc):
    """The player who wakes it: the nearest non-spectator within wake.radius of the bear's spot. No gate and no item
    (the Celebi's selector carries both; the owner asked for a bear that wakes when you get close)."""
    w = doc["ursaluna"]["wake"]
    gate = "".join(",advancements={%s:flag/%s=true}" % (doc["namespace"], f) for f in w.get("gate_flags") or [])
    return "@a[distance=..%d,gamemode=!spectator%s,limit=1,sort=nearest]" % (int(w["radius"]), gate)


def files(doc, ground):
    ns = doc["namespace"]
    u = doc["ursaluna"]
    k = u["keeper"]
    w = u["wake"]
    tag = u["tag"]
    obj = OBJ
    M = Model(doc, ground)
    at = _at(M, doc)
    bx, by, bz = M.bear
    nbt = ",".join("%s:%s" % (key, v) for key, v in u["nbt"].items())
    awake = ",".join("%s:%s" % (key, v) for key, v in w["awake_nbt"].items())
    ret = u["returns"]
    clear = int(ret["clear_radius"])
    catch_msg = json.dumps({"text": u["catch"]["message"], "color": "red"}, ensure_ascii=False)
    fn = {
        "%s/carve" % FN: carve_lines(doc, M),
        "%s/load" % FN: ["scoreboard objectives add %s dummy" % obj,
                         "# the awake score is NOT reset here: a restart must not put a woken bear back to sleep.",
                         "# ursaluna_cave/dress owns it.",
                         "# The return clock #gone (the game time the bear was first known gone; -1 while it stands) is",
                         "# set here only when it has never been set: a restart never moves it (contract C14's shape).",
                         "execute unless score #gone %s matches -2147483648.. run scoreboard players set #gone %s -1"
                         % (obj, obj),
                         "scoreboard players set #cool %s %d" % (obj, int(ret["cooldown_ticks"])),
                         "scoreboard players set #16 %s 16" % obj,
                         "data modify storage %s hex set value %s" % (STORE, json.dumps(list("0123456789abcdef"))),
                         "schedule function %s:%s/keeper %dt replace" % (ns, FN, k["period_ticks"])],
        "%s/dress_new" % FN: [
            "# just after a summon (the re-application's, or ursaluna_cave/respawn's): the nearest undressed Ursaluna",
            "# at the den spot, by species and NoAI, never a bare distance",
            "execute positioned %s as @e[type=cobblemon:pokemon,tag=!%s,distance=..4,%s,limit=1,sort=nearest] "
            "run function %s:%s/dress" % (at, tag, _species_sel(doc), ns, FN)],
        "%s/dress" % FN: ["data merge entity @s {%s}" % nbt,
                          "tag @s add %s" % tag,
                          "tp @s %s %s 0" % (at, u["yaw"]),
                          "# this bear is dormant by construction, so the awake flag describes it again",
                          awake_set(doc, 0),
                          "# and it stands: the return clock and its bookkeeping are clear",
                          "scoreboard players set #gone %s -1" % obj,
                          "scoreboard players set #why %s 0" % obj,
                          "scoreboard players set #abs %s 0" % obj,
                          "# its Pokemon UUID, for the callbacks that see it beaten or caught",
                          "function %s:%s/pid" % (ns, FN)],
        "%s/pid" % FN: ["# as the bear (from dress)"] + pid_lines(obj),
        "%s/pid_hex" % FN: ["$data modify storage %s px.$(k) set from storage %s hex[$(i)]" % (STORE, STORE)],
        "%s/pid_join" % FN: [pid_join_line()],
        "%s/keeper" % FN: ["# the return: only where the den spot is loaded; absence counts only on loaded passes in a row",
                           "execute unless loaded %d %d %d run scoreboard players set #abs %s 0" % (bx, by, bz, obj),
                           "execute if loaded %d %d %d run function %s:%s/track" % (bx, by, bz, ns, FN),
                           "execute positioned %s if entity @a[distance=..%d] run function %s:%s/near"
                           % (at, k["player_radius"], ns, FN),
                           "schedule function %s:%s/keeper %dt replace" % (ns, FN, k["period_ticks"])],
        "%s/track" % FN: [
            "# Is the bear here? It has NoAI and NoGravity, and keep puts a sleeping one back on its spot, so it cannot",
            "# wander: a tagged bear anywhere loaded is THE bear, and none means gone or not yet loaded.",
            "execute store result score #n %s if entity @e[type=cobblemon:pokemon,tag=%s]" % (obj, tag),
            "execute if score #n %s matches 1.. run scoreboard players set #abs %s 0" % (obj, obj),
            "# awake, alive and left alone (nobody within %d): it lies down again on its spot (a fight fled is not won)"
            % clear,
            "execute if score #n %s matches 1.. if %s if score #gone %s matches -1 positioned %s unless entity "
            "@a[distance=..%d] as @e[type=cobblemon:pokemon,tag=%s] run function %s:%s/dress"
            % (obj, awake_if(doc, 1), obj, at, clear, tag, ns, FN),
            "execute if score #n %s matches 1.. run return 0" % obj,
            "# absent on %d loaded passes in a row before it counts (entities load a moment after their chunk)"
            % int(ret["absent_passes"]),
            "scoreboard players add #abs %s 1" % obj,
            "execute if score #abs %s matches ..%d run return 0" % (obj, int(ret["absent_passes"]) - 1),
            "# gone with no callback having seen it go (a sword, an arrow, /kill): the clock starts now",
            "execute if score #gone %s matches -1 run function %s:%s/vanished" % (obj, ns, FN),
            "execute store result score #now %s run time query gametime" % obj,
            "scoreboard players operation #d %s = #now %s" % (obj, obj),
            "scoreboard players operation #d %s -= #gone %s" % (obj, obj),
            "execute if score #d %s < #cool %s run return 0" % (obj, obj),
            "# due: it returns only with nobody within %d, never in front of a player" % clear,
            "execute positioned %s if entity @a[distance=..%d] run return 0" % (at, clear),
            "function %s:%s/respawn" % (ns, FN)],
        "%s/vanished" % FN: ["execute store result score #gone %s run time query gametime" % obj,
                             "scoreboard players set #why %s 3" % obj],
        "%s/gone" % FN: [
            "# from a callback: $(pid) a Pokemon's UUID as text, $(why) 1 fainted in battle, 2 caught. Only the bear's",
            "$execute unless data storage %s bear{pid:\"$(pid)\"} run return 0" % STORE,
            "# the first sighting starts the clock; nothing later moves it",
            "execute unless score #gone %s matches -1 run return 0" % obj,
            "execute store result score #gone %s run time query gametime" % obj,
            "$scoreboard players set #why %s $(why)" % obj],
        "%s/respawn" % FN: [
            "# The summon guard: no tagged bear is loaded (track counted none) AND no undressed one of the species,",
            "# NoAI from its spawn, stands at the spot (an interrupted spawn, which is dressed instead). Never a bare",
            "# distance: R14C's failure, twice.",
            "execute positioned %s if entity @e[type=cobblemon:pokemon,tag=!%s,distance=..4,%s] run return run "
            "function %s:%s/dress_new" % (at, tag, _species_sel(doc), ns, FN),
            "# a spawn line parsed at server start spawns nothing until a /reload; a macro line is parsed when it runs",
            "# (EXP-046, which also saw a keeper put a killed worker back through its macro at a fresh boot)",
            "function %s:%s/spawn_at {x:%d,y:%d,z:%d}" % (ns, FN, bx, by, bz),
            "function %s:%s/dress_new" % (ns, FN)],
        "%s/spawn_at" % FN: ["$spawnpokemonat $(x) $(y) $(z) %s level=%d scale_modifier=%s %s"
                             % (u["species"], int(u["level"]), u["scale_modifier"], " ".join(u["spawn_properties"]))],
        "%s/catch_check" % FN: [
            "# as and at the thrower, from the poke_ball_capture_calculated callback: FREE on the thrower = it breaks free",
            "tag @s remove %s" % FREE,
            "# asleep: no ball takes it, and the ball wakes it (wake tells the thrower whether they may catch it)",
            "execute unless %s run tag @s add %s" % (awake_if(doc, 1), FREE),
            "execute unless %s positioned %s run return run function %s:%s/wake" % (awake_if(doc, 1), at, ns, FN),
            "# awake: only a thrower with the late badge flags (data/ursaluna_cave.json ursaluna.catch)",
            "execute unless entity %s run tag @s add %s" % (catch_allowed(doc), FREE),
            "execute if entity @s[tag=%s] run tellraw @s %s" % (FREE, catch_msg)],
        "%s/near" % FN: ["# WHILE IT SLEEPS ONLY. A woken bear is the fight: keeping it would teleport it back onto",
                         "# its spot every %d ticks, through the battle the wake exists to give." % k["period_ticks"],
                         "execute if %s run return 0" % awake_if(doc, 1),
                         "function %s:%s/keep" % (ns, FN),
                         "function %s:%s/wake_check" % (ns, FN)],
        "%s/keep" % FN: ["execute store result score #n %s if entity @e[tag=%s]" % (obj, tag),
                         "execute if score #n %s matches 2.. run kill @e[tag=%s,limit=1,sort=random]" % (obj, tag),
                         "execute as @e[tag=%s] positioned %s unless entity @s[distance=..%s] run tp @s %s %s 0"
                         % (tag, at, k["home_tolerance"], at, u["yaw"])],
        "%s/wake_check" % FN: [
            "# The wake (data/ursaluna_cave.json ursaluna.wake): a STATE CHECK on the keeper's loop, the sleeping",
            "# Celebi's mechanism (docs/mechanics/CELEBI_WAKE.md 1), never an advancement, so it cannot be burned.",
            "execute positioned %s as %s run function %s:%s/wake" % (at, wake_selector(doc), ns, FN)],
        "%s/wake" % FN: [
            "# run as the waking player, positioned at the bear's spot.",
            "# chunks-loaded-by: the waking player, who stands within %d blocks of the bear" % int(w["radius"]),
            "execute if %s run return 0" % awake_if(doc, 1),
            "# no bear (knocked out or caught, not yet returned): nothing to wake, and nothing to say",
            "execute unless entity @e[tag=%s] run return 0" % tag,
            "data merge entity @e[tag=%s,limit=1] {%s}" % (tag, awake),
            "# the keeper stands down on this score (ursaluna_cave/near)",
            awake_set(doc, 1),
            "tellraw @a[distance=..48] %s" % json.dumps({"text": w["message"], "color": "gold", "italic": True},
                                                        ensure_ascii=False),
            "playsound %s hostile @a[distance=..48] %d %d %d 2 0.6" % (w["sound"], bx, by, bz),
            "# the catch is per thrower and late (ursaluna.catch): say so to a waker who may not catch it",
            "execute unless entity %s run tellraw @s %s" % (catch_allowed(doc), catch_msg)],
    }
    out = {"data/%s/function/%s.mcfunction" % (ns, n): "\n".join(v) + "\n" for n, v in fn.items()}
    out.update(callback_files(doc))
    out["data/minecraft/tags/function/load.json"] = json.dumps({"values": ["%s:%s/load" % (ns, FN)]}, indent=2) + "\n"
    out["pack.mcmeta"] = json.dumps({"pack": {"pack_format": PACK_FORMAT,
                                              "description": "Cobblers: the Ursaluna's den west of Highwire "
                                                             "(tools/ursaluna_cave.py)"}}, indent=2) + "\n"
    return out


# ------------------------------------------------------------------ the re-application


def summon_command(doc, ground, M=None):
    M = M or Model(doc, ground)
    u = doc["ursaluna"]
    at = _at(M, doc)
    props = ["level=%d" % int(u["level"]), "scale_modifier=%s" % u["scale_modifier"]] + list(u["spawn_properties"])
    return ("execute unless entity @e[tag=%s] positioned %s unless entity @e[type=cobblemon:pokemon,distance=..4,%s] "
            "run spawnpokemonat %s %s %s" % (u["tag"], at, _species_sel(doc), at, u["species"], " ".join(props)))


def placement_steps(doc=None, ground=None):
    """For tools/reapply.py: hold the chunks, carve, summon over RCON, dress, release. Same tuple shape as
    tools/legendaries.py placement_steps (R14L) and tools/sapling_celebi.py (R14C)."""
    import ground as G
    doc = doc or load()
    ground = ground or G.load()
    M = Model(doc, ground)
    ns = doc["namespace"]
    hold = "%d %d %d %d" % M.bbox()
    return [("cmd", "forceload add " + hold), ("wait", 3),
            ("fn", "%s:%s/carve" % (ns, FN)),
            ("cmd", summon_command(doc, ground, M)),
            ("wait", 1),
            ("fn", "%s:%s/dress_new" % (ns, FN)),
            ("cmd", "forceload remove " + hold)]


def npc_placements(doc=None):
    """[(conversation id, (x, y, z), npc class)] for tools/reapply.py's "npc" action, from the committed data alone."""
    doc = doc or load()
    dl = json.loads((ROOT / "data" / "dialogue.json").read_text(encoding="utf-8"))
    conv = next((c for c in dl["conversations"] if c["id"] == doc["npc"]["conversation"]), None)
    if conv is None or not conv.get("npc_id"):
        raise CaveError("%s is not a conversation with an NPC in data/dialogue.json" % doc["npc"]["conversation"])
    return [(conv["id"], tuple(doc["npc"]["at"]), "%s:%s" % (doc["namespace"], conv["npc_id"]))]


# ------------------------------------------------------------------ CLI


def report(doc, ground):
    M = Model(doc, ground)
    c = doc["cave"]
    m = int(c["margin"])
    Y = np.arange(M.y0, M.y1 + 1)[:, None, None]
    cover = np.where(M.void, M.G[None] - Y, 10 ** 6)
    inner = M.S[None] > c["open_mouth_until"]
    worst = int(cover[M.void & inner].min()) if (M.void & inner).any() else None
    lines = ["mouth %s ground y%d = floor; cave voxels %d, shell %d, lanterns %d, no barrier"
             % (doc["site"]["mouth"], M.floor, int(M.void.sum()), int((M.shell & ~M.void).sum()), len(M.lanterns)),
             "bbox x%d..%d z%d..%d y%d..%d" % (M.x0, M.x1, M.z0, M.z1, M.y0, M.y1),
             "least ground over a carved block past s=%s: %s (margin %d needs %d)"
             % (c["open_mouth_until"], worst, m, m + 1),
             "bear at %s, yaw %s, scale %s, level %d; wakes for a player within %d (%s)"
             % (M.bear, doc["ursaluna"]["yaw"], doc["ursaluna"]["scale_modifier"], doc["ursaluna"]["level"],
                doc["ursaluna"]["wake"]["radius"], wake_selector(doc)),
             "returns %d ticks (%.1f h of server time) after it is gone, with nobody within %d; caught only by %s"
             % (doc["ursaluna"]["returns"]["cooldown_ticks"], doc["ursaluna"]["returns"]["cooldown_ticks"] / 72000.0,
                doc["ursaluna"]["returns"]["clear_radius"], catch_allowed(doc))]
    ch = c["chamber"]
    for s in (ch["centre"], doc["ursaluna"]["at_s"]):
        x, z = world_xz(doc, s, 0)
        col = M.void[:, z - M.z0, x - M.x0]
        across = M.void[M.floor + 1 - M.y0] & (np.abs(M.S - s) < 0.75)
        ps = M.P[across]
        lines.append("at s=%d (%d, %d): ground y%d, %d blocks of air over the floor, %.1f blocks across at the floor"
                     % (s, x, z, ground(x, z), int(col.sum()), float(ps.max() - ps.min() + 1)))
    for s in (0, 8, 17, 20, 25):
        x, z = world_xz(doc, s, 0)
        col = M.void[:, z - M.z0, x - M.x0]
        top = int(np.nonzero(col)[0].max()) + M.y0 if col.any() else None
        lines.append("passage s=%d (%d, %d): ground y%d, roof block y%s" % (s, x, z, ground(x, z), top))
    lines.append("steps: " + json.dumps([list(s) for s in placement_steps(doc, ground)]))
    try:
        lines.append("npc: %s" % (npc_placements(doc),))
    except CaveError as e:
        lines.append("npc: NOT PLACEABLE: %s" % e)
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", default=str(DATA))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--source-root")
    ap.add_argument("--report", action="store_true", help="print the geometry and the steps; write nothing")
    a = ap.parse_args(argv)
    import ground as G
    doc = load(Path(a.data))
    g = G.load(a.source_root)
    if a.report:
        print("\n".join(report(doc, g)))
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
    n = sum(1 for l in written["data/%s/function/%s/carve.mcfunction" % (doc["namespace"], FN)].splitlines()
            if l and not l.startswith("#"))
    print("ursaluna_cave: %d files -> %s (carve: %d commands)" % (len(written), out, n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

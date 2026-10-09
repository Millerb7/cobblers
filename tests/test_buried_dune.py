"""Undertow Basin (data/buried_dune.json, tools/buried_dune.py): a Sandaconda held under the east coast dunes.

Two kinds of test, kept apart:

  - EXPECTATIONS FROM OUTSIDE THE GENERATOR. The pack is built once and read as TEXT (its fill and setblock commands, its
    function bodies), then replayed onto a model of the world made from the canonical heightmap alone (solid at or under
    the ground, air above), the way a server would run it. Every property below is checked on that replay or on the
    heightmap, the caps, the sub-region's polygon, the route paths and the habitat blocks, never on a value the
    generator computed for itself. Mutating the GENERATOR (the chamber's depth, the bowl's cut, the roof) fails these;
    mutating only the record would move expectation and output together, so the record-side cases below are the guards
    (a copy of the record that breaks a rule must make the build refuse).
  - THE GUARDS BITE. Each edits a copy of the record and must make the build fail closed.

NOT covered (and not verified in any server): whether a Sandaconda spawned with scale_modifier=2.0 is twice normal size,
whether clearing NoAI on a live dormant entity wakes it into a normal wild Pokemon, whether the level-cap refusal stops a
throw in play, whether the block types the paint holds under the sand differ from the heightmap's idea of 'ground'.
"""
from __future__ import annotations

import copy
import json
import math
import re
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
np = pytest.importorskip("numpy")

import buried_dune as BD  # noqa: E402


def jl(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def g():
    import ground as G
    try:
        return G.load()
    except (SystemExit, OSError) as e:  # the canonical heightmap lives outside the repo (data/notes/source_tree.md)
        pytest.skip("NOT_EXECUTED: no canonical heightmap here: %s" % e)


@pytest.fixture(scope="module")
def doc():
    return BD.load()


@pytest.fixture(scope="module")
def pack(doc, g):
    out, _plan = BD.files(doc, g)
    return out


NS = "data/cobblers/function/buried_dune/"


def fn(pack, name):
    return pack[NS + name + ".mcfunction"].splitlines()


# ------------------------------------------------------------------ a replay of the build onto the heightmap

FILL = re.compile(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)( replace \S+)?$")
SET = re.compile(r"^setblock (-?\d+) (-?\d+) (-?\d+) (\S+)$")
AIR = "minecraft:air"


class World:
    """The heightmap as a world: stone at or under the ground, air above; then the pack's commands, in order. A `fill`
    with a `replace` filter acts only on the plants the filter names, and there are none on the model, so it is skipped
    (the only filters the pack uses are plants)."""

    def __init__(self, g, lines):
        self.g, self.cells = g, {}
        self.fills = []
        for ln in lines:
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            m = FILL.match(ln)
            if m:
                a = list(map(int, m.groups()[:6]))
                state, flt = m.group(7), m.group(8)
                self.fills.append((a, state, bool(flt)))
                if flt:
                    assert flt.split()[-1] in BD.PLANTS, ln
                    continue
                for x in range(a[0], a[3] + 1):
                    for y in range(a[1], a[4] + 1):
                        for z in range(a[2], a[5] + 1):
                            self.cells[(x, y, z)] = state
                continue
            m = SET.match(ln)
            assert m, "an unknown command in build: %s" % ln
            self.cells[(int(m.group(1)), int(m.group(2)), int(m.group(3)))] = m.group(4)

    def at(self, x, y, z):
        if (x, y, z) in self.cells:
            return self.cells[(x, y, z)]
        return "minecraft:stone" if y <= self.g(x, z) else AIR

    def top(self, x, z):
        """The highest block that is not air in a column (the model has nothing above the ground but our writes)."""
        y = self.g(x, z) + 12
        while self.at(x, y, z) == AIR:
            y -= 1
        return y


@pytest.fixture(scope="module")
def world(pack, g):
    return World(g, fn(pack, "build"))


def written_columns(world):
    return {(x, z) for x, _y, z in world.cells}


def cut_columns(world, g):
    """Columns whose top solid block is below their ground: cut down from the top."""
    return {(x, z) for x, z in written_columns(world) if world.top(x, z) < g(x, z)}


# ------------------------------------------------------------------ the premises in the record


def test_the_ground_numbers_the_record_quotes_are_the_heightmaps(doc, g):
    quoted = {7282: 99, 7298: 96, 7330: 85, 7350: 75, 7370: 68, 7390: 66, 7400: 64, 7410: 63, 7420: 62}
    assert {x: g(x, 5592) for x in quoted} == quoted
    assert doc["measured"]["centre_ground"] == g(*doc["site"]["centre"])
    ramp = {7298: 96, 7282: 99, 7274: 101, 7266: 104, 7258: 108}
    assert {x: g(x, 5592) for x in ramp} == ramp


def test_there_are_no_dune_landforms_to_find_the_largest_concavity_is_under_six_blocks(g):
    """The premise the place was designed on: the East Coast Dunes' F8 part has no basin. A ring-mean concavity over
    6 blocks anywhere would mean a basin exists and the record's first claim is false."""
    best = 0.0
    for z in range(5150, 6120, 8):
        for x in range(7170, 7400, 8):
            y = g(x, z)
            if y < 70:
                continue
            ring = [g(int(x + r * math.cos(a)), int(z + r * math.sin(a))) for r in (16, 28)
                    for a in np.linspace(0, 2 * math.pi, 16, endpoint=False)]
            best = max(best, float(np.mean(ring)) - y)
    assert 5.0 < best < 6.0, best


# ------------------------------------------------------------------ the siting, from the data the rules live in


def test_the_centre_is_in_cell_f8_and_in_the_east_coast_dunes(doc):
    x, z = doc["site"]["centre"]
    assert "ABCDEFGH"[z // 1024] + str(x // 1024 + 1) == doc["cell"] == "F8"
    from subregion_boxes import point_in_polygon
    subs = [s["id"] for s in jl("regions.json")["subregions"]
            if any(point_in_polygon(x, z, p) for p in s.get("polygons") or [])]
    assert doc["subregion"] in subs and "east_coast_dunes" in subs


def test_nothing_written_is_within_128_of_a_route_path_or_96_of_anything_authored(doc, world):
    paths = np.array([p for pl in jl("route_paths.json")["paths"].values() for p in pl], float)
    cols = np.array(sorted(written_columns(world)), float)
    dp = min(float(np.min(np.hypot(paths[:, 0] - x, paths[:, 1] - z))) for x, z in cols[::7])
    assert dp >= 128, dp
    # the habitat blocks are the authored things nearest to it; the whole scan is the generator's guard, so this is
    # the check against the one that matters: the palm's nest
    hb = [b for b in jl("habitat_blocks.json")["blocks"] if b.get("style") == "activated"]
    nearest = min(math.hypot(b["position"]["x"] - x, b["position"]["z"] - z) for b in hb for x, z in cols[::3])
    assert nearest >= 96, nearest


def test_the_leash_is_clear_of_every_activated_habitat_block(doc):
    ex, ez = doc["site"]["centre"]
    for b in jl("habitat_blocks.json")["blocks"]:
        if b.get("style") != "activated":
            continue
        d = math.hypot(b["position"]["x"] - ex, b["position"]["z"] - ez)
        assert d >= b["activated"]["spawn_range"] + doc["pokemon"]["leash"], (b["id"], d)


def test_no_written_column_is_wet_or_under_the_sea_margin(doc, world, g):
    import water_mask as WM
    bodies = WM.bodies()
    for x, z in sorted(written_columns(world)):
        assert g(x, z) >= doc["rules"]["min_ground"], (x, z, g(x, z))
        assert WM.level_at(x, z, g, bodies)[1] is None, (x, z)


# ------------------------------------------------------------------ the creature, its level and its gate


def test_the_level_is_over_the_band_and_at_the_ceiling_and_the_gate_is_the_cap_that_reaches_it(doc):
    import legendaries_audit as LA
    caps = LA.rct_caps()
    pk = doc["pokemon"]
    band = next(s for s in jl("spawns.json")["subregions"] if s["id"] == "east_coast_dunes")["level_band"]
    design = jl("encounter_design.json")
    tier = design["tables"]["east_coast_dunes"]["tier"]
    ceiling = design["rules"]["hearts"]["next_cap"][str(tier)]
    assert pk["level"] > band["maximum"] + 5, (pk["level"], band)       # well above the band
    assert pk["level"] <= ceiling
    gates = sorted((c, f) for f, c in caps.items() if f and f.startswith("gym"))
    first = next(f for c, f in gates if c >= pk["level"])                  # the first badge whose cap reaches it
    assert first == pk["gate"] == "gym7_cleared"
    prev = max(c for c, f in gates if c < pk["level"])
    assert prev < pk["level"] <= caps[first]
    assert pk["level"] > caps["gym6_cleared"], "a six-badge player must be unable to catch it"


def test_it_is_catchable_and_big_and_sandaconda(doc, pack):
    spawn = fn(pack, "undertow/spawn")
    line = next(l for l in spawn if "spawn_at" in l)
    assert 'species:"sandaconda"' in line and "level=55" in line and "scale_modifier=2.0" in line
    assert "uncatchable" not in "\n".join(l for ls in pack.values() for l in ls.splitlines() if "spawn_at" in l)
    act = "\n".join(l for k, v in pack.items() if k.endswith("summon_act.mcfunction") for l in v.splitlines())
    assert 'species:"sandaconda"' in act and "uncatchable" not in act
    assert doc["pokemon"]["species"] == "cobblemon:sandaconda" and doc["pokemon"]["catch_rule"] == "catchable_after_gate"


JAR = Path("C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/Cobblemon-fabric-1.8.0+1.21.1.jar")


def test_the_species_and_the_property_exist_in_the_cobblemon_1_8_0_jar():
    if not JAR.is_file():
        pytest.skip("NOT_EXECUTED: the 1.8.0 jar is not at %s" % JAR)
    z = zipfile.ZipFile(JAR)
    sp = json.loads(z.read("data/cobblemon/species/generation8/sandaconda.json"))
    assert sp["baseStats"]["hp"] == 72 and sp["hitbox"]["width"] == 2 and sp["baseScale"] == 0.8
    prop = [n for n in z.namelist() if n.endswith("PokemonProperties$Companion.class")]
    assert prop and b"scale_modifier" in z.read(prop[0])


# ------------------------------------------------------------------ the pack, replayed


def test_the_palette_is_only_the_declared_ids_and_none_is_a_spawn_condition(doc, world):
    spawn = set(jl("spawn_blocks.json")["blocks"])
    ids = set(doc["blocks"]["ids"])
    placed = {s.split("[")[0] for s in world.cells.values()}
    assert placed <= ids, placed - ids
    assert not (placed & spawn), placed & spawn


def test_no_sand_and_no_concrete_is_written_anywhere_in_the_pack(pack):
    for name, text in pack.items():
        for line in text.splitlines():
            if line.startswith(("fill", "setblock")) and name.endswith("build.mcfunction"):
                assert "sand " not in line.replace("sandstone", "") + " ", line
                assert "concrete" not in line, line
            if "concrete" in line:
                pytest.fail("concrete in %s: %s" % (name, line))


def test_the_chamber_is_a_sealed_shell_with_the_declared_interior(doc, world, g):
    c = doc["chamber"]
    cx, cz = doc["site"]["centre"]
    x0, x1, z0, z1 = cx - c["half_x"], cx + c["half_x"], cz - c["half_z"], cz + c["half_z"]
    shell = sorted(y for (x, y, z), s in world.cells.items() if s == c["shell"])
    assert shell, "no shell"
    bed, top = shell[0] + 1, shell[-1] - 1            # inside the floor and the roof
    assert top - bed + 1 == c["height"]
    interior = {(x, y, z) for x in range(x0, x1 + 1) for y in range(bed, top + 1) for z in range(z0, z1 + 1)}
    assert all(world.at(*p) in (AIR, "minecraft:light[level=1]") for p in interior)
    # sealed: every cell touching the interior from outside is the shell
    for (x, y, z) in interior:
        for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            q = (x + dx, y + dy, z + dz)
            if q not in interior:
                assert world.at(*q) == c["shell"], q
    # the lights are the four corners of the top row and nothing else is lit
    lights = [p for p, s in world.cells.items() if s.startswith("minecraft:light")]
    assert sorted(lights) == sorted((x, top, z) for x in (x0, x1) for z in (z0, z1))


def test_four_natural_blocks_stand_over_the_roof_at_the_lowest_column_of_the_bed(doc, world, g):
    """The cover, measured on the replayed world: the final surface of every column over the shell, less the roof."""
    c = doc["chamber"]
    cx, cz = doc["site"]["centre"]
    roof = max(y for (x, y, z), s in world.cells.items() if s == c["shell"] and x == cx and z == cz)
    low = min(world.top(x, z) for x in range(cx - c["half_x"] - 1, cx + c["half_x"] + 2)
              for z in range(cz - c["half_z"] - 1, cz + c["half_z"] + 2))
    assert low - roof >= c["cover"], (low, roof)
    # and the bed is the room above the sea, not a cave in the beach
    assert roof - c["height"] - 1 >= 66


def test_the_sleeper_lies_in_the_bed_and_rises_on_the_basins_floor(doc, pack, world, g):
    hold = fn(pack, "undertow/hold")
    home = re.search(r"tp @s ([\d.]+) (\d+) ([\d.]+) -90.0 0", hold[1])
    rise = re.search(r"tp @s ([\d.]+) (\d+) ([\d.]+) -90.0 0", hold[3])
    hx, hy, hz = float(home.group(1)), int(home.group(2)), float(home.group(3))
    rx, ry, rz = float(rise.group(1)), int(rise.group(2)), float(rise.group(3))
    assert (math.floor(hx), math.floor(hz)) == (math.floor(rx), math.floor(rz)) == tuple(doc["site"]["centre"])
    # feet in the bed with two blocks of air over them, on the shell's floor
    assert world.at(int(hx), hy, int(hz)) == AIR and world.at(int(hx), hy + 1, int(hz)) == AIR
    assert world.at(int(hx), hy - 1, int(hz)) == doc["chamber"]["shell"]
    # it rises onto solid ground with room: 3 blocks of air (the scaled hitbox is at most 3 high)
    assert world.at(int(rx), ry - 1, int(rz)) != AIR
    assert all(world.at(int(rx), ry + k, int(rz)) == AIR for k in range(0, 4))
    assert ry - 1 == world.top(int(rx), int(rz)) < g(int(rx), int(rz))      # the floor is CUT below the ground
    # the wake and the settle use the same two places
    wake = "\n".join(fn(pack, "undertow/wake"))
    settle = "\n".join(fn(pack, "undertow/settle"))
    assert "%.1f %d %.1f -90.0 0" % (rx, ry, rz) in wake and "%.1f %d %.1f -90.0 0" % (hx, hy, hz) in settle
    assert "NoAI:0b" in wake and "NoAI:1b" in settle and "remove cobblers.res_dormant" in wake and "add cobblers.res_dormant" in settle


def test_only_a_step_into_the_basin_wakes_it_not_the_rim_or_the_slope(doc, pack, world, g):
    """A player's feet on every standable column near the site, 3D from the bed, against the trigger: every column
    inside the trigger is a CUT column (the basin's), none on the natural rim or the dune around it."""
    hold = fn(pack, "undertow/hold")
    trig = int(re.search(r"distance=\.\.(\d+),gamemode=!spectator\] run function .*wake", hold[2]).group(1))
    assert trig == doc["pokemon"]["trigger"] == 14
    home = re.search(r"tp @s ([\d.]+) (\d+) ([\d.]+)", hold[1])
    ax, ay, az = float(home.group(1)), int(home.group(2)), float(home.group(3))
    cut = cut_columns(world, g)
    inside = []
    for x in range(int(ax) - 40, int(ax) + 41):
        for z in range(int(az) - 40, int(az) + 41):
            feet = world.top(x, z) + 1
            d = math.sqrt((x + 0.5 - ax) ** 2 + (feet - ay) ** 2 + (z + 0.5 - az) ** 2)
            if d <= trig:
                inside.append((x, z))
    assert inside and all(p in cut for p in inside), [p for p in inside if p not in cut][:5]
    # and a player standing on the basin's floor at the centre does wake it
    assert (int(ax), int(az)) in inside


def test_the_awake_leash_and_the_settle_are_from_where_it_rose(doc, pack):
    hold = "\n".join(fn(pack, "undertow/hold"))
    assert "unless entity @s[x=%.1f,y=%d,z=%.1f,distance=..36]" % (doc["site"]["centre"][0] + 0.5, 95, doc["site"]["centre"][1] + 0.5) in hold
    assert "distance=..52,gamemode=!spectator] run function cobblers:buried_dune/undertow/settle" in hold
    assert doc["pokemon"]["leash"] + doc["pokemon"]["settle_margin"] == 52


def test_the_pack_writes_air_only_from_the_ground_down_and_builds_nothing_above_it_but_bones(doc, world, g):
    for (a, state, flt) in world.fills:
        if flt or state != AIR:
            continue
        x0, y0, z0, x1, y1, z1 = a
        in_bed = False
        c = doc["chamber"]
        cx, cz = doc["site"]["centre"]
        if abs(x0 - cx) <= c["half_x"] and abs(z0 - cz) <= c["half_z"] and x1 - x0 > 3:
            in_bed = True
        if in_bed:
            continue
        # a surface cut: one column row, its top is its own ground, and no cut goes deeper than 7 below it
        for x in range(x0, x1 + 1):
            for z in range(z0, z1 + 1):
                assert y1 == g(x, z), ((x, z), y1, g(x, z))
                assert g(x, z) - y0 + 1 <= 7, ((x, z), y0, g(x, z))
    for (x, y, z), s in world.cells.items():
        if y > g(x, z) and s != AIR:
            assert s.startswith("minecraft:bone_block"), ((x, y, z), s)


def test_every_bone_stands_on_uncut_ground_or_on_another_bone(world, g):
    cut = cut_columns(world, g)
    for (x, y, z), s in world.cells.items():
        if not s.startswith("minecraft:bone_block"):
            continue
        assert (x, z) not in cut, (x, z)
        below = world.at(x, y - 1, z)
        assert below != AIR, ((x, y, z), "a floating bone")


def test_the_trails_are_v_grooves_cut_into_the_slope_and_reach_their_waypoints(doc, world, g):
    cut = cut_columns(world, g)
    tp = doc["trail_profile"]
    for t in doc["trails"]:
        for wp in (t["waypoints"][0], t["waypoints"][-1]):
            near = min(math.hypot(x + 0.5 - wp[0], z + 0.5 - wp[1]) for x, z in cut)
            assert near <= 3.0, (t["id"], wp, near)
    depths = {}
    for x, z in cut:
        depths[g(x, z) - world.top(x, z)] = depths.get(g(x, z) - world.top(x, z), 0) + 1
    assert depths.get(tp["centre_depth"], 0) > 100 and depths.get(tp["edge_depth"], 0) > 100, depths
    # the outbound trail ends in a pit deeper than the trail
    end = doc["trails"][3]["waypoints"][-1]
    assert g(*end) - world.top(*end) == doc["trails"][3]["end_pit"]["depth"]


def test_the_slip_face_points_are_the_tops_of_the_cut_west_wall(doc, pack, world, g):
    pts = [re.search(r"particle \S+ ([\d.]+) ([\d.]+) ([\d.]+) 0.3 0.9", l) for l in fn(pack, "undertow/signs") if "particle" in l]
    assert len(pts) == doc["bowl"]["slip_face"]["points"]
    cx, cz = doc["site"]["centre"]
    for m in pts:
        x, y, z = float(m.group(1)), float(m.group(2)), float(m.group(3))
        col = (int(math.floor(x)), int(math.floor(z)))
        assert g(*col) - world.top(*col) >= doc["bowl"]["slip_face"]["min_cut"], col
        assert abs(y - 0.2 - g(*col)) < 1e-6
        assert col[0] <= cx + 1, "the wall is on the high (west) side"


# ------------------------------------------------------------------ the functions and the steps


def test_the_keeper_loop_schedules_itself_runs_the_sleeper_and_the_signs_and_the_load_tag_names_load(doc, pack):
    keeper = "\n".join(fn(pack, "keeper"))
    assert "run function cobblers:buried_dune/undertow/keep" in keeper and "run function cobblers:buried_dune/undertow/signs" in keeper
    assert "schedule function cobblers:buried_dune/keeper 40t replace" in keeper
    assert json.loads(pack["data/minecraft/tags/function/load.json"]) == {"values": ["cobblers:buried_dune/load"]}
    assert "scoreboard objectives add cobblers.dune dummy" in "\n".join(fn(pack, "load"))


def test_every_function_is_run_by_a_step_or_named_by_another_file_of_the_pack(pack):
    names = {k[len("data/cobblers/function/"):-len(".mcfunction")] for k in pack if k.startswith("data/cobblers/function/")}
    text = "\n".join(pack.values())
    run_by_step = {"buried_dune/build", "buried_dune/summon"}
    for n in sorted(names - run_by_step):
        refs = text.count("cobblers:" + n)
        own = sum(1 for k, v in pack.items() if k.endswith(n + ".mcfunction") for l in v.splitlines() if "cobblers:" + n in l)
        assert refs - own >= 1 or n == "buried_dune/load", ("unreferenced", n)
    assert "cobblers:buried_dune/load" in pack["data/minecraft/tags/function/load.json"]


def test_the_steps_are_the_blocks_in_a_held_box_and_the_chain(doc, g):
    steps = BD.placement_steps(doc, g)
    assert [k for k, _v in steps] == ["cmd", "wait", "fn", "cmd"]
    add, rem = steps[0][1], steps[3][1]
    assert add.startswith("forceload add ") and rem == add.replace("add", "remove", 1)
    x0, z0, x1, z1 = map(int, add.split()[2:])
    assert ((x1 >> 4) - (x0 >> 4) + 1) * ((z1 >> 4) - (z0 >> 4) + 1) <= 256
    assert steps[2][1] == "cobblers:buried_dune/build"
    ent = BD.entity_steps(doc, g)
    assert [k for k, _v in ent] == ["fn", "wait", "check"]
    assert ent[0][1] == "cobblers:buried_dune/summon" and ent[2][1][0] == "chunk_look" and ent[2][1][2] == 1


def test_reapply_wires_the_two_steps_the_pack_and_the_prepare_job():
    text = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert text.index('"R9FS"') < text.index('"R9BD"') < text.index('("R9E"')
    assert text.index('"R18FS"') < text.index('"R18BD"')
    assert 'add("buried_dune", "buried_dune.py", *src)' in text
    import reapply
    assert "cobblers_buried_dune" in reapply.SERVER_PACKS and "cobblers_buried_dune" in reapply.WORLD_LOCAL
    assert "cobblers_buried_dune" not in reapply.EXCLUDED


def test_the_chain_is_the_look_then_act_chain_and_never_kills_what_stands(doc, pack):
    act = "\n".join(l for k, v in pack.items() if k.endswith("summon_act.mcfunction") for l in v.splitlines())
    assert "kill" not in act and "unless entity @e[type=cobblemon:pokemon,tag=cobblers.res.undertow]" in act
    assert "tag=cobblers.guardian" in act
    done = "\n".join(l for k, v in pack.items() if k.endswith("summon_done.mcfunction") for l in v.splitlines())
    assert "forceload remove" in done and "tag=!cobblers.dune_new" in done


# ------------------------------------------------------------------ the probes


def test_the_presence_probes_hold_on_the_replayed_world_and_name_the_keepers_entity(doc, pack, world, g):
    probes = json.loads((ROOT / "data" / "world_probes.json").read_text(encoding="utf-8"))["places"]["buried_dune"]
    blocks = [p for p in probes if "block" in p]
    ents = [p for p in probes if "entity" in p]
    assert len(blocks) >= 8 and len(ents) == 1
    for p in blocks:
        x, y, z, want = p["block"]
        got = world.at(x, y, z)
        if want == "!air":
            ok = got != AIR
        elif "[" in want:
            ok = got == want
        else:
            ok = got.split("[")[0] == want
        assert ok == p["expect"], (p["what"], want, got)
    e = ents[0]
    assert "tag=cobblers.res.undertow" in e["entity"] and "cobblemon:sandaconda" in e["entity"] and e["count"] == 1
    hold = fn(pack, "undertow/hold")
    home = re.search(r"tp @s ([\d.]+) (\d+) ([\d.]+)", hold[1])
    assert e["hold"] == [int(float(home.group(1))), int(home.group(2)), int(float(home.group(3)))]


def test_the_probes_in_the_file_are_what_the_generator_writes(doc, g):
    assert BD.probes(doc, g)["buried_dune"] == json.loads((ROOT / "data" / "world_probes.json").read_text(encoding="utf-8"))["places"]["buried_dune"]


# ------------------------------------------------------------------ the guards bite


def _refused(d, g, needle):
    with pytest.raises(SystemExit) as e:
        BD.files(d, g)
    assert needle in str(e.value), str(e.value)[:600]


def test_a_level_over_the_tier_ceiling_is_refused(doc, g):
    d = copy.deepcopy(doc)
    d["pokemon"]["level"] = 61
    _refused(d, g, "ceiling")


def test_a_site_moved_onto_authored_ground_is_refused(doc, g):
    d = copy.deepcopy(doc)
    d["site"]["centre"] = [7376, 5540]            # the palm sapling's nest block (7376, 5512) is 28 away
    _refused(d, g, "authored in data/")


def test_a_spawn_condition_block_in_the_shell_is_refused(doc, g):
    d = copy.deepcopy(doc)
    d["chamber"]["shell"] = "minecraft:sand"
    d["blocks"]["ids"].append("minecraft:sand")
    _refused(d, g, "spawn-condition")


def test_a_trail_into_the_sea_is_refused(doc, g):
    d = copy.deepcopy(doc)
    d["trails"][0]["waypoints"][0] = [7440, 5640]
    _refused(d, g, "wet or ground")


def test_a_record_the_heightmap_disagrees_with_is_refused(doc, g):
    d = copy.deepcopy(doc)
    d["measured"]["centre_ground"] = 104
    _refused(d, g, "centre_ground")


def test_a_wrong_cell_is_refused(doc, g):
    d = copy.deepcopy(doc)
    d["cell"] = "F7"
    _refused(d, g, "cell")


def test_a_trigger_outside_the_leash_is_refused(doc):
    d = copy.deepcopy(doc)
    d["pokemon"]["trigger"] = 40
    with pytest.raises(SystemExit):
        import tempfile
        p = Path(tempfile.mkdtemp()) / "x.json"
        p.write_text(json.dumps(d), encoding="utf-8")
        BD.load(p)

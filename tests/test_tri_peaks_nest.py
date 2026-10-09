"""The Tri Peaks' open-summit nest (data/tri_peaks_nest.json, tools/tri_peaks_nest.py, step R9TP).

Written by the builder of the nest, because the brief said so; the independent audit is still owed to another agent.
Every expectation is read from the file that owns the rule (data/trainers.json for the caps, data/encounter_design.json
for the tier ceiling, data/route_paths.json, data/habitat_blocks.json, data/spawn_blocks.json, the heightmap), never from
the record being checked; the sightline and the walk are recomputed here with code of this file's own, not the tool's.
The generator is mutated (the tor shape, the ground), never the record, to show it fails closed.
"""
import heapq
import json
import math
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import tri_peaks_nest as T  # noqa: E402
import resident_encounters as RE  # noqa: E402


def jload(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


RAW = json.loads(T.DATA.read_text(encoding="utf-8"))
REC = RAW["encounters"][0]
BUILD = REC["build"]
AX, AZ = REC["location"]["x"], REC["location"]["z"]
BOX = BUILD["bbox"]


@pytest.fixture(scope="module")
def ground():
    import ground as G
    try:
        return G.load()
    except BaseException as e:      # SystemExit when the heightmap root is not configured
        pytest.skip("NOT_EXECUTED: the canonical heightmap is not available (%s)" % str(e)[:80])


@pytest.fixture(scope="module")
def doc():
    return T.load()


@pytest.fixture(scope="module")
def pack(doc, ground):
    return T.files(doc, ground)


def _dress(pack):
    text = pack["data/cobblers/function/tri_peaks_nest/crownbreaker/dress.mcfunction"]
    sets, fills = {}, []
    for line in text.splitlines():
        m = re.match(r"setblock (-?\d+) (-?\d+) (-?\d+) (\S+) replace$", line)
        if m:
            x, y, z = (int(m.group(i)) for i in (1, 2, 3))
            sets[(x, y, z)] = m.group(4)
        m = re.match(r"fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) air replace #minecraft:replaceable$", line)
        if m:
            fills.append(tuple(int(m.group(i)) for i in range(1, 7)))
    return sets, fills


# ------------------------------------------------------------------ the record is the gym 3 nest the brief asked for


def test_the_catch_gate_is_the_level_cap_between_gym_3_and_gym_4():
    aces = jload("trainers.json")["generation_contract"]["gym_ace_levels"]
    lvl = REC["level"]
    assert lvl > aces[2], "L%d is within the cap %d a player carries before beating gym 3: not a mistake to meet" % (lvl, aces[2])
    assert lvl <= aces[3], "L%d is over the cap %d the third badge gives: not catchable from gym 3" % (lvl, aces[3])
    assert REC["gate"] == "gym3_cleared" and REC["catch_rule"] == "catchable_after_gate"


def test_it_has_no_presence_gate_so_it_can_be_seen_before_it_is_catchable(tmp_path):
    assert BUILD["appears_after"] is None
    bad = json.loads(T.DATA.read_text(encoding="utf-8"))
    bad["encounters"][0]["build"]["appears_after"] = "gym3_cleared"
    p = tmp_path / "gated.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(T.NestError):
        T.load(p)


def test_the_species_is_a_tyranitar_the_jar_knows():
    import glob
    import zipfile
    jars = glob.glob("C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/Cobblemon-fabric-1.8.0*.jar")
    if not jars:
        pytest.skip("NOT_EXECUTED: the 1.8.0 jar snapshot is not on this machine")
    names = zipfile.ZipFile(jars[0]).namelist()
    assert "data/cobblemon/species/generation2/tyranitar.json" in names
    assert REC["species"] == "cobblemon:tyranitar"


def test_the_level_is_within_its_places_ceiling(ground):
    import sys as _s
    _s.path.insert(0, str(ROOT / "tools"))
    from subregion_boxes import point_in_polygon
    design = jload("encounter_design.json")
    subs = [s["id"] for s in jload("regions.json")["subregions"]
            if any(point_in_polygon(AX, AZ, p) for p in s.get("polygons") or []) and s["id"] in design["tables"]]
    assert subs and subs[0] == "the_tri_peaks", subs
    tier = design["tables"][subs[0]]["tier"]
    assert REC["level"] <= design["rules"]["hearts"]["next_cap"][str(tier)]


# ------------------------------------------------------------------ siting


def test_it_stands_clear_of_every_route_path():
    d = min(math.hypot(x - AX, z - AZ) for pl in jload("route_paths.json")["paths"].values() for x, z in pl)
    assert d >= jload("encounter_design.json")["rules"]["hearts"]["clear_of_path_blocks"], d
    # the whole dressed box too: the scree's toe is the nearest part
    dbox = min(math.hypot(x - cx, z - cz) for pl in jload("route_paths.json")["paths"].values() for x, z in pl
               for cx in (BOX[0], BOX[2]) for cz in (BOX[1], BOX[3]))
    assert dbox >= 128, dbox


def test_its_fight_does_not_overlap_an_activated_habitat_block():
    near = []
    for b in jload("habitat_blocks.json")["blocks"]:
        if b.get("style") != "activated":
            continue
        d = math.hypot(b["position"]["x"] - AX, b["position"]["z"] - AZ)
        if d < b["activated"]["spawn_range"] + BUILD["leash"]:
            near.append((b["id"], round(d)))
    assert not near, near


def test_nothing_else_authored_stands_in_or_beside_the_box():
    """Our list is not the world: every x/z any other data file authors within 60 blocks of the dressed box."""
    x0, z0, x1, z1 = BOX[0] - 60, BOX[1] - 60, BOX[2] + 60, BOX[3] + 60
    hits = []

    def inb(x, z):
        return x0 <= x <= x1 and z0 <= z <= z1

    def walk(o, f):
        if isinstance(o, dict):
            if isinstance(o.get("x"), (int, float)) and isinstance(o.get("z"), (int, float)) and inb(o["x"], o["z"]):
                hits.append((f, o["x"], o["z"]))
            for v in o.values():
                walk(v, f)
        elif isinstance(o, list):
            if len(o) in (2, 3) and all(isinstance(t, (int, float)) for t in o):
                x, z = (o[0], o[1]) if len(o) == 2 else (o[0], o[2])
                if inb(x, z):
                    hits.append((f, x, z))
            else:
                for v in o:
                    walk(v, f)
    for p in sorted((ROOT / "data").glob("*.json")) + sorted((ROOT / "data").glob("*/*.json")):
        if p.name in ("tri_peaks_nest.json", "world_probes.json"):
            continue
        try:
            walk(json.loads(p.read_text(encoding="utf-8")), p.name)
        except ValueError:
            continue
    # the one rejected search option of Highwire's own site history (data/towns.json option_2_shelves): not a placement
    hits = [h for h in hits if not (h[0] == "towns.json" and (h[1], h[2]) == (1480, 1170))]
    assert not hits, hits[:5]


def test_the_anchor_and_box_are_the_heightmaps(doc, ground):
    got = T.measure(doc, ground)[0]
    assert list(got[1]) == BUILD["anchor"] and got[2] == BUILD["ground_y"] == REC["location"]["measured_surface_or_bed_y"]
    assert got[3] == BOX                       # exact, not merely inside: a stale box holds chunks it does not write


# ------------------------------------------------------------------ what the pack writes


def test_every_block_is_in_the_box_on_its_columns_ground_and_nothing_else(pack, ground):
    sets, fills = _dress(pack)
    assert len(sets) > 2000
    bad = []
    for (x, y, z), blk in sets.items():
        if not (BOX[0] <= x <= BOX[2] and BOX[1] <= z <= BOX[3]):
            bad.append(("outside the box", x, y, z))
        gy = ground(x, z)
        if not (gy <= y <= gy + 12):
            bad.append(("not seated on its column's ground", x, y, z, gy))
    assert not bad, bad[:5]
    # surface work replaces the ground's top block and nothing under it
    assert sum(1 for (x, y, z) in sets if y == ground(x, z)) > 1500
    for x0, y0, z0, x1, y1, z1 in fills:
        assert x0 == x1 and z0 == z1 and y0 > ground(x0, z0) - 1 and y1 - y0 <= 2, (x0, y0, z0)


def test_the_crown_has_six_teeth_and_the_south_is_open(pack, ground):
    sets, _ = _dress(pack)
    by_col = {}
    for (x, y, z), blk in sets.items():
        gy = ground(x, z)
        if y > gy:
            by_col.setdefault((x, z), []).append(y - gy)
    tall = {c: max(v) for c, v in by_col.items() if max(v) >= 7}
    clusters = []                                    # tall columns within 3.5 of each other are one tooth
    for c in sorted(tall):
        for cl in clusters:
            if any(math.hypot(c[0] - o[0], c[1] - o[1]) <= 3.5 for o in cl):
                cl.append(c)
                break
        else:
            clusters.append([c])
    heights = sorted(max(tall[c] for c in cl) for cl in clusters)
    assert heights == [7, 8, 9, 10, 11, 12], heights
    # nothing taller than the broken tooth's stump stands in the breach: x within 5 of the anchor, z 4..30 south
    assert not [c for c, h in by_col.items() if abs(c[0] - AX) <= 5 and AZ + 4 <= c[1] <= AZ + 30 and max(h) > 3]


def test_no_written_block_is_a_spawn_condition_and_none_is_concrete(pack):
    sets, _ = _dress(pack)
    policy = set(jload("spawn_blocks.json")["blocks"])
    ids = {re.sub(r"\[.*\]$", "", b) for b in sets.values()}
    assert not ids & policy, sorted(ids & policy)
    assert not [i for i in ids if "concrete" in i], ids
    assert all(i.startswith("minecraft:") for i in ids), ids


def test_the_pack_has_the_keeper_and_no_summon_and_nothing_orphaned(pack, doc, ground):
    base = "data/cobblers/function/tri_peaks_nest/"
    assert base + "crownbreaker/bind_new.mcfunction" not in pack
    for need in ("load", "keeper", "spawn_at", "crownbreaker/dress", "crownbreaker/keep", "crownbreaker/hold",
                 "crownbreaker/wake", "crownbreaker/settle", "crownbreaker/spawn", "crownbreaker/bind"):
        assert base + need + ".mcfunction" in pack, need
    names = {"cobblers:" + k[len("data/cobblers/function/"):-len(".mcfunction")]: k for k in pack
             if k.startswith("data/cobblers/function/") and k.endswith(".mcfunction")}
    run_by_step = {fn for kind, fn in T.placement_steps(doc, ground) if kind == "fn"}
    orphans = []
    for n, k in sorted(names.items()):
        elsewhere = "\n".join(v for kk, v in pack.items() if kk != k and kk.endswith((".mcfunction", ".json")))
        if n not in run_by_step and n not in set(re.findall(r"([a-z0-9_.-]+:[a-z0-9_./-]+)", elsewhere)):
            orphans.append(n)
    assert not orphans, orphans
    assert pack["data/minecraft/tags/function/load.json"].count("cobblers:tri_peaks_nest/load") == 1


def test_the_keeper_never_touches_a_guardian_and_the_pack_never_exempts_from_the_blackout(pack):
    for k, t in pack.items():
        if not k.endswith(".mcfunction"):
            continue
        assert "cobblers.gm" not in t, k
        for line in t.splitlines():
            if line.startswith("#"):
                continue
            if re.search(r"\bkill @e", line) or "run function cobblers:tri_peaks_nest/crownbreaker/hold" in line:
                assert "tag=!cobblers.guardian" in line, (k, line)
            assert not re.search(r"tag \S+ add cobblers\.guardian", line), (k, line)
    keep = pack["data/cobblers/function/tri_peaks_nest/crownbreaker/keep.mcfunction"]
    assert "advancements=" not in keep, "an ungated resident must not wait on a flag"
    assert "cobblers.tpn" in keep and "cobblers.res" not in keep.replace("cobblers.res_", "")


def test_it_spawns_a_level_35_tyranitar_that_can_be_caught(pack):
    spawn = pack["data/cobblers/function/tri_peaks_nest/crownbreaker/spawn.mcfunction"]
    assert 'species:"tyranitar"' in spawn and "level=35" in spawn and "uncatchable" not in spawn
    load = pack["data/cobblers/function/tri_peaks_nest/load.mcfunction"]
    assert "scoreboard players set #resp cobblers.tpn 72000" in load


def test_the_wake_faces_and_trigger_are_inside_the_leash(pack):
    hold = pack["data/cobblers/function/tri_peaks_nest/crownbreaker/hold.mcfunction"]
    assert "distance=..40" in hold and "distance=..30" in hold
    bind = pack["data/cobblers/function/tri_peaks_nest/crownbreaker/bind.mcfunction"]
    assert " -31.0 0" in bind
    # Minecraft yaw 0 faces +z; a negative yaw turns toward +x: the town is south-east of the crown
    towns = jload("towns.json")["towns"]
    c = next(t for t in towns if t.get("id") == "gym3_town")["centre"]
    yaw = -math.degrees(math.atan2(c["x"] - AX, c["z"] - AZ))
    assert abs(yaw - BUILD["yaw"]) < 1.0, yaw


# ------------------------------------------------------------------ the generator fails closed (mutate IT, not the record)


def test_a_wider_tooth_is_refused_because_it_leaves_the_recorded_box(doc, ground, monkeypatch):
    real = T.tor_blocks

    def wider(p, ax, az, salt):
        p = dict(p)
        p["radius"] = int(p["radius"]) + 3
        return real(p, ax, az, salt)
    monkeypatch.setattr(T, "tor_blocks", wider)
    mutated = T.load()
    with pytest.raises(RE.ResidentError):
        T.files(mutated, ground)


def test_a_ground_that_disagrees_with_the_record_is_refused(doc, ground):
    def lifted(x, z):
        return ground(x, z) + 1
    with pytest.raises(RE.ResidentError):
        T.files(doc, lifted)


def test_a_trigger_outside_the_leash_is_refused(tmp_path):
    bad = json.loads(T.DATA.read_text(encoding="utf-8"))
    bad["encounters"][0]["build"]["trigger"] = 60
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(T.NestError):
        T.load(p)


# ------------------------------------------------------------------ seen from below, and a walk up (this file's own code)


def _clear(ground, frm, to, to_y, eye=1.7):
    (fx, fz), (tx, tz) = frm, to
    fy = ground(fx, fz) + eye
    n = max(2, int(math.hypot(tx - fx, tz - fz) / 2))
    return min(fy + (to_y - fy) * i / n - ground(fx + (tx - fx) * i / n, fz + (tz - fz) * i / n) for i in range(1, n))


def _town():
    c = next(t for t in jload("towns.json")["towns"] if t.get("id") == "gym3_town")["centre"]
    return c["x"], c["z"]


def test_the_crowns_tallest_tooth_is_in_line_of_sight_of_the_town_and_the_end_of_route_3(ground, pack):
    sets, _ = _dress(pack)
    tip = max(sets, key=lambda k: k[1] - ground(k[0], k[2]))
    assert tip[1] - ground(tip[0], tip[2]) == 12
    top = (tip[0], tip[2]), tip[1] + 1
    m = _clear(ground, _town(), top[0], top[1])
    assert m > 0, "the town cannot see the crown (%.1f)" % m
    assert abs(m - RAW["design"]["measured"]["town_margin_to_tallest_tip_blocks"]) < 1.0
    r3 = jload("route_paths.json")["paths"]["route_03_misty_to_surge"]
    visible = [i for i in range(len(r3) - 160, len(r3)) if _clear(ground, tuple(r3[i]), top[0], top[1]) > 0]
    assert visible and visible[-1] == len(r3) - 1
    # the recorded 'final sight' starts within a few path points of where this recomputation puts it
    start = next(i for i in visible if all(j in visible for j in range(i, len(r3)) if j % 6 == 0))
    rec = RAW["design"]["measured"]["route_3_final_sight_path_points_to_town"]
    assert abs((len(r3) - start) - rec) <= 12, (len(r3) - start, rec)


def _astar(ground, start, goal, allowed=None):
    import numpy as np
    arr = np.rint(ground.heights).astype(int)
    ox, oz = ground.ox, ground.oz

    def hgt(x, z):
        return int(arr[z - oz, x - ox])
    pq, best, prev = [(0, 0, start)], {start: 0}, {}
    while pq:
        f, c, u = heapq.heappop(pq)
        if u == goal:
            break
        if c > best.get(u, 1e18):
            continue
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                v = (u[0] + dx, u[1] + dz)
                if v == u or not (1200 <= v[0] <= 1760 and 760 <= v[1] <= 1480):
                    continue
                if allowed is not None and v not in allowed:
                    continue
                dh = hgt(*v) - hgt(*u)
                if abs(dh) > 1:
                    continue
                nc = c + math.hypot(dx, dz) * (1.5 if dh > 0 else 1.0)
                if nc < best.get(v, 1e18):
                    best[v], prev[v] = nc, u
                    heapq.heappush(pq, (nc + math.hypot(goal[0] - v[0], goal[1] - v[1]), nc, v))
    if goal not in prev:
        return None
    p = [goal]
    while p[-1] != start:
        p.append(prev[p[-1]])
    return p[::-1]


def _stats(ground, p):
    return (round(sum(math.hypot(a[0] - b[0], a[1] - b[1]) for a, b in zip(p, p[1:]))),
            sum(max(0, ground(*b) - ground(*a)) for a, b in zip(p, p[1:])))


def test_a_player_can_walk_from_the_town_to_the_crown_and_up_the_scree_itself(ground, pack):
    """No step between adjacent columns over one block, so no block need be placed. Recomputed with this file's A*."""
    mw = RAW["design"]["measured"]
    p = _astar(ground, _town(), (AX, AZ))
    assert p, "no walkable path from the town to the crown"
    blocks, climb = _stats(ground, p)
    assert abs(blocks - mw["walk_town_to_crown"]["blocks"]) <= 12 and abs(climb - mw["walk_town_to_crown"]["climb"]) <= 8, (blocks, climb)
    sets, _ = _dress(pack)
    scree = {(x, z) for (x, y, z) in sets if y == ground(x, z) and z > AZ + 8}
    toe = max(scree, key=lambda c: c[1])
    q = _astar(ground, toe, (AX, AZ), allowed=scree | {(AX + i, AZ + j) for i in range(-8, 9) for j in range(-8, 9)})
    assert q, "the scree is not itself a walkable climb"
    blocks, climb = _stats(ground, q)
    assert abs(blocks - mw["walk_scree_toe_to_crown_inside_strip"]["blocks"]) <= 8, blocks


# ------------------------------------------------------------------ the re-application, the probes, the doc


def test_the_step_holds_exactly_the_recorded_box_and_runs_the_dress(doc, ground):
    steps = T.placement_steps(doc, ground)
    box = " ".join(str(v) for v in BOX)
    assert steps == [("cmd", "forceload add " + box), ("wait", 3), ("fn", "cobblers:tri_peaks_nest/crownbreaker/dress"),
                     ("cmd", "forceload remove " + box)]
    chunks = (BOX[2] // 16 - BOX[0] // 16 + 1) * (BOX[3] // 16 - BOX[1] // 16 + 1)
    assert chunks <= 64


def test_it_is_registered_where_its_neighbours_are():
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert src.count('"cobblers_tri_peaks_nest"') == 2         # SERVER_PACKS and the world-local list
    first, second = [m.start() for m in re.finditer(r'"cobblers_tri_peaks_nest"', src)]
    assert src.index("SERVER_PACKS = (") < first < second           # the pack list, then the world-local tuple
    assert src.rindex('"cobblers_far_south"', 0, second) > first     # the second sits with the other keepers
    assert 'add("tri_peaks_nest", "tri_peaks_nest.py", *src)' in src
    assert src.index('("R9FS"') < src.index('("R9TP"') < src.index('("R9E"')
    assert "tri_peaks_nest.placement_steps()" in src
    # no entity step: nothing in reapply summons it, so no chunk_look chain is owed
    assert "tri_peaks_nest.entity_steps" not in src


def test_the_probes_in_the_world_match_what_the_pack_writes(pack, ground):
    places = jload("world_probes.json")["places"]
    assert T.PROBE_KEY in places and len(places[T.PROBE_KEY]) >= 12
    sets, _ = _dress(pack)
    for pr in places[T.PROBE_KEY]:
        x, y, z, want = pr["block"]
        if want == "minecraft:air":
            assert (x, y, z) not in sets, pr
            assert y > ground(x, z), pr
        else:
            assert re.sub(r"\[.*\]$", "", sets.get((x, y, z), "")) == re.sub(r"\[.*\]$", "", want), pr
    # and the file still holds what tools/tri_peaks_nest.py probes would write (a stale probe set is a quiet failure)
    assert T.probes(T.load(), ground) == {T.PROBE_KEY: places[T.PROBE_KEY]}


def test_the_design_note_exists_and_names_the_step_and_the_pack():
    note = (ROOT / "docs" / "world-building" / "TRI_PEAKS_NEST.md").read_text(encoding="utf-8")
    for needle in ("R9TP", "cobblers_tri_peaks_nest", "Crownbreaker", "tools/tri_peaks_nest.py", "NOT verified"):
        assert needle in note, needle

"""tools/long_count.py's own guards, and the wiring of the Long Count (data/long_count.json) into the shared records.

These are the BUILDER'S tests (written 2026-10-09 by the agent that built the place): they prove that the generator's
fail-closed guards bite (each mutation edits a copy of the record and must make the build refuse), that the shipped
record builds, that every number a sign or Perrin states follows from the layout, and that the shared records
(data/quests.json, data/dialogue.json, data/progression.json, data/rewards.json, data/world_probes.json,
tools/reapply.py) say what the data says. They are NOT the independent audit: that is owed
(data/long_count.json audit_checklist), and whoever writes it must not import tools/long_count.py to derive anything.

What they do not prove: that the lane clears the wood, that the pole stands, that Perrin or the Grotle appear, that the
dialogue runs, or that the lantern is seen from Route 3. Nothing here was run in a game.
"""
from __future__ import annotations

import copy
import json
import math
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import long_count as LC  # noqa: E402

pytest.importorskip("numpy")


def jload(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def g():
    import ground as G
    import terrain
    try:
        return G.load()
    except terrain.TerrainUnavailable as e:  # the canonical heightmap lives outside the repo (data/notes/source_tree.md)
        pytest.skip("NOT_EXECUTED: no canonical heightmap here: %s" % e)


@pytest.fixture(scope="module")
def doc():
    return LC.load()


@pytest.fixture(scope="module")
def built(doc, g):
    out, sites = LC.files(doc, g)
    return out, sites


def _res(d):
    return d["residents"][0]


def _refused(d, g, needle):
    with pytest.raises(SystemExit) as e:
        LC.files(d, g)
    assert needle in str(e.value), str(e.value)[:900]


def _build_text(built):
    out, _ = built
    return out["data/cobblers/function/long_count/long_count/build.mcfunction"]


def _words(n):
    ones = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen " \
           "seventeen eighteen nineteen".split()
    tens = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
    if n < 20:
        return ones[n].capitalize()
    return (tens[n // 10] + ("-" + ones[n % 10] if n % 10 else "")).capitalize()


# ------------------------------------------------------------------ the shipped record


def test_the_shipped_record_builds_one_place_in_cell_c3(doc, built):
    out, sites = built
    assert len(sites) == 1
    r, s, extra, box = sites[0]
    assert r["cell"] == "C3"
    assert LC.cell_of(*r["site"]["centre"]) == "C3"
    assert box == r["bbox"]
    assert "data/cobblers/function/long_count/long_count/build.mcfunction" in out
    assert "data/cobblers/function/long_count/old_pace/bind_new.mcfunction" in out


def test_every_written_column_is_inside_cell_c3(doc, built):
    _, sites = built
    r, s, extra, box = sites[0]
    cb = LC.cell_box("C3")
    cols = set(s.cols) | {(c[0], c[2]) for c in s.clears} | {(c[3], c[5]) for c in s.clears}
    assert cols and all(cb["min_x"] <= x <= cb["max_x"] and cb["min_z"] <= z <= cb["max_z"] for x, z in cols)
    assert cb["min_x"] <= box[0] and box[2] <= cb["max_x"] and cb["min_z"] <= box[1] and box[3] <= cb["max_z"]


def test_the_forceload_box_is_under_the_servers_chunk_limit(doc, g):
    steps = LC.placement_steps(doc, g)
    hold = [a for k, a in steps if k == "cmd" and a.startswith("forceload add")][0].split()[2:]
    x0, z0, x1, z1 = (int(v) for v in hold)
    chunks = ((x1 >> 4) - (x0 >> 4) + 1) * ((z1 >> 4) - (z0 >> 4) + 1)
    assert 0 < chunks <= 256, chunks


def test_every_block_is_in_the_records_list_and_none_is_a_spawn_condition_or_concrete(doc):
    ids = set(doc["blocks"]["ids"])
    spawn = set(jload("spawn_blocks.json")["blocks"])
    assert not ids & spawn, sorted(ids & spawn)
    assert not any("concrete" in i for i in ids)
    assert "minecraft:oak_leaves" not in ids and "minecraft:chest" not in ids and not any(i.endswith("_bed") for i in ids)


def test_no_function_in_the_pack_is_orphaned(built):
    # every function is a step's or named by another file of the pack (the prepare's orphan gate, tools/reapply.py)
    out, _ = built
    names = {re.sub(r"^data/(\w+)/function/(.*)\.mcfunction$", r"\1:\2", k) for k in out if k.endswith(".mcfunction")}
    text = "\n".join(out.values())
    run = {"cobblers:long_count/long_count/build", "cobblers:long_count/old_pace/bind_new"}   # the steps'
    referenced = set(re.findall(r"cobblers:[a-z0-9_./]+", text)) | {"cobblers:long_count/load"}   # the load tag
    orphans = sorted(n for n in names if n not in run and n not in referenced)
    assert not orphans, orphans


# ------------------------------------------------------------------ the claims the place makes


def _stakes(built):
    """{year: (x, y, z)} of the year signs, read from the emitted build function and nothing else."""
    pat = re.compile(r"setblock (-?\d+) (-?\d+) (-?\d+) minecraft:oak_sign\[rotation=\d+,waterlogged=false\]"
                     r"\{front_text:\{messages:\['\"YEAR (\d+)\"'")
    return {int(m.group(4)): (int(m.group(1)), int(m.group(2)), int(m.group(3))) for m in pat.finditer(_build_text(built))}


def test_there_is_a_stake_for_every_year_from_13_down_to_0(built):
    st = _stakes(built)
    assert sorted(st) == list(range(14))


def test_the_line_points_at_the_world_tree_by_the_emitted_stakes(doc, built):
    st = _stakes(built)
    (x0, _, z0), (x13, _, z13) = st[0], st[13]
    # the walk goes from the year-0 hollow to the year-13 rest: that bearing against the bearing from the rest to the tree
    walk = math.degrees(math.atan2(x13 - x0, -(z13 - z0))) % 360
    tx, tz = doc["tree"]["centre"]
    to_tree = math.degrees(math.atan2(tx - x13, -(tz - z13))) % 360
    off = abs((walk - to_tree + 180) % 360 - 180)
    assert off <= 2.5, (walk, to_tree)
    # and the spacing is eight paces a year, measured on the stakes rather than read from the record
    for y in range(13):
        a, b = st[y], st[y + 1]
        assert abs(math.hypot(a[0] - b[0], a[2] - b[2]) - 8) <= 1.5, (y, a, b)


def test_the_tree_centre_is_the_world_trees(doc):
    import re as _re
    src = (ROOT / "tools" / "world_tree.py").read_text(encoding="utf-8")
    m = _re.search(r"CENTRE\s*=\s*\((\d+),\s*(\d+)\)", src)
    assert m and [int(m.group(1)), int(m.group(2))] == doc["tree"]["centre"]


def test_every_number_a_sign_states_follows_from_the_stakes(doc, built):
    st = _stakes(built)
    text = _build_text(built)
    ax, az = _res(doc)["pokemon"]["anchor"][0], _res(doc)["pokemon"]["anchor"][2]
    tx, tz = doc["tree"]["centre"]
    to_face = math.hypot(tx - ax, tz - az) - doc["tree"]["trunk_half_width"]
    years_to_tree = math.ceil(to_face / 8)
    assert years_to_tree == 22     # measured by hand from the anchor (2147, 2149) to the trunk face: 168.3 blocks
    assert '"%d YEARS"' % years_to_tree in text and '"13 YEARS"' in text and '"14 STAKES"' in text
    d = math.hypot(st[0][0] - st[13][0], st[0][2] - st[13][2])
    assert abs(d - 104) <= 3, d
    assert '"104 PACES"' in text


def test_perrins_numbers_are_the_layouts(doc):
    conv = next(c for c in jload("dialogue.json")["conversations"] if c["id"] == "dlg_long_count")
    lines = {n["id"]: n["text"] for n in conv["nodes"] if n["kind"] == "line"}
    f = LC.facts(doc, _res(doc))
    assert _words(f["years_to_tree"]) in lines["t002"]
    assert _words(f["years"]) in lines["k001"] and _words(f["paces_per_year"]) in lines["k001"]
    # "a hundred and seventy paces ... near enough": the trunk face is 168 from the rest
    assert "A hundred and seventy paces" in lines["t002"] and 165 <= f["grotle_to_trunk_face"] <= 175


def test_the_pole_is_the_tallest_thing_here(built):
    text = _build_text(built)
    cols = {}
    for m in re.finditer(r"^setblock (-?\d+) (\d+) (-?\d+) minecraft:stripped_spruce_log\[axis=y\]", text, re.M):
        cols.setdefault((m.group(1), m.group(3)), []).append(int(m.group(2)))
    assert cols, "no pole trunk"
    (px, pz), ys = max(cols.items(), key=lambda kv: len(kv[1]))
    base, top = min(ys), max(ys)
    assert ys and sorted(ys) == list(range(base, top + 1))          # one unbroken column
    lantern = re.search(r"^setblock %s (\d+) %s minecraft:lantern\[hanging=false" % (px, pz), text, re.M)
    assert lantern and int(lantern.group(1)) == top + 2             # a fence on the trunk, a lantern on the fence
    assert top - base + 1 >= 40      # the trunk alone is 40 blocks; the oldest tree is 8
    heights = _res(LC.load())["pieces"]
    tallest_tree = max(p["heights"] for p in heights if p["kind"] == "procession")
    assert max(tallest_tree) + 3 < top - base


def test_nothing_is_built_in_the_standing_room_of_perrin_or_the_grotle(doc, built):
    _, sites = built
    r, s, extra, box = sites[0]
    written = dict(s.solid)
    written.update(s.hung)
    for who, (x, y, z) in (("Perrin", r["npc"]["feet"]), ("the Grotle", r["pokemon"]["anchor"])):
        bad = [(x + dx, y + dy, z + dz, written[(x + dx, y + dy, z + dz)]) for dx in (-1, 0, 1) for dz in (-1, 0, 1)
               for dy in (0, 1) if (x + dx, y + dy, z + dz) in written and "air" not in written[(x + dx, y + dy, z + dz)]]
        assert not bad, (who, bad[:3])


def test_the_trees_grow_from_the_grotle_to_the_far_end(doc, built):
    _, sites = built
    r, s, extra, box = sites[0]
    line = s.floors["the line"]
    hs = [e["height"] for e in line]
    assert hs == sorted(hs) and hs[0] < hs[-1] and len(hs) == 14
    # the emitted trunks: one oak log column per tree, as tall as the record says, leaves not oak
    text = _build_text(built)
    assert "minecraft:oak_leaves" not in text and "minecraft:azalea_leaves" in text
    for e in line:
        x, gy, z = e["tree"]
        n = len(re.findall(r"(?:setblock %d \d+ %d|fill %d \d+ %d %d \d+ %d) minecraft:oak_log" % (x, z, x, z, x, z), text))
        assert n >= 1, e["year"]


# ------------------------------------------------------------------ siting, from other files


def test_the_centre_the_npc_the_anchor_and_the_cache_are_off_every_route_path(doc, g):
    import numpy as np
    paths = np.array([p for pl in jload("route_paths.json")["paths"].values() for p in pl], float)
    r = _res(doc)
    pts = [r["site"]["centre"], r["npc"]["feet"][::2], r["pokemon"]["anchor"][::2]]
    ca = jload("rewards.json")["rewards"]
    cache = next(x for x in ca if x["id"] == "long_count_first_oak")["container"]["at"]
    pts.append([cache[0], cache[2]])
    for x, z in pts:
        assert float(np.min(np.hypot(paths[:, 0] - x, paths[:, 1] - z))) >= 128, (x, z)


def _view_distance_chunks():
    txt = (ROOT / "server" / "config" / "server.properties.example").read_text(encoding="utf-8")
    return int(re.search(r"^view-distance=(\d+)", txt, re.M).group(1))


def test_the_pole_is_within_the_servers_view_distance_of_route_3_but_off_the_road(doc, g):
    """Seen from the road, measured: the server sends chunks within view-distance (10) of a player's chunk, and a thing
    outside them is only there if Distant Horizons has its LOD. The pole's lantern must be in the loaded window of some
    stretch of Route 3 AND in line of sight over the terrain and the world tree's trunk. The rules (96 from the route's
    corridor boxes) put every site about 150-160 from the path, so the window is narrow; this holds the place to the
    best the rules allow, not to a margin."""
    import numpy as np
    vd = _view_distance_chunks()
    r3 = np.array(jload("route_paths.json")["paths"]["route_03_misty_to_surge"], float)
    cx, cz = _res(doc)["site"]["centre"]
    d = float(np.min(np.hypot(r3[:, 0] - cx, r3[:, 1] - cz)))
    assert 128 <= d <= 175, d
    hint = _res(doc)["probe_hints"]["pole"]
    px, pz = cx + hint["trunk"][0], cz + hint["trunk"][1]
    top = g(px, pz) + 43          # the lantern, one above the fence on the 40-block trunk
    tx, tz = doc["tree"]["centre"]
    half = doc["tree"]["trunk_half_width"]

    def sees(p):
        x0, z0 = p
        y0 = g(x0, z0) + 2
        n = max(2, int(math.hypot(px - x0, pz - z0) / 3))
        for i in range(1, n):
            t = i / n
            x, z, y = x0 + (px - x0) * t, z0 + (pz - z0) * t, y0 + (top - y0) * t
            if g(x, z) > y or (abs(x - tx) <= half and abs(z - tz) <= half and y < 457):
                return False
        return True
    window = [p for p in r3 if abs(int(p[0]) // 16 - int(px) // 16) <= vd and abs(int(p[1]) // 16 - int(pz) // 16) <= vd]
    seen = [p for p in window if sees(p)]
    assert len(seen) >= 50, (len(window), len(seen))      # measured 99 path points when sited


def test_the_grotle_is_a_gym_two_gate_by_the_level_cap(doc):
    pk = _res(doc)["pokemon"]
    aces = jload("trainers.json")["generation_contract"]["gym_ace_levels"]
    assert pk["gate"] == "gym2_cleared" and pk["appears_after"] is None
    assert aces[1] < pk["level"] <= aces[2], (aces[:3], pk["level"])      # uncatchable at 1 badge, catchable at 2
    assert pk["species"] == "cobblemon:grotle" and pk["catch_rule"] == "catchable_after_gate"


def test_the_grotles_species_is_foothill_woods_own(doc):
    tbl = jload("encounter_design.json")["tables"]["foothill_woods"]
    assert "turtwig" in [s for s, _ in tbl["land"]] and tbl["tier"] == 3


def _jar():
    cands = [os.environ.get("COBBLERS_COBBLEMON_JAR"),
             "C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/Cobblemon-fabric-1.8.0+1.21.1.jar"]
    return next((c for c in cands if c and Path(c).is_file()), None)


def test_perrins_one_fact_about_pokemon_is_the_jars():
    jar = _jar()
    if not jar:
        pytest.skip("NOT_EXECUTED: no Cobblemon-fabric-1.8.0+1.21.1.jar here (COBBLERS_COBBLEMON_JAR)")
    sp = json.loads(zipfile.ZipFile(jar).read("data/cobblemon/species/generation4/grotle.json"))
    evo = {e["id"]: e for e in sp["evolutions"]}
    assert any(r.get("minLevel") == 32 for r in evo["grotle_torterra"]["requirements"])
    oak = evo["grotle_torterraoak"]
    assert any(r.get("itemCondition") == "minecraft:oak_sapling" for r in oak["requirements"])
    for item in ("growth_mulch", "miracle_seed", "oran_berry", "sitrus_berry"):
        assert "assets/cobblemon/models/item/%s.json" % item in zipfile.ZipFile(jar).namelist(), item


# ------------------------------------------------------------------ the generator's guards bite


def _mut(doc):
    return copy.deepcopy(doc)


def test_a_path_clearance_the_site_does_not_meet_is_refused(doc, g):
    d = _mut(doc)
    d["rules"]["path_clearance"] = 400
    _refused(d, g, "blocks from a route path (needs 400)")


def test_an_authored_clearance_the_site_does_not_meet_is_refused(doc, g):
    d = _mut(doc)
    d["rules"]["authored_clearance"] = 300
    _refused(d, g, "blocks from an x/z authored in data/")


def test_a_site_outside_its_cell_is_refused(doc, g):
    d = _mut(doc)
    d["rules"]["cell"] = "C4"
    _refused(d, g, "outside cell C4")


def test_a_line_that_misses_the_tree_is_refused(doc, g):
    d = _mut(doc)
    next(p for p in _res(d)["pieces"] if p["kind"] == "procession")["bearing"] = 95.0
    _refused(d, g, "the line walks toward bearing")


def test_a_wrong_tree_centre_is_refused(doc, g):
    d = _mut(doc)
    d["tree"]["centre"] = [2020, 2280]
    _refused(d, g, "doc.tree.centre must be the world tree's")


def test_a_level_over_the_places_ceiling_is_refused(doc, g):
    d = _mut(doc)
    _res(d)["pokemon"]["level"] = 40
    _refused(d, g, "over foothill_woods's tier-3 ceiling 35")


def test_a_spawn_condition_block_is_refused(doc, g):
    d = _mut(doc)
    d["blocks"]["ids"].append("minecraft:oak_leaves")
    next(p for p in _res(d)["pieces"] if p["kind"] == "procession")["leaves"] = "minecraft:oak_leaves[persistent=true]"
    _refused(d, g, "writes spawn-condition blocks")


def test_a_block_outside_the_list_is_refused(doc, g):
    d = _mut(doc)
    next(p for p in _res(d)["pieces"] if p["kind"] == "procession")["trunk"] = "minecraft:cherry_log[axis=y]"
    _refused(d, g, "is not in data/southern_residents.json blocks.ids")


def test_a_sign_that_names_a_number_the_generator_does_not_compute_is_refused(doc, g):
    d = _mut(doc)
    next(p for p in _res(d)["pieces"] if p["name"] == "the tally board")["blocks"][1][3]["sign"]["lines"][1] = "{nope} YEARS"
    _refused(d, g, "names {nope}")


def test_a_wrong_anchor_record_is_refused(doc, g):
    d = _mut(doc)
    a = list(_res(d)["pokemon"]["anchor"])
    a[1] += 1
    _res(d)["pokemon"]["anchor"] = a
    _refused(d, g, "the heightmap puts the anchor at")


def test_a_wrong_bbox_record_is_refused(doc, g):
    d = _mut(doc)
    b = list(_res(d)["bbox"])
    b[3] += 1
    _res(d)["bbox"] = b
    _refused(d, g, "the writes' box is")


def test_the_superseded_points_exception_is_the_nine_points_of_one_dead_record(doc, g):
    ex = doc["rules"]["superseded_points"]
    assert len(ex) == 1 and ex[0]["file"] == "towns.json"
    # the box is a footprint towns.json itself marks superseded, so the exception rests on that file, not on this one
    town = next(t for t in jload("towns.json")["towns"] if t["id"] == "gym3_town")
    dead = [h for h in town["site_history"] if h.get("from", {}).get("footprint") == ex[0]["corners_of"]]
    assert len(dead) == 1 and dead[0]["from"]["status"].startswith("superseded")
    assert len(LC.superseded_samples(doc)["towns.json"]) == 9
    # without it the lane's far end is refused: the exception is doing work, and only for those nine points
    d = _mut(doc)
    d["rules"]["superseded_points"] = []
    _refused(d, g, "blocks from an x/z authored in data/towns.json")


def test_a_trigger_outside_the_leash_is_refused(doc, tmp_path):
    d = _mut(doc)
    _res(d)["pokemon"]["trigger"] = 20
    f = tmp_path / "lc.json"
    f.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        LC.load(f)
    assert "the trigger must be inside the leash" in str(e.value)


def test_two_caches_are_refused(doc, tmp_path):
    d = _mut(doc)
    _res(d)["caches"].append(copy.deepcopy(_res(d)["caches"][0]))
    f = tmp_path / "lc.json"
    f.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        LC.load(f)
    assert "one cache" in str(e.value)


def test_a_site_on_water_is_refused(doc, g):
    # the whole site moved onto Lake Viltri (the dive portal dive_viltri_floor is at (1652, 2996)): the camp's clearing
    # is the first piece to meet a wet column, and a clear over water would drain it
    d = _mut(doc)
    _res(d)["site"]["centre"] = [1652, 2996]
    _refused(d, g, "the clearing has wet columns")


# ------------------------------------------------------------------ the steps


def test_the_steps_hold_the_bbox_and_summon_the_ungated_grotle(doc, g):
    r = _res(doc)
    bb = " ".join(str(v) for v in r["bbox"])
    steps = LC.placement_steps(doc, g)
    assert steps[0] == ("cmd", "forceload add " + bb) and steps[-1] == ("cmd", "forceload remove " + bb)
    assert ("fn", "cobblers:long_count/long_count/build") in steps
    ent = LC.entity_steps(doc, g)
    summon = next(a for k, a in ent if k == "cmd" and "spawnpokemonat" in a)
    assert "unless entity @e[type=cobblemon:pokemon,tag=cobblers.res.old_pace]" in summon and "grotle" in summon
    assert "level=29" in summon and "uncatchable" not in summon
    assert ("fn", "cobblers:long_count/old_pace/bind_new") in ent


def test_reapply_registers_the_pack_the_job_and_both_steps():
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert src.count('"cobblers_long_count"') == 2          # SERVER_PACKS and the world-local list
    assert 'add("long_count", "long_count.py", *src)' in src
    assert 'out.append(("R9LC"' in src and 'out.append(("R18LC"' in src
    assert src.index('out.append(("R9FS"') < src.index('out.append(("R9LC"') < src.index('out.append(("R9E"')
    assert src.index('out.append(("R18FS"') < src.index('out.append(("R18LC"')
    assert "long_count.placement_steps()" in src and "long_count.entity_steps()" in src
    # the keeper spawns Pokemon on its own: it is in the world-local tuple, which comes after SERVER_PACKS
    local = src[src.index('"cobblers_far_south",', src.index('"cobblers_far_south",') + 1):]
    assert '"cobblers_long_count"' in local[:1200]


# ------------------------------------------------------------------ the shared records


def test_the_quest_the_reward_and_the_cache_match_the_sites_spots(doc, built):
    _, sites = built
    r, s, extra, box = sites[0]
    q = next(x for x in jload("quests.json")["quests"] if x["id"] == "evt_long_count")
    feet = r["npc"]["feet"]
    assert q["npc_at"] == feet and q["dialogue_id"] == "dlg_long_count"
    rw = {x["id"]: x for x in jload("rewards.json")["rewards"]}
    grant = rw["long_count_thanks"]
    assert grant["kind"] == "npc_grant" and grant["npc_at"] == feet and grant["quest"] == "evt_long_count"
    cache = rw["long_count_first_oak"]
    cx, cy, cz = (int(v) for v in LC.SR.spot(s, r["caches"][0]["at"]))
    assert cache["kind"] == "cache" and cache["container"] == {"block": "minecraft:barrel", "at": [cx, cy - 1, cz]}
    lo, hi = cache["trigger"]["min"], cache["trigger"]["max"]
    assert all(a <= v <= b for a, v, b in zip(lo, (cx, cy, cz), hi))
    # a cache is only claimed by being there, so a player in the box stands on ground, not in a tree
    assert f"setblock {cx} {cy - 1} {cz} minecraft:barrel" in _build_text(built)


def test_the_progression_fields_cover_the_quest_and_the_cursor_covers_the_nodes():
    q = next(x for x in jload("quests.json")["quests"] if x["id"] == "evt_long_count")
    allf = {f["id"]: f for f in jload("progression.json")["quest_fields"]}
    for ref in q["progression_field_refs"]:
        assert ref in allf, ref
    conv = next(c for c in jload("dialogue.json")["conversations"] if c["id"] == "dlg_long_count")
    node_ids = {n["id"] for n in conv["nodes"]}
    cur = allf["quest.evt_long_count.dialogue_cursor"]
    assert set(cur["allowed_values"]) == node_ids      # every node is a place the cursor can rest
    assert cur["initial"] == conv["cursor"]["initial_node"]


def test_the_berry_is_shown_never_taken():
    q = next(x for x in jload("quests.json")["quests"] if x["id"] == "evt_long_count")
    show = next(t for t in q["transitions"] if t["id"] == "show_berry")
    kinds = [e["kind"] for e in show["effects"]]
    assert "consume_held_item" not in kinds and "grant_reward_once" in kinds
    assert {"kind": "held_item", "item_predicate": "cobblemon:sitrus_berry"} in show["conditions"]
    grant = next(e for e in show["effects"] if e["kind"] == "grant_reward_once")
    assert grant["claim_field"] == "quest.evt_long_count.reward_claimed"        # once per player
    r3 = next(x for x in jload("rewards.json")["rewards"] if x["id"] == "r3_world_tree_roots")
    assert "cobblemon:sitrus_berry" in [c["item"] for c in r3["contents"]]       # the berry she asks for is the roots'


def test_the_conversation_compiles(tmp_path):
    p = subprocess.run([sys.executable, str(ROOT / "tools" / "compile_dialogue.py"), "dlg_long_count", "--out", str(tmp_path)],
                       capture_output=True, text=True, cwd=str(ROOT))
    assert p.returncode == 0, p.stdout[-400:] + p.stderr[-400:]
    page = (tmp_path / "data" / "cobblers" / "dialogues" / "dlg_long_count.json").read_text(encoding="utf-8")
    assert "weapon.mainhand cobblemon:sitrus_berry" in page and "give @s cobblemon:growth_mulch 2" in page
    assert "item replace" not in page          # nothing is consumed
    assert (tmp_path / "data" / "cobblers" / "npcs" / "npc_long_count.json").is_file()


def test_the_world_probes_are_the_generators_and_each_block_probe_is_written_by_the_build(doc, g, built):
    wp = jload("world_probes.json")["places"]["long_count"]
    assert wp == LC.presence_probes(doc, g)["long_count"]
    text = _build_text(built)
    written = {}
    for m in re.finditer(r"^setblock (-?\d+) (-?\d+) (-?\d+) (\S+)", text, re.M):
        written[(int(m.group(1)), int(m.group(2)), int(m.group(3)))] = m.group(4)
    fills = [(tuple(int(v) for v in m.groups()[:6]), m.group(7)) for m in
             re.finditer(r"^fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (\S+)$", text, re.M)
             if "replace" not in m.group(7)]
    n = 0
    for pr in wp:
        if "block" not in pr:
            continue
        x, y, z, want = pr["block"]
        if want == "minecraft:air":
            continue
        base = want.split("[")[0]
        hit = written.get((x, y, z), "").split("[")[0].split("{")[0] == base or any(
            a[0] <= x <= a[3] and a[1] <= y <= a[4] and a[2] <= z <= a[5] and b.split("[")[0] == base for a, b in fills)
        assert hit, pr["what"]
        n += 1
    assert n >= 15


def test_probe_pack_has_a_lane_probe_per_gap_and_the_summon_probe():
    wp = jload("world_probes.json")["places"]["long_count"]
    assert sum(1 for p in wp if p.get("block", [0, 0, 0, ""])[3] == "minecraft:air") == 3
    ent = [p for p in wp if "entity" in p]
    assert len(ent) == 1 and "cobblers.res.old_pace" in ent[0]["entity"] and ent[0]["count"] == 1

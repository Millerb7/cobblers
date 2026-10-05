"""tools/fossil_dig.py, the Scorchbone Dig (data/fossil_dig.json): the builder's own tests.

These are the generator's tests, written by the agent that wrote the generator; they are NOT the independent audit
(docs/world-building/FOSSIL_DIG.md "What an audit must check" is the brief for that). Most run on synthetic ground (a
flat mesa and a tilted one) so they need no heightmap; the siting and the real seat need the canonical heightmap and
skip, naming it, when it is unusable. Where the Cobblemon jar is present the fossil tables are read from it.

NOT covered, and it needs a running server: that a setblock'd suspicious_gravel keeps its LootTable and brushes out a
fossil, that it turns to plain gravel, that the restore fires on approach, and that the foreman appears.
"""
import json
import re
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import fossil_dig as D  # noqa: E402

JAR = Path("C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/Cobblemon-fabric-1.8.0+1.21.1.jar")
DOC = D.load()


def flat(x, z):
    return 142


def tilted(x, z):
    return 140 + (x - 4140) // 20 + (z % 3 == 0)


@pytest.fixture(scope="module", params=[flat, tilted], ids=["flat", "tilted"])
def built(request):
    g = request.param
    out, pl = D.files(DOC, g)
    return g, out, pl


def _fn(out, name):
    return out["data/cobblers/function/fossil_dig/%s.mcfunction" % name].splitlines()


# ------------------------------------------------------------------------------------------- the record
def test_the_record_holds_no_spawn_condition_chest_or_bed():
    import wayside_kit as K
    assert K.unsafe_blocks(DOC["blocks"]["ids"], "fossil_dig") == {}


def test_no_light_block_water_or_bubble_column_is_in_the_palette():
    ids = set(DOC["blocks"]["ids"])
    assert not ids & {"minecraft:light", "minecraft:water", "minecraft:bubble_column", "minecraft:lava"}


def test_the_fifteen_tables_are_cobblemons_fossil_tag():
    items = {t["item"] for t in DOC["fossils"]["tables"]}
    assert len(items) == 15
    if not JAR.is_file():
        pytest.skip("NOT_EXECUTED: the Cobblemon jar is not at %s" % JAR)
    z = zipfile.ZipFile(str(JAR))
    assert items == set(json.loads(z.read("data/cobblemon/tags/item/fossils.json"))["values"])


def test_each_table_is_an_archaeology_table_that_drops_only_its_fossil():
    if not JAR.is_file():
        pytest.skip("NOT_EXECUTED: the Cobblemon jar is not at %s" % JAR)
    z = zipfile.ZipFile(str(JAR))
    for t in DOC["fossils"]["tables"]:
        ns, path = t["loot_table"].split(":")
        d = json.loads(z.read("data/%s/loot_table/%s.json" % (ns, path)))
        assert d["type"] == "minecraft:archaeology", t
        names = [e["name"] for p in d["pools"] for e in p["entries"]]
        assert names == [t["item"]], (t, names)


# ------------------------------------------------------------------------------------------- the plan
def test_every_seam_is_armed_exposed_supported_and_backed(built):
    g, _out, pl = built
    b = pl["blocks"]
    tables = {t["loot_table"] for t in DOC["fossils"]["tables"]}
    n = 0
    for f in pl["faces"]:
        dx, dz = D.SIDES[f["face"]["side"]]
        for s in f["seams"]:
            x, y, z = s["at"]
            n += 1
            m = re.fullmatch(r'minecraft:suspicious_gravel\{LootTable:"([^"]+)"\}', b[(x, y, z)])
            assert m and m.group(1) in tables, b[(x, y, z)]
            assert b[(x - dx, y, z - dz)] == D.AIR, "seam %s is not open to the pit" % (s["at"],)
            below = b[(x, y - 1, z)]
            assert below != D.AIR and D.K.base(below) not in D.GRAVITY, "seam %s stands on %s" % (s["at"], below)
            assert b.get((x + dx, y, z + dz), D.AIR) not in (D.AIR,), "seam %s has nothing behind it" % (s["at"],)
            assert y == pl["floors"][f["face"]["level"]] + 1
    assert n == sum(len(f["cells"]) for f in DOC["faces"]) == 12


def test_the_build_arms_twelve_different_fossils(built):
    _g, _out, pl = built
    got = [s["built_with"] for f in pl["faces"] for s in f["seams"]]
    assert len(set(got)) == len(got) == 12


def test_every_block_is_in_the_palette(built):
    _g, _out, pl = built
    ids = set(DOC["blocks"]["ids"])
    assert {D.K.base(s) for s in pl["blocks"].values()} <= ids


def test_the_cut_goes_down_from_the_top_and_the_walls_go_up_from_the_bottom(built):
    _g, out, _pl = built
    lines = _fn(out, "build")
    air = [int(l.split()[2]) for l in lines if l.startswith(("fill", "setblock")) and l.split()[-1] == "minecraft:air"
           and "replace" not in l]
    assert air == sorted(air, reverse=True), "an air write comes after a lower one: the sand over it would fall"
    first_solid = next(i for i, l in enumerate(lines) if l.startswith(("fill", "setblock")) and "minecraft:air" not in l)
    last_air = max(i for i, l in enumerate(lines) if l.startswith(("fill", "setblock")) and l.split()[-1] == "minecraft:air"
                   and "replace" not in l)
    assert last_air < first_solid


def test_the_foreman_stands_on_his_ground_in_two_blocks_of_air(built):
    g, _out, pl = built
    x, y, z = pl["npc"]
    assert y == g(x, z) + 1
    assert all(pl["blocks"].get((x, y + d, z), D.AIR) == D.AIR for d in (0, 1))


def test_each_level_can_be_walked_into_by_its_stairs(built):
    _g, _out, pl = built
    b = pl["blocks"]
    stairs = sorted(k for k, s in b.items() if s.startswith("minecraft:spruce_stairs"))
    assert stairs, "no stairs"
    ys = {k[1] for k in stairs}
    for lv, F0 in pl["floors"].items():
        if lv != "upper":
            assert F0 + 1 in ys and F0 + 2 in ys, "no stair run down to the %s level" % lv


# ------------------------------------------------------------------------------------------- the restore
def test_the_restore_writes_only_over_the_rearm_tag(built):
    _g, out, pl = built
    tag = "#cobblers:fossil_dig_rearm"
    for f in pl["faces"]:
        fid = f["face"]["id"]
        for l in _fn(out, "faces/restore_%s" % fid):
            if l.startswith("fill"):
                assert l.endswith("replace " + tag), l
        for k in range(len(f["seams"])):
            body = [l for l in _fn(out, "faces/seam_%s_%d" % (fid, k)) if not l.startswith("#")]
            x, y, z = f["seams"][k]["at"]
            assert body[0] == "execute unless block %d %d %d %s run return 0" % (x, y, z, tag)
            sets = [l for l in body if "setblock" in l]
            assert len(sets) == 15 and all(" setblock %d %d %d minecraft:suspicious_gravel{" % (x, y, z) in l for l in sets)
    rearm = json.loads(out["data/cobblers/tags/block/fossil_dig_rearm.json"])["values"]
    assert "minecraft:suspicious_gravel" not in rearm and "minecraft:gravel" in rearm


def test_a_face_is_restored_only_when_due_loaded_and_nobody_is_on_it(built):
    _g, out, pl = built
    for f in pl["faces"]:
        body = _fn(out, "faces/check_%s" % f["face"]["id"])
        assert any("< #period fd.t run return 0" in l for l in body)
        assert sum(1 for l in body if l.startswith("execute unless loaded")) == 4
        (x0, y0, z0, x1, y1, z1), vol = D._vol(f["bounds"], 1)
        assert "execute if entity @a[%s] run return 0" % vol in body
        assert "execute if entity @e[type=cobblemon:pokemon,%s] run return 0" % vol in body
        for (x, y, z) in list(f["wall"]) + [s["at"] for s in f["seams"]]:
            assert x0 <= x <= x1 and y0 <= y <= y1 and z0 <= z <= z1


def test_the_restore_puts_back_the_band_the_build_wrote(built):
    _g, _out, pl = built
    for f in pl["faces"]:
        for c, st in f["wall"].items():
            assert pl["blocks"][c] == st == D.strata(DOC, c[1])


def test_nothing_is_restored_before_the_build_and_the_period_is_respected(built):
    _g, out, _pl = built
    drive = _fn(out, "drive")
    assert "execute unless score #built fd.t matches 1 run return 0" in drive
    build = _fn(out, "build")
    writes = [i for i, l in enumerate(build) if l.startswith(("fill", "setblock"))]
    assert build.index("scoreboard players set #built fd.t 1") > max(writes)
    assert DOC["restore"]["period_ticks"] >= 12000


def test_the_pack_runs_its_load_and_tick():
    _out, _pl = D.files(DOC, flat)
    assert json.loads(_out["data/minecraft/tags/function/tick.json"])["values"] == ["cobblers:fossil_dig/tick"]
    assert json.loads(_out["data/minecraft/tags/function/load.json"])["values"] == ["cobblers:fossil_dig/load"]


# ------------------------------------------------------------------------------------------- the world and the record
@pytest.fixture(scope="module")
def ground():
    import ground as G
    import terrain as T
    try:
        return G.load()
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)


def test_the_dig_is_sited_clear_of_paths_places_and_nests(ground):
    pl = D.plan(DOC, ground)
    probs, near = D.siting(DOC, pl, ground)
    assert probs == [], probs
    assert near["route_path"][0] >= DOC["site"]["keep_clear"]["path_clearance"]


def test_the_foremans_seat_is_the_spot_the_plan_leaves_open(ground):
    pl = D.plan(DOC, ground)
    assert D.seat_problems(DOC, pl) == []


def test_a_seat_off_the_plans_spot_is_refused(ground, monkeypatch):
    pl = D.plan(DOC, ground)
    x, y, z = pl["npc"]
    pl = dict(pl, npc=(x + 1, y, z))
    assert any("plan leaves" in p for p in D.seat_problems(DOC, pl))


def test_the_site_reads_the_ground_the_record_states(ground):
    cx, cz = DOC["site"]["centre"]
    assert ground(cx, cz) == 142
    pl = D.plan(DOC, ground)
    assert pl["floors"] == {"upper": 140, "middle": 138, "bed": 136}


def test_the_conversation_compiles_and_its_cursor_names_every_node():
    import compile_dialogue as CD
    d, quests, fields = CD.load(ROOT / "data")
    conv = next(c for c in d["conversations"] if c["id"] == DOC["npc"]["conversation"])
    CD.compile_conversation(conv, quests, fields)
    prog = json.loads((ROOT / "data" / "progression.json").read_text(encoding="utf-8"))
    field = next(f for v in prog.values() if isinstance(v, list) for f in v
                 if isinstance(f, dict) and f.get("id") == conv["cursor"]["progression_field"])
    assert field["allowed_values"] == [n["id"] for n in conv["nodes"]]


def test_the_foreman_points_at_the_brush_and_the_machine():
    d = json.loads((ROOT / "data" / "dialogue.json").read_text(encoding="utf-8"))
    conv = next(c for c in d["conversations"] if c["id"] == DOC["npc"]["conversation"])
    text = " ".join(n["text"] for n in conv["nodes"])
    for w in ("brush", "Fossil Analyzer", "Restoration Tank", "Monitor", "amethyst", "Revive"):
        assert w in text, w

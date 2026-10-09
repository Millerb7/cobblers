"""tools/rookery.py's own guards, and the facts Gull Rock rests on (data/rookery.json).

These are the BUILDER'S tests (2026-10-09): they prove that the generator's fail-closed guards bite (each mutation edits
a copy of the record, or the generator itself, and must make the build refuse), that the shipped record builds, that the
records in the three shared files are the ones the generator writes, and that the numbers the record states are the
heightmap's and the jar's. They are NOT the independent audit (data/rookery.json audit_checklist): whoever writes that
must not import tools/rookery.py to derive anything.
"""
from __future__ import annotations

import copy
import glob
import json
import re
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import rookery as RK  # noqa: E402

np = pytest.importorskip("numpy")
JARS = glob.glob("C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/Cobblemon-fabric-*.jar")


def jl(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def g():
    import ground as G
    try:
        return G.load()
    except Exception as e:  # the canonical heightmap lives outside the repo (data/notes/source_tree.md)
        pytest.skip("no canonical heightmap here: %s" % e)


@pytest.fixture(scope="module")
def doc():
    return RK.load()


@pytest.fixture(scope="module")
def built(doc, g):
    return RK.files(doc, g)


@pytest.fixture(scope="module")
def sea(g):
    import terrain as T
    return int(T.sea_level(g.world))


def _refused(d, g, needle):
    with pytest.raises(SystemExit) as e:
        RK.files(d, g)
    assert needle in str(e.value), str(e.value)[:600]


# ------------------------------------------------------------------ the shipped record


def test_the_shipped_record_builds_a_stack_six_rocks_and_a_keeper(doc, built):
    out, m = built
    assert len(m.skerries) == 6 == doc["skerries"]["count"]
    assert len(m.blocks) > 5000 and len(m.stack_cols) > 150          # a real stack, not a token one
    base = "data/cobblers/function/rookery/"
    for f in ("build", "load", "keeper", "spawn_at", "gullmother/keep", "gullmother/hold", "gullmother/wake",
              "gullmother/settle", "gullmother/spawn", "gullmother/bind", "gullmother/bind_new"):
        assert base + f + ".mcfunction" in out, f
    assert "rookery/gullmother/keep" in out[base + "keeper.mcfunction"]
    assert json.loads(out["data/minecraft/tags/function/load.json"])["values"] == ["cobblers:rookery/load"]


def test_every_function_of_the_pack_is_run_by_a_step_or_named_by_another(doc, g, built):
    out, _ = built
    names = {re.sub(r"^data/([^/]+)/function/(.+)\.mcfunction$", r"\1:\2", k) for k in out if k.endswith(".mcfunction")}
    run = {v for k, v in RK.placement_steps(doc, g) + RK.entity_steps(doc, g) if k == "fn"}
    text = "\n".join(v for k, v in out.items())
    named = set(re.findall(r"function ([a-z0-9_.-]+:[a-z0-9_./-]+)", text)) | set(re.findall(r"([a-z0-9_.-]+:[a-z0-9_./-]+)\"", text))
    macro = {"cobblers:rookery/spawn_at"}                                 # called as `function <ns>:<f>/spawn_at {...}`
    orphans = sorted(n for n in names if n not in run and n not in named and n not in macro and not n.endswith("/dress"))
    assert not orphans, orphans


def test_the_steps_hold_build_release_and_hold_summon_bind_release(doc, g):
    p = RK.placement_steps(doc, g)
    assert [k for k, _v in p] == ["cmd", "wait", "fn", "cmd"] and p[2][1] == "cobblers:rookery/build"
    assert p[0][1].startswith("forceload add ") and p[3][1] == p[0][1].replace("add", "remove")
    e = RK.entity_steps(doc, g)
    assert [k for k, _v in e] == ["cmd", "wait", "cmd", "wait", "fn", "cmd"]
    summon = e[2][1]
    assert "tag=cobblers.res.gullmother" in summon and "spawnpokemonat" in summon and "dragonite" in summon   # the guard names tag AND species
    assert "level=55" in summon and e[4][1] == "cobblers:rookery/gullmother/bind_new"


def test_reapply_registers_the_steps_the_pack_and_the_world_local_list():
    text = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert text.index('"R9FS"') < text.index('"R9RK"') < text.index('("R9E"')
    assert text.index('"R18FS"') < text.index('"R18RK"')
    server = text[text.index("SERVER_PACKS = ("):text.index("EXCLUDED = {")]
    world_local = text[text.index("WORLD_LOCAL = ("):text.index("SPAWN_PACKS = (")]
    assert '"cobblers_rookery"' in server and '"cobblers_rookery"' in world_local
    assert 'add("rookery", "rookery.py", *src)' in text
    excluded = text[text.index("EXCLUDED = {"):text.index("WORLD_LOCAL = (")]
    assert "cobblers_rookery" not in excluded


# ------------------------------------------------------------------ the facts the record states


def test_every_written_column_is_under_the_sea_by_the_heightmap_alone(built, g, sea):
    # independent of Wet/water_mask: the heightmap's own bed is below the sea level at every column the rock stands on
    _, m = built
    dry = [c for c in m.top if g(*c) >= sea]
    assert not dry, dry[:5]
    x0, z0, x1, z1 = (6144, 2048, 7167, 3071)                     # cell C7, data/cells.json
    assert all(x0 <= x <= x1 and z0 <= z <= z1 for x, z in m.top)


def test_the_stack_is_far_from_land_and_the_swim_is_short(built, g, sea):
    _, m = built
    cx, cz = m.cx, m.cz
    land = [x for x in range(cx, cx - 300, -1) if g(x, cz) > sea]
    shore = land[0]
    foot = min(x for x, z in m.stack_cols if z == cz)
    assert foot - shore > 80                                       # a swim, not a wade
    deep = next(x for x in range(shore, cx) if sea - g(x, cz) >= 2)
    assert foot - deep <= 75, foot - deep                           # under the unaided limit (about 75 blocks, STATE surface exhaustion)
    nearest_rock = min(x for s in m.skerries for x, z in s["cols"] if abs(z - cz) < 14)
    assert nearest_rock - deep <= 40


def test_the_birds_are_in_sight_of_the_moor(built, g):
    # the head of the Gullmother (the crown + 1 + 3) is seen from the moor's edge 400 blocks inland: terrain only, along z
    _, m = built
    head = m.crown + 4
    x = m.cx - 380
    eye = g(x, m.cz) + 1.62
    for i in range(1, 200):
        t = i / 200.0
        assert g(int(round(x + (m.cx - x) * t)), m.cz) <= eye + (head - eye) * t + 0.01 or t > 0.96, (i, t)


def test_the_crown_plate_holds_the_gullmother_with_air_over_her(doc, built):
    _, m = built
    ax, ay, az = m.anchor
    assert doc["residents"][0]["pokemon"]["anchor"] == [ax, ay, az]
    assert m.blocks[(ax, ay - 1, az)] == "minecraft:calcite"
    assert not any((ax, ay + j, az) in m.blocks for j in range(4))
    assert ay - 1 - m.sea == doc["stack"]["crown_over_sea"]


def test_the_nest_rule_holds_for_this_nests_own_blocks_and_every_other_activated_block(doc):
    pk = doc["residents"][0]["pokemon"]
    ax, az = doc["residents"][0]["site"]["centre"]
    blocks = [b for b in jl("habitat_blocks.json")["blocks"] if b.get("style") == "activated"]
    own = [b for b in blocks if b["id"].startswith(RK.HABITAT_PREFIX)]
    assert len(own) == 6
    for b in blocks:
        import math
        d = math.hypot(b["position"]["x"] - ax, b["position"]["z"] - az)
        assert d >= b["activated"]["spawn_range"] + pk["leash"], (b["id"], d)
    assert min(math.hypot(b["position"]["x"] - ax, b["position"]["z"] - az) for b in own) >= 32


def test_the_level_gate_is_the_level_cap_and_the_colony_is_under_the_cap_at_five_badges(doc):
    aces = jl("trainers.json")["generation_contract"]["gym_ace_levels"]
    pk = doc["residents"][0]["pokemon"]
    cap_at = lambda badges: aces[badges]                           # 0 badges -> gym 1's ace, 7 badges -> gym 8's ace
    assert pk["level"] == cap_at(7) == 55 and pk["gate"] == "gym7_cleared"
    assert doc["colony"]["level_band"]["maximum"] <= cap_at(5) == 45
    assert pk["level"] > cap_at(6) and pk["appears_after"] is None  # early is a mistake, and she is there from the start
    hearts = jl("encounter_design.json")["rules"]["hearts"]["next_cap"]
    assert pk["level"] <= hearts["7"]                               # tier 7's ceiling, the eastern moor's
    assert jl("encounter_design.json")["tables"]["eastern_moor"]["tier"] == 7
    assert "gym7_cleared" in {f["id"] for f in jl("progression.json")["flags"]}


@pytest.mark.skipif(not JARS, reason="no Cobblemon 1.8.0 jar in the local snapshot")
def test_the_jar_agrees_with_the_record_on_dragonair_the_hitbox_and_the_roster():
    z = zipfile.ZipFile(JARS[0])
    sp = lambda g_, n: json.loads(z.read("data/cobblemon/species/generation%d/%s.json" % (g_, n)))
    evo = sp(1, "dragonair")["evolutions"]
    assert any(e["result"] == "dragonite" and any(r.get("minLevel") == 55 for r in e["requirements"]) for e in evo)
    assert sp(1, "dragonite")["hitbox"]["height"] == 3.2             # the four blocks of air over the anchor
    lang = json.loads(z.read("assets/cobblemon/lang/en_us.json"))
    assert "leads lost and foundering ships in a storm" in lang["cobblemon.species.dragonite.desc"]
    doc = RK.load()
    lo = doc["colony"]["level_band"]["minimum"]
    names = z.namelist()
    for ro in doc["colony"]["roster"]:
        f = next(n for n in names if n.endswith("/species/%s.json" % ro["pokemon"]) or ("/species/" in n and n.endswith("/%s.json" % ro["pokemon"])))
        for e in json.loads(z.read(f)).get("evolutions", []):
            levels = [r.get("minLevel") for r in e["requirements"] if r.get("variant") == "level"]
            assert not levels or min(levels) > doc["colony"]["level_band"]["maximum"], (ro["pokemon"], levels)
    for pre, at in (("wingull", 25), ("wattrel", 25), ("ducklett", 35), ("swablu", 35)):
        f = next(n for n in names if "/species/" in n and n.endswith("/%s.json" % pre))
        assert at < lo and any(r.get("minLevel") == at for e in json.loads(z.read(f))["evolutions"] for r in e["requirements"]), pre


# ------------------------------------------------------------------ the shared records are the generator's

def test_the_records_in_the_shared_files_are_the_ones_the_generator_writes(doc, built):
    _, m = built
    habs = {b["id"]: b for b in jl("habitat_blocks.json")["blocks"] if b["id"].startswith(RK.HABITAT_PREFIX)}
    want = {b["id"]: b for b in RK.habitat_records(doc, m)}
    assert len(want) == 6 and habs == want
    sp = jl("spawns.json")
    pool = RK.pool_records(doc, sp)
    assert [h for h in sp["habitats"] if h["id"] == doc["colony"]["pool"]] == [pool["habitat"]]
    assert [e for e in sp["entries"] if e.get("scope") == doc["colony"]["pool"]] == pool["entries"]
    assert len(pool["entries"]) == len(doc["colony"]["roster"]) == 6
    assert all(e["level"] == "36-44" and e["ambient"] for e in pool["entries"])
    assert {b["pool"] for b in habs.values()} == {"cobblers:" + doc["colony"]["pool"]}


def test_the_presence_probes_in_world_probes_are_the_generators(doc, built):
    _, m = built
    want = RK.presence_probes(doc, m)
    assert jl("world_probes.json")["places"][RK.PROBE_KEY] == want[RK.PROBE_KEY]
    rows = want[RK.PROBE_KEY]
    assert len(rows) >= 20 and sum(1 for r in rows if "entity" in r) == 1
    for r in rows:
        assert ("block" in r and len(r["block"]) == 4) or ("entity" in r and r["count"] == 1 and len(r["hold"]) == 3)
    assert any(r.get("block", [0, 0, 0, ""])[3] == "cobblemon:habitat_block" for r in rows)


def test_a_probe_block_is_the_block_the_pack_writes(doc, built):
    out, m = built
    build = out["data/cobblers/function/rookery/build.mcfunction"]
    for r in RK.presence_probes(doc, m)[RK.PROBE_KEY]:
        if "block" in r and r["block"][3] not in ("minecraft:air", "minecraft:water", "cobblemon:habitat_block"):
            x, y, z, st = r["block"]
            assert m.blocks[(x, y, z)].startswith(st.split("[")[0]), r
    assert build.count("fill ") + build.count("setblock ") == len([l for l in build.splitlines() if l and not l.startswith("#")])


def test_the_pack_writes_nothing_a_spawn_condition_or_gravity_would_object_to(built):
    out, m = built
    spawn = set(jl("spawn_blocks.json")["blocks"])
    used = {RK.base(v) for v in m.blocks.values()}
    assert not used & spawn, used & spawn
    assert not [b for b in used if any(b.endswith(x) for x in RK.GRAVITY)]


# ------------------------------------------------------------------ the guards bite (each mutation must be refused)


def test_a_ring_inside_the_nest_rule_is_refused_on_load(tmp_path, doc):
    d = copy.deepcopy(doc)
    d["skerries"]["ring_radius"] = 30
    p = tmp_path / "r.json"
    p.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        RK.load(p)
    assert "spawn_range + leash" in str(e.value)


def test_a_colony_over_the_cap_at_five_badges_is_refused_on_load(tmp_path, doc):
    d = copy.deepcopy(doc)
    d["colony"]["level_band"]["maximum"] = 46
    p = tmp_path / "r.json"
    p.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        RK.load(p)
    assert "at most 45" in str(e.value)


def test_a_gravity_block_is_refused_on_load(tmp_path, doc):
    d = copy.deepcopy(doc)
    d["blocks"]["ids"].append("minecraft:gravel")
    p = tmp_path / "r.json"
    p.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        RK.load(p)
    assert "gravity" in str(e.value)


def test_a_palette_block_outside_the_allow_list_is_refused_on_load(tmp_path, doc):
    d = copy.deepcopy(doc)
    d["stack"]["guano"]["palette"].append(["minecraft:white_wool", 1])
    p = tmp_path / "r.json"
    p.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        RK.load(p)
    assert "outside blocks.ids" in str(e.value)


def test_a_trigger_outside_the_leash_is_refused_on_load(tmp_path, doc):
    d = copy.deepcopy(doc)
    d["residents"][0]["pokemon"]["trigger"] = 20
    p = tmp_path / "r.json"
    p.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(SystemExit):
        RK.load(p)


def test_a_stack_moved_onto_the_beach_is_refused(doc, g):
    d = copy.deepcopy(doc)
    d["residents"][0]["site"]["centre"] = [6850, 2650]        # the sea's edge: the rock stands on the sand
    with pytest.raises(SystemExit) as e:
        RK.files(d, g)
    assert "dry" in str(e.value) or "not water" in str(e.value)


def test_a_stack_moved_onto_the_ferry_line_is_refused(doc, g):
    d = copy.deepcopy(doc)
    d["rules"]["ferry_clearance"] = 600                        # the stack is 442 from the Northlight packet
    _refused(d, g, "ferry crossing")


def test_a_level_over_the_ceiling_is_refused(doc, g):
    d = copy.deepcopy(doc)
    d["residents"][0]["pokemon"]["level"] = 56
    _refused(d, g, "ceiling")


def test_an_anchor_the_heightmap_disagrees_with_is_refused(doc, g):
    d = copy.deepcopy(doc)
    d["residents"][0]["pokemon"]["anchor"] = [6940, 84, 2650]
    _refused(d, g, "the heightmap puts the anchor")


def test_a_site_too_near_authored_ground_is_refused(doc, g):
    d = copy.deepcopy(doc)
    d["rules"]["authored_clearance"] = 400
    _refused(d, g, "blocks from an x/z authored")


def test_a_cell_box_the_rock_leaves_is_refused(doc, g):
    d = copy.deepcopy(doc)
    d["rules"]["cell_box"] = [6144, 2048, 6950, 3071]
    _refused(d, g, "outside cell")


def test_a_habitat_block_inside_the_leash_is_refused(doc, g, monkeypatch):
    # the GENERATOR, not the record: put every block 4 nearer the stack and the nest rule must catch it
    real = RK.Model._skerry

    def nearer(self, k):
        s = real(self, k)
        hx, hy, hz = s["habitat"]
        s["habitat"] = (self.cx + (hx - self.cx) // 2, hy, self.cz + (hz - self.cz) // 2)
        return s
    monkeypatch.setattr(RK.Model, "_skerry", nearer)
    with pytest.raises(SystemExit) as e:
        RK.files(doc, g)
    assert "needs 32" in str(e.value) or "not in its rock" in str(e.value)


def test_a_generator_that_scaled_the_ring_onto_the_shore_is_refused(doc, g, monkeypatch):
    # mutate the GENERATOR and leave the record alone: a ring scaled 80 blocks too wide puts the beach rock on the sand
    real = RK.Model._skerry

    def wide(self, k):
        saved = self.doc["skerries"]["ring_radius"]
        self.doc["skerries"]["ring_radius"] = saved + 80
        try:
            return real(self, k)
        finally:
            self.doc["skerries"]["ring_radius"] = saved
    monkeypatch.setattr(RK.Model, "_skerry", wide)
    with pytest.raises(SystemExit) as e:
        RK.files(doc, g)
    assert "not water" in str(e.value) or "outside cell" in str(e.value) or "dry" in str(e.value), str(e.value)[:400]


def test_a_gullmother_that_returns_inside_an_hour_is_refused_on_load(tmp_path, doc):
    d = copy.deepcopy(doc)
    d["build"]["respawn_ticks"] = 36000
    p = tmp_path / "r.json"
    p.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        RK.load(p)
    assert "a farm" in str(e.value)


def test_the_load_function_sets_the_shipped_respawn_clock(doc, built):
    out, _ = built
    load = out["data/cobblers/function/rookery/load.mcfunction"]
    assert "scoreboard players set #resp cobblers.rkres %d" % doc["build"]["respawn_ticks"] in load
    assert doc["build"]["respawn_ticks"] == 144000

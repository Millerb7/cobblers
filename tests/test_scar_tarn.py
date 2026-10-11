"""tools/scar_tarn.py: the Scar Tarn (data/scar_tarn.json).

The BUILDER's tests, written by the agent that wrote the generator: they hold the plan to the brief and to the shared data,
recomputing what they can from the heightmap and from the EMITTED FUNCTION (a replay of build.mcfunction over a world made
of the heightmap alone) rather than from the plan's own tables. They are not the independent audit
(docs/world-building/SCAR_TARN.md, "What an audit must check").

Needs the canonical heightmap; a skip names it. NOT covered, and it needs a running server: that the fills land, that the
tarn holds its water in game (and whether the cold biome freezes its surface), that the four activated Habitat Blocks keep
their pools alive, that the pool entry's `modifiers` ("alpha=true") makes the spawn an alpha, what the alpha level-matching
sensor does to the authored 29-33, and how any of it looks.
"""
import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import function_limits  # noqa: E402
import scar_tarn as ST  # noqa: E402


def _load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


DOC = ST.load()
YS = DOC["pond"]["water_level"]


@pytest.fixture(scope="module")
def ground():
    import ground as G
    import terrain as T
    try:
        return G.load()
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)


@pytest.fixture(scope="module")
def pl(ground):
    return ST.plan(DOC, ground)


@pytest.fixture(scope="module")
def built(pl):
    return ST.files(pl=pl)


NUM = r"(-?\d+)"
SET = re.compile(r"^setblock %s %s %s (\S+)( keep)?$" % ((NUM,) * 3))
FILL = re.compile(r"^fill %s %s %s %s %s %s (\S+)( keep| replace minecraft:snow)?$" % ((NUM,) * 6))


def replay(text, ground):
    """{(x, y, z): state} the function leaves, over a world that is the heightmap's ground and air: a replace write sets a
    cell, a keep write sets an air cell only, a snow-filtered fill touches nothing (the base has no snow)."""
    w = {}

    def air(x, y, z):
        return (x, y, z) not in w and y > ground(x, z)

    for line in text.splitlines():
        if not line or line.startswith("#") or line.startswith("forceload"):
            continue
        m = SET.match(line)
        if m:
            x, y, z = (int(m.group(i)) for i in (1, 2, 3))
            if m.group(5) and not air(x, y, z):
                continue
            w[(x, y, z)] = m.group(4)
            continue
        m = FILL.match(line)
        assert m, "an unreadable command: %r" % line
        x0, y0, z0, x1, y1, z1 = (int(m.group(i)) for i in range(1, 7))
        mode = (m.group(8) or "").strip()
        if mode.startswith("replace"):
            continue
        for x in range(min(x0, x1), max(x0, x1) + 1):
            for y in range(min(y0, y1), max(y0, y1) + 1):
                for z in range(min(z0, z1), max(z0, z1) + 1):
                    if mode == "keep" and not air(x, y, z):
                        continue
                    w[(x, y, z)] = m.group(7)
    return w


def fn_text(built):
    out, _pl = built
    return out["data/cobblers/function/scar_tarn/build.mcfunction"]


def leaks(w, ground, drop):
    """Water cells in a replayed world with an open side or floor; unwritten cells are solid at or under ground - drop."""
    def solid(c):
        st = w.get(c)
        if st is not None:
            return ST.base(st) not in ST.NOT_SOLID
        return c[1] <= ground(c[0], c[2]) - drop
    bad = []
    for (x, y, z), st in w.items():
        if st != ST.WATER:
            continue
        for n in ((x + 1, y, z), (x - 1, y, z), (x, y, z + 1), (x, y, z - 1), (x, y - 1, z)):
            if w.get(n) == ST.WATER or solid(n):
                continue
            bad.append(((x, y, z), n))
    return bad


# ------------------------------------------------------------------ the record


def test_the_record_names_the_owners_ask_and_the_subregion_it_stands_in():
    assert "recessed point" in DOC["owner"] and "alpha mons" in DOC["owner"]
    sub = [s for s in _load("spawns.json")["subregions"] if s["id"] == DOC["place"]["subregion"]]
    assert sub and sub[0]["level_band"]["tier"] == 3


def test_the_alpha_band_is_over_the_tables_top_and_under_the_next_cap():
    lo, hi = DOC["alphas"]["band"]
    sub = [s for s in _load("spawns.json")["subregions"] if s["id"] == DOC["place"]["subregion"]][0]
    nxt = _load("encounter_design.json")["rules"]["hearts"]["next_cap"][str(sub["level_band"]["tier"])]
    assert sub["level_band"]["maximum"] < lo <= hi < nxt, (sub["level_band"], lo, hi, nxt)


def test_every_alpha_species_has_evolved_to_its_stage_by_the_band_and_is_a_real_species():
    import zipfile
    jar = Path("C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/Cobblemon-fabric-1.8.0+1.21.1.jar")
    if not jar.is_file():
        pytest.skip("the Cobblemon 1.8.0 jar snapshot is not on this machine")
    z = zipfile.ZipFile(jar)
    names = z.namelist()
    lo = DOC["alphas"]["band"][0]
    for spec in DOC["alphas"]["pools"].values():
        for e in spec["entries"]:
            hit = [n for n in names if "/species/" in n and n.endswith("/%s.json" % e["species"])]
            assert hit, "%s is not a species in the jar" % e["species"]
            pre = json.loads(z.read(hit[0])).get("preEvolution")
            if pre:
                pre_hit = [n for n in names if "/species/" in n and n.endswith("/%s.json" % pre)][0]
                evo = [x for x in json.loads(z.read(pre_hit)).get("evolutions", []) if x.get("result") == e["species"]]
                lv = [r.get("minLevel") for x in evo for r in x.get("requirements", []) if r.get("variant") == "level"]
                assert all(v is not None and v <= lo for v in lv), (e["species"], lv, lo)


# ------------------------------------------------------------------ the hollow and the water


def test_the_pond_is_the_set_the_heightmap_gives_under_the_water_level(pl, ground):
    """Recomputed here from the heightmap alone: the 4-connected columns under y(level) from the seed."""
    sx, sz = DOC["pond"]["seed"]
    seen = {(sx, sz)}
    st = [(sx, sz)]
    while st:
        x, z = st.pop()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, z + dz)
            if n not in seen and ground(*n) <= YS - 1:
                seen.add(n)
                st.append(n)
    assert seen == pl.W and 1000 <= len(seen) <= 4000


def test_the_hollow_spills_no_lower_than_two_blocks_over_the_water(ground):
    """Water at y239 from the seed stays inside the hollow (measured: the fill level) and at y240 it escapes."""
    def escapes(level):
        sx, sz = DOC["pond"]["seed"]
        seen = {(sx, sz)}
        st = [(sx, sz)]
        while st:
            x, z = st.pop()
            if not (1900 <= x <= 2140 and 620 <= z <= 810):
                return True
            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (x + dx, z + dz)
                if n not in seen and ground(*n) <= level - 1:
                    seen.add(n)
                    st.append(n)
        return False
    assert not escapes(YS + 2) and escapes(YS + 3)


def test_the_replayed_function_holds_its_water_at_the_heightmap_and_one_block_under_it(built, ground):
    w = replay(fn_text(built), ground)
    water = [c for c, s in w.items() if s == ST.WATER]
    assert len(water) > 5000
    assert not leaks(w, ground, 0)[:3]
    assert not leaks(w, ground, 1)[:3]


def test_the_water_stands_at_the_level_and_nowhere_above_it(built):
    ys = {c[1] for c, s in replay(fn_text(built), lambda x, z: 0).items() if s == ST.WATER}
    assert max(ys) == YS


def test_no_trunk_stands_within_the_clear_distance_of_the_water(pl):
    for t in pl.trees:
        d = min(((t["x"] - x) ** 2 + (t["z"] - z) ** 2) ** 0.5 for (x, z) in pl.W)
        assert d > DOC["growth"]["trunk_clear"], t


def test_every_trunk_stands_on_the_rounded_ground(built, ground, pl):
    w = replay(fn_text(built), ground)
    for t in pl.trees:
        st = w.get((t["x"], ground(t["x"], t["z"]) + 1, t["z"]))
        assert st and ST.base(st) in ("minecraft:spruce_log", "minecraft:birch_log"), (t, st)


def test_the_pack_writes_one_spawn_condition_block_and_it_is_whitelisted_for_this_place(built):
    spawn = set(_load("spawn_blocks.json")["blocks"])
    text = fn_text(built)
    states = {m.group(1) for m in re.finditer(r"(minecraft:[a-z_]+)", text)}
    assert states & spawn == {"minecraft:water"}, states & spawn
    ok = [w for w in _load("spawn_block_policy.json")["whitelist"]
          if "minecraft:water" in w["blocks"] and "scar_tarn" in w["scope"]]
    assert ok and "concrete" not in text


def test_the_pack_passes_the_server_command_limits(built):
    assert function_limits.check_lines(fn_text(built).splitlines(), "build") == []


def test_authored_points_are_clear_of_every_column_written(pl):
    import southern_residents as SR
    mine = {(w[0], w[2]) for w in pl.wards.values()}
    pts = [(x, z) for x, z, f in SR.authored_points({"residents": []}, own_file=ST.DATA) if not (f == "habitat_blocks.json" and (x, z) in mine)]
    m = DOC["rules"]["authored_clearance"]
    near = [(x, z) for (x, z) in pts if pl.X0 - 40 <= x <= pl.X1 + 40 and pl.Z0 - 40 <= z <= pl.Z1 + 40]
    assert near, "the sweep found nothing to be clear of: the check would pass on nothing"
    for (px, pz) in near:
        d = min(((px - x) ** 2 + (pz - z) ** 2) ** 0.5 for (x, z) in pl.cols)
        assert d >= m, (px, pz, d)


def test_the_build_is_deterministic(pl, built):
    again, _ = ST.files(pl=pl)
    assert again == built[0]


# ------------------------------------------------------------------ the guards bite (mutate the generator, not the record)


def test_a_bank_that_is_not_lifted_leaves_a_leak_one_block_under_the_heightmap(ground, monkeypatch):
    real = ST.Plan.put

    def no_bank(self, phase, x, y, z, state, mode="replace"):
        if phase == "bank":
            return
        return real(self, phase, x, y, z, state, mode)
    monkeypatch.setattr(ST.Plan, "put", no_bank)
    p = ST.plan(DOC, ground)
    assert any("when the unwritten ground is 1 under" in s for s in p.problems), p.problems[:3]


def test_a_water_level_over_the_spill_is_refused(ground):
    d = copy.deepcopy(DOC)
    d["pond"]["water_level"] = 239
    d["pond"]["bank_lift_to"] = 240
    with pytest.raises(SystemExit):
        ST.plan(d, ground)


def test_a_window_the_water_would_leave_is_refused(ground):
    d = copy.deepcopy(DOC)
    d["pond"]["window"] = [2000, 690, 2030, 720]
    with pytest.raises(SystemExit):
        ST.plan(d, ground)


def test_a_block_outside_the_allow_list_is_refused(ground):
    d = copy.deepcopy(DOC)
    d["blocks"]["ids"] = [b for b in d["blocks"]["ids"] if b != "minecraft:spruce_log"]
    p = ST.plan(d, ground)
    assert any("not in blocks.ids" in s for s in p.problems)


def test_a_water_whitelist_removed_refuses_the_pack(ground, monkeypatch):
    real = ST.jload

    def jl(name):
        d = real(name)
        if name == "spawn_block_policy.json":
            d = copy.deepcopy(d)
            d["whitelist"] = [w for w in d["whitelist"] if "scar_tarn" not in (w.get("scope") or "")]
        return d
    monkeypatch.setattr(ST, "jload", jl)
    p = ST.plan(DOC, ground)
    assert any("spawn condition names" in s for s in p.problems)


def test_a_ward_cell_that_is_not_its_mimic_is_found(pl, monkeypatch):
    first = next(iter(pl.wards))
    x, y, z = pl.wards[first]
    saved = pl.final[(x, y, z)]
    pl.final[(x, y, z)] = "minecraft:stone"
    try:
        assert any(first in s for s in ST.check_plan(pl))
    finally:
        pl.final[(x, y, z)] = saved


# ------------------------------------------------------------------ the alphas and the shared files


def test_the_four_wards_are_in_cells_the_pack_writes_and_two_stand_under_the_water(pl, built, ground):
    w = replay(fn_text(built), ground)
    wards = {r["id"]: r for r in _load("habitat_blocks.json")["blocks"] if r["id"].startswith("scar_tarn_")}
    assert sorted(wards) == sorted(x["id"] for x in DOC["wards"]["land"] + DOC["wards"]["water"])
    for wid, r in wards.items():
        p = r["position"]
        assert w.get((p["x"], p["y"], p["z"])) == r["mimic"], wid
        assert r["style"] == "activated" and r["replace_spawns"] is False and r["status"] == "planned"
    wet = [wid for wid, r in wards.items() if w.get((r["position"]["x"], r["position"]["y"] + 1, r["position"]["z"])) == ST.WATER]
    assert sorted(wet) == ["scar_tarn_waters_east_ward", "scar_tarn_waters_west_ward"]


def test_the_records_on_disk_are_the_plans(pl):
    habs, pools = ST.records(pl)
    hd = {b["id"]: b for b in _load("habitat_blocks.json")["blocks"]}
    for h in habs:
        assert hd[h["id"]] == h
    sd = _load("spawns.json")
    for p in pools:
        assert [h for h in sd["habitats"] if h["id"] == p["habitat"]["id"]] == [p["habitat"]]
        mine = [e for e in sd["entries"] if e.get("scope") == p["habitat"]["id"]]
        assert mine == p["entries"]
    assert all(e["modifiers"] == "alpha=true" for p in pools for e in p["entries"])
    assert all("alpha" not in e for p in pools for e in p["entries"]), "the heart-only alpha key must not be used"


def test_the_compiled_pools_carry_alpha_at_the_authored_band():
    import compile_spawns as CS
    sd = _load("spawns.json")
    lo, hi = DOC["alphas"]["band"]
    seen = 0
    for h in sd["habitats"]:
        if not h["id"].startswith("scar_tarn_"):
            continue
        ents = [e for e in sd["entries"] if e["mechanism"] == "habitat_block" and e["scope"] == h["id"]]
        doc, _s = CS.compile_habitat(h, ents)
        assert doc["spawns"] and all(s["modifiers"] == "alpha=true" and s["levelRange"] == "%d-%d" % (lo, hi) for s in doc["spawns"])
        seen += len(doc["spawns"])
    assert seen == 6


def test_the_probes_on_disk_are_the_plans(pl):
    wp = _load("world_probes.json")["places"]
    got = ST.presence_probes(pl)
    assert wp["scar_tarn"] == got["scar_tarn"]
    rows = wp["scar_tarn"]
    ward = {tuple(w) for w in pl.wards.values()}
    assert len(rows) >= 30 and not [r for r in rows if tuple(r["block"][:3]) in ward]
    assert any(r["expect"] is False for r in rows) and any(r["block"][3] == ST.WATER and r["expect"] for r in rows)


def test_reapply_registers_the_pack_and_runs_r9st_before_r9e(pl):
    text = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert text.index('"R9FI"') < text.index('"R9ST"') < text.index('("R9E"')
    server = text[text.index("SERVER_PACKS = ("):text.index("WORLD_LOCAL = (")]
    world_local = text[text.index("WORLD_LOCAL = ("):text.index("SPAWN_PACKS = (")]
    assert '"cobblers_scar_tarn"' in server and '"cobblers_scar_tarn"' not in world_local
    assert 'add("scar_tarn:build", "scar_tarn.py", "build", *src)' in text
    steps = ST.placement_steps(pl=pl)
    adds = [v for k, v in steps if k == "cmd" and v.startswith("forceload add")]
    rems = [v.replace("remove", "add") for k, v in steps if k == "cmd" and v.startswith("forceload remove")]
    assert adds == rems and ("fn", "cobblers:scar_tarn/build") in steps
    x0, z0, x1, z1 = (int(t) for t in adds[0].split()[2:])
    assert ((x1 // 16 - x0 // 16) + 1) * ((z1 // 16 - z0 // 16) + 1) <= 256
    for (x, z) in pl.cols:
        assert x0 <= x <= x1 and z0 <= z <= z1

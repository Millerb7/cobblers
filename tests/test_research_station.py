"""tools/research_station_audit.py against tools/research_station.py: the clean pack passes, and a broken GENERATOR fails.

Written by the session that wrote the generator and the audit (the brief asked one agent for both), so the independent
half of the proof is the mutation standard of CLAUDE.md, "How to prove an audit is independent": every tamper case in
the generator section changes the generator's CODE (a function wrapped or replaced) and leaves data/research_station.json
and the quest records alone. A record-side mutation moves the expectation and the output together and proves nothing;
the one record-side case here (an ungated transition) tests a check that is ABOUT the records, the hold.

Re-sited 2026-10-02 to the west sea coast (the owner: "research station should be near 552 2812 not the lake"); the
cleanup section checks the one-off staging cleanup of the lake build against the audit's own water model, and a cleanup
that drains the lake (the generator's natural() mutated) fails it.

Needs the canonical heightmap (COBBLERS_SOURCE_ROOT); a skip names it. The cleanup tests also need git and commit
42ce560 (the lake build) in this checkout's history. NOT covered, and it needs a running server (data/research_station.json
probes): that the fills land, that the altars render and answer, that the study pool's Horsea spawn, that the NPCs
render, that the tick function removes a tag added by hand, that the cleanup's kills find the old NPCs.
"""
import copy
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import research_station as R  # noqa: E402
import research_station_audit as A  # noqa: E402

REC = json.loads((ROOT / "data" / "research_station.json").read_text(encoding="utf-8"))
JAR_DIR = Path(os.environ.get("COBBLERS_JAR_DIR", "C:/Users/wnd/Documents/github/cobblers/.claude/worktrees/"
                              "cobblemon-campaign-setup-64929d/experiments/EXP-000-cobblemon-1.8-compat/runtime/server/mods"))


@pytest.fixture(scope="module")
def ground():
    import ground as G
    import terrain as T
    try:
        return G.Ground(os.environ.get("COBBLERS_SOURCE_ROOT"))
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)


def run(ground, out, doc=None, rec=None, data=A.DATA, steps=True):
    doc = doc or R.load()
    written, _p = R.files(doc, ground)
    R.write(written, out)
    return A.audit(rec or REC, ground, out, R.placement_steps(doc, ground) if steps else None, data)


def checks(rep):
    return sorted({e.split(":", 1)[0] for e in rep.errors})


# ------------------------------------------------------------------------------------------- the committed station
def test_the_committed_station_is_clean(ground, tmp_path):
    rep = run(ground, tmp_path)
    assert rep.errors == []


def test_the_habitat_block_and_the_npcs_are_where_the_plan_puts_them(ground):
    p = R.plan(R.load(), ground)
    hb = {b["id"]: b for b in json.loads((ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8"))["blocks"]}
    b = hb[REC["study_pool"]["habitat_block"]]
    assert p.habitat == (b["position"]["x"], b["position"]["y"], b["position"]["z"])
    rw = {r["id"]: r for r in json.loads((ROOT / "data" / "rewards.json").read_text(encoding="utf-8"))["rewards"]}
    for n in REC["npcs"]:
        assert tuple(rw[n["reward"]]["npc_at"]) == p.npcs[n["id"]], n["id"]


def test_the_shrine_is_over_open_sea_and_every_deck_floats_by_its_rule(ground):
    # the audit's own water model (data/world.json's sea level, its own polygon test against every lake), not the
    # generator's: the two must agree column for column over every deck
    w = A.Water(REC, ground)
    assert REC["site"]["water"] == "sea" and w.level == REC["site"]["level_y"] == 62
    cx, cz = REC["shrine"]["centre"]
    assert w.depth(cx, cz) >= REC["shrine"]["min_depth"]
    gen = R.Water(REC, ground)
    for wk in REC["walks"]:
        need = REC["rules"]["min_depth"][wk["kind"]]
        for x, z in R.cells(wk["rect"]):
            d = w.depth(x, z)
            assert d == gen.depth(x, z), (wk["id"], x, z, d, gen.depth(x, z))
            assert (d is None and ground(x, z) == w.level and wk["kind"] in REC["rules"]["landfall_kinds"]) or \
                (d is not None and d >= need), (wk["id"], x, z, d)


def test_the_station_is_near_the_owners_coordinate_and_clear_of_the_zapdos_tower(ground):
    # the owner, 2026-10-02: "research station should be near 552 2812 not the lake"
    assert REC["site"]["asked_at"] == [552, 2812]
    land = [b["rect"] for b in REC["buildings"] if b["on"] == "land"] + [REC["plaza"]["rect"]]
    assert any(r[0] <= 552 <= r[2] and r[1] <= 2812 <= r[3] for r in land)
    for b in REC["buildings"]:
        if b["on"] == "land":
            assert min(ground(x, z) for x, z in R.cells(b["rect"])) >= REC["site"]["level_y"] + 1, b["id"]
    # the tower is scheduled: its position is data/placements.json legendary_zapdos_tower's, read through the resolver
    import adopted_sites
    w = adopted_sites.where(adopted_sites.site("adopted_zapdos_tower"))
    (tx, tz), (sx, _sy, sz) = w["corner"], w["size"]
    p = R.plan(R.load(), ground)
    near = min(max(tx - x, 0, x - (tx + sx - 1)) + max(tz - z, 0, z - (tz + sz - 1)) for (x, _y, z) in p.blocks())
    assert near > 100, near


# ------------------------------------------------------------------------------------------- the hold
def test_every_item_is_held_today(ground, tmp_path):
    assert REC["economy"]["issuing"] is False
    written, _p = R.files(R.load(), ground)
    assert not [k for k in written if "/advancement/" in k], "an earning advancement ships while held"
    tick = written["data/cobblers/function/research_station/tick.mcfunction"]
    assert "remove cobblers_station_issuing" in tick and " add " not in tick
    assert not any(" give " in (" " + t) for k, t in written.items() if k.endswith(".mcfunction"))


def test_issuing_ships_the_earning_and_adds_the_tags(ground, tmp_path):
    doc = copy.deepcopy(R.load())
    doc["economy"]["issuing"] = True
    doc["economy"]["post_champion_cap"] = 70
    written, _p = R.files(doc, ground)
    advs = sorted(k for k in written if "/advancement/" in k)
    assert len(advs) == 4, advs
    tick = written["data/cobblers/function/research_station/tick.mcfunction"]
    assert "add cobblers_station_issuing" in tick and "add cobblers_station_issuing_crown" in tick
    storm = json.loads(written["data/cobblers/advancement/research_station/storm_log.json"])
    conds = storm["criteria"]["earned"]["conditions"]["player"]
    assert {"condition": "minecraft:weather_check", "thundering": True} in conds
    R.write(written, tmp_path)
    rep = A.audit(doc, ground, tmp_path, R.placement_steps(doc, ground))
    assert rep.errors == []


def test_issuing_without_a_measured_cap_keeps_the_crown_held(ground):
    doc = copy.deepcopy(R.load())
    doc["economy"]["issuing"] = True
    tick = R.tick_lines(doc)
    assert "tag @a[tag=!cobblers_station_issuing] add cobblers_station_issuing" in tick
    assert "tag @a[tag=cobblers_station_issuing_crown] remove cobblers_station_issuing_crown" in tick


def _data_copy(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    for name in ("research_station.json", "landmarks.json", "habitat_blocks.json", "spawns.json", "rewards.json",
                 "quests.json", "dialogue.json", "spawn_blocks.json", "spawn_block_policy.json", "progression.json",
                 "world.json"):
        shutil.copy(ROOT / "data" / name, d / name)
    return d


def test_a_transition_that_gives_without_the_switch_is_caught(ground, tmp_path):
    d = _data_copy(tmp_path)
    q = json.loads((d / "quests.json").read_text(encoding="utf-8"))
    tr = next(t for x in q["quests"] if x["id"] == "evt_station_director" for t in x["transitions"] if t["id"] == "grant_thunder")
    tr["conditions"] = [c for c in tr["conditions"] if c.get("tag") != "cobblers_station_issuing"]
    (d / "quests.json").write_text(json.dumps(q), encoding="utf-8")
    rep = run(ground, tmp_path / "pack", data=d)
    assert "hold" in checks(rep)


# ------------------------------------------------------------------------------------------- generator mutations
def _wrap(monkeypatch, name, after):
    orig = getattr(R, name)

    def wrapped(p, *a, **k):
        r = orig(p, *a, **k)
        after(p)
        return r
    monkeypatch.setattr(R, name, wrapped)


def test_a_bridge_left_without_its_deck_is_caught(ground, tmp_path, monkeypatch):
    def drop(p):
        r = next(w for w in p.doc["walks"] if w["id"] == "bridge_west")["rect"]
        for x, z in R.cells(r):
            p.solid["crossing"].pop((x, p.level, z), None)
    _wrap(monkeypatch, "walks", drop)
    rep = run(ground, tmp_path)
    assert "decks" in checks(rep)


def test_a_deck_written_a_block_low_is_caught(ground, tmp_path, monkeypatch):
    def sink(p):
        r = next(w for w in p.doc["walks"] if w["id"] == "pier_west")["rect"]
        for x, z in R.cells(r):
            st = p.solid["platform"].pop((x, p.level, z), None)
            if st:
                p.solid["platform"][(x, p.level - 1, z)] = st
    _wrap(monkeypatch, "walks", sink)
    rep = run(ground, tmp_path)
    assert {"decks", "footprint"} <= set(checks(rep))


def test_the_extra_lamp_posts_left_out_are_caught(ground, tmp_path, monkeypatch):
    monkeypatch.setattr(R, "light_fill", lambda p: None)
    rep = run(ground, tmp_path)
    assert "light" in checks(rep)


def test_an_altar_turned_is_caught(ground, tmp_path, monkeypatch):
    def turn(p):
        x, z = p.doc["shrine"]["latias"]["at"]
        p.solid["platform"][(x, p.level + 2, z)] = "lumymon:latias_altar[facing=north]"
    _wrap(monkeypatch, "shrine", turn)
    rep = run(ground, tmp_path)
    assert "shrine" in checks(rep)


def test_the_anchor_left_out_is_caught(ground, tmp_path, monkeypatch):
    def drop(p):
        x, z = p.doc["shrine"]["anchor"]["at"]
        p.solid["platform"].pop((x, p.level + 2, z))
    _wrap(monkeypatch, "shrine", drop)
    rep = run(ground, tmp_path)
    assert "shrine" in checks(rep)


def test_the_habitat_post_cut_short_is_caught(ground, tmp_path, monkeypatch):
    def cut(p):
        x, z = p.doc["study_pool"]["habitat_post"]
        p.solid["study_pool"].pop((x, p.g(x, z) + 1, z))
    _wrap(monkeypatch, "study_pool", cut)
    rep = run(ground, tmp_path)
    assert "habitat" in checks(rep)


def test_a_building_seated_a_block_low_is_caught(ground, tmp_path, monkeypatch):
    orig = R.seat
    monkeypatch.setattr(R, "seat", lambda p, b: orig(p, b) - (1 if b["on"] == "land" else 0))
    rep = run(ground, tmp_path)
    assert {"seat", "npc"} <= set(checks(rep))


def test_a_write_into_the_lake_is_caught(ground, tmp_path, monkeypatch):
    def sink(p):
        x, z = p.doc["shrine"]["centre"]
        p.solid["platform"][(x, p.level - 3, z)] = "minecraft:tuff"
    _wrap(monkeypatch, "shrine", sink)
    rep = run(ground, tmp_path)
    assert "footprint" in checks(rep)


def test_a_spawn_condition_slipped_in_is_caught(ground, tmp_path, monkeypatch):
    monkeypatch.setattr(R.Plan, "_check", lambda self, st: None)

    def bell(p):
        x0, z0, _x1, _z1 = next(b for b in p.doc["buildings"] if b["id"] == "institute")["rect"]
        p.solid["strand"][(x0 + 8, p.floors["institute"] + 1, z0 + 4)] = "minecraft:lightning_rod"
    _wrap(monkeypatch, "plaza", bell)
    rep = run(ground, tmp_path)
    assert "blocks" in checks(rep)


def test_the_switch_tag_added_while_held_is_caught(ground, tmp_path, monkeypatch):
    monkeypatch.setattr(R, "tick_lines", lambda doc: ["tag @a[tag=!cobblers_station_issuing] add cobblers_station_issuing"])
    rep = run(ground, tmp_path)
    assert "hold" in checks(rep)


def test_an_earning_advancement_shipped_while_held_is_caught(ground, tmp_path, monkeypatch):
    orig = R.files

    def leaky(doc, g):
        out, p = orig(doc, g)
        for name, (a, lines) in R.earning(doc, g).items():
            out["data/cobblers/advancement/research_station/%s.json" % name] = json.dumps(a)
            out["data/cobblers/function/research_station/earned/%s.mcfunction" % name] = "\n".join(lines) + "\n"
        return out, p
    monkeypatch.setattr(R, "files", leaky)
    rep = run(ground, tmp_path)
    assert "hold" in checks(rep)


def test_a_zone_step_that_holds_too_little_is_caught(ground, tmp_path, monkeypatch):
    orig = R.zone_box

    def small(p, zone):
        x0, z0, x1, z1 = orig(p, zone)
        return (x0, z0, x0 + 8, z0 + 8) if zone == "platform" else (x0, z0, x1, z1)
    monkeypatch.setattr(R, "zone_box", small)
    rep = run(ground, tmp_path)
    assert "steps" in checks(rep)


# ------------------------------------------------------------------------------------------- generator refusals
def test_a_pier_over_the_shoal_is_refused(ground):
    doc = copy.deepcopy(R.load())
    next(w for w in doc["walks"] if w["id"] == "junction")["kind"] = "pier"
    with pytest.raises(SystemExit, match="needs 3"):
        R.plan(doc, ground)


def test_a_land_building_in_the_sea_is_refused(ground):
    doc = copy.deepcopy(R.load())
    b = next(b for b in doc["buildings"] if b["id"] == "bunkhouse")
    b["rect"] = [500, 2796, 508, 2802]
    with pytest.raises(SystemExit, match="in the water"):
        R.plan(doc, ground)


def test_a_land_building_on_the_waterline_strip_is_refused(ground):
    doc = copy.deepcopy(R.load())
    b = next(b for b in doc["buildings"] if b["id"] == "bunkhouse")
    b["rect"] = [526, 2796, 534, 2802]          # ground y62, dry but level with the sea
    with pytest.raises(SystemExit, match="under the water's level"):
        R.plan(doc, ground)


def test_a_shrine_over_less_water_than_its_minimum_is_refused(ground):
    doc = copy.deepcopy(R.load())
    doc["shrine"]["min_depth"] = REC["site"]["level_y"] - ground(*doc["shrine"]["centre"]) + 1
    with pytest.raises(SystemExit, match="shrine.min_depth"):
        R.plan(doc, ground)


def test_a_record_in_no_zone_is_refused(tmp_path):
    doc = copy.deepcopy(REC)
    doc["zones"]["study_pool"]["walks"] = ["study_walk"]
    f = tmp_path / "rs.json"
    f.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(SystemExit, match="belongs to no zone"):
        R.load(f)


def test_the_generator_reads_no_world():
    assert R.WORLD_READS == set()


# ------------------------------------------------------------------------------------------- the staging cleanup
OLD = REC["superseded_site"]


@pytest.fixture(scope="module")
def cleaned(ground):
    import subprocess
    if subprocess.run(["git", "cat-file", "-e", R.OLD_REV + "^{commit}"], cwd=ROOT).returncode != 0:
        pytest.skip("NOT_EXECUTED: commit %s (the lake build) is not in this checkout" % R.OLD_REV)
    return R.cleanup(R.plan(R.load(), ground), ground)


def _restored(lines):
    W = A.Replay()
    rep = A.Report()
    W.run("restore", lines, rep)
    assert rep.errors == []
    return W.blocks


def _expect_wrong(ground, op, restored):
    """[(cell, wanted, got)] against the audit's own lake model (data/landmarks.json, its own polygon test): over the
    ground, Shrew Lake's water to its level where the lake holds the column and air above it; the ground's own block
    sand or grass; and every cell the lake build wrote is either restored or was air written over air."""
    lake = A.Water({"site": {"water": OLD["lake"]}}, ground)
    assert lake.level == OLD["level_y"]
    out = []
    for (x, y, z), st in op.blocks().items():
        gy = ground(x, z)
        got = restored.get((x, y, z))
        if y > gy:
            want = "minecraft:water" if lake.depth(x, z) is not None and y <= lake.level else "minecraft:air"
            if got is None and want == "minecraft:air" and A.base(st) == "minecraft:air":
                continue
            if got != want:
                out.append(((x, y, z), want, got))
        elif got not in ("minecraft:sand", "minecraft:grass_block"):
            out.append(((x, y, z), "sand or grass", got))
    return out


def test_the_cleanup_puts_every_cell_the_lake_build_wrote_back_to_the_heightmap_world(ground, cleaned):
    lines, counts, _seats, op = cleaned
    restored = _restored(lines["restore"])
    assert _expect_wrong(ground, op, restored) == []
    hab = tuple(OLD["habitat_block"]["at"])
    assert restored[hab] == "minecraft:water"                  # the old Habitat Block's cell, mid-lake
    assert set(restored) <= set(op.blocks()) | {hab}           # nothing outside what the lake build wrote
    assert counts["to_water"] > 0 and counts["ground_top_restored"] > 0 and counts["under_ground"] == 0
    new = R.plan(R.load(), ground).blocks()
    assert not set(restored) & set(new)


def test_a_cleanup_that_drains_the_lake_is_caught(ground, cleaned, monkeypatch):
    monkeypatch.setattr(R, "natural", lambda s, g, x, y, z: "minecraft:air" if y > g(x, z) else "minecraft:grass_block")
    lines, _counts, _seats, op = R.cleanup(R.plan(R.load(), ground), ground)
    wrong = _expect_wrong(ground, op, _restored(lines["restore"]))
    assert wrong and all(w[1] == "minecraft:water" for w in wrong)


def test_the_cleanup_removes_the_four_old_npcs_by_type_in_a_tight_box_at_their_old_seats(cleaned, tmp_path):
    _lines, _counts, seats, _op = cleaned
    assert seats == {k: tuple(v) for k, v in OLD["npc_seats"].items()}
    hold, go = R.npc_cleanup_lines(seats, "research_station_cleanup")
    kills = [l for l in go if " kill " in l]
    assert len(kills) == 4
    for nid, (x, y, z) in seats.items():
        k = next(l for l in kills if ".%s " % nid in l)
        assert "@e[type=cobblemon:npc,x=%d,y=%d,z=%d,dx=2,dy=1,dz=2]" % (x - 1, y, z - 1) in k
        assert "distance" not in k
    assert any(l.startswith("schedule function cobblers:research_station_cleanup/npcs_go") for l in hold)
    assert go[0].startswith("# chunks-loaded-by: cobblers:research_station_cleanup/npcs")
    for x, _y, z in seats.values():
        assert "forceload add %d %d" % (x >> 4 << 4, z >> 4 << 4) in hold
        assert "forceload remove %d %d" % (x >> 4 << 4, z >> 4 << 4) in go


def test_the_cleanup_pack_is_staging_only_and_every_function_would_run(cleaned, tmp_path):
    import function_limits
    lines, _counts, seats, _op = cleaned
    assert R.CLEANUP_OUT.parent.name == "staging" and "datapacks" not in R.CLEANUP_OUT.parts
    out = tmp_path / "cobblers_research_station_cleanup"
    fn, order = R.write_cleanup(out, lines, seats)
    assert order[-1] == "npcs" and len(order) >= 2
    for f in fn.glob("*.mcfunction"):
        assert function_limits.check_lines(f.read_text(encoding="utf-8").splitlines(), f.name) == [], f.name


# ------------------------------------------------------------------------------------------- the jar, when present
def test_the_shrine_blocks_and_their_items_are_lumymons():
    jar = JAR_DIR / "LumyMon-0.6.6.jar"
    if not jar.is_file():
        pytest.skip("NOT_EXECUTED: no LumyMon-0.6.6.jar at %s (set COBBLERS_JAR_DIR)" % JAR_DIR)
    z = zipfile.ZipFile(jar)
    names = set(z.namelist())
    for key in ("latias", "latios"):
        bs = json.loads(z.read("assets/lumymon/blockstates/%s_altar.json" % key))
        assert "facing=%s" % REC["shrine"][key]["facing"] in bs["variants"]
    assert "assets/lumymon/blockstates/summon_anchor.json" in names
    lat = z.read("com/lumyverse/lumymon/block/custom/LatiasAltar.class")
    lao = z.read("com/lumyverse/lumymon/block/custom/LatiosAltar.class")
    assert b"RUBY_DEW" in lat and b"SAPPHIRE_DEW" in lao and b"SUMMON_ANCHOR" in lat and b"SUMMON_ANCHOR" in lao
    for lv in REC["shrine"]["levels"]["latias"]:
        assert b"latias level=%d" % lv in lat
    for it in ("thunder_feather", "glacier_feather", "ember_feather", "calyrex_crown", "ruby_dew", "sapphire_dew",
               "shaderoot_carrot"):
        assert "assets/lumymon/models/item/%s.json" % it in names

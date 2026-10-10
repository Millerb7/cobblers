"""The Drowned Reliquary (data/dungeons.json `flooded_ruin`, unit DG-RUIN): the third test dungeon, built and walked.

The author's own tests (the independent audit is another agent's). What they hold the record to:

  shape     every room type the owner named is present (maze, puzzle, parkour, resources, nest, habitat, stand,
            mini-boss) and at least three of ours; full length (1,200-1,600 walked); rooms 30-60 wide; connectors at most
            40 long and at least 7 wide; no two fight rooms back to back; the safe room past the middle and the resources
            before the hardest stretch;
  walk      the room kit's own plan and walk check (tools/dungeon_rooms.py problems()) over the generated blocks: entry
            to exit and back, every anchor reached, every standable cell lit;
  species   every species named (stands, ambush, nest, mini-boss, habitat, boss crews) is in the Cobblemon 1.8.0 jar;
            the habitat's is a legendary or mythical, no Ultra Beast, and nothing else in data/ or DUNGEONS.md 8 uses it;
  params    the wave-2 params contract's fields, in range (levels never above the band's upper cap);
  rip       within 60 blocks of the Night Shift's, on the heightmap's ground, outside the old mine.

And a GENERATOR mutation: the ruin's tall halls are lit from the floor (theme hull.tall_lights, dungeon_rooms
floor_lights / cap_dark_dressing). Switching either off in the code, with the data untouched, must leave cells in the
dark and the walk check must say so.

Not covered: anything in a running Minecraft. The room kinds wave 2 builds (stand, gauntlet, miniboss, nest, habitat,
puzzle, vault, the healer) build here as themed rooms with their declared anchors until those modules merge.
"""
from __future__ import annotations

import copy
import glob
import math
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import dungeon as D  # noqa: E402
import dungeon_fights as DF  # noqa: E402
import dungeon_rooms as R  # noqa: E402

DOC = D.load()
RUIN = next(d for d in DOC["dungeons"] if d["id"] == "flooded_ruin")
NS = next(d for d in DOC["dungeons"] if d["id"] == "night_shift")
OWNER_KINDS = {"maze", "puzzle", "parkour", "resources", "nest", "habitat", "stand", "miniboss"}
OURS = {"gauntlet", "ambush", "vault", "dark_room", "collapse_bridge", "safe_room"}
FIGHTS = {"stand", "gauntlet", "ambush", "miniboss", "nest", "habitat", "boss_arena"}
CONNECTORS = {"drift", "stairs"}
ENDS = {"entry_room", "exit_room"}


@pytest.fixture(autouse=True)
def fresh_cache():
    R._BUILT.clear()
    yield
    R._BUILT.clear()


def slot1(doc=DOC):
    return next(s for s in D.slots(doc) if s["dungeon"]["id"] == "flooded_ruin")


def kinds():
    return [r["kind"] for r in RUIN["rooms"]]


# ------------------------------------------------------------------------------------------------- shape


def test_every_room_type_the_owner_named_is_there_and_three_of_ours():
    k = set(kinds())
    assert OWNER_KINDS <= k, OWNER_KINDS - k
    assert len((OURS & k) - {"ambush"}) >= 3, OURS & k
    assert kinds()[0] == "entry_room" and kinds()[-2:] == ["boss_arena", "exit_room"]
    assert RUIN["theme"] == "flooded_ruin" and RUIN["test"] is True and RUIN["rip"]["test"] is True
    assert RUIN["gate_flag"] is None


def test_full_length_wide_rooms_and_short_wide_connectors():
    s = slot1()
    pt = D.points(DOC, s)
    assert 1200 <= pt["length"] <= 1600, pt["length"]
    for r in R.layout(DOC, RUIN, s):
        if r["kind"] in CONNECTORS:
            assert r["length"] <= 40 and r["width"] >= 7, r["id"]
        elif r["kind"] not in ENDS:
            assert 30 <= r["width"] <= 60, (r["id"], r["width"])


def test_pacing_no_two_fights_back_to_back_safe_room_late_resources_before_the_last_stretch():
    ks = kinds()
    for a, b in zip(ks, ks[1:]):
        assert not (a in FIGHTS and b in FIGHTS), (a, b)
    rooms = R.layout(DOC, RUIN, slot1())
    total = rooms[-1]["xb"] - rooms[0]["xa"] + 1
    at = {r["kind"]: (r["xa"] - rooms[0]["xa"]) / total for r in rooms}
    assert 0.55 <= at["safe_room"] <= 0.8, at["safe_room"]
    assert at["resources"] < at["habitat"] < at["boss_arena"]
    # the hardest stretch (the habitat to the boss) has no resource room in it: greed is decided before it
    assert all(r["kind"] != "resources" for r in rooms if r["xa"] - rooms[0]["xa"] >= at["habitat"] * total)


# ------------------------------------------------------------------------------------------------- the walk


def test_the_ruin_builds_and_walks_with_no_problem():
    assert R.problems(DOC, RUIN) == []
    assert not [p for p in D.problems(DOC) if "flooded_ruin" in p]


def test_the_ruin_builds_its_functions_and_its_shell_fits_the_chain():
    s = slot1()
    files = D.build(DOC)
    shell = [k for k in files if "/shells/s%d/" % s["g"] in k]
    assert len(shell) == len(RUIN["rooms"])
    assert R.chain_problems(DOC, RUIN, s) == []
    assert 0.3e6 < D.shell_blocks(DOC, s) < 1.2e6


def _tall_rooms():
    t = R.load_themes()["themes"]["flooded_ruin"]["hull"]
    under = t["tall_lights"]["under"]
    return [r["id"] for r in R.layout(DOC, RUIN, slot1())
            if 15 - t["min_light"] - (r["ceil_y"] - min(r["floor_in"], r["floor_out"])) < under]


def test_the_tall_halls_are_lit_from_the_floor_and_the_ceiling_stays_sparse():
    tall = _tall_rooms()
    assert {"sealed_chamber", "flood_chamber", "guardian"} <= set(tall)
    th = R.load_themes()["themes"]["flooded_ruin"]
    for b in R.slot_build(DOC, RUIN, slot1()):
        if b.room["id"] not in tall or b.room["pit"] or R.flags_of(b.room["kind"])["dark"]:
            continue
        r = b.room
        floor = [p for p in b.lights if p[1] == r["floor_in"] - 1]
        ceil = [p for p in b.lights if p[1] == r["ceil_y"]]
        assert floor, r["id"]
        area = (r["ix1"] - r["ix0"] + 1) * (r["iz1"] - r["iz0"] + 1)
        assert len(ceil) <= area / (th["hull"]["light_every"] ** 2) * 2 + 4, (r["id"], len(ceil))


@pytest.mark.parametrize("mutant", ["floor_lights", "cap_dark_dressing"])
def test_mutating_the_tall_light_generator_off_leaves_cells_dark_and_the_walk_check_says_so(monkeypatch, mutant):
    monkeypatch.setattr(R, mutant, lambda *a, **k: None)
    bad = R.problems(DOC, RUIN)
    assert any("have no light" in p for p in bad), bad


# ------------------------------------------------------------------------------------------------- species


@pytest.fixture(scope="module")
def species():
    import battle_sim as B
    try:
        jar = B.find_jar()
    except B.SimError:
        pytest.skip("no Cobblemon 1.8 jar")
    sp, _m, _c = B.load_pack(jar)
    return sp, B.key


def named_species():
    out = []
    for r in RUIN["rooms"]:
        p = r.get("params", {})
        for t in p.get("trainers", []) if isinstance(p.get("trainers"), list) else []:
            for team in t["team_by_band"].values():
                out += [(r["id"], x) for x in team]
        out += [(r["id"], x) for x in p.get("species", []) if r["kind"] == "nest"]
        out += [(r["id"], x) for x in p.get("species_by_band", {}).values()]
        if r["kind"] == "habitat":
            out.append((r["id"], p["species"]))
    for crews in RUIN["boss"]["teams"].values():
        for crew in crews:
            out += [("boss", x) for x in crew]
    return out


def test_every_species_named_is_in_the_jar(species):
    sp, key = species
    missing = sorted({x for _r, x in named_species() if key(x) not in sp})
    assert not missing, missing


def test_the_habitat_is_a_legendary_or_mythical_no_ultra_beast_and_used_nowhere_else(species):
    sp, key = species
    hab = next(r for r in RUIN["rooms"] if r["kind"] == "habitat")["params"]["species"]
    labels = set(sp[key(hab)].get("labels", []))
    assert labels & {"legendary", "mythical"} and "ultra_beast" not in labels, labels
    word = re.compile(r"(?<![a-z])%s(?![a-z])" % re.escape(hab))
    import json

    def mentions(v):
        """Every dict in v with a string value that names the species."""
        if isinstance(v, dict):
            if any(isinstance(x, str) and word.search(x.lower()) for x in v.values()):
                yield v
            for x in v.values():
                yield from mentions(x)
        elif isinstance(v, list):
            for x in v:
                yield from mentions(x)

    for f in glob.glob(str(ROOT / "data" / "*.json")):
        name = Path(f).name
        if name == "dungeons.json":
            continue
        text = Path(f).read_text(encoding="utf-8")
        if name == "adopted_legendary_sites.json":
            # the catalogue of Cobbleverse's legendary structures: a donor that is NOT loaded homes nothing
            hits = list(mentions(json.loads(text)))
            assert all(h.get("loaded") is False for h in hits), [h.get("template") for h in hits]
            continue
        assert not word.search(text.lower()), f
    others = [d for d in DOC["dungeons"] if d["id"] != "flooded_ruin"]
    assert not any(word.search(str(d).lower()) for d in others)
    # DUNGEONS.md 8: the legendaries the owner approved for the planned dungeons (D18) are theirs
    doc8 = (ROOT / "docs" / "mechanics" / "DUNGEONS.md").read_text(encoding="utf-8")
    sec = doc8.split("## 8. Which legendaries", 1)[1].split("\n## ", 1)[0].lower()
    assert hab not in re.sub(r"[^a-z]", "", sec), "reserved in DUNGEONS.md 8"
    # no legendary, mythical or Ultra Beast fights for the salvagers or the boss
    for where, x in named_species():
        if where == "sealed_chamber":
            continue
        lb = set(sp[key(x)].get("labels", []))
        assert not lb & {"legendary", "mythical", "ultra_beast", "paradox"}, (where, x)


# ------------------------------------------------------------------------------------------------- params


def test_the_fight_params_follow_the_contract_and_never_pass_the_bands_upper_cap():
    bands = {str(b["band"]): b for b in D.bands(DOC)}
    for r in RUIN["rooms"]:
        p = r.get("params", {})
        if r["kind"] in ("stand", "gauntlet", "ambush"):
            assert DF.stand_problems(DOC, r) == [], r["id"]
            assert DF.stand_classes(DOC, RUIN, r)
            if r["kind"] != "stand":
                tr = p["triggers"]
                assert len(tr) == len(p["trainers"]) and tr == sorted(tr) and all(0 < t < 1 for t in tr)
            assert r["gate"] == "cleared"
        elif r["kind"] == "miniboss":
            assert set(p["species_by_band"]) == set(bands) and p["level_offset"] <= 0 and p.get("catchable") is False
            assert r["gate"] == "cleared"
        elif r["kind"] == "nest":
            assert set(p["count_by_band"]) == set(bands) and p["species"]
            lo, hi = p["level_spread"]
            assert 0 <= lo <= hi
        elif r["kind"] == "habitat":
            assert p.get("fight_only", True) is True and r["gate"] == "cleared"
            for b, lvl in p["level_by_band"].items():
                assert lvl <= max(bands[b]["caps"]), (b, lvl)
            assert 95 <= p["level_by_band"]["6"] <= 100
        elif r["kind"] == "puzzle":
            assert p["variant"] in ("levers", "sequence", "plates") and p["penalty_s"] > 0
        elif r["kind"] == "vault":
            assert r.get("gate", "open") == "open" and p["chests"] >= 1 and p["clock_cost_s"] > 0
            assert set(p["loot_by_band"]) == set(bands)
        elif r["kind"] == "safe_room":
            assert p.get("healer") is True


def test_the_boss_has_a_crew_per_stage_per_band_the_ace_last():
    bo = RUIN["boss"]
    assert bo["name"] != NS["boss"]["name"]
    for b in D.bands(DOC):
        crews = bo["teams"][str(b["band"])]
        assert len(crews) == len(bo["stage_level_offsets"])
        assert len({c[-1] for c in crews}) == 1, "one ace, sent out last in every stage"


# ------------------------------------------------------------------------------------------------- the rip


def test_the_rip_stands_near_the_night_shifts_and_clear_of_the_old_mine():
    f, nf = RUIN["rip"]["frame"], NS["rip"]["frame"]
    c = ((f["x0"] + f["x1"]) / 2, f["z"])
    nc = ((nf["x0"] + nf["x1"]) / 2, nf["z"])
    assert math.dist(c, nc) <= 60
    assert f["x0"] > nf["x1"] + 2 or f["x1"] < nf["x0"] - 2 or abs(f["z"] - nf["z"]) > 4, "the frames overlap"
    import json
    mine = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["settlements"]["route1_old_mine"]
    x0, z0, x1, z1 = mine["plan"]["footprint"]["rect"]
    for x in range(f["x0"] - 1, f["x1"] + 2):
        for z in range(f["z"] - 1, f["z"] + 5):
            assert not (x0 <= x <= x1 and z0 <= z <= z1), (x, z)
    cx, cy, cz = RUIN["rip"]["click"]
    assert cz == f["z"] + 1 and cy == f["y"] and cx == (f["x0"] + f["x1"]) // 2
    ox, oy, oz, _yaw = RUIN["rip"]["outside"]
    assert oz - 0.5 > cz + 1.5, "the leaving player stands outside the click interaction"


def test_the_rip_is_on_the_heightmaps_ground_and_not_in_water():
    try:
        import ground as GR
        g = GR.load()
    except Exception as e:  # noqa: BLE001  (no heightmap in this checkout)
        pytest.skip("no heightmap: %s" % e)
    f = RUIN["rip"]["frame"]
    feet = {g(x, z) + 1 for x in range(f["x0"], f["x1"] + 1) for z in (f["z"], f["z"] + 1)}
    assert feet == {f["y"]}, feet
    ox, oy, oz, _ = RUIN["rip"]["outside"]
    assert g(int(ox), int(oz)) + 1 == oy
    import json
    sea = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))["vertical"]["sea_level"]
    assert f["y"] - 1 > sea, "the ground under the rip is at or below the sea"


def test_the_slots_follow_the_dungeons_index_and_do_not_overlap():
    doc = copy.deepcopy(DOC)
    i = [d["id"] for d in doc["dungeons"]].index("flooded_ruin")
    ss = [s for s in D.slots(doc) if s["dungeon"]["id"] == "flooded_ruin"]
    per = doc["engine"]["slots"]["per_dungeon"]
    assert [s["g"] for s in ss] == list(range(i * per + 1, i * per + per + 1))
    assert not [p for p in D.problems(doc) if "meets" in p]

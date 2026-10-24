"""RT-B's three rooms (tools/dungeon_extras2.py, data/dungeon_extras2.json): `fishing_room`, `egg_room`, `fossil_chamber`.

  geometry   every kind builds in the three themes with no problem (the kit's walk check, pits, the pick's count, lights),
             the features survive the dressing, every block exists in 1.21.1, the markers / dig block / calcite stand only
             in their own room, the fossil bay is closed (solid behind, over and beside every breakable cell).
  data       every band and bucket covered, species real and not legendary (or, for fishing, a fossil Pokemon), starters in the
             common bucket, levels under the band's lower cap, prices that cannot end a run, the 15 fossil ids.
  runtime    the generated functions driven on tests/pocket_sim.py (through test_dungeon_puzzles.PW, which models blocks and
             `random value`): the rod is lent and taken back, the band's marker is set by the reset, a fished catch weighs as
             a nest catch; the vendor is spawned, bound and killed, an egg is charged once, weighed once and given once; the
             fossil is rolled, found, given from the band's table, counted by the mined stat, and put back by the reset.
  mutation   the GENERATOR is changed (not the record) and a check or a runtime assertion must fail.

Not covered (experiments/EXP-089): anything in a running Minecraft -- that a PokeBobber spawns from the boxed pool, that the pool loads
on a datapack reload, `givepokemonegg` from a function, a dialogue of a non-battling NPC in the pocket, calcite mined under
can_break in adventure raising the stat.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import dungeon as D  # noqa: E402
import dungeon_clock as DC  # noqa: E402
import dungeon_extras2 as DX  # noqa: E402
import dungeon_greed as DGR  # noqa: E402
import dungeon_grid as G  # noqa: E402
import dungeon_rooms as R  # noqa: E402
import pocket_sim as PS  # noqa: E402
import test_dungeon as TD  # noqa: E402
import test_dungeon_puzzles as TP  # noqa: E402
import test_dungeon_rooms as TR  # noqa: E402

FIX = json.loads((ROOT / "tests" / "fixtures" / "dungeon_extras2_rooms.json").read_text(encoding="utf-8"))["rooms"]
DATA = DX.load()
POCKET = TR.POCKET
U1 = TR.BASE["engine"]["clock"]["units_per_tick"] * 20
THEMES = ("mine", "jungle", "flooded_ruin")
JAR = Path("C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/Cobblemon-fabric-1.8.0+1.21.1.jar")


def xdoc(theme="mine", rooms=None, per_dungeon=1, derive=True):
    """The fixture as a finished rooms dungeon carries the clock derived from its own rooms (DUNGEON_ROOMS.md 7)."""
    doc = TR.demo_doc(theme, rooms if rooms is not None else FIX, per_dungeon=per_dungeon)
    if derive:
        doc["dungeons"][0]["clock_s_by_band"] = DC.derive(doc, doc["dungeons"][0])
    return doc


@pytest.fixture(autouse=True)
def fresh_cache(request):
    """The kit caches a built slot by the record, not by the kind's code: a generator mutation must not see (or leave) a cached
    normal build. Every other test shares the cache, which is most of the time."""
    mutating = "mutation" in request.node.name or "other_room" in request.node.name
    if mutating:
        R._BUILT.clear()
    yield
    if mutating:
        R._BUILT.clear()


def built(doc, rid, slot_index=0):
    d = doc["dungeons"][0]
    return next(b for b in R.slot_build(doc, d, D.slots(doc)[slot_index]) if b.room["id"] == rid)


# ------------------------------------------------------------------------------------------------- the simulator


class EW(TP.PW):
    """PW (blocks, `random value`) plus Cobbreeding's command: a given egg is recorded (player, properties)."""

    def __init__(self, pack_dir, *a, **k):
        super().__init__(pack_dir, *a, **k)
        self.eggs = []
        # PW reuses `loot` for the block positions that carry a LootTable, which hides the pack's loot tables from
        # pocket_sim's own `loot give`: keep the tables apart and give from them here
        self.tables = {}
        for p in Path(pack_dir).rglob("loot_table/**/*.json"):
            m = re.fullmatch(r"data/([^/]+)/loot_table/(.+)\.json", p.relative_to(pack_dir).as_posix())
            if m:
                self.tables["%s:%s" % (m.group(1), m.group(2))] = json.loads(p.read_text(encoding="utf-8"))

    def run_tokens(self, t, ctx, from_macro=False, raw=None):
        if t[0] == "loot" and t[1] == "give" and t[3] == "loot":
            table = self.tables[t[4]]
            for e in self.select(t[2], ctx):
                for pool in table["pools"]:
                    for _ in range(int(pool["rolls"])):
                        i = self.rolls.pop(0) if self.rolls else 0       # a roll is an index into the pool's entries
                        e.inventory.append([pool["entries"][i]["name"], {}, 1])
            return 1
        if t[0] == "givepokemonegg":
            who = self.select(t[1], ctx)
            if not who or who[0].kind != "player":
                raise PS.Failed("givepokemonegg needs a player")
            self.eggs.append((who[0].name, " ".join(t[2:])))
            return 1
        return super().run_tokens(t, ctx, from_macro, raw)


_CACHE = {}


def world(theme="mine", tmp_path_factory=None, salt="", doc=None, files=None):
    doc = doc if doc is not None else xdoc(theme)
    key = (theme, salt)
    if key not in _CACHE:
        out = Path(tmp_path_factory.mktemp("cobblers_extras2"))
        D.write(files if files is not None else D.build(doc), out)
        _CACHE[key] = out
    w = EW(_CACHE[key], dict(TD.FAKES))
    w.objectives |= {"cobblers.lc_cap", "tailend", "stale"}
    w.boot()
    return doc, w


@pytest.fixture
def mk(tmp_path_factory):
    return lambda theme="mine", salt="", doc=None, files=None: world(theme, tmp_path_factory, salt, doc, files)


def start(doc, w, band=1):
    p, s = TR.enter_run(doc, w)
    if band != 1:
        w.set(p.name, "dg.band", band)
    return p, s


def into(doc, w, p, rid, dx=4):
    return TP.into(doc, w, p, rid, dx)


def hold(s, r, tag=""):
    return TP.hold(s, r) + tag


def reset_slot(w, p, s):
    TP.reset_slot(w, p, s)


def lent_rods(p):
    return [i for i in p.inventory if i[0] == "cobblemon:poke_rod" and i[1].get("cobblers_lent_rod") == 1]


# ------------------------------------------------------------------------------------------------- geometry


@pytest.mark.parametrize("theme", THEMES)
def test_every_kind_builds_in_every_theme_with_no_problem_and_the_features_survive_the_dressing(theme):
    doc = xdoc(theme)
    assert R.problems(doc) == [] and D.warnings(doc) == [], (R.problems(doc), D.warnings(doc))
    for rid in ("fish", "eggs", "dig"):
        b = built(doc, rid)
        assert b.meta["expect"], rid
        for pos, want in b.meta["expect"]:
            assert G.base(b.grid.block_at(*pos)) == G.base(want), (theme, rid, pos, want)


@pytest.mark.parametrize("theme", THEMES)
def test_the_blocks_exist_in_1_21_1_and_none_is_banned(theme):
    ids = TR.vanilla_ids()
    f, fo = DATA["fishing"], DATA["fossils"]
    blocks = set(f["markers"][str(b)] for b in range(1, 7)) | {f["bed"][theme], fo["dig"][theme], fo["block"]}
    th = R.load_themes()["themes"][theme]
    blocks |= {v for v in th["safe"].values() if isinstance(v, str)}
    for b in blocks:
        assert not G.forbidden(b) and G.classify(b) != G.HAZARD, b
        if ids is not None:
            assert G.base(b) in ids, (theme, b)


def test_the_markers_the_dig_blocks_and_calcite_are_used_by_no_theme_and_no_puzzle():
    """A band marker or the dig block elsewhere would let a spawn entry fire in the wrong place, or make a wall breakable."""
    own = {DATA["fishing"]["markers"][str(b)] for b in range(1, 7)} | set(DATA["fossils"]["dig"].values()) | {DATA["fossils"]["block"]}
    text = (ROOT / "data" / "dungeon_themes.json").read_text(encoding="utf-8") + (ROOT / "data" / "dungeon_puzzles.json").read_text(encoding="utf-8")
    for b in own:
        assert b not in text, b


@pytest.mark.parametrize("theme", THEMES)
def test_a_marker_or_dig_block_in_any_other_room_is_named(theme):
    """The check bites: a fishing marker written into the egg room is named by the kit's problems()."""
    doc = xdoc(theme)
    real = R.KINDS["egg_room"]

    def bad(doc_, d, slot, room, th):
        res = real(doc_, d, slot, room, th)
        res["blocks"] = list(res["blocks"]) + [R.setb((room["ix0"] + 2, room["floor_in"], room["iz1"] - 1), DATA["fishing"]["markers"]["1"])]
        return res
    R.KINDS["egg_room"] = bad
    try:
        probs = R.problems(doc)
    finally:
        R.KINDS["egg_room"] = real
    assert any("only a fishing_room may place" in p for p in probs), probs


def test_the_pick_gains_the_dig_block_and_calcite_only_in_a_dungeon_with_a_fossil_chamber():
    doc = xdoc("mine")
    d = doc["dungeons"][0]
    assert set(DX.pick_extra(d)) == {"minecraft:terracotta", "minecraft:calcite"}
    assert {"minecraft:terracotta", "minecraft:calcite"} <= set(R.pick_blocks(d))
    assert "minecraft:calcite" in D.pick_give(doc, d)
    d2 = copy.deepcopy(d)
    d2["rooms"] = [r for r in d2["rooms"] if r["kind"] != "fossil_chamber"]
    assert DX.pick_extra(d2) == [] and "minecraft:calcite" not in R.pick_blocks(d2)


@pytest.mark.parametrize("theme", THEMES)
def test_the_fossil_bay_is_closed_and_nothing_the_pick_breaks_is_on_a_room_hull(theme):
    import test_dungeon_greed as TG
    doc = xdoc(theme)
    d = doc["dungeons"][0]
    assert TG.breakable_on_the_shell(doc, d, D.slots(doc)[0]) == []
    b = built(doc, "dig")
    r, m = b.room, b.meta["fossil"]
    pick = set(R.pick_blocks(d))
    cells = [(x, y, z) for x in range(r["ix0"], r["ix1"] + 1) for y in range(r["floor_in"], r["floor_in"] + 6)
             for z in range(r["iz0"], r["iz1"] + 1) if G.base(b.grid.block_at(x, y, z)) in pick]
    assert len(cells) == (m["x1"] - m["x0"] - 1) * m["rows"] * m["depth"] == b.meta["breakable_extra"]
    cls = b.grid.cls()
    for (x, y, z) in cells:                  # every neighbour of a breakable cell is another, a solid, or this room's air
        for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            n = (x + dx, y + dy, z + dz)
            assert b.grid.inside(*n)
            assert (cls[b.grid.local(*n)] == G.SOLID or n in cells or r["iz0"] <= n[2] <= r["iz1"] and cls[b.grid.local(*n)] == G.PASS), (n, b.grid.block_at(*n))
    for (x, y, z) in cells:                  # and the one behind the back layer is the hull's wall, which the pick may not break
        if z == r["iz0"]:
            assert G.base(b.grid.block_at(x, y, z - 1)) not in pick and cls[b.grid.local(x, y, z - 1)] == G.SOLID


def test_the_four_slots_are_one_dungeon():
    doc = xdoc("jungle", per_dungeon=4)
    d = doc["dungeons"][0]
    ss = D.slots(doc)
    a, b = built(doc, "dig", 0), built(doc, "dig", 3)
    assert a.meta["fossil"]["spots"] == [(x, y, z - 0) for (x, y, z) in a.meta["fossil"]["spots"]]
    rel = lambda bb, sl: [(c[0], c[1], c[2] - sl["z0"]) for c in bb.meta["fossil"]["spots"]]   # noqa: E731
    assert rel(a, ss[0]) == rel(b, ss[3])
    assert built(doc, "fish", 0).meta["fishing"]["x0"] == built(doc, "fish", 2).meta["fishing"]["x0"]


def test_the_rooms_never_close_a_way_on():
    doc = xdoc("mine")
    for r in R.layout(doc, doc["dungeons"][0], D.slots(doc)[0]):
        if r["kind"] in DX.KINDS:
            assert r["gate"] == "open", r["id"]


def test_the_shell_and_the_functions_are_inside_the_limits():
    import function_limits as FL
    for t in THEMES:
        files = D.build(xdoc(t))
        for rel, body in files.items():
            if "/room/night_shift/" in rel and rel.endswith(".mcfunction") and any(("/%s/" % x) in rel for x in ("fish", "eggs", "dig")):
                assert FL.check_lines(body.splitlines(), rel) == [], rel


@pytest.mark.parametrize("params", [{"pool_length": 4}, {"pool_length": 11}, {"pool_width": 2}, {"pool_width": 11}])
def test_pool_params_are_checked(params):
    rooms = [dict(r, params=params) if r["id"] == "fish" else r for r in FIX]
    assert R.problems(xdoc("mine", rooms, derive=False)), params


def test_a_room_too_narrow_for_its_pool_or_bay_is_named():
    rooms = [dict(r, width=17) if r["id"] == "fish" else r for r in FIX]
    assert any("widen the room" in p for p in R.problems(xdoc("mine", rooms, derive=False)))
    rooms = [dict(r, length=18) if r["id"] == "dig" else r for r in FIX]
    assert any("fossil chamber needs" in p for p in R.problems(xdoc("mine", rooms, derive=False)))
    rooms = [dict(r, length=16) if r["id"] == "eggs" else r for r in FIX]
    assert any("egg room needs" in p for p in R.problems(xdoc("mine", rooms, derive=False)))


# ------------------------------------------------------------------------------------------------- the data


def test_the_data_passes_its_checks_against_the_jar():
    doc = xdoc("mine")
    assert DX.data_problems(doc, DX.jar_species()) == []


def test_the_data_checks_bite():
    doc = xdoc("mine")
    sp = DX.jar_species()
    saved = copy.deepcopy(DATA)
    try:
        DATA["fishing"]["species"]["mine"]["3"]["rare"] = []
        assert any("bucket rare is empty" in p for p in DX.data_problems(doc, sp))
        DATA["fishing"]["species"]["mine"]["3"]["rare"] = [["mewtwo", 3]]
        assert any("mewtwo" in p for p in DX.data_problems(doc, sp)) or sp is None
        DATA["fishing"]["species"]["mine"]["3"]["rare"] = [["omanyte", 3]]
        assert any("omanyte" in p for p in DX.data_problems(doc, sp)) or sp is None, "a fossil Pokemon is the fossil chamber's"
        DATA["fishing"]["species"]["mine"]["3"]["rare"] = saved["fishing"]["species"]["mine"]["3"]["rare"]
        DATA["eggs"]["price"]["clock_s_by_band"]["1"] = 99999
        assert any("eggs.price band 1" in p for p in DX.data_problems(doc, sp))
        DATA["eggs"]["price"]["clock_s_by_band"]["1"] = 90
        DATA["fossils"]["by_band"]["2"].append(["cobblemon:pikachu_fossil", 1])
        assert any("15 fossil ids" in p for p in DX.data_problems(doc, sp))
    finally:
        DATA.clear()
        DATA.update(saved)
    assert DX.data_problems(doc, sp) == []


@pytest.mark.skipif(not JAR.is_file(), reason="the Cobblemon jar is not on this machine")
def test_every_stock_fishing_entry_needs_a_biome_a_structure_or_a_dimension_so_only_ours_can_fire_in_the_void_pocket():
    """The premise of the mechanism: the pocket's biome is the_void (DUNGEONS.md) and 591 stock fishing entries all name a biome."""
    import zipfile
    n = 0
    with zipfile.ZipFile(JAR) as z:
        for name in z.namelist():
            if name.startswith("data/cobblemon/spawn_pool_world/") and name.endswith(".json"):
                try:
                    doc = json.loads(z.read(name))
                except ValueError:
                    continue
                for s in doc.get("spawns", []):
                    if s.get("spawnablePositionType") == "fishing":
                        n += 1
                        c = s.get("condition", {})
                        assert c.get("biomes") or c.get("structures") or c.get("dimensions"), (name, s.get("id"))
    assert n > 500


@pytest.mark.skipif(not JAR.is_file(), reason="the Cobblemon jar is not on this machine")
def test_the_fossil_group_is_the_jars_fossil_tag_and_the_vendor_and_rod_ids_are_real():
    import zipfile
    with zipfile.ZipFile(JAR) as z:
        names = set(z.namelist())
        tag = json.loads(z.read("data/cobblemon/tags/item/fossils.json"))["values"]
        lang = z.read("assets/cobblemon/lang/en_us.json").decode("utf-8")
    assert sorted(DGR.load()["groups"]["fossils"]["ids"]) == sorted(tag)
    assert '"item.%s.%s"' % tuple(DATA["fishing"]["rod"]["id"].split(":")) in lang
    assert "data/cobblemon/behaviours/looks_at_players.json" in names, "the vendor's behaviour preset"
    assert "assets/cobblemon/textures/item/fishing/poke_rod.png" in names


# ------------------------------------------------------------------------------------------------- greed's table


def test_greed_prices_the_new_blocks_and_the_fossil_and_agrees_with_the_room_data():
    doc = xdoc("mine")
    assert DGR.problems(doc) == []
    t = DGR.load()
    assert DGR.block_cp(t, "minecraft:calcite") == DATA["fossils"]["greed_cp"]
    for blk in DATA["fossils"]["dig"].values():
        assert DGR.block_cp(t, blk) == 0, blk
    for ids in DATA["fossils"]["by_band"].values():
        for item, _w in ids:
            assert DGR.item_cp(t, item) == DATA["fossils"]["greed_cp"], item
    assert "minecraft:calcite" in DGR.breakable(doc) and (DGR.catch_cp(t, "nest", 1, doc) > 0)


def test_the_greed_catch_alias_is_a_nest_and_the_fishing_room_has_a_row():
    pack = D.build(xdoc("mine"))
    rows = pack["data/cobblers/function/dungeons/greed/s1/kind.mcfunction"]
    b = built(xdoc("mine"), "fish")
    assert DGR.CATCH_ALIAS["fishing_room"] == "nest"
    assert R.sel_box(b.room["box"]) in rows


# ------------------------------------------------------------------------------------------------- the fishing pool file


def pool_problems(files, doc):
    """Every problem with the fishing spawn pool of the first dungeon, read from the generated text (not from the generator)."""
    d = doc["dungeons"][0]
    key = "data/cobblemon/spawn_pool_world/cobblers_dg_%s_fishing.json" % d["short"]
    if key not in files:
        return ["no pool file"]
    pool = json.loads(files[key])
    bad = []
    strips = [s for s in D.slots(doc) if s["dungeon"] is d]
    zlo = min(s["z0"] for s in strips)
    zhi = max(s["z0"] for s in strips) + doc["engine"]["slots"]["strip_width_max"] - 1
    markers = DATA["fishing"]["markers"]
    by_band = {}
    ids = set()
    for e in pool["spawns"]:
        band = next((b for b in range(1, 7) if e["condition"].get("neededNearbyBlocks") == [markers[str(b)]]), None)
        if band is None:
            bad.append("%s: not keyed to exactly one band marker" % e["id"])
            continue
        by_band.setdefault(band, []).append(e)
        c = e["condition"]
        if e["spawnablePositionType"] != "fishing" or e["type"] != "pokemon":
            bad.append("%s: not a fishing detail" % e["id"])
        if c.get("dimensions") != [doc["engine"]["pocket"]["dimension"]]:
            bad.append("%s: not boxed to the pocket" % e["id"])
        if not (c["minX"] <= 0 and c["maxX"] >= 2047 and c["minZ"] <= zlo and c["maxZ"] >= zhi):
            bad.append("%s: the box does not cover the dungeon's slot rows" % e["id"])
        lo, hi = (int(v) for v in e["level"].split("-"))
        if not (5 <= lo <= hi <= min(doc["engine"]["bands"][band - 1]["caps"])):
            bad.append("%s: level %s is not under band %d's lower cap" % (e["id"], e["level"], band))
        if e["id"] in ids:
            bad.append("%s: duplicate id" % e["id"])
        ids.add(e["id"])
    for band in range(1, 7):
        got = {e["bucket"] for e in by_band.get(band, [])}
        if got != set(DX.BUCKETS):
            bad.append("band %d: buckets %s" % (band, sorted(got)))
    return bad


def test_the_fishing_pool_is_boxed_keyed_to_the_band_marker_and_under_the_bands_lower_cap():
    for theme in THEMES:
        doc = xdoc(theme)
        assert pool_problems(D.build(doc), doc) == [], theme
    doc = xdoc("jungle", per_dungeon=4)
    assert pool_problems(D.build(doc), doc) == []


def test_the_pool_holds_the_wanted_species_in_the_common_bucket_and_a_starter_in_every_band():
    sp = DX.jar_species()
    for theme in THEMES:
        doc = xdoc(theme)
        pool = json.loads(D.build(doc)["data/cobblemon/spawn_pool_world/cobblers_dg_ns_fishing.json"])
        for band in range(1, 7):
            m = DATA["fishing"]["markers"][str(band)]
            commons = [e for e in pool["spawns"] if e["condition"]["neededNearbyBlocks"] == [m] and e["bucket"] == "common"]
            assert len(commons) == 3
            total = sum(e["weight"] for e in commons)
            assert total >= 2 * sum(e["weight"] for e in pool["spawns"] if e["condition"]["neededNearbyBlocks"] == [m] and e["bucket"] == "uncommon")
            if sp is not None:
                assert any(sp[e["pokemon"]] & {"starter", "starter_line"} for e in commons), (theme, band)


@pytest.mark.parametrize("mutation", ["no_marker", "wrong_marker", "unboxed", "over_cap"])
def test_a_generator_mutation_of_the_pool_is_caught(monkeypatch, mutation):
    doc = xdoc("mine")
    real = DX.spawn_entries

    def mutated(doc_, d, key=None):
        out = real(doc_, d, key)
        for e in out:
            c = e["condition"]
            if mutation == "no_marker":
                c.pop("neededNearbyBlocks")
            elif mutation == "wrong_marker":
                c["neededNearbyBlocks"] = [DATA["fishing"]["markers"]["2"]]
            elif mutation == "unboxed":
                c.pop("dimensions")
            elif mutation == "over_cap":
                e["level"] = "10-90"
        return out
    monkeypatch.setattr(DX, "spawn_entries", mutated)
    assert pool_problems(D.build(doc), doc) != []


# ------------------------------------------------------------------------------------------------- the lent rod


def test_every_line_that_takes_the_pick_back_takes_the_lent_rod_too():
    doc = xdoc("mine")
    files = D.build(doc)
    pick, lent = D.pick_match(doc), DX.lent_rod_match()
    n = 0
    for rel, body in files.items():
        lines = body.splitlines()
        for i, ln in enumerate(lines):
            if pick in ln and "clear @s" in ln:
                n += 1
                assert lines[i + 1] == ln.replace(pick, lent), (rel, i)
    assert n >= 3, "the end of a run, the keeper's stale pass and the rips all take the pick"
    plain = copy.deepcopy(doc)
    plain["dungeons"][0]["rooms"] = [r for r in plain["dungeons"][0]["rooms"] if r["kind"] != "fishing_room"]
    assert not any(lent in b for b in D.build(plain).values()), "no fishing room, no lent rod"


def test_the_rod_is_lent_at_the_first_step_in_and_taken_back_at_the_far_rip(mk):
    doc, w = mk()
    p, s = start(doc, w)
    r = into(doc, w, p, "fish")
    assert len(lent_rods(p)) == 1
    into(doc, w, p, "fish", dx=8)
    assert len(lent_rods(p)) == 1, "lent once a run"
    w.call("cobblers:dungeons/far", PS.Ctx(p, p.dim, p.pos))
    assert lent_rods(p) == [] and not any(i[0] == "minecraft:iron_pickaxe" for i in p.inventory)


def test_the_back_rip_and_a_logout_stale_pass_take_it_too(mk):
    doc, w = mk()
    p, s = start(doc, w)
    into(doc, w, p, "fish")
    assert lent_rods(p)
    p.inventory = [i for i in p.inventory if i[0] != "minecraft:iron_pickaxe"]       # the pick gone: the keeper's pass finds the rod
    w.call("cobblers:dungeons/far", PS.Ctx(p, p.dim, p.pos))
    assert lent_rods(p) == []


# ------------------------------------------------------------------------------------------------- the band marker


def marker_cells(doc):
    return built(doc, "fish").meta["marker_cells"]


def test_the_slot_reset_sets_the_entrants_band_marker_and_the_shell_holds_band_ones(mk):
    doc, w = mk()
    p, s = start(doc, w)
    b = built(doc, "fish")
    cells = b.meta["marker_cells"]
    assert len(cells) == 3 and {c[0] for c in cells} == {b.meta["fishing"]["cx"] - 2, b.meta["fishing"]["cx"], b.meta["fishing"]["cx"] + 2}
    shell_blocks = {G.base(b.grid.block_at(*c)) for c in cells}
    assert shell_blocks == {DATA["fishing"]["markers"]["1"]}, "a bare shell is a band 1 pool"
    for band in range(1, 7):
        w.set(p.name, "dg.band", band)
        w.blocks.clear()
        reset_slot(w, p, s)
        for c in cells:
            if band == 1:        # an identical state: the setblock fails and the shell's block stands, as in the game
                assert w.blocks.get(tuple(c), DATA["fishing"]["markers"]["1"]) == DATA["fishing"]["markers"]["1"]
            else:
                assert w.blocks[tuple(c)] == DATA["fishing"]["markers"][str(band)], (band, c)


def test_the_marker_cells_sit_within_four_blocks_of_every_water_cell_and_under_the_pier():
    for theme in THEMES:
        doc = xdoc(theme)
        b = built(doc, "fish")
        m = b.meta["fishing"]
        for (mx, my, mz) in b.meta["marker_cells"]:
            assert (mx, mz) in [(m["cx"] + k, m["zm"]) for k in (-2, 0, 2)]
        for x in range(m["x0"], m["x1"] + 1):
            for z in range(m["z0"], m["z1"] + 1):
                assert min(abs(x - mx) for (mx, _y, _z) in b.meta["marker_cells"]) <= 2 and abs(z - m["zm"]) <= 3, (x, z)
                assert max(abs(x - mx) for (mx, _y, _z) in b.meta["marker_cells"]) <= 6
        under = {(m["cx"], pz) for pz in m["pier_z"]}
        assert (m["cx"], m["zm"]) in under


# ------------------------------------------------------------------------------------------------- a fished catch


def catch_in(doc, w, p, rid, species="mudkip"):
    r = TR.room_of(doc, rid)
    p.pos = [(r["ix0"] + r["ix1"]) / 2.0, float(r["floor_in"]), (r["iz0"] + r["iz1"]) / 2.0]
    w.run_callback("pokemon_captured", query={"pokemon": {"species": {"identifier": species}, "id": "pk-" + species, "is_shiny": 0}, "player": {"uuid": p.uid}})


def test_a_catch_in_the_fishing_room_weighs_as_a_nest_catch_in_a_live_run(mk):
    doc, w = mk()
    p, s = start(doc, w)
    t = DGR.load()
    for band in (1, 3, 5):
        w.set(p.name, "dg.band", band)
        w.set(p.name, "dg.gp", 0)
        catch_in(doc, w, p, "fish")
        assert w.get(p.name, "dg.gp") == DGR.catch_cp(t, "nest", band, doc), band
    p.party.clear()
    w.set(p.name, "dg.gp", 0)
    w.set(p.name, "dg.st", 2)
    catch_in(doc, w, p, "fish")
    assert w.get(p.name, "dg.gp") == 0, "before the clock runs a catch weighs nothing"


def test_a_credited_catch_is_said_aloud_in_points_to_a_tenth_and_only_in_a_live_run(mk):
    # 2026-10-17: the owner caught a fished Horsea and saw nothing count (a catch under 2 points raises no rate). Breaks if the credit
    # is silent again, if the line shows a wrong number, or if a catch before the clock runs is announced as credited.
    doc, w = mk()
    p, s = start(doc, w)
    t = DGR.load()
    for band in (1, 3, 5):
        w.set(p.name, "dg.band", band)
        w.set(p.name, "dg.gp", 0)
        p.messages.clear()
        catch_in(doc, w, p, "fish")
        cp = DGR.catch_cp(t, "nest", band, doc)
        assert (w.get("#cw", "dg.t"), w.get("#ct", "dg.t")) == (cp // 100, cp // 10 % 10), band
        said = [m for m in p.messages if "Caught: +" in m]
        assert len(said) == 1 and '"objective": "dg.t"' in said[0], p.messages
    w.set(p.name, "dg.st", 2)
    p.messages.clear()
    catch_in(doc, w, p, "fish")
    assert not [m for m in p.messages if "Caught: +" in m], "nothing is credited before the clock runs, so nothing is announced"


# ------------------------------------------------------------------------------------------------- the egg vendor


def vendors(w):
    return [e for e in w.ents if e.kind == "cobblemon:npc" and e.alive]


def buy(w, p, s, band, k, room_id="eggs"):
    w.call("cobblers:dungeons/room/night_shift/%s/s%d/take_b%d_%d" % (room_id, s["g"], band, k), PS.Ctx(p, p.dim, p.pos))


def one_egg_cycle(doc, w, p, s, band=1):
    """The whole sale: the vendor stands, bound; an egg is charged once, weighed once and given once; a second asks for nothing."""
    w.set(p.name, "dg.band", band)
    r = into(doc, w, p, "eggs")
    v = vendors(w)
    assert len(v) == 1 and v[0].nbt["NPCClass"] == "cobblers:" + DX.vendor_class(doc["dungeons"][0], r, s["g"], band), v
    assert {"dg.npc", "dg.s%d" % s["g"], DX.room_tag(r)} <= v[0].tags
    clock, gp = w.get(p.name, "dg.clock"), w.get(p.name, "dg.gp") or 0
    buy(w, p, s, band, 1)
    cost = DX.price_s(doc, r, band)
    species = DX.offers_of(r, band)[1]["species"]
    assert w.eggs == [(p.name, species)], w.eggs
    assert w.get(p.name, "dg.clock") == clock - cost * U1, "the price is clock seconds"
    assert w.get(p.name, "dg.gp") == gp + DX.nest_cp(doc, band), "an egg weighs as a nest catch"
    buy(w, p, s, band, 0)
    buy(w, p, s, band, 1)
    assert len(w.eggs) == 1, "one egg a run"
    assert w.get(p.name, "dg.clock") == clock - cost * U1, "and nothing more is charged"
    assert w.get(hold(s, r, "e"), "dg.rs") == 1


def test_the_vendor_is_spawned_bound_and_sells_one_egg_charged_and_weighed_once(mk):
    doc, w = mk()
    p, s = start(doc, w)
    one_egg_cycle(doc, w, p, s)


@pytest.mark.parametrize("band", [2, 4, 6])
def test_every_band_sells_its_own_species_at_its_own_price(mk, band):
    doc, w = mk()
    p, s = start(doc, w, band)
    one_egg_cycle(doc, w, p, s, band)


def test_the_reset_takes_the_vendor_away_and_the_next_run_can_buy_again(mk):
    doc, w = mk()
    p, s = start(doc, w)
    r = into(doc, w, p, "eggs")
    buy(w, p, s, 1, 0)
    assert len(w.eggs) == 1
    reset_slot(w, p, s)
    assert vendors(w) == [] and w.get(hold(s, r, "e"), "dg.rs") == 0 and w.get(hold(s, r), "dg.rs") == 0
    into(doc, w, p, "eggs")
    assert len(vendors(w)) == 1
    buy(w, p, s, 1, 2)
    assert len(w.eggs) == 2 and w.eggs[1][1] == DX.offers_of(r, 1)[2]["species"]


def test_a_sale_never_ends_the_run_and_never_happens_outside_it(mk):
    doc, w = mk()
    p, s = start(doc, w)
    r = into(doc, w, p, "eggs")
    cost = DX.price_s(doc, r, 1)
    w.set(p.name, "dg.clock", (cost + DATA["eggs"]["price"]["min_left_s"]) * U1 - 1)
    buy(w, p, s, 1, 0)
    assert w.eggs == [] and w.get(p.name, "dg.clock") == (cost + DATA["eggs"]["price"]["min_left_s"]) * U1 - 1, "too little clock: no sale, no charge"
    assert w.get(hold(s, r, "e"), "dg.rs") == 0, "and the egg is still for sale"
    w.set(p.name, "dg.clock", (cost + DATA["eggs"]["price"]["min_left_s"]) * U1)
    buy(w, p, s, 1, 0)
    assert len(w.eggs) == 1 and w.get(p.name, "dg.clock") == DATA["eggs"]["price"]["min_left_s"] * U1
    reset_slot(w, p, s)
    into(doc, w, p, "eggs")
    w.set(p.name, "dg.st", 2)
    buy(w, p, s, 1, 0)
    assert len(w.eggs) == 1, "before the clock runs there is no sale"
    w.set(p.name, "dg.st", 3)
    w.set(p.name, "dg.band", 2)
    buy(w, p, s, 1, 0)
    assert len(w.eggs) == 1, "a button of another band's vendor sells nothing"


def test_the_dialogue_lists_every_offer_with_its_description_and_each_button_runs_its_own_species(tmp_path_factory):
    doc = xdoc("flooded_ruin", per_dungeon=4)
    files = D.build(doc)
    d = doc["dungeons"][0]
    slots = [s for s in D.slots(doc) if s["dungeon"] is d]
    assert len(slots) == 4
    for s in slots:
        for band in range(1, 7):
            name = DX.vendor_class(d, {"id": "eggs"}, s["g"], band)
            dlg = json.loads(files["data/cobblers/dialogues/%s.json" % name])
            cls = json.loads(files["data/cobblers/npcs/%s.json" % name])
            assert cls["interaction"] == {"type": "dialogue", "dialogue": "cobblers:" + name} and cls["isInvulnerable"]
            assert "party" not in cls and "battleConfiguration" not in cls, "a vendor does not fight"
            page = dlg["pages"][0]
            offers = DATA["eggs"]["offers"][str(band)]
            text = " ".join(page["lines"])
            opts = page["input"]["options"]
            assert len(opts) == len(offers) + 1
            for o, opt in zip(offers, opts):
                assert o["name"] in text and o["desc"] in text, (band, o)
                fn = re.search(r"function (\S+)'\);", opt["action"][0]).group(1)
                body = files["data/cobblers/function/dungeons/" + fn.split("dungeons/")[1] + ".mcfunction"]
                assert "givepokemonegg @s %s\n" % o["species"] in body and "/s%d/" % s["g"] in fn
                assert opt["action"][1] == "q.dialogue.close();"
            assert opts[-1]["value"] == "cancel"
            assert str(DATA["eggs"]["price"]["clock_s_by_band"][str(band)]) in page["lines"][0]
    assert not any(k for k in files if "_egg_" in k and "_s5_" in k), "no vendor for a slot that does not exist"


# ------------------------------------------------------------------------------------------------- the fossil


def cell_of(w, doc, s, j=None):
    b = built(doc, "dig")
    return b, [tuple(c) for c in b.meta["fossil"]["spots"]]


def enter_dig(doc, w, p, s, roll):
    reset_slot(w, p, s)
    w.rolls = [roll]
    return into(doc, w, p, "dig")


def mined_calcite_obj(doc):
    return "dg.m%d" % {b: i for i, b, _v in DGR.counted(doc)}["minecraft:calcite"]


def fossil_cycle(doc, w, p, s, roll, band=1):
    """Roll j, find the fossil where the roll put it, mine it: the fossil is given from the band's table, weighed by the
    mined stat, the room is cleared; the dig cells are untouched elsewhere."""
    w.set(p.name, "dg.band", band)
    b, spots = cell_of(w, doc, s)
    r = enter_dig(doc, w, p, s, roll)
    me = hold(s, r)
    assert w.get(me, "dg.rs") == 1 and w.get(me + "f", "dg.rs") == roll
    dig, calc = DATA["fossils"]["dig"]["mine"], DATA["fossils"]["block"]
    holders = [c for c in spots if w.blocks.get(c) == calc]
    assert holders == [spots[roll]], "exactly one fossil block, where the roll put it"
    assert all(w.blocks.get(c, dig) == dig for c in spots if c != spots[roll])
    inv = len(p.inventory)
    w.passes(1)
    assert len(p.inventory) == inv, "nothing is given before the block is mined"
    obj = mined_calcite_obj(doc)
    w.blocks[spots[roll]] = "minecraft:air"
    w.set(p.name, obj, 1)
    gp = w.get(p.name, "dg.gp") or 0
    w.passes(1)
    got = [i[0] for i in p.inventory][inv:]
    table = [e[0] for e in DX.fossils_of(r, band)]
    assert len(got) == 1 and got[0] in table, (got, table)
    assert w.get(me, "dg.rs") == 2, "the room is cleared"
    assert w.get(p.name, "dg.gp") == gp + DATA["fossils"]["greed_cp"], "GREED's mined count weighs the fossil"
    w.passes(2)
    assert len([i for i in p.inventory if i[0].endswith("fossil") or "fossilized" in i[0]]) == 1, "given once"
    return got[0]


@pytest.mark.parametrize("roll", range(8))
def test_the_fossil_is_rolled_found_given_and_weighed_for_every_spot(mk, roll):
    doc, w = mk()
    p, s = start(doc, w)
    fossil_cycle(doc, w, p, s, roll)


def test_each_band_gives_a_fossil_from_its_own_table(mk):
    doc, w = mk()
    p, s = start(doc, w)
    r = TR.room_of(doc, "dig")
    seen = set()
    for band in range(1, 7):
        table = DX.fossils_of(r, band)
        for i in range(len(table)):
            reset_slot(w, p, s)
            w.rolls = [i]
            w.set(p.name, "dg.band", band)
            b, spots = cell_of(w, doc, s)
            into(doc, w, p, "dig")
            w.blocks[spots[w.get(hold(s, r, "f"), "dg.rs")]] = "minecraft:air"
            w.rolls = [i]
            inv = len(p.inventory)
            w.passes(1)
            assert [x[0] for x in p.inventory][inv:] == [table[i][0]], (band, i)
            seen.add(table[i][0])
    assert len(seen) == 15, "all fifteen fossils are some band's"


def test_the_reset_puts_the_bay_back_and_the_next_run_rolls_again(mk):
    doc, w = mk()
    p, s = start(doc, w)
    fossil_cycle(doc, w, p, s, 3)
    b, spots = cell_of(w, doc, s)
    r = TR.room_of(doc, "dig")
    reset_slot(w, p, s)
    calc, dig = DATA["fossils"]["block"], DATA["fossils"]["dig"]["mine"]
    assert w.get(hold(s, r), "dg.rs") == 0 and w.get(hold(s, r, "f"), "dg.rs") == 0
    cells =[(x, y, z) for x in range(b.meta["fossil"]["x0"] + 1, b.meta["fossil"]["x1"]) for y in range(r["floor_in"], r["floor_in"] + 3)
             for z in range(r["iz0"], r["iz0"] + 3)]
    assert all(w.blocks[c] == (calc if c == spots[0] else dig) for c in cells), "every dig cell is back, the fossil at variant 0"
    w.rolls = [6]
    into(doc, w, p, "dig")
    assert w.blocks[spots[6]] == calc and w.blocks[spots[0]] == dig
    inv = len(p.inventory)
    w.passes(2)
    assert len(p.inventory) == inv, "a second run's fossil is not already given"


def test_a_member_outside_the_room_or_before_the_roll_is_given_nothing(mk):
    doc, w = mk()
    p, s = start(doc, w)
    b, spots = cell_of(w, doc, s)
    reset_slot(w, p, s)
    w.blocks[spots[0]] = "minecraft:air"                      # mined by someone who never stood in the room
    inv = len(p.inventory)
    w.passes(2)
    assert len(p.inventory) == inv


# ------------------------------------------------------------------------------------------------- generator mutations


def mutate_kind(monkeypatch, kind, fn):
    real = R.KINDS[kind]

    def wrapped(doc, d, slot, room, theme):
        return fn(real(doc, d, slot, room, theme), room)
    monkeypatch.setitem(R.KINDS, kind, wrapped)


def test_mutation_a_bay_without_its_lintel_is_named(monkeypatch):
    def no_lintel(res, room):
        res = dict(res)
        ops = list(res["blocks"])
        ops[0] = ("fill",) + tuple([ops[0][1]]) + tuple(ops[0][2:])
        x0, y0, z0, x1, y1, z1 = ops[0][1]
        ops[0] = ("fill", (x0, y0, z0, x1, y1 - 1, z1), ops[0][2])             # the frame only, one row short: no lintel
        res["blocks"] = ops
        return res
    mutate_kind(monkeypatch, "fossil_chamber", no_lintel)
    probs = R.problems(xdoc("mine"))
    assert any("nothing solid over the dig cell" in p or "expand" in p or "overwrote" in p for p in probs), probs


def test_mutation_a_dig_fill_one_cell_too_wide_breaks_the_pick_count(monkeypatch):
    def wide(res, room):
        res = dict(res)
        ops = list(res["blocks"])
        x0, y0, z0, x1, y1, z1 = ops[1][1]
        ops[1] = ("fill", (x0 - 1, y0, z0, x1 + 1, y1, z1), ops[1][2])
        res["blocks"] = ops
        return res
    mutate_kind(monkeypatch, "fossil_chamber", wide)
    probs = R.problems(xdoc("mine"))
    assert any("the rift pick can break" in p or "frame" in p for p in probs), probs


def test_mutation_a_pool_without_its_bed_is_named(monkeypatch):
    def no_bed(res, room):
        res = dict(res)
        res["blocks"] = list(res["blocks"])[1:]
        return res
    mutate_kind(monkeypatch, "fishing_room", no_bed)
    probs = R.problems(xdoc("mine"))
    assert any("bed" in p or "no floor" in p for p in probs), probs


def test_mutation_a_pool_two_deep_is_a_pit(monkeypatch):
    def deep(res, room):
        res = dict(res)
        ops = list(res["blocks"])
        x0, y0, z0, x1, y1, z1 = ops[0][1]
        ops[1] = ("fill", (x0, y0, z0, x1, y0 + 1, z1), "minecraft:water")        # water in the bed's row and the row above it
        res["blocks"] = ops
        return res
    mutate_kind(monkeypatch, "fishing_room", deep)
    probs = R.problems(xdoc("mine"))
    assert probs, "a bed of water is no bed"


def egg_variant(monkeypatch, edit):
    def mut(res, room):
        res = dict(res)
        res["functions"] = {k: edit(k, list(v)) for k, v in res["functions"].items()}
        return res
    mutate_kind(monkeypatch, "egg_room", mut)


@pytest.mark.parametrize("mutation", ["no_guard", "no_charge", "no_greed"])
def test_mutation_an_egg_sale_that_forgets_a_rule_fails_the_cycle(monkeypatch, tmp_path_factory, mutation):
    def edit(name, lines):
        if not name.startswith("take_"):
            return lines
        if mutation == "no_guard":
            return [l for l in lines if "return run tellraw" not in l or "dg.clock" in l]
        if mutation == "no_charge":
            return [l for l in lines if "scoreboard players remove @s dg.clock" not in l]
        return [l for l in lines if "greed/add" not in l]
    egg_variant(monkeypatch, edit)
    doc, w = world("mine", tmp_path_factory, salt="egg_" + mutation)
    p, s = start(doc, w)
    with pytest.raises(AssertionError):
        one_egg_cycle(doc, w, p, s)


def test_mutation_a_fossil_room_that_never_gives_fails_the_cycle(monkeypatch, tmp_path_factory):
    def mut(res, room):
        res = dict(res)
        res["functions"] = dict(res["functions"])
        res["functions"]["got"] = [l for l in res["functions"]["got"] if "loot give" not in l]
        return res
    mutate_kind(monkeypatch, "fossil_chamber", mut)
    doc, w = world("mine", tmp_path_factory, salt="fossil_nogive")
    p, s = start(doc, w)
    with pytest.raises(AssertionError):
        fossil_cycle(doc, w, p, s, 2)

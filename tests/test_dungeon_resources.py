"""The resources rooms' piles (tools/dungeon_resources.py, data/dungeon_resources.json), unit RESOURCES2, 2026-10-10.

The builder's own tests (the independent audit is another agent's). What they prove, and how each avoids sharing the
builder's derivation:

  the table         the DATA FILE's counts are compared with the content a room really ends with: the room's GENERATED reset
                    lines are replayed on a small model of the world for each band (setblock, `execute if score @s dg.band
                    matches N..`, the scoreboard sets), and every ore block it leaves is counted by block id. Nothing is read
                    from the generator's own plan (`meta`) to decide a pass.
  per band          band 1 holds only coal, iron and copper; nothing but diamond from band 5; the cache (the raw Mega stone and
                    the ancient debris) exists in the replayed world only at the bands the data allows, and its loot tables are
                    in the pack for exactly those bands.
  the seam          its mix per band equals tools/economy_sim.py's own World.seam_face (the economy's assumption), read from the
                    sim, not from the data.
  the budget        the sim's bank prices, rates and gathering tiers decide it (tools/dungeon_resources.py budget()); a
                    mutated table (a second Mega stone, twice the diamonds) must fail it.
  re-armed          mine every ore cell and open the chest, run the room's tick (one greed/take per block, once), then run the
                    reset at another band: the room holds that band's content and every watcher is armed again.
  the pick          its generated can_break is the engine's base list, the seam's blocks, the table's ore blocks for the theme's
                    family and the secret block, computed here from the theme file and the data, and every ore block a room
                    can hold is on it.
  no void           every cell the pick can break, at every band, is inside the room's interior with every neighbour solid or
                    the room's own air; and breaking all of them (every band at once) opens nothing that was closed (a flood
                    fill written here, not the module's).
  mutations         the GENERATOR changed with the data untouched: the wall-ore check that lets hull-wall cells be ore, the
                    cache at band 1, a diamond in band 1's seam, a table that places fewer ores than it counts. Each is caught.

Not covered: anything in a running Minecraft (a chest's loot table unpacking in adventure mode, the mining times, the stepped
heaps being climbed, the greed ladder's reading of the calls).
"""
from __future__ import annotations

import copy
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import dungeon as D  # noqa: E402
import dungeon_grid as G  # noqa: E402
import dungeon_resources as X  # noqa: E402
import dungeon_rooms as R  # noqa: E402
import economy_sim as E  # noqa: E402

BASE = D.load()
DATA = json.loads((ROOT / "data" / "dungeon_resources.json").read_text(encoding="utf-8"))
THEMES = json.loads((ROOT / "data" / "dungeon_themes.json").read_text(encoding="utf-8"))["themes"]
DUNGEONS = [d for d in BASE["dungeons"] if R.has_rooms(d)]
BANDS = (1, 2, 3, 4, 5, 6)
ORE_RES = {blk: res for res, e in DATA["resources"].items() for blk in e["blocks"].values()}
GREED = json.loads((ROOT / "data" / "dungeon_greed.json").read_text(encoding="utf-8"))

_BUILDS = {}


def room_slots():
    """[(dungeon, slot)] for every slot of every rooms dungeon (the four slots carry different variants)."""
    return [(s["dungeon"], s) for s in D.slots(BASE) if R.has_rooms(s["dungeon"])]


def resource_rooms(d, s):
    key = (d["id"], s["g"])
    if key not in _BUILDS:
        _BUILDS[key] = [b for b in R.slot_build(BASE, d, s) if b.room["kind"] == "resources"]
    return _BUILDS[key]


CASES = [(d, s) for d, s in room_slots() if resource_rooms(d, s)]
IDS = ["%s-s%d" % (d["id"], s["k"]) for d, s in CASES]


# ------------------------------------------------------------------------------------------------- a small model of the world


class World:
    """The blocks of one room as the generated hook lines leave them. Reads only the lines' text."""

    def __init__(self, b):
        self.b = b
        self.blocks = {}
        self.scores = {}
        self.credits = []          # the cp each greed/add credited
        self.opened = set()

    def get(self, pos):
        if pos in self.blocks:
            return self.blocks[pos]
        return self.b.grid.block_at(*pos) if self.b.grid.inside(*pos) else "minecraft:air"

    def run(self, lines, band):
        for ln in lines:
            self.line(ln.strip(), band)

    def line(self, ln, band):
        if not ln or ln.startswith("#"):
            return
        m = re.match(r"^execute if score @s dg\.band matches (\d+)(\.\.)? run (.*)$", ln)
        if m:
            n, open_ = int(m.group(1)), bool(m.group(2))
            if (band >= n) if open_ else (band == n):
                self.line(m.group(3), band)
            return
        m = re.match(r"^setblock (-?\d+) (-?\d+) (-?\d+) (\S+)$", ln)
        if m:
            self.blocks[tuple(int(v) for v in m.groups()[:3])] = m.group(4)
            return
        m = re.match(r"^scoreboard players set (\S+) dg\.rs (\d+)$", ln)
        if m:
            self.scores[m.group(1)] = int(m.group(2))
            return
        m = re.match(r"^execute if score (\S+) dg\.rs matches (\d+) if block (-?\d+) (-?\d+) (-?\d+) minecraft:air run scoreboard players set (\S+) dg\.rs (\d+)$", ln)
        if m:
            h, v, x, y, z, h2, v2 = m.groups()
            if self.scores.get(h) == int(v) and self.get((int(x), int(y), int(z))) == "minecraft:air":
                self.scores[h2] = int(v2)
            return
        m = re.match(r"^execute if score (\S+) dg\.rs matches (\d+) unless data block (-?\d+) (-?\d+) (-?\d+) LootTable run function (\S+)$", ln)
        if m:
            h, v, x, y, z, fn = m.groups()
            pos = (int(x), int(y), int(z))
            if self.scores.get(h) == int(v) and pos in self.opened:
                assert fn.endswith("/cache_open"), fn
                self.run(self.b.functions["cache_open"], band)
            return
        m = re.match(r"^scoreboard players set (#gv) (\S+) (\d+)$", ln)
        if m:
            self.scores["#gv"] = int(m.group(3))
            return
        if ln == "function cobblers:dungeons/greed/add":
            self.credits.append(self.scores.get("#gv", 0))
            return
        m = re.match(r"^execute if score (\S+) dg\.rs matches (\d+) run (.*)$", ln)
        if m:
            h, v, rest = m.groups()
            if self.scores.get(h) == int(v) and rest.startswith("scoreboard players set "):
                self.line(rest, band)
            return

    def ore_cells(self, pick):
        """{pos: block} for every cell of the room (grid plus replayed writes) whose block is one the pick may break."""
        out = {}
        g = self.b.grid
        for name in g.names():
            if G.base(name) in pick:
                import numpy as np
                for p in np.argwhere(g.a == g.idx[name]):
                    out[tuple(int(v) + o for v, o in zip(p, g.box[:3]))] = name
        for pos, blk in self.blocks.items():
            if G.base(blk) in pick:
                out[pos] = blk
            else:
                out.pop(pos, None)
        return out

    def chest(self):
        return {pos: blk for pos, blk in self.blocks.items() if blk.startswith("minecraft:chest")}


def reset_lines(b):
    return b.functions["reset"]


def tick_lines(b):
    return b.functions["tick"]


def dungeon_pick(d):
    """The set of block ids the dungeon's pick may break, computed from the theme file and the data (not from tools/)."""
    th = THEMES[d["theme"]]
    recs = R.all_records(d)
    out = set(BASE["engine"]["rift_pick"]["can_break"])
    if any(r["kind"] == "resources" for r in recs):
        out |= {e["block"] for e in th["seam"]["blocks"]}
        fam = DATA["themes"][d["theme"]]["family"]
        for res, e in DATA["table"].items():
            out.add(DATA["resources"][res]["blocks"][fam])
    if any(s.get("type", "cracked") == "cracked" for r in recs for s in r.get("secrets") or []):
        out.add(th["shapes"]["secret_block"])
    return out


def expected_row(d, band):
    """{resource: blocks} a room of this dungeon must end with at `band`, from the data file."""
    row = Counter()
    for res, e in DATA["table"].items():
        if e["min_band"] <= band <= e["max_band"]:
            row[res] += int(e["counts"].get(str(band), 0))
    if DATA["themes"][d["theme"]].get("seam", "table") == "table":
        for res, n in DATA["seam"][str(band)].items():
            row[res] += n
    return +row


def replay(b, band, pick):
    w = World(b)
    w.run(reset_lines(b), band)
    return w, w.ore_cells(pick)


def count_by_resource(cells):
    return Counter(ORE_RES[G.base(blk)] for blk in cells.values() if G.base(blk) in ORE_RES)


# ------------------------------------------------------------------------------------------------- the data


def test_the_table_is_consistent():
    assert X.check_data(BASE) == []


def test_every_table_row_has_a_why_and_a_count_for_each_band_it_names():
    for res, e in DATA["table"].items():
        assert e["why"].strip(), res
        assert set(e["counts"]) == {str(b) for b in range(e["min_band"], e["max_band"] + 1)}, res


def test_the_seam_mix_is_the_economy_sims_own():
    w = E.World(E.load_docs())
    for band in BANDS:
        sim = Counter(n.replace("_ore", "") for n in w.seam_face(band))
        assert dict(sim) == {k: v for k, v in DATA["seam"][str(band)].items()}, band


def test_early_bands_hold_nothing_great_and_diamonds_wait_for_band_5():
    rows = {band: X.table_row(band) for band in BANDS}
    assert set(rows[1]) == {"coal", "iron", "copper"} == set(rows[2]) | set()
    for band in (1, 2):
        assert not (set(rows[band]) & {"lapis", "redstone", "gold", "emerald", "diamond"})
    for band in (3, 4):
        assert "diamond" not in rows[band]
    for band in (5, 6):
        assert rows[band].get("diamond", 0) >= 2
    assert "emerald" not in rows[4] and rows[5].get("emerald") == 1


def test_the_budget_holds_and_names_every_band():
    out = X.budget(BASE)
    assert {b for b, _v, _d in out} == set(BANDS)
    over = [x for x in out if x[1] != "ok"]
    assert not over, over


def _with_data(monkeypatch, edit):
    doc = copy.deepcopy(DATA)
    edit(doc)
    monkeypatch.setitem(X._DATA, str(X.DATA_PATH), doc)


def test_a_second_mega_stone_or_double_the_diamonds_fails_the_budget(monkeypatch):
    _with_data(monkeypatch, lambda d: d["cache"]["items"]["mega"]["count_by_band"].update({"6": 2}))
    assert any(v == "OVER" and "mega" in det for _b, v, det in X.budget(BASE))
    _with_data(monkeypatch, lambda d: d["table"]["diamond"]["counts"].update({"5": 4, "6": 6}))
    assert any(v == "OVER" and "diamond" in det for _b, v, det in X.budget(BASE))
    _with_data(monkeypatch, lambda d: d["table"]["gold"]["counts"].update({"6": 60}))
    assert any(v == "OVER" and det.startswith("value") for _b, v, det in X.budget(BASE))


# ------------------------------------------------------------------------------------------------- the rooms


def band_findings(b, d):
    """Per band: the ore a room ends with equals the data file's counts for that band."""
    pick = dungeon_pick(d)
    bad = []
    for band in BANDS:
        _w, cells = replay(b, band, pick)
        got, want = dict(count_by_resource(cells)), dict(expected_row(d, band))
        if got != want:
            bad.append("band %d: %s, the table says %s" % (band, got, want))
    return bad


def cache_findings(b, d):
    """The cache chest stands at exactly the bands the data gives one, with a loot table that is in the pack."""
    files = X.pack_files(BASE)
    allowed = {int(k) for e in DATA["cache"]["items"].values() for k in e["count_by_band"]}
    bad = []
    for band in BANDS:
        w, _cells = replay(b, band, dungeon_pick(d))
        chests = w.chest()
        if band in allowed:
            if len(chests) != 1:
                bad.append("band %d: %d chests" % (band, len(chests)))
                continue
            (blk,) = chests.values()
            tid = re.search(r'LootTable:"([^"]+)"', blk).group(1)
            if "data/%s/loot_table/%s.json" % tuple(tid.split(":")) not in files or not tid.endswith("/b%d" % band):
                bad.append("band %d: loot table %s is not in the pack for this band" % (band, tid))
        elif chests:
            bad.append("band %d holds a chest and the data gives none" % band)
    return bad


@pytest.mark.parametrize("d,s", CASES, ids=IDS)
def test_each_band_ends_with_the_tables_ore(d, s):
    for b in resource_rooms(d, s):
        assert band_findings(b, d) == []


def test_the_cache_tables_in_the_pack_are_the_datas_and_only_for_the_bands_that_hold_one():
    files = X.pack_files(BASE)
    allowed = {int(k) for e in DATA["cache"]["items"].values() for k in e["count_by_band"]}
    assert {int(re.search(r"b(\d+)\.json$", p).group(1)) for p in files} == allowed
    for p, text in files.items():
        band = int(re.search(r"b(\d+)\.json$", p).group(1))
        tab = json.loads(text)
        items = {pool["entries"][0]["name"]: pool["entries"][0]["functions"][0]["count"] for pool in tab["pools"]}
        want = {e["item"]: e["count_by_band"][str(band)] for e in DATA["cache"]["items"].values() if str(band) in e["count_by_band"]}
        assert items == want, p


@pytest.mark.parametrize("d,s", CASES, ids=IDS)
def test_the_cache_chest_stands_at_the_bands_that_hold_one(d, s):
    for b in resource_rooms(d, s):
        assert cache_findings(b, d) == []


def test_the_mega_stone_is_the_raw_one_and_never_a_keyed_one():
    keyed = {"mega_showdown:" + n for n in ("aggronite", "charizardite_x", "charizardite_y", "gengarite", "mewtwonite_x", "mewtwonite_y")}
    for e in DATA["cache"]["items"].values():
        assert e["item"] not in keyed
    assert DATA["cache"]["items"]["mega"]["item"] == "mega_showdown:mega_stone"
    assert DATA["cache"]["items"]["debris"]["item"] == "minecraft:ancient_debris"
    for p, text in X.pack_files(BASE).items():
        names = [pool["entries"][0]["name"] for pool in json.loads(text)["pools"]]
        assert names == ["mega_showdown:mega_stone", "minecraft:ancient_debris"], p


def greed_cp_of(item):
    if item in GREED["items"]:
        return GREED["items"][item]["cp"]
    return next(g["cp"] for g in GREED["groups"].values() if item in g["ids"])


def cache_value(band):
    """The cache's value at `band` in cp, from the two data files and nothing of the generator's."""
    return sum(greed_cp_of(e["item"]) * e["count_by_band"][str(band)] for e in DATA["cache"]["items"].values()
               if str(band) in e["count_by_band"])


@pytest.mark.parametrize("d,s", CASES, ids=IDS)
def test_a_reset_re_arms_the_piles_and_the_cache_pays_its_points_once(d, s):
    secret = {THEMES[d["theme"]]["shapes"]["secret_block"]}
    pick = dungeon_pick(d) - secret
    legacy = 24 if DATA["themes"][d["theme"]].get("seam", "table") != "table" else 0       # the jungle's produce face
    for b in resource_rooms(d, s):
        tick = tick_lines(b)
        # GREED's mined stats weigh the blocks: no pile or vein block has a hook (a second count)
        assert not any("greed/take" in ln or re.search(r"r\d+o\d+", ln) for ln in tick + reset_lines(b)), "a per-block hook would count twice"
        for band in (1, 3, 5, 6):
            w, cells = replay(b, band, pick)
            assert len(cells) == sum(expected_row(d, band).values()) + legacy
            for pos in cells:
                w.blocks[pos] = "minecraft:air"                 # mined
            for pos in w.chest():
                w.opened.add(pos)
            w.run(tick, band)
            w.run(tick, band)                                    # a second pass pays nothing again
            assert w.credits == ([cache_value(band)] if w.chest() else []), (band, w.credits, cache_value(band))
            # the slot's reset at ANOTHER band puts that band's room back and arms the cache again
            for other in (2, 5):
                w.run(reset_lines(b), other)
                assert dict(count_by_resource(w.ore_cells(pick))) == dict(expected_row(d, other)), (band, other)
                w.opened.clear()
                w.credits.clear()
                w.run(tick, other)
                assert w.credits == []                           # nothing opened, nothing paid
                for pos in w.chest():
                    w.opened.add(pos)
                w.run(tick, other)
                assert w.credits == ([cache_value(other)] if w.chest() else [])


def test_every_block_the_piles_can_hold_has_a_greed_row_and_a_full_take_stays_under_the_cap():
    rate = GREED["rate"]
    cap_cp = (rate["cap"] - rate["base"]) * rate["per_step_cp"]
    for res, e in DATA["resources"].items():
        for blk in e["blocks"].values():
            row = GREED["blocks"][blk]
            assert row["cp"] > 0 and row["drops"] == {e["item"]: sum(e["drop"]) / 2}, blk
    for theme in DATA["themes"]:
        for band in BANDS:
            assert X.greed_cp(theme, band) < cap_cp, (theme, band)
        assert X.greed_cp(theme, 6) > X.greed_cp(theme, 3) > X.greed_cp(theme, 1)


def test_a_table_three_times_as_rich_would_hit_the_clock_cap(monkeypatch):
    rate = GREED["rate"]
    cap_cp = (rate["cap"] - rate["base"]) * rate["per_step_cp"]

    def triple(d):
        for e in d["table"].values():
            e["counts"] = {k: 3 * v for k, v in e["counts"].items()}
    _with_data(monkeypatch, triple)
    assert X.greed_cp("mine", 6) >= cap_cp


def _neighbours(x, y, z):
    return ((x + 1, y, z), (x - 1, y, z), (x, y + 1, z), (x, y - 1, z), (x, y, z + 1), (x, y, z - 1))


def room_findings(b, d):
    """Independent no-void check of one built room: every cell the pick can break (every band) is interior, every neighbour
    solid or the room's own air, and breaking them all opens nothing closed (a flood fill, written here)."""
    r = b.room
    g = b.grid
    pick = dungeon_pick(d)
    secret = {THEMES[d["theme"]]["shapes"]["secret_block"]}
    cells = set()
    for band in BANDS:
        _w, c = replay(b, band, pick - secret)
        cells |= set(c)
    # the shell's own band-1 cells too
    cells |= {p for p in World(b).ore_cells(pick - secret)}
    bad = []
    for (x, y, z) in sorted(cells):
        if not (r["ix0"] <= x <= r["ix1"] and r["iz0"] <= z <= r["iz1"] and r["y_lo"] <= y <= r["ceil_y"] - 2):
            bad.append("outside the interior: %s" % ((x, y, z),))
            continue
        for n in _neighbours(x, y, z):
            if not g.inside(*n):
                bad.append("%s reaches past the grid" % ((x, y, z),))
                break
            blk = g.block_at(*n)
            if G.base(blk) in G.AIR and not (r["ix0"] <= n[0] <= r["ix1"] and r["iz0"] <= n[2] <= r["iz1"] and r["y_lo"] <= n[1] <= r["ceil_y"] - 2):
                bad.append("%s touches air outside the interior at %s" % ((x, y, z), n))
                break
    if bad:
        return bad[:3]
    # a flood fill: what the room's air reaches, before and after every one of those cells is air
    cls = g.cls()
    start = R.room_start(r)

    def flood(extra_air):
        seen, stack = {start}, [start]
        while stack:
            c = stack.pop()
            for n in _neighbours(*c):
                if n in seen or not g.inside(*n):
                    continue
                passable = n in extra_air or cls[g.local(*n)] in (G.PASS, G.WATER)
                if passable:
                    seen.add(n)
                    stack.append(n)
        return seen
    before, after = flood(set()), flood(cells)
    new = after - before - cells
    if new:
        return ["breaking every pile cell opens %d closed cells, e.g. %s" % (len(new), sorted(new)[0])]
    return []


@pytest.mark.parametrize("d,s", CASES, ids=IDS)
def test_no_cell_the_pick_can_break_opens_the_room_to_the_void(d, s):
    for b in resource_rooms(d, s):
        assert room_findings(b, d) == []
        assert X.leak_problems("room", b) == []


@pytest.mark.parametrize("d,s", CASES, ids=IDS)
def test_the_picks_list_is_exactly_the_seam_the_piles_and_the_secret(d, s):
    give = D.pick_give(BASE, d)
    listed = set(re.search(r"can_break=\{predicates:\[\{blocks:\[([^\]]*)\]", give).group(1).replace('"', "").split(","))
    assert listed == dungeon_pick(d)
    assert set(R.pick_blocks(d)) | set(BASE["engine"]["rift_pick"]["can_break"]) == listed
    secret = THEMES[d["theme"]]["shapes"]["secret_block"]
    seen = set()
    for b in resource_rooms(d, s):
        for band in BANDS:
            w, _c = replay(b, band, listed)
            seen |= {G.base(blk) for blk in w.blocks.values()}
        seen |= {G.base(n) for n in b.grid.names()}
    extra = listed - set(BASE["engine"]["rift_pick"]["can_break"]) - {secret}
    assert extra <= seen, sorted(extra - seen)
    # nothing the rooms can hold from the table's ores is missing from the list
    held = {G.base(blk) for b in resource_rooms(d, s) for band in BANDS for blk in replay(b, band, listed)[0].blocks.values() if G.base(blk) in ORE_RES}
    assert held <= listed


@pytest.mark.parametrize("d,s", [c for c in CASES if c[0]["id"] == "night_shift"], ids=["night_shift-s%d" % c[1]["k"] for c in CASES if c[0]["id"] == "night_shift"])
def test_a_wall_vein_is_two_rows_of_one_ore_so_a_mined_column_is_a_pocket(d, s):
    pick = dungeon_pick(d) - {THEMES[d["theme"]]["shapes"]["secret_block"]}
    for b in resource_rooms(d, s):
        veins = {tuple(c["pos"]) for c in b.meta["deposits"]["cands"] if c["kind"] == "vein"}
        assert veins, "the mine's rock rooms hold wall veins"
        for band in BANDS:
            w, cells = replay(b, band, pick)
            for (x, y, z) in veins:
                if (x, y + 1, z) in veins:
                    lo, hi = w.get((x, y, z)), w.get((x, y + 1, z))
                    assert (lo in ORE_RES.keys()) == (hi in ORE_RES.keys()) and (lo == hi or lo not in ORE_RES), (band, (x, y, z), lo, hi)


def test_every_item_a_pile_or_the_cache_can_yield_is_listed_for_the_greed_table():
    listed = {i for i, _src in X.items_yielded()}
    want = {e["item"] for e in DATA["resources"].values()} | {e["item"] for e in DATA["cache"]["items"].values()}
    assert listed == want


# ------------------------------------------------------------------------------------------------- generator mutations


def _rebuild_resources_room(monkeypatch, d, slot):
    """The resources rooms of one slot built fresh under whatever the test has patched (the kit's cache cleared)."""
    monkeypatch.setattr(R, "_BUILT", {})
    return [b for b in R.slot_build(BASE, d, slot) if b.room["kind"] == "resources"]


def _lower_face():
    d = next(x for x in DUNGEONS if x["id"] == "night_shift")
    s = next(x for x in D.slots(BASE) if x["dungeon"]["id"] == "night_shift" and x["k"] == 1)
    return d, s


def test_mutation_wall_ore_allowed_in_the_hull_is_caught(monkeypatch):
    d, s = _lower_face()
    assert all(room_findings(b, d) == [] for b in resource_rooms(d, s))
    def hull_only(ctx, x, y, z, dx, dz, wall):
        # the interior bound turned inside out: only the hull's own wall column may hold ore (the fault the real check refuses)
        r = ctx.room
        interior = r["ix0"] <= x <= r["ix1"] and r["iz0"] <= z <= r["iz1"]
        return (not interior) and ctx.grid.inside(x, y, z) and ctx.air(x - dx, y, z - dz)
    monkeypatch.setattr(X, "backed", hull_only)
    found = []
    for b in _rebuild_resources_room(monkeypatch, d, s):
        found += room_findings(b, d)          # this file's own check, not the module's
    assert found, "ore in the hull wall was not caught"


def test_mutation_the_cache_at_band_1_is_caught(monkeypatch):
    d, s = _lower_face()
    assert all(cache_findings(b, d) == [] for b in resource_rooms(d, s))
    mega = DATA["cache"]["items"]["mega"]
    monkeypatch.setattr(X, "cache_items", lambda band: [("mega", mega["item"], 1)])
    monkeypatch.setattr(X, "cache_count", lambda band: 1)
    found = []
    for b in _rebuild_resources_room(monkeypatch, d, s):
        found += cache_findings(b, d)
    assert any("band 1" in f for f in found), found


def test_mutation_a_diamond_in_band_1s_seam_is_caught(monkeypatch):
    d, s = _lower_face()
    assert all(band_findings(b, d) == [] for b in resource_rooms(d, s))
    diamond = DATA["resources"]["diamond"]["blocks"][DATA["themes"]["mine"]["family"]]
    real = X.seam_face

    def mutant(theme_id, band, n):
        face = real(theme_id, band, n)
        return [diamond] + face[1:] if band == 1 else face
    monkeypatch.setattr(X, "seam_face", mutant)
    found = []
    for b in _rebuild_resources_room(monkeypatch, d, s):
        found += band_findings(b, d)
    assert any(f.startswith("band 1") for f in found), found


def test_mutation_a_generator_that_places_fewer_ores_than_the_table_counts_is_caught(monkeypatch):
    d, s = _lower_face()
    real = X.assign

    def short(cands, row, rg):
        out = real(cands, row, rg)
        out.pop(sorted(out)[0])
        return out
    monkeypatch.setattr(X, "assign", short)
    found = []
    for b in _rebuild_resources_room(monkeypatch, d, s):
        found += band_findings(b, d)
    assert len(found) == len(BANDS), found


def test_mutation_a_reset_that_forgets_to_arm_the_cache_is_caught(monkeypatch):
    d, s = _lower_face()
    bs = _rebuild_resources_room(monkeypatch, d, s)
    b = bs[0]
    keep = [ln for ln in reset_lines(b) if not re.match(r"^execute if score @s dg\.band matches \d+\.\. run scoreboard players set #s\d+r\d+k dg\.rs 1$", ln)]
    assert len(keep) < len(reset_lines(b))
    w = World(b)
    w.run(keep, 6)
    for pos in w.chest():
        w.opened.add(pos)
    w.run(tick_lines(b), 6)
    assert w.credits == []          # nothing was armed, nothing paid: the real reset's arming is what the test above counts

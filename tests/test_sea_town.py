"""The sea town ("Pacifidlog", working name): data/sea_town.json, tools/sea_town.py (plan, write, check, verify), the
sea_town settlement, services and earthworks it writes into data/placements.json, its data/towns.json record,
tools/ground.py's "sea_deck" ground kind, the Mart clerk sea_town_mart in data/traders.json, and its re-application
(tools/reapply.py R8).

Written by the test author, not by the session that designed the town or wrote tools/sea_town.py.

Independent sources: the canonical heightmap (tools/ground.Ground, plain, rounded: the seabed), data/world.json's
sea level, the rects, kinds and depth rules authored in data/sea_town.json, data/spawn_blocks.json and
data/spawn_block_policy.json (the scope text of each whitelist entry), the service templates' NBT, and the
committed earthwork commands, replayed here by a small fill/setblock interpreter (not the tool's Writer).

What is asserted: every raft and walk (and every bridge the plan draws) floats over water at least as deep as its
kind's rule; the jetty and the breakwater never cover ground above the deck, and each touches dry ground at its
landward end; replaying the committed commands leaves a deck block at y62 on every deck cell except where the
Centre's and the Mart's grade layer and the town plan's square paving stand, and every post reaches exactly the
seabed; sea_deck ground is y62 on every deck cell and the heightmap everywhere else; the Centre and the Mart are
seated at the deck (placement report) and the clerk stands at the walk level; `check` passes on the committed records
and fails on an altered copy, and `write` puts it right; `plan` refuses a raft over land; the commands pass
function_limits; no spawn-deciding block is placed that data/spawn_block_policy.json does not allow for the sea town
(water only as one y60 layer that replaces air); lanterns are the only light (no minecraft:light); the town is one
of R8's places and the fail-closed coverage check holds; `verify --world` passes a world holding the model and fails
one with a missing deck block, water on a deck or flowing water.

The heightmap is outside the repository (COBBLERS_SOURCE_ROOT); without it the heightmap tests SKIP. derived/ and
build/ are gitignored: without the placement report or the built packs those tests SKIP. A skip is not a pass.

Not covered, and it needs a running server: that water does not flow onto a deck or leak when the Centre's box is
cleared (verify --rcon does this), that a boat passes under nothing, that the lantern light model matches the game's
light, that the waystone, signs and barrels of boats work, that the clerk's shop opens, and how any of it looks.
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import sea_town as ST  # noqa: E402

PLAN = json.loads((ROOT / "data" / "sea_town.json").read_text(encoding="utf-8"))
DOC = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
TRADERS = json.loads((ROOT / "data" / "traders.json").read_text(encoding="utf-8"))
TOWNS = json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))
WORLD = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))
SPAWN_BLOCKS = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
POLICY = json.loads((ROOT / "data" / "spawn_block_policy.json").read_text(encoding="utf-8"))
SEA = int(WORLD["vertical"]["sea_level"])
SID = PLAN["settlement"]
EARTHWORKS = [p for p in DOC["placements"] if p.get("settlement") == SID and p.get("kind") == "earthwork"]
SERVICES = [p for p in DOC["placements"] if p.get("settlement") == SID and p.get("kind") == "service"]
DISTRICTS = {d["id"] for d in PLAN["districts"]}
BUILT_TOWN = ROOT / "build" / "datapacks" / "cobblers_towns" / "data" / "cobblers" / "function" / "towns" / "sea_town.mcfunction"


def _cells(rect):
    x0, z0, x1, z1 = rect
    return [(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)]


def _deck_elements():
    """(id, kind, rect, min depth, landfall) for every authored raft and walk, read straight from the data."""
    rules = PLAN["rules"]["min_depth"]
    out = [(r["id"], "square" if r.get("square") else "raft", r["rect"], rules["raft"], False) for r in PLAN["rafts"]]
    out += [(w["id"], w["kind"], w["rect"], w.get("min_depth", rules.get(w["kind"], 1)), bool(w.get("landfall")))
            for w in PLAN["walks"] if not w.get("decor")]
    return out


@pytest.fixture(scope="module")
def ground():
    import ground as G
    import terrain as T
    if not os.environ.get("COBBLERS_SOURCE_ROOT"):
        pytest.skip("COBBLERS_SOURCE_ROOT unset: the seabed comes from the canonical heightmap")
    try:
        return G.Ground()
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)


@pytest.fixture(scope="module")
def generated(ground):
    return ST.generate()


def _replay(cmds, model=None):
    """{(x, y, z): block} after the fill/setblock commands, `replace <block>` honoured; air removes a position."""
    model = {} if model is None else model
    for c in cmds:
        t = c.split()
        if not t or t[0].startswith("#"):
            continue
        if t[0] == "setblock":
            pts, blk, only = [(int(t[1]), int(t[2]), int(t[3]))], t[4], None
        elif t[0] == "fill":
            x0, y0, z0, x1, y1, z1 = (int(v) for v in t[1:7])
            blk = t[7]
            only = t[9] if len(t) > 9 and t[8] == "replace" else None
            pts = [(x, y, z) for x in range(min(x0, x1), max(x0, x1) + 1) for y in range(min(y0, y1), max(y0, y1) + 1)
                   for z in range(min(z0, z1), max(z0, z1) + 1)]
        else:
            continue
        for p in pts:
            if only is not None and model.get(p, "minecraft:air").split("[")[0] != only:
                continue
            if blk.split("[")[0] == "minecraft:air":
                model.pop(p, None)
            else:
                model[p] = blk
    return model


def _placed_blocks(cmds):
    """Every block id a fill or setblock writes (never the `replace` filter)."""
    out = []
    for c in cmds:
        t = c.split()
        if t and t[0] == "fill":
            out.append(t[7].split("[")[0].split("{")[0])
        elif t and t[0] == "setblock":
            out.append(t[4].split("[")[0].split("{")[0])
    return out


ALL_CMDS = [c for p in EARTHWORKS for c in p["commands"]]


# Without it the town could be dropped from the placements, or lose a district, and every check below would pass on
# nothing.
def test_the_placements_hold_the_settlement_both_services_and_one_earthwork_per_district():
    s = DOC["settlements"][SID]
    assert s["ground"] == "sea_deck"
    assert {p["id"] for p in SERVICES} == {sv["id"] for sv in PLAN["services"]} == {"sea_town_pokecenter",
                                                                                      "sea_town_pokemart"}
    assert {p["id"] for p in EARTHWORKS} == {"sea_town_%s" % d for d in DISTRICTS}
    assert len(ALL_CMDS) > 2000, len(ALL_CMDS)


# ------------------------------------------------------------------------------------- water, depth and landfall

# Without it a raft or pier is authored over the shelf's shallows or over land: a deck on the seabed, posts too short
# to see, no room for a boat, or a raft sitting on a beach. The depth (sea level - seabed) must meet the kind's rule.
@pytest.mark.parametrize("eid,kind,rect,need,landfall", [e for e in _deck_elements() if not e[4]],
                         ids=[e[0] for e in _deck_elements() if not e[4]])
def test_every_raft_and_walk_floats_over_water_at_least_its_rule_deep(ground, eid, kind, rect, need, landfall):
    assert SEA == 62
    shallowest = SEA - max(ground(x, z) for x, z in _cells(rect))
    assert shallowest >= need, (eid, kind, "shallowest %d, rule %d" % (shallowest, need))


# The bridges are drawn by the tool between the authored rects; without this a bridge could span a sand bar.
def test_every_bridge_the_plan_draws_is_over_water_at_least_its_rule_deep(ground):
    bridges = [e for e in ST.elements(PLAN) if e["kind"] == "bridge"]
    assert len(bridges) == len(PLAN["bridges"]) > 10
    need = PLAN["rules"]["min_depth"]["bridge"]
    bad = [(e["id"], SEA - max(ground(x, z) for x, z in _cells(e["rect"]))) for e in bridges
           if SEA - max(ground(x, z) for x, z in _cells(e["rect"])) < need]
    assert not bad, bad


# Without it the way in could stop short of the beach (a player lands in the sea) or run up onto the dunes and bury
# its deck under the sand. A landfall walk never covers ground above the deck, and its landward end touches dry
# ground (seabed at or above sea level, in the walk or beside its end); its other end is over water.
@pytest.mark.parametrize("wid", [w["id"] for w in PLAN["walks"] if w.get("landfall")])
def test_a_landfall_walk_touches_dry_ground_and_never_covers_ground_above_the_deck(ground, wid):
    w = next(q for q in PLAN["walks"] if q["id"] == wid)
    x0, z0, x1, z1 = w["rect"]
    cells = _cells(w["rect"])
    assert max(ground(x, z) for x, z in cells) <= SEA, (wid, "ground above the deck")
    along_x = x1 - x0 >= z1 - z0
    ends = ([[(x0, z) for z in range(z0, z1 + 1)], [(x1, z) for z in range(z0, z1 + 1)]] if along_x
            else [[(x, z0) for x in range(x0, x1 + 1)], [(x, z1) for x in range(x0, x1 + 1)]])
    step = [(-1, 0), (1, 0)] if along_x else [(0, -1), (0, 1)]

    def dry(end, d):
        return any(ground(x, z) >= SEA or ground(x + d[0], z + d[1]) >= SEA for x, z in end)

    landed = [i for i in (0, 1) if dry(ends[i], step[i])]
    assert len(landed) == 1, (wid, "landward ends", landed)
    sea_end = ends[1 - landed[0]]
    assert all(ground(x, z) < SEA for x, z in sea_end), (wid, "the seaward end is not over water")


# The jetty is the only way in: its landward end is itself on the beach, not a step off it.
def test_the_jetty_starts_on_the_beach(ground):
    w = next(q for q in PLAN["walks"] if q["id"] == "jetty")
    x0, z0, _x1, z1 = w["rect"]
    assert all(ground(x0, z) >= SEA for z in range(z0, z1 + 1)), [ground(x0, z) for z in range(z0, z1 + 1)]


# ------------------------------------------------------------------------------------------ the decks as built

def _service_grade_cells():
    """{(x, z)} of the non-air grade-layer blocks of the Centre and the Mart as the placement report seats them."""
    import nbt
    rep = ROOT / "derived" / "towns" / ("%s_placement.json" % SID)
    if not rep.is_file():
        pytest.skip("no derived/towns/sea_town_placement.json: run tools/place_town.py sea_town (derived/ is gitignored)")
    rot = {"none": lambda x, z: (x, z), "clockwise_90": lambda x, z: (-z, x), "180": lambda x, z: (-x, -z),
           "counterclockwise_90": lambda x, z: (z, -x)}
    files = {s["id"]: s["file"] for s in PLAN["services"]}
    out = set()
    for b in json.loads(rep.read_text(encoding="utf-8"))["buildings"]:
        _, doc = nbt.load(ROOT / files[b["id"]])
        pal = doc["palette"]
        px, _py, pz = b["command_position"]
        for q in doc["blocks"]:
            if q["pos"][1] == b["grade_layer"] and pal[q["state"]]["Name"] not in ("minecraft:air", "minecraft:structure_void"):
                dx, dz = rot[b["rotation"]](q["pos"][0], q["pos"][2])
                out.add((px + dx, pz + dz))
    return out


# Without it a deck is written at the wrong height (players wade, or step up onto it from a boat they cannot leave) or
# with holes a player falls through. Every deck cell holds a block at y62 after the committed commands, except the
# Centre's and the Mart's own floors (their grade layer, placed by the template) and the square (paved at y62 by the
# town plan, settlement plan.plaza).
def test_every_deck_cell_holds_a_block_at_the_sea_level_after_the_committed_commands():
    model = _replay(ALL_CMDS)
    grade = _service_grade_cells()
    plaza = DOC["settlements"][SID]["plan"]["plaza"]
    sq = next(r for r in PLAN["rafts"] if r.get("square"))
    assert plaza["rect"] == sq["rect"] and plaza["y"] == SEA, plaza
    holes = []
    n = 0
    for eid, kind, rect, _need, _lf in _deck_elements():
        if kind == "square":
            continue
        for x, z in _cells(rect):
            n += 1
            b = model.get((x, SEA, z), "minecraft:air").split("[")[0]
            if b in ("minecraft:air", "minecraft:water") and (x, z) not in grade:
                holes.append((eid, x, z))
    for e in ST.elements(PLAN):
        if e["kind"] == "bridge":
            for x, z in _cells(e["rect"]):
                n += 1
                if model.get((x, SEA, z), "minecraft:air").split("[")[0] in ("minecraft:air", "minecraft:water"):
                    holes.append((e["id"], x, z))
    assert n > 7000, n
    assert not holes, (len(holes), holes[:10])


# Without it a post stops short of the seabed (a raft on stilts over nothing, visibly floating on posts) or is driven
# into the seabed, cutting the painted ground: the lowest block of every column the town writes below the sub-deck is
# exactly one above the heightmap's ground. Only the post blocks data/sea_town.json names (materials.*.post) count:
# the slipway's stairs and the mangrove roots at the stilts' waterline are meant to stop short.
def test_every_post_reaches_exactly_the_seabed(ground):
    model = _replay(ALL_CMDS)
    posts = {m["post"] for m in PLAN["materials"].values() if isinstance(m, dict) and "post" in m}
    assert {"minecraft:jungle_log", "minecraft:mangrove_log"} <= posts, posts
    low = {}
    for (x, y, z), b in model.items():
        if y <= SEA - 2 and b.split("[")[0] in posts:
            low[(x, z)] = min(low.get((x, z), 10 ** 6), y)
    assert len(low) > 300, len(low)
    bad = [(x, z, y, ground(x, z)) for (x, z), y in low.items() if y != ground(x, z) + 1]
    assert not bad, (len(bad), bad[:10])


# Without it place_town seats the Centre and the Mart on the seabed (the ground kind not taken up), 8 to 10 blocks
# under water: the ground for the settlement is y62 on every deck cell and the heightmap everywhere else.
def test_sea_deck_ground_is_the_sea_level_on_every_deck_cell_and_the_heightmap_elsewhere(ground):
    import ground as G
    assert "sea_deck" in G.GROUND_KINDS
    g = G.for_settlement(SID)
    assert g.kind == "sea_deck"
    deck = set()
    for eid, _kind, rect, _n, _lf in _deck_elements():
        deck |= set(_cells(rect))
    for e in ST.elements(PLAN):
        if e["kind"] == "bridge":
            deck |= set(_cells(e["rect"]))
    assert all(g(x, z) == SEA for x, z in deck)
    fp = TOWNS_REC["footprint"]
    off = [(x, z) for x in range(fp["min_x"], fp["max_x"] + 1, 7) for z in range(fp["min_z"], fp["max_z"] + 1, 7)
           if (x, z) not in deck]
    assert len(off) > 1000
    assert all(g(x, z) == ground(x, z) for x, z in off)
    # and the plain heightmap under the rafts really is seabed: the kind is doing work
    assert sum(1 for x, z in deck if ground(x, z) < SEA) > 0.9 * len(deck)


TOWNS_REC = next(t for t in TOWNS["towns"] if t["id"] == SID)


# Without it data/towns.json records a footprint that leaves out a district (the Current Gate, the jetty), so the
# settlement clearance and the foliage and spawn tools treat part of the town as open country.
def test_the_towns_record_covers_every_authored_element_and_building():
    fp = TOWNS_REC["footprint"]
    rects = [r["rect"] for r in PLAN["rafts"]] + [w["rect"] for w in PLAN["walks"]] + [b["rect"] for b in PLAN["buildings"]]
    out = [r for r in rects if not (fp["min_x"] <= r[0] and r[2] <= fp["max_x"] and fp["min_z"] <= r[1] and r[3] <= fp["max_z"])]
    assert not out, out
    assert [TOWNS_REC["centre"]["x"], TOWNS_REC["centre"]["z"]] == list(PLAN["site"]["centre"])
    assert DOC["settlements"][SID]["plan"]["footprint"]["rect"] == [fp["min_x"], fp["min_z"], fp["max_x"], fp["max_z"]]


# Without it the Centre or the Mart is seated at the seabed, or its clerk is summoned under the deck. (The clerk's
# exact cell against the Mart template's shopkeeper jigsaw is tests/test_mart_clerks.py, which covers sea_town_mart.)
def test_the_services_stand_on_the_deck_and_the_clerk_at_the_walk_level():
    rep = ROOT / "derived" / "towns" / ("%s_placement.json" % SID)
    if not rep.is_file():
        pytest.skip("no derived/towns/sea_town_placement.json: run tools/place_town.py sea_town (derived/ is gitignored)")
    blds = {b["id"]: b for b in json.loads(rep.read_text(encoding="utf-8"))["buildings"]}
    assert set(blds) == {"sea_town_pokecenter", "sea_town_pokemart"}
    for b in blds.values():
        assert b["floor_y"] == SEA and b["command_position"][1] == SEA - b["grade_layer"], (b["id"], b["floor_y"])
    clerk = next(t for t in TRADERS["traders"] if t["id"] == "sea_town_mart")
    assert clerk["stock"] == "mart" and clerk["settlement"] == SID and clerk["building"] == "sea_town_pokemart"
    assert clerk["facing"] == next(s["facing"] for s in PLAN["services"] if s["id"] == "sea_town_pokemart")
    assert clerk["position"]["y"] == SEA + 1, clerk["position"]


# --------------------------------------------------------------------------------------- the tool's own modes

@pytest.fixture()
def tmp_records(tmp_path, monkeypatch, generated):
    """The committed placements and traders copied to tmp; the tool pointed at the copies; generation cached (it is a
    pure function of data/sea_town.json and the heightmap, and 2 s a run)."""
    for name in ("placements.json", "traders.json"):
        shutil.copyfile(ROOT / "data" / name, tmp_path / name)
    monkeypatch.setattr(ST, "PLACEMENTS", tmp_path / "placements.json")
    monkeypatch.setattr(ST, "TRADERS", tmp_path / "traders.json")
    monkeypatch.setattr(ST, "DERIVED", tmp_path / "derived")
    monkeypatch.setattr(ST, "generate", lambda *a, **k: generated)
    return tmp_path


def _edit(path, fn):
    d = json.loads(path.read_text(encoding="utf-8"))
    fn(d)
    path.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# Without it `plan` could report on a town it did not lay out on the sea: it exits 0, writes only its report (to the
# redirected derived/), and the report puts the deck at the sea level and the walk one above.
def test_plan_reports_the_deck_at_the_sea_level_and_writes_nothing_else(tmp_records):
    before = {n: (tmp_records / n).read_bytes() for n in ("placements.json", "traders.json")}
    assert ST.main(["plan"]) == 0
    rep = json.loads((tmp_records / "derived" / "plan.json").read_text(encoding="utf-8"))
    assert rep["deck_y"] == SEA and rep["walk_y"] == SEA + 1 and rep["deck_cells"] > 7000, rep["deck_cells"]
    assert {n: (tmp_records / n).read_bytes() for n in before} == before


# Without it `reapply.py prepare` would build a town the data no longer describes: check must pass on the committed
# records (they are what data/sea_town.json generates on this heightmap).
def test_check_passes_on_the_committed_records(tmp_records):
    assert ST.main(["check"]) == 0


# Without it a hand edit to a generated record (one earthwork command, the clerk's cell) goes unnoticed and is built.
@pytest.mark.parametrize("what", ["earthwork command", "service position", "clerk position", "settlement ground"])
def test_check_fails_when_a_committed_record_is_altered(tmp_records, what):
    def earthwork(d):
        p = next(q for q in d["placements"] if q.get("id") == "sea_town_fishers_row")
        i = next(k for k, c in enumerate(p["commands"]) if c.startswith("fill"))
        p["commands"][i] = "fill 0 0 0 0 0 0 minecraft:stone"

    def service(d):
        p = next(q for q in d["placements"] if q.get("id") == "sea_town_pokemart")
        p["position"]["x"] += 1

    def ground_kind(d):
        d["settlements"][SID]["ground"] = "islet"

    def clerk(d):
        t = next(q for q in d["traders"] if q.get("id") == "sea_town_mart")
        t["position"]["y"] -= 1

    if what == "clerk position":
        _edit(tmp_records / "traders.json", clerk)
    else:
        _edit(tmp_records / "placements.json", {"earthwork command": earthwork, "service position": service,
                                                "settlement ground": ground_kind}[what])
    assert ST.main(["check"]) == 1


# Without it `write` could leave an altered record in place (or damage the others): after it, check passes again and
# every other settlement's records are untouched.
def test_write_restores_what_check_refused_and_touches_no_other_place(tmp_records):
    _edit(tmp_records / "traders.json", lambda d: next(q for q in d["traders"] if q["id"] == "sea_town_mart")
          ["position"].update(y=0))
    assert ST.main(["check"]) == 1
    assert ST.main(["write"]) == 0
    assert ST.main(["check"]) == 0
    after = json.loads((tmp_records / "placements.json").read_text(encoding="utf-8"))
    assert [p for p in after["placements"] if p.get("settlement") != SID] == \
        [p for p in DOC["placements"] if p.get("settlement") != SID]
    assert {k: v for k, v in after["settlements"].items() if k != SID} == \
        {k: v for k, v in DOC["settlements"].items() if k != SID}


# Without it the plan's own rules are decoration: a raft moved onto the beach must be refused, not built.
def test_plan_refuses_a_raft_over_land(ground, monkeypatch):
    bad = copy.deepcopy(PLAN)
    x0, z0, _x1, z1 = next(w for w in PLAN["walks"] if w["id"] == "jetty")["rect"]
    bad["rafts"].append({"id": "raft_on_the_beach", "district": "mainland_jetty", "rect": [x0 - 12, z0 - 6, x0 - 2, z1 + 6]})
    assert all(ground(x, z) >= SEA - 1 for x, z in _cells(bad["rafts"][-1]["rect"])), "the fixture is not on land"
    monkeypatch.setattr(ST, "load", lambda path=None: bad)
    with pytest.raises(SystemExit, match="raft_on_the_beach stands over"):
        ST.generate()


# ------------------------------------------------------------------------------------------ what it places

# Without it a command the server refuses (a fill over 32,768 blocks) or silently drops (a write into an unloaded
# chunk) is committed, and part of the town is simply missing after the re-apply.
def test_the_committed_commands_pass_function_limits():
    import function_limits as FL
    bad = {}
    for p in EARTHWORKS:
        r = FL.check_lines(FL.ensure_loaded(p["commands"]), p["id"])
        if r:
            bad[p["id"]] = r[:3]
    assert not bad, bad
    if BUILT_TOWN.is_file():
        assert FL.check_file(BUILT_TOWN) == [], "the built town function"


# Without it the built function is stale against the data, or the water the old rafts' earthwork puts back runs before
# the Centre and the Mart are placed, so place_town's fluid clear under them leaves a dry layer between raft and sea.
def test_the_built_town_function_holds_every_earthwork_command_and_refills_water_after_the_services():
    if not BUILT_TOWN.is_file():
        pytest.skip("no build/datapacks/cobblers_towns/.../sea_town.mcfunction (python tools/place_town.py sea_town)")
    lines = [l.strip() for l in BUILT_TOWN.read_text(encoding="utf-8").splitlines()]
    have = set(lines)
    missing = [c for c in ALL_CMDS if not c.startswith("#") and c not in have]
    assert not missing, (len(missing), missing[:3])
    places = [i for i, l in enumerate(lines) if l.startswith("place template") and "__sea_town_poke" in l]
    water = [i for i, l in enumerate(lines) if l.startswith("fill") and _placed_blocks([l]) == ["minecraft:water"]]
    assert len(places) == 2 and water, (places, water)
    assert min(water) > max(places), (places, water)


def _allowed_for_sea_town():
    return {b for w in POLICY["whitelist"] if SID in (w.get("scope") or "") for b in w.get("blocks") or []}


# Without it the town places a block a loaded spawn condition names (a bell for Chimecho, a lily pad, coral, a white
# bed) and the town's encounters change with nobody deciding it. The only allowance is the policy's entry scoped to
# the sea town, and its water is exactly what that entry describes: one layer at y60 that replaces air, in the old
# rafts' earthwork, never over a block.
def test_no_spawn_deciding_block_is_placed_that_the_policy_does_not_allow_for_the_sea_town():
    placed = set(_placed_blocks(ALL_CMDS))
    assert len(placed) > 20
    allowed = _allowed_for_sea_town()
    assert allowed == {"minecraft:water"}, allowed
    assert not (placed & SPAWN_BLOCKS) - allowed, sorted((placed & SPAWN_BLOCKS) - allowed)
    water = [(p["id"], c) for p in EARTHWORKS for c in p["commands"]
             if c.startswith(("fill", "setblock")) and "minecraft:water" in _placed_blocks([c])]
    assert water
    for pid, c in water:
        t = c.split()
        assert pid == "sea_town_old_rafts" and t[0] == "fill" and t[2] == t[5] == "60", (pid, c)
        assert t[8:10] == ["replace", "minecraft:air"], c
    # teeth: a bell would be caught
    assert "minecraft:bell" in SPAWN_BLOCKS and "minecraft:bell" not in allowed


# The same rule for the two templates as the town places them: the built copies (materials applied) may carry only
# what the policy allows the sea town or service buildings (the PC and the healing machine).
def test_the_placed_service_templates_carry_no_spawn_deciding_block_beyond_the_policy():
    import nbt
    rep = ROOT / "derived" / "towns" / ("%s_placement.json" % SID)
    if not rep.is_file():
        pytest.skip("no derived/towns/sea_town_placement.json")
    allowed = _allowed_for_sea_town() | {b for w in POLICY["whitelist"] if w.get("scope") == "service buildings"
                                         for b in w["blocks"]}
    checked = 0
    for b in json.loads(rep.read_text(encoding="utf-8"))["buildings"]:
        ns, rel = b["template_placed"].split(":", 1)
        path = ROOT / "build" / "datapacks" / "cobblers_towns" / "data" / ns / "structure" / (rel + ".nbt")
        if not path.is_file():
            pytest.skip("no built template %s (python tools/place_town.py sea_town)" % path.name)
        _, doc = nbt.load(path)
        names = {p["Name"] for p in doc["palette"]}
        assert not (names & SPAWN_BLOCKS) - allowed, (b["id"], sorted((names & SPAWN_BLOCKS) - allowed))
        assert "minecraft:light" not in names, b["id"]
        checked += 1
    assert checked == 2


LIGHT_SOURCES = {"minecraft:light", "minecraft:torch", "minecraft:wall_torch", "minecraft:soul_torch",
                 "minecraft:soul_wall_torch", "minecraft:lantern", "minecraft:soul_lantern", "minecraft:sea_lantern",
                 "minecraft:glowstone", "minecraft:shroomlight", "minecraft:jack_o_lantern", "minecraft:redstone_lamp",
                 "minecraft:end_rod", "minecraft:campfire", "minecraft:soul_campfire", "minecraft:ochre_froglight",
                 "minecraft:verdant_froglight", "minecraft:pearlescent_froglight", "minecraft:glow_lichen",
                 "minecraft:sea_pickle", "minecraft:beacon", "minecraft:conduit", "minecraft:candle"}


# Without it an invisible light block (minecraft:light, which nobody can see or break) or a torch creeps in where the
# design says lanterns on posts: the town is lit by lanterns only. The smokehouse's one campfire is its fire, not a
# lamp, and is the only other light source allowed.
def test_the_town_is_lit_by_lanterns_only():
    placed = _placed_blocks(ALL_CMDS)
    lights = [b for b in placed if b in LIGHT_SOURCES or b.endswith("_candle")]
    assert lights.count("minecraft:lantern") >= 200, lights.count("minecraft:lantern")
    assert "minecraft:light" not in placed
    others = [b for b in lights if b != "minecraft:lantern"]
    assert others == ["minecraft:campfire"] * len(others) and len(others) <= 1, others


# --------------------------------------------------------------------------------------------- re-application

@pytest.fixture(scope="module")
def reapply_steps():
    import reapply
    try:
        return reapply, reapply.steps()
    except SystemExit as e:
        pytest.skip("reapply.steps() needs the built packs' index files (reapply.py prepare): %s" % e)


# Without it the sea town is authored but never built by a re-application (the export erases everything placed by
# hand): it must be one of R8's places, prep before town.
def test_the_sea_town_is_one_of_r8s_places(reapply_steps):
    reapply, steps = reapply_steps
    assert SID in reapply.places()
    r8 = next(acts for sid, _t, acts in steps if sid == "R8")
    fns = [v for k, v in r8 if k == "fn"]
    assert "cobblers:reapply/prep_%s" % SID in fns and "cobblers:towns/%s" % SID in fns
    assert fns.index("cobblers:reapply/prep_%s" % SID) < fns.index("cobblers:towns/%s" % SID)


# Without it prepare's fail-closed check would stop the pipeline, or be passing because it looks at nothing: every
# function pack is run by a step or excluded with a reason, and every function in a covered pack is run or named.
def test_prepares_fail_closed_coverage_check_passes(reapply_steps):
    reapply, steps = reapply_steps
    assert len(reapply.function_packs()) > 10
    assert reapply.uncovered(steps) == []
    assert reapply.unreferenced(steps) == []
    # teeth: with every step that runs a town function taken out, the towns pack is reported
    without = [(s, t, [(k, v) for k, v in a if not (k == "fn" and v.startswith("cobblers:towns/"))]) for s, t, a in steps]
    assert any(b.startswith("cobblers_towns ") for b in reapply.uncovered(without))


# -------------------------------------------------------------------------------------------------- verify

def _fake_capture(world_blocks):
    import structure_nbt as SN

    def capture(_world, lo, hi):
        b = SN.Builder()
        for (x, y, z), (name, props) in world_blocks.items():
            if lo[0] <= x <= hi[0] and lo[1] <= y <= hi[1] and lo[2] <= z <= hi[2]:
                b.set(x, y, z, name, props)
        return b
    return capture


def _world_from(expected):
    return {p: (blk.split("[")[0].split("{")[0], {}) for p, blk in expected.items()}


# Without it `verify --world` (the audit's sea-town gate) could pass a world where the town is not, or not only: it
# passes a world holding exactly the model, and fails one with a deck block missing, water standing on a deck, or
# flowing water beside the town.
def test_verify_world_passes_the_model_and_fails_a_hole_a_wet_deck_and_flowing_water(generated, tmp_path, monkeypatch):
    import structure_nbt as SN
    _plan, _s, _r, _c, _rep, writers, model = generated
    exp = ST.expected(writers, model)
    assert len(exp) > 20000
    world = tmp_path / "stopped_copy"
    (world / "region").mkdir(parents=True)

    def run(blocks):
        monkeypatch.setattr(SN, "capture", _fake_capture(blocks))
        return ST.verify_world(world, writers, model)

    clean = run(_world_from(exp))
    assert clean["mismatches"] == 0 and clean["water_on_deck"] == 0 and clean["flowing_water"] == 0, clean

    x, z = sorted(model["deck"])[len(model["deck"]) // 2]
    holed = _world_from(exp)
    holed.pop((x, SEA, z), None)
    assert run(holed)["mismatches"] >= 1

    wet = _world_from(exp)
    wx, wz = next(c for c in sorted(model["deck"]) if (c[0], SEA + 1, c[1]) not in exp)
    wet[(wx, SEA + 1, wz)] = ("minecraft:water", {})
    assert run(wet)["water_on_deck"] == 1

    flowing = _world_from(exp)
    fx, fz = next(c for c in sorted(model["deck"]) if (c[0], SEA - 1, c[1]) not in exp)
    flowing[(fx, SEA - 1, fz)] = ("minecraft:water", {"level": "3"})
    assert run(flowing)["flowing_water"] == 1

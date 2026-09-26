"""tools/route_events.py: the Routes 1-3 event sites, their scenes' positions and the trainers' seats.

Written by the test author, not by the session that wrote the tool, the scene data or the seats.

The sites are built from the canonical heightmap (tools/ground.py) and the dense walked line
build/routes/paths.json. Tests that need them SKIP, naming what is absent: COBBLERS_SOURCE_ROOT unset or the
heightmap unusable, or build/routes/paths.json not built in this checkout (python tools/build_routes.py). A skip is
not a pass.

What is asserted: the tool as run by `reapply.py prepare` exits 0 (no drift between the build and data/scenes.json /
data/route_trainers.json, nothing built on the walked line); the ground the walked lines were routed on equals the
current ground at every column the sites, scenes, seats and Route 1-3 lines use, and check_paths_heightmap refuses
paths routed on an unrelated heightmap, or on the pre-sculpt one where it differs inside REGION; nothing built stands within ROAD_CLEAR - 1 of a walked cell except ground-level surface work in a
surface material (a stricter rule than the tool's own, which exempts a whole trail column); every route-events scene
has exactly the props, markers and NPCs its site builds; every prop's `on` block is one its site writes, not air;
every marker slot and NPC is standable where its site writes the column, and no marker slot, NPC or seat has its
feet inside the heightmap ground; all vegetation clearing is in 00_clear, first in the index, and no site function
clears; each clear segment writes only inside its own forceload and none into a chunk the function released earlier;
each site function holds every chunk of its own build for its whole run (forceload add first, remove last) and
passes tools/function_limits.py; the seats are the 13 Route 1-3 trainers, each at least
ROAD_CLEAR off the walked line unless its record carries an override with a reason.

Not covered, and it needs a staging world (`route_events.py --verify-world`) or a server: that the blocks land as
planned, that the vegetation clearing leaves no log or leaf, that an actor at a water marker floats rather than
sinks, and anything a player sees.
"""
import json
import math
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import route_events as RE  # noqa: E402

PATHS = ROOT / "build" / "routes" / "paths.json"
WORLD = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))
SCENES = {s["id"]: s for s in json.loads((ROOT / "data" / "scenes.json").read_text(encoding="utf-8"))["scenes"]}
SEATS = json.loads((ROOT / "data" / "route_trainers.json").read_text(encoding="utf-8"))["trainers"]
TRAINERS = json.loads((ROOT / "data" / "trainers.json").read_text(encoding="utf-8"))["trainers"]
AIR = {"minecraft:air", "minecraft:cave_air", "minecraft:water"}
PASSABLE = ("_carpet", "minecraft:leaf_litter", "_trapdoor", "minecraft:candle", "_candle", "_button",
            "_pressure_plate", "minecraft:short_grass", "minecraft:fern")
DEFAULT_SLOTS = [[0.0, 0.0], [0.9, 0.0], [0.0, 0.9], [-0.9, 0.0]]     # tools/scenes_pack.py SLOTS
BUILT_HERE = sorted(sid for sid, s in SCENES.items() if "tools/route_events.py" in (s.get("built_by") or ""))


def base(b):
    return b.split("[")[0].split("{")[0] if b else b


def passable(b):
    return b is None or base(b) in AIR or base(b).endswith(PASSABLE)


def solid(b):
    return b is not None and not passable(b)


def need_paths():
    if not PATHS.is_file():
        pytest.skip("build/routes/paths.json is not built in this checkout (python tools/build_routes.py)")


@pytest.fixture(scope="module")
def walked():
    need_paths()
    doc = json.loads(PATHS.read_text(encoding="utf-8"))
    return {k: [tuple(p) for p in v] for k, v in doc["paths"].items()}


@pytest.fixture(scope="module")
def built():
    """(ground, road, sites, seats) from one real build, or a skip naming what is absent."""
    need_paths()
    import ground as G
    import terrain as T
    root = os.environ.get("COBBLERS_SOURCE_ROOT")
    if not root:
        pytest.skip("COBBLERS_SOURCE_ROOT unset: the sites stand on the canonical heightmap")
    try:
        g = G.Ground(root)
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)
    road = RE.Road()
    sites, seats = RE.build(g, road)
    return g, road, sites, seats


def site_for(sites, scene_id):
    got = [s for s in sites if s.scene == scene_id]
    assert len(got) == 1, "scene %s is built by %d sites" % (scene_id, len(got))
    return got[0]


def slot_cells(m, scene):
    at = m["at"] if isinstance(m, dict) else m[:3]
    slots = (m.get("slots") if isinstance(m, dict) else None) or scene.get("slots") or DEFAULT_SLOTS
    return [(math.floor(at[0] + 0.5 + ox), at[1], math.floor(at[2] + 0.5 + oz)) for ox, oz in slots]


# ------------------------------------------------------------------ the tool as prepare runs it

# Without it `reapply.py prepare` stops at this step (drift, or something standing on the road), or worse, a drift
# goes unnoticed because the command was never run in the test suite.
def test_route_events_exits_clean_as_prepare_runs_it(built, monkeypatch, tmp_path, capsys):
    orig = RE.write_pack
    monkeypatch.setattr(RE, "write_pack", lambda sites, out=None: orig(sites, tmp_path / "pack"))
    rc = RE.main(["--source-root", os.environ["COBBLERS_SOURCE_ROOT"]])
    out = capsys.readouterr().out
    assert rc == 0, "\n".join(l for l in out.splitlines() if "DRIFT" in l or "ROAD" in l or l.startswith("    "))
    assert "DRIFT" not in out and "ROAD CLEARANCE" not in out
    assert (tmp_path / "pack" / "data" / "cobblers" / "function" / "route_events" / "index.txt").is_file()


def _used_columns(road, sites, seats):
    """Every (x, z) whose ground these sites use: the Route 1-3 walked cells, every column a site writes or clears,
    every route-events scene's area, and every trainer's seat."""
    cols = set()
    for rid in RE.ROUTES.values():
        cols |= set(road.paths[rid])
    for s in sites:
        cols |= {(x, z) for (x, _y, z) in s.blocks}
        for (x0, _y0, z0, x1, _y1, z1) in s.cleared:
            cols |= {(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}
    for sid in BUILT_HERE:
        a = SCENES[sid]["area"]
        cols |= {(x, z) for x in range(min(a["from"][0], a["to"][0]), max(a["from"][0], a["to"][0]) + 1)
                 for z in range(min(a["from"][2], a["to"][2]), max(a["from"][2], a["to"][2]) + 1)}
    cols |= {(t["seat"][0], t["seat"][2]) for t in seats}
    return cols


# Without it the walked lines (routed on one heightmap) and the ground the sites stand on (another) could disagree
# where the sites use them, and "off the walked line" would be measured against a road that is not where
# tools/build_routes.py would put it on today's ground. Checked independently of the tool's REGION: the two files are
# compared at every column the sites, scenes, seats and Route 1-3 lines use, and REGION must hold them all.
def test_the_walked_lines_were_routed_on_the_ground_the_sites_use(built):
    import numpy as np
    from PIL import Image
    _g, road, sites, seats = built
    root = os.environ["COBBLERS_SOURCE_ROOT"]
    have = json.loads(PATHS.read_text(encoding="utf-8"))["heightmap_sha256"]
    hm = WORLD["heightmap"]
    msg = RE.check_paths_heightmap(root)                   # raises SystemExit when it cannot vouch for the paths
    if have == hm["sha256"]:
        assert msg == "routed on the current heightmap"
        return
    base_rec = hm.get("rift_sculpted_from") or {}
    assert have == base_rec.get("sha256"), "the tool accepted paths routed on %s" % have[:12]
    cols = _used_columns(road, sites, seats)
    assert len(cols) > 10000
    x0, z0, x1, z1 = RE.REGION
    outside = sorted(c for c in cols if not (x0 <= c[0] <= x1 and z0 <= c[1] <= z1))
    assert outside == [], "used columns outside REGION, which the tool does not compare: %s" % outside[:5]
    old_path = Path(root) / base_rec["path"]
    if not old_path.is_file():
        pytest.skip("%s (the heightmap the paths were routed on) is not under COBBLERS_SOURCE_ROOT" % old_path.name)
    cur, old = np.array(Image.open(Path(root) / hm["path"])), np.array(Image.open(old_path))
    ox, oz = WORLD["grid"]["origin_x"], WORLD["grid"]["origin_z"]
    xs = np.array([c[0] - ox for c in cols])
    zs = np.array([c[1] - oz for c in cols])
    assert xs.min() >= 0 and zs.min() >= 0 and xs.max() < cur.shape[1] and zs.max() < cur.shape[0]
    differ = int((cur[zs, xs] != old[zs, xs]).sum())
    assert differ == 0, "%d used columns differ between the routed-on and the current heightmap" % differ


def _fake_world(tmp_path, monkeypatch, paths_sha, poke=None):
    """A tmp ROOT whose data/world.json points at two small 16-bit heightmaps covering REGION with a margin, the
    current one equal to the routed-on one except at `poke` (world x, z), and a paths.json routed on `paths_sha`
    ("current", "rift", or a literal sha)."""
    import hashlib
    import numpy as np
    from PIL import Image
    x0, z0, x1, z1 = RE.REGION
    m = 10
    ox, oz = x0 - m, z0 - m
    arr = np.full((z1 - z0 + 1 + 2 * m, x1 - x0 + 1 + 2 * m), 20000, dtype=np.uint16)
    src = tmp_path / "src"
    src.mkdir()
    Image.fromarray(arr).save(src / "old.png", compress_level=1)
    arr[0, 0] += 7                     # in the margin, outside REGION: the Rift sculpt's own change, so the files differ
    if poke:
        arr[poke[1] - oz, poke[0] - ox] += 1
    Image.fromarray(arr).save(src / "cur.png", compress_level=1)
    sha = {n: hashlib.sha256((src / n).read_bytes()).hexdigest() for n in ("old.png", "cur.png")}
    (tmp_path / "data").mkdir()
    world = {"grid": {"origin_x": ox, "origin_z": oz},
             "heightmap": {"path": "cur.png", "sha256": sha["cur.png"], "status": "ok",
                           "rift_sculpted_from": {"path": "old.png", "sha256": sha["old.png"]}}}
    (tmp_path / "data" / "world.json").write_text(json.dumps(world), encoding="utf-8")
    routed_on = {"current": sha["cur.png"], "rift": sha["old.png"]}.get(paths_sha, paths_sha)
    paths = tmp_path / "paths.json"
    paths.write_text(json.dumps({"heightmap_sha256": routed_on, "paths": {}}), encoding="utf-8")
    monkeypatch.setattr(RE, "ROOT", tmp_path)
    monkeypatch.setattr(RE, "PATHS", paths)
    return str(src)


# Without it paths routed on any old heightmap (neither today's nor the one the Rift sculpt was pressed into) are read
# as the walked line, as they were before check_paths_heightmap existed.
def test_paths_routed_on_an_unrelated_heightmap_are_refused(tmp_path, monkeypatch):
    pytest.importorskip("PIL")
    src = _fake_world(tmp_path, monkeypatch, "ab" * 32)
    with pytest.raises(SystemExit, match="neither the current one nor"):
        RE.check_paths_heightmap(src)


# Without it the comparison could be skipped or look at the wrong window: one column changed inside REGION (its
# corners included) must refuse the paths, one changed just outside it must not, and unchanged ground must pass.
@pytest.mark.parametrize("poke,refused", [
    (None, False), ((1700, 3000), True), ((RE.REGION[0], RE.REGION[1]), True), ((RE.REGION[2], RE.REGION[3]), True),
    ((RE.REGION[0] - 5, 3000), False)])
def test_the_pre_sculpt_heightmap_is_accepted_only_if_identical_over_region(tmp_path, monkeypatch, poke, refused):
    pytest.importorskip("PIL")
    src = _fake_world(tmp_path, monkeypatch, "rift", poke)
    if refused:
        with pytest.raises(SystemExit, match="changed 1 columns"):
            RE.check_paths_heightmap(src)
    else:
        assert "identical to the current one" in RE.check_paths_heightmap(src)


# Without it paths routed on today's heightmap would be put through the comparison, or refused.
def test_paths_routed_on_the_current_heightmap_are_accepted(tmp_path, monkeypatch):
    pytest.importorskip("PIL")
    src = _fake_world(tmp_path, monkeypatch, "current")
    assert RE.check_paths_heightmap(src) == "routed on the current heightmap"


# Without it a Route 1-3 line that leaves REGION would be used where the comparison never looked.
def test_a_route_that_leaves_region_is_refused(tmp_path, monkeypatch):
    x0, z0, x1, _z1 = RE.REGION
    paths = {rid: [[x0 + 5, z0 + 5], [x0 + 6, z0 + 5]] for rid in RE.ROUTES.values()}
    paths["route_02_brock_to_misty"].append([x1 + 3, z0 + 5])
    f = tmp_path / "paths.json"
    f.write_text(json.dumps({"heightmap_sha256": "x", "paths": paths}), encoding="utf-8")
    monkeypatch.setattr(RE, "PATHS", f)
    with pytest.raises(SystemExit, match="route_02_brock_to_misty leaves REGION"):
        RE.Road()


# ------------------------------------------------------------------ the road

# Without it a fence, a barrel or a sign stands on the walked line (or one block off it) and players walk into it;
# the tool's own rule exempts any block in a column it also paved, so this one allows only the paving itself.
def test_nothing_but_ground_level_surface_work_stands_near_the_walked_line(built, walked):
    g, _road, sites, _seats = built
    cells = set().union(*[set(v) for v in walked.values()])
    r = RE.ROAD_CLEAR - 1
    bad = []
    for s in sites:
        for (x, y, z), b in s.blocks.items():
            if base(b) == "minecraft:air":
                continue
            if not any((x + dx, z + dz) in cells for dx in range(-r, r + 1) for dz in range(-r, r + 1)):
                continue
            if y == g(x, z) and base(b) in RE.SURFACE:
                continue
            bad.append("%s: %s at %s" % (s.id, b[:40], (x, y, z)))
    assert bad == []


# ------------------------------------------------------------------ scenes and sites agree

# Without it a prop, marker or NPC recorded in data/scenes.json has nothing built for it (the tool's drift check only
# looks from the build to the record, never back), or a scene claims a builder that does not build it.
@pytest.mark.parametrize("scene_id", BUILT_HERE)
def test_each_route_events_scene_has_exactly_what_its_site_builds(built, scene_id):
    _g, _road, sites, _seats = built
    s, rec = site_for(sites, scene_id), SCENES[scene_id]
    assert set(s.props) == {p["id"] for p in rec.get("props") or []}
    assert set(s.markers) == set(rec.get("markers") or {})
    assert sorted(n["conversation"] for n in s.npcs) == sorted(n["conversation"] for n in rec.get("npcs") or [])


def _props():
    return [(sid, p) for sid in BUILT_HERE for p in SCENES[sid].get("props") or []]


# Without it a prop's click box floats over grass beside the thing the dialogue talks about (the rut, the mud).
@pytest.mark.parametrize("scene_id,prop", _props(), ids=["%s/%s" % (s, p["id"]) for s, p in _props()])
def test_every_prop_is_on_a_block_its_site_writes(built, scene_id, prop):
    _g, _road, sites, _seats = built
    s = site_for(sites, scene_id)
    got = s.blocks.get(tuple(prop["on"]))
    assert got is not None and base(got) != "minecraft:air", (
        "%s: on %s is %s; the site writes nothing there (below it: %s)"
        % (prop["id"], prop["on"], got, s.blocks.get((prop["on"][0], prop["on"][1] - 1, prop["on"][2]))))


def _standers(scene_id):
    rec, out = SCENES[scene_id], []
    for name, m in (rec.get("markers") or {}).items():
        for cell in slot_cells(m, rec):
            out.append(("marker %s" % name, cell))
    for n in rec.get("npcs") or []:
        out.append(("npc %s" % n["conversation"], tuple(n["at"])))
    return out


# Without it the two tests below could pass on scenes with nothing to stand on.
def test_the_route_events_scenes_have_markers_and_npcs_to_check():
    assert len(BUILT_HERE) >= 9
    assert sum(len(_standers(sid)) for sid in BUILT_HERE) >= 30


# Without it an actor or NPC is placed inside a plank, a post or a barrel the site built, or over a hole in a deck.
# Many stand on natural ground the site never writes; those columns are left to the ground test below.
def test_markers_and_npcs_are_standable_where_their_site_writes_the_column(built):
    g, _road, sites, _seats = built
    bad, checked = [], 0
    for sid in BUILT_HERE:
        s = site_for(sites, sid)
        columns = {(bx, bz) for (bx, _by, bz) in s.blocks}
        for what, (x, y, z) in _standers(sid):
            if (x, z) not in columns:
                continue
            checked += 1
            feet, head, below = s.blocks.get((x, y, z)), s.blocks.get((x, y + 1, z)), s.blocks.get((x, y - 1, z))
            if not passable(feet):
                bad.append("%s %s: feet at %s is %s" % (sid, what, (x, y, z), feet))
            if not passable(head):
                bad.append("%s %s: head at %s is %s" % (sid, what, (x, y + 1, z), head))
            if not (solid(below) or (below is None and g(x, z) == y - 1)):
                bad.append("%s %s: below %s is %s, ground y%d" % (sid, what, (x, y, z), below, g(x, z)))
    assert checked >= 5, "only %d slots stand in columns a site writes: the rule was barely exercised" % checked
    assert bad == []


# Without it an actor or NPC is spawned with its feet inside the terrain (the Wooper in the pond bank).
@pytest.mark.parametrize("scene_id", BUILT_HERE)
def test_no_marker_slot_or_npc_has_its_feet_in_the_ground(built, scene_id):
    g, _road, sites, _seats = built
    s = site_for(sites, scene_id)
    bad = []
    for what, (x, y, z) in _standers(scene_id):
        if (x, y, z) in s.blocks:
            if not passable(s.blocks[(x, y, z)]):
                bad.append("%s: feet at %s is %s" % (what, (x, y, z), s.blocks[(x, y, z)]))
        elif y <= g(x, z):
            bad.append("%s: feet at %s, inside the ground (heightmap y%d)" % (what, (x, y, z), g(x, z)))
    assert bad == []


# ------------------------------------------------------------------ the functions

CLEAR = re.compile(r"fill -?\d+ -?\d+ -?\d+ -?\d+ -?\d+ -?\d+ minecraft:air replace ")
FORCELOAD = re.compile(r"forceload (add|remove) (-?\d+) (-?\d+) (-?\d+) (-?\d+)$")


@pytest.fixture(scope="module")
def pack(built, tmp_path_factory):
    """(sites, function dir, index) from write_pack into a temp folder (never build/)."""
    _g, _road, sites, _seats = built
    out = tmp_path_factory.mktemp("route_events") / "pack"
    RE.write_pack(sites, out)
    fdir = out / "data" / "cobblers" / "function" / "route_events"
    index = [l for l in (fdir / "index.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    return sites, fdir, index


def _lines(fdir, name):
    return (fdir / ("%s.mcfunction" % name)).read_text(encoding="utf-8").splitlines()


# Without it a site's vegetation clear (`replace #minecraft:logs`) runs after another site has built, and takes that
# site's own posts and piles (the north bank's trail took the sounding platform's clawed post on staging, 2026-09-24):
# R12 runs the index in order, so the clear function must come first and hold every site's clears, and no site
# function may clear.
def test_all_clearing_runs_before_any_site_builds(pack):
    sites, fdir, index = pack
    assert index == ["00_clear"] + [s.id for s in sites] and len(sites) >= 11
    clear = _lines(fdir, "00_clear")
    body = [l for l in clear if l.strip() and not l.startswith("#") and not l.startswith("forceload ")]
    want = [c for s in sites for c in s.clear_cmds]
    assert len(want) > 100, "the sites clear (almost) nothing: the rule was barely exercised"
    assert body == want
    assert all(CLEAR.match(c) for c in want), [c for c in want if not CLEAR.match(c)][:3]
    for s in sites:
        leaked = [l for l in _lines(fdir, s.id) if CLEAR.match(l) or re.search(r"replace #minecraft:(logs|leaves)\b", l)]
        assert leaked == [], "%s still clears in its own function: %s" % (s.id, leaked[:2])


# Without it a site's clearing segment writes into chunks it did not load, or its forceload is refused over the
# 256-chunk limit, and the vegetation stays where the site is about to build.
def test_each_clear_segment_is_inside_its_own_forceload(pack):
    import function_limits as FL
    sites, fdir, _index = pack
    lines = _lines(fdir, "00_clear")
    assert FL.unloaded_writes(lines) == []
    assert FL.check_lines(lines, "00_clear") == []
    held, segments = None, 0
    for l in lines:
        m = FORCELOAD.match(l)
        if m and m.group(1) == "add":
            held = (held or set()) | FL._chunks(*map(int, m.groups()[1:]))
            continue
        if m:
            held = None                                    # a segment ends: its writes must all have come before
            segments += 1
            continue
        if CLEAR.match(l):
            x0, _y0, z0, x1, _y1, z1 = map(int, l.split()[1:7])
            assert held is not None and FL._chunks(x0, z0, x1, z1) <= held, "outside its segment's forceload: %s" % l[:80]
    assert segments >= len([s for s in sites if s.clear_cmds])


# Without it the clear function releases a segment's chunks and the next segment re-adds an overlapping box: a chunk
# re-added straight after its release is found half way out (tools/function_limits.py releases_mid_run; Sunset West's
# Mart landed 6 of 1,731 blocks that way), and docs/STATE.md holds every generated function to its chunks for its
# whole run. The hazard stated precisely: no write lands in a chunk the function released earlier.
def test_the_clear_function_never_writes_into_a_chunk_it_already_released(pack):
    import function_limits as FL
    _sites, fdir, _index = pack
    released, bad = set(), []
    for l in _lines(fdir, "00_clear"):
        m = FORCELOAD.match(l)
        if m:
            if m.group(1) == "remove":
                released |= FL._chunks(*map(int, m.groups()[1:]))
            continue
        if CLEAR.match(l):
            x0, _y0, z0, x1, _y1, z1 = map(int, l.split()[1:7])
            if FL._chunks(x0, z0, x1, z1) & released:
                bad.append(l[:70])
    assert bad == [], "%d clears write into chunks released earlier in 00_clear, first: %s" % (len(bad), bad[0])


# Without it a site writes into chunks nobody loaded (nothing lands and nothing says so), releases them half way, or
# a fill is over the block limit and refused whole.
def test_each_site_function_holds_every_chunk_of_its_build_for_its_whole_run(pack):
    import function_limits as FL
    sites, fdir, _index = pack
    for s in sites:
        sid = s.id
        lines = _lines(fdir, sid)
        body = [l for l in lines if l.strip() and not l.startswith("#")]
        writes = [l for l in body if re.match(r"(setblock|fill) ", l)]
        assert writes, "%s writes nothing" % sid
        assert writes == [c for c in s.cmds if re.match(r"(setblock|fill) ", c)], "%s: not its own build" % sid
        adds = [i for i, l in enumerate(body) if l.startswith("forceload add ")]
        removes = [i for i, l in enumerate(body) if l.startswith("forceload remove ")]
        assert adds and adds == list(range(len(adds))), "%s: forceload add is not first" % sid
        assert removes and removes == list(range(len(body) - len(removes), len(body))), "%s: forceload remove is not last" % sid
        assert [l.split(" ", 2)[2] for l in (body[i] for i in adds)] == [l.split(" ", 2)[2] for l in (body[i] for i in removes)]
        assert FL.unloaded_writes(lines) == [], sid
        assert not FL.releases_mid_run(lines), sid
        assert FL.check_lines(lines, sid) == [], sid


# ------------------------------------------------------------------ the trainers' seats

ROUTE_IDS = sorted(t["id"] for t in TRAINERS if re.match(r"route_0[123]_", t["id"]))


# Without it a Route 1-3 trainer has no seat (never placed by R17), or a seat names a trainer nobody authored.
def test_the_seats_are_the_thirteen_route_1_to_3_trainers():
    assert len(ROUTE_IDS) == 13
    assert sorted(t["id"] for t in SEATS) == ROUTE_IDS
    assert set(RE.TRAINERS) == set(ROUTE_IDS)


# Without it a trainer stands on the walked line and players walk into it, unless the design put it somewhere else on
# purpose and says why (the apiary, the north-bank platform, the Swablu bench).
@pytest.mark.parametrize("seat", SEATS, ids=[t["id"] for t in SEATS])
def test_each_seat_is_off_the_walked_line_unless_its_record_says_why(walked, seat):
    x, _y, z = seat["seat"]
    d = min(math.hypot(px - x, pz - z) for v in walked.values() for px, pz in v)
    _skin, _eye, override, why = RE.TRAINERS[seat["id"]]
    if d < RE.ROAD_CLEAR:
        assert override is not None and why.strip() and seat["why"] == why, (
            "%s stands %.2f from the walked line with no override and reason" % (seat["id"], d))
    assert seat["why"].strip()


# Without it summon_persistent puts a trainer inside the ground or inside something a site built.
@pytest.mark.parametrize("seat", SEATS, ids=[t["id"] for t in SEATS])
def test_each_seat_has_room_to_stand(built, seat):
    g, _road, sites, _seats = built
    x, y, z = seat["seat"]
    for cell in ((x, y, z), (x, y + 1, z)):
        for s in sites:
            blk = s.blocks.get(cell)
            assert passable(blk), "%s: %s writes %s at %s" % (seat["id"], s.id, blk, cell)
    below = [s.blocks[(x, y - 1, z)] for s in sites if (x, y - 1, z) in s.blocks]
    assert (below and solid(below[-1])) or (not below and g(x, z) == y - 1), (seat["id"], below, g(x, z))

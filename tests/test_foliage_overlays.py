"""data/foliage.json "overlays" (marsh_giants, marsh_mangroves, jungle_thickets) through tools/foliage.py
overlay_layers() and place(), and the swamp objects tools/foliage_objects.py generates for them.

Written by the test author, not by the session that wrote the overlays or the swamp objects.

Speed and scope: place() runs on the real data (data/foliage.json, data/regions.json sub-region polygons rasterised by
tools/paint_maps.py, data/towns.json clearances, the committed object library) but on two square windows of the map,
not the whole 8192 x 8192: the marsh window (x 4160..6847, z 960..3647: marshy_marsh, marsh_creek and the forest
types around them) and the jungle window (x 4256..6047, z 6656..8447: jungle_west, jungle_east; the map ends at
z 8191 and the rest is empty). Landmark tree sites are shifted into window coordinates. The ground is synthetic: flat
at y100, slope 0, no water and every column allowed, because the heightmap lives outside the repository. paint_maps'
fill_gaps (unassigned land joined to its neighbours) is not applied, since land comes from the heightmap. About 4
seconds in all.

The route lane mask handed to place() is tools/paint_maps.py route_lanes (the tool's own input path); the clearance is
checked here against the route centrelines in data/routes.json by plain point-to-segment geometry.

Not covered: the real terrain's slopes, water and treelines (they only remove stems, but the counts here are not the
map's), the floor and understory painting of overlays in paint_maps, the jungle overlay's route clearance (no route in
data/routes.json reaches the jungle isle, so that case is vacuous and reported as such), WorldPainter placing the
objects, and how anything looks in game.
"""
import copy
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import foliage as F  # noqa: E402
import foliage_objects as FO  # noqa: E402
import paint_maps as PM  # noqa: E402
import structure_nbt as S  # noqa: E402

DOC = json.loads((ROOT / "data" / "foliage.json").read_text(encoding="utf-8"))
LIB_DIR = ROOT / "kits" / "structures" / "foliage"
LIB = json.loads((LIB_DIR / "library.json").read_text(encoding="utf-8"))
REGIONS = json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))
SUBS, PRESETS = REGIONS["subregions"], REGIONS["paint_presets"]
ROUTES = json.loads((ROOT / "data" / "routes.json").read_text(encoding="utf-8"))
SEED = 20260914                                   # tools/paint_maps.py --seed default
WINDOWS = {"marsh": (4160, 960, 2688), "jungle": (4256, 6656, 1792)}
LAYERS = {lay["id"]: lay for lay in DOC["overlays"]["layers"]}
SWAMP_GROUPS = {"mangrove", "tall_mangrove", "mangrove_scrub", "swamp_giant", "vine_snag", "root_tangle"}
GROUND_R = {}
for _r in LIB["objects"]:
    GROUND_R[_r["group"]] = max(GROUND_R.get(_r["group"], 0), _r.get("ground_radius", 0))


def _without_overlays(doc):
    d = copy.deepcopy(doc)
    d.pop("overlays", None)
    return d


@pytest.fixture(scope="module")
def full_masks():
    idx = PM.rasterise_subregions(SUBS)
    excl = PM.settlement_clearance(str(ROOT / "data" / "towns.json"), DOC["density_model"]["settlement_clearance_blocks"])
    _, lane = F.overlay_layers(DOC)
    paths = PM.route_lanes(str(ROOT / "data" / "routes.json"), lane)
    return idx, excl, paths


def _crop(a, x0, z0, s):
    out = np.zeros((s, s), a.dtype)
    zz, xx = min(s, a.shape[0] - z0), min(s, a.shape[1] - x0)
    out[:zz, :xx] = a[z0:z0 + zz, x0:x0 + xx]
    return out


def _place(doc, window, masks, with_paths=True):
    x0, z0, s = WINDOWS[window]
    idx, excl, paths = (_crop(m, x0, z0, s) for m in masks)
    d = copy.deepcopy(doc)
    for lt in d.get("landmark_trees") or []:
        lt["site"] = [lt["site"][0] - x0, lt["site"][1] - z0]
    flat = np.full((s, s), 100.0, np.float32)
    res = F.place(d, LIB, SUBS, PRESETS, idx, flat, np.zeros((s, s), np.float32), np.ones((s, s), bool),
                  np.zeros((s, s), np.float32), np.zeros((s, s), bool), excl, SEED, paths=paths if with_paths else None)
    return res, idx


@pytest.fixture(scope="module")
def runs(full_masks):
    out = {}
    for w in WINDOWS:
        with_, idx = _place(DOC, w, full_masks)
        without, _ = _place(_without_overlays(DOC), w, full_masks)
        added = {g: pts[len(without["positions"].get(g, [])):] for g, pts in with_["positions"].items()}
        out[w] = {"with": with_, "without": without, "idx": idx, "added": {g: p for g, p in added.items() if p}}
    return out


# removing this lets every property below pass on windows where the overlays placed nothing
def test_windows_hold_forest_types_and_overlay_stems(runs):
    for w, r in runs.items():
        base = sum(len(p) for p in r["without"]["positions"].values())
        added = sum(len(p) for p in r["added"].values())
        assert base > 1000 and added > 500, (w, base, added)
    assert set(runs["marsh"]["with"]["overlay_ids"]) == {"marsh_giants", "marsh_mangroves"}
    assert set(runs["jungle"]["with"]["overlay_ids"]) == {"jungle_thickets"}


# removing this lets an overlay draw from the forest types' random stream or reorder their draws, so adding a marsh
# overlay repaints every forest on the map (the overlays' promise: their effect is local to their sub-regions)
def test_overlays_leave_every_forest_type_placement_unchanged(runs):
    for w, r in runs.items():
        before, after = r["without"]["positions"], r["with"]["positions"]
        assert before
        for g, pts in before.items():
            assert after.get(g, [])[:len(pts)] == pts, (w, g)
        assert r["with"]["stats"] == r["without"]["stats"], w
        assert r["with"]["type_ids"] == r["without"]["type_ids"], w


# removing this lets an overlay's stems spill past its named sub-regions (its ragged edge or its box margin) into a
# neighbouring forest type or open ground. Checked on the origin column. A column no polygon covers (index 0: the
# slivers between polygons, which paint_maps.fill_gaps gives to a neighbour and this window does not reproduce) only
# passes when an allowed column is within one 4-block grid cell, the resolution place() draws at
def test_overlays_only_place_inside_their_named_subregions(runs):
    sub_index = {s["id"]: i for i, s in enumerate(SUBS, start=1)}
    for w, r in runs.items():
        allowed = {sub_index[sid] for oid in r["with"]["overlay_ids"] for sid in LAYERS[oid]["subregions"]}
        idx = r["idx"]
        inside, other, gap_far = 0, [], []
        for g, pts in r["added"].items():
            for x, z in pts:
                i = int(idx[z, x])
                if i in allowed:
                    inside += 1
                elif i != 0:
                    other.append((g, x, z, SUBS[i - 1]["id"]))
                elif not np.isin(idx[max(0, z - F.G):z + F.G + 1, max(0, x - F.G):x + F.G + 1], list(allowed)).any():
                    gap_far.append((g, x, z))
        assert inside > 500, (w, inside)
        assert not other, (w, "in another named sub-region", len(other), other[:8])
        assert not gap_far, (w, "on unassigned ground away from the overlay", gap_far[:8])


def _segments():
    for rt in ROUTES["routes"]:
        pts = [(float(p["x"]), float(p["z"])) for p in ((rt.get("corridor") or {}).get("polyline") or [])]
        for a, b in zip(pts, pts[1:]):
            yield rt["id"], a, b


def _dist(px, pz, a, b):
    (ax, az), (bx, bz) = a, b
    dx, dz = bx - ax, bz - az
    L = dx * dx + dz * dz
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / L))
    return math.hypot(px - (ax + t * dx), pz - (az + t * dz))


def _near_routes(added, window, clearance):
    """Added objects any column of whose ground-contact square lies within clearance of a route centreline."""
    x0, z0, s = WINDOWS[window]
    segs = [(rid, a, b) for rid, a, b in _segments()
            if max(a[0], b[0]) >= x0 - 64 and min(a[0], b[0]) <= x0 + s + 64
            and max(a[1], b[1]) >= z0 - 64 and min(a[1], b[1]) <= z0 + s + 64]
    near = []
    for g, pts in added.items():
        r = GROUND_R[g]
        for x, z in pts:
            wx, wz = x + x0, z + z0
            for rid, a, b in segs:
                # the nearest column of the square to the line is within r (Chebyshev) of the origin
                if _dist(wx, wz, a, b) - r * math.sqrt(2) > clearance:
                    continue
                cols = [(wx + i, wz + j) for i in range(-r, r + 1) for j in range(-r, r + 1)]
                d = min(_dist(cx, cz, a, b) for cx, cz in cols)
                if d < clearance:
                    near.append((g, wx, wz, rid, round(d, 2)))
                    break
    return near, segs


# removing this lets prop roots, knees and root tangles wall a route: overlays.path_clearance_blocks keeps every
# overlay object's ground contact that far from every route centreline in data/routes.json
def test_nothing_an_overlay_adds_is_within_route_clearance(runs, full_masks):
    clearance = DOC["overlays"]["path_clearance_blocks"]
    assert clearance > 0
    near, segs = _near_routes(runs["marsh"]["added"], "marsh", clearance)
    assert segs, "a route crosses the marsh window, so the rule has a case"
    assert not near, near[:8]
    # teeth: the same marsh overlays placed with no route lanes do put ground contact inside the clearance
    free, _ = _place(DOC, "marsh", full_masks, with_paths=False)
    without = runs["marsh"]["without"]["positions"]
    free_added = {g: pts[len(without.get(g, [])):] for g, pts in free["positions"].items()}
    assert _near_routes(free_added, "marsh", clearance)[0]
    # the jungle window has no route; recorded so a route added there later is checked here too
    jnear, _ = _near_routes(runs["jungle"]["added"], "jungle", clearance)
    assert not jnear, jnear[:8]


# removing this lets an overlay paint a biome, and every spawn pool that keys on biome changes under it
def test_no_overlay_sets_a_biome():
    assert LAYERS and all("biome" not in lay for lay in LAYERS.values())
    bad = copy.deepcopy(DOC)
    bad["overlays"]["layers"][0]["biome"] = "minecraft:mangrove_swamp"
    with pytest.raises(SystemExit, match="biome"):
        F.overlay_layers(bad)


# vanilla Minecraft 1.21.1 blocks the swamp objects may use, with the properties (and values) each accepts; written
# from the game's block states, not from the generator
BOOL = {"true", "false"}
AXIS = {"x", "y", "z"}
LEAVES = {"distance": {str(i) for i in range(1, 8)}, "persistent": BOOL, "waterlogged": BOOL}
VANILLA = {
    "minecraft:mangrove_roots": {"waterlogged": BOOL},
    "minecraft:muddy_mangrove_roots": {"axis": AXIS},
    "minecraft:mangrove_propagule": {"age": {str(i) for i in range(5)}, "hanging": BOOL, "stage": {"0", "1"},
                                     "waterlogged": BOOL},
    "minecraft:mangrove_log": {"axis": AXIS}, "minecraft:stripped_mangrove_log": {"axis": AXIS},
    "minecraft:oak_log": {"axis": AXIS}, "minecraft:stripped_oak_log": {"axis": AXIS},
    "minecraft:mangrove_leaves": LEAVES, "minecraft:oak_leaves": LEAVES,
    "minecraft:vine": {k: BOOL for k in ("north", "east", "south", "west", "up")},
    "minecraft:moss_carpet": {},
}


def _swamp_rows():
    return [r for r in LIB["objects"] if r["group"] in SWAMP_GROUPS]


# removing this lets a swamp object carry a modded or misspelled block, or a state vanilla 1.21.1 does not have, which
# WorldPainter writes into the export and Minecraft turns into air or refuses
def test_swamp_objects_use_only_vanilla_blocks_and_states():
    rows = _swamp_rows()
    assert {r["group"] for r in rows} == SWAMP_GROUPS and len(rows) >= 20
    for r in rows:
        t = S.load(LIB_DIR / r["file"])
        assert t["blocks"], r["name"]
        for name, props in t["palette"]:
            assert name in VANILLA, (r["name"], name)
            for k, v in props.items():
                assert k in VANILLA[name] and str(v) in VANILLA[name][k], (r["name"], name, k, v)


# removing this lets the committed swamp objects drift from the seeded code that claims to produce them (an edit to
# mangrove() without a regenerate, or a hand-edited .nbt), including a file whose bytes no longer match its library row
def test_committed_swamp_objects_match_the_generator():
    produced = {n: (g, b) for n, (g, b) in FO.generated_objects().items() if g in SWAMP_GROUPS}
    rows = {r["name"]: r for r in _swamp_rows()}
    assert set(rows) == set(produced), set(rows) ^ set(produced)
    for name, (group, builder) in produced.items():
        data, shift = builder.to_bytes()
        on_disk = (LIB_DIR / rows[name]["file"]).read_bytes()
        assert rows[name]["group"] == group and rows[name]["source"] == "generated", name
        assert list(rows[name]["origin"]) == list(shift), name
        assert hashlib.sha256(on_disk).hexdigest() == hashlib.sha256(data).hexdigest() == rows[name]["sha256"], name

"""tools/fungal_isle.py: the Fungal Isle grown over (data/fungal_isle.json).

The BUILDER's tests, written by the agent that wrote the generator: they hold the plan to the brief and the rules,
recomputing what they can from the heightmap and the shared data files (the ring, the tower and the Newmoon island from the
files that place them, the island from data/regions.json polygons by the ray cast, the sea from data/world.json) rather
than from the plan. They are not the independent audit (docs/world-building/FUNGAL_ISLE.md, "What an audit must check").

Needs the canonical heightmap; a skip names it. NOT covered, and it needs a running server: that the fills land, that the
pool holds water in game, that the three activated Habitat Blocks keep their pools visible (EXP-021's shape, the
Ursaluna's den and the Old Orchard use it), that Tadbulb spawns submerged in a 392-block pool, that no water-nearby species
appears at the hollow, that Toedscruel and night Shiinotic spawn only at night, and how any of it looks.
"""
import copy
import json
import math
import sys
from collections import deque
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import fungal_isle as FI  # noqa: E402
import function_limits  # noqa: E402


def _load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


DOC = FI.load()
SEA = _load("world.json")["vertical"]["sea_level"]


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
    return FI.plan(DOC, ground)


@pytest.fixture(scope="module")
def built(pl):
    return FI.files(pl=pl)


def _all(pl):
    return list(FI.all_blocks(pl))


# ------------------------------------------------------------------ the record


def test_one_nest_per_glade_and_the_glade_ids_are_unique():
    assert sorted(g["id"] for g in DOC["glades"]) == sorted(n["id"] for n in DOC["nests"])
    assert len({g["id"] for g in DOC["glades"]}) == 3


def test_the_island_is_the_fungal_isle_and_its_sea_level_is_the_worlds():
    assert DOC["island"]["region"] == "fungal_isle" and DOC["island"]["sea_level"] == SEA
    assert any(r["id"] == "fungal_isle" for r in _load("regions.json")["regions"])


def test_no_allowed_block_is_concrete_and_the_only_spawn_block_is_the_whitelisted_water():
    ids = set(DOC["blocks"]["ids"])
    assert not [b for b in ids if "concrete" in b]
    spawn = set(_load("spawn_blocks.json")["blocks"])
    assert ids & spawn == {"minecraft:water"}
    assert FI.policy_whitelist() == {"minecraft:water"}
    # the contract's own scope rule (tests/test_system_contracts.py C4): an entry whose scope names the place allows it
    pol = _load("spawn_block_policy.json")["whitelist"]
    assert [w for w in pol if "fungal_isle" in w["scope"] and "minecraft:water" in w["blocks"]]


# ------------------------------------------------------------------ the plan, against the heightmap


def test_the_plan_has_the_objects_and_the_counts_the_brief_asks_for(pl):
    c = pl.counts
    assert c["giants"] >= 60 and c["mediums"] >= 150 and c["stumps"] >= 50 and c["logs"] >= 25 and c["tufts"] >= 500, c
    kinds = {o.kind for o in pl.objs}
    assert {"beacon", "elder", "great_stump", "stump", "audience", "bowl", "lamps", "rim"} <= kinds
    assert set(pl.fns) >= {"cap_wood", "stump_court", "glowcap_hollow"}


def test_the_plan_is_deterministic(ground):
    a = FI.plan(DOC, ground)
    b = FI.plan(copy.deepcopy(DOC), ground)
    fa, fb = FI.functions(a), FI.functions(b)
    assert fa == fb and sum(len(v) for v in fa.values()) > 20000


def test_every_object_stands_in_the_island_above_the_sea_and_off_the_coast(pl, ground):
    """Recomputed by the ray cast against data/regions.json and the heightmap, not by the generator's raster."""
    import subregion_boxes as SB
    reg = [r for r in _load("regions.json")["regions"] if r["id"] == "fungal_isle"][0]
    polys = reg["polygons"]
    rules = DOC["rules"]
    bad = []
    for o in pl.objs:
        x, z = o.ax, o.az
        if not any(SB.point_in_polygon(x, z, p) for p in polys):
            bad.append((o.id, "outside", x, z))
            continue
        if ground(x, z) < rules["min_ground"]:
            bad.append((o.id, "low", x, z, ground(x, z)))
        for k in range(16):
            a = 2 * math.pi * k / 16
            qx, qz = int(round(x + rules["shore_clear"] * math.cos(a))), int(round(z + rules["shore_clear"] * math.sin(a)))
            if ground(qx, qz) <= SEA + 2 or not any(SB.point_in_polygon(qx, qz, p) for p in polys):
                bad.append((o.id, "coast", x, z))
                break
    assert not bad, bad[:5]


def test_nothing_is_written_inside_the_ring_the_tower_or_under_the_newmoon_island(pl):
    ring = [r for r in _load("southern_residents.json")["residents"] if r["id"] == "fairy_ring"][0]["site"]["centre"]
    pm = {p["id"]: p for p in _load("placements.json")["placements"]}
    tw = pm["legendary_zapdos_tower"]["position"]
    nm = pm["legendary_newmoon_island"]["position"]
    assert (ring, tw["x"], tw["z"], nm["x"], nm["y"], nm["z"]) == ([608, 5888], 881, 5569, 24, 141, 5582)
    bad = []
    for o, layer, (x, y, z), v in _all(pl):
        if math.hypot(x - ring[0], z - ring[1]) < 15 + 10:
            bad.append(("ring", o.id, x, z))
        if tw["x"] - 8 <= x <= tw["x"] + 30 + 8 and tw["z"] - 8 <= z <= tw["z"] + 28 + 8:
            bad.append(("tower", o.id, x, z))
        if nm["x"] - 16 <= x <= nm["x"] + 100 + 16 and nm["z"] - 16 <= z <= nm["z"] + 99 + 16:
            if y > nm["y"] - 2:
                bad.append(("newmoon", o.id, x, y, z))
            if o.kind in ("giants", "beacon", "elder", "wood", "audience", "rim"):
                bad.append(("newmoon giant", o.id, x, z))
    assert not bad, bad[:5]


def test_nothing_is_written_within_the_map_margin_of_the_west_edge(pl):
    assert min(x for x, _z in pl.written_cols) >= DOC["rules"]["map_margin"]


def test_no_block_is_concrete_or_outside_the_allow_list_and_the_text_has_no_concrete(pl, built):
    out, _ = built
    allowed = set(DOC["blocks"]["ids"])
    written = {FI.base(v) for _o, _l, _k, v in _all(pl)} | {p[6] for o in pl.objs for p in o.paints}
    assert written <= allowed
    assert not [t for t in out.values() if "concrete" in t]


def _neighbours(p):
    x, y, z = p
    return ((x + 1, y, z), (x - 1, y, z), (x, y + 1, z), (x, y - 1, z), (x, y, z + 1), (x, y, z - 1))


def _floating(pl, ground):
    """A breadth-first walk over each object's solid and hung blocks from the blocks that touch ground: the ground under a
    column is its rounded heightmap cell. Anything the walk does not reach hangs in the air."""
    floating = []
    for o in pl.objs:
        if o.kind in ("bowl",):
            continue
        blocks = set(o.solid) | set(o.hung)
        if not blocks:
            continue
        seeds = [p for p in blocks if p[1] - 1 <= ground(p[0], p[2])]
        seen = set(seeds)
        q = deque(seeds)
        while q:
            p = q.popleft()
            for n in _neighbours(p):
                if n in blocks and n not in seen:
                    seen.add(n)
                    q.append(n)
        lost = blocks - seen
        if lost:
            floating.append((o.id, o.kind, len(lost), sorted(lost)[:2]))
    return floating


def test_no_block_floats_every_object_is_one_piece_resting_on_its_ground(pl, ground):
    floating = _floating(pl, ground)
    assert not floating, floating[:5]


def test_a_stem_or_log_starts_on_its_own_columns_ground(pl, ground):
    """The lowest stem or log block of every column of every object is the block over that column's ground (not buried,
    not hovering): the tool places by `each on its own ground`."""
    off = []
    for o in pl.objs:
        if o.kind in ("bowl", "lamps"):
            continue
        cols = {}
        for (x, y, z), v in o.solid.items():
            if FI.base(v) in (FI.STEM, FI.LOG, "minecraft:dark_oak_log"):
                cols[(x, z)] = min(cols.get((x, z), 10 ** 9), y)
        for (x, z), y in cols.items():
            # a cap block can sit lower than the stem top, so only columns with no other block under the lowest stem count
            if y != ground(x, z) + 1 and (x, y - 1, z) not in o.solid and (x, y - 1, z) not in o.hung:
                # the stem of a leaning umbrella, a tiered mushroom's upper stem and a lamp's stem start on something else
                if not any((x, yy, z) in o.solid for yy in range(ground(x, z) + 1, y)):
                    off.append((o.id, x, z, y, ground(x, z)))
    assert not off, off[:5]


def test_every_small_mushroom_has_podzol_or_mycelium_written_under_it(pl):
    n = 0
    for o, layer, (x, y, z), v in _all(pl):
        if FI.base(v) in ("minecraft:red_mushroom", "minecraft:brown_mushroom"):
            n += 1
            below = pl.claimed.get((x, y - 1, z))
            assert below and FI.base(below[2]) in ("minecraft:podzol", "minecraft:mycelium"), (o.id, x, y, z)
    assert n > 1500


def test_the_spots_on_a_red_dome_are_stem_white_and_the_dome_is_closed_on_top():
    cap = FI.dome_cap(8, 6, 1.45, FI.RED, True, 7)
    tops = {}
    for (dx, dy, dz), v in cap.items():
        tops[(dx, dz)] = max(tops.get((dx, dz), -1), dy)
    assert any(v == FI.STEM for v in cap.values()) and any(v == FI.RED for v in cap.values())
    for (dx, dz), t in tops.items():
        if dx * dx + dz * dz <= 36:
            assert (dx, t, dz) in cap


# ------------------------------------------------------------------ the hollow


def _hollow(pl):
    return [o for o in pl.objs if o.id == "glowcap_hollow_bowl"][0]


def test_the_pool_cannot_leak_and_its_floor_is_under_the_water(pl, ground):
    o = _hollow(pl)
    yw = o.meta["pool_level"]
    water = {(x, z) for (x, y, z) in o.water}
    floor_top = {}
    for (x, y, z), v in o.floor.items():
        floor_top[(x, z)] = max(floor_top.get((x, z), -1), y)
    assert water and len(water) == o.meta["pool_cols"]
    for (x, z) in water:
        assert floor_top[(x, z)] < yw
        for n in ((x + 1, z), (x - 1, z), (x, z + 1), (x, z - 1)):
            if n not in water:
                top = floor_top.get(n, ground(*n))
                assert top >= yw, ("leak", (x, z), n, top, yw)
    ys = {y for (x, y, z) in o.water}
    assert max(ys) == yw
    cx, cz = [g for g in DOC["glades"] if g["id"] == "glowcap_hollow"][0]["centre"]
    assert (cx, cz) in water and (cx + 14, cz) not in water


def test_the_bowl_is_the_profile_the_data_says(pl, ground):
    gl = [g for g in DOC["glades"] if g["id"] == "glowcap_hollow"][0]
    cx, cz = gl["centre"]
    P = gl["pieces"]
    o = _hollow(pl)
    yc = ground(cx, cz)
    assert o.meta["yc"] == yc
    floor_top = {}
    for (x, y, z), v in o.floor.items():
        floor_top[(x, z)] = max(floor_top.get((x, z), -1), y)
    # the middle is the deepest point, depth below the surface as many blocks as pool.deep says
    assert floor_top[(cx, cz)] == yc - P["bowl"]["depth"] - P["pool"]["deep"]
    for (x, z), t in floor_top.items():
        assert t <= ground(x, z), "the bowl only cuts, it never raises ground"
        assert math.hypot(x - cx, z - cz) <= P["bowl"]["rim_radius"] + 2
    # carve boxes reach from above the floor to above the ground
    for x0, y0, z0, x1, y1, z1 in o.carve:
        assert x0 == x1 and z0 == z1 and y0 == floor_top[(x0, z0)] + 1 and y1 == ground(x0, z0) + 2


def test_the_hollow_has_light_and_every_light_is_a_froglight_or_shroomlight(pl):
    lights = [(FI.base(v)) for _o, _l, _k, v in _all(pl) if "light" in FI.base(v) and FI.base(v) != "minecraft:light"]
    assert lights and set(lights) <= {"minecraft:shroomlight", "minecraft:pearlescent_froglight", "minecraft:verdant_froglight"}
    froglights = [1 for o in pl.fns["glowcap_hollow"] for v in list(o.solid.values()) if "froglight" in v]
    assert len(froglights) >= 90


# ------------------------------------------------------------------ the wards and the records


def test_each_ward_is_a_block_the_pack_writes_and_is_its_mimic(pl):
    for n in DOC["nests"]:
        w = pl.wards[n["glade"]]
        st = pl.claimed.get(tuple(w))
        assert st and FI.base(st[2]) == n["mimic"], (n["id"], w, st)
        # with air to stand next to it: the ward is inside the object it hides in, never an exposed top block of a path
    assert len({tuple(w) for w in pl.wards.values()}) == 3


def test_the_records_on_disk_are_what_the_generator_writes(pl):
    habs, pools = FI.records(DOC, pl)
    hb = {b["id"]: b for b in _load("habitat_blocks.json")["blocks"]}
    for h in habs:
        assert hb[h["id"]] == h, h["id"]
        assert h["style"] == "activated" and h["replace_spawns"] is False and h["activated"]["cancel_range"] == -1
    sp = _load("spawns.json")
    for p in pools:
        assert [x for x in sp["habitats"] if x["id"] == p["habitat"]["id"]] == [p["habitat"]]
        assert [e for e in sp["entries"] if e["scope"] == p["habitat"]["id"]] == p["entries"]


def test_habitat_blocks_static_rules_hold_for_the_new_records():
    import habitat_blocks as HB
    probs = HB.static_problems(_load("habitat_blocks.json"), _load("spawns.json"))
    assert not [p for p in probs if p[0] and p[0].startswith("fungal_")], probs[:3]
    pools = HB.habitat_pool_ids(_load("spawns.json"))
    assert {"cobblers:fungal_cap_wood", "cobblers:fungal_stump_court", "cobblers:fungal_glowcap_hollow"} <= pools


def _species_json(name):
    import zipfile
    import glob
    cands = sorted(glob.glob("C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/Cobblemon-fabric-1.8.0*.jar"))
    if not cands:
        pytest.skip("the Cobblemon 1.8.0 jar snapshot is not on this machine")
    z = zipfile.ZipFile(cands[0])
    hits = [n for n in z.namelist() if n.startswith("data/cobblemon/species/") and n.endswith("/%s.json" % name)]
    assert hits, "no species %s in the Cobblemon 1.8.0 jar" % name
    return json.loads(z.read(hits[0]))


def _evo_level(species_doc):
    for e in species_doc.get("evolutions", []):
        for r in e.get("requirements", []):
            if r.get("variant") == "level":
                return e["result"], r["minLevel"]
    return None, None


def test_every_pool_species_exists_and_no_stage_is_younger_than_its_evolution():
    """Read from the Cobblemon 1.8.0 jar: an evolved stage spawns from its level; a base stage with a level evolution is held
    to four past it (data/spawns.json evolution_policy.rule)."""
    nests = {n["id"]: n for n in DOC["nests"]}
    pre = {}
    for n in DOC["nests"]:
        for r in n["entries"]:
            sd = _species_json(r["species"])
            nxt, lvl = _evo_level(sd)
            if nxt:
                pre[nxt] = (r["species"], lvl)
    for n in DOC["nests"]:
        for r in n["entries"]:
            lo, hi = (int(v) for v in r["level"].split("-"))
            sd = _species_json(r["species"])
            nxt, lvl = _evo_level(sd)
            if nxt:
                assert hi <= lvl + 4, (n["id"], r["species"], r["level"], lvl)
            if r["species"] in pre:
                assert lo >= pre[r["species"]][1], (n["id"], r["species"], r["level"], pre[r["species"]])


def test_the_bands_stay_inside_tier_three_and_the_above_cap_share_is_in_balance():
    design = _load("encounter_design.json")
    cap = design["rules"]["hearts"]["next_cap"]["3"]
    share = design["rules"]["hearts"]["above_cap_max_share"]
    top = _load("spawns.json")["subregions"]
    band = [s for s in top if s["id"] == "fungal_north"][0]["level_band"]
    assert band["maximum"] == 28 and cap == 35
    sp = _load("spawns.json")
    for n in DOC["nests"]:
        assert n["band"][0] == band["minimum"] and n["band"][1] <= cap
        es = [e for e in sp["entries"] if e["scope"] == n["pool"]]
        assert len(es) == len(n["entries"])
        tot = sum(e["weight"] for e in es)
        above = sum(e["weight"] for e in es if int(e["level"].split("-")[0]) > band["maximum"])
        assert above / tot <= share + 1e-9, (n["id"], above, tot)
        if n["id"] != "glowcap_hollow":
            assert n["band"][1] == band["maximum"] and above == 0


def test_the_new_pools_compile_and_carry_the_night_conditions():
    import compile_spawns as CS
    sp = _load("spawns.json")
    for n in DOC["nests"]:
        h = [x for x in sp["habitats"] if x["id"] == n["pool"]][0]
        ents = [e for e in sp["entries"] if e["mechanism"] == "habitat_block" and e["scope"] == n["pool"]]
        doc, _ = CS.compile_habitat(h, ents)
        assert len(doc["spawns"]) == len(n["entries"]) and all(" " not in s["species"] for s in doc["spawns"])
        night = {r["species"] for r in n["entries"] if (r.get("conditions") or {}).get("timeRange") == "night"}
        assert {s["species"] for s in doc["spawns"] if s.get("timeRange") == "night"} == night
    hollow = [e for e in sp["entries"] if e["scope"] == "fungal_glowcap_hollow" and e["species"] == "tadbulb"][0]
    assert hollow["spawnable_position"] == "submerged"


def test_the_nest_pools_are_micro_sites_for_the_nuzlocke_zones_tool():
    import nuzlocke_zones as NZ
    for n in DOC["nests"]:
        assert NZ.MICRO_SITE.search(n["pool"]), n["pool"]


def test_the_island_rosters_the_nests_lean_on_are_still_there():
    sp = _load("spawns.json")
    subs = {s["id"]: {e["pokemon"] for e in s["entries"]} for s in sp["subregions"]}
    assert {"paras", "shroomish", "morelull", "foongus", "toedscool"} <= subs["fungal_north"]
    assert {"croagunk", "tadbulb"} <= subs["fungal_south"]


# ------------------------------------------------------------------ the pack and the steps


def test_every_function_passes_the_function_limits_and_holds_its_chunks(pl, built):
    out, _ = built
    fns = [k for k in out if k.endswith(".mcfunction")]
    assert len(fns) == len(FI.functions_order(pl)) == 53
    steps = FI.placement_steps(pl=pl)
    holds = {}
    for kind, v in steps:
        if kind == "cmd" and v.startswith("forceload add"):
            cur = v
        if kind == "fn":
            holds[v] = cur
    for rel in fns:
        name = rel.rsplit("/", 1)[1][:-len(".mcfunction")]
        lines = out[rel].splitlines()
        assert function_limits.check_lines(lines, name) == []
        # the step's own forceload covers every write (the header's claim, checked rather than trusted)
        body = [holds["cobblers:fungal_isle/%s" % name]] + [l for l in lines if not l.startswith("# chunks-loaded-by")]
        assert function_limits.unloaded_writes(body) == [], name
        assert sum(1 for l in lines if l and not l.startswith("#")) < 5000


def test_the_steps_hold_run_and_release_every_function_and_the_pack_has_no_orphan(pl, built):
    out, _ = built
    steps = FI.placement_steps(pl=pl)
    fns = [v for k, v in steps if k == "fn"]
    packed = {"cobblers:fungal_isle/" + rel.rsplit("/", 1)[1][:-len(".mcfunction")] for rel in out if rel.endswith(".mcfunction")}
    assert set(fns) == packed and len(fns) == len(packed)
    assert len(steps) == 4 * len(fns)
    adds = [v for k, v in steps if k == "cmd" and v.startswith("forceload add")]
    rems = [v.replace("remove", "add") for k, v in steps if k == "cmd" and v.startswith("forceload remove")]
    assert adds == rems
    for a in adds:
        x0, z0, x1, z1 = (int(t) for t in a.split()[2:])
        assert ((x1 // 16 - x0 // 16) + 1) * ((z1 // 16 - z0 // 16) + 1) <= 256


def test_reapply_registers_the_pack_and_runs_r9fi_before_r9e_with_the_other_block_passes():
    text = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert text.index('"R9JT"') < text.index('"R9FI"') < text.index('("R9E"')
    server = text[text.index("SERVER_PACKS = ("):text.index("WORLD_LOCAL = (")]
    world_local = text[text.index("WORLD_LOCAL = ("):text.index("SPAWN_PACKS = (")]
    assert '"cobblers_fungal_isle"' in server and '"cobblers_fungal_isle"' not in world_local
    assert 'add("fungal_isle:build", "fungal_isle.py", "build", *src)' in text
    assert "cobblers_fungal_isle" not in text[text.index("EXCLUDED = {"):text.index("# server packs installed into the target world")]


def test_the_probes_on_disk_are_the_plans(pl):
    wp = _load("world_probes.json")["places"]
    got = FI.presence_probes(pl)
    assert wp["fungal_isle"] == got["fungal_isle"]
    rows = wp["fungal_isle"]
    assert len(rows) >= 60 and all(r["block"][1] > 0 for r in rows)
    ward = {tuple(w) for w in pl.wards.values()}
    assert not [r for r in rows if tuple(r["block"][:3]) in ward], "R9E replaces a ward block with the Habitat Block"
    assert any(r["expect"] is False for r in rows) and any(r["block"][3] == "minecraft:water" and r["expect"] for r in rows)


# ------------------------------------------------------------------ the guards bite (mutate the generator, not the record)


def test_a_log_hovering_over_its_ground_is_found_floating(ground, monkeypatch):
    def hover(plan, o, ax, az, length, seed):
        for k in range(length):
            plan.put(o, "solid", ax + k, plan.g(ax + k, az) + 4, az, "minecraft:dark_oak_log[axis=x]")
        o.meta.update({"stem_base": (ax, plan.g(ax, az) + 1, az), "top_y": plan.g(ax, az) + 4})
    monkeypatch.setattr(FI, "fallen_log", hover)
    p = FI.plan(DOC, ground)
    lost = _floating(p, ground)
    assert lost and all(f[1] == "logs" for f in lost) and len(lost) == p.counts["logs"], lost[:3]


def test_a_pool_whose_rim_is_cut_below_the_surface_is_refused(ground, monkeypatch):
    real = FI.hollow_profile

    def deeper(P, yc, r):
        out = real(P, yc, r)
        if out is None:
            return None
        fy, extra = out
        return (fy - 3 if r > 8 else fy), extra          # the bank round the pool dug under the water's surface
    monkeypatch.setattr(FI, "hollow_profile", deeper)
    p = FI.plan(DOC, ground)
    probs = FI.hollow_checks(p)
    assert probs and "leak" in " ".join(probs)


def test_a_glade_moved_onto_the_fairy_ring_is_refused(ground):
    d = copy.deepcopy(DOC)
    [g for g in d["glades"] if g["id"] == "stump_court"][0]["centre"] = [608, 5888]
    p = FI.plan(d, ground)
    probs = FI.check_plan(p)
    assert any("keep_clear" in s for s in probs), probs[:3]


def test_a_water_whitelist_removed_refuses_the_pool(pl, monkeypatch):
    monkeypatch.setattr(FI, "policy_whitelist", lambda: set())
    assert any("spawn condition names" in s for s in FI.check_plan(pl))


def test_a_block_outside_the_allow_list_is_refused(ground):
    d = copy.deepcopy(DOC)
    d["blocks"]["ids"] = [b for b in d["blocks"]["ids"] if b != "minecraft:shroomlight"]
    with pytest.raises(SystemExit):
        FI.plan(d, ground)

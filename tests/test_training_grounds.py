"""The levelling catch-up (data/training_grounds.json, tools/training_grounds.py, docs/mechanics/LEVEL_CATCHUP.md).

Every expectation here is read from where the rule lives -- the cap from rctmod's computation over data/trainers.json
(tools/legendaries_audit.py rct_caps), the ceilings from data/encounter_design.json, the ground from the canonical
heightmap, the paths from data/route_paths.json, the other nests from data/habitat_blocks.json, the yields and the
evolutions from the Cobblemon jar -- never from tools/training_grounds.py's own siting or record functions, except the
one test that says it checks the shared files are in step with the generator.
"""
import json
import math
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

DOC = json.loads((ROOT / "data" / "training_grounds.json").read_text(encoding="utf-8"))
HB = json.loads((ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8"))["blocks"]
SPAWNS = json.loads((ROOT / "data" / "spawns.json").read_text(encoding="utf-8"))
TOWNS = {t["id"]: t for t in json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]}
DESIGN = json.loads((ROOT / "data" / "encounter_design.json").read_text(encoding="utf-8"))
GROUNDS = DOC["grounds"]
IDS = [g["id"] for g in GROUNDS]


def block_of(gid):
    return next(b for b in HB if b["id"] == "%s_block" % gid)


def entries_of(gid):
    return [e for e in SPAWNS["entries"] if e.get("scope") == gid]


def cap_before(gym):
    import legendaries_audit as L
    c = L.rct_caps()
    return c[None] if gym == 1 else c["gym%d_cleared" % (gym - 1)]


def levels(s):
    a, _, b = s.partition("-")
    return int(a), int(b or a)


# Without it a gym town could be left without a ground, or one serve a town that is not a gym's.
def test_one_ground_per_gym_town():
    assert sorted(g["gym"] for g in GROUNDS) == list(range(1, 9))
    for g in GROUNDS:
        assert TOWNS[g["town"]]["role"] == "gym_town" and g["town"] == "gym%d_town" % g["gym"], g


# Without it the shared files could drift from the generator (a hand edit, a regeneration that dropped one).
def test_shared_records_are_in_step_with_the_generator():
    import training_grounds as TG
    hd, sd = TG.merged(DOC)
    assert TG.dumps(hd) == (ROOT / "data" / "habitat_blocks.json").read_text(encoding="utf-8")
    assert TG.dumps(sd) == (ROOT / "data" / "spawns.json").read_text(encoding="utf-8")


# The owner: "without letting anyone exceed it". A ground's Pokemon at or under the cap stay catchable (rctmod and the
# catch block refuse only strictly above it) and never out-level the team the ground is filling.
@pytest.mark.parametrize("gid", IDS)
def test_a_grounds_levels_sit_just_under_the_cap_before_its_gym(gid):
    g = next(x for x in GROUNDS if x["id"] == gid)
    cap = cap_before(g["gym"])
    es = entries_of(gid)
    assert es, "%s has no spawn entries" % gid
    for e in es:
        lo, hi = levels(e["level"])
        assert hi <= cap, "%s %s tops out at %d over the cap %d" % (gid, e["species"], hi, cap)
        assert lo >= cap - 5, "%s %s starts at %d, far under the cap %d: not a catch-up" % (gid, e["species"], lo, cap)
    hab = next(h for h in SPAWNS["habitats"] if h["id"] == gid)
    assert hab["level_band"]["maximum"] <= cap


# Without it a ground could hold a Pokemon over its place's ceiling (the residents' rule, tests/test_resident_siting.py).
@pytest.mark.parametrize("gid", IDS)
def test_a_grounds_levels_are_within_its_places_ceiling(gid):
    from subregion_boxes import point_in_polygon
    b = block_of(gid)
    x, z = b["position"]["x"], b["position"]["z"]
    subs = [s["id"] for s in json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))["subregions"]
            if any(point_in_polygon(x, z, p) for p in s.get("polygons") or []) and s["id"] in DESIGN["tables"]]
    assert subs, "%s stands in no sub-region with a table" % gid
    ceiling = DESIGN["rules"]["hearts"]["next_cap"][str(DESIGN["tables"][subs[0]]["tier"])]
    assert max(levels(e["level"])[1] for e in entries_of(gid)) <= ceiling, (gid, subs[0], ceiling)


def _jar_species():
    import battle_sim
    try:
        jar = battle_sim.find_jar()
    except Exception as exc:          # noqa: BLE001
        pytest.skip("NOT_EXECUTED: no Cobblemon 1.8 jar: %s" % exc)
    out = {}
    with zipfile.ZipFile(jar) as z:
        for n in z.namelist():
            if n.startswith("data/cobblemon/species/") and n.endswith(".json"):
                d = json.loads(z.read(n))
                out[d["name"].lower()] = d
    return out


# data/spawns.json evolution_policy: "Evolutions not by level appear only from tier 6". A species whose line has a
# non-level evolution into it (Chansey from Happiny by a held item, Blissey from Chansey by friendship) may stand only
# at a ground of gym 6 or later. Read from the jar, not from the design's roster split.
def test_a_species_reached_by_a_non_level_evolution_stands_only_from_tier_6():
    sp = _jar_species()
    by_result = {}
    for name, d in sp.items():
        for ev in d.get("evolutions") or []:
            res = str(ev.get("result", "")).split()[0].lower()
            by_result.setdefault(res, []).append([r.get("variant") for r in ev.get("requirements") or []])
    for g in GROUNDS:
        for e in entries_of(g["id"]):
            reqs = by_result.get(e["species"], [])
            non_level = any(set(r) != {"level"} for r in reqs) if reqs else False
            if non_level:
                assert g["gym"] >= DESIGN["rules"]["non_level_evolution_min_tier"]["other"], (g["id"], e["species"], reqs)


# The ground's whole point is its yield: each species must really be among the highest base-experience species.
def test_the_roster_is_the_jars_highest_yield():
    sp = _jar_species()
    for g in GROUNDS:
        for e in entries_of(g["id"]):
            assert sp[e["species"]]["baseExperienceYield"] >= 390, (e["species"], sp[e["species"]]["baseExperienceYield"])


# Without it a ground could sit in a street, on a path, in a lake, or inside another nest's spawns. Measured here from
# the heightmap and the data, not by the generator's own Site.
@pytest.mark.parametrize("gid", IDS)
def test_a_ground_is_sited_by_the_rules(gid):
    import ground as G
    import terrain as T
    g = next(x for x in GROUNDS if x["id"] == gid)
    r = DOC["rules"]
    b = block_of(gid)
    x, y, z = b["position"]["x"], b["position"]["y"], b["position"]["z"]
    sr = b["activated"]["spawn_range"]
    t = TOWNS[g["town"]]["centre"]
    d = math.hypot(x - t["x"], z - t["z"])
    assert r["ring_blocks"][0] <= d <= r["ring_blocks"][1], (gid, d)
    pts = np.array([p for pl in json.loads((ROOT / "data" / "route_paths.json").read_text(encoding="utf-8"))["paths"].values()
                    for p in pl], float)
    assert float(np.min(np.hypot(pts[:, 0] - x, pts[:, 1] - z))) >= r["path_clear_blocks"], gid
    for o in HB:
        if o["id"] == b["id"]:
            continue
        dd = math.hypot(o["position"]["x"] - x, o["position"]["z"] - z)
        need = o["activated"]["spawn_range"] + sr if o.get("style") == "activated" else o.get("range_of_influence", 0) + sr
        assert dd >= need, "%s is %.0f from %s, needs %d" % (gid, dd, o["id"], need)
    try:
        gr = G.load()
    except (SystemExit, Exception) as exc:   # noqa: BLE001
        pytest.skip("NOT_EXECUTED: no heightmap: %s" % exc)
    assert gr(x, z) == y, "%s's block y%d is not the heightmap's ground y%d" % (gid, y, gr(x, z))
    rr = r["flat_radius_blocks"]
    box = gr.box(x - rr, z - rr, x + rr, z + rr)
    yy, xx = np.mgrid[-rr:rr + 1, -rr:rr + 1]
    assert int(np.ptp(box[xx * xx + yy * yy <= rr * rr])) <= r["max_relief_blocks"], gid
    wr = sr + r["water_margin_blocks"]
    box = gr.box(x - wr, z - wr, x + wr, z + wr)
    yy, xx = np.mgrid[-wr:wr + 1, -wr:wr + 1]
    assert int((box[xx * xx + yy * yy <= wr * wr] <= T.sea_level(gr.world)).sum()) == 0, "%s has sea within %d" % (gid, wr)


# The design rests on rctmod clamping every EXP gain at the cap. That holds only while the server keeps
# allowOverLeveling false (rctmod 0.19.0-beta ModServer.onExperienceGained returns early when it is true).
def test_the_rctmod_config_keeps_the_exp_clamp_on():
    text = (ROOT / "modpack" / "config" / "rctmod-server.toml").read_text(encoding="utf-8")
    assert re.search(r"^\s*allowOverLeveling\s*=\s*false\s*$", text, re.M), "allowOverLeveling is not false"


# The estimate's multiplier must be the server's (Cobblemon config experienceMultiplier).
def test_the_estimate_uses_the_servers_exp_multiplier():
    import training_grounds as TG
    cfg = json.loads((ROOT / "modpack" / "config" / "cobblemon" / "main.json").read_text(encoding="utf-8"))
    assert TG.EXP_MULTIPLIER == cfg["experienceMultiplier"]


# One knock-out worked by hand from StandardExperienceCalculator (Cobblemon 1.8.0, javap): Audino L17 against a L12:
# 390 * 17 / 5 = 1326; ((2*17 + 10) / (17 + 12 + 10)) ** 2.5 = 1.35190; 1326 * 1.35190 + 1 = 1793.6; x 2.0 = 3587.
def test_one_knock_out_matches_the_hand_worked_figure():
    import training_grounds as TG
    assert TG.ko_exp(390, 17, 12) == 3587


# Without it the sign could be written somewhere other than its ground, facing away from the town, or carry a block
# that is a spawn condition.
def test_the_sign_pack_places_one_sign_per_ground_facing_its_town(tmp_path):
    import ground as G
    import training_grounds as TG
    try:
        gr = G.load()
    except (SystemExit, Exception) as exc:   # noqa: BLE001
        pytest.skip("NOT_EXECUTED: no heightmap: %s" % exc)
    fn, lines = TG.build(DOC, tmp_path / "pack", gr)
    sets = [l for l in lines if l.startswith("setblock")]
    assert len(sets) == len(GROUNDS)
    for g, line in zip(GROUNDS, sets):
        m = re.match(r"setblock (-?\d+) (-?\d+) (-?\d+) minecraft:oak_sign\[rotation=(\d+)\]", line)
        assert m, line
        x, y, z, rot = map(int, m.groups())
        s = g["site"]
        assert (x - s["x"], z - s["z"]) == tuple(DOC["sign"]["offset"]) and y == gr(x, z) + 1, (g["id"], line)
        t = TOWNS[g["town"]]["centre"]
        # rotation 0 faces +z (south), 4 -x (west), 8 -z (north), 12 +x (east)
        fx, fz = -math.sin(math.radians(rot * 22.5)), math.cos(math.radians(rot * 22.5))
        dx, dz = t["x"] - x, t["z"] - z
        assert (fx * dx + fz * dz) / math.hypot(dx, dz) > math.cos(math.radians(12)), (g["id"], rot, dx, dz)
    spawn_blocks = json.dumps(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
    assert "oak_sign" not in spawn_blocks


# The estimate is clamped as rctmod clamps it: no member is ever counted past the cap, and the KOs grow with the gym.
def test_the_estimate_never_counts_past_the_cap_and_grows_with_the_gym():
    import training_grounds as TG
    rows = TG.estimate(DOC)
    assert [r[0] for r in rows] == list(range(1, 9))
    assert all(r[2] <= r[3] for r in rows)
    assert rows[-1][3] > rows[0][3]

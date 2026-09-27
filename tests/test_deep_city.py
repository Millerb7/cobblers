"""tools/deep_city.py and tools/deep_city_audit.py: the Windward Deep's city and the relic area's surface.

What is asserted without a world:
  - the audit is independent of the build: it never imports tools/deep_city.py or reads data/deep_city.json, so its
    expectations do not come from the artifact it checks;
  - the audit, on a small synthetic pit with nonempty output, passes a clean city and catches each failure it exists
    for: a write outside the pit, below a terrace, into a sealed volume, into Victory Road's mouth or over its plaza,
    onto a lift or its rider's space, a lift with nowhere to land, a street walled off, a relic write too deep, and a
    gap in the relic cordon;
  - on the real build (when it and the heightmap are present), the audit is clean;
  - nothing the city places conditions a spawn, and nothing is a light block;
  - the stair towers' geometry lands on the back row for every riser the pit has;
  - the re-apply runs the city after the Deep and Victory Road and before the Habitat Blocks and the lights, and ships
    its pack;
  - the reserved volumes hold the sited cradle, passage and HQ.

Not covered, and it needs a running server and a player: that the functions load and run, that a player climbs the
towers and ladders, that a lumymon lift lands where the towers give it a floor, how the lighting looks at night.
"""
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import deep_city_audit as A  # noqa: E402

SPEC = json.loads((ROOT / "data" / "deep_city.json").read_text(encoding="utf-8"))
REGIONS = json.loads((ROOT / "data" / "rift_regions.json").read_text(encoding="utf-8"))
SPAWN = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
FN = ROOT / "build" / "datapacks" / "cobblers_deep_city" / "data" / "cobblers" / "function" / "deep_city"


# ------------------------------------------------------------------ independence

def test_the_audit_does_not_take_its_expectations_from_the_build():
    src = (ROOT / "tools" / "deep_city_audit.py").read_text(encoding="utf-8")
    code = "\n".join(l for l in src.splitlines() if not l.strip().startswith("#"))
    body = code.split('"""', 2)[2]                          # past the docstring
    assert "import deep_city\n" not in body and "import deep_city " not in body and "deep_city as" not in body
    assert "deep_city.json" not in body, "the audit reads the build's own layout"
    for source in ("rift_deep", "vr_caves.json", "rift_regions.json", "ground"):
        assert source in body


# ------------------------------------------------------------------ the audit on a synthetic pit

def _plan():
    """A 100 x 100 frame: a pit x5-94 z5-94, an upper ring at y20 west of x15 and a lower one at y10; the relic area
    x96-99 z80-85 on ground y30 with a sealed volume under it; a lift pair at the riser; Victory Road's mouth at
    (80, 11, 5), so its tunnel runs north out of the frame and its plaza covers x48-112 z6-65."""
    shape = (100, 100)
    pit = np.zeros(shape, bool)
    pit[5:95, 5:95] = True
    T = np.full(shape, -9999, np.int32)
    T[5:95, 5:15] = 20
    T[5:95, 15:95] = 10
    relic = np.zeros(shape, bool)
    relic[80:86, 96:100] = True
    H = np.full(shape, 30, np.int32)
    return {"X0": 0, "Z0": 0, "pit": pit, "T": T, "relic": relic, "H": H,
            "lifts": [((15, 10, 20), (14, 20, 20))], "mouth": (80, 11, 5),
            "sealed": {"cradle": (96, 0, 80, 99, 20, 85)}, "levels": [20, 10]}


def _clean():
    w = []
    w.append((20, 11, 74, 24, 19, 74, "moarconcrete:white_concrete_texture"))       # a building on the lower street
    w.append((20, 20, 74, 24, 20, 74, "rechiseled:blackstone_polished_connecting"))  # its roof, the street above
    w.append((8, 21, 8, 8, 22, 8, "minecraft:end_rod[facing=up]"))                   # something on the upper ring
    w.append((15, 20, 20, 15, 20, 20, "rechiseled:blackstone_polished_connecting"))  # the up-lift's landing floor
    w.append((14, 11, 20, 14, 12, 20, "minecraft:air"))                              # the down-lift's landing, cut
    for z in range(80, 86):                                                           # the relic cordon
        for x in range(96, 100):
            if x in (96, 99) or z in (80, 85):
                w.append((x, 31, z, x, 33, z, "minecraft:iron_bars"))
    w.append((97, 31, 82, 97, 40, 82, "minecraft:raw_gold_block"))                   # a relic ring piece
    return w


def _kinds(writes):
    problems, _stats = A.audit(writes, _plan())
    return {k for k, _m in problems}, problems


def test_a_clean_city_passes_and_is_not_empty():
    kinds, problems = _kinds(_clean())
    assert not problems, problems
    _p, stats = A.audit(_clean(), _plan())
    assert stats["writes"] > 0 and stats["relic_writes"] > 0 and stats["levels_written"] == [10, 20]


@pytest.mark.parametrize("write,kind", [
    ((2, 12, 2, 2, 12, 2, "minecraft:stone"), "inside"),
    ((25, 5, 25, 25, 5, 25, "minecraft:stone"), "terraces"),
    ((25, 160, 25, 25, 160, 25, "minecraft:stone"), "terraces"),
    ((97, 12, 82, 97, 12, 82, "minecraft:stone"), "sealed"),
    ((80, 12, 3, 80, 12, 3, "minecraft:stone"), "mouth"),
    ((80, 12, 12, 80, 12, 12, "minecraft:stone"), "mouth"),
    ((15, 11, 20, 15, 11, 20, "minecraft:stone"), "lifts"),
    ((14, 21, 20, 14, 21, 20, "minecraft:light_blue_stained_glass_pane"), "lifts"),
    ((98, 22, 83, 98, 22, 83, "minecraft:gravel"), "relic"),
])
def test_the_audit_catches_each_failure(write, kind):
    kinds, problems = _kinds(_clean() + [write])
    assert kind in kinds, problems


def test_the_audit_catches_a_lift_with_no_floor_to_land_on():
    kinds, _p = _kinds([w for w in _clean() if w[:3] != (15, 20, 20)])
    assert "lifts" in kinds


def test_the_audit_catches_a_down_lift_landing_in_rock():
    kinds, _p = _kinds([w for w in _clean() if w[:3] != (14, 11, 20)])
    assert "lifts" in kinds


def test_the_audit_catches_a_street_walled_off():
    ring = [(x, 11, z, x, 12, z, "minecraft:stone") for x in range(15, 18) for z in range(18, 23)
            if (x, z) != (15, 20) and (x == 17 or z in (18, 22))]
    kinds, problems = _kinds(_clean() + ring)
    assert "streets" in kinds, problems


def test_the_audit_catches_a_gap_in_the_cordon():
    kinds, _p = _kinds([w for w in _clean() if w[:3] != (99, 31, 83)])
    assert "cordon" in kinds


def test_the_audit_catches_an_empty_output():
    kinds, _p = _kinds([])
    assert "nonempty" in kinds


def test_parse_reads_fills_setblocks_and_templates():
    w = A.parse(["fill 3 4 5 1 2 9 minecraft:stone", "setblock 7 8 9 minecraft:air", "# a comment",
                 "place template cobblers:x 10 20 30 180 none 1.0 0"], {"cobblers:x": (3, 4, 5)})
    assert w[0] == (1, 2, 5, 3, 4, 9, "minecraft:stone")
    assert w[1] == (7, 8, 9, 7, 8, 9, "minecraft:air")
    assert w[2] == (8, 20, 26, 10, 23, 30, "template:cobblers:x")


# ------------------------------------------------------------------ the real build

def _source_root():
    root = os.environ.get("COBBLERS_SOURCE_ROOT")
    if not root or not Path(root).is_dir():
        pytest.skip("no COBBLERS_SOURCE_ROOT: the plan comes from the heightmap")
    return root


def test_the_built_city_audits_clean():
    if not (FN / "index.txt").is_file():
        pytest.skip("the city is not built here (python tools/deep_city.py build)")
    root = _source_root()
    lines, templates = A.output_lines()
    writes = A.parse(lines, templates)
    problems, stats = A.audit(writes, A.load_plan(root))
    assert not problems, problems[:10]
    assert stats["writes"] > 10000 and len(stats["levels_written"]) == 5


def test_the_built_city_places_no_light_block_and_no_unwhitelisted_spawn_block():
    if not (FN / "index.txt").is_file():
        pytest.skip("the city is not built here (python tools/deep_city.py build)")
    used = set()
    for f in FN.glob("*.mcfunction"):
        for line in f.read_text(encoding="utf-8").splitlines():
            m = re.match(r"(?:fill -?\d+ -?\d+ -?\d+ -?\d+ -?\d+ -?\d+|setblock -?\d+ -?\d+ -?\d+) (\S+)", line)
            if m:
                used.add(m.group(1).split("[")[0].split("{")[0])
    assert "minecraft:light" not in used
    assert not used & SPAWN, sorted(used & SPAWN)


# ------------------------------------------------------------------ the data

def _ids(obj):
    out = set()
    if isinstance(obj, dict):
        for v in obj.values():
            out |= _ids(v)
    elif isinstance(obj, list):
        for v in obj:
            out |= _ids(v)
    elif isinstance(obj, str) and re.fullmatch(r"[a-z_]+:[a-z0-9_]+(\[.*\])?", obj):
        out.add(obj.split("[")[0])
    return out


def test_nothing_the_palette_names_conditions_a_spawn_or_is_a_light_block():
    used = _ids(SPEC["materials"]) | _ids(SPEC["lights"]["emitters"]) | _ids(SPEC["districts"]) | _ids(SPEC["plaza"])
    src = (ROOT / "tools" / "deep_city.py").read_text(encoding="utf-8")
    used |= {m.split("[")[0] for m in re.findall(r'"((?:minecraft|handcrafted|beautify):[a-z0-9_]+)', src)}
    assert "minecraft:light" not in used
    assert not used & SPAWN, sorted(used & SPAWN)
    assert "minecraft:iron_block" not in used and "minecraft:redstone_lamp" not in used


def test_the_reserved_volumes_hold_what_the_rift_sites():
    s = REGIONS["sited"]
    boxes = {r["id"]: r["box"] for r in SPEC["reserved"]}

    def inside(p, b):
        return b[0] <= p[0] <= b[3] and b[1] <= p[1] <= b[4] and b[2] <= p[2] <= b[5]
    cx, cz = s["hoopa_cradle"]["centre"]
    assert inside((cx, s["hoopa_cradle"]["floor_y"], cz), boxes["hoopa_cradle"])
    assert inside(tuple(s["cradle_passage"]["from"]), boxes["cradle_passage"])
    assert inside(tuple(s["cradle_passage"]["to"]), boxes["cradle_passage"])
    assert inside(tuple(s["haven_compact_hq"]["at"]), boxes["hq_basement"])
    # the cavern stays under the relic area's lowest ground with rock between
    assert boxes["hoopa_cradle"][4] <= REGIONS["regions"]["relic_area_shrine"]["ground"]["min"] - 8


def test_every_story_room_is_labelled_and_the_finale_rooms_are_not_built():
    ids = {r["id"] for r in SPEC["rooms"]}
    for need in ("hq_secure_shaft_head", "hq_director_office", "hq_anchor_control", "hq_lower_hall", "nia_clinic",
                 "aster_home", "survey_office", "signal_room"):
        assert need in ids
    reserved = {r["id"] for r in SPEC["reserved"]}
    assert {"hoopa_cradle", "cradle_passage", "hq_basement", "hq_secure_shaft"} <= reserved


def test_the_resolved_rooms_match_the_data_when_built():
    plan = ROOT / "derived" / "deep_city" / "plan.json"
    if not plan.is_file():
        pytest.skip("the city is not built here")
    p = json.loads(plan.read_text(encoding="utf-8"))
    got = {r["id"] for r in p["rooms"]}
    assert {r["id"] for r in SPEC["rooms"]} <= got
    for r in p["rooms"]:
        x0, y0, z0, x1, y1, z1 = r["box"]
        assert x0 <= x1 and y0 <= y1 and z0 <= z1, r


# ------------------------------------------------------------------ the towers

def test_every_riser_the_pit_has_lands_its_stair_on_the_back_row():
    import deep_city as DC
    for R in (15, 16, 17, 18, 19):
        steps, top, opened = DC.stair_plan(R)
        assert top[1] == 0 and len(opened) == 2
        assert sum(len(v) for v in steps.values()) == R
    with pytest.raises(DC.CityError):
        DC.stair_plan(20)
    cells = DC.ring_cells()
    assert len(set(cells)) == 16
    for a, b in zip(cells, cells[1:] + cells[:1]):
        assert abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1, "the stair jumps between %s and %s" % (a, b)


# ------------------------------------------------------------------ the re-apply

@pytest.fixture()
def steps(monkeypatch):
    import reapply
    real = reapply.indexed

    def indexed(pack, folder):
        try:
            return real(pack, folder)
        except SystemExit:
            return ["stub"]
    monkeypatch.setattr(reapply, "indexed", indexed)
    return reapply.steps()


def test_the_city_runs_after_the_deep_and_victory_road_and_before_the_habitats_and_lights(steps):
    ids = [s[0] for s in steps]
    assert "R9DC" in ids
    assert ids.index("R9B") < ids.index("R9C") < ids.index("R9DC") < ids.index("R9E") < ids.index("R16")
    acts = steps[ids.index("R9DC")][2]
    assert acts and all(k == "fn" and v.startswith("cobblers:deep_city/") for k, v in acts)
    if (FN / "index.txt").is_file():
        listed = [x for x in (FN / "index.txt").read_text(encoding="utf-8").split() if x]
        assert acts == [("fn", "cobblers:deep_city/%s" % f) for f in listed]
        assert "services" in listed and listed.index("services") > 0
        assert all(n.startswith("p1_") for n in listed[:listed.index("services")])
        assert all(n.startswith("p2_") for n in listed[listed.index("services") + 1:])


def test_the_city_pack_is_installed_and_prepared_with_its_audit():
    import reapply
    assert "cobblers_deep_city" in reapply.SERVER_PACKS and "cobblers_deep_city" not in reapply.EXCLUDED
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8").split("def prepare")[1].split("def install")[0]
    assert src.index('"vr_caves.py"') < src.index('"deep_city.py"') < src.index('"deep_city_audit.py"')

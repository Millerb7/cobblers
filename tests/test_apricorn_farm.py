"""Unit tests for tools/apricorn_farm.py (Hollin's Apricorn Farm, data/apricorn_farm.json).

These are the builder's own tests of its generator: they check the plan against the rules the generator states. They
are NOT the independent audit, which is owed and must not import tools/apricorn_farm.py to derive anything
(data/apricorn_farm.json audit_checklist).
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import apricorn_farm as AF  # noqa: E402

OFFSETS = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
FRUIT = re.compile(r"^cobblemon:(\w+)_apricorn\[age=(\d),facing=(\w+)\]$")


@pytest.fixture(scope="module")
def built():
    try:
        import ground as G
        g = G.load()
    except Exception as e:  # no canonical heightmap in this checkout
        pytest.skip("no heightmap: %s" % e)
    doc = AF.load()
    out, res = AF.files(doc, g)
    return doc, g, out, res


def test_every_fruit_hangs_on_a_leaf_it_faces(built):
    _doc, _g, _out, res = built
    blocks = res["plan"].blocks()
    n = 0
    for (x, y, z), st in blocks.items():
        m = FRUIT.match(st)
        if not m:
            continue
        n += 1
        colour, age, facing = m.groups()
        assert colour in AF.COLOURS and 0 <= int(age) <= 3
        dx, dz = OFFSETS[facing]
        assert AF.base(blocks.get((x + dx, y, z + dz), "")) == "cobblemon:apricorn_leaves", ((x, y, z), st)
    assert n == sum(res["plan"].facts["fruit"].values()) > 0


def test_every_block_is_allowed_and_the_only_spawn_conditions_are_the_fruits(built):
    doc, _g, _out, res = built
    written = {AF.base(s) for s in res["plan"].blocks().values()}
    assert written <= set(doc["blocks"]["ids"])
    spawn = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
    assert written & spawn <= set(doc["blocks"]["spawn_conditions_allowed"])
    assert not written & {"minecraft:water", "minecraft:chest"}


def test_seven_groves_of_twelve_trees_with_walkable_gates(built):
    doc, _g, _out, res = built
    groves = res["plan"].facts["groves"]
    assert sorted(groves) == sorted(AF.COLOURS)
    per = len(doc["grove_layout"]["tree_x"]) * len(doc["grove_layout"]["tree_z"])
    for c, f in groves.items():
        assert f["trees"] == per, c
        assert f["gate_outside_diff"] <= 1, c


def test_the_spawn_policy_check_bites(built, monkeypatch):
    doc, g, _out, res = built
    real = json.loads((ROOT / "data" / "spawn_block_policy.json").read_text(encoding="utf-8"))
    stripped = dict(real, whitelist=[w for w in real["whitelist"] if "apricorn_farm" not in (w.get("scope") or "")])
    orig = Path.read_text

    def fake(self, *a, **k):
        if self.name == "spawn_block_policy.json":
            return json.dumps(stripped)
        return orig(self, *a, **k)
    monkeypatch.setattr(Path, "read_text", fake)
    probs = AF.check(doc, res["plan"])
    assert any("apricorn_farm" in p for p in probs), probs


def test_functions_pass_the_server_limits_and_clear_fruit_before_leaves(built):
    import function_limits
    _doc, _g, out, _res = built
    for rel, text in out.items():
        if rel.endswith(".mcfunction"):
            assert not function_limits.check_lines(text.splitlines(), rel), rel
    clear = out["data/cobblers/function/apricorn_farm/clear.mcfunction"].splitlines()
    fruit = [i for i, l in enumerate(clear) if l.endswith("#cobblemon:apricorns")]
    leaves = [i for i, l in enumerate(clear) if l.endswith("#minecraft:leaves")]
    assert fruit and leaves and max(fruit) < min(leaves)


def test_steps_and_their_order_in_reapply(built):
    doc, g, _out, res = built
    steps = AF.placement_steps(doc, g)
    assert steps[0][0] == "cmd" and steps[0][1].startswith("forceload add")
    assert ("fn", "cobblers:apricorn_farm/build") in steps
    ent = AF.entity_steps(doc, g)
    npc = [v for k, v in ent if k == "npc"]
    assert len(npc) == 1 and npc[0][2] == "cobblers:npc_apricorn_farmer" and npc[0][3] == doc["npc"]["yaw"]
    assert ("fn", "cobblers:apricorn_farm/merchant") in ent
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert src.index('("R9AF"') < src.index('("R9E"')
    assert src.index('("R17N"') < src.index('("R18AF"')
    assert '"cobblers_apricorn_farm"' in src and '"apricorn_farm:build"' in src


def test_the_farmer_compiles_and_the_merchant_sells_jar_items_at_whole_prices(built):
    import compile_dialogue as CD
    doc, _g, out, _res = built
    files = CD.build(doc["npc"]["conversation"], ROOT / "data")
    assert "data/cobblers/npcs/npc_apricorn_farmer.json" in files
    m = out["data/cobblers/function/apricorn_farm/merchant.mcfunction"]
    for it in doc["merchant"]["stock"]:
        assert 'id:"%s"},Price:"%d"' % (it["item"], it["price"]) in m

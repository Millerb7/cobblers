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
    m = out["data/cobblers/function/apricorn_farm/merchant_act.mcfunction"]     # the chain's act (N155)
    for it in doc["merchant"]["stock"]:
        assert 'id:"%s"},Price:"%d"' % (it["item"], it["price"]) in m


# ---- N155: the stall's chunk's saved merchant arrives late (tools/chunk_look.py; staging 2026-10-08, the stall
# merchants). The world is tests/test_markets_merchant_load.py's LateWorld. The spot is synthetic (no heightmap): the
# chain's shape does not depend on where the stall stands. Written by the implementer of the fix
# (minecraft-systems-dev); an independent test-author review is still owed (CLAUDE.md principle 16).
SPOT = (2070, 80, 5571)


def _merchant_world(fns, delay, seeded=True):
    sys.path.insert(0, str(ROOT / "tests"))
    import mcfunction_sim as S
    from test_markets_merchant_load import LateWorld
    doc = AF.load()
    w = LateWorld({"cobblers:apricorn_farm/%s" % k: v for k, v in fns.items()}, delay)
    if seeded:
        w.save(S.Entity(AF.MERCHANT_KIND, (SPOT[0] + 0.5, SPOT[1], SPOT[2] + 0.5), tags=(doc["merchant"]["tag"],)))
    return w, doc


def _old_merchant(doc):
    """The pre-N155 shape, from the same summon: R18AF force-loaded, waited 3 s (60 ticks), summoned with no look, and
    the done function 100 ticks later kept the new one; the step released the chunk at 10 s."""
    import traders as TR
    tag = doc["merchant"]["tag"]
    return {"old": ["forceload add %d %d" % (SPOT[0], SPOT[2]), "schedule function cobblers:apricorn_farm/old_place 60t"],
            "old_place": [TR.summon_line(AF.MERCHANT_KIND, *SPOT, AF.merchant_data(doc)),
                          "schedule function cobblers:apricorn_farm/old_done 100t replace"],
            "old_done": ["execute if entity @e[tag=%s,tag=%s_new] run kill @e[tag=%s,tag=!%s_new]" % (tag, tag, tag, tag),
                         "tag @e[tag=%s,tag=%s_new] remove %s_new" % (tag, tag, tag)]}


def _keepers(w, doc):
    return len(w.living(AF.MERCHANT_KIND, doc["merchant"]["tag"]))


# Without it the fix has nothing to fix: the old shape doubled the stall when its merchant arrived after the dedupe.
@pytest.mark.parametrize("delay", [161, 200])
def test_the_old_stall_shape_doubles_a_merchant_that_arrives_after_its_dedupe(delay):
    doc = AF.load()
    w, _ = _merchant_world(_old_merchant(doc), delay)
    w.run("cobblers:apricorn_farm/old", 200)
    assert _keepers(w, doc) == 2


# Without it a re-run doubles the stall again; 350 is past the blind act and caught by the de-duplication.
@pytest.mark.parametrize("delay", [0, 20, 161, 200, 299, 350])
def test_the_stall_chain_leaves_one_merchant_however_late_it_arrives(delay):
    import chunk_look as CL
    doc = AF.load()
    w, _ = _merchant_world(AF.merchant_functions(doc, SPOT), delay)
    w.run(AF.merchant_fn(doc), CL.STEP_TICKS + 5)
    assert _keepers(w, doc) == 1
    assert not any(doc["merchant"]["tag"] + "_new" in e.tags for e in w.living(AF.MERCHANT_KIND, doc["merchant"]["tag"]))
    assert w.scores[("#" + AF.MERCHANT_HOLDER, CL.OBJ)] == 1
    assert not w.forced, "the chain left the stall's chunk force-loaded"


# Without it a fresh world (an export erases entities) would never get its merchant.
def test_the_stall_chain_acts_blind_on_a_first_run():
    import chunk_look as CL
    doc = AF.load()
    w, _ = _merchant_world(AF.merchant_functions(doc, SPOT), 20, seeded=False)
    w.run(AF.merchant_fn(doc), CL.STEP_TICKS + 5)
    assert _keepers(w, doc) == 1


# Without it the look could be dropped from the generator unnoticed: mutated to act in the tick it force-loads, the
# chain doubles again, and the audit's chain check (tools/chunk_look_audit.py) names it.
def test_dropping_the_look_from_the_stall_generator_doubles_and_the_audit_names_it(monkeypatch, tmp_path):
    import chunk_look as CL
    import chunk_look_audit as CA
    doc = AF.load()
    clean = AF.merchant_functions(doc, SPOT)
    orig = CL.chain

    def at_once(base, *a, **k):
        fns = orig(base, *a, **k)
        fns[base] = fns[base] + ["function %s_act" % base]
        return fns
    monkeypatch.setattr(CL, "chain", at_once)
    bad = AF.merchant_functions(doc, SPOT)
    w, _ = _merchant_world(bad, 200)
    w.run(AF.merchant_fn(doc), CL.STEP_TICKS + 5)
    assert _keepers(w, doc) == 2
    for name, fns in (("clean", clean), ("bad", bad)):
        for k, lines in fns.items():
            p = tmp_path / name / "data" / "cobblers" / "function" / "apricorn_farm" / (k + ".mcfunction")
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tag = doc["merchant"]["tag"]
    assert CA.problems(tmp_path / "clean", AF.merchant_fn(doc), tag) == []
    assert any("in the tick it force-loads" in p for p in CA.problems(tmp_path / "bad", AF.merchant_fn(doc), tag))


# Without it R18AF could hold the stall's chunk at step level and release it under the chain, or stop reading back.
def test_r18af_runs_the_chain_without_a_step_forceload_and_reads_the_count_back(built):
    import chunk_look as CL
    doc, g, _out, _res = built
    ent = AF.entity_steps(doc, g)
    assert not [v for k, v in ent if k == "cmd" and v.startswith("forceload")]
    assert ent[-3:] == [("fn", AF.merchant_fn(doc)), ("wait", CL.STEP_SECONDS),
                        ("check", ("chunk_look", AF.MERCHANT_HOLDER, 1, "Hollin's stall merchant"))]

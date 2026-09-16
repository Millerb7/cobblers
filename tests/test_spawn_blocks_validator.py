"""check_spawn_blocks in tools/validate_data.py: no placed template decides encounters by accident.

Each rule has a passing baseline and a minimal breaking change. The fixture is a synthetic repository in tmp_path:
data/{spawn_blocks,spawn_block_policy,placements}.json and a kits/structures tree of real structure templates written
by tools/structure_nbt.py. The last test runs the check on the real data/ and kits/ (read only).

Not covered: whether tools/spawn_blocks.py finds every block a loaded spawn condition names (that needs the server's
mod jars and datapacks), whether a whitelisted block really has no effect at a placement's biome, and what a template
does in game.
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import structure_nbt as S  # noqa: E402
import validate_data as V  # noqa: E402

VAROOM = "varoom [minecraft:red_concrete, neededBaseBlocks, COBBLEVERSE-DP-v31.zip]"
TRIGGERS = {
    "minecraft:red_concrete": [VAROOM, "revavroom [minecraft:red_concrete, neededBaseBlocks, COBBLEVERSE-DP-v31.zip]"],
    "minecraft:quartz_block": ["carbink [minecraft:quartz_block, neededNearbyBlocks, Cobblemon-fabric-1.8.0.jar]"],
    "minecraft:oak_leaves": ["burmy [#minecraft:leaves, neededNearbyBlocks, Cobblemon-fabric-1.8.0.jar]"],
    "cobblemon:pc": ["rotom [cobblemon:pc, neededNearbyBlocks, Cobblemon-fabric-1.8.0.jar]"],
}
SUB = {"from": "minecraft:red_concrete", "to": "moarconcrete:red_concrete_texture",
       "why": "Cobbleverse spawns varoom on vanilla concrete in every overworld biome."}
HOUSE = "kits/structures/campaign/f4/buildings/house.nbt"
OAK = "kits/structures/prefabs/trees/tree_town/oak.nbt"
SHED = "kits/structures/campaign/f4/buildings/shed.nbt"        # in the kits, named by nothing


def _template(path, blocks):
    path.parent.mkdir(parents=True, exist_ok=True)
    palette = [(b, {}) for b in blocks]
    path.write_bytes(S.dumps([len(blocks), 1, 1], palette, [(i, 0, 0, i) for i in range(len(blocks))]))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(tmp_path, blocks=None, policy=None, placements=None, templates=None, skip=()):
    d, kits = tmp_path / "data", tmp_path / "kits" / "structures"
    d.mkdir(exist_ok=True)
    shas = {}
    for rel, pal in (templates if templates is not None else {
            HOUSE: ["minecraft:stone", "moarconcrete:red_concrete_texture", "minecraft:oak_leaves"],
            OAK: ["minecraft:oak_log", "minecraft:oak_leaves"],
            SHED: ["minecraft:stone", "minecraft:oak_planks"]}).items():
        shas[rel] = _template(tmp_path / rel, pal)
    files = {
        "spawn_blocks.json": blocks if blocks is not None else {"schema": "cobblers.spawn-blocks/1", "blocks": TRIGGERS},
        "spawn_block_policy.json": policy if policy is not None else {
            "schema": "cobblers.spawn-block-policy/1", "substitutions": [dict(SUB)],
            "whitelist": [{"blocks": ["minecraft:oak_leaves"], "why": "burmy in the trees is the encounter a town's "
                                                                     "gardens should create."}],
            "applied": {"templates": [{"template": HOUSE, "sha256_after": shas[HOUSE]}]}},
        "placements.json": placements if placements is not None else {
            "schema": "cobblers.placements/1",
            "placements": [{"id": "house_a", "settlement": "t", "file": HOUSE, "template": "cobblers:f4/buildings/house"}],
            "settlements": {"t": {"plan": {"anchors": [{"id": "grove", "template": "cobblers:kits/trees/tree_town/oak"},
                                                       {"id": "empty", "template": None}]}}}},
    }
    for name, doc in files.items():
        if name not in skip:
            (d / name).write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return d, kits, shas


def run(d):
    ctx = V.Context(d, None, V.Report())
    V.check_schema(ctx)
    V.check_spawn_blocks(ctx)
    return ctx.report.findings


def of(findings, severity):
    return [f.message for f in findings if f.check == "spawn-blocks" and f.severity == severity]


# ------------------------------------------------------------------ baseline and registration

# removing this lets every breaking-change test below pass on a fixture that was already failing
def test_baseline_fixture_is_clean(tmp_path):
    d, kits, shas = build(tmp_path)
    findings = run(d)
    assert of(findings, V.ERROR) == [] and of(findings, V.WARNING) == [] and of(findings, V.SKIPPED) == []
    assert of(findings, V.INFO) == ["checked 2 placed templates and prefabs against 4 spawn-triggering blocks "
                                    "(1 whitelisted)"]


# removing this lets check_spawn_blocks fall out of the CLI's CHECKS list unnoticed
def test_cli_runs_the_spawn_blocks_check(tmp_path, capsys):
    d, kits, shas = build(tmp_path, templates={
        HOUSE: ["minecraft:quartz_block"], OAK: ["minecraft:oak_log"], SHED: ["minecraft:stone"]})
    assert "spawn-blocks" in [name for name, _ in V.CHECKS]
    V.main(["--data", str(d), "--only", "spawn-blocks", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert any(f["check"] == "spawn-blocks" and "minecraft:quartz_block" in f["message"] for f in out["findings"])


# removing this lets a donor block that decides encounters reach the real placements, prefabs or policy
def test_real_spawn_block_policy_passes():
    ctx = V.Context(ROOT / "data", None, V.Report())
    V.check_schema(ctx)
    V.check_spawn_blocks(ctx)
    bad = [f.message for f in ctx.report.findings if f.check == "spawn-blocks" and f.severity in (V.ERROR, V.SKIPPED)]
    assert bad == []


# ------------------------------------------------------------------ triggers in placed templates

# removing this lets a placed building, a planned anchor's template or a prefab carry a spawn-triggering block that
# nothing whitelisted: the donor's concrete that spawned varoom in the middle of a town
@pytest.mark.parametrize("rel,who", [(HOUSE, "placement house_a"), (OAK, "t anchor grove")])
def test_trigger_block_in_a_placed_template_is_an_error(tmp_path, rel, who):
    templates = {HOUSE: ["minecraft:stone"], OAK: ["minecraft:oak_log"], SHED: ["minecraft:stone"]}
    templates[rel] = templates[rel] + ["minecraft:quartz_block"]
    d, kits, shas = build(tmp_path, templates=templates,
                          policy={"substitutions": [], "whitelist": [], "applied": {"templates": []}})
    errs = of(run(d), V.ERROR)
    assert len(errs) == 1 and "minecraft:quartz_block" in errs[0] and who in errs[0], errs
    assert Path(rel).name in errs[0] and "carbink" in errs[0], "the message names the template and a spawn using it"


# removing this lets an unplaced prefab carry a trigger: every prefab is placed sooner or later
def test_trigger_block_in_a_prefab_is_an_error(tmp_path):
    d, kits, shas = build(tmp_path, templates={
        HOUSE: ["minecraft:stone"], OAK: ["minecraft:oak_log", "cobblemon:pc"], SHED: ["minecraft:stone"]},
        policy={"substitutions": [], "whitelist": [], "applied": {"templates": []}},
        placements={"placements": [], "settlements": {}})
    errs = of(run(d), V.ERROR)
    assert len(errs) == 1 and "cobblemon:pc" in errs[0] and "prefab" in errs[0] and "rotom" in errs[0], errs


# removing this lets a whitelisted block still fail (the Pokemon Center's machines, the leaves of a town's trees)
def test_whitelisted_trigger_blocks_pass(tmp_path):
    d, kits, shas = build(tmp_path, templates={
        HOUSE: ["cobblemon:pc", "minecraft:oak_leaves"], OAK: ["minecraft:oak_leaves"], SHED: ["minecraft:stone"]},
        policy={"substitutions": [], "applied": {"templates": []},
                "whitelist": [{"blocks": ["cobblemon:pc", "minecraft:oak_leaves"], "why": "deliberate encounters"}]})
    assert of(run(d), V.ERROR) == []


# removing this lets a template that is named but not in the kits go unchecked
def test_placement_file_must_exist(tmp_path):
    d, kits, shas = build(tmp_path, placements={"placements": [{"id": "ghost", "file": "kits/structures/gone.nbt"}],
                                                "settlements": {}})
    errs = of(run(d), V.ERROR)
    assert len(errs) == 1 and "ghost" in errs[0] and "not in the repository" in errs[0], errs


# removing this lets an anchor's template id that resolves to nothing pass silently instead of being reported as not
# checked
def test_unresolvable_anchor_template_is_skipped_with_a_reason(tmp_path):
    d, kits, shas = build(tmp_path, placements={
        "placements": [], "settlements": {"t": {"plan": {"anchors": [{"id": "a", "template": "cobblers:kits/nope/nope"}]}}}})
    findings = run(d)
    assert of(findings, V.ERROR) == []
    assert any("cobblers:kits/nope/nope" in s for s in of(findings, V.SKIPPED)), of(findings, V.SKIPPED)
    assert of(findings, V.INFO) == ["checked 1 placed templates and prefabs against 4 spawn-triggering blocks "
                                    "(1 whitelisted)"], "the prefabs are still checked"


# ------------------------------------------------------------------ substitutions and the whitelist

# removing this lets a substitution swap one spawn trigger for another, leave the original in the kits, or record a
# hash that is no longer the file's (the substitution never applied, or the template edited since)
@pytest.mark.parametrize("change,needle", [
    (lambda p, t, s: p["substitutions"][0].update(to="minecraft:quartz_block"),
     "replaces a spawn-triggering block with another one"),
    (lambda p, t, s: t.__setitem__(SHED, ["minecraft:red_concrete"]), "is not applied: shed.nbt still contains"),
    (lambda p, t, s: p["applied"]["templates"][0].update(sha256_after="0" * 64), "not the recorded sha256_after"),
    (lambda p, t, s: p["applied"]["templates"][0].update(template="kits/structures/gone.nbt"),
     "is not in the repository"),
    (lambda p, t, s: p["substitutions"][0].pop("to"), "needs from and to block names"),
])
def test_substitution_breaks_are_errors(tmp_path, change, needle):
    policy = {"schema": "cobblers.spawn-block-policy/1", "substitutions": [dict(SUB)],
              "whitelist": [{"blocks": ["minecraft:oak_leaves"], "why": "deliberate"}],
              "applied": {"templates": [{"template": HOUSE, "sha256_after": None}]}}
    templates = {HOUSE: ["minecraft:stone", "moarconcrete:red_concrete_texture", "minecraft:oak_leaves"],
                 OAK: ["minecraft:oak_log", "minecraft:oak_leaves"], SHED: ["minecraft:stone"]}
    change(policy, templates, None)
    d, kits, shas = build(tmp_path, policy=policy, templates=templates)
    if policy["applied"]["templates"] and policy["applied"]["templates"][0].get("sha256_after") is None:
        policy["applied"]["templates"][0]["sha256_after"] = shas[HOUSE]
        (d / "spawn_block_policy.json").write_text(json.dumps(policy, indent=1), encoding="utf-8")
    errs = of(run(d), V.ERROR)
    assert any(needle in e for e in errs), errs


# removing this lets a template be edited after its substitution without the policy noticing
def test_edited_template_fails_its_recorded_hash(tmp_path):
    d, kits, shas = build(tmp_path)
    _template(tmp_path / HOUSE, ["minecraft:stone", "moarconcrete:red_concrete_texture"])
    errs = of(run(d), V.ERROR)
    assert len(errs) == 1 and "not the recorded sha256_after" in errs[0] and HOUSE in errs[0], errs


# removing this lets a block be whitelisted with no reason, or an entry with no blocks at all, so a trigger is allowed
# by an empty rule
@pytest.mark.parametrize("entry,needle", [
    ({"blocks": ["minecraft:oak_leaves"]}, "needs a why"),
    ({"blocks": ["minecraft:oak_leaves"], "why": "  "}, "needs a why"),
    ({"why": "no blocks"}, "needs a non-empty blocks list"),
    ({"blocks": [], "why": "empty"}, "needs a non-empty blocks list"),
])
def test_whitelist_entry_breaks_are_errors(tmp_path, entry, needle):
    d, kits, shas = build(tmp_path, policy={"substitutions": [], "whitelist": [entry],
                                            "applied": {"templates": []}})
    errs = of(run(d), V.ERROR)
    assert any(needle in e for e in errs), errs
    assert any("minecraft:oak_leaves" in e and "decides encounters" in e for e in errs), \
        "a block the broken entry claimed to allow is no longer allowed"


# ------------------------------------------------------------------ absent and malformed inputs

# removing this lets a missing or stale spawn-block list count as a pass: nothing would be checked and nobody told
@pytest.mark.parametrize("blocks,needle", [
    (None, "data/spawn_blocks.json is absent"),
    ({"schema": "cobblers.spawn-blocks/1", "blocks": {}}, "lists no blocks"),
    ({"schema": "cobblers.spawn-blocks/1"}, "lists no blocks"),
])
def test_absent_or_empty_spawn_blocks_is_skipped(tmp_path, blocks, needle):
    d, kits, shas = build(tmp_path, blocks=blocks, skip=("spawn_blocks.json",) if blocks is None else ())
    findings = run(d)
    assert of(findings, V.ERROR) == []
    assert len(of(findings, V.SKIPPED)) == 1 and needle in of(findings, V.SKIPPED)[0]


# removing this lets a repository with spawn triggers recorded but no policy pass unchecked
def test_absent_policy_is_an_error(tmp_path):
    d, kits, shas = build(tmp_path, skip=("spawn_block_policy.json",))
    errs = of(run(d), V.ERROR)
    assert len(errs) == 1 and "spawn_block_policy.json is absent" in errs[0], errs


# removing this lets a corrupt policy or spawn-block list be skipped (fail open) instead of failing
@pytest.mark.parametrize("name", ["spawn_blocks.json", "spawn_block_policy.json"])
def test_malformed_json_is_an_error(tmp_path, name):
    d, kits, shas = build(tmp_path)
    (d / name).write_text("{nope", encoding="utf-8")
    assert any("invalid JSON" in m for m in of(run(d), V.ERROR))


# removing this lets a template that cannot be read be passed over as if it held no triggers
def test_unreadable_template_is_an_error(tmp_path):
    d, kits, shas = build(tmp_path)
    (tmp_path / HOUSE).write_bytes(b"not nbt at all")
    errs = of(run(d), V.ERROR)
    assert any("cannot read template house.nbt" in e for e in errs), errs

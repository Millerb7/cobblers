"""Hummock Mere (data/hummock_mere.json, tools/hummock_mere.py, tools/hummock_mere_audit.py): the swamp monster's nest.

The nest is a drowned grove in the Marshy Marsh's shallows round a mud island with a Clodsire on it (L52, scale
modifier 2.2), and a warning sign on Route 6. These tests hold:

  - the record's numbers against the data they come from (the gym ace levels, the tier cap, the habitat blocks, the
    route paths), never against the builder;
  - the built pack against the independent audit (tools/hummock_mere_audit.py), and the audit against the GENERATOR:
    each mutation changes the builder's code and leaves the authored data alone, so a passing audit on a broken
    generator is a failing test (CLAUDE.md "How to prove an audit is independent");
  - the registration (tools/reapply.py steps, pack lists), the probes and the C4 contract's accounting.

Everything that needs the canonical heightmap skips with the reason when it is absent (terrain.env_source_root).
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import hummock_mere as HM  # noqa: E402
import hummock_mere_audit as AU  # noqa: E402

DATA = json.loads((ROOT / "data" / "hummock_mere.json").read_text(encoding="utf-8"))
R = DATA["residents"][0]
PK = R["pokemon"]


def _data(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ground():
    try:
        import ground as G
        return G.load()
    except (FileNotFoundError, OSError, SystemExit) as e:
        pytest.skip("NOT_EXECUTED: the canonical heightmap is not available: %s" % str(e)[:160])


@pytest.fixture(scope="module")
def built(ground, tmp_path_factory):
    out, parts = HM.files(HM.load(), ground)
    d = tmp_path_factory.mktemp("pack")
    for rel, text in out.items():
        f = d / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    return d, out


# ------------------------------------------------------------------ the record, against the data it comes from


def test_the_record_is_one_place_with_one_ungated_named_pokemon():
    assert DATA["schema"] == HM.SCHEMA and len(DATA["residents"]) == 1
    assert PK["species"] == "cobblemon:clodsire" and PK["appears_after"] is None
    assert 0 < PK["trigger"] < PK["leash"]


def test_the_level_is_well_over_the_places_cap_and_the_gate_is_the_first_gym_that_holds_it():
    design = _data("encounter_design.json")
    tier = design["tables"][R["subregion"]]["tier"]
    cap = design["rules"]["tiers"][str(tier)]["cap"]
    assert PK["level"] >= cap + DATA["rules"]["level_over_cap_min"] >= cap + 10      # the owner: "well above the local cap"
    aces = _data("trainers.json")["generation_contract"]["gym_ace_levels"]
    first = next(i for i, v in enumerate(aces) if v >= PK["level"])
    assert PK["gate"] == "gym%d_cleared" % first
    # one badge earlier a player still cannot catch it, which is what makes the gate a gate
    assert aces[first - 1] < PK["level"]


def test_it_is_over_its_places_ceiling_by_decision_and_the_record_says_so():
    # tests/test_resident_siting.py holds a resident to the place's ceiling (next_cap) unless the owner decided otherwise
    # (Split-Bark). This one is over it on purpose; the record must say the decision is the owner's brief
    design = _data("encounter_design.json")
    tier = design["tables"][R["subregion"]]["tier"]
    ceiling = design["rules"]["hearts"]["next_cap"][str(tier)]
    assert PK["level"] > ceiling
    assert "ceiling" in DATA["rules"]["level_over_cap_why"].lower() and "owner" in DATA["request"]


def test_the_species_exists_in_the_cobblemon_1_8_0_jar_with_a_model():
    import zipfile
    jar = Path("C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/Cobblemon-fabric-1.8.0+1.21.1.jar")
    if not jar.exists():
        pytest.skip("NOT_EXECUTED: the server snapshot's Cobblemon jar is not on this machine")
    z = zipfile.ZipFile(jar)
    names = set(z.namelist())
    sp = PK["species"].split(":")[1]
    assert any(n.endswith("/species/generation9/%s.json" % sp) for n in names)
    assert any("pokemon/models/" in n and sp in n and n.endswith(".geo.json") for n in names)
    assert any(b"scale_modifier" in z.read(n) for n in names if n.endswith("api/pokemon/PokemonProperties.class"))


def test_the_nest_is_clear_of_every_route_path_and_every_activated_habitat_block_and_town():
    paths = _data("route_paths.json")["paths"]
    cx, cz = R["site"]["centre"]
    ax, az = cx + PK["at"][0], cz + PK["at"][1]
    d = min(math.hypot(x - ax, z - az) for pl in paths.values() for x, z in pl)
    assert d >= DATA["rules"]["path_clearance"] >= _data("encounter_design.json")["rules"]["hearts"]["clear_of_path_blocks"], d
    for b in _data("habitat_blocks.json")["blocks"]:
        if b.get("style") == "activated":
            assert math.hypot(b["position"]["x"] - ax, b["position"]["z"] - az) >= b["activated"]["spawn_range"] + PK["leash"], b["id"]
    for t in _data("towns.json")["towns"]:
        f = t.get("footprint") or {}
        if f.get("min_x") is not None:
            dd = math.hypot(max(f["min_x"] - ax, ax - f["max_x"], 0), max(f["min_z"] - az, az - f["max_z"], 0))
            assert dd >= 200, (t["id"], dd)


def test_no_block_the_record_may_place_is_a_spawn_condition_or_concrete_or_water():
    spawn = set(_data("spawn_blocks.json")["blocks"])
    ids = set(DATA["blocks"]["ids"])
    assert ids and not (ids & spawn), sorted(ids & spawn)
    assert not [b for b in ids if "concrete" in b or "water" in b or "lava" in b]


def test_the_probe_block_names_a_place_in_the_probe_file_and_each_probe_is_well_formed():
    pr = _data("world_probes.json")["places"]["hummock_mere"]
    assert len(pr) >= 8
    for p in pr:
        assert p["what"]
        assert ("block" in p and len(p["block"]) == 4 and "expect" in p) or ("entity" in p and p["count"] == 1 and len(p["hold"]) == 3)
    assert any("entity" in p for p in pr) and any("block" in p for p in pr)


# ------------------------------------------------------------------ the registration


def test_the_steps_are_registered_in_order_and_the_pack_is_listed_in_both_places():
    text = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert text.index('"R9FS"') < text.index('"R9HM"') < text.index('("R9E"')
    assert text.index('"R18FS"') < text.index('"R18HM"')
    assert text.count('"cobblers_hummock_mere"') == 2          # SERVER_PACKS and WORLD_LOCAL, once each
    assert 'add("hummock_mere", "hummock_mere.py"' in text and 'add("hummock_mere_audit", "hummock_mere_audit.py"' in text
    assert text.index('add("hummock_mere", ') < text.index('add("hummock_mere_audit", ')
    assert text.index('"cobblers_hummock_mere"') < text.index("EXCLUDED = {")


def test_the_pack_is_not_excluded_and_every_function_is_run_by_a_step_or_called(built):
    d, out = built
    text = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert not re.search(r'EXCLUDED = \{[^}]*cobblers_hummock_mere', text, re.S)
    fns = {rel.split("/function/")[1][:-len(".mcfunction")] for rel in out if rel.endswith(".mcfunction")}
    referenced = " ".join(l for t in out.values() for l in t.splitlines() if not l.startswith("#"))
    stepped = " ".join(str(s[1]) for s in HM.placement_steps() + HM.entity_steps())
    for fn in fns:
        short = "cobblers:" + fn
        assert short in referenced or short in stepped or fn in ("hummock_mere/load", "hummock_mere/keeper") or fn.endswith("/build"), fn
    for fn in (f for f in fns if f.endswith("/build")):
        assert "cobblers:" + fn in stepped, fn
    for fn in ("hummock_mere/load",):
        load = json.loads(out["data/minecraft/tags/function/load.json"])["values"]
        assert "cobblers:" + fn in load


def test_the_entity_step_summons_one_guarded_pokemon_with_its_size():
    steps = HM.entity_steps()
    cmds = [s[1] for s in steps if s[0] == "cmd" and "spawnpokemonat" in s[1]]
    assert len(cmds) == 1
    c = cmds[0]
    assert "unless entity @e[type=cobblemon:pokemon,tag=cobblers.res.the_hummock]" in c
    assert 'Species:"cobblemon:clodsire"' in c
    assert c.endswith("level=%d scale_modifier=%s" % (PK["level"], PK["scale_modifier"]))
    assert steps[0][0] == "cmd" and steps[0][1].startswith("forceload add ") and steps[-1][1].startswith("forceload remove ")


def test_the_placement_step_holds_each_box_around_its_build_and_releases_it():
    steps = HM.placement_steps()
    fns = [s[1] for s in steps if s[0] == "fn"]
    assert fns == ["cobblers:hummock_mere/hummock_mere/build", "cobblers:hummock_mere/hummock_waysign/build"]
    kinds = [s[0] for s in steps]
    assert kinds == ["cmd", "wait", "fn", "cmd"] * 2


def test_the_contract_c4_accounts_for_both_tools():
    c4 = next(c for c in _data("system_contracts.json")["contracts"] if c["id"] == "C4")
    for t in ("hummock_mere.py", "hummock_mere_audit.py"):
        assert c4["tools"][t].startswith("checker:")


# ------------------------------------------------------------------ the pack, against the independent audit


def test_the_audit_passes_on_the_built_pack(built, ground):
    d, _out = built
    probs, notes = AU.audit(d)
    assert not probs, probs[:5]
    assert any(n.startswith("build:") for n in notes)


def test_the_pack_writes_no_spawn_condition_block_and_no_water(built):
    d, out = built
    spawn = set(_data("spawn_blocks.json")["blocks"])
    placed = set()
    for rel, text in out.items():
        if rel.endswith(".mcfunction"):
            blocks, clears, odd = AU.replay(text.splitlines())
            placed |= {AU.bid(v) for v in blocks.values()}
    assert placed and not (placed & spawn), sorted(placed & spawn)
    assert not [b for b in placed if "water" in b or "lava" in b or "concrete" in b]


def test_the_build_stays_under_the_function_limits_and_every_clear_is_above_the_lake(built):
    d, out = built
    build = out["data/cobblers/function/hummock_mere/hummock_mere/build.mcfunction"].splitlines()
    for ln in build:
        m = re.match(r"fill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) minecraft:air replace", ln)
        if m:
            assert int(m[2]) >= R["site"]["water_level"] + 1
            vol = (abs(int(m[1]) - int(m[4])) + 1) * (abs(int(m[2]) - int(m[5])) + 1) * (abs(int(m[3]) - int(m[6])) + 1)
            assert vol <= 32768


def test_the_roadside_sign_is_on_the_routes_left_four_out_and_dry(built, ground):
    d, out = built
    fn = out["data/cobblers/function/hummock_mere/hummock_waysign/build.mcfunction"]
    m = re.search(r"setblock (-?\d+) (-?\d+) (-?\d+) minecraft:mangrove_sign", fn)
    x, y, z = int(m[1]), int(m[2]), int(m[3])
    assert y == ground(x, z) + 1
    path = _data("route_paths.json")["paths"][DATA["waysign"]["route"]]
    near = min(path, key=lambda p: math.hypot(p[0] - x, p[1] - z))
    assert abs(math.hypot(near[0] - x, near[1] - z) - DATA["waysign"]["offset"]) <= 1.5


# ------------------------------------------------------------------ the audit against the GENERATOR (mutations)
# Each patches the builder's code and leaves data/hummock_mere.json alone. A record-side edit moves the expectation and
# the output together and proves nothing.


def _build_with(monkeypatch, ground, tmp_path, **patches):
    for name, fn in patches.items():
        monkeypatch.setattr(HM, name, fn)
    out, _parts = HM.files(HM.load(), ground, check=False)
    for rel, text in out.items():
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    return AU.audit(tmp_path)[0]


def test_audit_catches_a_generator_that_raises_the_island(monkeypatch, ground, tmp_path):
    real = HM.mound_top
    probs = _build_with(monkeypatch, ground, tmp_path, mound_top=lambda d, prof, L: (None if real(d, prof, L) is None else real(d, prof, L) + 2))
    assert any(p.startswith("island") or p.startswith("anchor") for p in probs), probs[:4]


def test_audit_catches_a_generator_that_waterlogs_roots_on_dry_land(monkeypatch, ground, tmp_path):
    probs = _build_with(monkeypatch, ground, tmp_path, root=lambda s, x, y, z, L: "minecraft:mangrove_roots[waterlogged=true]")
    assert any("waterlogged" in p for p in probs), probs[:4]


def test_audit_catches_a_generator_that_clears_into_the_lake(monkeypatch, ground, tmp_path):
    real = HM.lake_level
    probs = _build_with(monkeypatch, ground, tmp_path, lake_level=lambda s: real(s) - 3)
    assert any(p.startswith("flood") for p in probs), probs[:4]


def test_audit_catches_a_generator_that_cuts_the_trunks_short(monkeypatch, ground, tmp_path):
    real_doc = HM.load

    def short(path=HM.DATA):
        d = real_doc(path)
        for p in d["residents"][0]["pieces"]:
            if p["kind"] == "mangrove":
                p["height"] = 4          # the builder's input is mutated in memory only, never data/hummock_mere.json
        return d
    for name, fn in {"load": short}.items():
        monkeypatch.setattr(HM, name, fn)
    out, _parts = HM.files(HM.load(), ground, check=False)
    for rel, text in out.items():
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    probs = AU.audit(tmp_path)[0]
    assert any(p.startswith("tree") for p in probs), probs[:4]


def test_audit_catches_a_pack_whose_resident_lost_its_size(ground, tmp_path, built):
    d, out = built
    for rel, text in out.items():
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text.replace(" scale_modifier=%s" % PK["scale_modifier"], ""), encoding="utf-8", newline="\n")
    probs = AU.audit(tmp_path)[0]
    assert any("scale_modifier" in p for p in probs), probs[:4]

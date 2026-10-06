"""tools/legendary_sweep_audit.py: the independent audit of the 2026-10-06 legendaries sweep and the catchable Hoopa.

Written by an agent that built neither the sweep nor the Hoopa pack (their builder's tests are
tests/test_legendary_sweep.py and tests/test_hoopa_cradle.py).

HOW INDEPENDENCE IS PROVED. CLAUDE.md "How to prove an audit is independent": mutate the GENERATOR, not the record. Every
mutation below edits the SOURCE of a generator (tools/hoopa_cradle.py, tools/rewards_pack.py, tools/place_donor.py) in
memory, executes the edited source as a fresh module, and hands that module to the audit, with every file in data/
untouched. The audit's expectations come from data/relic_underground.json, data/hoopa_cradle.json's decision, the
heightmap, the template NBT and the LumyMon class files, none of which a generator edit can move, so each mutation
must turn the audit red. A few further cases perturb a COPY of data/placements.json or of a template, which is the
artifact itself (the paste position, the template's containers): the expectation there is the heightmap and the
item read from the altar's class, which such a copy cannot move either. Nothing on disk is written.

WHAT THIS DOES NOT COVER. The Hoopa scenarios run the generated commands in the audit's own model of vanilla 1.21.1 and
Cobblemon 1.8.0 semantics, not in a server; the altar, the shrine, the advancement and the callbacks are not run.
Those are data/hoopa_cradle.json runtime_checks and the staging checks in docs/world-building/LEGENDARY_SWEEP.md 9.
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import legendary_sweep_audit as A  # noqa: E402

SNAP = A.SNAPSHOT
HAVE_SNAPSHOT = (SNAP / "mods").is_dir() and any((SNAP / "mods").glob("LumyMon-*.jar"))
needs_snapshot = pytest.mark.skipif(not HAVE_SNAPSHOT, reason="NOT RUN: no offline server snapshot at %s" % SNAP)


def mutated(name, old, new):
    """tools/<name>.py with `old` replaced by `new` exactly once, executed as a fresh module (the file is untouched)."""
    path = ROOT / "tools" / ("%s.py" % name)
    src = path.read_text(encoding="utf-8")
    assert src.count(old) == 1, "the mutation's anchor %r is in %s %d times: the generator changed, update the test" \
        % (old, path.name, src.count(old))
    mod = types.ModuleType("%s_mutant" % name)
    mod.__file__ = str(path)
    exec(compile(src.replace(old, new), str(path), "exec"), mod.__dict__)
    return mod


def problems(R, area=None):
    return [m for a, m in R.problems if area is None or a == area]


# ------------------------------------------------------------------------------------------------ the Hoopa


def hoopa_report(mod=None):
    R = A.Report()
    A.hoopa_audit(R, mod)
    return R


def test_the_hoopa_pack_as_generated_passes_every_scenario():
    # Without it the scenarios could be wrong in a way that fails the real pack; the mutations below would then
    # prove nothing, because a red audit would be red for every input.
    R = hoopa_report()
    assert problems(R) == []
    assert R.facts["hoopa.came_back_after"] >= R.facts["hoopa.respawn_after_ticks"]


HOOPA_MUTATIONS = {
    # the keeper forgets the caught check: a player who caught theirs gets another, for ever
    "no_caught_check": ('eligible = "advancements={%s=true,%s=false}" % (doc["gate_flag"], doc["caught_advancement"])',
                        'eligible = "advancements={%s=true}" % (doc["gate_flag"],)',
                        "caught theirs got another"),
    # the keeper forgets the flag: Hoopa for a player who never released it
    "no_flag_check": ('eligible = "advancements={%s=true,%s=false}" % (doc["gate_flag"], doc["caught_advancement"])',
                      'eligible = "advancements={%s=false}" % (doc["caught_advancement"],)',
                      "without cobblers:flag/rift_crisis_resolved got"),
    # the spawn one block east of the cradle's centre
    "spawn_moved_one_block": ('doc["spot"][0] + 0.5, doc["spot"][1], doc["spot"][2] + 0.5, sp',
                              'doc["spot"][0] + 1.5, doc["spot"][1], doc["spot"][2] + 0.5, sp',
                              "not the cradle's centre"),
    # the respawn half as long as decided
    "respawn_shortened": ('% (W, k["respawn_after_ticks"] - 1)', '% (W, k["respawn_after_ticks"] - 601)',
                          "came back after"),
    # the ball check never refuses
    "ball_check_opened": ('"execute if score #ok %s matches 0 run tag @s add %s" % (W, t["refuse"])',
                          '"execute if score #ok %s matches 7 run tag @s add %s" % (W, t["refuse"])',
                          "can catch"),
    # the keeper no longer sees the player's Hoopa as present: a second one once the respawn clock runs out.
    # (Dropping the `#have ... return 0` line instead is an EQUIVALENT mutant: the clock it would reach is reset on the
    # same pass, so behaviour does not change. Measured while writing this test, and left out for that reason.)
    "no_one_per_player": ('run scoreboard players set #have %s 1"', 'run scoreboard players set #have %s 0"',
                          "Hoopas, not 1"),
    # a level over the cap at the cradle
    "level_over_cap": ('sp, int(doc["level"])),', 'sp, int(doc["level"]) + 1),', "not 60"),
    # the catch never recorded
    "catch_not_recorded": ('"advancement grant @s only %s" % doc["caught_advancement"],', '"# (no grant)",',
                           "did not grant"),
    # a command the audit's model does not know must fail closed, never pass
    "unmodelled_command": ('"scoreboard players set #have %s 0" % W,',
                           '"scoreboard players set #have %s 0" % W, "effect give @s minecraft:glowing 1",',
                           "does not model"),
}


@pytest.mark.parametrize("key", sorted(HOOPA_MUTATIONS))
def test_a_mutated_hoopa_generator_is_caught(key):
    # Without it the Hoopa scenarios could pass whatever the generator emits (a model that shares the generator's
    # reading, or a scenario that never reaches the line): each named fault must be named back.
    old, new, want = HOOPA_MUTATIONS[key]
    R = hoopa_report(mutated("hoopa_cradle", old, new))
    found = problems(R)
    assert any(want in p for p in found), "%s not caught; problems: %s" % (key, found)


def test_the_release_is_the_flags_only_source():
    # Without it a second grant of rift_crisis_resolved (another transition, another node) would hand out Hoopa to a
    # player who never beat Brann and Elara, and the keeper, which keys on the flag alone, would never know.
    R = hoopa_report()
    assert [g[0] for g in R.facts["hoopa.flag_granted_by"]] == ["unlock_league_after_rift_resolution"]
    assert R.facts["hoopa.release_run_by"] == ["release_001"]


def test_level_60_is_inside_the_cap_a_player_has_at_the_cradle():
    # Without it Hoopa's 60 could sit over the cap of a player who reached the cradle early, and the level-cap
    # callback would break every ball: uncatchable. The cap is rctmod's with Lorelei next, read from her team.
    R = hoopa_report()
    assert R.facts["hoopa.cap_after_gym8"] == 60
    assert all("cobblers:flag/gym8_cleared" in t for t in R.facts["hoopa.cradle_pass_thresholds"])


# ------------------------------------------------------------------------------------------------ the pastes and caches


@pytest.fixture(scope="module")
def ground():
    import ground as G
    try:
        return G.load()
    except (FileNotFoundError, OSError) as e:
        pytest.skip("NOT RUN: no canonical heightmap (%s)" % e)


@pytest.fixture(scope="module")
def packs():
    if not HAVE_SNAPSHOT:
        pytest.skip("NOT RUN: no offline server snapshot at %s" % SNAP)
    return A.Packs(SNAP)


@pytest.fixture(scope="module")
def pasted(packs, ground):
    R = A.Report()
    sites = A.paste_audit(R, packs, ground, sightlines=False)
    return R, sites


@needs_snapshot
@pytest.mark.slow
def test_the_whole_audit_passes_on_the_repository_as_it_stands(ground):
    # Without it a regression in the data (a moved paste, a new source of the Red Chain, a cache lost its gate) would
    # only show in a prepare run. The one KNOWN finding (the sealed dome) is reported, not failed.
    R = A.audit(SNAP, ground)
    assert problems(R) == []
    assert set(R.known) == set(A.KNOWN)


@needs_snapshot
@pytest.mark.slow
def test_each_paste_reads_its_item_from_the_altars_own_class(pasted):
    # Without it the audit would be checking the item the record names, which is the builder's claim: the class says
    # which item the summon block wants, and what it hands back.
    R, sites = pasted
    assert {s: v["item"] for s, v in sites.items()} == {"legendary_giratina_shrine": "lumymon:red_chain",
                                                        "legendary_newmoon_island": "lumymon:nightmare_weaver"}
    assert R.facts["legendary_giratina_shrine.reward_item"] == ["lumymon:broken_red_chain"]


@needs_snapshot
@pytest.mark.slow
def test_the_sunk_seat_is_the_heightmaps_cheapest(pasted):
    # Without it the slab could be seated a block high or low and stand proud of the trough, or bury the altar.
    R, _ = pasted
    seat = R.facts["legendary_giratina_shrine.seat"]
    assert seat["slab_top_y"] == seat["cheapest_seat"] == 77
    assert not problems(R)


@needs_snapshot
@pytest.mark.slow
def test_newmoon_island_floats_over_dry_land_with_nothing_of_ours_under_it(pasted):
    # Without it the island could be hung into the isle's ground or over one of our builds.
    R, _ = pasted
    seat = R.facts["legendary_newmoon_island.seat"]
    assert seat["kind"] == "floating" and seat["gap_over_highest_ground"] > 0
    assert R.facts["legendary_newmoon_island.placements_under"] == []


@needs_snapshot
@pytest.mark.slow
@pytest.mark.parametrize("record,changes,want", [
    # the island lowered into the isle: its bottom below the highest ground
    ("legendary_newmoon_island", {"y": 100}, "is not above the highest ground"),
    # the shrine one block high: the slab no longer at the cheapest seat
    ("legendary_giratina_shrine", {"y": 67}, "cheapest seat"),
    # the shrine's corner put 40 east of route_06_koga_to_sabrina's vertex (4718, 2518)
    ("legendary_giratina_shrine", {"x": 4758, "z": 2500}, "a route path"),
])
def test_a_moved_paste_is_caught(packs, ground, record, changes, want):
    # Without it the measurements could agree with the record by sharing it: the expectation is the heightmap and
    # the authored world around the site, which a moved copy of the placement cannot move.
    pl = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["placements"]
    q = next(p for p in pl if p["id"] == record)
    q["position"].update(changes)
    R = A.Report()
    A.paste_audit(R, packs, ground, pl, sightlines=False)
    assert any(want in p for p in problems(R)), problems(R)


@needs_snapshot
@pytest.mark.slow
def test_a_template_container_holding_the_activation_item_is_caught(packs, ground, monkeypatch):
    # Without it a donor template whose barrel holds the summoning item hands out a free legendary: exactly what the
    # bird towers' base barrels did on 2026-10-05. The item is put into a COPY of Newmoon Island's oak barrel.
    real = packs.template

    def spiked(tid):
        src, t = real(tid)
        if tid != "lumymon:newmoon_island":
            return src, t
        t = dict(t)
        t["blocks"] = list(t["blocks"])
        for i, b in enumerate(t["blocks"]):
            if (b.get("nbt") or {}).get("Items") and b["pos"] == [37, 38, 31]:
                nb = dict(b["nbt"])
                nb["Items"] = list(nb["Items"]) + [{"Slot": 20, "id": "lumymon:nightmare_weaver", "count": 1}]
                t["blocks"][i] = dict(b, nbt=nb)
        return src, t
    monkeypatch.setattr(packs, "template", spiked)
    R = A.Report()
    A.paste_audit(R, packs, ground, sightlines=False)
    assert any("holds lumymon:nightmare_weaver: a free legendary" in p for p in problems(R)), problems(R)


@needs_snapshot
@pytest.mark.slow
@pytest.mark.parametrize("old,new,want", [
    # the paste one block up from the sited seat
    ('1.0 0" % (rec["pack_template"], x, y, z,', '1.0 0" % (rec["pack_template"], x, y + 1, z,',
     "the paste command is"),
    # every jigsaw to air: the deepslate under the slab is lost
    ('final = (b.get("nbt") or {}).get("final_state") or "minecraft:air"', 'final = "minecraft:air"',
     "is not set to its own final state"),
])
def test_a_mutated_paste_generator_is_caught(packs, ground, old, new, want):
    # Without it tools/place_donor.py could paste somewhere other than the measured seat, or leave jigsaws standing.
    R = A.Report()
    A.paste_audit(R, packs, ground, donor=mutated("place_donor", old, new), sightlines=False)
    assert any(want in p for p in problems(R)), problems(R)


@needs_snapshot
@pytest.mark.slow
def test_the_caches_as_generated_give_one_item_to_a_champion_once(pasted):
    # Without it the audit's cache reading could fail the real pack, and the mutations below would prove nothing.
    R0, sites = pasted
    R = A.Report()
    A.cache_audit(R, sites)
    assert problems(R) == []
    assert R.known.keys() == {"giratina_dome_sealed"}


@needs_snapshot
@pytest.mark.slow
@pytest.mark.parametrize("old,new,want", [
    # the brief's own: the predicate loses type_specific, so anyone standing at the altar takes the item
    ('if r.get("requires_flags"):', 'if False:', "does not require cobblers:flag/champion_cleared"),
    # two of the item instead of one
    ('c.get("components", ""), c["count"]))', 'c.get("components", ""), c["count"] + 1))', "not one"),
    # the trigger box in the Nether
    ('pred = {"location": {"position": pos, "dimension": "minecraft:overworld"}}',
     'pred = {"location": {"position": pos, "dimension": "minecraft:the_nether"}}', "not an overworld box"),
])
def test_a_mutated_rewards_generator_is_caught(pasted, old, new, want):
    # Without it a cache that hands the activation item to a player under the Champion's cap (who then wastes it on a
    # legendary they cannot hold), or hands out two, would pass.
    _, sites = pasted
    R = A.Report()
    A.cache_audit(R, sites, rewards=mutated("rewards_pack", old, new))
    assert any(want in p for p in problems(R)), problems(R)


@needs_snapshot
@pytest.mark.slow
def test_no_loaded_pack_hands_out_either_activation_item(packs, pasted):
    # Without it a recipe, a loot table or a trainer drop in a loaded pack would be a second source, and the
    # Champion gate on the cache would gate nothing.
    _, sites = pasted
    R = A.Report()
    A.source_audit(R, packs, sites)
    assert problems(R) == []
    assert R.facts["legendary_giratina_shrine.sources_in_disabled_extra"]   # the scan does look: the Sinnoh recipe


@needs_snapshot
@pytest.mark.slow
def test_every_level_an_altar_can_roll_needs_the_champions_cap(pasted):
    # Without it a legendary that rolls under the Elite Four's cap would be gated behind the Champion for nothing,
    # and one that rolls over 100 could not be held by anyone.
    _, sites = pasted
    for s in sites.values():
        assert s["levels"] and min(s["levels"]) > 62 and max(s["levels"]) <= A.CHAMPION_CAP

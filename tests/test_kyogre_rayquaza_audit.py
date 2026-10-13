"""The independent audit of Kyogre's cave (R18KC) and Rayquaza's sky (R14R): tools/kyogre_rayquaza_audit.py.

Every property is checked on the packs the real generators build from the real data (into a temporary folder, never
build/). The audit is then proved to bite by MUTATING THE GENERATORS, not the records (CLAUDE.md "How to prove an audit is
independent"): each mutant edits one piece of tools/kyogre_cave.py or tools/rayquaza_sky.py source, leaves data/ untouched,
and must turn a property that holds on the real build into a failure. Kyogre's mutants are built past the builder's own
guards (its plan() refuses some of them itself), so it is the audit that has to catch them.

Four properties fail on the real build today; they are strict xfails naming the defect, so the day the content is fixed
the xfail turns into a failure and this file must be updated.

What this does NOT cover: anything at runtime. Whether the cage, the drain, the spawns, the callback, Slow Falling or the
sneak-only step behave in a running server is a staging test (KYOGRE_CAVE.md section 7 "In-game test list"), not pytest.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import kyogre_rayquaza_audit as A  # noqa: E402

KYOGRE_SRC = ROOT / "tools" / "kyogre_cave.py"
RAY_SRC = ROOT / "tools" / "rayquaza_sky.py"

# Each property, with what breaks if it is removed.
PROPERTIES = {
    # a carved cell next to the void lets a player (or the water) out into the pocket's void
    "kyogre.seal": None,
    # a source beside air flows: the drained hall refills, or a passage floods that the model calls dry
    "kyogre.water_still": None,
    # the Race's stream would spill onto the hub's floor
    "kyogre.race_contained": None,
    # without an ungated way out a player could be shut in by a condition they cannot meet
    "kyogre.ways_out_ungated": None,
    # the Trench or the Basin reachable before the lamps and the wheel: the puzzles are skippable
    "kyogre.sealed_until_solved": None,
    # the solved cave would not lead to the shrine, the catcher's pedestal or the Basin's way out
    "kyogre.basin_reachable_when_solved": None,
    # REVIEW 87: a place in some state from which no way-out click can be reached is a softlock
    "kyogre.always_a_way_out": None,
    # a reachable cell outside the keeper's sweep is never ejected or counted; one in the rescue box is teleported forever
    "kyogre.sweeps_cover_the_cave": None,
    # a blocking block or water written over a standing player with no no-player guard traps them
    "kyogre.no_write_over_a_player": None,
    # the cage's close writing barrier into the causeway or the lip while it stands closed
    "kyogre.cage_closes_only_on_its_own_cells": None,
    # KYOGRE_CAVE.md 3: the barrier must never enclose a cell a player can occupy (a logged-out player is filled in)
    "kyogre.cage_never_encloses_a_walkable_cell": "DEFECT: the cage (data/kyogre_cave.json kyogre.cage) is the whole "
        "11 x 4 x 11 volume over the dais, which the causeway reaches once Kyogre is awake; ky/close's guard sees online "
        "players only, so a player who logs out on the dais is filled in with barrier",
    # the crossing letting in a player without the dive tag, gym8_cleared or the station's attunement
    "kyogre.gate": None,
    # the owner said no overworld rain (KYOGRE_CAVE.md 9 answer 4)
    "kyogre.no_overworld_rain": None,
    # a player who already caught Kyogre could wake another one
    "kyogre.wake_needs_no_catch": None,
    # the Blue Orb going to someone who never caught Kyogre
    "kyogre.catchers_pedestal_needs_the_catch": None,
    # Kyogre put somewhere no player can reach it, or outside its own cage
    "kyogre.kyogre_is_reachable": None,
    # a set piece spawned into rock or somewhere unreachable
    "kyogre.set_pieces_are_reachable": None,
    # contract KC2: under a roof lower than the ladder's depth Dive's air gives nothing
    "kyogre.flooded_passages_hold_the_ladder": "DEFECT (minor): 21 water columns roofed by rock are under the ladder's "
        "deep_blocks + 2 = 7: the Trench's water under the south ledge's shelf (x 8333..8336, z 2246..2249, 5-6 high) and "
        "the Sounding's alcove sills through the wall (x 8465, 2 high); contract KC2 says every passage flooded to its roof",
    # a player without Dive has no dry place to breathe on the way down the Sounding
    "kyogre.sounding_alcoves_are_dry": None,
    # a spawn-condition block in the cave beyond the design's water
    "kyogre.no_spawn_condition_blocks": None,
    # the reef floating over or buried in the sea floor the heightmap gives
    "kyogre.reef_sits_on_heightmap_ground": None,
    # contract KC1: a kill that can reach a guardian deletes a player's claimed items
    "kyogre.kills_spare_guardians": None,
    # contract C26: the arch or the keeper opening for a player who lacks champion_cleared or a met
    "rayquaza.gate": None,
    # contract C27: the keeper teleporting, waking or killing a guardian that holds a player's items
    "rayquaza.keeper_never_touches_a_guardian": None,
    # the End's shiny level-100 Rayquaza would still spawn (the owner, KYOGRE_CAVE.md 9 answer 5)
    "rayquaza.end_spawn_overridden_empty": None,
    # the owner's level 70 (KYOGRE_CAVE.md 9 answer 6)
    "rayquaza.level": None,
    # a spawn-condition block on the island
    "rayquaza.no_spawn_condition_blocks": None,
    # the climb from the arch's landing must reach the crown at all
    "rayquaza.crown_reachable": None,
    # a player who does not think to sneak must still reach the crown
    "rayquaza.crown_reachable_upright": "DEFECT: the helix's last step, from (6412, 401.0, 5111) onto the half slab at "
        "(6412, 401.5, 5112), has 2.0 of headroom under the top floor (y403) and a half-block step needs 2.3 (vanilla "
        "lifts the box in place before it moves); tools/rayquaza_sky.py _pillar opens the floor only where a STANDING "
        "player needs 1.8, so only a sneaking player passes",
    # someone on the island with no way off but a lethal fall
    "rayquaza.nobody_is_stranded": None,
    # a reachable walk-off that kills
    "rayquaza.no_lethal_fall": "DEFECT: 27 walk-offs from the crown's broken wall tops (y405..y410) fall 35-41 blocks "
        "onto the island; the Slow Falling box (rescue) stops at y367, under the island's top, so nothing catches them",
    # the arch's doorway unreachable on foot from the summit, or the way down landing in the doorway (a tp loop)
    "rayquaza.doorway_walkable_from_the_summit": None,
    # contract C26: if no pack grants Kyogre's met, Rayquaza's gate never opens for anyone
    "trio.kyogre_met_is_defined_and_granted": None,
}


def _load_source(path, edits, name):
    """The generator module from its source with `edits` [(old, new)] applied. Each old text must occur exactly once, so a
    refactor of the generator fails this test loudly instead of silently testing nothing."""
    src = path.read_text(encoding="utf-8")
    for old, new in edits:
        n = src.count(old)
        assert n == 1, "mutation target occurs %d times in %s: %r" % (n, path.name, old[:80])
        src = src.replace(old, new)
    mod = types.ModuleType(name)
    mod.__file__ = str(path)
    exec(compile(src, str(path), "exec"), mod.__dict__)
    return mod


@pytest.fixture(scope="module")
def ground():
    import ground as G
    return G.Ground()


def _build_kyogre(mod, out, g, guarded=True):
    import coldwater_station as C
    doc = mod.load()
    if guarded:
        p = mod.plan(doc, g)                                    # the builder's own guards
    else:
        M = mod.build_model(doc)
        a = C.arch(C.load(), g)
        p = {"M": M, "O": mod.open_model(doc, M), "arch": a, "reef": mod.reef_blocks(doc, a, g)}
    mod.build(doc, p, out)
    return out


def _build_ray(mod, out, g):
    spec = mod.load()
    m = mod.geometry(spec, g)
    mod.write(mod.pack_files(spec, m), out)
    return out


@pytest.fixture(scope="module")
def real(tmp_path_factory, ground):
    d = tmp_path_factory.mktemp("real")
    k = _build_kyogre(_load_source(KYOGRE_SRC, [], "kc_real"), d / "cobblers_kyogre_cave", ground)
    r = _build_ray(_load_source(RAY_SRC, [], "ray_real"), d / "cobblers_rayquaza", ground)
    return A.audit(k, r, ground)


def test_the_audit_reports_exactly_the_properties_this_file_names(real):
    # a property silently dropped from the audit (or added without a test) would go unnoticed
    got = {it["id"] for it in real.items if it["kind"] == "property"}
    assert got == set(PROPERTIES)


@pytest.mark.parametrize("pid", sorted(PROPERTIES))
def test_property_holds_on_the_built_packs(real, pid, request):
    # each property's own comment in PROPERTIES says what breaks without it; a known defect is a strict xfail
    if PROPERTIES[pid]:
        request.node.add_marker(pytest.mark.xfail(reason=PROPERTIES[pid], strict=True))
    it = real.get(pid)
    assert it["ok"], "%s: %s %s" % (pid, it["detail"], it["cases"])


def test_the_audit_never_imports_a_builder():
    # an audit that imports the builder shares its derivation and proves nothing (KYOGRE_CAVE.md 7)
    src = (ROOT / "tools" / "kyogre_rayquaza_audit.py").read_text(encoding="utf-8")
    for name in ("kyogre_cave", "rayquaza_sky", "legendaries", "portals"):
        assert "import %s" % name not in src and "from %s" % name not in src, name


# ------------------------------------------------------------------------------------------------ mutations

KYOGRE_MUTANTS = {
    # the crossing's predicate loses gym8_cleared: the tp line and the keeper's eject no longer need eight badges
    "gate_without_gym8": ([('adv = ["%s:flag/%s=true" % (NS, f) for f in g["flags"]] + ["%s=true" % g["advancement"]]',
                            'adv = ["%s=true" % g["advancement"]]')], "kyogre.gate"),
    # the shell one block thinner than the four the design asks for
    "shell_margin_minus_one": ([('shell = dilate(M.inside, sh["margin"]) & ~M.inside',
                                 'shell = dilate(M.inside, sh["margin"] - 1) & ~M.inside')], "kyogre.seal"),
    # the cage's close grown by one in every direction, into the causeway's last cell
    "cage_close_grown": ([('"fill %d %d %d %d %d %d minecraft:barrier replace minecraft:air" % tuple(cage),',
                           '"fill %d %d %d %d %d %d minecraft:barrier replace minecraft:air" % tuple(cage_near),')],
                         "kyogre.cage_closes_only_on_its_own_cells"),
    # the reset guard's box shrunk to the rescue band: the puzzles reset around a player in the Tide Gate
    "reset_guard_box_shrunk": ([('"execute in %s run tag @a[%s] add cobblers.kc.here" % (dim, box_sel(cave_box)),',
                                 '"execute in %s run tag @a[%s] add cobblers.kc.here" % (dim, box_sel(rescue_box)),')],
                               "kyogre.no_write_over_a_player"),
    # every caught=false test on the way to the wake dropped (the shrine's refusal, its call, the wake's own return)
    "wake_without_caught": ([
        ('"execute if entity @s[advancements={%s=true}] run return run tellraw @s %s" % (ky["caught_advancement"], '
         'text(msg["wake_caught"], "dark_aqua", True)),', ''),
        ('ky["caught_advancement"], O, spot, sp_sel, F)]', 'ky["met_advancement"], O, spot, sp_sel, F)]'),
        ('"execute if entity @s[advancements={%s=true}] run return 0" % ky["caught_advancement"],', '')],
        "kyogre.wake_needs_no_catch"),
}

RAY_MUTANTS = {
    # the gate forgets met Groudon (contract C26)
    "gate_without_groudon": ([('+ [spec["gate"]["met_advancement"] % m for m in spec["gate"]["requires_met"]])',
                               '+ [spec["gate"]["met_advancement"] % m for m in spec["gate"]["requires_met"][:1]])')],
                             "rayquaza.gate"),
    # hold run on every tagged Rayquaza, guardians included (contract C27)
    "hold_reaches_a_guardian": ([('"execute if score %s %s matches 1.. as @e[type=cobblemon:pokemon,tag=%s,tag=!%s] run '
                                  'function %s/hold" % (n, obj, T, Gd, F),',
                                  '"execute if score %s %s matches 1.. as @e[type=cobblemon:pokemon,tag=%s] run '
                                  'function %s/hold" % (n, obj, T, F),')], "rayquaza.keeper_never_touches_a_guardian"),
    # the top floor never opened over the helix: the climb ends under a ceiling
    "top_floor_never_opened": ([('floor_open = floor_open or (stand > yF - 1.8 and ry < yF)', 'floor_open = False')],
                               "rayquaza.crown_reachable"),
}


@pytest.mark.parametrize("name", sorted(KYOGRE_MUTANTS))
def test_a_kyogre_generator_mutation_is_caught(name, tmp_path, ground, real):
    # a mutation of tools/kyogre_cave.py the audit lets through means the audit shares the builder's blind spot
    edits, pid = KYOGRE_MUTANTS[name]
    assert real.get(pid)["ok"], "the property must hold on the real build for the mutation to mean anything"
    mod = _load_source(KYOGRE_SRC, edits, "kc_" + name)
    k = _build_kyogre(mod, tmp_path / "cobblers_kyogre_cave", ground, guarded=False)
    rep = A.audit(k, None, ground, only="kyogre")
    assert not rep.get(pid)["ok"], "mutation %s passed %s: %s" % (name, pid, rep.get(pid)["detail"])


@pytest.mark.parametrize("name", sorted(RAY_MUTANTS))
def test_a_rayquaza_generator_mutation_is_caught(name, tmp_path, ground, real):
    # a mutation of tools/rayquaza_sky.py the audit lets through means the audit shares the builder's blind spot
    edits, pid = RAY_MUTANTS[name]
    assert real.get(pid)["ok"], "the property must hold on the real build for the mutation to mean anything"
    mod = _load_source(RAY_SRC, edits, "ray_" + name)
    r = _build_ray(mod, tmp_path / "cobblers_rayquaza", ground)
    rep = A.audit(None, r, ground, only="rayquaza")
    assert not rep.get(pid)["ok"], "mutation %s passed %s: %s" % (name, pid, rep.get(pid)["detail"])


def test_the_unguarded_kyogre_build_is_the_guarded_one(tmp_path, ground):
    # the mutants are built past plan()'s guards; if that path built something else, a caught mutant would prove nothing
    mod = _load_source(KYOGRE_SRC, [], "kc_same")
    a = _build_kyogre(mod, tmp_path / "a" / "cobblers_kyogre_cave", ground, guarded=True)
    b = _build_kyogre(mod, tmp_path / "b" / "cobblers_kyogre_cave", ground, guarded=False)
    for suffix in ("", "_build"):
        fa = {p.relative_to(a.with_name(a.name + suffix)).as_posix(): p.read_bytes()
              for p in a.with_name(a.name + suffix).rglob("*") if p.is_file()}
        fb = {p.relative_to(b.with_name(b.name + suffix)).as_posix(): p.read_bytes()
              for p in b.with_name(b.name + suffix).rglob("*") if p.is_file()}
        assert fa == fb


# ------------------------------------------------------------------------------------------------ the parser itself

def test_a_selector_box_covers_the_cells_its_volume_selects():
    # a wrong dx reading would let a guard box look like it contains a write it does not
    s = A.Sel("@a[x=10,y=20,z=30,dx=2,dy=0,dz=5,tag=!a.b,advancements={x:y/z=true,p:q=false}]")
    assert s.box() == (10, 20, 30, 12, 20, 35)
    assert s.tags() == ["!a.b"]
    assert s.advancements() == {"x:y/z": "true", "p:q": "false"}


def test_an_execute_chain_reads_its_conditions_executor_and_return():
    # the gate and guard checks read these fields; a misparse would pass a line that checks nothing
    c = A.parse_exec("execute if entity @s[tag=t] unless entity @a[tag=u] in cobblers:pocket as @e[type=cobblemon:pokemon,"
                     "tag=!cobblers.guardian] run return run function ns:f")
    assert c["returned"] and c["run"] == ["function", "ns:f"] and c["in"] == "cobblers:pocket"
    assert c["as"].is_pokemon() and c["as"].excludes_guardian()
    assert [(k[0], k[1]) for k in c["conds"]] == [("if", "entity"), ("unless", "entity")]


def test_the_half_block_walker_steps_half_a_block_only_with_room_to_rise():
    # the Rayquaza finding rests on this rule: a 0.5 step needs 2.3 over the column left behind (vanilla)
    def ground(x, z):
        return 0
    def world(ceiling):
        cells = {(1, 0): {1: "minecraft:stone_brick_slab[type=bottom]"}}
        if ceiling:
            cells[(0, 0)] = {3: "minecraft:stone"}               # 2.0 of headroom over the floor at y1
        return A.Sky(cells, ground, -2)
    start = (0, 0, 2 * (1 - (-2)), A.STAND)
    for ceiling, upright, sneaking in ((False, True, True), (True, False, True)):
        S = world(ceiling)
        dests = [d for d, k, f in A.sky_moves(S, start, sneak_ok=False) if d[:2] == (1, 0)]
        assert bool(dests) == upright
        sneak = (0, 0, start[2], A.SNEAK)
        dests = [d for d, k, f in A.sky_moves(S, sneak) if d[:2] == (1, 0)]
        assert bool(dests) == sneaking


def test_vanilla_free_fall_distance():
    # the Slow Falling catch window is derived from this; a wrong integrator would move every protected fall
    # closed form of v(t+1) = (v(t) - 0.08) * 0.98 from rest, moving by v(t) each tick: 3.92 n - 196 (1 - 0.98^n)
    for n in (0, 1, 10, 20, 40):
        assert A.fall_ticks_distance(n) == pytest.approx(3.92 * n - 196 * (1 - 0.98 ** n), abs=1e-9)

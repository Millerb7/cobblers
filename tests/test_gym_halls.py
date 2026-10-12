"""The rules of the walk-through gym halls (schema gym_hall/1, data/gym_arenas/SCHEMA.md) and of the shore exit
(`exit_passages`), proved against the independent audit's block replay and by breaking the GENERATOR.

WHAT IS READ. Every gym record in data/gym_arenas/ (the folder, never a list written here, so a gym that becomes a hall
later, or gains a shore exit, is covered the day it lands). The packs are built by tools/gym_arenas.py,
tools/gym_demolish.py and tools/gym_interiors.py into a scratch folder and replayed by tools/gym_arenas_audit.py, which
imports nothing from the generator; each property below is re-derived from the replayed blocks and the authored data
(the town plan, data/challenge_mode.json, data/gym_junior_trainers.json), never from the generator's own model.

WHAT A MUTATION IS HERE. The generator is broken in memory (tools/gym_arenas.py, tools/gym_demolish.py or
tools/reapply.py's step order patched), its own `check` silenced so the broken pack is actually written, and the same
property function is run on it: it must report a defect that it did not report on the real pack. The authored data is
never edited, so a mutation cannot move the expectation and the output together.

NOT COVERED (an experiment in a running server, not pytest): that an iron door really stays shut for a player on the
wrong side, that a stone button powers the block it is set on in the version we run, that rctmod starts a junior's
battle on sight at the distance modelled, that a player in a real client takes the stairs as modelled, and that the
takedown's `execute unless entity` guard really waits for a player to leave. Validity is not behaviour.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "tools"))

import gym_hall_harness as H  # noqa: E402
import gym_arenas as GA  # noqa: E402
import gym_arenas_audit as A  # noqa: E402

HALLS = H.halls()
PASSAGES = H.passage_gyms()
ALL = sorted(d["id"] for _p, d in H.records())


# ---------------------------------------------------------------------------------------------------- the fixtures
@pytest.fixture(scope="module")
def ctx():
    return H.Ctx()


@pytest.fixture(scope="module")
def packs(tmp_path_factory, ctx):
    """The real generators' output for every gym: the arenas and halls (their own checks ON), the R16F demolition, and
    Misty's dig (tools/gym_interiors.py writes only to build/, as tests/test_gym_arenas_audit.py already relies on)."""
    out = tmp_path_factory.mktemp("halls")
    arenas = H.build_pack(out / "arenas", G=ctx.G)
    demolish = H.build_demolish(out / "demolish")
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "gym_interiors.py"), "build"], capture_output=True, text=True)
    assert r.returncode == 0, (r.stderr or r.stdout)[-600:]
    return arenas, demolish, out


@pytest.fixture(scope="module")
def facts(ctx, packs):
    arenas, demolish, _out = packs
    return {g: H.audit(g, arenas, ctx, demolish) for g in ALL}


def mutant(ctx, packs, gym, mutate, tag, demolish=None, steps=None):
    """The audit's facts for `gym` from a pack built by the BROKEN generator."""
    _arenas, real_demolish, out = packs
    pack = H.build_pack(out / ("mut_%s_%s" % (tag, gym)), gyms=[gym], mutate=mutate, G=ctx.G)
    return H.audit(gym, pack, ctx, demolish or real_demolish, steps=steps), pack


# ---------------------------------------------------------------- the folder is not empty (the tests below are not vacuous)
def test_the_folder_holds_walk_through_halls_and_the_tests_below_cover_each_of_them():
    # breaks if: every hall record is reverted or renamed, and the parametrized tests below quietly become empty
    assert HALLS, "no data/gym_arenas/*.json is a gym_hall/1 record"
    for g in HALLS:
        assert H.record(g)["schema"] == "gym_hall/1"


# ============================================================ 1. a hall is walked street -> stand -> street
@pytest.mark.parametrize("gym", HALLS)
def test_a_hall_is_walked_from_the_street_to_the_challengers_stand_and_back_out(facts, gym):
    # breaks if: a hall is built that a player cannot enter from the street, cannot reach the challenger's stand in,
    # or cannot leave from (the owner's "a room I can't leave from")
    f = facts[gym]
    assert not H.problems(f, "REACH", "EXIT"), H.problems(f, "REACH", "EXIT")
    assert f["street_ring"] > 0 and f["reach_down"] and f["reach_up"] and f["exit_cells_on_street"] > 0


def seal_entrance(mp):
    """The generator forgets every door: after the hall is written it fills the lot's perimeter, two courses thick and
    from the street's level to head height over it, with stone (a forecourt open along its whole edge has no one door)."""
    orig = GA.place_markers

    def sealed(a, doc):
        orig(a, doc)
        (x0, z0, x1, z1), _lvl = GA.lot_of(doc)
        sy = doc["entry"]["street"][1]
        for box in ((x0, sy, z0, x0 + 1, sy + 3, z1), (x1 - 1, sy, z0, x1, sy + 3, z1),
                    (x0, sy, z0, x1, sy + 3, z0 + 1), (x0, sy, z1 - 1, x1, sy + 3, z1)):
            a.fill(box, "minecraft:stone")
    mp.setattr(GA, "place_markers", sealed)


@pytest.mark.parametrize("gym", H.two(HALLS))
def test_a_hall_whose_entrance_the_generator_seals_is_not_walkable_from_the_street(ctx, packs, facts, gym):
    # breaks if: the walk is not really replayed from the street (a hall with no door would pass)
    assert not H.problems(facts[gym], "REACH", "EXIT")
    f, _pack = mutant(ctx, packs, gym, seal_entrance, "seal")
    assert H.problems(f, "REACH"), f.get("problems")


# ================================== 2. the door past the leader opens only from a button inside the arena
def exit_findings(gym, pack, ctx, demolish):
    """Defects of the hall's door past the leader, derived from the replayed blocks: a closed iron door (both halves);
    the stone button(s) that power it, FOUND IN THE WORLD (a button moved by the generator is still found), the record's
    exit.button among them; nothing reached from the street outside the arena room can press any of them (reach 4.5
    from the eye, through open cells only); someone in the arena room can press one."""
    world, s, bounds, through, _w, _h, _l = H.assembled(gym, pack, ctx, demolish)
    rec = H.record(gym)
    door, declared_btn = tuple(rec["exit"]["door"]), tuple(rec["exit"]["button"])
    bad = []
    for half, c in (("lower", door), ("upper", (door[0], door[1] + 1, door[2]))):
        st = world.get(*c)
        if A.name_of(st) != "minecraft:iron_door" or A.prop(st, "half") != half or A.prop(st, "open") != "false":
            bad.append("door %s half %s is %r, not a closed iron door" % (list(door), half, st))
    # a button powers the block it is set on and its neighbours; an iron door beside either opens (vanilla)
    buttons = [c for c, st in world.cells.items() if A.name_of(st) == "minecraft:stone_button"
               and door in A.button_opened(world, [(c[0], c[2], c[1])])]
    if not buttons:
        bad.append("no stone button in the world opens the door %s" % (list(door),))
    elif declared_btn not in buttons:
        bad.append("the record's button %s is not among the buttons that open the door: %s" % (list(declared_btn), buttons))
    box = H.region_box(gym, s, bounds, through)
    W = A.Walker(world, box)
    starts = H.street_nodes(world, W, s["lot"])
    down = W.reach_many(starts)
    arena = [A.norm(r["box"]) for r in rec["rooms"] if r["kind"] == "arena"]
    if not arena or any(H.inside(H.feet_cell(n), b) for n in starts for b in arena):
        bad.append("the arena room box %s is empty or holds a street cell: 'inside the arena' would mean nothing" % arena)
    outside = [n for n in down if not any(H.inside(H.feet_cell(n), b) for b in arena)]
    for btn in buttons:
        near_out = [n for n in outside if H.pressable(world, n, btn)]
        if near_out:
            bad.append("the button %s can be pressed from %s, outside the arena room: the door would let a player in "
                       "past the juniors" % (list(btn), near_out[0]))
    if buttons and not any(H.pressable(world, n, btn) for btn in buttons for n in down
                           if any(H.inside(H.feet_cell(n), b) for b in arena)):
        bad.append("nobody in the arena room can reach a button: the door could never be opened from inside")
    return bad


def button_outside(target):
    """The generator writes the exit button on the OTHER side of the wall block it is set on."""
    def mutate(mp):
        orig = GA.Arena.set

        def set_(self, pos, state, seat=False):
            if tuple(pos) == tuple(target) and "stone_button" in self.state(state):
                pos, state = H.mirrored(self.state(state), pos)
            return orig(self, pos, state, seat)
        mp.setattr(GA.Arena, "set", set_)
    return mutate


def door_open(mp):
    """The generator writes every iron door standing open."""
    orig = GA.Arena.set

    def set_(self, pos, state, seat=False):
        if "iron_door" in self.state(state):
            state = self.state(state).replace("open=false", "open=true")
        return orig(self, pos, state, seat)
    mp.setattr(GA.Arena, "set", set_)


@pytest.mark.parametrize("gym", HALLS)
def test_the_door_past_the_leader_opens_only_from_a_button_inside_the_arena(ctx, packs, gym):
    # breaks if: the way out past the leader can be opened from the puzzle side, or opened by nothing at all
    arenas, demolish, _ = packs
    assert exit_findings(gym, arenas, ctx, demolish) == []


@pytest.mark.parametrize("gym", H.two(HALLS))
def test_a_button_the_generator_puts_outside_the_wall_is_caught(ctx, packs, gym):
    # breaks if: the reach test is not made from the street, so a button on the puzzle side passes
    arenas, demolish, out = packs
    target = H.record(gym)["exit"]["button"]
    pack = H.build_pack(out / ("mut_btn_" + gym), gyms=[gym], mutate=button_outside(target), G=ctx.G)
    bad = exit_findings(gym, pack, ctx, demolish)
    assert any("can be pressed from" in b for b in bad), bad


@pytest.mark.parametrize("gym", H.two(HALLS))
def test_a_door_the_generator_writes_open_is_caught(ctx, packs, gym):
    # breaks if: a standing-open door in the way out past the leader is accepted as a door
    arenas, demolish, out = packs
    pack = H.build_pack(out / ("mut_open_" + gym), gyms=[gym], mutate=door_open, G=ctx.G)
    bad = exit_findings(gym, pack, ctx, demolish)
    assert any("not a closed iron door" in b for b in bad), bad


# =============================== 3. the takedown leaves no cell of the old arena or the old building unwritten
def old_boxes(gym):
    """[(what, box)] of everything this hall replaces, from DECLARED data: replaces.arena (bounds and every
    through_building box) and the superseded building's bounds (data/gym_buildings/<gym>.json)."""
    rec = H.record(gym)
    arena = (rec.get("replaces") or {}).get("arena") or {}
    out = []
    if arena.get("bounds"):
        out.append(("the old arena", A.norm(arena["bounds"])))
    for t in arena.get("through_building") or []:
        out.append(("the old descent", A.norm(t["box"])))
    out += old_structure(gym)
    return out


def interior_of(gym):
    d = json.loads((ROOT / "data" / "gym_interiors.json").read_text(encoding="utf-8"))
    return next((g for g in d["gyms"] if g["id"] == gym), None)


def is_donor_hall(gym):
    """True when this hall replaced a COBBLEVERSE template outright (gym 2): no data/gym_buildings record, and
    data/gym_interiors.json says the template's interior is superseded by this hall's file."""
    i = interior_of(gym)
    return (not (ROOT / "data" / "gym_buildings" / ("%s.json" % gym)).is_file()
            and str((i or {}).get("superseded_by") or "").startswith("data/gym_arenas/%s.json" % gym))


def old_structure(gym):
    """[(what, box)] of the old building, from DECLARED data and never from the generator. A hall that replaced our own
    building: that building's `bounds` (data/gym_buildings/<gym>.json). A hall that replaced a donor template: the
    template's box (data/placements.json position and size of the interior's `donor`, which must equal the interior's
    shell.expect_box), its quay plinth (placements `plinth`: the lot's columns from plinth.from_y up to the template's
    first course) and the works dug under it (data/gym_interiors.json `dig`)."""
    bp = ROOT / "data" / "gym_buildings" / ("%s.json" % gym)
    if bp.is_file():
        return [("the old building", A.norm(json.loads(bp.read_text(encoding="utf-8"))["bounds"]))]
    assert is_donor_hall(gym), "%s has neither a building record nor a donor template it replaced" % gym
    i = interior_of(gym)
    pl = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["placements"]
    pl = next(p for p in pl if p["id"] == i["donor"])
    pos, size = pl["position"], pl["size"]
    tpl = (pos["x"], pos["y"], pos["z"], pos["x"] + size[0] - 1, pos["y"] + size[1] - 1, pos["z"] + size[2] - 1)
    assert tpl == tuple(i["shell"]["expect_box"]), "the placement and the interior disagree about the template's box"
    out = [("the old building", tpl)]
    if pl.get("plinth"):
        out.append(("the old plinth", (tpl[0], pl["plinth"]["from_y"], tpl[2], tpl[3], tpl[1] - 1, tpl[5])))
    out.append(("the old works", A.norm(i["dig"])))
    return out


def unwritten(gym, pack, ctx, demolish):
    """{what: (count, first cell)} of the old cells no function of the HALL (its takedown, the hall, its seat) writes.
    A hall that replaced a donor template shares the takedown with R16F (tools/gym_demolish.py, layer "demolish"),
    which fills the plinth and the works the hall does not reach; for any other hall R16F is not part of the hall."""
    world, *_ = H.assembled(gym, pack, ctx, demolish)
    mine = ("takedown", "arena", "seat", "cycle")   # "cycle": the Challenge spawner set into a cell the hall wrote
    if is_donor_hall(gym):
        mine += ("demolish",)
    out = {}
    for what, b in old_boxes(gym):
        miss = [(x, y, z) for x in range(b[0], b[3] + 1) for y in range(b[1], b[4] + 1) for z in range(b[2], b[5] + 1)
                if world.layer.get((x, y, z)) not in mine]
        if miss:
            out[what] = (len(miss), miss[0])
    return out


@pytest.mark.parametrize("gym", HALLS)
def test_the_takedown_leaves_no_cell_of_the_old_arena_or_the_old_building_unwritten(ctx, packs, gym):
    # breaks if: a cell of the carved arena or of the old building is left as it stood on a world that already holds
    # them (staging does): an open shaft under the new floor, or a stair from the old building in the new hall
    arenas, demolish, _ = packs
    assert unwritten(gym, arenas, ctx, demolish) == {}


def shrunk_takedown(mp):
    """The generator's takedown boxes stop one block short on every face."""
    orig = GA.takedown_boxes

    def short(doc):
        out = []
        for box, why in orig(doc):
            b = A.norm(box)
            out.append(((b[0] + 1, b[1] + 1, b[2] + 1, b[3] - 1, b[4] - 1, b[5] - 1), why))
        return out
    mp.setattr(GA, "takedown_boxes", short)


def no_first_carve(mp):
    """The generator drops the hall's first part, the carve of the lot above the pad that takes the old building down."""
    orig = GA.run_parts

    def run(a, parts, where="parts"):
        if where == "parts":
            i = next((k for k, q in enumerate(parts) if q.get("op") != "comment"), None)
            if i is not None and parts[i].get("op") == "carve":
                parts = parts[:i] + parts[i + 1:]
        return orig(a, parts, where)
    mp.setattr(GA, "run_parts", run)


@pytest.mark.parametrize("gym", H.two(HALLS))
@pytest.mark.parametrize("mut,what", [(shrunk_takedown, "the old arena"), (no_first_carve, "the old building")])
def test_a_generator_that_takes_down_less_than_it_replaces_is_caught(ctx, packs, gym, mut, what):
    # breaks if: the unwritten-cell count is taken from the generator's own boxes instead of the records' declared ones
    _arenas, demolish, out = packs
    pack = H.build_pack(out / ("mut_down_%s_%s" % (mut.__name__, gym)), gyms=[gym], mutate=mut, G=ctx.G)
    got = unwritten(gym, pack, ctx, demolish)
    assert what in got, got


DONOR_HALLS = [g for g in HALLS if is_donor_hall(g)]


def r16f_without(word):
    """R16F (tools/gym_demolish.py) writes no command for the box whose reason names `word` (the plinth, the works)."""
    def mutate(mp):
        import gym_demolish as GD
        orig = GD.box_commands

        def skip(box, gy, why, *a, **k):
            if word in why:
                return [], 0, 0, 0
            return orig(box, gy, why, *a, **k)
        mp.setattr(GD, "box_commands", skip)
    return mutate


def test_a_donor_template_hall_exists_so_the_template_takedown_tests_below_are_not_vacuous():
    # breaks if: no hall replaces a donor template any more and the three tests below parametrize over nothing
    assert DONOR_HALLS, "no hall replaced a donor template (data/gym_interiors.json superseded_by a gym_arenas file)"


@pytest.mark.parametrize("gym", DONOR_HALLS)
@pytest.mark.parametrize("which,what", [("plinth", "the old plinth"), ("the works", "the old works")])
def test_an_r16f_that_leaves_the_templates_plinth_or_the_works_standing_is_caught(ctx, packs, gym, which, what):
    # breaks if: the template hall's takedown is judged without R16F's share (the plinth and the dig are outside the
    # hall's bounds), or judged so loosely that R16F dropping one of them passes: shaft and cistern under a new floor
    arenas, _real, out = packs
    demolish = H.build_demolish(out / ("mut_r16f_%s_%s" % (which.replace(" ", "_"), gym)), mutate=r16f_without(which))
    got = unwritten(gym, arenas, ctx, demolish)
    assert what in got, got


def no_carve(mp):
    """The generator drops the hall's `carve` part, whichever it is: the one that clears the lot above the pad."""
    orig = GA.run_parts

    def run(a, parts, where="parts"):
        if where == "parts":
            i = next((k for k, q in enumerate(parts) if q.get("op") == "carve"), None)
            if i is not None:
                parts = parts[:i] + parts[i + 1:]
        return orig(a, parts, where)
    mp.setattr(GA, "run_parts", run)


@pytest.mark.parametrize("gym", DONOR_HALLS)
def test_a_hall_that_does_not_clear_the_template_it_stands_in_is_caught(ctx, packs, gym):
    # breaks if: the template's own box (placements position and size) is not judged: the hall's carve of the lot,
    # dropped, leaves the donor's masonry standing in the hall (R16F skips the hall's bounds, so nothing else clears it)
    _arenas, demolish, out = packs
    pack = H.build_pack(out / ("mut_tpl_" + gym), gyms=[gym], mutate=no_carve, G=ctx.G)
    got = unwritten(gym, pack, ctx, demolish)
    assert "the old building" in got, got


# =========== 4. every step alone (R16F, R16G, R16GA) on a finished world leaves every arena cell intact
def superseded_interiors():
    d = json.loads((ROOT / "data" / "gym_interiors.json").read_text(encoding="utf-8"))
    return {g["id"] for g in d["gyms"] if g.get("superseded_by")}


@pytest.mark.parametrize("gym", HALLS)
def test_every_step_alone_on_a_finished_world_leaves_every_arena_cell_intact(facts, gym):
    # breaks if: R16F, R16G or R16GA run alone (the apply supports --only) seals or opens a hall: a step that fills
    # the hall, or a takedown that runs after it, with a player inside
    f = facts[gym]
    order = f["order"]
    want = {"R16G", "R16GA"} | ({"R16F"} if gym in superseded_interiors() else set())
    assert set(order) == want, (sorted(order), sorted(want))
    for step, row in order.items():
        assert row["arena_cells_changed"] == 0 and row["reach_down"] and row["reach_up"], (step, row)
    assert not H.problems(f, "ORDER")


def takedown_last(real):
    """The step order with every hall's takedown moved AFTER its hall."""
    def steps():
        out = real()
        for step in ("R16G", "R16GA"):
            fns = list(out[step])
            for f in [f for f in fns if f.endswith("_takedown")]:
                fns.remove(f)
                fns.insert(fns.index(f.replace("_takedown", "")) + 1, f)
            out[step] = fns
        return out
    return steps


def order_matters(gym, packs, ctx):
    """True when running the hall's takedown AFTER the hall would change a cell: the hall writes a cell inside a takedown
    box and that cell does not end as the takedown's own fill block (read from the emitted takedown function). A hall
    whose only overlap with its takedown is a rock bed of the same block (gym 2: the lot filled to rock y101..104 over
    the old arena's top courses, which the takedown fills with the same stone) is order-insensitive by construction."""
    funcs = Path(packs[0]) / "data" / "cobblers" / "function" / "gym_arenas"
    boxes = [A.norm(b) for b, _w in GA.takedown_boxes(H.record(gym))]
    fills = {ln.split()[-1] for ln in (funcs / ("%s_takedown.mcfunction" % gym)).read_text(encoding="utf-8").splitlines()
             if " run fill " in ln}
    assert len(fills) == 1, (gym, fills)
    rock = fills.pop()
    world, *_ = H.assembled(gym, packs[0], ctx, packs[1])
    return any(A.name_of(world.get(*c)) != rock for c in A.function_writes(funcs / ("%s.mcfunction" % gym))
               if any(H.inside(c, b) for b in boxes))


def test_the_step_order_matters_for_at_least_one_hall_so_the_order_mutation_below_can_bite(ctx, packs):
    # breaks if: every hall's takedown becomes disjoint from the hall's own cells (or only overlaps its rock bed) and
    # the order test below skips for all
    assert any(order_matters(g, packs, ctx) for g in HALLS), "no hall's takedown overlaps what the hall writes"


@pytest.mark.parametrize("gym", HALLS)
def test_a_takedown_that_runs_after_its_hall_is_caught(ctx, packs, facts, gym):
    # breaks if: the step order is not replayed, so a takedown that fills the finished hall with rock passes. Run on the
    # halls whose takedown would change a cell the hall wrote (order_matters): for the others the order is harmless by
    # construction, and a mutation there could not bite (they skip, naming why; the test after this one proves the
    # replay agrees that they are harmless)
    import reapply
    if not order_matters(gym, packs, ctx):
        pytest.skip("%s's takedown changes no cell its hall writes: the order cannot matter" % gym)
    assert not facts[gym].get("problems"), facts[gym].get("problems")
    f, _ = mutant(ctx, packs, gym, lambda mp: None, "order", steps=takedown_last(reapply.gym_step_functions))
    if f.get("problems"):
        return
    # the audit is silent: that is only right when the wrong order changes nothing but cells wholly under the natural
    # ground (gym 2: its mud-brick foundation courses y101..102 inside the old arena's box, ground y103..108 there),
    # which no body can stand in or see. Judged from the two replays and the heightmap's own ground, never the audit.
    arenas, demolish, _ = packs
    right, *_ = H.assembled(gym, arenas, ctx, demolish)
    wrong, *_ = H.assembled(gym, arenas, ctx, demolish, steps=takedown_last(reapply.gym_step_functions))
    changed = [c for c in set(right.cells) | set(wrong.cells) if right.get(*c) != wrong.get(*c)]
    assert changed, "the takedown after the hall changed nothing in the replay and the audit is silent: not a mutation"
    exposed = [c for c in changed if c[1] > ctx.G(c[0], c[2])]
    assert exposed == [], "a takedown after the hall changes %d cell(s) above the ground and the audit says nothing: %s" % (
        len(exposed), exposed[:3])


@pytest.mark.parametrize("gym", HALLS)
def test_a_hall_judged_order_insensitive_really_is_so_in_the_replay(ctx, packs, facts, gym):
    # breaks if: order_matters() calls a hall order-insensitive (so the test above skips it) while a takedown run after
    # the hall does change something the audit sees: the skip would hide a real ordering defect. Runs on exactly the
    # halls the test above skips
    import reapply
    if order_matters(gym, packs, ctx):
        pytest.skip("%s's order matters: the test above mutates it" % gym)
    f, _ = mutant(ctx, packs, gym, lambda mp: None, "order_ins", steps=takedown_last(reapply.gym_step_functions))
    assert not f.get("problems"), f.get("problems")


@pytest.mark.parametrize("gym", [g for g in H.two(HALLS)])
def test_a_demolition_that_ignores_the_halls_reserved_volume_is_caught(ctx, packs, facts, gym):
    # breaks if: R16F alone is not replayed on a finished hall: tools/gym_demolish.py refills the old works and takes
    # down the donor shell, and the shell's box lies inside the new hall
    arenas, _real_demolish, out = packs
    if gym not in superseded_interiors():
        pytest.skip("%s has no R16F function" % gym)
    assert not H.problems(facts[gym], "ORDER", "REACH")
    demolish = H.build_demolish(out / ("mut_demolish_" + gym), mutate=lambda mp: mp.setattr(GA, "reserved_boxes",
                                                                                            lambda g: []))
    f = H.audit(gym, arenas, ctx, demolish)
    assert H.problems(f, "ORDER", "REACH"), "the audit did not see a demolition writing into the hall: %s" % f.get("order")


# ============ 5. the leader's seat and the Challenge cell are where data/challenge_mode.json says
def challenge_entry(gym):
    cm = json.loads((ROOT / "data" / "challenge_mode.json").read_text(encoding="utf-8"))
    up = H.record(gym)["leader"]["id"]
    return up, cm, cm["bosses"][up]


@pytest.mark.parametrize("gym", HALLS)
def test_the_leaders_one_spawner_stands_at_the_seat_the_challenge_data_resolves(ctx, packs, gym):
    # breaks if: the hall's seat function sets the leader's spawner anywhere but the cell tools/challenge_mode.py drives
    # (its swap would then toggle a spawner that does not exist) or leaves a second Normal spawner behind
    import challenge_mode as CM
    arenas, demolish, _ = packs
    up, cm, entry = challenge_entry(gym)
    world, s, bounds, *_ = H.assembled(gym, arenas, ctx, demolish)
    want = tuple(CM.normal_seat(up, entry))
    normal = [c for c, st in world.cells.items() if A.name_of(st) == "rctmod:trainer_spawner"
              and up in st and "_challenge" not in st and H.inside(c, bounds)]
    assert normal == [want], (normal, want)
    assert A.name_of(world.get(want[0], want[1] - 1, want[2])) == "minecraft:redstone_block"


def seat_off_by_one(mp):
    """The generator's seat function sets the spawner one block east of the seat."""
    orig = GA.hall_seat_lines

    def lines(doc):
        d = dict(doc, leader=dict(doc["leader"], seat=[doc["leader"]["seat"][0] + 1] + list(doc["leader"]["seat"][1:])))
        return orig(d)
    mp.setattr(GA, "hall_seat_lines", lines)


@pytest.mark.parametrize("gym", H.two(HALLS))
def test_a_seat_function_that_sets_the_spawner_off_the_seat_is_caught(ctx, packs, gym):
    # breaks if: the spawner cell is taken from the record the generator wrote from instead of from challenge_mode
    import challenge_mode as CM
    arenas, demolish, out = packs
    up, cm, entry = challenge_entry(gym)
    pack = H.build_pack(out / ("mut_seat_" + gym), gyms=[gym], mutate=seat_off_by_one, G=ctx.G)
    world, s, bounds, *_ = H.assembled(gym, pack, ctx, demolish)
    want = tuple(CM.normal_seat(up, entry))
    normal = [c for c, st in world.cells.items() if A.name_of(st) == "rctmod:trainer_spawner"
              and up in st and "_challenge" not in st and H.inside(c, bounds)]
    assert normal != [want], normal


@pytest.mark.parametrize("gym", HALLS)
def test_the_challenge_cell_is_in_the_arena_beside_the_seat_and_the_old_cell_is_its_superseded_at(ctx, packs, gym):
    # breaks if: a leader outside the one-leader rollout keeps a Challenge spawner somewhere the hall does not write
    # (set into rock), further than the leader's own room, or the old cell is not recorded and so never taken out
    arenas, demolish, _ = packs
    up, cm, entry = challenge_entry(gym)
    rec = H.record(gym)
    sp = entry["spawner"]
    at, seat = tuple(sp["at"]), tuple(rec["leader"]["seat"])
    world, s, bounds, through, arena_writes, _h, _l = H.assembled(gym, arenas, ctx, demolish)
    arena_room = [A.norm(r["box"]) for r in rec["rooms"] if r["kind"] == "arena"]
    assert any(H.inside(at, b) for b in arena_room), (at, arena_room)
    assert at != seat and at[1] == seat[1] and 2 <= abs(at[0] - seat[0]) + abs(at[2] - seat[2]) <= 5, (at, seat)
    assert at in arena_writes, "the hall writes nothing at %s: the Challenge spawner would be set into rock" % (at,)
    assert not A.collides(world.get(at[0], at[1] + 1, at[2])), "no headroom over the Challenge cell"
    old = sp.get("superseded_at")
    olds = [b for _w, b in old_boxes(gym)]
    inside_old = any(H.inside(at, b) for b in olds)
    if inside_old or old:
        assert old and tuple(old) != at, "the live Challenge cell %s is inside an old box and no superseded_at is recorded" % (at,)
        assert any(H.inside(tuple(old), b) for b in olds), "superseded_at %s is in none of the replaced volumes" % (old,)
        assert A.name_of(world.get(*old)) != "rctmod:trainer_spawner", "the old Challenge cell still holds a spawner"


def test_a_challenge_cell_beside_the_seat_and_the_replaced_cell_checks_agree_only_because_of_superseded_at():
    # breaks if: tools/gym_arenas.py reads a hall's LIVE Challenge cell as a replaced seat again. That was the gym 7
    # author's contradiction (2026-10-09): tests/test_challenge_mode.py needs the cell within 2..5 of the dais seat, the
    # audit forbade a spawner inside the old building's bounds, and the hall stands where the old building did, so a
    # cell 2 from the seat could be inside it. The two rules are about two cells: the LIVE one beside the seat, and the
    # OLD one the building held (`superseded_at`). With superseded_at recorded, replaced_seats() returns the old cell and
    # never the live one; without it a live cell inside the old bounds IS read as a replaced seat. Run on gym 5 and gym 1
    # (their live cells are inside the old building) with the data copied in memory.
    cm = json.loads((ROOT / "data" / "challenge_mode.json").read_text(encoding="utf-8"))
    checked = 0
    for gym in HALLS:
        rec = H.record(gym)
        sp = cm["bosses"][rec["leader"]["id"]]["spawner"]
        live = tuple(sp["at"])
        if is_donor_hall(gym):
            # a hall that replaced a donor TEMPLATE: the template's box covers the whole lot to y146, so it holds the
            # hall's own live cell and is deliberately NOT a replaced volume (replaced seats are named one by one):
            # the live cell is not a replaced seat, the old arena's cell (superseded_at) and the template's own
            # spawner (gym_interiors leader.expect_spawner_at, stamped by R9 every apply) are
            tpl = dict(old_structure(gym))["the old building"]
            assert H.inside(live, tpl), "%s: the live cell is no longer inside the template's box" % gym
            assert live not in GA.replaced_seats(rec), gym
            assert tuple(sp["superseded_at"]) in GA.replaced_seats(rec), gym
            assert tuple(interior_of(gym)["leader"]["expect_spawner_at"]) in GA.replaced_seats(rec), gym
            checked += 1
            continue
        olds = [A.norm(json.loads((ROOT / "data" / "gym_buildings" / ("%s.json" % gym)).read_text(encoding="utf-8"))["bounds"])]
        if not any(H.inside(live, b) for b in olds) or not sp.get("superseded_at"):
            continue
        checked += 1
        assert live not in GA.replaced_seats(rec), gym                      # as recorded: the live cell is not a replaced seat
        assert tuple(sp["superseded_at"]) in GA.replaced_seats(rec), gym     # the old one is
        stripped = json.loads(json.dumps(cm))
        stripped["bosses"][rec["leader"]["id"]]["spawner"].pop("superseded_at")
        real_load = GA.load
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(GA, "load", lambda p: stripped if Path(p).name == "challenge_mode.json" else real_load(p))
            assert live in GA.replaced_seats(rec), "%s: without superseded_at the live cell is not read as old" % gym
    assert checked, "no hall has a live Challenge cell inside its old building: the case this guards is gone"


@pytest.mark.parametrize("gym", DONOR_HALLS)
def test_a_generator_that_reads_the_donor_templates_box_as_a_replaced_volume_calls_the_live_cell_a_replaced_seat(gym):
    # breaks if: the template-hall branch above never bites: tools/gym_arenas.py replaced_seats() taking the template's
    # box (which holds the hall's own Challenge cell) as a replaced volume is the gym 7 contradiction again, and the
    # live-cell assertion above must see it. Mutates the GENERATOR (takedown_boxes), the data untouched.
    rec = H.record(gym)
    live = tuple(json.loads((ROOT / "data" / "challenge_mode.json").read_text(encoding="utf-8"))["bosses"][
        rec["leader"]["id"]]["spawner"]["at"])
    assert live not in GA.replaced_seats(rec)
    cm = json.loads((ROOT / "data" / "challenge_mode.json").read_text(encoding="utf-8"))
    stripped = json.loads(json.dumps(cm))
    stripped["bosses"][rec["leader"]["id"]]["spawner"].pop("superseded_at")
    real_load = GA.load
    tpl = dict(old_structure(gym))["the old building"]
    orig = GA.takedown_boxes
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(GA, "load", lambda p: stripped if Path(p).name == "challenge_mode.json" else real_load(p))
        # as the data stands, the template is no replaced volume, so the live cell is safe even without superseded_at
        assert live not in GA.replaced_seats(rec)
        mp.setattr(GA, "takedown_boxes", lambda doc: list(orig(doc)) + [(tpl, "mutant: the template box")])
        assert live in GA.replaced_seats(rec), "the template box as a replaced volume did not catch the live cell"


# ============================ 6. juniors stand on the walk and are fought before the arena
def seat_file():
    return json.loads((ROOT / "data" / "gym_junior_trainers.json").read_text(encoding="utf-8"))["trainers"]


U = 0.87      # a player's feet are anywhere in a cell: sqrt(3 * 0.5^2) from its centre (tools/gym_trainers_audit.py U)


def junior_findings(gym, pack, ctx, demolish, placements):
    """Defects of a hall's juniors against the replayed blocks. `placements` is [(id, seat, yaw)] as R17 summons them
    (tools/route_trainers.py placements()), the sight is the seat file's sight_distance. Per junior: the seat is a cell
    the street's walk stands in, and with every node the junior surely sees (distance <= sight - U, a clear line from
    the eye to its chest) removed, the street reaches neither the challenger's stand nor any cell of the arena room
    past it: every walk meets the junior before the fight the hall is built for. Unlike tools/gym_trainers_audit.py this
    asks for the clear line (a junior that covers the way only through a wall does not count)."""
    world, s, bounds, through, _w, _h, _l = H.assembled(gym, pack, ctx, demolish)
    rec = H.record(gym)
    box = H.region_box(gym, s, bounds, through)
    W = A.Walker(world, box)
    starts = H.street_nodes(world, W, s["lot"])
    down = W.reach_many(starts)
    ps = A.markers(world, bounds)["player_stand_position"][0]
    stand = (ps[0], ps[2], ps[1] + A.spawn_height_offset())
    assert stand in down, "the challenger's stand %s is not reached from the street: the cut below would be vacuous" % (stand,)
    where = {i: (seat, yaw) for i, seat, yaw in placements}
    bad = []
    for j in [t for t in seat_file() if t["gym"] == gym]:
        if j["id"] not in where:
            bad.append("%s: R17 does not summon it" % j["id"])
            continue
        seat = tuple(where[j["id"]][0])
        if not any(H.feet_cell(n) == seat or ((n[0], n[1]) == (seat[0], seat[2]) and abs(n[2] - seat[1]) <= 0.5)
                   for n in down):
            bad.append("%s: seat %s is not a cell the street's walk stands in (off the walk)" % (j["id"], list(seat)))
            continue
        sight = float(j["sight_distance"])
        centre = (seat[0] + 0.5, seat[1], seat[2] + 0.5)
        chest = (seat[0] + 0.5, seat[1] + 1.0, seat[2] + 0.5)

        def seen(n):
            return math.dist((n[0] + 0.5, n[2], n[1] + 0.5), centre) <= sight - U and H.line_clear(
                world, H.eye(n), chest, skip={seat, (seat[0], seat[1] + 1, seat[2])})
        blocked = {n for n in down if seen(n)}
        W2 = A.Walker(world, box)
        base_inbox = W2.inbox
        W2.inbox = lambda x, z, h, _b=blocked, _o=base_inbox: _o(x, z, h) and (x, z, h) not in _b
        reached = W2.reach_many([n for n in starts if n not in blocked])
        if stand in reached:
            bad.append("%s: the street reaches the challenger's stand without coming within its sight (%.1f - %.2f)"
                       % (j["id"], sight, U))
    return bad


@pytest.mark.parametrize("gym", HALLS)
def test_the_juniors_stand_on_the_walk_and_every_walk_meets_each_before_the_arena(ctx, packs, gym):
    # breaks if: a junior is seated off the walk, or beside a way round it, so a player reaches the leader without the
    # fight the hall is built around
    import route_trainers
    arenas, demolish, _ = packs
    assert [t for t in seat_file() if t["gym"] == gym], "%s has no juniors in data/gym_junior_trainers.json" % gym
    assert junior_findings(gym, arenas, ctx, demolish, route_trainers.placements()) == []


# Defects in the seat file's `room` field found by room_findings on 2026-10-09, each STRICT: a junior whose entry is
# fixed makes its test FAIL naming the entry to delete. The geometry above holds for all of them; what is stale is the
# NAME or the BOX the seat file (or the record's rooms) gives the place the junior stands.
KNOWN_ROOM_DEFECTS = {
    "gym1_junior_01": "data/gym_junior_trainers.json room 'the_wall'; data/gym_arenas/gym1.json renamed it 'sof_the_wall' "
                      "(the sof_ prefix commit ba30f21) and the seat file was not followed",
    "gym3_junior_01": "seat (1730, 175, 1394) is in the bay (room relay_lane_door, z1388..1395); relay_tower starts at z1395",
    "gym3_junior_02": "seat (1726, 177, 1403) is on the catwalk's first row; relay_leads starts at z1404, relay_tower ends at z1403 "
                      "and the seat is in it, not in the leads",
    "gym5_junior_02": "data/gym_junior_trainers.json room 'loft'; data/gym_arenas/gym5.json names it 'reed_loft' (the reed_ "
                      "prefix commit 7d7faa3)",
    "gym8_junior_02": "data/gym_junior_trainers.json room 'the_drift'; data/gym_arenas/gym8.json has no such room "
                      "(gate_yard, the_sap, the_heading, the_sally, muster_hall)",
}


def room_findings(gym):
    """Pure data: each junior of the gym names a room of the hall that comes before the arena, and stands in its box."""
    rec = H.record(gym)
    rooms = rec["rooms"]
    ids = [r["id"] for r in rooms]
    arena_i = [i for i, r in enumerate(rooms) if r["kind"] == "arena"][-1]
    out = {}
    for j in [t for t in seat_file() if t["gym"] == gym]:
        seat = tuple(j["seat"])
        if j.get("room") not in ids:
            out[j["id"]] = "room %r is not a room of data/gym_arenas/%s.json %s" % (j.get("room"), gym, ids)
        elif ids.index(j["room"]) >= arena_i:
            out[j["id"]] = "room %r is the arena or after it" % j["room"]
        elif not H.inside(seat, A.norm(rooms[ids.index(j["room"])]["box"])):
            out[j["id"]] = "seat %s is not in room %s's box %s" % (list(seat), j["room"], rooms[ids.index(j["room"])]["box"])
    return out


@pytest.mark.parametrize("gym", HALLS)
def test_each_junior_names_a_room_of_its_hall_before_the_arena_and_stands_in_it(gym):
    # breaks if: the seat file's `room` drifts from the hall's rooms (a rename, a moved box), so the walk-through
    # documentation of where each fight happens is wrong
    found = room_findings(gym)
    for jid, why in KNOWN_ROOM_DEFECTS.items():
        if jid.startswith(gym + "_"):
            assert jid in found, "fixed: remove %r from KNOWN_ROOM_DEFECTS" % jid
    unknown = {k: v for k, v in found.items() if k not in KNOWN_ROOM_DEFECTS}
    assert unknown == {}, unknown
    if found:
        pytest.xfail("; ".join("%s: %s" % (k, KNOWN_ROOM_DEFECTS[k]) for k in sorted(found)))


def mutated_route_trainers(seat_expr):
    """tools/route_trainers.py with its placements() return line replaced: the generator of what R17 summons."""
    import types
    path = ROOT / "tools" / "route_trainers.py"
    old = 'return [(s["id"], tuple(s["seat"]), s["yaw"]) for s in seats]'
    src = path.read_text(encoding="utf-8")
    assert src.count(old) == 1, "mutation anchor moved in tools/route_trainers.py"
    mod = types.ModuleType("route_trainers_mutant")
    mod.__file__ = str(path)
    exec(compile(src.replace(old, seat_expr), str(path), "exec"), mod.__dict__)
    return mod


def shifted_placements(last, shift):
    """tools/route_trainers.py's placements() with the junior `last` summoned `shift` (dx, dz) blocks from its seat."""
    return mutated_route_trainers(
        'return [(s["id"], (s["seat"][0] + %d, s["seat"][1], s["seat"][2] + %d) if s["id"] == %r else tuple(s["seat"]), '
        's["yaw"]) for s in seats]' % (shift[0], shift[1], last)).placements()


def test_a_junior_the_generator_seats_off_its_chokepoint_or_off_the_walk_is_caught(ctx, packs):
    # breaks if: the juniors are judged from the seat file instead of from what R17 summons, or the cut test can never
    # fail. The LAST junior of the first hall is summoned 40 blocks away (out of the hall: it must be named as off the
    # walk) and 3 blocks along each axis (a seat that may or may not still cover the chokepoint: the control run is
    # clean, and at least one of the four shifts must break the cut on the real geometry)
    import route_trainers
    arenas, demolish, _ = packs
    gym = HALLS[0]
    last = sorted(t["id"] for t in seat_file() if t["gym"] == gym)[-1]
    assert junior_findings(gym, arenas, ctx, demolish, route_trainers.placements()) == []
    far = junior_findings(gym, arenas, ctx, demolish, shifted_placements(last, (40, 0)))
    assert any(last in b and "walk" in b for b in far), far
    near = [junior_findings(gym, arenas, ctx, demolish, shifted_placements(last, sh))
            for sh in ((3, 0), (-3, 0), (0, 3), (0, -3))]
    assert any(near), "no 3-block shift of %s broke the cut: the test cannot fail" % last


# ============================================ 7. exit_passages: the shore exit
@pytest.mark.skipif(not PASSAGES, reason="no record carries exit_passages")
@pytest.mark.parametrize("gym", PASSAGES)
def test_the_shore_reaches_nothing_on_the_hall_side_the_stand_reaches_the_shore_and_no_water_enters(facts, gym):
    # breaks if: the passage is a way IN (the shore reaches the hall with the door shut, or a button in reach of it),
    # no way out (the stand never reaches the shore), or floods
    f = facts[gym]
    e = f["exit"]
    assert not H.problems(f, "EXIT", "WATER", "REACH"), H.problems(f, "EXIT", "WATER", "REACH")
    assert e["shore_reach"] > 0 and e["shore_starts"] > 0, "the shore walk started nowhere: the in-check is vacuous"
    assert e["shore_meets_hall_side"] == 0 and e["shore_reached_with_doors_shut"] == 0
    assert e["shore_nodes_reached"] > 0 and e["doors_opened"], "the stand reaches no ground outside the boxes"


def tread_short(mp):
    """The generator drops the middle tread of the stair that rises inside an exit passage's box."""
    orig = GA.straight_stair

    def stair(a, part):
        boxes = [b for b, _p in GA.passages(a.doc)]
        n = int(part["steps"])
        if n >= 3 and any(GA.inside(tuple(part["from"]), b) for b in boxes):
            k = n // 2
            dx, dz = GA.DIRS[part["dir"]]
            x, y, z = part["from"]
            orig(a, dict(part, steps=k))
            orig(a, dict(part, steps=n - k - 1, **{"from": [x + dx * (k + 1), y - (k + 1), z + dz * (k + 1)]}))
        else:
            orig(a, part)
    mp.setattr(GA, "straight_stair", stair)


def passage_door(gym):
    return tuple(H.record(gym)["exit_passages"][0]["door"])


def passage_door_open(gym):
    d = passage_door(gym)
    cells = {d, (d[0], d[1] + 1, d[2])}

    def mutate(mp):
        orig = GA.Arena.set

        def set_(self, pos, state, seat=False):
            if tuple(pos) in cells:
                state = self.state(state).replace("open=false", "open=true")
            return orig(self, pos, state, seat)
        mp.setattr(GA.Arena, "set", set_)
    return mutate


@pytest.mark.skipif(not PASSAGES, reason="no record carries exit_passages")
@pytest.mark.parametrize("gym", PASSAGES)
@pytest.mark.parametrize("which", ["door_open", "tread_short", "button_outside"])
def test_a_shore_exit_with_its_door_open_a_tread_short_or_its_button_outside_is_caught(ctx, packs, facts, gym, which):
    # breaks if: the shore walk does not really shut the door, step the stair or keep the button out of the shore's
    # reach: the passage would then be a way in, or no way out, and still read as clean
    assert not H.problems(facts[gym], "EXIT")
    mut = {"door_open": passage_door_open(gym), "tread_short": tread_short,
           "button_outside": button_outside(H.record(gym)["exit_passages"][0]["button"])}[which]
    f, _ = mutant(ctx, packs, gym, mut, which)
    assert H.problems(f, "EXIT"), (which, f.get("problems"))

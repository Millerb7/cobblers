"""tools/pokemon_farm_audit.py against tools/pokemon_farm.py (and the idle pack tools/ambient_idle.py writes for its
animals): the audit's own rules on hand-built worlds, and a broken GENERATOR failing a named check.

Written 2026-10-05 by an agent that built none of Arrow Creeks Farm (CLAUDE.md principle 16). Every mutation below
changes the generator's CODE (a function of tools/pokemon_farm.py) and leaves data/pokemon_farm.json and every other
data file alone: a record-side mutation moves the expectation and the output together and proves nothing (CLAUDE.md,
"How to prove an audit is independent"). A mutation counts as caught only by an error the unmutated build does not
already have. The generator's own guards are switched off (files(check=False)) so the audit is what must catch it.

THE MUTATION RUN (2026-10-05, on the synthetic flat ground below; the same four are the tests at the bottom):
  1. piece_fence writes its gates `open=true`               -> "pens: the cow pasture is open: ... gets out at ..."
                                                               (every pen), and the AI-on animals "not penned"
  2. idlers() moves mareep_1 twelve blocks west, outside the -> "claims: mareep_1 (mareep) ... is spawned by 0 idlers",
     sheep pasture and the farm fence                          "... inside the farm's bbox is none of the record's animals"
  3. idlers() gives cobblemon:pokemon_eats_grass to every    -> "animals: miltank_pasture (claim ...): cobblemon:pokemon_
     follower without one (the Miltank among them)             eats_grass is not one of miltank's own behaviours"
  4. plan() puts a minecraft:water block on the cow trough   -> "writes: minecraft:water at ... is a spawn condition"
Each is reverted by monkeypatch at the test's end.

Most tests run on a synthetic ground, flat at y100 and dry: every ground spot is y101 by hand. The committed build on
the canonical heightmap and the real Cobblemon jar is tested last (skipped, and says so, without them).

NOT covered (a running server): the blocks landing; shears on the farm's unowned flock, the fleece regrowing, a bucket
doing nothing on a farm Miltank (read from the jar only, see the audit's docstring); followers staying penned under
Cobblemon's real pathing; the frame rate.
"""
import inspect
import json
import math
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import ambient_idle_audit as AIA  # noqa: E402
import pokemon_farm_audit as A  # noqa: E402

DOC = json.loads((ROOT / "data" / "pokemon_farm.json").read_text(encoding="utf-8"))
IDLE = json.loads((ROOT / "data" / "ambient.json").read_text(encoding="utf-8"))["idle"]
REAPPLY = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")


class Flat:
    """Flat y100: every ground spot is y101 by hand. (On flat ground the generator's plant clears merge into fills over
    the server's 32,768-block limit and its function_limits guard refuses the build; bumpy ground instead trips its
    body guard on the Tauros and Bouffalant. build_pack() switches the limit guard off: the audit's replay reads a fill
    of any size, and the real heightmap build passes the guard.)"""

    def __call__(self, x, z):
        return 100


def dry(x, z):
    return None


class HandJar:
    """A synthetic jar: the species table of data/pokemon_farm.json (checked against the real jar in the last test)
    with the ai behaviours and features read from Cobblemon 1.8.0 by hand (2026-10-05): mareep/wooloo/dubwool
    ai [pokemon_eats_grass], features [sheared]; combee ai [pokemon_bee], features [has_nectar]; the rest none."""
    AI = {"mareep": {"cobblemon:pokemon_eats_grass"}, "wooloo": {"cobblemon:pokemon_eats_grass"},
          "dubwool": {"cobblemon:pokemon_eats_grass"}, "combee": {"cobblemon:pokemon_bee"}}
    FEAT = {"mareep": {"sheared"}, "wooloo": {"sheared"}, "dubwool": {"sheared"}, "combee": {"has_nectar"}}
    path = "hand"

    def species(self, name):
        t = DOC["species"].get(name)
        if t is None:
            return None
        return {"width": t["width"], "height": t["height"], "features": self.FEAT.get(name, set()),
                "ai": self.AI.get(name, set()), "file": "hand/%s.json" % name}


G, JAR = Flat(), HandJar()


# ------------------------------------------------------------------ building the artifacts (the generators run)


def build_pack(out, g=G):
    import pokemon_farm as PF
    with pytest.MonkeyPatch.context() as mp:
        if isinstance(g, Flat):
            mp.setattr(PF.function_limits, "check_lines", lambda *a, **k: [])
        written, _b = PF.files(PF.load(), g, lambda x, z: False, check=False)
    for rel, text in written.items():
        f = Path(out) / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    return Path(out)


def build_idle(out, g=G):
    """The idle pack's farm group as tools/ambient_idle.py writes it: its functions() over the farm's idlers (the town
    groups need a full build/ and are not the farm's). The keep gate is plan()'s formula."""
    import ambient_idle as AI
    import pokemon_farm as PF
    rules = dict(IDLE["rules"])
    kinds_on = [k for k in rules["enabled_kinds"] if k in AI.KINDS]
    idl = PF.idlers(g, rules, kinds_on)
    cx = sum(i["at"][0] for i in idl) / len(idl)
    cz = sum(i["at"][2] for i in idl) / len(idl)
    cy = int(round(sum(i["at"][1] for i in idl) / len(idl)))
    r = max(math.dist((cx, cz), (i["at"][0], i["at"][2])) for i in idl) + rules["keep_margin"]
    pl = {"rules": rules, "towns": {PF.TOWN: idl}, "gates": {PF.TOWN: {"centre": [round(cx, 1), cy, round(cz, 1)],
                                                                        "radius": int(math.ceil(r))}}}
    base = Path(out) / "data" / "cobblers" / "function" / "ambient_idle"
    for name, cmds in AI.functions(pl).items():
        p = base / (name + ".mcfunction")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(cmds) + "\n", encoding="utf-8", newline="\n")
    return Path(out)


def run(tmp, g=G, water=dry, jar=JAR):
    tmp = Path(tmp)
    pack = build_pack(tmp / "packs" / "cobblers_pokemon_farm", g)
    idle = build_idle(tmp / "packs" / "cobblers_ambient_idle", g)
    return A.audit(DOC, g, water, pack, jar=jar, idle_pack=idle, packs=tmp / "packs")


def mutate(monkeypatch, owner, name, *pairs):
    """Replace text in the SOURCE of owner.name and install the result: the generator's code, never its data."""
    fn = getattr(owner, name)
    src = textwrap.dedent(inspect.getsource(fn))
    for old, new in pairs:
        assert old in src, "the mutation's anchor is not in %s any more: %r" % (name, old)
        src = src.replace(old, new, 1)
    ns = dict(fn.__globals__)
    exec(compile(src, fn.__code__.co_filename, "exec"), ns)
    monkeypatch.setattr(owner, name, ns[name])


@pytest.fixture(scope="module")
def baseline(tmp_path_factory):
    return run(tmp_path_factory.mktemp("farm_base"))


def caught(rep, baseline, check):
    return [e for e in rep.errors if e not in set(baseline.errors) and e.startswith(check + ":")]


# ------------------------------------------------------------------ the rules, on hand-built worlds


class Cells:
    """A hand world: flat stone to y100, the given cells over it."""

    def __init__(self, cells):
        self.cells = cells

    def at(self, x, y, z):
        if (x, y, z) in self.cells:
            return self.cells[(x, y, z)]
        return "minecraft:stone" if y <= 100 else "minecraft:air"


def ring(x0, z0, x1, z1, block="minecraft:spruce_fence", y=101, skip=()):
    return {(x, y, z): block for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)
            if (x in (x0, x1) or z in (z0, z1)) and (x, z) not in skip}


def inside(x0, z0, x1, z1):
    return lambda x, z: x0 < x < x1 and z0 < z < z1


# Without it a pen with a missing rail would pass: the walker's flood is the whole closure rule.
def test_a_fence_ring_holds_a_walker_and_a_gap_lets_it_out():
    w = Cells(ring(0, 0, 6, 6))
    region, esc = AIA.enclosure(w.at, (3, 101, 3), inside(0, 0, 6, 6))
    assert esc is None and len(region) == 25                      # the 5 x 5 inside, by hand
    w = Cells(ring(0, 0, 6, 6, skip={(6, 3)}))
    assert AIA.enclosure(w.at, (3, 101, 3), inside(0, 0, 6, 6))[1] == (6, 3)


# Without it a pen walled by one-block blocks would pass: a walker jumps one block, never a 1.5-high fence.
def test_a_walker_jumps_one_block_but_never_a_fence():
    w = Cells(ring(0, 0, 6, 6, block="minecraft:hay_block"))
    assert AIA.enclosure(w.at, (3, 101, 3), inside(0, 0, 6, 6))[1] is not None
    cells = ring(0, 0, 6, 6)
    cells[(1, 101, 3)] = "minecraft:hay_block"                    # a feeder against the rail: still no way over
    assert AIA.enclosure(Cells(cells).at, (3, 101, 3), inside(0, 0, 6, 6))[1] is None
    cells = ring(0, 0, 6, 6, skip={(6, 3)})
    cells[(6, 101, 3)] = "minecraft:spruce_fence_gate[facing=east,open=false]"
    assert AIA.enclosure(Cells(cells).at, (3, 101, 3), inside(0, 0, 6, 6))[1] is None
    cells[(6, 101, 3)] = "minecraft:spruce_fence_gate[facing=east,open=true]"
    assert AIA.enclosure(Cells(cells).at, (3, 101, 3), inside(0, 0, 6, 6))[1] == (6, 3)


# Without it a follower walled in by a house would count as penned: a pen is fenced.
def test_penned_needs_a_fence_all_round_and_the_home_disc_inside():
    assert AIA.penned(Cells(ring(-6, -6, 6, 6)).at, (0, 101, 0), 3) == (True, None)
    planks = ring(-6, -6, 6, 6, block="minecraft:spruce_planks")
    planks.update(ring(-6, -6, 6, 6, block="minecraft:spruce_planks", y=102))
    ok, why = AIA.penned(Cells(planks).at, (0, 101, 0), 3)
    assert not ok and "not fence, gate or wall" in why
    ok, why = AIA.penned(Cells(ring(-3, -3, 3, 3)).at, (0, 101, 0), 3)   # the fence at 3 is inside the radius-3 disc
    assert not ok and "home disc" in why
    ok, why = AIA.penned(Cells({}).at, (0, 101, 0), 3)
    assert not ok and "walk out" in why


# Without it a fence's connection state could be anything: vanilla's FenceBlock.connectsTo, by hand.
def test_fence_joins_follow_vanilla():
    assert A.joins("minecraft:spruce_fence", "minecraft:oak_fence", "east")
    assert not A.joins("minecraft:spruce_fence", "minecraft:nether_brick_fence", "east")
    assert A.joins("minecraft:spruce_fence", "minecraft:spruce_fence_gate[facing=south]", "east")
    assert not A.joins("minecraft:spruce_fence", "minecraft:spruce_fence_gate[facing=south]", "north")
    assert A.joins("minecraft:spruce_fence", "minecraft:grass_block[snowy=false]", "west")
    assert A.joins("minecraft:spruce_fence", "minecraft:hay_block[axis=y]", "west")
    for no in ("minecraft:jack_o_lantern[facing=west]", "minecraft:oak_leaves", "minecraft:lantern[hanging=false]",
               "minecraft:air", "minecraft:farmland[moisture=7]", "minecraft:water_cauldron[level=3]"):
        assert not A.joins("minecraft:spruce_fence", no, "west"), no
    assert A.joins("minecraft:glass_pane", "minecraft:glass_pane", "north")


# Without it a sign's NBT (spaces inside quotes) or a fill-replace would be misread as blocks.
def test_the_reader_reads_setblocks_fills_and_clears():
    R = A.Replay("# chunks-loaded-by: forceload add 1 2 3 4\n"
                 "fill 0 1 0 1 1 1 minecraft:stone\n"
                 "fill 0 2 0 9 3 9 minecraft:air replace #minecraft:logs\n"
                 "setblock 5 5 5 minecraft:oak_sign[rotation=4]{front_text:{messages:['\"A b\"','\"\"','\"\"','\"\"']}}\n"
                 "say hi\n")
    assert R.hold == (1, 2, 3, 4) and len(R.blocks) == 5 and len(R.clears) == 1 and R.bad == ["say hi"]
    assert A.base(R.blocks[(5, 5, 5)]) == "minecraft:oak_sign"


# The behaviour rule: without it eats-grass on a Miltank, or a sheep that never regrows, would pass.
def test_an_extra_behaviour_must_be_the_species_own_and_a_sheared_walker_must_graze():
    cells = ring(-8, -8, 8, 8)
    cells.update({(x, 100, z): "minecraft:grass_block[snowy=false]" for x in range(-7, 8) for z in range(-7, 8)})
    w = Cells(cells)
    rules = IDLE["rules"]

    def errs(species, beh, ai_on=True):
        rep = A.Report()
        A.check_animal(rep, "t", {"species": species}, (0, 101, 0), w, JAR, rules, beh, ai_on, 4)
        return rep.errors
    assert errs("mareep", ["cobblemon:pokemon_eats_grass"]) == []
    assert any("not one of miltank's own" in e for e in errs("miltank", ["cobblemon:pokemon_eats_grass"]))
    assert any("never grows back" in e for e in errs("wooloo", []))
    assert any("never runs" in e for e in errs("combee", ["cobblemon:pokemon_bee"], ai_on=False))
    assert errs("combee", ["cobblemon:pokemon_bee"]) == []     # the owner's hive-working bees, if they come, by rule
    bare = Cells(ring(-8, -8, 8, 8))
    rep = A.Report()
    A.check_animal(rep, "t", {"species": "dubwool"}, (0, 101, 0), bare, JAR, rules, ["cobblemon:pokemon_eats_grass"], True, 4)
    assert any("not grass_block" in e for e in rep.errors)


# Without it a spawn-condition block allowed for some other place would pass here: the scope must name the farm.
def test_the_policy_whitelist_is_the_entries_scoped_to_this_farm():
    white = A.policy_white(ROOT / "data", DOC)
    assert "minecraft:wheat" not in white or any(
        "pokemon_farm" in (w.get("scope") or "") and "minecraft:wheat" in w["blocks"]
        for w in json.loads((ROOT / "data" / "spawn_block_policy.json").read_text(encoding="utf-8"))["whitelist"])
    assert "minecraft:quartz_block" not in white                 # scoped to overworld placements, not to this farm


# Without it the step could move after the Habitat Blocks or the claims audit run before the idle pack exists.
def test_the_wiring_is_read_from_reapply():
    rep = A.Report()
    A.check_wiring(DOC, rep, REAPPLY)
    assert rep.errors == []
    swapped = REAPPLY.replace('out.append(("R9E"', 'out.append(("R9TMP"', 1).replace('out.append(("R9PF"', 'out.append(("R9E"', 1) \
        .replace('out.append(("R9TMP"', 'out.append(("R9PF"', 1)
    rep = A.Report()
    A.check_wiring(DOC, rep, swapped)
    assert any("runs after R9E" in e for e in rep.errors)
    late = REAPPLY.replace('add("pokemon_farm_audit:animals"', 'add("pokemon_farm_audit_x"', 1).replace(
        'add("pokemon_farm_audit", "pokemon_farm_audit.py", *src)',
        'add("pokemon_farm_audit", "pokemon_farm_audit.py", *src)\n    add("pokemon_farm_audit:animals", "pokemon_farm_audit.py", "--animals", *src)', 1)
    rep = A.Report()
    A.check_wiring(DOC, rep, late)
    assert any("pokemon_farm_audit:animals runs before ambient_idle:build" in e for e in rep.errors)


# ------------------------------------------------------------------ the generator, mutated (data untouched)


# The baseline on flat ground: the only errors are the ones flat ground makes -- the record's measured centre (y88)
# and the two NPC seats, authored at the real ground's y (89 and 88), against y101 here.
def test_the_unmutated_farm_on_flat_ground_is_clean_but_for_the_ground(baseline):
    ground_made = ("siting: site.measured", "seats: the farmer at [3145, 89, 5710]", "seats: the stand keeper at [3153, 88, 5764]")
    assert [e for e in baseline.errors if not e.startswith(ground_made)] == [], baseline.errors[:5]
    assert len(baseline.errors) == 1 + 3 + 3       # each seat: not at y101, and stone in its feet and head


# Mutation 1. Without the pen check an open gate would pass.
def test_a_generator_that_leaves_its_gates_open_is_caught(monkeypatch, tmp_path, baseline):
    import pokemon_farm as PF
    mutate(monkeypatch, PF, "piece_fence", ("in_wall=false,open=false", "in_wall=false,open=true"))
    rep = run(tmp_path)
    assert any("the cow pasture is open" in e for e in caught(rep, baseline, "pens")), rep.errors[:5]
    assert any("not penned" in e for e in caught(rep, baseline, "animals"))


# Mutation 2. Without the claims' position match a sheep spawned outside its pen would pass.
def test_a_generator_that_puts_a_sheep_outside_its_pen_is_caught(monkeypatch, tmp_path, baseline):
    import pokemon_farm as PF
    mutate(monkeypatch, PF, "idlers", ('        x, y, z = animals[a["id"]]\n',
                                       '        x, y, z = animals[a["id"]]\n'
                                       '        if a["id"] == "mareep_1":\n            x -= 12\n'))
    rep = run(tmp_path)
    c = caught(rep, baseline, "claims")
    assert any("mareep_1 (mareep)" in e and "spawned by 0 idlers" in e for e in c), c
    assert any("is none of the record's animals" in e for e in c)


# Mutation 3. Without the jar's behaviour rule eats-grass on the Miltank would pass.
def test_a_generator_that_gives_the_miltank_eats_grass_is_caught(monkeypatch, tmp_path, baseline):
    import pokemon_farm as PF
    eg = '["cobblemon:pokemon_eats_grass"]'
    mutate(monkeypatch, PF, "idlers",
           ('if kind == "follower" and a.get("extra_behaviours"):', 'if kind == "follower":'),
           ('[b for b in a["extra_behaviours"] if b not in base_follow]',
            '[b for b in (a.get("extra_behaviours") or %s) if b not in base_follow]' % eg))
    rep = run(tmp_path)
    assert any("miltank_pasture" in e and "not one of miltank's own behaviours" in e
               for e in caught(rep, baseline, "animals")), rep.errors[:5]


# Mutation 4. Without the spawn-condition check a water block on the farm would pass.
def test_a_generator_that_places_water_is_caught(monkeypatch, tmp_path, baseline):
    import pokemon_farm as PF
    mutate(monkeypatch, PF, "plan", ("    connect(s)\n    return s",
                                     # straight into the plan: Site.put's own allow-list guard would refuse it
                                     '    s.solid[(s.cx + 20, s.g(s.cx + 20, s.cz - 20) + 1, s.cz - 20)] = "minecraft:water"\n'
                                     "    connect(s)\n    return s"))
    rep = run(tmp_path)
    assert any("minecraft:water" in e and "spawn condition" in e for e in caught(rep, baseline, "writes")), rep.errors[:5]


# ------------------------------------------------------------------ the committed build, real ground and jar


@pytest.fixture(scope="module")
def real():
    import ground as G
    from terrain import env_source_root
    root = env_source_root()
    if not root or not Path(root).is_dir():
        pytest.skip("NOT_EXECUTED: no canonical heightmap here (COBBLERS_SOURCE_ROOT %r)" % root)
    g = G.load(root)
    jp = A.find_jar()
    if not jp or not Path(jp).is_file():
        pytest.skip("NOT_EXECUTED: no Cobblemon 1.8 jar on this machine")
    return g, A.Jar(jp)


# The data's species table is what the builder checked bodies with: without this it could drift from the jar.
def test_the_records_species_table_is_the_jars(real):
    _g, jar = real
    for name, t in DOC["species"].items():
        if name in ("source",):
            continue
        sp = jar.species(name)
        assert sp is not None, name
        assert abs(sp["width"] - t["width"]) <= 0.01 and abs(sp["height"] - t["height"]) <= 0.01, (name, sp, t)
    assert "cobblemon:pokemon_eats_grass" in jar.species("mareep")["ai"]
    assert "cobblemon:pokemon_eats_grass" not in jar.species("miltank")["ai"]


# The whole audit on what the generators build from the committed data on the real heightmap: only KNOWN defects.
def test_the_committed_farm_has_no_unrecorded_defect(real, tmp_path):
    g, jar = real
    import southern_residents_audit as SA
    pack = build_pack(tmp_path / "packs" / "cobblers_pokemon_farm", g)
    idle = build_idle(tmp_path / "packs" / "cobblers_ambient_idle", g)
    water = SA.Water(g, [tuple(DOC["site"]["centre"])])
    rep = A.audit(DOC, g, water, pack, jar=jar, vanilla=A.vanilla_blocks(), idle_pack=idle, packs=tmp_path / "packs")
    real_, _hits, stale = A.classify(rep.errors)
    assert real_ == [] and stale == [], (real_[:6], stale)

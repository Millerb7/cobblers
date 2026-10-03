"""The Spectrier cap: tools/spectrier_cap.py -> build/datapacks/cobblers_spectrier_cap, from data/spectrier_cap.json.

The spec is data/adopted_legendary_sites.json adopted_crown_cemetery.spectrier_once_per_player (the owner, 2026-10-02):
one Spectrier per player at the Crown Cemetery, permanently, recorded ON THE SPAWN so every summon path is covered.

Written by a test author who did not build the pack. Independence:
  - the footprint, its corners and its centre are recomputed here from data/placements.json legendary_crown_cemetery
    (position + size), never from data/spectrier_cap.json's centre or coverage note;
  - the radii the pack USES are read from the emitted function text, not from the data the generator read;
  - behaviour is checked by running the emitted functions in tests/mcfunction_sim.py (extended below for the four
    things this pack needs: `execute in`, the advancements= and gamemode= selector arguments, `advancement grant`,
    and vanilla's half-block centring of an integer x/z in `positioned`);
  - the generator is MUTATED (a temp copy of its source, data untouched) to show the checks bite.

Everything is offline: packs are generated into tmp_path. Nothing here launches Minecraft or reads a world.

NOT COVERED (needs a boot and a functional test in experiments/): that Cobblemon 1.8.0 really writes
Pokemon.Species / Pokemon.PokemonOriginalTrainerType / a top-level Owner as data/spectrier_cap.json cites; that
LumyMon's summon makes a cobblemon:pokemon entity the tick sees; that `tp` to y-128 then `kill` leaves no drop in
the cemetery; that the advancement persists across restarts; that the tick costs what its comment says.
"""
from __future__ import annotations

import inspect
import json
import math
import re
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import function_limits  # noqa: E402
import mcfunction_sim as M  # noqa: E402
import reapply  # noqa: E402
import spectrier_cap  # noqa: E402

GEN_SRC = ROOT / "tools" / "spectrier_cap.py"
DOC = json.loads((ROOT / "data" / "spectrier_cap.json").read_text(encoding="utf-8"))
PLACEMENTS = ROOT / "data" / "placements.json"
FN = "cobblers:spectrier_cap/"
SPECIES = "cobblemon:spectrier"


def _placement(pid="legendary_crown_cemetery", path=PLACEMENTS):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    recs = [r for r in doc["placements"] if r.get("id") == pid]
    assert len(recs) == 1, "data/placements.json must carry exactly one %s" % pid
    return recs[0]


REC = _placement()


def generate(tmp_path, mod=spectrier_cap, placements=None, name="pack"):
    out = tmp_path / name
    argv = ["--out", str(out)]
    if placements is not None:
        argv += ["--placements", str(placements)]
    assert mod.main(argv) == 0
    return out


def mutant(old, new):
    """The generator with one source edit; data/ untouched. The anchor must occur exactly once."""
    src = GEN_SRC.read_text(encoding="utf-8")
    assert src.count(old) == 1, "mutation anchor not found once in tools/spectrier_cap.py: %r" % old
    mod = types.ModuleType("spectrier_cap_mutant")
    mod.__file__ = str(GEN_SRC)
    exec(compile(src.replace(old, new), "spectrier_cap_mutant", "exec"), mod.__dict__)
    return mod


def functions(pack):
    base = Path(pack) / "data" / "cobblers" / "function" / "spectrier_cap"
    return {p.stem: p.read_text(encoding="utf-8").splitlines() for p in sorted(base.glob("*.mcfunction"))}


def body(lines):
    return [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]


def callers(fns, name):
    """[(caller, line)] of every emitted line that runs function `name`."""
    pat = re.compile(r"\bfunction %s(\s|$)" % re.escape(FN + name))
    return [(f, l) for f, ls in fns.items() for l in body(ls) if pat.search(l)]


# ------------------------------------------------------------------------------------------------ the simulator


class Sim(M.World):
    """tests/mcfunction_sim.World plus what this pack needs, from vanilla 1.21.1 semantics."""

    MINE = ("advancements", "gamemode", "sort", "limit")

    def select(self, sel, ctx, single=False):
        m = re.match(r"@([aepsr])\[(.*)\]$", sel)
        if not m:
            return super().select(sel, ctx, single)
        kind, args = m.group(1), M._args(m.group(2))
        if kind in "pr":
            raise M.Unsupported("@%s with arguments" % kind)
        rest = [(k, v) for k, v in args if k not in self.MINE]
        pool = super().select("@%s[%s]" % (kind, ",".join("%s=%s" % kv for kv in rest)) if rest else "@" + kind, ctx)
        origin = list(ctx.pos)
        for k, v in rest:
            if k in ("x", "y", "z"):
                origin["xyz".index(k)] = float(v)
        sort, limit = "arbitrary", None
        for k, v in args:
            if k == "advancements":
                inner = v.strip()[1:-1]
                for item in inner.split(","):
                    aid, _, want = item.rpartition("=")
                    want = want == "true"
                    pool = [e for e in pool if (aid in getattr(e, "advancements", set())) == want]
            elif k == "gamemode":
                neg, gm = v.startswith("!"), v.lstrip("!")
                pool = [e for e in pool if (getattr(e, "gamemode", "survival") == gm) != neg]
            elif k == "sort":
                sort = v
            elif k == "limit":
                limit = int(v)
        if sort == "nearest":
            pool = sorted(pool, key=lambda e: math.dist(e.pos, origin))
        elif sort != "arbitrary":
            raise M.Unsupported("sort %s" % sort)
        return pool[:limit] if limit is not None else pool

    def _execute(self, toks, i, ctx, stores):
        if i < len(toks) and toks[i] == "in":
            if toks[i + 1] != "minecraft:overworld":
                raise M.Unsupported("dimension %s" % toks[i + 1])
            return self._execute(toks, i + 2, ctx, stores)
        if i < len(toks) and toks[i] == "positioned" and toks[i + 1] != "as":
            # Vec3Argument centre-corrects an integer literal x and z by half a block (y is not corrected)
            xyz = list(toks[i + 1:i + 4])
            for j in (0, 2):
                if re.fullmatch(r"-?\d+", xyz[j]):
                    xyz[j] = str(int(xyz[j]) + 0.5)
            return self._execute(toks, i + 4, ctx.but(pos=self.coords(xyz, ctx)), stores)
        return super()._execute(toks, i, ctx, stores)

    def c_advancement(self, rest, ctx):
        m = re.match(r"grant (\S+) only (\S+)$", rest)
        if not m:
            raise M.Unsupported("advancement %s" % rest)
        n = 0
        for e in self.select(m.group(1), ctx):
            if m.group(2) not in e.advancements:      # vanilla: granting a held advancement changes nothing, fails
                e.advancements.add(m.group(2))
                self._log((self.tick_no, "grant", (e, m.group(2))))
                n += 1
        if not n:
            raise M.Failed("nothing granted")
        return n


ADV = DOC["advancement"]


def world(pack):
    return Sim.from_pack(pack)


def centre_of(pack):
    """The emitted centre, as the game reads it (integer x/z centre-corrected)."""
    tick = body(functions(pack)["tick"])
    m = [re.search(r"positioned (\S+) (\S+) (\S+)", l) for l in tick]
    m = [x for x in m if x]
    assert len(m) == 1, "the tick must position at exactly one centre: %s" % tick
    x, y, z = (float(v) for v in m[0].groups())
    return (x + 0.5 if x.is_integer() else x, y, z + 0.5 if z.is_integer() else z)


def player(w, pos, name="p", holder=False, gamemode="survival"):
    p = w.add_player(pos, name)
    p.advancements = {ADV} if holder else set()
    p.gamemode = gamemode
    return p


def pokemon(w, pos, species=SPECIES, ot="NONE", owner=None, pastured=False):
    nbt = {"Tethering": {"PokemonOwnerId": "x"}} if pastured else {"Pokemon": {"Species": species,
                                                                               "PokemonOriginalTrainerType": ot}}
    if owner is not None:
        nbt["Owner"] = owner
    return w.add(M.Entity("cobblemon:pokemon", pos, nbt=nbt))


def off(c, dx=0.0, dy=0.0, dz=0.0):
    return (c[0] + dx, c[1] + dy, c[2] + dz)


# ------------------------------------------------------------------------------------------------ checks
# Each check takes a built pack and raises AssertionError; the mutation tests run them on mutated generators.


def check_wild_only(pack):
    fns = functions(pack)
    skip = DOC["tag_prefix"] + "skip"
    ins = body(fns["inspect"])
    # the NBT test names the species and requires an unheld Pokemon; anything else is tagged skip
    assert any('nbt={Pokemon:{Species:"%s",PokemonOriginalTrainerType:"NONE"}}' % SPECIES in l
               and l.startswith("execute unless entity @s[") and l.endswith("tag @s add %s" % skip) for l in ins), \
        "inspect must tag skip every entity that is not a Pokemon{Species:%s, OT NONE}: %s" % (SPECIES, ins)
    assert "execute if data entity @s Owner run tag @s add %s" % skip in ins, \
        "inspect must tag skip any entity with a top-level Owner (a sent-out Pokemon): %s" % ins
    # behaviour: a capped player stands beside every kind of not-wild Spectrier; none is ever judged
    w = world(pack)
    c = centre_of(pack)
    p = player(w, off(c, 2), holder=True)
    owned = pokemon(w, off(c, 1), ot="PLAYER", owner=[1, 2, 3, 4])            # a player's, sent out
    trainer = pokemon(w, off(c, -1), ot="NONE", owner=[5, 6, 7, 8])           # OT NONE but owned: an NPC's
    held = pokemon(w, off(c, 0, 0, 1), ot="PLAYER")                           # once held, no Owner now
    pastured = pokemon(w, off(c, 0, 0, -1), pastured=True)                     # Tethering instead of Pokemon
    other = pokemon(w, off(c, 3), species="cobblemon:glastrier")              # wild, wrong species
    w.tick(3)
    for e in (owned, trainer, held, pastured, other):
        assert e.alive, "a not-wild Spectrier (or another species) reached the removal: %r %s" % (e, e.nbt)
        assert skip in e.tags, "%r was not tagged skip after inspection" % e
    assert not any(f.endswith("/judge") for _t, f in w.calls), "judge ran for a not-wild Spectrier"
    assert not p.messages


def check_first_summoner_kept(pack):
    w = world(pack)
    c = centre_of(pack)
    p = player(w, off(c, 3))
    s = pokemon(w, c)
    w.tick()
    assert ADV in p.advancements, "the first summoner was not granted %s" % ADV
    assert s.alive, "a first summoner's Spectrier was removed"
    assert not p.messages, "a first summoner was told off: %s" % p.messages
    # a capped friend arriving later never takes it away: it is judged once
    player(w, off(c, -2), name="friend", holder=True)
    w.tick(5)
    assert s.alive, "a granted Spectrier was removed on a later tick"
    assert sum(1 for _t, f in w.calls if f.endswith("/judge")) == 1, "a Spectrier was judged more than once"


def check_holder_refused(pack):
    w = world(pack)
    c = centre_of(pack)
    p = player(w, off(c, 3), holder=True)
    s = pokemon(w, c)
    w.tick()
    assert not s.alive, "a holder's new Spectrier was not removed"
    assert p.messages == [{k: v for k, v in DOC["refusal_message"].items() if k in ("text", "color", "italic", "bold")}]
    assert not w.logged("grant"), "a holder was granted again"


def check_removal(pack):
    below = int(DOC["removal"]["below_y"])
    w = world(pack)
    c = centre_of(pack)
    player(w, off(c, 3), holder=True)
    s = pokemon(w, off(c, 1, 0, 1))
    start = list(s.pos)
    w.tick()
    # this Spectrier's own log entries, in order: tp entries carry (entity, pos, rot), kill entries the entity
    mine = [(kind, d) for _t, kind, d in w.log
            if d is s or (isinstance(d, tuple) and d and d[0] is s)]
    kinds = [k for k, _d in mine]
    assert "tp" in kinds and "kill" in kinds, "the refused Spectrier was not teleported and killed: %s" % kinds
    assert kinds.index("tp") < kinds.index("kill"), "killed before it was teleported below the world: %s" % kinds
    tp = mine[kinds.index("tp")][1][1]
    assert tp == (start[0], float(below), start[2]), \
        "the Spectrier was not sent straight down to y%d before the kill: %s" % (below, tp)


def check_coverage(pack, rec=REC):
    fns = functions(pack)
    near = [l for l in body(fns["near"]) if "type=cobblemon:pokemon" in l]
    assert len(near) == 1, near
    radius = int(re.search(r"distance=\.\.(\d+)", near[0]).group(1))
    assert callers(fns, "near") and all(f == "tick" for f, _l in callers(fns, "near")), \
        "near must be run only by the tick, at the tick's centre"
    p, (sx, sy, sz) = rec["position"], rec["size"]
    cx, cy, cz = centre_of(pack)
    for centre in ((cx, cy, cz), (math.floor(cx), cy, math.floor(cz))):   # with and without vanilla's half-block
        for x in (p["x"], p["x"] + sx):
            for y in (p["y"], p["y"] + sy):                                # the floor and the top of the template
                for z in (p["z"], p["z"] + sz):
                    d = math.dist(centre, (x, y, z))
                    assert d <= radius, ("footprint corner (%d, %d, %d) is %.2f from the centre %s, outside the "
                                         "emitted spawn radius %d" % (x, y, z, d, centre, radius))


def check_judge_order(pack):
    fns = functions(pack)
    holds = "@s[advancements={%s=true}]" % ADV
    j = body(fns["judge"])
    refuse = [i for i, l in enumerate(j) if "function %srefuse" % FN in l]
    grant = [i for i, l in enumerate(j) if "advancement grant" in l]
    assert len(refuse) == 1 and len(grant) == 1, j
    assert refuse[0] < grant[0], "judge grants before it refuses: a first summoner would be refused: %s" % j
    assert j[refuse[0]].startswith("execute if entity %s run" % holds), j[refuse[0]]
    assert j[grant[0]] == "execute unless entity %s run advancement grant @s only %s" % (holds, ADV), j[grant[0]]
    assert callers(fns, "refuse") == [("judge", j[refuse[0]])], "refuse must be reached only from judge's holder line"
    assert [f for f, _l in callers(fns, "remove")] == ["refuse"], "remove must be reached only from refuse"
    check_first_summoner_kept(pack)
    check_holder_refused(pack)


# ------------------------------------------------------------------------------------------------ the pack


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    return generate(tmp_path_factory.mktemp("spectrier"))


# 1. without it: a player's own Spectrier, sent out at the cemetery, could be judged and killed.
def test_only_a_wild_spectrier_is_ever_judged(pack):
    check_wild_only(pack)


# 2. without it: a Spectrier summoned in a corner of the cemetery is outside the search and is never capped.
def test_search_radius_covers_every_corner_of_the_cemetery(pack):
    check_coverage(pack)


# 2, hand-computed: if the corner arithmetic drifts, this pins it to the numbers worked out by hand.
def test_footprint_corner_distance_is_the_hand_computed_value(pack):
    # corner (4118, 1982), size 45 x 24 x 47 -> centre (4140.5, 2005.5); emitted y112, top face y133:
    # dx 22.5, dz 23.5, dy 21 -> sqrt(506.25 + 552.25 + 441) = sqrt(1499.5)
    assert (REC["position"], REC["size"]) == ({"x": 4118, "y": 109, "z": 1982}, [45, 24, 47])
    c = centre_of(pack)
    worst = max(math.dist(c, (x, y, z)) for x in (4118, 4163) for y in (109, 133) for z in (1982, 2029))
    assert worst == pytest.approx(math.sqrt(1499.5))


# 2b. without it: a wild Spectrier the search reaches can stand beside its summoner while the tick sleeps,
# because the tick's player guard is narrower than search radius + summoner radius. The summoner then catches it.
def test_the_tick_wakes_for_every_summoner_of_a_spectrier_inside_the_cemetery(pack):
    fns = functions(pack)
    guard = int(re.search(r"@a\[distance=\.\.(\d+)\]", " ".join(body(fns["tick"]))).group(1))
    summoner = int(re.search(r"@a\[distance=\.\.(\d+)", " ".join(body(fns["inspect"]))).group(1))
    p, (sx, sy, sz) = REC["position"], REC["size"]
    c = centre_of(pack)
    far = max(math.dist(c, (x, y, z)) for x in (p["x"], p["x"] + sx) for y in (p["y"], p["y"] + sy)
              for z in (p["z"], p["z"] + sz))
    assert guard >= far + summoner, (
        "the tick's player guard %d is under the farthest footprint corner %.2f + the summoner radius %d = %.2f: a "
        "player within %d of a Spectrier in that corner is not within %d of the centre, so it is never judged"
        % (guard, far, summoner, far + summoner, summoner, guard))


# 3. without it: the cap would search round a point that is not the cemetery the placement record puts in the world.
def test_emitted_centre_is_the_placements_footprint_centre(pack):
    p, (sx, sy, sz) = REC["position"], REC["size"]
    cx, cy, cz = centre_of(pack)
    assert (cx, cz) == (p["x"] + sx / 2, p["z"] + sz / 2), "emitted centre %s is not the footprint centre" % ((cx, cz),)
    assert p["y"] <= cy < p["y"] + sy, "emitted centre y%s is outside the template's height" % cy


def _moved(tmp_path, **change):
    doc = json.loads(PLACEMENTS.read_text(encoding="utf-8"))
    for r in doc["placements"]:
        if r.get("id") == "legendary_crown_cemetery":
            for k, v in change.items():
                if k in ("x", "y", "z"):
                    r["position"][k] += v
                else:
                    r[k] = v
    f = tmp_path / "placements.json"
    f.write_text(json.dumps(doc), encoding="utf-8")
    return f


# 3. without it: the cemetery could move and the cap keep guarding the old ground, silently.
@pytest.mark.parametrize("change", [{"x": 100}, {"z": -60}, {"x": 23}, {"y": 4}, {"rotation": "clockwise_90"}])
def test_tool_refuses_when_the_cemetery_has_left_its_centre(tmp_path, change):
    with pytest.raises(SystemExit):
        generate(tmp_path, placements=_moved(tmp_path, **change))


# 3. without it: a placement moved by less than half its width keeps the old centre inside, the tool still emits, and
# the far side of the moved cemetery is outside the search. The tool must refuse or still cover the moved footprint.
def test_tool_never_emits_a_cap_that_misses_the_cemetery_it_was_given(tmp_path):
    moved = _moved(tmp_path, x=20)
    try:
        out = generate(tmp_path, placements=moved)
    except SystemExit:
        return
    check_coverage(out, _placement(path=moved))


# 4. without it: a capped player summons again and keeps it, or a first summoner loses theirs.
def test_a_holder_is_refused_before_any_grant_and_a_first_summoner_is_kept(pack):
    check_judge_order(pack)


# 4. without it: the cap would be per summon, not per player: the second Spectrier of one player survives.
def test_one_spectrier_per_player_ever(pack):
    w = world(pack)
    c = centre_of(pack)
    p = player(w, off(c, 3))
    first = pokemon(w, c)
    w.tick()
    second = pokemon(w, off(c, -1))
    w.tick()
    assert first.alive and not second.alive and ADV in p.advancements


# 4. the spec's accepted weak point, pinned so a change to it is deliberate: the NEAREST player within the summoner
# radius is the summoner. Without it: attribution could silently move to someone else.
def test_the_nearest_player_is_the_summoner(pack):
    w = world(pack)
    c = centre_of(pack)
    capped = player(w, off(c, 4), name="capped", holder=True)
    friend = player(w, off(c, 9), name="friend")
    s = pokemon(w, c)
    w.tick()
    assert not s.alive and ADV not in friend.advancements and capped.messages


# 5. without it: the advancement could be earned by something other than the judge (a trigger a player can meet).
def test_advancement_has_exactly_one_impossible_criterion(pack):
    ns, path = ADV.split(":", 1)
    adv = json.loads((pack / "data" / ns / "advancement" / (path + ".json")).read_text(encoding="utf-8"))
    assert list(adv["criteria"].values()) == [{"trigger": "minecraft:impossible"}], adv
    assert adv["requirements"] == [list(adv["criteria"])], adv
    assert "rewards" not in adv, "the cap's advancement must not run anything when granted"
    grants = [l for ls in functions(pack).values() for l in body(ls) if "advancement grant" in l]
    assert len(grants) == 1 and grants[0].endswith("only %s" % ADV), grants


# 6. without it: an operator watching in spectator mode could be blamed for a summon, or the radius drift from data.
def test_spectators_are_never_a_summoner_and_the_radius_is_the_datas(pack):
    r = int(DOC["radii"]["summoner"])
    sel = [l for l in body(functions(pack)["inspect"]) if "@a[" in l]
    assert sel and all("@a[distance=..%d,gamemode=!spectator" % r in l for l in sel), sel
    w = world(pack)
    c = centre_of(pack)
    watcher = player(w, off(c, 1), name="op", holder=True, gamemode="spectator")
    s = pokemon(w, c)
    w.tick(3)
    assert s.alive and not s.tags and not watcher.messages, "a spectator was treated as the summoner"
    late = player(w, off(c, r + 0.5), name="late")
    w.tick()
    assert not late.advancements, "a player outside the summoner radius %d was judged" % r
    late.pos = list(off(c, r - 0.5))
    w.tick()
    assert ADV in late.advancements and s.alive and ADV in watcher.advancements and not watcher.messages


# 7. without it: the pack is generated and never installed, or installed and never rebuilt.
def test_pack_is_wired_into_reapply_and_prepare(monkeypatch):
    name = "cobblers_spectrier_cap"
    assert name in reapply.SERVER_PACKS and name in reapply.WORLD_LOCAL
    assert reapply.EXCLUDED.get(name, "").strip(), "%s must be EXCLUDED with a reason (it has no step)" % name
    assert reapply.PACKS / name == spectrier_cap.DEFAULT_OUT, "the tool writes where reapply installs from"
    jobs = reapply.prepare_jobs(types.SimpleNamespace(source_root="x", server_dir="x"))
    mine = [(n, f) for n, f in jobs if inspect.getclosurevars(f).nonlocals.get("tool") == "spectrier_cap.py"]
    assert len(mine) == 1, "exactly one prepare job must run spectrier_cap.py: %s" % [n for n, _f in jobs]
    ran = []
    monkeypatch.setattr(reapply, "py", lambda *a, **k: ran.append(a))
    mine[0][1]()
    assert ran == [(reapply.TOOLS / "spectrier_cap.py",)], ran


# 7. without it: a function the server refuses or truncates would load silently and never cap anything.
def test_every_emitted_function_passes_function_limits_and_resolves(pack):
    fns = functions(pack)
    assert set(fns) == {"tick", "near", "inspect", "judge", "refuse", "remove"}, set(fns)
    for n, lines in fns.items():
        assert function_limits.check_lines(lines, n) == [], n
    for n, lines in fns.items():
        for ref in re.findall(r"\bfunction (\S+)", " ".join(body(lines))):
            assert ref.startswith(FN) and ref[len(FN):] in fns, "%s calls a function the pack lacks: %s" % (n, ref)
    tick = json.loads((pack / "data" / "minecraft" / "tags" / "function" / "tick.json").read_text(encoding="utf-8"))
    assert tick == {"values": [FN + "tick"]}, tick


# 7. without it: a function removed from the generator would survive in build/ from a previous run.
def test_regeneration_leaves_no_stale_function(tmp_path):
    out = generate(tmp_path)
    stale = out / "data" / "cobblers" / "function" / "spectrier_cap" / "old.mcfunction"
    stale.write_text("kill @e\n", encoding="utf-8")
    generate(tmp_path)
    assert not stale.exists()


# 8. without it: the removed Spectrier's drops would lie in the cemetery, a reward for being refused.
def test_removal_is_what_the_data_says(pack):
    assert DOC["removal"]["method"] == "teleport below the world, then kill"
    ow = json.loads((ROOT / "modpack" / "datapacks" / "cobblers_height" / "data" / "minecraft" / "dimension_type"
                     / "overworld.json").read_text(encoding="utf-8"))
    below = int(DOC["removal"]["below_y"])
    assert below < ow["min_y"], "y%d is not below the overworld floor y%d" % (below, ow["min_y"])
    kills = [(f, l) for f, ls in functions(pack).items() for l in body(ls) if l.startswith("kill") or " kill " in l]
    assert kills == [("remove", "kill @s")], "the only kill is the removal's: %s" % kills
    check_removal(pack)


# ------------------------------------------------------------------------------------------------ mutations
# Each mutation edits the GENERATOR's source in memory (data/ untouched) and shows a check above fails.


def _fails(check, mod, tmp_path, *a):
    out = generate(tmp_path, mod=mod, name="mutant")
    with pytest.raises(AssertionError):
        check(out, *a)


# without it: nothing shows the wild check would notice a lost Owner skip.
def test_mutation_drop_owner_skip_is_caught(tmp_path):
    mod = mutant('        "execute if data entity @s Owner run tag @s add %s" % skip,\n', "")
    _fails(check_wild_only, mod, tmp_path)


# without it: nothing shows the order check would notice a grant moved ahead of the refusal.
def test_mutation_grant_before_refuse_is_caught(tmp_path):
    src = GEN_SRC.read_text(encoding="utf-8")
    a = '        "execute if entity %s run function %s" % (holds, _fn("refuse")),\n'
    b = '        "execute unless entity %s run advancement grant @s only %s" % (holds, adv),\n'
    assert a + b in src
    mod = mutant(a + b, b + a)
    _fails(check_judge_order, mod, tmp_path)
    _fails(check_first_summoner_kept, mod, tmp_path)      # behaviourally: the first summoner loses it


# without it: nothing shows the coverage check would notice the builder's original radius 32.
def test_mutation_shrink_spawn_radius_is_caught(tmp_path):
    mod = mutant('% (int(r["spawn"]), skip, seen, _fn("inspect"))', '% (32, skip, seen, _fn("inspect"))')
    _fails(check_coverage, mod, tmp_path)


# without it: nothing shows the removal check would notice a plain kill that drops loot in the cemetery.
def test_mutation_plain_kill_is_caught(tmp_path):
    mod = mutant('        "tp @s ~ %d ~" % int(doc["removal"]["below_y"]),\n', "")
    _fails(check_removal, mod, tmp_path)


# without it: nothing shows the refusal test would notice the footprint check going missing.
def test_mutation_no_centre_check_is_caught(tmp_path):
    # every guard in check_centre switched off at once (inside, footprint centre, coverage)
    mod = mutant("    x, y, z = doc[\"site\"][\"centre\"]\n    p = rec[\"position\"]\n",
                 "    return\n    x, y, z = doc[\"site\"][\"centre\"]\n    p = rec[\"position\"]\n")
    moved = _moved(tmp_path, x=100)
    assert generate(tmp_path, mod=mod, placements=moved, name="mutant").is_dir()

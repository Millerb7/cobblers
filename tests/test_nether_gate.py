"""The Nether's badge-8 gate: tools/nether_gate.py -> build/datapacks/cobblers_nether_gate, from data/nether_gate.json.

Written by the builder of the pack (an independent audit is a later unit's), so the checks are built to be mutated:
  - behaviour is checked by RUNNING the emitted functions, with the real generated blackout pack beside them, in
    tests/pocket_sim.py (dimensions, positional selectors), extended below for `ride ... dismount`, `execute on
    passengers`, `data modify storage ... set value`, and vanilla's changed_dimension trigger, modelled HERE from
    vanilla semantics (every change of a player's dimension grants each un-held advancement whose `to`/`from` match);
  - a teleport of a player who is still riding is refused by the model (what vanilla does with the mount across
    dimensions is EXP-063's), so the pack must dismount first;
  - the pallet's expected landing y comes from tools/ground.py (round(ground) + 1), never from the pack or the
    generator;
  - the generator is MUTATED (a temporary copy of its source, data untouched) to show each check bites.

NOT COVERED (EXP-063): that vanilla 1.21.1 raises changed_dimension for a portal, a /tp and a Waystones warp; that a
positional selector in `execute in` really confines @a to that dimension for players (EXP-047 showed it for the
reverse, an unpositioned @e reaching across); what Cobblemon does with a sent-out mount left in the Nether; the cost.
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import re
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import blackout_pack as BP  # noqa: E402
import entei_boss as EB  # noqa: E402
import function_limits  # noqa: E402
import nether_gate  # noqa: E402
import pocket_sim as P  # noqa: E402
import reapply  # noqa: E402

GEN_SRC = ROOT / "tools" / "nether_gate.py"
DOC = json.loads((ROOT / "data" / "nether_gate.json").read_text(encoding="utf-8"))
BLACKOUT = json.loads((ROOT / "data" / "blackout.json").read_text(encoding="utf-8"))
NETHER, OVER, POCKET = "minecraft:the_nether", "minecraft:overworld", "cobblers:pocket"
FLAG = "cobblers:flag/gym8_cleared"
CHAMP = "cobblers:flag/champion_cleared"
BOUNCE_TEXT = DOC["message"]["bounce"]


def _ground():
    try:
        import ground as G
        return G.load()
    except Exception as e:  # noqa: BLE001 - any missing heightmap
        pytest.skip("the canonical heightmap is not available here: %s" % e)


def _blackout_functions():
    files = BP.build(BLACKOUT, BP.load("water_mounts.json"), BP.load("placements.json"), BP.load("progression.json"))
    fns = {}
    for rel, text in files.items():
        m = re.fullmatch(r"data/([^/]+)/function/(.+)\.mcfunction", rel)
        if m:
            fns["%s:%s" % (m.group(1), m.group(2))] = text.splitlines()
    return fns


BO_FNS = _blackout_functions()
BO_OBJECTIVES = set(re.findall(r"^scoreboard objectives add (\S+)", "\n".join(BO_FNS["cobblers:blackout/load"]), re.M))
CHECKPOINTS = BP.checkpoints(BLACKOUT, BP.load("placements.json"), BP.load("progression.json"))


# ------------------------------------------------------------------------------------------------- the model


class GateWorld(P.World):
    """pocket_sim plus what the gate needs. Riding is a `vehicle` attribute on the rider."""

    def __init__(self, pack_dir, extra_functions=None, missing_ok=()):
        super().__init__(pack_dir, extra_functions)
        self.missing_ok = tuple(missing_ok)

    def call(self, name, ctx, args=None):
        if name not in self.functions and name.startswith(self.missing_ok):
            # vanilla: an unknown function is a runtime error of that one command, which fails
            raise P.Failed("unknown function %s" % name)
        return super().call(name, ctx, args)

    def run_tokens(self, t, ctx, from_macro=False, raw=None):
        if t[0] == "ride":
            e = self.one(t[1], ctx)
            if t[2] != "dismount":
                raise P.Unsupported(" ".join(t))
            if getattr(e, "vehicle", None) is None:
                raise P.Failed("not riding")
            e.vehicle = None
            return 1
        if t[0] == "tag" and t[2] == "remove":
            for e in self.select(t[1], ctx):
                e.tags.discard(t[3])
            return 1
        if t[0] == "tp":
            for e in self.select(t[1], ctx):
                if getattr(e, "vehicle", None) is not None:
                    raise P.Unsupported("tp of a rider: what vanilla does with the mount is EXP-063's")
        if t[0] == "data" and t[1] == "modify" and t[2] == "storage" and t[5:7] == ["set", "value"]:
            node = self.storage.setdefault(t[3], {})
            parts = t[4].split(".")
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node[parts[-1]] = json.loads(t[7]) if t[7].startswith('"') else t[7]
            return 1
        return super().run_tokens(t, ctx, from_macro, raw)

    def execute(self, t, ctx, from_macro):
        if t[0] == "on":
            if t[1] != "passengers":
                raise P.Unsupported("execute on %s" % t[1])
            riders = [e for e in self.ents if getattr(e, "vehicle", None) is ctx.ent]
            return sum(self.execute(t[2:], ctx.but(ent=e), from_macro) for e in riders) if riders else 0
        if "on" in t[:t.index("run")] if "run" in t else False:
            raise P.Unsupported("execute ... on: only as the first subcommand")
        return super().execute(t, ctx, from_macro)

    # vanilla's changed_dimension, modelled here: every change of a player's dimension fires it
    def fire_changed_dimension(self, p, old):
        for aid, adv in sorted(self.advs.items()):
            for crit in adv["criteria"].values():
                if crit["trigger"] != "minecraft:changed_dimension" or aid in p.advancements:
                    continue
                c = crit.get("conditions", {})
                if c.get("to", p.dim) == p.dim and c.get("from", old) == old:
                    p.advancements.add(aid)
                    fn = adv.get("rewards", {}).get("function")
                    if fn:
                        self.call(fn, P.Ctx(p, p.dim, p.pos))

    def as_player(self, p, fn):
        """Run a function as and at p (a mod teleport, a pack's own function), firing the trigger on a change."""
        before = {e.name: e.dim for e in self.players()}
        self.call(fn, P.Ctx(p, p.dim, p.pos))
        for e in self.players():
            if e.dim != before.get(e.name, e.dim):
                self.fire_changed_dimension(e, before[e.name])

    def arrive(self, p, dim, pos, mount=None):
        """A portal, an operator's /tp or a Waystones warp: the player (and a mount they ride) cross, then the
        trigger fires."""
        old = p.dim
        p.dim, p.pos = dim, [float(v) for v in pos]
        if mount is not None:
            mount.dim, mount.pos = dim, list(p.pos)
        self.fire_changed_dimension(p, old)


def gen(tmp_path, mod=nether_gate, name="gate"):
    out = tmp_path / name
    mod.write(mod.build(mod.load()), out)
    return out


def world(pack, blackout=True, extra=None):
    fns = dict(BO_FNS) if blackout else {}
    fns.update(extra or {})
    w = GateWorld(pack, fns, missing_ok=() if blackout else ("cobblers:blackout/",))
    if blackout:
        w.objectives |= BO_OBJECTIVES
    w.boot()
    return w


def at_checkpoint(w, p, kind="center"):
    cid, _k, name, x, y, z, _r = next(c for c in CHECKPOINTS if c[1] == kind)
    y = 70 if y is None else y
    for obj, v in (("bo.cp", cid), ("bo.cpx", x), ("bo.cpy", y), ("bo.cpz", z)):
        w.set(p.name, obj, v)
    return (x + 0.5, float(y), z + 0.5), name


def pallet_landing():
    g = _ground()
    x, _y, z = BLACKOUT["pallet"]["position"]
    return (x + 0.5, float(g(x, z) + 1), z + 0.5)


def landed(p):
    return p.dim, tuple(round(v, 3) for v in p.pos)


# ------------------------------------------------------------------------------------------------- scenarios
# Each is a function of a built pack, so the mutation tests below can run it against a mutated generator.


def scenario_portal_without_badge_goes_to_checkpoint(pack):
    w = world(pack)
    a = w.player("ash", OVER, (100.5, 70, 100.5))
    want, name = at_checkpoint(w, a)
    w.arrive(a, NETHER, (12.5, 64, 12.5))
    assert a.dim == NETHER, "the trigger must not teleport inside the dimension change"
    w.tick(1)
    assert landed(a) == (OVER, want), landed(a)
    assert any(BOUNCE_TEXT in m for m in a.messages), a.messages
    # the place line names the blackout's storage, and the blackout's own name function filled it with this Center
    assert any('"storage": "cobblers:blackout", "nbt": "place"' in m for m in a.messages), a.messages
    assert w.storage["cobblers:blackout"]["place"] == name, w.storage.get("cobblers:blackout")
    assert "cobblers:nether_gate/arrived" not in a.advancements, "the trigger must revoke itself, or fire only once"
    w.arrive(a, NETHER, (12.5, 64, 12.5))
    w.tick(1)
    assert landed(a) == (OVER, want) and w.get("ash", "ng.b") == 2, "a second arrival must bounce again"


def scenario_no_checkpoint_goes_to_the_pallet_on_ground(pack):
    w = world(pack)
    a = w.player("ash", OVER, (100.5, 70, 100.5))
    w.arrive(a, NETHER, (12.5, 64, 12.5))
    w.tick(1)
    assert landed(a) == (OVER, pallet_landing()), (landed(a), pallet_landing())
    assert any(BLACKOUT["pallet"]["name"] in m for m in a.messages), a.messages


def scenario_stale_checkpoint_goes_to_the_pallet(pack):
    w = world(pack)
    a = w.player("ash", OVER, (100.5, 70, 100.5))
    at_checkpoint(w, a)
    w.set("ash", "bo.cpx", w.get("ash", "bo.cpx") + 5000)        # the Center moved: the blackout rejects it
    w.arrive(a, NETHER, (12.5, 64, 12.5))
    w.tick(1)
    assert landed(a) == (OVER, pallet_landing()), landed(a)


def scenario_without_the_blackout_pack_the_net_still_sends_them_home(pack):
    w = world(pack, blackout=False)
    a = w.player("ash", NETHER, (12.5, 64, 12.5))
    w.tick(DOC["sweep"]["period_ticks"])
    assert landed(a) == (OVER, pallet_landing()), landed(a)


def scenario_two_arrive_together(pack):
    w = world(pack)
    a = w.player("ash", OVER, (100.5, 70, 100.5))
    b = w.player("brock", OVER, (101.5, 70, 100.5), advancements={FLAG})
    want, _n = at_checkpoint(w, a)
    w.arrive(a, NETHER, (12.5, 64, 12.5))
    w.arrive(b, NETHER, (13.5, 64, 12.5))
    w.tick(DOC["sweep"]["period_ticks"] * 3)
    assert landed(a) == (OVER, want), landed(a)
    assert landed(b) == (NETHER, (13.5, 64.0, 12.5)) and not b.messages, (landed(b), b.messages)
    assert w.get("brock", "ng.b") is None


def scenario_a_rider_is_dismounted_and_sent_home_without_the_mount(pack):
    w = world(pack)
    a = w.player("ash", OVER, (100.5, 70, 100.5))
    want, _n = at_checkpoint(w, a)
    mount = P.Ent("cobblemon:pokemon", OVER, (100.5, 70, 100.5), nbt={"Pokemon": {"Species": "cobblemon:rapidash"}})
    w.ents.append(mount)
    a.vehicle = mount
    rider = w.player("misty", OVER, (100.5, 71, 100.5), advancements={FLAG})
    rider.vehicle = a                                             # something riding the player
    w.arrive(a, NETHER, (12.5, 64, 12.5), mount=mount)
    rider.dim, rider.pos = NETHER, [12.5, 65.0, 12.5]
    w.tick(1)
    assert landed(a) == (OVER, want), landed(a)
    assert a.vehicle is None and rider.vehicle is None
    assert mount.dim == NETHER, "the mount must never be dragged across by the bounce"
    assert rider.dim == NETHER, "a badge holder riding a bounced player stays"


def scenario_routes_the_trigger_cannot_see(pack):
    """A respawn at an anchor, a login inside the Nether, a mod route that raises nothing: the sweep alone."""
    w = world(pack)
    a = w.player("ash", NETHER, (40.5, 120, -300.5))
    a.online = False
    w.tick(DOC["sweep"]["period_ticks"] * 2)
    assert a.dim == NETHER, "an offline player is in no selector"
    a.online = True
    w.tick(DOC["sweep"]["period_ticks"])
    assert landed(a) == (OVER, pallet_landing()), landed(a)
    roof = w.player("roof", NETHER, (5000.5, 300, 9000.5))          # above the roof, far out
    void = w.player("void", NETHER, (-900.5, -40, -900.5))          # fallen through the floor
    w.tick(DOC["sweep"]["period_ticks"])
    assert roof.dim == OVER and void.dim == OVER, (landed(roof), landed(void))


def scenario_operators_and_other_dimensions_are_untouched(pack):
    w = world(pack)
    c = w.player("op", NETHER, (0.5, 64, 0.5))
    c.gamemode = "creative"
    s = w.player("spec", NETHER, (1.5, 64, 0.5))
    s.gamemode = "spectator"
    adv = w.player("adv", NETHER, (2.5, 64, 0.5))
    adv.gamemode = "adventure"
    pocket = w.player("pocket", POCKET, (-768.5, 96, -770.5))
    end = w.player("end", "minecraft:the_end", (0.5, 64, 0.5))
    w.arrive(pocket, POCKET, (-768.5, 96, -770.5))
    w.tick(DOC["sweep"]["period_ticks"] * 2)
    assert c.dim == NETHER and s.dim == NETHER, "an operator in creative or spectator is never bounced"
    assert adv.dim == OVER, "adventure is a player's mode and is gated"
    assert pocket.dim == POCKET and not pocket.messages, "cobblers:pocket (the Entei rooms) is never gated"
    assert end.dim == "minecraft:the_end"


def scenario_the_entei_return_into_the_nether(pack, tmp_path):
    """The Entei's eject (its own generated function) returns its player from cobblers:pocket to the Nether block
    they ate the sigil in. A champion who holds gym8_cleared stays; a champion without it (an operator's grant) is
    sent to their checkpoint, not left in the Nether."""
    epack = tmp_path / "entei"
    EB.write(EB.build(EB.load()), epack)
    efns = {}
    for f in (epack / "data").rglob("*.mcfunction"):
        rel = f.relative_to(epack / "data").as_posix()
        ns, _, rest = rel.partition("/function/")
        efns["%s:%s" % (ns, rest[:-len(".mcfunction")])] = f.read_text(encoding="utf-8").splitlines()
    w = world(pack, extra=efns)
    w.objectives |= set(re.findall(r"^scoreboard objectives add (\S+)", "\n".join(efns["cobblers:entei_boss/load"]), re.M))
    a = w.player("ash", POCKET, (-767.5, 96, -771.5), advancements={FLAG, CHAMP})
    b = w.player("gary", POCKET, (-639.5, 96, -771.5), advancements={CHAMP})
    want, _n = at_checkpoint(w, b)
    for p in (a, b):
        for obj, v in (("eb.rx", 30), ("eb.ry", 70), ("eb.rz", 40), ("eb.slot", 0)):
            w.set(p.name, obj, v)
        w.as_player(p, "cobblers:entei_boss/eject")
        assert p.dim == NETHER, (p, "the Entei's eject must land in the Nether for this case to mean anything")
    w.tick(1)
    assert landed(a) == (NETHER, (30.5, 70.0, 40.5)), landed(a)
    assert landed(b) == (OVER, want), landed(b)


SCENARIOS = [scenario_portal_without_badge_goes_to_checkpoint, scenario_no_checkpoint_goes_to_the_pallet_on_ground,
             scenario_stale_checkpoint_goes_to_the_pallet, scenario_without_the_blackout_pack_the_net_still_sends_them_home,
             scenario_two_arrive_together, scenario_a_rider_is_dismounted_and_sent_home_without_the_mount,
             scenario_routes_the_trigger_cannot_see, scenario_operators_and_other_dimensions_are_untouched,
             scenario_the_entei_return_into_the_nether]


def _run(scenario, pack, tmp_path):
    if "tmp_path" in inspect.signature(scenario).parameters:
        return scenario(pack, tmp_path)
    return scenario(pack)


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    return gen(tmp_path_factory.mktemp("nether_gate"))


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s.__name__[len("scenario_"):] for s in SCENARIOS])
def test_scenario(scenario, pack, tmp_path):
    _run(scenario, pack, tmp_path)


# ------------------------------------------------------------------------------------------------- mutations
# The generator's source is copied and changed; data/nether_gate.json is untouched. Each scenario must then fail.

MUTATIONS = [
    ("the pallet sends them into the Nether", '"execute in %s run tp @s %d.5 %d %d.5" % (OVERWORLD,',
     '"execute in %s run tp @s %d.5 %d %d.5" % (NETHER,', scenario_no_checkpoint_goes_to_the_pallet_on_ground),
    ("the pallet lands two blocks high", "% (OVERWORLD, pal[0], pal[1], pal[2])",
     "% (OVERWORLD, pal[0], pal[1] + 2, pal[2])", scenario_no_checkpoint_goes_to_the_pallet_on_ground),
    ("the badge is not checked", ' + ["advancements={%s=false}" % flag])', ")",
     scenario_two_arrive_together),
    ("the net is gone", '"execute in %s positioned as @s as @a[tag=%s,distance=..1] run function %s" % (dim, tag, _fn("to_pallet")),',
     "", scenario_without_the_blackout_pack_the_net_still_sends_them_home),
    ("no dismount", '"ride @s dismount",', "", scenario_a_rider_is_dismounted_and_sent_home_without_the_mount),
    ("the sweep searches every dimension", "% (dim, _box(sweep_box(doc)), who, _fn(\"bounce\"))",
     "% (dim, \"tag=!x\", who, _fn(\"bounce\"))", scenario_operators_and_other_dimensions_are_untouched),
    ("the trigger does not revoke itself", '"advancement revoke @s only %s" % adv,', "",
     scenario_portal_without_badge_goes_to_checkpoint),
    ("the trigger teleports inside the change", '"schedule function %s 1t replace" % _fn("sweep")]',
     '"function %s" % _fn("sweep")]', scenario_portal_without_badge_goes_to_checkpoint),
    ("the keeper does not reschedule",
     '"function %s" % _fn("sweep"),\n        "schedule function %s %dt replace" % (_fn("keeper"), period)]',
     '"function %s" % _fn("sweep")]', scenario_routes_the_trigger_cannot_see),
]


def _mutated(tmp_path, old, new, tag):
    src = GEN_SRC.read_text(encoding="utf-8")
    assert src.count(old) == 1, "the mutation's anchor must occur exactly once: %r" % old
    root_line = "ROOT = Path(__file__).resolve().parent.parent"
    assert src.count(root_line) == 1
    src = src.replace(old, new).replace(root_line, "ROOT = Path(%r)" % str(ROOT))
    path = tmp_path / ("nether_gate_mut_%s.py" % tag)
    path.write_text(src, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("nether_gate_mut_%s" % tag, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("why,old,new,scenario", MUTATIONS, ids=[m[0].replace(" ", "_") for m in MUTATIONS])
def test_a_mutated_generator_fails_its_scenario(why, old, new, scenario, tmp_path):
    mod = _mutated(tmp_path, old, new, re.sub(r"\W", "_", why))
    mpack = gen(tmp_path, mod, "mut")        # every mutation here changes the OUTPUT, so the mutant must still build
    # a rider teleported without a dismount is refused by the model; every other mutant fails a scenario assertion
    with pytest.raises(P.Unsupported if why == "no dismount" else AssertionError):
        _run(scenario, mpack, tmp_path)


# ------------------------------------------------------------------------------------------------- data checks


def test_the_data_passes_and_the_pallet_stands_on_the_canonical_ground():
    assert nether_gate.problems(DOC, ground=_ground()) == []


@pytest.mark.parametrize("edit,needle", [
    (lambda d, b: d.__setitem__("gate_flag", "cobblers:flag/gym7_cleared"), "eighth badge"),
    (lambda d, b: d.__setitem__("dimension", POCKET), "dimension must be"),
    (lambda d, b: d["sweep"].__setitem__("box", {"corner": [-1024, 0, -1024], "size": [10240, 256, 10240]}), "sweep.box"),
    (lambda d, b: d["sweep"].__setitem__("period_ticks", 1200), "period_ticks"),
    (lambda d, b: d.__setitem__("exempt_gamemodes", ["creative", "adventure"]), "exempt_gamemodes"),
    (lambda d, b: d["trigger"]["criterion"]["conditions"].__setitem__("from", OVER), "trigger.criterion"),
    (lambda d, b: b["pallet"].__setitem__("position", [1461, 125, 5306]), "canonical ground"),
    (lambda d, b: b["pallet"].__setitem__("position", [-50, 70, 5306]), "bounds"),
])
def test_problems_refuse_a_gate_that_could_admit_or_trap(edit, needle):
    d, b = json.loads(json.dumps(DOC)), json.loads(json.dumps(BLACKOUT))
    edit(d, b)
    bad = nether_gate.problems(d, blackout=b, ground=_ground())
    assert any(needle in x for x in bad), bad
    with pytest.raises(nether_gate.GateError):
        nether_gate.build(d, blackout=b, ground=_ground())


def test_the_gate_flag_is_progressions_eighth_badge_not_a_new_one():
    prog = json.loads((ROOT / "data" / "progression.json").read_text(encoding="utf-8"))
    flag = next(f for f in prog["flags"] if f["id"] == "gym8_cleared")
    assert flag["set_by"]["kind"] == "trainer_defeat" and "kanto_giovanni" in flag["set_by"]["trainer_ids"]["kanto"]
    assert DOC["gate_flag"] == "%s:flag/%s" % (prog["namespace"], flag["id"])


# ------------------------------------------------------------------------------------------------- the pack


def _body(lines):
    return [l for l in lines if l.strip() and not l.startswith("#")]


def test_every_function_passes_function_limits_and_every_call_resolves(pack):
    fns = {f.stem: f.read_text(encoding="utf-8").splitlines()
           for f in (pack / "data" / "cobblers" / "function" / "nether_gate").glob("*.mcfunction")}
    assert set(fns) == {"load", "keeper", "sweep", "arrived", "bounce", "to_checkpoint", "to_pallet"}, set(fns)
    for n, lines in fns.items():
        assert function_limits.check_lines(lines, n) == [], n
        for ref in re.findall(r"\bfunction (\S+)", " ".join(_body(lines))):
            ok = ref.startswith("cobblers:nether_gate/") and ref.split("/", 1)[1] in fns
            assert ok or ref in BO_FNS, "%s calls %s, which neither pack defines" % (n, ref)
    load = json.loads((pack / "data" / "minecraft" / "tags" / "function" / "load.json").read_text(encoding="utf-8"))
    assert load == {"values": ["cobblers:nether_gate/load"]}
    assert not (pack / "data" / "minecraft" / "tags" / "function" / "tick.json").exists(), "no per-tick cost"


def test_the_period_cost_is_the_three_lines_the_data_states(pack):
    d = pack / "data" / "cobblers" / "function" / "nether_gate"
    n = sum(len(_body((d / ("%s.mcfunction" % f)).read_text(encoding="utf-8").splitlines())) for f in ("keeper", "sweep"))
    stated = int(re.match(r"period: (\d+) command lines every %d ticks" % DOC["sweep"]["period_ticks"], DOC["cost"]).group(1))
    assert n == stated == 3, (n, stated)


def test_pack_is_wired_into_reapply_and_prepare(monkeypatch):
    name = "cobblers_nether_gate"
    assert name in reapply.SERVER_PACKS and name in reapply.WORLD_LOCAL
    assert reapply.EXCLUDED.get(name, "").strip(), "%s must be EXCLUDED with a reason (it has no step)" % name
    assert reapply.PACKS / name == nether_gate.DEFAULT_OUT, "the tool writes where reapply installs from"
    jobs = reapply.prepare_jobs(types.SimpleNamespace(source_root="x", server_dir="x"))
    mine = [(n, f) for n, f in jobs if inspect.getclosurevars(f).nonlocals.get("tool") == "nether_gate.py"]
    assert len(mine) == 1, [n for n, _f in jobs]
    ran = []
    monkeypatch.setattr(reapply, "py", lambda *a, **k: ran.append(a))
    mine[0][1]()
    assert ran == [(reapply.TOOLS / "nether_gate.py",)], ran


def test_regeneration_leaves_no_stale_file(tmp_path):
    out = gen(tmp_path)
    stale = out / "data" / "cobblers" / "function" / "nether_gate" / "old.mcfunction"
    stale.write_text("say stale\n", encoding="utf-8")
    nether_gate.write(nether_gate.build(nether_gate.load()), out)
    assert not stale.exists()

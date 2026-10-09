"""The Rift's re-summoned entities through tools/chunk_look.py's look-then-act chain (N155, 2026-10-08): R9Z's guard
placeholders (tools/rift_zones.py), R9M's mine carts (tools/rift_mines.py), R1's trailhead placeholders and R1S's
portal sheets (tools/rift_skin.py).

A force-loaded chunk accepts a summon at once, but its SAVED entities arrive later, and two chunks' do not arrive
together. Each of these functions force-loaded, waited a fixed 40 or 60 ticks (or none) and then killed and summoned,
so a re-run whose saved entities came later killed nothing and doubled them. These sites lie far apart, so the chain
holds every site's chunk and one look requires an entity in EVERY site's chunk (all_shown), or acts blind after 300
ticks; the end de-duplicates, counts and releases.

The world is tests/test_markets_merchant_load.py's LateWorld with a delay per chunk and volume selectors
(dx/dy/dz). Every pack is built from synthetic sites, so no heightmap and no derived/ plan is needed: rift_skin's real
build needs derived/rift_sculpt, which cannot be rebuilt (docs/research/AGENT_WORKTREE_INPUTS.md).

Written by the implementer of the fix (minecraft-systems-dev); an independent test-author review is still owed
(CLAUDE.md principle 16).
"""
from __future__ import annotations

import json
import re
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import chunk_look as CL  # noqa: E402
import chunk_look_audit as CA  # noqa: E402
import mcfunction_sim as S  # noqa: E402
import rift_mines as RM  # noqa: E402
import rift_skin as SK  # noqa: E402
import rift_zones as RZ  # noqa: E402
from test_markets_merchant_load import LateWorld  # noqa: E402

TICKS = CL.STEP_TICKS + 5
NEAR, FAR = (1000, 1000), (1500, 1210)          # two sites in chunks 31 and 32 apart


def _chunk(x, z):
    return (int(x // 16), int(z // 16))


class Staggered(LateWorld):
    """LateWorld with each chunk's saved entities arriving after their own delay, and dx/dy/dz volume selectors."""

    def __init__(self, functions, delays, default=0):
        super().__init__(functions, default)
        self.delays = {_chunk(*xz): d for xz, d in delays.items()}

    def visible(self, e):
        if not getattr(e, "saved", False):
            return True
        at = self.forced_at.get(_chunk(e.pos[0], e.pos[2]))
        return at is not None and self.tick_no - at >= self.delays.get(_chunk(e.pos[0], e.pos[2]), self.delay)

    def select(self, sel, ctx, single=False):
        vol = dict(re.findall(r"\bd([xyz])=(-?\d+)", sel))
        if not vol:
            return super().select(sel, ctx, single)
        base = dict(re.findall(r"(?:\[|,)([xyz])=(-?[\d.]+)", sel))
        pool = super().select(re.sub(r",d[xyz]=-?\d+", "", sel), ctx, single)
        lo = [float(base[k]) for k in "xyz"]
        hi = [lo[i] + int(vol.get(k, 0)) + 1 for i, k in enumerate("xyz")]
        return [e for e in pool if all(lo[i] <= e.pos[i] < hi[i] for i in range(3))]


def _ns(prefix, fns):
    return {prefix + k: v for k, v in fns.items()}


def _run(fns, entry, saved, delays):
    w = Staggered(fns, delays)
    for e in saved:
        w.save(e)
    w.run(entry, TICKS)
    return w


def _write(tmp_path, fns):
    for ref, lines in fns.items():
        p = CA.pack_path(tmp_path, ref)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return tmp_path


def _at_once(monkeypatch):
    """The generator mutated: the entry runs the act in the tick it force-loads (no look)."""
    orig = CL.chain

    def at_once(base, *a, **k):
        fns = orig(base, *a, **k)
        fns[base] = fns[base] + ["function %s_act" % base]
        return fns
    monkeypatch.setattr(CL, "chain", at_once)


def _mutant(module, path, old, new):
    """A copy of a generator module with one line of its SOURCE changed (data untouched)."""
    src = (ROOT / "tools" / path).read_text(encoding="utf-8")
    assert src.count(old) == 1, old
    mod = types.ModuleType(module.__name__ + "_mutant")
    mod.__file__ = str(ROOT / "tools" / path)
    exec(compile(src.replace(old, new), mod.__file__, "exec"), mod.__dict__)
    return mod


# ============================================================================== R9Z: the guards' placeholders
GUARDS = [("z2", "G2", NEAR[0], 80, NEAR[1], '"G2 (placeholder)"'), ("z5", "G5", FAR[0], 90, FAR[1], '"G5 (placeholder)"')]
ZPRE = "cobblers:rift_zones/"


def _guards_old():
    """R9Z's guards as tools/rift_zones.py emitted them before 2026-10-08: force-load, 40 ticks, summon, 100 ticks on
    keep one per block."""
    new, f = "cobblers_rift_guard_new", ZPRE.rstrip("/")
    g = ["forceload add %d %d %d %d" % (x, z, x, z) for _n, _i, x, _y, z, _c in GUARDS]
    g.append("schedule function %s/guards_place 40t replace" % f)
    p = ["summon minecraft:armor_stand %d %d %d {Invulnerable:1b,NoGravity:1b,CustomNameVisible:1b,CustomName:'%s',"
         "Tags:[\"cobblers_rift_guard\",\"%s\",\"%s\"]}" % (x, y, z, c, n, new) for n, _i, x, y, z, c in GUARDS]
    p.append("schedule function %s/guards_done 100t replace" % f)
    d = ["execute if entity @e[type=minecraft:armor_stand,tag=%s,x=%d,y=%d,z=%d,dx=0,dy=1,dz=0] run kill "
         "@e[type=minecraft:armor_stand,tag=cobblers_rift_guard,tag=!%s,x=%d,y=%d,z=%d,dx=0,dy=1,dz=0]"
         % (new, x, y, z, new, x, y, z) for _n, _i, x, y, z, _c in GUARDS]
    d.append("tag @e[type=minecraft:armor_stand,tag=%s] remove %s" % (new, new))
    d += ["forceload remove %d %d %d %d" % (x, z, x, z) for _n, _i, x, _y, z, _c in GUARDS]
    return {f + "/guards": g, f + "/guards_place": p, f + "/guards_done": d}


def _guards_saved():
    return [S.Entity("minecraft:armor_stand", (x, y, z), tags=("cobblers_rift_guard", n)) for n, _i, x, y, z, _c in GUARDS]


def _stands(w):
    return len(w.living("minecraft:armor_stand", "cobblers_rift_guard"))


def test_guards_old_shape_doubles_the_late_guard():
    # Without it the fix has nothing to fix: the far guard's saved stand came after the 140-tick clean-up.
    w = _run(_guards_old(), ZPRE + "guards", _guards_saved(), {NEAR: 10, FAR: 200})
    assert _stands(w) == len(GUARDS) + 1


@pytest.mark.parametrize("late", [0, 60, 150, 200, 299, 350])
def test_guards_chain_leaves_one_per_guard_however_late_the_far_chunk(late):
    # Without it a re-run of R9Z doubles a guard whose chunk loads slower than another's.
    w = _run(_ns(ZPRE, RZ.guard_functions(GUARDS)), RZ.GUARDS_FN, _guards_saved(), {NEAR: 10, FAR: late})
    assert _stands(w) == len(GUARDS)
    assert sorted(t for e in w.living("minecraft:armor_stand", "cobblers_rift_guard") for t in e.tags
                  if t in ("z2", "z5")) == ["z2", "z5"]
    assert w.scores[("#" + RZ.GUARDS_HOLDER, CL.OBJ)] == len(GUARDS)
    assert not w.forced


def test_guards_first_run_acts_blind():
    # Without it a fresh export (no stands saved) would never get its placeholders.
    w = _run(_ns(ZPRE, RZ.guard_functions(GUARDS)), RZ.GUARDS_FN, [], {})
    assert [t for t, _e in w.logged("summon")][0] == CL.BLIND_TICKS and _stands(w) == len(GUARDS)


def test_guards_a_look_at_any_one_site_doubles_and_the_audit_names_it(tmp_path):
    # Without it the chain could act on the near guard's stand being seen and double the far one: the GENERATOR's
    # all_shown is mutated away, the guards untouched.
    mod = _mutant(RZ, "rift_zones.py", "note=\"tools/rift_zones.py\", all_shown=True)", "note=\"tools/rift_zones.py\")")
    fns = _ns(ZPRE, mod.guard_functions(GUARDS))
    assert _stands(_run(fns, RZ.GUARDS_FN, _guards_saved(), {NEAR: 10, FAR: 200})) == len(GUARDS) + 1
    sites = [(x, z) for _n, _i, x, _y, z, _c in GUARDS]
    probs = CA.problems(_write(tmp_path, fns), RZ.GUARDS_FN, "cobblers_rift_guard", sites=sites)
    assert any("no one look requires an entity in every site's chunk" in p for p in probs), probs


def test_guards_dropping_the_look_doubles_and_the_audit_names_it(tmp_path, monkeypatch):
    _at_once(monkeypatch)
    fns = _ns(ZPRE, RZ.guard_functions(GUARDS))
    assert _stands(_run(fns, RZ.GUARDS_FN, _guards_saved(), {NEAR: 150, FAR: 150})) == 2 * len(GUARDS)
    assert any("in the tick it force-loads" in p for p in CA.problems(_write(tmp_path, fns), RZ.GUARDS_FN,
                                                                     "cobblers_rift_guard"))


def test_guards_chain_passes_the_audit(tmp_path):
    fns = _ns(ZPRE, RZ.guard_functions(GUARDS))
    sites = [(x, z) for _n, _i, x, _y, z, _c in GUARDS]
    assert CA.problems(_write(tmp_path, fns), RZ.GUARDS_FN, "cobblers_rift_guard", sites=sites) == []


# ============================================================================== R9M: the mine carts
CARTS = [(NEAR[0], 70, NEAR[1]), (NEAR[0] + 3, 70, NEAR[1]), (FAR[0], 75, FAR[1])]
MPRE = "cobblers:rift_mines/"


def _carts_m():
    return types.SimpleNamespace(spec={"town": {"carts": [[x, z] for x, _y, z in CARTS]}},
                                 fit={(x, y, z): "minecraft:rail" for x, y, z in CARTS})


def _carts_old():
    """R9M's carts as tools/rift_mines.py emitted them before 2026-10-08: force-load, 60 ticks, kill, summon."""
    chunks = sorted({(x >> 4, z >> 4) for x, _y, z in CARTS})
    head = ["forceload add %d %d" % (cx * 16, cz * 16) for cx, cz in chunks]
    head.append("schedule function %scarts_go 60t replace" % MPRE)
    go = ["kill @e[type=minecraft:minecart,tag=%s]" % RM.TAG]
    go += ["summon minecraft:minecart %.1f %d %.1f {Tags:[\"%s\"],Invulnerable:1b}" % (x + 0.5, y, z + 0.5, RM.TAG)
           for x, y, z in CARTS]
    go += ["forceload remove %d %d" % (cx * 16, cz * 16) for cx, cz in chunks]
    return {MPRE + "carts": head, MPRE + "carts_go": go}


def _carts_saved():
    return [S.Entity("minecraft:minecart", (x + 0.5, y, z + 0.5), tags=(RM.TAG,)) for x, y, z in CARTS]


def _carts(w):
    return len(w.living("minecraft:minecart", RM.TAG))


def test_carts_old_shape_doubles_the_late_carts():
    w = _run(_carts_old(), RM.CARTS_FN, _carts_saved(), {NEAR: 10, FAR: 100})
    assert _carts(w) == len(CARTS) + 1


@pytest.mark.parametrize("late", [0, 100, 200, 299, 350])
def test_carts_chain_leaves_one_per_cart_however_late_the_far_chunk(late):
    fns, carts = RM.cart_files(_carts_m())
    w = _run(_ns(MPRE, fns), RM.CARTS_FN, _carts_saved(), {NEAR: 10, FAR: late})
    assert _carts(w) == len(CARTS) == len(carts)
    assert w.scores[("#" + RM.CARTS_HOLDER, CL.OBJ)] == len(CARTS)
    assert not w.forced


def test_carts_audit_passes_the_chain_and_names_a_look_at_any_one_chunk(tmp_path):
    # rift_mines_audit's carts check reads the chain's text and the data's cart columns, never the generator
    import rift_mines_audit as RA
    spec = _carts_m().spec
    assert RA.cart_problems(spec, _write(tmp_path / "ok", _ns(MPRE, RM.cart_files(_carts_m())[0]))) == []
    mod = _mutant(RM, "rift_mines.py", "note=\"tools/rift_mines.py\",\n                   all_shown=True)",
                  "note=\"tools/rift_mines.py\")")
    fns = _ns(MPRE, mod.cart_files(_carts_m())[0])
    assert _carts(_run(fns, RM.CARTS_FN, _carts_saved(), {NEAR: 10, FAR: 200})) == len(CARTS) + 1
    probs = RA.cart_problems(spec, _write(tmp_path / "any", fns))
    assert any("no one look requires" in p for p in probs), probs


def test_carts_dropping_the_look_doubles_and_the_audit_names_it(tmp_path, monkeypatch):
    import rift_mines_audit as RA
    _at_once(monkeypatch)
    fns = _ns(MPRE, RM.cart_files(_carts_m())[0])
    assert _carts(_run(fns, RM.CARTS_FN, _carts_saved(), {NEAR: 150, FAR: 150})) == 2 * len(CARTS)
    assert any("in the tick it force-loads" in p for p in RA.cart_problems(_carts_m().spec, _write(tmp_path, fns)))


def test_carts_audit_names_a_cart_the_data_has_and_the_chain_does_not(tmp_path):
    import rift_mines_audit as RA
    spec = {"town": {"carts": [[x, z] for x, _y, z in CARTS] + [[FAR[0] + 5, FAR[1]]]}}
    probs = RA.cart_problems(spec, _write(tmp_path, _ns(MPRE, RM.cart_files(_carts_m())[0])))
    assert any("the data's carts are at" in p for p in probs), probs


# ============================================================================== R1 / R1S: the Rift's skin entities
RPRE = "cobblers:rift/"
FX = ['summon minecraft:armor_stand %.1f %d %.1f {CustomName:\'"Rift guard (placeholder)"\',CustomNameVisible:1b,'
      'NoGravity:1b,Invulnerable:1b,Tags:["rift_fx","rift_fx_all"]}' % (x + 0.5, 80, z + 0.5) for x, z in (NEAR, FAR)]
PS = {"tag": "rift_fx", "sheet_tag": "rift_sheet"}
SHEETS = ['summon minecraft:block_display %.1f %d %.1f {block_state:{Name:"minecraft:nether_portal",Properties:'
          '{axis:"x"}},Tags:["rift_fx","rift_sheet"]}' % (x + 0.5, 100, z + 0.5) for x, z in (NEAR, FAR)]
OLD_SLOT = (NEAR[0] + 40, NEAR[1])
SHEET_LINES = ["fill %d 100 %d %d 100 %d minecraft:stone replace minecraft:air" % (OLD_SLOT + OLD_SLOT)]


def _fx_saved():
    return [S.Entity("minecraft:armor_stand", (x + 0.5, 80, z + 0.5), tags=("rift_fx", "rift_fx_all")) for x, z in (NEAR, FAR)]


def _fx(w):
    return len(w.living("minecraft:armor_stand", "rift_fx_all"))


def _fx_old():
    """R1's fx as tools/rift_skin.py emitted it before 2026-10-08: force-load, 60 ticks, kill by tag, summon, count."""
    boxes = sorted({(x >> 4 << 4, z >> 4 << 4) for x, z in (NEAR, FAR)})
    fx = ["forceload add %d %d %d %d" % (bx - 16, bz - 16, bx + 31, bz + 31) for bx, bz in boxes]
    fx.append("schedule function %sfx_go 60t replace" % RPRE)
    go = ["kill @e[tag=rift_fx_all]"] + FX + ["forceload remove %d %d %d %d" % (bx - 16, bz - 16, bx + 31, bz + 31)
                                             for bx, bz in boxes]
    return {RPRE + "fx": fx, RPRE + "fx_go": go}


def test_fx_old_shape_doubles_the_late_trailhead():
    assert _fx(_run(_fx_old(), SK.FX_FN, _fx_saved(), {NEAR: 10, FAR: 100})) == len(FX) + 1


@pytest.mark.parametrize("late", [0, 100, 200, 299, 350])
def test_fx_chain_leaves_one_per_trailhead_however_late_the_far_chunk(late):
    w = _run(_ns(RPRE, SK.fx_functions(FX)), SK.FX_FN, _fx_saved(), {NEAR: 10, FAR: late})
    assert _fx(w) == len(FX)
    assert w.scores[("#" + SK.FX_HOLDER, CL.OBJ)] == len(FX)
    assert not w.forced


def test_fx_a_look_at_any_one_site_or_none_is_named_by_the_audit(tmp_path, monkeypatch):
    sites = [(x + 0.5, z + 0.5) for x, z in (NEAR, FAR)]
    assert CA.problems(_write(tmp_path / "ok", _ns(RPRE, SK.fx_functions(FX))), SK.FX_FN, SK.FX_TAG, sites=sites) == []
    mod = _mutant(SK, "rift_skin.py", "act, [\"tag=%s\" % FX_TAG], new, \"tag=%s\" % FX_TAG, FX_HOLDER, "
                                      "note=\"tools/rift_skin.py\",\n                         all_shown=True))",
                  "act, [\"tag=%s\" % FX_TAG], new, \"tag=%s\" % FX_TAG, FX_HOLDER, note=\"tools/rift_skin.py\"))")
    fns = _ns(RPRE, mod.fx_functions(FX))
    assert _fx(_run(fns, SK.FX_FN, _fx_saved(), {NEAR: 10, FAR: 200})) == len(FX) + 1
    assert any("no one look requires" in p for p in CA.problems(_write(tmp_path / "any", fns), SK.FX_FN, SK.FX_TAG,
                                                                sites=sites))
    _at_once(monkeypatch)
    fns = _ns(RPRE, SK.fx_functions(FX))
    assert _fx(_run(fns, SK.FX_FN, _fx_saved(), {NEAR: 150, FAR: 150})) == 2 * len(FX)
    assert any("in the tick it force-loads" in p
               for p in CA.problems(_write(tmp_path / "now", fns), SK.FX_FN, SK.FX_TAG, sites=sites))


def _sheets_saved():
    return ([S.Entity("minecraft:block_display", (x + 0.5, 100, z + 0.5), tags=("rift_fx", "rift_sheet"))
             for x, z in (NEAR, FAR)]
            + [S.Entity("minecraft:block_display", (OLD_SLOT[0] + 0.5, 100, OLD_SLOT[1] + 0.5),
                        tags=("rift_fx", "rift_fx_all"))])


def _sheets(w):
    return len(w.living("minecraft:block_display", "rift_fx"))


def _sheet_fns(mod=SK):
    return _ns(RPRE, mod.sheet_functions(SHEET_LINES, SHEETS, list((NEAR, FAR, OLD_SLOT)), PS))


@pytest.mark.parametrize("late", [0, 100, 200, 299, 350])
def test_sheets_chain_leaves_one_per_sheet_and_no_old_slot_sheet(late):
    # the pre-2026-10-05 sheet in an old slot goes too, by the act's kill or, if it came late, the end's
    w = _run(_sheet_fns(), SK.SHEETS_FN, _sheets_saved(), {NEAR: 10, FAR: late, OLD_SLOT: late})
    assert _sheets(w) == len(SHEETS)
    assert not w.living("minecraft:block_display", "rift_fx_all")
    assert w.scores[("#" + SK.SHEETS_HOLDER, CL.OBJ)] == len(SHEETS)
    assert w.logged("fill") and not w.errors and not w.forced


def test_sheets_audit_passes_and_names_a_dropped_look(tmp_path, monkeypatch):
    sites = [(x + 0.5, z + 0.5) for x, z in (NEAR, FAR)]
    assert CA.problems(_write(tmp_path / "ok", _sheet_fns()), SK.SHEETS_FN, PS["tag"], sites=sites) == []
    _at_once(monkeypatch)
    fns = _sheet_fns()
    assert _sheets(_run(fns, SK.SHEETS_FN, _sheets_saved(), {NEAR: 150, FAR: 150, OLD_SLOT: 150})) > len(SHEETS)
    assert any("in the tick it force-loads" in p
               for p in CA.problems(_write(tmp_path / "now", fns), SK.SHEETS_FN, PS["tag"], sites=sites))


def test_sheets_block_lines_outside_the_held_boxes_fail_the_build():
    # Without it the seal and carve could land on an unloaded chunk inside the chain's act and do nothing
    with pytest.raises(SK.SkinError):
        SK.sheet_functions(["fill 9000 100 9000 9000 100 9000 minecraft:stone"], SHEETS, [NEAR, FAR], PS)


# ============================================================================== the reapply steps
def _step_block(src, sid, nxt):
    return src[src.index('("%s"' % sid):src.index('("%s"' % nxt)]


def test_the_steps_wait_for_the_whole_chain_and_read_its_count():
    # Without it a step reads the count before the chain ends (-1), or a step-level forceload remove releases the
    # chunks under it. reapply.steps() itself needs build/ (every pack's index), so the four steps are read from the
    # source here and their chain actions from the generators that supply them.
    spec = json.loads((ROOT / "data" / "rift_mines.json").read_text(encoding="utf-8"))
    assert RM.cart_steps(spec) == [("fn", RM.CARTS_FN), ("wait", CL.STEP_SECONDS),
                                   ("check", ("chunk_look", RM.CARTS_HOLDER, len(spec["town"]["carts"]),
                                              "the Rift dig camp's mine carts"))]
    zspec = json.loads((ROOT / "data" / "rift_zones.json").read_text(encoding="utf-8"))
    assert RZ.guard_count(zspec) > 0
    assert RZ.guard_steps(zspec) == [("fn", RZ.GUARDS_FN), ("wait", CL.STEP_SECONDS),
                                     ("check", ("chunk_look", RZ.GUARDS_HOLDER, RZ.guard_count(zspec),
                                                "the Rift's guard placeholders"))]
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    r1, r1s = _step_block(src, "R1", "R1L"), _step_block(src, "R1S", "R2")
    assert '("fn", "cobblers:rift/fx"), ("wait", chunk_look.STEP_SECONDS), ("check", "rift_fx")' in r1
    assert '("fn", "cobblers:rift/sheets"), ("wait", chunk_look.STEP_SECONDS), ("check", "rift_sheets")' in r1s
    r9m = _step_block(src, "R9M", "R9S")
    r9z = src[src.index('out.append(("R9Z"'):src.index("RZ.guard_steps(zspec)") + 30]
    assert "rift_mines.cart_steps()" in r9m and '"cobblers:rift_mines/carts"' not in r9m
    assert "RZ.guard_steps(zspec)" in r9z and '"cobblers:rift_zones/guards"' not in r9z
    for block in (r1, r1s, r9m, r9z):
        assert '("cmd"' not in block, "a step-level command could release the chain's chunks"
    assert "scoreboard players get #%s %s" % (SK.FX_HOLDER, CL.OBJ) in src
    assert "scoreboard players get #%s %s" % (SK.SHEETS_HOLDER, CL.OBJ) in src

"""Each of new_player_walk.py's Champion-leg checks bites: break the GENERATOR, leave data/ alone, and the check FAILs.

CLAUDE.md "How to prove an audit is independent": a mutation of the record moves the expectation and the output
together and proves nothing. Every test here builds the packs from committed data with the real generators
(W.build_from_data), asserts the check PASSes on that baseline, then rebuilds ONE pack with one line of its generator
changed -- data/ untouched -- and asserts the same check now FAILs and names the cause.

  generator                    mutation                                         check that must FAIL
  rift_zones.cmd_build         no qualify-on-entry line (the pre-2026-10-04 form) victory_road zone_admits:<fights 8-10>
  rift_zones.zone_masks        z4|z5 split 200 south (z4 released and kept       league zones_over_league
                               enforced; built past report 8c, which refuses it)
  route_trainers.cycle_lines   never seats route_09_trainer_08                   victory_road seated:route_09_trainer_08
  progression_pack             a defeat flag binds no trainer                    league champion_flag, victory_road gate_opens
  progression_pack.files       the crisis flag's grant line commented out        victory_road flag_emitted:rift_crisis_resolved
  place_donor.commands         the League placed unrotated                       league league_placed
  compile_spawns.compile_route no level on any route entry                       gym_1 cap_reachable

Needs the canonical heightmap (rift_zones and gym_buildings build from it, and the walks read it); SKIPS without it.
The fights are not run (battles=False): what is mutated here is never a team.

NOT COVERED: that the server runs any of these files; that the checks find every way each generator could break
(one mutation each, chosen as the failure that has happened or nearly has).
"""
from __future__ import annotations

import inspect
import shutil
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import new_player_walk as W  # noqa: E402

TOWNS = {"cobblers_towns": "not built from data (kits/)"}


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    d = tmp_path_factory.mktemp("base_packs")
    unbuilt = W.build_from_data(d)
    if set(unbuilt) - set(TOWNS):
        pytest.skip("committed data does not build here: %s" % unbuilt)
    return d


@pytest.fixture(scope="module")
def ground(base):
    try:
        return W.Inputs(packs=base).ground
    except (Exception, SystemExit) as e:
        pytest.skip("no canonical heightmap here: %s" % e)


def walker(packs, ground):
    return W.Walker(W.Inputs(packs=packs, ground=ground, battles=False, unbuilt=TOWNS))


def copy(base, tmp_path):
    p = tmp_path / "packs"
    shutil.copytree(base, p)
    return p


def mutated(module, fname, old, new, **over):
    """`module.fname` recompiled with `old` replaced by `new` in its source, in a copy of the module's globals."""
    src = textwrap.dedent(inspect.getsource(getattr(module, fname)))
    assert src.count(old) == 1, "the mutation no longer matches %s.%s: re-aim it" % (module.__name__, fname)
    g = dict(vars(module))
    g.update(over)
    exec(compile(src.replace(old, new), "<mutated %s.%s>" % (module.__name__, fname), "exec"), g)
    return g[fname]


def verdicts(st, prefix):
    return {c["check"]: c["verdict"] for c in st.checks if c["check"].startswith(prefix)}


def held_all(w):
    return w.held_after(W.GYM_COUNT) | {W.CRISIS_FLAG}


def test_fights_8_to_10_fail_when_rift_zones_admits_only_at_the_knock(base, ground, tmp_path, capsys):
    # without this, the P0 of CRITICAL_PATH_WALK_2 item 1 -- a flag holder turned back underground in z5 -- returns
    # unseen the day the generator loses its qualify-on-entry line
    import argparse
    import rift_zones
    st = W.Stage("v", "v")
    w = walker(base, ground)
    w.vr_stands(st, held_all(w))
    assert set(verdicts(st, "zone_admits:").values()) == {"PASS"}
    p = copy(base, tmp_path)
    old = 'testable = p["kind"] in ("badges", "flag") and bool(p.get("advancements"))'
    mutated(rift_zones, "cmd_build", old, "testable = False", PACKS=p)(argparse.Namespace(source_root=None))
    st = W.Stage("v", "v")
    w = walker(p, ground)
    w.vr_stands(st, held_all(w))
    bad = sorted(k for k, v in verdicts(st, "zone_admits:").items() if v == "FAIL")
    assert bad == ["zone_admits:route_09_trainer_%02d" % n for n in (8, 9, 10)]
    assert "only its knock box" in next(c for c in st.checks if c["check"] == bad[0])["evidence"]["summary"]


def rift_zones_into(packs, spec_copy, old=None, new=None):
    """tools/rift_zones.py recompiled with SPEC on a scratch copy of data/rift_zones.json (trace rewrites its spec) and
    PACKS on `packs`, z4 released (held_zones holds nothing) and, if given, `old` replaced by `new` in its source."""
    import rift_zones
    src = Path(rift_zones.__file__).read_text(encoding="utf-8")
    edits = [('SPEC = ROOT / "data" / "rift_zones.json"', 'SPEC = Path(r"%s")' % spec_copy),
             ('PACKS = ROOT / "build" / "datapacks"', 'PACKS = Path(r"%s")' % packs)]
    if old is not None:
        edits.append((old, new))
    for a, b in edits:
        assert src.count(a) == 1, "the mutation no longer matches tools/rift_zones.py: re-aim it (%r)" % a
        src = src.replace(a, b)
    shutil.copy(ROOT / "data" / "rift_zones.json", spec_copy)
    g = {"__name__": "rift_zones_mutated", "__file__": rift_zones.__file__}
    exec(compile(src, "<mutated rift_zones>", "exec"), g)
    g["held_zones"] = lambda spec: {}
    return g


def test_the_league_fails_when_rift_zones_traces_z4_over_it(base, ground, tmp_path, capsys):
    # without this, the blocker of CRITICAL_PATH_WALK_2 item 4 -- the League inside z4, gated on 120 species -- could
    # come back through the generator (fixed in data by fdbe1e5) and the walk would not see it the day z4 is released
    import argparse
    st = walker(base, ground).league_stage()
    assert verdicts(st, "zones_over_league")["zones_over_league"] == "PASS"
    # z4 released and ENFORCED, generator as committed: the League is not under it (the premise fdbe1e5 fixed)
    p = copy(base, tmp_path)
    rz = rift_zones_into(p, tmp_path / "spec_as_built.json")
    rz["cmd_build"](argparse.Namespace(source_root=None))
    assert verdicts(walker(p, ground).league_stage(), "zones_over_league")["zones_over_league"] == "PASS"
    # the GENERATOR's split of the two zones on behind_league moved 200 blocks south, to where the cut stood until
    # fdbe1e5 (z2560); data/ untouched. `report` 8c refuses the result, so the build is run past it: what is tested is
    # the walk's own check, not the gate in front of it
    old = '        masks[less] = both & (idx < c["at"])\n        masks[ge] = both & (idx >= c["at"])'
    new = '        masks[less] = both & (idx < c["at"] + 200)\n        masks[ge] = both & (idx >= c["at"] + 200)'
    q = tmp_path / "mutated"
    shutil.copytree(base, q)
    rz = rift_zones_into(q, tmp_path / "spec_mutated.json", old, new)
    rz["cmd_trace"](argparse.Namespace(source_root=None))
    rz["cmd_report"] = lambda a, quiet=False: 0
    # with the split moved, G4 (data: z2357) stands 200 blocks inside z4 and unreachable_zones ships z4 OPEN, the
    # owner's fail-open rule of 2026-10-03 -- measured: built that way the check PASSES, correctly, as nothing is
    # enforced. z4 is kept enforced here, as if its guard had been re-sited to the moved edge, exactly as held_zones
    # is emptied above
    real_unreachable = rz["unreachable_zones"]
    rz["unreachable_zones"] = lambda spec: {k: v for k, v in real_unreachable(spec).items() if k != "z4"}
    rz["cmd_build"](argparse.Namespace(source_root=None))
    c = next(c for c in walker(q, ground).league_stage().checks if c["check"] == "zones_over_league")
    assert c["verdict"] == "FAIL" and "z4" in c["evidence"], c


def test_a_stand_fails_when_route_trainers_stops_seating_it(base, ground, tmp_path, monkeypatch, capsys):
    # without this, a Victory Road trainer the cycle never seats (no fight, no hold-off) would pass on its roster
    import route_trainers
    p = copy(base, tmp_path)
    real = route_trainers.cycle_lines
    monkeypatch.setattr(route_trainers, "cycle_lines",
                        lambda tid, *a, **k: [] if tid == "route_09_trainer_08" else real(tid, *a, **k))
    shutil.rmtree(p / "cobblers_trainers")
    assert route_trainers.main(["--out", str(p / "cobblers_trainers")]) in (0, None)
    st = W.Stage("v", "v")
    w = walker(p, ground)
    w.vr_stands(st, held_all(w))
    bad = sorted(k for k, v in verdicts(st, "seated:").items() if v == "FAIL")
    assert bad == ["seated:route_09_trainer_08"]


def test_champion_and_the_badge_gate_fail_when_progression_pack_binds_no_trainer(base, ground, tmp_path, monkeypatch,
                                                                                 capsys):
    # without this, a progression pack whose defeat flags never fire would leave the Champion's flag and the eight
    # badges Victory Road's gate needs reading as emitted
    import progression_pack
    w = walker(base, ground)
    line = [tuple(x) for x in w.paths["victory_road"]]
    st = W.Stage("v", "v")
    w.gate_check(st, line, w.held_after(W.GYM_COUNT))
    assert st.checks[0]["verdict"] == "PASS"
    p = copy(base, tmp_path)
    old = '"conditions": {"trainer_ids": flag["trainer_ids"], "count": 1}'
    monkeypatch.setattr(progression_pack, "_flag_advancement",
                        mutated(progression_pack, "_flag_advancement", old, '"conditions": {"trainer_ids": [], "count": 1}'))
    shutil.rmtree(p / "cobblers_progression")
    assert progression_pack.main(["--out", str(p / "cobblers_progression")]) == 0
    w = walker(p, ground)
    st = W.Stage("v", "v")
    w.gate_check(st, line, w.held_after(W.GYM_COUNT))
    assert st.checks[0]["verdict"] == "FAIL" and "z2" in st.checks[0]["evidence"]["summary"]
    tid, _adv = W.flag_trainer(p, W.CHAMPION_FLAG)
    assert tid is None
    assert verdicts(w.league_stage(), "champion_flag")["champion_flag"] == "FAIL"


def test_the_crisis_flag_fails_when_progression_pack_comments_out_its_grant(base, ground, tmp_path, monkeypatch,
                                                                            capsys):
    # without this, the one flag that opens the League's precinct could be granted by a line that does nothing
    import progression_pack
    st = W.Stage("v", "v")
    assert walker(base, ground).crisis_flag(st) is True
    p = copy(base, tmp_path)
    old = '"advancement grant @s only %s:flag/%s" % (ns, flag["id"])'
    monkeypatch.setattr(progression_pack, "files",
                        mutated(progression_pack, "files", old, '"# advancement grant @s only %s:flag/%s" % (ns, flag["id"])'))
    shutil.rmtree(p / "cobblers_progression")
    assert progression_pack.main(["--out", str(p / "cobblers_progression")]) == 0
    st = W.Stage("v", "v")
    assert walker(p, ground).crisis_flag(st) is False
    assert verdicts(st, "flag_emitted:")["flag_emitted:rift_crisis_resolved"] == "FAIL"


def test_the_league_fails_when_place_donor_drops_its_rotation(base, ground, tmp_path, monkeypatch, capsys):
    # without this, the League placed unrotated -- 120 blocks off its lot, its entrance facing the wrong way -- would
    # pass, and every zone and walk check after it would be measured on the wrong footprint
    import place_donor
    assert verdicts(walker(base, ground).league_stage(), "league_placed")["league_placed"] == "PASS"
    p = copy(base, tmp_path)
    old = 'rec.get("rotation", "none"), rec.get("mirror", "none"))]'
    monkeypatch.setattr(place_donor, "commands",
                        mutated(place_donor, "commands", old, '"none", rec.get("mirror", "none"))]'))
    shutil.rmtree(p / "cobblers_donor")
    W.donor_pack(p / "cobblers_donor")
    c = next(c for c in walker(p, ground).league_stage().checks if c["check"] == "league_placed")
    assert c["verdict"] == "FAIL" and "data/placements.json says" in c["evidence"]


def test_cap_reachable_fails_when_compile_spawns_emits_no_levels(base, ground, tmp_path, monkeypatch, capsys):
    # without this, a spawn pack whose route entries carry no level -- nothing to catch or grind on -- would leave
    # the cap a fight assumes standing unexamined
    import compile_spawns
    st = walker(base, ground).gym_stage(1)
    assert verdicts(st, "cap_reachable")["cap_reachable"] != "FAIL"
    p = copy(base, tmp_path)
    monkeypatch.setattr(compile_spawns, "compile_route",
                        mutated(compile_spawns, "compile_route", '"level": e["level"],', '"level": None,'))
    shutil.rmtree(p / "cobblers_spawns")
    assert compile_spawns.main(["--out", str(p / "cobblers_spawns")]) in (0, None)
    c = next(c for c in walker(p, ground).gym_stage(1).checks if c["check"] == "cap_reachable")
    assert c["verdict"] == "FAIL" and "no compiled wild pool" in c["evidence"]

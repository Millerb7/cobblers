"""The legendary sanctuaries S2-S6 and the retired caves K1-K6 (tools/sanctuaries.py, tools/sanctuaries_audit.py,
data/sanctuaries.json). The keeper tests run once per area boss (Miraidon, Dialga, Koraidon) through the `boss_ctx` fixture.

Written by the same session that wrote the generator and the audit (the brief of 2026-10-12 asked one unit for both; CLAUDE.md
principle 16 wants different agents, so a second agent should grade this file). What keeps it from being a mirror of the generator:

  the build     the committed pack passes the audit, which imports nothing of the generator: it replays the pack's text over the
                heightmap and walks it on foot; and each GENERATOR mutation (a seal cell left out, a lantern off its post, a block
                left floating, a steep band, a keeper that forgets the guardian, a door box off by a block, a restore that skips a
                column or forgets the players, a build that does not refuse) makes it fail a NAMED check with data/sanctuaries.json
                untouched. The few record edits here test the loader, not independence.
  the keeper    the generated functions RUN on tests/gulch_sim.py's world model (the cave kit's harness, moved): nothing spawns for a
                player without the flag, in front of anyone or for nobody; one dormant alpha at the court's centre for a champion;
                24,000 ticks after a faint and 72,000 after a catch; a guardian is never held, woken, settled or killed (C25).
  the gate      the barrier door opens for a flagged player in the forecourt, never for another, and never closes on anyone inside.
  the restore   it refuses while a player stands in a retired cave's void and runs once; the audit replays it over the cave as applied.
  the wiring    the step's order (after R9CK, before R9E), the pack lists and the prepare jobs in tools/reapply.py.
"""
from __future__ import annotations

import copy
import functools
import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import gulch_sim as GS  # noqa: E402
import nbt_sim as N  # noqa: E402
import sanctuaries as S  # noqa: E402
import sanctuaries_audit as A  # noqa: E402

SPEC = json.loads((ROOT / "data" / "sanctuaries.json").read_text(encoding="utf-8"))
SANS = {s["id"]: s for s in SPEC["sanctuaries"]}
BOSSES = [s for s in SPEC["sanctuaries"] if s["occupant"]["mode"] == "area_boss"]
BOSS_IDS = [s["id"] for s in BOSSES]
OBJ = SPEC["gate"]["objective"]
CHAMPION = "cobblers:flag/champion_cleared"
GYM6 = "cobblers:flag/gym6_cleared"
GYM8 = "cobblers:flag/gym8_cleared"
GATED = [("sanctuary_singing_hollow", GYM6), ("sanctuary_tide_shrine", GYM8), ("sanctuary_broken_relay", CHAMPION),
         ("sanctuary_stopped_clock", CHAMPION), ("sanctuary_sunscar", CHAMPION)]


def _ground():
    import ground as G
    import terrain as T
    try:
        return G.Ground(os.environ.get("COBBLERS_SOURCE_ROOT"))
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)


@functools.lru_cache(maxsize=None)
def _raw_ground():
    return _ground()


@pytest.fixture(scope="module")
def ground():
    return A.cached(_raw_ground())


def make_pack(g, spec=None):
    """(fns, callback, plan, retired) of the pack the generator makes from the committed record: geometry only, no clearance inputs."""
    spec = spec or SPEC
    S._COMPOSED.clear()
    plan = [{"san": s, "geometry": S.geometry(spec, s, g)} for s in spec["sanctuaries"]]
    retired = [{"rc": rc, "geometry": S.retired_cells(rc, g)} for rc in spec["retired_caves"]]
    files = S.pack_files(spec, plan, retired, g)
    pre = "data/cobblers/function/sanctuaries/"
    fns = {k[len(pre):-len(".mcfunction")]: v.splitlines() for k, v in files.items() if k.endswith(".mcfunction")}
    return fns, files.get("data/cobblemon/callbacks/pokemon_captured/cobblers_sanctuaries.molang", ""), plan, retired


@functools.lru_cache(maxsize=None)
def _pack_cached():
    return make_pack(_raw_ground())


@pytest.fixture(scope="module")
def pack(ground):
    return _pack_cached()


def audit(g, fns, cb, **kw):
    probs, _n = A.audit(SPEC, fns, cb, g, **kw)
    return probs


# ------------------------------------------------------------------ the record

def test_the_committed_record_is_valid():
    # without it a sanctuary with a gate no flag opens, a boss with a pool, or a court level over its gate's cap reaches the builder
    assert S.static_problems(SPEC) == []


def test_the_five_sanctuaries_carry_the_five_legendary_homes_and_k1_has_none():
    # the owner's decision (2026-10-12): K1's Gible goes; K2-K6's legendaries stay, each in an open-air sanctuary of its own
    occ = {s["id"]: (s["occupant"]["mode"], s["occupant"]["species"], tuple(s["occupant"].get("co_occupants") or ())) for s in SPEC["sanctuaries"]}
    assert occ == {"sanctuary_singing_hollow": ("rare_spawn", "meloetta", ()), "sanctuary_broken_relay": ("area_boss", "miraidon", ()),
                   "sanctuary_tide_shrine": ("rare_spawn", "tapufini", ("nihilego",)), "sanctuary_stopped_clock": ("area_boss", "dialga", ()),
                   "sanctuary_sunscar": ("area_boss", "koraidon", ())}
    assert len({s["style"] for s in SPEC["sanctuaries"]}) == 5
    ret = {rc["cave"]["kind"]: rc.get("successor") for rc in SPEC["retired_caves"]}
    assert ret == {"K1": None, "K2": "sanctuary_singing_hollow", "K3": "sanctuary_broken_relay", "K4": "sanctuary_tide_shrine",
                   "K5": "sanctuary_stopped_clock", "K6": "sanctuary_sunscar"}


def test_no_non_legendary_power_line_keeps_a_home_in_a_sanctuary():
    # "we don't need the non-legendaries": no antechamber pool survives, a boss sanctuary has no pool, and Gible's line has no wild home
    sp = json.loads((ROOT / "data" / "spawns.json").read_text(encoding="utf-8"))
    pools = {h["pool"]["id"] for s in SPEC["sanctuaries"] for h in s.get("habitat") or []}
    assert pools == {"sanctuary_singing_hollow_court", "sanctuary_tide_shrine_court"}
    assert not [e for e in sp["entries"] if e["species"] in ("gible", "beldum", "honedge", "munchlax", "torkoal") and
                (str(e.get("scope")).startswith("cave_") or str(e.get("scope")).startswith("sanctuary_"))]
    roster = json.loads((ROOT / "data" / "dungeon_prize_roster.json").read_text(encoding="utf-8"))
    assert "no wild home" in roster["power_lines"]["lines"]["gible"]["now"]


def test_every_boss_keeps_its_own_tags_and_the_same_respawn_clocks():
    tags = [s["occupant"]["tag"] for s in BOSSES]
    assert len(set(tags)) == 3 and all(s["occupant"]["guardian_tag"] == "cobblers.guardian" for s in BOSSES)
    for s in BOSSES:
        k = s["occupant"]["keeper"]
        assert (k["cooldown_faint_ticks"], k["cooldown_catch_ticks"]) == (24000, 72000)
        assert s["gate"]["flags"] == ["champion_cleared"] and "alpha=true" in s["occupant"]["properties"]


def _edit(spec, sid, f):
    s = copy.deepcopy(spec)
    f(next(x for x in s["sanctuaries"] if x["id"] == sid))
    return s


@pytest.mark.parametrize("name,sid,edit,needle", [
    ("a boss gated below the Champion", "sanctuary_broken_relay", lambda s: s["gate"].update(flags=["gym8_cleared"]), "champion_cleared"),
    ("a boss that is not an alpha", "sanctuary_stopped_clock", lambda s: s["occupant"]["properties"].remove("alpha=true"), "native alpha"),
    ("the wrong respawn clock", "sanctuary_sunscar", lambda s: s["occupant"]["keeper"].update(cooldown_faint_ticks=12000), "24,000"),
    ("a guardian tag that is not the blackout's", "sanctuary_broken_relay", lambda s: s["occupant"].update(guardian_tag="x"), "guardian_tag"),
    ("a flag no progression declares", "sanctuary_singing_hollow", lambda s: s["gate"].update(flags=["gym6_cleared_typo"]), "not declared"),
    ("a court pool over the gate's cap", "sanctuary_singing_hollow",
     lambda s: s["habitat"][0]["pool"]["entries"][0].update(level="51-60"), "over the gate's cap 50"),
    ("Meloetta not ultra-rare", "sanctuary_singing_hollow",
     lambda s: s["habitat"][0]["pool"]["entries"][-1].update(bucket="rare"), "ultra-rare"),
    ("Nihilego not in the court's pool", "sanctuary_tide_shrine", lambda s: s["occupant"].update(co_occupants=["buzzwole"]), "buzzwole"),
    ("a boss sanctuary given a pool back", "sanctuary_stopped_clock",
     lambda s: s.update(habitat=copy.deepcopy(SANS["sanctuary_singing_hollow"]["habitat"])), "no Habitat Block"),
    ("a style nobody builds", "sanctuary_sunscar", lambda s: s.update(style="pyramid"), "style"),
])
def test_the_loader_refuses_a_record_that_breaks_a_rule(name, sid, edit, needle):
    probs = S.static_problems(_edit(SPEC, sid, edit))
    assert any(needle in p for p in probs), (name, probs)


def test_every_sanctuary_is_sited_with_its_site_recorded():
    for s in SPEC["sanctuaries"]:
        site = s["site"]
        assert site["front"] in S.FRONTS and len(site["centre"]) == 2 and site["subregion"], s["id"]
        assert site["height"] >= 12, s["id"]


# ------------------------------------------------------------------ the build, audited

def test_the_committed_pack_passes_the_independent_audit(pack, ground):
    fns, cb, _plan, _r = pack
    assert audit(ground, fns, cb) == []


def test_the_pack_the_generator_makes_is_deterministic(ground):
    a = make_pack(_raw_ground())
    b = make_pack(_raw_ground())
    assert a[0] == b[0] and a[1] == b[1]


def test_the_sanctuaries_read_as_set_pieces(pack):
    # nonempty on purpose: each one tall enough to read from 100 blocks, wide, of many blocks, weathered, and unlike the others
    _f, _c, plan, _r = pack
    heights = {e["san"]["id"]: e["geometry"]["height"] for e in plan}
    assert min(heights.values()) >= 12 and len(set(heights.values())) >= 3, heights
    for e in plan:
        kinds = {S.base(b) for b in e["geometry"]["cells"].values()} - {"minecraft:air", "minecraft:barrier"}
        assert len(kinds) >= 12, (e["san"]["id"], len(kinds))


def _mutated(monkeypatch, ground, patch, **kw):
    patch(monkeypatch)
    S._COMPOSED.clear()
    try:
        fns, cb, _p, _r = make_pack(_raw_ground())
    finally:
        S._COMPOSED.clear()
    return audit(ground, fns, cb, **kw)


def _wrap_composer(monkeypatch, style, fix):
    real = S.COMPOSERS[style]

    def composer(p):
        real(p)
        fix(p)
    monkeypatch.setitem(S.COMPOSERS, style, composer)


def test_a_seal_cell_left_out_lets_a_player_walk_in_with_the_door_closed(monkeypatch, ground):
    # one column of the clock court's wall gone (the GENERATOR's composition, the record untouched): the walk finds the way in
    def fix(p):
        u, d = -7, -11                       # in the front wall, clear of the gatehouse and of the rubble under the fallen stretch
        for h in range(1, 12):
            p.blocks[(u, d, h)] = S.AIR
    probs = _mutated(monkeypatch, ground, lambda mp: _wrap_composer(mp, "clock_court", fix), only={"sanctuary_stopped_clock"}, restore=False)
    assert any("door CLOSED" in p and "sanctuary_stopped_clock" in p for p in probs), probs


def test_a_door_built_open_is_refused(monkeypatch, ground):
    # the first build of this tool did exactly this (the barrier row written as air while the gate's score said closed): the
    # door stood open to everyone and the gate would never shut it, because close runs only from the open state
    def fix(p):
        for c in p.barrier:
            p.blocks[c] = S.AIR
    probs = _mutated(monkeypatch, ground, lambda mp: _wrap_composer(mp, "tide_shrine", fix), only={"sanctuary_tide_shrine"}, restore=False)
    assert any("no barrier written" in p and "sanctuary_tide_shrine" in p for p in probs), probs


def test_a_lantern_off_its_post_is_refused(monkeypatch, ground):
    def fix(p):
        for k, b in list(p.blocks.items()):
            if b == S.LANTERN_UP:
                p.blocks[(k[0], k[1], k[2] - 1)] = "minecraft:tuff"
                break
    probs = _mutated(monkeypatch, ground, lambda mp: _wrap_composer(mp, "amphitheatre", fix), walk_it=False, restore=False)
    assert any("not a post" in p for p in probs), probs


def test_a_light_block_is_refused(monkeypatch, ground):
    def fix(p):
        p.blocks[(0, 3, 1)] = "minecraft:sea_lantern"
    probs = _mutated(monkeypatch, ground, lambda mp: _wrap_composer(mp, "tide_shrine", fix), walk_it=False, restore=False)
    assert any("sea_lantern" in p and "gives light" in p for p in probs), probs


def test_a_block_left_floating_is_refused(monkeypatch, ground):
    def fix(p):
        p.blocks[(0, 0, 40)] = "minecraft:red_sandstone"
    probs = _mutated(monkeypatch, ground, lambda mp: _wrap_composer(mp, "sun_arena", fix), walk_it=False, restore=False)
    assert any("float free of the ground" in p for p in probs), probs


def test_a_band_that_is_not_graded_is_refused(monkeypatch, ground):
    # the generator's grading turned into a cliff: the band keeps the ground's height right up to the platform
    real = S.geometry

    def geometry(spec, san, g, centre=None, front=None):
        gm = real(spec, san, g, centre, front)
        if san["id"] == "sanctuary_broken_relay":
            xz = S.M.frame(tuple(gm["centre_uv"]), gm["front"])
            for (u, d), k in gm["band"].items():
                if k == 1:
                    x, z = xz(u, d)
                    for y in range(gm["yf"] + 1, gm["yf"] + 4):
                        gm["cells"][(x, y, z)] = san["palette"]["grade_fill"]
                    gm["cells"][(x, gm["yf"] + 4, z)] = san["palette"]["grade_top"]
        return gm
    probs = _mutated(monkeypatch, ground, lambda mp: mp.setattr(S, "geometry", geometry), walk_it=False, restore=False)
    assert any("graded column" in p and "sanctuary_broken_relay" in p for p in probs), probs


def _wrap_fn(monkeypatch, name, fix):
    real = getattr(S, name)

    def wrapped(*a, **k):
        out = real(*a, **k)
        fix(out)
        return out
    monkeypatch.setattr(S, name, wrapped)


def test_a_keeper_that_can_reach_a_guardian_is_refused(monkeypatch, ground):
    def fix(fns):
        for k, ls in fns.items():
            fns[k] = [l.replace(",tag=!cobblers.guardian", "") for l in ls]
    probs = _mutated(monkeypatch, ground, lambda mp: _wrap_fn(mp, "boss_files", fix), walk_it=False, restore=False)
    assert any("can reach a guardian" in p for p in probs), probs


def test_a_keeper_that_adds_the_guardian_tag_is_refused(monkeypatch, ground):
    def fix(fns):
        for k in fns:
            if k.endswith("/bind"):
                fns[k] = fns[k] + ["tag @s add cobblers.guardian"]
    probs = _mutated(monkeypatch, ground, lambda mp: _wrap_fn(mp, "boss_files", fix), walk_it=False, restore=False)
    assert any("adds or removes cobblers.guardian" in p for p in probs), probs


def test_a_door_box_off_by_a_block_is_refused(monkeypatch, ground):
    def fix(fns):
        for k in fns:
            if k.endswith("/open"):
                fns[k] = [re.sub(r"^fill (-?\d+)", lambda m: "fill %d" % (int(m.group(1)) - 1), l) for l in fns[k]]
    probs = _mutated(monkeypatch, ground, lambda mp: _wrap_fn(mp, "gate_files", fix), walk_it=False, restore=False)
    assert any("not the same box" in p or "not exactly the written barrier" in p for p in probs), probs


def test_a_restore_that_skips_a_column_is_refused(monkeypatch, ground):
    real = S.terrain_lines

    def terrain_lines(cols, g, terrain):
        return real({c: v for i, (c, v) in enumerate(sorted(cols.items())) if i != 7}, g, terrain)
    probs = _mutated(monkeypatch, ground, lambda mp: mp.setattr(S, "terrain_lines", terrain_lines), walk_it=False,
                     only={"sanctuary_sunscar"})
    assert any("after the restore" in p for p in probs), probs


def test_a_restore_that_forgets_the_players_is_refused(monkeypatch, ground):
    def fix(fns):
        for k in fns:
            if not k.endswith("_do"):
                fns[k] = [l for l in fns[k] if not l.startswith("tag @a[x=")]
    probs = _mutated(monkeypatch, ground, lambda mp: _wrap_fn(mp, "restore_files", fix), walk_it=False, only={"sanctuary_sunscar"})
    assert any("in no box that holds the restore" in p for p in probs), probs


def test_a_build_that_does_not_refuse_over_a_standing_cave_is_refused(monkeypatch, ground):
    real = S.build_lines

    def build_lines(spec, entry, retired):
        return [l for l in real(spec, entry, retired) if "run return 0" not in l]
    probs = _mutated(monkeypatch, ground, lambda mp: mp.setattr(S, "build_lines", build_lines), walk_it=False, only={"sanctuary_sunscar"})
    assert any("does not refuse while the probe" in p for p in probs), probs


def test_a_retired_cave_whose_text_moved_fails_closed(ground):
    # the restore stands on the cave's text as applied: a frozen record that no longer hashes to it stops everything
    rc = copy.deepcopy(SPEC["retired_caves"][2])
    rc["cave"]["chamber"]["rx"] += 1
    with pytest.raises(S.SanctuaryError, match="applied sha256"):
        S.retired_cells(rc, _raw_ground())


# ------------------------------------------------------------------ the records and the wiring

def test_the_derived_records_match_the_geometry(pack):
    _f, _c, plan, retired = pack
    assert S.record_problems(SPEC, plan, retired) == []


def test_no_block_the_pack_places_is_a_spawn_condition_or_a_light(pack):
    _f, _c, plan, _r = pack
    assert S.pack_problems(SPEC, plan) == [] and S.light_problems(plan) == []


def test_the_roster_gives_each_legendary_its_sanctuary_as_home_and_no_dungeon_pool_keeps_it():
    roster = json.loads((ROOT / "data" / "dungeon_prize_roster.json").read_text(encoding="utf-8"))
    placed = {}
    for s in SPEC["sanctuaries"]:
        placed[s["occupant"]["species"]] = s["id"]
        for co in s["occupant"].get("co_occupants") or []:
            placed[co] = s["id"]
    for sp, sid in placed.items():
        rec = roster["species"][sp]
        assert rec["status"] == "to_world" and rec["home"].startswith(sid), (sp, rec["home"])
        for d in roster["dungeons"]:
            pooled = {x for band in (d.get("legendary_pool_by_band") or {}).values() for x in band}
            pooled |= {x for band in (d.get("rare_pool_by_band") or {}).values() for x in band}
            assert sp not in pooled, (sp, d["id"])
    assert "cave_" not in json.dumps({k: v.get("home") for k, v in roster["species"].items() if k in placed})


def test_the_inherited_spawns_of_the_sanctuary_beasts_stay_off():
    sup = json.loads((ROOT / "data" / "spawn_suppression.json").read_text(encoding="utf-8"))
    off = set(sup["managed_species"]["species"]) | set(sup["removed_species"]["species"])
    assert {"tapufini", "nihilego", "koraidon", "miraidon"} <= off


def _reapply():
    return (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")


def test_reapply_names_the_pack_the_step_and_the_prepare_jobs():
    src = _reapply()
    assert src.count('"cobblers_sanctuaries"') >= 2                       # SERVER_PACKS and WORLD_LOCAL
    assert 'add("sanctuaries:build", "sanctuaries.py", "build", *src)' in src and '"sanctuaries_audit.py"' in src
    assert '("R9SY",' in src and "sanctuaries.placement_steps()" in src
    # after the natural caves (R9CK), before the Habitat Blocks (R9E), which stand in the courts' floors the step writes
    assert src.index('("R9CK",') < src.index('("R9SY",') < src.index('("R9E",')


def test_the_step_restores_each_retired_cave_reads_back_nobody_held_then_builds(ground):
    steps = S.placement_steps(SPEC, _raw_ground())
    fns = [v for k, v in steps if k == "fn"]
    assert fns == [x for rc in SPEC["retired_caves"] for x in
                   [S.restore_parts(rc)[0]] + (["%s/build_%s" % (S.F, rc["successor"])] if rc.get("successor") else [])]
    checks = [v for k, v in steps if k == "check"]
    assert len(checks) == 6 and all(c[0] == "chunk_look" and c[2] == 0 for c in checks)
    adds = [v for k, v in steps if k == "cmd" and v.startswith("forceload add")]
    rems = [v for k, v in steps if k == "cmd" and v.startswith("forceload remove")]
    assert [a.replace("add", "remove") for a in adds] == rems and len(adds) == 6
    for i, (k, v) in enumerate(steps):
        if k == "fn" and "/restore/" in v:
            assert steps[i + 1][0] == "check"                          # the read-back follows the restore, before any build


def test_every_function_of_the_pack_is_run_by_a_step_or_named_by_another(pack):
    fns, cb, _p, _r = pack
    text = "\n".join("\n".join(v) for v in fns.values()) + "\n" + cb + json.dumps({"values": ["cobblers:sanctuaries/load"]})
    refs = set(re.findall(r"([a-z0-9_.-]+:[a-z0-9_./-]+)", text))
    run = set(S.step_functions(SPEC))
    lost = [n for n in fns if "cobblers:sanctuaries/%s" % n not in refs and "cobblers:sanctuaries/%s" % n not in run]
    assert lost == []


def test_the_callback_names_only_the_bosses(pack):
    _f, cb, _p, _r = pack
    for b in BOSSES:
        assert "cobblemon:%s" % b["occupant"]["species"] in cb and "cobblers:sanctuaries/boss/%s/caught" % b["id"] in cb
    for other in ("meloetta", "tapufini", "nihilego", "gible"):
        assert "cobblemon:%s" % other not in cb
    assert cb.count("'") % 2 == 0


def test_the_natural_caves_are_left_alone():
    # another unit's: data/caves.json keeps exactly N1-N3, and nothing of the sanctuaries comes within natural_gap of them
    caves = json.loads((ROOT / "data" / "caves.json").read_text(encoding="utf-8"))["caves"]
    assert sorted(c["kind"] for c in caves) == ["N1", "N2", "N3"] and all(c["mode"] == "natural" for c in caves)


# ------------------------------------------------------------------ the keeper and the gate, run

class Lake(GS.World):
    """tests/gulch_sim.py's world plus what Cobblemon adds that the pack reads (the cave kit's harness): `nbt=` selector filters, a
    spawned Pokemon's Species and Level, and `fill ... replace <block>` with a plain block filter."""

    def command(self, cmd):
        t = cmd.split(" ")
        if t[0] in ("tellraw", "playsound"):
            self.log.append(cmd)
            return None
        if t[0] == "spawnpokemonat":
            x, y, z = (float(v) for v in t[1:4])
            e = self.pokemon((x, y, z), species=t[4])
            props = t[5:]
            e["nbt"]["Pokemon"]["Species"] = "cobblemon:%s" % t[4]
            e["nbt"]["Pokemon"]["Level"] = int(next(p for p in props if p.startswith("level="))[len("level="):])
            if "no_ai" in props:
                e["nbt"]["NoAI"] = N.Byte(1)
            e["props"] = props
            self.log.append(cmd)
            return None
        if t[0] == "fill" and len(t) > 9 and t[8] == "replace" and not t[9].startswith("#"):
            x0, y0, z0, x1, y1, z1 = (int(v) for v in t[1:7])
            for x in range(min(x0, x1), max(x0, x1) + 1):
                for y in range(min(y0, y1), max(y0, y1) + 1):
                    for z in range(min(z0, z1), max(z0, z1) + 1):
                        if self.blocks.get((x, y, z), "minecraft:air") == t[9]:
                            self.blocks[(x, y, z)] = t[7]
            self.log.append(cmd)
            return None
        return super().command(cmd)

    def select(self, sel, origin=None):
        m = re.fullmatch(r"(@[aes])\[(.*)\]", sel)
        if not m or "nbt=" not in m.group(2):
            return super().select(sel, origin)
        f = GS.split_filters(m.group(2))
        pats = [N.parse_snbt(v) for k, v in f if k == "nbt"]
        rest = ",".join("=".join(kv) for kv in f if kv[0] not in ("nbt", "limit", "sort"))
        out = [e for e in super().select("%s[%s]" % (m.group(1), rest), origin) if all(N.matches(p, e.get("nbt", {})) for p in pats)]
        o = origin or self.pos
        sort = [v for k, v in f if k == "sort"]
        if sort:
            out.sort(key=lambda e: GS.math.dist(e["pos"], o), reverse=sort[0] == "furthest")
        lim = [int(v) for k, v in f if k == "limit"]
        return out[:lim[0]] if lim else out


@functools.lru_cache(maxsize=None)
def _fns_cached():
    fns, _cb, plan, _r = _pack_cached()
    return fns, plan


def spot_of():
    _fns, plan = _fns_cached()
    gm = next(p["geometry"] for p in plan if p["san"]["id"] == BID)
    return gm, (gm["centre"][0] + 0.5, gm["centre"][1] + 1, gm["centre"][2] + 0.5)


def world(gt=5_000_000):
    fns, _plan = _fns_cached()
    w = Lake({"sanctuaries/" + k: v for k, v in fns.items()})
    w.gt = gt
    w.call("sanctuaries/load")
    return w


def _bind(bid):
    """Point the module's boss globals at one area boss (each sanctuary has its own tags, spot and holders)."""
    g = globals()
    g["BOSS"] = SANS[bid]
    g["OCC"] = g["BOSS"]["occupant"]
    g["KEEP"] = g["OCC"]["keeper"]
    g["BID"] = bid
    g["TAG"], g["DORM"], g["GUARD"] = g["OCC"]["tag"], g["OCC"]["dormant_tag"], g["OCC"]["guardian_tag"]
    g["PASS"] = g["KEEP"]["period_ticks"]
    g["GONE"], g["RESP"], g["CAUGHT"] = ("#%s_%s" % (bid, x) for x in ("gone", "resp", "caught"))


_bind(BOSS_IDS[0])


class as_boss:
    """`with as_boss(id):` runs a block against that boss and restores the previous one (tests/test_system_contracts.py C25)."""

    def __init__(self, bid):
        self.bid, self.prev = bid, None

    def __enter__(self):
        self.prev = BID
        _bind(self.bid)

    def __exit__(self, *exc):
        _bind(self.prev)


@pytest.fixture(params=BOSS_IDS)
def boss_ctx(request):
    with as_boss(request.param):
        yield request.param


KEEPER = pytest.mark.usefixtures("boss_ctx")


def bosses(w):
    return [e for e in w.entities if TAG in e["tags"]]


def score(w, holder):
    return w.score.get((holder, OBJ))


def passes(w, n):
    out = []
    for _ in range(n):
        w.gt += PASS
        w.call("sanctuaries/boss/%s/keeper" % BID)
        out.append(len(bosses(w)))
    return out


def player_at(w, dx, dz, dy=0.0, flags=(CHAMPION,), mode="survival"):
    _gm, spot = spot_of()
    return w.player((spot[0] + dx, spot[1] + dy, spot[2] + dz), flags=flags, mode=mode)


def summoned(w):
    p = player_at(w, KEEP["spawn_clear"] + 8, 0)
    assert passes(w, KEEP["absent_passes"]) == [0] * (KEEP["absent_passes"] - 1) + [1]
    return bosses(w)[0], p


def court_mid(gm):
    z = gm["chamber_zone"]
    return ((z[0] + z[3]) / 2 + 0.5, z[1], (z[2] + z[5]) / 2 + 0.5)


@KEEPER
def test_nothing_exists_at_load_and_the_clock_is_the_never_value():
    w = world()
    assert bosses(w) == [] and score(w, GONE) == S.NEVER


@KEEPER
def test_a_champion_who_comes_near_brings_one_dormant_alpha_boss_to_the_court_centre():
    w = world()
    _gm, spot = spot_of()
    b, _p = summoned(w)
    assert b["pos"] == spot and DORM in b["tags"] and b["nbt"]["PoseType"] == "SLEEP" and b["nbt"]["PersistenceRequired"] == N.Byte(1)
    assert b["nbt"]["Pokemon"]["Species"] == "cobblemon:%s" % OCC["species"] and b["nbt"]["Pokemon"]["Level"] == OCC["level"] == 70
    assert "alpha=true" in b["props"] and "no_ai" in b["props"]
    assert score(w, GONE) == S.PRESENT


@KEEPER
def test_a_player_without_the_flag_never_brings_it_in():
    w = world()
    player_at(w, 20, 0, flags=())
    player_at(w, 22, 0, flags=(GYM6,))
    assert passes(w, 5) == [0] * 5


@KEEPER
def test_nobody_near_brings_nothing_and_a_spectator_champion_counts_for_nothing():
    w = world()
    player_at(w, KEEP["spawn_radius"] + 30, 0)
    player_at(w, 20, 0, mode="spectator")
    assert passes(w, 4) == [0] * 4


@KEEPER
def test_it_does_not_come_in_front_of_anyone():
    w = world()
    near = player_at(w, KEEP["spawn_clear"] - 4, 0)
    assert passes(w, 3) == [0, 0, 0]
    near["pos"] = (near["pos"][0] + 40, near["pos"][1], near["pos"][2])
    assert passes(w, 1) == [1]


@KEEPER
def test_a_second_summons_never_makes_a_second_one():
    w = world()
    summoned(w)
    assert passes(w, 6) == [1] * 6


@KEEPER
def test_it_wakes_for_a_player_in_the_court_and_not_for_one_outside_it():
    w = world()
    gm, spot = spot_of()
    b, p = summoned(w)
    z = gm["chamber_zone"]
    p["pos"] = (z[3] + 30.0, spot[1], spot[2])                       # outside the court's box
    passes(w, 2)
    assert DORM in b["tags"] and b["nbt"]["Unbattleable"] == N.Byte(1)
    p["pos"] = court_mid(gm)
    passes(w, 1)
    assert DORM not in b["tags"] and b["nbt"]["Unbattleable"] == N.Byte(0) and b["nbt"]["NoAI"] == N.Byte(1)


@KEEPER
def test_an_awake_one_is_not_dragged_home_through_the_fight_and_lies_down_when_everyone_has_gone():
    w = world()
    gm, spot = spot_of()
    b, p = summoned(w)
    p["pos"] = court_mid(gm)
    passes(w, 1)
    b["pos"] = (spot[0] + 2.0, spot[1], spot[2])
    passes(w, 3)
    assert b["pos"] == (spot[0] + 2.0, spot[1], spot[2]) and DORM not in b["tags"]
    p["pos"] = (spot[0] + KEEP["settle_radius"] + 30, spot[1], spot[2])
    passes(w, 1)
    assert DORM in b["tags"] and b["pos"] == spot and b["nbt"]["Unbattleable"] == N.Byte(1)


@KEEPER
def test_after_a_faint_it_returns_in_24000_ticks_and_not_before():
    w = world()
    b, _p = summoned(w)
    w.entities.remove(b)
    passes(w, 2)
    t_gone = score(w, GONE)
    assert t_gone not in (S.PRESENT, S.NEVER) and score(w, RESP) == 24000
    while w.gt + PASS - t_gone < 24000:
        assert passes(w, 1) == [0], "it came back before its clock"
    assert passes(w, 1) == [1]


@KEEPER
def test_after_a_catch_it_returns_in_72000_ticks_and_not_before():
    w = world()
    b, p = summoned(w)
    w.me = p
    w.call("sanctuaries/boss/%s/caught" % BID)
    w.me = None
    w.entities.remove(b)
    passes(w, 2)
    t_gone = score(w, GONE)
    assert score(w, RESP) == 72000
    w.gt = t_gone + 24000 + 5 * PASS
    assert passes(w, 1) == [0], "a catch was treated as a faint"
    w.gt = t_gone + 72000
    assert passes(w, 1) == [1]


@KEEPER
def test_a_restart_never_moves_a_started_clock():
    w = world()
    b, _p = summoned(w)
    w.entities.remove(b)
    passes(w, 2)
    t = score(w, GONE)
    w.call("sanctuaries/load")
    assert score(w, GONE) == t


@KEEPER
def test_a_guardian_is_never_held_woken_settled_or_killed():
    # C25: the boss that blacks a player out becomes the claim's guardian (tag cobblers.guardian); the keeper only counts it
    w = world()
    gm, spot = spot_of()
    b, p = summoned(w)
    b["tags"].add(GUARD)
    b["pos"] = (spot[0] + 5.0, spot[1], spot[2])
    p["pos"] = court_mid(gm)
    passes(w, 5)
    assert b in w.entities and b["pos"] == (spot[0] + 5.0, spot[1], spot[2]) and DORM in b["tags"]
    assert b["nbt"]["Unbattleable"] == N.Byte(1)
    p["pos"] = (spot[0] + 900, spot[1], spot[2])
    passes(w, 5)
    assert b in w.entities and b["pos"] == (spot[0] + 5.0, spot[1], spot[2])


@KEEPER
def test_a_guardian_the_blackout_rebuilt_counts_as_present_and_no_second_boss_spawns():
    w = world()
    _gm, spot = spot_of()
    b, _p = summoned(w)
    w.entities.remove(b)
    rebuilt = w.pokemon((spot[0] + 6.0, spot[1], spot[2]), tags=(GUARD,), species=OCC["species"])
    rebuilt["nbt"]["Pokemon"]["Species"] = "cobblemon:%s" % OCC["species"]
    passes(w, 3)
    assert score(w, GONE) == S.PRESENT
    w.gt = 10 ** 8
    player_at(w, 30, 0)
    assert passes(w, 3) == [0, 0, 0] and len([e for e in w.entities if e["kind"] == "pokemon"]) == 1


@KEEPER
def test_a_duplicate_is_removed_and_never_a_guardian():
    w = world()
    _gm, spot = spot_of()
    summoned(w)
    second = w.pokemon((spot[0] + 1.0, spot[1], spot[2]), tags=(TAG,), species=OCC["species"])
    second["nbt"]["Pokemon"]["Species"] = "cobblemon:%s" % OCC["species"]
    passes(w, 1)
    assert len(bosses(w)) == 1
    guard = w.pokemon((spot[0] + 1.0, spot[1], spot[2]), tags=(TAG, GUARD), species=OCC["species"])
    guard["nbt"]["Pokemon"]["Species"] = "cobblemon:%s" % OCC["species"]
    passes(w, 2)
    assert guard in w.entities


@KEEPER
def test_the_old_caves_boss_carries_the_same_tag_and_is_taken_over_not_doubled():
    # the retired cave's dormant boss (tag kept from the cave kit) still standing when the sanctuary's keeper first runs: it is
    # counted as present and held to the court's spot, so no second one spawns (the restore kills nothing)
    w = world()
    _gm, spot = spot_of()
    old = w.pokemon((spot[0] + 30.0, spot[1] - 9, spot[2] + 4.0), tags=(TAG, DORM), species=OCC["species"])
    old["nbt"]["Pokemon"]["Species"] = "cobblemon:%s" % OCC["species"]
    player_at(w, 30, 0)
    assert passes(w, 3) == [1, 1, 1] and old["pos"] == spot


def _gate_world():
    fns, _plan = _fns_cached()
    w = Lake({"sanctuaries/" + k: v for k, v in fns.items()})
    w.gt = 5_000_000
    w.call("sanctuaries/load")
    return w


@pytest.mark.parametrize("sid,flag", GATED)
def test_the_door_opens_for_a_flagged_player_in_the_forecourt_and_not_for_anyone_else(sid, flag):
    _fns, plan = _fns_cached()
    gm = next(p["geometry"] for p in plan if p["san"]["id"] == sid)
    w = _gate_world()
    door = gm["barrier_cells"]
    for c in door:
        w.blocks[c] = "minecraft:barrier"
    z = gm["ante_zone"]
    mid = ((z[0] + z[3]) / 2 + 0.5, z[1], (z[2] + z[5]) / 2 + 0.5)
    other = {GYM6: "cobblers:flag/gym5_cleared", GYM8: "cobblers:flag/gym7_cleared"}.get(flag, GYM6)
    stranger = w.player(mid, flags=(other,))
    for _ in range(3):
        w.call("sanctuaries/tick")
    assert all(w.blocks[c] == "minecraft:barrier" for c in door), "the door opened for a player without the flag"
    stranger["pos"] = (mid[0] + 900, mid[1], mid[2])
    w.player(mid, flags=(flag,))
    w.call("sanctuaries/tick")
    assert all(w.blocks[c] == "minecraft:air" for c in door), "the door did not open for a flagged player in the forecourt"


@pytest.mark.parametrize("sid,flag", GATED)
def test_the_door_never_closes_on_a_player_inside_and_closes_when_the_last_has_gone(sid, flag):
    _fns, plan = _fns_cached()
    gm = next(p["geometry"] for p in plan if p["san"]["id"] == sid)
    w = _gate_world()
    door = gm["barrier_cells"]
    for c in door:
        w.blocks[c] = "minecraft:barrier"
    z = gm["ante_zone"]
    ante = ((z[0] + z[3]) / 2 + 0.5, z[1], (z[2] + z[5]) / 2 + 0.5)
    inside = court_mid(gm)
    p = w.player(ante, flags=(flag,))
    w.call("sanctuaries/tick")
    assert all(w.blocks[c] == "minecraft:air" for c in door)
    p["pos"] = inside
    for _ in range(3):
        w.call("sanctuaries/tick")
    assert all(w.blocks[c] == "minecraft:air" for c in door), "the door shut on a player inside"
    ch = gm["inside_zone"]
    p["pos"] = (ch[3] + 6.0, inside[1], ch[5] + 6.0)                  # out of every zone, still within the driver's reach
    assert GS.math.dist(p["pos"], (gm["centre"][0], gm["centre"][1], gm["centre"][2])) <= SPEC["gate"]["reach"]
    w.call("sanctuaries/tick")
    assert all(w.blocks[c] == "minecraft:barrier" for c in door), "the door stayed open with nobody left"


# ------------------------------------------------------------------ the restore, run

def _restore_world(rc):
    fns, _plan = _fns_cached()
    w = Lake({"sanctuaries/" + k: v for k, v in fns.items()})
    gm = S.retired_cells(rc, _raw_ground())
    for (x, y, z, b) in S.restore_probes(rc, gm):
        w.blocks[(x, y, z)] = b
    return w, gm


@pytest.mark.parametrize("idx", range(6))
def test_the_restore_refuses_while_a_player_stands_in_the_old_cave_and_runs_once_when_nobody_does(idx):
    rc = SPEC["retired_caves"][idx]
    w, gm = _restore_world(rc)
    entry, act, holder = S.restore_parts(rc)
    x, y, z = gm["centre"][0], gm["yh"] + 1, gm["centre"][2]
    p = w.player((x + 0.5, y, z + 0.5))
    w.call(entry[len("cobblers:"):])
    assert w.score.get(("#" + holder, S.CHUNK_OBJ)) == 1
    assert not [l for l in w.log if l.startswith("fill")], "the restore wrote with a player in the cave"
    w.entities.remove(p)
    w.call(entry[len("cobblers:"):])
    assert w.score.get(("#" + holder, S.CHUNK_OBJ)) == 0
    n = len([l for l in w.log if l.startswith("fill")])
    assert n > 0
    w.call(entry[len("cobblers:"):])
    assert len([l for l in w.log if l.startswith("fill")]) == n, "a second run wrote again"

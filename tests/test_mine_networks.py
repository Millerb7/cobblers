"""The long mine networks (data/mine_networks.json, tools/mine_networks.py, tools/mine_networks_audit.py).

Offline: the heightmap and the committed data, no world, no server. Nothing here proves the networks work in a running game;
it proves the generator writes what the data says and that an audit which never imports the generator's geometry catches a
generator that breaks a rule. The mutation tests change the GENERATOR (its ground reader, its water mask, its authored
margin, its shell) and leave the data alone, because a mutation of the record moves the expectation and the output together
and proves nothing about independence (CLAUDE.md "How to prove an audit is independent").
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import mine_networks as MN            # noqa: E402
import mine_networks_audit as AU      # noqa: E402
import mine_nets_world as W           # noqa: E402

SPEC = MN.load()


def build_to(tmp, spec):
    nets = MN.all_networks(spec)
    MN.write(spec, nets, out=tmp)
    return nets


@pytest.fixture(scope="module")
def real(tmp_path_factory):
    out = tmp_path_factory.mktemp("mine_networks_real")
    nets = build_to(out, SPEC)
    problems, stats = AU.audit(SPEC, out)
    return {"out": out, "nets": nets, "problems": problems, "stats": stats}


def one(net_id):
    net = next(n for n in SPEC["networks"] if n["id"] == net_id)
    return dict(SPEC, networks=[net])


# ------------------------------------------------------------------ the data and the real build

def test_the_data_names_two_or_three_networks_east_of_the_limit():
    nets = SPEC["networks"]
    assert 2 <= len(nets) <= 3
    for n in nets:
        assert n["box"][0] >= SPEC["rules"]["x_min"] >= 4096 + 64, "a network's box starts west of the limit the owner set"
        for a in n["adits"]:
            assert a["portal"][0] >= SPEC["rules"]["x_min"]


def test_the_real_build_passes_its_independent_audit(real):
    assert real["problems"] == [], "\n".join(real["problems"][:10])


def test_every_network_is_thousands_of_blocks_long_on_several_levels(real):
    # without this the owner's request (thousands long, six players) is quietly not met
    for L, m in real["nets"]:
        assert 2000 <= L.length() <= 5200, (L.net["id"], L.length())
        assert len(L.levels) >= 5
        assert len(L.stopes) >= 3 and len(L.inclines) >= 3 and len(L.shafts) >= 3
        est = real["stats"][L.net["id"]]["drift_estimate_blocks"]
        assert abs(est - L.length()) < 0.1 * L.length(), "the audit's own length estimate disagrees with the generator's"


def test_stopes_hold_six_players(real):
    for L, _m in real["nets"]:
        for s in L.stopes:
            free = (s["x1"] - s["x0"] + 1) * (s["z1"] - s["z0"] + 1) - len(s["pillars"])
            assert free >= 150, "a stope with fewer than 150 open columns is not a place six players can work"


def test_ore_is_richer_deeper_and_diamond_only_deep(real):
    for L, m in real["nets"]:
        per_level = {}
        for (x, y, z), (lvl, _d, _s) in m.air.items():
            per_level[lvl] = per_level.get(lvl, 0) + 1
        ore_level = {}
        for (x, y, z) in m.ores:
            # the nearest level floor under the ore
            lvl = max((k for k, F in enumerate(L.levels) if F - 2 <= y), key=lambda k: -abs(L.levels[k] - y), default=0)
            ore_level[lvl] = ore_level.get(lvl, 0) + 1
        n = len(L.levels)
        top = sum(ore_level.get(k, 0) for k in range(0, n // 3)) / max(1, sum(per_level.get(k, 0) for k in range(0, n // 3)))
        bot = sum(ore_level.get(k, 0) for k in range(n - n // 3, n)) / max(1, sum(per_level.get(k, 0) for k in range(n - n // 3, n)))
        assert bot > top, (L.net["id"], "ore per carved cell is not higher on the deepest third", top, bot)
        diamonds = [c for c, b in m.ores.items() if "diamond" in b]
        assert diamonds and all(c[1] <= 20 for c in diamonds), "diamond must sit on the deep levels only"
        assert all(b.startswith("minecraft:") for b in m.ores.values())


def test_the_build_is_deterministic(real):
    again = MN.Layout(SPEC, SPEC["networks"][0]).build()
    first = real["nets"][0][0]
    assert [(r["x0"], r["z0"], r["d"], r["n"], r["kind"]) for r in again.runs] == \
           [(r["x0"], r["z0"], r["d"], r["n"], r["kind"]) for r in first.runs]


def test_every_function_is_inside_the_server_limits(real):
    import function_limits as FL
    n = 0
    for f in Path(real["out"]).rglob("*.mcfunction"):
        n += 1
        assert FL.check_file(f) == [], f.name
    assert n >= 20


def test_no_tool_here_reads_a_world():
    # the ground rule: placement tools take ground from the heightmap. Checked by name here, and by tests/test_ground_rule.py
    # by AST over every tool
    for name in ("mine_networks.py", "mine_nets_world.py", "mine_networks_audit.py", "mine_networks_map.py"):
        src = (ROOT / "tools" / name).read_text(encoding="utf-8")
        assert "region_chunks" not in src and ".mca" not in src


def test_the_audit_does_not_import_the_generator():
    tree = ast.parse((ROOT / "tools" / "mine_networks_audit.py").read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module)
    assert not names & {"mine_networks", "mine_nets_world", "mines", "mining_caves"}, names


def test_the_spawn_policy_entry_covers_what_is_placed(real):
    spawn = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
    pol = json.loads((ROOT / "data" / "spawn_block_policy.json").read_text(encoding="utf-8"))["whitelist"]
    allowed = {b for w in pol if "mine_networks" in w["scope"] for b in w["blocks"]}
    placed = set()
    for L, m in real["nets"]:
        placed |= {MN.base(b) for b in m.ores.values()} | {MN.base(f[6]) for f in m.fills}
    assert (placed & spawn) <= allowed and (placed & spawn), "the entry must name every spawn block the networks place"


def test_reapply_prepares_audits_and_runs_the_networks():
    import reapply
    assert "cobblers_mine_networks" in reapply.SERVER_PACKS
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert '"mine_networks:build"' in src and '"mine_networks_audit"' in src and '"R9MN"' in src
    assert src.index('"mine_networks:build"') < src.index('"mines_audit"') or '"mines_audit"' not in src


# ------------------------------------------------------------------ the audit bites: mutate the generator, not the data

def mutated_audit(tmp, monkeypatch, spec, patch, live_guard=False):
    # the generator's own guards (the live-carve digest, the nest rooms re-checked on the new plan) would refuse a re-planned
    # working before the audit saw it; they are switched off so the AUDIT is what is tested. The digest guard has its own test.
    if not live_guard:
        monkeypatch.setattr(MN, "CHECK_LIVE", False)
        monkeypatch.setattr(MN, "NESTS", False)
    patch(monkeypatch)
    nets = MN.all_networks(spec)
    MN.write(spec, nets, out=tmp)
    monkeypatch.undo()
    return AU.audit(spec, tmp)[0]


def test_control_the_unmutated_network_passes(tmp_path, monkeypatch):
    spec = one("mn_gorge")
    nets = build_to(tmp_path, spec)
    assert nets and AU.audit(spec, tmp_path)[0] == []


def test_audit_catches_a_generator_that_over_reads_the_ground(tmp_path, monkeypatch):
    spec = one("mn_gorge")
    real_read = MN.read_ground

    def patch(mp):
        mp.setattr(MN, "read_ground", lambda box, sr=None: real_read(box, sr) + 14)
    probs = mutated_audit(tmp_path, monkeypatch, spec, patch)
    assert any(p.split(": ", 1)[1].startswith("cover:") for p in probs), probs[:5]


def test_audit_catches_a_generator_that_forgets_the_water(tmp_path, monkeypatch):
    spec = one("mn_gorge")

    def patch(mp):
        mp.setattr(MN, "water_mask", lambda box, hbox, rules: np.zeros(hbox.shape, bool))
    probs = mutated_audit(tmp_path, monkeypatch, spec, patch)
    assert any(": water:" in p for p in probs), probs[:5]


def test_audit_catches_a_generator_that_ignores_the_authored_places(tmp_path, monkeypatch):
    spec = one("mn_gorge")

    def patch(mp):
        mp.setattr(W, "authored_seed", lambda box: np.zeros(box.shape, bool))
    probs = mutated_audit(tmp_path, monkeypatch, spec, patch)
    assert any(": authored:" in p for p in probs), probs[:5]


def test_audit_catches_a_generator_that_drops_the_shell(tmp_path, monkeypatch):
    spec = one("mn_gorge")
    orig = MN.function_lines

    def patch(mp):
        def no_shell(L, m):
            out = orig(L, m)
            return {t: [ln for ln in lines if " replace " not in ln] for t, lines in out.items()}
        mp.setattr(MN, "function_lines", no_shell)
    probs = mutated_audit(tmp_path, monkeypatch, spec, patch)
    assert any(": shell:" in p for p in probs), probs[:5]


def test_audit_catches_a_shell_with_no_second_carve(tmp_path, monkeypatch):
    spec = one("mn_gorge")
    orig = MN.function_lines

    def patch(mp):
        def one_pass(L, m):
            out = orig(L, m)
            res = {}
            for t, lines in out.items():
                keep, skip = [], False
                for ln in lines:
                    if ln.startswith("# --- pass 2"):
                        skip = True
                    elif ln.startswith("# --- fittings"):
                        skip = False
                    if not skip:
                        keep.append(ln)
                res[t] = keep
            return res
        mp.setattr(MN, "function_lines", one_pass)
    probs = mutated_audit(tmp_path, monkeypatch, spec, patch)
    assert any("do not carve again" in p for p in probs), probs[:5]


def test_audit_catches_a_ladder_with_air_behind_it(tmp_path, monkeypatch):
    spec = one("mn_gorge")
    orig = MN.function_lines

    def patch(mp):
        def flip(L, m):
            out = orig(L, m)
            res = {}
            for t, lines in out.items():
                res[t] = [ln.replace("ladder[facing=north]", "ladder[facing=south]") if "minecraft:ladder" in ln else ln for ln in lines]
            return res
        mp.setattr(MN, "function_lines", flip)
    probs = mutated_audit(tmp_path, monkeypatch, spec, patch)
    assert any("ladder" in p for p in probs), probs[:5]


# ------------------------------------------------------------------ 2026-10-23: the nest rooms, added to the LIVE working
#
# Written in the same session as the rooms (the brief asked for both; CLAUDE.md principle 16 would have a second agent write
# them). The live working's cells are pinned in data/mine_networks.json live_carve, read from the as-installed pack's own lines.

def test_every_network_has_one_or_two_nest_rooms_that_pass_the_audit(real):
    # without it the owner's "random room ... where we have habitat blocks spawning a nest" could quietly be zero rooms
    for nid, st in real["stats"].items():
        assert 1 <= len(st["nest_rooms"]) <= 2, nid
        for r in st["nest_rooms"]:
            assert r["subregion"] and r["species"], r
    assert not [p for p in real["problems"] if ": nest" in p or ": live:" in p]


def test_the_live_working_is_carved_whole_and_only_added_to(real):
    # the working is in the live world: a re-run must carve every live cell again and only ever add air
    for nid, st in real["stats"].items():
        rec = SPEC["live_carve"]["networks"][nid]
        assert st["live_cells"] == rec["cells"], nid
        assert 0 < st["added_cells"] < 4000, (nid, st["added_cells"])       # rooms and spurs only: a few hundred to a few thousand


def test_the_rooms_move_no_fitting_and_no_carve_of_the_working():
    # a timber set or a ladder the rooms displaced would be half-written over the live one; the generator compares and refuses
    for net in SPEC["networks"]:
        L = MN.Layout(SPEC, net).build()
        base, rooms = MN.Model(L), MN.Model(L, net["nest_rooms"])
        assert rooms.fix == base.fix and rooms.fills == base.fills and rooms.air_boxes == base.air_boxes, net["id"]
        assert rooms.nest_boxes and set(rooms.air) > set(base.air), net["id"]


def test_the_rooms_records_are_in_data_as_the_rooms_imply():
    # a moved room with a stale Habitat Block record would put the block in rock, or in the passage
    assert MN.nest_problems(SPEC) == []


def test_the_generator_refuses_a_base_that_moved(monkeypatch):
    # CHECK_LIVE: a re-plan (here the ground read one block high) must fail closed, never carve a second working over the live one
    spec = one("mn_gorge")
    real_read = MN.read_ground
    monkeypatch.setattr(MN, "read_ground", lambda box, sr=None: real_read(box, sr) + 1)
    with pytest.raises(MN.MineError, match="live carve"):
        MN.all_networks(spec)


def test_audit_catches_rooms_written_into_the_live_section(tmp_path, monkeypatch):
    # MUTATE THE GENERATOR: the nest rooms' carve merged into the base's pass-1 section (no section of their own); the audit's digest
    # of the live section must no longer match the data
    spec = one("mn_gorge")
    orig = MN.function_lines

    def patch(mp):
        def merged(L, m):
            return {t: [ln for ln in lines if not ln.startswith("# --- nest rooms")] for t, lines in orig(L, m).items()}
        mp.setattr(MN, "function_lines", merged)
    probs = mutated_audit(tmp_path, monkeypatch, spec, patch, live_guard=True)
    assert any(": live:" in p for p in probs), probs[:5]


def test_audit_catches_a_room_that_breaks_into_the_working(tmp_path, monkeypatch):
    # MUTATE THE GENERATOR: its room shape made 1.8 times as wide and its own room guard silenced; the data is unchanged, so the
    # audit (which reads only the record and the replayed pack) must find the room no longer a dead end of the declared shape
    spec = one("mn_gorge")
    orig = MN.room_cells

    def patch(mp):
        mp.setattr(MN, "room_cells", lambda room: orig(dict(room, radius=[room["radius"][0] * 1.8, room["radius"][1] * 1.8])))
        mp.setattr(MN, "room_problems", lambda *a, **k: [])
    probs = mutated_audit(tmp_path, monkeypatch, spec, patch, live_guard=True)
    assert any(": nest " in p for p in probs), probs[:5]


def test_the_nest_species_are_in_the_jar():
    # a species the jar does not have compiles to a pool that spawns nothing
    import battle_sim
    try:
        jar = battle_sim.find_jar()
    except Exception as exc:          # noqa: BLE001
        pytest.skip("no Cobblemon jar here: %s" % exc)
    import nest_rooms as NR
    sp = NR.load_species(jar)
    habs = {h["id"]: h for h in json.loads((ROOT / "data" / "spawns.json").read_text(encoding="utf-8"))["habitats"]}
    for net in SPEC["networks"]:
        for r in net["nest_rooms"]:
            for e in habs[r["id"] + "_pool"]["entries"]:
                assert e["pokemon"] in sp, (r["id"], e["pokemon"])


# ------------------------------------------------------------------ 2026-10-23: the ore that goes into the rock (tools/ore_veins.py)

def test_the_ore_layer_hides_ore_and_adds_almost_no_exposed_ore(real):
    # the owner (2026-10-23): "some ore should be hidden", with the exposed ore staying roughly what it was. The AUDIT counts both
    # from the built functions (not the generator's own tally)
    for net_id, st in real["stats"].items():
        lay = st["ore_layer"]
        base_exposed = sum(1 for L, m in real["nets"] if L.net["id"] == net_id
                           for c in m.ores if any((c[0] + d[0], c[1] + d[1], c[2] + d[2]) in m.air
                                                  for d in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))))
        assert lay["cells"] > 1000, net_id
        assert lay["hidden"] >= 0.5 * base_exposed, (net_id, lay["hidden"], base_exposed)
        assert lay["exposed"] <= 0.05 * base_exposed, (net_id, lay["exposed"], base_exposed)


def test_every_ore_function_line_replaces_rock_only_and_runs_after_every_carve(real):
    d = real["out"] / "data" / "cobblers" / "function" / "mine_networks"
    files = sorted(d.glob("*_o_*_*.mcfunction"))
    assert files
    n = 0
    for f in files:
        for ln in f.read_text(encoding="utf-8").splitlines():
            if ln.startswith("fill"):
                assert ln.endswith(" replace #minecraft:base_stone_overworld"), (f.name, ln)
                n += 1
    assert n > 3000
    idx = (d / "index.txt").read_text(encoding="utf-8").split()
    kinds = ["o" if "_o_" in x else "t" for x in idx]
    assert kinds == sorted(kinds, key=lambda k: 0 if k == "t" else 1) and "o" in kinds     # ore last


def test_the_layer_never_touches_a_fitting_a_base_ore_or_a_carved_cell(real):
    for L, m in real["nets"]:
        assert m.layer_ores
        for (x, y, z, _b, _tid, _k) in m.layer_ores:
            c = (x, y, z)
            assert c not in m.air and c not in m.fix and c not in m.ores, (L.net["id"], c)


def test_the_layer_ore_stays_inside_the_reach_of_the_working_and_under_cover(real):
    # the generator's cover (8) and reach (7 of a wall cell, so 8 of a carved cell), read here from the model itself
    for L, m in real["nets"]:
        pb = L.pbox
        for (x, y, z, _b, _tid, _k) in m.layer_ores:
            assert int(L.H[z - pb.z0, x - pb.x0]) - y >= SPEC["rules"]["cover_min"]
        for (x, y, z, _b, _tid, _k) in m.layer_ores[::40]:                  # a sample: 17^3 lookups a cell
            assert any((x + dx, y + dy, z + dz) in m.air for dx in range(-8, 9) for dy in range(-8, 9) for dz in range(-8, 9)), (x, y, z)


def test_a_rare_ore_of_the_layer_stays_on_the_levels_its_type_allows(real):
    # y_max is the highest FLOOR a type may be seeded at; a layer cell lies at most a stope's height (6) and the reach (7) above one
    ymax = {t["id"]: t["y_max"] for t in SPEC["ores"]["table"]}
    for L, m in real["nets"]:
        for (x, y, z, _b, tid, _k) in m.layer_ores:
            assert y <= ymax[tid] + 6 + 7 + 1, (L.net["id"], tid, y)


def test_audit_catches_a_layer_written_without_the_rock_only_filter(tmp_path, monkeypatch):
    spec = one("mn_gorge")
    probs = mutated_audit(tmp_path, monkeypatch, spec, lambda mp: mp.setattr(MN, "ORE_FILTER", None))
    assert any("written with filter" in p for p in probs), probs[:5]


def test_audit_catches_a_generator_that_grows_ore_out_into_the_working(tmp_path, monkeypatch):
    import ore_veins as OV
    spec = one("mn_gorge")
    orig = OV.inward_of

    def patch(mp):
        mp.setattr(OV, "inward_of", lambda air, c: (lambda r: None if r is None else (r[0], -r[1]))(orig(air, c)))
        mp.setattr(OV.Layer, "hidden_ok", lambda self, c, w, t: (c[0] - w[0]) ** 2 + (c[1] - w[1]) ** 2 + (c[2] - w[2]) ** 2 <= OV.REACH2)
    probs = mutated_audit(tmp_path, monkeypatch, spec, patch)
    assert any("layer:" in p and ("inside a carved cell" in p or "carve functions wrote" in p) for p in probs), probs[:5]


def test_audit_catches_a_generator_that_lets_the_ore_wander_far_from_the_working(tmp_path, monkeypatch):
    import ore_veins as OV
    spec = one("mn_gorge")
    orig = OV.add

    def patch(mp):
        mp.setattr(OV, "REACH2", 100000)
        mp.setattr(OV, "add", lambda c, d, k=1: orig(c, d, k * 3 if k > 1 else k))
    probs = mutated_audit(tmp_path, monkeypatch, spec, patch)
    assert any("more than 8 from any carved cell" in p for p in probs), probs[:5]

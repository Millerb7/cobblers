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

def mutated_audit(tmp, monkeypatch, spec, patch):
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

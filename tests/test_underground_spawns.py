"""tools/underground_spawns.py and data/underground_spawns.json: wild Pokemon in the six dug systems.

The fault (the owner, 2026-10-22, "add pokemon to caves"): every compiled surface detail forces canSeeSky true, and
tools/suppress_inherited_spawns.py removes inherited cave spawns under every box at every height, so nothing spawned
underground. The fix is our own pool in its own pack, cobblers_underground_spawns, with canSeeSky false.

Written by the implementer of the table and the tool (the brief asked for it; no second agent). Independence is kept as far
as it goes: the expectations come from the plans (derived/cave_systems, derived/mine_networks), data/mine_crews.json,
data/cave_systems.json, data/towns.json and the Cobblemon jar, never from the tool's own functions, and the mutation tests
change the GENERATOR and leave the table alone.

Not covered, and it needs a running server: that Cobblemon loads the pack, that /checkspawn underground lists the pool,
and that the species really appear (docs/research/EXPERIMENT_BACKLOG.md EXP-028 is the habitat-block cousin).
"""
from __future__ import annotations

import json
import math
import sys
import types
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import reapply as RA  # noqa: E402
import suppress_inherited_spawns as SIS  # noqa: E402
import underground_spawns as U  # noqa: E402

BANDS = ("shallow", "mid", "deep")
DOC = U.load()
SYSTEMS = {s["id"]: s for s in DOC["systems"]}
CAVE_PLAN = ROOT / "derived" / "cave_systems" / "plan.json"
MINE_PLAN = ROOT / "derived" / "mine_networks" / "plan.json"


def _j(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    out = tmp_path_factory.mktemp("ug") / "cobblers_underground_spawns"
    U.write(DOC, out)
    return out


def _details(pack, sid):
    return json.loads((pack / U.SUBDIR / ("%s.json" % sid)).read_text(encoding="utf-8"))["spawns"]


# A system added to the dug data without a pool here would stay empty underground: the sweep is over the data files.
def test_every_dug_system_has_a_pool():
    dug = {s["id"] for s in _j("data/cave_systems.json")["systems"]} | {n["id"] for n in _j("data/mine_networks.json")["networks"]}
    assert dug == set(SYSTEMS), (sorted(dug ^ set(SYSTEMS)))
    assert len(dug) == 6


# Without all three bands the shallow tunnels would spawn and the deep ones stay empty, or the reverse.
def test_every_system_has_each_depth_band_in_the_written_pack(pack):
    for sid, s in SYSTEMS.items():
        det = _details(pack, sid)
        for band in BANDS:
            got = [d for d in det if d["id"].startswith("ug_%s_%s_" % (sid, band))]
            assert got, (sid, band)
            assert any(d["bucket"] == "common" for d in got), (sid, band, "no common pick")
        assert any(d["bucket"] in ("rare", "ultra-rare") and d["id"].startswith("ug_%s_deep_" % sid) for d in det), sid


# The whole point: canSeeSky false (the surface pools force true, so the two never overlap), bounded in x, y and z.
def test_every_detail_is_canseesky_false_inside_its_box_and_band(pack):
    for sid, s in SYSTEMS.items():
        x0, z0, x1, z1 = s["pool_box"]
        for d in _details(pack, sid):
            c = d["condition"]
            assert c["canSeeSky"] is False, d["id"]
            assert c["dimensions"] == ["minecraft:overworld"], d["id"]
            assert x0 <= c["minX"] <= c["maxX"] <= x1 and z0 <= c["minZ"] <= c["maxZ"] <= z1, d["id"]
            band = d["id"].split("_b")[0].rsplit("_", 1)[-1]
            assert (c["minY"], c["maxY"]) == (s["bands"][band]["minY"], s["bands"][band]["maxY"]), d["id"]
            assert d["spawnablePositionType"] == "grounded" and d["type"] == "pokemon", d["id"]
            assert "anticondition" not in d and "anticonditions" not in d, d["id"]
            assert not (set(c) - {"minX", "maxX", "minY", "maxY", "minZ", "maxZ", "canSeeSky", "dimensions"}), d["id"]


def test_the_audit_is_clean_on_the_real_table(pack):
    assert U.audit(DOC, pack) == []


# Weights are the rarity table's, not numbers tuned until the pools looked right.
def test_weights_come_from_the_rarity_table():
    fam = {r["bucket"]: r["family_weight"] for r in _j("data/spawns.json")["rarity"].values()}
    for s in DOC["systems"]:
        for band in BANDS:
            for sp, _lv, bucket, w in s["bands"][band]["entries"]:
                assert w in (fam[bucket], fam[bucket] * 0.75), (s["id"], band, sp, bucket, w)


# Paradoxes and the five managed legendaries are never wild by our hand either.
def test_no_removed_or_managed_species():
    sup = _j("data/spawn_suppression.json")
    banned = set(sup["removed_species"]["species"]) | set(sup["managed_species"]["species"])
    used = {e[0] for s in DOC["systems"] for b in BANDS for e in s["bands"][b]["entries"]}
    assert not (used & banned), used & banned
    assert len(used) >= 30


# Levels rise with depth inside a system, and none passes the system's cap.
def test_levels_rise_with_depth_and_stay_under_the_cap():
    for s in DOC["systems"]:
        tops = []
        for band in BANDS:
            ranges = [U.level_range(e[1]) for e in s["bands"][band]["entries"]]
            tops.append((min(r[0] for r in ranges), max(r[1] for r in ranges)))
            assert max(r[1] for r in ranges) <= s["cap"], (s["id"], band)
        assert tops[0][0] <= tops[1][0] <= tops[2][0] and tops[0][1] <= tops[1][1] <= tops[2][1], (s["id"], tops)


# The mines' wild levels follow the crews (data/mine_crews.json), level group by level group.
def test_mine_levels_overlap_the_crews_of_the_same_levels():
    crews = {n["id"]: n for n in _j("data/mine_crews.json")["networks"]}
    for s in DOC["systems"]:
        if s["kind"] != "mine":
            continue
        for band in BANDS:
            levels = set(s["level_groups"][band])
            crew = [m["level"] for c in crews[s["id"]]["crew"] if c["level"] in levels for m in c["normal"]]
            assert crew, (s["id"], band)
            ranges = [U.level_range(e[1]) for e in s["bands"][band]["entries"] if e[2] == "common"]
            lo, hi = min(r[0] for r in ranges), max(r[1] for r in ranges)
            assert lo <= max(crew) and hi >= min(crew), (s["id"], band, (lo, hi), (min(crew), max(crew)))


# The caves' bands sit on data/cave_systems.json's floors: upper in shallow, middle in mid, deep and abyss in deep.
def test_cave_bands_hold_the_authored_floors():
    levels = {lv["id"]: lv for lv in _j("data/cave_systems.json")["rules"]["levels"]}
    for s in DOC["systems"]:
        if s["kind"] != "cave":
            continue
        b = s["bands"]
        for lid, band in (("upper", "shallow"), ("middle", "mid"), ("deep", "deep"), ("abyss", "deep")):
            lv = levels[lid]
            assert b[band]["minY"] <= lv["y"] - lv["spread"] and lv["y"] + lv["spread"] <= b[band]["maxY"], (s["id"], lid)


# Every cut must leave the tunnels in: a plan cell (a drift run, a stope, a cave node) must fall in a part of the box.
def _parts(s):
    return U.system_parts(s, U.keep_out())


def _inside(parts, x, z):
    x, z = math.floor(x), math.floor(z)       # a block is its integer corner; the parts are inclusive integer boxes
    return any(p[0] <= x <= p[1] and p[2] <= z <= p[3] for p in parts)


@pytest.mark.skipif(not MINE_PLAN.is_file(), reason="derived/mine_networks/plan.json absent (run tools/mine_networks.py build)")
def test_the_mines_plan_lies_inside_the_boxes_and_the_levels_sit_in_their_bands():
    plan = json.loads(MINE_PLAN.read_text(encoding="utf-8"))["networks"]
    for nid, n in plan.items():
        s = SYSTEMS[nid]
        assert n["levels"] == s["levels_y"], (nid, n["levels"])
        x0, z0, x1, z1 = s["pool_box"]
        parts = _parts(s)
        net = next(q for q in _j("data/mine_networks.json")["networks"] if q["id"] == nid)
        nb = net["box"]
        assert nb[0] <= x0 and x1 <= nb[2] and nb[1] <= z0 and z1 <= nb[3], "the pool box leaves the network's box"
        cells = []
        for r in n["runs"]:
            for k in range(0, r["n"] + 1, 4):
                cells.append((r["x"] + r["dx"] * k, r["z"] + r["dz"] * k))
        for st in n["stopes"]:
            b = st["bounds"]
            cells += [(b[0], b[1]), (b[2], b[3])]
        for st in n["shafts"] + n["inclines"]:
            cells.append((st["x"], st["z"]))
        bad = [c for c in cells if not (x0 <= c[0] <= x1 and z0 <= c[1] <= z1)]
        assert not bad, (nid, bad[:3])
        cut = [c for c in cells if not _inside(parts, *c)]
        assert not cut, (nid, "a keep-out zone cuts a drift", cut[:3])
        for band in BANDS:
            floors = [n["levels"][i - 1] for i in s["level_groups"][band]]
            b = s["bands"][band]
            assert all(b["minY"] <= f + 1 <= b["maxY"] for f in floors), (nid, band, floors, b)
            others = [f for g in BANDS if g != band for f in [n["levels"][i - 1] for i in s["level_groups"][g]]]
            assert not any(b["minY"] <= f + 1 <= b["maxY"] for f in others), (nid, band, "another band's floor is in this band")


@pytest.mark.skipif(not CAVE_PLAN.is_file(), reason="derived/cave_systems/plan.json absent (run tools/cave_systems.py build)")
def test_the_caves_plan_lies_inside_the_boxes():
    plan = json.loads(CAVE_PLAN.read_text(encoding="utf-8"))["systems"]
    for sid, c in plan.items():
        s = SYSTEMS[sid]
        bx0, by0, bz0, bx1, by1, bz1 = c["bounds"]
        x0, z0, x1, z1 = s["pool_box"]
        assert x0 <= bx0 and bx1 <= x1 and z0 <= bz0 and bz1 <= z1, (sid, c["bounds"], s["pool_box"])
        assert by1 <= s["bands"]["shallow"]["maxY"], (sid, "the highest node is over the shallow band")
        assert by0 >= s["bands"]["deep"]["minY"]
        parts = _parts(s)
        cut = [(n[0], n[2]) for n in c["nodes_xyzwh"] if not _inside(parts, n[0], n[2])]
        assert not cut, (sid, "a keep-out zone cuts a tunnel", cut[:3])


# The table's level floor for an evolved stage comes from the jar, not from memory.
def test_evolved_stages_are_not_spawned_below_their_evolution_level():
    evo, jar = U.jar_species()
    if evo is None:
        pytest.skip("no Cobblemon jar on this machine: %s" % jar)
    pre = {}
    for sp, rows in evo.items():
        for res, lvl in rows:
            pre[res] = max(pre.get(res, 0), lvl)
    assert pre["aggron"] == 42 and pre["excadrill"] == 31 and pre["golbat"] == 22, "the jar read is wrong"
    for s in DOC["systems"]:
        for band in BANDS:
            for sp, lv, _b, _w in s["bands"][band]["entries"]:
                assert sp in evo, (s["id"], sp)
                assert U.level_range(lv)[0] >= pre.get(sp, 0), (s["id"], band, sp, lv, pre.get(sp))


# ---------------------------------------------------------------- the suppression must not reach this pack

FAKE = "data/cobblemon/spawn_pool_world/fake_zubat.json"
INHERITED = {"id": "fake-zubat-4", "pokemon": "zubat", "type": "pokemon", "spawnablePositionType": "grounded",
             "bucket": "uncommon", "level": "1-25", "weight": 25.0, "condition": {"canSeeSky": False}}


def _suppress(tmp_path, pack):
    server, world, out = tmp_path / "server", tmp_path / "world", tmp_path / "out"
    (server / "mods").mkdir(parents=True)
    with zipfile.ZipFile(server / "mods" / "fake.jar", "w") as z:
        z.writestr(FAKE, json.dumps({"enabled": True, "neededInstalledMods": [], "spawns": [dict(INHERITED)]}))
    dest = world / "datapacks" / "cobblers_underground_spawns"
    for f in pack.rglob("*"):
        if f.is_file():
            t = dest / f.relative_to(pack)
            t.parent.mkdir(parents=True, exist_ok=True)
            t.write_bytes(f.read_bytes())
    assert SIS.main(["--server", str(server), "--world", str(world), "--out", str(out)]) == 0
    return out


# Without it the anticondition (an x/z box, every height) lands on our details and empties the very caves they were written for.
def test_the_suppression_never_re_emits_or_marks_our_pool(tmp_path, pack):
    out = _suppress(tmp_path, pack)
    assert not (out / "data" / "cobblers").exists(), "the suppression re-emitted a cobblers_* file"
    assert not list(out.rglob("underground")), "the suppression wrote an underground pool"
    # and the installed copy, which the suppression only reads past, is byte for byte what the build wrote
    for sid in SYSTEMS:
        assert _details(pack, sid)
        assert all("anticonditions" not in d for d in _details(pack, sid))


# The premise: the inherited cave detail IS suppressed at every height under a box, which is why it had to be replaced.
def test_the_premise_the_suppression_box_has_no_height(tmp_path, pack):
    out = _suppress(tmp_path, pack)
    d = json.loads((out / FAKE).read_text(encoding="utf-8"))["spawns"][0]
    boxes = [c for c in d["anticonditions"] if "minX" in c]
    assert boxes and not any("minY" in c or "maxY" in c for c in boxes)


def test_the_pack_is_a_world_spawn_pack_and_a_prepare_job():
    assert "cobblers_underground_spawns" in RA.SPAWN_PACKS
    names = [n for n, _ in RA.prepare_jobs(types.SimpleNamespace(source_root="x", server_dir="x"))]
    i = names.index("compile_spawns")
    assert names[i + 1:i + 3] == ["underground_spawns", "underground_spawns_audit"], names[i:i + 4]


# ---------------------------------------------------------------- mutations: change the generator, never the table

def test_audit_catches_a_generator_that_drops_canseesky(tmp_path, monkeypatch):
    real = U.system_details

    def bad(system, zones):
        det, parts = real(system, zones)
        for d in det:
            d["condition"].pop("canSeeSky")
        return det, parts

    monkeypatch.setattr(U, "system_details", bad)
    out = tmp_path / "p"
    U.write(DOC, out)
    assert any("canSeeSky" in p for p in U.audit(DOC, out))


def test_audit_catches_a_generator_that_ignores_the_keep_out_zones(tmp_path, monkeypatch):
    monkeypatch.setattr(U, "system_parts", lambda s, z: [(s["pool_box"][0], s["pool_box"][2], s["pool_box"][1], s["pool_box"][3])])
    out = tmp_path / "p"
    U.write(DOC, out)
    assert any("town or spawn-free" in p for p in U.audit(DOC, out))


def test_audit_catches_a_generator_that_widens_the_y_range(tmp_path, monkeypatch):
    real = U.system_details

    def bad(system, zones):
        det, parts = real(system, zones)
        for d in det:
            d["condition"]["maxY"] += 4
        return det, parts

    monkeypatch.setattr(U, "system_details", bad)
    out = tmp_path / "p"
    U.write(DOC, out)
    assert any("y range" in p for p in U.audit(DOC, out))


def test_audit_catches_a_missing_band(tmp_path):
    doc = json.loads(json.dumps(DOC))
    doc["systems"][0]["bands"]["deep"]["entries"] = []
    out = tmp_path / "p"
    U.write(DOC, out)
    assert any("no deep pool" in p for p in U.audit(doc, out))


def test_audit_catches_a_species_the_jar_does_not_have(tmp_path):
    evo, _ = U.jar_species()
    if evo is None:
        pytest.skip("no Cobblemon jar on this machine")
    doc = json.loads(json.dumps(DOC))
    doc["systems"][0]["bands"]["mid"]["entries"].append(["notamon", "9-10", "common", 12])
    out = tmp_path / "p"
    U.write(doc, out)
    assert any("notamon" in p for p in U.audit(doc, out))

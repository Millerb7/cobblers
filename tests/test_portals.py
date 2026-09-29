"""The dive and sky portals: the data's rules, the emitted pack's shape, and that the audit fails closed.

WRITTEN BY THE AGENT THAT WROTE tools/portals.py. CLAUDE.md principle 16 says implementation and its test should
be different agents, and this is a stated breach, recorded here the way tests/test_mines_independent.py records
its own: the brief asked the builder for unit tests. A reviewer should re-derive these expectations, not trust
them, and in particular should not take the corruption tests below as a complete list of what can go wrong.

What is checked, and where the expectation comes from:

  data/portals.json     the owner's rule (1 in 6 meaningful), the x4000 line for sky sites, the gates, and that
                        every loot item id already appears in data/rewards.json (nothing invented: principle 7)
  tools/portals.py      the emitted pack, built against a FLAT stand-in ground so it needs no heightmap:
                        every portal's four functions, the crossing gated on its own tag and no other, the way
                        back never gated, rooms that do not overlap, and that the pack never grants cobblers.dive
  tools/portals_audit.py  it must FAIL on a pack that has been broken in eight named ways. An audit that passes
                        a broken artifact is worth nothing.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import portals as P  # noqa: E402
import portals_audit as PA  # noqa: E402
import function_limits  # noqa: E402

DOC = json.loads((ROOT / "data" / "portals.json").read_text(encoding="utf-8"))


class Flat:
    """A stand-in for tools/ground.py: flat ground, so the pack can be built with no heightmap.

    y40 is under every authored lake level (77 to 127), so the dive rules are satisfied everywhere, and flat
    ground has no relief, so the apron rule is too. Nothing here tests where the portals really are: that is
    tools/portals_audit.py's job, against the real heightmap."""

    def __init__(self, *a, **k):
        pass

    def __call__(self, x, z):
        return 40


@pytest.fixture(scope="module")
def built(tmp_path_factory, ):
    """{path: text} for the whole pack, built against Flat. No heightmap, no build/ directory touched."""
    S = P.sites(P.load(), Flat())
    for s in S.values():
        if DOC["rooms"][s["room"]]["chest"]:
            s["room_blocks"] = [(x, y, z, b if b != "minecraft:chest[facing=north]" else
                                 'minecraft:chest[facing=north]{LootTable:"cobblers:portals/%s"}' % s["id"])
                                for x, y, z, b in s["room_blocks"]]
    return P.files(P.load(), S), S


# ------------------------------------------------------------------------------------- the data's own rules


def test_data_loads_and_keeps_the_owners_one_in_six():
    doc = P.load()
    for gate in doc["gates"]:
        group = [p for p in doc["portals"] if p["gate"] == gate]
        assert len(group) % 6 == 0 and len(group) > 0
        assert sum(1 for p in group if p["meaningful"]) == len(group) // 6


def test_every_sky_portal_is_east_of_the_owners_line():
    line = DOC["rules"]["sky_min_x"]
    west = [p["id"] for p in DOC["portals"] if p["gate"] == "sky" and p["at"][0] < line]
    assert west == [], "a sky portal west of x%d sits unusable for three gyms: %s" % (line, west)


def test_the_dive_gate_is_the_existing_one_and_the_sky_gate_is_new():
    assert DOC["gates"]["dive"]["tag"] == "cobblers.dive"
    assert DOC["gates"]["dive"]["granted_by"] == "cobblers:water/grant_dive"
    assert DOC["gates"]["sky"]["tag"] == "cobblers.sky"
    assert DOC["gates"]["sky"]["flag"] == "gym4_cleared"
    flags = json.loads((ROOT / "data" / "progression.json").read_text(encoding="utf-8"))["flags"]
    assert any(f["id"] == "gym4_cleared" for f in flags), "the sky gate hangs off a flag that does not exist"


def test_no_loot_item_id_is_invented():
    """Every id must already appear in data/rewards.json, which was checked against the server (principle 7)."""
    known = set(re.findall(r'"((?:cobblemon|minecraft):[a-z0-9_]+)"',
                           (ROOT / "data" / "rewards.json").read_text(encoding="utf-8")))
    used = {i["item"] for t in DOC["loot"]["tables"].values() for i in t}
    assert used <= known, "invented item id(s): %s" % sorted(used - known)


def test_every_dive_portal_names_a_water_body_with_an_authored_level():
    bodies = P.water_bodies()
    for p in DOC["portals"]:
        if p["gate"] == "dive":
            assert p["water_body"] in bodies, p["id"]


@pytest.mark.parametrize("break_it, why", [
    (lambda d: d["portals"][0].update(meaningful=True), "two meaningful in one six"),
    (lambda d: d["portals"][0].update(story="a story I invented"), "a story that is not Codex's"),
    (lambda d: d["portals"][0].update(gate="water"), "a gate that does not exist"),
    (lambda d: d["portals"][0].update(facing="up"), "a facing that is not cardinal"),
    (lambda d: d["portals"].append(dict(d["portals"][0])), "a duplicate id"),
    (lambda d: d["portals"][5].update(room="cell"), "the meaningful one is not the vault"),
])
def test_load_refuses_broken_data(tmp_path, break_it, why):
    doc = json.loads((ROOT / "data" / "portals.json").read_text(encoding="utf-8"))
    break_it(doc)
    f = tmp_path / "portals.json"
    f.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(P.PortalError):
        P.load(f)


# ------------------------------------------------------------------------------------------- the built pack


def test_every_portal_gets_its_four_functions_and_its_advancements(built):
    out, _S = built
    for p in DOC["portals"]:
        for where in ("world", "pocket", "enter", "leave"):
            assert "data/cobblers/function/portals/%s/%s.mcfunction" % (where, p["id"]) in out, (p["id"], where)
        for where in ("enter", "leave"):
            assert "data/cobblers/advancement/portals/%s/%s.json" % (where, p["id"]) in out


def test_the_crossing_is_gated_on_its_own_tag_and_no_other(built):
    out, _S = built
    for p in DOC["portals"]:
        body = out["data/cobblers/function/portals/enter/%s.mcfunction" % p["id"]]
        mine = DOC["gates"][p["gate"]]["tag"]
        assert "execute unless entity @s[tag=%s] run return 0" % mine in body, p["id"]
        for other, g in DOC["gates"].items():
            if other != p["gate"]:
                assert g["tag"] not in body, p["id"]


def test_the_way_back_is_never_gated(built):
    out, _S = built
    for p in DOC["portals"]:
        body = out["data/cobblers/function/portals/leave/%s.mcfunction" % p["id"]]
        assert "return 0" not in body and "execute in minecraft:overworld run tp @s" in body
        for g in DOC["gates"].values():
            assert g["tag"] not in body, p["id"]


def test_the_pack_never_grants_or_revokes_the_dive_tag(built):
    """cobblers.dive is tools/blackout_pack.py's. This pack reads it and must never touch it."""
    out, _S = built
    for path, body in out.items():
        if not path.endswith(".mcfunction"):
            continue
        for line in body.splitlines():
            if line.strip().startswith("#"):
                continue
            assert "cobblers.dive" not in line or line.strip().startswith("execute unless entity @s[tag="), \
                "%s: %s" % (path, line)


def test_rooms_do_not_overlap_and_sit_in_their_own_band(built):
    _out, S = built
    boxes = {}
    for s in S.values():
        h = DOC["rooms"][s["room"]]["half"] + 1
        cx, cz = s["room_centre"]
        assert cz == DOC["pocket"]["bands"][s["gate"]]
        boxes[s["id"]] = (cx - h, cz - h, cx + h, cz + h)
    ids = sorted(boxes)
    for i, p in enumerate(ids):
        for q in ids[i + 1:]:
            a, b = boxes[p], boxes[q]
            assert not (a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]), (p, q)


def test_the_crossing_lands_inside_its_own_room(built):
    out, S = built
    fy = DOC["pocket"]["floor_y"]
    for s in S.values():
        body = out["data/cobblers/function/portals/enter/%s.mcfunction" % s["id"]]
        m = re.search(r"execute in (\S+) run tp @s (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)", body)
        assert m and m.group(1) == DOC["pocket"]["dimension"]
        x, y, z = (float(m.group(i)) for i in (2, 3, 4))
        h = DOC["rooms"][s["room"]]["half"]
        cx, cz = s["room_centre"]
        assert y == fy and cx - h <= x <= cx + h and cz - h <= z <= cz + h, s["id"]


def test_no_command_the_server_would_refuse(built):
    out, _S = built
    for path, body in out.items():
        if path.endswith(".mcfunction"):
            assert function_limits.check_lines(body.splitlines(), path) == []


def test_the_meaningful_reward_is_once_per_player(built):
    out, _S = built
    for p in DOC["portals"]:
        if not p["meaningful"]:
            continue
        body = out["data/cobblers/function/portals/claim/%s.mcfunction" % p["id"]]
        assert "advancement revoke" not in body, "%s: a re-armed claim is not once per player" % p["id"]
        assert "loot give @s loot cobblers:portals/%s" % p["id"] in body


def test_the_dimension_cannot_hold_a_players_spawn(built):
    out, _S = built
    t = json.loads(out["data/cobblers/dimension_type/pocket.json"])
    assert t["bed_works"] is False and t["respawn_anchor_works"] is False
    d = json.loads(out["data/cobblers/dimension/pocket.json"])
    assert d["generator"]["settings"]["biome"] == "minecraft:the_void"
    assert d["generator"]["settings"]["features"] is False


def test_the_rescue_covers_every_portal_and_has_a_fallback(built):
    out, S = built
    body = out["data/cobblers/function/portals/rescue.mcfunction"]
    for s in S.values():
        assert ("matches %d run function cobblers:portals/leave/%s" % (s["index"], s["id"])) in body
    assert "unless score @s cobblers.portal matches 1.." in body


# --------------------------------------------------------------------------- the audit has to fail closed


def _write(pack: Path, out: dict):
    for path, body in out.items():
        f = pack / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(body, encoding="utf-8")


def _run(monkeypatch, pack, packs_dir):
    monkeypatch.setattr(PA, "PACK", pack)
    monkeypatch.setattr(PA, "DATA", ROOT / "data" / "portals.json")

    class A:
        source_root = None
        packs = str(packs_dir)
    import ground as G
    monkeypatch.setattr(G, "Ground", Flat)
    return PA.audit(A())


CORRUPTIONS = {
    "no arch": lambda pk: (pk / "data/cobblers/function/portals/world/sky_far_reach.mcfunction").write_text(
        "# nothing\n", encoding="utf-8"),
    "the crossing is ungated": lambda pk: _strip(
        pk / "data/cobblers/function/portals/enter/sky_far_reach.mcfunction", "return 0"),
    "the way back is gated": lambda pk: _append(
        pk / "data/cobblers/function/portals/leave/sky_far_reach.mcfunction",
        "execute unless entity @s[tag=cobblers.sky] run return 0"),
    "a room that leaks": lambda pk: _strip(
        pk / "data/cobblers/function/portals/pocket/dive_shrew_pit.mcfunction", "fill 124 95 -4 132 95 -4"),
    "the rescue forgets a portal": lambda pk: _strip(
        pk / "data/cobblers/function/portals/rescue.mcfunction", "matches 3 run"),
    "a driver that never reschedules": lambda pk: _strip(
        pk / "data/cobblers/function/portals/tick.mcfunction", "schedule function"),
    "a bed that works in the pocket": lambda pk: _json_set(
        pk / "data/cobblers/dimension_type/pocket.json", "bed_works", True),
    "not in the load tag": lambda pk: (pk / "data/minecraft/tags/function/load.json").write_text(
        '{"values": []}', encoding="utf-8"),
    "a claim that re-arms": lambda pk: _append(
        pk / "data/cobblers/function/portals/claim/sky_tableland_head.mcfunction",
        "advancement revoke @s only cobblers:portals/claim/sky_tableland_head"),
}


def _strip(path, needle):
    path.write_text("\n".join(l for l in path.read_text(encoding="utf-8").splitlines()
                              if needle not in l) + "\n", encoding="utf-8")


def _append(path, line):
    path.write_text(path.read_text(encoding="utf-8") + line + "\n", encoding="utf-8")


def _json_set(path, key, value):
    d = json.loads(path.read_text(encoding="utf-8"))
    d[key] = value
    path.write_text(json.dumps(d), encoding="utf-8")


def test_the_audit_passes_the_pack_it_is_given(tmp_path, monkeypatch, built):
    out, _S = built
    pack = tmp_path / "datapacks" / "cobblers_portals"
    _write(pack, out)
    assert _run(monkeypatch, pack, tmp_path / "datapacks") == []


@pytest.mark.parametrize("why", sorted(CORRUPTIONS))
def test_the_audit_fails_on_a_broken_pack(tmp_path, monkeypatch, built, why):
    out, _S = built
    pack = tmp_path / "datapacks" / "cobblers_portals"
    _write(pack, out)
    before = sorted((f.relative_to(pack).as_posix(), f.read_text(encoding="utf-8")) for f in pack.rglob("*")
                    if f.is_file())
    CORRUPTIONS[why](pack)
    after = sorted((f.relative_to(pack).as_posix(), f.read_text(encoding="utf-8")) for f in pack.rglob("*")
                   if f.is_file())
    assert before != after, "the corruption %r changed nothing: the test would pass vacuously" % why
    bad = _run(monkeypatch, pack, tmp_path / "datapacks")
    assert bad, "the audit passed a pack broken by: %s" % why


def test_the_audit_refuses_a_pack_that_is_not_there(tmp_path, monkeypatch):
    assert _run(monkeypatch, tmp_path / "nothing", tmp_path)

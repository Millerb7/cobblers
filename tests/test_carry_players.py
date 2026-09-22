"""tools/carry_players.py: a re-export keeps what players earned, and the carry fails closed.

Offline: small fake worlds under tmp_path, laid out as Cobblemon 1.8, rctmod 0.19, CobbleDollars, TMCraft,
CobbleNav and Waystones lay out a real one (read from the staging export and the 2026-09-17 snapshot). Whether the
server loads a carried player is a runtime question (experiments/EXP-027-badge-flags).
"""
import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import carry_players as C  # noqa: E402
import level_dat as L  # noqa: E402

A = "aaaaaaaa-0000-0000-0000-000000000001"
B = "bbbbbbbb-0000-0000-0000-000000000002"


def _level_dat(hours_ago=0.5):
    ms = int((time.time() - hours_ago * 3600) * 1000)
    return L.dumps("", {"Data": (L.COMPOUND, {"LastPlayed": (L.LONG, ms)})})


def _rct(defeats):
    """rctmod 0.19's per-player record, as data/rctmod.player.<uuid>.stat.dat holds it."""
    return L.dumps("", {"data": (L.COMPOUND, {
        "progressDefeats": (L.COMPOUND, {t: (L.INT, n) for t, n in defeats.items()}),
        "currentSeries": (L.STRING, "kanto")})})


def _player(root, u, flags=("gym1_cleared",), defeats=None):
    defeats = {"kanto_brock": 1} if defeats is None else defeats
    files = {
        "playerdata/%s.dat" % u: "inventory and BalmData waystones",
        "playerdata/%s.dat_old" % u: "previous save",
        "advancements/%s.json" % u: json.dumps({"cobblers:flag/%s" % f: {"done": True} for f in flags}),
        "stats/%s.json" % u: "{}",
        "cobblemonplayerdata/%s/%s.json" % (u[:2], u): "{}",
        "pokedex/%s/%s.nbt" % (u[:2], u): "dex",
        "pokemon/pcstore/%s/%s.dat" % (u[:2], u): "pc",
        "pokemon/playerpartystore/%s/%s.dat" % (u[:2], u): "party",
        "cobbledollarsplayerdata/%s.json" % u: "{\"balance\": 5}",
        "data/rctmod.player.%s.stat.dat" % u: _rct(defeats),
        "tm_moves/%s/%s.nbt" % (u[:2], u): "tms",
        "cobblenav/spawndata/%s/%s.nbt" % (u[:2], u): "nav",
        "playermolangdata/%s.dat" % u: "quest fields and cursors",
    }
    for rel, content in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            (root / rel).write_bytes(content)
        else:
            (root / rel).write_text(content)
    return files


def _world(root, who=(A,), hours_ago=0.5):
    root.mkdir(parents=True)
    (root / "level.dat").write_bytes(_level_dat(hours_ago))
    (root / "data").mkdir()
    (root / "region").mkdir()
    (root / "region" / "r.0.0.mca").write_bytes(b"terrain")
    for u in who:
        _player(root, u)
    if who:
        (root / "data" / "rctmod.trainers.ver.dat").write_bytes(b"v")
        (root / "data" / "rctmod.trainers.0.mem").write_bytes(b"defeats")
        (root / "data" / "scoreboard.dat").write_bytes(b"scores")
        (root / "data" / "waystones.dat").write_bytes(b"old waystones")
        (root / "data" / "rctmod.spawn.chunks.map.dat").write_bytes(b"chunk bookkeeping")
    return root


@pytest.fixture
def worlds(tmp_path):
    return _world(tmp_path / "old", (A, B)), _world(tmp_path / "new", ())


def test_carry_takes_every_players_flags_party_pc_money_progress_and_quests(worlds, tmp_path):
    # Without this a re-export drops the badge flags, the party and PC, the balance, rctmod's progress (and so the
    # level cap), and our quest fields and dialogue cursors.
    old, new = worlds
    r = C.carry(old, new, tmp_path / "m.json")
    assert r["players"] == 2
    for u in (A, B):
        for rel in _player(tmp_path / "ref" / u, u):
            assert (new / rel).read_bytes() == (old / rel).read_bytes(), rel
    for rel in ("data/rctmod.trainers.ver.dat", "data/rctmod.trainers.0.mem", "data/scoreboard.dat"):
        assert (new / rel).read_bytes() == (old / rel).read_bytes()


def test_carry_leaves_terrain_waystones_and_spawn_bookkeeping_behind(worlds, tmp_path):
    # Without this the old waystone positions or rctmod's chunk bookkeeping would come back into the new world.
    old, new = worlds
    C.carry(old, new, tmp_path / "m.json")
    assert (new / "region" / "r.0.0.mca").read_bytes() == b"terrain"
    assert not (new / "data" / "waystones.dat").exists()
    assert not (new / "data" / "rctmod.spawn.chunks.map.dat").exists()


def test_carry_fails_when_there_is_no_player(tmp_path):
    # Fail closed: an old world with nobody in it (the wrong path) must not report a clean carry.
    old, new = _world(tmp_path / "old", ()), _world(tmp_path / "new", ())
    with pytest.raises(C.CarryError, match="nothing to carry"):
        C.carry(old, new, tmp_path / "m.json")


@pytest.mark.parametrize("missing", ["advancements/%s.json", "pokedex/aa/%s.nbt", "data/rctmod.player.%s.stat.dat",
                                     "cobbledollarsplayerdata/%s.json"])
def test_carry_fails_when_a_player_lacks_a_required_category(worlds, tmp_path, missing):
    # Without this a player whose flags or Pokedex were not where the tool looks would arrive without them, silently.
    old, new = worlds
    (old / (missing % A)).unlink()
    with pytest.raises(C.CarryError, match="player aaaaaaaa"):
        C.carry(old, new, tmp_path / "m.json")
    assert not (new / "playerdata").exists()


def test_carry_fails_on_an_empty_file(worlds, tmp_path):
    # An empty player file copies "successfully" and loses everything in it.
    old, new = worlds
    (old / "stats" / ("%s.json" % B)).write_bytes(b"")
    with pytest.raises(C.CarryError, match="empty file"):
        C.carry(old, new, tmp_path / "m.json")


def test_carry_refuses_to_overwrite_players_in_the_target(tmp_path):
    # Without this a carry into a world players have already joined would overwrite their newer state.
    old, new = _world(tmp_path / "old", (A,)), _world(tmp_path / "new", (B,))
    with pytest.raises(C.CarryError, match="not a fresh export"):
        C.carry(old, new, tmp_path / "m.json")


def test_carry_refuses_a_directory_that_is_not_a_world(tmp_path):
    old = _world(tmp_path / "old")
    (tmp_path / "empty").mkdir()
    with pytest.raises(C.CarryError, match="not a world"):
        C.carry(old, tmp_path / "empty", tmp_path / "m.json")


def test_verify_fails_when_a_carried_file_changed_or_went_missing(worlds, tmp_path):
    # The manifest check is what stands between the carry and the first boot: a changed or lost file must fail it.
    old, new = worlds
    C.carry(old, new, tmp_path / "m.json")
    assert C.verify(tmp_path / "m.json")["players"] == 2
    (new / "pokedex" / "aa" / ("%s.nbt" % A)).write_text("another dex")
    with pytest.raises(C.CarryError, match="differs"):
        C.verify(tmp_path / "m.json")
    (new / "playerdata" / ("%s.dat" % B)).unlink()
    with pytest.raises(C.CarryError, match="players: 2 in the old world, 1 in the new"):
        C.verify(tmp_path / "m.json")


def test_manifest_counts_every_category_before_and_after(worlds, tmp_path):
    old, new = worlds
    r = C.carry(old, new, tmp_path / "m.json")
    assert r["categories"]["advancements"] == {"before": 2, "after": 2}
    assert r["categories"]["pokemon"] == {"before": 4, "after": 4}
    assert r["categories"]["molang"] == {"before": 2, "after": 2}


def test_carry_refuses_a_stale_source_unless_rehearsal(tmp_path):
    # The live run carries from the world retired minutes ago. Without this an old copy would roll every player back.
    old, new = _world(tmp_path / "old", (A,), hours_ago=100), _world(tmp_path / "new", ())
    with pytest.raises(C.CarryError, match="last saved 100 hours ago"):
        C.carry(old, new, tmp_path / "m.json")
    assert C.carry(old, new, tmp_path / "m.json", rehearsal=True)["players"] == 1


def test_carry_refuses_a_retained_snapshot_unless_rehearsal(tmp_path):
    # A snapshot is for rehearsals: even a recently touched one is not the world being retired.
    old = _world(tmp_path / "2026-09-17-pre-grass" / "cobblers-10240", (A,))
    new = _world(tmp_path / "new", ())
    with pytest.raises(C.CarryError, match="rehearsals only"):
        C.carry(old, new, tmp_path / "m.json")
    assert C.carry(old, new, tmp_path / "m.json", rehearsal=True)["players"] == 1


@pytest.mark.parametrize("flags,defeats,says", [
    (("gym1_cleared",), {}, "gym1_cleared is set but rctmod records no defeat of kanto_brock"),
    ((), {"kanto_brock": 1}, "gym1_cleared is not set but rctmod records a defeat of kanto_brock"),
])
def test_carry_fails_when_badges_and_rctmod_disagree(tmp_path, flags, defeats, says):
    # The flags and rctmod's progress must travel together. A flag without the defeat: rctmod refuses the next
    # leader (missing_required_trainer). A defeat without the flag: the guards and waystones stay shut.
    old, new = _world(tmp_path / "old", ()), _world(tmp_path / "new", ())
    _player(old, A, flags=flags, defeats=defeats)
    (old / "data" / "rctmod.trainers.ver.dat").write_bytes(b"v")
    with pytest.raises(C.CarryError, match=says):
        C.carry(old, new, tmp_path / "m.json")


def test_verify_fails_when_rctmod_progress_did_not_arrive_with_the_flags(worlds, tmp_path):
    # Without this a carry that later lost rctmod's record (a half-restored world) would still verify.
    old, new = worlds
    C.carry(old, new, tmp_path / "m.json")
    (new / "data" / ("rctmod.player.%s.stat.dat" % A)).write_bytes(_rct({}))
    with pytest.raises(C.CarryError, match="gym1_cleared is set but rctmod records no defeat"):
        C.verify(tmp_path / "m.json")

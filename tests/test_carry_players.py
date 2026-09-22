"""tools/carry_players.py: a re-export keeps what players earned, and the carry fails closed.

Offline: small fake worlds under tmp_path. Whether the server loads a carried player is a runtime question
(experiments/EXP-027-badge-flags).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import carry_players as C  # noqa: E402

UUID = "aaaaaaaa-0000-0000-0000-000000000001"


def _world(root, players=True):
    root.mkdir(parents=True)
    (root / "level.dat").write_bytes(b"x")
    (root / "data").mkdir()
    (root / "region").mkdir()
    (root / "region" / "r.0.0.mca").write_bytes(b"terrain")
    if players:
        for d, name in (("playerdata", UUID + ".dat"), ("advancements", UUID + ".json"), ("stats", UUID + ".json"),
                        ("cobblemonplayerdata", UUID + ".json"), ("pokedex", UUID + ".nbt"),
                        ("pokemon/playerpartystore", UUID + ".dat")):
            (root / d).mkdir(parents=True, exist_ok=True)
            (root / d / name).write_text("%s of %s" % (d, UUID))
        (root / "data" / ("rctmod.player.%s.stat.dat" % UUID)).write_bytes(b"progress")
        (root / "data" / "rctmod.trainers.0.mem").write_bytes(b"defeats")
        (root / "data" / "scoreboard.dat").write_bytes(b"scores")
        (root / "data" / "waystones.dat").write_bytes(b"old waystones")
    return root


def test_carry_takes_the_badge_flags_party_and_rct_progress(tmp_path):
    # Without this a re-export would drop every player's badge flags (advancements), party and rctmod progress.
    old, new = _world(tmp_path / "old"), _world(tmp_path / "new", players=False)
    assert C.carry(old, new) == 0
    for rel in ("advancements/%s.json" % UUID, "playerdata/%s.dat" % UUID, "pokemon/playerpartystore/%s.dat" % UUID,
                "data/rctmod.player.%s.stat.dat" % UUID, "data/rctmod.trainers.0.mem", "data/scoreboard.dat"):
        assert (new / rel).read_bytes() == (old / rel).read_bytes(), rel


def test_carry_leaves_terrain_and_waystones_behind(tmp_path):
    # Without this the old terrain or the old waystone positions would come back into the new world.
    old, new = _world(tmp_path / "old"), _world(tmp_path / "new", players=False)
    assert C.carry(old, new) == 0
    assert (new / "region" / "r.0.0.mca").read_bytes() == b"terrain"
    assert not (new / "data" / "waystones.dat").exists()


def test_carry_fails_when_there_is_no_player(tmp_path, capsys):
    # Fail closed: an old world with nobody in it (the wrong path) must not report a clean carry.
    old, new = _world(tmp_path / "old", players=False), _world(tmp_path / "new", players=False)
    assert C.carry(old, new) == 1
    assert "nothing to carry" in capsys.readouterr().out


def test_carry_refuses_to_overwrite_players_in_the_target(tmp_path, capsys):
    # Without this a carry into a world players have already joined would overwrite their newer state.
    old, new = _world(tmp_path / "old"), _world(tmp_path / "new")
    assert C.carry(old, new) == 1
    assert "not a fresh export" in capsys.readouterr().out


def test_carry_refuses_a_directory_that_is_not_a_world(tmp_path, capsys):
    old = _world(tmp_path / "old")
    (tmp_path / "empty").mkdir()
    assert C.carry(old, tmp_path / "empty") == 1
    assert "not a world" in capsys.readouterr().out

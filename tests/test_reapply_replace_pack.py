"""tools/reapply.py replace_pack and install(): an installed pack holding files the build lacks is kept, never deleted.

Written by the test author, not by the session that wrote the change (e99a810, "Independent tests are owed").

Independent sources: the coordinator's contract for replace_pack(dest, src, retired_root) (2026-09-27): a copy with
files the build lacks is moved, not deleted, to <retired_root>/<date>-replaced-<name> keeping every file; an identical
or subset copy is replaced in place with nothing retired; with src None a stale copy with files is moved aside; a
fresh destination is installed; every replacement in install() goes through it, and no shutil.rmtree remains on a
pack destination except cobblers_restore and the global SPAWN_PACKS removal. The incident it answers: on 2026-09-26
an install deleted the only copy of a hand-installed template (the concrete-fixed Brock gym).

Offline: tmp_path folders only. install() is run end to end against a fake server tree under tmp_path with the port
probe, the suppression generator, the config install, the riding patch and the final install check stubbed; it never
opens a socket and never touches a real server.

Not covered: a real install on staging; what the operator does with a retired folder; a copy whose file has the same
path as a build file but different content (replaced, by the contract: "subset" is by path; see the report).
"""
from __future__ import annotations

import ast
import inspect
import re
import sys
import textwrap
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import reapply as RA  # noqa: E402

STAMP = re.compile(r"\d{4}-\d{2}-\d{2}-\d{6}-replaced-(.+)")


def tree(folder):
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in Path(folder).rglob("*") if p.is_file()}


def make(folder, files):
    for rel, body in files.items():
        p = Path(folder) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)
    return Path(folder)


BUILD = {"pack.mcmeta": b'{"pack":{"pack_format":48}}', "data/cobblers/function/a.mcfunction": b"say new"}


def retired_copies(root):
    return sorted(p for p in Path(root).iterdir()) if Path(root).exists() else []


# Without it the incident repeats: an installed copy holding a hand-added file (the concrete-fixed gym template) is
# deleted with the folder it sat in.
def test_a_copy_with_files_the_build_lacks_is_moved_aside_whole(tmp_path):
    src = make(tmp_path / "build" / "cobblers_towns", BUILD)
    old = {"pack.mcmeta": b"old", "data/cobblers/function/a.mcfunction": b"say old",
           "data/cobblers/structure/brock_gym_fixed.nbt": b"only copy"}
    dest = make(tmp_path / "server" / "datapacks" / "cobblers_towns", old)
    retired = tmp_path / "retired"
    RA.replace_pack(dest, src, retired)
    assert tree(dest) == BUILD, "the build is installed"
    kept = retired_copies(retired)
    assert len(kept) == 1 and STAMP.fullmatch(kept[0].name).group(1) == "cobblers_towns", kept
    assert tree(kept[0]) == old, "every file of the old copy is kept, the build-shadowed ones too"


# Without it an ordinary re-install (nothing hand-added) piles up retired copies, or leaves stale files behind.
@pytest.mark.parametrize("old", [dict(BUILD), {"pack.mcmeta": b"older"}, {}])
def test_an_identical_or_subset_copy_is_replaced_in_place_with_nothing_retired(tmp_path, old):
    src = make(tmp_path / "build" / "p", BUILD)
    dest = make(tmp_path / "dest" / "p", old)
    dest.mkdir(parents=True, exist_ok=True)
    RA.replace_pack(dest, src, tmp_path / "retired")
    assert tree(dest) == BUILD
    assert retired_copies(tmp_path / "retired") == []


# Without it a stale global copy of a world-local pack is deleted outright when it holds anything (src None: every file
# is one the build does not put there), and an empty stale folder is not cleaned up.
def test_with_no_source_a_stale_copy_with_files_is_moved_aside(tmp_path):
    stale = make(tmp_path / "server" / "datapacks" / "cobblers_scenes", {"pack.mcmeta": b"x", "data/f": b"y"})
    RA.replace_pack(stale, None, tmp_path / "retired")
    assert not stale.exists()
    kept = retired_copies(tmp_path / "retired")
    assert len(kept) == 1 and tree(kept[0]) == {"pack.mcmeta": b"x", "data/f": b"y"}
    empty = tmp_path / "server" / "datapacks" / "cobblers_empty"
    empty.mkdir(parents=True)
    RA.replace_pack(empty, None, tmp_path / "retired2")
    assert not empty.exists() and retired_copies(tmp_path / "retired2") == []


# Without it a first install onto a fresh world fails or installs nothing.
def test_a_fresh_destination_is_installed(tmp_path):
    src = make(tmp_path / "build" / "p", BUILD)
    dest = tmp_path / "world" / "datapacks" / "p"
    dest.parent.mkdir(parents=True)
    RA.replace_pack(dest, src, tmp_path / "retired")
    assert tree(dest) == BUILD and retired_copies(tmp_path / "retired") == []


# Without it a pack that was never built (a skipped prepare) deletes the installed copy before the final install check
# notices: the copy must survive somewhere.
def test_a_missing_build_never_deletes_the_installed_copy(tmp_path):
    dest = make(tmp_path / "dest" / "p", {"pack.mcmeta": b"x"})
    RA.replace_pack(dest, tmp_path / "build" / "not_built", tmp_path / "retired")
    kept = retired_copies(tmp_path / "retired")
    assert len(kept) == 1 and tree(kept[0]) == {"pack.mcmeta": b"x"}


# Without it the second of two copies retired in one second (a world-local pack's stale global copy, then its world
# copy, both named cobblers_scenes) lands inside the first one's folder instead of a folder of its own.
def test_two_copies_retired_in_one_second_each_get_their_own_folder(tmp_path, monkeypatch):
    import time
    monkeypatch.setattr(time, "strftime", lambda fmt, *a: "2026-09-27-120000")
    src = make(tmp_path / "build" / "cobblers_scenes", BUILD)
    glob_copy = make(tmp_path / "server" / "datapacks" / "cobblers_scenes", {"data/g": b"global"})
    world_copy = make(tmp_path / "world" / "datapacks" / "cobblers_scenes", {"data/w": b"world"})
    RA.replace_pack(glob_copy, None, tmp_path / "retired")
    RA.replace_pack(world_copy, src, tmp_path / "retired")
    kept = retired_copies(tmp_path / "retired")
    assert sorted((tree(k) for k in kept), key=lambda d: sorted(d)) == [{"data/g": b"global"}, {"data/w": b"world"}], \
        [(k.name, sorted(tree(k))) for k in kept]


# ------------------------------------------------------------------------------------------------ install(), as a whole

def _install_source():
    return textwrap.dedent(inspect.getsource(RA.install))


def _calls(node, owner, names):
    return [n for n in ast.walk(node) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr in names and isinstance(n.func.value, ast.Name) and n.func.value.id == owner]


# Without it a later edit brings back a bare rmtree + copytree on a pack destination and the incident with it: the only
# rmtree calls left in install() are the cobblers_restore removal and the global SPAWN_PACKS removal, and install()
# never copies a pack folder itself.
def test_install_replaces_packs_only_through_replace_pack():
    tree_ = ast.parse(_install_source())
    rm = [ast.unparse(c.args[0]) for c in _calls(tree_, "shutil", {"rmtree"})]
    assert sorted(rm) == sorted(["dp / 'cobblers_restore'", "dp / name"]), rm
    spawn_loops = [n for n in ast.walk(tree_) if isinstance(n, ast.For) and ast.unparse(n.iter) == "SPAWN_PACKS"
                   and _calls(n, "shutil", {"rmtree"})]
    assert len(spawn_loops) == 1, "the dp / name rmtree must be the global SPAWN_PACKS removal"
    assert not _calls(tree_, "shutil", {"copytree", "move"}), "install() copies packs itself"
    replaced = [ast.unparse(c.args[0]) for c in ast.walk(tree_)
                if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == "replace_pack"]
    assert sorted(replaced) == sorted(["stale", "dest", "wdp / src.name", "wdp / name"]), replaced


# Without it the retired copies land inside the server tree, where the next install (or the live world's datapack
# scan) would find them.
def test_the_retired_root_is_outside_the_server_tree():
    src = _install_source()
    assert 'retired = Path(a.server_dir).resolve().parent / "cobblers-server-retired"' in src
    assert src.count("replace_pack(") == 4 and all(", retired)" in l for l in src.splitlines() if "replace_pack(" in l)


@pytest.fixture
def fake_server(tmp_path, monkeypatch):
    """A server and world under tmp_path, a build of every pack install() installs, and every external step stubbed."""
    import socket
    import carry_players
    import install_check as IC
    import server_config_record as SCR

    class NoServer:
        def connect_ex(self, addr):
            return 111                                        # refused: nothing listens (never actually probed)

        def close(self):
            pass

    monkeypatch.setattr(socket, "socket", lambda *a, **k: NoServer())
    monkeypatch.setattr(carry_players, "players", lambda w: {"a"})
    monkeypatch.setattr(RA, "py", lambda *a, **k: None)
    monkeypatch.setattr(SCR, "install", lambda cfg: 0)
    monkeypatch.setattr(IC, "packs", lambda *a, **k: [])
    monkeypatch.setattr(IC, "configs", lambda *a, **k: [])
    build = tmp_path / "build"
    monkeypatch.setattr(RA, "PACKS", build)
    # the prepare gate has its own tests (tests/test_reapply_fail_closed.py); here a complete prepare is given
    monkeypatch.setattr(RA, "require_prepared", lambda what, names=None: {"checks": {"fingerprint": "f", "at": 1}})
    monkeypatch.setattr(RA, "INSTALLED", tmp_path / "install_record.json")
    for name in RA.SERVER_PACKS + RA.SPAWN_PACKS:
        make(build / name, dict(BUILD, **{"data/%s.txt" % name: name.encode()}))
    wp = tuple(make(tmp_path / "wp" / p.name, dict(BUILD)) for p in RA.WORLD_PACKS)
    monkeypatch.setattr(RA, "WORLD_PACKS", wp)
    patched = make(tmp_path / "cv", {"COBBLEVERSE-DP-v31.zip": b"zip"}) / "COBBLEVERSE-DP-v31.zip"
    monkeypatch.setattr(IC, "PATCHED_DP", patched)
    server = tmp_path / "servers" / "staging-server"
    (server / "datapacks").mkdir(parents=True)
    world = server.parent / "staging-world"
    (world / "datapacks").mkdir(parents=True)
    args = types.SimpleNamespace(server_dir=str(server), world_dir=str(world), no_players=False,
                                 cobbleverse_dp=str(patched))
    return server, world, args


# Without it one of install()'s paths (a server pack, a world-local pack and its stale global copy, a world pack, a
# spawn pack) still deletes a copy holding hand-added files; run end to end on a fake tree, every hand-added file must
# survive under the retired root, and every pack must be the build afterwards.
def test_an_install_keeps_every_hand_added_file_on_every_path(fake_server):
    server, world, args = fake_server
    gdp, wdp = server / "datapacks", world / "datapacks"
    extras = {}
    global_names = [n for n in RA.SERVER_PACKS if n not in RA.WORLD_LOCAL]
    local_names = [n for n in RA.SERVER_PACKS if n in RA.WORLD_LOCAL]
    cases = [(gdp / global_names[0], "server pack"), (wdp / local_names[0], "world-local pack"),
             (gdp / local_names[1], "stale global copy of a world-local pack"),
             (wdp / RA.WORLD_PACKS[0].name, "world pack"), (wdp / RA.SPAWN_PACKS[0], "spawn pack")]
    for folder, what in cases:
        rel = "data/cobblers/structure/hand_%s.nbt" % folder.name
        make(folder, {"pack.mcmeta": b"old", rel: what.encode()})
        extras[what] = (rel, what.encode())
    plain = gdp / global_names[1]
    make(plain, {"pack.mcmeta": b"old"})                       # nothing hand-added: replaced, not retired
    RA.install(args)
    retired = server.parent / "cobblers-server-retired"
    found = {}
    for p in retired.rglob("*"):
        if p.is_file():
            found.setdefault(p.read_bytes(), []).append(p)
    for what, (rel, body) in extras.items():
        assert body in found, "%s: the hand-added %s was deleted" % (what, rel)
    for name in global_names:
        assert tree(gdp / name) == tree(RA.PACKS / name), name
    for name in local_names:
        assert tree(wdp / name) == tree(RA.PACKS / name) and not (gdp / name).exists(), name
    assert tree(wdp / RA.WORLD_PACKS[0].name) == tree(RA.WORLD_PACKS[0])
    assert tree(wdp / RA.SPAWN_PACKS[0]) == tree(RA.PACKS / RA.SPAWN_PACKS[0])
    assert not [p for p in retired.iterdir() if p.name.endswith("-" + plain.name)], "a plain re-install was retired"
    assert not retired.resolve().is_relative_to(server.resolve())

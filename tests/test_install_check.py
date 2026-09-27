"""tools/install_check.py: "built but never installed" fails, and the live world is never read.

Fixtures are synthetic: a build folder holding one small pack per name in tools/reapply.py's real SERVER_PACKS,
SPAWN_PACKS and WORLD_PACKS (so the check runs over the real partition into global and world-local packs), a fake
patched COBBLEVERSE-DP zip, a staging server and a staging world under tmp_path, and a synthetic config record for
tools/server_config_record.py. No real server, world or build is read.

Not covered: that the installed packs load in the game or do what they are built for (runtime); that the real
`build/` is current (it is disposable and not in the repo); the world-local and world packs when no --world-dir is
given (by design the check then cannot see them).
"""
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import install_check as IC  # noqa: E402
import reapply as RA  # noqa: E402
import runtime_guard as G  # noqa: E402
import server_config_record as SCR  # noqa: E402

GLOBAL = [n for n in RA.SERVER_PACKS if n not in set(RA.WORLD_LOCAL)]
LOCAL = [n for n in RA.SERVER_PACKS if n in set(RA.WORLD_LOCAL)]
SPAWN_COMPARED = [n for n in RA.SPAWN_PACKS if n != "cobblers_suppress"]
WORLD_NAMES = [p.name for p in RA.WORLD_PACKS]


def make_pack(folder: Path, name: str):
    (folder / "data" / name / "function").mkdir(parents=True)
    (folder / "pack.mcmeta").write_text('{"pack": {"pack_format": 48, "description": "%s"}}' % name, encoding="utf-8")
    (folder / "data" / name / "function" / "load.mcfunction").write_text("say %s\n" % name, encoding="utf-8")


class Install:
    def __init__(self, tmp: Path):
        self.build = tmp / "repo" / "build" / "datapacks"
        self.height_src = tmp / "repo" / "modpack" / "datapacks" / "cobblers_height"
        self.dp_build = tmp / "repo" / "build" / "cobbleverse" / "COBBLEVERSE-DP-v31.zip"
        self.server = tmp / "staging-server"
        self.world = tmp / "staging-server" / "staging-world"
        self.gdp = self.server / "datapacks"
        self.wdp = self.world / "datapacks"

    def world_packs(self):
        return (self.height_src, self.build / "cobblers_worldtree")


@pytest.fixture
def inst(tmp_path, monkeypatch):
    """A staging server and world holding exactly what the synthetic build says they should."""
    monkeypatch.delenv(G.LOCK_ENV, raising=False)
    monkeypatch.delenv(G.OWNER_ENV, raising=False)
    s = Install(tmp_path)
    for name in list(RA.SERVER_PACKS) + list(RA.SPAWN_PACKS) + ["cobblers_worldtree"]:
        make_pack(s.build / name, name)
    make_pack(s.height_src, "cobblers_height")
    s.dp_build.parent.mkdir(parents=True)
    s.dp_build.write_bytes(b"PK riding-patched COBBLEVERSE-DP")
    monkeypatch.setattr(RA, "PACKS", s.build)
    monkeypatch.setattr(RA, "WORLD_PACKS", s.world_packs())
    monkeypatch.setattr(IC, "PATCHED_DP", s.dp_build)
    # installed, as tools/reapply.py install lays it out
    s.gdp.mkdir(parents=True)
    s.wdp.mkdir(parents=True)
    (s.world / "level.dat").write_bytes(b"staging")
    for name in GLOBAL:
        shutil.copytree(s.build / name, s.gdp / name)
    for name in LOCAL + list(RA.SPAWN_PACKS):
        shutil.copytree(s.build / name, s.wdp / name)
    for src in s.world_packs():
        shutil.copytree(src, s.wdp / src.name)
    shutil.copyfile(s.dp_build, s.gdp / s.dp_build.name)
    # packs the repo does not own sit beside ours and are not its business
    (s.gdp / "Terralith.zip").write_bytes(b"upstream")
    make_pack(s.gdp / "global_upstream_pack", "upstream")
    # a config record the server agrees with
    repo = tmp_path / "repo"
    for d in ("modpack/config", "server/config/mods", "base-pack/cobbleverse/config"):
        (repo / d).mkdir(parents=True)
    (repo / "modpack/config/rctmod-server.toml").write_text("maxTrainers = 0\n", encoding="utf-8")
    (s.server / "config").mkdir()
    (s.server / "config/rctmod-server.toml").write_text("# rewritten\nmaxTrainers = 0\n", encoding="utf-8")
    monkeypatch.setattr(SCR, "ROOT", repo)
    monkeypatch.setattr(SCR, "OVERLAY", repo / "modpack/config")
    monkeypatch.setattr(SCR, "MIRROR", repo / "server/config/mods")
    monkeypatch.setattr(SCR, "BASE", repo / "base-pack/cobbleverse/config")
    return s


def packs(s, world=True):
    return IC.packs(s.server, s.world if world else None)


def only_problem_about(problems, name):
    """At least one problem, and every problem is about this pack (a world-local pack found globally is reported by
    two rules, which is acceptable; a problem about another pack is not)."""
    assert problems, "no problem reported for %s" % name
    assert all(m.startswith(name + ":") for m in problems), problems


# ------------------------------------------------------------------ the fixture itself

def test_the_fixture_exercises_every_pack_group():
    # without this, a future reapply.py with an empty group would leave part of the check untested by these fixtures
    assert GLOBAL and LOCAL and SPAWN_COMPARED and WORLD_NAMES and "cobblers_suppress" in RA.SPAWN_PACKS


def test_a_complete_install_has_no_problems(inst):
    # without this, every fail-closed test below could pass on a check that reports everything
    assert packs(inst) == []
    assert packs(inst, world=False) == []
    assert IC.configs(inst.server) == []
    assert IC.main(["--server-dir", str(inst.server), "--world-dir", str(inst.world)]) == 0


# ------------------------------------------------------------------ fail closed: each fault is one problem

@pytest.mark.parametrize("group", ["global", "local", "spawn", "world"])
def test_a_missing_pack_is_a_problem(inst, group):
    # without this, a pack that was built but never installed (the structures pack, 2026-09-26) passes
    name, folder = {"global": (GLOBAL[0], inst.gdp), "local": (LOCAL[0], inst.wdp),
                    "spawn": (SPAWN_COMPARED[0], inst.wdp), "world": (WORLD_NAMES[0], inst.wdp)}[group]
    shutil.rmtree(folder / name)
    p = packs(inst)
    only_problem_about(p, name)
    assert "NOT INSTALLED" in p[0]


def test_a_generated_suppression_pack_missing_from_the_world_is_a_problem(inst):
    # without this, a world whose inherited spawns were never suppressed runs Cobbleverse's default spawns
    shutil.rmtree(inst.wdp / "cobblers_suppress")
    only_problem_about(packs(inst), "cobblers_suppress")


@pytest.mark.parametrize("change", ["byte", "extra", "missing"])
def test_an_installed_pack_that_differs_from_its_build_is_a_problem(inst, change):
    # without this, a stale or hand-edited install of a pack is taken for the current build
    for name, folder in ((GLOBAL[-1], inst.gdp), (LOCAL[-1], inst.wdp), (WORLD_NAMES[-1], inst.wdp)):
        f = folder / name / "data" / name / "function" / "load.mcfunction"
        if change == "byte":
            f.write_text("say stale\n", encoding="utf-8")
        elif change == "extra":
            (f.parent / "hand_added.mcfunction").write_text("say hi\n", encoding="utf-8")
        else:
            f.unlink()
        only_problem_about(packs(inst), name)
        shutil.rmtree(folder / name)
        shutil.copytree(inst.build / name if name != "cobblers_height" else inst.height_src, folder / name)
    assert packs(inst) == []


def test_a_pack_that_was_never_built_is_a_problem(inst):
    # without this, a missing build compares as "nothing to install" and the install check passes an empty build
    shutil.rmtree(inst.build / GLOBAL[0])
    shutil.rmtree(inst.gdp / GLOBAL[0])
    p = packs(inst)
    only_problem_about(p, GLOBAL[0])
    assert "not built" in p[0]


def test_a_stray_cobblers_pack_in_the_global_folder_is_a_problem(inst):
    # without this, a pack the repo no longer installs globally keeps running in every world, the live one included
    make_pack(inst.gdp / "cobblers_restore", "cobblers_restore")
    only_problem_about(packs(inst), "cobblers_restore")


@pytest.mark.parametrize("which", ["local", "spawn", "world"])
def test_a_world_pack_in_the_global_folder_is_a_problem(inst, which):
    # without this, a self-driving or spawn pack placed globally also acts in the live world (qa review of EXP-034)
    name = {"local": LOCAL[0], "spawn": RA.SPAWN_PACKS[0], "world": WORLD_NAMES[0]}[which]
    shutil.copytree(inst.wdp / name, inst.gdp / name)
    only_problem_about(packs(inst), name)
    only_problem_about(packs(inst, world=False), name)


@pytest.mark.parametrize("fault", ["wrong", "absent_on_server", "not_built"])
def test_the_patched_cobbleverse_datapack_must_be_the_build(inst, fault):
    # without this, the server keeps an unpatched COBBLEVERSE-DP and the 1.8 riding migration silently is not applied
    dp = inst.gdp / inst.dp_build.name
    if fault == "wrong":
        dp.write_bytes(b"PK upstream COBBLEVERSE-DP")
    elif fault == "absent_on_server":
        dp.unlink()
    else:
        inst.dp_build.unlink()
    only_problem_about(packs(inst), inst.dp_build.name)


def test_a_config_disagreement_is_a_problem(inst, capsys):
    # without this, install_check reports a clean server whose configs contradict the repo
    (inst.server / "config/rctmod-server.toml").write_text("maxTrainers = 5\n", encoding="utf-8")
    assert len(IC.configs(inst.server)) == 1
    assert IC.main(["--server-dir", str(inst.server), "--world-dir", str(inst.world)]) == 1
    assert "CONFIG rctmod-server.toml" in capsys.readouterr().out


def test_a_partial_install_reports_exactly_what_is_missing(inst):
    # without this, a half-finished install (some packs copied, the rest not) could report only its first gap or none;
    # the fixture keeps a nonempty part installed so the check is shown to tell the two halves apart
    kept, dropped = GLOBAL[::2], GLOBAL[1::2]
    assert kept and dropped
    for name in dropped:
        shutil.rmtree(inst.gdp / name)
    shutil.rmtree(inst.wdp / LOCAL[0])
    p = packs(inst)
    named = sorted(m.split(":", 1)[0] for m in p)
    assert named == sorted(dropped + [LOCAL[0]])
    assert all("NOT INSTALLED" in m for m in p)


def test_main_exits_nonzero_on_any_problem(inst, capsys):
    # without this, tools/reapply.py install and the session-start check would carry on past a missing pack
    shutil.rmtree(inst.gdp / GLOBAL[0])
    assert IC.main(["--server-dir", str(inst.server), "--world-dir", str(inst.world)]) == 1
    assert "PACK %s:" % GLOBAL[0] in capsys.readouterr().out


# ------------------------------------------------------------------ the live world is refused

def live_runtime(tmp_path, monkeypatch):
    """A synthetic tree shaped like the live runtime: cobblers-server/<world with level.dat and region/>."""
    server = tmp_path / "cobblers-server"
    world = server / "cobblers-10240"
    (world / "region").mkdir(parents=True)
    (world / "level.dat").write_bytes(b"live")
    (world / "datapacks").mkdir()
    (server / "datapacks").mkdir()
    (server / "config").mkdir()
    lock = tmp_path / "agent.lock"
    lock.write_text("owner: test-author\ntask: tests\n", encoding="utf-8")
    monkeypatch.setenv(G.LOCK_ENV, str(lock))
    monkeypatch.setenv(G.OWNER_ENV, "test-author")
    return server, world


def test_main_refuses_the_live_world_even_with_the_lock(tmp_path, monkeypatch):
    # without this, --world-dir pointed at the live world would hash its datapacks folder (CLAUDE.md forbids reading it)
    server, world = live_runtime(tmp_path, monkeypatch)
    called = []
    monkeypatch.setattr(IC, "packs", lambda *a: called.append(a) or [])
    with pytest.raises(G.RuntimeAccessRefused):
        IC.main(["--server-dir", str(server), "--world-dir", str(world)])
    assert called == []


def test_packs_refuses_the_server_runtime_without_the_lock(tmp_path, monkeypatch):
    # without this, the check could read the runtime's datapacks while another agent holds the coordination lock
    server, _ = live_runtime(tmp_path, monkeypatch)
    monkeypatch.delenv(G.OWNER_ENV)
    with pytest.raises(G.RuntimeAccessRefused):
        IC.packs(server)


@pytest.mark.xfail(strict=True, reason=(
    "tools/install_check.py:51-86: packs() passes only <server>/datapacks through runtime_guard; the world_dir it "
    "is given is read (compare() hashes <world>/datapacks/*) without a guard. Only main() (line 101) checks "
    "--world-dir. Latent today: the one other caller, tools/reapply.py install, guards the world first (line 311)."))
def test_packs_refuses_the_live_world_when_called_directly(tmp_path, monkeypatch):
    # without this, any new caller of packs() can read the live world's datapacks folder while holding the lock
    server, world = live_runtime(tmp_path, monkeypatch)
    with pytest.raises(G.RuntimeAccessRefused):
        IC.packs(server, world)

"""`reapply.py strip`, the `run` refusal it implies, and install_check's view of a stripped install.

Written by the same session that wrote strip (the brief asked for both): an independent review is still owed.

Synthetic: a staging server and world under tmp_path (never under a directory named cobblers-server, so the runtime
guard needs no lock), packs named from tools/reapply.py's real lists, and a hand-written build/pack_roles.json. What a
mistake here costs: a runtime pack moved out of a world (its keeper, callbacks and doors gone), or a re-apply step that
runs into "Unknown function" half way through an apply.
"""
import argparse
import json
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import install_check as IC  # noqa: E402
import reapply as RA  # noqa: E402
from test_install_check import inst, make_pack  # noqa: E402,F401  (the staging install fixture)

BUILD_GLOBAL = "cobblers_rift"              # a global pack, classed build in the fixture roles
BUILD_LOCAL = "cobblers_dungeons_build"     # a world-local one
RUNTIME = "cobblers_scenes"                 # world-local, runtime


def write_roles(path, packs_dir, steps=None, runtime_override=()):
    names = list(RA.SERVER_PACKS) + list(RA.SPAWN_PACKS) + [Path(p).name for p in RA.WORLD_PACKS]
    rep = {"packs_dir": str(packs_dir), "everything_reachable": False,
           "packs": {n: {"role": "build" if n in (BUILD_GLOBAL, BUILD_LOCAL) and n not in runtime_override else "runtime",
                         "lines": 100 if n in (BUILD_GLOBAL, BUILD_LOCAL) else 1, "why": []} for n in names},
           "totals": {"lines": 1000}, "steps": steps if steps is not None else {"R9": [BUILD_GLOBAL], "R1": [RUNTIME]}}
    path.write_text(json.dumps(rep), encoding="utf-8")
    return path


@pytest.fixture
def staged(inst, tmp_path, monkeypatch):
    """The installed staging fixture, with a recorded install and roles, and strip's outside hooks pinned."""
    record = tmp_path / "repo" / "build" / "install_record.json"
    record.write_text(json.dumps({str(inst.server.resolve()): {"world_dir": str(inst.world), "prepare": "p"}}),
                      encoding="utf-8")
    roles = write_roles(tmp_path / "repo" / "build" / "pack_roles.json", inst.build)
    monkeypatch.setattr(RA, "INSTALLED", record)
    monkeypatch.setattr(RA, "ROLES", roles)
    monkeypatch.setattr(RA, "server_running", lambda: [])
    monkeypatch.setattr(RA, "require_installed",
                        lambda server_dir: json.loads(record.read_text(encoding="utf-8"))[str(Path(server_dir).resolve())])
    inst.record, inst.roles = record, roles
    return inst


def strip_args(s):
    return argparse.Namespace(server_dir=str(s.server), world_dir=str(s.world))


# ------------------------------------------------------------------ strip

def test_strip_moves_only_build_packs_and_records_where(staged):
    # without it: a strip that deletes cannot be undone, and one that moves a runtime pack breaks the world
    RA.strip(strip_args(staged))
    assert not (staged.gdp / BUILD_GLOBAL).exists() and not (staged.wdp / BUILD_LOCAL).exists()
    assert (staged.wdp / RUNTIME).is_dir()
    rec = json.loads(staged.record.read_text(encoding="utf-8"))[str(staged.server.resolve())]
    assert set(rec["stripped"]) == {BUILD_GLOBAL, BUILD_LOCAL}
    for name, r in rec["stripped"].items():
        held = Path(r["to"])
        assert held.is_dir() and (held / "pack.mcmeta").is_file(), "moved, never deleted"
        assert "cobblers-server-retired" in held.parts
        assert staged.server.resolve() not in held.resolve().parents, "held OUTSIDE the server's folders"
    assert rec["stripped"][BUILD_LOCAL]["folder"] == "world" and rec["stripped"][BUILD_GLOBAL]["folder"] == "global"


def test_strip_refuses_while_the_server_may_run_and_moves_nothing(staged, monkeypatch):
    monkeypatch.setattr(RA, "server_running", lambda: ["port 25565 is in use"])
    with pytest.raises(SystemExit) as e:
        RA.strip(strip_args(staged))
    assert "refused" in str(e.value.code) and "25565" in str(e.value.code)
    assert (staged.gdp / BUILD_GLOBAL).is_dir() and (staged.wdp / BUILD_LOCAL).is_dir()


def test_strip_refuses_a_pack_that_is_not_installed_as_built(staged):
    (staged.gdp / BUILD_GLOBAL / "data" / "extra.txt").write_text("someone's", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        RA.strip(strip_args(staged))
    assert "nothing moved" in str(e.value.code)
    assert (staged.wdp / BUILD_LOCAL).is_dir()


def test_strip_refuses_roles_that_reach_everything(staged):
    rep = json.loads(staged.roles.read_text(encoding="utf-8"))
    rep["everything_reachable"] = True
    staged.roles.write_text(json.dumps(rep), encoding="utf-8")
    with pytest.raises(SystemExit):
        RA.strip(strip_args(staged))
    assert (staged.gdp / BUILD_GLOBAL).is_dir()


class _Done(Exception):
    pass


def test_server_running_sees_a_java_process(monkeypatch):
    class Sock:
        def connect_ex(self, addr):
            return 1

        def close(self):
            pass
    monkeypatch.setattr(socket, "socket", Sock)
    java = '"java.exe","4242","Console","1","9,000,000 K"\n' if RA.os.name == "nt" else "java\n"
    monkeypatch.setattr(RA.subprocess, "run",
                        lambda c, **k: subprocess.CompletedProcess(c, 0, stdout=java, stderr=""))
    assert any("java" in w for w in RA.server_running())
    none = "INFO: No tasks are running which match the specified criteria.\n" if RA.os.name == "nt" else "bash\n"
    monkeypatch.setattr(RA.subprocess, "run",
                        lambda c, **k: subprocess.CompletedProcess(c, 0, stdout=none, stderr=""))
    assert RA.server_running() == []
    # fail closed: a process list that cannot be read is a reason, not a pass
    monkeypatch.setattr(RA.subprocess, "run", lambda c, **k: subprocess.CompletedProcess(c, 1, stdout="", stderr="x"))
    assert RA.server_running()


# ------------------------------------------------------------------ run after a strip

def run_args(s, only=None):
    return argparse.Namespace(server_dir=str(s.server), only=only, from_step=None, with_spawns=False, no_reload=True)


@pytest.fixture
def stripped_run(staged, tmp_path, monkeypatch):
    RA.strip(strip_args(staged))
    monkeypatch.setattr(RA, "OUT", tmp_path / "derived_reapply")
    monkeypatch.setattr(RA, "steps", lambda with_spawns=False: [("R1", "scenes", [("fn", "cobblers:scenes/x")]),
                                                                ("R9", "the Rift", [("fn", "cobblers:rift/x")])])

    def no_rcon(server_dir):
        raise _Done("reached RCON")
    monkeypatch.setattr(RA, "Rcon", no_rcon)
    return staged


def test_run_refuses_a_step_that_needs_a_stripped_pack_before_any_rcon(stripped_run):
    with pytest.raises(SystemExit) as e:
        RA.run(run_args(stripped_run, only="R9"))
    msg = str(e.value.code)
    assert "R9 needs %s" % BUILD_GLOBAL in msg and "reapply.py install" in msg


def test_run_goes_on_when_no_selected_step_needs_a_stripped_pack(stripped_run):
    with pytest.raises(_Done):                     # got past the check to the first RCON connection
        RA.run(run_args(stripped_run, only="R1"))


def test_run_refuses_a_step_the_roles_do_not_know_once_anything_is_stripped(stripped_run):
    write_roles(stripped_run.roles, stripped_run.build, steps={"R1": [RUNTIME]})
    with pytest.raises(SystemExit) as e:
        RA.run(run_args(stripped_run, only="R9"))
    assert "R9 needs" in str(e.value.code)


def test_run_refuses_when_packs_are_stripped_and_the_roles_are_gone(stripped_run):
    stripped_run.roles.unlink()
    with pytest.raises(SystemExit) as e:
        RA.run(run_args(stripped_run, only="R1"))
    assert "stripped" in str(e.value.code)


# ------------------------------------------------------------------ install_check after a strip

def test_install_check_accepts_a_stripped_build_pack_as_absent(stripped_run):
    assert IC.packs(stripped_run.server, stripped_run.world, record=stripped_run.record, roles=stripped_run.roles) == []


def test_install_check_still_fails_on_a_missing_runtime_pack(stripped_run):
    shutil.rmtree(stripped_run.wdp / RUNTIME)
    problems = IC.packs(stripped_run.server, stripped_run.world, record=stripped_run.record, roles=stripped_run.roles)
    assert any(p.startswith(RUNTIME + ":") and "NOT INSTALLED" in p for p in problems), problems


def test_install_check_fails_a_stripped_pack_the_roles_call_runtime(stripped_run):
    write_roles(stripped_run.roles, stripped_run.build, runtime_override=(BUILD_LOCAL,))
    problems = IC.packs(stripped_run.server, stripped_run.world, record=stripped_run.record, roles=stripped_run.roles)
    assert any(p.startswith(BUILD_LOCAL + ":") and "runtime" in p for p in problems), problems


def test_install_check_without_a_record_still_wants_every_pack(staged):
    shutil.rmtree(staged.gdp / BUILD_GLOBAL)
    problems = IC.packs(staged.server, staged.world, record=staged.record, roles=staged.roles)
    assert any(p.startswith(BUILD_GLOBAL + ":") and "NOT INSTALLED" in p for p in problems), problems

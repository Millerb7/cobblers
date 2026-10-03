"""reapply.py fails closed between its phases (the owner, 2026-10-03: "prepare RESUMES PAST A FAILED STEP").

A failed prepare job used to stop that pass, but `prepare --from <the next job>` skipped it and still ended on
"prepared ... every function pack covered", and install and run asked nothing about prepare. These tests drive
prepare, install and run with fake jobs, a fake RCON and a ledger under tmp_path -- never a server, a world or the real
build/ -- and each gate is also proved by mutating the code path it lives in (CLAUDE.md: mutate the generator, not the
record): with the line that makes it bite changed, the same scenario must come out wrong.
"""
from __future__ import annotations

import ast
import inspect
import json
import sys
import textwrap
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import reapply as RA  # noqa: E402


# ------------------------------------------------------------------------------------------------------- helpers

def mutate(monkeypatch, name, old, new):
    """Replace RA.<name> with a copy whose source has `old` replaced by `new`, bound to the real module globals so
    every other monkeypatch still applies. Fails if `old` is not in the source (the mutation must hit real code)."""
    src = textwrap.dedent(inspect.getsource(getattr(RA, name)))
    assert old in src, "mutation target not found in %s: %r" % (name, old)
    scratch = {}
    exec(compile(src.replace(old, new, 1), RA.__file__, "exec"), dict(RA.__dict__), scratch)
    orig = getattr(RA, name)
    fn = types.FunctionType(scratch[name].__code__, RA.__dict__, name, orig.__defaults__)
    monkeypatch.setattr(RA, name, fn)


class Fingerprint:
    def __init__(self):
        self.values = ["fp1"]

    def __call__(self, root=None):
        v = self.values.pop(0) if len(self.values) > 1 else self.values[0]
        return v, {"data/x.json": v}


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    """Four fake jobs (a, b, c, d) whose failure is switched by `broken`; the ledger and install record in tmp_path."""
    broken, ran = set(), []

    def job(n):
        def go():
            ran.append(n)
            if n in broken:
                raise SystemExit("failed: %s.py" % n)
        return go

    fp = Fingerprint()
    monkeypatch.setattr(RA, "STAMP", tmp_path / "prepare_stamp.json")
    monkeypatch.setattr(RA, "INSTALLED", tmp_path / "install_record.json")
    monkeypatch.setattr(RA, "prepare_jobs", lambda a: [(n, job(n)) for n in "abcd"])
    monkeypatch.setattr(RA, "input_fingerprint", fp)
    monkeypatch.setattr(RA, "git_head", lambda: "0123456789abcdef")
    monkeypatch.setattr(RA, "_prepare_checks", lambda t0: "checks passed")
    return types.SimpleNamespace(broken=broken, ran=ran, fp=fp, tmp=tmp_path)


def prep(only=None, from_job=None):
    """prepare's outcome: (exit code as main() would return it, the last message)."""
    try:
        r = RA.prepare(types.SimpleNamespace(list=False, only=only, from_job=from_job))
    except SystemExit as e:
        return (1 if e.code else 0), str(e.code)
    return (r or 0), ""


def complete():
    try:
        RA.require_prepared("test")
    except SystemExit as e:
        return False, str(e.code)
    return True, ""


# ------------------------------------------------------------------------------------------------------- prepare

# Without it a failing job lets prepare go on, or exit 0, or end without naming the job.
def test_a_failed_job_stops_prepare_non_zero_and_names_it(ledger):
    ledger.broken.add("b")
    code, msg = prep()
    assert code != 0
    assert "PREPARE FAILED at job b" in msg and "failed: b.py" in msg
    assert "c, d" in msg, "the jobs the pass never reached are not named"
    assert ledger.ran == ["a", "b"], "a job after the failure ran"
    assert json.loads(RA.STAMP.read_text())["jobs"]["b"]["status"] == "failed"
    assert not complete()[0]


# The incident: `--from` the job after the failure ran clean and printed success. Now it exits non-zero and names b.
def test_resuming_past_a_failed_job_is_incomplete_and_names_it(ledger):
    ledger.broken.add("b")
    prep()
    ledger.ran.clear()
    code, msg = prep(from_job="c")
    assert ledger.ran == ["c", "d"]
    assert code != 0 and "PREPARE INCOMPLETE" in msg
    assert "b: FAILED (failed: b.py)" in msg
    assert "c: ran while an earlier job had not succeeded" in msg
    ok, why = complete()
    assert not ok and "b: FAILED" in why


def test_the_same_scenario_passes_when_a_failure_is_recorded_as_ok(ledger, monkeypatch):
    mutate(monkeypatch, "_run_jobs", 'recs[name] = {"status": "failed"', 'recs[name] = {"status": "ok", "upstream_ok": True')
    ledger.broken.add("b")
    prep()
    code, _ = prep(from_job="c")
    assert code == 0 and complete()[0], "the mutant should have resumed past b: the gate is not what catches it"


# Recovery stays possible: re-run the failed job, then the jobs after it, and the build is complete.
def test_recovery_by_only_then_from_completes_the_build(ledger):
    ledger.broken.add("b")
    prep()
    ledger.broken.clear()
    code, msg = prep(only="b")
    assert code != 0 and "c: ran while an earlier job had not succeeded" not in msg, msg
    assert "c: never ran" in msg and "d: never ran" in msg
    code, msg = prep(from_job="c")
    assert code == 0, msg
    assert complete()[0]


# But resuming in the wrong order (the jobs after b ran while b was still failed) is not complete.
def test_jobs_run_while_an_earlier_one_was_failed_stay_stale_after_it_is_fixed(ledger):
    ledger.broken.add("b")
    prep()
    prep(from_job="c")
    ledger.broken.clear()
    code, msg = prep(only="b")
    assert code != 0
    assert "c: ran while an earlier job had not succeeded" in msg and "d: ran while" in msg
    assert prep(from_job="c")[0] == 0 and complete()[0]


def test_wrong_order_recovery_passes_when_upstream_is_not_checked(ledger, monkeypatch):
    mutate(monkeypatch, "job_valid", ' and rec.get("upstream_ok") is True', "")
    mutate(monkeypatch, "stamp_problems", 'elif rec.get("upstream_ok") is not True:', "elif False:")
    ledger.broken.add("b")
    prep()
    prep(from_job="c")
    ledger.broken.clear()
    assert prep(only="b")[0] == 0, "the mutant should accept c and d run before b was fixed"


# Without it a partial prepare on a fresh ledger is reported as a build.
def test_a_partial_prepare_on_a_fresh_build_is_not_complete(ledger):
    code, msg = prep(only="a,b")
    assert code != 0 and "c: never ran" in msg and "d: never ran" in msg
    assert not complete()[0]


def test_a_full_clean_prepare_is_complete_and_says_so(ledger, capsys):
    assert prep() == (0, "")
    assert "PREPARE COMPLETE: all 4 jobs" in capsys.readouterr().out
    assert complete()[0]


# Without it a build prepared before an edit to data/ or tools/ is installed as if it were current.
def test_a_change_to_data_or_tools_after_prepare_makes_the_build_stale(ledger):
    assert prep()[0] == 0
    ledger.fp.values = ["fp2"]
    ok, why = complete()
    assert not ok and "a: last ran before the latest change to data/ or tools/" in why


def test_the_stale_build_passes_when_the_gate_trusts_the_stamps_own_fingerprint(ledger, monkeypatch):
    mutate(monkeypatch, "require_prepared", "fp, _ = input_fingerprint()", 'fp = stamp.get("fingerprint")')
    assert prep()[0] == 0
    ledger.fp.values = ["fp2"]
    assert complete()[0], "the mutant reads the expectation from the artifact it checks"


# Without it a job that rewrites data/ or tools/ mid-pass leaves the earlier jobs built from other inputs.
def test_inputs_changed_during_the_pass_are_named_and_incomplete(ledger):
    ledger.fp.values = ["fp1", "fp2"]
    code, msg = prep()
    assert code != 0 and "data/ or tools/ changed during the pass: data/x.json" in msg


# Without it the whole-build checks failing still leaves a complete stamp from an earlier pass.
def test_failed_whole_build_checks_stop_and_unstamp(ledger, monkeypatch):
    assert prep()[0] == 0

    def bad(t0):
        raise SystemExit("function_limits found problems: nothing may be installed until it reports 0")
    monkeypatch.setattr(RA, "_prepare_checks", bad)
    code, msg = prep(only="a")
    assert code != 0 and "PREPARE FAILED at the whole-build checks" in msg and "function_limits" in msg
    ok, why = complete()
    assert not ok and "checks: FAILED" in why


# ------------------------------------------------------------------------------------------------------- install

class _NoServer:
    def connect_ex(self, addr):
        return 111

    def close(self):
        pass


def _install_args(tmp):
    server, world = tmp / "server", tmp / "world"
    (server / "datapacks").mkdir(parents=True)
    (world / "datapacks").mkdir(parents=True)
    return types.SimpleNamespace(server_dir=str(server), world_dir=str(world), no_players=True, cobbleverse_dp=None)


def test_install_refuses_an_incomplete_prepare_and_copies_nothing(ledger, monkeypatch):
    import socket
    monkeypatch.setattr(socket, "socket", lambda *a, **k: _NoServer())
    ledger.broken.add("b")
    prep()
    args = _install_args(ledger.tmp)
    with pytest.raises(SystemExit) as e:
        RA.install(args)
    assert "reapply install refused" in str(e.value.code) and "b: FAILED" in str(e.value.code)
    assert not any((Path(args.server_dir) / "datapacks").iterdir())


def test_install_refuses_a_pack_missing_from_the_build_before_copying(ledger, monkeypatch):
    import socket
    monkeypatch.setattr(socket, "socket", lambda *a, **k: _NoServer())
    assert prep()[0] == 0
    build = ledger.tmp / "build"
    monkeypatch.setattr(RA, "PACKS", build)
    for n in RA.SERVER_PACKS + RA.SPAWN_PACKS:
        if n != "cobblers_shrines":
            (build / n).mkdir(parents=True)
            (build / n / "pack.mcmeta").write_text("{}")
    wp = []
    for p in RA.WORLD_PACKS:
        (ledger.tmp / "wp" / p.name).mkdir(parents=True)
        (ledger.tmp / "wp" / p.name / "pack.mcmeta").write_text("{}")
        wp.append(ledger.tmp / "wp" / p.name)
    monkeypatch.setattr(RA, "WORLD_PACKS", tuple(wp))
    args = _install_args(ledger.tmp)
    with pytest.raises(SystemExit) as e:
        RA.install(args)
    assert "cobblers_shrines" in str(e.value.code) and "nothing was copied" in str(e.value.code)
    assert not any((Path(args.server_dir) / "datapacks").iterdir())


# install() gates before it touches anything: the prepare check and the build check come before every copy, removal,
# generator and record of success.
def test_install_checks_the_prepare_before_it_touches_anything():
    tree = ast.parse(textwrap.dedent(inspect.getsource(RA.install)))
    body = tree.body[0].body
    src = [ast.unparse(s) for s in body]
    gate = next(i for i, s in enumerate(src) if "require_prepared(" in s)
    first_touch = next(i for i, s in enumerate(src) if any(k in s for k in
                       ("replace_pack(", "shutil.", "py(", "runtime_guard", "SCR.install", "done=True")))
    assert gate < first_touch, (src[gate], src[first_touch])
    assert src[-2].startswith("_record_install(") and "done=True" in src[-2], "success is recorded before the final check"


# ------------------------------------------------------------------------------------------------------- the install record

def test_run_needs_an_install_of_the_current_complete_prepare(ledger):
    assert prep()[0] == 0
    server = ledger.tmp / "server"
    with pytest.raises(SystemExit, match="no completed `reapply.py install`"):
        RA.require_installed(server)
    stamp = RA.load_stamp()
    RA._record_install(server, ledger.tmp / "world", stamp, done=True)
    assert RA.require_installed(server)["prepare"] == RA.stamp_id(stamp)
    # a new prepare after the install: the server holds the old build
    assert prep(only="a")[0] == 0
    with pytest.raises(SystemExit, match="install it first"):
        RA.require_installed(server)
    # an install that started and did not finish is no install
    RA._record_install(server, ledger.tmp / "world", RA.load_stamp(), done=False)
    with pytest.raises(SystemExit, match="no completed"):
        RA.require_installed(server)


# ------------------------------------------------------------------------------------------------------- run

class FakeRcon:
    def __init__(self, replies=None, raise_on=None):
        self.cmds, self.replies, self.raise_on = [], replies or {}, raise_on

    def __call__(self, cmd, timeout=None):
        self.cmds.append(cmd)
        if self.raise_on and self.raise_on in cmd:
            raise ConnectionError("RCON connection lost")
        for k, v in self.replies.items():
            if k in cmd:
                return v
        if cmd.startswith("function "):
            return "Running function %s" % cmd.split()[1]
        return ""


STEPS = [("R1", "one", [("fn", "cobblers:one")]),
         ("R2", "two", [("fn", "cobblers:two"), ("cmd", "forceload add 0 0"), ("fn", "cobblers:two_b")]),
         ("R3", "three", [("fn", "cobblers:three")])]


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setattr(RA, "OUT", tmp_path / "out")
    monkeypatch.setattr(RA, "steps", lambda *a, **k: STEPS)
    monkeypatch.setattr(RA, "require_installed", lambda d: {"prepare": "fp@1"})
    monkeypatch.setattr(RA.time, "sleep", lambda s: None)

    def go(rcon, only=None, from_step=None):
        monkeypatch.setattr(RA, "Rcon", lambda d: rcon)
        args = types.SimpleNamespace(server_dir=str(tmp_path / "s"), with_spawns=False, only=only, from_step=from_step,
                                     no_reload=True)
        try:
            RA.run(args)
            code, msg = 0, ""
        except SystemExit as e:
            code, msg = (1 if e.code else 0), str(e.code)
        recs = sorted((tmp_path / "out").glob("run_*.json"))
        return code, msg, json.loads(recs[-1].read_text()) if recs else None
    return go


def test_run_refuses_before_rcon_without_an_install_of_the_current_prepare(ledger, monkeypatch, tmp_path):
    made = []
    monkeypatch.setattr(RA, "Rcon", lambda d: made.append(d))
    with pytest.raises(SystemExit, match="reapply run refused"):
        RA.run(types.SimpleNamespace(server_dir=str(tmp_path / "s"), with_spawns=False, only=None, from_step=None,
                                     no_reload=True))
    assert made == [], "RCON was opened before the gate"


def test_a_bad_function_reply_stops_the_run_non_zero_and_is_named(server):
    rc = FakeRcon({"function cobblers:two_b": "Unknown function cobblers:two_b"})
    code, msg, rec = server(rc)
    assert code != 0
    assert "RUN STOPPED at R2" in msg and "cobblers:two_b: Unknown function" in msg
    assert rec["stopped_at"] == "R2" and rec["steps"][1]["problems"] == ["cobblers:two_b: Unknown function cobblers:two_b"]
    assert not any("cobblers:three" in c for c in rc.cmds), "R3 ran after R2's problem"


def test_a_command_vanilla_could_not_parse_is_a_problem(server):
    rc = FakeRcon({"forceload add 0 0": "Unknown or incomplete command, see below for error ...<--[HERE]"})
    code, msg, rec = server(rc)
    assert code != 0 and "R2" in msg and "forceload add 0 0" in msg
    assert rec["steps"][1]["problems"]


def test_an_unparsed_command_passes_when_cmd_replies_are_not_checked(server, monkeypatch):
    mutate(monkeypatch, "_run_steps", "if any(m in r for m in COMMAND_ERRORS):", "if False:")
    rc = FakeRcon({"forceload add 0 0": "Unknown or incomplete command, see below for error ...<--[HERE]"})
    assert server(rc)[0] == 0, "the mutant should have reported the bad command clean"


# Without it a step that raises mid-way (RCON dropped) is missing from the record, and the record says nothing.
def test_a_step_that_raises_is_recorded_with_its_problem(server):
    code, msg, rec = server(FakeRcon(raise_on="cobblers:two_b"))
    assert code != 0 and "RUN STOPPED at R2" in msg and "RCON connection lost" in msg
    assert rec["stopped_at"] == "R2"
    assert [s["step"] for s in rec["steps"]] == ["R1", "R2"]
    assert "RCON connection lost" in rec["steps"][1]["problems"][-1]


def test_a_raising_step_goes_unrecorded_without_the_live_step(server, monkeypatch):
    mutate(monkeypatch, "_run_steps", "live.update(sid=sid, title=title, bad=bad)", "pass")
    code, msg, rec = server(FakeRcon(raise_on="cobblers:two_b"))
    assert [s["step"] for s in rec["steps"]] == ["R1"], "the mutant should have lost R2 from the record"


def test_a_clean_partial_run_says_it_was_partial(server, capsys):
    code, msg, rec = server(FakeRcon(), only="R1,R3")
    out = capsys.readouterr().out
    assert code == 0 and "PARTIAL run (--only R1,R3): 2 of 3 steps" in out
    assert rec["selection"] == "--only R1,R3" and rec["of_steps"] == 3 and rec["prepare"] == "fp@1"


def test_a_clean_full_run_says_all_steps_and_zero_problems(server, capsys):
    code, msg, rec = server(FakeRcon())
    assert code == 0 and "run complete, 0 problems: ALL 3 steps" in capsys.readouterr().out


def test_run_from_an_unknown_step_is_refused(server):
    code, msg, rec = server(FakeRcon(), from_step="R9")
    assert code != 0 and "no step named R9" in msg


# The real fingerprint covers data/ and tools/ by content, and ignores bytecode.
def test_the_fingerprint_reads_content_not_bytecode(tmp_path):
    for d in RA.INPUT_DIRS:
        (tmp_path / d / "__pycache__").mkdir(parents=True)
        (tmp_path / d / "a.json").write_text("1")
    fp1, files = RA.input_fingerprint(tmp_path)
    assert sorted(files) == ["data/a.json", "tools/a.json"]
    (tmp_path / "tools" / "__pycache__" / "x.pyc").write_bytes(b"x")
    assert RA.input_fingerprint(tmp_path)[0] == fp1
    (tmp_path / "data" / "a.json").write_text("2")
    assert RA.input_fingerprint(tmp_path)[0] != fp1

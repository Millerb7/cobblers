"""tools/id_authorship.py + data/id_authorship.json: no id in data/ may have two authors unnoticed.

Written by the test author. The tool, the registry and route_trainers.py's field-level guard were
written by another session (commit 41f2255); this file is their first test and shares no code with them.

WHAT THIS PROTECTS. git merges text, so two branches that author the same ids in DIFFERENT FILES never
conflict: the merge is clean, the diff is clean, and nothing says that one thing now has two authors.
On 2026-10-01 that gave Victory Road's tenth trainer two names, two teams and two sets of lines
(CLAUDE.md, "A clean merge is not a clean union"). The only thing that noticed was
tools/route_trainers.py failing closed during pytest COLLECTION, which turned 5,200 tests into
`no tests ran` plus an INTERNALERROR for six hours -- no count, no red test, nothing comparable with the
run before it. So two things are asserted here: that the declaration-or-fault check bites, and that a
tool failing closed at import still costs one module and not the run.

HOW THE MUTATION PROOFS WORK (CLAUDE.md, "Mutate the GENERATOR, not the record"). A check whose
expectation comes from the thing it checks passes happily on a shared mistake. Every proof below either
changes the tool's own code (test_the_registry_is_not_derived_from_the_tool mutates
route_trainers.STAND_FIELDS in memory) or builds a MUTATED COPY of the whole real data/ tree under
tmp_path and points records()/--root at it. None of them relaxes a declaration in
data/id_authorship.json, and none of them edits the repository: the registry and the tool are read
exactly as committed, and the copy is thrown away with the temp directory.

The split is stated twice on purpose -- once in data/id_authorship.json's trainers space, once in
tools/route_trainers.py's STAND_FIELDS / ROSTER_ECHO / ROSTER_PRECEDENCE -- and
test_the_two_statements_of_the_trainer_split_agree is worth something only because neither is derived
from the other. If that test is deleted, the registry can describe a split the generator no longer
enforces, which is exactly the state the repository was in on the morning of 2026-10-01.

Facts the mutations lean on, read off the committed data (2026-10-01): data/late_route_trainers.json
restates `lesson` and `trainer_order` for 28 trainers and they MATCH the roster (declared echoes);
its 28 seats also author a `dialogue_text` whose roster value is EMPTY, which is the declared
precedence falling back rather than superseding anything, while Victory Road's ten carry real roster
text and author no seat copy -- so after B2 deleted the ten superseded sets there is no superseded pair
in the committed data, and the precedence case is reached by mutation; no seat file shares any other
field with data/trainers.json. Each such assumption is guarded by a fixture check that says
"fixture no longer exercises the property" rather than passing vacuously.

TWO DEFECTS WERE FOUND WHILE WRITING THIS FILE, REPORTED, AND FIXED THE SAME DAY BY THE TOOL'S AUTHOR.
Neither is asserted here, and BOTH ARE STILL UNCOVERED: the next test pass should add them.

  1. A collision between TWO SATELLITES of one space named the wrong file. `sat = fb if fa == owner
     else fa` assumes one of the pair is the owner, and when neither is -- two seat files both carrying
     a record for one trainer -- the message blamed space["owner"], a file carrying neither value. The
     original report read this as an `fa`/`fb` sort-order bug in the owner-satellite case; checking it
     against the data showed that case attributes correctly (the message names `owner`, which IS the
     file wrongly carrying a stand field) and that the real hole was the ownerless pair. A fault that
     names the wrong file is worse than a quiet one: it is a day spent in the wrong file.
     problems() now reports the ownerless pair as its own fault, naming both real files. UNCOVERED.
  2. A declared overlap whose ids stopped overlapping ENTIRELY was never reported stale, because the
     stale check ran inside a loop over the DATA's (file, file, field) keys and an emptied declaration
     has no such key. Dropping `name` from data/ferries.json's sunset_south_pier -- the only id of that
     declared overlap -- produced no fault at all. problems() now iterates the union of the data's keys
     and the registry's. test_an_id_leaving_a_declared_overlap_is_reported_as_a_stale_declaration still
     uses the 12-id `why` overlap, where one id leaving leaves the key alive, so the all-ids case is
     UNCOVERED.

test_a_stand_field_in_the_roster_faults uses data/vr_trainers.json and asserts the id, the field and the
owner file rather than the sentence, which is the right shape either way: a test author does not edit
tools/ to make a test pass, and a message is not a property.

NOT COVERED HERE.
  * Validity, not behaviour. That rctmod reads the record the roster wins, that a player hears the
    roster's lines rather than the seat file's superseded copy, and that a trainer stands where its
    stand says, are runtime facts and need a server (experiments/, the boot-test skill).
  * Only ids in TOP-LEVEL arrays of data/*.json are records to this tool. A nested object with an `id`
    (a town's doors, a gym's rooms) is its parent's, so a collision between two nested ids in two files
    is invisible to the check and to these tests.
  * Only data/. Two authors for one id across build/, kits/, server/ or a datapack are not examined.
  * Fields whose values are EQUAL in both files are not cross-file authorship to problems()
    (shared_fields filters them), so a dead-but-identical copy is not reported until one side changes.
    route_trainers.ownership() is stricter: it faults on a shared undeclared field even when the two
    values agree. The two checks therefore disagree about an identical duplicate; neither is asserted to
    match the other beyond the three declared field sets.
  * .githooks/post-merge running the tool on every merge is asserted nowhere here; only the tool's own
    exit code and return value are.
  * The two fixed defects above: an ownerless satellite pair, and a declared overlap that empties out
    completely. Both fixes were verified by hand against mutated copies of data/ and neither has a test.
  * test_the_registry_is_not_derived_from_the_tool asserts only that two sets differ after one of them
    is monkeypatched, which is true of any two sets and does not test derivation. The independence it
    claims rests on the two statements living in different files, which no test can see. It should be
    rewritten or dropped rather than trusted.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import id_authorship as IA     # noqa: E402
import route_trainers as RT    # noqa: E402

TRAINERS = "data/trainers.json"
VR = "data/vr_trainers.json"
LATE = "data/late_route_trainers.json"


# ----------------------------------------------------------------- helpers (no tool code reused)
def _faults(root: Path) -> list[str]:
    return IA.problems(IA.records(root), IA.registry(root))


def _mutate(tmp_path: Path, *edits) -> Path:
    """A throwaway copy of the real data/ with (relative path, fn(doc)) edits applied. Returns its root."""
    root = tmp_path / "mutated"
    shutil.copytree(ROOT / "data", root / "data")
    for rel, fn in edits:
        p = root / rel
        doc = json.loads(p.read_text(encoding="utf-8"))
        fn(doc)
        p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return root


def _doc(rel: str) -> dict:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _record(doc: dict, rid: str) -> dict:
    for arr in doc.values():
        if isinstance(arr, list):
            for o in arr:
                if isinstance(o, dict) and o.get("id") == rid:
                    return o
    raise AssertionError("fixture no longer exercises the property: no record %s" % rid)


def _add(key: str, rec: dict):
    def edit(doc):
        doc.setdefault(key, []).append(rec)
    return edit


def _naming(faults, *needles) -> list[str]:
    return [f for f in faults if all(n in f for n in needles)]


@pytest.fixture(scope="module")
def real():
    return IA.records(ROOT), IA.registry(ROOT)


# ----------------------------------------------------------------- 1. the split is stated twice
def test_the_two_statements_of_the_trainer_split_agree(real):
    # Without this the registry can document a split tools/route_trainers.py no longer enforces (or the
    # reverse): one of the two guards goes quiet and nothing says which, which is how 2026-10-01 began.
    _recs, reg = real
    space = next(s for s in reg["spaces"] if s["id"] == "trainers")
    for name, in_registry, in_tool in (
        ("satellite_fields/STAND_FIELDS", space["satellite_fields"], RT.STAND_FIELDS),
        ("echo_fields/ROSTER_ECHO", space["echo_fields"], RT.ROSTER_ECHO),
        ("precedence_fields/ROSTER_PRECEDENCE", space["precedence_fields"], RT.ROSTER_PRECEDENCE),
    ):
        reg_set, tool_set = set(in_registry), set(in_tool)
        assert reg_set == tool_set, (
            "%s drifted. data/id_authorship.json has and tools/route_trainers.py does not: %s. "
            "tools/route_trainers.py has and data/id_authorship.json does not: %s."
            % (name, sorted(reg_set - tool_set) or "-", sorted(tool_set - reg_set) or "-"))
        assert len(in_registry) == len(reg_set), "%s lists a field twice in the registry" % name


def test_the_registry_is_not_derived_from_the_tool(real, monkeypatch):
    # The agreement check above is only worth something if the two sides are independent statements.
    # MUTATE THE GENERATOR: drop a field from the tool's own frozenset and the comparison must notice.
    # If this passes while the tool is mutated, one side is reading the other and both guards are one.
    _recs, reg = real
    space = next(s for s in reg["spaces"] if s["id"] == "trainers")
    monkeypatch.setattr(RT, "STAND_FIELDS", frozenset(set(RT.STAND_FIELDS) - {"seat"}))
    assert set(space["satellite_fields"]) != set(RT.STAND_FIELDS)
    assert "seat" in set(space["satellite_fields"]) - set(RT.STAND_FIELDS)


# ----------------------------------------------------------------- 2. the real data is clean
def test_no_id_in_data_has_two_undeclared_authors(real):
    # The whole point: every cross-file id is a declared space, a declared overlap, or a fault. Remove
    # this and a clean merge can hand one trainer two teams again with nothing reporting it.
    recs, _reg = real
    assert _faults(ROOT) == []
    assert sum(1 for b in recs.values() if len(b) > 1) > 0, (
        "fixture no longer exercises the property: no id is carried by two files at all")


def test_the_trainer_generator_loads_the_split_without_failing_closed():
    # route_trainers.load() is the tool whose SystemExit took the suite down at collection; if it raises
    # again, the roster/stand split in the data has broken and every trainer artifact stops building.
    recs, entries, _fields = RT.load()
    assert recs and entries


def test_the_tool_exits_zero_on_the_real_data_and_nonzero_on_a_collision(tmp_path, capsys):
    # The exit code is what .githooks/post-merge and tools/validate.py read; a check that only ever
    # returns a list cannot fail a merge.
    assert IA.main([]) == 0
    capsys.readouterr()
    root = _mutate(tmp_path, (VR, lambda d: _record(d, "route_09_trainer_10").update(
        {"team": [{"species": "ditto", "level": 1}]})))
    assert IA.main(["--root", str(root)]) == 1


# ----------------------------------------------------------------- 3. mutation proofs, one per mode
def test_a_stand_that_authors_a_roster_field_faults_and_names_the_id_and_the_field(tmp_path):
    # This IS the 2026-10-01 collision: data/trainers.json and data/vr_trainers.json both holding a team
    # for one trainer, merged cleanly. Without this check nothing in the repository reports it.
    root = _mutate(tmp_path, (VR, lambda d: _record(d, "route_09_trainer_10").update(
        {"team": [{"species": "ditto", "level": 1}]})))
    faults = _faults(root)
    hit = _naming(faults, "route_09_trainer_10", "team", VR)
    assert hit, "a stand authoring the roster's `team` did not fault: %s" % faults
    assert "declares for neither" in hit[0]


def test_the_trainer_guard_raises_on_a_stand_that_authors_a_roster_field():
    # The generator must refuse to emit, not quietly pick one of the two rival values. ownership() is
    # called for every seat file by load(); if it stops raising, a half-dead team ships.
    stand = dict(_record(_doc(VR), "route_09_trainer_10"))
    roster = _record(_doc(TRAINERS), "route_09_trainer_10")
    RT.ownership({roster["id"]: roster}, [stand], VR)          # unmutated: no fault
    stand["team"] = [{"species": "ditto", "level": 1}]
    with pytest.raises(SystemExit) as e:
        RT.ownership({roster["id"]: roster}, [stand], VR)
    assert "route_09_trainer_10" in str(e.value) and "team" in str(e.value) and VR in str(e.value)


def test_a_stand_field_in_the_roster_faults(tmp_path):
    # The other direction of the same split: the roster is generated, so a generator that starts
    # emitting `yaw` would silently override every hand-authored stand's facing.
    root = _mutate(tmp_path, (TRAINERS, lambda d: _record(d, "route_09_trainer_10").update({"yaw": 177})))
    faults = _faults(root)
    hit = _naming(faults, "route_09_trainer_10", "yaw")
    assert hit, "the roster carrying the stand's `yaw` did not fault: %s" % faults
    assert TRAINERS in hit[0]


def test_an_echo_that_drifts_faults(tmp_path):
    # An echo is a restatement for a human reader. Once the two copies differ one of them is wrong and
    # nothing says which; without this the seat list can teach a lesson the trainer no longer gives.
    rid = next(e["id"] for e in _doc(LATE)["trainers"] if "lesson" in e)
    assert _naming(_faults(ROOT), rid, "lesson") == [], (
        "fixture no longer exercises the property: %s's echo already faults unmutated" % rid)
    root = _mutate(tmp_path, (LATE, lambda d: _record(d, rid).update({"lesson": "drifted"})))
    faults = _faults(root)
    hit = _naming(faults, rid, "lesson")
    assert hit, "a drifted echo did not fault: %s" % faults
    assert "no longer matches" in hit[0] and LATE in hit[0]


def test_a_matching_echo_is_not_a_fault_when_both_sides_move_together(tmp_path):
    # The complement: the check must bite on DRIFT, not on the mere fact that two files say a thing. A
    # check that faulted here would force the seat files to drop the restatement they exist to carry.
    rid = next(e["id"] for e in _doc(LATE)["trainers"] if "lesson" in e)
    root = _mutate(tmp_path,
                   (LATE, lambda d: _record(d, rid).update({"lesson": "moved in step"})),
                   (TRAINERS, lambda d: _record(d, rid).update({"lesson": "moved in step"})))
    assert _faults(root) == []


def test_a_dialogue_text_supersedes_only_when_the_roster_really_has_one(tmp_path):
    # dialogue_text is the one declared precedence, and the rule is `if r[f] and e[f] != r[f]`: the
    # roster's lines are what a player hears, but ONLY when it has any -- lines_of() falls back on an
    # empty roster value, so a seat set against one is the fallback working, not a superseded copy.
    # B2 deleted the ten superseded sets (docs/HANDOVER_SESSION.md), so the real data has no superseded
    # pair today and the old assertion `RT.SUPERSEDED` was asserting the state before that deletion.
    # The two halves that still matter: a precedence field NEVER faults (if it did, 38 real trainers
    # stop building), and a seat copy that sits behind a REAL roster line is still REPORTED, because an
    # unreported one is a hand-written line dying silently -- the whole fault class.
    roster = {r["id"]: r for r in _doc(TRAINERS)["trainers"]}
    late = _doc(LATE)["trainers"]
    vr = _doc(VR)["trainers"]
    # fixture: the 28 late-route seats author dialogue_text against an EMPTY roster value (the fallback
    # case), and the 10 Victory Road roster records carry REAL text (the precedence case, reachable only
    # by mutation because those seats author none). If either stops being true the test is vacuous.
    fallback = [e for e in late if "dialogue_text" in e]
    assert len(fallback) == 28 and all(
        "dialogue_text" in roster[e["id"]] and not roster[e["id"]]["dialogue_text"] for e in fallback), (
        "fixture no longer exercises the property: data/late_route_trainers.json's seats no longer sit "
        "against an empty roster dialogue_text")
    assert len(vr) == 10 and all(roster[v["id"]].get("dialogue_text") for v in vr), (
        "fixture no longer exercises the property: Victory Road's roster records no longer carry real "
        "dialogue_text, so nothing here can supersede")

    # the fallback half: not superseded, not a fault, and the seat's own text is what lines_of emits
    RT.load()
    both = [(e["id"], "dialogue_text") for ent in (late, vr) for e in ent
            if "dialogue_text" in e and roster.get(e["id"], {}).get("dialogue_text")
            and e["dialogue_text"] != roster[e["id"]]["dialogue_text"]]
    assert sorted(RT.SUPERSEDED) == sorted(both), (sorted(RT.SUPERSEDED), sorted(both))
    assert {f for _i, f in RT.SUPERSEDED} <= {"dialogue_text"}
    for e in fallback:
        assert RT.ownership({e["id"]: roster[e["id"]]}, [dict(e)], LATE) == []
        assert RT.lines_of(roster[e["id"]], e) == e["dialogue_text"]
    assert _naming(_faults(ROOT), fallback[0]["id"], "dialogue_text") == []

    # the precedence half: a seat set against a REAL, DIFFERENT roster line IS superseded -- reported,
    # never faulted -- and the roster's line is the one a player would hear
    stand = dict(_record(_doc(VR), "route_09_trainer_10"))
    r10 = _record(_doc(TRAINERS), "route_09_trainer_10")
    stand["dialogue_text"] = {"pre": "a line only the seat file has"}
    assert RT.ownership({r10["id"]: r10}, [stand], VR) == [("route_09_trainer_10", "dialogue_text")]
    assert RT.lines_of(r10, stand) == r10["dialogue_text"] != stand["dialogue_text"]
    root = _mutate(tmp_path, (VR, lambda d: _record(d, "route_09_trainer_10").update(
        {"dialogue_text": {"pre": "a line only the seat file has"}})))
    assert _naming(_faults(root), "route_09_trainer_10", "dialogue_text") == []


def test_an_id_joining_a_declared_overlap_faults_and_names_the_new_id(tmp_path):
    # An overlap is declared by its exact id set, never by a count or a tolerance. Without this, a
    # declaration written for one reviewed id would silently bless every id that joined it later.
    root = _mutate(tmp_path,
                   ("data/ferries.json", _add("docks", {"id": "zz_probe_dock", "name": "probe A"})),
                   ("data/ferry_docks.json", _add("docks", {"id": "zz_probe_dock", "name": "probe B"})))
    faults = _faults(root)
    hit = _naming(faults, "zz_probe_dock", "name", "does not list")
    assert hit, "an id joining the declared ferries/ferry_docks `name` overlap did not fault: %s" % faults


def test_an_id_leaving_a_declared_overlap_is_reported_as_a_stale_declaration(tmp_path):
    # A registry that keeps entries for overlaps that no longer exist stops describing the data, and the
    # next reader trusts a judgement about ids that have moved on.
    # Uses the 12-id ferries/ferry_docks `why` overlap, not the 1-id `name` one, because of the tool gap
    # recorded in this module's docstring: a declaration is only checked for stale ids while at least one
    # id still overlaps for that (file, file, field).
    declared = next(o for o in IA.registry(ROOT)["overlaps"]
                    if o["files"] == ["data/ferries.json", "data/ferry_docks.json"]
                    and o["fields"] == ["why"])
    assert len(declared["ids"]) > 1, "fixture no longer exercises the property"
    rid = declared["ids"][0]

    def drop(doc):
        _record(doc, rid).pop("why")

    root = _mutate(tmp_path, ("data/ferries.json", drop))
    faults = _faults(root)
    hit = _naming(faults, rid, "no longer overlap")
    assert hit, "a declaration left behind by the data was not reported: %s" % faults
    assert "Drop them from the registry" in hit[0]


# ----------------------------------------------------------------- 4. the declarations are well formed
def test_every_declared_overlap_carries_reviewed_prose_sorted_ids_and_two_real_files(real):
    # --declare emits an "UNREVIEWED" placeholder; a registry that keeps one has blessed a collision
    # nobody judged, which is indistinguishable from the fault it is meant to record.
    recs, reg = real
    assert "UNREVIEWED" in IA.declare(recs, reg), (
        "fixture no longer exercises the property: --declare's placeholder changed")
    for o in reg["overlaps"]:
        where = "/".join(o["files"]) + " " + ",".join(o["fields"])
        why = o.get("why", "")
        assert "UNREVIEWED" not in why, "%s is still the --declare placeholder" % where
        assert len(why.split()) >= 8 and why.strip().endswith("."), "%s: `why` is not reviewed prose" % where
        assert o["ids"] and o["ids"] == sorted(set(o["ids"])), "%s: ids not sorted-unique-nonempty" % where
        assert o["fields"] and all(isinstance(f, str) and f for f in o["fields"]), "%s: empty fields" % where
        assert len(o["files"]) == 2 and o["files"] == sorted(o["files"]), "%s: files are not a sorted pair" % where
        for f in o["files"]:
            assert (ROOT / f).is_file(), "%s names a file that does not exist: %s" % (where, f)


def test_every_declared_space_names_real_files_and_disjoint_field_modes(real):
    # A field in two modes at once, or a satellite that no longer exists, makes the space's own rules
    # unreadable: problems() takes the first mode it matches and the other declaration goes quiet.
    _recs, reg = real
    assert reg["spaces"], "a registry with no space declares nothing"
    for s in reg["spaces"]:
        assert (ROOT / s["owner"]).is_file(), "%s: owner missing" % s["id"]
        assert s["satellites"], "%s: a space with no satellite" % s["id"]
        for f in s["satellites"]:
            assert (ROOT / f).is_file(), "%s: satellite missing: %s" % (s["id"], f)
        sat, echo, prec = set(s["satellite_fields"]), set(s["echo_fields"]), set(s["precedence_fields"])
        assert not (sat & echo) and not (sat & prec) and not (echo & prec), (
            "%s: a field is declared in two modes" % s["id"])
        assert s.get("why", "").strip() and s.get("read_by", "").strip()
    for g in reg["file_local_ids"]:
        d = ROOT / (g[:-len("/*.json")] if g.endswith("/*.json") else g)
        assert d.exists(), "file_local_ids names a path that does not exist: %s" % g


# ----------------------------------------------------------------- 5. file-local ids
def test_two_gym_build_plans_may_share_a_record_id(tmp_path):
    # Each gym plan names its own door_bay and gallery; if this faulted, the only fixes would be to
    # rename every plan's rooms or to widen the check, and the second kills the whole guard.
    root = _mutate(tmp_path,
                   ("data/gym_buildings/gym1.json", _add("rooms", {"id": "zz_probe_room", "why": "gym1's probe"})),
                   ("data/gym_buildings/gym3.json", _add("rooms", {"id": "zz_probe_room", "why": "gym3's probe"})))
    assert _faults(root) == [], "two gym plans sharing a local id faulted: %s" % _faults(root)


def test_a_file_local_id_shared_with_a_file_outside_that_set_still_faults(tmp_path):
    # The exemption is for the plans with each other only. A plan id that collides with a campaign id is
    # how a tool reasoning over one list silently reaches the other thing (CLAUDE.md).
    root = _mutate(tmp_path,
                   ("data/gym_buildings/gym1.json", _add("rooms", {"id": "zz_probe_room", "why": "gym1's probe"})),
                   ("data/landmarks.json", _add("landmarks", {"id": "zz_probe_room", "why": "a landmark probe"})))
    faults = _faults(root)
    hit = _naming(faults, "zz_probe_room", "why")
    assert hit, "a gym-plan id colliding with a landmark id did not fault: %s" % faults
    assert "data/landmarks.json" in hit[0]


# ----------------------------------------------------------------- 6. the suite keeps its count
def test_a_tool_failing_closed_at_import_costs_one_module_and_not_the_run(tmp_path):
    # tests/conftest.py's pytest_make_collect_report. SystemExit is a BaseException, so pytest's
    # collection does not catch it: without the hook one failing generator reports `no tests ran` and an
    # INTERNALERROR, and 5,200 results vanish instead of turning red. A suite that reports nothing cannot
    # be compared with the run before it.
    shutil.copy(ROOT / "tests" / "conftest.py", tmp_path / "conftest.py")
    (tmp_path / "test_fails_closed.py").write_text(
        'raise SystemExit("CANARY: two authors for one trainer field")\n', encoding="utf-8")
    (tmp_path / "test_still_counts.py").write_text("def test_passes():\n    assert True\n", encoding="utf-8")
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(tmp_path)],
                       cwd=tmp_path, capture_output=True, text=True, env=dict(os.environ), timeout=180)
    out = r.stdout + r.stderr
    assert "INTERNALERROR" not in out, out[-2000:]
    assert "1 passed" in out, "the passing module lost its result:\n%s" % out[-2000:]
    assert "1 error" in out, "the failing import was not reported as one collection error:\n%s" % out[-2000:]
    assert "CANARY: two authors for one trainer field" in out, (
        "the tool's message did not survive verbatim:\n%s" % out[-2000:])

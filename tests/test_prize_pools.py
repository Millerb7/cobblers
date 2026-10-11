"""PRIZE-POOLS (2026-10-11): the Ultra Beast double x5 fix, prize pools, per-run rotation of trainer teams, minibosses and
the boss's crews, and the simulator walking every pool member. The builder's own tests (an independent audit is owed:
the report says so).

The catch arithmetic runs the GENERATED callbacks in tests/test_key_ball_audit.py's MoLang model (a test-author's, not
this unit's), with the jar's Beast Ball modifier (x5 on ultra_beast, x1 otherwise). Mutations change the generator (the
code), never the record, wherever the claim is about the code. Not covered: anything in a running Minecraft (probe UB3 in
docs/mechanics/ULTRA_BEAST_BOSSES.md: a tagged Ultra Beast, a Beast Ball at full HP, about 40% a throw with the native
tag; `random value` at the threshold).
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import dungeon as D  # noqa: E402
import dungeon_fights as DF  # noqa: E402
import dungeon_prize as PZ  # noqa: E402
import dungeon_rooms as R  # noqa: E402
import key_ball as KB  # noqa: E402
import test_key_ball_audit as KA  # noqa: E402

BASE = D.load()
KBDOC = KB.load()
UB = "kartana"          # labelled ultra_beast in the 1.8.0 jar (data/key_ball.json native_species_snapshot)
LEG = "volcanion"       # mythical, not an Ultra Beast


def ns_doc(edit=None):
    """The Night Shift alone, its variants off (as tests/test_dungeon_kit3.py's fx_doc), `edit(d)` applied."""
    doc = copy.deepcopy(BASE)
    d = next(x for x in doc["dungeons"] if x["id"] == "night_shift")
    d["variants"] = []
    doc["dungeons"] = [d]
    doc["engine"]["sigils"]["free_first_entry"]["dungeons"] = [d["id"]]
    # the record's own pools only: data/dungeon_prize_roster.json (COVERAGE's, when it lands) is tested on its own below
    rec(d, "sump")["params"]["prize"].pop("roster", None)
    if edit:
        edit(d)
    return doc


def rec(d, rid):
    for r in R.all_records(d):
        if r["id"] == rid:
            return r
    raise KeyError(rid)


def laid(doc, rid):
    d = doc["dungeons"][0]
    slot = D.slots(doc)[0]
    return d, slot, next(r for r in R.layout(doc, d, slot) if r["id"] == rid)


def fires(cond_lines, holder, value, obj="dg.rs"):
    """How many of `cond_lines` an execute's score clause on `holder` `obj` lets through when it holds `value` (None:
    unset). Only the forms the generators write: `if/unless score H <obj> matches a` / `a..b`."""
    n = 0
    for ln in cond_lines:
        ok = True
        for neg, h, o, lo, hi in re.findall(r"(if|unless) score (\S+) (dg\.\w+) matches (\d+)(?:\.\.(\d+))?", ln):
            if h != holder or o != obj:
                continue
            hit = value is not None and int(lo) <= value <= int(hi or lo)
            ok = ok and (hit if neg == "if" else not hit)
        n += ok
    return n


# ------------------------------------------------------------------------------------------------- 3: the Ultra Beast x5


def throw(files, tags, labels, ball=KA.BEAST, rate=45):
    w = KA.World(files)
    p = w.add(KA.survivor(ball=ball))
    t = w.add(KA.Entity("boss", tags=tags, labels=labels, catch_rate=rate))
    return w.throw(p, t, ball), p


def test_a_key_ultra_beast_gets_x5_once_and_any_other_key_boss_x5():
    files = KA.key_files()
    tag, nat = KBDOC["tag"], KBDOC["native_tag"]
    # an Ultra Beast boss carries both tags (bind_tag_lines): the jar's x5 alone
    assert throw(files, {tag, nat}, {"ultra_beast"})[0] == ("roll", 45 * 5.0)
    # a legendary boss carries the key tag only: ours alone, the jar's 1.0
    assert throw(files, {tag}, {"legendary"})[0] == ("roll", 45 * 5.0)
    # the defect the native tag exists for: the key tag alone on an Ultra Beast is x25
    assert throw(files, {tag}, {"ultra_beast"})[0] == ("roll", 45 * 25.0)
    # every other ball is still refused at an Ultra Beast boss, and handed back
    out, p = throw(files, {tag, nat}, {"ultra_beast"}, ball="cobblemon:ultra_ball")
    assert out[0] == "fail" and p.inv["cobblemon:ultra_ball"] == 1


def test_the_native_tag_follows_the_jar_label_and_the_snapshot_is_the_jars():
    assert KB.bind_tag_lines(UB) == ["tag @s add %s" % KBDOC["tag"], "tag @s add %s" % KBDOC["native_tag"]]
    assert KB.bind_tag_lines("cobblemon:" + UB)[-1].endswith(KBDOC["native_tag"])
    for sp in (LEG, "entei", "regidrago", "hakamoo"):
        assert KB.bind_tag_lines(sp) == ["tag @s add %s" % KBDOC["tag"]], sp
    jar = KB.jar_native_species("ultra_beast")
    if jar is not None:
        assert sorted(KBDOC["native_species_snapshot"]) == jar and len(jar) == 11
    bad = copy.deepcopy(KBDOC)
    bad["native_tag"] = bad["tag"]
    assert any("native_tag" in p for p in KB.problems(bad))


def test_the_rate_guard_fails_against_a_generator_without_it():
    # breaks if the UB check could not tell the generator from one that multiplies at a native boss anyway
    files = KA.key_files(KA.mutant(KB, '"  t.nat == 0 ? {",', '"  1 ? {",'))
    out, _ = throw(files, {KBDOC["tag"], KBDOC["native_tag"]}, {"ultra_beast"})
    assert out == ("roll", 45 * 25.0)


def ub_doc():
    def edit(d):
        pz = rec(d, "sump")["params"]["prize"]
        pz["legendary_pool_by_band"] = {"4": [UB], "6": [UB, "celesteela"]}
    return ns_doc(edit)


def test_an_ultra_beast_prize_binds_with_both_tags_and_a_legendary_with_the_key_alone():
    doc = ub_doc()
    d, slot, room = laid(doc, "sump")
    fns, enter, spawns, _pos = PZ.prize_functions(doc, d, slot, room)
    assert spawns[4] == [[LEG, 50, True], [UB, 50, True]]
    assert fns["prize/spawn_b4_2"][-1].endswith("prize/bind_native") and fns["prize/spawn_b4"][-1].endswith("prize/bind")
    assert "tag @s add %s" % KBDOC["native_tag"] in fns["prize/bind_native"]
    assert "tag @s add %s" % KBDOC["native_tag"] not in fns["prize/bind"]
    assert fns["prize/spawn_b1"][-1].endswith("prize/rare_bind")
    assert KB.native_sweep(PZ.key_sweep_files(doc), "tag @s add %s" % KBDOC["tag"],
                           "tag @s add %s" % KBDOC["native_tag"], KB.native_species()) == []


def test_the_sweep_names_an_ultra_beast_bound_without_the_native_tag(monkeypatch):
    # a generator mutation: the prize's bind choice ignores the jar label
    doc = ub_doc()
    monkeypatch.setattr(PZ, "bind_name", lambda doc, sp, leg: "prize/bind" if leg else "prize/rare_bind")
    bad = KB.native_sweep(PZ.key_sweep_files(doc), "tag @s add %s" % KBDOC["tag"],
                          "tag @s add %s" % KBDOC["native_tag"], KB.native_species())
    assert bad and all("x25" in p and UB in p or "celesteela" in p for p in bad), bad


# ------------------------------------------------------------------------------------------------- 1: prize pools


def test_a_pool_merges_the_single_form_the_rooms_pool_and_the_roster_in_order(monkeypatch, tmp_path):
    doc = ub_doc()
    room = rec(doc["dungeons"][0], "sump")
    assert PZ.pool_at(doc, room, 4) == ([LEG, UB], True)
    assert PZ.pool_at(doc, room, 1) == (["pupitar"], False)
    p = tmp_path / "roster.json"
    p.write_text(json.dumps({"dungeons": {"night_shift": {"rare_pool_by_band": {"1": ["gabite", "pupitar"]},
                                                          "legendary_pool_by_band": {"5": ["heatran"]}}}}))
    monkeypatch.setattr(PZ, "ROSTER", p)
    PZ._ROSTER.clear()
    room["params"]["prize"]["roster"] = "night_shift"
    try:
        assert PZ.pool_at(doc, room, 1) == (["pupitar", "gabite"], False)
        assert PZ.pool_at(doc, room, 5) == ([LEG, "heatran"], True)
        assert PZ.room_problems(doc, doc["dungeons"][0], room) == []
        room["params"]["prize"]["roster"] = "jungle_nope"
        assert any("has no entry" in m for m in PZ.room_problems(doc, doc["dungeons"][0], room))
        # the list shape is read too
        p.write_text(json.dumps({"dungeons": [{"id": "night_shift", "rare_pool_by_band": {"2": ["kirlia"]}}]}))
        PZ._ROSTER.clear()
        room["params"]["prize"]["roster"] = "night_shift"
        assert PZ.pool_at(doc, room, 2) == (["fraxure", "kirlia"], False)
    finally:
        PZ._ROSTER.clear()


def test_model_gated_roster_species_are_dropped_until_their_gate_is_delivered(monkeypatch, tmp_path):
    # COVERAGE's F3: species.<id>.model_gate "atm_subset" (the doll until ATMxMSD reaches players)
    doc = ub_doc()
    room = rec(doc["dungeons"][0], "sump")
    p = tmp_path / "roster.json"
    p.write_text(json.dumps({"dungeons": [{"id": "night_shift", "legendary_pool_by_band": {"4": ["xurkitree", "diancie"]}}],
                             "species": {"xurkitree": {"model_gate": "atm_subset"},
                                         UB: {"model_gate": "atm_subset: its only model is in ATMxMSD"}}}))
    monkeypatch.setattr(PZ, "ROSTER", p)
    PZ._ROSTER.clear()
    room["params"]["prize"]["roster"] = "night_shift"
    try:
        assert PZ.pool_at(doc, room, 4) == ([LEG, "diancie"], True)           # kartana and xurkitree gated
        doc["engine"]["prize"]["models_delivered"] = ["atm_subset"]
        assert PZ.pool_at(doc, room, 4) == ([LEG, UB, "xurkitree", "diancie"], True)
        doc["engine"]["prize"]["models_delivered"] = "atm_subset"
        assert any("models_delivered" in m for m in PZ.engine_problems(doc))
    finally:
        PZ._ROSTER.clear()


def test_a_paradox_is_a_legendary_pool_prize_and_never_a_rare_one():
    # COVERAGE's F1: the jar labels paradoxes `paradox` and nothing else
    assert "paradox" in PZ.jar_labels()["greattusk"] and "legendary" not in PZ.jar_labels()["greattusk"]
    ok = ns_doc(lambda d: rec(d, "sump")["params"]["prize"].update(legendary_pool_by_band={"5": ["greattusk"]}))
    assert PZ.room_problems(ok, ok["dungeons"][0], rec(ok["dungeons"][0], "sump")) == []
    bad = ns_doc(lambda d: rec(d, "sump")["params"]["prize"].update(rare_pool_by_band={"1": ["greattusk"]}))
    assert any("paradox" in m for m in PZ.room_problems(bad, bad["dungeons"][0], rec(bad["dungeons"][0], "sump")))
    # and a restricted (box) legendary only at band 6
    r = ns_doc(lambda d: rec(d, "sump")["params"]["prize"].update(legendary_pool_by_band={"5": ["zygarde"], "6": ["zygarde"]}))
    msgs = PZ.room_problems(r, r["dungeons"][0], rec(r["dungeons"][0], "sump"))
    assert [m for m in msgs if "restricted" in m] and all("band 5" in m for m in msgs if "restricted" in m)


@pytest.mark.parametrize("edit,needle", [
    (lambda p: p.update(rare_pool_by_band={"2": ["gabite", "zarude"]}), "before the Beast Ball stage"),
    (lambda p: p.update(legendary_pool_by_band={"5": ["gabite"]}), "not a legendary, mythical, Ultra Beast or paradox"),
    (lambda p: p.update(legendary_pool_by_band={"2": [UB]}), "the legendary prize is from band 4"),
    (lambda p: p.update(rare_pool_by_band={"1": ["gabite", "gabite"]}), "repeats a species"),
    (lambda p: p.update(rare_pool_by_band={"1": []}), "non-empty list"),
    (lambda p: p.update(rare_pool_by_band={"1": "gabite"}), "non-empty list"),
])
def test_prize_pool_checks_bite(edit, needle):
    doc = ns_doc(lambda d: edit(rec(d, "sump")["params"]["prize"]))
    d = doc["dungeons"][0]
    bad = PZ.room_problems(doc, d, rec(d, "sump"))
    assert any(needle in m for m in bad), bad


def test_the_species_is_rolled_only_when_present_and_exactly_one_spawn_fires_for_any_roll():
    doc = ub_doc()
    d, slot, room = laid(doc, "sump")
    H, Hs = PZ.holder(slot, room), PZ.species_holder(slot, room)
    st = PZ.start_lines(doc, slot)
    rolls = [l for l in st if Hs in l and "random value" in l]
    assert [l.rsplit(" ", 1)[1] for l in rolls] == ["1..2", "1..3"]      # band 4 (volcanion, kartana), band 6 (+ celesteela)
    assert all(("%s dg.rs matches 1 " % H) in l for l in rolls)
    assert st.index("scoreboard players set %s dg.rs 1" % Hs) < st.index(rolls[0])
    _fns, enter, _sp, _pos = PZ.prize_functions(doc, d, slot, room)
    for band in (4, 6):
        mine = [l for l in enter if "dg.band matches %d " % band in l]
        for v in (None, 0, 1, 2, 3, 7):
            assert fires(mine, Hs, v) == 1, (band, v)
    # a band with a pool of one has no condition on the species holder
    assert all(Hs not in l for l in enter if "dg.band matches 1 " in l)


def test_the_unset_fallback_fails_against_a_generator_without_it(monkeypatch):
    # breaks if the exactly-one check could pass a generator whose member 1 needs the roll to have happened
    monkeypatch.setattr(PZ, "species_cond", lambda Hs, k, n: "" if n <= 1 else "if score %s dg.rs matches %d " % (Hs, k))
    doc = ub_doc()
    d, slot, room = laid(doc, "sump")
    _fns, enter, _sp, _pos = PZ.prize_functions(doc, d, slot, room)
    mine = [l for l in enter if "dg.band matches 4 " in l]
    assert fires(mine, PZ.species_holder(slot, room), None) == 0


# ------------------------------------------------------------------------------------------------- 2: rotation


def pooled_doc():
    def edit(d):
        t = rec(d, "hands_stand")["params"]["trainers"][0]
        t["team_pool_by_band"] = {"1": [t["team_by_band"]["1"], list(reversed(t["team_by_band"]["1"])),
                                        ["geodude"] * len(t["team_by_band"]["1"])]}
        del t["team_by_band"]["1"]
        mb = rec(d, "the_fall")["params"]
        mb["species_pool_by_band"] = {"2": ["onix", "graveler"]}
        del mb["species_by_band"]["2"]
        bo = d["boss"]
        bo["teams_alt_by_band"] = {"1": [[["drilbur", "xurkitree"], bo["teams"]["1"][1]]]}
    return ns_doc(edit)


def test_rotation_records_pass_and_their_checks_bite():
    doc = pooled_doc()
    assert D.problems(doc) == []
    d = doc["dungeons"][0]
    # both forms naming one band
    t = rec(d, "hands_stand")["params"]["trainers"][0]
    t["team_by_band"]["1"] = t["team_pool_by_band"]["1"][0]
    assert any("both name it" in m for m in DF.stand_problems(doc, rec(d, "hands_stand")))
    del t["team_by_band"]["1"]
    # a pool team of the wrong size
    t["team_pool_by_band"]["1"].append(["onix"])
    assert any("pool team 4" in m and "members" in m for m in DF.stand_problems(doc, rec(d, "hands_stand")))
    t["team_pool_by_band"]["1"].pop()
    # a catchable miniboss is never a legendary or an Ultra Beast
    rec(d, "the_fall")["params"]["species_pool_by_band"]["2"].append(UB)
    assert any("catchable miniboss is never one" in m for m in DF.room_problems(doc, rec(d, "the_fall")))
    rec(d, "the_fall")["params"]["species_pool_by_band"]["2"].pop()
    # a boss alternate with the wrong stage count
    d["boss"]["teams_alt_by_band"]["1"].append([["onix"]])
    assert any("alternate 2: not one crew per stage" in m for m in D.problems(doc))


def test_a_rotating_stand_spawns_exactly_one_pool_team_for_any_roll():
    doc = pooled_doc()
    d, slot, room = laid(doc, "hands_stand")
    classes = DF.stand_classes(doc, d, room)
    assert {"dg_ns_st_hands_stand_t1_b1", "dg_ns_st_hands_stand_t1_b1_v2", "dg_ns_st_hands_stand_t1_b1_v3"} <= set(classes)
    assert "dg_ns_st_hands_stand_t1_b2_v2" not in classes
    fns = DF.stand_functions(doc, d, room, 1, slot["g"], (0, 96, 0), 101)
    H = DF.rot_holder(slot["g"], room)
    start = fns["stand/%s/start" % DF.stand_key(d, room, 1, slot["g"])]
    spawns = [l for l in start if "npc_at" in l and "dg.band matches 1 " in l]
    for v in (None, 0, 1, 2, 3, 9):
        assert fires(spawns, H, v) == 1, v
    assert [l for l in start if "npc_at" in l and "dg.band matches 2 " in l and H in l] == []
    roll = DF.rotation_start_lines(doc, slot)
    assert "execute if score @s dg.band matches 1 store result score %s dg.rs run random value 1..3" % H in roll
    assert not any("matches 2 store" in l and H in l for l in roll)


def test_a_rotating_miniboss_has_a_spawn_per_member_and_the_sim_walks_both():
    import dungeon_sim as S
    doc = pooled_doc()
    d, slot, room = laid(doc, "the_fall")
    res = R.KINDS["miniboss"](doc, d, slot, room, R.theme_for(d))
    fns = res["functions"]
    assert 'species:"onix"' in "\n".join(fns["spawn_b2"]) and 'species:"graveler"' in "\n".join(fns["spawn_b2_v2"])
    assert 'species:"onix"' not in "\n".join(fns["spawn_b2_v2"])
    H = DF.rot_holder(slot["g"], room)
    mine = [l for l in fns["enter"] if "dg.band matches 2 " in l]
    for v in (None, 1, 2, 5):
        assert fires(mine, H, v) == 1, v
    assert S.rotation_count(doc, d, 2) == 2
    pe = S.dungeon_paths(doc, d, 2)
    labels = {e["label"] for _l, seq in pe["paths"] for e in seq}
    assert {"the_fall: onix", "the_fall: graveler"} <= labels
    assert all("~v" in l for l, _ in pe["paths"])
    # band 1: three stand teams and two boss crews, walked in three variants
    pe1 = S.dungeon_paths(doc, d, 1)
    foes = {tuple(sp for sp, _ in e["foes"]) for _l, seq in pe1["paths"] for e in seq
            if e["label"].startswith("hands_stand") and "/3]" in e["label"]}
    assert len(foes) == 3                       # trainer 1's three pool teams; trainer 2 (no pool) is unlabelled
    assert any(e["label"].startswith("hands_stand") and "[" not in e["label"] for _l, seq in pe1["paths"] for e in seq)
    crews = {tuple(sp for sp, _ in e["foes"]) for _l, seq in pe1["paths"] for e in seq if e["label"].startswith("boss stage 1")}
    assert ("drilbur", "xurkitree") in crews and len(crews) == 2


def test_the_boss_rotates_its_crew_lists_by_the_members_roll():
    doc = pooled_doc()
    d = doc["dungeons"][0]
    classes = D.boss_classes(doc, d)
    assert classes["dg_ns_boss_b1_s1_v2"][0]["party"]["pokemon"][-1].startswith("xurkitree level=")
    assert "dg_ns_boss_b2_s1_v2" not in classes
    begin = DF.boss_functions(doc)["claw/boss_begin_ns"]
    b1s1 = [l for l in begin if "dg.band matches 1 " in l and "dg.stage matches 1 " in l]
    for v in (None, 1, 2, 4):
        assert fires(b1s1, "@s", v, "dg.bv") == 1, v
    assert D.boss_start_lines(doc, d)[-1] == "execute if score @s dg.band matches 1 store result score @s dg.bv run random value 1..2"
    assert D.boss_start_lines(ns_doc(), ns_doc()["dungeons"][0]) == []

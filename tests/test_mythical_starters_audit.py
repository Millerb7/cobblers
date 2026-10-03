"""tools/mythical_starters_audit.py: the five mythical starters checked against the DECISION and the 1.8.0 jar.

Written by a test author, not by the session that built the starters. Every mutation below changes the GENERATOR's
code (tools/mythical_starters.py `addition` or `files`, monkeypatched) and leaves data/mythical_starters.json alone
(an autouse fixture fails the test if the record's bytes change). A mutation of the record would move the builder's
own `check` and its output together; mutating the generator is what shows the audit's expectation is its own.

Two artifacts have no generator: modpack/config/cobblemon/starters.json (hand-maintained) and data/spawns.json. Those
mutations edit a temporary COPY of the artifact, and the expectation they break is still the decision's constant
(five lines, level 5, aspect cobblers_starter_1) or the jar's family of an upstream starter, never the copy.

Not covered here (runtime, EXP-049): forms loading, the aspect surviving a species change, a same-species form step,
the cap against Rare Candy, `level` on an item_interact evolution, other packs' forms or starter categories.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import mythical_starters as MS  # noqa: E402  the generator under mutation
import mythical_starters_audit as AU  # noqa: E402  the audit under test

A1, A2 = "cobblers_starter_1", "cobblers_starter_2"


@pytest.fixture(scope="module")
def jar():
    import battle_sim
    try:
        path = AU.find_jar()
    except battle_sim.SimError as exc:  # battle_sim.find_jar raises SimError when no 1.8 jar is anywhere
        pytest.skip("no Cobblemon 1.8.0 jar: %s" % exc)
    if not Path(path).is_file():
        pytest.skip("no Cobblemon 1.8.0 jar")
    return path


@pytest.fixture(autouse=True)
def record_untouched():
    before = hashlib.sha256(MS.DATA.read_bytes()).hexdigest()
    yield
    assert hashlib.sha256(MS.DATA.read_bytes()).hexdigest() == before, "a mutation edited the record, not the generator"


def build(monkeypatch, tmp_path, mutate=None, extra=None):
    """Run the real generator into tmp_path, with `mutate(species, addition)` applied inside its `addition`."""
    if mutate:
        original = MS.addition

        def mutated(doc, species, stages):
            out = copy.deepcopy(original(doc, species, stages))
            mutate(species, out)
            return out
        monkeypatch.setattr(MS, "addition", mutated)
    if extra:
        original_files = MS.files

        def more(doc):
            out = dict(original_files(doc))
            out.update({k: json.dumps(v) for k, v in extra.items()})
            return out
        monkeypatch.setattr(MS, "files", more)
    monkeypatch.setattr(MS, "OUT", tmp_path / "pack")
    MS.build(json.loads(MS.DATA.read_text(encoding="utf-8")))
    return tmp_path / "pack"


def faults(jar, pack, **kw):
    return AU.audit(pack=pack, jar=jar, **kw)[0]


def stage(addition, aspect):
    return [f for f in addition["forms"] if f["aspects"] == [aspect]]


def assert_named(found, *needles):
    text = "\n".join(found)
    for n in needles:
        assert n in text, "no fault names %r; faults were:\n%s" % (n, text or "(none)")


# Without it nothing shows the built pack, as the generator emits it today, meets the decision at all.
def test_the_built_pack_meets_the_decision(jar, monkeypatch, tmp_path):
    assert faults(jar, build(monkeypatch, tmp_path)) == []


# Without it a final evolution moved off 45 (the arrival cap for gym 6) would ship unnoticed.
def test_a_final_step_off_45_is_a_fault(jar, monkeypatch, tmp_path):
    def m(_sp, a):
        for f in stage(a, A2):
            for ev in f["evolutions"]:
                for r in ev["requirements"]:
                    if r["variant"] == "level":
                        r["minLevel"] = 46
    assert_named(faults(jar, build(monkeypatch, tmp_path, m)), "level requirement [46]")


# Without it the stage-2 point could open before gym 3's cap of 30.
def test_a_stage_2_step_off_30_is_a_fault(jar, monkeypatch, tmp_path):
    def m(_sp, a):
        for f in stage(a, A1):
            for ev in f["evolutions"]:
                ev["requirements"][0]["minLevel"] = 29
    assert_named(faults(jar, build(monkeypatch, tmp_path, m)), "level requirement [29]")


# Without it a final that keeps our aspect would not be native (and the stage-2 form's aspect would ride along).
def test_a_final_that_keeps_our_aspect_is_a_fault(jar, monkeypatch, tmp_path):
    def m(_sp, a):
        for f in stage(a, A2):
            for ev in f["evolutions"]:
                ev["result"] = " ".join(w for w in ev["result"].split() if not w.startswith("unaspect="))
    assert_named(faults(jar, build(monkeypatch, tmp_path, m)), "the final keeps our aspect")


# Without it Meltan could ship needing an anvil at 45, the one condition the owner dropped (6a).
def test_meltan_with_an_anvil_is_a_fault(jar, monkeypatch, tmp_path):
    def m(sp, a):
        if sp == "meltan":
            for f in stage(a, A2):
                f["evolutions"][0]["requirements"].append({"variant": "held_item", "itemCondition": "minecraft:anvil"})
    assert_named(faults(jar, build(monkeypatch, tmp_path, m)), "meltan stage 2 -> melmetal", "'held_item'")


# Without it Type: Null's native friendship 160 could come back and land wherever play style puts it (1.2).
def test_type_null_on_friendship_is_a_fault(jar, monkeypatch, tmp_path):
    def m(sp, a):
        if sp == "typenull":
            for f in stage(a, A2):
                f["evolutions"][0]["requirements"].append({"variant": "friendship", "amount": 160})
    assert_named(faults(jar, build(monkeypatch, tmp_path, m)), "'friendship'")


# Without it a forced evolution would take the choice of when to evolve from the player (7.3).
def test_a_forced_evolution_is_a_fault(jar, monkeypatch, tmp_path):
    def m(_sp, a):
        for f in a["forms"]:
            for ev in f["evolutions"]:
                ev["optional"] = False
    assert_named(faults(jar, build(monkeypatch, tmp_path, m)), "OFFERED")


# Without it a form on a final (Silvally's memories hidden by `getForm`'s last match) could ship (4).
def test_a_form_on_a_native_final_is_a_fault(jar, monkeypatch, tmp_path):
    extra = {"data/cobblers/species_additions/x_silvally.json":
             {"target": "cobblemon:silvally", "forms": [{"name": "Starter", "aspects": [A2]}]}}
    assert_named(faults(jar, build(monkeypatch, tmp_path, extra=extra)), "adds to silvally", "carries 11 forms")


# Without it a species-level change would reach every wild, raid and trainer copy of the species.
def test_a_species_level_change_is_a_fault(jar, monkeypatch, tmp_path):
    def m(sp, a):
        if sp == "kubfu":
            a["baseStats"] = {"hp": 1}
    assert_named(faults(jar, build(monkeypatch, tmp_path, m)), "species-level keys ['baseStats']")


# Without it a move outside the jar, or outside the line's own 1.8.0 learnsets, could enter a form's pool.
def test_an_illegal_or_unknown_move_is_a_fault(jar, monkeypatch, tmp_path):
    def m(sp, a):
        if sp == "kubfu":
            for f in a["forms"]:
                f["moves"] = f["moves"] + ["20:spore", "21:notamove"]
    assert_named(faults(jar, build(monkeypatch, tmp_path, m)),
                 "'spore' is in no 1.8.0 learnset", "'notamove' is not a move in the jar")


# Without it a stage could drift off the decided 330 / 430 strength band.
def test_a_stage_off_its_bst_is_a_fault(jar, monkeypatch, tmp_path):
    def m(sp, a):
        if sp == "typenull":
            stage(a, A1)[0]["baseStats"]["hp"] += 1
    assert_named(faults(jar, build(monkeypatch, tmp_path, m)), "typenull stage 1: BST 331")


# Without it Meltan could lose Melmetal's shape (6a: the variant that measured inside the band) at the right total.
def test_a_stage_out_of_its_shape_is_a_fault(jar, monkeypatch, tmp_path):
    def m(sp, a):
        if sp == "meltan":
            bs = stage(a, A1)[0]["baseStats"]
            bs["attack"], bs["special_attack"] = bs["special_attack"], bs["attack"]
    assert_named(faults(jar, build(monkeypatch, tmp_path, m)), "is not melmetal's share")


# Without it a line could lose its same-species stage 2 and evolve once (the decision's two points need two forms).
def test_a_missing_stage_2_form_is_a_fault(jar, monkeypatch, tmp_path):
    def m(sp, a):
        if sp == "kubfu":
            a["forms"] = stage(a, A1)
    assert_named(faults(jar, build(monkeypatch, tmp_path, m)), "kubfu: the chain never reaches a stage-2 form")


# Without it Cosmog's stage 2 could stop being Cosmoem (the one line that evolves twice natively, 1.1).
def test_cosmog_staying_cosmog_at_30_is_a_fault(jar, monkeypatch, tmp_path):
    def m(sp, a):
        if sp == "cosmog":
            stage(a, A1)[0]["evolutions"][0]["result"] = "cosmog unaspect=%s aspect=%s" % (A1, A2)
    assert_named(faults(jar, build(monkeypatch, tmp_path, m)), "stage 2 of the cosmog line is cosmoem")


# Without it one of Cosmoem's two native finals could vanish and with it the Solgaleo/Lunala choice (4).
def test_a_lost_native_final_is_a_fault(jar, monkeypatch, tmp_path):
    def m(sp, a):
        if sp == "cosmoem":
            f = stage(a, A2)[0]
            f["evolutions"] = [ev for ev in f["evolutions"] if not ev["result"].startswith("lunala")]
    assert_named(faults(jar, build(monkeypatch, tmp_path, m)), "the jar's native finals are")


# Without it Solgaleo and Lunala could swap day and night against the jar's own choice.
def test_a_swapped_time_choice_is_a_fault(jar, monkeypatch, tmp_path):
    def m(sp, a):
        if sp == "cosmoem":
            for ev in stage(a, A2)[0]["evolutions"]:
                for r in ev["requirements"]:
                    if r["variant"] == "time_range":
                        r["range"] = "night" if r["range"] == "day" else "day"
    assert_named(faults(jar, build(monkeypatch, tmp_path, m)), "time_range 'night', the jar's own choice is ['day']")


# Without it Kubfu's scroll could be dropped and with it the Single/Rapid Strike choice the decision keeps (2, 4).
def test_kubfu_without_its_scroll_is_a_fault(jar, monkeypatch, tmp_path):
    def m(sp, a):
        if sp == "kubfu":
            for ev in stage(a, A2)[0]["evolutions"]:
                ev["variant"] = "level_up"
                ev.pop("requiredContext", None)
    assert_named(faults(jar, build(monkeypatch, tmp_path, m)), "the kept native choice is item_interact")


# Without it a final could arrive without the move the jar teaches on that evolution (Wicked Blow, Multi-Attack).
def test_a_dropped_native_evolution_move_is_a_fault(jar, monkeypatch, tmp_path):
    def m(sp, a):
        if sp == "kubfu":
            for ev in stage(a, A2)[0]["evolutions"]:
                ev["learnableMoves"] = []
    assert_named(faults(jar, build(monkeypatch, tmp_path, m)), "drops the native evolution move(s) ['wickedblow']")


# Without it a Cosmog that cannot deal damage (1.2: Splash and Teleport) could be offered at level 5.
def test_a_starter_that_cannot_attack_is_a_fault(jar, monkeypatch, tmp_path):
    def m(sp, a):
        if sp == "cosmog":
            stage(a, A1)[0]["moves"] = ["1:splash", "1:teleport"]
    assert_named(faults(jar, build(monkeypatch, tmp_path, m)), "cosmog stage 1: no damaging move")


# Without it a datapack starter category in our pack would silently replace the config's five.
def test_a_starter_category_in_the_pack_is_a_fault(jar, monkeypatch, tmp_path):
    extra = {"data/cobblers/starters/x.json": {"name": "x", "pokemon": ["charmander level=5"]}}
    assert_named(faults(jar, build(monkeypatch, tmp_path, extra=extra)), "REPLACES the config's starters")


def _screen(tmp_path, pokemon):
    cfg = json.loads(AU.STARTERS.read_text(encoding="utf-8"))
    cfg["starters"] = [{"name": "cobblers_mythical", "displayName": "Cobblers", "pokemon": pokemon}]
    p = tmp_path / "starters.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    return p


FIVE = ["%s level=5 aspect=%s" % (s, A1) for s in ("cosmog", "kubfu", "typenull", "poipole", "meltan")]


# Without it the screen could offer a wrong level, no aspect (the wild-shaped Pokemon), a sixth or a missing line.
@pytest.mark.parametrize("pokemon, needle", [
    ([e.replace("level=5", "level=6") if e.startswith("kubfu") else e for e in FIVE], "the decision is level=5"),
    ([e.split(" aspect=")[0] if e.startswith("poipole") else e for e in FIVE], "the decision is level=5 aspect="),
    (FIVE + ["charmander level=5 aspect=%s" % A1], "offers ['charmander'"),
    (FIVE[:-1], "the decision is exactly the five"),
    (["Type: Null level=5 aspect=%s" % A1 if e.startswith("typenull") else e for e in FIVE], "is not a species id"),
])
def test_the_starter_screen_offers_exactly_the_five(jar, monkeypatch, tmp_path, pokemon, needle):
    pack = build(monkeypatch, tmp_path)
    assert faults(jar, pack, starters=_screen(tmp_path, FIVE)) == []
    assert_named(faults(jar, pack, starters=_screen(tmp_path, pokemon)), needle)


# Without it a traditional starter could leave the screen and be nowhere wild, the decision's other half.
def test_a_traditional_starter_with_no_wild_family_is_a_fault(jar, monkeypatch, tmp_path):
    doc = json.loads(AU.SPAWNS.read_text(encoding="utf-8"))
    for row in doc["entries"]:
        if row["species"].split()[0].lower() in ("charmander", "charmeleon", "charizard"):
            row["weight"] = 0
    spawns = tmp_path / "spawns.json"
    spawns.write_text(json.dumps(doc), encoding="utf-8")
    assert_named(faults(jar, build(monkeypatch, tmp_path), spawns=spawns), "charmander: no member of its family")


# Without it the record's list of the 27 (which other tests now read) could drift from the trios upstream offered.
def test_the_record_lists_the_upstream_trios(jar, monkeypatch, tmp_path):
    doc = json.loads(MS.DATA.read_text(encoding="utf-8"))
    doc["wild_traditional_starters"]["regions"]["Kanto"].remove("squirtle")
    record = tmp_path / "record.json"
    record.write_text(json.dumps(doc), encoding="utf-8")
    assert_named(faults(jar, build(monkeypatch, tmp_path), record=record), "missing ['squirtle']")


# Without it the scrolls Kubfu's final needs would be missing from the game with nothing saying so (7.5).
def test_an_unissued_scroll_is_reported_open_until_the_station_issues_it(jar, monkeypatch, tmp_path):
    pack = build(monkeypatch, tmp_path)
    station = json.loads(AU.STATION.read_text(encoding="utf-8"))
    issued = json.dumps(station["economy"]["items"])
    opens = AU.audit(pack=pack, jar=jar)[1]
    for scroll in ("cobblemon:scroll_of_darkness", "cobblemon:scroll_of_waters"):
        assert any(o.startswith(scroll) for o in opens) == (scroll not in issued)
    station["economy"]["items"].append({"id": "scrolls", "item": ["cobblemon:scroll_of_darkness",
                                                                  "cobblemon:scroll_of_waters"]})
    alt = tmp_path / "station.json"
    alt.write_text(json.dumps(station), encoding="utf-8")
    assert AU.audit(pack=pack, jar=jar, station=alt)[1] == []


# Without it the audit could start reusing the builder's own derivation and agree with it about anything.
def test_the_audit_does_not_import_the_builder():
    src = (ROOT / "tools" / "mythical_starters_audit.py").read_text(encoding="utf-8")
    assert "import mythical_starters" not in src and "from mythical_starters" not in src

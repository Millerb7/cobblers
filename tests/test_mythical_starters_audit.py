"""tools/mythical_starters_audit.py: the seven starters (five mythical, Larvesta and Smeargle since 2026-10-08) checked
against the DECISION and the 1.8.0 jar.

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
    assert_named(faults(jar, build(monkeypatch, tmp_path, extra=extra)), "adds to silvally", "carries 18 forms")


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


FIVE = ["%s level=5 aspect=%s" % (s, A1) for s in ("cosmog", "kubfu", "typenull", "poipole", "meltan", "larvesta",
                                                    "smeargle", "misdreavus")]


# Without it the screen could offer a wrong level, no aspect (the wild-shaped Pokemon), a sixth or a missing line.
@pytest.mark.parametrize("pokemon, needle", [
    ([e.replace("level=5", "level=6") if e.startswith("kubfu") else e for e in FIVE], "the decision is level=5"),
    ([e.split(" aspect=")[0] if e.startswith("poipole") else e for e in FIVE], "the decision is level=5 aspect="),
    (FIVE + ["charmander level=5 aspect=%s" % A1], "offers ['charmander'"),
    (FIVE[:-1], "the decision is exactly the 8 stage-1 lines"),
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


# ------------------------------------------------------------------------- Larvesta, the sixth (2026-10-08)
# Larvesta is the one line that is also an ordinary wild species, with a native level-59 step to Volcarona. These
# pin that the starter forms are reached by aspect alone and that the line's own jar facts are kept.

# Without it the grown form could keep the jar's 59 (the starter arriving at gym 6 un-evolved) and pass.
def test_larvesta_reaching_volcarona_at_the_jars_59_is_a_fault(jar, monkeypatch, tmp_path):
    def m(sp, a):
        if sp == "larvesta":
            stage(a, A2)[0]["evolutions"][0]["requirements"] = [{"variant": "level", "minLevel": 59}]
    assert_named(faults(jar, build(monkeypatch, tmp_path, m)), "larvesta stage 2 -> volcarona", "[59]")


# Without it the 45 step could lose Quiver Dance, the move the jar teaches on Larvesta's evolution.
def test_larvesta_losing_quiver_dance_on_its_evolution_is_a_fault(jar, monkeypatch, tmp_path):
    def m(sp, a):
        if sp == "larvesta":
            stage(a, A2)[0]["evolutions"][0]["learnableMoves"] = []
    assert_named(faults(jar, build(monkeypatch, tmp_path, m)), "drops the native evolution move(s) ['quiverdance']")


# Without it the weak form could jump straight to Volcarona at 30, skipping the grown form and the 45 point.
def test_larvesta_skipping_its_grown_form_is_a_fault(jar, monkeypatch, tmp_path):
    def m(sp, a):
        if sp == "larvesta":
            stage(a, A1)[0]["evolutions"][0]["result"] = "volcarona unaspect=%s" % A1
    assert_named(faults(jar, build(monkeypatch, tmp_path, m)), "stage 2 of the larvesta line is larvesta")


# Without it the line could take Volcarona's shape (135 SpA) at 330 and pass; the record says Larvesta's own.
# Hand check: the jar's Larvesta is 55/85/55/50/55/60 = 360, so at 330 Attack's share is 85*330/360 = 77.92 and
# Volcarona's shape (85/60/65/135/105/100 = 550) gives Attack 60*330/550 = 36, more than 1 off.
def test_larvesta_in_volcaronas_shape_is_a_fault(jar, monkeypatch, tmp_path):
    def m(sp, a):
        if sp == "larvesta":
            stage(a, A1)[0]["baseStats"] = {"hp": 51, "attack": 36, "defence": 39, "special_attack": 81,
                                            "special_defence": 63, "speed": 60}
    assert_named(faults(jar, build(monkeypatch, tmp_path, m)), "larvesta stage 1: attack 36 is not larvesta's share")


# Without it a wild Larvesta row could carry the starter aspect and put the 330 form in the grass; a plain wild row
# (data/spawns.json has three weighted ones) must still pass.
def test_a_wild_row_carrying_a_starter_form_is_a_fault(jar, monkeypatch, tmp_path):
    doc = json.loads(AU.SPAWNS.read_text(encoding="utf-8"))
    larv = [r for r in doc["entries"] if r["species"].split()[0] == "larvesta" and (r.get("weight") or 0) > 0]
    assert larv, "the fixture no longer has a wild Larvesta"
    pack = build(monkeypatch, tmp_path)
    assert faults(jar, pack) == []
    larv[0]["species"] = "larvesta aspect=%s" % A1
    spawns = tmp_path / "spawns.json"
    spawns.write_text(json.dumps(doc), encoding="utf-8")
    assert_named(faults(jar, pack, spawns=spawns), "carries a starter form ['aspect=%s']" % A1)


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


# ------------------------------------------------------------------------- Smeargle, the seventh (2026-10-08)
# Smeargle has no evolution, so its 45 step is a third form of its own; every form has Protean and keeps Sketch, and
# the pack carries the Sketch cap. Each case mutates the GENERATOR (addition, sketch_override or sketch_files); the
# expectation is the audit's FORM_FINALS / SKETCH_CAP, the owner's numbers.

def _smeargle_forms(fn):
    def m(sp, a):
        if sp == "smeargle":
            for f in a["forms"]:
                fn(f)
    return m


def _drop_third(sp, a):
    if sp == "smeargle":
        a["forms"][1]["evolutions"] = []


def _spore(f):
    f["moves"] = f["moves"] + ["1:spore"]


@pytest.mark.parametrize("mutate, needle", [
    # Without it a form could fall back to Smeargle's own Own Tempo / Technician / Moody and pass
    (_smeargle_forms(lambda f: f.pop("abilities")), "smeargle stage 1: abilities None; the decision is protean"),
    # ...or carry Protean only as its hidden ability, which a starter never rolls
    (_smeargle_forms(lambda f: f.update(abilities=["owntempo", "h:protean"])), "smeargle stage 2: abilities"),
    # Without it the 45 step could be lost and Smeargle stop at 430 for the rest of the game
    (_drop_third, "smeargle stage 2: 0 evolutions; the decision is one step, into the third form"),
    # Without it Spore could be a level-up move, which the decision keeps for Sketch alone
    (_smeargle_forms(_spore), "the decision is that they arrive only through Sketch"),
    # Without it a form could lose Sketch from its learnset
    (_smeargle_forms(lambda f: f.update(moves=[e for e in f["moves"] if e != "1:sketch"])), "sketch is not learnt at 1"),
])
def test_a_smeargle_form_off_the_decision_is_a_fault(jar, monkeypatch, tmp_path, mutate, needle):
    assert_named(faults(jar, build(monkeypatch, tmp_path, mutate)), needle)


# Without it the override could refuse at a count the decision did not set (or never), or a callback could be dropped
# and the count never rise, and the audit would still pass.
@pytest.mark.parametrize("part, needle", [
    ("guard", "does not carry 'if (source.dynamaxLevel >= 10) return false;'"),
    ("callback", "battle_fled/cobblers_sketch_cap.molang is missing"),
    ("comment", "a // or unbalanced comment"),
])
def test_the_sketch_cap_off_the_decision_is_a_fault(jar, monkeypatch, tmp_path, part, needle):
    if part in ("guard", "comment"):
        original = MS.sketch_override

        def override(cap, z):
            text = original(cap, z)
            if part == "guard":
                return text.replace(">= %d)" % cap, ">= %d)" % (cap + 1))
            return text.replace("const move = target.lastMove;", "const move = target.lastMove; // copied")
        monkeypatch.setattr(MS, "sketch_override", override)
    else:
        original_cb = MS.sketch_files
        monkeypatch.setattr(MS, "sketch_files", lambda line: {k: v for k, v in original_cb(line).items()
                                                              if "battle_fled" not in k})
    assert_named(faults(jar, build(monkeypatch, tmp_path)), needle)


# ------------------------------------------------------------------------- independent review, 2026-10-08
# Written by the reviewer of 4012bdb (Misdreavus) and d9c422d (Smeargle), not by either builder: neither unit
# mutation-tested its own new checks (the per-stage shape, the cross-species step, Smeargle's third form and the Sketch
# cap's files). Every case below mutates the GENERATOR's output (`addition`, `files`, `sketch_files`) and leaves the
# record alone; every expected number is hand-computed from the jar's base stats or the owner's spread, not read from
# the generator. Not covered (runtime, EXP-068 / EXP-065): the step into Flutter Mane happening in game, the aspect
# being removed there, and the Sketch cap counting.

def _on(species, aspect, fn):
    """Apply fn to our form of `species` that carries exactly [aspect]."""
    def m(sp, a):
        if sp == species:
            for f in stage(a, aspect):
                fn(f)
    return m


def _stats(hp, atk, de, spa, spd, spe):
    return {"hp": hp, "attack": atk, "defence": de, "special_attack": spa, "special_defence": spd, "speed": spe}


def _result(text):
    def fn(f):
        f["evolutions"][0]["result"] = text
    return fn


A3 = "cobblers_starter_3"


@pytest.mark.parametrize("mutate, needle", [
    # Without it stage 1 could be scaled into Mismagius's shape (the older one-species pattern: 330 x 60/495 = 40,
    # 105/495 = 70) instead of its own, Misdreavus's 60/60/60/85/85/85: hp share 60 x 330 / 435 = 45.52
    (_on("misdreavus", A1, lambda f: f.update(baseStats=_stats(40, 40, 40, 70, 70, 70))),
     "misdreavus stage 1: hp 40 is not misdreavus's share 45.52 of 330"),
    # Without it stage 2 could stay in Misdreavus's shape (430 x 60/435 = 59.3); Mismagius's share is 60 x 430/495
    (_on("mismagius", A2, lambda f: f.update(baseStats=_stats(59, 59, 59, 84, 84, 85))),
     "misdreavus stage 2: hp 59 is not mismagius's share 52.12 of 430"),
])
def test_a_misdreavus_stage_in_the_wrong_species_shape_is_a_fault(jar, monkeypatch, tmp_path, mutate, needle):
    assert_named(faults(jar, build(monkeypatch, tmp_path, mutate)), needle)


@pytest.mark.parametrize("mutate, needle", [
    # Without it the 45 step could point at another species (here another paradox) with the aspect handling kept
    (_on("mismagius", A2, _result("screamtail unaspect=%s" % A2)),
     "misdreavus: stage 2 reaches ['screamtail']; the jar's native finals are ['fluttermane']"),
    # ...or back into Mismagius, so the line never leaves stage 2's species
    (_on("mismagius", A2, _result("mismagius unaspect=%s" % A2)),
     "misdreavus: stage 2 reaches ['mismagius']"),
    # Without it Flutter Mane could keep cobblers_starter_2: a final carrying our aspect (finals stay native)
    (_on("mismagius", A2, _result("fluttermane")), "the final keeps our aspect ['cobblers_starter_2']"),
    # Without it the starter Misdreavus could also take a Dusk Stone before 30 (the jar's own Misdreavus step)
    (_on("misdreavus", A1, lambda f: f["evolutions"].append(
        {"id": "x", "variant": "item_interact", "result": "mismagius unaspect=%s aspect=%s" % (A1, A2),
         "requiredContext": "cobblemon:dusk_stone", "requirements": []})),
     "variant 'item_interact'; the decision advances this step by level_up"),
])
def test_the_cross_species_step_off_the_decision_is_a_fault(jar, monkeypatch, tmp_path, mutate, needle):
    assert_named(faults(jar, build(monkeypatch, tmp_path, mutate)), needle)


# Without it our pack could add forms to Flutter Mane itself, so the final would not be the jar's own species.
def test_a_form_on_the_cross_species_final_is_a_fault(jar, monkeypatch, tmp_path):
    extra = {"data/cobblers/species_additions/x_fluttermane.json":
             {"target": "cobblemon:fluttermane", "forms": [{"name": "Starter", "aspects": [A2]}]}}
    assert_named(faults(jar, build(monkeypatch, tmp_path, extra=extra)), "adds to fluttermane")


# Without it the premise could quietly change under a new jar: a Mismagius that evolves natively (so the tagged step
# displaces something) or a Flutter Mane that joins a line. These mutate the JAR's view, because the premise is the
# jar's; the generator and record are untouched.
@pytest.mark.parametrize("sp, change, needle", [
    ("mismagius", {"evolutions": [{"variant": "level_up", "result": "fluttermane"}]},
     "the jar now gives mismagius a native evolution"),
    ("fluttermane", {"preEvolution": "mismagius"}, "the jar now relates fluttermane to a line"),
])
def test_the_cross_species_premise_is_checked_against_the_jar(jar, monkeypatch, tmp_path, sp, change, needle):
    pack = build(monkeypatch, tmp_path)
    original = AU.load_jar

    def changed(j):
        species, moves = original(j)
        species = dict(species)
        species[sp] = dict(species[sp], **change)
        return species, moves
    monkeypatch.setattr(AU, "load_jar", changed)
    assert_named(faults(jar, pack), needle)


@pytest.mark.parametrize("mutate, needle", [
    # Without it the third form could leave the owner's 74/79/60/79/60/98 (attack and speed swapped: share 79.00)
    (_on("smeargle", A3, lambda f: f.update(baseStats=_stats(74, 98, 60, 79, 60, 79))),
     "smeargle stage 3: attack 98 is not the decided spread's share 79.00 of 450"),
    # Without it stage 1 could be scaled into the jar's Smeargle (55/20/35/20/45/75) instead: hp 74 x 330/450
    (_on("smeargle", A1, lambda f: f.update(baseStats=_stats(73, 26, 46, 26, 60, 99))),
     "smeargle stage 1: hp 73 is not the decided spread's share 54.27 of 330"),
    # Without it the third form alone could lose Protean (the earlier case strips every form at once)
    (_on("smeargle", A3, lambda f: f.pop("abilities")), "smeargle stage 3: abilities None"),
    # Without it the third form could evolve on, and the line would not stay at 450
    (_on("smeargle", A3, lambda f: f.update(evolutions=[{"variant": "level_up", "result": "smeargle"}])),
     "the third form is where the line stays"),
    # Without it the 45 step could leave Smeargle for another species
    (_on("smeargle", A2, _result("exploud unaspect=%s aspect=%s" % (A2, A3))), "the third form is smeargle's own"),
    # Without it the 45 step could drop cobblers_starter_2 without adding _3, landing on plain Smeargle
    (_on("smeargle", A2, _result("smeargle unaspect=%s" % A2)), "the third form needs exactly cobblers_starter_3"),
])
def test_smeargles_third_form_off_the_decision_is_a_fault(jar, monkeypatch, tmp_path, mutate, needle):
    assert_named(faults(jar, build(monkeypatch, tmp_path, mutate)), needle)


# Without it, since d9c422d taught the generator to emit a stage's `abilities`, any other line's form could carry an
# ability pool (Protean on Cosmog) and pass: the audit only looked at abilities on Smeargle.
def test_an_ability_pool_on_a_line_the_decision_gives_none_is_a_fault(jar, monkeypatch, tmp_path):
    m = _on("cosmog", A1, lambda f: f.update(abilities=["protean", "h:protean"]))
    assert_named(faults(jar, build(monkeypatch, tmp_path, m)), "cosmog stage 1: abilities ['protean', 'h:protean']")


@pytest.mark.parametrize("event", ["battle_started_post", "battle_victory", "battle_fled"])
# Without it any one of the three callbacks could be dropped (the earlier case drops only battle_fled)
def test_each_sketch_callback_is_required(jar, monkeypatch, tmp_path, event):
    original = MS.sketch_files
    monkeypatch.setattr(MS, "sketch_files", lambda line: {k: v for k, v in original(line).items() if event not in k})
    assert_named(faults(jar, build(monkeypatch, tmp_path)), "%s/cobblers_sketch_cap.molang is missing" % event)


# Without it the callbacks could count to a number other than the decided 10 while the override still refused at 10.
def test_sketch_callbacks_that_stop_short_of_ten_are_a_fault(jar, monkeypatch, tmp_path):
    original = MS.sketch_files

    def nine(line):
        line = copy.deepcopy(line)
        line["sketch_cap"]["uses"] = 9
        return original(line)
    monkeypatch.setattr(MS, "sketch_files", nine)
    assert_named(faults(jar, build(monkeypatch, tmp_path)),
                 "battle_victory/cobblers_sketch_cap.molang never raises the count to 10")


# Without it the move override itself could be missing and Sketch would be uncapped.
def test_a_missing_sketch_override_is_a_fault(jar, monkeypatch, tmp_path):
    original = MS.files
    monkeypatch.setattr(MS, "files", lambda doc, jar=None: {k: v for k, v in original(doc, jar).items()
                                                             if not k.endswith("moves/sketch.js")})
    assert_named(faults(jar, build(monkeypatch, tmp_path)), "data/cobblers/moves/sketch.js is missing")


# Without it the audit could start reusing the builder's own derivation and agree with it about anything.
def test_the_audit_does_not_import_the_builder():
    src = (ROOT / "tools" / "mythical_starters_audit.py").read_text(encoding="utf-8")
    assert "import mythical_starters" not in src and "from mythical_starters" not in src

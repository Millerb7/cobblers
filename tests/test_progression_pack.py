"""tools/progression_pack.py: data/progression.json -> progression datapack.

Covers validity of the generated pack (paths, JSON, command shape, determinism)
and fail-closed validation. It does NOT prove runtime behavior: whether
rctmod:defeat_count fires, whether `waystones activate/forget` take effect, or
whether the used_waystone re-sync beats a right-click unlock all need a player
on a running server (EXP-020).
"""
import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import progression_pack as PP  # noqa: E402

REAL_DATA = ROOT / "data" / "progression.json"
REAL_PLACEMENTS = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf8"))
NS = "cobblers"
KNOWN_COMMANDS = {"execute", "function", "advancement", "tag", "schedule", "scoreboard", "waystones", "tellraw"}


def _doc(**over):
    """A small valid document: two series, a gym flag with a placed waystone,
    a gym flag with an unplaced one, a run_start flag and a trigger flag."""
    doc = {
        "schema": "cobblers.progression/1",
        "namespace": NS,
        "active_series": "kanto",
        "series": [{"id": "kanto"}, {"id": "johto"}],
        "flags": [
            {"id": "gym2_cleared",
             "set_by": {"kind": "trainer_defeat",
                        "trainer_ids": {"kanto": ["kanto_misty"], "johto": ["johto_whitney"]}},
             "waystone": {"town": "zeta_town", "position": [100, 64, -200]}},
            {"id": "gym1_cleared",
             "set_by": {"kind": "trainer_defeat",
                        "trainer_ids": {"kanto": ["kanto_brock", "kanto_brock_rematch"],
                                        "johto": ["johto_falkner"]}},
             "waystone": {"town": "alpha_town", "position": None}},
            {"id": "run_started", "set_by": {"kind": "run_start"},
             "waystone": {"town": "home_town", "position": [0, 70, 0],
                          "dimension": "cobblers:region"}},
            {"id": "debug_unlock", "set_by": {"kind": "trigger", "objective": "cobblers.debug"}},
        ],
    }
    doc.update(over)
    return doc


def _flag(doc, fid):
    return next(f for f in doc["flags"] if f["id"] == fid)


def _pack(doc=None, series=None):
    return PP.files(PP.plan(doc or _doc(), series))


def _lines(text):
    return text.splitlines()


# ---------------------------------------------------------------- plan(): fail closed


def test_load_rejects_wrong_schema(tmp_path):
    # Without this a file for another schema version would be half-read into a pack.
    p = tmp_path / "progression.json"
    p.write_text(json.dumps(_doc(schema="cobblers.progression/2")), encoding="utf8")
    with pytest.raises(PP.ProgressionError, match="schema"):
        PP.load(p)


def test_load_accepts_right_schema(tmp_path):
    # Guards the negative test above against a load() that rejects everything.
    p = tmp_path / "progression.json"
    p.write_text(json.dumps(_doc()), encoding="utf8")
    assert PP.load(p)["active_series"] == "kanto"


def test_plan_requires_an_active_series():
    # Without this a pack with no series would build advancements for nobody's leaders.
    doc = _doc()
    del doc["active_series"]
    with pytest.raises(PP.ProgressionError, match="active_series"):
        PP.plan(doc)


def test_plan_rejects_active_series_not_declared():
    # Without this a typo in active_series would silently fail every trainer lookup later.
    with pytest.raises(PP.ProgressionError, match="not declared"):
        PP.plan(_doc(active_series="kantoo"))


@pytest.mark.parametrize("bad_id", ["Gym1", "gym-1", "gym 1", "", None, "flag/x"])
def test_plan_rejects_invalid_flag_id(bad_id):
    # Without this a flag id could produce an unloadable advancement path.
    doc = _doc()
    doc["flags"][0]["id"] = bad_id
    with pytest.raises(PP.ProgressionError, match="not a valid id"):
        PP.plan(doc)


def test_plan_rejects_duplicate_flag_id():
    # Without this the second flag would overwrite the first flag's advancement file.
    doc = _doc()
    doc["flags"][1]["id"] = doc["flags"][0]["id"]
    with pytest.raises(PP.ProgressionError, match="declared twice"):
        PP.plan(doc)


@pytest.mark.parametrize("set_by", [{"kind": "item_pickup"}, {}, "trainer_defeat", None])
def test_plan_rejects_unknown_set_by_kind(set_by):
    # Without this an unsupported kind would fall through to minecraft:impossible silently.
    doc = _doc()
    doc["flags"][0]["set_by"] = set_by
    with pytest.raises(PP.ProgressionError, match="set_by.kind"):
        PP.plan(doc)


@pytest.mark.parametrize("trainer_ids", [{"johto": ["johto_whitney"]}, {"kanto": []}, None])
def test_plan_rejects_trainer_defeat_without_ids_for_active_series(trainer_ids):
    # Without this a gym flag would get an empty criterion and never (or always) be set.
    doc = _doc()
    doc["flags"][0]["set_by"]["trainer_ids"] = trainer_ids
    with pytest.raises(PP.ProgressionError, match="no trainer_ids for series 'kanto'"):
        PP.plan(doc)


@pytest.mark.parametrize("objective", ["Cobblers.Debug", "a" * 33, "has space", "", None])
def test_plan_rejects_invalid_trigger_objective(objective):
    # Without this `scoreboard objectives add` in load would fail and the trigger never work.
    doc = _doc()
    _flag(doc, "debug_unlock")["set_by"]["objective"] = objective
    with pytest.raises(PP.ProgressionError, match="trigger objective"):
        PP.plan(doc)


def test_plan_accepts_trigger_objective_of_exactly_32_chars():
    # Guards the length boundary so the >32 rejection is not an off-by-one.
    doc = _doc()
    _flag(doc, "debug_unlock")["set_by"]["objective"] = "a" * 32
    assert any(f.get("objective") == "a" * 32 for f in PP.plan(doc)["flags"])


def test_plan_rejects_waystone_without_town():
    # Without this a waystone would be keyed under None and reconcile would have no town.
    doc = _doc()
    del doc["flags"][0]["waystone"]["town"]
    with pytest.raises(PP.ProgressionError, match="no town"):
        PP.plan(doc)


def test_plan_rejects_empty_waystone_object():
    # Without this a half-written waystone entry vanishes from the pack with no error.
    doc = _doc()
    doc["flags"][0]["waystone"] = {}
    with pytest.raises(PP.ProgressionError, match="no town"):
        PP.plan(doc)


def test_plan_rejects_same_town_on_two_flags():
    # Without this one town's waystone would follow whichever flag was declared last.
    doc = _doc()
    doc["flags"][1]["waystone"]["town"] = doc["flags"][0]["waystone"]["town"]
    with pytest.raises(PP.ProgressionError, match="two flags"):
        PP.plan(doc)


@pytest.mark.parametrize("position", [[1, 2], [1, 2, 3, 4], [1.0, 64, 2], [1, 64.5, 2],
                                      ["1", "64", "2"], {"x": 1, "y": 2, "z": 3}, "1 64 2"])
def test_plan_rejects_malformed_waystone_position(position):
    # Without this reconcile would emit `%d` of a float/str or crash while unpacking.
    doc = _doc()
    doc["flags"][0]["waystone"]["position"] = position
    with pytest.raises(PP.ProgressionError, match="position"):
        PP.plan(doc)


def test_plan_rejects_boolean_waystone_position():
    # Without this a JSON typo of true/false turns into a real coordinate in reconcile.
    doc = _doc()
    doc["flags"][0]["waystone"]["position"] = [True, 64, False]
    with pytest.raises(PP.ProgressionError, match="position"):
        PP.plan(doc)


def test_plan_rejects_trainer_ids_that_are_not_a_list():
    # Without this "kanto_brock" (no brackets) becomes eleven one-letter trainer ids.
    doc = _doc()
    doc["flags"][0]["set_by"]["trainer_ids"]["kanto"] = "kanto_misty"
    with pytest.raises(PP.ProgressionError):
        PP.plan(doc)


# ---------------------------------------------------------------- --series override


def test_series_override_selects_that_series_trainer_ids():
    # Without this the prestige build (--series johto) would still require Kanto leaders.
    p = PP.plan(_doc(), "johto")
    assert p["series"] == "johto"
    by_id = {f["id"]: f for f in p["flags"]}
    assert by_id["gym1_cleared"]["trainer_ids"] == ["johto_falkner"]
    assert by_id["gym2_cleared"]["trainer_ids"] == ["johto_whitney"]
    adv = json.loads(PP.files(p)["data/%s/advancement/flag/gym1_cleared.json" % NS])
    assert adv["criteria"]["defeated"]["conditions"]["trainer_ids"] == ["johto_falkner"]


def test_series_override_rejects_undeclared_series():
    # Without this --series with a typo would build a pack against a series that does not exist.
    with pytest.raises(PP.ProgressionError, match="not declared"):
        PP.plan(_doc(), "hoenn")


def test_series_override_rejects_declared_series_missing_trainer_ids():
    # Without this a prestige series added to series[] before its leaders are mapped would build.
    doc = _doc(series=[{"id": "kanto"}, {"id": "johto"}, {"id": "hoenn"}])
    with pytest.raises(PP.ProgressionError, match="no trainer_ids for series 'hoenn'"):
        PP.plan(doc, "hoenn")


# ---------------------------------------------------------------- files(): advancements


def test_pack_mcmeta_targets_minecraft_1_21_1():
    # Without this a pack_format change would make 1.21.1 refuse or warn on the pack.
    meta = json.loads(_pack()["pack.mcmeta"])
    assert meta["pack"]["pack_format"] == 48


def test_one_flag_advancement_per_flag_and_no_others():
    # Without this a flag could be missing its advancement, or a stale one could be emitted.
    out = _pack()
    got = {k for k in out if k.startswith("data/%s/advancement/flag/" % NS)}
    want = {"data/%s/advancement/flag/%s.json" % (NS, f["id"]) for f in _doc()["flags"]}
    assert got == want


def test_trainer_defeat_flag_uses_rct_defeat_count_with_exact_ids():
    # Without this a flag could be set by the wrong leader, or by a count the first win does not reach. rctmod
    # 0.19.0 records the defeat (TrainerBattleMemory.addDefeatedBy) before it fires the trigger, so on a first win
    # the player's count is already 1 when `count` is compared; it is pinned to 1 rather than left to the codec.
    adv = json.loads(_pack()["data/%s/advancement/flag/gym1_cleared.json" % NS])
    assert list(adv["criteria"]) == ["defeated"]
    crit = adv["criteria"]["defeated"]
    assert crit["trigger"] == "rctmod:defeat_count"
    assert crit["conditions"] == {"trainer_ids": ["kanto_brock", "kanto_brock_rematch"], "count": 1}


def test_flag_report_fails_on_a_world_with_no_players(tmp_path, capsys):
    # Without this the staging proof could "pass" by reading a world nobody has joined: no advancement files,
    # so no player lacks a flag and nothing looks wrong.
    assert PP.report(PP.plan(_doc()), tmp_path) == 1
    assert "FAIL" in capsys.readouterr().out


def test_flag_report_shows_each_player_only_their_own_flags(tmp_path, capsys):
    # Without this a flag landing on the wrong player, or on every player, would not show in the proof.
    adv = tmp_path / "advancements"
    adv.mkdir()
    (adv / "aaaaaaaa-0000-0000-0000-000000000001.json").write_text(json.dumps(
        {"%s:flag/gym1_cleared" % NS: {"criteria": {"defeated": "x"}, "done": True}}), encoding="utf8")
    (adv / "bbbbbbbb-0000-0000-0000-000000000002.json").write_text(json.dumps(
        {"%s:flag/gym2_cleared" % NS: {"criteria": {}, "done": False}}), encoding="utf8")
    assert PP.report(PP.plan(_doc()), tmp_path) == 0
    out = capsys.readouterr().out.splitlines()
    assert any(l.startswith("player aaaaaaaa") and "gym1_cleared" in l and "gym2" not in l for l in out)
    assert any(l.startswith("player bbbbbbbb") and ": 0 of" in l for l in out)


def test_run_start_flag_uses_tick_and_trigger_flag_is_impossible():
    # Without this run_start would never set, or a trigger flag could be earned by gameplay.
    out = _pack()
    start = json.loads(out["data/%s/advancement/flag/run_started.json" % NS])
    trig = json.loads(out["data/%s/advancement/flag/debug_unlock.json" % NS])
    assert [c["trigger"] for c in start["criteria"].values()] == ["minecraft:tick"]
    assert [c["trigger"] for c in trig["criteria"].values()] == ["minecraft:impossible"]


def test_every_flag_reward_function_exists_and_reconciles():
    # Without this setting a flag would reference a missing function and never unlock the waystone.
    out = _pack()
    for f in _doc()["flags"]:
        adv = json.loads(out["data/%s/advancement/flag/%s.json" % (NS, f["id"])])
        ref = adv["rewards"]["function"]
        assert ref == "%s:flag/%s/granted" % (NS, f["id"])
        ns, path = ref.split(":", 1)
        body = out["data/%s/function/%s.mcfunction" % (ns, path)]
        assert "function %s:navigation/reconcile" % NS in _lines(body)


def test_custom_namespace_is_used_for_every_data_path():
    # Without this a namespace change would leave files under cobblers and break references.
    out = _pack(_doc(namespace="myrun"))
    data = [k for k in out if k.startswith("data/") and not k.startswith("data/minecraft/")]
    assert data and all(k.startswith("data/myrun/") for k in data)
    text = "".join(v for k, v in out.items() if k.endswith((".mcfunction", ".json")))
    # cobblers:region (the fixture's dimension) and cobblers.debug (its objective) are data, not ns.
    assert not re.search(r"cobblers:(flag|navigation|load|tick)\b", text)
    assert "cobblers.resync" not in text and "cobblers.left" not in text


# ---------------------------------------------------------------- reconcile


def _reconcile(doc=None):
    return _lines(_pack(doc)["data/%s/function/navigation/reconcile.mcfunction" % NS])


def test_placed_waystone_has_one_guarded_activate_and_one_guarded_forget():
    # Without this a waystone could unlock without its flag, or never be revoked when unset.
    lines = _reconcile()
    act = [l for l in lines if "waystones activate" in l and "100 64 -200" in l]
    fgt = [l for l in lines if "waystones forget" in l and "100 64 -200" in l]
    assert act == ["execute if entity @s[advancements={cobblers:flag/gym2_cleared=true}] "
                   "in minecraft:overworld run waystones activate @s 100 64 -200"]
    assert fgt == ["execute if entity @s[advancements={cobblers:flag/gym2_cleared=false}] "
                   "in minecraft:overworld run waystones forget @s 100 64 -200"]


def test_placed_waystone_honours_custom_dimension():
    # Without this a waystone in a custom dimension would be looked up in the overworld.
    lines = [l for l in _reconcile() if "0 70 0" in l]
    assert len(lines) == 2
    assert all(" in cobblers:region run waystones " in l for l in lines)
    assert all("minecraft:overworld" not in l for l in lines)


def test_unplaced_town_appears_only_as_comment():
    # Without this a null position could reach a command as `None` or be silently dropped.
    lines = _reconcile()
    mentions = [l for l in lines if "alpha_town" in l]
    assert mentions and all(l.startswith("#") for l in mentions)
    assert not [l for l in lines if not l.startswith("#") and "gym1_cleared" in l]
    assert PP.plan(_doc())["unplaced"] == ["alpha_town"]


def test_reconcile_is_sorted_by_town_and_deterministic():
    # Without this regenerating the pack would produce noisy diffs from dict ordering.
    doc = _doc()
    marker = {"alpha_town": "alpha_town", "home_town": " 0 70 0", "zeta_town": " 100 64 -200"}
    order = []
    for line in _reconcile(doc):
        town = next((t for t, m in marker.items() if m in line), None)
        if town and town not in order:
            order.append(town)
    assert order == ["alpha_town", "home_town", "zeta_town"]
    shuffled = copy.deepcopy(doc)
    shuffled["flags"].reverse()
    assert _pack(doc) == _pack(copy.deepcopy(doc))
    assert _reconcile(doc) == _reconcile(shuffled)


# ---------------------------------------------------------------- hooks


def test_used_waystone_advancement_matches_any_waystone_block():
    # Without this using a waystone would not trigger the re-sync that undoes early unlocks.
    adv = json.loads(_pack()["data/%s/advancement/navigation/used_waystone.json" % NS])
    crit = adv["criteria"]["used"]
    assert crit["trigger"] == "minecraft:any_block_use"
    blocks = [c["predicate"]["block"]["blocks"] for c in crit["conditions"]["location"]
              if c["condition"] == "minecraft:location_check"]
    assert blocks == ["#waystones:waystones"]
    assert adv["rewards"]["function"] == "%s:navigation/on_use" % NS


def test_on_use_revokes_tags_and_defers_one_tick():
    # Without this the hook fires once per player ever, or reconciles before Waystones unlocks.
    lines = _lines(_pack()["data/%s/function/navigation/on_use.mcfunction" % NS])
    assert "advancement revoke @s only cobblers:navigation/used_waystone" in lines
    assert "tag @s add cobblers.resync" in lines
    assert "schedule function cobblers:navigation/deferred 1t replace" in lines


def test_deferred_reconciles_tagged_players_then_clears_tag():
    # Without this deferred would reconcile nobody, or keep re-syncing the same players forever.
    lines = _lines(_pack()["data/%s/function/navigation/deferred.mcfunction" % NS])
    run = "execute as @a[tag=cobblers.resync] at @s run function cobblers:navigation/reconcile"
    clear = "tag @a remove cobblers.resync"
    assert run in lines and clear in lines
    assert lines.index(run) < lines.index(clear)


def test_load_and_tick_function_tags_point_at_pack_functions():
    # Without this load/tick never run and join re-sync and triggers are dead.
    out = _pack()
    assert json.loads(out["data/minecraft/tags/function/load.json"]) == {"values": ["cobblers:load"]}
    assert json.loads(out["data/minecraft/tags/function/tick.json"]) == {"values": ["cobblers:tick"]}
    assert "data/cobblers/function/load.mcfunction" in out
    assert "data/cobblers/function/tick.mcfunction" in out


def test_tick_resyncs_rejoining_players_and_resets_leave_score():
    # Without this a player who rejoins keeps waystone state from before a flag was revoked.
    out = _pack()
    load = _lines(out["data/cobblers/function/load.mcfunction"])
    tick = _lines(out["data/cobblers/function/tick.mcfunction"])
    assert "scoreboard objectives add cobblers.left minecraft.custom:minecraft.leave_game" in load
    run = "execute as @a[scores={cobblers.left=1..}] at @s run function cobblers:navigation/reconcile"
    reset = "scoreboard players reset @a[scores={cobblers.left=1..}] cobblers.left"
    assert run in tick and reset in tick
    assert tick.index(run) < tick.index(reset)


def test_trigger_flag_adds_objective_and_enables_grants_resets_in_tick():
    # Without this `/trigger cobblers.debug` would be unavailable or grant the flag every tick.
    out = _pack()
    load = _lines(out["data/cobblers/function/load.mcfunction"])
    tick = _lines(out["data/cobblers/function/tick.mcfunction"])
    assert "scoreboard objectives add cobblers.debug trigger" in load
    enable = "scoreboard players enable @a[advancements={cobblers:flag/debug_unlock=false}] cobblers.debug"
    grant = "execute as @a[scores={cobblers.debug=1..}] run advancement grant @s only cobblers:flag/debug_unlock"
    reset = "scoreboard players reset @a[scores={cobblers.debug=1..}] cobblers.debug"
    for line in (enable, grant, reset):
        assert line in tick
    assert tick.index(grant) < tick.index(reset)


def test_no_trigger_flags_means_no_trigger_objectives():
    # Without this a pack with no trigger flags could still expose a /trigger to players.
    doc = _doc()
    doc["flags"] = [f for f in doc["flags"] if f["set_by"]["kind"] != "trigger"]
    out = _pack(doc)
    assert " trigger" not in out["data/cobblers/function/load.mcfunction"]
    assert "enable" not in out["data/cobblers/function/tick.mcfunction"]


# ---------------------------------------------------------------- whole-pack shape


def _all_packs():
    real = PP.plan(PP.load(REAL_DATA), placements=REAL_PLACEMENTS)
    return [PP.files(PP.plan(_doc())), PP.files(PP.plan(_doc(), "johto")), PP.files(real)]


def test_every_mcfunction_line_starts_with_a_known_command():
    # Without this a typo'd command word would only surface as a load error on the server.
    for out in _all_packs():
        for rel, text in out.items():
            if not rel.endswith(".mcfunction"):
                continue
            for n, line in enumerate(_lines(text), 1):
                if not line.strip() or line.startswith("#"):
                    continue
                assert line.split(" ", 1)[0] in KNOWN_COMMANDS, "%s:%d: %r" % (rel, n, line)


def test_every_json_file_parses():
    # Without this a broken JSON file would disable the whole datapack at load.
    for out in _all_packs():
        for rel, text in out.items():
            if rel.endswith(".json") or rel.endswith(".mcmeta"):
                json.loads(text)


def test_every_function_reference_resolves_to_a_generated_file():
    # Without this a renamed function would leave dangling `function` calls and rewards.
    for out in _all_packs():
        refs = set()
        for rel, text in out.items():
            if rel.endswith(".mcfunction"):
                refs.update(re.findall(r"function ([a-z0-9_.]+:[a-z0-9_./]+)", text))
            elif rel.endswith(".json") and "/advancement/" in rel:
                fn = json.loads(text).get("rewards", {}).get("function")
                if fn:
                    refs.add(fn)
            elif rel.startswith("data/minecraft/tags/function/"):
                refs.update(json.loads(text)["values"])
        for ref in refs:
            ns, path = ref.split(":", 1)
            assert "data/%s/function/%s.mcfunction" % (ns, path) in out, ref


# ---------------------------------------------------------------- write() and main()


def test_write_replaces_stale_output_dir(tmp_path):
    # Without this a flag removed from data would keep its old advancement in the built pack.
    out_dir = tmp_path / "pack"
    stale = out_dir / "data" / NS / "advancement" / "flag" / "removed_flag.json"
    stale.parent.mkdir(parents=True)
    stale.write_text("{}", encoding="utf8")
    (out_dir / "pack.mcmeta").write_text("{}", encoding="utf8")
    written = PP.write(PP.plan(_doc()), out_dir)
    assert not stale.exists()
    on_disk = sorted(p.relative_to(out_dir).as_posix() for p in out_dir.rglob("*") if p.is_file())
    assert on_disk == written == sorted(_pack())


def test_write_refuses_to_replace_a_directory_that_is_not_a_datapack(tmp_path):
    # Without this a mistyped --out would delete an unrelated directory.
    out_dir = tmp_path / "notes"
    out_dir.mkdir()
    (out_dir / "keep.txt").write_text("x", encoding="utf8")
    with pytest.raises(PP.ProgressionError, match="not a datapack"):
        PP.write(PP.plan(_doc()), out_dir)
    assert (out_dir / "keep.txt").exists()


def test_write_uses_lf_line_endings(tmp_path):
    # Without this Windows builds would differ byte-for-byte from Linux builds.
    PP.write(PP.plan(_doc()), tmp_path / "pack")
    raw = (tmp_path / "pack" / "data" / NS / "function" / "navigation" / "reconcile.mcfunction").read_bytes()
    assert b"\r\n" not in raw


def test_main_builds_real_data_into_out(tmp_path, capsys):
    # Without this the documented CLI entry point could break while plan()/files() still pass.
    out_dir = tmp_path / "pack"
    assert PP.main(["--data", str(REAL_DATA), "--out", str(out_dir)]) == 0
    assert (out_dir / "pack.mcmeta").is_file()
    assert "series kanto" in capsys.readouterr().out


def test_main_series_override_builds_prestige_pack(tmp_path):
    # Without this `--series johto` could be parsed but ignored.
    out_dir = tmp_path / "pack"
    assert PP.main(["--data", str(REAL_DATA), "--series", "johto", "--out", str(out_dir)]) == 0
    adv = json.loads((out_dir / "data/cobblers/advancement/flag/gym1_cleared.json").read_text(encoding="utf8"))
    assert adv["criteria"]["defeated"]["conditions"]["trainer_ids"] == ["johto_valerio"]


def test_main_returns_1_with_message_on_bad_data(tmp_path, capsys):
    # Without this bad data would traceback or exit 0, and a CI step would not fail clearly.
    bad = tmp_path / "progression.json"
    doc = _doc()
    doc["flags"][1]["id"] = doc["flags"][0]["id"]
    bad.write_text(json.dumps(doc), encoding="utf8")
    out_dir = tmp_path / "pack"
    assert PP.main(["--data", str(bad), "--out", str(out_dir)]) == 1
    err = capsys.readouterr().err
    assert err.startswith("error: ") and "declared twice" in err
    assert not out_dir.exists()


def test_main_returns_1_on_missing_or_unparseable_file(tmp_path, capsys):
    # Without this a wrong --data path or a JSON syntax error would crash with a traceback.
    assert PP.main(["--data", str(tmp_path / "nope.json"), "--out", str(tmp_path / "a")]) == 1
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf8")
    assert PP.main(["--data", str(broken), "--out", str(tmp_path / "b")]) == 1
    assert capsys.readouterr().err.count("error: ") == 2


# ---------------------------------------------------------------- real data/progression.json


@pytest.fixture(scope="module")
def real_doc():
    return PP.load(REAL_DATA)


def test_real_progression_plans_for_active_series(real_doc):
    # Without this the checked-in data could stop building and only fail at server assembly.
    p = PP.plan(real_doc, placements=REAL_PLACEMENTS)
    assert p["series"] == real_doc["active_series"]
    assert len(p["flags"]) == len(real_doc["flags"])


def test_real_every_flag_has_trainer_ids_for_every_declared_series(real_doc):
    # Without this a prestige series could be declared but not buildable with --series.
    series = [s["id"] for s in real_doc["series"]]
    for fl in real_doc["flags"]:
        if fl["set_by"]["kind"] != "trainer_defeat":
            continue
        ids = fl["set_by"]["trainer_ids"]
        for s in series:
            assert isinstance(ids.get(s), list) and ids[s], "%s lacks trainer_ids for %s" % (fl["id"], s)
    for s in series:
        PP.plan(real_doc, s, REAL_PLACEMENTS)


def test_real_trainer_ids_unique_across_flags_within_each_series(real_doc):
    # Without this one leader's defeat could set two gym flags at once.
    for s in [x["id"] for x in real_doc["series"]]:
        seen = {}
        for fl in real_doc["flags"]:
            for tid in (fl["set_by"].get("trainer_ids") or {}).get(s, []):
                assert tid not in seen, "%s: %s used by %s and %s" % (s, tid, seen[tid], fl["id"])
                seen[tid] = fl["id"]


def test_real_waystone_positions_are_all_still_unplaced(real_doc):
    # Deliberate tripwire: positions are null until towns are placed after the next terrain
    # rendition. When the first town is placed, update this test (and review reconcile output).
    placed = {fl["id"]: fl["waystone"]["position"] for fl in real_doc["flags"]
              if fl.get("waystone") and fl["waystone"].get("position") is not None}
    assert placed == {}
    p = PP.plan(real_doc, placements=REAL_PLACEMENTS)
    assert p["unplaced"] == sorted(p["waystones"])


def _real_pack():
    return PP.files(PP.plan(PP.load(REAL_DATA), placements=REAL_PLACEMENTS))


def test_each_gym_flag_offers_the_next_gym_to_the_player_who_earned_it():
    # One gym ahead (NAVIGATION.md section 6). Without this a cleared gym leaves the player with Cobbleverse's map to
    # a gym this world does not have, or with nothing.
    out = _real_pack()
    order = ["Gym 2 Misty", "Gym 3 Lt Surge", "Gym 4 Erika", "Gym 5 Koga", "Gym 6 Sabrina", "Gym 7 Blaine",
             "Gym 8 Giovanni", "Pokemon League"]
    for i, name in enumerate(order, 1):
        text = out["data/cobblers/function/flag/gym%d_cleared/granted.mcfunction" % i]
        tell = [l for l in text.splitlines() if l.startswith("tellraw")]
        assert len(tell) == 1 and tell[0].startswith("tellraw @s "), text
        share = re.search(r"xaero-waypoint:([^\"]+)", tell[0]).group(0)
        fields = share.split(":")
        # Xaero 26.4.2 parses: name, initials, x, y, z, colour, rotation, yaw, destination
        assert len(fields) == 10 and fields[1] == name and fields[-1] == "Internal-overworld-waypoints", share
        assert all(re.fullmatch(r"-?\d+", f) for f in fields[3:7]) and fields[7] == "false"
    assert "tellraw" not in out["data/cobblers/function/flag/champion_cleared/granted.mcfunction"]


def test_the_league_marker_stands_on_the_league():
    # The marker is the middle of the placed building, not the template corner or the town centre.
    league = PP.plan(PP.load(REAL_DATA), placements=REAL_PLACEMENTS)["markers"]["league"]
    assert 3517 <= league["x"] <= 3636 and 2591 <= league["z"] <= 2701, league


def test_a_marker_with_a_character_xaero_cannot_carry_fails():
    # Xaero's share splits on ':' and rewrites '-' and '_': such a name would arrive mangled or not at all.
    doc = PP.load(REAL_DATA)
    doc["gym_markers"]["markers"]["gym2_town"]["name"] = "Gym 2: Misty"
    with pytest.raises(PP.ProgressionError, match="Xaero"):
        PP.plan(doc, placements=REAL_PLACEMENTS)


def test_a_flag_offering_an_undefined_marker_fails():
    doc = PP.load(REAL_DATA)
    del doc["gym_markers"]["markers"]["league"]
    with pytest.raises(PP.ProgressionError, match="does not define"):
        PP.plan(doc, placements=REAL_PLACEMENTS)


def test_cobbleverse_gym_maps_are_emptied_and_missing_rewards_defined():
    # The gym maps point at naturally generated gyms this world does not have; the reward functions are named by
    # Cobbleverse's leader advancements and defined nowhere. Both are overridden at the upstream paths.
    out = _real_pack()
    for region in ("gym_map", "johto_gym_map", "hoenn_gym_map", "sinnoh_gym_map"):
        assert json.loads(out["data/cobbleverse/loot_table/%s.json" % region]) == {"pools": []}
    for leader in ("brock", "misty", "ltsurge", "erika", "koga", "sabrina", "blaine", "giovanni"):
        assert "data/cobbleverse/function/%s_defeated.mcfunction" % leader in out

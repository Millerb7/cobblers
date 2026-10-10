"""The relics behind the secrets (tools/dungeon_relics.py, data/dungeon_relics.json), unit DG2-RELICS.

The builder's own tests (the independent audit is another agent's). What they prove and how:

  once per player   the GENERATED relic function is replayed on a small model of a player (advancements, score, inventory)
                    that reads the generated lines, not the generator's records: a second visit, a visit in a later run
                    after the slot's reset, and a death-and-return all leave one grant, one give and one count. A second
                    player in the same run still gets theirs.
  the collection    the advancement the pack carries is compared with the relic ids read from the FIXTURE FILE (not from the
                    generator's catalog): one impossible criterion per relic, all required; replaying every relic's function
                    completes it on the last and not before.
  the reset         the slot's reset chain is followed through the generated functions: the pedestal's state holder goes back
                    to 0 and its armed block comes back (the display), and nothing in the pack revokes an advancement or
                    resets, sets or removes a relic count (the record).
  the secret stays  the trigger is read back from the generated tick line (centre and radius) and checked against the room's
                    BUILT grid: no cell a player can walk to without the secret's trick is inside it.
  mutations         change the GENERATOR with the data untouched: the guard dropped, a trigger radius of 6, a pedestal on the
                    spot, a collection short of a criterion, a reset that revokes. Each must fail a check.

Not covered: anything in a running Minecraft (whether the selector form and the item components parse, whether the sound and
particle ids play, whether a goal-frame root advancement shows as a tab).
"""
from __future__ import annotations

import copy
import json
import re
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import dungeon as D  # noqa: E402
import dungeon_grid as G  # noqa: E402
import dungeon_relics as X  # noqa: E402
import dungeon_rooms as R  # noqa: E402
import function_limits as FL  # noqa: E402
import test_dungeon_rooms as TR  # noqa: E402

BASE = D.load()
FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "dungeon_relics_demo.json").read_text(encoding="utf-8"))
KIT2 = json.loads((ROOT / "tests" / "fixtures" / "dungeon_kit2_demo.json").read_text(encoding="utf-8"))
THEMES = ("mine", "jungle", "flooded_ruin")
FN = "data/cobblers/function/dungeons/"


def doc_of(theme, fixture=FIXTURE, edit=None):
    doc = copy.deepcopy(BASE)
    d = doc["dungeons"][0]
    d["theme"] = theme
    d["rooms"] = copy.deepcopy(fixture["rooms"])
    d["variants"] = copy.deepcopy(fixture["variants"])
    d.pop("spine", None)
    d.pop("clock_s_by_band", None)
    doc["dungeons"] = [d]
    doc["engine"]["sigils"]["free_first_entry"]["dungeons"] = [d["id"]]
    doc["engine"]["slots"]["per_dungeon"] = 4
    if edit:
        edit(d)
    return doc


def fixture_ids(fixture=FIXTURE):
    """The relic ids and lore as the FILE says (an independent reading, not the generator's catalog)."""
    out = {}
    for r in fixture["rooms"]:
        secs = r.get("secrets") or []
        for s in secs:
            rid = s.get("relic") or (r.get("params") or {}).get("relic")
            lore = s.get("lore") or (r.get("params") or {}).get("lore")
            if rid:
                out[rid] = {"lore": lore, "room": r["id"], "secret": s["id"], "type": s["type"]}
    return out


IDS = fixture_ids()


@pytest.fixture(autouse=True)
def fresh_cache():
    R._BUILT.clear()
    yield
    R._BUILT.clear()


_FILES = {}


def files_of(theme):
    if theme not in _FILES:
        R._BUILT.clear()
        _FILES[theme] = D.build(doc_of(theme))
    return _FILES[theme]


def fn(files, name):
    return files[FN + name + ".mcfunction"].splitlines()


def relic_fn_names(files):
    return sorted(k for k in files if "/relic_" in k and k.startswith(FN + "room/"))


def slot_of(doc, k):
    return next(s for s in D.slots(doc) if s["k"] == k)


def built_room(doc, rid, k=1):
    d = doc["dungeons"][0]
    return next(b for b in R.slot_build(doc, d, slot_of(doc, k)) if b.room["id"] == rid)


# ================================================================================================= a model of a player


class Player:
    def __init__(self, name="p"):
        self.name, self.granted, self.done, self.score, self.items, self.said = name, set(), set(), 0, [], []

    def run(self, files, lines):
        """Replay generated lines as this player. Understands exactly what the relic function uses; anything else is
        recorded in `said` so a test can see it ran (a title, a sound) without pretending to model it."""
        adv_def = {}
        for k, v in files.items():
            m = re.match(r"data/cobblers/advancement/(.+)\.json$", k)
            if m:
                adv_def["cobblers:" + m.group(1)] = json.loads(v)
        for ln in lines:
            if not ln.strip() or ln.startswith("#"):
                continue
            m = re.fullmatch(r"execute if entity @s\[advancements=\{(\S+?)=\{(\w+)=true\}\}\] run (.*)", ln)
            if m:
                if (m.group(1), m.group(2)) not in self.granted:
                    continue
                ln = m.group(3)
            else:
                m = re.fullmatch(r"execute if entity @s\[advancements=\{(\S+?)=true\}\] run (.*)", ln)
                if m:
                    if m.group(1) not in self.done:
                        continue
                    ln = m.group(2)
            if ln == "return 0":
                return
            m = re.fullmatch(r"advancement grant @s only (\S+) (\w+)", ln)
            if m:
                self.granted.add((m.group(1), m.group(2)))
                crit = set(adv_def[m.group(1)]["criteria"])
                if crit <= {c for a, c in self.granted if a == m.group(1)}:
                    self.done.add(m.group(1))
                continue
            m = re.fullmatch(r"scoreboard players add @s (\S+) (\d+)", ln)
            if m:
                self.score += int(m.group(2))
                continue
            if ln.startswith("give @s "):
                self.items.append(ln[len("give @s "):])
                continue
            self.said.append(ln)


class World:
    """The shell's state the relic cares about: the holders and the blocks at the pedestals' tops."""

    def __init__(self):
        self.holders, self.blocks = {}, {}

    def run(self, lines):
        for ln in lines:
            m = re.fullmatch(r"scoreboard players set (#\S+) dg\.rs (\d+)", ln)
            if m:
                self.holders[m.group(1)] = int(m.group(2))
            m = re.fullmatch(r"setblock (-?\d+) (-?\d+) (-?\d+) (\S+)", ln)
            if m:
                self.blocks[tuple(int(m.group(i)) for i in (1, 2, 3))] = m.group(4)


def follow(files, name, seen=None):
    """Every line of a function and of every function it calls, in order (the slot's reset chain)."""
    seen = set() if seen is None else seen
    if name in seen or FN + name + ".mcfunction" not in files:
        return []
    seen.add(name)
    out = []
    for ln in fn(files, name):
        out.append(ln)
        m = re.search(r"function cobblers:dungeons/(\S+)$", ln)
        if m and not ln.startswith("#"):
            out += follow(files, m.group(1), seen)
    return out


def room_of_fn(path):
    m = re.search(r"room/([^/]+)/([^/]+)/s(\d+)/(relic_\w+)\.mcfunction$", path)
    return m.groups()


def once_per_player_holds(files):
    """True when running every relic function of slot 1 twice as one player grants, gives and counts exactly once each."""
    p = Player()
    names = [k for k in relic_fn_names(files) if "/s1/" in k]
    if not names:
        return False
    for _ in range(2):
        for k in names:
            p.run(files, files[k].splitlines())
    return len(p.granted) == len(names) and len(p.items) == len(names) and p.score == len(names)


# ================================================================================================= data


def jar():
    import town_character as TC
    j = TC.default_vanilla_jar()
    return j if j is not None and Path(j).is_file() else None


def test_data_is_legal_and_every_id_exists_in_the_jar():
    cfg = X.data()
    assert cfg["schema"] == X.SCHEMA and cfg["lore_max"] == 160
    assert set(cfg["themes"]) == set(R.load_themes()["themes"])
    z = zipfile.ZipFile(jar()) if jar() else None
    lang = json.loads(z.read("assets/minecraft/lang/en_us.json")) if z else None
    names = set(z.namelist()) if z else set()
    ids = TR.vanilla_ids()
    for theme, t in cfg["themes"].items():
        for key in ("pedestal", "armed", "taken"):
            b = t[key]
            assert not G.forbidden(b) and G.classify(b) != G.HAZARD, b
            assert G.base(b) not in BASE["engine"]["rift_pick"]["can_break"], b
            if ids is not None:
                assert G.base(b) in ids, (theme, b)
        assert G.classify(t["pedestal"]) == G.SOLID
        assert len(t["items"]) >= 2
        for item in t["items"]:
            assert re.fullmatch(r"minecraft:[a-z_0-9]+", item)
            if lang is not None:
                assert "item.minecraft.%s" % item.split(":")[1] in lang or "block.minecraft.%s" % item.split(":")[1] in lang, item
    if z is not None:
        assert "assets/minecraft/particles/%s.json" % cfg["particle"].split(":")[1] in names
        assert "assets/minecraft/" + cfg["collection"]["background"].split(":")[1] in names
        for key in ("sound_found", "sound_done"):
            assert re.fullmatch(r"minecraft:[a-z_.]+", cfg[key])
    assert cfg["trigger_radius"] >= X.MIN_TRIGGER


def test_a_relic_item_is_priced_nowhere():
    """No CobbleDollars and nothing sellable: no bank price, counter, buyer, trade or reward may name a relic's base item."""
    texts = {}
    for f in ["modpack/config/cobbledollars/bank.json", "data/markets.json", "data/traders.json", "data/produce_buyer.json",
              "data/rewards.json", "data/direct_trades.json", "data/bank.json"]:
        p = ROOT / f
        if p.exists():
            texts[f] = p.read_text(encoding="utf-8")
    assert "modpack/config/cobbledollars/bank.json" in texts
    bank = {e["item"] for e in json.loads(texts["modpack/config/cobbledollars/bank.json"])["bank"]}
    for theme, t in X.data()["themes"].items():
        for item in t["items"]:
            assert item not in bank, (theme, item)
            for f, text in texts.items():
                if f == "data/bank.json":
                    continue          # the design record names items it forbids; the config above is the price list
                assert '"%s"' % item not in text, (f, theme, item)


# ================================================================================================= the fixture builds


@pytest.mark.parametrize("theme", THEMES)
def test_the_fixture_builds_clean_in_every_theme_and_variant(theme):
    assert R.problems(doc_of(theme)) == []


@pytest.mark.parametrize("theme", THEMES)
def test_the_kit2_demo_with_relics_added_builds_clean(theme):
    def edit(d):
        for r in d["rooms"]:
            if r["id"] == "hall":
                r["params"] = {"relic": "hall_find", "lore": "A hall where something was kept."}
            if r["id"] == "court":
                r["params"] = {"relic": "court_find", "lore": "A court, seen better from above."}
    doc = doc_of(theme, KIT2, edit)
    assert R.problems(doc) == []
    d = doc["dungeons"][0]
    assert [r["id"] for r in X.catalog(doc, d)[0]] == ["hall_find", "court_find"]


@pytest.mark.parametrize("theme", THEMES)
def test_every_relic_is_built_in_every_slot_with_a_pedestal_beside_its_spot(theme):
    doc = doc_of(theme)
    d = doc["dungeons"][0]
    cfg = X.data()["themes"][theme]
    for k in (1, 2, 3, 4):
        seen = {}
        for b in R.slot_build(doc, d, slot_of(doc, k)):
            for m in b.meta.get("relics") or []:
                seen[m["id"]] = m
                px, py, pz = m["pedestal"]
                sx, sy, sz = m["spot"]
                assert abs(px - sx) + abs(pz - sz) == 1 and py == sy, (k, m)
                assert b.grid.block_at(px, py, pz) == cfg["pedestal"]
                assert b.grid.block_at(px, py + 1, pz) == cfg["armed"]
                assert [sx, sy, sz] in [list(a[:3]) for a in b.anchors["secret"]]
                assert m["type"] == IDS[m["id"]]["type"] and b.room["id"] == IDS[m["id"]]["room"]
        assert set(seen) == set(IDS), (k, sorted(seen))


def test_variants_play_a_relic_in_different_places():
    """Four slots, four variants: the mirrored one puts the pedestals on the other wall."""
    doc = doc_of("mine")
    d = doc["dungeons"][0]
    zs = {k: {m["id"]: m["pedestal"][2] - b.room["za"] for b in R.slot_build(doc, d, slot_of(doc, k)) for m in b.meta.get("relics") or []}
          for k in (1, 2)}
    assert zs[1] != zs[2]


# ================================================================================================= once per player


@pytest.mark.parametrize("theme", THEMES)
def test_a_relic_is_given_once_per_player_however_often_they_return(theme):
    files = files_of(theme)
    assert len([k for k in relic_fn_names(files) if "/s1/" in k]) == len(IDS)
    assert once_per_player_holds(files)
    # one function, run again and again, still one of each
    k = next(k for k in relic_fn_names(files) if "/s1/" in k and "first_find" in k)
    p = Player()
    for _ in range(5):
        p.run(files, files[k].splitlines())
    assert len(p.granted) == 1 and len(p.items) == 1 and p.score == 1
    item = p.items[0]
    assert "cobblers_relic" in item and "first_find" in item and "minecraft:lore=" in item and "item_name" in item
    # the lore reaches the player three ways: the item, the chat line and the title
    text = "\n".join(files[k].splitlines())
    assert IDS["first_find"]["lore"] in text and "title @s title" in text


def test_a_relic_survives_the_slot_reset_a_death_and_the_next_run():
    """Run 1 takes it; the slot resets; run 2 walks up to the same pedestal: it is armed again for the room and gives nothing."""
    files = files_of("mine")
    k = next(k for k in relic_fn_names(files) if "/s1/" in k and "second_find" in k)
    holder = "#s1r1l1"
    p, w = Player(), World()
    w.run(["scoreboard players set %s dg.rs 0" % holder])
    p.run(files, files[k].splitlines())
    w.run(files[k].splitlines())
    assert w.holders[holder] == 1 and p.score == 1
    top = next(c for c, v in w.blocks.items() if v == "minecraft:air")      # the one block the touch function set
    assert len([1 for v in w.blocks.values()]) == 1                         # (only the touch function ran on this world)
    w.blocks[top] = "minecraft:air"          # the lantern is out
    before = (set(p.granted), set(p.done), p.score, list(p.items))
    w.run(follow(files, "slot/s1/reset"))      # the slot's reset
    assert w.holders[holder] == 0                                        # re-armed
    assert w.blocks[top] == X.data()["themes"]["mine"]["armed"]          # the display is back
    assert (set(p.granted), set(p.done), p.score, list(p.items)) == before   # and the record is untouched
    p.run(files, files[k].splitlines())                                  # run 2
    assert p.score == 1 and len(p.items) == 1


def test_a_second_player_in_the_same_run_still_gets_theirs():
    files = files_of("mine")
    k = next(k for k in relic_fn_names(files) if "/s1/" in k and "first_find" in k)
    a, b = Player("a"), Player("b")
    a.run(files, files[k].splitlines())
    b.run(files, files[k].splitlines())
    assert a.score == b.score == 1 and len(a.items) == len(b.items) == 1


# ================================================================================================= the collection


@pytest.mark.parametrize("theme", THEMES)
def test_the_collection_advancement_has_one_required_criterion_per_relic(theme):
    files = files_of(theme)
    path = "data/cobblers/advancement/dungeons/relics/ns.json"
    adv = json.loads(files[path])
    assert set(adv["criteria"]) == set(IDS)
    assert all(c["trigger"] == "minecraft:impossible" for c in adv["criteria"].values())
    assert sorted(sum(adv["requirements"], [])) == sorted(IDS) and all(len(r) == 1 for r in adv["requirements"])
    assert adv["display"]["show_toast"] and adv["display"]["announce_to_chat"] and adv["display"]["frame"] == "goal"
    assert adv["display"]["icon"]["id"] in X.data()["themes"][theme]["items"]
    # nothing else in the pack grants or checks a different advancement
    for k, v in files.items():
        for m in re.finditer(r"advancements=\{([^=]+?)=", v):
            if "relics" in m.group(1):
                assert m.group(1) == "cobblers:dungeons/relics/ns", (k, m.group(1))


def test_the_collection_completes_on_the_last_relic_and_not_before():
    files = files_of("jungle")
    names = [k for k in relic_fn_names(files) if "/s1/" in k]
    p = Player()
    adv = "cobblers:dungeons/relics/ns"
    for n, k in enumerate(sorted(names), start=1):
        p.run(files, files[k].splitlines())
        assert (adv in p.done) == (n == len(IDS)), n
    assert adv in p.done and p.score == len(IDS)
    last = "\n".join(p.said)
    assert "Every relic of The Night Shift is yours" in last        # said on the one that completed it, and only then
    q = Player()
    for k in sorted(names)[:-1]:
        q.run(files, files[k].splitlines())
    assert "Every relic" not in "\n".join(q.said)


def test_each_dungeon_keeps_its_own_collection_and_count():
    """The advancement and the objective are keyed by the dungeon's short id, which is unique."""
    d = doc_of("mine")["dungeons"][0]
    assert X.adv_id(d) == "cobblers:dungeons/relics/ns" and X.obj_of(d) == "dg.rl_ns"
    shorts = [x["short"] for x in BASE["dungeons"]]
    assert len(set(shorts)) == len(shorts) == 3
    assert len({X.adv_id(x) for x in BASE["dungeons"]}) == len({X.obj_of(x) for x in BASE["dungeons"]}) == 3


def test_the_run_board_the_arrival_and_the_lobby_carry_the_count():
    doc = doc_of("mine")
    files = files_of("mine")
    d = doc["dungeons"][0]
    s = slot_of(doc, 1)
    board = D.board_text(doc, d, s)
    assert "Relics hidden here: %d." % len(IDS) in board
    assert "function cobblers:dungeons/relic/ns/show" in fn(files, "slot/s1/arrive")
    lobby = "\n".join(fn(files, "m/lobby"))
    for g in (1, 2, 3, 4):
        assert re.search(r"dg\.slot matches %d positioned [\d.]+ [\d.]+ [\d.]+ if entity @s\[distance=\.\.5\] run function cobblers:dungeons/relic/ns/bar" % g, lobby)
    show = "\n".join(fn(files, "relic/ns/show"))
    assert "/%d" % len(IDS) in show and "dg.rl_ns" in show
    assert "scoreboard objectives add dg.rl_ns dummy" in "\n".join(fn(files, "relic/load"))
    assert "cobblers:dungeons/relic/load" in json.loads(files["data/minecraft/tags/function/load.json"])["values"]
    # a dungeon with no relics has none of it
    plain = copy.deepcopy(doc)
    for r in plain["dungeons"][0]["rooms"]:
        r.pop("secrets", None)
        r.pop("params", None)
    pf = D.build(plain)
    assert not [k for k in pf if "relic" in k]
    assert "Relics hidden" not in D.board_text(plain, plain["dungeons"][0], slot_of(plain, 1))


def test_the_functions_obey_the_command_limits_and_each_is_called():
    files = files_of("flooded_ruin")
    for k in relic_fn_names(files) + [FN + n + ".mcfunction" for n in ("relic/load", "relic/ns/show", "relic/ns/bar")]:
        assert FL.check_lines(files[k].splitlines(), k) == [], k
    for k in relic_fn_names(files) + [FN + n + ".mcfunction" for n in ("relic/ns/show", "relic/ns/bar")]:
        ref = "cobblers:dungeons/" + k[len(FN):-len(".mcfunction")]
        assert any(ref in v for kk, v in files.items() if kk != k and isinstance(v, str)), "orphan: " + k


# ================================================================================================= the reset never touches the record


def record_touches(files):
    """Lines that revoke an advancement or change a relic count other than the relic function's own +1 and the show/bar
    guard that sets an unset count to 0."""
    bad = []
    for k, v in files.items():
        if not k.endswith(".mcfunction"):
            continue
        for ln in v.splitlines():
            if ln.startswith("#"):
                continue
            if "advancement revoke" in ln and ("relics" in ln or re.search(r" (everything|from|through|until)\b", ln)):
                bad.append((k, ln))
            if "scoreboard players" in ln and "dg.rl_" in ln:
                own = "/relic_" in k and ln == "scoreboard players add @s dg.rl_ns 1"
                guard = ln.startswith("execute unless score @s dg.rl_") and "matches -2147483648.." in ln
                if not (own or guard):
                    bad.append((k, ln))
            if "advancement grant" in ln and "relics" in ln and "/relic_" not in k:
                bad.append((k, ln))
    return bad


def test_nothing_in_the_pack_revokes_or_resets_a_players_record():
    assert record_touches(files_of("mine")) == []


def test_every_room_reset_re_arms_its_pedestal():
    files = files_of("mine")
    doc = doc_of("mine")
    for b in R.slot_build(doc, doc["dungeons"][0], slot_of(doc, 1)):
        for m in b.meta.get("relics") or []:
            reset = fn(files, "room/night_shift/%s/s1/reset" % b.room["id"])
            px, py, pz = m["pedestal"]
            assert "scoreboard players set %s dg.rs 0" % m["holder"] in reset
            assert "setblock %d %d %d %s" % (px, py + 1, pz, X.data()["themes"]["mine"]["armed"]) in reset
            assert "dg.rl_" not in "\n".join(reset)


# ================================================================================================= the record's refusals


def problems_with(edit):
    doc = doc_of("mine", edit=edit)
    return R.problems(doc)


def room(d, rid):
    return next(r for r in d["rooms"] if r["id"] == rid)


def test_a_relic_on_a_room_with_no_secret_is_refused():
    def edit(d):
        room(d, "arena")["params"] = {"relic": "orphan_find", "lore": "Nothing hides here."}
    assert any("no secret" in p for p in problems_with(edit))


def test_a_relic_id_used_in_two_rooms_is_refused():
    def edit(d):
        room(d, "b")["params"]["relic"] = "first_find"
    assert any("also in room" in p or "different lore" in p for p in problems_with(edit))


def test_the_same_id_with_other_words_is_refused():
    def edit(d):
        d["variants"][3]["swap"] = {"a": {"secrets": [dict(room(d, "a")["secrets"][0], lore="Different words.")] + room(d, "a")["secrets"][1:]}}
    assert any("different lore" in p for p in problems_with(edit))


@pytest.mark.parametrize("lore, word", [("x" * 161, "over the limit"), ("Café below the line.", "ASCII"), ("", "lore")])
def test_lore_over_160_or_not_printable_ascii_or_empty_is_refused(lore, word):
    def edit(d):
        room(d, "b")["params"]["lore"] = lore
    assert any(word in p for p in problems_with(edit))


def test_the_lore_limit_is_exact():
    def edit(d):
        room(d, "b")["params"]["lore"] = "y" * 160
    assert problems_with(edit) == []


@pytest.mark.parametrize("rid", ["Upper", "1abc", "has space", "x", "a" * 40])
def test_a_malformed_relic_id_is_refused(rid):
    def edit(d):
        room(d, "b")["params"]["relic"] = rid
    assert any("is not an id" in p for p in problems_with(edit))


def test_a_secret_without_a_relic_is_refused_once_the_dungeon_has_any():
    def edit(d):
        s = room(d, "a")["secrets"][1]
        s.pop("relic")
        s.pop("lore")
    assert any("no relic or lore" in p for p in problems_with(edit))


def test_a_dungeon_with_secrets_and_no_relics_builds_and_warns():
    def edit(d):
        for r in d["rooms"]:
            for s in r.get("secrets") or []:
                s.pop("relic", None)
                s.pop("lore", None)
                s.pop("relic_name", None)
            r.pop("params", None)
    doc = doc_of("mine", edit=edit)
    assert R.problems(doc) == []
    assert any("carry no params.relic" in w for w in X.warnings(doc))
    assert not [k for k in D.build(doc) if "relic" in k]


def test_a_name_over_the_limit_is_refused():
    def edit(d):
        room(d, "b")["params"]["relic_name"] = "N" * 33
    assert any("name is 33" in p for p in problems_with(edit))


# ================================================================================================= the real dungeons


def test_every_secret_in_the_real_dungeons_has_a_relic_and_the_record_is_clean():
    """Vacuous until the authored dungeons gain secrets; then it bites: each secret carries relic + lore, ids unique."""
    for d in BASE["dungeons"]:
        if not R.has_rooms(d):
            continue
        relics, bad, missing = X.catalog(BASE, d)
        assert bad == [] and missing == [], d["id"]
        assert len({r["id"] for r in relics}) == len(relics)
    assert D.problems(BASE) == []


# ================================================================================================= mutations of the generator


def test_mutation_dropping_the_guard_is_caught_by_the_once_per_player_check(monkeypatch):
    real = X.touch_lines

    def no_guard(*a, **kw):
        return [ln for ln in real(*a, **kw) if not ln.endswith("run return 0")]
    monkeypatch.setattr(X, "touch_lines", no_guard)
    R._BUILT.clear()
    files = D.build(doc_of("mine"))
    assert not once_per_player_holds(files)


def test_mutation_a_wide_trigger_is_caught_by_the_secret_check(monkeypatch):
    monkeypatch.setitem(X.data(), "trigger_radius", 6.0)
    R._BUILT.clear()
    bad = R.problems(doc_of("mine"))
    assert any("without the secret's trick" in p for p in bad), bad[:3]


def test_mutation_a_pedestal_on_the_spot_is_caught(monkeypatch):
    monkeypatch.setattr(X, "neighbours", lambda secret: [(0, 0)])
    R._BUILT.clear()
    bad = R.problems(doc_of("mine"))
    assert bad, "a pedestal standing on the relic spot went unnoticed"


def test_mutation_a_collection_short_of_a_criterion_is_caught(monkeypatch):
    real = X.catalog
    monkeypatch.setattr(X, "catalog", lambda doc, d: (real(doc, d)[0][:-1],) + tuple(real(doc, d)[1:]))
    R._BUILT.clear()
    files = D.build(doc_of("mine"))
    adv = json.loads(files["data/cobblers/advancement/dungeons/relics/ns.json"])
    assert set(adv["criteria"]) != set(IDS)


def test_mutation_a_reset_that_revokes_is_caught_by_the_record_check(monkeypatch):
    real = X.dress_relics

    def revoking(ctx, spec):
        real(ctx, spec)
        if ctx.built.meta.get("relics"):
            ctx.built.functions["reset"] = ctx.built.functions.get("reset", []) + ["advancement revoke @a only cobblers:dungeons/relics/ns"]
    monkeypatch.setattr(X, "dress_relics", revoking)
    monkeypatch.setitem(R.DRESS, "relics", (revoking, "light"))
    R._BUILT.clear()
    files = D.build(doc_of("mine"))
    assert record_touches(files)


def test_mutation_the_count_reset_by_a_slot_reset_is_caught(monkeypatch):
    real = X.dress_relics

    def resetting(ctx, spec):
        real(ctx, spec)
        if ctx.built.meta.get("relics"):
            ctx.built.functions["reset"] = ctx.built.functions.get("reset", []) + ["scoreboard players set @a dg.rl_ns 0"]
    monkeypatch.setitem(R.DRESS, "relics", (resetting, "light"))
    R._BUILT.clear()
    files = D.build(doc_of("mine"))
    assert record_touches(files)

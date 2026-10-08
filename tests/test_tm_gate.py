"""tools/tm_gate.py: crafted TMs unlock per player at their badge, and no other recipe is stranded.

The badge is the power rule (the owner, 2026-10-08): a shelf TM at its shelf line's badge, every other TM at the badge
an outlier group of data/tm_gate.json places it at, else at the band of its score in the committed table
docs/mechanics/TM_POWER_GATE.json. Every expectation is stated by tests/tm_gate_fixture.py (a synthetic server written
by hand), by the constants below (copied by hand from docs/mechanics/TM_POWER_GATE.md: the outlier table of section 6,
the shelf table of section 5, the distribution of section 3, and scores worked from section 2), or read here from
data/markets.json; the recipe book is modelled from the pack's own function text. The mutation tests rewrite the
GENERATOR's source in memory (CLAUDE.md "How to prove an audit is independent") and leave data/ untouched.

Removed with the type-and-grade rule (2026-10-08), because the rule they pinned is gone: the unlisted-rule test worked
by type and disc grade, "a type no leader teaches is never early", and the two mutants that ignored the grade and put
a leaderless type at the minimum. Their replacements are the power-band, outlier and distribution tests below.

Not covered (EXP-067): that Minecraft 1.21.1 enforces doLimitedCrafting as the jar reading says, that `recipe give @s *`
and the tick advancement behave as modelled, the toasts a sync shows, and Cobblemon's own TM Machine (out of scope,
data/tm_gate.json does_not_cover). Whether the scores value the moves well is the owner's judgement, not a test.
"""
from __future__ import annotations

import collections
import copy
import json
import os
import re
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import tm_gate as G  # noqa: E402
import tm_gate_fixture as F  # noqa: E402

MARKETS = json.loads((ROOT / "data" / "markets.json").read_text(encoding="utf-8"))
PROGRESSION = json.loads((ROOT / "data" / "progression.json").read_text(encoding="utf-8"))
SNAPSHOT = Path(os.environ.get("COBBLERS_SERVER_SNAPSHOT",
                               "C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05"))

T = "tmcraft:tm_"
# docs/mechanics/TM_POWER_GATE.md 6, by hand: group -> {TM: (the rule's badge, the suggested badge)}
OUTLIERS = {
    1: {T + "thunderwave": (6, 5)},
    2: {T + "willowisp": (4, 5)},
    3: {T + "nuzzle": (2, 5), T + "inferno": (3, 5), T + "zapcannon": (4, 5)},  # the owner, 2026-10-08
    4: {T + "trickroom": (5, 6)},
    5: {T + "uturn": (6, 5), T + "voltswitch": (6, 5), T + "flipturn": (5, 5), T + "partingshot": (3, 5)},
    6: {T + "knockoff": (4, 6)},
    7: {T + "swordsdance": (4, 6), T + "nastyplot": (4, 6), T + "dragondance": (4, 6), T + "bulkup": (3, 6),
        T + "quiverdance": (6, 7), T + "shiftgear": (7, 7), T + "bellydrum": (6, 7), T + "shellsmash": (8, 8)},
    8: {T + "magnitude": (4, 5)},
    9: {T + m: (4, 7) for m in ("hyperbeam", "gigaimpact", "blastburn", "frenzyplant", "hydrocannon", "rockwrecker",
                                "eternabeam", "meteorassault", "roaroftime")} | {T + "prismaticlaser": (5, 7)},
    # the owner, 2026-10-08: "Meteor Assault, Prismatic Laser and Roar of Time: Hyper Beam class, badge 7"
    10: {T + "explosion": (5, 7), T + "selfdestruct": (4, 6)},
    11: {T + "solarbeam": (3, 5), T + "solarblade": (3, 5)},
    12: {T + "sheercold": (3, 8), T + "horndrill": (3, 8)},
    13: {T + "dragonrage": (2, 4), T + "sonicboom": (1, 2), T + "seismictoss": (4, 4), T + "nightshade": (4, 4)},
    14: {T + "hex": (4, 5), T + "venoshock": (4, 5), T + "facade": (4, 5), T + "acrobatics": (3, 5),
         T + "weatherball": (2, 4)},
    15: {T + "sludgebomb": (7, 6), T + "ironhead": (6, 5)},
    16: {T + "return": (7, 7), T + "frustration": (7, 7)},  # measured 2026-10-08: full power is cheap, so 102's band
    17: {T + "glare": (7, 6)},
}
# the shelf lines the groups also name, which the shelf already places at the group's badge (groups 7, 8, 12, 15)
SHELF_AGREES = {T + "calmmind": 6, T + "earthquake": 8, T + "fissure": 8, T + "poisonjab": 5}
# docs/mechanics/TM_POWER_GATE.md 5, by hand: shelf TM -> (shelf badge, power badge); Shock Wave and Overheat agree
SHELF_VS_POWER = {
    T + "bide": (1, 2), T + "headbutt": (1, 5), T + "rockslide": (1, 4), T + "rocktomb": (1, 4),
    T + "bubblebeam": (2, 4), T + "scald": (2, 6), T + "waterpulse": (2, 3), T + "thunder": (3, 5),
    T + "thunderbolt": (3, 6), T + "gigadrain": (4, 6), T + "megadrain": (4, 2), T + "poisonfang": (5, 3),
    T + "poisongas": (5, 2), T + "poisonjab": (5, 6), T + "toxic": (5, 6), T + "calmmind": (6, 3),
    T + "psywave": (6, 3), T + "skillswap": (6, 1), T + "fireblast": (7, 6), T + "earthquake": (8, 7),
    T + "fissure": (8, 3),
}
# no shelf line, no outlier: score worked by hand from TM_POWER_GATE.md 2, badge from the bands of 3
BY_HAND = {
    T + "flamethrower": (93.0, 6),   # 90 + 10% burn x 30
    T + "psychic": (90.8, 6),        # 90 + 10% x one sp.def stage x 8
    T + "earthpower": (90.8, 6),     # the same
    T + "dragonclaw": (80.0, 5),     # 80, no effect
    T + "xscissor": (80.0, 5),
    T + "growl": (15.0, 1),          # one attack stage lowered x 15
    T + "boomburst": (140.0, 8),     # 140
    T + "leechseed": (54.0, 2),      # 90% x 60: a top (54) is inclusive
    T + "spark": (74.0, 4),          # 65 + 30% paralysis x 30 = 74: inclusive
    T + "searingshot": (104.0, 7),   # 100 x 0.95 (5 PP) + 30% burn x 30 = 104: inclusive
    T + "dragonpulse": (85.0, 6),    # 85, no effect: one over the badge-5 top (84)
}
# docs/mechanics/TM_POWER_GATE.md 3: TMs by badge, the rule alone and with the shelf
PROPOSAL_POWER_RULE = {1: 163, 2: 122, 3: 110, 4: 104, 5: 107, 6: 99, 7: 66, 8: 31}
PROPOSAL_WITH_SHELF = {1: 166, 2: 122, 3: 107, 4: 103, 5: 109, 6: 96, 7: 66, 8: 33}
APPLIED = {1: 165, 2: 120, 3: 99, 4: 85, 5: 122, 6: 99, 7: 77, 8: 35}
# the owner, 2026-10-08: "A craft that unlocks before its input is a dead recipe". The four chain TMs of the
# 2026-10-05 snapshot that opened before their input (read from tmcraft-1.4.19's recipes, listed here by hand):
# chain TM -> (its input TM, the badge before the raise, the input's badge)
CHAIN_RAISES = {T + "boneclub": (T + "bonemerang", 3, 6), T + "nobleroar": (T + "roar", 1, 2),
                T + "stunspore": (T + "spore", 5, 8), T + "triplekick": (T + "doublekick", 2, 3)}
# the snapshot's plan: APPLIED with the four raises (1: -1 Noble Roar; 2: +1 Noble Roar -1 Triple Kick; 3: -1 Bone
# Club +1 Triple Kick; 5: -1 Stun Spore; 6: +1 Bone Club; 8: +1 Stun Spore)
SNAPSHOT_APPLIED = {1: 164, 2: 120, 3: 99, 4: 85, 5: 121, 6: 100, 7: 77, 8: 36}
TM_ID = re.compile(r'"(tmcraft:tm_[a-z0-9_]+)"')


def chain_inputs(resolved):
    """{(recipe id, chain TM): {input TMs}} read here from the loaded recipes' own JSON (the ingredients or the key),
    not through the generator's traits()."""
    out = {}
    for rid, (_, r) in resolved["recipes"].items():
        res = G.result_id(r)
        if not (isinstance(res, str) and res.startswith(T)) or r.get("type") not in (
                "minecraft:crafting_shaped", "minecraft:crafting_shapeless"):
            continue
        ins = set(TM_ID.findall(json.dumps([r.get("ingredients"), r.get("key")])))
        if ins:
            out[(rid, res)] = ins
    return out


def chain_failures(plan, chains):
    """Every recipe whose chain TM opens before one of its input TMs."""
    tms = plan["tms"]
    return sorted("%s: %s %d < %s %d" % (rid, item, tms[item]["badge"], i, tms[i]["badge"])
                  for (rid, item), ins in chains.items() for i in sorted(ins)
                  if item in tms and i in tms and tms[i]["badge"] > tms[item]["badge"])


def _mutant(*subs):
    """tools/tm_gate.py with its own source rewritten in memory, as a fresh module."""
    src = Path(G.__file__).read_text(encoding="utf-8")
    for old, new in subs:
        assert old in src, "mutation target %r is no longer in the generator; re-aim it" % old
        src = src.replace(old, new, 1)
    mod = types.ModuleType("tm_gate_mutant")
    mod.__file__ = G.__file__
    exec(compile(src, "<mutant tm_gate>", "exec"), mod.__dict__)  # noqa: S102 - deliberate, in-memory, test-only
    return mod


def _make(mod, tmp, doc=None, scores=None, **kw):
    server, vanilla, exp = F.build_server(tmp, **kw)
    doc = doc or mod.load()
    resolved = mod.resolve(mod.read_server(server, vanilla))
    plan = mod.plan(doc, resolved, copy.deepcopy(MARKETS), copy.deepcopy(PROGRESSION),
                    scores=scores if scores is not None else F.score_table())
    return plan, exp, (mod.build(doc, plan) if not plan["problems"] else None)


def _place(mod, doc=None, table=None):
    """The power rule over all 802 scored TMs, no server needed."""
    return mod.place(doc or mod.load(), table if table is not None else F.score_table(),
                     mod.shelf_badges(copy.deepcopy(MARKETS)))


def _badge_of(plan, rid):
    return plan["gated"][rid]["badge"]


def outlier_failures(tms):
    """Each outlier TM's rule badge is the proposal's 'Score -> rule badge' and its placed badge its 'Suggested'."""
    out = []
    for n, items in sorted(OUTLIERS.items()):
        for item, (before, after) in sorted(items.items()):
            t = tms.get(item)
            if t is None:
                out.append("group %d %s: not placed at all" % (n, item))
            elif (t["power_badge"], t["badge"]) != (before, after):
                out.append("group %d %s: rule %s -> placed %s, the proposal says %d -> %d"
                           % (n, item, t["power_badge"], t["badge"], before, after))
    return out


# ---------------------------------------------------------------- the checks, each a list of failures

def stranding_failures(files, exp, plan):
    """A fresh player, a player from before the change and a player who picks a starter after syncing: each holds
    every non-gated recipe, and no gated recipe of a badge they lack."""
    out = []
    every = exp["book_all"]
    gated = set(exp["tms"]) | set(exp["devices"])
    must = every - gated
    for name, player in (("fresh", F.Player()),
                         ("before the change", F.Player(book={"minecraft:oak_planks", "tmcraft:tm_earthquake",
                                                              "tmcraft:tm_tackle"}, flags=["gym1_cleared"]))):
        F.tick(files, player, every)
        missing = sorted(must - player.book)
        if missing:
            out.append("%s player lacks %s" % (name, missing[:6]))
        held = 1 if name != "fresh" else 0
        early = sorted(r for r in gated & player.book if _badge_of(plan, r) > held)
        if early:
            out.append("%s player holds gated %s" % (name, early[:6]))
    for order in ("starter first", "ours first"):
        p = F.Player(flags=["gym1_cleared"])
        F.tick(files, p, every)
        F.pick_starter(files, p, every, ours_first=(order == "ours first"))
        F.tick(files, p, every)
        early = sorted(r for r in gated & p.book if _badge_of(plan, r) > 1)
        if early:
            out.append("after picking a starter (%s) a 1-badge player holds %s" % (order, early[:6]))
        if must - p.book:
            out.append("after picking a starter the player lacks %s" % sorted(must - p.book)[:6])
    return out


def shelf_failures(plan):
    """Each shelf TM's badge is its markets.json line's gate_badge."""
    shelf = F.shelf_from_markets()
    out = []
    for item, badge in sorted(shelf.items()):
        got = plan["tms"].get(item, {}).get("badge")
        if got != badge:
            out.append("%s: shelf %s, gate %s" % (item, badge, got))
    return out


def earn_failures(files, exp, plan):
    """A player who earns badge B mid-session gets exactly the TMs of badges <= B."""
    out = []
    every = exp["book_all"]
    p = F.Player()
    F.tick(files, p, every)
    for b in range(1, 9):
        p.adv.add("cobblers:flag/gym%d_cleared" % b)
        F.tick(files, p, every)
        for rid in exp["tms"]:
            want = _badge_of(plan, rid) <= b
            if (rid in p.book) != want:
                out.append("badge %d: %s %s" % (b, rid, "missing" if want else "held early"))
    return out


def device_failures(files, exp, plan):
    out = []
    top = max(t["badge"] for t in plan["tms"].values())
    for rid in exp["devices"]:
        if plan["gated"].get(rid, {}).get("badge") != top:
            out.append("device %s is not gated at %d" % (rid, top))
    if "data/carved_wood/recipe/wooden_crafter.json" not in files:
        out.append("the special crafter recipe is not closed")
    return out


def closed_failures(files, exp):
    out = []
    for aid in exp["tm_advancements"] + exp["device_advancements"]:
        ns, path = aid.split(":", 1)
        body = files.get("data/%s/advancement/%s.json" % (ns, path))
        if body is None or json.loads(body) != {"fabric:load_conditions": [G.NEVER]}:
            out.append("unlock advancement %s is not closed" % aid)
    for rel, body in files.items():
        if rel.startswith("data/minecraft/advancement/recipes/building_blocks") or "copper_blank_disc" in rel:
            out.append("closed an ordinary unlock: %s" % rel)
    return out


# ---------------------------------------------------------------- the generator as written

def test_no_recipe_is_stranded_and_no_tm_comes_early(tmp_path):
    plan, exp, files = _make(G, tmp_path)
    assert plan["problems"] == []
    assert stranding_failures(files, exp, plan) == []


def test_each_shelf_tm_unlocks_at_its_shelf_lines_badge(tmp_path):
    plan, _, _ = _make(G, tmp_path)
    assert len(F.shelf_from_markets()) == 23
    assert shelf_failures(plan) == []
    # the shelf wins where the power rule disagrees: the 21 lines of docs/mechanics/TM_POWER_GATE.md 5, kept
    got = {item for item, t in plan["tms"].items() if t["rule"] == "shelf" and t["badge"] != t["power_badge"]}
    assert got == set(SHELF_VS_POWER)


def test_unlisted_tms_follow_the_power_rule_worked_by_hand(tmp_path):
    plan, exp, _ = _make(G, tmp_path)
    got = {item: plan["tms"][item]["badge"] for item in exp["unlisted_badge"]}
    assert got == exp["unlisted_badge"]
    assert all(plan["tms"][i]["rule"].startswith("power:") for i in exp["unlisted_badge"])


def test_earning_a_badge_gives_exactly_its_tms(tmp_path):
    plan, exp, files = _make(G, tmp_path)
    assert earn_failures(files, exp, plan) == []


def test_devices_and_unlock_advancements(tmp_path):
    plan, exp, files = _make(G, tmp_path)
    assert device_failures(files, exp, plan) == []
    assert closed_failures(files, exp) == []


def test_only_gated_recipes_are_ever_taken(tmp_path):
    plan, exp, files = _make(G, tmp_path)
    allowed = set(exp["tms"]) | set(exp["devices"])
    for rel, text in files.items():
        for line in text.splitlines():
            if line.startswith("recipe take"):
                assert line.split()[-1] in allowed, (rel, line)
    assert not set(exp["conversions"]) & set(plan["gated"])  # a TM's conversion is never gated


def test_the_sync_gives_everything_before_it_takes(tmp_path):
    _, _, files = _make(G, tmp_path)
    lines = [l for l in files["data/cobblers/function/tm_gate/sync.mcfunction"].splitlines() if not l.startswith("#")]
    assert lines[0] == "recipe give @s *"
    assert lines[-1].startswith("scoreboard players set @s cobblers.tmgate ")
    load = files["data/cobblers/function/tm_gate/load.mcfunction"]
    assert "gamerule doLimitedCrafting true" in load


def test_sweep_counts_what_the_gamerule_alone_would_strand(tmp_path):
    server, vanilla, exp = F.build_server(tmp_path)
    s = G.sweep(G.load(), G.read_server(server, vanilla), G.resolve(G.read_server(server, vanilla)))
    no_adv = set(exp["ordinary"]) - exp["with_adv"]
    assert no_adv | {"toms_storage:crafting_terminal"} | set(exp["conversions"]) == set(s["stranded"])


def test_an_undeclared_give_all_fails_closed(tmp_path):
    plan, _, files = _make(G, tmp_path, extra_functions={
        "data/other/function/grant.mcfunction": "recipe give @a *\n"})
    assert files is None
    assert any("other:grant" in p for p in plan["problems"])


def test_an_unlock_that_also_unlocks_ordinary_recipes_fails_closed(tmp_path):
    adv = {"criteria": {"x": {"trigger": "minecraft:tick"}},
           "rewards": {"recipes": ["tmcraft:tm_tackle", "minecraft:oak_planks"]}}
    plan, _, files = _make(G, tmp_path, extra_advancements={"data/other/advancement/mixed.json": adv})
    assert files is None
    assert any("other:mixed" in p for p in plan["problems"])


def test_devices_can_be_given_back(tmp_path):
    doc = G.load()
    doc["devices"]["enforced"] = False
    plan, exp, files = _make(G, tmp_path, doc=doc)
    assert not set(exp["devices"]) & set(plan["gated"])
    assert "data/carved_wood/recipe/wooden_crafter.json" not in files


# ---------------------------------------------------------------- the power rule over the committed score table

def test_each_outlier_group_lands_where_the_proposal_says():
    tms, problems = _place(G)
    assert problems == []
    assert outlier_failures(tms) == []
    # the data names exactly the proposal's groups and TMs: an outlier dropped from data/tm_gate.json fails here too
    groups = {g["group"]: set(g.get("place", {})) for g in G.load()["badge_rule"]["power"]["outliers"]}
    assert groups == {n: set(v) for n, v in OUTLIERS.items()}
    agrees = {i: b for g in G.load()["badge_rule"]["power"]["outliers"] for i, b in g.get("shelf_agrees", {}).items()}
    assert agrees == SHELF_AGREES


def test_every_shelf_tm_is_at_its_shelf_badge_and_the_disagreements_are_documented():
    tms, problems = _place(G)
    assert problems == []
    shelf = F.shelf_from_markets()
    assert {i: tms[i]["badge"] for i in shelf} == shelf
    assert {i: (shelf[i], tms[i]["power_badge"]) for i in shelf if shelf[i] != tms[i]["power_badge"]} == SHELF_VS_POWER
    lines = G.load()["badge_rule"]["shelf_disagreements"]["lines"]
    assert {d["item"]: (d["shelf_badge"], d["power_badge"]) for d in lines} == SHELF_VS_POWER
    assert all(d["kept"] == "shelf" for d in lines)


def test_a_tm_with_no_shelf_line_and_no_outlier_is_at_its_power_band():
    tms, _ = _place(G)
    placed = {i for items in OUTLIERS.values() for i in items}
    for item, (score, badge) in BY_HAND.items():
        assert item not in placed and item not in F.shelf_from_markets(), item
        assert tms[item]["score"] == score, (item, tms[item]["score"])
        assert (tms[item]["badge"], tms[item]["rule"]) == (badge, "power: score %s -> %d" % (score, badge)), item


def test_the_distribution_is_the_proposals_moved_only_by_the_outliers():
    tms, _ = _place(G)
    power = collections.Counter(t["power_badge"] for t in tms.values())
    assert dict(power) == PROPOSAL_POWER_RULE
    want = collections.Counter(PROPOSAL_WITH_SHELF)
    for items in OUTLIERS.values():
        for item, (before, after) in items.items():
            want[before] -= 1
            want[after] += 1
    got = collections.Counter(t["badge"] for t in tms.values())
    assert dict(got) == dict(want)
    assert dict(got) == APPLIED  # the delta, stated: {1: -1, 2: -2, 3: -8, 4: -18, 5: +13, 6: +3, 7: +11, 8: +2}
    assert {b: APPLIED[b] - PROPOSAL_WITH_SHELF[b] for b in APPLIED} == \
        {1: -1, 2: -2, 3: -8, 4: -18, 5: 13, 6: 3, 7: 11, 8: 2}


def test_an_outlier_placed_on_a_shelf_tm_is_refused():
    doc = G.load()
    doc["badge_rule"]["power"]["outliers"][0]["place"]["tmcraft:tm_scald"] = 6
    _, problems = _place(G, doc=doc)
    assert any("tm_scald" in p and "shelf wins" in p for p in problems), problems


def test_a_moved_score_or_shelf_line_fails_closed():
    t = F.score_table()
    t["tms"]["tmcraft:tm_toxic"]["score"] = 75.0          # band 5: the shelf would now agree, the list says otherwise
    t["tms"]["tmcraft:tm_toxic"]["power_badge"] = 5
    t["tms"]["tmcraft:tm_tackle"]["power_badge"] = 3      # a row whose badge is not its score's band: stale
    _, problems = _place(G, table=t)
    assert any("tm_toxic" in p and "shelf_disagreements lists" in p for p in problems), problems
    assert any("tm_tackle" in p and "stale" in p for p in problems), problems


def test_a_server_whose_moves_differ_from_the_table_fails_closed(tmp_path):
    t = F.score_table()
    t["moves_sha256"] = "0" * 64
    server, vanilla, _ = F.build_server(tmp_path)
    plan = G.plan(G.load(), G.resolve(G.read_server(server, vanilla)), copy.deepcopy(MARKETS),
                  copy.deepcopy(PROGRESSION), scores=t)
    assert any("moves.js" in p and "re-run tools/tm_power_score.py" in p for p in plan["problems"]), plan["problems"]


def test_a_tm_the_table_has_not_scored_fails_closed(tmp_path):
    t = F.score_table()
    del t["tms"]["tmcraft:tm_icebeam"]
    plan, _, files = _make(G, tmp_path, scores=t)
    assert files is None
    assert any("tm_icebeam" in p and "no score" in p for p in plan["problems"]), plan["problems"]


# ---------------------------------------------------------------- mutations of the generator: each check bites

def test_mutant_without_the_give_strands_recipes(tmp_path):
    m = _mutant(('"recipe give @s *"]', '"# mutant: no give"]'))
    plan, exp, files = _make(m, tmp_path)
    assert any("lacks" in f for f in stranding_failures(files, exp, plan))


def test_mutant_off_by_one_shelf_badge_is_caught(tmp_path):
    m = _mutant(('badge, why = shelf[item], "shelf"', 'badge, why = shelf[item] + 1, "shelf"'))
    plan, _, _ = _make(m, tmp_path)
    assert shelf_failures(plan)


def test_mutant_where_the_power_rule_beats_the_shelf_is_caught(tmp_path):
    m = _mutant(('badge, why = shelf[item], "shelf"', 'badge, why = pb, "shelf"'))
    plan, _, _ = _make(m, tmp_path)
    fails = shelf_failures(plan)
    assert any("tm_scald" in f for f in fails), fails
    tms, _ = _place(m)
    shelf = F.shelf_from_markets()
    assert {i: tms[i]["badge"] for i in shelf} != shelf


def test_mutant_that_drops_an_outlier_group_is_caught():
    m = _mutant(('for g in rule["outliers"]:', 'for g in rule["outliers"][1:]:'))
    tms, _ = _place(m)
    fails = outlier_failures(tms)
    assert fails and all("group 1 " in f for f in fails), fails


def test_mutant_that_ignores_every_outlier_is_caught():
    m = _mutant(('elif item in hand:\n            badge, why = hand', 'elif False:\n            badge, why = hand'))
    tms, _ = _place(m)
    assert len(outlier_failures(tms)) == sum(1 for items in OUTLIERS.values() for i, (b, a) in items.items() if b != a)


def test_mutant_with_an_exclusive_band_top_is_caught():
    m = _mutant(("        if s <= top:", "        if s < top:"))
    tms, problems = _place(m)
    wrong = {i for i, (score, badge) in BY_HAND.items() if tms[i]["badge"] != badge}
    assert {T + "leechseed", T + "spark", T + "searingshot"} <= wrong, wrong
    assert any("stale" in p for p in problems)  # and the table's own power_badge column disagrees with it


def test_mutant_with_an_inclusive_badge_1_floor_is_caught(tmp_path):
    m = _mutant(('    if s < bands["badge_1_below"]:', '    if s <= bands["badge_1_below"]:'))
    plan, exp, files = _make(m, tmp_path)
    tms, _ = _place(m)
    assert tms[T + "howl"]["badge"] == 1 != exp["unlisted_badge"][T + "howl"]
    # howl is crafted from tackle (badge 2): in the plan the chain rule lifts it back to 2, and fails closed naming
    # the raise badge_rule.chain does not list, so the mutant still builds nothing
    assert plan["tms"][T + "howl"]["badge"] == 2 and files is None
    assert any(p.startswith(T + "howl is raised 1 -> 2") for p in plan["problems"]), plan["problems"]


def test_mutant_that_skips_the_resync_on_a_starter_pick_is_caught(tmp_path):
    m = _mutant(('"advancement revoke @s only %s" % adv, "scoreboard players reset @s %s" % SCORE]',
                 '"advancement revoke @s only %s" % adv]'))
    plan, exp, files = _make(m, tmp_path)
    assert any("starter" in f for f in stranding_failures(files, exp, plan))


def test_mutant_that_never_takes_is_caught(tmp_path):
    m = _mutant(('["recipe take @s %s" % r for r in ids]', '[]'))
    plan, exp, files = _make(m, tmp_path)
    assert any("holds gated" in f for f in stranding_failures(files, exp, plan))


def test_mutant_that_gives_every_badge_at_once_is_caught(tmp_path):
    m = _mutant(('"execute unless entity @s[advancements={%s:flag/%s=true}] run function %s:tm_gate/take/%s"',
                 '"execute unless entity @s[advancements={%s:flag/%s=true}] run function %s:tm_gate/give/%s"'))
    plan, exp, files = _make(m, tmp_path)
    assert earn_failures(files, exp, plan)


def test_mutant_without_devices_is_caught(tmp_path):
    m = _mutant(('    if dev["enforced"]:\n        found', '    if False:\n        found'))
    plan, exp, files = _make(m, tmp_path)
    assert device_failures(files, exp, plan)


def test_mutant_that_closes_no_unlock_is_caught(tmp_path):
    m = _mutant(("        if not hit:\n            continue", "        if True:\n            continue"))
    plan, exp, files = _make(m, tmp_path)
    assert closed_failures(files, exp)


# ---------------------------------------------------------------- the real server snapshot, when present

@pytest.mark.skipif(not (SNAPSHOT / "mods").is_dir(), reason="no server snapshot at %s" % SNAPSHOT)
def test_the_snapshot_places_every_tm_by_the_power_rule_and_matches_the_shelf():
    resolved = G.resolve(G.read_server(SNAPSHOT))
    plan = G.plan(G.load(), resolved, copy.deepcopy(MARKETS), copy.deepcopy(PROGRESSION))
    assert plan["problems"] == [], plan["problems"][:5]  # among them: the snapshot's moves.js is the one scored
    assert shelf_failures(plan) == []
    assert len(plan["shelf_disagreements"]) == len(SHELF_VS_POWER) == 21
    # every TMCraft TM recipe the server loads is gated, and every gated TM recipe makes a TMCraft TM
    made = {rid for rid, (_, r) in resolved["recipes"].items()
            if str(G.result_id(r)).startswith("tmcraft:tm_") and r.get("type") in G.load()["gated"]["grid_types"]}
    tm_gated = {rid for rid, g in plan["gated"].items() if not g.get("device")}
    assert made == tm_gated
    assert len(plan["tms"]) == 802
    assert plan["distribution"] == SNAPSHOT_APPLIED  # APPLIED, moved only by the four chain raises
    assert outlier_failures(plan["tms"]) == []
    assert plan["tms"]["tmcraft:tm_shadowball"]["badge"] == 5  # 81.6: no longer waiting for badge 8 by type


# ---------------------------------------------------------------- the owner's four calls of 2026-10-08

def _snapshot_plan(mod=G):
    resolved = mod.resolve(mod.read_server(SNAPSHOT))
    return mod.plan(mod.load(), resolved, copy.deepcopy(MARKETS), copy.deepcopy(PROGRESSION)), resolved


def test_inferno_and_zap_cannon_land_with_group_3_at_badge_5():
    tms, problems = _place(G)
    assert problems == []
    group = next(g for g in G.load()["badge_rule"]["power"]["outliers"] if g["group"] == 3)
    assert not group.get("not_placed")
    for item, band in ((T + "inferno", 3), (T + "zapcannon", 4)):
        assert (tms[item]["power_badge"], tms[item]["badge"]) == (band, 5), item
        assert tms[item]["rule"].startswith("outlier 3 (Nuzzle)"), tms[item]["rule"]
    # the same badge as the status moves the group compares them with (groups 1 and 2)
    assert {tms[T + m]["badge"] for m in ("nuzzle", "thunderwave", "willowisp", "inferno", "zapcannon")} == {5}


def test_the_three_unlisted_recharge_moves_are_hyper_beam_class_at_badge_7():
    tms, _ = _place(G)
    group = next(g for g in G.load()["badge_rule"]["power"]["outliers"] if g["group"] == 9)
    assert not group.get("not_placed")
    for item, band in ((T + "meteorassault", 4), (T + "prismaticlaser", 5), (T + "roaroftime", 4)):
        assert (tms[item]["power_badge"], tms[item]["badge"]) == (band, 7), item
        assert tms[item]["rule"].startswith("outlier 9 (recharge moves)"), tms[item]["rule"]
    assert tms[T + "hyperbeam"]["badge"] == 7


def test_return_and_frustration_are_placed_by_the_friendship_measurement():
    tms, _ = _place(G)
    # full power is 102 (floor(255 x 10 / 25)), and 102 sits in the badge-7 band (94.1-104), stated by hand
    assert G.band(102, G.load()["badge_rule"]["power"]["bands"]) == 7
    for m in ("return", "frustration"):
        assert (tms[T + m]["power_badge"], tms[T + m]["badge"]) == (7, 7), m
    group = next(g for g in G.load()["badge_rule"]["power"]["outliers"] if g["group"] == 16)
    assert "open" not in group  # the open question was answered by measuring, not left
    assert {"level_up", "walking", "battle", "soothe_bell", "items", "start", "return_at_each_cap"} <= set(
        group["measured"])


def test_every_chain_tm_opens_no_earlier_than_its_input():
    plan, resolved = _snapshot_plan()
    assert plan["problems"] == [], plan["problems"][:5]
    chains = chain_inputs(resolved)
    assert {item for _, item in chains} >= set(CHAIN_RAISES)
    assert chain_failures(plan, chains) == []
    raised = {r["item"]: (r["input"], r["from"], r["to"]) for r in plan["chain_raises"]}
    assert raised == CHAIN_RAISES
    for item, (inp, before, after) in CHAIN_RAISES.items():
        assert plan["tms"][item]["badge"] == after == plan["tms"][inp]["badge"], item
        assert plan["tms"][inp]["badge"] == after  # never the input lowered
    # every raise is a named, reasoned entry in the data
    declared = G.load()["badge_rule"]["chain"]["raises"]
    assert {d["item"]: (d["input"], d["from"], d["to"]) for d in declared} == CHAIN_RAISES
    assert all(d.get("why") for d in declared)


def test_mutant_without_the_chain_raise_is_caught():
    m = _mutant(("            if need > badge[item]:\n", "            if False:\n"))
    plan, resolved = _snapshot_plan(m)
    fails = chain_failures(plan, chain_inputs(resolved))
    assert {f.split(": ")[1].split(" ")[0] for f in fails} == set(CHAIN_RAISES), fails
    dead = [p for p in plan["problems"] if "a dead recipe" in p]
    assert len(dead) == len(CHAIN_RAISES), plan["problems"]
    assert sum("does not raise it" in p for p in plan["problems"]) == len(CHAIN_RAISES)


def test_mutant_without_the_raise_or_the_dead_recipe_check_is_still_caught_here():
    m = _mutant(("            if need > badge[item]:\n", "            if False:\n"),
                ("if i in tms and tms[i][\"badge\"] > tms[item][\"badge\"]:", "if False:"))
    plan, resolved = _snapshot_plan(m)
    assert len(chain_failures(plan, chain_inputs(resolved))) == len(CHAIN_RAISES)


def test_an_undeclared_chain_raise_fails_closed(tmp_path):
    # the fixture's howl is crafted from tackle; score tackle into band 3 and howl (band 2) must rise to it
    scores = F.score_table()
    scores["tms"][T + "tackle"].update(score=60.0, power_badge=3)
    plan, _, _ = _make(G, tmp_path / "a", scores=scores)
    assert [p for p in plan["problems"] if "badge_rule.chain.raises does not list it" in p] == [
        "%showl is raised 2 -> 3 to its input %stackle, and badge_rule.chain.raises does not list it" % (T, T)]
    doc = G.load()
    doc["badge_rule"]["chain"]["raises"].append({"item": T + "howl", "input": T + "tackle", "from": 2, "to": 3})
    plan, _, files = _make(G, tmp_path / "b", doc=doc, scores=copy.deepcopy(scores))
    assert plan["problems"] == [] and files
    assert plan["tms"][T + "howl"]["badge"] == 3


def test_mutant_that_drops_the_hyper_beam_class_placements_is_caught():
    m = _mutant(('for g in rule["outliers"]:', 'for g in [g for g in rule["outliers"] if g["group"] != 9]:'))
    tms, _ = _place(m)
    fails = outlier_failures(tms)
    assert {f.split(" ")[2].rstrip(":") for f in fails} == set(OUTLIERS[9]), fails
    assert all(f.startswith("group 9 ") for f in fails)

"""tools/tm_gate.py: crafted TMs unlock per player at their badge, and no other recipe is stranded.

Every expectation is stated by tests/tm_gate_fixture.py (a synthetic server written by hand) or read here from
data/markets.json; the recipe book is modelled from the pack's own function text. The mutation tests rewrite the
GENERATOR's source in memory (CLAUDE.md "How to prove an audit is independent") and leave data/ untouched.

Not covered (EXP-067): that Minecraft 1.21.1 enforces doLimitedCrafting as the jar reading says, that `recipe give @s *`
and the tick advancement behave as modelled, the toasts a sync shows, and Cobblemon's own TM Machine (out of scope,
data/tm_gate.json does_not_cover).
"""
from __future__ import annotations

import copy
import json
import os
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


def _make(mod, tmp, doc=None, **kw):
    server, vanilla, exp = F.build_server(tmp, **kw)
    doc = doc or mod.load()
    resolved = mod.resolve(mod.read_server(server, vanilla))
    plan = mod.plan(doc, resolved, copy.deepcopy(MARKETS), copy.deepcopy(PROGRESSION))
    return plan, exp, (mod.build(doc, plan) if not plan["problems"] else None)


def _badge_of(plan, rid):
    return plan["gated"][rid]["badge"]


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
    assert plan["shelf_disagreements"] == []  # the unlisted rule, applied to the shelf, reproduces it


def test_unlisted_tms_follow_the_rule_worked_by_hand(tmp_path):
    plan, exp, _ = _make(G, tmp_path)
    got = {item: plan["tms"][item]["badge"] for item in exp["unlisted_badge"]}
    assert got == exp["unlisted_badge"]


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


# ---------------------------------------------------------------- mutations of the generator: each check bites

def test_mutant_without_the_give_strands_recipes(tmp_path):
    m = _mutant(('"recipe give @s *"]', '"# mutant: no give"]'))
    plan, exp, files = _make(m, tmp_path)
    assert any("lacks" in f for f in stranding_failures(files, exp, plan))


def test_mutant_off_by_one_shelf_badge_is_caught(tmp_path):
    m = _mutant(('badge, rule = shelf[item], "shelf"', 'badge, rule = shelf[item] + 1, "shelf"'))
    plan, _, _ = _make(m, tmp_path)
    assert shelf_failures(plan)


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


def test_mutant_that_ignores_the_grade_is_caught(tmp_path):
    m = _mutant(("b, w = max(floor, tb, gb),", "b, w = max(floor, tb),"))
    plan, exp, _ = _make(m, tmp_path)
    got = {item: plan["tms"][item]["badge"] for item in exp["unlisted_badge"]}
    assert got != exp["unlisted_badge"]


# ---------------------------------------------------------------- the real server snapshot, when present

@pytest.mark.skipif(not (SNAPSHOT / "mods").is_dir(), reason="no server snapshot at %s" % SNAPSHOT)
def test_the_snapshot_places_every_tm_and_matches_the_shelf():
    resolved = G.resolve(G.read_server(SNAPSHOT))
    plan = G.plan(G.load(), resolved, copy.deepcopy(MARKETS), copy.deepcopy(PROGRESSION))
    assert plan["problems"] == [], plan["problems"][:5]
    assert shelf_failures(plan) == []
    assert plan["shelf_disagreements"] == []
    # every TMCraft TM recipe the server loads is gated, and every gated TM recipe makes a TMCraft TM
    made = {rid for rid, (_, r) in resolved["recipes"].items()
            if str(G.result_id(r)).startswith("tmcraft:tm_") and r.get("type") in G.load()["gated"]["grid_types"]}
    tm_gated = {rid for rid, g in plan["gated"].items() if not g.get("device")}
    assert made == tm_gated

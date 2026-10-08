"""tools/bank.py's AFK exclusion (data/bank.json base_removed, buys_removed, afk_rule; the owner, 2026-10-10).

The generator's own tests. The independent check that the bank buys no unblocked AFK item belongs to
tools/economy_audit.py (test-author's), which keeps its own AFK table."""
import copy
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import bank as B  # noqa: E402


def _doc():
    return copy.deepcopy(B.load())


def test_the_committed_data_has_no_afk_or_removal_problem():
    doc = _doc()
    bank = B.prices(doc)
    assert B.afk_problems(doc, bank) == []
    assert B.removal_problems(doc, {e["item"] for e in B.base_entries(doc)}, {b["item"] for b in doc["buys"]}) == []


def test_the_output_drops_every_base_removed_entry_and_keeps_the_rest_in_order():
    doc = _doc()
    gone = set(B.base_removed(doc))
    out = [e["item"] for e in B.entries(doc)]
    assert gone and not gone & set(out)
    kept_base = [e["item"] for e in B.base_entries(doc) if e["item"] not in gone]
    assert out[:len(kept_base)] == kept_base
    assert json.loads((ROOT / doc["output"]).read_text(encoding="utf-8")) == {"bank": B.entries(doc)}


def test_the_owner_named_goods_are_not_bought():
    bank = B.prices(_doc())
    for iid in ("minecraft:melon_slice", "minecraft:dried_kelp", "minecraft:cod", "minecraft:bread",
                "cobblemon:red_apricorn", "cobblemon:oran_berry", "minecraft:string", "minecraft:nether_wart",
                "minecraft:amethyst_shard", "cobblemon:relic_coin"):
        assert iid not in bank, iid
    for iid in ("minecraft:diamond", "minecraft:raw_iron", "minecraft:ancient_debris", "minecraft:netherite_ingot",
                "minecraft:quartz"):
        assert iid in bank, iid      # ore and the Nether tier stay flat


def test_a_farm_item_bought_without_an_exception_is_refused():
    doc = _doc()
    doc["buys"].append({"item": "minecraft:wheat", "price": 1, "group": "minerals", "tier": "early", "supply": "x",
                        "rate_per_hour": 0, "why": "x"})
    probs = B.afk_problems(doc, B.prices(doc))
    assert any(p.startswith("minecraft:wheat is bought") for p in probs), probs


def test_re_adding_a_removed_base_entry_is_refused():
    doc = _doc()
    doc["base_removed"]["entries"] = [r for r in doc["base_removed"]["entries"] if r["item"] != "minecraft:cod"]
    probs = B.afk_problems(doc, B.prices(doc))
    assert any(p.startswith("minecraft:cod is bought at $10") for p in probs), probs


def test_an_apricorn_back_in_buys_is_refused_by_group_and_by_buys_removed():
    doc = _doc()
    doc["buys"].append({"item": "cobblemon:red_apricorn", "price": 1, "group": "apricorns", "tier": "early",
                        "supply": "x", "rate_per_hour": 0, "why": "x", "in_place": True})
    probs = B.afk_problems(doc, B.prices(doc))
    assert any("group apricorns is excluded" in p for p in probs), probs
    rp = B.removal_problems(doc, set(), {b["item"] for b in doc["buys"]})
    assert any("removed and still in buys" in p for p in rp), rp


def test_a_stale_exception_or_removal_is_refused():
    doc = _doc()
    doc["afk_rule"]["exceptions"].append({"item": "minecraft:quartz", "why": "x", "decision": "x"})
    probs = B.afk_problems(doc, B.prices(doc))
    assert any("quartz: in no afk_rule list" in p for p in probs), probs
    doc = _doc()
    doc["base_removed"]["entries"].append({"item": "minecraft:wheat", "price": 1, "afk": "farm", "why": "x"})
    rp = B.removal_problems(doc, {e["item"] for e in B.base_entries(doc)}, set())
    assert any("the base does not buy it" in p for p in rp), rp
    doc = _doc()
    doc["base_removed"]["entries"][0]["price"] += 1
    rp = B.removal_problems(doc, {e["item"] for e in B.base_entries(doc)}, set())
    assert any("the record is stale" in p for p in rp), rp


def test_a_removal_without_a_reason_is_refused():
    doc = _doc()
    doc["buys_removed"]["entries"][0]["left_bank"] = ""
    rp = B.removal_problems(doc, set(), set())
    assert any("a removal is recorded, never silent" in p for p in rp), rp


def test_no_afk_rule_fails_closed():
    doc = _doc()
    del doc["afk_rule"]
    assert B.afk_problems(doc, B.prices(doc))


def _fake_server(tmp_path, drops, blacklist):
    (tmp_path / "mods").mkdir()
    (tmp_path / "datapacks").mkdir()
    (tmp_path / "config").mkdir()
    with zipfile.ZipFile(tmp_path / "mods" / "fake.jar", "w") as z:
        z.writestr("data/cobblemon/species/generation1/fakemon.json",
                   json.dumps({"name": "Fakemon", "drops": {"amount": 2, "entries": [{"item": i} for i in drops]}}))
        z.writestr("data/cobblemon/recipe/not_a_species.json", json.dumps({"drops": {"entries": [{"item": "x:y"}]}}))
    (tmp_path / "config" / "PastureLoot.json").write_text(json.dumps({"item_blacklist": blacklist}))
    return tmp_path


# Without it a bought item a pastured species drops could stay in the bank unnamed: the server's blacklist and a
# non-species file are skipped, a bought undeclared drop is a problem, and one afk_rule.ranch names is not.
# (Until ranch_ore was resolved the diamond was the declared case; the ore left afk_rule.ranch for the overlay's
# blacklist, so the declared case is now made explicitly on a copy of the record.)
def test_the_ranch_is_re_measured_from_the_species_tables(tmp_path):
    sd = _fake_server(tmp_path, ["minecraft:quartz", "minecraft:diamond", "minecraft:raw_gold"],
                      ["minecraft:raw_gold", "minecraft:diamond"])
    drops = B.ranch_drops(sd)
    assert set(drops) == {"minecraft:quartz"}      # the blacklist and non-species files skipped
    doc = _doc()
    probs = B.ranch_problems(doc, B.prices(doc), drops)
    assert len(probs) == 1 and probs[0].startswith("minecraft:quartz is bought"), probs
    doc["afk_rule"]["ranch"]["items"].append("minecraft:quartz")
    assert B.ranch_problems(doc, B.prices(doc), drops) == []


# Without it bank.py's own check could judge the ranch by a server's stale config/PastureLoot.json (the base file a
# snapshot taken before the overlay carries) and not by modpack/config/PastureLoot.json, which install delivers: the
# fake server's blacklist names nothing, the overlay names the bought ores, so with prefer_overlay no ore is a drop.
def test_the_bank_judges_the_ranch_by_the_overlay_blacklist(tmp_path):
    ores = ["minecraft:coal", "minecraft:raw_iron", "minecraft:diamond", "minecraft:emerald", "minecraft:redstone"]
    sd = _fake_server(tmp_path, ores + ["minecraft:quartz"], [])
    assert B.pasture_config(sd) == sd / "config" / "PastureLoot.json"
    assert B.pasture_config(sd, prefer_overlay=True) == B.PASTURE_LOOT
    assert set(B.ranch_drops(sd)) == set(ores) | {"minecraft:quartz"}
    assert set(B.ranch_drops(sd, B.pasture_config(sd, prefer_overlay=True))) == {"minecraft:quartz"}

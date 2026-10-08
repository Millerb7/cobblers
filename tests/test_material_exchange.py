"""The material exchange (docs/mechanics/MATERIAL_EXCHANGE.md): the bank buys real Minecraft effort, two off-path
counters sell rewards at exactly N x the bank's price for a named material.

Written by the builder of the exchange (the independent audit is owed: data/bank.json audit_checklist). Three layers:
  - the rules on the committed data (tools/bank.py check: 0 problems), and each rule made to fire by a record change;
  - the ARTIFACTS, read as text and never through tools/bank.py's exchange code: the bank file CobbleDollars reads
    (modpack/config/cobbledollars/bank.json) and the merchant summons tools/markets.py builds, parsed with
    tools/markets_audit.py's own SNBT reader. Every exchange line's offered Price is count x the written bank price;
  - GENERATOR mutations (CLAUDE.md "Mutate the GENERATOR, not the record"): tools/markets.py merchant_shop and
    tools/bank.py entries changed, data untouched; the artifact check must name the drift.
Jar facts (the barter answer, the ids) are checked when the snapshot jars are present, else skipped and said so.
"""
from __future__ import annotations

import copy
import json
import math
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
import sys  # noqa: E402

sys.path.insert(0, str(ROOT / "tools"))

import bank  # noqa: E402
import markets  # noqa: E402
import markets_audit as MA  # noqa: E402

DOC = bank.load()
MDOC = markets.load()
JAR_DIR = Path(os.environ.get("COBBLERS_JAR_DIR") or "C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods")
VANILLA = Path(os.environ.get("COBBLERS_VANILLA_JAR") or
               os.path.expandvars("%APPDATA%/ModrinthApp/meta/versions/1.21.1-0.19.5/1.21.1-0.19.5.jar"))


def _jar(prefix):
    if not JAR_DIR.is_dir():
        return None
    hits = sorted(JAR_DIR.glob(prefix + "*.jar"))
    return hits[0] if hits else None


def _lines():
    return bank.exchange_lines(MDOC)


# ================================================================================================ the rules, as committed
def test_bank_check_is_clean_on_the_committed_data():
    out, _skipped, n = bank.problems(DOC)
    assert out == [], out
    assert n > 0


def test_there_is_an_exchange_and_the_master_ball_is_netherite():
    lines = {(rec["id"], it["item"]): it for _k, rec, it in _lines()}
    assert len(lines) >= 10, "the exchange shrank to %d lines" % len(lines)
    mb = lines[("northlight_station", "cobblemon:master_ball")]
    assert mb["exchange_for"] == {"item": "minecraft:netherite_ingot", "count": 30}
    assert mb["price"] == 30 * bank.prices(DOC)["minecraft:netherite_ingot"]


def test_every_tier_holds_both_wage_rules():
    rows = bank.effort_rows(DOC, MDOC)
    assert {r[1].split()[1] for r in rows} == set(DOC["effort_model"]["tiers"])
    assert [p for p, _ in rows if p] == []


# ------------------------------------------------------------------------------------------------ each rule fires
def _ex(doc, mdoc):
    return bank.exchange_problems(doc, mdoc, bank.prices(doc))


def _line(mdoc, cid, item):
    for c in mdoc["counters"]:
        if c["id"] == cid:
            for it in c["stock"]:
                if it["item"] == item:
                    return c, it
    raise KeyError((cid, item))


def test_a_price_off_by_one_dollar_is_named():
    m = copy.deepcopy(MDOC)
    _c, it = _line(m, "fossick", "cobblemon:metal_coat")
    it["price"] += 1
    assert any("metal_coat" in p and "would lie about its rate" in p for p in _ex(DOC, m))


def test_an_exchange_on_the_critical_path_is_named():
    m = copy.deepcopy(MDOC)
    c, _it = _line(m, "northlight_station", "cobblemon:master_ball")
    c["path"] = "critical"
    assert any("on the price curve" in p for p in _ex(DOC, m))


def test_a_reward_the_bank_buys_back_is_named():
    d = copy.deepcopy(DOC)
    d["buys"].append({"item": "cobblemon:oval_stone", "price": 5, "group": "drops", "tier": "deep", "supply": "x",
                      "rate_per_hour": 0, "why": "x"})
    assert any("oval_stone" in p and "round trip" in p for p in _ex(d, MDOC))


def test_a_master_ball_cheaper_than_the_capsule_is_under_the_ball_floor():
    m = copy.deepcopy(MDOC)
    _c, it = _line(m, "northlight_station", "cobblemon:master_ball")
    it["exchange_for"]["count"] = 5
    it["price"] = 5 * bank.prices(DOC)["minecraft:netherite_ingot"]
    assert any("master_ball" in p and "ball floor" in p for p in _ex(DOC, m))


def _held_lines(m):
    held = set(DOC["exchanges"]["floors"]["held_item"]["from_items"])
    return [it for c in m["counters"] for it in c["stock"] if it["item"] in held and "exchange_for" not in it]


def test_the_held_item_floor_reads_only_lines_that_are_not_income_gated():
    # ECONOMY_OVERHAUL section 7 R8: "Read from lines that are not income-gated only, or the floor jumps to $35,000+".
    # By hand: the committed floor is the dearest of the eight held items, $1,000. Viltri's Mystic Water raised to
    # $35,000 AS AN INCOME-GATE line leaves it at $1,000; the same price as an ordinary line lifts it to $35,000.
    # Without it R3's income-gated held items would push every held-item exchange under its floor.
    assert bank.exchange_floors(DOC, MDOC)[0]["held_item"][0] == max(it["price"] for it in _held_lines(MDOC)) == 1000
    m = copy.deepcopy(MDOC)
    _c, it = _line(m, "viltri_quay", "cobblemon:mystic_water")
    it.update(price=35000, price_rule="income_gate")
    floors, stale = bank.exchange_floors(DOC, m)
    assert floors["held_item"][0] == 1000 and stale == []
    del it["price_rule"]
    assert bank.exchange_floors(DOC, m)[0]["held_item"][0] == 35000


def test_a_held_item_floor_with_every_line_income_gated_fails_closed_and_is_not_called_stale():
    # R8's edge: when every held item on the shelves is income-gated there is no ungated value to read. The floor must
    # be reported unreadable (never silently None), and the held items must not be called stale: they are sold.
    m = copy.deepcopy(MDOC)
    for it in _held_lines(m):
        it["price_rule"] = "income_gate"
    floors, stale = bank.exchange_floors(DOC, m)
    assert floors["held_item"][0] is None and stale == []
    assert any("floor for held_item cannot be read" in p for p in _ex(DOC, m))


def test_the_ball_floor_still_counts_income_gated_lines_until_the_owner_decides_r4():
    # R4 (exclude income-gate lines from the Master Ball floor) is the OWNER's decision and is not taken: the ball
    # floor still reads every non-exchange line, gated or not. An income-gated $35,000 line therefore lifts the ball
    # floor above the $27,000 Master Ball and is named -- which is why Fossick's dearer TMs stay held. When the owner
    # takes R4 this test must change with the rule, not be deleted.
    m = copy.deepcopy(MDOC)
    _c, it = _line(m, "viltri_quay", "cobblemon:mystic_water")
    it.update(price=35000, price_rule="income_gate")
    assert bank.exchange_floors(DOC, m)[0]["ball"][0] == 35000
    assert any("master_ball" in p and "ball floor" in p for p in _ex(DOC, m))


def test_an_evolution_item_under_the_stone_price_is_named():
    m = copy.deepcopy(MDOC)
    _c, it = _line(m, "fossick", "cobblemon:razor_claw")
    it["exchange_for"]["count"] = 10
    it["price"] = 10 * bank.prices(DOC)["minecraft:diamond"]
    assert any("razor_claw" in p and "evolution_item floor" in p for p in _ex(DOC, m))


def test_a_material_the_bank_does_not_buy_is_named():
    m = copy.deepcopy(MDOC)
    _c, it = _line(m, "fossick", "cobblemon:razor_fang")
    it["exchange_for"]["item"] = "minecraft:blaze_rod"
    assert any("razor_fang" in p and "not bought by the bank" in p for p in _ex(DOC, m))


def test_a_town_outside_exchanges_towns_is_named():
    d = copy.deepcopy(DOC)
    d["exchanges"]["towns"] = ["northlight"]
    assert any("fossick" in p and "exchanges.towns" in p for p in _ex(d, MDOC))


def test_a_netherite_ingot_worth_less_than_its_parts_is_named():
    d = copy.deepcopy(DOC)
    for b in d["buys"]:
        if b["item"] == "minecraft:netherite_ingot":
            b["price"] = 800
    assert any("netherite_ingot" in p and "inputs" in p for p in bank.craft_problems(d, bank.prices(d)))


R5_UPPER_FACTOR = 1.5   # docs/mechanics/ECONOMY_OVERHAUL.md section 7 R5: the upper hour <= 1.5 x the fight hour


def _r5_debris_break():
    """The lowest whole-dollar ancient_debris price at which the nether tier's upper hour passes R5's ceiling, worked
    here from R5 itself and not through tools/bank.py: the fight hour is the opening leg's battle income
    (data/markets.json income_basis.leg_by_badge) / effort_model.max_leg_hours, the ceiling 1.5 x that, and the upper
    hour the sum over the tier's buys of (rate_per_hour_upper, else rate_per_hour) x price."""
    em = DOC["effort_model"]
    t = em["tiers"]["nether"]
    fight = MDOC["income_basis"]["leg_by_badge"][str(t["opens_leg"])] / em["max_leg_hours"]
    rows = [b for b in DOC["buys"] if b.get("tier") in set(t["from_tiers"])]
    rate = lambda b: b["rate_per_hour_upper"] if b.get("rate_per_hour_upper") is not None else b["rate_per_hour"]  # noqa: E731
    debris = next(b for b in rows if b["item"] == "minecraft:ancient_debris")
    rest = sum(rate(b) * b["price"] for b in rows if b is not debris)
    return math.floor((R5_UPPER_FACTOR * fight - rest) / rate(debris)) + 1


def _debris_at(price):
    d = copy.deepcopy(DOC)
    for b in d["buys"]:
        if b["item"] == "minecraft:ancient_debris":
            b["price"] = price
    return [p for p, _ in bank.effort_rows(d, MDOC) if p]


# Without it debris priced as a shortcut past the economy would pass R5's upper wage. The breaking price is derived
# from R5 (about $549 on 2026-10-08 data): one dollar under it passes, at it the nether tier fails upper_wage. The
# committed price must sit under it, or the real data already breaks R5.
def test_debris_priced_for_a_shortcut_breaks_the_upper_wage():
    assert DOC["effort_model"]["upper_factor"] == R5_UPPER_FACTOR
    p = _r5_debris_break()
    real = next(b["price"] for b in DOC["buys"] if b["item"] == "minecraft:ancient_debris")
    assert real < p, (real, p)
    assert not [x for x in _debris_at(p - 1) if "nether" in x and "upper_wage" in x], p - 1
    probs = _debris_at(p)
    assert any("nether" in x and "upper_wage" in x for x in probs), (p, probs)


def test_buying_an_unreachable_item_is_named():
    d = copy.deepcopy(DOC)
    d["buys"].append({"item": "minecraft:dragon_egg", "price": 50000, "group": "nether", "tier": "nether",
                      "supply": "x", "rate_per_hour": 0, "why": "x"})
    out, _s, _n = bank.problems(d)
    assert any("dragon_egg" in p and "unreachable" in p for p in out)


def test_smelting_debris_pays_raw_to_raw_plus_two():
    p = bank.prices(DOC)
    assert p["minecraft:ancient_debris"] <= p["minecraft:netherite_scrap"] <= p["minecraft:ancient_debris"] + bank.SMELT_MAX


# ================================================================================================ the artifacts
def _bank_file_prices(text):
    """{item: price} from the bank file's TEXT (the shape CobbleDollars reads: {"bank": [{item, price}]})."""
    return {e["item"]: int(e["price"]) for e in json.loads(text)["bank"]}


def _offers_by_merchant(pack):
    """{tag: {item id: Price string}} from the built pack's summons, read with markets_audit's own SNBT reader."""
    out = {}
    for s in MA.merchant_summons(MA.load_pack(pack)):
        for t in s["tags"]:
            for cat in s["nbt"].get("CobbleMerchantShop") or []:
                for o in cat.get("Offers") or []:
                    out.setdefault(t, {})[(o.get("Item") or {}).get("id")] = o.get("Price")
    return out


def artifact_mismatches(bank_text, pack):
    """Every exchange line whose INSTALLED merchant offer is not count x the INSTALLED bank price of its material."""
    paid = _bank_file_prices(bank_text)
    offers = _offers_by_merchant(pack)
    tag = MDOC["stall_merchant"]["tag"]
    bad = []
    for _k, rec, it in _lines():
        mat, n = it["exchange_for"]["item"], it["exchange_for"]["count"]
        got = (offers.get("%s_%s" % (tag, rec["id"])) or {}).get(it["item"])
        want = n * paid.get(mat, -1)
        if got is None or int(got) != want:
            bad.append((rec["id"], it["item"], got, want))
    return bad


def _built():
    files, _npcs = markets.build(MDOC)
    return files


def test_the_installed_bank_file_is_the_committed_one():
    assert json.loads((ROOT / DOC["output"]).read_text(encoding="utf-8")) == json.loads(bank.text(DOC))


def test_every_installed_exchange_offer_is_count_times_the_installed_bank_price():
    text = (ROOT / DOC["output"]).read_text(encoding="utf-8")
    assert artifact_mismatches(text, _built()) == []


def test_mutating_the_merchant_writer_is_caught(monkeypatch):
    real = markets.merchant_shop

    def doubled(stall):
        shop = real(stall)
        for cat in shop:
            for o in cat["Offers"]:
                o["Price"] = str(int(o["Price"]) * 2)
        return shop

    monkeypatch.setattr(markets, "merchant_shop", doubled)
    bad = artifact_mismatches((ROOT / DOC["output"]).read_text(encoding="utf-8"), _built())
    assert len(bad) == len(_lines()), bad


def test_mutating_the_bank_writer_is_caught(monkeypatch):
    real = bank.entries

    def dearer(doc):
        return [dict(e, price=e["price"] + 1) if e["item"] == "minecraft:netherite_ingot" else e for e in real(doc)]

    monkeypatch.setattr(bank, "entries", dearer)
    bad = artifact_mismatches(bank.text(DOC), _built())
    assert {b[0] for b in bad} == {"northlight_station"}
    assert len(bad) == sum(1 for _k, _r, it in _lines() if it["exchange_for"]["item"] == "minecraft:netherite_ingot")


# ================================================================================================ the jars
def _lang(jar, ns):
    with zipfile.ZipFile(jar) as z:
        lang = json.loads(z.read("assets/%s/lang/en_us.json" % ns))
    return {k.split(".", 2)[2] for k in lang if k.startswith(("item.%s." % ns, "block.%s." % ns)) and k.count(".") == 2}


def test_every_new_id_is_an_item_in_the_snapshot_jars():
    cob = _jar("Cobblemon-fabric-1.8.0")
    if cob is None or not VANILLA.is_file():
        pytest.skip("NOT_EXECUTED: no snapshot Cobblemon jar (COBBLERS_JAR_DIR) or vanilla jar (COBBLERS_VANILLA_JAR)")
    have = {"cobblemon": _lang(cob, "cobblemon"), "minecraft": _lang(VANILLA, "minecraft")}
    ids = {b["item"] for b in DOC["buys"]} | {n["item"] for n in DOC["never_buy"]} | \
        {u["item"] for u in DOC["unreachable"]} | {it["item"] for _k, _r, it in _lines()} | \
        {it["exchange_for"]["item"] for _k, _r, it in _lines()}
    missing = sorted(i for i in ids if i.split(":")[0] in have and i.split(":")[1] not in have[i.split(":")[0]])
    assert missing == []


def test_the_master_ball_recipe_needs_what_the_world_cannot_supply():
    cob = _jar("Cobblemon-fabric-1.8.0")
    if cob is None:
        pytest.skip("NOT_EXECUTED: no snapshot Cobblemon jar (COBBLERS_JAR_DIR)")
    with zipfile.ZipFile(cob) as z:
        text = z.read("data/cobblemon/recipe/master_ball.json").decode()
    unreachable = {u["item"] for u in DOC["unreachable"]}
    assert "minecraft:nether_star" in text and "minecraft:shulker_shell" in text
    assert {"minecraft:nether_star", "minecraft:shulker_shell"} <= unreachable


def test_the_barter_answer_a_merchant_offer_holds_only_item_price_and_stock():
    jar = _jar("CobbleDollars-fabric-2.0.0+Beta-5.1")
    javap = shutil.which("javap")
    if jar is None or javap is None:
        pytest.skip("NOT_EXECUTED: no snapshot CobbleDollars jar (COBBLERS_JAR_DIR) or no javap on PATH")
    out = subprocess.run([javap, "-p", "-cp", str(jar), "fr.harmex.cobbledollars.common.world.item.trading.shop.Offer"],
                         capture_output=True, text=True, check=True).stdout
    fields = re.findall(r"^\s+private (?:final )?([\w.$]+) (\w+);$", out, re.M)
    assert sorted(fields, key=lambda f: f[1]) == [("net.minecraft.class_1799", "item"),
                                                  ("java.math.BigInteger", "price"), ("int", "stock")]

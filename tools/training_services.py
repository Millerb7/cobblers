#!/usr/bin/env python
"""Paid training services: a keeper at each training ground who, for CobbleDollars, raises one Pokemon to the player's
current RCT level cap, trains in an EV spread, or perfects IVs. Generated from data/training_services.json into the
world-local datapack build/datapacks/cobblers_training_services.

The design is docs/mechanics/ECONOMY_OVERHAUL.md section 5 (BUILD LIST U7). Every part is an existing piece; nothing
new runs in the game:

  the keeper     a Cobblemon NPC whose class opens a dialogue (tools/compile_dialogue.py), one per training ground
                 (data/training_grounds.json), seated two blocks east of the ground's sign on the canonical heightmap
                 (tools/ground.py, rounded, plus one), never on a world. Placed over RCON by tools/reapply.py R17TS
                 after a restart, as the ferrymen are (R17F), because NPC classes load only at a boot.
  the dialogue   one per keeper, compiled from a conversation built here in memory: a hub, then one page per service
                 that offers Slot 1..6. The EV and IV options are visible only to a player holding gym2_cleared and
                 gym8_cleared; the functions check the same flags again. Each slot option runs its own two-line
                 function that writes the slot into storage and calls the service's macro function with it: a
                 dialogue `function` effect takes a bare id, so the slot travels in the function's name.
  the slot read  testpartyslot @s <slot> level=L for L = 1..max_level, returning the first L that matches, or 0
                 for an empty slot (testpartyslot matches by equality only: note A1 of
                 docs/research/notes/paid-services-and-npc-payouts.md).
  the cap        `$execute store result score @s cob_ts_cap run rctmod player get level_cap @s$(x)` on a macro line
                 (EXP-046; tools/levelcap_pack.py). `level=` fires no experience event, so rctmod never clamps it:
                 the raise writes EXACTLY the score it has just read, through `req.cap`, and no level is authored.
  the payment    the ferry's checked sequence (tools/ferries.py trip_lines): read the balance, refuse when short,
                 set the click's cooldown, charge through `$cobbledollars remove @s $(amount)`, re-read, and do
                 nothing unless it fell by exactly the price. Every refusal before the charge charges nothing. A raise
                 that does not read back at the cap gives the price back (`cobbledollars give`).

  python tools/training_services.py seat [--write] [--source-root R]   recompute each keeper's seat from the heightmap
  python tools/training_services.py build [--out DIR]                  write the pack (no heightmap needed)
  python tools/training_services.py audit [--source-root R]            the builder's offline audit; exit 1 on a problem

What it does NOT cover: the moves and evolutions a level set skips (EXP-062 S2); reading the EVs and IVs back after
their edit (testpartyslot's EV/IV matching is unread); the postgame per-level price (owner question 7, not built);
keepers in a world that has not run R17TS.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import compile_dialogue as CD  # noqa: E402
import function_limits  # noqa: E402

DATA = ROOT / "data" / "training_services.json"
GROUNDS = ROOT / "data" / "training_grounds.json"
TOWNS = ROOT / "data" / "towns.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_training_services"
NS, FN = "cobblers", "training_services"
SCORE, CAP, COOLDOWN = "cob_ts", "cob_ts_cap", "cob_ts_cd"
STORAGE = "%s:%s" % (NS, FN)
QUEST = "training_services"
CURSOR = "quest.%s.menu_cursor" % QUEST
STATS = ("hp", "attack", "defence", "special_attack", "special_defence", "speed")
STAT_NAMES = {"hp": "HP", "attack": "Attack", "defence": "Defence", "special_attack": "Sp. Atk",
              "special_defence": "Sp. Def", "speed": "Speed"}
SLOTS = range(1, 7)
NPC_RADIUS = 2.5            # reapply's npc action counts cobblemon:npc within 2 blocks of the spot
# The ground rule (tools/ground_rule.py): nothing here reads a world; every position comes from tools/ground.py.
WORLD_READS: set = set()


class ServiceError(SystemExit):
    pass


def load(path=DATA):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fn_id(rel):
    return "%s:%s/%s" % (NS, FN, rel)


def fn_path(rel):
    return "data/%s/function/%s/%s.mcfunction" % (NS, FN, rel)


def fill(template, **kw):
    for k, v in kw.items():
        template = template.replace("{%s}" % k, str(v))
    if re.search(r"\{[a-z_]+\}", template):
        raise ServiceError("message %r names a placeholder this tool does not fill" % template)
    return template


def text(s, color="gray"):
    return json.dumps({"text": s, "color": color}, ensure_ascii=False)


def scored(template, holder, objective, placeholder, color="gray", **kw):
    """A tellraw component list with one placeholder rendered as a score."""
    before, _, after = template.partition("{%s}" % placeholder)
    return json.dumps([{"text": "", "color": color}, {"text": fill(before, **kw)},
                       {"score": {"name": holder, "objective": objective}}, {"text": fill(after, **kw)}],
                      ensure_ascii=False)


def snbt_str(s):
    if '"' in s or "\\" in s:
        raise ServiceError("a storage string may not hold a quote or a backslash: %r" % s)
    return '"%s"' % s


# ---------------------------------------------------------------------------------------------------------- the seats
def grounds():
    return {g["id"]: g for g in json.loads(GROUNDS.read_text(encoding="utf-8"))["grounds"]}


def seat_for(doc, gr, g, towns):
    """([x, y, z], yaw) for a ground's keeper: the seat offset from the ground's Habitat Block, one above the
    heightmap's rounded ground, turned to face the town centre (Minecraft yaw: 0 south, 90 west, 180 north)."""
    ox, oz = doc["seat"]["offset"]
    x, z = gr["site"]["x"] + ox, gr["site"]["z"] + oz
    t = towns[gr["town"]]["centre"]
    yaw = int(round(math.degrees(math.atan2(-(t["x"] - x), t["z"] - z)))) % 360
    return [x, int(g(x, z)) + 1, z], yaw


def seats(doc, source_root=None):
    import ground as G
    g = G.load(source_root)
    towns = {t["id"]: t for t in json.loads(TOWNS.read_text(encoding="utf-8"))["towns"]}
    gs = grounds()
    return {k["ground"]: seat_for(doc, gs[k["ground"]], g, towns) for k in doc["keepers"]}


def seated(doc):
    return [k for k in doc["keepers"] if isinstance(k.get("at"), list) and len(k["at"]) == 3]


def keeper_id(k):
    return k["ground"].replace("training_ground_", "")


def npc_placements(doc=None):
    """[(conversation id, (x, y, z), npc class, yaw)] for tools/reapply.py's "npc" action, from the committed data."""
    doc = doc or load()
    return [("dlg_training_keeper_%s" % keeper_id(k), tuple(k["at"]), "%s:npc_training_keeper_%s" % (NS, keeper_id(k)),
             int(k["yaw"])) for k in seated(doc)]


# ------------------------------------------------------------------------------------------------------- the functions
def slot_level_lines(max_level):
    """Macro $(slot): return the slot's level, 1..max_level, or 0 when no level matches (an empty slot)."""
    out = ["# Generated by tools/training_services.py. Macro $(slot): returns the slot's level, or 0 for an empty slot.",
           "# testpartyslot matches level= by equality only (paid-services note A1), so each level is tested in turn",
           "scoreboard players set #hit %s 0" % SCORE]
    for lv in range(1, max_level + 1):
        out += ["$execute store result score #hit %s run testpartyslot @s $(slot) level=%d" % (SCORE, lv),
                "execute if score #hit %s matches 1 run return %d" % (SCORE, lv)]
    out.append("return 0")
    return out


def cooldown_check():
    return ["# a second submit of the same click, or a purchase straight after one, does nothing",
            "execute store result score #now %s run time query gametime" % SCORE,
            "execute if score @s %s > #now %s run return 0" % (COOLDOWN, SCORE)]


def gate_check(doc, svc):
    flag = svc.get("gate")
    if not flag:
        return []
    req = "your %s badge" % {"gym2_cleared": "second", "gym8_cleared": "eighth"}.get(flag, flag)
    return ["# the dialogue hides this option without %s; checked again here, before anything is read or taken" % flag,
            "execute unless entity @s[advancements={%s:flag/%s=true}] run return run tellraw @s %s"
            % (NS, flag, text(fill(doc["messages"]["gated"], requirement=req), "gold"))]


def slot_read(doc):
    return ["# preset, so a slot read that never stored cannot leave another purchase's level behind",
            "scoreboard players set #lv %s 0" % SCORE,
            "execute store result score #lv %s run function %s with storage %s req" % (SCORE, fn_id("slot_level"), STORAGE),
            "execute unless score #lv %s matches 1.. run return run tellraw @s %s"
            % (SCORE, text(doc["messages"]["slot_empty"], "gold"))]


def payment(doc, price):
    """The ferry's checked charge (tools/ferries.py trip_lines): nothing above this block has taken anything."""
    m = doc["messages"]
    short = scored(m["short"], "@s", SCORE, "balance", "gold", price=price)
    return ["# the price, $%d: read the balance first (EXP-040), refuse if it is short, nothing taken" % price,
            "execute store result score @s %s run cobbledollars query @s" % SCORE,
            "execute unless score @s %s matches %d.. run return run tellraw @s %s" % (SCORE, price, short),
            "# from here the click is spent: a second one inside the cooldown is refused above",
            "scoreboard players operation @s %s = #now %s" % (COOLDOWN, SCORE),
            "scoreboard players add @s %s %d" % (COOLDOWN, int(doc["cooldown_ticks"])),
            "data modify storage %s charge.amount set value %d" % (STORAGE, price),
            "function %s with storage %s charge" % (fn_id("charge"), STORAGE),
            "# the charge must have taken exactly the price, or the service does nothing (#after preset to -1, so a read",
            "# that never stored cannot match)",
            "scoreboard players set #after %s -1" % SCORE,
            "execute store result score #after %s run cobbledollars query @s" % SCORE,
            "scoreboard players operation #want %s = @s %s" % (SCORE, SCORE),
            "scoreboard players remove #want %s %d" % (SCORE, price),
            "execute unless score #after %s = #want %s run return run tellraw @s %s"
            % (SCORE, SCORE, text(m["charge_failed"], "red"))]


def raise_run(doc):
    svc, m = doc["services"]["raise"], doc["messages"]
    price, top = int(svc["price"]), int(svc["max_cap"])
    return (["# Generated by tools/training_services.py from data/training_services.json: raise one Pokemon to the",
             "# player's RCT level cap. As the player, from a keeper's dialogue. Macro: $(slot) and $(x) (the cap read)."]
            + cooldown_check() + gate_check(doc, svc)
            + ["# the cap, read now: `level=` bypasses rctmod's clamp, so the set below writes exactly this score",
               "scoreboard players set @s %s 0" % CAP,
               "$execute store result score @s %s run rctmod player get level_cap @s$(x)" % CAP,
               "execute unless score @s %s matches 1.. run return run tellraw @s %s" % (CAP, text(m["cap_unread"], "gold")),
               "execute if score @s %s matches %d.. run return run tellraw @s %s" % (CAP, top + 1, text(m["cap_closed"], "gold")),
               "execute store result storage %s req.cap int 1 run scoreboard players get @s %s" % (STORAGE, CAP)]
            + slot_read(doc)
            + ["execute if score #lv %s = @s %s run return run tellraw @s %s" % (SCORE, CAP, text(m["slot_at_cap"], "gold")),
               "execute if score #lv %s > @s %s run return run tellraw @s %s" % (SCORE, CAP, text(m["slot_above_cap"], "gold"))]
            + payment(doc, price)
            + ["# the edit, to exactly the cap read above; a slot that does not read back at the cap is refunded",
               "scoreboard players set #done %s 0" % SCORE,
               "execute store result score #done %s run function %s with storage %s req" % (SCORE, fn_id("raise/apply"), STORAGE),
               "execute unless score #done %s matches 1 run function %s with storage %s charge" % (SCORE, fn_id("refund"), STORAGE),
               "execute unless score #done %s matches 1 run return run tellraw @s %s"
               % (SCORE, text(fill(m["refunded"], price=price), "red")),
               "tellraw @s %s" % scored(m["raised"], "@s", CAP, "cap", "green", price=price)])


def raise_apply():
    return ["# macro: $(slot), and $(cap), the score raise/run read from rctmod a moment ago. Returns 1 when the slot",
            "# reads back at exactly that level",
            "$pokemoneditother @s $(slot) level=$(cap)",
            "$return run testpartyslot @s $(slot) level=$(cap)"]


def stat_run(doc, key, price, done_key, apply_rel, header):
    svc, m = doc["services"][key], doc["messages"]
    done = fill(m[done_key].replace("{spread}", "$(name)").replace("{stat}", "$(name)"), price=price)
    return (["# Generated by tools/training_services.py from data/training_services.json: %s" % header,
             "# As the player, from a keeper's dialogue. Macro: $(slot), $(props) and $(name), written by the slot option."]
            + cooldown_check() + gate_check(doc, svc) + slot_read(doc) + payment(doc, price)
            + ["function %s with storage %s req" % (fn_id(apply_rel), STORAGE),
               "$tellraw @s %s" % text(done, "green")])


def ev_apply():
    return ["# macro: $(slot) and $(props). All six to 0 in one command first: EVs.canSet refuses a set past 510 and a",
            "# set names only the stats it lists (paid-services note A1)",
            "$pokemoneditother @s $(slot) %s" % " ".join("%s_ev=0" % s for s in STATS),
            "$pokemoneditother @s $(slot) $(props)"]


def iv_apply():
    return ["# macro: $(slot) and $(props), the stats bought at their value",
            "$pokemoneditother @s $(slot) $(props)"]


def ev_props(spread):
    return " ".join("%s_ev=%d" % (s, spread["evs"][s]) for s in STATS if s in spread["evs"])


def iv_props(stats, value):
    return " ".join("%s_iv=%d" % (s, value) for s in stats)


def wrapper(run_rel, slot, **extra):
    parts = ["slot:%d" % slot, 'x:""'] + ["%s:%s" % (k, snbt_str(v)) for k, v in extra.items()]
    return ["# a keeper's option: slot %d" % slot,
            "data modify storage %s req set value {%s}" % (STORAGE, ",".join(parts)),
            "function %s with storage %s req" % (fn_id(run_rel), STORAGE)]


def iv_options(doc):
    """[(option id, display name, stats, price)] for the IV page."""
    svc = doc["services"]["iv"]
    per = int(svc["price_per_stat"])
    out = [(s, STAT_NAMES[s], (s,), per) for s in STATS]
    if svc.get("all_six"):
        out.append(("all", "every stat", STATS, per * len(STATS)))
    return out


def functions(doc):
    files = {}
    files[fn_path("load")] = ["# the services' scores: the balance read, the cap read, and each player's click cooldown",
                              "scoreboard objectives add %s dummy" % SCORE, "scoreboard objectives add %s dummy" % CAP,
                              "scoreboard objectives add %s dummy" % COOLDOWN]
    files[fn_path("charge")] = ["# the blackout charge's macro, proven in game (EXP-042 run 1)", "$cobbledollars remove @s $(amount)"]
    files[fn_path("refund")] = ["# CobbleDollars' give, VERIFIED from the jar (EXP-040)", "$cobbledollars give @s $(amount)"]
    files[fn_path("slot_level")] = slot_level_lines(int(doc["max_level"]))
    files[fn_path("raise/run")] = raise_run(doc)
    files[fn_path("raise/apply")] = raise_apply()
    for n in SLOTS:
        files[fn_path("raise/slot%d" % n)] = wrapper("raise/run", n)
    ev = doc["services"]["ev"]
    files[fn_path("ev/run")] = stat_run(doc, "ev", int(ev["price"]), "ev_done", "ev/apply", "an EV spread")
    files[fn_path("ev/apply")] = ev_apply()
    for sp in ev["spreads"]:
        for n in SLOTS:
            files[fn_path("ev/%s/slot%d" % (sp["id"], n))] = wrapper("ev/run", n, props=ev_props(sp), name=sp["name"])
    iv = doc["services"]["iv"]
    prices = sorted({p for _, _, _, p in iv_options(doc)})
    for p in prices:
        files[fn_path("iv/run_%d" % p)] = stat_run(doc, "iv", p, "iv_done", "iv/apply", "IVs, $%d" % p)
    files[fn_path("iv/apply")] = iv_apply()
    for oid, name, stats, p in iv_options(doc):
        for n in SLOTS:
            files[fn_path("iv/%s/slot%d" % (oid, n))] = wrapper("iv/run_%d" % p, n, props=iv_props(stats, int(iv["value"])),
                                                                 name=name)
    return files


# -------------------------------------------------------------------------------------------------------- the dialogue
def conversation(doc, k):
    """(conversation, quest) for one keeper, in data/dialogue.json's and data/quests.json's shape."""
    m, svc = doc["messages"], doc["services"]
    sp = "keeper"
    transitions = []

    def slot_page(node, back, prompt, run_prefix):
        rs = []
        for n in SLOTS:
            tid = "t_%s_%d" % (node, n)
            transitions.append({"id": tid, "conditions": [],
                                "effects": [{"kind": "function", "function": fn_id("%s/slot%d" % (run_prefix, n))}]})
            rs.append({"id": "r_%s_%d" % (node, n), "text": fill(m["slot"], slot=n),
                       "actions": [{"kind": "quest_transition", "transition": tid}, {"kind": "close_dialogue"}]})
        rs.append({"id": "r_%s_back" % node, "text": m["back"], "next": back})
        return {"id": node, "kind": "choice", "speaker": sp, "text": prompt, "responses": rs}

    ivs = iv_options(doc)
    prices = dict(raise_price=svc["raise"]["price"], ev_price=svc["ev"]["price"], iv_price=svc["iv"]["price_per_stat"],
                  iv_all_price=svc["iv"]["price_per_stat"] * len(STATS))
    flag = lambda f: {"kind": "flag", "flag": f}   # noqa: E731
    hub = [{"id": "r_raise", "text": fill(m["raise_option"], **prices), "next": "raise"},
           {"id": "r_ev", "text": fill(m["ev_option"], **prices), "next": "ev", "visible_when": flag(svc["ev"]["gate"])},
           {"id": "r_iv", "text": fill(m["iv_option"], **prices), "next": "iv", "visible_when": flag(svc["iv"]["gate"])},
           {"id": "r_leave", "text": m["leave"], "actions": [{"kind": "close_dialogue"}]}]
    nodes = [{"id": "hub", "kind": "choice", "speaker": sp, "text": fill(m["greeting"], **prices), "responses": hub},
             slot_page("raise", "hub", m["raise_page"], "raise")]
    ev_rs = [{"id": "r_ev_%s" % s["id"], "text": "%s (%s)" % (s["name"], ", ".join(
        "%d %s" % (s["evs"][st], STAT_NAMES[st]) for st in STATS if st in s["evs"])), "next": "ev_%s" % s["id"]}
        for s in svc["ev"]["spreads"]]
    ev_rs.append({"id": "r_ev_back", "text": m["back"], "next": "hub"})
    nodes.append({"id": "ev", "kind": "choice", "speaker": sp, "text": m["ev_page"], "responses": ev_rs})
    for s in svc["ev"]["spreads"]:
        nodes.append(slot_page("ev_%s" % s["id"], "ev", fill(m["ev_slot_page"], spread=s["name"]), "ev/%s" % s["id"]))
    iv_rs = []
    for oid, name, stats, p in ivs:
        label = fill(m["iv_all"], **prices) if oid == "all" else "%s ($%d)" % (name, p)
        iv_rs.append({"id": "r_iv_%s" % oid, "text": label, "next": "iv_%s" % oid})
    iv_rs.append({"id": "r_iv_back", "text": m["back"], "next": "hub"})
    nodes.append({"id": "iv", "kind": "choice", "speaker": sp, "text": m["iv_page"], "responses": iv_rs})
    for oid, name, stats, p in ivs:
        nodes.append(slot_page("iv_%s" % oid, "iv", fill(m["iv_slot_page"], stat=name[0].upper() + name[1:]),
                               "iv/%s" % oid))
    kid = keeper_id(k)
    conv = {"id": "dlg_training_keeper_%s" % kid, "quest_id": QUEST, "npc_id": "npc_training_keeper_%s" % kid,
            "npc_name": k["name"], "scope": "player", "speakers": {sp: k["name"]},
            "cursor": {"progression_field": CURSOR, "initial_node": "hub"},
            "entry_rules": [{"priority": 10, "when": {"kind": "always"}, "node": "hub"}],
            "nodes": nodes}
    quest = {"id": QUEST, "progression_field_refs": [CURSOR], "transitions": transitions, "rewards": []}
    return conv, quest


# ------------------------------------------------------------------------------------------------------------ the pack
def build(doc):
    """{relative path in the pack: content (list of lines, or a JSON object)}."""
    files = {"pack.mcmeta": {"pack": {"pack_format": 48, "description":
                                      "Cobblers paid training services (generated by tools/training_services.py)"}},
             "data/minecraft/tags/function/load.json": {"values": [fn_id("load")]}}
    files.update(functions(doc))
    fields = {f["id"]: f for f in json.loads(
        (ROOT / "data" / "progression.json").read_text(encoding="utf-8")).get("quest_fields") or []}
    for k in seated(doc):
        conv, quest = conversation(doc, k)
        got = CD.compile_conversation(conv, {quest["id"]: quest}, fields)
        clash = [p for p in got if p in files]
        if clash:
            raise ServiceError("%s writes %s twice" % (k["ground"], clash))
        files.update(got)
    return files


def write(files, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, content in files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        body = "\n".join(content) + "\n" if isinstance(content, list) else json.dumps(content, indent=2, ensure_ascii=False) + "\n"
        f.write_text(body, encoding="utf-8", newline="\n")


# ----------------------------------------------------------------------------------------------------------- the audit
def static_problems(doc, prog, planned):
    out = []
    flags = {f["id"] for f in prog.get("flags") or []}
    fields = {f["id"]: f for f in prog.get("quest_fields") or []}
    f = fields.get(CURSOR)
    if not (f and f.get("scope") == "player" and f.get("type") == "enum" and f.get("initial") == "hub"):
        out.append("%s is not a declared player enum field with initial hub in data/progression.json" % CURSOR)
    s = doc.get("services") or {}
    for key, pk in (("raise", "price"), ("ev", "price"), ("iv", "price_per_stat")):
        v = (s.get(key) or {}).get(pk)
        if not (type(v) is int and v > 0):
            out.append("services.%s.%s must be a whole number of CobbleDollars above 0" % (key, pk))
        g = (s.get(key) or {}).get("gate")
        if g is not None and (g not in flags or g not in planned):
            out.append("services.%s.gate %r is not a declared and planned progression flag" % (key, g))
    if not (type(s.get("raise", {}).get("max_cap")) is int and 1 <= s["raise"]["max_cap"] < int(doc.get("max_level", 0))):
        out.append("services.raise.max_cap must be an integer below max_level")
    for sp in (s.get("ev") or {}).get("spreads") or []:
        evs = sp.get("evs") or {}
        if not re.fullmatch(r"[a-z_]+", sp.get("id") or "") or "\"" in (sp.get("name") or "\""):
            out.append("ev spread %r: id or name" % sp.get("id"))
        if set(evs) - set(STATS) or any(not (type(v) is int and 0 <= v <= 252) for v in evs.values()):
            out.append("ev spread %s: stats must be %s, each 0..252" % (sp.get("id"), ", ".join(STATS)))
        if sum(evs.values()) > 510:
            out.append("ev spread %s totals %d, past 510: EVs.canSet would refuse part of it" % (sp.get("id"), sum(evs.values())))
    if (s.get("iv") or {}).get("value") not in range(0, 32):
        out.append("services.iv.value must be 0..31")
    gs = grounds()
    if sorted(k.get("ground") for k in doc.get("keepers") or []) != sorted(gs):
        out.append("keepers must be exactly one per data/training_grounds.json ground")
    return out + price_rule_problems(doc)


def rule_price(doc, key, markets=None, bank=None):
    """The price price_rule gives services.<key>: the smallest multiple of round_to STRICTLY above hours_saved x the
    fight hour of the anchor leg (data/markets.json income_basis.leg_by_badge[anchor] / data/bank.json
    effort_model.max_leg_hours, the fight hour R5 already prices gathering against). None if the rule does not apply."""
    r = doc.get("price_rule") or {}
    a = (r.get("applies_to") or {}).get(key)
    if not a:
        return None
    markets = markets if markets is not None else json.loads((ROOT / "data" / "markets.json").read_text(encoding="utf-8"))
    bank = bank if bank is not None else json.loads((ROOT / "data" / "bank.json").read_text(encoding="utf-8"))
    leg = Fraction(int(markets["income_basis"]["leg_by_badge"][str(r["anchor_badge"])]))
    hour = leg / Fraction(bank["effort_model"]["max_leg_hours"])
    step = int(r["round_to"])
    return (int(Fraction(a["hours_saved"]) * hour) // step + 1) * step


def price_rule_problems(doc, markets=None, bank=None):
    """price_rule (the owner after the 2026-10-10 overnight: services against craftables, docs/mechanics/
    SERVICES_AND_CRAFTING.md): every service it names carries exactly the rule's price, so a re-measured income
    re-prices the service instead of leaving it cheap. A service the rule does not name says why in not_applied."""
    r = doc.get("price_rule")
    if not r:
        return ["no price_rule: the services' prices are not tied to what crafting saves"]
    out = []
    if not (type(r.get("anchor_badge")) is int and 1 <= r["anchor_badge"] <= 8 and type(r.get("round_to")) is int
            and r["round_to"] > 0):
        return ["price_rule: anchor_badge must be 1..8 and round_to a positive whole number"]
    s = doc.get("services") or {}
    named = set(r.get("applies_to") or {}) | set(r.get("not_applied") or {})
    for key in s:
        if key not in named:
            out.append("price_rule: services.%s is neither in applies_to nor in not_applied" % key)
    for key, a in sorted((r.get("applies_to") or {}).items()):
        field = a.get("field")
        if key not in s or field not in s[key]:
            out.append("price_rule.applies_to.%s: no services.%s.%s" % (key, key, field))
            continue
        if not (a.get("hours_saved") and a.get("why")):
            out.append("price_rule.applies_to.%s: needs hours_saved and why" % key)
            continue
        want = rule_price(doc, key, markets, bank)
        if s[key][field] != want:
            out.append("services.%s.%s is $%s; price_rule gives $%d (%s h x the leg-%d fight hour, rounded up past it "
                       "to $%d)" % (key, field, s[key][field], want, a["hours_saved"], r["anchor_badge"], r["round_to"]))
    return out


def output_problems(doc, files):
    """The generated pack, read as text: the level rule and the order of every paid run."""
    out = []
    cap_writes = [(p, l) for p, ls in files.items() if isinstance(ls, list) for l in ls if "req.cap" in l]
    if [l for _, l in cap_writes] != ["execute store result storage %s req.cap int 1 run scoreboard players get @s %s"
                                      % (STORAGE, CAP)]:
        out.append("req.cap must be written once, from the cap score: %s" % cap_writes)
    for p, ls in files.items():
        if not isinstance(ls, list):
            continue
        for l in ls:
            if "pokemoneditother" in l and re.search(r"\b(level|lvl|l)=", l) and not l.endswith("level=$(cap)"):
                out.append("%s writes a level other than the cap read: %s" % (p, l))
            if "data modify storage %s req " % STORAGE in l and re.search(r"\bcap:", l):
                out.append("%s authors a cap into the request: %s" % (p, l))
        bad = function_limits.check_lines(ls, p)
        if bad:
            out.append("%s: %s" % (p, bad[:2]))
    runs = [p for p in files if re.search(r"/(raise/run|ev/run|iv/run_\d+)\.mcfunction$", p)]
    for p in runs:
        ls = files[p]
        charge = [i for i, l in enumerate(ls) if l.startswith("function %s " % fn_id("charge"))]
        edits = [i for i, l in enumerate(ls) if "/apply " in l]
        if len(charge) != 1 or len(edits) != 1 or not charge[0] < edits[0]:
            out.append("%s: one charge, then one edit" % p)
            continue
        query = [i for i, l in enumerate(ls) if l.endswith("run cobbledollars query @s")]
        if not query or query[0] > charge[0]:
            out.append("%s: the balance is not read before the charge" % p)
    return out


def seat_problems(doc, source_root=None):
    out = []
    want = seats(doc, source_root)
    gs = grounds()
    sign = json.loads(GROUNDS.read_text(encoding="utf-8"))["sign"]["offset"]
    for k in doc["keepers"]:
        at, yaw = want[k["ground"]]
        if k.get("at") != at or k.get("yaw") != yaw:
            out.append("%s: seat %s yaw %s, the heightmap gives %s yaw %s (seat --write)" % (k["ground"], k.get("at"),
                                                                                          k.get("yaw"), at, yaw))
        s = gs[k["ground"]]["site"]
        for what, (cx, cz) in (("the Habitat Block", (s["x"], s["z"])), ("the sign", (s["x"] + sign[0], s["z"] + sign[1]))):
            if (at[0], at[2]) == (cx, cz):
                out.append("%s: the keeper stands on %s" % (k["ground"], what))
    import reapply
    others = [("npc %s" % c, p) for c, p, *_ in reapply.scene_npcs() + reapply.npcs()]
    try:
        import ferries
        others += [("ferryman %s" % c, p) for c, p, _ in ferries.npc_placements(ferries.load())]
    except Exception as e:  # noqa: BLE001 - reported, not swallowed
        out.append("could not list the ferrymen to space against: %s" % e)
    for c, p, *_ in npc_placements(doc):
        for what, q in others:
            if math.dist(p, q) < NPC_RADIUS:
                out.append("%s at %s is within %.1f of %s at %s" % (c, p, NPC_RADIUS, what, q))
    return out


def audit(doc, source_root=None):
    import progression_pack as PP
    prog = json.loads((ROOT / "data" / "progression.json").read_text(encoding="utf-8"))
    placements = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    planned = {f["id"] for f in PP.plan(prog, placements=placements)["flags"]}
    problems = static_problems(doc, prog, planned)
    if problems:
        return problems
    problems += output_problems(doc, build(doc))
    problems += seat_problems(doc, source_root)
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("seat")
    s.add_argument("--write", action="store_true")
    s.add_argument("--source-root")
    b = sub.add_parser("build")
    b.add_argument("--out", default=str(DEFAULT_OUT))
    a = sub.add_parser("audit")
    a.add_argument("--source-root")
    args = ap.parse_args(argv)
    doc = load()
    if args.cmd == "seat":
        want = seats(doc, args.source_root)
        drift = 0
        for k in doc["keepers"]:
            at, yaw = want[k["ground"]]
            if k.get("at") != at or k.get("yaw") != yaw:
                drift += 1
                print("%s: %s yaw %s -> %s yaw %s" % (k["ground"], k.get("at"), k.get("yaw"), at, yaw))
            k["at"], k["yaw"] = at, yaw
        if args.write and drift:
            DATA.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print("seats: %d keepers, %d moved%s" % (len(want), drift, " (written)" if args.write and drift else ""))
        return 1 if drift and not args.write else 0
    if args.cmd == "build":
        files = build(doc)
        write(files, args.out)
        print("training services: %d files, %d keepers -> %s" % (len(files), len(seated(doc)), args.out))
        return 0
    problems = audit(doc, args.source_root)
    for p in problems:
        print("PROBLEM %s" % p)
    print("training services audit: %d problem(s)" % len(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

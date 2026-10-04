#!/usr/bin/env python
"""The level-cap catch block: a ball thrown at a Pokemon over the thrower's RCT level cap breaks free, from
data/level_cap.json, as the world pack build/datapacks/cobblers_levelcap.

The trap it closes (docs/STATE.md "The level-cap trap"; EXP-035 row 13): rctmod stops experience at the cap but not
catching, and refuses every trainer battle while a party member is over the cap, so a player who catches something
strong is locked out of the next gym. The owner, 2026-09-28: block catching above the cap entirely.

How (docs/research/notes/level-cap-catch-block.md, every hook read in source, the chain not yet run):

  data/cobblemon/callbacks/poke_ball_capture_calculated/cobblers_level_cap.molang
      after the ball's own maths: a player's throw tags the target entity and runs, as the thrower and at the thrower,
      cobblers:levelcap/check; if the thrower then carries the tag cobblers.overcap, the shakes are set to 0 (it
      breaks free) and the tag is cleared. MoLang cannot read a score, so the tag carries the answer back.
  cobblers:levelcap/check
      the cap from `rctmod player get level_cap @s` (its result is the cap), the target's Pokemon.Level, the
      comparison (strictly over, as rctmod's own refusal), the message. A cap or level it cannot read (0) allows it.

Callbacks fire only from data/cobblemon/callbacks/<event>/, under a cobblers_ file name (.claude/rules/datapacks.md).
The rctmod line is a macro: a mod's command written plainly in a function may be parsed at server start before it is
usable, as `spawnpokemonat` is (EXP-046); a macro line is parsed when it runs.

  python tools/levelcap_pack.py      # -> build/datapacks/cobblers_levelcap (world-local: a callback acts on its own)
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "level_cap.json"
OUT = ROOT / "build" / "datapacks" / "cobblers_levelcap"
NS = "cobblers"
TARGET, OVER = "cobblers.lc_target", "cobblers.overcap"
CAP, LV = "cobblers.lc_cap", "cobblers.lc_lv"
CLOCK, PARTY_OVER, TOLD = "cobblers.lc_clock", "cobblers.party_overcap", "cobblers.oc_told"


def party_notice_files(doc):
    """The over-cap NOTICE (data/level_cap.json party_notice): tell a player standing near any rctmod trainer, once
    per approach, that their party is over their cap and so no trainer will battle them.

    rctmod's own refusal is a dialog line (over_level_cap) said only when the player interacts; a trainer with
    forceBattleOnSight simply never engages, and nothing names the cap. Every party_notice.period_ticks, each player
    within party_notice.radius of an rctmod:trainer entity (every trainer: seated, spawner-made gym leaders, the
    League's, rctmod's own wanderers) is checked:

      the cap      `rctmod player get level_cap @s` on a macro line (EXP-046: a plain mod-command line parsed at
                   server start can be inert until a /reload; the `$(x)` argument makes it a macro line, as check does)
      the party    runmolang, with the cap rendered into the expression: q.player.party.highest_level > cap, the same
                   strictly-over test rctmod's canBattleAgainst makes on the same quantity (the party's highest level)
      the answer   a tag, set in one branch and cleared in the other, so the latest answer stands even if
                   q.run_command were ever deferred
    and a tellraw with the cap (a score component) to an over-cap player not yet told on this approach. Leaving every
    trainer's radius, or getting under the cap, re-arms it.

    What it does NOT do: name the Pokemon (the party screen shows the levels; a get_pokemon slot is a struct or 0, and
    comparing it is unproven); speak for a player who is not near a trainer; catch rctmod's other refusals.
    """
    n = doc.get("party_notice")
    if not n:
        return {}
    color = n.get("color", "gold")
    msg = json.dumps(["", {"text": n["text"], "color": color},
                      {"score": {"name": "@s", "objective": CAP}, "color": color},
                      {"text": n.get("text_after", ""), "color": color}])
    radius, period = int(n["radius"]), int(n["period_ticks"])
    near = "@e[type=rctmod:trainer,distance=..%d]" % radius
    mol = ("(q.player.party.highest_level > $(cap)) ? { q.run_command('tag ' + q.player.uuid + ' add %s'); } : "
           "{ q.run_command('tag ' + q.player.uuid + ' remove %s'); };" % (PARTY_OVER, PARTY_OVER))
    return {
        "data/%s/function/levelcap/tick.mcfunction" % NS: "\n".join([
            "scoreboard players add #clock %s 1" % CLOCK,
            "execute if score #clock %s matches %d.. run function %s:levelcap/sweep" % (CLOCK, period, NS),
            ""]),
        "data/%s/function/levelcap/sweep.mcfunction" % NS: "\n".join([
            "# every %d ticks: an over-cap party near any rctmod trainer is told why no trainer will battle it" % period,
            "scoreboard players set #clock %s 0" % CLOCK,
            "execute as @a[tag=%s] at @s unless entity %s run tag @s remove %s" % (TOLD, near, TOLD),
            'execute as @a at @s if entity %s run function %s:levelcap/party_check {x:""}' % (near, NS),
            ""]),
        "data/%s/function/levelcap/party_check.mcfunction" % NS: "\n".join([
            "# as and at a player near an rctmod trainer: is the party strictly over the RCT level cap?",
            "scoreboard players set @s %s 0" % CAP,
            "$execute store result score @s %s run rctmod player get level_cap @s$(x)" % CAP,
            "# a cap that did not read (0: RCT still loading, or the command failed) says nothing",
            "execute unless score @s %s matches 1.. run tag @s remove %s" % (CAP, PARTY_OVER),
            "execute unless score @s %s matches 1.. run return 0" % CAP,
            "execute store result storage %s:levelcap cap int 1 run scoreboard players get @s %s" % (NS, CAP),
            "function %s:levelcap/party_compare with storage %s:levelcap" % (NS, NS),
            "execute unless entity @s[tag=%s] run tag @s remove %s" % (PARTY_OVER, TOLD),
            "execute if entity @s[tag=%s,tag=!%s] run tellraw @s %s" % (PARTY_OVER, TOLD, msg),
            "tag @s[tag=%s] add %s" % (PARTY_OVER, TOLD),
            ""]),
        "data/%s/function/levelcap/party_compare.mcfunction" % NS: "\n".join([
            "# macro: $(cap) is the player's RCT level cap; Cobblemon's runmolang binds q.player to @s",
            '$runmolang "%s" @s' % mol,
            ""]),
        "data/minecraft/tags/function/tick.json": json.dumps({"values": ["%s:levelcap/tick" % NS]}) + "\n",
    }


def files(doc):
    msg = json.dumps({"text": doc["message"], "color": doc.get("message_color", "red")})
    return {
        "data/cobblemon/callbacks/poke_ball_capture_calculated/cobblers_level_cap.molang": "\n".join([
            "'Generated by tools/levelcap_pack.py from data/level_cap.json. A ball a player throws at a Pokemon over their RCT';",
            "'level cap breaks free (the owner, 2026-09-28). The answer comes back as a tag: MoLang cannot read a score.';",
            "t.th = q.thrower;",
            "t.th.is_player ? {",
            "  t.pk = q.pokemon;",
            "  t.pk.add_tag('%s');" % TARGET,
            "  q.run_command('execute as ' + t.th.uuid + ' at @s run function %s:levelcap/check {x:\"\"}');" % NS,
            "  t.th.has_tag('%s') ? {" % OVER,
            "    q.set_shakes(0);",
            "    t.th.remove_tag('%s');" % OVER,
            "  };",
            "};",
            ""]),
        "data/%s/function/levelcap/check.mcfunction" % NS: "\n".join([
            "# as and at the thrower, from the poke_ball_capture_calculated callback: is the target over my cap?",
            "tag @s remove %s" % OVER,
            "$execute store result score @s %s run rctmod player get level_cap @s$(x)" % CAP,
            "scoreboard players set @s %s 0" % LV,
            "execute store result score @s %s run data get entity @e[type=cobblemon:pokemon,tag=%s,limit=1,sort=nearest] Pokemon.Level"
            % (LV, TARGET),
            "tag @e[type=cobblemon:pokemon,tag=%s] remove %s" % (TARGET, TARGET),
            "# strictly over, as rctmod's own refusal counts; a cap or a level that did not read (0) lets the catch through",
            "execute if score @s %s matches 1.. if score @s %s matches 1.. if score @s %s > @s %s run tag @s add %s"
            % (CAP, LV, LV, CAP, OVER),
            "execute if entity @s[tag=%s] run tellraw @s %s" % (OVER, msg),
            ""]),
        "data/%s/function/levelcap/load.mcfunction" % NS: "\n".join([
            "scoreboard objectives add %s dummy" % CAP,
            "scoreboard objectives add %s dummy" % LV,
            "scoreboard objectives add %s dummy" % CLOCK,
            ""]),
        "data/minecraft/tags/function/load.json": json.dumps({"values": ["%s:levelcap/load" % NS]}) + "\n",
        **party_notice_files(doc),
        "pack.mcmeta": json.dumps({"pack": {"pack_format": 48, "description":
                                   "Cobblers: no catching over the level cap (tools/levelcap_pack.py)"}}, indent=2) + "\n",
    }


def main():
    doc = json.loads(DATA.read_text(encoding="utf-8"))
    if OUT.exists():
        shutil.rmtree(OUT)
    for rel, text in files(doc).items():
        p = OUT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

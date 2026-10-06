#!/usr/bin/env python
"""Generate the Hoopa cradle pack from data/hoopa_cradle.json: one catchable Hoopa per player, after the release.

The owner, 2026-10-06: Hoopa is CATCHABLE after the Rift release. It appears at the cradle when the release runs,
once per player, level 60, and is back if fainted or fled from until that player has caught it.

THE WIRING. The release is data/dialogue.json dlg_main_relic_hall_release release_001, which runs data/quests.json
unlock_league_after_rift_resolution; that transition's FIRST effect grants cobblers:flag/rift_crisis_resolved to the
releasing player. This pack's keeper reads that grant per player (data/hoopa_cradle.json wired_to says why it is not
an effect on the transition itself), the residents' keeper's `appears_after` gate made per player with the arena's
owner score.

What it emits (namespace cobblers, folder hoopa_cradle/):

  load        the objectives, then the keeper's schedule
  keeper      every period_ticks: tend each eligible player standing in the cradle; hold each Hoopa on its leash
  tend        as one eligible player: their number; their Hoopa present -> nothing; never had one -> appear now;
              missing -> the clock starts, and after respawn_after_ticks -> appear
  appear      as the player: spawn_at (a macro, EXP-046), then bind the new wild Hoopa at the spot to this player
  bind        as the new Hoopa: tagged, owned (hp.own = the player's hp.id), PersistenceRequired
  hold        as a Hoopa: back on the spot when it has wandered past the leash
  ball_check  as a thrower whose ball struck a tagged Hoopa: refuse unless they own it and may still catch it
  caught      as the catcher: the caught advancement and a line of chat

and three MoLang callbacks beside Cobblemon's own (EXP-042: a callback fires only from data/cobblemon/callbacks/):
poke_ball_capture_calculated (the ball check), pokemon_captured (the catch) and nothing else.

What this does NOT cover is listed in data/hoopa_cradle.json does_not_cover.

  python tools/hoopa_cradle.py                 # write build/datapacks/cobblers_hoopa_cradle
  python tools/hoopa_cradle.py --out <dir>

Ownership: the output is generated and lives in build/ (gitignored); data/hoopa_cradle.json is the source.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import function_limits  # noqa: E402

DATA = ROOT / "data" / "hoopa_cradle.json"
RELIC = ROOT / "data" / "relic_underground.json"
QUESTS = ROOT / "data" / "quests.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_hoopa_cradle"
SCHEMA = "cobblers.hoopa_cradle/1"
PACK_FORMAT = 48
CALLBACKS = "data/cobblemon/callbacks/%s/cobblers_hoopa_cradle.molang"
RELEASE = "unlock_league_after_rift_resolution"


class HoopaError(ValueError):
    pass


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise HoopaError("%s: schema must be %s" % (path, SCHEMA))
    return doc


def problems(doc, relic=None, quests=None):
    """[problem] in the record, held against the cradle's own geometry and the release transition's first effect."""
    relic = relic if relic is not None else json.loads(RELIC.read_text(encoding="utf-8"))
    quests = quests if quests is not None else json.loads(QUESTS.read_text(encoding="utf-8"))
    bad = []
    cr = relic["geometry"]["cradle"]
    x, y, z = doc["spot"]
    cx, cz = cr["centre"]
    if math.hypot(x - cx, z - cz) > 1:
        bad.append("spot (%d, %d) is not the cradle's centre (%d, %d)" % (x, z, cx, cz))
    if y != cr["floor_y"] + 1:
        bad.append("spot y%d is not standing on the cradle's floor y%d" % (y, cr["floor_y"]))
    k = doc["keeper"]
    if k["leash"] >= cr["radius"]:
        bad.append("leash %d reaches the cradle's wall (radius %d)" % (k["leash"], cr["radius"]))
    binder = relic["geometry"]["release"]["at"]
    if math.hypot(binder[0] + 0.5 - (x + 0.5), binder[2] + 0.5 - (z + 0.5)) > k["near_radius"]:
        bad.append("the binder at %s is outside near_radius %d: the release would spawn nothing until the player "
                   "walks in" % (binder, k["near_radius"]))
    if k["period_ticks"] < 1 or k["respawn_after_ticks"] < k["period_ticks"]:
        bad.append("keeper period %d / respawn %d" % (k["period_ticks"], k["respawn_after_ticks"]))
    if not 1 <= int(doc["level"]) <= 100:
        bad.append("level %r" % doc["level"])
    if doc["catch"]["catch_radius"] < k["near_radius"]:
        bad.append("catch_radius %d is inside near_radius %d: a catch at the cradle's edge would not count"
                   % (doc["catch"]["catch_radius"], k["near_radius"]))
    # the flag this pack keys on must be what the release grants, first
    tr = None
    for q in quests.get("quests") or []:
        for t in q.get("transitions") or []:
            if t.get("id") == RELEASE:
                tr = t
    if tr is None:
        bad.append("data/quests.json has no transition %s" % RELEASE)
    else:
        want = "%s/grant" % doc["gate_flag"]
        first = (tr.get("effects") or [{}])[0]
        if first != {"kind": "function", "function": want}:
            bad.append("%s's first effect is %r, not the grant of %s this pack keys on" % (RELEASE, first, doc["gate_flag"]))
    return bad


def _fn(doc, name):
    return "%s:%s/%s" % (doc["namespace"], doc["folder"], name)


def _xyz(doc):
    x, y, z = doc["spot"]
    return "%.1f %d %.1f" % (x + 0.5, y, z + 0.5)


def _species_sel(doc):
    return 'nbt={Pokemon:{Species:"%s",PokemonOriginalTrainerType:"NONE"}}' % doc["species"]


def functions(doc):
    o, t, k, m = doc["objectives"], doc["tags"], doc["keeper"], doc["message"]
    ID, OWN, GONE, HAD, W = o["id"], o["own"], o["gone"], o["had"], o["work"]
    head = "# Generated by tools/hoopa_cradle.py from data/hoopa_cradle.json; never edit (build/ is regenerated)."
    at = _xyz(doc)
    dim = doc["dimension"]
    eligible = "advancements={%s=true,%s=false}" % (doc["gate_flag"], doc["caught_advancement"])
    sp = doc["species"].split(":", 1)[1]
    say = lambda key, colour: "tellraw @s %s" % json.dumps({"text": m[key], "color": colour, "italic": True},  # noqa: E731
                                                            ensure_ascii=False)
    out = {}
    out["load"] = [head] + ["scoreboard objectives add %s dummy" % v for v in (ID, OWN, GONE, HAD, W)] + [
        "schedule function %s %dt replace" % (_fn(doc, "keeper"), k["period_ticks"])]
    out["keeper"] = [
        head,
        "# Every %d ticks. Nothing happens unless a player is in the cradle." % k["period_ticks"],
        "execute store result score #now %s run time query gametime" % W,
        "execute in %s positioned %s as @a[distance=..%d,gamemode=!spectator,%s] at @s run function %s"
        % (dim, at, k["near_radius"], eligible, _fn(doc, "tend")),
        "execute in %s positioned %s as @e[type=cobblemon:pokemon,tag=%s,distance=..%d] unless entity @s[distance=..%d] "
        "run function %s" % (dim, at, t["hoopa"], k["near_radius"] * 3, k["leash"], _fn(doc, "hold")),
        "schedule function %s %dt replace" % (_fn(doc, "keeper"), k["period_ticks"]),
    ]
    out["tend"] = [
        head,
        "# As one player who has released Hoopa (%s) and not caught it, standing in the cradle." % doc["gate_flag"],
        "execute unless score @s %s matches 1.. run scoreboard players add #next %s 1" % (ID, ID),
        "execute unless score @s %s matches 1.. run scoreboard players operation @s %s = #next %s" % (ID, ID, ID),
        "scoreboard players operation #me %s = @s %s" % (ID, ID),
        "scoreboard players set #have %s 0" % W,
        "execute as @e[type=cobblemon:pokemon,tag=%s] if score @s %s = #me %s run scoreboard players set #have %s 1"
        % (t["hoopa"], OWN, ID, W),
        "# present: the clock is cleared and nothing else happens",
        "execute if score #have %s matches 1 run scoreboard players reset @s %s" % (W, GONE),
        "execute if score #have %s matches 1 run return 0" % W,
        "# never had one: the release has just run (or ran before this pack was installed). It appears now",
        "execute unless score @s %s matches 1 run return run function %s" % (HAD, _fn(doc, "appear")),
        "# had one, now missing (fainted, fled from, removed): the clock starts on the first pass that misses it",
        "execute unless score @s %s matches -2147483648.. run scoreboard players operation @s %s = #now %s"
        % (GONE, GONE, W),
        "scoreboard players operation #d %s = #now %s" % (W, W),
        "scoreboard players operation #d %s -= @s %s" % (W, GONE),
        "execute if score #d %s matches ..%d run return 0" % (W, k["respawn_after_ticks"] - 1),
        "function %s" % _fn(doc, "appear"),
    ]
    out["appear"] = [
        head,
        "# As the player: their own Hoopa at the spot, then bound to them by score.",
        "function %s {x:\"%.1f\",y:%d,z:\"%.1f\",species:\"%s\",props:\"level=%d\"}"
        % (_fn(doc, "spawn_at"), doc["spot"][0] + 0.5, doc["spot"][1], doc["spot"][2] + 0.5, sp, int(doc["level"])),
        "execute in %s positioned %s as @e[type=cobblemon:pokemon,tag=!%s,distance=..2,%s,limit=1,sort=nearest] "
        "run function %s" % (dim, at, t["hoopa"], _species_sel(doc), _fn(doc, "bind")),
        "scoreboard players set @s %s 1" % HAD,
        "scoreboard players reset @s %s" % GONE,
        say("appear", "light_purple"),
    ]
    out["spawn_at"] = [
        "# a macro, so the mod's command is parsed when it runs (EXP-046, .claude/rules/datapacks.md)",
        "$spawnpokemonat $(x) $(y) $(z) $(species) $(props)",
    ]
    out["bind"] = [
        head,
        "# As the new wild Hoopa: ours by tag, its owner's number on hp.own, kept from the despawner (EXP-041).",
        "tag @s add %s" % t["hoopa"],
        "scoreboard players operation @s %s = #me %s" % (OWN, ID),
        "data merge entity @s {PersistenceRequired:1b}",
    ]
    out["hold"] = [
        head,
        "# As a Hoopa past its leash of %d: back on the spot." % k["leash"],
        "tp @s %s" % at,
    ]
    out["ball_check"] = [
        head,
        "# As a thrower whose ball struck a Hoopa tagged %s (the capture callback tags it %s first)." % (t["hoopa"], t["hit"]),
        "scoreboard players set #ok %s 0" % W,
        "scoreboard players set #thr %s -1" % ID,
        "execute if score @s %s matches 1.. run scoreboard players operation #thr %s = @s %s" % (ID, ID, ID),
        "# the owner, still eligible, may catch it",
        "execute if entity @s[%s] as @e[type=cobblemon:pokemon,tag=%s,limit=1] if score @s %s = #thr %s run "
        "scoreboard players set #ok %s 1" % (eligible, t["hit"], OWN, ID, W),
        "# fallback (data/hoopa_cradle.json catch.fallback): no Hoopa took the hit tag, so judge the thrower alone",
        "execute unless entity @e[type=cobblemon:pokemon,tag=%s] if entity @s[%s] run scoreboard players set #ok %s 1"
        % (t["hit"], eligible, W),
        "execute if score #ok %s matches 0 run tag @s add %s" % (W, t["refuse"]),
        "execute if score #ok %s matches 0 run %s" % (W, say("refuse", "gray")),
    ]
    out["caught"] = [
        head,
        "# As the player who caught a Hoopa within %d of the spot." % doc["catch"]["catch_radius"],
        "execute unless entity @s[advancements={%s=true}] run %s" % (doc["caught_advancement"], say("caught", "light_purple")),
        "advancement grant @s only %s" % doc["caught_advancement"],
    ]
    return out


def callbacks(doc):
    """The two MoLang callbacks. No apostrophe inside a comment string: MoLang strings are single-quoted."""
    t = doc["tags"]
    x, y, z = doc["spot"]
    near = "execute as ' + q.player.uuid + ' at @s if entity @s[x=%d,y=%d,z=%d,distance=..%d] run function %s" % (
        x, y, z, doc["catch"]["catch_radius"], _fn(doc, "caught"))
    return {
        CALLBACKS % "poke_ball_capture_calculated": "\n".join([
            "'Generated by tools/hoopa_cradle.py from data/hoopa_cradle.json. A ball at a cradle Hoopa: it holds only for';",
            "'its owner, who has released Hoopa and not caught one. Any other ball breaks free.';",
            "t.pk = q.pokemon;",
            "t.th = q.thrower;",
            "t.pk.has_tag('%s') ? {" % t["hoopa"],
            "  t.th.is_player ? {",
            "    t.pk.add_tag('%s');" % t["hit"],
            "    q.run_command('execute as ' + t.th.uuid + ' at @s run function %s');" % _fn(doc, "ball_check"),
            "    t.pk.remove_tag('%s');" % t["hit"],
            "    t.th.has_tag('%s') ? {" % t["refuse"],
            "      q.set_shakes(0);",
            "      t.th.remove_tag('%s');" % t["refuse"],
            "    };",
            "  };",
            "};", ""]),
        CALLBACKS % "pokemon_captured": "\n".join([
            "'Generated by tools/hoopa_cradle.py from data/hoopa_cradle.json. A Hoopa caught near the cradle: the catcher';",
            "'has had theirs. A Hoopa caught anywhere else (a raid den) does not count.';",
            "t.id = q.pokemon.species.identifier;",
            "t.id == '%s' ? {" % doc["species"],
            "  q.run_command('%s');" % near,
            "};", ""]),
    }


def advancement():
    return {"criteria": {"granted": {"trigger": "minecraft:impossible"}}, "requirements": [["granted"]]}


def build(doc, relic=None, quests=None):
    bad = problems(doc, relic, quests)
    if bad:
        raise HoopaError("data/hoopa_cradle.json: " + "; ".join(bad))
    ns = doc["namespace"]
    adv_ns, adv_path = doc["caught_advancement"].split(":", 1)
    files = {
        "pack.mcmeta": json.dumps({"pack": {"pack_format": PACK_FORMAT,
                                            "description": "Cobblers: one catchable Hoopa per player at the cradle "
                                                           "(tools/hoopa_cradle.py)"}}, indent=2) + "\n",
        "data/minecraft/tags/function/load.json": json.dumps({"values": [_fn(doc, "load")]}, indent=2) + "\n",
        "data/%s/advancement/%s.json" % (adv_ns, adv_path): json.dumps(advancement(), indent=2) + "\n",
    }
    for name, lines in functions(doc).items():
        rel = "data/%s/function/%s/%s.mcfunction" % (ns, doc["folder"], name)
        refused = function_limits.check_lines(lines, rel)
        if refused:
            for n, cmd, why in refused:
                print("REFUSED %s line %d: %s\n   %s" % (rel, n, why, cmd))
            raise SystemExit("%s: %d command(s) the server would refuse; nothing written" % (rel, len(refused)))
        files[rel] = "\n".join(lines) + "\n"
    files.update(callbacks(doc))
    return files


def write(files, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in files.items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--data", default=str(DATA))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    a = p.parse_args(argv)
    files = build(load(a.data))
    write(files, a.out)
    print("cobblers_hoopa_cradle: %d files -> %s" % (len(files), a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())

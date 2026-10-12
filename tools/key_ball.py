#!/usr/bin/env python
"""Generate the Beast Ball key pack from data/key_ball.json: the one ball that catches a dungeon boss.

The owner's decisions of 2026-10-08 are data/key_ball.json `decision`; the hooks, rates and leaks are
docs/research/notes/beast-ball-key-1.8.0.md (VERIFIED from the Cobblemon 1.8.0 jar, nothing run in game).

THE RULE. A dungeon boss carries the entity tag data/key_ball.json `tag`, put on it at spawn by its own tool (today
tools/entei_boss.py slot/s<k>/bind). Then two MoLang callbacks, beside Cobblemon's own files under a cobblers_ name
(EXP-042: a callback fires only from data/cobblemon/callbacks/<event>/):

  pokemon_catch_rate_calculated   a key ball (cobblemon:beast_ball) at a tagged boss: the rate x `multiplier`. Never
                                  fired for a Master Ball (it is guaranteed before the rate is asked for). NOT for a
                                  boss that also carries `native_tag` (an Ultra Beast): the jar's own Beast Ball
                                  modifier already gives it x5, and ours on top was x25 (data/key_ball.json native_why).
                                  A boss tool takes its tags from bind_tag_lines(species), which adds `native_tag` for
                                  every species the jar labels `native_label`; boss_problems sweeps every spawn line.
  poke_ball_capture_calculated    any other ball at a tagged boss: set_shakes(0), so it breaks free, and, thrown by a
                                  player, key_ball/refused runs as them with the ball's id: one of the same ball back
                                  (not in creative) and the refusal line. Fired after every ball's maths, the Master
                                  Ball's included, so it stops a Master Ball too.

Both scripts only ever LOWER a chance or REFUSE: neither calls set_critical_capture or sets a successful shake count.
The level cap (tools/levelcap_pack.py), the Hoopa cradle (tools/hoopa_cradle.py) and Ursaluna (tools/ursaluna_cave.py)
run their own poke_ball_capture_calculated scripts in the same folder and also only refuse, so a refusal by any of them
wins whatever order Cobblemon runs the files in, and the order needs no contract. No other generated pack and no jar
in the server snapshot ships a pokemon_catch_rate_calculated script, so the x5 is the only rate change there
(CobbleCuisine's catch food changes the same rate in Kotlin and stacks: accepted, research note section 7).

THE RECIPE. The jar's beast_ball recipe (makes 8) and its unlock advancement are written back at their own paths
holding only Fabric API's `fabric:load_conditions` with a condition that never passes (data/key_ball.json
recipe_off.mechanism): the server skips both at load.

What it emits (namespace cobblers, folder key_ball/):
  data/cobblemon/callbacks/<event>/cobblers_key_ball.molang    the two callbacks
  data/cobblers/function/key_ball/refused.mcfunction           the refund and the line (a macro: $(ball))
  data/cobblemon/recipe/beast_ball.json, data/cobblemon/advancement/recipes/balls/beast_ball.json   closed
No load or tick tag, no blocks, no reapply step: self-driving, world-local (tools/reapply.py EXCLUDED, WORLD_LOCAL).

What it does NOT cover is data/key_ball.json does_not_cover: an untagged Pokemon is never touched, whatever its
species; the level cap's own refusal of a Beast Ball is not refunded; other Beast Ball sources (loot) stay open.

  python tools/key_ball.py                 # check, then write build/datapacks/cobblers_key_ball
  python tools/key_ball.py --check         # check only: the record, and every boss tool's bind adds the tag
  python tools/key_ball.py --out <dir>

Ownership: the output is generated and lives in build/ (gitignored); data/key_ball.json is the source.
"""
from __future__ import annotations

import argparse
import importlib
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import function_limits  # noqa: E402

DATA = ROOT / "data" / "key_ball.json"
BLACKOUT = ROOT / "data" / "blackout.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_key_ball"
SCHEMA = "cobblers.key_ball/1"
PACK_FORMAT = 48  # Minecraft 1.21.1
NS = "cobblers"
CALLBACK = "data/cobblemon/callbacks/%s/cobblers_key_ball.molang"
REFUSED = "%s:key_ball/refused" % NS
TAG_RE = re.compile(r"^[A-Za-z0-9_.+-]{1,64}$")          # an entity tag: no spaces, no quotes
ID_RE = re.compile(r"^[a-z0-9_.-]+:[a-z0-9_./-]+$")
NEVER = {"condition": "fabric:not", "value": {"condition": "fabric:true"}}
JAR = Path("C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods/Cobblemon-fabric-1.8.0+1.21.1.jar")
# a spawn line of the dungeon engine's wild macro (tools/dungeon.py wild_at): species:"<id>", then a line binding it
SPAWN_SPECIES = re.compile(r'function [a-z0-9_.-]+:[a-z0-9_./-]*wild_at \{[^}]*species:"([a-z0-9_-]+)"')
RUN_FUNCTION = re.compile(r"run function ([a-z0-9_.-]+):([a-z0-9_./-]+)$")


class KeyBallError(ValueError):
    pass


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise KeyBallError("%s: schema %r, expected %r" % (path, doc.get("schema"), SCHEMA))
    return doc


def boss_tag(doc=None):
    """The shared tag every dungeon boss carries. A boss tool calls this at its bind, so the name has one owner."""
    return (doc if doc is not None else load())["tag"]


_NATIVE = {}


def jar_native_species(label, jar=JAR):
    """sorted species the Cobblemon jar's own species files label `label`, or None when the jar is not here. Read
    here and not through tools/dungeon_prize.py, so the check does not share the boss tool's reader."""
    key = (label, str(jar))
    if key not in _NATIVE:
        if not Path(jar).is_file():
            _NATIVE[key] = None
        else:
            import zipfile
            out = []
            with zipfile.ZipFile(jar) as z:
                for n in z.namelist():
                    if n.startswith("data/cobblemon/species/") and n.endswith(".json"):
                        try:
                            j = json.loads(z.read(n))
                        except ValueError:
                            continue
                        if label in (j.get("labels") or []):
                            out.append(n.rsplit("/", 1)[1][:-5])
            _NATIVE[key] = sorted(out)
    return _NATIVE[key]


def native_species(doc=None):
    """The species the key ball's own jar modifier already favours (data/key_ball.json native_label): the jar's list,
    else the record's snapshot where the jar is not on this machine."""
    doc = doc if doc is not None else load()
    got = jar_native_species(doc["native_label"])
    return set(got if got is not None else doc["native_species_snapshot"])


def bind_tag_lines(species, doc=None):
    """The tag lines a boss tool's bind runs for a key boss of `species`: the key tag, and for an Ultra Beast (the jar's
    native_label) the native tag, so the rate callback leaves the jar's own x5 alone (data/key_ball.json native_why)."""
    doc = doc if doc is not None else load()
    sp = str(species).split(":")[-1]
    out = ["tag @s add %s" % doc["tag"]]
    if sp in native_species(doc):
        out.append("tag @s add %s" % doc["native_tag"])
    return out


def problems(doc, blackout=None):
    """[problem] in the record itself and against the blackout's claim list."""
    bad = []
    if not TAG_RE.match(str(doc.get("tag", ""))):
        bad.append("tag %r is not an entity tag" % doc.get("tag"))
    if not ID_RE.match(str(doc.get("key_ball", ""))):
        bad.append("key_ball %r is not an item id" % doc.get("key_ball"))
    m = doc.get("multiplier")
    if isinstance(m, bool) or not isinstance(m, (int, float)) or m <= 1:
        bad.append("multiplier %r: the key must raise the rate (> 1)" % (m,))
    if not TAG_RE.match(str(doc.get("native_tag", ""))) or doc.get("native_tag") == doc.get("tag"):
        bad.append("native_tag %r is not an entity tag distinct from tag (the Ultra Beast x25 guard)" % doc.get("native_tag"))
    if doc.get("native_label") != "ultra_beast":
        bad.append("native_label %r: the jar's Beast Ball is LabelModifier(5.0, true, \"ultra_beast\")" % doc.get("native_label"))
    snap = doc.get("native_species_snapshot")
    if not (isinstance(snap, list) and snap and all(isinstance(s, str) for s in snap)):
        bad.append("native_species_snapshot: the jar's ultra_beast species, a non-empty list")
    else:
        jar = jar_native_species(doc.get("native_label") or "")
        if jar is not None and sorted(snap) != jar:
            bad.append("native_species_snapshot differs from the jar's %s list: %s" % (
                doc.get("native_label"), ", ".join(sorted(set(snap) ^ set(jar)))))
    msg = doc.get("message") or ""
    if not msg:
        bad.append("no refusal message")
    if "'" in msg:
        bad.append("the message holds an apostrophe; it is carried in a JSON text, keep it plain")
    hint = [w for w in ("beast", "ultra", "cinderlee", "crater", "buy", "sold", "shop") if w in msg.lower()]
    if hint:
        bad.append("the message hints at the key (%s): the owner wants it to name nothing" % ", ".join(hint))
    if "Even a Master Ball will not close on it." not in msg:
        bad.append("the message lost the owner's 'Even a Master Ball will not close on it.'")
    ref = doc.get("refund") or {}
    if ref.get("ball_count") != 1:
        bad.append("refund.ball_count %r: one refused throw gives back exactly one ball" % ref.get("ball_count"))
    if ref.get("skip_gamemode") != "creative":
        bad.append("refund.skip_gamemode must be creative (a creative throw consumes nothing)")
    ro = doc.get("recipe_off") or {}
    if doc.get("key_ball") not in (ro.get("recipes") or []):
        bad.append("recipe_off.recipes does not close the key ball's own recipe %r" % doc.get("key_ball"))
    for rid in (ro.get("recipes") or []) + (ro.get("advancements") or []):
        if not ID_RE.match(rid):
            bad.append("recipe_off id %r" % rid)
    if ro.get("condition") != NEVER:
        bad.append("recipe_off.condition must be the never-passing %s" % json.dumps(NEVER))
    if not doc.get("bosses"):
        bad.append("no bosses: nothing carries the tag")
    for b in doc.get("bosses") or []:
        if not (ROOT / b.get("tool", "")).is_file() or not (ROOT / b.get("data", "")).is_file():
            bad.append("boss %s: tool or data file missing" % b.get("id"))
    blackout = blackout if blackout is not None else json.loads(BLACKOUT.read_text(encoding="utf-8"))
    claims = blackout.get("claims") or {}
    for cat in ("balls", "medicine", "consumables"):
        if doc.get("key_ball") in (claims.get(cat) or []):
            bad.append("data/blackout.json claims.%s takes the key ball: it is never lost, as the Master Ball" % cat)
    return bad


def boss_problems(doc):
    """[problem] for each declared boss whose generated bind does not add the tag. Builds the boss's pack in memory
    with its own tool (module.build(module.load())); writes nothing."""
    bad = []
    want = "tag @s add %s" % doc["tag"]
    nat = "tag @s add %s" % doc["native_tag"]
    natives = native_species(doc)
    for b in doc.get("bosses") or []:
        mod = importlib.import_module(b["module"])
        files = mod.build(mod.load())
        binds = {rel: text for rel, text in files.items() if re.search(r"/bind(_native)?\.mcfunction$", rel)}
        if not binds:
            bad.append("boss %s: its pack has no bind function to tag the boss in" % b["id"])
        for rel, text in sorted(binds.items()):
            if want not in text.split("\n"):
                bad.append("boss %s: %s does not run `%s`" % (b["id"], rel, want))
            if rel.endswith("/bind_native.mcfunction") and nat not in text.split("\n"):
                bad.append("boss %s: %s does not run `%s`" % (b["id"], rel, nat))
        # the Ultra Beast sweep: every wild_at spawn line's species against the function the next line binds it with
        sweep = dict(files)
        if hasattr(mod, "key_sweep_files"):
            sweep.update(mod.key_sweep_files(mod.load()))
        bad += ["boss %s: %s" % (b["id"], p) for p in native_sweep(sweep, want, nat, natives)]
    return bad


def native_sweep(files, want, nat, natives):
    """[problem] for each spawn line (the wild_at macro, species:"x") whose bind adds the key tag and either misses the
    native tag on an Ultra Beast (x25) or carries it on anything else (x1). The bind is the function the NEXT line runs."""
    bad = []
    for rel, text in sorted(files.items()):
        lines = text.split("\n")
        for i, ln in enumerate(lines):
            m = SPAWN_SPECIES.search(ln)
            if not m:
                continue
            f = RUN_FUNCTION.search(lines[i + 1]) if i + 1 < len(lines) else None
            target = files.get("data/%s/function/%s.mcfunction" % f.groups()) if f else None
            if target is None:
                continue
            tl = target.split("\n")
            if want not in tl:
                continue
            sp = m.group(1)
            if sp in natives and nat not in tl:
                bad.append("%s spawns %s (an Ultra Beast) and binds it with the key tag but not %s: the jar's x5 and ours "
                           "would make x25" % (rel, sp, nat.split()[-1]))
            elif sp not in natives and nat in tl:
                bad.append("%s spawns %s (not an Ultra Beast) and binds it with %s: the key's x5 would be lost (x1)"
                           % (rel, sp, nat.split()[-1]))
    return bad


def callbacks(doc):
    """The two MoLang callbacks. Only == and nested ?{} (the forms the repo's other callbacks use); no apostrophe
    inside a comment string, because MoLang strings are single-quoted."""
    tag, key, mult, native = doc["tag"], doc["key_ball"], doc["multiplier"], doc["native_tag"]
    return {
        CALLBACK % "pokemon_catch_rate_calculated": "\n".join([
            "'Generated by tools/key_ball.py from data/key_ball.json. A key ball at a dungeon boss (tagged %s):';" % tag,
            "'its catch rate times %s, fed to the jar formula. Any other target or ball: untouched. Not at a boss';" % mult,
            "'also tagged %s (an Ultra Beast): the jar gives the Beast Ball x5 on those already.';" % native,
            "t.pk = q.pokemon_entity;",
            "t.pk.has_tag('%s') ? {" % tag,
            "  t.nat = 0;",
            "  t.pk.has_tag('%s') ? {" % native,
            "    t.nat = 1;",
            "  };",
            "  t.nat == 0 ? {",
            "    q.poke_ball_entity.ball_type == '%s' ? {" % key,
            "      q.set_catch_rate(q.catch_rate * %s);" % mult,
            "    };",
            "  };",
            "};", ""]),
        CALLBACK % "poke_ball_capture_calculated": "\n".join([
            "'Generated by tools/key_ball.py from data/key_ball.json. Any ball but the key at a dungeon boss (tagged';",
            "'%s) breaks free, the Master Ball too. A player who threw it gets the same ball back and a line.';" % tag,
            "'It only refuses: it never forces a catch, so the order of this folder does not matter.';",
            "t.pk = q.pokemon;",
            "t.pk.has_tag('%s') ? {" % tag,
            "  t.key = 0;",
            "  t.ball = q.poke_ball.ball_type;",
            "  t.ball == '%s' ? {" % key,
            "    t.key = 1;",
            "  };",
            "  t.key == 0 ? {",
            "    q.set_shakes(0);",
            "    t.th = q.thrower;",
            "    t.th.is_player ? {",
            "      q.run_command('execute as ' + t.th.uuid + ' at @s run function %s {ball:\"' + t.ball + '\"}');"
            % REFUSED,
            "    };",
            "  };",
            "};", ""]),
    }


def refused_lines(doc):
    ref = doc["refund"]
    msg = json.dumps({"text": doc["message"], "color": doc.get("message_color", "gray"), "italic": True})
    return [
        "# Generated by tools/key_ball.py from data/key_ball.json; never edit (build/ is regenerated).",
        "# As and at a player whose ball %s's poke_ball_capture_calculated callback has just refused at a dungeon boss" % NS,
        "# (it breaks free and Cobblemon discards it with no item). $(ball) is the ball's own id (EmptyPokeBallEntity",
        "# struct ball_type). One back, never in %s: a %s throw takes no ball (ItemStack.consume)." % (
            ref["skip_gamemode"], ref["skip_gamemode"]),
        "$execute unless entity @s[gamemode=%s] run give @s $(ball) %d" % (ref["skip_gamemode"], ref["ball_count"]),
        "tellraw @s %s" % msg,
    ]


def closed(doc):
    """{path: text} for every recipe and advancement written back closed."""
    out = {}
    body = json.dumps({"fabric:load_conditions": [doc["recipe_off"]["condition"]]}, indent=2) + "\n"
    for kind, folder in (("recipes", "recipe"), ("advancements", "advancement")):
        for rid in doc["recipe_off"][kind]:
            ns, path = rid.split(":", 1)
            out["data/%s/%s/%s.json" % (ns, folder, path)] = body
    return out


def build(doc, blackout=None, check_bosses=True):
    bad = problems(doc, blackout)
    if check_bosses and not bad:
        bad += boss_problems(doc)
    if bad:
        raise KeyBallError("data/key_ball.json: " + "; ".join(bad))
    files = {
        "pack.mcmeta": json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                            "Cobblers: the Beast Ball is the key to dungeon bosses (tools/key_ball.py)"}},
                                  indent=2) + "\n",
    }
    files.update(callbacks(doc))
    lines = refused_lines(doc)
    rel = "data/%s/function/key_ball/refused.mcfunction" % NS
    refusals = function_limits.check_lines(lines, rel)
    if refusals:
        raise KeyBallError("%s: %d command(s) the server would refuse: %s" % (rel, len(refusals), refusals))
    files[rel] = "\n".join(lines) + "\n"
    files.update(closed(doc))
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
    p.add_argument("--check", action="store_true", help="check the record and the bosses' binds; write nothing")
    a = p.parse_args(argv)
    doc = load(a.data)
    try:
        files = build(doc)
    except KeyBallError as e:
        print("PROBLEM %s" % e)
        return 1
    if a.check:
        print("key_ball: ok (%d boss tool(s) tag %s)" % (len(doc["bosses"]), doc["tag"]))
        return 0
    write(files, a.out)
    print("cobblers_key_ball: %d files -> %s" % (len(files), a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python
"""A player's own waystone: Oak gives one, once; every other way to make a waystone or a warp item is closed.

THE OWNER (2026-10-09): fast travel by waystone stays limited so travel remains part of the game; "a player's own
waystone, given by Oak once after the starter ... one per player, its crafting recipe closed ..., and its pickup on break
kept so a player who moves keeps one." data/player_waystone.json holds the decision, the gift and the list of closed
recipes; the research is its `config_facts` and `recipe_off.found`.

TWO HALVES.
  The gift is data, not code: a grant_reward_once in data/quests.json main_worldshift_reveal (transition
  grant_oak_waystone), recorded in data/rewards.json (oak_waystone), spoken in Oak's conversation
  (data/dialogue.json dlg_main_pallet_oak, nodes oak_waystone_001/002/late). tools/compile_dialogue.py turns it into the
  MoLang that gives the item and writes the claim. This tool only checks that the three records agree.
  The recipes are this tool's pack. Every recipe in the Waystones jar that makes a placeable waystone, sharestone,
  portstone or warp plate, or a warp item, and the ingredients of those, is written back at its own path holding only
  Fabric API's `fabric:load_conditions` with a condition that never passes, and so is each recipe's unlock advancement:
  exactly tools/key_ball.py's Beast Ball closure (that file's docstring and data/key_ball.json recipe_off.mechanism give
  the source reading). The pack is world-local, has no function, no tag and no step; it acts when the server loads data.

  python tools/player_waystone.py check [--jar PATH]   # the records agree; with the jar, the list is the jar's
  python tools/player_waystone.py build [--out DIR]    # check, then write build/datapacks/cobblers_player_waystone

What it does NOT cover is data/player_waystone.json does_not_cover: a town waystone broken in survival drops the same
item; a creative or operator give; a lost item has no second grant; wild and village waystones in new chunks.

Ownership: the output is generated and lives in build/ (gitignored); data/player_waystone.json is the source.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

DATA = ROOT / "data" / "player_waystone.json"
QUESTS = ROOT / "data" / "quests.json"
REWARDS = ROOT / "data" / "rewards.json"
DIALOGUE = ROOT / "data" / "dialogue.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_player_waystone"
JAR_GLOB = "waystones-fabric-*.jar"
SNAPSHOT_MODS = Path("C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05/mods")
SCHEMA = "cobblers.player_waystone/1"
PACK_FORMAT = 48  # Minecraft 1.21.1
NEVER = {"condition": "fabric:not", "value": {"condition": "fabric:true"}}
ID_RE = re.compile(r"^[a-z0-9_.-]+:[a-z0-9_./-]+$")


class WaystoneError(ValueError):
    pass


def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise WaystoneError("%s: schema %r, expected %r" % (path, doc.get("schema"), SCHEMA))
    return doc


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def jar_ids(jar):
    """({recipe ids}, {advancement ids}) the Waystones jar ships, read from the zip."""
    z = zipfile.ZipFile(jar)
    rec, adv = set(), set()
    for n in z.namelist():
        if n.startswith("data/waystones/recipe/") and n.endswith(".json"):
            rec.add("waystones:" + n[len("data/waystones/recipe/"):-5])
        if n.startswith("data/waystones/advancement/recipes/") and n.endswith(".json"):
            adv.add("waystones:" + n[len("data/waystones/advancement/"):-5])
    return rec, adv


def find_jar():
    hits = sorted(SNAPSHOT_MODS.glob(JAR_GLOB)) if SNAPSHOT_MODS.is_dir() else []
    return hits[-1] if hits else None


def problems(doc, jar=None):
    """[problem]: the record against itself, the three data files and (when a jar is given) the jar."""
    bad = []
    ro = doc.get("recipe_off") or {}
    if ro.get("condition") != NEVER:
        bad.append("recipe_off.condition must be the never-passing %s" % json.dumps(NEVER))
    for kind in ("recipes", "advancements"):
        ids = ro.get(kind) or []
        if not ids:
            bad.append("recipe_off.%s is empty" % kind)
        if len(set(ids)) != len(ids):
            bad.append("recipe_off.%s repeats an id" % kind)
        for i in ids:
            if not ID_RE.match(i) or not i.startswith("waystones:"):
                bad.append("recipe_off.%s id %r is not a waystones: id" % (kind, i))
    gift = doc.get("gift") or {}
    item = gift.get("item")
    # the item Oak gives must be placeable but not craftable: its own recipe is among those closed
    if item not in {r for r in (ro.get("recipes") or [])}:
        bad.append("the gift %r is not among the recipes closed: it would stay craftable" % item)
    if jar is not None:
        rec, adv = jar_ids(jar)
        have_r, have_a = set(ro.get("recipes") or []), set(ro.get("advancements") or [])
        if rec - have_r:
            bad.append("the jar ships recipes this list does not close: %s" % sorted(rec - have_r))
        if adv - have_a:
            bad.append("the jar ships advancements this list does not close: %s" % sorted(adv - have_a))
        if have_r - rec:
            bad.append("this list closes recipes the jar does not ship: %s" % sorted(have_r - rec))
        if have_a - adv:
            bad.append("this list closes advancements the jar does not ship: %s" % sorted(have_a - adv))
    # the three records of the gift
    claim = gift.get("claim_field")
    q = next((x for x in _json(QUESTS)["quests"] if x["id"] == gift.get("quest")), None)
    if q is None:
        bad.append("quest %r is not in data/quests.json" % gift.get("quest"))
    else:
        t = next((x for x in q["transitions"] if x["id"] == gift.get("transition")), None)
        if t is None:
            bad.append("transition %r is not in quest %s" % (gift.get("transition"), gift.get("quest")))
        else:
            grants = [e for e in t.get("effects") or [] if e.get("kind") == "grant_reward_once"]
            if len(grants) != 1 or grants[0].get("reward") != "reward_%s" % gift.get("reward") or grants[0].get("claim_field") != claim:
                bad.append("transition %s must hold exactly one grant_reward_once of reward_%s claiming %s"
                           % (gift.get("transition"), gift.get("reward"), claim))
        if not any(r.get("id") == "reward_%s" % gift.get("reward") for r in q.get("rewards") or []):
            bad.append("quest %s has no rewards entry reward_%s" % (gift.get("quest"), gift.get("reward")))
    rw = next((r for r in _json(REWARDS)["rewards"] if r.get("id") == gift.get("reward")), None)
    if rw is None:
        bad.append("reward %r is not in data/rewards.json" % gift.get("reward"))
    elif [(c["item"], c["count"]) for c in rw.get("contents") or []] != [(item, gift.get("count"))]:
        bad.append("reward %s must hold exactly %s x%s" % (gift.get("reward"), item, gift.get("count")))
    conv = next((c for c in _json(DIALOGUE)["conversations"] if c["id"] == gift.get("conversation")), None)
    if conv is None:
        bad.append("conversation %r is not in data/dialogue.json" % gift.get("conversation"))
    else:
        run = [a.get("transition") for n in conv["nodes"] for a in n.get("actions_after_acknowledge") or []
               if a.get("kind") == "quest_transition"]
        if gift.get("transition") not in run:
            bad.append("no node of %s runs the transition %s" % (gift.get("conversation"), gift.get("transition")))
    return bad


def closed(doc):
    """{path: text} for every recipe and advancement written back closed."""
    out = {}
    body = json.dumps({"fabric:load_conditions": [doc["recipe_off"]["condition"]]}, indent=2) + "\n"
    for kind, folder in (("recipes", "recipe"), ("advancements", "advancement")):
        for rid in doc["recipe_off"][kind]:
            ns, path = rid.split(":", 1)
            out["data/%s/%s/%s.json" % (ns, folder, path)] = body
    return out


def build(doc, jar=None):
    bad = problems(doc, jar)
    if bad:
        raise WaystoneError("data/player_waystone.json: " + "; ".join(bad))
    files = {"pack.mcmeta": json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                                 "Cobblers: no craftable waystones or warp items (tools/player_waystone.py)"}},
                                       indent=2) + "\n"}
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
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    b = sub.add_parser("build")
    b.add_argument("--out", default=str(DEFAULT_OUT))
    for s in (c, b):
        s.add_argument("--jar", default=None, help="the Waystones jar (default: the server snapshot's, when present)")
        s.add_argument("--require-jar", action="store_true", help="fail when no jar is found (prepare passes this)")
    a = ap.parse_args(argv)
    jar = Path(a.jar) if a.jar else find_jar()
    try:
        if a.require_jar and jar is None:
            raise WaystoneError("--require-jar: no Waystones jar found in %s; the closed list cannot be checked" % SNAPSHOT_MODS)
        doc = load()
        if a.cmd == "check":
            bad = problems(doc, jar)
            if bad:
                raise WaystoneError("; ".join(bad))
            print("player_waystone: the records agree; %d recipes and %d advancements closed; %s"
                  % (len(doc["recipe_off"]["recipes"]), len(doc["recipe_off"]["advancements"]),
                     ("list checked against %s" % jar.name) if jar else "no jar found, the list is NOT checked against it"))
        else:
            files = build(doc, jar)
            write(files, a.out)
            print("wrote %s (%d file(s)); %s" % (a.out, len(files) - 1,
                                                 ("list checked against %s" % jar.name) if jar else "jar not found: list NOT checked"))
    except WaystoneError as e:
        print("player_waystone: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
"""Generate the TM recipe gate from data/tm_gate.json: a crafted TMCraft TM unlocks, per player, at its badge.

The owner's decision of 2026-10-08 is data/tm_gate.json `decision`; the mechanism and every jar fact it rests on are
that file's `mechanism` (read from the Minecraft 1.21.1 jar, TMCraft 1.4.19, Tom's Storage, Carved Wood, Sophisticated
Core; nothing run in game: experiments/EXP-067-tm-recipe-gate).

THE RULE. The world runs with the gamerule doLimitedCrafting: a crafting-grid recipe is craftable only once it is in the
player's recipe book. The pack makes the recipe book hold everything but the TMs a player has not earned:

  tick        a player whose score cobblers.tmgate is not this plan's key runs tm_gate/sync once
  sync        `recipe give @s *`, then for each badge the player lacks: revoke its earn advancement and
              tm_gate/take/<flag> (`recipe take` of that badge's gated recipes); then the key is set
  earn/<flag> an advancement on minecraft:tick, the player holding cobblers:flag/<flag>: tm_gate/give/<flag>

A gated recipe is a crafting-grid recipe whose result is a TMCraft TM (data/tm_gate.json `gated`), plus, while
`devices.enforced`, every grid recipe whose result is a crafting device that never asks the recipe book (the Crafter,
Tom's crafting terminal). Every loaded advancement that unlocks a gated recipe is written back at its own path closed,
and so is every special recipe `devices.special_recipes_closed` names.

THE BADGE: the power rule (the owner, 2026-10-08: "TAKE THE POWER RULE ... SHELF WINS where it disagrees").
  a TM with a shelf line   its gate_badge in data/markets.json, whatever its score (data/tm_gate.json badge_rule.shelf);
                           every shelf line the power rule would place elsewhere is listed in
                           badge_rule.shelf_disagreements, exactly, or the plan fails
  any other TM             an outlier group of badge_rule.power.outliers that places it by hand, named and reasoned;
                           else the band of its score (badge_rule.power.bands, docs/mechanics/TM_POWER_GATE.md 3)
The scores are the committed table docs/mechanics/TM_POWER_GATE.json. tools/tm_power_score.py writes it from Mega
Showdown's moves.js (it needs node) and `--check` says whether it is current; this tool needs no node and checks instead
that the server's moves.js has the sha256 the table was scored from, and that the table covers every TM it gates.

What it reads: the server's own mods (nested jars too) and its global datapacks folder (`datapacks/`, not `extra/`),
the vanilla jar when one is found or given, config/advancementdisable.toml, the committed score table. Never a world.
The content is GPL / no redistribution, so nothing of it is committed: the pack is generated into build/ at prepare.

What it does NOT cover is data/tm_gate.json `does_not_cover`; first among them, Cobblemon's own TM Machine.

  python tools/tm_gate.py --server-dir <server>                 # sweep, check, write build/datapacks/cobblers_tm_gate
  python tools/tm_gate.py --server-dir <server> --check         # sweep and check only
  python tools/tm_gate.py sweep --server-dir <server> [--vanilla-jar <jar>]   # what doLimitedCrafting alone would strand
  python tools/tm_gate.py ... --plan-out <file>                 # the plan (every gated recipe, its badge and rule)

Ownership: the output is generated and lives in build/ and derived/ (gitignored); data/tm_gate.json is the source.
"""
from __future__ import annotations

import argparse
import collections
import fnmatch
import hashlib
import io
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import function_limits  # noqa: E402

DATA = ROOT / "data" / "tm_gate.json"
MARKETS = ROOT / "data" / "markets.json"
PROGRESSION = ROOT / "data" / "progression.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_tm_gate"
DEFAULT_PLAN = ROOT / "derived" / "tm_gate" / "plan.json"
DEFAULT_SWEEP = ROOT / "derived" / "tm_gate" / "sweep.json"
SCHEMA = "cobblers.tm_gate/1"
SCORES_SCHEMA = "cobblers.tm_power_gate/2"
PACK_FORMAT = 48  # Minecraft 1.21.1
NS = "cobblers"
SCORE = "cobblers.tmgate"
NEVER = {"condition": "fabric:not", "value": {"condition": "fabric:true"}}
ENTRY_RE = re.compile(r"^data/([a-z0-9_.-]+)/(recipe|advancement|function)/(.+)\.(json|mcfunction)$")
GEM_RE = re.compile(r"^cobblemon:([a-z]+)_gem$")
DISC_RE = re.compile(r"^tmcraft:([a-z]+)_blank_disc$")
SPECIAL_VANILLA = ("minecraft:crafting_special_", "minecraft:crafting_decorated_pot")
# Mega Showdown's ShowdownPatcher copies this file over Cobblemon's data/moves.js at startup, so it is the move data
# battles run (docs/mechanics/TM_POWER_GATE.md 1); the score table records its sha256 and the plan checks it
MSD_JAR_GLOB = "mega_showdown-fabric-*.jar"
MSD_MOVES = "assets/mega_showdown/showdown/moves.js"
VANILLA_CANDIDATES = ("libraries/net/minecraft/server/1.21.1/server-1.21.1.jar", "versions/1.21.1/server-1.21.1.jar",
                      "versions/1.21.1/1.21.1.jar")


class TmGateError(ValueError):
    pass


# ---------------------------------------------------------------- reading the server

class Entry:
    __slots__ = ("source", "ns", "kind", "path", "raw")

    def __init__(self, source, ns, kind, path, raw):
        self.source, self.ns, self.kind, self.path, self.raw = source, ns, kind, path, raw

    @property
    def id(self):
        return "%s:%s" % (self.ns, self.path)


def _zip_entries(zf, label, out, mod_ids, rank):
    """Every recipe, advancement and function in a jar (its nested jars and built-in packs too)."""
    for name in zf.namelist():
        if name.startswith("META-INF/jars/") and name.endswith(".jar"):
            _zip_entries(zipfile.ZipFile(io.BytesIO(zf.read(name))), label + "!" + name.rsplit("/", 1)[1], out,
                         mod_ids, rank)
            continue
        if name == "fabric.mod.json":
            try:
                meta = json.loads(zf.read(name).decode("utf-8", "replace"), strict=False)
            except ValueError:
                meta = {}
            if meta.get("id"):
                mod_ids.add(meta["id"])
            for p in meta.get("provides") or []:
                mod_ids.add(p)
            continue
        rel, src = name, label
        m = re.match(r"^resourcepacks/([^/]+)/(data/.+)$", name)
        if m:  # a Fabric built-in pack: counted as loaded (conservative for the gate)
            rel, src = m.group(2), "%s!builtin:%s" % (label, m.group(1))
        e = ENTRY_RE.match(rel)
        if e:
            out.append((rank + (1 if m else 0), Entry(src, e.group(1), e.group(2), e.group(3), zf.read(name))))


def _folder_entries(folder, label, out, rank):
    for f in sorted(folder.rglob("*")):
        if f.is_file():
            e = ENTRY_RE.match(f.relative_to(folder).as_posix())
            if e:
                out.append((rank, Entry(label, e.group(1), e.group(2), e.group(3), f.read_bytes())))


def find_vanilla(server_dir):
    for rel in VANILLA_CANDIDATES:
        p = Path(server_dir) / rel
        if p.is_file():
            return p
    return None


def read_server(server_dir, vanilla_jar=None):
    """{"entries": [Entry in load order], "mod_ids": set, "vanilla": path or None, "disabled_adv_ns": set}."""
    server_dir = Path(server_dir)
    mods = server_dir / "mods"
    if not mods.is_dir():
        raise TmGateError("no mods folder at %s" % mods)
    raw, mod_ids = [], {"minecraft", "java", "fabricloader"}
    vanilla = Path(vanilla_jar) if vanilla_jar else find_vanilla(server_dir)
    if vanilla:
        _zip_entries(zipfile.ZipFile(vanilla), "vanilla", raw, set(), 0)
    moves = []  # (jar name, sha256 of moves.js): the move data battles run, which the score table was scored from
    for jar in sorted(mods.glob("*.jar")):
        zf = zipfile.ZipFile(jar)
        if fnmatch.fnmatchcase(jar.name, MSD_JAR_GLOB) and MSD_MOVES in zf.namelist():
            moves.append((jar.name, hashlib.sha256(zf.read(MSD_MOVES)).hexdigest()))
        _zip_entries(zf, jar.name, raw, mod_ids, 10)
    dp = server_dir / "datapacks"
    if dp.is_dir():
        for p in sorted(dp.iterdir()):
            if p.suffix == ".zip":
                _zip_entries(zipfile.ZipFile(p), "datapack:" + p.name, raw, set(), 20)
            elif p.is_dir() and p.name != "extra":  # extra/ is optional in global_packs.toml and off in our world
                _folder_entries(p, "datapack:" + p.name, raw, 20)
    disabled = set()
    cfg = server_dir / "config" / "advancementdisable.toml"
    if cfg.is_file() and any(m.startswith("advancementdisable") for m in mod_ids):
        m = re.search(r"disabledMods\s*=\s*\[(.*?)\]", cfg.read_text(encoding="utf-8"), re.S)
        if m:
            disabled = set(re.findall(r'"([^"]+)"', m.group(1)))
    raw.sort(key=lambda t: t[0])  # stable: vanilla, mods, built-in packs, datapacks; later wins at the same path
    return {"entries": [e for _, e in raw], "mod_ids": mod_ids, "vanilla": str(vanilla) if vanilla else None,
            "disabled_adv_ns": disabled, "moves": moves}


def condition(c, mod_ids):
    """True / False for the Fabric conditions we can decide, None for any other (counted, kept)."""
    if not isinstance(c, dict):
        return None
    t = c.get("condition")
    if t == "fabric:true":
        return True
    if t == "fabric:not":
        v = condition(c.get("value"), mod_ids)
        return None if v is None else not v
    if t in ("fabric:and", "fabric:or"):
        vals = [condition(x, mod_ids) for x in c.get("values", [])]
        if None in vals:
            return None
        return all(vals) if t == "fabric:and" else any(vals)
    if t == "fabric:all_mods_loaded":
        return all(m in mod_ids for m in c.get("values", []))
    if t == "fabric:any_mods_loaded":
        return any(m in mod_ids for m in c.get("values", []))
    return None


def resolve(server):
    """The loaded recipes and advancements: {id: (source, json)}, after overrides, load conditions and
    advancementdisable; plus the functions and what could not be decided."""
    last = {}
    for e in server["entries"]:
        last[(e.kind, e.id)] = e
    recipes, advancements, functions = {}, {}, {}
    unknown, unparsed, dropped = collections.Counter(), collections.Counter(), collections.Counter()
    for (kind, rid), e in last.items():
        if kind == "function":
            functions[rid] = (e.source, e.raw.decode("utf-8", "replace"))
            continue
        try:
            doc = json.loads(e.raw.decode("utf-8-sig", "replace"), strict=False)
        except ValueError:
            unparsed[kind] += 1
            continue
        if not isinstance(doc, dict):
            unparsed[kind] += 1
            continue
        conds = doc.get("fabric:load_conditions") or []
        verdicts = [condition(c, server["mod_ids"]) for c in conds]
        if False in verdicts:
            dropped[kind] += 1
            continue
        for c, v in zip(conds, verdicts):
            if v is None:
                unknown[c.get("condition") if isinstance(c, dict) else "?"] += 1
        if kind == "recipe":
            if "type" not in doc:  # a file that only closes a recipe (the key_ball form) loads nothing
                dropped[kind] += 1
                continue
            recipes[rid] = (e.source, doc)
        else:
            if e.ns in server["disabled_adv_ns"]:
                dropped["advancement (advancementdisable)"] += 1
                continue
            if "criteria" not in doc:
                dropped[kind] += 1
                continue
            advancements[rid] = (e.source, doc)
    return {"recipes": recipes, "advancements": advancements, "functions": functions, "moves": server.get("moves", []),
            "unknown_conditions": dict(unknown), "unparsed": dict(unparsed), "dropped": dict(dropped)}


def result_id(recipe):
    r = recipe.get("result")
    if isinstance(r, dict):
        return r.get("id") or r.get("item")
    return r if isinstance(r, str) else None


def ingredient_ids(recipe):
    """Every item id a grid recipe names (tags are not items and are skipped)."""
    out = []
    pool = list(recipe.get("ingredients") or []) + list((recipe.get("key") or {}).values())
    for ing in pool:
        for alt in (ing if isinstance(ing, list) else [ing]):
            if isinstance(alt, dict) and isinstance(alt.get("item"), str):
                out.append(alt["item"])
            elif isinstance(alt, str) and not alt.startswith("#"):
                out.append(alt)
    return out


def unlocks(advancements):
    """{recipe id: [advancement ids whose rewards.recipes name it]}."""
    out = collections.defaultdict(list)
    for aid, (_, doc) in advancements.items():
        for rid in (doc.get("rewards") or {}).get("recipes") or []:
            out[rid].append(aid)
    return out


def recipe_kind(rtype, grid_types):
    if rtype in grid_types:
        return "grid"
    if isinstance(rtype, str) and rtype.startswith(SPECIAL_VANILLA):
        return "special"
    return "other"


# ---------------------------------------------------------------- the rule

def load(path=DATA):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != SCHEMA:
        raise TmGateError("%s: schema %r, expected %r" % (path, doc.get("schema"), SCHEMA))
    return doc


def shelf_badges(markets):
    """{tmcraft item: badge} from every counter line (stock and held_stock) carrying gate_badge."""
    out = {}
    for c in markets.get("counters", []):
        for key in ("stock", "held_stock"):
            for line in c.get(key, []) or []:
                item, badge = line.get("item"), line.get("gate_badge")
                if isinstance(item, str) and item.startswith("tmcraft:tm_") and isinstance(badge, int):
                    out[item] = min(badge, out.get(item, badge))
    return out


def band(score, bands):
    """The power badge of one score, by data/tm_gate.json badge_rule.power.bands (the proposal's bands,
    docs/mechanics/TM_POWER_GATE.md 3): badge 1 below badge_1_below, then the first badge whose inclusive top holds
    it, else above_top. The score is rounded to 0.1 first, as the table prints it."""
    s = round(score, 1)
    if s < bands["badge_1_below"]:
        return 1
    for b, top in sorted((int(k), v) for k, v in bands["top"].items()):
        if s <= top:
            return b
    return bands["above_top"]


def load_scores(doc, path=None):
    """The committed score table tools/tm_power_score.py writes (badge_rule.power.scores)."""
    p = Path(path) if path else ROOT / doc["badge_rule"]["power"]["scores"]
    t = json.loads(p.read_text(encoding="utf-8"))
    if t.get("schema") != SCORES_SCHEMA:
        raise TmGateError("%s: schema %r, expected %r" % (p, t.get("schema"), SCORES_SCHEMA))
    return t


def place(doc, scores, shelf):
    """The power rule over every scored TM: (tms {item: {badge, rule, score, power_badge}}, problems).

    shelf wins: a TM with a shelf line takes its gate_badge, whatever its score. Otherwise an outlier group in
    badge_rule.power.outliers that places it by hand; otherwise its score's band. A placement is never silent: every
    hand badge is a named, reasoned group in data/tm_gate.json, and each shelf line the power rule would put elsewhere
    must be listed in badge_rule.shelf_disagreements, exactly (a score or a shelf line that moves is named here)."""
    rule = doc["badge_rule"]["power"]
    bands = rule["bands"]
    table = scores["tms"]
    problems = []
    power = {}
    for item, row in table.items():
        b = band(row["score"], bands)
        if b != row.get("power_badge"):
            problems.append("%s: the score table says power badge %s, the bands give %d for score %s: the table is "
                            "stale against badge_rule.power.bands (python tools/tm_power_score.py)"
                            % (item, row.get("power_badge"), b, row["score"]))
        power[item] = b
    hand = {}
    for g in rule["outliers"]:
        tag = "outlier %d (%s)" % (g["group"], g["name"])
        for item, b in sorted(g.get("place", {}).items()):
            if item not in table:
                problems.append("%s places %s, which the score table does not have" % (tag, item))
            elif item in shelf:
                problems.append("%s places %s, a shelf TM: the shelf wins, so the placement is dead; "
                                "put it under shelf_agrees" % (tag, item))
            elif item in hand:
                problems.append("%s places %s, already placed by %s" % (tag, item, hand[item][1]))
            elif not (isinstance(b, int) and 1 <= b <= 8):
                problems.append("%s places %s at %r, not a badge 1-8" % (tag, item, b))
            else:
                hand[item] = (b, tag)
        for item, b in sorted(g.get("shelf_agrees", {}).items()):
            if shelf.get(item) != b:
                problems.append("%s says %s's shelf line is badge %d; the shelf says %s"
                                % (tag, item, b, shelf.get(item)))
    tms = {}
    for item in sorted(table):
        pb, sc = power[item], table[item]["score"]
        if item in shelf:
            badge, why = shelf[item], "shelf"
        elif item in hand:
            badge, why = hand[item][0], "%s; score %s -> %d" % (hand[item][1], sc, pb)
        else:
            badge, why = pb, "power: score %s -> %d" % (sc, pb)
        tms[item] = {"badge": badge, "rule": why, "score": sc, "power_badge": pb}
    for item in sorted(set(shelf) - set(table)):
        problems.append("shelf line %s has no score in the table: the shelf/power comparison cannot be made" % item)
    got = {(i, shelf[i], power[i]) for i in shelf if i in power and shelf[i] != power[i]}
    doc_lines = doc["badge_rule"]["shelf_disagreements"]["lines"]
    want = {(d["item"], d["shelf_badge"], d["power_badge"]) for d in doc_lines}
    for i, s, p in sorted(got - want):
        problems.append("shelf line %s (badge %d) disagrees with the power rule (%d) and badge_rule."
                        "shelf_disagreements does not list it so" % (i, s, p))
    for i, s, p in sorted(want - got):
        problems.append("badge_rule.shelf_disagreements lists %s as shelf %d against power %d; the data now says "
                        "shelf %s, power %s" % (i, s, p, shelf.get(i), power.get(i)))
    return tms, problems


def traits(recipe, grade_order, prefix="tmcraft:tm_"):
    """(gem type or None, disc grade index or None, [input TM items]) of one TM recipe. A chain TM (tm_howl is
    tm_leer + a normal gem + a punching glove) names an input TM instead of a disc."""
    gem = grade = None
    inputs = []
    for i in ingredient_ids(recipe):
        m = GEM_RE.match(i)
        if m:
            gem = m.group(1)
        d = DISC_RE.match(i)
        if d and d.group(1) in grade_order:
            grade = max(grade or 0, grade_order.index(d.group(1)))
        if i.startswith(prefix):
            inputs.append(i)
    return gem, grade, inputs


def tm_recipe_table(doc, resolved):
    """({tm item: [(recipe id, gem, grade index, [input TMs])]}, problems): every loaded crafting-grid recipe whose
    result is a TMCraft TM. A TM recipe of another type is a problem: doLimitedCrafting would not reach it."""
    problems = []
    grid = set(doc["gated"]["grid_types"])
    prefix = doc["gated"]["result_prefix"]
    order = doc["badge_rule"]["grade_order"]
    out = collections.defaultdict(list)
    for rid, (_, r) in resolved["recipes"].items():
        res = result_id(r)
        if isinstance(res, str) and res.startswith(prefix):
            if recipe_kind(r.get("type"), grid) != "grid":
                problems.append("%s makes %s but is a %s recipe, which doLimitedCrafting does not reach"
                                % (rid, res, r.get("type")))
                continue
            out[res].append((rid,) + traits(r, order, prefix))
    if not out:
        problems.append("no loaded recipe makes a %s item: is TMCraft in the server's mods?" % prefix)
    return out, problems


def plan(doc, resolved, markets, progression, scores=None):
    """Every gated recipe with its badge and the rule that set it; the advancements and special recipes to close;
    the problems (fail closed). scores: the score table (default: the committed one, badge_rule.power.scores)."""
    notes = []
    grid = set(doc["gated"]["grid_types"])
    recipes = resolved["recipes"]
    tm_recipes, problems = tm_recipe_table(doc, resolved)
    scores = scores if scores is not None else load_scores(doc)
    # the table must have been scored from the move data this server's battles run
    moves = resolved.get("moves") or []
    if len(moves) != 1:
        problems.append("the server has %d Mega Showdown moves.js (%s), expected one: the score table's source cannot "
                        "be checked" % (len(moves), [m[0] for m in moves]))
    elif moves[0][1] != scores.get("moves_sha256"):
        problems.append("%s!%s has sha256 %s; the score table was scored from %s: re-run tools/tm_power_score.py"
                        % (moves[0][0], MSD_MOVES, moves[0][1][:12], str(scores.get("moves_sha256"))[:12]))
    shelf = shelf_badges(markets)
    flags = {f["id"] for f in progression.get("flags", [])}
    for b in range(1, 9):
        if "gym%d_cleared" % b not in flags:
            problems.append("data/progression.json has no flag gym%d_cleared" % b)
    placed, place_problems = place(doc, scores, shelf)
    problems += place_problems
    tms = {}
    for item in sorted(tm_recipes):
        if item not in placed:
            problems.append("%s has a crafting recipe on this server and no score in the table: re-run "
                            "tools/tm_power_score.py" % item)
            continue
        tms[item] = dict(placed[item], recipes=sorted(t[0] for t in tm_recipes[item]))
    extra = sorted(set(placed) - set(tm_recipes))
    if extra:
        notes.append("%d scored TM(s) have no loaded crafting recipe on this server: %s" % (len(extra), extra[:5]))
    for item in sorted(set(shelf) - set(tm_recipes)):
        notes.append("shelf line %s has no loaded crafting recipe: nothing to gate" % item)
    # a chain TM (tm_howl is tm_leer + a gem + a glove) is placed by its own score, not held behind its input TM: its
    # recipe needs the input TM in hand, which the shelf, loot or a trade can supply before the input's recipe opens
    early = sorted("%s %d < %s %d" % (item, t["badge"], inp, tms[inp]["badge"]) for item, t in tms.items()
                   for _, _, _, inputs in tm_recipes[item] for inp in inputs
                   if inp in tms and tms[inp]["badge"] > t["badge"])
    if early:
        notes.append("%d chain TM recipe(s) open before their input TM's recipe (by design): %s"
                     % (len(early), early[:6]))
    gated = {}
    for item, t in tms.items():
        for rid in t["recipes"]:
            gated[rid] = {"result": item, "badge": t["badge"]}
    top = max([t["badge"] for t in tms.values()] or [8])
    dev = doc["devices"]
    closed_recipes = []
    if dev["enforced"]:
        found = set()
        for rid, (_, r) in recipes.items():
            res = result_id(r)
            pat = next((pt for pt in dev["items"] if isinstance(res, str) and fnmatch.fnmatchcase(res, pt)), None)
            if pat and recipe_kind(r.get("type"), grid) == "grid":
                gated[rid] = {"result": res, "badge": top, "device": True}
                found.add(pat)
        for rid in dev.get("vanilla_recipes", []):  # vanilla's own id, for a server whose vanilla jar was not read
            gated.setdefault(rid, {"result": rid, "badge": top, "device": True})
        for rid in dev["special_recipes_closed"]:
            if rid in recipes:
                closed_recipes.append(rid)
            else:
                notes.append("special recipe %s is not loaded: nothing to close" % rid)
        for item in dev["items"]:
            if item not in found and item != "minecraft:crafter":
                notes.append("device %s: no loaded grid recipe makes it" % item)
    # every loaded advancement that unlocks a gated recipe is closed; it must unlock nothing else and do nothing else
    closed_adv = []
    for aid, (_, a) in sorted(resolved["advancements"].items()):
        rew = a.get("rewards") or {}
        names = rew.get("recipes") or []
        hit = [r for r in names if r in gated]
        if not hit:
            continue
        other = [r for r in names if r not in gated]
        extra = sorted(k for k in rew if k != "recipes")
        if other or extra:
            problems.append("advancement %s unlocks gated %s but also %s: closing it would take those too"
                            % (aid, hit[:3], (other[:3] + extra)))
            continue
        closed_adv.append(aid)
    if dev["enforced"]:
        closed_adv += [aid for aid in dev.get("vanilla_advancements", []) if aid not in closed_adv]
    closed = set(closed_adv)
    for aid, (_, a) in resolved["advancements"].items():
        if a.get("parent") in closed and aid not in closed:
            problems.append("advancement %s has the closed %s as its parent: it would not load" % (aid, a["parent"]))
    # nothing else on the server may hand out the gated recipes, or everything, unless data/tm_gate.json `regivers`
    # names it with the trigger that runs it (the pack re-syncs the player after it)
    declared = {r["function"]: r for r in doc.get("regivers", [])}
    regivers = []
    for fid, (src, text) in sorted(resolved["functions"].items()):
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("#") or "recipe give" not in s:
                continue
            arg = s.split("recipe give", 1)[1].split()
            if len(arg) >= 2 and (arg[1] == "*" or arg[1] in gated):
                if fid in declared:
                    regivers.append(fid)
                else:
                    problems.append("function %s (%s) runs `%s`: it would hand out gated recipes, and "
                                    "data/tm_gate.json regivers does not name it" % (fid, src, s))
    for fid in sorted(set(declared) - set(regivers)):
        notes.append("regiver %s no longer gives recipes on this server: its re-sync is kept, harmless" % fid)
    key_src = json.dumps({"recipes": sorted(recipes), "gated": sorted((k, v["badge"]) for k, v in gated.items()),
                          "version": doc["sync_version"]}, sort_keys=True)
    key = int(hashlib.sha256(key_src.encode()).hexdigest()[:8], 16) % 2000000000 + 1
    disagree = ["%s: shelf %d, power %d (score %s)" % (item, t["badge"], t["power_badge"], t["score"])
                for item, t in sorted(tms.items()) if t["rule"] == "shelf" and t["badge"] != t["power_badge"]]
    by_rule = collections.Counter(t["rule"].split(" ")[0].split(":")[0] for t in tms.values())
    return {"tms": tms, "gated": gated, "closed_advancements": closed_adv, "closed_recipes": sorted(closed_recipes),
            "top_badge": top, "key": key, "moves_sha256": scores.get("moves_sha256"),
            "distribution": dict(sorted(collections.Counter(t["badge"] for t in tms.values()).items())),
            "by_rule": dict(sorted(by_rule.items())),
            "shelf_disagreements": disagree, "problems": problems, "notes": notes,
            "counts": {"tm_items": len(tms), "gated_recipes": len(gated),
                       "gated_tm_recipes": sum(1 for g in gated.values() if not g.get("device")),
                       "closed_advancements": len(closed_adv), "loaded_recipes": len(recipes)}}


# ---------------------------------------------------------------- the pack

def flag_of(badge):
    return "gym%d_cleared" % badge


def build(doc, p):
    """{relative path: text} for the pack."""
    if p["problems"]:
        raise TmGateError("tm_gate: %d problem(s):\n  %s" % (len(p["problems"]), "\n  ".join(p["problems"])))
    by_badge = collections.defaultdict(list)
    for rid, g in p["gated"].items():
        by_badge[g["badge"]].append(rid)
    badges = sorted(by_badge)
    head = "# Generated by tools/tm_gate.py from data/tm_gate.json (plan key %d). Do not edit." % p["key"]
    out = {"pack.mcmeta": json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                               "Cobblers: crafted TMs unlock per player at their badge"}}, indent=2) + "\n"}
    out["data/minecraft/tags/function/load.json"] = json.dumps({"values": ["%s:tm_gate/load" % NS]}, indent=2) + "\n"
    out["data/minecraft/tags/function/tick.json"] = json.dumps({"values": ["%s:tm_gate/tick" % NS]}, indent=2) + "\n"
    fn = "data/%s/function/tm_gate/%%s.mcfunction" % NS
    out[fn % "load"] = "\n".join([head, "gamerule doLimitedCrafting true",
                                  "scoreboard objectives add %s dummy" % SCORE]) + "\n"
    out[fn % "tick"] = "\n".join([head, "execute as @a unless score @s %s matches %d run function %s:tm_gate/sync"
                                  % (SCORE, p["key"], NS)]) + "\n"
    sync = [head, "# as the player: every recipe the server has, then back the gated ones of every badge not held",
            "recipe give @s *"]
    for b in badges:
        sync.append("execute unless entity @s[advancements={%s:flag/%s=true}] run function %s:tm_gate/take/%s"
                    % (NS, flag_of(b), NS, flag_of(b)))
    sync.append("scoreboard players set @s %s %d" % (SCORE, p["key"]))
    out[fn % "sync"] = "\n".join(sync) + "\n"
    out[fn % "off"] = "\n".join([head, "# run once before removing the pack: the gamerule is saved with the world",
                                 "gamerule doLimitedCrafting false", "scoreboard objectives remove %s" % SCORE]) + "\n"
    for b in badges:
        f = flag_of(b)
        ids = sorted(by_badge[b])
        out[fn % ("take/" + f)] = "\n".join([head, "advancement revoke @s only %s:tm_gate/earn/%s" % (NS, f)]
                                            + ["recipe take @s %s" % r for r in ids]) + "\n"
        out[fn % ("give/" + f)] = "\n".join([head] + ["recipe give @s %s" % r for r in ids]) + "\n"
        out["data/%s/advancement/tm_gate/earn/%s.json" % (NS, f)] = json.dumps({
            "criteria": {"held": {"trigger": "minecraft:tick", "conditions": {"player": [
                {"condition": "minecraft:entity_properties", "entity": "this", "predicate": {"type_specific": {
                    "type": "minecraft:player", "advancements": {"%s:flag/%s" % (NS, f): True}}}}]}}},
            "rewards": {"function": "%s:tm_gate/give/%s" % (NS, f)}}, indent=2) + "\n"
    for n, r in enumerate(doc.get("regivers", []), 1):
        adv = "%s:tm_gate/resync/%d" % (NS, n)
        out["data/%s/advancement/tm_gate/resync/%d.json" % (NS, n)] = json.dumps({
            "criteria": {"ran": {"trigger": r["runs_on"]}},
            "rewards": {"function": "%s:tm_gate/resync/%d" % (NS, n)}}, indent=2) + "\n"
        out[fn % ("resync/%d" % n)] = "\n".join([
            head, "# %s runs `recipe give @s *` on %s: re-sync this player on the next tick" % (r["function"],
                                                                                              r["runs_on"]),
            "advancement revoke @s only %s" % adv, "scoreboard players reset @s %s" % SCORE]) + "\n"
    body = json.dumps({"fabric:load_conditions": [NEVER]}, indent=2) + "\n"
    for aid in p["closed_advancements"]:
        ns, path = aid.split(":", 1)
        out["data/%s/advancement/%s.json" % (ns, path)] = body
    for rid in p["closed_recipes"]:
        ns, path = rid.split(":", 1)
        out["data/%s/recipe/%s.json" % (ns, path)] = body
    refused = []
    for rel, text in out.items():
        if rel.endswith(".mcfunction"):
            refused += function_limits.check_lines(text.splitlines(), rel)
    if refused:
        raise TmGateError("function_limits refused: %s" % refused[:5])
    return out


def write(files, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in files.items():
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------- the stranding sweep

def sweep(doc, server, resolved):
    """What doLimitedCrafting alone would do to every loaded recipe, with no give: counted by namespace."""
    grid = set(doc["gated"]["grid_types"])
    unl = unlocks(resolved["advancements"])
    rows = collections.defaultdict(collections.Counter)
    types = collections.Counter()
    stranded = []
    for rid, (src, r) in sorted(resolved["recipes"].items()):
        ns = rid.split(":")[0]
        kind = recipe_kind(r.get("type"), grid)
        if kind == "other":
            t = r.get("type")
            if isinstance(t, str) and re.search(r"craft|shaped|shapeless", t) and not t.startswith("minecraft:"):
                types[t] += 1
                rows[ns]["mod crafting type (not swept)"] += 1
            else:
                rows[ns]["not a crafting-grid recipe"] += 1
            continue
        if kind == "special":
            rows[ns]["special (never limited)"] += 1
            continue
        if unl.get(rid):
            rows[ns]["grid, unlocked by an advancement"] += 1
        else:
            rows[ns]["grid, NO unlock: stranded without the give"] += 1
            stranded.append(rid)
    total = collections.Counter()
    for c in rows.values():
        total.update(c)
    return {"vanilla_read": server["vanilla"], "advancement_namespaces_disabled": sorted(server["disabled_adv_ns"]),
            "loaded_recipes": len(resolved["recipes"]), "totals": dict(total),
            "stranded_by_namespace": dict(collections.Counter(r.split(":")[0] for r in stranded).most_common()),
            "mod_crafting_types": dict(types), "unknown_conditions": resolved["unknown_conditions"],
            "unparsed": resolved["unparsed"], "dropped": resolved["dropped"], "stranded": stranded}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("mode", nargs="?", choices=["build", "sweep"], default="build")
    ap.add_argument("--server-dir", required=True)
    ap.add_argument("--vanilla-jar")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--plan-out", default=str(DEFAULT_PLAN))
    ap.add_argument("--sweep-out", default=str(DEFAULT_SWEEP))
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    doc = load()
    server = read_server(a.server_dir, a.vanilla_jar)
    resolved = resolve(server)
    if a.mode == "sweep":
        s = sweep(doc, server, resolved)
        Path(a.sweep_out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.sweep_out).write_text(json.dumps(s, indent=1) + "\n", encoding="utf-8")
        print("tm_gate sweep: %d loaded recipes (vanilla %s); %s" % (
            s["loaded_recipes"], "read" if s["vanilla_read"] else "NOT read",
            "; ".join("%s %d" % kv for kv in sorted(s["totals"].items()))))
        print("  stranded without the give, by namespace: %s" % s["stranded_by_namespace"])
        print("  mod crafting types not swept: %s" % s["mod_crafting_types"])
        print("  written %s" % a.sweep_out)
        return 0
    p = plan(doc, resolved, json.loads(MARKETS.read_text(encoding="utf-8")),
             json.loads(PROGRESSION.read_text(encoding="utf-8")))
    Path(a.plan_out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.plan_out).write_text(json.dumps(p, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if p["problems"]:
        print("tm_gate: %d PROBLEM(S) (plan %s):" % (len(p["problems"]), a.plan_out))
        for x in p["problems"][:20]:
            print("  PROBLEM " + x)
        return 1
    by = collections.Counter(t["badge"] for t in p["tms"].values())
    print("tm_gate: %d TMs, %d gated recipes (%d TM, %d device), %d unlock advancements closed, %d special recipes "
          "closed; TMs by badge %s; by rule %s; shelf lines kept against the power rule %d; key %d" % (
              p["counts"]["tm_items"], p["counts"]["gated_recipes"], p["counts"]["gated_tm_recipes"],
              p["counts"]["gated_recipes"] - p["counts"]["gated_tm_recipes"], len(p["closed_advancements"]),
              len(p["closed_recipes"]), dict(sorted(by.items())), p["by_rule"], len(p["shelf_disagreements"]),
              p["key"]))
    for n in p["notes"]:
        print("  note: " + n)
    if a.check:
        return 0
    files = build(doc, p)
    write(files, a.out)
    print("  wrote %d files to %s" % (len(files), a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())

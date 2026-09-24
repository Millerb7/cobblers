#!/usr/bin/env python
"""Town traders as data: the manifest (data/traders.json), its re-application function, and presence checks.

A trader is an entity, and a re-export regenerates every region and entity file from the WorldPainter project,
so a trader summoned in game is gone after the next export. The manifest is the source, like the Habitat Blocks
(tools/habitat_blocks.py): this tool writes the function that puts every trader back, and checks that each one
stands exactly once. Nothing is summoned by hand.

  function   python tools/traders.py function [--server-dir <server>] [--out build/datapacks/cobblers_vendors]
             then: /reload and /function cobblers:towns/vendors_<settlement>, and wait 8 seconds for it to finish
  verify     python tools/traders.py verify --rcon <server dir>     a running server, under the coordination lock
             python tools/traders.py verify --world <stopped world>  an offline snapshot or disposable copy

Each trader is summoned from the entity in its shopkeeper template: the trade list, name and look come from the
installed pack, and only the fields the engine owns are dropped. The function runs in three ticks' worth of steps,
each spaced by what was measured on the disposable world on 2026-09-21:

  vendors_<town>        force-load the plaza, then wait 40 ticks.
  vendors_<town>_place  summon every trader with a "new" tag.
  vendors_<town>_done   100 ticks later: where a new trader stands, kill every older one with its tag and any
                        untagged copy of it on its spot, drop the "new" tag, release the plaza.

Why the waits, measured with an old trader saved in an unloaded chunk and a new one summoned N ticks after
`forceload add`: at 1 and 2 ticks the chunk accepts a summon but its saved entities are not loaded yet, so a kill by
tag finds nothing and the old trader survives beside the new (old 1, new 1); at 20 and 100 ticks the kill finds it
(old 0, new 1). The first version killed at 2 ticks, and every run stacked another trader on each spot. Deduplicating
100 ticks after the summon, and only where the new one exists, makes a re-run converge on one trader per spot even if
loading is slower, and leaves the old trader standing if a summon ever fails.

Counting has the same trap: an entity in a chunk that is not force-loaded or near a player is invisible to @e even
while its chunk is still unloading, so a count taken after the plaza is released reads 0 with every trader in place.
That reading is what looked like "the function summons nothing". verify --rcon force-loads the plaza and waits for
the count to settle before it believes it.

Ownership: generated output under build/ (gitignored). Who stands where is authored in data/traders.json.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import function_limits  # noqa: E402
import nbt  # noqa: E402

MANIFEST = ROOT / "data" / "traders.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_vendors"
STATUSES = ("planned", "placed", "verified")
PLACED = ("placed", "verified")
TAG_ALL = "cobblers_vendor"
TAG_NEW = "cobblers_vendor_new"
LOAD_WAIT = 40      # ticks from forceload to summon: saved entities load within 20 (measured), doubled
DEDUPE_WAIT = 100   # ticks from summon to the de-duplication and release
SPOT_RADIUS = 3     # a trader wanders a little; further than this from its spot is not standing there
PLAZA_MARGIN = 48    # force-loaded round the plaza, so strays that walked off are found too


# The ground rule (tools/ground_rule.py): the functions here that read a world, each only to check, never to
# decide a position: `verify` counts traders in a stopped world; placement never reads one.
WORLD_READS = {'main', 'world_counts', 'world_problems'}


def tag_of(tid):
    return "%s_%s" % (TAG_ALL, tid)


def find_template(server_dir, template_id):
    """The raw nbt of a template the server can place, from a mod jar or a datapack."""
    ns, rel = template_id.split(":", 1)
    names = ("data/%s/structure/%s.nbt" % (ns, rel), "data/%s/structures/%s.nbt" % (ns, rel))
    sources = sorted(glob.glob(os.path.join(server_dir, "mods", "*.jar"))) + \
        sorted(glob.glob(os.path.join(server_dir, "datapacks", "*.zip")))
    for path in sources:
        try:
            z = zipfile.ZipFile(path)
        except (zipfile.BadZipFile, OSError):  # not a readable jar
            continue
        for name in names:
            if name in z.namelist():
                return z.read(name)
    raise SystemExit("template not found in the installed packs: %s" % template_id)


def to_snbt(value):
    """NBT value -> the SNBT a command takes."""
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], int):
        return to_snbt(value[1])
    if isinstance(value, dict):
        return "{%s}" % ",".join('%s:%s' % (k, to_snbt(v)) for k, v in value.items())
    if isinstance(value, list):
        return "[%s]" % ",".join(to_snbt(v) for v in value)
    if isinstance(value, bool):
        return "1b" if value else "0b"
    if isinstance(value, float):
        return "%sf" % value
    if isinstance(value, int):
        return str(value)
    # SNBT has no unicode escape, and json.dumps writes one for any non-ASCII character: a
    # trader whose shop category is spelled with an accent stopped the whole function loading.
    text = str(value).replace(chr(92), chr(92) * 2).replace('"', chr(92) + '"')
    return '"%s"' % text


# Keep what the trader is, drop what the engine owns. A copied UUID collides with the entity already in the
# world on a re-run, Pos and Motion fight the summon's own coordinates, and the brain and attribute block only
# lengthen the command.
ENGINE_OWNED = ("UUID", "Pos", "Motion", "Rotation", "Brain", "attributes", "Attributes", "HurtByTimestamp",
                "HurtTime", "DeathTime", "FallDistance", "FallFlying", "PortalCooldown", "OnGround", "Air",
                "AbsorptionAmount", "fabric:attachments", "cardinal_components", "Bukkit.updateLevel",
                "WorldUUIDLeast", "WorldUUIDMost", "Tags")


def entity_of(server_dir, template_id):
    """(entity id, nbt dict without engine-owned fields) of the trader in a shopkeeper template."""
    _, root = nbt.loads(find_template(server_dir, template_id))
    entities = root.get("entities") or []
    if not entities:
        raise SystemExit("%s holds no entity to summon" % template_id)
    data = dict(entities[0].get("nbt") or {})
    kind = data.pop("id", "minecraft:villager")
    kind = kind[1] if isinstance(kind, tuple) else kind
    for k in ENGINE_OWNED:
        data.pop(k, None)
    return str(kind), data


def _v(x):
    return x[1] if isinstance(x, tuple) and len(x) == 2 and isinstance(x[0], int) else x


def apply_stock_policy(data, policy):
    """(data with the shop filtered, kept item ids, withheld item ids).

    The shopkeeper templates sell whatever BCA stocked: ultra balls, max revives, X items next to the fish and
    bread. Until the badge-gated stock is designed, a trader sells only what the policy in data/traders.json
    leaves: whole categories and single items are withheld, and a category left empty is dropped."""
    shop = data.get("CobbleMerchantShop")
    if shop is None or not policy:
        return data, None, []                      # nothing to filter: not "nothing left"
    cats_out, kept, held = [], [], []
    no_cat = set(policy.get("withhold_categories") or [])
    no_item = set(policy.get("withhold_items") or [])
    for cat in _v(shop):
        cat = _v(cat)
        name = _v(cat.get("Category"))
        offers = []
        for off in _v(cat.get("Offers")) or []:
            iid = _v(_v(_v(off).get("Item")).get("id"))
            if name in no_cat or iid in no_item:
                held.append(iid)
            else:
                kept.append(iid)
                offers.append(off)
        if offers:
            c = dict(cat)
            c["Offers"] = offers
            cats_out.append(c)
    out = dict(data)
    out["CobbleMerchantShop"] = cats_out
    return out, kept, held


def display_name(data):
    """The plain name a template gives its trader, or None. CustomName is a JSON text component."""
    raw = data.get("CustomName")
    raw = raw[1] if isinstance(raw, tuple) else raw
    if not isinstance(raw, str):
        return None
    try:
        v = json.loads(raw)
    except ValueError:
        return None
    if isinstance(v, dict):
        v = v.get("text")
    return v if isinstance(v, str) and v and '"' not in v else None


def stray_selector(kind, name, x, y, z):
    """Untagged entities that are copies of this trader: same type and name within the plaza margin, or, for a
    trader without a name, same type on its spot."""
    if name:
        return 'type=%s,name="%s",tag=!%s,x=%d.5,y=%d,z=%d.5,distance=..%d' % (kind, name, TAG_ALL, x, y, z, PLAZA_MARGIN)
    return "type=%s,tag=!%s,x=%d.5,y=%d,z=%d.5,distance=..%d" % (kind, TAG_ALL, x, y, z, SPOT_RADIUS)


def plaza_box(recs):
    xs = [r["position"]["x"] for r in recs]
    zs = [r["position"]["z"] for r in recs]
    return min(xs) - PLAZA_MARGIN, min(zs) - PLAZA_MARGIN, max(xs) + PLAZA_MARGIN, max(zs) + PLAZA_MARGIN


def town_functions(town, recs, entity, policy=None):
    """{function name: lines} for one settlement. entity(template id) -> (kind, nbt dict). A trader the stock
    policy leaves with nothing to sell is withdrawn: no summon, and any copy already standing is removed."""
    box = "%d %d %d %d" % plaza_box(recs)
    loader = ["# Generated by tools/traders.py from data/traders.json: the traders of %s" % town,
              "# force-load the plaza and give its saved traders time to load before anything is summoned",
              "forceload add %s" % box,
              "schedule function cobblers:towns/vendors_%s_place %dt replace" % (town, LOAD_WAIT)]
    place = ["# Generated by tools/traders.py; called by cobblers:towns/vendors_%s" % town,
             # the loader force-loads the plaza and the _done step releases it, after the summons are saved
             "# chunks-loaded-by: cobblers:towns/vendors_%s" % town]
    done = ["# Generated by tools/traders.py; %d ticks after the summons: one trader per spot, then release" % DEDUPE_WAIT]
    for rec in sorted(recs, key=lambda q: q["id"]):
        kind, data = entity(rec["template"])
        data, kept, _held = apply_stock_policy(dict(data), policy)
        x, y, z = (rec["position"][k] for k in "xyz")
        tag = tag_of(rec["id"])
        if kept == [] or rec.get("stock") == "withdrawn":
            name = display_name(data)
            done += ["# %s: withdrawn, nothing left to sell under the stock policy" % rec["id"],
                     "kill @e[tag=%s]" % tag, "kill @e[%s]" % stray_selector(kind, name, x, y, z)]
            continue
        data["Tags"] = [TAG_ALL, tag, TAG_NEW]
        data["PersistenceRequired"] = True
        # The template's merchant keeps its AI and walks: copies summoned with it were found 2 to 40 blocks off
        # their stalls. A stall trader stands still.
        data["NoAI"] = True
        name = display_name(data)
        place += ["# %s: %s" % (rec["id"], rec["template"]),
                  # a jigsaw left by the earlier attempt that placed traders as structures
                  "execute if block %d %d %d minecraft:jigsaw run setblock %d %d %d minecraft:air" % (x, y, z, x, y, z),
                  "execute if block %d %d %d minecraft:jigsaw run setblock %d %d %d minecraft:air" % (x, y + 1, z, x, y + 1, z),
                  "summon %s %d.5 %d %d.5 %s" % (kind, x, y, z, to_snbt(data))]
        done += ["# %s" % rec["id"],
                 "execute if entity @e[tag=%s,tag=%s] run kill @e[tag=%s,tag=!%s]" % (tag, TAG_NEW, tag, TAG_NEW),
                 # untagged copies of this trader, left by structure placement or by hand: same type and name,
                 # anywhere round the plaza, since the earlier copies could walk
                 "execute if entity @e[tag=%s,tag=%s] run kill @e[%s]" % (tag, TAG_NEW, stray_selector(kind, name, x, y, z)),
                 # this trader's own "new" tag only: stripping it from every entity let the first town's pass
                 # clear the second town's before that town de-duplicated, and the second town kept stacking
                 "tag @e[tag=%s,tag=%s] remove %s" % (tag, TAG_NEW, TAG_NEW)]
    place.append("schedule function cobblers:towns/vendors_%s_done %dt replace" % (town, DEDUPE_WAIT))
    done += ["forceload remove %s" % box]
    return {"vendors_%s" % town: loader, "vendors_%s_place" % town: place, "vendors_%s_done" % town: done}


def static_problems(doc, placements_doc=None, plans_dir=None):
    """[(record id or None, message)] for rules that need no world."""
    out = []
    recs = doc.get("traders") if isinstance(doc, dict) else None
    if not isinstance(recs, list):
        return [(None, '"traders" must be a list')]
    towns = {s.get("id") for s in (placements_doc or {}).get("settlements") or [] if isinstance(s, dict)}
    seen, spots = set(), {}
    for r in recs:
        rid = r.get("id") if isinstance(r, dict) else None
        if not rid:
            out.append((None, "every trader needs an id"))
            continue
        if not re.fullmatch(r"[a-z0-9_]+", rid):
            out.append((rid, "id must be lower-case letters, digits and underscores (it becomes an entity tag)"))
        if rid in seen:
            out.append((rid, "duplicate id"))
        seen.add(rid)
        pos = r.get("position")
        if not (isinstance(pos, dict) and all(isinstance(pos.get(k), int) and not isinstance(pos.get(k), bool) for k in "xyz")):
            out.append((rid, "position must be {x, y, z} integers"))
            continue
        key = (pos["x"], pos["y"], pos["z"])
        if key in spots:
            out.append((rid, "stands on the same block as %s" % spots[key]))
        spots[key] = rid
        if not (isinstance(r.get("template"), str) and ":" in r["template"]):
            out.append((rid, "template must be a namespaced template id"))
        if r.get("stock") not in ("regional", "withdrawn"):
            out.append((rid, "stock must be regional or withdrawn"))
        if r.get("status") not in STATUSES:
            out.append((rid, "status must be one of %s" % ", ".join(STATUSES)))
        if towns and r.get("settlement") not in towns:
            out.append((rid, "settlement %r is not a settlement in data/placements.json" % r.get("settlement")))
        if plans_dir is not None:
            plan = Path(plans_dir) / ("%s_plan.json" % r.get("settlement"))
            if plan.is_file():
                p = json.loads(plan.read_text(encoding="utf-8"))
                py = (p.get("plaza") or {}).get("y")
                if isinstance(py, int) and pos["y"] != py + 1:
                    out.append((rid, "stands at y%d, but the town plan paves the plaza at y%d, so it should be y%d"
                                % (pos["y"], py, py + 1)))
    return out


def rcon_counts(server_dir, recs, settle=(4, 30), policy=None, leaks=None):
    """{id: (tagged count anywhere loaded, tagged count on its spot, untagged copies on its spot)} from a running
    server. Force-loads each plaza and polls until two samples agree: entities appear some ticks after their chunk.
    With a policy and a leaks dict, also reads each standing trader's shop and records withheld items it still sells."""
    import runtime_guard
    module, pw = runtime_guard.rcon(server_dir)
    run = lambda c: module.run([c], pw, timeout=120)[0].strip()

    def n(sel):
        run("execute store result score #n cobblers_traders if entity %s" % sel)
        return int(re.search(r"has (-?\d+)", run("scoreboard players get #n cobblers_traders")).group(1))

    run("scoreboard objectives add cobblers_traders dummy")
    ents = {r["template"]: entity_of(server_dir, r["template"]) for r in recs}
    by_town = {}
    for r in recs:
        by_town.setdefault(r["settlement"], []).append(r)
    out = {}
    for town, trs in by_town.items():
        box = "%d %d %d %d" % plaza_box(trs)
        run("forceload add %s" % box)
        try:
            step, limit = settle
            last, waited = None, 0
            while True:
                time.sleep(step)
                waited += step
                now = {}
                for r in trs:
                    x, y, z = (r["position"][k] for k in "xyz")
                    spot = "x=%d.5,y=%d,z=%d.5,distance=..%d" % (x, y, z, SPOT_RADIUS)
                    now[r["id"]] = (n("@e[tag=%s]" % tag_of(r["id"])), n("@e[tag=%s,%s]" % (tag_of(r["id"]), spot)),
                                    n("@e[%s]" % stray_selector(ents[r["template"]][0], display_name(ents[r["template"]][1]), x, y, z)))
                if now == last or waited >= limit:
                    out.update(now)
                    break
                last = now
            if policy is not None and leaks is not None:
                held = set(policy.get("withhold_items") or [])
                for r in trs:
                    if r.get("stock") == "withdrawn" or not out[r["id"]][0]:
                        continue
                    shop = run("data get entity @e[tag=%s,limit=1] CobbleMerchantShop" % tag_of(r["id"]))
                    ids = set(re.findall(r'id: "([^"]+)"', shop))
                    cats = set(re.findall(r'Category: "([^"]+)"', shop))
                    bad = sorted(ids & held) + sorted("category " + c for c in cats & set(policy.get("withhold_categories") or []))
                    if bad:
                        leaks[r["id"]] = bad
        finally:
            run("forceload remove %s" % box)
    return out


def world_counts(world_dir, recs):
    """{id: (tagged count in the chunks around its spot, tagged on its spot, None)} from a stopped world's
    entity files. Untagged copies are not counted offline."""
    import runtime_guard
    world = Path(runtime_guard.check(world_dir, "read"))
    want = {}
    for r in recs:
        x, z = r["position"]["x"], r["position"]["z"]
        for cx in range((x >> 4) - 1, (x >> 4) + 2):
            for cz in range((z >> 4) - 1, (z >> 4) + 2):
                want.setdefault((cx >> 5, cz >> 5), set()).add((cx & 31, cz & 31))
    found = []
    for (rx, rz), chunks in want.items():
        path = world / "entities" / ("r.%d.%d.mca" % (rx, rz))
        if not path.is_file():
            continue
        for _, _, ch in nbt.region_chunks(path, wanted=chunks):
            for e in ch.get("Entities") or []:
                tags = [t[1] if isinstance(t, tuple) else t for t in e.get("Tags") or []]
                pos = [p[1] if isinstance(p, tuple) else p for p in e.get("Pos") or []]
                found.append((set(tags), pos))
    out = {}
    for r in recs:
        tag = tag_of(r["id"])
        x, y, z = (r["position"][k] + 0.5 if k != "y" else r["position"][k] for k in "xyz")
        mine = [p for tags, p in found if tag in tags]
        near = [p for p in mine if len(p) == 3 and ((p[0] - x) ** 2 + (p[1] - y) ** 2 + (p[2] - z) ** 2) ** 0.5 <= SPOT_RADIUS]
        out[r["id"]] = (len(mine), len(near), None)
    return out


def problems_from_counts(counts, withdrawn=()):
    out = []
    for rid, (total, on_spot, strays) in sorted(counts.items()):
        if rid in withdrawn:
            if total or strays:
                out.append((rid, "withdrawn under the stock policy, but %d tagged and %s untagged copies stand"
                            % (total, strays if strays is not None else "?")))
            continue
        if total == 0:
            out.append((rid, "absent: no entity carries %s" % tag_of(rid)))
        elif total > 1:
            out.append((rid, "%d copies carry %s; there must be one" % (total, tag_of(rid))))
        if total and not on_spot:
            out.append((rid, "not on its spot: none within %d blocks" % SPOT_RADIUS))
        if strays:
            out.append((rid, "%d untagged copies of it round the plaza" % strays))
    return out


def world_problems(doc, world_dir):
    """[(id, message)] for placed/verified traders missing, doubled or off their spot in a stopped world."""
    recs = [r for r in doc.get("traders") or [] if isinstance(r, dict) and r.get("status") in PLACED]
    return problems_from_counts(world_counts(world_dir, recs), {r["id"] for r in recs if r.get("stock") == "withdrawn"})


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--manifest", default=str(MANIFEST))
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("function")
    f.add_argument("--server-dir", default=os.environ.get("COBBLERS_SERVER_ROOT"),
                   help="the server whose packs hold the shopkeeper templates; defaults to $COBBLERS_SERVER_ROOT")
    f.add_argument("--out", default=str(DEFAULT_OUT))
    v = sub.add_parser("verify")
    g = v.add_mutually_exclusive_group(required=True)
    g.add_argument("--world")
    g.add_argument("--rcon", metavar="SERVER_DIR")
    v.add_argument("--settlement", action="append", help="only these towns (default: every trader in the manifest)")
    a = p.parse_args(argv)
    doc = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    placements = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    problems = static_problems(doc, placements, ROOT / "derived" / "towns")
    if problems:
        for rid, m in problems:
            print("ERROR %s: %s" % (rid, m))
        return 1
    recs = doc["traders"]
    if a.cmd == "function":
        if not a.server_dir:
            raise SystemExit("no server directory: pass --server-dir, or set COBBLERS_SERVER_ROOT")
        cache = {}
        entity = lambda t: cache.setdefault(t, entity_of(a.server_dir, t))
        out = Path(a.out)
        fdir = out / "data" / "cobblers" / "function" / "towns"
        fdir.mkdir(parents=True, exist_ok=True)
        (out / "pack.mcmeta").write_text(json.dumps(
            {"pack": {"pack_format": 48, "description": "Cobblers town traders (generated)"}}, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        policy = doc.get("stock_policy")
        for r in recs:
            _, kept, held = apply_stock_policy(dict(entity(r["template"])[1]), policy)
            want = "withdrawn" if kept == [] else "regional"
            if r.get("stock") != want:
                raise SystemExit("%s: data/traders.json says stock %r, but the stock policy leaves it %s (%d kept, %d "
                                 "withheld); record what it will actually be" % (r["id"], r.get("stock"), want, len(kept or []), len(held)))
        by_town = {}
        for r in recs:
            by_town.setdefault(r["settlement"], []).append(r)
        for town, trs in sorted(by_town.items()):
            for name, lines in town_functions(town, trs, entity, policy).items():
                refused = function_limits.check_lines(lines, name)
                if refused:
                    raise SystemExit("%s: %d command(s) the server would refuse" % (name, len(refused)))
                (fdir / ("%s.mcfunction" % name)).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
            print("wrote vendors_%s: %d traders" % (town, len(trs)))
        return 0
    if a.settlement:
        recs = [r for r in recs if r["settlement"] in a.settlement]
    leaks = {}
    counts = world_counts(a.world, recs) if a.world else rcon_counts(a.rcon, recs, policy=doc.get("stock_policy"), leaks=leaks)
    problems = problems_from_counts(counts, {r["id"] for r in recs if r.get("stock") == "withdrawn"})
    problems += [(rid, "still sells withheld stock: %s" % ", ".join(v)) for rid, v in sorted(leaks.items())]
    for rid, (total, on_spot, strays) in sorted(counts.items()):
        print("%-16s %d tagged, %d on its spot%s" % (rid, total, on_spot, "" if strays is None else ", %d untagged copies" % strays))
    for rid, m in problems:
        print("PROBLEM %s: %s" % (rid, m))
    print("%d traders checked, %d problems" % (len(counts), len(problems)))
    if not counts:
        # fail closed: a selection that matches no trader (a mistyped --settlement, an empty manifest) checked nothing
        print("PROBLEM: no trader was checked")
        return 1
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

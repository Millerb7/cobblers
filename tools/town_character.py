#!/usr/bin/env python
"""How much of each town is bespoke and how much is straight donor: the owner's check on whether a town has character.

The owner's brief (docs/world-building/TOWN_CHARACTER.md): "Measure how much of each town is bespoke versus straight
donor, as a check on whether it has character." Everything is read from data/placements.json and the templates it
names; nothing is read from a world.

Every placement of a settlement falls in one class:

  straight donor   a template placed as it came: a pack's own structure placed by resource id (a Cobbleverse gym, a
                   BCA or Mega Showdown building, a vanilla or Repurposed Structures piece), or a kit copy of one
                   (CobbleTowns, Repurposed Structures, vanilla and Cobblemon village houses) placed unchanged
  re-materialed    a donor's geometry in the town's own materials (data/placements.json `materials`)
  ruined           a donor's geometry broken by tools/ruins.py (`ruin`)
  bespoke          geometry generated for this place: an earthwork's commands (its tower, pier, wall, works), and the
                   dressing (data/town_dressing.json, tools/town_dressing.py)
  infrastructure   what every place gets and no place is known by: the street and plaza paving, and the lanterns
                   (`<settlement>_lights`); counted, but left out of the ratio

Block volume is the measure: the non-air blocks a template stores (air, structure voids and jigsaws are not
geometry), and the non-air blocks an earthwork's fill and setblock commands write (a fill that replaces only some
blocks is counted at its full volume, so an earthwork can only be over-counted, never a donor). The ratio is

  straight-donor share = straight donor blocks / (straight donor + re-materialed + ruined + bespoke blocks)

A template is read from its kit file when the checkout has it (kits/structures/incoming is local only, never
committed), else from the installed pack's own copy by resource id: the datapacks, then the mods, then the vanilla
jar, in the order the game resolves them. A template that cannot be read is reported as unmeasured, never guessed.

  python tools/town_character.py measure [--pack-dir <COBBLEVERSE instance>] [--vanilla-jar <1.21.1 client jar>]
  python tools/town_character.py measure --markdown          # the table TOWN_CHARACTER.md carries
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import nbt  # noqa: E402

NOT_GEOMETRY = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air", "minecraft:structure_void",
                "minecraft:jigsaw"}
CLASSES = ("straight_donor", "rematerialed", "ruined", "bespoke")


def default_pack_dir():
    """The local Cobbleverse instance, found the way tools/reapply.py finds its COBBLEVERSE-DP (beside the checkout)."""
    for base in (ROOT.parent.parent.parent, ROOT.parent, ROOT):
        if (base / "COBBLEVERSE").is_dir():
            return base / "COBBLEVERSE"
    return None


def default_vanilla_jar():
    appdata = os.environ.get("APPDATA", "")
    pats = [os.path.join(appdata, "ModrinthApp", "meta", "versions", "1.21.1-*", "1.21.1-*.jar"),
            os.path.join(appdata, ".minecraft", "versions", "1.21.1", "1.21.1.jar")]
    for pat in pats:
        hits = sorted(glob.glob(pat))
        if hits:
            return Path(hits[-1])
    return None


class Templates:
    """Structure templates by resource id: kit files first, then the pack's own copies in resolution order."""

    def __init__(self, pack_dir=None, vanilla_jar=None):
        self.archives = []
        if pack_dir and Path(pack_dir).is_dir():
            self.archives += sorted(glob.glob(str(Path(pack_dir) / "datapacks" / "*.zip")))
            self.archives += sorted(glob.glob(str(Path(pack_dir) / "mods" / "*.jar")))
        if vanilla_jar and Path(vanilla_jar).is_file():
            self.archives.append(str(vanilla_jar))
        self._zips = {}
        self._cache = {}

    def _zip(self, path):
        if path not in self._zips:
            try:
                self._zips[path] = zipfile.ZipFile(path)
            except (zipfile.BadZipFile, OSError):
                self._zips[path] = None
        return self._zips[path]

    def from_archives(self, entry):
        for a in self.archives:
            z = self._zip(a)
            if z is not None:
                try:
                    return nbt.loads(z.read(entry))[1], "%s!%s" % (Path(a).name, entry)
                except KeyError:
                    continue
        return None, None

    def get(self, rec):
        """(template compound, where it was read) for a placement record, or (None, reason)."""
        key = rec.get("file") or rec.get("pack_template") or rec.get("template")
        if key in self._cache:
            return self._cache[key]
        out = (None, "not found")
        f = rec.get("file")
        if f and (ROOT / f).is_file():
            out = (nbt.loads((ROOT / f).read_bytes())[1], f)
        else:
            entries = []
            src = (rec.get("donor_source") or {}).get("path")
            if src and src.endswith(".nbt"):
                entries.append(src)
            tid = rec.get("pack_template") or rec.get("template")
            if tid and ":" in tid:
                ns, path = tid.split(":", 1)
                entries += ["data/%s/structure/%s.nbt" % (ns, path), "data/%s/structures/%s.nbt" % (ns, path)]
            for e in entries:
                doc, where = self.from_archives(e)
                if doc is not None:
                    out = (doc, where)
                    break
        self._cache[key] = out
        return out


def template_blocks(doc):
    """Non-air blocks a template stores (air, structure voids and jigsaws are not geometry)."""
    pal = doc.get("palette") or (doc.get("palettes") or [[]])[0]
    names = [p["Name"] for p in pal]
    return sum(1 for b in doc["blocks"] if names[b["state"]] not in NOT_GEOMETRY)


CMD = re.compile(r"^(?:execute .* run )?(fill|setblock)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)(?:\s+(-?\d+)\s+(-?\d+)\s+(-?\d+))?\s+(\S+)")


def command_blocks(cmds):
    """Non-air blocks an earthwork's fill and setblock commands write (a replace-filtered fill at full volume)."""
    n = 0
    for c in cmds or []:
        m = CMD.match(c.strip())
        if not m:
            continue
        block = m.group(8).split("[")[0].split("{")[0]
        if block in NOT_GEOMETRY:
            continue
        if m.group(1) == "setblock":
            n += 1
        else:
            x0, y0, z0, x1, y1, z1 = (int(v) for v in m.group(2, 3, 4, 5, 6, 7))
            n += (abs(x1 - x0) + 1) * (abs(y1 - y0) + 1) * (abs(z1 - z0) + 1)
    return n


def classify(rec):
    if rec.get("kind") == "earthwork":
        return "infrastructure" if rec["id"].endswith("_lights") else "bespoke"
    if rec.get("ruin"):
        return "ruined"
    if rec.get("materials"):
        return "rematerialed"
    return "straight_donor"


def paving_cells(settlement, doc):
    """Street and plaza cells, from the town plan (tools/town_plan.py) when it exists, else None."""
    p = ROOT / "derived" / "towns" / ("%s_plan.json" % settlement)
    if not p.is_file():
        return None
    plan = json.loads(p.read_text(encoding="utf-8"))
    cells = set()
    for st in (plan.get("streets") or {}).values():
        for z, _y, x0, x1 in st.get("cells") or []:
            cells |= {(x, z) for x in range(x0, x1 + 1)}
    pz = plan.get("plaza")
    if pz and pz.get("rect"):
        x0, z0, x1, z1 = pz["rect"]
        cells |= {(x, z) for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)}
    return len(cells)


def dressing_blocks(settlement):
    """Blocks the dressing writes for a settlement, from its generated function (tools/town_dressing.py), if built."""
    fn = ROOT / "build" / "datapacks" / "cobblers_town_dressing" / "data" / "cobblers" / "function" / "town_dressing" / (
        "%s.mcfunction" % settlement)
    if not fn.is_file():
        return None
    return command_blocks(fn.read_text(encoding="utf-8").splitlines())


def measure(doc, towns, templates, with_dressing=True):
    rows = []
    for t in towns:
        sid = t["id"]
        recs = [q for q in doc["placements"] if q.get("settlement") == sid]
        row = {"id": sid, "tier": t.get("tier"), "placements": {c: 0 for c in CLASSES + ("infrastructure",)},
               "blocks": {c: 0 for c in CLASSES + ("infrastructure",)}, "unmeasured": [], "templates": {},
               "sources": {}}
        for q in recs:
            c = classify(q)
            row["placements"][c] += 1
            if q.get("kind") == "earthwork":
                row["blocks"][c] += command_blocks(q.get("commands"))
                continue
            tid = q.get("pack_template") or q.get("template")
            row["templates"][tid] = row["templates"].get(tid, 0) + 1
            tdoc, where = templates.get(q)
            if tdoc is None:
                row["unmeasured"].append(q["id"])
                continue
            row["blocks"][c] += template_blocks(tdoc)
            row["sources"][tid] = where
        if with_dressing:
            db = dressing_blocks(sid)
            if db:
                row["blocks"]["bespoke"] += db
                row["dressing_blocks"] = db
        pav = paving_cells(sid, doc)
        row["paving_cells"] = pav
        character = sum(row["blocks"][c] for c in CLASSES)
        row["character_blocks"] = character
        row["straight_donor_share"] = round(row["blocks"]["straight_donor"] / character, 3) if character else None
        row["distinct_templates"] = len(row["templates"])
        row["most_repeated"] = max(row["templates"].values()) if row["templates"] else 0
        rows.append(row)
    return rows


def pasted_rank(rows):
    """Most pasted first: straight-donor share, then fewer bespoke blocks, then more straight-donor placements."""
    def key(r):
        share = r["straight_donor_share"]
        return (-(share if share is not None else -1), r["blocks"]["bespoke"], -r["placements"]["straight_donor"])
    return sorted(rows, key=key)


def markdown(rows):
    out = ["| Rank | Place | Straight donor | Re-materialed | Ruined | Bespoke | Share straight donor | Placements (donor / rem. / ruin / bespoke) | Most repeated template | Paving cells | Unmeasured |",
           "| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: |"]
    for i, r in enumerate(pasted_rank(rows), 1):
        b, p = r["blocks"], r["placements"]
        share = "n/a" if r["straight_donor_share"] is None else "%.0f%%" % (100 * r["straight_donor_share"])
        out.append("| %d | `%s` | %s | %s | %s | %s | %s | %d / %d / %d / %d | %d | %s | %d |" % (
            i, r["id"], format(b["straight_donor"], ","), format(b["rematerialed"], ","), format(b["ruined"], ","),
            format(b["bespoke"], ","), share, p["straight_donor"], p["rematerialed"], p["ruined"], p["bespoke"],
            r["most_repeated"], "-" if r["paving_cells"] is None else format(r["paving_cells"], ","), len(r["unmeasured"])))
    return "\n".join(out)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("measure")
    q.add_argument("--pack-dir", default=default_pack_dir())
    q.add_argument("--vanilla-jar", default=default_vanilla_jar())
    q.add_argument("--markdown", action="store_true")
    q.add_argument("--no-dressing", action="store_true", help="measure the towns as they stood before the dressing")
    a = p.parse_args(argv)
    doc = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))
    towns = json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]
    rows = measure(doc, towns, Templates(a.pack_dir, a.vanilla_jar), with_dressing=not a.no_dressing)
    out = ROOT / "derived" / "town_character" / ("measure%s.json" % ("_before" if a.no_dressing else ""))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"pack_dir": str(a.pack_dir), "vanilla_jar": str(a.vanilla_jar), "towns": rows},
                              indent=1), encoding="utf-8")
    if a.markdown:
        print(markdown(rows))
    else:
        for r in pasted_rank(rows):
            print("%-22s share %-6s donor %8d rem %7d ruin %7d bespoke %7d unmeasured %d" % (
                r["id"], r["straight_donor_share"], r["blocks"]["straight_donor"], r["blocks"]["rematerialed"],
                r["blocks"]["ruined"], r["blocks"]["bespoke"], len(r["unmeasured"])))
    print("wrote", out, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

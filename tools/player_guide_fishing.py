"""The player guide's fishing page (docs/player/fishing.html): what bites where.

  python tools/player_guide_fishing.py [--check]

Reads data/spawns.json (the `fishing` entries tools/build_encounters.py expands from data/encounter_design.json, the
owner's 2026-10-16 ask: every area its own catch), data/spawns.json `subregions` and data/regions.json for the area
and region names, and data/spawns.json `marine_zones` for the sea bands' names. One section per region, one table per area: species,
how often it bites (Cobblemon's bucket), and its levels. Dungeon fishing and bait rooms are described in words: the
dungeon rooms are not catching yet (docs/STATE.md), and the bait table is data/dungeon_extras.json's design
(docs/mechanics/DUNGEON_BAIT.md). No legendary is on any fishing list (the builder's rule); the page also drops any
legendary-class species by the region map's own test, so it can never name one the map keeps secret.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import player_site  # noqa: E402

OUT = ROOT / "docs" / "player" / "fishing.html"
GUIDE = {"file": "fishing.html", "title": "Fishing", "label": "Fishing", "order": 38,
         "description": "What you can catch with a rod in every area and sea, how often it bites, and at what levels.",
         "generator": "tools/player_guide_fishing.py"}
BUCKETS = ("common", "uncommon", "rare", "ultra-rare")
BUCKET_WORDS = {"common": "Common", "uncommon": "Uncommon", "rare": "Rare", "ultra-rare": "Very rare"}
esc = player_site.esc


def _load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def is_legend(sp):
    """The site never names a legendary-class species (tools/player_guide_map.py _legend_class, the jar's labels)."""
    import player_guide_map as PM
    return PM._legend_class(sp)


def mon_name(sp):
    return " ".join(w.capitalize() for w in sp.replace("_", " ").split())


def collect():
    spawns = _load("spawns.json")
    regions = _load("regions.json")
    region_names = {}
    for r in regions.get("regions", []):
        if isinstance(r, dict) and r.get("id"):
            region_names[r["id"]] = r.get("display_name") or mon_name(r["id"])
    areas = {}
    for s in spawns.get("subregions", []):
        areas[s["id"]] = (s.get("display_name") or mon_name(s["id"]),
                          region_names.get(s.get("region"), mon_name(s.get("region") or "elsewhere")))
    for zone in spawns.get("marine_zones", []):   # every sea, the Windward Sea included, with its bands' own names
        for b in zone.get("bands", []):
            areas.setdefault(b["id"], (b.get("display_name") or mon_name(b["id"]), "The seas"))
    by_area = defaultdict(list)
    for e in spawns["entries"]:
        if e.get("spawnable_position") != "fishing" or is_legend(e["species"]):
            continue
        by_area[e["scope"]].append(e)
    regions_out = defaultdict(list)
    for scope, ents in by_area.items():
        name, region = areas.get(scope, (mon_name(scope), "Elsewhere"))
        rows = sorted(ents, key=lambda e: (BUCKETS.index(e["bucket"]) if e["bucket"] in BUCKETS else 9,
                                           -float(e.get("weight") or 0), e["species"]))
        regions_out[region].append({"id": scope, "name": name, "rows": rows})
    out = []
    for region in sorted(regions_out, key=lambda r: (r == "The seas", r)):
        out.append({"region": region, "areas": sorted(regions_out[region], key=lambda a: a["name"])})
    n_species = len({e["species"] for ents in by_area.values() for e in ents})
    return {"regions": out, "areas": len(by_area), "species": n_species,
            "entries": sum(len(v) for v in by_area.values())}


def render_area(a):
    rows = "".join('<tr data-fish data-name="%s"><td>%s</td><td><span class="bk %s">%s</span></td><td class="n">%s</td></tr>'
                   % (esc(" ".join((mon_name(e["species"]), a["name"], a.get("region", ""))).lower()), esc(mon_name(e["species"])),
                      esc(e["bucket"]), esc(BUCKET_WORDS.get(e["bucket"], e["bucket"])), esc(str(e.get("level", ""))))
                   for e in a["rows"])
    return ('<article class="area" id="%s" data-search-group><h3>%s</h3><table><thead><tr><th>Pokemon</th><th>How often</th>'
            '<th class="n">Levels</th></tr></thead><tbody>%s</tbody></table></article>'
            % (esc(a["id"]), esc(a["name"]), rows))


def render(m):
    sections = "".join('<section data-search-group><h2>%s</h2><div class="areas">%s</div></section>'
                       % (esc(r["region"]), "".join(render_area(dict(a, region=r["region"])) for a in r["areas"]))
                       for r in m["regions"])
    body = ('<main><h1>Fishing</h1><p class="lead">Every area with water has its own catch: the Pokemon you see '
            'swimming there, and a few you can only get with a rod. %d areas and seas, %d species. Search by Pokemon '
            'or place.</p>'
            '<div class="box"><p>How it works: cast a Poke Rod into water and wait for a bite. What bites depends on '
            'where your bobber lands, not where you stand. Rare and very rare Pokemon bite more often on a rod than '
            'you meet them on foot, so fishing is the best way to the rare end of an area. Shiny and alpha chances '
            'are Cobblemon\'s own. Bait on the rod is Cobblemon\'s own system too.</p></div>%s%s'
            '<section id="dungeons"><h2>Dungeons</h2><p>Some dungeons have a fishing room with a pool, a pier and a '
            'rod to borrow; what bites there depends on your band. These rooms are not catching yet: we are fixing '
            'them. Dungeon bait rooms are different: you set out a berry and the berry\'s rarity sets the odds that '
            'what comes is shiny or alpha (common berries 1%% shiny and 5%% alpha, up to 8%% and 20%% for the rarest).'
            '</p></section>'
            '<section id="not-covered"><h2>What this page leaves out</h2><ul>'
            '<li>Places outside our mapped areas: there, fishing is Cobblemon\'s default for the biome.</li>'
            '<li>Exact chances: "How often" is the bite\'s rarity group; within a group some Pokemon are more common '
            'than others.</li>'
            '<li>What happens in a running game: this is worked out from our data, not counted cast by cast. Where '
            'the game differs, the game is right: say so.</li></ul></section></main>'
            % (m["areas"], m["species"], player_site.search_box("[data-fish]", "Find a Pokemon or place",
                                                                 "e.g. Magikarp or Lake Viltri"), sections))
    sources = ('<p class="src">From data/spawns.json (%d fishing entries, expanded from data/encounter_design.json by '
               'tools/build_encounters.py), and data/regions.json.</p>' % m["entries"])
    return player_site.page(GUIDE, body, body_class="page-fishing", not_covered_href="#not-covered",
                            sources_html=sources)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default=str(OUT))
    p.add_argument("--check", action="store_true", help="exit 1 if the page or its guides.json entry is not current")
    a = p.parse_args(argv)
    m = collect()
    text = render(m)
    out = Path(a.out)
    entry = GUIDE if out.resolve() == OUT.resolve() else None
    counts = "%d areas, %d species, %d entries" % (m["areas"], m["species"], m["entries"])
    if a.check:
        ok, why = player_site.check(out, text, entry)
        if not ok:
            print("%s is %s: run python tools/player_site.py" % (out, why))
            return 1
        print("%s is current (%s)" % (out, counts))
        return 0
    did = player_site.write(out, text, entry)
    print("%s %s: %s, %d bytes" % (did, out, counts, len(text.encode("utf-8"))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

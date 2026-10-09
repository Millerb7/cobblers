"""docs/player/ is published as a public website (the owner hosts the folder on Coolify straight from the repo):
nothing in it may give away a discovery.

Every file under docs/player/ (html, json, css, js, anything) is read and must not carry an id, a name, a coordinate
or a line of text from the campaign's secrets:

  legendaries    data/legendaries.json, data/adopted_legendary_sites.json and the per-site legendary records
  residents/NPCs data/resident_encounters.json, data/northern_residents.json, data/southern_residents.json,
                 data/npc_seats.json and the single-resident sites
  shrines/caches data/shrines.json, data/rewards.json, data/sea_drift.json (its caches), and every data/placements.json
                 record whose id, template or kind names a legendary, shrine, cache, portal or resident
  portals        data/portals.json
  story          data/quests.json, data/dialogue.json, data/scenes.json and every data/rift_*.json
  discoveries    data/mega_dens.json, data/elder_trees.json, data/themed_saplings.json: the region map says it leaves
                 them for players to find, so the site must not show them either

THE FORBIDDEN SET IS READ FROM THOSE FILES, never typed here: a record added to any of them is covered the day it is
added. What is taken from a record (see `secrets()`):
  ids        a string under `id` (and the id-shaped keys in ID_KEYS) that contains an underscore, matched as a whole
             token in the raw text; a top-level record's id is also matched humanised ("old_jaw" -> "old jaw")
  names      a string under a name-shaped key (NAME_KEYS), matched as a whole phrase, case-insensitive
  species    the legendary files' `species` / `legendary` values, matched by name ("mew" -> "Mew", not "Mewtwo")
  coordinates every {x, z} dict, [x, y, z] list and [x, z] list (not under a range-shaped key, RANGE_KEY) of
             world-sized integers (max |x|, |z| >= 100), matched as an adjacent pair, or as x and z with one number
             between them that could be a y, anywhere in the text. Town centres and route centrelines a secret file
             repeats are public (public_coords())
  lines      every string of 40 or more characters under a text-shaped key (TEXT_KEYS), matched verbatim

A name that is public by design and also appears in a secret file is let through by ALLOW (public names, each also
in a public data file), ORDINARY_WORDS (a role word used in its ordinary sense) or PUBLIC_TOWN_CENTRES (a town centre
a secret file repeats), each entry with why; `test_allow_list_is_needed_and_public` fails if an entry stops being
needed or names nothing public, so the lists cannot quietly grow into a hole.

`test_every_secret_looking_data_file_is_read` fails when a new data/ file whose name says legendary, resident,
shrine, cache, portal, quest, dialogue, scene, reward, rift or mythical is not in SECRET_FILES or PUBLIC_FILES.

What this does NOT cover: a page that describes a secret in its own words without naming it ("a bird lives on the
north tower"), a coordinate rounded or offset from the record's, and secrets held only in kits/, docs/ or a
generator's constants rather than in data/. Those need a reader.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "docs" / "player"
DATA = ROOT / "data"

# (file or glob under data/, category). Legendary files also give species.
SECRET_FILES = (
    ("legendaries.json", "legendary"),
    ("adopted_legendary_sites.json", "legendary"),
    ("entei_boss.json", "legendary"),
    ("hoopa_cradle.json", "legendary"),
    ("sapling_celebi.json", "legendary"),
    ("spectrier_cap.json", "legendary"),
    ("mythical_starters.json", "legendary"),
    ("resident_encounters.json", "resident"),
    ("northern_residents.json", "resident"),
    ("southern_residents.json", "resident"),
    ("long_count.json", "resident"),
    ("npc_seats.json", "resident"),
    ("ursaluna_cave.json", "resident"),
    ("lopunny_house.json", "resident"),
    ("rookery.json", "resident"),
    ("shrines.json", "shrine"),
    ("rewards.json", "cache"),
    ("sea_drift.json", "cache"),
    ("portals.json", "portal"),
    ("quests.json", "story"),
    ("dialogue.json", "story"),
    ("scenes.json", "story"),
    ("rift_*.json", "story"),
    ("mega_dens.json", "discovery"),
    ("elder_trees.json", "discovery"),
    ("themed_saplings.json", "discovery"),
)
# data/ files whose NAME looks secret but whose content the site may show, with why.
PUBLIC_FILES = {
    "mega_borders.json": "the Mega Evolution border rules (which badges allow what), a battle rule the guides may state",
}
SECRET_WORDS = re.compile(r"legend|resident|shrine|cache|portal|quest|dialog|scene|reward|rift|mythical")
PLACEMENT_SECRET = re.compile(r"legendary|shrine|cache|portal|resident")

ID_KEYS = {"id", "npc_id", "quest_id", "dialogue_id", "conversation", "conversation_id", "external_event_id"}
NAME_KEYS = {"name", "display_name", "title", "working_name", "npc_name", "speaker_name"}
SPECIES_KEYS = {"species", "legendary", "legendaries"}
TEXT_KEYS = {"text", "message", "line", "lines", "say", "says", "body", "prompt", "story", "enter", "appear",
             "caught", "locked_message"}
# Arrays whose `name` labels a prop for the builder ("the old oak", "snow bank", "observation deck"), not a name a
# player is ever told: matching them fails pages on ordinary phrases. Their coordinates are still forbidden.
SCENERY = re.compile(r"\.(pieces|dressing|superseded_dressing)\[\d+\]$")
# Keys whose two-integer lists are a range or a size, not an [x, z] (surveyed over the secret files 2026-10-08).
RANGE_KEY = re.compile(r"^([xyz]|.*_[xyz]|.*height.*|.*length.*|.*range.*|.*levels?|every|border|span)$")
MIN_LINE = 40
MIN_COORD = 100

# Names and ids that a secret file mentions and that are public by design. Key: the name normalised (lowercase, words
# of letters and digits; an id "route_01_trainer_01" is keyed "route 01 trainer 01"). Each says why a player may see
# it, and each must also be a name or id in a public source (PUBLIC_SOURCES). Added from what the test found on
# 2026-10-08, never in advance.
_STARTER = ("a starter species: offered on the starter screen (modpack/config/cobblemon/starters.json) or a stage of "
            "a starter's own line (data/mythical_starters.json lines[].learnset_from), which the player raises")
_ROUTE_TRAINER_QUEST = ("a route trainer. data/quests.json carries a defeat-this-trainer quest under the trainer's own "
                        "id; the trainer is public by design: the battle guide lists every route fight and anchors it "
                        "#t-<id>, and the trainer stands on the road")
ALLOW: dict[str, str] = {
    **{i.replace("_", " "): _ROUTE_TRAINER_QUEST for i in (
        "route_01_trainer_01", "route_01_trainer_02", "route_01_trainer_03", "route_01_trainer_04",
        "route_02_trainer_01", "route_02_trainer_02", "route_02_trainer_03", "route_02_shore_trainer_01",
        "route_03_trainer_01", "route_03_trainer_02", "route_03_trainer_03", "route_03_trainer_04",
        "route_03_trainer_05")},
    "the rift": "the region the_rift (data/regions.json): the canyon at the centre of the map, whose wild areas the "
                "region map lists. data/rift_skin.json uses it as its biome id cobblers:the_rift; the Rift's story "
                "records stay forbidden",
    # the starters (the owner, 2026-10-08: "add a starter page"): every player picks one of these five on the starter
    # screen (modpack/config/cobblemon/starters.json) and raises it through its own line, so the species names are
    # public. data/mythical_starters.json stays a secret file: its research station, Director and dialogue stay out
    # Larvesta, the sixth (the owner, 2026-10-08), is also wild (data/spawns.json), so the region map names it too;
    # Smeargle, the seventh (the owner, 2026-10-08), likewise
    **{n: _STARTER for n in ("cosmog", "cosmoem", "kubfu", "poipole", "meltan", "larvesta", "smeargle")},
    # the eighth (the owner, 2026-10-08): the line Misdreavus -> Mismagius -> Flutter Mane. Flutter Mane is a paradox,
    # and paradoxes stay dungeon content (docs/STATE.md), but a starter's own final is public: the page names the line
    # it raises. Exactly the line's three members; no other paradox, and the drops page's paradox exclusion stands.
    **{n: _STARTER for n in ("misdreavus", "mismagius", "fluttermane")},
}
# Single ordinary English words that a secret file uses as an NPC's label (data/dialogue.json npc_name "Courier",
# "Guide") and that the pages use in their ordinary sense ("this guide", the route trainer "Night Courier"). Matching
# them would fail every page for a word, not a secret; the NPC's conversation, seat and quest stay forbidden.
ORDINARY_WORDS: dict[str, str] = {
    "guide": "the pages call themselves guides; dialogue.json's 'Guide' is an unnamed role, not a name",
    "courier": "the battle guide's route trainer 'Night Courier' (data/trainers.json display_name); "
               "dialogue.json's 'Courier' is an unnamed role",
}
# Towns whose centre a secret file repeats and which are public by design: data/npc_seats.json records each gym town's
# old stand marker at the town's centre, and the region map puts a labelled dot there. Resolved to coordinates from
# data/towns.json, so a town that moves stays covered; a town not listed here gets no exemption.
PUBLIC_TOWN_CENTRES: dict[str, str] = {
    **{"gym%d_town" % n: "gym town %d: on the critical path, every player walks into it for its gym" % n
       for n in range(1, 9)},
    "hometown": "the starting town",
    "league": "the Pokemon League, the end of the critical path",
}


def norm(s):
    return " ".join(re.findall(r"[a-z0-9]+", html.unescape(str(s)).lower()))


def _files():
    for pattern, cat in SECRET_FILES:
        hits = sorted(DATA.glob(pattern))
        assert hits, "SECRET_FILES names data/%s and nothing matches it" % pattern
        for f in hits:
            yield f, cat


def _ints(v, n):
    return isinstance(v, list) and len(v) == n and all(isinstance(i, int) and not isinstance(i, bool) for i in v)


def _coord(v, key):
    if isinstance(v, dict) and isinstance(v.get("x"), int) and isinstance(v.get("z"), int) \
            and not isinstance(v.get("x"), bool) and not isinstance(v.get("z"), bool):
        return v["x"], v["z"]
    if _ints(v, 3) and -64 <= v[1] <= 320:
        return v[0], v[2]
    if _ints(v, 2) and not RANGE_KEY.search(key):  # [x, z]: portals' `at`, polylines, centres
        return v[0], v[1]
    return None


def _walk(node, path, out, src, cat):
    key = re.sub(r"\[\d+\]", "", path).rsplit(".", 1)[-1]
    c = _coord(node, key)
    if c and max(abs(c[0]), abs(c[1])) >= MIN_COORD:
        out["coords"].setdefault(c, src + ":" + path)
    if isinstance(node, dict):
        depth = path.count("[")
        for k, v in node.items():
            sub = "%s.%s" % (path, k) if path else k
            if isinstance(v, str):
                if k in ID_KEYS and "_" in v and len(v) >= 5:
                    out["ids"].setdefault(v.lower(), src + ":" + sub)
                    if depth == 1:
                        out["names"].setdefault(norm(v), src + ":" + sub)
                if k in NAME_KEYS and len(norm(v)) >= 4 and not SCENERY.search(path):
                    out["names"].setdefault(norm(v), src + ":" + sub)
            if k in SPECIES_KEYS and cat == "legendary":
                vals = v if isinstance(v, list) else [v.get("id")] if isinstance(v, dict) else [v]
                for s in vals:  # "cobblemon:mew", "Necrozma (Dawn Wings)", "type_null": the species word
                    words = s.split(":")[-1].split() if isinstance(s, str) else []
                    first = words[0].lower().strip("(),.") if words else ""
                    for form in {re.sub(r"[^a-z0-9]", "", first), norm(first)}:
                        if len(form) >= 3:
                            out["names"].setdefault(form, src + ":" + sub)
            if k in TEXT_KEYS:
                for line in ([v] if isinstance(v, str) else v if isinstance(v, list) else []):
                    if isinstance(line, str) and len(line) >= MIN_LINE:
                        out["lines"].setdefault(norm(line), src + ":" + sub)
            _walk(v, sub, out, src, cat)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _walk(v, "%s[%d]" % (path, i), out, src, cat)


def secrets():
    """{kind: {value: where it came from}} for ids, names, coords and lines, read from the secret files."""
    out = {"ids": {}, "names": {}, "coords": {}, "lines": {}}
    for f, cat in _files():
        _walk(json.loads(f.read_text(encoding="utf-8")), "", out, "data/" + f.name, cat)
    placements = json.loads((DATA / "placements.json").read_text(encoding="utf-8"))
    for i, p in enumerate(placements["placements"]):
        if PLACEMENT_SECRET.search(" ".join(str(p.get(k) or "") for k in ("id", "template", "kind")).lower()):
            _walk(p, "placements[%d]" % i, out, "data/placements.json", "placement")
    return out


def page_text(raw):
    """A page's text as the checks see it: inline images and other data: URIs removed (base64 is not content),
    entities decoded."""
    return html.unescape(re.sub(r"data:[\w/+.-]+;base64,[A-Za-z0-9+/=]+", "", raw))


def _pairs(text):
    """Every (a, b) of integers adjacent in the text, or with one integer between them that could be a y (-64..320:
    an x y z triple's x and z). Adjacent means separated by at most 12 characters, none a digit or a newline."""
    toks = [(int(m.group()), m.start(), m.end()) for m in re.finditer(r"(?<![\w.])-?\d+(?![\w.])", text)]
    near = [0 < toks[i + 1][1] - toks[i][2] <= 12 and "\n" not in text[toks[i][2]:toks[i + 1][1]]
            for i in range(len(toks) - 1)]
    out = set()
    for i in range(len(toks) - 1):
        if near[i]:
            out.add((toks[i][0], toks[i + 1][0]))
            if i + 2 < len(toks) and near[i + 1] and -64 <= toks[i + 1][0] <= 320:
                out.add((toks[i][0], toks[i + 2][0]))
    return out


def public_coords():
    """Coordinates that are public by design even when a secret file repeats them: the PUBLIC_TOWN_CENTRES' centres
    (the region map labels them) and every vertex of a route's centreline in data/routes.json (the region map draws
    it). Mega dens' approach points and the Rift zones' guards were laid out ON those lines, so they repeat vertices;
    the page draws the line and says nothing of what stands on it."""
    towns = {t["id"]: t for t in json.loads((DATA / "towns.json").read_text(encoding="utf-8"))["towns"]}
    coords = {(towns[t]["centre"]["x"], towns[t]["centre"]["z"]) for t in PUBLIC_TOWN_CENTRES if t in towns}
    for r in json.loads((DATA / "routes.json").read_text(encoding="utf-8"))["routes"]:
        coords.update((p["x"], p["z"]) for p in ((r.get("corridor") or {}).get("polyline") or []))
    # the fights' stands: every leader, Elite Four and Champion spawner the battle guide places
    # (data/challenge_mode.json spawner.at / single_leader.normal_at). data/rift_zones.json repeats the League's five
    # since the z4 re-cut (league.spawners), which made the battle guide's own League stands read as a Rift secret
    def stands(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "spawner" and isinstance(v, dict) and isinstance(v.get("at"), list):
                    coords.add((v["at"][0], v["at"][2]))
                elif k == "normal_at" and isinstance(v, list):
                    coords.add((v[0], v[2]))
                stands(v)
        elif isinstance(node, list):
            for v in node:
                stands(v)
    stands(json.loads((DATA / "challenge_mode.json").read_text(encoding="utf-8")))
    return coords


def allowed():
    """(names, coordinates) let through: ALLOW and ORDINARY_WORDS, and public_coords()."""
    return set(ALLOW) | set(ORDINARY_WORDS), public_coords()


def leaks(raw, sec, allow=None):
    """The secrets a page's text carries: [(kind, value, source)]. `allow` is (names, coordinates); default
    allowed()."""
    names_ok, coords_ok = allowed() if allow is None else allow
    text = page_text(raw)
    low = text.lower()
    words = " " + norm(text) + " "
    tokens = set(re.findall(r"[a-z0-9_]+", low))
    found = []
    for v, src in sec["ids"].items():
        seg = re.split(r"[:/]", v)[-1]  # "cobblers:leg_mew" is matched by its path, the part a page would show
        if seg in tokens and norm(seg) not in names_ok:
            found.append(("id", v, src))
    for v, src in sec["names"].items():
        if v and v not in names_ok and (" " + v + " ") in words:
            found.append(("name", v, src))
    for v, src in sec["lines"].items():
        if v in words:
            found.append(("line", v[:60], src))
    pairs = _pairs(text)
    for c, src in sec["coords"].items():
        if c in pairs and c not in coords_ok:
            found.append(("coordinate", "%d %d" % c, src))
    return sorted(found)


def site_files():
    return sorted(p for p in SITE.rglob("*") if p.is_file())


@pytest.fixture(scope="module")
def sec():
    return secrets()


def test_the_forbidden_set_is_not_empty(sec):
    # a walker that found nothing would pass every page; these floors are far under today's counts
    assert len(sec["ids"]) > 200 and len(sec["names"]) > 100 and len(sec["coords"]) > 200 and len(sec["lines"]) > 200, \
        {k: len(v) for k, v in sec.items()}


@pytest.mark.parametrize("path", site_files(), ids=lambda p: p.relative_to(SITE).as_posix())
def test_no_public_page_leaks_a_secret(path, sec):
    found = leaks(path.read_text(encoding="utf-8", errors="replace"), sec)
    assert not found, "%s carries %d secret(s):\n  %s" % (
        path.relative_to(ROOT).as_posix(), len(found), "\n  ".join("%s %r from %s" % f for f in found[:40]))


def test_every_secret_looking_data_file_is_read():
    read = {f.name for f, _c in _files()}
    missing = [f.name for f in sorted(DATA.glob("*.json"))
               if SECRET_WORDS.search(f.name) and f.name not in read and f.name not in PUBLIC_FILES]
    assert not missing, "data/ files that look secret and are neither read nor declared public: %s" % missing


# Where an ALLOW entry must also appear (a name, display name or id) for the test to accept it as public.
PUBLIC_SOURCES = ("data/towns.json", "data/trainers.json", "data/routes.json", "data/regions.json",
                  "data/nuzlocke_zones.json")


def _public_names():
    names = set()

    def grab(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("id", "name", "display_name", "working_name") and isinstance(v, str):
                    names.add(norm(v))
                    names.update(norm(w) for w in v.split())
                grab(v)
        elif isinstance(node, list):
            for v in node:
                grab(v)

    for rel in PUBLIC_SOURCES:
        grab(json.loads((ROOT / rel).read_text(encoding="utf-8")))
    # the starter screen's species and the stages of their own lines: what a player is handed and raises
    screen = json.loads((ROOT / "modpack" / "config" / "cobblemon" / "starters.json").read_text(encoding="utf-8"))
    offered = {norm(p.split()[0]) for c in screen["starters"] for p in c["pokemon"]}
    names |= offered
    lines = json.loads((ROOT / "data" / "mythical_starters.json").read_text(encoding="utf-8"))["lines"]
    for ln in lines:
        chain = [norm(s) for s in ln.get("learnset_from") or []]
        if chain and chain[0] in offered:
            names.update(chain)
    return names


# Without it the starter allowance could grow past the starter lines (another paradox, a legendary) on the strength of
# a public source elsewhere: every entry given the _STARTER reason must be offered on the starter screen or be a stage
# of an offered line (data/mythical_starters.json learnset_from), nothing else. (Independent review, 2026-10-08.)
def test_the_starter_allowance_is_exactly_the_starter_lines():
    screen = json.loads((ROOT / "modpack" / "config" / "cobblemon" / "starters.json").read_text(encoding="utf-8"))
    offered = {norm(p.split()[0]) for c in screen["starters"] for p in c["pokemon"]}
    chains = set(offered)
    for ln in json.loads((DATA / "mythical_starters.json").read_text(encoding="utf-8"))["lines"]:
        chain = [norm(s) for s in ln.get("learnset_from") or []]
        if chain and chain[0] in offered:
            chains.update(chain)
    starter = {n for n, why in ALLOW.items() if why == _STARTER}
    assert starter <= chains, "starter allowance outside the starter lines: %s" % sorted(starter - chains)
    assert {"misdreavus", "mismagius", "fluttermane"} <= starter


def test_allow_list_is_needed_and_public(sec):
    forbidden = set(sec["names"]) | {norm(re.split(r"[:/]", i)[-1]) for i in sec["ids"]}
    stale = [n for n in list(ALLOW) + list(ORDINARY_WORDS) if n not in forbidden]
    assert not stale, "allow entries no secret file names any more (remove them): %s" % stale
    public = _public_names()
    unsourced = [n for n in ALLOW if n not in public]
    assert not unsourced, "ALLOW entries in no public source (%s): %s" % (", ".join(PUBLIC_SOURCES), unsourced)
    assert all(re.fullmatch(r"[a-z]+", w) for w in ORDINARY_WORDS), "ORDINARY_WORDS holds single words only"
    towns = {t["id"]: t for t in json.loads((DATA / "towns.json").read_text(encoding="utf-8"))["towns"]}
    gone = [t for t in PUBLIC_TOWN_CENTRES if t not in towns or "centre" not in towns[t]]
    assert not gone, "PUBLIC_TOWN_CENTRES names towns data/towns.json does not centre: %s" % gone


def test_the_check_bites(sec):
    """A page carrying one secret of each kind fails, and the same page without them passes."""
    names_ok, coords_ok = allowed()
    name = next(v for v in sec["names"] if v not in names_ok and len(v.split()) >= 2)
    ident = next(v for v in sec["ids"] if ":" not in v and norm(v) not in names_ok and norm(v) not in sec["names"])
    (x, z) = next(c for c in sec["coords"] if c not in coords_ok)
    line = next(iter(sec["lines"]))
    clean = "<p>Route 1 has Pidgey.</p>"
    assert leaks(clean, sec) == []
    for bad, kind in (("<p>%s</p>" % name.title(), "name"), ('<a id="t-%s">' % ident, "id"),
                      ("<code>%d 64 %d</code>" % (x, z), "coordinate"), ('"label":[%d,%d]' % (x, z), "coordinate"),
                      ("<p>%s</p>" % line.capitalize(), "line")):
        assert any(f[0] == kind for f in leaks(clean + bad, sec)), (kind, bad)

"""The player guide's Nuzlocke tracker (docs/player/nuzlocke.html): every catch zone, in the order you meet them.

  python tools/player_guide_nuzlocke.py [--check]

The owner, 2026-10-21: "for a nuzlocke can we make a site on the website to track pokemon caught per region, make the
regions close to how many encounters you'd get in a normal rom hack."

WHAT IS READ, NEVER TYPED
  data/nuzlocke_zones.json     the zones (88 today: land, sea, waterway, cave, site), their tier, region and the order
                               each route leg meets them (`legs`). A later merge of zones there is a data change only:
                               this page draws whatever zones the file holds.
  data/spawns.json             each zone's spawnable species: the entries whose `scope` is the zone (a cave's `pools`),
                               ambient, weight above 0, and not a heart entry (hearts are a discovery; tools/
                               nuzlocke_zones.py counts species the same way and this tool checks its own count
                               against the file's `species` before dropping legendary-class species)
  data/encounter_design.json   the cap each tier is built under (rules.tiers), which places the zones that have no
                               tier of their own (sea, waterway, site) by their lowest level
  data/regions.json            region names
  the Cobblemon jar            species names, the legendary-class labels the site never names, and each species'
                               `evolutions` and `preEvolution`, from which the dupes clause's evolution lines are
                               computed here at build time (the page ships a line number per species, not the jar)
  the RCT series               the level cap for each badge count: tools/player_guide_battles.py level_caps(), the same
                               figure the battle guide prints (rctmod's rule), Normal and Challenge being equal

THE PAGE keeps the player's tracker in the browser (localStorage, a per-viewer convenience): status per zone (Caught,
Failed, Skipped, unset), a species picker drawn from the zone's own list, a nickname, and counts. A species whose
evolution line is already Caught or Failed in another zone shows as a dupe in every other zone's picker. Storage is
wrapped in try/catch everywhere; with storage unavailable the page works for the visit and says so. Export, Import and
Reset buttons move or clear the state.

SPOILERS. The page names no legendary-class species (the region map's own test, the jar's labels), no heart entry and
nothing from an elder tree or sapling site (a discovery: its pools are not in a zone's scope). tests/
test_player_site_leaks.py reads the finished page.

Not verified: the page has not been opened in a browser from this tool; the script was checked for syntax only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import player_site  # noqa: E402

OUT = ROOT / "docs" / "player" / "nuzlocke.html"
GUIDE = {"file": "nuzlocke.html", "title": "Nuzlocke tracker", "label": "Nuzlocke", "order": 39,
         "description": "Every catch zone in the order you meet it, with a tracker for your Nuzlocke: caught, failed "
                        "or skipped, the species and nickname, the dupes clause and the level cap.",
         "generator": "tools/player_guide_nuzlocke.py"}
esc = player_site.esc
POS_BIT = {"grounded": 1, "surface": 2, "submerged": 2, "seafloor": 2, "fishing": 4}
KIND_WORDS = {"land": "Land", "sea": "Open sea", "waterway": "Waterway", "cave": "Cave", "site": "Special place"}
FORM_WORDS = {"alolan": "Alolan", "galarian": "Galarian", "hisuian": "Hisuian", "paldean": "Paldean"}
SPECIAL_NAMES = {"mrmime": "Mr. Mime", "mimejr": "Mime Jr.", "mrrime": "Mr. Rime", "farfetchd": "Farfetch'd",
                 "sirfetchd": "Sirfetch'd", "nidoranf": "Nidoran F", "nidoranm": "Nidoran M", "porygonz": "Porygon-Z",
                 "hooh": "Ho-Oh", "jangmoo": "Jangmo-o", "hakamoo": "Hakamo-o", "kommoo": "Kommo-o",
                 "typenull": "Type: Null"}
_DEX = []


def _load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def dex():
    """The dungeon guide's Dex over the Cobblemon jar (names and the legendary-class labels), built once."""
    if not _DEX:
        import player_guide_battles as PB
        import player_guide_dungeons as PG
        _DEX.append(PG.Dex(PB.find_jar()))
    return _DEX[0]


def zone_key(zone_id):
    """The page's opaque key for a zone (DOM id, tracker key): a hash of the data id, stable while the id is. The data
    ids of Victory Road's zones are ids of secret records elsewhere (data/rewards.json), which the leak test matches as
    tokens, so the page never prints an id."""
    return "z" + hashlib.sha1(zone_id.encode("utf-8")).hexdigest()[:8]


def base_of(sp):
    return re.sub(r"[^a-z0-9]", "", sp.split()[0].split(":")[-1].lower())


def mon_name(sp):
    """Display name of a spawn-table species ("rattata alolan" -> "Alolan Rattata")."""
    parts = sp.split()
    base = parts[0]
    d = dex()
    try:
        name = d.name(base)
    except SystemExit:
        name = base.replace("_", " ").title()
    name = SPECIAL_NAMES.get(base_of(sp), name)
    return " ".join([FORM_WORDS.get(p, p.title()) for p in parts[1:]] + [name])


def evolution_lines(species, jar=None):
    """{species id: evolution-line number} for the given species ids, from the Cobblemon jar's species files.

    An edge joins a species to each `evolutions[].result` and to its `preEvolution` (form blocks included: Alolan
    Raichu is Raichu's). A line is a connected component, so Eevee, Vaporeon and Jolteon share one and Pichu, Pikachu
    and Raichu share one, which is what the dupes clause means by "the same evolution line". Line numbers are
    assigned over the given species only, in their sorted order; no species outside the list is named."""
    if jar is None:
        import player_guide_battles as PB
        jar = PB.find_jar()
    z = zipfile.ZipFile(jar)
    parent = {}

    def find(a):
        parent.setdefault(a, a)
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        parent[find(a)] = find(b)

    for n in z.namelist():
        m = re.fullmatch(r"data/cobblemon/species/[^/]+/([a-z0-9_]+)\.json", n)
        if not m:
            continue
        me = base_of(m.group(1))
        doc = json.loads(z.read(n).decode("utf-8"))
        blocks = [doc] + [f for f in doc.get("forms") or [] if isinstance(f, dict)]
        for b in blocks:
            if b.get("preEvolution"):
                union(me, base_of(str(b["preEvolution"])))
            for ev in b.get("evolutions") or []:
                if isinstance(ev, dict) and ev.get("result"):
                    union(me, base_of(str(ev["result"])))
    roots, out = {}, {}
    for sp in sorted({base_of(s) for s in species}):
        out[sp] = roots.setdefault(find(sp), len(roots))
    return out


def badge_caps():
    """[(label, cap)] for 0..8 badges, then after the Elite Four and after the Champion: the cap rctmod holds while the
    player heads to the next trainer of the chain (tools/player_guide_battles.py level_caps, the battle guide's own)."""
    import player_guide_battles as PB
    import route_trainers as RT
    import challenge_mode_audit as CA
    up = CA.Upstream()
    order, caps, _titles, rule = PB.level_caps(RT.files(), sorted(up.series_members("kanto")))
    normal = caps["normal"]
    out = []
    for b in range(9):
        out.append(("%d badge%s" % (b, "" if b == 1 else "s"), normal[order[b]]))
    out.append(("Elite Four beaten", normal[order[-1]]))
    out.append(("Champion beaten", rule["after_champion"]))
    return out


def _levels(entries):
    lo, hi = [], []
    for e in entries:
        a, _, b = str(e["level"]).partition("-")
        lo.append(int(a))
        hi.append(int(b or a))
    return [min(lo), max(hi)] if lo else None


def collect(caps=None):
    nz = _load("nuzlocke_zones.json")
    spawns = _load("spawns.json")
    regions = _load("regions.json")
    design = _load("encounter_design.json")
    tier_cap = {int(k): int(v["cap"]) for k, v in design["rules"]["tiers"].items()}
    d = dex()

    region_name = {r["id"]: r["display_name"] for r in regions["regions"]}
    region_name.update({r["id"]: r["display_name"] for r in regions.get("marine_regions", [])})
    by_name = {v: k for k, v in region_name.items()}
    region_name["waterways"] = "Waterways"

    scope_entries = defaultdict(list)
    for e in spawns["entries"]:
        if e.get("ambient") and e.get("weight", 0) > 0 and not e.get("heart"):
            scope_entries[e["scope"]].append(e)

    # the order a leg meets each zone: (leg number, place on the leg); a waterway by the first leg it touches
    leg_ids = [lg["route"] for lg in nz["legs"]]
    met = {}
    for i, lg in enumerate(nz["legs"]):
        for j, z in enumerate(lg["zones"]):
            met.setdefault(z["zone"], (i, j))

    def derived_tier(lo):
        for n in sorted(tier_cap):
            if tier_cap[n] >= lo:
                return n
        return max(tier_cap)

    zones, dropped, mismatched = [], defaultdict(int), []
    for z in nz["zones"]:
        scopes = z.get("pools") or [z["zone"]]
        rows = [e for s in scopes for e in scope_entries.get(s, [])]
        if len({e["species"] for e in rows}) != z["species"]:
            mismatched.append(z["zone"])
        kept = []
        for e in rows:
            if d.is_legend(base_of(e["species"])):
                dropped[z["zone"]] += 1       # the site never names a legendary-class species
                continue
            kept.append(e)
        mons = {}
        for e in kept:
            mons[e["species"]] = mons.get(e["species"], 0) | POS_BIT.get(e.get("spawnable_position"), 1)
        lv = _levels(kept)
        tier = z.get("tier")
        tier_is_own = tier is not None
        if tier is None:
            tier = derived_tier(lv[0]) if lv else 9
        if z["zone"] in met:
            place = met[z["zone"]]
        else:
            idx = [leg_ids.index(r) for r in z.get("legs") or [] if r in leg_ids]
            place = (min(idx), 500) if idx else None
        if z["kind"] == "cave":
            place = (leg_ids.index("victory_road"), 100) if "victory_road" in leg_ids else place
        region = z.get("region") or by_name.get(z.get("subtitle")) or "waterways"
        zones.append({"id": z["zone"], "key": zone_key(z["zone"]), "kind": z["kind"], "name": z["name"], "subtitle": z["subtitle"],
                      "region": region, "tier": tier, "tier_own": tier_is_own, "cap": tier_cap[tier],
                      "levels": lv, "on_path": place is not None, "place": place or (99, 0), "mons": mons})
    if mismatched:
        raise SystemExit("data/spawns.json and data/nuzlocke_zones.json disagree on the species count of %s: "
                         "regenerate data/nuzlocke_zones.json (python tools/nuzlocke_zones.py)" % mismatched)
    zones.sort(key=lambda z: (z["tier"], 0 if z["on_path"] else 1, z["place"], z["name"]))
    for i, z in enumerate(zones, 1):
        z["no"] = i

    species = sorted({s for z in zones for s in z["mons"]})
    lines = evolution_lines(species)
    mons = {s: [mon_name(s), lines[base_of(s)]] for s in species}

    first = {}
    for z in zones:
        first.setdefault(z["region"], z["no"])
    groups = []
    for rid in sorted(first, key=first.get):
        groups.append({"id": rid, "name": region_name.get(rid, rid.replace("_", " ").title()),
                       "zones": [z for z in zones if z["region"] == rid]})
    caps = caps if caps is not None else badge_caps()
    return {"groups": groups, "zones": zones, "mons": mons, "caps": caps, "tier_cap": tier_cap,
            "counts": nz["counts"], "dropped": dict(dropped), "total": len(zones)}


def band_words(z):
    n = z["tier"]
    if n >= 9:
        return "Victory Road, cap %d" % z["cap"] if z["tier_own"] else "Late game, cap %d" % z["cap"]
    return "Before gym %d (%d badge%s), cap %d" % (n, n - 1, "" if n == 2 else "s", z["cap"])


def how_words(mask):
    parts = []
    if mask & 1:
        parts.append("on land")
    if mask & 2:
        parts.append("on or in water")
    if mask & 4:
        parts.append("by rod")
    return ", ".join(parts)


def render_zone(z, mons):
    lv = ("Levels %d-%d" % tuple(z["levels"]) if z["levels"][0] != z["levels"][1] else "Level %d" % z["levels"][0]) \
        if z["levels"] else "No wild Pokemon listed"
    names = sorted(((mons[s][0], s, m) for s, m in z["mons"].items()))
    items = "".join('<li>%s <span class="nz-how">%s</span></li>' % (esc(n), esc(how_words(m))) for n, _s, m in names)
    status = "".join('<button type="button" data-s="%s" aria-pressed="false">%s</button>' % (k, t)
                     for k, t in (("caught", "Caught"), ("failed", "Failed"), ("skipped", "Skipped"), ("", "Unset")))
    return ('<article class="nz-zone" id="z-%s" data-nz="%s" data-name="%s" data-lo="%d">'
            '<h3><span class="nz-no">#%d</span> %s <small>%s</small></h3>'
            '<p class="nz-meta">%s &middot; %s &middot; %s<span class="nz-over" hidden> &middot; <b>above your cap</b></span></p>'
            '<div class="nz-ctl"><div class="nz-status" role="group" aria-label="Status of %s">%s</div>'
            '<select class="nz-sp" aria-label="Species met in %s"></select>'
            '<input class="nz-other" type="text" maxlength="40" placeholder="Species (not on the list)" '
            'aria-label="Other species in %s" hidden>'
            '<input class="nz-nick" type="text" maxlength="40" placeholder="Nickname" aria-label="Nickname in %s">'
            '<p class="nz-note" aria-live="polite"></p></div>'
            '<details class="nz-list"><summary>What lives here (%d)</summary><ul>%s</ul></details></article>'
            % (esc(z["key"]), esc(z["key"]), esc(" ".join((z["name"], z["subtitle"] or "")).lower()),
               z["levels"][0] if z["levels"] else 0, z["no"], esc(z["name"]), esc(z["subtitle"] or ""),
               esc(KIND_WORDS[z["kind"]]), esc(lv), esc(band_words(z)), esc(z["name"]), status, esc(z["name"]),
               esc(z["name"]), esc(z["name"]), len(z["mons"]), items))


SCRIPT = r"""
(function () {
  var data = JSON.parse(document.getElementById('nz-data').textContent);
  var KEY = 'cobblers-nuzlocke-v1', STATUS = ['caught', 'failed', 'skipped'];
  var zones = {}, order = data.zones;
  order.forEach(function (z) { zones[z.id] = z; });
  var state = { v: 1, badges: 0, zones: {} }, canStore = true, filter = 'all';

  function $(s, r) { return (r || document).querySelector(s); }
  function all(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function clip(s) { return String(s == null ? '' : s).slice(0, 40); }

  function read() {
    try { var t = localStorage.getItem(KEY); return t ? JSON.parse(t) : null; } catch (e) { canStore = false; return null; }
  }
  function write() {
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { canStore = false; }
    var w = $('#nz-warn'); if (w) w.hidden = canStore;
  }
  function clean(raw) {
    var out = { v: 1, badges: 0, zones: {} };
    if (!raw || typeof raw !== 'object' || !raw.zones || typeof raw.zones !== 'object') return null;
    var b = parseInt(raw.badges, 10);
    if (b >= 0 && b < data.caps.length) out.badges = b;
    Object.keys(raw.zones).forEach(function (id) {
      var r = raw.zones[id];
      if (!zones[id] || !r || typeof r !== 'object') return;
      var e = { s: STATUS.indexOf(r.s) >= 0 ? r.s : '', sp: data.mons[r.sp] ? r.sp : '', other: clip(r.other), nick: clip(r.nick) };
      if (e.s || e.sp || e.other || e.nick) out.zones[id] = e;
    });
    return out;
  }
  function rec(id) { return state.zones[id] || (state.zones[id] = { s: '', sp: '', other: '', nick: '' }); }

  // the dupes clause: evolution lines already Caught or Failed in some zone, with where and what
  function used() {
    var u = {};
    order.forEach(function (z) {
      var r = state.zones[z.id];
      if (r && (r.s === 'caught' || r.s === 'failed') && r.sp) {
        var line = data.mons[r.sp][1];
        if (!u[line]) u[line] = { zone: z.name, mon: data.mons[r.sp][0], s: r.s, id: z.id };
      }
    });
    return u;
  }
  function opt(v, t, sel) {
    var o = document.createElement('option'); o.value = v; o.textContent = t; if (sel) o.selected = true; return o;
  }
  function group(t) { var g = document.createElement('optgroup'); g.label = t; return g; }

  function drawZone(card, u) {
    var z = zones[card.getAttribute('data-nz')], r = state.zones[z.id] || { s: '', sp: '', other: '', nick: '' };
    all('.nz-status button', card).forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.getAttribute('data-s') === r.s));
    });
    card.setAttribute('data-state', r.s || 'unset');
    var sel = $('.nz-sp', card), fresh = [], dupes = [];
    z.mons.forEach(function (m) {
      var info = data.mons[m[0]], line = u[info[1]];
      if (line && line.id !== z.id) dupes.push([m[0], info[0] + ' - dupe of ' + line.mon + ' (' + line.s + ', ' + line.zone + ')']);
      else fresh.push([m[0], info[0]]);
    });
    while (sel.firstChild) sel.removeChild(sel.firstChild);
    sel.appendChild(opt('', 'Species met...', !r.sp && !r.other));
    var g1 = group('On this zone\'s list'); fresh.forEach(function (x) { g1.appendChild(opt(x[0], x[1], r.sp === x[0])); });
    sel.appendChild(g1);
    if (dupes.length) {
      var g2 = group('Dupes: this line is already used'); dupes.forEach(function (x) { g2.appendChild(opt(x[0], x[1], r.sp === x[0])); });
      sel.appendChild(g2);
    }
    sel.appendChild(opt('__other', 'Other (a site or event catch)...', !r.sp && !!r.other));
    var oth = $('.nz-other', card); oth.hidden = !(sel.value === '__other'); oth.value = r.other || '';
    var nick = $('.nz-nick', card); if (document.activeElement !== nick) nick.value = r.nick || '';
    var skipped = r.s === 'skipped';
    sel.hidden = skipped; nick.hidden = skipped; if (skipped) oth.hidden = true;
    var note = $('.nz-note', card), msg = '';
    if (!skipped && z.mons.length && dupes.length === z.mons.length) msg = 'Every species here is a dupe: under the dupes clause the first encounter is free to re-roll.';
    else if (!skipped && dupes.length) msg = dupes.length + ' of ' + z.mons.length + ' here are dupes.';
    note.textContent = msg;
    var cap = data.caps[state.badges][1], over = z.lo > cap;
    $('.nz-over', card).hidden = !over;
    var show = filter === 'all' || (filter === 'open' ? !r.s : r.s === filter);
    card.hidden = !show;
  }
  function draw() {
    var u = used(), c = { caught: 0, failed: 0, skipped: 0 };
    order.forEach(function (z) { var r = state.zones[z.id]; if (r && c[r.s] !== undefined) c[r.s]++; });
    $('#nz-caught').textContent = c.caught; $('#nz-failed').textContent = c.failed;
    $('#nz-skipped').textContent = c.skipped;
    $('#nz-left').textContent = order.length - c.caught - c.failed - c.skipped;
    $('#nz-cap').textContent = data.caps[state.badges][1];
    $('#nz-badges').value = String(state.badges);
    all('.nz-zone').forEach(function (card) { drawZone(card, u); });
    all('.nz-region').forEach(function (s) { s.hidden = !s.querySelector('.nz-zone:not([hidden])'); });
    var names = Object.keys(u).map(function (k) { return u[k].mon + ' (' + u[k].s + ')'; });
    $('#nz-used').textContent = names.length ? names.join(', ') : 'none yet';
  }
  function commit() { write(); draw(); }

  function wire() {
    all('.nz-zone').forEach(function (card) {
      var id = card.getAttribute('data-nz');
      all('.nz-status button', card).forEach(function (b) {
        b.addEventListener('click', function () { rec(id).s = b.getAttribute('data-s'); commit(); });
      });
      $('.nz-sp', card).addEventListener('change', function (e) {
        var r = rec(id);
        if (e.target.value === '__other') { r.sp = ''; } else { r.sp = e.target.value; r.other = ''; }
        if (r.sp && !r.s) r.s = 'caught';
        commit();
      });
      $('.nz-other', card).addEventListener('input', function (e) { rec(id).other = clip(e.target.value); write(); });
      $('.nz-nick', card).addEventListener('input', function (e) { rec(id).nick = clip(e.target.value); write(); });
    });
    $('#nz-badges').addEventListener('change', function (e) { state.badges = parseInt(e.target.value, 10) || 0; commit(); });
    all('[data-nzf]').forEach(function (b) {
      b.addEventListener('click', function () {
        filter = b.getAttribute('data-nzf');
        all('[data-nzf]').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
        draw();
      });
    });
    $('#nz-export').addEventListener('click', function () {
      try {
        var blob = new Blob([JSON.stringify(state, null, 2)], { type: 'application/json' });
        var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'nuzlocke-run.json';
        document.body.appendChild(a); a.click(); document.body.removeChild(a);
      } catch (e) { alert('Could not export: ' + e); }
    });
    $('#nz-import').addEventListener('change', function (e) {
      var f = e.target.files && e.target.files[0]; if (!f) return;
      var rd = new FileReader();
      rd.onload = function () {
        var n = null;
        try { n = clean(JSON.parse(String(rd.result))); } catch (x) { n = null; }
        if (!n) { alert('That file is not a Nuzlocke export from this page.'); return; }
        state = n; commit();
      };
      rd.readAsText(f); e.target.value = '';
    });
    $('#nz-reset').addEventListener('click', function () {
      var ok = true; try { ok = confirm('Clear every zone and start a new run?'); } catch (x) {}
      if (!ok) return;
      state = { v: 1, badges: state.badges, zones: {} }; commit();
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    var s = clean(read()); if (s) state = s;
    try { localStorage.setItem(KEY + '-probe', '1'); localStorage.removeItem(KEY + '-probe'); } catch (e) { canStore = false; }
    var w = $('#nz-warn'); if (w) w.hidden = canStore;
    wire(); draw();
  });
})();
"""


def js_data(m):
    """The data the script needs: zones (id, name, lowest level, [species key, how] rows), species (name, line), caps."""
    doc = {"zones": [{"id": z["key"], "name": z["name"], "lo": z["levels"][0] if z["levels"] else 0,
                      "mons": [[s, z["mons"][s]] for s in sorted(z["mons"])]} for z in m["zones"]],
           "mons": m["mons"], "caps": [[a, b] for a, b in m["caps"]]}
    return json.dumps(doc, separators=(",", ":"), ensure_ascii=True).replace("<", "\\u003c")


def render(m):
    mons = m["mons"]
    sections = "".join(
        '<section class="nz-region" data-search-group><h2>%s <small>%d zone%s</small></h2><div class="nz-zones">%s</div>'
        '</section>' % (esc(g["name"]), len(g["zones"]), "" if len(g["zones"]) == 1 else "s",
                        "".join(render_zone(z, mons) for z in g["zones"]))
        for g in m["groups"])
    caps = "".join('<option value="%d">%s: cap %d</option>' % (i, esc(a), b) for i, (a, b) in enumerate(m["caps"]))
    kinds = m["counts"]
    kind_words = ", ".join("%d %s" % (kinds[k], w) for k, w in
                           (("land", "land"), ("sea", "sea"), ("cave", "cave"), ("waterway", "waterway"),
                            ("site", "special place")) if kinds.get(k))
    filters = "".join('<button type="button" data-nzf="%s" aria-pressed="%s">%s</button>'
                      % (k, "true" if k == "all" else "false", t)
                      for k, t in (("all", "All"), ("open", "Not decided"), ("caught", "Caught"),
                                   ("failed", "Failed"), ("skipped", "Skipped")))
    body = (
        '<main><h1>Nuzlocke tracker</h1><p class="lead">%d catch zones in the order you meet them, grouped by region: '
        '%s. In a Nuzlocke the first wild Pokemon you meet in each zone is your only catch there.</p>'
        '<div class="box"><p><b>Rules this page helps with.</b> One catch per zone. A Pokemon that faints is gone. '
        'The dupes clause: if the first Pokemon you meet is from an evolution line you have already Caught or Failed, '
        'it is a dupe and you may meet another; the species list in each zone marks those for you. Your own Nuzlocke '
        'rules decide the rest: this page keeps score and enforces nothing.</p>'
        '<p>Your progress is saved in this browser only. Use Export to keep a copy or to move it to another device.</p>'
        '</div>'
        '<div class="box nz-warn" id="nz-warn" hidden><p><b>This browser is not letting the page save.</b> Your '
        'choices work until you leave; use Export before you go.</p></div>'
        '<noscript><div class="box warn"><p>The tracker needs JavaScript. The zones and their species are listed below '
        'without it.</p></div></noscript>'
        '<div class="nz-bar" role="status"><span>Caught <b id="nz-caught">0</b></span>'
        '<span>Failed <b id="nz-failed">0</b></span><span>Skipped <b id="nz-skipped">0</b></span>'
        '<span>Remaining <b id="nz-left">%d</b></span></div>'
        '<div class="nz-cap"><label for="nz-badges">Badges you hold</label> <select id="nz-badges">%s</select> '
        '<span>Level cap now: <b id="nz-cap">%d</b>. A Pokemon above your cap breaks free from every ball.</span></div>'
        '<div class="filter nz-filter" aria-label="Show zones">%s</div>%s'
        '<p class="nz-used">Evolution lines used (Caught or Failed): <span id="nz-used">none yet</span></p>'
        '<div class="nz-tools"><button type="button" id="nz-export">Export</button>'
        '<label class="nz-file">Import <input type="file" id="nz-import" accept="application/json,.json"></label>'
        '<button type="button" id="nz-reset">Reset</button></div>'
        '%s'
        '<section id="not-covered"><h2>What this page leaves out</h2><ul>'
        '<li>Legendary and mythical Pokemon, and anything you find by exploring (hearts, elder trees, saplings and other '
        'discoveries): the page lists each zone\'s ordinary wild Pokemon only. A catch from one of those places goes '
        'under "Other" in the species box.</li>'
        '<li>Dungeons, the Nether and the trainers\' own Pokemon: not catch zones here.</li>'
        '<li>Which Pokemon you will meet first: the list is what can appear, not what will. Rod catches count as the '
        'zone\'s first encounter only if you decide your rules say so.</li>'
        '<li>Zone borders: a zone is a place the game titles when you enter it; where the borders run is in-game, not '
        'drawn here. See the region map for the wild areas.</li>'
        '<li>Whether it works in a running game: the zones come from our data, not from a play-through. Where the game '
        'differs, the game is right: say so.</li></ul></section>'
        '<script id="nz-data" type="application/json">%s</script></main>'
        % (m["total"], esc(kind_words), m["total"], caps, m["caps"][0][1], filters,
           player_site.search_box("[data-nz]", "Find a zone", "e.g. Mt Clay or Viltri", ident="nz-find"), sections,
           js_data(m)))
    sources = ('<p class="src">From data/nuzlocke_zones.json, data/spawns.json and data/encounter_design.json; '
               'evolution lines from the Cobblemon jar; level caps from the battle guide\'s own rule.</p>')
    return player_site.page(GUIDE, body, body_class="page-nuzlocke", not_covered_href="#not-covered",
                            sources_html=sources, end_html="<script>%s</script>\n" % SCRIPT)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default=str(OUT))
    p.add_argument("--check", action="store_true", help="exit 1 if the page or its guides.json entry is not current")
    a = p.parse_args(argv)
    m = collect()
    text = render(m)
    out = Path(a.out)
    entry = GUIDE if out.resolve() == OUT.resolve() else None
    counts = "%d zones, %d species, %d legendary-class rows left out" % (
        m["total"], len(m["mons"]), sum(m["dropped"].values()))
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

"""Independent audit of the town ambient Pokemon composition (data/ambient.json key `composition`).

Two layers:

DATA, from the town files alone (data/ambient_towns/<settlement>.json). Every count is RE-DERIVED from the
records (working = len(workers), pets = len(pets), placed = len(placed), situations = the sum of every
situation member's `count`); the file's own `counts` is a claim that is checked, never an input.

PLACEMENT, from the generator's output (derived/ambient/idle_plan.json and derived/ambient/plan.json by
default): positions per Pokemon, with kind and town. When no output exists the placement checks report
NOT_CHECKED by name; they never pass. The in-view check samples its own grid over each town's plan footprint
(derived/towns/<t>_plan.json `footprint` [x0, z0, x1, z1]), one sample per block, never the generator's cells.

Independence: nothing is imported from tools/ambient.py or tools/ambient_idle.py. Every threshold is read
from the rules file at run time and each check records the key it came from (`derived_from`). The one
threshold stated only in prose -- the situations floor -- is parsed out of `composition.ratios.why`
("situations never under 0.30"), or read from `composition.ratios.situations_min` if the owner adds it; if
neither is there the check fails with that reason rather than assuming a number.

Interpretations, stated rather than hidden:
  * Mining towns: `working_min` replaces the working band (a 50% floor cannot coexist with 0.30 +- 0.08);
    pets, placed and situations keep their bands and the situations floor.
  * Species identity is the species id of a Cobblemon properties string, without namespace or aspects
    ("cobblemon:mrmime galarian" -> "mrmime"); a form counts as its species for variety and for the jar
    lookup, which keys the jar's display names the same way ("Mr. Mime" -> "mrmime").
  * Prop identity is the block id without state or NBT, namespaced ("rose_bush[half=lower]" ->
    "minecraft:rose_bush").
  * Distances: same-species uses 3D distance; in-view uses horizontal distance (a stricter count: a Pokemon
    on a roof above the sample point is still drawn). "Within r" is inclusive (d <= r).
  * Placement rules apply to the towns in `composition.scope`; plan entries for other places (Pallet, the
    farm) are listed in the report and still count toward a scope town's in-view sample if they are near.
  * A plan entry's position is `at`, else its route `points`, else a stationary worker's `start`, else `pos`.
  * A plan entry with a route (`points`) is counted at every point of its route: in view if any point is
    within the radius of a sample, near another if any two points are within the group radius.

Not covered (needs the game): whether anything spawns, renders, keeps its pose, or holds frame rate; the
server cost of AI-on kinds (named unmeasured in composition.ceiling.why); whether a pet's owner NPC exists
in the world; whether a `size` label is honest about the town's building count.

  python tools/ambient_composition_audit.py
  python tools/ambient_composition_audit.py --towns-dir <dir> --plan <file> [--plan <file>] --rules <file>

Writes the full report (default derived/ambient/composition_audit.json) and prints one summary line plus the
failures. Exit 0 when every check passed; 1 when any failed; 2 when none failed but some were NOT_CHECKED or
SKIPPED (an unchecked layer is never reported as a pass).
"""
from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RULES = ROOT / "data" / "ambient.json"
DEFAULT_TOWNS = ROOT / "data" / "ambient_towns"
DEFAULT_PLANS = [ROOT / "derived" / "ambient" / "idle_plan.json", ROOT / "derived" / "ambient" / "plan.json"]
DEFAULT_TOWN_PLANS = ROOT / "derived" / "towns"
DEFAULT_ATM = ROOT / "modpack" / "manifest" / "client-pack-atm-subset.json"
DEFAULT_REPORT = ROOT / "derived" / "ambient" / "composition_audit.json"

# Where the Cobblemon 1.8.0 jar lives, the way tools/battle_sim.py find_jar() looks: the experiment runtime
# in this checkout, then any worktree's copy of the same runtime folder.
JAR_NAME = "Cobblemon-fabric-1.8*.jar"
JAR_DIRS = [ROOT / "experiments" / "EXP-000-cobblemon-1.8-compat" / "runtime" / "server" / "mods"]
JAR_WORKTREE_GLOB = (Path(r"C:\Users\wnd\Documents\github\cobblers") / ".claude" / "worktrees",
                     "*/experiments/EXP-000-cobblemon-1.8-compat/runtime/server/mods/" + JAR_NAME)

# Town-file list key -> the composition share it fills.
KINDS = {"workers": "working", "pets": "pets", "placed": "placed", "situations": "situations"}
PASS, FAIL, NOT_CHECKED, SKIPPED = "PASS", "FAIL", "NOT_CHECKED", "SKIPPED"
EPS = 1e-9


# ---------------------------------------------------------------- normalisation

def rel(p) -> str:
    """A path as the repo names it when it is inside the repo, else as given."""
    try:
        return Path(p).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


def species_key(name, properties=True) -> str:
    """An authored species, written as a Cobblemon properties string ('cobblemon:mrmime galarian'), keys to
    its species id ('mrmime'): namespace and aspects dropped. A jar display name ('Mr. Mime', 'Type: Null')
    is keyed with properties=False, which keeps every word. The gender signs survive as f/m (nidoranf)."""
    s = str(name or "").strip().lower()
    if properties:
        s = re.sub(r"^[a-z0-9_.\-]+:(?=\S)", "", s)
        s = s.split()[0] if s.split() else ""
    s = s.replace("\u2640", "f").replace("\u2642", "m")
    return re.sub(r"[^a-z0-9]", "", s)


def block_key(block) -> str:
    b = re.sub(r"[\[{].*$", "", str(block or "").strip().lower())
    return b if ":" in b else "minecraft:" + b


def title_key(title) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(title or "").lower()).split())


def enum_from_schema(text: str, field: str) -> list[str]:
    """The allowed values the schema text lists for a field, e.g. 'mode: follow | wait' -> [follow, wait]."""
    m = re.search(re.escape(field) + r":\s*([a-z_]+(?:\s*\|\s*[a-z_]+)+)", text or "")
    return [v.strip() for v in m.group(1).split("|")] if m else []


# ---------------------------------------------------------------- rules

def load_rules(path: Path) -> dict:
    """The thresholds, each with the key it came from. Raises SystemExit if a rule cannot be read as written."""
    comp = json.loads(Path(path).read_text(encoding="utf-8"))["composition"]
    ratios = comp["ratios"]
    floor = ratios.get("situations_min")
    floor_from = "composition.ratios.situations_min"
    if floor is None:
        m = re.search(r"situations never under\s*([0-9.]+)", ratios.get("why", ""))
        floor = float(m.group(1)) if m else None
        floor_from = "composition.ratios.why: 'situations never under %s'" % (m.group(1) if m else "?")
    fields = comp.get("town_file", {}).get("fields", {})
    return {
        "source": str(path),
        "scope": list(comp["scope"]),
        "per_town": comp["ceiling"]["per_town"],
        "in_view_max": comp["ceiling"]["in_view_max"],
        "in_view_radius": comp["ceiling"]["in_view_radius"],
        "scale": {k: v for k, v in comp["scale"].items() if k != "why"},
        "targets": {k: ratios[k] for k in KINDS.values()},
        "tolerance": ratios["tolerance"],
        "situations_floor": floor,
        "situations_floor_from": floor_from,
        "mining": list(comp["mining_towns"]["settlements"]),
        "working_min": comp["mining_towns"]["working_min"],
        "max_towns_per_species": comp["variety"]["max_towns_per_species"],
        "max_roster_overlap": comp["variety"]["max_roster_overlap"],
        "group_radius": comp["variety"]["same_species_group_radius"],
        "pet_modes": enum_from_schema(fields.get("pets", ""), "mode"),
        "spots": enum_from_schema(fields.get("placed", ""), "spot"),
        "poses": enum_from_schema(fields.get("situations", ""), "pose"),
    }


def share_ok(n, total, kind, rules, mining) -> bool:
    s = n / total
    if kind == "working" and mining:
        return s >= rules["working_min"] - EPS
    ok = abs(s - rules["targets"][kind]) <= rules["tolerance"] + EPS
    if kind == "situations":
        ok = ok and s >= rules["situations_floor"] - EPS
    return ok


def feasible_totals(lo: int, hi: int, rules: dict, mining: bool) -> dict:
    """Which totals in [lo, hi] admit ANY integer split that satisfies the share rules as written."""
    out = {}
    for n in range(max(lo, 1), hi + 1):
        for w in range(n + 1):
            if not share_ok(w, n, "working", rules, mining):
                continue
            hit = None
            for p in range(n + 1 - w):
                if not share_ok(p, n, "pets", rules, mining):
                    continue
                for pl in range(n + 1 - w - p):
                    s = n - w - p - pl
                    if share_ok(pl, n, "placed", rules, mining) and share_ok(s, n, "situations", rules, mining):
                        hit = [w, p, pl, s]
                        break
                if hit:
                    break
            if hit:
                out[n] = hit
                break
    return out


# ---------------------------------------------------------------- data layer

def roster(town: dict) -> set:
    out = set()
    for key in ("workers", "pets", "placed"):
        for r in town.get(key) or []:
            if isinstance(r, dict) and species_key(r.get("species")):
                out.add(species_key(r.get("species")))
    for s in town.get("situations") or []:
        for m in (s.get("members") or []) if isinstance(s, dict) else []:
            if isinstance(m, dict) and species_key(m.get("species")):
                out.add(species_key(m.get("species")))
    return out


def derive_counts(town: dict) -> dict:
    c = {"working": len(town.get("workers") or []), "pets": len(town.get("pets") or []),
         "placed": len(town.get("placed") or [])}
    sit = 0
    for s in town.get("situations") or []:
        for m in (s.get("members") or []) if isinstance(s, dict) else []:
            n = m.get("count") if isinstance(m, dict) else None
            sit += n if isinstance(n, int) and not isinstance(n, bool) and n > 0 else 0
    c["situations"] = sit
    c["total"] = sum(c.values())
    return c


def check(name, layer, derived_from, problems, status=None, **extra) -> dict:
    return {"check": name, "layer": layer, "status": status or (FAIL if problems else PASS),
            "derived_from": derived_from, "problems": problems, **extra}


def load_towns(towns_dir: Path, rules: dict):
    """(towns {id: doc}, problems) for the scope; also flags files outside scope and unreadable files."""
    towns, problems = {}, []
    files = {p.stem: p for p in sorted(Path(towns_dir).glob("*.json"))} if Path(towns_dir).is_dir() else {}
    for t in rules["scope"]:
        if t not in files:
            problems.append(f"{t}: no town file {rel(Path(towns_dir) / (t + '.json'))}")
            continue
        try:
            doc = json.loads(files[t].read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            problems.append(f"{t}: does not parse ({e})")
            continue
        if not isinstance(doc, dict):
            problems.append(f"{t}: not a JSON object")
            continue
        if doc.get("settlement") != t:
            problems.append(f"{t}: file says settlement {doc.get('settlement')!r}")
        towns[t] = doc
    for stem in sorted(set(files) - set(rules["scope"])):
        problems.append(f"{stem}: town file outside composition.scope")
    return towns, problems


def check_fields(towns: dict, rules: dict) -> list:
    problems = []
    if not (rules["pet_modes"] and rules["spots"] and rules["poses"]):
        return ["cannot derive the allowed pet modes / placed spots / situation poses from "
                "composition.town_file.fields; the schema text no longer lists them as 'a | b'"]
    for t, doc in towns.items():
        if doc.get("size") not in rules["scale"]:
            problems.append(f"{t}: size {doc.get('size')!r} is not one of {sorted(rules['scale'])}")
        ids = []
        for key in KINDS:
            recs = doc.get(key)
            if recs is None:
                recs = []
            if not isinstance(recs, list):
                problems.append(f"{t}: {key} is not a list")
                continue
            for i, r in enumerate(recs):
                where = f"{t}: {key}[{i}]"
                if not isinstance(r, dict):
                    problems.append(f"{where} is not an object")
                    continue
                ids.append(r.get("id"))
                if not r.get("id"):
                    problems.append(f"{where} has no id")
                if key != "situations" and not species_key(r.get("species")):
                    problems.append(f"{where} ({r.get('id')}) has no species")
                if key == "workers" and r.get("settlement") not in (None, t):
                    problems.append(f"{where} ({r.get('id')}) settlement {r.get('settlement')!r}")
                if key == "pets":
                    if r.get("mode") not in rules["pet_modes"]:
                        problems.append(f"{where} ({r.get('id')}) mode {r.get('mode')!r} not in {rules['pet_modes']}")
                    if not r.get("owner"):
                        problems.append(f"{where} ({r.get('id')}) has no owner")
                if key == "placed":
                    if r.get("spot") not in rules["spots"]:
                        problems.append(f"{where} ({r.get('id')}) spot {r.get('spot')!r} not in {rules['spots']}")
                    if not r.get("building") and not r.get("at"):
                        problems.append(f"{where} ({r.get('id')}) has neither building nor at")
                if key == "situations":
                    if not r.get("title"):
                        problems.append(f"{where} ({r.get('id')}) has no title")
                    members = r.get("members")
                    if not isinstance(members, list) or not members:
                        problems.append(f"{where} ({r.get('id')}) has no members")
                        continue
                    for j, m in enumerate(members):
                        mw = f"{where} ({r.get('id')}) member {j}"
                        if not isinstance(m, dict):
                            problems.append(f"{mw} is not an object")
                            continue
                        n = m.get("count")
                        if not (isinstance(n, int) and not isinstance(n, bool) and n > 0):
                            problems.append(f"{mw} count {n!r} is not a positive integer")
                        elif len(m.get("offsets") or []) != n:
                            problems.append(f"{mw} count {n} but {len(m.get('offsets') or [])} offsets")
                        if not species_key(m.get("species")):
                            problems.append(f"{mw} has no species")
                        if m.get("pose") not in rules["poses"]:
                            problems.append(f"{mw} pose {m.get('pose')!r} not in {rules['poses']}")
        dup = sorted({i for i in ids if i and ids.count(i) > 1})
        if dup:
            problems.append(f"{t}: duplicate ids {dup}")
    return problems


def load_jar_species(jar: Path) -> set:
    out = set()
    with zipfile.ZipFile(jar) as z:
        for n in z.namelist():
            if n.startswith("data/cobblemon/species/") and n.endswith(".json"):
                d = json.loads(z.read(n))
                if d.get("implemented") is False:
                    continue
                out.add(species_key(d.get("name"), properties=False))
    return out


def find_jar(explicit):
    """(path or None, reason). An explicit --jar is never substituted by a search."""
    if explicit is not None:
        p = Path(explicit)
        return (p, "") if p.is_file() else (None, f"--jar {p} is not a file")
    for d in JAR_DIRS:
        hits = sorted(d.glob(JAR_NAME)) if d.is_dir() else []
        if hits:
            return hits[0], ""
    base, pattern = JAR_WORKTREE_GLOB
    hits = sorted(base.glob(pattern)) if base.is_dir() else []
    if hits:
        return hits[0], ""
    return None, ("no Cobblemon 1.8 jar found in experiments/EXP-000-cobblemon-1.8-compat/runtime/server/mods "
                  "or any worktree's copy; pass --jar")


def data_layer(rules, towns_dir, jar, jar_reason, atm):
    checks = []
    towns, scope_problems = load_towns(towns_dir, rules)
    checks.append(check("scope_files", "data", "composition.scope", scope_problems, towns=len(towns)))
    checks.append(check("fields", "data", "composition.town_file.fields (allowed modes, spots, poses parsed "
                        "from its text)", check_fields(towns, rules)))
    counts = {t: derive_counts(doc) for t, doc in towns.items()}

    p = []
    for t, doc in towns.items():
        claim = doc.get("counts")
        if not isinstance(claim, dict):
            p.append(f"{t}: no counts claim")
            continue
        for k, v in counts[t].items():
            if claim.get(k) != v:
                p.append(f"{t}: counts.{k} claims {claim.get(k)!r}, the records give {v}")
    checks.append(check("counts_claim", "data", "re-derived from workers, pets, placed and situation members", p))

    p = []
    for t, doc in towns.items():
        if doc.get("target") != counts[t]["total"]:
            p.append(f"{t}: target {doc.get('target')!r} but the records total {counts[t]['total']}")
    checks.append(check("target", "data", "composition.town_file.fields.target", p))

    p = []
    for t, doc in towns.items():
        band = rules["scale"].get(doc.get("size"))
        if band and not band[0] <= counts[t]["total"] <= band[1]:
            p.append(f"{t}: total {counts[t]['total']} outside the {doc.get('size')} band {band}")
    checks.append(check("size_band", "data", "composition.scale", p))

    p = [f"{t}: total {c['total']} over ceiling.per_town {rules['per_town']}"
         for t, c in counts.items() if c["total"] > rules["per_town"]]
    checks.append(check("ceiling", "data", "composition.ceiling.per_town", p))

    feas, ratio_p, floor_p, mine_p = {}, [], [], []
    for t, doc in towns.items():
        mining = t in rules["mining"]
        band = rules["scale"].get(doc.get("size"))
        if band and rules["situations_floor"] is not None:
            feas[t] = {"band": band, "mining": mining,
                       "feasible": {str(k): v for k, v in feasible_totals(band[0], band[1], rules, mining).items()}}
        n = counts[t]["total"]
        none_fit = t in feas and not feas[t]["feasible"]
        why = (f" (no total in the {doc.get('size')} band {band} admits an integer split under these rules"
               f"{' for a mining town' if mining else ''})") if none_fit else ""
        if n == 0:
            ratio_p.append(f"{t}: total 0, no shares")
            continue
        for kind in KINDS.values():
            if kind == "working" and mining:
                continue
            s = counts[t][kind] / n
            if abs(s - rules["targets"][kind]) > rules["tolerance"] + EPS:
                ratio_p.append(f"{t}: {kind} {counts[t][kind]}/{n} = {s:.3f}, outside "
                               f"{rules['targets'][kind]} +- {rules['tolerance']}{why}")
        s = counts[t]["situations"] / n
        if rules["situations_floor"] is None:
            floor_p.append(f"{t}: the situations floor cannot be read from {rules['situations_floor_from']}")
        elif s < rules["situations_floor"] - EPS:
            floor_p.append(f"{t}: situations {counts[t]['situations']}/{n} = {s:.3f}, under "
                           f"{rules['situations_floor']}{why}")
        if mining:
            w = counts[t]["working"] / n
            if w < rules["working_min"] - EPS:
                mine_p.append(f"{t}: working {counts[t]['working']}/{n} = {w:.3f}, under "
                              f"working_min {rules['working_min']}{why}")
    checks.append(check("ratios", "data", "composition.ratios (targets, tolerance); a mining town's working "
                        "share is held to mining_towns.working_min instead", ratio_p))
    checks.append(check("situations_floor", "data", rules["situations_floor_from"], floor_p))
    checks.append(check("mining_working", "data", "composition.mining_towns", mine_p,
                        mining_in_scope=[t for t in rules["mining"] if t in towns]))

    p = [f"{t}: no situation marked unique: true" for t, doc in towns.items()
         if not any(isinstance(s, dict) and s.get("unique") is True for s in doc.get("situations") or [])]
    checks.append(check("unique_situation", "data", "composition.town_file.fields.situations (unique: true)", p))

    p, titles, sets = [], {}, {}
    for t, doc in towns.items():
        for s in doc.get("situations") or []:
            if not isinstance(s, dict):
                continue
            tk = title_key(s.get("title"))
            sp = frozenset(species_key(m.get("species")) for m in s.get("members") or [] if isinstance(m, dict))
            pr = frozenset(block_key(x.get("block")) for x in s.get("props") or [] if isinstance(x, dict))
            for key, seen, what in ((tk, titles, "title"), ((sp, pr), sets, "species and props")):
                for other_t, other_id in seen.get(key, []):
                    if other_t != t:
                        p.append(f"{t}/{s.get('id')} and {other_t}/{other_id} share the same {what}"
                                 + (f" ({s.get('title')!r})" if what == "title" else
                                    f" ({sorted(sp)}, {sorted(pr)})"))
                seen.setdefault(key, []).append((t, s.get("id")))
    checks.append(check("situations_distinct", "data", "composition.request: each town gets at least one "
                        "thing nobody else has (title, and species set with prop set)", p))

    rosters = {t: roster(doc) for t, doc in towns.items()}
    where = {}
    for t, r in rosters.items():
        for sp in r:
            where.setdefault(sp, []).append(t)
    p = [f"{sp} in {len(ts)} towns {sorted(ts)}, over {rules['max_towns_per_species']}"
         for sp, ts in sorted(where.items()) if len(ts) > rules["max_towns_per_species"]]
    checks.append(check("species_spread", "data", "composition.variety.max_towns_per_species", p))

    p, worst = [], 0.0
    for a, b in itertools.combinations(sorted(rosters), 2):
        u = rosters[a] | rosters[b]
        j = len(rosters[a] & rosters[b]) / len(u) if u else 0.0
        worst = max(worst, j)
        if j > rules["max_roster_overlap"] + EPS:
            p.append(f"{a} and {b}: roster Jaccard {len(rosters[a] & rosters[b])}/{len(u)} = {j:.3f}, over "
                     f"{rules['max_roster_overlap']} (shared {sorted(rosters[a] & rosters[b])})")
    checks.append(check("roster_overlap", "data", "composition.variety.max_roster_overlap", p,
                        worst=round(worst, 4)))

    all_species = sorted(where)
    if jar is None:
        checks.append(check("species_in_jar", "data", "the Cobblemon 1.8.0 jar's data/cobblemon/species",
                             [], status=SKIPPED, reason=jar_reason))
    else:
        known = load_jar_species(jar)
        p = [f"{sp} (in {sorted(where[sp])}) is not an implemented species in {Path(jar).name}"
             for sp in all_species if sp not in known]
        checks.append(check("species_in_jar", "data", f"{jar} data/cobblemon/species (implemented)", p))

    if atm is None or not Path(atm).is_file():
        checks.append(check("species_not_atm", "data", "modpack/manifest/client-pack-atm-subset.json species",
                             [], status=SKIPPED, reason=f"no ATM subset manifest at {atm}"))
    else:
        atm_species = {species_key(s) for s in json.loads(Path(atm).read_text(encoding="utf-8")).get("species", [])}
        p = [f"{sp} (in {sorted(where[sp])}) is in the ATM client-model subset" for sp in all_species
             if sp in atm_species]
        checks.append(check("species_not_atm", "data", f"{atm} species", p))
    if not towns:
        # Fail closed: a rule with no town to apply to has not passed.
        for c in checks[1:]:
            if c["status"] == PASS:
                c["status"], c["reason"] = NOT_CHECKED, "no town file loaded"
    return checks, towns, counts, feas


# ---------------------------------------------------------------- placement layer

def plan_entries(paths):
    """(entries, problems, read_paths). Accepts the shapes the ambient generators write: a `towns` map of
    town -> list, a `workers` list (town from `settlement`, kind 'worker'), and a flat `pokemon` or
    `entries` list. Each entry is normalised to {id, town, species, kind, situation, pts (N x 3)}."""
    entries, problems, read = [], [], []
    for path in paths:
        path = Path(path)
        if not path.is_file():
            continue
        read.append(str(path))
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            problems.append(f"{path.name}: does not parse ({e})")
            continue
        raw = []
        towns = doc.get("towns") if isinstance(doc, dict) else None
        if isinstance(towns, dict):
            for t, lst in towns.items():
                for e in lst if isinstance(lst, list) else []:
                    raw.append((e, t, None))
        for key, kind in (("workers", "worker"), ("pokemon", None), ("entries", None)):
            lst = doc.get(key) if isinstance(doc, dict) else None
            for e in lst if isinstance(lst, list) else []:
                raw.append((e, None, kind))
        if not raw:
            problems.append(f"{path.name}: no Pokemon found under towns / workers / pokemon / entries")
        for e, town, kind in raw:
            if not isinstance(e, dict):
                problems.append(f"{path.name}: an entry is not an object")
                continue
            t = e.get("town") or e.get("settlement") or town
            k = e.get("kind") or kind
            pts = []
            if isinstance(e.get("at"), list) and len(e["at"]) == 3:
                pts = [e["at"]]
            elif isinstance(e.get("points"), list):
                pts = [q for q in e["points"] if isinstance(q, list) and len(q) == 3]
            elif isinstance(e.get("start"), list) and len(e["start"]) == 3:   # a stationary worker
                pts = [e["start"]]
            elif isinstance(e.get("pos"), list) and len(e["pos"]) == 3:
                pts = [e["pos"]]
            name = f"{path.name}: {e.get('id')}"
            if not t or not k or not species_key(e.get("species")) or not pts:
                problems.append(f"{name} lacks " + ", ".join(
                    w for w, ok in (("town", t), ("kind", k), ("species", species_key(e.get("species"))),
                                    ("position", pts)) if not ok))
                continue
            entries.append({"id": e.get("id"), "town": t, "species": species_key(e.get("species")), "kind": k,
                            "situation": e.get("situation") or e.get("situation_id"),
                            "pts": np.unique(np.round(np.asarray(pts, dtype=float), 2), axis=0)})
    return entries, problems, read


def placement_layer(rules, plan_paths, town_plans_dir, towns, counts):
    names = ["plan_entries", "plan_counts", "same_species_radius", "in_view"]
    entries, problems, read = plan_entries(plan_paths)
    if not read:
        reason = "no generator output at " + ", ".join(rel(p) for p in plan_paths)
        return [check(n, "placement", "generator output", [], status=NOT_CHECKED, reason=reason) for n in names]
    checks = [check("plan_entries", "placement", "positions per Pokemon with kind and town", problems,
                    files=read, entries=len(entries))]

    by_town = {}
    for e in entries:
        by_town.setdefault(e["town"], []).append(e)
    p, unmatched = [], []
    for t in rules["scope"]:
        if t not in towns:
            unmatched.append(f"{t}: no town file to compare the plan with")
            continue
        got = len(by_town.get(t, []))
        if got != counts[t]["total"]:
            p.append(f"{t}: the plan places {got}, the town file's records total {counts[t]['total']}")
        want = {}
        for s in towns[t].get("situations") or []:
            if isinstance(s, dict):
                want[s.get("id")] = sum(m.get("count", 0) for m in s.get("members") or []
                                        if isinstance(m, dict) and isinstance(m.get("count"), int))
        have = {}
        for e in by_town.get(t, []):
            if e["situation"]:
                have[e["situation"]] = have.get(e["situation"], 0) + 1
        for sid in sorted(set(want) | set(have), key=str):
            if want.get(sid, 0) != have.get(sid, 0):
                p.append(f"{t}/{sid}: the plan tags {have.get(sid, 0)} as members, the file has {want.get(sid, 0)}")
    checks.append(check("plan_counts", "placement", "re-derived town file totals and situation member counts",
                        p, status=FAIL if p else (NOT_CHECKED if unmatched else PASS), not_checked=unmatched,
                        outside_scope=sorted(t for t in by_town if t not in rules["scope"])))

    r = rules["group_radius"]
    p = []
    for t, lst in sorted(by_town.items()):
        if t not in rules["scope"]:      # composition governs the scope; Pallet, the farm etc. are not in it
            continue
        for a, b in itertools.combinations(lst, 2):
            if a["species"] != b["species"]:
                continue
            if a["situation"] and a["situation"] == b["situation"]:
                continue
            d = np.sqrt(((a["pts"][:, None, :] - b["pts"][None, :, :]) ** 2).sum(-1)).min()
            if d <= r + EPS:
                p.append(f"{t}: {a['species']} {a['id']} ({a['kind']}) and {b['id']} ({b['kind']}) "
                         f"{d:.2f} blocks apart, within {r}, not members of one situation")
    checks.append(check("same_species_radius", "placement", "composition.variety.same_species_group_radius", p))

    R, cap = rules["in_view_radius"], rules["in_view_max"]
    p, not_checked, worst = [], [], {}
    for t in rules["scope"]:
        plan = Path(town_plans_dir) / f"{t}_plan.json"
        fp = None
        if plan.is_file():
            fp = json.loads(plan.read_text(encoding="utf-8")).get("footprint")
        if not (isinstance(fp, list) and len(fp) == 4):
            not_checked.append(f"{t}: no footprint in {rel(plan)}")
            continue
        x0, z0, x1, z1 = (int(v) for v in fp)
        gx, gz = np.meshgrid(np.arange(min(x0, x1), max(x0, x1) + 1) + 0.5,
                             np.arange(min(z0, z1), max(z0, z1) + 1) + 0.5, indexing="ij")
        n = np.zeros(gx.shape, dtype=int)
        for e in entries:
            q = e["pts"][:, [0, 2]]
            if (q[:, 0].max() < gx.min() - R or q[:, 0].min() > gx.max() + R
                    or q[:, 1].max() < gz.min() - R or q[:, 1].min() > gz.max() + R):
                continue
            seen = np.zeros(gx.shape, dtype=bool)
            for qx, qz in np.unique(q, axis=0):
                seen |= (gx - qx) ** 2 + (gz - qz) ** 2 <= R * R + EPS
            n += seen
        i = np.unravel_index(int(n.argmax()), n.shape)
        worst[t] = {"max": int(n.max()), "at": [float(gx[i]), float(gz[i])], "samples": int(n.size)}
        if n.max() > cap:
            p.append(f"{t}: {int(n.max())} Pokemon within {R} blocks of ({gx[i]:.1f}, {gz[i]:.1f}), over "
                     f"in_view_max {cap}; {int((n > cap).sum())} of {n.size} sample points over")
    status = FAIL if p else (NOT_CHECKED if not_checked else PASS)
    checks.append(check("in_view", "placement", "composition.ceiling.in_view_max / in_view_radius, sampled "
                        "one point per block over derived/towns/<t>_plan.json footprint", p, status=status,
                        not_checked=not_checked, worst=worst))
    return checks


# ---------------------------------------------------------------- run

def run(rules_path=DEFAULT_RULES, towns_dir=DEFAULT_TOWNS, plans=None, town_plans=DEFAULT_TOWN_PLANS,
        jar=None, atm=DEFAULT_ATM, layer="all") -> dict:
    rules = load_rules(rules_path)
    jar_path, jar_reason = find_jar(jar)
    checks, towns, counts, feas = data_layer(rules, towns_dir, jar_path, jar_reason, atm)
    if layer != "data":
        placement = placement_layer(rules, plans if plans else DEFAULT_PLANS, town_plans, towns, counts)
        checks = placement if layer == "placement" else checks + placement
    statuses = [c["status"] for c in checks]
    verdict = FAIL if FAIL in statuses else (NOT_CHECKED if (NOT_CHECKED in statuses or SKIPPED in statuses)
                                             else PASS)
    return {"verdict": verdict, "layer": layer, "rules": rules, "counts": counts, "feasibility": feas,
            "checks": checks}


def summary(report) -> str:
    parts = []
    for layer in ("data", "placement"):
        cs = [c for c in report["checks"] if c["layer"] == layer]
        if not cs:
            parts.append(f"{layer} not requested")
            continue
        tally = {s: sum(c["status"] == s for c in cs) for s in (PASS, FAIL, NOT_CHECKED, SKIPPED)}
        parts.append(f"{layer} " + ", ".join(f"{v} {k}" for k, v in tally.items() if v))
    return f"ambient composition audit: {report['verdict']} ({'; '.join(parts)})"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--rules", type=Path, default=DEFAULT_RULES)
    ap.add_argument("--towns-dir", type=Path, default=DEFAULT_TOWNS)
    ap.add_argument("--plan", type=Path, action="append", help="generator output; repeatable")
    ap.add_argument("--town-plans", type=Path, default=DEFAULT_TOWN_PLANS)
    ap.add_argument("--jar", type=Path)
    ap.add_argument("--atm", type=Path, default=DEFAULT_ATM)
    ap.add_argument("--layer", choices=["all", "data", "placement"], default="all")
    ap.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    a = ap.parse_args(argv)
    report = run(a.rules, a.towns_dir, a.plan, a.town_plans, a.jar, a.atm, a.layer)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    print(summary(report) + f" -> {a.report}")
    shown, said = 0, set()
    for c in report["checks"]:
        if c["status"] == PASS:
            continue
        lines = c["problems"] or [c.get("reason") or "; ".join(c.get("not_checked", []))]
        if c["status"] != FAIL and c.get("not_checked"):
            lines = c["not_checked"]
        lines = [x for x in lines if not (c["status"] != FAIL and x in said)]
        said.update(lines)
        print(f"  {c['status']} {c['layer']}/{c['check']}: {len(c['problems'])} problem(s)"
              if c["status"] == FAIL else f"  {c['status']} {c['layer']}/{c['check']}")
        for line in lines:
            if shown >= 60:
                break
            print(f"    {line}")
            shown += 1
    if shown >= 60:
        print("    ... more in the report")
    return {PASS: 0, FAIL: 1}.get(report["verdict"], 2)


if __name__ == "__main__":
    sys.exit(main())

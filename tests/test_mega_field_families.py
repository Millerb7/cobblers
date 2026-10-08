"""The Mega field's evolution lines (the owner, 2026-10-05: "have some base mons of each version running around in the
area as well as the megas, like a charizard den with a few megas and some charmeleon, charizards and charmanders"),
checked on tools/compile_spawns.py's OUTPUT, the compiled sub-region files, against the data and the jar.

INDEPENDENCE. Which compiled details belong to which den is read from their ids (`<sub>_<den>_b<k>_<species>`, the
naming only); everything they are judged by comes from elsewhere: each den's anchor and leash (its range) from
data/gulch_mine.json farms, the sub-region a den stands in by a point-in-polygon written here over data/regions.json,
the level band from data/spawns.json, the tier cap from docs/mechanics/ENCOUNTER_DESIGN.md (test_encounter_design's
TIER_CAP, target 5: "No spawn in a table is above its tier's cap") and the tier from data/encounter_design.json, and the
evolution line of each Mega from the Cobblemon jar's own pre-evolutions (never mega_field.families.lines, which is
checked against it). The mutations change tools/compile_spawns.py's mega_den_spawns, never data.

Checked: every field den has its line compiled, in the file of the sub-region holding its anchor; every detail's box
lies wholly inside its den's range (all four corner columns within leash of the anchor) and inside anchor +-
families.box_half; no detail is uncatchable; the species are exactly the den's line less families.held, and a held
species is compiled for no den; every level range is inside its sub-region's level_band and at or under its tier's cap;
families.lines[species] is the jar's pre-evolution chain ending at the Mega's species.

NOT covered (needs a running server): that the lines actually spawn (Cobblemon's spawner budget, the biome and block
conditions, day and night), how many stand at once, that a player can catch one (the ball is not refused), and that
the Megas' Fight or Flight aggression leaves them alone. The holds (numel, camerupt, scizor, the Squirtle line) are
the builder's, declared with reasons; whether the owner's words override them is his call, not a test's.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import compile_spawns as CS  # noqa: E402  the generator, run only to produce the files under test
import test_encounter_design as ED  # noqa: E402  TIER_CAP (parsed from the document) and the jar's Dex
from test_encounter_design import jar  # noqa: E402,F401  session fixture

GM = json.loads((ROOT / "data" / "gulch_mine.json").read_text(encoding="utf-8"))
FAM = GM["mega_field"]["families"]
DENS = [d for fa in GM["farms"] if fa["id"].startswith("field_") for d in fa["dens"]]
REGIONS = json.loads((ROOT / "data" / "regions.json").read_text(encoding="utf-8"))["subregions"]
BANDS = {s["id"]: s.get("level_band") for s in json.loads((ROOT / "data" / "spawns.json").read_text(encoding="utf-8"))
         ["subregions"]}
TIERS = {k: v.get("tier") for k, v in ED.DESIGN["tables"].items()}


def inside(poly, x, z):
    """Even-odd ray cast, written here (not compile_spawns' or subregion_boxes')."""
    n, hit = len(poly), False
    for i in range(n):
        (x1, z1), (x2, z2) = poly[i], poly[(i + 1) % n]
        if (z1 > z) != (z2 > z) and x < x1 + (z - z1) * (x2 - x1) / (z2 - z1):
            hit = not hit
    return hit


def home_sub(d):
    ax, az = d["anchor"][0] + 0.5, d["anchor"][2] + 0.5
    subs = sorted(s["id"] for s in REGIONS if any(inside(p, ax, az) for p in s["polygons"]))
    return subs


def compile_pack(out):
    CS.main(["--out", str(out)])
    return out / "data" / "cobblers" / "spawn_pool_world" / "subregions"


def den_rows(sub_dir):
    """{den id: [(file stem, detail)]} by the id naming only."""
    out = {d["id"]: [] for d in DENS}
    pat = re.compile(r"_(gm_mf_\d+_\d+)_b\d+_[a-z_]+$")
    for p in sorted(sub_dir.glob("*.json")):
        for e in json.loads(p.read_text(encoding="utf-8"))["spawns"]:
            m = pat.search(e.get("id", ""))
            if m:
                out.setdefault(m.group(1), []).append((p.stem, e))
    return out


def audit(sub_dir):
    """Problems with the compiled den lines, judged from the data alone."""
    probs = []
    held = set(FAM.get("held") or {})
    rows = den_rows(sub_dir)
    known = {d["id"] for d in DENS}
    for i in sorted(set(rows) - known):
        probs.append("%s: compiled lines for no field den" % i)
    for d in DENS:
        did, ax, az, L = d["id"], d["anchor"][0], d["anchor"][2], d["leash"]
        rs = rows.get(did) or []
        subs = home_sub(d)
        want = [sp for sp in FAM["lines"][d["species"]] if sp not in held]
        if not rs:
            # a den whose whole line is held (Camerupt's numel+camerupt, Blastoise's Squirtle line) rightly has none
            if want:
                probs.append("%s: no line compiled" % did)
            continue
        files = {f for f, _e in rs}
        if not subs or files != {subs[0]}:
            probs.append("%s: compiled into %s, its anchor is in %s" % (did, sorted(files), subs))
        have = sorted({e["pokemon"] for _f, e in rs})
        if have != sorted(want):
            probs.append("%s: species %s, its line less the holds is %s" % (did, have, sorted(want)))
        band = BANDS.get(subs[0]) if subs else None
        cap = ED.TIER_CAP.get(TIERS.get(subs[0])) if subs else None
        for f, e in rs:
            c = e.get("condition") or {}
            corners = [(x, z) for x in (c.get("minX"), c.get("maxX")) for z in (c.get("minZ"), c.get("maxZ"))]
            if None in [v for xz in corners for v in xz]:
                probs.append("%s: %s has no box" % (did, e["id"]))
                continue
            far = max(((x - ax) ** 2 + (z - az) ** 2) ** 0.5 for x, z in corners)
            if far > L:
                probs.append("%s: %s reaches %.1f from its anchor, past its range (leash %d)" % (did, e["id"], far, L))
            h = FAM["box_half"]
            if c["minX"] < ax - h or c["maxX"] > ax + h or c["minZ"] < az - h or c["maxZ"] > az + h:
                probs.append("%s: %s leaves anchor +- box_half %d" % (did, e["id"], h))
            if "uncatchable" in json.dumps(e):
                probs.append("%s: %s is uncatchable" % (did, e["id"]))
            m = re.fullmatch(r"(\d+)-(\d+)", str(e.get("level")))
            if not m or not band or cap is None:
                probs.append("%s: %s level %r, band %s, cap %s" % (did, e["id"], e.get("level"), band, cap))
                continue
            lo, hi = int(m.group(1)), int(m.group(2))
            if lo < band["minimum"] or hi > band["maximum"] or lo > hi:
                probs.append("%s: %s level %d-%d outside %s's band %d-%d" % (did, e["id"], lo, hi, subs[0],
                                                                            band["minimum"], band["maximum"]))
            if hi > cap:
                probs.append("%s: %s level %d-%d over its tier's cap %d (catchable)" % (did, e["id"], lo, hi, cap))
    for i, rs in rows.items():
        for _f, e in rs:
            if e["pokemon"] in held:
                probs.append("%s: held species %s compiled (%s)" % (i, e["pokemon"], e["id"]))
    return probs


@pytest.fixture(scope="module")
def committed(tmp_path_factory):
    return compile_pack(tmp_path_factory.mktemp("den_lines"))


# Without it the owner's evolution lines could be compiled wrong, or not at all, and nothing would say so: on the
# committed data every field den's line is in its own sub-region file, inside its range, catchable, every stage but the
# declared holds, at levels inside its band and under its tier's cap.
def test_every_den_line_is_confined_catchable_complete_and_under_the_cap(committed):
    assert audit(committed) == []
    rows = den_rows(committed)
    held = set(FAM.get("held") or {})
    open_ = [d["id"] for d in DENS if any(sp not in held for sp in FAM["lines"][d["species"]])]
    assert open_ and all(rows[i] for i in open_), "a den with no line: this audit is not exercised"


# Without it "every stage" would mean whatever families.lines says: each Mega's line is the jar's own pre-evolution
# chain ending at the Mega's species (Glalie's Snorunt and not Froslass, Gallade's Ralts and Kirlia).
def test_each_dens_line_is_the_jars_evolution_chain(jar):
    bad = {}
    for sp in sorted({d["species"] for d in DENS}):
        chain = [sp]
        while chain[0] in jar.parent:
            chain.insert(0, jar.parent[chain[0]])
        if FAM["lines"].get(sp) != chain:
            bad[sp] = (FAM["lines"].get(sp), chain)
    assert not bad, bad


# Without it a hold could be silent: every held species is one of a den's line and states why.
def test_every_hold_names_a_line_species_and_a_reason():
    lines = {sp for d in DENS for sp in FAM["lines"][d["species"]]}
    held = FAM.get("held") or {}
    assert set(held) <= lines, sorted(set(held) - lines)
    assert all(isinstance(v, str) and len(v) > 20 for v in held.values()), held


# ------------------------------------------------------------- generator mutations (tools/compile_spawns.py; data untouched)
def _mutated(monkeypatch, tmp_path, change):
    orig = CS.mega_den_spawns

    def wrapped(*a, **k):
        out, summ = orig(*a, **k)
        change(out)
        return out, summ
    monkeypatch.setattr(CS, "mega_den_spawns", wrapped)
    return audit(compile_pack(tmp_path))


def _first(out, species=None):
    for sub, rows in sorted(out.items()):
        for e in rows:
            if species is None or e["pokemon"] == species:
                return e
    raise AssertionError("no den line compiled: the mutation cannot bite")


# Without it a den's line could spill past its range onto the next den's floor or the road: one detail's box shifted
# 30 blocks east is named as past its range.
def test_a_line_entry_outside_its_den_box_is_caught(monkeypatch, tmp_path):
    def shift(out):
        c = _first(out)["condition"]
        c["minX"] += 30
        c["maxX"] += 30
    probs = _mutated(monkeypatch, tmp_path, shift)
    assert any("past its range" in p for p in probs) and any("leaves anchor +- box_half" in p for p in probs), probs


# Without it a line could be compiled uncatchable (the Megas' rule leaking onto their families).
def test_a_line_entry_made_uncatchable_is_caught(monkeypatch, tmp_path):
    def unc(out):
        e = _first(out)
        e["pokemon"] = e["pokemon"] + " uncatchable"
    probs = _mutated(monkeypatch, tmp_path, unc)
    assert any("is uncatchable" in p for p in probs), probs


# Without it a stage could go missing: the generator dropping every Charmeleon is named for every Charizard den.
def test_a_missing_stage_is_caught(monkeypatch, tmp_path):
    def drop(out):
        for sub in out:
            out[sub] = [e for e in out[sub] if e["pokemon"] != "charmeleon"]
    probs = _mutated(monkeypatch, tmp_path, drop)
    zard = sorted(d["id"] for d in DENS if d["species"] == "charizard")
    assert zard, "no Charizard den: the mutation cannot bite"
    named = sorted(p.split(":")[0] for p in probs if "its line less the holds" in p)
    assert named == zard, probs


# Without it a catchable line could be compiled over the cap (the Megas' 70/77 instead of the band): one detail at
# 70-77 is named as over the cap and outside the band.
def test_a_line_over_the_cap_is_caught(monkeypatch, tmp_path):
    def high(out):
        _first(out)["level"] = "70-77"
    probs = _mutated(monkeypatch, tmp_path, high)
    assert any("over its tier's cap" in p for p in probs) and any("outside" in p and "band" in p for p in probs), probs


# Without it a hold could be ignored: the generator compiling a held species (numel) is named.
def test_a_held_species_compiled_is_caught(monkeypatch, tmp_path):
    held = sorted(FAM.get("held") or {})
    assert held, "no hold declared: the mutation cannot bite"

    def add(out):
        e = dict(_first(out))
        e["id"] = e["id"].rsplit("_", 1)[0] + "_" + held[0]
        e["pokemon"] = held[0]
        next(iter(out.values())).append(e)
    probs = _mutated(monkeypatch, tmp_path, add)
    assert any("held species %s compiled" % held[0] in p for p in probs), probs

"""A sweep site's declared EXTRA caches (U4 GRISEOUS, 2026-10-09; docs/OVERNIGHT_REVIEW_2026-10-06.md N118).

The Griseous Core and Orb belong at Giratina's altar, gated on champion_cleared (docs/mechanics/ITEM_ROUTES.md, the
drafted record). Before this, both the builder's check (tools/legendary_sweep.py) and the independent audit
(tools/legendary_sweep_audit.py) held the altar to ONE cache with ONE item, and a second record at the altar failed the
hidden-site clearance rule. A sweep site may now declare `extra_caches` [{"source", "items", "flags"}]; a declared one is
spared that site's clearance rule and NOTHING else.

Every scenario case uses a SCRATCH Griseous record built in memory (the drafted shape: sweep_red_chain's trigger and
container, champion_cleared, one Core and one Orb). Nothing on disk is written and data/ is untouched. Since 2026-10-09
the real record is COMMITTED (data/rewards.json giratina_griseous, declared on sweep_giratina_shrine.extra_caches), so
every scenario starts from an in-memory copy with the committed declaration STRIPPED (`adopted_with` names every
declaration a scenario has) and, where the scenario needs the record absent, the committed record removed
(`rewards_without`). One pair of tests holds the committed record itself to both checkers, unpatched.

INDEPENDENCE. The audit's mutations edit the GENERATOR (tools/rewards_pack.py, which writes every cache) in memory with
the authored data untouched (CLAUDE.md "How to prove an audit is independent"). The audit's expectations come from the
jars (the item ids), data/progression.json (the flag), the template NBT (the extent) and the declaration, none of which
a rewards_pack edit can move.

WHAT THIS DOES NOT COVER. That the advancement fires, that the Core or Orb does anything under Mega Showdown 1.0.2, or
that a player can reach the altar without breaking the dome (the audit's KNOWN giratina_dome_sealed): those need a
running server. Item reality is "the jar ships an item model", the same evidence data/rewards.json `verification` cites,
not a registry read.
"""
from __future__ import annotations

import copy
import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import hidden_sites as H  # noqa: E402
import legendary_sweep as S  # noqa: E402
import legendary_sweep_audit as A  # noqa: E402
import rewards_pack as RP  # noqa: E402

SNAP = A.SNAPSHOT
HAVE_SNAPSHOT = (SNAP / "mods").is_dir() and any((SNAP / "mods").glob("LumyMon-*.jar"))
needs_snapshot = pytest.mark.skipif(not HAVE_SNAPSHOT, reason="NOT RUN: no offline server snapshot at %s" % SNAP)

DOC = json.loads((ROOT / "data" / "adopted_legendary_sites.json").read_text(encoding="utf-8"))
PLACEMENTS = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["placements"]
REWARDS = json.loads((ROOT / "data" / "rewards.json").read_text(encoding="utf-8"))
GIRATINA = "sweep_giratina_shrine"
NEWMOON = "sweep_newmoon_island"
PASTE = "legendary_giratina_shrine"
CORE, ORB = "mega_showdown:griseous_core", "mega_showdown:griseous_orb"
SRC = "giratina_griseous"
JAR = "mega_showdown-fabric-1.0.2+1.8+1.21.1-release.jar"


def red_chain():
    return next(r for r in REWARDS["rewards"] if r["id"] == "sweep_red_chain")


def griseous(**over):
    """The drafted record (ITEM_ROUTES.md): sweep_red_chain's trigger and container, champion_cleared, one of each."""
    rc = red_chain()
    r = {"id": SRC, "kind": "cache", "place": "Giratina's altar (scratch, tests only)",
         "requires_flags": ["champion_cleared"],
         "contents": [{"item": CORE, "count": 1, "verification": "assets/mega_showdown/models/item/griseous_core.json in %s" % JAR},
                      {"item": ORB, "count": 1, "verification": "assets/mega_showdown/models/item/griseous_orb.json in %s" % JAR}],
         "message": "Scratch: a Griseous Core and a Griseous Orb.",
         "trigger": copy.deepcopy(rc["trigger"]), "container": copy.deepcopy(rc["container"])}
    r.update(over)
    return r


def declaration(**over):
    d = {"source": SRC, "items": [CORE, ORB], "flags": ["champion_cleared"]}
    d.update(over)
    return d


def rewards_with(*records):
    doc = copy.deepcopy(REWARDS)
    # a scratch record replaces a committed one of the same id (giratina_griseous is in the data since 2026-10-09)
    ids = {r["id"] for r in records}
    doc["rewards"] = [r for r in doc["rewards"] if r.get("id") not in ids] + [copy.deepcopy(r) for r in records]
    return doc


def rewards_without(*ids):
    """A copy of data/rewards.json with the named committed records removed."""
    doc = copy.deepcopy(REWARDS)
    doc["rewards"] = [r for r in doc["rewards"] if r.get("id") not in set(ids)]
    return doc


def adopted_with(decls):
    """{site id: [declaration]} applied to a copy of data/adopted_legendary_sites.json with EVERY committed
    extra_caches declaration stripped first, so a scenario holds exactly the declarations it names (the committed
    one on Giratina's site would otherwise spare every scratch record at the altar)."""
    doc = copy.deepcopy(DOC)
    for s in doc["sweep_sites"]:
        s.pop("extra_caches", None)
        if s["id"] in decls:
            s["extra_caches"] = decls[s["id"]]
    return doc


def site_of(doc, sid):
    return next(s for s in doc["sweep_sites"] if s["id"] == sid)


def shifted(r, dx=0, dy=0):
    r = copy.deepcopy(r)
    for k in ("min", "max"):
        r["trigger"][k] = [r["trigger"][k][0] + dx, r["trigger"][k][1] + dy, r["trigger"][k][2]]
    a = r["container"]["at"]
    r["container"]["at"] = [a[0] + dx, a[1] + dy, a[2]]
    return r


# ================================================================================ the builder's check (legendary_sweep)


@pytest.fixture(scope="module")
def ground():
    import ground as G
    from terrain import TerrainUnavailable
    try:
        return G.load()
    except (TerrainUnavailable, FileNotFoundError, OSError) as e:
        pytest.skip("NOT RUN: no canonical heightmap (%s)" % (str(e) or type(e).__name__)[:80])


def with_scratch_points(monkeypatch, *records):
    """H.authored_points as it would read data/rewards.json holding the scratch records: their coordinates join the
    clearance rule unless the caller's skip set names them (the real walker, the real skip semantics). A scratch record
    REPLACES a committed one of the same id (the committed giratina_griseous), as rewards_with does, so a scenario's
    verdict comes from its own record and not from the committed one at the same coordinates."""
    real = H.authored_points
    replaced = {r["id"] for r in records}

    def pts(skip_ids=()):
        out = real(set(skip_ids) | replaced)
        H._walk({"rewards": [copy.deepcopy(r) for r in records]}, out, "data/rewards.json", set(skip_ids))
        return out
    monkeypatch.setattr(H, "authored_points", pts)


def builder_problems(ground, site, rdoc):
    m = S.measure(site, ground, PLACEMENTS, rewards=rdoc)
    return S.rule_problems(site, m, S.runtime_top(DOC)) + S.record_problems(site, m) + S.placement_problems(site, PLACEMENTS, rdoc)


def test_a_declared_extra_cache_at_the_altar_passes_the_builders_check(ground, monkeypatch):
    # Without it the Griseous Core still cannot be built: the drafted record must pass every rule once declared.
    rec = griseous()
    assert RP.problems({"rewards": [rec]}) == []
    with_scratch_points(monkeypatch, rec)
    site = site_of(adopted_with({GIRATINA: [declaration()]}), GIRATINA)
    assert builder_problems(ground, site, rewards_with(rec)) == []


def test_an_undeclared_record_at_the_altar_still_fails_the_clearance_rule(ground, monkeypatch):
    # Without it any record could be dropped beside a hidden legendary: the exemption must come from a declaration.
    rec = griseous()
    with_scratch_points(monkeypatch, rec)
    bad = builder_problems(ground, site_of(adopted_with({}), GIRATINA), rewards_with(rec))
    assert any("authored point in data/rewards.json 0 from the footprint edge" in b for b in bad), bad


def test_a_record_declared_on_the_other_site_is_not_spared_here(ground, monkeypatch):
    # Without it a declaration on Newmoon Island would buy a record at Giratina's altar its clearance exemption.
    rec = griseous()
    with_scratch_points(monkeypatch, rec)
    doc = adopted_with({NEWMOON: [declaration()]})
    bad = builder_problems(ground, site_of(doc, GIRATINA), rewards_with(rec))
    assert any("authored point in data/rewards.json" in b for b in bad), bad
    assert any("not inside the site's carve" in b for b in S.placement_problems(site_of(doc, NEWMOON), PLACEMENTS, rewards_with(rec)))


def test_an_undeclared_second_item_in_the_activation_cache_still_fails():
    # Without it the Red Chain cache could hand out anything beside the chain, and the one-item contract is gone.
    rdoc = copy.deepcopy(REWARDS)
    rc = next(r for r in rdoc["rewards"] if r["id"] == "sweep_red_chain")
    rc["contents"].append({"item": CORE, "count": 1, "verification": "x"})
    for sites in ({}, {GIRATINA: [declaration(source="sweep_red_chain")]}):
        bad = S.placement_problems(site_of(adopted_with(sites), GIRATINA), PLACEMENTS, rdoc)
        assert any("not one lumymon:red_chain" in b for b in bad), bad


@pytest.mark.parametrize("rec,decl,want", [
    # 60 east of the shrine's corner + 42: off the template entirely
    (shifted(griseous(), dx=60), declaration(), "not inside the site's carve"),
    # straight up over the dome's top layer (y66 + 43 - 1 = y108)
    (shifted(griseous(), dy=40), declaration(), "not inside the site's carve"),
    # the declaration says two items, the record gives one
    (griseous(contents=griseous()["contents"][:1]), declaration(), "one of each"),
    # two Cores
    (griseous(contents=[dict(griseous()["contents"][0], count=2), griseous()["contents"][1]]), declaration(), "one of each"),
    # the gate the record carries is not the declared one
    (griseous(requires_flags=["gym8_cleared"]), declaration(), "the site declares ['champion_cleared']"),
    # a declared gate that is no progression flag
    (griseous(requires_flags=["not_a_flag"]), declaration(flags=["not_a_flag"]), "not data/progression.json flags"),
    # the extra cache hands out the activation item: a second source of the Red Chain
    (griseous(contents=griseous()["contents"] + [{"item": "lumymon:red_chain", "count": 1}]),
     declaration(items=[CORE, ORB, "lumymon:red_chain"]), "hands out the activation item"),
])
def test_a_declared_extra_cache_is_held_to_every_other_rule(rec, decl, want):
    # Without it a declaration would be a blanket exemption: outside the carve, the wrong gate or a second Red Chain.
    site = site_of(adopted_with({GIRATINA: [decl]}), GIRATINA)
    bad = S.placement_problems(site, PLACEMENTS, rewards_with(rec))
    assert any(want in b for b in bad), bad


def test_a_declaration_naming_no_record_fails():
    # Without it a declaration could outlive its record and nobody would notice the Core was gone.
    bad = S.placement_problems(site_of(adopted_with({GIRATINA: [declaration()]}), GIRATINA), PLACEMENTS,
                               rewards_without(SRC))
    assert any("names 0 data/rewards.json records" in b for b in bad), bad


def test_the_committed_griseous_cache_passes_the_builders_check(ground):
    # Without it the committed Core and Orb (data/rewards.json giratina_griseous) could break a rule while every
    # scenario above, built on scratch copies, stays green.
    site = site_of(DOC, GIRATINA)
    assert site.get("extra_caches") == [declaration()], site.get("extra_caches")
    rec = next(r for r in REWARDS["rewards"] if r["id"] == SRC)
    assert RP.problems({"rewards": [rec]}) == []
    assert builder_problems(ground, site, REWARDS) == []


# ================================================================================ the independent audit


def patched_j(monkeypatch, rdoc=None, adopted=None):
    """A._j as it would read data/ holding the scratch documents (the authored-point walker reads through it too)."""
    real = A._j

    def j(path):
        p = Path(path)
        if rdoc is not None and p.name == "rewards.json" and p.parent == A.DATA:
            return copy.deepcopy(rdoc)
        if adopted is not None and p.name == "adopted_legendary_sites.json" and p.parent == A.DATA:
            return copy.deepcopy(adopted)
        return real(path)
    monkeypatch.setattr(A, "_j", j)


@pytest.fixture(scope="module")
def packs():
    if not HAVE_SNAPSHOT:
        pytest.skip("NOT RUN: no offline server snapshot at %s" % SNAP)
    return A.Packs(SNAP)


@pytest.fixture(scope="module")
def declared(packs, ground):
    """paste_audit with the scratch record in data/rewards.json and DECLARED on Giratina's site."""
    rdoc, adopted = rewards_with(griseous()), adopted_with({GIRATINA: [declaration()]})
    with pytest.MonkeyPatch.context() as mp:
        patched_j(mp, rdoc, adopted)
        R = A.Report()
        sites = A.paste_audit(R, packs, ground, sightlines=False)
    return R, sites


def mutated(name, old, new):
    """tools/<name>.py with `old` replaced by `new` exactly once, executed as a fresh module (the file is untouched)."""
    path = ROOT / "tools" / ("%s.py" % name)
    src = path.read_text(encoding="utf-8")
    assert src.count(old) == 1, "the mutation's anchor %r is in %s %d times" % (old, path.name, src.count(old))
    mod = types.ModuleType("%s_mutant" % name)
    mod.__file__ = str(path)
    exec(compile(src.replace(old, new), str(path), "exec"), mod.__dict__)
    return mod


def problems(R):
    return [m for _a, m in R.problems]


@needs_snapshot
@pytest.mark.slow
def test_the_audit_passes_a_declared_extra_cache_at_the_altar(declared, packs, monkeypatch):
    # Without it the audit would still refuse the Griseous Core whatever the builder declared.
    R0, sites = declared
    assert problems(R0) == []
    patched_j(monkeypatch, rewards_with(griseous()), adopted_with({GIRATINA: [declaration()]}))
    R = A.Report()
    A.cache_audit(R, sites)
    A.extra_cache_audit(R, packs, sites)
    assert problems(R) == []
    assert R.facts[PASTE + ".extra_caches"] == [SRC]
    # inside the same sealed dome as the Red Chain: one KNOWN finding, which now names it too
    assert set(R.known) == {"giratina_dome_sealed"} and SRC in R.known["giratina_dome_sealed"]


@needs_snapshot
@pytest.mark.slow
def test_the_audit_fails_an_undeclared_record_at_the_altar(packs, ground, monkeypatch):
    # Without it the audit's clearance rule would have a hole any record at the altar could use.
    patched_j(monkeypatch, rewards_with(griseous()), adopted_with({}))
    R = A.Report()
    A.paste_audit(R, packs, ground, sightlines=False)
    assert any("authored point (4393, 2878) in data/rewards.json is 0 from the footprint edge" in p for p in problems(R)), problems(R)


@needs_snapshot
@pytest.mark.slow
def test_the_audit_does_not_spare_a_record_declared_on_the_other_site(packs, ground, monkeypatch):
    # Without it a declaration on Newmoon Island would exempt a record at Giratina's altar.
    patched_j(monkeypatch, rewards_with(griseous()), adopted_with({NEWMOON: [declaration()]}))
    R = A.Report()
    sites = A.paste_audit(R, packs, ground, sightlines=False)
    assert any(PASTE + ": authored point" in p for p in problems(R)), problems(R)
    A.extra_cache_audit(R, packs, sites)
    assert any("legendary_newmoon_island: extra cache 'giratina_griseous'" in p and "extent" in p for p in problems(R)), problems(R)


@needs_snapshot
@pytest.mark.slow
def test_the_audit_still_fails_a_second_item_in_the_activation_cache(declared, monkeypatch):
    # Without it the one-item contract on the Red Chain cache would be gone along with the clearance skip.
    rdoc = copy.deepcopy(REWARDS)
    next(r for r in rdoc["rewards"] if r["id"] == "sweep_red_chain")["contents"].append({"item": CORE, "count": 1})
    patched_j(monkeypatch, rdoc, adopted_with({GIRATINA: [declaration(source="sweep_red_chain")]}))
    R = A.Report()
    A.cache_audit(R, declared[1])
    assert any("cobblers:reward/sweep_red_chain gives more than the item" in p for p in problems(R)), problems(R)


@needs_snapshot
@pytest.mark.slow
def test_the_audit_passes_the_committed_griseous_cache(packs, ground):
    # Without it the committed Core and Orb could fail the independent audit (jars, flags, extent, contents) while the
    # scratch scenarios pass. Nothing is patched: the audit reads data/ as committed.
    R = A.Report()
    sites = A.paste_audit(R, packs, ground, sightlines=False)
    A.cache_audit(R, sites)
    A.extra_cache_audit(R, packs, sites)
    assert problems(R) == []
    assert R.facts[PASTE + ".extra_caches"] == [SRC]
    assert set(R.known) == {"giratina_dome_sealed"} and SRC in R.known["giratina_dome_sealed"]


@needs_snapshot
@pytest.mark.slow
@pytest.mark.parametrize("rec,decl,want", [
    (shifted(griseous(), dx=60), declaration(), "is not inside the template's extent"),
    (shifted(griseous(), dy=40), declaration(), "is not inside the template's extent"),
    (griseous(contents=[{"item": "mega_showdown:griseous_cor", "count": 1}, griseous()["contents"][1]]),
     declaration(items=["mega_showdown:griseous_cor", ORB]), "mega_showdown:griseous_cor is not an item any loaded jar ships"),
    (griseous(requires_flags=["not_a_flag"]), declaration(flags=["not_a_flag"]), "is not a list of data/progression.json flags"),
    (griseous(contents=griseous()["contents"][:1]), declaration(), "the site declares one each of"),
    (griseous(requires_flags=["gym8_cleared"]), declaration(), "does not require ['cobblers:flag/champion_cleared']"),
])
def test_the_audit_holds_a_declared_extra_cache_to_every_other_rule(declared, packs, monkeypatch, rec, decl, want):
    # Without it a declaration would exempt a cache from the carve, the jars, the flags and its own contents.
    patched_j(monkeypatch, rewards_with(rec), adopted_with({GIRATINA: [decl]}))
    R = A.Report()
    A.extra_cache_audit(R, packs, declared[1])
    assert any(want in p for p in problems(R)), problems(R)


@needs_snapshot
@pytest.mark.slow
@pytest.mark.parametrize("old,new,want", [
    # the predicate loses its flag check: anyone at the altar takes the Core and Orb
    ('if r.get("requires_flags"):', 'if False:', "does not require ['cobblers:flag/champion_cleared']"),
    # two of each instead of one
    ('c.get("components", ""), c["count"]))', 'c.get("components", ""), c["count"] + 1))', "the site declares one each of"),
    # the predicate box 60 blocks east: off the template
    ('pos = {"x": {"min": x0, "max": x1 + 1},', 'pos = {"x": {"min": x0 + 60, "max": x1 + 61},', "is not inside the template's extent"),
])
def test_a_mutated_rewards_generator_is_caught_on_the_extra_cache(declared, packs, monkeypatch, old, new, want):
    # Without it the extra cache's checks could share the record's reading and pass whatever the pack emits.
    patched_j(monkeypatch, rewards_with(griseous()), adopted_with({GIRATINA: [declaration()]}))
    R = A.Report()
    A.extra_cache_audit(R, packs, declared[1], rewards=mutated("rewards_pack", old, new))
    assert any("extra cache 'giratina_griseous'" in p and want in p for p in problems(R)), problems(R)

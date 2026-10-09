"""Independent review of N155's look-then-act chains (tools/chunk_look.py and its callers), by the test author.

The builders' own tests (tests/test_chunk_look.py, test_rift_chunk_look.py, test_traders_chunk_look.py,
test_direct_trades_chunk_look.py, test_chunk_sweep_cleanups.py) exercise each chain with ONE delay for every chunk,
except the Rift's and the traders'. A chain whose entities stand in several chunks is only sound when one look requires
an entity in EVERY one of them (two chunks' saved entities do not arrive together). These tests put the chunks at
different delays for the chains the builders tested uniformly, and mutate tools/chunk_look.py's SOURCE (never the
data) for the mutants the builders' tests did not catch.

The world is tests/test_rift_chunk_look.py's Staggered (tests/test_markets_merchant_load.py's LateWorld with a delay
per chunk). What this does not cover: the simulator is not Minecraft. Whether a real server's saved entities arrive
within 300 ticks of a forceload, and whether a summon into a not-yet-loaded entity section really doubles, are
staging observations (2026-10-08), not facts these tests establish.
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import chunk_look as CL  # noqa: E402
import chunk_look_audit as CA  # noqa: E402
import frostpeak_camp as FC  # noqa: E402
import gulch_mine as GM  # noqa: E402
import mcfunction_sim as S  # noqa: E402
from test_rift_chunk_look import Staggered  # noqa: E402

TICKS = CL.STEP_TICKS + 5
GULCH = json.loads((ROOT / "data" / "gulch_mine.json").read_text(encoding="utf-8"))
FROST = json.loads((ROOT / "data" / "frostpeak_camp.json").read_text(encoding="utf-8"))
COLD = json.loads((ROOT / "data" / "coldwater_station.json").read_text(encoding="utf-8"))


def _write(tmp_path, fns):
    for ref, lines in fns.items():
        p = CA.pack_path(tmp_path, ref)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return tmp_path


def _mutant_cl(old, new):
    """tools/chunk_look.py with one line of its SOURCE changed."""
    src = (ROOT / "tools" / "chunk_look.py").read_text(encoding="utf-8")
    assert src.count(old) == 1, old
    mod = types.ModuleType("chunk_look_mutant")
    mod.__file__ = str(ROOT / "tools" / "chunk_look.py")
    exec(compile(src.replace(old, new), mod.__file__, "exec"), mod.__dict__)
    return mod


# ============================================================================ the Cutters: benches in two chunks
BENCHES = GULCH["cutters"]["benches"]
CUT_TAG = GULCH["cutters"]["tag"]


def _bench_chunks():
    return sorted({(b["at"][0] >> 4, b["at"][2] >> 4) for b in BENCHES})


def _cutters_fns():
    fns = GM.cutter_files(types.SimpleNamespace(spec=GULCH))
    return {"%s:%s/%s" % (GM.NS, GM.FOLDER, k): v for k, v in fns.items()}


def _cutters_world(delays):
    w = Staggered(_cutters_fns(), delays)
    for b in BENCHES:
        x, y, z = b["at"]
        w.save(S.Entity("minecraft:villager", (x + 0.5, y, z + 0.5), tags=(CUT_TAG, "%s_%s" % (CUT_TAG, b["id"]))))
    w.run(GM.CUTTERS_FN, TICKS)
    return w


def _per_bench(w):
    return [len(w.living("minecraft:villager", "%s_%s" % (CUT_TAG, b["id"]))) for b in BENCHES]


def test_the_cutters_benches_span_two_chunks_in_the_data():
    # Without it the two tests below would test nothing: they exist because data/gulch_mine.json puts the benches in
    # two chunks (bench_3 at x 4307 is in chunk 269, the others in 268).
    assert len(_bench_chunks()) >= 2, _bench_chunks()


# fixed 2026-10-08: the Cutters' chain looks in every bench's chunk (all_shown)
def test_one_cutter_per_bench_when_one_benchs_chunk_is_slower_than_the_other():
    # Without it a re-run of R9S doubles the Cutter of a bench whose chunk loads 160+ ticks after its neighbour's.
    first = {}
    for b in BENCHES:
        first.setdefault((b["at"][0] >> 4, b["at"][2] >> 4), (b["at"][0], b["at"][2]))
    xz = [first[c] for c in _bench_chunks()]
    w = _cutters_world({xz[0]: 10, xz[-1]: 200})
    assert _per_bench(w) == [1] * len(BENCHES)


# fixed 2026-10-08: one look requires a Cutter in every bench's chunk
def test_the_cutters_chain_looks_in_every_benchs_chunk(tmp_path):
    # Without it the audit (tools/gulch_mine_audit.py, sites from the data's benches) could pass a single-chunk look.
    sites = [(b["at"][0], b["at"][2]) for b in BENCHES]
    assert CA.problems(_write(tmp_path, _cutters_fns()), GM.CUTTERS_FN, CUT_TAG, sites=sites) == []


# ============================================================================ the instrument tubes, from the data
def _tubes(doc):
    return [p for p in doc["pieces"] if p.get("kind") == "instrument"]


def _displays(doc, tag, shift=0):
    out = []
    for i, p in enumerate(_tubes(doc)):
        x, z = p["at"][0] + (shift if i == len(_tubes(doc)) - 1 else 0), p["at"][1]
        out.append({"id": p["id"], "pivot": [x + 0.5, 100.2, z + 0.5], "aim": [x, 110, z - 50], "bearing": 0.0,
                    "elevation": 10.0,
                    "command": 'summon minecraft:block_display %.2f 100.20 %.2f {block_state:{Name:"minecraft:stone"},'
                               'Tags:["%s","%s"]}' % (x + 0.5, z + 0.5, tag, p["id"])})
    return out


@pytest.mark.parametrize("site", ["frostpeak", "coldwater"])
def test_the_instrument_chain_looks_in_every_tubes_chunk_from_the_data(site, tmp_path):
    # Without it a tube moved into a neighbouring chunk would be served by one look at the deck's centre, and a re-run
    # whose chunks arrived apart would double it. The chain is built at the DATA's tube columns.
    doc, tag, base, holder = ((FROST, FC.TAG, FC.INSTRUMENTS_FN, FC.INSTRUMENTS_HOLDER) if site == "frostpeak" else
                              (COLD, "cobblers_coldwater_station", "cobblers:coldwater_station/instruments", "cw"))
    sites = [tuple(p["at"]) for p in _tubes(doc)]
    fns = FC.instrument_functions(_displays(doc, tag), tag, base, holder)
    assert CA.problems(_write(tmp_path / "ok", fns), base, tag, sites=sites) == []
    moved = FC.instrument_functions(_displays(doc, tag, shift=16), tag, base, holder)
    sites_moved = sites[:-1] + [(sites[-1][0] + 16, sites[-1][1])]
    probs = CA.problems(_write(tmp_path / "moved", moved), base, tag, sites=sites_moved)
    assert any("no one look requires" in p for p in probs), probs


def test_a_look_without_all_shown_acts_on_any_one_of_its_selectors():
    # Without it chain() could read only its first `shown` selector when all_shown is off (a mutant no builder's test
    # caught): a chain whose first selector's entity is gone would wait out the blind limit every run, and act blind
    # even though another selector's entity was in at the first look.
    from test_markets_merchant_load import LateWorld
    fns = CL.chain("cobblers:review/any", (0, 0, 15, 15), ["@e[tag=gone_one]", "@e[tag=here_one]"],
                   ["kill @e[tag=here_one]", 'summon minecraft:armor_stand 5 64 5 {Tags:["here_one","here_one_new"]}'],
                   ["tag=here_one"], "here_one_new", "tag=here_one", "review_any")
    w = LateWorld(fns, 20)
    w.save(S.Entity("minecraft:armor_stand", (5.5, 64, 5.5), tags=("here_one",)))
    w.run("cobblers:review/any", TICKS)
    assert [t for t, _e in w.logged("summon")] == [CL.LOAD_WAIT]
    assert len(w.living("minecraft:armor_stand", "here_one")) == 1 and not w.forced


def test_no_two_chains_share_a_score_holder():
    # Without it two chains (R14's towns and R18DT's barterers run at once) could share #<holder>_seen or a count, and
    # one chain's look or end would act on, or report, the other's. Every chain and sweep shares one objective
    # (chunk_look.OBJ), so the holders alone keep them apart: each name with its _looks/_seen (chain) or
    # _looks/_gone/_n (sweep) helpers.
    import apricorn_farm
    import articuno_tower
    import coldwater_station
    import direct_trades
    import research_station
    import rift_mines
    import rift_skin
    import rift_zones
    import traders
    import zapdos_tower
    towns = sorted({r["settlement"] for r in json.loads((ROOT / "data" / "traders.json").read_text(encoding="utf-8"))
                    ["traders"] if r.get("settlement")})
    chains = ([FC.INSTRUMENTS_HOLDER, coldwater_station.INSTRUMENTS_HOLDER, GM.CUTTERS_HOLDER, rift_skin.FX_HOLDER,
               rift_skin.SHEETS_HOLDER, rift_zones.GUARDS_HOLDER, rift_mines.CARTS_HOLDER,
               apricorn_farm.MERCHANT_HOLDER, direct_trades.holder("place"), direct_trades.holder("counter")]
              + [traders.holder_of(t) for t in towns])
    sweeps = [research_station.NPC_SWEEP_HOLDER, articuno_tower.ENTITIES_HOLDER, zapdos_tower.ENTITIES_HOLDER]
    names = ([h + s for h in chains for s in ("", "_looks", "_seen")]
             + [h + s for h in sweeps for s in ("", "_looks", "_gone", "_n")])
    dup = sorted({n for n in names if names.count(n) > 1})
    assert not dup, dup


def test_the_site_audits_pass_the_datas_sites_to_the_chain_check():
    # Without it the three audits call the chain check with no sites, and a single-chunk look over several chunks passes.
    for path, needle in (("frostpeak_camp_audit.py", "INSTRUMENTS_FN, TAG, \"instruments\", sites="),
                         ("coldwater_station_audit.py", "STATION_TAG, \"instruments\",\n"),
                         ("gulch_mine_audit.py", "\"the Cutters' chain\",\n")):
        src = (ROOT / "tools" / path).read_text(encoding="utf-8")
        assert needle in src, path
        i = src.index(needle)
        assert "sites=" in src[i:i + 300], path

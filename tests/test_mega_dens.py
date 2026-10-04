"""tools/mega_dens_audit.py against tools/mega_dens.py: the clean pack passes, and a broken GENERATOR fails.

Written by the session that wrote the generator and the audit (the brief asked one agent for both), so the independent
half of the proof is the mutation standard of CLAUDE.md, "How to prove an audit is independent": every tamper case below
changes the generator's CODE (a method wrapped or replaced) and leaves data/mega_dens.json and data/gulch_mine.json
alone. A record-side mutation moves the expectation and the output together and proves nothing.

Needs the canonical heightmap (tools/ground.py); a skip names it. NOT covered, and it needs a running server: that the
fills land on the ground the heightmap predicts, that the keeper's Mega spawns on the pad, and how the dens read from
the air (docs/world-building/MEGA_DENS.md "World probes").
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import mega_dens as M  # noqa: E402
import mega_dens_audit as A  # noqa: E402

REC = json.loads((ROOT / "data" / "mega_dens.json").read_text(encoding="utf-8"))
GULCH = json.loads((ROOT / "data" / "gulch_mine.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ground():
    import ground as G
    import terrain as T
    try:
        return G.load()
    except T.TerrainUnavailable as e:
        pytest.skip("the canonical heightmap is unusable: %s" % e)


def run(ground, out, steps=None):
    doc, dens = M.load()
    written, _ds = M.files(doc, dens, ground)
    M.write(written, out)
    return A.audit(REC, ground, out, steps if steps is not None else M.placement_steps(doc, dens, ground))


def checks(rep):
    return sorted({e.split(":", 1)[0] for e in rep.errors})


def test_the_committed_dens_are_clean(ground, tmp_path):
    rep = run(ground, tmp_path)
    assert rep.errors == []


# Without it a farm den could stand undressed (nothing to see from the air), a lair could dress a den that does not
# exist, or a retired den (data/gulch_mine.json superseded_farms) could still be dressed. Repointed 2026-10-03 from the
# seven plateau dens' count to the property: whatever the farms are, each has exactly one lair and no retired one has.
def test_every_open_air_den_is_dressed_and_none_is_invented():
    gulch = {d["id"]: d["species"] for f in GULCH["farms"] for d in f["dens"]}
    mine = {d["den"]: d["species"] for d in REC["dens"]}
    retired = {d["id"] for f in GULCH.get("superseded_farms", []) for d in f["dens"]} - set(gulch)
    assert mine == gulch and mine
    assert not set(mine) & retired


def test_the_dens_are_dark_and_use_no_spawn_condition():
    spawn = set(json.loads((ROOT / "data" / "spawn_blocks.json").read_text(encoding="utf-8"))["blocks"])
    assert REC["lighting"] == "dark"
    assert not set(REC["blocks"]["ids"]) & spawn


# ------------------------------------------------------------------------------------------- generator mutations
def _after(monkeypatch, name, after):
    orig = getattr(M.Den, name)

    def wrapped(self, *a, **k):
        r = orig(self, *a, **k)
        after(self)
        return r
    monkeypatch.setattr(M.Den, name, wrapped)


def test_a_pad_without_its_head_room_is_caught(ground, tmp_path, monkeypatch):
    # the pad levels the anchor's columns but no longer clears the air over them. Repointed 2026-10-03: it named Pinsir,
    # a retired den; now every den whose pad holds a column above the anchor's ground (on the heightmap) must be named
    def pad_only(self):
        for x in range(self.ax - self.clear, self.ax + self.clear + 1):
            for z in range(self.az - self.clear, self.az + self.clear + 1):
                if self.r(x, z) <= self.clear:
                    for k in [k for k in self.w if k[0] == x and k[2] == z]:
                        del self.w[k]
                    self.put(x, self.G0, z, self.rec["pad"])
    monkeypatch.setattr(M.Den, "pad", pad_only)
    rep = run(ground, tmp_path)
    cr = REC["anchor_pad"]["clear_radius"]
    gd = {d["id"]: d["anchor"] for f in GULCH["farms"] for d in f["dens"]}
    raised = sorted(r["species"] for r in REC["dens"] for (ax, ay, az) in [gd[r["den"]]]
                    if any(round(ground(x, z)) > ay - 1 for x in range(ax - cr, ax + cr + 1)
                           for z in range(az - cr, az + cr + 1) if (x - ax) ** 2 + (z - az) ** 2 <= cr * cr))
    assert raised, "no den's pad holds a raised column: this mutation cannot bite on the current dens"
    named = sorted({e.split(":")[1].strip() for e in rep.errors if e.startswith("anchor: ") and "spawn cylinder" in e})
    assert named == raised


def test_a_boulder_in_the_spawn_cylinder_is_caught(ground, tmp_path, monkeypatch):
    _after(monkeypatch, "pad", lambda d: d.w.__setitem__((d.ax + 2, d.G0 + 1, d.az), "minecraft:cobblestone"))
    rep = run(ground, tmp_path)
    assert "anchor" in checks(rep)


def test_a_spawn_condition_slipped_past_the_palette_is_caught(ground, tmp_path, monkeypatch):
    def sand(d):
        if d.species == "garchomp":
            for k, s in list(d.w.items()):
                if s == "minecraft:smooth_sandstone":
                    d.w[k] = "minecraft:sand"
    _after(monkeypatch, "build", sand)
    rep = run(ground, tmp_path)
    assert any(e.startswith("blocks: garchomp writes minecraft:sand, a spawn condition") for e in rep.errors)


def test_a_light_in_a_lair_is_caught(ground, tmp_path, monkeypatch):
    def lantern(d):
        x, z = d.fx, d.fz
        d.w[(x, d.gtop(x, z) + 1, z)] = "minecraft:lantern[hanging=false,waterlogged=false]"
    _after(monkeypatch, "build", lantern)
    rep = run(ground, tmp_path)
    assert any("a light source" in e for e in rep.errors)


def test_a_stack_that_leaves_a_gap_under_it_is_caught(ground, tmp_path, monkeypatch):
    def stack(self, x, z, state, n=1):
        for _ in range(n):
            y = self.gtop(x, z) + 2
            self.put(x, y, z, state)
            self.top[(x, z)] = y
    monkeypatch.setattr(M.Den, "stack", stack)
    rep = run(ground, tmp_path)
    assert "support" in checks(rep)


def test_a_dig_deeper_than_declared_is_caught(ground, tmp_path, monkeypatch):
    orig = M.Den.lower
    monkeypatch.setattr(M.Den, "lower", lambda self, x, z, newtop, floor: orig(self, x, z, newtop - 1, floor))
    rep = run(ground, tmp_path)
    # repointed 2026-10-03 from Tyranitar and Garchomp (retired) to every den whose kit digs (a crater or a burrow)
    digs = sorted(r["species"] for r in REC["dens"] if r.get("dig"))
    assert digs, "no den digs: this mutation cannot bite on the current dens"
    assert sorted({e.split(":")[1].strip() for e in rep.errors if e.startswith("ground: ")}) == digs


def test_a_write_outside_the_box_is_caught(ground, tmp_path, monkeypatch):
    _after(monkeypatch, "build", lambda d: d.w.__setitem__((d.ax + 30, d.G0, d.az), "minecraft:coarse_dirt"))
    rep = run(ground, tmp_path)
    assert "box" in checks(rep)


def test_a_sign_left_unbuilt_is_caught(ground, tmp_path, monkeypatch):
    # repointed 2026-10-03: it unbuilt Abomasnow's frost, and no field den carries that kit. The bone heap is the sign
    # of the most-used kit (Houndoom's); every den whose feature it is must be named, by its signature and its mark
    monkeypatch.setattr(M.Den, "bone_pile", lambda self: None)
    rep = run(ground, tmp_path)
    bones = sorted(r["species"] for r in REC["dens"] if r["feature"] == "bone_pile")
    assert bones, "no den's sign is a bone heap: this mutation cannot bite on the current dens"
    for check in ("signature", "visible"):
        named = {e.split(": ", 1)[1].split()[0].rstrip(":") for e in rep.errors if e.startswith(check + ": ")}
        assert sorted(named) == bones, check


def test_a_scrape_in_the_skins_own_stone_does_not_read(ground, tmp_path, monkeypatch):
    orig = M.Den.scrape

    def grey(self):
        orig(self)
        for k, s in list(self.w.items()):
            if self.species == "houndoom" and k[1] == self.ground(k[0], k[2]):
                self.w[k] = "minecraft:cobblestone"
    monkeypatch.setattr(M.Den, "scrape", grey)
    rep = run(ground, tmp_path)
    assert any(e.startswith("visible: houndoom") and "skin" in e for e in rep.errors)


def test_steps_that_do_not_hold_the_chunks_are_caught(ground, tmp_path):
    doc, dens = M.load()
    steps = [s for s in M.placement_steps(doc, dens, ground) if s[0] == "fn"]
    rep = run(ground, tmp_path, steps=steps)
    assert "steps" in checks(rep)


# ------------------------------------------------------------------------------------------- the re-application
def test_r9md_runs_after_the_gulch_and_before_the_habitat_blocks():
    src = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    order = [src.index(s) for s in ('("R9S"', '("R9MD"', '("R9E"')]
    assert order == sorted(order)
    assert '"cobblers_mega_dens"' in src
    assert 'add("mega_dens:build", "mega_dens.py", "build"' in src and 'add("mega_dens_audit"' in src

"""An auditor's independent check of cobblers_dimension_overrides (tools/dimension_overrides.py), written by a
different agent from the builder (CLAUDE.md principle 16).

Nothing here imports tools/dimension_overrides.py. The generator is RUN as a CLI (its output is what ships), and its
scan is replaced by this file's own: every structure in the server's mods and datapacks whose biomes resolve to a
Nether or End biome, every template reachable from it through ALL its jigsaw pools (not just the start pool), and the
blocks those templates hold, read from the NBT itself rather than from data/adopted_legendary_sites.json.

What this does NOT prove (validity is not behaviour, .claude/rules/testing.md):
  - that 1.21.1 honours "frequency": 0.0 at worldgen. The auditor read the 1.21.1 jar's StructurePlacement on
    2026-10-08 (codec Codec.floatRange(0.0, 1.0).optionalFieldOf("frequency", 1.0); the default reduction method
    places only when nextFloat() < frequency, so 0.0 never places), but only EXP-058 on a booted world proves it;
  - which pack wins at the same path: that is the enabled order in each world's level.dat, decided at boot;
  - that the pack reached the live world: nothing here can see a world;
  - vanilla mob spawners (fortress, bastion, Repurposed Structures temples), which are not campaign content.
"""
from __future__ import annotations

import gzip
import io
import json
import re
import subprocess
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "dimension_overrides.json"
GENERATOR = ROOT / "tools" / "dimension_overrides.py"
SNAPSHOT = Path("C:/Users/wnd/Documents/cobblers-local/server-snapshot-2026-10-05")

# vanilla 1.21.1 data/minecraft/tags/worldgen/biome/is_nether.json and is_end.json (read from the 1.21.1 jar by the
# auditor, 2026-10-08). No pack in the snapshot overrides the_nether or the_end dimension, so these are every biome
# either dimension can hold.
NETHER = {"minecraft:nether_wastes", "minecraft:soul_sand_valley", "minecraft:crimson_forest",
          "minecraft:warped_forest", "minecraft:basalt_deltas"}
END = {"minecraft:the_end", "minecraft:end_highlands", "minecraft:end_midlands", "minecraft:small_end_islands",
       "minecraft:end_barrens"}
VANILLA_TAGS = {"minecraft:is_nether": NETHER, "minecraft:is_end": END}

# what makes a generated copy dangerous: a trainer, a command chain, or a legendary summon block
DANGER = re.compile(r"^(rctmod:trainer_spawner|minecraft:(chain_|repeating_)?command_block|"
                    r"lumymon:[a-z_]*(altar|summon_anchor)|legendarymonuments:[a-z_]*(shrine|cocoon|altar|summon)|"
                    r"[a-z_]*:raid_den)$")
ID = re.compile(rb"[a-z0-9_.\-]+:[a-z0-9_./\-]+")
KINDS = {"worldgen/structure_set": "set", "worldgen/structure": "structure", "worldgen/template_pool": "pool",
         "tags/worldgen/biome": "tag"}
JSON_RX = re.compile(r"(?:^|/)data/([^/]+)/(worldgen/structure_set|worldgen/structure|worldgen/template_pool|"
                     r"tags/worldgen/biome)/(.+)\.json$")
NBT_RX = re.compile(r"(?:^|/)data/([^/]+)/structures?/(.+)\.nbt$")


def rid(s):
    return s if ":" in s else "minecraft:" + s


class Upstream:
    """Every structure_set, structure, pool, biome tag and template in a set of roots; `opt` marks a source under an
    extra/ folder (Global Packs' optional folder, never enabled in this world)."""

    def __init__(self, roots):
        self.recs = defaultdict(list)       # (kind, id) -> [(src, opt, data)]
        self.nbt = {}                       # template id -> set of namespaced ids in it
        for r in roots:
            self._root(Path(r))

    def _json(self, src, opt, name, raw):
        m = JSON_RX.search(name)
        if not m:
            return
        try:
            data = json.loads(raw.decode("utf-8-sig"))
        except ValueError:
            return
        self.recs[(KINDS[m.group(2)], m.group(1) + ":" + m.group(3))].append((src, opt, data))

    def _nbt(self, name, raw):
        m = NBT_RX.search(name)
        if not m:
            return
        try:
            raw = gzip.decompress(raw)
        except OSError:
            pass
        self.nbt.setdefault(m.group(1) + ":" + m.group(2), set()).update(x.decode() for x in ID.findall(raw))

    def _zip(self, z, src, opt):
        for n in z.namelist():
            low = n.lower()
            if low.endswith((".jar", ".zip")):
                try:
                    self._zip(zipfile.ZipFile(io.BytesIO(z.read(n))), src + "!" + n, opt)
                except zipfile.BadZipFile:
                    pass
            elif low.endswith(".json"):
                self._json(src, opt, n, z.read(n))
            elif low.endswith(".nbt"):
                self._nbt(n, z.read(n))

    def _root(self, root):
        files = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())
        for p in files:
            rel = p.as_posix()
            if "cobblers_dimension_overrides" in rel:
                continue                                     # the pack under test is never upstream
            opt = "/extra/" in rel
            if p.suffix.lower() in (".jar", ".zip"):
                try:
                    self._zip(zipfile.ZipFile(p), rel, opt)
                except zipfile.BadZipFile:
                    pass
            elif p.suffix == ".json":
                self._json(rel, opt, rel, p.read_bytes())
            elif p.suffix == ".nbt":
                self._nbt(rel, p.read_bytes())

    def ids(self, kind, with_opt=True):
        return {k[1] for k, v in self.recs.items() if k[0] == kind and (with_opt or any(not o for _s, o, _d in v))}

    def get(self, kind, i, with_opt=True):
        v = [d for _s, o, d in self.recs.get((kind, i), []) if with_opt or not o]
        return v[-1] if v else None

    def biomes(self, entry, with_opt, seen=()):
        out = set()
        if isinstance(entry, list):
            for e in entry:
                out |= self.biomes(e, with_opt, seen)
        elif isinstance(entry, str) and entry.startswith("#"):
            t = rid(entry[1:])
            if t not in seen:
                vals = set(VANILLA_TAGS.get(t, ()))
                for _s, o, d in self.recs.get(("tag", t), []):
                    if with_opt or not o:                    # a union: conservative, ignores "replace"
                        vals |= {v["id"] if isinstance(v, dict) else v for v in d.get("values", [])}
                for v in vals:
                    out |= self.biomes(v, with_opt, seen + (t,))
        elif isinstance(entry, str):
            out.add(rid(entry))
        return out

    def templates(self, structure):
        """Every template reachable from a structure: any string in its JSON naming a pool or template, every pool's
        element locations, and every pool named inside a reached template (jigsaw blocks), to a fixpoint."""
        pools = self.ids("pool")
        temps, seen, todo = set(), set(), []

        def strings(o):
            if isinstance(o, dict):
                for v in o.values():
                    yield from strings(v)
            elif isinstance(o, list):
                for v in o:
                    yield from strings(v)
            elif isinstance(o, str):
                yield rid(o)

        def visit(obj):
            for s in strings(obj):
                if s in self.nbt and s not in temps:
                    temps.add(s)
                    todo.extend(x for x in self.nbt[s] if x in pools)
                elif s in pools:
                    todo.append(s)

        visit(structure)
        while todo:
            p = todo.pop()
            if p not in seen:
                seen.add(p)
                visit(self.get("pool", p))
        return temps

    def dangers(self):
        """{structure id: (dimensions, danger blocks, always_loaded)} for every Nether/End structure."""
        out = {}
        for sid in self.ids("structure"):
            always = self.get("structure", sid, with_opt=False)
            data = always or self.get("structure", sid)
            b = self.biomes(data.get("biomes", []), with_opt=True)
            dims = sorted(n for n, s in (("the_nether", NETHER), ("the_end", END)) if b & s)
            if not dims:
                continue
            hits = sorted({x for t in self.templates(data) for x in self.nbt[t] if DANGER.match(x)})
            if hits:
                out[sid] = (dims, hits, always is not None)
        return out

    def homes(self, sid):
        """the structure_sets naming a structure"""
        return sorted(k for k in self.ids("set")
                      if any(s.get("structure") == sid for s in self.get("set", k).get("structures", [])))


def declared():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    return data, {e["structure_set"]: kind for kind in ("suppress", "kept", "not_covered") for e in data[kind]}


def build(out, generator=GENERATOR):
    r = subprocess.run([sys.executable, str(generator), "build", "--out", str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return out


def mismatches(up, pack, data):
    """Every suppressed set whose BUILT override is not the upstream set with frequency 0.0, or is missing."""
    bad = []
    for e in data["suppress"]:
        ns, path = e["structure_set"].split(":", 1)
        f = Path(pack) / "data" / ns / "worldgen" / "structure_set" / (path + ".json")
        upstream = up.get("set", e["structure_set"], with_opt=False)
        if upstream is None:
            bad.append("%s: no always-loaded upstream" % e["structure_set"])
            continue
        if not f.is_file():
            bad.append("%s: missing from the built pack" % e["structure_set"])
            continue
        got = json.loads(f.read_text(encoding="utf-8"))
        want = {"structures": upstream["structures"], "placement": dict(upstream["placement"], frequency=0.0)}
        if got != want:
            bad.append("%s: built %s, want %s" % (e["structure_set"], got, want))
    return bad


# ------------------------------------------------------------------ the scanner itself, on a synthetic upstream

def _zip(path, members):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        for name, obj in members.items():
            z.writestr(name, gzip.compress(obj) if name.endswith(".nbt") else json.dumps(obj))


def test_scanner_follows_jigsaw_pools_past_the_start_pool(tmp_path):
    # removing it lets a trainer two pools deep (a gym whose start piece is a corridor) pass unseen
    _zip(tmp_path / "datapacks" / "UP.zip", {
        "data/t/worldgen/structure/deep.json": {"biomes": "#minecraft:is_nether", "start_pool": "t:deep/start"},
        "data/t/worldgen/template_pool/deep/start.json": {"elements": [{"element": {"location": "t:deep/hall"}}]},
        "data/t/structure/deep/hall.nbt": b" minecraft:jigsaw t:deep/rooms ",
        "data/t/worldgen/template_pool/deep/rooms.json": {"elements": [{"element": {"location": "t:deep/arena"}}]},
        "data/t/structure/deep/arena.nbt": b" rctmod:trainer_spawner ",
        "data/t/worldgen/structure_set/deep.json": {"structures": [{"structure": "t:deep"}], "placement": {}},
        "data/t/worldgen/structure/alt.json": {"biomes": ["minecraft:end_midlands"], "start_pool": "t:alt"},
        "data/t/worldgen/template_pool/alt.json": {"elements": [{"element": {"location": "t:alt"}}]},
        "data/t/structure/alt.nbt": b" lumymon:zapdos_altar ",
        "data/t/worldgen/structure/ow.json": {"biomes": ["minecraft:plains"], "start_pool": "t:alt"},
        "data/t/worldgen/structure/benign.json": {"biomes": ["minecraft:warped_forest"], "start_pool": "t:b"},
        "data/t/worldgen/template_pool/b.json": {"elements": [{"element": {"location": "t:b"}}]},
        "data/t/structure/b.nbt": b" minecraft:spawner minecraft:golden_apple ",
    })
    up = Upstream([tmp_path / "datapacks"])
    found = up.dangers()
    assert found == {"t:deep": (["the_nether"], ["rctmod:trainer_spawner"], True),
                     "t:alt": (["the_end"], ["lumymon:zapdos_altar"], True)}
    assert up.homes("t:deep") == ["t:deep"]


# ------------------------------------------------------------------ the real server snapshot

needs_snapshot = pytest.mark.skipif(not (SNAPSHOT / "mods").is_dir(), reason="the offline server snapshot is local")


@pytest.fixture(scope="module")
def real():
    return Upstream([SNAPSHOT / "mods", SNAPSHOT / "datapacks"])


@needs_snapshot
def test_every_dangerous_nether_or_end_structure_has_a_declared_set(real):
    # removing it lets a gym, League or legendary copy that the builder's own scan missed generate in the Nether/End
    data, decl = declared()
    found = real.dangers()
    assert found, "the scan found nothing: the snapshot moved or the scanner broke"
    missing = ["%s %s %s" % (sid, dims, hits) for sid, (dims, hits, _a) in sorted(found.items())
               for h in real.homes(sid) if h not in decl]
    assert missing == []
    # the always-loaded dangers this audit found on 2026-10-08; a new one must be reviewed, not absorbed
    assert {s for s, v in found.items() if v[2]} == {
        "cobbleverse:blaine", "cobbleverse:legendary/moltres", "cobbleverse:kanto_league", "cobbleverse:dawn_tower",
        "cobbleverse:dusk_tower", "legendarymonuments:eternatus_cocoon", "legendarymonuments:stark_mountain",
        "legendarymonuments:firescourge_shrine", "legendarymonuments:grasswither_shrine",
        "legendarymonuments:icerend_shrine", "legendarymonuments:groundblight_shrine"}


@needs_snapshot
def test_not_covered_sets_live_only_in_optional_packs(real):
    # removing it lets a set declared "not covered because optional" ship in an always-loaded pack unsuppressed
    data, _ = declared()
    for e in data["not_covered"]:
        srcs = real.recs.get(("set", e["structure_set"]), [])
        assert srcs and all(o for _s, o, _d in srcs), e["structure_set"]


@needs_snapshot
def test_suppressed_sets_name_only_always_loaded_structures(real):
    # removing it lets an override name a structure only a disabled extra defines: an unbound reference fails the
    # world's registry load at boot and the server does not start
    data, _ = declared()
    always = real.ids("structure", with_opt=False)
    for e in data["suppress"]:
        assert {s["structure"] for s in e["structures"]} <= always, e["structure_set"]


@needs_snapshot
def test_kept_shrines_carry_no_trainer_or_command_block(real):
    # removing it lets a LegendaryMonuments update put a trainer or command chain in the kept Ruinous shrines unseen
    data, _ = declared()
    for e in data["kept"]:
        for sid in e["structures"]:
            temps = real.templates(real.get("structure", sid))
            bad = {x for t in temps for x in real.nbt[t]
                   if x == "rctmod:trainer_spawner" or x.endswith("command_block")}
            assert temps and not bad, (sid, bad)


@needs_snapshot
def test_built_pack_is_upstream_with_frequency_zero(real, tmp_path):
    # removing it lets the shipped override drift from the upstream set (wrong salt/spacing, a dropped set, a
    # misspelt field the codec silently ignores, defaulting frequency to 1.0)
    data, _ = declared()
    assert mismatches(real, build(tmp_path / "pack"), data) == []


@needs_snapshot
@pytest.mark.parametrize("old,new", [
    ('    for e in data["suppress"]:\n        out[', '    for e in data["suppress"][1:]:\n        out['),
    ('placement["frequency"] = FREQUENCY', 'placement["frequncy"] = FREQUENCY'),
    ('FREQUENCY = 0.0', 'FREQUENCY = 0.5'),
])
def test_a_mutated_generator_is_caught(real, tmp_path, old, new):
    # removing it loses the proof that the check above bites on the GENERATOR, not only on the data
    src = GENERATOR.read_text(encoding="utf-8")
    assert src.count(old) == 1, "the generator changed shape; re-point this mutation"
    (tmp_path / "tools").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "dimension_overrides.json").write_text(DATA.read_text(encoding="utf-8"), encoding="utf-8")
    mutant = tmp_path / "tools" / "dimension_overrides.py"
    mutant.write_text(src.replace(old, new), encoding="utf-8")
    data, _ = declared()
    assert mismatches(real, build(tmp_path / "pack", mutant), data) != []

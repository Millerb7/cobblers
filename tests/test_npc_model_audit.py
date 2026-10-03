"""Every NPC class the generators emit renders as a person, not as the green substitute doll (2026-10-02, Hollis).

Disclosed: written by the same agent as the fix and tools/npc_model_audit.py. Its independence rests on the rule and
the assets coming from the jar, and on the mutations being made to the generator, not to any record.

What is asserted, offline, against the Cobblemon 1.8.0 jar (tools/battle_sim.py's copy; the module skips without it):

- the selection rule tools/npc_model_audit.py applies is still in the jar's bytecode (rule_evidence);
- the rule, on Cobblemon's OWN classes from the jar: sacchi and standard carry no resourceIdentifier and still
  resolve, because their class ids have variations; a bare cobblers class with the same keys does not (Hollis's fault);
- every class the three generators emit today (tools/compile_dialogue.py --all, tools/ferries.py, and
  tools/frostpeak_camp.py when the heightmap is readable) resolves to a model, poser and texture in the jar;
- GENERATOR mutations bite, with the authored data untouched: compile_dialogue's NPC_RESOURCE pointed at a name with no
  variation, and compile_conversation stripped of the field, each fail every class;
- a resolver whose aspect-free texture is the player-skin placeholder "variable" is refused (synthetic resolver).

Not covered, and it needs a running client (experiments/EXP-051-npc-models): that the trainer model is what the
owner sees at each NPC, and that no client resource pack shadows Cobblemon's NPC files.
"""
import json
import os
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import battle_sim  # noqa: E402
import compile_dialogue as CD  # noqa: E402
import ferries as FE  # noqa: E402
import npc_model_audit as A  # noqa: E402

try:
    JAR = battle_sim.find_jar()
except battle_sim.SimError:
    JAR = None
pytestmark = pytest.mark.skipif(JAR is None, reason="no Cobblemon 1.8 jar on this machine")

DATA = ROOT / "data"


def write_npcs(files, out: Path):
    """Write only the NPC classes of a generator's {rel: content} into a pack folder."""
    n = 0
    for rel, content in files.items():
        if "/npcs/" in rel.replace("\\", "/"):
            f = out / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(content), encoding="utf-8")
            n += 1
    return n


def generate(tmp: Path, with_camp=True):
    packs = []
    files, done, _ = CD.build_all(DATA)
    p = tmp / "cobblers_dialogue"
    assert write_npcs(files, p) > 0
    packs.append(p)
    ffiles, _ = FE.build(FE.load())
    p = tmp / "cobblers_ferries"
    assert write_npcs(ffiles, p) > 0
    packs.append(p)
    if with_camp and os.environ.get("COBBLERS_SOURCE_ROOT"):
        import frostpeak_camp as FC
        import ground as G
        cfiles, _ = FC.build(FC.load(), G.Ground())
        p = tmp / "cobblers_frostpeak_camp"
        assert write_npcs(cfiles, p) > 0
        packs.append(p)
    return packs


@pytest.fixture(scope="module")
def assets():
    return A.Assets(JAR)


def test_rule_is_still_the_jars():
    assert A.rule_evidence(zipfile.ZipFile(JAR)) == []


def test_rule_on_cobblemons_own_classes(tmp_path, assets):
    z = zipfile.ZipFile(JAR)
    pack = tmp_path / "cobblemon_own"
    for name in ("sacchi", "standard"):
        doc = json.loads(z.read("data/cobblemon/npcs/%s.json" % name))
        assert "resourceIdentifier" not in doc
        f = pack / "data" / "cobblemon" / "npcs" / ("%s.json" % name)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(doc), encoding="utf-8")
    rep = A.audit([pack], JAR)
    assert rep["classes"] == 2 and rep["problems"] == [], rep["problems"]
    assert {r["resource"] for r in rep["rows"]} == {"cobblemon:sacchi", "cobblemon:standard"}


def test_bare_class_is_the_doll(tmp_path):
    """Hollis's class as it shipped before the fix: the same keys, no resourceIdentifier."""
    f = tmp_path / "p" / "data" / "cobblers" / "npcs" / "npc_ursaluna_den_watcher.json"
    f.parent.mkdir(parents=True)
    f.write_text(json.dumps({"hitbox": "player", "names": ["Hollis"], "canDespawn": False, "isInvulnerable": True,
                             "isMovable": False, "isLeashable": False, "allowProjectileHits": False}), encoding="utf-8")
    rep = A.audit([tmp_path / "p"], JAR)
    assert rep["problems"] and "no client variation is named cobblers:npc_ursaluna_den_watcher" in rep["problems"][0]


def test_every_generated_class_resolves(tmp_path):
    packs = generate(tmp_path)
    rep = A.audit(packs, JAR)
    assert rep["problems"] == [], rep["problems"][:5]
    assert rep["classes"] >= 30
    for r in rep["rows"]:
        assert r["model"] and r["poser"] and r["texture"], r


def test_mutation_unknown_resource_bites(tmp_path, monkeypatch):
    monkeypatch.setattr(CD, "NPC_RESOURCE", "cobblemon:nobody_at_all")
    packs = generate(tmp_path, with_camp=False)
    rep = A.audit(packs, JAR)
    assert rep["classes"] > 0
    assert len(rep["problems"]) == rep["classes"], "every class must fail when the generator names no variation"


def test_mutation_field_dropped_bites(tmp_path, monkeypatch):
    real = CD.compile_conversation

    def stripped(*a, **k):
        out = real(*a, **k)
        for rel, doc in out.items():
            if "/npcs/" in rel:
                doc.pop("resourceIdentifier", None)
        return out

    monkeypatch.setattr(CD, "compile_conversation", stripped)
    packs = generate(tmp_path, with_camp=False)
    rep = A.audit(packs, JAR)
    assert rep["classes"] > 0 and len(rep["problems"]) == rep["classes"]
    assert all("no client variation is named cobblers:" in p for p in rep["problems"])


def test_skin_only_variation_is_refused(assets, monkeypatch):
    """A resolver whose only aspect-free texture is the player-skin placeholder does not count as a person."""
    entries = [(0, "x.json", {"name": "cobblers:skin_only", "variations": [
        {"aspects": [], "poser": "cobblemon:standard", "model": "cobblemon:steve.geo", "texture": "variable"}]})]
    real = assets.stack.resolvers()
    monkeypatch.setattr(assets.stack, "resolvers", lambda: {**real, "cobblers:skin_only": entries})
    _, prob = assets.resolve("cobblers:skin_only")
    assert any("variable" in p for p in prob)

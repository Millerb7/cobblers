"""tools/ctm_pack.py: the Rift's connected-textures pack, built from the installed jars.

The pack exists because a 200-block face of one texture reads as a grid. The tests below check the parts that can
be wrong without anyone noticing: a rock the Rift is built from that the pack forgets, a variant set that is not
actually eight different images, and a pack that claims art it did not attribute.
"""
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import ctm_pack as C  # noqa: E402

PIL = pytest.importorskip("PIL.Image")


def _png(size=16, seed=0):
    im = PIL.new("RGBA", (size, size))
    im.putdata([(((x * 7 + y * 13 + seed) % 256), (x * 3) % 256, (y * 5) % 256, 255)
                for y in range(size) for x in range(size)])
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def _jar(tmp_path, textures, models=None, animated=()):
    p = tmp_path / "fake.jar"
    with zipfile.ZipFile(p, "w") as z:
        for name, data in textures.items():
            z.writestr("assets/testmod/textures/block/%s.png" % name, data)
            if name in animated:
                z.writestr("assets/testmod/textures/block/%s.png.mcmeta" % name, "{}")
        for name, doc in (models or {}).items():
            z.writestr("assets/testmod/models/block/%s.json" % name, json.dumps(doc))
    return zipfile.ZipFile(p)


def test_every_rock_the_rift_is_built_from_is_covered():
    # The pack is worth nothing if it misses one band: that band keeps its grid while its neighbours lose theirs.
    spec = json.loads((ROOT / "data" / "rift_fracture.json").read_text(encoding="utf-8"))
    want = set(C.rocks(spec))
    assert want
    named = set(spec["rim"]["materials"]) | {spec["rim"]["streak"]["block"]} | {
        spec["palette"][r]["block"] for r in ("face_upper", "face_lower", "tread")}
    assert want == {b for b in named if not b.startswith("minecraft:")}
    # and the rim itself names no vanilla block, or ctm_pack could never cover it
    assert not [b for b in spec["rim"]["materials"] if b.startswith("minecraft:")], spec["rim"]["materials"]


def test_the_eight_variants_are_eight_different_images():
    out = C.variants(_png())
    assert len(out) == 8
    raw = set()
    for im in out:
        b = io.BytesIO()
        im.save(b, "PNG")
        raw.add(b.getvalue())
    assert len(raw) == 8, "rotations collapsed: the texture would still tile"


def test_a_non_square_texture_is_refused():
    im = PIL.new("RGBA", (16, 32))
    b = io.BytesIO()
    im.save(b, "PNG")
    with pytest.raises(C.CtmError):
        C.variants(b.getvalue())


def test_the_texture_comes_from_the_block_model_when_it_has_one(tmp_path):
    z = _jar(tmp_path, {"rock_side": _png(seed=3)}, models={"rock": {"textures": {"all": "testmod:block/rock_side"}}})
    path, png = C.texture_of([z], "testmod:rock")
    assert path.endswith("rock_side.png") and png


def test_an_animated_texture_is_left_alone(tmp_path):
    # Rotating an animation strip would scramble its frames, so such a block is reported missing rather than broken.
    z = _jar(tmp_path, {"rock": _png(seed=5)}, animated=("rock",))
    path, png = C.texture_of([z], "testmod:rock")
    assert path is None and png is None


def test_a_missing_texture_fails_the_build_rather_than_half_covering(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "rocks", lambda spec: ["testmod:absent"])
    monkeypatch.setattr(C, "OUT", tmp_path / "pack")
    import runtime_guard
    monkeypatch.setattr(runtime_guard, "require_lock", lambda *a, **k: None)
    monkeypatch.setattr(runtime_guard, "check", lambda p, *a, **k: Path(tmp_path))
    with pytest.raises(C.CtmError):
        C.build(str(tmp_path))


def test_the_pack_names_the_licence_of_the_art_it_derives_from(tmp_path, monkeypatch):
    mods = tmp_path / "mods"
    mods.mkdir()
    with zipfile.ZipFile(mods / "m.jar", "w") as z:
        z.writestr("assets/testmod/textures/block/rock.png", _png())
    monkeypatch.setattr(C, "rocks", lambda spec: ["testmod:rock"])
    monkeypatch.setattr(C, "OUT", tmp_path / "pack")
    import runtime_guard
    monkeypatch.setattr(runtime_guard, "require_lock", lambda *a, **k: None)
    monkeypatch.setattr(runtime_guard, "check", lambda p, *a, **k: p)
    assert C.build(str(tmp_path)) == 0
    notice = (tmp_path / "pack" / "NOTICE.md").read_text(encoding="utf-8")
    assert "MPL-2.0" in notice and "not committed" in notice
    props = (tmp_path / "pack" / "assets" / "minecraft" / "optifine" / "ctm" / "rift" / "rock"
             / "rock.properties").read_text(encoding="utf-8")
    assert "matchBlocks=testmod:rock" in props and "method=random" in props and "tiles=0-7" in props
    tiles = sorted((tmp_path / "pack" / "assets" / "minecraft" / "optifine" / "ctm" / "rift" / "rock").glob("*.png"))
    assert len(tiles) == 8


def test_the_generated_pack_is_never_committed():
    # It is art derived from a mod: the generator is ours, the output is disposable.
    import subprocess
    r = subprocess.run(["git", "check-ignore", "-q", "build/resourcepacks/cobblers_rift_ctm"],
                       cwd=ROOT, capture_output=True)
    assert r.returncode == 0, "build/resourcepacks is not gitignored"

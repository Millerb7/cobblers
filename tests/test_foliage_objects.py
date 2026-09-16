"""tools/foliage_objects.py: seeded object generation, measure(), index(), and the committed library's agreement
with the generator.

generate() and index() run with LIB monkeypatched to a tmp directory; kits/structures/foliage is only read.
harvest (RCON against a running server) is never called.

Not covered: what the objects look like in game, whether WorldPainter places them on the marked column (paint.js
was checked on one real export, outside this suite), and the vanilla captures (source "vanilla"), which cannot be
regenerated without a server.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import foliage_objects as FO  # noqa: E402

REAL_LIB = ROOT / "kits" / "structures" / "foliage"


def _hashes(d):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(d).iterdir())}


# Removing this lets a generator draw from an unseeded source (or dict order), so every regeneration rewrites the
# library with new trees and new hashes.
def test_generate_is_byte_for_byte_deterministic(tmp_path, monkeypatch):
    runs = []
    for name in ("a", "b"):
        monkeypatch.setattr(FO, "LIB", tmp_path / name)
        rows = FO.generate()
        runs.append((rows, _hashes(tmp_path / name)))
    (rows_a, hashes_a), (rows_b, hashes_b) = runs
    assert rows_a == rows_b and len(rows_a) > 40
    assert hashes_a == hashes_b
    assert set(hashes_a) == {n + ext for n in rows_a for ext in (".nbt", ".json")}


# Removing this lets the committed generated objects drift from the code that claims to produce them (a generator
# edit without a regenerate, or a hand-edited .nbt).
def test_committed_generated_objects_match_the_generator():
    lib = json.loads((REAL_LIB / "library.json").read_text(encoding="utf-8"))
    rows = {r["name"]: r for r in lib["objects"] if r["source"] == "generated"}
    produced = FO.generated_objects()
    assert set(rows) == set(produced), (set(rows) ^ set(produced))
    for name, (group, builder) in produced.items():
        data, shift = builder.to_bytes()
        r = rows[name]
        assert r["group"] == group, name
        assert r["origin"] == shift, name
        assert r["sha256"] == hashlib.sha256(data).hexdigest(), name


# Removing this lets index() record a hash, origin or group that is not the file's, so WorldPainter offsets and
# the validator's sha check are computed from the wrong row.
def test_index_rows_describe_their_files(tmp_path, monkeypatch):
    monkeypatch.setattr(FO, "LIB", tmp_path)
    FO.generate()
    doc = FO.index()
    assert json.loads((tmp_path / "library.json").read_text(encoding="utf-8")) == doc
    assert doc["schema"] == "cobblers.foliage_library/1"
    for r in doc["objects"]:
        meta = json.loads((tmp_path / (r["name"] + ".json")).read_text(encoding="utf-8"))
        assert r["file"] == r["name"] + ".nbt"
        assert r["sha256"] == hashlib.sha256((tmp_path / r["file"]).read_bytes()).hexdigest()
        assert r["origin"] == meta["origin"] and r["group"] == meta["group"] and r["source"] == "generated"
        for key in ("size", "blocks", "height", "crown_radius", "trunk_footprint", "depth_below_origin", "eye_width",
                    "ground_radius"):
            assert key in r, (r["name"], key)
    groups = {r["group"] for r in doc["objects"]}
    assert set(doc["groups"]) == groups
    assert sum(g["objects"] for g in doc["groups"].values()) == len(doc["objects"])


# Removing this lets measure() count height from the template floor instead of the origin, crowns from the corner of
# the template, roots as trunk footprint, carpets and mushrooms as view-blocking eye width, or ground contact from
# leaves, vines or blocks above the lowest two layers.
def test_measure_on_hand_built_template():
    pal = [("minecraft:oak_log", {"axis": "y"}), ("minecraft:oak_leaves", {}), ("minecraft:moss_carpet", {}),
           ("minecraft:stone", {}), ("minecraft:vine", {"east": "true"})]
    LOG, LEAF, MOSS, STONE, VINE = range(5)
    origin = [2, 1, 2]
    blocks = [
        (2, 0, 2, LOG),                                                  # a root one below the origin layer
        (2, 1, 2, LOG), (3, 1, 2, LOG), (2, 1, 3, LOG), (3, 1, 3, LOG),  # 2x2 trunk base on the origin layer
        (2, 2, 2, LOG), (2, 3, 2, LOG), (2, 4, 2, LOG), (2, 5, 2, LOG),
        (0, 2, 3, STONE), (6, 2, 2, MOSS),                               # eye layer: stone blocks, moss does not
        (5, 4, 2, LEAF), (2, 4, 6, LEAF), (2, 6, 2, LEAF),               # crown: farthest leaf 4 blocks out in z
        (2, 2, 9, VINE),                                                 # low vine: not ground contact
        (9, 3, 9, STONE),                                                # third layer up: not ground contact
    ]
    m = FO.measure({"size": [10, 7, 10], "palette": pal, "blocks": blocks}, origin)
    assert m["height"] == 6, "y1..y6 above the origin layer"
    assert m["crown_radius"] == 4.0
    assert m["ground_radius"] == 4, "the moss carpet at x6 on the second layer (litter and moss count)"
    assert m["trunk_footprint"] == 4
    assert m["eye_width"] == 3, "stone at x0 to the log at x2; the carpet at x6 does not block"
    assert m["depth_below_origin"] == 1
    assert m["blocks"] == len(blocks) and m["size"] == [10, 7, 10]


def _measured(builder, tmp_path):
    data, shift = builder.to_bytes()
    p = tmp_path / "o.nbt"
    p.write_bytes(data)
    return FO.measure(FO.S.load(p), shift)


# Removing this lets a 2x2 trunk at the origin corner report ground radius 0, so placement checks one column and a
# rotated trunk stands on unchecked ground; or lets a wide crown well above the ground inflate the radius.
def test_ground_radius_of_a_2x2_trunk_is_one(tmp_path):
    b = FO.S.Builder()
    FO.trunk(b, 0, 0, 2, 0, 12, "spruce")
    FO.disk(b, 0.5, 6, 0.5, 6.0, FO.leaves("spruce"), np.random.default_rng(0), ragged=0)
    b.setdefault(-5, 1, 0, *FO.leaves("spruce"))                 # a leaf on the second layer does not count
    assert _measured(b, tmp_path)["ground_radius"] == 1


# Removing this lets a fallen log's length or its root plate be left out of ground contact, so a 10-block log is
# placed as if it stood on one column.
@pytest.mark.parametrize("length,expected", [(8, 7), (11, 10), (2, 2)])
def test_ground_radius_of_a_fallen_log_includes_length_and_root_plate(tmp_path, length, expected):
    b = FO.fallen_log(np.random.default_rng(1), length, "spruce")
    # the log runs x 0..length-1 from the origin; the root plate is at x -1 with a rooted-dirt knee at z +-2, which
    # decides the radius of a 2-block log
    m = _measured(b, tmp_path)
    assert m["ground_radius"] == expected


# Removing this lets an object with no trunk or leaves report a zero footprint, which placement would treat as no
# trunk at all.
def test_measure_without_logs_or_leaves_has_footprint_one_and_zero_crown():
    m = FO.measure({"size": [1, 1, 1], "palette": [("minecraft:leaf_litter", {})], "blocks": [(0, 0, 0, 0)]},
                   [0, 0, 0])
    assert m["trunk_footprint"] == 1 and m["crown_radius"] == 0.0 and m["height"] == 1 and m["eye_width"] == 0

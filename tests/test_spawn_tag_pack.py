"""tools/spawn_tag_pack.py: region plan spawn_tag_overlays -> biome-tag overlay datapack, plus the paint exclusivity check.

Synthetic overlays and a small synthetic biomes.png (WorldPainter biome ids from tools/paint_maps.py WP_BIOMES) in
tmp_path; the real data/regions.json is only read, and its pack is built into tmp_path.

Not covered: whether Minecraft 1.21.1 loads the pack and merges the tags (a tag listing a biome id that does not
exist, or a wrong pack_format, only shows up in the server log), whether Cobblemon 1.8 actually spawns on the
merged #cobblemon:is_volcanic / #cobblemon:is_thermal tags, and whether the real paint maps keep each overlay biome
inside its regions (that needs the 8192x8192 biomes.png from a paint run). Those are boot/functional experiments.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import paint_maps as PM  # noqa: E402
import spawn_tag_pack as STP  # noqa: E402

REAL_REGIONS = ROOT / "data" / "regions.json"
RESOURCE_LOCATION = re.compile(r"^[a-z0-9_.-]+:[a-z0-9_./-]+$")

STONY = "minecraft:stony_peaks"
PLATEAU = "minecraft:savanna_plateau"
PLAINS = "minecraft:plains"


def _square(x0, z0, x1, z1):
    return [[x0, z0], [x1, z0], [x1, z1], [x0, z1]]


def _doc(overlays, regions=None):
    return {
        "regions": regions if regions is not None else [
            {"id": "west", "polygons": [_square(0, 0, 9, 19)]},     # columns x 0..9
            {"id": "east", "polygons": [_square(12, 0, 19, 19)]},   # columns x 12..19
        ],
        "spawn_tag_overlays": overlays,
    }


def _volcanic(**extra):
    ov = {"tag": "cobblemon:is_volcanic", "biomes": [STONY, PLATEAU], "regions": ["west"]}
    ov.update(extra)
    return ov


def _biomes_png(path, inside, outside, biome=STONY, elsewhere=PLAINS):
    """20x20 biomes.png: `inside` columns of `biome` in the west region (x 2..7), `outside` in the gap/east (x 10..18)."""
    a = np.full((20, 20), PM.WP_BIOMES[elsewhere], np.uint8)
    cells_in = [(z, x) for z in range(20) for x in range(2, 8)]
    cells_out = [(z, x) for z in range(20) for x in range(10, 19)]
    assert inside <= len(cells_in) and outside <= len(cells_out)
    for z, x in cells_in[:inside]:
        a[z, x] = PM.WP_BIOMES[biome]
    for z, x in cells_out[:outside]:
        a[z, x] = PM.WP_BIOMES[biome]
    Image.fromarray(a).save(path)
    return path


def _row(rows, tag, biome):
    hits = [r for r in rows if r["tag"] == tag and r["biome"] == biome]
    assert len(hits) == 1, rows
    return hits[0]


# ------------------------------------------------------------------ build: tag files and pack


# Protects: tags merge with the upstream Cobblemon tag instead of replacing it; "replace": true would wipe every
# modded biome Cobblemon lists, and optional ids must be {"id", "required": false} or a missing mod fails the pack.
def test_tag_json_appends_required_then_optional_entries_without_replacing(tmp_path):
    doc = _doc([_volcanic(optional_biomes=["minecraft:sulfur_caves", "othermod:ash_field"])])
    STP.build(doc, tmp_path / "pack")
    tag = json.loads((tmp_path / "pack/data/cobblemon/tags/worldgen/biome/is_volcanic.json").read_text(encoding="utf-8"))
    assert tag["replace"] is False
    assert tag["values"] == [
        STONY, PLATEAU,
        {"id": "minecraft:sulfur_caves", "required": False},
        {"id": "othermod:ash_field", "required": False},
    ]
    assert set(tag) == {"replace", "values"}


# Protects: an overlay with no optional_biomes (key absent or null) still builds with only plain string entries.
@pytest.mark.parametrize("optional", [None, "absent", []])
def test_tag_without_optional_biomes_has_only_required_strings(tmp_path, optional):
    ov = _volcanic() if optional == "absent" else _volcanic(optional_biomes=optional)
    STP.build(_doc([ov]), tmp_path / "pack")
    tag = json.loads((tmp_path / "pack/data/cobblemon/tags/worldgen/biome/is_volcanic.json").read_text(encoding="utf-8"))
    assert tag == {"replace": False, "values": [STONY, PLATEAU]}


# Protects: "ns:path" maps to data/<ns>/tags/worldgen/biome/<path>.json (1.21 singular folder names, nested paths
# kept); a wrong folder means the game silently ignores the tag.
def test_tag_namespace_and_path_map_to_worldgen_biome_folder(tmp_path):
    doc = _doc([
        _volcanic(),
        {"tag": "cobblers:region/craters", "biomes": [STONY], "regions": ["west"]},
    ])
    files = STP.build(doc, tmp_path / "pack")
    assert set(files) == {
        "data/cobblemon/tags/worldgen/biome/is_volcanic.json",
        "data/cobblers/tags/worldgen/biome/region/craters.json",
    }
    written = sorted(p.relative_to(tmp_path / "pack").as_posix() for p in (tmp_path / "pack").rglob("*") if p.is_file())
    assert written == sorted(list(files) + ["pack.mcmeta"])


# Protects: pack.mcmeta declares pack_format 48 (Minecraft 1.21.1 data packs); another number makes the server
# flag the pack as incompatible.
def test_pack_mcmeta_declares_1_21_1_data_pack_format(tmp_path):
    STP.build(_doc([_volcanic()]), tmp_path / "pack")
    meta = json.loads((tmp_path / "pack/pack.mcmeta").read_text(encoding="utf-8"))
    assert meta["pack"]["pack_format"] == 48
    assert isinstance(meta["pack"]["description"], str) and meta["pack"]["description"]


# Protects: rebuilding clears the previous output, so an overlay removed from regions.json stops tagging biomes
# instead of lingering as a stale file in the pack.
def test_rebuild_removes_tags_of_dropped_overlays_and_foreign_files(tmp_path):
    out = tmp_path / "pack"
    STP.build(_doc([_volcanic(), {"tag": "cobblemon:is_thermal", "biomes": [STONY], "regions": ["west"]}]), out)
    (out / "data/cobblemon/stray.txt").write_text("left over", encoding="utf-8")
    STP.build(_doc([_volcanic()]), out)
    assert not (out / "data/cobblemon/tags/worldgen/biome/is_thermal.json").exists()
    assert not (out / "data/cobblemon/stray.txt").exists()
    assert (out / "data/cobblemon/tags/worldgen/biome/is_volcanic.json").is_file()


# Protects: a document with no overlays still yields a valid, empty pack rather than crashing.
def test_build_without_overlays_writes_only_pack_mcmeta(tmp_path):
    files = STP.build({"regions": []}, tmp_path / "pack")
    assert files == {}
    assert (tmp_path / "pack/pack.mcmeta").is_file()
    assert [p for p in (tmp_path / "pack").rglob("*") if p.is_file()] == [tmp_path / "pack/pack.mcmeta"]


# ------------------------------------------------------------------ check_paint: exclusivity


# Protects: the leak check passes exactly at min_share and fails just below it; an off-by-one comparison would
# let an identity leak or reject a region that meets the bar.
def test_inside_share_is_ok_at_exactly_min_share_and_not_below(tmp_path):
    png = _biomes_png(tmp_path / "biomes.png", inside=3, outside=1)   # share 0.75
    doc = _doc([{"tag": "cobblemon:is_volcanic", "biomes": [STONY], "regions": ["west"]}])
    at = _row(STP.check_paint(doc, png, 0.75), "cobblemon:is_volcanic", STONY)
    assert at["painted_columns"] == 4
    assert at["inside_share"] == 0.75
    assert at["ok"] is True
    above = _row(STP.check_paint(doc, png, 0.7501), "cobblemon:is_volcanic", STONY)
    assert above["ok"] is False


# Protects: a biome painted entirely inside its regions passes, one painted mostly elsewhere is reported as leaking.
def test_exclusive_biome_passes_and_widespread_biome_leaks(tmp_path):
    png = _biomes_png(tmp_path / "biomes.png", inside=40, outside=0)
    doc = _doc([{"tag": "cobblemon:is_volcanic", "biomes": [STONY, PLAINS], "regions": ["west"]}])
    rows = STP.check_paint(doc, png, 0.95)
    stony = _row(rows, "cobblemon:is_volcanic", STONY)
    assert stony["inside_share"] == 1.0 and stony["ok"] is True
    plains = _row(rows, "cobblemon:is_volcanic", PLAINS)          # plains fills the rest of the 20x20 map
    assert plains["painted_columns"] == 400 - 40
    assert plains["ok"] is False and plains["inside_share"] < 0.95


# Protects: only the overlay's own regions count as inside; paint in another region is a leak.
def test_paint_in_a_region_not_listed_by_the_overlay_counts_as_outside(tmp_path):
    png = _biomes_png(tmp_path / "biomes.png", inside=0, outside=0)
    a = np.asarray(Image.open(png)).copy()
    a[:, 14:18] = PM.WP_BIOMES[STONY]                                # all inside "east"
    Image.fromarray(a).save(png)
    west_only = _doc([{"tag": "cobblemon:is_volcanic", "biomes": [STONY], "regions": ["west"]}])
    assert _row(STP.check_paint(west_only, png, 0.5), "cobblemon:is_volcanic", STONY)["inside_share"] == 0.0
    both = _doc([{"tag": "cobblemon:is_volcanic", "biomes": [STONY], "regions": ["west", "east"]}])
    assert _row(STP.check_paint(both, png, 0.5), "cobblemon:is_volcanic", STONY)["ok"] is True


# Protects: a biome name WorldPainter cannot paint is flagged, not silently skipped or crashed on.
def test_unpaintable_biome_name_is_reported_not_ok(tmp_path):
    png = _biomes_png(tmp_path / "biomes.png", inside=10, outside=0)
    doc = _doc([{"tag": "cobblemon:is_volcanic", "biomes": [STONY, "minecraft:not_a_biome"], "regions": ["west"]}])
    rows = STP.check_paint(doc, png, 0.95)
    bad = _row(rows, "cobblemon:is_volcanic", "minecraft:not_a_biome")
    assert bad["ok"] is False
    assert bad["painted_columns"] == 0 and bad["inside_share"] is None
    assert "paintable" in bad.get("note", "")
    assert _row(rows, "cobblemon:is_volcanic", STONY)["ok"] is True


# Protects: an overlay biome that is never painted is not accepted as exclusive (0 of 0 columns proves nothing).
def test_paintable_biome_absent_from_paint_is_not_ok(tmp_path):
    png = _biomes_png(tmp_path / "biomes.png", inside=0, outside=0)
    doc = _doc([{"tag": "cobblemon:is_volcanic", "biomes": [PLATEAU], "regions": ["west"]}])
    row = _row(STP.check_paint(doc, png, 0.0), "cobblemon:is_volcanic", PLATEAU)
    assert row["painted_columns"] == 0 and row["ok"] is False


# Protects: optional biomes (mod biomes such as sulfur_caves that the paint never uses) are not measured, so an
# optional entry cannot make the check fail for a biome WorldPainter was never asked to paint.
def test_optional_biomes_are_not_measured(tmp_path):
    png = _biomes_png(tmp_path / "biomes.png", inside=10, outside=0)
    doc = _doc([_volcanic(biomes=[STONY], optional_biomes=["minecraft:sulfur_caves"])])
    rows = STP.check_paint(doc, png, 0.95)
    assert [r["biome"] for r in rows] == [STONY]
    assert all(r["ok"] for r in rows)


# ------------------------------------------------------------------ main


def _write(tmp_path, doc):
    p = tmp_path / "regions.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


# Protects: main exits 0 when every overlay biome stays inside its regions and 1 when any row leaks, so a paint
# change that spreads an identity fails the pipeline.
@pytest.mark.parametrize("inside,outside,rc", [(20, 0, 0), (19, 1, 0), (18, 2, 1)])
def test_main_exit_code_follows_the_leak_check(tmp_path, inside, outside, rc):
    doc = _doc([{"tag": "cobblemon:is_volcanic", "biomes": [STONY], "regions": ["west"]}])
    png = _biomes_png(tmp_path / "biomes.png", inside=inside, outside=outside)   # shares 1.0, 0.95, 0.9
    out = tmp_path / "pack"
    assert STP.main(["--regions", str(_write(tmp_path, doc)), "--out", str(out), "--check-paint", str(png),
                     "--min-share", "0.95"]) == rc
    assert (out / "data/cobblemon/tags/worldgen/biome/is_volcanic.json").is_file()


# Protects: an unpaintable biome makes main fail, not just print.
def test_main_fails_on_unpaintable_biome(tmp_path):
    doc = _doc([{"tag": "cobblemon:is_volcanic", "biomes": ["minecraft:not_a_biome"], "regions": ["west"]}])
    png = _biomes_png(tmp_path / "biomes.png", inside=0, outside=0)
    assert STP.main(["--regions", str(_write(tmp_path, doc)), "--out", str(tmp_path / "pack"),
                     "--check-paint", str(png)]) == 1


# Protects: building without a paint check succeeds (exit 0) and does not require a biomes.png.
def test_main_without_check_paint_builds_and_returns_zero(tmp_path):
    doc = _doc([_volcanic()])
    out = tmp_path / "pack"
    assert STP.main(["--regions", str(_write(tmp_path, doc)), "--out", str(out)]) == 0
    assert (out / "pack.mcmeta").is_file()


# Protects: --install replaces an existing installed copy wholesale, so a tag removed from the plan does not
# survive in the server's datapacks folder, and neighbouring datapacks are left alone.
def test_install_replaces_existing_copy_and_leaves_other_packs(tmp_path):
    datapacks = tmp_path / "server_datapacks"
    old = datapacks / STP.PACK_NAME
    (old / "data/cobblemon/tags/worldgen/biome").mkdir(parents=True)
    (old / "data/cobblemon/tags/worldgen/biome/is_thermal.json").write_text("{}", encoding="utf-8")
    (old / "pack.mcmeta").write_text("stale", encoding="utf-8")
    neighbour = datapacks / "someone_elses_pack"
    neighbour.mkdir()
    (neighbour / "pack.mcmeta").write_text("keep", encoding="utf-8")

    doc = _doc([_volcanic()])
    rc = STP.main(["--regions", str(_write(tmp_path, doc)), "--out", str(tmp_path / "pack"),
                   "--install", str(datapacks)])
    assert rc == 0
    installed = sorted(p.relative_to(old).as_posix() for p in old.rglob("*") if p.is_file())
    assert installed == ["data/cobblemon/tags/worldgen/biome/is_volcanic.json", "pack.mcmeta"]
    assert json.loads((old / "pack.mcmeta").read_text(encoding="utf-8"))["pack"]["pack_format"] == 48
    assert (neighbour / "pack.mcmeta").read_text(encoding="utf-8") == "keep"


# Protects: --install still happens (and the exit code still reports the leak) when the paint check fails, so the
# caller sees the failure rather than a silently skipped install; install into a fresh folder works.
def test_install_into_empty_folder_with_failing_check_returns_one(tmp_path):
    doc = _doc([{"tag": "cobblemon:is_volcanic", "biomes": [STONY], "regions": ["west"]}])
    png = _biomes_png(tmp_path / "biomes.png", inside=1, outside=5)
    datapacks = tmp_path / "datapacks"
    datapacks.mkdir()
    rc = STP.main(["--regions", str(_write(tmp_path, doc)), "--out", str(tmp_path / "pack"),
                   "--check-paint", str(png), "--install", str(datapacks)])
    assert rc == 1
    assert (datapacks / STP.PACK_NAME / "pack.mcmeta").is_file()


# ------------------------------------------------------------------ real data/regions.json (read-only)


@pytest.fixture(scope="module")
def real_doc():
    return json.loads(REAL_REGIONS.read_text(encoding="utf-8"))


# Protects: the committed plan actually declares overlays; if the key is renamed the pack builds empty and the
# volcanic/thermal spawns silently never happen.
def test_real_regions_declare_spawn_tag_overlays(real_doc):
    assert real_doc.get("spawn_tag_overlays"), "data/regions.json has no spawn_tag_overlays"


# Protects: the real overlays build into a pack with one file per overlay tag and no crash.
def test_real_overlays_build(real_doc, tmp_path):
    files = STP.build(real_doc, tmp_path / "pack")
    tags = [ov["tag"] for ov in real_doc["spawn_tag_overlays"]]
    assert len(files) == len(tags)
    for rel in files:
        assert (tmp_path / "pack" / rel).is_file()


# Protects: every overlay entry has the fields build/check_paint read, and tag names are valid resource locations
# that are not duplicated (a second overlay with the same tag would overwrite the first file).
def test_real_overlays_have_required_fields_and_unique_valid_tags(real_doc):
    seen = set()
    for ov in real_doc["spawn_tag_overlays"]:
        assert RESOURCE_LOCATION.match(ov["tag"]), ov["tag"]
        assert ov["tag"] not in seen, "duplicate overlay tag %s" % ov["tag"]
        seen.add(ov["tag"])
        assert ov.get("biomes"), ov["tag"]
        assert ov.get("regions"), ov["tag"]
        for b in list(ov["biomes"]) + list(ov.get("optional_biomes") or []):
            assert RESOURCE_LOCATION.match(b), (ov["tag"], b)


# Protects: every overlay region id names a region in the plan; a typo would leave the region mask empty and the
# paint check would call every biome a leak (or, worse, pass vacuously after a fix to the tool).
def test_real_overlay_region_ids_exist(real_doc):
    ids = {r["id"] for r in real_doc["regions"]}
    for ov in real_doc["spawn_tag_overlays"]:
        missing = [r for r in ov["regions"] if r not in ids]
        assert not missing, (ov["tag"], missing)
        for r in real_doc["regions"]:
            if r["id"] in ov["regions"]:
                assert r.get("polygons"), "region %s has no polygons to measure paint against" % r["id"]


# Protects: every required overlay biome is a biome WorldPainter can paint (so check_paint can measure it) and is
# one of the biomes its regions are planned with; an identity tag on a biome the region never uses tags nothing
# there and only leaks elsewhere.
def test_real_overlay_biomes_are_paintable_and_planned_in_their_regions(real_doc):
    by_id = {r["id"]: r for r in real_doc["regions"]}
    for ov in real_doc["spawn_tag_overlays"]:
        planned = set()
        for rid in ov["regions"]:
            planned.update(by_id[rid].get("biomes") or [])
        for b in ov["biomes"]:
            assert b in PM.WP_BIOMES, (ov["tag"], b, "not paintable")
            assert b in planned, (ov["tag"], b, "not among biomes of", ov["regions"])


# Protects: optional biomes are the escape hatch for mod biomes; a vanilla paintable biome listed as optional
# would be tagged without ever being exclusivity-checked.
def test_real_optional_biomes_are_not_paintable_vanilla_biomes(real_doc):
    for ov in real_doc["spawn_tag_overlays"]:
        for b in ov.get("optional_biomes") or []:
            assert b not in PM.WP_BIOMES, (ov["tag"], b)
            assert b not in ov["biomes"], (ov["tag"], b)

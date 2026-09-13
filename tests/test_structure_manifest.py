import json

from tools.validate import Context, check_structure_manifest


def write_manifest(root, data):
    path = root / "kits" / "structures" / "manifests" / "structure-dependencies.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def write_raw_manifest(root, text):
    path = root / "kits" / "structures" / "manifests" / "structure-dependencies.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def base_manifest():
    return {
        "schema": "cobblers.structure-dependencies/1",
        "components": {"cobblemon": {"kind": "mod", "runtime_id": "cobblemon"}},
        "verified_structures": [{
            "catalog_id": "CBM-CENTER-01",
            "source_component": "cobblemon",
            "structure_id": "cobblemon:test/center",
            "implementation": "VANILLA_STRUCTURE_NBT",
            "dimensions": [1, 2, 3],
            "evidence": "test.jar!data/cobblemon/structure/test/center.nbt",
        }],
        "campaign_structures": [],
    }


def issues_for(root, data):
    write_manifest(root, data)
    ctx = Context(root, strict_base=False)
    check_structure_manifest(ctx)
    return [issue.message for issue in ctx.issues if issue.level == "error"]


def test_repository_structure_manifest_is_valid(repo_root):
    ctx = Context(repo_root, strict_base=False)
    check_structure_manifest(ctx)
    assert not [issue for issue in ctx.issues if issue.level == "error"]


def test_structure_manifest_rejects_duplicate_and_broken_references(tmp_path):
    data = base_manifest()
    data["verified_structures"].append({
        **data["verified_structures"][0],
        "source_component": "missing-mod",
    })
    data["campaign_structures"].append({
        "id": "campaign:test_center",
        "based_on": "MISSING-ID",
        "asset": "kits/structures/campaign/towns/test.nbt",
        "required_components": ["missing-mod"],
    })
    errors = issues_for(tmp_path, data)
    assert any("duplicate catalog_id" in error for error in errors)
    assert any("unknown source_component" in error for error in errors)
    assert any("based_on references unknown" in error for error in errors)
    assert any("unknown required component" in error for error in errors)
    assert any("missing asset" in error for error in errors)


def test_structure_manifest_requires_dependencies_for_every_campaign_asset(tmp_path):
    data = base_manifest()
    asset = tmp_path / "kits" / "structures" / "campaign" / "towns" / "orphan.nbt"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"test")
    errors = issues_for(tmp_path, data)
    assert any("no dependency-manifest entry" in error for error in errors)


def test_structure_manifest_rejects_malformed_and_non_object_json(tmp_path):
    write_raw_manifest(tmp_path, "{")
    ctx = Context(tmp_path, strict_base=False)
    check_structure_manifest(ctx)
    assert any("invalid JSON" in issue.message for issue in ctx.issues)

    write_raw_manifest(tmp_path, "[]")
    ctx = Context(tmp_path, strict_base=False)
    check_structure_manifest(ctx)
    assert any("root must be an object" in issue.message for issue in ctx.issues)


def test_structure_manifest_rejects_unhashable_references_and_path_escape(tmp_path):
    data = base_manifest()
    data["verified_structures"][0]["source_component"] = []
    data["campaign_structures"].append({
        "id": "campaign:escape",
        "based_on": [],
        "asset": "kits/structures/campaign/../../../outside.nbt",
        "required_components": [[]],
    })
    (tmp_path / "outside.nbt").write_bytes(b"test")
    errors = issues_for(tmp_path, data)
    assert any("unknown source_component" in error for error in errors)
    assert any("based_on references unknown" in error for error in errors)
    assert any("unknown required component" in error for error in errors)
    assert any("asset escapes campaign structure root" in error for error in errors)


def test_structure_manifest_checks_component_against_pack_manifest(tmp_path):
    pack = tmp_path / "modpack" / "manifest" / "base-cobbleverse-1.7.42.json"
    pack.parent.mkdir(parents=True)
    pack.write_text(json.dumps({"files": [{"kind": "mod", "mod_id": "other", "filename": "other.jar"}]}), encoding="utf-8")
    errors = issues_for(tmp_path, base_manifest())
    assert any("runtime mod id 'cobblemon' is absent" in error for error in errors)

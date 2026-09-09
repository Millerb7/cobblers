import csv
import json
import subprocess

import pytest


@pytest.fixture(scope="module")
def base(repo_root):
    return json.loads((repo_root / "modpack/manifest/base-cobbleverse-1.7.42.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def overlay(repo_root):
    return json.loads((repo_root / "modpack/manifest/overlay.json").read_text(encoding="utf-8"))


def test_every_csv_hash_in_base_manifest(repo_root, base):
    with open(repo_root / "base-pack/inventory/pack_hashes.csv", newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    in_manifest = {f["sha256"]: f["path"] for f in base["files"]}
    missing = [r["relative_path"] for r in rows if r["sha256"] not in in_manifest]
    assert not missing, f"hashes in pack_hashes.csv but not in base manifest: {missing}"
    assert len([f for f in base["files"] if f.get("in_hash_csv", True)]) == len(rows)


def test_base_manifest_records_are_complete(base):
    for f in base["files"]:
        assert f["kind"] in ("mod", "resourcepack", "datapack", "shaderpack"), f
        assert f["side"] in ("client", "server", "both"), f
        assert f["source"]["type"] in ("modrinth", "unresolved"), f
        if f["kind"] == "mod":
            assert f.get("mod_id"), f["filename"]
        if f["source"]["type"] == "modrinth":
            assert f["source"]["url"] and f["source"]["version_id"], f["filename"]


def test_overlay_references_known_mod_ids(base, overlay):
    known = {f.get("mod_id") for f in base["files"] if f.get("mod_id")}
    known |= {a["mod_id"] for a in overlay.get("add", [])}
    for section in ("replace", "remove", "needs_functional_test"):
        unknown = [e["mod_id"] for e in overlay[section] if e["mod_id"] not in known]
        assert not unknown, f"overlay.{section} references unknown mod ids: {unknown}"
    unknown = [m for m in overlay["server_exclude"] if m not in known]
    assert not unknown, f"overlay.server_exclude references unknown mod ids: {unknown}"


def test_overlay_remove_file_pins_exist(base, overlay):
    filenames = {f["filename"] for f in base["files"]}
    for e in overlay["remove"]:
        if e.get("file"):
            assert e["file"] in filenames, e


def test_server_exclude_matches_client_side_mods(base, overlay):
    mods = [f for f in base["files"] if f["kind"] == "mod"]
    client = {f["mod_id"] for f in mods if f["side"] == "client"}
    non_client = {f["mod_id"] for f in mods if f["side"] != "client"}
    assert sorted(overlay["server_exclude"]) == sorted(client - non_client)
    assert sorted(e["mod_id"] for e in overlay.get("server_exclude_ambiguous", [])) == sorted(client & non_client)


def test_replace_entries_are_verified_or_flagged(overlay):
    for e in overlay["replace"]:
        v = e.get("verification", "unverified")
        if v != "unverified":
            assert e.get("sha512") and e["modrinth"].get("version_id") and e["modrinth"].get("url"), e["mod_id"]


def test_plan_server_side_has_no_client_mods(repo_root, python, overlay):
    r = subprocess.run(
        [python, "tools/pack_manifest.py", "plan", "--side", "server", "--json"],
        cwd=repo_root, capture_output=True, text=True, check=True,
    )
    plan = json.loads(r.stdout)
    active = [e for e in plan if e["status"] in ("base", "replace", "add")]
    excluded = set(overlay["server_exclude"])
    leaked = [e["mod_id"] for e in active if e["mod_id"] in excluded]
    assert not leaked, leaked
    assert {e["status"] for e in plan} >= {"base", "replace", "remove"}
    assert any(e["filename"] == "Cobblemon-fabric-1.8.0+1.21.1.jar" for e in active)

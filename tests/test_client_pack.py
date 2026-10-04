"""tools/client_pack.py: the players' .mrpack. Fixtures only; no network, nothing written outside tmp_path."""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import client_pack as cp  # noqa: E402
import pack_manifest as pm  # noqa: E402


def h(data: bytes) -> dict:
    return {"sha1": hashlib.sha1(data).hexdigest(), "sha512": hashlib.sha512(data).hexdigest(), "sha256": hashlib.sha256(data).hexdigest()}


MOD_BOTH = b"jar-both"
MOD_CLIENT = b"jar-client"
MOD_NEW = b"jar-new-version"
RP_MANUAL = b"PK\x03\x04 cobbleverse own pack"
RP_OPTIONAL_MANUAL = b"PK\x03\x04 licence-restricted pack"


def url(name: str) -> str:
    return f"https://cdn.modrinth.com/data/P/versions/V/{name}"


def base_file(path, kind, side, data, mod_id=None, resolved=True):
    name = path.rsplit("/", 1)[-1]
    return {
        "path": path, "kind": kind, "filename": name, "size": len(data), "side": side, "mod_id": mod_id,
        **h(data),
        "source": {"type": "modrinth", "url": url(name.replace(" ", "%20")), "filename": name} if resolved else {"type": "unresolved"},
    }


def fixture_inputs():
    base = {
        "target": {"minecraft": "1.21.1"},
        "files": [
            base_file("mods/both-1.0.jar", "mod", "both", MOD_BOTH, "both"),
            base_file("mods/client-1.0.jar", "mod", "client", MOD_CLIENT, "clientonly"),
            base_file("mods/old-1.0.jar", "mod", "both", b"old", "replaced"),
            base_file("mods/gone-1.0.jar", "mod", "both", b"gone", "gone"),
            base_file("mods/xclient-1.0.jar", "mod", "both", b"xc", "serverexcluded"),
            base_file("resourcepacks/Own RP.zip", "resourcepack", "client", RP_MANUAL, resolved=False),
            base_file("resourcepacks/Restricted RP.zip", "resourcepack", "client", RP_OPTIONAL_MANUAL, resolved=False),
            base_file("datapacks/World-DP.zip", "datapack", "both", b"dp", resolved=False),
        ],
    }
    overlay = {
        "target": {"minecraft": "1.21.1"},
        "replace": [{"mod_id": "replaced", "to_version": "2.0", "to_file": "new-2.0.jar", **{k: v for k, v in h(MOD_NEW).items() if k != "sha256"},
                     "modrinth": {"url": url("new-2.0.jar"), "size": len(MOD_NEW), "version_id": "V", "project_id": "P", "filename": "new-2.0.jar"}}],
        "remove": [{"mod_id": "gone", "reason": "test"}],
        "add": [],
        "server_exclude": ["serverexcluded"],
    }
    opt = b"optional resource pack"
    cfg = {
        "pack": {"name": "Cobblers", "version": "9.9.9", "summary": "test"},
        "exclude_kinds": {"datapack": "server data"},
        "optional_files": [{"path": "resourcepacks/Opt [v4].zip", "modrinth": {"url": url("Opt%20%5Bv4%5D.zip")},
                            "sha1": h(opt)["sha1"], "sha512": h(opt)["sha512"], "size": len(opt)}],
        "cobbleverse_mrpack": {
            "filename": "CV.mrpack", "overrides_prefix": "overrides/", "sha1": "x",
            "override_files": {"resourcepacks/Own RP.zip": len(RP_MANUAL), "resourcepacks/Restricted RP.zip": len(RP_OPTIONAL_MANUAL)},
            "cosmetic_prefixes": {"config/art/": "art"},
        },
        "manual_optional": {"resourcepacks/Restricted RP.zip": "licence"},
    }
    return base, overlay, cfg


def plan_of():
    base, overlay, cfg = fixture_inputs()
    return cfg, cp.client_plan(base, overlay, cfg)


# ------------------------------------------------------------------- plan
def test_index_follows_the_modrinth_format():
    cfg, plan = plan_of()
    idx = cp.build_index(cfg, plan, "1.21.1", "0.19.5")
    assert idx["formatVersion"] == 1 and idx["game"] == "minecraft" and idx["versionId"] == "9.9.9"
    assert idx["dependencies"] == {"minecraft": "1.21.1", "fabric-loader": "0.19.5"}
    for f in idx["files"]:
        assert set(f) == {"path", "hashes", "env", "downloads", "fileSize"}
        assert set(f["hashes"]) == {"sha1", "sha512"}
        assert f["env"]["client"] in ("required", "optional") and f["env"]["server"] in ("required", "unsupported")
        assert all(u.startswith("https://") and " " not in u for u in f["downloads"])
        assert cp.safe_path(f["path"])


def test_plan_sides_replacements_removals_and_exclusions():
    cfg, plan = plan_of()
    by = {f["path"]: f for f in plan["files"]}
    assert set(by) == {"mods/both-1.0.jar", "mods/client-1.0.jar", "mods/new-2.0.jar", "mods/xclient-1.0.jar", "resourcepacks/Opt [v4].zip"}
    assert by["mods/both-1.0.jar"]["env"] == {"client": "required", "server": "required"}
    assert by["mods/client-1.0.jar"]["env"]["server"] == "unsupported"
    assert by["mods/xclient-1.0.jar"]["env"]["server"] == "unsupported"  # overlay server_exclude
    assert by["mods/new-2.0.jar"]["hashes"]["sha512"] == h(MOD_NEW)["sha512"]
    assert by["resourcepacks/Opt [v4].zip"]["env"]["client"] == "optional"
    assert [m["path"] for m in plan["manual"]] == ["resourcepacks/Own RP.zip"]
    assert [m["path"] for m in plan["manual_optional"]] == ["resourcepacks/Restricted RP.zip"]
    assert [e["path"] for e in plan["excluded"]] == ["datapacks/World-DP.zip"]


def test_required_file_with_no_url_and_no_manual_source_fails_loudly():
    base, overlay, cfg = fixture_inputs()
    del cfg["cobbleverse_mrpack"]["override_files"]["resourcepacks/Own RP.zip"]
    with pytest.raises(cp.PackError, match="Own RP.zip: required on the client, no download URL"):
        cp.client_plan(base, overlay, cfg)


def test_manual_size_disagreement_fails():
    base, overlay, cfg = fixture_inputs()
    cfg["cobbleverse_mrpack"]["override_files"]["resourcepacks/Own RP.zip"] += 1
    with pytest.raises(cp.PackError, match="manifest says"):
        cp.client_plan(base, overlay, cfg)


def test_url_file_without_sha512_fails():
    base, overlay, cfg = fixture_inputs()
    base["files"][0]["sha512"] = None
    with pytest.raises(cp.PackError, match="no sha512"):
        cp.client_plan(base, overlay, cfg)


def test_unencoded_space_in_url_fails():
    base, overlay, cfg = fixture_inputs()
    base["files"][0]["source"]["url"] = "https://cdn.modrinth.com/data/P/versions/V/a b.jar"
    with pytest.raises(cp.PackError, match="RFC 3986"):
        cp.client_plan(base, overlay, cfg)


@pytest.mark.parametrize("p,ok", [("mods/a.jar", True), ("../a.jar", False), ("/a.jar", False), ("C:/a.jar", False), ("mods/../../a", False)])
def test_safe_path(p, ok):
    assert cp.safe_path(p) is ok


def test_fabric_loader_is_read_from_state(tmp_path):
    (tmp_path / "STATE.md").write_text("- **Runtime:** Minecraft 1.21.1, Fabric Loader 0.19.5, Cobblemon 1.8.0\n", encoding="utf-8")
    src = {"file": "STATE.md", "pattern": json.loads((ROOT / "data/client_pack.json").read_text(encoding="utf-8"))["fabric_loader_from"]["pattern"]}
    assert cp.fabric_loader({"fabric_loader_from": src}, tmp_path) == "0.19.5"
    (tmp_path / "STATE.md").write_text("no runtime line\n", encoding="utf-8")
    with pytest.raises(cp.PackError):
        cp.fabric_loader({"fabric_loader_from": src}, tmp_path)


# ----------------------------------------------------------------- embeds
def embed_tree(tmp_path, files):
    for rel, data in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def ls(root, rel):
        return sorted(k for k in files if k.startswith(rel + "/"))
    return ls


EMBED_CFG = {"embed": {
    "sources": [{"from": "base/config", "to": "config"}, {"from": "ours/config", "to": "config"},
                {"from": "base/licenses", "to": "licenses", "suffixes": [".txt"]}],
    "skip_names": ["README.md"],
    "exclude": {"config/servers.dat": "address", "config/removedmod/": "removed"},
}}


def test_embeds_later_source_wins_and_exclusions_hold(tmp_path):
    ls = embed_tree(tmp_path, {
        "base/config/a.toml": b"base", "ours/config/a.toml": b"ours", "base/config/servers.dat": b"x",
        "base/config/removedmod/c.json": b"{}", "ours/config/README.md": b"doc",
        "base/licenses/L.txt": b"licence", "base/licenses/logo.png": b"\x89PNG",
    })
    emb = cp.collect_embeds(EMBED_CFG, tmp_path, ls)
    assert set(emb) == {"config/a.toml", "licenses/L.txt"}
    assert emb["config/a.toml"].read_bytes() == b"ours"
    cp.check_embeds(emb, set())


@pytest.mark.parametrize("name,data", [("x.toml", b"PK\x03\x04zip"), ("x.json", b"a\x00b"), ("x.png", b"text"), ("x.jar", b"text")])
def test_embed_never_carries_an_archive_image_or_binary(tmp_path, name, data):
    p = tmp_path / name
    p.write_bytes(data)
    with pytest.raises(cp.PackError, match="never embedded"):
        cp.check_embeds({f"config/{name}": p}, set())


def test_embed_may_not_shadow_a_pack_file(tmp_path):
    q = tmp_path / "both-1.0.jar"
    q.write_bytes(b"t")
    with pytest.raises(cp.PackError):
        cp.check_embeds({"mods/both-1.0.jar": q}, {"both-1.0.jar"})


# ------------------------------------------------------------------ write
def test_mrpack_is_deterministic_and_holds_only_index_and_overrides(tmp_path):
    cfg, plan = plan_of()
    idx = cp.build_index(cfg, plan, "1.21.1", "0.19.5")
    src = tmp_path / "a.toml"
    src.write_bytes(b"k = 1\n")
    a = cp.write_mrpack(tmp_path / "out1" / "p.mrpack", idx, {"config/a.toml": src})
    b = cp.write_mrpack(tmp_path / "out2" / "p.mrpack", idx, {"config/a.toml": src})
    assert a["sha1"] == b["sha1"] and set(a) == {"path", "size", "sha1", "sha512"}
    with zipfile.ZipFile(a["path"]) as z:
        assert z.namelist() == ["modrinth.index.json", "overrides/config/a.toml"]
        assert json.loads(z.read("modrinth.index.json")) == idx


# ----------------------------------------------------------------- verify
def instance(tmp_path, files):
    g = tmp_path / "inst" / ".minecraft"
    for rel, data in files.items():
        (g / rel).parent.mkdir(parents=True, exist_ok=True)
        (g / rel).write_bytes(data)
    (g / "mods").mkdir(parents=True, exist_ok=True)
    return g


def test_verify_a_complete_instance_passes_without_optionals(tmp_path):
    cfg, plan = plan_of()
    idx = cp.build_index(cfg, plan, "1.21.1", "0.19.5")
    g = instance(tmp_path, {"mods/both-1.0.jar": MOD_BOTH, "mods/client-1.0.jar": MOD_CLIENT, "mods/new-2.0.jar": MOD_NEW,
                            "mods/xclient-1.0.jar": b"xc", "resourcepacks/Own RP.zip": RP_MANUAL})
    assert cp.game_dir(tmp_path / "inst") == g
    res = cp.verify_instance(g, idx, plan)
    assert not res["missing"] and not res["mismatch"] and not res["extra_mods"]
    assert sorted(res["optional_absent"]) == ["resourcepacks/Opt [v4].zip", "resourcepacks/Restricted RP.zip"]


def test_verify_names_missing_mismatched_and_extra(tmp_path):
    cfg, plan = plan_of()
    idx = cp.build_index(cfg, plan, "1.21.1", "0.19.5")
    g = instance(tmp_path, {"mods/both-1.0.jar": b"tampered", "mods/old-1.0.jar": b"old", "mods/new-2.0.jar": MOD_NEW})
    res = cp.verify_instance(g, idx, plan)
    assert res["mismatch"] == ["mods/both-1.0.jar"]
    assert "mods/client-1.0.jar" in res["missing"] and "resourcepacks/Own RP.zip" in res["missing"]
    assert res["extra_mods"] == ["mods/old-1.0.jar"]


# ----------------------------------------------------------------- manual
def cobbleverse_zip(tmp_path, own=RP_MANUAL):
    p = tmp_path / "CV.mrpack"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("modrinth.index.json", "{}")
        z.writestr("overrides/resourcepacks/Own RP.zip", own)
        z.writestr("overrides/resourcepacks/Restricted RP.zip", RP_OPTIONAL_MANUAL)
        z.writestr("overrides/config/art/a.png", b"art")
        z.writestr("overrides/config/art/keep.png", b"theirs")
    return p


def test_manual_copies_verified_files_and_never_overwrites_cosmetics(tmp_path):
    cfg, plan = plan_of()
    g = instance(tmp_path, {"config/art/keep.png": b"mine"})
    res = cp.extract_manual(cobbleverse_zip(tmp_path), g, plan, cfg, cosmetic=True, optional=False)
    assert res["copied"] == ["resourcepacks/Own RP.zip"] and not res["failed"]
    assert (g / "resourcepacks/Own RP.zip").read_bytes() == RP_MANUAL
    assert not (g / "resourcepacks/Restricted RP.zip").exists()
    assert (g / "config/art/a.png").read_bytes() == b"art" and (g / "config/art/keep.png").read_bytes() == b"mine"
    again = cp.extract_manual(cobbleverse_zip(tmp_path), g, plan, cfg, cosmetic=False, optional=False)
    assert again["present"] == ["resourcepacks/Own RP.zip"] and not again["copied"]


def test_manual_refuses_a_file_whose_hash_differs(tmp_path):
    cfg, plan = plan_of()
    g = instance(tmp_path, {})
    res = cp.extract_manual(cobbleverse_zip(tmp_path, own=b"other"), g, plan, cfg, cosmetic=False, optional=False)
    assert res["failed"] and not (g / "resourcepacks/Own RP.zip").exists()


# ---------------------------------------------------- the real repository
@pytest.fixture(scope="module")
def real():
    cfg = cp.load_config()
    base = pm.load_json(pm.BASE_MANIFEST)
    overlay = pm.load_json(pm.OVERLAY)
    plan = cp.client_plan(base, overlay, cfg)
    return cfg, base, plan


def test_real_loader_matches_the_state_runtime_line(real):
    cfg, _, _ = real
    state = (ROOT / "docs/STATE.md").read_text(encoding="utf-8")
    line = next(l for l in state.splitlines() if l.startswith("- **Runtime:**"))
    assert f"Fabric Loader {cp.fabric_loader(cfg)}," in line


def test_real_plan_never_lists_a_no_redistribution_file_by_url(real):
    _, base, plan = real
    unresolved = {f["path"] for f in base["files"] if f["source"]["type"] == "unresolved"}
    assert not unresolved & {f["path"] for f in plan["files"]}
    assert all(f["downloads"][0].startswith("https://cdn.modrinth.com/") for f in plan["files"])
    assert "resourcepacks/ATMxMSD RP.zip" not in {f["path"] for f in plan["files"]}
    assert [f["path"] for f in plan["files"] if f["env"]["client"] == "optional"] == ["resourcepacks/ATM x MSD [v4.0].zip"]


def test_real_every_manual_file_is_in_the_cobbleverse_mrpack_record(real):
    cfg, _, plan = real
    rec = cfg["cobbleverse_mrpack"]["override_files"]
    assert plan["manual"] and all(m["path"] in rec and m["sha512"] for m in plan["manual"] + plan["manual_optional"])


def test_real_embeds_are_tracked_text_and_never_a_pack_file(real):
    cfg, base, plan = real
    emb = cp.collect_embeds(cfg)
    names = {Path(f["path"]).name for f in base["files"]} | {Path(f["path"]).name for f in plan["files"]}
    cp.check_embeds(emb, names)
    assert "config/defaultoptions/servers.dat" not in emb
    assert not [d for d in emb if d.startswith(("mods/", "datapacks/"))]
    # our overlay wins over the base copy of the same config path
    assert emb["config/resourcepackoverrides.json"] == ROOT / "modpack/config/resourcepackoverrides.json"

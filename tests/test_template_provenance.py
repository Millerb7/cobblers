"""check_template_provenance in tools/validate.py: no structure template reaches git without a permissive source.

The fixture is a throwaway git repository in tmp_path with a kits/PROVENANCE.json. Each rule has a passing baseline
and a minimal breaking change. The last test runs the check on this repository.

Not covered: whether a record's licence claim is true. That is a human reading the source's terms.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import validate as V  # noqa: E402

PROVENANCE = {
    "schema": "cobblers.provenance/1",
    "permissive": ["MIT", "original", "generated"],
    "records": [
        {"paths": ["kits/structures/own/**/*.nbt"], "licence": "original", "source": "authored"},
        {"paths": ["kits/structures/mit/*.nbt"], "licence": "MIT", "source": "donor",
         "notice": "kits/structures/licenses/DONOR.md"},
        {"paths": ["kits/structures/arr/*.nbt"], "licence": "LicenseRef-All-Rights-Reserved", "source": "arr pack",
         "local_only": True},
    ],
}


def git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def write(root, rel, data=b"\x0a\x00\x00\x00"):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q")
    write(tmp_path, "kits/PROVENANCE.json", json.dumps(PROVENANCE))
    write(tmp_path, ".gitignore", "kits/structures/arr/*.nbt\n")
    write(tmp_path, "kits/structures/own/a/house.nbt")
    write(tmp_path, "kits/structures/mit/shop.nbt")
    write(tmp_path, "kits/structures/licenses/DONOR.md", "MIT")
    write(tmp_path, "kits/structures/arr/center.nbt")
    git(tmp_path, "add", "-A")
    return tmp_path


def errors(root):
    ctx = V.Context(root, strict_base=False)
    V.check_template_provenance(ctx)
    return [(i.path, i.message) for i in ctx.issues if i.level == "error"]


def test_baseline_passes(repo):
    assert errors(repo) == []


def test_template_without_record_fails(repo):
    write(repo, "kits/structures/stray.nbt")
    assert [p for p, _ in errors(repo)] == ["kits/structures/stray.nbt"]


def test_untracked_template_is_checked_before_add(repo):
    write(repo, "tests/fixtures/new.schem")
    assert [p for p, _ in errors(repo)] == ["tests/fixtures/new.schem"]


def test_force_added_non_permissive_template_fails(repo):
    git(repo, "add", "-f", "kits/structures/arr/center.nbt")
    (path, message), = errors(repo)
    assert path == "kits/structures/arr/center.nbt" and "not permissive" in message


def test_non_permissive_template_outside_gitignore_fails(repo):
    (repo / ".gitignore").write_text("", encoding="utf-8")
    assert [p for p, _ in errors(repo)] == ["kits/structures/arr/center.nbt"]


def test_third_party_template_needs_its_notice(repo):
    (repo / "kits/structures/licenses/DONOR.md").unlink()
    assert [p for p, _ in errors(repo)] == ["kits/structures/mit/shop.nbt"]


def test_missing_provenance_file_fails(repo):
    (repo / "kits/PROVENANCE.json").unlink()
    assert errors(repo)


def test_this_repository_passes():
    assert errors(ROOT) == []

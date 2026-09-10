import subprocess


def test_validate_runs(repo_root, python):
    r = subprocess.run([python, "tools/validate.py", "-v"], cwd=repo_root, capture_output=True, text=True)
    assert r.returncode == 0, f"validate.py failed:\n{r.stdout}\n{r.stderr}"
    assert "errors" in r.stdout


def test_validate_lists_extension_points(repo_root, python):
    r = subprocess.run([python, "tools/validate.py", "--list"], cwd=repo_root, capture_output=True, text=True)
    assert r.returncode == 0
    for name in ("duplicate_ids", "missing_pokemon_refs", "broken_refs", "progression_deps", "structure_manifest"):
        assert name in r.stdout

"""tools/server_config_record.py: the repo's record of the server's configs detects drift and install keeps it in step.

Every fixture is a synthetic tree under tmp_path laid out like the repo (modpack/config, server/config/mods,
base-pack/cobbleverse/config) plus a synthetic server `config/` folder; the module's ROOT, OVERLAY, MIRROR and BASE are
pointed at it. No real server directory is read. The last tests check properties of the committed record itself.

Not covered here: whether a mod reads a config the way `comparable()` assumes (for example that it ignores comment
lines, or that two JSON documents with the same values are read the same). That is runtime behaviour, not validity.
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import server_config_record as SCR  # noqa: E402

DH = "DistantHorizons.toml"
DH_OVERLAY = ("# Distant Horizons\n"
              "[server]\n"
              "\tenableServerGeneration = false\n"
              "\tserverId = 0\n"
              "\tgenerationBoundsRadius = 5120\n")
DH_SERVER = DH_OVERLAY.replace("serverId = 0", "serverId = 918273645")


class Repo:
    def __init__(self, root: Path, server: Path):
        self.root, self.server = root, server
        self.overlay = root / "modpack" / "config"
        self.mirror = root / "server" / "config" / "mods"
        self.base = root / "base-pack" / "cobbleverse" / "config"
        self.cfg = server / "config"

    def put(self, folder: Path, rel: str, text: str, newline="\n"):
        p = folder / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.replace("\n", newline).encode("utf-8"))
        return p


@pytest.fixture
def repo(tmp_path, monkeypatch):
    r = Repo(tmp_path / "repo", tmp_path / "staging-server")
    for d in (r.overlay, r.mirror, r.base, r.cfg):
        d.mkdir(parents=True)
    monkeypatch.setattr(SCR, "ROOT", r.root)
    monkeypatch.setattr(SCR, "OVERLAY", r.overlay)
    monkeypatch.setattr(SCR, "MIRROR", r.mirror)
    monkeypatch.setattr(SCR, "BASE", r.base)
    return r


@pytest.fixture
def consistent(repo):
    """A repo record and a server that agree: one file from each source, each differing from the record only in form."""
    repo.put(repo.overlay, "README.md", "the overlay\n")
    repo.put(repo.overlay, DH, DH_OVERLAY)
    repo.put(repo.overlay, "cobblemon/starters.json", '{"starters": ["bulbasaur", "charmander"], "enabled": true}')
    repo.put(repo.mirror, "README.md", "the mirror\n")
    repo.put(repo.mirror, "comforts-server.toml", "# sleeping bags\nsleepyTime = 12000\n")
    repo.put(repo.mirror, "iris.properties", "#Iris\nshaderPack=\nenableShaders=false\n")
    repo.put(repo.base, "betterf3.json", '{"a": 1, "b": [1, 2]}')
    repo.put(repo.base, "vanillabackport-common.toml", "[general]\nfoo = true\n")
    # the server: the same values in another form (CRLF, other comments, JSON reformatted, its own serverId)
    repo.put(repo.cfg, DH, DH_SERVER.replace("# Distant Horizons\n", "# rewritten by DH\n"), newline="\r\n")
    repo.put(repo.cfg, "cobblemon/starters.json", '{\n  "enabled": true,\n  "starters": ["bulbasaur","charmander"]\n}\n')
    repo.put(repo.cfg, "comforts-server.toml", "sleepyTime = 12000\n\n")
    repo.put(repo.cfg, "iris.properties", "#Iris Properties\n#Sat Sep 26 2026\nshaderPack=\nenableShaders=false\n",
             newline="\r\n")
    repo.put(repo.cfg, "betterf3.json", '{"b":[1,2],"a":1}')
    repo.put(repo.cfg, "vanillabackport-common.toml", "[general]\nfoo = true\n")
    # files the check leaves out: backups, images, unpack caches, notes
    repo.put(repo.cfg, "betterf3.json.bak", "anything")
    repo.put(repo.cfg, "fancymenu/icon.png", "not a config")
    repo.put(repo.cfg, "mod/.archive-unpack/x.toml", "a = 1\n")
    repo.put(repo.cfg, "notes.md", "server notes\n")
    return repo


def snapshot(folder: Path) -> dict:
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*") if p.is_file()}


# ------------------------------------------------------------------ comparable: meaning, not form

@pytest.mark.parametrize("rel, a, b", [
    ("x.toml", "a = 1\nb = 2\n", "a = 1\r\nb = 2\r\n"),
    ("x.toml", "# one comment\na = 1\n", "# another\n  # indented comment\na = 1\n"),
    ("x.properties", "#Sat Sep 26\nk=v\n", "k=v\n"),
    ("x.cfg", "# c\nk=v\n", "k=v   \n\n\n"),
    ("x.json", '{"a": 1, "b": {"c": [1, 2]}}', '{\r\n "b": {"c": [1,2]},\r\n "a": 1\r\n}\r\n'),
    ("x.txt", "k:v\n", "k:v\r\n\r\n"),
])
def test_form_only_differences_are_not_disagreements(rel, a, b):
    # without this, every CRLF checkout or mod that rewrites its own comments reports false drift, and drift reports
    # stop being read
    assert SCR.comparable(rel, a.encode()) == SCR.comparable(rel, b.encode())


@pytest.mark.parametrize("rel, a, b", [
    ("x.toml", "a = 1\n", "a = 2\n"),
    ("x.toml", "enableServerGeneration = false\n", "enableServerGeneration = true\n"),
    ("x.properties", "k=v\n", "k=w\n"),
    ("x.json", '{"a": 1}', '{"a": 2}'),
    ("x.json", '{"a": [1, 2]}', '{"a": [2, 1]}'),
    ("x.json", '{"a": 1}', '{"a": 1, "b": null}'),
    ("x.json5", "{a: 1 // c\n}", "{a: 1 // d\n}"),
    ("x.txt", "# k:v\n", "k:v\n"),
])
def test_a_difference_in_value_is_a_disagreement(rel, a, b):
    # without this, the 2026-09-26 case (enableServerGeneration flipped) and any changed value would compare equal
    assert SCR.comparable(rel, a.encode()) != SCR.comparable(rel, b.encode())


def test_server_id_is_ignored_only_in_distant_horizons():
    # without this, OWN_KEYS could widen to every file and hide a changed serverId-like value elsewhere
    assert SCR.comparable(DH, DH_OVERLAY.encode()) == SCR.comparable(DH, DH_SERVER.encode())
    assert SCR.comparable("other.toml", DH_OVERLAY.encode()) != SCR.comparable("other.toml", DH_SERVER.encode())


# ------------------------------------------------------------------ check

def test_a_server_that_matches_the_record_has_no_disagreements(consistent):
    # without this fixture the drift tests below could pass on a check that flags everything
    assert SCR.check(consistent.cfg) == []


@pytest.mark.parametrize("rel, text, source", [
    (DH, DH_SERVER.replace("enableServerGeneration = false", "enableServerGeneration = true"), "modpack/config/" + DH),
    ("cobblemon/starters.json", '{"starters": ["bulbasaur"], "enabled": true}', "modpack/config/cobblemon/starters.json"),
    ("comforts-server.toml", "sleepyTime = 0\n", "server/config/mods/comforts-server.toml"),
    ("iris.properties", "shaderPack=\nenableShaders=true\n", "server/config/mods/iris.properties"),
    ("betterf3.json", '{"a": 2, "b": [1, 2]}', "base-pack/cobbleverse/config/betterf3.json"),
])
def test_a_changed_value_on_the_server_is_reported_against_its_source(consistent, rel, text, source):
    # without this, a server value the repo does not hold (from the overlay, the mirror or the base pack) goes unseen
    consistent.put(consistent.cfg, rel, text)
    assert SCR.check(consistent.cfg) == ["%s: the server's copy differs from %s" % (rel, source)]


def test_the_overlay_outranks_the_base_pack(consistent):
    # without this, a server still running the upstream value of a file we override would pass the check
    consistent.put(consistent.base, "cobblemon/starters.json", '{"starters": ["pikachu"], "enabled": true}')
    consistent.put(consistent.cfg, "cobblemon/starters.json", '{"starters": ["pikachu"], "enabled": true}')
    assert SCR.check(consistent.cfg) == [
        "cobblemon/starters.json: the server's copy differs from modpack/config/cobblemon/starters.json"]


def test_a_config_the_repo_does_not_record_is_reported(consistent):
    # without this, a config added on the server by hand never reaches the repo
    consistent.put(consistent.cfg, "newmod.toml", "a = 1\n")
    assert SCR.check(consistent.cfg) == ["newmod.toml: runs on the server, recorded nowhere in the repo"]


@pytest.mark.parametrize("rel", ["cobblemon/starters.json", "comforts-server.toml"])
def test_a_recorded_config_missing_on_the_server_is_reported(consistent, rel):
    # without this, an overlay file that never reached the server (starters.json until 2026-09-26) passes silently
    (consistent.cfg / rel).unlink()
    assert SCR.check(consistent.cfg) == ["%s: recorded in the repo, absent on the server" % rel]


def test_every_disagreement_is_reported_not_only_the_first(consistent):
    # without this, fixing one drift would reveal the next only on the following run
    consistent.put(consistent.cfg, "comforts-server.toml", "sleepyTime = 1\n")
    consistent.put(consistent.cfg, "newmod.toml", "a = 1\n")
    (consistent.cfg / "iris.properties").unlink()
    assert len(SCR.check(consistent.cfg)) == 3


def test_check_cli_exits_nonzero_on_drift_and_zero_when_clean(consistent, capsys):
    # without this, tools/reapply.py and a human would see the report but a script would not stop
    assert SCR.main(["check", "--server-dir", str(consistent.server)]) == 0
    consistent.put(consistent.cfg, "comforts-server.toml", "sleepyTime = 1\n")
    assert SCR.main(["check", "--server-dir", str(consistent.server)]) == 1
    assert "DRIFT comforts-server.toml" in capsys.readouterr().out


def test_cli_refuses_a_server_without_a_config_folder(tmp_path, repo):
    # without this, a mistyped --server-dir reports "0 disagreements" over an empty tree
    with pytest.raises(SystemExit) as e:
        SCR.main(["check", "--server-dir", str(tmp_path / "nowhere")])
    assert e.value.code not in (0, None)


# ------------------------------------------------------------------ install

def test_install_puts_every_overlay_file_on_an_empty_server(repo):
    # without this, an overlay file never reaches a freshly assembled server (five files until 2026-09-26)
    repo.put(repo.overlay, "README.md", "x\n")
    repo.put(repo.overlay, DH, DH_OVERLAY)
    repo.put(repo.overlay, "cobblemon/starters.json", '{"starters": []}')
    assert SCR.install(repo.cfg) == 2
    assert snapshot(repo.cfg) == {DH: DH_OVERLAY.encode(), "cobblemon/starters.json": b'{"starters": []}'}


def test_install_keeps_the_servers_own_server_id(consistent):
    # without this, installing the overlay replaces the server's Distant Horizons serverId with the committed one
    consistent.put(consistent.overlay, DH, DH_OVERLAY.replace("5120", "4096"))
    assert SCR.install(consistent.cfg) == 1
    text = (consistent.cfg / DH).read_text(encoding="utf-8")
    assert "serverId = 918273645" in text and "serverId = 0" not in text
    assert "generationBoundsRadius = 4096" in text
    assert SCR.check(consistent.cfg) == []


@pytest.mark.xfail(strict=True, reason=(
    "tools/server_config_record.py:96-100: the server's serverId is kept only by substituting it into the overlay's "
    "own serverId line (pat.sub). When the overlay file has no serverId line and any other value differs, install "
    "writes the overlay verbatim and the server's serverId is lost. Latent: the committed overlay has the line "
    "(test_the_committed_distant_horizons_overlay_carries_the_server_owned_key)."))
def test_install_keeps_the_server_id_when_the_overlay_omits_the_key(consistent):
    # without this, deleting the serverId line from the overlay silently strips it from every server on install
    consistent.put(consistent.overlay, DH, DH_OVERLAY.replace("\tserverId = 0\n", "").replace("5120", "4096"))
    SCR.install(consistent.cfg)
    assert "serverId = 918273645" in (consistent.cfg / DH).read_text(encoding="utf-8")


def test_install_leaves_a_file_with_the_same_values_untouched(consistent):
    # without this, every install rewrites files a mod reformatted, churning CRLF and comments on the server
    before = snapshot(consistent.cfg)
    assert SCR.install(consistent.cfg) == 0
    assert snapshot(consistent.cfg) == before


def test_install_is_idempotent(consistent):
    # without this, a second install would rewrite files (or report installs) that the first already made current
    consistent.put(consistent.overlay, "cobblemon/starters.json", '{"starters": ["squirtle"], "enabled": true}')
    consistent.put(consistent.overlay, "rctmod-server.toml", "# ours\nmaxTrainersPerPlayer = 0\n")
    assert SCR.install(consistent.cfg) == 2
    after_first = snapshot(consistent.cfg)
    assert SCR.install(consistent.cfg) == 0
    assert snapshot(consistent.cfg) == after_first
    assert SCR.check(consistent.cfg) == []


def test_install_touches_only_overlay_files(consistent):
    # without this, install could overwrite or remove server values the repo records in the mirror or the base pack
    consistent.put(consistent.overlay, "cobblemon/starters.json", '{"starters": ["squirtle"], "enabled": true}')
    before = snapshot(consistent.cfg)
    SCR.install(consistent.cfg)
    after = snapshot(consistent.cfg)
    assert set(after) == set(before)
    changed = {k for k in before if before[k] != after[k]}
    assert changed == {"cobblemon/starters.json"}


def test_install_cli_runs_the_check_after_installing(consistent, capsys):
    # without this, `install` would report success over drift the overlay does not cover
    consistent.put(consistent.cfg, "comforts-server.toml", "sleepyTime = 1\n")
    assert SCR.main(["install", "--server-dir", str(consistent.server)]) == 1
    assert "DRIFT comforts-server.toml" in capsys.readouterr().out


# ------------------------------------------------------------------ record

def test_record_then_check_agrees(consistent):
    # without this, `record` could leave the repo in a state its own check rejects
    consistent.put(consistent.cfg, "newmod.toml", "a = 1\n")
    consistent.put(consistent.cfg, "comforts-server.toml", "sleepyTime = 1\n")
    assert SCR.check(consistent.cfg) != []
    SCR.record(consistent.cfg)
    assert SCR.check(consistent.cfg) == []


def test_record_mirrors_only_what_the_overlay_and_base_pack_do_not_already_hold(consistent):
    # without this, the mirror fills with copies of overlay and upstream files, backups and images
    consistent.put(consistent.cfg, "newmod.toml", "a = 1\n")
    consistent.put(consistent.cfg, "betterf3.json", '{"a": 1, "b": [1, 2]}')      # byte-identical to the base pack
    SCR.record(consistent.cfg)
    assert set(snapshot(consistent.mirror)) == {"README.md", "comforts-server.toml", "iris.properties", "newmod.toml",
                                                "notes.md"}


@pytest.mark.xfail(strict=True, reason=(
    "tools/server_config_record.py:122: record() compares the server file with the base pack byte for byte, while "
    "check() compares comparable() values. A server copy that differs from the base only in CRLF, comments or JSON "
    "layout is mirrored as if it differed. The committed mirror shows it: 38 of the 45 base-backed files in "
    "server/config/mods hold the base pack's values (34 byte-identical after git's eol=lf normalisation), "
    "contradicting server/config/mods/README.md ('each config that differs from the base pack')."))
def test_record_does_not_mirror_a_file_that_differs_from_the_base_pack_only_in_form(consistent):
    # without this, a CRLF server copy of an upstream config is recorded as a server-specific value
    consistent.put(consistent.cfg, "vanillabackport-common.toml", "[general]\nfoo = true\n", newline="\r\n")
    SCR.record(consistent.cfg)
    assert not (consistent.mirror / "vanillabackport-common.toml").exists()


def test_record_cannot_launder_overlay_drift(consistent):
    # without this, `record` would make a server value that contradicts the overlay look deliberate
    consistent.put(consistent.cfg, "cobblemon/starters.json", '{"starters": ["mew"], "enabled": true}')
    SCR.record(consistent.cfg)
    assert SCR.check(consistent.cfg) == [
        "cobblemon/starters.json: the server's copy differs from modpack/config/cobblemon/starters.json"]


def test_record_drops_stale_mirror_files_and_keeps_the_readme(consistent):
    # without this, a config removed from the server stays recorded and the check reports it absent forever
    consistent.put(consistent.mirror, "gone/old.toml", "a = 1\n")
    (consistent.cfg / "iris.properties").unlink()
    SCR.record(consistent.cfg)
    assert (consistent.mirror / "README.md").read_text(encoding="utf-8") == "the mirror\n"
    assert not (consistent.mirror / "gone").exists()
    assert not (consistent.mirror / "iris.properties").exists()
    assert SCR.check(consistent.cfg) == []


# ------------------------------------------------------------------ the committed record

MIRROR_REAL = ROOT / "server" / "config" / "mods"
OVERLAY_REAL = ROOT / "modpack" / "config"


def test_every_mirrored_config_is_one_the_check_consults():
    # without this, a mirror file shadowed by the overlay, or matching SKIP, is a dead record that looks authoritative
    overlay = {p.relative_to(OVERLAY_REAL).as_posix() for p in OVERLAY_REAL.rglob("*") if p.is_file()}
    mirror = [p.relative_to(MIRROR_REAL).as_posix() for p in MIRROR_REAL.rglob("*") if p.is_file()]
    assert len(mirror) > 1, "server/config/mods is empty"
    dead = [r for r in mirror if r != "README.md" and (r in overlay or SCR.SKIP.search("/" + r) or r.endswith(".md"))]
    assert dead == []


@pytest.mark.xfail(strict=True, reason=(
    "server/config/mods holds 38 files whose values equal base-pack/cobbleverse/config (e.g. advancementdisable.toml, "
    "betterf3.json, iris.properties, xaerohud.txt; modernfix-mixins.properties, packetfixer.properties, "
    "scalablelux.properties and zfastnoise.mixin.properties differ only in comment lines). Cause: the record() byte "
    "comparison at tools/server_config_record.py:122 (see the xfail above). Content defect, not fixed here."))
def test_no_mirrored_config_repeats_the_base_pack_values():
    # without this, the mirror stops meaning "what the server changed" and a real server-side value is hard to find
    base = ROOT / "base-pack" / "cobbleverse" / "config"
    same = sorted(p.relative_to(MIRROR_REAL).as_posix() for p in MIRROR_REAL.rglob("*") if p.is_file()
                  and (base / p.relative_to(MIRROR_REAL)).is_file()
                  and SCR.comparable(p.relative_to(MIRROR_REAL).as_posix(), p.read_bytes())
                  == SCR.comparable(p.relative_to(MIRROR_REAL).as_posix(),
                                    (base / p.relative_to(MIRROR_REAL)).read_bytes()))
    assert same == []


def test_the_committed_distant_horizons_overlay_carries_the_server_owned_key():
    # without this, install can no longer keep a server's serverId (see the xfail above) and nothing says so
    text = (OVERLAY_REAL / DH).read_text(encoding="utf-8")
    assert len(SCR.OWN_KEYS[DH].findall(text)) == 1


def test_the_committed_overlay_keeps_distant_horizons_server_generation_off():
    # without this, the overlay can again re-enable DH generation, which ignores the world border (tool docstring,
    # 2026-09-26)
    text = (OVERLAY_REAL / DH).read_text(encoding="utf-8")
    values = re.findall(r"^\s*enableServerGeneration\s*=\s*(\S+)", text, re.M)
    assert values == ["false"]

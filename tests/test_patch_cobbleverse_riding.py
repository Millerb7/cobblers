import json
from pathlib import Path
import sys
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from patch_cobbleverse_riding import patch_pack


def _write_zip(path: Path, entries: dict[str, object]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, value in entries.items():
            payload = value if isinstance(value, bytes) else json.dumps(value).encode()
            archive.writestr(name, payload)


def test_migrates_seats_and_preserves_custom_stats(tmp_path: Path) -> None:
    source = tmp_path / "source.zip"
    output = tmp_path / "output.zip"
    cobblemon = tmp_path / "cobblemon.jar"
    _write_zip(
        source,
        {
            "pack.mcmeta": {"pack": {"pack_format": 48, "description": "test"}},
            "data/cobblemon/species_additions/charizard.json": {
                "target": "cobblemon:charizard",
                "riding": {
                    "behaviours": {"AIR": {"stats": {"SPEED": "95-115"}}},
                    "seats": [{"offset": {"x": 0}, "poseOffsets": []}],
                },
            },
        },
    )
    _write_zip(
        cobblemon,
        {
            "data/cobblemon/species/generation1/charizard.json": {
                "name": "cobblemon:charizard",
                "riding": {"seats": [{"locator": "seat_1"}]},
            }
        },
    )

    assert patch_pack(source, output, cobblemon) == (1, 1)
    with zipfile.ZipFile(output) as archive:
        result = json.loads(
            archive.read("data/cobblemon/species_additions/charizard.json")
        )
        assert result["riding"]["seats"] == [{"locator": "seat_1"}]
        assert result["riding"]["behaviours"]["AIR"]["stats"]["SPEED"] == "95-115"
        assert json.loads(archive.read("pack.mcmeta"))["pack"]["description"] == "test"


def test_uses_cobblemon_seat_count_when_it_changed(tmp_path: Path) -> None:
    source = tmp_path / "source.zip"
    output = tmp_path / "output.zip"
    cobblemon = tmp_path / "cobblemon.jar"
    _write_zip(
        source,
        {
            "data/cobblemon/species_additions/test.json": {
                "target": "cobblemon:test",
                "riding": {"seats": [{"offset": {}}, {"offset": {}}]},
            }
        },
    )
    _write_zip(
        cobblemon,
        {
            "data/cobblemon/species/generation1/test.json": {
                "name": "cobblemon:test",
                "riding": {"seats": [{"locator": "seat_1"}]},
            }
        },
    )

    assert patch_pack(source, output, cobblemon) == (1, 1)
    with zipfile.ZipFile(output) as archive:
        result = json.loads(archive.read("data/cobblemon/species_additions/test.json"))
        assert result["riding"]["seats"] == [{"locator": "seat_1"}]


def test_preserves_cobbleverse_only_mount_offsets(tmp_path: Path) -> None:
    source = tmp_path / "source.zip"
    output = tmp_path / "output.zip"
    cobblemon = tmp_path / "cobblemon.jar"
    original_seat = {"offset": {"x": 1, "y": 2, "z": 3}, "poseOffsets": []}
    _write_zip(
        source,
        {
            "data/cobblemon/species_additions/alakazam.json": {
                "target": "cobblemon:alakazam",
                "riding": {"seats": [original_seat]},
            }
        },
    )
    _write_zip(
        cobblemon,
        {
            "data/cobblemon/species/generation1/alakazam.json": {
                "name": "Alakazam",
                "riding": {"seats": []},
            }
        },
    )

    assert patch_pack(source, output, cobblemon) == (0, 0)
    with zipfile.ZipFile(output) as archive:
        result = json.loads(
            archive.read("data/cobblemon/species_additions/alakazam.json")
        )
        assert result["riding"]["seats"] == [original_seat]


def test_expected_count_rejects_partial_pack_without_replacing_output(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.zip"
    output = tmp_path / "output.zip"
    cobblemon = tmp_path / "cobblemon.jar"
    output.write_bytes(b"existing runtime pack")
    _write_zip(
        source,
        {
            "data/cobblemon/species_additions/charizard.json": {
                "target": "cobblemon:charizard",
                "riding": {"seats": [{"offset": {}}]},
            }
        },
    )
    _write_zip(
        cobblemon,
        {
            "data/cobblemon/species/generation1/charizard.json": {
                "name": "Charizard",
                "riding": {"seats": [{"locator": "seat_1"}]},
            }
        },
    )

    with pytest.raises(ValueError, match="expected 51.*found 1"):
        patch_pack(source, output, cobblemon, expected_count=51)
    assert output.read_bytes() == b"existing runtime pack"

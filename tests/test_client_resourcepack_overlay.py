import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BROKEN_PACK = "file/ATMxMSD RP.zip"


def test_atmxmsd_is_not_enabled_by_default():
    config = ROOT / "modpack/config"
    overrides = json.loads((config / "resourcepackoverrides.json").read_text(encoding="utf-8-sig"))
    assert BROKEN_PACK not in overrides["default_packs"]
    assert BROKEN_PACK not in (config / "defaultoptions-common.toml").read_text(encoding="utf-8-sig")
    assert BROKEN_PACK not in (config / "defaultoptions/options.txt").read_text(encoding="utf-8-sig")


def test_atmxmsd_metadata_is_retained_for_manual_retest():
    overrides = json.loads(
        (ROOT / "modpack/config/resourcepackoverrides.json").read_text(encoding="utf-8-sig")
    )
    assert BROKEN_PACK in overrides["pack_overrides"]

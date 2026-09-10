import gzip
import hashlib
import io
import json
import re
import struct
import subprocess
from pathlib import Path


TEMPLATE_ID = "cobblers:f4/pallet_house_large2"
FUNCTION_ID = "cobblers:exp_001/f4_relic_island/place"
CAMPAIGN_ID = "campaign:f4/pallet_house_large2"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_nbt(path: Path) -> dict:
    raw = path.read_bytes()
    try:
        raw = gzip.decompress(raw)
    except OSError:
        pass
    stream = io.BytesIO(raw)

    def unpack(fmt: str):
        size = struct.calcsize(">" + fmt)
        return struct.unpack(">" + fmt, stream.read(size))[0]

    def read_string() -> str:
        return stream.read(unpack("H")).decode("utf-8")

    def read_payload(tag: int):
        if tag == 1:
            return unpack("b")
        if tag == 2:
            return unpack("h")
        if tag == 3:
            return unpack("i")
        if tag == 4:
            return unpack("q")
        if tag == 5:
            return unpack("f")
        if tag == 6:
            return unpack("d")
        if tag == 7:
            return stream.read(unpack("i"))
        if tag == 8:
            return read_string()
        if tag == 9:
            child_tag, length = unpack("b"), unpack("i")
            if child_tag == 0 and length == 0:
                return []
            return [read_payload(child_tag) for _ in range(length)]
        if tag == 10:
            value = {}
            while True:
                child_tag = unpack("b")
                if child_tag == 0:
                    return value
                key = read_string()
                value[key] = read_payload(child_tag)
        if tag == 11:
            return [unpack("i") for _ in range(unpack("i"))]
        if tag == 12:
            return [unpack("q") for _ in range(unpack("i"))]
        raise ValueError(f"unsupported NBT tag {tag}")

    assert unpack("b") == 10, "structure NBT root must be a compound"
    read_string()
    return read_payload(10)


def _run_generator(repo_root: Path, python: str, output: Path) -> dict[str, Path]:
    paths = {
        "function": output / "place.mcfunction",
        "preview": output / "preview.svg",
        "template": output / "pallet_house_large2.nbt",
    }
    subprocess.run(
        [
            python,
            "tools/generate_f4_relic_island.py",
            "--function",
            str(paths["function"]),
            "--preview",
            str(paths["preview"]),
            "--template-output",
            str(paths["template"]),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return paths


def test_generation_is_deterministic(repo_root, python, tmp_path):
    first = _run_generator(repo_root, python, tmp_path / "first")
    second = _run_generator(repo_root, python, tmp_path / "second")

    for artifact in first:
        assert first[artifact].read_bytes() == second[artifact].read_bytes(), artifact


def test_canonical_and_generated_nbt_match_manifest(repo_root):
    canonical = repo_root / "world/structures/campaign/f4/pallet_house_large2.nbt"
    generated = repo_root / (
        "modpack/datapacks/cobblers_campaign/data/cobblers/structure/"
        "f4/pallet_house_large2.nbt"
    )
    donors = json.loads(
        (repo_root / "world/structures/manifests/pokemon-town-donors.json").read_text(
            encoding="utf-8"
        )
    )
    city_towns = next(
        source for source in donors["sources"] if source["source_pack"] == "CobblemonCityTowns"
    )
    donor = next(
        template for template in city_towns["templates"] if template.get("campaign_id") == TEMPLATE_ID
    )

    assert canonical.read_bytes() == generated.read_bytes()
    assert _sha256(canonical) == donor["nbt_sha256"]
    assert _sha256(generated) == donor["nbt_sha256"]


def test_event_template_and_function_ids_are_consistent(repo_root):
    event = json.loads(
        (repo_root / "world/source/events/f4-relic-island.json").read_text(encoding="utf-8")
    )
    donors = json.loads(
        (repo_root / "world/structures/manifests/pokemon-town-donors.json").read_text(
            encoding="utf-8"
        )
    )
    dependencies = json.loads(
        (repo_root / "world/structures/manifests/structure-dependencies.json").read_text(
            encoding="utf-8"
        )
    )
    function_path = repo_root / (
        "modpack/datapacks/cobblers_campaign/data/cobblers/function/"
        "exp_001/f4_relic_island/place.mcfunction"
    )
    function_text = function_path.read_text(encoding="utf-8")
    placed_templates = re.findall(r"^place template (\S+)", function_text, flags=re.MULTILINE)
    donor_ids = {
        template["campaign_id"]
        for source in donors["sources"]
        for template in source["templates"]
        if "campaign_id" in template
    }
    dependency = next(
        entry
        for entry in dependencies["campaign_structures"]
        if entry["id"] == CAMPAIGN_ID
    )

    assert event["structure"]["template"] == TEMPLATE_ID
    assert event["structure"]["function"] == FUNCTION_ID
    assert event["placement"]["command"].endswith(f"function {FUNCTION_ID}")
    assert placed_templates == [TEMPLATE_ID]
    assert TEMPLATE_ID in donor_ids
    assert dependency["id"] == CAMPAIGN_ID
    assert dependency["structure_id"] == TEMPLATE_ID


def test_donor_nbt_shape_and_contents(repo_root):
    root = _read_nbt(repo_root / "world/structures/campaign/f4/pallet_house_large2.nbt")
    palette = root["palette"]
    blocks = root["blocks"]
    namespaces = {state["Name"].split(":", 1)[0] for state in palette}
    jigsaws = [
        block
        for block in blocks
        if palette[block["state"]]["Name"] == "minecraft:jigsaw"
    ]
    source_chests = [
        block
        for block in blocks
        if block.get("nbt", {}).get("id") == "minecraft:chest"
    ]

    assert root["size"] == [12, 9, 10]
    assert namespaces == {"minecraft"}
    assert len(jigsaws) == 3
    assert len(source_chests) == 1
    assert source_chests[0]["pos"] == [5, 1, 7]

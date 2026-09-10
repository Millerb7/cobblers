"""Migrate COBBLEVERSE 1.7 riding seats for a Cobblemon 1.8 runtime.

The upstream COBBLEVERSE datapack is not committed to this repository.  This
tool reads the user's local copy and writes a patched runtime copy while
preserving all other files and the pack's custom riding statistics.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import tempfile
import zipfile


SPECIES_ADDITION_PREFIX = "data/cobblemon/species_additions/"
SPECIES_PREFIX = "data/cobblemon/species/"


def _json_entry(archive: zipfile.ZipFile, name: str) -> dict:
    return json.loads(archive.read(name).decode("utf-8-sig"))


def _base_seats(cobblemon_jar: Path) -> dict[str, list[dict]]:
    seats: dict[str, list[dict]] = {}
    with zipfile.ZipFile(cobblemon_jar) as archive:
        for info in archive.infolist():
            if not (
                info.filename.startswith(SPECIES_PREFIX)
                and info.filename.endswith(".json")
            ):
                continue
            species = _json_entry(archive, info.filename)
            name = species.get("name")
            riding = species.get("riding")
            if name and isinstance(riding, dict) and isinstance(riding.get("seats"), list):
                seats[_species_key(name)] = riding["seats"]
    return seats


def _species_key(value: str) -> str:
    """Match display names and resource IDs (Mr. Mime/mrmime, Ho-Oh/hooh)."""
    return re.sub(r"[^a-z0-9]", "", value.rsplit(":", 1)[-1].lower())


def patch_pack(
    source: Path,
    output: Path,
    cobblemon_jar: Path,
    expected_count: int | None = None,
) -> tuple[int, int]:
    base_seats = _base_seats(cobblemon_jar)
    patched = 0
    verified = 0

    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)

    try:
        with zipfile.ZipFile(source) as source_zip, zipfile.ZipFile(
            temporary, "w"
        ) as output_zip:
            for info in source_zip.infolist():
                payload = source_zip.read(info.filename)
                if (
                    info.filename.startswith(SPECIES_ADDITION_PREFIX)
                    and info.filename.endswith(".json")
                ):
                    addition = json.loads(payload.decode("utf-8-sig"))
                    riding = addition.get("riding")
                    old_seats = riding.get("seats") if isinstance(riding, dict) else None
                    if isinstance(old_seats, list) and old_seats:
                        target = addition.get("target", "")
                        expected = base_seats.get(_species_key(target))
                        if expected:
                            expected_locators = [seat.get("locator") for seat in expected]
                            wanted_locators = [
                                f"seat_{index}" for index in range(1, len(expected) + 1)
                            ]
                            if expected_locators != wanted_locators:
                                raise ValueError(
                                    f"{target}: Cobblemon 1.8 defines unexpected seat "
                                    f"locators {expected_locators}"
                                )
                            verified += 1
                            riding["seats"] = [
                                {"locator": f"seat_{index}"}
                                for index in range(1, len(expected) + 1)
                            ]
                            payload = (
                                json.dumps(addition, indent=2, ensure_ascii=False) + "\n"
                            ).encode("utf-8")
                            patched += 1

                output_zip.writestr(info, payload)

        if expected_count is not None and patched != expected_count:
            raise ValueError(
                f"expected {expected_count} riding definitions, found {patched}"
            )

        os.replace(temporary, output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    return patched, verified


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Patch a local COBBLEVERSE 1.7 datapack for Cobblemon 1.8 riding."
    )
    parser.add_argument("source", type=Path, help="Original COBBLEVERSE-DP ZIP")
    parser.add_argument("output", type=Path, help="Patched runtime ZIP")
    parser.add_argument(
        "--cobblemon-jar",
        required=True,
        type=Path,
        help="Cobblemon 1.8 JAR used to verify seat counts and locator names",
    )
    parser.add_argument(
        "--expect-patched",
        type=int,
        help="Fail without replacing the output unless exactly this many definitions migrate",
    )
    args = parser.parse_args()

    for path, label in (
        (args.source, "source datapack"),
        (args.cobblemon_jar, "Cobblemon JAR"),
    ):
        if not path.is_file():
            parser.error(f"{label} does not exist: {path}")

    try:
        patched, verified = patch_pack(
            args.source,
            args.output,
            args.cobblemon_jar,
            expected_count=args.expect_patched,
        )
    except ValueError as error:
        parser.error(str(error))
    if patched == 0:
        parser.error("no riding species additions were found")
    print(f"Patched {patched} riding definitions ({verified} verified against Cobblemon 1.8).")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

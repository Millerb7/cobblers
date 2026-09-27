"""data/water_mounts.json: the Surf and Dive rider lists the water ladder reads (tools/blackout_pack.py).

Written by the test author, not by the session that authored the lists (EXP-038) or the pack.

Independent source: the Cobblemon 1.8.0 jar's species files (data/cobblemon/species/<generation>/<id>.json, the EXP-000
runtime copy found through tools/battle_sim.JAR_CANDIDATES). Without the jar the species-id test SKIPS; a skip is not a
pass, and the format checks still run.

Not covered: whether each species can actually carry a rider on or under water in game (EXP-038 read the riding data
from the jars; in-game riding is not checked), and whether a species added by a datapack is missing from the lists.
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

MOUNTS = json.loads((ROOT / "data" / "water_mounts.json").read_text(encoding="utf-8"))
ID = re.compile(r"[a-z][a-z0-9_]*")


# Without it a species in both lists is read as Dive by the party callback and Surf by the reader of the data (the two
# disagree about what the Pokemon gives), or a list is lost and the ladder has no riders at all.
def test_surf_and_dive_lists_are_disjoint_non_empty_and_without_repeats():
    surf, dive = MOUNTS["surf"], MOUNTS["dive"]
    assert len(surf) >= 10 and len(dive) >= 3, (len(surf), len(dive))
    assert len(surf) == len(set(surf)) and len(dive) == len(set(dive))
    assert not set(surf) & set(dive), sorted(set(surf) & set(dive))


# Without it a display name ("Mr. Mime", "Farfetch'd") or a capitalised name reaches the MoLang comparison
# t.id == 'cobblemon:<name>' and never matches, so that species gives no water support.
def test_every_species_is_a_lowercase_bare_id():
    bad = [s for s in MOUNTS["surf"] + MOUNTS["dive"] if not ID.fullmatch(s)]
    assert not bad, bad


@pytest.fixture(scope="module")
def jar_species():
    import battle_sim
    jar = next((c for c in battle_sim.JAR_CANDIDATES if c.is_file()), None)
    if jar is None:
        pytest.skip("no Cobblemon-fabric-1.8.0 jar outside the live server (EXP-000 runtime copy)")
    with zipfile.ZipFile(jar) as z:
        names = {n.rsplit("/", 1)[1][:-len(".json")] for n in z.namelist()
                 if n.startswith("data/cobblemon/species/") and n.endswith(".json")}
    assert len(names) > 1000, len(names)
    return names


# Without it a misspelt or non-existent species (a form name, a species another mod adds under its own namespace) sits
# in the list and silently never matches a party member.
def test_every_species_is_a_cobblemon_species_id(jar_species):
    missing = [s for s in MOUNTS["surf"] + MOUNTS["dive"] if s not in jar_species]
    assert not missing, missing

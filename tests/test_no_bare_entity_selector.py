"""A `execute if entity` / `unless entity` takes a full selector (@e[...]). A bare argument body there fails to parse
and the whole function is dropped at load: 2026-10-09, the Undertow's summon_look passed chunk_look a body where it
takes a selector, and only the server's boot log showed it. This reads every generator's source for that shape.
(Written by the main session that found it, not by a test author.)"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BARE = re.compile(r"(?:if|unless) entity type=")


def test_no_tool_emits_a_bare_selector_after_if_entity():
    hits = []
    for p in sorted((ROOT / "tools").glob("*.py")):
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if BARE.search(line):
                hits.append("%s:%d" % (p.name, n))
    assert hits == [], hits


def test_buried_dune_hands_chunk_look_full_selectors():
    # Breaks if removed: the Undertow's look would again fail to load and its summon chain never run
    src = (ROOT / "tools" / "buried_dune.py").read_text(encoding="utf-8")
    assert '["@e[type=cobblemon:pokemon,tag=%s]" % rtag], act' in src

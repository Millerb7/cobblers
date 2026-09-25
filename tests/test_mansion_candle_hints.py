"""The Gastly mansion's candle hints: the library narration (data/dialogue.json node p_library) and Channeler Jody's
after-win line (data/mansion_guardians.json mansion_guardian_4 after_win) both point at the candles, and each reaches
the pack a player sees it through.

Written by the test author, not by the session that wrote the lines.

What is asserted: both texts mention the candles; p_library's conversation is compiled by `compile_dialogue --all` (the
CLI, into a temporary directory) and its compiled dialogue carries the candle line; Jody's after-win line is the
tellraw in her won function (tools/route_trainers.files); and `--all` still refuses exactly the two pre-existing
crushed-house conversations, so adding the hint did not stop another conversation shipping.

Not covered, and it needs a running server: that the page renders, that Jody's tellraw fires once on a win
(rctmod:defeat_count), and that a player reads the hint as meaning the lamp order (a playtest).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import compile_dialogue as CD  # noqa: E402
import route_trainers as RT  # noqa: E402

DIALOGUE = json.loads((ROOT / "data" / "dialogue.json").read_text(encoding="utf-8"))
GUARDIANS = json.loads((ROOT / "data" / "mansion_guardians.json").read_text(encoding="utf-8"))["trainers"]
CANDLE = re.compile(r"\bcandles?\b", re.I)


def _library():
    for c in DIALOGUE["conversations"]:
        for n in c.get("nodes") or []:
            if n.get("id") == "p_library":
                return c, n
    pytest.fail("no node p_library in data/dialogue.json")


JODY = next(t for t in GUARDIANS if t["id"] == "mansion_guardian_4")


# Without it the library narration loses the hint and a player at the stair has no way to learn the candles matter.
def test_the_library_narration_mentions_the_candles():
    _c, node = _library()
    assert CANDLE.search(node["text"]), node["text"]


# Without it the guardian who gates the candle puzzle says nothing about it after she is beaten.
def test_jodys_after_win_line_mentions_the_candles():
    assert CANDLE.search(JODY["after_win"]), JODY["after_win"]


@pytest.fixture(scope="module")
def all_pack(tmp_path_factory):
    out = tmp_path_factory.mktemp("dialogue")
    assert CD.main(["--all", "--out", str(out)]) == 0
    return out


# Without it the hint is in the data but the conversation holding it is refused or dropped, and the page never shows.
def test_the_library_hint_reaches_the_compiled_dialogue(all_pack):
    conv, _node = _library()
    f = all_pack / "data" / "cobblers" / "dialogues" / ("%s.json" % conv["id"])
    assert f.is_file(), "compile_dialogue --all did not write %s" % f.name
    assert CANDLE.search(f.read_text(encoding="utf-8"))


# Without it a new refusal (a conversation that silently stops shipping, this one included) passes unnoticed.
def test_compile_all_refuses_only_the_two_crushed_house_conversations():
    _files, done, refused = CD.build_all(ROOT / "data")
    assert set(refused) == {"dlg_pallet_crushed_house_hank", "dlg_pallet_crushed_house_lena"}
    assert _library()[0]["id"] in done


# Without it Jody's line is in the data but her won function never shows it.
def test_jodys_after_win_line_is_told_when_she_is_beaten():
    files = RT.files()
    fn = files.get("data/cobblers/function/trainers/won/%s.mcfunction" % JODY["id"])
    assert fn, "no won function for %s" % JODY["id"]
    tell = [l for l in fn if l.startswith("tellraw @s ")]
    assert len(tell) == 1 and json.dumps(JODY["after_win"]) in tell[0], tell

"""Route signposts face the traveller and fit their text on a sign (tools/signposts.py). A post turned the wrong way
shows its blank back to the road; a line over 15 characters runs off the sign. And every route in data/routes.json
has a label, so no post reads as a raw id."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import signposts as S  # noqa: E402


def test_the_front_faces_the_way_it_is_asked_to():
    assert S.rotation(0, 1) == 0          # faces south
    assert S.rotation(-1, 0) == 4         # faces west
    assert S.rotation(0, -1) == 8         # faces north
    assert S.rotation(1, 0) == 12         # faces east


def test_text_wraps_at_word_boundaries_into_four_lines_of_fifteen():
    out = S.lines("Route 1", "River of Shrews Vale", "to Brock's town")
    assert len(out) == 4 and all(len(l) <= 15 for l in out)
    assert out[:3] == ["Route 1", "River of Shrews", "Vale"]


def test_every_route_has_a_label():
    labels = json.loads((ROOT / "data" / "signposts.json").read_text(encoding="utf-8"))["route_labels"]
    for r in json.loads((ROOT / "data" / "routes.json").read_text(encoding="utf-8"))["routes"]:
        assert r["id"] in labels, r["id"]

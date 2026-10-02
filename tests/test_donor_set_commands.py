"""`tools/place_donor.py` `command_rewrites()` and the `set_commands` the two Necrozma tower records carry.

Written by a test author who wrote neither (commit dfad147 added both).

WHAT BREAKS WITHOUT IT. The Dawn and Dusk towers ship a summit chain that spawns a level-80 Necrozma for whoever
steps on the plate and then fills itself in: one spawn, for the whole server. The records rewrite each link after
the paste so it fires only for a holder of `cobblers:flag/champion_cleared`. Three things can quietly undo that,
and each is tested here:

  the position   a rewrite aimed one block off lands on air or on the wrong link, and the ungated original
                 survives untouched. The template offset is turned with the paste; get the turn wrong and every
                 rotation but `none` rewrites the wrong blocks.
  the escaping   the tellraw link carries JSON with double quotes. Unescaped, the SNBT string ends early and the
                 whole `data merge` is a parse error, so the link keeps its shipped command.
  the order      a rewrite emitted before `place template`, or missing from a re-place, is overwritten by the
                 paste: the "_again" function re-pastes the template when the check block is missing.

THE INDEPENDENT SIDES. Expected positions are worked BY HAND below from Minecraft's own rotation about the
placement corner (StructureTemplate.transform with a zero pivot: clockwise_90 sends (x, z) to (-z, x)) -- a
relayed fact, from the game's source as the test author knows it, not measured here -- and cross-checked against
`place_donor.box()`, a separate function in the same tool that computes the rotated footprint without
`place_town.rotate`. The data contract reads data/placements.json only.

ON PROVING THESE BITE. Per CLAUDE.md "Mutate the GENERATOR, not the record": the mutation tests at the bottom
monkeypatch the code under test (`place_town.rotate` as `command_rewrites` sees it, and `place_donor.json`) and
leave every record alone, and assert the checks go red.

NOT COVERED. Validity is not behaviour (`.claude/rules/testing.md`):
  * that a command block exists at any `at` offset. No `.nbt` is read (no-redistribution pack); the offsets are
    taken from docs/research/notes/legendary-catalogue-reopened.md as relayed, and if they are wrong every
    rewrite here lands on air and these tests still pass.
  * that Minecraft 1.21.1 accepts the `data merge block` line, that `advancements={...}` in the selector
    resolves, that `pokespawnat` takes these arguments, or that `enable-command-block` is on (the record says
    the live server has it off). All of that is a staging experiment.
  * mirrors: `command_rewrites` refuses them, and that refusal is what is tested.
"""
from __future__ import annotations

import copy
import json
import re
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import place_donor  # noqa: E402
import place_town  # noqa: E402

PLACEMENTS = json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))["placements"]
TOWERS = ("legendary_dawn_tower", "legendary_dusk_tower")
FLAG = "cobblers:flag/champion_cleared"
ROTATIONS = ("none", "clockwise_90", "180", "counterclockwise_90")

LINE = re.compile(r"^data merge block (-?\d+) (-?\d+) (-?\d+) \{Command:(.*)\}$")

# The captured original, so a test that monkeypatches the module attribute can still say what the real one gives.
REAL_ROTATE = place_town.rotate


def synthetic(rotation="none", mirror="none", commands=None):
    """A minimal donor record: position (100, 64, 200), a 46 x 90 x 45 template, one or more set_commands."""
    return {"id": "synthetic", "pack_template": "cobbleverse:dawn_tower", "template": "cobbleverse:dawn_tower",
            "position": {"x": 100, "y": 64, "z": 200}, "size": [46, 90, 45], "rotation": rotation, "mirror": mirror,
            "set_commands": commands if commands is not None else [{"at": [16, 77, 22], "command": "say hi"}]}


def parse(line):
    """(x, y, z, command) from one emitted line; the command decoded from its SNBT string."""
    m = LINE.match(line)
    assert m, "not a data merge block line: %r" % line
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), json.loads(m.group(4))


# Worked by hand, NOT from place_town.rotate: offset (16, 77, 22) at position (100, 64, 200).
#   none                 (+16, +22)  -> (116, 141, 222)
#   clockwise_90         (-22, +16)  -> ( 78, 141, 216)
#   180                  (-16, -22)  -> ( 84, 141, 178)
#   counterclockwise_90  (+22, -16)  -> (122, 141, 184)
BY_HAND = {"none": (116, 141, 222), "clockwise_90": (78, 141, 216),
           "180": (84, 141, 178), "counterclockwise_90": (122, 141, 184)}


def position_problems():
    """[problem] where command_rewrites' position disagrees with the hand-worked one or with place_donor.box()."""
    bad = []
    for rot in ROTATIONS:
        (x, y, z, _), = [parse(l) for l in place_donor.command_rewrites(synthetic(rot))]
        if (x, y, z) != BY_HAND[rot]:
            bad.append("%s: emitted (%d, %d, %d), worked by hand %s" % (rot, x, y, z, BY_HAND[rot]))
        rx, rz = REAL_ROTATE(16, 22, rot)
        if (x, z) != (100 + rx, 200 + rz):
            bad.append("%s: emitted (%d, %d), place_town.rotate says (%d, %d)" % (rot, x, z, 100 + rx, 200 + rz))
        # Every template corner's rewrite must land inside the footprint box() computes for the same rotation.
        lo, hi = place_donor.box(synthetic(rot))
        corners = [{"at": [a, b, c], "command": "say"} for a in (0, 45) for b in (0, 89) for c in (0, 44)]
        for cx, cy, cz, _ in (parse(l) for l in place_donor.command_rewrites(synthetic(rot, commands=corners))):
            if not (lo[0] <= cx <= hi[0] and lo[1] <= cy <= hi[1] and lo[2] <= cz <= hi[2]):
                bad.append("%s: a template corner rewrites (%d, %d, %d), outside box() %s..%s"
                           % (rot, cx, cy, cz, lo, hi))
    return bad


AWKWARD = 'tellraw @a {"text":"say \\"hi\\" \\\\ back","color":"gray"} é'


def snbt_problems(line, want):
    """[problem] unless `line`'s Command value is one double-quoted string that decodes to `want` and uses no
    escape but \\" and \\\\ -- the only two Brigadier's StringReader (which 1.21.1's SNBT reader uses for quoted
    strings) accepts; a \\n or \\u would be an "Invalid escape sequence". Relayed from the game's source, not
    measured here."""
    m = LINE.match(line)
    if not m:
        return ["not a data merge block line: %r" % line]
    raw = m.group(4)
    bad = []
    if not (raw.startswith('"') and raw.endswith('"')):
        bad.append("the Command value is not one double-quoted string: %r" % raw)
    try:
        got = json.loads(raw)
    except json.JSONDecodeError as e:
        return bad + ["the Command value does not parse back as one string (%s): %r" % (e, raw)]
    if got != want:
        bad.append("round trip gave %r, not %r" % (got, want))
    escapes = {e.group(1) for e in re.finditer(r"\\(.)", raw[1:-1])}
    if escapes - {'"', "\\"}:
        bad.append("escapes %s are not ones the 1.21.1 SNBT reader accepts" % sorted(escapes - {'"', "\\"}))
    return bad


def escaping_problems():
    """[problem] unless an awkward command (quotes, a backslash, a non-ASCII letter) survives the SNBT string."""
    line, = place_donor.command_rewrites(synthetic(commands=[{"at": [0, 0, 0], "command": AWKWARD}]))
    return snbt_problems(line, AWKWARD)


def gate_problems(rec):
    """[problem] unless every spawn/fill/effect/sound link runs on `execute if entity`, and the one link that
    runs on `unless` is the refusal message."""
    bad = []
    for c in rec["set_commands"]:
        cmd = c["command"]
        if re.search(r"\b(pokespawnat|fill|effect|playsound)\b", cmd):
            if not cmd.startswith("execute if entity ") or " unless " in cmd:
                bad.append("a spawn/fill/effect/sound link is not `execute if entity`: %r" % cmd)
        elif not (cmd.startswith("execute unless entity ") and " run tellraw " in cmd):
            bad.append("the only link allowed to run on `unless` is the refusal tellraw: %r" % cmd)
    return bad


# ------------------------------------------------------------------------------------------- the generator


def test_rewrite_position_turns_with_the_paste_for_every_rotation():
    # Without it a rotated tower's rewrites land on the wrong blocks and the ungated chain survives as shipped.
    assert position_problems() == []


def test_rewrite_y_is_the_records_y_plus_the_offset_whatever_the_rotation():
    # Without it a rotation could disturb y, which /place template never turns.
    for rot in ROTATIONS:
        (_, y, _, _), = [parse(l) for l in place_donor.command_rewrites(synthetic(rot))]
        assert y == 64 + 77


def test_a_command_with_quotes_and_backslashes_survives_the_snbt_string():
    # Without it the tellraw link's JSON closes the SNBT string early and the whole data merge fails to parse.
    assert escaping_problems() == []


def test_mirror_with_set_commands_is_refused():
    # Without it a mirrored paste's rewrites would be aimed with an unmirrored offset, at the wrong blocks.
    for mirror in ("left_right", "front_back"):
        with pytest.raises(SystemExit):
            place_donor.command_rewrites(synthetic(mirror=mirror))


def test_mirror_without_set_commands_is_not_refused():
    # Without it the refusal could widen to every mirrored donor, which have nothing to rewrite.
    rec = synthetic(mirror="front_back")
    del rec["set_commands"]
    assert place_donor.command_rewrites(rec) == []


def test_a_record_without_set_commands_emits_nothing():
    # Without it every other donor (the gyms, the League) would gain stray data merge lines.
    rec = synthetic()
    del rec["set_commands"]
    assert place_donor.command_rewrites(rec) == []
    rec["set_commands"] = []
    assert place_donor.command_rewrites(rec) == []


def test_one_line_per_set_command_in_order():
    # Without it a link could be dropped or doubled silently.
    cmds = [{"at": [i, 1, 2], "command": "say %d" % i} for i in range(6)]
    out = [parse(l) for l in place_donor.command_rewrites(synthetic(commands=cmds))]
    assert [c for *_, c in out] == ["say %d" % i for i in range(6)]


@pytest.mark.parametrize("record_id", TOWERS)
def test_every_place_template_is_followed_by_every_rewrite(record_id):
    # Without it the "_again" re-place (place_donor.functions) re-pastes the shipped, ungated chain over the
    # rewrites, or a rewrite runs before the paste that then overwrites it.
    rec = next(q for q in PLACEMENTS if q["id"] == record_id)
    want = place_donor.command_rewrites(rec)
    assert len(want) == len(rec["set_commands"])
    fns = place_donor.functions(rec, [], check=(0, 0, 0, "minecraft:stone"))
    pasting = {name: body for name, body in fns.items() if any(l.startswith("place template ") for l in body)}
    assert set(pasting) >= {"place_%s_go" % record_id, "place_%s_again" % record_id}
    for name, body in pasting.items():
        p = next(i for i, l in enumerate(body) if l.startswith("place template "))
        assert body[p + 1:p + 1 + len(want)] == want, "%s: the rewrites do not follow its place template" % name
    for name, body in fns.items():
        if name not in pasting:
            assert not any(l.startswith("data merge block") for l in body), "%s rewrites with no paste" % name


# ---------------------------------------------------------------------------------------- the tower records


def tower(record_id):
    return next(q for q in PLACEMENTS if q["id"] == record_id)


def test_only_the_two_towers_carry_set_commands():
    # Without it a set_commands block on some other record would be emitted by a tool nobody checked it against.
    assert sorted(q["id"] for q in PLACEMENTS if q.get("set_commands")) == sorted(TOWERS)


@pytest.mark.parametrize("record_id", TOWERS)
def test_every_link_is_gated_on_our_champion_flag(record_id):
    # Without it a link can run for anyone, and the one spawn burns on a player below the cap.
    for c in tower(record_id)["set_commands"]:
        assert FLAG in c["command"], c["command"]


@pytest.mark.parametrize("record_id", TOWERS)
def test_exactly_one_link_spawns_and_it_is_this_towers_necrozma(record_id):
    # Without it the spawn can be lost, doubled, or swapped between the towers.
    spawns = [c["command"] for c in tower(record_id)["set_commands"] if "pokespawnat" in c["command"]]
    assert len(spawns) == 1, spawns
    assert re.search(r"pokespawnat \S+ \S+ \S+ necrozma\b", spawns[0]), spawns[0]
    form = "dawn" if "dawn" in record_id else "dusk"
    assert "prism_fusion=%s" % form in spawns[0], spawns[0]


@pytest.mark.parametrize("record_id", TOWERS)
def test_exactly_one_link_fills_the_chain_in(record_id):
    # Without it the chain either never seals itself (repeat spawns) or seals twice.
    fills = [c for c in tower(record_id)["set_commands"]
             if "replace minecraft:chain_command_block" in c["command"]]
    assert len(fills) == 1, fills


@pytest.mark.parametrize("record_id", TOWERS)
def test_every_spawn_and_fill_link_is_if_never_unless(record_id):
    # Without it one inverted word fires the spawn or the seal for exactly the players who must not have it.
    assert gate_problems(tower(record_id)) == []


@pytest.mark.parametrize("record_id", TOWERS)
def test_every_link_tests_the_same_selector(record_id):
    # Without it the refusal and the spawn can test different radii or flags, leaving a player for whom
    # neither fires or both do.
    sel = set()
    for c in tower(record_id)["set_commands"]:
        m = re.match(r"execute (?:if|unless) entity (\S+) run ", c["command"])
        assert m, c["command"]
        sel.add(m.group(1))
    assert len(sel) == 1, sel
    assert FLAG + "=true" in sel.pop()


@pytest.mark.parametrize("record_id", TOWERS)
def test_every_offset_is_inside_the_template_and_distinct(record_id):
    # Without it a rewrite can aim outside the paste (onto the world) or two rewrites at one block.
    rec = tower(record_id)
    sx, sy, sz = rec["size"]
    ats = [tuple(c["at"]) for c in rec["set_commands"]]
    assert len(set(ats)) == len(ats), ats
    for x, y, z in ats:
        assert 0 <= x < sx and 0 <= y < sy and 0 <= z < sz, (x, y, z, rec["size"])


@pytest.mark.parametrize("record_id", TOWERS)
def test_the_towers_own_rewrites_parse_back_to_the_authored_commands(record_id):
    # Without it the real tellraw link -- the one with JSON in it -- could be the one that fails to parse.
    rec = tower(record_id)
    lines = place_donor.command_rewrites(rec)
    assert len(lines) == len(rec["set_commands"])
    for line, c in zip(lines, rec["set_commands"]):
        assert snbt_problems(line, c["command"]) == []


# ------------------------------------------------------------------------------------------------ mutations
#
# The generator is mutated; no record is touched.


def test_dropping_the_rotation_is_caught(monkeypatch):
    # Proves the position test bites on the generator: with the turn removed, three rotations go red.
    monkeypatch.setattr(place_town, "rotate", lambda x, z, rot: (x, z))
    problems = position_problems()
    assert any(p.startswith("clockwise_90:") for p in problems), problems
    assert any(p.startswith("180:") for p in problems), problems
    assert any(p.startswith("counterclockwise_90:") for p in problems), problems


def test_a_rotation_turned_the_wrong_way_is_caught(monkeypatch):
    # The subtler fault: clockwise and counterclockwise swapped. 180 and none still agree; the two quarter
    # turns must not.
    swapped = {"clockwise_90": "counterclockwise_90", "counterclockwise_90": "clockwise_90"}
    monkeypatch.setattr(place_town, "rotate", lambda x, z, rot: REAL_ROTATE(x, z, swapped.get(rot, rot)))
    problems = position_problems()
    assert any(p.startswith("clockwise_90:") for p in problems), problems
    assert not any(p.startswith(("none:", "180:")) for p in problems), problems


def test_dropping_the_escaping_is_caught(monkeypatch):
    # Proves the escaping test bites: a generator that wraps the command in quotes without escaping it.
    fake = types.SimpleNamespace(dumps=lambda s, **kw: '"%s"' % s)
    monkeypatch.setattr(place_donor, "json", fake)
    assert escaping_problems() != []


def test_ascii_escaping_is_caught(monkeypatch):
    # The other way json.dumps can go wrong for SNBT: its default ensure_ascii=True turns the e-acute into a
    # \\u escape, which the 1.21.1 reader rejects. The generator passes ensure_ascii=False; this proves the
    # test would notice if it stopped.
    fake = types.SimpleNamespace(dumps=lambda s, **kw: json.dumps(s))
    monkeypatch.setattr(place_donor, "json", fake)
    assert any("escapes" in p for p in escaping_problems())


@pytest.mark.parametrize("link,old,new", [
    ("pokespawnat", "execute if entity", "execute unless entity"),
    ("chain_command_block", "execute if entity", "execute unless entity"),
    ("tellraw", "execute unless entity", "execute if entity"),
])
def test_a_flipped_gate_is_caught(link, old, new):
    # Proves gate_problems reads the word, on a copy of the Dawn tower's links; the record on disk is untouched.
    rec = copy.deepcopy(tower("legendary_dawn_tower"))
    c = next(c for c in rec["set_commands"] if link in c["command"])
    c["command"] = c["command"].replace(old, new, 1)
    assert gate_problems(rec) != []

"""Unit WAY's direction lines and charters (overnight 2026-10-08), checked by the test author, who did not build them.

  the picnicker  dlg_route1_rattata_picnic `o_birds` after `o_done` (the sapling hint)
  Koga's tracker dlg_main_koga_marsh_tracker `koga_mega` after `koga_repeat` (U47: the way to the Mega field)
  the charters   data/ferries.json: the four charters' SQ-SUNSET-01 gate moved to superseded_gates (A10)
  (Oak's `oak_birds` is checked in tests/test_oak_lab_scene.py, through that file's model of his commands.)

Reachability is judged on what tools/compile_dialogue.py WRITES, run on tools/oak_starter_audit.py's Molang
interpreter with the small command model below (a command it does not know fails the test). The claims the lines make
are judged against the data they describe, measured here and not taken from the lines' placeholder notes:
the Mega dens (data/gulch_mine.json farms) against data/rift_zones.json's zone boxes and passes; the gulch's flag
(data/gulch_mine.json flag) against data/progression.json's leaders; the tracker's seat (data/npc_seats.json) against
the lookout's grille (data/gulch_mine.json gate.grille); the tree nests (data/habitat_blocks.json) against every other
spawn entry in data/spawns.json. The charters are judged on tools/ferries.py's built output.

Mutations run 2026-10-08 (each restored):
  compile_dialogue Compiler.page: a self-looping line no longer closes (goto instead)   the picnic, Koga and Oak
                   hint tests fail (no end after 64 pages)
  ferries.gate_check returns None for every flag gate                                 test_every_built_charter_...
  data, in memory: charter_relic's superseded gate moved back into gates              test_no_built_ferry_line_...
  data, in memory: the grille moved 1,000 blocks north; z2's threshold set to 6        the distance/bearing and
                                                                                       badge-count tests

Not covered, and it needs a running server: that Cobblemon runs these pages as this interpreter does, that the
players read the hints, and that the Mega field's dens and the gulch's grille behave as their own tools say. "Nest
nowhere else" is checked against OUR spawn tables only: 36 subregions keep the pack's default spawns
(policy signature_overlay_keep_defaults), and whether Cobblemon's defaults spawn the tree-only species in the open is
not checked here.
"""
from __future__ import annotations

import copy
import json
import math
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import compile_dialogue as CD  # noqa: E402
import oak_starter_audit as OA  # noqa: E402

DATA = ROOT / "data"


def _json(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


CONVS = {c["id"]: c for c in _json("dialogue.json")["conversations"]}
SEATS = {s["id"]: s for s in _json("npc_seats.json")["seats"]}
PROG = _json("progression.json")
FLAGS = {f["id"]: f for f in PROG["flags"]}
PICNIC, KOGA = "dlg_route1_rattata_picnic", "dlg_main_koga_marsh_tracker"


# ------------------------------------------------------------------------------------------------ the runtime
class Commands:
    """The commands these conversations send, on one player. Anything else fails."""

    P = r"(?:PLAYER-UUID|Player|@s)"

    def on_write(self, run, key, val):
        pass

    def command(self, w, cmd):
        cmd = cmd.strip()
        m = re.fullmatch(r"scoreboard objectives add (\S+) dummy", cmd)
        if m:
            w["objectives"].add(m.group(1))
            return 1
        m = re.fullmatch(r"tag %s (add|remove) (\S+)" % self.P, cmd)
        if m:
            (w["tags"].add if m.group(1) == "add" else w["tags"].discard)(m.group(2))
            return 1
        m = re.fullmatch(r"execute as %s (.*)" % self.P, cmd)
        assert m, "a command this model does not interpret: %r" % cmd
        return self.sub(w, m.group(1))

    def sub(self, w, rest):
        m = re.fullmatch(r"if entity @s\[advancements=\{cobblers:flag/([a-z0-9_]+)=true\}\] run tag @s add (\S+)", rest)
        if m:
            if m.group(1) in w["flags"]:
                w["tags"].add(m.group(2))
                return 1
            return None
        raise AssertionError("an execute this model does not interpret: %r" % rest)


CMDS = Commands()


def fresh(flags=(), **fields):
    w = {"data": {}, "tags": set(), "flags": set(flags), "scores": {}, "objectives": set()}
    for fid, v in fields.items():
        w["data"][CD.key(fid.replace("__", "."))] = v
    return w


_DLG = {}


def dialogue(cid):
    if cid not in _DLG:
        _DLG[cid] = CD.build(cid, DATA)["data/cobblers/dialogues/%s.json" % cid]
    return _DLG[cid]


def talk(w, cid):
    """One click, read to the end (line pages only: these conversations' later pages have no choices)."""
    dlg = dialogue(cid)
    pages = {p["id"]: p for p in dlg["pages"]}
    r = OA.Run(w, CMDS)
    r.exec(dlg["initializationAction"])
    page, v, shown = (None if r.closed else r.page), r.v, []
    while page is not None:
        assert len(shown) < 64, "%s: no end after %s" % (cid, shown[-8:])
        assert page in pages, "%s sets page %r, which it does not have" % (cid, page)
        shown.append(page)
        inp = pages[page].get("input")
        assert isinstance(inp, str), "%s: a choice on %s, which this walk does not answer" % (cid, page)
        rr = OA.Run(w, CMDS, v)
        rr.exec(inp)
        page = None if rr.closed else rr.page
    return shown


def field(w, fid):
    return w["data"].get(CD.key(fid), 0.0)


# ------------------------------------------------------------------------------------------------ the picnicker
P = "quest__evt_route1_rattata_picnic__"


# Without it the bird line can be orphaned (a dead node) or, as in WAY's first commit, made to bounce between o_done
# and o_birds forever inside one talk.
def test_a_finished_picnic_ends_each_talk_on_the_bird_hint():
    w = fresh(**{P + "completed": 1.0})
    for _ in range(3):
        assert talk(w, PICNIC) == ["o_done", "o_birds"]


# Without it the hint could be cut off from the path a player actually takes to finish the picnic (leaving the berry).
def test_leaving_the_berry_finishes_the_picnic_and_reaches_the_bird_hint():
    w = fresh(**{P + "berry_left": 1.0})
    assert talk(w, PICNIC) == ["o_thanks", "o_done", "o_birds"]
    assert field(w, "quest.evt_route1_rattata_picnic.completed") in (1, 1.0, True)


# Without it the line could send the player away from the tree it names: "the great tree north of here".
def test_the_tree_the_picnicker_points_at_is_north_of_the_picnic():
    scene = next(s for s in _json("scenes.json")["scenes"] if s["id"] == "route1_rattata_picnic")
    (x0, _, z0), (x1, _, z1) = scene["area"]["from"], scene["area"]["to"]
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    blocks = {b["id"]: b for b in _json("habitat_blocks.json")["blocks"]}
    tree = blocks["route1_sapling_low"]["position"]
    text = next(n["text"] for n in CONVS[PICNIC]["nodes"] if n["id"] == "o_birds")
    assert "north" in text
    bearing = math.degrees(math.atan2(tree["x"] - cx, -(tree["z"] - cz))) % 360   # 0 = north (-z), 90 = east (+x)
    assert bearing <= 45 or bearing >= 315, bearing


# ------------------------------------------------------------------------------------------------ the bird hint's claim
def _tree_only_species():
    blocks = _json("habitat_blocks.json")["blocks"]
    # a nest is a Habitat Block disguised as part of a tree (its mimic is a log or leaves) in an elder or sapling
    trees = {b["pool"].split(":", 1)[1] for b in blocks
             if re.search(r"_(log|leaves|wood)$", b.get("mimic") or "")
             and re.match(r"(elder_|sapling_|route1_sapling)", b["id"])}
    tree, other = {}, set()
    for e in _json("spawns.json")["entries"]:
        if e.get("scope") in trees:
            tree.setdefault(e["species"], set()).add(e["scope"])
        else:
            other.add(e["species"])
    return {sp: sorted(s) for sp, s in tree.items() if sp not in other}


# Without it Oak's "some kinds nest nowhere else" can become false (a re-balance puts the last tree-only bird in the
# open) and nothing says so. Measured 2026-10-08: bombirdier, ledian, ledyba, mandibuzz, rowlet, vullaby.
def test_some_species_spawn_only_from_the_tree_nests():
    only = _tree_only_species()
    oak = next(n["text"] for n in CONVS["dlg_main_pallet_oak"]["nodes"] if n["id"] == "oak_birds")
    assert "nowhere else" in oak
    assert only, "Oak says some birds nest nowhere else; every tree species also spawns in the open"


# ------------------------------------------------------------------------------------------------ Koga's tracker
K = "quest__main_worldshift_reveal__"
KOGA_ACCOUNT = ["koga_001", "koga_002", "koga_003", "koga_004", "koga_005", "koga_006", "koga_007"]


# Without it the direction line can drop out of the account's end (a dead node), or the account can loop.
def test_the_account_ends_on_the_mega_direction_and_moves_the_stage():
    w = fresh(**{K + "stage": "erika_reveal_complete"})
    assert talk(w, KOGA) == KOGA_ACCOUNT + ["koga_repeat", "koga_mega"]
    assert field(w, "quest.main_worldshift_reveal.stage") == "koga_reveal_complete"


# Without it the direction could be heard once and lost, or the account replay: every later talk repeats the way.
def test_every_later_talk_repeats_the_mega_direction_alone():
    w = fresh(**{K + "stage": "erika_reveal_complete"})
    talk(w, KOGA)
    for _ in range(3):
        assert talk(w, KOGA) == ["koga_mega"]


def _koga_text():
    return next(n["text"] for n in CONVS[KOGA]["nodes"] if n["id"] == "koga_mega")


WORDS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}


def _inside(boxes, x, z):
    return any(a <= x <= c and b <= z <= d for a, b, c, d in boxes)


# Without it the line can promise the Mega field at a badge count the zone does not admit (Walk 2 item 14 said six).
def test_the_badge_count_the_line_names_is_the_one_every_mega_den_needs():
    m = re.search(r"\b(%s|\d) badges\b" % "|".join(WORDS), _koga_text())
    assert m, "koga_mega no longer names the field's badge count: re-check what it promises"
    said = WORDS.get(m.group(1)) or int(m.group(1))
    zones = _json("rift_zones.json")["zones"]
    dens = [d for f in _json("gulch_mine.json")["farms"] for d in f["dens"]]
    assert dens
    for d in dens:
        x, _, z = d["anchor"]
        holders = [zid for zid, zz in zones.items() if _inside(zz.get("boxes") or [], x, z)]
        assert len(holders) == 1, (d["id"], holders)
        p = zones[holders[0]]["pass"]
        assert p["kind"] == "badges" and p["threshold"] == said, (d["id"], holders[0], p.get("threshold"), said)


# Without it the line names the wrong leader for the gulch (its flag is the sixth badge: whose is it?).
def test_the_leader_the_line_names_gives_the_gulch_badge():
    adv = _json("gulch_mine.json")["flag"]["advancement"]
    fid = adv.split("cobblers:flag/", 1)[1]
    leaders = {t.split("_")[1] for ids in FLAGS[fid]["set_by"]["trainer_ids"].values() for t in ids}
    kanto = FLAGS[fid]["set_by"]["trainer_ids"]["kanto"][0].split("_", 1)[1]
    text = _koga_text()
    assert "%s's badge" % kanto.capitalize() in text, (fid, kanto, leaders)


# Without it "about N blocks south" can drift from where the lookout really is: a direction line that lies is worse
# than none.
def test_the_distance_and_bearing_to_the_gulch_lookout_hold_from_the_trackers_seat():
    m = re.search(r"about ([\d,]+) blocks (north|south|east|west)", _koga_text())
    assert m, "koga_mega no longer gives the gulch's distance: re-check what it promises"
    said, way = int(m.group(1).replace(",", "")), m.group(2)
    sx, _, sz = SEATS["npc_main_koga_marsh_tracker"]["at"]
    g = _json("gulch_mine.json")["gate"]["grille"]
    gx, gz = g["x"], sum(g["z"]) / 2
    dist = math.hypot(gx - sx, gz - sz)
    assert abs(dist - said) <= 0.1 * dist, (said, round(dist))
    bearing = math.degrees(math.atan2(gx - sx, -(gz - sz))) % 360
    want = {"north": 0, "east": 90, "south": 180, "west": 270}[way]
    assert min(abs(bearing - want), 360 - abs(bearing - want)) <= 45, (way, round(bearing))


# ------------------------------------------------------------------------------------------------ the charters
import ferries as FR  # noqa: E402

DOC = FR.load()
CHARTERS = [ln for ln in DOC["lines"] if ln.get("superseded_gates")]


def _setters():
    """{(field, value)} some quest transition sets: what a quest_field gate can ever see."""
    out = set()
    for q in _json("quests.json")["quests"]:
        for t in q["transitions"]:
            for e in t["effects"]:
                if e["kind"] == "set_progression":
                    out.add((e["field"], json.dumps(e["value"])))
    return out


def _gate_problems(doc):
    setters, out = _setters(), []
    for ln in FR.emitted_lines(doc):
        for g in ln.get("gates") or []:
            if g["kind"] == "quest_field" and (g["field"], json.dumps(g.get("value", True))) not in setters:
                out.append("%s: %s=%r is set by no quest transition" % (ln["id"], g["field"], g.get("value", True)))
            if g["kind"] == "flag" and g["flag"] not in FLAGS:
                out.append("%s: flag %s is undeclared" % (ln["id"], g["flag"]))
    return out


# Without it a built line can again be gated on a field nothing grants and shut for everyone (review N109).
def test_no_built_ferry_line_is_gated_on_something_nothing_sets():
    assert _gate_problems(DOC) == []
    # and the check bites: the superseded gate, put back, is named
    doc = copy.deepcopy(DOC)
    relic = next(ln for ln in doc["lines"] if ln["id"] == "charter_relic")
    relic["gates"] = relic["gates"] + relic["superseded_gates"]
    assert any("sq_sunset_01" in p for p in _gate_problems(doc))


# Without it dropping the quest gate could take the Champion gate or the fare with it: the charters are postgame.
def test_every_charter_keeps_the_champion_gate_and_a_fare():
    assert len(CHARTERS) == 4, [ln["id"] for ln in CHARTERS]
    for ln in CHARTERS:
        assert {"kind": "flag", "flag": "champion_cleared"} in [{"kind": g["kind"], "flag": g.get("flag")}
                                                                for g in ln["gates"]], ln["id"]
        assert int(ln.get("fare") or 0) > 0, ln["id"]
        assert all(g["kind"] == "quest_field" for g in ln["superseded_gates"]), ln["id"]


# Without it the built trip could charge or teleport a player who has not beaten the Champion.
def test_every_built_charter_refuses_a_non_champion_before_the_fare():
    files, _ = FR.build(DOC)
    built = [ln for ln in FR.emitted_lines(DOC) if ln in CHARTERS]
    assert built, "no charter is built: nothing here is exercised"
    for ln in built:
        for a, b in FR.trips(ln):
            body = files["data/cobblers/function/ferries/%s/%s_to_%s.mcfunction" % (ln["id"], a, b)]
            gate = next((i for i, l in enumerate(body)
                         if "cobblers:flag/champion_cleared=true" in l and "return" in l), None)
            charge = next((i for i, l in enumerate(body) if l.startswith("function cobblers:ferries/charge")), None)
            tp = next((i for i, l in enumerate(body) if l.startswith("tp @s")), None)
            assert gate is not None, "%s %s->%s: no Champion check in the trip" % (ln["id"], a, b)
            assert charge is not None and tp is not None, (ln["id"], charge, tp)
            assert gate < charge < tp, (ln["id"], gate, charge, tp)
            assert "charge.amount set value %d" % int(ln["fare"]) in "\n".join(body)
    # nothing built names a superseded gate's field
    text = json.dumps({k: v for k, v in files.items()})
    for ln in CHARTERS:
        for g in ln["superseded_gates"]:
            assert g["field"] not in text and g["quest"] not in text, (ln["id"], g["field"])


# ------------------------------------------------------------------------------------------------ flag grants
# Without it a quest transition can grant a flag some other system owns, or one whose own record names a different
# setter (WAY's held Pallet -> gym 1 waypoint adds the second grant in the data: oak_sendoff on record_oak_sendoff).
def test_every_flag_grant_a_transition_runs_is_that_flags_declared_setter():
    seen = 0
    for q in _json("quests.json")["quests"]:
        for t in q["transitions"]:
            for e in t["effects"]:
                m = re.fullmatch(r"cobblers:flag/([a-z0-9_]+)/grant", e.get("function") or "") \
                    if e["kind"] == "function" else None
                if not m:
                    continue
                seen += 1
                f = FLAGS.get(m.group(1))
                assert f is not None, (q["id"], t["id"], m.group(1))
                sb = f["set_by"]
                assert (sb["kind"], sb.get("quest"), sb.get("transition")) == ("quest_transition", q["id"], t["id"]), \
                    (m.group(1), sb, q["id"], t["id"])
    assert seen >= 1, "no transition grants a flag: the check exercises nothing"

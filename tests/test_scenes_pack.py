"""tools/scenes_pack.py: the scene runtime pack built from the real data/scenes.json.

Written by the test author, not by the session that wrote the tool or the scene data.

What is asserted: every prop and actor conversation exists, runs the scene's quest and has npc_id null, and every
NPC's has an npc_id; markers (and each owner's slot) lie inside the area; zone transitions exist, check no item and
move none; each beat's Molang has no double quote or backslash (it sits inside runmolang "..."); click advancements
match the tag the hitbox or prop carries and reward a function the pack writes; an actor click counts only when one
of the clicker's own boxes (cobblers_pid match) is within 1.5 of the box they hit (`on target`), and opens their own
conversation; an actor spawns through q.run_command (a bare spawnpokemonat in a function does nothing on this server)
and queues its claim as the owner, and no spawnpokemonat is bare anywhere in the pack; the claim adopts only a
Pokemon without AI, of the actor's species and not yet an actor, re-reading the owner; adopt marks it fresh and owned,
never cobblers_mine, and cobblers_mine never outlives its at-function; each at-function keeps one Pokemon and one
hitbox per owner and vanishes only that owner's extras; the cycle removes only actors not refreshed since the last
cycle; exactly the scenes with actors, effects or zones get a beat line; scene functions are written as authored,
spawns wrapped; every function the pack calls exists in the pack; and the tool refuses a scene that breaks the rules
above rather than emitting it.

Expected values are derived from data/scenes.json, data/dialogue.json and data/quests.json, not from the pack.

Not covered, and it needs a running server (EXP-034): that `spawnpokemonat ... uncatchable no_ai` then `data merge`
yields an unbattleable, invulnerable actor; that the interaction entity's click fires
minecraft:player_interacted_with_entity with its Tags; that two players at one marker get two copies side by side;
that an actor reappears after a restart where the owner's state says.
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import scenes_pack as SP  # noqa: E402

DATA = ROOT / "data"
SCENES = json.loads((DATA / "scenes.json").read_text(encoding="utf-8"))["scenes"]
CONVS = {c["id"]: c for c in json.loads((DATA / "dialogue.json").read_text(encoding="utf-8"))["conversations"]}
QUESTS = {q["id"]: q for q in json.loads((DATA / "quests.json").read_text(encoding="utf-8"))["quests"]}
FN = "data/cobblers/function/scenes/"


@pytest.fixture(scope="module")
def pack():
    files, _scenes = SP.build(DATA)
    return files


def fn(pack, rel):
    return pack[FN + rel + ".mcfunction"]


def box(b):
    lo = [min(b["from"][i], b["to"][i]) for i in range(3)]
    hi = [max(b["from"][i], b["to"][i]) for i in range(3)]
    return lo, hi


def marker_at(m):
    return m["at"] if isinstance(m, dict) else m[:3]


def walk(v):
    if isinstance(v, dict):
        yield v
        for c in v.values():
            yield from walk(c)
    elif isinstance(v, list):
        for c in v:
            yield from walk(c)


# Without it a prop or actor opens a conversation that is missing, belongs to another quest, or also has an NPC
# class; or a scene NPC's conversation has no class for R17 to spawn.
@pytest.mark.parametrize("s", SCENES, ids=[s["id"] for s in SCENES])
def test_scene_conversations_exist_belong_to_the_quest_and_match_their_opener(s):
    for kind in ("props", "actors"):
        for p in s.get(kind) or []:
            c = CONVS.get(p["conversation"])
            assert c is not None, p["conversation"]
            assert c["quest_id"] == s["quest_id"], p["conversation"]
            assert "npc_id" in c and c["npc_id"] is None, p["conversation"]
    for n in s.get("npcs") or []:
        c = CONVS.get(n["conversation"])
        assert c is not None and c["quest_id"] == s["quest_id"] and c.get("npc_id"), n["conversation"]


# Without it an actor stands (or a player's copy is slotted) outside the area its beat runs in: never refreshed, it
# vanishes and respawns every second.
@pytest.mark.parametrize("s", SCENES, ids=[s["id"] for s in SCENES])
def test_markers_and_their_slots_lie_inside_the_area(s):
    lo, hi = box(s["area"])
    for name, m in (s.get("markers") or {}).items():
        at = marker_at(m)
        assert all(lo[i] <= at[i] <= hi[i] for i in range(3)), (name, at)
        slots = (m.get("slots") if isinstance(m, dict) else None) or s.get("slots") or SP.SLOTS
        for ox, oz in slots:
            px, pz = at[0] + 0.5 + ox, at[2] + 0.5 + oz
            assert lo[0] <= px < hi[0] + 1 and lo[2] <= pz < hi[2] + 1, (name, (ox, oz))
    for n in s.get("npcs") or []:
        assert all(lo[i] <= n["at"][i] <= hi[i] for i in range(3)), n


# Without it a zone could run a transition that checks the held item (read before the queued probe runs) or gives,
# takes or rewards items from a box the player merely walks through.
def test_zone_transitions_exist_check_no_item_and_move_none():
    zones = [(s, z) for s in SCENES for z in s.get("zones") or []]
    assert zones, "no zone in data/scenes.json: the rule was never exercised"
    for s, z in zones:
        ts = {t["id"]: t for t in QUESTS[s["quest_id"]]["transitions"]}
        for tid in z["transitions"]:
            t = ts[tid]
            kinds = {d.get("kind") for d in walk(t["conditions"])}
            assert not kinds & {"held_item", "inventory_contains"}, (tid, kinds)
            effects = {d.get("kind") for d in walk(t["effects"])}
            assert not effects & {"consume_held_item", "give_item", "grant_reward_once"}, (tid, effects)


# Without it a quote in the beat's Molang ends the runmolang "..." argument early and the whole beat fails to parse.
def test_beat_molang_has_no_double_quote_or_backslash(pack):
    n = 0
    for k, lines in pack.items():
        if not k.endswith("/beat.mcfunction"):
            continue
        for line in lines:
            m = re.fullmatch(r'(?:execute .* run )?runmolang "(.*)" @s', line)
            if line.startswith("runmolang") or " runmolang " in line:
                assert m, line[:120]
                assert '"' not in m.group(1) and "\\" not in m.group(1), line[:120]
                n += 1
    assert n >= len([s for s in SCENES if s.get("actors") or s.get("effects") or s.get("zones")])


# Without it a click advancement matches a tag no entity carries (the click does nothing), or another actor's, or
# rewards a function that is not in the pack.
def test_click_advancements_match_the_tags_the_entities_carry(pack):
    checked = 0
    for s in SCENES:
        sid = s["id"]
        place = "\n".join(fn(pack, "%s/place" % sid))
        for a in s.get("actors") or []:
            tag = "cobblers_click_%s_%s" % (sid, a["id"])
            adv = pack["data/cobblers/advancement/scenes/click/%s_%s.json" % (sid, a["id"])]
            pred = adv["criteria"]["click"]["conditions"]["entity"][0]["predicate"]
            assert adv["criteria"]["click"]["trigger"] == "minecraft:player_interacted_with_entity"
            assert pred == {"type": "minecraft:interaction", "nbt": '{Tags:["%s"]}' % tag}
            hitboxes = [k for k in pack if k.startswith(FN + "%s/%s/hitbox/" % (sid, a["id"]))]
            assert hitboxes
            for k in hitboxes:
                assert '"%s"' % tag in pack[k][0] and pack[k][0].startswith("summon minecraft:interaction"), k
            assert adv["rewards"]["function"] == "cobblers:scenes/%s/%s/clicked" % (sid, a["id"])
            assert FN + "%s/%s/clicked.mcfunction" % (sid, a["id"]) in pack
            checked += 1
        for p in s.get("props") or []:
            tag = "cobblers_prop_%s_%s" % (sid, p["id"])
            adv = pack["data/cobblers/advancement/scenes/prop/%s_%s.json" % (sid, p["id"])]
            pred = adv["criteria"]["click"]["conditions"]["entity"][0]["predicate"]
            assert pred == {"type": "minecraft:interaction", "nbt": '{Tags:["%s"]}' % tag}
            assert '"%s"]' % tag in place
            assert adv["rewards"]["function"] == "cobblers:scenes/%s/prop/%s" % (sid, p["id"])
            opened = fn(pack, "%s/prop/%s" % (sid, p["id"]))
            assert "opendialogue cobblers:%s @s" % p["conversation"] in opened
            checked += 1
    assert checked >= 40


def actor_slots(s, a):
    """(marker, k) for every slot the actor's place rules can put it at."""
    out = []
    for r in a["place"]:
        m = s["markers"][r["marker"]]
        slots = (m.get("slots") if isinstance(m, dict) else None) or s.get("slots") or SP.SLOTS
        out += [(r["marker"], k) for k in range(len(slots)) if (r["marker"], k) not in out]
    return out


ACTORS = [(s, a) for s in SCENES for a in s.get("actors") or []]
ACTOR_IDS = ["%s/%s" % (s["id"], a["id"]) for s, a in ACTORS]


# Without it any player who clicks an actor opens a dialogue for someone else's state, or a click on another owner's
# copy stacked over one's own (one-slot markers) is refused. The rule: the box clicked is the one whose `on target`
# is the clicker (and any box within 0.05 of it); the click is the clicker's own only if one of their own boxes
# (cobblers_pid equal to theirs) is within 1.5 of a clicked box; the conversation opened is always the clicker's own.
@pytest.mark.parametrize("s,a", ACTORS, ids=ACTOR_IDS)
def test_an_actor_click_opens_the_dialogue_only_near_the_clickers_own_copy(pack, s, a):
    lines = fn(pack, "%s/%s/clicked" % (s["id"], a["id"]))
    click = "cobblers_click_%s_%s" % (s["id"], a["id"])
    assert lines[0] == "advancement revoke @s only cobblers:scenes/click/%s_%s" % (s["id"], a["id"])
    owner = lines.index("scoreboard players operation #owner cobblers_pid = @s cobblers_pid")
    hit = [i for i, l in enumerate(lines) if l.endswith("add cobblers_hit")]
    assert [lines[i] for i in hit] == [
        "execute as @e[type=minecraft:interaction,tag=%s,distance=..8] at @s on target if entity @s[tag=cobblers_clicker] "
        "run tag @e[type=minecraft:interaction,tag=%s,distance=..0.05] add cobblers_hit" % (click, click)]
    own = [i for i, l in enumerate(lines) if l.endswith("add cobblers_own_click")]
    assert [lines[i] for i in own] == [
        "execute as @e[type=minecraft:interaction,tag=%s,distance=..8] if score @s cobblers_pid = #owner cobblers_pid "
        "at @s if entity @e[type=minecraft:interaction,tag=cobblers_hit,distance=..1.5] run tag @a[tag=cobblers_clicker] "
        "add cobblers_own_click" % click]
    assert owner < hit[0] < own[0], "the owner is read, then the box clicked, then the ownership test"
    cleared = lines.index("tag @e[tag=cobblers_hit] remove cobblers_hit")
    assert cleared > own[0], "a stale cobblers_hit makes the next player's click on anything near it count as theirs"
    opens = [l for l in lines if "opendialogue" in l]
    assert opens == ["execute if entity @s[tag=cobblers_own_click] run opendialogue cobblers:%s @s" % a["conversation"]]
    assert lines[-2:] == ["tag @s remove cobblers_clicker", "tag @s remove cobblers_own_click"]


# Without it the spawn is a bare `spawnpokemonat` in a function, which this server runs as nothing (staging
# 2026-09-24): the actor never appears. It must go through q.run_command, with the claim queued after it as the owner.
@pytest.mark.parametrize("s,a", ACTORS, ids=ACTOR_IDS)
def test_an_actor_spawn_runs_through_molang_and_queues_its_claim_as_the_owner(pack, s, a):
    for m, k in actor_slots(s, a):
        x, y, z = (s["markers"][m]["at"] if isinstance(s["markers"][m], dict) else s["markers"][m][:3])
        base = "cobblers:scenes/%s/%s" % (s["id"], a["id"])
        assert fn(pack, "%s/%s/spawn/%s_%d" % (s["id"], a["id"], m, k)) == [
            "runmolang \"q.run_command('spawnpokemonat %d %d %d %s level=%d uncatchable no_ai'); "
            "q.run_command('execute as ' + q.player.uuid + ' at @s run function %s/claim/%s_%d');\" @s"
            % (x, y, z, a["species"], a["level"], base, m, k)]


# Without it the claim takes over whatever Pokemon is nearest the marker: a player's sent-out party Pokemon or a wild
# one becomes an uncatchable, unbattleable actor. Only one just spawned (no AI, this species, not yet an actor) may
# be adopted, and the owner is re-read from the player the claim runs as (other beats change #owner meanwhile).
@pytest.mark.parametrize("s,a", ACTORS, ids=ACTOR_IDS)
def test_the_claim_adopts_only_a_fresh_ai_less_pokemon_of_the_actors_species(pack, s, a):
    for m, k in actor_slots(s, a):
        x, y, z = (s["markers"][m]["at"] if isinstance(s["markers"][m], dict) else s["markers"][m][:3])
        claim = fn(pack, "%s/%s/claim/%s_%d" % (s["id"], a["id"], m, k))
        assert claim[0] == "scoreboard players operation #owner cobblers_pid = @s cobblers_pid"
        sel = re.fullmatch(r"execute positioned (\S+) (\S+) (\S+) as @e\[(.*)\] run function (\S+)", claim[1])
        assert sel and len(claim) == 2, claim
        assert tuple(map(int, sel.group(1, 2, 3))) == (x, y, z)
        parts = sel.group(4)
        for need in ("type=cobblemon:pokemon", "distance=..1.5", "tag=!cobblers_actor", "limit=1",
                     'nbt={NoAI:1b,Pokemon:{Species:"cobblemon:%s"}}' % a["species"]):
            assert need in parts, (need, parts)
        assert sel.group(5) == "cobblers:scenes/%s/%s/adopt/%s_%d" % (s["id"], a["id"], m, k)


# Without it an adopted actor keeps cobblers_mine (the queued adopt runs after the at-function cleared the tag), and
# the next owner's at-function treats it as theirs: moves it, keeps it, or vanishes it. It must be marked fresh (so the
# cycle keeps it) and take the owner's id.
@pytest.mark.parametrize("s,a", ACTORS, ids=ACTOR_IDS)
def test_adopt_marks_the_actor_fresh_and_owned_never_mine(pack, s, a):
    tag = "cobblers_actor_%s_%s" % (s["id"], a["id"])
    for m, k in actor_slots(s, a):
        adopt = fn(pack, "%s/%s/adopt/%s_%d" % (s["id"], a["id"], m, k))
        assert adopt[0].startswith("data merge entity @s {Unbattleable:1b,Invulnerable:1b,")
        for t in ("cobblers_actor", tag, "cobblers_fresh", "cobblers_at_%s_%s_%d" % (a["id"], m, k)):
            assert "tag @s add %s" % t in adopt
        assert "scoreboard players operation @s cobblers_pid = #owner cobblers_pid" in adopt
        assert not [l for l in adopt if "cobblers_mine" in l]


# Without it a cobblers_mine tag outlives the at-function that set it, and leaks into another owner's actors.
def test_cobblers_mine_is_added_only_inside_an_at_function_that_clears_it(pack):
    at_fn = re.compile(re.escape(FN) + r"[a-z0-9_]+/[a-z0-9_]+/at/[a-z0-9_]+_\d+\.mcfunction$")
    hitbox = re.compile(re.escape(FN) + r"[a-z0-9_]+/[a-z0-9_]+/hitbox/[a-z0-9_]+_\d+\.mcfunction$")
    n = 0
    for k, lines in pack.items():
        if not k.endswith(".mcfunction"):
            continue
        adds = [l for l in lines if re.search(r"add cobblers_mine\b", l) or '"cobblers_mine"' in l]
        if not adds:
            continue
        if hitbox.match(k):
            # summoned with the tag, and called only from its at-function, before that clears the tag
            callers = [c for c, ls in pack.items() if c.endswith(".mcfunction")
                       and any(l.endswith("run function cobblers:scenes/" + k[len(FN):-len(".mcfunction")]) for l in ls)]
            assert callers == [k.replace("/hitbox/", "/at/")], (k, callers)
            continue
        assert at_fn.match(k), "%s adds cobblers_mine outside an at-function" % k
        assert lines[-1] == "tag @e[tag=cobblers_mine] remove cobblers_mine", k
        n += 1
    assert n >= len(ACTORS)


# Without it a second copy of an owner's actor (saved with its chunk before the cycle removed it, and loaded after a
# new one spawned) stands beside the first for good, or a duplicate hitbox opens the dialogue twice. Each at-function
# keeps one Pokemon and one hitbox of this owner's, and vanishes the rest of theirs (never anyone else's), before it
# moves or spawns anything.
@pytest.mark.parametrize("s,a", ACTORS, ids=ACTOR_IDS)
def test_each_at_function_keeps_one_pokemon_and_one_hitbox_per_owner(pack, s, a):
    tag = "cobblers_actor_%s_%s" % (s["id"], a["id"])
    for m, k in actor_slots(s, a):
        lines = fn(pack, "%s/%s/at/%s_%d" % (s["id"], a["id"], m, k))
        assert lines[0] == ("execute as @e[tag=%s] if score @s cobblers_pid = #owner cobblers_pid run tag @s add "
                            "cobblers_mine" % tag)
        keep_p = lines.index("tag @e[type=cobblemon:pokemon,tag=cobblers_mine,limit=1,sort=arbitrary] add cobblers_keep")
        keep_i = lines.index("tag @e[type=minecraft:interaction,tag=cobblers_mine,limit=1,sort=arbitrary] add cobblers_keep")
        vanish = [i for i, l in enumerate(lines) if "vanish" in l]
        assert [lines[i] for i in vanish] == [
            "execute as @e[tag=cobblers_mine,tag=!cobblers_keep] at @s run function cobblers:scenes/vanish"]
        unkeep = lines.index("tag @e[tag=cobblers_keep] remove cobblers_keep")
        later = [i for i, l in enumerate(lines) if "/move/" in l or "/spawn/" in l or "/hitbox/" in l]
        assert keep_p < vanish[0] and keep_i < vanish[0] and vanish[0] < unkeep < min(later)


# Without it the cycle kills actors that were just refreshed (every actor flickers out), or something that is not an
# actor; the only other caller of vanish is the at-functions' dedupe, limited to the owner's own extra copies.
def test_the_cycle_removes_only_actors_nobody_refreshed(pack):
    cycle = fn(pack, "cycle")
    kills = [l for l in cycle if "vanish" in l or "kill" in l]
    assert kills == ["execute as @e[tag=cobblers_actor,tag=!cobblers_fresh] at @s run function cobblers:scenes/vanish"]
    i = cycle.index(kills[0])
    assert cycle[i + 1] == "tag @e[tag=cobblers_actor,tag=cobblers_fresh] remove cobblers_fresh"
    beats = [j for j, l in enumerate(cycle) if l.endswith("/beat")]
    assert beats and min(beats) > i + 1, "a beat that refreshes before the sweep is undone by it"
    at_fn = re.compile(re.escape(FN) + r"[a-z0-9_]+/[a-z0-9_]+/at/[a-z0-9_]+_\d+\.mcfunction$")
    for k, lines in pack.items():
        if not k.endswith(".mcfunction") or k == FN + "cycle.mcfunction":
            continue
        calls = [l for l in lines if "function cobblers:scenes/vanish" in l]
        if calls:
            assert at_fn.match(k), "%s calls vanish" % k
            assert calls == ["execute as @e[tag=cobblers_mine,tag=!cobblers_keep] at @s run function cobblers:scenes/vanish"]
    # the only other kills: vanish's own `kill @s`, and a prop's place function replacing its own box
    assert fn(pack, "vanish")[-1] == "kill @s"
    assert not [l for k, ls in pack.items() if k.endswith(".mcfunction") and k != FN + "vanish.mcfunction"
                for l in ls if l.startswith("kill ") and "type=minecraft:interaction,tag=cobblers_prop_" not in l]


# Without it a scene with an actor never runs its beat (the actor never appears), or an NPC-only or props-only scene
# burns a beat every second for nothing.
def test_exactly_the_scenes_with_actors_effects_or_zones_get_a_beat_in_the_cycle(pack):
    cycle = fn(pack, "cycle")
    got = {re.search(r"function cobblers:scenes/([a-z0-9_]+)/beat$", l).group(1) for l in cycle if l.endswith("/beat")}
    want = {s["id"] for s in SCENES if s.get("actors") or s.get("effects") or s.get("zones")}
    assert got == want
    assert {s["id"] for s in SCENES} - want, "no NPC-only or props-only scene: the exclusion was never exercised"
    for s in SCENES:
        if s["id"] in want:
            lo, hi = box(s["area"])
            sel = "x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d" % (lo[0], lo[1], lo[2], hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2])
            assert "execute as @a[%s] at @s run function cobblers:scenes/%s/beat" % (sel, s["id"]) in cycle


# Without it a generated command calls a function the pack never wrote, which fails silently at run time.
def test_every_function_the_pack_calls_is_in_the_pack(pack):
    have = {"cobblers:" + k[len("data/cobblers/function/"):-len(".mcfunction")] for k in pack if k.endswith(".mcfunction")}
    calls = set()
    for k, content in pack.items():
        text = "\n".join(content) if isinstance(content, list) else json.dumps(content)
        calls |= set(re.findall(r"function (cobblers:scenes/[a-z0-9_/]+)", text))
        if isinstance(content, dict) and "rewards" in content:
            calls.add(content["rewards"]["function"])
    for tag in ("load", "tick"):
        calls |= set(pack["data/minecraft/tags/function/%s.json" % tag]["values"])
    assert calls
    assert sorted(calls - have) == []


# Without it a scene function a dialogue runs is changed on the way (or emitted with a leading slash), or its
# spawnpokemonat is left bare and does nothing (the Wooper encounter never spawns): a spawn goes through
# q.run_command, every other command is written as authored.
def test_scene_functions_are_written_as_authored_with_spawns_through_molang(pack):
    spawns = 0
    for s in SCENES:
        for name, cmds in (s.get("functions") or {}).items():
            lines = fn(pack, "%s/fn/%s" % (s["id"], name))
            assert not any(c.startswith("/") for c in cmds)
            want = []
            for c in cmds:
                if c.startswith("spawnpokemonat "):
                    want.append("runmolang \"q.run_command('%s');\" @s" % c)
                    spawns += 1
                else:
                    want.append(c)
            assert lines[1:] == want, (s["id"], name)
    assert spawns, "no scene function spawns: the wrapping was never exercised"


# Without it a spawnpokemonat somewhere in the pack runs bare inside a function and spawns nothing, without a word.
def test_no_spawnpokemonat_is_bare_in_any_generated_function(pack):
    seen = 0
    for k, lines in pack.items():
        if not k.endswith(".mcfunction"):
            continue
        for l in lines:
            if "spawnpokemonat" not in l:
                continue
            seen += 1
            m = re.fullmatch(r'runmolang "(.*)" @s', l)
            assert m, "%s: %s" % (k, l[:100])
            outside = re.sub(r"q\.run_command\('[^']*'\)", "", m.group(1))
            assert "spawnpokemonat" not in outside, "%s: %s" % (k, l[:100])
            assert '"' not in m.group(1) and "\\" not in m.group(1)
    assert seen >= len(ACTORS)


# ------------------------------------------------------------------ the tool refuses rather than emits

def _build_with(tmp_path, mutate):
    for name in ("scenes.json", "dialogue.json", "quests.json", "progression.json"):
        (tmp_path / name).write_text((DATA / name).read_text(encoding="utf-8"), encoding="utf-8")
    doc = json.loads((tmp_path / "scenes.json").read_text(encoding="utf-8"))
    mutate(doc)
    (tmp_path / "scenes.json").write_text(json.dumps(doc), encoding="utf-8")
    return SP.build(tmp_path)


def _scene(doc, sid):
    return next(s for s in doc["scenes"] if s["id"] == sid)


# Without it these checks could be passing because the tool never looks: each broken copy must be refused.
@pytest.mark.parametrize("why,match,mutate", [
    ("marker outside", "outside the area", lambda d: _scene(d, "route2_rollaway_geodude")["markers"]["geodude_cart"]["at"].__setitem__(1, 0)),
    ("npc conversation on a prop", "must have npc_id null", lambda d: _scene(d, "route1_rattata_picnic")["props"][0].__setitem__(
        "conversation", "dlg_route1_rattata_picnic")),
    ("prop conversation on an npc", "has no npc_id", lambda d: _scene(d, "route1_rattata_picnic")["npcs"][0].__setitem__(
        "conversation", "dlg_route1_picnic_bush")),
    ("other quest", "runs quest evt_route1_gastly_family", lambda d: _scene(d, "route1_rattata_picnic")["props"][0].__setitem__(
        "conversation", "dlg_route1_gastly_cup")),
    ("quote in molang", "needs escaping", lambda d: _scene(d, "route1_gastly_family")["actors"][0]["place"][0]["when"].__setitem__(
        "value", 'fam"ily')),
    ("held item in a beat", "held-item conditions cannot run in a beat", lambda d: _scene(d, "route1_gastly_family")["effects"][0].__setitem__(
        "when", {"kind": "held_item", "item": "minecraft:stick"})),
])
def test_the_tool_refuses_a_scene_that_breaks_the_rules(tmp_path, why, match, mutate):
    with pytest.raises(SystemExit, match=re.escape(match)):
        _build_with(tmp_path, mutate)

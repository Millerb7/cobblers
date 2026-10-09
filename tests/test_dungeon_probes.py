"""tools/dungeon_probes.py and data/dungeon_probes.json: the Night Shift's staging-only probe pack (EXP-069..083).

Written by the builder of the pack at the coordinator's request (VALIDITY AND ISOLATION ONLY), so these are the
builder's own checks and NOT an independent audit. They prove nothing about behaviour: every probe's behaviour is
its EXP's in-game reading.

Where an expectation comes from, never the generator under test:
  the pocket and its rescue box   data/portals.json pocket (dimension, bands, rescue_margin), read here
  Entei's band                    data/entei_boss.json pocket and room, plus the keeper's 64-block sweep margin
                                  (tools/entei_boss.py band_box(margin=64), stated here as a constant)
  the dungeon rows                DUNGEONS.md section 1: from z 1,024 (stated here as a constant)
  the border                      docs/STATE.md:74, playable x/z -1024..9215, with data/entei_boss.json's margin 32
  the limits                      fill/clone 32,768 blocks; forceload 256 chunks per add (tools/function_limits.py)
  the exempt tag                  data/blackout.json claims.exempt_tag, read here
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import dungeon_probes as D  # noqa: E402
import function_limits  # noqa: E402

DOC = json.loads((ROOT / "data" / "dungeon_probes.json").read_text(encoding="utf-8"))
PORTALS = json.loads((ROOT / "data" / "portals.json").read_text(encoding="utf-8"))
ENTEI = json.loads((ROOT / "data" / "entei_boss.json").read_text(encoding="utf-8"))
BLACKOUT = json.loads((ROOT / "data" / "blackout.json").read_text(encoding="utf-8"))
NS = "cobblers_dg_probes"
POCKET = "cobblers:pocket"
BORDER, MARGIN = (-1024, 9215), 32
ENTEI_SWEEP = 64
DUNGEON_ROWS_Z = 1024
PROBES = ["p1", "b1", "b2", "b3", "r1", "r2", "f1", "l1", "l2", "c1", "xt1", "v1", "i2", "lo1", "sg1"]
EVENTS = {"pokemon_sent_post", "battle_victory"}

# Every command that acts on a PLAYER, by (probe, function): each is an owner step its EXP names. A new one fails here
# until it is reviewed and added.
PLAYER_COMMANDS = {
    ("*", "enter"), ("*", "leave"), ("*", "go"), ("*", "cleanup_end"),
    ("b1", "join"), ("b1", "clear"), ("b1", "pass"), ("b2", "kit"), ("b3", "fight"), ("b3", "out"),
    ("r1", "kit"), ("r1", "pick"), ("r1", "unkit"), ("r1", "take_pick"), ("r1", "zero"),
    ("r2", "kit"), ("r2", "pick"), ("r2", "unkit"), ("r2", "take_pick"),
    ("f1", "catch_pc"), ("f1", "catch_pb"), ("f1", "drop_pb"), ("f1", "drop_pc"),
    ("l2", "to_shallow"), ("l2", "to_deep"), ("v1", "at32"), ("v1", "at64"), ("v1", "at128"),
    ("lo1", "join"), ("lo1", "dead"), ("lo1", "timeout"), ("lo1", "charge"),
    ("sg1", "give_owner"), ("sg1", "recipes"),
    # these match the same command shapes but act on the probe's own mobs, not a player: the F1 husks, L1's sleeper
    ("f1", "catch_b"), ("f1", "catch_c"), ("l1", "dress"),
}
PLAYER_CMD = re.compile(r"(?:^|run )(kill @s|gamemode |give @s|clear @s|tp @s|effect give @s|recipe give @s|"
                        r"bossbar set \S+ players @s)")


@pytest.fixture(scope="module")
def files():
    return D.build(DOC)


def functions(files):
    out = {}
    pre = "data/%s/function/" % NS
    for rel, body in files.items():
        if rel.startswith(pre) and rel.endswith(".mcfunction"):
            pid, name = rel[len(pre):-len(".mcfunction")].split("/", 1)
            out[(pid, name)] = body.splitlines()
    return out


# ------------------------------------------------------------------ the record


def test_probe_list_and_numbering():
    assert [p["id"] for p in DOC["probes"]] == PROBES
    assert [p["exp"] for p in DOC["probes"]] == ["EXP-%03d" % n for n in range(69, 84)]
    assert "dx1" not in [p["id"] for p in DOC["probes"]], "DX1 waits for the run tag (E1)"


def test_every_probe_has_its_exp_readme():
    for p in DOC["probes"]:
        d = ROOT / "experiments" / ("%s-%s" % (p["exp"], p["slug"]))
        assert (d / "README.md").is_file(), d
        text = (d / "README.md").read_text(encoding="utf-8")
        for head in ("## Objective", "## Implementation", "## Test instructions", "## Results", "## Limitations",
                     "## Decision"):
            assert head in text, (p["exp"], head)
        # a status line, and an owner half still marked open: the RCON halves ran 2026-10-08, no owner half has
        assert "**Status:" in text, p["exp"]
        assert "OPEN" in text or "NOT_EXECUTED" in text or p["id"] == "i2", p["exp"]


def test_dimension_is_the_portals_pocket():
    assert DOC["dimension"] == PORTALS["pocket"]["dimension"] == POCKET


# ------------------------------------------------------------------ the areas, computed here


def _areas():
    out = {}
    row, i = DOC["row"], 0
    for p in DOC["probes"]:
        if p["id"] == "i2":
            s = p["strip"]
            out["i2"] = (s["x0"], s["z0"], s["x0"] + s["length"] - 1, s["z0"] + s["width"] - 1)
        else:
            x0 = row["origin_x"] + i * row["spacing"]
            out[p["id"]] = (x0, row["z_min"], x0 + row["spacing"] - 1, row["z_max"])
            i += 1
    return out


def _foreign():
    pp = PORTALS["pocket"]
    rescue_z = (min(pp["bands"].values()) - pp["rescue_margin"], max(pp["bands"].values()) + pp["rescue_margin"])
    ep, half = ENTEI["pocket"], ENTEI["room"]["half"]
    xs = [ep["origin"][0] + k * ep["spacing"] for k in range(ep["slots"])]
    entei = (min(xs) - half - ENTEI_SWEEP, ep["origin"][1] - half - ENTEI_SWEEP,
             max(xs) + half + ENTEI_SWEEP, ep["origin"][1] + half + ENTEI_SWEEP)
    return rescue_z, entei


def _meet(a, b):
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def test_areas_disjoint_from_each_other_and_every_foreign_box():
    areas = _areas()
    assert areas == {p: D.area(DOC, p) for p in PROBES}, "the generator's areas differ from the record's arithmetic"
    rescue_z, entei = _foreign()
    lo, hi = BORDER[0] + MARGIN, BORDER[1] - MARGIN
    for pid, a in areas.items():
        assert lo <= a[0] and a[2] <= hi and lo <= a[1] and a[3] <= hi, (pid, a)
        assert a[3] < rescue_z[0] or a[1] > rescue_z[1], (pid, "meets the portals' rescue box z", rescue_z)
        assert not _meet(a, entei), (pid, "meets Entei's band", entei)
        assert a[3] < DUNGEON_ROWS_Z, (pid, "meets the dungeon slot rows")
    ids = list(areas)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            assert not _meet(areas[a], areas[b]), (a, b)


def test_generator_refuses_an_overlap_with_entei():
    bad = json.loads(json.dumps(DOC))
    bad["row"]["origin_x"] = ENTEI["pocket"]["origin"][0]
    bad["row"]["z_min"], bad["row"]["z_max"] = ENTEI["pocket"]["origin"][1] - 8, ENTEI["pocket"]["origin"][1] + 8
    with pytest.raises(D.ProbeError):
        D.build(bad)


# ------------------------------------------------------------------ the pack's shape


def test_pack_format_and_no_load_or_tick_tag(files):
    assert json.loads(files["pack.mcmeta"])["pack"]["pack_format"] == 48
    assert not [r for r in files if r.startswith("data/minecraft/")], "the probes must not run on their own"


def test_namespaces(files):
    for rel in files:
        if rel == "pack.mcmeta":
            continue
        parts = rel.split("/")
        assert parts[0] == "data", rel
        if parts[1] == "cobblemon":
            assert parts[2] == "callbacks" and parts[3] in EVENTS and parts[4].startswith("cobblers_dg_probes_"), rel
            assert parts[4].endswith(".molang"), rel
        else:
            assert parts[1] == NS, rel


def test_json_files_parse(files):
    for rel, body in files.items():
        if rel.endswith(".json") or rel.endswith(".mcmeta"):
            json.loads(body)


def test_npc_classes(files):
    classes = {r: json.loads(b) for r, b in files.items() if "/npcs/" in r}
    assert len(classes) == 18
    for rel, c in classes.items():
        assert c["party"]["type"] == "simple" and 1 <= len(c["party"]["pokemon"]) <= 6, rel
        assert c["battleConfiguration"]["canChallenge"] is False, rel
        assert c["canDespawn"] is False and c["isInvulnerable"] is True, rel


def test_recipes_carry_the_sigil_components(files):
    rec = {r: json.loads(b) for r, b in files.items() if "/recipe/" in r}
    assert len(rec) == 2
    for rel, r in rec.items():
        comp = r["result"]["components"]
        assert "cobblers_dg_sigil" in comp["minecraft:custom_data"], rel
        assert comp["minecraft:rarity"] == "rare", rel


# ------------------------------------------------------------------ every function


def test_every_function_passes_function_limits(files):
    for (pid, name), lines in functions(files).items():
        assert function_limits.check_lines(lines, name) == [], (pid, name)


RUN_FILL = re.compile(r"\bfill (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+)")
FL_ADD = re.compile(r"forceload add (-?\d+) (-?\d+) (-?\d+) (-?\d+)")


def test_prefixed_fills_and_forceloads_are_within_limits(files):
    """function_limits' volume check reads a line that STARTS with fill; I2 prefixes every fill with
    `execute store result score ... run`, so the limit is checked here for every fill and forceload."""
    for (pid, name), lines in functions(files).items():
        for line in lines:
            for m in RUN_FILL.finditer(line):
                a = list(map(int, m.groups()))
                v = (abs(a[3] - a[0]) + 1) * (abs(a[4] - a[1]) + 1) * (abs(a[5] - a[2]) + 1)
                assert v <= 32768, (pid, name, line[:80], v)
            for m in FL_ADD.finditer(line):
                x0, z0, x1, z1 = map(int, m.groups())
                n = (abs(x1 // 16 - x0 // 16) + 1) * (abs(z1 // 16 - z0 // 16) + 1)
                assert n <= 256, (pid, name, line, n)


def test_i2_forceloads_one_strip_in_two_batches(files):
    lines = functions(files)[("i2", "shell_in")]
    adds = [l for l in lines if l.startswith("forceload add")]
    s = DOC["probes"][12]["strip"]
    assert len(adds) == 2 and s["length"] == 2048 and s["width"] == 64
    chunks = 0
    for l in adds:
        x0, z0, x1, z1 = map(int, l.split()[2:])
        chunks += (x1 // 16 - x0 // 16 + 1) * (z1 // 16 - z0 // 16 + 1)
    assert chunks == 512


OBJ = re.compile(r"\bdp[a-z0-9]+\.[a-z0-9_]+\b")
SCORE_OBJ = re.compile(r"(?:scoreboard players (?:set|add|remove|get|reset) \S+|if score \S+|unless score \S+|"
                       r"store result score \S+|operation \S+|objectives (?:add|remove)) (\S+)")


def test_objectives_and_tags_are_the_probes_own(files):
    exempt = BLACKOUT["claims"]["exempt_tag"]
    for (pid, name), lines in functions(files).items():
        own = "dp%s." % pid
        for line in lines:
            if line.lstrip().startswith("#"):
                continue
            for tok in OBJ.findall(line):
                assert tok.startswith(own), (pid, name, tok)
            for obj in SCORE_OBJ.findall(line):
                assert obj.startswith(own), (pid, name, obj, line[:100])
            for tag in re.findall(r"tag=!?([A-Za-z0-9_.]+)", line) + re.findall(r"\btag \S+ (?:add|remove) (\S+)", line):
                assert tag.startswith(own) or (tag == exempt and (pid, name) in {("l2", "bind_shallow"), ("l2", "bind_deep")}), (pid, name, tag)


def test_objective_criteria(files):
    """dummy, deathCount, or a mined stat in its dotted form (minecraft.mined:minecraft.coal_ore)."""
    for (pid, name), lines in functions(files).items():
        for line in lines:
            m = re.match(r"scoreboard objectives add (\S+) (\S+)$", line)
            if m:
                assert m.group(2) in ("dummy", "deathCount") or re.fullmatch(
                    r"minecraft\.mined:minecraft\.[a-z_]+", m.group(2)), (pid, name, line)


def test_callbacks_act_only_on_their_probes_tag(files):
    cbs = {r: b for r, b in files.items() if r.startswith("data/cobblemon/")}
    assert len(cbs) == 3
    for rel, body in cbs.items():
        pid = rel.rsplit("_", 1)[1].split(".")[0]
        cmds = re.findall(r"q\.run_command\('([^;]*)'\);", body)
        assert cmds, rel
        for c in cmds:
            assert ("tag=dp%s." % pid) in c or ("@s[x=" in c and "if dimension %s" % POCKET in c), (rel, c)
        assert body.count("{") == body.count("}") and body.count("(") == body.count(")"), rel


WORLD = re.compile(r"(?:^|run |\s)(fill|setblock|summon|forceload|spawnnpcat|spawnpokemonat|particle|item replace block|"
                   r"data (?:remove|merge|modify) block|kill @e)\b")
IN_POCKET = re.compile(r"\b(?:in|if dimension) cobblers:pocket\b")
CALLS = re.compile(r"function (%s:[a-z0-9_/]+)" % NS)


def _contexts(fns):
    """Functions whose every caller runs them in cobblers:pocket: called from a line carrying `execute in
    cobblers:pocket` or `if dimension cobblers:pocket`, or from a function already in the pocket's context."""
    callers = {}
    for (pid, name), lines in fns.items():
        for line in lines:
            for ref in CALLS.findall(line):
                callers.setdefault(ref, []).append(((pid, name), line))
    pocket = set()
    changed = True
    while changed:
        changed = False
        for (pid, name) in fns:
            ref = "%s:%s/%s" % (NS, pid, name)
            if (pid, name) in pocket or ref not in callers:
                continue
            if all(IN_POCKET.search(l) or c in pocket for c, l in callers[ref]
                   if "in minecraft:overworld" not in l):
                pocket.add((pid, name))
                changed = True
    return pocket


def test_every_world_write_is_in_the_pocket(files):
    fns = functions(files)
    pocket = _contexts(fns)
    for (pid, name), lines in fns.items():
        for line in lines:
            if line.startswith("#") or not WORLD.search(line):
                continue
            assert IN_POCKET.search(line) or (pid, name) in pocket, (pid, name, line[:100])


COORD_CMDS = [re.compile(p) for p in (
    r"fill (-?\d+) -?\d+ (-?\d+) (-?\d+) -?\d+ (-?\d+)", r"setblock (-?\d+) -?\d+ (-?\d+)",
    r"forceload (?:add|remove) (-?\d+) (-?\d+) (-?\d+) (-?\d+)", r"\btp @s (-?[\d.]+) [-\d.]+ (-?[\d.]+)",
    r"summon \S+ (-?[\d.]+) [-\d.]+ (-?[\d.]+)", r"positioned (-?[\d.]+) [-\d.]+ (-?[\d.]+)",
    r"particle \S+ (-?[\d.]+) [-\d.]+ (-?[\d.]+)", r"block (-?\d+) -?\d+ (-?\d+)",
    r"spawnnpcat (-?[\d.]+) [-\d.]+ (-?[\d.]+)", r"\{x:\"(-?[\d.]+)\",y:\"-?\d+\",z:\"(-?[\d.]+)\"")]
BOX = re.compile(r"x=(-?\d+),y=-?\d+,z=(-?\d+),dx=(\d+),dy=\d+,dz=(\d+)")


def test_every_coordinate_is_inside_the_probes_own_area(files):
    areas = _areas()
    for (pid, name), lines in functions(files).items():
        x0, z0, x1, z1 = areas[pid]
        for line in lines:
            if line.startswith("#") or "in minecraft:overworld" in line:
                continue
            pts = []
            for rx in COORD_CMDS:
                for g in rx.findall(line):
                    nums = [float(v) for v in g]
                    pts += list(zip(nums[0::2], nums[1::2]))
            for m in BOX.findall(line):
                bx, bz, dx, dz = map(int, m)
                pts += [(bx, bz), (bx + dx, bz + dz)]
            for x, z in pts:
                assert x0 <= x <= x1 + 1 and z0 <= z <= z1 + 1, (pid, name, (x, z), areas[pid], line[:100])
    for rel, body in files.items():
        if rel.startswith("data/cobblemon/"):
            pid = rel.rsplit("_", 1)[1].split(".")[0]
            for m in BOX.findall(body):
                bx, bz, dx, dz = map(int, m)
                a = areas[pid]
                assert a[0] <= bx and bx + dx <= a[2] + 1 and a[1] <= bz and bz + dz <= a[3] + 1, (rel, m)


def test_player_commands_only_in_named_owner_steps(files):
    for (pid, name), lines in functions(files).items():
        for line in lines:
            if line.startswith("#") or not PLAYER_CMD.search(line):
                continue
            assert (pid, name) in PLAYER_COMMANDS or ("*", name) in PLAYER_COMMANDS, (pid, name, line[:100])


def test_summoning_functions_wait_for_ready(files):
    """Look before acting (review N155): every owner or RCON entry that summons or spawns refuses until ready."""
    fns = functions(files)
    spawners = {k for k, lines in fns.items() if any(
        re.search(r"(summon |spawn_at |npc_at |spawnnpcat )", l) for l in lines if not l.startswith("#"))}
    entries = {k for k in spawners if k[1] not in ("spawn_at", "npc_at") and not re.match(r"spawn_\d", k[1])
               and k[1] not in ("spawn_stage",)}
    for k in entries:
        lines = fns[k]
        assert any("matches 1 run return 0" in l and "#ready" in l for l in lines), k


def test_macro_lines(files):
    for (pid, name), lines in functions(files).items():
        for line in lines:
            if line.startswith("$"):
                assert "$(" in line, (pid, name, line)


def test_staging_only_never_installed():
    """The pack must not enter the players' pack or the re-apply's install lists."""
    reapply = (ROOT / "tools" / "reapply.py").read_text(encoding="utf-8")
    assert "cobblers_dg_probes" not in reapply and "dungeon_probes" not in reapply
    for p in (ROOT / "modpack").rglob("*"):
        if p.is_file() and p.suffix in (".json", ".toml", ".txt", ".md", ".json5", ".yaml", ".yml"):
            assert "cobblers_dg_probes" not in p.read_text(encoding="utf-8", errors="ignore"), p


def test_build_is_deterministic():
    assert D.build(DOC) == D.build(DOC)

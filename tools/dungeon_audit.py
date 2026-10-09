#!/usr/bin/env python
"""Independent audit of the dungeon engine pack and the blackout's run-tag half (E1), read from the GENERATED packs.

Written by the test author, not by either builder (CLAUDE.md principle 16; "How to prove an audit is independent").
Every check reads the generated functions of cobblers_dungeons (tools/dungeon.py) and of the blackout pack
(tools/blackout_pack.py), and takes its expectation from somewhere else: DUNGEONS.md (the rates, the credit window, the
clock table), the other pocket users' own data or generated packs (the rescue box, Entei's sweep, the probe row), the
world border in data/entei_boss.json, EXP-083 (the sigil's byte form) and CobbleDollars' config. Nothing here calls
tools/dungeon.py's problems(), points(), foreign_boxes() or slots().

  python tools/dungeon_audit.py              # every static check; exit 1 on a problem
  python tools/dungeon_audit.py --payout     # also the boss stages' NPC payout per band (a finding, not a check)

Checks (DUNGEONS.md 11.4 and 2.5-2.6):
  V15     the run tag (E1): data, who removes it, the pocket guard on the tail end and backstop, the tag added at the
          click before the arrival, the blackout's player-side tests, every engine spawn tagged in its own function
  timer   no gametime, no `damage`, the timer's kill is `kill @s` behind the battle guard and the clawback
  V1      slots inside the border margin, disjoint from each other, the portals' rescue box, Entei's sweep and the
          probe row; the engine's own eject sweep covers none of those either
  V12     the lockout is at least the longest clock and counts the uptime counter
  C1      every spawnnpcat is a macro line and names a class the pack ships
  sigils  every sigil predicate, give and clear uses the byte form; the owner switches are OPEN, not decided

What this does NOT cover: anything at runtime. The simulated behaviour (clock per pass, sudden death, logout, every exit
path, the tail's length, the combined death-and-claim case) is tests/test_dungeon_audit.py on tests/pocket_sim.py; the
in-game proof is EXP-084 and DX1. Validity is not behaviour (.claude/rules/testing.md).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

DUNGEONS_MD = ROOT / "docs" / "mechanics" / "DUNGEONS.md"
BLACKOUT_JSON = ROOT / "data" / "blackout.json"
DUNGEONS_JSON = ROOT / "data" / "dungeons.json"
PORTALS_JSON = ROOT / "data" / "portals.json"
ENTEI_JSON = ROOT / "data" / "entei_boss.json"
PROBES_JSON = ROOT / "data" / "dungeon_probes.json"
CD_CONFIG = ROOT / "modpack" / "config" / "cobbledollars" / "common.json"

# DUNGEONS.md 11.3 E1 item 3: "the tag outlives the run by a tail of 100 ticks (tail_ticks, equal to the credit window)"
CREDIT_WINDOW_TICKS = 100
# DUNGEONS.md 11.3 E1 item 1: "added by door_click ... before the 40-tick arrival delay"
ARRIVAL_DELAY_TICKS = 40
# DUNGEONS.md 2.1: "The rates are 4 (x1), 5 (x1.25), 6 (x1.5), 8 (x2) and 12 (x3)"; a minute is 4,800 units
DESIGN_RATES = (4, 5, 6, 8, 12)
UNITS_PER_TICK = 4

POCKET = "cobblers:pocket"
FN_RE = re.compile(r"^data/([^/]+)/function/(.+)\.mcfunction$")
CALL_RE = re.compile(r"\bfunction ([a-z0-9_.\-]+:[a-z0-9_./\-]+)")
BOX_RE = re.compile(r"x=(-?\d+),y=(-?\d+),z=(-?\d+),dx=(\d+),dy=(\d+),dz=(\d+)")


# ------------------------------------------------------------------------------------------------- the packs


def _j(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dungeon_files(module=None):
    """The dungeon pack as tools/dungeon.py builds it ({relpath: text}); `module` is a (mutated) copy of the generator."""
    if module is None:
        import dungeon as module
    return module.build(module.load())


def blackout_files(module=None):
    if module is None:
        import blackout_pack as module
    cfg = _j(BLACKOUT_JSON)
    return module.build(cfg, _j(ROOT / "data" / "water_mounts.json"), _j(ROOT / "data" / "placements.json"),
                        _j(ROOT / "data" / "progression.json"), None)


def functions(files):
    """{"ns:path": [lines]} for every .mcfunction in a pack."""
    out = {}
    for rel, text in files.items():
        m = FN_RE.match(rel)
        if m:
            out["%s:%s" % (m.group(1), m.group(2))] = text.splitlines()
    return out


def body(lines):
    return [l for l in lines if l.strip() and not l.lstrip().startswith("#")]


def calls(line):
    return CALL_RE.findall(line)


def reach(fns, start):
    """Every function reachable from `start` by `function` calls (any line, conditional or not)."""
    seen, todo = set(), [start]
    while todo:
        f = todo.pop()
        if f in seen or f not in fns:
            continue
        seen.add(f)
        for l in body(fns[f]):
            todo.extend(calls(l))
    return seen


def callers(fns, target):
    return sorted({f for f, ls in fns.items() for l in body(ls) if target in calls(l)})


def blackout_terms():
    b = _j(BLACKOUT_JSON)
    ex = b.get("dungeon_exempt") or {}
    return {"tag": ex.get("player_tag"), "tail": ex.get("tail_ticks"), "tail_end": ex.get("tail_end_function"),
            "backstop": ex.get("backstop_function"), "exempt": (b.get("claims") or {}).get("exempt_tag")}


def pocket_marker(fns):
    """The tag the keeper puts on every player in the pocket: `execute in <pocket> run tag @a[...] add <T>`."""
    for f, ls in fns.items():
        for l in body(ls):
            m = re.fullmatch(r"execute in %s run tag @a\[distance=0\.\.\] add (\S+)" % re.escape(POCKET), l)
            if m:
                return f, m.group(1)
    return None, None


# ------------------------------------------------------------------------------------------------- V15 / E1


def spawn_helpers(fns):
    """Functions that hold a spawnnpcat / spawnpokemonat line themselves."""
    return sorted(f for f, ls in fns.items() if any(re.search(r"\b(spawnnpcat|spawnpokemonat)\b", l) for l in body(ls)))


def spawn_sites(fns):
    """[(the function that spawns, the helper it spawns through or itself)]: a macro helper's callers are the sites."""
    out = []
    for h in spawn_helpers(fns):
        cs = callers(fns, h)
        out.extend((c, h) for c in cs) if cs else out.append((h, h))
    return out


def check_v15(dg_files, bo_files):
    """The run tag's static half. The behaviour (death, tail, delivery) is the test's."""
    bad = []
    bt = blackout_terms()
    tag, tail, tail_end, backstop, exempt = bt["tag"], bt["tail"], bt["tail_end"], bt["backstop"], bt["exempt"]
    if not tag or not tail_end or not backstop or not exempt:
        return ["data/blackout.json: dungeon_exempt or claims.exempt_tag incomplete: %r" % bt]
    if not isinstance(tail, int) or tail < CREDIT_WINDOW_TICKS:
        bad.append("data/blackout.json dungeon_exempt.tail_ticks %r is below the credit window, %d ticks "
                   "(DUNGEONS.md 11.3 E1 item 3)" % (tail, CREDIT_WINDOW_TICKS))
    dg, bo = functions(dg_files), functions(bo_files)
    both = dict(bo)
    both.update(dg)
    if len(both) != len(dg) + len(bo):
        bad.append("the two packs define the same function: %s" % sorted(set(dg) & set(bo)))

    # removers: only the blackout's tail end removes the tag, and only the backstop calls it besides the engine
    removers = sorted({f for f, ls in both.items() for l in body(ls)
                       if re.search(r"\btag \S+ remove %s\b" % re.escape(tag), l)})
    if removers != [tail_end]:
        bad.append("the run tag is removed by %s; only %s may (V15)" % (removers, tail_end))
    bo_callers = sorted(set(callers(bo, tail_end)) | set(callers(bo, backstop)))
    if bo_callers != [backstop]:
        bad.append("in the blackout pack the tail end / backstop are called by %s; only the backstop may call the "
                   "tail end" % bo_callers)
    for t in (tail_end, backstop):
        if not callers(dg, t):
            bad.append("the dungeon pack never calls %s" % t)

    # the pocket guard: every engine call of the tail end or the backstop is behind the keeper's pocket marker
    mf, marker = pocket_marker(dg)
    if not marker:
        bad.append("the keeper marks no player in %s, so nothing can keep the tail end out of the pocket" % POCKET)
    else:
        for f in sorted(set(callers(dg, tail_end)) | set(callers(dg, backstop))):
            ls = body(dg[f])
            for i, l in enumerate(ls):
                if tail_end not in calls(l) and backstop not in calls(l):
                    continue
                guarded = ("tag=!%s" % marker) in l or any(
                    re.fullmatch(r"execute if entity @s\[tag=%s\] run return( run .*| \d+)" % re.escape(marker), p)
                    for p in ls[:i])
                if not guarded:
                    bad.append("%s calls %s with no pocket guard (tag %s): %s" % (f, calls(l), marker, l))
            # and the marker is set before the keeper reaches this function
            if f != mf and mf in dg:
                kl = body(dg[mf])
                mark_at = next(i for i, l in enumerate(kl) if ("add %s" % marker) in l)
                for i, l in enumerate(kl):
                    if any(f == c or f in reach(dg, c) for c in calls(l)) and i < mark_at:
                        bad.append("%s reaches %s before it marks the pocket" % (mf, f))

    # the tag is added on the click (an advancement's reward), in the function that reserves the slot, and the
    # teleport into the pocket is NOT reachable from the click: the arrival waits for the keeper
    adders = sorted(f for f, ls in dg.items() for l in body(ls) if l == "tag @s add %s" % tag)
    if not adders:
        bad.append("no dungeon function adds the run tag")
    rewards = {}
    for rel, text in dg_files.items():
        if re.match(r"data/[^/]+/advancement/", rel):
            fn = (json.loads(text).get("rewards") or {}).get("function")
            if fn:
                rewards[rel] = fn
    reserve = {f for f, ls in dg.items() for l in body(ls) if re.fullmatch(r"scoreboard players operation #\S+ dg\.own = @s \S+", l)}
    keeper = mf
    for f in adders:
        clicks = [r for r, fn in rewards.items() if f in reach(dg, fn)]
        if not clicks:
            bad.append("%s adds the run tag but no click advancement reaches it" % f)
        ls = body(dg[f])
        res =[i for i, l in enumerate(ls) if any(c in reserve for c in calls(l))]
        if not res or not reserve:
            bad.append("%s adds the run tag but does not reserve a slot (V15: in the function that reserves it)" % f)
        if keeper and f in reach(dg, keeper):
            bad.append("%s (the run tag) is reachable from the keeper: the tag must be added at the click" % f)
        for r, fn in rewards.items():
            if f in reach(dg, fn):
                into = [g for g in reach(dg, fn) for l in body(dg[g])
                        if re.search(r"execute in %s run tp @s" % re.escape(POCKET), l)]
                if into:
                    bad.append("the click %s teleports into the pocket in the same tick (%s): no arrival delay" % (r, into))

    # the blackout's player-side tests (E1 items 2 and 4); none in battle_loss_npc (DUNGEON_DEATH.md 4 rule 3)
    ns = tail_end.split(":")[0]
    player_test = "execute if entity @s[tag=%s] run " % tag
    wild = body(bo.get("%s:blackout/battle_loss_wild" % ns, []))
    t_at = [i for i, l in enumerate(wild) if l == player_test + "scoreboard players set #exempt bo.tmp 1"]
    make_at = [i for i, l in enumerate(wild) if "%s:recovery/make" % ns in calls(l)]
    if not t_at or not make_at or min(t_at) > min(make_at):
        bad.append("blackout/battle_loss_wild does not exempt a tagged player before it calls recovery/make")
    for f in ("recovery/make", "recovery/deliver"):
        ls = body(bo.get("%s:%s" % (ns, f), []))
        if not ls or ls[0] != player_test + "return 0":
            bad.append("%s's first command is not the run-tag return: %r" % (f, ls[:1]))
    if "%s:recovery/deliver" % ns not in reach(bo, "%s:blackout/login" % ns):
        bad.append("the login delivery does not go through recovery/deliver")
    chain = {"%s:recovery/%s" % (ns, n) for n in ("deliver", "deliver_next", "deliver_one")}
    for inner in sorted(chain - {"%s:recovery/deliver" % ns}):
        stray = sorted(set(callers(bo, inner)) - chain)
        if stray:
            bad.append("%s is called by %s, around recovery/deliver's guard" % (inner, stray))
    if any(tag in l for l in body(bo.get("%s:blackout/battle_loss_npc" % ns, []))):
        bad.append("blackout/battle_loss_npc reads the run tag; a trainer loss takes no items and must not")

    # every engine spawn site tags its entity with claims.exempt_tag in the SAME function (not a pass later)
    for site, helper in spawn_sites(dg):
        ls = body(dg[site])
        spawn_at = [i for i, l in enumerate(ls) if helper in calls(l) or (site == helper and re.search(r"spawn(npc|pokemon)at", l))]
        later = ls[max(spawn_at) + 1:] if spawn_at else []
        tags = any("tag @s add %s" % exempt in [x for g in reach(dg, c) for x in body(dg[g])] for l in later
                   if l.startswith("execute ") and " as @e[" in l for c in calls(l)) \
            or any(re.search(r"\btag @e\[[^\]]*\] add %s\b" % re.escape(exempt), l) for l in later)
        if not tags:
            bad.append("%s spawns through %s and does not tag the spawned entity %s in the same function (V15)"
                       % (site, helper, exempt))
    return bad


# ------------------------------------------------------------------------------------------------- the timer


def check_timer(dg_files):
    bad = []
    dg = functions(dg_files)
    for f, ls in sorted(dg.items()):
        for l in body(ls):
            if "gametime" in l or re.search(r"\btime query\b", l):
                bad.append("%s reads game time (DUNGEONS.md 2.1: nothing compares against gametime): %s" % (f, l))
            if re.search(r"(^|\brun )damage\b", l):
                bad.append("%s uses `damage` (B2: a totem stops it; the kill is `kill`): %s" % (f, l))
    killers = sorted(f for f, ls in dg.items() for l in body(ls) if re.search(r"(^|\brun )kill @s$", l))
    if not killers:
        bad.append("no function kills a player with `kill @s` (the timer's kill)")
    # the timer's kill: reached only through a runmolang that tests q.player.in_battle == 0, and it returns while the
    # clawback is measuring before the kill (E1 item 6)
    claw = "dg.claw"
    timer = [f for f in killers if any(re.search(r"scoreboard players set @s dg\.cause 1$", l) for l in body(dg[f]))]
    if len(timer) != 1:
        bad.append("expected exactly one timer kill (cause 1), found %s" % timer)
    for f in timer:
        ls = body(dg[f])
        kill = ls.index("kill @s")
        if not any(re.fullmatch(r"execute if score @s %s matches 1\.\. run return 0" % re.escape(claw), l) for l in ls[:kill]):
            bad.append("%s kills without waiting for the clawback (%s >= 1)" % (f, claw))
        for c in callers(dg, f):
            for l in body(dg[c]):
                if f in calls(l) and not ("runmolang" in l and "q.player.in_battle == 0" in l):
                    bad.append("%s calls the timer kill %s outside the in_battle guard: %s" % (c, f, l))
    return bad


# ------------------------------------------------------------------------------------------------- V1 / V12


def _rect(xs, zs):
    return (min(xs), min(zs), max(xs), max(zs))


def _meet(a, b):
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def _box_rect(m):
    x, _y, z, dx, _dy, dz = (int(v) for v in m.groups())
    return (x, z, x + dx, z + dz)


def slot_footprints(dg_files):
    """{slot number: (x0, z0, x1, z1)}: every block a slot's functions write (fill, setblock) and its presence box,
    read from the generated text. A slot's functions are those whose path holds the segment s<g>."""
    dg = functions(dg_files)
    pts = {}
    for f, ls in dg.items():
        m = re.search(r"/s(\d+)(/|$)", f)
        if not m or "/rips/" in f:
            continue
        g = int(m.group(1))
        for l in body(ls):
            t = l.split()
            if t[0] == "fill":
                pts.setdefault(g, []).extend([(int(t[1]), int(t[3])), (int(t[4]), int(t[6]))])
            elif t[0] == "setblock":
                pts.setdefault(g, []).append((int(t[1]), int(t[3])))
    for f, ls in dg.items():
        for l in body(ls):
            m = re.search(r"if score @s dg\.slot matches (\d+) .*if entity @s\[(x=-?\d+,y=-?\d+,z=-?\d+,dx=\d+,dy=\d+,dz=\d+)\]", l)
            if m:
                r = _box_rect(BOX_RE.search(m.group(2)))
                pts.setdefault(int(m.group(1)), []).extend([(r[0], r[1]), (r[2], r[3])])
    return {g: _rect([p[0] for p in v], [p[1] for p in v]) for g, v in pts.items()}


def engine_sweeps(dg_files):
    """The engine's own sweeps in the pocket: `execute in <pocket> as @e|@a[...box...]` in the keeper."""
    out = []
    for f, ls in functions(dg_files).items():
        for l in body(ls):
            m = re.match(r"execute in %s as @[ae]\[[^\]]*?(x=-?\d+,y=-?\d+,z=-?\d+,dx=\d+,dy=\d+,dz=\d+)" % re.escape(POCKET), l)
            if m and "type=minecraft:player" in l:
                out.append((f, _box_rect(BOX_RE.search(m.group(1)))))
    return out


def foreign(entei_files=None):
    """{name: (x0, z0, x1, z1)} of every other pocket user, each from its own data or generated pack."""
    out = {}
    p = _j(PORTALS_JSON)
    pk, gen = p["pocket"], p["pocket"]["generator"]
    per_gate = len(p["portals"]) // len(p["gates"])
    xs = [pk["origin_x"] + i * pk["spacing"] for i in range(per_gate)]
    zs = list(pk["bands"].values())
    m = pk["rescue_margin"]
    out["the portals' rescue sweep"] = (min(xs) - m, min(zs) - m, max(xs) + m, max(zs) + m)
    if entei_files is None:
        import entei_boss as E
        entei_files = E.build(E.load())
    boxes = []
    for f, ls in functions(entei_files).items():
        for l in body(ls):
            mm = re.match(r"execute in %s as @a\[(x=-?\d+,y=-?\d+,z=-?\d+,dx=\d+,dy=\d+,dz=\d+)" % re.escape(POCKET), l)
            if mm:
                boxes.append(_box_rect(BOX_RE.search(mm.group(1))))
    if boxes:
        out["Entei's keeper sweep"] = _rect([b[0] for b in boxes] + [b[2] for b in boxes],
                                            [b[1] for b in boxes] + [b[3] for b in boxes])
    r = _j(PROBES_JSON)["row"]
    out["the probe pack's row"] = (-10 ** 7, r["z_min"], 10 ** 7, r["z_max"])
    return out


def check_v1(dg_files, entei_files=None):
    bad = []
    e = _j(ENTEI_JSON)["pocket"]
    lo, hi = e["border"][0] + e["border_margin"], e["border"][1] - e["border_margin"]
    fp = slot_footprints(dg_files)
    if not fp:
        return ["no slot footprint could be read from the generated pack"]
    for g, r in sorted(fp.items()):
        if not (lo <= r[0] and r[2] <= hi and lo <= r[1] and r[3] <= hi):
            bad.append("slot %d %s leaves the border margin [%d, %d]" % (g, r, lo, hi))
    gs = sorted(fp)
    for i, a in enumerate(gs):
        for b in gs[i + 1:]:
            if _meet(fp[a], fp[b]):
                bad.append("slots %d %s and %d %s overlap" % (a, fp[a], b, fp[b]))
    fo = foreign(entei_files)
    if "Entei's keeper sweep" not in fo:
        bad.append("Entei's generated pack has no keeper sweep box to compare with")
    for name, box in fo.items():
        for g, r in sorted(fp.items()):
            if _meet(r, box):
                bad.append("slot %d %s meets %s %s" % (g, r, name, box))
        for f, sw in engine_sweeps(dg_files):
            if _meet(sw, box):
                bad.append("the engine's sweep in %s %s covers %s %s: it would put their players out" % (f, sw, name, box))
    return bad


def clocks_units(dg_files):
    """Every band's starting clock as the generated threshold functions set it (quarter-ticks)."""
    return sorted({int(m.group(1)) for ls in functions(dg_files).values() for l in body(ls)
                   for m in [re.search(r"if score @s dg\.band matches \d+ run scoreboard players set @s dg\.clock (\d+)$", l)] if m})


def design_clock_minutes():
    """DUNGEONS.md 4.2's table: the bold Clock column, in band order."""
    out, col = [], None
    for l in DUNGEONS_MD.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in l.strip().strip("|").split("|")]
        if "**Clock**" in cells and "**Required**" in cells:
            col = cells.index("**Clock**")
            continue
        if col is None:
            continue
        if not l.startswith("|"):
            break
        m = re.match(r"(\d) \(", cells[0])
        if m:
            out.append((int(m.group(1)), int(cells[col].strip("*"))))
    return [c for _b, c in sorted(out)]


def check_v12(dg_files):
    bad = []
    dg = functions(dg_files)
    clocks = clocks_units(dg_files)
    if not clocks:
        return ["no band clock found in the generated pack"]
    want = [m * 60 * 20 * UNITS_PER_TICK for m in design_clock_minutes()]
    if sorted(want) != clocks:
        bad.append("the generated clocks %s are not DUNGEONS.md 4.2's %s (units)" % (clocks, sorted(want)))
    longest = max(clocks) // UNITS_PER_TICK
    locks = []
    for f, ls in dg.items():
        for l in body(ls):
            m = re.fullmatch(r"execute if score #why dg\.t matches 0 if score #d dg\.t matches 0\.\.(\d+) run .*", l)
            if m:
                locks.append((f, int(m.group(1)) + 1, ls))
    if not locks:
        bad.append("no lockout test found in any door function")
    for f, n, ls in locks:
        if n < longest:
            bad.append("%s locks out for %d ticks, under the longest clock %d (V12)" % (f, n, longest))
        b = body(ls)
        if "execute if score @s dg.lk_%s matches -2147483648.. run scoreboard players operation #d dg.t = #up dg.up" % f.rsplit("/", 1)[1] not in b:
            bad.append("%s does not measure the lockout on the uptime counter #up" % f)
    stamps = [(f, l) for f, ls in dg.items() for l in body(ls) if re.fullmatch(r"scoreboard players operation @s dg\.lk_\w+ = (\S+) (\S+)", l)]
    if not stamps or any(not l.endswith("= #up dg.up") for _f, l in stamps):
        bad.append("the lockout stamp is not the uptime counter: %s" % stamps)
    keeper = [(f, body(ls)) for f, ls in dg.items() if f.endswith("/keeper")]
    for f, b in keeper:
        step = [int(m.group(1)) for l in b for m in [re.fullmatch(r"scoreboard players add #up dg\.up (\d+)", l)] if m]
        again = [int(m.group(1)) for l in b for m in [re.fullmatch(r"schedule function %s (\d+)t replace" % re.escape(f), l)] if m]
        if not step or step != again:
            bad.append("%s adds %s to #up a pass but re-schedules every %s ticks: #up would not count ticks" % (f, step, again))
    return bad


# ------------------------------------------------------------------------------------------------- C1, sigils


def check_c1(dg_files):
    bad = []
    dg = functions(dg_files)
    classes = {"%s:%s" % (m.group(1), m.group(2)) for rel in dg_files
               for m in [re.match(r"data/([^/]+)/npcs/(.+)\.json$", rel)] if m}
    for f, ls in dg.items():
        for l in body(ls):
            if re.search(r"\bspawnnpcat\b", l) and not l.startswith("$"):
                bad.append("%s: spawnnpcat on a plain line fails to parse at load (EXP-078): %s" % (f, l))
            for h in spawn_helpers(dg):
                if h in calls(l):
                    m = re.search(r'cls:"([^"]+)"', l)
                    if m and m.group(1) not in classes:
                        bad.append("%s spawns %s, which the pack does not ship" % (f, m.group(1)))
    return bad


def check_sigils(dg_files, doc=None):
    bad = []
    doc = doc if doc is not None else _j(DUNGEONS_JSON)
    key = "cobblers_dg_sigil"
    seen = 0
    for f, ls in functions(dg_files).items():
        for l in body(ls):
            for m in re.finditer(r"%s:([0-9]+)([a-zA-Z]?)\}" % key, l):
                seen += 1
                if m.group(2) != "b":
                    bad.append("%s names the sigil as %s:%s%s, not the byte form a crafted sigil holds (EXP-083)"
                               % (f, key, m.group(1), m.group(2)))
    if not seen:
        bad.append("no function names %s" % key)
    for rel, text in dg_files.items():
        if re.match(r"data/[^/]+/recipe/", rel) and key in text:
            v = json.loads(text)["result"]["components"]["minecraft:custom_data"][key]
            if not isinstance(v, int) or isinstance(v, bool):
                bad.append("%s's result %s is %r; EXP-083 crafted a JSON number as a byte" % (rel, key, v))
    sg = doc["engine"]["sigils"]
    md = DUNGEONS_MD.read_text(encoding="utf-8")
    for sw, q in (("free_first_entry", 20), ("recipe_gate", 23)):
        rec = sg.get(sw) or {}
        if "OPEN" not in str(rec.get("owner_decision")) or "NOT A DECISION" not in str(rec.get("staging_value")):
            bad.append("data/dungeons.json sigils.%s is not marked an OPEN owner decision: %r" % (sw, rec.get("owner_decision")))
        if not re.search(r"^%d\. \*\*OPEN" % q, md, re.M):
            bad.append("DUNGEONS.md Q%d is no longer OPEN: re-read the switch %s" % (q, sw))
    return bad


# ------------------------------------------------------------------------------------------------- the payout


def boss_payouts(dg_files, cd=None):
    """{band: (least, most) CobbleDollars credited for the run's boss stages together}, from each stage class's party
    and CobbleDollars' battleVictory arithmetic (docs/research/notes/paid-services-and-npc-payouts.md B2, VERIFIED
    bytecode there; nextBetween inclusive ASSUMED): B = int(5 * S * sum(L / 50)), amount = B + [B/2, 2B],
    credit = floor(amount * multiplier). None when CobbleDollars pays no NPC win."""
    cd = cd if cd is not None else _j(CD_CONFIG)
    if not cd.get("earnCobbleDollarsFromNPC"):
        return None
    mult = cd["cobbleDollarsIncomeMultiplier"]
    per = {}
    for rel, text in dg_files.items():
        m = re.match(r"data/[^/]+/npcs/dg_\w+_boss_b(\d+)_s(\d+)\.json$", rel)
        if not m:
            continue
        party = json.loads(text)["party"]["pokemon"]
        levels = [int(re.search(r"level=(\d+)", p).group(1)) for p in party]
        s = sum(levels)
        b = max(1, int(5 * s * sum(L / 50.0 for L in levels)))
        lo, hi = int((b + b // 2) * mult), int((b + 2 * b) * mult)
        a = per.setdefault(int(m.group(1)), [0, 0])
        a[0] += lo
        a[1] += hi
    return {k: tuple(v) for k, v in sorted(per.items())}


CHECKS = {"V15": lambda dg, bo, en: check_v15(dg, bo), "timer": lambda dg, bo, en: check_timer(dg),
          "V1": lambda dg, bo, en: check_v1(dg, en), "V12": lambda dg, bo, en: check_v12(dg),
          "C1": lambda dg, bo, en: check_c1(dg), "sigils": lambda dg, bo, en: check_sigils(dg)}


def run(dg=None, bo=None, en=None):
    dg = dg if dg is not None else dungeon_files()
    bo = bo if bo is not None else blackout_files()
    return {k: f(dg, bo, en) for k, f in CHECKS.items()}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--payout", action="store_true", help="also print the boss stages' NPC payout per band")
    a = p.parse_args(argv)
    dg = dungeon_files()
    res = run(dg)
    n = 0
    for k, probs in res.items():
        print("%-7s %s" % (k, "ok" if not probs else "%d problem(s)" % len(probs)))
        for x in probs:
            print("   PROBLEM %s" % x)
        n += len(probs)
    if a.payout:
        pay = boss_payouts(dg)
        for band, (lo, hi) in (pay or {}).items():
            print("payout  band %d: the three boss stages credit $%d-$%d a run (not clawed back: step 6)" % (band, lo, hi))
    print("dungeon_audit: %d problem(s)" % n)
    return 1 if n else 0


if __name__ == "__main__":
    raise SystemExit(main())

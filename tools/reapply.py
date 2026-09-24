#!/usr/bin/env python
"""The re-application after an export, as one supervised run: regenerate, install, run every step in order over RCON
with a check after each, and audit the result. docs/world-building/REEXPORT.md is the procedure; this runs it.

  python tools/reapply.py carry --old-world <retired old world copy> --world-dir <fresh export>
        with the server STOPPED, before the new world's first boot: every player's state (tools/carry_players.py),
        checked file by file by sha256 and player by player; install refuses a world with no player carried
  python tools/reapply.py prepare --source-root <root> --server-dir <server>
        regenerate every function and pack from the heightmap and committed data (server not needed), assemble the
        loose functions into build/datapacks/cobblers_reapply, and refuse to go on if any function would be refused
  python tools/reapply.py install --server-dir <server> --world-dir <world folder>
        with the server STOPPED: copy the packs into <server>/datapacks, and cobblers_height and cobblers_worldtree
        into the world folder's own datapacks (they raise the build limit the world tree's crown needs)
  python tools/reapply.py run --server-dir <server> [--from R8] [--only R8] [--with-spawns]
        with the server running and the coordination lock held: R2 to R16 in order, timed, each function's reply
        checked, the checkpoints below enforced; writes derived/reapply/run_<time>.json
  python tools/reapply.py audit --server-dir <server> --world <stopped world copy>
        with the server STOPPED: build_audit (cavern, forest, world tree, islet), town_audit for every place, the
        signposts, and the light check (tools/light_plan.py: nothing walkable under a roof or in the cavern at block
        light 0); writes derived/reapply/audit_<time>.json and exits non-zero on any mismatch

R16 runs each place's after-donor function (its lights, the cavern fields' crops) after the pack donors (R9), which
are placed whole and would erase them.

The order differs from the table in one place: the islet (R10) runs before the towns, because Relic Island's house
stands on it. The Displaced City comes after the cavern (R2) for the same reason.

Checkpoints that stop a run: a function that does not answer "Running function"; the world tree's crown block
missing after R3 (cobblers_height is not in the world folder); a floor verify with any gap; a trader verify with any
problem. Everything else is found by `audit`, which reads the saved world and compares it with what each step
should have built.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))
import runtime_guard  # noqa: E402
BUILD = ROOT / "build"
PACKS = BUILD / "datapacks"
REAPPLY = PACKS / "cobblers_reapply"
OUT = ROOT / "derived" / "reapply"
SERVER_PACKS = ("cobblers_cavern", "cobblers_route1", "cobblers_towns", "cobblers_donor", "cobblers_vendors", "cobblers_reapply",
                "cobblers_signs", "cobblers_titles", "cobblers_progression",
                # the Rift. Every one of these was hand-applied to the staging world and had no step here at
                # all until 2026-09-23, so a re-export would have erased all five silently (see EXCLUDED).
                "cobblers_rift", "cobblers_rift_biome", "cobblers_league_tunnel", "cobblers_deep",
                "cobblers_victory_road",
                # Victory Road's regions, their Habitat Blocks and their finds (2026-09-23)
                "cobblers_vr_regions", "cobblers_habitats", "cobblers_rewards",
                # the NPC classes and dialogues the placed NPCs use; no functions (see npcs())
                "cobblers_dialogue")

# Packs that ship functions and deliberately have NO step, each with the reason. Anything not here and not run
# by a step makes `prepare` fail: that is the fail-closed check.
EXCLUDED = {
    "cobblers_reapply": "the loose-function container; its functions are run by the steps that own them",
    "cobblers_vr_backfill": "staging only: it buries schema 1's labyrinth, which a fresh export never has",
    "cobblers_restore": "disposable worlds only; install() deletes it if it is found",
    "cobblers_rift_fracture": "retired, replaced by the sculpt in the heightmap",
    "cobblers_worldtree": "a WORLD pack, installed into the world folder and run by R3",
    "cobblers_height": "a WORLD pack: it raises the build limit and runs nothing",
    "cobblers_suppress": "generated from the installed set on a disposable world; not part of a re-export",
    # these three drive themselves and write no blocks: found by the check below the moment it was added
    "cobblers_progression": "self-driving: its own minecraft load and tick tags run it",
    "cobblers_sizes": "self-driving: its own minecraft load tag runs it",
    "cobblers_titles": "event functions (enter_place_*), fired on entering a place, not applied to the world",
    "cobblers_rewards": "self-driving: each find is an advancement that runs its own reward function as the player "
                        "who earns it; it writes no blocks (the containers are placed by R9D)",
}
WORLD_PACKS = (ROOT / "modpack" / "datapacks" / "cobblers_height", PACKS / "cobblers_worldtree")
CROWN = (2044, 535, 2282)                      # the world tree's highest block (tools/build_audit.py world_tree)
CAVERN = ["00_seal", "02_shell", "05_reset", "10_excavate", "20_surfaces", "30_trees", "40_light", "50_tunnel", "70_drain", "15_cap", "60_biome"]
UNPLACED = {"hometown"}                          # has roads, not a town plan: placed by R7


def placements():
    return json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))


def npcs():
    """[(conversation id, (x, y, z), npc class)] for every NPC a reward is given through (data/rewards.json npc_grant).

    An NPC is an entity, so an export erases it like a block. It cannot be put back by a function: NPC classes load
    only at server start, after functions are parsed, so a function naming the class fails to load
    (tools/compile_dialogue.py). The class ships in cobblers_dialogue, installed before boot, and the NPC is placed by
    a raw spawnnpcat over RCON in step R9F."""
    rw = json.loads((ROOT / "data" / "rewards.json").read_text(encoding="utf-8"))
    dl = json.loads((ROOT / "data" / "dialogue.json").read_text(encoding="utf-8"))
    out = []
    for r in rw.get("rewards") or []:
        if r.get("kind") != "npc_grant":
            continue
        conv = next((c for c in dl["conversations"] if c.get("quest_id") == r["quest"]), None)
        if conv is None:
            raise SystemExit("reward %s names quest %s, and no conversation in data/dialogue.json runs it" % (r["id"], r["quest"]))
        out.append((conv["id"], tuple(r["npc_at"]), "cobblers:%s" % conv["npc_id"]))
    return out


def places(doc=None):
    """Every planned place, in build order: the Displaced City and Relic Island last, after their ground exists."""
    doc = doc or placements()
    ids = [s for s, v in doc["settlements"].items() if s not in UNPLACED and (v.get("plan") or {}).get("streets")]
    late = [s for s in ("relic_island", "displaced_city") if s in ids]
    return [s for s in ids if s not in late] + late


def donors(doc=None):
    doc = doc or placements()
    return [q["id"] for q in doc["placements"] if q.get("pack_template") and q.get("kind") != "vendor"]


def py(*args, cwd=ROOT):
    print("  $ python %s" % " ".join(str(a) for a in args), flush=True)
    r = subprocess.run([sys.executable] + [str(a) for a in args], cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        print(r.stdout[-2000:], r.stderr[-3000:])
        raise SystemExit("failed: %s" % " ".join(str(a) for a in args[:2]))
    return r.stdout


def prepare(a):
    src = ["--source-root", a.source_root]
    t0 = time.time()
    py(TOOLS / "critical_legs.py", *src)
    py(TOOLS / "cavern_plan.py", *src)
    py(TOOLS / "world_tree.py", *src)
    py(TOOLS / "tree_grove.py", *src, "--site", "2016,2272", "--id", "foothill_woods")
    py(TOOLS / "tree_grove.py", *src, "--augment", "foothill_woods")
    py(TOOLS / "elder_trees.py", *src)
    py(TOOLS / "maze_forest.py", *src)
    py(TOOLS / "islet.py", *src)
    # the Rift, in the order the world needs it: the skin lies over the sculpted shape, the biome is painted
    # on top of it, the League's lot is levelled before the donor stamps the building on it, the Deep is sunk
    # into the Rift floor, and Victory Road runs from the Deep to the League's apron and so needs both.
    py(TOOLS / "rift_skin.py", *src)
    py(TOOLS / "rift_league_tunnel.py", *src)
    py(TOOLS / "rift_deep.py", *src)
    py(TOOLS / "victory_road.py", *src)
    # the regions read the road's plan (derived/victory_road/plan.json), so they come after it; their Habitat
    # Blocks and their finds are data the region build checks against its own model
    py(TOOLS / "vr_regions.py", "build", *src)
    py(TOOLS / "habitat_blocks.py", "function")
    py(TOOLS / "rewards_pack.py")
    dlg = PACKS / "cobblers_dialogue"
    if dlg.exists():
        shutil.rmtree(dlg)
    for conv, _at, _cls in npcs():
        py(TOOLS / "compile_dialogue.py", conv, "--out", dlg)
    py(TOOLS / "rematerial.py")
    py(TOOLS / "place_town.py", "hometown", *src)
    for s in places():
        py(TOOLS / "town_plan.py", s, *src)
        py(TOOLS / "place_town.py", s, *src)
    py(TOOLS / "place_donor.py", "function", "--server-dir", a.server_dir)
    py(TOOLS / "traders.py", "function", "--server-dir", a.server_dir)
    py(TOOLS / "signposts.py", "function", *src)
    py(TOOLS / "location_titles.py")
    # the badge flags: one advancement per gym leader and the Champion, set by rctmod on a won battle
    py(TOOLS / "progression_pack.py")
    # the loose functions (town prep, elders, grove, islet) in one pack
    if REAPPLY.exists():
        shutil.rmtree(REAPPLY)
    fn = REAPPLY / "data" / "cobblers" / "function" / "reapply"
    fn.mkdir(parents=True)
    (REAPPLY / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description": "Cobblers: loose re-application functions (tools/reapply.py)"}}) + "\n", encoding="utf-8")
    loose = [(BUILD / "town_prep" / ("prep_%s.mcfunction" % s), "prep_%s" % s) for s in places()]
    loose += [(BUILD / "elders" / "elders.mcfunction", "elders"), (BUILD / "grove" / "grove_foothill_woods.mcfunction", "grove"),
              (BUILD / "grove" / "grove_foothill_woods_augment.mcfunction", "grove_augment"),
              (BUILD / "islet" / "relic_island.mcfunction", "islet")]
    for path, name in loose:
        if not path.is_file():
            raise SystemExit("missing %s" % path)

        shutil.copyfile(path, fn / ("%s.mcfunction" % name))
    out = py(TOOLS / "function_limits.py", *[PACKS / p for p in SERVER_PACKS + ("cobblers_worldtree",)])
    last = out.strip().splitlines()[-1]
    print(last)
    if " 0 with problems" not in last:
        raise SystemExit("function_limits found problems: nothing may be installed until it reports 0")
    # FAIL CLOSED. A generated pack that ships functions and that no step runs is a build a re-export deletes and
    # nothing puts back -- and the run stays green while it happens. That is not hypothetical: the Rift skin, the
    # Rift biome, the Windward Deep, Victory Road and the League's lot were all in exactly that state while this
    # procedure was twice reported as rehearsed end to end. Either a step runs a pack, or EXCLUDED says why not.
    missing = uncovered(steps())
    if missing:
        raise SystemExit("no re-apply step runs these packs, and EXCLUDED does not say why:\n  %s\n"
                         "Add a step in steps(), or add the pack to EXCLUDED with its reason."
                         % "\n  ".join(missing))
    # and every settlement and donor the placements name has to be reachable too, not only the packs
    doc = placements()
    ran = {v for _sid, _title, acts in steps() for kind, v in acts if kind == "fn"}
    for s_ in places(doc):
        if "cobblers:towns/%s" % s_ not in ran:
            raise SystemExit("settlement %r has a plan in data/placements.json but no re-apply step" % s_)
    for d in donors(doc):
        if "cobblers:structures/place_%s" % d not in ran:
            raise SystemExit("donor %r is placed in data/placements.json but no re-apply step stamps it" % d)
    print("prepared in %.0f s: %d places, %d pack donors, %d steps, every function pack covered"
          % (time.time() - t0, len(places()), len(donors()), len(steps())))


def install(a):
    import socket
    s = socket.socket()
    busy = s.connect_ex(("127.0.0.1", 25565)) == 0
    s.close()
    if busy:
        raise SystemExit("port 25565 is in use: install with the server stopped")
    # the port says the server is down; only the lock says nobody else is using the runtime
    dp = runtime_guard.check(Path(a.server_dir) / "datapacks", "install packs into")
    runtime_guard.check(a.world_dir, "install world packs into")
    # the players first: a world nobody has been carried into loses every player's party, flags and progress on the
    # first boot that anyone joins. Only a staging export nobody plays may skip it, and must say so
    import carry_players
    if not carry_players.players(Path(a.world_dir)) and not a.no_players:
        raise SystemExit("no player in %s/playerdata: run `reapply.py carry` first, or pass --no-players for a "
                         "staging world nobody has played" % a.world_dir)
    # cobblers_restore puts ground back to the heightmap: a disposable-world tool that must never be installed
    # beside the live world, where one mistyped function would flatten a town
    if (dp / "cobblers_restore").exists():
        shutil.rmtree(dp / "cobblers_restore")
        print("removed", dp / "cobblers_restore", "(disposable worlds only)")
    for name in SERVER_PACKS:
        if (dp / name).exists():
            shutil.rmtree(dp / name)
        shutil.copytree(PACKS / name, dp / name)
        print("installed", dp / name)
    wdp = Path(a.world_dir) / "datapacks"
    wdp.mkdir(exist_ok=True)
    for src in WORLD_PACKS:
        if (wdp / src.name).exists():
            shutil.rmtree(wdp / src.name)
        shutil.copytree(src, wdp / src.name)
        print("installed into the world folder", wdp / src.name)


class Rcon:
    def __init__(self, server_dir):
        sys.path.insert(0, str(TOOLS))
        import runtime_guard
        self.rcon, self.pw = runtime_guard.rcon(server_dir)

    def __call__(self, cmd, timeout=3600):
        return self.rcon.run([cmd], self.pw, timeout=timeout)[0].strip()


def indexed(pack, folder):
    """The function names a generated pack lists in its own index.txt, in the order it wrote them."""
    idx = PACKS / pack / "data" / "cobblers" / "function" / folder / "index.txt"
    if not idx.is_file():
        raise SystemExit("no %s: run `reapply.py prepare` first" % idx)
    return [x for x in idx.read_text(encoding="utf-8").split("\n") if x.strip()]


def function_packs():
    """Every generated pack that ships at least one .mcfunction, as {pack: [namespaced prefixes]}."""
    out = {}
    if not PACKS.is_dir():
        return out
    for pack in sorted(p.name for p in PACKS.iterdir() if p.is_dir()):
        base = PACKS / pack / "data" / "cobblers" / "function"
        if not base.is_dir():
            continue
        folders = [d.name for d in base.iterdir() if d.is_dir() and any(d.glob("*.mcfunction"))]
        if folders:
            out[pack] = folders
    return out


def uncovered(todo):
    """Packs that ship functions, are not deliberately excluded, and no step runs.

    This exists because five of the largest builds in the project -- the Rift skin, the Rift biome, the Windward
    Deep, Victory Road and the League's lot -- were hand-applied to the staging world and had no step here, while
    the re-export was twice reported as rehearsed end to end. A missing step is invisible: the run is green and
    the build is simply gone after the next export. Fail closed instead.
    """
    run_ns = set()
    for _sid, _title, acts in todo:
        for kind, value in acts:
            if kind == "fn" and ":" in value:
                run_ns.add(value.split(":", 1)[1].split("/", 1)[0])
    bad = []
    for pack, folders in function_packs().items():
        if pack in EXCLUDED:
            continue
        if not any(f in run_ns for f in folders):
            bad.append("%s (functions in %s)" % (pack, ", ".join(folders)))
    return bad


def steps(with_spawns=False):
    """[(step id, title, [(kind, value)])]; kind is fn (a function), wait (seconds), check (a callable name)."""
    doc = placements()
    out = [("R1", "the Rift skin: the block pass over the sculpted shape",
            [("fn", "cobblers:rift/%s" % f) for f in indexed("cobblers_rift", "rift")]),
           ("R1B", "the Rift biome, painted over the skin",
            [("fn", "cobblers:rift/%s" % f) for f in indexed("cobblers_rift_biome", "rift")]),
           ("R2", "Displaced City cavern", [("fn", "cobblers:cavern/%s" % f) for f in CAVERN]),
           ("R3", "world tree", [("fn", "cobblers:worldtree/%02d_tree" % k) for k in range(4)]
            + [("fn", "cobblers:worldtree/90_foundation"), ("check", "crown")]),
           ("R4", "Foothill grove", [("fn", "cobblers:reapply/grove"), ("fn", "cobblers:reapply/grove_augment")]),
           ("R5", "elders", [("fn", "cobblers:reapply/elders")]),
           ("R6", "Route 1 maze forest", [("fn", "cobblers:route1/tile_%d_%d" % (i, j)) for i in range(4) for j in range(4)]),
           ("R10", "Relic Island islet (before the towns: the house stands on it)", [("fn", "cobblers:reapply/islet")]),
           ("R7", "hometown", [("fn", "cobblers:towns/hometown")])]
    r8 = []
    for s in places(doc):
        r8 += [("fn", "cobblers:reapply/prep_%s" % s), ("fn", "cobblers:towns/%s" % s)]
    out.append(("R8", "planned towns and places (%d)" % len(places(doc)), r8))
    r9 = []
    for d in donors(doc):
        r9 += [("fn", "cobblers:structures/place_%s" % d), ("wait", 3)]
    # After the towns and BEFORE the donors: the town pass would re-level ground under it, and place_donor
    # stamps the League building onto the lot this levels.
    out.append(("R8B", "the League's lot on the apex oval, levelled before its donor",
                [("fn", "cobblers:league_tunnel/%s" % f)
                 for f in indexed("cobblers_league_tunnel", "league_tunnel")]))
    out.append(("R9", "pack donors (%d)" % len(donors(doc)), r9))
    # the Deep is sunk into the Rift floor; Victory Road runs from its floor to the League's apron, so it needs
    # the Deep carved and the lot levelled first. Its backfill pack is staging-only and is excluded on purpose.
    out.append(("R9B", "the Windward Deep",
                [("fn", "cobblers:deep/%s" % f) for f in indexed("cobblers_deep", "deep")]))
    out.append(("R9C", "Victory Road",
                [("fn", "cobblers:victory_road/%s" % f) for f in indexed("cobblers_victory_road", "victory_road")]))
    # the regions open their forks through the road's own wall, so they come after it: re-running R9C alone would
    # close every fork again (data/vr_regions.json re_apply_after)
    out.append(("R9D", "Victory Road's five regions, after the road",
                [("fn", "cobblers:vr_regions/%s" % f) for f in indexed("cobblers_vr_regions", "vr_regions")]))
    # the Habitat Blocks, after everything that builds the floors they sit in (R9D's shell pass overwrites them). A
    # block placed by command stays inert until its chunk loads from disk, and EXP-021 found only a restart does that
    # reliably: the audit runs with the server stopped, so the boot after it is that restart. Verify after it.
    out.append(("R9E", "Habitat Blocks (data/habitat_blocks.json), then let their chunks reload",
                [("fn", "cobblers:habitats/place"), ("wait", 20)]))
    # after the rooms they stand in exist; their classes loaded at boot from cobblers_dialogue
    out.append(("R9F", "NPCs a reward is given through (data/rewards.json npc_grant)",
                [("npc", n) for n in npcs()]))
    # what must stand after the donors, which are placed whole and erase what was inside them: the lights
    late = sorted({q["settlement"] for q in doc["placements"] if q.get("kind") == "earthwork" and q.get("after") == "donors"})
    out.append(("R16", "lights, after the donors (%d places)" % len(late), [("fn", "cobblers:towns/%s_after_donors" % s) for s in late]))
    # the signposts after the donors too: a donor is placed whole, and Sabrina's department store's air margin erased
    # the post where Route 7 leaves her town when the signs went in first (the staging run of 2026-09-21)
    out.append(("R15", "route signposts, after the donors", [("fn", "cobblers:signs/place")]))
    trad = json.loads((ROOT / "data" / "traders.json").read_text(encoding="utf-8"))
    towns = sorted({t["settlement"] for t in trad.get("traders") or [] if t.get("settlement")})
    out.append(("R14", "town traders", [x for t in towns for x in (("fn", "cobblers:towns/vendors_%s" % t), ("wait", 8))]))
    out.append(("V", "floor verify and trader verify", [("check", "verify")]))
    return out


def run(a):
    rc = Rcon(a.server_dir)
    OUT.mkdir(parents=True, exist_ok=True)
    rec = {"started": time.strftime("%Y-%m-%dT%H:%M:%S"), "steps": []}
    path = OUT / ("run_%s.json" % time.strftime("%Y%m%d_%H%M%S"))
    todo = steps(a.with_spawns)
    ids = [s[0] for s in todo]
    if a.only:
        todo = [s for s in todo if s[0] == a.only]
    elif getattr(a, "from_step", None):
        todo = todo[ids.index(a.from_step):]
    print("reload:", rc("reload"))
    for sid, title, actions in todo:
        t0 = time.time()
        print("== %s %s" % (sid, title), flush=True)
        bad = []
        for kind, v in actions:
            if kind == "fn":
                r = rc("function %s" % v)
                if not r.startswith("Running function"):
                    bad.append("%s: %s" % (v, r[:120]))
                    print("   !! %s -> %s" % (v, r[:120]), flush=True)
            elif kind == "wait":
                time.sleep(v)
            elif kind == "npc":
                conv, (x, y, z), cls = v
                rc("forceload add %d %d" % (x, z))
                for _ in range(30):
                    if "passed" in rc("execute if loaded %d %d %d" % (x, y, z)):
                        break
                    time.sleep(1)
                # once: an NPC already standing there (a re-run) is left alone rather than doubled. A chunk's
                # entities load after its blocks, so "loaded" above does not mean the NPC is visible yet: a query
                # the moment the chunk loaded missed one that was there (staging, 2026-09-23). Look for a while.
                near = "@e[type=cobblemon:npc,x=%d,y=%d,z=%d,distance=..2]" % (x, y, z)
                there = False
                for _ in range(12):
                    if "passed" in rc("execute if entity %s" % near):
                        there = True
                        break
                    time.sleep(0.5)
                if not there:
                    r = rc("spawnnpcat %d %d %d %s" % (x, y, z, cls))
                    print("   %s -> %s" % (cls, r[:120] or "(no reply)"), flush=True)
                rc("execute store result storage cobblers:reapply npcs int 1 if entity %s" % near)
                got = rc("data get storage cobblers:reapply npcs")
                n = int(got.rsplit(":", 1)[-1].strip()) if got.rsplit(":", 1)[-1].strip().isdigit() else -1
                if n != 1:
                    bad.append("%s: %s NPCs at %s, not 1 (is cobblers_dialogue installed, and was the server "
                               "restarted since?)" % (conv, n, (x, y, z)))
                rc("forceload remove %d %d" % (x, z))
            elif kind == "check" and v == "crown":
                x, y, z = CROWN
                # hold the crown's chunk: the tree's functions release theirs when they finish, and a block test in
                # an unloaded chunk fails as if the block were missing (the first staging run stopped here on that)
                rc("forceload add %d %d" % (x, z))
                for _ in range(30):
                    if "passed" in rc("execute if loaded %d 0 %d" % (x, z)):
                        break
                    time.sleep(1)
                r = rc("execute unless block %d %d %d minecraft:air" % (x, y, z))
                rc("forceload remove %d %d" % (x, z))
                if "passed" not in r:
                    bad.append("the world tree's crown block at %s is missing: cobblers_height is not in the world folder" % (CROWN,))
            elif kind == "check" and v == "verify":
                time.sleep(5)
                print(rc("save-all flush", timeout=600))
                for s in ["hometown"] + places():
                    # the result file is removed first: a verify that fails leaves no file, and reading an old one
                    # reported Sabrina's town at 9 gaps from a run before the corner rule changed (staging, 2026-09-21)
                    vf = ROOT / "derived" / "towns" / ("%s_verify.json" % s)
                    vf.unlink(missing_ok=True)
                    r = subprocess.run([sys.executable, str(TOOLS / "place_town.py"), s, "--verify", "--server-dir", a.server_dir],
                                       cwd=ROOT, capture_output=True, text=True)
                    gaps, unverified = None, []
                    if vf.is_file():
                        vres = json.loads(vf.read_text(encoding="utf-8"))
                        gaps, unverified = vres["gaps"], vres.get("unverified") or []
                    elif r.returncode:
                        print("   verify %s failed: %s" % (s, (r.stderr or r.stdout).strip().splitlines()[-1:]), flush=True)
                    print("   verify %-16s gaps %s%s" % (s, gaps, ", unverified: %s" % unverified if unverified else ""), flush=True)
                    # fail closed: the exit code, the gaps and every building the data records, not only the gaps
                    if gaps != 0 or unverified or r.returncode:
                        bad.append("%s: floor verify %s" % (s, "failed to run" if gaps is None else
                                                            "%d gaps, %d unverified, exit %d" % (gaps, len(unverified), r.returncode)))
                r = subprocess.run([sys.executable, str(TOOLS / "traders.py"), "verify", "--rcon", a.server_dir],
                                   cwd=ROOT, capture_output=True, text=True)
                print("   traders verify exit %d" % r.returncode, flush=True)
                if r.returncode:
                    bad.append("traders verify: %s" % r.stdout[-400:])
        dt = time.time() - t0
        rec["steps"].append({"step": sid, "title": title, "seconds": round(dt, 1), "commands": sum(1 for k, _ in actions if k == "fn"),
                             "problems": bad})
        path.write_text(json.dumps(rec, indent=1), encoding="utf-8")
        print("   %s done in %.0f s%s" % (sid, dt, "" if not bad else ", %d PROBLEM(S): stopping" % len(bad)), flush=True)
        if bad:
            rec["stopped_at"] = sid
            path.write_text(json.dumps(rec, indent=1), encoding="utf-8")
            raise SystemExit("stopped at %s. Re-run that step alone (--only %s) once, then continue with --from the next step"
                             % (sid, sid))
    print(rc("save-all flush", timeout=600))
    rec["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    path.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    print("run complete:", path)


def audit(a):
    OUT.mkdir(parents=True, exist_ok=True)
    res = {"world": a.world, "started": time.strftime("%Y-%m-%dT%H:%M:%S")}
    r = subprocess.run([sys.executable, str(TOOLS / "build_audit.py"), "--world", a.world], cwd=ROOT, capture_output=True, text=True)
    res["build_audit"] = {"exit": r.returncode, "tail": r.stdout.strip().splitlines()[-12:]}
    print("build_audit exit", r.returncode)
    print("\n".join(res["build_audit"]["tail"]))
    res["towns"] = {}
    for s in places():
        r = subprocess.run([sys.executable, str(TOOLS / "town_audit.py"), s, "--world", a.world, "--server-dir", a.server_dir],
                           cwd=ROOT, capture_output=True, text=True)
        lines = r.stdout.strip().splitlines()
        problems = [l.strip() for l in lines if "MISMATCH" in l or "NOT POLICIED" in l.upper() or "unpolicied" in l
                    or "NOT AUDITED" in l or "NOT IN POLICY" in l or "UNSUBSTITUTED" in l]
        notes = [l.strip() for l in lines if "NOT CHECKABLE" in l]
        # fail closed: clean only when the audit exits 0, says the plan is clean, and nothing was left unchecked. It
        # used to ignore the exit code and pass "not checkable" (Codex review, 2026-09-21)
        clean = r.returncode == 0 and any("plan clean" in l for l in lines) and not problems and not notes
        res["towns"][s] = {"exit": r.returncode, "clean": clean, "problems": problems, "not_checkable": notes}
        print("%-16s %s%s" % (s, "clean" if clean else "PROBLEMS: %s" % problems[:3],
                              "  (%s)" % "; ".join(n.replace("NOT CHECKABLE  ", "") for n in notes) if notes else ""), flush=True)
    r = subprocess.run([sys.executable, str(TOOLS / "signposts.py"), "verify", "--world", a.world], cwd=ROOT, capture_output=True, text=True)
    res["signposts"] = {"exit": r.returncode, "tail": r.stdout.strip().splitlines()[-6:]}
    print("signposts:", " | ".join(res["signposts"]["tail"]))
    # no walkable position under a roof, or anywhere in the cavern, at block light 0 (tools/light_plan.py check, from
    # the saved world's own light arrays)
    # every place but those whose plan says dark by design (the Scar, the jungle ruins): asking the check about one of
    # those fails it, so the list comes from the data, not from a hand edit here
    import light_plan
    lp = [sys.executable, str(TOOLS / "light_plan.py"), "check", *light_plan.light_places(placements()),
          "--world", a.world, "--server-dir", a.server_dir]
    if getattr(a, "source_root", None):
        lp += ["--source-root", a.source_root]
    r = subprocess.run(lp, cwd=ROOT, capture_output=True, text=True)
    res["lights"] = {"exit": r.returncode, "tail": [l[:200] for l in r.stdout.strip().splitlines()]}
    print("lights:", "0 dark everywhere" if r.returncode == 0 else
          "\n  ".join(l for l in res["lights"]["tail"] if " 0 at block light 0" not in l))
    # all() of nothing is True: the places audited must be every place the data plans, and there must be some
    res["clean"] = (res["build_audit"]["exit"] == 0 and len(res["towns"]) == len(places()) > 0
                    and all(v["clean"] for v in res["towns"].values())
                    and res["signposts"]["exit"] == 0 and res["lights"]["exit"] == 0)
    path = OUT / ("audit_%s.json" % time.strftime("%Y%m%d_%H%M%S"))
    path.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print("audit %s: %s" % ("CLEAN" if res["clean"] else "NOT CLEAN", path))
    return 0 if res["clean"] else 1


def carry(a):
    import socket
    s = socket.socket()
    busy = s.connect_ex(("127.0.0.1", 25565)) == 0
    s.close()
    if busy:
        raise SystemExit("port 25565 is in use: carry players with the server stopped, before the first boot")
    import carry_players
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        r = carry_players.carry(Path(a.old_world), Path(a.world_dir),
                                OUT / ("carry_%s.json" % time.strftime("%Y%m%d_%H%M%S")), a.rehearsal)
    except carry_players.CarryError as e:
        raise SystemExit("carry FAILED: %s" % e)
    print("carried: " + carry_players.summary(r))
    print("manifest (names files by UUID; keep it out of documents):", r["manifest"])


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("carry", help="with the server STOPPED, before the new world's first boot: every player's state")
    q.add_argument("--old-world", required=True,
                   help="the live world as retired in REEXPORT step 2 (last saved within 12 hours)")
    q.add_argument("--world-dir", required=True, help="the fresh export")
    q.add_argument("--rehearsal", action="store_true",
                   help="staging only: allow a retained snapshot or an older copy as the source")
    q = sub.add_parser("prepare")
    q.add_argument("--source-root", default=os.environ.get("COBBLERS_SOURCE_ROOT"), required=not os.environ.get("COBBLERS_SOURCE_ROOT"))
    q.add_argument("--server-dir", required=True)
    q = sub.add_parser("install")
    q.add_argument("--server-dir", required=True)
    q.add_argument("--world-dir", required=True)
    q.add_argument("--no-players", action="store_true",
                   help="install into a staging world nobody has played, with no players carried")
    q = sub.add_parser("run")
    q.add_argument("--server-dir", required=True)
    q.add_argument("--from", dest="from_step")
    q.add_argument("--only")
    q.add_argument("--with-spawns", action="store_true", help="not yet part of the run: spawn pools are a separate decision")
    q = sub.add_parser("audit")
    q.add_argument("--server-dir", required=True)
    q.add_argument("--world", required=True)
    q.add_argument("--source-root", default=os.environ.get("COBBLERS_SOURCE_ROOT"), help="heightmap root, for the light check")
    q = sub.add_parser("plan", help="print the steps and their commands without running anything")
    a = p.parse_args(argv)
    if a.cmd == "plan":
        for sid, title, actions in steps():
            print("%-4s %-60s %4d functions" % (sid, title, sum(1 for k, _ in actions if k == "fn")))
        print("places:", ", ".join(places()))
        return 0
    # Every subcommand but `plan` reads or writes the server or a world (prepare reads the installed packs' donor
    # templates; install writes the packs; run drives RCON; audit reads a world): the lock first, before anything.
    runtime_guard.require_lock("reapply %s" % a.cmd)
    return {"carry": carry, "prepare": prepare, "install": install, "run": run, "audit": audit}[a.cmd](a) or 0


if __name__ == "__main__":
    raise SystemExit(main())

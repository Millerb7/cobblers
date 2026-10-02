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
  python tools/reapply.py run --server-dir <server> [--from R8] [--only R8] [--with-spawns] [--no-reload]
        with the server running, booted with max-tick-time=-1 in its server.properties (the run refuses otherwise;
        restore it afterwards), and the coordination lock held: R2 to R16 in order, timed, each function's reply
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
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))
from terrain import env_source_root  # noqa: E402  (the env var, else .claude/settings.json)
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
                # the Deep's city and the relic area's surface (tools/deep_city.py, 2026-09-27): stood on the pit R9B
                # sinks, after Victory Road's caves (R9C) write round the mouth
                "cobblers_deep_city",
                # Victory Road as one cave network (2026-09-23; it replaced the spine and its regions), its Habitat
                # Block tiles and its finds
                "cobblers_vr_caves", "cobblers_habitats", "cobblers_rewards",
                # the NPC classes and dialogues the placed NPCs use; no functions (see npcs())
                "cobblers_dialogue",
                # Routes 1-3 and the mansion (2026-09-24): the event sites, the scene runtime (props, per-player actors,
                # zones, effects) and the route trainers
                "cobblers_route_events", "cobblers_scenes", "cobblers_trainers",
                # the sleeping Celebi in the Route 1 sapling and its keeper (2026-09-25)
                "cobblers_celebi",
                # the authored legendary encounters and their chambers (2026-09-29, tools/legendaries.py):
                # blocks plus the per-chamber gate; the legendaries themselves are summoned over RCON by R14L,
                # and the pack's own tick drives the gates, so it is world-local below
                "cobblers_legendaries",
                # the Rift's own storm: thunder and lightning for players inside the Rift (2026-09-25)
                "cobblers_rift_storm",
                # 2026-09-26, the install sweep: three packs the game needs that were only ever copied by hand, or
                # never installed. The structure templates every `place template` step uses (elders, themed saplings,
                # the maze forest's sapling) - a server rebuilt from the repo had none of them; the spawn biome tags;
                # and the size outliers (self-driving, so world-local below)
                "cobblers_kits", "cobblers_spawn_tags", "cobblers_sizes",
                # 2026-09-26: blackout, recovery claims and the water ladder (tools/blackout_pack.py, EXP-042);
                # self-driving and it sets keepInventory, so world-local below
                "cobblers_blackout",
                # 2026-09-27: the bridges (tools/bridges.py, data/bridges.json): the Route 7 crossing of Tilpey's
                # outflow, the one required bridge; block functions run by R9G
                "cobblers_bridges",
                # 2026-09-27: each dressed town's landmark and set dressing (tools/town_dressing.py,
                # data/town_dressing.json), run by R16B after the donors and the lights
                "cobblers_town_dressing",
                # 2026-09-28: working Pokemon in the towns (tools/ambient.py, data/ambient.json): a keeper and the work
                # loops run on their own (a tick driver), so world-local below; placed again by R16C after an export
                "cobblers_ambient",
                # 2026-09-28: the wayside shrines on the approaches of towns people pass through (tools/shrines.py,
                # data/shrines.json): block functions run by R16D after the dressing and the working Pokemon
                "cobblers_shrines",
                # 2026-10-02: the Ursaluna's den west of Highwire (tools/ursaluna_cave.py, data/ursaluna_cave.json): a
                # keeper loop holds the bear in its den, so world-local; carved, summoned and dressed by R18U
                "cobblers_ursaluna_cave",
                # 2026-10-02: the Frostpeak research camp (tools/frostpeak_camp.py, data/frostpeak_camp.json): block
                # functions and the instruments' display entities, run by R18F
                "cobblers_frostpeak_camp",
                # 2026-10-02: the Seaward Drift, its strip mine and Driftmouth Isle (tools/sea_drift.py,
                # data/sea_drift.json): 90 block functions run by R9SD, before the Habitat Blocks that sit in its rock
                "cobblers_sea_drift",
                # 2026-10-02: Frostpeak's summit dressing round Articuno's tower (tools/frostpeak_summit.py): wind-shaped
                # tors, rime, lee plants and the old pilgrims' way to the north door. Block functions run by R18S
                "cobblers_frostpeak_summit",
                # 2026-10-02: the Lopunny superfan's house and its Buneary cellar (tools/lopunny_house.py), run by R9LH
                "cobblers_lopunny_house",
                # 2026-10-02: the Old Orchard on Sunset Isle round the Orchard Sleeper (tools/old_orchard.py), run by R9SO
                "cobblers_old_orchard",
                # 2026-10-02: the Copperway Khan in the south-east dunes and its milestones (tools/dune_ruin.py), run by R9DU
                "cobblers_dune_ruin",
                # 2026-10-02: Codex's ten named residents (tools/resident_encounters.py, data/resident_encounters.json):
                # a keeper loop and respawn clock hold them, so world-local; dressed and the ungated ones summoned by R18R
                "cobblers_residents",
                # 2026-10-02: the relic site underground (tools/relic_underground.py, data/relic_underground.json): the
                # old surface build taken off, then the hall, gallery and passage carved, by R9RU; its zone check acts on
                # its own (an advancement), so world-local below
                "cobblers_relic_underground",
                # 2026-10-02: the Drovers' Hollow in the Rift Foot (tools/drovers_hollow.py): a longbarn, its fold and
                # the old working under the bank, run by R9HF
                "cobblers_drovers_hollow",
                # 2026-10-02: Shrew Station on the west sea coast (tools/research_station.py), run by R9RS; every
                # item it can give stays held behind data/research_station.json economy.issuing
                "cobblers_research_station",
                # 2026-10-02: the seven open-air Mega dens made visible (tools/mega_dens.py, data/mega_dens.json): scrape,
                # boulders, bones and each species' sign round the gulch's den anchors. Block functions run by R9MD
                "cobblers_mega_dens",
                # 2026-10-02: water life (docs/mechanics/WATER_LIFE.md): the lake skin and the lake hooks
                # (tools/lake_life.py), and the shore, the seabed's wrecks and Rift debris and the two sea caves
                # (tools/sea_life.py). Pure block functions, no load or tick, run by R9LL and R9SL
                "cobblers_lake_life", "cobblers_sea_life",
                # 2026-09-29: the gym interiors (tools/gym_interiors.py, data/gym_interiors.json): the healing
                # machines out of all eight placed gyms, and gym 1's works carved under its lot. Block functions run
                # by R16E, after the donors (R9) that stamp the gyms whole and would erase anything written first
                "cobblers_gym_interiors",
                # 2026-09-29: the five rejected sets of gym works filled in and their COBBLEVERSE shells taken down
                # (tools/gym_demolish.py, data/gym_interiors.json `superseded_by`). Gyms 1, 3, 4, 5 and 7 only:
                # Misty's (gym 2) is kept exactly as built. Block functions run by R16F, after R16E
                "cobblers_gym_demolish",
                # 2026-09-29: the authored gym buildings (tools/gym_buildings.py, data/gym_buildings/*.json): one
                # hall per gym with its puzzle inside it, on the lot the shell stood on. Block functions run by
                # R16G, after the demolition (R16F) that clears the lot for them
                "cobblers_gym_buildings",
                # 2026-09-28: no catching over the level cap (tools/levelcap_pack.py, data/level_cap.json): a Cobblemon
                # callback acts on its own, so world-local below
                "cobblers_levelcap",
                # 2026-10-02: one Spectrier per player at the Crown Cemetery (tools/spectrier_cap.py,
                # data/spectrier_cap.json): its own tick tag judges each new wild Spectrier, so world-local below,
                # the cobblers_sizes shape (self-driving, no blocks, no step)
                "cobblers_spectrier_cap",
                # 2026-09-27: the Rift dig camp's mines, quarries and the mega stone seam (tools/rift_mines.py): blocks
                # run by R9M, and the seam crystal's ward and daily face that act on their own (an advancement, a tick
                # driver), so world-local below. Its gated galleries went to the gulch the same day
                "cobblers_rift_mines",
                # 2026-09-27: the southern Rift's mega site, prototype slice (tools/gulch_mine.py, SOUTHERN_RIFT_MEGA.md):
                # blocks and the Cutters run by R9S; the gate, the zone check, the faces' ward and the Megas' keeper act
                # on their own (advancements, a tick driver), so world-local below
                "cobblers_gulch_mine",
                # 2026-09-30: the Rift's zones Z1, Z2, Z4 and Z5 (tools/rift_zones.py, data/rift_zones.json,
                # docs/mechanics/RIFT_ZONES.md): the cross-walls and gatehouse shells run by R9Z; the four zone
                # checks, the exit boxes and the passes act on their own (advancements and a load function that
                # makes the cob_pass objectives), so world-local below. Z3 is superseded by the gulch's own zone
                "cobblers_rift_zones",
                # 2026-09-30: the nine built ferry docks (tools/ferry_docks.py, data/ferry_docks.json).
                # Blocks in the overworld, so WORLD_LOCAL like the other block packs
                "cobblers_ferry_docks",
                # 2026-09-30: the lake beds tools/rift_skin.py painted over before it was fixed the same day
                # (F5). A REPAIR for worlds exported before the fix: the skin no longer writes those cells, so
                # nothing puts back the gravel and clay tools/paint_maps.py paints, and re-running R1 leaves
                # them purple (probed on cobblers-dryrun12, 2026-09-30). On a world exported after the fix it
                # lays back exactly what is already there, so it is harmless rather than conditional
                "cobblers_lakebed_repair",
                # the 92 Mega Showdown stone recipes raised to 4 raw stones (decision 5A; tools/mega_recipes.py, generated
                # from the server's own jar, never committed). Data only; world-local so no other world's recipes change
                "cobblers_mega_recipes",
                # 2026-09-27: the ferry (tools/ferries.py, data/ferries.json): the ferrymen's NPC classes and dialogues and
                # the trips their dialogues run; the ferrymen are placed over RCON by R17F. It charges CobbleDollars and
                # teleports players, so world-local below
                "cobblers_ferries",
                # 2026-09-28: the evolution-stone faces (tools/mines.py, data/mines.json, STONE_ECONOMY.md): blocks run by
                # R9O; the faces' restore on approach acts on its own (a tick driver), so world-local below
                "cobblers_mines",
                # 2026-09-29: the dive and sky portals and the pocket dimension (tools/portals.py, data/portals.json,
                # ADR-004, EXP-047). It ships a `dimension` and a `dimension_type`, which register only at a server
                # BOOT, not at a /reload: installing this pack needs a restart before R16P will run. The arches are
                # blocks in the overworld (R16P); the rooms live inside the world folder, which a re-export replaces,
                # so R16P rebuilds them every time. The gate sweep and the rescue act on their own (tick drivers)
                "cobblers_portals")

# Packs that ship functions and deliberately have NO step, each with the reason. Anything not here and not run
# by a step makes `prepare` fail: that is the fail-closed check.
EXCLUDED = {
    "cobblers_reapply": "the loose-function container; its functions are run by the steps that own them",
    # 2026-09-30: HELD BACK ON PURPOSE, and this is a safety hold, not tidiness. R9Z places obsidian walls
    # across the Rift's throat, the League's gate and behind the League, plus gatehouse barriers. The hold was
    # put on because the functions that let a player EARN a pass - cobblers:rift_zones/z{1,2,4,5}/qualify -
    # were called by nothing at all, so the walls would have gone up with nobody able to pass them.
    # `unreferenced()` found it, which is exactly what it is for (see its docstring).
    #   HALF DONE, 2026-09-30 (later the same day): every qualify is now called. Each gate has a knock box --
    #   the walkway blocks in front of the guard -- with a minecraft:location advancement whose reward runs
    #   <zone>/qualify, the shape data/gulch_mine.json gate.knock already uses at the gulch's grille. Z2's two
    #   unstaffed sculpted descents are staffed posts granting the same pass. With this pack un-excluded and
    #   R9Z restored, `unreferenced()` is empty and `uncovered()` no longer names it (measured, not assumed).
    #   STILL OWED, and why the hold stays: z5 gates on cobblers:flag/rift_crisis_resolved, which
    #   data/progression.json does not declare and nothing sets (Codex has the contract on
    #   origin/codex/trainer-modes data/quests.json and records that it has no authoritative setter), and z4's
    #   120-species test exists only in G4's dialogue, which is not written. Both fail CLOSED, so those two
    #   zones would simply be shut. Lift the hold and restore the R9Z step IN THE SAME CHANGE - un-excluding
    #   without the step makes `uncovered()` fail, and the step without the pack installs nothing.
    # (not excluded any more: R9Z installs the half that can be passed -- see the step)
    "_cobblers_rift_zones_was": "held: z5's rift_crisis_resolved has no setter and z4's caught test has no dialogue, "
                           "so both would be shut walls (2026-09-30; qualify is wired, see the note above)",
    "cobblers_vr_backfill": "staging only: it buries schema 1's labyrinth, which a fresh export never has",
    "cobblers_restore": "disposable worlds only; install() deletes it if it is found",
    "cobblers_rift_fracture": "retired, replaced by the sculpt in the heightmap",
    "cobblers_worldtree": "a WORLD pack, installed into the world folder and run by R3",
    "cobblers_height": "a WORLD pack: it raises the build limit and runs nothing",
    "cobblers_suppress": "spawn data, no functions to run: generated and installed by `install` (SPAWN_PACKS)",
    # these three drive themselves and write no blocks: found by the check below the moment it was added
    "cobblers_progression": "self-driving: its own minecraft load and tick tags run it",
    "cobblers_sizes": "self-driving: its own minecraft load tag runs it",
    "cobblers_levelcap": "self-driving: a Cobblemon poke_ball_capture_calculated callback runs its check; its load tag makes the scores",
    "cobblers_rift_storm": "self-driving: its own minecraft load tag starts the storm loop (tools/rift_storm.py)",
    "cobblers_spectrier_cap": "self-driving: its own minecraft tick tag judges each new wild Spectrier at the Crown "
                              "Cemetery (tools/spectrier_cap.py); it writes no blocks",
    "cobblers_blackout": "self-driving: its own load and tick tags, an advancement and three Cobblemon callbacks run it; "
                         "it writes no blocks",
    "cobblers_titles": "event functions (enter_place_*), fired on entering a place, not applied to the world",
    "cobblers_trainers": "self-driving: each trainer's won function is an advancement reward rctmod fires for the winner, "
                         "and its tick cycle keeps each trainer home and refuses a rematch; the trainers themselves are "
                         "placed by R17 over RCON (summon_persistent), not by a function",
    "cobblers_rewards": "self-driving: each find is an advancement that runs its own reward function as the player "
                        "who earns it; it writes no blocks (the containers are placed by R9C)",
    # Victory Road schema 2, retired 2026-09-23 when the owner chose a cave network (data/vr_caves.json)
    "cobblers_victory_road": "retired: the schema 2 spine, replaced by cobblers_vr_caves (R9C)",
    "cobblers_vr_regions": "retired: schema 2's five regions, folded into cobblers_vr_caves as its zones",
    "cobblers_vr_clear": "staging only: rock back into what the retired spine and regions carved; a fresh export never had them",
    # 2026-09-27: the spur's gated galleries, chambers and Heart are retired (SOUTHERN_RIFT_MEGA.md decisions 1-2)
    "cobblers_rift_mines_refill": "staging only: rock back into the Rift spur's retired gated section (tools/rift_mines.py, "
                                  "data/rift_mines.json retired_gated_section); a fresh export never had it",
}
# server packs installed into the target world's own datapacks folder, not the server's: they act without being called
# (the scene runtime's tick; the trainers and event sites travel with it), and the global folder is loaded by every
# world the server runs, the live one included (qa review of EXP-034, 2026-09-24)
WORLD_LOCAL = ("cobblers_scenes", "cobblers_trainers", "cobblers_route_events", "cobblers_celebi", "cobblers_rift_storm",
               "cobblers_sizes", "cobblers_blackout", "cobblers_rift_mines", "cobblers_gulch_mine",
               "cobblers_rift_zones", "cobblers_mega_recipes",
               "cobblers_ferries", "cobblers_ambient", "cobblers_levelcap", "cobblers_mines",
               "cobblers_legendaries", "cobblers_spectrier_cap",
               # 2026-10-02: the den keeper loop holds the bear on its own tick, so world-local as its own comment says
               "cobblers_ursaluna_cave",
               # 2026-10-02: the residents' keeper SPAWNS Pokemon on its own when a player comes near, so it must never
               # load in the global folder, where the live world would run it too
               "cobblers_residents", "cobblers_relic_underground")
# the wild spawns: our rosters (compile_spawns.py, at prepare) and the bounded suppression of inherited spawn files
# (suppress_inherited_spawns.py, at install, against the server and world); world packs, never global
SPAWN_PACKS = ("cobblers_spawns", "cobblers_suppress")
WORLD_PACKS = (ROOT / "modpack" / "datapacks" / "cobblers_height", PACKS / "cobblers_worldtree")
CROWN = (2044, 535, 2282)                      # the world tree's highest block (tools/build_audit.py world_tree)
# 25_reshell added 2026-09-30: the shell's own fills run a SECOND time, after the carve and before the tunnel.
# 02_shell runs once, before the excavation, and `replace #cobblers:cavern_void` only touches blocks the tag
# names - so cave decoration the tag did not list (dripstone, hanging roots, lichen, vines) stayed standing,
# and broke to air when the excavation took its support. That is the best account of how shell_voids went 0 -> 12
# between exports; the pre-carve world is gone, so it is a hypothesis, not a measurement. The tag grew 8 -> 27
# blocks in the same change. 25_reshell is safe where it sits because inside the box the shell starts at the
# ceiling and the excavation stops at ceiling-2, so it cannot undo the carve. It must come BEFORE 50_tunnel,
# which is dug THROUGH the shell and would otherwise be filled back in.
CAVERN = ["00_seal", "02_shell", "05_reset", "10_excavate", "20_surfaces", "25_reshell", "30_trees", "40_light", "50_tunnel", "70_drain", "15_cap", "60_biome"]
UNPLACED = {"hometown"}                          # has roads, not a town plan: placed by R7


def placements():
    return json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))


def bridges():
    """Every bridge data/bridges.json authors, in order (tools/bridges.py builds each as cobblers:bridges/<id>)."""
    return json.loads((ROOT / "data" / "bridges.json").read_text(encoding="utf-8"))["bridges"]


def scene_npcs():
    """[(conversation id, (x, y, z), npc class)] for every NPC a scene places (data/scenes.json npcs)."""
    sc = json.loads((ROOT / "data" / "scenes.json").read_text(encoding="utf-8"))
    dl = {c["id"]: c for c in json.loads((ROOT / "data" / "dialogue.json").read_text(encoding="utf-8"))["conversations"]}
    out = []
    for s in sc["scenes"]:
        for n in s.get("npcs") or []:
            c = dl.get(n["conversation"])
            if c is None or not c.get("npc_id"):
                raise SystemExit("scene %s places an NPC for %s, which has no NPC class" % (s["id"], n["conversation"]))
            out.append((n["conversation"], tuple(n["at"]), "cobblers:%s" % c["npc_id"]))
    return out


def scene_props():
    """[(scene id, box x0 z0 x1 z1, prop count)] for every scene with props (its place function)."""
    sc = json.loads((ROOT / "data" / "scenes.json").read_text(encoding="utf-8"))
    out = []
    for s in sc["scenes"]:
        props = s.get("props") or []
        if props:
            xs, zs = [int(q["at"][0]) for q in props], [int(q["at"][2]) for q in props]
            out.append((s["id"], (min(xs), min(zs), max(xs), max(zs)), len(props)))
    return out


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
        if not (isinstance(r.get("npc_at"), list) and len(r["npc_at"]) == 3):
            raise SystemExit("reward %s is an npc_grant with no npc_at [x, y, z]: nowhere to place it" % r["id"])
        out.append((conv["id"], tuple(r["npc_at"]), "cobblers:%s" % conv["npc_id"]))
    return out


def places(doc=None):
    """Every planned place, in build order: the Displaced City and Relic Island last, after their ground exists."""
    doc = doc or placements()
    ids = []
    for sid, value in doc["settlements"].items():
        plan = value.get("plan") or {}
        if value.get("retired"):
            continue                              # data/placements.json settlements.<id>.retired says why
        if sid not in UNPLACED and (plan.get("streets") or plan.get("plaza") or plan.get("anchors")):
            ids.append(sid)
    late = [s for s in ("relic_island", "displaced_city") if s in ids]
    return [s for s in ids if s not in late] + late


def donors(doc=None):
    doc = doc or placements()
    retired = {s for s, v in doc["settlements"].items() if v.get("retired")}
    return [q["id"] for q in doc["placements"] if q.get("pack_template") and q.get("kind") != "vendor"
            and q.get("settlement") not in retired]


def py(*args, cwd=ROOT):
    print("  $ python %s" % " ".join(str(a) for a in args), flush=True)
    # PYTHONHASHSEED is pinned for every tool the build runs: a set of strings iterates in hash order, so an
    # unpinned build can write the same data in a different order and look like a regression. It did:
    # derived/deep_city/plan.json varied run to run (one `for k in set(feats)`, fixed at its source 2026-09-28), and
    # a sweep read the change as damage from an unrelated edit. The seed only orders what is otherwise unordered;
    # no output depends on its value (checked by rebuilding every job under two seeds).
    env = dict(os.environ, PYTHONHASHSEED="0")
    r = subprocess.run([sys.executable] + [str(a) for a in args], cwd=cwd, capture_output=True, text=True, env=env)
    if r.returncode:
        print(r.stdout[-2000:], r.stderr[-3000:])
        raise SystemExit("failed: %s" % " ".join(str(a) for a in args[:2]))
    return r.stdout


def derived_inputs(a):
    """Rebuild the derived inputs prepare reads that a checkout without them lacks (a fresh clone, an agent's
    worktree). Each is reproducible from the heightmap and committed data, bit for bit, and each is rebuilt only when
    missing, or for the Rift plan when it names another heightmap:

      derived/rift_sculpt/   the Rift's lip ring, entrances and masks   rift_heightmap.py --plan    ~15 s
      build/paint/           the region paint (biomes, forests, frost)  paint_maps.py               ~2 min
      derived/water_shape/   the pending water export's changed columns water_shape.py --no-maps   ~5 min

    --plan refuses unless the sculpt it computes is the heightmap data/world.json names, pixel for pixel.

    First the local-only kit files git does not carry (kits/LOCAL_ONLY.json): extracted from the server's own jars,
    or, for the two that no jar reproduces, copied from COBBLERS_LOCAL_STORE by sha256 (tools/local_inputs.py)."""
    src = ["--source-root", a.source_root]
    store = getattr(a, "store", None) or os.environ.get("COBBLERS_LOCAL_STORE")
    py(TOOLS / "local_inputs.py", "hydrate", *(["--server-dir", a.server_dir] if a.server_dir else []),
       *(["--store", store] if store else []))
    world = json.loads((ROOT / "data" / "world.json").read_text(encoding="utf-8"))
    plan = ROOT / "derived" / "rift_sculpt" / "plan.json"
    have = json.loads(plan.read_text(encoding="utf-8")).get("sha256") if plan.is_file() else None
    if have != world["heightmap"]["sha256"] or not (plan.parent / "basin.npy").is_file():
        py(TOOLS / "rift_heightmap.py", *src, "--plan")
    if not (BUILD / "paint" / "manifest.json").is_file():
        py(TOOLS / "paint_maps.py", *src, "--out", BUILD / "paint")
    water = ROOT / "derived" / "water_shape"
    if not (water / "changed.npy").is_file() or not (water / "manifest.json").is_file():
        py(TOOLS / "water_shape.py", *src, "--no-maps")


def select_jobs(names, only=None, from_job=None):
    """The jobs to run: every one; or those --only names (comma separated, shell patterns: town:*, mines*); or
    --from one to the end. An unknown name is an error, never an empty run."""
    import fnmatch
    if only and from_job:
        raise SystemExit("--only and --from cannot be combined")
    if from_job:
        if from_job not in names:
            raise SystemExit("--from %s: no such job (reapply.py prepare --list)" % from_job)
        return set(names[names.index(from_job):])
    if only:
        run = set()
        for pat in only.split(","):
            hit = [n for n in names if fnmatch.fnmatchcase(n, pat.strip())]
            if not hit:
                raise SystemExit("--only %s: matches no job (reapply.py prepare --list)" % pat)
            run.update(hit)
        return run
    return set(names)


def prepare_jobs(a):
    """prepare's work as named jobs, in order: (name, callable). `reapply.py prepare --list` prints them."""
    src = ["--source-root", a.source_root]
    J = []

    def add(name, tool, *args):
        J.append((name, lambda: py(TOOLS / tool, *args)))

    J.append(("hydrate", lambda: derived_inputs(a)))
    add("critical_legs", "critical_legs.py", *src)
    add("cavern_plan", "cavern_plan.py", *src)
    add("world_tree", "world_tree.py", *src)
    add("tree_grove", "tree_grove.py", *src, "--site", "2016,2272", "--id", "foothill_woods")
    add("tree_grove:augment", "tree_grove.py", *src, "--augment", "foothill_woods")
    add("elder_trees", "elder_trees.py", *src)
    add("themed_saplings", "themed_saplings.py", *src)                            # placed from data/themed_saplings.json's pins
    add("maze_forest", "maze_forest.py", *src)
    add("islet", "islet.py", *src)
    # the Rift, in the order the world needs it: the skin lies over the sculpted shape, the biome is painted
    # on top of it, the League's lot is levelled before the donor stamps the building on it, the Deep is sunk
    # into the Rift floor, and Victory Road runs from the Deep to the League's apron and so needs both.
    add("rift_skin", "rift_skin.py", *src)
    add("rift_league_tunnel", "rift_league_tunnel.py", *src)
    add("rift_deep", "rift_deep.py", *src)
    # Victory Road: one cave network; its Habitat Block tiles and its finds are data the build checks against its
    # own model (`vr_caves.py records --write` writes them)
    add("vr_caves:build", "vr_caves.py", "build", *src)
    # the Rift dig camp's mines, quarries and the mega stone seam (data/rift_mines.json); audited below, once the
    # camp's own plan exists. It also writes the staging-only refill of the spur's retired gated section (EXCLUDED)
    add("rift_mines:build", "rift_mines.py", "build", *src)
    # the southern Rift's mega site, prototype slice (data/gulch_mine.json), then its offline audit: every write inside
    # the plan and the zone, the zone sealed except through the gate, cover over the halls, the faces and the Cutters
    add("gulch_mine:build", "gulch_mine.py", "build", *src)
    add("gulch_mine_audit", "gulch_mine_audit.py", *src)
    # the Rift's zones (data/rift_zones.json): AFTER gulch_mine, because z2 is cut round the gulch's built zone
    # and reads data/gulch_mine.json's polygon. `build` runs its own fail-closed report first and refuses on a
    # problem. The boxes and wall lines are committed data; `trace` is not run here, because it needs the
    # owner's annotated source map, which prepare does not have
    add("rift_zones:build", "rift_zones.py", "build", *src)
    # the Mega Showdown stone recipes raised to 4 raw stones, from the server's own jar (never committed)
    add("mega_recipes", "mega_recipes.py", "--server-dir", a.server_dir)
    # the Deep's city and the relic area's surface, stood on the pit's ring model; the audit checks what it wrote
    # against the ring model, Victory Road's mouth and the sealed volumes, and refuses to go on if anything is wrong
    add("deep_city:build", "deep_city.py", "build", *src)
    add("deep_city_audit", "deep_city_audit.py", *src)
    # the relic site underground (2026-10-02): its own fail-closed report runs first and refuses on a problem; the
    # undo is derived from the superseded surface generator minus the city build above. Its audit runs LATE (below),
    # once every other block pack is built, because it sweeps them all for a cell the undo or the shell would touch
    add("relic_underground:build", "relic_underground.py", *src, "build")
    add("habitat_blocks:function", "habitat_blocks.py", "function")
    add("rewards_pack", "rewards_pack.py")
    # every conversation that compiles, in one pack: the NPCs', the props' and the actors' (refusals are listed)
    def dialogue():
        dlg = PACKS / "cobblers_dialogue"
        if dlg.exists():
            shutil.rmtree(dlg)
        py(TOOLS / "compile_dialogue.py", "--all", "--out", dlg)
    J.append(("compile_dialogue", dialogue))
    # the ferry: its ferrymen's classes and dialogues and the trips (data/ferries.json), then its offline audit: every
    # landing on ground or a deck, every gate a planned flag, every fare read before it is charged, and every line
    # declared a gate still unswimmable under data/blackout.json's fatigue on the heightmap
    add("ferries:build", "ferries.py", "build")
    add("ferries:audit", "ferries.py", "audit", *src)
    # the ferry docks' pack (a SERVER_PACKS member): until 2026-10-02 no job built it, and a build/ left over from an
    # earlier hand run hid that; function_limits failed on a fresh checkout without it
    add("ferry_docks:build", "ferry_docks.py", "build", *src)
    # Routes 1-3: the event sites (it fails when data/scenes.json or data/route_trainers.json disagree with the
    # build, or anything stands on the walked line), then the scene runtime and the trainers
    add("route_events", "route_events.py", *src)
    add("scenes_pack", "scenes_pack.py")
    # routes 4-8's 28 trainers (tools/late_route_trainers.py, data/late_route_trainers.json, 2026-09-30): the
    # biggest unplaced content in the project until now. BEFORE route_trainers, which reads its seat file as a
    # fourth source. No --write: it re-seats from the route paths and the heightmap and FAILS on drift, the way
    # route_events does, so a seat cannot quietly move when the ground under it changes.
    add("late_route_trainers", "late_route_trainers.py", *src)
    add("route_trainers", "route_trainers.py")
    add("rematerial", "rematerial.py")
    # the sea town's settlement, Centre, Mart, earthworks and clerk are generated into data/placements.json and
    # data/traders.json from data/sea_town.json and the heightmap; stop here if the committed records are stale. The
    # town itself is then built with every other place (R8: prep_sea_town, towns/sea_town; its clerk in R14)
    add("sea_town:check", "sea_town.py", "check", *src)
    add("town:hometown", "place_town.py", "hometown", *src)
    for s in places():
        J.append(("town:%s" % s, lambda s=s: (py(TOOLS / "town_plan.py", s, *src), py(TOOLS / "place_town.py", s, *src))))
    # the mines against the camp's plan, the haul road and the other places, the seam's crystal behind its grille and
    # ward, and the refill exactly the retired gated section: offline, fail-closed (tools/rift_mines_audit.py)
    add("rift_mines_audit", "rift_mines_audit.py", *src)
    add("place_donor:function", "place_donor.py", "function", "--server-dir", a.server_dir)
    add("traders:function", "traders.py", "function", "--server-dir", a.server_dir)
    add("sapling_celebi", "sapling_celebi.py")
    # the authored legendary chambers, then their offline audit: a chamber whose roof would break a lake bed,
    # whose shell is not sealed, whose gate line lacks its badge flag or whose mouth falls outside the water
    # export's keep zone stops prepare here, before anything is installed
    add("legendaries", "legendaries.py")
    add("legendaries:audit", "legendaries_audit.py")
    add("rift_storm", "rift_storm.py")
    add("signposts:function", "signposts.py", "function", *src)
    # the bridges, then their offline audit against the heightmap and the water: a bridge that would stand in the
    # water, fall short of a bank or crowd a town stops prepare here, before anything is installed
    add("bridges:function", "bridges.py", "function", *src)
    add("bridges:audit", "bridges.py", "audit", *src)
    # the towns' landmarks and set dressing: after the town plans, the placement reports and the signposts, which it
    # keeps clear of; then the plan audit, which fails the prepare on any write on a lot, a road or a building
    add("town_dressing:build", "town_dressing.py", "build", *src)
    add("town_dressing_audit", "town_dressing_audit.py", *src)
    # the working Pokemon: after the dressing, whose pieces they stand beside and keep clear of
    add("ambient:build", "ambient.py", "build", *src)
    # the evolution-stone faces: after the town plans, the signposts, the dressing and the working Pokemon, which they
    # keep clear of; then their offline audit, which recomputes every rule from other files' data and stops the prepare
    # on a face the build should not have written
    add("mines:build", "mines.py", "build", *src)
    # the lake-bed repair pack (R1R): until 2026-10-02 no prepare job built it, and only a build/ left over from
    # 2026-09-30 hid that. mines_audit runs at the END (below): it lists reapply's steps, which index every pack
    add("lakebed_repair:build", "lakebed_repair.py", "build", *src)
    # the wayside shrines, then their offline audit against the plans, the legs, the water and the other packs, which
    # fails the prepare on any write where a shrine may not stand. After every other block pack is built (the stone
    # faces included): the generator keeps clear of what they write
    add("shrines:build", "shrines.py", "build", *src)
    add("shrines_audit", "shrines_audit.py", *src)
    # the Ursaluna's den and the Frostpeak research camp (2026-10-02), each then its own independent audit, which
    # replays the written functions against its own reading of the plan and fails the prepare on a broken build
    add("ursaluna_cave", "ursaluna_cave.py", *src)
    add("ursaluna_cave_audit", "ursaluna_cave_audit.py", *src)
    add("frostpeak_camp:build", "frostpeak_camp.py", "build", *src)
    add("frostpeak_camp_audit", "frostpeak_camp_audit.py", "--inputs-root", str(ROOT), *src)
    add("sea_drift:build", "sea_drift.py", "build", *src)
    add("frostpeak_summit:build", "frostpeak_summit.py", "build", *src)
    add("frostpeak_summit_audit", "frostpeak_summit_audit.py", *src)
    add("lopunny_house:build", "lopunny_house.py", "build", *src)
    add("lopunny_house_audit", "lopunny_house_audit.py", *src)
    add("old_orchard:build", "old_orchard.py", "build", *src)
    add("old_orchard_audit", "old_orchard_audit.py", *src)
    add("dune_ruin:build", "dune_ruin.py", "build", *src)
    add("dune_ruin_audit", "dune_ruin_audit.py", *src)
    # the ten named residents (2026-10-02), then their independent audit, which re-derives every site and write from
    # the data and the heightmap and fails the prepare on a broken pack
    add("resident_encounters", "resident_encounters.py", *src)
    add("resident_encounters_audit", "resident_encounters_audit.py", *src)
    add("drovers_hollow:build", "drovers_hollow.py", "build", *src)
    add("drovers_hollow_audit", "drovers_hollow_audit.py", *src)
    add("research_station:build", "research_station.py", "build", *src)
    add("research_station_audit", "research_station_audit.py", *src)
    add("mega_dens:build", "mega_dens.py", "build", *src)
    add("mega_dens_audit", "mega_dens_audit.py", *src)
    add("sea_drift_audit", "sea_drift_audit.py", *src)
    add("relic_underground_audit", "relic_underground_audit.py", *src)
    # water life (docs/mechanics/WATER_LIFE.md): each pack, then its independent audit, which replays the written
    # functions over a world built from the heightmap alone and never imports its builder
    add("lake_life:build", "lake_life.py", "build", *src)
    add("lake_life_audit", "lake_life_audit.py", *src)
    add("sea_life:build", "sea_life.py", "build", *src)
    add("sea_life_audit", "sea_life_audit.py", *src)
    # the gym interiors: the healing machines out of all eight placed gyms, and gym 1's works carved under its lot;
    # then the offline audit, which re-derives every shell box from data/placements.json, replays the written
    # functions into a voxel model and fails the prepare on a broken route, a trainer that can be walked round, a
    # room that breaks its cover or a fall that would hurt
    add("gym_interiors:build", "gym_interiors.py", "build", *src)
    add("gym_interiors_audit", "gym_interiors_audit.py", *src)
    # the demolition of the five rejected interiors and their donor shells, then the authored halls that replace
    # them. In this order: the building is written onto a lot the shell has just been cleared off. Neither reads a
    # world; both take their ground from tools/ground.py and the town plan's levelled lot
    add("gym_demolish:build", "gym_demolish.py", "build", *src)
    add("gym_buildings:build", "gym_buildings.py", "build", *src)
    # (no audit job for the gym buildings yet: the audit and the tests are another agent's, CLAUDE.md principle 16.
    # Add it here, after gym_buildings:build, so a broken hall stops the prepare before anything is installed.)
    # the dive and sky portals and the pocket dimension they lead into (data/portals.json, EXP-047, ADR-004);
    # then the offline audit, which replays the written functions into a voxel model and holds it against its own
    # reading of the heightmap, the lake levels, the towns, the placements, the legendary mouths and the other
    # packs. LAST of the block builds, because its cross-pack check reads what every other pack has written
    # F7's gate, BEFORE the two below and before the ferry docks: every claim that a thing stands in water,
    # tested against the water that is actually PAINTED (inside a basin_polygons ring and under that basin's
    # level_y) rather than against a landmark's loose `extent`. The old check tested `extent` and the
    # "independent" portals audit tested the same wrong polygons, so builder and auditor agreed with each other
    # about a hole up to 219,737 columns wide on lake_tilpey alone. It is cheap and it covers portals, docks and
    # anything else that claims water, so it runs first: one failing claim here beats a dry dive portal in the
    # world (tools/water_mask.py, tests/test_water_mask.py).
    add("water_mask:claims", "water_mask.py", "claims", *src)
    add("portals:build", "portals.py", "build", *src)
    add("portals_audit", "portals_audit.py", *src)
    # no catching over the level cap: a callback and its check
    add("levelcap_pack", "levelcap_pack.py")
    add("location_titles", "location_titles.py")
    # the badge flags: one advancement per gym leader and the Champion, set by rctmod on a won battle
    add("progression_pack", "progression_pack.py")
    # our wild spawns: the route and sub-region rosters from data/spawns.json (the suppression that makes them the
    # only thing spawning there is generated at install, against the server and world it will run on)
    add("compile_spawns", "compile_spawns.py")
    # the structure templates the placement steps use, the spawn biome tags, and the size outliers: all three were
    # on the server only by hand, or not at all, until 2026-09-26 (install sweep)
    add("kit:pack", "kit.py", "pack")
    add("spawn_tag_pack", "spawn_tag_pack.py", "--check-paint", str(BUILD / "paint" / "biomes.png"))
    add("size_outliers", "size_outliers.py")
    # one Spectrier per player at the Crown Cemetery (data/spectrier_cap.json; fails closed if the placement moved)
    add("spectrier_cap", "spectrier_cap.py")
    # blackout, recovery claims and the water ladder (data/blackout.json, data/water_mounts.json)
    add("blackout_pack", "blackout_pack.py")
    # the loose functions (town prep, elders, grove, islet) in one pack

    # the stone faces' audit LAST: it checks R9O through steps(), which indexes every pack built above, so on a fresh
    # build/ it failed closed on whichever pack came after it in this list (found 2026-10-02 on a new worktree)
    add("mines_audit", "mines_audit.py", *src)
    return J


def prepare(a):
    t0 = time.time()
    jobs = prepare_jobs(a)
    names = [n for n, _ in jobs]
    if a.list:
        print("\n".join(names))
        return 0
    run = select_jobs(names, a.only, a.from_job)
    for name, job in jobs:
        if name in run:
            print("[%s]" % name, flush=True)
            job()
    if len(run) < len(names):
        print("partial prepare: %d of %d jobs ran (%s); every other pack is as the last run left it"
              % (len(run), len(names), ", ".join(n for n in names if n in run)))
    # the checks below always run, on the whole build: a partial prepare is held to the same gate
    if REAPPLY.exists():
        shutil.rmtree(REAPPLY)
    fn = REAPPLY / "data" / "cobblers" / "function" / "reapply"
    fn.mkdir(parents=True)
    (REAPPLY / "pack.mcmeta").write_text(json.dumps({"pack": {"pack_format": 48, "description": "Cobblers: loose re-application functions (tools/reapply.py)"}}) + "\n", encoding="utf-8")
    loose = [(BUILD / "town_prep" / ("prep_%s.mcfunction" % s), "prep_%s" % s) for s in places()]
    loose += [(BUILD / "elders" / "elders.mcfunction", "elders"),
              (BUILD / "themed_saplings" / "themed_saplings.mcfunction", "themed_saplings"),
              (BUILD / "grove" / "grove_foothill_woods.mcfunction", "grove"),
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
    # and inside a covered pack, every function has to be run by a step or named by something that runs
    orphans = unreferenced(steps())
    if orphans:
        raise SystemExit("these functions are run by no step and named by nothing in any pack:\n  %s\n"
                         "Run each from a step, call it from one that is, or exclude its pack with a reason."
                         % "\n  ".join(orphans))
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


def replace_pack(dest, src, retired_root):
    """Put the build `src` at `dest`. An installed copy holding files the build lacks is moved aside to a dated folder
    under `retired_root` (outside the server tree), never deleted: on 2026-09-26 an install deleted the only copy of a
    hand-installed template (the concrete-fixed Brock gym) that the fresh build did not have."""
    dest = Path(dest)
    src = Path(src) if src is not None else None
    if dest.exists():
        have = {p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file()}
        want = {p.relative_to(src).as_posix() for p in src.rglob("*") if p.is_file()} if src and src.exists() else set()
        extra = sorted(have - want)
        if extra:
            keep = Path(retired_root) / ("%s-replaced-%s" % (time.strftime("%Y-%m-%d-%H%M%S"), dest.name))
            # two copies of one pack retired in the same second (a stale global copy, then the world copy) each get a
            # folder of their own, never one inside the other (test-author's finding)
            base, n = keep, 1
            while keep.exists():
                n += 1
                keep = base.with_name("%s-%d" % (base.name, n))
            keep.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dest), str(keep))
            print("moved %s aside to %s: it held %d file(s) the build does not, e.g. %s"
                  % (dest, keep, len(extra), ", ".join(extra[:3])))
        else:
            shutil.rmtree(dest)
    if src is not None and src.exists():
        shutil.copytree(src, dest)


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
    wdp = Path(a.world_dir) / "datapacks"
    wdp.mkdir(exist_ok=True)
    retired = Path(a.server_dir).resolve().parent / "cobblers-server-retired"
    for name in SERVER_PACKS:
        # a pack that acts on its own (the scene runtime's tick) belongs to the world it was built for: the global
        # folder is loaded by every world this server runs, the live one included
        dest = (wdp if name in WORLD_LOCAL else dp) / name
        # and the other way round: a global pack copied into the world's folder shadows the one installed here
        stale = dp / name if name in WORLD_LOCAL else wdp / name
        if stale is not None and stale.exists():
            replace_pack(stale, None, retired)
            print("removed", stale, "(it belongs in the %s folder)" % ("world" if name in WORLD_LOCAL else "global"))
        replace_pack(dest, PACKS / name, retired)
        print("installed", dest)
    for src in WORLD_PACKS:
        replace_pack(wdp / src.name, src, retired)
        print("installed into the world folder", wdp / src.name)
    # Our wild spawns, and the suppression that makes them the only thing spawning on the routes and in the
    # sub-regions (the owner, 2026-09-24: the playtest had been Cobbleverse's defaults, a level-44 Ursaluna before
    # Misty and no Wooper at the creek). The suppression pack re-emits every inherited spawn file the server can load
    # with the corridors and sub-region polygons as anticonditions (EXP-012), so it is generated here, against the
    # mods, global packs and world packs this server will actually load, and never committed (upstream data).
    # Both go in the world's own folder: a world pack first seen is enabled above every other pack, so these win
    # over the upstream spawn files, and the global folder the live world shares is left alone
    for name in SPAWN_PACKS:
        if (dp / name).exists():
            shutil.rmtree(dp / name)
            print("removed", dp / name, "(it belongs in the world folder)")
    py(TOOLS / "suppress_inherited_spawns.py", "--server", a.server_dir, "--world", a.world_dir,
       "--subregions", "--boxes", "merged", "--grid", "16")
    for name in SPAWN_PACKS:
        src = PACKS / name
        if not (src / "pack.mcmeta").is_file():
            raise SystemExit("no %s: the spawn packs were not generated" % src)
        replace_pack(wdp / name, src, retired)
        print("installed into the world folder", wdp / name)
    # The configs, last, and fail-closed. Until 2026-09-26 nothing copied modpack/config to the server: five committed
    # overlay files had never reached it (starters.json still offered the starters dropped on 2026-09-23). Install the
    # overlay, then require that every config the server runs is recorded in the repo exactly as it runs
    # (tools/server_config_record.py: the overlay, server/config/mods/ or the base pack)
    import server_config_record as SCR
    cfg = Path(a.server_dir) / "config"
    print("installed %d overlay config files" % SCR.install(cfg))
    # the riding-patched COBBLEVERSE datapack (Cobblemon 1.8 seat migration): the server's copy had been patched by
    # hand in another checkout, and no step made it (install sweep, 2026-09-26)
    import install_check as IC
    src = Path(a.cobbleverse_dp) if a.cobbleverse_dp else None
    if src is None or not src.is_file():
        raise SystemExit("no upstream COBBLEVERSE-DP-v31.zip at %s: pass --cobbleverse-dp <the pack's own zip>" % src)
    IC.PATCHED_DP.parent.mkdir(parents=True, exist_ok=True)
    py(TOOLS / "patch_cobbleverse_riding.py", str(src), str(IC.PATCHED_DP), "--cobblemon-jar",
       str(Path(a.server_dir) / "mods" / "Cobblemon-fabric-1.8.0+1.21.1.jar"), "--expect-patched", "51")
    shutil.copyfile(IC.PATCHED_DP, dp / IC.PATCHED_DP.name)
    print("installed", dp / IC.PATCHED_DP.name, "(riding-patched)")
    # last, fail-closed: everything the repo builds for this server is installed and current, packs and configs
    problems = IC.packs(a.server_dir, a.world_dir) + IC.configs(a.server_dir)
    if problems:
        raise SystemExit("the server does not hold what the repo builds (%d):\n  %s\nfix the install, or record a "
                         "deliberate server value with `tools/server_config_record.py record`"
                         % (len(problems), "\n  ".join(problems)))
    print("install check: every pack and config the repo builds is installed and current")


class Rcon:
    """One RCON connection for the whole run, reconnected when it drops.

    The server directory's client (`rcon.run`) opens a connection per call. R17 makes hundreds of calls (every prop,
    NPC and trainer is placed, polled and counted), and on Windows each closed connection holds its local port in
    TIME_WAIT: the rehearsal of 2026-09-24 ran out of ephemeral ports (WinError 10048) and the verify after R17
    could not connect. The wire protocol is the one that client speaks (a login packet, then one command packet and
    its reply per command); only the connection is kept. The reply is the command's whole output: the server splits
    one over 4096 bytes into several packets, which one call per connection used to cut off at the first.

    A command is sent at most once. A connection found dead before sending is replaced and the command sent on the
    new one; a failure after sending (the command may have run) closes the connection and raises, as a failed call
    did before, and the next command opens a fresh one."""

    CHUNK = 4096                                  # the server's largest reply body per packet
    MARKER = 200                                  # a packet type the server does not handle: it answers it at once

    def __init__(self, server_dir):
        sys.path.insert(0, str(TOOLS))
        import runtime_guard
        self.rcon, self.pw = runtime_guard.rcon(server_dir)
        self.host = getattr(self.rcon, "HOST", "127.0.0.1")
        self.port = getattr(self.rcon, "PORT", 25575)
        self.sock = None
        self.rid = 1

    @staticmethod
    def _packet(rid, kind, body):
        import struct
        payload = struct.pack("<ii", rid, kind) + body.encode("utf8") + b"\x00\x00"
        return struct.pack("<i", len(payload)) + payload

    def _read(self):
        """(request id, body bytes) of the next packet."""
        import struct

        def exact(n):
            buf = b""
            while len(buf) < n:
                chunk = self.sock.recv(n - len(buf))
                if not chunk:
                    raise EOFError("RCON connection closed by the server")
                buf += chunk
            return buf
        (length,) = struct.unpack("<i", exact(4))
        data = exact(length)
        rid, _kind = struct.unpack("<ii", data[:8])
        return rid, data[8:-2]

    def _connect(self, timeout):
        import socket
        last = None
        for attempt in range(5):
            try:
                s = socket.create_connection((self.host, self.port), timeout=timeout)
                break
            except OSError as e:                       # the server busy, or ports briefly short: wait and retry
                last = e
                time.sleep(2 * (attempt + 1))
        else:
            raise SystemExit("RCON: cannot connect to %s:%d: %s" % (self.host, self.port, last))
        self.sock = s
        self.rid += 1
        s.sendall(self._packet(self.rid, 3, self.pw))
        rid, _ = self._read()
        if rid == -1:
            self.close()
            raise SystemExit("RCON auth failed")

    def _alive(self):
        """False when the server has closed the idle connection (a read would return nothing)."""
        import select
        import socket
        try:
            readable, _, _ = select.select([self.sock], [], [], 0)
            return not readable or self.sock.recv(1, socket.MSG_PEEK) != b""
        except OSError:
            return False

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    def __call__(self, cmd, timeout=3600):
        if self.sock is not None and not self._alive():
            self.close()
        for attempt in (0, 1):
            if self.sock is None:
                self._connect(timeout)
            self.sock.settimeout(timeout)
            self.rid += 1
            rid = self.rid
            try:
                self.sock.sendall(self._packet(rid, 2, cmd))
            except OSError:
                self.close()                               # not sent: safe to send once more on a new connection
                if attempt:
                    raise
                continue
            try:
                got, body = self._read()
                parts = [body] if got == rid else []
                if len(body) >= self.CHUNK or got != rid:
                    # possibly split: ask for a marker the server answers after the rest of this reply
                    self.rid += 1
                    mark = self.rid
                    self.sock.sendall(self._packet(mark, self.MARKER, ""))
                    while True:
                        got, body = self._read()
                        if got == mark:
                            break
                        if got == rid:
                            parts.append(body)
            except (OSError, EOFError):
                self.close()                               # sent: it may have run, so never sent twice
                raise
            return b"".join(parts).decode("utf8", "replace").strip()


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
            if kind == "props":
                run_ns.add("scenes")
    bad = []
    for pack, folders in function_packs().items():
        if pack in EXCLUDED:
            continue
        if not any(f in run_ns for f in folders):
            bad.append("%s (functions in %s)" % (pack, ", ".join(folders)))
    return bad


FUNCTION_REF = re.compile(r"([a-z0-9_.-]+:[a-z0-9_./-]+)")


def unreferenced(todo):
    """Functions that no step runs and no file of any pack names: not called, scheduled, tagged, rewarded by an
    advancement or run by a dialogue. A pack with a step can still hold a function nothing runs: the Rift's entities
    (`cobblers:rift/fx`) sat beside its 1,005 block functions, the pack counted as covered, and the 2026-09-24
    rehearsal found 0 of 14 in the world. Packs in EXCLUDED are skipped with their reason, and so are the
    functions HELD_FUNCTIONS names -- a function a step deliberately does not run YET, with the reason and the
    condition that releases it read from the data, not a list anyone has to remember to prune."""
    names, text = {}, []
    for pack in sorted(p.name for p in PACKS.iterdir() if p.is_dir()) if PACKS.is_dir() else []:
        root = PACKS / pack / "data"
        for f in root.rglob("*"):
            if not f.is_file():
                continue
            if f.suffix == ".mcfunction":
                rel = f.relative_to(root).parts
                if len(rel) > 2 and rel[1] == "function":
                    names["%s:%s" % (rel[0], "/".join(rel[2:])[:-len(".mcfunction")])] = pack
            # a Cobblemon MoLang callback names functions too (q.run_command('function ...'))
            if f.suffix in (".mcfunction", ".json", ".molang"):
                text.append(f.read_text(encoding="utf-8", errors="replace"))
    run = {v for _s, _t, acts in todo for k, v in acts if k == "fn"}
    if any(k == "props" for _s, _t, acts in todo for k, _v in acts):
        run |= {n for n in names if n.startswith("cobblers:scenes/") and n.endswith("/place")}
    referenced = set()
    for t in text:
        referenced.update(FUNCTION_REF.findall(t))
    held = held_functions()
    return sorted(n for n, pack in names.items()
                  if pack not in EXCLUDED and n not in run and n not in referenced and n not in held)


def held_functions():
    """{function: why} for output a step deliberately withholds, derived from the data that withholds it.

    Today: the Rift's zone walls and gatehouses for a zone that cannot GRANT its pass yet (z4 needs Codex's
    dialogue to read caught_count, z5 needs the rift_crisis_resolved setter). Their blocks are correct and
    built; installing them would wall off the apex and seal the League's precinct, which ends the game for
    anyone who reaches it. When Codex lands either half the `needs_*` field goes from data/rift_zones.json and
    the function stops being held here, with nothing to remember."""
    out = {}
    f = ROOT / "data" / "rift_zones.json"
    if not f.is_file():
        return out
    z = json.loads(f.read_text(encoding="utf-8"))["zones"]
    shut = {zid: [k for k in ("needs_progression", "needs_dialogue") if zz.get(k)]
            for zid, zz in z.items() if zz.get("needs_progression") or zz.get("needs_dialogue")}
    for zid, why in shut.items():
        out["cobblers:rift_zones/gatehouse_%s" % zid] = "%s cannot grant its pass: %s" % (zid, ", ".join(why))
        w = z[zid].get("wall")
        if w:
            out["cobblers:rift_zones/wall_%s" % w] = "%s cannot grant its pass: %s" % (zid, ", ".join(why))
    return out


def steps(with_spawns=False):
    """[(step id, title, [(kind, value)])]; kind is fn (a function), wait (seconds), check (a callable name)."""
    doc = placements()
    # the Rift's entities (the trailhead guards' placeholders and the portal sheets) after its blocks: fx force-loads
    # their chunks and schedules fx_go 60 ticks on, which summons them and counts them. No step ran it until the
    # 2026-09-24 rehearsal found 0 of 14 on a fresh export: they had been placed by hand on staging
    out = [("R1", "the Rift skin: the block pass over the sculpted shape, then its entities",
            [("fn", "cobblers:rift/%s" % f) for f in indexed("cobblers_rift", "rift")]
            + [("fn", "cobblers:rift/fx"), ("wait", 8), ("check", "rift_fx")]),
           # the lake-bed repair (tools/lakebed_repair.py): AFTER R1, because R1 is the pass that did the damage
           # in every world exported before 2026-09-30 and would undo this if it ran second. The skin itself no
           # longer writes these cells, so on a world exported after the fix this lays back exactly what is
           # already there. Its 113,841 columns are the same set the skin now caps one course short - the two
           # counts are derived independently and agree, which is what says the scope is right.
           ("R1L", "the lake beds the Rift skin painted over, laid back (F5)",
            [("fn", "cobblers:lakebed_repair/%s" % f) for f in indexed("cobblers_lakebed_repair", "lakebed_repair")]),
           ("R1B", "the Rift biome, painted over the skin",
            [("fn", "cobblers:rift/%s" % f) for f in indexed("cobblers_rift_biome", "rift")]),
           ("R2", "Displaced City cavern", [("fn", "cobblers:cavern/%s" % f) for f in CAVERN]),
           ("R3", "world tree", [("fn", "cobblers:worldtree/%02d_tree" % k) for k in range(4)]
            + [("fn", "cobblers:worldtree/90_foundation"), ("check", "crown")]),
           ("R4", "Foothill grove", [("fn", "cobblers:reapply/grove"), ("fn", "cobblers:reapply/grove_augment")]),
           ("R5", "elders", [("fn", "cobblers:reapply/elders")]),
           # the themed saplings (tools/themed_saplings.py): before R9E, which puts their nest blocks in their trunks
           ("R5B", "themed saplings", [("fn", "cobblers:reapply/themed_saplings")]),
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
    out.append(("R9C", "Victory Road's caves, from the Deep's mouth to the ravine onto the League's apron",
                [("fn", "cobblers:vr_caves/%s" % f) for f in indexed("cobblers_vr_caves", "vr_caves")]))
    # the Rift dig camp as a mining town and the mega stone seam in its spur (tools/rift_mines.py): after the camp's
    # prep (R8) and tents (R9), whose cells it keeps clear, and before its lights (R16). Shell, air, fittings, then the
    # surface; then the carts, entities summoned 60 ticks after their chunks are force-loaded (the Rift's fx pattern).
    # The seam crystal's ward and daily face drive themselves (an advancement, the pack's tick) and need no step.
    out.append(("R9M", "the Rift dig camp's mines, quarries and the mega stone seam, then its carts",
                [("fn", "cobblers:rift_mines/%s" % f) for f in indexed("cobblers_rift_mines", "rift_mines")]
                + [("fn", "cobblers:rift_mines/carts"), ("wait", 5)]))
    # the southern Rift's mega site, prototype slice (tools/gulch_mine.py; SOUTHERN_RIFT_MEGA.md decision 12 names the
    # step): after the Rift skin (R1), whose surface it paves and cuts, and before the Habitat Blocks (R9E) and the
    # lights (R16). Earthworks, shell, air, fittings, surface, the faces at variant 0; then the Cutters, villagers
    # summoned 40 ticks after their chunks are force-loaded and de-duplicated 100 ticks later (tools/traders.py's
    # pattern). The gate, the zone check, the faces' ward and the Megas act on their own and need no step.
    out.append(("R9S", "the southern Rift's mega site: the gulch gate, the Cutters' square, the Tally Hall and the "
                       "Cutting Floor, then the Cutters",
                [("fn", "cobblers:gulch_mine/%s" % f) for f in indexed("cobblers_gulch_mine", "gulch_mine")]
                + [("fn", "cobblers:gulch_mine/cutters"), ("wait", 8)]))
    # the Rift's zone walls and gatehouse shells (tools/rift_zones.py, data/rift_zones.json; docs/mechanics/
    # RIFT_ZONES.md sections 5 and 6). After the Rift skin (R1), whose surface the walls stand on, after the
    # Deep and Victory Road (R9B, R9C) and the gulch (R9S) whose zone z2 is cut around, and after the League's
    # donor stamp, because the league_gate and behind_league walls run within 30 blocks of the lot and a donor
    # stamped later would erase them. Before the Habitat Blocks (R9E) and the lights (R16). Three cross-walls
    # then four gatehouse shells, in the pack's own index order. The zone checks, the exit boxes and the
    # cob_pass objectives act on their own (advancements and a load function) and need no step. The guards
    # themselves are armour-stand placeholders: Codex writes the NPCs (docs/HANDOVER_CODEX.md item 23)
    # ONLY THE HALF THAT CAN BE PASSED. Every guard calls its qualify now (2026-09-30), so the owner's condition
    # for releasing this is met -- but z4 and z5 still cannot GRANT: z4's test needs Codex's dialogue to read
    # caught_count, z5's flag has no setter. Installing their walls would wall off the apex and, worse, seal the
    # LEAGUE'S PRECINCT, which ends the game for anyone who reaches it. A wall nobody can pass is not a gate.
    # So a zone's wall and gatehouses go in only when that zone declares nothing owed, read from the DATA
    # (zones.<id>.needs_progression / needs_dialogue) and not from a list here: when Codex lands either half, the
    # field goes and the wall follows with no switch to remember.
    zspec = json.loads((ROOT / "data" / "rift_zones.json").read_text(encoding="utf-8"))
    shut = {zid for zid, zz in zspec["zones"].items() if zz.get("needs_progression") or zz.get("needs_dialogue")}
    # a zone names the cross-wall that closes it in zones.<id>.wall ("throat", "behind_league", ...)
    closes = {"wall_%s" % zz["wall"]: zid for zid, zz in zspec["zones"].items() if zz.get("wall")}
    def zone_of(fn):
        # "gatehouse_z2_rim_post_descent" -> z2; a wall names the zone it closes in the spec
        for zid in zspec["zones"]:
            if fn.startswith("gatehouse_%s" % zid):
                return zid
        return closes.get(fn)
    live = [f for f in indexed("cobblers_rift_zones", "rift_zones") if zone_of(f) not in shut]
    heldb = [f for f in indexed("cobblers_rift_zones", "rift_zones") if zone_of(f) in shut]
    out.append(("R9Z", "the Rift's zone walls and gatehouse shells for the zones that can be passed (%d of %d; "
                       "held: %s)" % (len(live), len(live) + len(heldb), ", ".join(sorted(shut)) or "none"),
                [("fn", "cobblers:rift_zones/%s" % f) for f in live]))
    # the evolution-stone faces (tools/mines.py, data/mines.json; STONE_ECONOMY.md 5.5 names the step): after the towns
    # (R8) and the donors (R9), whose cells they keep clear, and the Displaced City cavern (R2), whose shell two of the
    # sites cut into; before the Habitat Blocks (R9E) and the lights (R16). One build function a site, named from the
    # committed data, not the pack's index. The faces' restore on approach drives itself and needs no step
    import mines
    out.append(("R9O", "the evolution-stone faces at their seven places (data/mines.json)",
                [("fn", f) for f in mines.build_functions()]))
    # the city stands on the pit R9B sinks, after R9C (the caves write round the mouth the city keeps clear) and before
    # R9E (Habitat Blocks sit on finished floors) and the lights (R16). Structure, then the Centre and Mart by
    # /place template, then what hangs on the structure (ladders, hatches, panes, doors, signs, lamps). R9DC, not R9D:
    # R9D was the retired Victory Road regions step, and tests/test_reapply_vr_steps.py keeps that id retired
    out.append(("R9DC", "the Deep's city and the relic area's surface (tools/deep_city.py)",
                [("fn", "cobblers:deep_city/%s" % f) for f in indexed("cobblers_deep_city", "deep_city")]))
    # the relic site underground (2026-10-02, tools/relic_underground.py): AFTER R9DC, because its undo takes off the
    # old surface build minus what the city now writes, and its passage meets the HQ's side of the pit; BEFORE R9E and
    # before Codex's cradle, whose own shell would seal the passage. Hold the box, undo, carve (CAVERN pattern), release
    import relic_underground
    out.append(("R9RU", "the relic site underground: the old surface build off, the hall carved (data/relic_underground.json)",
                relic_underground.placement_steps()))
    # the Habitat Blocks, after everything that builds the floors they sit in (R9C's shell pass overwrites them). A
    # block placed by command stays inert until its chunk loads from disk, and EXP-021 found only a restart does that
    # reliably: the audit runs with the server stopped, so the boot after it is that restart. Verify after it.
    # the Seaward Drift, its strip mine and Driftmouth Isle (2026-10-02, tools/sea_drift.py): a pure block pass, so it
    # runs here, BEFORE R9E - ten of the Habitat Blocks sit inside the isle's rock, and a block pass after R9E would
    # write rock over them. Each function force-loads its own chunks first, the pattern R1's Rift pass has used on
    # every verified apply
    out.append(("R9SD", "the Seaward Drift, its strip mine and Driftmouth Isle (data/sea_drift.json)",
                [("fn", "cobblers:sea_drift/%s" % f) for f in indexed("cobblers_sea_drift", "sea_drift")]))
    # water life (2026-10-02, docs/mechanics/WATER_LIFE.md): pure block passes over the applied water export, after
    # the drift (Driftmouth Isle's rock and cover are excluded from both) and before R9E and BEFORE the 2026-10-02 builds below, so a build that overlaps a wreck or
    # shore dressing writes last and wins (merge, 2026-10-02); no Habitat Block placed
    # there is written over. Every lake-skin write replaces only water, air or a natural bed block (the pack's own
    # #cobblers:lake_bed tag), so it cannot overwrite a build it does not know about
    out.append(("R9LL", "the lake skin and the lake hooks (data/lake_life.json)",
                [("fn", "cobblers:lake_life/%s" % f) for f in indexed("cobblers_lake_life", "lake_life")]))
    out.append(("R9SL", "the shore, the wrecks and Rift debris, and the sea caves (data/sea_life.json)",
                [("fn", "cobblers:sea_life/%s" % f) for f in indexed("cobblers_sea_life", "sea_life")]))
    # the Lopunny superfan's house (2026-10-02, tools/lopunny_house.py): BEFORE R9E, because its build writes the cellar
    # floor - after R9E it would lay stone bricks over the Buneary Habitat Block set in that floor
    import lopunny_house
    out.append(("R9LH", "the Lopunny superfan's house and its Buneary cellar (data/lopunny_house.json)",
                lopunny_house.placement_steps()))
    # the Old Orchard on Sunset Isle (2026-10-02, tools/old_orchard.py): BEFORE R9E, because its build writes the trunk
    # the Applin Habitat Block sits in - after R9E it would write the log back over the block
    import old_orchard
    out.append(("R9SO", "the Old Orchard on Sunset Isle: rows, press-house and cellar, garden (data/old_orchard.json)",
                old_orchard.placement_steps()))
    # the Copperway Khan (2026-10-02, tools/dune_ruin.py): BEFORE R9E, because its build writes the vault floor - after
    # R9E it would lay smooth sandstone over the Cofagrigus Habitat Block set in that floor
    import dune_ruin
    out.append(("R9DU", "the Copperway Khan, its sealed store and the Copperway's milestones (data/dune_ruin.json)",
                dune_ruin.placement_steps()))
    # the Drovers' Hollow (2026-10-02, tools/drovers_hollow.py): BEFORE R9E, because its build writes the fold's floor -
    # after R9E it would lay coarse dirt over the herd's Habitat Block set in that floor
    import drovers_hollow
    out.append(("R9HF", "the Drovers' Hollow: its barn, fold and old working (data/drovers_hollow.json)",
                drovers_hollow.placement_steps()))
    # Shrew Station (2026-10-02, tools/research_station.py): BEFORE R9E, because the study pool's Habitat Block sits in a
    # post this pack writes; its four NPCs are placed by R9F
    import research_station
    out.append(("R9RS", "Shrew Station, the research station on the west sea coast (data/research_station.json)",
                research_station.placement_steps()))
    # the seven open-air Mega dens, dressed (2026-10-02, tools/mega_dens.py): a pure block pass round each den anchor of
    # data/gulch_mine.json. AFTER R9S (the gulch's own block pass, whose keeper spawns the Megas at these anchors) and
    # the Rift skin (R1), whose surface it rewrites; BEFORE R9E with the other block passes. Per den: hold, build, release
    import mega_dens
    out.append(("R9MD", "the seven open-air Mega dens: scrape, boulders, bones and each species' sign (data/mega_dens.json)",
                mega_dens.placement_steps()))
    out.append(("R9E", "Habitat Blocks (data/habitat_blocks.json), then let their chunks reload",
                [("fn", "cobblers:habitats/place"), ("wait", 20)]))
    # after the rooms they stand in exist; their classes loaded at boot from cobblers_dialogue
    out.append(("R9F", "NPCs a reward is given through (data/rewards.json npc_grant)",
                [("npc", n) for n in npcs()]))
    # the bridges, after the towns and donors (neither may stand on one, and a donor placed whole would erase what it
    # overlaps) and before the lights; each is one function that holds its own chunks. Named from the data, not the
    # pack's index, so a checkout without the built pack still lists the step
    out.append(("R9G", "bridges (data/bridges.json)",
                [("fn", "cobblers:bridges/%s" % b["id"]) for b in bridges()]))
    # what must stand after the donors, which are placed whole and erase what was inside them: the lights
    late = sorted({q["settlement"] for q in doc["placements"] if q.get("kind") == "earthwork" and q.get("after") == "donors"})
    out.append(("R16", "lights, after the donors (%d places)" % len(late), [("fn", "cobblers:towns/%s_after_donors" % s) for s in late]))
    # the towns' landmarks and set dressing (tools/town_dressing.py): after the donors, which are placed whole, and the
    # lights, so nothing placed later erases a piece. Listed from the committed data, not the build, so the step exists
    # whether or not the pack is built here; the prepare's audit fails if a dressed town's function is missing
    dressed = list(json.loads((ROOT / "data" / "town_dressing.json").read_text(encoding="utf-8")).get("towns") or {})
    out.append(("R16B", "town landmarks and set dressing (%d towns)" % len(dressed),
                [("fn", "cobblers:town_dressing/%s" % s) for s in dressed]))
    # the working Pokemon (tools/ambient.py): entities, so an export erases them; after the dressing they stand beside.
    # Each station's chunk is force-loaded and its worker placed (twice: a chunk's saved entities load a moment after
    # its blocks, and the keeper removes a second), then all are counted
    import ambient
    out.append(("R16C", "working Pokemon in the towns (data/ambient.json)", ambient.placement_steps() + [("check", "ambient")]))
    # the wayside shrines (tools/shrines.py): blocks beside the roads into the towns, after the dressing (R16B) and the
    # working Pokemon (R16C) they keep clear of; each function holds its own chunks. Listed from the committed data,
    # not the build, so the step exists whether or not the pack is built here; the prepare's audit fails on a missing one
    shrine_ids = [q["id"] for q in json.loads((ROOT / "data" / "shrines.json").read_text(encoding="utf-8")).get("shrines") or []]
    out.append(("R16D", "wayside shrines on the town approaches (%d, data/shrines.json)" % len(shrine_ids),
                [("fn", "cobblers:shrines/%s" % s) for s in shrine_ids]))
    # the gym interiors (tools/gym_interiors.py): the healers out of all eight placed gyms, then each built gym's
    # carved works. After the donors (R9), which are placed whole: a healer removed before the donor runs would be
    # stamped back, and a shaft cut before it would be filled in. Listed from the committed data, not the built pack,
    # so the step exists whether or not the pack is built here; the prepare's audit fails on a missing function
    gym_doc = json.loads((ROOT / "data" / "gym_interiors.json").read_text(encoding="utf-8"))
    gym_built = [g["id"] for g in gym_doc.get("gyms") or [] if g.get("built")]
    out.append(("R16E", "gym interiors: no healer in any of the 8 gyms, and %d carved interior(s)" % len(gym_built),
                [("fn", "cobblers:gym_interiors/healers")]
                + [("fn", "cobblers:gym_interiors/%s" % g) for g in gym_built]))
    # the demolition (tools/gym_demolish.py): the five rejected sets of works filled back in and their COBBLEVERSE
    # shells taken down, at every gym data/gym_interiors.json marks `superseded_by`. Gym 2 is never in this list -
    # Misty's is kept exactly as built (the owner, 2026-09-29). After R16E, whose healer sweep still runs over all
    # eight shells, and before the buildings that stand where the shells were
    gym_gone = [g["id"] for g in gym_doc.get("gyms") or [] if g.get("superseded_by")]
    out.append(("R16F", "the rejected gym works filled in and %d donor shell(s) taken down" % len(gym_gone),
                [("fn", "cobblers:gym_demolish/%s" % g) for g in gym_gone]))
    # the authored gym buildings (tools/gym_buildings.py): one hall per record in data/gym_buildings/, each with
    # its puzzle inside it and the leader's spawner at the end of it. Listed from the committed data, not the built
    # pack, so the step exists whether or not the pack is built here; the prepare's audit fails on a missing one
    gym_halls = sorted(p.stem for p in (ROOT / "data" / "gym_buildings").glob("*.json"))
    out.append(("R16G", "the authored gym buildings (%d)" % len(gym_halls),
                [("fn", "cobblers:gym_buildings/%s" % g) for g in gym_halls]))
    # the dive and sky portals (tools/portals.py, data/portals.json): the world-side arches, then `place`, which
    # builds every room inside cobblers:pocket. The rooms live in the world folder and a re-export makes a new one
    # (EXP-047 result 6), so they are rebuilt here every run; they are flat and deterministic, so that is exact.
    # The DIMENSION itself registers only at a server boot, so a first install must restart before this step runs.
    # Listed from the committed data, not the built pack, so the step exists whether or not the pack is built here
    portal_ids = [q["id"] for q in json.loads((ROOT / "data" / "portals.json").read_text(encoding="utf-8"))["portals"]]
    # the ferry docks (tools/ferry_docks.py, data/ferry_docks.json): nine of the twelve planned, the other three
    # unsited and saying why in their records. After R16G, because two of them stand on town ground the gym and
    # town passes level, and BEFORE R17F, which stands a ferryman on each built dock: a ferryman with no dock
    # under him is the fault this whole unit exists to fix. A dock whose `structure` is `host` is built by its
    # host town's own pass (tools/sea_town.py) and is not run here.
    import ferry_docks as FD
    dock_ids = [d["id"] for d in FD.built_docks()] if hasattr(FD, "built_docks") else         [d["id"] for d in json.loads((ROOT / "data" / "ferry_docks.json").read_text(encoding="utf-8"))["docks"]
         if d.get("structure") != "host"]
    out.append(("R16H", "the ferry docks (%d) that make the charters reachable" % len(dock_ids),
                [("fn", "cobblers:ferry_docks/%s" % d) for d in dock_ids]))
    out.append(("R16P", "the dive and sky portals (%d) and their rooms in cobblers:pocket" % len(portal_ids),
                [("fn", "cobblers:portals/world/%s" % p) for p in portal_ids]
                + [("fn", "cobblers:portals/place")]))
    # the signposts after the donors too: a donor is placed whole, and Sabrina's department store's air margin erased
    # the post where Route 7 leaves her town when the signs went in first (the staging run of 2026-09-21)
    out.append(("R15", "route signposts, after the donors", [("fn", "cobblers:signs/place")]))
    # Routes 1-3's event sites after the signposts and every town, and before the things that stand in them
    out.append(("R12", "Routes 1-3 event sites (tools/route_events.py)",
                [("fn", "cobblers:route_events/%s" % f) for f in indexed("cobblers_route_events", "route_events")]))
    # what stands in the sites and the mansion: the scenes' props (interaction boxes, once each), their NPCs, and
    # the route trainers; entities, so an export erases them like blocks, and NPC classes and trainer data load at
    # boot, so these run over RCON after the restart that followed install
    import route_trainers
    out.append(("R17", "scene props, scene NPCs and the route trainers",
                [("props", p) for p in scene_props()] + [("npc", n) for n in scene_npcs()]
                + [("trainer", t) for t in route_trainers.placements()]))
    # the ferrymen (data/ferries.json): NPCs, so an export erases them, and their classes load at boot from
    # cobblers_ferries, so they are placed over RCON after the restart, as R9F and R17 place theirs; the load function
    # first (the pack's scores, also created by its load tag). Listed from the committed data, not the build
    import ferries
    out.append(("R17F", "the ferrymen at the built docks (data/ferries.json)",
                [("fn", "cobblers:ferries/load")] + [("npc", n) for n in ferries.npc_placements(ferries.load())]))
    # the settlement NPCs (data/npc_seats.json): the main reveal's residents and the stone-tip speakers. NPCs like the
    # ferrymen, so placed over RCON after the restart that loaded cobblers_dialogue's classes, and after every town and
    # gym pass so the plaza, lot and lab floor they stand on exist. Each is turned to its authored yaw
    import npc_seats
    out.append(("R17N", "the settlement NPCs (data/npc_seats.json)",
                [("npc", n) for n in npc_seats.placements()]))
    # the Old Orchard's keeper (2026-10-02, tools/old_orchard.py): an NPC like the settlement ones, placed over RCON
    # after the restart that loaded cobblers_dialogue's classes, on the ground R9SO's orchard stands on
    out.append(("R18SO", "the Old Orchard's keeper, Wenna Marlow (data/old_orchard.json npc)",
                [("npc", n) for n in old_orchard.npc_placements()]))
    # the Copperway Khan's salvager (2026-10-02): an NPC on the dug-out hall's floor R9DU wrote, her class loaded at boot
    # from cobblers_dialogue, so placed over RCON after the restart like R17N's
    out.append(("R18DU", "the Copperway Khan's salvager (data/dune_ruin.json npc)",
                [("npc", n) for n in dune_ruin.npc_placements()]))
    # the Ursaluna's den (2026-10-02): carve, summon the sleeping bear over RCON (an entity the export erases, as the
    # Celebi and the legendaries are, and guarded on its tag AND species, not distance - R14C failed twice on a bare
    # distance guard), dress, then its keeper Hollis, whose class loads at boot from cobblers_dialogue
    import ursaluna_cave
    out.append(("R18U", "the Ursaluna's den west of Highwire (data/ursaluna_cave.json)",
                ursaluna_cave.placement_steps() + [("npc", n) for n in ursaluna_cave.npc_placements()]))
    # the Compact guards at the HQ's ring-0 door (2026-10-02, data/relic_underground.json geometry.hq.guard): the door
    # stays shut and the guard's dialogue moves a player at rift_crisis_pending or later inside; the inside guard lets
    # anyone out. NPCs, so after the restart that loaded cobblers_dialogue's classes, like R17N's, each turned to its yaw
    import relic_underground
    out.append(("R18RU", "the Compact guards at the HQ's ring-0 door (data/relic_underground.json geometry.hq.guard)",
                [("npc", n) for n in relic_underground.npc_placements()]))
    # Codex's ten named residents (2026-10-02, data/resident_encounters.json): each one's dressing inside a forceload of
    # its recorded bbox, then - for the two with no presence gate (Old Jaw, Whiteback) - an RCON summon guarded on tag
    # AND species, and its bind. The eight gated ones are left to the pack's keeper, which brings each in the first time
    # a player holding its gate comes near. Entities, so an export erases them, as the den's bear
    import resident_encounters
    out.append(("R18R", "the ten named residents (data/resident_encounters.json)",
                resident_encounters.placement_steps()))
    # the Drovers' Hollow's drover (2026-10-02): after R17N, on the path R9HF wrote, his class loaded at boot from
    # cobblers_dialogue
    out.append(("R18HF", "the Drovers' Hollow's drover, Owen Cray (data/drovers_hollow.json npc)",
                [("npc", n) for n in drovers_hollow.npc_placements()]))
    # the Frostpeak research camp (2026-10-02): its blocks and instruments, held in a forceload so no fill lands on an
    # unloaded chunk, then its three researchers
    import frostpeak_camp
    out.append(("R18F", "the Frostpeak research camp (data/frostpeak_camp.json)",
                [("cmd", "forceload add 680 680 735 735"), ("wait", 3),
                 ("fn", "cobblers:frostpeak_camp/build"), ("fn", "cobblers:frostpeak_camp/instruments"),
                 ("cmd", "forceload remove 680 680 735 735")]
                + [("npc", n) for n in frostpeak_camp.npc_placements()]))
    # Articuno's tower on Frostpeak's summit (2026-10-02, tools/articuno_tower.py): the first adopted Cobbleverse site
    # any step places. On the summit because the owner chose it once the build limit was measured at y575
    # (cobblers_height), not the 320 that had pushed it onto the shoulder. After R18F, whose telescope aims at its crown
    import articuno_tower
    out.append(("R18A", "Articuno's tower on Frostpeak's summit (data/adopted_legendary_sites.json)",
                articuno_tower.placement_steps()))
    # the summit round it (2026-10-02, tools/frostpeak_summit.py): after the tower, whose box and north door it keeps clear
    import frostpeak_summit
    out.append(("R18S", "Frostpeak's summit: tors, rime, lee plants and the pilgrims' way (data/frostpeak_summit.json)",
                frostpeak_summit.placement_steps()))
    trad = json.loads((ROOT / "data" / "traders.json").read_text(encoding="utf-8"))
    towns = sorted({t["settlement"] for t in trad.get("traders") or [] if t.get("settlement")})
    out.append(("R14", "town traders", [x for t in towns for x in (("fn", "cobblers:towns/vendors_%s" % t), ("wait", 8))]))
    # the sleeping Celebi: an entity, so the export erased it; summoned over RCON because Cobblemon's spawn command
    # does nothing from a function (tools/sapling_celebi.py), then walled and dressed by its pack
    import sapling_celebi
    out.append(("R14C", "the Celebi in the Route 1 sapling", sapling_celebi.placement_steps(sapling_celebi.load())
                + [("check", "celebi")]))
    # the authored legendaries: the chambers are blocks, but each legendary is an entity that an export erases,
    # so it is summoned over RCON here for the same reason as the Celebi (spawnpokemonat in a function spawns
    # nothing until a /reload, EXP-046). Only the sited encounters are placed; a blocked one writes nothing.
    import legendaries
    out.append(("R14L", "the authored legendary chambers and their legendaries (data/legendaries.json)",
                legendaries.placement_steps(legendaries.load())))
    out.append(("V", "floor verify and trader verify", [("check", "verify")]))
    return out


def watchdog_setting(server_dir):
    """The max-tick-time value in <server>/server.properties (only that key is read), or None when it is not set,
    which leaves the server's default watchdog of 60 s."""
    props = runtime_guard.check(Path(server_dir) / "server.properties", "read the watchdog setting in")
    if not props.is_file():
        raise SystemExit("no server.properties in %s: is --server-dir the server?" % server_dir)
    for line in props.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line.startswith("#") and line.split("=", 1)[0].strip() == "max-tick-time":
            return line.split("=", 1)[1].strip() if "=" in line else ""
    return None


def require_watchdog_off(server_dir):
    """Refuse the run unless the server's watchdog is off. The Rift's functions leave a lighting backlog that held one
    tick past the 60 s watchdog at R5 on 2026-09-24, and the server killed itself mid-run. The file is what the server
    read at boot only if nobody edited it since: it is set before the boot, and restored after the run."""
    wd = watchdog_setting(server_dir)
    if wd != "-1":
        raise SystemExit(
            "server.properties has max-tick-time=%s: the re-apply run needs the watchdog off. With the server "
            "stopped, set max-tick-time=-1 in %s, boot, and run again; after the run, with the server stopped again, "
            "%s. docs/world-building/REEXPORT.md, the run table, steps 5b and 8a."
            % ("(not set: the default 60000)" if wd is None else wd, Path(server_dir) / "server.properties",
               "remove the line again" if wd is None else "put back max-tick-time=%s" % wd))
    print("watchdog: max-tick-time=-1 in server.properties (restore it after the run)")


def run(a):
    rc = Rcon(a.server_dir)
    OUT.mkdir(parents=True, exist_ok=True)
    rec = {"started": time.strftime("%Y-%m-%dT%H:%M:%S"), "steps": []}
    path = OUT / ("run_%s.json" % time.strftime("%Y%m%d_%H%M%S"))
    todo = steps(a.with_spawns)
    ids = [s[0] for s in todo]
    if a.only:
        # comma separated, and FAIL-CLOSED on an id that matches nothing. Until 2026-09-30 this was a single
        # exact match, so `--only R16E,R16F,R16G` selected zero steps, ran nothing, wrote {"steps": []} and
        # exited 0 - an apply that reports success without applying anything is the worst shape a tool can have.
        want = [t.strip() for t in a.only.split(",") if t.strip()]
        unknown = [w for w in want if w not in ids]
        if unknown:
            raise SystemExit("reapply run --only: no step named %s (have: %s)" % (", ".join(unknown), " ".join(ids)))
        todo = [s for s in todo if s[0] in want]
        print("run --only: %d step(s) selected in plan order: %s" % (len(todo), " ".join(s[0] for s in todo)))
    elif getattr(a, "from_step", None):
        todo = todo[ids.index(a.from_step):]
    if not todo:
        raise SystemExit("reapply run: no steps selected; nothing would be applied")
    if getattr(a, "no_reload", False):
        print("no reload: the packs loaded at boot (a second /reload on this pack stack exhausted a 10 GB heap twice on staging, 2026-09-24)")
    else:
        print("reload:", rc("reload"))
    # No drops while building. Every fill that replaces the block under a flower, a torch or a sapling pops it off as
    # an item, and a falling block that lands on a torch drops both: the owner picked up seeds, flowers and torches all
    # over staging after run 4 (2026-09-25). The rules come back on afterwards, even when a step stops the run, and
    # always to true, never to what was found: a run that died with the server (run 5, out of memory) left them off in
    # the world, and the next run would have "restored" that
    drops = {}
    for rule in DROP_RULES:
        drops[rule] = "true"
        rc("gamerule %s false" % rule)
    try:
        _run_steps(a, rc, todo, rec, path)
    finally:
        for rule, value in drops.items():
            rc("gamerule %s %s" % (rule, value))
        print("drop rules restored:", drops, flush=True)
    print(rc("save-all flush", timeout=600))
    getattr(rc, "close", lambda: None)()
    rec["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    path.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    print("run complete:", path)


DROP_RULES = ("doTileDrops", "doEntityDrops")


def _run_steps(a, rc, todo, rec, path):
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
            elif kind == "cmd":
                # a command a function cannot run for us (Cobblemon's spawn command does nothing inside one)
                r = rc(v)
                print("   %s -> %s" % (v[:100], r[:120] or "(no output)"), flush=True)
            elif kind == "check" and v == "ambient":
                import ambient
                problems = ambient.verify(rc)
                bad += ["ambient: %s" % m for m in problems]
            elif kind == "check" and v == "celebi":
                import sapling_celebi
                x, y, z = (int(q // 1) for q in sapling_celebi.load()["position"])
                rc("forceload add %d %d" % (x, z))
                time.sleep(2)
                n = rc("execute if entity @e[tag=%s]" % sapling_celebi.TAG)
                rc("forceload remove %d %d" % (x, z))
                print("   celebi: %s" % n, flush=True)
                if "count: 1" not in n:
                    bad.append("celebi: expected one tagged Celebi on its branch, got %r" % n)
            elif kind == "npc":
                # (conversation, (x, y, z), class) or, for a seat that faces somewhere (data/npc_seats.json), a fourth
                # element: its yaw, applied below whether the NPC was just spawned or already stood there
                conv, (x, y, z), cls = v[:3]
                yaw = v[3] if len(v) > 3 else None
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
                if yaw is not None:
                    time.sleep(1)
                    rc("tp %s %d.5 %d %d.5 %d 0" % (near.replace("]", ",limit=1]"), x, y, z, yaw))
                rc("execute store result storage cobblers:reapply npcs int 1 if entity %s" % near)
                got = rc("data get storage cobblers:reapply npcs")
                n = int(got.rsplit(":", 1)[-1].strip()) if got.rsplit(":", 1)[-1].strip().isdigit() else -1
                if n != 1:
                    bad.append("%s: %s NPCs at %s, not 1 (is cobblers_dialogue installed, and was the server "
                               "restarted since?)" % (conv, n, (x, y, z)))
                rc("forceload remove %d %d" % (x, z))
            elif kind == "props":
                # a scene's interaction boxes: load the chunks, give their entities time to load (they load after the
                # blocks), run the place function (it kills the old boxes, then summons), then count them. The place
                # function releases its own forceload at the end, which clears this step's too (a chunk is forced or
                # not, there is no count), so the chunks are held again for the count
                scene, (x0, z0, x1, z1), n = v
                hold = "%d %d %d %d" % (x0, z0, x1, z1)
                rc("forceload add " + hold)
                for _ in range(30):
                    if "passed" in rc("execute if loaded %d 64 %d" % (x0, z0)) and "passed" in rc("execute if loaded %d 64 %d" % (x1, z1)):
                        break
                    time.sleep(1)
                time.sleep(4)
                r = rc("function cobblers:scenes/%s/place" % scene)
                if not r.startswith("Running function"):
                    bad.append("%s props: %s" % (scene, r[:120]))
                rc("forceload add " + hold)
                time.sleep(2)
                box = "x=%d,y=-64,z=%d,dx=%d,dy=640,dz=%d" % (x0 - 1, z0 - 1, x1 - x0 + 2, z1 - z0 + 2)
                rc("execute store result storage cobblers:reapply props int 1 if entity "
                   "@e[type=minecraft:interaction,tag=cobblers_prop,%s]" % box)
                got = rc("data get storage cobblers:reapply props").rsplit(":", 1)[-1].strip()
                if got != str(n):
                    bad.append("%s: %s props standing, %d expected" % (scene, got, n))
                print("   %s: %s of %d props" % (scene, got, n), flush=True)
                rc("forceload remove " + hold)
            elif kind == "trainer":
                # an rctmod trainer, persistent, at its seat, once: one already standing there (a re-run) is left.
                # Pinned: an rctmod trainer strolls (RandomStrollAwayGoal), and on staging a mansion guardian had
                # climbed the grand stair within two minutes of being placed (2026-09-24). NoAI would also stop
                # ForceIntoBattleGoal, the goal that battles on sight, so the goals keep running with nowhere to go:
                # movement speed 0, which the entity saves with its attributes
                tid, (x, y, z), yaw = v
                rc("forceload add %d %d" % (x, z))
                for _ in range(30):
                    if "passed" in rc("execute if loaded %d %d %d" % (x, y, z)):
                        break
                    time.sleep(1)
                near = '@e[type=rctmod:trainer,x=%d,y=%d,z=%d,distance=..24,nbt={TrainerId:"%s"}]' % (x, y, z, tid)
                there = False
                for _ in range(12):
                    if "passed" in rc("execute if entity %s" % near):
                        there = True
                        break
                    time.sleep(0.5)
                if not there:
                    r = rc("rctmod trainer summon_persistent %s %d %d %d" % (tid, x, y, z))
                    print("   %s -> %s" % (tid, r[:120] or "(no reply)"), flush=True)
                    time.sleep(1)
                rc("tp %s %d.5 %d %d.5 %d 0" % (near, x, y, z, yaw))
                rc("execute as %s run attribute @s minecraft:generic.movement_speed base set 0" % near)
                # and unhurt: on staging a Channeler took damage in her own battle and could have been killed
                rc("data merge entity %s {Invulnerable:1b}" % near.replace("]", ",limit=1]"))
                rc("execute store result storage cobblers:reapply trainers int 1 if entity %s" % near)
                got = rc("data get storage cobblers:reapply trainers").rsplit(":", 1)[-1].strip()
                if got != "1":
                    bad.append("%s: %s trainers at %s, not 1" % (tid, got, (x, y, z)))
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
            elif kind == "check" and v == "rift_fx":
                # fx_go counts what it summoned into a score; the plan says how many there must be
                want = json.loads((ROOT / "derived" / "rift_skin" / "plan.json").read_text(encoding="utf-8"))["entities_expected"]
                got = None
                for _ in range(10):
                    r = rc("scoreboard players get #rift_fx_all cobblers.rift_fx")
                    m = re.search(r"has (\d+) ", r)
                    if m:
                        got = int(m.group(1))
                        if got == want:
                            break
                    time.sleep(2)
                print("   the Rift's entities: %s of %d" % (got, want), flush=True)
                if got != want:
                    bad.append("the Rift's entities: %s of %d summoned (cobblers:rift/fx)" % (got, want))
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
                # the sea town's decks, posts, huts and lanterns against its model, and no water standing on a deck
                r = subprocess.run([sys.executable, str(TOOLS / "sea_town.py"), "verify", "--rcon", a.server_dir],
                                   cwd=ROOT, capture_output=True, text=True)
                print("   sea town verify exit %d" % r.returncode, flush=True)
                if r.returncode:
                    bad.append("sea town verify: %s" % (r.stdout or r.stderr)[-400:])
        # save after every step: run 5's server ran out of memory at R17 and every step since its last autosave (R12,
        # R15, R16 and the lamps) was gone from the world although the run had reported each one done
        rc("save-all")
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
    # the sea town block by block against its model, water on a deck, flowing water round it (tools/sea_town.py)
    r = subprocess.run([sys.executable, str(TOOLS / "sea_town.py"), "verify", "--world", a.world], cwd=ROOT,
                       capture_output=True, text=True)
    res["sea_town"] = {"exit": r.returncode, "tail": (r.stdout or r.stderr).strip().splitlines()[-12:]}
    print("sea town exit", r.returncode)
    # the Deep's city and the relic area, sampled against the plan its build wrote (tools/deep_city.py verify)
    r = subprocess.run([sys.executable, str(TOOLS / "deep_city.py"), "verify", "--world", a.world], cwd=ROOT,
                       capture_output=True, text=True)
    res["deep_city"] = {"exit": r.returncode, "tail": (r.stdout or r.stderr).strip().splitlines()[-12:]}
    print("the Deep's city exit", r.returncode)
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
    res["lights"] = {"exit": r.returncode, "gate": False,
                     "tail": [l[:200] for l in r.stdout.strip().splitlines()]}
    print("lights (report only):", "0 dark everywhere" if r.returncode == 0 else
          "\n  ".join(l for l in res["lights"]["tail"] if " 0 at block light 0" not in l))
    # all() of nothing is True: the places audited must be every place the data plans, and there must be some.
    # Lighting remains in the report, but snow-layer cells can store light 0 while the lit air above them is safe in
    # play, and vanilla hostiles are disabled. It is evidence for builders, not a re-export gate.
    res["clean"] = (res["build_audit"]["exit"] == 0 and len(res["towns"]) == len(places()) > 0
                    and all(v["clean"] for v in res["towns"].values())
                    and res["signposts"]["exit"] == 0 and res["sea_town"]["exit"] == 0
                    and res["deep_city"]["exit"] == 0)
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
    q.add_argument("--source-root", default=env_source_root(), required=not env_source_root())
    q.add_argument("--server-dir", required=True)
    q.add_argument("--only", help="run only these jobs (comma separated, shell patterns: town:*,mines*); see --list")
    q.add_argument("--from", dest="from_job", help="run from this job to the end, after a failure")
    q.add_argument("--list", action="store_true", help="print the job names in order and stop")
    q = sub.add_parser("hydrate", help="only the inputs a fresh checkout lacks (local kits, Rift plan, paint, water "
                       "shape); an agent's worktree runs this first. Needs the lock only with --server-dir")
    q.add_argument("--source-root", default=env_source_root(), required=not env_source_root())
    q.add_argument("--server-dir", help="extract the jar-sourced kit files from this server's jars (takes the lock)")
    q.add_argument("--store", help="a folder holding the local-only kit files (default: COBBLERS_LOCAL_STORE)")
    q = sub.add_parser("install")
    q.add_argument("--server-dir", required=True)
    q.add_argument("--world-dir", required=True)
    q.add_argument("--no-players", action="store_true",
                   help="install into a staging world nobody has played, with no players carried")
    q.add_argument("--cobbleverse-dp", default=str(ROOT.parent.parent.parent / "COBBLEVERSE" / "datapacks"
                                                  / "COBBLEVERSE-DP-v31.zip")
                   if (ROOT.parent.parent.parent / "COBBLEVERSE").is_dir()
                   else str(ROOT / "COBBLEVERSE" / "datapacks" / "COBBLEVERSE-DP-v31.zip"),
                   help="the upstream COBBLEVERSE-DP-v31.zip (not committed: no-redistribution), patched at install")
    q = sub.add_parser("run")
    q.add_argument("--server-dir", required=True)
    q.add_argument("--from", dest="from_step")
    q.add_argument("--only")
    q.add_argument("--with-spawns", action="store_true", help="not yet part of the run: spawn pools are a separate decision")
    q.add_argument("--no-reload", action="store_true", help="skip the /reload: run straight after a boot, the packs are loaded")
    q = sub.add_parser("audit")
    q.add_argument("--server-dir", required=True)
    q.add_argument("--world", required=True)
    q.add_argument("--source-root", default=env_source_root(), help="heightmap root, for the light check")
    q = sub.add_parser("plan", help="print the steps and their commands without running anything")
    a = p.parse_args(argv)
    if a.cmd == "plan":
        for sid, title, actions in steps():
            print("%-4s %-60s %4d functions" % (sid, title, sum(1 for k, _ in actions if k == "fn")))
        print("places:", ", ".join(places()))
        return 0
    if a.cmd == "hydrate":
        if a.server_dir:
            runtime_guard.require_lock("reapply hydrate --server-dir")
        derived_inputs(a)
        return 0
    # Every subcommand but `plan` reads or writes the server or a world (prepare reads the installed packs' donor
    # templates; install writes the packs; run drives RCON; audit reads a world): the lock first, before anything.
    if a.cmd == "prepare" and a.list:                  # printing the job names reads nothing
        return prepare(a) or 0
    runtime_guard.require_lock("reapply %s" % a.cmd)
    if a.cmd == "run":
        require_watchdog_off(a.server_dir)             # before the first RCON command (REEXPORT.md step 5b)
    return {"carry": carry, "prepare": prepare, "install": install, "run": run, "audit": audit}[a.cmd](a) or 0


if __name__ == "__main__":
    raise SystemExit(main())

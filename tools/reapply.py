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
                # the Rift's own storm: thunder and lightning for players inside the Rift (2026-09-25)
                "cobblers_rift_storm")

# Packs that ship functions and deliberately have NO step, each with the reason. Anything not here and not run
# by a step makes `prepare` fail: that is the fail-closed check.
EXCLUDED = {
    "cobblers_reapply": "the loose-function container; its functions are run by the steps that own them",
    "cobblers_vr_backfill": "staging only: it buries schema 1's labyrinth, which a fresh export never has",
    "cobblers_restore": "disposable worlds only; install() deletes it if it is found",
    "cobblers_rift_fracture": "retired, replaced by the sculpt in the heightmap",
    "cobblers_worldtree": "a WORLD pack, installed into the world folder and run by R3",
    "cobblers_height": "a WORLD pack: it raises the build limit and runs nothing",
    "cobblers_suppress": "spawn data, no functions to run: generated and installed by `install` (SPAWN_PACKS)",
    # these three drive themselves and write no blocks: found by the check below the moment it was added
    "cobblers_progression": "self-driving: its own minecraft load and tick tags run it",
    "cobblers_sizes": "self-driving: its own minecraft load tag runs it",
    "cobblers_rift_storm": "self-driving: its own minecraft load tag starts the storm loop (tools/rift_storm.py)",
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
}
# server packs installed into the target world's own datapacks folder, not the server's: they act without being called
# (the scene runtime's tick; the trainers and event sites travel with it), and the global folder is loaded by every
# world the server runs, the live one included (qa review of EXP-034, 2026-09-24)
WORLD_LOCAL = ("cobblers_scenes", "cobblers_trainers", "cobblers_route_events", "cobblers_celebi", "cobblers_rift_storm")
# the wild spawns: our rosters (compile_spawns.py, at prepare) and the bounded suppression of inherited spawn files
# (suppress_inherited_spawns.py, at install, against the server and world); world packs, never global
SPAWN_PACKS = ("cobblers_spawns", "cobblers_suppress")
WORLD_PACKS = (ROOT / "modpack" / "datapacks" / "cobblers_height", PACKS / "cobblers_worldtree")
CROWN = (2044, 535, 2282)                      # the world tree's highest block (tools/build_audit.py world_tree)
CAVERN = ["00_seal", "02_shell", "05_reset", "10_excavate", "20_surfaces", "30_trees", "40_light", "50_tunnel", "70_drain", "15_cap", "60_biome"]
UNPLACED = {"hometown"}                          # has roads, not a town plan: placed by R7


def placements():
    return json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8"))


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
        if sid not in UNPLACED and (plan.get("streets") or plan.get("plaza") or plan.get("anchors")):
            ids.append(sid)
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
    # Victory Road: one cave network; its Habitat Block tiles and its finds are data the build checks against its
    # own model (`vr_caves.py records --write` writes them)
    py(TOOLS / "vr_caves.py", "build", *src)
    py(TOOLS / "habitat_blocks.py", "function")
    py(TOOLS / "rewards_pack.py")
    dlg = PACKS / "cobblers_dialogue"
    if dlg.exists():
        shutil.rmtree(dlg)
    # every conversation that compiles, in one pack: the NPCs', the props' and the actors' (refusals are listed)
    py(TOOLS / "compile_dialogue.py", "--all", "--out", dlg)
    # Routes 1-3: the event sites (it fails when data/scenes.json or data/route_trainers.json disagree with the
    # build, or anything stands on the walked line), then the scene runtime and the trainers
    py(TOOLS / "route_events.py", *src)
    py(TOOLS / "scenes_pack.py")
    py(TOOLS / "route_trainers.py")
    py(TOOLS / "rematerial.py")
    py(TOOLS / "place_town.py", "hometown", *src)
    for s in places():
        py(TOOLS / "town_plan.py", s, *src)
        py(TOOLS / "place_town.py", s, *src)
    py(TOOLS / "place_donor.py", "function", "--server-dir", a.server_dir)
    py(TOOLS / "traders.py", "function", "--server-dir", a.server_dir)
    py(TOOLS / "sapling_celebi.py")
    py(TOOLS / "rift_storm.py")
    py(TOOLS / "signposts.py", "function", *src)
    py(TOOLS / "location_titles.py")
    # the badge flags: one advancement per gym leader and the Champion, set by rctmod on a won battle
    py(TOOLS / "progression_pack.py")
    # our wild spawns: the route and sub-region rosters from data/spawns.json (the suppression that makes them the
    # only thing spawning there is generated at install, against the server and world it will run on)
    py(TOOLS / "compile_spawns.py")
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
    for name in SERVER_PACKS:
        # a pack that acts on its own (the scene runtime's tick) belongs to the world it was built for: the global
        # folder is loaded by every world this server runs, the live one included
        dest = (wdp if name in WORLD_LOCAL else dp) / name
        stale = dp / name if name in WORLD_LOCAL else None
        if stale is not None and stale.exists():
            shutil.rmtree(stale)
            print("removed", stale, "(it belongs in the world folder)")
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(PACKS / name, dest)
        print("installed", dest)
    for src in WORLD_PACKS:
        if (wdp / src.name).exists():
            shutil.rmtree(wdp / src.name)
        shutil.copytree(src, wdp / src.name)
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
        if (wdp / name).exists():
            shutil.rmtree(wdp / name)
        shutil.copytree(src, wdp / name)
        print("installed into the world folder", wdp / name)


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
    rehearsal found 0 of 14 in the world. Packs in EXCLUDED are skipped with their reason."""
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
            if f.suffix in (".mcfunction", ".json"):
                text.append(f.read_text(encoding="utf-8", errors="replace"))
    run = {v for _s, _t, acts in todo for k, v in acts if k == "fn"}
    if any(k == "props" for _s, _t, acts in todo for k, _v in acts):
        run |= {n for n in names if n.startswith("cobblers:scenes/") and n.endswith("/place")}
    referenced = set()
    for t in text:
        referenced.update(FUNCTION_REF.findall(t))
    return sorted(n for n, pack in names.items() if pack not in EXCLUDED and n not in run and n not in referenced)


def steps(with_spawns=False):
    """[(step id, title, [(kind, value)])]; kind is fn (a function), wait (seconds), check (a callable name)."""
    doc = placements()
    # the Rift's entities (the trailhead guards' placeholders and the portal sheets) after its blocks: fx force-loads
    # their chunks and schedules fx_go 60 ticks on, which summons them and counts them. No step ran it until the
    # 2026-09-24 rehearsal found 0 of 14 on a fresh export: they had been placed by hand on staging
    out = [("R1", "the Rift skin: the block pass over the sculpted shape, then its entities",
            [("fn", "cobblers:rift/%s" % f) for f in indexed("cobblers_rift", "rift")]
            + [("fn", "cobblers:rift/fx"), ("wait", 8), ("check", "rift_fx")]),
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
    out.append(("R9C", "Victory Road's caves, from the Deep's mouth to the ravine onto the League's apron",
                [("fn", "cobblers:vr_caves/%s" % f) for f in indexed("cobblers_vr_caves", "vr_caves")]))
    # the Habitat Blocks, after everything that builds the floors they sit in (R9C's shell pass overwrites them). A
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
    trad = json.loads((ROOT / "data" / "traders.json").read_text(encoding="utf-8"))
    towns = sorted({t["settlement"] for t in trad.get("traders") or [] if t.get("settlement")})
    out.append(("R14", "town traders", [x for t in towns for x in (("fn", "cobblers:towns/vendors_%s" % t), ("wait", 8))]))
    # the sleeping Celebi: an entity, so the export erased it; summoned over RCON because Cobblemon's spawn command
    # does nothing from a function (tools/sapling_celebi.py), then walled and dressed by its pack
    import sapling_celebi
    out.append(("R14C", "the Celebi in the Route 1 sapling", sapling_celebi.placement_steps(sapling_celebi.load())
                + [("check", "celebi")]))
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
        todo = [s for s in todo if s[0] == a.only]
    elif getattr(a, "from_step", None):
        todo = todo[ids.index(a.from_step):]
    if getattr(a, "no_reload", False):
        print("no reload: the packs loaded at boot (a second /reload on this pack stack exhausted a 10 GB heap twice on staging, 2026-09-24)")
    else:
        print("reload:", rc("reload"))
    # No drops while building. Every fill that replaces the block under a flower, a torch or a sapling pops it off as
    # an item, and a falling block that lands on a torch drops both: the owner picked up seeds, flowers and torches all
    # over staging after run 4 (2026-09-25). The rules come back as they were, even when a step stops the run.
    drops = {}
    for rule in DROP_RULES:
        m = re.search(r"(true|false)\s*$", str(rc("gamerule %s" % rule)))
        drops[rule] = m.group(1) if m else "true"
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
                    and res["signposts"]["exit"] == 0)
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
    q.add_argument("--no-reload", action="store_true", help="skip the /reload: run straight after a boot, the packs are loaded")
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
    if a.cmd == "run":
        require_watchdog_off(a.server_dir)             # before the first RCON command (REEXPORT.md step 5b)
    return {"carry": carry, "prepare": prepare, "install": install, "run": run, "audit": audit}[a.cmd](a) or 0


if __name__ == "__main__":
    raise SystemExit(main())

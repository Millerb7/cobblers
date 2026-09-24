#!/usr/bin/env python
"""Carry every player's state from a stopped old world into a fresh export, before the new world's first boot.

A re-export builds a new world directory. Without this step every player joins it with nothing: no party, PC,
Pokedex or money, no badge flags, no quest progress, and rctmod forgets which trainers they beat, which also resets
their level cap. It is a required step of the re-export (`tools/reapply.py carry`, docs/world-building/REEXPORT.md
step 4a), and `reapply.py install` refuses a world with no carried player unless told the world has none on purpose.

What is carried, per player (<uuid>), and where each mod keeps it (read from the jars and the worlds, 2026-09-21):

  CATEGORY             PATH IN THE WORLD                               REQUIRED  WHAT
  playerdata           playerdata/<uuid>.dat(_old)                     yes       inventory, position, ender chest;
                                                                                 also Waystones' activated waystones
                                                                                 (Balm persistent data, BalmData)
  advancements         advancements/<uuid>.json                        yes       the badge flags (cobblers:flag/*)
  stats                stats/<uuid>.json                               yes       statistics
  cobblemonplayerdata  cobblemonplayerdata/<xx>/<uuid>.json(.old)      yes       Cobblemon player data: starter, key
                                                                                 items, capture totals
  pokedex              pokedex/<xx>/<uuid>.nbt(.old)                   yes       the Pokedex (caught_count)
  pokemon              pokemon/<store>/<xx>/<uuid>.*                   yes       PC (pcstore) and party storage
  cobbledollars        cobbledollarsplayerdata/<uuid>.json             yes       CobbleDollars balance
  rctmod_player        data/rctmod.player.<uuid>.stat.dat              yes       series progress, level cap
  tm_moves             tm_moves/<xx>/<uuid>.nbt(.old)                  no        TMCraft's learned TMs
  cobblenav            cobblenav/**/<uuid>.nbt(.old)                   no        CobbleNav's per-player spawn data
  molang               playermolangdata/<uuid>.dat                     no        our quest_fields and dialogue
                                                                                 cursors (q.player.data(), EXP-022)

and, world-wide but about players: data/rctmod.trainers.* (each trainer's per-player defeat counts: required,
since rctmod writes rctmod.trainers.ver.dat on first boot) and data/scoreboard.dat (per-player scores).

Not carried: region, entity and POI files (the new terrain replaces them); waystones.dat (the waystones stand in new
places; a player's old activations, inside playerdata, name waystones the new world does not have, and the badge
flags re-activate the town waystones on join, tools/progression_pack.py); rctmod.spawn.chunks.map.dat (spawn
bookkeeping by chunk); Distant Horizons' cache.

Fails closed:
  - the old world has no player, a player lacks a required category, or any file to carry is empty;
  - the new world already holds any file of these categories (it is not a fresh export);
  - after the copy, any file's size or sha256 differs, the new world's player count differs, or any category's file
    count differs.

  python tools/carry_players.py --from <stopped old world copy> --to <new world> [--manifest <path>]
  python tools/carry_players.py --verify <manifest>        re-check a carry later (both worlds still in place)

Both worlds must be outside the live server runtime (tools/runtime_guard.py): the old world is the retired copy.
The manifest names files by UUID, so it goes under derived/ (gitignored), never into a document.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import runtime_guard  # noqa: E402

UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
# (category, glob under the world, required per player)
PER_PLAYER = (
    ("playerdata", "playerdata/*", True),
    ("advancements", "advancements/*", True),
    ("stats", "stats/*", True),
    ("cobblemonplayerdata", "cobblemonplayerdata/**/*", True),
    ("pokedex", "pokedex/**/*", True),
    ("pokemon", "pokemon/**/*", True),
    ("cobbledollars", "cobbledollarsplayerdata/*", True),
    ("rctmod_player", "data/rctmod.player.*", True),
    ("tm_moves", "tm_moves/**/*", False),
    ("cobblenav", "cobblenav/**/*", False),
    ("molang", "playermolangdata/**/*", False),
)
# (category, glob, required in the old world)
WORLD_WIDE = (
    ("rctmod_trainers", "data/rctmod.trainers.*", True),
    ("scoreboard", "data/scoreboard.dat", False),
)
DEFAULT_OUT = ROOT / "derived" / "reapply"
# The live run carries from the live world as it was retired a few minutes earlier (REEXPORT step 2), never from an
# older copy: a snapshot's players are days out of date, and carrying one would silently roll every player back. An
# old world last saved longer ago than this, or one of the retained snapshots (docs/world-building/SNAPSHOTS.md),
# is refused unless the carry is a rehearsal.
FRESH_HOURS = 12
REHEARSAL_SNAPSHOTS = ("2026-09-16-pre-rescale", "2026-09-17-pre-grass")


class CarryError(RuntimeError):
    pass


def _r(rel: str) -> str:
    """A path with its UUID cut to 8 characters: enough to find the file, not an identity to print."""
    return re.sub(UUID, lambda m: m.group(0)[:8] + "…", rel)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def players(world: Path) -> set:
    return {m.group(0) for p in (world / "playerdata").glob("*.dat") if (m := re.fullmatch(UUID, p.stem))}


def inventory(world: Path) -> dict:
    """{category: {relative path: (size, sha256)}} for every file of every category in `world`."""
    inv = {}
    for cat, pattern, _ in PER_PLAYER + WORLD_WIDE:
        files = {}
        for p in sorted(world.glob(pattern)):
            if p.is_file():
                files[p.relative_to(world).as_posix()] = (p.stat().st_size, sha(p))
        inv[cat] = files
    return inv


def check_old(world: Path, inv: dict) -> set:
    who = players(world)
    problems = []
    if not who:
        problems.append("no player in %s/playerdata: nothing to carry" % world)
    for cat, _, required in PER_PLAYER:
        have = {u for rel in inv[cat] for u in re.findall(UUID, rel)}
        if required:
            for u in sorted(who - have):
                problems.append("player %s… has no %s file" % (u[:8], cat))
    for cat, _, required in WORLD_WIDE:
        if required and not inv[cat]:
            problems.append("no %s file in the old world" % cat)
    empty = [rel for files in inv.values() for rel, (size, _) in files.items() if size == 0]
    problems += ["empty file: %s" % _r(rel) for rel in empty]
    if problems:
        raise CarryError("the old world cannot be carried:\n  " + "\n  ".join(problems))
    return who


def last_played(world: Path) -> float:
    """Seconds since the epoch when the world was last saved (level.dat Data.LastPlayed)."""
    import level_dat as L
    return L.plain(L.data_of(L.load(world / "level.dat")[1])["LastPlayed"]) / 1000.0


def check_source(old: Path, rehearsal: bool) -> None:
    snap = [part for part in old.parts if part in REHEARSAL_SNAPSHOTS]
    age_h = (time.time() - last_played(old)) / 3600.0
    if rehearsal:
        return
    if snap:
        raise CarryError("%s is the retained snapshot %s: a snapshot is for rehearsals only (--rehearsal). The live "
                         "run carries from the world retired in REEXPORT step 2" % (old, snap[0]))
    if age_h > FRESH_HOURS:
        raise CarryError("%s was last saved %.0f hours ago: the live run carries from the world retired minutes "
                         "ago (REEXPORT step 2), not an older copy. Pass --rehearsal to carry it anyway"
                         % (old, age_h))


def _flag_trainers() -> dict:
    """{flag id: [trainer ids]} for every flag a trainer defeat sets, from data/progression.json."""
    import progression_pack as PP
    p = PP.plan(PP.load(ROOT / "data" / "progression.json"),
                placements=json.loads((ROOT / "data" / "placements.json").read_text(encoding="utf-8")))
    return {f["id"]: f["trainer_ids"] for f in p["flags"] if f["kind"] == "trainer_defeat"}, p["namespace"]


def trainer_memory(world: Path) -> dict:
    """{trainer id: {player uuid: defeats}} from rctmod's trainer memory, data/rctmod.trainers.<n>.mem.dat
    (data.defeats), the record `/rctmod player set defeats` writes and the badge loot condition reads."""
    import nbt
    mem = {}
    for p in sorted((world / "data").glob("rctmod.trainers.*.mem*")):
        for t, by in nbt.load(p)[1]["data"]["defeats"].items():
            for u, n in by.items():
                mem.setdefault(t, {})[u] = mem.get(t, {}).get(u, 0) + int(n)
    return mem


def badge_agreement(world: Path) -> list:
    """Every disagreement, per player and flag, between the badge flag (advancements/<uuid>.json) and rctmod's two
    records of whom the player beat: series progress (data/rctmod.player.<uuid>.stat.dat, data.progressDefeats: a
    trainer's KEY there means beaten; its value is not a count, a first win stores 0) and trainer memory
    (data/rctmod.trainers.<n>.mem.dat, data.defeats[trainer][uuid] > 0). All three must agree. A flag without the
    defeat makes rctmod refuse the next leader (missing_required_trainer) while the world says the badge is earned; a
    defeat without the flag leaves the guards, traders and waystones closed to a player rctmod has let through; and
    the two rctmod records disagreeing is a half-carried or hand-edited player."""
    import nbt
    flags, ns = _flag_trainers()
    if not flags:
        return ["data/progression.json has no trainer-defeat flag: nothing to compare"]
    try:
        memory = trainer_memory(world)
    except (KeyError, TypeError, ValueError, OSError) as e:
        return ["rctmod trainer memory unreadable (%s)" % e]
    out = []
    for u in sorted(players(world)):
        adv_p = world / "advancements" / ("%s.json" % u)
        rct_p = world / "data" / ("rctmod.player.%s.stat.dat" % u)
        if not adv_p.is_file() or not rct_p.is_file():
            out.append("player %s…: %s missing, so its badges cannot be checked against rctmod"
                       % (u[:8], "advancements" if not adv_p.is_file() else "rctmod record"))
            continue
        adv = json.loads(adv_p.read_text(encoding="utf-8"))
        try:
            progress = nbt.load(rct_p)[1]["data"]["progressDefeats"]
        except (KeyError, TypeError, ValueError, OSError) as e:
            out.append("player %s…: rctmod record unreadable (%s)" % (u[:8], e))
            continue
        for fid, trainers in sorted(flags.items()):
            says = {"the flag": bool(adv.get("%s:flag/%s" % (ns, fid), {}).get("done")),
                    "rctmod's series progress": any(t in progress for t in trainers),
                    "rctmod's trainer memory": any(memory.get(t, {}).get(u, 0) > 0 for t in trainers)}
            if len(set(says.values())) > 1:
                out.append("player %s…: %s (%s) disagree: %s" % (
                    u[:8], fid, "/".join(trainers),
                    ", ".join("%s says %s" % (k, "beaten" if v else "not beaten") for k, v in says.items())))
    return out


def compare(old: Path, new: Path, before: dict) -> dict:
    """Every carried file in the new world, the same size and sha256 as before; counts per category and players."""
    problems = []
    counts = {}
    for cat, files in before.items():
        ok = 0
        for rel, (size, digest) in files.items():
            p = new / rel
            if not p.is_file():
                problems.append("missing after the copy: %s" % _r(rel))
            elif p.stat().st_size == 0:
                problems.append("empty after the copy: %s" % _r(rel))
            elif (p.stat().st_size, sha(p)) != (size, digest):
                problems.append("differs after the copy: %s" % _r(rel))
            else:
                ok += 1
        counts[cat] = {"before": len(files), "after": ok}
    who_old, who_new = players(old), players(new)
    if who_old != who_new:
        problems.append("players: %d in the old world, %d in the new" % (len(who_old), len(who_new)))
    problems += ["badges and rctmod disagree in the new world: " + d for d in badge_agreement(new)]
    if problems:
        raise CarryError("the carry is not complete:\n  " + "\n  ".join(problems))
    return {"players": len(who_new), "categories": counts}


def carry(old: Path, new: Path, manifest: Path | None = None, rehearsal: bool = False) -> dict:
    old = runtime_guard.check(old, "carry players from")
    new = runtime_guard.check(new, "carry players into")
    for w, what in ((old, "--from"), (new, "--to")):
        if not (w / "level.dat").is_file():
            raise CarryError("%s %s has no level.dat: not a world" % (what, w))
    if old == new:
        raise CarryError("--from and --to are the same world")
    check_source(old, rehearsal)
    before = inventory(old)
    who = check_old(old, before)
    already = badge_agreement(old)
    if already:
        raise CarryError("badges and rctmod already disagree in the old world; resolve it there (grant or revoke the "
                         "flag to match rctmod) before carrying:\n  " + "\n  ".join(already))
    present = inventory(new)
    clash = sorted(rel for files in present.values() for rel in files)
    if clash:
        raise CarryError("%d files of these categories already exist in %s (first: %s): not a fresh export"
                         % (len(clash), new, _r(clash[0])))
    for files in before.values():
        for rel in files:
            (new / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old / rel, new / rel)
    result = compare(old, new, before)
    record = {"carried": time.strftime("%Y-%m-%dT%H:%M:%S"), "from": str(old), "to": str(new), "rehearsal": rehearsal,
              "players": sorted(who), "files": before, **result}
    manifest = manifest or DEFAULT_OUT / ("carry_%s.json" % time.strftime("%Y%m%d_%H%M%S"))
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(record, indent=1), encoding="utf-8")
    result["manifest"] = str(manifest)
    return result


def verify(manifest: Path) -> dict:
    rec = json.loads(manifest.read_text(encoding="utf-8"))
    old = runtime_guard.check(rec["from"], "verify a carry from")
    new = runtime_guard.check(rec["to"], "verify a carry into")
    before = {cat: {rel: tuple(v) for rel, v in files.items()} for cat, files in rec["files"].items()}
    if not before or not any(before.values()):
        raise CarryError("the manifest lists no files: nothing was carried")
    return compare(old, new, before)


def summary(result: dict) -> str:
    cats = ", ".join("%s %d" % (c, v["after"]) for c, v in result["categories"].items() if v["before"])
    none = [c for c, v in result["categories"].items() if not v["before"]]
    return ("%d players, every file present, non-empty and matching by sha256: %s%s"
            % (result["players"], cats, ("; none in the old world: " + ", ".join(none)) if none else ""))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--from", dest="old", type=Path, help="the stopped old world copy")
    ap.add_argument("--to", dest="new", type=Path, help="the fresh export, before its first boot")
    ap.add_argument("--manifest", type=Path, help="where to write the record (default derived/reapply/carry_<time>.json)")
    ap.add_argument("--verify", type=Path, metavar="MANIFEST", help="re-check an earlier carry")
    ap.add_argument("--rehearsal", action="store_true",
                    help="allow a retained snapshot or an old copy as the source (staging only, never the live run)")
    a = ap.parse_args(argv)
    try:
        if a.verify:
            print("verified: " + summary(verify(a.verify)))
        elif a.old and a.new:
            r = carry(a.old, a.new, a.manifest, a.rehearsal)
            print("carried: " + summary(r))
            print("manifest:", r["manifest"])
        else:
            ap.error("give --from and --to, or --verify")
    except (CarryError, runtime_guard.RuntimeAccessRefused) as e:
        print("FAIL: %s" % e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

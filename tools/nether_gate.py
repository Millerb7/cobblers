#!/usr/bin/env python
"""Generate the Nether's badge-8 gate from data/nether_gate.json: a player without the eighth badge is sent back.

docs/mechanics/NETHER_ENCOUNTERS.md section 1 G1, approved by the owner. The rung and every choice is recorded in
data/nether_gate.json; the runtime proofs are experiments/EXP-063-nether-gate.

THE LOOP. Two ways in, one judgement:
  arrived  an advancement on vanilla's minecraft:changed_dimension `to` the Nether. Its reward revokes itself and
           schedules the sweep for the NEXT tick (never a teleport from inside the dimension change).
  keeper   every period_ticks, the sweep: the backstop for a respawn, a login or any route the trigger misses.
  sweep    `execute in` the Nether, as every player inside an absolute box larger than any Nether (positional, so
           vanilla searches that dimension only: EXP-047 result 4), not creative or spectator, WITHOUT the flag ->
           bounce. A flag holder is never selected; a player in cobblers:pocket (the Entei rooms) is never selected.
  bounce   as that player: dismount, the line, then the blackout's checkpoint (validate, then its own tp macro); and
           the net: a positional check in the Nether finds them if they are still there, and sends them to the
           pallet by literal coordinates, which need no other pack. So the bounce cannot leave anyone in the Nether.

Cross-pack: it CALLS cobblers:blackout/checkpoint/validate, /tp and /name and reads bo.ok, bo.cpx, bo.cpy and bo.cpz
(tools/blackout_pack.py). It never writes them. Contract C20 in data/system_contracts.json.

What it does NOT cover is data/nether_gate.json does_not_cover.

  python tools/nether_gate.py                 # write build/datapacks/cobblers_nether_gate
  python tools/nether_gate.py --out <dir>

Ownership: the output is generated and lives in build/ (gitignored); data/nether_gate.json is the source.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import function_limits  # noqa: E402

DATA = ROOT / "data" / "nether_gate.json"
PROGRESSION = ROOT / "data" / "progression.json"
BLACKOUT = ROOT / "data" / "blackout.json"
PORTALS = ROOT / "data" / "portals.json"
ENTEI = ROOT / "data" / "entei_boss.json"
WORLD = ROOT / "data" / "world.json"
DEFAULT_OUT = ROOT / "build" / "datapacks" / "cobblers_nether_gate"
SCHEMA = "cobblers.nether_gate/1"
PACK_FORMAT = 48  # Minecraft 1.21.1
NS = "cobblers"
BADGE = 8
NETHER = "minecraft:the_nether"
OVERWORLD = "minecraft:overworld"
STORE = "cobblers:nether_gate"
# the blackout pack's checkpoint (tools/blackout_pack.py blackout/checkpoint/*): read and called, never written
BO_VALIDATE = "cobblers:blackout/checkpoint/validate"
BO_TP = "cobblers:blackout/checkpoint/tp"
BO_NAME = "cobblers:blackout/checkpoint/name"
BO_OK, BO_X, BO_Y, BO_Z = "bo.ok", "bo.cpx", "bo.cpy", "bo.cpz"
BO_PLACE = ("cobblers:blackout", "place")
# vanilla's dimension_type limits: min_y >= -2032, min_y + height <= 2032; the world's x/z limit is 30,000,000
Y_LIMIT, XZ_LIMIT = 2032, 30_000_000
OBJ_RE = re.compile(r"^[a-z0-9_.]{1,16}$")
TAG_RE = re.compile(r"^[a-z0-9_.]+$")


class GateError(ValueError):
    pass


def _j(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load(path=DATA):
    doc = _j(path)
    if doc.get("schema") != SCHEMA:
        raise GateError("%s: schema must be %s" % (path, SCHEMA))
    return doc


def badge_flag(progression):
    """The advancement data/progression.json makes the eighth badge, or None if it does not declare one."""
    want = "gym%d_cleared" % BADGE
    for f in progression.get("flags", []):
        if f.get("id") == want and (f.get("set_by") or {}).get("kind") == "trainer_defeat":
            return "%s:flag/%s" % (progression["namespace"], want)
    return None


def problems(doc, progression=None, blackout=None, portals=None, entei=None, world=None, ground=None):
    """Every reason the data cannot make a gate that gates the right players and can never trap one. ground, if
    given, is tools/ground.py's callable: the pallet must stand one block above the rounded canonical heightmap."""
    progression = progression if progression is not None else _j(PROGRESSION)
    blackout = blackout if blackout is not None else _j(BLACKOUT)
    portals = portals if portals is not None else _j(PORTALS)
    entei = entei if entei is not None else _j(ENTEI)
    world = world if world is not None else _j(WORLD)
    bad = []
    flag = badge_flag(progression)
    if flag is None:
        bad.append("data/progression.json declares no trainer_defeat flag gym%d_cleared" % BADGE)
    elif doc.get("gate_flag") != flag:
        bad.append("gate_flag %r is not the eighth badge's advancement %r" % (doc.get("gate_flag"), flag))
    if doc.get("dimension") != NETHER:
        bad.append("dimension must be %s, not %r" % (NETHER, doc.get("dimension")))
    for name, dim in (("data/portals.json pocket", portals["pocket"]["dimension"]),
                      ("data/entei_boss.json pocket", entei["pocket"]["dimension"])):
        if dim == doc.get("dimension") or dim == OVERWORLD:
            bad.append("%s dimension %s must be neither the gated dimension nor the overworld" % (name, dim))
    crit = doc["trigger"]["criterion"]
    if crit != {"trigger": "minecraft:changed_dimension", "conditions": {"to": doc.get("dimension")}}:
        bad.append("trigger.criterion must be changed_dimension to %s and nothing else: %r" % (doc.get("dimension"), crit))
    p = int(doc["sweep"]["period_ticks"])
    if not 1 <= p <= 200:
        bad.append("sweep.period_ticks %d outside 1..200 (the backstop must run at least every ten seconds)" % p)
    x, y, z, dx, dy, dz = sweep_box(doc)
    if not (x <= -XZ_LIMIT and x + dx >= XZ_LIMIT and z <= -XZ_LIMIT and z + dz >= XZ_LIMIT):
        bad.append("sweep.box x/z must cover -%d..%d, every column of any dimension" % (XZ_LIMIT, XZ_LIMIT))
    if not (y <= -Y_LIMIT and y + dy >= Y_LIMIT):
        bad.append("sweep.box y must cover -%d..%d, every block of any dimension type" % (Y_LIMIT, Y_LIMIT))
    ex = doc["exempt_gamemodes"]
    if not set(ex) <= {"creative", "spectator"}:
        bad.append("exempt_gamemodes may name only creative and spectator: %r" % ex)
    for k, v in doc["objectives"].items():
        if not OBJ_RE.match(v):
            bad.append("objective %s %r is not a valid objective name" % (k, v))
    if not TAG_RE.match(doc["tags"]["bouncing"]):
        bad.append("tags.bouncing %r is not a valid tag" % doc["tags"]["bouncing"])
    for k in ("bounce", "where"):
        if not isinstance(doc["message"].get(k), str) or not doc["message"][k]:
            bad.append("message.%s must be a non-empty string" % k)
    pal = blackout["pallet"]["position"]
    if len(pal) != 3 or not all(isinstance(v, int) for v in pal):
        bad.append("data/blackout.json pallet.position must be three integers: %r" % pal)
    else:
        b = world["bounds"]
        if not (b["min_x"] <= pal[0] <= b["max_x"] and b["min_z"] <= pal[2] <= b["max_z"]):
            bad.append("the pallet %r is outside the map's bounds %r" % (pal, b))
        elif ground is not None and pal[1] != ground(pal[0], pal[2]) + 1:
            bad.append("the pallet %r does not stand on the canonical ground: round(ground) + 1 is %d"
                       % (pal, ground(pal[0], pal[2]) + 1))
    return bad


# ------------------------------------------------------------------------------------------------- the pack


def _fn(name):
    return "%s:nether_gate/%s" % (NS, name)


def sweep_box(doc):
    """The sweep's selector volume as x, y, z, dx, dy, dz, from data/nether_gate.json sweep.box {corner, size}."""
    b = doc["sweep"]["box"]
    return list(b["corner"]) + list(b["size"])


def _box(box):
    return "x=%d,y=%d,z=%d,dx=%d,dy=%d,dz=%d" % tuple(box)


def functions(doc, blackout=None):
    blackout = blackout if blackout is not None else _j(BLACKOUT)
    o, m, tag = doc["objectives"], doc["message"], doc["tags"]["bouncing"]
    B, OK = o["bounces"], o["ok"]
    dim, flag, period = doc["dimension"], doc["gate_flag"], int(doc["sweep"]["period_ticks"])
    pal = blackout["pallet"]["position"]
    adv = doc["trigger"]["advancement"]
    head = "# Generated by tools/nether_gate.py from data/nether_gate.json; never edit (build/ is regenerated)."
    who = ",".join(["gamemode=!%s" % g for g in doc["exempt_gamemodes"]] + ["advancements={%s=false}" % flag])
    where = {"text": m["where"], "color": "gray", "italic": True}

    out = {}
    out["load"] = [head] + ["scoreboard objectives add %s dummy" % v for v in o.values()] + [
        "schedule function %s %dt replace" % (_fn("keeper"), period)]
    out["keeper"] = [
        head,
        "# every %d ticks: the backstop sweep (a respawn, a login, any arrival the trigger did not see)" % period,
        "function %s" % _fn("sweep"),
        "schedule function %s %dt replace" % (_fn("keeper"), period)]
    out["sweep"] = [
        head,
        "# every player in %s, wherever they stand: the box is larger than any dimension, and only makes the" % dim,
        "# selector positional, so vanilla searches this dimension alone (EXP-047 result 4). cobblers:pocket is",
        "# never searched. A holder of %s, or a creative or spectator player, is never selected." % flag,
        "execute in %s as @a[%s,%s] run function %s" % (dim, _box(sweep_box(doc)), who, _fn("bounce"))]
    out["arrived"] = [
        head,
        "# the reward of %s (changed_dimension to %s), as the arriving player. Revoked so it fires" % (adv, dim),
        "# again next time; the sweep runs NEXT tick, outside the dimension change, and judges everyone there.",
        "advancement revoke @s only %s" % adv,
        "schedule function %s 1t replace" % _fn("sweep")]
    out["bounce"] = [
        head,
        "# As a player in %s without %s (the sweep chose them). Out, to the overworld, always." % (dim, flag),
        "tag @s add %s" % tag,
        "ride @s dismount",
        "execute on passengers run ride @s dismount",
        "scoreboard players add @s %s 1" % B,
        "tellraw @s %s" % json.dumps({"text": m["bounce"], "color": "gold", "italic": True}, ensure_ascii=False),
        "# the blackout's own checkpoint, validated by the blackout (tools/blackout_pack.py); read, never written",
        "scoreboard players set @s %s 0" % OK,
        "function %s" % BO_VALIDATE,
        "execute if score @s %s matches 1 run scoreboard players set @s %s 1" % (BO_OK, OK),
        "execute if score @s %s matches 1 run function %s" % (OK, _fn("to_checkpoint")),
        "# the net: still in %s (no checkpoint, or the checkpoint path failed)? The pallet, by literal" % dim,
        "# coordinates. A positional selector, so it finds them only if they are still in this dimension.",
        "execute in %s positioned as @s as @a[tag=%s,distance=..1] run function %s" % (dim, tag, _fn("to_pallet")),
        "execute if score @s %s matches 1 run function %s" % (OK, BO_NAME),
        "execute if score @s %s matches 1 run tellraw @s %s" % (OK, json.dumps(
            ["", where, {"storage": BO_PLACE[0], "nbt": BO_PLACE[1], "color": "white"}, {"text": "."}],
            ensure_ascii=False)),
        "execute if score @s %s matches 0 run tellraw @s %s" % (OK, json.dumps(
            ["", where, {"text": blackout["pallet"]["name"], "color": "white"}, {"text": "."}], ensure_ascii=False)),
        "tag @s remove %s" % tag]
    out["to_checkpoint"] = [
        head,
        "# the blackout's checkpoint, as the blackout itself reaches it (blackout/arrive: the stored scores into its",
        "# tp macro, which names the overworld)",
        "execute store result storage %s go.x int 1 run scoreboard players get @s %s" % (STORE, BO_X),
        "execute store result storage %s go.y int 1 run scoreboard players get @s %s" % (STORE, BO_Y),
        "execute store result storage %s go.z int 1 run scoreboard players get @s %s" % (STORE, BO_Z),
        "function %s with storage %s go" % (BO_TP, STORE)]
    out["to_pallet"] = [
        head,
        "# data/blackout.json pallet.position, read at generation; feet on the rounded canonical ground (checked)",
        "scoreboard players set @s %s 0" % OK,
        "execute in %s run tp @s %d.5 %d %d.5" % (OVERWORLD, pal[0], pal[1], pal[2])]
    return out


def arrived_advancement(doc):
    return {"criteria": {"arrived": doc["trigger"]["criterion"]}, "requirements": [["arrived"]],
            "rewards": {"function": _fn("arrived")}}


def build(doc, **kw):
    bad = problems(doc, **kw)
    if bad:
        raise GateError("data/nether_gate.json: " + "; ".join(bad))
    files = {
        "pack.mcmeta": json.dumps({"pack": {"pack_format": PACK_FORMAT, "description":
                                            "Cobblers: the Nether's badge-8 gate (tools/nether_gate.py)"}},
                                  indent=2) + "\n",
        "data/minecraft/tags/function/load.json": json.dumps({"values": [_fn("load")]}, indent=2) + "\n",
    }
    ns, path = doc["trigger"]["advancement"].split(":", 1)
    files["data/%s/advancement/%s.json" % (ns, path)] = json.dumps(arrived_advancement(doc), indent=2) + "\n"
    for name, lines in functions(doc, kw.get("blackout")).items():
        rel = "data/%s/function/nether_gate/%s.mcfunction" % (NS, name)
        refused = function_limits.check_lines(lines, rel)
        if refused:
            for ln, cmd, why in refused:
                print("REFUSED %s line %d: %s\n   %s" % (rel, ln, why, cmd))
            raise SystemExit("%s: %d command(s) the server would refuse; nothing written" % (rel, len(refused)))
        files[rel] = "\n".join(lines) + "\n"
    return files


def write(files, out):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    for rel, text in files.items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--data", default=str(DATA))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    a = p.parse_args(argv)
    import ground as G
    files = build(load(a.data), ground=G.load())
    write(files, a.out)
    print("cobblers_nether_gate: %d files -> %s" % (len(files), a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())

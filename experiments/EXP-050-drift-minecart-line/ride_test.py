"""EXP-050 ride test: a minecart carrying a NoAI villager, launched by the stop's own button, ridden end to end both
ways with the line force-loaded. Fails on a stall away from the far stop, a derailment (off z 1795), or the passenger
leaving. Run with the server up and the owner offline from the line."""
import sys, time, re
sys.path.insert(0, "C:/Users/wnd/Documents/github/cobblers/.claude/worktrees/cobblers-cobblemon-session-start-531d15/tools")
import reapply

r = reapply.Rcon("C:/Users/wnd/Documents/github/cobblers-server")
def go(c):
    return (r(c, timeout=60) or "").strip()

EAST = (1461, 113, 1795)     # Foothill Gate stop
WEST = (325, 70, 1795)       # Driftmouth Light stop
BUTTON = "minecraft:stone_button"
TAG = "cobblers_ridetest"
CART = "@e[type=minecraft:minecart,tag=%s,limit=1]" % TAG

def pos():
    out = go("data get entity %s Pos" % CART)
    m = re.findall(r"(-?[\d.]+)d", out)
    return tuple(float(v) for v in m[:3]) if len(m) >= 3 else None

def rider():
    return "villager" in go("data get entity %s Passengers[0].id" % CART)

def ride(start, end, label):
    go("kill @e[tag=%s]" % TAG)
    sx, sy, sz = start
    go('summon minecraft:minecart %.1f %d %.1f {Tags:["%s"],Passengers:[{id:"minecraft:villager",NoAI:1b,'
       'PersistenceRequired:1b,Invulnerable:1b,Tags:["%s"]}]}' % (sx + 0.5, sy, sz + 0.5, TAG, TAG))
    time.sleep(2)
    p0 = pos()
    if p0 is None:
        return "%s: FAIL - no cart after summon" % label
    # press the stop's own button: find its facing from the world, set it powered, release after 1.5 s
    bx, by, bz = sx, sy, sz + 1
    facing = None
    for f in ("east", "west", "north", "south"):
        if go("execute if block %d %d %d %s[face=floor,facing=%s]" % (bx, by, bz, BUTTON, f)).startswith("Test passed"):
            facing = f
            break
    if facing is None:
        return "%s: FAIL - no stone button at (%d, %d, %d)" % (label, bx, by, bz)
    go("setblock %d %d %d %s[face=floor,facing=%s,powered=true]" % (bx, by, bz, BUTTON, facing))
    time.sleep(1.5)
    go("setblock %d %d %d %s[face=floor,facing=%s,powered=false]" % (bx, by, bz, BUTTON, facing))
    t0, last, still, track = time.time(), p0, 0, []
    while time.time() - t0 < 420:
        time.sleep(5)
        p = pos()
        if p is None:
            return "%s: FAIL - cart gone near %s after %.0f s" % (label, last, time.time() - t0)
        track.append((round(time.time() - t0), round(p[0], 1), round(p[1], 1), round(p[2], 1)))
        if abs(p[2] - (sz + 0.5)) > 1.0:
            return "%s: FAIL - off the line at %s (%.0f s)" % (label, p, time.time() - t0)
        if not rider():
            return "%s: FAIL - passenger gone at %s (%.0f s)" % (label, p, time.time() - t0)
        if abs(p[0] - (end[0] + 0.5)) <= 2.5 and abs(p[1] - end[1]) <= 1.5:
            return "%s: PASS - at the far stop %s in %.0f s, passenger aboard; track %s" % (
                label, tuple(round(v, 1) for v in p), time.time() - t0, track)
        moved = abs(p[0] - last[0]) + abs(p[1] - last[1])
        still = still + 1 if moved < 0.5 else 0
        if still >= 2:
            return "%s: FAIL - stalled at %s (%.0f s); track %s" % (label, p, time.time() - t0, track)
        last = p
    return "%s: FAIL - not arrived after 420 s, last %s" % (label, last)

go("forceload add 320 1790 1470 1800")
time.sleep(10)
try:
    print(ride(EAST, WEST, "gate -> isle"))
    print(ride(WEST, EAST, "isle -> gate"))
finally:
    go("kill @e[tag=%s]" % TAG)
    go("forceload remove 320 1790 1470 1800")

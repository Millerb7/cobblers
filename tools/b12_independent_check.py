"""Independent check of the B12 gatehouse fix. Written by the integrating session, parsing only the
emitted .mcfunction text -- it shares no code with tools/rift_zones.py."""
import sys, re, collections
from pathlib import Path

PASSABLE = {"air", "cave_air", "void_air", "water", "light"}   # barrier is SOLID to a player

def blocks(path):
    """{(x,y,z): block} the function leaves behind, applied in order."""
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"): continue
        t = line.split()
        if t[0] == "fill" and len(t) >= 8:
            a = list(map(int, t[1:4])); b = list(map(int, t[4:7])); blk = t[7].split("[")[0].split("{")[0]
            if len(t) > 8 and t[8] in ("replace", "keep", "destroy", "outline", "hollow"):
                pass
            for x in range(min(a[0],b[0]), max(a[0],b[0])+1):
                for y in range(min(a[1],b[1]), max(a[1],b[1])+1):
                    for z in range(min(a[2],b[2]), max(a[2],b[2])+1):
                        out[(x,y,z)] = blk
        elif t[0] == "setblock" and len(t) >= 5:
            out[(int(t[1]),int(t[2]),int(t[3]))] = t[4].split("[")[0].split("{")[0]
    return out

def solid(b): return b is not None and b.replace("minecraft:","") not in PASSABLE

def standable(bm, open_barrier=False):
    """feet cells: solid under, two passable at feet and head."""
    def at(p):
        b = bm.get(p)
        if b is None: return None
        n = b.replace("minecraft:","")
        if open_barrier and n == "barrier": return "air"
        return n
    cells = set()
    for (x,y,z) in bm:
        f = at((x,y,z)); h = at((x,y+1,z)); u = at((x,y-1,z))
        if f is None or h is None or u is None: continue
        if f in PASSABLE and h in PASSABLE and u not in PASSABLE:
            cells.add((x,y,z))
    return cells

def pieces(cells):
    """4-connected, allowing a 1-block step up or down."""
    seen=set(); n=0
    byxz = collections.defaultdict(set)
    for (x,y,z) in cells: byxz[(x,z)].add(y)
    for c in cells:
        if c in seen: continue
        n+=1; stack=[c]; seen.add(c)
        while stack:
            x,y,z = stack.pop()
            for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
                for dy in (0,1,-1):
                    p=(x+dx,y+dy,z+dz)
                    if p in cells and p not in seen:
                        seen.add(p); stack.append(p)
    return n

for d in sys.argv[1:]:
    print("==", Path(d).name)
    for f in sorted(Path(d).glob("gatehouse_*.mcfunction")):
        bm = blocks(f)
        s = standable(bm); so = standable(bm, open_barrier=True)
        nb = sum(1 for v in bm.values() if "barrier" in v)
        # 1-wide check: walkway neighbours of each standable cell
        maxn = 0
        for (x,y,z) in s:
            k = sum(1 for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)) for dy in (0,1,-1) if (x+dx,y+dy,z+dz) in s)
            maxn = max(maxn,k)
        print("   %-34s blocks %4d  standable %3d  pieces %d  pieces(barrier open) %d  max walkway neighbours %d"
              % (f.stem, len(bm), len(s), pieces(s), pieces(so), maxn))

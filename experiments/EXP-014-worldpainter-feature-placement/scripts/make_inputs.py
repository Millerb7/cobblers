#!/usr/bin/env python
"""EXP-014 inputs: flat height map, biome mask, and hand-made Cobblemon objects.

Writes into the directory given as argv[1]:
  heightmap.png            256x256 8-bit grey, value 80 everywhere (terrain y=80)
  biomemask.png            256x256 8-bit grey, x<128 -> 255 (forest), x>=128 -> 0 (plains)
  objects/apricorn_v2.schem  Sponge schematic v2: apricorn log/leaves, red apricorn, oran berry + block entity
  objects/apricorn_v3.schem  same content as Sponge schematic v3 (block entity data nested under "Data")
  objects/oran_bush.nbt      vanilla structure template: grass + oran berry + block entity
  objects/berry_patch10.nbt  (only if argv[2] = Cobblemon 1.8.0 jar) copied unchanged from the jar
Standard library only.
"""
import gzip
import struct
import sys
import zlib
from pathlib import Path

END, BYTE, SHORT, INT, LONG, FLOAT, DOUBLE, BYTE_ARRAY, STRING, LIST, COMPOUND, INT_ARRAY, LONG_ARRAY = range(13)


# --- minimal typed NBT writer -------------------------------------------------------------
class T:
    def __init__(self, tag, value, inner=None):
        self.tag, self.value, self.inner = tag, value, inner


def _payload(t: T) -> bytes:
    tag, v = t.tag, t.value
    if tag == BYTE:
        return struct.pack(">b", v)
    if tag == SHORT:
        return struct.pack(">h", v)
    if tag == INT:
        return struct.pack(">i", v)
    if tag == LONG:
        return struct.pack(">q", v)
    if tag == BYTE_ARRAY:
        return struct.pack(">i", len(v)) + bytes(v)
    if tag == STRING:
        b = v.encode("utf-8")
        return struct.pack(">H", len(b)) + b
    if tag == LIST:
        out = struct.pack(">bi", t.inner if v else END, len(v))
        return out + b"".join(_payload(x) for x in v)
    if tag == COMPOUND:
        out = b""
        for k, x in v.items():
            kb = k.encode("utf-8")
            out += struct.pack(">bH", x.tag, len(kb)) + kb + _payload(x)
        return out + b"\x00"
    if tag == INT_ARRAY:
        return struct.pack(">i%di" % len(v), len(v), *v)
    raise ValueError(tag)


def write_nbt(path, root_name, compound: dict):
    rb = root_name.encode("utf-8")
    data = struct.pack(">bH", COMPOUND, len(rb)) + rb + _payload(T(COMPOUND, compound))
    Path(path).write_bytes(gzip.compress(data))


S = lambda s: T(STRING, s)
I = lambda i: T(INT, i)
C = lambda d: T(COMPOUND, d)


# --- PNG writer (8-bit greyscale) ----------------------------------------------------------
def write_grey_png(path, w, h, pixel):
    raw = b"".join(b"\x00" + bytes(pixel(x, y) for x in range(w)) for y in range(h))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    Path(path).write_bytes(png)


# --- object content ------------------------------------------------------------------------
W, H, L = 5, 6, 5  # x, y (height), z
BERRY_STATE = "cobblemon:oran_berry[age=5,generated=true,mulch=none,rooted=false]"
BERRY_POS = (4, 0, 4)
# Block entity fields copied from cobblemon:berry entries in Cobblemon 1.8.0 habitats/berry_patch10.nbt
BERRY_BE = {
    "Berry": S("cobblemon:oran_berry"),
    "GrowthPoints": T(LIST, [S("cobblemon:oran_berry"), S("cobblemon:oran_berry")], STRING),
    "GrowthPointsSequence": S("ED8A0135CFB46279"),
    "GrowthTimer": I(0),
    "LastTickTime": T(LONG, 0),
    "MulchDuration": I(0),
    "MulchVariant": S("NONE"),
    "StageTimer": I(0),
}


def object_blocks():
    """Return {(x,y,z): 'state string'} for the hand-made apricorn tree + oran berry."""
    b = {}
    for y in range(0, 4):
        b[(2, y, 2)] = "cobblemon:apricorn_log[axis=y]"
    for y in (3, 4):
        for x in range(0, 5):
            for z in range(0, 5):
                if (x, z) in ((0, 0), (0, 4), (4, 0), (4, 4)):
                    continue
                if (x, y, z) not in b:
                    b[(x, y, z)] = "cobblemon:apricorn_leaves"
    for x in range(1, 4):
        for z in range(1, 4):
            b[(x, 5, z)] = "cobblemon:apricorn_leaves"
    b[(2, 2, 0)] = "cobblemon:red_apricorn[age=3,facing=south]"
    b[BERRY_POS] = BERRY_STATE
    return b


def varint(n):
    out = bytearray()
    while True:
        byte = n & 0x7F
        n >>= 7
        if n:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def schem(path, version):
    blocks = object_blocks()
    palette = {"minecraft:air": 0}
    for s in blocks.values():
        palette.setdefault(s, len(palette))
    data = bytearray()
    for y in range(H):
        for z in range(L):
            for x in range(W):
                data += varint(palette[blocks.get((x, y, z), "minecraft:air")])
    pal = C({k: I(v) for k, v in palette.items()})
    be_fields = dict(BERRY_BE)
    if version == 2:
        be = C(dict(Pos=T(INT_ARRAY, list(BERRY_POS)), Id=S("cobblemon:berry"), **be_fields))
        root = {
            "Version": I(2), "DataVersion": I(3955),
            "Width": T(SHORT, W), "Height": T(SHORT, H), "Length": T(SHORT, L),
            "Palette": pal, "PaletteMax": I(len(palette)),
            "BlockData": T(BYTE_ARRAY, data),
            "BlockEntities": T(LIST, [be], COMPOUND),
            "Offset": T(INT_ARRAY, [0, 0, 0]),
        }
        write_nbt(path, "Schematic", root)
    else:
        be = C({"Pos": T(INT_ARRAY, list(BERRY_POS)), "Id": S("cobblemon:berry"), "Data": C(be_fields)})
        inner = {
            "Version": I(3), "DataVersion": I(3955),
            "Width": T(SHORT, W), "Height": T(SHORT, H), "Length": T(SHORT, L),
            "Offset": T(INT_ARRAY, [0, 0, 0]),
            "Blocks": C({"Palette": pal, "Data": T(BYTE_ARRAY, data), "BlockEntities": T(LIST, [be], COMPOUND)}),
        }
        write_nbt(path, "", {"Schematic": C(inner)})


def structure_nbt(path):
    def parse(state):
        if "[" not in state:
            return state, {}
        name, props = state[:-1].split("[", 1)
        return name, dict(p.split("=") for p in props.split(","))

    content = {(0, 0, 0): "minecraft:grass_block[snowy=false]", (0, 1, 0): BERRY_STATE}
    palette, blocks = [], []
    for pos, state in content.items():
        name, props = parse(state)
        entry = {"Name": S(name)}
        if props:
            entry["Properties"] = C({k: S(v) for k, v in props.items()})
        palette.append(C(entry))
        blk = {"pos": T(LIST, [I(p) for p in pos], INT), "state": I(len(palette) - 1)}
        if name == "cobblemon:oran_berry":
            blk["nbt"] = C(dict(id=S("cobblemon:berry"), **BERRY_BE))
        blocks.append(C(blk))
    write_nbt(path, "", {
        "DataVersion": I(3955),
        "size": T(LIST, [I(1), I(2), I(1)], INT),
        "palette": T(LIST, palette, COMPOUND),
        "blocks": T(LIST, blocks, COMPOUND),
        "entities": T(LIST, [], COMPOUND),
    })


if __name__ == "__main__":
    out = Path(sys.argv[1])
    (out / "objects").mkdir(parents=True, exist_ok=True)
    write_grey_png(out / "heightmap.png", 256, 256, lambda x, y: 80)
    write_grey_png(out / "biomemask.png", 256, 256, lambda x, y: 255 if x < 128 else 0)
    schem(out / "objects" / "apricorn_v2.schem", 2)
    schem(out / "objects" / "apricorn_v3.schem", 3)
    structure_nbt(out / "objects" / "oran_bush.nbt")
    if len(sys.argv) > 2:  # optional: path to Cobblemon-fabric-1.8.0+1.21.1.jar
        import zipfile
        with zipfile.ZipFile(sys.argv[2]) as jar:
            (out / "objects" / "berry_patch10.nbt").write_bytes(
                jar.read("data/cobblemon/structure/habitats/berry_patch10.nbt"))
    print("inputs written to", out)

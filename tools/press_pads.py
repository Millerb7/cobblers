#!/usr/bin/env python
"""Press data/sculpt.json's flat pads on the rescaled heightmap.

The sculpt pass pressed two deliberate flats (the Scar, the Frostpeak shrine's summit) before the vertical rescale.
Both sit above the rescale threshold, so the rescale's landform gain tilted them: the Scar went from a y194 table to
y241-278 with 44-degree edges. This tool presses every pad on the rescaled heightmap:

  - a pad's level is either its authored pre-rescale `y` carried through the rescale curve (tools/rescale.gain_curve),
    so it keeps its place relative to the mountain (the Scar's y194, 6 under the old summit, becomes y280 under a
    y300 summit), or a `pressed_y` authored directly on the rescaled terrain (a shelf cut after the rescale)
  - the brush is sculpt.py's own: fully flat within radius, a smoothstep feather over feather blocks
  - every column outside a brush keeps its 16-bit sample exactly; inside, samples are the nearest level to the target
  - it always starts from the unpressed rescaled heightmap (heightmap.pressed_from when the canonical file is already
    pressed), so running it again never feathers a pad twice

  python tools/press_pads.py --source-root <root>            # report
  python tools/press_pads.py --source-root <root> --apply    # write land_8k_16_rescaled_b145_pads.png and data/world.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

import terrain as T
import rescale as RS

ROOT = T.ROOT
OUT_NAME = "land_8k_16_rescaled_b145_pads.png"


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def pad_level(pd):
    if pd.get("pressed_y") is not None:
        return float(pd["pressed_y"])
    return float(RS.gain_curve(np.array([float(pd["y"])]))[0])


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    T.add_common_args(p)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args(argv)
    world = T.load_world(a.world)
    current = T.resolve_heightmap(world, Path(a.world), a.source_root)
    base = world["heightmap"].get("pressed_from")
    if base:
        src = current.parent / base["path"]
        if hashlib.sha256(src.read_bytes()).hexdigest() != base["sha256"]:
            raise SystemExit("pressed_from %s does not hash to %s" % (src, base["sha256"][:8]))
        base_ref = {"path": base["path"], "sha256": base["sha256"]}
    else:
        src = current
        base_ref = {"path": world["heightmap"]["path"], "sha256": world["heightmap"]["sha256"]}
    raw = np.array(Image.open(src)).astype(np.uint16)
    imp = world["import"]
    hi_out = imp["high_out"]
    n = raw.shape[0]
    sculpt = json.loads((ROOT / "data" / "sculpt.json").read_text(encoding="utf-8"))
    towns = {t["id"]: t for t in json.loads((ROOT / "data" / "towns.json").read_text(encoding="utf-8"))["towns"]}
    out = raw.copy()
    report = []
    for pd in sculpt["pads"]:
        tw = towns[pd["site"]]
        cx, cz = tw["centre"]["x"], tw["centre"]["z"]
        R, F = pd["radius"], pd["feather"]
        level = pad_level(pd)
        x0, x1, z0, z1 = max(0, cx - R - F), min(n, cx + R + F + 1), max(0, cz - R - F), min(n, cz + R + F + 1)
        zz, xx = np.mgrid[z0:z1, x0:x1]
        w = 1 - smoothstep(R, R + F, np.hypot(xx - cx, zz - cz))
        region = out[z0:z1, x0:x1]
        y_before = RS.y_of_h(region.astype(np.float64), imp, hi_out)
        y_target = y_before * (1 - w) + level * w
        h = np.clip(np.rint(RS.h_of_y(y_target, imp, hi_out)), 0, RS.FULL).astype(np.uint16)
        touched = w > 0
        region[touched] = h[touched]
        y_after = RS.y_of_h(region.astype(np.float64), imp, hi_out)
        flat = w > 0.999
        entry = {"site": pd["site"], "pressed_y": round(level, 1), "centre": [cx, cz], "radius": R, "feather": F,
                 "flat_columns": int(flat.sum()), "touched_columns": int(touched.sum()),
                 "before_flat_zone_y": [round(float(y_before[flat].min()), 1), round(float(y_before[flat].max()), 1)],
                 "after_flat_zone_y": [round(float(y_after[flat].min()), 1), round(float(y_after[flat].max()), 1)],
                 "max_change_blocks": round(float(np.abs(y_after - y_before).max()), 1)}
        if pd.get("pressed_y") is None:
            entry["authored_y"] = pd["y"]
        report.append(entry)
    changed = int((out != raw).sum())
    for r in report:
        print(json.dumps(r))
    print("columns changed: %d; outside the brushes: bit-identical by construction" % changed)
    if not a.apply:
        print("(dry run -- pass --apply)")
        return 0
    dest = current.parent / OUT_NAME
    Image.fromarray(out, mode="I;16").save(dest)
    sha = hashlib.sha256(dest.read_bytes()).hexdigest()
    # data/world.json is hand-formatted: rewrite only the heightmap object's text
    wpath = Path(a.world)
    text = wpath.read_text(encoding="utf-8")
    doc = json.loads(text)
    hm = doc["heightmap"]
    old_sha = hm["sha256"]
    hm["path"], hm["sha256"] = OUT_NAME, sha
    hm["pressed_from"] = {**base_ref, "generator": "python tools/press_pads.py --apply", "pads": report,
                          "note": "data/sculpt.json pads pressed on the rescaled heightmap: pre-rescale pads at their authored level carried "
                                  "through the rescale curve, post-rescale shelves at pressed_y. Columns outside the pad brushes are "
                                  "bit-identical to the rescaled heightmap."}
    if old_sha != sha and old_sha not in hm.get("previous_sha256", []):
        hm["previous_sha256"] = [old_sha] + hm.get("previous_sha256", [])
    start = text.index('"heightmap"')
    brace = text.index("{", start)
    depth, i = 0, brace
    while True:
        ch = text[i]
        if ch == '"':
            i += 1
            while text[i] != '"':
                i += 2 if text[i] == "\\" else 1
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    block = json.dumps(hm, indent=2, ensure_ascii=False).replace("\n", "\n  ")
    text = text[:brace] + block + text[i + 1:]
    assert json.loads(text)["heightmap"]["sha256"] == sha
    wpath.write_text(text, encoding="utf-8")
    print("wrote %s (sha256 %s) and %s" % (dest, sha, wpath))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

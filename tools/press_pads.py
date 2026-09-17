#!/usr/bin/env python
"""Re-press data/sculpt.json's flat pads on the rescaled heightmap.

The sculpt pass pressed two deliberate flats (the Scar, the Frostpeak shrine's summit) before the vertical rescale.
Both sit above the rescale threshold, so the rescale's landform gain tilted them: the Scar went from a y194 table to
y241-278 with 44-degree edges. This tool presses them again, on the rescaled heightmap:

  - each pad's level is its authored y carried through the rescale curve (tools/rescale.gain_curve), so it keeps its
    place relative to the mountain: the Scar's y194, 6 under the old summit, becomes y280 under a y300 summit
  - the brush is sculpt.py's own: fully flat within radius, a smoothstep feather over feather blocks
  - every column outside a brush keeps its 16-bit sample exactly; inside, samples are the nearest level to the target

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


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    T.add_common_args(p)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args(argv)
    heights, world = T.load_from_args(a)
    src = T.resolve_heightmap(world, Path(a.world), a.source_root)
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
        level = float(RS.gain_curve(np.array([float(pd["y"])]))[0])
        x0, x1, z0, z1 = max(0, cx - R - F), min(n, cx + R + F + 1), max(0, cz - R - F), min(n, cz + R + F + 1)
        zz, xx = np.mgrid[z0:z1, x0:x1]
        w = 1 - smoothstep(R, R + F, np.hypot(xx - cx, zz - cz))
        y_before = RS.y_of_h(raw[z0:z1, x0:x1].astype(np.float64), imp, hi_out)
        y_target = y_before * (1 - w) + level * w
        h = np.clip(np.rint(RS.h_of_y(y_target, imp, hi_out)), 0, RS.FULL).astype(np.uint16)
        region = out[z0:z1, x0:x1]
        touched = w > 0
        region[touched] = h[touched]
        y_after = RS.y_of_h(region.astype(np.float64), imp, hi_out)
        flat = w > 0.999
        report.append({"site": pd["site"], "authored_y": pd["y"], "pressed_y": round(level, 1),
                       "flat_columns": int(flat.sum()), "touched_columns": int(touched.sum()),
                       "before_flat_zone_y": [round(float(y_before[flat].min()), 1), round(float(y_before[flat].max()), 1)],
                       "after_flat_zone_y": [round(float(y_after[flat].min()), 1), round(float(y_after[flat].max()), 1)],
                       "max_change_blocks": round(float(np.abs(y_after - y_before).max()), 1)})
    changed = int((out != raw).sum())
    for r in report:
        print(json.dumps(r))
    print("columns changed: %d; outside the brushes: bit-identical by construction" % changed)
    if not a.apply:
        print("(dry run -- pass --apply)")
        return 0
    dest = src.parent / OUT_NAME
    Image.fromarray(out, mode="I;16").save(dest)
    sha = hashlib.sha256(dest.read_bytes()).hexdigest()
    # data/world.json is hand-formatted: edit the heightmap block's text rather than re-serialising the file
    wpath = Path(a.world)
    text = wpath.read_text(encoding="utf-8")
    doc = json.loads(text)
    prev = {"path": doc["heightmap"]["path"], "sha256": doc["heightmap"]["sha256"]}
    pressed = {"path": prev["path"], "sha256": prev["sha256"], "generator": "python tools/press_pads.py --apply", "pads": report,
               "note": "The sculpt pads re-pressed after the vertical rescale, at their authored level carried through the rescale "
                       "curve. Columns outside the pad brushes are bit-identical to the rescaled heightmap."}
    old_head = '"path": "%s",' % prev["path"]
    old_sha = '"sha256": "%s",' % prev["sha256"]
    i = text.index('"heightmap"')
    j = text.index(old_head, i)
    k = text.index(old_sha, j)
    block = json.dumps(pressed, indent=2, ensure_ascii=False).replace("\n", "\n    ")
    text = (text[:j] + '"path": "%s",' % OUT_NAME + text[j + len(old_head):k] + '"sha256": "%s",' % sha
            + '\n    "pressed_from": ' + block + "," + text[k + len(old_sha):])
    p_prev = text.index('"previous_sha256": [', i)
    text = text[:p_prev + len('"previous_sha256": [')] + '"%s", ' % prev["sha256"] + text[p_prev + len('"previous_sha256": ['):]
    check = json.loads(text)
    assert check["heightmap"]["sha256"] == sha and check["heightmap"]["previous_sha256"][0] == prev["sha256"]
    wpath.write_text(text, encoding="utf-8")
    print("wrote %s (sha256 %s) and %s" % (dest, sha, wpath))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

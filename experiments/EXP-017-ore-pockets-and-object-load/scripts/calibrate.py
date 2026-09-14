#!/usr/bin/env python
"""EXP-017 Task A: fit the Underground Pockets relation from the sweep measurements.

  python calibrate.py <sweep measure.json> <out.json>

Source relation (UndergroundPocketsLayerExporter + PerlinNoise.getLevelForPromillage):
  threshold = noise level exceeded by (frequency x 0.9^(8 - layerValue)) per mille of samples
  noise sampled at (x, z, y) / (4.099 x scale / 100)
so the nominal replaced fraction is frequency x 0.9^(8-value) per mille. Here
  k = measured permille / (frequency x 0.9^(8 - value))
is reported per world, and blob sizes per (frequency, scale).
World names: sw-f<frequency>-s<scale> (value 8) and val-f<frequency>-s<scale>-v<value>.
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

rows = json.loads(Path(sys.argv[1]).read_text(encoding="utf8"))
table = []
for r in rows:
    m = re.match(r"(?:sw|val)-f(\d+)-s(\d+)(?:-v(\d+))?$", r["world"])
    if not m:
        continue
    f, s, v = int(m.group(1)), int(m.group(2)), int(m.group(3) or 8)
    nominal = f * 0.9 ** (8 - v)
    rp = np.array(r["row_permille"])
    table.append({"world": r["world"], "frequency": f, "scale": s, "value": v, "nominal_permille": round(nominal, 4),
                  "measured_permille": r["permille"], "k": round(r["permille"] / nominal, 3),
                  "blob_size_mean": r["blob_size_mean"], "blob_size_p90": r["blob_size_p90"], "blob_size_max": r["blob_size_max"],
                  "blobs_per_1000": r["blobs_per_1000"],
                  "row_permille_min": float(rp.min()), "row_permille_max": float(rp.max()),
                  "row_mod4_profile": [round(float(rp[i::4].mean()), 3) for i in range(4)]})

sw = [t for t in table if t["world"].startswith("sw-")]
k_by_f = defaultdict(list)
k_by_s = defaultdict(list)
blob = {}
for t in sw:
    k_by_f[t["frequency"]].append(t["k"])
    k_by_s[t["scale"]].append(t["k"])
    blob.setdefault(t["scale"], {})[t["frequency"]] = t["blob_size_mean"]
summary = {
    "k_all_value8": {"mean": round(float(np.mean([t["k"] for t in sw])), 3), "min": min(t["k"] for t in sw),
                     "max": max(t["k"] for t in sw), "n": len(sw)},
    "k_by_frequency": {str(f): {"mean": round(float(np.mean(v)), 3), "min": min(v), "max": max(v)} for f, v in sorted(k_by_f.items())},
    "k_by_scale": {str(s): {"mean": round(float(np.mean(v)), 3), "min": min(v), "max": max(v)} for s, v in sorted(k_by_s.items())},
    "blob_size_mean_by_scale_then_frequency": {str(s): {str(f): b for f, b in sorted(v.items())} for s, v in sorted(blob.items())},
    "value_tests": [t for t in table if t["world"].startswith("val-")],
}
Path(sys.argv[2]).write_text(json.dumps({"summary": summary, "worlds": table}, indent=1), encoding="utf8")
print(json.dumps(summary, indent=1))
print("%-16s %4s %4s %3s %8s %8s %6s %7s %6s %s" % ("world", "f", "s", "v", "nominal", "measured", "k", "blob_mean", "p90", "row mod4"))
for t in table:
    print("%-16s %4d %4d %3d %8.3f %8.3f %6.3f %7.3f %6.1f %s" % (t["world"], t["frequency"], t["scale"], t["value"],
          t["nominal_permille"], t["measured_permille"], t["k"], t["blob_size_mean"], t["blob_size_p90"], t["row_mod4_profile"]))

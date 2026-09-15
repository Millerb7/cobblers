#!/usr/bin/env python
"""Read data/landmarks.json so tools look features up instead of inferring them.

A landmark is an authored statement that a feature exists at a place: the
rift, the glacier corridor, the range. Tools ask this module where a feature
is, what its axes are, and whether it may hold water. They do not rediscover
features from the heightmap, which is how an under-carved glacier went
unreported.

  python tools/landmarks.py            # list landmarks and their status
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LANDMARKS = ROOT / "data" / "landmarks.json"

STATUSES = ("built", "partial", "planned")
WATER_POLICIES = ("allowed", "never")


class LandmarkError(RuntimeError):
    """The landmarks file is missing, malformed, or lacks what was asked for."""


def load(path=None):
    path = Path(path or DEFAULT_LANDMARKS)
    if not path.is_file():
        raise LandmarkError("landmarks file not found: %s" % path)
    doc = json.loads(path.read_text(encoding="utf-8"))
    problems = check(doc)
    if problems:
        raise LandmarkError("%s is malformed: %s" % (path, "; ".join(problems)))
    return doc


def check(doc):
    """Structural problems as strings. Empty means usable."""
    out = []
    if doc.get("schema") != "cobblers.landmarks/1":
        out.append('schema must be "cobblers.landmarks/1"')
    seen = set()
    for i, lm in enumerate(doc.get("landmarks") or []):
        lid = lm.get("id")
        where = "landmarks[%d]" % i if not lid else lid
        if not lid:
            out.append("%s has no id" % where)
        elif lid in seen:
            out.append("duplicate landmark id %s" % lid)
        seen.add(lid)
        if lm.get("status") not in STATUSES:
            out.append("%s status must be one of %s" % (where, "|".join(STATUSES)))
        if (lm.get("water") or "allowed") not in WATER_POLICIES:
            out.append("%s water must be one of %s" % (where, "|".join(WATER_POLICIES)))
        for poly in (lm.get("extent") or {}).get("polygons") or []:
            if len(poly) < 3:
                out.append("%s has a polygon with fewer than 3 points" % where)
        axis_ids = set()
        for ax in lm.get("axes") or []:
            if not ax.get("id") or ax["id"] in axis_ids:
                out.append("%s has an axis with a missing or duplicate id" % where)
            axis_ids.add(ax.get("id"))
            if len(ax.get("polyline") or []) < 2:
                out.append("%s axis %s needs at least two points" % (where, ax.get("id")))
    return out


def get(doc, landmark_id):
    for lm in doc.get("landmarks") or []:
        if lm.get("id") == landmark_id:
            return lm
    raise LandmarkError("no landmark %r" % landmark_id)


def axis(lm, axis_id=None):
    axes = lm.get("axes") or []
    if not axes:
        raise LandmarkError("landmark %s has no axes" % lm.get("id"))
    if axis_id is None:
        return axes[0]
    for ax in axes:
        if ax.get("id") == axis_id:
            return ax
    raise LandmarkError("landmark %s has no axis %r" % (lm.get("id"), axis_id))


def point(doc, ref):
    """Resolve LANDMARK or LANDMARK.ANCHOR to (x, z).

    A bare landmark id resolves to its "anchor"; a dotted name to a named
    entry in its "anchors" map.
    """
    lid, _, name = ref.partition(".")
    lm = get(doc, lid)
    if not name:
        a = lm.get("anchor")
        if not a:
            raise LandmarkError("landmark %s has no anchor" % lid)
        return int(a["x"]), int(a["z"])
    anchors = lm.get("anchors") or {}
    if name not in anchors:
        raise LandmarkError("landmark %s has no anchor %r (has %s)"
                            % (lid, name, ", ".join(sorted(anchors)) or "none"))
    a = anchors[name]
    return int(a["x"]), int(a["z"])


def mask(lm, shape, factor=1):
    """Boolean raster of a landmark's polygons at 1/factor resolution.

    shape is the raster shape (rows, cols). Polygons are block coordinates.
    """
    img = Image.new("1", (shape[1], shape[0]), 0)
    draw = ImageDraw.Draw(img)
    for poly in (lm.get("extent") or {}).get("polygons") or []:
        draw.polygon([(x / factor, z / factor) for x, z in poly], fill=1, outline=1)
    return np.array(img, dtype=bool)


def no_water_mask(doc, shape, factor=1):
    """Union of every landmark that must never be treated as a water body."""
    out = np.zeros(shape, dtype=bool)
    for lm in doc.get("landmarks") or []:
        if lm.get("water") == "never":
            out |= mask(lm, shape, factor)
    return out


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--landmarks", default=str(DEFAULT_LANDMARKS))
    a = p.parse_args(argv)
    try:
        doc = load(a.landmarks)
    except LandmarkError as exc:
        raise SystemExit("landmarks: %s" % exc)
    for lm in doc["landmarks"]:
        print("%-22s %-8s %-10s water=%-7s axes=%s anchors=%s"
              % (lm["id"], lm["status"], lm.get("kind", ""), lm.get("water", "allowed"),
                 ",".join(ax["id"] for ax in lm.get("axes") or []) or "-",
                 ",".join(sorted(lm.get("anchors") or {})) or "-"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

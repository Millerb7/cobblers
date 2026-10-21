#!/usr/bin/env python3
"""Put the legendary gate items into the dungeon vaults as chance rewards (data/vault_keys.json).

    python tools/vault_keys.py            # apply: rewrite data/dungeons.json loot_by_band and data/dungeon_greed.json items
    python tools/vault_keys.py --check    # change nothing; exit 1 if the files differ from the table or the table breaks a rule

WHAT IT WRITES
  data/dungeons.json  in the `loot_by_band` of EVERY `vault` and `bank_vault` room (all 15 today), one stack per pool
                      in each band the pool names: {"one_of": [{"item", "weight"}, ...], "chance": c}. Only the
                      `loot_by_band` object's text is replaced, so the rest of the file's hand formatting is untouched.
                      A stack whose options are all key items is ours: it is removed and re-added, so a run is
                      idempotent and a changed table moves the stacks, never duplicates them.
  data/dungeon_greed.json  one `items` row a key item (cp 1, source "unpriced", the Rare Candy's placeholder): a vault
                      chest is priced by the greed table and refuses an item it does not price. See the table's `price`.

RULES IT REFUSES (the table, not the data, is checked, and the check runs before any write)
  - a pool in a band whose LOWEST cap is below the cap an item's gate implies (a gym8 item in band 4, a champion item
    in band 5): "never in a band earlier than its legendary's gate". The caps are the engine's own bands
    (data/dungeons.json engine.bands) and the table's `gates`.
  - a pool's chance that is not q_per_item x its weight sum / 2 (the base weight), so a stated per-item rate is the
    rate a stack really has; a duplicate item, an unknown gate, a pool band the engine does not have.

NOT COVERED: that Minecraft rolls the pool as the shape says (tests/test_dungeon_vault_one_of.py proves the shape,
a run proves the roll), and an item id's existence in a jar (the table's id_check says which were read where).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TABLE = ROOT / "data" / "vault_keys.json"
DUNGEONS = ROOT / "data" / "dungeons.json"
GREED = ROOT / "data" / "dungeon_greed.json"
BASE_CHESTS = 4          # every vault's chance is normalised to a 4-chest vault's odds per run
BASE_WEIGHT = 2          # a weight-2 option is one item at the stated per-item rate; the crown's weight 1 is half of it
KINDS = ("vault", "bank_vault")


def load(path=TABLE):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def key_items(table):
    return {o["item"] for p in table["pools"] for o in p["items"]}


def table_problems(table, doc):
    """The faults of the table against the engine's bands: [] when sound."""
    bad = []
    lowest = {b["band"]: b["caps"][0] for b in doc["engine"]["bands"]}
    seen = set()
    q = table["chance"]["q_per_item"]
    for p in table["pools"]:
        wsum = sum(o["weight"] for o in p["items"])
        want = round(q * wsum / BASE_WEIGHT, 4)
        if abs(p["chance_4"] - want) > 1e-9:
            bad.append("pool %s: chance_4 %r, but q_per_item %r x weight sum %d / %d is %r"
                       % (p["id"], p["chance_4"], q, wsum, BASE_WEIGHT, want))
        for band in p["bands"]:
            if band not in lowest:
                bad.append("pool %s: band %r is not an engine band" % (p["id"], band))
                continue
            for o in p["items"]:
                g = table["gates"].get(o["gate"])
                if g is None:
                    bad.append("%s: gate %r is not in the table's gates" % (o["item"], o["gate"]))
                elif lowest[band] < g["cap"]:
                    bad.append("pool %s band %d: its lowest cap %d is under the %d that %s implies for %s "
                               "(an item may not sit in a band earlier than its gate)"
                               % (p["id"], band, lowest[band], g["cap"], o["gate"], o["item"]))
        for o in p["items"]:
            if o["item"] in seen:
                bad.append("%s is in two pools" % o["item"])
            seen.add(o["item"])
            if not re.fullmatch(r"[a-z0-9_.-]+:[a-z0-9_./-]+", o["item"]):
                bad.append("%r is not an item id" % o["item"])
            if not (isinstance(o["weight"], int) and o["weight"] >= 1):
                bad.append("%s: weight must be a positive integer" % o["item"])
    return bad


def chance_for(c4, chests):
    """The per-chest chance that gives a `chests`-chest vault the same odds per RUN as a 4-chest vault at c4."""
    if chests == BASE_CHESTS:
        return c4
    return round(1 - (1 - c4) ** (BASE_CHESTS / chests), 3)


def stack_for(pool, chests):
    return {"one_of": [{"item": o["item"], "weight": o["weight"]} for o in pool["items"]],
            "chance": chance_for(pool["chance_4"], chests)}


def vault_params(doc):
    """[params dict] of every vault and bank_vault room, in document (= text) order, every variant."""
    out = []

    def walk(o):
        if isinstance(o, dict):
            if o.get("kind") in KINDS and isinstance((o.get("params") or {}).get("loot_by_band"), dict):
                out.append(o["params"])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(doc["dungeons"])
    return out


def new_loot(old, chests, table):
    ours = key_items(table)
    new = {}
    for band, stacks in old.items():
        keep = [s for s in stacks if not ("one_of" in s and s["one_of"] and all(o.get("item") in ours for o in s["one_of"]))
                and s.get("item") not in ours]
        add = [stack_for(p, chests) for p in table["pools"] if int(band) in p["bands"]]
        new[band] = keep + add
    return new


BAND_LINE = re.compile(r'(?m)^[ ]*"(\d)": ')


def rewrite_bands(seg, old, new, offset):
    """seg is a loot_by_band object's text, one band a line (the closing brace on the last band's line or its own); only
    each band's list text is replaced, so the indentation and the line layout stay as hand-written."""
    dec = json.JSONDecoder()
    out, pos, found = [], 0, []
    for m in BAND_LINE.finditer(seg):
        band = m.group(1)
        lst, end = dec.raw_decode(seg, m.end())
        if lst != old[band] or json.dumps(lst) != seg[m.end():end]:
            raise SystemExit("vault_keys: band %s of the loot_by_band at offset %d does not round-trip through json.dumps; "
                             "rewriting it would reformat the hand-written text" % (band, offset))
        out.append(seg[pos:m.end()])
        out.append(json.dumps(new[band]))
        pos = end
        found.append(band)
    out.append(seg[pos:])
    if found != list(old):
        raise SystemExit("vault_keys: found bands %s but the object has %s at offset %d" % (found, list(old), offset))
    return "".join(out)


def rewrite_dungeons(raw, table):
    """The new text of data/dungeons.json: only each loot_by_band object is replaced."""
    doc = json.loads(raw)
    params = vault_params(doc)
    marker = '"loot_by_band": '
    starts = [m.end() for m in re.finditer(re.escape(marker), raw)]
    if len(starts) != len(params):
        raise SystemExit("vault_keys: %d loot_by_band objects in the text but %d vault rooms in the data; refusing to guess"
                         % (len(starts), len(params)))
    dec = json.JSONDecoder()
    out, pos = [], 0
    for start, p in zip(starts, params):
        old, end = dec.raw_decode(raw, start)
        if old != p["loot_by_band"]:
            raise SystemExit("vault_keys: the text and the parsed order disagree at offset %d; refusing to guess" % start)
        chests = int(p.get("chests", BASE_CHESTS))
        new = new_loot(old, chests, table)
        seg = raw[start:end]
        out.append(raw[pos:start])
        out.append(rewrite_bands(seg, old, new, start))
        pos = end
    out.append(raw[pos:])
    return "".join(out)


def greed_row(table, o):
    return ('    "%s": {\n      "cp": 1,\n      "source": "unpriced",\n      "why": %s\n    },\n'
            % (o["item"], json.dumps(
                "a legendary gate item (data/vault_keys.json): %s. Not wealth: the bank does not buy it, the wishing well refuses an "
                "'unpriced' row, and the clock charges a chest's expected value, so it is the placeholder floor, as the Rare Candy "
                "(data/vault_keys.json price)" % o["legendary"], ensure_ascii=False)))


def rewrite_greed(raw, table):
    have = set(json.loads(raw)["items"])
    lines = raw.split("\n")
    try:
        i0 = lines.index('  "items": {')
    except ValueError:
        raise SystemExit("vault_keys: no top-level items block in data/dungeon_greed.json")
    new = sorted((o for p in table["pools"] for o in p["items"] if o["item"] not in have), key=lambda o: o["item"])
    for o in new:
        keys = [(n, re.fullmatch(r'    "([^"]+)": \{', lines[n]).group(1)) for n in range(i0 + 1, len(lines))
                if re.fullmatch(r'    "([^"]+)": \{', lines[n])]
        # the block ends at the first line that closes it at two spaces
        end = next(n for n in range(i0 + 1, len(lines)) if lines[n] in ("  },", "  }"))
        keys = [(n, k) for n, k in keys if n < end]
        at = next((n for n, k in keys if k > o["item"]), None)
        if at is None:
            raise SystemExit("vault_keys: %s sorts after every item row; the insert would need a comma fix" % o["item"])
        lines[at:at] = greed_row(table, o).rstrip("\n").split("\n")
    return "\n".join(lines)


def greed_problems(table, greed):
    bad = []
    for p in table["pools"]:
        for o in p["items"]:
            row = greed["items"].get(o["item"])
            if row is None:
                bad.append("data/dungeon_greed.json has no row for %s" % o["item"])
            elif row.get("source") != "unpriced" or row.get("cp") != 1:
                bad.append("%s is priced %r %r in the greed table, not the unpriced floor" % (o["item"], row.get("cp"), row.get("source")))
    return bad


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    check = "--check" in argv
    table = load()
    raw = DUNGEONS.read_text(encoding="utf-8")
    greed_raw = GREED.read_text(encoding="utf-8")
    bad = table_problems(table, json.loads(raw))
    if bad:
        print("vault_keys: %d problem(s)" % len(bad))
        for b in bad:
            print("  " + b)
        return 1
    new_raw = rewrite_dungeons(raw, table)
    new_greed = rewrite_greed(greed_raw, table)
    changed = [n for n, a, b in (("data/dungeons.json", raw, new_raw), ("data/dungeon_greed.json", greed_raw, new_greed)) if a != b]
    if check:
        if changed:
            print("vault_keys --check: out of date: " + ", ".join(changed))
            return 1
        print("vault_keys --check: ok (%d items, %d vault rooms)" % (len(key_items(table)), len(vault_params(json.loads(raw)))))
        return 0
    if changed:
        if new_raw != raw:
            DUNGEONS.write_text(new_raw, encoding="utf-8", newline="\n")
        if new_greed != greed_raw:
            GREED.write_text(new_greed, encoding="utf-8", newline="\n")
    gp = greed_problems(table, json.loads(GREED.read_text(encoding="utf-8")))
    if gp:
        print("vault_keys: " + "; ".join(gp))
        return 1
    print("vault_keys: wrote %s; %d items, %d vault rooms" % (", ".join(changed) or "nothing (already current)",
                                                              len(key_items(table)), len(vault_params(json.loads(new_raw)))))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Read a generated look-then-act function chain from its text and say what is wrong with it, for the audits of the
sites that re-summon display entities (tools/frostpeak_camp_audit.py, tools/coldwater_station_audit.py) and of the
town traders and the barterers (tests/test_traders_chunk_look.py, tests/test_direct_trades.py).

Independent of the generator: it never imports tools/chunk_look.py and follows the chain by the `function` and
`schedule function` lines it finds, from the entry function a reapply step calls. What it proves, each from the
staging finding behind it (N155, 2026-10-08: a force-loaded chunk accepts a summon at once but its saved entities
arrive later, so a kill in the same tick as the forceload misses them and the summon doubles them):

  hold      the entry force-loads; every summon and every kill/look selector centre lies in its chunks; the chunks are
            released only in a function that schedules and calls nothing more (the chain's end), and all of them are
  gate      the function that summons is never the entry nor called from it; it is called only behind a score flag that
            is set only by a look that saw an entity with the site's tag (or, in a look needing several at once, saw
            every one, each with the site's tag), or by a look counter run out; the counter
            and flag are reset in the entry; the blind case comes no sooner than BLIND_MIN ticks after the forceload
  sites     (given sites, for a chain over several far apart: the Rift's) every site's chunk is held and one look
            requires an entity in each of them, since two chunks' saved entities do not arrive together
  order     the summoning function kills the site's tagged displays before its first summon
  once      every summon carries the site's tag and its `<tag>_new` tag; the end kills, where a new one stands, every
            tagged display without the new tag, drops the new tag, and stores a count of the tagged displays

BLIND_MIN is R17M's blind limit (tools/markets.py MERCHANT_POLLS: 300 ticks), the longest the staging runs saw a
chunk's entities take was about 5 s (100 ticks); it is the standard the stall merchants were fixed to, not a value
read from the chain.
"""
from __future__ import annotations

import re
from pathlib import Path

BLIND_MIN = 300
CALL = re.compile(r"(?:^|\brun\s+)function\s+(\S+)\s*$")
SCHEDULE = re.compile(r"(?:^|\brun\s+)schedule\s+function\s+(\S+)\s+(\d+)t\b")
FORCELOAD = re.compile(r"^forceload\s+(add|remove)\s+(-?\d+)\s+(-?\d+)(?:\s+(-?\d+)\s+(-?\d+))?\s*$")
SUMMON = re.compile(r"(?:^|\brun\s+)summon\s+\S+\s+(-?[\d.]+)\s+\S+\s+(-?[\d.]+)\s+(\{.*\})\s*$")
SELECTOR = re.compile(r"@e\[([^\]]*(?:\[[^\]]*\][^\]]*)*)\]")


def pack_path(pack, ref):
    ns, path = ref.split(":", 1)
    return Path(pack) / "data" / ns / "function" / (path + ".mcfunction")


def read_chain(pack, entry):
    """{function id: [commands]} reached from entry (comments and blanks dropped), and [missing ids]."""
    ns = entry.split(":", 1)[0]
    fns, missing, todo = {}, [], [entry]
    while todo:
        ref = todo.pop()
        if ref in fns or ref in missing:
            continue
        p = pack_path(pack, ref)
        if not p.is_file():
            missing.append(ref)
            continue
        cmds = [s.strip() for s in p.read_text(encoding="utf-8").splitlines() if s.strip() and not s.strip().startswith("#")]
        fns[ref] = cmds
        for c in cmds:
            for m in (CALL.search(c), SCHEDULE.search(c)):
                if m and m.group(1).startswith(ns + ":"):
                    todo.append(m.group(1))
    return fns, missing


def _chunks(m):
    x0, z0 = int(m.group(2)), int(m.group(3))
    x1, z1 = (int(m.group(4)), int(m.group(5))) if m.group(4) else (x0, z0)
    return {(cx, cz) for cx in range(min(x0, x1) >> 4, (max(x0, x1) >> 4) + 1)
            for cz in range(min(z0, z1) >> 4, (max(z0, z1) >> 4) + 1)}


def _args(body):
    return dict(a.split("=", 1) for a in body.split(",") if "=" in a and not a.startswith("tag="))


def _tags(body):
    return [a[4:] for a in body.split(",") if a.startswith("tag=")]


def problems(pack, entry, tag, label=None, sites=None):
    """[problem] for the chain at `entry` re-summoning displays tagged `tag`. `sites`: [(x, z)] the caller's own data
    says the chain serves, when it serves several far apart (sites below)."""
    label = label or entry
    fns, missing = read_chain(pack, entry)
    out = ["%s: %s is called but not in the pack" % (label, m) for m in missing]
    if entry not in fns:
        return out or ["%s: no entry function" % label]
    new = tag + "_new"

    def calls(ref):
        return [m.group(1) for c in fns[ref] for m in (CALL.search(c), SCHEDULE.search(c)) if m]

    # hold
    added, removed = set(), set()
    for ref, cmds in fns.items():
        for c in cmds:
            m = FORCELOAD.match(c)
            if not m:
                continue
            if m.group(1) == "add":
                if ref != entry:
                    out.append("%s: %s force-loads; only the entry may, or the chain's end cannot release it" % (label, ref))
                added |= _chunks(m)
            else:
                if calls(ref):
                    out.append("%s: %s releases its chunks and still calls %s: the chain is not over" % (label, ref, calls(ref)))
                removed |= _chunks(m)
    if not added:
        out.append("%s: the entry force-loads nothing" % label)
    if added != removed:
        out.append("%s: chunks force-loaded %s are not the ones released %s" % (label, sorted(added), sorted(removed)))
    cols = []
    for ref, cmds in fns.items():
        for c in cmds:
            m = SUMMON.search(c)
            if m:
                cols.append((ref, float(m.group(1)), float(m.group(2))))
            for body in SELECTOR.findall(c):
                a = _args(body)
                if "x" in a and "z" in a:
                    cols.append((ref, float(a["x"]), float(a["z"])))
    for ref, x, z in cols:
        if (int(x // 1) >> 4, int(z // 1) >> 4) not in added:
            out.append("%s: %s acts at (%.1f, %.1f), outside every chunk the chain holds" % (label, ref, x, z))
            break

    # gate
    summoners = [ref for ref, cmds in fns.items() if any(SUMMON.search(c) for c in cmds)]
    if len(summoners) != 1:
        out.append("%s: %d functions summon (%s); the chain has one act" % (label, len(summoners), summoners))
        return out
    act = summoners[0]
    if act == entry or act in calls(entry):
        out.append("%s: %s summons in the tick it force-loads: nothing has been seen yet" % (label, act))
    callers = [(ref, c) for ref, cmds in fns.items() for c in cmds
               if (CALL.search(c) or SCHEDULE.search(c)) and (CALL.search(c) or SCHEDULE.search(c)).group(1) == act]
    flags = set()
    for ref, c in callers:
        m = re.match(r"execute if score (\S+) (\S+) matches 1 run function \S+$", c)
        if not m:
            out.append("%s: %s calls the act ungated: %s" % (label, ref, c[:100]))
        else:
            flags.add((m.group(1), m.group(2)))
    if not callers:
        out.append("%s: nothing calls %s" % (label, act))
    looks = {ref for ref, _c in callers}
    looked = []                 # per look line: the chunks its `if entity` selectors look in
    for flag, obj in flags:
        setters = [(ref, c) for ref, cmds in fns.items() for c in cmds
                   if re.search(r"scoreboard players set %s %s 1$" % (re.escape(flag), re.escape(obj)), c)]
        counter = None
        for ref, c in setters:
            # one look may require several sites at once (`if entity A if entity B ...`): every one must be the site's
            seen = re.match(r"execute (?:if score \S+ \S+ matches 0 )?((?:if entity @e\[[^\]]*\] )+)run ", c)
            blind = re.match(r"execute (?:if score \S+ \S+ matches 0 )?if score (\S+) %s matches \.\.0 run " % re.escape(obj), c)
            if seen and all(tag in _tags(b) for b in re.findall(r"@e\[([^\]]*)\]", seen.group(1))):
                looked.append({(int(float(a["x"]) // 1) >> 4, int(float(a["z"]) // 1) >> 4)
                               for b in re.findall(r"@e\[([^\]]*)\]", seen.group(1)) for a in [_args(b)]
                               if "x" in a and "z" in a})
                continue
            if blind:
                counter = blind.group(1)
                continue
            out.append("%s: %s sets the act's flag without a look or the blind limit: %s" % (label, ref, c[:100]))
        if "scoreboard players set %s %s 0" % (flag, obj) not in fns[entry]:
            out.append("%s: the entry does not reset the act's flag %s: a stale one acts at the first look" % (label, flag))
        if counter is None:
            out.append("%s: no blind limit: a first run (nothing to see) never acts" % label)
            continue
        polls = [int(c.split()[-1]) for c in fns[entry] if c.startswith("scoreboard players set %s %s " % (counter, obj))]
        first = [int(m.group(2)) for c in fns[entry] for m in [SCHEDULE.search(c)] if m and m.group(1) in looks]
        again = [int(m.group(2)) for ref in looks for c in fns[ref] for m in [SCHEDULE.search(c)] if m and m.group(1) in looks]
        decs = [c for ref in looks for c in fns[ref] if c == "scoreboard players remove %s %s 1" % (counter, obj)]
        if len(polls) != 1 or len(first) != 1 or len(again) != 1 or len(decs) != 1:
            out.append("%s: cannot read the blind limit (counter %s set %s, first look %s, look again %s, %d decrements)"
                       % (label, counter, polls, first, again, len(decs)))
        elif first[0] + (polls[0] - 1) * again[0] < BLIND_MIN:
            out.append("%s: acts blind %d ticks after the forceload, under %d" % (label, first[0] + (polls[0] - 1) * again[0],
                                                                                  BLIND_MIN))

    # sites (a chain serving several sites far apart): each site's chunk is held, and ONE look requires an entity in
    # every one of them. Two chunks' saved entities do not arrive together, so a look that acts on any one site
    # kills nothing at a site whose entities are still out and the summon doubles them there
    if sites:
        want = {(int(x // 1) >> 4, int(z // 1) >> 4) for x, z in sites}
        if want - added:
            out.append("%s: site chunk(s) %s are not force-loaded by the entry" % (label, sorted(want - added)))
        if not any(want <= c for c in looked):
            out.append("%s: no one look requires an entity in every site's chunk %s (looks see %s): it acts on one "
                       "site's entities while another's may still be out" % (label, sorted(want), [sorted(c) for c in looked]))

    # order
    first_summon = next(i for i, c in enumerate(fns[act]) if SUMMON.search(c))
    if not any(c.startswith("kill @e[") and tag in _tags(SELECTOR.search(c).group(1)) for c in fns[act][:first_summon]):
        out.append("%s: %s summons before it kills the site's old displays" % (label, act))

    # once
    for c in fns[act]:
        m = SUMMON.search(c)
        if m and not ('"%s"' % tag in m.group(3) and '"%s"' % new in m.group(3)):
            out.append("%s: a summon lacks %s or %s: %s" % (label, tag, new, c[:100]))
    ends = [ref for ref in fns if any(FORCELOAD.match(c) and c.split()[1] == "remove" for c in fns[ref])]
    for ref in ends:
        cmds = fns[ref]
        dedupe = [i for i, c in enumerate(cmds)
                  if re.match(r"execute if entity @e\[[^\]]*\] run kill @e\[([^\]]*)\]$", c)
                  and "tag=%s" % new in c.split(" run ")[0] and "tag=!%s" % new in c.split(" run ")[1]
                  and "tag=%s" % tag in c.split(" run ")[1]]
        untag = [i for i, c in enumerate(cmds) if c.startswith("tag @e[") and c.endswith(" remove %s" % new)]
        count = [i for i, c in enumerate(cmds) if c.startswith("execute store result score ")
                 and re.search(r" if entity @e\[[^\]]*tag=%s[,\]]" % re.escape(tag), c)]
        rel = [i for i, c in enumerate(cmds) if FORCELOAD.match(c)]
        if not dedupe or not untag or not count:
            out.append("%s: %s does not de-duplicate by %s, drop it and count (dedupe %s, untag %s, count %s)"
                       % (label, ref, new, dedupe, untag, count))
        elif not max(dedupe) < min(untag) < min(count) < min(rel):
            out.append("%s: %s de-duplicates, untags, counts and releases out of order" % (label, ref))
    if not ends:
        out.append("%s: the chain never releases its chunks" % label)
    return out


def sweep_problems(pack, entry, label=None):
    """[problem] for a KILL-ONLY sweep at `entry` (a staging cleanup that summons nothing). Read from the text like
    problems(): the entry force-loads and kills nothing (a kill in the tick of the forceload misses saved entities);
    one function holds every kill, reschedules itself and, when its counter runs out, calls the function that releases;
    its last run comes no sooner than BLIND_MIN ticks after the forceload; nothing summons; the chunks released are the
    chunks held, and every positioned kill lies in them."""
    label = label or entry
    fns, missing = read_chain(pack, entry)
    out = ["%s: %s is called but not in the pack" % (label, m) for m in missing]
    if entry not in fns:
        return out or ["%s: no entry function" % label]
    added, removed, releasers = set(), set(), []
    for ref, cmds in fns.items():
        for c in cmds:
            m = FORCELOAD.match(c)
            if m and m.group(1) == "add":
                if ref != entry:
                    out.append("%s: %s force-loads; only the entry may" % (label, ref))
                added |= _chunks(m)
            elif m:
                removed |= _chunks(m)
                releasers.append(ref)
            if SUMMON.search(c):
                out.append("%s: %s summons; a sweep only kills" % (label, ref))
    if not added:
        out.append("%s: the entry force-loads nothing" % label)
    if added != removed:
        out.append("%s: chunks force-loaded %s are not the ones released %s" % (label, sorted(added), sorted(removed)))
    for ref in set(releasers):
        if any(CALL.search(c) or SCHEDULE.search(c) for c in fns[ref]):
            out.append("%s: %s releases its chunks and still calls on: the sweep is not over" % (label, ref))
    killers = sorted({ref for ref, cmds in fns.items() if any(re.search(r"\brun kill @e\[|^kill @e\[", c) for c in cmds)})
    if entry in killers:
        out.append("%s: the entry kills in the tick it force-loads: the saved entities are not in yet" % label)
    looks = [ref for ref in killers if ref != entry]
    if len(looks) != 1:
        out.append("%s: %d functions kill after the entry (%s); a sweep has one look" % (label, len(looks), looks))
        return out
    look = looks[0]
    for c in fns[look]:
        for body in SELECTOR.findall(c):
            a = _args(body)
            if "x" in a and "z" in a and (int(float(a["x"]) // 1) >> 4, int(float(a["z"]) // 1) >> 4) not in added:
                out.append("%s: %s kills at (%s, %s), outside every chunk the sweep holds" % (label, look, a["x"], a["z"]))
    first = [int(m.group(2)) for c in fns[entry] for m in [SCHEDULE.search(c)] if m and m.group(1) == look]
    again = [(re.match(r"execute if score (\S+) (\S+) matches 1\.\. run ", c), int(m.group(2)))
             for c in fns[look] for m in [SCHEDULE.search(c)] if m and m.group(1) == look]
    if len(first) != 1 or len(again) != 1 or not again[0][0]:
        out.append("%s: cannot read the sweep's window (first look %s, look again %s)" % (label, first, [a for _m, a in again]))
        return out
    counter, obj = again[0][0].group(1), again[0][0].group(2)
    polls = [int(c.split()[-1]) for c in fns[entry] if c.startswith("scoreboard players set %s %s " % (counter, obj))]
    decs = [c for c in fns[look] if c == "scoreboard players remove %s %s 1" % (counter, obj)]
    ends = [c for c in fns[look] if re.match(r"execute if score %s %s matches \.\.0 run function (\S+)$"
                                             % (re.escape(counter), re.escape(obj)), c)]
    if len(polls) != 1 or len(decs) != 1 or len(ends) != 1:
        out.append("%s: cannot read the sweep's counter %s (set %s, %d decrements, %d ends)" % (label, counter, polls,
                                                                                                len(decs), len(ends)))
        return out
    if ends[0].split()[-1] not in releasers:
        out.append("%s: the sweep's last look does not call the function that releases" % label)
    last = first[0] + (polls[0] - 1) * again[0][1]
    if last < BLIND_MIN:
        out.append("%s: the last kill runs %d ticks after the forceload, under %d" % (label, last, BLIND_MIN))
    return out


def chain_lines(pack, entry):
    """Every command of the chain, entry first, for an audit that reads summons from it."""
    fns, _missing = read_chain(pack, entry)
    return [c for ref in sorted(fns, key=lambda r: (r != entry, r)) for c in fns[ref]]

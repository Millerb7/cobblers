#!/usr/bin/env python
"""Check tools/battle_sim.py's damage against a real Cobblemon battle. PREPARED, NOT RUN.

The simulator's tests prove it agrees with the published mainline formula. They cannot prove that Cobblemon's own
embedded Showdown agrees with either, at these levels, with this pack's configs on top. Only a battle settles it.

WHAT THIS CAN AND CANNOT AUTOMATE. Read this before running.

The 1.8 jar has 74 commands. It has `spawnpokemon`, `givepokemon`, `pokemonedit`, `teach`, `helditem`, `getnbt`,
`healpokemon`, `stopbattle` and `spectatebattle`. It has NOTHING that starts a battle or selects a move: there is
no command that drives a turn. So the fight itself needs a human making two clicks -- engage the wild Pokemon,
pick the named move -- and everything either side of that is scripted here:

  setup     both Pokemon built with explicit properties so nothing is rolled: species, level, nature, ability,
            held item and all six IVs and EVs. The keys are the ones PokemonProperties actually parses, read out
            of the jar: species, level, nature, ability, held_item, ivs, evs, shiny, gender, form, friendship,
            status, tera_type, aspects.
  the move  taught explicitly with `/teach`, so the attacker has exactly one damaging move and the choice cannot
            be got wrong.
  reading   the defender's HP before and after, from `/getnbt` on the party slot.
  compare   against battle_sim.damage with the random roll divided out, which gives the 85-100% band the game
            should land inside.

  python tools/verify_damage.py plan                 # print the matchups and the commands, run nothing
  python tools/verify_damage.py run --server-dir <d> # needs the coordination lock and a player at the keyboard

SAFETY. `run` acquires the shared lock through tools/runtime_guard.py and refuses if another session holds it.
It touches no world data: it spawns Pokemon, reads NBT, and heals afterwards. Use a staging server.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

# It talks to a running server over RCON and reads no world save, so the ground rule has nothing to
# declare here. It decides no position either.
WORLD_READS = set()

# Ten matchups. Between them they exercise a neutral hit, STAB, a resisted hit, a 2x and a 4x weakness, an
# immunity, Sturdy, Focus Sash, a stat stage and weather -- the cases where a damage model most often diverges.
MATCHUPS = [
    {"id": "neutral_physical_no_stab", "why": "the base case: no STAB, no type interaction, nothing held",
     "attacker": "rattata level=50 nature=hardy ability=runaway ivs=15,15,15,15,15,15 evs=0,0,0,0,0,0",
     "defender": "bidoof level=50 nature=hardy ability=simple ivs=15,15,15,15,15,15 evs=0,0,0,0,0,0",
     "move": "tackle"},
    {"id": "stab_physical", "why": "STAB alone: the same attacker and move, so the delta is the 1.5x",
     "attacker": "rattata level=50 nature=hardy ability=runaway ivs=15,15,15,15,15,15 evs=0,0,0,0,0,0",
     "defender": "bidoof level=50 nature=hardy ability=simple ivs=15,15,15,15,15,15 evs=0,0,0,0,0,0",
     "move": "hyperfang"},
    {"id": "special_neutral", "why": "the special side of the split, which uses different stats",
     "attacker": "mareep level=50 nature=hardy ability=static ivs=15,15,15,15,15,15 evs=0,0,0,0,0,0",
     "defender": "bidoof level=50 nature=hardy ability=simple ivs=15,15,15,15,15,15 evs=0,0,0,0,0,0",
     "move": "thundershock"},
    {"id": "super_effective_2x", "why": "one 2x multiplier",
     "attacker": "mareep level=50 nature=hardy ability=static ivs=15,15,15,15,15,15 evs=0,0,0,0,0,0",
     "defender": "krabby level=50 nature=hardy ability=hypercutter ivs=15,15,15,15,15,15 evs=0,0,0,0,0,0",
     "move": "thundershock"},
    {"id": "super_effective_4x", "why": "two stacked 2x multipliers: Water/Flying into Electric",
     "attacker": "mareep level=50 nature=hardy ability=static ivs=15,15,15,15,15,15 evs=0,0,0,0,0,0",
     "defender": "wingull level=50 nature=hardy ability=keeneye ivs=15,15,15,15,15,15 evs=0,0,0,0,0,0",
     "move": "thundershock"},
    {"id": "resisted", "why": "a 0.5x multiplier, where rounding order shows up most",
     "attacker": "charmander level=50 nature=hardy ability=blaze ivs=15,15,15,15,15,15 evs=0,0,0,0,0,0",
     "defender": "squirtle level=50 nature=hardy ability=torrent ivs=15,15,15,15,15,15 evs=0,0,0,0,0,0",
     "move": "ember"},
    {"id": "immune_ability", "why": "Lightning Rod must be exactly zero, not merely small",
     "attacker": "mareep level=50 nature=hardy ability=static ivs=15,15,15,15,15,15 evs=0,0,0,0,0,0",
     "defender": "pikachu level=50 nature=hardy ability=lightningrod ivs=15,15,15,15,15,15 evs=0,0,0,0,0,0",
     "move": "thundershock"},
    {"id": "sturdy_survives", "why": "a lethal hit must leave exactly 1 HP",
     "attacker": "machop level=50 nature=adamant ability=guts ivs=31,31,31,31,31,31 evs=0,252,0,0,0,0",
     "defender": "geodude level=5 nature=hardy ability=sturdy ivs=0,0,0,0,0,0 evs=0,0,0,0,0,0",
     "move": "lowkick"},
    {"id": "focus_sash_survives", "why": "the item, not the ability: seven leader Pokemon hold one",
     "attacker": "machop level=50 nature=adamant ability=guts ivs=31,31,31,31,31,31 evs=0,252,0,0,0,0",
     "defender": "rattata level=5 nature=hardy ability=runaway held_item=cobblemon:focus_sash "
                 "ivs=0,0,0,0,0,0 evs=0,0,0,0,0,0",
     "move": "karatechop"},
    {"id": "sun_boosts_fire", "why": "weather: Drought should multiply Fire by 1.5 and is what decides Blaine",
     "attacker": "charmander level=50 nature=hardy ability=blaze ivs=15,15,15,15,15,15 evs=0,0,0,0,0,0",
     "defender": "bidoof level=50 nature=hardy ability=simple ivs=15,15,15,15,15,15 evs=0,0,0,0,0,0",
     "move": "ember", "setup": ["weather clear", "time set noon"],
     "note": "spawn a torkoal with ability=drought alongside, or the sun will not be up: "
             "/spawnpokemon torkoal level=50 ability=drought"},
]
SAMPLES = 8   # enough to see the 85-100% band; the extremes are 1 roll in 16 each


def prop_line(cmd, props):
    return "%s %s" % (cmd, props)


def plan_lines(m):
    """Every command for one matchup, in order, with the two manual steps called out."""
    out = []
    out.append("# --- %s: %s" % (m["id"], m["why"]))
    for s in m.get("setup") or []:
        out.append(s)
    if m.get("note"):
        out.append("# NOTE: %s" % m["note"])
    out.append("healpokemon @s")
    out.append("clearparty @s")
    out.append(prop_line("givepokemon @s", m["attacker"]))
    out.append("teach @s 0 %s" % m["move"])
    out.append(prop_line("spawnpokemon", m["defender"]))
    out.append("# MANUAL: engage the spawned Pokemon and select %s" % m["move"])
    out.append("getnbt @s 0")
    return out


def expected_band(m):
    """What battle_sim says, with the random roll divided back out: the 85-100% window to compare against."""
    import battle_sim as BS
    species, moves, chart = BS.load_pack(BS.find_jar())

    def build(spec):
        bits = spec.split()
        name, kw = bits[0], dict(b.split("=", 1) for b in bits[1:] if "=" in b)
        ivs = int((kw.get("ivs") or "15").split(",")[0])
        return BS.Mon(species, name, int(kw.get("level", 50)), moves, chart, ivs=ivs,
                      nature=kw.get("nature"), ability=kw.get("ability"),
                      item=(kw.get("held_item") or "").split(":")[-1] or None)

    att, dfn = build(m["attacker"]), build(m["defender"])
    field = BS.Field()
    if m["id"] == "sun_boosts_fire":
        field.weather = "sun"
    mv = moves.get(m["move"])
    if mv is None:
        return None
    d = BS.damage(att, dfn, m["move"], moves, chart, field, species)
    if d <= 0:
        return {"expect": "exactly 0", "defender_hp": dfn.hp}
    centre = d / 0.925 / (mv["accuracy"] / 100.0)
    return {"low": round(centre * 0.85, 1), "high": round(centre, 1),
            "defender_hp": dfn.hp, "move": m["move"], "power": mv["power"]}


def do_plan():
    print(__doc__.split("  python tools/verify_damage.py")[0].strip())
    print("\n%d matchups, %d samples each: %d battles.\n" % (len(MATCHUPS), SAMPLES, len(MATCHUPS) * SAMPLES))
    for m in MATCHUPS:
        band = expected_band(m)
        print("=" * 96)
        for ln in plan_lines(m):
            print("  " + ln)
        print("  EXPECT: %s" % json.dumps(band))
    print("=" * 96)
    print("\nWhat would invalidate the simulator: damage outside the 85-100% band on a neutral hit (a different")
    print("stat formula), a consistent one-or-two-point offset (a different rounding order), Lightning Rod not")
    print("reading exactly 0, Sturdy or Focus Sash not leaving exactly 1, or sun not multiplying Fire by 1.5.")
    return 0


def do_run(server_dir, out_path):
    import runtime_guard
    runtime_guard.require_lock("run the damage verification")
    rcon, pw = runtime_guard.rcon(server_dir)

    def cmd(c, timeout=120):
        return rcon.run([c], pw, timeout=timeout)[0].strip()

    rec = {"started": time.strftime("%Y-%m-%dT%H:%M:%S"), "samples": SAMPLES, "matchups": []}
    for m in MATCHUPS:
        band = expected_band(m)
        obs = []
        print("\n=== %s (%s)" % (m["id"], m["why"]))
        print("    expect %s" % json.dumps(band))
        for i in range(SAMPLES):
            for ln in plan_lines(m):
                if ln.startswith("#"):
                    continue
                if ln.startswith("getnbt"):
                    continue
                cmd(ln)
            before = cmd("getnbt @s 0")
            input("    sample %d/%d: engage the spawn, use %s, then press Enter > " % (i + 1, SAMPLES, m["move"]))
            after = cmd("getnbt @s 0")
            obs.append({"before": before, "after": after})
        rec["matchups"].append({"id": m["id"], "expect": band, "observed": obs})
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8")
    print("\nwrote %s -- the HP fields still need reading out of the NBT blobs by hand" % out_path)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", nargs="?", default="plan", choices=("plan", "run"))
    ap.add_argument("--server-dir")
    ap.add_argument("--out", default=str(ROOT / "derived" / "verify_damage.json"))
    a = ap.parse_args(argv)
    if a.cmd == "run":
        if not a.server_dir:
            ap.error("run needs --server-dir, and the coordination lock")
        return do_run(a.server_dir, a.out)
    return do_plan()


if __name__ == "__main__":
    sys.exit(main())

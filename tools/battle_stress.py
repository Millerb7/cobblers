#!/usr/bin/env python3
"""Stress-test Normal and Challenge gyms against 108 deterministic plausible player teams.

This is a sampling harness around ``tools/battle_sim.py``. It does not add battle
mechanics and it does not change a roster. The sample is intentionally stratified
rather than claimed as player telemetry: all 27 configured starter species appear
four times, and only the collector and critical-path archetypes make even a modest
attempt to answer the current leader.

The fixed seed makes every team and result reproducible. Use ``--markdown`` to write
the full report and ``--json`` to retain the machine-readable run.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import battle_sim as B


ROOT = Path(__file__).resolve().parent.parent
SEED = 20260929
SAMPLE_SIZE = 108
ORDER_SAMPLES = 36
ARCHETYPE_COUNTS = {
    "collector": 24,
    "loyal_six": 18,
    "favourite_heavy": 18,
    "type_blind": 18,
    "critical_path_only": 15,
    "nuzlocke": 15,
}
RARITY_WEIGHT = {"common": 5.0, "uncommon": 3.0, "rare": 1.2, "ultra-rare": 0.35}


@dataclass
class Profile:
    id: int
    starter: str
    archetype: str
    seed: int
    core: list[str] = field(default_factory=list)
    favourite: str | None = None


def mode_trainer(trainer, mode):
    """Return the selected immutable roster as the shape battle_sim expects."""
    if mode not in trainer.get("modes", {}):
        raise B.SimError("%s has no %s mode" % (trainer.get("id"), mode))
    out = dict(trainer)
    out["team"] = trainer["modes"][mode]["team"]
    return out


def unique_rows(rows, cap, species, moves, chart):
    """One catch row per resulting family/form at this cap, preserving provenance."""
    seen, out = set(), []
    for row in rows:
        mon = B.Mon(species, row["species"], cap, moves, chart)
        if mon.name in seen:
            continue
        seen.add(mon.name)
        item = dict(row)
        item["used_as"] = mon.name
        out.append(item)
    return out


def weighted_without_replacement(rng, rows, count, extra_weight=None):
    rows = list(rows)
    picked = []
    while rows and len(picked) < count:
        weights = []
        for row in rows:
            w = RARITY_WEIGHT.get(row.get("bucket"), 1.0)
            if extra_weight:
                w *= max(0.01, float(extra_weight(row)))
            weights.append(w)
        choice = rng.choices(rows, weights=weights, k=1)[0]
        picked.append(choice)
        rows.remove(choice)
    return picked


def build_profiles(starters, gym1_rows, species, moves, chart):
    if SAMPLE_SIZE % len(starters):
        raise B.SimError("sample size must give every starter equal representation")
    labels = [name for name, count in ARCHETYPE_COUNTS.items() for _ in range(count)]
    if len(labels) != SAMPLE_SIZE:
        raise B.SimError("archetype counts total %d, expected %d" % (len(labels), SAMPLE_SIZE))
    random.Random(SEED).shuffle(labels)
    profiles = []
    pool = unique_rows(gym1_rows, 20, species, moves, chart)
    for i in range(SAMPLE_SIZE):
        starter = starters[i % len(starters)]
        rng = random.Random(SEED * 1000 + i)
        eligible = [r for r in pool if B.key(r["species"]) != B.key(starter)]
        core_rows = weighted_without_replacement(rng, eligible, 5)
        core = [r["species"] for r in core_rows]
        favourite = core[rng.randrange(len(core))] if core else starter
        profiles.append(Profile(i + 1, starter, labels[i], SEED * 1000 + i, core, favourite))
    return profiles


def answer_scores(rows, trainer, cap, species, moves, chart):
    foes = B.build_leader(trainer, species, moves, chart, 15, False)
    scores = {}
    for row in rows:
        mon = B.Mon(species, row["species"], cap, moves, chart)
        scores[row["species"]] = sum(
            B.duel(mon, foe, moves, chart, species=species)[0] is mon for foe in foes
        )
    return scores


def level_for(row, cap, archetype, slot, rng):
    floor = int(row.get("hi", row.get("lo", 5)))
    if archetype == "favourite_heavy":
        offsets = [0, 2, 4, 5, 6, 7]
        target = cap - offsets[min(slot, len(offsets) - 1)]
    elif archetype == "loyal_six":
        target = cap - rng.choice([0, 1, 1, 2])
    elif archetype == "nuzlocke":
        target = cap - rng.choice([0, 1, 2, 3])
    else:
        target = cap - rng.choice([0, 0, 1, 1, 2])
    return max(floor, target)


def select_team(profile, gym, rows, trainer, cap, species, moves, chart, scores=None):
    rng = random.Random(profile.seed + gym * 100_003)
    candidates = unique_rows(rows, cap, species, moves, chart)
    by_species = {B.key(r["species"]): r for r in candidates}
    srow = {"species": profile.starter, "bucket": "starter", "pool": "oak", "kind": "starter",
            "off_corridor": 0, "lo": 5, "hi": 5, "used_as": profile.starter}
    available = [r for r in candidates if B.key(r["species"]) != B.key(profile.starter)]
    scores = scores if scores is not None else answer_scores(available, trainer, cap, species, moves, chart)

    def random_rows(source, n):
        return weighted_without_replacement(rng, source, n)

    picked = [srow]
    prepared = False
    if profile.archetype == "collector":
        prepared = True
        answers = [r for r in available if scores.get(r["species"], 0) > 0]
        chosen = weighted_without_replacement(
            rng, answers, 2, lambda r: 1.0 + min(2, scores.get(r["species"], 0)) * 0.35)
        rest = [r for r in available if r not in chosen]
        picked += chosen + random_rows(rest, 5 - len(chosen))
    elif profile.archetype in ("loyal_six", "favourite_heavy"):
        for name in profile.core:
            row = by_species.get(B.key(name))
            if row and row not in picked:
                picked.append(row)
        picked += random_rows([r for r in available if r not in picked], 6 - len(picked))
    elif profile.archetype == "critical_path_only":
        prepared = True
        route_rows = [r for r in available if r.get("kind") == "route" and not r.get("off_corridor")]
        answers = [r for r in route_rows if scores.get(r["species"], 0) > 0]
        chosen = weighted_without_replacement(
            rng, answers, 1, lambda r: 1.0 + min(2, scores.get(r["species"], 0)) * 0.25)
        picked += chosen
        picked += random_rows([r for r in route_rows if r not in chosen], 6 - len(picked))
    elif profile.archetype == "nuzlocke":
        # One random catch per named area. Early gyms may legitimately field fewer than six.
        by_pool = defaultdict(list)
        for row in available:
            by_pool[row.get("pool", "unknown")].append(row)
        catches = []
        for pool in sorted(by_pool):
            catches += weighted_without_replacement(rng, by_pool[pool], 1)
        rng.shuffle(catches)
        picked += catches[:5]
    else:  # type_blind
        picked += random_rows(available, 5)

    # Remove resulting duplicate forms/families and keep at most six.
    clean, seen = [], set()
    for row in picked:
        form = B.Mon(species, row["species"], cap, moves, chart).name
        if form in seen:
            continue
        seen.add(form)
        clean.append(row)
        if len(clean) == 6:
            break

    if profile.archetype == "favourite_heavy":
        clean.sort(key=lambda r: (B.key(r["species"]) != B.key(profile.favourite),
                                  B.key(r["species"]) != B.key(profile.starter)))
    elif profile.archetype in ("loyal_six", "nuzlocke"):
        clean.sort(key=lambda r: B.key(r["species"]) != B.key(profile.starter))
    elif prepared and clean:
        # A prepared player leads the selected member that handles most of this roster.
        clean.sort(key=lambda r: scores.get(r["species"], 0), reverse=True)
    else:
        rng.shuffle(clean)

    specs = []
    for slot, row in enumerate(clean):
        specs.append({
            "species": row["species"],
            "level": level_for(row, cap, profile.archetype, slot, rng),
            "pool": row.get("pool", "oak"),
        })
    return specs


def build_player(specs, species, moves, chart, *, cap, at_cap=False, order=None):
    rows = specs if order is None else [specs[i] for i in order]
    return [B.Mon(species, s["species"], cap if at_cap else s["level"], moves, chart) for s in rows]


def stripped_trainer(trainer):
    """Same species and levels, but no authored items, abilities, natures, or movesets."""
    out = dict(trainer)
    out["team"] = [{"species": m["species"], "level": m["level"]} for m in trainer["team"]]
    return out


def fight(specs, trainer, species, moves, chart, *, at_cap=False, order=None):
    cap = max(m["level"] for m in trainer["team"])
    team = build_player(specs, species, moves, chart, cap=cap, at_cap=at_cap, order=order)
    foes = B.build_leader(trainer, species, moves, chart, 15, False)
    won, faints, downed, left = B.run_gauntlet(team, foes, moves, chart, species=species)
    return {"won": won, "faints": faints, "downed": downed, "left": round(left, 4)}


def sampled_order_wins(specs, trainer, species, moves, chart, *, at_cap=False):
    """Try every order for short teams and 36 stable orders for full teams.

    This is a scouting sensitivity, not an exhaustive ceiling for six-member teams.
    Full enumeration would multiply this already-large run by 720 and still would not
    model switching, so it would add precision without answering the missing question.
    """
    orders = list(itertools.permutations(range(len(specs))))
    if len(orders) > ORDER_SAMPLES:
        payload = json.dumps(specs, sort_keys=True).encode("utf-8")
        seed = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
        rng = random.Random(seed)
        chosen = [tuple(range(len(specs)))]
        remaining = [o for o in orders if o != chosen[0]]
        chosen += rng.sample(remaining, ORDER_SAMPLES - 1)
        orders = chosen
    for order in orders:
        result = fight(specs, trainer, species, moves, chart, at_cap=at_cap, order=order)
        if result["won"]:
            return True
    return False


def classify_loss(*, cap_same, reorder, cap_reorder, stripped_reorder):
    if cap_same:
        return "wrong_levels"
    if reorder:
        return "gimmick_or_order"
    if cap_reorder:
        return "wrong_levels_and_order"
    if stripped_reorder:
        return "gimmick"
    return "no_answer_in_model"


def team_label(specs):
    return ", ".join("%s L%d" % (s["species"], s["level"]) for s in specs)


def verdict(summary):
    win = summary["win_rate"]
    prepared = summary["prepared_win_rate"]
    ceiling = summary["sampled_reorder_win_rate"]
    impossible = 100.0 - summary["cap_sampled_reorder_win_rate"]
    faints = summary["average_faints_on_win"]
    if win >= 85 and faints <= 1.5:
        return "trivial"
    if prepared >= 65 and win >= 45 and impossible <= 10:
        return "fair"
    if ceiling >= 65 and impossible <= 20:
        return "punishing but fair"
    return "unwinnable risk"


def summarise_runs(runs):
    wins = [r for r in runs if r["result"]["won"]]
    prepared = [r for r in runs if r["prepared"]]
    type_blind = [r for r in runs if r["archetype"] == "type_blind"]
    nuz = [r for r in runs if r["archetype"] == "nuzlocke"]
    losses = Counter(r["loss_reason"] for r in runs if not r["result"]["won"])
    out = {
        "teams": len(runs),
        "wins": len(wins),
        "win_rate": round(100 * len(wins) / len(runs), 1),
        "average_faints_on_win": round(sum(r["result"]["faints"] for r in wins) / len(wins), 2)
            if wins else None,
        "prepared_win_rate": round(100 * sum(r["result"]["won"] for r in prepared) / len(prepared), 1),
        "sampled_reorder_win_rate": round(100 * sum(r["sampled_reorder_wins"] for r in runs) / len(runs), 1),
        "cap_sampled_reorder_win_rate": round(
            100 * sum(r["cap_sampled_reorder_wins"] for r in runs) / len(runs), 1),
        "type_blind_wins": sum(r["result"]["won"] for r in type_blind),
        "type_blind_teams": len(type_blind),
        "nuzlocke_wins": sum(r["result"]["won"] for r in nuz),
        "nuzlocke_teams": len(nuz),
        "nuzlocke_clean_wins": sum(r["result"]["won"] and r["result"]["faints"] == 0 for r in nuz),
        "nuzlocke_average_deaths_on_win": round(
            sum(r["result"]["faints"] for r in nuz if r["result"]["won"])
            / max(1, sum(r["result"]["won"] for r in nuz)), 2),
        "loss_reasons": dict(sorted(losses.items())),
    }
    out["verdict"] = verdict(out)
    return out


def run():
    jar = B.find_jar()
    species, moves, chart = B.load_pack(jar)
    # battle_sim's reader deliberately narrows rows to the fields its old report needs.
    # This sampler needs pool/kind/bucket/off_corridor to distinguish route-only and
    # one-catch-per-area profiles, so read the generated sidecar directly.
    sidecar = json.loads(B.AVAIL_JSON.read_text(encoding="utf-8"))
    avail = {int(g): {"rows": rows} for g, rows in sidecar["gyms"].items()}
    leaders, _contract = B.gym_leaders()
    starters = B.config_starters()
    if len(starters) != 27:
        raise B.SimError("expected 27 unique configured starters, found %d" % len(starters))
    profiles = build_profiles(starters, avail[1]["rows"], species, moves, chart)
    results = {"seed": SEED, "sample_size": SAMPLE_SIZE, "archetypes": ARCHETYPE_COUNTS,
               "starters": starters, "gyms": {}}
    for gym in range(1, 9):
        results["gyms"][str(gym)] = {}
        cap = int(sidecar["caps"][str(gym)])
        # Generate one party per profile and pair it against both modes. Preparation
        # uses the Normal presentation of the gym; otherwise Challenge gets a better
        # bespoke sample and the mode comparison stops measuring the roster change.
        sample_trainer = mode_trainer(leaders[gym], "normal")
        sample_scores = answer_scores(
            unique_rows(avail[gym]["rows"], cap, species, moves, chart), sample_trainer,
            cap, species, moves, chart)
        sampled_teams = {
            profile.id: select_team(profile, gym, avail[gym]["rows"], sample_trainer, cap,
                                    species, moves, chart, scores=sample_scores)
            for profile in profiles
        }
        for mode in ("normal", "challenge"):
            trainer = mode_trainer(leaders[gym], mode)
            runs = []
            for profile in profiles:
                specs = sampled_teams[profile.id]
                result = fight(specs, trainer, species, moves, chart)
                reorder = result["won"] or sampled_order_wins(specs, trainer, species, moves, chart)
                cap_same = result["won"] or fight(
                    specs, trainer, species, moves, chart, at_cap=True)["won"]
                cap_reorder = reorder or cap_same or sampled_order_wins(
                    specs, trainer, species, moves, chart, at_cap=True)
                stripped_reorder = cap_reorder or sampled_order_wins(
                    specs, stripped_trainer(trainer), species, moves, chart, at_cap=True)
                reason = None if result["won"] else classify_loss(
                    cap_same=cap_same, reorder=reorder, cap_reorder=cap_reorder,
                    stripped_reorder=stripped_reorder)
                runs.append({
                    "profile": profile.id,
                    "starter": profile.starter,
                    "archetype": profile.archetype,
                    "prepared": profile.archetype in ("collector", "critical_path_only"),
                    "team": specs,
                    "result": result,
                    "sampled_reorder_wins": reorder,
                    "cap_sampled_reorder_wins": cap_reorder,
                    "loss_reason": reason,
                })
            results["gyms"][str(gym)][mode] = {"summary": summarise_runs(runs), "runs": runs}
    return results


def write_markdown(results, path):
    lines = [
        "# Realistic-team gym stress test",
        "",
        "**Generated:** `python tools/battle_stress.py --markdown docs/story/BATTLE_STRESS.md`",
        "",
        "This is a deterministic structural stress test, not play evidence. It runs 108 sampled profiles per gym",
        "and mode against the exact committed rosters, using the fixed-order/no-switch engine in",
        "`tools/battle_sim.py`. No roster is changed.",
        "",
        "## Sample",
        "",
        "The seed is `%d`. All 27 configured starter species appear exactly four times. The archetypes are:" % results["seed"],
        "",
        "| Archetype | Teams | Selection and levelling |",
        "| --- | ---: | --- |",
        "| Collector | 24 | Broad catches; only two slots deliberately seek a positive matchup; even levels. |",
        "| Loyal six | 18 | Starter plus five early catches retained; nearly even levels. |",
        "| Favourite-heavy | 18 | Early core retained; favourite at cap, four members trail by 4-7 levels. |",
        "| Type-blind | 18 | Rarity-weighted catches with no matchup check; even levels. |",
        "| Critical-path only | 15 | Route pools only; one modestly informed answer, no optional subregions. |",
        "| Nuzlocke-shaped | 15 | One random catch per named pool, no matchup selection; early teams may have fewer than six. |",
        "",
        "Common encounters are 4.2 times as likely to be selected as rare encounters and 14.3 times as likely",
        "as ultra-rare encounters. This is a design assumption, not player telemetry. Only 39 of 108 profiles",
        "prepare for the leader at all, preventing the sample from quietly becoming 108 informed teams.",
        "Each profile uses the exact same party against Normal and Challenge. Modest preparation reads the Normal",
        "presentation of the gym so Challenge does not receive a secretly hand-picked comparison sample.",
        "",
        "`Sampled reorder` means at least one of 36 deterministic pre-battle orders of the same team wins. It",
        "does not model switching and is not an exhaustive ceiling. `Cap sampled reorder` also raises every",
        "straggler to the cap and is used only to separate level failures from composition failures.",
        "",
        "## Results",
        "",
        "| Gym | Mode | First-order wins | Avg losses on win | Prepared wins | Sampled reorder | Cap sampled reorder | Blind wins | Nuzlocke wins (clean) | Verdict |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for gym in range(1, 9):
        for mode in ("normal", "challenge"):
            s = results["gyms"][str(gym)][mode]["summary"]
            lines.append("| %d | %s | %.1f%% | %s | %.1f%% | %.1f%% | %.1f%% | %d/%d | %d/%d (%d) | **%s** |" % (
                gym, mode.title(), s["win_rate"],
                "—" if s["average_faints_on_win"] is None else "%.2f" % s["average_faints_on_win"],
                s["prepared_win_rate"], s["sampled_reorder_win_rate"],
                s["cap_sampled_reorder_win_rate"],
                s["type_blind_wins"], s["type_blind_teams"], s["nuzlocke_wins"],
                s["nuzlocke_teams"], s["nuzlocke_clean_wins"], s["verdict"]))
    lines += ["", "## Loss diagnosis", "",
              "The engine has no random rolls, critical hits, secondary effects, or move-choice variance, so it",
              "assigns **zero losses to bad luck**. That is a simulator limitation, not a claim that bad luck",
              "cannot decide the real fight.", ""]
    for gym in range(1, 9):
        lines += ["### Gym %d" % gym, ""]
        for mode in ("normal", "challenge"):
            block = results["gyms"][str(gym)][mode]
            s = block["summary"]
            reasons = ", ".join("%s %d" % (k.replace("_", " "), v)
                                for k, v in s["loss_reasons"].items()) or "none"
            losers = [r for r in block["runs"] if not r["result"]["won"]][:3]
            lines.append("- **%s:** %s. Representative losses: %s." % (
                mode.title(), reasons,
                "; ".join("%s (%s; %s)" % (team_label(r["team"]), r["archetype"],
                                            r["loss_reason"].replace("_", " ")) for r in losers) or "none"))
        lines.append("")
    lines += [
        "## Nuzlocke reading",
        "",
        "A Nuzlocke win with fainted members is recorded as a win here but those members are permanent deaths.",
        "The table's clean count is therefore the only run that advances without attrition. These are independent",
        "gym snapshots; deaths are not carried from one gym into the next, so the report is optimistic for a full",
        "campaign Nuzlocke.",
        "",
        "## What the simulator cannot settle",
        "",
        "- **No switching:** the percentages are fixed-order first attempts. Any-order tests scouting and lead order,",
        "  but neither player switching nor the leaders' configured switch bias runs. A team marked unable to win",
        "  may still win through intelligent switches; hazards and Intimidate may also make switching worse.",
        "- **No player items:** the authored rules set max item uses to zero, so this matches the current roster data,",
        "  but any runtime rule that permits bag items would raise player results.",
        "- **No battle RNG:** accuracy is averaged into damage; crits, flinches, confusion, secondary status and damage",
        "  rolls do not exist. The tool cannot measure luck and overstates the certainty of close outcomes.",
        "- **Incomplete mechanics:** hazards, Protect, Substitute, Encore, Taunt, Pain Split, Trick Room, Tailwind,",
        "  Baton Pass and many abilities are inert. Gym-specific sensitivity must be read beside these numbers.",
        "- **Player moves:** player sets use level-up moves only and no held items. TMs and deliberate player items",
        "  would improve real prepared teams, so the results lean against the player.",
        "- **Stats:** both sides use IV 15 and EV 0. Real captures and trained teams vary.",
        "- **Engine parity:** the mainline damage formula used here has never been checked against Cobblemon's embedded",
        "  Showdown at these levels. A result resting on one surviving hit is not a verdict until EXP-010 runs.",
        "",
    ]
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--markdown")
    ap.add_argument("--json")
    args = ap.parse_args(argv)
    results = run()
    if args.markdown:
        write_markdown(results, ROOT / args.markdown)
        print("wrote %s" % args.markdown)
    if args.json:
        (ROOT / args.json).write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        print("wrote %s" % args.json)
    if not args.markdown and not args.json:
        for gym in range(1, 9):
            print("Gym %d" % gym)
            for mode in ("normal", "challenge"):
                print("  %-9s %s" % (mode, results["gyms"][str(gym)][mode]["summary"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Generate data/trainers.json from the campaign trainer rule set.

This file intentionally lives beside the human-editable rule set in docs/story.
It emits campaign source data with embedded RCT-ready trainer payloads; installing
those payloads into a datapack is a separate, unimplemented build step.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = ROOT / "docs" / "story" / "TRAINER_RULES.json"
ROUTES_PATH = ROOT / "data" / "routes.json"
OUTPUT_PATH = ROOT / "data" / "trainers.json"
AI_KEYS = {"moveBias", "switchBias", "statusMoveBias", "itemBias", "maxSelectMargin"}
# A Challenge team is installed under its own rctmod id, <id>_challenge (tools/challenge_mode.py,
# docs/mechanics/OAK_AND_CHALLENGE.md), and rctmod refuses to spawn a second trainer of the same IDENTITY within
# uniqueTrainerRadius of the first (TrainerSpawner.isUnique, docs/research/RCT_PER_PLAYER_MODE.md section 2). Both
# leaders stand in one gym, so the Challenge payload carries an identity of its own.
CHALLENGE_SUFFIX = "_challenge"
RUNTIME_MODE_SELECTION = (
    "per player: Oak records the choice once (quest.main_worldshift_reveal.trainer_mode) and puts a Challenge "
    "player in rctmod series cobblers_challenge; each record's modes.challenge.rct is installed as "
    "<rctmod id>_challenge by tools/challenge_mode.py (docs/mechanics/OAK_AND_CHALLENGE.md); top-level team and "
    "rct mirror normal"
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def nearest_vertex(polyline, target_distance):
    walked = 0.0
    best = (abs(target_distance), 0, polyline[0])
    for index in range(1, len(polyline)):
        a, b = polyline[index - 1], polyline[index]
        walked += math.hypot(b["x"] - a["x"], b["z"] - a["z"])
        candidate = (abs(walked - target_distance), index, b)
        if candidate[0] < best[0]:
            best = candidate
    return best[1], best[2], round(walked, 3)


def trainer_ai(profile_name, rules):
    data = deepcopy(rules["ai_profiles"][profile_name])
    if set(data) != AI_KEYS:
        raise ValueError(f"AI profile {profile_name} must contain exactly {sorted(AI_KEYS)}")
    if data["maxSelectMargin"] <= 0:
        raise ValueError(f"AI profile {profile_name} maxSelectMargin must be positive")
    return {"type": "rct", "data": data}


def validate_pokemon(pokemon, context):
    if not pokemon.get("species"):
        raise ValueError(f"{context}: missing species")
    if not 1 <= pokemon.get("level", 0) <= 100:
        raise ValueError(f"{context}: level must be 1..100")
    if len(pokemon.get("moveset", [])) > 4:
        raise ValueError(f"{context}: RCT accepts at most four moves")
    ivs = pokemon.get("ivs", {})
    evs = pokemon.get("evs", {})
    if any(not 0 <= value <= 31 for value in ivs.values()):
        raise ValueError(f"{context}: IV outside 0..31")
    if any(not 0 <= value <= 252 for value in evs.values()) or sum(evs.values()) > 510:
        raise ValueError(f"{context}: EV spread violates campaign limits")


def make_rct(trainer, rules):
    payload = {
        "identity": trainer.get("identity", trainer["id"]),
        "name": {"literal": trainer["name"]},
        "battleFormat": trainer.get("battle_format", "GEN_9_SINGLES"),
        "battleRules": {
            "maxItemUses": trainer.get("max_item_uses", 0),
            "healPlayers": False,
            "adjustPlayerLevels": False,
            "adjustNPCLevels": False,
        },
        "ai": trainer_ai(trainer["ai_profile"], rules),
        "bag": deepcopy(trainer.get("bag", [])),
        "team": deepcopy(trainer["team"]),
    }
    for index, pokemon in enumerate(payload["team"], 1):
        validate_pokemon(pokemon, f"{trainer['id']} team member {index}")
    if len(payload["team"]) > 6:
        raise ValueError(f"{trainer['id']}: RCT truncates teams above six")
    return payload


def boss_level(ace_level, offset):
    return ace_level + offset


def build_boss_mode(slot, mode_name, rules):
    """Build one boss mode. Normal inherits the slot; Challenge overlays it."""
    mode = deepcopy(slot.get("modes", {}).get(mode_name, {}))
    members = mode.get("members", slot.get("members", []))
    if not members:
        return None
    team = []
    ace_count = 0
    ace_species = None
    for member in members:
        pokemon = deepcopy(member)
        pokemon["level"] = boss_level(slot["ace_level"], pokemon.pop("level_offset"))
        if pokemon.pop("ace", False):
            ace_count += 1
            ace_species = pokemon["species"]
        team.append(pokemon)
    if ace_count != 1:
        raise ValueError(f"{slot['id']} {mode_name}: expected exactly one ace, found {ace_count}")
    if max(member["level"] for member in team) != slot["ace_level"]:
        raise ValueError(f"{slot['id']} {mode_name}: ace level is not the team ceiling")
    ai_profile = mode.get("ai_profile", slot["ai_profile"])
    source = {
        "id": slot["id"],
        "identity": slot["id"] + (CHALLENGE_SUFFIX if mode_name == "challenge" else ""),
        "name": slot["name"],
        "ai_profile": ai_profile,
        "battle_format": mode.get("battle_format", slot.get("battle_format", "GEN_9_SINGLES")),
        "max_item_uses": mode.get("max_item_uses", slot.get("max_item_uses", 0)),
        "bag": mode.get("bag", slot.get("bag", [])),
        "team": team,
    }
    return {
        "strategy": mode.get("strategy", slot["strategy"]),
        "ace_species": ace_species,
        "ace_math_change": mode.get("ace_math_change", slot["ace_math_change"]),
        "member_count": len(team),
        "ai_profile": ai_profile,
        "team": deepcopy(team),
        "rct": make_rct(source, rules),
        "open_line": deepcopy(mode.get("open_line", [])),
        "line_obviousness": mode.get("line_obviousness"),
    }


def build_bosses(rules):
    result = []
    expected_aces = rules["difficulty"]["gym_ace_levels"]
    seen_gym_aces = []
    for slot in rules["bosses"]:
        entry = {
            "id": slot["id"],
            "display_name": slot["name"],
            "class": {"gym": "gym_leader", "elite_four": "elite_four", "champion": "champion"}[slot["category"]],
            "order": slot["order"],
            "theme": slot["theme"],
            "status": slot.get("status", "authored"),
            "strategy": slot["strategy"],
            "format": slot.get("battle_format", "GEN_9_SINGLES"),
            "team": [],
            "dialogue": deepcopy(slot["dialogue"]),
        }
        if slot["category"] == "gym":
            seen_gym_aces.append(slot["ace_level"])
        if entry["status"] == "held":
            entry["blocked_by"] = slot["blocked_by"]
            result.append(entry)
            continue
        normal = build_boss_mode(slot, "normal", rules)
        challenge = build_boss_mode(slot, "challenge", rules)
        if challenge is None:
            # an Elite Four or Champion slot with no Challenge members: the same team, under its own identity
            challenge = deepcopy(normal)
            challenge["rct"]["identity"] = slot["id"] + CHALLENGE_SUFFIX
        entry.update(
            {
                "ace_level": slot["ace_level"],
                "ace_species": normal["ace_species"],
                "ace_math_change": normal["ace_math_change"],
                "member_count": normal["member_count"],
                "team": deepcopy(normal["team"]),
                "availability_contract": deepcopy(slot["availability_contract"]),
                "rct": deepcopy(normal["rct"]),
                "modes": {"normal": normal, "challenge": challenge},
            }
        )
        result.append(entry)
    if seen_gym_aces != expected_aces:
        raise ValueError(f"gym ace curve {seen_gym_aces} != configured {expected_aces}")
    return result


def choose_team(placement_index, role, route, rules):
    explicit = route["placements"][placement_index].get("team_species")
    if explicit:
        unknown = [species for species in explicit if species not in rules["species_kits"]]
        if unknown:
            raise ValueError(
                f"{route['id']} placement {placement_index + 1}: unknown species kits {unknown}"
            )
        return explicit
    profile = rules["route_archetypes"][role]
    count = profile["member_count"]
    pool_name = profile.get("pool", "ambient_pool")
    pool = route[pool_name]
    start = (placement_index * 2 + route["pool_rotation"]) % len(pool)
    selected = [pool[(start + step) % len(pool)] for step in range(count)]
    return selected


def build_route_mode(base_team, placement, route_rule, mode_name, rules):
    """Create a route-trainer mode without changing its level ceiling."""
    team = deepcopy(base_team)
    if mode_name == "challenge":
        config = route_rule.get("challenge", {})
        if placement["role"] in config.get("extra_member_roles", []):
            pool = route_rule.get(config.get("extra_member_pool", "ambient_pool"), [])
            used = {member["species"] for member in team}
            extra_key = next((key for key in pool if rules["species_kits"][key]["species"] not in used), None)
            if extra_key:
                extra = deepcopy(rules["species_kits"][extra_key])
                extra["level"] = max(member["level"] for member in team) - 1
                team.insert(-1 if len(team) > 1 else len(team), extra)
        item = placement.get("challenge_held_item", config.get("held_item"))
        if item and team:
            team[-1]["heldItem"] = item
        overrides = placement.get("challenge_movesets")
        if overrides is not None:
            if len(overrides) != len(team):
                raise ValueError(f"{route_rule['id']} {placement['name']}: challenge_movesets must match challenge team")
            for pokemon, moveset in zip(team, overrides):
                pokemon["moveset"] = deepcopy(moveset)
    ai_profile = placement.get(
        f"{mode_name}_ai_profile",
        route_rule.get(mode_name, {}).get("ai_profile", "route_standard" if mode_name == "normal" else "route_challenge"),
    )
    return team, ai_profile


def build_route_trainers(rules, routes_doc, route_orders=None):
    route_index = {route["id"]: route for route in routes_doc["routes"]}
    generated = []
    for route_rule in rules["routes"]:
        if route_orders is not None and route_rule["order"] not in route_orders:
            continue
        route = route_index[route_rule["id"]]
        polyline = route["corridor"]["polyline"]
        band = route["party_level_band"]
        placements = route_rule["placements"]
        if route_rule["expected_count"] != len(placements):
            raise ValueError(f"{route_rule['id']}: expected_count mismatch")
        previous_distance = -1
        for index, placement in enumerate(placements, 1):
            distance = placement["at_distance_blocks"]
            if distance <= previous_distance:
                raise ValueError(f"{route_rule['id']}: placements must be ordered")
            previous_distance = distance
            fixed_xyz = placement.get("fixed_coordinate_xyz")
            if fixed_xyz is not None:
                if len(fixed_xyz) != 3:
                    raise ValueError(f"{route_rule['id']} placement {index}: fixed_coordinate_xyz must be x/y/z")
                point = {"x": fixed_xyz[0], "y": fixed_xyz[1], "z": fixed_xyz[2]}
                vertex_index = None
                measured_total = route_rule["placement_route_length"]
            else:
                vertex_index, point, measured_total = nearest_vertex(polyline, distance)
            expected = placement["expected_coordinate"]
            route_anchor = placement.get("route_anchor_coordinate", expected)
            if [point["x"], point["z"]] != route_anchor:
                raise ValueError(
                    f"{route_rule['id']} placement {index}: derived coordinate "
                    f"{[point['x'], point['z']]} != configured anchor {route_anchor}"
                )
            off_route = placement.get("off_route", False)
            actual_x, actual_z = expected if off_route else [point["x"], point["z"]]
            if off_route:
                measured_gap = math.hypot(
                    actual_x - point["x"], actual_z - point["z"]
                )
                expected_gap = placement["off_route_gap_blocks"]
                if abs(measured_gap - expected_gap) > 0.6:
                    raise ValueError(
                        f"{route_rule['id']} placement {index}: off-route gap "
                        f"{measured_gap:.1f} != configured {expected_gap}"
                    )
            progress = distance / measured_total
            base_level = round(band["minimum"] + progress * (band["maximum"] - band["minimum"] - 1))
            explicit_modes = placement.get("teams")
            if explicit_modes is not None:
                if set(explicit_modes) != {"normal", "challenge"}:
                    raise ValueError(f"{route_rule['id']} placement {index}: teams must define normal and challenge")
                normal_team = deepcopy(explicit_modes["normal"])
                challenge_team = deepcopy(explicit_modes["challenge"])
                normal_ai = placement.get("normal_ai_profile", "route_normal")
                challenge_ai = placement.get("challenge_ai_profile", "route_challenge")
            else:
                selected = choose_team(index - 1, placement["role"], route_rule, rules)
                move_overrides = placement.get("movesets")
                if move_overrides is not None and len(move_overrides) != len(selected):
                    raise ValueError(
                        f"{route_rule['id']} placement {index}: movesets must match team_species"
                    )
                team = []
                for team_index, species_key in enumerate(selected):
                    kit = deepcopy(rules["species_kits"][species_key])
                    if move_overrides is not None:
                        kit["moveset"] = deepcopy(move_overrides[team_index])
                    kit["level"] = max(band["minimum"], base_level - (len(selected) - team_index - 1))
                    team.append(kit)
                normal_team, normal_ai = build_route_mode(team, placement, route_rule, "normal", rules)
                challenge_team, challenge_ai = build_route_mode(team, placement, route_rule, "challenge", rules)
            trainer_id = placement.get(
                "id", f"route_{route_rule['order']:02d}_trainer_{index:02d}"
            )
            source = {
                "id": trainer_id,
                "name": placement["name"],
                "ai_profile": normal_ai,
                "team": normal_team,
            }
            challenge_source = {
                "id": trainer_id,
                "identity": trainer_id + CHALLENGE_SUFFIX,
                "name": placement["name"],
                "ai_profile": challenge_ai,
                "team": challenge_team,
            }
            placement_payload = {
                "status": "proposed",
                "at_distance_blocks": distance,
                "progress_fraction": round(progress, 4),
                "polyline_vertex_index": vertex_index,
                "x": actual_x,
                "z": actual_z,
                "sampled_y": placement.get("sampled_y", point.get("y")),
                "route_measured_blocks": measured_total,
            }
            if fixed_xyz is not None:
                placement_payload["placement_authority"] = "data/vr_caves.json trainer stand"
            if off_route:
                placement_payload.update(
                    {
                        "off_route": True,
                        "route_anchor": {"x": point["x"], "z": point["z"]},
                        "off_route_gap_blocks": placement["off_route_gap_blocks"],
                        "shared_route_ids": placement.get("shared_route_ids", []),
                    }
                )
            generated.append(
                {
                    "id": trainer_id,
                    "display_name": placement["name"],
                    "class": "optional_route" if off_route else "route",
                    "format": "GEN_9_SINGLES",
                    "team": deepcopy(normal_team),
                    "route_id": route_rule["id"],
                    "route_order": route_rule["order"],
                    "trainer_order": index,
                    "route_theme": route_rule.get("theme"),
                    "mode_intent": {
                        "normal": route_rule.get("normal", {}).get("intent"),
                        "challenge": route_rule.get("challenge", {}).get("intent"),
                    },
                    "archetype": placement["role"],
                    "lesson": placement["lesson"],
                    "placement": placement_payload,
                    "dialogue": {
                        "pre": f"dlg_{trainer_id}_pre",
                        "win": f"dlg_{trainer_id}_win",
                        "loss": f"dlg_{trainer_id}_loss",
                    },
                    "dialogue_text": deepcopy(placement.get("dialogue_text", {})),
                    "rct": make_rct(source, rules),
                    "modes": {
                        "normal": {
                            "team": deepcopy(normal_team),
                            "ai_profile": normal_ai,
                            "rct": make_rct(source, rules),
                        },
                        "challenge": {
                            "team": deepcopy(challenge_team),
                            "ai_profile": challenge_ai,
                            "rct": make_rct(challenge_source, rules),
                        },
                    },
                }
            )
    return generated


def build_gym_trainers(rules):
    """The gym juniors (TRAINER_RULES gym_trainers): explicit Normal and Challenge teams, both below the leader's ace.

    Fails rather than adjusts: a member at or over its gym's ace, a Challenge top level that differs from Normal's
    (the caps do not move between modes), or a gym whose juniors' top levels fall in the order they are listed --
    which is the order a player reaches them (data/gym_junior_trainers.json, proved by tools/gym_trainers.py)."""
    section = rules.get("gym_trainers")
    if not section:
        return []
    aces = rules["difficulty"]["gym_ace_levels"]
    profiles = section["ai_profiles"]
    out, last_top = [], {}
    by_gym = {}
    for slot in section["trainers"]:
        by_gym[slot["gym"]] = by_gym.get(slot["gym"], 0) + 1
        ace = aces[slot["gym"] - 1]
        tops = {}
        for mode_name in ("normal", "challenge"):
            team = slot["teams"][mode_name]
            if not team:
                raise ValueError(f"{slot['id']} {mode_name}: empty team")
            over = [m["species"] for m in team if m["level"] >= ace]
            if over:
                raise ValueError(f"{slot['id']} {mode_name}: {over} at or over gym {slot['gym']}'s ace {ace}")
            tops[mode_name] = max(m["level"] for m in team)
        if tops["normal"] != tops["challenge"]:
            raise ValueError(f"{slot['id']}: Challenge tops out at {tops['challenge']}, Normal at {tops['normal']}")
        if len(slot["teams"]["challenge"]) != len(slot["teams"]["normal"]) + 1:
            raise ValueError(f"{slot['id']}: Challenge adds exactly one member to Normal")
        if tops["normal"] < last_top.get(slot["gym"], 0):
            raise ValueError(f"{slot['id']}: tops out below the junior a player passes before it")
        last_top[slot["gym"]] = tops["normal"]
        modes = {}
        for mode_name in ("normal", "challenge"):
            # a Challenge copy stands beside the Normal one in the gym, so it carries an identity of its own
            source = {"id": slot["id"], "name": slot["name"], "ai_profile": profiles[mode_name],
                      "team": slot["teams"][mode_name],
                      "identity": slot["id"] + (CHALLENGE_SUFFIX if mode_name == "challenge" else "")}
            modes[mode_name] = {"team": deepcopy(slot["teams"][mode_name]), "ai_profile": profiles[mode_name],
                                "rct": make_rct(source, rules)}
        out.append({
            "id": slot["id"],
            "display_name": slot["name"],
            "class": "gym_trainer",
            "format": "GEN_9_SINGLES",
            "team": deepcopy(modes["normal"]["team"]),
            "gym_order": slot["gym"],
            # the stretch of the game it belongs to, for tools/challenge_guide.py (1-8: the gym's own split)
            "split": slot["gym"],
            "leader_ace_level": ace,
            "type_theme": slot["type"],
            "trainer_order": by_gym[slot["gym"]],
            "lesson": slot["lesson"],
            "dialogue": {"pre": f"dlg_{slot['id']}_pre", "win": f"dlg_{slot['id']}_win",
                         "loss": f"dlg_{slot['id']}_loss"},
            "dialogue_text": deepcopy(slot["dialogue_text"]),
            "rct": deepcopy(modes["normal"]["rct"]),
            "modes": modes,
        })
    return out


def build_document(rules, routes):
    bosses = build_bosses(rules)
    route_trainers = build_route_trainers(rules, routes)
    gym_trainers = build_gym_trainers(rules)
    return {
        "schema": "cobblers.trainers/1",
        "schema_version": 1,
        "generated_from": "docs/story/TRAINER_RULES.json",
        "generator": "docs/story/generate_trainers.py",
        "target": {
            "minecraft": "1.21.1",
            "cobblemon": "1.8.x",
            "rctmod": "0.19.0-beta",
            "rctapi": "0.16.1-beta",
        },
        "generation_contract": {
            "relative_level_cap": rules["difficulty"]["relative_level_cap"],
            "gym_ace_levels": rules["difficulty"]["gym_ace_levels"],
            "boss_slots": len(bosses),
            "authored_boss_rosters": sum(boss["status"] != "held" for boss in bosses),
            "held_boss_slots": sum(boss["status"] == "held" for boss in bosses),
            "route_trainers": len(route_trainers),
            "gym_trainers": len(gym_trainers),
            "placement_status": "proposal_only",
            "dialogue_ids": "campaign metadata; RCT sidecars require a future compiler",
            "difficulty_modes": ["normal", "challenge"],
            "runtime_mode_selection": RUNTIME_MODE_SELECTION,
        },
        "trainers": bosses + route_trainers + gym_trainers,
    }


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="write data/trainers.json")
    mode.add_argument("--check", action="store_true", help="check committed output is current")
    mode.add_argument(
        "--write-early",
        action="store_true",
        help="replace only route 1-3 trainer records in data/trainers.json",
    )
    mode.add_argument(
        "--check-early",
        action="store_true",
        help="check only route 1-3 trainer records without evaluating later routes",
    )
    mode.add_argument(
        "--write-active",
        action="store_true",
        help="replace bosses and routes 1-9 from the current authored rules",
    )
    mode.add_argument(
        "--check-active",
        action="store_true",
        help="check bosses and routes 1-9 from the current authored rules",
    )
    args = parser.parse_args()

    rules = load_json(RULES_PATH)
    routes = load_json(ROUTES_PATH)
    if args.write_active or args.check_active:
        current_document = load_json(OUTPUT_PATH)
        active = build_bosses(rules) + build_route_trainers(
            rules, routes, route_orders=set(range(1, 10))
        ) + build_gym_trainers(rules)
        rebuilt = active
        expected = deepcopy(current_document)
        expected["trainers"] = rebuilt
        expected["target"]["rctapi"] = "0.16.1-beta"
        expected["generation_contract"].update(
            {
                "difficulty_modes": ["normal", "challenge"],
                "runtime_mode_selection": RUNTIME_MODE_SELECTION,
                "authored_boss_rosters": sum(
                    trainer.get("class") in {"gym_leader", "elite_four", "champion"}
                    and trainer.get("status") != "held"
                    for trainer in rebuilt
                ),
                "held_boss_slots": sum(
                    trainer.get("class") in {"gym_leader", "elite_four", "champion"}
                    and trainer.get("status") == "held"
                    for trainer in rebuilt
                ),
                "route_trainers": sum(
                    trainer.get("class") in {"route", "optional_route"}
                    for trainer in rebuilt
                ),
                "preserved_blocked_route_orders": [],
                "gym_trainers": sum(trainer.get("class") == "gym_trainer" for trainer in rebuilt),
            }
        )
        rendered = json.dumps(expected, indent=2, ensure_ascii=False) + "\n"
        if args.check_active:
            if OUTPUT_PATH.read_text(encoding="utf-8") != rendered:
                print("stale active trainer modes: run --write-active", file=sys.stderr)
                return 1
            print(f"ok: {len(active)} active boss/route records; Victory Road uses ten cave stands")
            return 0
        OUTPUT_PATH.write_text(rendered, encoding="utf-8", newline="\n")
        print(f"updated {len(active)} active boss/route records; Victory Road uses ten cave stands")
        return 0
    if args.write_early or args.check_early:
        early = build_route_trainers(rules, routes, route_orders={1, 2, 3})
        current_document = load_json(OUTPUT_PATH)
        current_early = [
            trainer
            for trainer in current_document["trainers"]
            if trainer.get("class") in {"route", "optional_route"}
            and trainer.get("route_order") in {1, 2, 3}
        ]
        if args.check_early:
            if current_early != early:
                print(
                    f"stale early routes: run {Path(__file__).relative_to(ROOT)} --write-early",
                    file=sys.stderr,
                )
                return 1
            print(f"ok: {len(early)} route 1-3 trainers")
            return 0
        early_ids = {trainer["id"] for trainer in early}
        rebuilt = []
        inserted = False
        for trainer in current_document["trainers"]:
            if trainer["id"] in early_ids:
                if not inserted:
                    rebuilt.extend(early)
                    inserted = True
                continue
            rebuilt.append(trainer)
        if not inserted:
            rebuilt.extend(early)
        current_document["trainers"] = rebuilt
        current_document["generation_contract"]["route_trainers"] = sum(
            trainer.get("class") in {"route", "optional_route"}
            for trainer in current_document["trainers"]
        )
        OUTPUT_PATH.write_text(
            json.dumps(current_document, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"updated {len(early)} route 1-3 trainers in {OUTPUT_PATH.relative_to(ROOT)}")
        return 0
    rendered = json.dumps(build_document(rules, routes), indent=2, ensure_ascii=False) + "\n"
    if args.write:
        OUTPUT_PATH.write_text(rendered, encoding="utf-8", newline="\n")
        print(f"wrote {OUTPUT_PATH.relative_to(ROOT)}")
        return 0
    current = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.exists() else ""
    if current != rendered:
        print(f"stale: run {Path(__file__).relative_to(ROOT)} --write", file=sys.stderr)
        return 1
    document = json.loads(rendered)
    print(
        f"ok: {document['generation_contract']['authored_boss_rosters']} boss rosters, "
        f"{document['generation_contract']['held_boss_slots']} held slot, "
        f"{document['generation_contract']['route_trainers']} route trainers"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

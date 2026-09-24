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
        "identity": trainer["id"],
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
        team = []
        ace_count = 0
        ace_species = None
        for member in slot["members"]:
            pokemon = deepcopy(member)
            pokemon["level"] = boss_level(slot["ace_level"], pokemon.pop("level_offset"))
            if pokemon.pop("ace", False):
                ace_count += 1
                ace_species = pokemon["species"]
            team.append(pokemon)
        if ace_count != 1:
            raise ValueError(f"{slot['id']}: expected exactly one ace, found {ace_count}")
        if max(member["level"] for member in team) != slot["ace_level"]:
            raise ValueError(f"{slot['id']}: ace level is not the team ceiling")
        source = {
            "id": slot["id"],
            "name": slot["name"],
            "ai_profile": slot["ai_profile"],
            "battle_format": slot.get("battle_format", "GEN_9_SINGLES"),
            "max_item_uses": slot.get("max_item_uses", 0),
            "bag": slot.get("bag", []),
            "team": team,
        }
        entry.update(
            {
                "ace_level": slot["ace_level"],
                "ace_species": ace_species,
                "ace_math_change": slot["ace_math_change"],
                "member_count": len(team),
                "team": deepcopy(team),
                "availability_contract": deepcopy(slot["availability_contract"]),
                "rct": make_rct(source, rules),
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
            vertex_index, point, measured_total = nearest_vertex(polyline, distance)
            expected = placement["expected_coordinate"]
            if [point["x"], point["z"]] != expected:
                raise ValueError(
                    f"{route_rule['id']} placement {index}: derived coordinate "
                    f"{[point['x'], point['z']]} != configured {expected}"
                )
            progress = distance / route["distance"]["computed_walked_blocks"]
            base_level = round(band["minimum"] + progress * (band["maximum"] - band["minimum"] - 1))
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
            trainer_id = f"route_{route_rule['order']:02d}_trainer_{index:02d}"
            source = {
                "id": trainer_id,
                "name": placement["name"],
                "ai_profile": placement.get("ai_profile", "route_standard"),
                "team": team,
            }
            generated.append(
                {
                    "id": trainer_id,
                    "display_name": placement["name"],
                    "class": "route",
                    "format": "GEN_9_SINGLES",
                    "team": deepcopy(team),
                    "route_id": route_rule["id"],
                    "route_order": route_rule["order"],
                    "trainer_order": index,
                    "archetype": placement["role"],
                    "lesson": placement["lesson"],
                    "placement": {
                        "status": "proposed",
                        "at_distance_blocks": distance,
                        "progress_fraction": round(progress, 4),
                        "polyline_vertex_index": vertex_index,
                        "x": point["x"],
                        "z": point["z"],
                        "sampled_y": point.get("y"),
                        "route_measured_blocks": measured_total,
                    },
                    "dialogue": {
                        "pre": f"dlg_{trainer_id}_pre",
                        "win": f"dlg_{trainer_id}_win",
                        "loss": f"dlg_{trainer_id}_loss",
                    },
                    "dialogue_text": deepcopy(placement.get("dialogue_text", {})),
                    "rct": make_rct(source, rules),
                }
            )
    return generated


def build_document(rules, routes):
    bosses = build_bosses(rules)
    route_trainers = build_route_trainers(rules, routes)
    return {
        "schema": "cobblers.trainers/1",
        "schema_version": 1,
        "generated_from": "docs/story/TRAINER_RULES.json",
        "generator": "docs/story/generate_trainers.py",
        "target": {
            "minecraft": "1.21.1",
            "cobblemon": "1.8.x",
            "rctmod": "0.19.0-beta",
            "rctapi": "0.16.0-beta",
        },
        "generation_contract": {
            "relative_level_cap": rules["difficulty"]["relative_level_cap"],
            "gym_ace_levels": rules["difficulty"]["gym_ace_levels"],
            "boss_slots": len(bosses),
            "authored_boss_rosters": sum(boss["status"] != "held" for boss in bosses),
            "held_boss_slots": sum(boss["status"] == "held" for boss in bosses),
            "route_trainers": len(route_trainers),
            "placement_status": "proposal_only",
            "dialogue_ids": "campaign metadata; RCT sidecars require a future compiler",
        },
        "trainers": bosses + route_trainers,
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
    args = parser.parse_args()

    rules = load_json(RULES_PATH)
    routes = load_json(ROUTES_PATH)
    if args.write_early or args.check_early:
        early = build_route_trainers(rules, routes, route_orders={1, 2, 3})
        current_document = load_json(OUTPUT_PATH)
        current_early = [
            trainer
            for trainer in current_document["trainers"]
            if trainer.get("class") == "route" and trainer.get("route_order") in {1, 2, 3}
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
            trainer.get("class") == "route" for trainer in current_document["trainers"]
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

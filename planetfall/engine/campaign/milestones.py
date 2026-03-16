"""Milestone system and end game triggers.

7 milestones trigger the end game. Each milestone has escalating
effects on the campaign world.
"""

from __future__ import annotations

import random

from planetfall.engine.dice import roll_d6, roll_d100, roll_nd6
from planetfall.engine.models import GameState, TurnEvent, TurnEventType, DiceRoll


# Effects applied when each milestone is achieved
MILESTONE_EFFECTS = {
    1: {
        "description": (
            "Colony gains attention. Enemy forces stir.\n"
            "- Roll 2 Character Events immediately\n"
            "- +1 Mission Data (check for breakthrough)\n"
            "- +1 Calamity Point (check for calamity)\n"
            "- A Tactical Enemy emerges"
        ),
        "character_events": 2,
        "mission_data": 1,
        "calamity_points": 1,
        "tactical_enemy_emerges": 1,
        # Placement: not in or adjacent to colony
        "enemy_placement": "not_colony_adjacent",
    },
    2: {
        "description": (
            "The colony's presence reshapes the region.\n"
            "- Roll an additional Colony Event\n"
            "- All enemies expand to an adjacent sector\n"
            "- +1 Ancient Sign (check for ancient site)\n"
            "- +1 Mission Data (check for breakthrough)\n"
            "- +2 Calamity Points (check for calamity)\n"
            "- A Tactical Enemy emerges"
        ),
        "colony_event": 1,
        "enemies_expand": True,
        "ancient_signs": 1,
        "mission_data": 1,
        "calamity_points": 2,
        "tactical_enemy_emerges": 1,
        # Placement: not adjacent to colony or other enemies
        "enemy_placement": "not_colony_or_enemy_adjacent",
    },
    3: {
        "description": (
            "A turning point. The colony grows in power and opposition.\n"
            "- +3 Story Points, +1 Colony Integrity\n"
            "- Roll an additional Enemy Activity\n"
            "- Tactical Enemies: Panic range -1, specialists +1 KP\n"
            "- +2 Mission Data (check for breakthrough)\n"
            "- +2 Calamity Points (check for calamity)\n"
            "- A Tactical Enemy emerges"
        ),
        "story_points": 3,
        "integrity": 1,
        "enemy_activity_roll": True,
        "enemy_panic_reduced": 1,
        "enemy_specialists_kp": 1,
        "mission_data": 2,
        "calamity_points": 2,
        "tactical_enemy_emerges": 1,
        "enemy_placement": "not_colony_or_enemy_adjacent",
    },
    4: {
        "description": (
            "The world shifts beneath you.\n"
            "- Erase and replace one battlefield condition\n"
            "- +1 Augmentation Point, +2 Grunts\n"
            "- +1 Mission Data (check for breakthrough)\n"
            "- +1 Calamity Point (check for calamity)\n"
            "- Begin tracking Slyn victories"
        ),
        "battlefield_condition_regenerate": True,
        "augmentation_points": 1,
        "grunts": 2,
        "mission_data": 1,
        "calamity_points": 1,
        "slyn_victory_tracking": True,
    },
    5: {
        "description": (
            "The final chapters begin to unfold.\n"
            "- +1 Augmentation Point\n"
            "- +1 Mission Data (check for breakthrough)\n"
            "- +2 Calamity Points (check for calamity)"
        ),
        "augmentation_points": 1,
        "mission_data": 1,
        "calamity_points": 2,
    },
    6: {
        "description": (
            "All forces converge. The end draws near.\n"
            "- Tactical encounters: +1 additional specialist\n"
            "- Roll Enemy Activity for every enemy each turn\n"
            "- +2 Mission Data (check for breakthrough)\n"
            "- +2 Calamity Points (check for calamity)"
        ),
        "enemy_extra_specialists": True,
        "enemy_activity_all": True,
        "mission_data": 2,
        "calamity_points": 2,
    },
    7: {
        "description": (
            "The End Game launches. The Summit will be called.\n"
            "- +2 Mission Data (check for breakthrough)\n"
            "- +1 Calamity Point (check for calamity)\n"
            "- If no Calamity occurs, no more Calamities for the campaign"
        ),
        "end_game": True,
        "mission_data": 2,
        "calamity_points": 1,
    },
}


# Lifeform evolution table (rolled each milestone)
LIFEFORM_EVOLUTION_TABLE = {
    (1, 10): {"name": "Enhanced Profile", "description": "CS +0->+1, Speed +1\", Strike +0->+1"},
    (11, 20): {"name": "Poison", "description": "Hits apply Poison marker; D6 per marker on activation, 6=casualty"},
    (21, 30): {"name": "Spines", "description": "Creatures lose brawl = take +0 Damage hit"},
    (31, 40): {"name": "Duplication", "description": "Start Enemy Phase: D6, on 6 duplicate random lifeform"},
    (41, 50): {"name": "Dramatic Transformations", "description": "Delete Unique Ability, roll new each battle"},
    (51, 60): {"name": "Summoning", "description": "Start Enemy Phase: D6, on 6 place Contact on table edge"},
    (61, 70): {"name": "Evasion", "description": "Fired upon: D6, on 6 evade (can't be hit rest of round)"},
    (71, 80): {"name": "Darts", "description": "End activation: dart at closest (Range 9\", hit on 6, Damage +0)"},
    (81, 90): {"name": "Bigger Leaders", "description": "4th lifeform = secondary leader +1 KP; 6th = pack leader +3 KP"},
    (91, 100): {"name": "Tougher Specimens", "description": "Place each: D6, on 5-6 gain +1 KP"},
}


def roll_lifeform_evolution() -> dict:
    """Roll on the lifeform evolution table."""
    roll = roll_d100("Lifeform Evolution")
    for (low, high), entry in LIFEFORM_EVOLUTION_TABLE.items():
        if low <= roll.total <= high:
            return entry
    return {"name": "Unknown", "description": ""}


def _get_adjacent_sector_ids(state: GameState, sector_id: int) -> set[int]:
    """Get sector IDs adjacent to a given sector on the 6-column grid map."""
    cols = 6
    total = len(state.campaign_map.sectors)
    row, col = divmod(sector_id, cols)
    adjacent = set()
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            nr, nc = row + dr, col + dc
            nid = nr * cols + nc
            if 0 <= nr < (total + cols - 1) // cols and 0 <= nc < cols and 0 <= nid < total:
                adjacent.add(nid)
    return adjacent


def _valid_sectors_for_enemy(
    state: GameState, placement_rule: str,
) -> list[int]:
    """Get valid sector IDs for tactical enemy placement per rules constraints."""
    colony_id = state.campaign_map.colony_sector_id
    all_ids = {s.sector_id for s in state.campaign_map.sectors}

    # Always exclude colony sector
    excluded = {colony_id}

    # Exclude sectors adjacent to colony
    excluded |= _get_adjacent_sector_ids(state, colony_id)

    if placement_rule == "not_colony_or_enemy_adjacent":
        # Also exclude sectors held by or adjacent to other tactical enemies
        for te in state.enemies.tactical_enemies:
            for sid in te.sectors:
                excluded.add(sid)
                excluded |= _get_adjacent_sector_ids(state, sid)

    return [sid for sid in all_ids if sid not in excluded]


def apply_milestone(state: GameState, milestone_num: int) -> list[TurnEvent]:
    """Apply the effects of reaching a milestone.

    Called when milestones_completed reaches a new threshold.
    """
    if milestone_num not in MILESTONE_EFFECTS:
        return []

    effects = MILESTONE_EFFECTS[milestone_num]
    # Common effects applied every milestone are appended to the description
    full_desc = (
        f"{effects['description']}\n"
        f"- Roll Lifeform Evolution\n"
        f"- +1 Replacement available for roster"
    )
    events = [TurnEvent(
        step=0, event_type=TurnEventType.NARRATIVE,
        description=full_desc,
        state_changes={"milestone": milestone_num},
    )]

    # --- Resource effects ---
    if "story_points" in effects:
        state.colony.resources.story_points += effects["story_points"]
        events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                description=f"+{effects['story_points']} Story Points"))
    if "integrity" in effects:
        state.colony.integrity += effects["integrity"]
        events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                description=f"+{effects['integrity']} Colony Integrity"))
    if "augmentation_points" in effects:
        state.colony.resources.augmentation_points += effects["augmentation_points"]
        events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                description=f"+{effects['augmentation_points']} Augmentation Points"))
    if "grunts" in effects:
        state.grunts.count += effects["grunts"]
        events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                description=f"+{effects['grunts']} grunts added to roster"))
    if "mission_data" in effects:
        state.campaign.mission_data_count += effects["mission_data"]
        events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                description=f"+{effects['mission_data']} Mission Data (total: {state.campaign.mission_data_count})"))
    if "calamity_points" in effects:
        state.colony.resources.calamity_points += effects["calamity_points"]
        events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                description=f"+{effects['calamity_points']} Calamity Points (total: {state.colony.resources.calamity_points})"))
    if "ancient_signs" in effects:
        state.campaign.ancient_signs_count += effects["ancient_signs"]
        events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                description=f"+{effects['ancient_signs']} Ancient Sign(s)"))
        from planetfall.engine.campaign.ancient_signs import check_ancient_signs
        events.extend(check_ancient_signs(state, signs_obtained=effects["ancient_signs"]))

    # --- Replacement bonus (every milestone) ---
    state.tracking.pending_replacements += 1
    events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                            description="You may recruit 1 additional replacement for your roster."))

    # --- Character events (Milestone 1) ---
    if "character_events" in effects:
        from planetfall.engine.steps.step17_character_event import execute as run_char_event
        count = effects["character_events"]
        for _ in range(count):
            char_events = run_char_event(state)
            events.extend(char_events)
        events.append(TurnEvent(
            step=0, event_type=TurnEventType.CHARACTER_EVENT,
            description=f"Milestone triggered {count} character event(s).",
        ))

    # --- Colony event (Milestone 2) ---
    if effects.get("colony_event"):
        events.append(TurnEvent(
            step=0, event_type=TurnEventType.COLONY_EVENT,
            description="Milestone triggers an additional Colony Event roll.",
        ))

    # --- Enemies expand (Milestone 2) ---
    if effects.get("enemies_expand"):
        for enemy in state.enemies.tactical_enemies:
            if enemy.defeated or not enemy.sectors:
                continue
            # Expand to a random adjacent sector
            adj_candidates = set()
            for sid in enemy.sectors:
                adj_candidates |= _get_adjacent_sector_ids(state, sid)
            # Exclude colony, already-held sectors
            colony_id = state.campaign_map.colony_sector_id
            adj_candidates -= {colony_id}
            adj_candidates -= set(enemy.sectors)
            total_sectors = len(state.campaign_map.sectors)
            adj_candidates = {s for s in adj_candidates if 0 <= s < total_sectors}
            if adj_candidates:
                new_sector = random.choice(list(adj_candidates))
                enemy.sectors.append(new_sector)
                events.append(TurnEvent(
                    step=0, event_type=TurnEventType.ENEMY_ACTIVITY,
                    description=f"{enemy.name} expands to sector {new_sector}!",
                    state_changes={"enemy_expand": enemy.name, "sector": new_sector},
                ))

    # --- Enemy activity roll (Milestone 3) ---
    if effects.get("enemy_activity_roll"):
        events.append(TurnEvent(
            step=0, event_type=TurnEventType.ENEMY_ACTIVITY,
            description="Milestone triggers an additional Enemy Activity roll.",
        ))

    # --- Enemy panic reduction (Milestone 3) ---
    if effects.get("enemy_panic_reduced"):
        reduction = effects["enemy_panic_reduced"]
        state.tracking.enemy_panic_reduction += reduction
        for enemy in state.enemies.tactical_enemies:
            if not enemy.defeated:
                events.append(TurnEvent(
                    step=0, event_type=TurnEventType.ENEMY_ACTIVITY,
                    description=f"Enemy panic: {enemy.name} panic range reduced by {reduction}.",
                    state_changes={"enemy_panic_reduced": reduction, "enemy": enemy.name},
                ))

    # --- Specialist KP bonus (Milestone 3) ---
    if effects.get("enemy_specialists_kp"):
        kp_bonus = effects["enemy_specialists_kp"]
        state.tracking.enemy_specialist_kp_bonus += kp_bonus
        events.append(TurnEvent(
            step=0, event_type=TurnEventType.ENEMY_ACTIVITY,
            description=f"All tactical specialists now receive +{state.tracking.enemy_specialist_kp_bonus} KP.",
        ))

    # --- Battlefield condition regenerate (Milestone 4) ---
    if effects.get("battlefield_condition_regenerate"):
        conditions = list(state.tracking.battlefield_conditions)
        filled = [i for i, c in enumerate(conditions) if c is not None]
        if filled:
            slot = random.choice(filled)
            from planetfall.engine.tables.battlefield_conditions import _roll_generation_table, _condition_to_dict
            old_name = conditions[slot].name if hasattr(conditions[slot], 'name') else (conditions[slot].get('name', '?') if isinstance(conditions[slot], dict) else '?')
            new_cond = _roll_generation_table()
            conditions[slot] = _condition_to_dict(new_cond)
            state.tracking.battlefield_conditions = conditions
            events.append(TurnEvent(
                step=0, event_type=TurnEventType.NARRATIVE,
                description=f"Battlefield condition '{old_name}' erased and replaced with '{new_cond.name}'.",
            ))

    # --- Slyn victory tracking (Milestone 4) ---
    if effects.get("slyn_victory_tracking"):
        state.tracking.slyn_victory_tracking_active = True
        events.append(TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=(
                "Slyn victory tracking begins. Each Slyn defeat: roll 2D6, "
                "if ≤ tracked victories the Slyn leave permanently."
            ),
        ))

    # --- Enemy extra specialists (Milestone 6) ---
    if effects.get("enemy_extra_specialists"):
        state.tracking.enemy_extra_specialists = True
        events.append(TurnEvent(
            step=0, event_type=TurnEventType.ENEMY_ACTIVITY,
            description="All tactical enemy encounters now include 1 additional specialist figure.",
        ))

    # --- Enemy activity all (Milestone 6) ---
    if effects.get("enemy_activity_all"):
        state.tracking.enemy_activity_all_enemies = True
        events.append(TurnEvent(
            step=0, event_type=TurnEventType.ENEMY_ACTIVITY,
            description="From now on, roll Enemy Activity for every enemy on the map each turn.",
        ))

    # --- Tactical enemy emerges ---
    if effects.get("tactical_enemy_emerges"):
        from planetfall.engine.tables.tactical_enemy_gen import (
            TACTICAL_ENEMY_TABLE, TACTICAL_ENEMY_PROFILES,
        )
        from planetfall.engine.models import TacticalEnemy, TacticalEnemyProfile
        _, entry = TACTICAL_ENEMY_TABLE.roll_on_table("Tactical enemy emergence")
        enemy_type_id = entry.result_id
        profile = TACTICAL_ENEMY_PROFILES[enemy_type_id]
        placement_rule = effects.get("enemy_placement", "not_colony_adjacent")
        available = _valid_sectors_for_enemy(state, placement_rule)
        enemy_sectors = random.sample(available, min(1, len(available))) if available else []
        from planetfall.engine.tables.tactical_enemy_gen import generate_enemy_faction_name
        faction_name = generate_enemy_faction_name(enemy_type_id, state)
        new_enemy = TacticalEnemy(
            name=faction_name,
            enemy_type=enemy_type_id,
            sectors=enemy_sectors,
            profile=TacticalEnemyProfile(
                speed=profile.speed,
                combat_skill=profile.combat_skill,
                toughness=profile.toughness,
                panic_range=profile.panic_range,
                armor_save=profile.armor_save,
                special_rules=list(profile.special_rules),
                number_dice=profile.number_dice,
            ),
        )
        state.enemies.tactical_enemies.append(new_enemy)
        from planetfall.engine.utils import sync_enemy_sectors
        sync_enemy_sectors(state)
        sector_str = ", ".join(str(s) for s in enemy_sectors) if enemy_sectors else "unknown"
        events.append(TurnEvent(
            step=0, event_type=TurnEventType.ENEMY_ACTIVITY,
            description=(
                f"TACTICAL ENEMY EMERGES: {faction_name} ({profile.name}) detected in sector {sector_str}!"
            ),
            state_changes={"tactical_enemy": enemy_type_id, "sectors": enemy_sectors},
        ))

    # --- Lifeform evolution (every milestone) ---
    evolution = roll_lifeform_evolution()
    state.tracking.lifeform_evolutions.append(evolution["name"])
    events.append(TurnEvent(
        step=0, event_type=TurnEventType.NARRATIVE,
        description=f"Lifeform Evolution: {evolution['name']} — {evolution['description']}",
    ))

    # --- Mission data breakthrough check ---
    from planetfall.engine.campaign.ancient_signs import check_mission_data_breakthrough
    md_events = check_mission_data_breakthrough(state)
    events.extend(md_events)

    # --- Calamity check ---
    from planetfall.engine.campaign.calamities import check_calamity
    calamity_events = check_calamity(state)
    events.extend(calamity_events)

    # --- End game trigger ---
    if effects.get("end_game"):
        state.campaign.end_game_triggered = True
        events.append(TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description="THE END GAME HAS BEEN TRIGGERED! The Summit will be called.",
        ))

    return events


def check_and_apply_milestones(state: GameState, previous_count: int) -> list[TurnEvent]:
    """Check if new milestones were achieved and apply their effects.

    Args:
        previous_count: Milestone count before the current action.
    """
    events = []
    current = state.campaign.milestones_completed
    for m in range(previous_count + 1, current + 1):
        events.extend(apply_milestone(state, m))
    return events


# --- End Game: The Summit ---

SUMMIT_OPINIONS = {
    1: "Independence",
    2: "Ascension",
    3: "Loyalty",
    4: "Isolation",
    5: "No opinion",
    6: "No opinion",
}

SUMMIT_COSTS = {
    "Independence": {"bp": 15, "rp": 5},
    "Ascension": {"bp": 5, "rp": 15},
    "Loyalty": {"bp": 10, "rp": 5},
    "Isolation": {"bp": 5, "rp": 10},
}

# Colony security: how many tactical enemies must be defeated per path
SECURITY_REQUIREMENTS = {
    "Independence": 1,
    "Ascension": 1,
    "Loyalty": 2,
    "Isolation": 1,
}


def run_summit_votes(state: GameState) -> dict[str, list[str]]:
    """Roll summit votes for each character + general population.

    Returns dict mapping opinion -> list of voter names.
    """
    votes: dict[str, list[str]] = {
        "Independence": [], "Ascension": [], "Loyalty": [],
        "Isolation": [], "No opinion": [],
    }

    # Each character votes
    for char in state.characters:
        roll = roll_d6(f"Summit vote: {char.name}")
        opinion = SUMMIT_OPINIONS[roll.total]
        votes[opinion].append(char.name)

    # General population votes
    roll = roll_d6("Summit vote: Population")
    opinion = SUMMIT_OPINIONS[roll.total]
    votes[opinion].append("Population")

    return votes


def get_viable_paths(votes: dict[str, list[str]]) -> list[str]:
    """Get summit paths with at least 1 supporter."""
    viable = []
    for path in ("Independence", "Ascension", "Loyalty", "Isolation"):
        voters = votes.get(path, [])
        if len(voters) >= 1:
            viable.append(path)
    return viable


def count_defeated_enemies(state: GameState) -> int:
    """Count tactical enemies whose strongpoints have been destroyed."""
    return sum(1 for e in state.enemies.tactical_enemies if e.defeated)


def check_colony_security(state: GameState, path: str) -> tuple[bool, int, int]:
    """Check colony security requirement for a summit path.

    Returns (is_met, defeated_count, required_count).
    """
    required = SECURITY_REQUIREMENTS.get(path, 1)
    defeated = count_defeated_enemies(state)
    return defeated >= required, defeated, required


# --- Summit Path Descriptions ---

SUMMIT_PATH_DESCRIPTIONS = {
    "Independence": (
        "With the colony set on a path of independence, you order the "
        "large-scale construction of defenses and issue a proclamation "
        "that the world is now independent."
    ),
    "Ascension": (
        "Strange machines are built all over the colony as engineers and "
        "scientists push themselves to align the moment of ascension "
        "with optimal planetary conditions."
    ),
    "Loyalty": (
        "You have completed all assigned tasks. The only step left is to "
        "prepare the colony for formal inclusion as a registered Unity "
        "Main World."
    ),
    "Isolation": (
        "Your scouts have selected a suitable location for the new colony. "
        "Your characters set out on a lonely march, attempting to become "
        "a tribe of nomads living in harmony with the world."
    ),
}


def execute_summit(
    state: GameState,
    chosen_path: str,
) -> list[TurnEvent]:
    """Execute The Summit — the endgame sequence.

    1. Check colony security (defeated tactical enemies).
    2. Check and pay resource costs (with breakthrough discounts).
    3. Resolve the chosen path.

    Args:
        chosen_path: One of Independence, Ascension, Loyalty, Isolation.
    """
    events: list[TurnEvent] = []

    # Validate path
    if chosen_path not in SUMMIT_COSTS:
        events.append(TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=f"Invalid summit path: {chosen_path}",
        ))
        return events

    # Colony security check
    security_met, defeated, required = check_colony_security(state, chosen_path)
    if not security_met:
        events.append(TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=(
                f"Colony security not met for {chosen_path}: "
                f"need {required} defeated tactical enemy(ies), have {defeated}. "
                f"Defeat enemy strongpoints before proceeding."
            ),
        ))
        return events

    # Calculate costs (with breakthrough discounts for Loyalty)
    costs = dict(SUMMIT_COSTS[chosen_path])
    bp_cost = costs["bp"]
    rp_cost = costs["rp"]
    breakthroughs = set(state.tracking.breakthroughs)

    if chosen_path == "Loyalty":
        if "ancient_factory" in breakthroughs:
            bp_cost = 5
        if "terraforming" in breakthroughs:
            rp_cost = 0
        if "ancient_colony" in breakthroughs:
            bp_cost = min(bp_cost, 6)
            rp_cost = min(rp_cost, 2)

    can_afford = (
        state.colony.resources.build_points >= bp_cost
        and state.colony.resources.research_points >= rp_cost
    )

    if not can_afford:
        events.append(TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=(
                f"Cannot afford {chosen_path} path "
                f"(need {bp_cost} BP + {rp_cost} RP, "
                f"have {state.colony.resources.build_points} BP + "
                f"{state.colony.resources.research_points} RP)."
            ),
        ))
        return events

    # Pay costs
    state.colony.resources.build_points -= bp_cost
    state.colony.resources.research_points -= rp_cost

    events.append(TurnEvent(
        step=0, event_type=TurnEventType.NARRATIVE,
        description=(
            f"THE SUMMIT: Path chosen — {chosen_path}. "
            f"Paid {bp_cost} BP and {rp_cost} RP."
        ),
        state_changes={"summit_path": chosen_path},
    ))

    path_desc = SUMMIT_PATH_DESCRIPTIONS.get(chosen_path, "")
    events.append(TurnEvent(
        step=0, event_type=TurnEventType.NARRATIVE,
        description=path_desc,
    ))

    # Resolve the path
    if chosen_path == "Independence":
        events.extend(_resolve_independence(state, breakthroughs))
    elif chosen_path == "Ascension":
        events.extend(_resolve_ascension(state, breakthroughs))
    elif chosen_path == "Loyalty":
        events.extend(_resolve_loyalty(state))
    elif chosen_path == "Isolation":
        events.extend(_resolve_isolation(state, breakthroughs))

    # Mark campaign as complete
    state.campaign.campaign_story_track.append(f"SUMMIT: {chosen_path}")
    state.flags.summit_path = chosen_path
    state.flags.campaign_complete = True

    return events


# --- Path Resolution ---

UNITY_RESPONSE_TABLE = {
    2: "total_war",
    3: "war", 4: "war", 5: "war", 6: "war", 7: "war",
    8: "negotiations", 9: "negotiations", 10: "negotiations",
    11: "recognized", 12: "recognized",
}


def _resolve_independence(
    state: GameState, breakthroughs: set[str],
) -> list[TurnEvent]:
    """Resolve Independence path: 2D6 Unity Response table."""
    events: list[TurnEvent] = []
    roll = roll_nd6(2, "Unity Response")
    total = roll.total

    # Defense Network breakthrough: +1 unless doubles
    has_defense_network = "defense_network" in breakthroughs
    is_doubles = len(roll.values) == 2 and roll.values[0] == roll.values[1]
    if has_defense_network and not is_doubles:
        total += 1
        events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                description="Defense Network breakthrough: +1 to Unity Response roll."))

    result = UNITY_RESPONSE_TABLE.get(min(total, 12), "war")

    dice = [DiceRoll(dice_type="2d6", values=roll.values, total=roll.total, label="Unity Response")]

    if result == "total_war":
        if "artificial_construction" in breakthroughs:
            events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                    description=(
                                        f"Unity Response: {total} — Total War! "
                                        f"But Artificial Construction breakthrough converts to War instead."
                                    ), dice_rolls=dice))
            result = "war"
        else:
            events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                    description=(
                                        f"Unity Response: {total} — TOTAL WAR. "
                                        f"Unity obliterates the colony. Campaign ends in defeat."
                                    ), dice_rolls=dice))
            state.flags.campaign_complete = True
            return events

    if result == "war":
        events.extend(_resolve_independence_war(state, breakthroughs, dice))
    elif result == "negotiations":
        events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                description=(
                                    f"Unity Response: {total} — Negotiations drag on. "
                                    f"The outcome remains uncertain but the colony survives."
                                ), dice_rolls=dice))
        # Re-roll: 8=War, 10+=Recognized
        reroll = roll_nd6(2, "Unity Negotiations")
        reroll_total = reroll.total
        if has_defense_network and reroll.values[0] != reroll.values[1]:
            reroll_total += 1
        if reroll_total <= 8:
            events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                    description=f"Negotiations break down (rolled {reroll_total}). War begins."))
            events.extend(_resolve_independence_war(state, breakthroughs, []))
        elif reroll_total >= 10:
            events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                    description=f"Negotiations succeed (rolled {reroll_total})! Recognized status granted."))
        else:
            events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                    description=f"Negotiations continue (rolled {reroll_total}). The colony perseveres."))
    elif result == "recognized":
        events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                description=(
                                    f"Unity Response: {total} — RECOGNIZED STATUS! "
                                    f"Unity grants semi-autonomous status. Your colony becomes "
                                    f"an independent, Unity-Allied world. Congratulations!"
                                ), dice_rolls=dice))

    return events


def _resolve_independence_war(
    state: GameState, breakthroughs: set[str], initial_dice: list[DiceRoll],
) -> list[TurnEvent]:
    """Resolve the War sub-mechanic for Independence path.

    Opposed D6 rolls. Colony wins on tie or higher. War Fatigue accumulates.
    """
    events: list[TurnEvent] = []
    events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                            description="WAR! Unity responds with military force."))

    war_fatigue_colony = 0
    war_fatigue_unity = 0
    if "warzone" in breakthroughs:
        war_fatigue_unity += 1
        events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                description="Warzone breakthrough: Unity starts with 1 War Fatigue."))

    max_rounds = 10
    for rnd in range(1, max_rounds + 1):
        colony_roll = roll_d6(f"War round {rnd}: Colony")
        unity_roll = roll_d6(f"War round {rnd}: Unity")

        c_total = colony_roll.total + war_fatigue_unity  # Unity fatigue helps colony
        u_total = unity_roll.total + war_fatigue_colony  # Colony fatigue helps unity

        if colony_roll.total == unity_roll.total:
            # Draw — both gain fatigue
            war_fatigue_colony += 1
            war_fatigue_unity += 1
            events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                    description=(
                                        f"War round {rnd}: Draw ({colony_roll.total} vs {unity_roll.total}). "
                                        f"Both sides gain War Fatigue."
                                    )))
        elif c_total >= u_total:
            events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                    description=(
                                        f"War round {rnd}: Colony wins! ({colony_roll.total}+{war_fatigue_unity} "
                                        f"vs {unity_roll.total}+{war_fatigue_colony}). "
                                        f"Independence secured!"
                                    )))
            return events
        else:
            war_fatigue_colony += 1
            events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                    description=(
                                        f"War round {rnd}: Unity pushes back "
                                        f"({colony_roll.total}+{war_fatigue_unity} vs "
                                        f"{unity_roll.total}+{war_fatigue_colony}). "
                                        f"Colony gains War Fatigue ({war_fatigue_colony})."
                                    )))
            # Colony loses when fatigue reaches 5
            if war_fatigue_colony >= 5:
                events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                        description="Colony War Fatigue reaches 5. The war is lost."))
                return events

    events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                            description="The war grinds to a stalemate. Independence is maintained, barely."))
    return events


ASCENSION_FATE = {
    1: "Your colonists become a new psionic sub-species.",
    2: "Your colonists join into a single hivemind.",
    3: "Your colonists join into a single hivemind.",
    4: "Your colonists ascend to become beings of pure thought.",
    5: "Your colonists leave for a parallel dimension shaped by thoughts.",
    6: "Your colonists leave for a parallel dimension shaped by thoughts.",
}


def _resolve_ascension(
    state: GameState, breakthroughs: set[str],
) -> list[TurnEvent]:
    """Resolve Ascension path: each character rolls D6 for ascension."""
    events: list[TurnEvent] = []
    ascension_energy = 0

    # Moved in Time/Space: one character auto-succeeds
    auto_success_char = None
    if "moved_in_time_or_space" in breakthroughs and state.characters:
        auto_success_char = state.characters[0].name
        events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                description=f"Moved in Time/Space breakthrough: {auto_success_char} automatically rolls 6."))

    for char in state.characters:
        if char.name == auto_success_char:
            roll_val = 6
        else:
            roll_result = roll_d6(f"Ascension: {char.name}")
            roll_val = roll_result.total

        if roll_val == 1:
            events.append(TurnEvent(step=0, event_type=TurnEventType.CHARACTER_EVENT,
                                    description=f"{char.name} perishes in the ascension process (rolled {roll_val})."))
        elif roll_val <= 4:
            events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                    description=f"{char.name} undergoes ascension successfully (rolled {roll_val})."))
        else:
            ascension_energy += 1
            events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                    description=f"{char.name} ascends and generates 1 ascension energy (rolled {roll_val})!"))

    # Signs of Genetic Modification: +2 energy
    if "signs_of_genetic_modification" in breakthroughs:
        ascension_energy += 2
        events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                description="Signs of Genetic Modification breakthrough: +2 ascension energy."))

    events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                            description=f"Total ascension energy: {ascension_energy}"))

    if ascension_energy > 0:
        fate_roll = roll_d6("Ascension fate")
        if fate_roll.total <= ascension_energy:
            fate_desc = ASCENSION_FATE.get(fate_roll.total, "Your colonists ascend to a new state of being.")
            events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                    description=f"Ascension fate (rolled {fate_roll.total} ≤ {ascension_energy}): {fate_desc}"))
        else:
            events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                    description=(
                                        f"Ascension fate: rolled {fate_roll.total} > {ascension_energy}. "
                                        f"Your colonists are now a distinct sub-species, "
                                        f"perfectly adapted to this world."
                                    )))
    else:
        events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                description="No ascension energy generated. Your colonists adapt naturally to this world."))

    return events


LOYALTY_FUTURE = {
    1: "Trading post",
    2: "Staging ground for continued colonization missions",
    3: "Resource extraction",
    4: "Research station",
    5: "Unity naval base",
    6: "Major habitation",
}

LOYALTY_CHARACTER_FATE = {
    1: "Retires in civilian life",
    2: "Retires if Disloyal, otherwise assigned to a new expedition",
    3: "Assigned to a new expedition",
    4: "Assigned to Unity field agent or operative role",
    5: "Gets lucrative job with megacorporation",
    6: "A future as an independent adventurer",
}


def _resolve_loyalty(state: GameState) -> list[TurnEvent]:
    """Resolve Loyalty path: colony future + character fates."""
    events: list[TurnEvent] = []

    # Colony future
    future_roll = roll_nd6(2, "Colony future")
    # Pick either die result
    f1 = LOYALTY_FUTURE.get(future_roll.values[0], "Major habitation")
    f2 = LOYALTY_FUTURE.get(future_roll.values[1], "Major habitation")
    events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                            description=(
                                f"Colony future: rolled {future_roll.values[0]} and {future_roll.values[1]}. "
                                f"Options: '{f1}' or '{f2}'."
                            ),
                            dice_rolls=[DiceRoll(dice_type="2d6", values=future_roll.values,
                                                 total=future_roll.total, label="Colony Future")]))

    # Character fates
    for char in state.characters:
        fate_roll = roll_d6(f"Fate: {char.name}")
        fate = LOYALTY_CHARACTER_FATE.get(fate_roll.total, "Unknown future")
        events.append(TurnEvent(step=0, event_type=TurnEventType.CHARACTER_EVENT,
                                description=f"{char.name}: {fate} (rolled {fate_roll.total})"))

    events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                            description="The colony is formally registered as a Unity Main World. Congratulations!"))

    return events


def _resolve_isolation(
    state: GameState, breakthroughs: set[str],
) -> list[TurnEvent]:
    """Resolve Isolation path: Nomad Struggles 2D6 repeated rolls."""
    events: list[TurnEvent] = []
    wisdom = 0
    hardship_chars: set[str] = set()
    dead_chars: set[str] = set()

    semi_living = "semi_living_organism" in breakthroughs
    psionic_manip = "psionic_manipulation" in breakthroughs
    hardship_ignores = 2 if semi_living else 0
    first_death_wisdom = psionic_manip

    alive_chars = [c.name for c in state.characters]
    max_rolls = 20  # Safety limit

    for rnd in range(1, max_rolls + 1):
        if not alive_chars or wisdom >= 3:
            break

        roll = roll_nd6(2, f"Nomad Struggles round {rnd}")
        total = roll.total

        if total <= 2:
            # Character death
            victim = random.choice(alive_chars)
            alive_chars.remove(victim)
            dead_chars.add(victim)
            death_desc = f"Round {rnd}: rolled {total}. {victim} falls, never to stand again."
            if first_death_wisdom:
                wisdom += 1
                first_death_wisdom = False
                death_desc += f" Psionic Manipulation: +1 Wisdom (now {wisdom})."
            events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                    description=death_desc,
                                    dice_rolls=[DiceRoll(dice_type="2d6", values=roll.values,
                                                         total=roll.total, label="Nomad Struggles")]))
        elif total <= 7:
            # Hardship
            victim = random.choice(alive_chars)
            if hardship_ignores > 0:
                hardship_ignores -= 1
                events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                        description=(
                                            f"Round {rnd}: rolled {total}. {victim} faces hardship, "
                                            f"but Semi-Living Organism breakthrough negates it."
                                        )))
            elif victim in hardship_chars:
                # Second hardship = death
                alive_chars.remove(victim)
                dead_chars.add(victim)
                events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                        description=f"Round {rnd}: rolled {total}. {victim} suffers a second hardship and dies."))
            else:
                hardship_chars.add(victim)
                events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                        description=f"Round {rnd}: rolled {total}. {victim} suffers hardship."))
        else:
            # Wisdom
            wisdom += 1
            events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                    description=(
                                        f"Round {rnd}: rolled {total}. A vision reveals how to "
                                        f"attain oneness with nature. Wisdom: {wisdom}/3."
                                    ),
                                    dice_rolls=[DiceRoll(dice_type="2d6", values=roll.values,
                                                         total=roll.total, label="Nomad Struggles")]))

    if wisdom >= 3:
        events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                description="3 Wisdom attained! Your colonists have founded a new tribe. Congratulations!"))
    elif not alive_chars:
        events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                description="All characters have perished on the march. The colony's story ends here."))
    else:
        events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                description=f"The march continues. Wisdom: {wisdom}/3. {len(alive_chars)} survivors remain."))

    return events


def calculate_campaign_score(state: GameState) -> dict:
    """Calculate the final campaign score.

    Scoring:
    - +2 per milestone completed
    - +1 per character still alive
    - +1 per 10 colony morale (floored)
    - +1 per remaining colony integrity point
    - +1 per tactical enemy fully defeated (enemy_info >= 3)
    - +3 if Slyn driven off
    - +2 if summit path was affordable (campaign_complete)
    - -1 per calamity point remaining
    - -2 per character death during campaign
    """
    score = 0
    breakdown: list[str] = []

    # Milestones
    ms = state.campaign.milestones_completed
    ms_pts = ms * 2
    score += ms_pts
    breakdown.append(f"Milestones ({ms} x 2): +{ms_pts}")

    # Surviving characters
    alive = len(state.characters)
    score += alive
    breakdown.append(f"Surviving characters: +{alive}")

    # Morale
    morale_pts = max(0, state.colony.morale // 10)
    score += morale_pts
    breakdown.append(f"Colony morale ({state.colony.morale} / 10): +{morale_pts}")

    # Integrity
    integrity_pts = max(0, state.colony.integrity)
    score += integrity_pts
    breakdown.append(f"Colony integrity: +{integrity_pts}")

    # Defeated enemies
    defeated = sum(
        1 for e in state.enemies.tactical_enemies
        if e.enemy_info_count >= 3
    )
    score += defeated
    breakdown.append(f"Defeated tactical enemies: +{defeated}")

    # Slyn
    if not state.enemies.slyn.active and state.enemies.slyn.encounters > 0:
        score += 3
        breakdown.append("Slyn driven off: +3")

    # Summit completed
    if state.flags.campaign_complete:
        score += 2
        breakdown.append("Summit completed: +2")

    # Calamity penalty
    cal = state.colony.resources.calamity_points
    if cal > 0:
        score -= cal
        breakdown.append(f"Calamity points remaining: -{cal}")

    deaths = state.flags.total_character_deaths
    if deaths > 0:
        death_pen = deaths * 2
        score -= death_pen
        breakdown.append(f"Character deaths ({deaths} x 2): -{death_pen}")

    # Rating
    if score >= 30:
        rating = "Legendary"
    elif score >= 24:
        rating = "Outstanding"
    elif score >= 18:
        rating = "Commendable"
    elif score >= 12:
        rating = "Adequate"
    elif score >= 6:
        rating = "Struggling"
    else:
        rating = "Catastrophic"

    return {
        "score": score,
        "rating": rating,
        "breakdown": breakdown,
        "turns_played": state.current_turn - 1,
        "summit_path": state.flags.summit_path or "None",
    }

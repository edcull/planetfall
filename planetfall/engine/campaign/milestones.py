"""Milestone system and end game triggers.

7 milestones trigger the end game. Each milestone has escalating
effects on the campaign world.
"""

from __future__ import annotations

from planetfall.engine.dice import roll_d6, roll_d100
from planetfall.engine.models import GameState, TurnEvent, TurnEventType, DiceRoll


# Effects applied when each milestone is achieved
MILESTONE_EFFECTS = {
    1: {
        "description": "Colony gains attention. Enemy forces stir.",
        "character_events": 2,
        "mission_data": 1,
        "calamity_points": 1,
        "tactical_enemy_emerges": 1,
    },
    2: {
        "description": "The colony's presence reshapes the region.",
        "colony_event": 1,
        "enemies_expand": True,
        "ancient_signs": 1,
        "mission_data": 1,
        "calamity_points": 2,
        "tactical_enemy_emerges": 1,
    },
    3: {
        "description": "A turning point. The colony grows in power and opposition.",
        "story_points": 3,
        "integrity": 1,
        "grunts": 2,
        "enemy_panic_reduced": 1,
        "enemy_specialists_kp": 1,
        "mission_data": 2,
        "calamity_points": 2,
        "tactical_enemy_emerges": 1,
    },
    4: {
        "description": "The world shifts beneath you.",
        "augmentation_points": 1,
        "mission_data": 1,
        "calamity_points": 1,
        "slyn_check": True,
    },
    5: {
        "description": "The final chapters begin to unfold.",
        "augmentation_points": 1,
        "savvy_demands": True,
        "mission_data": 1,
        "calamity_points": 2,
    },
    6: {
        "description": "All forces converge. The end draws near.",
        "enemy_extra_specialists": True,
        "enemy_activity_all": True,
        "mission_data": 2,
        "calamity_points": 2,
    },
    7: {
        "description": "The Summit is called. The colony's fate will be decided.",
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


def apply_milestone(state: GameState, milestone_num: int) -> list[TurnEvent]:
    """Apply the effects of reaching a milestone.

    Called when milestones_completed reaches a new threshold.
    """
    if milestone_num not in MILESTONE_EFFECTS:
        return []

    effects = MILESTONE_EFFECTS[milestone_num]
    events = [TurnEvent(
        step=0, event_type=TurnEventType.NARRATIVE,
        description=f"=== MILESTONE {milestone_num} === {effects['description']}",
        state_changes={"milestone": milestone_num},
    )]

    # Apply resource effects
    if "story_points" in effects:
        state.colony.resources.story_points += effects["story_points"]
        events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                description=f"+{effects['story_points']} Story Points"))
    if "integrity" in effects:
        state.colony.integrity += effects["integrity"]
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
    if "calamity_points" in effects:
        state.colony.resources.calamity_points += effects["calamity_points"]
    if "ancient_signs" in effects:
        state.campaign.ancient_signs_count += effects["ancient_signs"]

    # Character events (Milestone 1: roll TWO character events)
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

    # Enemy panic reduction (Milestone 3: reduce enemy panic by 1)
    if effects.get("enemy_panic_reduced"):
        reduction = effects["enemy_panic_reduced"]
        for enemy in state.enemies.tactical_enemies:
            if not enemy.defeated:
                # Reduce enemy info needed (enemies become easier to defeat)
                events.append(TurnEvent(
                    step=0, event_type=TurnEventType.ENEMY_ACTIVITY,
                    description=f"Enemy panic: {enemy.name} threat reduced by {reduction}.",
                    state_changes={"enemy_panic_reduced": reduction, "enemy": enemy.name},
                ))

    # Specialist KP bonus (Milestone 3: enemy specialists gain +1 KP)
    if effects.get("enemy_specialists_kp"):
        kp_bonus = effects["enemy_specialists_kp"]
        events.append(TurnEvent(
            step=0, event_type=TurnEventType.ENEMY_ACTIVITY,
            description=f"Enemy specialists gain +{kp_bonus} KP from this point forward.",
            state_changes={"enemy_specialists_kp_bonus": kp_bonus},
        ))

    # Savvy demands (Milestone 5: roll 1D6+Savvy per char; 5+ = demands satisfied)
    if effects.get("savvy_demands"):
        events.append(TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description="Colony demands! Each character must roll 1D6+Savvy (5+ to satisfy).",
        ))
        unsatisfied = 0
        for char in state.characters:
            d6 = roll_d6(f"Savvy demands: {char.name}")
            result = d6.total + char.savvy
            satisfied = result >= 5
            status = "satisfied" if satisfied else "UNSATISFIED"
            if not satisfied:
                unsatisfied += 1
            events.append(TurnEvent(
                step=0, event_type=TurnEventType.CHARACTER_EVENT,
                description=(
                    f"{char.name}: D6({d6.total}) + Savvy({char.savvy}) = {result} — {status}"
                ),
                dice_rolls=[DiceRoll(
                    dice_type="d6", values=d6.values,
                    total=d6.total, label=f"Savvy demands: {char.name}",
                )],
            ))
        if unsatisfied > 0:
            morale_loss = unsatisfied
            state.colony.morale -= morale_loss
            events.append(TurnEvent(
                step=0, event_type=TurnEventType.MORALE,
                description=f"{unsatisfied} unsatisfied demand(s): -{morale_loss} Colony Morale.",
                state_changes={"morale_change": -morale_loss},
            ))

    # Lifeform evolution
    evolution = roll_lifeform_evolution()
    events.append(TurnEvent(
        step=0, event_type=TurnEventType.NARRATIVE,
        description=f"Lifeform Evolution: {evolution['name']} — {evolution['description']}",
    ))

    # Calamity check (triggered each milestone if CP > 0)
    from planetfall.engine.campaign.calamities import check_calamity
    calamity_events = check_calamity(state)
    events.extend(calamity_events)

    # End game trigger
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


# --- Summit Path Descriptions ---

SUMMIT_PATH_DESCRIPTIONS = {
    "Independence": (
        "The colony declares independence from the sponsoring corporation. "
        "Self-governance begins. The colony charts its own course among the stars."
    ),
    "Ascension": (
        "Through scientific breakthroughs and unity, the colony transcends its "
        "origins. A new era of discovery and evolution dawns."
    ),
    "Loyalty": (
        "The colony reaffirms its bonds with the sponsoring body. Resources "
        "flow freely, and the colony becomes a model outpost."
    ),
    "Isolation": (
        "The colony severs all ties and disappears from the galactic stage. "
        "Hidden among the stars, they build something entirely their own."
    ),
}


def execute_summit(
    state: GameState,
    chosen_path: str,
) -> list[TurnEvent]:
    """Execute The Summit — the endgame sequence.

    The Summit is a final pitched battle followed by a vote on the
    colony's future. The player chooses a path after seeing the votes
    and paying the resource cost.

    Args:
        chosen_path: One of Independence, Ascension, Loyalty, Isolation.

    Returns:
        Events describing the summit outcome.
    """
    events: list[TurnEvent] = []

    # Validate path
    if chosen_path not in SUMMIT_COSTS:
        events.append(TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=f"Invalid summit path: {chosen_path}",
        ))
        return events

    # Check resource costs
    costs = SUMMIT_COSTS[chosen_path]
    bp_cost = costs.get("bp", 0)
    rp_cost = costs.get("rp", 0)

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

    # Mark campaign as complete
    state.campaign.campaign_story_track.append(f"SUMMIT: {chosen_path}")
    state.flags.summit_path = chosen_path
    state.flags.campaign_complete = True

    path_desc = SUMMIT_PATH_DESCRIPTIONS.get(chosen_path, "")
    events.append(TurnEvent(
        step=0, event_type=TurnEventType.NARRATIVE,
        description=path_desc,
    ))

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

"""Step 5: Colony Events — Roll on the Colony Events table."""

from __future__ import annotations

from planetfall.engine.dice import roll_d6, roll_nd6
from planetfall.engine.models import GameState, TurnEvent, TurnEventType, DiceRoll
from planetfall.engine.tables.colony_events import COLONY_EVENTS_TABLE
from planetfall.engine.utils import format_display


def roll_colony_event():
    """Roll on the colony events table without applying effects.

    Returns (roll_result, entry) for reroll support.
    """
    return COLONY_EVENTS_TABLE.roll_on_table("Colony Events")


def apply_colony_event(state: GameState, roll_result, entry) -> list[TurnEvent]:
    """Apply a chosen colony event result and return events."""
    events = []

    desc = (
        f"Colony Event roll: {roll_result.total} — "
        f"{format_display(entry.result_id)}. "
        f"{entry.description}"
    )
    effects = entry.effects or {}

    # Apply automatic effects
    if "research_points" in effects:
        state.colony.resources.research_points += effects["research_points"]
    if "build_points" in effects:
        state.colony.resources.build_points += effects["build_points"]
    if "morale" in effects:
        state.colony.morale += effects["morale"]
    if "colony_damage" in effects:
        state.colony.integrity -= effects["colony_damage"]
    if "ancient_signs" in effects:
        state.campaign.ancient_signs_count += effects["ancient_signs"]
    if "all_xp" in effects:
        for char in state.characters:
            char.xp += effects["all_xp"]
    if "grunt" in effects:
        state.grunts.count += effects["grunt"]
    if effects.get("no_story_points"):
        state.flags.no_story_points_this_turn = True

    events.append(TurnEvent(
        step=5,
        event_type=TurnEventType.COLONY_EVENT,
        description=desc,
        dice_rolls=[
            DiceRoll(
                dice_type="d100", values=[roll_result.total],
                total=roll_result.total, label="Colony Events",
            ),
        ],
        state_changes={"event": entry.result_id, "effects": effects},
    ))

    # If an ancient sign was obtained, immediately check for Ancient Site
    if "ancient_signs" in effects and state.campaign.ancient_signs_count > 0:
        from planetfall.engine.campaign.ancient_signs import check_ancient_signs
        events.extend(check_ancient_signs(state))

    return events


def execute(state: GameState) -> list[TurnEvent]:
    """Roll on the Colony Events table and apply immediate effects."""
    roll_result, entry = roll_colony_event()
    return apply_colony_event(state, roll_result, entry)

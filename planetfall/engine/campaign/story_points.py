"""Story Points — spending mechanics for rerolls, prevention, and resources.

Rules (pages 55-57):
- Reroll any random table and pick either result.
- Prevent a roll on Enemy Activity, Morale Incident, or Integrity Failure.
- Roll 2D6 pick highest → take any combo of RP/BP/RM up to that value.
- Ignore a post-battle injury roll.
- During Crisis, roll twice on Crisis Outcome and pick the better score.
"""

from __future__ import annotations

from planetfall.engine.dice import roll_nd6, RollResult
from planetfall.engine.models import GameState, TurnEvent, TurnEventType, DiceRoll


def can_spend(state: GameState, amount: int = 1) -> bool:
    """Check if the colony has enough Story Points."""
    return state.colony.resources.story_points >= amount


def _spend(state: GameState, amount: int = 1) -> None:
    """Deduct Story Points from colony resources."""
    state.colony.resources.story_points -= amount


def spend_to_prevent_roll(
    state: GameState,
    roll_type: str,
) -> list[TurnEvent]:
    """Spend 1 SP to prevent a roll on Enemy Activity, Morale Incident,
    or Integrity Failure tables.

    Args:
        roll_type: One of "enemy_activity", "morale_incident", "integrity_failure".
    """
    if not can_spend(state):
        return [TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description="Not enough Story Points to prevent this roll.",
        )]

    valid_types = ("enemy_activity", "morale_incident", "integrity_failure")
    if roll_type not in valid_types:
        return [TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=f"Invalid roll type '{roll_type}'. Must be one of: {valid_types}",
        )]

    _spend(state)
    label = roll_type.replace("_", " ").title()

    return [TurnEvent(
        step=0, event_type=TurnEventType.NARRATIVE,
        description=(
            f"Story Point spent to prevent {label} roll. "
            f"Remaining: {state.colony.resources.story_points} SP."
        ),
        state_changes={"story_point_spent": roll_type},
    )]


def spend_for_resources(
    state: GameState,
    bp: int = 0,
    rp: int = 0,
    rm: int = 0,
) -> list[TurnEvent]:
    """Spend 1 SP → roll 2D6 pick highest → take any combo of RP/BP/RM
    up to that value.

    The caller must specify how to split the resources. The total
    (bp + rp + rm) must be <= the highest die roll.
    """
    if not can_spend(state):
        return [TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description="Not enough Story Points.",
        )]

    _spend(state)
    roll = roll_nd6(2, "Story Point resource roll")
    highest = max(roll.values)

    total_requested = bp + rp + rm
    if total_requested > highest:
        # Cap at what's available
        bp = min(bp, highest)
        rp = min(rp, highest - bp)
        rm = min(rm, highest - bp - rp)

    state.colony.resources.build_points += bp
    state.colony.resources.research_points += rp
    state.colony.resources.raw_materials += rm

    parts = []
    if bp:
        parts.append(f"+{bp} BP")
    if rp:
        parts.append(f"+{rp} RP")
    if rm:
        parts.append(f"+{rm} RM")

    return [TurnEvent(
        step=0, event_type=TurnEventType.NARRATIVE,
        description=(
            f"Story Point spent for resources. Rolled 2D6: {roll.values}, "
            f"highest = {highest}. Gained: {', '.join(parts) or 'nothing'}. "
            f"Remaining: {state.colony.resources.story_points} SP."
        ),
        dice_rolls=[DiceRoll(
            dice_type="2d6", values=roll.values,
            total=highest, label="Story Point resources",
        )],
    )]


def spend_to_ignore_injury(state: GameState, character_name: str) -> list[TurnEvent]:
    """Spend 1 SP to ignore a post-battle injury roll for a character."""
    if not can_spend(state):
        return [TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description="Not enough Story Points to ignore injury.",
        )]

    _spend(state)
    return [TurnEvent(
        step=9, event_type=TurnEventType.INJURY,
        description=(
            f"Story Point spent to ignore injury roll for {character_name}. "
            f"Remaining: {state.colony.resources.story_points} SP."
        ),
        state_changes={"story_point_spent": "ignore_injury", "character": character_name},
    )]


def spend_crisis_reroll(state: GameState) -> list[TurnEvent]:
    """Spend 1 SP during Crisis Outcome to roll twice and pick the better score."""
    if not can_spend(state):
        return [TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description="Not enough Story Points for crisis reroll.",
        )]

    _spend(state)

    # Mark that the next crisis outcome should roll twice
    state.flags.crisis_reroll_active = True

    return [TurnEvent(
        step=11, event_type=TurnEventType.MORALE,
        description=(
            f"Story Point spent: Crisis Outcome will roll twice, pick better. "
            f"Remaining: {state.colony.resources.story_points} SP."
        ),
    )]

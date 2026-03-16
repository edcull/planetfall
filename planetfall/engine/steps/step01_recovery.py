"""Step 1: Recovery — Characters in Sick Bay heal."""

from __future__ import annotations

from planetfall.engine.campaign.augmentation import has_augmentation
from planetfall.engine.models import GameState, TurnEvent, TurnEventType


def execute(state: GameState) -> list[TurnEvent]:
    """Reduce sick_bay_turns by 1 for all characters. Return events."""
    # Clear per-turn flags from previous turn
    state.flags.augmentation_bought_this_turn = False
    state.flags.no_story_points_this_turn = False
    state.flags.bot_repaired_this_turn = False
    state.flags.benched_trooper = ""

    events = []
    for char in state.characters:
        if char.sick_bay_turns > 0:
            # Check for saved excellent health bonus (from step 17)
            if "[EXCELLENT_HEALTH: saved]" in (char.notes or ""):
                old = char.sick_bay_turns
                char.sick_bay_turns = max(0, char.sick_bay_turns - 2)
                char.notes = char.notes.replace(
                    "[EXCELLENT_HEALTH: saved]", ""
                ).strip()
                events.append(TurnEvent(
                    step=1,
                    event_type=TurnEventType.RECOVERY,
                    description=(
                        f"{char.name} uses saved Excellent Health bonus! "
                        f"Recovery reduced by 2 ({old} → {char.sick_bay_turns} turns)."
                    ),
                ))
                if char.sick_bay_turns == 0:
                    continue  # Fully recovered via bonus

            char.sick_bay_turns -= 1
            if char.sick_bay_turns == 0:
                events.append(TurnEvent(
                    step=1,
                    event_type=TurnEventType.RECOVERY,
                    description=f"{char.name} has fully recovered and is available for duty.",
                ))
            else:
                events.append(TurnEvent(
                    step=1,
                    event_type=TurnEventType.RECOVERY,
                    description=(
                        f"{char.name} is recovering. "
                        f"{char.sick_bay_turns} turn(s) remaining in Sick Bay."
                    ),
                ))
    if not events:
        events.append(TurnEvent(
            step=1,
            event_type=TurnEventType.RECOVERY,
            description="No characters in Sick Bay. All crew available.",
        ))
    return events

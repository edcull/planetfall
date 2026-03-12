"""Step 18: Update Colony Tracking Sheet — Save state and advance turn."""

from __future__ import annotations

from planetfall.engine.models import GameState, TurnEvent, TurnEventType
from planetfall.engine.persistence import save_state


def execute(state: GameState) -> list[TurnEvent]:
    """Save the game state and advance to the next turn."""
    # Reset per-turn flags
    for enemy in state.enemies.tactical_enemies:
        enemy.disrupted_this_turn = False

    # Clear turn log for next turn
    turn_summary = [e.description for e in state.turn_log]

    # Save snapshot for current turn
    save_state(state)

    # Advance turn
    old_turn = state.current_turn
    state.current_turn += 1

    # Clear turn log
    state.turn_log.clear()

    return [TurnEvent(
        step=18,
        event_type=TurnEventType.NARRATIVE,
        description=(
            f"Turn {old_turn} complete. State saved. "
            f"Advancing to Turn {state.current_turn}."
        ),
        state_changes={
            "turn_completed": old_turn,
            "next_turn": state.current_turn,
            "summary": turn_summary,
        },
    )]

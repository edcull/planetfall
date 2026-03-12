"""Step 13: Replacements — Add new characters if roster has vacancies."""

from __future__ import annotations

from planetfall.engine.models import GameState, TurnEvent, TurnEventType

MAX_ROSTER_SIZE = 8


def get_vacancies(state: GameState) -> int:
    """Return number of open roster slots."""
    return MAX_ROSTER_SIZE - len(state.characters)


def execute(state: GameState) -> list[TurnEvent]:
    """Check for and report roster vacancies."""
    vacancies = get_vacancies(state)
    if vacancies > 0:
        return [TurnEvent(
            step=13,
            event_type=TurnEventType.REPLACEMENT,
            description=(
                f"Roster has {vacancies} vacancy(ies). "
                f"You may recruit new characters."
            ),
            state_changes={"vacancies": vacancies},
        )]
    return [TurnEvent(
        step=13,
        event_type=TurnEventType.REPLACEMENT,
        description="Roster is full. No replacements needed.",
    )]

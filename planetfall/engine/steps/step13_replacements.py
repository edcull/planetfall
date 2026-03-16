"""Step 13: Replacements — Add new characters if roster has vacancies.

Rules (p.69): Roll 2D6 when roster has vacancies.
  2-6:  Random class (sub-roll 1D6: 1-2 Trooper, 3-4 Scientist, 5-6 Scout)
  7-8:  Player choice of class
  9-12: Player choice of class
One replacement per milestone completed (pending_replacements counter).
"""

from __future__ import annotations

from planetfall.engine.dice import roll_nd6, roll_d6
from planetfall.engine.models import GameState, TurnEvent, TurnEventType

MAX_ROSTER_SIZE = 8


def get_vacancies(state: GameState) -> int:
    """Return number of open roster slots."""
    return MAX_ROSTER_SIZE - len(state.characters)


def roll_replacement_class() -> tuple[str, int, int | None]:
    """Roll on the replacement table (rules p.69).

    Returns (class_name, roll_2d6_total, sub_roll_or_none).
    If roll is 7+, class_name is "choice" (player decides).
    """
    roll = roll_nd6(2, "Replacement table")
    total = roll.total

    if total >= 7:
        return "choice", total, None

    # 2-6: Random class from sub-roll
    sub = roll_d6("Replacement class").total
    if sub <= 2:
        return "trooper", total, sub
    elif sub <= 4:
        return "scientist", total, sub
    else:
        return "scout", total, sub


def execute(state: GameState) -> list[TurnEvent]:
    """Check for roster vacancies and roll on the replacement table."""
    vacancies = get_vacancies(state)
    available_replacements = state.tracking.pending_replacements

    if vacancies <= 0:
        return [TurnEvent(
            step=13,
            event_type=TurnEventType.REPLACEMENT,
            description="Roster is full. No replacements needed.",
        )]

    if available_replacements <= 0:
        return [TurnEvent(
            step=13,
            event_type=TurnEventType.REPLACEMENT,
            description=(
                f"Roster has {vacancies} vacancy(ies) but no pending "
                f"replacements available (earned via milestones)."
            ),
            state_changes={"vacancies": vacancies, "available": 0},
        )]

    # Roll for each available replacement (up to vacancies)
    events = []
    rolls_to_make = min(vacancies, available_replacements)

    for i in range(rolls_to_make):
        char_class, roll_total, sub_roll = roll_replacement_class()
        state.tracking.pending_replacements -= 1

        if char_class == "choice":
            desc = (
                f"Replacement {i+1}: 2D6={roll_total} — "
                f"player chooses class (Trooper, Scientist, or Scout)."
            )
        else:
            desc = (
                f"Replacement {i+1}: 2D6={roll_total}, D6={sub_roll} — "
                f"{char_class.capitalize()} assigned."
            )

        events.append(TurnEvent(
            step=13,
            event_type=TurnEventType.REPLACEMENT,
            description=desc,
            state_changes={
                "replacement_class": char_class,
                "roll_2d6": roll_total,
                "sub_roll": sub_roll,
            },
        ))

    return events

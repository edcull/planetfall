"""Step 17a: Character Roleplay Event (Optional) — Narrative flavor only.

These events have NO mechanical effects. They exist purely to flesh
out the ongoing story for players who enjoy writing up campaigns.
See rules page 72.
"""

from __future__ import annotations

import random

from planetfall.engine.dice import roll_d6
from planetfall.engine.models import GameState, TurnEvent, TurnEventType, DiceRoll
from planetfall.engine.tables.character_events import CHARACTER_EVENTS_TABLE
from planetfall.engine.utils import format_display

# D6 outcome interpretations per roleplay event type
_D6_OUTCOMES: dict[str, dict[int, str]] = {
    "work_project": {
        1: "doesn't work",
        2: "succeeds", 3: "succeeds", 4: "succeeds",
        5: "succeeds extremely well", 6: "succeeds extremely well",
    },
    "letter_from_home": {
        1: "bad news",
        2: "general updates", 3: "general updates",
        4: "heartwarming", 5: "heartwarming",
        6: "great news",
    },
    "argument": {
        1: "worsens",
        2: "unresolved",
        3: "resolved", 4: "resolved",
        5: "another character resolves it",
        6: "strengthens relationship",
    },
    "night_out": {
        1: "trouble",
        2: "fine night", 3: "fine night", 4: "fine night",
        5: "completely wasted", 6: "completely wasted",
    },
    "work_with_colleague": {
        1: "bicker constantly",
        2: "work well together", 3: "work well together",
        4: "work well together", 5: "work well together",
        6: "strengthens relationship",
    },
}


def execute(state: GameState) -> list[TurnEvent]:
    """Pick a random character and roll a purely narrative roleplay event.

    These events have NO mechanical effects on game state.
    """
    if not state.characters:
        return []

    char = random.choice(state.characters)
    roll_result, entry = CHARACTER_EVENTS_TABLE.roll_on_table(
        f"Roleplay Event: {char.name}"
    )
    effects = entry.effects or {}

    # Pick other characters if needed
    others = [c for c in state.characters if c.name != char.name]
    involved = []
    num_others = effects.get("involves_other", 0)
    if num_others > 0 and others:
        involved = random.sample(others, min(num_others, len(others)))

    desc = (
        f"[Roleplay] {char.name}: "
        f"{format_display(entry.result_id)}. "
        f"{entry.description}"
    )
    if involved:
        names = " and ".join(c.name for c in involved)
        desc += f" (with {names})"

    all_dice = [DiceRoll(
        dice_type="d100", values=[roll_result.total],
        total=roll_result.total, label=f"Roleplay Event: {char.name}",
    )]

    # Roll D6 sub-roll if needed (purely narrative)
    if effects.get("roll_d6"):
        d6_roll = roll_d6(f"{entry.result_id} outcome")
        all_dice.append(DiceRoll(
            dice_type="d6", values=d6_roll.values,
            total=d6_roll.total, label=f"{entry.result_id} outcome",
        ))
        outcomes = _D6_OUTCOMES.get(entry.result_id, {})
        d6_outcome = outcomes.get(d6_roll.total, f"roll {d6_roll.total}")
        desc += f" D6 result: {d6_roll.total} — {d6_outcome}."

    return [TurnEvent(
        step=17,
        event_type=TurnEventType.CHARACTER_EVENT,
        description=desc,
        dice_rolls=all_dice,
        state_changes={
            "character": char.name,
            "event": entry.result_id,
            "involved": [c.name for c in involved],
            "roleplay_only": True,
        },
    )]

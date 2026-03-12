"""Step 9: Injuries — Roll on injury tables for casualties."""

from __future__ import annotations

from planetfall.engine.campaign.augmentation import has_augmentation
from planetfall.engine.dice import roll_d6
from planetfall.engine.models import GameState, TurnEvent, TurnEventType, DiceRoll
from planetfall.engine.tables.injuries import CHARACTER_INJURY_TABLE, GRUNT_INJURY_TABLE


def execute(
    state: GameState,
    character_casualties: list[str],
    grunt_casualties: int = 0,
) -> list[TurnEvent]:
    """Roll injuries for all casualties.

    Args:
        character_casualties: Names of characters who became casualties.
        grunt_casualties: Number of grunts who became casualties.
    """
    events = []

    # Check for Med-Evac building (1 casualty gets 2 rolls, pick better)
    has_medevac = any(b.name == "Med-Evac Shuttle Facility" for b in state.colony.buildings)
    medevac_used = False

    # Character injuries
    for name in character_casualties:
        char = None
        char_idx = None
        for i, c in enumerate(state.characters):
            if c.name == name:
                char = c
                char_idx = i
                break

        if char is None:
            continue

        # Med-Evac: first casualty gets 2 rolls, pick better result
        if has_medevac and not medevac_used:
            medevac_used = True
            roll1, entry1 = CHARACTER_INJURY_TABLE.roll_on_table(f"Injury: {name} (Med-Evac roll 1)")
            roll2, entry2 = CHARACTER_INJURY_TABLE.roll_on_table(f"Injury: {name} (Med-Evac roll 2)")
            # Higher roll = better outcome on injury table
            if roll2.total > roll1.total:
                roll_result, entry = roll2, entry2
                other_roll = roll1.total
            else:
                roll_result, entry = roll1, entry1
                other_roll = roll2.total
            events.append(TurnEvent(
                step=9, event_type=TurnEventType.INJURY,
                description=(
                    f"{name}: Med-Evac — rolled {roll1.total} and {roll2.total}, "
                    f"keeping {roll_result.total}."
                ),
                dice_rolls=[DiceRoll(
                    dice_type="d100", values=[roll1.total, roll2.total],
                    total=roll_result.total, label=f"Med-Evac Injury: {name}",
                )],
            ))
        else:
            roll_result, entry = CHARACTER_INJURY_TABLE.roll_on_table(f"Injury: {name}")

        effects = entry.effects or {}

        if effects.get("dead"):
            # Character dies — gain 1 story point
            state.characters.pop(char_idx)
            state.colony.resources.story_points += 1
            desc = (
                f"{name}: Roll {roll_result.total} — DEAD. "
                f"Colony gains +1 Story Point."
            )
        elif "sick_bay_turns" in effects:
            turns = effects["sick_bay_turns"]
            # Boosted Recovery augmentation: -1 turn when sent to Sick Bay
            if has_augmentation(state, "boosted_recovery"):
                turns = max(1, turns - 1)
            char.sick_bay_turns = turns
            desc = (
                f"{name}: Roll {roll_result.total} — "
                f"{entry.result_id.replace('_', ' ').title()}. "
                f"{char.sick_bay_turns} turns in Sick Bay."
            )
            if has_augmentation(state, "boosted_recovery"):
                desc += " (Boosted Recovery: -1 turn)"
        elif effects.get("xp"):
            char.xp += effects["xp"]
            desc = (
                f"{name}: Roll {roll_result.total} — School of Hard Knocks. "
                f"Okay, +1 XP."
            )
        else:
            desc = f"{name}: Roll {roll_result.total} — Okay."

        events.append(TurnEvent(
            step=9,
            event_type=TurnEventType.INJURY,
            description=desc,
            dice_rolls=[DiceRoll(
                dice_type="d100", values=[roll_result.total],
                total=roll_result.total, label=f"Injury: {name}",
            )],
        ))

    # Grunt injuries
    grunts_lost = 0
    for i in range(grunt_casualties):
        roll_result, entry = GRUNT_INJURY_TABLE.roll_on_table(f"Grunt #{i+1} Injury")
        if entry.effects and entry.effects.get("dead"):
            grunts_lost += 1

    if grunt_casualties > 0:
        state.grunts.count -= grunts_lost
        survivors = grunt_casualties - grunts_lost
        desc = (
            f"Grunt casualties: {grunt_casualties}. "
            f"Lost: {grunts_lost}. Recovered: {survivors}. "
            f"Remaining grunts: {state.grunts.count}."
        )
        events.append(TurnEvent(
            step=9,
            event_type=TurnEventType.INJURY,
            description=desc,
        ))

    if not events:
        events.append(TurnEvent(
            step=9,
            event_type=TurnEventType.INJURY,
            description="No casualties to process.",
        ))

    return events

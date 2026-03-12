"""Step 16: Colony Integrity — Check for Integrity Failure.

Rules (pages 87-88):
- If Integrity is -3 or worse, roll 3D6.
- If roll ≤ |Integrity|, consult the Integrity Failure table.
- You may spend 1 Story Point to avoid rolling.
- Integrity of -1 or -2 has no risk (can't roll below 3 on 3D6).
"""

from __future__ import annotations

import random

from planetfall.engine.dice import roll_nd6
from planetfall.engine.models import GameState, TurnEvent, TurnEventType, DiceRoll
from planetfall.engine.tables.integrity_failure import INTEGRITY_FAILURE_TABLE
from planetfall.engine.tables.injuries import CHARACTER_INJURY_TABLE


def execute(state: GameState, spend_story_point: bool = False) -> list[TurnEvent]:
    """Check colony integrity and roll for failure if needed.

    Args:
        spend_story_point: If True, spend 1 SP to skip the Integrity Failure roll.
    """
    integrity = state.colony.integrity
    events = []

    if integrity >= 0:
        events.append(TurnEvent(
            step=16,
            event_type=TurnEventType.REPAIR,
            description=f"Colony Integrity: {integrity}. Colony is stable.",
        ))
        return events

    if integrity >= -2:
        events.append(TurnEvent(
            step=16,
            event_type=TurnEventType.REPAIR,
            description=(
                f"Colony Integrity: {integrity}. Damaged but no failure "
                f"risk (minimum 3D6 roll is 3)."
            ),
        ))
        return events

    # Integrity is -3 or worse — player may spend 1 SP to skip
    if spend_story_point and state.colony.resources.story_points >= 1:
        state.colony.resources.story_points -= 1
        events.append(TurnEvent(
            step=16,
            event_type=TurnEventType.REPAIR,
            description=(
                f"Colony Integrity: {integrity}. Story Point spent to avoid "
                f"Integrity Failure roll. "
                f"Remaining: {state.colony.resources.story_points} SP."
            ),
            state_changes={"story_point_spent": "integrity_failure"},
        ))
        return events

    # Roll for failure
    threshold = abs(integrity)
    roll = roll_nd6(3, "Integrity Failure check")
    dice = [DiceRoll(
        dice_type="3d6", values=roll.values,
        total=roll.total, label="Integrity Failure check",
    )]

    if roll.total > threshold:
        events.append(TurnEvent(
            step=16,
            event_type=TurnEventType.REPAIR,
            description=(
                f"Colony Integrity: {integrity}. "
                f"Failure check: Roll {roll.total} > {threshold} — "
                f"no failure this turn."
            ),
            dice_rolls=dice,
        ))
        return events

    # Failure! Look up the result on the table
    entry = INTEGRITY_FAILURE_TABLE.lookup(roll.total)
    effects = entry.effects or {}

    desc = (
        f"Colony Integrity: {integrity}. "
        f"INTEGRITY FAILURE! Roll {roll.total} ≤ {threshold}. "
        f"{entry.description}"
    )

    extra_dice: list[DiceRoll] = []

    # Apply effects
    effect_desc = _apply_failure_effects(state, effects, extra_dice)
    if effect_desc:
        desc += f" Effect: {effect_desc}"

    events.append(TurnEvent(
        step=16,
        event_type=TurnEventType.REPAIR,
        description=desc,
        dice_rolls=dice + extra_dice,
        state_changes={"failure_result": entry.result_id},
    ))

    return events


def _apply_failure_effects(
    state: GameState,
    effects: dict,
    extra_dice: list[DiceRoll],
) -> str:
    """Apply the effects of an integrity failure result."""
    parts: list[str] = []

    # Morale loss
    if "morale" in effects:
        state.colony.morale += effects["morale"]
        parts.append(f"Colony Morale {effects['morale']:+d}")

    # Colony damage
    if "colony_damage" in effects:
        dmg = effects["colony_damage"]
        state.colony.integrity -= dmg
        # Colony damage also reduces morale (rules p.87)
        state.colony.morale -= dmg
        parts.append(
            f"{dmg} Colony Damage (Integrity now {state.colony.integrity}, "
            f"Morale -{dmg})"
        )

    # BP/RP penalties next turn (store for orchestrator to apply)
    if "bp_penalty_next" in effects:
        state.flags.bp_penalty_next += effects["bp_penalty_next"]
        parts.append(f"BP next turn {effects['bp_penalty_next']:+d}")
    if "rp_penalty_next" in effects:
        state.flags.rp_penalty_next += effects["rp_penalty_next"]
        parts.append(f"RP next turn {effects['rp_penalty_next']:+d}")

    # Injury roll for random character
    if effects.get("injury_roll"):
        if state.characters:
            char = random.choice(state.characters)
            inj_roll, inj_entry = CHARACTER_INJURY_TABLE.roll_on_table(
                f"Integrity failure injury: {char.name}"
            )
            extra_dice.append(DiceRoll(
                dice_type="d100", values=[inj_roll.total],
                total=inj_roll.total,
                label=f"Injury: {char.name}",
            ))
            inj_effects = inj_entry.effects or {}
            death_override = effects.get("death_override_turns")

            if inj_effects.get("dead"):
                if death_override:
                    char.sick_bay_turns = death_override
                    parts.append(
                        f"{char.name} injury roll {inj_roll.total}: "
                        f"Would be dead — {death_override} turns recovery"
                    )
                else:
                    state.characters.remove(char)
                    state.colony.resources.story_points += 1
                    parts.append(
                        f"{char.name} injury roll {inj_roll.total}: DEAD. "
                        f"+1 Story Point"
                    )
            elif "sick_bay_turns" in inj_effects:
                char.sick_bay_turns = inj_effects["sick_bay_turns"]
                parts.append(
                    f"{char.name} injury roll {inj_roll.total}: "
                    f"{char.sick_bay_turns} turns Sick Bay"
                )
            else:
                parts.append(
                    f"{char.name} injury roll {inj_roll.total}: Okay"
                )

    # Character slain outright
    if effects.get("character_slain"):
        if state.characters:
            char = random.choice(state.characters)
            state.characters.remove(char)
            state.colony.resources.story_points += 1
            parts.append(f"{char.name} is slain. +1 Story Point")

    return "; ".join(parts)

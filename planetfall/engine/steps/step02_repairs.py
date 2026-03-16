"""Step 2: Repairs — Restore colony damage using repair capacity + raw materials."""

from __future__ import annotations

from planetfall.engine.models import GameState, TurnEvent, TurnEventType


def execute(state: GameState, raw_materials_spent: int = 0) -> list[TurnEvent]:
    """Repair colony damage.

    Args:
        raw_materials_spent: Extra raw materials to spend on repairs (max 3).

    Returns list of events describing what happened.
    """
    events = []
    colony = state.colony

    if colony.integrity >= 0:
        events.append(TurnEvent(
            step=2,
            event_type=TurnEventType.REPAIR,
            description="Colony is undamaged. No repairs needed.",
        ))
        return events

    # Clamp raw materials spent
    raw_materials_spent = min(raw_materials_spent, 3)
    raw_materials_spent = min(raw_materials_spent, colony.resources.raw_materials)

    # Calculate total repair
    repair_capacity = colony.per_turn_rates.repair_capacity
    total_repair = repair_capacity + raw_materials_spent

    # Apply repairs
    old_integrity = colony.integrity
    colony.integrity = min(0, colony.integrity + total_repair)
    colony.resources.raw_materials -= raw_materials_spent
    actual_repair = colony.integrity - old_integrity

    # Repair bots
    bot_repaired = False
    if not state.grunts.bot_operational:
        state.grunts.bot_operational = True
        bot_repaired = True
        state.flags.bot_repaired_this_turn = True  # Cannot deploy this turn (rules p.58)

    desc = (
        f"Repaired {actual_repair} point(s) of Colony Damage "
        f"(capacity: {repair_capacity}, raw materials spent: {raw_materials_spent}). "
        f"Colony Integrity: {colony.integrity}."
    )
    if bot_repaired:
        desc += " Bot repaired and operational."

    events.append(TurnEvent(
        step=2,
        event_type=TurnEventType.REPAIR,
        description=desc,
        state_changes={
            "integrity": colony.integrity,
            "raw_materials_spent": raw_materials_spent,
        },
    ))
    return events

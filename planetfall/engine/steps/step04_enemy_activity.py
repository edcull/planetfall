"""Step 4: Enemy Activity — Roll for each tactical enemy's actions."""

from __future__ import annotations

import random

from planetfall.engine.dice import roll_d6
from planetfall.engine.models import GameState, TurnEvent, TurnEventType, DiceRoll
from planetfall.engine.tables.enemy_activity import ENEMY_ACTIVITY_TABLE


def execute(state: GameState) -> list[TurnEvent]:
    """Roll enemy activity for each active tactical enemy.

    Returns events describing enemy actions. May set forced missions.
    """
    events = []
    active_enemies = [
        e for e in state.enemies.tactical_enemies
        if not e.defeated and not e.disrupted_this_turn
    ]

    if not active_enemies:
        events.append(TurnEvent(
            step=4,
            event_type=TurnEventType.ENEMY_ACTIVITY,
            description="No active Tactical Enemies. Skipping enemy activity.",
        ))
        return events

    for enemy in active_enemies:
        roll_result, entry = ENEMY_ACTIVITY_TABLE.roll_on_table(
            f"Enemy Activity: {enemy.name}"
        )

        desc = (
            f"{enemy.name} ({enemy.enemy_type}): "
            f"Roll {roll_result.total} — {entry.result_id.replace('_', ' ').title()}. "
            f"{entry.description}"
        )

        # Handle raid damage
        if entry.result_id == "raid":
            damage = len(enemy.sectors) + 1
            # Roll colony defenses
            defense_negated = 0
            if state.colony.defenses > 0:
                for _ in range(state.colony.defenses):
                    d = roll_d6("Colony Defense")
                    if d.total >= 4:
                        defense_negated += 1
            actual_damage = max(0, damage - defense_negated)
            state.colony.integrity -= actual_damage
            desc += (
                f" Colony takes {actual_damage} damage "
                f"({damage} base, {defense_negated} negated by defenses)."
            )

        events.append(TurnEvent(
            step=4,
            event_type=TurnEventType.ENEMY_ACTIVITY,
            description=desc,
            dice_rolls=[
                DiceRoll(
                    dice_type="d100", values=[roll_result.total],
                    total=roll_result.total, label=f"Enemy Activity: {enemy.name}",
                ),
            ],
            state_changes={
                "enemy": enemy.name,
                "activity": entry.result_id,
                "effects": entry.effects,
            },
        ))

    return events

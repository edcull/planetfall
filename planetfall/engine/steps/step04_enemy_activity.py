"""Step 4: Enemy Activity — Roll for each tactical enemy's actions."""

from __future__ import annotations

import random

from planetfall.engine.dice import roll_d6
from planetfall.engine.models import GameState, TurnEvent, TurnEventType, DiceRoll
from planetfall.engine.tables.enemy_activity import ENEMY_ACTIVITY_TABLE
from planetfall.engine.utils import format_display, sync_enemy_sectors


def _get_adjacent_sector_ids(state: GameState, sector_id: int) -> set[int]:
    """Get sector IDs adjacent to a given sector on the 6-column grid map."""
    cols = 6
    total = len(state.campaign_map.sectors)
    row, col = divmod(sector_id, cols)
    adjacent = set()
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            nr, nc = row + dr, col + dc
            nid = nr * cols + nc
            if 0 <= nr < (total + cols - 1) // cols and 0 <= nc < cols and 0 <= nid < total:
                adjacent.add(nid)
    return adjacent


def _apply_raid(state: GameState, enemy, events: list[TurnEvent]) -> str:
    """Apply raid damage: sectors+1, minus colony defense rolls."""
    damage = len(enemy.sectors) + 1
    defense_negated = 0
    if state.colony.defenses > 0:
        for _ in range(state.colony.defenses):
            d = roll_d6("Colony Defense")
            if d.total >= 4:
                defense_negated += 1
    actual_damage = max(0, damage - defense_negated)
    state.colony.integrity -= actual_damage
    return (
        f" Colony takes {actual_damage} damage "
        f"({damage} base, {defense_negated} negated by defenses)."
    )


def _apply_occupy(state: GameState, enemy, events: list[TurnEvent], count: int = 1) -> str:
    """Enemy expands into adjacent sectors. Returns description suffix."""
    colony_id = state.campaign_map.colony_sector_id
    extra_desc = ""

    for _ in range(count):
        # Find all adjacent sectors to enemy-held sectors
        adj_candidates = set()
        for sid in enemy.sectors:
            adj_candidates |= _get_adjacent_sector_ids(state, sid)
        adj_candidates -= set(enemy.sectors)
        total_sectors = len(state.campaign_map.sectors)
        adj_candidates = {s for s in adj_candidates if 0 <= s < total_sectors}

        if not adj_candidates:
            extra_desc += f" {enemy.name} has no room to expand."
            break

        new_sector = random.choice(list(adj_candidates))

        # If colony sector, treat as raid instead
        if new_sector == colony_id:
            extra_desc += f" Expansion targets colony — treated as Raid!"
            extra_desc += _apply_raid(state, enemy, events)
            continue

        # If another enemy's sector, randomly determine who keeps it
        other_owner = None
        for other in state.enemies.tactical_enemies:
            if other.name != enemy.name and not other.defeated and new_sector in other.sectors:
                other_owner = other
                break

        if other_owner:
            winner = random.choice([enemy, other_owner])
            if winner == enemy:
                other_owner.sectors.remove(new_sector)
                enemy.sectors.append(new_sector)
                extra_desc += (
                    f" {enemy.name} takes sector {new_sector} from {other_owner.name}!"
                )
            else:
                extra_desc += (
                    f" {other_owner.name} holds sector {new_sector} against {enemy.name}."
                )
        else:
            enemy.sectors.append(new_sector)
            extra_desc += f" {enemy.name} occupies sector {new_sector}."

    sync_enemy_sectors(state)
    return extra_desc


def _apply_relocate(state: GameState, enemy, events: list[TurnEvent]) -> str:
    """Enemy moves from one sector to an adjacent one."""
    colony_id = state.campaign_map.colony_sector_id

    if not enemy.sectors:
        return " No sectors to relocate from."

    # Pick a random occupied sector
    from_sector = random.choice(enemy.sectors)

    # Find adjacent unoccupied sectors
    adj = _get_adjacent_sector_ids(state, from_sector)
    total_sectors = len(state.campaign_map.sectors)
    adj = {s for s in adj if 0 <= s < total_sectors}
    adj -= set(enemy.sectors)

    if not adj:
        return f" {enemy.name} has nowhere to relocate."

    to_sector = random.choice(list(adj))

    # If target is colony, raid and move opposite direction
    if to_sector == colony_id:
        extra = f" Relocation targets colony — treated as Raid!"
        extra += _apply_raid(state, enemy, events)
        # Move away from colony instead — just stay put
        return extra

    enemy.sectors.remove(from_sector)
    enemy.sectors.append(to_sector)
    sync_enemy_sectors(state)
    return f" {enemy.name} relocates from sector {from_sector} to sector {to_sector}."


def roll_enemy_activity(enemy_name: str):
    """Roll on the enemy activity table without applying effects.

    Returns (roll_result, entry) for the orchestrator to optionally reroll.
    """
    return ENEMY_ACTIVITY_TABLE.roll_on_table(f"Enemy Activity: {enemy_name}")


def apply_enemy_activity(
    state: GameState, enemy, roll_result, entry,
) -> list[TurnEvent]:
    """Apply a chosen enemy activity result and return events."""
    events = []

    desc = (
        f"{enemy.name} ({enemy.enemy_type}): "
        f"Roll {roll_result.total} — {format_display(entry.result_id)}. "
        f"{entry.description}"
    )

    if entry.result_id == "raid":
        desc += _apply_raid(state, enemy, events)
    elif entry.result_id == "occupy":
        desc += _apply_occupy(state, enemy, events, count=1)
    elif entry.result_id == "rapid_expansion":
        desc += _apply_occupy(state, enemy, events, count=2)
    elif entry.result_id == "relocate":
        desc += _apply_relocate(state, enemy, events)
    elif entry.result_id == "attack":
        pass  # Forced mission picked up by step 6 via state_changes

    state_changes = {
        "enemy": enemy.name,
        "activity": entry.result_id,
        "effects": entry.effects,
    }
    if entry.effects.get("forced_mission"):
        state_changes["forced_mission"] = entry.effects["forced_mission"]

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
        state_changes=state_changes,
    ))

    return events


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
        roll_result, entry = roll_enemy_activity(enemy.name)
        events.extend(apply_enemy_activity(state, enemy, roll_result, entry))

    return events

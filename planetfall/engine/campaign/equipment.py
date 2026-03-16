"""Equipment management — buy, swap, and manage character gear.

Characters carry equipment as a list of string names. This module
provides the armory catalog and trade/swap mechanics.
"""

from __future__ import annotations

from planetfall.engine.models import GameState, TurnEvent, TurnEventType


# Armory catalog: items available for purchase
ARMORY = {
    # Ranged weapons
    "colony_rifle": {"name": "Colony Rifle", "type": "weapon", "cost_bp": 1, "range": 24, "shots": 1, "damage": 0, "traits": []},
    "hand_gun": {"name": "Hand Gun", "type": "weapon", "cost_bp": 0, "range": 12, "shots": 1, "damage": 0, "traits": []},
    "shotgun": {"name": "Shotgun", "type": "weapon", "cost_bp": 1, "range": 12, "shots": 2, "damage": 0, "traits": []},
    "marksman_rifle": {"name": "Marksman Rifle", "type": "weapon", "cost_bp": 2, "range": 36, "shots": 1, "damage": 0, "traits": ["stabilized"]},
    "auto_rifle": {"name": "Auto Rifle", "type": "weapon", "cost_bp": 2, "range": 18, "shots": 2, "damage": 0, "traits": []},
    "blast_pistol": {"name": "Blast Pistol", "type": "weapon", "cost_bp": 2, "range": 9, "shots": 1, "damage": 1, "traits": []},
    "blast_rifle": {"name": "Blast Rifle", "type": "weapon", "cost_bp": 3, "range": 18, "shots": 1, "damage": 1, "traits": []},
    "flak_gun": {"name": "Flak Gun", "type": "weapon", "cost_bp": 2, "range": 18, "shots": 2, "damage": 0, "traits": ["area"]},
    "beam_emitter": {"name": "Beam Emitter", "type": "weapon", "cost_bp": 3, "range": 24, "shots": 1, "damage": 1, "traits": ["ap_ammo"]},
    "fury_rifle": {"name": "Fury Rifle", "type": "weapon", "cost_bp": 3, "range": 18, "shots": 3, "damage": 0, "traits": []},
    # Melee weapons
    "blade": {"name": "Blade", "type": "melee", "cost_bp": 0, "melee_damage": 1, "traits": ["melee"]},
    "power_claw": {"name": "Power Claw", "type": "melee", "cost_bp": 2, "melee_damage": 2, "traits": ["melee"]},
    "carver_blade": {"name": "Carver Blade", "type": "melee", "cost_bp": 2, "melee_damage": 2, "traits": ["melee", "ap_ammo"]},
    # Armor
    "trooper_armor": {"name": "Trooper Armor", "type": "armor", "cost_bp": 1, "armor_save": 5},
    "battle_armor": {"name": "Battle Armor", "type": "armor", "cost_bp": 3, "armor_save": 4},
    "screen_generator": {"name": "Screen Generator", "type": "armor", "cost_bp": 3, "armor_save": 5, "traits": ["regenerating"]},
    # Gear
    "scanner": {"name": "Scanner", "type": "gear", "cost_bp": 1, "effect": "+1 Savvy for detection rolls"},
    "med_kit": {"name": "Med Kit", "type": "gear", "cost_bp": 1, "effect": "Reduce sick bay by 1 turn"},
    "stim_pack": {"name": "Stim Pack", "type": "gear", "cost_bp": 1, "effect": "Single-use: ignore wounds for 1 battle"},
    "grapple_launcher": {"name": "Grapple Launcher", "type": "gear", "cost_bp": 1, "effect": "Can move to any adjacent zone ignoring terrain"},
}


def get_armory_catalog(state: GameState) -> list[dict]:
    """Get available items from the armory with affordability."""
    bp = state.colony.resources.build_points
    return [
        {
            "id": item_id,
            **item,
            "affordable": bp >= item["cost_bp"],
        }
        for item_id, item in ARMORY.items()
    ]


def purchase_equipment(
    state: GameState, item_id: str, character_name: str
) -> list[TurnEvent]:
    """Purchase an item from the armory and give it to a character."""
    if item_id not in ARMORY:
        return [TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=f"Unknown item: {item_id}",
        )]

    item = ARMORY[item_id]
    cost = item["cost_bp"]

    if state.colony.resources.build_points < cost:
        return [TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=f"Not enough BP ({cost} needed, {state.colony.resources.build_points} available).",
        )]

    char = state.find_character(character_name)
    if not char:
        return [TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=f"Character not found: {character_name}",
        )]

    state.colony.resources.build_points -= cost
    char.equipment.append(item["name"])

    return [TurnEvent(
        step=0, event_type=TurnEventType.NARRATIVE,
        description=(
            f"{character_name} equipped with {item['name']}. "
            f"({cost} BP spent, {state.colony.resources.build_points} remaining)"
        ),
        state_changes={"item": item["name"], "character": character_name, "cost": cost},
    )]


def swap_equipment(
    state: GameState,
    from_char: str,
    to_char: str,
    item_name: str,
) -> list[TurnEvent]:
    """Swap an equipment item between two characters."""
    source = state.find_character(from_char)
    target = state.find_character(to_char)

    if not source or not target:
        return [TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description="Character not found for equipment swap.",
        )]

    if item_name not in source.equipment:
        return [TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=f"{from_char} doesn't have {item_name}.",
        )]

    source.equipment.remove(item_name)
    target.equipment.append(item_name)

    return [TurnEvent(
        step=0, event_type=TurnEventType.NARRATIVE,
        description=f"{item_name} transferred from {from_char} to {to_char}.",
    )]


def sell_equipment(
    state: GameState, character_name: str, item_name: str
) -> list[TurnEvent]:
    """Sell equipment back for half cost (minimum 1 RM)."""
    char = state.find_character(character_name)
    if not char or item_name not in char.equipment:
        return [TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=f"Cannot sell: item not found.",
        )]

    # Find original cost
    refund = 1  # minimum
    for item_id, item in ARMORY.items():
        if item["name"] == item_name:
            refund = max(1, item["cost_bp"] // 2)
            break

    char.equipment.remove(item_name)
    state.colony.resources.raw_materials += refund

    return [TurnEvent(
        step=0, event_type=TurnEventType.NARRATIVE,
        description=f"{character_name} sold {item_name} for {refund} Raw Materials.",
    )]

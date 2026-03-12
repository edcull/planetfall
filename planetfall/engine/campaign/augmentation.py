"""Augmentation system — colony-wide genetic enhancements.

Rules (pages 105-106):
- Progressive cost: 1st augmentation costs 1 AP, 2nd costs 2 AP, etc.
  Cost is based on TOTAL colony augmentations, not per-character.
- Each augmentation can only be purchased ONCE per campaign.
- Once selected, an augmentation applies to EVERY current and future character.
- Only one augmentation may be purchased per campaign turn.
- Bots and Soulless are unaffected.
"""

from __future__ import annotations

from planetfall.engine.models import GameState, SubSpecies, TurnEvent, TurnEventType


# Available augmentations
AUGMENTATIONS = {
    "boosted_decision_making": {
        "name": "Boosted Decision Making",
        "description": (
            "Reroll one reaction die per battle round. "
            "Counts as a Milestone. +1 Story Point."
        ),
        "effect": "reaction_reroll",
        "story_points": 1,
        "is_milestone": True,
    },
    "boosted_recovery": {
        "name": "Boosted Recovery",
        "description": (
            "When a character is sent to Sick Bay, reduce initial "
            "recovery time by 1 turn. No effect on Grunts."
        ),
        "effect": "recovery_boost",
    },
    "claws": {
        "name": "Claws",
        "description": (
            "All characters have a Damage +0 Melee weapon that cannot "
            "be lost."
        ),
        "effect": "melee_boost",
    },
    "enhanced_mobility": {
        "name": "Enhanced Mobility",
        "description": (
            "Characters moving in a straight line increase base move by 1\". "
            "Dash moves are 3\" instead of 2\"."
        ),
        "effect": "speed_boost",
    },
    "enhanced_vision": {
        "name": "Enhanced Vision",
        "description": "All visibility limits increased by +3\".",
        "effect": "vision_boost",
    },
    "inherent_protection": {
        "name": "Inherent Protection",
        "description": (
            "All characters receive a 6+ Saving Throw against incoming "
            "damage. Normal combined Saving Throw rules apply."
        ),
        "effect": "armor_boost",
    },
    "mental_links": {
        "name": "Mental Links",
        "description": (
            "Each battle round, you may reroll one Initiative die. "
            "Counts as a Milestone."
        ),
        "effect": "initiative_reroll",
        "is_milestone": True,
    },
    "psionic_cohesion": {
        "name": "Psionic Cohesion",
        "description": (
            "Any character that would lose a level of Loyalty rolls 1D6. "
            "On 5-6, they do not lose a level."
        ),
        "effect": "loyalty_protection",
    },
}


def get_colony_augmentations(state: GameState) -> list[str]:
    """Get the list of augmentation IDs the colony has purchased."""
    return list(state.flags.colony_augmentations)


def has_augmentation(state: GameState, augmentation_id: str) -> bool:
    """Check if the colony has a specific augmentation."""
    return augmentation_id in get_colony_augmentations(state)


def get_augmentation_cost(state: GameState) -> int:
    """Get the AP cost for the next colony augmentation.

    Cost = number of augmentations already purchased + 1.
    """
    return len(get_colony_augmentations(state)) + 1


def get_available_augmentations(state: GameState) -> list[dict]:
    """Get augmentations available for purchase."""
    owned = set(get_colony_augmentations(state))
    cost = len(owned) + 1

    available = []
    for aug_id, aug in AUGMENTATIONS.items():
        if aug_id not in owned:
            available.append({
                "id": aug_id,
                "name": aug["name"],
                "description": aug["description"],
                "cost": cost,
                "affordable": state.colony.resources.augmentation_points >= cost,
            })
    return available


def apply_augmentation(
    state: GameState, augmentation_id: str
) -> list[TurnEvent]:
    """Purchase and apply a colony-wide augmentation.

    Applies to all current characters (except Bots/Soulless).
    Future characters automatically inherit colony augmentations.
    """
    if augmentation_id not in AUGMENTATIONS:
        return [TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=f"Unknown augmentation: {augmentation_id}",
        )]

    aug = AUGMENTATIONS[augmentation_id]
    owned = get_colony_augmentations(state)

    if augmentation_id in owned:
        return [TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=f"Colony already has {aug['name']}.",
        )]

    # Check if already bought one this turn
    if state.flags.augmentation_bought_this_turn:
        return [TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description="Only one augmentation may be purchased per campaign turn.",
        )]

    cost = len(owned) + 1
    if state.colony.resources.augmentation_points < cost:
        return [TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=(
                f"Not enough AP ({cost} needed, "
                f"{state.colony.resources.augmentation_points} available)."
            ),
        )]

    # Spend AP
    state.colony.resources.augmentation_points -= cost

    # Record colony-wide augmentation
    owned.append(augmentation_id)
    state.flags.colony_augmentations = owned
    state.flags.augmentation_bought_this_turn = True

    events = []

    # Apply immediate stat effects to all eligible characters
    affected = _apply_to_all_characters(state, augmentation_id)

    # Apply colony effects
    if aug.get("story_points"):
        state.colony.resources.story_points += aug["story_points"]

    # Milestone check
    if aug.get("is_milestone"):
        state.campaign.milestones_completed += 1
        events.append(TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=f"MILESTONE! {aug['name']} triggers a milestone.",
        ))

    events.insert(0, TurnEvent(
        step=0, event_type=TurnEventType.NARRATIVE,
        description=(
            f"Colony augmentation purchased: {aug['name']} — "
            f"{aug['description']} (Cost: {cost} AP, "
            f"Remaining: {state.colony.resources.augmentation_points} AP). "
            f"Applied to {affected} character(s)."
        ),
        state_changes={
            "augmentation": augmentation_id,
            "cost": cost,
            "affected_characters": affected,
        },
    ))

    return events


def _apply_to_all_characters(state: GameState, augmentation_id: str) -> int:
    """Apply an augmentation's immediate stat effects to all eligible characters.

    Returns the number of characters affected.
    """
    aug = AUGMENTATIONS[augmentation_id]
    effect = aug["effect"]
    count = 0

    for char in state.characters:
        # Bots and Soulless are unaffected
        if char.sub_species == SubSpecies.SOULLESS:
            continue
        if char.char_class.value == "bot":
            continue

        if effect == "speed_boost":
            char.speed = min(char.speed + 1, 8)
        elif effect == "melee_boost":
            if "Claws (melee +0)" not in char.equipment:
                char.equipment.append("Claws (melee +0)")
        elif effect == "armor_boost":
            if "Inherent Protection (6+ save)" not in char.equipment:
                char.equipment.append("Inherent Protection (6+ save)")
        # vision_boost, reaction_reroll, initiative_reroll, loyalty_protection,
        # recovery_boost are checked dynamically during gameplay

        count += 1

    return count


def apply_augmentations_to_new_character(state: GameState, character_name: str) -> None:
    """Apply all colony augmentations to a newly created character.

    Called when a replacement character joins (step 13).
    """
    owned = get_colony_augmentations(state)
    char = None
    for c in state.characters:
        if c.name == character_name:
            char = c
            break
    if not char:
        return

    # Skip Bots and Soulless
    if char.sub_species == SubSpecies.SOULLESS or char.char_class.value == "bot":
        return

    for aug_id in owned:
        aug = AUGMENTATIONS[aug_id]
        effect = aug["effect"]
        if effect == "speed_boost":
            char.speed = min(char.speed + 1, 8)
        elif effect == "melee_boost":
            if "Claws (melee +0)" not in char.equipment:
                char.equipment.append("Claws (melee +0)")
        elif effect == "armor_boost":
            if "Inherent Protection (6+ save)" not in char.equipment:
                char.equipment.append("Inherent Protection (6+ save)")

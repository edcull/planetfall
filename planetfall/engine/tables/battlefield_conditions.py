"""Battlefield Conditions table (D100).

Rolled when setting up a mission to determine environmental modifiers
that affect combat. Conditions persist on the campaign tracking sheet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from planetfall.engine.dice import roll_d100, roll_d6


@dataclass
class BattlefieldCondition:
    """A battlefield condition affecting combat."""
    id: str
    name: str
    description: str
    visibility_limit: int = 0       # 0 = no limit; >0 = max zone range for shooting
    shooting_penalty: int = 0       # penalty to hit rolls
    movement_penalty: bool = False  # can't dash
    extra_contacts: int = 0         # additional enemy contacts
    enemy_size_mod: int = 0         # +/- to encounter size
    extra_finds_rolls: int = 0      # bonus post-mission finds rolls
    terrain_hazards: int = 0        # number of zones become impassable
    terrain_unstable: bool = False  # terrain can collapse


# D100 Master Conditions Table
BATTLEFIELD_CONDITIONS_TABLE = {
    (1, 8): BattlefieldCondition(
        id="visibility_limits",
        name="Visibility Limits",
        description="Fog, darkness, or interference limits visibility.",
        visibility_limit=1,  # Can only shoot within 1 zone
    ),
    (9, 13): BattlefieldCondition(
        id="shooting_penalty",
        name="Shooting Penalties",
        description="Atmospheric distortion makes aiming difficult.",
        shooting_penalty=1,
    ),
    (14, 19): BattlefieldCondition(
        id="movement_penalty",
        name="Movement Penalty",
        description="Heavy gravity or treacherous surfaces slow movement.",
        movement_penalty=True,
    ),
    (20, 25): BattlefieldCondition(
        id="uncertain_terrain",
        name="Uncertain Terrain",
        description="Terrain features are unreliable and may shift.",
        terrain_unstable=True,
    ),
    (26, 30): BattlefieldCondition(
        id="unstable_terrain",
        name="Unstable Terrain",
        description="Terrain may collapse — figures risk becoming casualties.",
        terrain_unstable=True,
    ),
    (31, 35): BattlefieldCondition(
        id="shifting_terrain",
        name="Shifting Terrain",
        description="Terrain features drift at the end of each round.",
        terrain_unstable=True,
    ),
    (36, 41): BattlefieldCondition(
        id="hazardous_environment",
        name="Hazardous Environment",
        description="Two terrain zones become impassable due to environmental hazards.",
        terrain_hazards=2,
    ),
    (42, 49): BattlefieldCondition(
        id="resource_rich",
        name="Resource Rich",
        description="This area is rich with recoverable materials.",
        extra_finds_rolls=1,
    ),
    (50, 55): BattlefieldCondition(
        id="heavy_scanner",
        name="Heavy Scanner Signals",
        description="Scanner picks up unusual activity — expect more contacts.",
        extra_contacts=1,
    ),
    (56, 61): BattlefieldCondition(
        id="unusual_activity",
        name="Unusual Activity Levels",
        description="Enemy activity in this area is elevated.",
        enemy_size_mod=1,
    ),
    (62, 68): BattlefieldCondition(
        id="reduced_activity",
        name="Reduced Enemy Activity",
        description="The area seems quieter than expected.",
        enemy_size_mod=-1,
    ),
    (69, 75): BattlefieldCondition(
        id="clear_skies",
        name="Clear Skies",
        description="Perfect visibility — no penalties to shooting.",
    ),
    (76, 82): BattlefieldCondition(
        id="favorable_terrain",
        name="Favorable Terrain",
        description="Good cover positions available for the colony forces.",
    ),
    (83, 88): BattlefieldCondition(
        id="scout_advantage",
        name="Scout Advantage",
        description="Scouts have mapped this area — tactical advantage.",
    ),
    (89, 94): BattlefieldCondition(
        id="elevated_positions",
        name="Elevated Positions",
        description="High ground available for defensive positioning.",
    ),
    (95, 100): BattlefieldCondition(
        id="ancient_ruins",
        name="Ancient Ruins",
        description="Pre-collapse structures provide excellent cover and may hold secrets.",
        extra_finds_rolls=1,
    ),
}


def roll_battlefield_condition() -> BattlefieldCondition:
    """Roll a random battlefield condition."""
    roll = roll_d100("Battlefield Condition")
    for (low, high), condition in BATTLEFIELD_CONDITIONS_TABLE.items():
        if low <= roll.total <= high:
            return condition
    return BattlefieldCondition(id="none", name="Normal", description="No special conditions.")


def get_or_generate_condition(
    state,
    slot_index: int,
) -> BattlefieldCondition:
    """Get a battlefield condition for a given slot, generating if empty.

    Conditions are stored in state.tracking.battlefield_conditions
    as a list of up to 10 condition dicts. Once generated, they persist.
    """
    conditions = list(state.tracking.battlefield_conditions)

    # Extend list to slot_index if needed
    while len(conditions) <= slot_index:
        conditions.append(None)

    if conditions[slot_index] is None:
        cond = roll_battlefield_condition()
        conditions[slot_index] = {
            "id": cond.id, "name": cond.name,
            "description": cond.description,
            "visibility_limit": cond.visibility_limit,
            "shooting_penalty": cond.shooting_penalty,
            "movement_penalty": cond.movement_penalty,
            "extra_contacts": cond.extra_contacts,
            "enemy_size_mod": cond.enemy_size_mod,
            "extra_finds_rolls": cond.extra_finds_rolls,
            "terrain_hazards": cond.terrain_hazards,
            "terrain_unstable": cond.terrain_unstable,
        }

    state.tracking.battlefield_conditions = conditions
    data = conditions[slot_index]
    return BattlefieldCondition(**data)


def get_mission_condition(state, turn: int) -> BattlefieldCondition:
    """Get the battlefield condition for the current mission.

    Uses turn number mod 10 as the slot index.
    """
    slot = (turn - 1) % 10
    return get_or_generate_condition(state, slot)

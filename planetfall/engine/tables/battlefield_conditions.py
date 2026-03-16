"""Battlefield Conditions — 10-slot persistent D100 encounter table.

Works like the Lifeform Encounters table: roll D100 to pick a slot,
if the slot is empty generate a new condition from the Master Condition
table (with sub-rolls for severity/triggers), if filled reuse the
existing condition.

Master Condition Table (rules pp.111-112):
  01-08  Visibility Limits       (sub-roll: variable round / fixed / variable battle)
  09-13  Shooting Penalties      (sub-roll: random round / range / terrain type)
  14-19  Movement Penalty        (sub-roll: table surface / terrain / climbing / obstacles)
  20-25  Uncertain Terrain       (add 1 uncertain feature; or Unstable if not using rule)
  26-30  Unstable Terrain        (terrain collapses on D6=1)
  31-35  Shifting Terrain        (terrain drifts 1D6" each round)
  36-41  Hazardous Environment   (2 terrain features become Impassable)
  42-49  Resource Rich           (+1 Post-Mission Finds roll)
  50-55  Heavy Scanner Signals   (+1 Contact marker)
  56-61  Unusual Activity        (sub-roll: Aggression die +1 or -1)
  62-68  Enemy Activity          (sub-roll: encounter size +1 or -1)
  69-75  Drifting Clouds         (sub-roll: safe / toxic / corrosive)
  76-82  Clear Escape Paths      (1 character escapes per round)
  83-90  Confined Spaces         (only 2 entry/exit points)
  91-100 No Conditions           (all clear)
"""

from __future__ import annotations

from planetfall.engine.dice import roll_d6, roll_d100, roll_nd6
from planetfall.engine.models import BattlefieldCondition


# D100 ranges for the 10-slot campaign conditions table
_CONDITIONS_D100_RANGES = [
    (1, 18), (19, 32), (33, 44), (45, 54), (55, 64),
    (65, 73), (74, 82), (83, 89), (90, 95), (96, 100),
]


# --- Sub-roll generators for conditions that need them ---

def _generate_visibility_limits() -> BattlefieldCondition:
    """01-08: Visibility Limits — sub-roll determines type."""
    sub = roll_d100("Visibility type").total
    if sub <= 30:
        # Variable by round: roll 1D6+8 each round
        vis = roll_d6("Initial visibility (1D6+8)").total + 8
        return BattlefieldCondition(
            id="visibility_limits", name="Visibility Limits",
            description=(
                "Vision limited by darkness, fog, or psionic interference. "
                f"Visibility changes each round (1D6+8\"). Current: {vis}\"."
            ),
            visibility_limit=vis, visibility_type="variable_round",
            effects_summary=[
                f"Visibility limit: {vis}\" (re-rolled each round as 1D6+8\")",
                "Cannot fire at or interact with targets beyond visibility limit",
            ],
        )
    elif sub <= 70:
        # Fixed: 1D6+8" for all battles with this condition
        vis = roll_d6("Fixed visibility (1D6+8)").total + 8
        return BattlefieldCondition(
            id="visibility_limits", name="Visibility Limits",
            description=(
                "Vision limited by darkness, fog, or psionic interference. "
                f"Fixed visibility limit: {vis}\"."
            ),
            visibility_limit=vis, visibility_type="fixed",
            effects_summary=[
                f"Visibility limit: {vis}\" (fixed for all battles with this condition)",
                "Cannot fire at or interact with targets beyond visibility limit",
            ],
        )
    else:
        # Variable by battle: 1D6+8" rolled each battle
        vis = roll_d6("Battle visibility (1D6+8)").total + 8
        return BattlefieldCondition(
            id="visibility_limits", name="Visibility Limits",
            description=(
                "Vision limited by darkness, fog, or psionic interference. "
                f"Visibility this battle: {vis}\" (re-rolled each battle)."
            ),
            visibility_limit=vis, visibility_type="variable_battle",
            effects_summary=[
                f"Visibility limit: {vis}\" (re-rolled each battle)",
                "Cannot fire at or interact with targets beyond visibility limit",
            ],
        )


def _generate_shooting_penalties() -> BattlefieldCondition:
    """09-13: Shooting Penalties — sub-roll determines circumstance."""
    sub = roll_d100("Shooting penalty type").total
    if sub <= 35:
        return BattlefieldCondition(
            id="shooting_penalties", name="Shooting Penalties",
            description=(
                "Atmospheric distortion affects targeting. Each round, "
                "roll D6: on 5-6, -1 to all ranged attacks that round."
            ),
            shooting_penalty=-1, shooting_circumstance="random_round",
            effects_summary=[
                "-1 to ranged attacks (when active)",
                "Each round roll D6: penalty applies on 5-6",
            ],
        )
    elif sub <= 65:
        return BattlefieldCondition(
            id="shooting_penalties", name="Shooting Penalties",
            description=(
                "Atmospheric distortion affects long-range targeting. "
                "-1 to all ranged attacks over 15\" range."
            ),
            shooting_penalty=-1, shooting_circumstance="range",
            effects_summary=[
                "-1 to all ranged attacks over 15\" range",
            ],
        )
    else:
        return BattlefieldCondition(
            id="shooting_penalties", name="Shooting Penalties",
            description=(
                "Environmental interference near certain terrain. "
                "-1 to shots originating from, targeting, or passing "
                "through a randomly selected terrain type."
            ),
            shooting_penalty=-1, shooting_circumstance="terrain_type",
            effects_summary=[
                "-1 to shots from/at/through a random terrain type",
                "Terrain type selected at battle setup",
            ],
        )


def _generate_movement_penalty() -> BattlefieldCondition:
    """14-19: Movement Penalty — sub-roll determines circumstance."""
    sub = roll_d100("Movement penalty type").total
    if sub <= 25:
        circumstance = "table_surface"
        desc_detail = "on open ground (not in terrain features)"
        effect_line = "Cannot Dash on open ground (terrain features unaffected)"
    elif sub <= 60:
        circumstance = "terrain_features"
        desc_detail = "in or on terrain features"
        effect_line = "Cannot Dash in or on terrain features"
    elif sub <= 80:
        circumstance = "climbing"
        desc_detail = "while climbing up or down"
        effect_line = "Cannot Dash while climbing"
    else:
        circumstance = "obstacles"
        desc_detail = "when crossing obstacles"
        effect_line = "Cannot Dash when crossing obstacles"

    return BattlefieldCondition(
        id="movement_penalty", name="Movement Penalty",
        description=(
            f"Treacherous conditions prevent Dashing {desc_detail}."
        ),
        movement_penalty=True, movement_circumstance=circumstance,
        effects_summary=[effect_line],
    )


def _generate_unusual_activity() -> BattlefieldCondition:
    """56-61: Unusual Activity — sub-roll determines +1 or -1 Aggression."""
    sub = roll_d100("Activity level").total
    if sub <= 55:
        mod = 1
        desc = "elevated"
    else:
        mod = -1
        desc = "reduced"

    return BattlefieldCondition(
        id="unusual_activity", name="Unusual Activity Levels",
        description=(
            f"The area has {desc} hostile activity. "
            f"Aggression die modifier: {mod:+d}."
        ),
        aggression_mod=mod,
        effects_summary=[
            f"Aggression die {mod:+d} when testing for Contacts",
        ],
    )


def _generate_enemy_activity() -> BattlefieldCondition:
    """62-68: Enemy Activity — sub-roll determines encounter size +1 or -1."""
    sub = roll_d100("Enemy activity level").total
    if sub <= 45:
        mod = -1
        desc = "Reduced"
    else:
        mod = 1
        desc = "Increased"

    return BattlefieldCondition(
        id="enemy_activity", name=f"{desc} Enemy Activity",
        description=(
            f"Enemy patrol levels are {'lower' if mod < 0 else 'higher'} "
            f"than expected. Encounter sizes {mod:+d}."
        ),
        enemy_size_mod=mod,
        effects_summary=[
            f"Tactical enemy encounter sizes {mod:+d}",
        ],
    )


def _generate_drifting_clouds() -> BattlefieldCondition:
    """69-75: Drifting Clouds — sub-roll determines cloud type."""
    sub = roll_d100("Cloud type").total
    if sub <= 70:
        cloud_type = "safe"
        type_desc = "Safe — visibility only"
        effects = [
            "3 cloud markers placed 6\" from center (2\" radius each)",
            "Cannot fire through clouds; cover within",
            "All clouds drift 1D6\" in a random direction each round",
        ]
    elif sub <= 85:
        cloud_type = "toxic"
        toxin = max(roll_nd6(2, "Toxin level (2D6 pick highest)").values)
        type_desc = f"Toxic — toxin level {toxin}"
        effects = [
            "3 cloud markers placed 6\" from center (2\" radius each)",
            "Cannot fire through clouds; cover within",
            "All clouds drift 1D6\" in a random direction each round",
            f"Toxic: non-Lifeforms in contact roll D6, {toxin}+ = Casualty/lose 1 KP",
        ]
        return BattlefieldCondition(
            id="drifting_clouds", name="Drifting Clouds",
            description=(
                f"Toxic clouds drift through the area. Toxin level: {toxin}. "
                "3 cloud markers (2\" radius), drift 1D6\" each round."
            ),
            clouds=3, cloud_type=cloud_type, cloud_toxin_level=toxin,
            effects_summary=effects,
        )
    else:
        cloud_type = "corrosive"
        type_desc = "Corrosive — +0 damage hit"
        effects = [
            "3 cloud markers placed 6\" from center (2\" radius each)",
            "Cannot fire through clouds; cover within",
            "All clouds drift 1D6\" in a random direction each round",
            "Corrosive: figures activating within a cloud take a hit (+0 damage)",
        ]

    return BattlefieldCondition(
        id="drifting_clouds", name="Drifting Clouds",
        description=(
            f"Great clouds of gas drift through the area. Type: {type_desc}. "
            "3 cloud markers (2\" radius), drift 1D6\" each round."
        ),
        clouds=3, cloud_type=cloud_type,
        effects_summary=effects,
    )


# --- Master Condition Generation Table ---

# Maps D100 range to a generator function or a static BattlefieldCondition.
# Entries with sub-rolls use functions; simple entries use static instances.

_MASTER_CONDITION_TABLE: dict[tuple[int, int], BattlefieldCondition | callable] = {
    (1, 8): _generate_visibility_limits,
    (9, 13): _generate_shooting_penalties,
    (14, 19): _generate_movement_penalty,
    (20, 25): BattlefieldCondition(
        id="uncertain_terrain", name="Uncertain Terrain",
        description=(
            "Long-range scans are unreliable. Add 1 additional Uncertain "
            "terrain feature. If not using that optional rule, treat as "
            "Unstable Terrain instead."
        ),
        terrain_unstable=True,
        effects_summary=[
            "+1 Uncertain terrain feature at setup",
            "(If not using Uncertain Terrain rule: treat as Unstable Terrain)",
        ],
    ),
    (26, 30): BattlefieldCondition(
        id="unstable_terrain", name="Unstable Terrain",
        description=(
            "Seemingly solid features are extremely unstable. A random "
            "terrain type is selected; when figures move adjacent/on or "
            "are fired upon while on it, D6=1 collapses the feature."
        ),
        terrain_unstable=True,
        effects_summary=[
            "Random terrain type selected at setup",
            "D6 when moving adjacent/on or firing at figures on feature",
            "On D6=1: feature removed, figures knocked Sprawling",
        ],
    ),
    (31, 35): BattlefieldCondition(
        id="shifting_terrain", name="Shifting Terrain",
        description=(
            "Terrain features drift 1D6\" in a random direction at the "
            "end of each round. Figures on features roll 4+ or Sprawling."
        ),
        shifting_terrain=True,
        effects_summary=[
            "End of each round: random terrain moves 1D6\" random direction",
            "Figures on moving terrain: D6 roll, 4+ or knocked Sprawling",
            "Features stop if they would collide",
        ],
    ),
    (36, 41): BattlefieldCondition(
        id="hazardous_environment", name="Hazardous Environment",
        description=(
            "Two randomly selected terrain features become Impassable "
            "due to environmental hazards."
        ),
        terrain_hazards=2,
        effects_summary=[
            "2 random terrain features become Impassable",
        ],
    ),
    (42, 49): BattlefieldCondition(
        id="resource_rich", name="Resource Rich",
        description=(
            "This area is rich with recoverable materials. If you win "
            "the mission, roll one additional time on the Post-Mission "
            "Finds table."
        ),
        extra_finds_rolls=1,
        effects_summary=[
            "+1 Post-Mission Finds roll on victory",
        ],
    ),
    (50, 55): BattlefieldCondition(
        id="heavy_scanner_signals", name="Heavy Scanner Signals",
        description=(
            "Unusual scanner readings in the area. If the mission uses "
            "Contacts, place one additional Contact marker."
        ),
        extra_contacts=1,
        effects_summary=[
            "+1 additional Contact marker at setup",
        ],
    ),
    (56, 61): _generate_unusual_activity,
    (62, 68): _generate_enemy_activity,
    (69, 75): _generate_drifting_clouds,
    (76, 82): BattlefieldCondition(
        id="clear_escape_paths", name="Clear Escape Paths",
        description=(
            "Once per battle round, you may select any one character "
            "that escapes the battle as if they moved off a battlefield edge."
        ),
        free_escape=True,
        effects_summary=[
            "Once per round: 1 character can escape as if moving off-table",
        ],
    ),
    (83, 90): BattlefieldCondition(
        id="confined_spaces", name="Confined Spaces",
        description=(
            "Randomly select two points on the battlefield edge. The "
            "table can only be entered or exited at these two points."
        ),
        confined_exits=2,
        effects_summary=[
            "Only 2 entry/exit points on the battlefield edge",
        ],
    ),
    (91, 100): BattlefieldCondition(
        id="no_conditions", name="No Conditions",
        description="All clear! No special conditions apply.",
        no_effect=True,
        effects_summary=[],
    ),
}

# Legacy alias
BATTLEFIELD_CONDITIONS_TABLE = _MASTER_CONDITION_TABLE


def _roll_generation_table() -> BattlefieldCondition:
    """Roll D100 on the Master Condition table and resolve sub-rolls."""
    roll = roll_d100("Master Condition Generation")
    for (low, high), entry in _MASTER_CONDITION_TABLE.items():
        if low <= roll.total <= high:
            if callable(entry):
                return entry()
            # Static entry — return a copy so mutations don't affect the template
            return entry.model_copy()
    return BattlefieldCondition(
        id="no_conditions", name="No Conditions",
        description="All clear! No special conditions apply.",
        no_effect=True,
    )


def _condition_to_model(cond: BattlefieldCondition | dict) -> BattlefieldCondition:
    """Ensure a BattlefieldCondition is a proper Pydantic model instance."""
    if isinstance(cond, dict):
        return BattlefieldCondition(**cond)
    return cond


def get_mission_condition(state, turn: int = 0) -> BattlefieldCondition:
    """Roll D100 on the campaign conditions table and return a condition.

    Works like the lifeform encounters table:
    1. Roll D100 to determine which of the 10 slots is hit
    2. If the slot is empty, generate a new condition and store it
    3. If the slot is filled, return the existing condition

    The turn parameter is accepted for backwards compatibility but ignored.
    """
    conditions = list(state.tracking.battlefield_conditions)

    # Roll D100 to pick a slot
    d100 = roll_d100("Conditions table").total
    slot_idx = 0
    for i, (low, high) in enumerate(_CONDITIONS_D100_RANGES):
        if low <= d100 <= high:
            slot_idx = i
            break

    # Extend list to have enough entries
    while len(conditions) <= slot_idx:
        conditions.append(None)

    if conditions[slot_idx] is None:
        # Empty slot — generate from Master Condition table
        cond = _roll_generation_table()
        conditions[slot_idx] = cond
    else:
        # Ensure legacy dicts are converted to models
        conditions[slot_idx] = _condition_to_model(conditions[slot_idx])

    state.tracking.battlefield_conditions = conditions
    return conditions[slot_idx]


# Keep legacy function names working
def get_or_generate_condition(state, slot_index: int) -> BattlefieldCondition:
    """Legacy wrapper — use get_mission_condition instead."""
    return get_mission_condition(state)


def roll_battlefield_condition() -> BattlefieldCondition:
    """Roll a random condition from the generation table (no persistence)."""
    return _roll_generation_table()


# --- Uncertain Terrain Features D100 Table (rules p.137) ---

UNCERTAIN_TERRAIN_TABLE: dict[tuple[int, int], dict] = {
    (1, 15): {
        "id": "plant_growths",
        "name": "Plant Growths",
        "description": "Plants that do not inhibit movement but provide cover.",
        "terrain": "light_cover",
        "difficult": False,
    },
    (16, 30): {
        "id": "scatter_terrain",
        "name": "Cluster of Scatter Terrain",
        "description": "3-5 pieces of scatter terrain.",
        "terrain": "light_cover",
        "difficult": False,
    },
    (31, 45): {
        "id": "heavy_growth",
        "name": "Heavy Growth",
        "description": "Area terrain that provides cover (e.g. forest).",
        "terrain": "heavy_cover",
        "difficult": False,
    },
    (46, 50): {
        "id": "heavy_growth_concerning",
        "name": "Heavy Growth (Concerning)",
        "description": "Area terrain with cover. Place a Contact marker in the center.",
        "terrain": "heavy_cover",
        "difficult": False,
        "spawn_contact": True,
    },
    (51, 55): {
        "id": "heavy_growth_promising",
        "name": "Heavy Growth (Promising)",
        "description": "Area terrain with cover. On D6=6, gain a Post-Mission Find.",
        "terrain": "heavy_cover",
        "difficult": False,
        "find_on_6": True,
    },
    (56, 65): {
        "id": "difficult_going",
        "name": "Difficult Going",
        "description": "Difficult ground; does not affect visibility.",
        "terrain": "open",
        "difficult": True,
    },
    (66, 70): {
        "id": "difficult_going_concerning",
        "name": "Difficult Going (Concerning)",
        "description": "Difficult ground. Place a Contact marker in the center.",
        "terrain": "open",
        "difficult": True,
        "spawn_contact": True,
    },
    (71, 75): {
        "id": "difficult_going_promising",
        "name": "Difficult Going (Promising)",
        "description": "Difficult ground. On D6=6, gain a Post-Mission Find.",
        "terrain": "open",
        "difficult": True,
        "find_on_6": True,
    },
    (76, 85): {
        "id": "difficult_going_dense",
        "name": "Difficult Going (Dense)",
        "description": "Cover and difficult ground (e.g. thick forest/jungle).",
        "terrain": "heavy_cover",
        "difficult": True,
    },
    (86, 95): {
        "id": "high_ground",
        "name": "High Ground",
        "description": "Hill or slope.",
        "terrain": "high_ground",
        "difficult": False,
    },
    (96, 100): {
        "id": "terrain_block",
        "name": "Terrain Block",
        "description": "Impassable block feature (e.g. boulders).",
        "terrain": "impassable",
        "difficult": False,
    },
}


def roll_uncertain_terrain() -> dict:
    """Roll D100 on the Uncertain Terrain Features table (rules p.137).

    Returns a dict with id, name, description, terrain type, and flags.
    """
    roll = roll_d100("Uncertain Terrain Feature")
    for (low, high), entry in UNCERTAIN_TERRAIN_TABLE.items():
        if low <= roll.total <= high:
            return {**entry, "roll": roll.total}
    # Fallback
    return {
        "id": "plant_growths", "name": "Plant Growths",
        "description": "Plants that provide cover.",
        "terrain": "light_cover", "difficult": False, "roll": roll.total,
    }

"""Battlefield Conditions — Campaign Condition table and Master Condition table.

The campaign maintains a 10-slot condition table. Each slot starts blank.
When a mission calls for a condition, roll D100 on the Campaign table.
If the slot is blank, roll on the Master table to fill it.
"""

from planetfall.engine.dice import RandomTable, TableEntry

# Campaign Condition table: maps D100 roll to slot number (1-10)
CAMPAIGN_CONDITION_SLOTS = {
    (1, 15): 1,
    (16, 30): 2,
    (31, 42): 3,
    (43, 52): 4,
    (53, 62): 5,
    (63, 72): 6,
    (73, 82): 7,
    (83, 90): 8,
    (91, 95): 9,
    (96, 100): 10,
}


def lookup_condition_slot(roll: int) -> int:
    """Given a D100 roll, return the condition slot number (1-10)."""
    for (low, high), slot in CAMPAIGN_CONDITION_SLOTS.items():
        if low <= roll <= high:
            return slot
    return 1


# Master Condition table (D100) — rolled to fill a blank slot
MASTER_CONDITION_TABLE = RandomTable(
    name="Master Battlefield Conditions",
    dice_type="d100",
    entries=[
        TableEntry(
            low=1, high=8,
            result_id="visibility_limits",
            description=(
                "Visibility limits: Vision limited by darkness, fog, or psionic "
                "interference. Roll D100: 01-30 Variable by round (1D6+8\" each round), "
                "31-70 Fixed (1D6+8\" for all battles), 71-00 Variable by battle "
                "(1D6+8\" rolled per battle)."
            ),
            effects={"visibility_limit": True, "sub_roll": "d100"},
        ),
        TableEntry(
            low=9, high=13,
            result_id="shooting_penalties",
            description=(
                "Shooting penalties: -1 to all ranged attacks in certain "
                "circumstances. Roll D100: 01-35 Random by round (D6, 5-6 applies), "
                "36-65 Range (over 15\"), 66-00 Certain terrain types."
            ),
            effects={"shooting_penalty": -1, "sub_roll": "d100"},
        ),
        TableEntry(
            low=14, high=19,
            result_id="movement_penalty",
            description=(
                "Movement penalty: Cannot Dash under certain circumstances. "
                "Roll D100: 01-25 Table surface (not in terrain), "
                "26-60 Terrain features, 61-80 Climbing, "
                "81-00 Crossing obstacles."
            ),
            effects={"no_dash": True, "sub_roll": "d100"},
        ),
        TableEntry(
            low=20, high=25,
            result_id="uncertain_terrain",
            description=(
                "Uncertain terrain features: If using optional rule, add 1 "
                "additional Uncertain feature. Otherwise treat as Unstable Terrain."
            ),
            effects={"extra_uncertain_feature": 1},
        ),
        TableEntry(
            low=26, high=30,
            result_id="unstable_terrain",
            description=(
                "Unstable terrain: Randomly select a terrain type. Each time "
                "a figure moves adjacent/on or is fired upon while on feature, "
                "roll D6. On 1, feature collapses (removed), figures Sprawling."
            ),
            effects={"unstable_terrain": True},
        ),
        TableEntry(
            low=31, high=35,
            result_id="shifting_terrain",
            description=(
                "Shifting terrain: End of each round, random terrain feature "
                "moves 1D6\" random direction. Figures on it roll 4+ or Sprawling. "
                "Features stop if they would collide."
            ),
            effects={"shifting_terrain": True},
        ),
        TableEntry(
            low=36, high=41,
            result_id="hazardous_environment",
            description=(
                "Hazardous environment: Randomly select two terrain features "
                "which become Impassable."
            ),
            effects={"impassable_features": 2},
        ),
        TableEntry(
            low=42, high=49,
            result_id="resource_rich",
            description=(
                "Resource rich: If you win the mission, roll one additional "
                "time on the Post-Mission Finds table."
            ),
            effects={"extra_find_roll": 1},
        ),
        TableEntry(
            low=50, high=55,
            result_id="heavy_scanner_signals",
            description=(
                "Heavy scanner signals: If the mission uses Contacts, place "
                "one additional Contact marker initially."
            ),
            effects={"extra_contacts": 1},
        ),
        TableEntry(
            low=56, high=61,
            result_id="unusual_activity",
            description=(
                "Unusual activity levels: If using Contacts, roll D100. "
                "01-55: Aggression die +1. 56-00: Aggression die -1."
            ),
            effects={"aggression_modifier": True, "sub_roll": "d100"},
        ),
        TableEntry(
            low=62, high=68,
            result_id="enemy_activity",
            description=(
                "Enemy activity: Affects encounter size for Tactical Enemies. "
                "Roll D100: 01-45 Encounter size -1. 46-00 Encounter size +1."
            ),
            effects={"encounter_size_modifier": True, "sub_roll": "d100"},
        ),
        TableEntry(
            low=69, high=75,
            result_id="drifting_clouds",
            description=(
                "Drifting clouds: Place 3 cloud markers 6\" from center. "
                "2\" radius, cannot fire through; count as cover within. "
                "Drift 1D6\" same direction each round. Roll D100: "
                "01-70 Safe, 71-85 Toxic (2D6 pick highest for toxin level), "
                "86-00 Corrosive (+0 damage hit when activating within)."
            ),
            effects={"clouds": 3, "sub_roll": "d100"},
        ),
        TableEntry(
            low=76, high=82,
            result_id="clear_escape",
            description=(
                "Clear escape paths: Once per battle round, select one "
                "character that escapes as if they moved off a battlefield edge."
            ),
            effects={"free_escape": 1},
        ),
        TableEntry(
            low=83, high=90,
            result_id="confined_spaces",
            description=(
                "Confined spaces: Randomly select 2 points on the battlefield "
                "edge. Table can only be entered or exited at these 2 points."
            ),
            effects={"exit_points": 2},
        ),
        TableEntry(
            low=91, high=100,
            result_id="no_conditions",
            description="No Conditions: All clear! No special conditions apply.",
            effects={},
        ),
    ],
)

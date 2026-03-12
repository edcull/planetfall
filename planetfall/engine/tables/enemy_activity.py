"""Enemy Activity Table (D100) - Campaign Turn Step 4."""

from planetfall.engine.dice import RandomTable, TableEntry

ENEMY_ACTIVITY_TABLE = RandomTable(
    name="Enemy Activity",
    dice_type="d100",
    entries=[
        TableEntry(
            low=1, high=25,
            result_id="patrol",
            description=(
                "The enemy is sending out patrols near their controlled zones. "
                "You may choose to play a Strike Mission this turn to track "
                "down an enemy Leader and gain 1 Enemy Information."
            ),
            effects={"mission_option": "strike", "enemy_info_reward": 1},
        ),
        TableEntry(
            low=26, high=35,
            result_id="relocate",
            description=(
                "The enemy is shifting their deployments. Randomly pick an "
                "enemy-occupied sector. They move to a random adjacent "
                "unoccupied sector. If the selected sector is your colony, "
                "they launch a Raid and move in the opposite direction."
            ),
            effects={"relocate": True},
        ),
        TableEntry(
            low=36, high=65,
            result_id="occupy",
            description=(
                "The enemy expands into a random adjacent sector. If this "
                "would be your colony, treat as a Raid. If another enemy's "
                "sector, randomly determine who gains control."
            ),
            effects={"occupy": True},
        ),
        TableEntry(
            low=66, high=75,
            result_id="rapid_expansion",
            description=(
                "As Occupy, but two adjacent sectors are occupied."
            ),
            effects={"occupy": True, "extra_sectors": 2},
        ),
        TableEntry(
            low=76, high=90,
            result_id="attack",
            description=(
                "The enemy launches an attack on you. Play the Pitched Battle "
                "mission this campaign turn. If you lose, you take damage as "
                "per Raid."
            ),
            effects={"forced_mission": "pitched_battle"},
        ),
        TableEntry(
            low=91, high=100,
            result_id="raid",
            description=(
                "The enemy launches a sneak attack on your colony. You suffer "
                "Colony Damage equal to the number of map sectors this enemy "
                "occupies +1. Colony Defenses roll D6s; each 4+ negates a "
                "point of damage."
            ),
            effects={"raid": True},
        ),
    ],
)

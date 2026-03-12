"""Uncertain Terrain Features table (D100).

Revealed when within 9" of crew or within 18" with LoS.
"""

from planetfall.engine.dice import RandomTable, TableEntry

UNCERTAIN_TERRAIN_TABLE = RandomTable(
    name="Uncertain Terrain Features",
    dice_type="d100",
    entries=[
        TableEntry(
            low=1, high=15,
            result_id="plant_growths",
            description=(
                "Plant growths: Does not inhibit movement, but figures "
                "within the feature count as being in cover."
            ),
            effects={"terrain_type": "light_cover"},
        ),
        TableEntry(
            low=16, high=30,
            result_id="scatter_terrain",
            description="Cluster of scatter terrain: 3-5 pieces of Scatter.",
            effects={"terrain_type": "scatter"},
        ),
        TableEntry(
            low=31, high=45,
            result_id="heavy_growth",
            description=(
                "Heavy growth: Area terrain that provides cover. "
                "Example: Forest."
            ),
            effects={"terrain_type": "heavy_cover"},
        ),
        TableEntry(
            low=46, high=50,
            result_id="heavy_growth_concerning",
            description=(
                "Heavy growth (concerning): Area terrain that provides cover. "
                "If the mission uses Contacts, place one marker in the center."
            ),
            effects={"terrain_type": "heavy_cover", "spawn_contact": True},
        ),
        TableEntry(
            low=51, high=55,
            result_id="heavy_growth_promising",
            description=(
                "Heavy growth (promising): Area terrain that provides cover. "
                "If a squad member enters, roll 1D6. On 6, roll once on "
                "Post-Mission Finds table."
            ),
            effects={"terrain_type": "heavy_cover", "find_chance": True},
        ),
        TableEntry(
            low=56, high=65,
            result_id="difficult_going",
            description=(
                "Difficult going: Difficult ground; does not affect "
                "visibility. Example: Swamp."
            ),
            effects={"terrain_type": "difficult"},
        ),
        TableEntry(
            low=66, high=70,
            result_id="difficult_concerning",
            description=(
                "Difficult going (concerning): Difficult ground. "
                "If the mission uses Contacts, place one marker in center."
            ),
            effects={"terrain_type": "difficult", "spawn_contact": True},
        ),
        TableEntry(
            low=71, high=75,
            result_id="difficult_promising",
            description=(
                "Difficult going (promising): Difficult ground. "
                "If a squad member enters, roll 1D6. On 6, roll once on "
                "Post-Mission Finds table."
            ),
            effects={"terrain_type": "difficult", "find_chance": True},
        ),
        TableEntry(
            low=76, high=85,
            result_id="difficult_dense",
            description=(
                "Difficult going (dense): Area feature that provides cover "
                "and acts as Difficult ground. Example: Thick forest."
            ),
            effects={"terrain_type": "heavy_cover_difficult"},
        ),
        TableEntry(
            low=86, high=95,
            result_id="high_ground",
            description="High ground: Hill or slope.",
            effects={"terrain_type": "high_ground"},
        ),
        TableEntry(
            low=96, high=100,
            result_id="terrain_block",
            description=(
                "Terrain block: Cannot be entered but can be climbed. "
                "Example: Boulders."
            ),
            effects={"terrain_type": "impassable_climbable"},
        ),
    ],
)

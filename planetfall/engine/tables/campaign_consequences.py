"""Campaign Consequences table (D100) — rolled after losing a Pitched Battle."""

from planetfall.engine.dice import RandomTable, TableEntry

CAMPAIGN_CONSEQUENCES_TABLE = RandomTable(
    name="Campaign Consequences",
    dice_type="d100",
    entries=[
        TableEntry(
            low=1, high=20,
            result_id="colony_damage",
            description=(
                "Colony damage: Reduce Integrity by 1D6+2 points. "
                "If you have Colony Defenses, roll 1D6 for each point, "
                "4+ negates it."
            ),
            effects={"integrity_damage": "1d6+2", "defenses_mitigate": True},
        ),
        TableEntry(
            low=21, high=40,
            result_id="interruption",
            description=(
                "Interruption: All building and research projects that are "
                "only partially completed lose all progress."
            ),
            effects={"reset_partial_projects": True},
        ),
        TableEntry(
            low=41, high=60,
            result_id="morale_loss",
            description=(
                "Morale loss: Reduce Morale by 1D6+2 points. "
                "If you have Colony Defenses, roll 1D6 for each point, "
                "4+ negates it."
            ),
            effects={"morale_damage": "1d6+2", "defenses_mitigate": True},
        ),
        TableEntry(
            low=61, high=80,
            result_id="attrition",
            description=(
                "Attrition: Remove 2 grunts from your Colony Tracking Sheet."
            ),
            effects={"lose_grunts": 2},
        ),
        TableEntry(
            low=81, high=100,
            result_id="prolonged_battle",
            description=(
                "Prolonged battle: 2 random characters on your roster must "
                "roll on the Post-Battle Injury table. Characters injured "
                "during the mission cannot be selected."
            ),
            effects={"random_injuries": 2},
        ),
    ],
)

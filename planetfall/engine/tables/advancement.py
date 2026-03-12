"""Advancement Table (D100) - Campaign Turn Step 10."""

from planetfall.engine.dice import RandomTable, TableEntry

ADVANCEMENT_TABLE = RandomTable(
    name="Advancement",
    dice_type="d100",
    entries=[
        TableEntry(
            low=1, high=15,
            result_id="speed",
            description=(
                "Speed increase (max 8\"). First time +2\", subsequent +1\"."
            ),
            effects={
                "stat": "speed",
                "first_bonus": 2,
                "subsequent_bonus": 1,
                "max": 8,
            },
        ),
        TableEntry(
            low=16, high=35,
            result_id="reactions",
            description=(
                "Reactions increase (max 6). +1 each time. "
                "Scientists may trade this for Savvy."
            ),
            effects={
                "stat": "reactions",
                "bonus": 1,
                "max": 6,
                "trade_class": "scientist",
                "trade_stat": "savvy",
            },
        ),
        TableEntry(
            low=36, high=55,
            result_id="combat_skill",
            description=(
                "Combat Skill increase (max +5). +1 each time. "
                "Scouts may trade this for Reactions."
            ),
            effects={
                "stat": "combat_skill",
                "bonus": 1,
                "max": 5,
                "trade_class": "scout",
                "trade_stat": "reactions",
            },
        ),
        TableEntry(
            low=56, high=75,
            result_id="toughness",
            description="Toughness increase (max 6). +1 each time.",
            effects={
                "stat": "toughness",
                "bonus": 1,
                "max": 6,
            },
        ),
        TableEntry(
            low=76, high=90,
            result_id="savvy",
            description=(
                "Savvy increase (max +5). +1 each time. "
                "Troopers may trade this for Toughness."
            ),
            effects={
                "stat": "savvy",
                "bonus": 1,
                "max": 5,
                "trade_class": "trooper",
                "trade_stat": "toughness",
            },
        ),
        TableEntry(
            low=91, high=100,
            result_id="kill_points",
            description="Kill Point increase (max 3). +1 KP.",
            effects={
                "stat": "kill_points",
                "bonus": 1,
                "max": 3,
            },
        ),
    ],
)

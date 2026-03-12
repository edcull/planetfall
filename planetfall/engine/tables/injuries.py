"""Injury Tables - Campaign Turn Step 9."""

from planetfall.engine.dice import RandomTable, TableEntry

CHARACTER_INJURY_TABLE = RandomTable(
    name="Character Injuries",
    dice_type="d100",
    entries=[
        TableEntry(
            low=1, high=20,
            result_id="dead",
            description="The character is gone.",
            effects={"dead": True},
        ),
        TableEntry(
            low=21, high=30,
            result_id="seriously_wounded",
            description="The character must recover for 5 campaign turns.",
            effects={"sick_bay_turns": 5},
        ),
        TableEntry(
            low=31, high=45,
            result_id="moderately_wounded",
            description="The character must recover for 4 campaign turns.",
            effects={"sick_bay_turns": 4},
        ),
        TableEntry(
            low=46, high=60,
            result_id="lightly_wounded",
            description="The character must recover for 2 campaign turns.",
            effects={"sick_bay_turns": 2},
        ),
        TableEntry(
            low=61, high=95,
            result_id="okay",
            description="The character is okay.",
        ),
        TableEntry(
            low=96, high=100,
            result_id="hard_knocks",
            description=(
                "The character is okay and gains +1 XP as they reflect "
                "on their experiences."
            ),
            effects={"xp": 1},
        ),
    ],
)

GRUNT_INJURY_TABLE = RandomTable(
    name="Grunt Injuries",
    dice_type="d6",
    entries=[
        TableEntry(
            low=1, high=2,
            result_id="permanent_casualty",
            description=(
                "They have either died, their injuries were so severe they "
                "cannot continue, or they opt to retire."
            ),
            effects={"dead": True},
        ),
        TableEntry(
            low=3, high=6,
            result_id="okay",
            description="They are okay and recover in time for the next mission.",
        ),
    ],
)

"""Mission-specific objective tables.

Skirmish Objective table (D6) and Investigation Discovery table (D6).
"""

from planetfall.engine.dice import RandomTable, TableEntry

# D6 Skirmish Objective table — rolled twice per skirmish mission
SKIRMISH_OBJECTIVE_TABLE = RandomTable(
    name="Skirmish Objective",
    dice_type="d6",
    entries=[
        TableEntry(
            low=1, high=1, result_id="secure",
            description=(
                "Secure: End a battle round with only your characters "
                "within 3\" of the Objective."
            ),
        ),
        TableEntry(
            low=2, high=2, result_id="sweep",
            description="Sweep: Moving into contact completes the objective.",
        ),
        TableEntry(
            low=3, high=3, result_id="destroy",
            description=(
                "Destroy: Select one character to carry demo charges — they "
                "auto-destroy on contact. Otherwise, base contact + roll "
                "1D6 + melee damage, 6+ destroys."
            ),
        ),
        TableEntry(
            low=4, high=4, result_id="search",
            description=(
                "Search: Take an action within 2\" and roll 1D6+Savvy. "
                "6+ completes the objective."
            ),
        ),
        TableEntry(
            low=5, high=5, result_id="deliver",
            description=(
                "Deliver: Select 2 characters each carrying an item. Either "
                "must move into base contact with objective. If 2 Deliver "
                "objectives, 4 characters carry items usable for either."
            ),
        ),
        TableEntry(
            low=6, high=6, result_id="retrieve",
            description=(
                "Retrieve: Move into base contact to retrieve the item. "
                "It must then be carried off the table."
            ),
        ),
    ],
)

# D6 Investigation Discovery table — rolled when investigating a marker
INVESTIGATION_DISCOVERY_TABLE = RandomTable(
    name="Investigation Discovery",
    dice_type="d6",
    entries=[
        TableEntry(
            low=1, high=1, result_id="enemy",
            description=(
                "Enemy sentries! Place a Sleeper in the most distant "
                "terrain feature the investigating figure can see."
            ),
            effects={"spawn_sleeper": True},
        ),
        TableEntry(
            low=2, high=2, result_id="rewards",
            description=(
                "Rewards: Tag location for extraction. Roll once on "
                "Post-Mission Finds table after the mission."
            ),
            effects={"post_mission_find": 1},
        ),
        TableEntry(
            low=3, high=3, result_id="contact",
            description=(
                "Lifeforms lurking. Place a Contact in the terrain feature "
                "closest to where the Discovery marker was."
            ),
            effects={"spawn_contact": True},
        ),
        TableEntry(
            low=4, high=4, result_id="action_required",
            description=(
                "Action required: Character must move into base contact and "
                "take an action. Roll 1D6+Savvy; 5+ earns 1 Raw Materials."
            ),
            effects={"savvy_check": 5, "reward_rm": 1},
        ),
        TableEntry(
            low=5, high=6, result_id="data",
            description=(
                "Mission Data: Character must move into base contact and "
                "spend an action to collect. Data is transmitted to colony "
                "for post-battle analysis."
            ),
            effects={"mission_data": 1},
        ),
    ],
)

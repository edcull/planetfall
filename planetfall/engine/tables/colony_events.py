"""Colony Events Table (D100) - Campaign Turn Step 5."""

from planetfall.engine.dice import RandomTable, TableEntry

COLONY_EVENTS_TABLE = RandomTable(
    name="Colony Events",
    dice_type="d100",
    entries=[
        TableEntry(
            low=1, high=5,
            result_id="research_breakthrough",
            description=(
                "One of the researchers had an epiphany that will solve a "
                "stubborn problem. Receive 2 Research Points."
            ),
            effects={"research_points": 2},
        ),
        TableEntry(
            low=6, high=10,
            result_id="catastrophic_malfunction",
            description=(
                "A major accident. You suffer 1 Colony Damage that cannot be "
                "mitigated. Adjust Colony Morale by -1."
            ),
            effects={"colony_damage": 1, "morale": -1},
        ),
        TableEntry(
            low=11, high=15,
            result_id="rapid_construction",
            description=(
                "Streamlining the process has made great strides. "
                "Receive 2 Building Points."
            ),
            effects={"build_points": 2},
        ),
        TableEntry(
            low=16, high=20,
            result_id="public_relations_demand",
            description=(
                "Colony administration needs to put its best foot forward. "
                "Select a character who will not be able to participate in a "
                "mission this campaign turn. If you choose not to, adjust "
                "Colony Morale by -2."
            ),
            effects={"bench_character": True, "decline_morale": -2},
        ),
        TableEntry(
            low=21, high=25,
            result_id="specialist_training",
            description=(
                "You may either add a new character to your roster if you "
                "have a vacancy OR grant +3 XP to an existing character."
            ),
            effects={"new_character_or_xp": 3},
        ),
        TableEntry(
            low=26, high=30,
            result_id="scientific_dead_end",
            description=(
                "A promising hypothesis turns out to lead nowhere. Your next "
                "3 Research Points earned are wasted."
            ),
            effects={"rp_wasted": 3},
        ),
        TableEntry(
            low=31, high=35,
            result_id="new_scout_recruits",
            description=(
                "A recruiting campaign has allowed the scout service to expand "
                "operations. You may carry out a free Scout action."
            ),
            effects={"free_scout": True},
        ),
        TableEntry(
            low=36, high=40,
            result_id="gold_rush",
            description=(
                "Colonists exploring have unveiled promising resource caches. "
                "Select 2 random sectors: If unexplored or previously "
                "Exploited, roll to generate Resource and Hazard values. If "
                "Explored but not Exploited, increase Resource value by +1."
            ),
            effects={"gold_rush_sectors": 2},
        ),
        TableEntry(
            low=41, high=45,
            result_id="colonists_find",
            description=(
                "Unconfirmed reports indicate something of particular interest. "
                "Receive 1 Ancient Sign."
            ),
            effects={"ancient_signs": 1},
        ),
        TableEntry(
            low=46, high=50,
            result_id="hostile_wildlife",
            description=(
                "The colonists are complaining about the hazards in the field. "
                "Unless you play a Patrol Mission this turn, adjust Colony "
                "Morale by -2."
            ),
            effects={"mission_required": "patrol", "decline_morale": -2},
        ),
        TableEntry(
            low=51, high=55,
            result_id="new_training_program",
            description=(
                "The core team undergoes expanded and refresher training. "
                "Every character on your roster receives 1 XP. You may also "
                "add an additional grunt."
            ),
            effects={"all_xp": 1, "grunt": 1},
        ),
        TableEntry(
            low=56, high=60,
            result_id="experimental_medicine",
            description=(
                "A new drug from local flora is showing promising results. "
                "Select a character recovering from injuries and reduce their "
                "recovery time by 2 turns. If fully recovered, they can act "
                "normally. Increase Colony Morale by +1."
            ),
            effects={"heal_turns": 2, "morale": 1},
        ),
        TableEntry(
            low=61, high=65,
            result_id="spare_parts_efficiency",
            description=(
                "The repair crews have improved their recovery program. Any "
                "damaged bots are repaired immediately. Also, repair 2 points "
                "of Colony Damage."
            ),
            effects={"repair_bots": True, "colony_repair": 2},
        ),
        TableEntry(
            low=66, high=70,
            result_id="report_on_progress",
            description=(
                "The report to Unity headquarters highlights the hard work of "
                "a crew member. Select one character to earn 1D6 XP. Increase "
                "Colony Morale by +1."
            ),
            effects={"character_xp_d6": True, "morale": 1},
        ),
        TableEntry(
            low=71, high=75,
            result_id="animal_migrations",
            description=(
                "The wildlife migrates according to changes in weather. Erase "
                "a random existing entry from your Lifeform Encounter Table. "
                "It is filled again when you roll that entry again."
            ),
            effects={"erase_lifeform": True},
        ),
        TableEntry(
            low=76, high=80,
            result_id="hostile_virus",
            description=(
                "A particularly virulent infection has bypassed containment. "
                "Roll D6 for each character; natural 1 = infected. For each "
                "infected, pick a random non-infected and roll again. Continue "
                "until no more 1s. Each infected character spends 1D3 turns in "
                "Sick Bay. Adjust Colony Morale by -2."
            ),
            effects={"virus_check": True, "morale": -2},
        ),
        TableEntry(
            low=81, high=85,
            result_id="changing_climate",
            description=(
                "Planetary phenomena change unpredictably. Erase a random "
                "existing entry from your Campaign Conditions table. Filled "
                "again when rolled."
            ),
            effects={"erase_condition": True},
        ),
        TableEntry(
            low=86, high=90,
            result_id="colony_unrest",
            description=(
                "Widespread protests break out due to dissatisfaction. "
                "Adjust Colony Morale by -3."
            ),
            effects={"morale": -3},
        ),
        TableEntry(
            low=91, high=95,
            result_id="supply_ship",
            description=(
                "A Unity supply ship is en route. Select either Research or "
                "Build Points as priority, then roll 2D6. You receive the "
                "highest die for priority and lowest for the other. Add +1 "
                "grunt to your roster."
            ),
            effects={"supply_ship": True, "grunt": 1},
        ),
        TableEntry(
            low=96, high=100,
            result_id="foreboding",
            description=(
                "You realize that you are ultimately on your own out here. "
                "You cannot use any Story Points for the rest of this "
                "campaign turn."
            ),
            effects={"no_story_points": True},
        ),
    ],
)

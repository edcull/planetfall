"""Scout Discovery Table (D100) - Campaign Turn Step 3."""

from planetfall.engine.dice import RandomTable, TableEntry

SCOUT_DISCOVERY_TABLE = RandomTable(
    name="Scout Discovery",
    dice_type="d100",
    entries=[
        TableEntry(
            low=1, high=10,
            result_id="routine_trip",
            description="The scouts find nothing at all.",
        ),
        TableEntry(
            low=11, high=20,
            result_id="good_practice",
            description=(
                "The scouts find nothing, but it is a good opportunity to "
                "rehearse the basics. If a scout was assigned, they receive +2 XP."
            ),
            effects={"scout_xp": 2},
        ),
        TableEntry(
            low=21, high=25,
            result_id="sos_signal",
            description=(
                "The scouts report a distress signal. This campaign turn you "
                "have the choice of playing a Rescue Mission. If you do not, "
                "Colony Morale drops by -3."
            ),
            effects={"mission_option": "rescue", "decline_morale": -3},
        ),
        TableEntry(
            low=26, high=30,
            result_id="scout_down",
            description=(
                "The scout vehicle crashes. If you assigned a scout, they need "
                "rescue. You can opt to have them escape on foot (roll on injury "
                "table, +2 XP if survive), or play the Scout Down! mission. If "
                "no scout assigned, the crash left no survivors."
            ),
            effects={"scout_xp_survive": 2},
        ),
        TableEntry(
            low=31, high=60,
            result_id="exploration_report",
            description=(
                "Select any sector that has not yet been Explored and generate "
                "Resource and Hazard levels."
            ),
            effects={"explore_sector": True},
        ),
        TableEntry(
            low=61, high=70,
            result_id="recon_patrol",
            description=(
                "If there are Tactical Enemies on the map, select one and add "
                "an Enemy Information for them. If there are currently no "
                "Tactical Enemies present, treat this as no event."
            ),
            effects={"enemy_info": 1},
        ),
        TableEntry(
            low=71, high=80,
            result_id="ancient_sign",
            description=(
                "Randomly select a map sector, then mark that it has an "
                "Ancient Sign within it. Completing any mission in the sector "
                "awards the Ancient Sign."
            ),
            effects={"ancient_sign": True},
        ),
        TableEntry(
            low=81, high=100,
            result_id="revised_survey",
            description=(
                "Randomly pick a map sector. If not yet Explored, generate "
                "Resource and Hazard levels normally. If Explored but not yet "
                "Exploited, increase Resource level by +1. If already Exploited, "
                "generate new Resource and Hazard levels. You can Exploit it again."
            ),
            effects={"revised_survey": True},
        ),
    ],
)

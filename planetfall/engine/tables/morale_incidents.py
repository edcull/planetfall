"""Morale Incident Table (D100) and Crisis Outcome Table (2D6).

Triggered when Colony Morale reaches -10 or worse during Step 11.
See rules pages 89-90.
"""

from planetfall.engine.dice import RandomTable, TableEntry

MORALE_INCIDENT_TABLE = RandomTable(
    name="Morale Incident",
    dice_type="d100",
    entries=[
        TableEntry(
            low=1, high=10,
            result_id="character_loyalty_loss",
            description=(
                "A random character on your roster loses one level "
                "of Loyalty."
            ),
            effects={"loyalty_loss_random": True},
        ),
        TableEntry(
            low=11, high=25,
            result_id="protests",
            description=(
                "Widespread protests hit the colony. Select a trooper "
                "that is unable to undertake any missions next campaign "
                "turn. If you have to fight a Pitched Battle, the protests "
                "recede and the trooper can take part normally."
            ),
            effects={"bench_trooper": True},
        ),
        TableEntry(
            low=26, high=35,
            result_id="sabotage",
            description=(
                "A dissident conducts large scale sabotage, causing 1D6 "
                "Colony Damage. This cannot be mitigated by buildings "
                "that normally mitigate damage."
            ),
            effects={"colony_damage_d6": True, "unmitigable": True},
        ),
        TableEntry(
            low=36, high=55,
            result_id="work_stoppage",
            description=(
                "You suffer a -3 penalty to any BP and RP earned this "
                "campaign turn, though this will not affect points "
                "already spent."
            ),
            effects={"bp_rp_penalty": -3},
        ),
        TableEntry(
            low=56, high=75,
            result_id="colonist_demands",
            description=(
                "Your scout teams are redirected to focus on threats "
                "close to the colony. Each campaign turn, assign any "
                "number of scouts or troopers to supervise security. "
                "They cannot take part in any missions except Pitched "
                "Battles. For each character, roll 1D6+Savvy with a 5+ "
                "indicating the demands have been satisfied."
            ),
            effects={"colonist_demands": True},
        ),
        TableEntry(
            low=76, high=100,
            result_id="political_strife",
            description=(
                "Administration is faced with a political challenge to "
                "its authority such as dissident groups, rival claims for "
                "administration, or secretive factions. "
                "Make a Crisis check."
            ),
            effects={"crisis_check": True},
        ),
    ],
)

CRISIS_OUTCOME_TABLE = RandomTable(
    name="Crisis Outcome",
    dice_type="2d6",
    entries=[
        TableEntry(
            low=2, high=3,
            result_id="high_tensions",
            description=(
                "Make another Crisis check using 2D6. If the result is "
                "equal to or below Political Upheaval, the colony "
                "collapses into open rebellion and your campaign ends. "
                "If higher, add +1 Political Upheaval."
            ),
            effects={"double_crisis_check": True},
        ),
        TableEntry(
            low=4, high=5,
            result_id="deteriorating_conditions",
            description="Add +1 Political Upheaval.",
            effects={"upheaval_increase": 1},
        ),
        TableEntry(
            low=6, high=8,
            result_id="deadlock",
            description="No agreement is reached, and no progress is made.",
            effects={},
        ),
        TableEntry(
            low=9, high=10,
            result_id="building_bridges",
            description=(
                "-1 to Political Upheaval. If this reduces the total "
                "to 0, treat as 'Agreements reached'."
            ),
            effects={"upheaval_reduction": -1},
        ),
        TableEntry(
            low=11, high=12,
            result_id="agreements_reached",
            description=(
                "You reach an agreement about the future of the colony. "
                "Reduce Political Upheaval by 2. Set Morale to 0."
            ),
            effects={"upheaval_reduction": -2, "set_morale_zero": True},
        ),
    ],
)

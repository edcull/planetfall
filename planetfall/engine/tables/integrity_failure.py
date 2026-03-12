"""Integrity Failure Table (3D6) - Campaign Turn Step 16.

Triggered when Colony Integrity is -3 or worse.
Roll 3D6; if the roll is equal to or below |Integrity|,
consult this table. See rules pages 87-88.
"""

from planetfall.engine.dice import RandomTable, TableEntry

INTEGRITY_FAILURE_TABLE = RandomTable(
    name="Integrity Failure",
    dice_type="3d6",
    entries=[
        TableEntry(
            low=3, high=3,
            result_id="minor_morale_loss",
            description="-1 Colony Morale.",
            effects={"morale": -1},
        ),
        TableEntry(
            low=4, high=4,
            result_id="morale_loss_2",
            description="-2 Colony Morale.",
            effects={"morale": -2},
        ),
        TableEntry(
            low=5, high=5,
            result_id="colony_damage_1",
            description="1 Colony Damage.",
            effects={"colony_damage": 1},
        ),
        TableEntry(
            low=6, high=6,
            result_id="reduced_income",
            description=(
                "Reduce available Build and Research points next turn "
                "by 2 each."
            ),
            effects={"bp_penalty_next": -2, "rp_penalty_next": -2},
        ),
        TableEntry(
            low=7, high=7,
            result_id="morale_loss_3",
            description="-3 Colony Morale.",
            effects={"morale": -3},
        ),
        TableEntry(
            low=8, high=8,
            result_id="colony_damage_3",
            description=(
                "3 Colony Damage. This can be mitigated normally."
            ),
            effects={"colony_damage": 3, "mitigable": True},
        ),
        TableEntry(
            low=9, high=9,
            result_id="morale_loss_5",
            description="-5 Colony Morale.",
            effects={"morale": -5},
        ),
        TableEntry(
            low=10, high=10,
            result_id="character_injury",
            description=(
                "A random character on your roster must make an injury "
                "roll. Treat 'Death' as 5 turns of recovery instead."
            ),
            effects={"injury_roll": True, "death_override_turns": 5},
        ),
        TableEntry(
            low=11, high=11,
            result_id="reduced_bp",
            description=(
                "Reduce available Build points next turn by 5. This "
                "only affects points earned, not any stored or "
                "already spent."
            ),
            effects={"bp_penalty_next": -5},
        ),
        TableEntry(
            low=12, high=12,
            result_id="reduced_rp",
            description=(
                "Reduce available Research points next turn by 5. "
                "This only affects points earned, not any stored "
                "or already spent."
            ),
            effects={"rp_penalty_next": -5},
        ),
        TableEntry(
            low=13, high=13,
            result_id="colony_damage_4",
            description=(
                "4 Colony Damage. This can be mitigated normally."
            ),
            effects={"colony_damage": 4, "mitigable": True},
        ),
        TableEntry(
            low=14, high=14,
            result_id="colony_damage_5_mitigable",
            description=(
                "5 Colony Damage. This can be mitigated normally."
            ),
            effects={"colony_damage": 5, "mitigable": True},
        ),
        TableEntry(
            low=15, high=15,
            result_id="character_injury_full",
            description=(
                "A random character on your roster must make an "
                "injury roll."
            ),
            effects={"injury_roll": True},
        ),
        TableEntry(
            low=16, high=16,
            result_id="colony_damage_5_unmitigable",
            description=(
                "5 Colony Damage. This cannot be mitigated."
            ),
            effects={"colony_damage": 5, "unmitigable": True},
        ),
        TableEntry(
            low=17, high=17,
            result_id="character_injury_full_2",
            description=(
                "A random character on your roster must make an "
                "injury roll."
            ),
            effects={"injury_roll": True},
        ),
        TableEntry(
            low=18, high=18,
            result_id="character_slain",
            description="A random character on your roster is slain.",
            effects={"character_slain": True},
        ),
    ],
)

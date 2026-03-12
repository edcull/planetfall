"""Delve mission tables — Hazard resolution, Traps, Environmental Hazards, Devices.

Used during Delve missions when exploring ancient alien facilities.
"""

from planetfall.engine.dice import RandomTable, TableEntry

# D6 Delve Hazard resolution (rolled when crew reveals a hazard marker)
DELVE_HAZARD_TABLE = RandomTable(
    name="Delve Hazard",
    dice_type="d6",
    entries=[
        TableEntry(low=1, high=2, result_id="enemy",
                   description="Place a Sleeper figure. It immediately fires its weapon."),
        TableEntry(low=3, high=4, result_id="trap",
                   description="Roll on the Delve Trap table."),
        TableEntry(low=5, high=6, result_id="environmental",
                   description="Roll on the Environmental Hazard table."),
    ],
)

# D100 Delve Trap table
DELVE_TRAP_TABLE = RandomTable(
    name="Delve Trap",
    dice_type="d100",
    entries=[
        TableEntry(
            low=1, high=8, result_id="turret",
            description=(
                "Turret: Place a gun turret. Each Enemy Phase fires at closest "
                "visible non-Sleeper/non-bot. +0 Combat Skill, +0 Damage, "
                "negates Saving Throws. Destroy: ranged 6 to hit, melee 5+, "
                "damage 4+ destroys. Scientist can shut down with Savvy 4+."
            ),
            effects={"spawn": "turret"},
        ),
        TableEntry(
            low=9, high=19, result_id="paralysis",
            description=(
                "Paralysis: Revealing character cannot move or act when next "
                "activated. Roll 1D6+Toughness, 8+ shakes it off. Scouts "
                "roll twice and take best."
            ),
            effects={"paralysis": True},
        ),
        TableEntry(
            low=20, high=30, result_id="blockage",
            description=(
                "Blockage: Area within 1\" becomes Impassable. Scout can "
                "remove by rolling Savvy 5+ in base contact."
            ),
            effects={"blockage": True},
        ),
        TableEntry(
            low=31, high=40, result_id="laser_beam",
            description=(
                "Laser beam: Revealing character takes a weapon hit with "
                "+0 Damage."
            ),
            effects={"damage_hit": 0},
        ),
        TableEntry(
            low=41, high=46, result_id="explosive_trap",
            description=(
                "Explosive trap: Every character within 3\" takes a weapon "
                "hit with +0 Damage. Partial cover between character and "
                "hazard: 4+ on D6 required to hit."
            ),
            effects={"aoe_damage": 0, "range_inches": 3},
        ),
        TableEntry(
            low=47, high=60, result_id="sleepers",
            description=(
                "Sleepers! Randomly place 2 Sleepers within 6\" of hazard. "
                "They do not activate this round."
            ),
            effects={"spawn_sleepers": 2},
        ),
        TableEntry(
            low=61, high=68, result_id="alarm",
            description=(
                "Alarm: Each future Enemy Phase, a Sleeper arrives at center "
                "of random edge. Shut down: base contact with hazard, "
                "Savvy 6+."
            ),
            effects={"alarm": True},
        ),
        TableEntry(
            low=69, high=80, result_id="gas",
            description=(
                "Gas: Everyone within 1\" affected. Expands to 2\" next round, "
                "3\" after. Affected roll 5+ to avoid being overcome (scouts +1). "
                "Overcome: move random direction, no actions. Recover outside "
                "gas on 3+ (scouts +1)."
            ),
            effects={"gas": True},
        ),
        TableEntry(
            low=81, high=92, result_id="security_systems",
            description=(
                "Security systems: Place one additional Delve Hazard in "
                "center of table and one at center of random edge."
            ),
            effects={"extra_hazards": 2},
        ),
        TableEntry(
            low=93, high=100, result_id="lockdown",
            description=(
                "Lock-down: A random Delve Device is locked. Unlock: base "
                "contact, Savvy 6+. Natural 1 on unlock spawns a Sleeper "
                "at random edge center. Once unlocked, roll normally to activate."
            ),
            effects={"lockdown": True},
        ),
    ],
)

# D100 Environmental Hazard table
ENVIRONMENTAL_HAZARD_TABLE = RandomTable(
    name="Environmental Hazard",
    dice_type="d100",
    entries=[
        TableEntry(
            low=1, high=15, result_id="confused_signal",
            description=(
                "Confused signal: A random Delve Device is moved 1D6+2\" "
                "in a random direction."
            ),
            effects={"move_device": True},
        ),
        TableEntry(
            low=16, high=24, result_id="high_security",
            description=(
                "High security: Area within 4\" and LoS of hazard is high "
                "security for rest of mission. Any non-Sleeper/non-bot figure "
                "in area during activation rolls D6; on 6, Sleeper spawns "
                "at nearest edge."
            ),
            effects={"high_security_zone": True},
        ),
        TableEntry(
            low=25, high=39, result_id="unstable_area",
            description=(
                "Unstable Area: Within 3\" of hazard is unstable. Moving "
                "through or firing in/out/through: D6, on 6 partial collapse. "
                "All in area take +0 hit, ground becomes Difficult. Second "
                "collapse = Impassable, all casualties. Scouts move through "
                "safely but roll if starting/ending in area."
            ),
            effects={"unstable_area": True},
        ),
        TableEntry(
            low=40, high=50, result_id="shock_discharge",
            description=(
                "Shock discharge: Immediately and each Enemy Phase, roll D6. "
                "All characters within that distance (inches) cannot move/act "
                "when next activated. Sleepers and bots also take +0 hit "
                "ignoring saves. Roll of 6 ends the discharge."
            ),
            effects={"shock": True},
        ),
        TableEntry(
            low=51, high=67, result_id="toxic_fog",
            description=(
                "Toxic fog: Expands 2\" each direction (blocked by walls), "
                "moves 1D6\" random direction each Enemy Phase. Non-Sleeper/ "
                "non-bot touched take +1 hit ignoring saves. Scouts take "
                "+0 instead."
            ),
            effects={"toxic_fog": True},
        ),
        TableEntry(
            low=68, high=79, result_id="sleeper_reset",
            description=(
                "Sleeper reset: All Sleepers unable to activate next Enemy "
                "Phase. At end of that phase, place additional Sleeper at "
                "center of 2 random edges."
            ),
            effects={"sleeper_reset": True, "spawn_sleepers": 2},
        ),
        TableEntry(
            low=80, high=88, result_id="collapse",
            description=(
                "Collapse: Replace marker with rubble blocking all access. "
                "Corridor: blocks width. Open space: 1.5\" radius. Figures "
                "within can leap out of the way."
            ),
            effects={"collapse": True},
        ),
        TableEntry(
            low=89, high=100, result_id="radiation",
            description=(
                "Radiation build-up: Within 3\" and LoS is radioactive. "
                "Non-Sleeper/non-bot starting or ending activation in area "
                "takes +0 hit ignoring saves. Special save: scouts 5+, "
                "scientists 4+."
            ),
            effects={"radiation": True},
        ),
    ],
)

# D6 Delve Device activation table
DELVE_DEVICE_TABLE = RandomTable(
    name="Delve Device Activation",
    dice_type="d6",
    entries=[
        TableEntry(low=1, high=1, result_id="unusable",
                   description="Unusable: Ignore this Device."),
        TableEntry(low=2, high=3, result_id="time_based",
                   description=(
                       "Time-based activation: A character must be within 1\" "
                       "for two consecutive battle rounds to activate."
                   )),
        TableEntry(low=4, high=5, result_id="automatic",
                   description="Automatic activation: No actions required."),
        TableEntry(low=6, high=6, result_id="skill_based",
                   description=(
                       "Skill-based activation: Character must take an action "
                       "and roll 1D6+Savvy scoring 4+."
                   )),
    ],
)

"""Character Event Table (D100) - Campaign Turn Step 17.

This is the MECHANICAL character event table from the rules (page 70).
These events have real game effects (XP, loyalty, sick bay, etc.).

NOT to be confused with the optional Character Roleplay Events table
(page 72), which is purely narrative flavor.
"""

from planetfall.engine.dice import RandomTable, TableEntry

CHARACTER_EVENT_TABLE = RandomTable(
    name="Character Events",
    dice_type="d100",
    entries=[
        TableEntry(
            low=1, high=5,
            result_id="personal_training",
            description=(
                "The character undergoes a training course to hone their "
                "mission-relevant skills. The character gains +2 XP."
            ),
            effects={"xp": 2},
        ),
        TableEntry(
            low=6, high=10,
            result_id="minor_promotion",
            description=(
                "Proficiency is rewarded with improvements in rank and "
                "responsibility. The character gains a level of Loyalty "
                "and +1 XP. If already Loyal, gain +2 XP total."
            ),
            effects={"loyalty_up": 1, "xp": 1, "loyal_bonus_xp": 2},
        ),
        TableEntry(
            low=11, high=15,
            result_id="personal_investigation",
            description=(
                "The character does a bit of information gathering. "
                "Randomly choose a Tactical Enemy and receive "
                "+1 Enemy Information."
            ),
            effects={"enemy_info": 1},
        ),
        TableEntry(
            low=16, high=20,
            result_id="something_in_the_water",
            description=(
                "The character comes down with a minor illness. "
                "If in sick bay, increase recovery time by 1 turn. "
                "Otherwise, they get a tummy ache but are fine."
            ),
            effects={"extend_sick_bay": 1},
        ),
        TableEntry(
            low=21, high=25,
            result_id="r_and_r",
            description=(
                "The character earns some time off world. Gone for 2 "
                "campaign turns, cannot be targeted by events. Recovers "
                "completely from any injuries. If Disloyal, roll D6: "
                "1-2 = does not return; 3-5 = stays Disloyal; "
                "6 = becomes Committed."
            ),
            effects={"gone_turns": 2, "full_heal": True, "disloyal_check": True},
        ),
        TableEntry(
            low=26, high=30,
            result_id="change_of_assignment",
            description=(
                "The character is offered a new assignment. If they "
                "accept, they earn 5 XP and are transferred out of the "
                "campaign. If they decline, gain 1 level of Loyalty."
            ),
            effects={"accept_xp": 5, "decline_loyalty_up": 1},
        ),
        TableEntry(
            low=31, high=35,
            result_id="disputes_with_leadership",
            description=(
                "The character has a heated disagreement with "
                "Administration. The character loses a level of Loyalty "
                "but cannot drop below Disloyal."
            ),
            effects={"loyalty_down": 1},
        ),
        TableEntry(
            low=36, high=40,
            result_id="commitment_to_the_cause",
            description=(
                "The character is satisfied with recent Administration "
                "actions and is dedicated to the cause. "
                "The character gains a level of Loyalty."
            ),
            effects={"loyalty_up": 1},
        ),
        TableEntry(
            low=41, high=45,
            result_id="dispute",
            description=(
                "A clash of personalities occurs. Randomly pick a second "
                "character. The two cannot both be assigned to the mission "
                "next campaign turn unless fighting a Pitched Battle."
            ),
            effects={"dispute_pair": True},
        ),
        TableEntry(
            low=46, high=50,
            result_id="personal_calibrations",
            description=(
                "Time spent customizing gun sights and ammunition loads "
                "pays off. The next time the character is on a mission, "
                "select one weapon they carry which receives a +1 hit "
                "bonus for the duration of that mission."
            ),
            effects={"next_mission_hit_bonus": 1},
        ),
        TableEntry(
            low=51, high=55,
            result_id="sickness",
            description=(
                "The character falls ill. They must spend 2 campaign "
                "turns recovering."
            ),
            effects={"sick_bay_turns": 2},
        ),
        TableEntry(
            low=56, high=60,
            result_id="making_friends",
            description=(
                "The character has spent some quality time with a random "
                "character on your roster. They each earn +1 XP and may "
                "each roll D6: On 5-6, they gain one level of Loyalty."
            ),
            effects={"xp": 1, "friend_loyalty_check": True},
        ),
        TableEntry(
            low=61, high=65,
            result_id="personal_life_achievement",
            description=(
                "Something significant happens in the character's life "
                "(marriage, a new baby, a graduation, etc.). "
                "Receive 1 Story Point and 1 point of Colony Morale."
            ),
            effects={"story_points": 1, "morale": 1},
        ),
        TableEntry(
            low=66, high=70,
            result_id="excellent_health",
            description=(
                "All that fresh air is paying off. If currently recovering "
                "from injuries, reduce the time required by 2 turns. "
                "If not injured, the effect can be saved."
            ),
            effects={"heal_turns": 2},
        ),
        TableEntry(
            low=71, high=75,
            result_id="accident",
            description=(
                "The character injures themselves during work. Roll on "
                "the Post-battle Injury table. If you roll 'Dead', it "
                "instead counts as 5 turns of recovery."
            ),
            effects={"injury_roll": True, "death_override_turns": 5},
        ),
        TableEntry(
            low=76, high=80,
            result_id="personal_reflection",
            description=(
                "After some hard lessons, the character is determined "
                "to learn. The next time they go on a mission, they "
                "earn double XP."
            ),
            effects={"double_xp_next_mission": True},
        ),
        TableEntry(
            low=81, high=85,
            result_id="personal_conviction",
            description=(
                "If the last mission was a success, gain one level "
                "of Loyalty."
            ),
            effects={"loyalty_if_last_victory": True},
        ),
        TableEntry(
            low=86, high=90,
            result_id="losing_faith",
            description=(
                "The character has serious disagreements over the mission "
                "and how it is being done. If the last mission was a "
                "failure, they lose one level of Loyalty."
            ),
            effects={"loyalty_loss_if_last_defeat": True},
        ),
        TableEntry(
            low=91, high=95,
            result_id="personal_tragedy",
            description=(
                "Something happens to throw the character off their game. "
                "Next campaign turn they forfeit all XP they would have "
                "earned that turn."
            ),
            effects={"forfeit_xp_next_turn": True},
        ),
        TableEntry(
            low=96, high=100,
            result_id="new_hobby",
            description=(
                "The character has found something new to do in their "
                "spare time. They receive +1 XP and will irritate "
                "everyone else as they talk about it constantly."
            ),
            effects={"xp": 1},
        ),
    ],
)

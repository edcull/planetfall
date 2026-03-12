"""Character Roleplay Events Table (D100) - Campaign Turn Step 17."""

from planetfall.engine.dice import RandomTable, TableEntry

CHARACTER_EVENTS_TABLE = RandomTable(
    name="Character Roleplay Events",
    dice_type="d100",
    entries=[
        TableEntry(
            low=1, high=5,
            result_id="adapting",
            description=(
                "The character is adapting to colony life and changes some "
                "of their habits."
            ),
        ),
        TableEntry(
            low=6, high=10,
            result_id="work_project",
            description=(
                "The character spends long hours finishing a project. "
                "Roll D6: 1 = doesn't work; 2-4 = succeeds; "
                "5-6 = succeeds extremely well."
            ),
            effects={"roll_d6": True},
        ),
        TableEntry(
            low=11, high=15,
            result_id="post_duty_plans",
            description=(
                "The character makes a detailed plan for what they will "
                "do after their tour of duty ends."
            ),
        ),
        TableEntry(
            low=16, high=20,
            result_id="opinion_change",
            description="The character changes their opinion on something.",
        ),
        TableEntry(
            low=21, high=25,
            result_id="letter_from_home",
            description=(
                "The character receives a letter from home. Roll D6: "
                "1 = Bad news; 2-3 = General updates; 4-5 = Heartwarming; "
                "6 = Great news."
            ),
            effects={"roll_d6": True},
        ),
        TableEntry(
            low=26, high=30,
            result_id="funk",
            description=(
                "The character spends a few days in a bit of a funk "
                "about life."
            ),
        ),
        TableEntry(
            low=31, high=35,
            result_id="visit",
            description="The character pays another character a visit.",
            effects={"involves_other": 1},
        ),
        TableEntry(
            low=36, high=40,
            result_id="argument",
            description=(
                "The character gets in an argument with another character. "
                "Roll D6: 1 = worsens; 2 = unresolved; 3-4 = resolved; "
                "5 = another resolves it; 6 = strengthens."
            ),
            effects={"involves_other": 1, "roll_d6": True},
        ),
        TableEntry(
            low=41, high=45,
            result_id="street_encounter",
            description=(
                "Two characters run into each other and spend some time talking."
            ),
            effects={"involves_other": 1},
        ),
        TableEntry(
            low=46, high=50,
            result_id="gift",
            description="Another character gets the character a gift.",
            effects={"involves_other": 1},
        ),
        TableEntry(
            low=51, high=55,
            result_id="new_interest",
            description=(
                "The character decides to pursue a new interest or hobby."
            ),
        ),
        TableEntry(
            low=56, high=60,
            result_id="randr",
            description="The character takes a few days of R&R.",
        ),
        TableEntry(
            low=61, high=65,
            result_id="night_out",
            description=(
                "The character goes out for a night on the town with two "
                "others. Roll D6: 1 = trouble; 2-4 = fine night; "
                "5-6 = completely wasted."
            ),
            effects={"involves_other": 2, "roll_d6": True},
        ),
        TableEntry(
            low=66, high=70,
            result_id="work_embarrassment",
            description=(
                "The character makes a fool of themselves at work."
            ),
        ),
        TableEntry(
            low=71, high=75,
            result_id="movie_night",
            description=(
                "The character arranges a movie night with two other characters."
            ),
            effects={"involves_other": 2},
        ),
        TableEntry(
            low=76, high=80,
            result_id="work_with_colleague",
            description=(
                "The character is assigned to a special work project with "
                "another character. Roll D6: 1 = bicker; 2-5 = work well; "
                "6 = strengthens relationship."
            ),
            effects={"involves_other": 1, "roll_d6": True},
        ),
        TableEntry(
            low=81, high=85,
            result_id="heart_to_heart",
            description=(
                "The character has a heart-to-heart talk with another character."
            ),
            effects={"involves_other": 1},
        ),
        TableEntry(
            low=86, high=90,
            result_id="new_passion",
            description=(
                "The character finds a new passion in life such as music "
                "or literature."
            ),
        ),
        TableEntry(
            low=91, high=95,
            result_id="writing_book",
            description=(
                "The character begins writing a book about their experiences."
            ),
        ),
        TableEntry(
            low=96, high=100,
            result_id="meal_together",
            description=(
                "The character goes out for lunch or dinner with another character."
            ),
            effects={"involves_other": 1},
        ),
    ],
)

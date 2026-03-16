"""Character creation, import, and related D100 tables."""

from __future__ import annotations

import random

from planetfall.engine.dice import roll_d100
from planetfall.engine.models import (
    Character,
    CharacterClass,
    Loyalty,
    STARTING_PROFILES,
    SubSpecies,
)


# --- Motivation table (all characters) ---

MOTIVATION_TABLE = [
    (1, 11, "Curiosity"),
    (12, 22, "Personal Achievement"),
    (23, 34, "Loyalty"),
    (35, 41, "Danger"),
    (42, 50, "Independence"),
    (51, 56, "Circumstance"),
    (57, 63, "Progress"),
    (64, 72, "Adventure"),
    (73, 82, "Exploration"),
    (83, 89, "Greater Cause"),
    (90, 95, "Escape"),
    (96, 100, "Obligation"),
]

# --- Prior Experience table (experienced characters only) ---

PRIOR_EXPERIENCE_TABLE = [
    (1, 5, "Army", {"reactions": 1}),
    (6, 11, "Freelancer", {"reactions": 1}),
    (12, 21, "Researcher", {"savvy": 1}),
    (22, 27, "Trader", {"xp": 3}),
    (28, 37, "Orphan/Utility program", {"loyalty": Loyalty.LOYAL}),
    (38, 44, "Unity Agent", {"loyalty": Loyalty.LOYAL}),
    (45, 48, "Bug Hunter", {"kill_points": 1}),
    (49, 56, "Administration", {"loyalty": Loyalty.LOYAL}),
    (57, 61, "Corporate", {"savvy": 1}),
    (62, 70, "Explorer", {"speed": 1}),
    (71, 77, "Adventurer", {"xp": 3}),
    (78, 82, "Records Deleted", {"toughness": 1}),
    (83, 87, "Enforcer", {"toughness": 1}),
    (88, 96, "Fleet Officer", {"xp": 3}),
    (97, 100, "Access Denied", {"story_points": 1}),
]

# --- Administrator Past History ---

ADMIN_HISTORY_TABLE = [
    (1, 8, "Unity armed forces"),
    (9, 21, "Exploration service"),
    (22, 37, "Colonial"),
    (38, 48, "Unity field agent"),
    (49, 56, "Corporate"),
    (57, 67, "Unity Bureaucracy"),
    (68, 76, "Diplomatic"),
    (77, 88, "Unity fleet"),
    (89, 100, "Scientist"),
]


# --- Notable Event table (experienced: 3 rolls, inexperienced: 1 roll) ---

NOTABLE_EVENT_TABLE = [
    (1, 5, "Journey", "You went somewhere far from home."),
    (6, 10, "Establish family", "You established or expanded your family, adopted or otherwise."),
    (11, 15, "Betrayal", "Someone betrayed you or you betrayed someone."),
    (16, 20, "Personal advancement", "You made great strides as a person."),
    (21, 25, "Disaster struck", "A dreadful disaster struck you, your organization, or your home."),
    (26, 30, "Injured", "You were seriously injured or sick."),
    (31, 35, "Joined a group", "You joined an organization, community, or philosophical movement."),
    (36, 40, "Changed perspective", "Life changed how you look at things."),
    (41, 45, "Went missing", "You spent a period of time when nobody knew where you were."),
    (46, 50, "Did a good deed", "Without expecting a reward, you did the right thing."),
    (51, 55, "Became a student", "You decided to learn a new skill or career."),
    (56, 60, "Was framed", "You did nothing but you got blamed regardless."),
    (61, 65, "Made a mistake", "You screwed up and it got noticed."),
    (66, 70, "Progressed a career", "You made advances in your career."),
    (71, 75, "Good luck", "Something lucky and unlikely happened."),
    (76, 80, "Confrontation", "You had a showdown with a rival or threat."),
    (81, 85, "Great danger", "You experienced great physical danger."),
    (86, 90, "Narrow escape", "Once arrested, destitute, or nearly dead, you eventually came out ahead."),
    (91, 95, "Second chance", "Someone gave you a second chance."),
    (96, 100, "Change of lifestyle", "You changed something fundamental about your lifestyle."),
]


def roll_notable_events(count: int = 3) -> list[str]:
    """Roll on the Notable Event table multiple times. Returns list of event names."""
    events = []
    for i in range(count):
        result = roll_d100(f"Notable Event {i + 1}")
        for low, high, name, _desc in NOTABLE_EVENT_TABLE:
            if low <= result.total <= high:
                events.append(name)
                break
        else:
            events.append(NOTABLE_EVENT_TABLE[-1][2])
    return events


def _roll_on_table(table, label: str) -> str:
    """Roll D100 and look up result in a simple (low, high, value) table."""
    result = roll_d100(label)
    for entry in table:
        low, high = entry[0], entry[1]
        if low <= result.total <= high:
            return entry[2] if len(entry) == 3 else entry
    return table[-1][2] if len(table[-1]) == 3 else table[-1]


def roll_motivation() -> str:
    return _roll_on_table(MOTIVATION_TABLE, "Motivation")


def roll_prior_experience() -> tuple:
    """Returns (name, effects_dict)."""
    result = roll_d100("Prior Experience")
    for low, high, name, effects in PRIOR_EXPERIENCE_TABLE:
        if low <= result.total <= high:
            return name, effects
    last = PRIOR_EXPERIENCE_TABLE[-1]
    return last[2], last[3]


def roll_admin_history() -> str:
    return _roll_on_table(ADMIN_HISTORY_TABLE, "Administrator History")


# --- Character creation ---


def create_character(
    name: str,
    char_class: CharacterClass,
    experienced: bool = False,
    sub_species: SubSpecies = SubSpecies.STANDARD,
) -> Character:
    """Create a character with starting profile and optional background rolls."""
    profile = STARTING_PROFILES[char_class].model_dump()

    # Apply sub-species modifications
    if sub_species == SubSpecies.HULKER:
        profile["toughness"] = 5
    # Feral and Stalker have no stat modifications (just special abilities)

    char = Character(
        name=name,
        char_class=char_class,
        sub_species=sub_species,
        **profile,
    )

    # Roll motivation for all characters
    char.background_motivation = roll_motivation()

    # Experienced characters get prior experience and 3 notable events
    if experienced:
        exp_name, exp_effects = roll_prior_experience()
        char.background_prior_experience = exp_name

        # Apply stat effects from prior experience
        for stat, value in exp_effects.items():
            if stat == "loyalty":
                char.loyalty = value
            elif stat == "story_points":
                pass  # Handled at game state level
            elif hasattr(char, stat):
                current = getattr(char, stat)
                setattr(char, stat, current + value)

        char.background_notable_events = roll_notable_events(3)
    else:
        # Inexperienced characters get 1 notable event
        char.background_notable_events = roll_notable_events(1)

    return char


def import_character(
    name: str,
    char_class: CharacterClass,
    reactions: int = 1,
    speed: int = 4,
    combat_skill: int = 0,
    toughness: int = 3,
    savvy: int = 0,
    xp: int = 0,
    kill_points: int = 0,
    loyalty: Loyalty = Loyalty.COMMITTED,
    sub_species: SubSpecies = SubSpecies.STANDARD,
    title: str = "",
    role: str = "",
    motivation: str = "",
    prior_experience: str = "",
    equipment: list[str] | None = None,
    narrative_background: str = "",
    notes: str = "",
) -> Character:
    """Import an existing character with manually specified stats."""
    return Character(
        name=name,
        char_class=char_class,
        reactions=reactions,
        speed=speed,
        combat_skill=combat_skill,
        toughness=toughness,
        savvy=savvy,
        xp=xp,
        kill_points=kill_points,
        loyalty=loyalty,
        sub_species=sub_species,
        title=title,
        role=role,
        background_motivation=motivation,
        background_prior_experience=prior_experience,
        narrative_background=narrative_background,
        equipment=equipment or [],
        notes=notes,
    )

"""Campaign setup — character creation, map generation, colonization agenda.

This package re-exports all public symbols so that existing imports like
``from planetfall.engine.campaign.setup import create_new_campaign`` continue
to work unchanged.
"""

from __future__ import annotations

from typing import Optional

from planetfall.engine.dice import roll_d100
from planetfall.engine.models import (
    Administrator,
    CampaignProgress,
    CharacterClass,
    Colony,
    ColonizationAgenda,
    Enemies,
    GameSettings,
    GameState,
    GruntPool,
    Resources,
    SubSpecies,
    TechTree,
)

# --- Re-export submodule symbols ---

from planetfall.engine.campaign.setup.characters import (  # noqa: F401
    ADMIN_HISTORY_TABLE,
    MOTIVATION_TABLE,
    PRIOR_EXPERIENCE_TABLE,
    create_character,
    import_character,
    roll_admin_history,
    roll_motivation,
    roll_prior_experience,
)

from planetfall.engine.campaign.setup.backgrounds import (  # noqa: F401
    _TITLE_PREFIXES,
    _build_batch_background_prompt,
    _is_unnamed,
    _parse_batch_backgrounds,
    _strip_title_from_name,
    build_character_background_prompt,
    generate_character_background_local,
    generate_character_backgrounds_api,
    generate_character_names,
)

from planetfall.engine.campaign.setup.map_gen import (  # noqa: F401
    generate_campaign_map,
)


# --- Colonization Agenda effects ---

AGENDA_EFFECTS: dict[ColonizationAgenda, dict] = {
    ColonizationAgenda.SCIENTIFIC: {
        "description": "Scientific Mission — begin with 3 Research Points",
        "research_points": 3,
    },
    ColonizationAgenda.CORPORATE: {
        "description": "Corporate Funded — 2 additional Investigation Sites on map",
        "extra_investigation_sites": 2,
    },
    ColonizationAgenda.UNITY: {
        "description": "Unity Colonization Drive — begin with 3 Raw Materials",
        "raw_materials": 3,
    },
    ColonizationAgenda.INDEPENDENT: {
        "description": "Independent Mission — begin with 1 additional Story Point",
        "story_points": 1,
    },
    ColonizationAgenda.MILITARY: {
        "description": "Military Expedition — begin with 2 additional grunts",
        "extra_grunts": 2,
    },
    ColonizationAgenda.AFFINITY: {
        "description": "Affinity Group — begin with 5 Morale points",
        "morale": 5,
    },
}

# D100 table for rolling agenda
AGENDA_TABLE = [
    (1, 15, ColonizationAgenda.SCIENTIFIC),
    (16, 30, ColonizationAgenda.CORPORATE),
    (31, 60, ColonizationAgenda.UNITY),
    (61, 80, ColonizationAgenda.INDEPENDENT),
    (81, 90, ColonizationAgenda.MILITARY),
    (91, 100, ColonizationAgenda.AFFINITY),
]


def roll_colonization_agenda() -> ColonizationAgenda:
    """Roll D100 to determine colonization agenda."""
    result = roll_d100("Colonization Agenda")
    for low, high, agenda in AGENDA_TABLE:
        if low <= result.total <= high:
            return agenda
    return ColonizationAgenda.UNITY


# --- Full campaign creation ---


def create_new_campaign(
    campaign_name: str,
    colony_name: str,
    agenda: Optional[ColonizationAgenda] = None,
    character_specs: Optional[list[dict]] = None,
    admin_name: str = "",
    api_key: str = "",
) -> GameState:
    """Create a complete new campaign with all starting state.

    Args:
        campaign_name: Name for the save file.
        colony_name: Name of the colony.
        agenda: Colonization agenda (rolled if None).
        character_specs: List of dicts with keys: name, class, experienced, sub_species.
            If None, creates default roster of 2 scouts, 2 scientists, 4 troopers.
        admin_name: Name for the administrator.
    """
    # Determine agenda
    if agenda is None:
        agenda = roll_colonization_agenda()

    # Create characters
    if character_specs is None:
        character_specs = [
            {"name": "Scientist 1", "class": CharacterClass.SCIENTIST, "experienced": True},
            {"name": "Scientist 2", "class": CharacterClass.SCIENTIST, "experienced": False},
            {"name": "Scout 1", "class": CharacterClass.SCOUT, "experienced": True},
            {"name": "Scout 2", "class": CharacterClass.SCOUT, "experienced": False},
            {"name": "Trooper 1", "class": CharacterClass.TROOPER, "experienced": True},
            {"name": "Trooper 2", "class": CharacterClass.TROOPER, "experienced": True},
            {"name": "Trooper 3", "class": CharacterClass.TROOPER, "experienced": False},
            {"name": "Trooper 4", "class": CharacterClass.TROOPER, "experienced": False},
        ]

    characters = []
    extra_story_points = 0
    for spec in character_specs:
        char = create_character(
            name=spec["name"],
            char_class=spec["class"],
            experienced=spec.get("experienced", False),
            sub_species=spec.get("sub_species", SubSpecies.STANDARD),
        )
        # Check if prior experience gave story points
        if char.background_prior_experience == "Access Denied":
            extra_story_points += 1
        characters.append(char)

    # Generate narrative backgrounds (AI if api_key provided, else template)
    generate_character_backgrounds_api(
        characters, agenda, colony_name, api_key=api_key,
    )

    # Generate map
    agenda_effects = AGENDA_EFFECTS[agenda]
    extra_sites = agenda_effects.get("extra_investigation_sites", 0)
    campaign_map = generate_campaign_map(
        num_investigation_sites=10 + extra_sites,
        colony_name=colony_name,
        api_key=api_key,
    )

    # Build resources
    resources = Resources(
        story_points=5 + extra_story_points + agenda_effects.get("story_points", 0),
        research_points=agenda_effects.get("research_points", 0),
        raw_materials=agenda_effects.get("raw_materials", 0),
    )

    # Grunt count
    grunt_count = 12 + agenda_effects.get("extra_grunts", 0)

    # Colony morale
    morale = agenda_effects.get("morale", 0)

    # Administrator
    admin_history = roll_admin_history()
    administrator = Administrator(
        name=admin_name or "Administrator",
        past_history=admin_history,
    )

    # Assemble state
    state = GameState(
        campaign_name=campaign_name,
        current_turn=1,
        colony=Colony(
            name=colony_name,
            morale=morale,
            resources=resources,
        ),
        characters=characters,
        administrator=administrator,
        grunts=GruntPool(count=grunt_count),
        tech_tree=TechTree(),
        campaign_map=campaign_map,
        enemies=Enemies(),
        campaign=CampaignProgress(),
        settings=GameSettings(colonization_agenda=agenda),
    )

    # Colony description is generated after character backgrounds are finalized,
    # so it has full crew context. See main.py and web/server.py setup paths.

    return state

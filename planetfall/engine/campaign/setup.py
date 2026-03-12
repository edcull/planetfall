"""Campaign setup — character creation, map generation, colonization agenda."""

from __future__ import annotations

import random
from typing import Optional

from planetfall.engine.dice import roll_d100, roll_d6
from planetfall.engine.models import (
    Administrator,
    CampaignMap,
    CampaignProgress,
    Character,
    CharacterClass,
    Colony,
    ColonizationAgenda,
    Enemies,
    GameSettings,
    GameState,
    GruntPool,
    Loyalty,
    Resources,
    Sector,
    SectorStatus,
    STARTING_PROFILES,
    SubSpecies,
    TechTree,
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
    profile = dict(STARTING_PROFILES[char_class])

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

    # Experienced characters get prior experience and notable event
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


# --- Narrative background generation ---


def build_character_background_prompt(
    char: Character,
    other_characters: list[Character],
    agenda: ColonizationAgenda,
    colony_name: str = "the colony",
) -> str:
    """Build a Claude API prompt to generate a character's narrative background.

    Uses the character's rolled traits (motivation, prior experience, class,
    sub-species) and the rest of the crew for interpersonal context.
    """
    # Crew context
    crew_lines = []
    for c in other_characters:
        if c.name == char.name:
            continue
        parts = [f"{c.name} ({c.char_class.value})"]
        if c.background_motivation:
            parts.append(f"motivated by {c.background_motivation.lower()}")
        if c.background_prior_experience:
            parts.append(f"formerly {c.background_prior_experience.lower()}")
        crew_lines.append(", ".join(parts))
    crew_text = "\n".join(f"  - {l}" for l in crew_lines) if crew_lines else "  None yet."

    subspecies_note = ""
    if char.sub_species != SubSpecies.STANDARD:
        subspecies_note = f"\nSUB-SPECIES: {char.sub_species.value} (non-human traits affect personality and worldview)"

    prompt = f"""Write a 2-3 sentence narrative background for a character in a gritty frontier sci-fi colony game.
This is for internal use as a personality reference when narrating scenes — keep it punchy and specific.

CHARACTER: {f"{char.title} " if char.title else ""}{char.name}
CLASS: {char.char_class.value}{subspecies_note}
{f"TITLE: {char.title}" + chr(10) if char.title else ""}ROLE: {char.role or char.char_class.value}
MOTIVATION: {char.background_motivation or 'Unknown'}
PRIOR EXPERIENCE: {char.background_prior_experience or 'None — fresh recruit'}
LOYALTY: {char.loyalty.value}
COLONIZATION AGENDA: {agenda.value}
COLONY: {colony_name}

CREWMATES:
{crew_text}

Write a brief personality sketch: who they are, why they joined this mission, and one distinctive trait or habit.
Reference their motivation and prior experience naturally — don't just list them.
Keep it grounded, no purple prose. This person is real, flawed, and interesting.
Do NOT include their name at the start — just the description."""
    return prompt


def generate_character_background_local(
    char: Character,
    other_characters: list[Character] | None = None,
) -> str:
    """Generate a template-based narrative background (no API needed).

    Combines motivation, prior experience, class, and loyalty into a
    short prose description. Used as fallback when AI is unavailable.
    """
    parts = []

    # Opening based on prior experience
    exp = char.background_prior_experience
    class_name = char.char_class.value
    if exp:
        exp_intros = {
            "Army": f"A former army {class_name} who's seen enough combat to last a lifetime",
            "Freelancer": f"A freelance {class_name} who's worked the edges of known space",
            "Researcher": f"An ex-researcher who traded the lab for fieldwork as a {class_name}",
            "Trader": f"A former trader who picked up plenty of tricks before signing on as {class_name}",
            "Orphan/Utility program": f"Raised in a Unity orphan program, now a {class_name} with nowhere else to go",
            "Unity Agent": f"A former Unity agent retrained as a {class_name}, still loyal to the cause",
            "Bug Hunter": f"A veteran bug hunter who knows what lurks in unexplored sectors",
            "Administration": f"Ex-administration staff who got tired of paperwork and became a {class_name}",
            "Corporate": f"A corporate transfer who brought sharp instincts to the {class_name} role",
            "Explorer": f"A seasoned explorer, quick on their feet and always pushing forward",
            "Adventurer": f"A restless adventurer who signed up as {class_name} for the thrill of the unknown",
            "Records Deleted": f"A {class_name} whose past records were scrubbed — tough and tight-lipped about why",
            "Enforcer": f"A former enforcer, built hard and not afraid to throw their weight around",
            "Fleet Officer": f"An ex-fleet officer who gave up rank to get boots on the ground as {class_name}",
            "Access Denied": f"A {class_name} with a classified background that even admin can't access",
        }
        parts.append(exp_intros.get(exp, f"A {class_name} with a background in {exp.lower()}"))
    else:
        parts.append(f"A fresh {class_name} recruit with no prior deep-space experience")

    # Motivation
    mot = char.background_motivation
    if mot:
        mot_phrases = {
            "Curiosity": "driven by an insatiable need to understand what's out there",
            "Personal Achievement": "here to prove something — to themselves more than anyone",
            "Loyalty": "fiercely loyal to the crew, the kind who'd take a hit for someone else",
            "Danger": "drawn to the edge, most alive when things go sideways",
            "Independence": "values their autonomy above all, chafes at too much authority",
            "Circumstance": "didn't choose this life — circumstance pushed them here, and they're making the best of it",
            "Progress": "believes in building something that lasts, focused on the mission",
            "Adventure": "chasing the next story, the next discovery, the next close call",
            "Exploration": "a born explorer who wants to see what no one else has seen",
            "Greater Cause": "driven by a cause bigger than themselves, willing to sacrifice for it",
            "Escape": "running from something — the colony is as far as they could get",
            "Obligation": "here out of duty, carrying a debt or promise they intend to keep",
        }
        parts.append(mot_phrases.get(mot, f"motivated by {mot.lower()}"))

    # Loyalty flavour
    if char.loyalty == Loyalty.LOYAL:
        parts.append("deeply committed to the colony's survival")
    elif char.loyalty == Loyalty.DISLOYAL:
        parts.append("though their commitment to the group is questionable at best")

    # Sub-species note
    if char.sub_species == SubSpecies.FERAL:
        parts.append("with feral instincts that make others uneasy")
    elif char.sub_species == SubSpecies.HULKER:
        parts.append("towering and thick-skinned, impossible to ignore in a room")
    elif char.sub_species == SubSpecies.STALKER:
        parts.append("eerily quiet, always watching from the periphery")
    elif char.sub_species == SubSpecies.SOULLESS:
        parts.append("with a flat affect that unsettles even the crew")

    # Join into prose
    text = ". ".join(parts[:2]) + "." if len(parts) >= 2 else parts[0] + "."
    if len(parts) > 2:
        text = text[:-1] + ", " + ". ".join(parts[2:]) + "."

    return text


def generate_character_backgrounds_api(
    characters: list[Character],
    agenda: ColonizationAgenda,
    colony_name: str = "the colony",
    api_key: str = "",
) -> None:
    """Generate narrative backgrounds for all characters in a single API call.

    Modifies characters in-place. Falls back to local generation on failure.
    """
    if not api_key:
        for char in characters:
            char.narrative_background = generate_character_background_local(
                char, characters,
            )
        return

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        from planetfall.config import get_background_model
        model = get_background_model()

        prompt = _build_batch_background_prompt(characters, agenda, colony_name)
        from planetfall.api_tracker import tracked_api_call
        message = tracked_api_call(
            client, caller="background_gen",
            model=model,
            max_tokens=250 * len(characters),
            messages=[{"role": "user", "content": prompt}],
        )
        _parse_batch_backgrounds(message.content[0].text, characters)

    except Exception:
        # Fall back to local generation for any characters not yet filled
        for char in characters:
            if not char.narrative_background:
                char.narrative_background = generate_character_background_local(
                    char, characters,
                )


def _build_batch_background_prompt(
    characters: list[Character],
    agenda: ColonizationAgenda,
    colony_name: str,
) -> str:
    """Build a single prompt to generate backgrounds for all characters."""
    char_blocks = []
    for char in characters:
        subspecies_note = ""
        if char.sub_species != SubSpecies.STANDARD:
            subspecies_note = f"  Sub-species: {char.sub_species.value}\n"
        block = (
            f"[{char.name}]\n"
            f"  Class: {char.char_class.value}\n"
            f"{subspecies_note}"
            f"  Title: {char.title or 'None'}\n"
            f"  Role: {char.role or char.char_class.value}\n"
            f"  Motivation: {char.background_motivation or 'Unknown'}\n"
            f"  Prior Experience: {char.background_prior_experience or 'None — fresh recruit'}\n"
            f"  Loyalty: {char.loyalty.value}"
        )
        char_blocks.append(block)

    roster = "\n\n".join(char_blocks)

    return f"""Write a 2-3 sentence narrative background for EACH character in a gritty frontier sci-fi colony crew.
These are personality references for narrating scenes — keep them punchy and specific.

COLONIZATION AGENDA: {agenda.value}
COLONY: {colony_name}

CREW ROSTER:
{roster}

For each character, write a brief personality sketch: who they are, why they joined, and one distinctive trait.
Reference their motivation and prior experience naturally. Keep it grounded, no purple prose.
Characters should feel interconnected — they know each other.

Format your response EXACTLY as:
[Character Name]
Background text here.

[Next Character Name]
Background text here.

Do NOT include the character's name in the background text itself — just the description."""


def _parse_batch_backgrounds(text: str, characters: list[Character]) -> None:
    """Parse batch API response and assign backgrounds to characters."""
    import re
    # Split on [Name] headers
    sections = re.split(r'\[([^\]]+)\]', text.strip())
    # sections = ['', 'Name1', '\ntext1\n', 'Name2', '\ntext2\n', ...]

    name_to_char = {c.name.lower(): c for c in characters}

    for i in range(1, len(sections) - 1, 2):
        header = sections[i].strip().lower()
        body = sections[i + 1].strip()
        if body and header in name_to_char:
            name_to_char[header].narrative_background = body


# --- Map generation ---


def generate_campaign_map(
    rows: int = 6,
    cols: int = 6,
    colony_sector: Optional[int] = None,
    num_investigation_sites: int = 10,
    num_ancient_signs: int = 3,
) -> CampaignMap:
    """Generate the campaign map with sectors, investigation sites, and ancient signs."""
    total_sectors = rows * cols

    # Create sectors
    sectors = [
        Sector(sector_id=i) for i in range(total_sectors)
    ]

    # Place colony centrally (within the center 2x2 area)
    if colony_sector is None:
        center_rows = [rows // 2 - 1, rows // 2]
        center_cols = [cols // 2 - 1, cols // 2]
        center_sectors = [r * cols + c for r in center_rows for c in center_cols]
        colony_sector = random.choice(center_sectors)
    sectors[colony_sector].status = SectorStatus.EXPLOITED
    sectors[colony_sector].notes = "Colony"

    # Place investigation sites
    available = [
        s.sector_id for s in sectors
        if s.sector_id != colony_sector
    ]
    random.shuffle(available)
    for i in range(min(num_investigation_sites, len(available))):
        sectors[available[i]].has_investigation_site = True

    # Place ancient signs
    remaining = [
        sid for sid in available[num_investigation_sites:]
    ] + [
        sid for sid in available[:num_investigation_sites]
    ]
    random.shuffle(remaining)
    signs_placed = 0
    for sid in remaining:
        if sid != colony_sector and signs_placed < num_ancient_signs:
            sectors[sid].has_ancient_sign = True
            signs_placed += 1

    return CampaignMap(sectors=sectors, colony_sector_id=colony_sector)


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

    return state

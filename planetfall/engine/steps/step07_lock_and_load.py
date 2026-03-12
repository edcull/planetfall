"""Step 7: Lock and Load — Deploy characters and equip them."""

from __future__ import annotations

from planetfall.engine.models import (
    Character, CharacterClass, Fireteam, GameState,
    TurnEvent, TurnEventType,
)


# Default deployment slots by mission type
MISSION_SLOTS = {
    "investigation": 4,
    "scouting": 4,
    "exploration": 6,
    "science": 4,
    "hunt": 5,
    "patrol": 5,
    "skirmish": 6,
    "rescue": 6,  # Any combo of characters + grunts
    "scout_down": 4,
    "pitched_battle": 8,  # Full roster
    "strike": 5,
    "assault": 8,  # Full roster
    "delve": 5,
}


def get_available_characters(state: GameState) -> list[Character]:
    """Get characters available for deployment (not in sick bay)."""
    return [c for c in state.characters if c.is_available]


def get_deployment_slots(mission_type: str) -> int:
    """Get max character slots for a mission type."""
    return MISSION_SLOTS.get(mission_type, 5)


def validate_deployment(
    state: GameState,
    character_names: list[str],
    mission_type: str,
) -> tuple[bool, str]:
    """Validate a proposed deployment.

    Returns (is_valid, message).
    """
    max_slots = get_deployment_slots(mission_type)
    available = get_available_characters(state)
    available_names = {c.name for c in available}

    # Check all selected characters are available
    for name in character_names:
        if name not in available_names:
            return False, f"{name} is not available (may be in Sick Bay)."

    if len(character_names) > max_slots:
        return False, (
            f"Too many characters selected ({len(character_names)}). "
            f"Max for {mission_type}: {max_slots}."
        )

    return True, "Deployment valid."


def organize_fireteams(state: GameState, grunt_count: int) -> list[Fireteam]:
    """Organize grunts into fireteams (2-4 per team, 5+ = 2 teams)."""
    if grunt_count <= 0:
        return []
    if grunt_count <= 4:
        return [Fireteam(name="Fireteam Alpha", size=grunt_count)]
    # Split into two teams
    half = grunt_count // 2
    return [
        Fireteam(name="Fireteam Alpha", size=half),
        Fireteam(name="Fireteam Bravo", size=grunt_count - half),
    ]


def execute(
    state: GameState,
    deployed_characters: list[str],
    deployed_grunts: int = 0,
    mission_type: str = "patrol",
    deployed_bot: bool = False,
) -> list[TurnEvent]:
    """Record deployment for the mission."""
    events = []

    fireteams = organize_fireteams(state, deployed_grunts)
    state.grunts.fireteams = fireteams

    char_list = ", ".join(deployed_characters) or "None"
    desc = (
        f"Deployed for {mission_type.replace('_', ' ').title()}: "
        f"{char_list}."
    )
    if deployed_grunts > 0:
        team_desc = ", ".join(f"{ft.name} ({ft.size})" for ft in fireteams)
        desc += f" Grunts: {deployed_grunts} ({team_desc})."
    if deployed_bot:
        desc += " Bot: Deployed."

    events.append(TurnEvent(
        step=7,
        event_type=TurnEventType.MISSION,
        description=desc,
        state_changes={
            "deployed": deployed_characters,
            "grunts": deployed_grunts,
            "bot": deployed_bot,
            "fireteams": [ft.model_dump() for ft in fireteams],
        },
    ))
    return events

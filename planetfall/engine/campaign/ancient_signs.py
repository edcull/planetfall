"""Ancient Signs quest line — discover alien artifacts and mission data breakthroughs.

Ancient Signs are collected from post-mission finds, milestones, and
exploration. Accumulating signs unlocks ancient sites which can be
explored for mission data breakthroughs.
"""

from __future__ import annotations

import random
from planetfall.engine.dice import roll_d6, roll_d100
from planetfall.engine.models import GameState, TurnEvent, TurnEventType


# Mission Data Breakthrough table (D100)
BREAKTHROUGH_TABLE = {
    (1, 25): {
        "id": "ancient_colony",
        "name": "Ancient Colony Discovered",
        "description": (
            "Ruins of a pre-collapse colony found. Add 2 Ancient Sites "
            "to random sectors. Bonus for Loyalty endgame path."
        ),
        "ancient_sites": 2,
        "endgame_bonus": "Loyalty",
    },
    (26, 50): {
        "id": "ancient_factory",
        "name": "Ancient Factory",
        "description": (
            "A functional alien fabricator is recovered. "
            "+1 Build Point per turn permanently."
        ),
        "bp_per_turn": 1,
        "endgame_bonus": "Loyalty",
    },
    (51, 75): {
        "id": "artificial_construction",
        "name": "Artificial Construction",
        "description": (
            "Evidence of massive engineering projects. "
            "+3 Story Points, +2 XP to 3 characters."
        ),
        "story_points": 3,
        "xp_bonus": 2,
        "xp_count": 3,
        "endgame_bonus": "Independence",
    },
    (76, 100): {
        "id": "defense_network",
        "name": "Defense Network",
        "description": (
            "An ancient defensive grid is partially restored. "
            "+2 Colony Defense, +1 Colony Integrity."
        ),
        "colony_defense": 2,
        "colony_integrity": 1,
        "endgame_bonus": "Independence",
    },
}


def check_ancient_signs(state: GameState) -> list[TurnEvent]:
    """Check if accumulated ancient signs trigger a site discovery.

    Every 3 ancient signs, a new ancient site appears on the map.
    """
    signs = state.campaign.ancient_signs_count
    sites_discovered = state.tracking.ancient_sites_total
    expected_sites = signs // 3

    events = []
    while sites_discovered < expected_sites:
        sites_discovered += 1
        # Place ancient site in a random explored sector
        explored = [
            s for s in state.campaign_map.sectors
            if not s.has_ancient_site
            and s.sector_id != state.campaign_map.colony_sector_id
        ]
        if explored:
            sector = random.choice(explored)
            sector.has_ancient_site = True
            events.append(TurnEvent(
                step=0, event_type=TurnEventType.NARRATIVE,
                description=(
                    f"Ancient Site discovered in sector {sector.sector_id}! "
                    f"An alien structure of unknown origin awaits exploration."
                ),
                state_changes={"ancient_site_sector": sector.sector_id},
            ))

    state.tracking.ancient_sites_total = sites_discovered
    return events


def explore_ancient_site(
    state: GameState, sector_id: int
) -> list[TurnEvent]:
    """Explore an ancient site for mission data.

    Requires sending a team to the sector. Rolls for mission data
    breakthrough.
    """
    sector = None
    for s in state.campaign_map.sectors:
        if s.sector_id == sector_id:
            sector = s
            break

    if not sector or not sector.has_ancient_site:
        return [TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=f"No ancient site in sector {sector_id}.",
        )]

    # Mark as explored
    sector.has_ancient_site = False
    state.campaign.mission_data_count += 1

    events = [TurnEvent(
        step=0, event_type=TurnEventType.NARRATIVE,
        description=(
            f"Ancient site in sector {sector_id} explored. "
            f"+1 Mission Data. Total: {state.campaign.mission_data_count}"
        ),
    )]

    # Check for breakthrough
    events.extend(check_mission_data_breakthrough(state))

    return events


def check_mission_data_breakthrough(state: GameState) -> list[TurnEvent]:
    """Check if mission data triggers a breakthrough.

    Roll 1D6; if <= total mission data count, breakthrough occurs.
    """
    data_count = state.campaign.mission_data_count
    if data_count <= 0:
        return []

    roll = roll_d6("Mission Data Breakthrough check")
    if roll.total > data_count:
        return [TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=(
                f"Mission Data check: {roll.total} > {data_count}. "
                f"No breakthrough yet."
            ),
        )]

    # Breakthrough! Roll on table
    occurred = list(state.tracking.breakthroughs)
    bt_roll = roll_d100("Breakthrough Table")
    breakthrough = None
    for (low, high), entry in BREAKTHROUGH_TABLE.items():
        if low <= bt_roll.total <= high:
            breakthrough = entry
            break

    if not breakthrough:
        return []

    # Skip duplicates
    if breakthrough["id"] in occurred:
        for (low, high), entry in BREAKTHROUGH_TABLE.items():
            if entry["id"] not in occurred:
                breakthrough = entry
                break
        else:
            return [TurnEvent(
                step=0, event_type=TurnEventType.NARRATIVE,
                description="All breakthroughs already discovered!",
            )]

    occurred.append(breakthrough["id"])
    state.tracking.breakthroughs = occurred

    events = [TurnEvent(
        step=0, event_type=TurnEventType.NARRATIVE,
        description=(
            f"=== MISSION DATA BREAKTHROUGH: {breakthrough['name']} === "
            f"{breakthrough['description']}"
        ),
        state_changes={"breakthrough": breakthrough["id"]},
    )]

    # Apply effects
    if breakthrough.get("ancient_sites"):
        for _ in range(breakthrough["ancient_sites"]):
            explored = [
                s for s in state.campaign_map.sectors
                if not s.has_ancient_site
            ]
            if explored:
                sector = random.choice(explored)
                sector.has_ancient_site = True

    if breakthrough.get("bp_per_turn"):
        state.colony.per_turn_rates.build_points += breakthrough["bp_per_turn"]
        events.append(TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=f"+{breakthrough['bp_per_turn']} BP per turn permanently.",
        ))

    if breakthrough.get("story_points"):
        state.colony.resources.story_points += breakthrough["story_points"]

    if breakthrough.get("xp_bonus") and breakthrough.get("xp_count"):
        chars = random.sample(
            state.characters,
            min(breakthrough["xp_count"], len(state.characters))
        )
        for c in chars:
            c.xp += breakthrough["xp_bonus"]
        names = ", ".join(c.name for c in chars)
        events.append(TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=f"+{breakthrough['xp_bonus']} XP to: {names}",
        ))

    if breakthrough.get("colony_defense"):
        state.colony.defenses += breakthrough["colony_defense"]

    if breakthrough.get("colony_integrity"):
        state.colony.integrity += breakthrough["colony_integrity"]

    return events

"""Ancient Signs quest line — discover alien artifacts and mission data breakthroughs.

Ancient Signs are collected from post-mission finds, milestones, and
exploration. Accumulating signs unlocks ancient sites which can be
explored for mission data breakthroughs.

Mission Data Breakthroughs are sequential (1st through 4th).
The 4th breakthrough rolls on a D100 table with 11 possible outcomes.
"""

from __future__ import annotations

import random
from planetfall.engine.dice import roll_d6, roll_d100
from planetfall.engine.models import GameState, TurnEvent, TurnEventType, DiceRoll


# --- 4th Breakthrough D100 table (11 entries) ---

FOURTH_BREAKTHROUGH_TABLE = {
    (1, 10): {
        "id": "ancient_colony",
        "name": "Ancient Colony",
        "description": (
            "Remnants of ruins make it clear this was once a colony. "
            "Add 2 Ancient Sites to your map in random sectors."
        ),
        "ancient_sites": 2,
        "endgame_bonus": "Loyalty",
    },
    (11, 20): {
        "id": "ancient_factory",
        "name": "Ancient Factory",
        "description": (
            "The world was intended as a site for a massive factory. "
            "+1 Build Point per turn permanently."
        ),
        "bp_per_turn": 1,
        "endgame_bonus": "Loyalty",
    },
    (21, 30): {
        "id": "artificial_construction",
        "name": "Artificial Construction",
        "description": (
            "Evidence points to the planet itself having been manufactured. "
            "+3 Story Points, +2 XP to 3 characters."
        ),
        "story_points": 3,
        "xp_bonus": 2,
        "xp_count": 3,
        "endgame_bonus": "Independence",
    },
    (31, 40): {
        "id": "defense_network",
        "name": "Defense Network",
        "description": (
            "The planet bears signs of a grand defensive network. "
            "Sleepers no longer receive a Saving Throw against your attacks."
        ),
        "sleeper_no_save": True,
        "endgame_bonus": "Independence",
    },
    (41, 50): {
        "id": "moved_in_time_or_space",
        "name": "Moved in Time or Space",
        "description": (
            "This world's location or timeline has been manipulated. "
            "+10 Research Points."
        ),
        "research_points": 10,
        "endgame_bonus": "Ascension",
    },
    (51, 60): {
        "id": "psionic_manipulation",
        "name": "Psionic Manipulation",
        "description": (
            "The world has been subjected to massive psionic engineering. "
            "+1 Reactions to 3 characters."
        ),
        "reactions_bonus": 1,
        "reactions_count": 3,
        "endgame_bonus": "Isolation",
    },
    (61, 70): {
        "id": "semi_living_organism",
        "name": "Semi-Living Organism",
        "description": (
            "The entire planet appears to be a cohesive organism. "
            "Reduce all current and future Hazard levels by -1."
        ),
        "hazard_reduction": 1,
        "endgame_bonus": "Isolation",
    },
    (71, 80): {
        "id": "signs_of_genetic_modification",
        "name": "Signs of Genetic Modification",
        "description": (
            "The Lifeforms on this world are the result of intentional "
            "genetic modification. +5 Augmentation Points."
        ),
        "augmentation_points": 5,
        "endgame_bonus": "Ascension",
    },
    (81, 90): {
        "id": "terraforming",
        "name": "Terraforming",
        "description": (
            "The world underwent massive terraforming efforts. "
            "+10 Build Points."
        ),
        "build_points": 10,
        "endgame_bonus": "Loyalty",
    },
    (91, 100): {
        "id": "warzone",
        "name": "Warzone",
        "description": (
            "The world bears the scars of a massive conflict. "
            "+4 Grunts, +3 Research Points."
        ),
        "grunts": 4,
        "research_points": 3,
        "endgame_bonus": "Independence",
    },
}

# Keep legacy alias for any code referencing the old table
BREAKTHROUGH_TABLE = FOURTH_BREAKTHROUGH_TABLE


def check_ancient_signs(state: GameState, signs_obtained: int = 1) -> list[TurnEvent]:
    """Roll to see if newly obtained ancient signs locate an Ancient Site.

    Per rules: each time you obtain a sign, roll 1D6. If <= your current
    sign count, you locate an Ancient Site and discard ALL signs.
    Multiple signs in one turn are tested one at a time; on success,
    discard tested signs and start over with remaining.

    Args:
        signs_obtained: Number of new signs obtained this check (usually 1).
    """
    events = []

    for i in range(signs_obtained):
        signs = state.campaign.ancient_signs_count
        if signs <= 0:
            break

        roll = roll_d6("Ancient Sign check")
        events.append(TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=(
                f"Ancient Sign check: rolled {roll.total} vs {signs} signs."
            ),
            dice_rolls=[DiceRoll(
                dice_type="d6", values=roll.values,
                total=roll.total, label="Ancient Sign check",
            )],
        ))

        if roll.total <= signs:
            # Success — locate an Ancient Site, discard all signs
            state.campaign.ancient_signs_count = 0
            state.tracking.ancient_sites_total += 1

            # Place site in a random sector
            candidates = [
                s for s in state.campaign_map.sectors
                if not s.has_ancient_site
                and s.sector_id != state.campaign_map.colony_sector_id
            ]
            if candidates:
                sector = random.choice(candidates)
                sector.has_ancient_site = True
                events.append(TurnEvent(
                    step=0, event_type=TurnEventType.NARRATIVE,
                    description=(
                        f"Ancient Site located in sector {sector.sector_id}! "
                        f"All Ancient Signs discarded. "
                        f"A Delve expedition can now be carried out."
                    ),
                    state_changes={"ancient_site_sector": sector.sector_id},
                ))
            else:
                events.append(TurnEvent(
                    step=0, event_type=TurnEventType.NARRATIVE,
                    description=(
                        "Ancient Site located but no eligible sector available. "
                        "All Ancient Signs discarded."
                    ),
                ))
            # After success, remaining signs start from 0
            break
        else:
            events[-1] = TurnEvent(
                step=0, event_type=TurnEventType.NARRATIVE,
                description=(
                    f"Ancient Sign check: rolled {roll.total} vs {signs} signs — "
                    f"not enough data yet."
                ),
                dice_rolls=[DiceRoll(
                    dice_type="d6", values=roll.values,
                    total=roll.total, label="Ancient Sign check",
                )],
            )

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
    bonus = sector.ancient_site_bonus_mission_data
    sector.ancient_site_bonus_mission_data = 0
    mission_data_gained = 1 + bonus
    state.campaign.mission_data_count += mission_data_gained

    # Record explored site
    finding = f"+{mission_data_gained} Mission Data"
    from planetfall.engine.models import ExploredAncientSite
    state.tracking.explored_ancient_sites.append(ExploredAncientSite(
        sector_id=sector_id,
        name=sector.name or f"Sector {sector_id}",
        finding=finding,
    ))

    events = [TurnEvent(
        step=0, event_type=TurnEventType.NARRATIVE,
        description=(
            f"Ancient site in sector {sector_id} explored. "
            f"+{mission_data_gained} Mission Data. Total: {state.campaign.mission_data_count}"
        ),
    )]

    # Check for breakthrough
    events.extend(check_mission_data_breakthrough(state))

    return events


def check_mission_data_breakthrough(state: GameState) -> list[TurnEvent]:
    """Check if mission data triggers a breakthrough.

    Roll 1D6; if <= total mission data count, breakthrough occurs.
    Reduce mission data by the roll. Breakthroughs are sequential (1st-4th).
    """
    data_count = state.campaign.mission_data_count
    if data_count <= 0:
        return []

    # All 4 breakthroughs already achieved
    if state.tracking.breakthroughs_count >= 4:
        return []

    roll = roll_d6("Mission Data Breakthrough check")
    if roll.total > data_count:
        return [TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=(
                f"Mission Data check: rolled {roll.total} > {data_count}. "
                f"No breakthrough yet."
            ),
            dice_rolls=[DiceRoll(
                dice_type="d6", values=roll.values,
                total=roll.total, label="Mission Data check",
            )],
        )]

    # Breakthrough! Reduce mission data by the roll
    state.campaign.mission_data_count -= roll.total
    state.tracking.breakthroughs_count += 1
    bt_num = state.tracking.breakthroughs_count

    events = [TurnEvent(
        step=0, event_type=TurnEventType.NARRATIVE,
        description=(
            f"MISSION DATA BREAKTHROUGH #{bt_num}! "
            f"Rolled {roll.total} ≤ {data_count}. "
            f"Mission Data reduced by {roll.total} (now {state.campaign.mission_data_count})."
        ),
        dice_rolls=[DiceRoll(
            dice_type="d6", values=roll.values,
            total=roll.total, label="Mission Data Breakthrough",
        )],
    )]

    # Apply the sequential breakthrough
    if bt_num == 1:
        events.extend(_apply_first_breakthrough(state))
    elif bt_num == 2:
        events.extend(_apply_second_breakthrough(state))
    elif bt_num == 3:
        events.extend(_apply_third_breakthrough(state))
    elif bt_num == 4:
        events.extend(_apply_fourth_breakthrough(state))

    return events


def _apply_first_breakthrough(state: GameState) -> list[TurnEvent]:
    """1st Breakthrough: Discover 2 Ancient Sites + 1 Mission Data each."""
    events = []
    for _ in range(2):
        candidates = [
            s for s in state.campaign_map.sectors
            if not s.has_ancient_site
            and s.sector_id != state.campaign_map.colony_sector_id
        ]
        if candidates:
            sector = random.choice(candidates)
            sector.has_ancient_site = True
            sector.ancient_site_bonus_mission_data = 1
            events.append(TurnEvent(
                step=0, event_type=TurnEventType.NARRATIVE,
                description=f"Ancient Site placed in sector {sector.sector_id}.",
                state_changes={"ancient_site_sector": sector.sector_id},
            ))

    state.tracking.breakthroughs.append("first_breakthrough")
    events.insert(0, TurnEvent(
        step=0, event_type=TurnEventType.NARRATIVE,
        description=(
            "1st Breakthrough: 2 Ancient Sites discovered! "
            "Exploring each awards +1 Mission Data."
        ),
        state_changes={"breakthrough": "first_breakthrough"},
    ))
    return events


def _apply_second_breakthrough(state: GameState) -> list[TurnEvent]:
    """2nd Breakthrough: 4 random sectors become Explored, +2 Resource each."""
    events = []
    from planetfall.engine.models import SectorStatus

    unexplored = [
        s for s in state.campaign_map.sectors
        if s.status != SectorStatus.EXPLORED
        and s.sector_id != state.campaign_map.colony_sector_id
    ]
    chosen = random.sample(unexplored, min(4, len(unexplored)))
    for sector in chosen:
        sector.status = SectorStatus.EXPLORED
        sector.resource_level = min(sector.resource_level + 2, 5)
        events.append(TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=f"Sector {sector.sector_id} explored! Resource level +2 (now {sector.resource_level}).",
        ))

    state.tracking.breakthroughs.append("second_breakthrough")
    events.insert(0, TurnEvent(
        step=0, event_type=TurnEventType.NARRATIVE,
        description=(
            "2nd Breakthrough: Resource caches discovered! "
            f"{len(chosen)} sectors explored with +2 Resource each."
        ),
        state_changes={"breakthrough": "second_breakthrough"},
    ))
    return events


def _apply_third_breakthrough(state: GameState) -> list[TurnEvent]:
    """3rd Breakthrough: Mark 2 sectors for Investigation."""
    events = []
    candidates = [
        s for s in state.campaign_map.sectors
        if not s.has_investigation_site
        and s.sector_id != state.campaign_map.colony_sector_id
    ]
    chosen = random.sample(candidates, min(2, len(candidates)))
    for sector in chosen:
        sector.has_investigation_site = True
        events.append(TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=f"Sector {sector.sector_id} marked for Investigation.",
        ))

    state.tracking.breakthroughs.append("third_breakthrough")
    events.insert(0, TurnEvent(
        step=0, event_type=TurnEventType.NARRATIVE,
        description="3rd Breakthrough: New areas of interest identified for investigation.",
        state_changes={"breakthrough": "third_breakthrough"},
    ))
    return events


def _apply_fourth_breakthrough(state: GameState) -> list[TurnEvent]:
    """4th Breakthrough: Roll D100 on the final breakthrough table."""
    events = []
    bt_roll = roll_d100("4th Breakthrough Table")
    breakthrough = None
    for (low, high), entry in FOURTH_BREAKTHROUGH_TABLE.items():
        if low <= bt_roll.total <= high:
            breakthrough = entry
            break

    if not breakthrough:
        return events

    state.tracking.breakthroughs.append(breakthrough["id"])

    events.append(TurnEvent(
        step=0, event_type=TurnEventType.NARRATIVE,
        description=(
            f"4th & FINAL Breakthrough: {breakthrough['name']}! "
            f"(D100: {bt_roll.total}) {breakthrough['description']} "
            f"Mission Data no longer has any value."
        ),
        state_changes={"breakthrough": breakthrough["id"]},
        dice_rolls=[DiceRoll(
            dice_type="d100", values=[bt_roll.total],
            total=bt_roll.total, label="4th Breakthrough",
        )],
    ))

    # Apply specific effects
    if breakthrough.get("ancient_sites"):
        for _ in range(breakthrough["ancient_sites"]):
            candidates = [s for s in state.campaign_map.sectors if not s.has_ancient_site]
            if candidates:
                sector = random.choice(candidates)
                sector.has_ancient_site = True

    if breakthrough.get("bp_per_turn"):
        state.colony.per_turn_rates.build_points += breakthrough["bp_per_turn"]
        events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                description=f"+{breakthrough['bp_per_turn']} BP per turn permanently."))

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
        events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                description=f"+{breakthrough['xp_bonus']} XP to: {names}"))

    if breakthrough.get("sleeper_no_save"):
        state.tracking.sleeper_no_save = True
        events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                description="Sleepers no longer receive a Saving Throw."))

    if breakthrough.get("research_points"):
        state.colony.resources.research_points += breakthrough["research_points"]
        events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                description=f"+{breakthrough['research_points']} Research Points."))

    if breakthrough.get("reactions_bonus"):
        chars = random.sample(
            state.characters,
            min(breakthrough.get("reactions_count", 3), len(state.characters))
        )
        for c in chars:
            c.reactions += breakthrough["reactions_bonus"]
        names = ", ".join(c.name for c in chars)
        events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                description=f"+{breakthrough['reactions_bonus']} Reactions to: {names}"))

    if breakthrough.get("hazard_reduction"):
        for sector in state.campaign_map.sectors:
            sector.hazard_level = max(0, sector.hazard_level - breakthrough["hazard_reduction"])
        state.tracking.hazard_level_reduction = breakthrough["hazard_reduction"]
        events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                description="All Hazard levels reduced by -1."))

    if breakthrough.get("augmentation_points"):
        state.colony.resources.augmentation_points += breakthrough["augmentation_points"]
        events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                description=f"+{breakthrough['augmentation_points']} Augmentation Points."))

    if breakthrough.get("build_points"):
        state.colony.resources.build_points += breakthrough["build_points"]
        events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                description=f"+{breakthrough['build_points']} Build Points."))

    if breakthrough.get("grunts"):
        state.grunts.count += breakthrough["grunts"]
        events.append(TurnEvent(step=0, event_type=TurnEventType.NARRATIVE,
                                description=f"+{breakthrough['grunts']} Grunts."))

    if breakthrough.get("research_points") and breakthrough.get("grunts"):
        # Warzone gives both — already handled above
        pass

    return events

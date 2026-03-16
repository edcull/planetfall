"""Step 6: Mission Determination — Determine which mission to play."""

from __future__ import annotations

from planetfall.engine.models import (
    GameState, MissionType, SectorStatus, TurnEvent, TurnEventType,
)
from planetfall.engine.utils import format_display


def get_available_missions(state: GameState) -> list[dict]:
    """Determine which missions are available based on current game state.

    Returns list of dicts with keys:
        type, description, rewards, sector_id (optional),
        target_sectors (optional), forced (optional).
    """
    available = []

    # Check for forced missions from turn events
    for event in state.turn_log:
        if event.state_changes.get("forced_mission") == "pitched_battle":
            return [{"type": MissionType.PITCHED_BATTLE,
                      "description": "Enemy attack! You must defend the colony.",
                      "rewards": "Colony survival. Failure costs morale and integrity.",
                      "forced": True}]

    # Patrol — always available, within 2 of colony, not enemy-occupied
    from planetfall.engine.utils import sectors_within_distance
    patrol_sectors = [
        sid for sid in sectors_within_distance(state, state.campaign_map.colony_sector_id, 2)
        if not state.campaign_map.sectors[sid].enemy_occupied_by
    ]
    patrol_entry: dict = {
        "type": MissionType.PATROL,
        "description": "Patrol near the colony to deal with hostile wildlife.",
        "rewards": "Increase Colony Morale.",
    }
    if patrol_sectors:
        patrol_entry["target_sectors"] = patrol_sectors
    available.append(patrol_entry)

    # Investigation — if any sectors have investigation sites
    inv_sectors = [
        s for s in state.campaign_map.sectors
        if s.has_investigation_site
        and s.status in (SectorStatus.UNEXPLORED, SectorStatus.EXPLORED,
                         SectorStatus.EXPLOITED)
    ]
    if inv_sectors:
        if len(inv_sectors) == 1:
            available.append({
                "type": MissionType.INVESTIGATION,
                "description": f"Investigate sector {inv_sectors[0].sector_id}.",
                "rewards": "Potential Mission Data.",
                "sector_id": inv_sectors[0].sector_id,
            })
        else:
            available.append({
                "type": MissionType.INVESTIGATION,
                "description": f"Search an Investigation Site ({len(inv_sectors)} available).",
                "rewards": "Potential Mission Data.",
                "target_sectors": [s.sector_id for s in inv_sectors],
            })

    # Scouting — unexplored sectors
    unexplored = [
        s for s in state.campaign_map.sectors
        if s.status == SectorStatus.UNEXPLORED
        and s.sector_id != state.campaign_map.colony_sector_id
    ]
    if unexplored:
        available.append({
            "type": MissionType.SCOUTING,
            "description": f"Survey a Sector ({len(unexplored)} available).",
            "rewards": "Surveys a sector.",
            "target_sectors": [s.sector_id for s in unexplored],
        })

    # Exploration — explored but unexploited sectors
    explored = [
        s for s in state.campaign_map.sectors
        if s.status == SectorStatus.EXPLORED
        and s.sector_id != state.campaign_map.colony_sector_id
    ]
    if explored:
        sector_info = [
            f"{s.sector_id} (R{s.resource_level}/H{s.hazard_level})"
            for s in explored
        ]
        available.append({
            "type": MissionType.EXPLORATION,
            "description": f"Extract Raw Materials ({len(explored)} available).",
            "rewards": "Extract Raw Materials and Research Samples.",
            "target_sectors": [s.sector_id for s in explored],
            "target_details": sector_info,
        })

    # Science — explored sectors
    if explored:
        available.append({
            "type": MissionType.SCIENCE,
            "description": f"Obtain Research Samples ({len(explored)} available).",
            "rewards": "Obtain Research Samples.",
            "target_sectors": [s.sector_id for s in explored],
        })

    # Hunt — if lifeforms have been encountered, within 4 of colony
    if state.enemies.lifeform_table:
        hunt_sectors = sectors_within_distance(
            state, state.campaign_map.colony_sector_id, 4,
        )
        hunt_entry: dict = {
            "type": MissionType.HUNT,
            "description": "Hunt dangerous lifeforms.",
            "rewards": "Recover specimens for Bio-analysis research.",
        }
        if hunt_sectors:
            hunt_entry["target_sectors"] = hunt_sectors
        available.append(hunt_entry)

    # Skirmish — if tactical enemies present
    active_enemies = [e for e in state.enemies.tactical_enemies if not e.defeated]
    if active_enemies:
        enemy = active_enemies[0]
        available.append({
            "type": MissionType.SKIRMISH,
            "description": "Engage an enemy in a skirmish.",
            "rewards": f"+1 Enemy Info on victory (have {enemy.enemy_info_count}). Disrupts enemy this turn.",
        })

    # Strike — if tactical enemies with patrols
    if active_enemies:
        enemy = active_enemies[0]
        available.append({
            "type": MissionType.STRIKE,
            "description": "Strike mission against an enemy.",
            "rewards": "+2 Enemy Info on victory. Harder fight than skirmish.",
        })

    # Assault — if strongpoint located
    strongpoint_enemies = [e for e in active_enemies if e.strongpoint_located]
    if strongpoint_enemies:
        enemy = strongpoint_enemies[0]
        available.append({
            "type": MissionType.ASSAULT,
            "description": "Assault an enemy strongpoint.",
            "rewards": "Defeats enemy faction permanently. High difficulty.",
        })

    # Delve — if ancient sites found
    ancient_sectors = [
        s for s in state.campaign_map.sectors if s.has_ancient_site
    ]
    if ancient_sectors:
        if len(ancient_sectors) == 1:
            available.append({
                "type": MissionType.DELVE,
                "description": f"Delve into ancient site in sector {ancient_sectors[0].sector_id}.",
                "rewards": "+1 Mission Data. Chance of unique tech discovery.",
                "sector_id": ancient_sectors[0].sector_id,
            })
        else:
            available.append({
                "type": MissionType.DELVE,
                "description": f"Delve into an ancient site ({len(ancient_sectors)} available).",
                "rewards": "+1 Mission Data. Chance of unique tech discovery.",
                "target_sectors": [s.sector_id for s in ancient_sectors],
            })

    # Rescue — if flagged by player choosing rescue in _handle_rescue_or_morale (forced)
    # Only match the explicit flag event (no "discovery" key), not the original table roll
    for event in state.turn_log:
        effects = event.state_changes.get("effects", {})
        if (isinstance(effects, dict)
                and effects.get("mission_option") == "rescue"
                and "discovery" not in event.state_changes):
            return [{
                "type": MissionType.RESCUE,
                "description": "Respond to distress signal.",
                "rewards": "Potential new crew member. +1 Story Point on victory.",
                "forced": True,
            }]

    # Scout Down — if flagged by player choosing rescue in _handle_scout_down (forced)
    # Only match the explicit flag event (no "discovery" key), not the original table roll
    for event in state.turn_log:
        effects = event.state_changes.get("effects", {})
        if (isinstance(effects, dict)
                and effects.get("mission_option") == "scout_down"
                and "discovery" not in event.state_changes):
            scout_name = event.state_changes.get("scout_at_risk", "your scout")
            return [{
                "type": MissionType.SCOUT_DOWN,
                "description": f"Scout Down! — rescue {scout_name} from the crash site.",
                "rewards": "+2 XP for rescued scout. Recovery of scout vehicle.",
                "forced": True,
            }]

    return available


def execute(state: GameState, chosen_mission: MissionType, sector_id: int | None = None) -> list[TurnEvent]:
    """Record the chosen mission for this turn."""
    events = [TurnEvent(
        step=6,
        event_type=TurnEventType.MISSION,
        description=f"Mission selected: {format_display(chosen_mission.value)}.",
        state_changes={"mission_type": chosen_mission.value, "sector_id": sector_id},
    )]
    return events

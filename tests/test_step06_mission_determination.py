"""Tests for Step 6: Mission Determination."""

from planetfall.engine.models import (
    MissionType, SectorStatus, TacticalEnemy, TurnEvent,
    TurnEventType,
)
from planetfall.engine.steps.step06_mission_determination import (
    execute, get_available_missions,
)


class TestAvailableMissions:
    def test_patrol_always_available(self, game_state):
        state = game_state
        missions = get_available_missions(state)
        types = [m["type"] for m in missions]
        assert MissionType.PATROL in types

    def test_forced_pitched_battle(self, game_state):
        state = game_state
        state.turn_log.append(TurnEvent(
            step=4, event_type=TurnEventType.ENEMY_ACTIVITY,
            description="Attack!",
            state_changes={"forced_mission": "pitched_battle"},
        ))
        missions = get_available_missions(state)
        assert len(missions) == 1
        assert missions[0]["type"] == MissionType.PITCHED_BATTLE
        assert missions[0].get("forced") is True

    def test_scouting_with_unexplored_sectors(self, game_state):
        state = game_state
        # Ensure at least one sector is UNKNOWN and not colony
        for s in state.campaign_map.sectors:
            if s.sector_id != state.campaign_map.colony_sector_id:
                s.status = SectorStatus.UNEXPLORED
                break
        missions = get_available_missions(state)
        types = [m["type"] for m in missions]
        assert MissionType.SCOUTING in types

    def test_investigation_with_site(self, game_state):
        state = game_state
        for s in state.campaign_map.sectors:
            if s.sector_id != state.campaign_map.colony_sector_id:
                s.has_investigation_site = True
                s.status = SectorStatus.UNEXPLORED
                break
        missions = get_available_missions(state)
        types = [m["type"] for m in missions]
        assert MissionType.INVESTIGATION in types

    def test_exploration_with_explored_sectors(self, game_state):
        state = game_state
        for s in state.campaign_map.sectors:
            if s.sector_id != state.campaign_map.colony_sector_id:
                s.status = SectorStatus.EXPLORED
                break
        missions = get_available_missions(state)
        types = [m["type"] for m in missions]
        assert MissionType.EXPLORATION in types
        assert MissionType.SCIENCE in types

    def test_hunt_with_lifeforms(self, game_state):
        state = game_state
        state.enemies.lifeform_table = [{"name": "Bug"}]
        missions = get_available_missions(state)
        types = [m["type"] for m in missions]
        assert MissionType.HUNT in types

    def test_skirmish_and_strike_with_enemies(self, game_state):
        state = game_state
        state.enemies.tactical_enemies = [
            TacticalEnemy(name="Raiders", enemy_type="Marauders", sectors=[1])
        ]
        missions = get_available_missions(state)
        types = [m["type"] for m in missions]
        assert MissionType.SKIRMISH in types
        assert MissionType.STRIKE in types

    def test_assault_with_strongpoint(self, game_state):
        state = game_state
        state.enemies.tactical_enemies = [
            TacticalEnemy(
                name="Raiders", enemy_type="Marauders", sectors=[1],
                strongpoint_located=True,
            )
        ]
        missions = get_available_missions(state)
        types = [m["type"] for m in missions]
        assert MissionType.ASSAULT in types

    def test_delve_with_ancient_site(self, game_state):
        state = game_state
        for s in state.campaign_map.sectors:
            s.has_ancient_site = True
            break
        missions = get_available_missions(state)
        types = [m["type"] for m in missions]
        assert MissionType.DELVE in types

    def test_rescue_from_turn_log(self, game_state):
        state = game_state
        state.turn_log.append(TurnEvent(
            step=3, event_type=TurnEventType.SCOUT_REPORT,
            description="Distress signal!",
            state_changes={"effects": {"mission_option": "rescue"}},
        ))
        missions = get_available_missions(state)
        types = [m["type"] for m in missions]
        assert MissionType.RESCUE in types


class TestExecute:
    def test_records_chosen_mission(self, game_state):
        state = game_state
        events = execute(state, MissionType.PATROL)
        assert len(events) == 1
        assert "Patrol" in events[0].description

    def test_records_sector_id(self, game_state):
        state = game_state
        events = execute(state, MissionType.SCOUTING, sector_id=3)
        assert events[0].state_changes["sector_id"] == 3

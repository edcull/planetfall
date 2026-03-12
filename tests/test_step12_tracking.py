"""Tests for Step 12: Track Enemy Information & Mission Data."""

from planetfall.engine.campaign.setup import create_new_campaign
from planetfall.engine.models import ColonizationAgenda, MissionType, TacticalEnemy
from planetfall.engine.steps.step12_tracking import execute


def _make_state():
    return create_new_campaign("T", "C", agenda=ColonizationAgenda.UNITY)


class TestMissionDataTracking:
    def test_exploration_victory_adds_mission_data(self):
        state = _make_state()
        old = state.campaign.mission_data_count
        events = execute(state, MissionType.EXPLORATION, mission_victory=True)
        assert state.campaign.mission_data_count == old + 1

    def test_science_victory_adds_mission_data(self):
        state = _make_state()
        old = state.campaign.mission_data_count
        events = execute(state, MissionType.SCIENCE, mission_victory=True)
        assert state.campaign.mission_data_count == old + 1

    def test_patrol_no_mission_data(self):
        state = _make_state()
        old = state.campaign.mission_data_count
        events = execute(state, MissionType.PATROL, mission_victory=True)
        assert state.campaign.mission_data_count == old

    def test_defeat_no_mission_data(self):
        state = _make_state()
        old = state.campaign.mission_data_count
        events = execute(state, MissionType.EXPLORATION, mission_victory=False)
        assert state.campaign.mission_data_count == old


class TestEnemyInformation:
    def test_skirmish_adds_1_info(self):
        state = _make_state()
        enemy = TacticalEnemy(name="Raiders", enemy_type="Marauders", sectors=[1])
        state.enemies.tactical_enemies = [enemy]
        events = execute(state, MissionType.SKIRMISH, mission_victory=True)
        assert enemy.enemy_info_count == 1

    def test_strike_adds_2_info(self):
        state = _make_state()
        enemy = TacticalEnemy(name="Raiders", enemy_type="Marauders", sectors=[1])
        state.enemies.tactical_enemies = [enemy]
        events = execute(state, MissionType.STRIKE, mission_victory=True)
        assert enemy.enemy_info_count == 2

    def test_strongpoint_located_at_3(self):
        state = _make_state()
        enemy = TacticalEnemy(name="Raiders", enemy_type="Marauders", sectors=[1])
        enemy.enemy_info_count = 1
        state.enemies.tactical_enemies = [enemy]
        events = execute(state, MissionType.STRIKE, mission_victory=True)
        assert enemy.enemy_info_count == 3
        assert enemy.strongpoint_located is True
        assert any("STRONGPOINT LOCATED" in e.description for e in events)


class TestAssaultVictory:
    def test_assault_defeats_enemy(self):
        state = _make_state()
        enemy = TacticalEnemy(
            name="Raiders", enemy_type="Marauders", sectors=[1],
            strongpoint_located=True,
        )
        state.enemies.tactical_enemies = [enemy]
        old_milestones = state.campaign.milestones_completed
        events = execute(state, MissionType.ASSAULT, mission_victory=True)
        assert enemy.defeated is True
        assert state.campaign.milestones_completed == old_milestones + 1
        assert any("ENEMY DEFEATED" in e.description for e in events)


class TestNoUpdates:
    def test_no_tracking_message(self):
        state = _make_state()
        events = execute(state, MissionType.PATROL, mission_victory=True)
        assert any("No tracking updates" in e.description for e in events)

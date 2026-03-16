"""Tests for Step 4: Enemy Activity."""

from unittest.mock import patch

from planetfall.engine.dice import RollResult, TableEntry
from planetfall.engine.models import TacticalEnemy
from planetfall.engine.steps.step04_enemy_activity import execute


class TestNoEnemies:
    def test_no_tactical_enemies(self, game_state):
        state = game_state
        state.enemies.tactical_enemies = []
        events = execute(state)
        assert len(events) == 1
        assert "No active" in events[0].description

    def test_all_enemies_defeated(self, game_state):
        state = game_state
        for e in state.enemies.tactical_enemies:
            e.defeated = True
        events = execute(state)
        assert "No active" in events[0].description

    def test_disrupted_enemy_skipped(self, game_state):
        state = game_state
        for e in state.enemies.tactical_enemies:
            e.disrupted_this_turn = True
        events = execute(state)
        assert "No active" in events[0].description


class TestEnemyActivity:
    @patch("planetfall.engine.steps.step04_enemy_activity.ENEMY_ACTIVITY_TABLE")
    def test_normal_activity(self, mock_table, game_state):
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[50], total=50, label=""),
            TableEntry(low=41, high=60, result_id="patrol",
                      description="Enemy patrols their territory.", effects={}),
        )
        state = game_state
        # Ensure at least one active enemy
        state.enemies.tactical_enemies = [
            TacticalEnemy(name="Raiders", enemy_type="Marauders", sectors=[1])
        ]
        events = execute(state)
        assert len(events) == 1
        assert "Raiders" in events[0].description
        assert "Patrol" in events[0].description

    @patch("planetfall.engine.steps.step04_enemy_activity.roll_d6")
    @patch("planetfall.engine.steps.step04_enemy_activity.ENEMY_ACTIVITY_TABLE")
    def test_raid_damages_colony(self, mock_table, mock_d6, game_state):
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[90], total=90, label=""),
            TableEntry(low=81, high=100, result_id="raid",
                      description="Enemy raids the colony!", effects={}),
        )
        mock_d6.return_value = RollResult(dice_type="d6", values=[3], total=3, label="")
        state = game_state
        state.enemies.tactical_enemies = [
            TacticalEnemy(name="Raiders", enemy_type="Marauders", sectors=[1, 2])
        ]
        state.colony.defenses = 0
        old_integrity = state.colony.integrity
        events = execute(state)
        # Damage = len(sectors) + 1 = 3
        assert state.colony.integrity == old_integrity - 3
        assert "Colony takes" in events[0].description

    @patch("planetfall.engine.steps.step04_enemy_activity.roll_d6")
    @patch("planetfall.engine.steps.step04_enemy_activity.ENEMY_ACTIVITY_TABLE")
    def test_raid_with_defenses(self, mock_table, mock_d6, game_state):
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[90], total=90, label=""),
            TableEntry(low=81, high=100, result_id="raid",
                      description="Enemy raids!", effects={}),
        )
        # Defense rolls: all succeed (4+)
        mock_d6.return_value = RollResult(dice_type="d6", values=[5], total=5, label="")
        state = game_state
        state.enemies.tactical_enemies = [
            TacticalEnemy(name="Raiders", enemy_type="Marauders", sectors=[1])
        ]
        state.colony.defenses = 2
        old_integrity = state.colony.integrity
        events = execute(state)
        # Damage = 2 (sectors+1), negated = 2 (defenses), actual = 0
        assert state.colony.integrity == old_integrity
        assert "negated by defenses" in events[0].description

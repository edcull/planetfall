"""Tests for Step 18: Update Colony Tracking Sheet."""

from unittest.mock import patch

from planetfall.engine.models import TacticalEnemy
from planetfall.engine.steps.step18_update_sheet import execute


class TestUpdateSheet:
    @patch("planetfall.engine.steps.step18_update_sheet.save_state")
    def test_advances_turn(self, mock_save, game_state):
        state = game_state
        old_turn = state.current_turn
        events = execute(state)
        assert state.current_turn == old_turn + 1
        assert f"Turn {old_turn} complete" in events[0].description

    @patch("planetfall.engine.steps.step18_update_sheet.save_state")
    def test_clears_turn_log(self, mock_save, game_state):
        state = game_state
        from planetfall.engine.models import TurnEvent, TurnEventType
        state.turn_log.append(TurnEvent(
            step=1, event_type=TurnEventType.RECOVERY, description="test",
        ))
        execute(state)
        assert len(state.turn_log) == 0

    @patch("planetfall.engine.steps.step18_update_sheet.save_state")
    def test_resets_disrupted_enemies(self, mock_save, game_state):
        state = game_state
        enemy = TacticalEnemy(
            name="Raiders", enemy_type="Marauders", sectors=[1],
            disrupted_this_turn=True,
        )
        state.enemies.tactical_enemies = [enemy]
        execute(state)
        assert enemy.disrupted_this_turn is False

    @patch("planetfall.engine.steps.step18_update_sheet.save_state")
    def test_saves_state(self, mock_save, game_state):
        state = game_state
        execute(state)
        mock_save.assert_called_once_with(state)

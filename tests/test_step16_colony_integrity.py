"""Tests for Step 16: Colony Integrity — Integrity Failure checks."""

from unittest.mock import patch

from planetfall.engine.dice import RollResult, TableEntry
from planetfall.engine.steps.step16_colony_integrity import execute


class TestStableColony:
    def test_positive_integrity(self, game_state):
        state = game_state
        state.colony.integrity = 2
        events = execute(state)
        assert "stable" in events[0].description.lower()

    def test_zero_integrity(self, game_state):
        state = game_state
        state.colony.integrity = 0
        events = execute(state)
        assert "stable" in events[0].description.lower()


class TestMinorDamage:
    def test_integrity_minus_1(self, game_state):
        state = game_state
        state.colony.integrity = -1
        events = execute(state)
        assert "no failure risk" in events[0].description.lower()

    def test_integrity_minus_2(self, game_state):
        state = game_state
        state.colony.integrity = -2
        events = execute(state)
        assert "no failure risk" in events[0].description.lower()


class TestSpendStoryPoint:
    def test_spend_sp_skips_roll(self, game_state):
        state = game_state
        state.colony.integrity = -5
        state.colony.resources.story_points = 2
        events = execute(state, spend_story_point=True)
        assert state.colony.resources.story_points == 1
        assert any("Story Point spent" in e.description for e in events)


class TestIntegrityFailureRoll:
    @patch("planetfall.engine.steps.step16_colony_integrity.roll_nd6")
    def test_roll_passes(self, mock_roll, game_state):
        mock_roll.return_value = RollResult(
            dice_type="3d6", values=[6, 5, 4], total=15, label=""
        )
        state = game_state
        state.colony.integrity = -5  # threshold = 5
        events = execute(state)
        assert "no failure this turn" in events[0].description.lower()

    @patch("planetfall.engine.steps.step16_colony_integrity.INTEGRITY_FAILURE_TABLE")
    @patch("planetfall.engine.steps.step16_colony_integrity.roll_nd6")
    def test_roll_fails_morale_loss(self, mock_roll, mock_table, game_state):
        mock_roll.return_value = RollResult(
            dice_type="3d6", values=[1, 1, 1], total=3, label=""
        )
        mock_table.lookup.return_value = TableEntry(
            low=3, high=3, result_id="minor_morale_loss",
            description="-1 Colony Morale.", effects={"morale": -1},
        )
        state = game_state
        state.colony.integrity = -5
        old_morale = state.colony.morale
        events = execute(state)
        assert state.colony.morale == old_morale - 1
        assert "INTEGRITY FAILURE" in events[0].description

    @patch("planetfall.engine.steps.step16_colony_integrity.INTEGRITY_FAILURE_TABLE")
    @patch("planetfall.engine.steps.step16_colony_integrity.roll_nd6")
    def test_roll_fails_colony_damage(self, mock_roll, mock_table, game_state):
        mock_roll.return_value = RollResult(
            dice_type="3d6", values=[2, 1, 2], total=5, label=""
        )
        mock_table.lookup.return_value = TableEntry(
            low=5, high=5, result_id="colony_damage_1",
            description="1 Colony Damage.", effects={"colony_damage": 1},
        )
        state = game_state
        state.colony.integrity = -5
        old_integrity = state.colony.integrity
        events = execute(state)
        assert state.colony.integrity == old_integrity - 1

    @patch("planetfall.engine.steps.step16_colony_integrity.INTEGRITY_FAILURE_TABLE")
    @patch("planetfall.engine.steps.step16_colony_integrity.roll_nd6")
    def test_roll_fails_bp_rp_penalty(self, mock_roll, mock_table, game_state):
        mock_roll.return_value = RollResult(
            dice_type="3d6", values=[2, 2, 2], total=6, label=""
        )
        mock_table.lookup.return_value = TableEntry(
            low=6, high=6, result_id="reduced_income",
            description="Reduced income.",
            effects={"bp_penalty_next": -2, "rp_penalty_next": -2},
        )
        state = game_state
        state.colony.integrity = -6
        events = execute(state)
        assert state.flags.bp_penalty_next == -2
        assert state.flags.rp_penalty_next == -2

    @patch("planetfall.engine.steps.step16_colony_integrity.CHARACTER_INJURY_TABLE")
    @patch("planetfall.engine.steps.step16_colony_integrity.INTEGRITY_FAILURE_TABLE")
    @patch("planetfall.engine.steps.step16_colony_integrity.roll_nd6")
    def test_roll_fails_character_slain(self, mock_roll, mock_table, mock_injury, game_state):
        mock_roll.return_value = RollResult(
            dice_type="3d6", values=[6, 6, 6], total=18, label=""
        )
        mock_table.lookup.return_value = TableEntry(
            low=18, high=18, result_id="character_slain",
            description="A character is slain.",
            effects={"character_slain": True},
        )
        state = game_state
        state.colony.integrity = -18
        old_count = len(state.characters)
        old_sp = state.colony.resources.story_points
        events = execute(state)
        assert len(state.characters) == old_count - 1
        assert state.colony.resources.story_points == old_sp + 1

"""Tests for Story Points spending mechanics."""

from unittest.mock import patch

import pytest

from planetfall.engine.campaign.setup import create_new_campaign
from planetfall.engine.campaign.story_points import (
    can_spend, spend_to_prevent_roll, spend_for_resources,
    spend_to_ignore_injury, spend_crisis_reroll,
)
from planetfall.engine.models import ColonizationAgenda, GameState


def _make_state() -> GameState:
    return create_new_campaign("T", "C", agenda=ColonizationAgenda.UNITY)


class TestCanSpend:
    def test_has_enough(self):
        state = _make_state()
        state.colony.resources.story_points = 3
        assert can_spend(state, 2) is True

    def test_not_enough(self):
        state = _make_state()
        state.colony.resources.story_points = 0
        assert can_spend(state, 1) is False

    def test_exact_amount(self):
        state = _make_state()
        state.colony.resources.story_points = 1
        assert can_spend(state, 1) is True


class TestSpendToPreventRoll:
    def test_prevent_enemy_activity(self):
        state = _make_state()
        state.colony.resources.story_points = 2
        events = spend_to_prevent_roll(state, "enemy_activity")
        assert state.colony.resources.story_points == 1
        assert "Enemy Activity" in events[0].description

    def test_prevent_morale_incident(self):
        state = _make_state()
        state.colony.resources.story_points = 1
        events = spend_to_prevent_roll(state, "morale_incident")
        assert state.colony.resources.story_points == 0
        assert "Morale Incident" in events[0].description

    def test_prevent_integrity_failure(self):
        state = _make_state()
        state.colony.resources.story_points = 1
        events = spend_to_prevent_roll(state, "integrity_failure")
        assert state.colony.resources.story_points == 0
        assert "Integrity Failure" in events[0].description

    def test_invalid_roll_type(self):
        state = _make_state()
        state.colony.resources.story_points = 5
        events = spend_to_prevent_roll(state, "invalid_type")
        assert state.colony.resources.story_points == 5  # not spent
        assert "Invalid" in events[0].description

    def test_insufficient_sp(self):
        state = _make_state()
        state.colony.resources.story_points = 0
        events = spend_to_prevent_roll(state, "enemy_activity")
        assert "Not enough" in events[0].description


class TestSpendForResources:
    @patch("planetfall.engine.campaign.story_points.roll_nd6")
    def test_gain_resources(self, mock_roll):
        from planetfall.engine.dice import RollResult
        mock_roll.return_value = RollResult(dice_type="2d6", values=[4, 5], total=9, label="")

        state = _make_state()
        state.colony.resources.story_points = 2
        old_bp = state.colony.resources.build_points
        old_rp = state.colony.resources.research_points

        events = spend_for_resources(state, bp=3, rp=2, rm=0)
        assert state.colony.resources.story_points == 1
        assert state.colony.resources.build_points == old_bp + 3
        assert state.colony.resources.research_points == old_rp + 2
        assert "+3 BP" in events[0].description

    @patch("planetfall.engine.campaign.story_points.roll_nd6")
    def test_capped_by_roll(self, mock_roll):
        from planetfall.engine.dice import RollResult
        # Highest die is 2, requesting 5 total
        mock_roll.return_value = RollResult(dice_type="2d6", values=[1, 2], total=3, label="")

        state = _make_state()
        state.colony.resources.story_points = 1
        old_bp = state.colony.resources.build_points

        events = spend_for_resources(state, bp=3, rp=2, rm=0)
        # Should cap: bp=2, rp=0, rm=0
        assert state.colony.resources.build_points == old_bp + 2

    def test_insufficient_sp(self):
        state = _make_state()
        state.colony.resources.story_points = 0
        events = spend_for_resources(state, bp=1)
        assert "Not enough" in events[0].description


class TestSpendToIgnoreInjury:
    def test_ignore_injury(self):
        state = _make_state()
        state.colony.resources.story_points = 1
        events = spend_to_ignore_injury(state, "Alice")
        assert state.colony.resources.story_points == 0
        assert "Alice" in events[0].description
        assert events[0].state_changes["story_point_spent"] == "ignore_injury"

    def test_insufficient_sp(self):
        state = _make_state()
        state.colony.resources.story_points = 0
        events = spend_to_ignore_injury(state, "Alice")
        assert "Not enough" in events[0].description


class TestSpendCrisisReroll:
    def test_crisis_reroll(self):
        state = _make_state()
        state.colony.resources.story_points = 1
        events = spend_crisis_reroll(state)
        assert state.colony.resources.story_points == 0
        assert state.flags.crisis_reroll_active is True
        assert "roll twice" in events[0].description

    def test_insufficient_sp(self):
        state = _make_state()
        state.colony.resources.story_points = 0
        events = spend_crisis_reroll(state)
        assert "Not enough" in events[0].description
        assert state.flags.crisis_reroll_active is False

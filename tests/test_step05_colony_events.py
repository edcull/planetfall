"""Tests for Step 5: Colony Events."""

from unittest.mock import patch

from planetfall.engine.campaign.setup import create_new_campaign
from planetfall.engine.dice import RollResult, TableEntry
from planetfall.engine.models import ColonizationAgenda
from planetfall.engine.steps.step05_colony_events import execute


def _make_state():
    return create_new_campaign("T", "C", agenda=ColonizationAgenda.UNITY)


class TestColonyEvents:
    @patch("planetfall.engine.steps.step05_colony_events.COLONY_EVENTS_TABLE")
    def test_research_points_effect(self, mock_table):
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[20], total=20, label=""),
            TableEntry(low=11, high=20, result_id="discovery",
                      description="A discovery!", effects={"research_points": 2}),
        )
        state = _make_state()
        old_rp = state.colony.resources.research_points
        events = execute(state)
        assert state.colony.resources.research_points == old_rp + 2
        assert len(events) == 1

    @patch("planetfall.engine.steps.step05_colony_events.COLONY_EVENTS_TABLE")
    def test_build_points_effect(self, mock_table):
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[40], total=40, label=""),
            TableEntry(low=31, high=40, result_id="windfall",
                      description="Resources found.", effects={"build_points": 3}),
        )
        state = _make_state()
        old_bp = state.colony.resources.build_points
        events = execute(state)
        assert state.colony.resources.build_points == old_bp + 3

    @patch("planetfall.engine.steps.step05_colony_events.COLONY_EVENTS_TABLE")
    def test_morale_effect(self, mock_table):
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[60], total=60, label=""),
            TableEntry(low=51, high=60, result_id="celebration",
                      description="Colony celebration!", effects={"morale": 2}),
        )
        state = _make_state()
        old_morale = state.colony.morale
        events = execute(state)
        assert state.colony.morale == old_morale + 2

    @patch("planetfall.engine.steps.step05_colony_events.COLONY_EVENTS_TABLE")
    def test_colony_damage_effect(self, mock_table):
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[80], total=80, label=""),
            TableEntry(low=71, high=80, result_id="disaster",
                      description="Natural disaster!", effects={"colony_damage": 2}),
        )
        state = _make_state()
        old_integrity = state.colony.integrity
        events = execute(state)
        assert state.colony.integrity == old_integrity - 2

    @patch("planetfall.engine.steps.step05_colony_events.COLONY_EVENTS_TABLE")
    def test_all_xp_effect(self, mock_table):
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[95], total=95, label=""),
            TableEntry(low=91, high=100, result_id="training",
                      description="Colony training!", effects={"all_xp": 1}),
        )
        state = _make_state()
        old_xps = [c.xp for c in state.characters]
        events = execute(state)
        for i, c in enumerate(state.characters):
            assert c.xp == old_xps[i] + 1

    @patch("planetfall.engine.steps.step05_colony_events.COLONY_EVENTS_TABLE")
    def test_no_effects(self, mock_table):
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[50], total=50, label=""),
            TableEntry(low=41, high=50, result_id="nothing",
                      description="Quiet day.", effects={}),
        )
        state = _make_state()
        events = execute(state)
        assert len(events) == 1
        assert "Colony Event" in events[0].description

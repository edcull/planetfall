"""Tests for Step 11: Colony Morale Adjustments."""

from unittest.mock import patch

from planetfall.engine.campaign.setup import create_new_campaign
from planetfall.engine.dice import RollResult, TableEntry
from planetfall.engine.models import ColonizationAgenda, MissionType
from planetfall.engine.steps.step11_morale import execute, resolve_colonist_demands


def _make_state():
    return create_new_campaign("T", "C", agenda=ColonizationAgenda.UNITY)


class TestBasicMorale:
    def test_automatic_minus_one(self):
        state = _make_state()
        old_morale = state.colony.morale
        events = execute(state)
        assert state.colony.morale == old_morale - 1

    def test_battle_casualties_reduce_morale(self):
        state = _make_state()
        old_morale = state.colony.morale
        events = execute(state, battle_casualties=3)
        assert state.colony.morale == old_morale - 1 - 3

    def test_rescue_mission_ignores_casualties(self):
        state = _make_state()
        old_morale = state.colony.morale
        events = execute(state, battle_casualties=3, mission_type=MissionType.RESCUE)
        assert state.colony.morale == old_morale - 1  # only automatic -1
        assert any("do not affect morale" in e.description for e in events)


class TestMoraleIncident:
    @patch("planetfall.engine.steps.step11_morale.CRISIS_OUTCOME_TABLE")
    @patch("planetfall.engine.steps.step11_morale.roll_nd6")
    @patch("planetfall.engine.steps.step11_morale.MORALE_INCIDENT_TABLE")
    def test_incident_triggers_at_minus_10(self, mock_incident, mock_nd6, mock_crisis):
        mock_incident.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[30], total=30, label=""),
            TableEntry(low=21, high=40, result_id="work_stoppage",
                      description="Workers stop.", effects={}),
        )
        # Crisis check roll > upheaval → no crisis
        mock_nd6.return_value = RollResult(dice_type="2d6", values=[6, 6], total=12, label="")
        state = _make_state()
        state.colony.morale = -9  # will become -10 after automatic -1
        events = execute(state)
        assert state.colony.morale == 0  # reset after incident
        assert any("MORALE INCIDENT" in e.description for e in events)

    def test_spend_sp_prevents_incident(self):
        state = _make_state()
        state.colony.morale = -9
        state.colony.resources.story_points = 2
        events = execute(state, spend_sp_prevent_incident=True)
        assert state.colony.morale == 0
        assert state.colony.resources.story_points == 1
        assert any("Story Point spent" in e.description for e in events)


class TestCrisisResolution:
    @patch("planetfall.engine.steps.step11_morale.CRISIS_OUTCOME_TABLE")
    def test_crisis_ends(self, mock_table):
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="2d6", values=[6, 6], total=12, label=""),
            TableEntry(low=12, high=12, result_id="crisis_resolved",
                      description="Crisis resolved!", effects={"crisis_ends": True}),
        )
        state = _make_state()
        state.flags.crisis_active = True
        state.flags.political_upheaval = 3
        events = execute(state)
        assert state.flags.crisis_active is False
        assert state.flags.political_upheaval == 0

    @patch("planetfall.engine.steps.step11_morale.CRISIS_OUTCOME_TABLE")
    def test_crisis_upheaval_reduction(self, mock_table):
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="2d6", values=[5, 5], total=10, label=""),
            TableEntry(low=10, high=11, result_id="cooling_off",
                      description="Tensions ease.", effects={"upheaval_reduction": -1}),
        )
        state = _make_state()
        state.flags.crisis_active = True
        state.flags.political_upheaval = 2
        events = execute(state)
        assert state.flags.political_upheaval == 1
        assert state.flags.crisis_active is True  # still active (upheaval > 0)


class TestColonistDemands:
    @patch("planetfall.engine.steps.step11_morale.roll_d6")
    def test_demands_satisfied(self, mock_d6):
        mock_d6.return_value = RollResult(dice_type="d6", values=[4], total=4, label="")
        state = _make_state()
        state.flags.colonist_demands_active = True
        char = state.characters[0]
        char.savvy = 1  # 4 + 1 = 5, satisfied
        events = resolve_colonist_demands(state, [char.name])
        assert state.flags.colonist_demands_active is False

    @patch("planetfall.engine.steps.step11_morale.roll_d6")
    def test_demands_not_satisfied(self, mock_d6):
        mock_d6.return_value = RollResult(dice_type="d6", values=[1], total=1, label="")
        state = _make_state()
        state.flags.colonist_demands_active = True
        char = state.characters[0]
        char.savvy = 1  # 1 + 1 = 2, not satisfied
        events = resolve_colonist_demands(state, [char.name])
        assert state.flags.colonist_demands_active is True

    def test_no_demands_active(self):
        state = _make_state()
        state.flags.colonist_demands_active = False
        events = resolve_colonist_demands(state, [state.characters[0].name])
        assert len(events) == 0

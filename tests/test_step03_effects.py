"""Tests for Step 3 scout discovery effect handling."""

from unittest.mock import patch

import pytest

from planetfall.engine.campaign.setup import create_new_campaign
from planetfall.engine.models import (
    ColonizationAgenda, GameState, SectorStatus, TacticalEnemy,
)
from planetfall.engine.steps import step03_scout_reports


def _make_state() -> GameState:
    return create_new_campaign("T", "C", agenda=ColonizationAgenda.UNITY)


class TestScoutExplore:
    def test_explore_sets_status(self):
        state = _make_state()
        sector = state.campaign_map.sectors[1]
        assert sector.status == SectorStatus.UNKNOWN
        events = step03_scout_reports.execute_scout_explore(state, sector.sector_id)
        assert sector.status == SectorStatus.INVESTIGATED
        assert sector.resource_level > 0 or sector.hazard_level > 0
        assert len(events) == 1
        assert "surveyed" in events[0].description

    def test_explore_invalid_sector(self):
        state = _make_state()
        events = step03_scout_reports.execute_scout_explore(state, 999)
        assert "Invalid" in events[0].description


class TestGoodPractice:
    @patch("planetfall.engine.steps.step03_scout_reports.SCOUT_DISCOVERY_TABLE")
    def test_awards_xp_to_scout(self, mock_table):
        from planetfall.engine.dice import RollResult, TableEntry
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[15], total=15, label=""),
            TableEntry(low=11, high=20, result_id="good_practice",
                       description="Good practice.", effects={"scout_xp": 2}),
        )
        state = _make_state()
        scout = state.characters[0]
        scout.name = "TestScout"
        old_xp = scout.xp
        events = step03_scout_reports.execute_scout_discovery(state, "TestScout")
        assert scout.xp == old_xp + 2
        assert "TestScout gains +2 XP" in events[0].description


class TestExplorationReport:
    @patch("planetfall.engine.steps.step03_scout_reports.SCOUT_DISCOVERY_TABLE")
    def test_explores_unknown_sector(self, mock_table):
        from planetfall.engine.dice import RollResult, TableEntry
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[45], total=45, label=""),
            TableEntry(low=31, high=60, result_id="exploration_report",
                       description="Explore.", effects={"explore_sector": True}),
        )
        state = _make_state()
        # Ensure at least one unknown sector exists
        unknown_before = [
            s for s in state.campaign_map.sectors
            if s.status == SectorStatus.UNKNOWN
            and s.sector_id != state.campaign_map.colony_sector_id
        ]
        assert len(unknown_before) > 0

        events = step03_scout_reports.execute_scout_discovery(state)
        # Exploration report now defers to player choice
        ctx = events[0].state_changes.get("narrative_context", {})
        assert ctx.get("pending_choice") == "exploration_report"


class TestRevisedSurvey:
    @patch("planetfall.engine.steps.step03_scout_reports.SCOUT_DISCOVERY_TABLE")
    @patch("planetfall.engine.steps.step03_scout_reports.random")
    def test_revised_survey_unknown(self, mock_random, mock_table):
        from planetfall.engine.dice import RollResult, TableEntry
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[90], total=90, label=""),
            TableEntry(low=81, high=100, result_id="revised_survey",
                       description="Revised.", effects={"revised_survey": True}),
        )
        state = _make_state()
        # Pick a specific unknown sector
        target = state.campaign_map.sectors[2]
        target.status = SectorStatus.UNKNOWN
        mock_random.choice.return_value = target

        events = step03_scout_reports.execute_scout_discovery(state)
        assert target.status == SectorStatus.INVESTIGATED
        assert target.resource_level > 0 or target.hazard_level > 0

    @patch("planetfall.engine.steps.step03_scout_reports.SCOUT_DISCOVERY_TABLE")
    @patch("planetfall.engine.steps.step03_scout_reports.random")
    def test_revised_survey_explored_adds_resource(self, mock_random, mock_table):
        from planetfall.engine.dice import RollResult, TableEntry
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[90], total=90, label=""),
            TableEntry(low=81, high=100, result_id="revised_survey",
                       description="Revised.", effects={"revised_survey": True}),
        )
        state = _make_state()
        target = state.campaign_map.sectors[3]
        target.status = SectorStatus.EXPLORED
        target.resource_level = 3
        mock_random.choice.return_value = target

        events = step03_scout_reports.execute_scout_discovery(state)
        assert target.resource_level == 4
        assert "increased" in events[0].description.lower()

    @patch("planetfall.engine.steps.step03_scout_reports.SCOUT_DISCOVERY_TABLE")
    @patch("planetfall.engine.steps.step03_scout_reports.random")
    def test_revised_survey_exploited_regenerates(self, mock_random, mock_table):
        from planetfall.engine.dice import RollResult, TableEntry
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[90], total=90, label=""),
            TableEntry(low=81, high=100, result_id="revised_survey",
                       description="Revised.", effects={"revised_survey": True}),
        )
        state = _make_state()
        target = state.campaign_map.sectors[4]
        target.status = SectorStatus.EXPLOITED
        target.resource_level = 2
        target.hazard_level = 2
        mock_random.choice.return_value = target

        events = step03_scout_reports.execute_scout_discovery(state)
        assert target.status == SectorStatus.EXPLORED  # Can be exploited again
        assert "exploited" in events[0].description.lower()


class TestAncientSign:
    @patch("planetfall.engine.steps.step03_scout_reports.SCOUT_DISCOVERY_TABLE")
    def test_marks_sector(self, mock_table):
        from planetfall.engine.dice import RollResult, TableEntry
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[75], total=75, label=""),
            TableEntry(low=71, high=80, result_id="ancient_sign",
                       description="Ancient sign.", effects={"ancient_sign": True}),
        )
        state = _make_state()
        events = step03_scout_reports.execute_scout_discovery(state)
        signed = [s for s in state.campaign_map.sectors if s.has_ancient_sign]
        assert len(signed) >= 1
        assert "Ancient Sign" in events[0].description


class TestReconPatrol:
    @patch("planetfall.engine.steps.step03_scout_reports.SCOUT_DISCOVERY_TABLE")
    def test_adds_enemy_info(self, mock_table):
        from planetfall.engine.dice import RollResult, TableEntry
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[65], total=65, label=""),
            TableEntry(low=61, high=70, result_id="recon_patrol",
                       description="Recon.", effects={"enemy_info": 1}),
        )
        state = _make_state()
        enemy = TacticalEnemy(name="Raiders", enemy_type="outlaws", enemy_info_count=1)
        state.enemies.tactical_enemies.append(enemy)

        events = step03_scout_reports.execute_scout_discovery(state)
        assert enemy.enemy_info_count == 2
        assert "Raiders" in events[0].description

    @patch("planetfall.engine.steps.step03_scout_reports.SCOUT_DISCOVERY_TABLE")
    def test_no_enemies_no_effect(self, mock_table):
        from planetfall.engine.dice import RollResult, TableEntry
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[65], total=65, label=""),
            TableEntry(low=61, high=70, result_id="recon_patrol",
                       description="Recon.", effects={"enemy_info": 1}),
        )
        state = _make_state()
        events = step03_scout_reports.execute_scout_discovery(state)
        assert "No tactical enemies" in events[0].description


class TestSosSignal:
    @patch("planetfall.engine.steps.step03_scout_reports.SCOUT_DISCOVERY_TABLE")
    def test_stores_pending_choice(self, mock_table):
        from planetfall.engine.dice import RollResult, TableEntry
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[22], total=22, label=""),
            TableEntry(low=21, high=25, result_id="sos_signal",
                       description="Distress signal.",
                       effects={"mission_option": "rescue", "decline_morale": -3}),
        )
        state = _make_state()
        events = step03_scout_reports.execute_scout_discovery(state)
        ctx = events[0].state_changes["narrative_context"]
        assert ctx["pending_choice"] == "rescue_or_morale"
        assert ctx["decline_morale_penalty"] == -3


class TestNarrativeContext:
    @patch("planetfall.engine.steps.step03_scout_reports.SCOUT_DISCOVERY_TABLE")
    def test_includes_scout_info(self, mock_table):
        from planetfall.engine.dice import RollResult, TableEntry
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[5], total=5, label=""),
            TableEntry(low=1, high=10, result_id="routine_trip",
                       description="Nothing."),
        )
        state = _make_state()
        events = step03_scout_reports.execute_scout_discovery(state, "Alice")
        ctx = events[0].state_changes["narrative_context"]
        assert ctx["assigned_scout"] == "Alice"
        assert ctx["discovery_type"] == "routine_trip"

"""Tests for Step 9: Injuries — character and grunt injury resolution."""

from unittest.mock import patch

import pytest

from planetfall.engine.campaign.setup import create_new_campaign
from planetfall.engine.dice import RollResult
from planetfall.engine.models import ColonizationAgenda, GameState
from planetfall.engine.steps.step09_injuries import execute


def _make_state() -> GameState:
    return create_new_campaign("T", "C", agenda=ColonizationAgenda.UNITY)


class TestNoInjuries:
    def test_no_casualties(self):
        state = _make_state()
        events = execute(state, [], 0)
        assert len(events) == 1
        assert "No casualties" in events[0].description


class TestCharacterInjuries:
    @patch("planetfall.engine.steps.step09_injuries.CHARACTER_INJURY_TABLE")
    def test_character_death(self, mock_table):
        from planetfall.engine.dice import TableEntry
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[5], total=5, label=""),
            TableEntry(low=1, high=10, result_id="dead", description="Dead",
                      effects={"dead": True}),
        )
        state = _make_state()
        char_name = state.characters[0].name
        old_sp = state.colony.resources.story_points
        old_count = len(state.characters)

        events = execute(state, [char_name], 0)
        assert len(state.characters) == old_count - 1
        assert state.colony.resources.story_points == old_sp + 1
        assert any("DEAD" in e.description for e in events)

    @patch("planetfall.engine.steps.step09_injuries.CHARACTER_INJURY_TABLE")
    def test_character_sick_bay(self, mock_table):
        from planetfall.engine.dice import TableEntry
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[50], total=50, label=""),
            TableEntry(low=41, high=60, result_id="serious_wound",
                      description="Serious wound", effects={"sick_bay_turns": 3}),
        )
        state = _make_state()
        char_name = state.characters[0].name
        events = execute(state, [char_name], 0)
        char = next(c for c in state.characters if c.name == char_name)
        assert char.sick_bay_turns == 3
        assert any("Sick Bay" in e.description for e in events)

    @patch("planetfall.engine.steps.step09_injuries.CHARACTER_INJURY_TABLE")
    def test_character_okay_with_xp(self, mock_table):
        from planetfall.engine.dice import TableEntry
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[90], total=90, label=""),
            TableEntry(low=81, high=100, result_id="school_hard_knocks",
                      description="Okay", effects={"xp": 1}),
        )
        state = _make_state()
        char_name = state.characters[0].name
        old_xp = state.characters[0].xp
        events = execute(state, [char_name], 0)
        char = next(c for c in state.characters if c.name == char_name)
        assert char.xp == old_xp + 1
        assert any("Hard Knocks" in e.description for e in events)

    @patch("planetfall.engine.steps.step09_injuries.CHARACTER_INJURY_TABLE")
    def test_character_okay_no_effects(self, mock_table):
        from planetfall.engine.dice import TableEntry
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[75], total=75, label=""),
            TableEntry(low=71, high=80, result_id="okay",
                      description="Okay", effects={}),
        )
        state = _make_state()
        char_name = state.characters[0].name
        events = execute(state, [char_name], 0)
        assert any("Okay" in e.description for e in events)

    @patch("planetfall.engine.steps.step09_injuries.CHARACTER_INJURY_TABLE")
    def test_missing_character_skipped(self, mock_table):
        state = _make_state()
        events = execute(state, ["NonExistentChar"], 0)
        mock_table.roll_on_table.assert_not_called()
        assert any("No casualties" in e.description for e in events)

    @patch("planetfall.engine.steps.step09_injuries.CHARACTER_INJURY_TABLE")
    def test_boosted_recovery_reduces_sick_bay(self, mock_table):
        from planetfall.engine.dice import TableEntry
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[50], total=50, label=""),
            TableEntry(low=41, high=60, result_id="serious_wound",
                      description="Serious wound", effects={"sick_bay_turns": 3}),
        )
        state = _make_state()
        # Add boosted_recovery augmentation via colony flags
        state.flags.colony_augmentations = ["boosted_recovery"]
        char_name = state.characters[0].name
        events = execute(state, [char_name], 0)
        char = next(c for c in state.characters if c.name == char_name)
        assert char.sick_bay_turns == 2  # 3 - 1


class TestGruntInjuries:
    @patch("planetfall.engine.steps.step09_injuries.GRUNT_INJURY_TABLE")
    def test_grunt_casualties(self, mock_table):
        from planetfall.engine.dice import TableEntry
        # Alternate: first grunt dies, second survives
        mock_table.roll_on_table.side_effect = [
            (
                RollResult(dice_type="d6", values=[1], total=1, label=""),
                TableEntry(low=1, high=2, result_id="dead", description="Dead",
                          effects={"dead": True}),
            ),
            (
                RollResult(dice_type="d6", values=[5], total=5, label=""),
                TableEntry(low=4, high=6, result_id="okay", description="Okay",
                          effects={}),
            ),
        ]
        state = _make_state()
        old_grunts = state.grunts.count
        events = execute(state, [], 2)
        assert state.grunts.count == old_grunts - 1
        assert any("Lost: 1" in e.description for e in events)
        assert any("Recovered: 1" in e.description for e in events)

    @patch("planetfall.engine.steps.step09_injuries.GRUNT_INJURY_TABLE")
    def test_all_grunts_survive(self, mock_table):
        from planetfall.engine.dice import TableEntry
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d6", values=[5], total=5, label=""),
            TableEntry(low=4, high=6, result_id="okay", description="Okay",
                      effects={}),
        )
        state = _make_state()
        old_grunts = state.grunts.count
        events = execute(state, [], 3)
        assert state.grunts.count == old_grunts  # no permanent losses
        assert any("Lost: 0" in e.description for e in events)


class TestMedEvac:
    @patch("planetfall.engine.steps.step09_injuries.CHARACTER_INJURY_TABLE")
    def test_medevac_picks_better_roll(self, mock_table):
        from planetfall.engine.dice import TableEntry
        from planetfall.engine.models import Building
        # First roll = 10 (bad), second roll = 90 (good)
        mock_table.roll_on_table.side_effect = [
            (
                RollResult(dice_type="d100", values=[10], total=10, label="roll 1"),
                TableEntry(low=1, high=15, result_id="dead", description="Dead",
                          effects={"dead": True}),
            ),
            (
                RollResult(dice_type="d100", values=[90], total=90, label="roll 2"),
                TableEntry(low=81, high=100, result_id="okay", description="Okay",
                          effects={}),
            ),
        ]
        state = _make_state()
        state.colony.buildings.append(
            Building(name="Med-Evac Shuttle Facility", build_progress=0, completed=True)
        )
        char_name = state.characters[0].name
        old_count = len(state.characters)

        events = execute(state, [char_name], 0)
        # Should keep the better roll (90 = okay), character survives
        assert len(state.characters) == old_count
        assert any("Med-Evac" in e.description for e in events)

"""Tests for Step 17 character event effect handling (mechanical events)."""

from unittest.mock import patch

import pytest

from planetfall.engine.models import Loyalty
from planetfall.engine.steps import step17_character_event


class TestCharacterEventBasic:
    def test_produces_event(self, game_state):
        state = game_state
        events = step17_character_event.execute(state)
        assert len(events) == 1
        assert events[0].event_type.value == "character_event"
        assert events[0].state_changes.get("narrative_context")

    def test_no_characters(self, game_state):
        state = game_state
        state.characters.clear()
        events = step17_character_event.execute(state)
        assert "No characters" in events[0].description


class TestMechanicalEffects:
    @patch("planetfall.engine.steps.step17_character_event.CHARACTER_EVENT_TABLE")
    @patch("planetfall.engine.steps.step17_character_event.random")
    def test_personal_training_xp(self, mock_random, mock_table, game_state):
        from planetfall.engine.dice import RollResult, TableEntry
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[3], total=3, label=""),
            TableEntry(low=1, high=5, result_id="personal_training",
                       description="Training.", effects={"xp": 2}),
        )
        state = game_state
        char = state.characters[0]
        old_xp = char.xp
        mock_random.choice.return_value = char
        events = step17_character_event.execute(state)
        assert char.xp == old_xp + 2
        assert "+2 XP" in events[0].description

    @patch("planetfall.engine.steps.step17_character_event.CHARACTER_EVENT_TABLE")
    @patch("planetfall.engine.steps.step17_character_event.random")
    def test_minor_promotion_loyalty(self, mock_random, mock_table, game_state):
        from planetfall.engine.dice import RollResult, TableEntry
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[8], total=8, label=""),
            TableEntry(low=6, high=10, result_id="minor_promotion",
                       description="Promotion.",
                       effects={"loyalty_up": 1, "xp": 1, "loyal_bonus_xp": 2}),
        )
        state = game_state
        char = state.characters[0]
        char.loyalty = Loyalty.COMMITTED
        mock_random.choice.return_value = char
        events = step17_character_event.execute(state)
        assert char.loyalty == Loyalty.LOYAL

    @patch("planetfall.engine.steps.step17_character_event.CHARACTER_EVENT_TABLE")
    @patch("planetfall.engine.steps.step17_character_event.random")
    def test_sickness_sick_bay(self, mock_random, mock_table, game_state):
        from planetfall.engine.dice import RollResult, TableEntry
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[60], total=60, label=""),
            TableEntry(low=56, high=60, result_id="sickness",
                       description="Sick.", effects={"sick_bay": 2}),
        )
        state = game_state
        char = state.characters[0]
        mock_random.choice.return_value = char
        events = step17_character_event.execute(state)
        assert char.sick_bay_turns >= 2

    @patch("planetfall.engine.steps.step17_character_event.CHARACTER_EVENT_TABLE")
    @patch("planetfall.engine.steps.step17_character_event.random")
    def test_disputes_loyalty_down(self, mock_random, mock_table, game_state):
        from planetfall.engine.dice import RollResult, TableEntry
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[38], total=38, label=""),
            TableEntry(low=36, high=40, result_id="disputes_with_leadership",
                       description="Disputes.", effects={"loyalty_down": 1}),
        )
        state = game_state
        char = state.characters[0]
        char.loyalty = Loyalty.COMMITTED
        mock_random.choice.return_value = char
        events = step17_character_event.execute(state)
        assert char.loyalty == Loyalty.DISLOYAL


class TestLoyaltyHelpers:
    def test_increase_loyalty(self, game_state):
        state = game_state
        char = state.characters[0]
        char.loyalty = Loyalty.DISLOYAL
        result = step17_character_event._increase_loyalty(char)
        assert char.loyalty == Loyalty.COMMITTED
        assert result  # non-empty string

    def test_increase_loyalty_already_loyal(self, game_state):
        state = game_state
        char = state.characters[0]
        char.loyalty = Loyalty.LOYAL
        result = step17_character_event._increase_loyalty(char)
        assert char.loyalty == Loyalty.LOYAL
        assert result == ""

    def test_decrease_loyalty(self, game_state):
        state = game_state
        char = state.characters[0]
        char.loyalty = Loyalty.COMMITTED
        result = step17_character_event._decrease_loyalty(char)
        assert char.loyalty == Loyalty.DISLOYAL
        assert result

    def test_decrease_loyalty_already_disloyal(self, game_state):
        state = game_state
        char = state.characters[0]
        char.loyalty = Loyalty.DISLOYAL
        result = step17_character_event._decrease_loyalty(char)
        assert char.loyalty == Loyalty.DISLOYAL
        assert result == ""


class TestNarrativeContext:
    @patch("planetfall.engine.steps.step17_character_event.CHARACTER_EVENT_TABLE")
    @patch("planetfall.engine.steps.step17_character_event.random")
    def test_includes_character_info(self, mock_random, mock_table, game_state):
        from planetfall.engine.dice import RollResult, TableEntry
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[3], total=3, label=""),
            TableEntry(low=1, high=5, result_id="personal_training",
                       description="Training.", effects={"xp": 2}),
        )
        state = game_state
        char = state.characters[0]
        char.background_motivation = "Seeking redemption"
        mock_random.choice.return_value = char

        events = step17_character_event.execute(state)
        ctx = events[0].state_changes["narrative_context"]
        assert ctx["motivation"] == "Seeking redemption"
        assert ctx["character"] == char.name
        assert ctx["character_class"] == char.char_class.value

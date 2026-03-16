"""Tests for Step 1: Recovery — Characters in Sick Bay heal."""

from planetfall.engine.steps.step01_recovery import execute


class TestRecoveryNoSickBay:
    def test_no_one_in_sick_bay(self, game_state):
        state = game_state
        events = execute(state)
        assert len(events) == 1
        assert "No characters in Sick Bay" in events[0].description

    def test_clears_per_turn_flags(self, game_state):
        state = game_state
        state.flags.augmentation_bought_this_turn = True
        state.flags.benched_trooper = "Alice"
        execute(state)
        assert state.flags.augmentation_bought_this_turn is False
        assert state.flags.benched_trooper == ""


class TestRecoverySickBay:
    def test_character_recovers_one_turn(self, game_state):
        state = game_state
        char = state.characters[0]
        char.sick_bay_turns = 1
        events = execute(state)
        assert char.sick_bay_turns == 0
        assert any("fully recovered" in e.description for e in events)

    def test_character_still_recovering(self, game_state):
        state = game_state
        char = state.characters[0]
        char.sick_bay_turns = 3
        events = execute(state)
        assert char.sick_bay_turns == 2
        assert any("2 turn(s) remaining" in e.description for e in events)

    def test_multiple_characters_in_sick_bay(self, game_state):
        state = game_state
        state.characters[0].sick_bay_turns = 1
        state.characters[1].sick_bay_turns = 2
        events = execute(state)
        assert state.characters[0].sick_bay_turns == 0
        assert state.characters[1].sick_bay_turns == 1
        assert len(events) == 2


class TestExcellentHealthBonus:
    def test_excellent_health_reduces_by_2(self, game_state):
        state = game_state
        char = state.characters[0]
        char.sick_bay_turns = 3
        char.notes = "[EXCELLENT_HEALTH: saved]"
        events = execute(state)
        # 3 - 2 (bonus) = 1, then -1 (normal) = 0
        assert char.sick_bay_turns == 0
        assert "[EXCELLENT_HEALTH: saved]" not in (char.notes or "")

    def test_excellent_health_fully_recovers(self, game_state):
        state = game_state
        char = state.characters[0]
        char.sick_bay_turns = 2
        char.notes = "[EXCELLENT_HEALTH: saved]"
        events = execute(state)
        # 2 - 2 = 0, fully recovered via bonus
        assert char.sick_bay_turns == 0
        assert any("Excellent Health" in e.description for e in events)

"""Tests for Step 7: Lock and Load — deployment validation and fireteams."""

import pytest

from planetfall.engine.steps.step07_lock_and_load import (
    get_available_characters, get_deployment_slots, validate_deployment,
    organize_fireteams, execute, MISSION_SLOTS,
)


class TestGetAvailableCharacters:
    def test_all_available(self, game_state):
        state = game_state
        available = get_available_characters(state)
        assert len(available) == len(state.characters)

    def test_sick_bay_excluded(self, game_state):
        state = game_state
        state.characters[0].sick_bay_turns = 3
        available = get_available_characters(state)
        assert state.characters[0].name not in [c.name for c in available]
        assert len(available) == len(state.characters) - 1


class TestGetDeploymentSlots:
    def test_known_missions(self):
        assert get_deployment_slots("investigation") == 4
        assert get_deployment_slots("pitched_battle") == 8
        assert get_deployment_slots("patrol") == 2
        assert get_deployment_slots("skirmish") == 6

    def test_unknown_mission_defaults(self):
        assert get_deployment_slots("unknown_mission") == 5


class TestValidateDeployment:
    def test_valid_deployment(self, game_state):
        state = game_state
        names = [c.name for c in state.characters[:2]]  # patrol = 2 chars
        valid, msg = validate_deployment(state, names, "patrol")
        assert valid is True
        assert "valid" in msg.lower()

    def test_too_many_characters(self, game_state):
        state = game_state
        names = [c.name for c in state.characters]  # 8 chars
        valid, msg = validate_deployment(state, names, "investigation")  # max 4
        assert valid is False
        assert "Too many" in msg

    def test_unavailable_character(self, game_state):
        state = game_state
        state.characters[0].sick_bay_turns = 2
        names = [state.characters[0].name]
        valid, msg = validate_deployment(state, names, "patrol")
        assert valid is False
        assert "not available" in msg


class TestOrganizeFireteams:
    def test_no_grunts(self, game_state):
        state = game_state
        teams = organize_fireteams(state, 0)
        assert teams == []

    def test_small_group(self, game_state):
        state = game_state
        teams = organize_fireteams(state, 3)
        assert len(teams) == 1
        assert teams[0].size == 3
        assert teams[0].name == "Fireteam Alpha"

    def test_max_single_team(self, game_state):
        state = game_state
        teams = organize_fireteams(state, 4)
        assert len(teams) == 1
        assert teams[0].size == 4

    def test_split_into_two(self, game_state):
        state = game_state
        teams = organize_fireteams(state, 6)
        assert len(teams) == 2
        assert teams[0].size + teams[1].size == 6
        assert teams[0].name == "Fireteam Alpha"
        assert teams[1].name == "Fireteam Bravo"

    def test_odd_split(self, game_state):
        state = game_state
        teams = organize_fireteams(state, 7)
        assert len(teams) == 2
        assert teams[0].size == 3
        assert teams[1].size == 4


class TestExecute:
    def test_basic_deployment(self, game_state):
        state = game_state
        names = [c.name for c in state.characters[:2]]
        events = execute(state, names, deployed_grunts=0, mission_type="patrol")
        assert len(events) == 1
        assert "Patrol" in events[0].description
        for name in names:
            assert name in events[0].description

    def test_deployment_with_grunts(self, game_state):
        state = game_state
        names = [state.characters[0].name]
        events = execute(state, names, deployed_grunts=6, mission_type="skirmish")
        assert "Grunts: 6" in events[0].description
        assert "Fireteam Alpha" in events[0].description
        assert "Fireteam Bravo" in events[0].description
        assert len(state.grunts.fireteams) == 2

"""Tests for endgame, victory/loss, calibration, excellent health, forfeit/double XP."""

from unittest.mock import patch

import pytest


# --- Endgame / Summit ---


class TestSummitVotes:
    @patch("planetfall.engine.campaign.milestones.roll_d6")
    def test_run_summit_votes(self, mock_roll, game_state):
        from planetfall.engine.dice import RollResult
        from planetfall.engine.campaign.milestones import run_summit_votes

        # All rolls return 1 -> "Independence"
        mock_roll.return_value = RollResult(dice_type="d6", values=[1], total=1, label="")
        state = game_state
        votes = run_summit_votes(state)
        assert len(votes["Independence"]) == len(state.characters) + 1  # chars + population

    def test_get_viable_paths(self):
        from planetfall.engine.campaign.milestones import get_viable_paths

        votes = {
            "Independence": ["Alice", "Population"],
            "Ascension": [],
            "Loyalty": ["Bob"],
            "Isolation": [],
            "No opinion": ["Carol"],
        }
        viable = get_viable_paths(votes)
        assert "Independence" in viable
        assert "Loyalty" in viable
        assert "Ascension" not in viable
        assert "Isolation" not in viable

    def test_get_viable_paths_empty(self):
        from planetfall.engine.campaign.milestones import get_viable_paths

        votes = {"Independence": [], "Ascension": [], "Loyalty": [], "Isolation": [], "No opinion": []}
        assert get_viable_paths(votes) == []


class TestExecuteSummit:
    def test_summit_success(self, game_state):
        from planetfall.engine.campaign.milestones import execute_summit
        from planetfall.engine.models import TacticalEnemy

        state = game_state
        state.colony.resources.build_points = 20
        state.colony.resources.research_points = 10
        # Must have at least 1 defeated enemy for colony security
        state.enemies.tactical_enemies.append(
            TacticalEnemy(name="Test Enemy", defeated=True)
        )
        events = execute_summit(state, "Independence")
        assert any("Independence" in e.description for e in events)
        assert state.flags.campaign_complete is True
        assert state.colony.resources.build_points == 5  # 20 - 15
        assert state.colony.resources.research_points == 5  # 10 - 5

    def test_summit_cannot_afford(self, game_state):
        from planetfall.engine.campaign.milestones import execute_summit
        from planetfall.engine.models import TacticalEnemy

        state = game_state
        state.colony.resources.build_points = 0
        state.colony.resources.research_points = 0
        # Must pass security check first to reach the cost check
        state.enemies.tactical_enemies.append(
            TacticalEnemy(name="Test Enemy", defeated=True)
        )
        events = execute_summit(state, "Independence")
        assert any("Cannot afford" in e.description for e in events)
        assert state.flags.campaign_complete is False

    def test_summit_invalid_path(self, game_state):
        from planetfall.engine.campaign.milestones import execute_summit

        state = game_state
        events = execute_summit(state, "InvalidPath")
        assert any("Invalid" in e.description for e in events)


class TestCampaignScore:
    def test_basic_scoring(self, game_state):
        from planetfall.engine.campaign.milestones import calculate_campaign_score

        state = game_state
        state.campaign.milestones_completed = 3
        state.colony.morale = 25
        state.colony.integrity = 5
        state.flags.campaign_complete = True
        score_data = calculate_campaign_score(state)
        assert score_data["score"] > 0
        assert score_data["rating"] in (
            "Legendary", "Outstanding", "Commendable",
            "Adequate", "Struggling", "Catastrophic",
        )
        assert "Milestones" in score_data["breakdown"][0]

    def test_defeat_scoring(self, game_state):
        from planetfall.engine.campaign.milestones import calculate_campaign_score

        state = game_state
        state.campaign.milestones_completed = 0
        state.colony.morale = 0
        state.colony.integrity = -5
        state.characters.clear()
        state.flags.total_character_deaths = 4
        score_data = calculate_campaign_score(state)
        # Should be low / negative
        assert score_data["rating"] in ("Catastrophic", "Struggling")


# --- Forfeit XP / Double XP ---


class TestXPFlags:
    def test_double_xp(self, game_state):
        from planetfall.engine.steps.step10_experience import award_mission_xp

        state = game_state
        char = state.characters[0]
        char.notes = "[DOUBLE_XP: next mission]"
        old_xp = char.xp
        events = award_mission_xp(state, [char.name], [])
        # participation (1) + survived (1) = 2, doubled = 4
        assert char.xp == old_xp + 4
        assert "DOUBLE XP" in events[0].description
        assert "[DOUBLE_XP" not in (char.notes or "")

    def test_forfeit_xp(self, game_state):
        from planetfall.engine.steps.step10_experience import award_mission_xp

        state = game_state
        char = state.characters[0]
        char.notes = "[FORFEIT_XP: next turn]"
        old_xp = char.xp
        events = award_mission_xp(state, [char.name], [])
        assert char.xp == old_xp  # No XP gained
        assert "FORFEITED" in events[0].description
        assert "[FORFEIT_XP" not in (char.notes or "")

    def test_no_flag_normal_xp(self, game_state):
        from planetfall.engine.steps.step10_experience import award_mission_xp

        state = game_state
        char = state.characters[0]
        char.notes = ""
        old_xp = char.xp
        events = award_mission_xp(state, [char.name], [])
        # participation (1) + survived (1) = 2
        assert char.xp == old_xp + 2


# --- Calibration Hit Bonus ---


class TestCalibrationBonus:
    def test_calibration_sets_hit_bonus(self, game_state):
        from planetfall.engine.combat.missions import _deploy_player_figures

        state = game_state
        char = state.characters[0]
        char.notes = "[CALIBRATION: +1 hit bonus next mission]"
        figures = _deploy_player_figures(state, [char.name])
        fig = next(f for f in figures if f.name == char.name)
        assert fig.hit_bonus == 1
        # Note should be consumed
        assert "[CALIBRATION" not in (char.notes or "")

    def test_no_calibration_no_bonus(self, game_state):
        from planetfall.engine.combat.missions import _deploy_player_figures

        state = game_state
        char = state.characters[0]
        char.notes = ""
        figures = _deploy_player_figures(state, [char.name])
        fig = next(f for f in figures if f.name == char.name)
        assert fig.hit_bonus == 0

    def test_hit_bonus_applied_in_shooting(self):
        from planetfall.engine.combat.battlefield import Battlefield, Figure, FigureSide
        from planetfall.engine.combat.shooting import resolve_shot

        bf = Battlefield()
        shooter = Figure(
            name="Cal", side=FigureSide.PLAYER, zone=(2, 1),
            combat_skill=0, weapon_range=24, weapon_shots=1,
            hit_bonus=1,
        )
        target = Figure(
            name="Enemy", side=FigureSide.ENEMY, zone=(0, 1),
            toughness=5,
        )
        bf.figures = [shooter, target]
        # Run multiple shots to verify bonus is applied
        result = resolve_shot(bf, shooter, target)
        # The hit_bonus should appear in the log
        assert any("Calibration" in line for line in result.log)


# --- Excellent Health Saved ---


class TestExcellentHealth:
    def test_excellent_health_reduces_sick_bay(self, game_state):
        from planetfall.engine.steps.step01_recovery import execute

        state = game_state
        char = state.characters[0]
        char.sick_bay_turns = 4
        char.notes = "[EXCELLENT_HEALTH: saved]"
        events = execute(state)
        # Should reduce by 2 (bonus) then by 1 (normal recovery)
        # 4 - 2 = 2, then 2 - 1 = 1
        assert char.sick_bay_turns == 1
        assert "[EXCELLENT_HEALTH" not in (char.notes or "")
        assert any("Excellent Health" in e.description for e in events)

    def test_excellent_health_instant_recovery(self, game_state):
        from planetfall.engine.steps.step01_recovery import execute

        state = game_state
        char = state.characters[0]
        char.sick_bay_turns = 2
        char.notes = "[EXCELLENT_HEALTH: saved]"
        events = execute(state)
        # 2 - 2 = 0, fully recovered via bonus
        assert char.sick_bay_turns == 0
        assert any("Excellent Health" in e.description for e in events)

    def test_no_excellent_health_normal_recovery(self, game_state):
        from planetfall.engine.steps.step01_recovery import execute

        state = game_state
        char = state.characters[0]
        char.sick_bay_turns = 3
        char.notes = ""
        events = execute(state)
        assert char.sick_bay_turns == 2


# --- Rules Section Files ---


class TestRulesSections:
    def test_section_files_exist(self):
        from planetfall.rules.loader import SECTIONS_DIR, SECTION_RANGES

        for name in SECTION_RANGES:
            section_file = SECTIONS_DIR / f"{name}.txt"
            assert section_file.exists(), f"Missing section file: {name}.txt"

    def test_load_section_from_file(self):
        from planetfall.rules.loader import load_section, _cache

        _cache.clear()
        text = load_section("introduction")
        assert len(text) > 100
        assert "introduction" in _cache

    def test_list_sections(self):
        from planetfall.rules.loader import list_sections

        sections = list_sections()
        assert len(sections) == 35
        assert "introduction" in sections
        assert "quick_reference" in sections

    def test_search_rules(self):
        from planetfall.rules.loader import search_rules

        results = search_rules("combat", max_results=3)
        assert len(results) >= 1
        assert any("combat" in text.lower() for _, text in results)

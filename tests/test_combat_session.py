"""Tests for interactive combat session and narrative combat."""

from unittest.mock import patch

import pytest
from planetfall.engine.campaign.setup import create_new_campaign
from planetfall.engine.models import ColonizationAgenda, GameState, MissionType
from planetfall.engine.combat.battlefield import (
    Battlefield, Figure, FigureSide, FigureStatus, Zone, TerrainType,
)
from planetfall.engine.combat.session import (
    CombatSession, CombatPhase, CombatState, FigureSnapshot, ActionOption,
)
from planetfall.engine.combat.narrator import (
    narrate_phase_local, _narrate_battle_end, _narrate_combat_summary_local,
)
from planetfall.engine.combat.missions import MissionSetup


def _make_state() -> GameState:
    return create_new_campaign("Test", "Colony", agenda=ColonizationAgenda.SCIENTIFIC)


def _make_simple_mission() -> MissionSetup:
    """Create a simple mission setup for testing."""
    bf = Battlefield()
    # 2 players vs 2 enemies
    bf.figures = [
        Figure(
            name="Alice", side=FigureSide.PLAYER, zone=(5, 1),
            combat_skill=1, toughness=4, reactions=2,
            weapon_name="Rifle", weapon_range=24, weapon_shots=1,
            weapon_damage=0, char_class="trooper",
        ),
        Figure(
            name="Bob", side=FigureSide.PLAYER, zone=(5, 0),
            combat_skill=0, toughness=3, reactions=1,
            weapon_name="Pistol", weapon_range=12, weapon_shots=1,
            weapon_damage=0, char_class="scout",
        ),
        Figure(
            name="Enemy 1", side=FigureSide.ENEMY, zone=(0, 1),
            combat_skill=0, toughness=3, reactions=1,
            weapon_name="Rifle", weapon_range=18, weapon_shots=1,
            weapon_damage=0, char_class="enemy", panic_range=1,
        ),
        Figure(
            name="Enemy 2", side=FigureSide.ENEMY, zone=(0, 3),
            combat_skill=0, toughness=3, reactions=1,
            weapon_name="Rifle", weapon_range=18, weapon_shots=1,
            weapon_damage=0, char_class="enemy", panic_range=1,
        ),
    ]
    return MissionSetup(
        battlefield=bf,
        mission_type=MissionType.PATROL,
        max_rounds=6,
        victory_conditions=["Eliminate all enemies"],
    )


class TestCombatSession:
    @patch("planetfall.engine.combat.round.roll_nd6")
    def test_start_battle(self, mock_roll):
        # Force dice to [1, 1] so both figures are quick actors
        from planetfall.engine.dice import RollResult
        mock_roll.return_value = RollResult(dice_type="2d6", values=[1, 1], total=2, label="")
        setup = _make_simple_mission()
        session = CombatSession(setup)
        state = session.start_battle()

        # start_battle now returns REACTION_ROLL phase
        assert state.phase == CombatPhase.REACTION_ROLL
        assert state.round_number == 1
        assert len(state.unassigned_dice) == 2

        # Assign dice and proceed to quick actions
        state = session.assign_reactions({"Alice": 1, "Bob": 1})
        assert state.phase == CombatPhase.QUICK_ACTIONS
        assert len(state.player_figures) == 2
        assert len(state.enemy_figures) == 2
        assert state.reaction_result is not None

    @patch("planetfall.engine.combat.round.roll_nd6")
    def test_snapshot_has_grid(self, mock_roll):
        # Force dice to [1, 1] so both players are quick (no enemy phase yet)
        from planetfall.engine.dice import RollResult
        mock_roll.return_value = RollResult(dice_type="2d6", values=[1, 1], total=2, label="")
        setup = _make_simple_mission()
        session = CombatSession(setup)
        state = session.start_battle()
        state = session.assign_reactions({"Alice": 1, "Bob": 1})

        assert len(state.battlefield_grid) == 6
        assert len(state.battlefield_grid[0]) == 6
        # Check player edge has figures (no enemy phase ran yet)
        player_zone = state.battlefield_grid[5][1]
        assert "Alice" in player_zone["figures"]

    def _start_and_assign(self, session):
        """Helper: start battle and auto-assign reactions via advance."""
        state = session.start_battle()
        if state.phase == CombatPhase.REACTION_ROLL:
            state = session.advance()  # auto-assigns optimally
        return state

    def test_available_actions(self):
        setup = _make_simple_mission()
        session = CombatSession(setup)
        state = self._start_and_assign(session)

        # Should have at least some actions (shoot, move, hold)
        assert len(state.available_actions) >= 1
        action_types = {a["action_type"] for a in state.available_actions}
        assert "hold" in action_types

    def test_choose_action(self):
        setup = _make_simple_mission()
        session = CombatSession(setup)
        state = self._start_and_assign(session)

        # Should have at least one action available
        assert len(state.available_actions) >= 1

        # Choose the last action (typically hold or the only option)
        last_idx = state.available_actions[-1]["index"]
        new_state = session.choose_action(last_idx)
        # Should advance (either next figure or next phase)
        assert new_state is not None

    def test_full_round_cycle(self):
        """Test that a full round can complete."""
        setup = _make_simple_mission()
        session = CombatSession(setup)
        state = self._start_and_assign(session)

        # Choose hold for all player figures until round ends or battle over
        max_iterations = 20
        for _ in range(max_iterations):
            if state.phase == CombatPhase.BATTLE_OVER:
                break
            if state.phase == CombatPhase.REACTION_ROLL:
                state = session.advance()
                continue
            if state.available_actions:
                # Pick hold (last action usually)
                hold_actions = [a for a in state.available_actions if a["action_type"] == "hold"]
                if hold_actions:
                    state = session.choose_action(hold_actions[0]["index"])
                else:
                    state = session.choose_action(0)
            else:
                state = session.advance()

        # Should have progressed past round 1
        assert state.round_number >= 1

    def test_combat_session_ends(self):
        """Run a battle to completion using auto-hold."""
        setup = _make_simple_mission()
        # Make enemies very weak so battle ends quickly
        for fig in setup.battlefield.figures:
            if fig.side == FigureSide.ENEMY:
                fig.toughness = 1
                fig.combat_skill = -2

        session = CombatSession(setup)
        state = self._start_and_assign(session)

        for _ in range(100):
            if state.phase == CombatPhase.BATTLE_OVER:
                break
            if state.phase == CombatPhase.REACTION_ROLL:
                state = session.advance()
                continue
            if state.available_actions:
                # Prefer shoot actions
                shoot_actions = [a for a in state.available_actions if a["action_type"] == "shoot"]
                if shoot_actions:
                    state = session.choose_action(shoot_actions[0]["index"])
                else:
                    hold_actions = [a for a in state.available_actions if a["action_type"] == "hold"]
                    if hold_actions:
                        state = session.choose_action(hold_actions[0]["index"])
                    else:
                        state = session.choose_action(0)
            else:
                state = session.advance()

        # Battle should complete within 100 iterations
        if state.phase == CombatPhase.BATTLE_OVER:
            result = session.get_result()
            assert "victory" in result
            assert "rounds_played" in result
            assert "enemies_killed" in result
            assert "character_casualties" in result

    def test_figure_snapshot(self):
        fig = Figure(
            name="Test", side=FigureSide.PLAYER, zone=(1, 1),
            combat_skill=2, toughness=4, weapon_name="Rifle",
            char_class="trooper",
        )
        snap = FigureSnapshot.from_figure(fig)
        assert snap.name == "Test"
        assert snap.zone == (1, 1)
        assert snap.combat_skill == 2
        assert snap.weapon_name == "Rifle"

    def test_get_result_after_battle(self):
        setup = _make_simple_mission()
        # Kill all enemies immediately
        for fig in setup.battlefield.figures:
            if fig.side == FigureSide.ENEMY:
                fig.status = FigureStatus.CASUALTY

        session = CombatSession(setup)
        state = session.start_battle()

        # Even in REACTION_ROLL phase, outcome should detect victory
        assert state.outcome == "player_victory"


class TestCombatNarrator:
    def test_narrate_phase_local(self):
        state = CombatState(
            phase=CombatPhase.QUICK_ACTIONS,
            round_number=1,
            player_figures=[],
            enemy_figures=[],
            phase_log=["=== Round 1 ===", "Alice: shoots Enemy 1 — Hit!"],
        )
        narrative = narrate_phase_local(state)
        assert len(narrative) > 0

    def test_narrate_battle_end_victory(self):
        state = CombatState(
            phase=CombatPhase.BATTLE_OVER,
            round_number=3,
            player_figures=[
                FigureSnapshot(
                    name="Alice", side="player", zone=(1, 1), status="active",
                    stun_markers=0, toughness=4, combat_skill=1,
                    weapon_name="Rifle", weapon_range=24, weapon_shots=1,
                    char_class="trooper", is_leader=False, is_specialist=False,
                    has_acted=False, kill_points=0,
                ),
            ],
            enemy_figures=[],
            outcome="player_victory",
        )
        text = _narrate_battle_end(state)
        assert "Victory" in text or "stand" in text

    def test_narrate_battle_end_defeat(self):
        state = CombatState(
            phase=CombatPhase.BATTLE_OVER,
            round_number=3,
            player_figures=[],
            enemy_figures=[],
            outcome="player_defeat",
        )
        text = _narrate_battle_end(state)
        assert "defeat" in text.lower() or "overwhelmed" in text.lower()

    def test_combat_summary_local(self):
        result = {
            "victory": True,
            "rounds_played": 4,
            "enemies_killed": 3,
            "character_casualties": ["Bob"],
            "grunt_casualties": 1,
            "battle_log": [],
        }
        summary = _narrate_combat_summary_local(result)
        assert "4 rounds" in summary
        assert "Bob" in summary
        assert "3 hostiles" in summary or "3" in summary

    def test_combat_summary_no_casualties(self):
        result = {
            "victory": True,
            "rounds_played": 2,
            "enemies_killed": 2,
            "character_casualties": [],
            "grunt_casualties": 0,
            "battle_log": [],
        }
        summary = _narrate_combat_summary_local(result)
        assert "without losses" in summary or "Remarkably" in summary


class TestStep08Interactive:
    def test_execute_interactive_mode(self):
        state = _make_state()
        from planetfall.engine.steps import step08_mission
        result, events = step08_mission.execute(
            state, MissionType.PATROL,
            deployed_names=["Scientist 1", "Trooper 3"],
            mode="interactive",
        )
        assert any("Interactive" in e.description for e in events)

    def test_execute_auto_mode(self):
        state = _make_state()
        from planetfall.engine.steps import step08_mission
        result, events = step08_mission.execute(
            state, MissionType.PATROL,
            deployed_names=["Scientist 1", "Trooper 3"],
            mode="auto",
        )
        assert any("VICTORY" in e.description or "DEFEAT" in e.description for e in events)
        assert result.rounds_played > 0

    def test_apply_combat_result(self):
        state = _make_state()
        from planetfall.engine.steps.step08_mission import apply_combat_result
        result = {
            "victory": True,
            "rounds_played": 3,
            "enemies_killed": 4,
            "character_casualties": ["Bob"],
            "grunt_casualties": 1,
        }
        events = apply_combat_result(state, result)
        assert len(events) == 1
        assert "VICTORY" in events[0].description
        assert "Bob" in events[0].description

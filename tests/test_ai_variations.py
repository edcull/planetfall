"""Tests for AI Variation tables (ploys and AI actions)."""

from unittest.mock import patch

import pytest

from planetfall.engine.combat.battlefield import (
    Battlefield, Figure, FigureSide, FigureStatus, TerrainType, Zone,
)
from planetfall.engine.combat.enemy_ai import (
    roll_ai_variation, _apply_ploy, _apply_ai_action,
    AIVariationResult, TACTICAL_PLOYS, TACTICAL_AI_ACTIONS,
    LIFEFORM_PLOYS, LIFEFORM_AI_ACTIONS,
)
from planetfall.engine.dice import RollResult


def _make_battlefield():
    """Create a battlefield with one player and one enemy."""
    bf = Battlefield()
    player = Figure(name="Player1", side=FigureSide.PLAYER, zone=(2, 1),
                    combat_skill=1, toughness=4)
    enemy = Figure(name="Enemy1", side=FigureSide.ENEMY, zone=(0, 1),
                   combat_skill=0, toughness=3, is_specialist=False)
    bf.figures = [player, enemy]
    return bf, player, enemy


class TestAIVariationTables:
    def test_tactical_ploys_complete(self):
        """All 6 entries exist in tactical ploys table."""
        for i in range(1, 7):
            assert i in TACTICAL_PLOYS
            assert "id" in TACTICAL_PLOYS[i]

    def test_tactical_actions_complete(self):
        for i in range(1, 7):
            assert i in TACTICAL_AI_ACTIONS

    def test_lifeform_ploys_complete(self):
        for i in range(1, 7):
            assert i in LIFEFORM_PLOYS

    def test_lifeform_actions_complete(self):
        for i in range(1, 7):
            assert i in LIFEFORM_AI_ACTIONS


class TestRollAIVariation:
    @patch("planetfall.engine.combat.enemy_ai.roll_d6")
    def test_nothing_happens(self, mock_roll):
        mock_roll.return_value = RollResult(dice_type="d6", values=[3], total=3, label="")
        bf, _, _ = _make_battlefield()
        result = roll_ai_variation(bf, "tactical")
        assert result.variation_type == "nothing"
        assert "Nothing" in result.log[0]

    @patch("planetfall.engine.combat.enemy_ai.roll_d6")
    def test_ploy_triggered(self, mock_roll):
        # First call = variation roll (1 = ploy), second = ploy sub-roll
        mock_roll.side_effect = [
            RollResult(dice_type="d6", values=[1], total=1, label=""),
            RollResult(dice_type="d6", values=[4], total=4, label=""),
        ]
        bf, _, _ = _make_battlefield()
        result = roll_ai_variation(bf, "tactical")
        assert result.variation_type == "ploy"
        assert result.sub_roll == 4
        assert result.entry["id"] == "reinforcements"
        assert any("Ploy" in line for line in result.log)

    @patch("planetfall.engine.combat.enemy_ai.roll_d6")
    def test_ai_action_triggered(self, mock_roll):
        mock_roll.side_effect = [
            RollResult(dice_type="d6", values=[5], total=5, label=""),
            RollResult(dice_type="d6", values=[2], total=2, label=""),
        ]
        bf, _, _ = _make_battlefield()
        result = roll_ai_variation(bf, "tactical")
        assert result.variation_type == "ai_action"
        assert result.sub_roll == 2
        assert result.entry["id"] == "hesitate"

    @patch("planetfall.engine.combat.enemy_ai.roll_d6")
    def test_lifeform_ploy(self, mock_roll):
        mock_roll.side_effect = [
            RollResult(dice_type="d6", values=[1], total=1, label=""),
            RollResult(dice_type="d6", values=[3], total=3, label=""),
        ]
        bf, _, _ = _make_battlefield()
        result = roll_ai_variation(bf, "lifeform")
        assert result.variation_type == "ploy"
        assert result.entry["id"] == "frenzy"

    @patch("planetfall.engine.combat.enemy_ai.roll_d6")
    def test_lifeform_ai_action(self, mock_roll):
        mock_roll.side_effect = [
            RollResult(dice_type="d6", values=[6], total=6, label=""),
            RollResult(dice_type="d6", values=[1], total=1, label=""),
        ]
        bf, _, _ = _make_battlefield()
        result = roll_ai_variation(bf, "lifeform")
        assert result.variation_type == "ai_action"
        assert result.entry["id"] == "focus"


class TestApplyPloy:
    def test_redeploy_to_cover(self):
        bf = Battlefield()
        # Put cover adjacent to enemy
        bf.zones[0][0].terrain = TerrainType.HEAVY_COVER
        enemy = Figure(name="E1", side=FigureSide.ENEMY, zone=(0, 1))
        bf.figures = [enemy]
        entry = {"id": "redeploy", "description": ""}
        result = AIVariationResult(variation_roll=1, variation_type="ploy")

        _apply_ploy(bf, enemy, entry, result)
        assert enemy.zone == (0, 0)  # moved to cover

    def test_recovery_clears_stun(self):
        bf = Battlefield()
        enemy = Figure(name="E1", side=FigureSide.ENEMY, zone=(0, 1),
                      stun_markers=2, status=FigureStatus.STUNNED)
        bf.figures = [enemy]
        entry = {"id": "recovery", "description": ""}
        result = AIVariationResult(variation_roll=1, variation_type="ploy")

        _apply_ploy(bf, enemy, entry, result)
        assert enemy.stun_markers == 0

    def test_recovery_clears_sprawling(self):
        bf = Battlefield()
        enemy = Figure(name="E1", side=FigureSide.ENEMY, zone=(0, 1),
                      status=FigureStatus.SPRAWLING)
        bf.figures = [enemy]
        entry = {"id": "recovery", "description": ""}
        result = AIVariationResult(variation_roll=1, variation_type="ploy")

        _apply_ploy(bf, enemy, entry, result)
        assert enemy.status == FigureStatus.ACTIVE

    def test_recovery_no_effect_when_active(self):
        bf = Battlefield()
        enemy = Figure(name="E1", side=FigureSide.ENEMY, zone=(0, 1))
        bf.figures = [enemy]
        entry = {"id": "recovery", "description": ""}
        result = AIVariationResult(variation_roll=1, variation_type="ploy")

        _apply_ploy(bf, enemy, entry, result)
        assert any("no effect" in line for line in result.log)

    def test_reinforcements(self):
        bf = Battlefield()
        enemy = Figure(name="E1", side=FigureSide.ENEMY, zone=(0, 1))
        bf.figures = [enemy]
        entry = {"id": "reinforcements", "description": ""}
        result = AIVariationResult(variation_roll=1, variation_type="ploy")

        _apply_ploy(bf, enemy, entry, result)
        assert len(bf.figures) == 2  # original + reinforcement
        new_fig = bf.figures[-1]
        assert new_fig.side == FigureSide.ENEMY
        assert new_fig.zone == (0, bf.cols // 2)  # enemy edge center

    def test_concentrated_attack(self):
        bf = Battlefield()
        e1 = Figure(name="E1", side=FigureSide.ENEMY, zone=(0, 0))
        e2 = Figure(name="E2", side=FigureSide.ENEMY, zone=(1, 1))
        bf.figures = [e1, e2]
        entry = {"id": "concentrated_attack", "description": ""}
        result = AIVariationResult(variation_roll=1, variation_type="ploy")

        _apply_ploy(bf, e1, entry, result)
        assert e1.hit_bonus >= 1
        assert e2.hit_bonus >= 1

    def test_frenzy_clears_stun_and_moves(self):
        bf = Battlefield()
        enemy = Figure(name="E1", side=FigureSide.ENEMY, zone=(0, 1),
                      stun_markers=1, status=FigureStatus.SPRAWLING)
        player = Figure(name="P1", side=FigureSide.PLAYER, zone=(2, 1))
        bf.figures = [enemy, player]
        entry = {"id": "frenzy", "description": ""}
        result = AIVariationResult(variation_roll=1, variation_type="ploy")

        _apply_ploy(bf, enemy, entry, result)
        assert enemy.stun_markers == 0
        assert enemy.status == FigureStatus.ACTIVE
        assert enemy.zone[0] > 0 or enemy.zone == (0, 1)  # tried to move toward player

    def test_lurk_adds_special_rule(self):
        bf = Battlefield()
        enemy = Figure(name="E1", side=FigureSide.ENEMY, zone=(0, 1))
        bf.figures = [enemy]
        entry = {"id": "lurk", "description": ""}
        result = AIVariationResult(variation_roll=1, variation_type="ploy")

        _apply_ploy(bf, enemy, entry, result)
        assert "lurking" in enemy.special_rules


class TestApplyAIAction:
    def test_hold_position_moves_to_cover(self):
        bf = Battlefield()
        bf.zones[0][0].terrain = TerrainType.LIGHT_COVER
        enemy = Figure(name="E1", side=FigureSide.ENEMY, zone=(0, 1))
        bf.figures = [enemy]
        entry = {"id": "hold_position", "description": ""}
        result = AIVariationResult(variation_roll=5, variation_type="ai_action")

        _apply_ai_action(bf, enemy, entry, result)
        assert enemy.zone == (0, 0)  # moved to cover
        assert "holding_position" in enemy.special_rules

    def test_hold_position_already_in_cover(self):
        bf = Battlefield()
        bf.zones[0][1].terrain = TerrainType.HEAVY_COVER
        enemy = Figure(name="E1", side=FigureSide.ENEMY, zone=(0, 1))
        bf.figures = [enemy]
        entry = {"id": "hold_position", "description": ""}
        result = AIVariationResult(variation_roll=5, variation_type="ai_action")

        _apply_ai_action(bf, enemy, entry, result)
        assert enemy.zone == (0, 1)  # stays put

    def test_hesitate_marks_acted(self):
        bf = Battlefield()
        enemy = Figure(name="E1", side=FigureSide.ENEMY, zone=(0, 1))
        bf.figures = [enemy]
        entry = {"id": "hesitate", "description": ""}
        result = AIVariationResult(variation_roll=5, variation_type="ai_action")

        _apply_ai_action(bf, enemy, entry, result)
        assert enemy.has_acted is True

    def test_advance_toward_player(self):
        bf = Battlefield()
        enemy = Figure(name="E1", side=FigureSide.ENEMY, zone=(0, 1))
        player = Figure(name="P1", side=FigureSide.PLAYER, zone=(2, 1))
        bf.figures = [enemy, player]
        entry = {"id": "advance", "description": ""}
        result = AIVariationResult(variation_roll=5, variation_type="ai_action")

        _apply_ai_action(bf, enemy, entry, result)
        assert enemy.zone[0] > 0  # moved toward player edge

    def test_group_up_moves_toward_ally(self):
        bf = Battlefield()
        e1 = Figure(name="E1", side=FigureSide.ENEMY, zone=(0, 0))
        e2 = Figure(name="E2", side=FigureSide.ENEMY, zone=(0, 2))
        bf.figures = [e1, e2]
        entry = {"id": "group_up", "description": ""}
        result = AIVariationResult(variation_roll=5, variation_type="ai_action")

        _apply_ai_action(bf, e1, entry, result)
        # E1 should move closer to E2
        assert bf.zone_distance(e1.zone, e2.zone) <= 1

    def test_group_up_no_allies(self):
        bf = Battlefield()
        enemy = Figure(name="E1", side=FigureSide.ENEMY, zone=(0, 1))
        bf.figures = [enemy]
        entry = {"id": "group_up", "description": ""}
        result = AIVariationResult(variation_roll=5, variation_type="ai_action")

        _apply_ai_action(bf, enemy, entry, result)
        assert any("no allies" in line for line in result.log)

    def test_focus_sets_target(self):
        bf = Battlefield()
        enemy = Figure(name="E1", side=FigureSide.ENEMY, zone=(0, 1))
        player = Figure(name="P1", side=FigureSide.PLAYER, zone=(2, 1))
        bf.figures = [enemy, player]
        entry = {"id": "focus", "description": ""}
        result = AIVariationResult(variation_roll=5, variation_type="ai_action")

        _apply_ai_action(bf, enemy, entry, result)
        assert any("focus:P1" in rule for rule in enemy.special_rules)

    def test_move_to_cover(self):
        bf = Battlefield()
        bf.zones[0][0].terrain = TerrainType.HEAVY_COVER
        enemy = Figure(name="E1", side=FigureSide.ENEMY, zone=(0, 1))
        bf.figures = [enemy]
        entry = {"id": "move_to_cover", "description": ""}
        result = AIVariationResult(variation_roll=5, variation_type="ai_action")

        _apply_ai_action(bf, enemy, entry, result)
        assert enemy.zone == (0, 0)

    def test_move_to_cover_already_in_cover(self):
        bf = Battlefield()
        bf.zones[0][1].terrain = TerrainType.HEAVY_COVER
        enemy = Figure(name="E1", side=FigureSide.ENEMY, zone=(0, 1))
        bf.figures = [enemy]
        entry = {"id": "move_to_cover", "description": ""}
        result = AIVariationResult(variation_roll=5, variation_type="ai_action")

        _apply_ai_action(bf, enemy, entry, result)
        assert enemy.zone == (0, 1)  # stays
        assert any("already in cover" in line for line in result.log)

    def test_move_to_flank(self):
        bf = Battlefield()
        enemy = Figure(name="E1", side=FigureSide.ENEMY, zone=(1, 1))  # center
        bf.figures = [enemy]
        entry = {"id": "move_to_flank", "description": ""}
        result = AIVariationResult(variation_roll=5, variation_type="ai_action")

        _apply_ai_action(bf, enemy, entry, result)
        # Should move to a col=0 or col=2 zone
        assert enemy.zone[1] == 0 or enemy.zone[1] == 2


class TestEnemyPhaseWithVariations:
    @patch("planetfall.engine.combat.enemy_ai.roll_d6")
    def test_execute_enemy_phase_with_variations(self, mock_roll):
        """Integration test: enemy phase with AI variations enabled."""
        from planetfall.engine.combat.round import execute_enemy_phase

        # AI variation roll = 3 (nothing), then enemy action rolls
        mock_roll.side_effect = [
            RollResult(dice_type="d6", values=[3], total=3, label="AI Var"),
            # Enemy shooting rolls
            RollResult(dice_type="d6", values=[6], total=6, label="hit"),
            RollResult(dice_type="d6", values=[6], total=6, label="dmg"),
        ]

        bf, player, enemy = _make_battlefield()
        enemy.weapon_range = 24
        results = execute_enemy_phase(bf, use_ai_variations=True, enemy_type="tactical")
        # Should have at least the variation result + enemy activation
        assert len(results) >= 1

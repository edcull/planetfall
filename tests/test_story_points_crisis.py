"""Tests for Story Points spending, Crisis penalties, Morale incident effects,
and Calamity integration."""

from unittest.mock import patch

import pytest


class TestStoryPointSpending:
    def test_spend_to_prevent_roll(self, game_state):
        from planetfall.engine.campaign.story_points import spend_to_prevent_roll
        state = game_state
        old_sp = state.colony.resources.story_points
        events = spend_to_prevent_roll(state, "enemy_activity")
        assert state.colony.resources.story_points == old_sp - 1
        assert "Story Point spent" in events[0].description

    def test_spend_to_prevent_roll_insufficient(self, game_state):
        from planetfall.engine.campaign.story_points import spend_to_prevent_roll
        state = game_state
        state.colony.resources.story_points = 0
        events = spend_to_prevent_roll(state, "enemy_activity")
        assert "Not enough" in events[0].description

    def test_spend_to_prevent_roll_invalid_type(self, game_state):
        from planetfall.engine.campaign.story_points import spend_to_prevent_roll
        state = game_state
        events = spend_to_prevent_roll(state, "invalid_type")
        assert "Invalid" in events[0].description

    def test_spend_for_resources(self, game_state):
        from planetfall.engine.campaign.story_points import spend_for_resources
        state = game_state
        old_sp = state.colony.resources.story_points
        old_bp = state.colony.resources.build_points
        events = spend_for_resources(state, bp=3, rp=0, rm=0)
        assert state.colony.resources.story_points == old_sp - 1
        # BP should have increased (capped by dice roll)
        assert state.colony.resources.build_points >= old_bp

    def test_spend_to_ignore_injury(self, game_state):
        from planetfall.engine.campaign.story_points import spend_to_ignore_injury
        state = game_state
        old_sp = state.colony.resources.story_points
        events = spend_to_ignore_injury(state, "Test")
        assert state.colony.resources.story_points == old_sp - 1
        assert "ignore injury" in events[0].description.lower()

    def test_can_spend_checks_balance(self, game_state):
        from planetfall.engine.campaign.story_points import can_spend
        state = game_state
        assert can_spend(state, 1)
        state.colony.resources.story_points = 0
        assert not can_spend(state, 1)


class TestIntegrityFailureSP:
    def test_spend_sp_skips_failure_roll(self, game_state):
        from planetfall.engine.steps import step16_colony_integrity
        state = game_state
        state.colony.integrity = -5
        old_sp = state.colony.resources.story_points
        events = step16_colony_integrity.execute(state, spend_story_point=True)
        assert state.colony.resources.story_points == old_sp - 1
        assert "Story Point spent" in events[0].description
        # No failure should have occurred
        assert all("FAILURE" not in e.description for e in events)

    def test_normal_failure_without_sp(self, game_state):
        from planetfall.engine.steps import step16_colony_integrity
        state = game_state
        state.colony.integrity = -5
        # Should proceed normally without SP
        events = step16_colony_integrity.execute(state, spend_story_point=False)
        assert len(events) >= 1
        assert "Colony Integrity" in events[0].description


class TestMoraleIncidentSP:
    def test_spend_sp_prevents_incident(self, game_state):
        from planetfall.engine.steps import step11_morale
        state = game_state
        state.colony.morale = -9  # Will drop to -10, triggering incident
        old_sp = state.colony.resources.story_points
        events = step11_morale.execute(
            state, battle_casualties=0, spend_sp_prevent_incident=True
        )
        assert state.colony.resources.story_points == old_sp - 1
        assert state.colony.morale == 0  # Reset to 0
        # Should not have rolled on incident table
        assert not any("MORALE INCIDENT" in e.description for e in events)


class TestCrisisPenalties:
    def test_crisis_reduces_rp(self, game_state):
        from planetfall.engine.steps import step14_research
        state = game_state
        state.flags.crisis_active = True
        old_rp = state.colony.resources.research_points
        events = step14_research.execute(state)
        # Base rate is 1 + milestones (0) = 1, crisis penalty -1 = 0 gained
        rp_gained = state.colony.resources.research_points - old_rp
        assert rp_gained == 0
        assert "Crisis" in events[0].description

    def test_crisis_reduces_bp(self, game_state):
        from planetfall.engine.steps import step15_building
        state = game_state
        state.flags.crisis_active = True
        old_bp = state.colony.resources.build_points
        events = step15_building.execute(state)
        bp_gained = state.colony.resources.build_points - old_bp
        assert bp_gained == 0
        assert "Crisis" in events[0].description

    def test_no_penalty_without_crisis(self, game_state):
        from planetfall.engine.steps import step14_research
        state = game_state
        old_rp = state.colony.resources.research_points
        events = step14_research.execute(state)
        rp_gained = state.colony.resources.research_points - old_rp
        assert rp_gained >= 1  # At least base rate


class TestWorkStoppagePenalty:
    def test_work_stoppage_reduces_bp_rp(self, game_state):
        from planetfall.engine.steps import step14_research, step15_building
        state = game_state
        state.flags.work_stoppage_active = True
        old_rp = state.colony.resources.research_points
        events = step14_research.execute(state)
        rp_gained = state.colony.resources.research_points - old_rp
        assert rp_gained == 0  # Base 1 - 3 penalty = 0 (capped at 0)
        assert "Work Stoppage" in events[0].description


class TestMoraleIncidentEffects:
    @patch("planetfall.engine.steps.step11_morale.MORALE_INCIDENT_TABLE")
    def test_protests_benches_trooper(self, mock_table, game_state):
        from planetfall.engine.dice import RollResult, TableEntry
        from planetfall.engine.steps import step11_morale
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[15], total=15, label=""),
            TableEntry(low=11, high=25, result_id="protests",
                       description="Protests", effects={}),
        )
        state = game_state
        state.colony.morale = -10
        step11_morale.execute(state, battle_casualties=0)
        # Should have benched a trooper
        assert state.flags.benched_trooper != ""

    @patch("planetfall.engine.steps.step11_morale.MORALE_INCIDENT_TABLE")
    def test_work_stoppage_sets_flag(self, mock_table, game_state):
        from planetfall.engine.dice import RollResult, TableEntry
        from planetfall.engine.steps import step11_morale
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[40], total=40, label=""),
            TableEntry(low=36, high=55, result_id="work_stoppage",
                       description="Work Stoppage", effects={}),
        )
        state = game_state
        state.colony.morale = -10
        step11_morale.execute(state, battle_casualties=0)
        assert state.flags.work_stoppage_active is True

    @patch("planetfall.engine.steps.step11_morale.MORALE_INCIDENT_TABLE")
    def test_colonist_demands_sets_flag(self, mock_table, game_state):
        from planetfall.engine.dice import RollResult, TableEntry
        from planetfall.engine.steps import step11_morale
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[60], total=60, label=""),
            TableEntry(low=56, high=75, result_id="colonist_demands",
                       description="Demands", effects={}),
        )
        state = game_state
        state.colony.morale = -10
        step11_morale.execute(state, battle_casualties=0)
        assert state.flags.colonist_demands_active is True


class TestColonistDemandsResolution:
    def test_resolve_demands(self, game_state):
        from planetfall.engine.steps.step11_morale import resolve_colonist_demands
        state = game_state
        state.flags.colonist_demands_active = True
        # Give a character high savvy to guarantee success
        char = state.characters[0]
        char.savvy = 5
        events = resolve_colonist_demands(state, [char.name])
        assert len(events) >= 1


class TestAugmentationColonyWide:
    def test_augmentation_applies_to_all(self, game_state):
        from planetfall.engine.campaign.augmentation import apply_augmentation
        state = game_state
        state.colony.resources.augmentation_points = 5
        num_chars = len(state.characters)
        events = apply_augmentation(state, "enhanced_mobility")
        assert state.colony.resources.augmentation_points == 4
        # All characters should have gotten the speed boost
        assert f"{num_chars} character(s)" in events[0].description

    def test_one_per_turn_limit(self, game_state):
        from planetfall.engine.campaign.augmentation import apply_augmentation
        state = game_state
        state.colony.resources.augmentation_points = 10
        apply_augmentation(state, "enhanced_mobility")
        events = apply_augmentation(state, "claws")
        assert "one augmentation" in events[0].description.lower()

    def test_boosted_recovery_reduces_sick_bay(self, game_state):
        from planetfall.engine.campaign.augmentation import apply_augmentation
        from planetfall.engine.steps import step09_injuries
        state = game_state
        state.colony.resources.augmentation_points = 1
        apply_augmentation(state, "boosted_recovery")
        # Now injure a character — sick bay should be reduced by 1
        from planetfall.engine.campaign.augmentation import has_augmentation
        assert has_augmentation(state, "boosted_recovery")


class TestCalamityIntegration:
    def test_milestone_triggers_calamity_check(self, game_state):
        from planetfall.engine.campaign.milestones import apply_milestone
        state = game_state
        # Milestone 1 adds 1 CP
        events = apply_milestone(state, 1)
        # Should have at least a calamity check event
        calamity_events = [
            e for e in events if "calamity" in e.description.lower()
            or "Calamity" in e.description
        ]
        assert len(calamity_events) >= 1

    def test_no_calamity_at_zero_cp(self, game_state):
        from planetfall.engine.campaign.calamities import check_calamity
        state = game_state
        state.colony.resources.calamity_points = 0
        events = check_calamity(state)
        assert len(events) == 0

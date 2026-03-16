"""Tests for Phase 4: Research, Buildings, Milestones, Narrative."""

import pytest
from planetfall.engine.models import (
    GameState, Theory, Building,
)
from planetfall.engine.campaign.research import (
    THEORIES, APPLICATIONS, MILESTONE_APPLICATIONS,
    get_available_theories, get_available_applications,
    invest_in_theory, unlock_application, perform_bio_analysis,
)
from planetfall.engine.campaign.buildings import (
    BUILDINGS, get_available_buildings, invest_in_building,
    process_per_turn_buildings, reclaim_building,
)
from planetfall.engine.campaign.milestones import (
    MILESTONE_EFFECTS, apply_milestone, check_and_apply_milestones,
    roll_lifeform_evolution, run_summit_votes, get_viable_paths,
)
from planetfall.engine.steps import step14_research, step15_building
from planetfall.narrative import (
    build_narrative_prompt, generate_narrative_local, get_narrative_summary,
    init_narrative_memory,
)


# --- Research tests ---

class TestResearch:
    def test_theories_exist(self):
        assert len(THEORIES) == 13  # 8 primary + 5 secondary

    def test_applications_exist(self):
        assert len(APPLICATIONS) > 40

    def test_all_applications_have_valid_theory(self):
        for app_id, app in APPLICATIONS.items():
            assert app.theory_id in THEORIES, f"{app_id} references invalid theory {app.theory_id}"

    def test_all_theory_applications_exist(self):
        for tid, theory in THEORIES.items():
            for app_id in theory.applications:
                assert app_id in APPLICATIONS, f"Theory {tid} references invalid app {app_id}"

    def test_available_theories_initial(self, game_state_scientific):
        state = game_state_scientific
        available = get_available_theories(state)
        # Only primary theories (no prerequisites) should be available
        assert len(available) == 8
        assert all(t.prerequisite == "" for t in available)

    def test_invest_in_theory(self, game_state_scientific):
        state = game_state_scientific
        state.colony.resources.research_points = 10
        events = invest_in_theory(state, "infantry_equipment", 2)
        assert len(events) >= 1
        assert state.colony.resources.research_points == 8
        theory = state.tech_tree.theories["infantry_equipment"]
        assert theory.invested_rp == 2
        assert theory.completed  # cost is 2

    def test_invest_partial_theory(self, game_state_scientific):
        state = game_state_scientific
        state.colony.resources.research_points = 2
        events = invest_in_theory(state, "ai_theories", 2)
        theory = state.tech_tree.theories["ai_theories"]
        assert theory.invested_rp == 2
        assert not theory.completed  # cost is 4

    def test_secondary_theory_requires_prerequisite(self, game_state_scientific):
        state = game_state_scientific
        available = get_available_theories(state)
        secondary_ids = {t.id for t in available if t.prerequisite != ""}
        assert len(secondary_ids) == 0

        # Complete a prerequisite
        state.tech_tree.theories["environmental_research"] = Theory(
            name="Environmental Research", invested_rp=2, required_rp=2, completed=True
        )
        available = get_available_theories(state)
        secondary_ids = {t.id for t in available if t.prerequisite != ""}
        assert "environmental_adaptation" in secondary_ids

    def test_unlock_application(self, game_state_scientific):
        state = game_state_scientific
        state.colony.resources.research_points = 10
        # Complete theory first
        state.tech_tree.theories["infantry_equipment"] = Theory(
            name="Infantry Equipment", invested_rp=2, required_rp=2, completed=True
        )
        events = unlock_application(state, "carver_blade")
        assert "carver_blade" in state.tech_tree.unlocked_applications
        assert state.colony.resources.research_points == 8  # cost 2

    def test_application_with_morale_effect(self, game_state_scientific):
        state = game_state_scientific
        state.colony.resources.research_points = 10
        state.tech_tree.theories["social_theories"] = Theory(
            name="Social Theories", invested_rp=3, required_rp=3, completed=True
        )
        old_morale = state.colony.morale
        events = unlock_application(state, "conflict_resolution")
        assert state.colony.morale == old_morale + 4

    def test_milestone_application(self, game_state_scientific):
        state = game_state_scientific
        state.colony.resources.research_points = 10
        state.tech_tree.theories["social_theories"] = Theory(
            name="Social Theories", invested_rp=3, required_rp=3, completed=True
        )
        old_milestones = state.campaign.milestones_completed
        events = unlock_application(state, "frontier_doctrines")
        assert state.campaign.milestones_completed == old_milestones + 1

    def test_bio_analysis(self, game_state_scientific):
        from planetfall.engine.models import LifeformEntry
        state = game_state_scientific
        state.colony.resources.research_points = 5
        # Need a specimen to analyze
        state.enemies.lifeform_table.append(
            LifeformEntry(d100_low=1, d100_high=18, name="TestCreature", specimen_collected=True)
        )
        events = perform_bio_analysis(state, lifeform_name="TestCreature")
        assert len(events) == 1
        assert "Bio-analysis" in events[0].description
        assert state.colony.resources.research_points == 2

    def test_bio_analysis_insufficient_rp(self, game_state_scientific):
        state = game_state_scientific
        state.colony.resources.research_points = 1
        events = perform_bio_analysis(state)
        assert "Not enough" in events[0].description

    def test_not_enough_rp_for_application(self, game_state_scientific):
        state = game_state_scientific
        state.colony.resources.research_points = 0
        state.tech_tree.theories["infantry_equipment"] = Theory(
            name="Infantry Equipment", invested_rp=2, required_rp=2, completed=True
        )
        events = unlock_application(state, "carver_blade")
        assert "Not enough" in events[0].description


# --- Building tests ---

class TestBuildings:
    def test_buildings_defined(self):
        assert len(BUILDINGS) > 30

    def test_available_buildings_initial(self, game_state_scientific):
        state = game_state_scientific
        available = get_available_buildings(state)
        # Only no-prerequisite buildings
        no_prereq = [b for b in available if b.prerequisite == ""]
        assert len(no_prereq) >= 10

    def test_invest_in_building_partial(self, game_state_scientific):
        state = game_state_scientific
        state.colony.resources.build_points = 3
        events = invest_in_building(state, "advanced_manufacturing_plant", 3)
        assert len(events) >= 1
        progress = dict(state.tracking.construction_progress)
        assert progress.get("advanced_manufacturing_plant") == 3

    def test_invest_in_building_complete(self, game_state_scientific):
        state = game_state_scientific
        state.colony.resources.build_points = 10
        events = invest_in_building(state, "advanced_manufacturing_plant", 4)
        assert any("completed" in e.description.lower() for e in events)
        assert any(b.name == "Advanced Manufacturing Plant" for b in state.colony.buildings)

    def test_building_with_effects(self, game_state_scientific):
        state = game_state_scientific
        state.colony.resources.build_points = 10
        old_defenses = state.colony.defenses
        events = invest_in_building(state, "patrol_base", 4)
        assert state.colony.defenses == old_defenses + 1

    def test_milestone_building(self, game_state_scientific):
        state = game_state_scientific
        state.colony.resources.build_points = 20
        # Need prerequisite for galactic_comms
        state.tech_tree.unlocked_applications.append("galactic_comms")
        old_milestones = state.campaign.milestones_completed
        events = invest_in_building(state, "galactic_comms", 10)
        assert state.campaign.milestones_completed == old_milestones + 1

    def test_raw_materials_conversion(self, game_state_scientific):
        state = game_state_scientific
        state.colony.resources.build_points = 2
        state.colony.resources.raw_materials = 5
        events = invest_in_building(state, "advanced_manufacturing_plant", 2, raw_materials_convert=2)
        # Should have used 2 BP + 2 RM = 4 total
        assert state.colony.resources.raw_materials == 3
        assert any("completed" in e.description.lower() for e in events)

    def test_per_turn_building_effects(self, game_state_scientific):
        state = game_state_scientific
        # No buildings -> no effects
        events = process_per_turn_buildings(state)
        assert len(events) == 0

    def test_reclaim_building(self, game_state_scientific):
        state = game_state_scientific
        state.colony.buildings.append(Building(
            name="Patrol Base", built_turn=1, effects=["1 Colony Defense"]
        ))
        old_rm = state.colony.resources.raw_materials
        events = reclaim_building(state, "Patrol Base")
        assert len(state.colony.buildings) == 0
        assert state.colony.resources.raw_materials == old_rm + 2  # 4//2

    def test_prerequisite_building(self, game_state_scientific):
        state = game_state_scientific
        available = get_available_buildings(state)
        # "research_lab" requires "research_lab" application
        lab_available = any(b.id == "research_lab" for b in available)
        assert not lab_available

        # Unlock the application
        state.tech_tree.unlocked_applications.append("research_lab")
        available = get_available_buildings(state)
        lab_available = any(b.id == "research_lab" for b in available)
        assert lab_available


# --- Milestone tests ---

class TestMilestones:
    def test_milestone_effects_defined(self):
        assert len(MILESTONE_EFFECTS) == 7

    def test_apply_milestone_1(self, game_state_scientific):
        state = game_state_scientific
        # Prevent breakthrough from consuming mission data
        state.tracking.breakthroughs_count = 4
        # Disable calamities so the CP check isn't consumed by a triggered calamity
        state.tracking.calamities_disabled = True
        events = apply_milestone(state, 1)
        assert len(events) >= 2  # description + lifeform evolution
        assert state.campaign.mission_data_count >= 1
        assert state.colony.resources.calamity_points >= 1

    def test_apply_milestone_7_triggers_end_game(self, game_state_scientific):
        state = game_state_scientific
        events = apply_milestone(state, 7)
        assert state.campaign.end_game_triggered

    def test_check_and_apply_new_milestones(self, game_state_scientific):
        state = game_state_scientific
        state.campaign.milestones_completed = 2
        events = check_and_apply_milestones(state, 0)
        # Should apply milestones 1 and 2
        assert len(events) >= 4  # 2 milestones * (description + evolution)

    def test_lifeform_evolution_roll(self):
        result = roll_lifeform_evolution()
        assert "name" in result
        assert "description" in result

    def test_summit_votes(self, game_state_scientific):
        state = game_state_scientific
        votes = run_summit_votes(state)
        assert isinstance(votes, dict)
        total_voters = sum(len(v) for v in votes.values())
        assert total_voters == len(state.characters) + 1  # +1 for population

    def test_viable_paths(self):
        votes = {
            "Independence": ["Alice", "Population"],
            "Ascension": [],
            "Loyalty": ["Bob"],
            "Isolation": [],
            "No opinion": ["Charlie"],
        }
        viable = get_viable_paths(votes)
        assert "Independence" in viable
        assert "Loyalty" in viable
        assert "Ascension" not in viable


# --- Step 14/15 integration ---

class TestStepIntegration:
    def test_step14_basic(self, game_state_scientific):
        state = game_state_scientific
        events = step14_research.execute(state)
        assert len(events) >= 1
        assert state.colony.resources.research_points >= 1

    def test_step14_with_theory(self, game_state_scientific):
        state = game_state_scientific
        state.colony.resources.research_points = 5
        events = step14_research.execute(
            state, theory_id="infantry_equipment", theory_rp=2
        )
        assert any("Infantry Equipment" in e.description for e in events)
        theory = state.tech_tree.theories.get("infantry_equipment")
        assert theory and theory.completed

    def test_step14_get_options(self, game_state_scientific):
        state = game_state_scientific
        options = step14_research.get_research_options(state)
        assert "theories" in options
        assert "applications" in options
        assert len(options["theories"]) == 8  # 8 primary theories

    def test_step15_basic(self, game_state_scientific):
        state = game_state_scientific
        events = step15_building.execute(state)
        assert len(events) >= 1
        assert state.colony.resources.build_points >= 1

    def test_step15_with_building(self, game_state_scientific):
        state = game_state_scientific
        state.colony.resources.build_points = 10
        events = step15_building.execute(
            state, building_id="patrol_base", bp_amount=4
        )
        assert any("Patrol Base" in e.description for e in events)

    def test_step15_get_options(self, game_state_scientific):
        state = game_state_scientific
        options = step15_building.get_building_options(state)
        assert "available" in options
        assert "built" in options
        assert len(options["available"]) >= 10


# --- Narrative tests ---

class TestNarrative:
    def test_init_memory(self, game_state_scientific):
        state = game_state_scientific
        init_narrative_memory(state)
        assert isinstance(state.narrative.themes, list)
        assert isinstance(state.narrative.character_arcs, dict)
        assert isinstance(state.narrative.key_events, list)

    def test_build_prompt(self, game_state_scientific):
        state = game_state_scientific
        from planetfall.engine.models import TurnEvent, TurnEventType
        events = [TurnEvent(
            step=5, event_type=TurnEventType.COLONY_EVENT,
            description="Supply ship arrives with fresh provisions",
        )]
        prompt = build_narrative_prompt(state, events)
        assert "Colony" in prompt
        assert "Supply ship" in prompt
        assert "gritty frontier sci-fi" in prompt

    def test_generate_local_narrative(self, game_state_scientific):
        state = game_state_scientific
        from planetfall.engine.models import TurnEvent, TurnEventType
        events = [TurnEvent(
            step=8, event_type=TurnEventType.COMBAT,
            description="Patrol mission: Victory in 4 rounds",
        )]
        narrative = generate_narrative_local(state, events)
        assert "Battle report" in narrative
        assert len(narrative) > 0

    def test_narrative_memory_updates(self, game_state_scientific):
        state = game_state_scientific
        from planetfall.engine.models import TurnEvent, TurnEventType
        events = [TurnEvent(
            step=8, event_type=TurnEventType.COMBAT,
            description="Fierce battle at the ridge",
        )]
        generate_narrative_local(state, events)
        assert len(state.narrative.key_events) > 0

    def test_get_summary_empty(self, game_state_scientific):
        state = game_state_scientific
        summary = get_narrative_summary(state)
        assert "Colony" in summary

    def test_get_summary_with_history(self, game_state_scientific):
        state = game_state_scientific
        init_narrative_memory(state)
        state.narrative.key_events = [
            "Turn 1: Colony established",
            "Turn 2: First contact with lifeforms",
        ]
        summary = get_narrative_summary(state)
        assert "Turn 1" in summary

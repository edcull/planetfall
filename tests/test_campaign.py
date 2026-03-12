"""Tests for campaign setup and step functions."""

import pytest
from planetfall.engine.campaign.setup import (
    create_new_campaign,
    create_character,
    generate_campaign_map,
    roll_motivation,
    AGENDA_EFFECTS,
)
from planetfall.engine.models import (
    CharacterClass, ColonizationAgenda, GameState,
    SectorStatus, SubSpecies, STARTING_PROFILES,
)
from planetfall.engine.steps import (
    step01_recovery,
    step02_repairs,
    step05_colony_events,
    step09_injuries,
    step10_experience,
    step11_morale,
    step13_replacements,
    step14_research,
    step15_building,
    step16_colony_integrity,
    step17_character_event,
)


class TestCampaignSetup:
    def test_create_default_campaign(self):
        state = create_new_campaign(
            campaign_name="Test",
            colony_name="TestColony",
            agenda=ColonizationAgenda.UNITY,
        )
        assert state.campaign_name == "Test"
        assert state.colony.name == "TestColony"
        assert len(state.characters) == 8
        assert state.grunts.count == 12
        assert state.colony.resources.raw_materials == 3  # Unity bonus
        assert len(state.campaign_map.sectors) == 36

    def test_agenda_effects(self):
        # Scientific
        state = create_new_campaign("T", "C", agenda=ColonizationAgenda.SCIENTIFIC)
        assert state.colony.resources.research_points == 3

        # Military
        state = create_new_campaign("T", "C", agenda=ColonizationAgenda.MILITARY)
        assert state.grunts.count == 14

        # Affinity
        state = create_new_campaign("T", "C", agenda=ColonizationAgenda.AFFINITY)
        assert state.colony.morale == 5

        # Independent
        state = create_new_campaign("T", "C", agenda=ColonizationAgenda.INDEPENDENT)
        assert state.colony.resources.story_points >= 6

    def test_create_character(self):
        char = create_character("Test", CharacterClass.TROOPER, experienced=True)
        assert char.name == "Test"
        assert char.char_class == CharacterClass.TROOPER
        assert char.reactions == 2 or char.reactions > 2  # May have exp bonus
        assert char.background_motivation != ""
        assert char.background_prior_experience != ""

    def test_hulker_subspecies(self):
        char = create_character(
            "Hulk", CharacterClass.TROOPER, sub_species=SubSpecies.HULKER
        )
        assert char.toughness == 5

    def test_map_generation(self):
        campaign_map = generate_campaign_map()
        assert len(campaign_map.sectors) == 36
        colony = campaign_map.sectors[campaign_map.colony_sector_id]
        assert colony.status == SectorStatus.EXPLOITED
        investigation_count = sum(
            1 for s in campaign_map.sectors if s.has_investigation_site
        )
        assert investigation_count == 10


class TestStepFunctions:
    def _make_state(self) -> GameState:
        return create_new_campaign("T", "C", agenda=ColonizationAgenda.UNITY)

    def test_step1_recovery(self):
        state = self._make_state()
        state.characters[0].sick_bay_turns = 2
        events = step01_recovery.execute(state)
        assert state.characters[0].sick_bay_turns == 1
        assert len(events) >= 1

    def test_step1_full_recovery(self):
        state = self._make_state()
        state.characters[0].sick_bay_turns = 1
        events = step01_recovery.execute(state)
        assert state.characters[0].sick_bay_turns == 0
        assert "fully recovered" in events[0].description

    def test_step2_no_damage(self):
        state = self._make_state()
        events = step02_repairs.execute(state)
        assert "undamaged" in events[0].description.lower() or "no repairs" in events[0].description.lower()

    def test_step2_with_damage(self):
        state = self._make_state()
        state.colony.integrity = -3
        state.colony.resources.raw_materials = 5
        events = step02_repairs.execute(state, raw_materials_spent=2)
        assert state.colony.integrity > -3
        assert state.colony.resources.raw_materials == 3

    def test_step5_colony_events(self):
        state = self._make_state()
        events = step05_colony_events.execute(state)
        assert len(events) == 1
        assert events[0].event_type.value == "colony_event"

    def test_step9_no_casualties(self):
        state = self._make_state()
        events = step09_injuries.execute(state, [], 0)
        assert "No casualties" in events[0].description

    def test_step11_morale_auto_drop(self):
        state = self._make_state()
        old_morale = state.colony.morale
        events = step11_morale.execute(state, battle_casualties=0)
        # -1 automatic each campaign turn
        assert state.colony.morale == old_morale - 1

    def test_step11_morale_with_casualties(self):
        state = self._make_state()
        old_morale = state.colony.morale
        events = step11_morale.execute(state, battle_casualties=3)
        # -1 automatic + -3 for casualties = -4 total
        assert state.colony.morale == old_morale - 4

    def test_step13_full_roster(self):
        state = self._make_state()
        events = step13_replacements.execute(state)
        assert "full" in events[0].description.lower()

    def test_step13_vacancies(self):
        state = self._make_state()
        state.characters.pop()
        events = step13_replacements.execute(state)
        assert "1 vacancy" in events[0].description

    def test_step14_research(self):
        state = self._make_state()
        old_rp = state.colony.resources.research_points
        events = step14_research.execute(state)
        assert state.colony.resources.research_points == old_rp + 1

    def test_step15_building(self):
        state = self._make_state()
        old_bp = state.colony.resources.build_points
        events = step15_building.execute(state)
        assert state.colony.resources.build_points == old_bp + 1

    def test_step16_stable(self):
        state = self._make_state()
        events = step16_colony_integrity.execute(state)
        assert "stable" in events[0].description.lower()

    def test_step16_damaged(self):
        state = self._make_state()
        state.colony.integrity = -5
        events = step16_colony_integrity.execute(state)
        # Should roll for failure or report damage
        desc = events[0].description.lower()
        assert "integrity" in desc

    def test_step17_character_event(self):
        state = self._make_state()
        events = step17_character_event.execute(state)
        assert len(events) == 1
        assert events[0].event_type.value == "character_event"

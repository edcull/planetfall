"""Tests for new game systems: augmentation, calamities, Slyn, equipment,
extraction, ancient signs, post-mission finds, battlefield conditions."""

import pytest
from planetfall.engine.campaign.setup import create_new_campaign
from planetfall.engine.models import (
    ColonizationAgenda, GameState, SectorStatus, CharacterClass,
)


def _make_state() -> GameState:
    return create_new_campaign("Test", "Colony", agenda=ColonizationAgenda.SCIENTIFIC)


# --- Augmentation tests ---

class TestAugmentation:
    def test_augmentations_catalog(self):
        from planetfall.engine.campaign.augmentation import AUGMENTATIONS
        assert len(AUGMENTATIONS) == 8

    def test_get_available_augmentations(self):
        from planetfall.engine.campaign.augmentation import get_available_augmentations
        state = _make_state()
        state.colony.resources.augmentation_points = 5
        available = get_available_augmentations(state)
        assert len(available) == 8
        assert all(a["affordable"] for a in available)
        assert all(a["cost"] == 1 for a in available)

    def test_apply_augmentation(self):
        from planetfall.engine.campaign.augmentation import apply_augmentation
        state = _make_state()
        state.colony.resources.augmentation_points = 3
        events = apply_augmentation(state, "enhanced_mobility")
        assert len(events) >= 1
        assert "Enhanced Mobility" in events[0].description
        assert state.colony.resources.augmentation_points == 2
        # Colony-wide: all characters should get speed boost
        for char in state.characters:
            if char.sub_species.value != "soulless" and char.char_class.value != "bot":
                assert char.speed >= 5  # base speed + 1

    def test_progressive_cost(self):
        from planetfall.engine.campaign.augmentation import (
            apply_augmentation, get_augmentation_cost,
        )
        state = _make_state()
        state.colony.resources.augmentation_points = 10
        assert get_augmentation_cost(state) == 1
        apply_augmentation(state, "enhanced_mobility")
        state.flags.augmentation_bought_this_turn = False
        assert get_augmentation_cost(state) == 2
        apply_augmentation(state, "claws")
        state.flags.augmentation_bought_this_turn = False
        assert get_augmentation_cost(state) == 3

    def test_duplicate_augmentation_rejected(self):
        from planetfall.engine.campaign.augmentation import apply_augmentation
        state = _make_state()
        state.colony.resources.augmentation_points = 10
        apply_augmentation(state, "claws")
        state.flags.augmentation_bought_this_turn = False
        events = apply_augmentation(state, "claws")
        assert "already has" in events[0].description

    def test_insufficient_ap(self):
        from planetfall.engine.campaign.augmentation import apply_augmentation
        state = _make_state()
        state.colony.resources.augmentation_points = 0
        events = apply_augmentation(state, "claws")
        assert "Not enough AP" in events[0].description


# --- Calamity tests ---

class TestCalamities:
    def test_calamity_table_coverage(self):
        from planetfall.engine.campaign.calamities import CALAMITY_TABLE
        assert len(CALAMITY_TABLE) == 8

    def test_no_calamity_when_zero_cp(self):
        from planetfall.engine.campaign.calamities import check_calamity
        state = _make_state()
        state.colony.resources.calamity_points = 0
        events = check_calamity(state)
        assert events == []

    def test_calamity_check_with_cp(self):
        from planetfall.engine.campaign.calamities import check_calamity
        state = _make_state()
        state.colony.resources.calamity_points = 6  # High CP, always triggers
        events = check_calamity(state)
        # Should always get at least a check result
        assert len(events) >= 1

    def test_resolve_mega_predators(self):
        from planetfall.engine.campaign.calamities import resolve_calamity_progress
        state = _make_state()
        state.tracking.active_calamities = {
            "mega_predators": {"kills_needed": 5, "kills_done": 0},
        }
        events = resolve_calamity_progress(state, "mega_predators", 5)
        assert any("eliminated" in e.description for e in events)
        assert "mega_predators" not in state.tracking.active_calamities

    def test_resolve_unknown_calamity(self):
        from planetfall.engine.campaign.calamities import resolve_calamity_progress
        state = _make_state()
        events = resolve_calamity_progress(state, "nonexistent", 1)
        assert events == []

    def test_process_active_calamities_empty(self):
        from planetfall.engine.campaign.calamities import process_active_calamities
        state = _make_state()
        events = process_active_calamities(state)
        assert events == []


# --- Slyn tests ---

class TestSlyn:
    def test_slyn_inactive_no_interference(self):
        from planetfall.engine.campaign.slyn import check_slyn_interference
        state = _make_state()
        state.enemies.slyn.active = False
        events = check_slyn_interference(state)
        assert events == []

    def test_activate_slyn(self):
        from planetfall.engine.campaign.slyn import activate_slyn
        state = _make_state()
        state.enemies.slyn.active = False
        events = activate_slyn(state)
        assert len(events) == 1
        assert "SLYN EMERGE" in events[0].description
        assert state.enemies.slyn.active is True

    def test_activate_slyn_already_active(self):
        from planetfall.engine.campaign.slyn import activate_slyn
        state = _make_state()
        state.enemies.slyn.active = True
        events = activate_slyn(state)
        assert events == []

    def test_record_slyn_kills(self):
        from planetfall.engine.campaign.slyn import record_slyn_kills
        state = _make_state()
        events = record_slyn_kills(state, 2)
        assert state.tracking.slyn_victories == 2
        assert any("Slyn casualties: 2" in e.description for e in events)

    def test_slyn_departure_check(self):
        from planetfall.engine.campaign.slyn import record_slyn_kills
        state = _make_state()
        state.enemies.slyn.active = True
        # Give enough kills that departure is likely
        state.tracking.slyn_victories = 10
        events = record_slyn_kills(state, 2)
        # Should have departure check
        assert any("departure" in e.description.lower() or "withdraw" in e.description.lower()
                    for e in events)


# --- Equipment tests ---

class TestEquipment:
    def test_armory_catalog(self):
        from planetfall.engine.campaign.equipment import ARMORY
        assert len(ARMORY) >= 20

    def test_get_armory_catalog(self):
        from planetfall.engine.campaign.equipment import get_armory_catalog
        state = _make_state()
        state.colony.resources.build_points = 5
        items = get_armory_catalog(state)
        assert len(items) > 0
        assert all("affordable" in item for item in items)

    def test_purchase_equipment(self):
        from planetfall.engine.campaign.equipment import purchase_equipment
        state = _make_state()
        state.colony.resources.build_points = 10
        char_name = state.characters[0].name
        events = purchase_equipment(state, "colony_rifle", char_name)
        assert "equipped" in events[0].description.lower() or "Colony Rifle" in events[0].description
        assert "Colony Rifle" in state.characters[0].equipment

    def test_purchase_unknown_item(self):
        from planetfall.engine.campaign.equipment import purchase_equipment
        state = _make_state()
        events = purchase_equipment(state, "nonexistent", "Nobody")
        assert "Unknown" in events[0].description

    def test_purchase_insufficient_bp(self):
        from planetfall.engine.campaign.equipment import purchase_equipment
        state = _make_state()
        state.colony.resources.build_points = 0
        char_name = state.characters[0].name
        events = purchase_equipment(state, "battle_armor", char_name)
        assert "Not enough BP" in events[0].description

    def test_swap_equipment(self):
        from planetfall.engine.campaign.equipment import swap_equipment
        state = _make_state()
        state.characters[0].equipment.append("Colony Rifle")
        from_name = state.characters[0].name
        to_name = state.characters[1].name
        events = swap_equipment(state, from_name, to_name, "Colony Rifle")
        assert "Colony Rifle" not in state.characters[0].equipment
        assert "Colony Rifle" in state.characters[1].equipment

    def test_sell_equipment(self):
        from planetfall.engine.campaign.equipment import sell_equipment
        state = _make_state()
        state.characters[0].equipment.append("Colony Rifle")
        char_name = state.characters[0].name
        old_rm = state.colony.resources.raw_materials
        events = sell_equipment(state, char_name, "Colony Rifle")
        assert "sold" in events[0].description.lower()
        assert state.colony.resources.raw_materials > old_rm


# --- Extraction tests ---

class TestExtraction:
    def test_get_exploitable_sectors_empty(self):
        from planetfall.engine.campaign.extraction import get_exploitable_sectors
        state = _make_state()
        # By default no explored sectors with resources
        results = get_exploitable_sectors(state)
        # May or may not have results depending on setup
        assert isinstance(results, list)

    def test_start_extraction(self):
        from planetfall.engine.campaign.extraction import start_extraction
        state = _make_state()
        # Set up a sector as explored with resources
        sector = state.campaign_map.sectors[1]
        sector.status = SectorStatus.EXPLORED
        sector.resource_level = 4
        events = start_extraction(state, sector.sector_id)
        assert any("extraction begun" in e.description.lower() for e in events)

    def test_start_extraction_unexplored(self):
        from planetfall.engine.campaign.extraction import start_extraction
        state = _make_state()
        sector = state.campaign_map.sectors[1]
        sector.status = SectorStatus.UNKNOWN
        events = start_extraction(state, sector.sector_id)
        assert any("explored first" in e.description.lower() for e in events)

    def test_process_extractions(self):
        from planetfall.engine.campaign.extraction import start_extraction, process_extractions
        state = _make_state()
        sector = state.campaign_map.sectors[1]
        sector.status = SectorStatus.EXPLORED
        sector.resource_level = 4
        start_extraction(state, sector.sector_id)
        old_rm = state.colony.resources.raw_materials
        events = process_extractions(state)
        assert len(events) >= 1
        assert state.colony.resources.raw_materials > old_rm

    def test_stop_extraction(self):
        from planetfall.engine.campaign.extraction import (
            start_extraction, stop_extraction,
        )
        state = _make_state()
        sector = state.campaign_map.sectors[1]
        sector.status = SectorStatus.EXPLORED
        sector.resource_level = 4
        start_extraction(state, sector.sector_id)
        events = stop_extraction(state, sector.sector_id)
        assert any("stopped" in e.description.lower() for e in events)


# --- Ancient Signs tests ---

class TestAncientSigns:
    def test_no_signs_no_events(self):
        from planetfall.engine.campaign.ancient_signs import check_ancient_signs
        state = _make_state()
        state.campaign.ancient_signs_count = 0
        events = check_ancient_signs(state)
        assert events == []

    def test_three_signs_trigger_site(self):
        from planetfall.engine.campaign.ancient_signs import check_ancient_signs
        state = _make_state()
        state.campaign.ancient_signs_count = 3
        events = check_ancient_signs(state)
        assert len(events) >= 1
        assert any("ancient site" in e.description.lower() for e in events)

    def test_explore_ancient_site(self):
        from planetfall.engine.campaign.ancient_signs import explore_ancient_site
        state = _make_state()
        # Place an ancient site
        sector = state.campaign_map.sectors[1]
        sector.has_ancient_site = True
        old_md = state.campaign.mission_data_count
        events = explore_ancient_site(state, sector.sector_id)
        assert state.campaign.mission_data_count == old_md + 1
        assert sector.has_ancient_site is False

    def test_explore_no_site(self):
        from planetfall.engine.campaign.ancient_signs import explore_ancient_site
        state = _make_state()
        sector = state.campaign_map.sectors[1]
        sector.has_ancient_site = False
        events = explore_ancient_site(state, sector.sector_id)
        assert any("no ancient site" in e.description.lower() for e in events)

    def test_breakthrough_table(self):
        from planetfall.engine.campaign.ancient_signs import BREAKTHROUGH_TABLE
        assert len(BREAKTHROUGH_TABLE) == 4


# --- Post-Mission Finds tests ---

class TestPostMissionFinds:
    def test_finds_table_coverage(self):
        from planetfall.engine.tables.post_mission_finds import POST_MISSION_FINDS
        assert len(POST_MISSION_FINDS) == 7

    def test_alien_artifacts_table(self):
        from planetfall.engine.tables.post_mission_finds import ALIEN_ARTIFACTS
        assert len(ALIEN_ARTIFACTS) == 29

    def test_roll_post_mission_finds(self):
        from planetfall.engine.tables.post_mission_finds import roll_post_mission_finds
        state = _make_state()
        events = roll_post_mission_finds(state)
        assert len(events) == 1
        assert "Post-Mission Find" in events[0].description

    def test_roll_with_scientist_bonus(self):
        from planetfall.engine.tables.post_mission_finds import roll_post_mission_finds
        state = _make_state()
        # Just test it doesn't crash
        events = roll_post_mission_finds(state, scientist_alive=True)
        assert len(events) >= 1

    def test_roll_multiple(self):
        from planetfall.engine.tables.post_mission_finds import roll_post_mission_finds
        state = _make_state()
        events = roll_post_mission_finds(state, num_rolls=3)
        assert len(events) == 3

    def test_alien_artifact_roll(self):
        from planetfall.engine.tables.post_mission_finds import roll_alien_artifact
        state = _make_state()
        event = roll_alien_artifact(state)
        assert "Alien Artifact" in event.description


# --- Battlefield Conditions tests ---

class TestBattlefieldConditions:
    def test_conditions_table_coverage(self):
        from planetfall.engine.tables.battlefield_conditions import BATTLEFIELD_CONDITIONS_TABLE
        assert len(BATTLEFIELD_CONDITIONS_TABLE) == 16

    def test_roll_condition(self):
        from planetfall.engine.tables.battlefield_conditions import roll_battlefield_condition
        cond = roll_battlefield_condition()
        assert cond.id != ""
        assert cond.name != ""

    def test_get_mission_condition(self):
        from planetfall.engine.tables.battlefield_conditions import get_mission_condition
        state = _make_state()
        cond = get_mission_condition(state, 1)
        assert cond.id != ""
        # Second call should return same condition
        cond2 = get_mission_condition(state, 1)
        assert cond2.id == cond.id

    def test_different_turns_different_slots(self):
        from planetfall.engine.tables.battlefield_conditions import get_mission_condition
        state = _make_state()
        cond1 = get_mission_condition(state, 1)
        cond2 = get_mission_condition(state, 2)
        # Different slots but could randomly be same condition
        conditions = state.tracking.battlefield_conditions
        assert len(conditions) >= 2


# --- Tool Handlers integration tests ---

class TestToolHandlers:
    def test_augmentation_handler(self):
        from planetfall.tools.handlers import handle_tool_call
        import json
        state = _make_state()
        state.colony.resources.augmentation_points = 5
        result = json.loads(handle_tool_call(
            state, "get_augmentation_options", {}
        ))
        assert "augmentations" in result
        assert len(result["augmentations"]) == 8
        assert result["next_cost"] == 1
        assert result["ap_available"] == 5

    def test_equipment_handler(self):
        from planetfall.tools.handlers import handle_tool_call
        import json
        state = _make_state()
        result = json.loads(handle_tool_call(state, "get_armory", {}))
        assert "items" in result

    def test_calamity_handler(self):
        from planetfall.tools.handlers import handle_tool_call
        import json
        state = _make_state()
        state.colony.resources.calamity_points = 0
        result = json.loads(handle_tool_call(state, "check_calamity", {}))
        assert "events" in result
        assert result["events"] == []

    def test_slyn_handler(self):
        from planetfall.tools.handlers import handle_tool_call
        import json
        state = _make_state()
        state.enemies.slyn.active = False
        result = json.loads(handle_tool_call(
            state, "check_slyn_interference", {}
        ))
        assert "events" in result
        assert result["events"] == []

    def test_extraction_handler(self):
        from planetfall.tools.handlers import handle_tool_call
        import json
        state = _make_state()
        result = json.loads(handle_tool_call(
            state, "get_exploitable_sectors", {}
        ))
        assert "sectors" in result

    def test_ancient_signs_handler(self):
        from planetfall.tools.handlers import handle_tool_call
        import json
        state = _make_state()
        state.campaign.ancient_signs_count = 0
        result = json.loads(handle_tool_call(
            state, "check_ancient_signs", {}
        ))
        assert "events" in result

    def test_post_mission_finds_handler(self):
        from planetfall.tools.handlers import handle_tool_call
        import json
        state = _make_state()
        result = json.loads(handle_tool_call(
            state, "roll_post_mission_finds", {}
        ))
        assert "events" in result
        assert len(result["events"]) == 1

    def test_battlefield_condition_handler(self):
        from planetfall.tools.handlers import handle_tool_call
        import json
        state = _make_state()
        result = json.loads(handle_tool_call(
            state, "get_battlefield_condition", {}
        ))
        assert "condition" in result
        assert "name" in result["condition"]

    def test_unknown_tool(self):
        from planetfall.tools.handlers import handle_tool_call
        import json
        state = _make_state()
        result = json.loads(handle_tool_call(state, "nonexistent_tool", {}))
        assert "error" in result

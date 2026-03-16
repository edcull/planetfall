"""Tests for new game systems: augmentation, calamities, Slyn, equipment,
extraction, ancient signs, post-mission finds, battlefield conditions."""

import pytest
from planetfall.engine.models import SectorStatus


# --- Augmentation tests ---

class TestAugmentation:
    def test_augmentations_catalog(self):
        from planetfall.engine.campaign.augmentation import AUGMENTATIONS
        assert len(AUGMENTATIONS) == 8

    def test_get_available_augmentations(self, game_state_scientific):
        from planetfall.engine.campaign.augmentation import get_available_augmentations
        state = game_state_scientific
        state.colony.resources.augmentation_points = 5
        available = get_available_augmentations(state)
        assert len(available) == 8
        assert all(a["affordable"] for a in available)
        assert all(a["cost"] == 1 for a in available)

    def test_apply_augmentation(self, game_state_scientific):
        from planetfall.engine.campaign.augmentation import apply_augmentation
        state = game_state_scientific
        state.colony.resources.augmentation_points = 3
        events = apply_augmentation(state, "enhanced_mobility")
        assert len(events) >= 1
        assert "Enhanced Mobility" in events[0].description
        assert state.colony.resources.augmentation_points == 2
        # Colony-wide: all characters should get speed boost
        for char in state.characters:
            if char.sub_species.value != "soulless" and char.char_class.value != "bot":
                assert char.speed >= 5  # base speed + 1

    def test_progressive_cost(self, game_state_scientific):
        from planetfall.engine.campaign.augmentation import (
            apply_augmentation, get_augmentation_cost,
        )
        state = game_state_scientific
        state.colony.resources.augmentation_points = 10
        assert get_augmentation_cost(state) == 1
        apply_augmentation(state, "enhanced_mobility")
        state.flags.augmentation_bought_this_turn = False
        assert get_augmentation_cost(state) == 2
        apply_augmentation(state, "claws")
        state.flags.augmentation_bought_this_turn = False
        assert get_augmentation_cost(state) == 3

    def test_duplicate_augmentation_rejected(self, game_state_scientific):
        from planetfall.engine.campaign.augmentation import apply_augmentation
        state = game_state_scientific
        state.colony.resources.augmentation_points = 10
        apply_augmentation(state, "claws")
        state.flags.augmentation_bought_this_turn = False
        events = apply_augmentation(state, "claws")
        assert "already has" in events[0].description

    def test_insufficient_ap(self, game_state_scientific):
        from planetfall.engine.campaign.augmentation import apply_augmentation
        state = game_state_scientific
        state.colony.resources.augmentation_points = 0
        events = apply_augmentation(state, "claws")
        assert "Not enough AP" in events[0].description


# --- Calamity tests ---

class TestCalamities:
    def test_calamity_table_coverage(self):
        from planetfall.engine.campaign.calamities import CALAMITY_TABLE
        assert len(CALAMITY_TABLE) == 8

    def test_no_calamity_when_zero_cp(self, game_state_scientific):
        from planetfall.engine.campaign.calamities import check_calamity
        state = game_state_scientific
        state.colony.resources.calamity_points = 0
        events = check_calamity(state)
        assert events == []

    def test_calamity_check_with_cp(self, game_state_scientific):
        from planetfall.engine.campaign.calamities import check_calamity
        state = game_state_scientific
        state.colony.resources.calamity_points = 6  # High CP, always triggers
        events = check_calamity(state)
        # Should always get at least a check result
        assert len(events) >= 1

    def test_resolve_mega_predators(self, game_state_scientific):
        from planetfall.engine.campaign.calamities import resolve_calamity_progress
        state = game_state_scientific
        state.tracking.active_calamities = {
            "mega_predators": {"kills_needed": 5, "kills_done": 0},
        }
        events = resolve_calamity_progress(state, "mega_predators", 5)
        assert any("eliminated" in e.description for e in events)
        assert "mega_predators" not in state.tracking.active_calamities

    def test_resolve_unknown_calamity(self, game_state_scientific):
        from planetfall.engine.campaign.calamities import resolve_calamity_progress
        state = game_state_scientific
        events = resolve_calamity_progress(state, "nonexistent", 1)
        assert events == []

    def test_process_active_calamities_empty(self, game_state_scientific):
        from planetfall.engine.campaign.calamities import process_active_calamities
        state = game_state_scientific
        events = process_active_calamities(state)
        assert events == []


# --- Slyn tests ---

class TestSlyn:
    def test_slyn_driven_off_no_interference(self, game_state_scientific):
        from planetfall.engine.campaign.slyn import check_slyn_interference
        state = game_state_scientific
        state.enemies.slyn.active = False  # Driven off
        events = check_slyn_interference(state)
        assert events == []

    def test_record_slyn_kills_before_milestone4(self, game_state_scientific):
        """Victories before milestone 4 are not counted."""
        from planetfall.engine.campaign.slyn import record_slyn_kills
        state = game_state_scientific
        state.tracking.slyn_victory_tracking_active = False
        events = record_slyn_kills(state, 2)
        assert state.tracking.slyn_victories == 0  # Not tracked yet
        assert any("not yet tracked" in e.description.lower() for e in events)

    def test_record_slyn_kills_after_milestone4(self, game_state_scientific):
        """After milestone 4, victories are tracked and trigger departure check."""
        from planetfall.engine.campaign.slyn import record_slyn_kills
        state = game_state_scientific
        state.tracking.slyn_victory_tracking_active = True
        events = record_slyn_kills(state, 2)
        assert state.tracking.slyn_victories == 2
        assert any("Tracked victories: 2" in e.description for e in events)
        # Should always have a departure check after milestone 4
        assert any("departure" in e.description.lower() or "withdraw" in e.description.lower()
                    for e in events)

    def test_slyn_departure_check(self, game_state_scientific):
        from planetfall.engine.campaign.slyn import record_slyn_kills
        state = game_state_scientific
        state.enemies.slyn.active = True
        state.tracking.slyn_victory_tracking_active = True
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

    def test_get_armory_catalog(self, game_state_scientific):
        from planetfall.engine.campaign.equipment import get_armory_catalog
        state = game_state_scientific
        state.colony.resources.build_points = 5
        items = get_armory_catalog(state)
        assert len(items) > 0
        assert all("affordable" in item for item in items)

    def test_purchase_equipment(self, game_state_scientific):
        from planetfall.engine.campaign.equipment import purchase_equipment
        state = game_state_scientific
        state.colony.resources.build_points = 10
        char_name = state.characters[0].name
        events = purchase_equipment(state, "colony_rifle", char_name)
        assert "equipped" in events[0].description.lower() or "Colony Rifle" in events[0].description
        assert "Colony Rifle" in state.characters[0].equipment

    def test_purchase_unknown_item(self, game_state_scientific):
        from planetfall.engine.campaign.equipment import purchase_equipment
        state = game_state_scientific
        events = purchase_equipment(state, "nonexistent", "Nobody")
        assert "Unknown" in events[0].description

    def test_purchase_insufficient_bp(self, game_state_scientific):
        from planetfall.engine.campaign.equipment import purchase_equipment
        state = game_state_scientific
        state.colony.resources.build_points = 0
        char_name = state.characters[0].name
        events = purchase_equipment(state, "battle_armor", char_name)
        assert "Not enough BP" in events[0].description

    def test_swap_equipment(self, game_state_scientific):
        from planetfall.engine.campaign.equipment import swap_equipment
        state = game_state_scientific
        state.characters[0].equipment.append("Colony Rifle")
        from_name = state.characters[0].name
        to_name = state.characters[1].name
        events = swap_equipment(state, from_name, to_name, "Colony Rifle")
        assert "Colony Rifle" not in state.characters[0].equipment
        assert "Colony Rifle" in state.characters[1].equipment

    def test_sell_equipment(self, game_state_scientific):
        from planetfall.engine.campaign.equipment import sell_equipment
        state = game_state_scientific
        state.characters[0].equipment.append("Colony Rifle")
        char_name = state.characters[0].name
        old_rm = state.colony.resources.raw_materials
        events = sell_equipment(state, char_name, "Colony Rifle")
        assert "sold" in events[0].description.lower()
        assert state.colony.resources.raw_materials > old_rm


# --- Extraction tests ---

class TestExtraction:
    def test_get_exploitable_sectors_empty(self, game_state_scientific):
        from planetfall.engine.campaign.extraction import get_exploitable_sectors
        state = game_state_scientific
        # By default no explored sectors with resources
        results = get_exploitable_sectors(state)
        # May or may not have results depending on setup
        assert isinstance(results, list)

    def test_start_extraction(self, game_state_scientific):
        from planetfall.engine.campaign.extraction import start_extraction
        state = game_state_scientific
        # Set up a sector as explored with resources
        sector = state.campaign_map.sectors[1]
        sector.status = SectorStatus.EXPLORED
        sector.resource_level = 4
        events = start_extraction(state, sector.sector_id)
        assert any("extraction begun" in e.description.lower() for e in events)

    def test_start_extraction_unexplored(self, game_state_scientific):
        from planetfall.engine.campaign.extraction import start_extraction
        state = game_state_scientific
        sector = state.campaign_map.sectors[1]
        sector.status = SectorStatus.UNEXPLORED
        events = start_extraction(state, sector.sector_id)
        assert any("explored first" in e.description.lower() for e in events)

    def test_process_extractions(self, game_state_scientific):
        from planetfall.engine.campaign.extraction import start_extraction, process_extractions
        state = game_state_scientific
        sector = state.campaign_map.sectors[1]
        sector.status = SectorStatus.EXPLORED
        sector.resource_level = 4
        start_extraction(state, sector.sector_id)
        old_rm = state.colony.resources.raw_materials
        events = process_extractions(state)
        assert len(events) >= 1
        assert state.colony.resources.raw_materials > old_rm

    def test_stop_extraction(self, game_state_scientific):
        from planetfall.engine.campaign.extraction import (
            start_extraction, stop_extraction,
        )
        state = game_state_scientific
        sector = state.campaign_map.sectors[1]
        sector.status = SectorStatus.EXPLORED
        sector.resource_level = 4
        start_extraction(state, sector.sector_id)
        events = stop_extraction(state, sector.sector_id)
        assert any("stopped" in e.description.lower() for e in events)


# --- Ancient Signs tests ---

class TestAncientSigns:
    def test_no_signs_no_events(self, game_state_scientific):
        from planetfall.engine.campaign.ancient_signs import check_ancient_signs
        state = game_state_scientific
        state.campaign.ancient_signs_count = 0
        events = check_ancient_signs(state)
        assert events == []

    def test_sign_check_rolls_d6(self, game_state_scientific, monkeypatch):
        from planetfall.engine.campaign.ancient_signs import check_ancient_signs
        from planetfall.engine import dice as dice_mod
        state = game_state_scientific
        state.campaign.ancient_signs_count = 3
        # Force roll of 1 (always succeeds vs 3 signs)
        monkeypatch.setattr(dice_mod, "_do_roll", lambda n, s, label="": [1])
        events = check_ancient_signs(state)
        assert len(events) >= 1
        assert any("ancient site" in e.description.lower() for e in events)
        assert state.campaign.ancient_signs_count == 0  # Signs discarded on success

    def test_sign_check_fails_on_high_roll(self, game_state_scientific, monkeypatch):
        from planetfall.engine.campaign.ancient_signs import check_ancient_signs
        from planetfall.engine import dice as dice_mod
        state = game_state_scientific
        state.campaign.ancient_signs_count = 1
        # Force roll of 6 (fails vs 1 sign)
        monkeypatch.setattr(dice_mod, "_do_roll", lambda n, s, label="": [6])
        events = check_ancient_signs(state)
        assert len(events) >= 1
        assert any("not enough" in e.description.lower() for e in events)
        assert state.campaign.ancient_signs_count == 1  # Signs kept

    def test_explore_ancient_site(self, game_state_scientific, monkeypatch):
        from planetfall.engine.campaign.ancient_signs import explore_ancient_site
        from planetfall.engine import dice as dice_mod
        state = game_state_scientific
        # Prevent breakthrough roll from consuming mission data
        state.tracking.breakthroughs_count = 4
        # Place an ancient site
        sector = state.campaign_map.sectors[1]
        sector.has_ancient_site = True
        old_md = state.campaign.mission_data_count
        events = explore_ancient_site(state, sector.sector_id)
        assert state.campaign.mission_data_count == old_md + 1
        assert sector.has_ancient_site is False

    def test_explore_no_site(self, game_state_scientific):
        from planetfall.engine.campaign.ancient_signs import explore_ancient_site
        state = game_state_scientific
        sector = state.campaign_map.sectors[1]
        sector.has_ancient_site = False
        events = explore_ancient_site(state, sector.sector_id)
        assert any("no ancient site" in e.description.lower() for e in events)

    def test_breakthrough_table(self):
        from planetfall.engine.campaign.ancient_signs import FOURTH_BREAKTHROUGH_TABLE
        # 4th breakthrough D100 table has 10 entries (10 ranges covering 1-100)
        assert len(FOURTH_BREAKTHROUGH_TABLE) == 10


# --- Post-Mission Finds tests ---

class TestPostMissionFinds:
    def test_finds_table_coverage(self):
        from planetfall.engine.tables.post_mission_finds import POST_MISSION_FINDS
        assert len(POST_MISSION_FINDS) == 7

    def test_alien_artifacts_table(self):
        from planetfall.engine.tables.post_mission_finds import ALIEN_ARTIFACTS
        assert len(ALIEN_ARTIFACTS) == 29

    def test_roll_post_mission_finds(self, game_state_scientific):
        from planetfall.engine.tables.post_mission_finds import roll_post_mission_finds
        state = game_state_scientific
        events = roll_post_mission_finds(state)
        assert len(events) >= 1  # May include ancient sign check event
        assert "Post-Mission Find" in events[0].description

    def test_roll_with_scientist_bonus(self, game_state_scientific):
        from planetfall.engine.tables.post_mission_finds import roll_post_mission_finds
        state = game_state_scientific
        # Just test it doesn't crash
        events = roll_post_mission_finds(state, scientist_alive=True)
        assert len(events) >= 1

    def test_roll_multiple(self, game_state_scientific):
        from planetfall.engine.tables.post_mission_finds import roll_post_mission_finds
        state = game_state_scientific
        events = roll_post_mission_finds(state, num_rolls=3)
        # At least 3 find events, possibly more from ancient sign checks
        find_events = [e for e in events if "Post-Mission Find" in e.description]
        assert len(find_events) == 3

    def test_alien_artifact_roll(self, game_state_scientific):
        from planetfall.engine.tables.post_mission_finds import roll_alien_artifact
        state = game_state_scientific
        event = roll_alien_artifact(state)
        assert "Alien Artifact" in event.description


# --- Battlefield Conditions tests ---

class TestBattlefieldConditions:
    def test_conditions_table_coverage(self):
        from planetfall.engine.tables.battlefield_conditions import BATTLEFIELD_CONDITIONS_TABLE
        assert len(BATTLEFIELD_CONDITIONS_TABLE) == 15  # 15 entries in Master Condition table

    def test_roll_condition(self):
        from planetfall.engine.tables.battlefield_conditions import roll_battlefield_condition
        cond = roll_battlefield_condition()
        assert cond.id != ""
        assert cond.name != ""

    def test_get_mission_condition(self, game_state_scientific):
        from planetfall.engine.tables.battlefield_conditions import get_mission_condition
        state = game_state_scientific
        cond = get_mission_condition(state)
        assert cond.id != ""
        assert cond.name != ""
        # The condition should be stored in the conditions list
        assert any(c is not None for c in state.tracking.battlefield_conditions)

    def test_slot_persistence(self, game_state_scientific):
        """Once a slot is filled, subsequent rolls hitting that slot return the same condition."""
        from planetfall.engine.tables.battlefield_conditions import get_mission_condition
        from unittest.mock import patch
        state = game_state_scientific
        # Force roll to hit slot 0
        with patch("planetfall.engine.tables.battlefield_conditions.roll_d100") as mock_d100:
            mock_d100.return_value = type("R", (), {"total": 1, "values": [1]})()
            cond1 = get_mission_condition(state)
            cond2 = get_mission_condition(state)
        assert cond1.id == cond2.id

    def test_multiple_slots_filled(self, game_state_scientific):
        from planetfall.engine.tables.battlefield_conditions import get_mission_condition
        state = game_state_scientific
        for _ in range(10):
            get_mission_condition(state)
        conditions = state.tracking.battlefield_conditions
        filled = [c for c in conditions if c is not None]
        assert len(filled) >= 1


# --- Tool Handlers integration tests ---

class TestToolHandlers:
    def test_augmentation_handler(self, game_state_scientific):
        from planetfall.tools.handlers import handle_tool_call
        import json
        state = game_state_scientific
        state.colony.resources.augmentation_points = 5
        result = json.loads(handle_tool_call(
            state, "get_augmentation_options", {}
        ))
        assert "augmentations" in result
        assert len(result["augmentations"]) == 8
        assert result["next_cost"] == 1
        assert result["ap_available"] == 5

    def test_equipment_handler(self, game_state_scientific):
        from planetfall.tools.handlers import handle_tool_call
        import json
        state = game_state_scientific
        result = json.loads(handle_tool_call(state, "get_armory", {}))
        assert "items" in result

    def test_calamity_handler(self, game_state_scientific):
        from planetfall.tools.handlers import handle_tool_call
        import json
        state = game_state_scientific
        state.colony.resources.calamity_points = 0
        result = json.loads(handle_tool_call(state, "check_calamity", {}))
        assert "events" in result
        assert result["events"] == []

    def test_slyn_handler(self, game_state_scientific):
        from planetfall.tools.handlers import handle_tool_call
        import json
        state = game_state_scientific
        state.enemies.slyn.active = False
        result = json.loads(handle_tool_call(
            state, "check_slyn_interference", {}
        ))
        assert "events" in result
        assert result["events"] == []

    def test_extraction_handler(self, game_state_scientific):
        from planetfall.tools.handlers import handle_tool_call
        import json
        state = game_state_scientific
        result = json.loads(handle_tool_call(
            state, "get_exploitable_sectors", {}
        ))
        assert "sectors" in result

    def test_ancient_signs_handler(self, game_state_scientific):
        from planetfall.tools.handlers import handle_tool_call
        import json
        state = game_state_scientific
        state.campaign.ancient_signs_count = 0
        result = json.loads(handle_tool_call(
            state, "check_ancient_signs", {}
        ))
        assert "events" in result

    def test_post_mission_finds_handler(self, game_state_scientific):
        from planetfall.tools.handlers import handle_tool_call
        import json
        state = game_state_scientific
        result = json.loads(handle_tool_call(
            state, "roll_post_mission_finds", {}
        ))
        assert "events" in result
        assert len(result["events"]) == 1

    def test_battlefield_condition_handler(self, game_state_scientific):
        from planetfall.tools.handlers import handle_tool_call
        import json
        state = game_state_scientific
        result = json.loads(handle_tool_call(
            state, "get_battlefield_condition", {}
        ))
        assert "condition" in result
        assert "name" in result["condition"]

    def test_unknown_tool(self, game_state_scientific):
        from planetfall.tools.handlers import handle_tool_call
        import json
        state = game_state_scientific
        result = json.loads(handle_tool_call(state, "nonexistent_tool", {}))
        assert "error" in result

"""Tests for game state models and persistence."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from planetfall.engine.models import (
    Character,
    CharacterClass,
    Colony,
    GameState,
    Loyalty,
    SubSpecies,
    STARTING_PROFILES,
    get_weapon_by_name,
)
from planetfall.engine.persistence import (
    save_state,
    load_state,
    list_campaigns,
    list_snapshots,
    SAVES_DIR,
)


class TestCharacterModel:
    def test_create_scientist(self):
        profile = STARTING_PROFILES[CharacterClass.SCIENTIST]
        char = Character(name="Dr. Patel", char_class=CharacterClass.SCIENTIST, **profile)
        assert char.reactions == 1
        assert char.speed == 4
        assert char.combat_skill == 0
        assert char.toughness == 3
        assert char.savvy == 1

    def test_create_trooper(self):
        profile = STARTING_PROFILES[CharacterClass.TROOPER]
        char = Character(name="Vasquez", char_class=CharacterClass.TROOPER, **profile)
        assert char.reactions == 2
        assert char.combat_skill == 1

    def test_is_available(self):
        char = Character(
            name="Test",
            char_class=CharacterClass.SCOUT,
            **STARTING_PROFILES[CharacterClass.SCOUT],
        )
        assert char.is_available
        char.sick_bay_turns = 3
        assert not char.is_available

    def test_stat_bounds(self):
        with pytest.raises(Exception):
            Character(
                name="Bad",
                char_class=CharacterClass.TROOPER,
                reactions=0,  # below min of 1
                speed=4,
                combat_skill=0,
                toughness=3,
                savvy=0,
            )


class TestGameState:
    def test_default_state(self):
        state = GameState()
        assert state.current_turn == 1
        assert state.colony.morale == 0
        assert state.colony.integrity == 0
        assert state.colony.resources.story_points == 5
        assert state.colony.per_turn_rates.build_points == 1
        assert state.colony.per_turn_rates.research_points == 1
        assert state.grunts.count == 12
        assert state.grunts.bot_operational is True

    def test_serialization_roundtrip(self):
        state = GameState(campaign_name="Test Colony")
        state.characters.append(
            Character(
                name="Theodora",
                char_class=CharacterClass.SCOUT,
                **STARTING_PROFILES[CharacterClass.SCOUT],
            )
        )
        state.colony.morale = 3
        state.colony.resources.research_points = 5

        json_str = state.model_dump_json()
        restored = GameState.model_validate_json(json_str)

        assert restored.campaign_name == "Test Colony"
        assert len(restored.characters) == 1
        assert restored.characters[0].name == "Theodora"
        assert restored.colony.morale == 3
        assert restored.colony.resources.research_points == 5


class TestWeapons:
    def test_lookup_by_name(self):
        weapon = get_weapon_by_name("Trooper Rifle")
        assert weapon is not None
        assert weapon.range_inches == 30
        assert "ap_ammo" in weapon.traits

    def test_lookup_case_insensitive(self):
        weapon = get_weapon_by_name("handgun")
        assert weapon is not None
        assert weapon.name == "Handgun"

    def test_lookup_missing(self):
        assert get_weapon_by_name("Laser Sword") is None


class TestPersistence:
    def test_save_and_load(self, tmp_path, monkeypatch):
        monkeypatch.setattr("planetfall.engine.persistence.SAVES_DIR", tmp_path)

        state = GameState(campaign_name="TestSave")
        state.colony.morale = 5
        state.characters.append(
            Character(
                name="Tester",
                char_class=CharacterClass.TROOPER,
                **STARTING_PROFILES[CharacterClass.TROOPER],
            )
        )

        save_state(state)
        loaded = load_state("TestSave")

        assert loaded.campaign_name == "TestSave"
        assert loaded.colony.morale == 5
        assert len(loaded.characters) == 1
        assert loaded.characters[0].name == "Tester"

    def test_snapshot_created(self, tmp_path, monkeypatch):
        monkeypatch.setattr("planetfall.engine.persistence.SAVES_DIR", tmp_path)

        state = GameState(campaign_name="SnapTest")
        save_state(state)

        snapshots = list_snapshots("SnapTest")
        assert 1 in snapshots

    def test_list_campaigns(self, tmp_path, monkeypatch):
        monkeypatch.setattr("planetfall.engine.persistence.SAVES_DIR", tmp_path)

        state1 = GameState(campaign_name="Alpha")
        state2 = GameState(campaign_name="Beta")
        save_state(state1)
        save_state(state2)

        campaigns = list_campaigns()
        assert "Alpha" in campaigns
        assert "Beta" in campaigns

    def test_load_missing_campaign(self, tmp_path, monkeypatch):
        monkeypatch.setattr("planetfall.engine.persistence.SAVES_DIR", tmp_path)
        with pytest.raises(FileNotFoundError):
            load_state("NonExistent")

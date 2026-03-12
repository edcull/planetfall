"""Tests for all random tables - verify completeness and coverage."""

import pytest

from planetfall.engine.tables.scout_discovery import SCOUT_DISCOVERY_TABLE
from planetfall.engine.tables.colony_events import COLONY_EVENTS_TABLE
from planetfall.engine.tables.enemy_activity import ENEMY_ACTIVITY_TABLE
from planetfall.engine.tables.injuries import CHARACTER_INJURY_TABLE, GRUNT_INJURY_TABLE
from planetfall.engine.tables.advancement import ADVANCEMENT_TABLE
from planetfall.engine.tables.character_events import CHARACTER_EVENTS_TABLE


def _check_d100_coverage(table):
    """Verify a D100 table covers all values 1-100 with no gaps or overlaps."""
    covered = set()
    for entry in table.entries:
        for v in range(entry.low, entry.high + 1):
            assert v not in covered, (
                f"Table '{table.name}': value {v} appears in multiple entries "
                f"(at least '{entry.result_id}')"
            )
            covered.add(v)
    expected = set(range(1, 101))
    missing = expected - covered
    extra = covered - expected
    assert not missing, f"Table '{table.name}' missing values: {missing}"
    assert not extra, f"Table '{table.name}' has extra values: {extra}"


def _check_d6_coverage(table):
    """Verify a D6 table covers all values 1-6."""
    covered = set()
    for entry in table.entries:
        for v in range(entry.low, entry.high + 1):
            covered.add(v)
    expected = set(range(1, 7))
    assert covered == expected, (
        f"Table '{table.name}' coverage: {covered}, expected {expected}"
    )


class TestScoutDiscoveryTable:
    def test_full_coverage(self):
        _check_d100_coverage(SCOUT_DISCOVERY_TABLE)

    def test_key_entries(self):
        entry = SCOUT_DISCOVERY_TABLE.lookup(1)
        assert entry.result_id == "routine_trip"

        entry = SCOUT_DISCOVERY_TABLE.lookup(25)
        assert entry.result_id == "sos_signal"

        entry = SCOUT_DISCOVERY_TABLE.lookup(71)
        assert entry.result_id == "ancient_sign"

        entry = SCOUT_DISCOVERY_TABLE.lookup(100)
        assert entry.result_id == "revised_survey"


class TestColonyEventsTable:
    def test_full_coverage(self):
        _check_d100_coverage(COLONY_EVENTS_TABLE)

    def test_key_entries(self):
        entry = COLONY_EVENTS_TABLE.lookup(1)
        assert entry.result_id == "research_breakthrough"
        assert entry.effects["research_points"] == 2

        entry = COLONY_EVENTS_TABLE.lookup(100)
        assert entry.result_id == "foreboding"

        entry = COLONY_EVENTS_TABLE.lookup(50)
        assert entry.result_id == "hostile_wildlife"


class TestEnemyActivityTable:
    def test_full_coverage(self):
        _check_d100_coverage(ENEMY_ACTIVITY_TABLE)

    def test_key_entries(self):
        entry = ENEMY_ACTIVITY_TABLE.lookup(1)
        assert entry.result_id == "patrol"

        entry = ENEMY_ACTIVITY_TABLE.lookup(80)
        assert entry.result_id == "attack"
        assert entry.effects["forced_mission"] == "pitched_battle"

        entry = ENEMY_ACTIVITY_TABLE.lookup(95)
        assert entry.result_id == "raid"


class TestInjuryTables:
    def test_character_coverage(self):
        _check_d100_coverage(CHARACTER_INJURY_TABLE)

    def test_grunt_coverage(self):
        _check_d6_coverage(GRUNT_INJURY_TABLE)

    def test_character_key_entries(self):
        entry = CHARACTER_INJURY_TABLE.lookup(1)
        assert entry.result_id == "dead"

        entry = CHARACTER_INJURY_TABLE.lookup(100)
        assert entry.result_id == "hard_knocks"
        assert entry.effects["xp"] == 1

    def test_grunt_key_entries(self):
        entry = GRUNT_INJURY_TABLE.lookup(1)
        assert entry.result_id == "permanent_casualty"

        entry = GRUNT_INJURY_TABLE.lookup(6)
        assert entry.result_id == "okay"


class TestAdvancementTable:
    def test_full_coverage(self):
        _check_d100_coverage(ADVANCEMENT_TABLE)

    def test_key_entries(self):
        entry = ADVANCEMENT_TABLE.lookup(1)
        assert entry.result_id == "speed"
        assert entry.effects["max"] == 8

        entry = ADVANCEMENT_TABLE.lookup(50)
        assert entry.result_id == "combat_skill"

        entry = ADVANCEMENT_TABLE.lookup(100)
        assert entry.result_id == "kill_points"


class TestCharacterEventsTable:
    def test_full_coverage(self):
        _check_d100_coverage(CHARACTER_EVENTS_TABLE)

    def test_key_entries(self):
        entry = CHARACTER_EVENTS_TABLE.lookup(1)
        assert entry.result_id == "adapting"

        entry = CHARACTER_EVENTS_TABLE.lookup(40)
        assert entry.result_id == "argument"
        assert entry.effects["involves_other"] == 1

        entry = CHARACTER_EVENTS_TABLE.lookup(100)
        assert entry.result_id == "meal_together"

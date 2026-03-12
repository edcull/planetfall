"""Tests for Step 2: Repairs — Restore colony damage."""

from planetfall.engine.campaign.setup import create_new_campaign
from planetfall.engine.models import ColonizationAgenda
from planetfall.engine.steps.step02_repairs import execute


def _make_state():
    return create_new_campaign("T", "C", agenda=ColonizationAgenda.UNITY)


class TestNoRepairsNeeded:
    def test_undamaged_colony(self):
        state = _make_state()
        events = execute(state)
        assert len(events) == 1
        assert "No repairs needed" in events[0].description


class TestRepairs:
    def test_basic_repair(self):
        state = _make_state()
        state.colony.integrity = -3
        events = execute(state)
        assert state.colony.integrity > -3
        assert any("Repaired" in e.description for e in events)

    def test_repair_with_raw_materials(self):
        state = _make_state()
        state.colony.integrity = -5
        state.colony.resources.raw_materials = 3
        old_rm = state.colony.resources.raw_materials
        events = execute(state, raw_materials_spent=2)
        assert state.colony.resources.raw_materials == old_rm - 2

    def test_raw_materials_clamped_to_3(self):
        state = _make_state()
        state.colony.integrity = -10
        state.colony.resources.raw_materials = 10
        execute(state, raw_materials_spent=5)
        # Max 3 raw materials can be spent
        assert state.colony.resources.raw_materials == 7

    def test_raw_materials_clamped_to_available(self):
        state = _make_state()
        state.colony.integrity = -5
        state.colony.resources.raw_materials = 1
        execute(state, raw_materials_spent=3)
        assert state.colony.resources.raw_materials == 0

    def test_integrity_cannot_exceed_zero(self):
        state = _make_state()
        state.colony.integrity = -1
        state.colony.per_turn_rates.repair_capacity = 5
        execute(state)
        assert state.colony.integrity == 0

    def test_bot_repaired(self):
        state = _make_state()
        state.colony.integrity = -1
        state.grunts.bot_operational = False
        events = execute(state)
        assert state.grunts.bot_operational is True
        assert any("Bot repaired" in e.description for e in events)

"""Tests for the dice rolling module."""

import pytest
from unittest.mock import patch

from planetfall.engine.dice import (
    RollResult,
    RandomTable,
    TableEntry,
    roll_d6,
    roll_d100,
    roll_nd6,
    roll_2d6_pick_lowest,
    set_manual_mode,
    is_manual_mode,
)


class TestDigitalRolling:
    """Test digital (automatic) dice rolling."""

    def setup_method(self):
        set_manual_mode(False)

    def test_roll_d6_range(self):
        for _ in range(100):
            result = roll_d6("test")
            assert 1 <= result.total <= 6
            assert result.dice_type == "d6"
            assert len(result.values) == 1

    def test_roll_d100_range(self):
        for _ in range(100):
            result = roll_d100("test")
            assert 1 <= result.total <= 100
            assert result.dice_type == "d100"

    def test_roll_nd6(self):
        result = roll_nd6(3, "test")
        assert result.dice_type == "3d6"
        assert len(result.values) == 3
        assert result.total == sum(result.values)
        assert 3 <= result.total <= 18

    def test_roll_2d6_pick_lowest(self):
        for _ in range(50):
            result = roll_2d6_pick_lowest("test")
            assert result.dice_type == "2d6_low"
            assert len(result.values) == 2
            assert result.total == min(result.values)
            assert 1 <= result.total <= 6

    def test_roll_result_str(self):
        r = RollResult(dice_type="d6", values=[4], total=4, label="test")
        assert "[d6] 4" in str(r)

        r2 = RollResult(dice_type="2d6", values=[3, 5], total=8, label="test")
        assert "[2d6]" in str(r2)
        assert "8" in str(r2)


class TestManualMode:
    """Test manual dice mode toggling."""

    def test_toggle(self):
        set_manual_mode(False)
        assert not is_manual_mode()
        set_manual_mode(True)
        assert is_manual_mode()
        set_manual_mode(False)

    def test_manual_with_callback(self):
        values_returned = [3]
        set_manual_mode(True, lambda dtype, label: values_returned)
        result = roll_d6("test")
        assert result.total == 3
        set_manual_mode(False)


class TestRandomTable:
    """Test table lookup mechanics."""

    def setup_method(self):
        self.table = RandomTable(
            name="Test Table",
            dice_type="d6",
            entries=[
                TableEntry(low=1, high=2, result_id="low", description="Low roll"),
                TableEntry(low=3, high=4, result_id="mid", description="Mid roll"),
                TableEntry(low=5, high=6, result_id="high", description="High roll"),
            ],
        )

    def test_lookup_boundaries(self):
        assert self.table.lookup(1).result_id == "low"
        assert self.table.lookup(2).result_id == "low"
        assert self.table.lookup(3).result_id == "mid"
        assert self.table.lookup(4).result_id == "mid"
        assert self.table.lookup(5).result_id == "high"
        assert self.table.lookup(6).result_id == "high"

    def test_lookup_out_of_range(self):
        with pytest.raises(ValueError, match="out of range"):
            self.table.lookup(7)

    def test_roll_on_table(self):
        set_manual_mode(False)
        for _ in range(50):
            roll, entry = self.table.roll_on_table()
            assert entry.result_id in ("low", "mid", "high")
            assert entry.low <= roll.total <= entry.high

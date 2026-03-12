"""Dice rolling utilities for Planetfall.

Supports digital (automatic) and manual (player-input) modes.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class RollResult:
    """Result of a dice roll."""
    dice_type: str       # e.g. "d6", "d100", "2d6"
    values: list[int]    # individual die results
    total: int           # sum of values
    label: str = ""      # what this roll was for

    def __str__(self) -> str:
        if len(self.values) == 1:
            return f"[{self.dice_type}] {self.total}"
        return f"[{self.dice_type}] {self.values} = {self.total}"


# Type for manual input callback: (dice_type, label) -> list[int]
ManualInputFn = Callable[[str, str], list[int]]

# Global state for dice mode
_manual_mode: bool = False
_manual_input_fn: Optional[ManualInputFn] = None


def set_manual_mode(enabled: bool, input_fn: Optional[ManualInputFn] = None) -> None:
    """Toggle between digital and manual dice rolling."""
    global _manual_mode, _manual_input_fn
    _manual_mode = enabled
    _manual_input_fn = input_fn


def is_manual_mode() -> bool:
    return _manual_mode


def _roll_digital(num_dice: int, sides: int) -> list[int]:
    """Roll dice digitally using RNG."""
    return [random.randint(1, sides) for _ in range(num_dice)]


def _roll_manual(num_dice: int, sides: int, label: str) -> list[int]:
    """Get dice values from manual input."""
    if _manual_input_fn is not None:
        dice_type = f"{num_dice}d{sides}" if num_dice > 1 else f"d{sides}"
        return _manual_input_fn(dice_type, label)
    # Fallback to stdin if no callback set
    dice_type = f"{num_dice}d{sides}" if num_dice > 1 else f"d{sides}"
    prompt = f"Roll {dice_type}"
    if label:
        prompt += f" ({label})"
    prompt += ": "
    while True:
        raw = input(prompt).strip()
        try:
            values = [int(x.strip()) for x in raw.replace(",", " ").split()]
            if len(values) != num_dice:
                print(f"Expected {num_dice} value(s), got {len(values)}. Try again.")
                continue
            if all(1 <= v <= sides for v in values):
                return values
            print(f"Values must be between 1 and {sides}. Try again.")
        except ValueError:
            print("Enter numbers separated by spaces. Try again.")


def _do_roll(num_dice: int, sides: int, label: str = "") -> list[int]:
    """Roll dice using current mode."""
    if _manual_mode:
        return _roll_manual(num_dice, sides, label)
    return _roll_digital(num_dice, sides)


def roll_d6(label: str = "") -> RollResult:
    """Roll a single D6."""
    values = _do_roll(1, 6, label)
    return RollResult(dice_type="d6", values=values, total=values[0], label=label)


def roll_d100(label: str = "") -> RollResult:
    """Roll D100 (1-100)."""
    values = _do_roll(1, 100, label)
    return RollResult(dice_type="d100", values=values, total=values[0], label=label)


def roll_nd6(n: int, label: str = "") -> RollResult:
    """Roll N x D6."""
    values = _do_roll(n, 6, label)
    return RollResult(
        dice_type=f"{n}d6", values=values, total=sum(values), label=label
    )


def roll_2d6_pick_lowest(label: str = "") -> RollResult:
    """Roll 2D6 and take the lowest value (used for scout reports)."""
    values = _do_roll(2, 6, label)
    lowest = min(values)
    return RollResult(
        dice_type="2d6_low", values=values, total=lowest, label=label
    )


# --- Table lookup ---


@dataclass
class TableEntry:
    """A single entry in a D100 or D6 random table."""
    low: int
    high: int
    result_id: str
    description: str
    effects: dict | None = None


class RandomTable:
    """A random table that maps dice ranges to results."""

    def __init__(self, name: str, dice_type: str, entries: list[TableEntry]):
        self.name = name
        self.dice_type = dice_type
        self.entries = entries

    def lookup(self, roll: int) -> TableEntry:
        """Find the table entry matching a roll value."""
        for entry in self.entries:
            if entry.low <= roll <= entry.high:
                return entry
        raise ValueError(
            f"Roll {roll} out of range for table '{self.name}'"
        )

    def roll_on_table(self, label: str = "") -> tuple[RollResult, TableEntry]:
        """Roll on this table and return the result."""
        effective_label = label or f"Rolling on {self.name}"
        if self.dice_type == "d100":
            result = roll_d100(effective_label)
        elif self.dice_type == "d6":
            result = roll_d6(effective_label)
        elif self.dice_type == "2d6":
            result = roll_nd6(2, effective_label)
        elif self.dice_type == "3d6":
            result = roll_nd6(3, effective_label)
        else:
            raise ValueError(f"Unsupported dice type: {self.dice_type}")
        entry = self.lookup(result.total)
        return result, entry

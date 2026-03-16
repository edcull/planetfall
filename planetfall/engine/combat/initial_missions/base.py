"""Shared helpers for initial Planetfall missions."""

from __future__ import annotations

import random

from planetfall.engine.combat.battlefield import (
    Battlefield, Figure, FigureSide, FigureStatus, Zone, TerrainType,
    generate_random_terrain, GRID_SMALL, ZONE_INCHES,
)
from planetfall.engine.combat.missions import (
    MissionSetup, _create_player_figure,
)
from planetfall.engine.combat.session import CombatSession, CombatPhase
from planetfall.engine.dice import roll_d6
from planetfall.engine.models import (
    GameState, MissionType, Character, CharacterClass,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_chars_by_class(state: GameState, cls: CharacterClass) -> list[Character]:
    """Get all characters of a given class."""
    return [c for c in state.characters if c.char_class == cls]


def _random_edge(rows: int, cols: int) -> tuple[str, int]:
    """Pick a random edge and return (edge_name, edge_row).

    Returns the player deployment row index for the chosen edge.
    Row 0 = top (enemy edge default), last row = bottom (player edge default).
    We pick randomly and set player edge accordingly.
    """
    edge = random.choice(["top", "bottom", "left", "right"])
    # For simplicity, always use bottom row as player edge
    # (the grid is symmetrical enough for tutorial missions)
    return "bottom", rows - 1


def _zones_within_range(
    origin: tuple[int, int], max_zones: int, rows: int, cols: int,
) -> list[tuple[int, int]]:
    """All zones within max_zones Chebyshev distance of origin."""
    r0, c0 = origin
    result = []
    for r in range(rows):
        for c in range(cols):
            dist = max(abs(r - r0), abs(c - c0))
            if 0 < dist <= max_zones:
                result.append((r, c))
    return result


def _adjacent_zones(
    origin: tuple[int, int], rows: int, cols: int,
) -> list[tuple[int, int]]:
    """All 8-connected adjacent zones (within 1)."""
    return _zones_within_range(origin, 1, rows, cols)


def _chebyshev(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

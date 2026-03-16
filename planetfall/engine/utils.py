"""Shared utility functions for the Planetfall engine."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from planetfall.engine.models import GameState


def format_display(value: str) -> str:
    """Convert snake_case or enum values to Title Case display strings.

    Examples:
        'pitched_battle' -> 'Pitched Battle'
        'scout_down' -> 'Scout Down'
    """
    return value.replace("_", " ").title()


def sectors_within_distance(state: GameState, origin: int, max_dist: int) -> list[int]:
    """Return sector IDs within *max_dist* grid steps of *origin* (Chebyshev distance)."""
    sectors = state.campaign_map.sectors
    total = len(sectors)
    cols = 6
    rows = (total + cols - 1) // cols
    or_, oc = divmod(origin, cols)
    result = []
    for s in sectors:
        sr, sc = divmod(s.sector_id, cols)
        if max(abs(sr - or_), abs(sc - oc)) <= max_dist and s.sector_id != origin:
            result.append(s.sector_id)
    return result


def sync_enemy_sectors(state: GameState) -> None:
    """Sync tactical enemy sector assignments to the campaign map.

    Sets enemy_occupied_by on sectors where tactical enemies are present,
    and clears it from sectors where they no longer are.
    """
    # Build mapping: sector_id -> enemy name
    enemy_by_sector: dict[int, str] = {}
    for te in state.enemies.tactical_enemies:
        if not te.defeated:
            for sid in te.sectors:
                enemy_by_sector[sid] = te.name

    # Update all sectors
    for sector in state.campaign_map.sectors:
        sector.enemy_occupied_by = enemy_by_sector.get(sector.sector_id)

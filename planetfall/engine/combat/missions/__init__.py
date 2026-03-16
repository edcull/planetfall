"""Mission setup and victory conditions for Planetfall combat.

Each mission type defines:
- Enemy type (tactical or lifeform)
- Number and placement of enemies
- Deployment zones
- Victory conditions
- Special rules

This package re-exports all public names so that existing imports like
``from planetfall.engine.combat.missions import setup_mission`` continue to work.
"""

from planetfall.engine.combat.missions.base import (
    MAX_PER_ZONE,
    LifeformRollResult,
    MissionSetup,
    get_or_generate_lifeform,
    _assign_zone_with_overflow,
    _create_player_figure,
    _create_enemy_figure,
    _build_lifeform_info,
    _create_lifeform_figure,
    _deploy_player_figures,
    _deploy_tactical_enemies,
    _deploy_slyn,
    _create_sleeper_figure,
    _deploy_lifeforms,
)

from planetfall.engine.combat.missions.setup import setup_mission

__all__ = [
    "MAX_PER_ZONE",
    "LifeformRollResult",
    "MissionSetup",
    "get_or_generate_lifeform",
    "setup_mission",
    # Private helpers re-exported for tests and internal use
    "_assign_zone_with_overflow",
    "_create_player_figure",
    "_create_enemy_figure",
    "_build_lifeform_info",
    "_create_lifeform_figure",
    "_deploy_player_figures",
    "_deploy_tactical_enemies",
    "_deploy_slyn",
    "_create_sleeper_figure",
    "_deploy_lifeforms",
]

"""Orchestrator step functions — split into submodules by phase.

Re-exports all public step functions so callers can still do:
    from planetfall.orchestrator_steps import execute_step03_scout
"""

from planetfall.orchestrator_steps.pre_mission import (
    execute_step03_scout,
    execute_step04_enemy,
    execute_step05_colony_events,
)
from planetfall.orchestrator_steps.mission import (
    execute_step06_mission,
    execute_step07_deploy,
    execute_step08_mission,
)
from planetfall.orchestrator_steps.combat import (
    _get_move_zones,
    _get_dash_zones,
    _handle_player_turn,
    _run_interactive_combat,
    _run_manual_combat,
)
from planetfall.orchestrator_steps.post_mission import (
    execute_post_mission_finds,
    execute_step11_morale,
    execute_mid_turn_systems,
)
from planetfall.orchestrator_steps.colony import (
    prompt_research_spending,
    prompt_building_spending,
    execute_augmentation_opportunity,
    execute_step16_integrity,
)

__all__ = [
    "execute_step03_scout",
    "execute_step04_enemy",
    "execute_step05_colony_events",
    "execute_step06_mission",
    "execute_step07_deploy",
    "execute_step08_mission",
    "execute_post_mission_finds",
    "execute_step11_morale",
    "execute_mid_turn_systems",
    "prompt_research_spending",
    "prompt_building_spending",
    "execute_augmentation_opportunity",
    "execute_step16_integrity",
    "_get_move_zones",
    "_get_dash_zones",
    "_handle_player_turn",
    "_run_interactive_combat",
    "_run_manual_combat",
]

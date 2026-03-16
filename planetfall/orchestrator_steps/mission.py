"""Mission orchestrator steps (Steps 6-8)."""
from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from planetfall.engine.models import (
    GameState, MissionType, TurnEvent, TurnEventType,
)

if TYPE_CHECKING:
    from planetfall.ui.adapter import UIAdapter

RecordFn = Callable[[list[TurnEvent]], None]


def execute_step06_mission(
    ui: UIAdapter,
    state: GameState,
    _record: RecordFn,
) -> tuple[MissionType, int | None]:
    """Step 6: Mission Determination — choose mission and sector."""
    from planetfall.engine.steps import step06_mission_determination

    mission_options = step06_mission_determination.get_available_missions(state)
    ui.show_mission_options(mission_options)

    if len(mission_options) == 1 and mission_options[0].get("forced"):
        mission_idx = 0
        ui.message("  Forced mission — no choice available.", style="error")
    else:
        mission_idx = ui.prompt_mission_choice(mission_options)

    chosen = mission_options[mission_idx]
    mission_type = chosen["type"]

    sector_id = chosen.get("sector_id")
    target_sectors = chosen.get("target_sectors")
    if target_sectors and len(target_sectors) > 1 and sector_id is None:
        # Mission-specific prompt
        mission_verbs = {
            MissionType.INVESTIGATION: "Investigate which sector?",
            MissionType.SCOUTING: "Scout which sector?",
            MissionType.EXPLORATION: "Explore which sector?",
            MissionType.SCIENCE: "Research which sector?",
            MissionType.PATROL: "Patrol which sector?",
            MissionType.HUNT: "Hunt in which sector?",
        }
        prompt = mission_verbs.get(mission_type, "Which sector?")
        sector_id = ui.prompt_sector_coords(prompt, target_sectors)
    elif target_sectors and len(target_sectors) == 1:
        sector_id = target_sectors[0]

    events = step06_mission_determination.execute(state, mission_type, sector_id)
    _record(events)

    return mission_type, sector_id


def execute_step07_deploy(
    ui: UIAdapter,
    state: GameState,
    mission_type: MissionType,
    _record: RecordFn,
) -> tuple[list[str], int, bool, int, dict[str, str]]:
    """Step 7: Lock and Load — deploy characters, grunts, bot, civilians.

    Returns (deployed, grunts, bot, civilians, weapon_loadout).
    """
    from planetfall.engine.steps import step07_lock_and_load
    from planetfall.engine.steps.step07_lock_and_load import MISSION_FORCED_GRUNTS

    available = step07_lock_and_load.get_available_characters(state)
    max_slots = step07_lock_and_load.get_deployment_slots(mission_type.value)
    forced_grunts = MISSION_FORCED_GRUNTS.get(mission_type.value)
    available_names = [c.name for c in available]
    available_classes = {c.name: c.char_class.value for c in available}
    char_profiles = {
        c.name: {
            "char_class": c.char_class.value,
            "speed": c.speed,
            "reactions": c.reactions,
            "combat_skill": c.combat_skill,
            "toughness": c.toughness,
            "savvy": c.savvy,
            "equipment": list(c.equipment),
            "upgrades": list(c.upgrades),
        }
        for c in available
    }

    # Determine grunt availability — patrol forces a fireteam of 4
    grunt_count = state.grunts.count
    bot_available = state.grunts.bot_operational

    # Use combined Lock and Load modal if available (web UI),
    # otherwise fall back to two-step deployment + loadout (CLI)
    if hasattr(ui, "prompt_lock_and_load"):
        result = ui.prompt_lock_and_load(
            state,
            available_names,
            max_slots,
            grunt_count=grunt_count,
            bot_available=bot_available,
            char_profiles=char_profiles,
            forced_grunts=forced_grunts,
        )
        deployed_chars = result["characters"]
        grunt_deploy = result["grunts"]
        bot_deploy = result["bot"]
        civilian_deploy = result.get("civilians", 0)
        weapon_loadout = result.get("weapon_loadout", {})
    else:
        deployment = ui.prompt_deployment(
            available_names,
            max_slots,
            char_classes=available_classes,
            grunt_count=grunt_count,
            bot_available=bot_available,
            char_profiles=char_profiles,
        )

        deployed_chars = deployment["characters"]
        grunt_deploy = deployment["grunts"]
        bot_deploy = deployment["bot"]
        civilian_deploy = deployment.get("civilians", 0)

        # Weapon selection — Lock and Load
        ui.message("\n=== Lock and Load ===", style="heading")
        ui.message("Choose weapons for each character.\n", style="dim")
        weapon_loadout = ui.prompt_loadout(state, deployed_chars)

    # Override grunt count for missions with forced grunts
    if forced_grunts is not None:
        grunt_deploy = min(forced_grunts, grunt_count)

    events = step07_lock_and_load.execute(
        state, deployed_chars, grunt_deploy, mission_type.value, bot_deploy,
    )
    _record(events)

    if weapon_loadout:
        loadout_desc = ", ".join(f"{name}: {wpn}" for name, wpn in weapon_loadout.items())
        _record([TurnEvent(
            step=7,
            event_type=TurnEventType.MISSION,
            description=f"Weapon loadout: {loadout_desc}",
            state_changes={"weapon_loadout": weapon_loadout},
        )])

    return deployed_chars, grunt_deploy, bot_deploy, civilian_deploy, weapon_loadout


def execute_step08_mission(
    ui: UIAdapter,
    state: GameState,
    mission_type: MissionType,
    deployed_chars: list[str],
    grunt_deploy: int,
    _record: RecordFn,
    bot_deploy: bool = False,
    civilian_deploy: int = 0,
    weapon_loadout: dict[str, str] | None = None,
    condition: Any = None,
    slyn_briefing: dict | None = None,
    sector_id: int | None = None,
) -> tuple[bool, list[str], int]:
    """Step 8: Play Out Mission — interactive or manual. Returns (victory, casualties, grunt_casualties)."""
    from planetfall.orchestrator_steps.combat import _run_interactive_combat, _run_manual_combat

    combat_mode_choices = ["Interactive (AI combat)", "Manual (tabletop)"]
    combat_mode_choice = ui.select("Combat mode?", combat_mode_choices)
    use_interactive = combat_mode_choice.startswith("Interactive")

    if use_interactive and deployed_chars:
        return _run_interactive_combat(
            ui, state, mission_type, deployed_chars, grunt_deploy, _record,
            bot_deploy, civilian_deploy, weapon_loadout=weapon_loadout,
            condition=condition, slyn_briefing=slyn_briefing,
            sector_id=sector_id,
        )
    else:
        return _run_manual_combat(
            ui, state, mission_type, deployed_chars, grunt_deploy, _record,
        )

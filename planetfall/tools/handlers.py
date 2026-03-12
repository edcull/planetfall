"""Tool call dispatch — routes Claude tool_use calls to engine functions.

Each handler receives the game state and tool input dict, executes the
corresponding engine function, and returns a JSON-serializable result.

Uses a registry-based dispatch instead of a long if/elif chain.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from planetfall.engine.models import GameState, MissionType, TurnEvent
from planetfall.engine.combat.session import CombatSession, CombatPhase


class _CombatHolder:
    """Non-global holder for the active combat session."""
    session: CombatSession | None = None

_combat = _CombatHolder()


def get_active_combat() -> CombatSession | None:
    """Get the active combat session (if any)."""
    return _combat.session


def _events_to_dicts(events: list[TurnEvent]) -> list[dict]:
    """Convert TurnEvent list to serializable dicts."""
    return [
        {
            "step": e.step,
            "type": e.event_type.value,
            "description": e.description,
            "state_changes": e.state_changes or {},
        }
        for e in events
    ]


def _event_result(state: GameState, events: list[TurnEvent]) -> dict:
    """Record events to turn_log and return serializable dict."""
    state.turn_log.extend(events)
    return {"events": _events_to_dicts(events)}


def _state_summary(state: GameState) -> dict:
    """Build a concise state summary for the orchestrator."""
    return {
        "turn": state.current_turn,
        "colony": {
            "name": state.colony.name,
            "morale": state.colony.morale,
            "integrity": state.colony.integrity,
            "defenses": state.colony.defenses,
        },
        "resources": {
            "build_points": state.colony.resources.build_points,
            "research_points": state.colony.resources.research_points,
            "raw_materials": state.colony.resources.raw_materials,
            "story_points": state.colony.resources.story_points,
            "augmentation_points": state.colony.resources.augmentation_points,
            "calamity_points": state.colony.resources.calamity_points,
        },
        "characters": [
            {
                "name": c.name,
                "class": c.char_class.value,
                "available": c.is_available,
                "sick_bay_turns": c.sick_bay_turns,
                "xp": c.xp,
                "kill_points": c.kill_points,
            }
            for c in state.characters
        ],
        "grunts": state.grunts.count,
        "campaign": {
            "milestones_completed": state.campaign.milestones_completed,
            "mission_data_count": state.campaign.mission_data_count,
            "end_game_triggered": state.campaign.end_game_triggered,
        },
        "buildings": [b.name for b in state.colony.buildings],
        "unlocked_apps": state.tech_tree.unlocked_applications,
    }


# ---------------------------------------------------------------------------
# Handler functions — each returns a JSON-serializable dict
# ---------------------------------------------------------------------------

# --- Query handlers ---

def _handle_get_state_summary(state: GameState, tool_input: dict) -> dict:
    return _state_summary(state)


def _handle_get_research_options(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.steps import step14_research
    return step14_research.get_research_options(state)


def _handle_get_building_options(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.steps import step15_building
    return step15_building.get_building_options(state)


def _handle_get_scouting_options(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.models import CharacterClass, SectorStatus
    unexplored = [
        {
            "sector_id": s.sector_id,
            "has_investigation_site": s.has_investigation_site,
            "has_ancient_sign": s.has_ancient_sign,
        }
        for s in state.campaign_map.sectors
        if s.status == SectorStatus.UNKNOWN
        and s.sector_id != state.campaign_map.colony_sector_id
    ]
    available_scouts = [
        {"name": c.name, "xp": c.xp, "savvy": c.savvy}
        for c in state.characters
        if c.char_class == CharacterClass.SCOUT and c.is_available
    ]
    return {
        "unexplored_sectors": unexplored,
        "available_scouts": available_scouts,
        "total_sectors": len(state.campaign_map.sectors),
        "explored_count": sum(
            1 for s in state.campaign_map.sectors
            if s.status != SectorStatus.UNKNOWN
        ),
    }


def _handle_get_mission_options(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.steps import step06_mission_determination
    missions = step06_mission_determination.get_available_missions(state)
    return {"missions": missions}


def _handle_get_deployment_options(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.steps import step07_lock_and_load
    mission_type = tool_input.get("mission_type", "patrol")
    available = step07_lock_and_load.get_available_characters(state)
    max_slots = step07_lock_and_load.get_deployment_slots(mission_type)
    return {
        "available_characters": [
            {"name": c.name, "class": c.char_class.value}
            for c in available
        ],
        "max_deployment_slots": max_slots,
        "available_grunts": state.grunts.count,
    }


# --- Rules handlers ---

def _handle_load_rules_section(state: GameState, tool_input: dict) -> dict:
    from planetfall.rules.loader import load_section
    section = tool_input["section_name"]
    text = load_section(section)
    return {"section": section, "text": text}


def _handle_search_rules(state: GameState, tool_input: dict) -> dict:
    from planetfall.rules.loader import search_rules
    results = search_rules(
        tool_input["query"],
        tool_input.get("max_results", 5),
    )
    return {"results": [{"line": ln, "text": txt} for ln, txt in results]}


# --- Step handlers ---

def _handle_step01(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.steps import step01_recovery
    return _event_result(state, step01_recovery.execute(state))


def _handle_step02(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.steps import step02_repairs
    events = step02_repairs.execute(
        state, raw_materials_spent=tool_input.get("raw_materials_spent", 0)
    )
    return _event_result(state, events)


def _handle_step03_explore(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.steps import step03_scout_reports
    events = step03_scout_reports.execute_scout_explore(
        state, tool_input["sector_id"]
    )
    return _event_result(state, events)


def _handle_step03_discovery(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.steps import step03_scout_reports
    events = step03_scout_reports.execute_scout_discovery(
        state, tool_input.get("scout_name")
    )
    return _event_result(state, events)


def _handle_step04(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.steps import step04_enemy_activity
    return _event_result(state, step04_enemy_activity.execute(state))


def _handle_step05(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.steps import step05_colony_events
    return _event_result(state, step05_colony_events.execute(state))


def _handle_step06(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.steps import step06_mission_determination
    mt = MissionType(tool_input["mission_type"])
    events = step06_mission_determination.execute(
        state, mt, tool_input.get("sector_id")
    )
    return _event_result(state, events)


def _handle_step07(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.steps import step07_lock_and_load
    events = step07_lock_and_load.execute(
        state,
        tool_input["deployed_characters"],
        tool_input.get("deployed_grunts", 0),
        tool_input.get("mission_type", "patrol"),
        tool_input.get("deployed_bot", False),
    )
    return _event_result(state, events)


def _handle_step08(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.steps import step08_mission
    mt = MissionType(tool_input["mission_type"])
    deployed = tool_input.get("deployed_names")
    grunt_count = tool_input.get("grunt_count", 0)

    if tool_input.get("auto_battle") and deployed:
        result, events = step08_mission.execute(
            state, mt, deployed, grunt_count
        )
        state.turn_log.extend(events)
        return {
            "events": _events_to_dicts(events),
            "result": {
                "victory": result.victory,
                "rounds_played": result.rounds_played,
                "character_casualties": result.character_casualties,
                "grunt_casualties": result.grunt_casualties,
            },
        }
    else:
        result, events = step08_mission.execute(state, mt)
        state.turn_log.extend(events)
        return {
            "events": _events_to_dicts(events),
            "result": {
                "victory": result.victory,
                "manual_resolution_needed": True,
            },
        }


def _handle_report_mission_result(state: GameState, tool_input: dict) -> dict:
    state.flags.last_mission = {
        "victory": tool_input["victory"],
        "character_casualties": tool_input.get("character_casualties", []),
        "grunt_casualties": tool_input.get("grunt_casualties", 0),
    }
    return {
        "stored": True,
        "victory": tool_input["victory"],
        "character_casualties": tool_input.get("character_casualties", []),
        "grunt_casualties": tool_input.get("grunt_casualties", 0),
    }


def _handle_step09(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.steps import step09_injuries
    events = step09_injuries.execute(
        state,
        tool_input["character_casualties"],
        tool_input.get("grunt_casualties", 0),
    )
    return _event_result(state, events)


def _handle_step10_xp(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.steps import step10_experience
    events = step10_experience.award_mission_xp(
        state,
        tool_input["deployed"],
        tool_input["casualties"],
    )
    return _event_result(state, events)


def _handle_step10_advancement(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.steps import step10_experience
    events = step10_experience.roll_advancement(
        state, tool_input["character_name"]
    )
    return _event_result(state, events)


def _handle_step11(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.steps import step11_morale
    mission_type = None
    if tool_input.get("mission_type"):
        mission_type = MissionType(tool_input["mission_type"])
    events = step11_morale.execute(
        state,
        battle_casualties=tool_input.get("battle_casualties", 0),
        mission_type=mission_type,
        mission_victory=tool_input.get("mission_victory"),
    )
    return _event_result(state, events)


def _handle_step12(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.steps import step12_tracking
    mt = MissionType(tool_input["mission_type"])
    events = step12_tracking.execute(
        state, mt, tool_input["mission_victory"]
    )
    return _event_result(state, events)


def _handle_step13(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.steps import step13_replacements
    return _event_result(state, step13_replacements.execute(state))


def _handle_step14(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.steps import step14_research
    events = step14_research.execute(
        state,
        theory_id=tool_input.get("theory_id"),
        theory_rp=tool_input.get("theory_rp", 0),
        application_id=tool_input.get("application_id"),
        bio_analysis=tool_input.get("bio_analysis", False),
    )
    return _event_result(state, events)


def _handle_step15(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.steps import step15_building
    events = step15_building.execute(
        state,
        building_id=tool_input.get("building_id"),
        bp_amount=tool_input.get("bp_amount", 0),
        raw_materials_convert=tool_input.get("raw_materials_convert", 0),
    )
    return _event_result(state, events)


def _handle_step16(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.steps import step16_colony_integrity
    return _event_result(state, step16_colony_integrity.execute(state))


def _handle_step17(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.steps import step17_character_event
    return _event_result(state, step17_character_event.execute(state))


def _handle_step18(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.steps import step18_update_sheet
    return _event_result(state, step18_update_sheet.execute(state))


# --- Narrative handlers ---

def _handle_generate_narrative(state: GameState, tool_input: dict) -> dict:
    from planetfall.narrative import generate_narrative_local
    context = tool_input.get("context", "turn_end")
    narrative = generate_narrative_local(state, state.turn_log, context)
    return {"narrative": narrative}


def _handle_get_narrative_summary(state: GameState, tool_input: dict) -> dict:
    from planetfall.narrative import get_narrative_summary
    return {"summary": get_narrative_summary(state)}


# --- Campaign Log & Rollback handlers ---

def _handle_export_turn_log(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.campaign_log import save_turn_log
    path = save_turn_log(state)
    return {"exported": True, "path": str(path)}


def _handle_export_campaign_log(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.campaign_log import save_campaign_log
    path = save_campaign_log(state)
    return {"exported": True, "path": str(path)}


def _handle_undo_last_turn(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.rollback import undo_last_turn
    restored = undo_last_turn(state)
    if restored:
        for field in state.model_fields:
            setattr(state, field, getattr(restored, field))
        return {
            "success": True,
            "restored_turn": restored.current_turn,
            "summary": _state_summary(state),
        }
    return {"success": False, "error": "No previous turn to undo."}


def _handle_rollback_to_turn(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.rollback import rollback_to_turn
    target = tool_input["turn"]
    try:
        restored = rollback_to_turn(state.campaign_name, target)
        for field in state.model_fields:
            setattr(state, field, getattr(restored, field))
        return {
            "success": True,
            "restored_turn": restored.current_turn,
            "summary": _state_summary(state),
        }
    except FileNotFoundError as e:
        return {"success": False, "error": str(e)}


def _handle_list_snapshots(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.persistence import list_snapshots
    return {
        "campaign": state.campaign_name,
        "current_turn": state.current_turn,
        "snapshots": list_snapshots(state.campaign_name),
    }


def _handle_save_game(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.persistence import save_state
    path = save_state(state)
    return {"saved": True, "path": str(path)}


# --- Augmentation handlers ---

def _handle_get_augmentation_options(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.campaign.augmentation import (
        get_available_augmentations, get_augmentation_cost,
    )
    return {
        "augmentations": get_available_augmentations(state),
        "next_cost": get_augmentation_cost(state),
        "ap_available": state.colony.resources.augmentation_points,
    }


def _handle_apply_augmentation(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.campaign.augmentation import apply_augmentation
    events = apply_augmentation(state, tool_input["augmentation_id"])
    return _event_result(state, events)


# --- Equipment handlers ---

def _handle_get_armory(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.campaign.equipment import get_armory_catalog
    return {"items": get_armory_catalog(state)}


def _handle_purchase_equipment(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.campaign.equipment import purchase_equipment
    events = purchase_equipment(
        state, tool_input["item_id"], tool_input["character_name"]
    )
    return _event_result(state, events)


def _handle_swap_equipment(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.campaign.equipment import swap_equipment
    events = swap_equipment(
        state, tool_input["from_character"],
        tool_input["to_character"], tool_input["item_name"]
    )
    return _event_result(state, events)


def _handle_sell_equipment(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.campaign.equipment import sell_equipment
    events = sell_equipment(
        state, tool_input["character_name"], tool_input["item_name"]
    )
    return _event_result(state, events)


# --- Extraction handlers ---

def _handle_get_exploitable_sectors(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.campaign.extraction import get_exploitable_sectors
    return {"sectors": get_exploitable_sectors(state)}


def _handle_start_extraction(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.campaign.extraction import start_extraction
    events = start_extraction(
        state, tool_input["sector_id"],
        tool_input.get("resource_type", "raw_materials"),
    )
    return _event_result(state, events)


def _handle_stop_extraction(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.campaign.extraction import stop_extraction
    events = stop_extraction(state, tool_input["sector_id"])
    return _event_result(state, events)


def _handle_get_active_extractions(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.campaign.extraction import get_active_extractions
    return {"extractions": get_active_extractions(state)}


# --- Calamity handlers ---

def _handle_check_calamity(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.campaign.calamities import check_calamity
    return _event_result(state, check_calamity(state))


def _handle_resolve_calamity(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.campaign.calamities import resolve_calamity_progress
    events = resolve_calamity_progress(
        state, tool_input["calamity_id"],
        tool_input.get("progress", 1),
    )
    return _event_result(state, events)


# --- Slyn handlers ---

def _handle_check_slyn(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.campaign.slyn import check_slyn_interference
    return _event_result(state, check_slyn_interference(state))


def _handle_record_slyn_kills(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.campaign.slyn import record_slyn_kills
    return _event_result(state, record_slyn_kills(state, tool_input["kills"]))


# --- Ancient Signs handlers ---

def _handle_check_ancient_signs(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.campaign.ancient_signs import check_ancient_signs
    return _event_result(state, check_ancient_signs(state))


def _handle_explore_ancient_site(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.campaign.ancient_signs import explore_ancient_site
    return _event_result(state, explore_ancient_site(state, tool_input["sector_id"]))


# --- Post-Mission & Battlefield handlers ---

def _handle_roll_post_mission_finds(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.tables.post_mission_finds import roll_post_mission_finds
    events = roll_post_mission_finds(
        state,
        scientist_alive=tool_input.get("scientist_alive", False),
        scout_alive=tool_input.get("scout_alive", False),
        xp_character_name=tool_input.get("xp_character_name"),
        num_rolls=tool_input.get("num_rolls", 1),
    )
    return _event_result(state, events)


def _handle_get_battlefield_condition(state: GameState, tool_input: dict) -> dict:
    from planetfall.engine.tables.battlefield_conditions import get_mission_condition
    cond = get_mission_condition(state, state.current_turn)
    return {
        "condition": {
            "id": cond.id, "name": cond.name,
            "description": cond.description,
            "visibility_limit": cond.visibility_limit,
            "shooting_penalty": cond.shooting_penalty,
            "movement_penalty": cond.movement_penalty,
            "extra_contacts": cond.extra_contacts,
            "enemy_size_mod": cond.enemy_size_mod,
            "extra_finds_rolls": cond.extra_finds_rolls,
            "terrain_hazards": cond.terrain_hazards,
            "terrain_unstable": cond.terrain_unstable,
        },
    }


# --- Interactive Combat handlers ---

def _combat_state_to_dict(combat_state) -> dict:
    """Convert a CombatState to a serializable dict."""
    return {
        "phase": combat_state.phase.value,
        "round": combat_state.round_number,
        "grid": combat_state.battlefield_grid,
        "player_figures": [
            {
                "name": f.name, "zone": f.zone, "status": f.status,
                "class": f.char_class, "weapon": f.weapon_name,
                "stun_markers": f.stun_markers, "has_acted": f.has_acted,
            }
            for f in combat_state.player_figures
        ],
        "enemy_figures": [
            {
                "name": f.name, "zone": f.zone, "status": f.status,
                "class": f.char_class, "weapon": f.weapon_name,
                "kill_points": f.kill_points, "is_leader": f.is_leader,
                "is_specialist": f.is_specialist,
            }
            for f in combat_state.enemy_figures
        ],
        "reaction": combat_state.reaction_result,
        "current_figure": combat_state.current_figure,
        "available_actions": combat_state.available_actions,
        "log": combat_state.phase_log[-15:],
        "outcome": combat_state.outcome,
    }


def _handle_combat_start(state: GameState, tool_input: dict) -> dict:
    """Start an interactive combat session."""
    from planetfall.engine.combat.missions import setup_mission

    mt = MissionType(tool_input["mission_type"])
    deployed = tool_input["deployed_names"]
    grunt_count = tool_input.get("grunt_count", 0)

    bot_deploy = tool_input.get("bot_deploy", False)
    mission_setup = setup_mission(state, mt, deployed, grunt_count, bot_deploy=bot_deploy)
    _combat.session = CombatSession(mission_setup)
    combat_state = _combat.session.start_battle()

    from planetfall.engine.combat.narrator import narrate_phase_local
    narrative = narrate_phase_local(combat_state)

    result = _combat_state_to_dict(combat_state)
    result["narrative"] = narrative
    return result


def _handle_combat_action(state: GameState, tool_input: dict) -> dict:
    """Execute a player's chosen combat action."""
    if not _combat.session:
        return {"error": "No active combat session. Call combat_start first."}

    action_index = tool_input["action_index"]
    combat_state = _combat.session.choose_action(action_index)

    from planetfall.engine.combat.narrator import narrate_phase_local
    narrative = narrate_phase_local(combat_state)

    result = _combat_state_to_dict(combat_state)
    result["narrative"] = narrative

    if combat_state.phase == CombatPhase.BATTLE_OVER:
        result["final_result"] = _combat.session.get_result()
        from planetfall.engine.combat.narrator import _narrate_combat_summary_local
        result["battle_summary"] = _narrate_combat_summary_local(
            _combat.session.get_result()
        )
        _combat.session = None

    return result


def _handle_combat_advance(state: GameState, tool_input: dict) -> dict:
    """Advance combat to the next phase."""
    if not _combat.session:
        return {"error": "No active combat session. Call combat_start first."}

    combat_state = _combat.session.advance()

    from planetfall.engine.combat.narrator import narrate_phase_local
    narrative = narrate_phase_local(combat_state)

    result = _combat_state_to_dict(combat_state)
    result["narrative"] = narrative

    if combat_state.phase == CombatPhase.BATTLE_OVER:
        result["final_result"] = _combat.session.get_result()
        from planetfall.engine.combat.narrator import _narrate_combat_summary_local
        result["battle_summary"] = _narrate_combat_summary_local(
            _combat.session.get_result()
        )
        _combat.session = None

    return result


def _handle_combat_status(state: GameState, tool_input: dict) -> dict:
    """Get current combat status."""
    if not _combat.session:
        return {"error": "No active combat session.", "active": False}

    combat_state = _combat.session._snapshot()
    result = _combat_state_to_dict(combat_state)
    result["active"] = True
    return result


def _handle_combat_narrate(state: GameState, tool_input: dict) -> dict:
    """Generate narrative for current combat phase."""
    if not _combat.session:
        return {"error": "No active combat session.", "narrative": ""}

    combat_state = _combat.session._snapshot()
    from planetfall.engine.combat.narrator import narrate_phase_local
    narrative = narrate_phase_local(combat_state)
    return {"narrative": narrative}


# ---------------------------------------------------------------------------
# Dispatch registry — maps tool names to handler functions
# ---------------------------------------------------------------------------

_DISPATCH: dict[str, Callable[[GameState, dict], dict]] = {
    # Queries
    "get_state_summary": _handle_get_state_summary,
    "get_research_options": _handle_get_research_options,
    "get_building_options": _handle_get_building_options,
    "get_scouting_options": _handle_get_scouting_options,
    "get_mission_options": _handle_get_mission_options,
    "get_deployment_options": _handle_get_deployment_options,
    # Rules
    "load_rules_section": _handle_load_rules_section,
    "search_rules": _handle_search_rules,
    # Campaign steps
    "step01_recovery": _handle_step01,
    "step02_repairs": _handle_step02,
    "step03_scout_explore": _handle_step03_explore,
    "step03_scout_discovery": _handle_step03_discovery,
    "step04_enemy_activity": _handle_step04,
    "step05_colony_events": _handle_step05,
    "step06_mission_determination": _handle_step06,
    "step07_lock_and_load": _handle_step07,
    "step08_mission": _handle_step08,
    "report_mission_result": _handle_report_mission_result,
    "step09_injuries": _handle_step09,
    "step10_award_xp": _handle_step10_xp,
    "step10_advancement": _handle_step10_advancement,
    "step11_morale": _handle_step11,
    "step12_tracking": _handle_step12,
    "step13_replacements": _handle_step13,
    "step14_research": _handle_step14,
    "step15_building": _handle_step15,
    "step16_colony_integrity": _handle_step16,
    "step17_character_event": _handle_step17,
    "step18_update_sheet": _handle_step18,
    # Interactive combat
    "combat_start": _handle_combat_start,
    "combat_action": _handle_combat_action,
    "combat_advance": _handle_combat_advance,
    "combat_status": _handle_combat_status,
    "combat_narrate": _handle_combat_narrate,
    # Narrative
    "generate_narrative": _handle_generate_narrative,
    "get_narrative_summary": _handle_get_narrative_summary,
    # Campaign log & rollback
    "export_turn_log": _handle_export_turn_log,
    "export_campaign_log": _handle_export_campaign_log,
    "undo_last_turn": _handle_undo_last_turn,
    "rollback_to_turn": _handle_rollback_to_turn,
    "list_snapshots": _handle_list_snapshots,
    # Save
    "save_game": _handle_save_game,
    # Augmentation
    "get_augmentation_options": _handle_get_augmentation_options,
    "apply_augmentation": _handle_apply_augmentation,
    # Equipment
    "get_armory": _handle_get_armory,
    "purchase_equipment": _handle_purchase_equipment,
    "swap_equipment": _handle_swap_equipment,
    "sell_equipment": _handle_sell_equipment,
    # Extraction
    "get_exploitable_sectors": _handle_get_exploitable_sectors,
    "start_extraction": _handle_start_extraction,
    "stop_extraction": _handle_stop_extraction,
    "get_active_extractions": _handle_get_active_extractions,
    # Calamity
    "check_calamity": _handle_check_calamity,
    "resolve_calamity": _handle_resolve_calamity,
    # Slyn
    "check_slyn_interference": _handle_check_slyn,
    "record_slyn_kills": _handle_record_slyn_kills,
    # Ancient Signs
    "check_ancient_signs": _handle_check_ancient_signs,
    "explore_ancient_site": _handle_explore_ancient_site,
    # Post-mission & battlefield
    "roll_post_mission_finds": _handle_roll_post_mission_finds,
    "get_battlefield_condition": _handle_get_battlefield_condition,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def handle_tool_call(
    state: GameState,
    tool_name: str,
    tool_input: dict[str, Any],
) -> str:
    """Dispatch a tool call and return JSON result string.

    Args:
        state: Current game state (mutated in place by step tools).
        tool_name: Name of the tool being called.
        tool_input: Input parameters from Claude.

    Returns:
        JSON string with the tool result.
    """
    handler = _DISPATCH.get(tool_name)
    if handler is None:
        result = {"error": f"Unknown tool: {tool_name}"}
    else:
        result = handler(state, tool_input)
    return json.dumps(result, default=str)

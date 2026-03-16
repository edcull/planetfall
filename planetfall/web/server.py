"""FastAPI server — serves the web UI and bridges WebSocket to game loop."""

from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from planetfall.web.adapter import WebAdapter

_STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Planetfall")
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/")
async def index():
    return FileResponse(str(_STATIC_DIR / "index.html"))


@app.get("/api/campaigns")
async def list_campaigns():
    from planetfall.engine.persistence import list_campaigns as _list, get_campaign_info
    names = _list()
    campaigns = []
    for name in names:
        info = get_campaign_info(name)
        campaigns.append({"name": name, **info})
    return {"campaigns": campaigns}


@app.delete("/api/campaigns/{name}")
async def delete_campaign_endpoint(name: str):
    from planetfall.engine.persistence import delete_campaign
    deleted = delete_campaign(name)
    return {"deleted": deleted}


@app.websocket("/ws/game")
async def game_websocket(websocket: WebSocket):
    await websocket.accept()
    loop = asyncio.get_event_loop()

    def send_fn(payload: dict) -> None:
        """Thread-safe send: push JSON from game thread into async loop."""
        future = asyncio.run_coroutine_threadsafe(
            websocket.send_json(payload), loop
        )
        future.result(timeout=10)

    adapter = WebAdapter(send_fn)

    # Wait for init message from client
    init_msg = await websocket.receive_json()

    thread = threading.Thread(
        target=_run_game_loop, args=(adapter, init_msg), daemon=True
    )
    thread.start()

    try:
        while True:
            msg = await websocket.receive_json()
            if msg.get("type") == "input_response":
                adapter.resolve(msg["id"], msg["value"])
            elif msg.get("type") == "update_roster":
                _apply_roster_update(adapter, msg)
                # Send updated roster directly (avoid deadlock from send_fn)
                if adapter.game_state:
                    from planetfall.web.serializers import serialize_roster
                    await websocket.send_json({
                        "type": "show_roster",
                        "data": serialize_roster(adapter.game_state),
                    })
            elif msg.get("type") == "request_log":
                state = adapter.game_state
                if state:
                    from planetfall.engine.campaign_log import export_turn_log, export_day_zero_log
                    from planetfall.engine.persistence import list_snapshots, load_snapshot, _campaign_dir

                    requested_turn = msg.get("turn")
                    available_turns = list_snapshots(state.campaign_name)
                    current_turn = state.current_turn

                    # Include Day 0 if the log file exists
                    day0_path = _campaign_dir(state.campaign_name) / "turn_000_log.md"
                    if day0_path.exists() and 0 not in available_turns:
                        available_turns = [0] + available_turns

                    if requested_turn == 0:
                        # Day 0: colony founding log
                        if day0_path.exists():
                            log_md = day0_path.read_text(encoding="utf-8")
                        else:
                            log_md = export_day_zero_log(state)
                        display_turn = 0
                    elif requested_turn and requested_turn != current_turn and requested_turn in available_turns:
                        try:
                            snapshot = load_snapshot(state.campaign_name, requested_turn)
                            log_md = export_turn_log(snapshot, snapshot.turn_log)
                        except Exception:
                            log_md = f"# Turn {requested_turn}\n\n*Snapshot unavailable.*"
                        display_turn = requested_turn
                    else:
                        log_md = export_turn_log(state)
                        display_turn = current_turn

                    await websocket.send_json({
                        "type": "colony_log",
                        "markdown": log_md,
                        "current_turn": display_turn,
                        "available_turns": sorted(set(available_turns + [current_turn])),
                    })
                else:
                    await websocket.send_json({
                        "type": "colony_log",
                        "markdown": "# Colony Log\n\n*No data yet.*",
                        "current_turn": 0,
                        "available_turns": [],
                    })
            elif msg.get("type") == "debug_add_milestone":
                state = adapter.game_state
                if state:
                    from planetfall.engine.campaign.milestones import apply_milestone
                    from planetfall.web.serializers import (
                        serialize_milestones, serialize_colony_status,
                        serialize_enemies, serialize_map,
                        serialize_calamities, serialize_ancient_signs,
                    )
                    state.campaign.milestones_completed += 1
                    ms = state.campaign.milestones_completed
                    apply_milestone(state, ms)
                    await websocket.send_json({
                        "type": "show_milestones",
                        "data": serialize_milestones(state),
                    })
                    await websocket.send_json({
                        "type": "show_colony_status",
                        "data": serialize_colony_status(state),
                    })
                    await websocket.send_json({
                        "type": "show_enemies",
                        "data": serialize_enemies(state),
                    })
                    await websocket.send_json({
                        "type": "show_map",
                        "data": serialize_map(state),
                    })
                    await websocket.send_json({
                        "type": "show_calamities",
                        "data": serialize_calamities(state),
                    })
                    await websocket.send_json({
                        "type": "show_ancient_signs",
                        "data": serialize_ancient_signs(state),
                    })
            elif msg.get("type") == "update_setting":
                state = adapter.game_state
                if state:
                    key = msg.get("key")
                    value = msg.get("value")
                    if key == "narrative_disabled" and isinstance(value, bool):
                        state.settings.narrative_disabled = value
                        from planetfall.engine.persistence import save_state
                        save_state(state)
            elif msg.get("type") == "resource_cache_request":
                # Out-of-band SP spend for resources from colony panel
                state = adapter.game_state
                if state:
                    from planetfall.engine.campaign.story_points import (
                        can_spend, roll_resource_cache, allocate_resource_cache,
                    )
                    from planetfall.web.serializers import serialize_colony_status
                    if not can_spend(state):
                        await websocket.send_json({
                            "type": "resource_cache_result",
                            "success": False,
                            "message": "Not enough Story Points.",
                        })
                    else:
                        events, budget = roll_resource_cache(state)
                        state.turn_log.extend(events)
                        # Send roll result to client for allocation UI
                        await websocket.send_json({
                            "type": "resource_cache_rolled",
                            "budget": budget,
                            "dice": events[0].dice_rolls[0].values if events and events[0].dice_rolls else [],
                            "sp_remaining": state.colony.resources.story_points,
                        })
            elif msg.get("type") == "resource_cache_allocate":
                state = adapter.game_state
                if state:
                    from planetfall.engine.campaign.story_points import allocate_resource_cache
                    from planetfall.web.serializers import serialize_colony_status
                    from planetfall.engine.persistence import save_state
                    bp = int(msg.get("bp", 0))
                    rp = int(msg.get("rp", 0))
                    rm = int(msg.get("rm", 0))
                    budget = int(msg.get("budget", 0))
                    alloc_events = allocate_resource_cache(state, budget, bp, rp, rm)
                    # Record in turn log
                    state.turn_log.extend(alloc_events)
                    save_state(state)
                    await websocket.send_json({
                        "type": "resource_cache_result",
                        "success": True,
                        "bp": bp, "rp": rp, "rm": rm,
                        "budget": budget,
                    })
                    await websocket.send_json({
                        "type": "show_colony_status",
                        "data": serialize_colony_status(state),
                    })
            elif msg.get("type") == "debug_set_step":
                state = adapter.game_state
                if state:
                    step = int(msg.get("step", 0))
                    step = max(0, min(step, 18))
                    state.current_step = step
                    from planetfall.engine.persistence import save_state
                    save_state(state)
                    await websocket.send_json({
                        "type": "debug_step_set",
                        "step": state.current_step,
                        "message": f"current_step set to {state.current_step}",
                    })
    except WebSocketDisconnect:
        adapter.disconnect()


def _apply_roster_update(adapter: WebAdapter, msg: dict) -> None:
    """Update character title/name/role from a client roster edit (no send)."""
    state = adapter.game_state
    if not state:
        return
    name = msg.get("character_name")
    updates = msg.get("updates", {})
    if not name or not updates:
        return
    for char in state.characters:
        if char.name == name:
            if "name" in updates and updates["name"].strip():
                char.name = updates["name"].strip()
            if "title" in updates:
                char.title = updates["title"].strip()
            if "role" in updates:
                char.role = updates["role"].strip()
            if "narrative" in updates:
                char.narrative_background = updates["narrative"].strip()
            break


def _run_game_loop(adapter: WebAdapter, init_msg: dict) -> None:
    """Run the game loop in a background thread using the WebAdapter."""
    from planetfall.cli.prompts import SaveAndQuit

    try:
        action = init_msg.get("action", "")

        if action == "new":
            state = _setup_new_campaign(adapter, init_msg)
        elif action == "continue":
            from planetfall.engine.persistence import load_state, _campaign_dir
            campaign_name = init_msg.get("campaign_name", "")
            state = load_state(campaign_name)
            # Generate Day 0 log retroactively if missing
            day0 = _campaign_dir(campaign_name) / "turn_000_log.md"
            if not day0.exists():
                from planetfall.engine.campaign_log import save_day_zero_log
                save_day_zero_log(state)
            adapter.show_colony_status(state)
            adapter.show_map(state)
            adapter.show_roster(state)
            adapter.show_armory(state)
            adapter.show_ancient_signs(state)
            adapter.show_milestones(state)
            adapter.show_conditions(state)
            adapter.show_lifeforms(state)
            adapter.show_enemies(state)
            adapter.show_augmentations(state)
            adapter.show_artifacts(state)
            adapter.show_calamities(state)
            adapter.show_morale(state)
        else:
            adapter.message("Unknown action.", style="error")
            return

        adapter.game_state = state

        # Initial missions if needed
        if not state.campaign.initial_missions_complete:
            _web_initial_missions(adapter, state)

        # Campaign turn loop
        while True:
            from planetfall.orchestrator import run_campaign_turn_local
            from planetfall.config import get_api_key, get_orchestrator_mode

            mode = get_orchestrator_mode()
            use_narrative = mode == "hybrid" and bool(get_api_key())
            state = run_campaign_turn_local(state, use_narrative_api=use_narrative, ui=adapter)

            # Auto-save turn log
            from planetfall.engine.campaign_log import save_turn_log
            save_turn_log(state)

            # Check end conditions
            if state.campaign.end_game_triggered:
                adapter.message("The End Game has been triggered!", style="bold")
                break

            if state.colony.integrity <= -10:
                adapter.message(
                    f"COLONY COLLAPSE! Integrity at {state.colony.integrity}.",
                    style="error",
                )
                break

            if state.colony.morale <= 0 and len(state.characters) == 0:
                adapter.message("TOTAL LOSS! No characters remain.", style="error")
                break

            # Between-turns menu
            should_continue = _between_turns_menu(adapter, state)
            if not should_continue:
                break

        adapter._send({"type": "game_over"})

    except SaveAndQuit:
        from planetfall.engine.persistence import save_state
        save_state(state)
        adapter.message("Game saved.", style="success")
        adapter._send({"type": "game_over"})

    except Exception as e:
        adapter._send({"type": "error", "message": str(e)})


def _build_setup_reference_data() -> dict:
    """Build reference data for colony setup and roster editor."""
    from planetfall.engine.models import CharacterClass, STARTING_PROFILES
    from planetfall.engine.campaign.setup import MOTIVATION_TABLE, PRIOR_EXPERIENCE_TABLE

    class_profiles = {}
    for cls in [CharacterClass.SCIENTIST, CharacterClass.SCOUT, CharacterClass.TROOPER]:
        p = STARTING_PROFILES[cls]
        class_profiles[cls.value] = {
            "reactions": p.reactions, "speed": p.speed,
            "combat_skill": p.combat_skill, "toughness": p.toughness,
            "savvy": p.savvy,
        }

    motivations = sorted(set(entry[2] for entry in MOTIVATION_TABLE))

    experiences = [{"name": "None", "label": "None — fresh recruit", "effects": {}}]
    seen: set[str] = set()
    for _low, _high, exp_name, effects in PRIOR_EXPERIENCE_TABLE:
        if exp_name in seen:
            continue
        seen.add(exp_name)
        serialized_effects = {}
        for stat, val in effects.items():
            if stat == "loyalty":
                serialized_effects[stat] = val.value
            else:
                serialized_effects[stat] = val
        effect_parts = []
        for stat, val in effects.items():
            if stat == "loyalty":
                effect_parts.append(f"Loyalty: {val.value}")
            elif stat == "story_points":
                effect_parts.append(f"+{val} SP")
            else:
                stat_label = {
                    "reactions": "React", "speed": "Spd", "combat_skill": "CS",
                    "toughness": "Tough", "savvy": "Savvy", "xp": "XP",
                    "kill_points": "KP",
                }.get(stat, stat)
                effect_parts.append(f"{stat_label} +{val}")
        label = f"{exp_name} ({', '.join(effect_parts)})" if effect_parts else exp_name
        experiences.append({
            "name": exp_name, "label": label, "effects": serialized_effects,
        })

    return {
        "class_profiles": class_profiles,
        "motivations": motivations,
        "experiences": experiences,
        "subspecies": ["standard", "feral", "hulker", "stalker"],
    }


def _build_default_roster() -> list[dict]:
    """Build default roster for new campaign."""
    layout = [
        ("Scientist", True), ("Scientist", False),
        ("Scout", True), ("Scout", False),
        ("Trooper", True), ("Trooper", True),
        ("Trooper", False), ("Trooper", False),
    ]
    roster = []
    for i, (cls_name, exp) in enumerate(layout, 1):
        roster.append({
            "name": f"{cls_name} {i}",
            "char_class": cls_name.lower(),
            "experienced": exp,
            "sub_species": "standard",
            "title": "", "role": "",
            "motivation": "", "prior_experience": "",
            "narrative_background": "",
        })
    return roster


def _process_roster_data(roster_data: list[dict]) -> list:
    """Process roster editor result into Character objects.

    Characters with no motivation/experience get them rolled randomly.
    All user-provided fields (name, title, role, background) are preserved.
    """
    from planetfall.engine.models import CharacterClass, SubSpecies, Loyalty, STARTING_PROFILES
    from planetfall.engine.campaign.setup import (
        import_character, PRIOR_EXPERIENCE_TABLE,
        roll_motivation, roll_prior_experience,
    )

    characters = []

    for char_data in roster_data:
        cls = CharacterClass(char_data["char_class"])
        sub = SubSpecies(char_data.get("sub_species", "standard"))
        prior_exp = char_data.get("prior_experience", "")
        has_experience = prior_exp and prior_exp != "None"
        motivation = char_data.get("motivation", "")
        experienced = char_data.get("experienced", False) or has_experience

        # Roll motivation if not provided
        if not motivation:
            motivation = roll_motivation()

        # Roll prior experience if experienced but not specified
        if experienced and not has_experience:
            prior_exp, exp_effects = roll_prior_experience()
            has_experience = True
        else:
            exp_effects = None

        profile = STARTING_PROFILES[cls].model_dump()
        if sub == SubSpecies.HULKER:
            profile["toughness"] = 5
        xp = 0
        kill_points = 0
        loyalty = Loyalty.COMMITTED

        if has_experience:
            if exp_effects is not None:
                # Already have effects from rolling
                for stat, val in exp_effects.items():
                    if stat == "loyalty":
                        loyalty = val
                    elif stat == "story_points":
                        pass
                    elif stat in profile:
                        profile[stat] += val
                    elif stat == "xp":
                        xp = val
                    elif stat == "kill_points":
                        kill_points = val
            else:
                # Look up effects from table
                for _l, _h, ename, effects in PRIOR_EXPERIENCE_TABLE:
                    if ename == prior_exp:
                        for stat, val in effects.items():
                            if stat == "loyalty":
                                loyalty = val
                            elif stat == "story_points":
                                pass
                            elif stat in profile:
                                profile[stat] += val
                            elif stat == "xp":
                                xp = val
                            elif stat == "kill_points":
                                kill_points = val
                        break

        characters.append(
            import_character(
                name=char_data["name"],
                char_class=cls,
                reactions=profile["reactions"],
                speed=profile["speed"],
                combat_skill=profile["combat_skill"],
                toughness=profile["toughness"],
                savvy=profile["savvy"],
                xp=xp,
                kill_points=kill_points,
                loyalty=loyalty,
                sub_species=sub,
                title=char_data.get("title", ""),
                role=char_data.get("role", ""),
                motivation=motivation,
                prior_experience=prior_exp,
                narrative_background=char_data.get("narrative_background", ""),
            )
        )

    return characters


def _setup_new_campaign(adapter: WebAdapter, init_msg: dict) -> Any:
    """Run campaign setup using a single colony_setup modal."""
    from planetfall.engine.campaign.setup import create_new_campaign
    from planetfall.engine.models import ColonizationAgenda
    from planetfall.engine.persistence import save_state
    from planetfall.config import get_api_key
    from uuid import uuid4

    # Build all reference data
    ref_data = _build_setup_reference_data()

    agendas = [
        {"value": "", "label": "Roll randomly"},
        {"value": "scientific", "label": "Scientific Mission (+3 RP)"},
        {"value": "corporate", "label": "Corporate Funded (+2 Investigation Sites)"},
        {"value": "unity", "label": "Unity Colonization Drive (+3 Raw Materials)"},
        {"value": "independent", "label": "Independent Mission (+1 Story Point)"},
        {"value": "military", "label": "Military Expedition (+2 Grunts)"},
        {"value": "affinity", "label": "Affinity Group (+5 Morale)"},
    ]

    # Send colony_setup modal with all data
    rid = str(uuid4())
    adapter._send({
        "type": "input_request",
        "input_type": "colony_setup",
        "id": rid,
        "campaign_name": init_msg.get("campaign_name", "Colony Alpha"),
        "agendas": agendas,
        **ref_data,
        "default_roster": _build_default_roster(),
    })
    setup_data = adapter._wait_for_response(rid)

    # Extract colony settings
    campaign_name = setup_data.get("campaign_name", "Colony Alpha")
    colony_name = setup_data.get("colony_name", "Haven")
    admin_name = setup_data.get("admin_name", "Commander")

    agenda_val = setup_data.get("agenda", "")
    agenda_mapping = {
        "scientific": ColonizationAgenda.SCIENTIFIC,
        "corporate": ColonizationAgenda.CORPORATE,
        "unity": ColonizationAgenda.UNITY,
        "independent": ColonizationAgenda.INDEPENDENT,
        "military": ColonizationAgenda.MILITARY,
        "affinity": ColonizationAgenda.AFFINITY,
    }
    agenda = agenda_mapping.get(agenda_val)  # None = roll randomly

    # Process roster
    roster_data = setup_data.get("roster", [])
    characters = _process_roster_data(roster_data)

    api_key = get_api_key()

    # Create campaign shell (no character generation — we handle it here)
    state = create_new_campaign(
        campaign_name=campaign_name,
        colony_name=colony_name,
        agenda=agenda,
        character_specs=None,
        admin_name=admin_name,
        api_key="",  # skip background gen inside create_new_campaign
    )
    state.characters = characters

    # Generate names/backgrounds only for characters that need them
    from planetfall.engine.campaign.setup import (
        generate_character_backgrounds_api, generate_character_names,
        _is_unnamed,
    )
    needs_names = any(_is_unnamed(c.name) for c in characters)
    needs_bg = any(not c.narrative_background for c in characters)

    if needs_names or needs_bg:
        if api_key:
            adapter.message("Generating campaign with AI narrative backgrounds...", style="dim")
        else:
            adapter.message("Generating campaign...", style="dim")
        generate_character_backgrounds_api(
            state.characters, agenda, colony_name, api_key=api_key,
        )
    else:
        adapter.message("Creating campaign...", style="dim")

    # Generate colony founding description
    if not state.colony.description:
        from planetfall.engine.campaign.setup.backgrounds import generate_colony_description
        state.colony.description = generate_colony_description(state, api_key=api_key)

    # Allow roster edits on colony_ready screen
    adapter.game_state = state

    # Send colony_ready with full roster for the loading modal
    from planetfall.web.serializers import serialize_roster
    roster_result = serialize_roster(state)
    rid2 = str(uuid4())
    adapter._send({
        "type": "input_request",
        "input_type": "colony_ready",
        "id": rid2,
        "characters": roster_result["characters"],
        "colony_description": state.colony.description or "",
    })
    adapter._wait_for_response(rid2)

    adapter.show_colony_status(state)
    adapter.show_roster(state)
    adapter.show_map(state)
    adapter.show_armory(state)
    adapter.show_ancient_signs(state)
    adapter.show_milestones(state)
    adapter.show_conditions(state)
    adapter.show_lifeforms(state)
    adapter.show_enemies(state)
    adapter.show_augmentations(state)
    adapter.show_artifacts(state)
    adapter.show_calamities(state)
    adapter.show_morale(state)

    save_state(state)
    from planetfall.engine.campaign_log import save_day_zero_log
    save_day_zero_log(state)

    return state


def _prompt_import_character(adapter: WebAdapter, index: int) -> dict:
    """Prompt for creating a character with class template + motivation/experience."""
    from planetfall.engine.models import (
        CharacterClass, SubSpecies, Loyalty, STARTING_PROFILES,
    )
    from planetfall.engine.campaign.setup import (
        MOTIVATION_TABLE, PRIOR_EXPERIENCE_TABLE,
    )

    adapter.message(f"\n--- Character {index} ---", style="info")
    name = adapter.text("Name:")

    cls_choice = adapter.select("Class:", ["Scientist", "Scout", "Trooper"])
    char_class = CharacterClass(cls_choice.lower())

    sub_species = SubSpecies.STANDARD
    if adapter.confirm("Choose sub-species?", default=False):
        ss_choice = adapter.select(
            "Sub-species:",
            ["Standard Human", "Feral", "Hulker", "Stalker"],
        )
        ss_mapping = {
            "Standard Human": SubSpecies.STANDARD,
            "Feral": SubSpecies.FERAL,
            "Hulker": SubSpecies.HULKER,
            "Stalker": SubSpecies.STALKER,
        }
        sub_species = ss_mapping[ss_choice]

    profile = STARTING_PROFILES[char_class].model_dump()
    if sub_species == SubSpecies.HULKER:
        profile["toughness"] = 5

    title = adapter.text("Title (optional):", default="")
    role = adapter.text("Role (optional):", default="")

    # Motivation
    motivation_names = sorted(set(entry[2] for entry in MOTIVATION_TABLE))
    motivation = adapter.select("Motivation:", motivation_names)

    # Prior experience with stat effects shown
    exp_choices = ["None — fresh recruit"]
    exp_map: dict[str, dict] = {}
    seen: set[str] = set()
    for _low, _high, exp_name, effects in PRIOR_EXPERIENCE_TABLE:
        if exp_name in seen:
            continue
        seen.add(exp_name)
        effect_parts = []
        for stat, val in effects.items():
            if stat == "loyalty":
                effect_parts.append(f"Loyalty: {val.value}")
            elif stat == "story_points":
                effect_parts.append(f"+{val} SP")
            else:
                stat_label = {
                    "reactions": "React", "speed": "Spd", "combat_skill": "CS",
                    "toughness": "Tough", "savvy": "Savvy", "xp": "XP",
                    "kill_points": "KP",
                }.get(stat, stat)
                effect_parts.append(f"{stat_label} +{val}")
        label = f"{exp_name} ({', '.join(effect_parts)})" if effect_parts else exp_name
        exp_choices.append(label)
        exp_map[label] = effects

    exp_choice = adapter.select("Prior Experience:", exp_choices)

    loyalty = Loyalty.COMMITTED
    xp = 0
    kill_points = 0
    prior_experience = ""

    if not exp_choice.startswith("None"):
        effects = exp_map[exp_choice]
        prior_experience = exp_choice.split(" (")[0]
        for stat, val in effects.items():
            if stat == "loyalty":
                loyalty = val
            elif stat == "story_points":
                pass
            elif stat in profile:
                profile[stat] = profile[stat] + val
            elif stat == "xp":
                xp = val
            elif stat == "kill_points":
                kill_points = val

    narrative_bg = adapter.text("Background (optional):", default="")

    return {
        "name": name,
        "class": char_class,
        "sub_species": sub_species,
        "title": title,
        "role": role,
        "reactions": profile["reactions"],
        "speed": profile["speed"],
        "combat_skill": profile["combat_skill"],
        "toughness": profile["toughness"],
        "savvy": profile["savvy"],
        "xp": xp,
        "kill_points": kill_points,
        "loyalty": loyalty,
        "motivation": motivation,
        "prior_experience": prior_experience,
        "narrative_background": narrative_bg,
    }


def _web_initial_missions(adapter: WebAdapter, state: Any) -> None:
    """Web-compatible initial missions handler."""
    from planetfall.engine.persistence import save_state
    from planetfall.engine.combat.initial_missions import MISSION_ORDER

    adapter.clear()
    adapter.show_colony_status(state)
    adapter.show_map(state)

    missions = [
        {"value": "play", "name": "Play Initial Missions",
         "description": "Complete 3 tactical missions to establish your colony.",
         "rewards": "Earn bonuses based on mission outcomes."},
        {"value": "skip_bonus", "name": "Skip Missions (All Bonuses)",
         "description": "Automatically establish the colony with all bonuses granted.",
         "rewards": "+2 Raw Materials, +2 Research Points, +3 Morale."},
        {"value": "skip_none", "name": "Skip Missions (No Bonuses)",
         "description": "Establish the colony immediately without any starting bonuses.",
         "rewards": "No bonuses. Start from scratch."},
    ]
    from uuid import uuid4
    rid = str(uuid4())
    adapter._send({
        "type": "input_request", "input_type": "mission_select",
        "id": rid, "prompt": "Establish Colony", "missions": missions,
    })
    choice = adapter._wait_for_response(rid)

    if choice == "play":
        from planetfall.engine.combat.initial_missions import run_initial_missions_ui
        run_initial_missions_ui(state, adapter)
        return

    if choice == "skip_bonus":
        adapter.clear()
        adapter.message("Landing site established — all bonuses granted.")

        state.colony.resources.raw_materials += 2
        adapter.message("Beacons: +2 Raw Materials")

        state.colony.resources.research_points += 2
        adapter.message("Analysis: +2 Research Points")

        state.colony.morale += 3
        adapter.message("Perimeter: +3 Colony Morale")

        from planetfall.engine.models import MissionResult
        for _, key in MISSION_ORDER:
            state.campaign.initial_mission_results[key] = MissionResult(victory=True)

    else:
        adapter.clear()
        adapter.message("Landing site established — no bonuses granted.", style="dim")

        from planetfall.engine.models import MissionResult
        for _, key in MISSION_ORDER:
            state.campaign.initial_mission_results[key] = MissionResult(victory=False)

    state.campaign.initial_missions_complete = True
    save_state(state)
    adapter.pause()


def _between_turns_menu(adapter: WebAdapter, state: Any) -> bool:
    """Between-turns menu. Returns True to continue, False to quit."""
    from planetfall.engine.persistence import save_state

    while True:
        adapter.clear()
        adapter.show_colony_status(state)
        adapter.show_map(state)
        adapter.show_armory(state)
        adapter.show_ancient_signs(state)
        adapter.show_milestones(state)
        adapter.show_conditions(state)
        adapter.show_lifeforms(state)
        adapter.show_enemies(state)
        adapter.show_augmentations(state)
        adapter.show_artifacts(state)
        adapter.show_calamities(state)
        adapter.show_morale(state)

        choices = [
            "Continue to next turn",
            "Save and quit",
        ]
        choice = adapter.select("Between turns:", choices)

        if choice == "Continue to next turn":
            return True
        elif choice == "Save and quit":
            save_state(state)
            adapter.message("Game saved. See you next time!", style="success")
            return False


def _view_colony_log(adapter: WebAdapter, state: Any) -> None:
    """View turn logs with navigation."""
    from planetfall.engine.persistence import _campaign_dir

    campaign_dir = _campaign_dir(state.campaign_name)
    log_files = sorted(campaign_dir.glob("turn_*_log.md"))

    if not log_files:
        adapter.message("No turn logs available yet.", style="dim")
        adapter.pause()
        return

    i = len(log_files) - 1
    while True:
        adapter.clear()
        md_text = log_files[i].read_text(encoding="utf-8")
        adapter._send({
            "type": "show_log",
            "text": md_text,
            "index": i + 1,
            "total": len(log_files),
        })

        choices = []
        if i > 0:
            choices.append("Previous day")
        if i < len(log_files) - 1:
            choices.append("Next day")
        choices.append("Exit logs")

        choice = adapter.select("", choices)
        if choice == "Previous day":
            i -= 1
        elif choice == "Next day":
            i += 1
        else:
            return


def run_server(host: str = "127.0.0.1", port: int = 8000):
    """Start the web server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()

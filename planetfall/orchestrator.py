"""Orchestrator — Claude API-powered game master for Planetfall.

Uses Claude's tool_use capability to drive the 18-step campaign turn.
Claude acts as the game master: it reads rules sections on demand,
calls engine functions via tools, presents choices to the player,
and generates narrative summaries.

Falls back to a simple sequential loop if no API key is configured.
"""

from __future__ import annotations

import json
from typing import Any

from planetfall.config import get_api_key

from planetfall.engine.models import GameState, TurnEvent, TurnEventType, DiceRoll
from planetfall.engine.persistence import save_state
from planetfall.tools.definitions import ALL_TOOLS
from planetfall.tools.handlers import handle_tool_call
from planetfall.rules.loader import get_section_for_step


# --- System prompt for the orchestrator ---

SYSTEM_PROMPT = """\
You are the Game Master for **Planetfall**, a solo sci-fi colony management \
wargame. You guide the player through each 18-step campaign turn, calling \
game engine tools to execute mechanics and presenting results with narrative flair.

## Your Role
- Execute each campaign turn step in order (1-18)
- Present choices to the player when decisions are needed
- Call the appropriate tool for each step
- Narrate events in a gritty frontier sci-fi tone
- Track context across the turn (casualties, mission type, etc.)

## Turn Step Sequence
1. Recovery — heal sick bay characters
2. Repairs — spend raw materials on colony integrity
3. Scout Reports — explore sectors, roll discoveries
4. Enemy Activity — check enemy movements
5. Colony Events — random colony events
6. Mission Determination — choose mission type
7. Lock and Load — deploy characters and grunts
8. Play Out Mission — resolve combat (auto or manual)
9. Injuries — roll for casualty outcomes
10. Experience — award XP, check advancements
11. Morale — adjust colony morale
12. Tracking — update enemy/mission tracking
13. Replacements — check for new recruits/gear
14. Research — spend RP on theories/applications
15. Building — spend BP on colony buildings
16. Colony Integrity — check colony status
17. Character Event — roll for character events
18. Update Sheet — finalize turn

## Combat (Step 8) — Interactive Mode
When the player has deployed characters and is ready for combat:
1. Call `combat_start` with the mission type and deployed characters
2. Present the battlefield layout and available actions to the player
3. For each player figure activation:
   - Show the figure's position, status, and available actions
   - Include the narrative description from the tool result
   - Ask the player which action to take (by index number)
   - Call `combat_action` with their chosen index
4. When no player actions remain, call `combat_advance` to run the enemy phase
5. Repeat until battle_over — then report the final_result and battle_summary
6. Use the combat results for Steps 9-12 (injuries, XP, morale, tracking)

When narrating combat, weave the narrative text from tool results into your \
response. Describe the battlefield, the tension, and the consequences of \
each action. Make combat feel visceral and tactical.

## Formatting
- Start each step with a markdown header: ## Step N: Name
  (e.g. "## Step 1: Recovery", "## Step 8: Play Out Mission")
- This header format is required — the client uses it to render styled separators

## Player Choice Steps — IMPORTANT
For steps that require player decisions, you MUST call the query tool first \
to get real game data, then present the actual options. Never guess or invent \
options. Specifically:

- **Step 3 (Scouting):** Call `get_scouting_options` FIRST. Present the list \
of unexplored sectors with their IDs. Ask which sector to scout. Then present \
the list of available scout characters by name and ask which scout to assign \
for the discovery roll (or "none").
- **Step 6 (Mission):** Call `get_mission_options` FIRST. Present missions with \
their rewards. If a mission has `target_sectors` with multiple entries, tell the \
player multiple locations are available. After they pick the mission type, ask \
which sector to target (show sector details if `target_details` is present).
- **Step 7 (Deployment):** Call `get_deployment_options` FIRST. List characters \
by name and let the player choose who to deploy.
- **Steps 14/15 (Research/Building):** Call the respective options tool first.

Always present choices as a numbered list of the ACTUAL options from the tool, \
then ask the player to pick.

## Guidelines
- Always start by getting a state summary to understand the current situation
- After combat-heavy or dramatic events, generate a narrative passage
- During combat, include the narrative descriptions from combat tools \
in your responses to create an immersive battle experience
- Be concise but atmospheric — blend mechanics with storytelling
- When the player asks about rules, use load_rules_section or search_rules
- Save the game after completing the turn
"""


import re

# Pattern to detect step headers in Claude's markdown output
_STEP_HEADER_RE = re.compile(
    r"^#{1,3}\s+\*{0,2}(?:Step\s+)?(\d{1,2})[\s:.\-—]+(.+?)\*{0,2}\s*$",
    re.MULTILINE,
)


def _render_api_text(text: str) -> None:
    """Render Claude API text output with Rich step headers.

    Detects step header lines (e.g. '## Step 3: Scout Reports') and replaces
    them with the same styled rule lines used by the local orchestrator.
    All other text is rendered through Rich Markdown.
    """
    from rich.markdown import Markdown
    from planetfall.cli.display import console

    # Split text around step headers
    parts = _STEP_HEADER_RE.split(text)

    # parts alternates: [before, step_num, step_name, between, step_num, step_name, ...]
    i = 0
    while i < len(parts):
        if i + 2 < len(parts):
            # Check if parts[i+1] is a step number
            try:
                step_num = int(parts[i + 1])
                step_name = parts[i + 2].strip().rstrip("*").strip()

                # Render any text before this header
                before = parts[i].strip()
                if before:
                    console.print(Markdown(before))

                # Render the styled step header
                from planetfall.cli.display import print_step_header
                print_step_header(step_num, step_name)

                i += 3
                continue
            except (ValueError, IndexError):
                pass

        # Regular text chunk
        chunk = parts[i].strip()
        if chunk:
            console.print(Markdown(chunk))
        i += 1


def run_campaign_turn_api(
    state: GameState,
    api_key: str = "",
) -> GameState:
    """Run a campaign turn using Claude API as the orchestrator.

    Claude drives the turn sequence, calling tools to execute each step
    and interacting with the player for decisions.
    """
    from planetfall.cli.display import console
    from planetfall.config import get_narrative_model

    if not api_key:
        api_key = get_api_key()

    if not api_key:
        console.print("[yellow]No API key found. Falling back to local orchestrator.[/yellow]")
        return run_campaign_turn_local(state)

    try:
        import anthropic
    except ImportError:
        console.print("[yellow]anthropic package not installed. Falling back to local orchestrator.[/yellow]")
        return run_campaign_turn_local(state)

    client = anthropic.Anthropic(api_key=api_key)

    # Build initial context with rules for early steps
    rules_context = get_section_for_step(1)

    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": (
                f"Begin Campaign Turn {state.current_turn}. "
                f"Start by getting the state summary, then guide me through "
                f"all 18 steps.\n\n"
                f"Relevant rules for early steps:\n{rules_context[:3000]}"
            ),
        },
    ]

    # Conversation loop
    while True:
        from planetfall.api_tracker import tracked_api_call
        response = tracked_api_call(
            client, caller="orchestrator",
            model=get_narrative_model(),
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=ALL_TOOLS,
            messages=messages,
        )

        # Process response content blocks
        assistant_content = response.content
        tool_results = []
        has_text = False

        for block in assistant_content:
            if block.type == "text":
                has_text = True
                _render_api_text(block.text)
            elif block.type == "tool_use":
                # Execute the tool
                result_str = handle_tool_call(
                    state, block.name, block.input
                )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_str,
                })

        # Add assistant message to history
        messages.append({"role": "assistant", "content": assistant_content})

        # If there were tool calls, send results back
        if tool_results:
            messages.append({"role": "user", "content": tool_results})
            continue

        # If Claude stopped and wants user input
        if response.stop_reason == "end_turn":
            if has_text:
                user_input = input("\n> ").strip()
                if user_input.lower() in ("quit", "exit", "q"):
                    console.print("[yellow]Saving and exiting...[/yellow]")
                    save_state(state)
                    break
                messages.append({"role": "user", "content": user_input})
            else:
                # No text and no tool calls — turn is done
                break
        else:
            # tool_use stop — loop continues via tool results above
            pass

    # Show API usage summary
    from planetfall.api_tracker import get_tracker
    tracker = get_tracker()
    if tracker.call_count > 0:
        from planetfall.cli.display import console
        console.print(f"\n{tracker.summary()}")

    return state


# --- Local fallback orchestrator (no API) ---

STEP_NAMES = {
    1: "Recovery",
    2: "Repairs",
    3: "Scout Reports",
    4: "Enemy Activity",
    5: "Colony Events",
    6: "Mission Determination",
    7: "Lock and Load",
    8: "Play Out Mission",
    9: "Battle Results",
    10: "Experience Progression",
    11: "Colony Morale Adjustments",
    12: "Track Enemy Info & Mission Data",
    13: "Replacements",
    14: "Research",
    15: "Building",
    16: "Colony Integrity",
    17: "Character Event",
    18: "Update Colony Tracking Sheet",
}


def run_campaign_turn_local(
    state: GameState,
    use_narrative_api: bool = False,
    ui: Any | None = None,
) -> GameState:
    """Execute a campaign turn using local Python loop.

    All game mechanics run instantly via local Python. When use_narrative_api
    is True (hybrid mode), Claude API generates narrative prose at key moments
    using a fast model — typically 1-3 API calls per turn instead of 15+.

    Args:
        use_narrative_api: If True, call Claude API for narrative at dramatic
            moments (post-combat, colony events, turn end).
    """
    from planetfall.engine.models import MissionType
    from planetfall.engine.steps import (
        step01_recovery, step02_repairs, step09_injuries,
        step10_experience, step12_tracking,
        step13_replacements, step14_research, step15_building,
        step17_character_event, step18_update_sheet,
    )
    from planetfall.narrative import generate_narrative_local, generate_narrative_api
    if ui is None:
        from planetfall.ui import CLIAdapter
        ui = CLIAdapter()
    from planetfall.config import get_api_key, get_hybrid_narrative_model
    from planetfall.orchestrator_steps import (
        execute_step03_scout, execute_step04_enemy, execute_step05_colony_events,
        execute_step06_mission, execute_step07_deploy,
        execute_step08_mission, execute_post_mission_finds,
        execute_step11_morale, execute_mid_turn_systems,
        execute_augmentation_opportunity, execute_step16_integrity,
    )

    api_key = get_api_key() if use_narrative_api else ""
    narrative_model = get_hybrid_narrative_model() if use_narrative_api else ""

    all_events: list[TurnEvent] = []
    _narrative_batch: list[TurnEvent] = []

    def _record(evts: list[TurnEvent]) -> None:
        """Extend all_events + turn_log and print."""
        all_events.extend(evts)
        state.turn_log.extend(evts)
        _narrative_batch.extend(evts)
        ui.show_events(evts)

    # Map narrative contexts to their associated step numbers
    _NARRATIVE_STEP_MAP = {
        "scout_report": 3, "colony_event": 5, "battle": 9,
        "character_event": 17, "turn_end": 18,
    }

    def _narrate(context: str, combat_log: list[str] | None = None, modal: bool = False) -> str | None:
        """Generate and display narrative for batched events, then clear batch.

        If modal=True, returns the text without displaying (caller shows it).
        """
        if not _narrative_batch:
            return None
        if use_narrative_api and api_key:
            text = generate_narrative_api(
                state, _narrative_batch, context,
                api_key=api_key, model=narrative_model,
                combat_log=combat_log,
            )
        else:
            text = generate_narrative_local(state, _narrative_batch, context)

        if not modal:
            ui.message(f"\n{text}", style="narrative")

        # Save narrative prose to turn log so it persists in save files
        narr_step = _NARRATIVE_STEP_MAP.get(context, 0)
        state.turn_log.append(TurnEvent(
            step=narr_step,
            event_type=TurnEventType.NARRATIVE,
            description=text,
        ))
        _narrative_batch.clear()
        return text

    def _save(step: int = 0):
        """Auto-save after each step, recording progress."""
        if step:
            state.current_step = step
        save_state(state)
        from planetfall.engine.campaign_log import save_turn_log
        save_turn_log(state)

    # Resume point: skip steps already completed this turn
    done = state.current_step  # last completed step
    td = state.turn_data  # inter-step data dict

    if done > 0:
        ui.message(
            f"\nResuming turn {state.current_turn} from step {done + 1}...\n", style="info"
        )

    # --- Step 1: Recovery ---
    if done < 1:
        ui.show_step_header(1, STEP_NAMES[1], state)
        recovery_events = step01_recovery.execute(state)
        _record(recovery_events)
        for ev in recovery_events:
            ui.message(f"  {ev.description}")
        _save(1)
        ui.pause("Continue")

    # --- Step 2: Repairs ---
    if done < 2:
        ui.show_step_header(2, STEP_NAMES[2], state)
        raw_spend = 0
        if state.colony.integrity < 0:
            current = state.colony.resources.raw_materials
            damage = state.colony.integrity
            max_spend = min(3, current, abs(damage))
            if max_spend > 0:
                raw_spend = ui.number(
                    f"Spend raw materials on repairs? (have {current}, damage: {damage})",
                    min_val=0, max_val=max_spend,
                )
        repair_events = step02_repairs.execute(state, raw_materials_spent=raw_spend)
        _record(repair_events)
        for ev in repair_events:
            ui.message(f"  {ev.description}")
        _save(2)
        ui.pause("Continue")

    # --- Step 3: Scout Reports ---
    if done < 3:
        ui.show_step_header(3, STEP_NAMES[3], state)
        did_discovery = execute_step03_scout(ui, state, _record)
        _save(3)

        # Scout narrative — only if a discovery roll was made
        if did_discovery:
            step3_events = [e for e in all_events if e.step == 3]
            mech_text = "\n".join(f"- {e.description}" for e in step3_events)
            narrative_text = _narrate("scout_report", modal=True)
            if narrative_text:
                combined = f"{narrative_text}\n\n---\n\n**Results:**\n{mech_text}" if mech_text else narrative_text
                ui.show_narrative_modal(combined, title="Scout Reports")
            else:
                combined = f"**Results:**\n{mech_text}" if mech_text else "No discoveries this turn."
                ui.show_narrative_modal(combined, title="Scout Reports")

    # --- Step 4: Enemy Activity ---
    if done < 4:
        ui.show_step_header(4, STEP_NAMES[4], state)
        execute_step04_enemy(ui, state, _record)
        _save(4)
        ui.pause("Continue")

    # --- Step 5: Colony Events ---
    if done < 5:
        ui.show_step_header(5, STEP_NAMES[5], state)
        ui.show_loading_modal("Colony Events")
        execute_step05_colony_events(ui, state, _record)
        _save(5)

        # Colony event narrative — blocking modal (replaces loading spinner)
        step5_events = [e for e in all_events if e.step == 5]
        mech_text = "\n".join(f"- {e.description}" for e in step5_events)
        narrative_text = _narrate("colony_event", modal=True)
        if narrative_text:
            combined = f"{narrative_text}\n\n---\n\n**Effects:**\n{mech_text}" if mech_text else narrative_text
            ui.show_narrative_modal(combined, title="Colony Events")
        else:
            combined = f"**Effects:**\n{mech_text}" if mech_text else "No colony events this turn."
            ui.show_narrative_modal(combined, title="Colony Events")

    # --- Step 6: Mission Determination ---
    if done < 6:
        ui.show_step_header(6, STEP_NAMES[6], state)
        mission_type, sector_id = execute_step06_mission(ui, state, _record)
        td["mission_type"] = mission_type.value
        td["sector_id"] = sector_id
        _save(6)
    else:
        mission_type = MissionType(td["mission_type"])
        sector_id = td.get("sector_id")

    # --- Step 7: Lock and Load ---
    if done < 7:
        ui.show_step_header(7, STEP_NAMES[7], state)
        deployed_chars, grunt_deploy, bot_deploy, civilian_deploy, weapon_loadout = execute_step07_deploy(ui, state, mission_type, _record)
        td["deployed_chars"] = deployed_chars
        td["grunt_deploy"] = grunt_deploy
        td["bot_deploy"] = bot_deploy
        td["civilian_deploy"] = civilian_deploy
        td["weapon_loadout"] = weapon_loadout
        _save(7)
    else:
        deployed_chars = td["deployed_chars"]
        grunt_deploy = td["grunt_deploy"]
        bot_deploy = td["bot_deploy"]
        civilian_deploy = td["civilian_deploy"]
        weapon_loadout = td.get("weapon_loadout", {})

    # --- Battlefield Condition ---
    from planetfall.engine.tables.battlefield_conditions import get_mission_condition
    condition = get_mission_condition(state, state.current_turn)

    if done < 8:
        ui.message(
            f"  Battlefield Condition: {condition.name} — {condition.description}",
            style="bold",
        )

        # --- Slyn interference check ---
        from planetfall.engine.campaign.slyn import check_slyn_interference
        slyn_encounter_before = state.enemies.slyn.encounters
        slyn_events = check_slyn_interference(state)
        if slyn_events:
            _record(slyn_events)
            # Dramatic reveal screen
            slyn_data = slyn_events[0].state_changes
            encounter_num = slyn_data.get("slyn_encounter", 1)
            slyn_count = slyn_data.get("slyn_count", 4)
            is_first = encounter_num == 1

            ui.message("")
            if is_first:
                ui.message("═══ UNKNOWN ALIEN CONTACT ═══", style="error")
                ui.message(
                    "\n  Warning: Unidentified alien signatures detected "
                    "in the mission area.", style="error"
                )
                ui.message(
                    f"  {slyn_count} unknown hostiles inbound. "
                    "Exercise extreme caution.", style="error"
                )
                ui.message(
                    "\n  Your team has no prior intel on this species. "
                    "Weapons and tactics unknown.", style="dim"
                )
            else:
                ui.message("═══ SLYN INTERFERENCE ═══", style="error")
                ui.message(
                    f"\n  Slyn signatures detected! "
                    f"{slyn_count} Slyn warriors moving to intercept.", style="error"
                )
                ui.message(
                    f"  Encounter #{encounter_num} with the Slyn.", style="dim"
                )
            ui.message("")
            ui.pause()

    # --- Step 8: Play Out Mission ---
    if done < 8:
        ui.show_step_header(8, STEP_NAMES[8])
        mission_victory, character_casualties, grunt_casualties = execute_step08_mission(
            ui, state, mission_type, deployed_chars, grunt_deploy, _record,
            bot_deploy, civilian_deploy, weapon_loadout=weapon_loadout,
        )
        td["mission_victory"] = mission_victory
        td["character_casualties"] = character_casualties
        td["grunt_casualties"] = grunt_casualties
        _save(8)

        # Show mission result banner
        mission_label = mission_type.value.replace("_", " ").upper()
        cas_count = len(character_casualties) + grunt_casualties
        if mission_victory:
            detail = "All objectives completed."
            if cas_count:
                detail += f" {cas_count} casualt{'y' if cas_count == 1 else 'ies'} sustained."
            ui.show_mission_result(True, f"{mission_label} — MISSION SUCCESS", detail)
        else:
            detail = "Objectives not met."
            if cas_count:
                detail += f" {cas_count} casualt{'y' if cas_count == 1 else 'ies'} sustained."
            ui.show_mission_result(False, f"{mission_label} — MISSION FAILED", detail)
    else:
        mission_victory = td["mission_victory"]
        character_casualties = td["character_casualties"]
        grunt_casualties = td["grunt_casualties"]

    # --- Step 9: Battle Results, Finds, Injuries ---
    if done < 9:
        # Page 1: Battle concluded + post-mission finds
        ui.show_step_header(8, STEP_NAMES[9], state)

        combat_result = td.get("combat_result")
        if combat_result:
            from planetfall.engine.steps import step08_mission
            combat_events = step08_mission.apply_combat_result(state, combat_result)
            _record(combat_events)

        # Mark lifeform specimen collected on successful hunt
        if mission_victory and mission_type == MissionType.HUNT:
            for lf in state.enemies.lifeform_table:
                if lf.name and not lf.specimen_collected:
                    lf.specimen_collected = True
                    _record([TurnEvent(
                        step=9, event_type=TurnEventType.MISSION,
                        description=f"Specimen collected: {lf.name}",
                    )])
                    break  # one specimen per hunt

        execute_post_mission_finds(
            ui, state, mission_victory, deployed_chars,
            character_casualties, condition, _record,
            mission_type=mission_type,
            objectives_secured=td.get("objectives_secured", 0),
        )

        # Page 2: Battle narrative — loading modal while generating
        ui.clear()
        ui.show_colony_status(state)
        ui.show_map(state)
        if _narrative_batch:
            ui.show_loading_modal("Battle Report")
            narrative_text = _narrate("battle", combat_log=td.get("combat_log"), modal=True)
            if narrative_text:
                ui.show_narrative_modal(narrative_text, title="Battle Report")
        else:
            _narrate("battle", combat_log=td.get("combat_log"))

        # Page 3: Injuries
        ui.show_step_header(9, "Injuries", state)
        injury_events = step09_injuries.execute(state, character_casualties, grunt_casualties)
        _record(injury_events)
        for ev in injury_events:
            ui.message(f"  {ev.description}")
        _save(9)
        ui.pause()

    # --- Step 10: Experience ---
    if done < 10:
        ui.show_step_header(10, STEP_NAMES[10], state)

        # Apply XP and civvy promotion once, store results for display
        if "xp_awards" not in td:
            # Build XP award details before applying
            xp_awards = []
            for char in state.characters:
                if char.name not in deployed_chars:
                    continue
                xp = 1
                reasons = ["participation"]
                if char.name not in character_casualties:
                    xp += 1
                    reasons.append("survived")
                xp_awards.append({
                    "name": char.name,
                    "xp": xp,
                    "reasons": ", ".join(reasons),
                    "total_xp": char.xp + xp,  # preview
                })

            # Apply XP
            _record(step10_experience.award_mission_xp(
                state, deployed_chars, character_casualties
            ))

            # Civvy Heroic Promotion
            civvy_promo_data = None
            promo_events, promoted, roll_total = \
                step10_experience.roll_civvy_heroic_promotion(
                    state, civilian_deploy, character_casualties,
                )
            _record(promo_events)
            if civilian_deploy > 0:
                civvy_casualties = sum(
                    1 for c in character_casualties if c.startswith("Civvy")
                )
                if civilian_deploy - civvy_casualties > 0:
                    civvy_promo_data = {
                        "promoted": promoted,
                        "roll": roll_total,
                    }

            # Persist so resume doesn't re-apply XP
            td["xp_awards"] = xp_awards
            td["civvy_promo"] = civvy_promo_data
            _save()

        xp_awards = td["xp_awards"]
        civvy_promo_data = td.get("civvy_promo")

        # Interactive experience screen loop (advancements are idempotent —
        # they deduct XP, so re-running the loop on resume is safe)
        def _build_exp_data():
            chars = []
            for c in state.characters:
                chars.append({
                    "name": c.name,
                    "char_class": c.char_class.value,
                    "reactions": c.reactions,
                    "speed": c.speed,
                    "combat_skill": c.combat_skill,
                    "toughness": c.toughness,
                    "savvy": c.savvy,
                    "xp": c.xp,
                    "kill_points": c.kill_points,
                    "loyalty": c.loyalty.value,
                    "title": c.title,
                    "role": c.role,
                })
            return {
                "xp_awards": xp_awards,
                "civvy_promotion": civvy_promo_data,
                "characters": chars,
            }

        last_advancement = None  # {character, description} for re-opening modal
        while True:
            exp_data = _build_exp_data()
            if last_advancement:
                exp_data["last_advancement"] = last_advancement
            result = ui.prompt_experience(exp_data)
            action = result.get("action", "done")
            if action == "done":
                break
            char_name = result.get("character", "")
            events = []
            if action == "roll":
                events = step10_experience.roll_advancement(state, char_name)
            elif action == "buy":
                stat = result.get("stat", "")
                events = step10_experience.buy_advancement(
                    state, char_name, stat,
                )
            elif action == "alternate":
                choice = result.get("choice", "")
                events = step10_experience.alternate_advancement(
                    state, char_name, choice,
                )
            _record(events)
            desc = events[0].description if events else "No change."
            last_advancement = {"character": char_name, "description": desc}
            _save()  # save after each advancement

        _save(10)
        ui.show_roster(state)  # refresh roster sidebar after advancements

    # --- Step 11: Morale ---
    if done < 11:
        ui.show_step_header(11, STEP_NAMES[11], state)
        execute_step11_morale(
            ui, state, mission_type, mission_victory,
            character_casualties, grunt_casualties, _record
        )
        _save(11)
        ui.pause("Continue")

    # --- Step 12: Tracking ---
    if done < 12:
        ui.show_step_header(12, STEP_NAMES[12], state)
        tracking_events = step12_tracking.execute(state, mission_type, mission_victory)
        _record(tracking_events)
        for ev in tracking_events:
            ui.message(f"  {ev.description}")
        _save(12)
        ui.pause("Continue")

        # --- Mid-turn systems (extractions, calamities, demands, SP) ---
        execute_mid_turn_systems(ui, state, mission_type, mission_victory, _record)

    # --- Step 13: Replacements ---
    if done < 13:
        ui.show_step_header(13, STEP_NAMES[13], state)
        replacement_events = step13_replacements.execute(state)
        _record(replacement_events)
        for ev in replacement_events:
            ui.message(f"  {ev.description}")
        _save(13)
        ui.pause("Continue")

    # --- Step 14: Research ---
    if done < 14:
        ui.show_step_header(14, STEP_NAMES[14], state)

        # Gain RP once, store in td to prevent double-application on resume
        if "rp_gained" not in td:
            rp_events = step14_research.execute(state)
            _record(rp_events)
            td["rp_gained"] = rp_events[0].state_changes.get("rp_gained", 0) if rp_events and rp_events[0].state_changes else 0
            _save()
        rp_gained = td["rp_gained"]

        # Interactive research spending via modal
        from planetfall.engine.steps.step14_research import get_research_options
        from planetfall.engine.campaign.research import (
            invest_in_theory, unlock_application, perform_bio_analysis,
            THEORIES, APPLICATIONS, get_available_applications,
        )

        last_action_desc = ""
        while True:
            opts = get_research_options(state)
            unlocked_apps = set(state.tech_tree.unlocked_applications)

            def _build_apps_data(tdef):
                apps_data = []
                for app_id in tdef.applications:
                    adef = APPLICATIONS.get(app_id)
                    if adef:
                        apps_data.append({
                            "name": adef.name,
                            "type": adef.app_type,
                            "description": adef.description,
                            "unlocked": app_id in unlocked_apps,
                        })
                return apps_data

            # Build theory list: incomplete theories from get_research_options
            theory_list = []
            seen_ids = set()
            for t in opts["theories"]:
                tdef = THEORIES.get(t["id"])
                theory_list.append({
                    "id": t["id"],
                    "name": t["name"],
                    "rp_cost": t["rp_cost"],
                    "app_cost": t.get("app_cost", 0),
                    "invested_rp": t["invested"].invested_rp if t["invested"] else 0,
                    "applications": _build_apps_data(tdef) if tdef else [],
                })
                seen_ids.add(t["id"])

            # Add completed theories that still have unlockable applications
            for tid, tdata in state.tech_tree.theories.items():
                if tid in seen_ids or not tdata.completed:
                    continue
                tdef = THEORIES.get(tid)
                if not tdef:
                    continue
                has_unlockable = any(
                    app_id not in unlocked_apps for app_id in tdef.applications
                )
                if has_unlockable:
                    theory_list.append({
                        "id": tid,
                        "name": tdef.name,
                        "rp_cost": tdef.rp_cost,
                        "app_cost": tdef.app_cost,
                        "invested_rp": tdef.rp_cost,  # fully invested
                        "applications": _build_apps_data(tdef),
                    })

            research_data = {
                "rp_available": opts["rp_available"],
                "rp_gained": rp_gained,
                "theories": theory_list,
                "applications": [
                    {
                        "id": a["id"],
                        "name": a["name"],
                        "theory": a["theory"],
                        "cost": a["cost"],
                        "description": a["description"],
                    }
                    for a in opts["applications"]
                ],
                "bio_specimens": opts["bio_specimens"],
                "last_action_desc": last_action_desc,
            }
            result = ui.prompt_research(research_data)
            action = result.get("action", "done")
            if action == "done":
                break

            events = []
            if action == "invest":
                theory_id = result.get("theory_id", "")
                amount = int(result.get("amount", 1))
                events = invest_in_theory(state, theory_id, amount)
            elif action == "unlock_app":
                theory_name = result.get("theory_name", "")
                avail_apps = get_available_applications(state)
                theory_apps = [a for a in avail_apps if THEORIES[a.theory_id].name == theory_name]
                if theory_apps:
                    import random
                    selected = random.choice(theory_apps)
                    events = unlock_application(state, selected.id)
            elif action == "bio_analysis":
                lifeform_name = result.get("lifeform_name", "")
                events = perform_bio_analysis(state, lifeform_name=lifeform_name)

            _record(events)
            last_action_desc = events[0].description if events else ""
        _save(14)

    # --- Step 15: Building ---
    if done < 15:
        ui.show_step_header(15, STEP_NAMES[15], state)

        # Gain BP once, guard against double-application on resume
        if "bp_gained" not in td:
            bp_events = step15_building.execute(state)
            _record(bp_events)
            td["bp_gained"] = bp_events[0].state_changes.get("bp_gained", 0) if bp_events and bp_events[0].state_changes else 0
            _save()
        bp_gained = td["bp_gained"]

        # Interactive building spending via modal
        from planetfall.engine.steps.step15_building import get_building_options
        from planetfall.engine.campaign.buildings import invest_in_building

        last_action_desc = ""
        while True:
            opts = get_building_options(state)
            building_data = {
                "bp_available": opts["bp_available"],
                "rm_available": opts["rm_available"],
                "bp_gained": bp_gained,
                "built": opts["built"],
                "available": opts["available"],
                "in_progress": opts["in_progress"],
                "last_action_desc": last_action_desc,
            }
            result = ui.prompt_building(building_data)
            action = result.get("action", "done")
            if action == "done":
                break

            events = []
            if action == "build":
                building_id = result.get("building_id", "")
                bp_amount = int(result.get("bp_amount", 0))
                rm_convert = int(result.get("rm_convert", 0))
                events = invest_in_building(state, building_id, bp_amount, rm_convert)
            elif action == "convert":
                rm_amount = int(result.get("rm_amount", 0))
                rm_amount = min(rm_amount, state.colony.resources.raw_materials)
                if rm_amount > 0:
                    state.colony.resources.raw_materials -= rm_amount
                    bp_from_rm = rm_amount // 3
                    state.colony.resources.build_points += bp_from_rm
                    events = [TurnEvent(
                        step=15, event_type=TurnEventType.BUILDING,
                        description=f"Converted {rm_amount} Raw Materials into {bp_from_rm} Build Points.",
                    )]

            _record(events)
            last_action_desc = events[0].description if events else ""
            _save()
        _save(15)

        # --- Augmentation opportunity ---
        execute_augmentation_opportunity(ui, state, _record)

    # --- Step 16: Colony Integrity ---
    if done < 16:
        ui.show_step_header(16, STEP_NAMES[16], state)
        execute_step16_integrity(ui, state, _record)
        _save(16)
        ui.pause("Continue")

    # --- Step 17: Character Event ---
    if done < 17:
        ui.show_step_header(17, STEP_NAMES[17], state)
        ui.show_loading_modal("Character Event")
        char_events = step17_character_event.execute(state, last_mission_victory=mission_victory)
        _record(char_events)
        # Build event summary for the narrative modal
        event_summary = "\n".join(ev.description for ev in char_events)
        _save(17)

        # Character event narrative — blocking modal (replaces loading spinner)
        narrative_text = _narrate("character_event", modal=True)
        if narrative_text:
            combined = f"**{event_summary}**\n\n---\n\n{narrative_text}"
            ui.show_narrative_modal(combined, title="Character Event")
        else:
            ui.show_narrative_modal(f"**{event_summary}**", title="Character Event")

    # --- Step 18: Update Sheet ---
    if done < 18:
        ui.show_step_header(18, STEP_NAMES[18], state)
        ui.show_loading_modal("Colony Log")
        update_events = step18_update_sheet.execute(state)
        _record(update_events)

        # Turn-end narrative — blocking modal (replaces loading spinner)
        narrative_text = _narrate("turn_end", modal=True)
        if narrative_text:
            ui.show_narrative_modal(narrative_text, title="Colony Log")

        # Show colony status, map, roster after closing narrative
        ui.show_colony_status(state)
        ui.show_map(state)
        ui.show_roster(state)

    # Reset step tracking for next turn
    state.current_step = 0
    state.turn_data = {}
    _save()

    # Show API usage summary
    from planetfall.api_tracker import get_tracker
    tracker = get_tracker()
    if tracker.call_count > 0:
        ui.message(f"\n{tracker.summary()}", style="dim")

    return state


# --- Public API ---

def run_campaign_turn(state: GameState, api_key: str = "") -> GameState:
    """Run a campaign turn — routes based on ORCHESTRATOR_MODE config.

    Modes:
        api:    Claude drives all 18 steps via tool_use (richest narrative, slowest).
        hybrid: Local mechanics + Claude API narrative at key moments (default).
        local:  Pure Python, template narrative, zero API calls (fastest).
    """
    from planetfall.config import get_orchestrator_mode, get_api_key

    mode = get_orchestrator_mode()

    if mode == "api":
        return run_campaign_turn_api(state, api_key)
    elif mode == "hybrid":
        has_key = bool(api_key or get_api_key())
        return run_campaign_turn_local(state, use_narrative_api=has_key)
    else:  # local
        return run_campaign_turn_local(state, use_narrative_api=False)

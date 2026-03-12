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
    from planetfall.cli import display, prompts
    from planetfall.narrative import generate_narrative_local, generate_narrative_api
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
        display.print_events(evts)

    def _narrate(context: str, combat_log: list[str] | None = None) -> None:
        """Generate and display narrative for batched events, then clear batch."""
        if not _narrative_batch:
            return
        if use_narrative_api and api_key:
            text = generate_narrative_api(
                state, _narrative_batch, context,
                api_key=api_key, model=narrative_model,
                combat_log=combat_log,
            )
        else:
            text = generate_narrative_local(state, _narrative_batch, context)
        display.console.print(f"\n[italic]{text}[/italic]")
        # Save narrative prose to turn log so it persists in save files
        state.turn_log.append(TurnEvent(
            event_type=TurnEventType.NARRATIVE,
            description=text,
        ))
        _narrative_batch.clear()

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
        display.console.print(
            f"\n[bold cyan]Resuming turn {state.current_turn} from step {done + 1}...[/bold cyan]\n"
        )

    # --- Step 1: Recovery ---
    if done < 1:
        display.print_step_header(1, STEP_NAMES[1], state)
        _record(step01_recovery.execute(state))
        _save(1)

    # --- Step 2: Repairs ---
    if done < 2:
        display.print_step_header(2, STEP_NAMES[2], state)
        raw_spend = 0
        if state.colony.integrity < 0:
            raw_spend = prompts.prompt_raw_materials_repair(
                state.colony.resources.raw_materials, state.colony.integrity,
            )
        _record(step02_repairs.execute(state, raw_materials_spent=raw_spend))
        _save(2)

    # --- Step 3: Scout Reports ---
    if done < 3:
        display.print_step_header(3, STEP_NAMES[3], state)
        execute_step03_scout(state, _record)
        _save(3)

    # --- Step 4: Enemy Activity ---
    if done < 4:
        display.print_step_header(4, STEP_NAMES[4], state)
        execute_step04_enemy(state, _record)
        _save(4)

    # --- Step 5: Colony Events ---
    if done < 5:
        display.print_step_header(5, STEP_NAMES[5], state)
        execute_step05_colony_events(state, _record)
        _save(5)

        if _narrative_batch:
            display.console.print("\n  [dim italic]Generating narrative...[/dim italic]")
        _narrate("colony_event")

    # --- Step 6: Mission Determination ---
    if done < 6:
        display.print_step_header(6, STEP_NAMES[6], state)
        mission_type, sector_id = execute_step06_mission(state, _record)
        td["mission_type"] = mission_type.value
        td["sector_id"] = sector_id
        _save(6)
    else:
        mission_type = MissionType(td["mission_type"])
        sector_id = td.get("sector_id")

    # --- Step 7: Lock and Load ---
    if done < 7:
        display.print_step_header(7, STEP_NAMES[7], state)
        deployed_chars, grunt_deploy, bot_deploy, civilian_deploy, weapon_loadout = execute_step07_deploy(state, mission_type, _record)
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
        display.console.print(
            f"  [bold]Battlefield Condition:[/bold] {condition.name} — {condition.description}"
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

            display.console.print()
            if is_first:
                display.console.print(
                    "[bold red]═══ UNKNOWN ALIEN CONTACT ═══[/bold red]"
                )
                display.console.print(
                    "\n  [red]Warning: Unidentified alien signatures detected "
                    "in the mission area.[/red]"
                )
                display.console.print(
                    f"  [red]{slyn_count} unknown hostiles inbound. "
                    "Exercise extreme caution.[/red]"
                )
                display.console.print(
                    "\n  [dim]Your team has no prior intel on this species. "
                    "Weapons and tactics unknown.[/dim]"
                )
            else:
                display.console.print(
                    "[bold red]═══ SLYN INTERFERENCE ═══[/bold red]"
                )
                display.console.print(
                    f"\n  [red]Slyn signatures detected! "
                    f"{slyn_count} Slyn warriors moving to intercept.[/red]"
                )
                display.console.print(
                    f"  [dim]Encounter #{encounter_num} with the Slyn.[/dim]"
                )
            display.console.print()
            prompts.pause()

    # --- Step 8: Play Out Mission ---
    if done < 8:
        display.print_step_header(8, STEP_NAMES[8])
        mission_victory, character_casualties, grunt_casualties = execute_step08_mission(
            state, mission_type, deployed_chars, grunt_deploy, _record,
            bot_deploy, civilian_deploy, weapon_loadout=weapon_loadout,
        )
        td["mission_victory"] = mission_victory
        td["character_casualties"] = character_casualties
        td["grunt_casualties"] = grunt_casualties
        _save(8)
    else:
        mission_victory = td["mission_victory"]
        character_casualties = td["character_casualties"]
        grunt_casualties = td["grunt_casualties"]

    # --- Step 9: Battle Results, Finds, Injuries ---
    if done < 9:
        # Page 1: Battle concluded + post-mission finds
        display.print_step_header(8, STEP_NAMES[9], state)

        combat_result = td.get("combat_result")
        if combat_result:
            from planetfall.engine.steps import step08_mission
            combat_events = step08_mission.apply_combat_result(state, combat_result)
            _record(combat_events)

        execute_post_mission_finds(
            state, mission_victory, deployed_chars,
            character_casualties, condition, _record,
            mission_type=mission_type,
            objectives_secured=td.get("objectives_secured", 0),
        )

        # Page 2: Injuries (print_step_header pauses + clears before showing)
        display.print_step_header(9, "Injuries", state)
        _record(step09_injuries.execute(state, character_casualties, grunt_casualties))
        _save(9)
        prompts.pause()

        # Page 3: Narrative
        display.clear_screen()
        display.print_colony_status(state)
        display.print_map(state)
        if _narrative_batch:
            display.console.print("\n  [dim italic]Generating narrative...[/dim italic]")
        _narrate("battle", combat_log=td.get("combat_log"))

    # --- Step 10: Experience ---
    if done < 10:
        display.print_step_header(10, STEP_NAMES[10], state)
        _record(step10_experience.award_mission_xp(
            state, deployed_chars, character_casualties
        ))
        for char in state.characters:
            while char.xp >= 5:
                if prompts.ask_confirm(
                    f"{char.name} has {char.xp} XP. Spend 5 for advancement?"
                ):
                    _record(step10_experience.roll_advancement(state, char.name))
                else:
                    break
        _save(10)

    # --- Step 11: Morale ---
    if done < 11:
        display.print_step_header(11, STEP_NAMES[11], state)
        execute_step11_morale(
            state, mission_type, mission_victory,
            character_casualties, grunt_casualties, _record
        )
        _save(11)

    # --- Step 12: Tracking ---
    if done < 12:
        display.print_step_header(12, STEP_NAMES[12], state)
        _record(step12_tracking.execute(state, mission_type, mission_victory))
        _save(12)

        # --- Mid-turn systems (extractions, calamities, demands, SP) ---
        execute_mid_turn_systems(state, mission_type, mission_victory, _record)

    # --- Step 13: Replacements ---
    if done < 13:
        display.print_step_header(13, STEP_NAMES[13], state)
        _record(step13_replacements.execute(state))
        _save(13)

    # --- Step 14: Research ---
    if done < 14:
        display.print_step_header(14, STEP_NAMES[14], state)
        # Gain RP first (no spending args)
        _record(step14_research.execute(state))
        # Offer interactive spending
        from planetfall.orchestrator_steps import prompt_research_spending
        prompt_research_spending(state, _record)
        _save(14)

    # --- Step 15: Building ---
    if done < 15:
        display.print_step_header(15, STEP_NAMES[15], state)
        # Gain BP first (no spending args)
        _record(step15_building.execute(state))
        # Offer interactive spending
        from planetfall.orchestrator_steps import prompt_building_spending
        prompt_building_spending(state, _record)
        _save(15)

        # --- Augmentation opportunity ---
        execute_augmentation_opportunity(state, _record)

    # --- Step 16: Colony Integrity ---
    if done < 16:
        display.print_step_header(16, STEP_NAMES[16], state)
        execute_step16_integrity(state, _record)
        _save(16)

    # --- Step 17: Character Event ---
    if done < 17:
        display.print_step_header(17, STEP_NAMES[17], state)
        _record(step17_character_event.execute(state, last_mission_victory=mission_victory))
        _save(17)

        _narrate("character_event")

    # --- Step 18: Update Sheet ---
    if done < 18:
        display.print_step_header(18, STEP_NAMES[18], state)
        display.print_roster(state)
        _record(step18_update_sheet.execute(state))

        _narrate("turn_end")
        prompts.pause()

    display.print_turn_summary(all_events)

    # Reset step tracking for next turn
    state.current_step = 0
    state.turn_data = {}
    _save()

    # Show API usage summary
    from planetfall.api_tracker import get_tracker
    tracker = get_tracker()
    if tracker.call_count > 0:
        display.console.print(f"\n{tracker.summary()}")

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

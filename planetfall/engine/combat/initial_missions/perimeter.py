"""Perimeter (Trooper) initial mission — kill 6 melee lifeforms using full combat."""

from __future__ import annotations

from typing import Any

from planetfall.engine.combat.battlefield import (
    Battlefield, Figure, FigureSide,
    generate_random_terrain, GRID_SMALL,
)
from planetfall.engine.combat.missions import MissionSetup, _create_player_figure
from planetfall.engine.combat.session import CombatSession, CombatPhase
from planetfall.engine.models import GameState, MissionType, CharacterClass

from planetfall.engine.combat.initial_missions.base import _get_chars_by_class


# ---------------------------------------------------------------------------
# Perimeter Mission (Trooper) — uses full combat session
# ---------------------------------------------------------------------------

def _setup_perimeter(state: GameState) -> MissionSetup:
    """Set up the Perimeter mission — full combat with 6 melee lifeforms."""
    rows, cols = GRID_SMALL
    zones = generate_random_terrain(rows, cols)
    bf = Battlefield(zones=zones, rows=rows, cols=cols)

    # Deploy troopers — they can set up anywhere, we'll let the player choose later
    # For now place them at center-bottom area
    troopers = _get_chars_by_class(state, CharacterClass.TROOPER)
    player_row = rows - 1
    for i, char in enumerate(troopers):
        col = min(i + 1, cols - 1)
        fig = _create_player_figure(
            name=char.name,
            char_class="trooper",
            speed=char.speed,
            combat_skill=char.combat_skill,
            toughness=char.toughness,
            reactions=char.reactions,
            savvy=char.savvy,
            weapon_name="Trooper Rifle",
            weapon_range=30,
            weapon_shots=1,
            weapon_damage=0,
            weapon_traits=["trooper", "ap_ammo"],
            zone=(player_row, col),
        )
        bf.figures.append(fig)

    # Deploy 6 lifeforms on random edge (top edge = row 0)
    enemy_edge = 0
    for i in range(6):
        col = i % cols
        fig = Figure(
            name=f"Lifeform {i + 1}",
            side=FigureSide.ENEMY,
            zone=(enemy_edge, col),
            speed=5,
            combat_skill=1,
            toughness=4,
            melee_damage=0,  # +0 Damage
            weapon_name="Claws",
            weapon_range=0,  # melee only
            weapon_shots=0,
            weapon_damage=0,
            weapon_traits=[],
            panic_range=0,  # not subject to panic
            char_class="lifeform",
            special_rules=["no_panic"],
        )
        bf.figures.append(fig)

    setup = MissionSetup(
        mission_type=MissionType.HUNT,  # closest existing type
        battlefield=bf,
        max_rounds=8,
        victory_conditions=["Kill all 6 lifeforms"],
        defeat_conditions=["All troopers eliminated"],
        special_rules=[
            "Lifeforms move directly toward nearest trooper for brawling",
            "Lifeforms: Speed 5\", CS +1, Toughness 4, +0 Damage (melee)",
            "No injury rolls for casualties in this tutorial mission",
        ],
        enemy_type="lifeform",
    )
    return setup


def run_perimeter(state: GameState) -> dict:
    """Run the Perimeter (Trooper) mission using full combat session.

    Returns {"victory": bool, "log": list[str]}.
    """
    from planetfall.engine.combat.battlefield import FigureSide
    from planetfall.cli import display, prompts
    from planetfall.engine.models import TurnEvent, TurnEventType

    troopers = _get_chars_by_class(state, CharacterClass.TROOPER)
    if not troopers:
        display.console.print("[red]No troopers on roster! Cannot play Perimeter mission.[/red]")
        return {"victory": False, "log": ["No troopers available"]}

    display.console.print("\n[bold cyan]═══ PERIMETER — Trooper Mission ═══[/bold cyan]")
    display.console.print(
        "\n  Troopers must kill all 6 lifeforms heading toward the drop site."
        "\n  Each trooper is armed with a standard Trooper Rifle."
        "\n  Lifeforms: Speed 5\", CS +1, Toughness 4, +0 Damage (brawling)."
        "\n  Full combat rules apply — this is your combat tutorial.\n"
    )

    mission_setup = _setup_perimeter(state)
    bf = mission_setup.battlefield

    # Let player choose deployment zones
    player_figs = [f for f in bf.figures if f.side == FigureSide.PLAYER]
    available_zones = [
        (r, c) for r in range(bf.rows) for c in range(bf.cols)
    ]  # Can set up anywhere

    display.reset_enemy_labels()
    display.print_battlefield(bf, title="Perimeter — Deployment")

    # Show special rules
    display.console.print("[bold yellow]Special Rules:[/bold yellow]")
    for rule in mission_setup.special_rules:
        display.console.print(f"  [yellow]• {rule}[/yellow]")
    display.console.print()

    zone_assignments = prompts.prompt_deployment_zones(
        [f.name for f in player_figs],
        available_zones,
    )
    for fig in player_figs:
        if fig.name in zone_assignments:
            fig.zone = zone_assignments[fig.name]

    # Run full combat session
    session = CombatSession(mission_setup)
    combat_state = session.start_battle()
    display.print_battlefield(session.bf)

    prev_log_len = 0
    log = []

    while combat_state.phase.value != "battle_over":
        current_phase = combat_state.phase.value

        if current_phase == "reaction_roll":
            display.clear_screen()
            display.print_battlefield(session.bf)
            display.print_combat_phase(current_phase, combat_state.round_number)

            display.console.print(
                f"\n  [bold]Reaction Dice:[/bold] {combat_state.unassigned_dice}"
            )
            for name, react in combat_state.reaction_figures:
                display.console.print(f"    {name} (Reactions {react})")

            assignments = prompts.prompt_reaction_assignment(
                combat_state.unassigned_dice,
                combat_state.reaction_figures,
            )
            combat_state = session.assign_reactions(assignments)

            if combat_state.reaction_result:
                display.print_reaction_roll(combat_state.reaction_result)
                prompts.pause()

            prev_log_len = len(combat_state.phase_log)
            continue

        if combat_state.available_actions:
            active_fig = next(
                (f for f in session.bf.figures
                 if f.name == combat_state.current_figure),
                None,
            )

            overlay_modes_p = [
                display.OVERLAY_VISION, display.OVERLAY_MOVEMENT,
                display.OVERLAY_SHOOTING,
            ]
            overlay_names_p = ["Vision", "Movement", "Shooting"]
            overlay_idx_p = 0
            action_descs = [a["description"] for a in combat_state.available_actions]

            while True:
                display.clear_screen()
                display.print_battlefield(
                    session.bf, active_fig=active_fig,
                    overlay_mode=overlay_modes_p[overlay_idx_p],
                )
                display.print_combat_phase(current_phase, combat_state.round_number)

                new_entries = combat_state.phase_log[prev_log_len:]
                if new_entries:
                    display.print_combat_log(new_entries)

                display.console.print(
                    f"\n  [bold]Current figure: {combat_state.current_figure}[/bold]"
                )

                next_name_p = overlay_names_p[(overlay_idx_p + 1) % len(overlay_names_p)]
                cycle_label_p = f"[Overlay: {overlay_names_p[overlay_idx_p]} → {next_name_p}]"
                all_choices = action_descs + [cycle_label_p]
                choice = prompts.ask_select("Choose action:", all_choices)
                if choice == cycle_label_p:
                    overlay_idx_p = (overlay_idx_p + 1) % len(overlay_modes_p)
                    continue
                break

            action_idx = action_descs.index(choice)
            combat_state = session.choose_action(action_idx)

            new_log = combat_state.phase_log[prev_log_len:]
            if new_log:
                display.clear_screen()
                display.print_battlefield(session.bf)
                display.print_combat_phase(current_phase, combat_state.round_number)
                display.print_combat_log(new_log)
                prompts.pause()
            prev_log_len = len(combat_state.phase_log)

        elif current_phase == "enemy_phase":
            display.clear_screen()
            display.print_battlefield(session.bf)
            display.print_combat_phase(current_phase, combat_state.round_number)

            while combat_state.phase.value == "enemy_phase":
                pre_step_len = len(combat_state.phase_log)
                combat_state = session.advance_enemy_step()
                new_log = combat_state.phase_log[pre_step_len:]
                substantive = [l for l in new_log if not l.startswith("---") and not l.startswith("===")]
                if substantive:
                    display.clear_screen()
                    display.print_battlefield(session.bf)
                    display.print_combat_phase(current_phase, combat_state.round_number)
                    display.print_combat_log(substantive)
                    prompts.pause()

            prev_log_len = len(combat_state.phase_log)
        else:
            pre_len = len(combat_state.phase_log)
            combat_state = session.advance()
            new_log = combat_state.phase_log[pre_len:]
            substantive = [l for l in new_log if not l.startswith("---") and not l.startswith("===")]
            if substantive:
                display.clear_screen()
                display.print_battlefield(session.bf)
                display.print_combat_phase(combat_state.phase.value, combat_state.round_number)
                display.print_combat_log(substantive)
                prompts.pause()
            prev_log_len = len(combat_state.phase_log)

    final_result = session.get_result()
    victory = final_result.get("victory", False)

    display.clear_screen()
    if victory:
        display.console.print("\n[bold green]═══ PERIMETER — MISSION SUCCESS ═══[/bold green]")
        display.console.print("  All 6 lifeforms eliminated! +3 Colony Morale bonus.")
    else:
        display.console.print("\n[bold red]═══ PERIMETER — MISSION FAILED ═══[/bold red]")
        display.console.print("  Troopers evacuated. A grunt squad clears the site. No bonus.")
    prompts.pause()

    return {"victory": victory, "log": log}


def run_perimeter_ui(state: GameState, ui: Any) -> dict:
    """Run the Perimeter (Trooper) mission using a UIAdapter and full combat session.

    Returns {"victory": bool, "log": list[str]}.
    """
    from planetfall.engine.combat.battlefield import FigureSide

    troopers = _get_chars_by_class(state, CharacterClass.TROOPER)
    if not troopers:
        ui.message("No troopers on roster! Cannot play Perimeter mission.", style="error")
        return {"victory": False, "log": ["No troopers available"]}

    # Mission intro modal
    ui.show_mission_intro({
        "title": "Perimeter (Trooper Mission)",
        "subtitle": "Initial Landing Mission 3 of 3",
        "sections": [
            {"heading": "", "body": (
                "The third landing is by the troopers of the team, establishing a defensive "
                "perimeter as hostile Lifeforms are rapidly headed towards your drop site."
            )},
            {"heading": "Setup", "body": (
                "◆ Set up any troopers from your roster. Each is armed with the standard "
                "trooper rifle from the Armory. You may set up anywhere on your deployment edge.\n"
                "◆ After setting up, 6 Lifeform miniatures are placed along a randomly selected "
                "battlefield edge."
            )},
            {"heading": "Objective", "body": (
                "You must kill all 6 to complete the mission."
            )},
            {"heading": "Obstacles", "body": (
                "The Lifeforms move 5\" per action, have a +1 Combat Skill and Toughness 4. "
                "They will move as directly as possible to attack you in brawling combat and "
                "will strike with +0 Damage if they do.\n"
                "They are not subject to Panic tests."
            )},
            {"heading": "Reward", "body": (
                "Killing all 6 Lifeforms earns you +3 Colony Morale to begin the campaign.\n"
                "If you fail the mission, your troopers are evacuated, and a squad of grunts "
                "clears up the site. You may proceed to Campaign Setup in both cases."
            )},
        ],
    })

    mission_setup = _setup_perimeter(state)
    bf = mission_setup.battlefield

    # Hide player figures for deployment
    player_figs = [f for f in bf.figures if f.side == FigureSide.PLAYER]
    for f in player_figs:
        bf.figures.remove(f)

    # Show mission briefing (persistent info panel)
    ui.reset_enemy_labels()
    ui.show_mission_briefing(
        bf,
        mission_type="Perimeter",
        enemy_info=[
            "6 melee lifeforms approaching from the north",
            "Lifeforms: Speed 5\", CS +1, Toughness 4, +0 Damage (brawling)",
        ],
        special_rules=[],
        victory_conditions=list(mission_setup.victory_conditions),
        defeat_conditions=list(mission_setup.defeat_conditions),
        enemy_type=mission_setup.enemy_type,
    )

    # Deployment — player places troopers
    ui.show_combat_phase("deployment", 0)
    player_row = bf.rows - 1
    available_zones = [(player_row, c) for c in range(bf.cols)]
    ui.prompt_deployment_zones(bf, player_figs, available_zones)

    # Run full combat session
    session = CombatSession(mission_setup)
    combat_state = session.start_battle()

    ui.reset_enemy_labels()
    ui.show_battlefield(session.bf)

    prev_log_len = 0

    # Import the combat helpers from orchestrator_steps
    from planetfall.orchestrator_steps import _handle_player_turn

    while combat_state.phase.value != "battle_over":
        current_phase = combat_state.phase.value

        if current_phase == "reaction_roll":
            ui.clear()
            ui.show_combat_phase(current_phase, combat_state.round_number)
            ui.show_battlefield(session.bf)

            assignments = ui.prompt_reaction_assignment(
                combat_state.unassigned_dice,
                combat_state.reaction_figures,
            )
            combat_state = session.assign_reactions(assignments)
            prev_log_len = len(combat_state.phase_log)
            continue

        if combat_state.available_actions:
            # Player activation — reuse orchestrator combat handler
            queue = session.get_activation_queue()
            if len(queue) > 1:
                valid = [
                    n for n in queue
                    if (f := session.bf.get_figure_by_name(n))
                    and f.is_alive and not f.has_acted
                ]
                if len(valid) > 1:
                    from planetfall.cli.display import get_figure_map_label
                    fig_choices = []
                    for n in valid:
                        f = session.bf.get_figure_by_name(n)
                        label = get_figure_map_label(f)
                        cls = f.char_class.title() if f.char_class else ""
                        fig_choices.append(f"{n} ({label}) — {cls}")

                    ui.clear()
                    ui.show_combat_phase(current_phase, combat_state.round_number)
                    ui.show_battlefield(session.bf)
                    chosen = ui.select("Activate which figure?", fig_choices)
                    chosen_name = chosen.split(" (")[0]
                    if chosen_name != queue[0]:
                        session.set_next_figure(chosen_name)
                        combat_state = session._snapshot()

            combat_state, prev_log_len = _handle_player_turn(
                ui, session, combat_state, prev_log_len,
            )

        elif current_phase == "enemy_phase":
            ui.clear()
            ui.show_combat_phase(current_phase, combat_state.round_number)
            ui.show_battlefield(session.bf)

            while combat_state.phase.value == "enemy_phase":
                pre_step_len = len(combat_state.phase_log)
                combat_state = session.advance_enemy_step()
                new_log = combat_state.phase_log[pre_step_len:]
                substantive = [
                    entry for entry in new_log
                    if not entry.startswith("---") and not entry.startswith("===")
                ]
                if substantive:
                    ui.clear()
                    ui.show_combat_phase(current_phase, combat_state.round_number)
                    ui.show_battlefield(session.bf)
                    ui.show_combat_log(substantive)
                    if combat_state.phase.value != "battle_over":
                        ui.pause()

            prev_log_len = len(combat_state.phase_log)

        else:
            # Auto-advance (end phase, etc.)
            advancing_from = current_phase
            pre_len = len(combat_state.phase_log)
            combat_state = session.advance()
            new_log = combat_state.phase_log[pre_len:]
            substantive = [
                entry for entry in new_log
                if not entry.startswith("---") and not entry.startswith("===")
            ]

            # Always show End Phase with phase tracker
            if advancing_from in ("slow_actions", "quick_actions"):
                ui.clear()
                ui.show_combat_phase("end_phase", combat_state.round_number)
                ui.show_battlefield(session.bf)
                if substantive:
                    ui.show_combat_log(substantive)
                if combat_state.phase.value != "battle_over":
                    ui.pause()
            elif substantive:
                ui.clear()
                ui.show_combat_phase(
                    combat_state.phase.value, combat_state.round_number,
                )
                ui.show_battlefield(session.bf)
                ui.show_combat_log(substantive)
                if combat_state.phase.value != "battle_over":
                    ui.pause()
            prev_log_len = len(combat_state.phase_log)

    final_result = session.get_result()
    victory = final_result.get("victory", False)

    ui.show_battlefield(session.bf)
    if victory:
        ui.show_mission_result(
            success=True,
            title="PERIMETER — MISSION SUCCESS",
            detail="All 6 lifeforms eliminated! +3 Colony Morale bonus.",
        )
    else:
        ui.show_mission_result(
            success=False,
            title="PERIMETER — MISSION FAILED",
            detail="Troopers evacuated. A grunt squad clears the site. No bonus.",
        )

    return {"victory": victory, "log": final_result.get("log", [])}

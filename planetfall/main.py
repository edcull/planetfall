"""Planetfall — Main entry point.

Run with: python -m planetfall.main
"""

from __future__ import annotations

import sys

from planetfall.cli import display, prompts
from planetfall.config import get_api_key
from planetfall.engine.campaign.setup import create_new_campaign, import_character
from planetfall.engine.models import CharacterClass, ColonizationAgenda, SubSpecies
from planetfall.engine.persistence import (
    list_campaigns, load_state, save_state,
    get_campaign_info, delete_campaign, copy_campaign, rename_campaign,
    list_snapshots, _campaign_dir,
)
from planetfall.orchestrator import run_campaign_turn
from planetfall.engine.utils import format_display


def setup_new_campaign():
    """Interactive campaign setup."""
    display.console.print("[bold]New Campaign Setup[/bold]\n")

    colony_name = prompts.prompt_colony_name()
    campaign_name = colony_name
    admin_name = prompts.prompt_admin_name()

    # Colonization agenda
    agenda = prompts.prompt_colonization_agenda()

    # Character creation
    display.console.print("\n[bold]Character Creation[/bold]")

    creation_mode = prompts.ask_select(
        "How do you want to create your crew?",
        [
            "Default roster (roll backgrounds) — 2 Scientists, 2 Scouts, 4 Troopers",
            "Custom roster (roll backgrounds) — choose class/experience for each",
            "Import existing — choose class, motivation, and experience for each",
        ],
    )

    character_specs = []
    imported_characters = []

    if creation_mode.startswith("Default"):
        class_layout = [
            (CharacterClass.SCIENTIST, True),
            (CharacterClass.SCIENTIST, False),
            (CharacterClass.SCOUT, True),
            (CharacterClass.SCOUT, False),
            (CharacterClass.TROOPER, True),
            (CharacterClass.TROOPER, True),
            (CharacterClass.TROOPER, False),
            (CharacterClass.TROOPER, False),
        ]
        for i, (cls, experienced) in enumerate(class_layout, 1):
            exp_tag = " (experienced)" if experienced else ""
            name = prompts.ask_text(
                f"{cls.value.title()}{exp_tag} name:",
                default=f"{cls.value.title()} {i}",
            )

            sub_species = SubSpecies.STANDARD
            if i in (1, 3, 5):
                if prompts.ask_confirm("Choose sub-species?", default=False):
                    sub_species = prompts.prompt_character_subspecies()

            character_specs.append({
                "name": name,
                "class": cls,
                "experienced": experienced,
                "sub_species": sub_species,
            })

    elif creation_mode.startswith("Custom"):
        display.console.print(
            "[dim]Create 8 characters. Choose class and experience for each.[/dim]"
        )
        for i in range(1, 9):
            display.console.print(f"\n[cyan]Character {i}/8[/cyan]")
            name = prompts.ask_text(f"Name:")
            cls_choice = prompts.ask_select(
                "Class:",
                ["Scientist", "Scout", "Trooper"],
            )
            cls = CharacterClass(cls_choice.lower())
            experienced = prompts.ask_confirm("Experienced?", default=i <= 4)

            sub_species = SubSpecies.STANDARD
            if prompts.ask_confirm("Choose sub-species?", default=False):
                sub_species = prompts.prompt_character_subspecies()

            character_specs.append({
                "name": name,
                "class": cls,
                "experienced": experienced,
                "sub_species": sub_species,
            })

    else:  # Import existing
        display.console.print(
            "\n[dim]Create 1-8 characters using class templates. "
            "Select motivation and experience for each.[/dim]"
        )
        for i in range(1, 9):
            if i > 1:
                if not prompts.ask_confirm(f"Add character {i}?", default=i <= 8):
                    break
            spec = prompts.prompt_import_character(i)
            imported_characters.append(
                import_character(
                    name=spec["name"],
                    char_class=spec["class"],
                    reactions=spec["reactions"],
                    speed=spec["speed"],
                    combat_skill=spec["combat_skill"],
                    toughness=spec["toughness"],
                    savvy=spec["savvy"],
                    xp=spec["xp"],
                    kill_points=spec["kill_points"],
                    loyalty=spec["loyalty"],
                    sub_species=spec["sub_species"],
                    title=spec.get("title", ""),
                    role=spec.get("role", ""),
                    motivation=spec["motivation"],
                    prior_experience=spec["prior_experience"],
                    narrative_background=spec.get("narrative_background", ""),
                )
            )

    # Create the campaign
    api_key = get_api_key()
    if api_key:
        display.console.print(
            "\n[dim]Generating campaign with AI narrative backgrounds...[/dim]"
        )
    else:
        display.console.print("\n[dim]Generating campaign...[/dim]")

    if imported_characters:
        # Use import path — create campaign then replace characters
        state = create_new_campaign(
            campaign_name=campaign_name,
            colony_name=colony_name,
            agenda=agenda,
            character_specs=None,  # will be overridden
            admin_name=admin_name,
            api_key=api_key,
        )
        state.characters = imported_characters
        # Generate backgrounds for imported characters that don't have one
        from planetfall.engine.campaign.setup import generate_character_backgrounds_api
        needs_bg = [c for c in state.characters if not c.narrative_background]
        if needs_bg:
            generate_character_backgrounds_api(
                state.characters, agenda, colony_name, api_key=api_key,
            )
    else:
        state = create_new_campaign(
            campaign_name=campaign_name,
            colony_name=colony_name,
            agenda=agenda,
            character_specs=character_specs,
            admin_name=admin_name,
            api_key=api_key,
        )

    # Generate colony description (after backgrounds exist for full context)
    if not state.colony.description:
        from planetfall.engine.campaign.setup.backgrounds import generate_colony_description
        state.colony.description = generate_colony_description(state, api_key=api_key)

    # Page 1: Character backgrounds
    display.clear_screen()
    display.print_character_backgrounds(state)
    prompts.pause()

    # Page 2: Colony overview
    display.clear_screen()
    from planetfall.engine.campaign.setup import AGENDA_EFFECTS
    agenda_desc = AGENDA_EFFECTS[state.settings.colonization_agenda]["description"]
    display.console.print(f"\n[bold green]Colonization Agenda:[/bold green] {agenda_desc}")
    display.console.print(
        f"[bold green]Administrator:[/bold green] {state.administrator.name} "
        f"({state.administrator.past_history})"
    )

    display.print_colony_status(state)
    display.print_roster(state)
    display.print_map(state)

    # Save
    save_state(state)
    from planetfall.engine.campaign_log import save_day_zero_log
    save_day_zero_log(state)
    display.console.print(f"\n[green]Campaign saved![/green]")
    prompts.pause()

    return state


def manage_saves():
    """Save slot management menu."""
    while True:
        display.clear_screen()
        display.print_title()
        campaigns = list_campaigns()
        if not campaigns:
            display.console.print("  [dim]No saved campaigns.[/dim]")
            return

        # Show campaign info
        display.console.print("[bold]Saved Campaigns[/bold]")
        for name in campaigns:
            info = get_campaign_info(name)
            if info["exists"]:
                display.console.print(
                    f"  [cyan]{name}[/cyan] — "
                    f"Turn {info['turn']}, "
                    f"{info['characters']} characters, "
                    f"{info['snapshots']} snapshots, "
                    f"{info['total_size_kb']} KB"
                )

        choices = [
            "Back to main menu",
            "Duplicate a campaign",
            "Rename a campaign",
            "Delete a campaign",
        ]
        choice = prompts.ask_select("Save management:", choices)

        if choice == "Back to main menu":
            return
        elif choice == "Duplicate a campaign":
            source = prompts.ask_select("Which campaign to duplicate?", campaigns)
            dest = prompts.ask_text("New campaign name:")
            try:
                copy_campaign(source, dest)
                display.console.print(f"  [green]Duplicated '{source}' as '{dest}'[/green]")
            except (FileExistsError, FileNotFoundError) as e:
                display.console.print(f"  [red]{e}[/red]")
        elif choice == "Rename a campaign":
            source = prompts.ask_select("Which campaign to rename?", campaigns)
            new_name = prompts.ask_text("New name:")
            try:
                rename_campaign(source, new_name)
                display.console.print(f"  [green]Renamed '{source}' to '{new_name}'[/green]")
            except (FileExistsError, FileNotFoundError) as e:
                display.console.print(f"  [red]{e}[/red]")
        elif choice == "Delete a campaign":
            target = prompts.ask_select("Which campaign to DELETE?", campaigns)
            if prompts.ask_confirm(f"Really delete '{target}'? This cannot be undone!", default=False):
                delete_campaign(target)
                display.console.print(f"  [red]Deleted '{target}'[/red]")


def undo_menu(state):
    """Undo/rollback menu."""
    display.clear_screen()
    from planetfall.engine.rollback import (
        get_rollback_options, rollback_to_turn, undo_last_turn,
        recover_pre_rollback,
    )
    snapshots = list_snapshots(state.campaign_name)
    if len(snapshots) < 2:
        display.console.print("  [dim]No previous turns to roll back to.[/dim]")
        return state

    display.console.print(f"\n[bold]Undo/Rollback[/bold] (current: Turn {state.current_turn})")
    display.console.print(f"  Available snapshots: {snapshots}")

    choices = ["Cancel"]
    if len(snapshots) >= 2:
        prev = [t for t in snapshots if t < state.current_turn]
        if prev:
            choices.insert(0, f"Undo last turn (back to Turn {max(prev)})")
    choices.append("Roll back to specific turn")

    choice = prompts.ask_select("Choose:", choices)

    if choice == "Cancel":
        return state
    elif choice.startswith("Undo last"):
        restored = undo_last_turn(state)
        if restored:
            display.console.print(f"  [green]Rolled back to Turn {restored.current_turn}[/green]")
            display.print_colony_status(restored)
            return restored
        else:
            display.console.print("  [red]No previous turn to undo.[/red]")
            return state
    elif choice == "Roll back to specific turn":
        target_choices = [str(t) for t in snapshots if t < state.current_turn]
        if not target_choices:
            display.console.print("  [dim]No earlier snapshots available.[/dim]")
            return state
        turn_str = prompts.ask_select("Roll back to turn:", target_choices)
        target = int(turn_str)
        if prompts.ask_confirm(
            f"Roll back to Turn {target}? Turns after {target} will be deleted.",
            default=False,
        ):
            restored = rollback_to_turn(state.campaign_name, target)
            display.console.print(f"  [green]Rolled back to Turn {restored.current_turn}[/green]")
            display.print_colony_status(restored)
            return restored
        return state
    return state


def export_log_menu(state):
    """Campaign log export menu."""
    from planetfall.engine.campaign_log import (
        save_turn_log, save_campaign_log, export_turn_log,
    )

    choices = [
        "Export current turn log",
        "Export full campaign log",
        "Cancel",
    ]
    choice = prompts.ask_select("Export:", choices)

    if choice == "Export current turn log":
        path = save_turn_log(state)
        display.console.print(f"  [green]Turn log saved to {path}[/green]")
    elif choice == "Export full campaign log":
        path = save_campaign_log(state)
        display.console.print(f"  [green]Campaign log saved to {path}[/green]")


def rules_search_menu():
    """Interactive rules search."""
    from planetfall.rules.loader import search_rules, load_section, list_sections

    while True:
        choices = [
            "Search by keyword",
            "Browse section",
            "Back",
        ]
        choice = prompts.ask_select("Rules:", choices)

        if choice == "Back":
            return
        elif choice == "Search by keyword":
            query = prompts.ask_text("Search for:")
            if not query:
                continue
            results = search_rules(query, max_results=10)
            if not results:
                display.console.print("  [dim]No results found.[/dim]")
            else:
                display.console.print(f"\n  [bold]Found {len(results)} results:[/bold]")
                for line_num, text in results:
                    display.console.print(f"  [cyan]L{line_num}:[/cyan] {text}")
                display.console.print()
        elif choice == "Browse section":
            sections = list_sections()
            section_labels = [format_display(s) for s in sections]
            label = prompts.ask_select("Section:", section_labels)
            section_name = sections[section_labels.index(label)]
            try:
                text = load_section(section_name)
                # Show first ~80 lines
                lines = text.split("\n")[:80]
                display.console.print(f"\n[bold]{label}[/bold] ({len(text.split(chr(10)))} lines)")
                for line in lines:
                    display.console.print(f"  {line}")
                if len(text.split("\n")) > 80:
                    display.console.print(f"  [dim]... ({len(text.split(chr(10))) - 80} more lines)[/dim]")
                display.console.print()
            except (KeyError, FileNotFoundError) as e:
                display.console.print(f"  [red]{e}[/red]")


def view_colony_log(state):
    """Display turn log files one at a time in the console."""
    from rich.markdown import Markdown

    campaign_dir = _campaign_dir(state.campaign_name)
    log_files = sorted(campaign_dir.glob("turn_*_log.md"))

    if not log_files:
        display.console.print("  [dim]No turn logs available yet.[/dim]")
        prompts.pause()
        return

    i = len(log_files) - 1  # Start at most recent
    while True:
        display.clear_screen()
        md_text = log_files[i].read_text(encoding="utf-8")
        display.console.print(Markdown(md_text))
        display.console.print(f"\n  [dim]Log {i + 1}/{len(log_files)}[/dim]")

        choices = []
        if i > 0:
            choices.append("Previous day")
        if i < len(log_files) - 1:
            choices.append("Next day")
        choices.append("Exit logs")

        choice = prompts.ask_select("", choices)
        if choice == "Previous day":
            i -= 1
        elif choice == "Next day":
            i += 1
        else:
            return


def between_turns_menu(state):
    """Menu shown between campaign turns for utility actions."""
    while True:
        display.clear_screen()
        display.print_colony_status(state)
        display.print_map(state)
        choices = [
            "Continue to next turn",
            "View colony log",
            "Search rules",
            "Export campaign log",
            "Undo/rollback",
            "Manage saves",
            "Save and quit",
        ]
        choice = prompts.ask_select("Between turns:", choices)

        if choice == "Continue to next turn":
            return state, True
        elif choice == "View colony log":
            view_colony_log(state)
        elif choice == "Search rules":
            rules_search_menu()
        elif choice == "Export campaign log":
            export_log_menu(state)
        elif choice == "Undo/rollback":
            state = undo_menu(state)
        elif choice == "Manage saves":
            manage_saves()
        elif choice == "Save and quit":
            save_state(state)
            display.console.print("[green]Game saved. See you next time![/green]")
            return state, False



def main():
    """Main game loop."""
    display.clear_screen()
    display.print_title()

    # Check for existing campaigns
    campaigns = list_campaigns()

    if campaigns:
        choices = [
            "New Campaign",
            *[f"Continue: {c}" for c in campaigns],
            "Manage saves",
            "Search rules",
            "Exit",
        ]
        choice = prompts.ask_select("What would you like to do?", choices)

        if choice == "Exit" or choice is None:
            display.clear_screen()
            return
        elif choice == "New Campaign":
            display.clear_screen()
            display.print_title()
            state = setup_new_campaign()
        elif choice == "Manage saves":
            manage_saves()
            return main()  # Re-enter main after managing
        elif choice == "Search rules":
            rules_search_menu()
            return main()
        else:
            campaign_name = choice.replace("Continue: ", "")
            state = load_state(campaign_name)
            display.clear_screen()
            display.print_colony_status(state)
            display.print_map(state)
            display.print_roster(state)
            resume_choice = prompts.ask_select(
                "Resume:", ["Continue", "View colony log"]
            )
            if resume_choice == "View colony log":
                view_colony_log(state)
    else:
        choice = prompts.ask_select("What would you like to do?", ["New Campaign"])
        state = setup_new_campaign()

    # Initial Planetfall missions (before campaign proper)
    if not state.campaign.initial_missions_complete:
        from planetfall.engine.combat.initial_missions import run_initial_missions
        try:
            run_initial_missions(state)
        except prompts.SaveAndQuit:
            display.console.print("\n[yellow]Saving...[/yellow]")
            save_state(state)
            display.console.print("[green]Saved![/green]")
            return main()

    # Campaign turn loop
    while True:
        try:
            state = run_campaign_turn(state)

            # Auto-save turn log
            from planetfall.engine.campaign_log import save_turn_log
            save_turn_log(state)

            if state.campaign.end_game_triggered:
                display.console.print(
                    "\n[bold yellow]The End Game has been triggered![/bold yellow]"
                )
                run_endgame(state)
                break

            # Check colony collapse (loss condition)
            if state.colony.integrity <= -10:
                display.console.print(
                    "\n[bold red]COLONY COLLAPSE! Integrity has fallen to "
                    f"{state.colony.integrity}. The colony cannot sustain itself.[/bold red]"
                )
                show_campaign_result(state, defeat_reason="Colony integrity collapse")
                break

            if state.colony.morale <= 0 and len(state.characters) == 0:
                display.console.print(
                    "\n[bold red]TOTAL LOSS! No characters remain and morale "
                    "has collapsed. The colony is abandoned.[/bold red]"
                )
                show_campaign_result(state, defeat_reason="No surviving characters")
                break

            state, should_continue = between_turns_menu(state)
            if not should_continue:
                break

        except prompts.SaveAndQuit:
            display.console.print("\n[yellow]Saving and returning to main menu...[/yellow]")
            save_state(state)
            display.console.print("[green]Saved![/green]")
            return main()

        except KeyboardInterrupt:
            display.console.print("\n\n[yellow]Game interrupted.[/yellow]")
            if prompts.ask_confirm("Save before quitting?"):
                save_state(state)
                display.console.print("[green]Saved![/green]")
            break

    display.clear_screen()


def run_endgame(state):
    """Execute The Summit endgame sequence."""
    from planetfall.engine.campaign.milestones import (
        run_summit_votes, get_viable_paths, execute_summit,
        SUMMIT_COSTS, SUMMIT_PATH_DESCRIPTIONS, calculate_campaign_score,
    )

    display.console.print("\n[bold cyan]═══ THE SUMMIT ═══[/bold cyan]")
    display.console.print(
        "\nThe colony has reached a critical juncture. A summit is called "
        "to decide the future of the settlement. Characters and the general "
        "population vote on the path forward.\n"
    )

    # Run the vote
    votes = run_summit_votes(state)

    display.console.print("[bold]Summit Votes:[/bold]")
    for path, voters in votes.items():
        if voters:
            display.console.print(f"  [cyan]{path}:[/cyan] {', '.join(voters)}")

    # Show viable paths
    viable = get_viable_paths(votes)
    if not viable:
        viable = ["Independence", "Ascension", "Loyalty", "Isolation"]
        display.console.print(
            "\n  [yellow]No clear consensus — all paths remain available.[/yellow]"
        )

    display.console.print("\n[bold]Available Paths:[/bold]")
    for path in viable:
        costs = SUMMIT_COSTS[path]
        desc = SUMMIT_PATH_DESCRIPTIONS[path]
        can_afford = (
            state.colony.resources.build_points >= costs["bp"]
            and state.colony.resources.research_points >= costs["rp"]
        )
        afford_tag = "[green]Can afford[/green]" if can_afford else "[red]Cannot afford[/red]"
        display.console.print(
            f"  [bold]{path}[/bold] (Cost: {costs['bp']} BP + {costs['rp']} RP) — {afford_tag}"
        )
        display.console.print(f"    [dim]{desc}[/dim]")

    # Player chooses
    affordable = [
        p for p in viable
        if state.colony.resources.build_points >= SUMMIT_COSTS[p]["bp"]
        and state.colony.resources.research_points >= SUMMIT_COSTS[p]["rp"]
    ]

    if not affordable:
        display.console.print(
            "\n[red]Cannot afford any summit path! The colony's future "
            "remains uncertain.[/red]"
        )
        state.flags.summit_path = "Uncertain"
        state.flags.campaign_complete = False
    else:
        chosen = prompts.ask_select("Choose the colony's path:", affordable)
        events = execute_summit(state, chosen)
        display.print_events(events)
        state.turn_log.extend(events)

    save_state(state)
    show_campaign_result(state)


def show_campaign_result(state, defeat_reason: str | None = None):
    """Display the final campaign result screen."""
    from planetfall.engine.campaign.milestones import calculate_campaign_score

    score_data = calculate_campaign_score(state)

    display.console.print("\n")
    display.console.print("[bold cyan]" + "=" * 50 + "[/bold cyan]")

    if defeat_reason:
        display.console.print(
            f"[bold red]  CAMPAIGN OVER — DEFEAT[/bold red]"
        )
        display.console.print(f"  [red]Reason: {defeat_reason}[/red]")
    elif state.flags.campaign_complete:
        display.console.print(
            f"[bold green]  CAMPAIGN COMPLETE — VICTORY[/bold green]"
        )
        summit_path = score_data["summit_path"]
        display.console.print(f"  [green]Summit Path: {summit_path}[/green]")
    else:
        display.console.print(
            f"[bold yellow]  CAMPAIGN ENDED[/bold yellow]"
        )

    display.console.print("[bold cyan]" + "=" * 50 + "[/bold cyan]")

    display.console.print(f"\n[bold]Campaign Statistics[/bold]")
    display.console.print(f"  Turns played: {score_data['turns_played']}")
    display.console.print(f"  Milestones: {state.campaign.milestones_completed} / 7")
    display.console.print(f"  Characters remaining: {len(state.characters)}")
    display.console.print(f"  Colony morale: {state.colony.morale}")
    display.console.print(f"  Colony integrity: {state.colony.integrity}")

    display.console.print(f"\n[bold]Score Breakdown[/bold]")
    for line in score_data["breakdown"]:
        display.console.print(f"  {line}")

    display.console.print(
        f"\n[bold]Final Score: {score_data['score']}[/bold] — "
        f"[bold cyan]{score_data['rating']}[/bold cyan]"
    )
    display.console.print()

    # Save final state
    save_state(state)

    # Export final campaign log
    from planetfall.engine.campaign_log import save_campaign_log
    path = save_campaign_log(state)
    display.console.print(f"  [dim]Campaign log saved to {path}[/dim]")


if __name__ == "__main__":
    main()

"""Initial Planetfall missions — three tutorial missions before the campaign begins.

Beacons (Scout Mission):
    Scouts deploy 3 beacons on raised ground while avoiding storm clusters.
    Reward: +2 Raw Materials on success.

Analysis (Scientist Mission):
    Scientists uncover 4+ of 6 contacts. Contacts move away each round.
    Reward: +2 Research Points (+3 if all 6 revealed) on success.

Perimeter (Trooper Mission):
    Troopers kill 6 melee lifeforms using full combat rules.
    Reward: +3 Colony Morale on success.

All missions use a 6x6 (2'x2') table. Casualties don't require injury rolls.
"""

from __future__ import annotations

from typing import Any

from planetfall.engine.models import GameState

# Re-export all public functions from submodules
from planetfall.engine.combat.initial_missions.beacons import (
    run_beacons,
    run_beacons_ui,
)
from planetfall.engine.combat.initial_missions.analysis import (
    run_analysis,
    run_analysis_ui,
)
from planetfall.engine.combat.initial_missions.perimeter import (
    run_perimeter,
    run_perimeter_ui,
)


# ---------------------------------------------------------------------------
# Main runner — plays all 3 missions in sequence
# ---------------------------------------------------------------------------

MISSION_ORDER = [
    ("Beacons (Scout Mission)", "beacons"),
    ("Analysis (Scientist Mission)", "analysis"),
    ("Perimeter (Trooper Mission)", "perimeter"),
]


def run_initial_missions(state: GameState) -> None:
    """Run the 3 initial Planetfall missions, apply rewards, mark complete."""
    from planetfall.cli import display, prompts
    from planetfall.engine.persistence import save_state

    display.clear_screen()
    display.console.print("\n[bold cyan]╔══════════════════════════════════════════╗[/bold cyan]")
    display.console.print("[bold cyan]║         PLANETFALL — LANDING SITE        ║[/bold cyan]")
    display.console.print("[bold cyan]╚══════════════════════════════════════════╝[/bold cyan]")
    display.console.print(
        "\n  Before the campaign begins, you must establish the landing site"
        "\n  by playing through three initial missions:\n"
    )
    for label, _ in MISSION_ORDER:
        display.console.print(f"    • {label}")
    display.console.print(
        "\n  Casualties during initial missions do not require injury rolls."
        "\n  You may play these in any order.\n"
    )

    # Offer skip options
    start_choices = [
        "Play initial missions",
        "Skip missions (gain all bonuses)",
        "Skip missions (no bonuses)",
    ]
    start_choice = prompts.ask_select("How would you like to begin?", start_choices)

    if start_choice.startswith("Skip missions (gain"):
        # Auto-victory all missions with bonuses
        display.clear_screen()
        display.console.print("\n[bold cyan]═══ LANDING SITE ESTABLISHED ═══[/bold cyan]\n")
        display.console.print("  [dim]Initial missions skipped — all bonuses granted.[/dim]\n")

        state.colony.resources.raw_materials += 2
        display.console.print("  [green]Beacons: +2 Raw Materials[/green]")

        state.colony.resources.research_points += 2
        display.console.print("  [green]Analysis: +2 Research Points[/green]")

        state.colony.morale += 3
        display.console.print("  [green]Perimeter: +3 Colony Morale[/green]")

        from planetfall.engine.models import MissionResult
        for _, key in MISSION_ORDER:
            state.campaign.initial_mission_results[key] = MissionResult(victory=True)

        state.campaign.initial_missions_complete = True
        save_state(state)
        return

    if start_choice.startswith("Skip missions (no"):
        # Skip all missions with no bonuses
        display.clear_screen()
        display.console.print("\n[bold cyan]═══ LANDING SITE ESTABLISHED ═══[/bold cyan]\n")
        display.console.print("  [dim]Initial missions skipped — no bonuses granted.[/dim]")

        from planetfall.engine.models import MissionResult
        for _, key in MISSION_ORDER:
            state.campaign.initial_mission_results[key] = MissionResult(victory=False)

        state.campaign.initial_missions_complete = True
        save_state(state)
        return

    # Play missions normally — skip already-completed missions on resume
    remaining = [
        (label, key) for label, key in MISSION_ORDER
        if key not in state.campaign.initial_mission_results
    ]
    results = dict(state.campaign.initial_mission_results)

    while remaining:
        if len(remaining) == 1:
            mission_label, mission_key = remaining[0]
        else:
            choices = [label for label, _ in remaining]
            chosen_label = prompts.ask_select("Choose next mission:", choices)
            mission_key = next(key for label, key in remaining if label == chosen_label)
            mission_label = chosen_label

        remaining = [(l, k) for l, k in remaining if k != mission_key]

        if mission_key == "beacons":
            result = run_beacons(state)
        elif mission_key == "analysis":
            result = run_analysis(state)
        elif mission_key == "perimeter":
            result = run_perimeter(state)
        else:
            continue

        results[mission_key] = result

        # Save after each mission and increment step
        from planetfall.engine.models import MissionResult
        state.campaign.initial_mission_results[mission_key] = MissionResult(
            victory=result["victory"],
        )
        state.campaign.initial_mission_step += 1
        save_state(state)

    # Apply rewards
    display.clear_screen()
    display.console.print("\n[bold cyan]═══ LANDING SITE ESTABLISHED ═══[/bold cyan]\n")

    if results.get("beacons", {}).get("victory"):
        state.colony.resources.raw_materials += 2
        display.console.print("  [green]Beacons: SUCCESS — +2 Raw Materials[/green]")
    else:
        display.console.print("  [red]Beacons: Failed — no bonus[/red]")

    if results.get("analysis", {}).get("victory"):
        contacts = results["analysis"].get("contacts_revealed", 0)
        rp_bonus = 3 if contacts >= 6 else 2
        state.colony.resources.research_points += rp_bonus
        display.console.print(f"  [green]Analysis: SUCCESS — +{rp_bonus} Research Points[/green]")
    else:
        display.console.print("  [red]Analysis: Failed — no bonus[/red]")

    if results.get("perimeter", {}).get("victory"):
        state.colony.morale += 3
        display.console.print("  [green]Perimeter: SUCCESS — +3 Colony Morale[/green]")
    else:
        display.console.print("  [red]Perimeter: Failed — no bonus[/red]")

    display.console.print(
        "\n  [bold]All initial missions complete. Proceeding to Campaign Setup.[/bold]"
    )
    prompts.pause()

    # Mark complete
    state.campaign.initial_missions_complete = True
    save_state(state)


def run_initial_missions_ui(state: GameState, ui: Any) -> None:
    """Run all 3 initial missions using a UIAdapter, apply rewards, mark complete."""
    from planetfall.engine.persistence import save_state

    # Let player choose mission order — skip already-completed missions on resume
    remaining = [
        (label, key) for label, key in MISSION_ORDER
        if key not in state.campaign.initial_mission_results
    ]
    results = dict(state.campaign.initial_mission_results)

    while remaining:
        if len(remaining) == 1:
            mission_label, mission_key = remaining[0]
            ui.message(f"Final mission: {mission_label}", style="bold")
        else:
            choices = [label for label, _ in remaining]
            mission_label = ui.select("Choose next mission:", choices)
            mission_key = next(key for label, key in remaining if label == mission_label)

        remaining = [(l, k) for l, k in remaining if k != mission_key]

        if mission_key == "beacons":
            result = run_beacons_ui(state, ui)
        elif mission_key == "analysis":
            result = run_analysis_ui(state, ui)
        elif mission_key == "perimeter":
            result = run_perimeter_ui(state, ui)
        else:
            continue

        results[mission_key] = result

        # Save after each mission and increment step
        from planetfall.engine.models import MissionResult
        state.campaign.initial_mission_results[mission_key] = MissionResult(
            victory=result["victory"],
        )
        state.campaign.initial_mission_step += 1
        save_state(state)

    # Apply rewards and build summary
    summary = []

    if results.get("beacons", {}).get("victory"):
        state.colony.resources.raw_materials += 2
        summary.append({"name": "Beacons", "success": True, "detail": "+2 Raw Materials"})
    else:
        summary.append({"name": "Beacons", "success": False, "detail": "No bonus"})

    if results.get("analysis", {}).get("victory"):
        contacts = results["analysis"].get("contacts_revealed", 0)
        rp_bonus = 3 if contacts >= 6 else 2
        state.colony.resources.research_points += rp_bonus
        summary.append({"name": "Analysis", "success": True, "detail": f"+{rp_bonus} Research Points"})
    else:
        summary.append({"name": "Analysis", "success": False, "detail": "No bonus"})

    if results.get("perimeter", {}).get("victory"):
        state.colony.morale += 3
        summary.append({"name": "Perimeter", "success": True, "detail": "+3 Colony Morale"})
    else:
        summary.append({"name": "Perimeter", "success": False, "detail": "No bonus"})

    ui.clear()
    ui.show_mission_summary(summary)
    ui.pause()

    state.campaign.initial_missions_complete = True
    save_state(state)


__all__ = [
    "MISSION_ORDER",
    "run_beacons",
    "run_beacons_ui",
    "run_analysis",
    "run_analysis_ui",
    "run_perimeter",
    "run_perimeter_ui",
    "run_initial_missions",
    "run_initial_missions_ui",
]

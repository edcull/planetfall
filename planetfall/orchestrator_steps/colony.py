"""Colony management orchestrator steps (Steps 14-18)."""
from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from planetfall.engine.models import (
    GameState, TurnEvent, TurnEventType,
)

if TYPE_CHECKING:
    from planetfall.ui.adapter import UIAdapter

RecordFn = Callable[[list[TurnEvent]], None]


def prompt_research_spending(ui: UIAdapter, state: GameState, _record: RecordFn) -> None:
    """Interactive research spending prompt after RP gain."""
    from planetfall.engine.steps.step14_research import get_research_options
    from planetfall.engine.campaign.research import (
        invest_in_theory, unlock_application, perform_bio_analysis,
        THEORIES, get_available_applications,
    )
    from planetfall.engine.dice import roll_d6

    while True:
        opts = get_research_options(state)
        rp = opts["rp_available"]

        if rp == 0:
            ui.message("  No Research Points available.", style="dim")
            break

        choices = ["Skip research spending"]

        for t in opts["theories"]:
            invested = t["invested"]
            inv_str = f"{invested.invested_rp}/{t['rp_cost']}" if invested else f"0/{t['rp_cost']}"
            choices.append(f"Invest in theory: {t['name']} ({inv_str} RP)")

        # Group available applications by theory for random selection
        available_apps = get_available_applications(state)
        theory_app_groups: dict[str, list] = {}
        for app in available_apps:
            theory_app_groups.setdefault(app.theory_id, []).append(app)

        for tid, apps in theory_app_groups.items():
            tdef = THEORIES[tid]
            if rp >= tdef.app_cost:
                choices.append(
                    f"Research application from: {tdef.name} ({tdef.app_cost} RP) — {len(apps)} undiscovered"
                )

        if opts["can_bio_analysis"]:
            choices.append("Perform bio-analysis (3 RP)")

        ui.message(f"\n  Research Points available: {rp}", style="bold")
        choice = ui.select("Research:", choices)

        if choice.startswith("Skip"):
            break
        elif choice.startswith("Invest in theory:"):
            theory_name = choice.split(": ", 1)[1].split(" (")[0]
            theory = next((t for t in opts["theories"] if t["name"] == theory_name), None)
            if theory:
                max_invest = min(rp, theory["rp_cost"] - (theory["invested"].invested_rp if theory["invested"] else 0))
                if max_invest <= 0:
                    ui.message("  Theory already fully invested.", style="dim")
                    continue
                if max_invest == 1:
                    amount = 1
                else:
                    amount = ui.number(f"How much RP to invest? (1-{max_invest})", min_val=1, max_val=max_invest)
                _record(invest_in_theory(state, theory["id"], amount))
        elif choice.startswith("Research application from:"):
            theory_name = choice.split(": ", 1)[1].split(" (")[0]
            tid = next((t for t, td in THEORIES.items() if td.name == theory_name), None)
            if tid and tid in theory_app_groups:
                apps = theory_app_groups[tid]
                # Randomly select from undiscovered applications
                import random
                selected = random.choice(apps)
                ui.message(
                    f"  Rolling for application... "
                    f"D{len(apps)} = {apps.index(selected) + 1}", style="warning"
                )
                _record(unlock_application(state, selected.id))
        elif choice.startswith("Perform bio"):
            _record(perform_bio_analysis(state))


def prompt_building_spending(ui: UIAdapter, state: GameState, _record: RecordFn) -> None:
    """Interactive building spending prompt after BP gain."""
    from planetfall.engine.steps.step15_building import get_building_options
    from planetfall.engine.campaign.buildings import invest_in_building

    while True:
        opts = get_building_options(state)
        bp = opts["bp_available"]
        rm = opts["rm_available"]

        if bp == 0 and rm == 0:
            ui.message("  No Build Points or Raw Materials available.", style="dim")
            break

        choices = ["Skip building spending"]

        # In-progress buildings first
        for bid, info in opts["in_progress"].items():
            remaining = info["total"] - info["invested"]
            choices.append(
                f"Continue: {info['name']} ({info['invested']}/{info['total']} BP, {remaining} remaining)"
            )

        # New buildings
        for b in opts["available"]:
            if b["progress"] == 0:
                milestone = " [milestone]" if b["is_milestone"] else ""
                choices.append(f"Start: {b['name']} ({b['bp_cost']} BP){milestone} — {b['description']}")

        if len(choices) == 1:
            ui.message("  No buildings available to construct.", style="dim")
            break

        ui.message(f"\n  Build Points: {bp} BP | Raw Materials: {rm}", style="bold")
        choice = ui.select("Building:", choices)

        if choice.startswith("Skip"):
            break

        # Find the building
        building_name = choice.split(": ", 1)[1].split(" (")[0]
        building = None
        for b in opts["available"]:
            if b["name"] == building_name:
                building = b
                break
        if not building:
            for bid, info in opts["in_progress"].items():
                if info["name"] == building_name:
                    building = {"id": bid, "name": info["name"], "bp_cost": info["total"]}
                    break

        if building:
            max_bp = min(bp, building["bp_cost"] - building.get("progress", 0))
            rm_convert = 0
            if rm > 0 and max_bp < building["bp_cost"]:
                rm_convert = ui.number(
                    f"Convert raw materials to BP? (0-{min(3, rm)})",
                    min_val=0, max_val=min(3, rm),
                )
            total = max_bp + rm_convert
            if total > 0:
                _record(invest_in_building(state, building["id"], max_bp, rm_convert))
            else:
                ui.message("  No BP to invest.", style="dim")


def execute_augmentation_opportunity(
    ui: UIAdapter,
    state: GameState,
    _record: RecordFn,
) -> None:
    """Augmentation purchase opportunity between steps 15 and 16."""
    from planetfall.engine.campaign.augmentation import (
        get_available_augmentations, apply_augmentation, get_augmentation_cost,
    )

    if (state.colony.resources.augmentation_points >= get_augmentation_cost(state)
            and not state.flags.augmentation_bought_this_turn):
        avail_augs = get_available_augmentations(state)
        if avail_augs:
            cost = get_augmentation_cost(state)
            if ui.confirm(
                f"Purchase an augmentation? (Cost: {cost} AP, "
                f"Available: {state.colony.resources.augmentation_points} AP)",
                default=False,
            ):
                aug_choices = [
                    f"{a['name']} — {a['description']}" for a in avail_augs
                ]
                choice = ui.select("Choose augmentation:", aug_choices)
                aug_idx = aug_choices.index(choice)
                aug_events = apply_augmentation(state, avail_augs[aug_idx]["id"])
                _record(aug_events)


def execute_step16_integrity(
    ui: UIAdapter,
    state: GameState,
    _record: RecordFn,
) -> None:
    """Step 16: Colony Integrity — with optional SP prevention."""
    from planetfall.engine.steps import step16_colony_integrity

    spend_sp_integrity = False
    if state.colony.integrity <= -3 and state.colony.resources.story_points >= 1:
        spend_sp_integrity = ui.confirm(
            f"Colony Integrity is {state.colony.integrity}. "
            f"Spend 1 Story Point to skip Integrity Failure roll? "
            f"({state.colony.resources.story_points} SP)",
            default=False,
        )
    events = step16_colony_integrity.execute(state, spend_story_point=spend_sp_integrity)
    _record(events)
    for ev in events:
        ui.message(f"  {ev.description}")

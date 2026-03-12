"""Step 15: Building — Spend Build Points on colony buildings."""

from __future__ import annotations

from planetfall.engine.models import GameState, TurnEvent, TurnEventType
from planetfall.engine.campaign.buildings import (
    get_available_buildings,
    get_construction_progress,
    invest_in_building,
    process_per_turn_buildings,
    BUILDINGS,
)
from planetfall.engine.campaign.milestones import check_and_apply_milestones


def execute(
    state: GameState,
    building_id: str | None = None,
    bp_amount: int = 0,
    raw_materials_convert: int = 0,
) -> list[TurnEvent]:
    """Execute building step: gain BP, process buildings, optionally construct.

    Args:
        building_id: Building to invest BP in.
        bp_amount: BP to invest from colony reserves.
        raw_materials_convert: Raw materials to convert to BP (max 3/turn).
    """
    events = []

    # Gain per-turn BP
    base_rate = state.colony.per_turn_rates.build_points

    # Apply penalties
    penalty = 0
    penalty_notes: list[str] = []

    # Crisis penalty: all BP sources provide 1 less (rules p.90)
    if state.flags.crisis_active:
        penalty += 1
        penalty_notes.append("Crisis -1")

    # Work stoppage: -3 to BP this turn
    if state.flags.work_stoppage_active:
        state.flags.work_stoppage_active = False
        penalty += 3
        penalty_notes.append("Work Stoppage -3")

    # Integrity failure BP penalty
    bp_penalty = state.flags.bp_penalty_next
    state.flags.bp_penalty_next = 0
    if bp_penalty:
        penalty += abs(bp_penalty)
        penalty_notes.append(f"Integrity Failure {bp_penalty:+d}")

    rate = max(0, base_rate - penalty)
    state.colony.resources.build_points += rate

    desc = f"Gained {rate} Build Point(s)."
    if penalty > 0:
        desc += f" (Base {base_rate}, penalties: {', '.join(penalty_notes)})"
    desc += f" Total: {state.colony.resources.build_points} BP."

    events.append(TurnEvent(
        step=15,
        event_type=TurnEventType.BUILDING,
        description=desc,
        state_changes={"bp_gained": rate, "bp_total": state.colony.resources.build_points},
    ))

    # Process per-turn building effects
    events.extend(process_per_turn_buildings(state))

    # Track milestones before spending
    prev_milestones = state.campaign.milestones_completed

    # Invest in building
    if building_id and bp_amount > 0:
        events.extend(invest_in_building(
            state, building_id, bp_amount, raw_materials_convert
        ))

    # Check for new milestones
    events.extend(check_and_apply_milestones(state, prev_milestones))

    return events


def get_building_options(state: GameState) -> dict:
    """Get available building options for display."""
    progress = get_construction_progress(state)
    available = get_available_buildings(state)

    return {
        "available": [
            {
                "id": b.id,
                "name": b.name,
                "bp_cost": b.bp_cost,
                "progress": progress.get(b.id, 0),
                "is_milestone": b.is_milestone,
                "description": b.description,
            }
            for b in available
        ],
        "in_progress": {
            bid: {
                "name": BUILDINGS[bid].name,
                "invested": invested,
                "total": BUILDINGS[bid].bp_cost,
            }
            for bid, invested in progress.items()
            if bid in BUILDINGS
        },
        "bp_available": state.colony.resources.build_points,
        "rm_available": state.colony.resources.raw_materials,
        "built": [b.name for b in state.colony.buildings],
    }

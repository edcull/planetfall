"""Step 14: Research — Spend Research Points on theories and applications."""

from __future__ import annotations

from planetfall.engine.models import GameState, TurnEvent, TurnEventType
from planetfall.engine.campaign.research import (
    get_available_theories,
    get_available_applications,
    invest_in_theory,
    unlock_application,
    perform_bio_analysis,
    THEORIES,
    APPLICATIONS,
)
from planetfall.engine.campaign.milestones import check_and_apply_milestones


def execute(
    state: GameState,
    theory_id: str | None = None,
    theory_rp: int = 0,
    application_id: str | None = None,
    bio_analysis: bool = False,
) -> list[TurnEvent]:
    """Execute research step: gain RP, then optionally spend on research.

    Args:
        theory_id: Theory to invest RP in.
        theory_rp: Amount of RP to invest in theory.
        application_id: Application to unlock.
        bio_analysis: Whether to perform bio-analysis (3 RP).
    """
    events = []

    # Gain per-turn RP: base rate + 1 per milestone achieved
    base_rate = state.colony.per_turn_rates.research_points + state.campaign.milestones_completed

    # Apply penalties
    penalty = 0
    penalty_notes: list[str] = []

    # Crisis penalty: all RP sources provide 1 less (rules p.90)
    if state.flags.crisis_active:
        penalty += 1
        penalty_notes.append("Crisis -1")

    # Work stoppage: -3 to RP this turn
    if state.flags.work_stoppage_active:
        penalty += 3
        penalty_notes.append("Work Stoppage -3")

    # Integrity failure RP penalty
    rp_penalty = state.flags.rp_penalty_next
    state.flags.rp_penalty_next = 0
    if rp_penalty:
        penalty += abs(rp_penalty)
        penalty_notes.append(f"Integrity Failure {rp_penalty:+d}")

    rate = max(0, base_rate - penalty)
    state.colony.resources.research_points += rate

    desc = f"Gained {rate} Research Point(s)."
    if penalty > 0:
        desc += f" (Base {base_rate}, penalties: {', '.join(penalty_notes)})"
    desc += f" Total: {state.colony.resources.research_points} RP."

    events.append(TurnEvent(
        step=14,
        event_type=TurnEventType.RESEARCH,
        description=desc,
        state_changes={"rp_gained": rate, "rp_total": state.colony.resources.research_points},
    ))

    # Track milestones before spending
    prev_milestones = state.campaign.milestones_completed

    # Invest in theory
    if theory_id and theory_rp > 0:
        events.extend(invest_in_theory(state, theory_id, theory_rp))

    # Unlock application
    if application_id:
        events.extend(unlock_application(state, application_id))

    # Bio-analysis
    if bio_analysis:
        events.extend(perform_bio_analysis(state))

    # Check for new milestones
    events.extend(check_and_apply_milestones(state, prev_milestones))

    return events


def get_research_options(state: GameState) -> dict:
    """Get available research options for display."""
    return {
        "theories": [
            {
                "id": t.id,
                "name": t.name,
                "rp_cost": t.rp_cost,
                "invested": state.tech_tree.theories.get(t.id, None),
                "app_cost": t.app_cost,
            }
            for t in get_available_theories(state)
        ],
        "applications": [
            {
                "id": a.id,
                "name": a.name,
                "theory": THEORIES[a.theory_id].name,
                "cost": THEORIES[a.theory_id].app_cost,
                "description": a.description,
            }
            for a in get_available_applications(state)
        ],
        "rp_available": state.colony.resources.research_points,
        "bio_specimens": [
            {"name": lf.name, "analyzed": bool(lf.bio_analysis_result)}
            for lf in state.enemies.lifeform_table
            if lf.specimen_collected and lf.name
        ],
    }

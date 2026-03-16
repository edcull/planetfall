"""Slyn faction — mysterious alien antagonists.

The Slyn are always a potential threat from the start of the campaign.
Their interference can be checked during missions, and they can be
permanently driven off once milestone 4 enables victory tracking and
enough victories are accumulated.
"""

from __future__ import annotations

from planetfall.engine.dice import roll_d6, roll_nd6
from planetfall.engine.models import GameState, TurnEvent, TurnEventType


def check_slyn_interference(state: GameState) -> list[TurnEvent]:
    """Check if the Slyn interfere with the current mission.

    Slyn are always active unless driven off. Returns events
    describing Slyn encounter if triggered.
    """
    if not state.enemies.slyn.active:
        return []

    # Check if Slyn assault calamity is active (doubles interference chance)
    active_calamities = state.tracking.active_calamities
    slyn_assault = "slyn_assault" in active_calamities

    roll = roll_d6("Slyn interference check")
    threshold = 2 if slyn_assault else 1  # 1-in-6 normally, 2-in-6 during assault

    if roll.total > threshold:
        return []

    state.enemies.slyn.encounters += 1

    # Determine Slyn force size
    base_count = 8 if slyn_assault else 4
    count = base_count + (state.enemies.slyn.encounters // 3)  # Escalate over time

    return [TurnEvent(
        step=8, event_type=TurnEventType.COMBAT,
        description=(
            f"SLYN INTERFERENCE! {count} Slyn warriors appear on the battlefield! "
            f"(Encounter #{state.enemies.slyn.encounters})"
        ),
        state_changes={
            "slyn_count": count,
            "slyn_encounter": state.enemies.slyn.encounters,
        },
    )]


def record_slyn_kills(state: GameState, kills: int) -> list[TurnEvent]:
    """Record Slyn kills and check if they can be driven off.

    Victories prior to milestone 4 are not counted. After milestone 4
    enables tracking, each victory is recorded and triggers a 2D6
    departure check — if the roll is equal to or below the tracked
    victories, the Slyn leave permanently.
    """
    if not state.tracking.slyn_victory_tracking_active:
        return [TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=f"Slyn casualties: {kills}. (Victories not yet tracked — need milestone 4.)",
        )]

    state.tracking.slyn_victories += kills
    slyn_victories = state.tracking.slyn_victories

    events = [TurnEvent(
        step=0, event_type=TurnEventType.NARRATIVE,
        description=f"Slyn casualties: {kills}. Tracked victories: {slyn_victories}.",
    )]

    # Each time you beat the Slyn, roll 2D6 — if <= tracked victories, they leave
    check = roll_nd6(2, "Slyn departure check")
    if check.total <= slyn_victories:
        state.enemies.slyn.active = False
        events.append(TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=(
                f"The Slyn withdraw! Roll {check.total} <= {slyn_victories} victories. "
                f"They will not trouble the colony again."
            ),
            state_changes={"slyn_driven_off": True},
        ))
    else:
        events.append(TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=(
                f"Slyn departure check: rolled {check.total} > {slyn_victories} victories. "
                f"The Slyn remain a threat."
            ),
        ))

    return events

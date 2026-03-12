"""Slyn faction — mysterious alien antagonists.

The Slyn become active at milestone 4. Their interference can be
checked during missions, and they can be permanently driven off
once enough victories against them are accumulated.
"""

from __future__ import annotations

from planetfall.engine.dice import roll_d6, roll_nd6
from planetfall.engine.models import GameState, TurnEvent, TurnEventType


def check_slyn_interference(state: GameState) -> list[TurnEvent]:
    """Check if the Slyn interfere with the current mission.

    Only applies after milestone 4 when Slyn become active.
    Returns events describing Slyn encounter if triggered.
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

    After milestone 4, track victories. Roll 2D6; if <= total Slyn
    victories, the Slyn leave permanently.
    """
    state.tracking.slyn_victories += kills
    slyn_victories = state.tracking.slyn_victories

    events = [TurnEvent(
        step=0, event_type=TurnEventType.NARRATIVE,
        description=f"Slyn casualties: {kills}. Total Slyn defeated: {slyn_victories}.",
    )]

    # Check if Slyn leave
    if slyn_victories >= 3:  # Need at least 3 before checking
        check = roll_nd6(2, "Slyn departure check")
        if check.total <= slyn_victories:
            state.enemies.slyn.active = False
            events.append(TurnEvent(
                step=0, event_type=TurnEventType.NARRATIVE,
                description=(
                    f"The Slyn withdraw! Roll {check.total} <= {slyn_victories} victories. "
                    f"They will not trouble the colony again."
                ),
            ))
        else:
            events.append(TurnEvent(
                step=0, event_type=TurnEventType.NARRATIVE,
                description=(
                    f"Slyn departure check: {check.total} > {slyn_victories}. "
                    f"The Slyn remain a threat."
                ),
            ))

    return events


def activate_slyn(state: GameState) -> list[TurnEvent]:
    """Activate the Slyn faction (called at milestone 4)."""
    if state.enemies.slyn.active:
        return []

    state.enemies.slyn.active = True
    return [TurnEvent(
        step=0, event_type=TurnEventType.NARRATIVE,
        description=(
            "THE SLYN EMERGE. A shadowy alien faction has taken notice of the "
            "colony. Their agents will now interfere with missions."
        ),
    )]

"""Step 12: Track Enemy Information & Mission Data."""

from __future__ import annotations

from planetfall.engine.models import GameState, MissionType, TurnEvent, TurnEventType
from planetfall.engine.campaign.ancient_signs import check_mission_data_breakthrough


def execute(
    state: GameState,
    mission_type: MissionType,
    mission_victory: bool = True,
) -> list[TurnEvent]:
    """Update enemy information and mission data based on mission results."""
    events = []

    # Mission Data tracking
    if mission_victory and mission_type in (
        MissionType.EXPLORATION, MissionType.SCIENCE,
        MissionType.INVESTIGATION, MissionType.DELVE,
    ):
        state.campaign.mission_data_count += 1
        events.append(TurnEvent(
            step=12,
            event_type=TurnEventType.MISSION,
            description=(
                f"Mission Data +1 (total: {state.campaign.mission_data_count})."
            ),
        ))
        # Check for mission data breakthrough
        events.extend(check_mission_data_breakthrough(state))

    # Enemy Information from skirmishes/strikes
    if mission_victory and mission_type in (
        MissionType.SKIRMISH, MissionType.STRIKE,
    ):
        state.campaign.enemy_information_count += 1
        # Also increment on the specific tactical enemy
        active_enemies = [e for e in state.enemies.tactical_enemies if not e.defeated]
        if active_enemies:
            enemy = active_enemies[0]
            info_gain = 1 if mission_type == MissionType.SKIRMISH else 2
            enemy.enemy_info_count += info_gain
            events.append(TurnEvent(
                step=12,
                event_type=TurnEventType.MISSION,
                description=(
                    f"Enemy Information +{info_gain} on {enemy.name} "
                    f"(total: {enemy.enemy_info_count})."
                ),
            ))

            # Strongpoint located when enemy info reaches 3+
            if enemy.enemy_info_count >= 3 and not enemy.strongpoint_located:
                enemy.strongpoint_located = True
                events.append(TurnEvent(
                    step=12,
                    event_type=TurnEventType.MISSION,
                    description=(
                        f"STRONGPOINT LOCATED: {enemy.name}'s strongpoint has been found! "
                        f"Assault mission now available."
                    ),
                    state_changes={"strongpoint_located": enemy.name},
                ))
        else:
            events.append(TurnEvent(
                step=12,
                event_type=TurnEventType.MISSION,
                description=f"Enemy Information +1 (total: {state.campaign.enemy_information_count}).",
            ))

    # Assault victory: enemy defeated, counts as milestone
    if mission_victory and mission_type == MissionType.ASSAULT:
        active_enemies = [e for e in state.enemies.tactical_enemies if not e.defeated]
        if active_enemies:
            enemy = active_enemies[0]
            enemy.defeated = True
            state.campaign.milestones_completed += 1
            events.append(TurnEvent(
                step=12,
                event_type=TurnEventType.MISSION,
                description=(
                    f"ENEMY DEFEATED: {enemy.name}'s strongpoint destroyed! "
                    f"MILESTONE achieved ({state.campaign.milestones_completed} total)."
                ),
                state_changes={
                    "enemy_defeated": enemy.name,
                    "milestone": state.campaign.milestones_completed,
                },
            ))

    if not events:
        events.append(TurnEvent(
            step=12,
            event_type=TurnEventType.MISSION,
            description="No tracking updates this turn.",
        ))

    return events

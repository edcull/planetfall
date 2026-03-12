"""Step 8: Play Out Mission — Combat system integration.

Sets up the battlefield, runs combat rounds with human-in-the-loop
player decisions and deterministic enemy AI.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from planetfall.engine.models import GameState, MissionType, TurnEvent, TurnEventType
from planetfall.engine.combat.battlefield import Battlefield, FigureSide
from planetfall.engine.combat.missions import MissionSetup, setup_mission
from planetfall.engine.combat.round import (
    RoundResult, ReactionRollResult,
    roll_reactions, execute_enemy_phase, execute_player_activation,
    check_panic, check_battle_end, reset_round, get_round_casualties,
)


@dataclass
class MissionResult:
    """Result of playing out a mission."""
    mission_type: MissionType
    victory: bool = False
    character_casualties: list[str] = field(default_factory=list)
    grunt_casualties: int = 0
    enemies_killed: int = 0
    objectives_completed: list[str] = field(default_factory=list)
    loot: dict = field(default_factory=dict)
    narrative_seed: dict = field(default_factory=dict)
    rounds_played: int = 0
    battle_log: list[str] = field(default_factory=list)


def setup(
    state: GameState,
    mission_type: MissionType,
    deployed_names: list[str],
    grunt_count: int = 0,
    enemy_type_id: str | None = None,
) -> MissionSetup:
    """Set up the mission battlefield. Returns setup for the combat loop."""
    return setup_mission(
        state, mission_type, deployed_names, grunt_count, enemy_type_id
    )


def run_auto_battle(
    mission_setup: MissionSetup,
) -> MissionResult:
    """Run a fully automated battle (no human input).

    Useful for testing and for battles the player wants to auto-resolve.
    Player figures use a simple AI: shoot nearest enemy, advance if no target.
    """
    bf = mission_setup.battlefield
    result = MissionResult(mission_type=mission_setup.mission_type)

    for round_num in range(1, mission_setup.max_rounds + 1):
        bf.round_number = round_num
        reset_round(bf)

        pre_round = [f.name for f in bf.figures if f.is_alive]

        # Reaction roll (auto-assign)
        reaction = roll_reactions(bf)
        result.battle_log.extend(reaction.log)

        # Quick actions (auto: shoot nearest enemy)
        for name in reaction.quick_actors:
            fig = bf.get_figure_by_name(name)
            if not fig or not fig.is_alive:
                continue
            target = _find_nearest_enemy(bf, fig)
            if target:
                act = execute_player_activation(
                    bf, fig, "shoot", target_name=target.name, phase="quick"
                )
            else:
                act = execute_player_activation(bf, fig, "hold", phase="quick")
            result.battle_log.extend(act.log)

        # Enemy phase
        enemy_acts = execute_enemy_phase(bf)
        for act in enemy_acts:
            result.battle_log.extend(act.log)

        # Slow actions (auto: shoot nearest enemy)
        for name in reaction.slow_actors:
            fig = bf.get_figure_by_name(name)
            if not fig or not fig.is_alive:
                continue
            target = _find_nearest_enemy(bf, fig)
            if target:
                act = execute_player_activation(
                    bf, fig, "shoot", target_name=target.name, phase="slow"
                )
            else:
                act = execute_player_activation(bf, fig, "hold", phase="slow")
            result.battle_log.extend(act.log)

        # End phase
        casualties = get_round_casualties(bf, pre_round)
        result.battle_log.append(f"--- Round {round_num} end: {len(casualties)} casualties ---")

        # Panic check
        enemy_casualties = [
            c for c in casualties
            if any(f.name == c and f.side == FigureSide.ENEMY for f in bf.figures)
        ]
        if enemy_casualties:
            panic = check_panic(bf, enemy_casualties)
            if panic:
                result.battle_log.extend(panic.log)

        # Check battle end
        outcome = check_battle_end(bf)
        if outcome:
            result.victory = outcome == "player_victory"
            result.rounds_played = round_num
            break
    else:
        # Max rounds reached
        result.rounds_played = mission_setup.max_rounds
        result.victory = check_battle_end(bf) == "player_victory"

    # Tally results
    result.enemies_killed = sum(
        1 for f in bf.figures
        if f.side == FigureSide.ENEMY and not f.is_alive
    )
    result.character_casualties = [
        f.name for f in bf.figures
        if f.side == FigureSide.PLAYER and not f.is_alive
        and f.char_class != "grunt"
    ]
    result.grunt_casualties = sum(
        1 for f in bf.figures
        if f.side == FigureSide.PLAYER and not f.is_alive
        and f.char_class == "grunt"
    )

    return result


def _find_nearest_enemy(bf: Battlefield, fig):
    """Find the nearest living enemy figure."""
    enemies = [
        f for f in bf.figures
        if f.side != fig.side and f.is_alive
    ]
    if not enemies:
        return None
    return min(enemies, key=lambda e: bf.zone_distance(fig.zone, e.zone))


def execute(
    state: GameState,
    mission_type: MissionType,
    deployed_names: list[str] | None = None,
    grunt_count: int = 0,
    mode: str = "auto",
) -> tuple[MissionResult, list[TurnEvent]]:
    """Execute a mission.

    Args:
        mode: "auto" for AI-resolved battle, "interactive" to set up
              for human-in-the-loop play via CombatSession, "manual"
              for tabletop resolution stub.
    """
    if deployed_names and mode == "auto":
        mission_setup = setup(state, mission_type, deployed_names, grunt_count)
        result = run_auto_battle(mission_setup)
        events = [_make_combat_event(mission_type, result)]
        return result, events

    elif deployed_names and mode == "interactive":
        # Set up battlefield but don't run — the CombatSession handles rounds
        result = MissionResult(mission_type=mission_type)
        events = [TurnEvent(
            step=8,
            event_type=TurnEventType.COMBAT,
            description=(
                f"Mission: {mission_type.value.replace('_', ' ').title()}. "
                f"Interactive combat begins."
            ),
            state_changes={"mission_type": mission_type.value, "mode": "interactive"},
        )]
        return result, events

    else:
        # Stub for manual/tabletop resolution
        result = MissionResult(mission_type=mission_type)
        events = [TurnEvent(
            step=8,
            event_type=TurnEventType.COMBAT,
            description=(
                f"Mission: {mission_type.value.replace('_', ' ').title()}. "
                f"[Resolve manually and enter results]"
            ),
            state_changes={"mission_type": mission_type.value},
        )]
        return result, events


def apply_combat_result(state: GameState, result: dict) -> list[TurnEvent]:
    """Apply interactive combat results to generate TurnEvents for downstream steps."""
    victory = result.get("victory", False)
    rounds_played = result.get("rounds_played", 0)
    enemies_killed = result.get("enemies_killed", 0)
    char_casualties = result.get("character_casualties", [])
    grunt_casualties = result.get("grunt_casualties", 0)

    summary = (
        f"Battle concluded: {'VICTORY' if victory else 'DEFEAT'} "
        f"in {rounds_played} rounds. "
        f"{enemies_killed} enemies killed."
    )
    if char_casualties:
        summary += f" Casualties: {', '.join(char_casualties)}."
    if grunt_casualties:
        summary += f" {grunt_casualties} grunt(s) lost."

    return [TurnEvent(
        step=8,
        event_type=TurnEventType.COMBAT,
        description=summary,
        state_changes={
            "victory": victory,
            "enemies_killed": enemies_killed,
            "rounds_played": rounds_played,
        },
    )]


def _make_combat_event(mission_type: MissionType, result: MissionResult) -> TurnEvent:
    """Create a TurnEvent from a completed auto-battle MissionResult."""
    summary = (
        f"Mission: {mission_type.value.replace('_', ' ').title()} — "
        f"{'VICTORY' if result.victory else 'DEFEAT'} "
        f"in {result.rounds_played} rounds. "
        f"{result.enemies_killed} enemies killed."
    )
    if result.character_casualties:
        summary += f" Character casualties: {', '.join(result.character_casualties)}."
    if result.grunt_casualties:
        summary += f" Grunt casualties: {result.grunt_casualties}."

    return TurnEvent(
        step=8,
        event_type=TurnEventType.COMBAT,
        description=summary,
        state_changes={
            "mission_type": mission_type.value,
            "victory": result.victory,
            "enemies_killed": result.enemies_killed,
            "rounds_played": result.rounds_played,
        },
    )

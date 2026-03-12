"""Step 11: Colony Morale Adjustments.

Rules (page 68, 89):
- Colony Morale automatically drops 1 point during this step.
- It drops an additional point for every battle casualty
  (characters AND grunts who became casualties).
- If playing a Rescue Mission, do NOT suffer morale loss due to
  squad casualties (only penalized if colonists become casualties).
- If morale is -10 or worse, roll on the Morale Incident table.
"""

from __future__ import annotations

import random

from planetfall.engine.campaign.augmentation import has_augmentation
from planetfall.engine.dice import roll_d6, roll_nd6
from planetfall.engine.models import (
    GameState, Loyalty, MissionType, TurnEvent, TurnEventType, DiceRoll,
)
from planetfall.engine.tables.morale_incidents import (
    MORALE_INCIDENT_TABLE, CRISIS_OUTCOME_TABLE,
)


_LOYALTY_LEVELS = [Loyalty.DISLOYAL, Loyalty.COMMITTED, Loyalty.LOYAL]


def execute(
    state: GameState,
    battle_casualties: int = 0,
    mission_type: MissionType | None = None,
    mission_victory: bool | None = None,
    spend_sp_prevent_incident: bool = False,
) -> list[TurnEvent]:
    """Adjust colony morale based on rules.

    Args:
        battle_casualties: Total number of casualties on the battlefield
            (characters + grunts who became casualties during the mission).
        mission_type: The mission type played this turn, if any.
        mission_victory: Whether the mission was won (for Crisis resolution).
    """
    events = []
    old_morale = state.colony.morale
    adjustments: list[str] = []

    # Automatic -1 each campaign turn
    state.colony.morale -= 1
    adjustments.append("-1 (automatic)")

    # -1 per battle casualty (skip for Rescue missions per rules p.89)
    is_rescue = mission_type in (MissionType.RESCUE, MissionType.SCOUT_DOWN)
    if battle_casualties > 0 and not is_rescue:
        state.colony.morale -= battle_casualties
        adjustments.append(f"-{battle_casualties} ({battle_casualties} battle casualty(ies))")
    elif battle_casualties > 0 and is_rescue:
        adjustments.append(
            f"(Rescue mission: {battle_casualties} squad casualty(ies) "
            f"do not affect morale)"
        )

    desc = (
        f"Colony Morale: {old_morale} → {state.colony.morale} "
        f"({', '.join(adjustments)})."
    )

    events.append(TurnEvent(
        step=11,
        event_type=TurnEventType.MORALE,
        description=desc,
        state_changes={"old_morale": old_morale, "new_morale": state.colony.morale},
    ))

    # Check for Morale Incident at -10 or worse
    if state.colony.morale <= -10:
        if spend_sp_prevent_incident and state.colony.resources.story_points >= 1:
            # Spend 1 SP to prevent the incident (morale still resets to 0)
            state.colony.resources.story_points -= 1
            state.colony.morale = 0
            events.append(TurnEvent(
                step=11,
                event_type=TurnEventType.MORALE,
                description=(
                    f"Morale reached {state.colony.morale}! Story Point spent "
                    f"to prevent Morale Incident. Morale reset to 0. "
                    f"Remaining: {state.colony.resources.story_points} SP."
                ),
                state_changes={"story_point_spent": "morale_incident"},
            ))
        else:
            incident_events = _handle_morale_incident(state, mission_victory)
            events.extend(incident_events)

    # Resolve ongoing Crisis each turn
    if state.flags.crisis_active:
        crisis_events = resolve_crisis(state, mission_victory)
        events.extend(crisis_events)

    return events


def _handle_morale_incident(
    state: GameState,
    mission_victory: bool | None,
) -> list[TurnEvent]:
    """Roll on the Morale Incident table and apply results.

    After rolling, morale is reset to 0 and Political Upheaval increases.
    """
    events = []

    roll_result, entry = MORALE_INCIDENT_TABLE.roll_on_table("Morale Incident")
    effects = entry.effects or {}

    # Morale is reset to 0 after the incident
    state.colony.morale = 0

    # Add +1 Political Upheaval
    if not hasattr(state.campaign, "political_upheaval"):
        # Store on campaign progress (we use campaign_story_track as fallback)
        pass
    political_upheaval = _get_political_upheaval(state)
    political_upheaval += 1
    _set_political_upheaval(state, political_upheaval)

    desc = (
        f"MORALE INCIDENT! Roll {roll_result.total}: "
        f"{entry.result_id.replace('_', ' ').title()}. "
        f"{entry.description} "
        f"Morale reset to 0. Political Upheaval now {political_upheaval}."
    )

    all_dice = [DiceRoll(
        dice_type="d100", values=[roll_result.total],
        total=roll_result.total, label="Morale Incident",
    )]

    # Apply specific incident effects
    effect_desc, extra_dice = _apply_incident_effects(
        state, entry.result_id, effects, mission_victory
    )
    all_dice.extend(extra_dice)
    if effect_desc:
        desc += f" Effect: {effect_desc}"

    events.append(TurnEvent(
        step=11,
        event_type=TurnEventType.MORALE,
        description=desc,
        dice_rolls=all_dice,
    ))

    # Crisis check (always triggered when Political Upheaval increases)
    crisis_events = _crisis_check(state, mission_victory)
    events.extend(crisis_events)

    return events


def _apply_incident_effects(
    state: GameState,
    event_id: str,
    effects: dict,
    mission_victory: bool | None,
) -> tuple[str, list[DiceRoll]]:
    """Apply effects from a morale incident."""
    result_parts: list[str] = []
    extra_dice: list[DiceRoll] = []

    if event_id == "character_loyalty_loss":
        if state.characters:
            char = random.choice(state.characters)
            # Psionic Cohesion: roll 1D6, on 5-6 prevent loss
            if has_augmentation(state, "psionic_cohesion"):
                check = roll_d6(f"Psionic Cohesion: {char.name}")
                extra_dice.append(DiceRoll(
                    dice_type="d6", values=check.values,
                    total=check.total, label=f"Psionic Cohesion: {char.name}",
                ))
                if check.total >= 5:
                    result_parts.append(
                        f"{char.name} would lose Loyalty, but Psionic "
                        f"Cohesion prevents it (rolled {check.total})"
                    )
                    return "; ".join(result_parts), extra_dice

            idx = _LOYALTY_LEVELS.index(char.loyalty) if char.loyalty in _LOYALTY_LEVELS else 1
            if idx > 0:
                old = char.loyalty.value
                char.loyalty = _LOYALTY_LEVELS[idx - 1]
                result_parts.append(
                    f"{char.name} Loyalty {old} → {char.loyalty.value}"
                )
            else:
                result_parts.append(f"{char.name} already Disloyal")

    elif event_id == "sabotage":
        d6 = roll_d6("Sabotage damage")
        extra_dice.append(DiceRoll(
            dice_type="d6", values=d6.values,
            total=d6.total, label="Sabotage Colony Damage",
        ))
        state.colony.integrity -= d6.total
        # Colony damage also reduces morale (but morale was just reset to 0)
        state.colony.morale -= d6.total
        result_parts.append(
            f"{d6.total} Colony Damage (unmitigable). "
            f"Morale also drops by {d6.total}."
        )

    elif event_id == "protests":
        # Bench a random trooper for next campaign turn
        troopers = [c for c in state.characters
                     if c.char_class.value == "trooper" and c.is_available]
        if troopers:
            benched = random.choice(troopers)
            state.flags.benched_trooper = benched.name
            result_parts.append(
                f"{benched.name} is benched next turn due to protests "
                f"(unless a Pitched Battle occurs)"
            )
        else:
            result_parts.append("No available troopers to bench")

    elif event_id == "work_stoppage":
        # -3 penalty to BP and RP earned this turn
        state.flags.work_stoppage_active = True
        result_parts.append(
            "-3 penalty to BP and RP earned this campaign turn"
        )

    elif event_id == "colonist_demands":
        # Track that colonist demands are active — requires assignment
        state.flags.colonist_demands_active = True
        result_parts.append(
            "Colonist demands active! Assign scouts/troopers to security "
            "each turn. They cannot deploy on missions (except Pitched Battle). "
            "Roll 1D6+Savvy per assigned character; 5+ = demands satisfied."
        )

    elif event_id == "political_strife":
        result_parts.append("Political strife — Crisis check triggered")

    return "; ".join(result_parts), extra_dice


def _crisis_check(
    state: GameState,
    mission_victory: bool | None,
) -> list[TurnEvent]:
    """Roll 2D6 for Crisis check.

    If roll <= Political Upheaval, colony enters Crisis.
    """
    political_upheaval = _get_political_upheaval(state)
    roll = roll_nd6(2, "Crisis check")
    dice = [DiceRoll(
        dice_type="2d6", values=roll.values,
        total=roll.total, label="Crisis check",
    )]

    if roll.total <= political_upheaval:
        desc = (
            f"CRISIS! Roll {roll.total} ≤ Political Upheaval "
            f"{political_upheaval}. Colony enters Crisis. "
            f"Morale fixed at 0; RP/BP/RM reduced by 1 during Crisis."
        )
        state.flags.crisis_active = True
    else:
        desc = (
            f"Crisis check: Roll {roll.total} > Political Upheaval "
            f"{political_upheaval}. No crisis."
        )

    return [TurnEvent(
        step=11,
        event_type=TurnEventType.MORALE,
        description=desc,
        dice_rolls=dice,
    )]


def resolve_crisis(
    state: GameState,
    mission_victory: bool | None = None,
) -> list[TurnEvent]:
    """Resolve an ongoing Crisis during Step 11.

    Each campaign turn during Crisis, roll 2D6 on the Crisis Outcome table.
    """
    if not state.flags.crisis_active:
        return []

    # Story Point reroll: roll twice, pick the better score
    reroll = state.flags.crisis_reroll_active
    state.flags.crisis_reroll_active = False
    if reroll:
        roll1, entry1 = CRISIS_OUTCOME_TABLE.roll_on_table("Crisis Outcome (1st)")
        roll2, entry2 = CRISIS_OUTCOME_TABLE.roll_on_table("Crisis Outcome (2nd)")
        # Higher roll is generally better on this table
        if roll2.total > roll1.total:
            roll_result, entry = roll2, entry2
        else:
            roll_result, entry = roll1, entry1
    else:
        roll_result, entry = CRISIS_OUTCOME_TABLE.roll_on_table("Crisis Outcome")
    effects = entry.effects or {}
    political_upheaval = _get_political_upheaval(state)

    desc = (
        f"Crisis Outcome: Roll {roll_result.total} — "
        f"{entry.result_id.replace('_', ' ').title()}. "
        f"{entry.description}"
    )

    dice = [DiceRoll(
        dice_type="2d6", values=roll_result.values,
        total=roll_result.total, label="Crisis Outcome",
    )]

    if effects.get("double_crisis_check"):
        # High tensions: another crisis check
        check = roll_nd6(2, "High tensions crisis check")
        dice.append(DiceRoll(
            dice_type="2d6", values=check.values,
            total=check.total, label="High tensions check",
        ))
        if check.total <= political_upheaval:
            desc += (
                f" Roll {check.total} ≤ {political_upheaval}: "
                f"CAMPAIGN FAILURE — colony collapses into rebellion."
            )
            state.campaign.end_game_triggered = True
        else:
            political_upheaval += 1
            _set_political_upheaval(state, political_upheaval)
            desc += (
                f" Roll {check.total} > {political_upheaval - 1}: "
                f"+1 Political Upheaval (now {political_upheaval})."
            )

    elif effects.get("upheaval_if_mission_failed"):
        if mission_victory is False:
            political_upheaval += 1
            _set_political_upheaval(state, political_upheaval)
            desc += f" Mission failed: +1 Political Upheaval (now {political_upheaval})."
        else:
            desc += " Mission succeeded: no changes."

    elif effects.get("upheaval_reduction"):
        political_upheaval = max(0, political_upheaval + effects["upheaval_reduction"])
        _set_political_upheaval(state, political_upheaval)
        if political_upheaval == 0:
            state.flags.crisis_active = False
            state.colony.morale = 0
            desc += " Crisis ends! Political Upheaval and Morale set to 0."
        else:
            desc += f" Political Upheaval now {political_upheaval}."

    elif effects.get("crisis_ends"):
        political_upheaval = 0
        _set_political_upheaval(state, political_upheaval)
        state.flags.crisis_active = False
        state.colony.morale = 0
        desc += " Crisis ends. Political Upheaval and Morale set to 0."

    return [TurnEvent(
        step=11,
        event_type=TurnEventType.MORALE,
        description=desc,
        dice_rolls=dice,
    )]


def resolve_colonist_demands(
    state: GameState,
    assigned_characters: list[str],
) -> list[TurnEvent]:
    """Resolve colonist demands by rolling for each assigned character.

    Each assigned scout/trooper rolls 1D6 + Savvy; 5+ = demands satisfied.
    Assigned characters cannot deploy on missions (except Pitched Battle).
    """
    if not state.flags.colonist_demands_active:
        return []

    events = []
    state.flags.colonist_demands_assigned = list(assigned_characters)

    for char_name in assigned_characters:
        char = None
        for c in state.characters:
            if c.name == char_name:
                char = c
                break
        if not char:
            continue

        roll = roll_d6(f"Colonist demands: {char_name}")
        result = roll.total + char.savvy
        if result >= 5:
            state.flags.colonist_demands_active = False
            state.flags.colonist_demands_assigned = []
            events.append(TurnEvent(
                step=11, event_type=TurnEventType.MORALE,
                description=(
                    f"{char_name} rolled {roll.total} + Savvy {char.savvy} = "
                    f"{result} (≥5). Colonist demands satisfied!"
                ),
                dice_rolls=[DiceRoll(
                    dice_type="d6", values=roll.values,
                    total=roll.total, label=f"Demands: {char_name}",
                )],
            ))
            return events
        else:
            events.append(TurnEvent(
                step=11, event_type=TurnEventType.MORALE,
                description=(
                    f"{char_name} rolled {roll.total} + Savvy {char.savvy} = "
                    f"{result} (<5). Demands continue."
                ),
            ))

    return events


def _get_political_upheaval(state: GameState) -> int:
    """Get the current Political Upheaval value from state."""
    return state.flags.political_upheaval


def _set_political_upheaval(state: GameState, value: int) -> None:
    """Set the Political Upheaval value on state."""
    state.flags.political_upheaval = value

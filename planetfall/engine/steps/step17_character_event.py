"""Step 17: Character Event — Roll on the Character Event table (page 70).

This uses the MECHANICAL character event table with real game effects.
The optional Character Roleplay Events table (page 72) is handled
separately via step17a_roleplay_event.py.
"""

from __future__ import annotations

import random

from planetfall.engine.campaign.augmentation import has_augmentation
from planetfall.engine.dice import roll_d6
from planetfall.engine.models import (
    GameState, Loyalty, TurnEvent, TurnEventType, DiceRoll,
)
from planetfall.engine.tables.character_events_mechanical import (
    CHARACTER_EVENT_TABLE,
)
from planetfall.engine.tables.injuries import CHARACTER_INJURY_TABLE
from planetfall.engine.utils import format_display


_LOYALTY_LEVELS = [Loyalty.DISLOYAL, Loyalty.COMMITTED, Loyalty.LOYAL]


def _increase_loyalty(char) -> str:
    """Increase character loyalty by one step. Returns description."""
    idx = _LOYALTY_LEVELS.index(char.loyalty) if char.loyalty in _LOYALTY_LEVELS else 1
    if idx < len(_LOYALTY_LEVELS) - 1:
        old = char.loyalty.value
        char.loyalty = _LOYALTY_LEVELS[idx + 1]
        return f"{char.name} Loyalty {old} → {char.loyalty.value}"
    return ""


def _decrease_loyalty(char, state: GameState | None = None) -> str:
    """Decrease character loyalty by one step. Returns description.

    If the colony has the Psionic Cohesion augmentation, rolls 1D6;
    on 5-6 the loyalty loss is prevented.
    """
    # Psionic Cohesion protection
    if state and has_augmentation(state, "psionic_cohesion"):
        check = roll_d6(f"Psionic Cohesion: {char.name}")
        if check.total >= 5:
            return (
                f"{char.name} would lose Loyalty, but Psionic Cohesion "
                f"prevents it (rolled {check.total})"
            )

    idx = _LOYALTY_LEVELS.index(char.loyalty) if char.loyalty in _LOYALTY_LEVELS else 1
    if idx > 0:
        old = char.loyalty.value
        char.loyalty = _LOYALTY_LEVELS[idx - 1]
        return f"{char.name} Loyalty {old} → {char.loyalty.value}"
    return ""


def roll_character_event(char_name: str) -> tuple:
    """Roll on the Character Event table without applying effects.

    Returns (roll_result, entry) for reroll support.
    """
    return CHARACTER_EVENT_TABLE.roll_on_table(f"Character Event: {char_name}")


def apply_character_event(
    state: GameState,
    char,
    roll_result,
    entry,
    last_mission_victory: bool | None = None,
) -> list[TurnEvent]:
    """Apply a character event result to state. Returns events."""
    effects = entry.effects or {}
    event_id = entry.result_id

    desc = (
        f"{char.name}: Roll {roll_result.total} — "
        f"{format_display(event_id)}. "
        f"{entry.description}"
    )

    all_dice = [DiceRoll(
        dice_type="d100", values=[roll_result.total],
        total=roll_result.total, label=f"Character Event: {char.name}",
    )]

    # Apply mechanical effects
    effect_desc, extra_dice = _apply_event_effects(
        state, char, event_id, effects, last_mission_victory
    )
    all_dice.extend(extra_dice)
    if effect_desc:
        desc += f" Effect: {effect_desc}"

    # Build narrative context for AI consumption
    narrative_ctx = {
        "event_type": event_id,
        "character": char.name,
        "character_class": char.char_class.value,
    }
    if char.background_motivation:
        narrative_ctx["motivation"] = char.background_motivation

    return [TurnEvent(
        step=17,
        event_type=TurnEventType.CHARACTER_EVENT,
        description=desc,
        dice_rolls=all_dice,
        state_changes={
            "character": char.name,
            "event": event_id,
            "narrative_context": narrative_ctx,
            "mechanical_effects": effect_desc,
        },
    )]


def execute(
    state: GameState,
    last_mission_victory: bool | None = None,
) -> list[TurnEvent]:
    """Pick a random character and roll a mechanical event for them.

    Args:
        last_mission_victory: Whether the last mission was a victory
            (used by personal_conviction and losing_faith events).
    """
    if not state.characters:
        return [TurnEvent(
            step=17,
            event_type=TurnEventType.CHARACTER_EVENT,
            description="No characters on roster for events.",
        )]

    char = random.choice(state.characters)
    roll_result, entry = roll_character_event(char.name)
    return apply_character_event(state, char, roll_result, entry, last_mission_victory)


def _apply_event_effects(
    state: GameState,
    char,
    event_id: str,
    effects: dict,
    last_mission_victory: bool | None,
) -> tuple[str, list[DiceRoll]]:
    """Apply mechanical effects from the Character Event table.

    Returns (description_of_changes, extra_dice_rolls).
    """
    result_parts: list[str] = []
    extra_dice: list[DiceRoll] = []

    # --- Simple XP gain ---
    if effects.get("xp") and event_id not in ("minor_promotion", "making_friends"):
        char.xp += effects["xp"]
        result_parts.append(f"{char.name} +{effects['xp']} XP")

    # --- Minor promotion: +1 Loyalty, +1 XP (or +2 XP if already Loyal) ---
    if event_id == "minor_promotion":
        if char.loyalty == Loyalty.LOYAL:
            char.xp += effects.get("loyal_bonus_xp", 2)
            result_parts.append(f"{char.name} already Loyal, +2 XP")
        else:
            msg = _increase_loyalty(char)
            if msg:
                result_parts.append(msg)
            char.xp += effects.get("xp", 1)
            result_parts.append(f"{char.name} +1 XP")

    # --- Personal investigation: +1 Enemy Info ---
    if event_id == "personal_investigation":
        if state.enemies.tactical_enemies:
            enemy = random.choice(state.enemies.tactical_enemies)
            enemy.enemy_info_count += 1
            result_parts.append(f"+1 Enemy Information ({enemy.name})")
        else:
            result_parts.append("No tactical enemies to investigate")

    # --- Something in the water: extend sick bay ---
    if event_id == "something_in_the_water":
        if char.sick_bay_turns > 0:
            char.sick_bay_turns += 1
            result_parts.append(
                f"{char.name} recovery extended by 1 turn "
                f"(now {char.sick_bay_turns} turns)"
            )
        else:
            result_parts.append(f"{char.name} has a tummy ache but is fine")

    # --- R&R: gone 2 turns, full heal, disloyal check ---
    if event_id == "r_and_r":
        char.sick_bay_turns = 2  # Gone for 2 turns (re-uses sick bay mechanic)
        result_parts.append(f"{char.name} gone for 2 campaign turns (R&R)")
        if char.loyalty == Loyalty.DISLOYAL:
            d6 = roll_d6(f"R&R disloyal check: {char.name}")
            extra_dice.append(DiceRoll(
                dice_type="d6", values=d6.values,
                total=d6.total, label="R&R disloyal check",
            ))
            if d6.total <= 2:
                # Character does not return — death compensation
                state.characters.remove(char)
                state.colony.resources.story_points += 1
                result_parts.append(
                    f"D6={d6.total}: {char.name} does not return! +1 Story Point."
                )
            elif d6.total == 6:
                char.loyalty = Loyalty.COMMITTED
                result_parts.append(
                    f"D6={d6.total}: {char.name} becomes Committed"
                )
            else:
                result_parts.append(
                    f"D6={d6.total}: {char.name} remains Disloyal"
                )

    # --- Change of assignment: player choice (auto-decline for now) ---
    if event_id == "change_of_assignment":
        # In automated play, default to declining (gains loyalty)
        msg = _increase_loyalty(char)
        if msg:
            result_parts.append(f"{char.name} declines assignment. {msg}")
        else:
            result_parts.append(f"{char.name} declines assignment (already Loyal)")

    # --- Disputes with leadership: -1 Loyalty ---
    if event_id == "disputes_with_leadership":
        msg = _decrease_loyalty(char, state)
        if msg:
            result_parts.append(msg)
        else:
            result_parts.append(f"{char.name} already Disloyal")

    # --- Commitment to the cause: +1 Loyalty ---
    if event_id == "commitment_to_the_cause":
        msg = _increase_loyalty(char)
        if msg:
            result_parts.append(msg)
        else:
            result_parts.append(f"{char.name} already Loyal")

    # --- Dispute: two characters can't both deploy next turn ---
    if event_id == "dispute":
        others = [c for c in state.characters if c.name != char.name]
        if others:
            other = random.choice(others)
            result_parts.append(
                f"{char.name} and {other.name} cannot both deploy "
                f"next campaign turn (unless Pitched Battle)"
            )
            # Store the dispute on state for the orchestrator to enforce
            if not hasattr(state, "_disputes"):
                state._disputes = []

    # --- Personal calibrations: +1 hit bonus next mission ---
    if event_id == "personal_calibrations":
        char.notes = (char.notes + " [CALIBRATION: +1 hit bonus next mission]").strip()
        result_parts.append(
            f"{char.name} gets +1 hit bonus on a weapon next mission"
        )

    # --- Sickness: 2 turns in sick bay ---
    if event_id == "sickness":
        char.sick_bay_turns = max(char.sick_bay_turns, 2)
        result_parts.append(f"{char.name} is sick — 2 turns in Sick Bay")

    # --- Making friends: +1 XP each, loyalty check ---
    if event_id == "making_friends":
        others = [c for c in state.characters if c.name != char.name]
        if others:
            friend = random.choice(others)
            char.xp += 1
            friend.xp += 1
            result_parts.append(f"{char.name} +1 XP, {friend.name} +1 XP")
            # Each rolls D6; 5-6 = +1 Loyalty
            for c in [char, friend]:
                d6 = roll_d6(f"Making friends loyalty check: {c.name}")
                extra_dice.append(DiceRoll(
                    dice_type="d6", values=d6.values,
                    total=d6.total, label=f"Friendship loyalty: {c.name}",
                ))
                if d6.total >= 5:
                    msg = _increase_loyalty(c)
                    if msg:
                        result_parts.append(f"D6={d6.total}: {msg}")
        else:
            char.xp += 1
            result_parts.append(f"{char.name} +1 XP (no one else on roster)")

    # --- Personal life achievement: +1 Story Point, +1 Morale ---
    if event_id == "personal_life_achievement":
        state.colony.resources.story_points += 1
        state.colony.morale += 1
        result_parts.append("+1 Story Point, +1 Colony Morale")

    # --- Excellent health: reduce recovery by 2 ---
    if event_id == "excellent_health":
        if char.sick_bay_turns > 0:
            old = char.sick_bay_turns
            char.sick_bay_turns = max(0, char.sick_bay_turns - 2)
            result_parts.append(
                f"{char.name} recovery reduced by 2 "
                f"({old} → {char.sick_bay_turns} turns)"
            )
        else:
            char.notes = (char.notes + " [EXCELLENT_HEALTH: saved]").strip()
            result_parts.append(
                f"{char.name} not injured — health bonus saved"
            )

    # --- Accident: roll injury table (death → 5 turns) ---
    if event_id == "accident":
        inj_roll, inj_entry = CHARACTER_INJURY_TABLE.roll_on_table(
            f"Accident injury: {char.name}"
        )
        extra_dice.append(DiceRoll(
            dice_type="d100", values=[inj_roll.total],
            total=inj_roll.total, label=f"Accident injury: {char.name}",
        ))
        inj_effects = inj_entry.effects or {}
        if inj_effects.get("dead"):
            # Death overridden to 5 turns recovery
            char.sick_bay_turns = 5
            result_parts.append(
                f"Injury roll {inj_roll.total}: Would be dead — "
                f"5 turns recovery instead"
            )
        elif "sick_bay_turns" in inj_effects:
            char.sick_bay_turns = inj_effects["sick_bay_turns"]
            result_parts.append(
                f"Injury roll {inj_roll.total}: "
                f"{char.sick_bay_turns} turns in Sick Bay"
            )
        elif inj_effects.get("xp"):
            char.xp += inj_effects["xp"]
            result_parts.append(
                f"Injury roll {inj_roll.total}: School of Hard Knocks, +1 XP"
            )
        else:
            result_parts.append(f"Injury roll {inj_roll.total}: Okay")

    # --- Personal reflection: double XP next mission ---
    if event_id == "personal_reflection":
        char.notes = (char.notes + " [DOUBLE_XP: next mission]").strip()
        result_parts.append(f"{char.name} earns double XP next mission")

    # --- Personal conviction: +1 Loyalty if last mission was victory ---
    if event_id == "personal_conviction":
        if last_mission_victory:
            msg = _increase_loyalty(char)
            if msg:
                result_parts.append(f"Last mission was a success. {msg}")
            else:
                result_parts.append(f"Last mission success, already Loyal")
        else:
            result_parts.append("Last mission was not a success — no effect")

    # --- Losing faith: -1 Loyalty if last mission was defeat ---
    if event_id == "losing_faith":
        if last_mission_victory is False:
            msg = _decrease_loyalty(char, state)
            if msg:
                result_parts.append(f"Last mission was a failure. {msg}")
            else:
                result_parts.append(f"Last mission failed, already Disloyal")
        else:
            result_parts.append("Last mission was not a failure — no effect")

    # --- Personal tragedy: forfeit XP next turn ---
    if event_id == "personal_tragedy":
        char.notes = (char.notes + " [FORFEIT_XP: next turn]").strip()
        result_parts.append(
            f"{char.name} forfeits all XP earned next campaign turn"
        )

    return "; ".join(result_parts), extra_dice

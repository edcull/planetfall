"""Step 10: Experience Progression — Award XP and roll advancements.

Rules (pages 67-68):
- +1 XP for participating in battle
- +1 XP for not becoming a casualty
- +1 XP for directly killing an enemy Boss or Leader (once per battle)
- Spend 5 XP to roll D100 on Advancement table
- OR buy specific stats at fixed XP costs
- OR take alternate options (loyalty, RP for scientists, RM for scouts)
"""

from __future__ import annotations

from planetfall.engine.models import (
    CharacterClass, GameState, Loyalty, TurnEvent, TurnEventType, DiceRoll,
    STARTING_PROFILES,
)
from planetfall.engine.tables.advancement import ADVANCEMENT_TABLE
from planetfall.engine.dice import roll_d6

XP_PER_ADVANCEMENT = 5

# XP Buy costs (rules page 68)
XP_BUY_COSTS = {
    "reactions": 7,
    "combat_skill": 7,
    "speed": 5,
    "toughness": 6,
    "savvy": 5,
}

# Max values for each stat
STAT_MAXIMUMS = {
    "reactions": 6,
    "combat_skill": 5,
    "speed": 8,
    "toughness": 6,
    "savvy": 5,
}

# Speed starting values by class for first-time bonus detection
STARTING_PROFILES_SPEED = {
    cls: p["speed"] for cls, p in STARTING_PROFILES.items()
}

_LOYALTY_LEVELS = [Loyalty.DISLOYAL, Loyalty.COMMITTED, Loyalty.LOYAL]


def award_mission_xp(
    state: GameState,
    deployed: list[str],
    casualties: list[str],
    killed_leader: list[str] | None = None,
) -> list[TurnEvent]:
    """Award XP to deployed characters.

    Args:
        deployed: Names of characters who participated.
        casualties: Names of characters who became casualties.
        killed_leader: Names of characters who directly killed an enemy
            Boss or Leader. Each character gets +1 XP max once per battle.
    """
    events = []
    killed_leader = killed_leader or []

    for char in state.characters:
        if char.name not in deployed:
            continue
        xp_gained = 1  # participation
        reasons = ["participation"]

        if char.name not in casualties:
            xp_gained += 1
            reasons.append("survived")

        # Capped at +1 per battle (rules: "once per battle")
        if char.name in killed_leader:
            xp_gained += 1
            reasons.append("leader/boss kill")

        # Double XP from personal_reflection (step 17)
        if "[DOUBLE_XP: next mission]" in (char.notes or ""):
            xp_gained *= 2
            reasons.append("DOUBLE XP (personal reflection)")
            char.notes = char.notes.replace("[DOUBLE_XP: next mission]", "").strip()

        # Forfeit XP from personal_tragedy (step 17)
        if "[FORFEIT_XP: next turn]" in (char.notes or ""):
            xp_gained = 0
            reasons = ["FORFEITED (personal tragedy)"]
            char.notes = char.notes.replace("[FORFEIT_XP: next turn]", "").strip()

        char.xp += xp_gained
        events.append(TurnEvent(
            step=10,
            event_type=TurnEventType.EXPERIENCE,
            description=(
                f"{char.name}: +{xp_gained} XP ({', '.join(reasons)}). "
                f"Total: {char.xp} XP."
            ),
        ))

    return events


def roll_civvy_heroic_promotion(
    state: GameState,
    civilian_deploy: int,
    casualties: list[str],
) -> tuple[list[TurnEvent], bool, int]:
    """Roll for Civvy Heroic Promotion (rules page 67).

    If any civvies participated, pick one who didn't become a casualty
    and roll 2D6. On 10-12, they are promoted to the grunt roster.

    Returns (events, promoted, roll_total).
    """
    events = []
    if civilian_deploy <= 0:
        return events, False, 0

    # At least one civvy must have survived
    civvy_casualties = sum(1 for c in casualties if c.startswith("Civvy"))
    civvy_survivors = civilian_deploy - civvy_casualties
    if civvy_survivors <= 0:
        return events, False, 0

    die1 = roll_d6("Civvy heroic promotion die 1")
    die2 = roll_d6("Civvy heroic promotion die 2")
    total = die1.total + die2.total
    promoted = total >= 10

    if promoted:
        state.colony.grunts += 1
        events.append(TurnEvent(
            step=10,
            event_type=TurnEventType.EXPERIENCE,
            description=(
                f"Civvy Heroic Promotion: Rolled {total} (2D6) — "
                f"Promoted to grunt roster! (+1 grunt)"
            ),
            dice_rolls=[
                DiceRoll(dice_type="d6", values=[die1.total], total=die1.total, label="Heroic promotion"),
                DiceRoll(dice_type="d6", values=[die2.total], total=die2.total, label="Heroic promotion"),
            ],
        ))
    else:
        events.append(TurnEvent(
            step=10,
            event_type=TurnEventType.EXPERIENCE,
            description=(
                f"Civvy Heroic Promotion: Rolled {total} (2D6) — "
                f"Not promoted (need 10+)."
            ),
            dice_rolls=[
                DiceRoll(dice_type="d6", values=[die1.total], total=die1.total, label="Heroic promotion"),
                DiceRoll(dice_type="d6", values=[die2.total], total=die2.total, label="Heroic promotion"),
            ],
        ))

    return events, promoted, total


def roll_advancement(state: GameState, character_name: str) -> list[TurnEvent]:
    """Spend 5 XP to roll D100 on the Advancement table.

    If the rolled stat is already maxed, the player may select
    any other advance of choice (handled by orchestrator).
    """
    events = []
    char = _find_character(state, character_name)

    if char is None or char.xp < XP_PER_ADVANCEMENT:
        return events

    char.xp -= XP_PER_ADVANCEMENT
    roll_result, entry = ADVANCEMENT_TABLE.roll_on_table(
        f"Advancement: {character_name}"
    )
    effects = entry.effects or {}
    stat = effects.get("stat", "")
    max_val = effects.get("max", 99)

    current_val = getattr(char, stat, 0) if stat else 0

    if current_val >= max_val:
        desc = (
            f"{character_name}: Roll {roll_result.total} — {stat} "
            f"already at max ({max_val}). Player may select any "
            f"other advance."
        )
    else:
        bonus = _get_speed_bonus(char, effects) if stat == "speed" else effects.get("bonus", 1)
        new_val = min(current_val + bonus, max_val)
        setattr(char, stat, new_val)
        desc = (
            f"{character_name}: Roll {roll_result.total} — "
            f"{stat.replace('_', ' ').title()} +{bonus} "
            f"({current_val} → {new_val})."
        )

        # Note trade options
        trade_class = effects.get("trade_class")
        trade_stat = effects.get("trade_stat")
        if trade_class and char.char_class.value == trade_class:
            desc += f" (Could trade for {trade_stat} instead.)"

    events.append(TurnEvent(
        step=10,
        event_type=TurnEventType.EXPERIENCE,
        description=desc,
        dice_rolls=[DiceRoll(
            dice_type="d100", values=[roll_result.total],
            total=roll_result.total, label=f"Advancement: {character_name}",
        )],
    ))
    return events


def buy_advancement(
    state: GameState,
    character_name: str,
    stat: str,
) -> list[TurnEvent]:
    """Buy a specific stat upgrade at fixed XP cost (rules page 68).

    Each ability score increases by 1 point per purchase.
    """
    events = []
    char = _find_character(state, character_name)

    if char is None:
        return events

    cost = XP_BUY_COSTS.get(stat)
    if cost is None:
        return events

    if char.xp < cost:
        events.append(TurnEvent(
            step=10,
            event_type=TurnEventType.EXPERIENCE,
            description=(
                f"{character_name}: Cannot buy {stat} upgrade "
                f"(need {cost} XP, have {char.xp})."
            ),
        ))
        return events

    max_val = STAT_MAXIMUMS.get(stat, 99)
    current_val = getattr(char, stat, 0)

    if current_val >= max_val:
        events.append(TurnEvent(
            step=10,
            event_type=TurnEventType.EXPERIENCE,
            description=(
                f"{character_name}: {stat} already at max ({max_val})."
            ),
        ))
        return events

    char.xp -= cost
    bonus = 1
    if stat == "speed":
        bonus = _get_speed_bonus_for_buy(char)

    new_val = min(current_val + bonus, max_val)
    setattr(char, stat, new_val)

    events.append(TurnEvent(
        step=10,
        event_type=TurnEventType.EXPERIENCE,
        description=(
            f"{character_name}: Bought {stat.replace('_', ' ').title()} "
            f"+{bonus} for {cost} XP ({current_val} → {new_val}). "
            f"Remaining: {char.xp} XP."
        ),
    ))
    return events


def alternate_advancement(
    state: GameState,
    character_name: str,
    choice: str,
) -> list[TurnEvent]:
    """Use an advancement for an alternate option (rules page 68).

    Choices:
    - "loyalty": Increase Loyalty one level (any class)
    - "research_points": Scientist gains 3 RP
    - "raw_materials": Scout gains 3 Raw Materials
    """
    events = []
    char = _find_character(state, character_name)

    if char is None or char.xp < XP_PER_ADVANCEMENT:
        return events

    if choice == "loyalty":
        idx = _LOYALTY_LEVELS.index(char.loyalty) if char.loyalty in _LOYALTY_LEVELS else 1
        if idx >= len(_LOYALTY_LEVELS) - 1:
            events.append(TurnEvent(
                step=10,
                event_type=TurnEventType.EXPERIENCE,
                description=f"{character_name}: Already Loyal, cannot increase.",
            ))
            return events
        char.xp -= XP_PER_ADVANCEMENT
        old = char.loyalty.value
        char.loyalty = _LOYALTY_LEVELS[idx + 1]
        events.append(TurnEvent(
            step=10,
            event_type=TurnEventType.EXPERIENCE,
            description=(
                f"{character_name}: Spent {XP_PER_ADVANCEMENT} XP — "
                f"Loyalty {old} → {char.loyalty.value}."
            ),
        ))

    elif choice == "research_points":
        if char.char_class != CharacterClass.SCIENTIST:
            events.append(TurnEvent(
                step=10,
                event_type=TurnEventType.EXPERIENCE,
                description=f"{character_name}: Only scientists can gain RP.",
            ))
            return events
        char.xp -= XP_PER_ADVANCEMENT
        state.colony.resources.research_points += 3
        events.append(TurnEvent(
            step=10,
            event_type=TurnEventType.EXPERIENCE,
            description=(
                f"{character_name}: Spent {XP_PER_ADVANCEMENT} XP — "
                f"+3 Research Points (scientist)."
            ),
        ))

    elif choice == "raw_materials":
        if char.char_class != CharacterClass.SCOUT:
            events.append(TurnEvent(
                step=10,
                event_type=TurnEventType.EXPERIENCE,
                description=f"{character_name}: Only scouts can gain RM.",
            ))
            return events
        char.xp -= XP_PER_ADVANCEMENT
        state.colony.resources.raw_materials += 3
        events.append(TurnEvent(
            step=10,
            event_type=TurnEventType.EXPERIENCE,
            description=(
                f"{character_name}: Spent {XP_PER_ADVANCEMENT} XP — "
                f"+3 Raw Materials (scout)."
            ),
        ))

    return events


def _find_character(state: GameState, name: str):
    """Find a character by name."""
    for c in state.characters:
        if c.name == name:
            return c
    return None


def _get_speed_bonus(char, effects: dict) -> int:
    """Get the speed bonus (first time +2, subsequent +1)."""
    if char.speed == STARTING_PROFILES_SPEED.get(char.char_class, 4):
        return effects.get("first_bonus", 2)
    return effects.get("subsequent_bonus", 1)


def _get_speed_bonus_for_buy(char) -> int:
    """Get speed bonus for XP buy (first time +2, subsequent +1)."""
    if char.speed == STARTING_PROFILES_SPEED.get(char.char_class, 4):
        return 2
    return 1

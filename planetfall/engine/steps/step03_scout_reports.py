"""Step 3: Scout Reports — Scout exploration and discovery rolls."""

from __future__ import annotations

import random

from planetfall.engine.dice import roll_2d6_pick_lowest, roll_d6, RollResult
from planetfall.engine.models import (
    GameState, TurnEvent, TurnEventType, DiceRoll, SectorStatus,
)
from planetfall.engine.tables.scout_discovery import SCOUT_DISCOVERY_TABLE
from planetfall.engine.utils import format_display


def roll_sector_survey() -> tuple[RollResult, RollResult]:
    """Roll 2D6-pick-lowest twice for Resource and Hazard levels."""
    resource = roll_2d6_pick_lowest("Sector Resource Level")
    hazard = roll_2d6_pick_lowest("Sector Hazard Level")
    return resource, hazard


def _check_ancient_sign_doubles(
    state: GameState, sector, resource_roll: RollResult, hazard_roll: RollResult,
) -> bool:
    """Check if survey rolls contain double 4/5/6 → Ancient Signs.

    Ancient signs are abstract counters (not map markers). When found,
    increment the count and check if enough signs locate an Ancient Site.
    Returns True if an ancient sign was discovered.
    """
    for roll in (resource_roll, hazard_roll):
        if len(roll.values) == 2 and roll.values[0] == roll.values[1] and roll.values[0] >= 4:
            state.campaign.ancient_signs_count += 1
            return True
    return False


def execute_scout_explore(state: GameState, sector_id: int) -> list[TurnEvent]:
    """Perform the mandatory scout exploration of a sector.

    Args:
        sector_id: Which sector to explore.
    """
    events = []
    sector = state.get_sector(sector_id)

    if sector is None:
        events.append(TurnEvent(
            step=3,
            event_type=TurnEventType.SCOUT_REPORT,
            description=f"Invalid sector ID: {sector_id}",
        ))
        return events

    resource_roll, hazard_roll = roll_sector_survey()
    sector.resource_level = resource_roll.total
    sector.hazard_level = hazard_roll.total

    if sector.status == SectorStatus.UNEXPLORED:
        sector.status = SectorStatus.EXPLORED

    desc = (
        f"Sector {sector_id} surveyed. "
        f"Resource Level: {resource_roll.total}, "
        f"Hazard Level: {hazard_roll.total}."
    )

    # Double 4, 5, or 6 on either survey roll → Ancient Signs
    got_sign = _check_ancient_sign_doubles(state, sector, resource_roll, hazard_roll)
    if got_sign:
        desc += f" Double rolled — Ancient Signs discovered!"

    events.append(TurnEvent(
        step=3,
        event_type=TurnEventType.SCOUT_REPORT,
        description=desc,
        dice_rolls=[
            DiceRoll(
                dice_type="2d6_low", values=resource_roll.values,
                total=resource_roll.total, label="Resource Level",
            ),
            DiceRoll(
                dice_type="2d6_low", values=hazard_roll.values,
                total=hazard_roll.total, label="Hazard Level",
            ),
        ],
    ))

    # Immediately roll to see if the sign locates an Ancient Site
    if got_sign:
        from planetfall.engine.campaign.ancient_signs import check_ancient_signs
        events.extend(check_ancient_signs(state))

    return events


def _pick_random_sector(state: GameState, exclude_colony: bool = True) -> int | None:
    """Pick a random non-colony sector ID, or None if no sectors exist."""
    candidates = [
        s for s in state.campaign_map.sectors
        if not exclude_colony or s.sector_id != state.campaign_map.colony_sector_id
    ]
    if not candidates:
        return None
    return random.choice(candidates).sector_id


def _get_sector(state: GameState, sector_id: int):
    """Look up a sector by ID."""
    return state.get_sector(sector_id)


def _apply_exploration_report(
    state: GameState, sector_id: int | None = None,
) -> tuple[str, list[DiceRoll]]:
    """Exploration Report: explore a specific unexplored sector.

    Args:
        sector_id: Which sector to explore. If None, picks randomly (for auto mode).
    """
    unexplored = [
        s for s in state.campaign_map.sectors
        if s.status == SectorStatus.UNEXPLORED
        and s.sector_id != state.campaign_map.colony_sector_id
    ]
    if not unexplored:
        return "No unexplored sectors remaining.", []

    if sector_id is not None:
        sector = next((s for s in unexplored if s.sector_id == sector_id), None)
        if not sector:
            return f"Sector {sector_id} is not available for exploration.", []
    else:
        sector = random.choice(unexplored)

    resource_roll, hazard_roll = roll_sector_survey()
    sector.resource_level = resource_roll.total
    sector.hazard_level = hazard_roll.total
    sector.status = SectorStatus.EXPLORED

    dice = [
        DiceRoll(dice_type="2d6_low", values=resource_roll.values,
                 total=resource_roll.total, label="Resource Level"),
        DiceRoll(dice_type="2d6_low", values=hazard_roll.values,
                 total=hazard_roll.total, label="Hazard Level"),
    ]
    desc = (
        f"Sector {sector.sector_id} explored: "
        f"Resource {resource_roll.total}, Hazard {hazard_roll.total}."
    )
    if _check_ancient_sign_doubles(state, sector, resource_roll, hazard_roll):
        desc += " Double rolled — Ancient Signs discovered!"
    return desc, dice


def _apply_revised_survey(state: GameState) -> tuple[str, list[DiceRoll]]:
    """Revised Survey: random sector, effect depends on status."""
    non_colony = [
        s for s in state.campaign_map.sectors
        if s.sector_id != state.campaign_map.colony_sector_id
    ]
    if not non_colony:
        return "No sectors available for revised survey.", []

    sector = random.choice(non_colony)
    dice: list[DiceRoll] = []

    if sector.status == SectorStatus.UNEXPLORED:
        # Not yet explored — generate normally
        resource_roll, hazard_roll = roll_sector_survey()
        sector.resource_level = resource_roll.total
        sector.hazard_level = hazard_roll.total
        sector.status = SectorStatus.EXPLORED
        dice = [
            DiceRoll(dice_type="2d6_low", values=resource_roll.values,
                     total=resource_roll.total, label="Resource Level"),
            DiceRoll(dice_type="2d6_low", values=hazard_roll.values,
                     total=hazard_roll.total, label="Hazard Level"),
        ]
        desc = (
            f"Sector {sector.sector_id} surveyed (was unknown): "
            f"Resource {resource_roll.total}, Hazard {hazard_roll.total}."
        )
        if _check_ancient_sign_doubles(state, sector, resource_roll, hazard_roll):
            desc += " Double rolled — Ancient Signs discovered!"
    elif sector.status == SectorStatus.EXPLORED:
        # Explored but not exploited — increase resource by +1
        sector.resource_level += 1
        desc = (
            f"Sector {sector.sector_id} revised (was {sector.status.value}): "
            f"Resource level increased to {sector.resource_level}."
        )
    elif sector.status == SectorStatus.EXPLOITED:
        # Already exploited — regenerate, can exploit again
        resource_roll, hazard_roll = roll_sector_survey()
        sector.resource_level = resource_roll.total
        sector.hazard_level = hazard_roll.total
        sector.status = SectorStatus.EXPLORED  # Can be exploited again
        dice = [
            DiceRoll(dice_type="2d6_low", values=resource_roll.values,
                     total=resource_roll.total, label="Resource Level"),
            DiceRoll(dice_type="2d6_low", values=hazard_roll.values,
                     total=hazard_roll.total, label="Hazard Level"),
        ]
        desc = (
            f"Sector {sector.sector_id} re-surveyed (was exploited): "
            f"Resource {resource_roll.total}, Hazard {hazard_roll.total}. "
            f"Can be exploited again."
        )
        if _check_ancient_sign_doubles(state, sector, resource_roll, hazard_roll):
            desc += " Double rolled — Ancient Signs discovered!"
    else:
        desc = f"Sector {sector.sector_id}: no change."

    return desc, dice


def _apply_ancient_sign(state: GameState) -> str:
    """Ancient Sign: place on a random sector on the map.

    The sign is a map marker — completing a mission in that sector
    collects the sign (increments count, removes marker).
    """
    non_colony = [
        s for s in state.campaign_map.sectors
        if s.sector_id != state.campaign_map.colony_sector_id
        and not s.has_ancient_sign
    ]
    if not non_colony:
        return "No eligible sectors for Ancient Sign."

    sector = random.choice(non_colony)
    sector.has_ancient_sign = True
    return f"Ancient Sign placed in Sector {sector.sector_id}."


def _apply_recon_patrol(state: GameState) -> str:
    """Recon Patrol: add enemy info to a tactical enemy."""
    active_enemies = [
        e for e in state.enemies.tactical_enemies if not e.defeated
    ]
    if not active_enemies:
        return "No tactical enemies present — no effect."

    enemy = random.choice(active_enemies)
    enemy.enemy_info_count += 1
    return (
        f"Recon intel on {enemy.name}: "
        f"Enemy Information now {enemy.enemy_info_count}."
    )


def roll_scout_discovery() -> tuple:
    """Roll on the Scout Discovery table without applying effects.

    Returns (roll_result, entry) for reroll support.
    """
    return SCOUT_DISCOVERY_TABLE.roll_on_table("Scout Discovery")


def apply_scout_discovery(
    state: GameState,
    roll_result,
    entry,
    assigned_scout: str | None = None,
) -> list[TurnEvent]:
    """Apply the scout discovery result to state. Returns events."""
    events = []
    effects = entry.effects or {}

    desc = (
        f"Scout Discovery roll: {roll_result.total} — "
        f"{format_display(entry.result_id)}. "
        f"{entry.description}"
    )
    extra_dice: list[DiceRoll] = []
    narrative_ctx: dict = {
        "discovery_type": entry.result_id,
        "assigned_scout": assigned_scout,
    }

    # --- Apply effects by type ---

    if entry.result_id == "good_practice" and assigned_scout:
        xp_gain = effects.get("scout_xp", 2)
        for char in state.characters:
            if char.name == assigned_scout:
                char.xp += xp_gain
                desc += f" {assigned_scout} gains +{xp_gain} XP."
                narrative_ctx["xp_awarded"] = xp_gain
                break

    elif entry.result_id == "sos_signal":
        narrative_ctx["pending_choice"] = "rescue_or_morale"
        narrative_ctx["decline_morale_penalty"] = effects.get("decline_morale", -3)

    elif entry.result_id == "scout_down":
        narrative_ctx["pending_choice"] = "scout_down_or_escape"
        narrative_ctx["scout_at_risk"] = assigned_scout

    elif entry.result_id == "exploration_report":
        narrative_ctx["pending_choice"] = "exploration_report"

    elif entry.result_id == "recon_patrol":
        extra_desc = _apply_recon_patrol(state)
        desc += f" {extra_desc}"

    elif entry.result_id == "ancient_sign":
        extra_desc = _apply_ancient_sign(state)
        desc += f" {extra_desc}"
        narrative_ctx["ancient_sign_placed"] = True

    elif entry.result_id == "revised_survey":
        extra_desc, extra_dice = _apply_revised_survey(state)
        desc += f" {extra_desc}"

    all_dice = [
        DiceRoll(
            dice_type="d100", values=[roll_result.total],
            total=roll_result.total, label="Scout Discovery",
        ),
    ] + extra_dice

    events.append(TurnEvent(
        step=3,
        event_type=TurnEventType.SCOUT_REPORT,
        description=desc,
        dice_rolls=all_dice,
        state_changes={
            "discovery": entry.result_id,
            "effects": effects,
            "narrative_context": narrative_ctx,
        },
    ))

    # If a sign was collected (doubles during survey), check for Ancient Site location
    # Note: "ancient_sign" discovery places on map (not collected until mission there)
    _SIGN_COLLECTED_RESULTS = ("revised_survey", "exploration_report")
    if entry.result_id in _SIGN_COLLECTED_RESULTS and state.campaign.ancient_signs_count > 0:
        from planetfall.engine.campaign.ancient_signs import check_ancient_signs
        events.extend(check_ancient_signs(state))

    return events


def execute_scout_discovery(
    state: GameState,
    assigned_scout: str | None = None,
) -> list[TurnEvent]:
    """Roll on the Scout Discovery table and apply effects."""
    roll_result, entry = roll_scout_discovery()
    return apply_scout_discovery(state, roll_result, entry, assigned_scout)

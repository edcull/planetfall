"""Step 3: Scout Reports — Scout exploration and discovery rolls."""

from __future__ import annotations

import random

from planetfall.engine.dice import roll_2d6_pick_lowest, roll_d6, RollResult
from planetfall.engine.models import (
    GameState, TurnEvent, TurnEventType, DiceRoll, SectorStatus,
)
from planetfall.engine.tables.scout_discovery import SCOUT_DISCOVERY_TABLE


def roll_sector_survey() -> tuple[RollResult, RollResult]:
    """Roll 2D6-pick-lowest twice for Resource and Hazard levels."""
    resource = roll_2d6_pick_lowest("Sector Resource Level")
    hazard = roll_2d6_pick_lowest("Sector Hazard Level")
    return resource, hazard


def execute_scout_explore(state: GameState, sector_id: int) -> list[TurnEvent]:
    """Perform the mandatory scout exploration of a sector.

    Args:
        sector_id: Which sector to explore.
    """
    events = []
    sector = None
    for s in state.campaign_map.sectors:
        if s.sector_id == sector_id:
            sector = s
            break

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

    if sector.status == SectorStatus.UNKNOWN:
        sector.status = SectorStatus.INVESTIGATED

    events.append(TurnEvent(
        step=3,
        event_type=TurnEventType.SCOUT_REPORT,
        description=(
            f"Sector {sector_id} surveyed. "
            f"Resource Level: {resource_roll.total}, "
            f"Hazard Level: {hazard_roll.total}."
        ),
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
    for s in state.campaign_map.sectors:
        if s.sector_id == sector_id:
            return s
    return None


def _apply_exploration_report(
    state: GameState, sector_id: int | None = None,
) -> tuple[str, list[DiceRoll]]:
    """Exploration Report: explore a specific unexplored sector.

    Args:
        sector_id: Which sector to explore. If None, picks randomly (for auto mode).
    """
    unexplored = [
        s for s in state.campaign_map.sectors
        if s.status == SectorStatus.UNKNOWN
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
    sector.status = SectorStatus.INVESTIGATED

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

    if sector.status == SectorStatus.UNKNOWN:
        # Not yet explored — generate normally
        resource_roll, hazard_roll = roll_sector_survey()
        sector.resource_level = resource_roll.total
        sector.hazard_level = hazard_roll.total
        sector.status = SectorStatus.INVESTIGATED
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
    elif sector.status in (SectorStatus.INVESTIGATED, SectorStatus.EXPLORED):
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
    else:
        desc = f"Sector {sector.sector_id}: no change."

    return desc, dice


def _apply_ancient_sign(state: GameState) -> str:
    """Ancient Sign: mark a random sector."""
    non_colony = [
        s for s in state.campaign_map.sectors
        if s.sector_id != state.campaign_map.colony_sector_id
        and not s.has_ancient_sign
    ]
    if not non_colony:
        return "No eligible sectors for Ancient Sign."

    sector = random.choice(non_colony)
    sector.has_ancient_sign = True
    return f"Sector {sector.sector_id} now has an Ancient Sign."


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


def execute_scout_discovery(
    state: GameState,
    assigned_scout: str | None = None,
) -> list[TurnEvent]:
    """Roll on the Scout Discovery table and apply effects."""
    events = []
    roll_result, entry = SCOUT_DISCOVERY_TABLE.roll_on_table("Scout Discovery")
    effects = entry.effects or {}

    desc = (
        f"Scout Discovery roll: {roll_result.total} — "
        f"{entry.result_id.replace('_', ' ').title()}. "
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
        # Player must choose: play rescue mission or lose morale
        # Store the pending choice; orchestrator will prompt
        narrative_ctx["pending_choice"] = "rescue_or_morale"
        narrative_ctx["decline_morale_penalty"] = effects.get("decline_morale", -3)

    elif entry.result_id == "scout_down":
        # Player must choose: escape on foot (injury roll) or play mission
        narrative_ctx["pending_choice"] = "scout_down_or_escape"
        narrative_ctx["scout_at_risk"] = assigned_scout

    elif entry.result_id == "exploration_report":
        # Defer sector choice to orchestrator (player picks)
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
    return events

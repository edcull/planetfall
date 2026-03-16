"""Map resource extraction — exploit sectors for ongoing resource income.

Explored sectors with resources can be exploited. Exploited sectors
provide per-turn income but may attract enemy attention.
"""

from __future__ import annotations

from planetfall.engine.dice import roll_d6
from planetfall.engine.models import (
    ExtractionData, GameState, SectorStatus, TurnEvent, TurnEventType,
)


def get_exploitable_sectors(state: GameState) -> list[dict]:
    """Get sectors available for resource extraction."""
    results = []
    for sector in state.campaign_map.sectors:
        if sector.sector_id == state.campaign_map.colony_sector_id:
            continue
        if sector.status == SectorStatus.EXPLORED and sector.resource_level > 0:
            results.append({
                "sector_id": sector.sector_id,
                "resource_level": sector.resource_level,
                "hazard_level": sector.hazard_level,
                "status": sector.status.value,
            })
    return results


def get_active_extractions(state: GameState) -> list[dict]:
    """Get sectors currently being exploited."""
    extractions = dict(state.tracking.active_extractions)
    results = []
    for sid_str, data in extractions.items():
        results.append({
            "sector_id": int(sid_str),
            "resource_type": data.resource_type,
            "yield_per_turn": data.yield_per_turn,
            "turns_active": data.turns_active,
            "depleted": data.depleted,
        })
    return results


def start_extraction(
    state: GameState,
    sector_id: int,
    resource_type: str = "raw_materials",
) -> list[TurnEvent]:
    """Begin exploiting a sector for resources.

    Args:
        sector_id: Sector to exploit.
        resource_type: "raw_materials", "research_points", or "build_points".
    """
    sector = None
    for s in state.campaign_map.sectors:
        if s.sector_id == sector_id:
            sector = s
            break

    if not sector:
        return [TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=f"Sector {sector_id} not found.",
        )]

    if sector.status != SectorStatus.EXPLORED:
        return [TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=f"Sector {sector_id} must be explored first.",
        )]

    if sector.resource_level <= 0:
        return [TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=f"Sector {sector_id} has no extractable resources.",
        )]

    extractions = dict(state.tracking.active_extractions)
    sid_str = str(sector_id)

    if sid_str in extractions and not extractions[sid_str].depleted:
        return [TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=f"Sector {sector_id} is already being exploited.",
        )]

    sector.status = SectorStatus.EXPLOITED
    yield_per_turn = max(1, sector.resource_level // 2)

    extractions[sid_str] = ExtractionData(
        resource_type=resource_type,
        yield_per_turn=yield_per_turn,
        turns_active=0,
        max_turns=sector.resource_level * 3,
        depleted=False,
    )
    state.tracking.active_extractions = extractions

    return [TurnEvent(
        step=0, event_type=TurnEventType.NARRATIVE,
        description=(
            f"Resource extraction begun in sector {sector_id}. "
            f"Yield: {yield_per_turn} {resource_type.replace('_', ' ')} per turn. "
            f"Estimated duration: {sector.resource_level * 3} turns."
        ),
        state_changes={"sector_id": sector_id, "extraction": resource_type},
    )]


def process_extractions(state: GameState) -> list[TurnEvent]:
    """Process per-turn resource extraction from all active sectors.

    Called during the campaign turn (after step 2 or step 18).
    """
    extractions = dict(state.tracking.active_extractions)
    events = []

    for sid_str, data in list(extractions.items()):
        if data.depleted:
            continue

        data.turns_active += 1
        yield_amt = data.yield_per_turn
        rtype = data.resource_type

        # Apply yield
        if rtype == "raw_materials":
            state.colony.resources.raw_materials += yield_amt
        elif rtype == "research_points":
            state.colony.resources.research_points += yield_amt
        elif rtype == "build_points":
            state.colony.resources.build_points += yield_amt

        events.append(TurnEvent(
            step=0, event_type=TurnEventType.COLONY_EVENT,
            description=(
                f"Sector {sid_str} extraction: +{yield_amt} "
                f"{rtype.replace('_', ' ')}."
            ),
        ))

        # Check depletion
        if data.turns_active >= data.max_turns:
            data.depleted = True
            events.append(TurnEvent(
                step=0, event_type=TurnEventType.NARRATIVE,
                description=f"Sector {sid_str} resources depleted.",
            ))

        # Hazard check: extraction may attract enemies
        sector = None
        for s in state.campaign_map.sectors:
            if s.sector_id == int(sid_str):
                sector = s
                break
        if sector and sector.hazard_level > 0:
            hazard_roll = roll_d6(f"Extraction hazard (sector {sid_str})")
            if hazard_roll.total <= sector.hazard_level:
                events.append(TurnEvent(
                    step=0, event_type=TurnEventType.NARRATIVE,
                    description=(
                        f"Enemy activity detected near extraction site "
                        f"in sector {sid_str}!"
                    ),
                ))

    state.tracking.active_extractions = extractions
    return events


def stop_extraction(state: GameState, sector_id: int) -> list[TurnEvent]:
    """Stop exploiting a sector."""
    extractions = dict(state.tracking.active_extractions)
    sid_str = str(sector_id)

    if sid_str not in extractions:
        return [TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=f"No active extraction in sector {sector_id}.",
        )]

    del extractions[sid_str]
    state.tracking.active_extractions = extractions

    # Reset sector status
    for s in state.campaign_map.sectors:
        if s.sector_id == sector_id:
            s.status = SectorStatus.EXPLORED
            break

    return [TurnEvent(
        step=0, event_type=TurnEventType.NARRATIVE,
        description=f"Extraction stopped in sector {sector_id}.",
    )]

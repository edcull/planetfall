"""Building system — colony construction with Build Points.

Buildings provide colony bonuses, unlock capabilities, and some
grant milestones toward the end game.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from planetfall.engine.dice import roll_d6
from planetfall.engine.models import Building, GameState, TurnEvent, TurnEventType


@dataclass
class BuildingDef:
    """Definition of a building that can be constructed."""
    id: str
    name: str
    bp_cost: int
    prerequisite: str  # "" = none, else application id
    is_milestone: bool = False
    effects: dict = field(default_factory=dict)
    description: str = ""


BUILDINGS: dict[str, BuildingDef] = {
    # No prerequisites
    "advanced_manufacturing_plant": BuildingDef(
        "advanced_manufacturing_plant", "Advanced Manufacturing Plant", 4, "",
        description="Tier 1 equipment prerequisite"),
    "civilian_market": BuildingDef(
        "civilian_market", "Civilian Market", 4, "",
        effects={"story_points": 1}, description="1 Story Point"),
    "drone_turret_network": BuildingDef(
        "drone_turret_network", "Drone Turret Network", 6, "",
        effects={"defenses": 1}, description="1 Colony Defense"),
    "expanded_living": BuildingDef(
        "expanded_living", "Expanded Living Facility", 4, "",
        effects={"roster_expand": 2}, description="Expand roster by 2"),
    "heavy_construction": BuildingDef(
        "heavy_construction", "Heavy Construction Site", 8, "",
        effects={"bp_per_turn": 1}, description="+1 BP per campaign turn"),
    "military_training": BuildingDef(
        "military_training", "Military Training Facility", 5, "",
        description="Any character +1 XP (once per turn)"),
    "militia_training": BuildingDef(
        "militia_training", "Militia Training Camp", 4, "",
        description="Civvies on missions get Reactions 2"),
    "patrol_base": BuildingDef(
        "patrol_base", "Patrol Base", 4, "",
        effects={"defenses": 1}, description="1 Colony Defense"),
    "protective_shelter": BuildingDef(
        "protective_shelter", "Protective Shelter", 6, "",
        effects={"integrity": 2}, description="+2 Colony Integrity"),
    "resource_processing": BuildingDef(
        "resource_processing", "Resource Processing", 8, "",
        description="+1 Raw Materials on every Raw Material receive"),
    "scout_drone_network": BuildingDef(
        "scout_drone_network", "Scout Drone Network", 8, "",
        effects={"mission_data": 1}, description="Hazard 5-6 sectors reduced by 1; +1 Mission Data"),
    # Require research applications
    "ai_school": BuildingDef(
        "ai_school", "AI-Assisted School", 6, "ai_school",
        description="New characters start with 2 XP"),
    "bot_maintenance": BuildingDef(
        "bot_maintenance", "Bot Maintenance Bay", 4, "bot_maintenance",
        description="Bots deploy same campaign turn"),
    "cybernetics": BuildingDef(
        "cybernetics", "Cybernetics Facility", 6, "cybernetics",
        effects={"augmentation_points": 1}, description="1 Augmentation Point"),
    "damage_containment": BuildingDef(
        "damage_containment", "Damage Containment Centre", 4, "damage_containment",
        effects={"repair_capacity": 1}, description="Colony repair +1"),
    "high_tech_manufacturing": BuildingDef(
        "high_tech_manufacturing", "High Tech Manufacturing Plant", 4, "high_tech_manufacturing",
        description="Tier 2 equipment prerequisite"),
    "hardened_life_support": BuildingDef(
        "hardened_life_support", "Hardened Life Support System", 6, "hardened_life_support",
        effects={"integrity": 2}, description="+2 Colony Integrity"),
    "food_production": BuildingDef(
        "food_production", "Locally Adapted Food Production Site", 4, "food_production",
        effects={"morale": 5}, description="+5 Colony Morale (one-time)"),
    "remote_research": BuildingDef(
        "remote_research", "Remote Research Station", 8, "remote_research",
        description="Roll 1D6/turn: 5-6 = 1 RP"),
    "remote_extraction": BuildingDef(
        "remote_extraction", "Remote Extraction Site", 8, "remote_extraction",
        description="Roll 1D6/turn: 5-6 = 1 Raw Material"),
    "scout_facilities": BuildingDef(
        "scout_facilities", "Scout Facilities", 6, "scout_facilities",
        effects={"mission_data": 1}, description="All scouts +3 XP; +1 Mission Data"),
    "early_warning": BuildingDef(
        "early_warning", "Early Warning System", 4, "early_warning",
        effects={"defenses": 1}, description="1 Colony Defense"),
    "military_barracks": BuildingDef(
        "military_barracks", "Military Barracks", 8, "military_barracks",
        description="All troopers +3 XP"),
    "medevac": BuildingDef(
        "medevac", "Med-Evac Shuttle Facility", 4, "medevac",
        description="1/turn casualty gets 2 injury rolls (pick better)"),
    "rapid_response": BuildingDef(
        "rapid_response", "Rapid Response Network", 4, "rapid_response",
        effects={"defenses": 1}, description="1 Colony Defense"),
    "advanced_medical": BuildingDef(
        "advanced_medical", "Advanced Medical Center", 5, "advanced_medical",
        description="Reduce injury recovery 1 turn"),
    "recreational": BuildingDef(
        "recreational", "Recreational Facility", 6, "recreational",
        effects={"story_points": 1, "morale": 1}, description="1 Story Point, +1 Colony Morale"),
    "satellite_launch": BuildingDef(
        "satellite_launch", "Satellite Launch Facility", 6, "satellite_launch",
        effects={"mission_data": 1}, description="3 sectors +1 Resource value; +1 Mission Data"),
    "env_control": BuildingDef(
        "env_control", "Environmental Control Facility", 8, "env_control",
        effects={"story_points": 1, "morale": 2}, description="1 Story Point, +2 Colony Morale"),
    "research_lab": BuildingDef(
        "research_lab", "Research Laboratory", 8, "research_lab",
        effects={"rp_per_turn": 1}, description="+1 RP per campaign turn"),
    "theoretical_school": BuildingDef(
        "theoretical_school", "School of Theoretical Sciences", 12, "theoretical_school",
        effects={"rp_per_turn": 1}, description="+1 RP per campaign turn"),
    "adapted_shield": BuildingDef(
        "adapted_shield", "Adapted Protective Shield Installation", 8, "adapted_shield",
        effects={"integrity": 3}, description="+3 Colony Integrity"),
    "bio_adaptation_site": BuildingDef(
        "bio_adaptation_site", "Biological Adaptation Research Site", 10, "bio_adaptation_site",
        effects={"augmentation_points": 2}, description="2 Augmentation Points"),
    "academy": BuildingDef(
        "academy", "Academy", 8, "academy",
        effects={"rp_per_turn": 1}, description="+1 RP per campaign turn"),
    "colony_shield": BuildingDef(
        "colony_shield", "Colony Shield Network", 8, "colony_shield",
        description="Mitigate 1 Colony Damage per event"),
    "scientific_training": BuildingDef(
        "scientific_training", "Scientific Training Facility", 6, "scientific_training",
        description="All scientists +3 XP"),
    # Milestone buildings
    "galactic_comms": BuildingDef(
        "galactic_comms", "Galactic Comms Relay", 10, "galactic_comms",
        is_milestone=True, effects={"story_points": 1}, description="1 Milestone, +1 Story Point"),
    "genetic_adaptation": BuildingDef(
        "genetic_adaptation", "Genetic Adaptation Facility", 15, "genetic_adaptation",
        is_milestone=True, effects={"augmentation_points": 2}, description="1 Milestone, 2 Augmentation Points"),
    "orbital_facility": BuildingDef(
        "orbital_facility", "Orbital Facility", 20, "improved_construction",
        is_milestone=True, effects={"morale": 5, "integrity": 3},
        description="1 Milestone, +5 Colony Morale, +3 Colony Integrity"),
    "terraforming": BuildingDef(
        "terraforming", "Terraforming Control Center", 15, "terraforming",
        is_milestone=True, effects={"integrity": 3}, description="1 Milestone, +3 Colony Damage resistance"),
}

# Track partial construction: building_id -> BP invested so far
# Stored in state.tracking.construction_progress as dict


def get_available_buildings(state: GameState) -> list[BuildingDef]:
    """Get buildings that can be constructed (prerequisites met, not already built)."""
    built_names = {b.name for b in state.colony.buildings}
    available = []

    for bid, bdef in BUILDINGS.items():
        # Already built?
        if bdef.name in built_names:
            continue
        # Check prerequisite (must be an unlocked application)
        if bdef.prerequisite and bdef.prerequisite not in state.tech_tree.unlocked_applications:
            continue
        available.append(bdef)

    return available


def get_construction_progress(state: GameState) -> dict[str, int]:
    """Get current construction progress for partially built buildings."""
    return dict(state.tracking.construction_progress)


def invest_in_building(
    state: GameState,
    building_id: str,
    bp_amount: int,
    raw_materials_convert: int = 0,
) -> list[TurnEvent]:
    """Invest BP (and optionally convert raw materials) in a building.

    Args:
        bp_amount: BP to invest from colony reserves.
        raw_materials_convert: Raw materials to convert to BP (max 3/turn).
    """
    bdef = BUILDINGS.get(building_id)
    if not bdef:
        return [TurnEvent(step=15, event_type=TurnEventType.BUILDING,
                          description=f"Unknown building: {building_id}")]

    # Convert raw materials (max 3)
    rm_convert = min(raw_materials_convert, 3, state.colony.resources.raw_materials)
    if rm_convert > 0:
        state.colony.resources.raw_materials -= rm_convert

    total_bp = bp_amount + rm_convert
    if total_bp > state.colony.resources.build_points + rm_convert:
        total_bp = state.colony.resources.build_points + rm_convert

    actual_bp_from_pool = total_bp - rm_convert
    if actual_bp_from_pool > state.colony.resources.build_points:
        actual_bp_from_pool = state.colony.resources.build_points
        total_bp = actual_bp_from_pool + rm_convert

    state.colony.resources.build_points -= actual_bp_from_pool

    # Track progress
    progress = state.tracking.construction_progress
    current = progress.get(building_id, 0)
    current += total_bp
    progress[building_id] = current

    events = []

    if current >= bdef.bp_cost:
        # Building complete!
        del progress[building_id]
        state.colony.buildings.append(Building(
            name=bdef.name,
            built_turn=state.current_turn,
            effects=[bdef.description],
        ))

        events.append(TurnEvent(
            step=15, event_type=TurnEventType.BUILDING,
            description=f"Building completed: {bdef.name} — {bdef.description}",
            state_changes={"building_completed": building_id},
        ))

        # Apply effects
        _apply_building_effects(state, bdef, events)
    else:
        remaining = bdef.bp_cost - current
        events.append(TurnEvent(
            step=15, event_type=TurnEventType.BUILDING,
            description=(
                f"Invested {total_bp} BP in {bdef.name} "
                f"({current}/{bdef.bp_cost}, {remaining} remaining)"
            ),
        ))

    return events


def _apply_building_effects(state: GameState, bdef: BuildingDef, events: list[TurnEvent]):
    """Apply immediate effects when a building is completed."""
    effects = bdef.effects

    if "morale" in effects:
        state.colony.morale += effects["morale"]
    if "integrity" in effects:
        state.colony.integrity += effects["integrity"]
    if "defenses" in effects:
        state.colony.defenses += effects["defenses"]
    if "story_points" in effects:
        state.colony.resources.story_points += effects["story_points"]
    if "augmentation_points" in effects:
        state.colony.resources.augmentation_points += effects["augmentation_points"]
    if "rp_per_turn" in effects:
        state.colony.per_turn_rates.research_points += effects["rp_per_turn"]
    if "bp_per_turn" in effects:
        state.colony.per_turn_rates.build_points += effects["bp_per_turn"]
    if "repair_capacity" in effects:
        state.colony.per_turn_rates.repair_capacity += effects["repair_capacity"]
    if "mission_data" in effects:
        state.campaign.mission_data_count += effects["mission_data"]

    # Milestone buildings
    if bdef.is_milestone:
        state.campaign.milestones_completed += 1
        events.append(TurnEvent(
            step=15, event_type=TurnEventType.BUILDING,
            description=f"MILESTONE achieved! ({state.campaign.milestones_completed} total)",
            state_changes={"milestone": state.campaign.milestones_completed},
        ))


def process_per_turn_buildings(state: GameState) -> list[TurnEvent]:
    """Process buildings with per-turn random effects (e.g., remote extraction)."""
    events = []
    built_names = {b.name for b in state.colony.buildings}

    if "Remote Extraction Site" in built_names:
        roll = roll_d6("Remote Extraction Site")
        if roll.total >= 5:
            state.colony.resources.raw_materials += 1
            events.append(TurnEvent(
                step=15, event_type=TurnEventType.BUILDING,
                description=f"Remote Extraction Site: rolled {roll.total} -> +1 Raw Material",
            ))

    if "Remote Research Station" in built_names:
        roll = roll_d6("Remote Research Station")
        if roll.total >= 5:
            state.colony.resources.research_points += 1
            events.append(TurnEvent(
                step=15, event_type=TurnEventType.BUILDING,
                description=f"Remote Research Station: rolled {roll.total} -> +1 RP",
            ))

    return events


def reclaim_building(state: GameState, building_name: str) -> list[TurnEvent]:
    """Reclaim a building, receiving half BP cost in Raw Materials."""
    building = None
    for b in state.colony.buildings:
        if b.name == building_name:
            building = b
            break

    if not building:
        return [TurnEvent(step=15, event_type=TurnEventType.BUILDING,
                          description=f"Building not found: {building_name}")]

    # Find the building def
    bdef = None
    for bid, bd in BUILDINGS.items():
        if bd.name == building_name:
            bdef = bd
            break

    rm_refund = bdef.bp_cost // 2 if bdef else 0
    state.colony.buildings.remove(building)
    state.colony.resources.raw_materials += rm_refund

    return [TurnEvent(
        step=15, event_type=TurnEventType.BUILDING,
        description=f"Reclaimed {building_name}: +{rm_refund} Raw Materials",
    )]

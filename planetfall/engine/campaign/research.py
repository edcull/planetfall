"""Research system — theories, applications, and bio-analysis.

Players spend Research Points (RP) on theories to unlock applications.
Theories are broad fields; applications are specific benefits unlocked
by completing a theory.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from planetfall.engine.dice import roll_d6
from planetfall.engine.models import GameState, Theory, TurnEvent, TurnEventType


# --- Theory definitions ---

@dataclass
class TheoryDef:
    """Definition of a research theory."""
    id: str
    name: str
    rp_cost: int  # RP to complete the theory
    app_cost: int  # RP per application
    prerequisite: str  # "" = none, else theory id
    applications: list[str] = field(default_factory=list)


@dataclass
class ApplicationDef:
    """Definition of a research application."""
    id: str
    name: str
    theory_id: str
    app_type: str  # "building", "weapon", "bonus", "milestone", "grunt_upgrade"
    effects: dict = field(default_factory=dict)
    description: str = ""


# Primary theories (no prerequisites)
THEORIES: dict[str, TheoryDef] = {
    "ai_theories": TheoryDef(
        id="ai_theories", name="AI Theories", rp_cost=4, app_cost=4,
        prerequisite="",
        applications=["ai_school", "bot_maintenance", "cybernetics", "enhanced_simulation", "social_disorder"],
    ),
    "advanced_manufacturing": TheoryDef(
        id="advanced_manufacturing", name="Advanced Manufacturing", rp_cost=3, app_cost=3,
        prerequisite="",
        applications=["damage_containment", "high_tech_manufacturing", "improved_construction"],
    ),
    "environmental_research": TheoryDef(
        id="environmental_research", name="Environmental Research", rp_cost=2, app_cost=3,
        prerequisite="",
        applications=["hardened_life_support", "food_production", "remote_research", "remote_extraction", "scout_facilities"],
    ),
    "infantry_equipment": TheoryDef(
        id="infantry_equipment", name="Infantry Equipment", rp_cost=2, app_cost=2,
        prerequisite="",
        applications=["carver_blade", "kill_break_shotgun", "ripper_pistol", "shard_pistol", "steady_rifle"],
    ),
    "military_doctrine": TheoryDef(
        id="military_doctrine", name="Military Doctrine", rp_cost=3, app_cost=3,
        prerequisite="",
        applications=["civil_drills", "early_warning", "military_barracks", "medevac", "rapid_response"],
    ),
    "genetic_advancement": TheoryDef(
        id="genetic_advancement", name="Genetic Advancement", rp_cost=4, app_cost=4,
        prerequisite="",
        applications=["advanced_medical", "neuro_therapy", "reverse_genetics", "subspecific_genetics"],
    ),
    "social_theories": TheoryDef(
        id="social_theories", name="Social Theories", rp_cost=3, app_cost=3,
        prerequisite="",
        applications=["frontier_doctrines", "conflict_resolution", "consensus_mechanics", "recreational", "satellite_launch"],
    ),
    "theoretical_physics": TheoryDef(
        id="theoretical_physics", name="Theoretical Physics", rp_cost=4, app_cost=3,
        prerequisite="",
        applications=["env_control", "galactic_comms", "research_lab", "theoretical_school"],
    ),
    # Secondary theories (require prerequisites)
    "environmental_adaptation": TheoryDef(
        id="environmental_adaptation", name="Environmental Adaptation", rp_cost=3, app_cost=3,
        prerequisite="environmental_research",
        applications=["immune_bio", "survival_kit", "post_organic", "terraforming", "viral_elimination"],
    ),
    "adapted_combat_gear": TheoryDef(
        id="adapted_combat_gear", name="Adapted Combat Gear", rp_cost=2, app_cost=2,
        prerequisite="infantry_equipment",
        applications=["bio_gun", "dart_pistol", "hyper_rifle", "mind_link_pistol", "phase_rifle"],
    ),
    "high_level_adaptation": TheoryDef(
        id="high_level_adaptation", name="High Level Adaptation", rp_cost=4, app_cost=4,
        prerequisite="genetic_advancement",
        applications=["adapted_shield", "bio_adaptation_site", "genetic_adaptation", "hyper_molecular", "localized_therapy"],
    ),
    "non_linear_physics": TheoryDef(
        id="non_linear_physics", name="Non-Linear Physics", rp_cost=4, app_cost=3,
        prerequisite="theoretical_physics",
        applications=["academy", "colony_shield", "scientific_training"],
    ),
    "psionic_engineering": TheoryDef(
        id="psionic_engineering", name="Psionic Engineering", rp_cost=4, app_cost=4,
        prerequisite="genetic_advancement",
        applications=["mental_uplift", "psionic_integration", "psionic_reengineering"],
    ),
}

APPLICATIONS: dict[str, ApplicationDef] = {
    # AI Theories
    "ai_school": ApplicationDef("ai_school", "AI-Assisted School", "ai_theories", "building",
        description="New characters start with 2 XP"),
    "bot_maintenance": ApplicationDef("bot_maintenance", "Bot Maintenance Bay", "ai_theories", "building",
        description="Bots deploy same campaign turn"),
    "cybernetics": ApplicationDef("cybernetics", "Cybernetics Facility", "ai_theories", "building",
        effects={"augmentation_points": 1}, description="1 Augmentation Point"),
    "enhanced_simulation": ApplicationDef("enhanced_simulation", "Enhanced Predictive Simulation", "ai_theories", "bonus",
        effects={"rp_per_turn": 1}, description="+1 RP per campaign turn"),
    "social_disorder": ApplicationDef("social_disorder", "Social Disorder Prediction", "ai_theories", "bonus",
        effects={"morale": 4}, description="+4 Colony Morale"),
    # Advanced Manufacturing
    "damage_containment": ApplicationDef("damage_containment", "Damage Containment Centre", "advanced_manufacturing", "building",
        effects={"repair_capacity": 1}, description="Colony repair +1"),
    "high_tech_manufacturing": ApplicationDef("high_tech_manufacturing", "High Tech Manufacturing Plant", "advanced_manufacturing", "building",
        description="Tier 2 equipment prerequisite"),
    "improved_construction": ApplicationDef("improved_construction", "Improved Construction Materials", "advanced_manufacturing", "bonus",
        effects={"integrity": 1}, description="+1 Colony Integrity"),
    # Environmental Research
    "hardened_life_support": ApplicationDef("hardened_life_support", "Hardened Life Support System", "environmental_research", "building",
        effects={"integrity": 2}, description="+2 Colony Integrity"),
    "food_production": ApplicationDef("food_production", "Locally Adapted Food Production Site", "environmental_research", "building",
        effects={"morale": 5}, description="+5 Colony Morale (one-time)"),
    "remote_research": ApplicationDef("remote_research", "Remote Research Station", "environmental_research", "building",
        effects={"mission_data": 1}, description="+1 Mission Data"),
    "remote_extraction": ApplicationDef("remote_extraction", "Remote Extraction Site", "environmental_research", "building",
        description="Roll 1D6/turn: 5-6 = 1 Raw Material"),
    "scout_facilities": ApplicationDef("scout_facilities", "Scout Facilities", "environmental_research", "building",
        effects={"mission_data": 1}, description="All scouts +3 XP; +1 Mission Data"),
    # Infantry Equipment
    "carver_blade": ApplicationDef("carver_blade", "Carver Blade", "infantry_equipment", "weapon"),
    "kill_break_shotgun": ApplicationDef("kill_break_shotgun", "Kill-Break Shotgun", "infantry_equipment", "weapon"),
    "ripper_pistol": ApplicationDef("ripper_pistol", "Ripper Pistol", "infantry_equipment", "weapon"),
    "shard_pistol": ApplicationDef("shard_pistol", "Shard Pistol", "infantry_equipment", "weapon"),
    "steady_rifle": ApplicationDef("steady_rifle", "Steady Rifle", "infantry_equipment", "weapon"),
    # Military Doctrine
    "civil_drills": ApplicationDef("civil_drills", "Civil Preparation Drills", "military_doctrine", "bonus",
        effects={"morale": 3}, description="+3 Colony Morale"),
    "early_warning": ApplicationDef("early_warning", "Early Warning System", "military_doctrine", "building",
        effects={"defenses": 1}, description="1 Colony Defense"),
    "military_barracks": ApplicationDef("military_barracks", "Military Barracks", "military_doctrine", "building",
        description="All troopers +3 XP"),
    "medevac": ApplicationDef("medevac", "Med-Evac Shuttle Facility", "military_doctrine", "building",
        description="1/turn casualty gets 2 injury rolls (pick better)"),
    "rapid_response": ApplicationDef("rapid_response", "Rapid Response Network", "military_doctrine", "building",
        effects={"defenses": 1}, description="1 Colony Defense"),
    # Genetic Advancement
    "advanced_medical": ApplicationDef("advanced_medical", "Advanced Medical Center", "genetic_advancement", "building",
        description="Reduce injury recovery 1 turn"),
    "neuro_therapy": ApplicationDef("neuro_therapy", "Neuro-Adjustment Therapy", "genetic_advancement", "bonus",
        effects={"morale": 3}, description="+3 Colony Morale"),
    "reverse_genetics": ApplicationDef("reverse_genetics", "Reverse-Optimization of Genetics", "genetic_advancement", "bonus",
        effects={"augmentation_points": 1}, description="+1 Augmentation Point"),
    "subspecific_genetics": ApplicationDef("subspecific_genetics", "Sub-Specific Genetic Addition", "genetic_advancement", "bonus",
        effects={"augmentation_points": 1}, description="+1 Augmentation Point"),
    # Social Theories
    "frontier_doctrines": ApplicationDef("frontier_doctrines", "Frontier World Doctrines", "social_theories", "milestone",
        description="1 Milestone"),
    "conflict_resolution": ApplicationDef("conflict_resolution", "Integrated Conflict Resolution", "social_theories", "bonus",
        effects={"morale": 4}, description="+4 Colony Morale"),
    "consensus_mechanics": ApplicationDef("consensus_mechanics", "Post-Democratic Consensus Mechanics", "social_theories", "bonus",
        effects={"morale": 4}, description="+4 Colony Morale"),
    "recreational": ApplicationDef("recreational", "Recreational Facility", "social_theories", "building",
        effects={"story_points": 1, "morale": 1}, description="1 Story Point, +1 Colony Morale"),
    "satellite_launch": ApplicationDef("satellite_launch", "Satellite Launch Facility", "social_theories", "building",
        effects={"mission_data": 1}, description="3 sectors +1 Resource value; +1 Mission Data"),
    # Theoretical Physics
    "env_control": ApplicationDef("env_control", "Environmental Control Facility", "theoretical_physics", "building",
        effects={"story_points": 1, "morale": 2}, description="1 Story Point, +2 Colony Morale"),
    "galactic_comms": ApplicationDef("galactic_comms", "Galactic Comms Relay", "theoretical_physics", "building",
        effects={"story_points": 1}, description="1 Milestone, +1 Story Point"),
    "research_lab": ApplicationDef("research_lab", "Research Laboratory", "theoretical_physics", "building",
        effects={"rp_per_turn": 1}, description="+1 RP per campaign turn"),
    "theoretical_school": ApplicationDef("theoretical_school", "School of Theoretical Sciences", "theoretical_physics", "building",
        effects={"rp_per_turn": 1}, description="+1 RP per campaign turn"),
    # Environmental Adaptation
    "immune_bio": ApplicationDef("immune_bio", "Immune System Bio-Delineation", "environmental_adaptation", "bonus",
        effects={"augmentation_points": 1}, description="+1 Augmentation Point"),
    "survival_kit": ApplicationDef("survival_kit", "Bolstered Survival Kit", "environmental_adaptation", "grunt_upgrade",
        description="Grunts gain +1 Toughness save"),
    "post_organic": ApplicationDef("post_organic", "Integrated Post-Organic Demarcation", "environmental_adaptation", "milestone",
        description="1 Milestone"),
    "terraforming": ApplicationDef("terraforming", "Terraforming Control Center", "environmental_adaptation", "building",
        description="1 Milestone"),
    "viral_elimination": ApplicationDef("viral_elimination", "Viral Elimination Therapy", "environmental_adaptation", "bonus",
        effects={"augmentation_points": 1}, description="+1 Augmentation Point"),
    # Adapted Combat Gear
    "bio_gun": ApplicationDef("bio_gun", "Bio-Gun", "adapted_combat_gear", "weapon"),
    "dart_pistol": ApplicationDef("dart_pistol", "Dart Pistol", "adapted_combat_gear", "weapon"),
    "hyper_rifle": ApplicationDef("hyper_rifle", "Hyper-Rifle", "adapted_combat_gear", "weapon"),
    "mind_link_pistol": ApplicationDef("mind_link_pistol", "Mind-Link Pistol", "adapted_combat_gear", "weapon"),
    "phase_rifle": ApplicationDef("phase_rifle", "Phase Rifle", "adapted_combat_gear", "weapon"),
    # High Level Adaptation
    "adapted_shield": ApplicationDef("adapted_shield", "Adapted Protective Shield", "high_level_adaptation", "building",
        effects={"integrity": 3}, description="+3 Colony Integrity"),
    "bio_adaptation_site": ApplicationDef("bio_adaptation_site", "Biological Adaptation Research Site", "high_level_adaptation", "building",
        effects={"augmentation_points": 2}, description="2 Augmentation Points"),
    "genetic_adaptation": ApplicationDef("genetic_adaptation", "Genetic Adaptation Facility", "high_level_adaptation", "building",
        effects={"augmentation_points": 2}, description="1 Milestone, 2 Augmentation Points"),
    "hyper_molecular": ApplicationDef("hyper_molecular", "Hyper-Resonant Molecular Adjustment", "high_level_adaptation", "bonus",
        effects={"augmentation_points": 1}, description="+1 Augmentation Point"),
    "localized_therapy": ApplicationDef("localized_therapy", "Localized Adaptation Therapy", "high_level_adaptation", "bonus",
        effects={"augmentation_points": 1}, description="+1 Augmentation Point"),
    # Non-Linear Physics
    "academy": ApplicationDef("academy", "Academy", "non_linear_physics", "building",
        effects={"rp_per_turn": 1}, description="+1 RP per campaign turn"),
    "colony_shield": ApplicationDef("colony_shield", "Colony Shield Network", "non_linear_physics", "building",
        description="Mitigate 1 Colony Damage per event"),
    "scientific_training": ApplicationDef("scientific_training", "Scientific Training Facility", "non_linear_physics", "building",
        description="All scientists +3 XP"),
    # Psionic Engineering
    "mental_uplift": ApplicationDef("mental_uplift", "Mental Bio-Uplift Therapy", "psionic_engineering", "bonus",
        effects={"augmentation_points": 2}, description="+2 Augmentation Points"),
    "psionic_integration": ApplicationDef("psionic_integration", "Psionic Personality Integration", "psionic_engineering", "milestone",
        description="1 Milestone"),
    "psionic_reengineering": ApplicationDef("psionic_reengineering", "Psionic Re-Engineering Principles", "psionic_engineering", "bonus",
        effects={"augmentation_points": 2}, description="+2 Augmentation Points"),
}

# Applications that grant milestones
MILESTONE_APPLICATIONS = {"frontier_doctrines", "post_organic", "psionic_integration"}

# Grunt upgrades auto-triggered by unlocking prerequisite applications
GRUNT_UPGRADE_TRIGGERS: dict[str, tuple[str, str, str]] = {
    # app_id that triggers -> (upgrade_id, upgrade_name, description)
    "shard_pistol": ("side_arms", "Side Arms",
        "All grunts carry a handgun in addition to their normal weapons."),
    "carver_blade": ("sergeant_weaponry", "Sergeant Weaponry",
        "One grunt per fireteam receives a Damage +1 melee weapon."),
    "early_warning": ("sharpshooter_sight", "Sharpshooter Sight",
        "One grunt per fireteam gets +1 to hit when stationary (military rifle only)."),
    "food_production": ("adapted_armor", "Adapted Armor",
        "All grunts receive a 6+ Saving Throw."),
    "military_barracks": ("ammo_packs", "Ammo Packs",
        "Once per battle, roll an extra die to hit for every grunt in the fireteam."),
}
MILESTONE_BUILDINGS = {"galactic_comms", "genetic_adaptation", "terraforming"}

# Bio-analysis table
BIO_ANALYSIS_TABLE = {
    1: {"name": "Hit bonus", "description": "+1 to hit ranged attacks against lifeform"},
    2: {"name": "Brawling bonus", "description": "+1 to brawling combat roll"},
    3: {"name": "Critical hits", "description": "Natural 6 hit + natural 6 damage = creature slain regardless of KP"},
    4: {"name": "Defensive reduction", "description": "Reduce creature Saving Throws by 1 step"},
    5: {"name": "Defensive bonus", "description": "6+ Saving Throw against all creature attacks"},
    6: {"name": "Predictive movement", "description": "Reduce creature movement by 1\""},
}


def get_available_theories(state: GameState) -> list[TheoryDef]:
    """Get theories available to research (prerequisites met, not completed)."""
    available = []
    for tid, theory in THEORIES.items():
        # Already completed?
        if tid in state.tech_tree.theories and state.tech_tree.theories[tid].completed:
            continue
        # Check prerequisite
        if theory.prerequisite:
            prereq = state.tech_tree.theories.get(theory.prerequisite)
            if not prereq or not prereq.completed:
                continue
        available.append(theory)
    return available


def get_available_applications(state: GameState) -> list[ApplicationDef]:
    """Get applications available to research (theory completed, not yet unlocked)."""
    available = []
    for app_id, app in APPLICATIONS.items():
        if app_id in state.tech_tree.unlocked_applications:
            continue
        # Theory must be completed
        theory = state.tech_tree.theories.get(app.theory_id)
        if theory and theory.completed:
            available.append(app)
    return available


def invest_in_theory(state: GameState, theory_id: str, rp_amount: int) -> list[TurnEvent]:
    """Invest RP in a theory. Completes it if enough RP invested."""
    theory_def = THEORIES.get(theory_id)
    if not theory_def:
        return [TurnEvent(step=14, event_type=TurnEventType.RESEARCH,
                          description=f"Unknown theory: {theory_id}")]

    if rp_amount > state.colony.resources.research_points:
        rp_amount = state.colony.resources.research_points

    if rp_amount <= 0:
        return []

    # Get or create theory tracking
    if theory_id not in state.tech_tree.theories:
        state.tech_tree.theories[theory_id] = Theory(
            name=theory_def.name, required_rp=theory_def.rp_cost
        )

    theory = state.tech_tree.theories[theory_id]
    if theory.completed:
        return [TurnEvent(step=14, event_type=TurnEventType.RESEARCH,
                          description=f"{theory.name} already completed")]

    state.colony.resources.research_points -= rp_amount
    theory.invested_rp += rp_amount

    events = []
    if theory.invested_rp >= theory.required_rp:
        theory.completed = True
        events.append(TurnEvent(
            step=14, event_type=TurnEventType.RESEARCH,
            description=f"Theory completed: {theory.name}! Applications now available.",
            state_changes={"theory_completed": theory_id},
        ))
    else:
        remaining = theory.required_rp - theory.invested_rp
        events.append(TurnEvent(
            step=14, event_type=TurnEventType.RESEARCH,
            description=f"Invested {rp_amount} RP in {theory.name} ({theory.invested_rp}/{theory.required_rp}, {remaining} remaining)",
        ))

    return events


def unlock_application(state: GameState, app_id: str) -> list[TurnEvent]:
    """Spend RP to unlock an application."""
    app_def = APPLICATIONS.get(app_id)
    if not app_def:
        return [TurnEvent(step=14, event_type=TurnEventType.RESEARCH,
                          description=f"Unknown application: {app_id}")]

    theory_def = THEORIES[app_def.theory_id]
    cost = theory_def.app_cost

    if state.colony.resources.research_points < cost:
        return [TurnEvent(step=14, event_type=TurnEventType.RESEARCH,
                          description=f"Not enough RP for {app_def.name} (need {cost}, have {state.colony.resources.research_points})")]

    state.colony.resources.research_points -= cost
    state.tech_tree.unlocked_applications.append(app_id)

    events = [TurnEvent(
        step=14, event_type=TurnEventType.RESEARCH,
        description=f"Application unlocked: {app_def.name} — {app_def.description}",
        state_changes={"application_unlocked": app_id},
    )]

    # Apply immediate effects
    effects = app_def.effects
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
    if "mission_data" in effects:
        state.campaign.mission_data_count += effects["mission_data"]

    # Grunt upgrades (explicit grunt_upgrade type)
    if app_def.app_type == "grunt_upgrade":
        if app_id not in state.grunts.upgrades:
            state.grunts.upgrades.append(app_id)
            events.append(TurnEvent(
                step=14, event_type=TurnEventType.RESEARCH,
                description=f"Grunt upgrade applied: {app_def.name} — {app_def.description}",
                state_changes={"grunt_upgrade": app_id},
            ))

    # Auto-unlock grunt upgrades when their prerequisite application is researched
    if app_id in GRUNT_UPGRADE_TRIGGERS:
        upg_id, upg_name, upg_desc = GRUNT_UPGRADE_TRIGGERS[app_id]
        if upg_id not in state.grunts.upgrades:
            state.grunts.upgrades.append(upg_id)
            events.append(TurnEvent(
                step=14, event_type=TurnEventType.RESEARCH,
                description=f"Grunt upgrade unlocked: {upg_name} — {upg_desc}",
                state_changes={"grunt_upgrade": upg_id},
            ))

    # Check milestone
    if app_id in MILESTONE_APPLICATIONS:
        state.campaign.milestones_completed += 1
        events.append(TurnEvent(
            step=14, event_type=TurnEventType.RESEARCH,
            description=f"MILESTONE achieved! ({state.campaign.milestones_completed} total)",
            state_changes={"milestone": state.campaign.milestones_completed},
        ))

    return events


def sync_grunt_upgrades(state: GameState) -> None:
    """Retroactively apply any missing grunt upgrades based on unlocked applications.

    Call on state load to catch upgrades that should have been granted
    but weren't (e.g., code was added after the research was done).
    """
    unlocked = set(state.tech_tree.unlocked_applications)
    for trigger_app, (upg_id, _, _) in GRUNT_UPGRADE_TRIGGERS.items():
        if trigger_app in unlocked and upg_id not in state.grunts.upgrades:
            state.grunts.upgrades.append(upg_id)


def perform_bio_analysis(state: GameState, lifeform_name: str = "") -> list[TurnEvent]:
    """Spend 3 RP to perform bio-analysis on a specific lifeform specimen."""
    cost = 3
    if state.colony.resources.research_points < cost:
        return [TurnEvent(step=14, event_type=TurnEventType.RESEARCH,
                          description=f"Not enough RP for bio-analysis (need {cost})")]

    # Find the lifeform entry
    lf_entry = None
    for lf in state.enemies.lifeform_table:
        if lf.name == lifeform_name and lf.specimen_collected and not lf.bio_analysis_result:
            lf_entry = lf
            break

    if lf_entry is None:
        return [TurnEvent(step=14, event_type=TurnEventType.RESEARCH,
                          description="No unanalyzed specimen available.")]

    state.colony.resources.research_points -= cost
    roll = roll_d6("Bio-analysis")
    result = BIO_ANALYSIS_TABLE[roll.total]

    # Store result on the lifeform entry for combat bonuses
    lf_entry.bio_analysis_result = result["name"]
    lf_entry.bio_analysis_level = 1

    return [TurnEvent(
        step=14, event_type=TurnEventType.RESEARCH,
        description=(
            f"Bio-analysis of {lifeform_name}: {result['name']} — "
            f"{result['description']}"
        ),
        state_changes={"bio_analysis": result["name"], "lifeform": lifeform_name},
    )]

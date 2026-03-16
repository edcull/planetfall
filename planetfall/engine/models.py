"""Pydantic models for the Planetfall game state."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


# --- Enums ---


class CharacterClass(str, Enum):
    SCIENTIST = "scientist"
    SCOUT = "scout"
    TROOPER = "trooper"
    GRUNT = "grunt"
    CIVVY = "civvy"
    BOT = "bot"


class Loyalty(str, Enum):
    LOYAL = "loyal"
    COMMITTED = "committed"
    DISLOYAL = "disloyal"


class SubSpecies(str, Enum):
    STANDARD = "standard"
    FERAL = "feral"
    HULKER = "hulker"
    STALKER = "stalker"
    SOULLESS = "soulless"


class ColonizationAgenda(str, Enum):
    SCIENTIFIC = "scientific"
    CORPORATE = "corporate"
    UNITY = "unity"
    INDEPENDENT = "independent"
    MILITARY = "military"
    AFFINITY = "affinity"


class SectorStatus(str, Enum):
    UNEXPLORED = "unexplored"
    EXPLORED = "explored"
    EXPLOITED = "exploited"


class SectorTerrain(str, Enum):
    PLAINS = "plains"
    FOREST = "forest"
    HILLS = "hills"
    RUINS = "ruins"
    WETLANDS = "wetlands"
    CRAGS = "crags"
    DESERT = "desert"
    TUNDRA = "tundra"


class WeaponTier(str, Enum):
    STANDARD = "standard"
    TIER_1 = "tier_1"
    TIER_2 = "tier_2"


class MissionType(str, Enum):
    INVESTIGATION = "investigation"
    SCOUTING = "scouting"
    EXPLORATION = "exploration"
    SCIENCE = "science"
    HUNT = "hunt"
    PATROL = "patrol"
    SKIRMISH = "skirmish"
    RESCUE = "rescue"
    SCOUT_DOWN = "scout_down"
    PITCHED_BATTLE = "pitched_battle"
    STRIKE = "strike"
    ASSAULT = "assault"
    DELVE = "delve"


class TurnEventType(str, Enum):
    RECOVERY = "recovery"
    REPAIR = "repair"
    SCOUT_REPORT = "scout_report"
    ENEMY_ACTIVITY = "enemy_activity"
    COLONY_EVENT = "colony_event"
    MISSION = "mission"
    INJURY = "injury"
    EXPERIENCE = "experience"
    MORALE = "morale"
    REPLACEMENT = "replacement"
    RESEARCH = "research"
    BUILDING = "building"
    CHARACTER_EVENT = "character_event"
    COMBAT = "combat"
    NARRATIVE = "narrative"


# --- Starting profiles ---


class CharacterProfile(BaseModel):
    """Base stat profile for a character class."""
    reactions: int
    speed: int
    combat_skill: int
    toughness: int
    savvy: int


STARTING_PROFILES: dict[CharacterClass, CharacterProfile] = {
    CharacterClass.SCIENTIST: CharacterProfile(reactions=1, speed=4, combat_skill=0, toughness=3, savvy=1),
    CharacterClass.SCOUT: CharacterProfile(reactions=1, speed=5, combat_skill=0, toughness=3, savvy=0),
    CharacterClass.TROOPER: CharacterProfile(reactions=2, speed=4, combat_skill=1, toughness=3, savvy=0),
    CharacterClass.GRUNT: CharacterProfile(reactions=2, speed=4, combat_skill=0, toughness=3, savvy=0),
    CharacterClass.CIVVY: CharacterProfile(reactions=1, speed=4, combat_skill=0, toughness=3, savvy=0),
    CharacterClass.BOT: CharacterProfile(reactions=2, speed=4, combat_skill=0, toughness=4, savvy=0),
}


# --- Weapon model ---


class Weapon(BaseModel):
    name: str
    range_inches: int = 0  # 0 = melee
    shots: int = 1
    damage_bonus: int = 0
    traits: list[str] = Field(default_factory=list)
    tier: WeaponTier = WeaponTier.STANDARD


# --- Character model ---


class Character(BaseModel):
    name: str
    char_class: CharacterClass
    reactions: int = Field(ge=1, le=6)
    speed: int = Field(ge=1, le=8)
    combat_skill: int = Field(ge=0, le=5)
    toughness: int = Field(ge=1, le=6)
    savvy: int = Field(ge=0, le=5)
    xp: int = 0
    kill_points: int = 0
    loyalty: Loyalty = Loyalty.COMMITTED
    sub_species: SubSpecies = SubSpecies.STANDARD
    equipment: list[str] = Field(default_factory=list)
    sick_bay_turns: int = 0
    title: str = ""                        # e.g. "Lt. Commander"
    role: str = ""                          # e.g. "Head of Security"
    background_motivation: str = ""
    background_prior_experience: str = ""
    background_notable_events: list[str] = Field(default_factory=list)
    narrative_background: str = ""
    upgrades: list[str] = Field(default_factory=list)
    notes: str = ""

    @property
    def level(self) -> int:
        """Character level: 1 + total stat increases above base + kill points."""
        base = STARTING_PROFILES.get(self.char_class)
        if not base:
            return 1
        base_tough = base.toughness
        if self.sub_species == SubSpecies.HULKER:
            base_tough = 5
        gains = (
            max(0, self.reactions - base.reactions)
            + max(0, self.speed - base.speed)
            + max(0, self.combat_skill - base.combat_skill)
            + max(0, self.toughness - base_tough)
            + max(0, self.savvy - base.savvy)
            + self.kill_points
        )
        return 1 + gains

    @property
    def is_available(self) -> bool:
        return self.sick_bay_turns == 0


class Administrator(BaseModel):
    name: str = ""
    past_history: str = ""
    notes: str = ""


# --- Grunt tracking ---


class Fireteam(BaseModel):
    name: str = ""
    size: int = 0  # 2-4 per fireteam
    equipment: list[str] = Field(default_factory=list)


class GruntPool(BaseModel):
    count: int = 12
    bot_operational: bool = True
    fireteams: list[Fireteam] = Field(default_factory=list)
    upgrades: list[str] = Field(default_factory=list)


# --- Colony ---


class Resources(BaseModel):
    build_points: int = 0
    research_points: int = 0
    raw_materials: int = 0
    augmentation_points: int = 0
    story_points: int = 5
    calamity_points: int = 0


class PerTurnRates(BaseModel):
    build_points: int = 1
    research_points: int = 1
    repair_capacity: int = 1


class Building(BaseModel):
    name: str
    built_turn: int = 0
    effects: list[str] = Field(default_factory=list)


class Colony(BaseModel):
    name: str = "Home"
    description: str = ""  # AI-generated colony founding narrative
    morale: int = 0
    integrity: int = 0
    defenses: int = 0
    buildings: list[Building] = Field(default_factory=list)
    resources: Resources = Field(default_factory=Resources)
    per_turn_rates: PerTurnRates = Field(default_factory=PerTurnRates)


# --- Tech tree ---


class Theory(BaseModel):
    name: str
    invested_rp: int = 0
    required_rp: int = 0
    completed: bool = False


class TechTree(BaseModel):
    theories: dict[str, Theory] = Field(default_factory=dict)
    unlocked_applications: list[str] = Field(default_factory=list)


# --- Campaign map ---


class SectorQuality(str, Enum):
    """Sector qualities that affect battlefield conditions."""
    DIFFICULT_GROUND = "difficult_ground"


class Sector(BaseModel):
    sector_id: int
    status: SectorStatus = SectorStatus.UNEXPLORED
    terrain: SectorTerrain = SectorTerrain.PLAINS
    name: str = ""
    resource_level: int = 0
    hazard_level: int = 0
    qualities: list[SectorQuality] = Field(default_factory=list)
    enemy_occupied_by: Optional[str] = None
    has_ancient_sign: bool = False
    has_ancient_site: bool = False
    ancient_site_bonus_mission_data: int = 0
    has_investigation_site: bool = False
    notes: str = ""


class CampaignMap(BaseModel):
    sectors: list[Sector] = Field(default_factory=list)
    colony_sector_id: int = 0


# --- Enemies ---


class LifeformEntry(BaseModel):
    d100_low: int
    d100_high: int
    name: str = ""
    mobility: int = 0
    toughness: int = 0
    combat_skill: int = 0
    strike_damage: int = 0
    armor_save: int = 0
    kill_points: int = 1
    partially_airborne: bool = False
    dodge: bool = False
    weapons: list[str] = Field(default_factory=list)
    special_rules: list[str] = Field(default_factory=list)
    bio_analysis_level: int = 0
    specimen_collected: bool = False
    bio_analysis_result: str = ""  # e.g. "hit_bonus", "defensive_bonus" — applied in combat vs this lifeform


class TacticalEnemyProfile(BaseModel):
    """Stat profile for a tactical enemy faction."""
    speed: int = 4
    combat_skill: int = 0
    toughness: int = 3
    panic_range: int = 0
    armor_save: int = 0
    special_rules: list[str] = Field(default_factory=list)
    number_dice: str = "1d6"


class TacticalEnemy(BaseModel):
    name: str
    enemy_type: str = ""  # e.g. "outlaws", "pirates", "k_erin"
    sectors: list[int] = Field(default_factory=list)
    enemy_info_count: int = 0
    boss_located: bool = False
    strongpoint_located: bool = False
    defeated: bool = False
    disrupted_this_turn: bool = False
    profile: TacticalEnemyProfile = Field(default_factory=TacticalEnemyProfile)


class SlynState(BaseModel):
    active: bool = True  # Always active; set False when driven off after milestone 4
    encounters: int = 0


class Enemies(BaseModel):
    tactical_enemies: list[TacticalEnemy] = Field(default_factory=list)
    lifeform_table: list[LifeformEntry] = Field(default_factory=list)
    slyn: SlynState = Field(default_factory=SlynState)


# --- Turn log ---


class DiceRoll(BaseModel):
    dice_type: str  # "d6", "d100", "2d6"
    values: list[int]
    total: int
    label: str = ""


class TurnEvent(BaseModel):
    step: int = 0
    event_type: TurnEventType
    description: str = ""
    dice_rolls: list[DiceRoll] = Field(default_factory=list)
    state_changes: dict[str, Any] = Field(default_factory=dict)


# --- Campaign progress ---


class MissionResult(BaseModel):
    """Result of the most recent mission."""
    victory: bool = False
    character_casualties: list[str] = Field(default_factory=list)
    grunt_casualties: int = 0


class CampaignProgress(BaseModel):
    milestones_completed: int = 0
    mission_data_count: int = 0
    ancient_signs_count: int = 0
    enemy_information_count: int = 0
    campaign_story_track: list[str] = Field(default_factory=list)
    end_game_triggered: bool = False
    initial_missions_complete: bool = False
    initial_mission_results: dict[str, MissionResult] = Field(default_factory=dict)
    initial_mission_step: int = 0


# --- Top-level game state ---


class GameSettings(BaseModel):
    manual_dice: bool = False
    colonization_agenda: ColonizationAgenda = ColonizationAgenda.UNITY
    narrative_disabled: bool = False


class ExtractionData(BaseModel):
    """State of a resource extraction operation."""
    resource_type: str = "raw_materials"
    yield_per_turn: int = 1
    turns_active: int = 0
    max_turns: int = 0
    depleted: bool = False


class BattlefieldCondition(BaseModel):
    """A battlefield condition affecting combat."""
    id: str = ""
    name: str = ""
    description: str = ""
    # Mechanical effects
    visibility_limit: int = 0          # max range in inches (0 = unlimited)
    visibility_type: str = ""          # "variable_round", "fixed", "variable_battle"
    shooting_penalty: int = 0          # modifier to hit rolls
    shooting_circumstance: str = ""    # "random_round", "range", "terrain_type"
    movement_penalty: bool = False     # cannot Dash
    movement_circumstance: str = ""    # "table_surface", "terrain_features", "climbing", "obstacles"
    extra_contacts: int = 0            # additional Contact markers
    aggression_mod: int = 0            # modifier to Aggression die for contacts
    enemy_size_mod: int = 0            # modifier to encounter sizes
    extra_finds_rolls: int = 0         # extra Post-Mission Finds rolls
    terrain_hazards: int = 0           # number of terrain features made Impassable
    terrain_unstable: bool = False     # terrain may collapse on D6=1
    shifting_terrain: bool = False     # terrain drifts 1D6" each round
    clouds: int = 0                    # number of cloud markers
    cloud_type: str = ""               # "safe", "toxic", "corrosive"
    cloud_toxin_level: int = 0         # toxin level for toxic clouds (2D6 pick highest)
    free_escape: bool = False          # once per round, a character can escape
    confined_exits: int = 0            # number of entry/exit points (0 = normal)
    no_effect: bool = False            # "No Conditions" result
    # Display
    effects_summary: list[str] = Field(default_factory=list)  # human-readable effect lines


class ExploredAncientSite(BaseModel):
    """Record of an explored ancient site."""
    sector_id: int = 0
    name: str = ""
    finding: str = ""


class SlynBriefing(BaseModel):
    """Briefing data for a Slyn interference event."""
    encounter_num: int = 1
    count: int = 4
    is_first: bool = False


class XpAward(BaseModel):
    """Per-character XP award after a mission."""
    name: str = ""
    xp: int = 0
    reasons: str = ""
    total_xp: int = 0


class CivvyPromotion(BaseModel):
    """Result of a civvy heroic promotion roll."""
    promoted: bool = False
    roll: int = 0


class CombatResult(BaseModel):
    """Result of a completed combat encounter."""
    victory: bool = False
    rounds_played: int = 0
    enemies_killed: int = 0
    character_casualties: list[str] = Field(default_factory=list)
    grunt_casualties: int = 0
    objectives_secured: int = 0
    evacuated: list[str] = Field(default_factory=list)
    battle_log: list[str] = Field(default_factory=list)
    investigation_results: dict[str, Any] = Field(default_factory=dict)


class MechanicalFlags(BaseModel):
    """Typed game-mechanical flags (replaces narrative_memory mechanical keys)."""
    crisis_active: bool = False
    crisis_reroll_active: bool = False
    political_upheaval: int = 0
    benched_trooper: str = ""
    work_stoppage_active: bool = False
    colonist_demands_active: bool = False
    colonist_demands_assigned: list[str] = Field(default_factory=list)
    bp_penalty_next: int = 0
    rp_penalty_next: int = 0
    no_story_points_this_turn: bool = False
    augmentation_bought_this_turn: bool = False
    bot_repaired_this_turn: bool = False
    colony_augmentations: list[str] = Field(default_factory=list)
    campaign_complete: bool = False
    summit_path: str = ""
    total_character_deaths: int = 0
    last_mission: MissionResult = Field(default_factory=MissionResult)


class TrackingData(BaseModel):
    """Typed tracking counters and lists (replaces narrative_memory tracking keys)."""
    construction_progress: dict[str, int] = Field(default_factory=dict)
    active_extractions: dict[str, ExtractionData] = Field(default_factory=dict)
    occurred_calamities: list[str] = Field(default_factory=list)
    active_calamities: dict[str, dict[str, Any]] = Field(default_factory=dict)  # Polymorphic per calamity type
    slyn_victories: int = 0
    slyn_victory_tracking_active: bool = False  # Milestone 4: track Slyn defeats
    ancient_sites_total: int = 0
    explored_ancient_sites: list[ExploredAncientSite] = Field(default_factory=list)
    breakthroughs: list[str] = Field(default_factory=list)
    breakthroughs_count: int = 0  # Sequential count (1st, 2nd, 3rd, 4th)
    found_artifacts: list[str] = Field(default_factory=list)
    battlefield_conditions: list[Optional[BattlefieldCondition]] = Field(default_factory=list)
    # Milestone-driven persistent flags
    pending_replacements: int = 0  # +1 per milestone, consumed during recruitment
    enemy_panic_reduction: int = 0  # Cumulative panic range reduction for tactical enemies
    enemy_specialist_kp_bonus: int = 0  # Cumulative KP bonus for tactical specialists
    enemy_extra_specialists: bool = False  # Milestone 6: +1 specialist per encounter
    enemy_activity_all_enemies: bool = False  # Milestone 6: roll activity for every enemy
    calamities_disabled: bool = False  # Milestone 7: set if calamity check passes
    lifeform_evolutions: list[str] = Field(default_factory=list)  # Track rolled evolutions
    sleeper_no_save: bool = False  # Defense Network breakthrough: sleepers lose saving throw
    hazard_level_reduction: int = 0  # Semi-Living Organism breakthrough: global hazard reduction


class NarrativeData(BaseModel):
    """Typed narrative memory for AI narration context."""
    themes: list[str] = Field(default_factory=list)
    character_arcs: dict[str, str] = Field(default_factory=dict)
    key_events: list[str] = Field(default_factory=list)
    tone: str = "gritty frontier sci-fi"


from planetfall.engine.migrations import CURRENT_SCHEMA_VERSION

SCHEMA_VERSION = CURRENT_SCHEMA_VERSION


class TurnData(BaseModel):
    """Typed inter-step data for mid-turn resume."""
    mission_type: str | None = None
    sector_id: int | None = None
    deployed_chars: list[str] = Field(default_factory=list)
    grunt_deploy: int = 0
    bot_deploy: bool = False
    civilian_deploy: int = 0
    weapon_loadout: dict[str, str] = Field(default_factory=dict)
    condition: BattlefieldCondition | None = None
    condition_rolled: bool = False
    condition_reroll_offered: bool = False
    slyn_checked: bool = False
    slyn_briefing: SlynBriefing | None = None
    mission_victory: bool | None = None
    character_casualties: list[str] = Field(default_factory=list)
    grunt_casualties: int = 0
    xp_awards: list[XpAward] | None = None
    civvy_promo: CivvyPromotion | None = None
    rp_gained: int | None = None
    bp_gained: int | None = None
    combat_session: dict[str, Any] | None = None  # For Phase 3: serialized combat state
    combat_log: list[str] | None = None
    objectives_secured: int = 0
    combat_result: CombatResult | None = None
    step_narratives: dict[str, str] = Field(default_factory=dict)  # step -> displayed modal text
    scout_wants_discovery: bool | None = None  # step 3: None=not asked, True/False=decided
    scout_discovery_scout: str | None = None  # step 3: assigned scout name for discovery
    scout_explored: bool = False  # step 3: mandatory sector exploration done
    scout_discovery_done: bool = False  # step 3: discovery roll done


class GameState(BaseModel):
    """Complete game state for a Planetfall campaign."""

    schema_version: int = SCHEMA_VERSION
    campaign_name: str = "New Colony"
    current_turn: int = 1
    current_step: int = 0  # Last completed step in current turn (0 = start of turn)
    turn_data: TurnData = Field(default_factory=TurnData)  # Inter-step data for mid-turn resume
    colony: Colony = Field(default_factory=Colony)
    characters: list[Character] = Field(default_factory=list)
    administrator: Administrator = Field(default_factory=Administrator)
    grunts: GruntPool = Field(default_factory=GruntPool)
    tech_tree: TechTree = Field(default_factory=TechTree)
    campaign_map: CampaignMap = Field(default_factory=CampaignMap)
    enemies: Enemies = Field(default_factory=Enemies)
    campaign: CampaignProgress = Field(default_factory=CampaignProgress)
    turn_log: list[TurnEvent] = Field(default_factory=list)
    settings: GameSettings = Field(default_factory=GameSettings)
    flags: MechanicalFlags = Field(default_factory=MechanicalFlags)
    tracking: TrackingData = Field(default_factory=TrackingData)
    narrative: NarrativeData = Field(default_factory=NarrativeData)
    # Deprecated — kept for backward-compat save loading; migrated on load
    narrative_memory: dict[str, Any] = Field(default_factory=dict)

    def find_character(self, name: str) -> Optional[Character]:
        """Find a character by name."""
        return next((c for c in self.characters if c.name == name), None)

    def get_available_characters(self) -> list[Character]:
        """Get characters not in sick bay."""
        return [c for c in self.characters if c.is_available]

    def get_sector(self, sector_id: int) -> Optional[Sector]:
        """Find a sector by ID."""
        return next(
            (s for s in self.campaign_map.sectors if s.sector_id == sector_id),
            None,
        )

    @model_validator(mode="after")
    def _migrate_narrative_memory(self) -> "GameState":
        """Migrate legacy narrative_memory dict into typed fields."""
        nm = self.narrative_memory
        if not nm:
            return self

        # Mechanical flags
        _FLAG_KEYS = {
            "crisis_active", "crisis_reroll_active", "political_upheaval",
            "benched_trooper", "work_stoppage_active", "colonist_demands_active",
            "colonist_demands_assigned", "bp_penalty_next", "rp_penalty_next",
            "augmentation_bought_this_turn", "colony_augmentations",
            "campaign_complete", "summit_path", "total_character_deaths",
        }
        for key in _FLAG_KEYS:
            if key in nm:
                setattr(self.flags, key, nm.pop(key))
        if "_last_mission" in nm:
            raw = nm.pop("_last_mission")
            self.flags.last_mission = raw if isinstance(raw, MissionResult) else MissionResult(**raw)
        if "last_mission" in nm:
            raw = nm.pop("last_mission")
            self.flags.last_mission = raw if isinstance(raw, MissionResult) else MissionResult(**raw)

        # Tracking data
        _TRACKING_KEYS = {
            "construction_progress", "active_extractions",
            "occurred_calamities", "active_calamities", "slyn_victories",
            "ancient_sites_total", "breakthroughs", "found_artifacts",
            "battlefield_conditions",
        }
        for key in _TRACKING_KEYS:
            if key in nm:
                setattr(self.tracking, key, nm.pop(key))

        # Narrative data
        _NARRATIVE_KEYS = {"themes", "character_arcs", "key_events", "tone"}
        for key in _NARRATIVE_KEYS:
            if key in nm:
                setattr(self.narrative, key, nm.pop(key))

        return self


# --- Weapon catalog ---

STANDARD_WEAPONS: list[Weapon] = [
    Weapon(name="Handgun", range_inches=6, shots=1, damage_bonus=0,
           traits=["civilian", "pistol"]),
    Weapon(name="Colonial Shotgun", range_inches=12, shots=1, damage_bonus=0,
           traits=["civilian", "critical"]),
    Weapon(name="Colony Rifle", range_inches=18, shots=1, damage_bonus=0,
           traits=["civilian"]),
    Weapon(name="Scout Pistol", range_inches=9, shots=1, damage_bonus=0,
           traits=["scout", "pistol", "stabilized"]),
    Weapon(name="Infantry Rifle", range_inches=24, shots=1, damage_bonus=0,
           traits=["grunt"]),
    Weapon(name="Light Machine Gun", range_inches=36, shots=3, damage_bonus=0,
           traits=["grunt", "cumbersome", "hail_of_fire"]),
    Weapon(name="Trooper Rifle", range_inches=30, shots=1, damage_bonus=0,
           traits=["trooper", "ap_ammo"]),
    Weapon(name="Assault Gun", range_inches=18, shots=2, damage_bonus=0,
           traits=["trooper"]),
    Weapon(name="Flame Projector", range_inches=6, shots=0, damage_bonus=1,
           traits=["trooper", "stream", "burning"]),
]

TIER_1_WEAPONS: list[Weapon] = [
    Weapon(name="Shard Pistol", range_inches=9, shots=2, damage_bonus=1,
           traits=["trooper", "focused", "pistol"], tier=WeaponTier.TIER_1),
    Weapon(name="Ripper Pistol", range_inches=9, shots=2, damage_bonus=0,
           traits=["scout", "pistol"], tier=WeaponTier.TIER_1),
    Weapon(name="Kill-Break Shotgun", range_inches=12, shots=1, damage_bonus=2,
           traits=["trooper", "knockback"], tier=WeaponTier.TIER_1),
    Weapon(name="Steady Rifle", range_inches=24, shots=1, damage_bonus=0,
           traits=["civilian", "stabilized"], tier=WeaponTier.TIER_1),
    Weapon(name="Carver Blade", range_inches=0, shots=0, damage_bonus=2,
           traits=["civilian", "flexible", "melee"], tier=WeaponTier.TIER_1),
]

TIER_2_WEAPONS: list[Weapon] = [
    Weapon(name="Bio-gun", range_inches=12, shots=0, damage_bonus=1,
           traits=["trooper", "area"], tier=WeaponTier.TIER_2),
    Weapon(name="Mind-link Pistol", range_inches=9, shots=1, damage_bonus=0,
           traits=["scientist", "mind_link"], tier=WeaponTier.TIER_2),
    Weapon(name="Phase Rifle", range_inches=16, shots=1, damage_bonus=1,
           traits=["scout", "phased_fire"], tier=WeaponTier.TIER_2),
    Weapon(name="Dart Pistol", range_inches=9, shots=1, damage_bonus=1,
           traits=["civilian", "armor_piercing"], tier=WeaponTier.TIER_2),
    Weapon(name="Hyper-rifle", range_inches=16, shots=1, damage_bonus=1,
           traits=["trooper", "hyperfire"], tier=WeaponTier.TIER_2),
]

ALL_WEAPONS = STANDARD_WEAPONS + TIER_1_WEAPONS + TIER_2_WEAPONS

# Map weapon names to their research application IDs.
# Tier 1/2 weapons require both the manufacturing building AND
# the specific weapon to be unlocked as a research application.
WEAPON_APP_IDS: dict[str, str] = {
    # Tier 1 (Infantry Equipment theory)
    "Shard Pistol": "shard_pistol",
    "Ripper Pistol": "ripper_pistol",
    "Kill-Break Shotgun": "kill_break_shotgun",
    "Steady Rifle": "steady_rifle",
    "Carver Blade": "carver_blade",
    # Tier 2 (Adapted Combat Gear theory)
    "Bio-gun": "bio_gun",
    "Mind-link Pistol": "mind_link_pistol",
    "Phase Rifle": "phase_rifle",
    "Dart Pistol": "dart_pistol",
    "Hyper-rifle": "hyper_rifle",
}


def get_weapon_by_name(name: str) -> Optional[Weapon]:
    """Look up a weapon by name (case-insensitive)."""
    for w in ALL_WEAPONS:
        if w.name.lower() == name.lower():
            return w
    return None


# --- Weapon class restrictions ---
# Each class can use weapons tagged with these trait classes.
# A weapon's class trait is the first trait that matches a class name.

ALLOWED_WEAPON_CLASSES: dict[str, set[str]] = {
    "scientist": {"civilian", "scientist"},
    "scout": {"civilian", "scout"},
    "trooper": {"civilian", "trooper"},
    "grunt": {"grunt"},
    "civvy": {"civilian"},
    "bot": {"civilian"},
}

# Class traits used on weapons to indicate who can wield them
_WEAPON_CLASS_TRAITS = {"civilian", "scientist", "scout", "trooper", "grunt"}


def get_weapon_class_trait(weapon: Weapon) -> str:
    """Extract the class restriction trait from a weapon.

    Returns the first trait that is a class identifier, or 'civilian' if none found.
    """
    for t in weapon.traits:
        if t in _WEAPON_CLASS_TRAITS:
            return t
    return "civilian"  # Untagged weapons default to civilian (usable by all)


def can_use_weapon(char_class: str, weapon: Weapon) -> bool:
    """Check if a character class can use a given weapon."""
    allowed = ALLOWED_WEAPON_CLASSES.get(char_class, {"civilian"})
    weapon_class = get_weapon_class_trait(weapon)
    return weapon_class in allowed


def get_available_loadout(
    char_class: str,
    colony_buildings: list | None = None,
    unlocked_applications: set[str] | None = None,
) -> list[Weapon]:
    """Get all weapons available for a character class during Lock and Load.

    Standard class weapons are always available (issued from colony stores).
    Tier 1/2 weapons require BOTH:
      - The manufacturing building (Advanced or High-Tech)
      - The specific weapon to be researched (unlocked as application)
    Equipment-owned weapons handled separately by the caller.
    """
    building_names = set()
    if colony_buildings:
        building_names = {b.name.lower() if hasattr(b, 'name') else str(b).lower()
                         for b in colony_buildings}

    has_tier1 = any("advanced manufacturing" in n for n in building_names)
    has_tier2 = any("high-tech manufacturing" in n or "high tech manufacturing" in n
                    for n in building_names)
    apps = unlocked_applications or set()

    weapons = []
    seen = set()

    for wpn in ALL_WEAPONS:
        if not can_use_weapon(char_class, wpn):
            continue
        # Check tier availability (building + research)
        if wpn.tier == WeaponTier.TIER_1:
            if not has_tier1:
                continue
            app_id = WEAPON_APP_IDS.get(wpn.name)
            if app_id and app_id not in apps:
                continue
        if wpn.tier == WeaponTier.TIER_2:
            if not has_tier2:
                continue
            app_id = WEAPON_APP_IDS.get(wpn.name)
            if app_id and app_id not in apps:
                continue
        if wpn.name not in seen:
            weapons.append(wpn)
            seen.add(wpn.name)

    return weapons

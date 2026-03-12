"""Pydantic models for the Planetfall game state."""

from __future__ import annotations

from enum import Enum
from typing import Optional

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
    UNKNOWN = "unknown"
    INVESTIGATED = "investigated"
    EXPLORED = "explored"
    EXPLOITED = "exploited"


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

STARTING_PROFILES: dict[CharacterClass, dict] = {
    CharacterClass.SCIENTIST: {
        "reactions": 1, "speed": 4, "combat_skill": 0,
        "toughness": 3, "savvy": 1,
    },
    CharacterClass.SCOUT: {
        "reactions": 1, "speed": 5, "combat_skill": 0,
        "toughness": 3, "savvy": 0,
    },
    CharacterClass.TROOPER: {
        "reactions": 2, "speed": 4, "combat_skill": 1,
        "toughness": 3, "savvy": 0,
    },
    CharacterClass.GRUNT: {
        "reactions": 2, "speed": 4, "combat_skill": 0,
        "toughness": 3, "savvy": 0,
    },
    CharacterClass.CIVVY: {
        "reactions": 1, "speed": 4, "combat_skill": 0,
        "toughness": 3, "savvy": 0,
    },
    CharacterClass.BOT: {
        "reactions": 2, "speed": 4, "combat_skill": 0,
        "toughness": 4, "savvy": 0,
    },
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
    background_notable_event: str = ""
    narrative_background: str = ""
    upgrades: list[str] = Field(default_factory=list)
    notes: str = ""

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


class Sector(BaseModel):
    sector_id: int
    status: SectorStatus = SectorStatus.UNKNOWN
    resource_level: int = 0
    hazard_level: int = 0
    enemy_occupied_by: Optional[str] = None
    has_ancient_sign: bool = False
    has_ancient_site: bool = False
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
    weapons: list[str] = Field(default_factory=list)
    special_rules: list[str] = Field(default_factory=list)
    bio_analysis_level: int = 0


class TacticalEnemy(BaseModel):
    name: str
    enemy_type: str = ""  # e.g. "outlaws", "pirates", "k_erin"
    sectors: list[int] = Field(default_factory=list)
    enemy_info_count: int = 0
    boss_located: bool = False
    strongpoint_located: bool = False
    defeated: bool = False
    disrupted_this_turn: bool = False
    profile: dict = Field(default_factory=dict)


class SlynState(BaseModel):
    active: bool = False
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
    state_changes: dict = Field(default_factory=dict)


# --- Campaign progress ---


class CampaignProgress(BaseModel):
    milestones_completed: int = 0
    mission_data_count: int = 0
    ancient_signs_count: int = 0
    enemy_information_count: int = 0
    campaign_story_track: list[str] = Field(default_factory=list)
    end_game_triggered: bool = False
    initial_missions_complete: bool = False
    initial_mission_results: dict = Field(default_factory=dict)


# --- Top-level game state ---


class GameSettings(BaseModel):
    manual_dice: bool = False
    colonization_agenda: ColonizationAgenda = ColonizationAgenda.UNITY


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
    augmentation_bought_this_turn: bool = False
    colony_augmentations: list[str] = Field(default_factory=list)
    campaign_complete: bool = False
    summit_path: str = ""
    total_character_deaths: int = 0
    last_mission: dict = Field(default_factory=dict)


class TrackingData(BaseModel):
    """Typed tracking counters and lists (replaces narrative_memory tracking keys)."""
    construction_progress: dict[str, int] = Field(default_factory=dict)
    active_extractions: dict[str, dict] = Field(default_factory=dict)
    occurred_calamities: list[str] = Field(default_factory=list)
    active_calamities: dict[str, dict] = Field(default_factory=dict)
    slyn_victories: int = 0
    ancient_sites_total: int = 0
    breakthroughs: list[str] = Field(default_factory=list)
    found_artifacts: list[str] = Field(default_factory=list)
    battlefield_conditions: list[dict] = Field(default_factory=list)


class NarrativeData(BaseModel):
    """Typed narrative memory for AI narration context."""
    themes: list[str] = Field(default_factory=list)
    character_arcs: dict[str, str] = Field(default_factory=dict)
    key_events: list[str] = Field(default_factory=list)
    tone: str = "gritty frontier sci-fi"


class GameState(BaseModel):
    """Complete game state for a Planetfall campaign."""

    campaign_name: str = "New Colony"
    current_turn: int = 1
    current_step: int = 0  # Last completed step in current turn (0 = start of turn)
    turn_data: dict = Field(default_factory=dict)  # Inter-step data for mid-turn resume
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
    narrative_memory: dict = Field(default_factory=dict)

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
            self.flags.last_mission = nm.pop("_last_mission")
        if "last_mission" in nm:
            self.flags.last_mission = nm.pop("last_mission")

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
) -> list[Weapon]:
    """Get all weapons available for a character class during Lock and Load.

    Standard class weapons are always available (issued from colony stores).
    Tier 1 weapons require Advanced Manufacturing Plant.
    Tier 2 weapons require High-Tech Manufacturing Plant.
    Equipment-owned weapons handled separately by the caller.
    """
    building_names = set()
    if colony_buildings:
        building_names = {b.name.lower() if hasattr(b, 'name') else str(b).lower()
                         for b in colony_buildings}

    has_tier1 = any("advanced manufacturing" in n for n in building_names)
    has_tier2 = any("high-tech manufacturing" in n or "high tech manufacturing" in n
                    for n in building_names)

    weapons = []
    seen = set()

    for wpn in ALL_WEAPONS:
        if not can_use_weapon(char_class, wpn):
            continue
        # Check tier availability
        if wpn.tier == WeaponTier.TIER_1 and not has_tier1:
            continue
        if wpn.tier == WeaponTier.TIER_2 and not has_tier2:
            continue
        if wpn.name not in seen:
            weapons.append(wpn)
            seen.add(wpn.name)

    return weapons

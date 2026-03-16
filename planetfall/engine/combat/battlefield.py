"""Zone-based battlefield representation.

The tabletop game uses exact inch measurements on a physical table.
We abstract this into a grid of 4"x4" zones that preserves tactical
decisions (flanking, cover, positioning) while mapping closely to
actual weapon ranges and movement distances.

Grid sizes (4" zones):
    6x6 = 24"x24" (2'x2' table) — small missions
    9x9 = 36"x36" (3'x3' table) — standard missions

Row 0 = enemy edge, last row = player edge.
"""

from __future__ import annotations

import re
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


def _base_species_name(fig_name: str) -> str:
    """Extract species/type base name from a figure name like 'HowlerFox 3 (Pack Leader)' -> 'HowlerFox'."""
    return re.sub(r'\s*\d+.*$', '', fig_name).strip() or fig_name


class TerrainType(str, Enum):
    OPEN = "open"
    LIGHT_COVER = "light_cover"      # Scatter terrain, low walls
    HEAVY_COVER = "heavy_cover"      # Forest, ruins, barricades
    HIGH_GROUND = "high_ground"      # Hills, elevated positions
    IMPASSABLE = "impassable"        # Cannot enter, does NOT block LoS
    IMPASSABLE_BLOCKING = "impassable_blocking"  # Cannot enter, blocks LoS


def is_impassable(terrain: TerrainType) -> bool:
    """Check if terrain is any impassable variant (blocking or non-blocking)."""
    return terrain in (TerrainType.IMPASSABLE, TerrainType.IMPASSABLE_BLOCKING)


class FigureStatus(str, Enum):
    ACTIVE = "active"
    STUNNED = "stunned"
    SPRAWLING = "sprawling"
    CASUALTY = "casualty"


class FigureSide(str, Enum):
    PLAYER = "player"
    ENEMY = "enemy"


# Weapon abbreviation lookup (shared by CLI + web via Figure.abbreviation)
_WEAPON_ABBREVS: dict[str, str] = {
    "rattle gun": "RG", "military rifle": "MR", "colony rifle": "CR",
    "auto rifle": "AR", "hunting rifle": "HR", "scrap gun": "SG",
    "hand cannon": "HC", "blade": "BL", "ripper sword": "RS",
    "shatter axe": "SA", "shotgun": "SH", "infantry rifle": "IR",
    "trooper rifle": "TR", "assault gun": "AG", "light machine gun": "LM",
    "flame projector": "FP", "handgun": "HG", "colonial shotgun": "CS",
    "scout pistol": "SP", "natural weapons": "NW", "unarmed": "UA",
}


@dataclass
class Figure:
    """A figure on the battlefield (player character, grunt, or enemy)."""
    name: str
    side: FigureSide
    zone: tuple[int, int] = (2, 1)  # row, col — default player center
    speed: int = 4
    reactions: int = 1
    combat_skill: int = 0
    toughness: int = 3
    savvy: int = 0
    kill_points: int = 0
    status: FigureStatus = FigureStatus.ACTIVE
    stun_markers: int = 0
    has_acted: bool = False
    weapon_name: str = ""
    weapon_range: int = 18
    weapon_shots: int = 1
    weapon_damage: int = 0
    weapon_traits: list[str] = field(default_factory=list)
    melee_damage: int = 0  # bonus for melee weapon
    armor_save: int = 0    # 0 = no save, 5 = 5+, 6 = 6+
    hit_bonus: int = 0     # temporary hit bonus (e.g. calibration from step 17)
    char_class: str = ""   # scientist, scout, trooper, grunt, bot, enemy
    is_leader: bool = False
    is_specialist: bool = False
    panic_range: int = 0   # 0 = fearless; 1 = panic on 1; 2 = on 1-2; etc.
    special_rules: list[str] = field(default_factory=list)
    is_contact: bool = False  # hidden enemy contact (revealed when player approaches)
    aid_marker: bool = False  # has an Aid marker (can be spent for +1/-1 bonuses)
    fireteam_id: str = ""     # fireteam name (e.g. "Alpha") — grunts in same fireteam share 1 initiative die

    @property
    def abbreviation(self) -> str:
        """2-letter abbreviation: weapon abbrev for enemies, name initials for players."""
        if self.side == FigureSide.ENEMY:
            key = self.weapon_name.strip().lower()
            if key in _WEAPON_ABBREVS:
                return _WEAPON_ABBREVS[key]
            parts = self.weapon_name.split()
            if len(parts) >= 2:
                return (parts[0][0] + parts[1][0]).upper()
            return self.weapon_name[:2].upper()
        else:
            parts = self.name.split()
            if len(parts) >= 2:
                return (parts[0][0] + parts[1][0]).upper()
            return self.name[:2].upper()

    def display_label(self, code: str) -> str:
        """Build the full display label from a base code (e.g. '1RG').

        Appends status suffixes (~stunned, _sprawling, Xcasualty)
        and +aid marker.  Contacts always return '??'.
        """
        if self.is_contact:
            return "??"
        if self.status == FigureStatus.STUNNED:
            code += "~"
        elif self.status == FigureStatus.SPRAWLING:
            code += "_"
        elif self.status == FigureStatus.CASUALTY:
            code += "X"
        if self.aid_marker:
            code += "+"
        return code

    def to_dict(self) -> dict:
        return {
            "name": self.name, "side": self.side.value,
            "zone": list(self.zone), "speed": self.speed,
            "reactions": self.reactions, "combat_skill": self.combat_skill,
            "toughness": self.toughness, "savvy": self.savvy,
            "kill_points": self.kill_points, "status": self.status.value,
            "stun_markers": self.stun_markers, "has_acted": self.has_acted,
            "weapon_name": self.weapon_name, "weapon_range": self.weapon_range,
            "weapon_shots": self.weapon_shots, "weapon_damage": self.weapon_damage,
            "weapon_traits": list(self.weapon_traits),
            "melee_damage": self.melee_damage, "armor_save": self.armor_save,
            "hit_bonus": self.hit_bonus, "char_class": self.char_class,
            "is_leader": self.is_leader, "is_specialist": self.is_specialist,
            "panic_range": self.panic_range,
            "special_rules": list(self.special_rules),
            "is_contact": self.is_contact, "aid_marker": self.aid_marker,
            "fireteam_id": self.fireteam_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Figure":
        return cls(
            name=d["name"], side=FigureSide(d["side"]),
            zone=tuple(d["zone"]), speed=d.get("speed", 4),
            reactions=d.get("reactions", 1),
            combat_skill=d.get("combat_skill", 0),
            toughness=d.get("toughness", 3),
            savvy=d.get("savvy", 0),
            kill_points=d.get("kill_points", 0),
            status=FigureStatus(d.get("status", "active")),
            stun_markers=d.get("stun_markers", 0),
            has_acted=d.get("has_acted", False),
            weapon_name=d.get("weapon_name", ""),
            weapon_range=d.get("weapon_range", 18),
            weapon_shots=d.get("weapon_shots", 1),
            weapon_damage=d.get("weapon_damage", 0),
            weapon_traits=d.get("weapon_traits", []),
            melee_damage=d.get("melee_damage", 0),
            armor_save=d.get("armor_save", 0),
            hit_bonus=d.get("hit_bonus", 0),
            char_class=d.get("char_class", ""),
            is_leader=d.get("is_leader", False),
            is_specialist=d.get("is_specialist", False),
            panic_range=d.get("panic_range", 0),
            special_rules=d.get("special_rules", []),
            is_contact=d.get("is_contact", False),
            aid_marker=d.get("aid_marker", False),
            fireteam_id=d.get("fireteam_id", ""),
        )

    @property
    def is_alive(self) -> bool:
        return self.status != FigureStatus.CASUALTY

    @property
    def is_active(self) -> bool:
        return self.status == FigureStatus.ACTIVE

    @property
    def effective_toughness(self) -> int:
        """Toughness is reduced by 1 when stunned or sprawling."""
        if self.status in (FigureStatus.STUNNED, FigureStatus.SPRAWLING):
            return max(1, self.toughness - 1)
        return self.toughness

    @property
    def can_act(self) -> bool:
        return self.is_alive and self.status != FigureStatus.CASUALTY


@dataclass
class Zone:
    """A zone on the battlefield grid."""
    row: int
    col: int
    terrain: TerrainType = TerrainType.OPEN
    difficult: bool = False  # Difficult ground — movement penalties apply
    terrain_name: str = ""  # Thematic name (e.g. "Copse", "Tor") — set by generation
    has_objective: bool = False
    objective_label: str = ""
    has_cloud: bool = False
    unstable: bool = False  # Unstable terrain — D6=1 collapse on movement/fire
    uncertain: bool = False  # Uncertain terrain feature — not yet revealed
    notes: str = ""

    def to_dict(self) -> dict:
        d = {
            "row": self.row, "col": self.col,
            "terrain": self.terrain.value,
            "has_objective": self.has_objective,
            "objective_label": self.objective_label,
            "notes": self.notes,
        }
        if self.difficult:
            d["difficult"] = True
        if self.terrain_name:
            d["terrain_name"] = self.terrain_name
        if self.has_cloud:
            d["has_cloud"] = True
        if self.unstable:
            d["unstable"] = True
        if self.uncertain:
            d["uncertain"] = True
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Zone":
        return cls(
            row=d["row"], col=d["col"],
            terrain=TerrainType(d.get("terrain", "open")),
            difficult=d.get("difficult", False),
            terrain_name=d.get("terrain_name", ""),
            has_objective=d.get("has_objective", False),
            objective_label=d.get("objective_label", ""),
            has_cloud=d.get("has_cloud", False),
            unstable=d.get("unstable", False),
            uncertain=d.get("uncertain", False),
            notes=d.get("notes", ""),
        )


# Zone size in inches (each grid cell represents this many inches)
ZONE_INCHES = 4

# Max friendly figures per zone (stacking limit)
MAX_FIGURES_PER_ZONE = 2

# Contact detection ranges (zones)
# Close range: within 9" (2 zones) — auto-detect clear LoS, D6 4+ obscured
CONTACT_CLOSE_RANGE = 2
CONTACT_EXTREME_RANGE = 6  # Clear LoS at 5-6 zones → D6 4+ detection
# Far range: within 18" (4 zones) — auto-detect clear LoS only
CONTACT_FAR_RANGE = 4

# Grid presets: table size → (rows, cols)
GRID_SMALL = (6, 6)    # 2'x2' table (24"x24")
GRID_STANDARD = (9, 9)  # 3'x3' table (36"x36")


# ── Module-level LoS & contact detection functions ────────────────────
#
# Extracted from Battlefield methods for reuse and testability.
# The Battlefield class retains thin wrappers that delegate here.


def compute_zones_between(
    bf: "Battlefield", z1: tuple[int, int], z2: tuple[int, int],
) -> list[tuple[int, int]]:
    """Get all zones along a line between z1 and z2 (excluding endpoints).

    Uses Bresenham-style supercover line algorithm to get every zone
    the line passes through, ensuring no gaps on diagonals.
    """
    r1, c1 = z1
    r2, c2 = z2
    dr = abs(r2 - r1)
    dc = abs(c2 - c1)
    sr = 1 if r2 > r1 else -1 if r2 < r1 else 0
    sc = 1 if c2 > c1 else -1 if c2 < c1 else 0

    zones: list[tuple[int, int]] = []
    r, c = r1, c1
    err = dr - dc

    # Walk the line (excluding start and end)
    steps = max(dr, dc)
    for _ in range(steps + dc + dr):  # generous bound
        if (r, c) == (r2, c2):
            break
        e2 = 2 * err
        if e2 > -dc:
            err -= dc
            r += sr
        if e2 < dr:
            err += dr
            c += sc
        if (r, c) != (r2, c2):
            zones.append((r, c))

    return zones


def compute_los(
    bf: "Battlefield", z1: tuple[int, int], z2: tuple[int, int],
) -> str:
    """Check line of sight between two zones.

    Returns:
        "clear"    — no intervening cover or blocking terrain
        "obscured" — light/heavy cover in the path (partial LoS)
        "blocked"  — impassable/high ground blocks LoS

    High ground rules:
    - High ground always blocks LoS to zones beyond it.
    - If the observer (z1) is on high ground, the first intervening
      high ground zone is visible (target can be ON that ridge),
      but everything past it is blocked.
    - If not on high ground, any intervening high ground blocks.
    """
    if z1 == z2:
        return "clear"

    z1_terrain = bf.zones[z1[0]][z1[1]].terrain if (
        0 <= z1[0] < bf.rows and 0 <= z1[1] < bf.cols
    ) else TerrainType.OPEN
    observer_on_high = z1_terrain == TerrainType.HIGH_GROUND

    between = compute_zones_between(bf, z1, z2)

    has_cover = False
    high_ground_seen = False  # have we already passed a high ground zone?
    for pos in between:
        r, c = pos
        if not (0 <= r < bf.rows and 0 <= c < bf.cols):
            continue
        terrain = bf.zones[r][c].terrain
        if terrain == TerrainType.IMPASSABLE_BLOCKING:
            return "blocked"
        if terrain == TerrainType.HIGH_GROUND:
            if not observer_on_high:
                # Not on high ground — any ridge blocks
                return "blocked"
            if high_ground_seen:
                # On high ground but already passed one ridge — blocked
                return "blocked"
            high_ground_seen = True
        if terrain in (TerrainType.HEAVY_COVER, TerrainType.LIGHT_COVER):
            has_cover = True

    # If we passed through a high ground zone and target is beyond it,
    # the target is blocked (high ground blocks everything past it).
    # But if the target IS on the high ground zone, it was the last
    # element in `between` or the target itself — check target zone.
    z2_terrain = bf.zones[z2[0]][z2[1]].terrain if (
        0 <= z2[0] < bf.rows and 0 <= z2[1] < bf.cols
    ) else TerrainType.OPEN
    if high_ground_seen and z2_terrain != TerrainType.HIGH_GROUND:
        return "blocked"

    # Target zone's own cover also obscures LoS
    if z2_terrain in (TerrainType.HEAVY_COVER, TerrainType.LIGHT_COVER):
        has_cover = True

    return "obscured" if has_cover else "clear"


def compute_cover_los(
    bf: "Battlefield",
    shooter_zone: tuple[int, int],
    target_zone: tuple[int, int],
) -> bool:
    """Check if target benefits from heavy cover along the line of sight.

    Returns True if:
    - Target zone itself is heavy cover, OR
    - Any zone between shooter and target is heavy cover
    """
    if bf.get_zone(*target_zone).terrain == TerrainType.HEAVY_COVER:
        return True
    between = compute_zones_between(bf, shooter_zone, target_zone)
    for r, c in between:
        if bf.get_zone(r, c).terrain == TerrainType.HEAVY_COVER:
            return True
    return False


def compute_detect_contacts_auto(bf: "Battlefield") -> list[Figure]:
    """Detect contacts that are automatically revealed (no roll needed).

    Auto-detect conditions:
    - Same zone: always detected
    - 1-2 zones: detected unless LoS blocked
    - 3-4 zones: detected if clear LoS
    """
    detected = []
    player_figs = bf.get_player_figures()
    for fig in bf.figures:
        if not fig.is_contact or not fig.is_alive:
            continue
        for pf in player_figs:
            dist = bf.zone_distance(fig.zone, pf.zone)
            if dist == 0:
                # Same zone — always detected
                detected.append(fig)
                break
            los = compute_los(bf, pf.zone, fig.zone)
            if dist <= CONTACT_CLOSE_RANGE:
                # 1-2 zones — detect unless blocked
                if los != "blocked":
                    detected.append(fig)
                    break
            elif dist <= CONTACT_FAR_RANGE:
                # 3-4 zones — detect if clear LoS
                if los == "clear":
                    detected.append(fig)
                    break
    return detected


def compute_detect_contacts_obscured(bf: "Battlefield") -> list[Figure]:
    """Detect non-auto contacts via D6 4+ roll.

    Triggers for:
    - Obscured LoS within FAR_RANGE (4 zones): D6 4+
    - Clear LoS at EXTREME_RANGE (5-6 zones): D6 4+
    Called during Enemy Phase.
    """
    from planetfall.engine.dice import roll_d6
    detected = []
    player_figs = bf.get_player_figures()
    already_auto = {id(f) for f in compute_detect_contacts_auto(bf)}
    for fig in bf.figures:
        if not fig.is_contact or not fig.is_alive:
            continue
        if id(fig) in already_auto:
            continue  # already auto-detected, skip
        for pf in player_figs:
            dist = bf.zone_distance(fig.zone, pf.zone)
            los = compute_los(bf, pf.zone, fig.zone)
            needs_roll = False
            if dist <= CONTACT_FAR_RANGE and los == "obscured":
                # Obscured within 4 zones
                needs_roll = True
            elif CONTACT_FAR_RANGE < dist <= CONTACT_EXTREME_RANGE and los == "clear":
                # Clear LoS but far away (5-6 zones)
                needs_roll = True
            if needs_roll:
                roll = roll_d6(f"Detect {fig.name}")
                if roll.total >= 4:
                    detected.append(fig)
                break  # only roll once per contact
    return detected


def compute_reveal_contact(bf: "Battlefield", contact: Figure) -> list[str]:
    """Reveal a detected contact using the Contact Reveal table (D6).

    D6 results:
    1-2: False alarm — remove contact
    3:   False alarm — place 2 new contacts at random edge zones
    4-5: 1 Lifeform (contact revealed as its figure)
    6:   2 Lifeforms (reveal + spawn 1 additional adjacent)

    Returns log lines describing what happened.
    """
    import random as rng
    from planetfall.engine.dice import roll_d6

    roll = roll_d6(f"Reveal {contact.name}")
    log = [f"Contact Reveal — {contact.name}: D6 = {roll.total}"]

    if roll.total <= 2:
        # False alarm — remove
        contact.status = FigureStatus.CASUALTY
        contact.is_contact = False
        log.append(f"  False alarm! {contact.name} was nothing.")
        return log

    if roll.total == 3:
        # False alarm — spawn 2 new contacts at edges
        contact.status = FigureStatus.CASUALTY
        contact.is_contact = False
        log.append(f"  False alarm! But 2 new contacts appear at the edges.")
        edge_zones = [z for z in bf._get_edge_zones()
                      if bf.zone_has_capacity(*z, FigureSide.ENEMY)]
        for i in range(2):
            if edge_zones:
                spawn_zone = rng.choice(edge_zones)
                _species = _base_species_name(contact.name)
                new_fig = Figure(
                    name=f"{_species} {len(bf.figures) + 1}",
                    side=FigureSide.ENEMY,
                    zone=spawn_zone,
                    toughness=contact.toughness,
                    combat_skill=contact.combat_skill,
                    speed=contact.speed,
                    melee_damage=contact.melee_damage,
                    armor_save=contact.armor_save,
                    kill_points=contact.kill_points,
                    weapon_name=contact.weapon_name,
                    weapon_range=contact.weapon_range,
                    weapon_shots=contact.weapon_shots,
                    weapon_damage=contact.weapon_damage,
                    weapon_traits=list(contact.weapon_traits),
                    special_rules=list(contact.special_rules),
                    char_class=contact.char_class,
                    is_contact=True,
                )
                bf.figures.append(new_fig)
                log.append(f"  New contact placed at zone {spawn_zone}.")
        return log

    if roll.total <= 5:
        # 1 Lifeform — reveal the contact as-is
        contact.is_contact = False
        log.append(f"  {contact.name} revealed as a hostile!")
        return log

    # roll == 6: 2 Lifeforms — reveal + spawn 1 additional
    contact.is_contact = False
    log.append(f"  {contact.name} revealed — and it's not alone!")
    adj = bf.adjacent_zones(*contact.zone)
    valid_adj = [z for z in adj if bf.zone_has_capacity(*z, FigureSide.ENEMY)]
    cover_adj = [z for z in valid_adj if bf.has_cover(z)]
    spawn_zone = rng.choice(cover_adj) if cover_adj else (rng.choice(valid_adj) if valid_adj else contact.zone)
    _species = _base_species_name(contact.name)
    extra = Figure(
        name=f"{_species} {len(bf.figures) + 1}",
        side=FigureSide.ENEMY,
        zone=spawn_zone,
        toughness=contact.toughness,
        combat_skill=contact.combat_skill,
        speed=contact.speed,
        melee_damage=contact.melee_damage,
        armor_save=contact.armor_save,
        kill_points=contact.kill_points,
        weapon_name=contact.weapon_name,
        weapon_range=contact.weapon_range,
        weapon_shots=contact.weapon_shots,
        weapon_damage=contact.weapon_damage,
        weapon_traits=list(contact.weapon_traits),
        special_rules=list(contact.special_rules),
        char_class=contact.char_class,
        is_contact=False,
    )
    bf.figures.append(extra)
    log.append(f"  Additional hostile appears at zone {spawn_zone}!")
    return log


@dataclass
class Battlefield:
    """Variable-size zone-based battlefield (4" per zone)."""
    zones: list[list[Zone]] = field(default_factory=list)
    figures: list[Figure] = field(default_factory=list)
    round_number: int = 0
    battle_log: list[str] = field(default_factory=list)
    rows: int = 6
    cols: int = 6
    # Condition-driven battlefield state
    exit_zones: list[tuple[int, int]] = field(default_factory=list)  # Confined Spaces
    cloud_positions: list[tuple[int, int]] = field(default_factory=list)  # Drifting Clouds
    cloud_type: str = ""  # "safe", "toxic", "corrosive"
    cloud_toxin_level: int = 0  # For toxic clouds
    unstable_terrain_type: str = ""  # Terrain type selected for Unstable Terrain
    uncertain_features: list[tuple[int, int]] = field(default_factory=list)  # Uncertain terrain zones

    def __post_init__(self):
        if not self.zones:
            self.zones = [
                [Zone(row=r, col=c) for c in range(self.cols)]
                for r in range(self.rows)
            ]
        else:
            # Infer dimensions from provided zones
            self.rows = len(self.zones)
            self.cols = len(self.zones[0]) if self.zones else 0

    def to_dict(self) -> dict:
        d = {
            "rows": self.rows, "cols": self.cols,
            "round_number": self.round_number,
            "battle_log": list(self.battle_log),
            "zones": [[z.to_dict() for z in row] for row in self.zones],
            "figures": [f.to_dict() for f in self.figures],
        }
        if self.exit_zones:
            d["exit_zones"] = [list(z) for z in self.exit_zones]
        if self.cloud_positions:
            d["cloud_positions"] = [list(z) for z in self.cloud_positions]
            d["cloud_type"] = self.cloud_type
            d["cloud_toxin_level"] = self.cloud_toxin_level
        if self.unstable_terrain_type:
            d["unstable_terrain_type"] = self.unstable_terrain_type
        if self.uncertain_features:
            d["uncertain_features"] = [list(z) for z in self.uncertain_features]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Battlefield":
        zones = [[Zone.from_dict(z) for z in row] for row in d["zones"]]
        figures = [Figure.from_dict(f) for f in d["figures"]]
        bf = cls.__new__(cls)
        bf.rows = d["rows"]
        bf.cols = d["cols"]
        bf.round_number = d.get("round_number", 0)
        bf.battle_log = d.get("battle_log", [])
        bf.zones = zones
        bf.figures = figures
        bf.exit_zones = [tuple(z) for z in d.get("exit_zones", [])]
        bf.cloud_positions = [tuple(z) for z in d.get("cloud_positions", [])]
        bf.cloud_type = d.get("cloud_type", "")
        bf.cloud_toxin_level = d.get("cloud_toxin_level", 0)
        bf.unstable_terrain_type = d.get("unstable_terrain_type", "")
        bf.uncertain_features = [tuple(z) for z in d.get("uncertain_features", [])]
        return bf

    def get_zone(self, row: int, col: int) -> Zone:
        return self.zones[row][col]

    def get_figures_in_zone(self, row: int, col: int) -> list[Figure]:
        return [f for f in self.figures if f.zone == (row, col) and f.is_alive]

    def get_player_figures(self) -> list[Figure]:
        return [f for f in self.figures if f.side == FigureSide.PLAYER and f.is_alive]

    def get_enemy_figures(self) -> list[Figure]:
        return [f for f in self.figures if f.side == FigureSide.ENEMY and f.is_alive]

    def get_figure_by_name(self, name: str) -> Optional[Figure]:
        for f in self.figures:
            if f.name == name:
                return f
        return None

    def get_fireteam_members(self, fireteam_id: str) -> list[Figure]:
        """Get all alive figures belonging to a fireteam."""
        if not fireteam_id:
            return []
        return [f for f in self.figures if f.fireteam_id == fireteam_id and f.is_alive]

    def fireteam_in_formation(self, fireteam_id: str) -> bool:
        """Check if a fireteam is in formation for the Reactions bonus.

        - 1 grunt: never in formation.
        - 2 grunts: must be in the same zone.
        - 3-4 grunts: must all be within adjacent zones of each other
          (every pair at most 1 zone apart).
        """
        members = self.get_fireteam_members(fireteam_id)
        if len(members) < 2:
            return False
        if len(members) == 2:
            return members[0].zone == members[1].zone
        # 3-4 members: every pair must be adjacent (Chebyshev distance ≤ 1)
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                if self.zone_distance(a.zone, b.zone) > 1:
                    return False
        return True

    def get_fireteam_ids(self) -> list[str]:
        """Get unique fireteam IDs for alive player figures."""
        ids = set()
        for f in self.figures:
            if f.fireteam_id and f.side == FigureSide.PLAYER and f.is_alive:
                ids.add(f.fireteam_id)
        return sorted(ids)

    def zone_friendly_count(self, row: int, col: int, side: FigureSide) -> int:
        """Count alive figures of the given side in a zone."""
        return sum(1 for f in self.figures
                   if f.zone == (row, col) and f.is_alive and f.side == side)

    def zone_has_capacity(self, row: int, col: int, side: FigureSide) -> bool:
        """Check if a zone can accept another friendly figure (stacking limit)."""
        return self.zone_friendly_count(row, col, side) < MAX_FIGURES_PER_ZONE

    def zone_distance(self, z1: tuple[int, int], z2: tuple[int, int]) -> int:
        """Chebyshev distance between zones (diagonal = 1)."""
        return max(abs(z1[0] - z2[0]), abs(z1[1] - z2[1]))

    def is_adjacent(self, z1: tuple[int, int], z2: tuple[int, int]) -> bool:
        return self.zone_distance(z1, z2) <= 1 and z1 != z2

    def adjacent_zones(self, row: int, col: int) -> list[tuple[int, int]]:
        """Get all valid adjacent zone coordinates."""
        adj = []
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = row + dr, col + dc
                if 0 <= nr < self.rows and 0 <= nc < self.cols:
                    if not is_impassable(self.zones[nr][nc].terrain):
                        adj.append((nr, nc))
        return adj

    def jump_destinations(self, row: int, col: int, max_dist: int) -> list[tuple[int, int]]:
        """Get zones reachable by jump jets (straight-line, can cross impassable).

        Jump jets move in a straight line (8 directions) up to max_dist zones.
        Can cross impassable zones but cannot land on them.
        """
        destinations = []
        directions = [(-1, -1), (-1, 0), (-1, 1), (0, -1),
                      (0, 1), (1, -1), (1, 0), (1, 1)]
        for dr, dc in directions:
            for dist in range(1, max_dist + 1):
                nr, nc = row + dr * dist, col + dc * dist
                if not (0 <= nr < self.rows and 0 <= nc < self.cols):
                    break  # off grid, stop this direction
                if not is_impassable(self.zones[nr][nc].terrain) and (nr, nc) not in destinations:
                    destinations.append((nr, nc))
        return destinations

    def get_standard_move_zones(
        self, row: int, col: int, speed: int, is_scout: bool = False,
    ) -> list[tuple[int, int]]:
        """Canonical raw move destinations (no stacking check).

        For scouts: uses jump_destinations (straight-line, can cross impassable).
        For others: Chebyshev distance within move_zones(speed) range.
        Filters out impassable terrain and current zone.
        """
        num = move_zones(speed)
        if num == 0:
            return []
        if is_scout:
            return self.jump_destinations(row, col, num)
        results = []
        for dr in range(-num, num + 1):
            for dc in range(-num, num + 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = row + dr, col + dc
                if not (0 <= nr < self.rows and 0 <= nc < self.cols):
                    continue
                if max(abs(dr), abs(dc)) > num:
                    continue
                if not is_impassable(self.zones[nr][nc].terrain):
                    results.append((nr, nc))
        return results

    def get_rush_zones(
        self, row: int, col: int, speed: int,
    ) -> list[tuple[int, int]]:
        """Canonical raw rush/dash destinations (no stacking check).

        Returns zones reachable by rushing but NOT by standard movement.
        Uses rush_available() and rush_total_zones() from module level.
        """
        if not rush_available(speed):
            return []
        max_dist = rush_total_zones(speed)
        results = []
        for dr in range(-max_dist, max_dist + 1):
            for dc in range(-max_dist, max_dist + 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = row + dr, col + dc
                if not (0 <= nr < self.rows and 0 <= nc < self.cols):
                    continue
                if max(abs(dr), abs(dc)) > max_dist:
                    continue
                if not is_impassable(self.zones[nr][nc].terrain):
                    results.append((nr, nc))
        return results

    def has_cover(self, target_zone: tuple[int, int]) -> bool:
        """Check if a zone provides any cover/protection.

        Returns True for both light cover (scatter) and heavy cover.
        Used by AI movement, LoS checks, etc.
        For the shooting 6+ to-hit modifier, use has_heavy_cover().
        """
        zone = self.get_zone(*target_zone)
        return zone.terrain in (TerrainType.HEAVY_COVER, TerrainType.LIGHT_COVER)

    def has_heavy_cover(self, target_zone: tuple[int, int]) -> bool:
        """Check if a zone provides full cover (6+ to-hit modifier).

        Only heavy cover (forests, ruins, barricades) grants the 6+
        cover modifier. Light cover (scatter terrain) instead absorbs
        hits on exact rolls (handled separately in shooting code).
        """
        zone = self.get_zone(*target_zone)
        return zone.terrain == TerrainType.HEAVY_COVER

    def has_cover_los(self, shooter_zone: tuple[int, int], target_zone: tuple[int, int]) -> bool:
        """Check if target benefits from heavy cover along the line of sight."""
        return compute_cover_los(self, shooter_zone, target_zone)

    def target_in_cover_zone(self, target_zone: tuple[int, int]) -> bool:
        """Check if target is directly inside a heavy cover zone."""
        return self.get_zone(*target_zone).terrain == TerrainType.HEAVY_COVER

    def has_scatter(self, shooter_zone: tuple[int, int], target_zone: tuple[int, int]) -> bool:
        """Check if target is in scatter terrain (light cover zone).

        Scatter terrain absorbs hits: a hit roll that exactly matches the
        to-hit number means scatter absorbed the hit (no effect).
        Only applies when the target is in a light cover zone.
        """
        return self.get_zone(*target_zone).terrain == TerrainType.LIGHT_COVER

    def shooter_on_high_ground(
        self, shooter_zone: tuple[int, int], target_zone: tuple[int, int],
    ) -> bool:
        """Check if shooter is on high ground relative to target.

        Per rules p.35: target on lower ground only receives cover if
        within 1" of the far side of terrain. In zone terms, we simplify:
        shooter on HIGH_GROUND and target NOT on HIGH_GROUND = high ground advantage.
        """
        s = self.get_zone(*shooter_zone)
        t = self.get_zone(*target_zone)
        return (
            s.terrain == TerrainType.HIGH_GROUND
            and t.terrain != TerrainType.HIGH_GROUND
        )

    def get_zones_between(
        self, z1: tuple[int, int], z2: tuple[int, int],
    ) -> list[tuple[int, int]]:
        """Get all zones along a line between z1 and z2 (excluding endpoints)."""
        return compute_zones_between(self, z1, z2)

    def check_los(
        self, z1: tuple[int, int], z2: tuple[int, int],
    ) -> str:
        """Check line of sight between two zones."""
        return compute_los(self, z1, z2)

    def detect_contacts_auto(self) -> list[Figure]:
        """Detect contacts that are automatically revealed (no roll needed)."""
        return compute_detect_contacts_auto(self)

    def detect_contacts_obscured(self) -> list[Figure]:
        """Detect non-auto contacts via D6 4+ roll."""
        return compute_detect_contacts_obscured(self)

    def reveal_contact(self, contact: Figure) -> list[str]:
        """Reveal a detected contact using the Contact Reveal table (D6)."""
        return compute_reveal_contact(self, contact)

    def _get_edge_zones(self) -> list[tuple[int, int]]:
        """Get all non-impassable edge zones."""
        edges = []
        for c in range(self.cols):
            if not is_impassable(self.zones[0][c].terrain):
                edges.append((0, c))
            if not is_impassable(self.zones[self.rows - 1][c].terrain):
                edges.append((self.rows - 1, c))
        for r in range(1, self.rows - 1):
            if not is_impassable(self.zones[r][0].terrain):
                edges.append((r, 0))
            if not is_impassable(self.zones[r][self.cols - 1].terrain):
                edges.append((r, self.cols - 1))
        return edges

    def is_edge_zone(self, r: int, c: int) -> bool:
        """Check if a zone is on any battlefield edge."""
        return r == 0 or r == self.rows - 1 or c == 0 or c == self.cols - 1

    def log(self, message: str):
        self.battle_log.append(message)

    def remove_casualties(self):
        """Remove all casualty figures from the battlefield."""
        self.figures = [f for f in self.figures if f.is_alive]


# --- Zone Movement & Range Mapping ---
#
# Each zone is 4"x4". Zone distance maps directly to inches:
#   distance * ZONE_INCHES = approximate range in inches
#
# MOVEMENT (Speed stat → zone movement per activation):
#   Speed 1-2": move 0 zones. Rush: 1 zone (no action).
#   Speed 3-4": move 1 zone + action. No rush.
#   Speed 5-6": move 1 zone + action. Rush: 2 zones (no action).
#   Speed 7-8": move 2 zones + action. No rush.
#
# Rush is an ACTION that grants +2" additional movement.
# Figures with Speed 1-2" need Rush just to move 1 zone.
# Speed 5-6" figures use Rush to extend from 1 zone to 2 zones.
#
# Speed also matters for:
#   - Reaction rolls (higher Speed = more likely to act first)
#   - Brawling resolution
#   - Scenario-specific checks (escape, pursuit)
#
# RANGE (zone distance → tabletop inches):
#   Same zone (dist 0) → 0-2" (close range, melee possible)
#   dist 1 → ~4"    dist 2 → ~8"    dist 3 → ~12"
#   dist 4 → ~16"   dist 5 → ~20"   dist 6 → ~24"
#
# WEAPON RANGE EXAMPLES (4" zones):
#   Pistol 6"       → 1 zone    | Colony Rifle 18"   → 4 zones
#   Scout Pistol 9" → 2 zones   | Infantry Rifle 24" → 6 zones
#   Shotgun 12"     → 3 zones   | Trooper Rifle 30"  → 7 zones
#   Flame Proj 6"   → 1 zone    | LMG 36"            → 9 zones
#
# COVER:
#   Light Cover / Heavy Cover zones → target gets cover bonus
#   High Ground → elevated, no cover
#   Open → no cover bonus
#
# LINE OF SIGHT:
#   All zones have line of sight to all other zones (simplified).
#   Impassable zones cannot be entered but don't block LoS.

def zone_range_inches(distance: int) -> int:
    """Convert zone distance to approximate inch range for weapon checks.

    Each zone is ZONE_INCHES (4") wide. Center-to-center distance is
    distance * ZONE_INCHES. Same-zone is treated as ~2" (close range).
    """
    if distance == 0:
        return 2  # within same zone — close range / melee
    return distance * ZONE_INCHES


def move_zones(speed: int) -> int:
    """Number of zones a figure can move as their standard move.

    Speed 1-2": 0 zones (can't move without Rush).
    Speed 3-6": 1 zone.
    Speed 7+":  2 zones.
    """
    if speed <= 2:
        return 0
    if speed >= 7:
        return 2
    return 1


def rush_available(speed: int) -> bool:
    """Whether the Rush action is available for this Speed.

    Speed 1-2": Rush gives them their only movement (1 zone).
    Speed 5-6": Rush extends from 1 zone to 2 zones.
    Speed 3-4, 7-8": No rush available.
    """
    return speed <= 2 or speed in (5, 6)


def rush_total_zones(speed: int) -> int:
    """Total zone reach when using the Rush action (no other action).

    Speed 1-2": 1 zone.  Speed 5-6": 2 zones.
    """
    if speed <= 2:
        return 1
    return 2


# --- Difficult ground ---


def ignores_difficult_ground(figure: Figure) -> bool:
    """Check if a figure ignores difficult ground movement penalties.

    Scouts (jet packs) and partially airborne lifeforms are exempt.
    """
    if figure.char_class == "scout":
        return True
    if "partially_airborne" in figure.special_rules:
        return True
    return False


# --- Difficult ground movement modifiers ---

def move_zones_difficult(speed: int) -> int:
    """Standard move zones when moving in/out of difficult ground.

    Speed 1-3: 0 zones (must dash to move 1 zone)
    Speed 4-8: 1 zone
    """
    if speed <= 3:
        return 0
    return 1


def rush_available_difficult(speed: int) -> bool:
    """Whether Rush is available when moving in/out of difficult ground.

    Speed 1-3: yes (only way to move 1 zone)
    Speed 4-5: no (cannot dash in difficult ground)
    Speed 6-8: yes (can dash to move 2 zones)
    """
    return speed <= 3 or speed >= 6


def rush_total_zones_difficult(speed: int) -> int:
    """Total zone reach when rushing in/out of difficult ground.

    Speed 1-3: 1 zone.  Speed 6-8: 2 zones.
    """
    if speed <= 3:
        return 1
    return 2


# ── Per-sector terrain distributions & names ─────────────────
#
# Each sector terrain type defines:
#   "weights" — weighted pool of TerrainType values (picked via random.choice)
#   "names"   — mapping of (TerrainType, difficult?) → thematic zone name

SECTOR_TERRAIN_CONFIG: dict[str, dict] = {
    # Plains  — open grassland, few obstacles        IMP ~5%
    "plains": {
        "weights": [
            (TerrainType.OPEN, 8),
            (TerrainType.LIGHT_COVER, 4),
            (TerrainType.HEAVY_COVER, 4),
            (TerrainType.HIGH_GROUND, 2),
            (TerrainType.IMPASSABLE, 1),
        ],
        "names": {
            (TerrainType.OPEN, False): "Open Ground",
            (TerrainType.OPEN, True): "Open Ground",
            (TerrainType.LIGHT_COVER, False): "Scrub Patch",
            (TerrainType.LIGHT_COVER, True): "Broken Ground",
            (TerrainType.HEAVY_COVER, False): "Copse",
            (TerrainType.HEAVY_COVER, True): "Thicket",
            (TerrainType.HIGH_GROUND, False): "Hill",
            (TerrainType.HIGH_GROUND, True): "Tor",
            (TerrainType.IMPASSABLE, False): "Sinkhole",
            (TerrainType.IMPASSABLE, True): "Sinkhole",
            (TerrainType.IMPASSABLE_BLOCKING, False): "Termite Mound",
            (TerrainType.IMPASSABLE_BLOCKING, True): "Termite Mound",
        },
    },
    # Forest  — dense growth, lots of cover          IMP ~10%
    "forest": {
        "weights": [
            (TerrainType.OPEN, 1),
            (TerrainType.LIGHT_COVER, 3),
            (TerrainType.HEAVY_COVER, 3),
            (TerrainType.HIGH_GROUND, 1),
            (TerrainType.IMPASSABLE, 1),
        ],
        "names": {
            (TerrainType.OPEN, False): "Clearing",
            (TerrainType.OPEN, True): "Clearing",
            (TerrainType.LIGHT_COVER, False): "Undergrowth",
            (TerrainType.LIGHT_COVER, True): "Tangled Brush",
            (TerrainType.HEAVY_COVER, False): "Dense Canopy",
            (TerrainType.HEAVY_COVER, True): "Root Maze",
            (TerrainType.HIGH_GROUND, False): "Fallen Trunk",
            (TerrainType.HIGH_GROUND, True): "Overgrown Rise",
            (TerrainType.IMPASSABLE, False): "Deadfall",
            (TerrainType.IMPASSABLE, True): "Deadfall",
            (TerrainType.IMPASSABLE_BLOCKING, False): "Ancient Trunk",
            (TerrainType.IMPASSABLE_BLOCKING, True): "Ancient Trunk",
        },
    },
    # Hills   — high ground dominant, cliffs         IMP ~10%
    "hills": {
        "weights": [
            (TerrainType.OPEN, 2),
            (TerrainType.LIGHT_COVER, 1),
            (TerrainType.HEAVY_COVER, 1),
            (TerrainType.HIGH_GROUND, 4),
            (TerrainType.IMPASSABLE, 1),
        ],
        "names": {
            (TerrainType.OPEN, False): "Open Slope",
            (TerrainType.OPEN, True): "Open Slope",
            (TerrainType.LIGHT_COVER, False): "Scree Field",
            (TerrainType.LIGHT_COVER, True): "Boulder Scatter",
            (TerrainType.HEAVY_COVER, False): "Rock Outcrop",
            (TerrainType.HEAVY_COVER, True): "Crag Shelter",
            (TerrainType.HIGH_GROUND, False): "Ridge",
            (TerrainType.HIGH_GROUND, True): "Bluff",
            (TerrainType.IMPASSABLE, False): "Ravine",
            (TerrainType.IMPASSABLE, True): "Ravine",
            (TerrainType.IMPASSABLE_BLOCKING, False): "Cliff Face",
            (TerrainType.IMPASSABLE_BLOCKING, True): "Cliff Face",
        },
    },
    # Ruins   — dense cover, lots of collapsed areas IMP ~20%
    "ruins": {
        "weights": [
            (TerrainType.OPEN, 1),
            (TerrainType.LIGHT_COVER, 2),
            (TerrainType.HEAVY_COVER, 3),
            (TerrainType.HIGH_GROUND, 1),
            (TerrainType.IMPASSABLE, 2),
        ],
        "names": {
            (TerrainType.OPEN, False): "Rubble Flat",
            (TerrainType.OPEN, True): "Rubble Flat",
            (TerrainType.LIGHT_COVER, False): "Debris Field",
            (TerrainType.LIGHT_COVER, True): "Collapsed Wall",
            (TerrainType.HEAVY_COVER, False): "Ruined Structure",
            (TerrainType.HEAVY_COVER, True): "Shattered Hab",
            (TerrainType.HIGH_GROUND, False): "Upper Floor",
            (TerrainType.HIGH_GROUND, True): "Unstable Platform",
            (TerrainType.IMPASSABLE, False): "Rubble Pit",
            (TerrainType.IMPASSABLE, True): "Rubble Pit",
            (TerrainType.IMPASSABLE_BLOCKING, False): "Collapsed Building",
            (TerrainType.IMPASSABLE_BLOCKING, True): "Collapsed Building",
        },
    },
    # Wetlands — balanced cover, deep water          IMP ~10%
    "wetlands": {
        "weights": [
            (TerrainType.OPEN, 2),
            (TerrainType.LIGHT_COVER, 2),
            (TerrainType.HEAVY_COVER, 3),
            (TerrainType.HIGH_GROUND, 1),
            (TerrainType.IMPASSABLE, 1),
        ],
        "names": {
            (TerrainType.OPEN, False): "Mud Flat",
            (TerrainType.OPEN, True): "Mud Flat",
            (TerrainType.LIGHT_COVER, False): "Reed Bed",
            (TerrainType.LIGHT_COVER, True): "Boggy Reeds",
            (TerrainType.HEAVY_COVER, False): "Mangrove Tangle",
            (TerrainType.HEAVY_COVER, True): "Deep Marsh",
            (TerrainType.HIGH_GROUND, False): "Dry Mound",
            (TerrainType.HIGH_GROUND, True): "Slippery Bank",
            (TerrainType.IMPASSABLE, False): "Deep Water",
            (TerrainType.IMPASSABLE, True): "Deep Water",
            (TerrainType.IMPASSABLE_BLOCKING, False): "Dam Wall",
            (TerrainType.IMPASSABLE_BLOCKING, True): "Dam Wall",
        },
    },
    # Crags   — vertical, jagged, many chasms        IMP ~30%
    "crags": {
        "weights": [
            (TerrainType.OPEN, 1),
            (TerrainType.LIGHT_COVER, 1),
            (TerrainType.HEAVY_COVER, 1),
            (TerrainType.HIGH_GROUND, 4),
            (TerrainType.IMPASSABLE, 3),
        ],
        "names": {
            (TerrainType.OPEN, False): "Ravine Floor",
            (TerrainType.OPEN, True): "Ravine Floor",
            (TerrainType.LIGHT_COVER, False): "Loose Shale",
            (TerrainType.LIGHT_COVER, True): "Jagged Scree",
            (TerrainType.HEAVY_COVER, False): "Rock Column",
            (TerrainType.HEAVY_COVER, True): "Crystal Fissure",
            (TerrainType.HIGH_GROUND, False): "Pinnacle",
            (TerrainType.HIGH_GROUND, True): "Knife Edge",
            (TerrainType.IMPASSABLE, False): "Chasm",
            (TerrainType.IMPASSABLE, True): "Chasm",
            (TerrainType.IMPASSABLE_BLOCKING, False): "Rock Wall",
            (TerrainType.IMPASSABLE_BLOCKING, True): "Rock Wall",
        },
    },
    # Desert  — wide open, sparse cover              IMP ~5%
    "desert": {
        "weights": [
            (TerrainType.OPEN, 8),
            (TerrainType.LIGHT_COVER, 4),
            (TerrainType.HEAVY_COVER, 2),
            (TerrainType.HIGH_GROUND, 4),
            (TerrainType.IMPASSABLE, 1),
        ],
        "names": {
            (TerrainType.OPEN, False): "Sand Flat",
            (TerrainType.OPEN, True): "Sand Flat",
            (TerrainType.LIGHT_COVER, False): "Rock Scatter",
            (TerrainType.LIGHT_COVER, True): "Shifting Dune",
            (TerrainType.HEAVY_COVER, False): "Sandstone Shelf",
            (TerrainType.HEAVY_COVER, True): "Sinkhole",
            (TerrainType.HIGH_GROUND, False): "Dune Crest",
            (TerrainType.HIGH_GROUND, True): "Eroded Mesa",
            (TerrainType.IMPASSABLE, False): "Sand Pit",
            (TerrainType.IMPASSABLE, True): "Sand Pit",
            (TerrainType.IMPASSABLE_BLOCKING, False): "Canyon Wall",
            (TerrainType.IMPASSABLE_BLOCKING, True): "Canyon Wall",
        },
    },
    # Tundra  — frozen wasteland, crevasses           IMP ~10%
    "tundra": {
        "weights": [
            (TerrainType.OPEN, 3),
            (TerrainType.LIGHT_COVER, 2),
            (TerrainType.HEAVY_COVER, 1),
            (TerrainType.HIGH_GROUND, 2),
            (TerrainType.IMPASSABLE, 1),
        ],
        "names": {
            (TerrainType.OPEN, False): "Frozen Plain",
            (TerrainType.OPEN, True): "Frozen Plain",
            (TerrainType.LIGHT_COVER, False): "Ice Rubble",
            (TerrainType.LIGHT_COVER, True): "Frost Heave",
            (TerrainType.HEAVY_COVER, False): "Ice Formation",
            (TerrainType.HEAVY_COVER, True): "Crevasse Edge",
            (TerrainType.HIGH_GROUND, False): "Ice Ridge",
            (TerrainType.HIGH_GROUND, True): "Glacial Shelf",
            (TerrainType.IMPASSABLE, False): "Crevasse",
            (TerrainType.IMPASSABLE, True): "Crevasse",
            (TerrainType.IMPASSABLE_BLOCKING, False): "Ice Wall",
            (TerrainType.IMPASSABLE_BLOCKING, True): "Ice Wall",
        },
    },
}

# Default fallback (used when no sector terrain specified)
_DEFAULT_WEIGHTS = [
    (TerrainType.OPEN, 3),
    (TerrainType.LIGHT_COVER, 2),
    (TerrainType.HEAVY_COVER, 2),
    (TerrainType.HIGH_GROUND, 2),
    (TerrainType.IMPASSABLE, 1),
]


def generate_random_terrain(
    rows: int = 6, cols: int = 6,
    sector_terrain: str | None = None,
) -> list[list[Zone]]:
    """Generate randomized terrain for a battlefield.

    Args:
        sector_terrain: Campaign sector terrain type (e.g. "plains", "forest").
            Controls terrain distribution and thematic zone names.

    Difficult ground zones are always generated (~20% of non-open zones).
    """
    config = SECTOR_TERRAIN_CONFIG.get(sector_terrain or "", None)
    if config:
        weights = config["weights"]
        name_map = config["names"]
    else:
        weights = _DEFAULT_WEIGHTS
        name_map = None

    # Scale weights up (x10) and apply ±10% random jitter per mission
    # Impassable types are excluded from jitter — their % is fixed
    scaled = []
    for t, w in weights:
        base = w * 10
        if is_impassable(t):
            scaled.append((t, base))
        else:
            jitter = random.randint(-base // 10, base // 10) if base >= 10 else random.randint(-1, 1)
            scaled.append((t, max(1, base + jitter)))

    # Build weighted pool from scaled weights
    terrain_pool = [t for t, w in scaled for _ in range(w)]

    zones = []
    for r in range(rows):
        row = []
        for c in range(cols):
            terrain = random.choice(terrain_pool)
            # Split IMPASSABLE into blocking (70%) / non-blocking (30%)
            if terrain == TerrainType.IMPASSABLE:
                if random.random() < 0.7:
                    terrain = TerrainType.IMPASSABLE_BLOCKING
            row.append(Zone(row=r, col=c, terrain=terrain))
        zones.append(row)

    # Always apply difficult ground to ~20% of non-impassable zones
    eligible = [
        z for row in zones for z in row
        if not is_impassable(z.terrain)
    ]
    if eligible:
        count = max(1, len(eligible) // 5)
        for z in random.sample(eligible, min(count, len(eligible))):
            z.difficult = True

    # Assign thematic terrain names
    if name_map:
        for row in zones:
            for z in row:
                key = (z.terrain, z.difficult)
                z.terrain_name = name_map.get(key, "")
    else:
        # Generic names when no sector config
        _generic = {
            TerrainType.OPEN: "Open Ground",
            TerrainType.LIGHT_COVER: "Scatter",
            TerrainType.HEAVY_COVER: "Cover",
            TerrainType.HIGH_GROUND: "High Ground",
            TerrainType.IMPASSABLE: "Impassable",
            TerrainType.IMPASSABLE_BLOCKING: "Impassable Wall",
        }
        for row in zones:
            for z in row:
                z.terrain_name = _generic.get(z.terrain, "")

    return zones

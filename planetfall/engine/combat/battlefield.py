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

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TerrainType(str, Enum):
    OPEN = "open"
    LIGHT_COVER = "light_cover"      # Scatter terrain, low walls
    HEAVY_COVER = "heavy_cover"      # Forest, ruins, barricades
    HIGH_GROUND = "high_ground"      # Hills, elevated positions
    IMPASSABLE = "impassable"        # Cannot enter


class FigureStatus(str, Enum):
    ACTIVE = "active"
    STUNNED = "stunned"
    SPRAWLING = "sprawling"
    CASUALTY = "casualty"


class FigureSide(str, Enum):
    PLAYER = "player"
    ENEMY = "enemy"


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
    has_objective: bool = False
    objective_label: str = ""
    notes: str = ""


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


@dataclass
class Battlefield:
    """Variable-size zone-based battlefield (4" per zone)."""
    zones: list[list[Zone]] = field(default_factory=list)
    figures: list[Figure] = field(default_factory=list)
    round_number: int = 0
    battle_log: list[str] = field(default_factory=list)
    rows: int = 6
    cols: int = 6

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
                    if self.zones[nr][nc].terrain != TerrainType.IMPASSABLE:
                        adj.append((nr, nc))
        return adj

    def jump_destinations(self, row: int, col: int, max_dist: int) -> list[tuple[int, int]]:
        """Get zones reachable by jump jets (straight-line, ignores impassable).

        Jump jets move in a straight line (8 directions) up to max_dist zones.
        Can cross AND land on impassable zones (scouts can jump on/off things).
        """
        destinations = []
        directions = [(-1, -1), (-1, 0), (-1, 1), (0, -1),
                      (0, 1), (1, -1), (1, 0), (1, 1)]
        for dr, dc in directions:
            for dist in range(1, max_dist + 1):
                nr, nc = row + dr * dist, col + dc * dist
                if not (0 <= nr < self.rows and 0 <= nc < self.cols):
                    break  # off grid, stop this direction
                if (nr, nc) not in destinations:
                    destinations.append((nr, nc))
        return destinations

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

    def has_scatter(self, shooter_zone: tuple[int, int], target_zone: tuple[int, int]) -> bool:
        """Check if LoS crosses light cover (scatter terrain).

        Per rules p.36: scatter doesn't grant cover; instead a hit roll
        that exactly matches the to-hit number means the scatter absorbed
        the hit (remove scatter, shot has no effect).
        """
        between = self.get_zones_between(shooter_zone, target_zone)
        for r, c in between:
            if self.get_zone(r, c).terrain == TerrainType.LIGHT_COVER:
                return True
        # Also check target zone itself
        target = self.get_zone(*target_zone)
        return target.terrain == TerrainType.LIGHT_COVER

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

    def check_los(
        self, z1: tuple[int, int], z2: tuple[int, int],
    ) -> str:
        """Check line of sight between two zones.

        Returns:
            "clear"    — no intervening cover or blocking terrain
            "obscured" — light/heavy cover in the path (partial LoS)
            "blocked"  — impassable terrain blocks the line entirely
        """
        if z1 == z2:
            return "clear"

        between = self.get_zones_between(z1, z2)

        has_cover = False
        for pos in between:
            r, c = pos
            if not (0 <= r < self.rows and 0 <= c < self.cols):
                continue
            terrain = self.zones[r][c].terrain
            if terrain == TerrainType.IMPASSABLE:
                return "blocked"
            if terrain in (TerrainType.HEAVY_COVER, TerrainType.LIGHT_COVER):
                has_cover = True

        # Target zone's own cover also obscures LoS
        t_r, t_c = z2
        if 0 <= t_r < self.rows and 0 <= t_c < self.cols:
            target_terrain = self.zones[t_r][t_c].terrain
            if target_terrain in (TerrainType.HEAVY_COVER, TerrainType.LIGHT_COVER):
                has_cover = True

        return "obscured" if has_cover else "clear"

    def detect_contacts_auto(self) -> list[Figure]:
        """Detect contacts that are automatically revealed (no roll needed).

        Auto-detect conditions:
        - Same zone: always detected
        - 1-2 zones: detected unless LoS blocked
        - 3-4 zones: detected if clear LoS
        """
        detected = []
        player_figs = self.get_player_figures()
        for fig in self.figures:
            if not fig.is_contact or not fig.is_alive:
                continue
            for pf in player_figs:
                dist = self.zone_distance(fig.zone, pf.zone)
                if dist == 0:
                    # Same zone — always detected
                    detected.append(fig)
                    break
                los = self.check_los(pf.zone, fig.zone)
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

    def detect_contacts_obscured(self) -> list[Figure]:
        """Detect non-auto contacts via D6 4+ roll.

        Triggers for:
        - Obscured LoS within FAR_RANGE (4 zones): D6 4+
        - Clear LoS at EXTREME_RANGE (5-6 zones): D6 4+
        Called during Enemy Phase.
        """
        from planetfall.engine.dice import roll_d6
        detected = []
        player_figs = self.get_player_figures()
        already_auto = {id(f) for f in self.detect_contacts_auto()}
        for fig in self.figures:
            if not fig.is_contact or not fig.is_alive:
                continue
            if id(fig) in already_auto:
                continue  # already auto-detected, skip
            for pf in player_figs:
                dist = self.zone_distance(fig.zone, pf.zone)
                los = self.check_los(pf.zone, fig.zone)
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

    def reveal_contact(self, contact: Figure) -> list[str]:
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
            edge_zones = self._get_edge_zones()
            for i in range(2):
                if edge_zones:
                    spawn_zone = rng.choice(edge_zones)
                    new_fig = Figure(
                        name=f"Contact-{len(self.figures) + 1}",
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
                    self.figures.append(new_fig)
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
        adj = self.adjacent_zones(*contact.zone)
        cover_adj = [z for z in adj if self.has_cover(z)]
        spawn_zone = rng.choice(cover_adj) if cover_adj else (rng.choice(adj) if adj else contact.zone)
        extra = Figure(
            name=f"Lifeform {len(self.figures) + 1}",
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
        self.figures.append(extra)
        log.append(f"  Additional hostile appears at zone {spawn_zone}!")
        return log

    def _get_edge_zones(self) -> list[tuple[int, int]]:
        """Get all non-impassable edge zones."""
        edges = []
        for c in range(self.cols):
            if self.zones[0][c].terrain != TerrainType.IMPASSABLE:
                edges.append((0, c))
            if self.zones[self.rows - 1][c].terrain != TerrainType.IMPASSABLE:
                edges.append((self.rows - 1, c))
        for r in range(1, self.rows - 1):
            if self.zones[r][0].terrain != TerrainType.IMPASSABLE:
                edges.append((r, 0))
            if self.zones[r][self.cols - 1].terrain != TerrainType.IMPASSABLE:
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


def generate_random_terrain(
    rows: int = 6, cols: int = 6,
) -> list[list[Zone]]:
    """Generate randomized terrain for a battlefield.

    Terrain distribution follows tabletop norms:
    - ~40% open, ~25% light cover, ~25% heavy cover, ~10% high ground
    - Player and enemy edge rows are always open (deployment zones)
    """
    terrain_options = [
        TerrainType.OPEN,
        TerrainType.OPEN,
        TerrainType.LIGHT_COVER,
        TerrainType.HEAVY_COVER,
        TerrainType.HIGH_GROUND,
    ]

    zones = []
    for r in range(rows):
        row = []
        for c in range(cols):
            # Keep edge rows open for deployment
            if r == 0 or r == rows - 1:
                terrain = TerrainType.OPEN
            else:
                terrain = random.choice(terrain_options)
            row.append(Zone(row=r, col=c, terrain=terrain))
        zones.append(row)
    return zones

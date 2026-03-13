"""Mission setup and victory conditions for Planetfall combat.

Each mission type defines:
- Enemy type (tactical or lifeform)
- Number and placement of enemies
- Deployment zones
- Victory conditions
- Special rules
"""

from __future__ import annotations

from dataclasses import dataclass, field

from planetfall.engine.combat.battlefield import (
    Battlefield, Figure, FigureSide, FigureStatus, Zone, TerrainType,
    generate_random_terrain, GRID_SMALL, GRID_STANDARD,
)
from planetfall.engine.combat.enemy_ai import AIAction
from planetfall.engine.dice import roll_d6, roll_2d6_pick_lowest
from planetfall.engine.models import GameState, MissionType
from planetfall.engine.tables.tactical_enemy_gen import (
    generate_tactical_enemy_group, GeneratedEnemy, ENEMY_WEAPONS,
)
from planetfall.engine.tables.lifeform_gen import (
    generate_lifeform, generate_callsign, LifeformProfile,
)
from planetfall.engine.models import LifeformEntry

import random as _rng

MAX_PER_ZONE = 2  # max enemies per zone during deployment

# D100 ranges for the 10-slot lifeform encounter table
_LIFEFORM_D100_RANGES = [
    (1, 18), (19, 32), (33, 44), (45, 54), (55, 64),
    (65, 73), (74, 82), (83, 89), (90, 95), (96, 100),
]


@dataclass
class LifeformRollResult:
    """Result of rolling on the Lifeform Encounters table."""
    profile: LifeformProfile
    name: str
    d100_roll: int
    slot_idx: int
    is_new: bool  # True if a new lifeform was generated


def get_or_generate_lifeform(state: GameState) -> LifeformRollResult:
    """Roll D100 on the Campaign Lifeform Encounters table.

    If the slot is filled, reuse that lifeform profile.
    If blank, generate a new lifeform, name it, and store it.

    Returns a LifeformRollResult with the profile, name, roll details.
    """
    from planetfall.engine.dice import roll_d100

    d100 = roll_d100("Lifeform encounter table").total

    # Find which slot this roll maps to
    slot_idx = 0
    for i, (low, high) in enumerate(_LIFEFORM_D100_RANGES):
        if low <= d100 <= high:
            slot_idx = i
            break

    # Extend lifeform_table to have enough entries
    while len(state.enemies.lifeform_table) <= slot_idx:
        state.enemies.lifeform_table.append(LifeformEntry(
            d100_low=_LIFEFORM_D100_RANGES[len(state.enemies.lifeform_table)][0],
            d100_high=_LIFEFORM_D100_RANGES[len(state.enemies.lifeform_table)][1],
        ))

    entry = state.enemies.lifeform_table[slot_idx]

    if entry.name:
        # Slot is filled — reuse existing lifeform
        special_attack = ""
        unique_ability = ""
        for rule in entry.special_rules:
            if rule in ("razor_claws", "eruption", "shoot", "spit", "overpower", "ferocity"):
                special_attack = rule
            elif rule in ("pull", "jump", "teleport", "paralyze", "terror",
                          "confuse", "hinder", "knock_down"):
                unique_ability = rule
        profile = LifeformProfile(
            speed=entry.mobility,
            partially_airborne=entry.partially_airborne,
            combat_skill=entry.combat_skill,
            strike_damage=entry.strike_damage,
            toughness=entry.toughness,
            armor_save=entry.armor_save,
            kill_points=entry.kill_points,
            dodge=entry.dodge,
            special_attack=special_attack,
            special_attack_details={},
            unique_ability=unique_ability,
            unique_ability_details={},
        )
        return LifeformRollResult(
            profile=profile, name=entry.name,
            d100_roll=d100, slot_idx=slot_idx, is_new=False,
        )

    # Slot is blank — generate new lifeform and store
    profile = generate_lifeform()
    callsign = generate_callsign(profile)

    # Build weapon descriptions
    weapons = []
    if profile.strike_damage:
        weapons.append(f"Claws/Fangs (Melee D+{profile.strike_damage})")
    if profile.special_attack:
        weapons.append(f"{profile.special_attack.replace('_', ' ').title()}")

    special_rules_list = []
    if profile.partially_airborne:
        special_rules_list.append("partially_airborne")
    if profile.dodge:
        special_rules_list.append("dodge")
    if profile.unique_ability:
        special_rules_list.append(profile.unique_ability)

    entry.name = callsign
    entry.mobility = profile.speed
    entry.combat_skill = profile.combat_skill
    entry.toughness = profile.toughness
    entry.strike_damage = profile.strike_damage
    entry.armor_save = profile.armor_save
    entry.kill_points = profile.kill_points
    entry.partially_airborne = profile.partially_airborne
    entry.dodge = profile.dodge
    entry.weapons = weapons
    entry.special_rules = special_rules_list
    entry.bio_analysis_level = 0

    return LifeformRollResult(
        profile=profile, name=callsign,
        d100_roll=d100, slot_idx=slot_idx, is_new=True,
    )


def _assign_zone_with_overflow(
    target_zone: tuple[int, int],
    zone_counts: dict[tuple[int, int], int],
    grid_rows: int,
    grid_cols: int,
    max_per_zone: int = MAX_PER_ZONE,
) -> tuple[int, int]:
    """Assign a figure to a zone, overflowing to adjacent if full."""
    if zone_counts.get(target_zone, 0) < max_per_zone:
        zone_counts[target_zone] = zone_counts.get(target_zone, 0) + 1
        return target_zone
    # Find adjacent zones with capacity
    r, c = target_zone
    adjacent = []
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            nr, nc = r + dr, c + dc
            if 0 <= nr < grid_rows and 0 <= nc < grid_cols:
                if zone_counts.get((nr, nc), 0) < max_per_zone:
                    adjacent.append((nr, nc))
    if adjacent:
        chosen = _rng.choice(adjacent)
        zone_counts[chosen] = zone_counts.get(chosen, 0) + 1
        return chosen
    # All adjacent full — just stack (shouldn't happen normally)
    zone_counts[target_zone] = zone_counts.get(target_zone, 0) + 1
    return target_zone


@dataclass
class MissionSetup:
    """Configuration for a mission before combat begins."""
    mission_type: MissionType
    battlefield: Battlefield
    max_rounds: int = 6
    victory_conditions: list[str] = field(default_factory=list)
    defeat_conditions: list[str] = field(default_factory=list)
    special_rules: list[str] = field(default_factory=list)
    objectives: list[dict] = field(default_factory=list)
    enemy_type: str = ""  # "tactical" or "lifeform"
    log: list[str] = field(default_factory=list)
    enemy_info: list[str] = field(default_factory=list)  # human-readable enemy generation results


def _create_player_figure(
    name: str,
    char_class: str,
    speed: int,
    combat_skill: int,
    toughness: int,
    reactions: int,
    savvy: int,
    weapon_name: str = "",
    weapon_range: int = 18,
    weapon_shots: int = 1,
    weapon_damage: int = 0,
    weapon_traits: list[str] | None = None,
    armor_save: int = 0,
    is_leader: bool = False,
    zone: tuple[int, int] = (2, 1),
) -> Figure:
    """Create a player Figure from character data."""
    return Figure(
        name=name,
        side=FigureSide.PLAYER,
        zone=zone,
        speed=speed,
        combat_skill=combat_skill,
        toughness=toughness,
        reactions=reactions,
        savvy=savvy,
        weapon_name=weapon_name,
        weapon_range=weapon_range,
        weapon_shots=weapon_shots,
        weapon_damage=weapon_damage,
        weapon_traits=weapon_traits or [],
        armor_save=armor_save,
        char_class=char_class,
        is_leader=is_leader,
    )


def _create_enemy_figure(
    enemy: GeneratedEnemy,
    zone: tuple[int, int] = (0, 1),
) -> Figure:
    """Create an enemy Figure from a generated enemy."""
    return Figure(
        name=enemy.name,
        side=FigureSide.ENEMY,
        zone=zone,
        speed=enemy.speed,
        combat_skill=enemy.combat_skill,
        toughness=enemy.toughness,
        weapon_name=enemy.weapon.name,
        weapon_range=enemy.weapon.range_inches,
        weapon_shots=enemy.weapon.shots,
        weapon_damage=enemy.weapon.damage_bonus,
        weapon_traits=list(enemy.weapon.traits),
        melee_damage=enemy.weapon.damage_bonus if "melee" in enemy.weapon.traits else 0,
        armor_save=enemy.armor_save,
        kill_points=enemy.kill_points,
        is_leader=enemy.role == "leader",
        is_specialist=enemy.role == "specialist",
        panic_range=enemy.panic_range,
        special_rules=list(enemy.special_rules),
        char_class=enemy.role,
    )


def _build_lifeform_info(profile: LifeformProfile, name: str, deployment_desc: str) -> list[str]:
    """Build human-readable enemy info lines for a lifeform profile."""
    info = [f"{name} — {deployment_desc}"]
    info.append(
        f"  Speed {profile.speed}\""
        + (" (partially airborne)" if profile.partially_airborne else "")
    )
    info.append(f"  Combat Skill +{profile.combat_skill}  Toughness {profile.toughness}")
    info.append(f"  Strike Damage +{profile.strike_damage}")
    if profile.armor_save:
        info.append(f"  Armor Save {profile.armor_save}+")
    if profile.kill_points and profile.kill_points > 1:
        info.append(f"  Kill Points {profile.kill_points}")
    if profile.special_attack:
        info.append(f"  Special: {profile.special_attack.replace('_', ' ').title()}")
    if profile.unique_ability:
        info.append(f"  Ability: {profile.unique_ability.replace('_', ' ').title()}")
    return info


def _create_lifeform_figure(
    profile: LifeformProfile,
    index: int,
    zone: tuple[int, int] = (0, 1),
) -> Figure:
    """Create a lifeform Figure from a generated profile."""
    traits = []
    if profile.special_attack == "shoot":
        traits.append("chain_on_6")

    # Pack leader: 6th lifeform in a mission gets +2 KP
    kp = profile.kill_points
    is_pack_leader = index == 6
    if is_pack_leader:
        kp += 2

    return Figure(
        name=f"Lifeform {index}" + (" (Pack Leader)" if is_pack_leader else ""),
        side=FigureSide.ENEMY,
        zone=zone,
        speed=profile.speed,
        combat_skill=profile.combat_skill,
        toughness=profile.toughness,
        melee_damage=profile.strike_damage,
        armor_save=profile.armor_save,
        kill_points=kp,
        panic_range=0,  # Lifeforms are fearless
        weapon_name="Natural weapons",
        weapon_range=0,
        weapon_shots=0,
        weapon_damage=profile.strike_damage,
        weapon_traits=traits,
        special_rules=[profile.special_attack, profile.unique_ability],
        char_class="lifeform",
    )


def _deploy_player_figures(
    state: GameState,
    deployed_names: list[str],
    grunt_count: int = 0,
    grid_rows: int = 6,
    grid_cols: int = 6,
    bot_deploy: bool = False,
    weapon_loadout: dict[str, str] | None = None,
) -> list[Figure]:
    """Convert deployed characters, grunts, and bot to battlefield Figures."""
    from planetfall.engine.models import get_weapon_by_name, can_use_weapon

    figures = []
    loadout = weapon_loadout or {}

    # Player edge = last row, spread across columns
    player_row = grid_rows - 1
    player_zones = [(player_row, c) for c in range(grid_cols)]

    for i, name in enumerate(deployed_names):
        char = next((c for c in state.characters if c.name == name), None)
        if not char:
            continue

        zone = player_zones[i % len(player_zones)]

        # Determine armor save from class
        armor = 0
        if char.char_class.value == "trooper":
            armor = 5
        elif char.char_class.value == "bot":
            armor = 6

        # Get weapon from loadout selection, fall back to first usable or Colony Rifle
        weapon_name = "Colony Rifle"
        weapon_range = 18
        weapon_shots = 1
        weapon_damage = 0
        weapon_traits: list[str] = []

        selected = loadout.get(name)
        if selected:
            wpn = get_weapon_by_name(selected)
            if wpn and can_use_weapon(char.char_class.value, wpn):
                weapon_name = wpn.name
                weapon_range = wpn.range_inches
                weapon_shots = wpn.shots
                weapon_damage = wpn.damage_bonus
                weapon_traits = list(wpn.traits)
            else:
                selected = None  # Invalid selection, fall through

        if not selected:
            # Legacy fallback: use first usable weapon from equipment
            for eq in char.equipment:
                wpn = get_weapon_by_name(eq)
                if wpn and can_use_weapon(char.char_class.value, wpn):
                    weapon_name = wpn.name
                    weapon_range = wpn.range_inches
                    weapon_shots = wpn.shots
                    weapon_damage = wpn.damage_bonus
                    weapon_traits = list(wpn.traits)
                    break

        # Check for calibration hit bonus from step 17
        hit_bonus = 0
        if "[CALIBRATION: +1 hit bonus next mission]" in (char.notes or ""):
            hit_bonus = 1
            char.notes = char.notes.replace(
                "[CALIBRATION: +1 hit bonus next mission]", ""
            ).strip()

        fig = _create_player_figure(
            name=char.name,
            char_class=char.char_class.value,
            speed=char.speed,
            combat_skill=char.combat_skill,
            toughness=char.toughness,
            reactions=char.reactions,
            savvy=char.savvy,
            weapon_name=weapon_name,
            weapon_range=weapon_range,
            weapon_shots=weapon_shots,
            weapon_damage=weapon_damage,
            weapon_traits=weapon_traits,
            armor_save=armor,
            zone=zone,
        )
        fig.hit_bonus = hit_bonus
        figures.append(fig)

    # Add grunts (one may have LMG if fireteam 3+ and player chose it)
    has_lmg = loadout.get("grunt_lmg") == "1"
    for i in range(grunt_count):
        zone = player_zones[(len(figures) + i) % len(player_zones)]
        if i == 0 and has_lmg:
            # First grunt gets LMG
            fig = Figure(
                name="Grunt 1 (LMG)",
                side=FigureSide.PLAYER,
                zone=zone,
                speed=4,
                combat_skill=0,
                toughness=3,
                reactions=2,
                weapon_name="Light Machine Gun",
                weapon_range=36,
                weapon_shots=3,
                weapon_damage=0,
                weapon_traits=["grunt", "cumbersome", "hail_of_fire"],
                char_class="grunt",
            )
        else:
            fig = Figure(
                name=f"Grunt {i+1}",
                side=FigureSide.PLAYER,
                zone=zone,
                speed=4,
                combat_skill=0,
                toughness=3,
                reactions=2,
                weapon_name="Infantry Rifle",
                weapon_range=24,
                weapon_shots=1,
                weapon_damage=0,
                char_class="grunt",
            )
        figures.append(fig)

    # Add bot
    if bot_deploy:
        zone = player_zones[len(figures) % len(player_zones)]
        bot_weapon = "Colony Rifle"
        bot_range = 18
        bot_shots = 1
        bot_damage = 0
        bot_traits: list[str] = []
        bot_selected = loadout.get("Colony Bot")
        if bot_selected:
            wpn = get_weapon_by_name(bot_selected)
            if wpn and can_use_weapon("bot", wpn):
                bot_weapon = wpn.name
                bot_range = wpn.range_inches
                bot_shots = wpn.shots
                bot_damage = wpn.damage_bonus
                bot_traits = list(wpn.traits)
        fig = Figure(
            name="Colony Bot",
            side=FigureSide.PLAYER,
            zone=zone,
            speed=4,
            combat_skill=0,
            toughness=4,
            reactions=2,
            weapon_name=bot_weapon,
            weapon_range=bot_range,
            weapon_shots=bot_shots,
            weapon_damage=bot_damage,
            weapon_traits=bot_traits,
            armor_save=6,
            char_class="bot",
        )
        figures.append(fig)

    return figures


def _deploy_tactical_enemies(
    enemy_type_id: str | None = None,
    extra_enemies: int = 0,
    grid_rows: int = 6,
    grid_cols: int = 6,
) -> tuple[list[Figure], list[str]]:
    """Generate and deploy tactical enemies.

    Returns (figures, info_lines) where info_lines describe the generated group.
    """
    enemies = generate_tactical_enemy_group(enemy_type_id)

    # Remove enemies if extra_enemies is negative (e.g. Pitched Battle Force A)
    if extra_enemies < 0 and enemies:
        remove_count = min(abs(extra_enemies), max(0, len(enemies) - 2))  # keep at least 2
        # Remove from the end (regular enemies first)
        for _ in range(remove_count):
            enemies.pop()

    # Add extra enemies if needed
    if extra_enemies > 0 and enemies:
        profile_enemy = enemies[-1]  # Use regular enemy template
        for i in range(extra_enemies):
            from planetfall.engine.tables.tactical_enemy_gen import GeneratedEnemy, roll_grunt_weapon, ENEMY_WEAPONS
            weapon_id, has_blade = roll_grunt_weapon()
            weapon = ENEMY_WEAPONS[weapon_id]
            extra = GeneratedEnemy(
                name=f"Extra Enemy {i+1}",
                enemy_type=profile_enemy.enemy_type,
                role="regular",
                speed=profile_enemy.speed,
                combat_skill=profile_enemy.combat_skill,
                toughness=profile_enemy.toughness,
                panic_range=profile_enemy.panic_range,
                armor_save=profile_enemy.armor_save,
                kill_points=0,
                weapon_id=weapon_id,
                weapon=weapon,
                has_blade=has_blade,
                special_rules=list(profile_enemy.special_rules),
            )
            enemies.append(extra)

    # Build human-readable group description
    info = []
    if enemies:
        e0 = enemies[0]
        info.append(f"Enemy: {e0.enemy_type.replace('_', ' ').title()} — {len(enemies)} hostiles")
        info.append(f"  Speed {e0.speed}\"  Toughness {e0.toughness}  Panic {e0.panic_range}")
        if e0.armor_save:
            info.append(f"  Armor Save {e0.armor_save}+")
        if e0.special_rules:
            info.append(f"  Rules: {', '.join(e0.special_rules)}")
        for enemy in enemies:
            weapon_desc = f"{enemy.weapon.name} (R{enemy.weapon.range_inches}\" S{enemy.weapon.shots} D+{enemy.weapon.damage_bonus})"
            role_tag = f" [{enemy.role}]" if enemy.role != "regular" else ""
            info.append(f"  {enemy.name}{role_tag}: {weapon_desc}")

    # Deploy as contacts dispersed across enemy half of the grid
    # Enemy half = rows 0 to mid_row-1
    mid_row = grid_rows // 2
    contact_zones = [
        (r, c) for r in range(mid_row) for c in range(grid_cols)
    ]
    # Spread evenly by stepping through zones, max 2 per zone
    step = max(1, len(contact_zones) // max(1, len(enemies)))
    zone_counts: dict[tuple[int, int], int] = {}
    figures = []
    for i, enemy in enumerate(enemies):
        zone_idx = (i * step) % len(contact_zones)
        target = contact_zones[zone_idx]
        zone = _assign_zone_with_overflow(target, zone_counts, grid_rows, grid_cols, max_per_zone=1)
        fig = _create_enemy_figure(enemy, zone)
        fig.is_contact = True
        figures.append(fig)

    return figures, info


def _deploy_slyn(
    grid_rows: int = 9,
    grid_cols: int = 9,
    battlefield: Battlefield | None = None,
) -> tuple[list[Figure], list[str]]:
    """Deploy Slyn encounter.

    Slyn stats: Speed 5", CS +1, Toughness 4, Beam focus 18" S1 D1,
    Claws (melee D1). Operate in pairs. 1D6: 1-4 = 6 Slyn (3 pairs),
    5-6 = 8 Slyn (4 pairs). Deploy in pairs in terrain near center.
    Not subject to stun or panic.
    """
    import random as rng

    # Determine encounter size
    size_roll = roll_d6("Slyn encounter size")
    if size_roll.total <= 4:
        slyn_count = 6
        pair_count = 3
    else:
        slyn_count = 8
        pair_count = 4

    info = [
        f"Slyn Encounter — {slyn_count} Slyn ({pair_count} pairs)",
        "  Speed 5\"  Combat Skill +1  Toughness 4",
        "  Beam Focus (R18\" S1 D+1)  Claws (Melee D+1)",
        "  Cannot be Stunned. Not subject to Panic.",
        "  Pairs linked — both must fall to destroy a pair.",
    ]

    # Find terrain features for deployment (near center, one pair per feature)
    center_r, center_c = grid_rows // 2, grid_cols // 2
    terrain_zones = []
    if battlefield:
        for r in range(grid_rows):
            for c in range(grid_cols):
                z = battlefield.get_zone(r, c)
                if z.terrain not in (TerrainType.OPEN, TerrainType.IMPASSABLE):
                    dist = abs(r - center_r) + abs(c - center_c)
                    terrain_zones.append((dist, r, c))
        terrain_zones.sort(key=lambda x: x[0])

    if not terrain_zones:
        # Fallback: spread across top half
        terrain_zones = [(0, r, c) for r in range(grid_rows // 2)
                         for c in range(grid_cols)]
        rng.shuffle(terrain_zones)

    figures = []
    for pair_idx in range(pair_count):
        # Each pair deploys in the same zone (within 1" of each other)
        if pair_idx < len(terrain_zones):
            _, r, c = terrain_zones[pair_idx]
        else:
            _, r, c = terrain_zones[pair_idx % len(terrain_zones)]
        zone = (r, c)

        for member in range(2):
            fig_num = pair_idx * 2 + member + 1
            fig = Figure(
                name=f"Slyn {fig_num} (P{pair_idx+1})",
                side=FigureSide.ENEMY,
                zone=zone,
                speed=5,
                combat_skill=1,
                toughness=4,
                reactions=0,
                weapon_name="Beam Focus",
                weapon_range=18,
                weapon_shots=1,
                weapon_damage=1,
                weapon_traits=["burning"],
                melee_damage=1,
                char_class="slyn",
                is_contact=False,
                special_rules=[f"pair_{pair_idx+1}", "no_stun", "no_panic"],
            )
            figures.append(fig)

    return figures, info


def _create_sleeper_figure(index: int, zone: tuple[int, int]) -> Figure:
    """Create a single Sleeper robot figure.

    Sleepers: Speed 5", CS +1, Toughness 4, 6+ save (force screen).
    Weapon: D6 roll — 1-5 Beam weapon (12" S1 D1), 6 Heavy beam (18" S2 D1).
    Cannot be stunned. Fearless (no panic).
    """
    weapon_roll = roll_d6(f"Sleeper {index} weapon")
    if weapon_roll.total >= 6:
        weapon_name = "Heavy Beam"
        weapon_range = 18
        weapon_shots = 2
    else:
        weapon_name = "Beam Weapon"
        weapon_range = 12
        weapon_shots = 1

    return Figure(
        name=f"Sleeper {index}",
        side=FigureSide.ENEMY,
        zone=zone,
        speed=5,
        combat_skill=1,
        toughness=4,
        reactions=0,
        weapon_name=weapon_name,
        weapon_range=weapon_range,
        weapon_shots=weapon_shots,
        weapon_damage=1,
        armor_save=6,  # Force screen — works against all fire including burning
        char_class="sleeper",
        is_contact=False,
        special_rules=["no_stun", "no_panic", "force_screen"],
    )


def _deploy_lifeforms(
    count: int = 0,
    grid_rows: int = 6,
    grid_cols: int = 6,
    state: GameState | None = None,
) -> tuple[list[Figure], list[str]]:
    """Generate and deploy lifeforms as contacts across enemy half.

    Returns (figures, info_lines) where info_lines describe the generated profile.
    """
    if state:
        result = get_or_generate_lifeform(state)
        profile = result.profile
        lifeform_name = result.name
    else:
        profile = generate_lifeform()
        lifeform_name = generate_callsign(profile)
    if count == 0:
        count = roll_d6("Lifeform count").total + 3

    # Build human-readable profile description
    info = [f"{lifeform_name} — {count} contacts deployed"]
    info.append(
        f"  Speed {profile.speed}\""
        + (" (partially airborne)" if profile.partially_airborne else "")
    )
    info.append(f"  Combat Skill +{profile.combat_skill}  Toughness {profile.toughness}")
    info.append(f"  Strike Damage +{profile.strike_damage}")
    if profile.armor_save:
        info.append(f"  Armor Save {profile.armor_save}+")
    if profile.kill_points:
        info.append(f"  Kill Points {profile.kill_points}")
    if profile.dodge:
        info.append("  Dodge: evades hit on natural 6")
    if profile.special_attack:
        desc = profile.special_attack_details.get("description", profile.special_attack)
        info.append(f"  Special Attack: {profile.special_attack.replace('_', ' ').title()} — {desc}")
    if profile.unique_ability:
        desc = profile.unique_ability_details.get("description", profile.unique_ability)
        info.append(f"  Unique Ability: {profile.unique_ability.replace('_', ' ').title()} — {desc}")

    # Deploy across enemy half as contacts, max 2 per zone
    mid_row = grid_rows // 2
    contact_zones = [
        (r, c) for r in range(mid_row) for c in range(grid_cols)
    ]
    step = max(1, len(contact_zones) // max(1, count))
    zone_counts: dict[tuple[int, int], int] = {}
    figures = []
    for i in range(count):
        zone_idx = (i * step) % len(contact_zones)
        target = contact_zones[zone_idx]
        zone = _assign_zone_with_overflow(target, zone_counts, grid_rows, grid_cols, max_per_zone=1)
        fig = _create_lifeform_figure(profile, i + 1, zone)
        fig.is_contact = True
        figures.append(fig)

    return figures, info


def setup_mission(
    state: GameState,
    mission_type: MissionType,
    deployed_names: list[str],
    grunt_count: int = 0,
    enemy_type_id: str | None = None,
    bot_deploy: bool = False,
    civilian_deploy: int = 0,
    scout_at_risk: str | None = None,
    weapon_loadout: dict[str, str] | None = None,
) -> MissionSetup:
    """Set up a mission battlefield with all figures deployed.

    Returns a MissionSetup ready for the combat loop.
    """
    # Determine grid size based on mission type
    # Small missions (2'x2' = 6x6): scouting, science, rescue, scout_down
    # Standard missions (3'x3' = 9x9): investigation, patrol, skirmish, exploration, hunt, pitched_battle, assault, strike, delve
    SMALL_MISSIONS = {
        MissionType.SCOUTING, MissionType.SCIENCE,
        MissionType.RESCUE, MissionType.SCOUT_DOWN,
    }
    if mission_type in SMALL_MISSIONS:
        grid_rows, grid_cols = GRID_SMALL
    else:
        grid_rows, grid_cols = GRID_STANDARD

    terrain = generate_random_terrain(grid_rows, grid_cols)
    battlefield = Battlefield(zones=terrain, rows=grid_rows, cols=grid_cols)

    # Deploy player figures
    player_figs = _deploy_player_figures(
        state, deployed_names, grunt_count, grid_rows, grid_cols, bot_deploy,
        weapon_loadout=weapon_loadout,
    )
    battlefield.figures.extend(player_figs)

    # Deploy civilians (basic stats, player side)
    for i in range(civilian_deploy):
        civ = Figure(
            name=f"Civilian {i + 1}",
            side=FigureSide.PLAYER,
            zone=(grid_rows - 1, grid_cols // 2),
            speed=4,
            combat_skill=0,
            toughness=3,
            weapon_name="Unarmed",
            weapon_range=0,
            weapon_shots=0,
            char_class="civilian",
        )
        battlefield.figures.append(civ)

    setup = MissionSetup(
        mission_type=mission_type,
        battlefield=battlefield,
    )

    # Helper: scale objective placement to grid size
    mid_row = grid_rows // 2
    mid_col = grid_cols // 2

    # Mission-specific setup
    if mission_type == MissionType.INVESTIGATION:
        setup.max_rounds = 99  # no round limit — ends when squad leaves
        setup.enemy_type = "lifeform"

        # 1 Contact at center of each non-deployment edge (3 contacts)
        # Player deploys from last row, so contacts on top/left/right edges
        lf_result = get_or_generate_lifeform(state)
        profile = lf_result.profile
        contact_edges = [
            (0, mid_col),                    # top edge center
            (mid_row, 0),                    # left edge center
            (mid_row, grid_cols - 1),        # right edge center
        ]
        for i, zone in enumerate(contact_edges):
            fig = _create_lifeform_figure(profile, i + 1, zone)
            fig.is_contact = True
            battlefield.figures.append(fig)

        setup.enemy_info = _build_lifeform_info(
            profile, lf_result.name, "3 contacts deployed (1 per non-deploy edge)",
        )

        # 4 Discovery markers in center of each table quarter
        q_row = grid_rows // 4
        q_col = grid_cols // 4
        three_q_row = grid_rows * 3 // 4
        three_q_col = grid_cols * 3 // 4
        setup.objectives = [
            {"type": "discovery", "zone": (q_row, q_col)},
            {"type": "discovery", "zone": (q_row, three_q_col)},
            {"type": "discovery", "zone": (three_q_row, q_col)},
            {"type": "discovery", "zone": (three_q_row, three_q_col)},
        ]
        setup.victory_conditions = [
            "Investigate 4 Discovery markers and evacuate off any edge",
        ]
        setup.special_rules = [
            "Deploy up to 4 figures (any combination of characters/bots/grunts/civilians)",
            "No Slyn; no Battle Conditions",
            "Investigate: move within zone of marker, roll D6 for result",
            "Each Enemy Phase: D6 per non-deploy edge (1-3 = new Contact)",
            "Mission ends when squad leaves the table",
        ]
        setup.log.append("Investigation: 3 contacts, 4 discovery markers")

    elif mission_type == MissionType.SCOUTING:
        setup.max_rounds = 99  # no round limit — ends when squad leaves
        setup.enemy_type = "lifeform"

        # 1 contact at center of map
        center_row = grid_rows // 2
        center_col = grid_cols // 2
        lf_result = get_or_generate_lifeform(state)
        profile = lf_result.profile
        contact_fig = _create_lifeform_figure(profile, 1, (center_row, center_col))
        contact_fig.is_contact = True
        battlefield.figures.append(contact_fig)

        setup.enemy_info = _build_lifeform_info(
            profile, lf_result.name, "1 contact deployed (center)",
        )

        # Place 6 Recon markers in the largest terrain features
        # Find non-open, non-impassable zones sorted by "size" (prefer heavy cover)
        terrain_candidates = []
        for r in range(grid_rows):
            for c in range(grid_cols):
                z = battlefield.get_zone(r, c)
                if z.terrain in (TerrainType.HEAVY_COVER, TerrainType.LIGHT_COVER, TerrainType.HIGH_GROUND):
                    # Weight: heavy > high > light
                    weight = 3 if z.terrain == TerrainType.HEAVY_COVER else (2 if z.terrain == TerrainType.HIGH_GROUND else 1)
                    terrain_candidates.append((weight, r, c))
        terrain_candidates.sort(key=lambda x: -x[0])  # largest first
        recon_count = min(6, len(terrain_candidates))
        for i in range(recon_count):
            _, r, c = terrain_candidates[i]
            setup.objectives.append({"type": "recon", "zone": (r, c)})

        setup.victory_conditions = [
            f"Investigate {recon_count} Recon markers and evacuate off any edge",
        ]
        setup.special_rules = [
            "Deploy up to 2 figures (any combination)",
            "Scouts auto-recon on contact; others need D6+Savvy 5+",
            "No Slyn attack; no Battle Conditions",
            "Each Enemy Phase: D6, on 6 new Contact at random edge center",
            "Equal Aggression/Random: contact stays in place (no new spawn)",
            "Mission ends when squad leaves the table",
        ]
        setup.log.append(f"Scouting: 1 contact, {recon_count} recon markers")

    elif mission_type == MissionType.EXPLORATION:
        setup.max_rounds = 99  # no round limit — ends when squad leaves

        # Find sector resource/hazard from turn log
        resource_level = 3  # fallback
        hazard_level = 2    # fallback
        for ev in reversed(state.turn_log):
            if ev.state_changes.get("mission_type") == "exploration":
                sid = ev.state_changes.get("sector_id")
                if sid is not None:
                    for s in state.campaign_map.sectors:
                        if s.sector_id == sid:
                            resource_level = s.resource_level
                            hazard_level = s.hazard_level
                            break
                break

        # Opposition: 2D6, on 2-4 = Slyn, else lifeforms (contacts)
        from planetfall.engine.dice import roll_nd6 as _roll_nd6
        opp_roll = _roll_nd6(2, "Exploration opposition")
        slyn_attack = opp_roll.total <= 4

        if slyn_attack:
            setup.enemy_type = "slyn"
            slyn_figs, slyn_info = _deploy_slyn(
                grid_rows=grid_rows, grid_cols=grid_cols,
                battlefield=battlefield,
            )
            battlefield.figures.extend(slyn_figs)
            setup.enemy_info = slyn_info
            setup.special_rules.append(
                "Slyn operate in pairs — both must be killed to destroy a pair"
            )
            setup.special_rules.append(
                "Slyn teleport: start of Enemy Phase, random pair moves 2D6\" random direction"
            )
            setup.special_rules.append(
                "Slyn withdraw when only 1 pair remains at end of round"
            )
            setup.log.append(
                f"Exploration: Slyn attack! {len(slyn_figs)} Slyn ({len(slyn_figs)//2} pairs)"
            )
        else:
            # Lifeform contacts equal to Hazard Level, placed near center terrain
            setup.enemy_type = "lifeform"
            contact_count = max(1, hazard_level)
            lf_result = get_or_generate_lifeform(state)
            profile = lf_result.profile

            # Find terrain features nearest to center for contact placement
            center_r, center_c = grid_rows // 2, grid_cols // 2
            terrain_near_center = []
            for r in range(grid_rows):
                for c in range(grid_cols):
                    z = battlefield.get_zone(r, c)
                    if z.terrain not in (TerrainType.OPEN, TerrainType.IMPASSABLE):
                        dist = abs(r - center_r) + abs(c - center_c)
                        terrain_near_center.append((dist, r, c))
            terrain_near_center.sort(key=lambda x: x[0])

            enemy_info = _build_lifeform_info(
                profile, lf_result.name,
                f"{contact_count} contacts deployed (Hazard Level {hazard_level})",
            )

            zone_counts: dict[tuple[int, int], int] = {}
            for i in range(contact_count):
                if terrain_near_center:
                    _, r, c = terrain_near_center[i % len(terrain_near_center)]
                else:
                    r, c = center_r, center_c
                zone = _assign_zone_with_overflow((r, c), zone_counts, grid_rows, grid_cols, max_per_zone=1)
                fig = _create_lifeform_figure(profile, i + 1, zone)
                fig.is_contact = True
                battlefield.figures.append(fig)

            setup.enemy_info = enemy_info
            setup.log.append(
                f"Exploration: {contact_count} lifeform contacts "
                f"(Hazard Level {hazard_level})"
            )

        # Objectives equal to Resource Level, distributed evenly
        obj_count = max(1, resource_level)
        for i in range(obj_count):
            row = (i * (grid_rows - 2)) // max(1, obj_count - 1) + 1 if obj_count > 1 else mid_row
            col = (i * (grid_cols - 1)) // max(1, obj_count) + 1
            row = min(row, grid_rows - 2)
            col = min(col, grid_cols - 1)
            setup.objectives.append({"type": "resource", "zone": (row, col)})

        setup.victory_conditions = [
            f"Sweep {obj_count} objective markers (Resource Level {resource_level})",
            "End round in zone with no enemies closer to secure",
        ]
        setup.special_rules = [
            f"Sector Resource Level: {resource_level}  Hazard Level: {hazard_level}",
            "Sweep objective: end round in zone, no enemies closer",
            "One objective secured per side per round",
            "Mission ends when squad leaves the table",
        ]
        if slyn_attack:
            setup.special_rules.append(
                "Slyn: one pair moves toward nearest objective each Enemy Phase"
            )

    elif mission_type == MissionType.SCIENCE:
        setup.max_rounds = 99  # no round limit — ends when squad leaves
        setup.enemy_type = "lifeform"

        # 1 contact at center of map
        center_row = grid_rows // 2
        center_col = grid_cols // 2
        lf_result = get_or_generate_lifeform(state)
        profile = lf_result.profile
        contact_fig = _create_lifeform_figure(profile, 1, (center_row, center_col))
        contact_fig.is_contact = True
        battlefield.figures.append(contact_fig)

        setup.enemy_info = _build_lifeform_info(
            profile, lf_result.name, "1 contact deployed (center)",
        )

        # Place 6 Science markers in largest terrain features
        terrain_candidates = []
        for r in range(grid_rows):
            for c in range(grid_cols):
                z = battlefield.get_zone(r, c)
                if z.terrain in (TerrainType.HEAVY_COVER, TerrainType.LIGHT_COVER, TerrainType.HIGH_GROUND):
                    weight = 3 if z.terrain == TerrainType.HEAVY_COVER else (2 if z.terrain == TerrainType.HIGH_GROUND else 1)
                    terrain_candidates.append((weight, r, c))
        terrain_candidates.sort(key=lambda x: -x[0])
        science_count = min(6, len(terrain_candidates))
        for i in range(science_count):
            _, r, c = terrain_candidates[i]
            setup.objectives.append({"type": "science", "zone": (r, c)})

        # Determine hazard level for contact spawning
        hazard_level = 2  # fallback
        for ev in reversed(state.turn_log):
            if ev.state_changes.get("mission_type") == "science":
                sid = ev.state_changes.get("sector_id")
                if sid is not None:
                    for s in state.campaign_map.sectors:
                        if s.sector_id == sid:
                            hazard_level = s.hazard_level
                            break
                break

        setup.victory_conditions = [
            f"Collect samples from {science_count} Science markers and evacuate",
        ]
        setup.special_rules = [
            "Deploy up to 2 figures (any combination)",
            "Scientists auto-collect on contact; others need D6+Savvy 5+",
            "Failed collection: sample is ruined",
            "No Slyn; no Battle Conditions",
            f"Each Enemy Phase: D6 (2D6 if Hazard {hazard_level}+4) on 6 new Contact at random edge",
            "Equal Aggression/Random: contact stays in place (no new spawn)",
            "Mission ends when squad leaves the table",
        ]
        setup.log.append(f"Science: 1 contact, {science_count} science markers")

    elif mission_type == MissionType.HUNT:
        setup.max_rounds = 99  # no round limit — ends when squad leaves
        setup.enemy_type = "lifeform"  # unless Slyn

        # Opposition: 2D6, on 2-4 = Slyn; otherwise hunt lifeforms
        from planetfall.engine.dice import roll_nd6 as _hunt_roll
        opp_roll = _hunt_roll(2, "Hunt opposition")
        slyn_attack = opp_roll.total <= 4

        if slyn_attack:
            setup.enemy_type = "slyn"
            slyn_figs, slyn_info = _deploy_slyn(
                grid_rows=grid_rows, grid_cols=grid_cols,
                battlefield=battlefield,
            )
            battlefield.figures.extend(slyn_figs)
            setup.enemy_info = slyn_info
            setup.victory_conditions = [
                "Fight off the Slyn and evacuate",
            ]
            setup.special_rules.append(
                "Slyn operate in pairs — both must be killed to destroy a pair"
            )
            setup.log.append(
                f"Hunt: Slyn attack! {len(slyn_figs)} Slyn ({len(slyn_figs)//2} pairs) — no specimens"
            )
        else:
            # Contacts placed in terrain features with LoS to player, D6 per feature
            # At least 3 contacts guaranteed
            lf_result = get_or_generate_lifeform(state)
            profile = lf_result.profile
            terrain_features = []
            for r in range(grid_rows):
                for c in range(grid_cols):
                    z = battlefield.get_zone(r, c)
                    if z.terrain not in (TerrainType.OPEN, TerrainType.IMPASSABLE):
                        terrain_features.append((r, c))

            # Roll D6 per terrain feature; 6 = contact
            contact_zones = []
            for r, c in terrain_features:
                spot_roll = roll_d6(f"Spot terrain ({r},{c})")
                if spot_roll.total == 6:
                    contact_zones.append((r, c))

            # Minimum 3 contacts
            remaining_features = [z for z in terrain_features if z not in contact_zones]
            import random as _rng
            _rng.shuffle(remaining_features)
            while len(contact_zones) < 3 and remaining_features:
                contact_zones.append(remaining_features.pop())

            contact_count = len(contact_zones)
            setup.enemy_info = _build_lifeform_info(
                profile, lf_result.name, f"{contact_count} contacts deployed",
            )

            for i, (r, c) in enumerate(contact_zones):
                fig = _create_lifeform_figure(profile, i + 1, (r, c))
                fig.is_contact = True
                battlefield.figures.append(fig)

            setup.victory_conditions = [
                "Kill 2 lifeforms, collect specimens (action in base contact), evacuate",
            ]
            setup.log.append(f"Hunt: {contact_count} lifeform contacts in terrain")

        setup.special_rules = [
            "Deploy up to 6 figures (any combination)",
            "Kill 2 lifeforms, then action in base contact to collect specimen",
            "Collected specimens auto-transmitted to colony",
            "Mission ends when squad leaves the table",
        ]
        if slyn_attack:
            setup.special_rules = [
                "Slyn attack! No specimens can be collected",
                "Fight off the Slyn and evacuate",
                "Mission ends when squad leaves the table",
            ]

    elif mission_type == MissionType.PATROL:
        setup.max_rounds = 99  # no round limit — ends when squad leaves

        # Opposition: 2D6, on 2-4 = Slyn; on 5-6 = animals (contacts)
        from planetfall.engine.dice import roll_nd6 as _patrol_roll
        opp_roll = _patrol_roll(2, "Patrol opposition")
        slyn_attack = opp_roll.total <= 4

        if slyn_attack:
            setup.enemy_type = "slyn"
            slyn_figs, slyn_info = _deploy_slyn(
                grid_rows=grid_rows, grid_cols=grid_cols,
                battlefield=battlefield,
            )
            battlefield.figures.extend(slyn_figs)
            setup.enemy_info = slyn_info
            setup.special_rules.append(
                "Slyn operate in pairs — both must be killed to destroy a pair"
            )
            setup.log.append(
                f"Patrol: Slyn attack! {len(slyn_figs)} Slyn ({len(slyn_figs)//2} pairs)"
            )
        else:
            # Animals — no contacts initially, spawn at end of each round
            setup.enemy_type = "lifeform"
            setup.enemy_info = ["Wildlife patrol — contacts spawn each round"]
            setup.log.append("Patrol: wildlife — contacts appear each round")

        # 3 objectives at terrain features nearest center
        center_r, center_c = grid_rows // 2, grid_cols // 2
        terrain_near_center = []
        for r in range(grid_rows):
            for c in range(grid_cols):
                z = battlefield.get_zone(r, c)
                if z.terrain not in (TerrainType.OPEN, TerrainType.IMPASSABLE):
                    dist = abs(r - center_r) + abs(c - center_c)
                    terrain_near_center.append((dist, r, c))
        terrain_near_center.sort(key=lambda x: x[0])
        obj_count = min(3, len(terrain_near_center))
        for i in range(obj_count):
            _, r, c = terrain_near_center[i]
            setup.objectives.append({"type": "secure", "zone": (r, c)})
        # Fallback if not enough terrain
        while len(setup.objectives) < 3:
            setup.objectives.append({"type": "secure", "zone": (mid_row, len(setup.objectives))})

        setup.victory_conditions = [
            "Clear all 3 objectives (figure within zone, no enemies within zone)",
        ]
        setup.special_rules = [
            "Deploy 2 characters + 1 fireteam of up to 4 grunts (6 total)",
            "Objectives cleared when figure in zone with no enemies in zone",
            "Can clear multiple objectives in same round",
            "Slyn/animals ignore objectives",
            "Mission ends when squad leaves the table",
        ]
        if not slyn_attack:
            setup.special_rules.append(
                "End of each round: 1 Contact at random edge (not player entry edge)"
            )

    elif mission_type == MissionType.SKIRMISH:
        setup.max_rounds = 99  # no round limit — ends when squad leaves
        setup.enemy_type = "tactical"
        enemy_figs, enemy_info = _deploy_tactical_enemies(
            enemy_type_id, grid_rows=grid_rows, grid_cols=grid_cols,
        )
        # Deploy enemies in terrain near enemy edge
        terrain_zones = [
            (r, c) for r in range(min(3, grid_rows // 3))
            for c in range(grid_cols)
            if battlefield.get_zone(r, c).terrain
            not in (TerrainType.OPEN, TerrainType.IMPASSABLE)
        ]
        if not terrain_zones:
            terrain_zones = [(0, c) for c in range(grid_cols)]
        for i, fig in enumerate(enemy_figs):
            zone = terrain_zones[i % len(terrain_zones)]
            fig.zone = zone
            fig.is_contact = False  # enemies are known
        battlefield.figures.extend(enemy_figs)
        setup.enemy_info = enemy_info

        # 2 objectives from Skirmish Objective table (D6 each)
        # Place randomly near center (D6+1" from center ≈ 1-2 zones)
        import random as _sk_rng
        obj_types = ["secure", "sweep", "destroy", "search", "deliver", "retrieve"]
        for _ in range(2):
            obj_type_roll = roll_d6("Skirmish objective type")
            obj_type = obj_types[obj_type_roll.total - 1]
            # Place ~1-2 zones from center
            offset_r = _sk_rng.randint(-1, 1)
            offset_c = _sk_rng.randint(-1, 1)
            obj_r = max(1, min(grid_rows - 2, mid_row + offset_r))
            obj_c = max(1, min(grid_cols - 2, mid_col + offset_c))
            setup.objectives.append({"type": obj_type, "zone": (obj_r, obj_c)})

        setup.victory_conditions = [
            "Complete both skirmish objectives and evacuate",
        ]
        setup.special_rules = [
            "Deploy 4 characters + 1 fireteam of 4 grunts (8 total)",
            "No Slyn interference",
            "Enemies ignore objectives — focus on killing squad",
            "End of each round: D6 (+1D6 per completed objective), 6 = reinforcement at random edge",
            "Two 6s = regular + specialist; Three 6s = regular + specialist + leader",
            "Mission ends when squad leaves the table",
        ]
        setup.log.append(f"Skirmish: {len(enemy_figs)} tactical enemies, 2 objectives")

    elif mission_type == MissionType.RESCUE:
        setup.max_rounds = 99  # no round limit — ends when all leave/casualty
        setup.enemy_type = "lifeform"
        # Rescue uses lifeforms (animals), 2 contacts at center of each edge
        edge_zones = [
            (0, mid_col), (0, max(0, mid_col - 1)),                    # top edge
            (grid_rows - 1, mid_col), (grid_rows - 1, max(0, mid_col - 1)),  # bottom edge
            (mid_row, 0), (max(0, mid_row - 1), 0),                    # left edge
            (mid_row, grid_cols - 1), (max(0, mid_row - 1), grid_cols - 1),  # right edge
        ]
        result = get_or_generate_lifeform(state)
        profile = result.profile
        info = _build_lifeform_info(profile, result.name, "8 contacts deployed (2 per edge)")

        for i, zone in enumerate(edge_zones):
            fig = _create_lifeform_figure(profile, i + 1, zone)
            fig.is_contact = True
            battlefield.figures.append(fig)
        setup.enemy_info = info

        # 3 colonist NPCs at center
        for i in range(3):
            col = max(0, mid_col - 1 + i) if mid_col > 0 else i
            col = min(col, grid_cols - 1)
            colonist = Figure(
                name=f"Colonist {i + 1}",
                side=FigureSide.PLAYER,
                zone=(mid_row, col),
                speed=4, combat_skill=0, toughness=3,
                melee_damage=0, armor_save=0, kill_points=0,
                panic_range=0,
                weapon_name="Unarmed", weapon_range=0,
                weapon_shots=0, weapon_damage=0,
                char_class="colonist",
            )
            battlefield.figures.append(colonist)

        # Player deploys near center (within 3" ≈ center zone)
        for fig in player_figs:
            fig.zone = (mid_row, mid_col)

        setup.victory_conditions = [
            "Save colonists by escorting them off any edge",
            "Colonist is saved if within 3\" of squad member at exit",
        ]
        setup.defeat_conditions = [
            "Lose 1 Colony Morale per colonist not saved",
        ]
        setup.special_rules = [
            "3 colonists at center (civvy stats, unarmed, act as squad)",
            "End of each round: roll D6 per edge, on 6 new Contact appears",
            "Colonist exiting alone: D6, 5-6 = saved, else killed",
            "Squad casualties do not affect Colony Morale",
        ]
        setup.log.append(f"Rescue: 8 lifeform contacts, 3 colonists to save")

    elif mission_type == MissionType.SCOUT_DOWN:
        setup.max_rounds = 99  # no round limit — ends when all leave/casualty
        setup.enemy_type = "tactical"

        # Determine scout name and profile
        scout_label = scout_at_risk or "Downed Scout"
        # Check if scout is on roster for profile
        roster_char = None
        if scout_at_risk:
            roster_char = next(
                (c for c in state.characters if c.name == scout_at_risk), None,
            )

        # Place scout at center of map
        center_row = grid_rows // 2
        center_col = grid_cols // 2
        if roster_char:
            # Use roster scout's actual profile
            from planetfall.engine.models import get_weapon_by_name
            weapon_name = "Scout Pistol"
            weapon_range = 8
            weapon_shots = 1
            weapon_damage = 0
            weapon_traits: list[str] = []
            for eq in roster_char.equipment:
                wpn = get_weapon_by_name(eq)
                if wpn:
                    weapon_name = wpn.name
                    weapon_range = wpn.range_inches
                    weapon_shots = wpn.shots
                    weapon_damage = wpn.damage_bonus
                    weapon_traits = list(wpn.traits)
                    break
            scout_fig = Figure(
                name=scout_label,
                side=FigureSide.PLAYER,
                zone=(center_row, center_col),
                speed=roster_char.speed,
                combat_skill=roster_char.combat_skill,
                toughness=roster_char.toughness,
                reactions=roster_char.reactions,
                savvy=roster_char.savvy,
                weapon_name=weapon_name,
                weapon_range=weapon_range,
                weapon_shots=weapon_shots,
                weapon_damage=weapon_damage,
                weapon_traits=weapon_traits,
                char_class="scout",
            )
        else:
            # Unknown scout: base profile + scout pistol
            scout_fig = Figure(
                name=scout_label,
                side=FigureSide.PLAYER,
                zone=(center_row, center_col),
                speed=4,
                combat_skill=0,
                toughness=3,
                reactions=1,
                weapon_name="Scout Pistol",
                weapon_range=8,
                weapon_shots=1,
                weapon_damage=0,
                char_class="scout",
            )
        # Mark scout as injured (move OR act, not both) and undetected
        scout_fig.special_rules = ["injured_scout", "undetected"]
        battlefield.figures.append(scout_fig)

        # Opposition: 2D6, on 2-3 Slyn attack; otherwise tactical enemies
        from planetfall.engine.dice import roll_nd6
        opp_roll = roll_nd6(2, "Scout Down opposition")
        slyn_attack = opp_roll.total <= 3

        if slyn_attack:
            setup.enemy_type = "slyn"
            slyn_figs, slyn_info = _deploy_slyn(
                grid_rows=grid_rows, grid_cols=grid_cols,
                battlefield=battlefield,
            )
            battlefield.figures.extend(slyn_figs)
            setup.enemy_info = slyn_info
            setup.special_rules.append(
                "Slyn operate in pairs — both must be killed to destroy a pair"
            )
            setup.log.append(
                f"Scout Down: Slyn attack! {len(slyn_figs)} Slyn ({len(slyn_figs)//2} pairs)"
            )
        else:
            enemy_figs, enemy_info = _deploy_tactical_enemies(
                enemy_type_id, grid_rows=grid_rows, grid_cols=grid_cols,
            )
            # Divide into 3 groups along enemy edge (row 0)
            group_size = max(1, len(enemy_figs) // 3)
            col_step = max(1, grid_cols // 3)
            for i, fig in enumerate(enemy_figs):
                group_idx = min(i // group_size, 2)  # 0, 1, or 2
                col = group_idx * col_step + (col_step // 2)
                col = min(col, grid_cols - 1)
                fig.zone = (0, col)
                fig.is_contact = False  # enemies are known
            battlefield.figures.extend(enemy_figs)
            setup.enemy_info = enemy_info
            setup.log.append(
                f"Scout Down: {len(enemy_figs)} tactical enemies in 3 groups"
            )

        setup.victory_conditions = [
            f"Rescue {scout_label} off any battlefield edge",
        ]
        setup.defeat_conditions = [
            f"{scout_label} is killed",
        ]
        setup.special_rules = [
            f"{scout_label} is injured: can move OR act each round, not both",
            f"{scout_label} begins undetected — enemy ignores until detected",
            "Scout detected if: fires weapon, spotted out of cover, or moves >1 zone",
            "End of each round: D6, on 6 enemy reinforcement at enemy edge center",
            "Squad casualties do not affect Colony Morale",
        ]

    elif mission_type == MissionType.PITCHED_BATTLE:
        setup.max_rounds = 99  # no round limit — ends when all enemies killed/panicked
        setup.enemy_type = "tactical"

        # Two enemy forces, each generated separately
        # First force: reduce count by 1; Second force: increase by 1
        enemy_figs, enemy_info = _deploy_tactical_enemies(
            enemy_type_id, extra_enemies=-1, grid_rows=grid_rows, grid_cols=grid_cols,
        )
        enemy_figs2, enemy_info2 = _deploy_tactical_enemies(
            enemy_type_id, extra_enemies=1, grid_rows=grid_rows, grid_cols=grid_cols,
        )

        # Rename second group for clarity
        for i, fig in enumerate(enemy_figs2):
            fig.name = f"Force B {i+1}"

        # Both forces arrive from enemy edge in round 1, at 3 markers
        # Force A at first marker (round 1), Force B at second (round 2)
        # For setup, place Force A at enemy edge; Force B off-map (arrives round 2)
        col_step = max(1, grid_cols // 3)
        marker_cols = [col_step // 2, col_step + col_step // 2, 2 * col_step + col_step // 2]
        import random as _pb_rng
        _pb_rng.shuffle(marker_cols)

        # Force A enters round 1 at first marker
        for fig in enemy_figs:
            fig.zone = (0, min(marker_cols[0], grid_cols - 1))
            fig.is_contact = False
        # Force B enters round 2 — place at second marker initially
        for fig in enemy_figs2:
            fig.zone = (0, min(marker_cols[1], grid_cols - 1))
            fig.is_contact = False

        battlefield.figures.extend(enemy_figs)
        battlefield.figures.extend(enemy_figs2)
        setup.enemy_info = enemy_info + [""] + ["Force B:"] + enemy_info2

        setup.victory_conditions = [
            "Kill or drive off every enemy",
        ]
        setup.defeat_conditions = [
            "Squad wiped out — roll on Campaign Consequences table",
        ]
        setup.special_rules = [
            "Deploy up to 4 characters + up to 8 grunts in 2 fireteams (12 total)",
            "No Slyn, no Battle Conditions",
            "Force A arrives enemy edge round 1; Force B arrives round 2",
            "Mission ends when all enemies killed or panicked, or squad eliminated",
        ]
        setup.log.append(
            f"Pitched Battle: {len(enemy_figs) + len(enemy_figs2)} total enemies (2 forces)"
        )

    elif mission_type == MissionType.STRIKE:
        setup.max_rounds = 99  # no round limit
        setup.enemy_type = "tactical"
        enemy_figs, enemy_info = _deploy_tactical_enemies(
            enemy_type_id, extra_enemies=2, grid_rows=grid_rows, grid_cols=grid_cols,
        )

        # Boss/Leader at center, 1/3 within 1 zone of center, rest in pairs spread out
        center_r, center_c = grid_rows // 2, grid_cols // 2
        leader_fig = next((f for f in enemy_figs if f.is_leader), None)
        if leader_fig:
            leader_fig.zone = (center_r, center_c)

        # Split remaining: 1/3 near center, rest spread out
        non_leaders = [f for f in enemy_figs if not f.is_leader]
        third = max(1, len(non_leaders) // 3)
        for i, fig in enumerate(non_leaders):
            if i < third:
                # Near center (within 1 zone)
                import random as _st_rng
                fig.zone = (
                    max(0, min(grid_rows - 1, center_r + _st_rng.randint(-1, 1))),
                    max(0, min(grid_cols - 1, center_c + _st_rng.randint(-1, 1))),
                )
            else:
                # Spread out from center (2-3 zones away)
                import random as _st_rng2
                dist = _st_rng2.randint(2, 3)
                angle_r = _st_rng2.choice([-1, 0, 1])
                angle_c = _st_rng2.choice([-1, 0, 1])
                fig.zone = (
                    max(0, min(grid_rows - 1, center_r + angle_r * dist)),
                    max(0, min(grid_cols - 1, center_c + angle_c * dist)),
                )
            fig.is_contact = False
        battlefield.figures.extend(enemy_figs)
        setup.enemy_info = enemy_info

        setup.victory_conditions = [
            "Defeat the Boss/Leader and secure their data, then evacuate",
        ]
        setup.special_rules = [
            "Deploy up to 6 characters + 4 grunts in 1 fireteam (10 total)",
            "No Slyn interference",
            "Undetected: squad members that only move (no actions) are undetected",
            "Enemy fights defensively — stays in cover, fires when in range",
            "Enemy ignores undetected squad members",
            "If Boss/Leader killed: nearest enemy moves to collect data and escape",
            "Mission ends when squad leaves or all enemies defeated",
        ]
        setup.log.append(f"Strike: {len(enemy_figs)} enemies (Boss/Leader at center)")

    elif mission_type == MissionType.ASSAULT:
        setup.max_rounds = 99  # no round limit
        setup.enemy_type = "tactical"

        # Max enemy strength + 2 regulars + 2 specialists + 1 leader
        enemy_figs, enemy_info = _deploy_tactical_enemies(
            enemy_type_id, extra_enemies=5, grid_rows=grid_rows, grid_cols=grid_cols,
        )

        # Deploy evenly throughout central 12x12" area (≈ center 3x3 zones)
        center_r, center_c = grid_rows // 2, grid_cols // 2
        import random as _as_rng
        center_zones = [
            (r, c)
            for r in range(max(0, center_r - 1), min(grid_rows, center_r + 2))
            for c in range(max(0, center_c - 1), min(grid_cols, center_c + 2))
        ]
        for i, fig in enumerate(enemy_figs):
            fig.zone = center_zones[i % len(center_zones)]
            fig.is_contact = False  # known defenders
        battlefield.figures.extend(enemy_figs)
        setup.enemy_info = enemy_info

        setup.victory_conditions = [
            "Kill or drive off every enemy to destroy the Strongpoint",
        ]
        setup.defeat_conditions = [
            "Retreat/defeat: enemy restored to full strength, expands to adjacent sector",
        ]
        setup.special_rules = [
            "Deploy up to 6 characters + 8 grunts in 2 fireteams (14 total)",
            "No Slyn, no Battle Conditions",
            "All enemy Panic ranges reduced by 1 (defending home turf)",
            "Round 1: enemies not ready unless they had LoS to a firing/exposed crew",
            "Round 2+: all enemies ready and fight normally",
            "Enemy fights defensively — stays in cover and fires",
            "End of each round: D6, on 6 random enemy gains +1 KP",
        ]
        setup.log.append(f"Assault: {len(enemy_figs)} enemies (max strength, defensive)")

    elif mission_type == MissionType.DELVE:
        setup.max_rounds = 99  # no round limit — ends when squad leaves
        setup.enemy_type = "delve_hazard"

        # No initial enemies — Delve Hazards spawn in round 1 enemy phase
        # 4 Delve Hazard markers placed in round 1, revealed when crew within range
        setup.enemy_info = [
            "Delve Hazards — no initial enemies",
            "  4 Hazard markers placed in round 1 (1 per table quarter)",
            "  Revealed when crew within 1 zone + LoS",
            "  Result: 1-2 Sleeper, 3-4 Trap, 5-6 Environmental hazard",
        ]

        # 4 Delve Device markers, 1 in center of each table quarter
        q_row = grid_rows // 4
        q_col = grid_cols // 4
        three_q_row = grid_rows * 3 // 4
        three_q_col = grid_cols * 3 // 4
        setup.objectives = [
            {"type": "hazard", "zone": (q_row, q_col)},
            {"type": "hazard", "zone": (q_row, three_q_col)},
            {"type": "hazard", "zone": (three_q_row, q_col)},
            {"type": "hazard", "zone": (three_q_row, three_q_col)},
        ]

        setup.victory_conditions = [
            "Activate 3 of 4 Delve Devices to reveal Artifact location",
            "Collect Artifact and evacuate via entrance or discovered exit",
        ]
        setup.defeat_conditions = [
            "Squad eliminated before retrieving Artifact",
        ]
        setup.special_rules = [
            "Deploy up to 6 figures (characters only, no grunts)",
            "No Battle Conditions or Uncertain Features",
            "Round 1: 4 Delve Hazard markers placed (1 per quarter)",
            "Hazards move 3\" random direction each Enemy Phase (round 2+)",
            "Hazard revealed within 1 zone + LoS: D6 (1-2 Sleeper, 3-4 Trap, 5-6 Environmental)",
            "Maintain 4 hazards: if <4, one spawns at center each Enemy Phase",
            "Activate Delve Device: action in base contact, roll D6 for activation type",
            "After 3 activations: Artifact placed randomly near center",
            "Exit via entrance point or discovered exit (end of round 1)",
        ]
        setup.log.append("Delve: 4 Delve Devices, hazard-based opposition")

    else:
        # Default: generic skirmish
        setup.enemy_type = "tactical"
        enemy_figs, enemy_info = _deploy_tactical_enemies(enemy_type_id, grid_rows=grid_rows, grid_cols=grid_cols)
        battlefield.figures.extend(enemy_figs)
        setup.enemy_info = enemy_info
        setup.victory_conditions = ["Defeat all enemies"]

    # Place objectives on battlefield zones so they show on the map
    for obj in setup.objectives:
        r, c = obj["zone"]
        zone = battlefield.get_zone(r, c)
        zone.has_objective = True
        obj_type = obj.get("type", "obj")
        label_map = {
            "resource": "RES", "discovery": "DIS", "secure": "SEC",
            "hazard": "HAZ", "sample": "SMP", "recon": "REC",
            "science": "SCI", "sweep": "SWP", "destroy": "DEM",
            "search": "SRC", "deliver": "DLV", "retrieve": "RET",
        }
        zone.objective_label = label_map.get(obj_type, "OBJ")

    return setup

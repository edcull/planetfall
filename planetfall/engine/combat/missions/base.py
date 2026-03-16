"""Shared types, constants, and helper functions for mission setup.

This module contains everything used across mission types:
- Data classes (MissionSetup, LifeformRollResult)
- Enemy profile tables and deployment helpers
- Figure creation helpers (player, enemy, lifeform, slyn, sleeper)
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
from planetfall.engine.utils import format_display
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
        weapons.append(f"{format_display(profile.special_attack)}")

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
    lifeform_template: dict | None = None  # stored profile for spawning contacts mid-battle
    condition: object = None  # BattlefieldCondition or None

    def to_dict(self) -> dict:
        cond_data = None
        if self.condition is not None:
            cond_data = (self.condition.model_dump()
                         if hasattr(self.condition, "model_dump")
                         else self.condition)
        return {
            "mission_type": self.mission_type.value,
            "max_rounds": self.max_rounds,
            "victory_conditions": list(self.victory_conditions),
            "defeat_conditions": list(self.defeat_conditions),
            "special_rules": list(self.special_rules),
            "objectives": list(self.objectives),
            "enemy_type": self.enemy_type,
            "log": list(self.log),
            "enemy_info": list(self.enemy_info),
            "battlefield": self.battlefield.to_dict(),
            "lifeform_template": self.lifeform_template,
            "condition": cond_data,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MissionSetup":
        from planetfall.engine.combat.battlefield import Battlefield
        bf = Battlefield.from_dict(d["battlefield"])
        setup = cls.__new__(cls)
        setup.mission_type = MissionType(d["mission_type"])
        setup.battlefield = bf
        setup.max_rounds = d.get("max_rounds", 6)
        setup.victory_conditions = d.get("victory_conditions", [])
        setup.defeat_conditions = d.get("defeat_conditions", [])
        setup.special_rules = d.get("special_rules", [])
        setup.objectives = d.get("objectives", [])
        setup.enemy_type = d.get("enemy_type", "")
        setup.log = d.get("log", [])
        setup.enemy_info = d.get("enemy_info", [])
        setup.lifeform_template = d.get("lifeform_template")
        # Restore condition
        cond_dict = d.get("condition")
        if cond_dict:
            from planetfall.engine.models import BattlefieldCondition
            setup.condition = BattlefieldCondition(**cond_dict)
        else:
            setup.condition = None
        return setup


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
        info.append(f"  Special: {format_display(profile.special_attack)}")
    if profile.unique_ability:
        info.append(f"  Ability: {format_display(profile.unique_ability)}")
    return info


def _create_lifeform_figure(
    profile: LifeformProfile,
    index: int,
    zone: tuple[int, int] = (0, 1),
    lifeform_name: str = "Lifeform",
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
        name=f"{lifeform_name} {index}" + (" (Pack Leader)" if is_pack_leader else ""),
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
    fireteams: list | None = None,
    grunt_upgrades: list[str] | None = None,
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
    # Build fireteam_id mapping: grunt index -> fireteam name
    ft_ids: list[str] = []
    if fireteams:
        for ft in fireteams:
            ft_name = getattr(ft, "name", str(ft)) if not isinstance(ft, str) else ft
            ft_size = getattr(ft, "size", 1) if not isinstance(ft, str) else 1
            ft_ids.extend([ft_name] * ft_size)

    has_lmg = loadout.get("grunt_lmg") == "1"
    upgrades = grunt_upgrades or []
    for i in range(grunt_count):
        zone = player_zones[(len(figures) + i) % len(player_zones)]
        ft_id = ft_ids[i] if i < len(ft_ids) else ""
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
                fireteam_id=ft_id,
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
                fireteam_id=ft_id,
            )
        # Apply grunt upgrades
        if "adapted_armor" in upgrades:
            fig.armor_save = 6  # 6+ Saving Throw
        if "survival_kit" in upgrades:
            fig.toughness += 1  # +1 Toughness
        if "side_arms" in upgrades:
            fig.special_rules.append("side_arms")
        if "sergeant_weaponry" in upgrades:
            fig.special_rules.append("sergeant_weaponry")
        if "sharpshooter_sight" in upgrades:
            fig.special_rules.append("sharpshooter_sight")
        if "ammo_packs" in upgrades:
            fig.special_rules.append("ammo_packs")
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
    enemy_size_mod: int = 0,
) -> tuple[list[Figure], list[str]]:
    """Generate and deploy tactical enemies.

    Returns (figures, info_lines) where info_lines describe the generated group.
    """
    enemies = generate_tactical_enemy_group(enemy_type_id)

    # Apply condition enemy size modifier
    extra_enemies += enemy_size_mod

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
        info.append(f"Enemy: {format_display(e0.enemy_type)} — {len(enemies)} hostiles")
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
                if z.terrain not in (TerrainType.OPEN, TerrainType.IMPASSABLE, TerrainType.IMPASSABLE_BLOCKING):
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
        info.append(f"  Special Attack: {format_display(profile.special_attack)} — {desc}")
    if profile.unique_ability:
        desc = profile.unique_ability_details.get("description", profile.unique_ability)
        info.append(f"  Unique Ability: {format_display(profile.unique_ability)} — {desc}")

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
        fig = _create_lifeform_figure(profile, i + 1, zone, lifeform_name=lifeform_name)
        fig.is_contact = True
        figures.append(fig)

    return figures, info

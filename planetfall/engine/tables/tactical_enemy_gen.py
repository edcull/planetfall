"""Tactical enemy generation tables for Planetfall.

D100 table for generating tactical enemy groups with full stat profiles,
weapons, and special rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from planetfall.engine.dice import (
    RandomTable, TableEntry, roll_d6, roll_nd6, roll_d100,
)


# --- Enemy weapon profiles ---

@dataclass
class EnemyWeapon:
    name: str
    range_inches: int = 0  # 0 = melee only
    shots: int = 1
    damage_bonus: int = 0
    traits: list[str] = field(default_factory=list)


ENEMY_WEAPONS = {
    "scrap_gun": EnemyWeapon("Scrap Gun", range_inches=7, shots=1, damage_bonus=0, traits=["pistol"]),
    "colony_rifle": EnemyWeapon("Colony Rifle", range_inches=18, shots=1, damage_bonus=0),
    "military_rifle": EnemyWeapon("Military Rifle", range_inches=24, shots=1, damage_bonus=0),
    "auto_rifle": EnemyWeapon("Auto Rifle", range_inches=24, shots=2, damage_bonus=0),
    "hunting_rifle": EnemyWeapon("Hunting Rifle", range_inches=30, shots=1, damage_bonus=1, traits=["heavy", "critical"]),
    "rattle_gun": EnemyWeapon("Rattle Gun", range_inches=24, shots=3, damage_bonus=0, traits=["heavy"]),
    "blade": EnemyWeapon("Blade", range_inches=0, shots=0, damage_bonus=1, traits=["melee"]),
    "hand_cannon": EnemyWeapon("Hand Cannon", range_inches=6, shots=1, damage_bonus=2, traits=["pistol"]),
    "ripper_sword": EnemyWeapon("Ripper Sword", range_inches=0, shots=0, damage_bonus=2, traits=["melee"]),
    "shatter_axe": EnemyWeapon("Shatter Axe", range_inches=0, shots=0, damage_bonus=3, traits=["melee", "clumsy", "shockwave"]),
    "shotgun": EnemyWeapon("Shotgun", range_inches=8, shots=1, damage_bonus=1, traits=["critical"]),
}


# --- Weapon generation tables ---

GRUNT_WEAPON_TABLE = {
    1: "scrap_gun",
    2: "colony_rifle",
    3: "colony_rifle",  # + blade (handled in generation)
    4: "military_rifle",
    5: "military_rifle",
    6: "military_rifle",
}

SPECIALIST_WEAPON_TABLE = {
    1: "auto_rifle",
    2: "auto_rifle",
    3: "hunting_rifle",
    4: "hunting_rifle",
    5: "rattle_gun",
    6: "rattle_gun",
}

LEADER_WEAPON_TABLE = {
    1: "shatter_axe",
    2: "hand_cannon",
    3: "hand_cannon",
    4: "ripper_sword",
    5: "ripper_sword",
    6: "shotgun",
}


def roll_grunt_weapon() -> tuple[str, bool]:
    """Roll for a grunt's weapon. Returns (weapon_id, has_blade)."""
    roll = roll_d6("Grunt weapon").total
    has_blade = (roll == 3)
    return GRUNT_WEAPON_TABLE[roll], has_blade


def roll_specialist_weapon() -> str:
    """Roll for a specialist's weapon."""
    roll = roll_d6("Specialist weapon").total
    return SPECIALIST_WEAPON_TABLE[roll]


def roll_leader_weapon() -> str:
    """Roll for a leader's extra weapon."""
    roll = roll_d6("Leader weapon").total
    return LEADER_WEAPON_TABLE[roll]


# --- Tactical enemy type profiles ---

@dataclass
class EnemyProfile:
    """Profile for a tactical enemy type."""
    name: str
    number_dice: str  # e.g. "2d3+3", "1d3+5"
    speed: int
    combat_skill: int
    combat_skill_elite: int  # for leaders/specialists
    toughness: int
    toughness_elite: int  # for leaders
    panic_range: int  # 0 = fearless
    armor_save: int  # 0 = none
    armor_save_elite: int  # for leaders/specialists with armor
    special_rules: list[str] = field(default_factory=list)
    kill_points_leader: int = 1
    kill_points_boss: int = 2


TACTICAL_ENEMY_PROFILES: dict[str, EnemyProfile] = {
    "outlaws": EnemyProfile(
        name="Outlaws", number_dice="2d3+3", speed=4,
        combat_skill=0, combat_skill_elite=0,
        toughness=3, toughness_elite=3,
        panic_range=2, armor_save=0, armor_save_elite=0,
        special_rules=["fragile_discipline"],
    ),
    "hostile_colonists": EnemyProfile(
        name="Hostile Colonists", number_dice="1d3+5", speed=4,
        combat_skill=0, combat_skill_elite=0,
        toughness=3, toughness_elite=3,
        panic_range=1, armor_save=0, armor_save_elite=0,
        special_rules=["variable_motivation"],
    ),
    "nomad_patrol": EnemyProfile(
        name="Nomad Patrol", number_dice="1d3+5", speed=6,
        combat_skill=0, combat_skill_elite=1,
        toughness=3, toughness_elite=4,
        panic_range=2, armor_save=0, armor_save_elite=0,
        special_rules=["keen_shots"],
    ),
    "remnant_colonists": EnemyProfile(
        name="Remnant Colonists", number_dice="1d6+3", speed=4,
        combat_skill=0, combat_skill_elite=0,
        toughness=3, toughness_elite=3,
        panic_range=3, armor_save=0, armor_save_elite=0,
        special_rules=["blood_crazed"],
    ),
    "renegades": EnemyProfile(
        name="Renegades", number_dice="1d3+5", speed=4,
        combat_skill=0, combat_skill_elite=0,
        toughness=3, toughness_elite=4,
        panic_range=2, armor_save=0, armor_save_elite=0,
        special_rules=["mob_rules"],
    ),
    "pirates_inexperienced": EnemyProfile(
        name="Pirates (Inexperienced)", number_dice="1d3+6", speed=4,
        combat_skill=0, combat_skill_elite=1,
        toughness=3, toughness_elite=3,
        panic_range=2, armor_save=0, armor_save_elite=0,
        special_rules=["lack_of_tactics"],
    ),
    "mysterious_raiders": EnemyProfile(
        name="Mysterious Raiders", number_dice="1d3+4", speed=5,
        combat_skill=1, combat_skill_elite=1,
        toughness=4, toughness_elite=4,
        panic_range=1, armor_save=0, armor_save_elite=0,
        special_rules=["intense_firepower"],
    ),
    "pirates_hardened": EnemyProfile(
        name="Pirates (Hardened)", number_dice="1d3+5", speed=5,
        combat_skill=1, combat_skill_elite=1,
        toughness=4, toughness_elite=4,
        panic_range=1, armor_save=0, armor_save_elite=6,
        special_rules=["vacc_suits"],
    ),
    "alien_raiders": EnemyProfile(
        name="Alien Raiders", number_dice="1d3+4", speed=4,
        combat_skill=0, combat_skill_elite=1,
        toughness=4, toughness_elite=4,
        panic_range=2, armor_save=0, armor_save_elite=0,
        special_rules=["slip_sideways"],
    ),
    "kerin_landing_party": EnemyProfile(
        name="K'Erin Landing Party", number_dice="1d3+4", speed=4,
        combat_skill=1, combat_skill_elite=1,
        toughness=4, toughness_elite=5,
        panic_range=1, armor_save=0, armor_save_elite=6,
        special_rules=["paramilitary"],
        kill_points_leader=2, kill_points_boss=3,
    ),
    "converted_recon_team": EnemyProfile(
        name="Converted Recon Team", number_dice="1d3+4", speed=4,
        combat_skill=1, combat_skill_elite=1,
        toughness=4, toughness_elite=4,
        panic_range=0, armor_save=6, armor_save_elite=6,
        special_rules=["fearless", "bolt_on_armor", "enhanced_models"],
    ),
}


# D100 lookup table
TACTICAL_ENEMY_TABLE = RandomTable(
    name="Tactical Enemy Type",
    dice_type="d100",
    entries=[
        TableEntry(1, 12, "outlaws", "Outlaws"),
        TableEntry(13, 22, "hostile_colonists", "Hostile Colonists"),
        TableEntry(23, 30, "nomad_patrol", "Nomad Patrol"),
        TableEntry(31, 39, "remnant_colonists", "Remnant Colonists"),
        TableEntry(40, 49, "renegades", "Renegades"),
        TableEntry(50, 61, "pirates_inexperienced", "Pirates (Inexperienced)"),
        TableEntry(62, 71, "mysterious_raiders", "Mysterious Raiders"),
        TableEntry(72, 78, "pirates_hardened", "Pirates (Hardened)"),
        TableEntry(79, 87, "alien_raiders", "Alien Raiders"),
        TableEntry(88, 95, "kerin_landing_party", "K'Erin Landing Party"),
        TableEntry(96, 100, "converted_recon_team", "Converted Recon Team"),
    ],
)


@dataclass
class GeneratedEnemy:
    """A fully generated enemy figure for the battlefield."""
    name: str
    enemy_type: str
    role: str  # "regular", "specialist", "leader", "boss"
    speed: int
    combat_skill: int
    toughness: int
    panic_range: int
    armor_save: int
    kill_points: int
    weapon_id: str
    weapon: EnemyWeapon
    has_blade: bool = False
    special_rules: list[str] = field(default_factory=list)


def roll_number_appearing(dice_str: str) -> int:
    """Roll for number of enemies appearing.

    Formats: "2d3+3", "1d3+5", "1d6+3", "1d3+6", "1d3+4"
    """
    parts = dice_str.split("+")
    bonus = int(parts[1]) if len(parts) > 1 else 0
    dice_part = parts[0]

    num, sides = dice_part.split("d")
    num = int(num)
    sides = int(sides)

    total = sum(roll_d6(f"Number appearing ({dice_str})").total % sides + 1
                for _ in range(num))

    # Proper dice rolling for non-d6
    if sides == 3:
        # d3 = (d6+1) // 2
        total = 0
        for _ in range(num):
            r = roll_d6("Number appearing").total
            total += (r + 1) // 2
    elif sides == 6:
        result = roll_nd6(num, "Number appearing")
        total = result.total
    else:
        total = sum(roll_d6("Number appearing").total for _ in range(num))

    return total + bonus


def generate_tactical_enemy_group(
    enemy_type_id: str | None = None,
) -> list[GeneratedEnemy]:
    """Generate a complete tactical enemy group.

    Args:
        enemy_type_id: Specific enemy type, or None to roll randomly.

    Returns:
        List of generated enemy figures with full stats and weapons.
    """
    if enemy_type_id is None:
        _, entry = TACTICAL_ENEMY_TABLE.roll_on_table("Tactical enemy type")
        enemy_type_id = entry.result_id

    if enemy_type_id not in TACTICAL_ENEMY_PROFILES:
        # Unknown type (e.g. slyn placeholder) — fall back to random
        _, entry = TACTICAL_ENEMY_TABLE.roll_on_table("Tactical enemy type")
        enemy_type_id = entry.result_id
    profile = TACTICAL_ENEMY_PROFILES[enemy_type_id]
    count = roll_number_appearing(profile.number_dice)

    # Determine roles: 1 specialist always, 1 leader if 6+
    has_leader = count >= 6
    enemies: list[GeneratedEnemy] = []

    for i in range(count):
        if i == 0:
            role = "specialist"
        elif i == 1 and has_leader:
            role = "leader"
        else:
            role = "regular"

        # Stats based on role
        is_elite = role in ("specialist", "leader")
        cs = profile.combat_skill_elite if is_elite else profile.combat_skill
        tough = profile.toughness_elite if role == "leader" else profile.toughness
        armor = profile.armor_save_elite if is_elite else profile.armor_save
        kp = 0
        if role == "leader":
            kp = profile.kill_points_leader
            cs = max(cs, profile.combat_skill + 1)  # Leaders get +1 CS minimum
        elif role == "specialist":
            # Some enemy types give specialists KP
            if "enhanced_models" in profile.special_rules:
                kp = 1

        # Roll weapon
        has_blade = False
        if role == "specialist":
            weapon_id = roll_specialist_weapon()
        elif role == "leader":
            weapon_id, has_blade = roll_grunt_weapon()
            # Leaders also get a leader weapon (we'll use whichever is better)
            leader_weapon_id = roll_leader_weapon()
            leader_wpn = ENEMY_WEAPONS[leader_weapon_id]
            grunt_wpn = ENEMY_WEAPONS[weapon_id]
            # Use the leader weapon if it's melee, otherwise keep both
            if leader_wpn.range_inches == 0:
                has_blade = True  # They carry the melee weapon as secondary
            else:
                weapon_id = leader_weapon_id  # Use the ranged leader weapon
        else:
            weapon_id, has_blade = roll_grunt_weapon()

        weapon = ENEMY_WEAPONS[weapon_id]

        enemy = GeneratedEnemy(
            name=f"{profile.name} {i+1}" if role == "regular" else f"{profile.name} {role.title()}",
            enemy_type=enemy_type_id,
            role=role,
            speed=profile.speed,
            combat_skill=cs,
            toughness=tough,
            panic_range=profile.panic_range,
            armor_save=armor,
            kill_points=kp,
            weapon_id=weapon_id,
            weapon=weapon,
            has_blade=has_blade,
            special_rules=list(profile.special_rules),
        )
        enemies.append(enemy)

    return enemies

"""Lifeform generation tables for Planetfall.

Lifeforms are alien creatures generated from multiple D100 tables:
mobility, combat skill, strike power, defense, special attacks, unique abilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import random as _rng

from planetfall.engine.dice import roll_d100, roll_d6


@dataclass
class LifeformProfile:
    """A generated lifeform type with full stats."""
    speed: int
    partially_airborne: bool
    combat_skill: int
    strike_damage: int  # melee damage bonus
    toughness: int
    armor_save: int  # 0 = none
    kill_points: int
    dodge: bool  # evade hit on natural 6
    special_attack: str = ""  # "" = none
    special_attack_details: dict = field(default_factory=dict)
    unique_ability: str = ""  # "" = none
    unique_ability_details: dict = field(default_factory=dict)


def _roll_mobility() -> tuple[int, bool]:
    """Roll on the mobility table.

    Returns (speed, partially_airborne).
    Airborne if roll ends in 0 or 5.
    """
    roll = roll_d100("Lifeform mobility").total
    airborne = roll % 10 in (0, 5)

    if roll <= 25:
        return 5, airborne
    elif roll <= 80:
        return 6, airborne
    else:
        return 7, airborne


def _roll_combat_skill() -> int:
    """Roll on the combat skill table."""
    roll = roll_d100("Lifeform combat skill").total
    if roll <= 25:
        return 0
    elif roll <= 85:
        return 1
    else:
        return 2


def _roll_strike_power() -> tuple[int, bool]:
    """Roll on strike power table.

    Returns (damage_bonus, has_special_attack).
    Special attack if roll ends in 0 or 5.
    """
    roll = roll_d100("Lifeform strike power").total
    has_special = roll % 10 in (0, 5)

    if roll <= 20:
        return 0, has_special
    elif roll <= 85:
        return 1, has_special
    else:
        return 2, has_special


def _roll_special_attack() -> tuple[str, dict]:
    """Roll on the special attack table."""
    roll = roll_d100("Lifeform special attack").total

    if roll <= 15:
        return "razor_claws", {"description": "Melee attacks negate Saving Throws"}
    elif roll <= 30:
        return "eruption", {
            "description": "When activates, D6 to hit every character within 6\" LoS. On 6, Damage +0 hit, knocked Sprawling",
            "range": 6, "hit_on": 6, "damage_bonus": 0,
        }
    elif roll <= 50:
        return "shoot", {
            "description": "Range 18\", Damage 1. On natural 6, may shoot again",
            "range": 18, "damage_bonus": 1, "chain_on_6": True,
        }
    elif roll <= 70:
        return "spit", {
            "description": "Range 9\". Target and figures within 1\" hit on 5-6. Damage +0. Ignores Armor",
            "range": 9, "hit_on": 5, "damage_bonus": 0, "ignores_armor": True,
        }
    elif roll <= 85:
        return "overpower", {
            "description": "Hit but survives = thrown 1D6\" backwards",
        }
    else:
        return "ferocity", {
            "description": "When initiating brawling, roll twice and pick best die",
        }


def _roll_defense() -> tuple[int, int, int, bool]:
    """Roll on the defensive abilities table.

    Returns (toughness, armor_save, kill_points, has_dodge).
    """
    roll = roll_d100("Lifeform defense").total

    if roll <= 25:
        return 4, 0, 0, False
    elif roll <= 35:
        return 4, 5, 0, False  # 5+ armor save
    elif roll <= 45:
        return 3, 0, 0, True  # Dodge: evade on natural 6
    elif roll <= 65:
        return 4, 0, 1, False  # 1 KP
    elif roll <= 80:
        return 5, 0, 0, False
    elif roll <= 90:
        return 5, 5, 0, False  # 5+ armor save
    else:
        return 5, 0, 1, False  # 1 KP


def _roll_unique_ability() -> tuple[str, dict]:
    """Roll on the unique abilities table."""
    roll = roll_d100("Lifeform unique ability").total

    if roll <= 30:
        return "", {}  # No special ability
    elif roll <= 40:
        return "pull", {
            "description": "Closest character in sight pulled 1D6\" closer. If base contact, brawl with +2 Damage",
            "damage_bonus": 2,
        }
    elif roll <= 50:
        return "jump", {
            "description": "Jumps 1D6+1\" towards nearest character. Clears obstacles. Can knock Sprawling",
        }
    elif roll <= 55:
        return "teleport", {
            "description": "Teleports 2D6\" away, random direction",
        }
    elif roll <= 60:
        return "paralyze", {
            "description": "Characters within 6\" LoS roll 1D6+Savvy. Under 4 = cannot act",
            "range": 6, "resist_target": 4, "uses_savvy": True,
        }
    elif roll <= 70:
        return "terror", {
            "description": "Characters within 6\" LoS roll 1D6+Savvy. Under 5 = retreat and Stunned",
            "range": 6, "resist_target": 5, "uses_savvy": True,
        }
    elif roll <= 80:
        return "confuse", {
            "description": "Closest character rolls 1D6+Savvy. Under 6 = full move random direction",
            "resist_target": 6, "uses_savvy": True,
        }
    elif roll <= 90:
        return "hinder", {
            "description": "Characters within 8\" have movement halved next activation",
            "range": 8,
        }
    else:
        return "knock_down", {
            "description": "Roll 1D6. Characters within that distance knocked Sprawling",
        }


def generate_callsign(profile: LifeformProfile) -> str:
    """Generate a callsign/nickname for a lifeform based on its traits."""
    # Prefixes based on combat characteristics
    fast_prefixes = ["Dart", "Flash", "Blur", "Whip", "Bolt", "Streak"]
    tough_prefixes = ["Iron", "Stone", "Titan", "Brute", "Tank", "Ridge"]
    deadly_prefixes = ["Fang", "Claw", "Razor", "Spike", "Gore", "Maw"]
    stealthy_prefixes = ["Ghost", "Shade", "Wraith", "Haze", "Wisp", "Phantom"]
    generic_prefixes = ["Crawler", "Stalker", "Howler", "Lurker", "Prowler", "Skitter"]

    # Suffixes based on unique traits
    airborne_suffixes = ["wing", "hawk", "bat", "raptor", "kite", "glider"]
    armored_suffixes = ["shell", "hide", "scale", "plate", "carapace", "back"]
    agile_suffixes = ["runner", "dancer", "snake", "fox", "cat", "hound"]
    savage_suffixes = ["maw", "jaw", "tooth", "horn", "tail", "crest"]
    generic_suffixes = ["beast", "thing", "fiend", "spawn", "form", "brood"]

    # Choose prefix based on dominant trait
    if profile.speed >= 8:
        prefix = _rng.choice(fast_prefixes)
    elif profile.toughness >= 5:
        prefix = _rng.choice(tough_prefixes)
    elif profile.strike_damage >= 2:
        prefix = _rng.choice(deadly_prefixes)
    elif profile.dodge:
        prefix = _rng.choice(stealthy_prefixes)
    else:
        prefix = _rng.choice(generic_prefixes)

    # Choose suffix based on secondary traits
    if profile.partially_airborne:
        suffix = _rng.choice(airborne_suffixes)
    elif profile.armor_save:
        suffix = _rng.choice(armored_suffixes)
    elif profile.speed >= 6:
        suffix = _rng.choice(agile_suffixes)
    elif profile.strike_damage >= 1:
        suffix = _rng.choice(savage_suffixes)
    else:
        suffix = _rng.choice(generic_suffixes)

    return f"{prefix}{suffix}"


def generate_lifeform() -> LifeformProfile:
    """Generate a complete lifeform profile from all tables."""
    speed, airborne = _roll_mobility()
    combat_skill = _roll_combat_skill()
    strike_damage, has_special_attack = _roll_strike_power()
    toughness, armor_save, kill_points, dodge = _roll_defense()

    special_attack = ""
    special_attack_details = {}
    if has_special_attack:
        special_attack, special_attack_details = _roll_special_attack()

    # Also check combat_skill roll for special attack trigger
    # (roll ending in 0 or 5 on combat skill also triggers)
    # Already handled by strike_power check above

    unique_ability, unique_ability_details = _roll_unique_ability()

    return LifeformProfile(
        speed=speed,
        partially_airborne=airborne,
        combat_skill=combat_skill,
        strike_damage=strike_damage,
        toughness=toughness,
        armor_save=armor_save,
        kill_points=kill_points,
        dodge=dodge,
        special_attack=special_attack,
        special_attack_details=special_attack_details,
        unique_ability=unique_ability,
        unique_ability_details=unique_ability_details,
    )


def generate_lifeform_group(count: int = 0) -> list[LifeformProfile]:
    """Generate a group of lifeforms.

    If count is 0, rolls 1D6+3 for number appearing.
    All lifeforms in a group share the same profile.
    """
    if count == 0:
        roll = roll_d6("Lifeform count")
        count = roll.total + 3

    profile = generate_lifeform()
    return [profile] * count  # All share same stats

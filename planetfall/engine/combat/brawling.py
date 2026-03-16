"""Brawling (melee) resolution for Planetfall combat.

Brawling occurs when a figure moves into base contact (same zone) with
an enemy. Both sides roll 1D6 + Combat Skill + weapon modifier.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from planetfall.engine.combat.battlefield import (
    Battlefield, Figure, FigureStatus,
)
from planetfall.engine.dice import roll_d6


@dataclass
class BrawlResult:
    """Result of a brawl between two figures."""
    attacker: str
    defender: str
    attacker_roll: int
    attacker_total: int
    defender_roll: int
    defender_total: int
    winner: str  # "attacker", "defender", "draw"
    attacker_hits_taken: int = 0
    defender_hits_taken: int = 0
    attacker_outcome: str = ""  # "fine", "casualty", "sprawling", "stunned"
    defender_outcome: str = ""
    log: list[str] = field(default_factory=list)


def _get_brawl_modifier(figure: Figure) -> int:
    """Get the brawling weapon modifier for a figure.

    Melee weapon: +2
    Pistol: +1
    No weapon: +0
    """
    if figure.status == FigureStatus.SPRAWLING:
        return 0  # Sprawling: no weapon bonuses

    if figure.melee_damage > 0 or any(
        t in figure.weapon_traits for t in ("melee",)
    ):
        return 2  # melee weapon

    if "pistol" in figure.weapon_traits:
        return 1

    return 0


def _resolve_brawl_damage(
    attacker: Figure,
    target: Figure,
    log: list[str],
) -> str:
    """Resolve damage from a brawl hit.

    Returns outcome: "casualty", "sprawling", or "stunned".
    """
    damage_roll = roll_d6(f"Brawl damage vs {target.name}")
    damage_bonus = attacker.melee_damage

    # If attacker has a melee weapon, use its damage
    if any(t in attacker.weapon_traits for t in ("melee",)):
        damage_bonus = max(damage_bonus, attacker.weapon_damage)

    damage_total = damage_roll.total + damage_bonus
    toughness = target.effective_toughness

    if damage_total > toughness:
        target.status = FigureStatus.CASUALTY
        log.append(
            f"  Brawl damage: {damage_roll.total}+{damage_bonus}={damage_total} "
            f"vs Toughness {toughness} -> CASUALTY"
        )
        return "casualty"
    elif damage_total == toughness:
        target.status = FigureStatus.SPRAWLING
        log.append(
            f"  Brawl damage: {damage_roll.total}+{damage_bonus}={damage_total} "
            f"vs Toughness {toughness} -> Sprawling"
        )
        return "sprawling"
    else:
        target.stun_markers = min(target.stun_markers + 1, 3)
        log.append(
            f"  Brawl damage: {damage_roll.total}+{damage_bonus}={damage_total} "
            f"vs Toughness {toughness} -> Stunned ({target.stun_markers} markers)"
        )
        return "stunned"


def resolve_brawl(
    battlefield: Battlefield,
    attacker: Figure,
    defender: Figure,
    attacker_bonus: int = 0,
    defender_bonus: int = 0,
) -> BrawlResult:
    """Resolve a brawl between attacker and defender.

    Args:
        attacker_bonus: Additional bonus (e.g., from multiple opponents).
        defender_bonus: Additional bonus (e.g., from stun markers removed).
    """
    result = BrawlResult(
        attacker=attacker.name,
        defender=defender.name,
        attacker_roll=0,
        attacker_total=0,
        defender_roll=0,
        defender_total=0,
        winner="draw",
    )
    log = result.log

    # Handle stunned figures entering brawl:
    # Remove stun markers, opponent gets +1 per marker removed
    if attacker.stun_markers > 0:
        defender_bonus += attacker.stun_markers
        log.append(
            f"{attacker.name} stunned ({attacker.stun_markers} markers) "
            f"-> {defender.name} gets +{attacker.stun_markers} bonus"
        )
        attacker.stun_markers = 0

    if defender.stun_markers > 0:
        attacker_bonus += defender.stun_markers
        log.append(
            f"{defender.name} stunned ({defender.stun_markers} markers) "
            f"-> {attacker.name} gets +{defender.stun_markers} bonus"
        )
        defender.stun_markers = 0

    # Roll 1D6 each
    atk_roll = roll_d6(f"{attacker.name} brawl")
    def_roll = roll_d6(f"{defender.name} brawl")

    result.attacker_roll = atk_roll.total
    result.defender_roll = def_roll.total

    # Calculate totals
    atk_cs = attacker.combat_skill if attacker.status != FigureStatus.SPRAWLING else 0
    def_cs = defender.combat_skill if defender.status != FigureStatus.SPRAWLING else 0

    atk_weapon_mod = _get_brawl_modifier(attacker)
    def_weapon_mod = _get_brawl_modifier(defender)

    atk_total = atk_roll.total + atk_cs + atk_weapon_mod + attacker_bonus
    def_total = def_roll.total + def_cs + def_weapon_mod + defender_bonus

    result.attacker_total = atk_total
    result.defender_total = def_total

    log.append(
        f"{attacker.name}: {atk_roll.total} + CS{atk_cs} + W{atk_weapon_mod}"
        f"{f' + B{attacker_bonus}' if attacker_bonus else ''} = {atk_total}"
    )
    log.append(
        f"{defender.name}: {def_roll.total} + CS{def_cs} + W{def_weapon_mod}"
        f"{f' + B{defender_bonus}' if defender_bonus else ''} = {def_total}"
    )

    # Track hits from natural 6 (feint) and natural 1 (fumble)
    attacker_bonus_hits = 0
    defender_bonus_hits = 0

    if atk_roll.total == 6:
        attacker_bonus_hits += 1
        log.append(f"{attacker.name} rolled natural 6 -> Feint! Bonus hit on defender")

    if def_roll.total == 6:
        defender_bonus_hits += 1
        log.append(f"{defender.name} rolled natural 6 -> Feint! Bonus hit on attacker")

    if atk_roll.total == 1:
        defender_bonus_hits += 1
        log.append(f"{attacker.name} rolled natural 1 -> Fumble! Bonus hit on attacker")

    if def_roll.total == 1:
        attacker_bonus_hits += 1
        log.append(f"{defender.name} rolled natural 1 -> Fumble! Bonus hit on defender")

    # Determine winner
    if atk_total > def_total:
        result.winner = "attacker"
        result.defender_hits_taken = 1 + attacker_bonus_hits
        result.attacker_hits_taken = defender_bonus_hits
        log.append(f"{attacker.name} wins the brawl!")
    elif def_total > atk_total:
        result.winner = "defender"
        result.attacker_hits_taken = 1 + defender_bonus_hits
        result.defender_hits_taken = attacker_bonus_hits
        log.append(f"{defender.name} wins the brawl!")
    else:
        result.winner = "draw"
        # Draw: both take a hit
        result.attacker_hits_taken = 1 + defender_bonus_hits
        result.defender_hits_taken = 1 + attacker_bonus_hits
        log.append("Draw! Both figures take a hit")

    # Resolve damage for all hits
    result.defender_outcome = "fine"
    for i in range(result.defender_hits_taken):
        if not defender.is_alive:
            break
        outcome = _resolve_brawl_damage(attacker, defender, log)
        result.defender_outcome = outcome

    result.attacker_outcome = "fine"
    for i in range(result.attacker_hits_taken):
        if not attacker.is_alive:
            break
        outcome = _resolve_brawl_damage(defender, attacker, log)
        result.attacker_outcome = outcome

    # Brawl knockback (rules p.38): surviving figure knocked back 1" per hit taken.
    # 1" = no effect, 2" = Sprawling, 3"+ = pushed back a zone + Sprawling.
    _apply_brawl_knockback(battlefield, defender, result.defender_hits_taken, attacker, log)
    _apply_brawl_knockback(battlefield, attacker, result.attacker_hits_taken, defender, log)

    return result


def _apply_brawl_knockback(
    battlefield: Battlefield,
    target: Figure,
    hits_taken: int,
    pusher: Figure,
    log: list[str],
) -> None:
    """Apply knockback from brawling hits (rules p.38).

    Each hit survived knocks back 1". More than 1" = Sprawling.
    3"+ = pushed back a zone + Sprawling.
    """
    if not target.is_alive or hits_taken == 0:
        return
    if target.status == FigureStatus.CASUALTY:
        return

    knockback_inches = hits_taken  # 1" per hit taken
    if knockback_inches >= 3:
        # Push to adjacent zone away from pusher + Sprawling
        adj = battlefield.adjacent_zones(*target.zone)
        push_zones = [
            z for z in adj
            if battlefield.zone_distance(z, pusher.zone) > battlefield.zone_distance(target.zone, pusher.zone)
            and battlefield.zone_has_capacity(*z, target.side)
        ]
        if push_zones:
            import random
            target.zone = random.choice(push_zones)
            log.append(
                f"Brawl knockback {knockback_inches}\": {target.name} "
                f"pushed to {target.zone} and Sprawling!"
            )
        else:
            log.append(
                f"Brawl knockback {knockback_inches}\": {target.name} knocked Sprawling!"
            )
        if target.status != FigureStatus.CASUALTY:
            target.status = FigureStatus.SPRAWLING
    elif knockback_inches >= 2:
        if target.status != FigureStatus.CASUALTY:
            target.status = FigureStatus.SPRAWLING
        log.append(
            f"Brawl knockback {knockback_inches}\": {target.name} knocked Sprawling!"
        )

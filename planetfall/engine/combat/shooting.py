"""Shooting resolution for Planetfall combat.

To-hit: 1D6 + Combat Skill vs target number based on range/cover.
Damage: 1D6 + weapon damage vs toughness -> casualty/sprawling/stunned.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from planetfall.engine.combat.battlefield import (
    Battlefield, Figure, FigureStatus, TerrainType, zone_range_inches,
)
from planetfall.engine.dice import roll_d6, RollResult


def _get_slyn_pair_id(fig: Figure) -> str | None:
    """Get the pair ID for a Slyn figure (e.g. 'pair_1'), or None if not Slyn."""
    if fig.char_class != "slyn":
        return None
    for rule in fig.special_rules:
        if rule.startswith("pair_") and rule != "pair_hit":
            return rule
    return None


def _find_slyn_partner(
    battlefield: Battlefield, fig: Figure, pair_id: str
) -> Figure | None:
    """Find the other Slyn in the same pair."""
    for f in battlefield.figures:
        if (f is not fig and pair_id in f.special_rules
                and f.status != FigureStatus.CASUALTY):
            return f
    return None


@dataclass
class ShotResult:
    """Result of a single shot at a target."""
    shooter: str
    target: str
    hit_roll: int
    hit_needed: int
    hit: bool
    damage_roll: int = 0
    damage_total: int = 0
    target_toughness: int = 0
    armor_saved: bool = False
    outcome: str = ""  # "miss", "casualty", "sprawling", "stunned", "saved"
    log: list[str] = field(default_factory=list)


def get_hit_target(
    battlefield: Battlefield,
    shooter: Figure,
    target: Figure,
    shooter_moved: bool = False,
    condition: object = None,
) -> int:
    """Determine the to-hit target number (roll this or higher to hit).

    Returns:
        Target number on 1D6 (3, 5, or 6). Returns 7 if impossible.
    """
    # LoS check — blocked = cannot shoot
    los = battlefield.check_los(shooter.zone, target.zone)
    if los == "blocked":
        return 7  # no line of sight

    dist = battlefield.zone_distance(shooter.zone, target.zone)
    approx_inches = zone_range_inches(dist)

    # Visibility limit — cannot fire beyond visibility range
    if condition and getattr(condition, "visibility_limit", 0) > 0:
        if approx_inches > condition.visibility_limit:
            return 7  # beyond visibility

    # Cloud LoS blocking — cannot fire through cloud zones
    if battlefield.cloud_positions:
        between = battlefield.get_zones_between(shooter.zone, target.zone)
        for pz in between:
            zone = battlefield.get_zone(*pz)
            if zone.has_cloud:
                return 7  # cloud blocks LoS

    # Check range
    effective_range = shooter.weapon_range
    if "cumbersome" in shooter.weapon_traits and shooter_moved:
        effective_range = min(effective_range, 12)
    # Visibility also caps effective range
    if condition and getattr(condition, "visibility_limit", 0) > 0:
        effective_range = min(effective_range, condition.visibility_limit)

    if approx_inches > effective_range:
        return 7  # out of range

    # Cover check — LoS-based: target has cover if in a heavy cover zone
    # OR if LoS passes through any heavy cover zone between shooter and target
    target_has_cover = battlefield.has_cover_los(shooter.zone, target.zone)

    if target_has_cover:
        # Cover is ignored by area, stream, phased_fire
        if any(t in shooter.weapon_traits for t in ("area", "stream", "phased_fire")):
            target_has_cover = False
        # High ground negates cover UNLESS target is directly in a heavy cover zone
        if (battlefield.shooter_on_high_ground(shooter.zone, target.zone)
                and not battlefield.target_in_cover_zone(target.zone)):
            target_has_cover = False

    if target_has_cover:
        hit_needed = 6
    elif dist <= 2:
        hit_needed = 3  # within 2 zones (~8") and in the open
    else:
        hit_needed = 5  # in the open, beyond 2 zones

    return hit_needed


def get_effective_hit(
    battlefield: Battlefield,
    shooter: Figure,
    target: Figure,
    shooter_moved: bool = False,
    condition: object = None,
) -> int:
    """Effective natural D6 roll needed to hit, accounting for all modifiers.

    This is hit_needed minus (CS + stabilized + calibration), clamped to 1-7.
    A result of 1 means auto-hit, 7 means impossible.
    Used for action descriptions so the player sees the real difficulty.
    """
    hit_needed = get_hit_target(battlefield, shooter, target, shooter_moved, condition=condition)
    if hit_needed > 6:
        return 7

    bonus = shooter.combat_skill
    if "mind_link" in shooter.weapon_traits:
        bonus = shooter.savvy
    if "stabilized" in shooter.weapon_traits and not shooter_moved:
        bonus += 1
    if shooter.hit_bonus > 0:
        bonus += shooter.hit_bonus

    effective = hit_needed - bonus
    return max(1, min(effective, 7))


def resolve_shot(
    battlefield: Battlefield,
    shooter: Figure,
    target: Figure,
    shooter_moved: bool = False,
    condition: object = None,
) -> ShotResult:
    """Resolve a single shot from shooter at target.

    Returns a ShotResult with full resolution details.
    """
    result = ShotResult(
        shooter=shooter.name,
        target=target.name,
        hit_roll=0,
        hit_needed=0,
        hit=False,
    )
    log = result.log

    hit_needed = get_hit_target(battlefield, shooter, target, shooter_moved, condition=condition)
    result.hit_needed = hit_needed

    if hit_needed > 6:
        result.outcome = "miss"
        log.append(f"{shooter.name} -> {target.name}: Out of range")
        return result

    # Roll to hit: 1D6 + Combat Skill (or Savvy for mind-link weapons)
    roll = roll_d6(f"{shooter.name} shooting at {target.name}")
    natural_roll = roll.total
    if "mind_link" in shooter.weapon_traits:
        # Mind-link: use Savvy instead of Combat Skill
        modified_roll = natural_roll + shooter.savvy
        log.append(f"Mind-link: using Savvy +{shooter.savvy} instead of Combat Skill")
        # Scientists roll twice, pick best (Scientific Mind applies to Savvy tests)
        if shooter.char_class == "scientist":
            roll2 = roll_d6(f"{shooter.name} mind-link (2nd roll)")
            best = max(natural_roll, roll2.total)
            modified_roll = best + shooter.savvy
            log.append(
                f"Scientific Mind: rolled {natural_roll},{roll2.total} "
                f"best={best}+Savvy({shooter.savvy})={modified_roll}"
            )
            natural_roll = best
    else:
        modified_roll = natural_roll + shooter.combat_skill

    # Stabilized bonus
    if "stabilized" in shooter.weapon_traits and not shooter_moved:
        modified_roll += 1
        log.append("Stabilized: +1 to hit")

    # Calibration hit bonus (from step 17 personal_calibrations)
    if shooter.hit_bonus > 0:
        modified_roll += shooter.hit_bonus
        log.append(f"Calibration: +{shooter.hit_bonus} to hit")

    # Defensive Aid marker: if target is a player with an aid marker and
    # shooter is an enemy, auto-spend for -1 to incoming attack
    from planetfall.engine.combat.battlefield import FigureSide
    if (target.aid_marker
            and target.side == FigureSide.PLAYER
            and shooter.side == FigureSide.ENEMY):
        target.aid_marker = False
        modified_roll -= 1
        log.append(f"{target.name} spends Aid marker: -1 to enemy attack")

    # Condition shooting penalty
    if condition and getattr(condition, "shooting_penalty", 0) != 0:
        circ = getattr(condition, "shooting_circumstance", "")
        apply_penalty = False
        if circ == "range":
            dist = battlefield.zone_distance(shooter.zone, target.zone)
            from planetfall.engine.combat.battlefield import zone_range_inches
            if zone_range_inches(dist) > 15:
                apply_penalty = True
        elif circ == "terrain_type":
            # Penalty for shots from/at/through selected terrain type
            apply_penalty = True  # simplified: always applies when terrain_type
        elif circ == "random_round":
            # This is handled per-round in session._apply_condition_effects
            # Check battlefield flag
            apply_penalty = getattr(battlefield, "_shooting_penalty_active", False)
        else:
            apply_penalty = True
        if apply_penalty:
            modified_roll += condition.shooting_penalty  # negative value
            log.append(f"Condition penalty: {condition.shooting_penalty} to hit")

    # Cloud cover: targets inside clouds get cover
    if battlefield.cloud_positions:
        target_zone = battlefield.get_zone(*target.zone)
        if target_zone.has_cloud:
            hit_needed = max(hit_needed, 6)  # counts as cover
            log.append("Target in cloud: counts as cover (6+ to hit)")

    result.hit_roll = modified_roll

    is_hit = modified_roll >= hit_needed
    is_critical = natural_roll == 6 and "critical" in shooter.weapon_traits

    # Build the skill label for log output
    if "mind_link" in shooter.weapon_traits:
        skill_label = f"Savvy({shooter.savvy})"
        skill_val = shooter.savvy
    else:
        skill_label = str(shooter.combat_skill)
        skill_val = shooter.combat_skill

    if not is_hit:
        result.outcome = "miss"
        log.append(
            f"{shooter.name} -> {target.name}: "
            f"Rolled {natural_roll}+{skill_val}={modified_roll} "
            f"vs {hit_needed}+ -> Miss"
        )
        return result

    # Scatter terrain absorption: if target is in scatter terrain and the
    # modified roll exactly equals the to-hit number, scatter absorbs the hit
    # and the scatter terrain is destroyed (zone becomes open)
    if (not any(t in shooter.weapon_traits for t in ("area", "stream", "phased_fire"))
            and battlefield.has_scatter(shooter.zone, target.zone)
            and modified_roll == hit_needed):
        result.outcome = "miss"
        result.hit = False
        # Destroy the scatter terrain
        zone = battlefield.get_zone(*target.zone)
        zone.terrain = TerrainType.OPEN
        log.append(
            f"{shooter.name} -> {target.name}: "
            f"Rolled {natural_roll}+{skill_val}={modified_roll} "
            f"vs {hit_needed}+ -> Scatter terrain absorbs the hit! "
            f"Zone ({target.zone[0]},{target.zone[1]}) is now open ground."
        )
        return result

    result.hit = True
    log.append(
        f"{shooter.name} -> {target.name}: "
        f"Rolled {natural_roll}+{skill_val}={modified_roll} "
        f"vs {hit_needed}+ -> Hit!"
    )

    # Resolve damage for the hit (critical gives 2 hits, resolve best)
    hits_to_resolve = 2 if is_critical else 1
    if is_critical:
        log.append("Critical hit! 2 hits on target")

    best_outcome = _resolve_damage(battlefield, shooter, target, shooter_moved, log)
    if hits_to_resolve == 2:
        second = _resolve_damage(battlefield, shooter, target, shooter_moved, log)
        # Keep the worse outcome for the target (casualty > sprawling > stunned)
        severity = {"casualty": 3, "sprawling": 2, "stunned": 1, "saved": 0}
        if severity.get(second.outcome, 0) > severity.get(best_outcome.outcome, 0):
            best_outcome = second

    result.damage_roll = best_outcome.damage_roll
    result.damage_total = best_outcome.damage_total
    result.target_toughness = best_outcome.target_toughness
    result.armor_saved = best_outcome.armor_saved
    result.outcome = best_outcome.outcome

    # Knockback: target that survives a hit is knocked back 1" per hit.
    # 1" = no effect, 2" = Sprawling, 3"+ = knocked back a zone + Sprawling.
    if ("knockback" in shooter.weapon_traits
            and result.hit and target.is_alive
            and result.outcome not in ("casualty", "saved")):
        # Each surviving hit = 1" knockback. shots that hit contribute.
        knockback_inches = 1  # base: 1 hit = 1"
        if knockback_inches >= 3:
            # Push to adjacent zone + Sprawling
            from planetfall.engine.combat.battlefield import FigureSide
            adj = battlefield.adjacent_zones(*target.zone)
            # Push away from shooter
            push_zones = [z for z in adj if battlefield.zone_distance(z, shooter.zone) > battlefield.zone_distance(target.zone, shooter.zone)]
            if push_zones and battlefield.zone_has_capacity(*push_zones[0], target.side):
                target.zone = push_zones[0]
                log.append(f"Knockback {knockback_inches}\": {target.name} pushed to {push_zones[0]} and Sprawling!")
            else:
                log.append(f"Knockback {knockback_inches}\": {target.name} knocked Sprawling!")
            target.status = FigureStatus.SPRAWLING
            result.outcome = "sprawling"
        elif knockback_inches >= 2:
            target.status = FigureStatus.SPRAWLING
            result.outcome = "sprawling"
            log.append(f"Knockback {knockback_inches}\": {target.name} knocked Sprawling!")
        else:
            log.append(f"Knockback {knockback_inches}\": {target.name} pushed but stays standing")

    return result


@dataclass
class _DamageResult:
    damage_roll: int
    damage_total: int
    target_toughness: int
    armor_saved: bool
    outcome: str


def _resolve_damage(
    battlefield: Battlefield,
    shooter: Figure,
    target: Figure,
    shooter_moved: bool,
    log: list[str],
) -> _DamageResult:
    """Resolve damage for a single hit."""
    # Armor save first
    if target.armor_save > 0:
        can_save = True
        # Force screen (Sleepers) ignores burning/AP — only negated by brawling
        has_force_screen = "force_screen" in target.special_rules
        if not has_force_screen and any(t in shooter.weapon_traits for t in ("burning", "ap_ammo")):
            can_save = False
            log.append("Armor save negated by weapon trait")
        if target.status == FigureStatus.SPRAWLING:
            can_save = False
            log.append("Sprawling: forfeits saving throw")

        if can_save:
            save_roll = roll_d6(f"{target.name} armor save")
            if save_roll.total >= target.armor_save:
                log.append(
                    f"{target.name} armor save: {save_roll.total} "
                    f"vs {target.armor_save}+ -> Saved!"
                )
                return _DamageResult(0, 0, target.effective_toughness, True, "saved")
            log.append(
                f"{target.name} armor save: {save_roll.total} "
                f"vs {target.armor_save}+ -> Failed"
            )

    # Damage roll
    damage_roll = roll_d6(f"Damage vs {target.name}")
    damage_bonus = shooter.weapon_damage

    # AP ammo: +1 damage if stationary
    if "ap_ammo" in shooter.weapon_traits and not shooter_moved:
        damage_bonus += 1
        log.append("AP Ammo: +1 damage (stationary)")

    damage_total = damage_roll.total + damage_bonus
    toughness = target.effective_toughness

    if damage_total > toughness:
        # Slyn pair damage: first hit wounds the pair, second destroys both
        slyn_pair = _get_slyn_pair_id(target)
        if slyn_pair and battlefield:
            if "pair_hit" not in target.special_rules:
                # First hit on this pair — wound but keep fighting
                target.special_rules.append("pair_hit")
                outcome = "stunned"  # treated as "wounded" for Slyn
                log.append(
                    f"Damage {damage_roll.total}+{damage_bonus}={damage_total} "
                    f"vs Toughness {toughness} -> Slyn pair wounded! (1 hit on pair)"
                )
                # Mark the partner too
                partner = _find_slyn_partner(battlefield, target, slyn_pair)
                if partner and "pair_hit" not in partner.special_rules:
                    partner.special_rules.append("pair_hit")
            else:
                # Second hit — both Slyn in pair are destroyed
                outcome = "casualty"
                target.status = FigureStatus.CASUALTY
                log.append(
                    f"Damage {damage_roll.total}+{damage_bonus}={damage_total} "
                    f"vs Toughness {toughness} -> CASUALTY — Slyn pair destroyed!"
                )
                partner = _find_slyn_partner(battlefield, target, slyn_pair)
                if partner and partner.is_alive:
                    partner.status = FigureStatus.CASUALTY
                    log.append(f"  {partner.name} also falls — psionic bond severed!")
        else:
            outcome = "casualty"
            target.status = FigureStatus.CASUALTY
            log.append(
                f"Damage {damage_roll.total}+{damage_bonus}={damage_total} "
                f"vs Toughness {toughness} -> CASUALTY"
            )
    elif damage_total == toughness:
        outcome = "sprawling"
        target.status = FigureStatus.SPRAWLING
        log.append(
            f"Damage {damage_roll.total}+{damage_bonus}={damage_total} "
            f"vs Toughness {toughness} -> Sprawling"
        )
    else:
        if "no_stun" in target.special_rules:
            outcome = "saved"
            log.append(
                f"Damage {damage_roll.total}+{damage_bonus}={damage_total} "
                f"vs Toughness {toughness} -> No effect (immune to stun)"
            )
        else:
            outcome = "stunned"
            target.stun_markers = min(target.stun_markers + 1, 3)
            log.append(
                f"Damage {damage_roll.total}+{damage_bonus}={damage_total} "
                f"vs Toughness {toughness} -> Stunned ({target.stun_markers} markers)"
            )

    return _DamageResult(
        damage_roll.total, damage_total, toughness, False, outcome
    )


def resolve_area_weapon(
    battlefield: Battlefield,
    shooter: Figure,
    target_zone: tuple[int, int],
    shooter_moved: bool = False,
) -> list[ShotResult]:
    """Resolve an Area weapon attack.

    Area weapons hit each enemy in the target zone on 4+ (no cover benefit).
    """
    results = []
    targets = battlefield.get_figures_in_zone(*target_zone)
    # Area doesn't affect friendly figures
    targets = [t for t in targets if t.side != shooter.side and t.is_alive]

    for target in targets:
        result = ShotResult(
            shooter=shooter.name,
            target=target.name,
            hit_roll=0,
            hit_needed=4,
            hit=False,
        )
        roll = roll_d6(f"Area hit on {target.name}")
        result.hit_roll = roll.total

        if roll.total >= 4:
            result.hit = True
            result.log.append(f"Area hit on {target.name}: {roll.total} vs 4+ -> Hit!")
            dmg = _resolve_damage(battlefield, shooter, target, shooter_moved, result.log)
            result.damage_roll = dmg.damage_roll
            result.damage_total = dmg.damage_total
            result.target_toughness = dmg.target_toughness
            result.armor_saved = dmg.armor_saved
            result.outcome = dmg.outcome
        else:
            result.outcome = "miss"
            result.log.append(f"Area hit on {target.name}: {roll.total} vs 4+ -> Miss")

        results.append(result)

    return results


def resolve_stream_weapon(
    battlefield: Battlefield,
    shooter: Figure,
    target_zone: tuple[int, int],
) -> list[ShotResult]:
    """Resolve a Stream weapon attack.

    Stream weapons automatically hit all figures in the target zone
    (including allies!).
    """
    results = []
    targets = battlefield.get_figures_in_zone(*target_zone)
    targets = [t for t in targets if t.is_alive]

    for target in targets:
        result = ShotResult(
            shooter=shooter.name,
            target=target.name,
            hit_roll=6,
            hit_needed=0,
            hit=True,
        )
        result.log.append(f"Stream auto-hit on {target.name}")
        dmg = _resolve_damage(battlefield, shooter, target, False, result.log)
        result.damage_roll = dmg.damage_roll
        result.damage_total = dmg.damage_total
        result.target_toughness = dmg.target_toughness
        result.armor_saved = dmg.armor_saved
        result.outcome = dmg.outcome
        results.append(result)

    return results


def resolve_shooting_action(
    battlefield: Battlefield,
    shooter: Figure,
    target: Figure,
    shooter_moved: bool = False,
    condition: object = None,
) -> list[ShotResult]:
    """Resolve a full shooting action (all shots from weapon).

    Handles multi-shot weapons and hail_of_fire trait.
    """
    if not shooter.is_alive or not target.is_alive:
        return []

    # Area weapons
    if "area" in shooter.weapon_traits:
        return resolve_area_weapon(
            battlefield, shooter, target.zone, shooter_moved
        )

    # Stream weapons
    if "stream" in shooter.weapon_traits:
        return resolve_stream_weapon(battlefield, shooter, target.zone)

    # Normal shooting
    shots = shooter.weapon_shots

    # Hail of fire: if all shots at same target, fire 4 instead
    if "hail_of_fire" in shooter.weapon_traits:
        shots = 4

    from planetfall.engine.combat.battlefield import FigureSide

    current_target = target
    results = []
    for _ in range(shots):
        if not current_target.is_alive:
            # Target killed — redirect remaining shots to another enemy in the same zone
            new_target = _find_overflow_target(
                battlefield, shooter, current_target, shooter_moved,
            )
            if new_target:
                results.append(_make_overflow_note(current_target, new_target))
                current_target = new_target
            else:
                break
        result = resolve_shot(battlefield, shooter, current_target, shooter_moved, condition=condition)
        results.append(result)

        # Hyperfire: if hit doesn't destroy target, fire again
        if "hyperfire" in shooter.weapon_traits and result.hit and current_target.is_alive:
            extra = resolve_shot(battlefield, shooter, current_target, shooter_moved, condition=condition)
            extra.log.insert(0, "Hyperfire: bonus shot!")
            results.append(extra)
            # Continue hyperfire chain while hitting and target alive
            while extra.hit and current_target.is_alive:
                extra = resolve_shot(battlefield, shooter, current_target, shooter_moved, condition=condition)
                extra.log.insert(0, "Hyperfire: bonus shot!")
                results.append(extra)

    return results


def _find_overflow_target(
    battlefield: Battlefield,
    shooter: Figure,
    dead_target: Figure,
    shooter_moved: bool,
) -> Figure | None:
    """Find another valid enemy in the same zone to redirect remaining shots."""
    from planetfall.engine.combat.battlefield import FigureSide
    candidates = [
        f for f in battlefield.figures
        if f.zone == dead_target.zone
        and f.side != shooter.side
        and f.is_alive
        and not f.is_contact
        and f is not dead_target
    ]
    if not candidates:
        return None
    # Pick the closest-to-original (first available)
    return candidates[0]


def _make_overflow_note(dead_target: Figure, new_target: Figure) -> ShotResult:
    """Create a log-only ShotResult noting the shot overflow."""
    note = ShotResult(
        shooter="", target=new_target.name,
        hit_roll=0, hit_needed=0, hit=False,
    )
    note.outcome = "redirect"
    note.log.append(
        f"{dead_target.name} destroyed — remaining shots redirect to {new_target.name}"
    )
    return note

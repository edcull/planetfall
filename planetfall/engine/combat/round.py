"""Battle round sequence for Planetfall combat.

Round phases:
1. Start Phase — scenario-specific triggers
2. Reaction Roll — assign dice to player characters
3. Quick Actions Phase — player chars with die <= Reaction
4. Enemy Actions Phase — all enemies act (specialists first)
5. Slow Actions Phase — player chars with die > Reaction
6. End Phase — victory check, panic, cleanup
"""

from __future__ import annotations

from dataclasses import dataclass, field

from planetfall.engine.combat.battlefield import (
    Battlefield, Figure, FigureSide, FigureStatus,
)
from planetfall.engine.combat.shooting import resolve_shooting_action, ShotResult
from planetfall.engine.combat.brawling import resolve_brawl, BrawlResult
from planetfall.engine.combat.enemy_ai import (
    get_enemy_activation_order, plan_enemy_action, find_move_toward_player, AIAction,
)
from planetfall.engine.dice import roll_d6, roll_nd6


@dataclass
class ActivationResult:
    """Result of a single figure's activation."""
    figure_name: str
    phase: str  # "quick", "enemy", "slow"
    action_type: str  # "move", "shoot", "brawl", "move_and_shoot", "aid", "hold"
    moved_to: tuple[int, int] | None = None
    shot_results: list[ShotResult] = field(default_factory=list)
    brawl_result: BrawlResult | None = None
    log: list[str] = field(default_factory=list)


@dataclass
class ReactionRollResult:
    """Result of the reaction roll phase."""
    dice_rolled: list[int]
    assignments: dict[str, int]  # figure_name -> die value
    quick_actors: list[str]
    slow_actors: list[str]
    log: list[str] = field(default_factory=list)


@dataclass
class PanicResult:
    """Result of a panic check."""
    roll: int
    panic_range: int
    panicked: bool
    fled_figure: str | None = None
    log: list[str] = field(default_factory=list)


@dataclass
class RoundResult:
    """Complete result of a battle round."""
    round_number: int
    reaction: ReactionRollResult | None = None
    activations: list[ActivationResult] = field(default_factory=list)
    panic: PanicResult | None = None
    casualties_this_round: list[str] = field(default_factory=list)
    log: list[str] = field(default_factory=list)


def _fireteam_effective_reactions(battlefield: Battlefield, fireteam_id: str, base_reactions: int = 2) -> int:
    """Get effective reactions for a fireteam, including formation bonus.

    If all surviving members are in the same zone and ≥2 are alive,
    reactions score is one point higher (e.g. 3 instead of 2).
    """
    if battlefield.fireteam_in_formation(fireteam_id):
        return base_reactions + 1
    return base_reactions


def roll_reaction_dice(battlefield: Battlefield) -> tuple[list[int], list[tuple[str, int]]]:
    """Roll reaction dice and return (sorted_dice, [(name, reactions_stat), ...]).

    Fireteams contribute a single die to the pool and appear as one entry
    in figures_info (using the fireteam name, e.g. "Fireteam Alpha").
    Non-fireteam figures contribute one die each as before.
    """
    player_figs = [
        f for f in battlefield.figures
        if f.side == FigureSide.PLAYER and f.is_alive and f.can_act
    ]
    if not player_figs:
        return [], []

    scientist_count = sum(
        1 for f in player_figs
        if f.char_class == "scientist" and f.is_active
    )

    # Count dice: 1 per non-fireteam figure + 1 per fireteam + scientist bonus
    seen_fireteams: set[str] = set()
    num_dice = 0
    figures_info: list[tuple[str, int]] = []

    for f in player_figs:
        if f.fireteam_id:
            if f.fireteam_id not in seen_fireteams:
                seen_fireteams.add(f.fireteam_id)
                num_dice += 1
                eff_reactions = _fireteam_effective_reactions(
                    battlefield, f.fireteam_id, f.reactions,
                )
                figures_info.append((f.fireteam_id, eff_reactions))
        else:
            num_dice += 1
            figures_info.append((f.name, f.reactions))

    num_dice += scientist_count
    roll_result = roll_nd6(num_dice, "Reaction roll")
    dice = sorted(roll_result.values)
    figures_info = sorted(figures_info, key=lambda x: x[1], reverse=True)
    return dice, figures_info


def roll_reactions(
    battlefield: Battlefield,
    assignments: dict[str, int] | None = None,
) -> ReactionRollResult:
    """Roll reaction dice and determine quick/slow actors.

    Fireteam rules:
    - Each fireteam contributes 1 die (not 1 per grunt).
    - All fireteam members share the same die and are all quick or all slow.
    - Formation bonus: if all alive members in same zone (≥2 alive), +1 Reactions.

    Args:
        assignments: Optional pre-set assignments (for human-in-the-loop).
            Keys are figure names OR fireteam IDs (e.g. "Fireteam Alpha").
            If None, auto-assigns optimally.
    """
    player_figs = [
        f for f in battlefield.figures
        if f.side == FigureSide.PLAYER and f.is_alive and f.can_act
    ]

    if not player_figs:
        return ReactionRollResult(
            dice_rolled=[], assignments={},
            quick_actors=[], slow_actors=[], log=["No player figures to activate"]
        )

    # Count scientists for bonus dice
    scientist_count = sum(
        1 for f in player_figs
        if f.char_class == "scientist" and f.is_active
    )

    # Build initiative units: individual figures + fireteam groups
    seen_fireteams: set[str] = set()
    # Each unit: (name_or_id, reactions, [figure_names])
    initiative_units: list[tuple[str, int, list[str]]] = []

    for f in player_figs:
        if f.fireteam_id:
            if f.fireteam_id not in seen_fireteams:
                seen_fireteams.add(f.fireteam_id)
                members = battlefield.get_fireteam_members(f.fireteam_id)
                member_names = [m.name for m in members if m.can_act]
                eff_reactions = _fireteam_effective_reactions(
                    battlefield, f.fireteam_id, f.reactions,
                )
                initiative_units.append((f.fireteam_id, eff_reactions, member_names))
        else:
            initiative_units.append((f.name, f.reactions, [f.name]))

    num_dice = len(initiative_units) + scientist_count

    # Roll dice
    roll_result = roll_nd6(num_dice, "Reaction roll")
    dice = sorted(roll_result.values)

    result = ReactionRollResult(
        dice_rolled=dice,
        assignments={},
        quick_actors=[],
        slow_actors=[],
    )
    result.log.append(f"Reaction roll: {dice} ({num_dice} dice, {scientist_count} scientist bonus)")

    # Log formation bonuses
    for ft_id in seen_fireteams:
        if battlefield.fireteam_in_formation(ft_id):
            result.log.append(f"  {ft_id}: in formation — Reactions +1")

    if assignments:
        # Use provided assignments — expand fireteam assignments to all members
        expanded: dict[str, int] = {}
        for key, die_val in assignments.items():
            # Check if key is a fireteam ID
            unit = next((u for u in initiative_units if u[0] == key), None)
            if unit:
                for member_name in unit[2]:
                    expanded[member_name] = die_val
            else:
                expanded[key] = die_val
        result.assignments = expanded
    else:
        # Auto-assign: greedily assign lowest dice to highest-reaction units
        units_by_reaction = sorted(initiative_units, key=lambda u: -u[1])
        available_dice = list(dice)

        for unit_name, reactions, member_names in units_by_reaction:
            if not available_dice:
                break
            # Find best die for this unit (lowest that qualifies for quick)
            best_die = None
            for d in available_dice:
                if d <= reactions:
                    best_die = d
                    break
            if best_die is not None:
                for name in member_names:
                    result.assignments[name] = best_die
                available_dice.remove(best_die)
            else:
                die_val = available_dice.pop(0)
                for name in member_names:
                    result.assignments[name] = die_val

    # Categorize into quick/slow per initiative unit
    for unit_name, reactions, member_names in initiative_units:
        die_val = result.assignments.get(member_names[0]) if member_names else None
        if die_val is not None and die_val <= reactions:
            result.quick_actors.extend(member_names)
            if len(member_names) > 1:
                result.log.append(
                    f"  {unit_name} ({len(member_names)} grunts): "
                    f"die {die_val} <= Reactions {reactions} -> QUICK"
                )
            else:
                result.log.append(
                    f"  {member_names[0]}: die {die_val} <= Reactions {reactions} -> QUICK"
                )
        else:
            result.slow_actors.extend(member_names)
            die_str = str(die_val) if die_val else "none"
            if len(member_names) > 1:
                result.log.append(
                    f"  {unit_name} ({len(member_names)} grunts): "
                    f"die {die_str} > Reactions {reactions} -> SLOW"
                )
            else:
                result.log.append(
                    f"  {member_names[0]}: die {die_str} > Reactions {reactions} -> SLOW"
                )

    return result


def _activate_contact(
    battlefield: Battlefield,
    contact: Figure,
    all_contacts: list[Figure],
    condition: object = None,
) -> ActivationResult | None:
    """Activate a single contact per rulebook rules.

    Roll 2D6: Aggression (red) and Random (white).
    - Aggression highest: move toward nearest player, distance = Aggression die inches
    - Random highest: move in random direction, distance = Random die inches
    - Equal: stay in place; if ≤2 contacts on table, spawn a new one adjacent

    Movement in inches → zones: each zone is 4", so die/4 rounded down (1-3=0, 4-6=1).
    """
    import random as rng

    aggression = roll_d6("Contact Aggression").total
    random_die = roll_d6("Contact Random").total

    # Apply aggression modifier from battlefield condition
    agg_mod = getattr(condition, "aggression_mod", 0)
    if agg_mod:
        aggression = max(1, min(6, aggression + agg_mod))

    log = [f"{contact.name} (contact): Aggression {aggression}{f' (mod {agg_mod:+d})' if agg_mod else ''}, Random {random_die}"]

    if aggression == random_die:
        # Equal — stay in place
        log.append(f"  Dice equal — {contact.name} remains in place.")
        # If ≤2 contacts on table, spawn a new contact adjacent
        alive_contacts = [c for c in all_contacts if c.is_alive]
        if len(alive_contacts) <= 2:
            adj = battlefield.adjacent_zones(*contact.zone)
            if adj:
                spawn_zone = rng.choice(adj)
                from planetfall.engine.combat.battlefield import _base_species_name
                _species = _base_species_name(contact.name)
                new_contact = Figure(
                    name=f"{_species} {len(battlefield.figures) + 1}",
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
                battlefield.figures.append(new_contact)
                all_contacts.append(new_contact)
                log.append(f"  New contact spawned at zone {spawn_zone}!")

        return ActivationResult(
            figure_name=contact.name,
            phase="enemy",
            action_type="hold",
            log=log,
        )

    if aggression > random_die:
        # Move toward nearest player
        move_zones = aggression // 4  # 1-3 = 0 zones, 4-6 = 1 zone
        if move_zones == 0:
            log.append(f"  Aggression highest but only {aggression}\" — not enough to cross a zone.")
            return ActivationResult(
                figure_name=contact.name,
                phase="enemy",
                action_type="hold",
                log=log,
            )
        move_to = find_move_toward_player(battlefield, contact)
        if move_to:
            contact.zone = move_to
            log.append(f"  Moves aggressively toward players → zone {move_to}")
            activation = ActivationResult(
                figure_name=contact.name,
                phase="enemy",
                action_type="move",
                log=log,
                moved_to=move_to,
            )
            # Check contact detection after movement (clear LoS = auto)
            detected = battlefield.detect_contacts_auto()
            for det in detected:
                reveal_log = battlefield.reveal_contact(det)
                activation.log.extend(reveal_log)
            return activation
        else:
            log.append(f"  Aggression highest but can't move closer.")
            return ActivationResult(
                figure_name=contact.name,
                phase="enemy",
                action_type="hold",
                log=log,
            )

    # Random highest — move in random direction
    move_zones = random_die // 4  # 1-3 = 0 zones, 4-6 = 1 zone
    if move_zones == 0:
        log.append(f"  Random highest but only {random_die}\" — not enough to cross a zone.")
        return ActivationResult(
            figure_name=contact.name,
            phase="enemy",
            action_type="hold",
            log=log,
        )

    # Pick a random adjacent zone (not impassable — handled by adjacent_zones)
    adj = battlefield.adjacent_zones(*contact.zone)
    if adj:
        # Contacts that would move off the edge halt in place
        # (adjacent_zones already filters out-of-bounds, so all are valid)
        move_to = rng.choice(adj)
        contact.zone = move_to
        log.append(f"  Moves randomly → zone {move_to}")
        activation = ActivationResult(
            figure_name=contact.name,
            phase="enemy",
            action_type="move",
            log=log,
            moved_to=move_to,
        )
        # Check contact detection after movement (clear LoS = auto)
        detected = battlefield.detect_contacts_auto()
        for det in detected:
            reveal_log = battlefield.reveal_contact(det)
            activation.log.extend(reveal_log)
        return activation
    else:
        log.append(f"  Random highest but no valid zone to move to.")
        return ActivationResult(
            figure_name=contact.name,
            phase="enemy",
            action_type="hold",
            log=log,
        )


def execute_enemy_phase(
    battlefield: Battlefield,
    use_ai_variations: bool = False,
    enemy_type: str = "tactical",
    condition: object = None,
) -> list[ActivationResult]:
    """Execute the enemy actions phase.

    All enemy figures act according to AI rules.

    Args:
        use_ai_variations: If True, roll on the AI Variation table before
            enemy activations (optional rule, p.31).
        enemy_type: "tactical" or "lifeform" — determines which ploy/action
            tables are used.
    """
    results = []

    # Optional AI variation roll
    if use_ai_variations:
        from planetfall.engine.combat.enemy_ai import roll_ai_variation
        variation = roll_ai_variation(battlefield, enemy_type)
        if variation.log:
            # Create a pseudo-activation for the variation result
            var_activation = ActivationResult(
                figure_name=variation.target_figure or "AI",
                phase="enemy",
                action_type="ai_variation",
                log=variation.log,
            )
            results.append(var_activation)

    # Contact movement per rulebook: roll 2D6 (Aggression + Random)
    contacts = [
        f for f in battlefield.figures
        if f.side == FigureSide.ENEMY and f.is_alive and f.is_contact
    ]
    for contact in contacts:
        activation = _activate_contact(battlefield, contact, contacts, condition=condition)
        if activation:
            results.append(activation)

    enemies = get_enemy_activation_order(battlefield)

    for enemy in enemies:
        if not enemy.is_alive or not enemy.can_act or enemy.is_contact:
            continue

        action = plan_enemy_action(battlefield, enemy, condition=condition)
        activation = ActivationResult(
            figure_name=enemy.name,
            phase="enemy",
            action_type=action.action_type,
            log=list(action.log),
        )

        # Execute the planned action
        if action.move_to and action.action_type in ("move", "move_and_shoot"):
            enemy.zone = action.move_to
            activation.moved_to = action.move_to

        if action.target_name and action.action_type in ("shoot", "move_and_shoot"):
            target = battlefield.get_figure_by_name(action.target_name)
            if target and target.is_alive:
                shooter_moved = action.move_to is not None
                shots = resolve_shooting_action(
                    battlefield, enemy, target, shooter_moved,
                    condition=condition,
                )
                activation.shot_results = shots
                for shot in shots:
                    activation.log.extend(shot.log)

        elif action.action_type == "brawl" and action.target_name:
            target = battlefield.get_figure_by_name(action.target_name)
            if target and target.is_alive:
                brawl = resolve_brawl(battlefield, enemy, target)
                activation.brawl_result = brawl
                activation.log.extend(brawl.log)

        # Remove stun marker after activation
        if enemy.stun_markers > 0:
            enemy.stun_markers = max(0, enemy.stun_markers - 1)

        enemy.has_acted = True
        results.append(activation)

    # End of Enemy Phase: detect obscured contacts (D6 4+ each)
    obscured_detected = battlefield.detect_contacts_obscured()
    if obscured_detected:
        detect_activation = ActivationResult(
            figure_name="Contacts",
            phase="enemy",
            action_type="detection",
            log=["--- End-of-phase contact detection ---"],
        )
        for det in obscured_detected:
            reveal_log = battlefield.reveal_contact(det)
            detect_activation.log.extend(reveal_log)
        results.append(detect_activation)

    return results


def execute_player_activation(
    battlefield: Battlefield,
    figure: Figure,
    action_type: str,
    move_to: tuple[int, int] | None = None,
    target_name: str | None = None,
    phase: str = "quick",
    use_aid: bool = False,
    condition: object = None,
) -> ActivationResult:
    """Execute a player figure's activation.

    This is called by the human-in-the-loop system after the player
    chooses their action.
    """
    activation = ActivationResult(
        figure_name=figure.name,
        phase=phase,
        action_type=action_type,
    )

    shooter_moved = False

    # Handle shoot_and_move (Flexible Combat Training — scouts shoot then move)
    if action_type == "shoot_and_move":
        # Shoot first from current position (not moving yet)
        if target_name:
            target = battlefield.get_figure_by_name(target_name)
            if target and target.is_alive:
                shots = resolve_shooting_action(
                    battlefield, figure, target, False,  # shooting before moving
                    condition=condition,
                )
                activation.shot_results = shots
                for shot in shots:
                    activation.log.extend(shot.log)
        # Then move
        if move_to:
            figure.zone = move_to
            activation.moved_to = move_to
            activation.log.append(f"{figure.name} relocates to zone {move_to}")

    else:
        # Handle movement for any action type (except shoot_and_move handled above)
        if move_to:
            figure.zone = move_to
            activation.moved_to = move_to
            shooter_moved = True
            if action_type == "rush":
                activation.log.append(f"{figure.name} dashes to zone {move_to}")
            else:
                activation.log.append(f"{figure.name} moves to zone {move_to}")

        # Consume aid marker if spending it
        aid_bonus = 0
        if use_aid and figure.aid_marker:
            figure.aid_marker = False
            aid_bonus = 1
            activation.log.append(f"{figure.name} spends Aid marker (+1 bonus)")

        # Handle shooting
        if target_name and action_type in ("shoot", "move_and_shoot"):
            target = battlefield.get_figure_by_name(target_name)
            if target and target.is_alive:
                # Temporarily apply aid bonus to hit
                figure.hit_bonus += aid_bonus
                shots = resolve_shooting_action(
                    battlefield, figure, target, shooter_moved,
                    condition=condition,
                )
                figure.hit_bonus -= aid_bonus
                activation.shot_results = shots
                for shot in shots:
                    activation.log.extend(shot.log)

        # Handle brawling
        elif action_type == "brawl" and target_name:
            target = battlefield.get_figure_by_name(target_name)
            if target and target.is_alive:
                brawl = resolve_brawl(
                    battlefield, figure, target, attacker_bonus=aid_bonus,
                )
                activation.brawl_result = brawl
                activation.log.extend(brawl.log)

        # Handle aid — place aid marker on ally
        elif action_type == "aid_marker" and target_name:
            target = battlefield.get_figure_by_name(target_name)
            if target and target.zone == figure.zone and not target.aid_marker:
                target.aid_marker = True
                activation.log.append(
                    f"{figure.name} aids {target.name}: Aid marker placed"
                )

        # Handle aid — remove stun from ally
        elif action_type == "aid_stun" and target_name:
            target = battlefield.get_figure_by_name(target_name)
            if target and target.zone == figure.zone and target.stun_markers > 0:
                target.stun_markers -= 1
                activation.log.append(
                    f"{figure.name} aids {target.name}: "
                    f"removed 1 stun marker ({target.stun_markers} remaining)"
                )

        # Handle leave battlefield
        elif action_type == "leave_battlefield":
            activation.log.append(f"{figure.name} leaves the battlefield")

        # Handle free escape (Clear Escape Paths condition)
        elif action_type == "free_escape":
            activation.log.append(
                f"{figure.name} escapes the battlefield (Clear Escape Paths)"
            )

    # Unstable terrain check — D6=1 when moving onto unstable zone
    if move_to and getattr(condition, "terrain_unstable", False):
        dest_zone = battlefield.get_zone(*move_to)
        if getattr(dest_zone, "unstable", False):
            collapse_roll = roll_d6("Unstable terrain").total
            if collapse_roll == 1:
                figure.status = FigureStatus.SPRAWLING
                activation.log.append(
                    f"Unstable terrain! {figure.name} rolls {collapse_roll} — ground collapses, Sprawling!"
                )
            else:
                activation.log.append(
                    f"Unstable terrain: {figure.name} rolls {collapse_roll} — safe"
                )

    # Remove stun marker after activation
    if figure.stun_markers > 0:
        figure.stun_markers = max(0, figure.stun_markers - 1)

    # Sprawling figures stand up
    if figure.status == FigureStatus.SPRAWLING:
        figure.status = FigureStatus.ACTIVE
        activation.log.append(f"{figure.name} stands up from sprawling")

    figure.has_acted = True
    return activation


def check_panic(
    battlefield: Battlefield,
    casualties_this_round: list[str],
) -> PanicResult | None:
    """Check if enemies panic after taking casualties.

    Only applies to tactical enemies with a panic range > 0.
    """
    if not casualties_this_round:
        return None

    # Find an enemy with a panic range
    enemies = [
        f for f in battlefield.figures
        if f.side == FigureSide.ENEMY and f.is_alive and f.panic_range > 0
    ]
    if not enemies:
        return None

    panic_range = enemies[0].panic_range  # All enemies in a group share panic range
    roll = roll_d6("Panic check")

    result = PanicResult(
        roll=roll.total,
        panic_range=panic_range,
        panicked=roll.total <= panic_range,
    )

    if result.panicked:
        # Find casualty location (use first casualty's last known zone)
        # Remove the enemy figure furthest from player edge (row 2)
        eligible = sorted(enemies, key=lambda f: f.zone[0])  # lowest row = furthest
        if eligible:
            fled = eligible[0]
            fled.status = FigureStatus.CASUALTY
            result.fled_figure = fled.name
            result.log.append(
                f"Panic! Roll {roll.total} <= {panic_range}: "
                f"{fled.name} flees the battlefield!"
            )
        else:
            result.log.append(f"Panic! But no eligible figures to flee")
    else:
        result.log.append(
            f"Panic check: {roll.total} vs {panic_range} -> No panic"
        )

    return result


def reset_round(battlefield: Battlefield):
    """Reset per-round state at the start of a new round."""
    for fig in battlefield.figures:
        fig.has_acted = False


def get_round_casualties(
    battlefield: Battlefield,
    pre_round_figures: list[str],
) -> list[str]:
    """Get names of figures that became casualties this round."""
    current_alive = {f.name for f in battlefield.figures if f.is_alive}
    return [name for name in pre_round_figures if name not in current_alive]


def check_battle_end(battlefield: Battlefield) -> str | None:
    """Check if the battle should end.

    Returns:
        "player_victory" if all enemies eliminated.
        "player_defeat" if all player figures eliminated.
        None if battle continues.
    """
    player_alive = any(
        f for f in battlefield.figures
        if f.side == FigureSide.PLAYER and f.is_alive
    )
    enemy_alive = any(
        f for f in battlefield.figures
        if f.side == FigureSide.ENEMY and f.is_alive
    )

    if not enemy_alive:
        return "player_victory"
    if not player_alive:
        return "player_defeat"
    return None

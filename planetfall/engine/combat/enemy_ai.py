"""Deterministic enemy AI for Planetfall combat.

Enemy behavior rules:
- Target selection: highest hit probability, then closest to player edge
- Movement: advance toward closest player figure, prefer cover
- Specialists act first, then others closest-to-farthest from player edge
"""

from __future__ import annotations

from dataclasses import dataclass, field

from planetfall.engine.combat.battlefield import (
    Battlefield, Figure, FigureSide, FigureStatus, TerrainType,
    zone_range_inches,
)
from planetfall.engine.combat.shooting import get_hit_target
from planetfall.engine.dice import roll_d6


@dataclass
class AIAction:
    """A planned action for an enemy figure."""
    figure_name: str
    action_type: str = "hold"  # "move_and_shoot", "shoot", "move", "brawl", "move_to_cover", "hold"
    move_to: tuple[int, int] | None = None
    target_name: str | None = None
    log: list[str] = field(default_factory=list)


def get_enemy_activation_order(battlefield: Battlefield) -> list[Figure]:
    """Get enemy figures in activation order.

    Rules (p.30): "activates all specialists first, then activates all
    remaining figures. In both cases, activate the enemies closest to the
    player's battlefield edge first."

    Leaders are NOT a separate tier — they activate with remaining figures
    unless they are also specialists.
    """
    enemies = [
        f for f in battlefield.figures
        if f.side == FigureSide.ENEMY and f.is_alive
    ]

    specialists = [f for f in enemies if f.is_specialist]
    remaining = [f for f in enemies if not f.is_specialist]

    # Sort each group: closest to player edge first (highest row number)
    def by_player_proximity(fig: Figure) -> tuple[int, int]:
        return (-fig.zone[0], fig.zone[1])  # higher row = closer to player

    specialists.sort(key=by_player_proximity)
    remaining.sort(key=by_player_proximity)

    return specialists + remaining


def find_best_target(
    battlefield: Battlefield,
    shooter: Figure,
    shooter_moved: bool = False,
) -> Figure | None:
    """Find the best target for an enemy shooter.

    Priority: highest hit probability, then closest to player edge.
    """
    player_figs = [
        f for f in battlefield.figures
        if f.side == FigureSide.PLAYER and f.is_alive
    ]
    if not player_figs:
        return None

    best_target = None
    best_score = (999, 999)  # (hit_needed, -row)  lower is better

    for target in player_figs:
        hit_needed = get_hit_target(battlefield, shooter, target, shooter_moved)
        if hit_needed > 6:
            continue  # out of range
        # Prefer lower hit_needed, then targets closer to player edge (higher row)
        score = (hit_needed, -target.zone[0])
        if score < best_score:
            best_score = score
            best_target = target

    return best_target


def find_move_toward_player(
    battlefield: Battlefield,
    figure: Figure,
) -> tuple[int, int] | None:
    """Find the best zone to move toward the closest player figure.

    Prefers cover zones. Moves toward player edge (higher row numbers).
    Speed 7+ enemies can move up to 2 zones.
    """
    from planetfall.engine.combat.battlefield import move_zones

    player_figs = [
        f for f in battlefield.figures
        if f.side == FigureSide.PLAYER and f.is_alive
    ]
    if not player_figs:
        return None

    # Find closest player figure
    closest = min(
        player_figs,
        key=lambda p: battlefield.zone_distance(figure.zone, p.zone),
    )

    # Determine move range based on Speed
    num_move = move_zones(figure.speed)

    # Build candidate zones (adjacent for Speed 1-6, up to 2 away for Speed 7+)
    if num_move >= 2:
        candidates = []
        for dr in range(-num_move, num_move + 1):
            for dc in range(-num_move, num_move + 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = figure.zone[0] + dr, figure.zone[1] + dc
                if (0 <= nr < battlefield.rows and 0 <= nc < battlefield.cols
                        and max(abs(dr), abs(dc)) <= num_move):
                    terrain = battlefield.get_zone(nr, nc).terrain
                    if terrain != TerrainType.IMPASSABLE:
                        candidates.append((nr, nc))
    else:
        candidates = list(battlefield.adjacent_zones(*figure.zone))

    if not candidates:
        return None

    # Score each candidate zone
    best_zone = None
    best_score = (999, 0)  # (distance_to_target, -has_cover)

    for zone in candidates:
        # Respect stacking limit
        if not battlefield.zone_has_capacity(*zone, figure.side):
            continue
        # Contacts limited to 1 per zone
        if figure.is_contact:
            has_contact = any(
                f for f in battlefield.figures
                if f.zone == zone and f.is_contact and f.is_alive and f is not figure
            )
            if has_contact:
                continue
        dist = battlefield.zone_distance(zone, closest.zone)
        has_cover = battlefield.has_cover(zone)
        score = (dist, 0 if has_cover else 1)
        if score < best_score:
            best_score = score
            best_zone = zone

    # Only move if it gets us closer
    current_dist = battlefield.zone_distance(figure.zone, closest.zone)
    if best_zone and best_score[0] < current_dist:
        return best_zone

    # If we can't get closer, try to move to cover
    if not battlefield.has_cover(figure.zone):
        for zone in candidates:
            if battlefield.has_cover(zone) and battlefield.zone_has_capacity(*zone, figure.side):
                return zone

    return None


def find_cover_retreat(
    battlefield: Battlefield,
    figure: Figure,
) -> tuple[int, int] | None:
    """Find a cover zone to retreat to (for stunned enemies with no target)."""
    adjacent = battlefield.adjacent_zones(*figure.zone)
    for zone in adjacent:
        if battlefield.has_cover(zone) and battlefield.zone_has_capacity(*zone, figure.side):
            return zone
    return None


def plan_enemy_action(
    battlefield: Battlefield,
    figure: Figure,
) -> AIAction:
    """Plan the action for a single enemy figure.

    Stunned enemies: move OR attack (not both).
    Active enemies: move + attack.
    Sprawling enemies: stand up (lose action).
    """
    action = AIAction(figure_name=figure.name)

    # Sleeper rapid fire: don't move, fire with +1 shot
    if "rapid_fire" in figure.special_rules:
        target = find_best_target(battlefield, figure, shooter_moved=False)
        if target:
            action.action_type = "shoot"
            action.target_name = target.name
            action.log.append(
                f"{figure.name} [RAPID FIRE] fires at {target.name} (+1 shot)"
            )
            # rapid_fire is consumed by shooting code after resolving
            return action
        else:
            # No target visible — leave rapid fire mode
            figure.special_rules.remove("rapid_fire")
            action.action_type = "hold"
            action.log.append(
                f"{figure.name} exits Rapid Fire — no targets visible"
            )
            return action

    # Sprawling: stand up, no action
    if figure.status == FigureStatus.SPRAWLING:
        figure.status = FigureStatus.ACTIVE
        action.action_type = "stand_up"
        action.log.append(f"{figure.name} stands up from sprawling")
        return action

    is_stunned = figure.stun_markers > 0

    # Check if we can shoot from current position
    target = find_best_target(battlefield, figure, shooter_moved=False)

    if is_stunned:
        # Stunned: move OR attack, not both
        if target:
            # Can shoot: stay and shoot
            action.action_type = "shoot"
            action.target_name = target.name
            action.log.append(
                f"{figure.name} (stunned) fires at {target.name}"
            )
        else:
            # No target: move to cover or toward player
            move_to = find_cover_retreat(battlefield, figure)
            if not move_to:
                move_to = find_move_toward_player(battlefield, figure)
            if move_to:
                action.action_type = "move"
                action.move_to = move_to
                action.log.append(
                    f"{figure.name} (stunned) moves to {move_to}"
                )
            else:
                action.action_type = "hold"
                action.log.append(f"{figure.name} (stunned) holds position")
    else:
        # Active: move + attack
        # Check if moving gets a better shot
        move_to = find_move_toward_player(battlefield, figure)

        if target and not move_to:
            # Have target, no need to move
            action.action_type = "shoot"
            action.target_name = target.name
            action.log.append(f"{figure.name} fires at {target.name}")
        elif move_to:
            action.move_to = move_to
            # Check if we can shoot after moving
            old_zone = figure.zone
            figure.zone = move_to
            target_after = find_best_target(battlefield, figure, shooter_moved=True)
            figure.zone = old_zone  # restore

            if target_after:
                action.action_type = "move_and_shoot"
                action.target_name = target_after.name
                action.log.append(
                    f"{figure.name} moves to {move_to} and fires at {target_after.name}"
                )
            else:
                action.action_type = "move"
                action.log.append(f"{figure.name} moves to {move_to}")
        elif target:
            action.action_type = "shoot"
            action.target_name = target.name
            action.log.append(f"{figure.name} fires at {target.name}")
        else:
            # No target, no useful move — check for brawl opportunity
            # Move toward closest player figure
            player_figs = [
                f for f in battlefield.figures
                if f.side == FigureSide.PLAYER and f.is_alive
            ]
            if player_figs:
                closest = min(
                    player_figs,
                    key=lambda p: battlefield.zone_distance(figure.zone, p.zone),
                )
                if battlefield.zone_distance(figure.zone, closest.zone) == 0:
                    # Same zone — brawl!
                    action.action_type = "brawl"
                    action.target_name = closest.name
                    action.log.append(
                        f"{figure.name} charges into brawl with {closest.name}"
                    )
                else:
                    general_move = find_move_toward_player(battlefield, figure)
                    if general_move:
                        action.action_type = "move"
                        action.move_to = general_move
                        action.log.append(f"{figure.name} advances to {general_move}")
                    else:
                        action.action_type = "hold"
                        action.log.append(f"{figure.name} holds position")
            else:
                action.action_type = "hold"
                action.log.append(f"{figure.name} holds position")

    return action


# --- AI Variation Tables (optional, rules p.31-33) ---
# D6 AI VARIATION: 1 = Ploy, 2-4 = Nothing, 5-6 = AI Action


TACTICAL_PLOYS = {
    1: {
        "id": "redeploy",
        "description": "Moved to nearest terrain feature at highest point.",
    },
    2: {
        "id": "take_charge",
        "description": "Next Panic die rolled by enemy side is ignored.",
    },
    3: {
        "id": "recovery",
        "description": "Removes all Stun and Sprawling markers, activates normally.",
        "requires_stunned": True,
    },
    4: {
        "id": "reinforcements",
        "description": "An additional enemy with basic weapons arrives at enemy edge center.",
    },
    5: {
        "id": "reinforcements",
        "description": "An additional enemy with basic weapons arrives at enemy edge center.",
    },
    6: {
        "id": "concentrated_attack",
        "description": "All enemies that can see a player character fire on them with +1 hit bonus.",
    },
}

TACTICAL_AI_ACTIONS = {
    1: {
        "id": "hold_position",
        "description": "Remains in place and defends current position for the rest of battle. Moves to cover if in the open.",
    },
    2: {
        "id": "hesitate",
        "description": "Does not act this phase unless opponents within 6\", in which case fires in place.",
    },
    3: {
        "id": "brief_halt",
        "description": "Does not move this phase but may fire normally.",
    },
    4: {
        "id": "brief_halt",
        "description": "Does not move this phase but may fire normally.",
    },
    5: {
        "id": "advance",
        "description": "Moves toward nearest terrain feature closer to player edge, rushing if needed.",
    },
    6: {
        "id": "group_up",
        "description": "Moves toward nearest ally. If already close, sticks with them.",
    },
}

LIFEFORM_PLOYS = {
    1: {
        "id": "call_for_more",
        "description": "Remains in place; next activation, an additional enemy appears within 1\".",
    },
    2: {
        "id": "hide",
        "description": "Removed from table; a Contact is placed in nearest terrain feature.",
    },
    3: {
        "id": "frenzy",
        "description": "Removes all Stun/Sprawling, moves at full speed toward nearest opponent for brawl.",
    },
    4: {
        "id": "lurk",
        "description": "Does not activate this phase; -1 hit penalty until next activation.",
    },
    5: {
        "id": "flanking_attack",
        "description": "Additional Contact placed at center of random battlefield edge.",
    },
    6: {
        "id": "flanking_attack",
        "description": "Additional Contact placed at center of random battlefield edge.",
    },
}

LIFEFORM_AI_ACTIONS = {
    1: {
        "id": "focus",
        "description": "Picks a visible opponent; moves toward and tries to kill them for the rest of battle.",
    },
    2: {
        "id": "hesitate",
        "description": "Takes no actions this round but recovers if Stunned/Sprawling.",
    },
    3: {
        "id": "move_to_cover",
        "description": "Moves to closest terrain feature with cover; stays if already in cover.",
    },
    4: {
        "id": "move_to_cover",
        "description": "Moves to closest terrain feature with cover; stays if already in cover.",
    },
    5: {
        "id": "move_to_flank",
        "description": "Moves toward nearest neutral battlefield edge, staying out of sight or in cover.",
    },
    6: {
        "id": "move_to_flank",
        "description": "Moves toward nearest neutral battlefield edge, staying out of sight or in cover.",
    },
}


@dataclass
class AIVariationResult:
    """Result of rolling on the AI Variation table."""
    variation_roll: int
    variation_type: str  # "nothing", "ploy", "ai_action"
    sub_roll: int = 0
    entry: dict = field(default_factory=dict)
    target_figure: str = ""
    log: list[str] = field(default_factory=list)


def roll_ai_variation(
    battlefield: Battlefield,
    enemy_type: str = "tactical",
) -> AIVariationResult:
    """Roll on the AI Variation table (optional rule, p.31).

    D6: 1 = Roll on Ploy table, 2-4 = Nothing, 5-6 = Roll on AI Action table.
    Separate tables for Tactical Enemies and Lifeforms.

    Args:
        enemy_type: "tactical" or "lifeform"

    Returns:
        AIVariationResult describing what happens.
    """
    import random

    variation_roll = roll_d6("AI Variation").total

    result = AIVariationResult(variation_roll=variation_roll, variation_type="nothing")

    if variation_roll == 1:
        result.variation_type = "ploy"
        ploy_table = TACTICAL_PLOYS if enemy_type == "tactical" else LIFEFORM_PLOYS
        sub_roll = roll_d6("Ploy").total
        result.sub_roll = sub_roll
        entry = ploy_table.get(sub_roll, {"id": "nothing", "description": "No effect."})
        result.entry = entry

        # Select random target enemy
        enemies = [f for f in battlefield.figures if f.side == FigureSide.ENEMY and f.is_alive]
        if enemies:
            target = random.choice(enemies)
            result.target_figure = target.name
            _apply_ploy(battlefield, target, entry, result)

        result.log.append(
            f"AI Variation: Ploy! D6={sub_roll} — {entry['id'].replace('_', ' ').title()}: "
            f"{entry['description']}"
        )

    elif variation_roll >= 5:
        result.variation_type = "ai_action"
        action_table = TACTICAL_AI_ACTIONS if enemy_type == "tactical" else LIFEFORM_AI_ACTIONS
        sub_roll = roll_d6("AI Action").total
        result.sub_roll = sub_roll
        entry = action_table.get(sub_roll, {"id": "nothing", "description": "No effect."})
        result.entry = entry

        # Select random target enemy
        enemies = [f for f in battlefield.figures if f.side == FigureSide.ENEMY and f.is_alive]
        if enemies:
            target = random.choice(enemies)
            result.target_figure = target.name
            _apply_ai_action(battlefield, target, entry, result)

        result.log.append(
            f"AI Variation: Action! D6={sub_roll} — {entry['id'].replace('_', ' ').title()}: "
            f"{entry['description']}"
        )

    else:
        result.log.append(f"AI Variation: D6={variation_roll} — Nothing happens.")

    return result


def _apply_ploy(
    battlefield: Battlefield,
    target: Figure,
    entry: dict,
    result: AIVariationResult,
):
    """Apply a ploy effect to the target figure."""
    ploy_id = entry["id"]

    if ploy_id == "redeploy":
        for zone in battlefield.adjacent_zones(*target.zone):
            if battlefield.has_cover(zone):
                target.zone = zone
                result.log.append(f"  {target.name} redeployed to {zone}")
                break

    elif ploy_id == "recovery":
        if target.stun_markers > 0 or target.status == FigureStatus.SPRAWLING:
            target.stun_markers = 0
            if target.status == FigureStatus.SPRAWLING:
                target.status = FigureStatus.ACTIVE
            result.log.append(f"  {target.name} recovers — stun/sprawling cleared")
        else:
            result.log.append(f"  {target.name} not stunned/sprawling — no effect")

    elif ploy_id == "reinforcements":
        new_enemy = Figure(
            name=f"Reinforcement {len(battlefield.figures)+1}",
            side=FigureSide.ENEMY,
            zone=(0, battlefield.cols // 2),
            combat_skill=0,
            toughness=3,
            weapon_name="Basic Weapon",
            weapon_range=18,
            weapon_shots=1,
            char_class="enemy",
            panic_range=1,
        )
        battlefield.figures.append(new_enemy)
        result.log.append(f"  Reinforcement arrives at enemy edge!")

    elif ploy_id == "concentrated_attack":
        for enemy in battlefield.figures:
            if enemy.side == FigureSide.ENEMY and enemy.is_alive:
                enemy.hit_bonus += 1
        result.log.append(f"  All enemies gain +1 hit bonus this phase!")

    elif ploy_id == "frenzy":
        target.stun_markers = 0
        if target.status == FigureStatus.SPRAWLING:
            target.status = FigureStatus.ACTIVE
        move_to = find_move_toward_player(battlefield, target)
        if move_to:
            target.zone = move_to
        result.log.append(f"  {target.name} enters frenzy — clears stun, charges!")

    elif ploy_id == "lurk":
        target.special_rules.append("lurking")
        result.log.append(f"  {target.name} lurks — -1 hit penalty until next activation")


def _apply_ai_action(
    battlefield: Battlefield,
    target: Figure,
    entry: dict,
    result: AIVariationResult,
):
    """Apply an AI action effect to the target figure."""
    action_id = entry["id"]

    if action_id == "hold_position":
        if not battlefield.has_cover(target.zone):
            for zone in battlefield.adjacent_zones(*target.zone):
                if battlefield.has_cover(zone):
                    target.zone = zone
                    result.log.append(f"  {target.name} holds — moved to cover at {zone}")
                    break
            else:
                result.log.append(f"  {target.name} holds position (no cover nearby)")
        else:
            result.log.append(f"  {target.name} holds position in cover")
        target.special_rules.append("holding_position")

    elif action_id == "hesitate":
        target.has_acted = True
        result.log.append(f"  {target.name} hesitates — no action this phase")

    elif action_id == "brief_halt":
        result.log.append(f"  {target.name} halts but may fire")

    elif action_id == "advance":
        move_to = find_move_toward_player(battlefield, target)
        if move_to:
            target.zone = move_to
            result.log.append(f"  {target.name} advances to {move_to}")
        else:
            result.log.append(f"  {target.name} cannot advance further")

    elif action_id == "group_up":
        allies = [
            f for f in battlefield.figures
            if f.side == FigureSide.ENEMY and f.is_alive and f.name != target.name
        ]
        if allies:
            closest_ally = min(
                allies,
                key=lambda a: battlefield.zone_distance(target.zone, a.zone),
            )
            if battlefield.zone_distance(target.zone, closest_ally.zone) > 0:
                for zone in battlefield.adjacent_zones(*target.zone):
                    if battlefield.zone_distance(zone, closest_ally.zone) < \
                       battlefield.zone_distance(target.zone, closest_ally.zone):
                        target.zone = zone
                        break
            result.log.append(f"  {target.name} groups up with {closest_ally.name}")
        else:
            result.log.append(f"  {target.name} has no allies to group with")

    elif action_id == "focus":
        players = [f for f in battlefield.figures if f.side == FigureSide.PLAYER and f.is_alive]
        if players:
            focus_target = min(
                players,
                key=lambda p: battlefield.zone_distance(target.zone, p.zone),
            )
            target.special_rules.append(f"focus:{focus_target.name}")
            result.log.append(f"  {target.name} focuses on {focus_target.name}")

    elif action_id == "move_to_cover":
        if not battlefield.has_cover(target.zone):
            cover_zone = find_cover_retreat(battlefield, target)
            if cover_zone:
                target.zone = cover_zone
                result.log.append(f"  {target.name} moves to cover at {cover_zone}")
            else:
                result.log.append(f"  {target.name} — no cover available")
        else:
            result.log.append(f"  {target.name} already in cover — stays put")

    elif action_id == "move_to_flank":
        adj = battlefield.adjacent_zones(*target.zone)
        edge_zones = [z for z in adj if z[1] == 0 or z[1] == battlefield.cols - 1]
        if edge_zones:
            target.zone = edge_zones[0]
            result.log.append(f"  {target.name} flanks to {target.zone}")
        else:
            result.log.append(f"  {target.name} cannot flank")

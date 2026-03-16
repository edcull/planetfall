"""Beacons (Scout) initial mission — deploy 3 beacons on raised ground."""

from __future__ import annotations

import random
from typing import Any

from planetfall.engine.combat.battlefield import (
    Battlefield, Figure, FigureSide, FigureStatus, TerrainType,
    generate_random_terrain, GRID_SMALL,
)
from planetfall.engine.combat.missions import _create_player_figure
from planetfall.engine.dice import roll_d6
from planetfall.engine.models import GameState, CharacterClass

from planetfall.engine.combat.initial_missions.base import _get_chars_by_class


# ---------------------------------------------------------------------------
# Beacons Mission (Scout)
# ---------------------------------------------------------------------------

def _setup_beacons(state: GameState) -> tuple[Battlefield, list[str]]:
    """Set up the Beacons mission battlefield.

    Returns (battlefield, log_lines).
    """
    rows, cols = GRID_SMALL
    zones = generate_random_terrain(rows, cols)

    # Ensure at least 3 high_ground zones for beacons — upgrade some if needed
    high_ground = [
        (r, c) for r in range(rows) for c in range(cols)
        if zones[r][c].terrain == TerrainType.HIGH_GROUND
    ]
    # Exclude edge rows (deployment zones)
    interior_hg = [(r, c) for r, c in high_ground if 0 < r < rows - 1]

    # If fewer than 3 interior high ground, upgrade some terrain zones
    while len(interior_hg) < 3:
        candidates = [
            (r, c) for r in range(1, rows - 1) for c in range(cols)
            if zones[r][c].terrain != TerrainType.HIGH_GROUND
            and (r, c) not in interior_hg
        ]
        if not candidates:
            break
        pick = random.choice(candidates)
        zones[pick[0]][pick[1]].terrain = TerrainType.HIGH_GROUND
        interior_hg.append(pick)

    # Pick 3 well-distributed beacon locations (one per column third)
    # Divide the map into 3 column bands: left, center, right
    third = max(1, cols // 3)
    bands = [
        [z for z in interior_hg if z[1] < third],
        [z for z in interior_hg if third <= z[1] < 2 * third],
        [z for z in interior_hg if z[1] >= 2 * third],
    ]
    beacon_zones: list[tuple[int, int]] = []
    # Pick one from each band if available
    for band in bands:
        if band and len(beacon_zones) < 3:
            beacon_zones.append(random.choice(band))
    # Fill remaining from unused zones
    if len(beacon_zones) < 3:
        remaining = [z for z in interior_hg if z not in beacon_zones]
        random.shuffle(remaining)
        for z in remaining:
            if len(beacon_zones) >= 3:
                break
            # Ensure minimum distance of 2 (Chebyshev) from existing beacons
            if all(max(abs(z[0] - b[0]), abs(z[1] - b[1])) >= 2 for b in beacon_zones):
                beacon_zones.append(z)
        # Last resort: just fill if distance constraint can't be met
        if len(beacon_zones) < 3:
            for z in remaining:
                if z not in beacon_zones and len(beacon_zones) < 3:
                    beacon_zones.append(z)
    for r, c in beacon_zones:
        zones[r][c].has_objective = True
        zones[r][c].objective_label = "BCN"

    bf = Battlefield(zones=zones, rows=rows, cols=cols)

    # Deploy scouts on bottom edge
    scouts = _get_chars_by_class(state, CharacterClass.SCOUT)
    log = []
    if not scouts:
        log.append("WARNING: No scouts on roster! Mission cannot be played.")
        return bf, log

    player_row = rows - 1
    for i, char in enumerate(scouts):
        col = min(i + 1, cols - 1)
        fig = _create_player_figure(
            name=char.name,
            char_class="scout",
            speed=char.speed,
            combat_skill=char.combat_skill,
            toughness=char.toughness,
            reactions=char.reactions,
            savvy=char.savvy,
            zone=(player_row, col),
        )
        bf.figures.append(fig)

    log.append(f"Deployed {len(scouts)} scout(s) on southern edge")
    log.append(f"3 Beacon locations marked on raised ground (BCN)")
    log.append("Objective: Move a scout to each Beacon location and end activation there")
    return bf, log


def _spawn_storm(bf: Battlefield) -> list[str]:
    """Spawn a storm cluster at the center of the battlefield (max 5)."""
    storms = [f for f in bf.figures if f.char_class == "storm"]
    if len(storms) >= 5:
        return []

    center_r, center_c = bf.rows // 2, bf.cols // 2
    storm_num = len(storms) + 1
    storm = Figure(
        name=f"Storm {storm_num}",
        side=FigureSide.ENEMY,
        zone=(center_r, center_c),
        speed=0,
        combat_skill=0,
        toughness=99,
        char_class="storm",
        weapon_name="Lightning",
        weapon_range=0,
        weapon_shots=0,
        weapon_damage=0,
        special_rules=["storm_cluster"],
    )
    bf.figures.append(storm)
    return [f"Storm cluster spawns at center ({center_r},{center_c})"]


def _move_storms(bf: Battlefield) -> list[str]:
    """Move all storm clusters 1D6\" in a random direction."""
    log = []
    directions = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    storms = [f for f in bf.figures if f.char_class == "storm" and f.is_alive]

    for storm in storms:
        roll = roll_d6(f"{storm.name} movement")
        # 1-4 = 1 zone, 5-6 = 2 zones
        move_zones = 1 if roll.total <= 4 else 2
        direction = random.choice(directions)

        r, c = storm.zone
        new_r = r + direction[0] * move_zones
        new_c = c + direction[1] * move_zones

        # Check if storm leaves the table
        if new_r < 0 or new_r >= bf.rows or new_c < 0 or new_c >= bf.cols:
            bf.figures.remove(storm)
            log.append(f"{storm.name} drifts off the table — removed")
        else:
            storm.zone = (new_r, new_c)
            log.append(f"{storm.name} moves to ({new_r},{new_c})")

    return log


def _storm_damage(bf: Battlefield) -> list[str]:
    """Check if any storms are in the same zone as scouts; deal +0 damage."""
    log = []
    storms = [f for f in bf.figures if f.char_class == "storm" and f.is_alive]
    scouts = [f for f in bf.figures if f.side == FigureSide.PLAYER and f.is_alive]

    for storm in storms:
        for scout in scouts:
            if scout.zone == storm.zone and scout.is_alive:
                damage_roll = roll_d6(f"Storm damage vs {scout.name}")
                damage_total = damage_roll.total + 0  # +0 damage
                if damage_total > scout.toughness:
                    scout.status = FigureStatus.CASUALTY
                    log.append(
                        f"Storm hits {scout.name}! Damage {damage_roll.total}+0={damage_total} "
                        f"vs Toughness {scout.toughness} -> CASUALTY"
                    )
                elif damage_total == scout.toughness:
                    scout.status = FigureStatus.SPRAWLING
                    log.append(
                        f"Storm hits {scout.name}! Damage {damage_roll.total}+0={damage_total} "
                        f"vs Toughness {scout.toughness} -> Sprawling"
                    )
                else:
                    scout.stun_markers = min(scout.stun_markers + 1, 3)
                    log.append(
                        f"Storm hits {scout.name}! Damage {damage_roll.total}+0={damage_total} "
                        f"vs Toughness {scout.toughness} -> Stunned"
                    )
    return log


def run_beacons(state: GameState) -> dict:
    """Run the Beacons (Scout) mission.

    Returns {"victory": bool, "log": list[str]}.
    """
    from planetfall.cli import display, prompts

    bf, log = _setup_beacons(state)
    scouts = [f for f in bf.figures if f.side == FigureSide.PLAYER]
    if not scouts:
        return {"victory": False, "log": log}

    display.console.print("\n[bold cyan]═══ BEACONS — Scout Mission ═══[/bold cyan]")
    display.console.print(
        "\n  Scouts must deploy beacons on 3 raised ground locations."
        "\n  Storm clusters spawn each round at the center and drift randomly."
        "\n  A storm in your zone deals a +0 Damage hit.\n"
    )

    beacons_deployed: set[tuple[int, int]] = set()
    beacon_zones = [
        (z.row, z.col) for row in bf.zones for z in row if z.has_objective
    ]
    max_rounds = 12

    display.reset_enemy_labels()
    display.print_battlefield(bf, title="Beacons — Deployment")
    prompts.pause()

    for round_num in range(1, max_rounds + 1):
        # --- Player Phase: move each scout ---
        display.clear_screen()
        display.print_battlefield(bf, title=f"Beacons — Round {round_num}")
        display.console.print(
            f"\n  [bold]Round {round_num}[/bold] — "
            f"Beacons deployed: {len(beacons_deployed)}/3"
        )

        alive_scouts = [f for f in bf.figures if f.side == FigureSide.PLAYER and f.is_alive]
        if not alive_scouts:
            log.append("All scouts are casualties — mission failed!")
            break

        for scout in alive_scouts:
            # Recovery: sprawling -> active at start of activation
            if scout.status == FigureStatus.SPRAWLING:
                scout.status = FigureStatus.ACTIVE
                log.append(f"{scout.name} recovers from sprawling")
            if scout.status == FigureStatus.STUNNED:
                scout.stun_markers = max(0, scout.stun_markers - 1)
                if scout.stun_markers == 0:
                    scout.status = FigureStatus.ACTIVE

            from planetfall.engine.combat.battlefield import (
                move_zones as calc_move_zones,
                rush_available,
                rush_total_zones,
            )
            num_move = calc_move_zones(scout.speed)
            # Scouts use jump jets (straight-line movement)
            move_options = bf.jump_destinations(*scout.zone, num_move) if num_move > 0 else []
            # Build action choices
            action_choices = [f"Stay at ({scout.zone[0]},{scout.zone[1]})"]
            for z in move_options:
                terrain = bf.get_zone(z[0], z[1]).terrain.value
                bcn_tag = " [BCN]" if z in beacon_zones and z not in beacons_deployed else ""
                deployed_tag = " [DEPLOYED]" if z in beacons_deployed else ""
                action_choices.append(f"Move to ({z[0]},{z[1]}) [{terrain}]{bcn_tag}{deployed_tag}")

            # Rush option (uses action — no beacon deploy after rush)
            if rush_available(scout.speed):
                rush_reach = rush_total_zones(scout.speed)
                rush_options = bf.jump_destinations(*scout.zone, rush_reach)
                rush_only = [z for z in rush_options if z not in move_options and z != scout.zone]
                for z in rush_only:
                    terrain = bf.get_zone(z[0], z[1]).terrain.value
                    bcn_tag = " [BCN]" if z in beacon_zones and z not in beacons_deployed else ""
                    action_choices.append(f"Rush to ({z[0]},{z[1]}) [{terrain}]{bcn_tag} (no action)")

            # Overlay toggle loop
            overlay_modes = [
                display.OVERLAY_VISION, display.OVERLAY_MOVEMENT,
                display.OVERLAY_SHOOTING,
            ]
            overlay_names = ["Vision", "Movement", "Shooting"]
            overlay_idx = 0
            while True:
                display.clear_screen()
                display.reset_enemy_labels()
                display.print_battlefield(
                    bf, title=f"Beacons — Round {round_num}",
                    active_fig=scout,
                    overlay_mode=overlay_modes[overlay_idx],
                )
                display.console.print(
                    f"\n  [bold]Round {round_num}[/bold] — "
                    f"Beacons deployed: {len(beacons_deployed)}/3"
                )
                display.console.print(
                    f"\n  [bold green]{scout.name}[/bold green] at ({scout.zone[0]},{scout.zone[1]})"
                )
                next_name = overlay_names[(overlay_idx + 1) % len(overlay_names)]
                cycle_label = f"[Overlay: {overlay_names[overlay_idx]} → {next_name}]"
                all_choices = action_choices + [cycle_label]
                choice = prompts.ask_select(f"{scout.name} action:", all_choices)
                if choice == cycle_label:
                    overlay_idx = (overlay_idx + 1) % len(overlay_modes)
                    continue
                break

            used_rush = choice.startswith("Rush")
            if choice.startswith("Stay"):
                pass  # stays in place
            else:
                # Parse zone from choice
                import re
                match = re.search(r"\((\d+),(\d+)\)", choice)
                if match:
                    new_zone = (int(match.group(1)), int(match.group(2)))
                    scout.zone = new_zone
                    label = "rushes" if used_rush else "moves"
                    log.append(f"{scout.name} {label} to ({new_zone[0]},{new_zone[1]})")

            # Check beacon deployment (not available after Rush — uses action)
            if not used_rush and scout.zone in beacon_zones and scout.zone not in beacons_deployed:
                beacons_deployed.add(scout.zone)
                # Mark as deployed on the zone
                z = bf.get_zone(scout.zone[0], scout.zone[1])
                z.objective_label = "BCN✓"
                log.append(f"BEACON DEPLOYED at ({scout.zone[0]},{scout.zone[1]}) by {scout.name}!")
                display.console.print(
                    f"  [bold green]BEACON DEPLOYED![/bold green] ({len(beacons_deployed)}/3)"
                )

        # Check immediate victory
        if len(beacons_deployed) >= 3:
            log.append("All 3 beacons deployed — mission complete!")
            break

        # --- Enemy Phase: spawn and move storms ---
        storm_log = _spawn_storm(bf)
        storm_log.extend(_move_storms(bf))
        damage_log = _storm_damage(bf)
        storm_log.extend(damage_log)

        if storm_log:
            display.clear_screen()
            display.print_battlefield(bf, title=f"Beacons — Round {round_num} (Storms)")
            display.print_combat_log(storm_log)
            log.extend(storm_log)
            prompts.pause()

    victory = len(beacons_deployed) >= 3

    display.clear_screen()
    if victory:
        display.console.print("\n[bold green]═══ BEACONS — MISSION SUCCESS ═══[/bold green]")
        display.console.print("  All 3 beacons deployed! +2 Raw Materials bonus.")
    else:
        display.console.print("\n[bold red]═══ BEACONS — MISSION FAILED ═══[/bold red]")
        display.console.print("  A second wave of scouts completes the job. No bonus.")
    prompts.pause()

    return {"victory": victory, "log": log}


def run_beacons_ui(state: GameState, ui: Any) -> dict:
    """Run the Beacons (Scout) mission using a UIAdapter.

    Returns {"victory": bool, "log": list[str]}.
    """
    from planetfall.orchestrator_steps import _get_move_zones, _get_dash_zones

    bf, log = _setup_beacons(state)
    scouts = [f for f in bf.figures if f.side == FigureSide.PLAYER]
    if not scouts:
        return {"victory": False, "log": log}

    beacons_deployed: set[tuple[int, int]] = set()
    beacon_zones = [
        (z.row, z.col) for row in bf.zones for z in row if z.has_objective
    ]
    max_rounds = 12

    ui.reset_enemy_labels()

    # Mission intro modal
    ui.show_mission_intro({
        "title": "Beacons (Scout Mission)",
        "subtitle": "Initial Landing Mission 1 of 3",
        "sections": [
            {"heading": "", "body": (
                "The first to land are the scouts, establishing the beacons "
                "required for the rest of the colonization fleet to begin deploying. "
                "The scouts must brave terrible storms to complete their mission."
            )},
            {"heading": "Setup", "body": (
                "◆ Place 3 Beacon locations on any raised ground on the table.\n"
                "◆ Randomly determine which battlefield edge you will set up near "
                "and deploy any scouts from your roster within 1\"."
            )},
            {"heading": "Objective", "body": (
                "The scouts must move to each of the Beacon locations. "
                "When a scout is on a Beacon location, use the \"Set up Beacon\" action to deploy it. "
                "Scouts may choose to act before or after moving. "
                "Once a Beacon is deployed on each location, the mission is completed."
            )},
            {"heading": "Obstacles", "body": (
                "At the start of each Enemy Phase, a storm cluster spawns at the center "
                "of the table unless there are currently 5 storm clusters on the table. "
                "Each storm cluster moves 1D6\" in a random direction during the Enemy Phase. "
                "Any that leave the table are removed.\n"
                "A scout that is contacted by a storm cluster as it moves takes a +0 Damage hit."
            )},
            {"heading": "Reward", "body": (
                "If you place all 3 Beacons successfully, the mission ends immediately "
                "and when you establish your colony, you receive 2 units of Raw Materials as a bonus.\n"
                "If the mission is a failure, you do not receive the bonus but may still proceed "
                "to the next mission, as a second wave of scouts succeeds."
            )},
        ],
    })

    # Mission briefing (persistent info panel)
    ui.show_mission_briefing(
        bf,
        mission_type="Beacons",
        enemy_info=["Storm clusters spawn at center each round and drift randomly"],
        special_rules=[],
        victory_conditions=["Deploy all 3 beacons on raised ground"],
        defeat_conditions=["All scouts eliminated", "12 rounds elapsed"],
        enemy_type="storm",
    )

    for round_num in range(1, max_rounds + 1):
        alive_scouts = [f for f in bf.figures if f.side == FigureSide.PLAYER and f.is_alive]
        if not alive_scouts:
            log.append("All scouts are casualties — mission failed!")
            break

        ui.clear()
        ui.show_combat_phase("beacons_round", round_num)
        ui.show_battlefield(bf)
        ui.message(
            f"Round {round_num} — Beacons deployed: {len(beacons_deployed)}/3",
            style="bold",
        )

        for scout in alive_scouts:
            # Recovery
            if scout.status == FigureStatus.SPRAWLING:
                scout.status = FigureStatus.ACTIVE
                log.append(f"{scout.name} recovers from sprawling")
            if scout.status == FigureStatus.STUNNED:
                scout.stun_markers = max(0, scout.stun_markers - 1)
                if scout.stun_markers == 0:
                    scout.status = FigureStatus.ACTIVE

            action_used = False
            action_first = False

            # Check if scout is already on an undeployed beacon
            sr, sc = scout.zone
            can_beacon_here = (
                any(sr == br and sc == bc for br, bc in beacon_zones)
                and not any(sr == dr and sc == dc for dr, dc in beacons_deployed)
            )

            # Movement phase — offer "action first" if on a beacon
            move_zones = _get_move_zones(bf, scout)
            dash_zones = _get_dash_zones(bf, scout)

            result = ui.prompt_movement(
                bf, scout,
                move_zones=move_zones,
                dash_zones=dash_zones,
                can_scout_first=can_beacon_here,
                overlay_mode=ui.OVERLAY_MOVEMENT,
            )

            move_type = result.get("type", "stay")
            dashed = False

            if move_type == "scout_first":
                # Action before movement — show action choices
                action_first = True
                action_used = True
                on_beacon = any(sr == br and sc == bc for br, bc in beacon_zones)
                already_deployed = any(sr == dr and sc == dc for dr, dc in beacons_deployed)
                if on_beacon and not already_deployed:
                    ui.show_battlefield(bf, active_fig=scout)
                    action = ui.select(f"{scout.name} — Action:", ["Set up Beacon", "Hold"])
                    if action == "Set up Beacon":
                        beacons_deployed.add((sr, sc))
                        z = bf.get_zone(sr, sc)
                        z.objective_label = "BCN✓"
                        log.append(f"BEACON DEPLOYED at ({sr},{sc}) by {scout.name}!")
                        ui.show_battlefield(bf)
                        ui.show_combat_log([
                            f"BEACON DEPLOYED at ({sr},{sc}) by {scout.name}! "
                            f"({len(beacons_deployed)}/3)",
                        ])
                    else:
                        ui.show_combat_log([f"{scout.name} holds position."])
                else:
                    ui.show_combat_log([f"{scout.name} holds position (no beacon here)."])

                # Skip movement if mission just completed
                if len(beacons_deployed) >= 3:
                    break

                # Now do movement (no dash since action used)
                move_zones = _get_move_zones(bf, scout)
                result = ui.prompt_movement(
                    bf, scout,
                    move_zones=move_zones,
                    dash_zones=[],
                    overlay_mode=ui.OVERLAY_MOVEMENT,
                )
                move_type = result.get("type", "stay")
                if move_type == "move":
                    idx = result["zone_idx"]
                    new_zone = move_zones[idx][0]
                    scout.zone = (new_zone[0], new_zone[1])
                    log.append(f"{scout.name} moves to ({new_zone[0]},{new_zone[1]})")

            elif move_type == "move":
                idx = result["zone_idx"]
                new_zone = move_zones[idx][0]
                scout.zone = (new_zone[0], new_zone[1])
                log.append(f"{scout.name} moves to ({new_zone[0]},{new_zone[1]})")
            elif move_type == "dash":
                dashed = True
                idx = result["zone_idx"]
                new_zone = dash_zones[idx][0]
                scout.zone = (new_zone[0], new_zone[1])
                log.append(f"{scout.name} dashes to ({new_zone[0]},{new_zone[1]})")

            # Action phase after movement (if not already used)
            if not action_used and not dashed:
                sr, sc = scout.zone
                on_beacon = any(sr == br and sc == bc for br, bc in beacon_zones)
                already_deployed = any(sr == dr and sc == dc for dr, dc in beacons_deployed)

                if on_beacon and not already_deployed:
                    ui.show_battlefield(bf, active_fig=scout)
                    action = ui.select(
                        f"{scout.name} — Action:", ["Set up Beacon", "Hold"],
                    )
                    if action == "Set up Beacon":
                        beacons_deployed.add((sr, sc))
                        z = bf.get_zone(sr, sc)
                        z.objective_label = "BCN✓"
                        log.append(f"BEACON DEPLOYED at ({sr},{sc}) by {scout.name}!")
                        ui.show_battlefield(bf)
                        ui.show_combat_log([
                            f"BEACON DEPLOYED at ({sr},{sc}) by {scout.name}! "
                            f"({len(beacons_deployed)}/3)",
                        ])

            # Break inner loop if all beacons deployed
            if len(beacons_deployed) >= 3:
                break

        # Check immediate victory
        if len(beacons_deployed) >= 3:
            log.append("All 3 beacons deployed — mission complete!")
            break

        # Enemy Phase: spawn and move storms
        storm_log = _spawn_storm(bf)
        storm_log.extend(_move_storms(bf))
        damage_log = _storm_damage(bf)
        storm_log.extend(damage_log)

        if storm_log:
            ui.clear()
            ui.show_battlefield(bf)
            ui.show_combat_log(storm_log)
            log.extend(storm_log)
            ui.pause()

    victory = len(beacons_deployed) >= 3

    ui.show_battlefield(bf)
    if victory:
        ui.show_mission_result(
            success=True,
            title="BEACONS — MISSION SUCCESS",
            detail="All 3 beacons deployed! +2 Raw Materials bonus.",
        )
    else:
        ui.show_mission_result(
            success=False,
            title="BEACONS — MISSION FAILED",
            detail="A second wave of scouts completes the job. No bonus.",
        )

    return {"victory": victory, "log": log}

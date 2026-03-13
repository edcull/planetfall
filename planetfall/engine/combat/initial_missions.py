"""Initial Planetfall missions — three tutorial missions before the campaign begins.

Beacons (Scout Mission):
    Scouts deploy 3 beacons on raised ground while avoiding storm clusters.
    Reward: +2 Raw Materials on success.

Analysis (Scientist Mission):
    Scientists uncover 4+ of 6 contacts. Contacts move away each round.
    Reward: +2 Research Points (+3 if all 6 revealed) on success.

Perimeter (Trooper Mission):
    Troopers kill 6 melee lifeforms using full combat rules.
    Reward: +3 Colony Morale on success.

All missions use a 6x6 (2'x2') table. Casualties don't require injury rolls.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from planetfall.engine.combat.battlefield import (
    Battlefield, Figure, FigureSide, FigureStatus, Zone, TerrainType,
    generate_random_terrain, GRID_SMALL, ZONE_INCHES,
)
from planetfall.engine.combat.missions import (
    MissionSetup, _create_player_figure,
)
from planetfall.engine.combat.session import CombatSession, CombatPhase
from planetfall.engine.dice import roll_d6
from planetfall.engine.models import (
    GameState, MissionType, Character, CharacterClass,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_chars_by_class(state: GameState, cls: CharacterClass) -> list[Character]:
    """Get all characters of a given class."""
    return [c for c in state.characters if c.char_class == cls]


def _random_edge(rows: int, cols: int) -> tuple[str, int]:
    """Pick a random edge and return (edge_name, edge_row).

    Returns the player deployment row index for the chosen edge.
    Row 0 = top (enemy edge default), last row = bottom (player edge default).
    We pick randomly and set player edge accordingly.
    """
    edge = random.choice(["top", "bottom", "left", "right"])
    # For simplicity, always use bottom row as player edge
    # (the grid is symmetrical enough for tutorial missions)
    return "bottom", rows - 1


def _zones_within_range(
    origin: tuple[int, int], max_zones: int, rows: int, cols: int,
) -> list[tuple[int, int]]:
    """All zones within max_zones Chebyshev distance of origin."""
    r0, c0 = origin
    result = []
    for r in range(rows):
        for c in range(cols):
            dist = max(abs(r - r0), abs(c - c0))
            if 0 < dist <= max_zones:
                result.append((r, c))
    return result


def _adjacent_zones(
    origin: tuple[int, int], rows: int, cols: int,
) -> list[tuple[int, int]]:
    """All 8-connected adjacent zones (within 1)."""
    return _zones_within_range(origin, 1, rows, cols)


def _chebyshev(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


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
        # 1-3 = 1 zone, 4-5 = 1 zone, 6 = 2 zones
        move_zones = 1 if roll.total <= 5 else 2
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


# ---------------------------------------------------------------------------
# Analysis Mission (Scientist)
# ---------------------------------------------------------------------------

def _setup_analysis(state: GameState) -> tuple[Battlefield, list[str]]:
    """Set up the Analysis mission battlefield."""
    rows, cols = GRID_SMALL
    zones = generate_random_terrain(rows, cols)
    bf = Battlefield(zones=zones, rows=rows, cols=cols)

    # Place 6 contacts evenly around the table
    # Spread across rows 1-4, various columns
    contact_positions = [
        (1, 1), (1, 4), (2, 2), (2, 4), (3, 1), (3, 3),
    ]
    # Shuffle to add variety
    random.shuffle(contact_positions)
    contact_positions = contact_positions[:6]

    for i, pos in enumerate(contact_positions):
        contact = Figure(
            name=f"Contact {i + 1}",
            side=FigureSide.ENEMY,
            zone=pos,
            speed=0,
            combat_skill=0,
            toughness=99,
            char_class="contact",
            weapon_name="",
            weapon_range=0,
            weapon_shots=0,
            weapon_damage=0,
            is_contact=True,
        )
        bf.figures.append(contact)

    # Deploy scientists on bottom edge
    scientists = _get_chars_by_class(state, CharacterClass.SCIENTIST)
    log = []
    if not scientists:
        log.append("WARNING: No scientists on roster!")
        return bf, log

    player_row = rows - 1
    for i, char in enumerate(scientists):
        col = min(i + 1, cols - 1)
        fig = _create_player_figure(
            name=char.name,
            char_class="scientist",
            speed=char.speed,
            combat_skill=char.combat_skill,
            toughness=char.toughness,
            reactions=char.reactions,
            savvy=char.savvy,
            zone=(player_row, col),
        )
        bf.figures.append(fig)

    log.append(f"Deployed {len(scientists)} scientist(s) on southern edge")
    log.append("6 Contacts placed around the table")
    log.append("Objective: Reveal at least 4 Contacts (end activation within 2 zones)")
    return bf, log


def _move_contacts_away(bf: Battlefield) -> list[str]:
    """Move contacts using the contact movement system (flee variant).

    Roll 2D6 per contact — Flee die and Random die:
    - Flee highest: move 1 zone away from nearest scientist (die must be 4+)
    - Random highest: move 1 zone in random direction (die must be 4+)
    - Equal: remain in place
    Contacts that move off the table edge are removed.
    """
    log = []
    contacts = [f for f in bf.figures if f.char_class == "contact" and f.is_alive]
    scientists = [f for f in bf.figures if f.side == FigureSide.PLAYER and f.is_alive]

    if not scientists:
        return log

    for contact in contacts:
        flee_die = roll_d6("Contact Flee").total
        random_die = roll_d6("Contact Random").total

        entry = f"{contact.name}: Flee {flee_die}, Random {random_die}"

        if flee_die == random_die:
            log.append(f"{entry} — remains in place")
            continue

        if flee_die > random_die:
            # Flee: move away from nearest scientist
            if flee_die < 4:
                log.append(f"{entry} — not enough to cross a zone")
                continue
            nearest = min(scientists, key=lambda s: _chebyshev(s.zone, contact.zone))
            dr = contact.zone[0] - nearest.zone[0]
            dc = contact.zone[1] - nearest.zone[1]
            dr = (1 if dr > 0 else (-1 if dr < 0 else 0))
            dc = (1 if dc > 0 else (-1 if dc < 0 else 0))
            if dr == 0 and dc == 0:
                dr, dc = random.choice([(-1, 0), (1, 0), (0, -1), (0, 1)])
            new_r = contact.zone[0] + dr
            new_c = contact.zone[1] + dc
        else:
            # Random: move in random direction
            if random_die < 4:
                log.append(f"{entry} — not enough to cross a zone")
                continue
            adj = bf.adjacent_zones(*contact.zone)
            if adj:
                new_r, new_c = random.choice(adj)
            else:
                log.append(f"{entry} — no valid zone to move to")
                continue

        if new_r < 0 or new_r >= bf.rows or new_c < 0 or new_c >= bf.cols:
            bf.figures.remove(contact)
            log.append(f"{entry} — flees off the table!")
        else:
            contact.zone = (new_r, new_c)
            log.append(f"{entry} — moves to ({new_r},{new_c})")

    return log


def run_analysis(state: GameState) -> dict:
    """Run the Analysis (Scientist) mission.

    Returns {"victory": bool, "contacts_revealed": int, "log": list[str]}.
    """
    from planetfall.cli import display, prompts

    bf, log = _setup_analysis(state)
    scientists = [f for f in bf.figures if f.side == FigureSide.PLAYER]
    if not scientists:
        return {"victory": False, "contacts_revealed": 0, "log": log}

    display.console.print("\n[bold cyan]═══ ANALYSIS — Scientist Mission ═══[/bold cyan]")
    display.console.print(
        "\n  Scientists must uncover at least 4 of 6 Contacts."
        "\n  End your activation within 2 zones of a Contact to reveal (remove) it."
        "\n  Contacts flee away from scientists each round."
        "\n  Contacts that leave the table count against you.\n"
    )

    contacts_revealed = 0
    contacts_fled = 0
    max_rounds = 10

    display.reset_enemy_labels()
    display.print_battlefield(bf, title="Analysis — Deployment")
    prompts.pause()

    for round_num in range(1, max_rounds + 1):
        remaining_contacts = [
            f for f in bf.figures if f.char_class == "contact" and f.is_alive
        ]
        if not remaining_contacts:
            break

        alive_scientists = [f for f in bf.figures if f.side == FigureSide.PLAYER and f.is_alive]
        if not alive_scientists:
            log.append("No scientists remaining — mission over")
            break

        for sci in alive_scientists:
            from planetfall.engine.combat.battlefield import (
                move_zones as calc_move_zones,
                rush_available,
                rush_total_zones,
            )
            num_move = calc_move_zones(sci.speed)
            move_options = _zones_within_range(
                sci.zone, num_move, bf.rows, bf.cols,
            ) if num_move > 0 else []
            action_choices = [f"Stay at ({sci.zone[0]},{sci.zone[1]})"]
            for z in move_options:
                terrain = bf.get_zone(z[0], z[1]).terrain.value
                # Check if any contacts are near this zone
                nearby_contacts = sum(
                    1 for ct in remaining_contacts
                    if _chebyshev(z, ct.zone) <= 2
                )
                near_tag = f" [{nearby_contacts} contacts in range]" if nearby_contacts > 0 else ""
                action_choices.append(f"Move to ({z[0]},{z[1]}) [{terrain}]{near_tag}")

            # Rush option
            if rush_available(sci.speed):
                rush_reach = rush_total_zones(sci.speed)
                rush_options = _zones_within_range(
                    sci.zone, rush_reach, bf.rows, bf.cols,
                )
                rush_only = [z for z in rush_options if z not in move_options and z != sci.zone]
                for z in rush_only:
                    terrain = bf.get_zone(z[0], z[1]).terrain.value
                    nearby_contacts = sum(
                        1 for ct in remaining_contacts
                        if _chebyshev(z, ct.zone) <= 2
                    )
                    near_tag = f" [{nearby_contacts} contacts in range]" if nearby_contacts > 0 else ""
                    action_choices.append(f"Rush to ({z[0]},{z[1]}) [{terrain}]{near_tag} (no action)")

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
                    bf, title=f"Analysis — Round {round_num}",
                    active_fig=sci,
                    overlay_mode=overlay_modes[overlay_idx],
                )
                display.console.print(
                    f"\n  [bold]Round {round_num}[/bold] — "
                    f"Revealed: {contacts_revealed} | Fled: {contacts_fled} | "
                    f"Remaining: {len(remaining_contacts)}"
                )
                display.console.print(
                    f"\n  [bold green]{sci.name}[/bold green] at ({sci.zone[0]},{sci.zone[1]})"
                )
                next_name = overlay_names[(overlay_idx + 1) % len(overlay_names)]
                cycle_label = f"[Overlay: {overlay_names[overlay_idx]} → {next_name}]"
                all_choices = action_choices + [cycle_label]
                choice = prompts.ask_select(f"{sci.name} action:", all_choices)
                if choice == cycle_label:
                    overlay_idx = (overlay_idx + 1) % len(overlay_modes)
                    continue
                break

            if not choice.startswith("Stay"):
                import re
                match = re.search(r"\((\d+),(\d+)\)", choice)
                if match:
                    sci.zone = (int(match.group(1)), int(match.group(2)))

            # Check for reveals — contacts within 2 zones
            remaining_contacts = [
                f for f in bf.figures if f.char_class == "contact" and f.is_alive
            ]
            for contact in remaining_contacts[:]:
                if _chebyshev(sci.zone, contact.zone) <= 2:
                    bf.figures.remove(contact)
                    contacts_revealed += 1
                    log.append(f"{sci.name} reveals {contact.name}!")
                    display.console.print(
                        f"  [bold green]CONTACT REVEALED![/bold green] "
                        f"({contacts_revealed} total)"
                    )

        # Check victory
        remaining_contacts = [
            f for f in bf.figures if f.char_class == "contact" and f.is_alive
        ]
        if contacts_revealed >= 4 and not remaining_contacts:
            break
        if contacts_revealed >= 4:
            # Can keep going to try for all 6
            if remaining_contacts:
                keep_going = prompts.ask_confirm(
                    f"4+ contacts revealed! Continue to try for all 6? "
                    f"({len(remaining_contacts)} remaining)",
                    default=True,
                )
                if not keep_going:
                    break

        if not remaining_contacts:
            break

        # --- Enemy Phase: contacts flee ---
        contact_log = _move_contacts_away(bf)
        fled_this_round = sum(1 for l in contact_log if "flees off" in l)
        contacts_fled += fled_this_round

        if contact_log:
            display.clear_screen()
            display.print_battlefield(bf, title=f"Analysis — Round {round_num} (Contact Movement)")
            display.print_combat_log(contact_log)
            log.extend(contact_log)
            prompts.pause()

    victory = contacts_revealed >= 4

    display.clear_screen()
    if victory:
        rp_bonus = 3 if contacts_revealed >= 6 else 2
        display.console.print("\n[bold green]═══ ANALYSIS — MISSION SUCCESS ═══[/bold green]")
        display.console.print(
            f"  {contacts_revealed} contacts revealed! +{rp_bonus} Research Points bonus."
        )
    else:
        display.console.print("\n[bold red]═══ ANALYSIS — MISSION FAILED ═══[/bold red]")
        display.console.print(
            f"  Only {contacts_revealed} contacts revealed (needed 4). No bonus."
        )
    prompts.pause()

    return {"victory": victory, "contacts_revealed": contacts_revealed, "log": log}


# ---------------------------------------------------------------------------
# Perimeter Mission (Trooper) — uses full combat session
# ---------------------------------------------------------------------------

def _setup_perimeter(state: GameState) -> MissionSetup:
    """Set up the Perimeter mission — full combat with 6 melee lifeforms."""
    rows, cols = GRID_SMALL
    zones = generate_random_terrain(rows, cols)
    bf = Battlefield(zones=zones, rows=rows, cols=cols)

    # Deploy troopers — they can set up anywhere, we'll let the player choose later
    # For now place them at center-bottom area
    troopers = _get_chars_by_class(state, CharacterClass.TROOPER)
    player_row = rows - 1
    for i, char in enumerate(troopers):
        col = min(i + 1, cols - 1)
        fig = _create_player_figure(
            name=char.name,
            char_class="trooper",
            speed=char.speed,
            combat_skill=char.combat_skill,
            toughness=char.toughness,
            reactions=char.reactions,
            savvy=char.savvy,
            weapon_name="Trooper Rifle",
            weapon_range=30,
            weapon_shots=1,
            weapon_damage=0,
            weapon_traits=["trooper", "ap_ammo"],
            zone=(player_row, col),
        )
        bf.figures.append(fig)

    # Deploy 6 lifeforms on random edge (top edge = row 0)
    enemy_edge = 0
    for i in range(6):
        col = i % cols
        fig = Figure(
            name=f"Lifeform {i + 1}",
            side=FigureSide.ENEMY,
            zone=(enemy_edge, col),
            speed=5,
            combat_skill=1,
            toughness=4,
            melee_damage=0,  # +0 Damage
            weapon_name="Claws",
            weapon_range=0,  # melee only
            weapon_shots=0,
            weapon_damage=0,
            weapon_traits=[],
            panic_range=0,  # not subject to panic
            char_class="lifeform",
            special_rules=["no_panic"],
        )
        bf.figures.append(fig)

    setup = MissionSetup(
        mission_type=MissionType.HUNT,  # closest existing type
        battlefield=bf,
        max_rounds=8,
        victory_conditions=["Kill all 6 lifeforms"],
        defeat_conditions=["All troopers eliminated"],
        special_rules=[
            "Lifeforms move directly toward nearest trooper for brawling",
            "Lifeforms: Speed 5\", CS +1, Toughness 4, +0 Damage (melee)",
            "No injury rolls for casualties in this tutorial mission",
        ],
        enemy_type="lifeform",
    )
    return setup


def run_perimeter(state: GameState) -> dict:
    """Run the Perimeter (Trooper) mission using full combat session.

    Returns {"victory": bool, "log": list[str]}.
    """
    from planetfall.engine.combat.battlefield import FigureSide
    from planetfall.cli import display, prompts
    from planetfall.engine.models import TurnEvent, TurnEventType

    troopers = _get_chars_by_class(state, CharacterClass.TROOPER)
    if not troopers:
        display.console.print("[red]No troopers on roster! Cannot play Perimeter mission.[/red]")
        return {"victory": False, "log": ["No troopers available"]}

    display.console.print("\n[bold cyan]═══ PERIMETER — Trooper Mission ═══[/bold cyan]")
    display.console.print(
        "\n  Troopers must kill all 6 lifeforms heading toward the drop site."
        "\n  Each trooper is armed with a standard Trooper Rifle."
        "\n  Lifeforms: Speed 5\", CS +1, Toughness 4, +0 Damage (brawling)."
        "\n  Full combat rules apply — this is your combat tutorial.\n"
    )

    mission_setup = _setup_perimeter(state)
    bf = mission_setup.battlefield

    # Let player choose deployment zones
    player_figs = [f for f in bf.figures if f.side == FigureSide.PLAYER]
    available_zones = [
        (r, c) for r in range(bf.rows) for c in range(bf.cols)
    ]  # Can set up anywhere

    display.reset_enemy_labels()
    display.print_battlefield(bf, title="Perimeter — Deployment")

    # Show special rules
    display.console.print("[bold yellow]Special Rules:[/bold yellow]")
    for rule in mission_setup.special_rules:
        display.console.print(f"  [yellow]• {rule}[/yellow]")
    display.console.print()

    zone_assignments = prompts.prompt_deployment_zones(
        [f.name for f in player_figs],
        available_zones,
    )
    for fig in player_figs:
        if fig.name in zone_assignments:
            fig.zone = zone_assignments[fig.name]

    # Run full combat session
    session = CombatSession(mission_setup)
    combat_state = session.start_battle()
    display.print_battlefield(session.bf)

    prev_log_len = 0
    log = []

    while combat_state.phase.value != "battle_over":
        current_phase = combat_state.phase.value

        if current_phase == "reaction_roll":
            display.clear_screen()
            display.print_battlefield(session.bf)
            display.print_combat_phase(current_phase, combat_state.round_number)

            display.console.print(
                f"\n  [bold]Reaction Dice:[/bold] {combat_state.unassigned_dice}"
            )
            for name, react in combat_state.reaction_figures:
                display.console.print(f"    {name} (Reactions {react})")

            assignments = prompts.prompt_reaction_assignment(
                combat_state.unassigned_dice,
                combat_state.reaction_figures,
            )
            combat_state = session.assign_reactions(assignments)

            if combat_state.reaction_result:
                display.print_reaction_roll(combat_state.reaction_result)
                prompts.pause()

            prev_log_len = len(combat_state.phase_log)
            continue

        if combat_state.available_actions:
            active_fig = next(
                (f for f in session.bf.figures
                 if f.name == combat_state.current_figure),
                None,
            )

            overlay_modes_p = [
                display.OVERLAY_VISION, display.OVERLAY_MOVEMENT,
                display.OVERLAY_SHOOTING,
            ]
            overlay_names_p = ["Vision", "Movement", "Shooting"]
            overlay_idx_p = 0
            action_descs = [a["description"] for a in combat_state.available_actions]

            while True:
                display.clear_screen()
                display.print_battlefield(
                    session.bf, active_fig=active_fig,
                    overlay_mode=overlay_modes_p[overlay_idx_p],
                )
                display.print_combat_phase(current_phase, combat_state.round_number)

                new_entries = combat_state.phase_log[prev_log_len:]
                if new_entries:
                    display.print_combat_log(new_entries)

                display.console.print(
                    f"\n  [bold]Current figure: {combat_state.current_figure}[/bold]"
                )

                next_name_p = overlay_names_p[(overlay_idx_p + 1) % len(overlay_names_p)]
                cycle_label_p = f"[Overlay: {overlay_names_p[overlay_idx_p]} → {next_name_p}]"
                all_choices = action_descs + [cycle_label_p]
                choice = prompts.ask_select("Choose action:", all_choices)
                if choice == cycle_label_p:
                    overlay_idx_p = (overlay_idx_p + 1) % len(overlay_modes_p)
                    continue
                break

            action_idx = action_descs.index(choice)
            combat_state = session.choose_action(action_idx)

            new_log = combat_state.phase_log[prev_log_len:]
            if new_log:
                display.clear_screen()
                display.print_battlefield(session.bf)
                display.print_combat_phase(current_phase, combat_state.round_number)
                display.print_combat_log(new_log)
                prompts.pause()
            prev_log_len = len(combat_state.phase_log)

        elif current_phase == "enemy_phase":
            display.clear_screen()
            display.print_battlefield(session.bf)
            display.print_combat_phase(current_phase, combat_state.round_number)

            while combat_state.phase.value == "enemy_phase":
                pre_step_len = len(combat_state.phase_log)
                combat_state = session.advance_enemy_step()
                new_log = combat_state.phase_log[pre_step_len:]
                substantive = [l for l in new_log if not l.startswith("---") and not l.startswith("===")]
                if substantive:
                    display.clear_screen()
                    display.print_battlefield(session.bf)
                    display.print_combat_phase(current_phase, combat_state.round_number)
                    display.print_combat_log(substantive)
                    prompts.pause()

            prev_log_len = len(combat_state.phase_log)
        else:
            pre_len = len(combat_state.phase_log)
            combat_state = session.advance()
            new_log = combat_state.phase_log[pre_len:]
            substantive = [l for l in new_log if not l.startswith("---") and not l.startswith("===")]
            if substantive:
                display.clear_screen()
                display.print_battlefield(session.bf)
                display.print_combat_phase(combat_state.phase.value, combat_state.round_number)
                display.print_combat_log(substantive)
                prompts.pause()
            prev_log_len = len(combat_state.phase_log)

    final_result = session.get_result()
    victory = final_result.get("victory", False)

    display.clear_screen()
    if victory:
        display.console.print("\n[bold green]═══ PERIMETER — MISSION SUCCESS ═══[/bold green]")
        display.console.print("  All 6 lifeforms eliminated! +3 Colony Morale bonus.")
    else:
        display.console.print("\n[bold red]═══ PERIMETER — MISSION FAILED ═══[/bold red]")
        display.console.print("  Troopers evacuated. A grunt squad clears the site. No bonus.")
    prompts.pause()

    return {"victory": victory, "log": log}


# ---------------------------------------------------------------------------
# Main runner — plays all 3 missions in sequence
# ---------------------------------------------------------------------------

MISSION_ORDER = [
    ("Beacons (Scout Mission)", "beacons"),
    ("Analysis (Scientist Mission)", "analysis"),
    ("Perimeter (Trooper Mission)", "perimeter"),
]


def run_initial_missions(state: GameState) -> None:
    """Run the 3 initial Planetfall missions, apply rewards, mark complete."""
    from planetfall.cli import display, prompts
    from planetfall.engine.persistence import save_state

    display.clear_screen()
    display.console.print("\n[bold cyan]╔══════════════════════════════════════════╗[/bold cyan]")
    display.console.print("[bold cyan]║         PLANETFALL — LANDING SITE        ║[/bold cyan]")
    display.console.print("[bold cyan]╚══════════════════════════════════════════╝[/bold cyan]")
    display.console.print(
        "\n  Before the campaign begins, you must establish the landing site"
        "\n  by playing through three initial missions:\n"
    )
    for label, _ in MISSION_ORDER:
        display.console.print(f"    • {label}")
    display.console.print(
        "\n  Casualties during initial missions do not require injury rolls."
        "\n  You may play these in any order.\n"
    )

    # Offer skip options
    start_choices = [
        "Play initial missions",
        "Skip missions (gain all bonuses)",
        "Skip missions (no bonuses)",
    ]
    start_choice = prompts.ask_select("How would you like to begin?", start_choices)

    if start_choice.startswith("Skip missions (gain"):
        # Auto-victory all missions with bonuses
        display.clear_screen()
        display.console.print("\n[bold cyan]═══ LANDING SITE ESTABLISHED ═══[/bold cyan]\n")
        display.console.print("  [dim]Initial missions skipped — all bonuses granted.[/dim]\n")

        state.colony.resources.raw_materials += 2
        display.console.print("  [green]Beacons: +2 Raw Materials[/green]")

        state.colony.resources.research_points += 2
        display.console.print("  [green]Analysis: +2 Research Points[/green]")

        state.colony.morale += 3
        display.console.print("  [green]Perimeter: +3 Colony Morale[/green]")

        for _, key in MISSION_ORDER:
            state.campaign.initial_mission_results[key] = {"victory": True}

        state.campaign.initial_missions_complete = True
        save_state(state)
        return

    if start_choice.startswith("Skip missions (no"):
        # Skip all missions with no bonuses
        display.clear_screen()
        display.console.print("\n[bold cyan]═══ LANDING SITE ESTABLISHED ═══[/bold cyan]\n")
        display.console.print("  [dim]Initial missions skipped — no bonuses granted.[/dim]")

        for _, key in MISSION_ORDER:
            state.campaign.initial_mission_results[key] = {"victory": False}

        state.campaign.initial_missions_complete = True
        save_state(state)
        return

    # Play missions normally
    remaining = list(MISSION_ORDER)
    results = {}

    while remaining:
        if len(remaining) == 1:
            mission_label, mission_key = remaining[0]
        else:
            choices = [label for label, _ in remaining]
            chosen_label = prompts.ask_select("Choose next mission:", choices)
            mission_key = next(key for label, key in remaining if label == chosen_label)
            mission_label = chosen_label

        remaining = [(l, k) for l, k in remaining if k != mission_key]

        if mission_key == "beacons":
            result = run_beacons(state)
        elif mission_key == "analysis":
            result = run_analysis(state)
        elif mission_key == "perimeter":
            result = run_perimeter(state)
        else:
            continue

        results[mission_key] = result

        # Save after each mission
        state.campaign.initial_mission_results[mission_key] = {
            "victory": result["victory"],
        }
        save_state(state)

    # Apply rewards
    display.clear_screen()
    display.console.print("\n[bold cyan]═══ LANDING SITE ESTABLISHED ═══[/bold cyan]\n")

    if results.get("beacons", {}).get("victory"):
        state.colony.resources.raw_materials += 2
        display.console.print("  [green]Beacons: SUCCESS — +2 Raw Materials[/green]")
    else:
        display.console.print("  [red]Beacons: Failed — no bonus[/red]")

    if results.get("analysis", {}).get("victory"):
        contacts = results["analysis"].get("contacts_revealed", 0)
        rp_bonus = 3 if contacts >= 6 else 2
        state.colony.resources.research_points += rp_bonus
        display.console.print(f"  [green]Analysis: SUCCESS — +{rp_bonus} Research Points[/green]")
    else:
        display.console.print("  [red]Analysis: Failed — no bonus[/red]")

    if results.get("perimeter", {}).get("victory"):
        state.colony.morale += 3
        display.console.print("  [green]Perimeter: SUCCESS — +3 Colony Morale[/green]")
    else:
        display.console.print("  [red]Perimeter: Failed — no bonus[/red]")

    display.console.print(
        "\n  [bold]All initial missions complete. Proceeding to Campaign Setup.[/bold]"
    )
    prompts.pause()

    # Mark complete
    state.campaign.initial_missions_complete = True
    save_state(state)


# ---------------------------------------------------------------------------
# UI-adapter-compatible mission runners (for web and generic UI backends)
# ---------------------------------------------------------------------------

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


def run_analysis_ui(state: GameState, ui: Any) -> dict:
    """Run the Analysis (Scientist) mission using a UIAdapter.

    Returns {"victory": bool, "contacts_revealed": int, "log": list[str]}.
    """
    from planetfall.orchestrator_steps import _get_move_zones, _get_dash_zones

    bf, log = _setup_analysis(state)
    scientists = [f for f in bf.figures if f.side == FigureSide.PLAYER]
    if not scientists:
        return {"victory": False, "contacts_revealed": 0, "log": log}

    contacts_revealed = 0
    contacts_fled = 0
    max_rounds = 10

    ui.reset_enemy_labels()

    # Mission intro modal
    ui.show_mission_intro({
        "title": "Analysis (Scientist Mission)",
        "subtitle": "Initial Landing Mission 2 of 3",
        "sections": [
            {"heading": "", "body": (
                "The second landing is by the Science Team, establishing the parameters "
                "of the mission site and conducting detailed scientific scans."
            )},
            {"heading": "Setup", "body": (
                "◆ Place 6 Contact markers fairly evenly around the table, then "
                "randomly select a battlefield edge.\n"
                "◆ Deploy your scientist characters within 1\" of the selected battlefield edge."
            )},
            {"heading": "Objective", "body": (
                "You must uncover at least 4 Contacts to complete the mission. "
                "Contacts that leave the table count against you. Note that in this mission, "
                "revealing a Contact simply removes it. You do not have to roll on the Contact Reveal table."
            )},
            {"heading": "Reward", "body": (
                "If you successfully complete the mission, you will begin the campaign with "
                "2 Research Points as a bonus (increased to 3 if you reveal all 6 Contacts).\n"
                "If the mission is a failure, you do not receive the reward as your initial scans "
                "are not sufficiently detailed, but you may progress to the next mission."
            )},
        ],
    })

    # Mission briefing (persistent info panel)
    ui.show_mission_briefing(
        bf,
        mission_type="Analysis",
        enemy_info=["6 Contacts placed around the table", "Contacts flee from scientists each round"],
        special_rules=[
            "End activation within 2 zones of a Contact to reveal it",
            "Contacts that flee off the table are lost",
            "Reveal 4+ contacts to succeed (6 for bonus)",
        ],
        victory_conditions=["Reveal at least 4 of 6 Contacts"],
        defeat_conditions=["All scientists eliminated", "Too few contacts remain"],
        enemy_type="contact",
    )

    for round_num in range(1, max_rounds + 1):
        remaining_contacts = [
            f for f in bf.figures if f.char_class == "contact" and f.is_alive
        ]
        if not remaining_contacts:
            break

        alive_scientists = [f for f in bf.figures if f.side == FigureSide.PLAYER and f.is_alive]
        if not alive_scientists:
            log.append("No scientists remaining — mission over")
            break

        ui.clear()
        ui.show_combat_phase("analysis_round", round_num)
        ui.show_battlefield(bf)
        ui.message(
            f"Round {round_num} — Revealed: {contacts_revealed} | "
            f"Fled: {contacts_fled} | Remaining: {len(remaining_contacts)}",
            style="bold",
        )

        for sci in alive_scientists:
            # Use standard movement system
            move_zones = _get_move_zones(bf, sci)
            dash_zones = _get_dash_zones(bf, sci)

            result = ui.prompt_movement(
                bf, sci,
                move_zones=move_zones,
                dash_zones=dash_zones,
                overlay_mode=ui.OVERLAY_MOVEMENT,
            )

            move_type = result.get("type", "stay")
            if move_type == "move":
                idx = result["zone_idx"]
                new_zone = move_zones[idx][0]
                sci.zone = new_zone
                log.append(f"{sci.name} moves to ({new_zone[0]},{new_zone[1]})")
            elif move_type == "dash":
                idx = result["zone_idx"]
                new_zone = dash_zones[idx][0]
                sci.zone = new_zone
                log.append(f"{sci.name} rushes to ({new_zone[0]},{new_zone[1]})")

            # Check for reveals — contacts within 2 zones
            remaining_contacts = [
                f for f in bf.figures if f.char_class == "contact" and f.is_alive
            ]
            revealed_this_activation = []
            for contact in remaining_contacts[:]:
                if _chebyshev(sci.zone, contact.zone) <= 2:
                    bf.figures.remove(contact)
                    contacts_revealed += 1
                    revealed_this_activation.append(
                        f"{sci.name} reveals {contact.name}! ({contacts_revealed} total)"
                    )
                    log.append(f"{sci.name} reveals {contact.name}!")

            if revealed_this_activation:
                ui.show_battlefield(bf)
                ui.show_combat_log(revealed_this_activation)

        # Check victory
        remaining_contacts = [
            f for f in bf.figures if f.char_class == "contact" and f.is_alive
        ]
        if contacts_revealed >= 4 and not remaining_contacts:
            break
        if contacts_revealed >= 4:
            if remaining_contacts:
                keep_going = ui.confirm(
                    f"4+ contacts revealed! Continue to try for all 6? "
                    f"({len(remaining_contacts)} remaining)",
                )
                if not keep_going:
                    break

        if not remaining_contacts:
            break

        # Enemy Phase: contacts flee
        contact_log = _move_contacts_away(bf)
        fled_this_round = sum(1 for entry in contact_log if "flees off" in entry)
        contacts_fled += fled_this_round

        if contact_log:
            ui.clear()
            ui.show_battlefield(bf)
            ui.show_combat_log(contact_log)
            log.extend(contact_log)
            ui.pause()

    victory = contacts_revealed >= 4

    ui.show_battlefield(bf)
    if victory:
        rp_bonus = 3 if contacts_revealed >= 6 else 2
        ui.show_mission_result(
            success=True,
            title="ANALYSIS — MISSION SUCCESS",
            detail=f"{contacts_revealed} contacts revealed! +{rp_bonus} Research Points bonus.",
        )
    else:
        ui.show_mission_result(
            success=False,
            title="ANALYSIS — MISSION FAILED",
            detail=f"Only {contacts_revealed} contacts revealed (needed 4). No bonus.",
        )

    return {"victory": victory, "contacts_revealed": contacts_revealed, "log": log}


def run_perimeter_ui(state: GameState, ui: Any) -> dict:
    """Run the Perimeter (Trooper) mission using a UIAdapter and full combat session.

    Returns {"victory": bool, "log": list[str]}.
    """
    from planetfall.engine.combat.battlefield import FigureSide

    troopers = _get_chars_by_class(state, CharacterClass.TROOPER)
    if not troopers:
        ui.message("No troopers on roster! Cannot play Perimeter mission.", style="error")
        return {"victory": False, "log": ["No troopers available"]}

    # Mission intro modal
    ui.show_mission_intro({
        "title": "Perimeter (Trooper Mission)",
        "subtitle": "Initial Landing Mission 3 of 3",
        "sections": [
            {"heading": "", "body": (
                "The third landing is by the troopers of the team, establishing a defensive "
                "perimeter as hostile Lifeforms are rapidly headed towards your drop site."
            )},
            {"heading": "Setup", "body": (
                "◆ Set up any troopers from your roster. Each is armed with the standard "
                "trooper rifle from the Armory. You may set up anywhere on your deployment edge.\n"
                "◆ After setting up, 6 Lifeform miniatures are placed along a randomly selected "
                "battlefield edge."
            )},
            {"heading": "Objective", "body": (
                "You must kill all 6 to complete the mission."
            )},
            {"heading": "Obstacles", "body": (
                "The Lifeforms move 5\" per action, have a +1 Combat Skill and Toughness 4. "
                "They will move as directly as possible to attack you in brawling combat and "
                "will strike with +0 Damage if they do.\n"
                "They are not subject to Panic tests."
            )},
            {"heading": "Reward", "body": (
                "Killing all 6 Lifeforms earns you +3 Colony Morale to begin the campaign.\n"
                "If you fail the mission, your troopers are evacuated, and a squad of grunts "
                "clears up the site. You may proceed to Campaign Setup in both cases."
            )},
        ],
    })

    mission_setup = _setup_perimeter(state)
    bf = mission_setup.battlefield

    # Hide player figures for deployment
    player_figs = [f for f in bf.figures if f.side == FigureSide.PLAYER]
    for f in player_figs:
        bf.figures.remove(f)

    # Show mission briefing (persistent info panel)
    ui.reset_enemy_labels()
    ui.show_mission_briefing(
        bf,
        mission_type="Perimeter",
        enemy_info=[
            "6 melee lifeforms approaching from the north",
            "Lifeforms: Speed 5\", CS +1, Toughness 4, +0 Damage (brawling)",
        ],
        special_rules=[],
        victory_conditions=list(mission_setup.victory_conditions),
        defeat_conditions=list(mission_setup.defeat_conditions),
        enemy_type=mission_setup.enemy_type,
    )

    # Deployment — player places troopers
    ui.show_combat_phase("deployment", 0)
    player_row = bf.rows - 1
    available_zones = [(player_row, c) for c in range(bf.cols)]
    ui.prompt_deployment_zones(bf, player_figs, available_zones)

    # Run full combat session
    session = CombatSession(mission_setup)
    combat_state = session.start_battle()

    ui.reset_enemy_labels()
    ui.show_battlefield(session.bf)

    prev_log_len = 0

    # Import the combat helpers from orchestrator_steps
    from planetfall.orchestrator_steps import _handle_player_turn

    while combat_state.phase.value != "battle_over":
        current_phase = combat_state.phase.value

        if current_phase == "reaction_roll":
            ui.clear()
            ui.show_combat_phase(current_phase, combat_state.round_number)
            ui.show_battlefield(session.bf)

            assignments = ui.prompt_reaction_assignment(
                combat_state.unassigned_dice,
                combat_state.reaction_figures,
            )
            combat_state = session.assign_reactions(assignments)
            prev_log_len = len(combat_state.phase_log)
            continue

        if combat_state.available_actions:
            # Player activation — reuse orchestrator combat handler
            queue = session.get_activation_queue()
            if len(queue) > 1:
                valid = [
                    n for n in queue
                    if (f := session.bf.get_figure_by_name(n))
                    and f.is_alive and not f.has_acted
                ]
                if len(valid) > 1:
                    from planetfall.cli.display import get_figure_map_label
                    fig_choices = []
                    for n in valid:
                        f = session.bf.get_figure_by_name(n)
                        label = get_figure_map_label(f)
                        cls = f.char_class.title() if f.char_class else ""
                        fig_choices.append(f"{n} ({label}) — {cls}")

                    ui.clear()
                    ui.show_combat_phase(current_phase, combat_state.round_number)
                    ui.show_battlefield(session.bf)
                    chosen = ui.select("Activate which figure?", fig_choices)
                    chosen_name = chosen.split(" (")[0]
                    if chosen_name != queue[0]:
                        session.set_next_figure(chosen_name)
                        combat_state = session._snapshot()

            combat_state, prev_log_len = _handle_player_turn(
                ui, session, combat_state, prev_log_len,
            )

        elif current_phase == "enemy_phase":
            ui.clear()
            ui.show_combat_phase(current_phase, combat_state.round_number)
            ui.show_battlefield(session.bf)

            while combat_state.phase.value == "enemy_phase":
                pre_step_len = len(combat_state.phase_log)
                combat_state = session.advance_enemy_step()
                new_log = combat_state.phase_log[pre_step_len:]
                substantive = [
                    entry for entry in new_log
                    if not entry.startswith("---") and not entry.startswith("===")
                ]
                if substantive:
                    ui.clear()
                    ui.show_combat_phase(current_phase, combat_state.round_number)
                    ui.show_battlefield(session.bf)
                    ui.show_combat_log(substantive)
                    if combat_state.phase.value != "battle_over":
                        ui.pause()

            prev_log_len = len(combat_state.phase_log)

        else:
            # Auto-advance (end phase, etc.)
            advancing_from = current_phase
            pre_len = len(combat_state.phase_log)
            combat_state = session.advance()
            new_log = combat_state.phase_log[pre_len:]
            substantive = [
                entry for entry in new_log
                if not entry.startswith("---") and not entry.startswith("===")
            ]

            # Always show End Phase with phase tracker
            if advancing_from in ("slow_actions", "quick_actions"):
                ui.clear()
                ui.show_combat_phase("end_phase", combat_state.round_number)
                ui.show_battlefield(session.bf)
                if substantive:
                    ui.show_combat_log(substantive)
                if combat_state.phase.value != "battle_over":
                    ui.pause()
            elif substantive:
                ui.clear()
                ui.show_combat_phase(
                    combat_state.phase.value, combat_state.round_number,
                )
                ui.show_battlefield(session.bf)
                ui.show_combat_log(substantive)
                if combat_state.phase.value != "battle_over":
                    ui.pause()
            prev_log_len = len(combat_state.phase_log)

    final_result = session.get_result()
    victory = final_result.get("victory", False)

    ui.show_battlefield(session.bf)
    if victory:
        ui.show_mission_result(
            success=True,
            title="PERIMETER — MISSION SUCCESS",
            detail="All 6 lifeforms eliminated! +3 Colony Morale bonus.",
        )
    else:
        ui.show_mission_result(
            success=False,
            title="PERIMETER — MISSION FAILED",
            detail="Troopers evacuated. A grunt squad clears the site. No bonus.",
        )

    return {"victory": victory, "log": final_result.get("log", [])}


def run_initial_missions_ui(state: GameState, ui: Any) -> None:
    """Run all 3 initial missions using a UIAdapter, apply rewards, mark complete."""
    from planetfall.engine.persistence import save_state

    # Let player choose mission order
    remaining = list(MISSION_ORDER)
    results = {}

    while remaining:
        if len(remaining) == 1:
            mission_label, mission_key = remaining[0]
            ui.message(f"Final mission: {mission_label}", style="bold")
        else:
            choices = [label for label, _ in remaining]
            mission_label = ui.select("Choose next mission:", choices)
            mission_key = next(key for label, key in remaining if label == mission_label)

        remaining = [(l, k) for l, k in remaining if k != mission_key]

        if mission_key == "beacons":
            result = run_beacons_ui(state, ui)
        elif mission_key == "analysis":
            result = run_analysis_ui(state, ui)
        elif mission_key == "perimeter":
            result = run_perimeter_ui(state, ui)
        else:
            continue

        results[mission_key] = result

        # Save after each mission
        state.campaign.initial_mission_results[mission_key] = {
            "victory": result["victory"],
        }
        save_state(state)

    # Apply rewards and build summary
    summary = []

    if results.get("beacons", {}).get("victory"):
        state.colony.resources.raw_materials += 2
        summary.append({"name": "Beacons", "success": True, "detail": "+2 Raw Materials"})
    else:
        summary.append({"name": "Beacons", "success": False, "detail": "No bonus"})

    if results.get("analysis", {}).get("victory"):
        contacts = results["analysis"].get("contacts_revealed", 0)
        rp_bonus = 3 if contacts >= 6 else 2
        state.colony.resources.research_points += rp_bonus
        summary.append({"name": "Analysis", "success": True, "detail": f"+{rp_bonus} Research Points"})
    else:
        summary.append({"name": "Analysis", "success": False, "detail": "No bonus"})

    if results.get("perimeter", {}).get("victory"):
        state.colony.morale += 3
        summary.append({"name": "Perimeter", "success": True, "detail": "+3 Colony Morale"})
    else:
        summary.append({"name": "Perimeter", "success": False, "detail": "No bonus"})

    ui.clear()
    ui.show_mission_summary(summary)
    ui.pause()

    state.campaign.initial_missions_complete = True
    save_state(state)

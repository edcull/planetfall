"""Analysis (Scientist) initial mission — reveal 4+ of 6 contacts."""

from __future__ import annotations

import random
from typing import Any

from planetfall.engine.combat.battlefield import (
    Battlefield, Figure, FigureSide, FigureStatus,
    generate_random_terrain, GRID_SMALL,
)
from planetfall.engine.combat.missions import _create_player_figure
from planetfall.engine.dice import roll_d6
from planetfall.engine.models import GameState, CharacterClass

from planetfall.engine.combat.initial_missions.base import (
    _get_chars_by_class, _chebyshev, _zones_within_range,
)


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

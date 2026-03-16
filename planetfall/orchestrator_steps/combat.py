"""Combat orchestrator — interactive combat loop and player turn handling."""
from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from planetfall.engine.models import (
    GameState, MissionType, TurnEvent, TurnEventType,
)
from planetfall.engine.combat.battlefield import FigureSide
from planetfall.engine.utils import format_display

if TYPE_CHECKING:
    from planetfall.ui.adapter import UIAdapter

RecordFn = Callable[[list[TurnEvent]], None]


# ---------------------------------------------------------------------------
# Multi-step player turn helpers
# ---------------------------------------------------------------------------

def _get_move_zones(bf, fig):
    """Valid standard move destinations for a figure.

    Returns [(zone, terrain_label, [fig_names_in_zone], is_jump), ...]
    """
    is_scout = fig.char_class == "scout"
    raw = bf.get_standard_move_zones(*fig.zone, fig.speed, is_scout)
    adj_zones = bf.adjacent_zones(*fig.zone)

    results = []
    for zone in raw:
        if not bf.zone_has_capacity(*zone, fig.side):
            continue
        terrain = bf.get_zone(*zone).terrain.value.replace("_", " ")
        figs = [f.name for f in bf.get_figures_in_zone(*zone)]
        is_jump = is_scout and zone not in adj_zones
        results.append((zone, terrain, figs, is_jump))
    return results


def _get_dash_zones(bf, fig):
    """Valid dash destinations from the figure's current position.

    Speed 1-2: 1 zone.  Speed 5-6: 2 zones.
    Speed 3-4, 7-8: No dash available.
    Uses Chebyshev distance (same as movement overlay).
    Returns [(zone, terrain_label, [fig_names], is_jump), ...]
    """
    raw = bf.get_rush_zones(*fig.zone, fig.speed)

    results = []
    for zone in raw:
        if not bf.zone_has_capacity(*zone, fig.side):
            continue
        terrain = bf.get_zone(*zone).terrain.value.replace("_", " ")
        figs = [f.name for f in bf.get_figures_in_zone(*zone)]
        results.append((zone, terrain, figs, False))
    return results


def _enemies_in_range(bf, fig, from_zone):
    """Return set of enemy names within weapon range and LoS from a zone (for highlighting)."""
    from planetfall.engine.combat.battlefield import zone_range_inches, FigureSide
    names = set()
    for e in bf.figures:
        if e.side != FigureSide.ENEMY or not e.is_alive or e.is_contact:
            continue
        dist = bf.zone_distance(from_zone, e.zone)
        if zone_range_inches(dist) <= fig.weapon_range:
            if bf.check_los(from_zone, e.zone) != "blocked":
                names.add(e.name)
    return names


def _get_shoot_targets(bf, fig, from_zone, moved):
    """Enemies in weapon range from a given zone.

    Returns [{name, map_label, eff_label, eff, range_label, shots}, ...]
    """
    from planetfall.engine.combat.shooting import get_hit_target, get_effective_hit
    from planetfall.engine.combat.battlefield import zone_range_inches, FigureSide
    from planetfall.cli.display import get_figure_map_label

    enemies = [e for e in bf.figures
               if e.side == FigureSide.ENEMY and e.is_alive and not e.is_contact]
    results = []
    for enemy in enemies:
        dist = bf.zone_distance(from_zone, enemy.zone)
        approx_range = zone_range_inches(dist)
        if approx_range <= fig.weapon_range:
            hit_needed = get_hit_target(bf, fig, enemy, shooter_moved=moved)
            if hit_needed <= 6:
                eff = get_effective_hit(bf, fig, enemy, shooter_moved=moved)
                eff_label = "auto" if eff <= 1 else f"{eff}+"
                range_label = "close" if dist <= 2 else "medium" if approx_range <= 18 else "long"
                # Build modifier list for UI display
                modifiers = []
                if bf.has_cover_los(from_zone, enemy.zone):
                    if bf.target_in_cover_zone(enemy.zone):
                        modifiers.append("in cover")
                    else:
                        modifiers.append("cover (LoS)")
                if bf.has_scatter(from_zone, enemy.zone):
                    modifiers.append("scatter")
                if bf.shooter_on_high_ground(from_zone, enemy.zone):
                    modifiers.append("high ground")
                if moved and "cumbersome" in fig.weapon_traits:
                    modifiers.append("cumbersome")
                results.append({
                    "name": enemy.name,
                    "map_label": get_figure_map_label(enemy),
                    "eff_label": eff_label,
                    "eff": eff,
                    "range_label": range_label,
                    "shots": fig.weapon_shots,
                    "modifiers": modifiers,
                })
    return results


def _get_aid_options(bf, fig, at_zone):
    """Allies that can be aided at a zone.

    Returns [{name, can_place_marker, can_remove_stun, stun_count}, ...]
    """
    results = []
    for a in bf.figures:
        if a.side != fig.side or not a.is_alive or a.name == fig.name:
            continue
        if a.zone != at_zone:
            continue
        can_marker = not a.aid_marker
        can_stun = a.stun_markers > 0
        if can_marker or can_stun:
            results.append({
                "name": a.name,
                "can_place_marker": can_marker,
                "can_remove_stun": can_stun,
                "stun_count": a.stun_markers,
            })
    return results


def _get_figure_profile(fig) -> dict:
    """Build a dict of figure stats for UI display."""
    from planetfall.cli.display import get_figure_map_label
    label = get_figure_map_label(fig)
    profile = {
        "name": fig.name,
        "label": label,
        "char_class": fig.char_class.title() if fig.char_class else "",
        "speed": fig.speed,
        "reactions": fig.reactions,
        "combat_skill": fig.combat_skill,
        "toughness": fig.toughness,
        "savvy": fig.savvy,
        "armor_save": fig.armor_save,
        "weapon_name": fig.weapon_name or "Unarmed",
        "weapon_range": fig.weapon_range,
        "weapon_shots": fig.weapon_shots,
        "weapon_damage": fig.weapon_damage,
        "weapon_traits": list(fig.weapon_traits) if fig.weapon_traits else [],
    }
    statuses = []
    if fig.stun_markers:
        statuses.append(f"Stun x{fig.stun_markers}")
    if fig.status.value == "sprawling":
        statuses.append("Sprawling")
    if fig.aid_marker:
        statuses.append("Aid marker")
    if fig.hit_bonus:
        statuses.append(f"Hit +{fig.hit_bonus}")
    profile["statuses"] = statuses
    return profile


def _print_figure_stats(ui: UIAdapter, fig):
    """Print active figure stats, weapon, and status (CLI only)."""
    from planetfall.cli.display import get_figure_map_label

    label = get_figure_map_label(fig)
    class_str = fig.char_class.title() if fig.char_class else ""

    parts = [f"{fig.name} ({label})"]
    if class_str:
        parts.append(class_str)
    ui.message(f"\n  {' — '.join(parts)}", style="bold")

    stat_parts = [
        f"Spd {fig.speed}",
        f"React {fig.reactions}",
        f"CS +{fig.combat_skill}",
        f"Tough {fig.toughness}",
        f"Savvy +{fig.savvy}",
    ]
    if fig.armor_save:
        stat_parts.append(f"Armor {fig.armor_save}+")
    ui.message(f"  {' | '.join(stat_parts)}", style="dim")

    weapon_parts = [fig.weapon_name or "Unarmed"]
    weapon_parts.append(f"Range {fig.weapon_range}\"")
    weapon_parts.append(f"Shots {fig.weapon_shots}")
    if fig.weapon_damage:
        weapon_parts.append(f"Dmg +{fig.weapon_damage}")
    if fig.weapon_traits:
        weapon_parts.append(f"Traits: {', '.join(fig.weapon_traits)}")
    ui.message(f"  {' | '.join(weapon_parts)}")

    statuses = []
    if fig.stun_markers:
        statuses.append(f"Stun x{fig.stun_markers}")
    if fig.status.value == "sprawling":
        statuses.append("Sprawling")
    if fig.aid_marker:
        statuses.append("Aid marker")
    if fig.hit_bonus:
        statuses.append(f"Hit +{fig.hit_bonus}")
    if statuses:
        ui.message(f"  {' | '.join(statuses)}", style="warning")


def _prompt_with_overlay(ui: UIAdapter, session, fig, choices, prompt_text, default_overlay, phase_str, round_num, log_entries, slyn_unknown=False, highlighted_enemies=None):
    """Show battlefield + prompt with overlay cycling.

    Returns the selected choice string (not the overlay cycle label).
    """
    overlay_modes = [
        ui.OVERLAY_VISION, ui.OVERLAY_MOVEMENT, ui.OVERLAY_SHOOTING,
    ]
    overlay_names = ["Vision", "Movement", "Shooting"]
    overlay_idx = overlay_modes.index(default_overlay) if default_overlay in overlay_modes else 0

    while True:
        overlay_mode = overlay_modes[overlay_idx]
        ui.clear()
        ui.show_combat_phase(phase_str, round_num)
        ui.show_battlefield(
            session.bf, active_fig=fig, overlay_mode=overlay_mode,
            slyn_unknown=slyn_unknown,
            highlighted_enemies=highlighted_enemies,
        )
        if log_entries:
            ui.show_combat_log(log_entries)
        if not ui.HAS_OVERLAY_BUTTONS:
            _print_figure_stats(ui, fig)

        # Web UI has native overlay toggle buttons — no need for text cycling
        if ui.HAS_OVERLAY_BUTTONS:
            return ui.select(prompt_text, list(choices))

        next_name = overlay_names[(overlay_idx + 1) % len(overlay_names)]
        cycle_label = f"[Overlay: {overlay_names[overlay_idx]} → {next_name}]"
        all_choices = list(choices) + [cycle_label]

        choice = ui.select(prompt_text, all_choices)
        if choice == cycle_label:
            overlay_idx = (overlay_idx + 1) % len(overlay_modes)
            continue
        return choice


def _handle_movement_phase(ui: 'UIAdapter', session, fig, is_scout, is_trooper, in_quick, num_move, can_dash, is_delayed, slyn_unknown, in_range, phase_str, round_num):
    """Steps 1+2: movement type + destination selection.

    Returns (move_to, dashed, trooper_delay, scout_action_first) or None if cancelled.
    """
    from planetfall.engine.combat.battlefield import FigureSide  # noqa: F811

    move_to = None
    dashed = False
    trooper_delay = False
    scout_action_first = False

    if is_delayed:
        # Delayed trooper returning in slow phase: no movement, just action
        return move_to, dashed, trooper_delay, scout_action_first

    all_move_zones = _get_move_zones(session.bf, fig) if num_move > 0 else []
    all_dash_zones = _get_dash_zones(session.bf, fig) if can_dash else []

    # Trooper in quick phase: staying stationary enables delay action
    if is_trooper and in_quick:
        trooper_delay = True  # will be cleared if they choose to move

    if not all_move_zones and not all_dash_zones and not is_scout:
        return move_to, dashed, trooper_delay, scout_action_first

    result = ui.prompt_movement(
        session.bf, fig,
        move_zones=all_move_zones,
        dash_zones=all_dash_zones,
        can_scout_first=is_scout,
        can_trooper_delay=is_trooper and in_quick,
        overlay_mode=ui.OVERLAY_MOVEMENT,
        slyn_unknown=slyn_unknown,
        highlighted_enemies=in_range,
        active_figure=_get_figure_profile(fig),
    )
    move_result_type = result.get("type", "stay")

    if move_result_type == "cancel":
        return None  # sentinel: go back to figure selection

    if move_result_type == "move":
        trooper_delay = False
        idx = result["zone_idx"]
        move_to = all_move_zones[idx][0]
    elif move_result_type == "dash":
        trooper_delay = False
        dashed = True
        idx = result["zone_idx"]
        move_to = all_dash_zones[idx][0]
    elif move_result_type == "scout_first":
        trooper_delay = False
        scout_action_first = True
    # "stay" — trooper_delay stays True if applicable

    return move_to, dashed, trooper_delay, scout_action_first


def _handle_action_phase(ui: 'UIAdapter', session, fig, action_zone, move_to, slyn_unknown, in_range, phase_str, round_num, log_entries):
    """Steps 3+4: action selection + target.

    Returns (action_type, target_name, use_aid).
    """
    action_type = "hold"
    target_name = None
    use_aid = False

    action_choices = []

    # Shoot
    shoot_targets = _get_shoot_targets(
        session.bf, fig, action_zone, moved=(move_to is not None),
    )

    # Build shoot target descriptors for UI
    shoot_descs = []
    shoot_target_data = []
    if shoot_targets:
        for t in shoot_targets:
            desc = (
                f"{t['name']} ({t['map_label']}) at {t['range_label']} range "
                f"({t['eff_label']}, {t['shots']} shot(s))"
            )
            shoot_descs.append(desc)
            shoot_target_data.append({
                "name": t["name"],
                "map_label": t["map_label"],
                "eff_label": t["eff_label"],
                "range_label": t["range_label"],
                "shots": t["shots"],
                "modifiers": t.get("modifiers", []),
                "desc": desc,
            })
        if fig.aid_marker:
            for t in shoot_targets:
                aided_eff = max(1, t["eff"] - 1)
                aided_label = "auto" if aided_eff <= 1 else f"{aided_eff}+"
                desc = (
                    f"{t['name']} ({t['map_label']}) at {t['range_label']} range "
                    f"({aided_label}, {t['shots']} shot(s)) [spend Aid +1]"
                )
                shoot_descs.append(desc)
                shoot_target_data.append({
                    "name": t["name"],
                    "map_label": t["map_label"],
                    "eff_label": aided_label,
                    "range_label": t["range_label"],
                    "shots": t["shots"],
                    "modifiers": t.get("modifiers", []),
                    "desc": desc,
                    "use_aid": True,
                })

    # Brawl (enemy in action zone)
    brawl_targets = [
        e for e in session.bf.figures
        if e.side == FigureSide.ENEMY and e.is_alive and not e.is_contact
        and e.zone == action_zone
    ]
    if brawl_targets:
        action_choices.append("Brawl")

    # Aid (ally in action zone)
    aid_options = _get_aid_options(session.bf, fig, action_zone)
    if aid_options:
        action_choices.append("Aid")

    # Leave battlefield (edge zone)
    if session.bf.is_edge_zone(*action_zone):
        action_choices.append("Leave battlefield")

    action_choices.append("Hold")

    # Present action choices — shoot targets go in info panel for web UI
    overlay_modes = [
        ui.OVERLAY_VISION, ui.OVERLAY_MOVEMENT, ui.OVERLAY_SHOOTING,
    ]
    overlay_names = ["Vision", "Movement", "Shooting"]
    overlay_idx = (
        overlay_modes.index(ui.OVERLAY_SHOOTING)
        if ui.OVERLAY_SHOOTING in overlay_modes else 0
    )

    action_choice = None
    while True:
        overlay_mode = overlay_modes[overlay_idx]
        ui.clear()
        ui.show_combat_phase(phase_str, round_num)
        ui.show_battlefield(
            session.bf, active_fig=fig, overlay_mode=overlay_mode,
            slyn_unknown=slyn_unknown,
            highlighted_enemies=in_range,
        )
        if log_entries:
            ui.show_combat_log(log_entries)

        if ui.HAS_OVERLAY_BUTTONS:
            action_choice = ui.select_action(
                "Action:", action_choices,
                shoot_targets=shoot_target_data if shoot_target_data else None,
                active_figure=_get_figure_profile(fig),
            )
            break

        _print_figure_stats(ui, fig)

        # CLI: add Shoot to choices normally
        cli_choices = list(action_choices)
        if shoot_targets:
            cli_choices.insert(0, "Shoot")
        next_name = overlay_names[(overlay_idx + 1) % len(overlay_names)]
        cycle_label = f"[Overlay: {overlay_names[overlay_idx]} → {next_name}]"
        cli_choices.append(cycle_label)

        action_choice = ui.select("Action:", cli_choices)
        if action_choice == cycle_label:
            overlay_idx = (overlay_idx + 1) % len(overlay_modes)
            continue
        break

    # === Action Target ===

    # Check if response is a shoot target desc (from info panel click)
    if action_choice in shoot_descs:
        idx = shoot_descs.index(action_choice)
        if idx >= len(shoot_targets):
            target_name = shoot_targets[idx - len(shoot_targets)]["name"]
            use_aid = True
        else:
            target_name = shoot_targets[idx]["name"]
        action_type = "shoot"

    elif action_choice == "Shoot":
        # CLI fallback: two-step target selection
        choice = _prompt_with_overlay(
            ui, session, fig, shoot_descs, "Shoot:",
            ui.OVERLAY_SHOOTING, phase_str, round_num, log_entries,
            slyn_unknown=slyn_unknown, highlighted_enemies=in_range,
        )
        idx = shoot_descs.index(choice)
        if idx >= len(shoot_targets):
            target_name = shoot_targets[idx - len(shoot_targets)]["name"]
            use_aid = True
        else:
            target_name = shoot_targets[idx]["name"]
        action_type = "shoot"

    elif action_choice == "Brawl":
        if len(brawl_targets) == 1:
            target_name = brawl_targets[0].name
        else:
            brawl_descs = [f"{e.name}" for e in brawl_targets]
            if fig.aid_marker:
                brawl_descs += [f"{e.name} [spend Aid +1]" for e in brawl_targets]
            choice = _prompt_with_overlay(
                ui, session, fig, brawl_descs, "Brawl:",
                ui.OVERLAY_VISION, phase_str, round_num, log_entries,
                slyn_unknown=slyn_unknown, highlighted_enemies=in_range,
            )
            idx = brawl_descs.index(choice)
            if idx >= len(brawl_targets):
                target_name = brawl_targets[idx - len(brawl_targets)].name
                use_aid = True
            else:
                target_name = brawl_targets[idx].name
        action_type = "brawl"

    elif action_choice == "Aid":
        aid_descs = []
        for opt in aid_options:
            if opt["can_place_marker"]:
                aid_descs.append(f"Place Aid marker on {opt['name']}")
            if opt["can_remove_stun"]:
                aid_descs.append(
                    f"Remove stun from {opt['name']} ({opt['stun_count']} markers)"
                )
        choice = _prompt_with_overlay(
            ui, session, fig, aid_descs, "Aid:",
            ui.OVERLAY_VISION, phase_str, round_num, log_entries,
            slyn_unknown=slyn_unknown, highlighted_enemies=in_range,
        )
        if choice.startswith("Place"):
            action_type = "aid_marker"
        else:
            action_type = "aid_stun"
        for opt in aid_options:
            if opt["name"] in choice:
                target_name = opt["name"]
                break

    elif action_choice == "Leave battlefield":
        action_type = "leave_battlefield"

    elif action_choice == "Hold":
        if move_to:
            action_type = "move"
        else:
            action_type = "hold"

    return action_type, target_name, use_aid


def _handle_player_turn(ui: UIAdapter, session, combat_state, prev_log_len, slyn_unknown=False):
    """Multi-step player turn: movement type -> location -> action -> target -> scout post-move.

    Returns (new_combat_state, new_prev_log_len).
    """
    from planetfall.engine.combat.battlefield import (
        move_zones as calc_move_zones, rush_available,
    )
    from planetfall.engine.combat.session import CombatPhase

    fig = next(
        (f for f in session.bf.figures if f.name == combat_state.current_figure),
        None,
    )
    if not fig:
        return session.advance(), prev_log_len

    is_scout = fig.char_class == "scout"
    is_trooper = fig.char_class == "trooper"
    in_quick = session.phase == CombatPhase.QUICK_ACTIONS
    num_move = calc_move_zones(fig.speed)
    can_dash = rush_available(fig.speed)
    phase_str = combat_state.phase.value
    round_num = combat_state.round_number
    log_entries = combat_state.phase_log[prev_log_len:]
    is_delayed = fig.name in session._delayed_troopers

    # Update phase header (e.g. reaction_roll -> quick_actions)
    ui.show_combat_phase(phase_str, round_num)

    # Enemies in range from current position (for movement phase highlighting)
    in_range = _enemies_in_range(session.bf, fig, fig.zone)

    # === STEP 1+2: Movement ===
    move_result = _handle_movement_phase(
        ui, session, fig, is_scout, is_trooper, in_quick,
        num_move, can_dash, is_delayed, slyn_unknown, in_range,
        phase_str, round_num,
    )
    if move_result is None:
        return None  # cancelled

    move_to, dashed, trooper_delay, scout_action_first = move_result
    action_type = "rush" if dashed else "hold"

    # Temporarily move fig to chosen destination so overlays render correctly
    original_zone = fig.zone
    if move_to and not scout_action_first:
        fig.zone = move_to

        # Check contact detection after movement — reveal before action selection
        detected = session.bf.detect_contacts_auto()
        if detected:
            reveal_log = []
            for det in detected:
                reveal_log.extend(session.bf.reveal_contact(det))
            if reveal_log:
                session.round_log.extend(reveal_log)
                session.full_log.extend(reveal_log)
                ui.clear()
                ui.show_combat_phase(phase_str, round_num)
                ui.show_battlefield(session.bf, slyn_unknown=slyn_unknown)
                ui.show_combat_log(reveal_log)
                ui.pause()

        # Check interactive objectives (discovery/recon/science) immediately on entry
        log_before = len(session.round_log)
        session._check_objective_interaction(fig)
        obj_log = session.round_log[log_before:]
        if obj_log:
            ui.clear()
            ui.show_combat_phase(phase_str, round_num)
            ui.show_battlefield(session.bf, slyn_unknown=slyn_unknown)
            ui.show_combat_log(obj_log)
            ui.pause()

    # Update in-range enemies from new position for action phase
    action_zone = move_to if move_to else original_zone
    in_range = _enemies_in_range(session.bf, fig, action_zone)

    # === STEP 3+4: Action ===
    target_name = None
    use_aid = False
    if not dashed:
        action_type, target_name, use_aid = _handle_action_phase(
            ui, session, fig, action_zone, move_to, slyn_unknown, in_range,
            phase_str, round_num, log_entries,
        )
        # Leave battlefield overrides move_to
        if action_type == "leave_battlefield":
            move_to = None

    # === STEP 5: Scout Post-Action Move ===
    if scout_action_first:
        if action_type == "shoot":
            action_type = "shoot_and_move"

        scout_move_zones = _get_move_zones(session.bf, fig)
        if scout_move_zones:
            result = ui.prompt_movement(
                session.bf, fig,
                move_zones=scout_move_zones,
                dash_zones=[],
                can_scout_first=False,
                can_trooper_delay=False,
                overlay_mode=ui.OVERLAY_MOVEMENT,
                slyn_unknown=slyn_unknown,
                highlighted_enemies=in_range,
                active_figure=_get_figure_profile(fig),
            )
            move_result_type = result.get("type", "stay")
            if move_result_type == "move":
                idx = result["zone_idx"]
                move_to = scout_move_zones[idx][0]

    # === EXECUTE ===
    # Restore original zone so engine handles the move
    fig.zone = original_zone
    full_log_before = len(session.full_log)
    combat_state = session.execute_direct_action(
        action_type=action_type,
        move_to=move_to,
        target_name=target_name,
        use_aid=use_aid,
    )

    # Handle trooper delay: queue for slow phase (always, regardless of action)
    if trooper_delay:
        session.queue_for_slow_phase(fig.name)

    # Redraw map after action — use full_log to avoid missing entries
    # when round advances and phase_log resets
    new_log = session.full_log[full_log_before:]
    # Filter out phase/round separators and end-phase entries
    # (end phase is shown separately in the main combat loop)
    end_phase_keywords = (
        "Casualties this round:", "BATTLE OVER:", "PANIC:",
        "flees the battlefield", "panics and flees",
        "Remaining squad eliminated",
    )
    substantive = [
        l for l in new_log
        if not l.startswith("---") and not l.startswith("===")
        and not any(kw in l for kw in end_phase_keywords)
    ]
    if substantive:
        ui.clear()
        ui.show_combat_phase(phase_str, round_num)
        ui.show_battlefield(session.bf, slyn_unknown=slyn_unknown)
        ui.show_combat_log(substantive)
        # Skip pause on battle_over — end phase handles it
        if combat_state.phase.value != "battle_over":
            ui.pause()
    prev_log_len = len(combat_state.phase_log)

    return combat_state, prev_log_len


# ---------------------------------------------------------------------------
# Mission intro descriptions (extracted to module level)
# ---------------------------------------------------------------------------

_MISSION_INTROS = {
    MissionType.INVESTIGATION: {
        "subtitle": "Search the area for features of interest",
        "sections": [
            {"heading": "", "body": (
                "Long range scans show interesting sights in this sector. Your team is being "
                "deployed to search the area, look for features of interest, and secure any "
                "valuable finds. You are going in quick with a smaller team, trying to avoid "
                "detection by any potential hostiles."
            )},
            {"heading": "Setup", "body": (
                "◆ 3x3 table with Discovery markers in each table quarter.\n"
                "◆ Deploy 4 characters within 1\" of your battlefield edge.\n"
                "◆ No battle conditions. Slyn will not attack."
            )},
            {"heading": "Objective", "body": (
                "Investigate Discovery markers by moving within 2\" and rolling D6. "
                "Results range from enemy sentries to valuable data. "
                "Mission ends when your squad leaves the table."
            )},
            {"heading": "Rewards", "body": (
                "Completing 2+ markers clears the Investigation site. "
                "Roll for Science and Scouting mission eligibility."
            )},
        ],
    },
    MissionType.SCOUTING: {
        "subtitle": "Assess the area for exploration and exploitation",
        "sections": [
            {"heading": "", "body": (
                "A small scouting mission is being deployed to assess the area for further "
                "exploration and exploitation."
            )},
            {"heading": "Setup", "body": (
                "◆ 2x2 table with Recon markers in the 6 largest terrain features.\n"
                "◆ Deploy 2 characters. A scout is highly recommended.\n"
                "◆ No battle conditions. Slyn will not attack."
            )},
            {"heading": "Objective", "body": (
                "Collect recon data by moving into base contact with Recon markers. "
                "Scouts recon automatically; others must roll D6+Savvy (5+ succeeds). "
                "Mission ends when your squad leaves the table."
            )},
            {"heading": "Rewards", "body": (
                "Each Recon marker: roll D6, on 6 sector Resource level +1. "
                "3+ markers cleared: roll for Post-Mission Find. "
                "Sector becomes Explored with Resource and Hazard levels generated."
            )},
        ],
    },
    MissionType.EXPLORATION: {
        "subtitle": "Sweep the area and deal with any opposition",
        "sections": [
            {"heading": "", "body": (
                "You are tasked with sweeping the area and dealing with any opposition or "
                "hazards that present themselves. The job may or may not be simple — you "
                "won't know until you land."
            )},
            {"heading": "Setup", "body": (
                "◆ 3x3 table with Objective markers equal to the sector's Resource Value.\n"
                "◆ Deploy 6 characters from your roster.\n"
                "◆ On 2D6 roll of 2-4, Slyn attack; otherwise wildlife Contacts."
            )},
            {"heading": "Objective", "body": (
                "Sweep Objective markers by ending a battle round with a figure within 3\" "
                "and no enemies closer. If Slyn attack, they compete for Objectives. "
                "Mission ends when your squad leaves the table or Slyn are driven off."
            )},
            {"heading": "Rewards", "body": (
                "Roll Post-Mission Find once per completed Objective. "
                "Each Objective: D6 — 1 increases Hazard, 3-6 reduces Resources. "
                "Resources reaching 0 means sector is Exploited."
            )},
        ],
    },
    MissionType.SCIENCE: {
        "subtitle": "Obtain scientific samples from the field",
        "sections": [
            {"heading": "", "body": (
                "You are carrying out a quick mission to obtain scientific samples, "
                "hopefully without attracting too much attention."
            )},
            {"heading": "Setup", "body": (
                "◆ 2x2 table with Science markers in the 6 largest terrain features.\n"
                "◆ Deploy 2 characters. A scientist is highly recommended.\n"
                "◆ Slyn will not attack. 1 Contact placed at center."
            )},
            {"heading": "Objective", "body": (
                "Collect samples by moving into base contact with Science markers. "
                "Scientists collect automatically; others roll D6+Savvy (5+ succeeds, "
                "failure ruins the sample). Mission ends when squad leaves the table."
            )},
            {"heading": "Rewards", "body": (
                "Each sample: D6, on 4-6 receive 1 Research Point. "
                "Multiple 6s also grant Mission Data. "
                "3+ markers: roll for Post-Mission Find. Sector Resource -1."
            )},
        ],
    },
    MissionType.HUNT: {
        "subtitle": "Acquire a specimen of a local Lifeform",
        "sections": [
            {"heading": "", "body": (
                "The researchers want you to acquire a specimen of a local Lifeform "
                "for investigation."
            )},
            {"heading": "Setup", "body": (
                "◆ 3x3 table. Any sector within 4 spaces of colony.\n"
                "◆ Deploy up to 6 figures (characters or grunts).\n"
                "◆ On 2D6 roll of 2-4, Slyn attack; otherwise hunting Lifeforms."
            )},
            {"heading": "Objective", "body": (
                "Kill two Lifeforms, then move into base contact with each and spend "
                "an action to transmit data. Then escape the table. "
                "If Slyn attack, fight them off (no specimen rewards)."
            )},
            {"heading": "Rewards", "body": (
                "Two Lifeform samples: authorizes Bio-Analysis Research. "
                "Driving off Slyn: roll for Post-Mission Find. "
                "If sector has Hazard: D6, on 5-6 Hazard reduced by 1."
            )},
        ],
    },
    MissionType.PATROL: {
        "subtitle": "Conduct a routine patrol near the colony",
        "sections": [
            {"heading": "", "body": (
                "Survival on a hostile world requires vigilance. You send out a team to "
                "conduct a patrol near the colony to keep everyone safe and have a look "
                "at conditions in the field."
            )},
            {"heading": "Setup", "body": (
                "◆ 3x3 table within 2 squares of colony (non-enemy-occupied).\n"
                "◆ Deploy 2 characters + up to 4 grunts.\n"
                "◆ 3 Objectives in terrain features closest to center.\n"
                "◆ On 2D6 of 2-4, Slyn attack; 5-6 animals."
            )},
            {"heading": "Objective", "body": (
                "Clear each Objective by ending a round with a figure within 2\" and "
                "no enemies within that distance. Multiple Objectives can be cleared "
                "per round. Mission ends when squad leaves the table."
            )},
            {"heading": "Rewards", "body": (
                "1+ Objectives: Colony Morale +1. "
                "All 3 Objectives: roll for Post-Mission Find."
            )},
        ],
    },
    MissionType.SKIRMISH: {
        "subtitle": "Take on the enemy directly in their territory",
        "sections": [
            {"heading": "", "body": (
                "Enemy activity has been intensifying, and it is time to fight back. "
                "You deploy from your shuttle to take on the enemy directly."
            )},
            {"heading": "Setup", "body": (
                "◆ 3x3 table in enemy-occupied sector.\n"
                "◆ Deploy 4 characters + 4 grunts.\n"
                "◆ Roll 2 Skirmish Objectives (Secure, Sweep, Destroy, Search, Deliver, Retrieve).\n"
                "◆ Slyn will not interfere. Tactical enemies deploy opposite edge."
            )},
            {"heading": "Objective", "body": (
                "Complete both Skirmish Objectives. Enemies ignore Objectives and focus "
                "on killing your squad. At end of each round, D6 per completed Objective — "
                "on 6, reinforcements arrive."
            )},
            {"heading": "Rewards", "body": (
                "Both Objectives: roll Post-Mission Find and enemy no longer occupies sector. "
                "If their last sector, they move to adjacent sector."
            )},
        ],
    },
    MissionType.RESCUE: {
        "subtitle": "Save stranded colonists before they're overwhelmed",
        "sections": [
            {"heading": "", "body": (
                "Colonists have sent up an SOS signal, and your squad is headed out "
                "to rescue them before they get overwhelmed."
            )},
            {"heading": "Setup", "body": (
                "◆ 2x2 table. 3 colonists placed in the center.\n"
                "◆ Deploy up to 6 figures (characters and/or grunts) within 3\" of center.\n"
                "◆ Slyn will not interfere. 2 Contacts at center of each edge."
            )},
            {"heading": "Objective", "body": (
                "Save colonists by escorting them off any battlefield edge (must be within "
                "3\" of a squad member). Colonists leaving alone: D6, on 5-6 saved, "
                "otherwise killed."
            )},
            {"heading": "Rewards", "body": (
                "Lose 1 Colony Morale per colonist not saved. "
                "Squad casualties do not affect Morale during Rescue."
            )},
        ],
    },
    MissionType.SCOUT_DOWN: {
        "subtitle": "Rescue a downed scout with enemies closing in",
        "sections": [
            {"heading": "", "body": (
                "One of your scouts has been shot down with enemies closing in. "
                "You deploy to rescue them."
            )},
            {"heading": "Setup", "body": (
                "◆ 2x2 table. Injured scout placed in center.\n"
                "◆ Deploy up to 6 figures (characters and/or grunts).\n"
                "◆ On 2D6 of 2-3, Slyn attack; otherwise Tactical Enemies."
            )},
            {"heading": "Objective", "body": (
                "Rescue the crashed scout by moving them off any battlefield edge. "
                "The injured scout can move OR act each round, but not both. "
                "They begin undetected until they fire, are spotted in the open, or move more than 2\"."
            )},
            {"heading": "Rewards", "body": (
                "Saving a non-roster scout: +1 Colony Morale. "
                "Unexplored sector becomes Explored. "
                "Squad casualties do not affect Morale."
            )},
        ],
    },
    MissionType.PITCHED_BATTLE: {
        "subtitle": "Defend the colony against a direct attack",
        "sections": [
            {"heading": "", "body": (
                "The enemy is launching an attack on you and you will have to fight "
                "to see them off. Significant damage to the colony can ensue."
            )},
            {"heading": "Setup", "body": (
                "◆ 3x3 table in your colony sector.\n"
                "◆ Deploy up to 4 characters + up to 8 grunts (2 fireteams).\n"
                "◆ Slyn will not interfere. Two enemy forces arrive on rounds 1 and 2."
            )},
            {"heading": "Objective", "body": (
                "Kill or drive off every enemy. This is a fight to the end."
            )},
            {"heading": "Rewards", "body": (
                "Victory: each survivor gains +1 XP. "
                "Defeat: roll D100 on Campaign Consequences (colony damage, morale loss, "
                "attrition, or prolonged battle injuries)."
            )},
        ],
    },
    MissionType.STRIKE: {
        "subtitle": "Raid to capture an enemy leader",
        "sections": [
            {"heading": "", "body": (
                "You have detected the location of an enemy leader and are launching "
                "a raid to capture them."
            )},
            {"heading": "Setup", "body": (
                "◆ 3x3 table adjacent to enemy-occupied sector.\n"
                "◆ Deploy up to 6 characters + up to 4 grunts.\n"
                "◆ You set up AFTER enemy. Slyn will not interfere.\n"
                "◆ Enemy deploys around center with Boss/Leader in middle."
            )},
            {"heading": "Objective", "body": (
                "Defeat the Boss/Leader in brawl or kill them, then move a character "
                "to their location to secure data. Undetected squad members (move only, "
                "no actions) are ignored by the enemy."
            )},
            {"heading": "Rewards", "body": (
                "Boss data: reveals enemy Strongpoint location. "
                "Leader data: +1 Enemy Information."
            )},
        ],
    },
    MissionType.ASSAULT: {
        "subtitle": "Storm the enemy Strongpoint",
        "sections": [
            {"heading": "", "body": (
                "It is time. You have tracked down the enemy Strongpoint and are ready "
                "to take it by storm. Check the ammunition one last time — it will be "
                "a hot landing."
            )},
            {"heading": "Setup", "body": (
                "◆ 3x3 table at enemy Strongpoint sector.\n"
                "◆ Deploy up to 6 characters + up to 8 grunts (2 fireteams).\n"
                "◆ Maximum enemy force +2 regulars, +2 specialists, +1 leader.\n"
                "◆ Enemy deployed in defensive positions in central 12\"x12\" area."
            )},
            {"heading": "Objective", "body": (
                "Straight fight to the death. Kill or drive off every enemy. "
                "Enemies not in Line of Sight of your forces in round 1 are unready "
                "and cannot activate. Enemy Panic ranges reduced by 1."
            )},
            {"heading": "Rewards", "body": (
                "Victory eliminates this enemy from the campaign. "
                "All their sectors relinquished. Roll Post-Mission Finds twice. "
                "Defeat: enemy restored to full strength, occupies adjacent sector."
            )},
        ],
    },
    MissionType.DELVE: {
        "subtitle": "Explore an ancient alien facility",
        "sections": [
            {"heading": "", "body": (
                "You have located and gained access to a site left behind by inhabitants "
                "of this world, thousands of years ago. As you enter, strange power systems "
                "spring to life and indecipherable glyphs illuminate the halls."
            )},
            {"heading": "Setup", "body": (
                "◆ 3x3 table (ancient alien interior). Delve Device in each table quarter.\n"
                "◆ Deploy 6 characters from roster.\n"
                "◆ Delve Hazards placed each round (Sleepers, Traps, Environmental Hazards)."
            )},
            {"heading": "Objective", "body": (
                "Activate 3 Delve Devices (base contact + action + D6 roll for activation type). "
                "This reveals the Artifact location. Pick it up and escape via entrance or "
                "discovered exit."
            )},
            {"heading": "Rewards", "body": (
                "Random Alien Artifact (extracted by drone even if crew falls). "
                "+2 Research Points, +2 Build Points. Ancient Site removed from map."
            )},
        ],
    },
}


# ---------------------------------------------------------------------------
# Combat setup / loop / resolution helpers
# ---------------------------------------------------------------------------

def _setup_combat(
    ui: 'UIAdapter',
    state: GameState,
    mission_type: MissionType,
    deployed_chars: list[str],
    grunt_deploy: int,
    bot_deploy: bool,
    civilian_deploy: int,
    weapon_loadout: dict[str, str] | None,
    condition: object | None,
    slyn_briefing: dict | None,
    sector_id: int | None,
    save_fn: Callable[[], None],
):
    """Set up or resume a combat session.

    Returns (session, combat_state, first_slyn, prev_log_len).
    """
    from planetfall.engine.combat.session import CombatSession
    from planetfall.engine.combat.missions import setup_mission as combat_setup_mission

    # Check for saved combat session to resume
    saved_combat = state.turn_data.combat_session
    if saved_combat:
        try:
            session = CombatSession.from_dict(saved_combat)
            combat_state = session._snapshot()
            first_slyn = (
                saved_combat.get("mission_setup", {}).get("enemy_type") == "slyn"
                and state.enemies.slyn.encounters <= 1
            )
            # Rebuild mission briefing cache so the info panel shows on resume
            ms = saved_combat.get("mission_setup", {})
            if hasattr(ui, '_mission_briefing_cache'):
                cache = {
                    "mission_type": format_display(ms.get("mission_type", "")),
                    "enemy_info": ms.get("enemy_info", []),
                    "special_rules": ms.get("special_rules", []),
                    "victory_conditions": ms.get("victory_conditions", []),
                    "defeat_conditions": ms.get("defeat_conditions", []),
                    "enemy_type": ms.get("enemy_type", ""),
                }
                # Restore battlefield condition from turn data
                if condition and hasattr(condition, "name") and condition.name:
                    cond_data = {
                        "name": condition.name,
                        "description": condition.description,
                    }
                    if hasattr(condition, "effects_summary") and condition.effects_summary:
                        cond_data["effects_summary"] = condition.effects_summary
                    if hasattr(condition, "no_effect"):
                        cond_data["no_effect"] = condition.no_effect
                    cache["condition"] = cond_data
                ui._mission_briefing_cache = cache

            # Skip all setup — go straight to combat loop
            ui.reset_enemy_labels()
            ui.show_battlefield(session.bf)
            prev_log_len = len(combat_state.phase_log)
            return session, combat_state, first_slyn, prev_log_len
        except Exception:
            # Corrupted save — restart combat
            state.turn_data.combat_session = None

    # --- Fresh setup ---
    # Extract scout_at_risk for Scout Down missions
    scout_at_risk = None
    if mission_type == MissionType.SCOUT_DOWN:
        for ev in state.turn_log:
            effects = ev.state_changes.get("effects", {})
            if isinstance(effects, dict) and effects.get("mission_option") == "scout_down":
                scout_at_risk = ev.state_changes.get("scout_at_risk")
                break

    mission_setup = combat_setup_mission(
        state, mission_type, deployed_chars, grunt_deploy,
        bot_deploy=bot_deploy, civilian_deploy=civilian_deploy,
        scout_at_risk=scout_at_risk,
        weapon_loadout=weapon_loadout,
        sector_id=sector_id,
        condition=condition,
    )

    # Refresh lifeform table in sidebar (may have generated new lifeform)
    ui.show_lifeforms(state)

    # Let player choose deployment zones
    bf = mission_setup.battlefield
    # Exclude special figures (injured scout, colonists) from deployment selection
    player_figs = [
        f for f in bf.figures
        if f.side == FigureSide.PLAYER
        and "injured_scout" not in f.special_rules
        and f.char_class != "colonist"
    ]
    player_row = bf.rows - 1
    available_zones = [(player_row, c) for c in range(bf.cols)]

    # Check if this is a first Slyn encounter — mask identity
    has_slyn = any(f.char_class == "slyn" for f in bf.figures)
    first_slyn = has_slyn and state.enemies.slyn.encounters <= 1

    # Hide player figures until deployed
    hidden_players = [f for f in bf.figures if f.side == FigureSide.PLAYER]
    for f in hidden_players:
        bf.figures.remove(f)

    # Show mission intro modal
    mission_title = format_display(mission_type.value)
    intro = _MISSION_INTROS.get(mission_type)
    if intro:
        ui.show_mission_intro({
            "title": mission_title,
            "subtitle": intro.get("subtitle", ""),
            "sections": intro["sections"],
        })

    # Mask Slyn references if first encounter
    enemy_info = list(mission_setup.enemy_info)
    special_rules = list(mission_setup.special_rules)
    victory_conditions = list(mission_setup.victory_conditions)
    defeat_conditions = list(mission_setup.defeat_conditions)
    enemy_type_label = mission_setup.enemy_type
    if first_slyn:
        victory_conditions = [v.replace("Slyn", "Unknown Alien").replace("slyn", "unknown alien") for v in victory_conditions]
        defeat_conditions = [d.replace("Slyn", "Unknown Alien").replace("slyn", "unknown alien") for d in defeat_conditions]

    ui.reset_enemy_labels()
    ui.show_mission_briefing(
        bf,
        mission_type=mission_title,
        enemy_info=enemy_info,
        special_rules=[],
        victory_conditions=victory_conditions,
        defeat_conditions=defeat_conditions,
        enemy_type=enemy_type_label,
        slyn_unknown=first_slyn,
        condition=condition,
        slyn_briefing=slyn_briefing,
    )

    ui.pause("Begin deployment")
    ui.clear()
    ui.show_combat_phase("deployment", 0)

    # Scouting/science: rules require all figures within 1" = same zone
    from planetfall.engine.models import MissionType as MT
    same_zone = mission_setup.mission_type in (MT.SCOUTING, MT.SCIENCE)
    ui.prompt_deployment_zones(bf, player_figs, available_zones, same_zone=same_zone)

    session = CombatSession(mission_setup)
    combat_state = session.start_battle()

    # Show battlefield after deployment with players visible
    ui.reset_enemy_labels()
    ui.show_battlefield(session.bf)

    prev_log_len = 0
    return session, combat_state, first_slyn, prev_log_len


def _run_combat_loop(ui: 'UIAdapter', session, combat_state, prev_log_len, first_slyn, save_fn):
    """Main combat loop. Returns final combat_state."""
    while combat_state.phase.value != "battle_over":
        current_phase = combat_state.phase.value

        # Handle REACTION_ROLL phase — player assigns dice
        if current_phase == "reaction_roll":
            ui.clear()
            ui.show_combat_phase(current_phase, combat_state.round_number)
            ui.show_battlefield(session.bf)

            assignments = ui.prompt_reaction_assignment(
                combat_state.unassigned_dice,
                combat_state.reaction_figures,
            )
            combat_state = session.assign_reactions(assignments)
            save_fn()

            prev_log_len = len(combat_state.phase_log)
            continue

        if combat_state.available_actions:
            # Let player choose which figure to activate, with cancel-back support
            while True:
                queue = session.get_activation_queue()
                if len(queue) > 1:
                    valid = [
                        n for n in queue
                        if (f := session.bf.get_figure_by_name(n))
                        and f.is_alive and not f.has_acted
                    ]
                    if len(valid) > 1:
                        ui.clear()
                        ui.show_combat_phase(current_phase, combat_state.round_number)
                        ui.show_battlefield(session.bf, slyn_unknown=first_slyn)

                        if hasattr(ui, "prompt_figure_select"):
                            chosen_name = ui.prompt_figure_select(
                                "Activate which figure?", valid,
                            )
                        else:
                            from planetfall.cli.display import get_figure_map_label
                            fig_choices = []
                            for n in valid:
                                f = session.bf.get_figure_by_name(n)
                                label = get_figure_map_label(f)
                                cls = f.char_class.title() if f.char_class else ""
                                fig_choices.append(f"{n} ({label}) — {cls}")
                            chosen = ui.select("Activate which figure?", fig_choices)
                            chosen_name = chosen.split(" (")[0]
                        if chosen_name != queue[0]:
                            session.set_next_figure(chosen_name)
                            combat_state = session._snapshot()

                result = _handle_player_turn(
                    ui, session, combat_state, prev_log_len,
                    slyn_unknown=first_slyn,
                )
                if result is None:
                    # Player cancelled — loop back to figure selection
                    continue
                combat_state, prev_log_len = result
                save_fn()
                break
        elif current_phase == "enemy_phase":
            # Step through enemy activations one at a time
            ui.clear()
            ui.show_combat_phase(current_phase, combat_state.round_number)
            ui.show_battlefield(session.bf)

            while combat_state.phase.value == "enemy_phase":
                pre_step_len = len(combat_state.phase_log)
                combat_state = session.advance_enemy_step()
                new_log = combat_state.phase_log[pre_step_len:]
                substantive_log = [
                    l for l in new_log
                    if not l.startswith("---") and not l.startswith("===")
                ]
                if substantive_log:
                    ui.clear()
                    ui.show_combat_phase(
                        current_phase, combat_state.round_number,
                    )
                    ui.show_battlefield(session.bf)
                    ui.show_combat_log(substantive_log)
                    if combat_state.phase.value != "battle_over":
                        ui.pause()

            prev_log_len = len(combat_state.phase_log)
            save_fn()
        else:
            # Auto-advance (end phase, etc.)
            advancing_from = current_phase
            pre_advance_len = len(combat_state.phase_log)
            combat_state = session.advance()
            new_log = combat_state.phase_log[pre_advance_len:]
            substantive_log = [
                l for l in new_log
                if not l.startswith("---") and not l.startswith("===")
            ]

            # Always show End Phase with phase tracker
            if advancing_from in ("slow_actions", "quick_actions"):
                ui.clear()
                ui.show_combat_phase("end_phase", combat_state.round_number)
                ui.show_battlefield(session.bf)
                if substantive_log:
                    ui.show_combat_log(substantive_log)
                if combat_state.phase.value != "battle_over":
                    ui.pause()
            elif substantive_log:
                ui.clear()
                ui.show_combat_phase(
                    combat_state.phase.value, combat_state.round_number,
                )
                ui.show_battlefield(session.bf)
                ui.show_combat_log(substantive_log)
                if combat_state.phase.value != "battle_over":
                    ui.pause()
            prev_log_len = len(combat_state.phase_log)
            save_fn()

    return combat_state


def _resolve_combat(state: GameState, session, combat_state):
    """Extract results after battle. Returns (victory, char_casualties, grunt_casualties)."""
    from planetfall.engine.models import CombatResult

    # Combat finished — clear saved combat session
    state.turn_data.combat_session = None

    raw_result = session.get_result()
    final_result = CombatResult(**raw_result)
    mission_victory = final_result.victory
    character_casualties = list(final_result.character_casualties)
    grunt_casualties = final_result.grunt_casualties

    # Stash combat data for narrative and post-mission finds
    state.turn_data.combat_log = combat_state.phase_log
    state.turn_data.objectives_secured = final_result.objectives_secured
    state.turn_data.combat_result = final_result

    return mission_victory, character_casualties, grunt_casualties


def _run_interactive_combat(
    ui: UIAdapter,
    state: GameState,
    mission_type: MissionType,
    deployed_chars: list[str],
    grunt_deploy: int,
    _record: RecordFn,
    bot_deploy: bool = False,
    civilian_deploy: int = 0,
    weapon_loadout: dict[str, str] | None = None,
    condition: object = None,
    slyn_briefing: dict | None = None,
    sector_id: int | None = None,
) -> tuple[bool, list[str], int]:
    """Run interactive AI combat and return results."""
    from planetfall.engine.persistence import save_state as _persist

    def _save_combat():
        """Save combat state into turn_data for mid-combat resume."""
        state.turn_data.combat_session = session.to_dict()
        _persist(state)

    session, combat_state, first_slyn, prev_log_len = _setup_combat(
        ui, state, mission_type, deployed_chars, grunt_deploy,
        bot_deploy=bot_deploy, civilian_deploy=civilian_deploy,
        weapon_loadout=weapon_loadout, condition=condition,
        slyn_briefing=slyn_briefing, sector_id=sector_id,
        save_fn=_save_combat,
    )

    combat_state = _run_combat_loop(
        ui, session, combat_state, prev_log_len, first_slyn, _save_combat,
    )

    return _resolve_combat(state, session, combat_state)


def _run_manual_combat(
    ui: UIAdapter,
    state: GameState,
    mission_type: MissionType,
    deployed_chars: list[str],
    grunt_deploy: int,
    _record: RecordFn,
) -> tuple[bool, list[str], int]:
    """Run manual tabletop combat and collect results from player."""
    from planetfall.engine.steps import step08_mission

    mission_result, events = step08_mission.execute(state, mission_type)
    _record(events)

    ui.message(
        "\n  Resolve the mission using tabletop rules, "
        "then enter results below.\n", style="warning"
    )

    # Investigation missions: prompt for discovery marker results instead of win/lose
    if mission_type == MissionType.INVESTIGATION:
        return _resolve_manual_investigation(
            ui, state, mission_result, deployed_chars, grunt_deploy, _record,
        )

    mission_victory = ui.confirm("Did you win the mission?")
    mission_result.victory = mission_victory

    character_casualties: list[str] = []
    if deployed_chars:
        character_casualties = ui.checkbox(
            "Which characters became casualties?", deployed_chars,
        )
    mission_result.character_casualties = character_casualties

    grunt_casualties = 0
    if grunt_deploy > 0:
        grunt_casualties = ui.number(
            "How many grunts became casualties?",
            min_val=0, max_val=grunt_deploy,
        )
    mission_result.grunt_casualties = grunt_casualties

    # Ask for objectives secured on missions that use them
    objectives_secured = 0
    if mission_victory and mission_type == MissionType.SCOUTING:
        objectives_secured = ui.number(
            "How many Recon markers were successfully investigated?",
            min_val=0, max_val=6,
        )
    elif mission_victory and mission_type == MissionType.EXPLORATION:
        objectives_secured = ui.number(
            "How many objectives were secured?",
            min_val=0, max_val=10,
        )
    state.turn_data.objectives_secured = objectives_secured

    # Store combat result for battle concluded display
    from planetfall.engine.models import CombatResult
    state.turn_data.combat_result = CombatResult(
        victory=mission_victory,
        rounds_played=0,
        enemies_killed=0,
        character_casualties=character_casualties,
        grunt_casualties=grunt_casualties,
        objectives_secured=objectives_secured,
    )

    return mission_victory, character_casualties, grunt_casualties


def _resolve_manual_investigation(
    ui: UIAdapter,
    state: GameState,
    mission_result,
    deployed_chars: list[str],
    grunt_deploy: int,
    _record: RecordFn,
) -> tuple[bool, list[str], int]:
    """Resolve a manual investigation mission by prompting for discovery results."""
    from planetfall.engine.dice import roll_d6
    from planetfall.engine.models import TurnEvent, TurnEventType

    # --- Discovery markers ---
    discoveries_completed = ui.number(
        "How many Discovery markers were investigated?",
        min_val=0, max_val=4,
    )

    discovery_results = {
        "enemy": 0, "rewards": 0, "contact": 0,
        "action_required": 0, "data": 0,
    }
    discovery_choices = [
        "1 — Enemy (Sleeper placed)",
        "2 — Rewards (Post-Mission Find)",
        "3 — Contact (Lifeform placed)",
        "4 — Action Required (D6+Savvy, 5+ = 1 Raw Material)",
        "5-6 — Data (Mission Data collected)",
    ]

    for i in range(discoveries_completed):
        result = ui.select(
            f"Discovery marker {i + 1} result:",
            discovery_choices,
        )
        if result.startswith("1"):
            discovery_results["enemy"] += 1
        elif result.startswith("2"):
            discovery_results["rewards"] += 1
        elif result.startswith("3"):
            discovery_results["contact"] += 1
        elif result.startswith("4"):
            discovery_results["action_required"] += 1
        elif result.startswith("5"):
            discovery_results["data"] += 1

    # --- Apply discovery effects ---
    events: list[TurnEvent] = []

    # Action Required: prompt for savvy check result
    for i in range(discovery_results["action_required"]):
        success = ui.confirm(
            f"Action Required #{i + 1}: Did the character pass the D6+Savvy >= 5 check?",
            default=False,
        )
        if success:
            state.colony.resources.raw_materials += 1
            events.append(TurnEvent(
                step=8, event_type=TurnEventType.MISSION,
                description="Action Required: Savvy check passed — +1 Raw Materials.",
            ))
        else:
            events.append(TurnEvent(
                step=8, event_type=TurnEventType.MISSION,
                description="Action Required: Savvy check failed.",
            ))

    # Mission Data — process one at a time, each triggers a breakthrough check
    from planetfall.engine.campaign.ancient_signs import check_mission_data_breakthrough
    for i in range(discovery_results["data"]):
        state.campaign.mission_data_count += 1
        events.append(TurnEvent(
            step=8, event_type=TurnEventType.MISSION,
            description=(
                f"Mission Data #{i + 1} collected "
                f"(total: {state.campaign.mission_data_count})."
            ),
        ))
        bt_events = check_mission_data_breakthrough(state)
        events.extend(bt_events)

    # --- Casualties ---
    character_casualties: list[str] = []
    if deployed_chars:
        character_casualties = ui.checkbox(
            "Which characters became casualties?", deployed_chars,
        )
    mission_result.character_casualties = character_casualties

    grunt_casualties = 0
    if grunt_deploy > 0:
        grunt_casualties = ui.number(
            "How many grunts became casualties?",
            min_val=0, max_val=grunt_deploy,
        )
    mission_result.grunt_casualties = grunt_casualties

    # Investigation is always considered a "victory" for post-mission purposes
    mission_victory = True
    mission_result.victory = mission_victory

    # Store results
    objectives_secured = discoveries_completed
    state.turn_data.objectives_secured = objectives_secured
    state.turn_data.combat_result = CombatResult(
        victory=mission_victory,
        rounds_played=0,
        enemies_killed=0,
        character_casualties=character_casualties,
        grunt_casualties=grunt_casualties,
        objectives_secured=objectives_secured,
        investigation_results=discovery_results,
    )

    # Record discovery events
    desc = f"Investigation complete: {discoveries_completed}/4 Discovery markers investigated."
    if discovery_results["rewards"] > 0:
        desc += f" {discovery_results['rewards']}x Rewards (Post-Mission Find rolls)."
    if discovery_results["data"] > 0:
        desc += f" {discovery_results['data']}x Mission Data collected."
    events.insert(0, TurnEvent(
        step=8, event_type=TurnEventType.MISSION,
        description=desc,
    ))
    _record(events)

    return mission_victory, character_casualties, grunt_casualties

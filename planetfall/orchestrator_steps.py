"""Step helper functions for the local orchestrator.

Extracted from run_campaign_turn_local() to keep each step's logic
isolated and the main loop readable.
"""

from __future__ import annotations

from typing import Callable

from planetfall.engine.models import (
    CharacterClass, GameState, MissionType, SectorStatus,
    TurnEvent, TurnEventType,
)
from planetfall.engine.combat.battlefield import FigureSide


# Type alias for the record/narrate callbacks passed from the orchestrator
RecordFn = Callable[[list[TurnEvent]], None]
NarrateFn = Callable[[str], None]


def execute_step03_scout(
    state: GameState,
    _record: RecordFn,
) -> None:
    """Step 3: Scout Reports — explore sectors and roll discoveries."""
    from planetfall.engine.steps import step03_scout_reports, step09_injuries
    from planetfall.cli import prompts, display

    unexplored = [
        s for s in state.campaign_map.sectors
        if s.status == SectorStatus.UNKNOWN
        and s.sector_id != state.campaign_map.colony_sector_id
    ]
    if unexplored:
        valid_ids = [s.sector_id for s in unexplored]
        sector_id = prompts.ask_sector_coords("Scout which sector?", valid_ids)
        events = step03_scout_reports.execute_scout_explore(state, sector_id)
        _record(events)
        # Redraw with updated map
        display.clear_screen()
        display.print_colony_status(state)
        display.print_map(state)
        display.print_events(events)
    else:
        display.console.print("  [dim]No unexplored sectors to scout.[/dim]")

    if prompts.ask_confirm("Roll on Scout Discovery table?", default=True):
        available_scouts = [
            c for c in state.characters
            if c.char_class == CharacterClass.SCOUT and c.is_available
        ]
        if available_scouts:
            scout_choices = [c.name for c in available_scouts] + ["None (no scout assigned)"]
            choice = prompts.ask_select("Assign a scout to lead?", scout_choices)
            scout_name = None if choice.startswith("None") else choice
        else:
            scout_name = None
        events = step03_scout_reports.execute_scout_discovery(state, scout_name)
        _record(events)
        # Redraw with discovery results
        display.clear_screen()
        display.print_colony_status(state)
        display.print_map(state)
        display.print_events(events)

        _handle_scout_pending_choices(state, events, _record)


def _handle_scout_pending_choices(
    state: GameState,
    events: list[TurnEvent],
    _record: RecordFn,
) -> None:
    """Handle pending player choices from scout discovery results."""
    from planetfall.engine.steps import step09_injuries
    from planetfall.cli import prompts

    for ev in events:
        ctx = ev.state_changes.get("narrative_context", {})
        if ctx.get("pending_choice") == "scout_down_or_escape":
            _handle_scout_down(state, ctx, _record)
        elif ctx.get("pending_choice") == "rescue_or_morale":
            _handle_rescue_or_morale(state, ctx, _record)
        elif ctx.get("pending_choice") == "exploration_report":
            _handle_exploration_report(state, _record)


def _handle_scout_down(
    state: GameState,
    ctx: dict,
    _record: RecordFn,
) -> None:
    """Handle the scout down/escape choice."""
    from planetfall.engine.steps import step09_injuries
    from planetfall.cli import prompts

    scout_at_risk = ctx.get("scout_at_risk")
    if not scout_at_risk:
        no_survivor = TurnEvent(
            step=3,
            event_type=TurnEventType.SCOUT_REPORT,
            description="Scout vehicle crashed with no assigned scout. No survivors.",
        )
        _record([no_survivor])
        return

    sd_choice = prompts.ask_select(
        f"{scout_at_risk} is down! Choose resolution:",
        [
            "Escape on foot — roll on injury table, +2 XP if survive",
            "Play the Scout Down! mission to rescue them",
        ],
    )
    if sd_choice.startswith("Escape"):
        inj_events = step09_injuries.execute(
            state, character_casualties=[scout_at_risk],
        )
        _record(inj_events)
        for c in state.characters:
            if c.name == scout_at_risk:
                c.xp += 2
                xp_ev = TurnEvent(
                    step=3,
                    event_type=TurnEventType.CHARACTER_EVENT,
                    description=f"{scout_at_risk} escaped on foot. +2 XP.",
                )
                _record([xp_ev])
                break
    else:
        sd_flag = TurnEvent(
            step=3,
            event_type=TurnEventType.SCOUT_REPORT,
            description=f"Scout Down! mission flagged to rescue {scout_at_risk}.",
            state_changes={
                "effects": {"mission_option": "scout_down"},
                "scout_at_risk": scout_at_risk,
            },
        )
        _record([sd_flag])


def _handle_rescue_or_morale(
    state: GameState,
    ctx: dict,
    _record: RecordFn,
) -> None:
    """Handle the rescue vs morale penalty choice."""
    from planetfall.cli import prompts

    sos_choice = prompts.ask_select(
        "Distress signal received! Choose resolution:",
        [
            "Play the Rescue mission",
            f"Decline — lose {abs(ctx.get('decline_morale_penalty', -3))} Morale",
        ],
    )
    if sos_choice.startswith("Play"):
        rescue_ev = TurnEvent(
            step=3,
            event_type=TurnEventType.SCOUT_REPORT,
            description="Rescue mission accepted — must play Rescue this turn.",
            state_changes={"effects": {"mission_option": "rescue"}},
        )
        _record([rescue_ev])
    else:
        penalty = ctx.get("decline_morale_penalty", -3)
        state.colony.morale += penalty
        decline_ev = TurnEvent(
            step=3,
            event_type=TurnEventType.MORALE,
            description=f"Distress signal ignored. Morale {penalty}.",
        )
        _record([decline_ev])


def _handle_exploration_report(
    state: GameState,
    _record: RecordFn,
) -> None:
    """Handle the Exploration Report pending choice — player picks a sector to explore."""
    from planetfall.engine.steps.step03_scout_reports import _apply_exploration_report
    from planetfall.cli import display, prompts

    unexplored = [
        s for s in state.campaign_map.sectors
        if s.status == SectorStatus.UNKNOWN
        and s.sector_id != state.campaign_map.colony_sector_id
    ]
    if not unexplored:
        ev = TurnEvent(
            step=3,
            event_type=TurnEventType.SCOUT_REPORT,
            description="Exploration Report: No unexplored sectors remaining.",
        )
        _record([ev])
        return

    valid_ids = [s.sector_id for s in unexplored]
    sector_id = prompts.ask_sector_coords(
        "Exploration Report — choose a sector to explore:", valid_ids,
    )

    desc, dice = _apply_exploration_report(state, sector_id)
    ev = TurnEvent(
        step=3,
        event_type=TurnEventType.SCOUT_REPORT,
        description=f"Exploration Report: {desc}",
        dice_rolls=dice,
    )
    _record([ev])
    # Redraw with updated map
    display.clear_screen()
    display.print_colony_status(state)
    display.print_map(state)
    display.print_events([ev])


def execute_step05_colony_events(
    state: GameState,
    _record: RecordFn,
) -> None:
    """Step 5: Colony Events — roll and handle player choices."""
    from planetfall.engine.steps import step05_colony_events
    from planetfall.engine.dice import roll_d6, roll_nd6
    from planetfall.cli import prompts

    events = step05_colony_events.execute(state)
    _record(events)

    # Handle events requiring player choices
    for ev in events:
        effects = ev.state_changes.get("effects", {})
        event_id = ev.state_changes.get("event", "")

        if effects.get("character_xp_d6"):
            # report_on_progress: Select one character to earn 1D6 XP
            available = [c.name for c in state.characters if c.is_available]
            if available:
                chosen = prompts.ask_select(
                    "Select a character to earn 1D6 XP:", available,
                )
                xp_roll = roll_d6("Report on Progress XP")
                for c in state.characters:
                    if c.name == chosen:
                        c.xp += xp_roll.total
                        break
                xp_ev = TurnEvent(
                    step=5,
                    event_type=TurnEventType.CHARACTER_EVENT,
                    description=f"{chosen} earns {xp_roll.total} XP from Report on Progress.",
                )
                _record([xp_ev])

        if effects.get("bench_character"):
            # public_relations_demand: Bench a character or lose morale
            available = [c.name for c in state.characters if c.is_available]
            choices = [f"Bench {name} (unavailable this turn)" for name in available]
            choices.append(f"Decline — lose {abs(effects.get('decline_morale', -2))} Morale")
            choice = prompts.ask_select("Public Relations Demand:", choices)
            if choice.startswith("Decline"):
                penalty = effects.get("decline_morale", -2)
                state.colony.morale += penalty
                _record([TurnEvent(
                    step=5, event_type=TurnEventType.MORALE,
                    description=f"Declined PR demand. Morale {penalty}.",
                )])
            else:
                benched = available[choices.index(choice)]
                for c in state.characters:
                    if c.name == benched:
                        c.sick_bay_turns = max(c.sick_bay_turns, 1)
                        break
                _record([TurnEvent(
                    step=5, event_type=TurnEventType.CHARACTER_EVENT,
                    description=f"{benched} assigned to PR duties — unavailable this turn.",
                )])

        if effects.get("new_character_or_xp"):
            # specialist_training: Add new character OR grant XP to existing
            xp_amount = effects["new_character_or_xp"]
            has_vacancy = len(state.characters) < 8
            options = []
            if has_vacancy:
                options.append("Add a new character to roster")
            options.append(f"Grant +{xp_amount} XP to an existing character")
            choice = prompts.ask_select("Specialist Training:", options)
            if choice.startswith("Grant"):
                available = [c.name for c in state.characters]
                chosen = prompts.ask_select("Select character for XP:", available)
                for c in state.characters:
                    if c.name == chosen:
                        c.xp += xp_amount
                        break
                _record([TurnEvent(
                    step=5, event_type=TurnEventType.CHARACTER_EVENT,
                    description=f"{chosen} earns {xp_amount} XP from Specialist Training.",
                )])
            else:
                # Flag for new character creation (handled elsewhere)
                _record([TurnEvent(
                    step=5, event_type=TurnEventType.CHARACTER_EVENT,
                    description="New character slot opened from Specialist Training.",
                    state_changes={"add_character": True},
                )])

        if effects.get("heal_turns"):
            # experimental_medicine: Select an injured character to heal
            injured = [
                c.name for c in state.characters if c.sick_bay_turns > 0
            ]
            if injured:
                chosen = prompts.ask_select(
                    "Select an injured character to reduce recovery:", injured,
                )
                heal = effects["heal_turns"]
                for c in state.characters:
                    if c.name == chosen:
                        c.sick_bay_turns = max(0, c.sick_bay_turns - heal)
                        status = (
                            "fully recovered" if c.sick_bay_turns == 0
                            else f"{c.sick_bay_turns} turns remaining"
                        )
                        break
                _record([TurnEvent(
                    step=5, event_type=TurnEventType.CHARACTER_EVENT,
                    description=f"{chosen} treated with experimental medicine — {status}.",
                )])

        if effects.get("supply_ship"):
            # supply_ship: Choose priority resource, roll 2D6
            priority = prompts.ask_select(
                "Supply Ship — prioritize which resource?",
                ["Research Points", "Build Points"],
            )
            rolls = roll_nd6(2, "Supply Ship")
            high = max(rolls.values)
            low = min(rolls.values)
            if priority == "Research Points":
                state.colony.resources.research_points += high
                state.colony.resources.build_points += low
                desc = f"Supply Ship: {high} Research Points, {low} Build Points."
            else:
                state.colony.resources.build_points += high
                state.colony.resources.research_points += low
                desc = f"Supply Ship: {high} Build Points, {low} Research Points."
            _record([TurnEvent(
                step=5, event_type=TurnEventType.COLONY_EVENT,
                description=desc,
            )])

        if effects.get("free_scout"):
            # new_scout_recruits: Free scout action — explore a sector
            from planetfall.engine.steps import step03_scout_reports
            from planetfall.cli import display
            unexplored = [
                s for s in state.campaign_map.sectors
                if s.status == SectorStatus.UNKNOWN
                and s.sector_id != state.campaign_map.colony_sector_id
            ]
            if unexplored:
                valid_ids = [s.sector_id for s in unexplored]
                sector_id = prompts.ask_sector_coords(
                    "Free Scout Action — choose a sector to explore:", valid_ids,
                )
                scout_events = step03_scout_reports.execute_scout_explore(
                    state, sector_id,
                )
                _record(scout_events)
                display.clear_screen()
                display.print_colony_status(state)
                display.print_map(state)
                display.print_events(scout_events)
            else:
                _record([TurnEvent(
                    step=5, event_type=TurnEventType.COLONY_EVENT,
                    description="Free Scout Action: No unexplored sectors remaining.",
                )])


def execute_step04_enemy(
    state: GameState,
    _record: RecordFn,
) -> None:
    """Step 4: Enemy Activity — with optional SP prevention."""
    from planetfall.engine.steps import step04_enemy_activity
    from planetfall.cli import prompts

    active_enemies = [e for e in state.enemies.tactical_enemies if not e.defeated]
    if not active_enemies:
        from planetfall.cli import display
        display.console.print("  [dim]No active Tactical Enemies. Skipping enemy activity.[/dim]")
        return

    skip_enemy = False
    if state.colony.resources.story_points >= 1:
        skip_enemy = prompts.ask_confirm(
            f"Spend 1 Story Point to skip Enemy Activity roll? "
            f"({state.colony.resources.story_points} SP available)",
            default=False,
        )
        if skip_enemy:
            from planetfall.engine.campaign.story_points import spend_to_prevent_roll
            sp_events = spend_to_prevent_roll(state, "enemy_activity")
            _record(sp_events)
    if not skip_enemy:
        events = step04_enemy_activity.execute(state)
        _record(events)


def execute_step06_mission(
    state: GameState,
    _record: RecordFn,
) -> tuple[MissionType, int | None]:
    """Step 6: Mission Determination — choose mission and sector."""
    from planetfall.engine.steps import step06_mission_determination
    from planetfall.cli import display, prompts

    mission_options = step06_mission_determination.get_available_missions(state)
    display.print_mission_options(mission_options)

    if len(mission_options) == 1 and mission_options[0].get("forced"):
        mission_idx = 0
        display.console.print("  [red]Forced mission — no choice available.[/red]")
    else:
        mission_idx = prompts.prompt_mission_choice(mission_options)

    chosen = mission_options[mission_idx]
    mission_type = chosen["type"]

    sector_id = chosen.get("sector_id")
    target_sectors = chosen.get("target_sectors")
    if target_sectors and len(target_sectors) > 1 and sector_id is None:
        sector_id = prompts.ask_sector_coords(
            "Which sector?", target_sectors,
        )
    elif target_sectors and len(target_sectors) == 1:
        sector_id = target_sectors[0]

    events = step06_mission_determination.execute(state, mission_type, sector_id)
    _record(events)

    return mission_type, sector_id


def execute_step07_deploy(
    state: GameState,
    mission_type: MissionType,
    _record: RecordFn,
) -> tuple[list[str], int, bool, int, dict[str, str]]:
    """Step 7: Lock and Load — deploy characters, grunts, bot, civilians.

    Returns (deployed, grunts, bot, civilians, weapon_loadout).
    """
    from planetfall.engine.steps import step07_lock_and_load
    from planetfall.cli import display, prompts

    available = step07_lock_and_load.get_available_characters(state)
    max_slots = step07_lock_and_load.get_deployment_slots(mission_type.value)
    available_names = [c.name for c in available]

    deployment = prompts.prompt_deployment(
        available_names,
        max_slots,
        grunt_count=state.grunts.count,
        bot_available=state.grunts.bot_operational,
        civilians_available=True,
    )

    deployed_chars = deployment["characters"]
    grunt_deploy = deployment["grunts"]
    bot_deploy = deployment["bot"]
    civilian_deploy = deployment.get("civilians", 0)

    # Weapon selection — Lock and Load
    display.console.print("\n[bold yellow]═══ Lock and Load ═══[/bold yellow]")
    display.console.print("[dim]Choose weapons for each character.[/dim]\n")
    weapon_loadout = prompts.prompt_loadout(
        state, deployed_chars, bot_deploy, grunt_count=grunt_deploy,
    )

    events = step07_lock_and_load.execute(
        state, deployed_chars, grunt_deploy, mission_type.value, bot_deploy,
    )
    _record(events)

    if weapon_loadout:
        loadout_desc = ", ".join(f"{name}: {wpn}" for name, wpn in weapon_loadout.items())
        _record([TurnEvent(
            step=7,
            event_type=TurnEventType.MISSION,
            description=f"Weapon loadout: {loadout_desc}",
            state_changes={"weapon_loadout": weapon_loadout},
        )])

    return deployed_chars, grunt_deploy, bot_deploy, civilian_deploy, weapon_loadout


def execute_step08_mission(
    state: GameState,
    mission_type: MissionType,
    deployed_chars: list[str],
    grunt_deploy: int,
    _record: RecordFn,
    bot_deploy: bool = False,
    civilian_deploy: int = 0,
    weapon_loadout: dict[str, str] | None = None,
) -> tuple[bool, list[str], int]:
    """Step 8: Play Out Mission — interactive or manual. Returns (victory, casualties, grunt_casualties)."""
    from planetfall.engine.steps import step08_mission
    from planetfall.cli import display, prompts

    combat_mode_choices = ["Interactive (AI combat)", "Manual (tabletop)"]
    combat_mode_choice = prompts.ask_select("Combat mode?", combat_mode_choices)
    use_interactive = combat_mode_choice.startswith("Interactive")

    if use_interactive and deployed_chars:
        return _run_interactive_combat(
            state, mission_type, deployed_chars, grunt_deploy, _record,
            bot_deploy, civilian_deploy, weapon_loadout=weapon_loadout,
        )
    else:
        return _run_manual_combat(
            state, mission_type, deployed_chars, grunt_deploy, _record,
        )


# ---------------------------------------------------------------------------
# Multi-step player turn helpers
# ---------------------------------------------------------------------------

def _get_move_zones(bf, fig):
    """Valid standard move destinations for a figure.

    Returns [(zone, terrain_label, [fig_names_in_zone], is_jump), ...]
    """
    from planetfall.engine.combat.battlefield import (
        move_zones as calc_move_zones, TerrainType,
    )
    num_move = calc_move_zones(fig.speed)
    if num_move == 0:
        return []

    is_scout = fig.char_class == "scout"
    adj_zones = bf.adjacent_zones(*fig.zone)

    if is_scout:
        raw = bf.jump_destinations(*fig.zone, num_move)
    elif num_move >= 2:
        raw = []
        for dr in range(-num_move, num_move + 1):
            for dc in range(-num_move, num_move + 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = fig.zone[0] + dr, fig.zone[1] + dc
                if (0 <= nr < bf.rows and 0 <= nc < bf.cols
                        and max(abs(dr), abs(dc)) <= num_move):
                    if bf.get_zone(nr, nc).terrain != TerrainType.IMPASSABLE:
                        raw.append((nr, nc))
    else:
        raw = [z for z in adj_zones
               if bf.get_zone(*z).terrain != TerrainType.IMPASSABLE]

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
    Uses Chebyshev distance (same as movement overlay).
    Scouts can land on impassable terrain via jump jets.
    Returns [(zone, terrain_label, [fig_names], is_jump), ...]
    """
    from planetfall.engine.combat.battlefield import (
        TerrainType, rush_total_zones,
    )
    max_dist = rush_total_zones(fig.speed)
    is_scout = fig.char_class == "scout"

    results = []
    for dr in range(-max_dist, max_dist + 1):
        for dc in range(-max_dist, max_dist + 1):
            if dr == 0 and dc == 0:
                continue
            nr, nc = fig.zone[0] + dr, fig.zone[1] + dc
            if not (0 <= nr < bf.rows and 0 <= nc < bf.cols):
                continue
            if max(abs(dr), abs(dc)) > max_dist:
                continue
            zone = (nr, nc)
            terrain_type = bf.get_zone(nr, nc).terrain
            if not is_scout and terrain_type == TerrainType.IMPASSABLE:
                continue
            if not bf.zone_has_capacity(nr, nc, fig.side):
                continue
            terrain = terrain_type.value.replace("_", " ")
            figs = [f.name for f in bf.get_figures_in_zone(nr, nc)]
            is_jump = is_scout and terrain_type == TerrainType.IMPASSABLE
            results.append((zone, terrain, figs, is_jump))
    return results


def _enemies_in_range(bf, fig, from_zone):
    """Return set of enemy names within weapon range from a zone (for highlighting)."""
    from planetfall.engine.combat.battlefield import zone_range_inches, FigureSide
    names = set()
    for e in bf.figures:
        if e.side != FigureSide.ENEMY or not e.is_alive or e.is_contact:
            continue
        dist = bf.zone_distance(from_zone, e.zone)
        if zone_range_inches(dist) <= fig.weapon_range:
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
                range_label = "close" if approx_range <= 6 else "medium" if approx_range <= 18 else "long"
                results.append({
                    "name": enemy.name,
                    "map_label": get_figure_map_label(enemy),
                    "eff_label": eff_label,
                    "eff": eff,
                    "range_label": range_label,
                    "shots": fig.weapon_shots,
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


def _print_figure_stats(fig):
    """Print active figure stats, weapon, and status above the action prompt."""
    from planetfall.cli.display import console, get_figure_map_label

    label = get_figure_map_label(fig)
    class_str = fig.char_class.title() if fig.char_class else ""

    # Line 1: name, class, core stats
    parts = [f"[bold]{fig.name}[/bold] ({label})"]
    if class_str:
        parts.append(f"[dim]{class_str}[/dim]")
    console.print(f"\n  {' — '.join(parts)}")

    stat_parts = [
        f"Spd {fig.speed}",
        f"React {fig.reactions}",
        f"CS +{fig.combat_skill}",
        f"Tough {fig.toughness}",
        f"Savvy +{fig.savvy}",
    ]
    if fig.armor_save:
        stat_parts.append(f"Armor {fig.armor_save}+")
    console.print(f"  [dim]{' | '.join(stat_parts)}[/dim]")

    # Line 2: weapon
    weapon_parts = [f"[yellow]{fig.weapon_name or 'Unarmed'}[/yellow]"]
    weapon_parts.append(f"Range {fig.weapon_range}\"")
    weapon_parts.append(f"Shots {fig.weapon_shots}")
    if fig.weapon_damage:
        weapon_parts.append(f"Dmg +{fig.weapon_damage}")
    if fig.weapon_traits:
        weapon_parts.append(f"Traits: {', '.join(fig.weapon_traits)}")
    console.print(f"  {' | '.join(weapon_parts)}")

    # Line 3: statuses (only if any)
    statuses = []
    if fig.stun_markers:
        statuses.append(f"[yellow]Stun x{fig.stun_markers}[/yellow]")
    if fig.status.value == "sprawling":
        statuses.append("[red]Sprawling[/red]")
    if fig.aid_marker:
        statuses.append("[green]Aid marker[/green]")
    if fig.hit_bonus:
        statuses.append(f"[cyan]Hit +{fig.hit_bonus}[/cyan]")
    if statuses:
        console.print(f"  {' | '.join(statuses)}")


def _prompt_with_overlay(session, fig, choices, prompt_text, default_overlay, phase_str, round_num, log_entries, slyn_unknown=False, highlighted_enemies=None):
    """Show battlefield + prompt with overlay cycling.

    Returns the selected choice string (not the overlay cycle label).
    """
    from planetfall.cli import display, prompts

    overlay_modes = [
        display.OVERLAY_VISION, display.OVERLAY_MOVEMENT, display.OVERLAY_SHOOTING,
    ]
    overlay_names = ["Vision", "Movement", "Shooting"]
    overlay_idx = overlay_modes.index(default_overlay) if default_overlay in overlay_modes else 0

    while True:
        overlay_mode = overlay_modes[overlay_idx]
        display.clear_screen()
        display.print_combat_phase(phase_str, round_num)
        display.print_battlefield(
            session.bf, active_fig=fig, overlay_mode=overlay_mode,
            slyn_unknown=slyn_unknown,
            highlighted_enemies=highlighted_enemies,
        )
        if log_entries:
            display.print_combat_log(log_entries)
        _print_figure_stats(fig)

        next_name = overlay_names[(overlay_idx + 1) % len(overlay_names)]
        cycle_label = f"[Overlay: {overlay_names[overlay_idx]} → {next_name}]"
        all_choices = list(choices) + [cycle_label]

        choice = prompts.ask_select(prompt_text, all_choices)
        if choice == cycle_label:
            overlay_idx = (overlay_idx + 1) % len(overlay_modes)
            continue
        return choice


def _handle_player_turn(session, combat_state, prev_log_len, slyn_unknown=False):
    """Multi-step player turn: movement type → location → action → target → scout post-move.

    Returns (new_combat_state, new_prev_log_len).
    """
    from planetfall.cli import display, prompts
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

    move_to = None
    action_type = "hold"
    target_name = None
    use_aid = False
    scout_action_first = False
    trooper_delay = False
    dashed = False

    # Enemies in range from current position (for movement phase highlighting)
    in_range = _enemies_in_range(session.bf, fig, fig.zone)

    # === STEP 1: Movement Type (with movement overlay) ===
    if is_delayed:
        # Delayed trooper returning in slow phase: no movement, just action
        pass
    else:
        move_choices = ["Stay stationary"]
        if num_move > 0:
            move_choices.append("Move")
        if can_dash:
            move_choices.append("Dash")
        if is_scout:
            move_choices.append("Take action first, then move")

        # Trooper staying stationary in quick phase enables delay
        if is_trooper and in_quick:
            trooper_delay = True  # will be cleared if they choose to move

        if len(move_choices) == 1:
            move_type = move_choices[0]
        else:
            move_type = _prompt_with_overlay(
                session, fig, move_choices, "Movement:",
                display.OVERLAY_MOVEMENT, phase_str, round_num, log_entries,
                slyn_unknown=slyn_unknown, highlighted_enemies=in_range,
            )

        if move_type == "Move":
            trooper_delay = False
            # === STEP 2a: Move Location ===
            move_zones = _get_move_zones(session.bf, fig)
            if move_zones:
                zone_descs = []
                for zone, terrain, figs_in_zone, is_jump in move_zones:
                    label = "Jump to" if is_jump else "Move to"
                    desc = f"{label} ({zone[0]},{zone[1]}) ({terrain})"
                    if figs_in_zone:
                        desc += f" [{', '.join(figs_in_zone)}]"
                    zone_descs.append(desc)

                choice = _prompt_with_overlay(
                    session, fig, zone_descs, "Move to:",
                    display.OVERLAY_MOVEMENT, phase_str, round_num, log_entries,
                    slyn_unknown=slyn_unknown, highlighted_enemies=in_range,
                )
                idx = zone_descs.index(choice)
                move_to = move_zones[idx][0]

        elif move_type == "Dash":
            trooper_delay = False
            dashed = True
            # === STEP 2b: Dash Location ===
            dash_zones = _get_dash_zones(session.bf, fig)
            if dash_zones:
                dash_descs = []
                for zone, terrain, figs_in_zone, is_jump in dash_zones:
                    label = "Jump to" if is_jump else "Dash to"
                    desc = f"{label} ({zone[0]},{zone[1]}) ({terrain})"
                    if figs_in_zone:
                        desc += f" [{', '.join(figs_in_zone)}]"
                    dash_descs.append(desc)

                choice = _prompt_with_overlay(
                    session, fig, dash_descs, "Dash to:",
                    display.OVERLAY_MOVEMENT, phase_str, round_num, log_entries,
                    slyn_unknown=slyn_unknown, highlighted_enemies=in_range,
                )
                idx = dash_descs.index(choice)
                move_to = dash_zones[idx][0]
            action_type = "rush"

        elif move_type.startswith("Take action"):
            trooper_delay = False
            scout_action_first = True

        # "Stay stationary" — trooper_delay stays True if applicable

    # Temporarily move fig to chosen destination so overlays render correctly
    original_zone = fig.zone
    if move_to and not scout_action_first:
        fig.zone = move_to

    # Update in-range enemies from new position for action phase
    action_zone = move_to if move_to else original_zone
    in_range = _enemies_in_range(session.bf, fig, action_zone)

    # === STEP 3: Action (skip if dashed — dash consumes the action) ===
    action_choice = None
    if not dashed:

        action_choices = []

        # Shoot
        shoot_targets = _get_shoot_targets(
            session.bf, fig, action_zone, moved=(move_to is not None),
        )
        if shoot_targets:
            action_choices.append("Shoot")

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

        action_choice = _prompt_with_overlay(
            session, fig, action_choices, "Action:",
            display.OVERLAY_SHOOTING, phase_str, round_num, log_entries,
            slyn_unknown=slyn_unknown, highlighted_enemies=in_range,
        )

        # === STEP 4: Action Target ===
        if action_choice == "Shoot":
            shoot_descs = []
            for t in shoot_targets:
                desc = (
                    f"{t['name']} ({t['map_label']}) at {t['range_label']} range "
                    f"({t['eff_label']}, {t['shots']} shot(s))"
                )
                shoot_descs.append(desc)
            if fig.aid_marker:
                for t in shoot_targets:
                    aided_eff = max(1, t["eff"] - 1)
                    aided_label = "auto" if aided_eff <= 1 else f"{aided_eff}+"
                    desc = (
                        f"{t['name']} ({t['map_label']}) at {t['range_label']} range "
                        f"({aided_label}, {t['shots']} shot(s)) [spend Aid +1]"
                    )
                    shoot_descs.append(desc)

            choice = _prompt_with_overlay(
                session, fig, shoot_descs, "Shoot:",
                display.OVERLAY_SHOOTING, phase_str, round_num, log_entries,
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
                    session, fig, brawl_descs, "Brawl:",
                    display.OVERLAY_VISION, phase_str, round_num, log_entries,
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
                session, fig, aid_descs, "Aid:",
                display.OVERLAY_VISION, phase_str, round_num, log_entries,
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
            move_to = None  # Don't move, just leave from current position

        elif action_choice == "Hold":
            if move_to:
                action_type = "move"
            else:
                action_type = "hold"

    # === STEP 5: Scout Post-Action Move ===
    if scout_action_first:
        if action_type == "shoot":
            action_type = "shoot_and_move"

        scout_move_zones = _get_move_zones(session.bf, fig)
        if scout_move_zones:
            scout_descs = ["Stay stationary"]
            for zone, terrain, figs_in_zone, is_jump in scout_move_zones:
                label = "Jump to" if is_jump else "Move to"
                desc = f"{label} ({zone[0]},{zone[1]}) ({terrain})"
                if figs_in_zone:
                    desc += f" [{', '.join(figs_in_zone)}]"
                scout_descs.append(desc)

            choice = _prompt_with_overlay(
                session, fig, scout_descs, "Scout move:",
                display.OVERLAY_MOVEMENT, phase_str, round_num, log_entries,
                slyn_unknown=slyn_unknown, highlighted_enemies=in_range,
            )
            if choice != "Stay stationary":
                idx = scout_descs.index(choice) - 1
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

    # Handle trooper delay: queue for slow phase
    if trooper_delay and action_choice and action_choice != "Hold":
        session.queue_for_slow_phase(fig.name)

    # Redraw map after action — use full_log to avoid missing entries
    # when round advances and phase_log resets
    new_log = session.full_log[full_log_before:]
    # Filter out phase/round separators
    substantive = [
        l for l in new_log
        if not l.startswith("---") and not l.startswith("===")
    ]
    if substantive:
        display.clear_screen()
        display.print_combat_phase(phase_str, round_num)
        display.print_battlefield(session.bf, slyn_unknown=slyn_unknown)
        display.print_combat_log(substantive)
        # Skip pause on battle_over — print_step_header will pause next
        if combat_state.phase.value != "battle_over":
            prompts.pause()
    prev_log_len = len(combat_state.phase_log)

    return combat_state, prev_log_len


def _run_interactive_combat(
    state: GameState,
    mission_type: MissionType,
    deployed_chars: list[str],
    grunt_deploy: int,
    _record: RecordFn,
    bot_deploy: bool = False,
    civilian_deploy: int = 0,
    weapon_loadout: dict[str, str] | None = None,
) -> tuple[bool, list[str], int]:
    """Run interactive AI combat and return results."""
    from planetfall.engine.steps import step08_mission
    from planetfall.engine.combat.session import CombatSession
    from planetfall.engine.combat.missions import setup_mission as combat_setup_mission
    from planetfall.engine.combat.narrator import narrate_phase_local  # noqa: F401
    from planetfall.cli import display, prompts

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
    )

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

    # Show mission briefing: phase header → enemy info → special rules → map
    mission_title = mission_type.value.replace("_", " ").title()
    display.console.print()
    display.console.rule(f"[bold yellow]Mission: {mission_title}[/bold yellow]")

    # Enemy info
    if mission_setup.enemy_info:
        display.console.print()
        for line in mission_setup.enemy_info:
            if first_slyn:
                masked = line.replace("Slyn", "Unknown Alien").replace("slyn", "unknown alien")
                display.console.print(f"  [bold red]{masked}[/bold red]")
            else:
                display.console.print(f"  [bold red]{line}[/bold red]")

    # Special rules
    if mission_setup.special_rules:
        display.console.print()
        for rule in mission_setup.special_rules:
            if first_slyn:
                masked = rule.replace("Slyn", "Unknown Alien").replace("slyn", "unknown alien")
                display.console.print(f"  [yellow]• {masked}[/yellow]")
            else:
                display.console.print(f"  [yellow]• {rule}[/yellow]")

    # Map
    display.reset_enemy_labels()
    display.print_battlefield(bf, slyn_unknown=first_slyn)

    prompts.pause("Press any key to begin deployment...")
    display.clear_screen()

    # Deploy one figure at a time: phase header → map → stats → prompt
    zone_counts: dict[tuple[int, int], int] = {z: 0 for z in available_zones}
    for fig in player_figs:
        display.console.print()
        display.console.rule(f"[bold yellow]Deployment[/bold yellow]")
        display.reset_enemy_labels()
        display.print_battlefield(bf)
        _print_figure_stats(fig)

        # Build zone choices with remaining capacity
        choices = []
        for z in available_zones:
            remaining = 2 - zone_counts[z]
            if remaining > 0:
                choices.append(f"Zone {z[0]},{z[1]} ({remaining} slots)")

        if choices:
            choice = prompts.ask_select(f"Deploy {fig.name}:", choices)
            parts = choice.split(" ")[1].split(",")
            zone = (int(parts[0]), int(parts[1]))
        else:
            zone = available_zones[0]

        fig.zone = zone
        zone_counts[zone] = zone_counts.get(zone, 0) + 1
        bf.figures.append(fig)
        display.clear_screen()

    session = CombatSession(mission_setup)
    combat_state = session.start_battle()

    # Show battlefield after deployment with players visible
    display.reset_enemy_labels()
    display.print_battlefield(session.bf)

    prev_log_len = 0

    while combat_state.phase.value != "battle_over":
        current_phase = combat_state.phase.value

        # Handle REACTION_ROLL phase — player assigns dice
        if current_phase == "reaction_roll":
            display.clear_screen()
            display.print_combat_phase(current_phase, combat_state.round_number)
            display.print_battlefield(session.bf)

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

            # Show final assignments
            if combat_state.reaction_result:
                display.print_reaction_roll(combat_state.reaction_result)
                prompts.pause()

            prev_log_len = len(combat_state.phase_log)
            continue

        if combat_state.available_actions:
            # Let player choose which figure to activate if multiple waiting
            queue = session.get_activation_queue()
            if len(queue) > 1:
                # Filter to alive, non-acted figures
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

                    display.clear_screen()
                    display.print_combat_phase(current_phase, combat_state.round_number)
                    display.print_battlefield(session.bf, slyn_unknown=first_slyn)
                    chosen = prompts.ask_select("Activate which figure?", fig_choices)
                    chosen_name = chosen.split(" (")[0]
                    if chosen_name != queue[0]:
                        session.set_next_figure(chosen_name)
                        combat_state = session._snapshot()

            combat_state, prev_log_len = _handle_player_turn(
                session, combat_state, prev_log_len,
                slyn_unknown=first_slyn,
            )
        elif current_phase == "enemy_phase":
            # Step through enemy activations one at a time
            display.clear_screen()
            display.print_combat_phase(current_phase, combat_state.round_number)
            display.print_battlefield(session.bf)

            while combat_state.phase.value == "enemy_phase":
                pre_step_len = len(combat_state.phase_log)
                combat_state = session.advance_enemy_step()
                new_log = combat_state.phase_log[pre_step_len:]
                substantive_log = [
                    l for l in new_log
                    if not l.startswith("---") and not l.startswith("===")
                ]
                if substantive_log:
                    display.clear_screen()
                    display.print_combat_phase(
                        current_phase, combat_state.round_number,
                    )
                    display.print_battlefield(session.bf)
                    display.print_combat_log(substantive_log)
                    if combat_state.phase.value != "battle_over":
                        prompts.pause()

            prev_log_len = len(combat_state.phase_log)
        else:
            # Auto-advance (end phase, etc.)
            pre_advance_len = len(combat_state.phase_log)
            combat_state = session.advance()
            new_log = combat_state.phase_log[pre_advance_len:]
            substantive_log = [
                l for l in new_log
                if not l.startswith("---") and not l.startswith("===")
            ]
            if substantive_log:
                display.clear_screen()
                display.print_combat_phase(
                    combat_state.phase.value, combat_state.round_number,
                )
                display.print_battlefield(session.bf)
                display.print_combat_log(substantive_log)
                # Skip pause on battle_over — print_step_header will pause next
                if combat_state.phase.value != "battle_over":
                    prompts.pause()
            prev_log_len = len(combat_state.phase_log)

    final_result = session.get_result()
    mission_victory = final_result.get("victory", False)
    character_casualties = final_result.get("character_casualties", [])
    grunt_casualties = final_result.get("grunt_casualties", 0)

    # Stash combat data for narrative and post-mission finds
    state.turn_data["combat_log"] = combat_state.phase_log
    state.turn_data["objectives_secured"] = final_result.get("objectives_secured", 0)
    state.turn_data["combat_result"] = final_result

    return mission_victory, character_casualties, grunt_casualties


def _run_manual_combat(
    state: GameState,
    mission_type: MissionType,
    deployed_chars: list[str],
    grunt_deploy: int,
    _record: RecordFn,
) -> tuple[bool, list[str], int]:
    """Run manual tabletop combat and collect results from player."""
    from planetfall.engine.steps import step08_mission
    from planetfall.cli import display, prompts

    mission_result, events = step08_mission.execute(state, mission_type)
    _record(events)

    display.console.print(
        "\n  [yellow]Resolve the mission using tabletop rules, "
        "then enter results below.[/yellow]\n"
    )
    mission_victory = prompts.ask_confirm("Did you win the mission?")
    mission_result.victory = mission_victory

    character_casualties: list[str] = []
    if deployed_chars:
        character_casualties = prompts.ask_checkbox(
            "Which characters became casualties?", deployed_chars,
        )
    mission_result.character_casualties = character_casualties

    grunt_casualties = 0
    if grunt_deploy > 0:
        grunt_casualties = prompts.ask_number(
            "How many grunts became casualties?",
            min_val=0, max_val=grunt_deploy,
        )
    mission_result.grunt_casualties = grunt_casualties

    # Store combat result for battle concluded display
    state.turn_data["combat_result"] = {
        "victory": mission_victory,
        "rounds_played": 0,
        "enemies_killed": 0,
        "character_casualties": character_casualties,
        "grunt_casualties": grunt_casualties,
    }

    return mission_victory, character_casualties, grunt_casualties


def prompt_research_spending(state: GameState, _record: RecordFn) -> None:
    """Interactive research spending prompt after RP gain."""
    from planetfall.cli import display, prompts
    from planetfall.engine.steps.step14_research import get_research_options
    from planetfall.engine.campaign.research import (
        invest_in_theory, unlock_application, perform_bio_analysis,
        THEORIES, get_available_applications,
    )
    from planetfall.engine.dice import roll_d6

    while True:
        opts = get_research_options(state)
        rp = opts["rp_available"]

        if rp == 0:
            display.console.print(f"  [dim]No Research Points available.[/dim]")
            break

        choices = ["Skip research spending"]

        for t in opts["theories"]:
            invested = t["invested"]
            inv_str = f"{invested.rp_invested}/{t['rp_cost']}" if invested else f"0/{t['rp_cost']}"
            choices.append(f"Invest in theory: {t['name']} ({inv_str} RP)")

        # Group available applications by theory for random selection
        available_apps = get_available_applications(state)
        theory_app_groups: dict[str, list] = {}
        for app in available_apps:
            theory_app_groups.setdefault(app.theory_id, []).append(app)

        for tid, apps in theory_app_groups.items():
            tdef = THEORIES[tid]
            if rp >= tdef.app_cost:
                choices.append(
                    f"Research application from: {tdef.name} ({tdef.app_cost} RP) — {len(apps)} undiscovered"
                )

        if opts["can_bio_analysis"]:
            choices.append("Perform bio-analysis (3 RP)")

        display.console.print(f"\n  [bold]Research Points available: {rp}[/bold]")
        choice = prompts.ask_select("Research:", choices)

        if choice.startswith("Skip"):
            break
        elif choice.startswith("Invest in theory:"):
            theory_name = choice.split(": ", 1)[1].split(" (")[0]
            theory = next((t for t in opts["theories"] if t["name"] == theory_name), None)
            if theory:
                max_invest = min(rp, theory["rp_cost"] - (theory["invested"].rp_invested if theory["invested"] else 0))
                if max_invest <= 0:
                    display.console.print("  [dim]Theory already fully invested.[/dim]")
                    continue
                if max_invest == 1:
                    amount = 1
                else:
                    amount = prompts.ask_number(f"How much RP to invest? (1-{max_invest})", min_val=1, max_val=max_invest)
                _record(invest_in_theory(state, theory["id"], amount))
        elif choice.startswith("Research application from:"):
            theory_name = choice.split(": ", 1)[1].split(" (")[0]
            tid = next((t for t, td in THEORIES.items() if td.name == theory_name), None)
            if tid and tid in theory_app_groups:
                apps = theory_app_groups[tid]
                # Randomly select from undiscovered applications
                import random
                selected = random.choice(apps)
                display.console.print(
                    f"  [yellow]Rolling for application... "
                    f"D{len(apps)} = {apps.index(selected) + 1}[/yellow]"
                )
                _record(unlock_application(state, selected.id))
        elif choice.startswith("Perform bio"):
            _record(perform_bio_analysis(state))


def prompt_building_spending(state: GameState, _record: RecordFn) -> None:
    """Interactive building spending prompt after BP gain."""
    from planetfall.cli import display, prompts
    from planetfall.engine.steps.step15_building import get_building_options
    from planetfall.engine.campaign.buildings import invest_in_building

    while True:
        opts = get_building_options(state)
        bp = opts["bp_available"]
        rm = opts["rm_available"]

        if bp == 0 and rm == 0:
            display.console.print(f"  [dim]No Build Points or Raw Materials available.[/dim]")
            break

        choices = ["Skip building spending"]

        # In-progress buildings first
        for bid, info in opts["in_progress"].items():
            remaining = info["total"] - info["invested"]
            choices.append(
                f"Continue: {info['name']} ({info['invested']}/{info['total']} BP, {remaining} remaining)"
            )

        # New buildings
        for b in opts["available"]:
            if b["progress"] == 0:
                milestone = " [milestone]" if b["is_milestone"] else ""
                choices.append(f"Start: {b['name']} ({b['bp_cost']} BP){milestone} — {b['description']}")

        if len(choices) == 1:
            display.console.print(f"  [dim]No buildings available to construct.[/dim]")
            break

        display.console.print(f"\n  [bold]Build Points: {bp} BP | Raw Materials: {rm}[/bold]")
        choice = prompts.ask_select("Building:", choices)

        if choice.startswith("Skip"):
            break

        # Find the building
        building_name = choice.split(": ", 1)[1].split(" (")[0]
        building = None
        for b in opts["available"]:
            if b["name"] == building_name:
                building = b
                break
        if not building:
            for bid, info in opts["in_progress"].items():
                if info["name"] == building_name:
                    building = {"id": bid, "name": info["name"], "bp_cost": info["total"]}
                    break

        if building:
            max_bp = min(bp, building["bp_cost"] - building.get("progress", 0))
            rm_convert = 0
            if rm > 0 and max_bp < building["bp_cost"]:
                rm_convert = prompts.ask_number(
                    f"Convert raw materials to BP? (0-{min(3, rm)})",
                    min_val=0, max_val=min(3, rm),
                )
            total = max_bp + rm_convert
            if total > 0:
                _record(invest_in_building(state, building["id"], max_bp, rm_convert))
            else:
                display.console.print("  [dim]No BP to invest.[/dim]")


def execute_post_mission_finds(
    state: GameState,
    mission_victory: bool,
    deployed_chars: list[str],
    character_casualties: list[str],
    condition,
    _record: RecordFn,
    mission_type: MissionType | None = None,
    objectives_secured: int = 0,
) -> None:
    """Post-mission finds + ancient signs check (after victories)."""
    if not mission_victory:
        return

    from planetfall.engine.tables.post_mission_finds import roll_post_mission_finds
    from planetfall.engine.campaign.ancient_signs import check_ancient_signs

    scientist_alive = any(
        c.char_class == CharacterClass.SCIENTIST
        and c.name in deployed_chars
        and c.name not in character_casualties
        for c in state.characters
    )
    scout_alive = any(
        c.char_class == CharacterClass.SCOUT
        and c.name in deployed_chars
        and c.name not in character_casualties
        for c in state.characters
    )

    # Exploration missions: roll once per objective secured (rules p.117)
    if mission_type == MissionType.EXPLORATION and objectives_secured > 0:
        num_rolls = objectives_secured
    else:
        num_rolls = 1 + (condition.extra_finds_rolls if condition else 0)

    finds_events = roll_post_mission_finds(
        state, scientist_alive=scientist_alive,
        scout_alive=scout_alive, num_rolls=num_rolls,
    )
    _record(finds_events)

    # Exploration campaign factors: D6 per objective (rules p.117)
    if mission_type == MissionType.EXPLORATION and objectives_secured > 0:
        from planetfall.engine.dice import roll_d6
        from planetfall.cli import display

        sector = None
        sector_id = state.turn_data.get("sector_id")
        if sector_id is not None:
            sector = next(
                (s for s in state.campaign_map.sectors if s.sector_id == sector_id),
                None,
            )

        if sector:
            hazard_increase = 0
            resource_decrease = 0
            factor_lines = []
            for i in range(objectives_secured):
                roll = roll_d6()
                if roll == 1:
                    hazard_increase += 1
                    factor_lines.append(f"  Objective {i+1}: D6 = {roll} → Hazard +1")
                elif roll == 2:
                    factor_lines.append(f"  Objective {i+1}: D6 = {roll} → No effect")
                else:
                    resource_decrease += 1
                    factor_lines.append(f"  Objective {i+1}: D6 = {roll} → Resource -1")

            if hazard_increase:
                sector.hazard_level += hazard_increase
            if resource_decrease:
                sector.resource_level = max(0, sector.resource_level - resource_decrease)

            # Mark exploited if resources depleted
            exploited = False
            if sector.resource_level <= 0:
                from planetfall.engine.models import SectorStatus
                sector.status = SectorStatus.EXPLOITED
                exploited = True

            desc = (
                f"Exploration Campaign Factors — Sector {sector_id}: "
                f"Hazard {'+' + str(hazard_increase) if hazard_increase else '+0'}, "
                f"Resource {'-' + str(resource_decrease) if resource_decrease else '-0'} "
                f"(now R{sector.resource_level}/H{sector.hazard_level})"
            )
            if exploited:
                desc += " — Sector EXPLOITED (no further exploration possible)"

            display.console.print(f"\n[bold yellow]Exploration Campaign Factors:[/bold yellow]")
            for line in factor_lines:
                display.console.print(line)
            display.console.print(
                f"  [bold]Sector {sector_id}: "
                f"Resource={sector.resource_level}, Hazard={sector.hazard_level}[/bold]"
            )
            if exploited:
                display.console.print(
                    f"  [red]Sector {sector_id} is now Exploited![/red]"
                )

            _record([TurnEvent(
                step=8, event_type=TurnEventType.MISSION,
                description=desc,
            )])

    sign_events = check_ancient_signs(state)
    if sign_events:
        _record(sign_events)


def execute_step11_morale(
    state: GameState,
    mission_type: MissionType,
    mission_victory: bool,
    character_casualties: list[str],
    grunt_casualties: int,
    _record: RecordFn,
) -> None:
    """Step 11: Morale — with optional SP prevention of incident."""
    from planetfall.engine.steps import step11_morale
    from planetfall.cli import prompts

    total_casualties = len(character_casualties) + grunt_casualties

    preview_morale = state.colony.morale - 1 - (
        total_casualties if mission_type not in (MissionType.RESCUE, MissionType.SCOUT_DOWN) else 0
    )
    spend_sp_incident = False
    if preview_morale <= -10 and state.colony.resources.story_points >= 1:
        spend_sp_incident = prompts.ask_confirm(
            f"Morale will drop to {preview_morale}, triggering a Morale Incident. "
            f"Spend 1 Story Point to prevent it? ({state.colony.resources.story_points} SP)",
            default=False,
        )

    events = step11_morale.execute(
        state,
        battle_casualties=total_casualties,
        mission_type=mission_type,
        mission_victory=mission_victory,
        spend_sp_prevent_incident=spend_sp_incident,
    )
    _record(events)


def execute_mid_turn_systems(
    state: GameState,
    mission_type: MissionType,
    mission_victory: bool,
    _record: RecordFn,
) -> None:
    """Mid-turn systems: extractions, calamities, colonist demands, SP spending."""
    from planetfall.engine.steps import step11_morale
    from planetfall.cli import display, prompts

    # Resource extractions
    from planetfall.engine.campaign.extraction import process_extractions
    extraction_events = process_extractions(state)
    if extraction_events:
        display.console.print("  [bold]Resource Extraction:[/bold]")
        _record(extraction_events)

    # Active calamities
    from planetfall.engine.campaign.calamities import process_active_calamities
    calamity_events = process_active_calamities(state)
    if calamity_events:
        display.console.print("  [bold]Active Calamity Effects:[/bold]")
        _record(calamity_events)

    # Colonist demands
    if state.flags.colonist_demands_active:
        display.console.print("  [bold yellow]Colonist Demands are active![/bold yellow]")
        available_security = [
            c.name for c in state.characters
            if c.is_available and c.char_class.value in ("scout", "trooper")
        ]
        if available_security:
            assigned = prompts.ask_checkbox(
                "Assign scouts/troopers to security (cannot deploy on missions):",
                available_security,
            )
            if assigned:
                demand_events = step11_morale.resolve_colonist_demands(state, assigned)
                _record(demand_events)

    # Story Point resource spending
    if state.colony.resources.story_points >= 1:
        if prompts.ask_confirm(
            f"Spend 1 Story Point for resources (2D6, pick highest)? "
            f"({state.colony.resources.story_points} SP)",
            default=False,
        ):
            from planetfall.engine.campaign.story_points import spend_for_resources
            resource_choice = prompts.ask_select(
                "Maximize which resource?",
                ["Build Points", "Research Points", "Raw Materials"],
            )
            if resource_choice == "Build Points":
                sp_events = spend_for_resources(state, bp=6, rp=0, rm=0)
            elif resource_choice == "Research Points":
                sp_events = spend_for_resources(state, bp=0, rp=6, rm=0)
            else:
                sp_events = spend_for_resources(state, bp=0, rp=0, rm=6)
            _record(sp_events)


def execute_augmentation_opportunity(
    state: GameState,
    _record: RecordFn,
) -> None:
    """Augmentation purchase opportunity between steps 15 and 16."""
    from planetfall.engine.campaign.augmentation import (
        get_available_augmentations, apply_augmentation, get_augmentation_cost,
    )
    from planetfall.cli import prompts

    if (state.colony.resources.augmentation_points >= get_augmentation_cost(state)
            and not state.flags.augmentation_bought_this_turn):
        avail_augs = get_available_augmentations(state)
        if avail_augs:
            cost = get_augmentation_cost(state)
            if prompts.ask_confirm(
                f"Purchase an augmentation? (Cost: {cost} AP, "
                f"Available: {state.colony.resources.augmentation_points} AP)",
                default=False,
            ):
                aug_choices = [
                    f"{a['name']} — {a['description']}" for a in avail_augs
                ]
                choice = prompts.ask_select("Choose augmentation:", aug_choices)
                aug_idx = aug_choices.index(choice)
                aug_events = apply_augmentation(state, avail_augs[aug_idx]["id"])
                _record(aug_events)


def execute_step16_integrity(
    state: GameState,
    _record: RecordFn,
) -> None:
    """Step 16: Colony Integrity — with optional SP prevention."""
    from planetfall.engine.steps import step16_colony_integrity
    from planetfall.cli import prompts

    spend_sp_integrity = False
    if state.colony.integrity <= -3 and state.colony.resources.story_points >= 1:
        spend_sp_integrity = prompts.ask_confirm(
            f"Colony Integrity is {state.colony.integrity}. "
            f"Spend 1 Story Point to skip Integrity Failure roll? "
            f"({state.colony.resources.story_points} SP)",
            default=False,
        )
    events = step16_colony_integrity.execute(state, spend_story_point=spend_sp_integrity)
    _record(events)

"""Step helper functions for the local orchestrator.

Extracted from run_campaign_turn_local() to keep each step's logic
isolated and the main loop readable.

All functions accept a ``ui`` parameter (UIAdapter) instead of importing
cli.display / cli.prompts directly, so the same logic works for CLI
and a future web UI.
"""

from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from planetfall.engine.models import (
    CharacterClass, GameState, MissionType, SectorStatus,
    TurnEvent, TurnEventType,
)
from planetfall.engine.combat.battlefield import FigureSide

if TYPE_CHECKING:
    from planetfall.ui.adapter import UIAdapter


# Type alias for the record/narrate callbacks passed from the orchestrator
RecordFn = Callable[[list[TurnEvent]], None]
NarrateFn = Callable[[str], None]


def execute_step03_scout(
    ui: UIAdapter,
    state: GameState,
    _record: RecordFn,
) -> bool:
    """Step 3: Scout Reports — explore sectors and roll discoveries.

    Returns True if a discovery roll was made (narrative should be generated).
    """
    from planetfall.engine.steps import step03_scout_reports, step09_injuries

    unexplored = [
        s for s in state.campaign_map.sectors
        if s.status == SectorStatus.UNKNOWN
        and s.sector_id != state.campaign_map.colony_sector_id
    ]
    if unexplored:
        valid_ids = [s.sector_id for s in unexplored]
        sector_id = ui.prompt_sector_coords("Scout which sector?", valid_ids)
        events = step03_scout_reports.execute_scout_explore(state, sector_id)
        _record(events)
        # Redraw with updated map
        ui.clear()
        ui.show_colony_status(state)
        ui.show_map(state)
        ui.show_events(events)
    else:
        ui.message("  No unexplored sectors to scout.", style="dim")

    if ui.confirm("Roll on Scout Discovery table?", default=True):
        available_scouts = [
            c for c in state.characters
            if c.char_class == CharacterClass.SCOUT and c.is_available
        ]
        if available_scouts:
            scout_choices = [c.name for c in available_scouts] + ["None (no scout assigned)"]
            choice = ui.select("Assign a scout to lead?", scout_choices)
            scout_name = None if choice.startswith("None") else choice
        else:
            scout_name = None

        # Show loading modal while generating narrative
        ui.show_loading_modal("Scout Reports")

        events = step03_scout_reports.execute_scout_discovery(state, scout_name)
        _record(events)
        # Redraw with discovery results
        ui.clear()
        ui.show_colony_status(state)
        ui.show_map(state)
        ui.show_events(events)

        _handle_scout_pending_choices(ui, state, events, _record)
        return True

    return False


def _handle_scout_pending_choices(
    ui: UIAdapter,
    state: GameState,
    events: list[TurnEvent],
    _record: RecordFn,
) -> None:
    """Handle pending player choices from scout discovery results."""
    from planetfall.engine.steps import step09_injuries

    for ev in events:
        ctx = ev.state_changes.get("narrative_context", {})
        if ctx.get("pending_choice") == "scout_down_or_escape":
            _handle_scout_down(ui, state, ctx, _record)
        elif ctx.get("pending_choice") == "rescue_or_morale":
            _handle_rescue_or_morale(ui, state, ctx, _record)
        elif ctx.get("pending_choice") == "exploration_report":
            _handle_exploration_report(ui, state, _record)


def _handle_scout_down(
    ui: UIAdapter,
    state: GameState,
    ctx: dict,
    _record: RecordFn,
) -> None:
    """Handle the scout down/escape choice."""
    from planetfall.engine.steps import step09_injuries

    scout_at_risk = ctx.get("scout_at_risk")
    if not scout_at_risk:
        no_survivor = TurnEvent(
            step=3,
            event_type=TurnEventType.SCOUT_REPORT,
            description="Scout vehicle crashed with no assigned scout. No survivors.",
        )
        _record([no_survivor])
        return

    sd_choice = ui.select(
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
    ui: UIAdapter,
    state: GameState,
    ctx: dict,
    _record: RecordFn,
) -> None:
    """Handle the rescue vs morale penalty choice."""
    sos_choice = ui.select(
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
    ui: UIAdapter,
    state: GameState,
    _record: RecordFn,
) -> None:
    """Handle the Exploration Report pending choice — player picks a sector to explore."""
    from planetfall.engine.steps.step03_scout_reports import _apply_exploration_report

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
    sector_id = ui.prompt_sector_coords(
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
    ui.clear()
    ui.show_colony_status(state)
    ui.show_map(state)
    ui.show_events([ev])


def execute_step05_colony_events(
    ui: UIAdapter,
    state: GameState,
    _record: RecordFn,
) -> None:
    """Step 5: Colony Events — roll and handle player choices."""
    from planetfall.engine.steps import step05_colony_events
    from planetfall.engine.dice import roll_d6, roll_nd6

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
                chosen = ui.select(
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
            choice = ui.select("Public Relations Demand:", choices)
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
            choice = ui.select("Specialist Training:", options)
            if choice.startswith("Grant"):
                available = [c.name for c in state.characters]
                chosen = ui.select("Select character for XP:", available)
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
                chosen = ui.select(
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
            priority = ui.select(
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
            unexplored = [
                s for s in state.campaign_map.sectors
                if s.status == SectorStatus.UNKNOWN
                and s.sector_id != state.campaign_map.colony_sector_id
            ]
            if unexplored:
                valid_ids = [s.sector_id for s in unexplored]
                sector_id = ui.prompt_sector_coords(
                    "Free Scout Action — choose a sector to explore:", valid_ids,
                )
                scout_events = step03_scout_reports.execute_scout_explore(
                    state, sector_id,
                )
                _record(scout_events)
                ui.clear()
                ui.show_colony_status(state)
                ui.show_map(state)
                ui.show_events(scout_events)
            else:
                _record([TurnEvent(
                    step=5, event_type=TurnEventType.COLONY_EVENT,
                    description="Free Scout Action: No unexplored sectors remaining.",
                )])


def execute_step04_enemy(
    ui: UIAdapter,
    state: GameState,
    _record: RecordFn,
) -> None:
    """Step 4: Enemy Activity — with optional SP prevention."""
    from planetfall.engine.steps import step04_enemy_activity

    active_enemies = [e for e in state.enemies.tactical_enemies if not e.defeated]
    if not active_enemies:
        ui.message("  No active Tactical Enemies. Skipping enemy activity.", style="dim")
        return

    skip_enemy = False
    if state.colony.resources.story_points >= 1:
        skip_enemy = ui.confirm(
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
    ui: UIAdapter,
    state: GameState,
    _record: RecordFn,
) -> tuple[MissionType, int | None]:
    """Step 6: Mission Determination — choose mission and sector."""
    from planetfall.engine.steps import step06_mission_determination

    mission_options = step06_mission_determination.get_available_missions(state)
    ui.show_mission_options(mission_options)

    if len(mission_options) == 1 and mission_options[0].get("forced"):
        mission_idx = 0
        ui.message("  Forced mission — no choice available.", style="error")
    else:
        mission_idx = ui.prompt_mission_choice(mission_options)

    chosen = mission_options[mission_idx]
    mission_type = chosen["type"]

    sector_id = chosen.get("sector_id")
    target_sectors = chosen.get("target_sectors")
    if target_sectors and len(target_sectors) > 1 and sector_id is None:
        # Mission-specific prompt
        mission_verbs = {
            MissionType.INVESTIGATION: "Investigate which sector?",
            MissionType.SCOUTING: "Scout which sector?",
            MissionType.EXPLORATION: "Explore which sector?",
            MissionType.SCIENCE: "Research which sector?",
        }
        prompt = mission_verbs.get(mission_type, "Which sector?")
        sector_id = ui.prompt_sector_coords(prompt, target_sectors)
    elif target_sectors and len(target_sectors) == 1:
        sector_id = target_sectors[0]

    events = step06_mission_determination.execute(state, mission_type, sector_id)
    _record(events)

    return mission_type, sector_id


def execute_step07_deploy(
    ui: UIAdapter,
    state: GameState,
    mission_type: MissionType,
    _record: RecordFn,
) -> tuple[list[str], int, bool, int, dict[str, str]]:
    """Step 7: Lock and Load — deploy characters, grunts, bot, civilians.

    Returns (deployed, grunts, bot, civilians, weapon_loadout).
    """
    from planetfall.engine.steps import step07_lock_and_load

    available = step07_lock_and_load.get_available_characters(state)
    max_slots = step07_lock_and_load.get_deployment_slots(mission_type.value)
    available_names = [c.name for c in available]
    available_classes = {c.name: c.char_class.value for c in available}

    deployment = ui.prompt_deployment(
        available_names,
        max_slots,
        char_classes=available_classes,
        grunt_count=state.grunts.count,
        bot_available=state.grunts.bot_operational,
    )

    deployed_chars = deployment["characters"]
    grunt_deploy = deployment["grunts"]
    bot_deploy = deployment["bot"]
    civilian_deploy = deployment.get("civilians", 0)

    # Weapon selection — Lock and Load
    ui.message("\n=== Lock and Load ===", style="heading")
    ui.message("Choose weapons for each character.\n", style="dim")
    weapon_loadout = ui.prompt_loadout(state, deployed_chars)

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
    ui: UIAdapter,
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
    combat_mode_choices = ["Interactive (AI combat)", "Manual (tabletop)"]
    combat_mode_choice = ui.select("Combat mode?", combat_mode_choices)
    use_interactive = combat_mode_choice.startswith("Interactive")

    if use_interactive and deployed_chars:
        return _run_interactive_combat(
            ui, state, mission_type, deployed_chars, grunt_deploy, _record,
            bot_deploy, civilian_deploy, weapon_loadout=weapon_loadout,
        )
    else:
        return _run_manual_combat(
            ui, state, mission_type, deployed_chars, grunt_deploy, _record,
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
        raw = bf.jump_destinations(*fig.zone, num_move) if num_move > 0 else []
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
    Speed 3-4, 7-8: No dash available.
    Uses Chebyshev distance (same as movement overlay).
    Scouts can land on impassable terrain via jump jets.
    Returns [(zone, terrain_label, [fig_names], is_jump), ...]
    """
    from planetfall.engine.combat.battlefield import (
        TerrainType, rush_available, rush_total_zones,
    )
    if not rush_available(fig.speed):
        return []
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

    move_to = None
    action_type = "hold"
    target_name = None
    use_aid = False
    scout_action_first = False
    trooper_delay = False
    dashed = False

    # Enemies in range from current position (for movement phase highlighting)
    in_range = _enemies_in_range(session.bf, fig, fig.zone)

    # === STEP 1+2: Combined movement type + destination ===
    if is_delayed:
        # Delayed trooper returning in slow phase: no movement, just action
        pass
    else:
        all_move_zones = _get_move_zones(session.bf, fig) if num_move > 0 else []
        all_dash_zones = _get_dash_zones(session.bf, fig) if can_dash else []

        # Trooper in quick phase: staying stationary enables delay action
        if is_trooper and in_quick:
            trooper_delay = True  # will be cleared if they choose to move

        if not all_move_zones and not all_dash_zones and not is_scout:
            pass  # no movement options, stay stationary
        else:
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

            if move_result_type == "move":
                trooper_delay = False
                idx = result["zone_idx"]
                move_to = all_move_zones[idx][0]
            elif move_result_type == "dash":
                trooper_delay = False
                dashed = True
                idx = result["zone_idx"]
                move_to = all_dash_zones[idx][0]
                action_type = "rush"
            elif move_result_type == "scout_first":
                trooper_delay = False
                scout_action_first = True
            # "stay" — trooper_delay stays True if applicable

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

        # === STEP 4: Action Target ===

        # Check if response is a shoot target desc (from info panel click)
        if action_choice in shoot_descs:
            idx = shoot_descs.index(action_choice)
            if idx >= len(shoot_targets):
                target_name = shoot_targets[idx - len(shoot_targets)]["name"]
                use_aid = True
            else:
                target_name = shoot_targets[idx]["name"]
            action_type = "shoot"
            action_choice = "Shoot"

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
) -> tuple[bool, list[str], int]:
    """Run interactive AI combat and return results."""
    from planetfall.engine.steps import step08_mission
    from planetfall.engine.combat.session import CombatSession
    from planetfall.engine.combat.missions import setup_mission as combat_setup_mission
    from planetfall.engine.combat.narrator import narrate_phase_local  # noqa: F401

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

    # Show mission intro modal
    mission_title = mission_type.value.replace("_", " ").title()
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
        enemy_info = [l.replace("Slyn", "Unknown Alien").replace("slyn", "unknown alien") for l in enemy_info]
        special_rules = [r.replace("Slyn", "Unknown Alien").replace("slyn", "unknown alien") for r in special_rules]
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
    )

    ui.pause("Begin deployment")
    ui.clear()
    ui.show_combat_phase("deployment", 0)

    ui.prompt_deployment_zones(bf, player_figs, available_zones)

    session = CombatSession(mission_setup)
    combat_state = session.start_battle()

    # Show battlefield after deployment with players visible
    ui.reset_enemy_labels()
    ui.show_battlefield(session.bf)

    prev_log_len = 0

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

                    ui.clear()
                    ui.show_combat_phase(current_phase, combat_state.round_number)
                    ui.show_battlefield(session.bf, slyn_unknown=first_slyn)
                    chosen = ui.select("Activate which figure?", fig_choices)
                    chosen_name = chosen.split(" (")[0]
                    if chosen_name != queue[0]:
                        session.set_next_figure(chosen_name)
                        combat_state = session._snapshot()

            combat_state, prev_log_len = _handle_player_turn(
                ui, session, combat_state, prev_log_len,
                slyn_unknown=first_slyn,
            )
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

    # Store combat result for battle concluded display
    state.turn_data["combat_result"] = {
        "victory": mission_victory,
        "rounds_played": 0,
        "enemies_killed": 0,
        "character_casualties": character_casualties,
        "grunt_casualties": grunt_casualties,
    }

    return mission_victory, character_casualties, grunt_casualties


def prompt_research_spending(ui: UIAdapter, state: GameState, _record: RecordFn) -> None:
    """Interactive research spending prompt after RP gain."""
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
            ui.message("  No Research Points available.", style="dim")
            break

        choices = ["Skip research spending"]

        for t in opts["theories"]:
            invested = t["invested"]
            inv_str = f"{invested.invested_rp}/{t['rp_cost']}" if invested else f"0/{t['rp_cost']}"
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

        ui.message(f"\n  Research Points available: {rp}", style="bold")
        choice = ui.select("Research:", choices)

        if choice.startswith("Skip"):
            break
        elif choice.startswith("Invest in theory:"):
            theory_name = choice.split(": ", 1)[1].split(" (")[0]
            theory = next((t for t in opts["theories"] if t["name"] == theory_name), None)
            if theory:
                max_invest = min(rp, theory["rp_cost"] - (theory["invested"].invested_rp if theory["invested"] else 0))
                if max_invest <= 0:
                    ui.message("  Theory already fully invested.", style="dim")
                    continue
                if max_invest == 1:
                    amount = 1
                else:
                    amount = ui.number(f"How much RP to invest? (1-{max_invest})", min_val=1, max_val=max_invest)
                _record(invest_in_theory(state, theory["id"], amount))
        elif choice.startswith("Research application from:"):
            theory_name = choice.split(": ", 1)[1].split(" (")[0]
            tid = next((t for t, td in THEORIES.items() if td.name == theory_name), None)
            if tid and tid in theory_app_groups:
                apps = theory_app_groups[tid]
                # Randomly select from undiscovered applications
                import random
                selected = random.choice(apps)
                ui.message(
                    f"  Rolling for application... "
                    f"D{len(apps)} = {apps.index(selected) + 1}", style="warning"
                )
                _record(unlock_application(state, selected.id))
        elif choice.startswith("Perform bio"):
            _record(perform_bio_analysis(state))


def prompt_building_spending(ui: UIAdapter, state: GameState, _record: RecordFn) -> None:
    """Interactive building spending prompt after BP gain."""
    from planetfall.engine.steps.step15_building import get_building_options
    from planetfall.engine.campaign.buildings import invest_in_building

    while True:
        opts = get_building_options(state)
        bp = opts["bp_available"]
        rm = opts["rm_available"]

        if bp == 0 and rm == 0:
            ui.message("  No Build Points or Raw Materials available.", style="dim")
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
            ui.message("  No buildings available to construct.", style="dim")
            break

        ui.message(f"\n  Build Points: {bp} BP | Raw Materials: {rm}", style="bold")
        choice = ui.select("Building:", choices)

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
                rm_convert = ui.number(
                    f"Convert raw materials to BP? (0-{min(3, rm)})",
                    min_val=0, max_val=min(3, rm),
                )
            total = max_bp + rm_convert
            if total > 0:
                _record(invest_in_building(state, building["id"], max_bp, rm_convert))
            else:
                ui.message("  No BP to invest.", style="dim")


def execute_post_mission_finds(
    ui: UIAdapter,
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
                    factor_lines.append(f"  Objective {i+1}: D6 = {roll} -> Hazard +1")
                elif roll == 2:
                    factor_lines.append(f"  Objective {i+1}: D6 = {roll} -> No effect")
                else:
                    resource_decrease += 1
                    factor_lines.append(f"  Objective {i+1}: D6 = {roll} -> Resource -1")

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

            ui.message(f"\nExploration Campaign Factors:", style="heading")
            for line in factor_lines:
                ui.message(line)
            ui.message(
                f"  Sector {sector_id}: "
                f"Resource={sector.resource_level}, Hazard={sector.hazard_level}", style="bold"
            )
            if exploited:
                ui.message(
                    f"  Sector {sector_id} is now Exploited!", style="error"
                )

            _record([TurnEvent(
                step=8, event_type=TurnEventType.MISSION,
                description=desc,
            )])

    sign_events = check_ancient_signs(state)
    if sign_events:
        _record(sign_events)


def execute_step11_morale(
    ui: UIAdapter,
    state: GameState,
    mission_type: MissionType,
    mission_victory: bool,
    character_casualties: list[str],
    grunt_casualties: int,
    _record: RecordFn,
) -> None:
    """Step 11: Morale — with optional SP prevention of incident."""
    from planetfall.engine.steps import step11_morale

    total_casualties = len(character_casualties) + grunt_casualties

    preview_morale = state.colony.morale - 1 - (
        total_casualties if mission_type not in (MissionType.RESCUE, MissionType.SCOUT_DOWN) else 0
    )
    spend_sp_incident = False
    if preview_morale <= -10 and state.colony.resources.story_points >= 1:
        spend_sp_incident = ui.confirm(
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
    for ev in events:
        ui.message(f"  {ev.description}")


def execute_mid_turn_systems(
    ui: UIAdapter,
    state: GameState,
    mission_type: MissionType,
    mission_victory: bool,
    _record: RecordFn,
) -> None:
    """Mid-turn systems: extractions, calamities, colonist demands, SP spending."""
    from planetfall.engine.steps import step11_morale

    # Resource extractions
    from planetfall.engine.campaign.extraction import process_extractions
    extraction_events = process_extractions(state)
    if extraction_events:
        ui.message("  Resource Extraction:", style="bold")
        _record(extraction_events)

    # Active calamities
    from planetfall.engine.campaign.calamities import process_active_calamities
    calamity_events = process_active_calamities(state)
    if calamity_events:
        ui.message("  Active Calamity Effects:", style="bold")
        _record(calamity_events)

    # Colonist demands
    if state.flags.colonist_demands_active:
        ui.message("  Colonist Demands are active!", style="heading")
        available_security = [
            c.name for c in state.characters
            if c.is_available and c.char_class.value in ("scout", "trooper")
        ]
        if available_security:
            assigned = ui.checkbox(
                "Assign scouts/troopers to security (cannot deploy on missions):",
                available_security,
            )
            if assigned:
                demand_events = step11_morale.resolve_colonist_demands(state, assigned)
                _record(demand_events)

    # TODO: Story Point resource spending (disabled for now)


def execute_augmentation_opportunity(
    ui: UIAdapter,
    state: GameState,
    _record: RecordFn,
) -> None:
    """Augmentation purchase opportunity between steps 15 and 16."""
    from planetfall.engine.campaign.augmentation import (
        get_available_augmentations, apply_augmentation, get_augmentation_cost,
    )

    if (state.colony.resources.augmentation_points >= get_augmentation_cost(state)
            and not state.flags.augmentation_bought_this_turn):
        avail_augs = get_available_augmentations(state)
        if avail_augs:
            cost = get_augmentation_cost(state)
            if ui.confirm(
                f"Purchase an augmentation? (Cost: {cost} AP, "
                f"Available: {state.colony.resources.augmentation_points} AP)",
                default=False,
            ):
                aug_choices = [
                    f"{a['name']} — {a['description']}" for a in avail_augs
                ]
                choice = ui.select("Choose augmentation:", aug_choices)
                aug_idx = aug_choices.index(choice)
                aug_events = apply_augmentation(state, avail_augs[aug_idx]["id"])
                _record(aug_events)


def execute_step16_integrity(
    ui: UIAdapter,
    state: GameState,
    _record: RecordFn,
) -> None:
    """Step 16: Colony Integrity — with optional SP prevention."""
    from planetfall.engine.steps import step16_colony_integrity

    spend_sp_integrity = False
    if state.colony.integrity <= -3 and state.colony.resources.story_points >= 1:
        spend_sp_integrity = ui.confirm(
            f"Colony Integrity is {state.colony.integrity}. "
            f"Spend 1 Story Point to skip Integrity Failure roll? "
            f"({state.colony.resources.story_points} SP)",
            default=False,
        )
    events = step16_colony_integrity.execute(state, spend_story_point=spend_sp_integrity)
    _record(events)
    for ev in events:
        ui.message(f"  {ev.description}")

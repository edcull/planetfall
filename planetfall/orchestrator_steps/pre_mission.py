"""Pre-mission orchestrator steps (Steps 3-5)."""
from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from planetfall.engine.models import (
    CharacterClass, GameState, MissionType, SectorStatus,
    TurnEvent, TurnEventType,
)

if TYPE_CHECKING:
    from planetfall.ui.adapter import UIAdapter

RecordFn = Callable[[list[TurnEvent]], None]

_EFFECT_LABELS = {
    "research_points": "Research Points", "build_points": "Build Points",
    "morale": "Morale", "colony_damage": "Colony Damage",
    "ancient_signs": "Ancient Signs", "all_xp": "XP (all characters)",
    "grunt": "Grunts", "raw_materials": "Raw Materials",
    "story_points": "Story Points", "calamity_points": "Calamity Points",
    "forced_mission": "Forced Mission",
    "scout_xp": "Scout XP", "enemy_info": "Enemy Information",
    "loyalty_up": "Loyalty +1", "loyalty_down": "Loyalty -1",
    "xp": "XP", "sick_bay_turns": "Sick Bay turns",
}


def _summarize_effects(effects: dict | None) -> str | None:
    """Build a short human-readable effects summary for display."""
    if not effects:
        return None
    parts = []
    for k, label in _EFFECT_LABELS.items():
        if k in effects:
            val = effects[k]
            if isinstance(val, (int, float)):
                sign = "+" if val > 0 else ""
                parts.append(f"{sign}{val} {label}")
            elif isinstance(val, bool) and val:
                parts.append(label)
            elif isinstance(val, str):
                parts.append(f"{label}: {val}")
    if effects.get("no_story_points"):
        parts.append("No Story Points this turn")
    return ", ".join(parts) if parts else None


def execute_step03_scout(
    ui: UIAdapter,
    state: GameState,
    _record: RecordFn,
    _persist: Callable[[], None] | None = None,
) -> bool:
    """Step 3: Scout Reports — explore sectors and roll discoveries.

    Flow:
      1. Ask if player wants discovery roll; if yes, choose scout
      2. Player chooses sector to explore
      3. Survey sector (resource/hazard levels)
      4. If discovery chosen: roll discovery, handle choices

    Returns True if a discovery roll was made (narrative should be generated).
    Uses turn_data flags to guard against re-execution on resume.
    """
    from planetfall.engine.steps import step03_scout_reports

    td = state.turn_data

    # Phase 1: Discovery roll decision + scout assignment (guarded)
    if td.scout_wants_discovery is None:
        if ui.confirm("Roll on Scout Discovery table?", default=True):
            available_scouts = [
                c for c in state.characters
                if c.char_class == CharacterClass.SCOUT and c.is_available
            ]
            if available_scouts:
                scout_choices = [c.name for c in available_scouts] + ["None (no scout assigned)"]
                choice = ui.select("Assign a scout to lead?", scout_choices)
                td.scout_discovery_scout = None if choice.startswith("None") else choice
            else:
                td.scout_discovery_scout = None
            td.scout_wants_discovery = True
        else:
            td.scout_wants_discovery = False
        if _persist:
            _persist()

    # Phase 2: Sector exploration (guarded — only once per turn)
    if not td.scout_explored:
        unexplored = [
            s for s in state.campaign_map.sectors
            if s.status == SectorStatus.UNEXPLORED
            and s.sector_id != state.campaign_map.colony_sector_id
        ]
        if unexplored:
            valid_ids = [s.sector_id for s in unexplored]
            sector_id = ui.prompt_sector_coords("Scout which sector?", valid_ids)
            events = step03_scout_reports.execute_scout_explore(state, sector_id)
            _record(events)
        else:
            ui.message("  No unexplored sectors to scout.", style="dim")
        td.scout_explored = True
        if _persist:
            _persist()
        # Redraw with updated map
        ui.redraw(state)

    # Phase 3: Discovery roll (if chosen, guarded) — with SP reroll
    if td.scout_wants_discovery and not td.scout_discovery_done:
        from planetfall.engine.campaign.story_points import can_spend, spend_for_reroll
        from planetfall.engine.steps.step03_scout_reports import (
            roll_scout_discovery, apply_scout_discovery,
        )
        from planetfall.engine.utils import format_display as _fmt

        roll_result, entry = roll_scout_discovery()

        # Offer SP reroll
        if can_spend(state):
            want_reroll = ui.confirm_reroll_offer(
                "Scout Discovery",
                {"roll": roll_result.total, "name": _fmt(entry.result_id),
                 "description": entry.description,
                 "effects": _summarize_effects(entry.effects)},
                state.colony.resources.story_points,
            )
            if want_reroll:
                sp_events = spend_for_reroll(state, "Scout Discovery")
                _record(sp_events)
                new_roll, new_entry = roll_scout_discovery()
                choice = ui.prompt_reroll_choice(
                    "Scout Discovery",
                    {"roll": roll_result.total, "name": _fmt(entry.result_id),
                     "description": entry.description},
                    {"roll": new_roll.total, "name": _fmt(new_entry.result_id),
                     "description": new_entry.description},
                )
                if choice == "b":
                    roll_result, entry = new_roll, new_entry

        events = apply_scout_discovery(state, roll_result, entry, td.scout_discovery_scout)
        _record(events)
        td.scout_discovery_done = True
        if _persist:
            _persist()
        # Redraw with discovery results
        ui.redraw(state, events)

        _handle_scout_pending_choices(ui, state, events, _record)
        if _persist:
            _persist()
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
        c = state.find_character(scout_at_risk)
        if c:
            c.xp += 2
            xp_ev = TurnEvent(
                step=3,
                event_type=TurnEventType.CHARACTER_EVENT,
                description=f"{scout_at_risk} escaped on foot. +2 XP.",
            )
            _record([xp_ev])
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
        if s.status == SectorStatus.UNEXPLORED
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
    ui.redraw(state, [ev])


def execute_step05_colony_events(
    ui: UIAdapter,
    state: GameState,
    _record: RecordFn,
) -> None:
    """Step 5: Colony Events — roll and handle player choices."""
    from planetfall.engine.steps.step05_colony_events import (
        roll_colony_event, apply_colony_event,
    )
    from planetfall.engine.campaign.story_points import can_spend, spend_for_reroll
    from planetfall.engine.dice import roll_d6, roll_nd6
    from planetfall.engine.utils import format_display as _fmt

    roll_result, entry = roll_colony_event()

    # Offer SP reroll
    if can_spend(state):
        want_reroll = ui.confirm_reroll_offer(
            "Colony Event",
            {"roll": roll_result.total, "name": _fmt(entry.result_id),
             "description": entry.description,
             "effects": _summarize_effects(entry.effects)},
            state.colony.resources.story_points,
        )
        if want_reroll:
            sp_events = spend_for_reroll(state, "Colony Events")
            _record(sp_events)
            new_roll, new_entry = roll_colony_event()
            choice = ui.prompt_reroll_choice(
                "Colony Events",
                {"roll": roll_result.total, "name": _fmt(entry.result_id),
                 "description": entry.description},
                {"roll": new_roll.total, "name": _fmt(new_entry.result_id),
                 "description": new_entry.description},
            )
            if choice == "b":
                roll_result, entry = new_roll, new_entry

    events = apply_colony_event(state, roll_result, entry)
    _record(events)

    # Handle events requiring player choices
    for ev in events:
        effects = ev.state_changes.get("effects", {})
        event_id = ev.state_changes.get("event", "")

        if effects.get("character_xp_d6"):
            # report_on_progress: Select one character to earn 1D6 XP
            available = [c.name for c in state.get_available_characters()]
            if available:
                chosen = ui.select(
                    "Select a character to earn 1D6 XP:", available,
                )
                xp_roll = roll_d6("Report on Progress XP")
                c = state.find_character(chosen)
                if c:
                    c.xp += xp_roll.total
                xp_ev = TurnEvent(
                    step=5,
                    event_type=TurnEventType.CHARACTER_EVENT,
                    description=f"{chosen} earns {xp_roll.total} XP from Report on Progress.",
                )
                _record([xp_ev])

        if effects.get("bench_character"):
            # public_relations_demand: Bench a character or lose morale
            available = [c.name for c in state.get_available_characters()]
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
                c = state.find_character(benched)
                if c:
                    c.sick_bay_turns = max(c.sick_bay_turns, 1)
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
                c = state.find_character(chosen)
                if c:
                    c.xp += xp_amount
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
                c = state.find_character(chosen)
                if c:
                    c.sick_bay_turns = max(0, c.sick_bay_turns - heal)
                    status = (
                        "fully recovered" if c.sick_bay_turns == 0
                        else f"{c.sick_bay_turns} turns remaining"
                    )
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
                if s.status == SectorStatus.UNEXPLORED
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
                ui.redraw(state, scout_events)
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
        from planetfall.engine.models import TurnEvent, TurnEventType
        _record([TurnEvent(
            step=4,
            event_type=TurnEventType.ENEMY_ACTIVITY,
            description="No active Tactical Enemies. Skipping enemy activity.",
        )])
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
        from planetfall.engine.campaign.story_points import can_spend, spend_for_reroll
        from planetfall.engine.steps.step04_enemy_activity import (
            roll_enemy_activity, apply_enemy_activity,
        )
        from planetfall.engine.utils import format_display as _fmt

        for enemy in active_enemies:
            roll_result, entry = roll_enemy_activity(enemy.name)

            # Offer SP reroll
            if can_spend(state):
                want_reroll = ui.confirm_reroll_offer(
                    f"Enemy Activity: {enemy.name}",
                    {"roll": roll_result.total, "name": _fmt(entry.result_id),
                     "description": entry.description,
                     "effects": _summarize_effects(entry.effects)},
                    state.colony.resources.story_points,
                )
                if want_reroll:
                    sp_events = spend_for_reroll(state, "Enemy Activity")
                    _record(sp_events)
                    new_roll, new_entry = roll_enemy_activity(enemy.name)
                    choice = ui.prompt_reroll_choice(
                        f"Enemy Activity: {enemy.name}",
                        {"roll": roll_result.total, "name": _fmt(entry.result_id),
                         "description": entry.description},
                        {"roll": new_roll.total, "name": _fmt(new_entry.result_id),
                         "description": new_entry.description},
                    )
                    if choice == "b":
                        roll_result, entry = new_roll, new_entry

            events = apply_enemy_activity(state, enemy, roll_result, entry)
            _record(events)

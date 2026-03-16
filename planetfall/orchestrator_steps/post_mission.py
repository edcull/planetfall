"""Post-mission orchestrator steps (Steps 9-13)."""
from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from planetfall.engine.models import (
    CharacterClass, GameState, MissionType, SectorStatus,
    TurnEvent, TurnEventType,
)

if TYPE_CHECKING:
    from planetfall.ui.adapter import UIAdapter

RecordFn = Callable[[list[TurnEvent]], None]

_FIND_LABELS = {
    "rp": "Research Points", "bp": "Build Points", "rm": "Raw Materials",
    "sp": "Story Points", "morale": "Morale", "ancient_sign": "Ancient Sign",
    "xp_pick": "XP (choose character)",
}


def _summarize_find_effects(find: dict) -> str | None:
    """Build a human-readable effects summary for a post-mission find."""
    parts = []
    for k, label in _FIND_LABELS.items():
        if find.get(k):
            val = find[k]
            sign = "+" if isinstance(val, (int, float)) and val > 0 else ""
            parts.append(f"{sign}{val} {label}")
    if find.get("scientist_bonus_rp"):
        parts.append(f"+{find['scientist_bonus_rp']} RP (scientist)")
    if find.get("scout_bonus_rm"):
        parts.append(f"+{find['scout_bonus_rm']} RM (scout)")
    return ", ".join(parts) if parts else None


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

    from planetfall.engine.tables.post_mission_finds import (
        roll_single_find, apply_single_find,
    )
    from planetfall.engine.campaign.story_points import can_spend, spend_for_reroll
    from planetfall.orchestrator_steps.pre_mission import _summarize_effects

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
    # Scouting missions: post-mission find only if 3+ recon markers investigated
    elif mission_type == MissionType.SCOUTING and objectives_secured >= 3:
        num_rolls = 1 + (condition.extra_finds_rolls if condition else 0)
    elif mission_type == MissionType.SCOUTING:
        num_rolls = 0  # no post-mission find if < 3 recon markers
    # Investigation missions: "Rewards" discoveries grant extra find rolls
    elif mission_type == MissionType.INVESTIGATION:
        cr = state.turn_data.combat_result
        inv_results = cr.investigation_results if cr else {}
        num_rolls = inv_results.get("rewards", 0)
    else:
        num_rolls = 1 + (condition.extra_finds_rolls if condition else 0)

    if num_rolls > 0:
        ui.message("\nPost-Mission Finds:", style="heading")
        for i in range(num_rolls):
            roll_total, find = roll_single_find(f"Post-Mission Finds (roll {i + 1})")

            # Offer SP reroll
            if can_spend(state):
                find_effects = _summarize_find_effects(find)
                want_reroll = ui.confirm_reroll_offer(
                    "Post-Mission Find",
                    {"roll": roll_total, "name": find["name"],
                     "description": find["description"],
                     "effects": find_effects},
                    state.colony.resources.story_points,
                )
                if want_reroll:
                    sp_events = spend_for_reroll(state, "Post-Mission Finds")
                    _record(sp_events)
                    new_total, new_find = roll_single_find("Post-Mission Finds (SP Reroll)")
                    choice = ui.prompt_reroll_choice(
                        "Post-Mission Finds",
                        {"roll": roll_total, "name": find["name"],
                         "description": find["description"]},
                        {"roll": new_total, "name": new_find["name"],
                         "description": new_find["description"]},
                    )
                    if choice == "b":
                        roll_total, find = new_total, new_find

            find_events = apply_single_find(
                state, roll_total, find,
                scientist_alive, scout_alive,
            )
            _record(find_events)
            for ev in find_events:
                ui.message(f"  {ev.description}")

    # Scouting campaign factors: survey sector + recon marker rewards
    if mission_type == MissionType.SCOUTING:
        from planetfall.engine.dice import roll_d6, roll_2d6_pick_lowest

        sector = None
        sector_id = state.turn_data.sector_id
        if sector_id is not None:
            sector = state.get_sector(sector_id)

        if sector:
            # Recon marker rewards: D6 per marker investigated, 6 = Resource +1
            recon_bonus = 0
            recon_lines = []
            for i in range(objectives_secured):
                roll = roll_d6(f"Recon marker {i+1}")
                if roll.total == 6:
                    recon_bonus += 1
                    recon_lines.append(f"  Recon {i+1}: D6 = {roll.total} -> Resource +1")
                else:
                    recon_lines.append(f"  Recon {i+1}: D6 = {roll.total} -> No effect")

            # Survey sector: 2D6-pick-lowest for Resource and Hazard
            resource_roll = roll_2d6_pick_lowest("Sector Resource Level")
            hazard_roll = roll_2d6_pick_lowest("Sector Hazard Level")
            sector.resource_level = resource_roll.total + recon_bonus
            sector.hazard_level = hazard_roll.total
            sector.status = SectorStatus.EXPLORED

            # Double 4, 5, or 6 on either survey roll → Ancient Signs
            from planetfall.engine.steps.step03_scout_reports import _check_ancient_sign_doubles
            ancient_sign = _check_ancient_sign_doubles(state, sector, resource_roll, hazard_roll)

            ui.message(f"\nScouting Campaign Factors:", style="heading")
            if objectives_secured > 0:
                ui.message(f"  Recon markers investigated: {objectives_secured}")
                for line in recon_lines:
                    ui.message(line)
                if recon_bonus:
                    ui.message(f"  Resource bonus from recon: +{recon_bonus}", style="bold")
            ui.message(
                f"  Sector {sector_id} surveyed: "
                f"Resource={sector.resource_level} "
                f"(base {resource_roll.total}{f' +{recon_bonus} recon' if recon_bonus else ''}), "
                f"Hazard={sector.hazard_level}",
                style="bold",
            )
            if ancient_sign:
                ui.message(f"  Double rolled — Ancient Signs discovered!", style="success")
            ui.message(f"  Sector {sector_id} is now Explored.", style="success")

            desc = (
                f"Scouting Campaign Factors — Sector {sector_id}: "
                f"Resource {sector.resource_level}, Hazard {sector.hazard_level}. "
                f"Sector Explored."
            )
            if recon_bonus:
                desc += f" (+{recon_bonus} Resource from recon markers)"
            if ancient_sign:
                desc += " Ancient Signs discovered!"

            _record([TurnEvent(
                step=8, event_type=TurnEventType.MISSION,
                description=desc,
            )])

            # Immediately check for Ancient Site location
            if ancient_sign:
                from planetfall.engine.campaign.ancient_signs import check_ancient_signs
                sign_events = check_ancient_signs(state)
                if sign_events:
                    _record(sign_events)

    # Exploration campaign factors: D6 per objective (rules p.117)
    if mission_type == MissionType.EXPLORATION and objectives_secured > 0:
        from planetfall.engine.dice import roll_d6

        sector = None
        sector_id = state.turn_data.sector_id
        if sector_id is not None:
            sector = state.get_sector(sector_id)

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

    # Investigation campaign factors
    if mission_type == MissionType.INVESTIGATION:
        _apply_investigation_campaign_factors(
            ui, state, objectives_secured, _record,
        )


def _apply_investigation_campaign_factors(
    ui: UIAdapter,
    state: GameState,
    discoveries_completed: int,
    _record: RecordFn,
) -> None:
    """Apply investigation post-mission campaign factors.

    If 2+ Discovery markers completed: remove investigation site from sector,
    then roll D6 twice — 4-6 on first = eligible for Scientific mission,
    4-6 on second = eligible for Scouting mission.
    Investigating does NOT make the sector Explored or Exploited.
    """
    from planetfall.engine.dice import roll_d6

    sector_id = state.turn_data.sector_id
    sector = state.get_sector(sector_id) if sector_id is not None else None

    if discoveries_completed < 2:
        ui.message(
            f"\n  Fewer than 2 Discovery markers completed — "
            f"Investigation Site remains.", style="dim",
        )
        _record([TurnEvent(
            step=8, event_type=TurnEventType.MISSION,
            description=(
                f"Investigation: only {discoveries_completed}/4 markers completed. "
                f"Site remains for future investigation."
            ),
        )])
        return

    # 2+ discoveries: remove investigation site
    if sector and sector.has_investigation_site:
        sector.has_investigation_site = False

    ui.message(f"\nInvestigation Campaign Factors:", style="heading")
    ui.message(
        f"  {discoveries_completed} Discovery markers completed — "
        f"Investigation Site cleared.", style="success",
    )

    desc_parts = [
        f"Investigation complete: {discoveries_completed} markers. Site cleared.",
    ]

    # Roll D6 twice for sector eligibility
    roll_science = roll_d6("Investigation: Science eligibility")
    roll_scouting = roll_d6("Investigation: Scouting eligibility")

    science_eligible = roll_science.total >= 4
    scouting_eligible = roll_scouting.total >= 4

    if science_eligible:
        ui.message(
            f"  Science eligibility: D6 = {roll_science.total} (4+) — "
            f"sector can be targeted for Scientific Mission.", style="success",
        )
        desc_parts.append(
            f"Science roll: {roll_science.total} — eligible for Scientific Mission."
        )
    else:
        ui.message(
            f"  Science eligibility: D6 = {roll_science.total} — no.", style="dim",
        )
        desc_parts.append(f"Science roll: {roll_science.total} — not eligible.")

    if scouting_eligible:
        ui.message(
            f"  Scouting eligibility: D6 = {roll_scouting.total} (4+) — "
            f"sector can be targeted for Scouting Mission.", style="success",
        )
        desc_parts.append(
            f"Scouting roll: {roll_scouting.total} — eligible for Scouting Mission."
        )
    else:
        ui.message(
            f"  Scouting eligibility: D6 = {roll_scouting.total} — no.", style="dim",
        )
        desc_parts.append(f"Scouting roll: {roll_scouting.total} — not eligible.")

    _record([TurnEvent(
        step=8, event_type=TurnEventType.MISSION,
        description=" ".join(desc_parts),
    )])


def execute_step11_morale(
    ui: UIAdapter,
    state: GameState,
    mission_type: MissionType,
    mission_victory: bool,
    character_casualties: list[str],
    grunt_casualties: int,
    _record: RecordFn,
) -> bool:
    """Step 11: Morale — with optional SP prevention of incident.

    Returns True if a morale incident occurred (for narrative generation).
    """
    from planetfall.engine.steps import step11_morale

    total_casualties = len(character_casualties) + grunt_casualties

    preview_morale = state.colony.morale - 1 - (
        total_casualties if mission_type not in (MissionType.RESCUE, MissionType.SCOUT_DOWN) else 0
    )
    # Offer crisis reroll if crisis is active
    if state.flags.crisis_active and state.colony.resources.story_points >= 1:
        from planetfall.engine.campaign.story_points import spend_crisis_reroll
        crisis_reroll = ui.confirm(
            f"Crisis is active. Spend 1 SP to roll Crisis Outcome twice and pick the better result? "
            f"({state.colony.resources.story_points} SP)",
            default=False,
        )
        if crisis_reroll:
            cr_events = spend_crisis_reroll(state)
            _record(cr_events)

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

    # Show morale change via modal (web) or message (CLI)
    if events and events[0].state_changes:
        change_data = {
            "old": events[0].state_changes.get("old_morale", 0),
            "new": events[0].state_changes.get("new_morale", 0),
            "description": events[0].description,
        }
        if hasattr(ui, "show_morale"):
            ui.show_morale(state, change=change_data)
        else:
            ui.message(f"  {events[0].description}")
    elif events:
        ui.message(f"  {events[0].description}")

    # Check if an incident occurred (any event beyond the initial adjustment)
    has_incident = len(events) > 1
    return has_incident


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

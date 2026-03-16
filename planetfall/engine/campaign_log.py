"""Campaign log export - generate markdown summaries of campaign turns.

Exports turn events, combat results, and campaign state to readable
markdown files. Updated every time the game state is saved.
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime

from planetfall.engine.models import GameState, TurnEvent, TurnEventType
from planetfall.engine.persistence import (
    _campaign_dir, list_snapshots, load_snapshot,
)


STEP_NAMES = {
    1: "Recovery", 2: "Repairs", 3: "Scout Reports",
    4: "Enemy Activity", 5: "Colony Events",
    6: "Mission Determination", 7: "Lock and Load",
    8: "Battle Results", 9: "Injuries",
    10: "Experience", 11: "Morale",
    12: "Tracking", 13: "Replacements",
    14: "Research", 15: "Building",
    16: "Colony Integrity", 17: "Character Event",
    18: "Update Sheet",
}


def _format_event(e: TurnEvent) -> list[str]:
    """Format a single event into markdown lines."""
    lines = []
    lines.append(f"- {e.description}")
    for roll in e.dice_rolls:
        lines.append(f"  - *{roll.label}: {roll.values} = {roll.total}*")
    if e.state_changes:
        sc = e.state_changes
        # Render mechanical effects from colony/discovery events
        effects = sc.get("effects", {})
        if effects:
            effect_parts = []
            effect_labels = {
                "research_points": "Research Points",
                "build_points": "Build Points",
                "morale": "Morale",
                "colony_damage": "Colony Damage",
                "ancient_signs": "Ancient Signs",
                "all_xp": "XP (all characters)",
                "grunt": "Grunts",
                "raw_materials": "Raw Materials",
                "story_points": "Story Points",
                "calamity_points": "Calamity Points",
            }
            for k, label in effect_labels.items():
                if k in effects:
                    val = effects[k]
                    sign = "+" if val > 0 else ""
                    effect_parts.append(f"{sign}{val} {label}")
            if effect_parts:
                lines.append(f"  - **{', '.join(effect_parts)}**")
        # Log other significant state changes
        change_parts = []
        for key in ("victory", "weapon_loadout", "mission_type",
                     "application_unlocked", "building_invested"):
            if key in sc:
                change_parts.append(f"{key}: {sc[key]}")
        if change_parts:
            lines.append(f"  - `{', '.join(change_parts)}`")
    return lines


def export_turn_log(
    state: GameState,
    events: list[TurnEvent] | None = None,
) -> str:
    """Generate a markdown summary for the current turn.

    Args:
        state: Current game state (after the turn).
        events: Turn events to summarize. Uses state.turn_log if None.

    Returns:
        Markdown string for the turn.
    """
    events = events or state.turn_log
    lines: list[str] = []

    lines.append(f"# Turn {state.current_turn}")
    lines.append(f"*{state.colony.name} - {state.campaign_name}*\n")

    # Colony status snapshot
    res = state.colony.resources
    lines.append("## Colony Status")
    lines.append(f"| Stat | Value | Stat | Value |")
    lines.append(f"|------|-------|------|-------|")
    lines.append(f"| Morale | {state.colony.morale} | Integrity | {state.colony.integrity} |")
    lines.append(f"| Story Points | {res.story_points} | Defenses | {state.colony.defenses} |")
    lines.append(f"| Build Points | {res.build_points} | Research Points | {res.research_points} |")
    lines.append(f"| Raw Materials | {res.raw_materials} | Augmentation Pts | {res.augmentation_points} |")
    lines.append(f"| Grunts | {state.grunts.count} | Milestones | {state.campaign.milestones_completed}/7 |")
    lines.append("")

    # Research & applications
    if state.tech_tree.theories or state.tech_tree.unlocked_applications:
        from planetfall.engine.campaign.research import THEORIES, APPLICATIONS
        lines.append("## Research & Applications")
        for tid, theory in state.tech_tree.theories.items():
            tdef = THEORIES.get(tid)
            if tdef:
                if theory.completed:
                    lines.append(f"- **{tdef.name}** - completed")
                else:
                    lines.append(f"- **{tdef.name}** - {theory.invested_rp}/{tdef.rp_cost} RP")
        for app_id in state.tech_tree.unlocked_applications:
            adef = APPLICATIONS.get(app_id)
            if adef:
                lines.append(f"  - *{adef.name}* - {adef.description}")
        lines.append("")

    # Buildings
    if state.colony.buildings:
        lines.append("## Buildings")
        for b in state.colony.buildings:
            effects_str = f" - {', '.join(b.effects)}" if b.effects else ""
            lines.append(f"- **{b.name}**{effects_str}")
        lines.append("")

    # Roster (before events for quick reference)
    lines.append("## Roster\n")
    lines.append("| Name | Class | React | Speed | CS | Tough | Savvy | XP | KP | Status |")
    lines.append("|------|-------|-------|-------|-----|-------|-------|----|----|--------|")
    for c in state.characters:
        status = "Ready" if c.sick_bay_turns == 0 else f"Sick Bay ({c.sick_bay_turns}t)"
        lines.append(
            f"| {c.name} | {c.char_class.value.title()} | "
            f"{c.reactions} | {c.speed}\" | +{c.combat_skill} | "
            f"{c.toughness} | +{c.savvy} | {c.xp} | {c.kill_points} | {status} |"
        )
    bot_status = "Operational" if state.grunts.bot_operational else "Destroyed"
    lines.append(f"\n*Bot: {bot_status} | Grunts: {state.grunts.count}*\n")

    # Group events by step. step=0 events are attached to the most recent
    # non-zero step that precedes them, or to step 12 (tracking) by default.
    step_events: dict[int, list[TurnEvent]] = {}
    narratives: dict[int, list[TurnEvent]] = {}
    last_step = 0

    for e in events:
        step = e.step if e.step > 0 else last_step
        if e.step > 0:
            last_step = e.step

        if e.event_type == TurnEventType.NARRATIVE and e.step == 0 and not e.dice_rolls:
            # Pure narrative text (from AI) — attach to current step
            narratives.setdefault(step or 12, []).append(e)
        else:
            step_events.setdefault(step or 12, []).append(e)

    lines.append("## Events\n")

    completed_step = state.current_step
    for step in sorted(step_events.keys()):
        step_name = STEP_NAMES.get(step, f"Step {step}")
        lines.append(f"### Step {step}: {step_name}\n")
        for e in step_events[step]:
            lines.extend(_format_event(e))
        lines.append("")

        # Insert narrative for this step
        if step in narratives:
            for n in narratives[step]:
                lines.append("---\n")
                lines.append(f"*{n.description}*\n")
                lines.append("---\n")

    # Show incomplete step marker if mid-turn
    if completed_step > 0 and completed_step < 18:
        lines.append(f"*-- Save point: Step {completed_step} completed --*\n")

    lines.append("")
    lines.append(f"---\n*Updated {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")

    return "\n".join(lines)


def export_campaign_log(state: GameState) -> str:
    """Export the full campaign history as markdown.

    Loads all turn snapshots and generates a combined log.
    """
    campaign_name = state.campaign_name
    turns = list_snapshots(campaign_name)
    lines: list[str] = []

    lines.append(f"# Campaign Log: {campaign_name}")
    lines.append(f"*Colony: {state.colony.name}*\n")
    lines.append(f"*Agenda: {state.settings.colonization_agenda.value.title()}*\n")
    lines.append("---\n")

    for turn_num in turns:
        try:
            snapshot = load_snapshot(campaign_name, turn_num)
            turn_md = export_turn_log(snapshot, snapshot.turn_log)
            lines.append(turn_md)
            lines.append("---\n")
        except (FileNotFoundError, Exception):
            lines.append(f"# Turn {turn_num}\n*Snapshot unavailable*\n---\n")

    lines.append(f"*Full log exported {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")
    return "\n".join(lines)


def export_day_zero_log(state: GameState) -> str:
    """Generate a Day 0 markdown log capturing colony founding and crew roster.

    Includes colony details, agenda, administrator, and full character
    descriptions with backgrounds/motivations/prior experience.
    """
    lines: list[str] = []

    lines.append("# Day 0 — Colony Founded")
    lines.append(f"*{state.colony.name} - {state.campaign_name}*\n")

    # Colonization agenda
    agenda = state.settings.colonization_agenda.value.replace("_", " ").title()
    lines.append(f"**Colonization Agenda:** {agenda}\n")

    # Colony founding description
    if state.colony.description:
        lines.append(f"{state.colony.description}\n")

    # Administrator
    if state.administrator.name:
        admin = state.administrator
        lines.append("## Administrator")
        history = f" — {admin.past_history}" if admin.past_history else ""
        lines.append(f"**{admin.name}**{history}\n")

    # Colony status
    res = state.colony.resources
    lines.append("## Colony Status")
    lines.append("| Stat | Value | Stat | Value |")
    lines.append("|------|-------|------|-------|")
    lines.append(f"| Morale | {state.colony.morale} | Integrity | {state.colony.integrity} |")
    lines.append(f"| Story Points | {res.story_points} | Defenses | {state.colony.defenses} |")
    lines.append(f"| Build Points | {res.build_points} | Research Points | {res.research_points} |")
    lines.append(f"| Raw Materials | {res.raw_materials} | Grunts | {state.grunts.count} |")
    lines.append("")

    # Crew roster with full backgrounds
    lines.append("## Crew Roster\n")
    for c in state.characters:
        char_class = c.char_class.value.title()
        title_str = f" — {c.title}" if c.title else ""
        role_str = f", {c.role}" if c.role else ""
        lines.append(f"### {c.name}{title_str}")
        lines.append(f"*{char_class}{role_str}*\n")

        lines.append(
            f"| React | Speed | CS | Tough | Savvy |"
        )
        lines.append("|-------|-------|----|-------|-------|")
        lines.append(
            f"| {c.reactions} | {c.speed}\" | +{c.combat_skill} | "
            f"{c.toughness} | +{c.savvy} |"
        )
        lines.append("")

        if c.background_motivation:
            lines.append(f"**Motivation:** {c.background_motivation}\n")
        if c.background_prior_experience:
            lines.append(f"**Prior Experience:** {c.background_prior_experience}\n")
        if c.narrative_background:
            lines.append(f"{c.narrative_background}\n")

        lines.append("---\n")

    # Bot & grunts
    bot_status = "Operational" if state.grunts.bot_operational else "Destroyed"
    lines.append(f"*Colony Bot: {bot_status} | Grunts: {state.grunts.count}*\n")

    # Campaign map summary
    if state.campaign_map.sectors:
        colony_id = state.campaign_map.colony_sector_id
        colony_sector = next(
            (s for s in state.campaign_map.sectors if s.sector_id == colony_id), None
        )
        if colony_sector and colony_sector.name:
            lines.append(f"**Colony Sector:** {colony_sector.name} (Sector {colony_id})\n")

    lines.append(f"---\n*Colony founded {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")

    return "\n".join(lines)


def save_day_zero_log(state: GameState) -> Path:
    """Save the Day 0 colony founding log."""
    campaign_dir = _campaign_dir(state.campaign_name)
    campaign_dir.mkdir(parents=True, exist_ok=True)
    md = export_day_zero_log(state)
    path = campaign_dir / "turn_000_log.md"
    path.write_text(md, encoding="utf-8")
    return path


def save_turn_log(state: GameState, events: list[TurnEvent] | None = None) -> Path:
    """Save the current turn's log as a markdown file."""
    campaign_dir = _campaign_dir(state.campaign_name)
    campaign_dir.mkdir(parents=True, exist_ok=True)
    md = export_turn_log(state, events)
    path = campaign_dir / f"turn_{state.current_turn:03d}_log.md"
    path.write_text(md, encoding="utf-8")
    return path


def save_campaign_log(state: GameState) -> Path:
    """Save the full campaign log as a markdown file."""
    campaign_dir = _campaign_dir(state.campaign_name)
    campaign_dir.mkdir(parents=True, exist_ok=True)
    md = export_campaign_log(state)
    path = campaign_dir / "campaign_log.md"
    path.write_text(md, encoding="utf-8")
    return path

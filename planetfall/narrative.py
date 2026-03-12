"""Narrative agent — converts mechanical events into immersive prose.

Uses Claude API to generate gritty frontier sci-fi narration from
structured event logs. Maintains compressed narrative memory across
turns for character arcs, themes, and motifs.

Called after battles, dramatic colony events, character events, and turn ends.
"""

from __future__ import annotations

import json
from typing import Optional

from planetfall.engine.models import GameState, TurnEvent, TurnEventType


# Narrative memory keys
MEMORY_THEMES = "themes"  # recurring themes/motifs
MEMORY_ARCS = "character_arcs"  # per-character narrative threads
MEMORY_HISTORY = "key_events"  # compressed event history
MEMORY_TONE = "tone"  # current narrative tone


def init_narrative_memory(state: GameState) -> None:
    """No-op — narrative data is now a typed NarrativeData model with defaults."""
    pass


def build_narrative_prompt(
    state: GameState,
    events: list[TurnEvent],
    context: str = "turn_end",
    combat_log: list[str] | None = None,
) -> str:
    """Build a prompt for the narrative agent from game events.

    Args:
        state: Current game state.
        events: Events to narrate.
        context: One of "battle", "colony_event", "character_event", "turn_end".
        combat_log: Optional detailed combat log entries from interactive combat.

    Returns:
        A formatted prompt string for Claude API.
    """
    nd = state.narrative

    # Build event summary
    event_lines = []
    for e in events:
        if e.description:
            event_lines.append(f"- [{e.event_type.value}] {e.description}")

    events_text = "\n".join(event_lines) if event_lines else "No significant events."

    # Build character roster summary (with personality backgrounds)
    roster = []
    for c in state.characters:
        status = "available" if c.is_available else f"sick bay ({c.sick_bay_turns} days remaining)"
        line = f"  {c.name} ({c.char_class.value}): {status}"
        if c.narrative_background:
            line += f"\n    Background: {c.narrative_background}"
        roster.append(line)
    roster_text = "\n".join(roster)

    # Build memory context
    recent_history = nd.key_events[-5:] if nd.key_events else []
    history_text = "\n".join(f"- {h}" for h in recent_history) if recent_history else "None yet."

    themes_text = ", ".join(nd.themes[-5:]) if nd.themes else "None established."

    arcs_text = ""
    for name, arc in list(nd.character_arcs.items())[:4]:
        arcs_text += f"\n  {name}: {arc}"
    if not arcs_text:
        arcs_text = "\n  None yet."

    # Build prior narratives section (for turn_end context, include earlier narratives)
    prior_narratives_section = ""
    if context == "turn_end":
        prior_narrs = [
            e.description for e in state.turn_log
            if e.event_type == TurnEventType.NARRATIVE and e.description
        ]
        if prior_narrs:
            narr_text = "\n---\n".join(prior_narrs)
            prior_narratives_section = f"""
EARLIER NARRATIVES THIS DAY (reference and build on these — do not repeat them verbatim, but weave continuity):
{narr_text}
"""

    # Build combat log section if available (for battle context)
    combat_log_section = ""
    if combat_log:
        # Filter out header/separator lines, keep substantive entries
        substantive = [
            l for l in combat_log
            if not l.startswith("---") and not l.startswith("===") and l.strip()
        ]
        if substantive:
            # Limit to keep prompt reasonable (last 60 entries = most recent action)
            trimmed = substantive[-60:]
            log_text = "\n".join(f"- {l}" for l in trimmed)
            combat_log_section = f"""
DETAILED COMBAT LOG (use these specific events to ground the narrative):
{log_text}

Reference specific combat moments — who fought whom, what was discovered, key shots and movements.
"""

    prompt = f"""You are the narrative voice of a gritty frontier sci-fi colony game.
Write a short narrative passage (2-4 paragraphs) for the following events.

TONE: {nd.tone}
CONTEXT: {context}
COLONY: {state.colony.name} (Day {state.current_turn}, Morale: {state.colony.morale})

CREW ROSTER:
{roster_text}

RECENT HISTORY:
{history_text}

THEMES: {themes_text}
CHARACTER ARCS:{arcs_text}

EVENTS THIS TURN:
{events_text}
{combat_log_section}{prior_narratives_section}
Write vivid, concise prose. Reference specific characters by name.
End with a one-sentence hook or observation about what's coming.
Do NOT use game mechanics language — translate everything into narrative.
Specifically: never say "Turn", "roll", "dice", "table", "morale points", or reference game steps.
Use "day" or narrative time markers instead of "Turn X".

CRITICAL TIMING RULES:
- If CONTEXT is "colony_event": This happens EARLY in the day (morning/midday). The day has barely started. Do NOT describe sunsets, evening, end-of-day reflections, or winding down. The mission and combat are STILL AHEAD.
- If CONTEXT is "battle": This happens MID-DAY after combat. Do not summarize the entire day.
- If CONTEXT is "character_event": This happens LATE in the day but the day is not yet over.
- If CONTEXT is "turn_end": This is the END of the day — you may now summarize and reflect.
Never frame a narrative as a complete day summary unless CONTEXT is "turn_end".
"""
    return prompt


def generate_narrative_local(
    state: GameState,
    events: list[TurnEvent],
    context: str = "turn_end",
) -> str:
    """Generate a narrative summary without API calls (template-based fallback).

    Used when Claude API is not configured.
    """
    init_narrative_memory(state)

    # Simple template-based narration
    colony = state.colony.name
    turn = state.current_turn

    parts = [f"Day {turn} at {colony}."]

    for e in events:
        if not e.description:
            continue
        etype = e.event_type.value

        if etype == "combat":
            parts.append(f"Battle report: {e.description}")
        elif etype == "colony_event":
            parts.append(f"Colony dispatch: {e.description}")
        elif etype == "character_event":
            parts.append(f"Personal log: {e.description}")
        elif etype == "injury":
            parts.append(f"Medical update: {e.description}")
        elif etype == "morale":
            parts.append(f"Morale status: {e.description}")
        elif etype == "research":
            parts.append(f"Research division: {e.description}")
        elif etype == "building":
            parts.append(f"Construction report: {e.description}")
        elif etype == "narrative":
            parts.append(e.description)
        else:
            parts.append(e.description)

    narrative = " ".join(parts)

    # Update memory
    _update_memory(state, events, narrative)

    return narrative


def generate_narrative_api(
    state: GameState,
    events: list[TurnEvent],
    context: str = "turn_end",
    api_key: str = "",
    model: str = "",
    combat_log: list[str] | None = None,
) -> str:
    """Generate narrative using Claude API.

    Falls back to local generation if API is not available.
    """
    if not api_key:
        return generate_narrative_local(state, events, context)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        if not model:
            from planetfall.config import get_narrative_model
            model = get_narrative_model()

        prompt = build_narrative_prompt(state, events, context, combat_log=combat_log)

        from planetfall.api_tracker import tracked_api_call
        message = tracked_api_call(
            client, caller="narrative",
            model=model,
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}],
        )

        narrative = message.content[0].text
        _update_memory(state, events, narrative)
        return narrative

    except Exception:
        return generate_narrative_local(state, events, context)


def _update_memory(
    state: GameState,
    events: list[TurnEvent],
    narrative: str,
) -> None:
    """Update narrative memory with key events from this turn."""
    nd = state.narrative

    # Add compressed event to history
    summary = f"Day {state.current_turn}: "
    key_parts = []
    for e in events:
        if e.event_type.value in ("combat", "colony_event", "character_event", "injury", "narrative"):
            key_parts.append(e.description[:80])
    if key_parts:
        summary += "; ".join(key_parts[:3])
    else:
        summary += "Routine operations."

    nd.key_events.append(summary)
    # Keep only last 20 entries
    nd.key_events = nd.key_events[-20:]

    # Track character involvement
    for e in events:
        if e.event_type.value == "injury" and e.description:
            for c in state.characters:
                if c.name in e.description:
                    nd.character_arcs[c.name] = f"Day {state.current_turn}: {e.description[:60]}"
        if e.event_type.value == "character_event" and e.description:
            for c in state.characters:
                if c.name in e.description:
                    nd.character_arcs[c.name] = f"Day {state.current_turn}: {e.description[:60]}"


def get_narrative_summary(state: GameState) -> str:
    """Get a brief narrative summary of the campaign so far."""
    history = state.narrative.key_events
    if not history:
        return f"The colony of {state.colony.name} has just been established."

    recent = history[-3:]
    return " | ".join(recent)

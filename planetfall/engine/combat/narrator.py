"""Combat narrative generator.

Converts mechanical combat logs into vivid, atmospheric prose.
Uses Claude API when available, falls back to template-based generation.

Called after each combat phase to narrate what happened, giving the
player an immersive description of the firefight.
"""

from __future__ import annotations

from planetfall.engine.combat.session import CombatState, CombatPhase


# --- Zone flavor text for descriptions ---

TERRAIN_FLAVOR = {
    "open": ["exposed ground", "open terrain", "bare earth", "the clearing"],
    "light_cover": ["scattered debris", "low walls", "broken cover", "rubble"],
    "heavy_cover": ["dense cover", "thick ruins", "barricades", "fortified position"],
    "high_ground": ["elevated ridge", "high ground", "the hilltop", "raised position"],
    "impassable": ["impassable wreckage", "collapsed structure"],
}

ZONE_NAMES = {
    (0, 0): "far left flank",
    (0, 1): "enemy center",
    (0, 2): "far right flank",
    (1, 0): "left midfield",
    (1, 1): "center ground",
    (1, 2): "right midfield",
    (2, 0): "left deployment",
    (2, 1): "home base",
    (2, 2): "right deployment",
}


def _zone_desc(zone: tuple[int, int], terrain: str = "open") -> str:
    """Get a narrative description of a zone."""
    name = ZONE_NAMES.get(zone, f"zone {zone}")
    import random
    flavors = TERRAIN_FLAVOR.get(terrain, TERRAIN_FLAVOR["open"])
    flavor = random.choice(flavors)
    return f"the {name} ({flavor})"


# --- Template-based combat narration ---

_SHOT_HIT_TEMPLATES = [
    "{shooter} lines up {target} and fires — a clean hit!",
    "{shooter}'s shot finds its mark, slamming into {target}.",
    "A burst from {shooter}'s weapon catches {target} squarely.",
    "{shooter} squeezes the trigger. {target} staggers from the impact.",
]

_SHOT_MISS_TEMPLATES = [
    "{shooter} fires at {target} — the shot goes wide.",
    "{shooter}'s rounds chew into the ground near {target}, missing.",
    "A near-miss from {shooter} forces {target} to duck, but no hit.",
    "{shooter} opens fire but {target} is untouched.",
]

_CASUALTY_TEMPLATES = [
    "{target} goes down hard and doesn't get back up.",
    "{target} crumples — they're out of the fight.",
    "That's the end of {target}. They won't be getting up.",
    "{target} takes a fatal hit and falls.",
]

_STUNNED_TEMPLATES = [
    "{target} is rocked by the impact — stunned!",
    "The hit staggers {target}, leaving them dazed.",
    "{target} catches a glancing blow and is stunned.",
]

_SPRAWLING_TEMPLATES = [
    "{target} is knocked sprawling by the force of the hit!",
    "The impact sends {target} tumbling to the ground.",
    "{target} goes down, sprawling in the dirt.",
]

_BRAWL_TEMPLATES = [
    "{winner} overpowers {loser} in a brutal close-quarters exchange!",
    "Blades flash as {winner} gets the better of {loser} in melee.",
    "{winner} and {loser} clash — {winner} comes out on top.",
]

_MOVE_TEMPLATES = [
    "{name} advances to {zone_desc}.",
    "{name} pushes forward into {zone_desc}.",
    "{name} repositions to {zone_desc}.",
    "{name} dashes to {zone_desc}, seeking better ground.",
]

_PANIC_TEMPLATES = [
    "The enemy's nerve breaks! {fled} turns tail and flees!",
    "Panic spreads through the enemy ranks — {fled} bolts for the exit!",
    "{fled} loses their nerve and abandons the fight!",
]

_HOLD_TEMPLATES = [
    "{name} holds position, scanning for threats.",
    "{name} stays put, weapon ready.",
    "{name} keeps low and waits.",
]


def _pick(templates: list[str], **kwargs) -> str:
    """Pick a random template and fill it in."""
    import random
    return random.choice(templates).format(**kwargs)


def narrate_phase_local(state: CombatState) -> str:
    """Generate a narrative description of what happened in the current phase.

    Template-based fallback when no API is available.
    Narrates the entire phase_log — use narrate_log_entries() for incremental narration.
    """
    lines = []
    log = state.phase_log

    if state.phase == CombatPhase.QUICK_ACTIONS:
        lines.append(_narrate_round_start(state))

    # Parse the log entries to generate narrative
    for entry in log:
        line = _narrate_log_entry(entry, state)
        if line:
            lines.append(line)

    if state.phase == CombatPhase.BATTLE_OVER:
        lines.append(_narrate_battle_end(state))

    return " ".join(lines) if lines else ""


def narrate_log_entries(entries: list[str]) -> str:
    """Generate narrative for a specific set of log entries.

    Use this for incremental narration (e.g. after a single action).
    """
    lines = []
    for entry in entries:
        line = _narrate_log_entry(entry, None)
        if line:
            lines.append(line)
    return " ".join(lines) if lines else ""


def _narrate_round_start(state: CombatState) -> str:
    """Narrate the start of a combat round."""
    r = state.round_number
    player_count = len(state.player_figures)
    enemy_count = len(state.enemy_figures)

    if r == 1:
        return (
            f"The firefight erupts. {player_count} colonists face off against "
            f"{enemy_count} hostiles across the battlefield."
        )
    elif r <= 3:
        return f"Round {r}. The fighting intensifies."
    else:
        return f"Round {r}. Both sides are battered but neither yields."


def _narrate_log_entry(entry: str, state: CombatState) -> str:
    """Convert a single log entry into narrative text."""
    entry_lower = entry.lower()

    # Skip meta-lines and raw movement logs
    if entry.startswith("===") or entry.startswith("---"):
        return ""
    if "reaction roll" in entry_lower:
        return ""
    if "-> QUICK" in entry or "-> SLOW" in entry:
        return ""
    # Contact entries — shown in mechanical log, skip in narrative
    if "(contact)" in entry_lower:
        return ""
    if "contact reveal" in entry_lower:
        return ""
    if "false alarm" in entry_lower:
        return ""
    if "new contact" in entry_lower:
        return ""
    if "additional hostile" in entry_lower:
        return ""

    # Objective interaction entries — already displayed in mechanical log
    if entry.startswith("**"):
        return ""

    # Shooting hits
    if "hit!" in entry_lower and "miss" not in entry_lower:
        parts = entry.split(":")
        if parts:
            shooter = parts[0].strip()
            return _pick(_SHOT_HIT_TEMPLATES, shooter=shooter, target="the target")

    # Shooting misses
    if "miss" in entry_lower:
        parts = entry.split(":")
        if parts:
            shooter = parts[0].strip()
            return _pick(_SHOT_MISS_TEMPLATES, shooter=shooter, target="the target")

    # Casualty
    if "casualty" in entry_lower:
        # Try to extract the target name
        for word in ["casualty", "killed", "eliminated"]:
            if word in entry_lower:
                return _pick(_CASUALTY_TEMPLATES, target=entry.split(":")[0].strip() if ":" in entry else "A combatant")

    # Stunned
    if "stunned" in entry_lower and "stun marker" not in entry_lower:
        return _pick(_STUNNED_TEMPLATES, target=entry.split(":")[0].strip() if ":" in entry else "A combatant")

    # Sprawling
    if "sprawling" in entry_lower:
        return _pick(_SPRAWLING_TEMPLATES, target=entry.split(":")[0].strip() if ":" in entry else "A combatant")

    # Movement
    if "moves to zone" in entry_lower:
        name = entry.split(" moves")[0].strip()
        return _pick(_MOVE_TEMPLATES, name=name, zone_desc="a new position")

    # Brawl
    if "wins brawl" in entry_lower or "overpowers" in entry_lower:
        return entry  # Already narrative enough

    # Panic
    if "panic" in entry_lower and "flees" in entry_lower:
        fled = entry.split(":")[-1].strip() if ":" in entry else "an enemy"
        return _pick(_PANIC_TEMPLATES, fled=fled)

    # Hold
    if "holds position" in entry_lower or "holds" in entry_lower:
        name = entry.split(" holds")[0].strip() if " holds" in entry else "A colonist"
        return _pick(_HOLD_TEMPLATES, name=name)

    # Aid
    if "aids" in entry_lower or "removed 1 stun" in entry_lower:
        return entry  # Keep as-is

    # Generic fallback — include if it has substance
    if len(entry) > 10 and not entry.startswith(" "):
        return entry

    return ""


def _narrate_battle_end(state: CombatState) -> str:
    """Narrate the battle conclusion."""
    if state.outcome == "player_victory":
        remaining = len(state.player_figures)
        return (
            f"The last hostile falls. {remaining} colonists stand amid the aftermath, "
            f"weapons still hot. Victory — but at what cost?"
        )
    elif state.outcome == "player_defeat":
        return (
            "The colony forces are overwhelmed. The survivors fall back, "
            "dragging their wounded through the dust. A bitter defeat."
        )
    return "The battle ends inconclusively."


def narrate_phase_api(
    state: CombatState,
    api_key: str = "",
) -> str:
    """Generate narrative using Claude API for richer prose.

    Falls back to local if API unavailable.
    """
    if not api_key:
        return narrate_phase_local(state)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        # Build a compact prompt from the phase log
        log_text = "\n".join(state.phase_log[-20:])  # Last 20 entries

        player_summary = ", ".join(
            f"{f.name} ({f.char_class}, zone {f.zone}, {f.status})"
            for f in state.player_figures
        )
        enemy_summary = ", ".join(
            f"{f.name} ({f.char_class}, zone {f.zone}, {f.status})"
            for f in state.enemy_figures
        )

        prompt = f"""You are narrating a tactical sci-fi battle in a gritty frontier style.
Write 2-3 vivid sentences describing what just happened. Be concise and punchy.
Reference specific characters by name. Use sensory details — smoke, dust, muzzle flash.

ROUND: {state.round_number}
PHASE: {state.phase.value}

COLONISTS: {player_summary or 'None standing'}
HOSTILES: {enemy_summary or 'None standing'}

COMBAT LOG:
{log_text}

Write the narration (2-3 sentences, no game mechanics language):"""

        from planetfall.api_tracker import tracked_api_call
        message = tracked_api_call(
            client, caller="combat_narrator",
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()

    except Exception:
        return narrate_phase_local(state)


def narrate_combat_summary_api(
    result: dict,
    api_key: str = "",
) -> str:
    """Generate a full battle summary narrative after combat ends.

    Args:
        result: The get_result() dict from CombatSession.
        api_key: Anthropic API key.
    """
    if not api_key:
        return _narrate_combat_summary_local(result)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        # Compress battle log to key moments
        key_moments = [
            line for line in result.get("battle_log", [])
            if any(kw in line.lower() for kw in
                   ["casualty", "hit!", "panic", "brawl", "victory", "defeat",
                    "round", "stunned", "sprawling"])
        ][:15]
        log_text = "\n".join(key_moments)

        prompt = f"""You are narrating the aftermath of a tactical sci-fi battle.
Write a 3-4 sentence battle summary in a gritty frontier style.
Include the outcome, notable moments, and the human cost.

OUTCOME: {'VICTORY' if result['victory'] else 'DEFEAT'}
ROUNDS: {result['rounds_played']}
ENEMIES KILLED: {result['enemies_killed']}
CHARACTER CASUALTIES: {', '.join(result['character_casualties']) or 'None'}
GRUNT CASUALTIES: {result['grunt_casualties']}

KEY MOMENTS:
{log_text}

Write the battle summary (3-4 sentences, no mechanics):"""

        from planetfall.api_tracker import tracked_api_call
        message = tracked_api_call(
            client, caller="combat_summary",
            model="claude-sonnet-4-20250514",
            max_tokens=250,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()

    except Exception:
        return _narrate_combat_summary_local(result)


def _narrate_combat_summary_local(result: dict) -> str:
    """Template-based battle summary."""
    victory = result.get("victory", False)
    rounds = result.get("rounds_played", 0)
    killed = result.get("enemies_killed", 0)
    char_cas = result.get("character_casualties", [])
    grunt_cas = result.get("grunt_casualties", 0)

    if victory:
        opening = f"After {rounds} rounds of brutal fighting, the colony forces prevail."
    else:
        opening = f"After {rounds} rounds of desperate combat, the colony forces are driven back."

    body = f"{killed} hostiles eliminated."
    if char_cas:
        body += f" But the cost is steep — {', '.join(char_cas)} fell in the fighting."
    if grunt_cas:
        body += f" {grunt_cas} grunt(s) lost."
    if not char_cas and not grunt_cas:
        body += " Remarkably, the team came through without losses."

    return f"{opening} {body}"

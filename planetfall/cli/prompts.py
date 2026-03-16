"""Interactive prompts for Planetfall CLI using questionary."""

from __future__ import annotations

import questionary
from questionary import Style

from planetfall.engine.models import (
    CharacterClass, ColonizationAgenda, Loyalty, SubSpecies, GameState,
    STARTING_PROFILES,
)
from planetfall.engine.campaign.setup import (
    MOTIVATION_TABLE, PRIOR_EXPERIENCE_TABLE,
)
from planetfall.engine.utils import format_display


class SaveAndQuit(Exception):
    """Raised when player requests save-and-quit from any prompt."""
    pass


QUIT_COMMANDS = {"/quit", "/exit", "/q"}

# Custom style for prompts
STYLE = Style([
    ("question", "bold"),
    ("answer", "fg:cyan bold"),
    ("pointer", "fg:cyan bold"),
    ("highlighted", "fg:cyan bold"),
    ("selected", "fg:green"),
])


def _check_quit(value) -> None:
    """Check if the user cancelled (Ctrl+C/None) or typed a quit command.

    Raises SaveAndQuit for any quit signal so the game saves and exits cleanly.
    """
    if value is None:
        raise SaveAndQuit()
    if isinstance(value, str) and value.strip().lower() in QUIT_COMMANDS:
        raise SaveAndQuit()


def flush_input():
    """Flush any buffered keystrokes so they don't skip the next prompt."""
    try:
        import msvcrt
        while msvcrt.kbhit():
            msvcrt.getch()
    except ImportError:
        import sys
        import termios
        termios.tcflush(sys.stdin, termios.TCIFLUSH)


def pause(message: str = "Press any key to continue..."):
    """Pause and wait for user to press any key."""
    flush_input()
    try:
        questionary.press_any_key_to_continue(message, style=STYLE).ask()
    except KeyboardInterrupt:
        raise SaveAndQuit()


def ask_text(message: str, default: str = "") -> str:
    """Ask for text input."""
    result = questionary.text(message, default=default, style=STYLE).ask()
    _check_quit(result)
    return result or default


def ask_select(message: str, choices: list[str]) -> str:
    """Ask user to select from a list."""
    result = questionary.select(message, choices=choices, style=STYLE).ask()
    _check_quit(result)
    return result


def ask_confirm(message: str, default: bool = True) -> bool:
    """Ask a yes/no question."""
    result = questionary.confirm(message, default=default, style=STYLE).ask()
    _check_quit(result)
    return result


def ask_number(message: str, min_val: int = 0, max_val: int = 100) -> int:
    """Ask for a number input."""
    while True:
        raw = questionary.text(
            f"{message} ({min_val}-{max_val})", style=STYLE
        ).ask()
        _check_quit(raw)
        try:
            val = int(raw)
            if min_val <= val <= max_val:
                return val
            print(f"Please enter a number between {min_val} and {max_val}.")
        except (ValueError, TypeError):
            print("Please enter a valid number.")


def ask_checkbox(message: str, choices: list[str]) -> list[str]:
    """Ask user to select multiple items."""
    result = questionary.checkbox(message, choices=choices, style=STYLE).ask()
    _check_quit(result)
    return result or []


# --- Campaign setup prompts ---


def prompt_campaign_name() -> str:
    return ask_text("Campaign name:", default="New Colony")


def prompt_colony_name() -> str:
    return ask_text("Colony name:", default="Home")


def prompt_admin_name() -> str:
    return ask_text("Administrator name:", default="Administrator")


def prompt_colonization_agenda() -> ColonizationAgenda | None:
    """Ask player to choose or roll their agenda."""
    choice = ask_select(
        "Colonization Agenda:",
        [
            "Roll randomly",
            "Scientific Mission (+3 RP)",
            "Corporate Funded (+2 Investigation Sites)",
            "Unity Colonization Drive (+3 Raw Materials)",
            "Independent Mission (+1 Story Point)",
            "Military Expedition (+2 Grunts)",
            "Affinity Group (+5 Morale)",
        ],
    )
    if choice == "Roll randomly":
        return None
    mapping = {
        "Scientific Mission (+3 RP)": ColonizationAgenda.SCIENTIFIC,
        "Corporate Funded (+2 Investigation Sites)": ColonizationAgenda.CORPORATE,
        "Unity Colonization Drive (+3 Raw Materials)": ColonizationAgenda.UNITY,
        "Independent Mission (+1 Story Point)": ColonizationAgenda.INDEPENDENT,
        "Military Expedition (+2 Grunts)": ColonizationAgenda.MILITARY,
        "Affinity Group (+5 Morale)": ColonizationAgenda.AFFINITY,
    }
    return mapping.get(choice)


def prompt_character_name(class_name: str, index: int) -> str:
    return ask_text(f"{class_name} #{index} name:")


def prompt_character_subspecies() -> SubSpecies:
    choice = ask_select(
        "Sub-species:",
        ["Standard Human", "Feral", "Hulker", "Stalker"],
    )
    mapping = {
        "Standard Human": SubSpecies.STANDARD,
        "Feral": SubSpecies.FERAL,
        "Hulker": SubSpecies.HULKER,
        "Stalker": SubSpecies.STALKER,
    }
    return mapping[choice]


# --- Character import prompts ---


def prompt_import_character(index: int) -> dict:
    """Prompt for creating a character with class template + motivation/experience selection."""
    print(f"\n--- Character {index} ---")
    name = ask_text("Name:")

    cls_choice = ask_select(
        "Class:",
        ["Scientist", "Scout", "Trooper"],
    )
    char_class = CharacterClass(cls_choice.lower())

    sub_species = SubSpecies.STANDARD
    if ask_confirm("Choose sub-species?", default=False):
        sub_species = prompt_character_subspecies()

    # Start from class template
    profile = STARTING_PROFILES[char_class].model_dump()
    if sub_species == SubSpecies.HULKER:
        profile["toughness"] = 5

    # Title and role (optional)
    title = ask_text("Title (e.g. Lt. Commander, optional):", default="")
    role = ask_text("Role (e.g. Head of Security, optional):", default="")

    # Motivation selection
    motivation_names = sorted(set(entry[2] for entry in MOTIVATION_TABLE))
    motivation = ask_select("Motivation:", motivation_names)

    # Prior Experience selection (with stat effects shown)
    exp_choices = ["None — fresh recruit"]
    exp_map: dict[str, dict] = {}
    seen = set()
    for _low, _high, exp_name, effects in PRIOR_EXPERIENCE_TABLE:
        if exp_name in seen:
            continue
        seen.add(exp_name)
        # Build a label showing what this experience gives
        effect_parts = []
        for stat, val in effects.items():
            if stat == "loyalty":
                effect_parts.append(f"Loyalty: {val.value}")
            elif stat == "story_points":
                effect_parts.append(f"+{val} SP")
            else:
                stat_label = {"reactions": "React", "speed": "Spd", "combat_skill": "CS",
                              "toughness": "Tough", "savvy": "Savvy", "xp": "XP",
                              "kill_points": "KP"}.get(stat, stat)
                effect_parts.append(f"{stat_label} +{val}")
        label = f"{exp_name} ({', '.join(effect_parts)})" if effect_parts else exp_name
        exp_choices.append(label)
        exp_map[label] = effects

    exp_choice = ask_select("Prior Experience:", exp_choices)

    # Apply experience stat effects
    loyalty = Loyalty.COMMITTED
    xp = 0
    kill_points = 0
    if not exp_choice.startswith("None"):
        effects = exp_map[exp_choice]
        prior_experience = exp_choice.split(" (")[0]  # strip the effect label
        for stat, val in effects.items():
            if stat == "loyalty":
                loyalty = val
            elif stat == "story_points":
                pass  # handled at game state level
            elif stat in profile:
                profile[stat] = profile[stat] + val
            elif stat == "xp":
                xp = val
            elif stat == "kill_points":
                kill_points = val
    else:
        prior_experience = ""

    # Narrative background (free text)
    print("Enter character background (leave blank to skip, or paste text):")
    narrative_bg = ask_text("Background:", default="")

    return {
        "name": name,
        "class": char_class,
        "sub_species": sub_species,
        "title": title,
        "role": role,
        "reactions": profile["reactions"],
        "speed": profile["speed"],
        "combat_skill": profile["combat_skill"],
        "toughness": profile["toughness"],
        "savvy": profile["savvy"],
        "xp": xp,
        "kill_points": kill_points,
        "loyalty": loyalty,
        "motivation": motivation,
        "prior_experience": prior_experience,
        "narrative_background": narrative_bg,
    }


# --- Turn prompts ---


def prompt_mission_choice(options: list[dict]) -> int:
    """Ask player to choose a mission. Returns 0-based index."""
    choices = []
    for opt in options:
        name = format_display(opt["type"].value)
        forced = " (FORCED)" if opt.get("forced") else ""
        choices.append(f"{name}{forced} — {opt['description']}")

    result = ask_select("Choose your mission:", choices)
    return choices.index(result)


def prompt_deployment(
    available_characters: list[str],
    max_slots: int,
    grunt_count: int = 0,
    bot_available: bool = False,
    civilians_available: bool = False,
) -> dict:
    """Ask player which units to deploy within max_slots.

    Characters and bot are selected via checkbox. Grunts and civilians
    are single numeric entries (how many to bring).
    Enforces the max_slots limit — cannot over-select.

    Returns dict with keys:
        characters (list[str]), grunts (int), bot (bool), civilians (int).
    """
    # Phase 1: select characters and bot via checkbox
    unit_choices = list(available_characters)
    if bot_available:
        unit_choices.append("[Bot]")

    total_available = len(unit_choices) + grunt_count
    if total_available <= max_slots and not civilians_available:
        if ask_confirm(f"Deploy all {total_available} available units?"):
            chars = list(available_characters)
            bot = bot_available
            grunts = grunt_count
            return {"characters": chars, "grunts": grunts, "bot": bot, "civilians": 0}

    # Select named units (characters + bot)
    while True:
        selected = ask_checkbox(
            f"Select characters to deploy (max {max_slots} total):",
            unit_choices,
        )
        if len(selected) > max_slots:
            print(f"Too many selected ({len(selected)}). Max is {max_slots}.")
            continue
        break

    characters = [s for s in selected if not s.startswith("[")]
    bot = "[Bot]" in selected
    used_slots = len(selected)

    # Phase 2: grunts as a single numeric value
    remaining_slots = max_slots - used_slots
    grunts = 0
    if grunt_count > 0 and remaining_slots > 0:
        max_grunts = min(grunt_count, remaining_slots)
        if max_grunts == 1:
            if ask_confirm("Deploy 1 grunt?"):
                grunts = 1
        else:
            grunts = ask_number(
                f"How many grunts to deploy?",
                min_val=0, max_val=max_grunts,
            )
    remaining_slots -= grunts

    # Phase 3: civilians (unlimited pool, capped by remaining slots)
    civilians = 0
    if civilians_available and remaining_slots > 0:
        civilians = ask_number(
            f"How many civilians to deploy?",
            min_val=0, max_val=remaining_slots,
        )

    return {"characters": characters, "grunts": grunts, "bot": bot, "civilians": civilians}


def prompt_raw_materials_repair(current: int, damage: int) -> int:
    """Ask how many raw materials to spend on repairs."""
    max_spend = min(3, current, abs(damage))
    if max_spend <= 0:
        return 0
    return ask_number(
        f"Spend raw materials on repairs? (have {current}, damage: {damage})",
        min_val=0, max_val=max_spend,
    )


def ask_sector_coords(
    message: str,
    valid_ids: list[int],
    cols: int = 6,
) -> int:
    """Ask user to enter sector coordinates as row,col. Returns sector_id."""
    # Build a set of valid (row,col) tuples for quick lookup
    valid_coords = {(sid // cols, sid % cols): sid for sid in valid_ids}

    while True:
        raw = questionary.text(
            f"{message} (row,col e.g. 2,3)", style=STYLE
        ).ask()
        _check_quit(raw)
        raw = raw.strip()
        try:
            parts = raw.replace(" ", "").split(",")
            if len(parts) == 2:
                r, c = int(parts[0]), int(parts[1])
                if (r, c) in valid_coords:
                    return valid_coords[(r, c)]
            print(f"Invalid coordinates. Valid sectors: "
                  f"{', '.join(f'{sid // cols},{sid % cols}' for sid in valid_ids[:8])}"
                  f"{'...' if len(valid_ids) > 8 else ''}")
        except ValueError:
            print("Enter coordinates as row,col (e.g. 2,3)")


def prompt_continue() -> bool:
    """Ask if player wants to continue to next turn."""
    return ask_confirm("Continue to next turn?")


def prompt_deployment_zones(
    figure_names: list[str],
    available_zones: list[tuple[int, int]],
    zone_capacity: int = 2,
) -> dict[str, tuple[int, int]]:
    """Let player assign deployment zones for each figure.

    Args:
        figure_names: Names of figures to place.
        available_zones: List of (row, col) zones on the player edge.
        zone_capacity: Max figures per zone.

    Returns:
        dict mapping figure_name -> (row, col).
    """
    assignments: dict[str, tuple[int, int]] = {}
    zone_counts: dict[tuple[int, int], int] = {z: 0 for z in available_zones}

    for name in figure_names:
        # Build choices showing zone coordinates and remaining capacity
        choices = []
        for z in available_zones:
            remaining = zone_capacity - zone_counts[z]
            if remaining > 0:
                choices.append(f"Zone {z[0]},{z[1]} ({remaining} slots)")

        if not choices:
            # Fallback: no capacity left, use first zone
            assignments[name] = available_zones[0]
            continue

        choice = ask_select(f"Place {name} in:", choices)
        # Parse zone from choice
        parts = choice.split(" ")[1].split(",")
        zone = (int(parts[0]), int(parts[1]))
        assignments[name] = zone
        zone_counts[zone] = zone_counts.get(zone, 0) + 1

    return assignments


def prompt_loadout(
    state: GameState,
    deployed_names: list[str],
    bot_deploy: bool = False,
    grunt_count: int = 0,
) -> dict[str, str]:
    """Let each deployed character choose their weapon for combat.

    Standard class weapons are always available. Tier 1/2 weapons
    require the appropriate manufacturing buildings.
    Returns dict mapping character_name -> chosen weapon name.
    Special key "grunt_lmg" -> "1" if a grunt takes an LMG.
    """
    from planetfall.engine.models import get_available_loadout

    loadout: dict[str, str] = {}
    buildings = state.colony.buildings
    unlocked_apps = set(state.tech_tree.unlocked_applications)

    for name in deployed_names:
        char = next((c for c in state.characters if c.name == name), None)
        if not char:
            continue

        weapons = get_available_loadout(char.char_class.value, buildings, unlocked_apps)
        if not weapons:
            loadout[name] = "Colony Rifle"
            continue

        if len(weapons) == 1:
            wpn = weapons[0]
            print(f"  {name} ({char.char_class.value}): {_format_weapon(wpn)}")
            loadout[name] = wpn.name
            continue

        # Multiple choices — let player pick
        choices = [_format_weapon(w) for w in weapons]
        choice = ask_select(
            f"{name} ({char.char_class.value}) — choose weapon:",
            choices,
        )
        idx = choices.index(choice)
        loadout[name] = weapons[idx].name

    # Bot weapon selection (civilian weapons only)
    if bot_deploy:
        bot_weapons = get_available_loadout("bot", buildings, unlocked_apps)
        if len(bot_weapons) > 1:
            choices = [_format_weapon(w) for w in bot_weapons]
            choice = ask_select("Colony Bot (bot) — choose weapon:", choices)
            idx = choices.index(choice)
            loadout["Colony Bot"] = bot_weapons[idx].name
        elif bot_weapons:
            print(f"  Colony Bot (bot): {_format_weapon(bot_weapons[0])}")
            loadout["Colony Bot"] = bot_weapons[0].name
        else:
            loadout["Colony Bot"] = "Colony Rifle"

    # Grunt LMG option: if fireteam of 3+, one grunt may take LMG
    if grunt_count >= 3:
        lmg_choice = ask_confirm(
            f"Fireteam has {grunt_count} grunts — equip one with a Light Machine Gun?"
        )
        if lmg_choice:
            loadout["grunt_lmg"] = "1"

    return loadout


def _format_weapon(w) -> str:
    """Format a weapon for display in selection list."""
    parts = [w.name]
    if w.range_inches > 0:
        parts.append(f"{w.range_inches}\"")
    else:
        parts.append("melee")
    if w.shots > 0:
        parts.append(f"{w.shots} shot{'s' if w.shots > 1 else ''}")
    if w.damage_bonus:
        parts.append(f"+{w.damage_bonus} dmg")
    combat_traits = [t for t in w.traits if t not in (
        "civilian", "scientist", "scout", "trooper", "grunt",
    )]
    if combat_traits:
        parts.append(f"[{', '.join(combat_traits)}]")
    return " | ".join(parts)


def prompt_reaction_assignment(
    dice: list[int],
    figures: list[tuple[str, int]],
) -> dict[str, int]:
    """Let player assign reaction dice to figures.

    Args:
        dice: Sorted list of rolled dice values.
        figures: List of (figure_name, reactions_stat) tuples.

    Returns:
        dict mapping figure_name -> assigned die value.
    """
    if not dice or not figures:
        return {}

    available = list(dice)
    assignments: dict[str, int] = {}

    for name, reactions in figures:
        if not available:
            break
        if len(available) == 1:
            # Last die, auto-assign
            assignments[name] = available.pop(0)
            continue

        # Show available dice and figure info
        die_choices = []
        for d in sorted(set(available)):
            quick_mark = " (Q)" if d <= reactions else " (S)"
            count = available.count(d)
            label = f"{d}{quick_mark}"
            if count > 1:
                label += f" x{count}"
            die_choices.append(label)

        choice = ask_select(
            f"Assign die to {name} (Reactions {reactions}):",
            die_choices,
        )
        # Parse the chosen die value
        chosen = int(choice.split(" ")[0])
        available.remove(chosen)
        assignments[name] = chosen

    return assignments

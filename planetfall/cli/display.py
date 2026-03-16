"""Rich terminal output for Planetfall CLI."""

from __future__ import annotations

import os

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from planetfall.engine.models import GameState, Character, TurnEvent, STARTING_PROFILES
from planetfall.engine.utils import format_display
from planetfall.cli.styles import (
    TERRAIN_SYMBOL, TERRAIN_STYLE, TERRAIN_BG,
    OVERLAY_ACTIVE, MOVE_STANDARD, MOVE_RUSH,
    SHOOT_CLOSE, SHOOT_MEDIUM, SHOOT_COVER,
    VISION_CLOSE, VISION_FAR, VISION_EXTREME,
    PLAYER_STYLE, ENEMY_STYLE, CONTACT_STYLE, STORM_STYLE, SLYN_STYLE,
    SLEEPER_STYLE, ACTIVE_FIG_STYLE_TEMPLATE, HIGHLIGHTED_ENEMY_STYLE,
    OBJECTIVE_STYLE,
    OVERLAY_VISION, OVERLAY_MOVEMENT, OVERLAY_SHOOTING, OVERLAY_MODES,
    OVERLAY_LEGENDS,
    BOX_UNICODE, BOX_ASCII,
)

console = Console()


def clear_screen():
    """Clear the terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")


_TITLE_ART = r"""[bold cyan]
 ____  _       _    _   _ _____ _____ _____ _    _     _
|  _ \| |     / \  | \ | | ____|_   _|  ___/ \  | |   | |
| |_) | |    / _ \ |  \| |  _|   | | | |_ / _ \ | |   | |
|  __/| |__ / ___ \| |\  | |___  | | |  _/ ___ \| |__ | |__
|_|   |____/_/   \_|_| \_|_____| |_| |_|/_/   \_|____|____|[/bold cyan]
[dim]       Adventure Wargaming on Alien Worlds - AI Game Master[/dim]"""


def print_title():
    """Print the game title with ASCII art."""
    console.print(_TITLE_ART)
    console.print()


def print_colony_status(state: GameState):
    """Print a summary of the colony status."""
    colony = state.colony
    res = colony.resources

    table = Table(
        title=f"[bold]{colony.name}[/bold] — Turn {state.current_turn}",
        box=box.ROUNDED,
        border_style="blue",
        show_header=False,
        pad_edge=True,
    )
    table.add_column("Stat", style="cyan", width=20)
    table.add_column("Value", style="white", width=10)
    table.add_column("Stat", style="cyan", width=20)
    table.add_column("Value", style="white", width=10)

    morale_style = "green" if colony.morale >= 0 else "red"
    integrity_style = "green" if colony.integrity >= 0 else "red"

    table.add_row(
        "Colony Morale", f"[{morale_style}]{colony.morale}[/{morale_style}]",
        "Colony Integrity", f"[{integrity_style}]{colony.integrity}[/{integrity_style}]",
    )
    table.add_row(
        "Story Points", str(res.story_points),
        "Colony Defenses", str(colony.defenses),
    )
    table.add_row(
        "Build Points", str(res.build_points),
        "Research Points", str(res.research_points),
    )
    table.add_row(
        "Raw Materials", str(res.raw_materials),
        "Augmentation Pts", str(res.augmentation_points),
    )
    table.add_row(
        "Grunts", str(state.grunts.count),
        "Bot", "Operational" if state.grunts.bot_operational else "[red]Damaged[/red]",
    )
    table.add_row(
        "Roster Size", f"{len(state.characters)}/8",
        "Agenda", state.settings.colonization_agenda.value.title(),
    )
    console.print(table)

    # Research progress
    if state.tech_tree.theories or state.tech_tree.unlocked_applications:
        from planetfall.engine.campaign.research import THEORIES, APPLICATIONS
        lines = []

        # Theories in progress / completed
        for tid, theory in state.tech_tree.theories.items():
            tdef = THEORIES.get(tid)
            if tdef:
                if theory.invested_rp >= tdef.rp_cost:
                    lines.append(f"  [green]✓ {tdef.name}[/green] [dim](completed)[/dim]")
                else:
                    lines.append(f"  [yellow]◦ {tdef.name}[/yellow] [dim]({theory.invested_rp}/{tdef.rp_cost} RP)[/dim]")

        # Unlocked applications
        for app_id in state.tech_tree.unlocked_applications:
            adef = APPLICATIONS.get(app_id)
            if adef:
                lines.append(f"  [cyan]• {adef.name}[/cyan] [dim]— {adef.description}[/dim]")

        if lines:
            console.print("\n[bold]Research & Applications[/bold]")
            for line in lines:
                console.print(line)

    # Buildings
    if state.colony.buildings:
        console.print("\n[bold]Buildings[/bold]")
        for b in state.colony.buildings:
            effects_str = f" [dim]— {', '.join(b.effects)}[/dim]" if b.effects else ""
            console.print(f"  [cyan]• {b.name}[/cyan]{effects_str}")


def print_roster(state: GameState):
    """Print the character roster."""
    table = Table(
        title="[bold]Colony Roster[/bold]",
        box=box.SIMPLE_HEAVY,
        border_style="green",
    )
    table.add_column("Name", style="bold white")
    table.add_column("Class", style="cyan")
    table.add_column("React", justify="center")
    table.add_column("Speed", justify="center")
    table.add_column("Combat", justify="center")
    table.add_column("Tough", justify="center")
    table.add_column("Savvy", justify="center")
    table.add_column("XP", justify="center")
    table.add_column("KP", justify="center")
    table.add_column("Status", style="dim")

    for char in state.characters:
        status = "[green]Ready[/green]"
        if char.sick_bay_turns > 0:
            status = f"[red]Sick Bay ({char.sick_bay_turns}t)[/red]"

        table.add_row(
            char.name,
            char.char_class.value.title(),
            str(char.reactions),
            f"{char.speed}\"",
            f"+{char.combat_skill}",
            str(char.toughness),
            f"+{char.savvy}",
            str(char.xp),
            str(char.kill_points),
            status,
        )

    console.print(table)


def pause_and_clear():
    """Pause for user input, then clear the screen."""
    from planetfall.cli.prompts import pause
    pause()
    clear_screen()


def print_step_header(step: int, name: str, state: GameState | None = None):
    """Print a campaign turn step header, optionally with colony status."""
    pause_and_clear()
    if state is not None:
        print_colony_status(state)
        print_map(state)
    console.print()
    console.rule(f"[bold yellow]Step {step}: {name}[/bold yellow]")


def print_events(events: list[TurnEvent]):
    """Print turn events."""
    for event in events:
        icon = _event_icon(event.event_type.value)
        console.print(f"  {icon} {event.description}")
        for roll in event.dice_rolls:
            console.print(
                f"    [dim]{roll.label}: {roll.values} = {roll.total}[/dim]"
            )


def print_mission_options(options: list[dict]):
    """Print available mission choices with rewards and target info."""
    table = Table(
        title="[bold]Available Missions[/bold]",
        box=box.SIMPLE,
        show_header=True,
    )
    table.add_column("#", style="bold cyan", width=3)
    table.add_column("Mission", style="white", min_width=14)
    table.add_column("Description", style="dim")
    table.add_column("Rewards", style="green")

    for i, opt in enumerate(options, 1):
        forced = " [red](FORCED)[/red]" if opt.get("forced") else ""
        mission_name = format_display(opt["type"].value) + forced

        desc = opt["description"]
        targets = opt.get("target_sectors")
        if targets and len(targets) > 1:
            details = opt.get("target_details")
            if details:
                desc += f"\n[dim]  Sectors: {', '.join(details)}[/dim]"

        rewards = opt.get("rewards", "")

        table.add_row(str(i), mission_name, desc, rewards)

    console.print(table)


def _sector_symbol_parts(sector, colony_id: int) -> tuple[str, str]:
    """Get the display symbol and style for a sector as (text, style)."""
    if sector.sector_id == colony_id:
        return ("H", "bold green")
    elif sector.enemy_occupied_by:
        return ("X", "red")
    elif sector.has_ancient_site:
        return ("A", "yellow")
    elif sector.has_investigation_site:
        return ("?", "cyan")
    elif sector.has_ancient_sign:
        return ("S", "magenta")
    elif sector.status == SectorStatus.EXPLORED:
        return (".", "dim")
    elif sector.status == SectorStatus.EXPLOITED:
        return ("+", "green")
    return ("-", "dim")


def print_map(state: GameState, cols: int = 6):
    """Print the campaign map as a fixed-width grid with box-drawing borders."""
    sectors = state.campaign_map.sectors
    colony_id = state.campaign_map.colony_sector_id
    total = len(sectors)
    rows = (total + cols - 1) // cols

    CELL_W = 7
    LABEL_W = 3

    B = _BOX_UNICODE if _detect_unicode_support() else _BOX_ASCII

    # -- Title --
    console.print(f"\n  [bold]Campaign Map[/]")

    # -- Column header --
    header = Text()
    header.append(" " * LABEL_W + " ")
    for c in range(cols):
        col_str = str(c).center(CELL_W)
        header.append(col_str, style="bold cyan")
        if c < cols - 1:
            header.append(" ")
    console.print(header)

    # -- Border helpers --
    def h_border(left: str, mid: str, right: str) -> str:
        return (" " * LABEL_W) + left + mid.join(
            [B["h"] * CELL_W] * cols
        ) + right

    top_border = h_border(B["tl"], B["mt"], B["tr"])
    mid_border = h_border(B["ml"], B["cx"], B["mr"])
    bot_border = h_border(B["bl"], B["mb"], B["br"])

    console.print(top_border, style="dim")

    for r in range(rows):
        line1 = Text()  # sector symbol
        line2 = Text()  # resource/hazard

        row_label = str(r).rjust(LABEL_W - 1) + " "
        line1.append(row_label, style="bold")
        line2.append(" " * LABEL_W)

        for c in range(cols):
            idx = r * cols + c

            line1.append(B["v"], style="dim")
            line2.append(B["v"], style="dim")

            cell1 = Text()
            cell2 = Text()

            if idx < total:
                sector = sectors[idx]
                sym, sym_style = _sector_symbol_parts(sector, colony_id)

                # Line 1: centered symbol
                cell1.append(f"  {sym}  ", style=sym_style)

                # Line 2: resource/hazard for explored sectors
                if (sector.status != SectorStatus.UNEXPLORED
                        and sector.sector_id != colony_id
                        and (sector.resource_level > 0 or sector.hazard_level > 0)):
                    cell2.append(" ", style="")
                    cell2.append(f"R{sector.resource_level}", style="blue")
                    cell2.append(" ", style="")
                    cell2.append(f"H{sector.hazard_level}", style="red")

            _pad_cell(cell1, CELL_W)
            _pad_cell(cell2, CELL_W)
            line1.append(cell1)
            line2.append(cell2)

        line1.append(B["v"], style="dim")
        line2.append(B["v"], style="dim")

        console.print(line1)
        console.print(line2)

        if r < rows - 1:
            console.print(mid_border, style="dim")

    console.print(bot_border, style="dim")

    # -- Legend --
    console.print(
        "  [dim]Sectors:[/] "
        "[bold green]H[/]=Colony  "
        "[cyan]?[/]=Investigation  "
        "[magenta]S[/]=Sign  "
        "[yellow]A[/]=Ancient  "
        "[red]X[/]=Enemy  "
        "[dim].[/]=Explored  "
        "[green]+[/]=Exploited  "
        "[dim]-[/]=Unknown"
    )
    console.print(
        "  [blue]R#[/]=Resource  [red]H#[/]=Hazard  "
        "[dim]Coordinates: row,col (e.g. 2,3)[/dim]"
    )
    console.print()


def _stat_increases(char: Character) -> list[str]:
    """Return list of stat increases over the class baseline."""
    base = STARTING_PROFILES.get(char.char_class)
    increases = []
    stat_labels = [
        ("reactions", "React"),
        ("speed", "Spd"),
        ("combat_skill", "CS"),
        ("toughness", "Tough"),
        ("savvy", "Savvy"),
    ]
    for field, label in stat_labels:
        current = getattr(char, field, 0)
        baseline = getattr(base, field, 0) if base else 0
        diff = current - baseline
        if diff > 0:
            increases.append(f"{label} +{diff}")
        elif diff < 0:
            increases.append(f"{label} {diff}")
    if char.xp > 0:
        increases.append(f"XP {char.xp}")
    if char.kill_points > 0:
        increases.append(f"KP {char.kill_points}")
    return increases


import re

_NARRATIVE_HEADER_RE = re.compile(
    r"^\*\*[A-Z ]+:?\*\*\s*$|^\*\*[A-Za-z ]+:?\*\*\s*$|^#+\s",
)

# Inline bold labels like **Distinctive trait:** at start of a line
_INLINE_BOLD_LABEL_RE = re.compile(r"^\*\*[A-Za-z ]+:?\*\*\s*")


def _clean_narrative(text: str) -> str:
    """Strip markdown headers and bold section labels from narrative text."""
    lines = text.strip().split("\n")
    cleaned = []
    for ln in lines:
        stripped = ln.strip()
        # Skip lines that are just bold headers like **PERSONALITY SKETCH**
        if _NARRATIVE_HEADER_RE.match(stripped):
            continue
        # Strip inline bold labels like **Distinctive trait:** from start of line
        stripped = _INLINE_BOLD_LABEL_RE.sub("", stripped)
        # Skip empty lines that follow removed headers
        if not stripped and cleaned and not cleaned[-1]:
            continue
        if stripped:
            cleaned.append(stripped)
        else:
            cleaned.append(ln)
    return "\n".join(cleaned).strip()


def print_character_backgrounds(state: GameState):
    """Print character backgrounds with formatted motivation, experience, and stats."""
    console.print("\n[bold]Character Backgrounds[/bold]")
    for char in state.characters:
        # Header: title + name + role + class
        name_parts = []
        if char.title:
            name_parts.append(f"[bold white]{char.title}[/bold white]")
        name_parts.append(f"[bold cyan]{char.name}[/bold cyan]")
        if char.role:
            name_parts.append(f"[dim italic]{char.role}[/dim italic]")
        header = f"  {' '.join(name_parts)} — [dim]{char.char_class.value.title()}[/dim]"
        console.print(header)

        # Motivation + Prior Experience + Notable Event + Stat increases — one line
        tags = []
        if char.background_motivation:
            tags.append(f"[green]{char.background_motivation}[/green]")
        if char.background_prior_experience:
            tags.append(f"[dark_orange]{char.background_prior_experience}[/dark_orange]")
        if char.background_notable_events:
            tags.append(f"[yellow]{' → '.join(char.background_notable_events)}[/yellow]")
        increases = _stat_increases(char)
        for inc in increases:
            tags.append(f"[blue]{inc}[/blue]")
        if tags:
            console.print(f"    {' | '.join(tags)}")

        # Narrative background (strip headers and bold section labels)
        if char.narrative_background:
            bg = _clean_narrative(char.narrative_background)
            if bg:
                console.print(f"    [dim italic]{bg}[/dim italic]")

        console.print()


def print_turn_summary(events: list[TurnEvent]):
    """Print end-of-turn summary."""
    console.print()
    console.print(Panel(
        "\n".join(f"  {e.description}" for e in events),
        title="[bold]Turn Summary[/bold]",
        border_style="blue",
        box=box.ROUNDED,
    ))


def _event_icon(event_type: str) -> str:
    """Get a text marker for event types."""
    icons = {
        "recovery": "[green]>[/green]",
        "repair": "[blue]>[/blue]",
        "scout_report": "[cyan]>[/cyan]",
        "enemy_activity": "[red]>[/red]",
        "colony_event": "[yellow]>[/yellow]",
        "mission": "[magenta]>[/magenta]",
        "injury": "[red]>[/red]",
        "experience": "[green]>[/green]",
        "morale": "[yellow]>[/yellow]",
        "replacement": "[cyan]>[/cyan]",
        "research": "[blue]>[/blue]",
        "building": "[blue]>[/blue]",
        "character_event": "[magenta]>[/magenta]",
        "combat": "[red]>[/red]",
        "narrative": "[dim]>[/dim]",
    }
    return icons.get(event_type, ">")


# Need the import for print_map
from planetfall.engine.models import SectorStatus


# --- Battlefield Grid Renderer ---

from planetfall.engine.combat.battlefield import (
    Battlefield, Figure, FigureSide, FigureStatus, TerrainType,
)

_TERRAIN_SYMBOL = TERRAIN_SYMBOL
_TERRAIN_STYLE = TERRAIN_STYLE


def _weapon_abbrev(weapon_name: str) -> str:
    """Generate 2-letter weapon type abbreviation from weapon name."""
    _ABBREVS = {
        "rattle gun": "RG",
        "military rifle": "MR",
        "colony rifle": "CR",
        "auto rifle": "AR",
        "hunting rifle": "HR",
        "scrap gun": "SG",
        "hand cannon": "HC",
        "blade": "BL",
        "ripper sword": "RS",
        "shatter axe": "SA",
        "shotgun": "SH",
        "infantry rifle": "IR",
        "trooper rifle": "TR",
        "assault gun": "AG",
        "light machine gun": "LM",
        "flame projector": "FP",
        "handgun": "HG",
        "colonial shotgun": "CS",
        "scout pistol": "SP",
        "natural weapons": "NW",
        "unarmed": "UA",
    }
    key = weapon_name.strip().lower()
    if key in _ABBREVS:
        return _ABBREVS[key]
    # Fallback: first letters of first two words, or first two chars
    parts = weapon_name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return weapon_name[:2].upper()


# Counters for assigning sequential figure numbers within a battle
_enemy_label_map: dict[str, str] = {}
_enemy_counter: int = 0
_player_label_map: dict[str, str] = {}
_player_counter: int = 0


def _name_abbrev(name: str) -> str:
    """Generate 2-letter abbreviation from a figure name.

    Multi-word: first letter of each of first two words (e.g. "Sarah Chen" -> "SC").
    Single word: first two letters (e.g. "Bot" -> "BO").
    """
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return name[:2].upper()


def _allocate_code(fig: Figure) -> str:
    """Allocate and cache the base code (e.g. '1RG') for a figure. Not including status suffixes."""
    global _enemy_counter, _player_counter
    if fig.side == FigureSide.ENEMY:
        if fig.name not in _enemy_label_map:
            _enemy_counter += 1
            _enemy_label_map[fig.name] = f"{_enemy_counter}{fig.abbreviation}"
        return _enemy_label_map[fig.name]
    else:
        if fig.name not in _player_label_map:
            _player_counter += 1
            _player_label_map[fig.name] = f"{_player_counter}{fig.abbreviation}"
        return _player_label_map[fig.name]


def get_figure_map_label(fig: Figure) -> str:
    """Return the short map label (e.g. '3BF') for a figure, allocating one if needed."""
    return _allocate_code(fig)


def reset_enemy_labels():
    """Reset all figure label assignments (call at start of each battle)."""
    global _enemy_label_map, _enemy_counter, _player_label_map, _player_counter
    _enemy_label_map = {}
    _enemy_counter = 0
    _player_label_map = {}
    _player_counter = 0


def _fig_label(fig: Figure) -> str:
    """3-char label for a figure on the grid, wrapped in Rich markup.

    All figures use XYY format: X=sequential number, YY=abbreviation.
    Enemies: YY = weapon abbreviation. Players: YY = name initials.
    """
    label, style = _fig_label_parts(fig)
    return f"[{style}]{label}[/]"


def _build_zone_overlay(
    bf: Battlefield,
    origin: tuple[int, int],
    criteria_fn: "Callable[[Battlefield, tuple[int, int], tuple[int, int]], str | None]",
) -> dict[tuple[int, int], str]:
    """Generic overlay builder: iterate all zones and apply criteria_fn.

    Args:
        bf: The battlefield.
        origin: The active figure's zone (marked with OVERLAY_ACTIVE).
        criteria_fn: Called as criteria_fn(bf, origin, pos) for each zone.
            Should return a style string for the zone, or None to skip.

    Returns:
        Dict mapping (row, col) -> Rich background style string.
    """
    overlay: dict[tuple[int, int], str] = {}
    overlay[origin] = OVERLAY_ACTIVE

    for r in range(bf.rows):
        for c in range(bf.cols):
            pos = (r, c)
            if pos == origin:
                continue
            style = criteria_fn(bf, origin, pos)
            if style is not None:
                overlay[pos] = style

    return overlay


def _shooting_criteria(bf: Battlefield, origin: tuple[int, int], pos: tuple[int, int]) -> str | None:
    """Criteria function for shooting overlay: returns style based on range/cover."""
    from planetfall.engine.combat.battlefield import ZONE_INCHES

    los = bf.check_los(origin, pos)
    if los == "blocked":
        return None
    dist = bf.zone_distance(origin, pos)
    # Need fig context — stored on the function by the caller
    approx_inches = dist * ZONE_INCHES
    if approx_inches > _shooting_criteria._weapon_range:
        return None

    if bf.has_cover_los(origin, pos):
        return SHOOT_COVER
    elif dist <= 2:
        return SHOOT_CLOSE
    else:
        return SHOOT_MEDIUM


def _vision_criteria(bf: Battlefield, origin: tuple[int, int], pos: tuple[int, int]) -> str | None:
    """Criteria function for vision overlay: returns style based on LoS and detection range."""
    from planetfall.engine.combat.battlefield import (
        CONTACT_CLOSE_RANGE, CONTACT_FAR_RANGE, CONTACT_EXTREME_RANGE,
    )

    los = bf.check_los(origin, pos)
    if los == "blocked":
        return None
    dist = bf.zone_distance(origin, pos)

    if dist <= CONTACT_CLOSE_RANGE:
        return VISION_CLOSE
    elif dist <= CONTACT_FAR_RANGE:
        return VISION_FAR if los == "clear" else VISION_EXTREME
    elif dist <= CONTACT_EXTREME_RANGE:
        return VISION_EXTREME if los == "clear" else None
    return None


def _build_movement_map(
    bf: Battlefield, fig: Figure,
) -> dict[tuple[int, int], str]:
    """Build a zone -> background style map showing movement range.

    Movement has unique logic (scout jumps, rush zones, capacity checks)
    that doesn't fit the simple per-zone criteria pattern, so it builds
    its overlay directly while reusing the shared style constants.
    """
    from planetfall.engine.combat.battlefield import (
        move_zones as calc_move_zones,
        rush_available,
        rush_total_zones,
    )

    movement: dict[tuple[int, int], str] = {}
    movement[fig.zone] = OVERLAY_ACTIVE

    is_scout = fig.char_class == "scout"
    adj_zones = bf.adjacent_zones(*fig.zone)
    num_move = calc_move_zones(fig.speed)

    # Standard move zones
    std_zones: set[tuple[int, int]] = set()
    if num_move > 0:
        if is_scout:
            for z in bf.jump_destinations(*fig.zone, num_move):
                std_zones.add(z)
        elif num_move >= 2:
            for dr in range(-num_move, num_move + 1):
                for dc in range(-num_move, num_move + 1):
                    nr, nc = fig.zone[0] + dr, fig.zone[1] + dc
                    if (0 <= nr < bf.rows and 0 <= nc < bf.cols
                            and max(abs(dr), abs(dc)) <= num_move
                            and (nr, nc) != fig.zone):
                        if bf.get_zone(nr, nc).terrain != TerrainType.IMPASSABLE:
                            std_zones.add((nr, nc))
        else:
            for z in adj_zones:
                if bf.get_zone(*z).terrain != TerrainType.IMPASSABLE:
                    std_zones.add(z)

    for z in std_zones:
        if bf.zone_has_capacity(*z, fig.side):
            movement[z] = MOVE_STANDARD

    # Rush zones (beyond standard move)
    if rush_available(fig.speed):
        rush_reach = rush_total_zones(fig.speed)
        for r in range(bf.rows):
            for c in range(bf.cols):
                pos = (r, c)
                if pos in movement or pos == fig.zone:
                    continue
                dist = bf.zone_distance(fig.zone, pos)
                if 0 < dist <= rush_reach:
                    zone = bf.get_zone(r, c)
                    if (zone.terrain != TerrainType.IMPASSABLE
                            and bf.zone_has_capacity(r, c, fig.side)):
                        movement[pos] = MOVE_RUSH

    return movement


def _build_shooting_map(
    bf: Battlefield, fig: Figure,
) -> dict[tuple[int, int], str]:
    """Build shooting overlay using the generic zone overlay builder."""
    _shooting_criteria._weapon_range = fig.weapon_range
    return _build_zone_overlay(bf, fig.zone, _shooting_criteria)


def _build_vision_map(
    bf: Battlefield, active_zone: tuple[int, int],
) -> dict[tuple[int, int], str]:
    """Build vision overlay using the generic zone overlay builder."""
    return _build_zone_overlay(bf, active_zone, _vision_criteria)


_OVERLAY_LEGENDS = OVERLAY_LEGENDS


def build_overlay(
    bf: Battlefield, fig: Figure, mode: str = OVERLAY_VISION,
) -> dict[tuple[int, int], str]:
    """Build a zone overlay map for the given mode and figure."""
    if mode == OVERLAY_MOVEMENT:
        return _build_movement_map(bf, fig)
    elif mode == OVERLAY_SHOOTING:
        return _build_shooting_map(bf, fig)
    return _build_vision_map(bf, fig.zone)


def print_battlefield(
    bf: Battlefield,
    title: str = "Battlefield",
    active_fig: "Figure | None" = None,
    overlay_mode: str = OVERLAY_VISION,
    slyn_unknown: bool = False,
    highlighted_enemies: "set[str] | None" = None,
):
    """Render the battlefield grid using box-drawing chars and Rich Text.

    Fixed-width cells (7 chars) with ASCII grid lines (auto-upgrades to
    Unicode box-drawing on UTF-8 terminals). Two lines per cell:
    terrain+objective on top, figures below.
    slyn_unknown: If True, label Slyn as "Unknown Alien" in legend (first encounter).

    Args:
        active_fig: If set, highlights this figure's zone with an overlay.
        highlighted_enemies: Set of enemy figure names to highlight (in-range targets).
        overlay_mode: One of OVERLAY_VISION, OVERLAY_MOVEMENT, OVERLAY_SHOOTING.
    """
    CELL_W = 7   # inner character width per cell
    LABEL_W = 3  # row label width (space + digit + space)

    B = _BOX_UNICODE if _detect_unicode_support() else _BOX_ASCII

    # Build overlay if we have an active figure
    vision: dict[tuple[int, int], str] = {}
    if active_fig and active_fig.is_alive:
        vision = build_overlay(bf, active_fig, overlay_mode)

    # -- Title --
    console.print(
        f"\n  [bold]{title}[/] ({bf.rows}x{bf.cols}, 4\" zones)"
    )

    # -- Column header --
    header = Text()
    header.append(" " * LABEL_W + " ")  # align with left border
    for c in range(bf.cols):
        col_str = str(c).center(CELL_W)
        header.append(col_str, style="bold cyan")
        if c < bf.cols - 1:
            header.append(" ")  # separator gap
    console.print(header)

    # -- Border helpers --
    def h_border(left: str, mid: str, right: str) -> str:
        return (" " * LABEL_W) + left + mid.join(
            [B["h"] * CELL_W] * bf.cols
        ) + right

    top_border = h_border(B["tl"], B["mt"], B["tr"])
    mid_border = h_border(B["ml"], B["cx"], B["mr"])
    bot_border = h_border(B["bl"], B["mb"], B["br"])

    console.print(top_border, style="dim")

    for r in range(bf.rows):
        # Two content lines per row
        line1 = Text()  # terrain + objective
        line2 = Text()  # figures

        # Row label on line 1; blank on line 2
        row_label = str(r).rjust(LABEL_W - 1) + " "
        line1.append(row_label, style="bold")
        line2.append(" " * LABEL_W)

        for c in range(bf.cols):
            zone = bf.zones[r][c]
            figures = bf.get_figures_in_zone(r, c)

            # Vision overlay takes priority over terrain background
            if (r, c) in vision:
                bg = vision[(r, c)]
            else:
                bg = _TERRAIN_BG.get(zone.terrain, "")

            # Left border
            line1.append(B["v"], style="dim")
            line2.append(B["v"], style="dim")

            # -- Line 1: terrain symbol + objective --
            cell1 = Text()
            t_sym = _TERRAIN_SYMBOL[zone.terrain]
            t_style = _TERRAIN_STYLE[zone.terrain]
            if bg:
                t_style = f"{t_style} {bg}"

            if zone.objective_label:
                # Compact: no leading space to fit "tt *OBJ" in 7 chars
                cell1.append(t_sym, style=t_style)
                cell1.append(" ", style=bg)
                obj_label = f"*{zone.objective_label[:3]}"
                cell1.append(obj_label, style=OBJECTIVE_STYLE)
            else:
                cell1.append(f" {t_sym}", style=t_style)
            _pad_cell(cell1, CELL_W, bg)
            line1.append(cell1)

            # -- Line 2: figures (up to stacking limit) --
            cell2 = Text()
            alive_figs = [f for f in figures if f.is_alive]
            dead_figs = [f for f in figures if not f.is_alive]
            display_figs = alive_figs[:3]  # show alive first
            if len(display_figs) < 3 and dead_figs:
                display_figs.extend(dead_figs[:3 - len(display_figs)])

            if len(display_figs) <= 1:
                cell2.append(" ", style=bg)  # leading pad when room

            for i, fig in enumerate(display_figs):
                if i > 0:
                    cell2.append(" ", style=bg)
                label, style = _fig_label_parts(fig)
                # Active figure gets highlighted label
                if active_fig and fig.name == active_fig.name:
                    style = ACTIVE_FIG_STYLE_TEMPLATE.format(bg=bg)
                # Highlight in-range enemies
                elif highlighted_enemies and fig.name in highlighted_enemies:
                    style = HIGHLIGHTED_ENEMY_STYLE
                cell2.append(label, style=style)
            if len(figures) > 3:
                cell2.append(f"+{len(figures) - 3}", style="dim")
            _pad_cell(cell2, CELL_W, bg)
            line2.append(cell2)

        # Right border
        line1.append(B["v"], style="dim")
        line2.append(B["v"], style="dim")

        console.print(line1)
        console.print(line2)

        # Row separator or bottom border
        if r < bf.rows - 1:
            console.print(mid_border, style="dim")

    console.print(bot_border, style="dim")

    # -- Legend --
    legend_terrain = (
        "  [dim]Terrain:[/] "
        "[dim]..[/]=Open  "
        "[yellow]~~[/]=Scatter  "
        "[yellow on grey15]##[/]=Heavy Cover  "
        "[cyan]^^[/]=High Ground  "
        "[red]XX[/]=Impassable"
    )
    # Build dynamic figure legend based on what's on the battlefield
    _special_classes = ("slyn", "sleeper", "storm")
    has_player = any(f.side == FigureSide.PLAYER and f.is_alive for f in bf.figures)
    has_enemy = any(
        f.side == FigureSide.ENEMY and f.is_alive
        and not f.is_contact
        and getattr(f, "char_class", "") not in _special_classes
        for f in bf.figures
    )
    has_contact = any(f.is_contact and f.is_alive for f in bf.figures)
    has_storm = any(
        getattr(f, "char_class", "") == "storm" and f.is_alive for f in bf.figures
    )
    has_slyn = any(
        getattr(f, "char_class", "") == "slyn" and f.is_alive for f in bf.figures
    )
    has_sleeper = any(
        getattr(f, "char_class", "") == "sleeper" and f.is_alive for f in bf.figures
    )
    has_objective = any(
        bf.zones[r][c].has_objective
        for r in range(bf.rows)
        for c in range(bf.cols)
    )

    fig_parts: list[str] = ["  [dim]Figures:[/] "]
    if has_player:
        fig_parts.append("[bright_green]1AB[/]=Player  ")
    if has_enemy or has_contact:
        fig_parts.append("[red]1AB[/]=Enemy  ")
    if has_storm:
        fig_parts.append("[yellow]1AB[/]=Storm  ")
    if has_slyn:
        if slyn_unknown:
            fig_parts.append("[cyan]1AB[/]=Unknown  ")
        else:
            fig_parts.append("[cyan]1AB[/]=Slyn  ")
    if has_sleeper:
        fig_parts.append("[magenta]1AB[/]=Sleeper  ")
    if has_contact:
        fig_parts.append("[red]??[/]=Contact  ")
    fig_parts.append("[dim]~Stun _Sprawl +Aid[/]  ")
    if has_objective:
        fig_parts.append("[bold bright_white on dark_red]*OBJ[/]=Objective")
    legend_figs = "".join(fig_parts)
    console.print(legend_terrain)
    console.print(legend_figs)
    if active_fig and overlay_mode in _OVERLAY_LEGENDS:
        console.print(_OVERLAY_LEGENDS[overlay_mode])


def _fig_label_parts(fig: Figure) -> tuple[str, str]:
    """Return (label_text, rich_style) for a figure — no markup wrapper.

    All figures use XYY format: X=sequential number, YY=abbreviation.
    Enemies: YY = weapon abbreviation. Players: YY = name initials.
    Label text and status suffixes are produced by Figure.display_label().
    """
    code = _allocate_code(fig)
    label = fig.display_label(code)

    if fig.is_contact:
        return (label, CONTACT_STYLE)
    if fig.side == FigureSide.PLAYER:
        return (label, PLAYER_STYLE)
    if fig.char_class == "storm":
        return (label, STORM_STYLE)
    if fig.char_class == "slyn":
        return (label, SLYN_STYLE)
    if fig.char_class == "sleeper":
        return (label, SLEEPER_STYLE)
    return (label, ENEMY_STYLE)


_TERRAIN_BG = TERRAIN_BG


def _pad_cell(cell: Text, width: int, bg_style: str = "") -> Text:
    """Pad a Rich Text cell to exact display width, filling with bg style."""
    gap = width - cell.cell_len
    if gap > 0:
        cell.append(" " * gap, style=bg_style)
    return cell


def _detect_unicode_support() -> bool:
    """Check if the terminal can handle Unicode box-drawing characters."""
    import sys
    try:
        encoding = sys.stdout.encoding or ""
        return encoding.lower().replace("-", "") in (
            "utf8", "utf16", "utf32", "utf8sig",
        )
    except Exception:
        return False


_BOX_UNICODE = BOX_UNICODE
_BOX_ASCII = BOX_ASCII


def print_reaction_roll(reaction: dict):
    """Print the reaction roll results: dice, assignments, quick/slow split."""
    dice = reaction.get("dice", [])
    assignments = reaction.get("assignments", {})
    quick = reaction.get("quick", [])
    slow = reaction.get("slow", [])

    console.print(f"\n  [bold]Reaction Roll:[/bold] {dice}")

    parts = []
    for name, die in assignments.items():
        if name in quick:
            parts.append(f"[green]{name}={die}(Q)[/green]")
        else:
            parts.append(f"[yellow]{name}={die}(S)[/yellow]")
    if parts:
        console.print(f"  Assignments: {', '.join(parts)}")

    if quick:
        console.print(f"  [green]Quick:[/green] {', '.join(quick)}")
    if slow:
        console.print(f"  [yellow]Slow:[/yellow] {', '.join(slow)}")


def print_combat_phase(phase: str, round_number: int):
    """Print a combat phase header."""
    labels = {
        "quick_actions": "Quick Actions Phase",
        "enemy_phase": "Enemy Actions Phase",
        "slow_actions": "Slow Actions Phase",
        "end_phase": "End of Round",
    }
    label = labels.get(phase, format_display(phase))
    console.print()
    console.rule(f"[bold yellow]Round {round_number} — {label}[/bold yellow]")


def print_combat_log(log_lines: list[str]):
    """Print recent combat log entries."""
    for line in log_lines:
        if line.startswith("===") or line.startswith("---"):
            continue  # skip internal separators
        console.print(f"    [dim]{line}[/dim]")

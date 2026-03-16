"""Centralized color and style constants for the Planetfall CLI."""

from __future__ import annotations

from planetfall.engine.combat.battlefield import TerrainType


# --- Terrain display ---

TERRAIN_SYMBOL = {
    TerrainType.OPEN: "..",
    TerrainType.LIGHT_COVER: "~~",
    TerrainType.HEAVY_COVER: "##",
    TerrainType.HIGH_GROUND: "^^",
    TerrainType.IMPASSABLE: "XX",
}

TERRAIN_STYLE = {
    TerrainType.OPEN: "dim",
    TerrainType.LIGHT_COVER: "yellow",
    TerrainType.HEAVY_COVER: "yellow",
    TerrainType.HIGH_GROUND: "cyan",
    TerrainType.IMPASSABLE: "red",
}

# Background tints per terrain type (subtle, for zone fill)
TERRAIN_BG = {
    TerrainType.OPEN: "",
    TerrainType.LIGHT_COVER: "on grey11",
    TerrainType.HEAVY_COVER: "on grey15",
    TerrainType.HIGH_GROUND: "on grey7",
    TerrainType.IMPASSABLE: "on grey19",
}


# --- Overlay colors ---

# Active figure's zone (shared by all overlays)
OVERLAY_ACTIVE = "on dark_green"

# Movement overlay
MOVE_STANDARD = "on rgb(20,80,30)"    # bright green - standard move
MOVE_RUSH = "on rgb(12,50,20)"        # dark green - rush only

# Shooting overlay
SHOOT_CLOSE = "on rgb(120,30,20)"     # bright - close range (3+)
SHOOT_MEDIUM = "on rgb(80,20,15)"     # medium - standard range (5+)
SHOOT_COVER = "on rgb(50,15,10)"      # dark - in cover (6+)

# Vision overlay
VISION_CLOSE = "on rgb(30,60,120)"    # bright blue - close range
VISION_FAR = "on rgb(20,40,85)"       # medium blue - far range (clear)
VISION_EXTREME = "on rgb(12,25,55)"   # dark blue - extreme or obscured


# --- Figure styles ---

PLAYER_STYLE = "bold bright_green"
ENEMY_STYLE = "bold red"
CONTACT_STYLE = "bold red"
STORM_STYLE = "bold yellow"
SLYN_STYLE = "bold cyan"
SLEEPER_STYLE = "bold magenta"

# Highlighted figures
ACTIVE_FIG_STYLE_TEMPLATE = "bold bright_white {bg}"
HIGHLIGHTED_ENEMY_STYLE = "bold bright_white on dark_red"
OBJECTIVE_STYLE = "bold bright_white on dark_red"


# --- Overlay mode constants ---

OVERLAY_VISION = "vision"
OVERLAY_MOVEMENT = "movement"
OVERLAY_SHOOTING = "shooting"
OVERLAY_MODES = [OVERLAY_VISION, OVERLAY_MOVEMENT, OVERLAY_SHOOTING]


# --- Overlay legends ---

OVERLAY_LEGENDS = {
    OVERLAY_VISION: (
        "  [dim]Vision:[/] "
        f"[{OVERLAY_ACTIVE}]  [/]=Active  "
        f"[{VISION_CLOSE}]  [/]=Close 1-2z  "
        f"[{VISION_FAR}]  [/]=Far 3-4z  "
        f"[{VISION_EXTREME}]  [/]=Extreme/Obscured  "
        "[dim]dark=Blocked[/]"
    ),
    OVERLAY_MOVEMENT: (
        "  [dim]Movement:[/] "
        f"[{OVERLAY_ACTIVE}]  [/]=Active  "
        f"[{MOVE_STANDARD}]  [/]=Move (1 zone)  "
        f"[{MOVE_RUSH}]  [/]=Dash/Jump  "
        "[dim]dark=Blocked[/]"
    ),
    OVERLAY_SHOOTING: (
        "  [dim]Shooting:[/] "
        f"[{OVERLAY_ACTIVE}]  [/]=Active  "
        f"[{SHOOT_CLOSE}]  [/]=Close 3+  "
        f"[{SHOOT_MEDIUM}]  [/]=Range 5+  "
        f"[{SHOOT_COVER}]  [/]=Cover 6+  "
        "[dim]dark=Out of range[/]"
    ),
}


# --- Box-drawing character sets ---

BOX_UNICODE = {
    "h": "\u2500", "v": "\u2502",
    "tl": "\u250c", "tr": "\u2510", "bl": "\u2514", "br": "\u2518",
    "ml": "\u251c", "mr": "\u2524", "mt": "\u252c", "mb": "\u2534",
    "cx": "\u253c",
}

BOX_ASCII = {
    "h": "-", "v": "|",
    "tl": "+", "tr": "+", "bl": "+", "br": "+",
    "ml": "+", "mr": "+", "mt": "+", "mb": "+",
    "cx": "+",
}

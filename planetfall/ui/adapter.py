"""UI adapter protocol — abstracts display and input for CLI/web backends.

All orchestrator and game-loop code should interact with the UI
through this protocol instead of importing cli.display or cli.prompts
directly.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable, Any


@runtime_checkable
class UIAdapter(Protocol):
    """Abstract UI backend that both CLI and web adapters implement."""

    HAS_OVERLAY_BUTTONS: bool = False

    # ------------------------------------------------------------------
    # Input — blocking, returns user choice
    # ------------------------------------------------------------------

    def select(self, message: str, choices: list[str]) -> str:
        """Single selection from a list of options."""
        ...

    def select_action(
        self, message: str, choices: list[str],
        shoot_targets: list[dict] | None = None,
        active_figure: dict | None = None,
    ) -> str:
        """Action selection with optional shoot targets shown in info panel.

        shoot_targets: list of {name, map_label, eff_label, range_label, shots, desc}.
        Returns either a choice string or a shoot target desc string.
        Falls back to select() if not overridden.
        """
        if shoot_targets:
            choices = ["Shoot"] + choices
        return self.select(message, choices)


    def confirm(self, message: str, default: bool = True) -> bool:
        """Yes/no confirmation prompt."""
        ...

    def number(self, message: str, min_val: int = 0, max_val: int = 100) -> int:
        """Numeric input within a range."""
        ...

    def checkbox(self, message: str, choices: list[str]) -> list[str]:
        """Multi-select from a list."""
        ...

    def text(self, message: str, default: str = "") -> str:
        """Free text input."""
        ...

    def show_loading_modal(self, title: str = "Colony Log") -> None:
        """Show a loading modal with spinner (non-blocking)."""
        ...

    def show_narrative_modal(self, text: str, title: str = "Colony Log") -> None:
        """Show narrative in a blocking modal — waits for user to close."""
        ...

    def pause(self, message: str = "Press any key to continue...") -> None:
        """Wait for user acknowledgment before continuing."""
        ...

    # ------------------------------------------------------------------
    # Output — display only
    # ------------------------------------------------------------------

    def message(self, text: str, style: str = "") -> None:
        """Display a message. Style is a semantic hint (dim, error, success, etc.)."""
        ...

    def rule(self, text: str, style: str = "bold yellow") -> None:
        """Display a horizontal rule/divider with optional label."""
        ...

    def clear(self) -> None:
        """Clear the screen / reset the view."""
        ...

    def show_events(self, events: list) -> None:
        """Render a list of TurnEvent objects."""
        ...

    def show_colony_status(self, state: Any) -> None:
        """Render colony status dashboard."""
        ...

    def show_map(self, state: Any) -> None:
        """Render the campaign map."""
        ...

    def show_roster(self, state: Any) -> None:
        """Render the character roster table."""
        ...

    def show_step_header(self, step: int, name: str, state: Any = None) -> None:
        """Display step header (includes pause, clear, colony status)."""
        ...

    def show_mission_options(self, options: list[dict]) -> None:
        """Render the mission selection table."""
        ...

    def show_character_backgrounds(self, state: Any) -> None:
        """Render character background summaries."""
        ...

    def show_turn_summary(self, events: list) -> None:
        """Render end-of-turn summary panel."""
        ...

    def show_mission_summary(self, missions: list[dict]) -> None:
        """Show initial mission summary with results and bonuses.

        Each mission dict: {name, success, detail}
        """
        ...

    def show_mission_result(self, success: bool, title: str, detail: str) -> None:
        """Show mission success/failure result screen and wait for continue."""
        ...

    def prompt_experience(self, data: dict) -> dict:
        """Show experience screen with advancement options.

        Returns action dict: done, roll, buy, or alternate.
        """
        ...

    def prompt_research(self, data: dict) -> dict:
        """Show research modal with spending options.

        Returns action dict: done, invest, unlock_app, or bio_analysis.
        """
        ...

    def prompt_building(self, data: dict) -> dict:
        """Show building modal with construction options.

        Returns action dict: done, build, or convert.
        """
        ...

    def show_mission_intro(self, data: dict) -> None:
        """Show a mission intro modal and wait for dismissal.

        data keys: title, subtitle, sections (list of {heading, body}).
        """
        ...

    # ------------------------------------------------------------------
    # Combat display
    # ------------------------------------------------------------------

    def show_mission_briefing(
        self,
        bf: Any,
        mission_type: str,
        enemy_info: list[str],
        special_rules: list[str],
        victory_conditions: list[str],
        defeat_conditions: list[str],
        enemy_type: str = "",
        slyn_unknown: bool = False,
    ) -> None:
        """Render mission briefing panel (map + mission info)."""
        ...

    def show_battlefield(self, bf: Any, **kwargs: Any) -> None:
        """Render the battlefield grid."""
        ...

    def show_combat_phase(self, phase: str, round_number: int) -> None:
        """Display the combat phase header."""
        ...

    def show_combat_log(self, lines: list[str]) -> None:
        """Display combat action log entries."""
        ...

    def show_reaction_roll(self, reaction: dict) -> None:
        """Display reaction roll results."""
        ...

    def reset_enemy_labels(self) -> None:
        """Reset enemy label mapping (for fresh battlefield display)."""
        ...

    # ------------------------------------------------------------------
    # Combat overlays (used by _prompt_with_overlay pattern)
    # ------------------------------------------------------------------

    @property
    def OVERLAY_VISION(self) -> str:
        """Overlay type constant for vision cones."""
        ...

    @property
    def OVERLAY_MOVEMENT(self) -> str:
        """Overlay type constant for movement range."""
        ...

    @property
    def OVERLAY_SHOOTING(self) -> str:
        """Overlay type constant for shooting arcs."""
        ...

    # ------------------------------------------------------------------
    # Compound prompts (complex multi-step interactions)
    # ------------------------------------------------------------------

    def prompt_mission_choice(self, options: list[dict]) -> int:
        """Prompt player to choose a mission from options. Returns index."""
        ...

    def prompt_deployment(
        self, available_names: list[str], max_slots: int,
        grunt_count: int = 0, bot_available: bool = False,
        char_classes: dict[str, str] | None = None,
    ) -> dict:
        """Prompt for squad deployment (characters, grunts, bot, civilians)."""
        ...

    def prompt_loadout(
        self, state: Any, deployed_chars: list[str],
    ) -> dict[str, str]:
        """Prompt weapon selection for each deployed character."""
        ...

    def prompt_deployment_zones(
        self, bf: Any, figures: list, deployment_zones: list,
    ) -> None:
        """Interactive deployment zone assignment for figures on battlefield."""
        ...

    def prompt_reaction_assignment(
        self, dice: list[int], figures: list[tuple[str, int]],
    ) -> dict[str, int]:
        """Prompt player to assign reaction dice to figures."""
        ...

    def prompt_movement(
        self, bf: Any, fig: Any,
        move_zones: list, dash_zones: list,
        can_scout_first: bool = False,
        can_trooper_delay: bool = False,
        overlay_mode: str = "movement",
        slyn_unknown: bool = False,
        highlighted_enemies: list | None = None,
        active_figure: dict | None = None,
    ) -> dict:
        """Combined movement prompt: type + destination in one step.

        Returns dict with keys:
            - 'type': 'stay' | 'move' | 'dash' | 'scout_first'
            - 'zone_idx': index into move_zones or dash_zones (if applicable)
        """
        ...

    def prompt_zone_select(
        self, bf: Any, fig: Any, message: str,
        valid_zones: list[tuple[tuple[int, int], str, list[str], bool]],
        overlay_mode: str = "movement",
        slyn_unknown: bool = False,
        highlighted_enemies: list | None = None,
    ) -> int:
        """Prompt player to select a zone on the battlefield. Returns index into valid_zones."""
        ...

    def prompt_sector_coords(
        self, message: str, valid_ids: list[int],
    ) -> int:
        """Prompt player to select a sector by ID."""
        ...

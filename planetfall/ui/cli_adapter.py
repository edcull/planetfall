"""CLI adapter — wraps existing cli.display and cli.prompts as a UIAdapter.

This is a thin delegation layer. All actual rendering and input logic
stays in cli/display.py and cli/prompts.py.
"""

from __future__ import annotations

from typing import Any

from planetfall.cli import display, prompts


# Semantic style → Rich markup mapping
_STYLE_MAP = {
    "dim": "dim",
    "error": "bold red",
    "success": "green",
    "warning": "yellow",
    "info": "cyan",
    "bold": "bold",
    "heading": "bold yellow",
    "narrative": "italic",
    "stat": "bold cyan",
    "section": "bold yellow",
}


class CLIAdapter:
    """UIAdapter implementation backed by Rich + Questionary."""

    # ------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------

    def select(self, message: str, choices: list[str]) -> str:
        return prompts.ask_select(message, choices)

    def confirm(self, message: str, default: bool = True) -> bool:
        return prompts.ask_confirm(message, default)

    def number(self, message: str, min_val: int = 0, max_val: int = 100) -> int:
        return prompts.ask_number(message, min_val, max_val)

    def checkbox(self, message: str, choices: list[str]) -> list[str]:
        return prompts.ask_checkbox(message, choices)

    def text(self, message: str, default: str = "") -> str:
        return prompts.ask_text(message, default)

    def pause(self, message: str = "Press any key to continue...") -> None:
        prompts.pause(message)

    def show_loading_modal(self, title: str = "Colony Log") -> None:
        pass  # CLI doesn't need loading state

    def show_narrative_modal(self, text: str, title: str = "Colony Log") -> None:
        display.console.print(f"\n[bold cyan]═══ {title} ═══[/bold cyan]")
        display.console.print(text)
        prompts.pause()

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def message(self, text: str, style: str = "") -> None:
        if style:
            markup = _STYLE_MAP.get(style, style)
            display.console.print(f"[{markup}]{text}[/{markup}]")
        else:
            display.console.print(text)

    def rule(self, text: str, style: str = "bold yellow") -> None:
        display.console.rule(f"[{style}]{text}[/{style}]")

    def clear(self) -> None:
        display.clear_screen()

    def show_events(self, events: list) -> None:
        display.print_events(events)

    def show_colony_status(self, state: Any) -> None:
        display.print_colony_status(state)

    def show_map(self, state: Any) -> None:
        display.print_map(state)

    def show_roster(self, state: Any) -> None:
        display.print_roster(state)

    def show_step_header(self, step: int, name: str, state: Any = None) -> None:
        display.print_step_header(step, name, state)

    def show_mission_options(self, options: list[dict]) -> None:
        display.print_mission_options(options)

    def show_character_backgrounds(self, state: Any) -> None:
        display.print_character_backgrounds(state)

    def show_turn_summary(self, events: list) -> None:
        display.print_turn_summary(events)

    def show_mission_result(self, success: bool, title: str, detail: str) -> None:
        style = "bold green" if success else "bold red"
        icon = "✓" if success else "✗"
        self._display.console.print(f"\n[{style}]{icon} {title}[/{style}]")
        if detail:
            self._display.console.print(f"  {detail}")

    def prompt_experience(self, data: dict) -> dict:
        """CLI experience screen — show XP awards, then offer advancement."""
        # Show XP awards
        for a in data.get("xp_awards", []):
            self._display.console.print(
                f"  {a['name']}: +{a['xp']} XP ({a['reasons']}). Total: {a['total_xp']} XP"
            )
        cp = data.get("civvy_promotion")
        if cp:
            result = "Promoted!" if cp["promoted"] else "Not promoted"
            self._display.console.print(f"  Civvy Heroic Promotion: {cp['roll']} — {result}")

        # Check for advancement-eligible characters
        for c in data.get("characters", []):
            if c["xp"] >= 5:
                from planetfall.cli.prompts import select
                choices = ["Roll D100 (5 XP)", "Skip"]
                choice = select(
                    f"{c['name']} has {c['xp']} XP. Advancement?", choices,
                )
                if choice.startswith("Roll"):
                    return {"action": "roll", "character": c["name"]}
        return {"action": "done"}

    def prompt_research(self, data: dict) -> dict:
        return {"action": "done"}

    def prompt_building(self, data: dict) -> dict:
        return {"action": "done"}

    def show_mission_summary(self, missions: list[dict]) -> None:
        """Show mission summary in CLI."""
        self._display.console.print("\n[bold cyan]═══ LANDING SITE ESTABLISHED ═══[/bold cyan]")
        for m in missions:
            style = "bold green" if m["success"] else "bold red"
            icon = "✓" if m["success"] else "✗"
            self._display.console.print(f"  [{style}]{icon} {m['name']}[/{style}]: {m['detail']}")

    def show_mission_intro(self, data: dict) -> None:
        """Show mission intro — CLI just prints title and pauses."""
        from planetfall.cli import prompts
        title = data.get("title", "Mission")
        self._display.console.print(f"\n[bold cyan]═══ {title} ═══[/bold cyan]")
        for section in data.get("sections", []):
            if section.get("heading"):
                self._display.console.print(f"\n[bold yellow]{section['heading']}[/bold yellow]")
            if section.get("body"):
                self._display.console.print(f"  {section['body']}")
        prompts.pause()

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
        """CLI fallback: print mission info as text then show battlefield."""
        self.rule(f"Mission: {mission_type}")
        if enemy_info:
            self.message("")
            for line in enemy_info:
                self.message(f"  {line}", style="error")
        if special_rules:
            self.message("")
            for rule in special_rules:
                self.message(f"  * {rule}", style="warning")
        display.print_battlefield(bf, slyn_unknown=slyn_unknown)

    def show_battlefield(self, bf: Any, **kwargs: Any) -> None:
        display.print_battlefield(bf, **kwargs)

    def show_combat_phase(self, phase: str, round_number: int) -> None:
        display.print_combat_phase(phase, round_number)

    def show_combat_log(self, lines: list[str]) -> None:
        display.print_combat_log(lines)

    def show_reaction_roll(self, reaction: dict) -> None:
        display.print_reaction_roll(reaction)

    def reset_enemy_labels(self) -> None:
        display.reset_enemy_labels()

    @property
    def OVERLAY_VISION(self) -> str:
        return display.OVERLAY_VISION

    @property
    def OVERLAY_MOVEMENT(self) -> str:
        return display.OVERLAY_MOVEMENT

    @property
    def OVERLAY_SHOOTING(self) -> str:
        return display.OVERLAY_SHOOTING

    # ------------------------------------------------------------------
    # Compound prompts
    # ------------------------------------------------------------------

    def prompt_mission_choice(self, options: list[dict]) -> int:
        return prompts.prompt_mission_choice(options)

    def prompt_deployment(
        self, available_names: list[str], max_slots: int,
        grunt_count: int = 0, bot_available: bool = False,
        char_classes: dict[str, str] | None = None,
    ) -> dict:
        return prompts.prompt_deployment(
            available_names, max_slots, grunt_count, bot_available,
        )

    def prompt_loadout(
        self, state: Any, deployed_chars: list[str],
    ) -> dict[str, str]:
        return prompts.prompt_loadout(state, deployed_chars)

    def prompt_deployment_zones(
        self, bf: Any, figures: list, deployment_zones: list,
    ) -> None:
        figure_names = [f.name for f in figures]
        assignments = prompts.prompt_deployment_zones(
            figure_names, deployment_zones,
        )
        for fig in figures:
            if fig.name in assignments:
                fig.zone = assignments[fig.name]
                bf.figures.append(fig)

    def prompt_reaction_assignment(
        self, dice: list[int], figures: list[tuple[str, int]],
    ) -> dict[str, int]:
        return prompts.prompt_reaction_assignment(dice, figures)

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
        # CLI fallback: two-step approach
        choices = ["Stay stationary"]
        if move_zones:
            choices.append("Move")
        if dash_zones:
            choices.append("Dash")
        if can_scout_first:
            choices.append("Take action first, then move")
        move_type = prompts.ask_select("Movement:", choices)
        if move_type == "Move":
            zone_descs = []
            for zone, terrain, figs, is_jump in move_zones:
                label = "Jump to" if is_jump else "Move to"
                desc = f"{label} ({zone[0]},{zone[1]}) ({terrain})"
                if figs:
                    desc += f" [{', '.join(figs)}]"
                zone_descs.append(desc)
            choice = prompts.ask_select("Move to:", zone_descs)
            return {"type": "move", "zone_idx": zone_descs.index(choice)}
        elif move_type == "Dash":
            zone_descs = []
            for zone, terrain, figs, is_jump in dash_zones:
                label = "Jump to" if is_jump else "Dash to"
                desc = f"{label} ({zone[0]},{zone[1]}) ({terrain})"
                if figs:
                    desc += f" [{', '.join(figs)}]"
                zone_descs.append(desc)
            choice = prompts.ask_select("Dash to:", zone_descs)
            return {"type": "dash", "zone_idx": zone_descs.index(choice)}
        elif move_type.startswith("Take action"):
            return {"type": "scout_first"}
        return {"type": "stay"}

    def prompt_zone_select(
        self, bf: Any, fig: Any, message: str,
        valid_zones: list[tuple[tuple[int, int], str, list[str], bool]],
        overlay_mode: str = "movement",
        slyn_unknown: bool = False,
        highlighted_enemies: list | None = None,
    ) -> int:
        # Build text choices and use select prompt
        zone_descs = []
        for zone, terrain, figs_in_zone, is_jump in valid_zones:
            label = "Jump to" if is_jump else message.replace(":", "").strip()
            desc = f"{label} ({zone[0]},{zone[1]}) ({terrain})"
            if figs_in_zone:
                desc += f" [{', '.join(figs_in_zone)}]"
            zone_descs.append(desc)
        choice = prompts.ask_select(message, zone_descs)
        return zone_descs.index(choice)

    def prompt_sector_coords(
        self, message: str, valid_ids: list[int],
    ) -> int:
        return prompts.ask_sector_coords(message, valid_ids)

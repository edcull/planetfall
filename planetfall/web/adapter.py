"""WebAdapter — UIAdapter implementation that bridges sync game loop to async WebSocket.

The game loop runs in a background thread and calls WebAdapter methods synchronously.
Output methods serialize data and push JSON over the WebSocket.
Input methods send an input_request, then block on a threading.Event until the
browser sends back an input_response which is routed to resolve().
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Callable
from uuid import uuid4

from planetfall.engine.utils import format_display


class _Disconnected(Exception):
    """Raised when the WebSocket disconnects while waiting for input."""


class WebAdapter:
    """UIAdapter for the web frontend, backed by WebSocket JSON messages."""

    OVERLAY_VISION = "vision"
    OVERLAY_MOVEMENT = "movement"
    OVERLAY_SHOOTING = "shooting"
    HAS_OVERLAY_BUTTONS = True

    def __init__(self, send_fn: Callable[[dict], None]) -> None:
        """Create a WebAdapter.

        Args:
            send_fn: Callable that sends a JSON-serializable dict to the client.
                     Must be safe to call from any thread (typically wraps
                     asyncio.run_coroutine_threadsafe).
        """
        self._send = send_fn
        self._pending: dict[str, dict] = {}
        self._disconnected = False
        self._mission_briefing_cache: dict | None = None  # cached for combat display
        self.game_state: Any = None  # set by game loop for roster edits etc.

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _wait_for_response(self, request_id: str) -> Any:
        """Block the game thread until the browser responds."""
        event = threading.Event()
        self._pending[request_id] = {"event": event, "value": None}
        event.wait()
        if self._disconnected:
            from planetfall.cli.prompts import SaveAndQuit
            raise SaveAndQuit()
        result = self._pending.pop(request_id, {})
        return result.get("value")

    def resolve(self, request_id: str, value: Any) -> None:
        """Called by the WebSocket handler when the browser sends a response."""
        entry = self._pending.get(request_id)
        if entry:
            entry["value"] = value
            entry["event"].set()

    def disconnect(self) -> None:
        """Signal all pending waits that the connection is gone."""
        self._disconnected = True
        for entry in self._pending.values():
            entry["event"].set()

    # ------------------------------------------------------------------
    # Input — blocking, returns user choice
    # ------------------------------------------------------------------

    def _request_input(self, input_type: str, **kwargs: Any) -> Any:
        """Send an input request and block until the browser responds.

        Common factory for the uuid -> send -> wait pattern used by all
        input methods.
        """
        rid = str(uuid4())
        self._send({"type": "input_request", "input_type": input_type, "id": rid, **kwargs})
        return self._wait_for_response(rid)

    def select(self, message: str, choices: list[str]) -> str:
        return self._request_input("select", message=message, choices=choices)

    def select_action(
        self, message: str, choices: list[str],
        shoot_targets: list[dict] | None = None,
        active_figure: dict | None = None,
    ) -> str:
        return self._request_input(
            "action_select", message=message, choices=choices,
            shoot_targets=shoot_targets or [], active_figure=active_figure,
        )

    def confirm(self, message: str, default: bool = True) -> bool:
        return self._request_input("confirm", message=message, default=default)

    def number(self, message: str, min_val: int = 0, max_val: int = 100) -> int:
        return self._request_input("number", message=message, min=min_val, max=max_val)

    def checkbox(self, message: str, choices: list[str]) -> list[str]:
        return self._request_input("checkbox", message=message, choices=choices)

    def text(self, message: str, default: str = "") -> str:
        return self._request_input("text", message=message, default=default)

    def pause(self, message: str = "Continue") -> None:
        self._request_input("pause", message=message)

    def prompt_experience(self, data: dict) -> dict:
        """Show experience screen and wait for advancement actions or continue.

        data keys: xp_awards, civvy_promotion, characters, advancement_table,
                   buy_table, alternate_options.
        Returns dict: {"action": "done"} or
                      {"action": "roll", "character": name} or
                      {"action": "buy", "character": name, "stat": stat} or
                      {"action": "alternate", "character": name, "choice": choice}
        """
        resp = self._request_input("experience", **data)
        return resp if isinstance(resp, dict) else {"action": "done"}

    def prompt_research(self, data: dict) -> dict:
        """Show research spending modal and wait for action."""
        resp = self._request_input("research_spend", **data)
        return resp if isinstance(resp, dict) else {"action": "done"}

    def prompt_building(self, data: dict) -> dict:
        """Show building modal and wait for action."""
        resp = self._request_input("building_spend", **data)
        return resp if isinstance(resp, dict) else {"action": "done"}

    def show_mission_result(
        self, success: bool, title: str, detail: str,
        summary: list[str] | None = None,
    ) -> None:
        """Show mission result as a bottom overlay and wait for continue."""
        kwargs: dict = {"success": success, "title": title, "detail": detail}
        if summary:
            kwargs["summary"] = summary
        self._request_input("mission_result", **kwargs)

    # ------------------------------------------------------------------
    # Output — display only
    # ------------------------------------------------------------------

    def message(self, text: str, style: str = "") -> None:
        self._send({"type": "message", "text": text, "style": style})

    def show_loading_modal(self, title: str = "Colony Log") -> None:
        """Show a modal with a loading spinner (non-blocking)."""
        self._send({
            "type": "show_loading_modal", "title": title,
        })

    def show_narrative_modal(self, text: str, title: str = "Colony Log") -> None:
        """Show narrative in a blocking modal — waits for user to close."""
        self._request_input("narrative_modal", text=text, title=title)

    def rule(self, text: str, style: str = "bold yellow") -> None:
        self._send({"type": "rule", "text": text, "style": style})

    def clear(self) -> None:
        self._send({"type": "clear"})

    def show_events(self, events: list) -> None:
        from planetfall.web.serializers import serialize_events
        self._send({"type": "show_events", "events": serialize_events(events)})

    def show_colony_status(self, state: Any) -> None:
        from planetfall.web.serializers import serialize_colony_status
        self._send({"type": "show_colony_status", "data": serialize_colony_status(state)})

    def show_map(self, state: Any) -> None:
        from planetfall.web.serializers import serialize_map
        self._send({"type": "show_map", "data": serialize_map(state)})

    def redraw(self, state: Any, events: list | None = None) -> None:
        self.clear()
        self.show_colony_status(state)
        self.show_map(state)
        if events:
            self.show_events(events)

    def show_roster(self, state: Any) -> None:
        from planetfall.web.serializers import serialize_roster
        self._send({"type": "show_roster", "data": serialize_roster(state)})

    def show_armory(self, state: Any) -> None:
        from planetfall.web.serializers import serialize_armory
        self._send({"type": "show_armory", "data": serialize_armory(state)})

    def show_ancient_signs(self, state: Any) -> None:
        from planetfall.web.serializers import serialize_ancient_signs
        self._send({"type": "show_ancient_signs", "data": serialize_ancient_signs(state)})

    def show_milestones(self, state: Any) -> None:
        from planetfall.web.serializers import serialize_milestones
        self._send({"type": "show_milestones", "data": serialize_milestones(state)})

    def show_conditions(self, state: Any) -> None:
        from planetfall.web.serializers import serialize_conditions
        self._send({"type": "show_conditions", "data": serialize_conditions(state)})

    def show_lifeforms(self, state: Any) -> None:
        from planetfall.web.serializers import serialize_lifeforms
        self._send({"type": "show_lifeforms", "data": serialize_lifeforms(state)})

    def show_augmentations(self, state: Any) -> None:
        from planetfall.web.serializers import serialize_augmentations
        self._send({"type": "show_augmentations", "data": serialize_augmentations(state)})

    def show_enemies(self, state: Any) -> None:
        from planetfall.web.serializers import serialize_enemies
        self._send({"type": "show_enemies", "data": serialize_enemies(state)})

    def show_artifacts(self, state: Any) -> None:
        from planetfall.web.serializers import serialize_artifacts
        self._send({"type": "show_artifacts", "data": serialize_artifacts(state)})

    def show_calamities(self, state: Any) -> None:
        from planetfall.web.serializers import serialize_calamities
        self._send({"type": "show_calamities", "data": serialize_calamities(state)})

    def show_morale(self, state: Any, change: dict | None = None) -> None:
        from planetfall.web.serializers import serialize_morale
        data = serialize_morale(state)
        if change:
            data["change"] = change
        self._send({"type": "show_morale", "data": data})

    def show_step_header(self, step: int, name: str, state: Any = None, **kwargs) -> None:
        payload: dict[str, Any] = {"type": "show_step_header", "step": step, "name": name}
        if state is not None:
            from planetfall.web.serializers import (
                serialize_colony_status, serialize_map,
                serialize_roster, serialize_enemies,
            )
            payload["colony"] = serialize_colony_status(state)
            payload["map"] = serialize_map(state)
            # Auto-open roster on step 1 (Recovery) so player sees sick bay status
            if step == 1:
                payload["roster"] = serialize_roster(state)
                if kwargs.get("recovery_messages"):
                    payload["recovery_messages"] = kwargs["recovery_messages"]
            # Auto-open enemies panel on step 4 (Enemy Activity)
            if step == 4:
                payload["enemies"] = serialize_enemies(state)
            # Auto-open roster on step 13 (Replacements) with replacement messages
            if step == 13:
                payload["roster"] = serialize_roster(state)
                if kwargs.get("replacement_messages"):
                    payload["replacement_messages"] = kwargs["replacement_messages"]
        self._send(payload)

    def show_mission_options(self, options: list[dict]) -> None:
        # Serialize MissionType enums to friendly names
        serialized = []
        for opt in options:
            entry = dict(opt)
            if hasattr(entry.get("type"), "value"):
                entry["name"] = format_display(entry["type"].value)
                entry["type"] = entry["type"].value
            serialized.append(entry)
        self._send({"type": "show_mission_options", "options": serialized})

    def show_character_backgrounds(self, state: Any) -> None:
        from planetfall.web.serializers import serialize_character_backgrounds
        self._send({
            "type": "show_character_backgrounds",
            "data": serialize_character_backgrounds(state),
        })

    def show_info_modal(self, modal_name: str) -> None:
        """Open a sidebar info modal (enemies, ancient_signs, etc.) and wait for close."""
        self._request_input("info_modal", modal=modal_name)

    def show_turn_summary(self, events: list) -> None:
        from planetfall.web.serializers import serialize_events
        self._send({"type": "show_turn_summary", "events": serialize_events(events)})

    def show_mission_intro(self, data: dict) -> None:
        rid = str(uuid4())
        self._send({"type": "mission_intro", "id": rid, "data": data})
        self._wait_for_response(rid)

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
        condition: object = None,
        slyn_briefing: object | None = None,
    ) -> None:
        from planetfall.web.serializers import serialize_battlefield
        data: dict = {
            "battlefield": serialize_battlefield(bf, slyn_unknown=slyn_unknown),
            "mission_type": mission_type,
            "enemy_info": enemy_info,
            "special_rules": special_rules,
            "victory_conditions": victory_conditions,
            "defeat_conditions": defeat_conditions,
            "enemy_type": enemy_type,
        }
        if condition and hasattr(condition, "name") and condition.name:
            cond_data = {
                "name": condition.name,
                "description": condition.description,
            }
            if hasattr(condition, "effects_summary") and condition.effects_summary:
                cond_data["effects_summary"] = condition.effects_summary
            if hasattr(condition, "no_effect"):
                cond_data["no_effect"] = condition.no_effect
            data["condition"] = cond_data
        if slyn_briefing:
            data["slyn_briefing"] = slyn_briefing.model_dump() if hasattr(slyn_briefing, 'model_dump') else slyn_briefing
        # Cache mission info (without battlefield) for persistent combat display
        self._mission_briefing_cache = {
            k: v for k, v in data.items() if k != "battlefield"
        }
        self._send({"type": "show_mission_briefing", "data": data})

    def show_battlefield(self, bf: Any, **kwargs: Any) -> None:
        from planetfall.web.serializers import serialize_battlefield
        self._last_bf = bf
        payload: dict = {
            "type": "show_battlefield",
            "data": serialize_battlefield(bf, **kwargs),
        }
        if self._mission_briefing_cache:
            payload["mission_info"] = self._mission_briefing_cache
        self._send(payload)

    def show_combat_phase(self, phase: str, round_number: int) -> None:
        self._send({
            "type": "show_combat_phase",
            "phase": phase, "round_number": round_number,
        })

    def show_combat_log(self, lines: list[str]) -> None:
        self._send({"type": "show_combat_log", "lines": lines})

    def show_mission_summary(self, missions: list[dict]) -> None:
        """Show initial mission summary with results and bonuses.

        Each mission dict: {name, success, detail}
        """
        self._send({"type": "show_mission_summary", "missions": missions})

    def show_reaction_roll(self, reaction: dict) -> None:
        self._send({"type": "show_reaction_roll", "data": reaction})

    def reset_enemy_labels(self) -> None:
        self._enemy_label_counter = 0
        self._enemy_label_map = {}

    # ------------------------------------------------------------------
    # Compound prompts
    # ------------------------------------------------------------------

    def prompt_figure_select(
        self, message: str, figure_names: list[str],
    ) -> str:
        """Show figure selection as cards. Returns the chosen figure name."""
        bf = getattr(self, '_last_bf', None)
        fig_profiles = []
        for name in figure_names:
            entry: dict = {"name": name}
            if bf:
                fig = bf.get_figure_by_name(name)
                if fig:
                    entry["char_class"] = (fig.char_class or "").title()
                    entry["speed"] = fig.speed
                    entry["combat_skill"] = fig.combat_skill
                    entry["toughness"] = fig.toughness
                    entry["weapon"] = fig.weapon_name or ""
            fig_profiles.append(entry)

        return self._request_input("figure_select", message=message, figures=fig_profiles)

    def prompt_mission_choice(self, options: list[dict]) -> int:
        serialized = []
        for i, opt in enumerate(options):
            t = opt.get("type", "?")
            name = format_display(t.value) if hasattr(t, "value") else format_display(str(t))
            serialized.append({
                "index": i,
                "name": name,
                "description": opt.get("description", ""),
                "rewards": opt.get("rewards", ""),
                "forced": opt.get("forced", False),
            })
        result = self._request_input("mission_select", missions=serialized)
        try:
            return int(result)
        except (ValueError, TypeError):
            return 0

    def prompt_deployment(
        self, available_names: list[str], max_slots: int,
        grunt_count: int = 0, bot_available: bool = False,
        char_classes: dict[str, str] | None = None,
        char_profiles: dict[str, dict] | None = None,
    ) -> dict:
        return self._request_input(
            "deployment", available=available_names, max_slots=max_slots,
            grunt_count=grunt_count, bot_available=bot_available,
            char_classes=char_classes or {}, char_profiles=char_profiles or {},
        )

    def prompt_loadout(
        self, state: Any, deployed_chars: list[str],
    ) -> dict[str, str]:
        from planetfall.engine.models import ALL_WEAPONS, can_use_weapon

        # Determine which weapon tiers are unlocked via buildings
        built_names = {b.name for b in state.colony.buildings}
        has_tier1 = "Advanced Manufacturing Plant" in built_names
        has_tier2 = "High-Tech Manufacturing Plant" in built_names

        def _is_unlocked(w: Any) -> bool:
            tier = w.tier.value if hasattr(w.tier, "value") else str(w.tier)
            if tier == "tier_1":
                return has_tier1
            if tier == "tier_2":
                return has_tier1 and has_tier2
            return True  # standard weapons always available

        loadout = {}
        for name in deployed_chars:
            char = next((c for c in state.characters if c.name == name), None)
            if not char:
                continue
            usable_weapons = [
                w for w in ALL_WEAPONS
                if can_use_weapon(char.char_class, w) and _is_unlocked(w)
            ]
            if not usable_weapons:
                usable_weapons = [w for w in ALL_WEAPONS if _is_unlocked(w)]

            # Build weapon profiles with stats for display
            weapon_profiles = []
            for w in usable_weapons:
                # Filter out class-restriction traits for display
                display_traits = [
                    t for t in w.traits
                    if t not in ("civilian", "scout", "trooper", "grunt", "scientist")
                ]
                weapon_profiles.append({
                    "name": w.name,
                    "range": w.range_inches,
                    "shots": w.shots,
                    "damage": w.damage_bonus,
                    "traits": display_traits,
                    "tier": w.tier.value if hasattr(w.tier, "value") else str(w.tier),
                })

            # Build character profile for display
            profile = {
                "name": char.name,
                "char_class": char.char_class.value.title() if hasattr(char.char_class, "value") else str(char.char_class),
                "speed": char.speed,
                "reactions": char.reactions,
                "combat_skill": char.combat_skill,
                "toughness": char.toughness,
                "savvy": char.savvy,
                "armor_save": getattr(char, "armor_save", None),
            }

            choice = self._request_input(
                "weapon_select", message=f"Weapon for {name}:",
                weapons=weapon_profiles, active_figure=profile,
            )
            loadout[name] = choice
        return loadout

    def prompt_lock_and_load(
        self, state: Any,
        available_names: list[str], max_slots: int,
        grunt_count: int = 0, bot_available: bool = False,
        char_profiles: dict[str, dict] | None = None,
        forced_grunts: int | None = None,
    ) -> dict:
        """Combined deployment + weapon loadout in a single modal.

        Returns {characters, grunts, bot, civilians, weapon_loadout}.
        """
        from planetfall.engine.models import (
            ALL_WEAPONS, can_use_weapon, get_weapon_class_trait,
            WEAPON_APP_IDS,
        )

        # Determine weapon tier unlocks (building + research)
        built_names = {b.name for b in state.colony.buildings}
        has_tier1 = "Advanced Manufacturing Plant" in built_names
        has_tier2 = "High-Tech Manufacturing Plant" in built_names
        unlocked_apps = set(state.tech_tree.unlocked_applications)

        def _is_unlocked(w: Any) -> bool:
            tier = w.tier.value if hasattr(w.tier, "value") else str(w.tier)
            if tier == "tier_1":
                if not has_tier1:
                    return False
                app_id = WEAPON_APP_IDS.get(w.name)
                return app_id in unlocked_apps if app_id else True
            if tier == "tier_2":
                if not (has_tier1 and has_tier2):
                    return False
                app_id = WEAPON_APP_IDS.get(w.name)
                return app_id in unlocked_apps if app_id else True
            return True

        # Build flat deduplicated weapon list with class tag
        seen_weapons: set[str] = set()
        weapons: list[dict] = []
        for w in ALL_WEAPONS:
            if not _is_unlocked(w) or w.name in seen_weapons:
                continue
            seen_weapons.add(w.name)
            weapon_class = get_weapon_class_trait(w)
            display_traits = [
                t for t in w.traits
                if t not in ("civilian", "scout", "trooper", "grunt", "scientist")
            ]
            weapons.append({
                "name": w.name,
                "range": w.range_inches,
                "shots": w.shots,
                "damage": w.damage_bonus,
                "traits": display_traits,
                "tier": w.tier.value if hasattr(w.tier, "value") else str(w.tier),
                "weapon_class": weapon_class,
            })

        # Build compatibility map: class -> list of usable weapon names
        all_classes = set()
        for name in available_names:
            char = next((c for c in state.characters if c.name == name), None)
            if char:
                cls = char.char_class.value if hasattr(char.char_class, "value") else str(char.char_class)
                all_classes.add(cls)
        all_classes.update(("grunt", "bot", "civvy"))

        compatibility: dict[str, list[str]] = {}
        for cls in all_classes:
            compatibility[cls] = [
                w.name for w in ALL_WEAPONS
                if can_use_weapon(cls, w) and _is_unlocked(w)
            ]

        # Grunt upgrades for display on cards
        active_grunt_upgrades = list(state.grunts.upgrades) if state.grunts else []

        kwargs: dict = {
            "available": available_names, "max_slots": max_slots,
            "grunt_count": grunt_count, "bot_available": bot_available,
            "char_profiles": char_profiles or {}, "weapons": weapons,
            "compatibility": compatibility, "grunt_upgrades": active_grunt_upgrades,
        }
        if forced_grunts is not None:
            kwargs["forced_grunts"] = forced_grunts
        return self._request_input("lock_and_load", **kwargs)

    def prompt_deployment_zones(
        self, bf: Any, figures: list, deployment_zones: list,
        same_zone: bool = False,
    ) -> None:
        from planetfall.web.serializers import serialize_battlefield
        from planetfall.cli.display import get_figure_map_label

        # Send battlefield state
        self._send({
            "type": "show_battlefield",
            "data": serialize_battlefield(bf),
        })

        # Build figure profiles
        fig_profiles = []
        for fig in figures:
            label = get_figure_map_label(fig)
            fig_profiles.append({
                "name": fig.name,
                "label": label,
                "char_class": fig.char_class.title() if fig.char_class else "",
                "speed": fig.speed,
                "reactions": fig.reactions,
                "combat_skill": fig.combat_skill,
                "toughness": fig.toughness,
                "savvy": fig.savvy,
                "armor_save": fig.armor_save,
                "weapon_name": fig.weapon_name or "Unarmed",
                "weapon_range": fig.weapon_range,
                "weapon_shots": fig.weapon_shots,
                "weapon_damage": fig.weapon_damage,
                "weapon_traits": list(fig.weapon_traits) if fig.weapon_traits else [],
            })

        # Build valid deployment zones (max 2 per zone)
        valid_zones = []
        for r, c in deployment_zones:
            occupied = len([f for f in bf.figures if f.is_alive and f.zone == (r, c)])
            if occupied < 2:
                valid_zones.append({"row": r, "col": c, "capacity": 2 - occupied})

        kwargs: dict = {
            "figures": fig_profiles, "valid_zones": valid_zones, "max_per_zone": 2,
        }
        if same_zone:
            kwargs["same_zone"] = True
        resp = self._request_input("deploy_zones_batch", **kwargs)

        # resp is {name: {row, col}, ...}
        placements = resp.get("placements", resp)
        for fig in figures:
            pos = placements.get(fig.name)
            if pos:
                fig.zone = (pos["row"], pos["col"])
                bf.figures.append(fig)

    def prompt_reaction_assignment(
        self, dice: list[int], figures: list[tuple[str, int]],
    ) -> dict[str, int]:
        # Enrich figure data with profile info from battlefield
        fig_data = []
        bf = getattr(self, '_last_bf', None)
        for name, reactions in figures:
            entry: dict = {"name": name, "speed": reactions}
            if bf:
                fig = bf.get_figure_by_name(name)
                if fig:
                    # Individual figure
                    entry["char_class"] = (fig.char_class or "").title()
                    entry["combat_skill"] = fig.combat_skill
                    entry["toughness"] = fig.toughness
                    entry["weapon"] = fig.weapon_name or ""
                else:
                    # Fireteam entry — look up first member for display
                    members = bf.get_fireteam_members(name)
                    if members:
                        entry["char_class"] = name  # "Fireteam Alpha"
                        entry["member_count"] = len(members)
            fig_data.append(entry)
        resp = self._request_input("reaction_assign", data={"dice": dice, "figures": fig_data})
        # resp is {name: die_value, ...}
        assignments: dict[str, int] = {}
        for name, val in resp.items():
            assignments[name] = int(val)
        return assignments

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
        from planetfall.web.serializers import serialize_battlefield
        self._send({
            "type": "show_battlefield",
            "data": serialize_battlefield(
                bf, active_fig=fig.name, overlay_mode=overlay_mode,
                slyn_unknown=slyn_unknown,
                highlighted_enemies=highlighted_enemies or [],
            ),
        })
        # Build zone data with move/dash type tags
        zones_data = []
        move_coords = set()
        for i, (zone, terrain, figs_in_zone, is_jump) in enumerate(move_zones):
            move_coords.add(zone)
            zones_data.append({
                "row": zone[0], "col": zone[1],
                "index": i, "move_type": "move",
                "terrain": terrain, "figs": figs_in_zone,
                "is_jump": is_jump,
            })
        for i, (zone, terrain, figs_in_zone, is_jump) in enumerate(dash_zones):
            if zone not in move_coords:  # dash-only zones
                zones_data.append({
                    "row": zone[0], "col": zone[1],
                    "index": i, "move_type": "dash",
                    "terrain": terrain, "figs": figs_in_zone,
                    "is_jump": is_jump,
                })
        return self._request_input(
            "movement", figure_name=fig.name, zones=zones_data,
            can_scout_first=can_scout_first, can_trooper_delay=can_trooper_delay,
            active_figure=active_figure,
        )

    def prompt_zone_select(
        self, bf: Any, fig: Any, message: str,
        valid_zones: list[tuple[tuple[int, int], str, list[str], bool]],
        overlay_mode: str = "movement",
        slyn_unknown: bool = False,
        highlighted_enemies: list | None = None,
    ) -> int:
        from planetfall.web.serializers import serialize_battlefield
        # Show battlefield with overlay for the active figure
        self._send({
            "type": "show_battlefield",
            "data": serialize_battlefield(
                bf, active_fig=fig.name, overlay_mode=overlay_mode,
                slyn_unknown=slyn_unknown,
                highlighted_enemies=highlighted_enemies or [],
            ),
        })
        # Build valid zone data for the client
        zones_data = []
        for i, (zone, terrain, figs_in_zone, is_jump) in enumerate(valid_zones):
            label_prefix = "Jump to" if is_jump else message.replace(":", "").strip()
            desc = f"{label_prefix} ({zone[0]},{zone[1]}) ({terrain})"
            if figs_in_zone:
                desc += f" [{', '.join(figs_in_zone)}]"
            zones_data.append({
                "row": zone[0], "col": zone[1],
                "index": i, "label": desc,
                "terrain": terrain, "figs": figs_in_zone,
            })
        return int(self._request_input("zone_select", message=message, valid_zones=zones_data))

    def prompt_resource_cache(self, budget: int, sp_remaining: int) -> dict:
        """Show resource cache allocation modal. Returns {bp, rp, rm}."""
        resp = self._request_input("resource_cache", budget=budget, sp_remaining=sp_remaining)
        return resp if isinstance(resp, dict) else {"bp": 0, "rp": 0, "rm": 0}

    def confirm_reroll_offer(
        self, table_name: str, result: dict, sp_available: int,
    ) -> bool:
        """Show rolled result as card with reroll offer."""
        return self._request_input(
            "reroll_offer", table_name=table_name, result=result, sp_available=sp_available,
        )

    def prompt_reroll_choice(
        self, table_name: str, option_a: dict, option_b: dict,
    ) -> str:
        """Show two results as cards, player picks one. Returns 'a' or 'b'."""
        resp = self._request_input(
            "reroll_choice", table_name=table_name, option_a=option_a, option_b=option_b,
        )
        return resp if resp in ("a", "b") else "a"

    def prompt_sector_coords(
        self, message: str, valid_ids: list[int],
    ) -> int:
        return int(self._request_input("sector_select", message=message, valid_ids=valid_ids))

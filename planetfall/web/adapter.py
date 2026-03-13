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

    def select(self, message: str, choices: list[str]) -> str:
        rid = str(uuid4())
        self._send({
            "type": "input_request", "input_type": "select",
            "id": rid, "message": message, "choices": choices,
        })
        return self._wait_for_response(rid)

    def select_action(
        self, message: str, choices: list[str],
        shoot_targets: list[dict] | None = None,
        active_figure: dict | None = None,
    ) -> str:
        rid = str(uuid4())
        self._send({
            "type": "input_request", "input_type": "action_select",
            "id": rid, "message": message, "choices": choices,
            "shoot_targets": shoot_targets or [],
            "active_figure": active_figure,
        })
        return self._wait_for_response(rid)

    def confirm(self, message: str, default: bool = True) -> bool:
        rid = str(uuid4())
        self._send({
            "type": "input_request", "input_type": "confirm",
            "id": rid, "message": message, "default": default,
        })
        return self._wait_for_response(rid)

    def number(self, message: str, min_val: int = 0, max_val: int = 100) -> int:
        rid = str(uuid4())
        self._send({
            "type": "input_request", "input_type": "number",
            "id": rid, "message": message, "min": min_val, "max": max_val,
        })
        return self._wait_for_response(rid)

    def checkbox(self, message: str, choices: list[str]) -> list[str]:
        rid = str(uuid4())
        self._send({
            "type": "input_request", "input_type": "checkbox",
            "id": rid, "message": message, "choices": choices,
        })
        return self._wait_for_response(rid)

    def text(self, message: str, default: str = "") -> str:
        rid = str(uuid4())
        self._send({
            "type": "input_request", "input_type": "text",
            "id": rid, "message": message, "default": default,
        })
        return self._wait_for_response(rid)

    def pause(self, message: str = "Continue") -> None:
        rid = str(uuid4())
        self._send({
            "type": "input_request", "input_type": "pause",
            "id": rid, "message": message,
        })
        self._wait_for_response(rid)

    def prompt_experience(self, data: dict) -> dict:
        """Show experience screen and wait for advancement actions or continue.

        data keys: xp_awards, civvy_promotion, characters, advancement_table,
                   buy_table, alternate_options.
        Returns dict: {"action": "done"} or
                      {"action": "roll", "character": name} or
                      {"action": "buy", "character": name, "stat": stat} or
                      {"action": "alternate", "character": name, "choice": choice}
        """
        rid = str(uuid4())
        self._send({
            "type": "input_request", "input_type": "experience",
            "id": rid, **data,
        })
        resp = self._wait_for_response(rid)
        if isinstance(resp, dict):
            return resp
        return {"action": "done"}

    def prompt_research(self, data: dict) -> dict:
        """Show research spending modal and wait for action."""
        rid = str(uuid4())
        self._send({
            "type": "input_request", "input_type": "research_spend",
            "id": rid, **data,
        })
        resp = self._wait_for_response(rid)
        if isinstance(resp, dict):
            return resp
        return {"action": "done"}

    def prompt_building(self, data: dict) -> dict:
        """Show building modal and wait for action."""
        rid = str(uuid4())
        self._send({
            "type": "input_request", "input_type": "building_spend",
            "id": rid, **data,
        })
        resp = self._wait_for_response(rid)
        if isinstance(resp, dict):
            return resp
        return {"action": "done"}

    def show_mission_result(
        self, success: bool, title: str, detail: str,
    ) -> None:
        """Show mission result as a bottom overlay and wait for continue."""
        rid = str(uuid4())
        self._send({
            "type": "input_request", "input_type": "mission_result",
            "id": rid, "success": success, "title": title, "detail": detail,
        })
        self._wait_for_response(rid)

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
        rid = str(uuid4())
        self._send({
            "type": "input_request", "input_type": "narrative_modal",
            "id": rid, "text": text, "title": title,
        })
        self._wait_for_response(rid)

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

    def show_morale(self, state: Any) -> None:
        from planetfall.web.serializers import serialize_morale
        self._send({"type": "show_morale", "data": serialize_morale(state)})

    def show_step_header(self, step: int, name: str, state: Any = None) -> None:
        payload: dict[str, Any] = {"type": "show_step_header", "step": step, "name": name}
        if state is not None:
            from planetfall.web.serializers import serialize_colony_status, serialize_map
            payload["colony"] = serialize_colony_status(state)
            payload["map"] = serialize_map(state)
        self._send(payload)

    def show_mission_options(self, options: list[dict]) -> None:
        # Serialize MissionType enums to friendly names
        serialized = []
        for opt in options:
            entry = dict(opt)
            if hasattr(entry.get("type"), "value"):
                entry["name"] = entry["type"].value.replace("_", " ").title()
                entry["type"] = entry["type"].value
            serialized.append(entry)
        self._send({"type": "show_mission_options", "options": serialized})

    def show_character_backgrounds(self, state: Any) -> None:
        from planetfall.web.serializers import serialize_character_backgrounds
        self._send({
            "type": "show_character_backgrounds",
            "data": serialize_character_backgrounds(state),
        })

    def show_turn_summary(self, events: list) -> None:
        from planetfall.web.serializers import serialize_events
        self._send({"type": "show_turn_summary", "events": serialize_events(events)})

    def show_mission_intro(self, data: dict) -> None:
        rid = str(uuid4())
        self._send({
            "type": "mission_intro",
            "id": rid,
            "data": data,
        })
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
    ) -> None:
        from planetfall.web.serializers import serialize_battlefield
        self._send({
            "type": "show_mission_briefing",
            "data": {
                "battlefield": serialize_battlefield(bf, slyn_unknown=slyn_unknown),
                "mission_type": mission_type,
                "enemy_info": enemy_info,
                "special_rules": special_rules,
                "victory_conditions": victory_conditions,
                "defeat_conditions": defeat_conditions,
                "enemy_type": enemy_type,
            },
        })

    def show_battlefield(self, bf: Any, **kwargs: Any) -> None:
        from planetfall.web.serializers import serialize_battlefield
        self._send({
            "type": "show_battlefield",
            "data": serialize_battlefield(bf, **kwargs),
        })

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

    def prompt_mission_choice(self, options: list[dict]) -> int:
        def _friendly_name(opt: dict) -> str:
            t = opt.get("type", "?")
            if hasattr(t, "value"):
                return t.value.replace("_", " ").title()
            return str(t).replace("_", " ").title()

        choices = [
            f"{i+1}. {_friendly_name(opt)}"
            for i, opt in enumerate(options)
        ]
        result = self.select("Choose a mission:", choices)
        # Parse the index from the selection
        try:
            return int(result.split(".")[0]) - 1
        except (ValueError, IndexError):
            return 0

    def prompt_deployment(
        self, available_names: list[str], max_slots: int,
        grunt_count: int = 0, bot_available: bool = False,
        char_classes: dict[str, str] | None = None,
    ) -> dict:
        rid = str(uuid4())
        self._send({
            "type": "input_request", "input_type": "deployment",
            "id": rid,
            "available": available_names,
            "max_slots": max_slots,
            "grunt_count": grunt_count,
            "bot_available": bot_available,
            "char_classes": char_classes or {},
        })
        return self._wait_for_response(rid)

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

            rid = str(uuid4())
            self._send({
                "type": "input_request", "input_type": "weapon_select",
                "id": rid, "message": f"Weapon for {name}:",
                "weapons": weapon_profiles,
                "active_figure": profile,
            })
            choice = self._wait_for_response(rid)
            loadout[name] = choice
        return loadout

    def prompt_deployment_zones(
        self, bf: Any, figures: list, deployment_zones: list,
    ) -> None:
        from planetfall.web.serializers import serialize_battlefield
        for fig in figures:
            # Re-render battlefield so previously placed figures show up
            self._send({
                "type": "show_battlefield",
                "data": serialize_battlefield(bf),
            })
            # Build valid zones with capacity info
            valid = []
            for r, c in deployment_zones:
                if bf.zone_has_capacity(r, c, fig.side):
                    valid.append({"row": r, "col": c, "slots": 2 - len([f for f in bf.figures if f.is_alive and f.zone == (r, c)])})
            rid = str(uuid4())
            self._send({
                "type": "input_request",
                "input_type": "deploy_zone",
                "id": rid,
                "message": f"Deploy {fig.name}",
                "figure_name": fig.name,
                "valid_zones": valid,
            })
            resp = self._wait_for_response(rid)
            # Place figure on the battlefield
            fig.zone = (resp["row"], resp["col"])
            bf.figures.append(fig)

    def prompt_reaction_assignment(
        self, dice: list[int], figures: list[tuple[str, int]],
    ) -> dict[str, int]:
        rid = str(uuid4())
        self._send({
            "type": "input_request",
            "input_type": "reaction_assign",
            "id": rid,
            "data": {
                "dice": dice,
                "figures": [{"name": n, "speed": s} for n, s in figures],
            },
        })
        resp = self._wait_for_response(rid)
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
        rid = str(uuid4())
        self._send({
            "type": "input_request",
            "input_type": "movement",
            "id": rid,
            "figure_name": fig.name,
            "zones": zones_data,
            "can_scout_first": can_scout_first,
            "can_trooper_delay": can_trooper_delay,
            "active_figure": active_figure,
        })
        return self._wait_for_response(rid)

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
        rid = str(uuid4())
        self._send({
            "type": "input_request",
            "input_type": "zone_select",
            "id": rid,
            "message": message,
            "valid_zones": zones_data,
        })
        return int(self._wait_for_response(rid))

    def prompt_sector_coords(
        self, message: str, valid_ids: list[int],
    ) -> int:
        rid = str(uuid4())
        self._send({
            "type": "input_request", "input_type": "sector_select",
            "id": rid, "message": message, "valid_ids": valid_ids,
        })
        return int(self._wait_for_response(rid))

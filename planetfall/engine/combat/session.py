"""Interactive combat session manager.

Manages a human-in-the-loop battle where the player makes tactical
decisions each round while the AI narrates the action. The session
exposes a state-machine API: get options -> choose action -> resolve
-> get next options, etc.

Flow per round:
1. Start phase (auto)
2. Reaction roll -> player can reassign dice
3. Quick actions -> player picks action per quick figure
4. Enemy phase (auto, AI-driven)
5. Slow actions -> player picks action per slow figure
6. End phase: panic, casualties, victory check (auto)

Between phases the session returns a CombatState snapshot so the
orchestrator/UI can display status and the narrative agent can
describe what happened.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from planetfall.engine.combat.battlefield import (
    Battlefield, Figure, FigureSide, FigureStatus, TerrainType,
    is_impassable,
)
from planetfall.engine.combat.round import (
    roll_reaction_dice, roll_reactions, execute_enemy_phase,
    execute_player_activation, check_panic, check_battle_end,
    reset_round, get_round_casualties,
    ReactionRollResult, ActivationResult,
)
from planetfall.engine.combat.missions import MissionSetup

COMBAT_SAVE_VERSION = 1


class CombatPhase(str, Enum):
    """Current phase of the combat session."""
    SETUP = "setup"
    REACTION_ROLL = "reaction_roll"
    QUICK_ACTIONS = "quick_actions"
    ENEMY_PHASE = "enemy_phase"
    SLOW_ACTIONS = "slow_actions"
    END_PHASE = "end_phase"
    BATTLE_OVER = "battle_over"


@dataclass
class FigureSnapshot:
    """Serializable snapshot of a figure for display."""
    name: str
    side: str
    zone: tuple[int, int]
    status: str
    stun_markers: int
    toughness: int
    combat_skill: int
    weapon_name: str
    weapon_range: int
    weapon_shots: int
    char_class: str
    is_leader: bool
    is_specialist: bool
    has_acted: bool
    kill_points: int
    is_contact: bool = False
    fireteam_id: str = ""

    @classmethod
    def from_figure(cls, f: Figure) -> FigureSnapshot:
        return cls(
            name=f.name, side=f.side.value,
            zone=f.zone, status=f.status.value,
            stun_markers=f.stun_markers,
            toughness=f.toughness,
            combat_skill=f.combat_skill,
            weapon_name=f.weapon_name,
            weapon_range=f.weapon_range,
            weapon_shots=f.weapon_shots,
            char_class=f.char_class,
            is_leader=f.is_leader,
            is_specialist=f.is_specialist,
            has_acted=f.has_acted,
            kill_points=f.kill_points,
            is_contact=f.is_contact,
            fireteam_id=f.fireteam_id,
        )


@dataclass
class ActionOption:
    """A possible action for a player figure."""
    action_type: str  # "shoot", "move", "move_and_shoot", "brawl", "aid_marker", "aid_stun", "hold", "rush"
    description: str
    target_name: str | None = None
    move_to: tuple[int, int] | None = None
    use_aid: bool = False  # spend Aid marker for +1 to hit / +1 brawl


@dataclass
class CombatState:
    """Snapshot of the current combat state for display/decisions."""
    phase: CombatPhase
    round_number: int
    battlefield_grid: list[list[dict]] = field(default_factory=list)
    player_figures: list[FigureSnapshot] = field(default_factory=list)
    enemy_figures: list[FigureSnapshot] = field(default_factory=list)
    reaction_result: dict | None = None
    current_figure: str | None = None
    available_actions: list[dict] = field(default_factory=list)
    phase_log: list[str] = field(default_factory=list)
    outcome: str | None = None  # "player_victory" / "player_defeat" / None
    # For REACTION_ROLL phase: unassigned dice and figure info
    unassigned_dice: list[int] = field(default_factory=list)
    reaction_figures: list[tuple[str, int]] = field(default_factory=list)  # (name, reactions)


class CombatSession:
    """Manages an interactive combat encounter.

    Usage:
        session = CombatSession(mission_setup)
        state = session.start_battle()

        while state.phase != CombatPhase.BATTLE_OVER:
            # Display state to player, get their choice
            if state.available_actions:
                state = session.choose_action(action_index)
            else:
                state = session.advance()
    """

    def __init__(self, mission_setup: MissionSetup):
        self.bf = mission_setup.battlefield
        self.mission_setup = mission_setup
        self.round_number = 0
        self.phase = CombatPhase.SETUP
        self.reaction: ReactionRollResult | None = None
        self.quick_queue: list[str] = []
        self.slow_queue: list[str] = []
        self.round_log: list[str] = []
        self.full_log: list[str] = []
        self.objectives_secured: int = 0
        self.pre_round_alive: list[str] = []
        self._pending_actions: list[ActionOption] = []
        self._reaction_dice: list[int] = []
        self._reaction_figures: list[tuple[str, int]] = []
        self._delayed_troopers: set[str] = set()  # troopers who forgo quick for double slow
        self._had_objectives = len(mission_setup.objectives) > 0
        self.evacuated: list[str] = []  # figures that left the battlefield (non-casualty)
        self._free_escape_used = False  # per-round free escape (Clear Escape Paths)
        self._brawl_count: dict[str, int] = {}  # figure_name -> brawls this phase (multiple opponents bonus)

    @property
    def condition(self):
        """Shortcut to battlefield condition from mission setup."""
        return getattr(self.mission_setup, "condition", None)

    def to_dict(self) -> dict:
        """Serialize combat session state for save/resume."""
        return {
            "_version": COMBAT_SAVE_VERSION,
            "mission_setup": self.mission_setup.to_dict(),
            "round_number": self.round_number,
            "phase": self.phase.value,
            "reaction": {
                "dice_rolled": self.reaction.dice_rolled,
                "assignments": self.reaction.assignments,
                "quick_actors": self.reaction.quick_actors,
                "slow_actors": self.reaction.slow_actors,
                "log": self.reaction.log,
            } if self.reaction else None,
            "quick_queue": list(self.quick_queue),
            "slow_queue": list(self.slow_queue),
            "round_log": list(self.round_log),
            "full_log": list(self.full_log),
            "objectives_secured": self.objectives_secured,
            "pre_round_alive": list(self.pre_round_alive),
            "reaction_dice": list(self._reaction_dice),
            "reaction_figures": list(self._reaction_figures),
            "delayed_troopers": list(self._delayed_troopers),
            "had_objectives": self._had_objectives,
            "evacuated": list(self.evacuated),
            "free_escape_used": self._free_escape_used,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CombatSession":
        """Restore combat session from serialized state.

        Checks _version against COMBAT_SAVE_VERSION. If the saved version
        is newer than what we support, raises ValueError so the caller
        can fall back to a fresh combat start.
        """
        saved_version = d.get("_version", 0)
        if saved_version > COMBAT_SAVE_VERSION:
            raise ValueError(
                f"Combat save version {saved_version} is newer than "
                f"supported version {COMBAT_SAVE_VERSION}. "
                f"Cannot resume — will start fresh."
            )
        from planetfall.engine.combat.missions.base import MissionSetup as MS
        setup = MS.from_dict(d["mission_setup"])
        session = cls.__new__(cls)
        session.bf = setup.battlefield
        session.mission_setup = setup
        session.round_number = d["round_number"]
        session.phase = CombatPhase(d["phase"])
        if d.get("reaction"):
            r = d["reaction"]
            session.reaction = ReactionRollResult(
                dice_rolled=r["dice_rolled"],
                assignments=r["assignments"],
                quick_actors=r["quick_actors"],
                slow_actors=r["slow_actors"],
                log=r.get("log", []),
            )
        else:
            session.reaction = None
        session.quick_queue = d.get("quick_queue", [])
        session.slow_queue = d.get("slow_queue", [])
        session.round_log = d.get("round_log", [])
        session.full_log = d.get("full_log", [])
        session.objectives_secured = d.get("objectives_secured", 0)
        session.pre_round_alive = d.get("pre_round_alive", [])
        session._pending_actions = []  # recomputed on next advance
        session._reaction_dice = d.get("reaction_dice", [])
        session._reaction_figures = [tuple(x) for x in d.get("reaction_figures", [])]
        session._delayed_troopers = set(d.get("delayed_troopers", []))
        session._had_objectives = d.get("had_objectives", False)
        session.evacuated = d.get("evacuated", [])
        session._free_escape_used = d.get("free_escape_used", False)
        return session

    def _savvy_roll(self, fig: Figure, label: str) -> tuple[int, str]:
        """Roll a Savvy test, applying Scientific Mind (roll twice, pick best).

        Returns (total, description_string).
        """
        from planetfall.engine.dice import roll_d6

        if fig.char_class == "scientist":
            roll1 = roll_d6(f"{label} (1)")
            roll2 = roll_d6(f"{label} (2)")
            best = max(roll1.total, roll2.total)
            total = best + fig.savvy
            desc = (
                f"D6({roll1.total},{roll2.total} best={best})"
                f"+Savvy({fig.savvy})={total}"
            )
        else:
            roll = roll_d6(label)
            total = roll.total + fig.savvy
            desc = f"D6({roll.total})+Savvy({fig.savvy})={total}"
        return total, desc

    def _snapshot(self) -> CombatState:
        """Build a CombatState snapshot."""
        grid = []
        for r in range(self.bf.rows):
            row = []
            for c in range(self.bf.cols):
                zone = self.bf.get_zone(r, c)
                figs = self.bf.get_figures_in_zone(r, c)
                row.append({
                    "row": r, "col": c,
                    "terrain": zone.terrain.value,
                    "has_objective": zone.has_objective,
                    "objective_label": zone.objective_label,
                    "figures": [f.name for f in figs],
                })
            grid.append(row)

        action_dicts = [
            {
                "index": i,
                "action_type": a.action_type,
                "description": a.description,
                "target": a.target_name,
                "move_to": a.move_to,
            }
            for i, a in enumerate(self._pending_actions)
        ]

        return CombatState(
            phase=self.phase,
            round_number=self.round_number,
            battlefield_grid=grid,
            player_figures=[
                FigureSnapshot.from_figure(f)
                for f in self.bf.figures
                if f.side == FigureSide.PLAYER and f.is_alive
            ],
            enemy_figures=[
                FigureSnapshot.from_figure(f)
                for f in self.bf.figures
                if f.side == FigureSide.ENEMY and f.is_alive
            ],
            reaction_result=(
                {
                    "dice": self.reaction.dice_rolled,
                    "assignments": self.reaction.assignments,
                    "quick": self.reaction.quick_actors,
                    "slow": self.reaction.slow_actors,
                }
                if self.reaction else None
            ),
            current_figure=(
                self.quick_queue[0] if self.phase == CombatPhase.QUICK_ACTIONS and self.quick_queue
                else self.slow_queue[0] if self.phase == CombatPhase.SLOW_ACTIONS and self.slow_queue
                else None
            ),
            available_actions=action_dicts,
            phase_log=list(self.round_log),
            outcome=check_battle_end(self.bf),
            unassigned_dice=list(self._reaction_dice),
            reaction_figures=list(self._reaction_figures),
        )

    def start_battle(self) -> CombatState:
        """Initialize and start round 1. Returns REACTION_ROLL phase for player assignment."""
        self.round_number = 1
        self.bf.round_number = 1
        reset_round(self.bf)
        self.pre_round_alive = [f.name for f in self.bf.figures if f.is_alive]
        self.round_log = [f"=== Round {self.round_number} ==="]

        # Roll dice but don't assign yet — let player choose
        self._reaction_dice, self._reaction_figures = roll_reaction_dice(self.bf)
        self.round_log.append(
            f"Reaction roll: {self._reaction_dice} "
            f"({len(self._reaction_dice)} dice)"
        )
        self.phase = CombatPhase.REACTION_ROLL
        return self._snapshot()

    def assign_reactions(self, assignments: dict[str, int]) -> CombatState:
        """Finalize reaction dice assignments and transition to quick actions.

        Args:
            assignments: dict mapping figure_name -> die value chosen by player.
        """
        # Reveal contacts before assigning reactions
        self._check_contacts()

        self.reaction = roll_reactions(self.bf, assignments=assignments)
        self.round_log.extend(self.reaction.log)
        self.quick_queue = list(self.reaction.quick_actors)
        self.slow_queue = list(self.reaction.slow_actors)

        self.phase = CombatPhase.QUICK_ACTIONS
        self._brawl_count.clear()  # Reset multiple opponents bonus
        self._prepare_next_activation()

        if not self._pending_actions:
            return self.advance()

        return self._snapshot()

    def _check_contacts(self, include_obscured: bool = False):
        """Detect and reveal contacts using LoS + distance rules.

        Called after player movement. Auto-detects contacts based on:
        - Same zone: always
        - Adjacent (1 zone): if LoS not blocked
        - Within 18" (4 zones): if clear LoS (no intervening cover)

        If *include_obscured* is True, also runs the D6 4+ obscured
        detection check (contacts within 9"/2 zones with intervening
        cover). Used at the end of the Enemy Phase.
        """
        detected = self.bf.detect_contacts_auto()
        if include_obscured:
            detected.extend(self.bf.detect_contacts_obscured())
        self._reveal_detected_contacts(detected)

    def _reveal_detected_contacts(self, detected: list[Figure]):
        """Reveal a list of detected contacts, logging results."""
        for contact in detected:
            reveal_log = self.bf.reveal_contact(contact)
            for msg in reveal_log:
                self.round_log.append(msg)
                self.full_log.append(msg)

    # Objective types resolved on movement (not sweep)
    INTERACTIVE_OBJ_TYPES = {"discovery", "recon", "science"}

    def _clear_objective_zone(self, obj_zone: tuple[int, int], msg: str) -> None:
        """Clear an objective from a zone and log a message.

        Shared helper used by both sweep-check and auto-secure paths.
        """
        zone = self.bf.get_zone(*obj_zone)
        zone.has_objective = False
        zone.objective_label = ""
        self.objectives_secured += 1
        self.round_log.append(msg)
        self.full_log.append(msg)

    def _check_objective_interaction(self, fig: Figure):
        """Check if a player figure entered a zone with an interactive objective.

        Interactive objectives are resolved immediately when a figure enters:
        - discovery: Roll D6 on Investigation Discovery table.
        - recon: Scout auto-succeeds, others D6+Savvy 5+.
        - science: Scientist auto-succeeds, others D6+Savvy 5+.
        """
        if fig.side != FigureSide.PLAYER or not fig.is_alive:
            return

        zone = self.bf.get_zone(*fig.zone)
        if not zone.has_objective:
            return

        # Find matching interactive objective in this zone
        obj_match = None
        for obj in self.mission_setup.objectives:
            if obj["zone"] == fig.zone and obj.get("type") in self.INTERACTIVE_OBJ_TYPES:
                obj_match = obj
                break

        if not obj_match:
            return

        obj_type = obj_match["type"]

        if obj_type == "discovery":
            self._resolve_discovery(fig, obj_match, zone)
        elif obj_type == "recon":
            self._resolve_recon(fig, obj_match, zone)
        elif obj_type == "science":
            self._resolve_science(fig, obj_match, zone)

    def _resolve_discovery(self, fig: Figure, obj: dict, zone):
        """Resolve an Investigation Discovery marker (D6 table)."""
        from planetfall.engine.dice import roll_d6
        from planetfall.engine.tables.mission_objectives import INVESTIGATION_DISCOVERY_TABLE

        # Remove the objective
        zone.has_objective = False
        zone.objective_label = ""
        self.objectives_secured += 1
        self.mission_setup.objectives.remove(obj)

        # Roll on the table
        roll_result, entry = INVESTIGATION_DISCOVERY_TABLE.roll_on_table(
            f"Discovery at {fig.zone}"
        )

        msg_lines = [
            f"** Discovery at {fig.zone} — {fig.name} investigates! **",
            f"  D6 = {roll_result.total}: {entry.description}",
        ]

        # Apply effects
        effects = entry.effects or {}
        if effects.get("spawn_sleeper"):
            # Place a sleeper in the most distant terrain feature
            terrain_zones = [
                (r, c)
                for r in range(self.bf.rows)
                for c in range(self.bf.cols)
                if self.bf.get_zone(r, c).terrain
                not in (TerrainType.OPEN, TerrainType.IMPASSABLE, TerrainType.IMPASSABLE_BLOCKING)
            ]
            # Filter to zones with capacity
            terrain_zones = [
                z for z in terrain_zones
                if self.bf.zone_has_capacity(*z, FigureSide.ENEMY)
            ]
            if terrain_zones:
                farthest = max(
                    terrain_zones,
                    key=lambda z: self.bf.zone_distance(fig.zone, z),
                )
                # Spawn a basic sleeper enemy
                sleeper = Figure(
                    name=f"Sleeper-{len(self.bf.figures) + 1}",
                    side=FigureSide.ENEMY,
                    zone=farthest,
                    combat_skill=0, toughness=3, speed=4,
                    weapon_name="Military Rifle", weapon_range=24,
                    weapon_shots=1, weapon_damage=0,
                    char_class="sleeper", panic_range=0,
                )
                self.bf.figures.append(sleeper)
                msg_lines.append(f"  Sleeper placed at zone {farthest}!")

        if effects.get("spawn_contact"):
            # Place a contact in closest terrain feature
            terrain_zones = [
                (r, c)
                for r in range(self.bf.rows)
                for c in range(self.bf.cols)
                if self.bf.get_zone(r, c).terrain
                not in (TerrainType.OPEN, TerrainType.IMPASSABLE, TerrainType.IMPASSABLE_BLOCKING)
                and (r, c) != fig.zone
                and self.bf.zone_has_capacity(r, c, FigureSide.ENEMY)
            ]
            if terrain_zones:
                closest = min(
                    terrain_zones,
                    key=lambda z: self.bf.zone_distance(fig.zone, z),
                )
                # Derive species name from existing enemy figures
                from planetfall.engine.combat.battlefield import _base_species_name
                _existing = [f for f in self.bf.figures if f.side == FigureSide.ENEMY and f.char_class != "sleeper"]
                _species = _base_species_name(_existing[0].name) if _existing else "Lifeform"
                _template = _existing[0] if _existing else None
                contact = Figure(
                    name=f"{_species} {len(self.bf.figures) + 1}",
                    side=FigureSide.ENEMY,
                    zone=closest,
                    combat_skill=_template.combat_skill if _template else 0,
                    toughness=_template.toughness if _template else 3,
                    speed=_template.speed if _template else 4,
                    melee_damage=_template.melee_damage if _template else 0,
                    weapon_name=_template.weapon_name if _template else "Natural weapons",
                    weapon_range=_template.weapon_range if _template else 0,
                    weapon_shots=_template.weapon_shots if _template else 0,
                    char_class=_template.char_class if _template else "lifeform",
                    is_contact=True,
                )
                self.bf.figures.append(contact)
                msg_lines.append(f"  Contact placed at zone {closest}!")

        if effects.get("post_mission_find"):
            msg_lines.append("  Tagged for extraction — roll Post-Mission Finds after battle.")

        if effects.get("savvy_check"):
            threshold = effects["savvy_check"]
            total, desc = self._savvy_roll(fig, f"{fig.name} Savvy check")
            if total >= threshold:
                msg_lines.append(
                    f"  Savvy check: {desc} >= {threshold} — +1 Raw Materials!"
                )
            else:
                msg_lines.append(
                    f"  Savvy check: {desc} < {threshold} — failed."
                )

        if effects.get("mission_data"):
            msg_lines.append("  Mission Data collected! Transmitted to colony for analysis.")

        for line in msg_lines:
            self.round_log.append(line)
            self.full_log.append(line)

    def _resolve_recon(self, fig: Figure, obj: dict, zone):
        """Resolve a Recon marker (Scouting mission).

        Scouts auto-succeed. Others roll D6+Savvy, 5+ succeeds.
        On failure the recon is not possible (marker stays).
        """
        from planetfall.engine.dice import roll_d6

        if fig.char_class == "scout":
            # Auto-succeed
            zone.has_objective = False
            zone.objective_label = ""
            self.objectives_secured += 1
            self.mission_setup.objectives.remove(obj)
            msg = f"** Recon at {fig.zone} — {fig.name} (scout) recons automatically! **"
            self.round_log.append(msg)
            self.full_log.append(msg)
        else:
            total, desc = self._savvy_roll(fig, f"{fig.name} Recon Savvy check")
            if total >= 5:
                zone.has_objective = False
                zone.objective_label = ""
                self.objectives_secured += 1
                self.mission_setup.objectives.remove(obj)
                msg = (
                    f"** Recon at {fig.zone} — {fig.name} "
                    f"{desc} >= 5 — success! **"
                )
            else:
                msg = (
                    f"** Recon at {fig.zone} — {fig.name} "
                    f"{desc} < 5 — failed. "
                    f"Recon not possible. **"
                )
            self.round_log.append(msg)
            self.full_log.append(msg)

    def _resolve_science(self, fig: Figure, obj: dict, zone):
        """Resolve a Science marker (Science mission).

        Scientists auto-succeed. Others roll D6+Savvy, 5+ succeeds.
        On failure the sample is ruined (marker removed either way).
        """
        from planetfall.engine.dice import roll_d6

        zone.has_objective = False
        zone.objective_label = ""
        self.objectives_secured += 1
        self.mission_setup.objectives.remove(obj)

        if fig.char_class == "scientist":
            msg = f"** Science at {fig.zone} — {fig.name} (scientist) collects sample automatically! **"
            self.round_log.append(msg)
            self.full_log.append(msg)
        else:
            total, desc = self._savvy_roll(fig, f"{fig.name} Science Savvy check")
            if total >= 5:
                msg = (
                    f"** Science at {fig.zone} — {fig.name} "
                    f"{desc} >= 5 — sample collected! **"
                )
            else:
                msg = (
                    f"** Science at {fig.zone} — {fig.name} "
                    f"{desc} < 5 — sample ruined! **"
                )
            self.round_log.append(msg)
            self.full_log.append(msg)

    def _check_objective_sweep(self):
        """Check and secure sweep-type objectives at end of round.

        Sweep rules by objective type:
        - resource (Exploration): Same zone, no enemies in zone. One per side per round.
        - patrol: Same zone, no enemies in zone. Multiple per round.
        - hunt: Same zone as lifeform corpse + action. Handled separately.
        - secure/sweep/other skirmish: Same zone, no enemies closer. One per round.

        Interactive objectives (discovery, recon, science) are skipped here.
        """
        if not self.mission_setup.objectives:
            return

        player_figs = [f for f in self.bf.figures if f.side == FigureSide.PLAYER and f.is_alive]
        enemy_figs = [
            f for f in self.bf.figures
            if f.side == FigureSide.ENEMY and f.is_alive and not f.is_contact
        ]

        secured_count = 0  # track for one-per-round types
        remaining = []
        for obj in self.mission_setup.objectives:
            obj_type = obj.get("type", "objective")

            # Interactive objectives are resolved on movement, not sweep
            if obj_type in self.INTERACTIVE_OBJ_TYPES:
                remaining.append(obj)
                continue

            obj_zone = obj["zone"]

            # --- Patrol: same zone, no enemy in zone, multiple per round ---
            if obj_type == "patrol":
                player_in_zone = any(pf.zone == obj_zone for pf in player_figs)
                enemy_in_zone = any(ef.zone == obj_zone for ef in enemy_figs)
                if player_in_zone and not enemy_in_zone:
                    self._clear_objective_zone(
                        obj_zone, f"** Patrol objective at {obj_zone} cleared! **"
                    )
                else:
                    remaining.append(obj)
                continue

            # --- Resource (Exploration): same zone, no enemy in zone, one per round ---
            if obj_type == "resource":
                if secured_count > 0:
                    remaining.append(obj)
                    continue
                player_in_zone = any(pf.zone == obj_zone for pf in player_figs)
                enemy_in_zone = any(ef.zone == obj_zone for ef in enemy_figs)
                if player_in_zone and not enemy_in_zone:
                    secured_count += 1
                    self._clear_objective_zone(
                        obj_zone, f"** Resource objective at {obj_zone} secured! **"
                    )
                else:
                    remaining.append(obj)
                continue

            # --- Hunt: same zone as corpse, spend action to transmit ---
            if obj_type == "hunt":
                player_in_zone = any(pf.zone == obj_zone for pf in player_figs)
                if player_in_zone:
                    self._clear_objective_zone(
                        obj_zone, f"** Hunt data at {obj_zone} — transmitted to colony! **"
                    )
                else:
                    remaining.append(obj)
                continue

            # --- Default sweep (skirmish secure/sweep/etc): within 1 zone, no enemy closer, one per round ---
            if secured_count > 0:
                remaining.append(obj)
                continue

            min_player_dist = min(
                (self.bf.zone_distance(pf.zone, obj_zone) for pf in player_figs),
                default=999,
            )
            if min_player_dist > 1:
                remaining.append(obj)
                continue

            enemy_closer = any(
                self.bf.zone_distance(ef.zone, obj_zone) <= min_player_dist
                for ef in enemy_figs
            )
            if enemy_closer:
                remaining.append(obj)
                continue

            secured_count += 1
            self._clear_objective_zone(
                obj_zone, f"** Objective ({obj_type}) at {obj_zone} secured! **"
            )

        self.mission_setup.objectives = remaining

    def _auto_secure_remaining_objectives(self):
        """Auto-secure all remaining objectives when no enemies/contacts remain.

        With no threats on the battlefield, moving figures to each objective
        is a foregone conclusion. We resolve each objective automatically:
        - Sweep/patrol/resource/secure/hunt: auto-secured, no roll needed.
        - Interactive (discovery/recon/science): resolved with best available
          figure (specialist auto-succeeds, otherwise roll D6+Savvy).
        """
        if not self.mission_setup.objectives:
            return

        self.round_log.append(
            "Area secured — auto-resolving remaining objectives..."
        )

        player_figs = [
            f for f in self.bf.figures
            if f.side == FigureSide.PLAYER and f.is_alive
        ]

        for obj in list(self.mission_setup.objectives):
            obj_type = obj.get("type", "objective")
            obj_zone = obj["zone"]
            zone = self.bf.get_zone(*obj_zone)

            if obj_type in self.INTERACTIVE_OBJ_TYPES:
                # Pick best figure: specialist first, then highest Savvy
                best = self._pick_best_figure_for(obj_type, player_figs)
                if best:
                    # Temporarily move figure to objective zone for resolution
                    original_zone = best.zone
                    best.zone = obj_zone
                    if obj_type == "discovery":
                        self._resolve_discovery(best, obj, zone)
                    elif obj_type == "recon":
                        self._resolve_recon(best, obj, zone)
                    elif obj_type == "science":
                        self._resolve_science(best, obj, zone)
                    best.zone = original_zone
                else:
                    # No living figures — just clear it
                    self._clear_objective_zone(
                        obj_zone, f"** {obj_type.capitalize()} objective at {obj_zone} auto-secured (no figures)! **"
                    )
            else:
                # Non-interactive objectives: auto-secured
                self._clear_objective_zone(
                    obj_zone, f"** {obj_type.capitalize()} objective at {obj_zone} auto-secured! **"
                )

        self.mission_setup.objectives.clear()

    def _pick_best_figure_for(
        self, obj_type: str, player_figs: list[Figure]
    ) -> Figure | None:
        """Pick the best player figure to resolve an interactive objective.

        Specialists auto-succeed, so prefer them. Otherwise pick highest Savvy.
        """
        specialist_class = {
            "recon": "scout",
            "science": "scientist",
            "discovery": None,  # No specialist auto-success for discovery
        }.get(obj_type)

        if specialist_class:
            for fig in player_figs:
                if fig.char_class == specialist_class:
                    return fig

        # Highest Savvy for the D6+Savvy roll
        return max(player_figs, key=lambda f: f.savvy, default=None)

    def _prepare_next_activation(self):
        """Prepare action options for the next figure in queue."""
        self._pending_actions = []

        if self.phase == CombatPhase.QUICK_ACTIONS:
            queue = self.quick_queue
        elif self.phase == CombatPhase.SLOW_ACTIONS:
            queue = self.slow_queue
        else:
            return

        # Skip dead/acted figures
        while queue:
            fig = self.bf.get_figure_by_name(queue[0])
            if fig and fig.is_alive and not fig.has_acted:
                break
            queue.pop(0)

        if not queue:
            return

        fig = self.bf.get_figure_by_name(queue[0])
        if not fig:
            return

        self._pending_actions = self._get_actions_for(fig)

    def _get_actions_for(self, fig: Figure) -> list[ActionOption]:
        """Build the list of possible actions for a player figure."""
        actions: list[ActionOption] = []

        # If sprawling, only option is to stand up (handled automatically)
        if fig.status == FigureStatus.SPRAWLING:
            actions.append(ActionOption(
                action_type="hold",
                description=f"{fig.name} stands up from sprawling position",
            ))
            return actions

        enemies = [e for e in self.bf.figures
                   if e.side == FigureSide.ENEMY and e.is_alive and not e.is_contact]
        allies = [a for a in self.bf.figures
                  if a.side == FigureSide.PLAYER and a.is_alive and a.name != fig.name]
        adj_zones = self.bf.adjacent_zones(*fig.zone)

        # SHOOT — each visible enemy in range
        from planetfall.engine.combat.shooting import get_hit_target, get_effective_hit
        from planetfall.engine.combat.battlefield import zone_range_inches

        for enemy in enemies:
            dist = self.bf.zone_distance(fig.zone, enemy.zone)
            approx_range = zone_range_inches(dist)
            if approx_range <= fig.weapon_range:
                hit_needed = get_hit_target(self.bf, fig, enemy, shooter_moved=False, condition=self.condition)
                if hit_needed <= 6:
                    eff = get_effective_hit(self.bf, fig, enemy, shooter_moved=False, condition=self.condition)
                    eff_label = "auto" if eff <= 1 else f"{eff}+"
                    range_label = "close" if dist <= 2 else "medium" if approx_range <= 18 else "long"
                    actions.append(ActionOption(
                        action_type="shoot",
                        description=(
                            f"Shoot {enemy.name} at {range_label} range "
                            f"({eff_label}, {fig.weapon_shots} shot(s))"
                        ),
                        target_name=enemy.name,
                    ))
                    # Aid marker variant: +1 to hit
                    if fig.aid_marker:
                        aided_eff = max(1, eff - 1)
                        aided_label = "auto" if aided_eff <= 1 else f"{aided_eff}+"
                        actions.append(ActionOption(
                            action_type="shoot",
                            description=(
                                f"Shoot {enemy.name} at {range_label} range "
                                f"({aided_label}, {fig.weapon_shots} shot(s)) [spend Aid +1]"
                            ),
                            target_name=enemy.name,
                            use_aid=True,
                        ))

        # Determine move zones based on class and Speed
        from planetfall.engine.combat.battlefield import (
            move_zones as calc_move_zones,
            rush_available,
            rush_total_zones,
            move_zones_difficult,
            rush_available_difficult,
            rush_total_zones_difficult,
            ignores_difficult_ground,
        )
        is_scout = fig.char_class == "scout"
        fig_ignores_dg = ignores_difficult_ground(fig)
        source_difficult = self.bf.get_zone(*fig.zone).difficult

        def _effective_move(dest_zone: tuple[int, int]) -> int:
            """Get effective standard move zones, accounting for difficult ground."""
            if fig_ignores_dg:
                return calc_move_zones(fig.speed)
            if source_difficult or self.bf.get_zone(*dest_zone).difficult:
                return move_zones_difficult(fig.speed)
            return calc_move_zones(fig.speed)

        num_move_zones = calc_move_zones(fig.speed)

        # Build standard move zone list (check difficulty per-destination)
        # Start from canonical zones, then adjust for difficult ground
        base_move = self.bf.get_standard_move_zones(*fig.zone, fig.speed, is_scout)
        if not is_scout and not fig_ignores_dg and (source_difficult or True):
            # Re-check each zone with per-destination difficult ground penalty
            move_zones = []
            for zone in base_move:
                dist = max(abs(zone[0] - fig.zone[0]), abs(zone[1] - fig.zone[1]))
                eff = _effective_move(zone)
                if dist <= eff:
                    move_zones.append(zone)
        else:
            move_zones = list(base_move)

        # MOVE to zone (respecting stacking limit) — only if they have move zones
        for zone in move_zones:
            if not self.bf.zone_has_capacity(*zone, fig.side):
                continue
            zone_terrain = self.bf.get_zone(*zone).terrain
            terrain_label = zone_terrain.value.replace("_", " ")
            zone_figs = self.bf.get_figures_in_zone(*zone)
            fig_names = [f.name for f in zone_figs]
            is_jump = is_scout and zone not in adj_zones
            move_label = "Jump to" if is_jump else "Move to"
            desc = f"{move_label} zone {zone} ({terrain_label})"
            if fig_names:
                desc += f" [{', '.join(fig_names)}]"
            actions.append(ActionOption(
                action_type="move",
                description=desc,
                move_to=zone,
            ))

        # RUSH — uses action to extend movement (rules p.30: +2")
        # Speed 1-2: rush 1 zone (only way to move). Speed 5-6: rush 2 zones.
        # Difficult ground modifies rush availability and reach per-destination.
        # Movement penalty conditions block rushing entirely
        _cond = self.condition
        _movement_blocked = getattr(_cond, "movement_penalty", False)
        move_set = set(move_zones)
        base_rush = self.bf.get_rush_zones(*fig.zone, fig.speed)
        for zone in base_rush:
            if zone in move_set or zone == fig.zone:
                continue
            if not self.bf.zone_has_capacity(*zone, fig.side):
                continue
            dist = max(abs(zone[0] - fig.zone[0]), abs(zone[1] - fig.zone[1]))
            dest_difficult = self.bf.get_zone(*zone).difficult
            if fig_ignores_dg or (not source_difficult and not dest_difficult):
                can_rush = rush_available(fig.speed)
                rush_reach = rush_total_zones(fig.speed)
            else:
                can_rush = rush_available_difficult(fig.speed)
                rush_reach = rush_total_zones_difficult(fig.speed)
            if can_rush and dist <= rush_reach and not _movement_blocked:
                zone_terrain = self.bf.get_zone(*zone).terrain
                terrain_label = zone_terrain.value.replace("_", " ")
                zone_figs = self.bf.get_figures_in_zone(*zone)
                fig_names = [f.name for f in zone_figs]
                desc = f"Rush to zone {zone} ({terrain_label}) (no action)"
                if fig_names:
                    desc += f" [{', '.join(fig_names)}]"
                actions.append(ActionOption(
                    action_type="rush",
                    description=desc,
                    move_to=zone,
                ))

        # MOVE AND SHOOT — move then shoot (respecting stacking)
        for zone in move_zones:
            if not self.bf.zone_has_capacity(*zone, fig.side):
                continue
            for enemy in enemies:
                dist = self.bf.zone_distance(zone, enemy.zone)
                approx_range = zone_range_inches(dist)
                if approx_range <= fig.weapon_range:
                    hit_needed = get_hit_target(self.bf, fig, enemy, shooter_moved=True, condition=self.condition)
                    if hit_needed <= 6:
                        eff = get_effective_hit(self.bf, fig, enemy, shooter_moved=True, condition=self.condition)
                        eff_label = "auto" if eff <= 1 else f"{eff}+"
                        is_jump = is_scout and zone not in adj_zones
                        move_label = "Jump to" if is_jump else "Move to"
                        actions.append(ActionOption(
                            action_type="move_and_shoot",
                            description=(
                                f"{move_label} {zone} then shoot {enemy.name} "
                                f"({eff_label})"
                            ),
                            target_name=enemy.name,
                            move_to=zone,
                        ))

        # SHOOT THEN MOVE — Flexible Combat Training (scouts only)
        if is_scout:
            for enemy in enemies:
                dist = self.bf.zone_distance(fig.zone, enemy.zone)
                approx_range = zone_range_inches(dist)
                if approx_range <= fig.weapon_range:
                    hit_needed = get_hit_target(self.bf, fig, enemy, shooter_moved=False)
                    if hit_needed <= 6:
                        eff = get_effective_hit(self.bf, fig, enemy, shooter_moved=False)
                        eff_label = "auto" if eff <= 1 else f"{eff}+"
                        for zone in move_zones:
                            if not self.bf.zone_has_capacity(*zone, fig.side):
                                continue
                            is_jump = zone not in adj_zones
                            move_label = "jump to" if is_jump else "move to"
                            actions.append(ActionOption(
                                action_type="shoot_and_move",
                                description=(
                                    f"Shoot {enemy.name} ({eff_label}) "
                                    f"then {move_label} {zone}"
                                ),
                                target_name=enemy.name,
                                move_to=zone,
                            ))

        # BRAWL — enemies in same zone
        for enemy in enemies:
            if enemy.zone == fig.zone:
                actions.append(ActionOption(
                    action_type="brawl",
                    description=f"Brawl with {enemy.name} in melee combat",
                    target_name=enemy.name,
                ))
                if fig.aid_marker:
                    actions.append(ActionOption(
                        action_type="brawl",
                        description=f"Brawl with {enemy.name} in melee combat [spend Aid +1]",
                        target_name=enemy.name,
                        use_aid=True,
                    ))

        # AID — place aid marker OR remove stun from ally in same zone
        for ally in allies:
            if ally.zone != fig.zone:
                continue
            # Option 1: Place aid marker (if they don't already have one)
            if not ally.aid_marker:
                actions.append(ActionOption(
                    action_type="aid_marker",
                    description=(
                        f"Aid {ally.name} — place Aid marker"
                    ),
                    target_name=ally.name,
                ))
            # Option 2: Remove stun marker
            if ally.stun_markers > 0:
                actions.append(ActionOption(
                    action_type="aid_stun",
                    description=(
                        f"Aid {ally.name} — remove 1 stun marker "
                        f"({ally.stun_markers} current)"
                    ),
                    target_name=ally.name,
                ))

        # DELAY — trooper forgoes quick action for double slow action
        if (fig.char_class == "trooper"
                and self.phase == CombatPhase.QUICK_ACTIONS
                and fig.name not in self._delayed_troopers):
            actions.append(ActionOption(
                action_type="delay",
                description=f"{fig.name} delays — will take 2 actions in slow phase",
            ))

        # FREE ESCAPE — condition allows one character per round to escape
        # from anywhere on the battlefield (Clear Escape Paths)
        _cond_fe = self.condition
        if (getattr(_cond_fe, "free_escape", False)
                and not self._free_escape_used):
            actions.append(ActionOption(
                action_type="free_escape",
                description=f"{fig.name} escapes the battlefield (free — Clear Escape Paths)",
            ))

        # LEAVE BATTLEFIELD — available at edge zones
        if self.bf.is_edge_zone(*fig.zone):
            actions.append(ActionOption(
                action_type="leave_battlefield",
                description=f"{fig.name} leaves the battlefield",
            ))

        # HOLD — do nothing
        actions.append(ActionOption(
            action_type="hold",
            description=f"{fig.name} holds position and stays alert",
        ))

        return actions

    def choose_action(self, action_index: int) -> CombatState:
        """Player chooses an action for the current figure.

        Args:
            action_index: Index into available_actions list.

        Returns:
            Updated CombatState after resolution.
        """
        if not self._pending_actions or action_index >= len(self._pending_actions):
            return self._snapshot()

        action = self._pending_actions[action_index]

        # Get the current figure
        if self.phase == CombatPhase.QUICK_ACTIONS and self.quick_queue:
            fig_name = self.quick_queue.pop(0)
        elif self.phase == CombatPhase.SLOW_ACTIONS and self.slow_queue:
            fig_name = self.slow_queue.pop(0)
        else:
            return self._snapshot()

        fig = self.bf.get_figure_by_name(fig_name)
        if not fig:
            return self._snapshot()

        # Handle trooper delay — skip quick action, get 2 slow activations
        if action.action_type == "delay":
            self._delayed_troopers.add(fig_name)
            # Add to slow queue twice (at the start for priority)
            self.slow_queue.insert(0, fig_name)
            self.slow_queue.insert(0, fig_name)
            msg = f"{fig_name} delays — will take 2 actions in the slow phase"
            self.round_log.append(msg)
            self.full_log.append(msg)
            fig.has_acted = False  # Not yet acted — will act in slow phase

            self._prepare_next_activation()
            if not self._pending_actions:
                return self.advance()
            return self._snapshot()

        # Execute the action
        phase_str = "quick" if self.phase == CombatPhase.QUICK_ACTIONS else "slow"
        activation = execute_player_activation(
            self.bf, fig,
            action_type=action.action_type,
            move_to=action.move_to,
            target_name=action.target_name,
            phase=phase_str,
            use_aid=action.use_aid,
            condition=self.condition,
        )
        return self._finalize_activation(fig, fig_name, activation)

    def get_activation_queue(self) -> list[str]:
        """Return the current phase's activation queue (names of figures waiting to act)."""
        if self.phase == CombatPhase.QUICK_ACTIONS:
            return list(self.quick_queue)
        elif self.phase == CombatPhase.SLOW_ACTIONS:
            return list(self.slow_queue)
        return []

    def set_next_figure(self, fig_name: str) -> None:
        """Move a figure to the front of the current phase's activation queue."""
        if self.phase == CombatPhase.QUICK_ACTIONS and fig_name in self.quick_queue:
            self.quick_queue.remove(fig_name)
            self.quick_queue.insert(0, fig_name)
        elif self.phase == CombatPhase.SLOW_ACTIONS and fig_name in self.slow_queue:
            self.slow_queue.remove(fig_name)
            self.slow_queue.insert(0, fig_name)
        # Refresh pending actions for the new front figure
        self._prepare_next_activation()

    def _pop_current_figure(self) -> tuple[str, "Figure"] | None:
        """Pop the current figure from the activation queue."""
        if self.phase == CombatPhase.QUICK_ACTIONS and self.quick_queue:
            fig_name = self.quick_queue.pop(0)
        elif self.phase == CombatPhase.SLOW_ACTIONS and self.slow_queue:
            fig_name = self.slow_queue.pop(0)
        else:
            return None
        fig = self.bf.get_figure_by_name(fig_name)
        if not fig:
            return None
        return fig_name, fig

    def _finalize_activation(
        self, fig: "Figure", fig_name: str, activation: "ActivationResult",
    ) -> CombatState:
        """Post-action processing: logging, contacts, objectives, advance."""
        self.round_log.extend(activation.log)
        self.full_log.extend(activation.log)

        # Handle leave battlefield / free escape — remove figure (non-casualty)
        if activation.action_type in ("leave_battlefield", "free_escape"):
            self.evacuated.append(fig_name)
            if activation.action_type == "free_escape":
                self._free_escape_used = True
            if fig in self.bf.figures:
                self.bf.figures.remove(fig)
            # Remove from queues
            if fig_name in self.quick_queue:
                self.quick_queue.remove(fig_name)
            if fig_name in self.slow_queue:
                self.slow_queue.remove(fig_name)
            self._prepare_next_activation()
            if not self._pending_actions:
                return self.advance()
            return self._snapshot()

        if fig_name in self._delayed_troopers and fig_name in self.slow_queue:
            fig.has_acted = False

        self._check_contacts()
        self._check_objective_interaction(fig)

        self._prepare_next_activation()
        if not self._pending_actions:
            return self.advance()
        return self._snapshot()

    def execute_direct_action(
        self,
        action_type: str,
        move_to: tuple[int, int] | None = None,
        target_name: str | None = None,
        use_aid: bool = False,
    ) -> CombatState:
        """Execute a player figure's turn with explicit parameters.

        Used by the multi-step UI. Handles same post-action logic as choose_action.
        """
        result = self._pop_current_figure()
        if not result:
            return self._snapshot()
        fig_name, fig = result

        phase_str = "quick" if self.phase == CombatPhase.QUICK_ACTIONS else "slow"
        activation = execute_player_activation(
            self.bf, fig,
            action_type=action_type,
            move_to=move_to,
            target_name=target_name,
            phase=phase_str,
            use_aid=use_aid,
            condition=self.condition,
        )
        return self._finalize_activation(fig, fig_name, activation)

    def queue_for_slow_phase(self, fig_name: str) -> None:
        """Queue a figure for an additional slow phase activation (trooper delay).

        The trooper acts in quick phase (no move) and then gets one more
        action in slow phase (also no move).
        """
        self._delayed_troopers.add(fig_name)
        # Reset has_acted so _prepare_next_activation doesn't skip them
        fig = self.bf.get_figure_by_name(fig_name)
        if fig:
            fig.has_acted = False
        if fig_name not in self.slow_queue:
            self.slow_queue.insert(0, fig_name)

    def advance(self) -> CombatState:
        """Advance to the next phase automatically.

        Call this when the current phase has no player decisions
        (enemy phase, end phase) or when a player-decision phase
        is exhausted.
        """
        if self.phase == CombatPhase.REACTION_ROLL:
            # Auto-assign (optimal greedy) if player doesn't choose
            return self.assign_reactions({})

        if self.phase == CombatPhase.QUICK_ACTIONS:
            # Move to enemy phase — just transition, don't execute yet
            self.phase = CombatPhase.ENEMY_PHASE
            self._brawl_count.clear()  # Reset multiple opponents bonus
            self.round_log.append("--- Enemy Actions Phase ---")
            return self._snapshot()

        elif self.phase == CombatPhase.ENEMY_PHASE:
            # Execute all enemy actions at once (use advance_enemy_step for one-at-a-time)
            while True:
                state = self.advance_enemy_step()
                if self.phase != CombatPhase.ENEMY_PHASE:
                    return state

        elif self.phase == CombatPhase.SLOW_ACTIONS:
            # Move to end phase
            return self._end_phase()

        elif self.phase == CombatPhase.END_PHASE:
            # Start next round
            return self._start_next_round()

        return self._snapshot()

    def _build_enemy_queue(self):
        """Build the queue of enemy activations for step-by-step execution."""
        from planetfall.engine.combat.round import _activate_contact
        from planetfall.engine.combat.enemy_ai import get_enemy_activation_order, plan_enemy_action

        self._enemy_queue = []

        # Investigation/Scouting: spawn contacts at start of enemy phase
        self._spawn_mission_contacts()

        # Contacts first
        contacts = [
            f for f in self.bf.figures
            if f.side == FigureSide.ENEMY and f.is_alive and f.is_contact
        ]
        for contact in contacts:
            self._enemy_queue.append(("contact", contact, contacts))

        # Then revealed enemies
        enemies = get_enemy_activation_order(self.bf)
        for enemy in enemies:
            if not enemy.is_alive or not enemy.can_act or enemy.is_contact:
                continue
            self._enemy_queue.append(("enemy", enemy, None))

        # End-of-phase detection
        self._enemy_queue.append(("end_detection", None, None))

    def advance_enemy_step(self) -> CombatState:
        """Execute a single enemy activation and return updated state.

        Call repeatedly during ENEMY_PHASE. Returns snapshot after each
        activation. When all enemies have acted, transitions to SLOW_ACTIONS.
        """
        from planetfall.engine.combat.round import _activate_contact
        from planetfall.engine.combat.enemy_ai import plan_enemy_action
        from planetfall.engine.combat.shooting import resolve_shooting_action
        from planetfall.engine.combat.brawling import resolve_brawl

        # Build queue on first call
        if not hasattr(self, '_enemy_queue') or self._enemy_queue is None:
            self._build_enemy_queue()

        if not self._enemy_queue:
            # All done — transition to slow actions
            self._enemy_queue = None
            self._check_contacts(include_obscured=True)
            self.phase = CombatPhase.SLOW_ACTIONS
            self._brawl_count.clear()  # Reset multiple opponents bonus
            self.round_log.append("--- Slow Actions Phase ---")
            self._prepare_next_activation()
            if not self._pending_actions:
                return self.advance()
            return self._snapshot()

        entry_type, figure, extra = self._enemy_queue.pop(0)

        if entry_type == "contact":
            contacts_list = extra
            activation = _activate_contact(self.bf, figure, contacts_list, condition=self.condition)
            if activation:
                self.round_log.extend(activation.log)
                self.full_log.extend(activation.log)
            return self._snapshot()

        if entry_type == "end_detection":
            # End-of-phase obscured contact detection
            detected = self.bf.detect_contacts_obscured()
            for det in detected:
                reveal_log = self.bf.reveal_contact(det)
                self.round_log.extend(reveal_log)
                self.full_log.extend(reveal_log)
            # Check if any newly revealed enemies need to be queued
            # (Per rules: revealed during enemy phase act NEXT phase, so don't queue)
            return self._snapshot()

        # Regular enemy activation
        enemy = figure
        if not enemy.is_alive or not enemy.can_act or enemy.is_contact:
            return self._snapshot()

        action = plan_enemy_action(self.bf, enemy, condition=self.condition)
        log = list(action.log)

        if action.move_to and action.action_type in ("move", "move_and_shoot"):
            enemy.zone = action.move_to
            # Check contact detection after enemy movement
            detected = self.bf.detect_contacts_auto()
            for det in detected:
                reveal_log = self.bf.reveal_contact(det)
                log.extend(reveal_log)

        if action.target_name and action.action_type in ("shoot", "move_and_shoot"):
            target = self.bf.get_figure_by_name(action.target_name)
            if target and target.is_alive:
                shooter_moved = action.move_to is not None
                shots = resolve_shooting_action(self.bf, enemy, target, shooter_moved, condition=self.condition)
                for shot in shots:
                    log.extend(shot.log)

        elif action.action_type == "brawl" and action.target_name:
            target = self.bf.get_figure_by_name(action.target_name)
            if target and target.is_alive:
                # Multiple opponents bonus (rules p.39): cumulative +1 per prior brawl
                atk_bonus = self._brawl_count.get(target.name, 0)
                def_bonus = self._brawl_count.get(enemy.name, 0)
                brawl = resolve_brawl(self.bf, enemy, target,
                                      attacker_bonus=atk_bonus, defender_bonus=def_bonus)
                self._brawl_count[enemy.name] = self._brawl_count.get(enemy.name, 0) + 1
                self._brawl_count[target.name] = self._brawl_count.get(target.name, 0) + 1
                log.extend(brawl.log)

        if enemy.stun_markers > 0:
            enemy.stun_markers = max(0, enemy.stun_markers - 1)
        enemy.has_acted = True

        self.round_log.extend(log)
        self.full_log.extend(log)
        return self._snapshot()

    def _end_phase(self) -> CombatState:
        """Execute end-of-round: casualties, panic, victory check."""
        self.phase = CombatPhase.END_PHASE
        self.round_log.append("--- End Phase ---")

        casualties = get_round_casualties(self.bf, self.pre_round_alive)
        if casualties:
            self.round_log.append(f"Casualties this round: {', '.join(casualties)}")

        # Panic check for enemy casualties
        enemy_casualties = [
            c for c in casualties
            if any(f.name == c and f.side == FigureSide.ENEMY for f in self.bf.figures)
        ]
        if enemy_casualties:
            panic = check_panic(self.bf, enemy_casualties)
            if panic:
                self.round_log.extend(panic.log)
                self.full_log.extend(panic.log)

        # Objective sweep check — end of round, auto-secure nearby objectives
        self._check_objective_sweep()

        # Patrol wildlife: spawn 1 contact at random edge each round
        self._patrol_wildlife_spawn()

        # Battlefield condition end-of-round effects
        self._apply_condition_end_of_round()

        # Victory check
        outcome = check_battle_end(self.bf)
        remaining_objectives = len(self.mission_setup.objectives)

        if outcome == "player_defeat":
            # If figures evacuated, not a true defeat
            if self.evacuated:
                # All remaining players dead but some escaped
                self.phase = CombatPhase.BATTLE_OVER
                self.round_log.append("Remaining squad eliminated — partial evacuation.")
                self.full_log.extend(self.round_log)
                return self._snapshot()
            self.phase = CombatPhase.BATTLE_OVER
            self.round_log.append("BATTLE OVER: DEFEAT...")
            self.full_log.extend(self.round_log)
            return self._snapshot()

        # Objective-based victory checks
        from planetfall.engine.models import MissionType
        # Missions that require evacuation after objectives are done
        EVAC_MISSIONS = {
            MissionType.INVESTIGATION, MissionType.SCOUTING, MissionType.SCIENCE,
        }
        requires_evac = self.mission_setup.mission_type in EVAC_MISSIONS

        if remaining_objectives == 0 and self._had_objectives:
            if requires_evac:
                # Must evacuate all players after completing objectives
                players_on_field = [
                    f for f in self.bf.figures
                    if f.side == FigureSide.PLAYER and f.is_alive
                ]
                if not players_on_field:
                    self.phase = CombatPhase.BATTLE_OVER
                    self.round_log.append(
                        "All objectives completed and squad evacuated — VICTORY!"
                    )
                    self.full_log.extend(self.round_log)
                    return self._snapshot()
                # else: objectives done but players still on field — continue
            else:
                # Other missions: objectives secured = auto-victory
                self.phase = CombatPhase.BATTLE_OVER
                self.round_log.append("All objectives secured — VICTORY!")
                self.full_log.extend(self.round_log)
                return self._snapshot()

        if outcome == "player_victory":
            # Missions with contacts/evac don't end just because no enemies are on the table
            is_patrol = self.mission_setup.mission_type == MissionType.PATROL
            if is_patrol and remaining_objectives > 0:
                # Continue — enemies will spawn, objectives still need clearing
                pass
            elif requires_evac:
                # Evac missions: auto-secure remaining objectives but keep playing
                if remaining_objectives > 0:
                    self._auto_secure_remaining_objectives()
                # Don't end — players still need to evacuate
            else:
                if remaining_objectives > 0:
                    # No threats left — auto-secure all remaining objectives
                    self._auto_secure_remaining_objectives()
                self.phase = CombatPhase.BATTLE_OVER
                self.round_log.append("BATTLE OVER: VICTORY!")
                self.full_log.extend(self.round_log)
                return self._snapshot()

        # Continue to next round
        return self._start_next_round()

    def _start_next_round(self) -> CombatState:
        """Start a new combat round. Returns REACTION_ROLL phase for player assignment."""
        self.full_log.extend(self.round_log)
        self.round_number += 1
        self.bf.round_number = self.round_number
        reset_round(self.bf)
        self._delayed_troopers.clear()
        self.pre_round_alive = [f.name for f in self.bf.figures if f.is_alive]
        self.round_log = [f"=== Round {self.round_number} ==="]

        # Check max rounds
        if self.round_number > self.mission_setup.max_rounds:
            self.phase = CombatPhase.BATTLE_OVER
            outcome = check_battle_end(self.bf)
            self.round_log.append(
                f"Max rounds reached. "
                f"{'VICTORY!' if outcome == 'player_victory' else 'DEFEAT...'}"
            )
            self.full_log.extend(self.round_log)
            return self._snapshot()

        # Roll dice but don't assign yet — let player choose
        self._reaction_dice, self._reaction_figures = roll_reaction_dice(self.bf)
        self.round_log.append(
            f"Reaction roll: {self._reaction_dice} "
            f"({len(self._reaction_dice)} dice)"
        )

        self.phase = CombatPhase.REACTION_ROLL
        return self._snapshot()

    def _spawn_mission_contacts(self) -> None:
        """Spawn contacts at start of enemy phase for missions that require it.

        Investigation: D6 per non-deploy edge (3 edges), 1-3 = new Contact.
        Scouting: D6, on 6 = new Contact at random edge center.
        Science: D6 (or 2D6 at high hazard), on 6 = new Contact at random edge.
        """
        from planetfall.engine.models import MissionType
        from planetfall.engine.dice import roll_d6
        import random

        mt = self.mission_setup.mission_type
        template = self.mission_setup.lifeform_template
        if not template:
            return

        if mt not in (MissionType.INVESTIGATION, MissionType.SCOUTING, MissionType.SCIENCE):
            return

        # Build non-deploy edge zones (top, left, right — excluding bottom/player edge)
        edges_by_side: list[list[tuple[int, int]]] = []
        # Top edge
        top = [(0, c) for c in range(self.bf.cols)
               if not is_impassable(self.bf.get_zone(0, c).terrain)
               and self.bf.zone_has_capacity(0, c, FigureSide.ENEMY)]
        if top:
            edges_by_side.append(top)
        # Left edge
        left = [(r, 0) for r in range(1, self.bf.rows - 1)
                if not is_impassable(self.bf.get_zone(r, 0).terrain)
                and self.bf.zone_has_capacity(r, 0, FigureSide.ENEMY)]
        if left:
            edges_by_side.append(left)
        # Right edge
        right = [(r, self.bf.cols - 1) for r in range(1, self.bf.rows - 1)
                 if not is_impassable(self.bf.get_zone(r, self.bf.cols - 1).terrain)
                 and self.bf.zone_has_capacity(r, self.bf.cols - 1, FigureSide.ENEMY)]
        if right:
            edges_by_side.append(right)

        spawned = []

        if mt == MissionType.INVESTIGATION:
            # D6 per non-deploy edge; 1-3 = spawn contact on that edge
            for edge_zones in edges_by_side:
                roll = roll_d6("Investigation contact spawn")
                if roll.total <= 3 and edge_zones:
                    zone = random.choice(edge_zones)
                    spawned.append((zone, roll.total))

        elif mt == MissionType.SCOUTING:
            # D6, on 6 = new contact at random edge center
            roll = roll_d6("Scouting contact spawn")
            if roll.total == 6:
                all_edges = [z for edge in edges_by_side for z in edge]
                if all_edges:
                    zone = random.choice(all_edges)
                    spawned.append((zone, roll.total))

        elif mt == MissionType.SCIENCE:
            # D6 (or 2D6 at high hazard), on 6 = new contact
            roll = roll_d6("Science contact spawn")
            if roll.total == 6:
                all_edges = [z for edge in edges_by_side for z in edge]
                if all_edges:
                    zone = random.choice(all_edges)
                    spawned.append((zone, roll.total))

        # Create contact figures
        for zone, roll_val in spawned:
            next_idx = sum(1 for f in self.bf.figures if f.side == FigureSide.ENEMY) + 1
            lf_name = template.get("name", "Lifeform")
            contact = Figure(
                name=f"{lf_name} {next_idx}",
                side=FigureSide.ENEMY,
                zone=zone,
                speed=template.get("speed", 4),
                combat_skill=template.get("combat_skill", 0),
                toughness=template.get("toughness", 3),
                melee_damage=template.get("strike_damage", 0),
                armor_save=template.get("armor_save", 0),
                kill_points=template.get("kill_points", 1),
                panic_range=0,
                weapon_name="Natural weapons",
                weapon_range=0,
                weapon_shots=0,
                weapon_damage=template.get("strike_damage", 0),
                special_rules=list(template.get("special_rules", [])),
                char_class="lifeform",
                is_contact=True,
            )
            self.bf.figures.append(contact)
            self.round_log.append(
                f"Contact detected at zone {zone}! (D6 = {roll_val})"
            )
            self.full_log.append(
                f"Contact detected at zone {zone}! (D6 = {roll_val})"
            )

    def _patrol_wildlife_spawn(self) -> None:
        """Spawn 1 contact at a random non-player edge for patrol wildlife missions."""
        from planetfall.engine.models import MissionType
        if self.mission_setup.mission_type != MissionType.PATROL:
            return
        template = self.mission_setup.lifeform_template
        if not template:
            return  # Slyn patrol — no spawning

        # Get edge zones excluding bottom row (player entry)
        import random
        edges = []
        for c in range(self.bf.cols):
            # Top edge
            if self.bf.get_zone(0, c).terrain not in (TerrainType.IMPASSABLE, TerrainType.IMPASSABLE_BLOCKING):
                edges.append((0, c))
        for r in range(1, self.bf.rows - 1):
            # Left and right edges
            if self.bf.get_zone(r, 0).terrain not in (TerrainType.IMPASSABLE, TerrainType.IMPASSABLE_BLOCKING):
                edges.append((r, 0))
            if self.bf.get_zone(r, self.bf.cols - 1).terrain not in (TerrainType.IMPASSABLE, TerrainType.IMPASSABLE_BLOCKING):
                edges.append((r, self.bf.cols - 1))
        # Exclude bottom row (player entry edge)

        # Filter to zones with capacity
        valid = [z for z in edges if self.bf.zone_has_capacity(*z, FigureSide.ENEMY)]
        if not valid:
            return

        zone = random.choice(valid)
        traits = []
        if template.get("special_attack") == "shoot":
            traits.append("chain_on_6")

        next_idx = sum(1 for f in self.bf.figures if f.side == FigureSide.ENEMY) + 1
        lf_name = template.get("name", "Lifeform")
        contact = Figure(
            name=f"{lf_name} {next_idx}",
            side=FigureSide.ENEMY,
            zone=zone,
            speed=template.get("speed", 4),
            combat_skill=template.get("combat_skill", 0),
            toughness=template.get("toughness", 3),
            melee_damage=template.get("strike_damage", 0),
            armor_save=template.get("armor_save", 0),
            kill_points=template.get("kill_points", 1),
            panic_range=0,
            weapon_name="Natural weapons",
            weapon_range=0,
            weapon_shots=0,
            weapon_damage=template.get("strike_damage", 0),
            weapon_traits=traits,
            special_rules=[
                template.get("special_attack", ""),
                template.get("unique_ability", ""),
            ],
            char_class="lifeform",
            is_contact=True,
        )
        self.bf.figures.append(contact)
        self.round_log.append(f"Wildlife contact detected at zone {zone}!")

    def _apply_condition_end_of_round(self) -> None:
        """Apply battlefield condition effects at end of each round."""
        import random as rng
        from planetfall.engine.dice import roll_d6

        cond = self.condition
        if not cond:
            return

        # Variable round visibility: re-roll each round
        if getattr(cond, "visibility_type", "") == "variable_round":
            new_vis = roll_d6("Visibility re-roll").total + 8
            old_vis = cond.visibility_limit
            cond.visibility_limit = new_vis
            self.round_log.append(
                f"Visibility shifts: {old_vis}\" → {new_vis}\" (D6+8)"
            )

        # Uncertain terrain: reveal features within 2 zones (~9") of crew
        # or within 4 zones (~18") with LoS, roll D100 on Uncertain Features table
        if self.bf.uncertain_features:
            self._reveal_uncertain_terrain()

        # Shifting terrain: drift terrain 1D6" random direction,
        # figures on shifted terrain roll 4+ or become Sprawling
        if getattr(cond, "shifting_terrain", False):
            shift_inches = roll_d6("Shifting terrain drift").total
            shift_zones = shift_inches // 4  # convert inches to zones
            if shift_zones > 0:
                # Pick a random terrain feature zone and shift it
                directions = [(-1, 0), (1, 0), (0, -1), (0, 1),
                              (-1, -1), (-1, 1), (1, -1), (1, 1)]
                direction = rng.choice(directions)
                terrain_zones = [
                    (r, c) for r in range(self.bf.rows) for c in range(self.bf.cols)
                    if self.bf.get_zone(r, c).terrain.value not in ("open", "impassable", "impassable_blocking")
                ]
                if terrain_zones:
                    src = rng.choice(terrain_zones)
                    src_zone = self.bf.get_zone(*src)
                    nr = min(max(0, src[0] + direction[0] * shift_zones), self.bf.rows - 1)
                    nc = min(max(0, src[1] + direction[1] * shift_zones), self.bf.cols - 1)
                    dest_zone = self.bf.get_zone(nr, nc)

                    # Only shift if destination is open (no collision)
                    if dest_zone.terrain == TerrainType.OPEN:
                        # Swap terrain
                        dest_zone.terrain = src_zone.terrain
                        dest_zone.terrain_name = src_zone.terrain_name
                        dest_zone.difficult = src_zone.difficult
                        src_zone.terrain = TerrainType.OPEN
                        src_zone.terrain_name = ""
                        src_zone.difficult = False
                        self.round_log.append(
                            f"Terrain shifts {shift_inches}\": "
                            f"{dest_zone.terrain_name or dest_zone.terrain.value} "
                            f"moves {src} → ({nr},{nc})"
                        )
                    else:
                        self.round_log.append(
                            f"Terrain shifts {shift_inches}\" but blocked — feature stays at {src}"
                        )

                    # Check figures on the shifted feature — roll 4+ or Sprawling
                    affected_figs = [
                        f for f in self.bf.figures
                        if f.is_alive and f.zone == src
                    ]
                    for fig in affected_figs:
                        stability = roll_d6(f"{fig.name} stability").total
                        if stability < 4:
                            fig.status = FigureStatus.SPRAWLING
                            self.round_log.append(
                                f"  {fig.name} rolls {stability} — knocked Sprawling by shifting terrain!"
                            )
                        else:
                            self.round_log.append(
                                f"  {fig.name} rolls {stability} — stays standing"
                            )

        # Cloud drift: move clouds 1D6" in random direction, apply toxic/corrosive
        if getattr(self.bf, "cloud_positions", None):
            drift_inches = roll_d6("Cloud drift").total
            drift_zones = drift_inches // 4
            if drift_zones > 0:
                directions = [(-1, 0), (1, 0), (0, -1), (0, 1),
                              (-1, -1), (-1, 1), (1, -1), (1, 1)]
                direction = rng.choice(directions)
                new_positions = []
                for pos in self.bf.cloud_positions:
                    # Clear old cloud marker
                    old_zone = self.bf.get_zone(*pos)
                    old_zone.has_cloud = False
                    # Calculate new position
                    nr = pos[0] + direction[0] * drift_zones
                    nc = pos[1] + direction[1] * drift_zones
                    if 0 <= nr < self.bf.rows and 0 <= nc < self.bf.cols:
                        new_positions.append((nr, nc))
                        new_zone = self.bf.get_zone(nr, nc)
                        new_zone.has_cloud = True
                self.bf.cloud_positions = new_positions
                self.round_log.append(
                    f"Clouds drift {drift_inches}\" — now at {new_positions}"
                )

            # Apply toxic/corrosive damage to figures in cloud zones
            cloud_type = getattr(self.bf, "cloud_type", "safe")
            if cloud_type in ("toxic", "corrosive"):
                toxin_level = getattr(self.bf, "cloud_toxin_level", 0)
                for fig in self.bf.figures:
                    if not fig.is_alive:
                        continue
                    zone_obj = self.bf.get_zone(*fig.zone)
                    if getattr(zone_obj, "has_cloud", False):
                        resist = roll_d6(f"{fig.name} toxin resist").total
                        if resist <= toxin_level:
                            fig.stun_markers += 1
                            self.round_log.append(
                                f"  {fig.name} in {cloud_type} cloud — "
                                f"rolls {resist} vs toxin {toxin_level} — Stunned!"
                            )
                        else:
                            self.round_log.append(
                                f"  {fig.name} resists {cloud_type} cloud "
                                f"({resist} vs {toxin_level})"
                            )

        # Reset free escape flag for next round
        if getattr(cond, "free_escape", False):
            self._free_escape_used = False

    def _reveal_uncertain_terrain(self) -> None:
        """Check and reveal Uncertain Terrain features at end of round.

        Rules (p.137): At end of each round, for any uncertain feature within
        9" (~2 zones) of any crew member OR within 18" (~4 zones) and in LoS,
        roll D100 on the Uncertain Features table to reveal it.
        """
        from planetfall.engine.tables.battlefield_conditions import roll_uncertain_terrain
        from planetfall.engine.combat.battlefield import TerrainType

        player_figs = [
            f for f in self.bf.figures
            if f.side == FigureSide.PLAYER and f.is_alive
        ]
        if not player_figs:
            return

        to_reveal = []
        for uf_zone in list(self.bf.uncertain_features):
            for fig in player_figs:
                dist = self.bf.zone_distance(fig.zone, uf_zone)
                if dist <= 2:
                    # Within 9" (~2 zones) — auto-reveal
                    to_reveal.append(uf_zone)
                    break
                elif dist <= 4 and self.bf.check_los(fig.zone, uf_zone) != "blocked":
                    # Within 18" (~4 zones) + LoS — auto-reveal
                    to_reveal.append(uf_zone)
                    break

        for uf_zone in to_reveal:
            if uf_zone not in self.bf.uncertain_features:
                continue
            self.bf.uncertain_features.remove(uf_zone)
            result = roll_uncertain_terrain()
            zone_obj = self.bf.get_zone(*uf_zone)
            zone_obj.uncertain = False

            # Apply terrain type
            terrain_map = {
                "light_cover": TerrainType.LIGHT_COVER,
                "heavy_cover": TerrainType.HEAVY_COVER,
                "high_ground": TerrainType.HIGH_GROUND,
                "impassable": TerrainType.IMPASSABLE,
                "open": TerrainType.OPEN,
            }
            zone_obj.terrain = terrain_map.get(result["terrain"], TerrainType.OPEN)
            if result.get("difficult"):
                zone_obj.difficult = True

            self.round_log.append(
                f"Uncertain Terrain revealed at {uf_zone}: "
                f"{result['name']} (D100={result['roll']}) — {result['description']}"
            )

            # Special effects
            if result.get("spawn_contact") and self.mission_setup.lifeform_template:
                self.round_log.append(
                    f"  Contact spawned at {uf_zone}!"
                )
            if result.get("find_on_6"):
                from planetfall.engine.dice import roll_d6
                find_roll = roll_d6("Promising terrain").total
                if find_roll == 6:
                    self.round_log.append(
                        f"  Promising terrain! D6={find_roll} — bonus Post-Mission Find!"
                    )
                else:
                    self.round_log.append(
                        f"  Promising terrain: D6={find_roll} — nothing found"
                    )

    def get_result(self) -> dict:
        """Get final battle results after BATTLE_OVER."""
        outcome = check_battle_end(self.bf)
        remaining_objectives = len(self.mission_setup.objectives)
        objective_victory = remaining_objectives == 0 and self._had_objectives

        # Evacuation victory: all objectives done + all players evacuated
        evac_victory = (
            objective_victory
            and self.evacuated
            and not any(
                f for f in self.bf.figures
                if f.side == FigureSide.PLAYER and f.is_alive
            )
        )

        return {
            "victory": outcome == "player_victory" or objective_victory or evac_victory,
            "rounds_played": self.round_number,
            "enemies_killed": sum(
                1 for f in self.bf.figures
                if f.side == FigureSide.ENEMY and not f.is_alive
            ),
            "character_casualties": [
                f.name for f in self.bf.figures
                if f.side == FigureSide.PLAYER and not f.is_alive
                and f.char_class != "grunt"
                and f.name not in self.evacuated
            ],
            "grunt_casualties": sum(
                1 for f in self.bf.figures
                if f.side == FigureSide.PLAYER and not f.is_alive
                and f.char_class == "grunt"
                and f.name not in self.evacuated
            ),
            "evacuated": list(self.evacuated),
            "battle_log": self.full_log,
            "objectives_secured": self.objectives_secured,
        }

"""Mission setup dispatcher — the setup_mission() function and all per-mission-type logic."""

from __future__ import annotations

import random as _rng

from planetfall.engine.combat.battlefield import (
    Battlefield, Figure, FigureSide, TerrainType,
    generate_random_terrain, GRID_SMALL, GRID_STANDARD,
    is_impassable,
)
from planetfall.engine.dice import roll_d6
from planetfall.engine.models import GameState, MissionType

from planetfall.engine.combat.missions.base import (
    MissionSetup,
    get_or_generate_lifeform,
    _assign_zone_with_overflow,
    _create_lifeform_figure,
    _build_lifeform_info,
    _deploy_player_figures,
    _deploy_tactical_enemies,
    _deploy_slyn,
    _deploy_lifeforms,
)


def _lifeform_special_rules(profile) -> list[str]:
    """Build special_rules list from LifeformProfile fields."""
    rules = []
    if profile.partially_airborne:
        rules.append("partially_airborne")
    if profile.dodge:
        rules.append("dodge")
    if profile.unique_ability:
        rules.append(profile.unique_ability)
    return rules


def _get_sector_context(state: GameState, mission_type_str: str) -> tuple[int, int]:
    """Get (resource_level, hazard_level) from turn log for the current mission sector.

    Searches turn_log in reverse for a matching mission_type entry, then looks up
    the sector's resource and hazard levels.  Falls back to (3, 2) if not found.
    """
    resource_level = 3  # fallback
    hazard_level = 2    # fallback
    for ev in reversed(state.turn_log):
        if ev.state_changes.get("mission_type") == mission_type_str:
            sid = ev.state_changes.get("sector_id")
            if sid is not None:
                sector = state.get_sector(sid)
                if sector:
                    resource_level = sector.resource_level
                    hazard_level = sector.hazard_level
            break
    return resource_level, hazard_level


def _build_lifeform_template(profile, name: str) -> dict:
    """Build a lifeform template dict from a LifeformProfile.

    Includes all keys used by both the investigation/scouting/science spawner
    (which reads ``special_rules``) and the patrol spawner (which reads
    ``special_attack`` / ``unique_ability``).
    """
    return {
        "name": name,
        "speed": profile.speed,
        "combat_skill": profile.combat_skill,
        "toughness": profile.toughness,
        "strike_damage": profile.strike_damage,
        "armor_save": profile.armor_save,
        "kill_points": profile.kill_points,
        "dodge": profile.dodge,
        "special_rules": _lifeform_special_rules(profile),
        "special_attack": profile.special_attack,
        "unique_ability": profile.unique_ability,
    }


def _get_enemy_size_mod(condition) -> int:
    """Extract enemy_size_mod from a battlefield condition, defaulting to 0."""
    return getattr(condition, "enemy_size_mod", 0) if condition else 0


def _roll_slyn_opposition(
    state: GameState,
    setup: MissionSetup,
    battlefield,
    grid_rows: int,
    grid_cols: int,
    label: str,
    threshold: int = 4,
) -> tuple[bool, list]:
    """Roll 2D6 for Slyn opposition and deploy if triggered.

    Returns (slyn_attack, slyn_figs) — slyn_figs is empty if not a Slyn attack.
    """
    from planetfall.engine.dice import roll_nd6
    opp_roll = roll_nd6(2, f"{label} opposition")
    slyn_attack = opp_roll.total <= threshold and state.enemies.slyn.active

    if not slyn_attack:
        return False, []

    setup.enemy_type = "slyn"
    slyn_figs, slyn_info = _deploy_slyn(
        grid_rows=grid_rows, grid_cols=grid_cols,
        battlefield=battlefield,
    )
    battlefield.figures.extend(slyn_figs)
    setup.enemy_info = slyn_info
    setup.special_rules.append(
        "Slyn operate in pairs — both must be killed to destroy a pair"
    )
    return True, slyn_figs


def setup_mission(
    state: GameState,
    mission_type: MissionType,
    deployed_names: list[str],
    grunt_count: int = 0,
    enemy_type_id: str | None = None,
    bot_deploy: bool = False,
    civilian_deploy: int = 0,
    scout_at_risk: str | None = None,
    weapon_loadout: dict[str, str] | None = None,
    sector_id: int | None = None,
    condition: object = None,
) -> MissionSetup:
    """Set up a mission battlefield with all figures deployed.

    Returns a MissionSetup ready for the combat loop.
    """
    # Determine grid size based on mission type
    # Small missions (2'x2' = 6x6): scouting, science, rescue, scout_down
    # Standard missions (3'x3' = 9x9): investigation, patrol, skirmish, exploration, hunt, pitched_battle, assault, strike, delve
    SMALL_MISSIONS = {
        MissionType.SCOUTING, MissionType.SCIENCE,
        MissionType.RESCUE, MissionType.SCOUT_DOWN,
    }
    if mission_type in SMALL_MISSIONS:
        grid_rows, grid_cols = GRID_SMALL
    else:
        grid_rows, grid_cols = GRID_STANDARD

    # Look up mission sector terrain type
    sector_terrain_str: str | None = None
    _sid = sector_id
    if _sid is None:
        for ev in reversed(state.turn_log):
            s = ev.state_changes.get("sector_id")
            if s is not None:
                _sid = s
                break
    # Fall back to colony sector if no specific sector (e.g. patrol, hunt)
    if _sid is None and state.campaign_map:
        _sid = state.campaign_map.colony_sector_id
    if _sid is not None:
        sector = state.get_sector(_sid)
        if sector:
            sector_terrain_str = sector.terrain.value if sector.terrain else None

    terrain = generate_random_terrain(
        grid_rows, grid_cols,
        sector_terrain=sector_terrain_str,
    )
    battlefield = Battlefield(zones=terrain, rows=grid_rows, cols=grid_cols)

    # Deploy player figures
    player_figs = _deploy_player_figures(
        state, deployed_names, grunt_count, grid_rows, grid_cols, bot_deploy,
        weapon_loadout=weapon_loadout,
        fireteams=state.grunts.fireteams if state.grunts else None,
        grunt_upgrades=state.grunts.upgrades if state.grunts else None,
    )
    battlefield.figures.extend(player_figs)

    # Deploy civilians (basic stats, player side)
    for i in range(civilian_deploy):
        civ = Figure(
            name=f"Civilian {i + 1}",
            side=FigureSide.PLAYER,
            zone=(grid_rows - 1, grid_cols // 2),
            speed=4,
            combat_skill=0,
            toughness=3,
            weapon_name="Unarmed",
            weapon_range=0,
            weapon_shots=0,
            char_class="civilian",
        )
        battlefield.figures.append(civ)

    setup = MissionSetup(
        mission_type=mission_type,
        battlefield=battlefield,
        condition=condition,
    )

    # Apply condition: make terrain features Impassable (Hazardous Environment)
    if condition and getattr(condition, "terrain_hazards", 0) > 0:
        import random as _rng
        from planetfall.engine.combat.battlefield import TerrainType
        eligible = [
            z for row in terrain for z in row
            if z.terrain in (TerrainType.LIGHT_COVER, TerrainType.HEAVY_COVER, TerrainType.HIGH_GROUND)
        ]
        if eligible:
            chosen = _rng.sample(eligible, min(condition.terrain_hazards, len(eligible)))
            for z in chosen:
                setup.log.append(f"Hazardous Environment: zone ({z.row},{z.col}) {z.terrain.value} → Impassable")
                z.terrain = TerrainType.IMPASSABLE

    # Extract condition modifiers for use by mission setup functions
    _esm = _get_enemy_size_mod(condition)

    # Helper: scale objective placement to grid size
    mid_row = grid_rows // 2
    mid_col = grid_cols // 2

    # Mission-specific setup
    if mission_type == MissionType.INVESTIGATION:
        _setup_investigation(state, setup, battlefield, grid_rows, grid_cols, mid_row, mid_col)

    elif mission_type == MissionType.SCOUTING:
        _setup_scouting(state, setup, battlefield, grid_rows, grid_cols, mid_row, mid_col)

    elif mission_type == MissionType.EXPLORATION:
        _setup_exploration(state, setup, battlefield, grid_rows, grid_cols, mid_row, mid_col)

    elif mission_type == MissionType.SCIENCE:
        _setup_science(state, setup, battlefield, grid_rows, grid_cols, mid_row, mid_col)

    elif mission_type == MissionType.HUNT:
        _setup_hunt(state, setup, battlefield, grid_rows, grid_cols, mid_row, mid_col)

    elif mission_type == MissionType.PATROL:
        _setup_patrol(state, setup, battlefield, grid_rows, grid_cols, mid_row, mid_col)

    elif mission_type == MissionType.SKIRMISH:
        _setup_skirmish(state, setup, battlefield, enemy_type_id, grid_rows, grid_cols, mid_row, mid_col)

    elif mission_type == MissionType.RESCUE:
        _setup_rescue(state, setup, battlefield, player_figs, grid_rows, grid_cols, mid_row, mid_col)

    elif mission_type == MissionType.SCOUT_DOWN:
        _setup_scout_down(state, setup, battlefield, enemy_type_id, scout_at_risk, grid_rows, grid_cols, mid_row, mid_col)

    elif mission_type == MissionType.PITCHED_BATTLE:
        _setup_pitched_battle(state, setup, battlefield, enemy_type_id, grid_rows, grid_cols, mid_row, mid_col)

    elif mission_type == MissionType.STRIKE:
        _setup_strike(state, setup, battlefield, enemy_type_id, grid_rows, grid_cols, mid_row, mid_col)

    elif mission_type == MissionType.ASSAULT:
        _setup_assault(state, setup, battlefield, enemy_type_id, grid_rows, grid_cols, mid_row, mid_col)

    elif mission_type == MissionType.DELVE:
        _setup_delve(state, setup, battlefield, grid_rows, grid_cols, mid_row, mid_col)

    else:
        # Default: generic skirmish
        setup.enemy_type = "tactical"
        _esm = _get_enemy_size_mod(setup.condition)
        enemy_figs, enemy_info = _deploy_tactical_enemies(enemy_type_id, grid_rows=grid_rows, grid_cols=grid_cols, enemy_size_mod=_esm)
        battlefield.figures.extend(enemy_figs)
        setup.enemy_info = enemy_info
        setup.victory_conditions = ["Defeat all enemies"]

    # Place objectives on battlefield zones so they show on the map
    for obj in setup.objectives:
        r, c = obj["zone"]
        zone = battlefield.get_zone(r, c)
        # If target zone is impassable, find the nearest valid zone
        if is_impassable(zone.terrain):
            best = None
            best_dist = 999
            for dr in range(-3, 4):
                for dc in range(-3, 4):
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < grid_rows and 0 <= nc < grid_cols:
                        candidate = battlefield.get_zone(nr, nc)
                        if not is_impassable(candidate.terrain) and not candidate.has_objective:
                            d = abs(dr) + abs(dc)
                            if d < best_dist:
                                best_dist = d
                                best = (nr, nc)
            if best:
                r, c = best
                obj["zone"] = best
                zone = battlefield.get_zone(r, c)
        zone.has_objective = True
        obj_type = obj.get("type", "obj")
        label_map = {
            "resource": "RES", "discovery": "DIS", "secure": "SEC",
            "hazard": "HAZ", "sample": "SMP", "recon": "REC",
            "science": "SCI", "sweep": "SWP", "destroy": "DEM",
            "search": "SRC", "deliver": "DLV", "retrieve": "RET",
        }
        zone.objective_label = label_map.get(obj_type, "OBJ")

    # --- Apply remaining condition effects to the setup ---
    if condition:
        # Extra contacts (Heavy Scanner Signals)
        if getattr(condition, "extra_contacts", 0) > 0:
            import random as _rng
            from planetfall.engine.combat.battlefield import FigureSide
            from planetfall.engine.combat.missions.base import _assign_zone_with_overflow, Figure
            for i in range(condition.extra_contacts):
                # Place extra contact in enemy half
                r = _rng.randint(0, max(0, grid_rows // 2 - 1))
                c = _rng.randint(0, grid_cols - 1)
                fig = Figure(
                    name=f"Contact-Extra-{i + 1}", side=FigureSide.ENEMY,
                    zone=(r, c), speed=4, combat_skill=0, toughness=3,
                    weapon_name="Unknown", weapon_range=0, weapon_shots=0,
                    is_contact=True,
                )
                _assign_zone_with_overflow(battlefield, fig, r, c, grid_rows, grid_cols)
                battlefield.figures.append(fig)
                setup.log.append(f"Heavy Scanner Signals: +1 Contact marker placed")

        # Confined exits (Confined Spaces)
        if getattr(condition, "confined_exits", 0) > 0:
            import random as _rng
            edges: list[tuple[int, int]] = []
            for c in range(grid_cols):
                edges.append((0, c))
                edges.append((grid_rows - 1, c))
            for r in range(1, grid_rows - 1):
                edges.append((r, 0))
                edges.append((r, grid_cols - 1))
            exit_points = _rng.sample(edges, min(condition.confined_exits, len(edges)))
            battlefield.exit_zones = exit_points
            setup.log.append(
                f"Confined Spaces: battlefield can only be entered/exited at "
                f"{', '.join(str(z) for z in exit_points)}"
            )
            setup.special_rules.append(
                f"Confined Spaces: entry/exit only at {', '.join(str(z) for z in exit_points)}"
            )

        # Drifting clouds — place 3 cloud markers
        if getattr(condition, "clouds", 0) > 0:
            import random as _rng
            cloud_positions = []
            center_r, center_c = grid_rows // 2, grid_cols // 2
            for i in range(condition.clouds):
                # Place ~6" (1-2 zones) from center in random direction
                dr = _rng.randint(-2, 2)
                dc = _rng.randint(-2, 2)
                cr = max(0, min(grid_rows - 1, center_r + dr))
                cc = max(0, min(grid_cols - 1, center_c + dc))
                cloud_positions.append((cr, cc))
                zone = battlefield.get_zone(cr, cc)
                zone.has_cloud = True
            battlefield.cloud_positions = cloud_positions
            battlefield.cloud_type = condition.cloud_type
            battlefield.cloud_toxin_level = getattr(condition, "cloud_toxin_level", 0)
            type_label = condition.cloud_type.capitalize() if condition.cloud_type else "Safe"
            setup.log.append(f"Drifting Clouds ({type_label}): {len(cloud_positions)} cloud markers placed")
            setup.special_rules.append(
                f"Drifting Clouds ({type_label}): cannot fire through; cover within; "
                f"drift 1D6\" random direction each round"
            )

        # Uncertain terrain — place 1 uncertain feature marker
        if getattr(condition, "id", "") == "uncertain_terrain":
            import random as _rng
            from planetfall.engine.combat.battlefield import TerrainType
            # Find open zones in neutral area (not edges) for placement
            candidates = [
                (r, c) for r in range(1, grid_rows - 1) for c in range(1, grid_cols - 1)
                if battlefield.get_zone(r, c).terrain == TerrainType.OPEN
                and not battlefield.get_zone(r, c).has_objective
            ]
            if candidates:
                uf_zone = _rng.choice(candidates)
                zone = battlefield.get_zone(*uf_zone)
                zone.uncertain = True
                zone.terrain = TerrainType.LIGHT_COVER  # blocks fire until revealed
                zone.terrain_name = "Uncertain"
                battlefield.uncertain_features.append(uf_zone)
                setup.log.append(f"Uncertain Terrain: feature placed at {uf_zone}")
                setup.special_rules.append(
                    "Uncertain Terrain: cannot fire across; revealed at end of round "
                    "if within 2 zones or 4 zones + LoS"
                )

        # Add condition effects to special rules for display
        if getattr(condition, "effects_summary", None):
            for eff in condition.effects_summary:
                setup.special_rules.append(eff)

    # Always note difficult ground rules (difficult zones are always present)
    setup.special_rules.append(
        "Difficult Ground: Spd 1-3 must dash to move 1 zone; "
        "Spd 4-5 move 1 zone, cannot dash; Spd 6-8 move 1 zone, may dash 2"
    )

    return setup


# ---------------------------------------------------------------------------
# Per-mission-type setup functions
# ---------------------------------------------------------------------------

def _setup_investigation(
    state: GameState, setup: MissionSetup, battlefield: Battlefield,
    grid_rows: int, grid_cols: int, mid_row: int, mid_col: int,
) -> None:
    setup.max_rounds = 99  # no round limit — ends when squad leaves
    setup.enemy_type = "lifeform"

    # 1 Contact at center of each non-deployment edge (3 contacts)
    lf_result = get_or_generate_lifeform(state)
    profile = lf_result.profile
    contact_edges = [
        (0, mid_col),                    # top edge center
        (mid_row, 0),                    # left edge center
        (mid_row, grid_cols - 1),        # right edge center
    ]
    for i, zone in enumerate(contact_edges):
        fig = _create_lifeform_figure(profile, i + 1, zone, lifeform_name=lf_result.name)
        fig.is_contact = True
        battlefield.figures.append(fig)

    setup.enemy_info = _build_lifeform_info(
        profile, lf_result.name, "3 contacts deployed (1 per non-deploy edge)",
    )

    # Store template for spawning new contacts during enemy phase
    setup.lifeform_template = _build_lifeform_template(profile, lf_result.name)

    # 4 Discovery markers in center of each table quarter
    q_row = grid_rows // 4
    q_col = grid_cols // 4
    three_q_row = grid_rows * 3 // 4
    three_q_col = grid_cols * 3 // 4
    setup.objectives = [
        {"type": "discovery", "zone": (q_row, q_col)},
        {"type": "discovery", "zone": (q_row, three_q_col)},
        {"type": "discovery", "zone": (three_q_row, q_col)},
        {"type": "discovery", "zone": (three_q_row, three_q_col)},
    ]
    setup.victory_conditions = [
        "Investigate 4 Discovery markers and evacuate off any edge",
    ]
    setup.special_rules = [
        "Deploy up to 4 figures (any combination of characters/bots/grunts/civilians)",
        "No Slyn; no Battle Conditions",
        "Investigate: move within zone of marker, roll D6 for result",
        "Each Enemy Phase: D6 per non-deploy edge (1-3 = new Contact)",
        "Mission ends when squad leaves the table",
    ]
    setup.log.append("Investigation: 3 contacts, 4 discovery markers")


def _setup_scouting(
    state: GameState, setup: MissionSetup, battlefield: Battlefield,
    grid_rows: int, grid_cols: int, mid_row: int, mid_col: int,
) -> None:
    setup.max_rounds = 99  # no round limit — ends when squad leaves
    setup.enemy_type = "lifeform"

    # 1 contact at center of map
    center_row = grid_rows // 2
    center_col = grid_cols // 2
    lf_result = get_or_generate_lifeform(state)
    profile = lf_result.profile
    contact_fig = _create_lifeform_figure(profile, 1, (center_row, center_col), lifeform_name=lf_result.name)
    contact_fig.is_contact = True
    battlefield.figures.append(contact_fig)

    setup.enemy_info = _build_lifeform_info(
        profile, lf_result.name, "1 contact deployed (center)",
    )

    # Store template for spawning new contacts during enemy phase
    setup.lifeform_template = _build_lifeform_template(profile, lf_result.name)

    # Place 6 Recon markers in the largest terrain features
    terrain_candidates = []
    for r in range(grid_rows):
        for c in range(grid_cols):
            z = battlefield.get_zone(r, c)
            if z.terrain in (TerrainType.HEAVY_COVER, TerrainType.LIGHT_COVER, TerrainType.HIGH_GROUND):
                weight = 3 if z.terrain == TerrainType.HEAVY_COVER else (2 if z.terrain == TerrainType.HIGH_GROUND else 1)
                terrain_candidates.append((weight, r, c))
    terrain_candidates.sort(key=lambda x: -x[0])  # largest first
    recon_count = min(6, len(terrain_candidates))
    for i in range(recon_count):
        _, r, c = terrain_candidates[i]
        setup.objectives.append({"type": "recon", "zone": (r, c)})

    setup.victory_conditions = [
        f"Investigate {recon_count} Recon markers and evacuate off any edge",
    ]
    setup.special_rules = [
        "Deploy up to 2 figures (any combination)",
        "Scouts auto-recon on contact; others need D6+Savvy 5+",
        "No Slyn attack; no Battle Conditions",
        "Each Enemy Phase: D6, on 6 new Contact at random edge center",
        "Equal Aggression/Random: contact stays in place (no new spawn)",
        "Mission ends when squad leaves the table",
    ]
    setup.log.append(f"Scouting: 1 contact, {recon_count} recon markers")


def _setup_exploration(
    state: GameState, setup: MissionSetup, battlefield: Battlefield,
    grid_rows: int, grid_cols: int, mid_row: int, mid_col: int,
) -> None:
    setup.max_rounds = 99  # no round limit — ends when squad leaves

    # Find sector resource/hazard from turn log
    resource_level, hazard_level = _get_sector_context(state, "exploration")

    # Opposition: 2D6, on 2-4 = Slyn, else lifeforms (contacts)
    slyn_attack, slyn_figs = _roll_slyn_opposition(
        state, setup, battlefield, grid_rows, grid_cols, "Exploration",
    )

    if slyn_attack:
        setup.special_rules.append(
            "Slyn teleport: start of Enemy Phase, random pair moves 2D6\" random direction"
        )
        setup.special_rules.append(
            "Slyn withdraw when only 1 pair remains at end of round"
        )
        setup.log.append(
            f"Exploration: Slyn attack! {len(slyn_figs)} Slyn ({len(slyn_figs)//2} pairs)"
        )
    else:
        # Lifeform contacts equal to Hazard Level, placed near center terrain
        setup.enemy_type = "lifeform"
        contact_count = max(1, hazard_level)
        lf_result = get_or_generate_lifeform(state)
        profile = lf_result.profile

        # Find terrain features nearest to center for contact placement
        center_r, center_c = grid_rows // 2, grid_cols // 2
        terrain_near_center = []
        for r in range(grid_rows):
            for c in range(grid_cols):
                z = battlefield.get_zone(r, c)
                if z.terrain not in (TerrainType.OPEN, TerrainType.IMPASSABLE, TerrainType.IMPASSABLE_BLOCKING):
                    dist = abs(r - center_r) + abs(c - center_c)
                    terrain_near_center.append((dist, r, c))
        terrain_near_center.sort(key=lambda x: x[0])

        enemy_info = _build_lifeform_info(
            profile, lf_result.name,
            f"{contact_count} contacts deployed (Hazard Level {hazard_level})",
        )

        zone_counts: dict[tuple[int, int], int] = {}
        for i in range(contact_count):
            if terrain_near_center:
                _, r, c = terrain_near_center[i % len(terrain_near_center)]
            else:
                r, c = center_r, center_c
            zone = _assign_zone_with_overflow((r, c), zone_counts, grid_rows, grid_cols, max_per_zone=1)
            fig = _create_lifeform_figure(profile, i + 1, zone, lifeform_name=lf_result.name)
            fig.is_contact = True
            battlefield.figures.append(fig)

        setup.enemy_info = enemy_info
        setup.log.append(
            f"Exploration: {contact_count} lifeform contacts "
            f"(Hazard Level {hazard_level})"
        )

    # Objectives equal to Resource Level, distributed evenly
    obj_count = max(1, resource_level)
    for i in range(obj_count):
        row = (i * (grid_rows - 2)) // max(1, obj_count - 1) + 1 if obj_count > 1 else mid_row
        col = (i * (grid_cols - 1)) // max(1, obj_count) + 1
        row = min(row, grid_rows - 2)
        col = min(col, grid_cols - 1)
        setup.objectives.append({"type": "resource", "zone": (row, col)})

    setup.victory_conditions = [
        f"Sweep {obj_count} objective markers (Resource Level {resource_level})",
        "End round in zone with no enemies closer to secure",
    ]
    setup.special_rules = [
        f"Sector Resource Level: {resource_level}  Hazard Level: {hazard_level}",
        "Sweep objective: end round in zone, no enemies closer",
        "One objective secured per side per round",
        "Mission ends when squad leaves the table",
    ]
    if slyn_attack:
        setup.special_rules.append(
            "Slyn: one pair moves toward nearest objective each Enemy Phase"
        )


def _setup_science(
    state: GameState, setup: MissionSetup, battlefield: Battlefield,
    grid_rows: int, grid_cols: int, mid_row: int, mid_col: int,
) -> None:
    setup.max_rounds = 99  # no round limit — ends when squad leaves
    setup.enemy_type = "lifeform"

    # 1 contact at center of map
    center_row = grid_rows // 2
    center_col = grid_cols // 2
    lf_result = get_or_generate_lifeform(state)
    profile = lf_result.profile
    contact_fig = _create_lifeform_figure(profile, 1, (center_row, center_col), lifeform_name=lf_result.name)
    contact_fig.is_contact = True
    battlefield.figures.append(contact_fig)

    setup.enemy_info = _build_lifeform_info(
        profile, lf_result.name, "1 contact deployed (center)",
    )

    # Store template for spawning new contacts during enemy phase
    setup.lifeform_template = _build_lifeform_template(profile, lf_result.name)

    # Place 6 Science markers in largest terrain features
    terrain_candidates = []
    for r in range(grid_rows):
        for c in range(grid_cols):
            z = battlefield.get_zone(r, c)
            if z.terrain in (TerrainType.HEAVY_COVER, TerrainType.LIGHT_COVER, TerrainType.HIGH_GROUND):
                weight = 3 if z.terrain == TerrainType.HEAVY_COVER else (2 if z.terrain == TerrainType.HIGH_GROUND else 1)
                terrain_candidates.append((weight, r, c))
    terrain_candidates.sort(key=lambda x: -x[0])
    science_count = min(6, len(terrain_candidates))
    for i in range(science_count):
        _, r, c = terrain_candidates[i]
        setup.objectives.append({"type": "science", "zone": (r, c)})

    # Determine hazard level for contact spawning
    _, hazard_level = _get_sector_context(state, "science")

    setup.victory_conditions = [
        f"Collect samples from {science_count} Science markers and evacuate",
    ]
    setup.special_rules = [
        "Deploy up to 2 figures (any combination)",
        "Scientists auto-collect on contact; others need D6+Savvy 5+",
        "Failed collection: sample is ruined",
        "No Slyn; no Battle Conditions",
        f"Each Enemy Phase: D6 (2D6 if Hazard {hazard_level}+4) on 6 new Contact at random edge",
        "Equal Aggression/Random: contact stays in place (no new spawn)",
        "Mission ends when squad leaves the table",
    ]
    setup.log.append(f"Science: 1 contact, {science_count} science markers")


def _setup_hunt(
    state: GameState, setup: MissionSetup, battlefield: Battlefield,
    grid_rows: int, grid_cols: int, mid_row: int, mid_col: int,
) -> None:
    setup.max_rounds = 99  # no round limit — ends when squad leaves
    setup.enemy_type = "lifeform"  # unless Slyn

    # Opposition: 2D6, on 2-4 = Slyn; otherwise hunt lifeforms
    slyn_attack, slyn_figs = _roll_slyn_opposition(
        state, setup, battlefield, grid_rows, grid_cols, "Hunt",
    )

    if slyn_attack:
        setup.victory_conditions = [
            "Fight off the Slyn and evacuate",
        ]
        setup.log.append(
            f"Hunt: Slyn attack! {len(slyn_figs)} Slyn ({len(slyn_figs)//2} pairs) — no specimens"
        )
    else:
        # Contacts placed in terrain features with LoS to player, D6 per feature
        # At least 3 contacts guaranteed
        lf_result = get_or_generate_lifeform(state)
        profile = lf_result.profile
        terrain_features = []
        for r in range(grid_rows):
            for c in range(grid_cols):
                z = battlefield.get_zone(r, c)
                if z.terrain not in (TerrainType.OPEN, TerrainType.IMPASSABLE, TerrainType.IMPASSABLE_BLOCKING):
                    terrain_features.append((r, c))

        # Roll D6 per terrain feature; 6 = contact
        contact_zones = []
        for r, c in terrain_features:
            spot_roll = roll_d6(f"Spot terrain ({r},{c})")
            if spot_roll.total == 6:
                contact_zones.append((r, c))

        # Minimum 3 contacts
        remaining_features = [z for z in terrain_features if z not in contact_zones]
        import random as _rng_hunt
        _rng_hunt.shuffle(remaining_features)
        while len(contact_zones) < 3 and remaining_features:
            contact_zones.append(remaining_features.pop())

        contact_count = len(contact_zones)
        setup.enemy_info = _build_lifeform_info(
            profile, lf_result.name, f"{contact_count} contacts deployed",
        )

        for i, (r, c) in enumerate(contact_zones):
            fig = _create_lifeform_figure(profile, i + 1, (r, c), lifeform_name=lf_result.name)
            fig.is_contact = True
            battlefield.figures.append(fig)

        setup.victory_conditions = [
            "Kill 2 lifeforms, collect specimens (action in base contact), evacuate",
        ]
        setup.log.append(f"Hunt: {contact_count} lifeform contacts in terrain")

    setup.special_rules = [
        "Deploy up to 6 figures (any combination)",
        "Kill 2 lifeforms, then action in base contact to collect specimen",
        "Collected specimens auto-transmitted to colony",
        "Mission ends when squad leaves the table",
    ]
    if slyn_attack:
        setup.special_rules = [
            "Slyn attack! No specimens can be collected",
            "Fight off the Slyn and evacuate",
            "Mission ends when squad leaves the table",
        ]


def _setup_patrol(
    state: GameState, setup: MissionSetup, battlefield: Battlefield,
    grid_rows: int, grid_cols: int, mid_row: int, mid_col: int,
) -> None:
    setup.max_rounds = 99  # no round limit — ends when squad leaves

    # Opposition: 2D6, on 2-4 = Slyn; on 5-6 = animals (contacts)
    slyn_attack, slyn_figs = _roll_slyn_opposition(
        state, setup, battlefield, grid_rows, grid_cols, "Patrol",
    )

    if slyn_attack:
        setup.log.append(
            f"Patrol: Slyn attack! {len(slyn_figs)} Slyn ({len(slyn_figs)//2} pairs)"
        )
    else:
        # Animals — no contacts initially, spawn at end of each round
        setup.enemy_type = "lifeform"
        lf_result = get_or_generate_lifeform(state)
        profile = lf_result.profile
        setup.lifeform_template = _build_lifeform_template(profile, lf_result.name)
        setup.enemy_info = _build_lifeform_info(
            profile, lf_result.name, "contacts spawn each round",
        )
        setup.log.append(f"Patrol: wildlife ({lf_result.name}) — contacts appear each round")

    # 3 objectives at high ground or cover terrain in the central area (rows 2-5, cols 2-6)
    cover_terrains = {
        TerrainType.LIGHT_COVER, TerrainType.HEAVY_COVER, TerrainType.HIGH_GROUND,
    }
    center_r, center_c = grid_rows // 2, grid_cols // 2
    obj_candidates = []
    for r in range(2, min(6, grid_rows)):
        for c in range(2, min(7, grid_cols)):
            z = battlefield.get_zone(r, c)
            if z.terrain in cover_terrains:
                dist = abs(r - center_r) + abs(c - center_c)
                obj_candidates.append((dist, r, c))
    obj_candidates.sort(key=lambda x: x[0])
    obj_count = min(3, len(obj_candidates))
    for i in range(obj_count):
        _, r, c = obj_candidates[i]
        setup.objectives.append({"type": "secure", "zone": (r, c)})
    # Fallback: expand to any non-open/non-impassable terrain nearest center
    if len(setup.objectives) < 3:
        used = {obj["zone"] for obj in setup.objectives}
        fallback = []
        for r in range(grid_rows):
            for c in range(grid_cols):
                if (r, c) in used:
                    continue
                z = battlefield.get_zone(r, c)
                if z.terrain not in (TerrainType.OPEN, TerrainType.IMPASSABLE,
                                     TerrainType.IMPASSABLE_BLOCKING):
                    dist = abs(r - center_r) + abs(c - center_c)
                    fallback.append((dist, r, c))
        fallback.sort(key=lambda x: x[0])
        for dist, r, c in fallback:
            if len(setup.objectives) >= 3:
                break
            setup.objectives.append({"type": "secure", "zone": (r, c)})
    # Final fallback if still not enough
    while len(setup.objectives) < 3:
        setup.objectives.append({"type": "secure", "zone": (mid_row, len(setup.objectives))})

    setup.victory_conditions = [
        "Clear all 3 objectives (figure within zone, no enemies within zone)",
    ]
    setup.special_rules = [
        "Deploy 2 characters + 1 fireteam of up to 4 grunts (6 total)",
        "Objectives cleared when figure in zone with no enemies in zone",
        "Can clear multiple objectives in same round",
        "Slyn/animals ignore objectives",
        "Mission ends when squad leaves the table",
    ]
    if not slyn_attack:
        setup.special_rules.append(
            "End of each round: 1 Contact at random edge (not player entry edge)"
        )


def _setup_skirmish(
    state: GameState, setup: MissionSetup, battlefield: Battlefield,
    enemy_type_id: str | None,
    grid_rows: int, grid_cols: int, mid_row: int, mid_col: int,
) -> None:
    setup.max_rounds = 99  # no round limit — ends when squad leaves
    setup.enemy_type = "tactical"
    _esm = _get_enemy_size_mod(setup.condition)
    enemy_figs, enemy_info = _deploy_tactical_enemies(
        enemy_type_id, grid_rows=grid_rows, grid_cols=grid_cols, enemy_size_mod=_esm,
    )
    # Deploy enemies in terrain near enemy edge
    terrain_zones = [
        (r, c) for r in range(min(3, grid_rows // 3))
        for c in range(grid_cols)
        if battlefield.get_zone(r, c).terrain
        not in (TerrainType.OPEN, TerrainType.IMPASSABLE, TerrainType.IMPASSABLE_BLOCKING)
    ]
    if not terrain_zones:
        terrain_zones = [(0, c) for c in range(grid_cols)]
    for i, fig in enumerate(enemy_figs):
        zone = terrain_zones[i % len(terrain_zones)]
        fig.zone = zone
        fig.is_contact = False  # enemies are known
    battlefield.figures.extend(enemy_figs)
    setup.enemy_info = enemy_info

    # 2 objectives from Skirmish Objective table (D6 each)
    import random as _sk_rng
    obj_types = ["secure", "sweep", "destroy", "search", "deliver", "retrieve"]
    for _ in range(2):
        obj_type_roll = roll_d6("Skirmish objective type")
        obj_type = obj_types[obj_type_roll.total - 1]
        # Place ~1-2 zones from center
        offset_r = _sk_rng.randint(-1, 1)
        offset_c = _sk_rng.randint(-1, 1)
        obj_r = max(1, min(grid_rows - 2, mid_row + offset_r))
        obj_c = max(1, min(grid_cols - 2, mid_col + offset_c))
        setup.objectives.append({"type": obj_type, "zone": (obj_r, obj_c)})

    setup.victory_conditions = [
        "Complete both skirmish objectives and evacuate",
    ]
    setup.special_rules = [
        "Deploy 4 characters + 1 fireteam of 4 grunts (8 total)",
        "No Slyn interference",
        "Enemies ignore objectives — focus on killing squad",
        "End of each round: D6 (+1D6 per completed objective), 6 = reinforcement at random edge",
        "Two 6s = regular + specialist; Three 6s = regular + specialist + leader",
        "Mission ends when squad leaves the table",
    ]
    setup.log.append(f"Skirmish: {len(enemy_figs)} tactical enemies, 2 objectives")


def _setup_rescue(
    state: GameState, setup: MissionSetup, battlefield: Battlefield,
    player_figs: list[Figure],
    grid_rows: int, grid_cols: int, mid_row: int, mid_col: int,
) -> None:
    setup.max_rounds = 99  # no round limit — ends when all leave/casualty
    setup.enemy_type = "lifeform"
    # Rescue uses lifeforms (animals), 2 contacts at center of each edge
    edge_zones = [
        (0, mid_col), (0, max(0, mid_col - 1)),                    # top edge
        (grid_rows - 1, mid_col), (grid_rows - 1, max(0, mid_col - 1)),  # bottom edge
        (mid_row, 0), (max(0, mid_row - 1), 0),                    # left edge
        (mid_row, grid_cols - 1), (max(0, mid_row - 1), grid_cols - 1),  # right edge
    ]
    result = get_or_generate_lifeform(state)
    profile = result.profile
    info = _build_lifeform_info(profile, result.name, "8 contacts deployed (2 per edge)")

    for i, zone in enumerate(edge_zones):
        fig = _create_lifeform_figure(profile, i + 1, zone, lifeform_name=result.name)
        fig.is_contact = True
        battlefield.figures.append(fig)
    setup.enemy_info = info

    # 3 colonist NPCs at center
    for i in range(3):
        col = max(0, mid_col - 1 + i) if mid_col > 0 else i
        col = min(col, grid_cols - 1)
        colonist = Figure(
            name=f"Colonist {i + 1}",
            side=FigureSide.PLAYER,
            zone=(mid_row, col),
            speed=4, combat_skill=0, toughness=3,
            melee_damage=0, armor_save=0, kill_points=0,
            panic_range=0,
            weapon_name="Unarmed", weapon_range=0,
            weapon_shots=0, weapon_damage=0,
            char_class="colonist",
        )
        battlefield.figures.append(colonist)

    # Player deploys near center (within 3" ≈ center zone)
    for fig in player_figs:
        fig.zone = (mid_row, mid_col)

    setup.victory_conditions = [
        "Save colonists by escorting them off any edge",
        "Colonist is saved if within 3\" of squad member at exit",
    ]
    setup.defeat_conditions = [
        "Lose 1 Colony Morale per colonist not saved",
    ]
    setup.special_rules = [
        "3 colonists at center (civvy stats, unarmed, act as squad)",
        "End of each round: roll D6 per edge, on 6 new Contact appears",
        "Colonist exiting alone: D6, 5-6 = saved, else killed",
        "Squad casualties do not affect Colony Morale",
    ]
    setup.log.append(f"Rescue: 8 lifeform contacts, 3 colonists to save")


def _setup_scout_down(
    state: GameState, setup: MissionSetup, battlefield: Battlefield,
    enemy_type_id: str | None, scout_at_risk: str | None,
    grid_rows: int, grid_cols: int, mid_row: int, mid_col: int,
) -> None:
    setup.max_rounds = 99  # no round limit — ends when all leave/casualty
    setup.enemy_type = "tactical"

    # Determine scout name and profile
    scout_label = scout_at_risk or "Downed Scout"
    # Check if scout is on roster for profile
    roster_char = None
    if scout_at_risk:
        roster_char = next(
            (c for c in state.characters if c.name == scout_at_risk), None,
        )

    # Place scout at center of map
    center_row = grid_rows // 2
    center_col = grid_cols // 2
    if roster_char:
        # Use roster scout's actual profile
        from planetfall.engine.models import get_weapon_by_name
        weapon_name = "Scout Pistol"
        weapon_range = 8
        weapon_shots = 1
        weapon_damage = 0
        weapon_traits: list[str] = []
        for eq in roster_char.equipment:
            wpn = get_weapon_by_name(eq)
            if wpn:
                weapon_name = wpn.name
                weapon_range = wpn.range_inches
                weapon_shots = wpn.shots
                weapon_damage = wpn.damage_bonus
                weapon_traits = list(wpn.traits)
                break
        scout_fig = Figure(
            name=scout_label,
            side=FigureSide.PLAYER,
            zone=(center_row, center_col),
            speed=roster_char.speed,
            combat_skill=roster_char.combat_skill,
            toughness=roster_char.toughness,
            reactions=roster_char.reactions,
            savvy=roster_char.savvy,
            weapon_name=weapon_name,
            weapon_range=weapon_range,
            weapon_shots=weapon_shots,
            weapon_damage=weapon_damage,
            weapon_traits=weapon_traits,
            char_class="scout",
        )
    else:
        # Unknown scout: base profile + scout pistol
        scout_fig = Figure(
            name=scout_label,
            side=FigureSide.PLAYER,
            zone=(center_row, center_col),
            speed=4,
            combat_skill=0,
            toughness=3,
            reactions=1,
            weapon_name="Scout Pistol",
            weapon_range=8,
            weapon_shots=1,
            weapon_damage=0,
            char_class="scout",
        )
    # Mark scout as injured (move OR act, not both) and undetected
    scout_fig.special_rules = ["injured_scout", "undetected"]
    battlefield.figures.append(scout_fig)

    # Opposition: 2D6, on 2-3 Slyn attack; otherwise tactical enemies
    slyn_attack, slyn_figs = _roll_slyn_opposition(
        state, setup, battlefield, grid_rows, grid_cols, "Scout Down", threshold=3,
    )

    if slyn_attack:
        setup.log.append(
            f"Scout Down: Slyn attack! {len(slyn_figs)} Slyn ({len(slyn_figs)//2} pairs)"
        )
    else:
        _esm = _get_enemy_size_mod(setup.condition)
        enemy_figs, enemy_info = _deploy_tactical_enemies(
            enemy_type_id, grid_rows=grid_rows, grid_cols=grid_cols, enemy_size_mod=_esm,
        )
        # Divide into 3 groups along enemy edge (row 0)
        group_size = max(1, len(enemy_figs) // 3)
        col_step = max(1, grid_cols // 3)
        for i, fig in enumerate(enemy_figs):
            group_idx = min(i // group_size, 2)  # 0, 1, or 2
            col = group_idx * col_step + (col_step // 2)
            col = min(col, grid_cols - 1)
            fig.zone = (0, col)
            fig.is_contact = False  # enemies are known
        battlefield.figures.extend(enemy_figs)
        setup.enemy_info = enemy_info
        setup.log.append(
            f"Scout Down: {len(enemy_figs)} tactical enemies in 3 groups"
        )

    setup.victory_conditions = [
        f"Rescue {scout_label} off any battlefield edge",
    ]
    setup.defeat_conditions = [
        f"{scout_label} is killed",
    ]
    setup.special_rules = [
        f"{scout_label} is injured: can move OR act each round, not both",
        f"{scout_label} begins undetected — enemy ignores until detected",
        "Scout detected if: fires weapon, spotted out of cover, or moves >1 zone",
        "End of each round: D6, on 6 enemy reinforcement at enemy edge center",
        "Squad casualties do not affect Colony Morale",
    ]


def _setup_pitched_battle(
    state: GameState, setup: MissionSetup, battlefield: Battlefield,
    enemy_type_id: str | None,
    grid_rows: int, grid_cols: int, mid_row: int, mid_col: int,
) -> None:
    setup.max_rounds = 99  # no round limit — ends when all enemies killed/panicked
    setup.enemy_type = "tactical"

    # Two enemy forces, each generated separately
    # First force: reduce count by 1; Second force: increase by 1
    _esm = _get_enemy_size_mod(setup.condition)
    enemy_figs, enemy_info = _deploy_tactical_enemies(
        enemy_type_id, extra_enemies=-1, grid_rows=grid_rows, grid_cols=grid_cols, enemy_size_mod=_esm,
    )
    enemy_figs2, enemy_info2 = _deploy_tactical_enemies(
        enemy_type_id, extra_enemies=1, grid_rows=grid_rows, grid_cols=grid_cols, enemy_size_mod=_esm,
    )

    # Rename second group for clarity
    for i, fig in enumerate(enemy_figs2):
        fig.name = f"Force B {i+1}"

    # Both forces arrive from enemy edge in round 1, at 3 markers
    col_step = max(1, grid_cols // 3)
    marker_cols = [col_step // 2, col_step + col_step // 2, 2 * col_step + col_step // 2]
    import random as _pb_rng
    _pb_rng.shuffle(marker_cols)

    # Force A enters round 1 at first marker
    for fig in enemy_figs:
        fig.zone = (0, min(marker_cols[0], grid_cols - 1))
        fig.is_contact = False
    # Force B enters round 2 — place at second marker initially
    for fig in enemy_figs2:
        fig.zone = (0, min(marker_cols[1], grid_cols - 1))
        fig.is_contact = False

    battlefield.figures.extend(enemy_figs)
    battlefield.figures.extend(enemy_figs2)
    setup.enemy_info = enemy_info + [""] + ["Force B:"] + enemy_info2

    setup.victory_conditions = [
        "Kill or drive off every enemy",
    ]
    setup.defeat_conditions = [
        "Squad wiped out — roll on Campaign Consequences table",
    ]
    setup.special_rules = [
        "Deploy up to 4 characters + up to 8 grunts in 2 fireteams (12 total)",
        "No Slyn, no Battle Conditions",
        "Force A arrives enemy edge round 1; Force B arrives round 2",
        "Mission ends when all enemies killed or panicked, or squad eliminated",
    ]
    setup.log.append(
        f"Pitched Battle: {len(enemy_figs) + len(enemy_figs2)} total enemies (2 forces)"
    )


def _setup_strike(
    state: GameState, setup: MissionSetup, battlefield: Battlefield,
    enemy_type_id: str | None,
    grid_rows: int, grid_cols: int, mid_row: int, mid_col: int,
) -> None:
    setup.max_rounds = 99  # no round limit
    setup.enemy_type = "tactical"
    _esm = _get_enemy_size_mod(setup.condition)
    enemy_figs, enemy_info = _deploy_tactical_enemies(
        enemy_type_id, extra_enemies=2, grid_rows=grid_rows, grid_cols=grid_cols, enemy_size_mod=_esm,
    )

    # Boss/Leader at center, 1/3 within 1 zone of center, rest in pairs spread out
    center_r, center_c = grid_rows // 2, grid_cols // 2
    leader_fig = next((f for f in enemy_figs if f.is_leader), None)
    if leader_fig:
        leader_fig.zone = (center_r, center_c)

    # Split remaining: 1/3 near center, rest spread out
    non_leaders = [f for f in enemy_figs if not f.is_leader]
    third = max(1, len(non_leaders) // 3)
    for i, fig in enumerate(non_leaders):
        if i < third:
            # Near center (within 1 zone)
            import random as _st_rng
            fig.zone = (
                max(0, min(grid_rows - 1, center_r + _st_rng.randint(-1, 1))),
                max(0, min(grid_cols - 1, center_c + _st_rng.randint(-1, 1))),
            )
        else:
            # Spread out from center (2-3 zones away)
            import random as _st_rng2
            dist = _st_rng2.randint(2, 3)
            angle_r = _st_rng2.choice([-1, 0, 1])
            angle_c = _st_rng2.choice([-1, 0, 1])
            fig.zone = (
                max(0, min(grid_rows - 1, center_r + angle_r * dist)),
                max(0, min(grid_cols - 1, center_c + angle_c * dist)),
            )
        fig.is_contact = False
    battlefield.figures.extend(enemy_figs)
    setup.enemy_info = enemy_info

    setup.victory_conditions = [
        "Defeat the Boss/Leader and secure their data, then evacuate",
    ]
    setup.special_rules = [
        "Deploy up to 6 characters + 4 grunts in 1 fireteam (10 total)",
        "No Slyn interference",
        "Undetected: squad members that only move (no actions) are undetected",
        "Enemy fights defensively — stays in cover, fires when in range",
        "Enemy ignores undetected squad members",
        "If Boss/Leader killed: nearest enemy moves to collect data and escape",
        "Mission ends when squad leaves or all enemies defeated",
    ]
    setup.log.append(f"Strike: {len(enemy_figs)} enemies (Boss/Leader at center)")


def _setup_assault(
    state: GameState, setup: MissionSetup, battlefield: Battlefield,
    enemy_type_id: str | None,
    grid_rows: int, grid_cols: int, mid_row: int, mid_col: int,
) -> None:
    setup.max_rounds = 99  # no round limit
    setup.enemy_type = "tactical"

    # Max enemy strength + 2 regulars + 2 specialists + 1 leader
    _esm = _get_enemy_size_mod(setup.condition)
    enemy_figs, enemy_info = _deploy_tactical_enemies(
        enemy_type_id, extra_enemies=5, grid_rows=grid_rows, grid_cols=grid_cols, enemy_size_mod=_esm,
    )

    # Deploy evenly throughout central 12x12" area (≈ center 3x3 zones)
    center_r, center_c = grid_rows // 2, grid_cols // 2
    import random as _as_rng
    center_zones = [
        (r, c)
        for r in range(max(0, center_r - 1), min(grid_rows, center_r + 2))
        for c in range(max(0, center_c - 1), min(grid_cols, center_c + 2))
    ]
    for i, fig in enumerate(enemy_figs):
        fig.zone = center_zones[i % len(center_zones)]
        fig.is_contact = False  # known defenders
    battlefield.figures.extend(enemy_figs)
    setup.enemy_info = enemy_info

    setup.victory_conditions = [
        "Kill or drive off every enemy to destroy the Strongpoint",
    ]
    setup.defeat_conditions = [
        "Retreat/defeat: enemy restored to full strength, expands to adjacent sector",
    ]
    setup.special_rules = [
        "Deploy up to 6 characters + 8 grunts in 2 fireteams (14 total)",
        "No Slyn, no Battle Conditions",
        "All enemy Panic ranges reduced by 1 (defending home turf)",
        "Round 1: enemies not ready unless they had LoS to a firing/exposed crew",
        "Round 2+: all enemies ready and fight normally",
        "Enemy fights defensively — stays in cover and fires",
        "End of each round: D6, on 6 random enemy gains +1 KP",
    ]
    setup.log.append(f"Assault: {len(enemy_figs)} enemies (max strength, defensive)")


def _setup_delve(
    state: GameState, setup: MissionSetup, battlefield: Battlefield,
    grid_rows: int, grid_cols: int, mid_row: int, mid_col: int,
) -> None:
    setup.max_rounds = 99  # no round limit — ends when squad leaves
    setup.enemy_type = "delve_hazard"

    # No initial enemies — Delve Hazards spawn in round 1 enemy phase
    setup.enemy_info = [
        "Delve Hazards — no initial enemies",
        "  4 Hazard markers placed in round 1 (1 per table quarter)",
        "  Revealed when crew within 1 zone + LoS",
        "  Result: 1-2 Sleeper, 3-4 Trap, 5-6 Environmental hazard",
    ]

    # 4 Delve Device markers, 1 in center of each table quarter
    q_row = grid_rows // 4
    q_col = grid_cols // 4
    three_q_row = grid_rows * 3 // 4
    three_q_col = grid_cols * 3 // 4
    setup.objectives = [
        {"type": "device", "zone": (q_row, q_col)},
        {"type": "device", "zone": (q_row, three_q_col)},
        {"type": "device", "zone": (three_q_row, q_col)},
        {"type": "device", "zone": (three_q_row, three_q_col)},
    ]

    setup.victory_conditions = [
        "Activate 3 of 4 Delve Devices to reveal Artifact location",
        "Collect Artifact and evacuate via entrance or discovered exit",
    ]
    setup.defeat_conditions = [
        "Squad eliminated before retrieving Artifact",
    ]
    setup.special_rules = [
        "Deploy up to 6 figures (characters only, no grunts)",
        "No Battle Conditions or Uncertain Features",
        "Round 1: 4 Delve Hazard markers placed (1 per quarter)",
        "Hazards move 3\" random direction each Enemy Phase (round 2+)",
        "Hazard revealed within 1 zone + LoS: D6 (1-2 Sleeper, 3-4 Trap, 5-6 Environmental)",
        "Maintain 4 hazards: if <4, one spawns at center each Enemy Phase",
        "Activate Delve Device: action in base contact, roll D6 for activation type",
        "After 3 activations: Artifact placed randomly near center",
        "Exit via entrance point or discovered exit (end of round 1)",
    ]
    setup.log.append("Delve: 4 Delve Devices, hazard-based opposition")

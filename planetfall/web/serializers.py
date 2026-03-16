"""JSON serializers for web frontend — convert game state and display data to dicts."""

from __future__ import annotations

from typing import Any


def serialize_events(events: list) -> list[dict]:
    """Serialize TurnEvent list to JSON-ready dicts."""
    result = []
    for e in events:
        d: dict[str, Any] = {
            "event_type": e.event_type.value,
            "description": e.description,
            "step": e.step,
        }
        if e.dice_rolls:
            d["dice_rolls"] = [
                {"dice_type": r.dice_type, "values": r.values,
                 "total": r.total, "label": r.label}
                for r in e.dice_rolls
            ]
        if e.state_changes:
            d["state_changes"] = e.state_changes
        result.append(d)
    return result


def serialize_colony_status(state: Any) -> dict:
    """Serialize colony status dashboard data."""
    colony = state.colony
    res = colony.resources
    data = {
        "colony_name": colony.name,
        "turn": state.current_turn,
        "morale": colony.morale,
        "integrity": colony.integrity,
        "defenses": colony.defenses,
        "resources": {
            "build_points": res.build_points,
            "research_points": res.research_points,
            "raw_materials": res.raw_materials,
            "augmentation_points": res.augmentation_points,
            "story_points": res.story_points,
        },
        "grunts": state.grunts.count,
        "bot_operational": state.grunts.bot_operational,
        "roster_size": len(state.characters),
        "roster_max": 8,
        "agenda": state.settings.colonization_agenda.value,
        "settings": {
            "narrative_disabled": state.settings.narrative_disabled,
        },
    }

    # Research — full tech tree
    try:
        tech_tree = serialize_tech_tree(state)
        data["tech_tree"] = tech_tree["theories"]
    except Exception:
        data["tech_tree"] = []

    # Buildings — built + available
    data["buildings_built"] = [
        {"name": b.name, "effects": b.effects, "built_turn": b.built_turn} for b in colony.buildings
    ]
    try:
        data["buildings_available"] = serialize_buildings(state)
    except Exception:
        data["buildings_available"] = []

    return data


def serialize_tech_tree(state: Any) -> dict:
    """Serialize the full tech tree for the research modal."""
    from planetfall.engine.campaign.research import THEORIES, APPLICATIONS

    unlocked_apps = set(state.tech_tree.unlocked_applications)
    invested_theories = state.tech_tree.theories  # dict[str, Theory]

    theories = []
    for tid, tdef in THEORIES.items():
        theory_state = invested_theories.get(tid)
        invested = theory_state.invested_rp if theory_state else 0
        completed = invested >= tdef.rp_cost

        # Check if prerequisite is met
        prereq_met = True
        if tdef.prerequisite:
            prereq_state = invested_theories.get(tdef.prerequisite)
            prereq_def = THEORIES.get(tdef.prerequisite)
            if not prereq_state or not prereq_def:
                prereq_met = False
            else:
                prereq_met = prereq_state.invested_rp >= prereq_def.rp_cost

        # Build applications list
        apps = []
        for app_id in tdef.applications:
            adef = APPLICATIONS.get(app_id)
            if adef:
                apps.append({
                    "id": app_id,
                    "name": adef.name,
                    "type": adef.app_type,
                    "description": adef.description,
                    "unlocked": app_id in unlocked_apps,
                })

        theories.append({
            "id": tid,
            "name": tdef.name,
            "rp_cost": tdef.rp_cost,
            "app_cost": tdef.app_cost,
            "invested": invested,
            "completed": completed,
            "prerequisite": tdef.prerequisite,
            "prerequisite_name": THEORIES[tdef.prerequisite].name if tdef.prerequisite else None,
            "prerequisite_met": prereq_met,
            "is_secondary": bool(tdef.prerequisite),
            "applications": apps,
        })

    return {"theories": theories}


def serialize_buildings(state: Any) -> list[dict]:
    """Serialize available buildings for the buildings modal."""
    from planetfall.engine.campaign.buildings import BUILDINGS, get_available_buildings, get_construction_progress

    available = get_available_buildings(state)
    available_ids = {b.id for b in available}
    progress = get_construction_progress(state)
    built_names = {b.name for b in state.colony.buildings}

    result = []
    for bid, bdef in BUILDINGS.items():
        built = bdef.name in built_names
        avail = bid in available_ids
        locked = not built and not avail

        # Determine prerequisite label
        prereq_label = ""
        if bdef.prerequisite:
            from planetfall.engine.campaign.research import APPLICATIONS
            adef = APPLICATIONS.get(bdef.prerequisite)
            prereq_label = adef.name if adef else bdef.prerequisite

        result.append({
            "id": bid,
            "name": bdef.name,
            "bp_cost": bdef.bp_cost,
            "description": bdef.description,
            "is_milestone": bdef.is_milestone,
            "prerequisite": prereq_label,
            "built": built,
            "available": avail,
            "locked": locked,
            "invested_bp": progress.get(bid, 0),
        })

    return result


def serialize_map(state: Any) -> dict:
    """Serialize campaign map for web rendering."""
    sectors = []
    colony_id = state.campaign_map.colony_sector_id
    for s in state.campaign_map.sectors:
        is_known = s.status.value != "unexplored"
        sectors.append({
            "sector_id": s.sector_id,
            "status": s.status.value,
            "terrain": s.terrain.value if hasattr(s.terrain, 'value') else s.terrain,
            "name": s.name if is_known else "",
            "resource_level": s.resource_level if is_known else 0,
            "hazard_level": s.hazard_level if is_known else 0,
            "enemy_occupied_by": s.enemy_occupied_by,
            "has_ancient_sign": s.has_ancient_sign,
            "has_ancient_site": s.has_ancient_site,
            "has_investigation_site": s.has_investigation_site,  # visible from start
            "qualities": [q.value for q in s.qualities] if is_known else [],
            "is_colony": s.sector_id == colony_id,
        })
    return {
        "sectors": sectors,
        "colony_sector_id": colony_id,
        "cols": 6,
        "rows": (len(sectors) + 5) // 6,
    }


def serialize_roster(state: Any) -> dict:
    """Serialize character roster, including base stats for bonus display."""
    from planetfall.engine.models import STARTING_PROFILES

    chars = []
    for c in state.characters:
        # Base stats from class profile
        base = STARTING_PROFILES.get(c.char_class)
        # Compute stat bonuses (current - base)
        stat_bonuses = {}
        for stat in ("reactions", "speed", "combat_skill", "toughness", "savvy"):
            base_val = getattr(base, stat, 0) if base else 0
            curr_val = getattr(c, stat, 0)
            diff = curr_val - base_val
            if diff != 0:
                stat_bonuses[stat] = diff

        chars.append({
            "name": c.name,
            "char_class": c.char_class.value,
            "reactions": c.reactions,
            "speed": c.speed,
            "combat_skill": c.combat_skill,
            "toughness": c.toughness,
            "savvy": c.savvy,
            "stat_bonuses": stat_bonuses,
            "xp": c.xp,
            "kill_points": c.kill_points,
            "level": c.level,
            "loyalty": c.loyalty.value,
            "equipment": c.equipment,
            "sick_bay_turns": c.sick_bay_turns,
            "title": c.title,
            "role": c.role,
            "upgrades": c.upgrades,
            "narrative": c.narrative_background,
            "motivation": c.background_motivation,
            "prior_experience": c.background_prior_experience,
        })
    return {"characters": chars}


def serialize_character_backgrounds(state: Any) -> dict:
    """Serialize character background data."""
    chars = []
    for c in state.characters:
        chars.append({
            "name": c.name,
            "char_class": c.char_class.value,
            "title": c.title,
            "role": c.role,
            "motivation": c.background_motivation,
            "prior_experience": c.background_prior_experience,
            "notable_events": c.background_notable_events,
            "narrative": c.narrative_background,
        })
    return {"characters": chars}


def serialize_battlefield(bf: Any, **kwargs: Any) -> dict:
    """Serialize battlefield state for web rendering.

    Accepts same kwargs as cli/display.py print_battlefield:
        active_fig, overlay_mode, slyn_unknown, highlighted_enemies
    """
    active_fig = kwargs.get("active_fig")
    active_fig_name = active_fig.name if hasattr(active_fig, "name") else active_fig
    overlay_mode = kwargs.get("overlay_mode")
    slyn_unknown = kwargs.get("slyn_unknown", False)
    highlighted_enemies = kwargs.get("highlighted_enemies") or []

    # Build zone grid
    zones = []
    for r in range(bf.rows):
        row = []
        for c in range(bf.cols):
            zone = bf.zones[r][c]
            zd = {
                "row": r, "col": c,
                "terrain": zone.terrain.value,
                "has_objective": zone.has_objective,
                "objective_label": zone.objective_label,
            }
            if zone.terrain_name:
                zd["terrain_name"] = zone.terrain_name
            if zone.difficult:
                zd["difficult"] = True
            row.append(zd)
        zones.append(row)

    # Build figure list
    figures = []
    _label_counters: dict[str, int] = {"player": 0, "enemy": 0}
    _label_cache: dict[str, str] = {}

    for fig in bf.figures:
        if not fig.is_alive:
            # Include player casualties as fallen markers
            if fig.side.value == "player":
                figures.append({
                    "name": fig.name,
                    "label": "\u2020",  # dagger/cross symbol
                    "side": "player",
                    "zone": list(fig.zone),
                    "status": "casualty",
                    "color": "player-fallen",
                    "is_contact": False,
                    "is_active": False,
                    "is_highlighted": False,
                    "weapon": fig.weapon_name,
                    "char_class": fig.char_class,
                    "speed": 0,
                    "toughness": 0,
                    "combat_skill": 0,
                    "stun_markers": 0,
                })
            continue

        # Generate label using Figure.display_label() (single source of truth)
        if fig.name in _label_cache:
            code = _label_cache[fig.name]
        elif fig.is_contact:
            code = "??"
        else:
            side_key = "player" if fig.side.value == "player" else "enemy"
            _label_counters[side_key] += 1
            num = _label_counters[side_key]
            code = f"{num}{fig.abbreviation}"
            _label_cache[fig.name] = code
        label = fig.display_label(code)

        # Color class
        if fig.side.value == "player":
            color = "player"
        elif fig.char_class == "storm":
            color = "storm"
        elif fig.char_class == "slyn":
            color = "slyn"
        elif fig.char_class == "sleeper":
            color = "sleeper"
        else:
            color = "enemy"

        fig_data = {
            "name": fig.name,
            "label": label,
            "side": fig.side.value,
            "zone": list(fig.zone),
            "status": fig.status.value,
            "color": color,
            "is_contact": fig.is_contact,
            "is_active": fig.name == active_fig_name,
            "is_highlighted": fig.name in highlighted_enemies,
            "weapon": fig.weapon_name,
            "char_class": fig.char_class,
            "speed": fig.speed,
            "toughness": fig.toughness,
            "combat_skill": fig.combat_skill,
            "stun_markers": fig.stun_markers,
            "fireteam_id": fig.fireteam_id,
            "armor_save": fig.armor_save,
            "special_rules": list(fig.special_rules) if fig.special_rules else [],
        }
        # Include weapon details for enemy figures
        if fig.side.value == "enemy":
            fig_data["weapon_range"] = fig.weapon_range
            fig_data["weapon_shots"] = fig.weapon_shots
            fig_data["weapon_damage"] = getattr(fig, "weapon_damage", 0)
            fig_data["weapon_traits"] = list(fig.weapon_traits) if fig.weapon_traits else []
            fig_data["melee_damage"] = getattr(fig, "melee_damage", 0)

        figures.append(fig_data)

    # Build overlay data — send all three when there's an active figure
    overlay = None
    overlays = None
    if active_fig_name:
        active = bf.get_figure_by_name(active_fig_name)
        if active:
            overlays = {
                "movement": _build_overlay_data(bf, active, "movement"),
                "shooting": _build_overlay_data(bf, active, "shooting"),
                "vision": _build_overlay_data(bf, active, "vision"),
            }
            # Set initial overlay based on requested mode
            if overlay_mode:
                overlay = overlays.get(overlay_mode)

    return {
        "rows": bf.rows,
        "cols": bf.cols,
        "zones": zones,
        "figures": figures,
        "overlay": overlay,
        "overlays": overlays,
        "round_number": bf.round_number,
    }


def _build_overlay_data(
    bf: Any, fig: Any, mode: str,
) -> dict:
    """Build overlay zone highlights for movement/shooting/vision."""
    highlighted: dict[str, str] = {}
    fr, fc = fig.zone

    if mode == "movement":
        from planetfall.engine.combat.battlefield import (
            move_zones, rush_available, rush_total_zones,
            move_zones_difficult, rush_available_difficult, rush_total_zones_difficult,
            TerrainType, is_impassable, ignores_difficult_ground,
        )
        highlighted[f"{fr},{fc}"] = "active"
        is_scout = fig.char_class == "scout"
        fig_ignores_dg = ignores_difficult_ground(fig)
        source_difficult = bf.get_zone(fr, fc).difficult

        def _move_reach(dest_r: int, dest_c: int) -> tuple[int, bool, int]:
            """Get (normal_move, can_rush, rush_total) for a destination zone.

            Difficult ground applies if source OR destination is difficult,
            unless the figure ignores difficult ground (scouts, airborne).
            """
            if fig_ignores_dg:
                return (
                    move_zones(fig.speed),
                    rush_available(fig.speed),
                    rush_total_zones(fig.speed),
                )
            dest_difficult = bf.get_zone(dest_r, dest_c).difficult
            if source_difficult or dest_difficult:
                return (
                    move_zones_difficult(fig.speed),
                    rush_available_difficult(fig.speed),
                    rush_total_zones_difficult(fig.speed),
                )
            return (
                move_zones(fig.speed),
                rush_available(fig.speed),
                rush_total_zones(fig.speed),
            )

        # Build move and rush highlights per-zone
        max_reach = max(2, move_zones(fig.speed), rush_total_zones(fig.speed))
        for dr in range(-max_reach, max_reach + 1):
            for dc in range(-max_reach, max_reach + 1):
                nr, nc = fr + dr, fc + dc
                if (nr, nc) == (fr, fc):
                    continue
                if not (0 <= nr < bf.rows and 0 <= nc < bf.cols):
                    continue
                if is_impassable(bf.get_zone(nr, nc).terrain):
                    continue
                if not bf.zone_has_capacity(nr, nc, fig.side):
                    continue
                dist = max(abs(dr), abs(dc))
                nm, can_rush, rush_tot = _move_reach(nr, nc)
                key = f"{nr},{nc}"
                if is_scout and dist <= nm:
                    # Scout jump — skip pathing
                    highlighted[key] = "move"
                elif dist <= nm:
                    highlighted[key] = "move"
                elif can_rush and dist <= rush_tot and key not in highlighted:
                    highlighted[key] = "rush"

    elif mode == "shooting":
        weapon_range_zones = max(1, fig.weapon_range // 4)
        # Mark ALL zones as out of range, then upgrade reachable ones
        for r in range(bf.rows):
            for c in range(bf.cols):
                if (r, c) != (fr, fc):
                    highlighted[f"{r},{c}"] = "no_los"
        for dr in range(-weapon_range_zones, weapon_range_zones + 1):
            for dc in range(-weapon_range_zones, weapon_range_zones + 1):
                nr, nc = fr + dr, fc + dc
                if (0 <= nr < bf.rows and 0 <= nc < bf.cols
                        and (nr, nc) != (fr, fc)):
                    dist = max(abs(dr), abs(dc))
                    if dist <= weapon_range_zones:
                        los = bf.check_los((fr, fc), (nr, nc))
                        if los == "blocked":
                            highlighted[f"{nr},{nc}"] = "blocked"
                        elif bf.has_cover_los((fr, fc), (nr, nc)):
                            highlighted[f"{nr},{nc}"] = "cover"
                        elif dist <= 2:
                            highlighted[f"{nr},{nc}"] = "close_range"
                        else:
                            highlighted[f"{nr},{nc}"] = "long_range"
        highlighted[f"{fr},{fc}"] = "active"

    elif mode == "vision":
        # First mark ALL zones as no_los, then upgrade visible ones
        for r in range(bf.rows):
            for c in range(bf.cols):
                if (r, c) != (fr, fc):
                    highlighted[f"{r},{c}"] = "no_los"
        # Check LoS to every zone within range 6
        for dr in range(-6, 7):
            for dc in range(-6, 7):
                nr, nc = fr + dr, fc + dc
                if 0 <= nr < bf.rows and 0 <= nc < bf.cols and (nr, nc) != (fr, fc):
                    los = bf.check_los((fr, fc), (nr, nc))
                    if los == "blocked":
                        highlighted[f"{nr},{nc}"] = "blocked"
                    else:
                        dist = max(abs(dr), abs(dc))
                        if dist <= 2:
                            highlighted[f"{nr},{nc}"] = "close"
                        elif dist <= 4:
                            highlighted[f"{nr},{nc}"] = "medium"
                        elif dist <= 6:
                            highlighted[f"{nr},{nc}"] = "far"
        highlighted[f"{fr},{fc}"] = "active"

    return {"mode": mode, "zones": highlighted}


def serialize_armory(state: Any) -> dict:
    """Serialize weapon catalog and grunt upgrades for the armory modal."""
    from planetfall.engine.models import ALL_WEAPONS, ALLOWED_WEAPON_CLASSES, WEAPON_APP_IDS
    from planetfall.engine.campaign.research import APPLICATIONS, THEORIES

    # Check which tier buildings are built
    built_names = {b.name for b in state.colony.buildings}
    has_tier1 = "Advanced Manufacturing Plant" in built_names
    has_tier2 = "High-Tech Manufacturing Plant" in built_names
    unlocked_apps = set(state.tech_tree.unlocked_applications)

    def _theory_name_for_app(app_id: str) -> str:
        adef = APPLICATIONS.get(app_id)
        if adef:
            tdef = THEORIES.get(adef.theory_id)
            if tdef:
                return f"{tdef.name} Research"
        return ""

    weapons = []
    for w in ALL_WEAPONS:
        tier_str = w.tier.value if hasattr(w.tier, 'value') else str(w.tier)
        available = True
        prereq = ""
        if tier_str == "tier_1":
            app_id = WEAPON_APP_IDS.get(w.name)
            has_research = app_id in unlocked_apps if app_id else True
            available = has_tier1 and has_research
            if not has_tier1:
                prereq = "Advanced Manufacturing Plant"
            elif not has_research:
                prereq = _theory_name_for_app(app_id) if app_id else "Research required"
        elif tier_str == "tier_2":
            app_id = WEAPON_APP_IDS.get(w.name)
            has_research = app_id in unlocked_apps if app_id else True
            available = has_tier1 and has_tier2 and has_research
            if not (has_tier1 and has_tier2):
                prereq = "High-Tech Manufacturing Plant"
            elif not has_research:
                prereq = _theory_name_for_app(app_id) if app_id else "Research required"

        weapons.append({
            "name": w.name,
            "range_inches": w.range_inches,
            "shots": w.shots,
            "damage_bonus": w.damage_bonus,
            "traits": w.traits,
            "tier": tier_str,
            "available": available,
            "prerequisite": prereq,
        })

    # Grunt upgrades — both explicit (app_type=grunt_upgrade) and auto-triggered
    grunt_upgrades_list = list(state.grunts.upgrades) if state.grunts else []
    grunt_upgrades = []
    try:
        from planetfall.engine.campaign.research import APPLICATIONS
        # Explicit grunt_upgrade applications
        for app_id, adef in APPLICATIONS.items():
            if adef.app_type == "grunt_upgrade":
                grunt_upgrades.append({
                    "id": app_id,
                    "name": adef.name,
                    "description": adef.description,
                    "available": app_id in grunt_upgrades_list,
                    "prerequisite": adef.theory_id if app_id not in grunt_upgrades_list else "",
                })
        # Auto-triggered upgrades (from weapon/building research)
        _AUTO_UPGRADES = {
            "side_arms": ("Side Arms", "All grunts carry a handgun.", "Shard Pistol"),
            "sergeant_weaponry": ("Sergeant Weaponry", "One grunt per fireteam gets Damage +1 melee.", "Carver Blade"),
            "sharpshooter_sight": ("Sharpshooter Sight", "One grunt per fireteam gets +1 to hit when stationary.", "Early Warning System"),
            "adapted_armor": ("Adapted Armor", "All grunts receive a 6+ Saving Throw.", "Food Production Site"),
            "ammo_packs": ("Ammo Packs", "Once per battle, extra hit die per grunt in fireteam.", "Military Barracks"),
        }
        for upg_id, (name, desc, prereq_name) in _AUTO_UPGRADES.items():
            grunt_upgrades.append({
                "id": upg_id,
                "name": name,
                "description": desc,
                "available": upg_id in grunt_upgrades_list,
                "prerequisite": prereq_name if upg_id not in grunt_upgrades_list else "",
            })
    except Exception:
        pass

    return {"weapons": weapons, "grunt_upgrades": grunt_upgrades}


def serialize_ancient_signs(state: Any) -> dict:
    """Serialize ancient signs data for the modal."""
    progress = state.campaign
    signs_count = progress.ancient_signs_count if hasattr(progress, 'ancient_signs_count') else 0
    mission_data = progress.mission_data_count if hasattr(progress, 'mission_data_count') else 0
    breakthrough_ids = set(progress.breakthroughs if hasattr(progress, 'breakthroughs') else [])

    # Breakthroughs achieved
    from planetfall.engine.campaign.ancient_signs import BREAKTHROUGH_TABLE
    breakthroughs = []
    for _range, bt in BREAKTHROUGH_TABLE.items():
        if bt["id"] in breakthrough_ids:
            breakthroughs.append({
                "id": bt["id"],
                "name": bt["name"],
                "description": bt["description"],
            })

    # Active ancient sites (unexplored)
    active_sites = []
    for s in state.campaign_map.sectors:
        if s.has_ancient_site:
            active_sites.append({
                "sector_id": s.sector_id,
                "name": s.name or f"Sector {s.sector_id}",
                "status": "unexplored",
            })

    # Explored ancient sites (from tracking)
    raw_sites = state.tracking.explored_ancient_sites if hasattr(state.tracking, 'explored_ancient_sites') else []
    explored_sites = [s.model_dump() if hasattr(s, 'model_dump') else s for s in raw_sites]

    # Breakthrough tracker (1-4)
    bt_count = state.tracking.breakthroughs_count if hasattr(state.tracking, 'breakthroughs_count') else 0

    return {
        "ancient_signs_count": signs_count,
        "mission_data_count": mission_data,
        "breakthroughs": breakthroughs,
        "breakthroughs_count": bt_count,
        "active_sites": active_sites,
        "explored_sites": explored_sites,
    }


def serialize_milestones(state: Any) -> dict:
    """Serialize milestones data for the modal."""
    from planetfall.engine.campaign.milestones import MILESTONE_EFFECTS

    completed = state.campaign.milestones_completed if hasattr(state.campaign, 'milestones_completed') else 0

    effects = []
    for i in range(1, 8):
        eff = MILESTONE_EFFECTS.get(i, {})
        descriptions = []
        desc = eff.get("description", "")
        if desc:
            descriptions.append(desc)
        # Add specific effect descriptions
        if eff.get("story_points"):
            descriptions.append(f"+{eff['story_points']} Story Points")
        if eff.get("grunts"):
            descriptions.append(f"+{eff['grunts']} Grunts")
        if eff.get("integrity"):
            descriptions.append(f"+{eff['integrity']} Colony Integrity")
        if eff.get("augmentation_points"):
            descriptions.append(f"+{eff['augmentation_points']} Augmentation Points")
        if eff.get("calamity_points"):
            descriptions.append(f"+{eff['calamity_points']} Calamity Points")
        if eff.get("end_game"):
            descriptions.append("Triggers the Summit / End Game")

        effects.append({
            "milestone": i,
            "descriptions": descriptions,
        })

    return {
        "milestones_completed": completed,
        "effects": effects,
    }


def serialize_conditions(state: Any) -> dict:
    """Serialize campaign condition table (10 d100 slots) for the modal."""
    from planetfall.engine.tables.battlefield_conditions import _CONDITIONS_D100_RANGES

    conditions_list = state.tracking.battlefield_conditions if hasattr(state.tracking, 'battlefield_conditions') else []

    slots = []
    for i, (low, high) in enumerate(_CONDITIONS_D100_RANGES):
        entry = conditions_list[i] if i < len(conditions_list) else None
        # Convert BattlefieldCondition model to dict for JSON serialization
        condition_data = entry.model_dump() if entry is not None and hasattr(entry, 'model_dump') else entry
        slots.append({
            "index": i + 1,
            "d100_low": low,
            "d100_high": high,
            "condition": condition_data,
        })

    return {"slots": slots}


def serialize_lifeforms(state: Any) -> dict:
    """Serialize lifeform d100 table for the modal.

    Always returns all 10 slots (with empty names for unencountered slots).
    """
    _D100_RANGES = [
        (1, 18), (19, 32), (33, 44), (45, 54), (55, 64),
        (65, 73), (74, 82), (83, 89), (90, 95), (96, 100),
    ]
    existing = state.enemies.lifeform_table
    lifeforms = []
    for i, (low, high) in enumerate(_D100_RANGES):
        if i < len(existing):
            lf = existing[i]
            lifeforms.append({
                "d100_low": lf.d100_low,
                "d100_high": lf.d100_high,
                "name": lf.name,
                "mobility": lf.mobility,
                "toughness": lf.toughness,
                "combat_skill": lf.combat_skill,
                "strike_damage": lf.strike_damage,
                "armor_save": lf.armor_save,
                "kill_points": lf.kill_points,
                "dodge": lf.dodge,
                "partially_airborne": lf.partially_airborne,
                "weapons": lf.weapons,
                "special_rules": lf.special_rules,
                "bio_analysis_level": lf.bio_analysis_level,
                "specimen_collected": lf.specimen_collected,
                "bio_analysis_result": lf.bio_analysis_result,
            })
        else:
            lifeforms.append({
                "d100_low": low,
                "d100_high": high,
                "name": "",
                "mobility": 0,
                "toughness": 0,
                "combat_skill": 0,
                "strike_damage": 0,
                "armor_save": 0,
                "kill_points": 0,
                "dodge": False,
                "partially_airborne": False,
                "weapons": [],
                "special_rules": [],
                "bio_analysis_level": 0,
                "specimen_collected": False,
                "bio_analysis_result": "",
            })
    return {"lifeforms": lifeforms}


def serialize_enemies(state: Any) -> dict:
    """Serialize tactical enemies and Slyn data for the modal."""
    tactical = []
    for te in state.enemies.tactical_enemies:
        tactical.append({
            "name": te.name,
            "enemy_type": te.enemy_type,
            "sectors": te.sectors,
            "enemy_info_count": te.enemy_info_count,
            "boss_located": te.boss_located,
            "strongpoint_located": te.strongpoint_located,
            "defeated": te.defeated,
            "profile": te.profile.model_dump() if hasattr(te.profile, 'model_dump') else te.profile,
        })

    slyn = {
        "active": state.enemies.slyn.active,
        "encounters": state.enemies.slyn.encounters,
        "victories": state.tracking.slyn_victories if hasattr(state.tracking, 'slyn_victories') else 0,
    }

    return {
        "tactical_enemies": tactical,
        "slyn": slyn,
    }


def serialize_augmentations(state: Any) -> dict:
    """Serialize augmentation data for the modal."""
    from planetfall.engine.campaign.augmentation import (
        AUGMENTATIONS, get_colony_augmentations, get_augmentation_cost,
    )

    owned = set(get_colony_augmentations(state))
    next_cost = get_augmentation_cost(state)
    ap = state.colony.resources.augmentation_points
    bought_this_turn = state.flags.augmentation_bought_this_turn

    augmentations = []
    for aug_id, aug in AUGMENTATIONS.items():
        is_owned = aug_id in owned
        augmentations.append({
            "id": aug_id,
            "name": aug["name"],
            "description": aug["description"],
            "is_milestone": aug.get("is_milestone", False),
            "owned": is_owned,
        })

    return {
        "augmentations": augmentations,
        "owned_count": len(owned),
        "next_cost": next_cost,
        "augmentation_points": ap,
        "bought_this_turn": bought_this_turn,
    }


def serialize_artifacts(state: Any) -> dict:
    """Serialize discovered artifacts for the modal."""
    artifacts = []
    artifact_list = state.campaign.artifacts if hasattr(state.campaign, 'artifacts') else []
    for art in artifact_list:
        artifacts.append({
            "name": art.name if hasattr(art, 'name') else str(art),
            "description": art.description if hasattr(art, 'description') else "",
            "artifact_type": art.artifact_type if hasattr(art, 'artifact_type') else "unknown",
            "assigned_to": art.assigned_to if hasattr(art, 'assigned_to') else "",
            "used": art.used if hasattr(art, 'used') else False,
        })
    return {"artifacts": artifacts}


def serialize_calamities(state: Any) -> dict:
    """Serialize calamity data for the modal."""
    calamity_points = state.colony.resources.calamity_points if hasattr(state.colony.resources, 'calamity_points') else 0
    calamity_events = []
    events_list = state.tracking.calamity_events if hasattr(state.tracking, 'calamity_events') else []
    for evt in events_list:
        calamity_events.append({
            "turn": evt.turn if hasattr(evt, 'turn') else "?",
            "name": evt.name if hasattr(evt, 'name') else str(evt),
            "description": evt.description if hasattr(evt, 'description') else "",
        })
    return {
        "calamity_points": calamity_points,
        "calamity_events": calamity_events,
    }


def serialize_morale(state: Any) -> dict:
    """Serialize morale and crisis data for the modal."""
    morale = state.colony.morale
    political_upheaval = state.tracking.political_upheaval if hasattr(state.tracking, 'political_upheaval') else 0
    in_crisis = state.tracking.in_crisis if hasattr(state.tracking, 'in_crisis') else False
    incidents = []
    incident_list = state.tracking.morale_incidents if hasattr(state.tracking, 'morale_incidents') else []
    for inc in incident_list:
        incidents.append({
            "turn": inc.turn if hasattr(inc, 'turn') else "?",
            "name": inc.name if hasattr(inc, 'name') else str(inc),
            "description": inc.description if hasattr(inc, 'description') else "",
        })
    return {
        "morale": morale,
        "political_upheaval": political_upheaval,
        "in_crisis": in_crisis,
        "incidents": incidents,
    }

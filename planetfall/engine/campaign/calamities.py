"""Calamity system — catastrophic events triggered by milestone progression.

Each milestone, roll 1D6 vs accumulated Calamity Points. If roll <= CP,
subtract roll from CP and trigger a calamity from the D100 table.
Each calamity can only occur once per campaign.
"""

from __future__ import annotations

import random
from planetfall.engine.dice import roll_d6, roll_d100, roll_nd6
from planetfall.engine.models import GameState, TurnEvent, TurnEventType, DiceRoll


# D100 Calamity Table — ordered list for wrapping
CALAMITY_TABLE_ENTRIES = [
    ((1, 11), {
        "id": "swarm_infestation",
        "name": "Swarm Infestation",
        "description": (
            "Alien creatures swarm from underground. "
            "Randomly infest a map sector. Swarm: Speed 6\", CS +1, "
            "Toughness 4, Claws +1 Damage. 2D6+4 encountered. "
            "Clear via Skirmish missions."
        ),
        "effect": "spawn_swarm",
    }),
    ((12, 25), {
        "id": "environmental_risk",
        "name": "Environmental Risk",
        "description": (
            "Atmospheric anomalies in 3 random sectors. End of each turn: "
            "D6 per sector (5-6 = flare). Flare D6: 1-2 crew injured, "
            "3-4 colony damage, 5 nothing, 6 new anomaly. "
            "Clear via Patrol Missions."
        ),
        "effect": "environmental_hazard",
    }),
    ((26, 36), {
        "id": "enemy_super_weapon",
        "name": "Enemy Super Weapon",
        "description": (
            "A tactical enemy constructs a super weapon. D6 progress/turn "
            "(target 15). When complete: 3D6 colony damage, each 6 also "
            "injures a character. Destroy via Strike Mission."
        ),
        "effect": "super_weapon",
    }),
    ((37, 48), {
        "id": "virus",
        "name": "Virus Outbreak",
        "description": (
            "Virus infects 2 random characters (D6 virus points, 6=ill). "
            "Each turn: 3 chars checked, +1 virus point. "
            "Total 6 = ill (quarantined). Cure via Hunt missions."
        ),
        "effect": "virus",
    }),
    ((49, 63), {
        "id": "mega_predators",
        "name": "Mega Predators",
        "description": (
            "Each lifeform reveal: D6, on 6 = +1 KP (keep rolling). "
            "Kill 5 enhanced lifeforms via Patrol to end threat. "
            "Reward: +1 Resource to 3 random sectors."
        ),
        "effect": "mega_predators",
    }),
    ((64, 77), {
        "id": "wildlife_aggression",
        "name": "Wildlife Aggression",
        "description": (
            "Controller agitates local wildlife. +1 lifeform per reveal. "
            "Hunt mission: each reveal D6, on 6 = Controller "
            "(+3 KP, flees toward edge). Kill to end. "
            "Reward: +1 Augmentation Point."
        ),
        "effect": "wildlife_controller",
    }),
    ((78, 91), {
        "id": "robot_rampage",
        "name": "Robot Rampage",
        "description": (
            "Sleeper robots activate. Missions: 6 markers in terrain, "
            "reveal within 12\": D6 1-3 nothing, 4-5 Sleeper, 6 Sleeper+chain. "
            "Find 5 shutdown chips to end. Reward: +4 Research Points."
        ),
        "effect": "robots",
    }),
    ((92, 100), {
        "id": "slyn_assault",
        "name": "Slyn Assault",
        "description": (
            "Slyn escalate attacks. Double Slyn interference rolls; "
            "if both trigger, encounter 8 Slyn. "
            "Kill 30 Slyn total to end. Reward: +2 Grunts."
        ),
        "effect": "slyn_assault",
    }),
]

# Dict form for backwards compatibility
CALAMITY_TABLE = {r: e for r, e in CALAMITY_TABLE_ENTRIES}


def check_calamity(state: GameState) -> list[TurnEvent]:
    """Check if a calamity is triggered (called after milestones).

    Roll 1D6 vs current Calamity Points. If roll <= CP, trigger calamity.
    """
    # Check if calamities are disabled (Milestone 7 passed without triggering)
    if state.tracking.calamities_disabled:
        return []

    cp = state.colony.resources.calamity_points
    if cp <= 0:
        return []

    roll = roll_d6("Calamity Check")
    if roll.total > cp:
        return [TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=f"Calamity check: rolled {roll.total} vs {cp} CP — no calamity.",
            dice_rolls=[DiceRoll(dice_type="d6", values=roll.values,
                                 total=roll.total, label="Calamity Check")],
        )]

    # Calamity triggered! Subtract roll from CP
    state.colony.resources.calamity_points -= roll.total

    # Roll on the calamity table
    occurred = set(state.tracking.occurred_calamities)
    calamity_roll = roll_d100("Calamity Table")

    # Find which entry was rolled
    rolled_idx = 0
    calamity = None
    for i, ((low, high), entry) in enumerate(CALAMITY_TABLE_ENTRIES):
        if low <= calamity_roll.total <= high:
            calamity = entry
            rolled_idx = i
            break

    if not calamity:
        return []

    # Check for duplicates — wrap forward from rolled entry
    if calamity["id"] in occurred:
        found = False
        num_entries = len(CALAMITY_TABLE_ENTRIES)
        for offset in range(1, num_entries):
            idx = (rolled_idx + offset) % num_entries
            candidate = CALAMITY_TABLE_ENTRIES[idx][1]
            if candidate["id"] not in occurred:
                calamity = candidate
                found = True
                break
        if not found:
            return [TurnEvent(
                step=0, event_type=TurnEventType.NARRATIVE,
                description="All calamities have already occurred!",
            )]

    # Record occurrence
    state.tracking.occurred_calamities = list(occurred | {calamity["id"]})

    # Initialize calamity tracking
    _init_calamity_tracking(state, calamity)

    return [TurnEvent(
        step=0, event_type=TurnEventType.NARRATIVE,
        description=(
            f"=== CALAMITY: {calamity['name']} === "
            f"{calamity['description']}"
        ),
        state_changes={"calamity": calamity["id"], "calamity_roll": calamity_roll.total},
        dice_rolls=[
            DiceRoll(dice_type="d6", values=roll.values, total=roll.total, label="Calamity Check"),
            DiceRoll(dice_type="d100", values=[calamity_roll.total], total=calamity_roll.total, label="Calamity Table"),
        ],
    )]


def _init_calamity_tracking(state: GameState, calamity: dict):
    """Initialize tracking data for an active calamity."""
    active = dict(state.tracking.active_calamities)
    cid = calamity["id"]

    if cid == "swarm_infestation":
        # Pick a non-enemy, non-colony sector to infest
        colony_id = state.campaign_map.colony_sector_id
        candidates = [
            s.sector_id for s in state.campaign_map.sectors
            if s.sector_id != colony_id
            and s.enemy_occupied_by is None
        ]
        sector = random.choice(candidates) if candidates else 0
        active[cid] = {"infested_sectors": [sector], "cleared_sectors": []}
    elif cid == "environmental_risk":
        sector_ids = [s.sector_id for s in state.campaign_map.sectors]
        sectors = random.sample(sector_ids, min(3, len(sector_ids)))
        active[cid] = {"affected_sectors": sectors, "cleared_sectors": []}
    elif cid == "enemy_super_weapon":
        active[cid] = {"progress": 0, "target": 15, "destroyed": False}
    elif cid == "virus":
        # Roll D6 for 2 random characters: 1-5 = virus points, 6 = immediately ill
        chars = random.sample(state.characters, min(2, len(state.characters)))
        infected: dict[str, int] = {}
        quarantined: list[str] = []
        for c in chars:
            vr = roll_d6(f"Virus: {c.name}")
            if vr.total == 6:
                quarantined.append(c.name)
                c.sick_bay_turns = max(c.sick_bay_turns, 99)  # Quarantined until cured
            else:
                infected[c.name] = vr.total
        active[cid] = {
            "infected": infected,  # name -> virus points
            "quarantined": quarantined,
            "cure_data": 0,
            "cured": False,
        }
    elif cid == "mega_predators":
        active[cid] = {"enhanced_kills": 0, "kills_needed": 5}
    elif cid == "wildlife_controller":
        active[cid] = {"controller_found": False, "controller_killed": False}
    elif cid == "robots":
        active[cid] = {"chips_found": 0, "chips_needed": 5}
    elif cid == "slyn_assault":
        active[cid] = {"slyn_kills": 0, "kills_needed": 30}

    state.tracking.active_calamities = active


def process_active_calamities(state: GameState) -> list[TurnEvent]:
    """Process per-turn effects of active calamities."""
    active = dict(state.tracking.active_calamities)
    events = []

    # --- Swarm Infestation: spreading + colony damage ---
    if "swarm_infestation" in active:
        data = active["swarm_infestation"]
        infested = list(data.get("infested_sectors", []))
        cleared = set(data.get("cleared_sectors", []))
        active_infested = [s for s in infested if s not in cleared]
        colony_id = state.campaign_map.colony_sector_id
        cols = 6
        total_sectors = len(state.campaign_map.sectors)

        # Spreading: roll D6 per adjacent sector, stop on first 6
        spread_done = False
        for sid in list(active_infested):
            if spread_done:
                break
            row, col = divmod(sid, cols)
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if dr == 0 and dc == 0:
                        continue
                    nid = (row + dr) * cols + (col + dc)
                    if 0 <= nid < total_sectors and nid not in infested:
                        sr = roll_d6(f"Swarm spread to sector {nid}")
                        if sr.total == 6:
                            infested.append(nid)
                            events.append(TurnEvent(
                                step=0, event_type=TurnEventType.COLONY_EVENT,
                                description=f"Swarm spreads to sector {nid}!",
                            ))
                            spread_done = True
                            break
                if spread_done:
                    break

        # Colony damage from adjacent infested sectors
        for sid in active_infested:
            row, col = divmod(sid, cols)
            c_row, c_col = divmod(colony_id, cols)
            if max(abs(row - c_row), abs(col - c_col)) <= 1 and sid != colony_id:
                dr = roll_d6(f"Swarm perimeter attack from sector {sid}")
                if dr.total <= 2:
                    pass  # No effect
                elif dr.total <= 5:
                    state.colony.integrity -= dr.total
                    events.append(TurnEvent(
                        step=0, event_type=TurnEventType.COLONY_EVENT,
                        description=f"Swarm attacks from sector {sid}: {dr.total} colony damage!",
                    ))
                else:  # 6
                    state.colony.integrity -= 6
                    state.grunts.count = max(0, state.grunts.count - 1)
                    events.append(TurnEvent(
                        step=0, event_type=TurnEventType.COLONY_EVENT,
                        description=f"Swarm attacks from sector {sid}: 6 colony damage + 1 grunt killed!",
                    ))

        data["infested_sectors"] = infested
        active["swarm_infestation"] = data

    # --- Environmental Risk: flare-ups ---
    if "environmental_risk" in active:
        data = active["environmental_risk"]
        affected = data.get("affected_sectors", [])
        cleared = set(data.get("cleared_sectors", []))
        for sector_id in affected:
            if sector_id in cleared:
                continue
            roll = roll_d6(f"Environmental check (sector {sector_id})")
            if roll.total >= 5:
                flare = roll_d6(f"Flare effect (sector {sector_id})")
                if flare.total <= 2:
                    # Crew member injured
                    if state.characters:
                        victim = random.choice(state.characters)
                        victim.sick_bay_turns = max(victim.sick_bay_turns, 1)
                        events.append(TurnEvent(
                            step=0, event_type=TurnEventType.COLONY_EVENT,
                            description=f"Environmental flare in sector {sector_id}: {victim.name} injured (1 turn sick bay).",
                        ))
                elif flare.total <= 4:
                    # Colony damage
                    state.colony.integrity -= 1
                    events.append(TurnEvent(
                        step=0, event_type=TurnEventType.COLONY_EVENT,
                        description=f"Environmental flare in sector {sector_id}: 1 colony damage.",
                    ))
                elif flare.total == 5:
                    events.append(TurnEvent(
                        step=0, event_type=TurnEventType.NARRATIVE,
                        description=f"Environmental flare in sector {sector_id}: no effect.",
                    ))
                else:  # 6
                    # Chain reaction: new anomaly sector
                    all_ids = [s.sector_id for s in state.campaign_map.sectors]
                    new_candidates = [s for s in all_ids if s not in affected]
                    if new_candidates:
                        new_sector = random.choice(new_candidates)
                        affected.append(new_sector)
                        events.append(TurnEvent(
                            step=0, event_type=TurnEventType.COLONY_EVENT,
                            description=f"Environmental flare in sector {sector_id}: chain reaction! Sector {new_sector} develops anomaly.",
                        ))
        data["affected_sectors"] = affected
        active["environmental_risk"] = data

    # --- Super Weapon: progress ---
    if "enemy_super_weapon" in active:
        data = active["enemy_super_weapon"]
        if not data.get("destroyed"):
            progress_roll = roll_d6("Super weapon progress")
            data["progress"] += progress_roll.total
            if data["progress"] >= data["target"]:
                # Weapon fires!
                damage = roll_nd6(3, "Super weapon fires")
                state.colony.integrity -= damage.total
                desc = f"ENEMY SUPER WEAPON FIRES! {damage.total} colony damage!"
                # Each 6 on damage roll injures a random character
                sixes = sum(1 for v in damage.values if v == 6)
                for _ in range(sixes):
                    if state.characters:
                        victim = random.choice(state.characters)
                        victim.sick_bay_turns = max(victim.sick_bay_turns, 1)
                        desc += f" {victim.name} injured by blast!"
                events.append(TurnEvent(
                    step=0, event_type=TurnEventType.COLONY_EVENT,
                    description=desc,
                    dice_rolls=[DiceRoll(dice_type="3d6", values=damage.values,
                                        total=damage.total, label="Super Weapon Damage")],
                ))
                data["progress"] = 0  # Reset for next firing
            else:
                events.append(TurnEvent(
                    step=0, event_type=TurnEventType.NARRATIVE,
                    description=(
                        f"Super weapon progress: {data['progress']}/{data['target']} "
                        f"(+{progress_roll.total} this turn)"
                    ),
                ))
        active["enemy_super_weapon"] = data

    # --- Virus: spread ---
    if "virus" in active:
        data = active["virus"]
        if not data.get("cured"):
            infected = dict(data.get("infected", {}))
            quarantined = list(data.get("quarantined", []))

            # Select 3 characters to check
            char_names = [c.name for c in state.characters if c.name not in quarantined]
            check_chars = random.sample(char_names, min(3, len(char_names)))
            for name in check_chars:
                if name in infected:
                    infected[name] += 1
                    if infected[name] >= 6:
                        quarantined.append(name)
                        del infected[name]
                        char = state.find_character(name)
                        if char:
                            char.sick_bay_turns = max(char.sick_bay_turns, 99)
                        events.append(TurnEvent(
                            step=0, event_type=TurnEventType.COLONY_EVENT,
                            description=f"Virus: {name} falls ill (quarantined)!",
                        ))
                    else:
                        events.append(TurnEvent(
                            step=0, event_type=TurnEventType.NARRATIVE,
                            description=f"Virus: {name} virus points now {infected[name]}/6.",
                        ))
                else:
                    vr = roll_d6(f"Virus check: {name}")
                    if vr.total == 6:
                        quarantined.append(name)
                        char = state.find_character(name)
                        if char:
                            char.sick_bay_turns = max(char.sick_bay_turns, 99)
                        events.append(TurnEvent(
                            step=0, event_type=TurnEventType.COLONY_EVENT,
                            description=f"Virus: {name} immediately falls ill!",
                        ))
                    elif vr.total >= 1:
                        infected[name] = vr.total
                        events.append(TurnEvent(
                            step=0, event_type=TurnEventType.NARRATIVE,
                            description=f"Virus: {name} infected with {vr.total} virus points.",
                        ))

            # Cure check
            cure_data = data.get("cure_data", 0)
            if cure_data > 0:
                cure_roll = roll_nd6(2, "Virus cure check")
                if cure_roll.total <= cure_data:
                    data["cured"] = True
                    # Release quarantined characters
                    for qname in quarantined:
                        char = state.find_character(qname)
                        if char and char.sick_bay_turns >= 99:
                            char.sick_bay_turns = 0
                    events.append(TurnEvent(
                        step=0, event_type=TurnEventType.COLONY_EVENT,
                        description=f"VIRUS CURED! (rolled {cure_roll.total} ≤ {cure_data} cure data). All quarantined recover.",
                    ))
                else:
                    events.append(TurnEvent(
                        step=0, event_type=TurnEventType.NARRATIVE,
                        description=f"Cure check: {cure_roll.total} > {cure_data} cure data. No cure yet.",
                    ))

            data["infected"] = infected
            data["quarantined"] = quarantined
            active["virus"] = data

    state.tracking.active_calamities = active
    return events


def resolve_calamity_progress(
    state: GameState, calamity_id: str, progress: int = 1
) -> list[TurnEvent]:
    """Record progress toward resolving a calamity.

    Args:
        calamity_id: Which calamity to progress.
        progress: Amount of progress (kills, chips, etc.)
    """
    active = dict(state.tracking.active_calamities)
    if calamity_id not in active:
        return []

    data = active[calamity_id]
    events = []

    if calamity_id == "swarm_infestation":
        # Clear a specific sector (called after Skirmish victory)
        cleared = list(data.get("cleared_sectors", []))
        infested = data.get("infested_sectors", [])
        active_infested = [s for s in infested if s not in cleared]
        if active_infested:
            cleared.append(active_infested[0])
            data["cleared_sectors"] = cleared
            events.append(TurnEvent(
                step=0, event_type=TurnEventType.NARRATIVE,
                description=f"Swarm cleared from sector {active_infested[0]}!",
            ))
        remaining = [s for s in infested if s not in cleared]
        if not remaining:
            events.append(TurnEvent(
                step=0, event_type=TurnEventType.NARRATIVE,
                description="All Swarm sectors cleared! Calamity ended. You may recruit 1 trooper.",
            ))
            del active[calamity_id]

    elif calamity_id == "environmental_risk":
        # Clear a specific sector
        cleared = list(data.get("cleared_sectors", []))
        affected = data.get("affected_sectors", [])
        active_affected = [s for s in affected if s not in cleared]
        if active_affected:
            cleared.append(active_affected[0])
            data["cleared_sectors"] = cleared
            state.colony.resources.raw_materials += 2
            events.append(TurnEvent(
                step=0, event_type=TurnEventType.NARRATIVE,
                description=f"Anomaly cleared in sector {active_affected[0]}! +2 Raw Materials.",
            ))
        remaining = [s for s in affected if s not in cleared]
        if not remaining:
            events.append(TurnEvent(
                step=0, event_type=TurnEventType.NARRATIVE,
                description="All environmental anomalies cleared! Calamity ended.",
            ))
            del active[calamity_id]

    elif calamity_id == "mega_predators":
        data["enhanced_kills"] = data.get("enhanced_kills", 0) + progress
        if data["enhanced_kills"] >= data.get("kills_needed", 5):
            # Reward: +1 resource to 3 random sectors
            sectors = random.sample(
                state.campaign_map.sectors,
                min(3, len(state.campaign_map.sectors))
            )
            for s in sectors:
                s.resource_level = min(s.resource_level + 1, 5)
            events.append(TurnEvent(
                step=0, event_type=TurnEventType.NARRATIVE,
                description="Mega Predator threat eliminated! +1 Resource to 3 random sectors.",
            ))
            del active[calamity_id]
        else:
            events.append(TurnEvent(
                step=0, event_type=TurnEventType.NARRATIVE,
                description=f"Mega Predator kills: {data['enhanced_kills']}/{data['kills_needed']}",
            ))

    elif calamity_id == "robots":
        data["chips_found"] += progress
        if data["chips_found"] >= data["chips_needed"]:
            state.colony.resources.research_points += 4
            events.append(TurnEvent(
                step=0, event_type=TurnEventType.NARRATIVE,
                description="Robot shutdown signal sent! Rampage ended. +4 Research Points.",
            ))
            del active[calamity_id]
        else:
            events.append(TurnEvent(
                step=0, event_type=TurnEventType.NARRATIVE,
                description=f"Sleeper chips: {data['chips_found']}/{data['chips_needed']}",
            ))

    elif calamity_id == "slyn_assault":
        data["slyn_kills"] += progress
        if data["slyn_kills"] >= data["kills_needed"]:
            state.grunts.count += 2
            events.append(TurnEvent(
                step=0, event_type=TurnEventType.NARRATIVE,
                description="Slyn threat neutralized! +2 Grunts recruited.",
            ))
            del active[calamity_id]
        else:
            events.append(TurnEvent(
                step=0, event_type=TurnEventType.NARRATIVE,
                description=f"Slyn kills: {data['slyn_kills']}/{data['kills_needed']}",
            ))

    elif calamity_id == "virus":
        data["cure_data"] = data.get("cure_data", 0) + (progress * 2)
        events.append(TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=f"Hunt mission complete: +{progress * 2} Cure Data (total: {data['cure_data']}).",
        ))

    elif calamity_id == "wildlife_controller":
        data["controller_killed"] = True
        state.colony.resources.augmentation_points += 1
        events.append(TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description="Wildlife controller destroyed! +1 Augmentation Point.",
        ))
        del active[calamity_id]

    elif calamity_id == "enemy_super_weapon":
        data["destroyed"] = True
        events.append(TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description="Enemy super weapon destroyed! You may roll twice on Post-Mission Finds.",
        ))
        del active[calamity_id]

    state.tracking.active_calamities = active
    return events

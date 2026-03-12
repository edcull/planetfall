"""Calamity system — catastrophic events triggered by milestone progression.

Each milestone, roll 1D6 vs accumulated Calamity Points. If roll <= CP,
subtract roll from CP and trigger a calamity from the D100 table.
Each calamity can only occur once per campaign.
"""

from __future__ import annotations

import random
from planetfall.engine.dice import roll_d6, roll_d100
from planetfall.engine.models import GameState, TurnEvent, TurnEventType


# D100 Calamity Table
CALAMITY_TABLE = {
    (1, 11): {
        "id": "swarm_infestation",
        "name": "Swarm Infestation",
        "description": (
            "Alien creatures swarm from underground nests. 2D6+4 lifeforms "
            "emerge in a nearby sector. Cleared via Skirmish missions."
        ),
        "effect": "spawn_swarm",
    },
    (12, 25): {
        "id": "environmental_risk",
        "name": "Environmental Risk",
        "description": (
            "Atmospheric anomalies affect 3 random sectors. End of each turn: "
            "D6 per sector, 5-6 triggers flare damage to colony or crew."
        ),
        "effect": "environmental_hazard",
    },
    (26, 36): {
        "id": "enemy_super_weapon",
        "name": "Enemy Super Weapon",
        "description": (
            "An enemy faction is constructing a super weapon. It gains D6 "
            "progress per turn (needs 15). When complete: 3D6 colony damage. "
            "Destroyed via Strike Mission on weapon site."
        ),
        "effect": "super_weapon",
    },
    (37, 48): {
        "id": "virus",
        "name": "Virus Outbreak",
        "description": (
            "A mysterious virus infects 2 random characters. Quarantine "
            "required. Cure via Hunt missions (2 points per mission)."
        ),
        "effect": "virus",
    },
    (49, 63): {
        "id": "mega_predators",
        "name": "Mega Predators",
        "description": (
            "Lifeforms gain +2 KP. Must kill 5 enhanced lifeforms "
            "via Patrol missions to end the threat."
        ),
        "effect": "mega_predators",
    },
    (64, 77): {
        "id": "wildlife_aggression",
        "name": "Wildlife Aggression",
        "description": (
            "An unknown controller is agitating local wildlife. "
            "Find and destroy the controller via Hunt mission. "
            "Reward: +1 Augmentation Point."
        ),
        "effect": "wildlife_controller",
    },
    (78, 91): {
        "id": "robot_rampage",
        "name": "Robot Rampage",
        "description": (
            "Ancient sleeper robots activate across the region. "
            "Find 5 shutdown chips via missions to end the threat."
        ),
        "effect": "robots",
    },
    (92, 100): {
        "id": "slyn_assault",
        "name": "Slyn Assault",
        "description": (
            "The Slyn escalate their operations. Double chance of Slyn "
            "interference on all missions. Kill 30 Slyn total to end. "
            "Reward: +2 Grunts."
        ),
        "effect": "slyn_assault",
    },
}


def check_calamity(state: GameState) -> list[TurnEvent]:
    """Check if a calamity is triggered (called after milestones).

    Roll 1D6 vs current Calamity Points. If roll <= CP, trigger calamity.
    """
    cp = state.colony.resources.calamity_points
    if cp <= 0:
        return []

    roll = roll_d6("Calamity Check")
    if roll.total > cp:
        return [TurnEvent(
            step=0, event_type=TurnEventType.NARRATIVE,
            description=f"Calamity check: rolled {roll.total} vs {cp} CP — no calamity.",
        )]

    # Calamity triggered!
    state.colony.resources.calamity_points -= roll.total

    # Roll on the calamity table
    occurred = list(state.tracking.occurred_calamities)
    calamity_roll = roll_d100("Calamity Table")
    calamity = None
    for (low, high), entry in CALAMITY_TABLE.items():
        if low <= calamity_roll.total <= high:
            calamity = entry
            break

    if not calamity:
        return []

    # Check for duplicates — find next unused entry
    if calamity["id"] in occurred:
        for (low, high), entry in CALAMITY_TABLE.items():
            if entry["id"] not in occurred:
                calamity = entry
                break
        else:
            return [TurnEvent(
                step=0, event_type=TurnEventType.NARRATIVE,
                description="All calamities have already occurred!",
            )]

    # Record occurrence
    occurred.append(calamity["id"])
    state.tracking.occurred_calamities = occurred

    # Initialize calamity tracking
    _init_calamity_tracking(state, calamity)

    return [TurnEvent(
        step=0, event_type=TurnEventType.NARRATIVE,
        description=(
            f"=== CALAMITY: {calamity['name']} === "
            f"{calamity['description']}"
        ),
        state_changes={"calamity": calamity["id"], "calamity_roll": calamity_roll.total},
    )]


def _init_calamity_tracking(state: GameState, calamity: dict):
    """Initialize tracking data for an active calamity."""
    active = dict(state.tracking.active_calamities)
    cid = calamity["id"]

    if cid == "swarm_infestation":
        active[cid] = {"spawned": True, "cleared": False}
    elif cid == "environmental_risk":
        sectors = random.sample(range(len(state.campaign_map.sectors)), min(3, len(state.campaign_map.sectors)))
        active[cid] = {"affected_sectors": sectors, "cleared_count": 0}
    elif cid == "enemy_super_weapon":
        active[cid] = {"progress": 0, "target": 15, "destroyed": False}
    elif cid == "virus":
        chars = random.sample(state.characters, min(2, len(state.characters)))
        active[cid] = {
            "infected": [c.name for c in chars],
            "cure_data": 0, "cured": False,
        }
    elif cid == "mega_predators":
        active[cid] = {"kills_needed": 5, "kills_done": 0}
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

    if "environmental_risk" in active and not active["environmental_risk"].get("cleared"):
        data = active["environmental_risk"]
        for sector_idx in data.get("affected_sectors", []):
            roll = roll_d6(f"Environmental flare (sector {sector_idx})")
            if roll.total >= 5:
                dmg_roll = roll_d6("Flare damage")
                state.colony.integrity -= 1
                events.append(TurnEvent(
                    step=0, event_type=TurnEventType.COLONY_EVENT,
                    description=(
                        f"Environmental flare in sector {sector_idx}! "
                        f"Colony takes 1 integrity damage."
                    ),
                ))

    if "enemy_super_weapon" in active:
        data = active["enemy_super_weapon"]
        if not data.get("destroyed"):
            progress_roll = roll_d6("Super weapon progress")
            data["progress"] += progress_roll.total
            if data["progress"] >= data["target"]:
                # Weapon fires!
                from planetfall.engine.dice import roll_nd6
                damage = roll_nd6(3, "Super weapon fires")
                state.colony.integrity -= damage.total
                events.append(TurnEvent(
                    step=0, event_type=TurnEventType.COLONY_EVENT,
                    description=(
                        f"ENEMY SUPER WEAPON FIRES! {damage.total} colony damage! "
                        f"Colony integrity: {state.colony.integrity}"
                    ),
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

    if calamity_id == "mega_predators":
        data["kills_done"] += progress
        if data["kills_done"] >= data["kills_needed"]:
            events.append(TurnEvent(
                step=0, event_type=TurnEventType.NARRATIVE,
                description="Mega Predator threat eliminated!",
            ))
            del active[calamity_id]

    elif calamity_id == "robots":
        data["chips_found"] += progress
        if data["chips_found"] >= data["chips_needed"]:
            events.append(TurnEvent(
                step=0, event_type=TurnEventType.NARRATIVE,
                description="Robot shutdown signal sent! Rampage ended.",
            ))
            del active[calamity_id]

    elif calamity_id == "slyn_assault":
        data["slyn_kills"] += progress
        if data["slyn_kills"] >= data["kills_needed"]:
            state.grunts.count += 2
            events.append(TurnEvent(
                step=0, event_type=TurnEventType.NARRATIVE,
                description="Slyn threat neutralized! +2 Grunts recruited.",
            ))
            del active[calamity_id]

    elif calamity_id == "virus":
        data["cure_data"] += progress
        cure_roll = roll_d6("Virus cure check") if data["cure_data"] > 0 else None
        if cure_roll and cure_roll.total * 2 <= data["cure_data"]:
            events.append(TurnEvent(
                step=0, event_type=TurnEventType.NARRATIVE,
                description="Virus cure discovered! Outbreak contained.",
            ))
            del active[calamity_id]

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
            description="Enemy super weapon destroyed!",
        ))
        del active[calamity_id]

    state.tracking.active_calamities = active
    return events

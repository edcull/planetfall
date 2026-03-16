"""Post-Mission Finds table (D100) and Alien Artifacts table.

Rolled after victorious missions. Some results depend on whether
a scientist or scout survived the battle.
"""

from __future__ import annotations

from planetfall.engine.dice import roll_d100, roll_d6
from planetfall.engine.models import GameState, TurnEvent, TurnEventType


# D100 Post-Mission Finds table
POST_MISSION_FINDS = {
    (1, 25): {
        "id": "scientific_curiosities",
        "name": "Scientific Curiosities",
        "description": "Unusual specimens recovered from the field.",
        "rp": 2,
        "scientist_bonus_rp": 1,
    },
    (26, 35): {
        "id": "building_materials",
        "name": "Building Materials",
        "description": "Salvageable construction materials found on site.",
        "bp": 2,
    },
    (36, 60): {
        "id": "raw_materials",
        "name": "Raw Materials",
        "description": "Valuable raw materials recovered from the area.",
        "rm": 3,
    },
    (61, 70): {
        "id": "planetary_history",
        "name": "Hints of Planetary History",
        "description": "Ancient data fragments hint at the planet's past.",
        "sp": 1,
        "scientist_bonus_rp": 1,
    },
    (71, 80): {
        "id": "by_the_book",
        "name": "By the Book Victory",
        "description": "Textbook execution — the team learned from this one.",
        "xp_pick": 1,
        "scout_bonus_rm": 1,
    },
    (81, 95): {
        "id": "decisive_victory",
        "name": "Decisive Victory",
        "description": "A clear win that lifts the colony's spirits.",
        "morale": 1,
        "scout_bonus_rm": 1,
    },
    (96, 100): {
        "id": "ancient_sign",
        "name": "Ancient Sign",
        "description": "An alien artifact of unknown origin is uncovered.",
        "ancient_sign": 1,
        "scientist_bonus_rp": 1,
    },
}

# Alien Artifacts table (D100) — found via Delve missions / Ancient Sites
# Each artifact is unique per campaign; duplicates take next entry down.
ALIEN_ARTIFACTS = {
    (1, 3): {
        "name": "Flex-rigid Armor Vest", "type": "equipment",
        "effect": "4+ Armor Saving Throw.",
    },
    (4, 7): {
        "name": "Preventative Nano Deployment", "type": "colony",
        "effect": "Increase Colony Repair Rate by +1.",
    },
    (8, 10): {
        "name": "Ancient AI Chip", "type": "colony",
        "effect": "Gain one additional Research Point per campaign turn.",
    },
    (11, 13): {
        "name": "Inherent Core Principal Carbine", "type": "equipment",
        "effect": "Range 15\", Damage 2, Shots 1, +1 to hit.",
    },
    (14, 16): {
        "name": "Mutative Nano Materials", "type": "colony",
        "effect": "Gain one additional Build Point per campaign turn.",
    },
    (17, 19): {
        "name": "Short-range Phase Displacer", "type": "equipment",
        "effect": "When moving, character may teleport to any location within movement range.",
    },
    (20, 22): {
        "name": "Adjusted Bio-targeting Array", "type": "colony",
        "effect": "Increase Colony Defenses by +1.",
    },
    (23, 26): {
        "name": "Altered Psi-wave Emitter", "type": "single_use",
        "effect": "All characters in Sick Bay immediately recover completely.",
    },
    (27, 30): {
        "name": "Alien Translation Guide", "type": "single_use",
        "effect": "Next two research topics have RP cost halved (rounded up).",
    },
    (31, 34): {
        "name": "Bio-present Induction Schematic", "type": "single_use",
        "effect": "Gain 3 Augmentation Points.",
    },
    (35, 37): {
        "name": "Nervous System Override Cathode", "type": "equipment",
        "effect": "Character increases base Move and Dash distances by +1\" each.",
    },
    (38, 40): {
        "name": "Phase Anticipation Sword", "type": "equipment",
        "effect": "Weapon: Damage 2, Melee. No penalty when rolling 1 during brawl.",
    },
    (41, 44): {
        "name": "Programmed Restoration Settlement Module", "type": "single_use",
        "effect": "When activated, restore up to 10 points of Colony Integrity.",
    },
    (45, 47): {
        "name": "Regenerative Building Material Schematic", "type": "colony",
        "effect": "Mitigate 1 point of building damage per campaign turn.",
    },
    (48, 50): {
        "name": "Psi-boosted Nano-blade", "type": "equipment",
        "effect": "Weapon: Damage 2, Melee. Ignores Saving Throws.",
    },
    (51, 53): {
        "name": "Ancient Language Translation Aid", "type": "single_use",
        "effect": "Gain 3 Story Points and 1 Mission Data.",
    },
    (54, 56): {
        "name": "Visual Distortion Module", "type": "equipment",
        "effect": "All ranged attacks targeting the character take -1 hit penalty.",
    },
    (57, 59): {
        "name": "Flexible Bolt Launcher", "type": "equipment",
        "effect": "Weapon: Range 8\" Shots 2 Damage 1 OR Range 24\" Shots 1 Damage 2. Pick each time.",
    },
    (60, 63): {
        "name": "Neo-ancient Data Cache", "type": "single_use",
        "effect": "When activated, counts as completing a campaign Milestone.",
    },
    (64, 67): {
        "name": "Predictive Sighting Module", "type": "equipment",
        "effect": "Character may reroll all 1s on to-hit dice when firing.",
    },
    (68, 71): {
        "name": "Bio-frame Optimization Serum", "type": "single_use",
        "effect": "Permanently increase one character's Toughness by +1.",
    },
    (72, 75): {
        "name": "Transcendence Blueprints", "type": "single_use",
        "effect": "Increase Colony Morale by +4 and gain +1 Augmentation Points.",
    },
    (76, 79): {
        "name": "Time Dilution Serum", "type": "single_use",
        "effect": "Permanently increase one character's Speed by +1\".",
    },
    (80, 82): {
        "name": "Shard Projection Rifle", "type": "equipment",
        "effect": "Weapon: Range 24\", Shots 2, Damage 2, Focus (both shots same target).",
    },
    (83, 85): {
        "name": "Crystalline Assault Harness", "type": "equipment",
        "effect": "5+ Armor Saving Throw. When brawling, roll twice and pick best.",
    },
    (86, 88): {
        "name": "Focused Beam Emitter", "type": "equipment",
        "effect": "Weapon: Range 18\", Shots 1, Damage 4.",
    },
    (89, 92): {
        "name": "Organic Pattern Booster", "type": "single_use",
        "effect": "A character that just died can be restored to life.",
    },
    (93, 96): {
        "name": "Sub-psionic Visor", "type": "equipment",
        "effect": "Character may extend all visibility penalties by 4\".",
    },
    (97, 100): {
        "name": "Mind Induction Device", "type": "single_use",
        "effect": "Character immediately gains 5 XP. Gain 1 Mission Data.",
    },
}


def _lookup_table(table: dict, roll: int) -> dict:
    for (low, high), entry in table.items():
        if low <= roll <= high:
            return entry
    return {"name": "Nothing", "description": "Nothing found."}


def roll_single_find(label: str = "") -> tuple:
    """Roll on the post-mission finds table without applying effects.

    Returns (roll_total, find_entry) for reroll support.
    """
    roll = roll_d100(label or "Post-Mission Finds")
    find = _lookup_table(POST_MISSION_FINDS, roll.total)
    return roll.total, find


def apply_single_find(
    state: GameState, roll_total: int, find: dict,
    scientist_alive: bool = False,
    scout_alive: bool = False,
    xp_character_name: str | None = None,
) -> list[TurnEvent]:
    """Apply a single post-mission find result."""
    events = []
    desc = f"Post-Mission Find: {find['name']} — {find['description']}"
    changes = {}

    if find.get("rp"):
        state.colony.resources.research_points += find["rp"]
        changes["rp"] = find["rp"]
    if find.get("bp"):
        state.colony.resources.build_points += find["bp"]
        changes["bp"] = find["bp"]
    if find.get("rm"):
        state.colony.resources.raw_materials += find["rm"]
        changes["rm"] = find["rm"]
    if find.get("sp"):
        state.colony.resources.story_points += find["sp"]
        changes["sp"] = find["sp"]
    if find.get("morale"):
        state.colony.morale = min(20, state.colony.morale + find["morale"])
        changes["morale"] = find["morale"]

    got_sign = False
    if find.get("ancient_sign"):
        state.campaign.ancient_signs_count += find["ancient_sign"]
        changes["ancient_sign"] = find["ancient_sign"]
        desc += " +1 Ancient Sign!"
        got_sign = True

    if find.get("xp_pick") and xp_character_name:
        c = state.find_character(xp_character_name)
        if c:
            c.xp += find["xp_pick"]
            changes["xp"] = {xp_character_name: find["xp_pick"]}

    if scientist_alive and find.get("scientist_bonus_rp"):
        bonus = find["scientist_bonus_rp"]
        state.colony.resources.research_points += bonus
        desc += f" (Scientist bonus: +{bonus} RP)"
        changes["scientist_bonus_rp"] = bonus

    if scout_alive and find.get("scout_bonus_rm"):
        bonus = find["scout_bonus_rm"]
        state.colony.resources.raw_materials += bonus
        desc += f" (Scout bonus: +{bonus} Raw Materials)"
        changes["scout_bonus_rm"] = bonus

    events.append(TurnEvent(
        step=9, event_type=TurnEventType.COLONY_EVENT,
        description=desc, state_changes=changes,
    ))

    if got_sign:
        from planetfall.engine.campaign.ancient_signs import check_ancient_signs
        events.extend(check_ancient_signs(state))

    return events


def roll_post_mission_finds(
    state: GameState,
    scientist_alive: bool = False,
    scout_alive: bool = False,
    xp_character_name: str | None = None,
    num_rolls: int = 1,
) -> list[TurnEvent]:
    """Roll on the post-mission finds table.

    Args:
        scientist_alive: Whether a scientist survived the mission.
        scout_alive: Whether a scout survived the mission.
        xp_character_name: Character to receive XP from "by the book" result.
        num_rolls: Number of times to roll (usually 1, some conditions grant extra).
    """
    events = []
    for i in range(num_rolls):
        roll_total, find = roll_single_find(f"Post-Mission Finds (roll {i + 1})")
        events.extend(apply_single_find(
            state, roll_total, find,
            scientist_alive, scout_alive, xp_character_name,
        ))
    return events


def roll_alien_artifact(state: GameState) -> TurnEvent:
    """Roll on the alien artifacts table."""
    roll = roll_d100("Alien Artifact")
    artifact = _lookup_table(ALIEN_ARTIFACTS, roll.total)

    name = artifact["name"]
    atype = artifact.get("type", "single_use")
    effect = artifact.get("effect", "")

    # Check for duplicates
    found_artifacts = list(state.tracking.found_artifacts)
    if name in found_artifacts:
        # Reroll once on duplicate
        roll = roll_d100("Alien Artifact (reroll)")
        artifact = _lookup_table(ALIEN_ARTIFACTS, roll.total)
        name = artifact["name"]
        atype = artifact.get("type", "single_use")
        effect = artifact.get("effect", "")

    found_artifacts.append(name)
    state.tracking.found_artifacts = found_artifacts

    # Apply colony-level artifacts immediately
    if atype == "colony":
        if "Repair Rate" in effect:
            state.colony.per_turn_rates.repair_rate += 1
        if "Research Point per campaign turn" in effect:
            state.colony.per_turn_rates.research_points += 1
        if "Build Point per campaign turn" in effect:
            state.colony.per_turn_rates.build_points += 1
        if "Colony Defenses" in effect:
            state.colony.defenses += 1
        if "Colony Integrity" in effect:
            import re
            match = re.search(r'(\d+) points? of Colony Integrity', effect)
            if not match:
                match = re.search(r'\+?(\d+) Colony Integrity', effect)
            if match:
                state.colony.integrity += int(match.group(1))
        if "building damage" in effect:
            pass  # tracked as passive effect

    desc = f"Alien Artifact found: {name} ({atype}) — {effect}"
    return TurnEvent(
        step=9, event_type=TurnEventType.NARRATIVE,
        description=desc,
        state_changes={"artifact": name, "type": atype, "effect": effect},
    )

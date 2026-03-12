"""Tool definitions — 18 campaign step execution tools."""

from __future__ import annotations

TOOL_STEP01_RECOVERY = {
    "name": "step01_recovery",
    "description": "Execute Step 1: Recovery. Reduces sick bay turns for injured characters.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

TOOL_STEP02_REPAIRS = {
    "name": "step02_repairs",
    "description": (
        "Execute Step 2: Repairs. Spend raw materials to repair colony integrity."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "raw_materials_spent": {
                "type": "integer",
                "description": "Number of raw materials to spend on repairs (0 if none).",
                "default": 0,
            },
        },
        "required": [],
    },
}

TOOL_STEP03_SCOUT_EXPLORE = {
    "name": "step03_scout_explore",
    "description": "Execute Step 3a: Scout a sector to reveal its contents.",
    "input_schema": {
        "type": "object",
        "properties": {
            "sector_id": {
                "type": "integer",
                "description": "ID of the sector to explore.",
            },
        },
        "required": ["sector_id"],
    },
}

TOOL_STEP03_SCOUT_DISCOVERY = {
    "name": "step03_scout_discovery",
    "description": "Execute Step 3b: Roll on the Scout Discovery table for bonus finds.",
    "input_schema": {
        "type": "object",
        "properties": {
            "scout_name": {
                "type": "string",
                "description": "Name of the scout character (optional, gives bonus).",
            },
        },
        "required": [],
    },
}

TOOL_STEP04_ENEMY_ACTIVITY = {
    "name": "step04_enemy_activity",
    "description": "Execute Step 4: Enemy Activity. Rolls for enemy movements and threats.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

TOOL_STEP05_COLONY_EVENTS = {
    "name": "step05_colony_events",
    "description": "Execute Step 5: Colony Events. Rolls for random colony events.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

TOOL_STEP06_MISSION_DETERMINATION = {
    "name": "step06_mission_determination",
    "description": "Execute Step 6: Set the chosen mission for this turn.",
    "input_schema": {
        "type": "object",
        "properties": {
            "mission_type": {
                "type": "string",
                "description": "The chosen mission type (e.g. 'patrol', 'defense', 'raid').",
            },
            "sector_id": {
                "type": "integer",
                "description": "Sector ID for sector-based missions (optional).",
            },
        },
        "required": ["mission_type"],
    },
}

TOOL_STEP07_LOCK_AND_LOAD = {
    "name": "step07_lock_and_load",
    "description": "Execute Step 7: Deploy characters and grunts for the mission.",
    "input_schema": {
        "type": "object",
        "properties": {
            "deployed_characters": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Names of characters to deploy.",
            },
            "deployed_grunts": {
                "type": "integer",
                "description": "Number of grunts to deploy.",
                "default": 0,
            },
            "mission_type": {
                "type": "string",
                "description": "The mission type for deployment slot calculation.",
                "default": "patrol",
            },
        },
        "required": ["deployed_characters"],
    },
}

TOOL_STEP08_MISSION = {
    "name": "step08_mission",
    "description": (
        "Execute Step 8: Run the mission battle. Can run auto-battle or "
        "set up for manual resolution."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "mission_type": {
                "type": "string",
                "description": "The mission type.",
            },
            "auto_battle": {
                "type": "boolean",
                "description": "If true, run automated combat. If false, set up for manual play.",
                "default": False,
            },
            "deployed_names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Character names deployed (needed for auto-battle).",
            },
            "grunt_count": {
                "type": "integer",
                "description": "Number of grunts deployed.",
                "default": 0,
            },
        },
        "required": ["mission_type"],
    },
}

TOOL_REPORT_MISSION_RESULT = {
    "name": "report_mission_result",
    "description": (
        "Report the outcome of a manually-resolved mission. Use this after "
        "the player has resolved combat on the tabletop."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "victory": {
                "type": "boolean",
                "description": "Whether the player won the mission.",
            },
            "character_casualties": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Names of characters who became casualties.",
            },
            "grunt_casualties": {
                "type": "integer",
                "description": "Number of grunts who became casualties.",
                "default": 0,
            },
        },
        "required": ["victory"],
    },
}

TOOL_STEP09_INJURIES = {
    "name": "step09_injuries",
    "description": "Execute Step 9: Roll for injuries on casualties.",
    "input_schema": {
        "type": "object",
        "properties": {
            "character_casualties": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Names of characters who were casualties.",
            },
            "grunt_casualties": {
                "type": "integer",
                "description": "Number of grunts who were casualties.",
                "default": 0,
            },
        },
        "required": ["character_casualties"],
    },
}

TOOL_STEP10_AWARD_XP = {
    "name": "step10_award_xp",
    "description": "Execute Step 10a: Award mission XP to deployed characters.",
    "input_schema": {
        "type": "object",
        "properties": {
            "deployed": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Names of deployed characters.",
            },
            "casualties": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Names of character casualties.",
            },
        },
        "required": ["deployed", "casualties"],
    },
}

TOOL_STEP10_ADVANCEMENT = {
    "name": "step10_advancement",
    "description": "Execute Step 10b: Spend 5 XP to roll advancement for a character.",
    "input_schema": {
        "type": "object",
        "properties": {
            "character_name": {
                "type": "string",
                "description": "Name of the character to advance.",
            },
        },
        "required": ["character_name"],
    },
}

TOOL_STEP11_MORALE = {
    "name": "step11_morale",
    "description": (
        "Execute Step 11: Colony Morale Adjustments. "
        "Automatically drops 1 per turn + 1 per battle casualty. "
        "Checks for Morale Incident at -10 or worse."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "battle_casualties": {
                "type": "integer",
                "description": (
                    "Total number of battle casualties (characters + grunts "
                    "who became casualties during the mission)."
                ),
                "default": 0,
            },
            "mission_type": {
                "type": "string",
                "description": (
                    "Mission type played this turn (e.g. 'rescue', 'patrol'). "
                    "Rescue missions don't suffer morale loss from squad casualties."
                ),
            },
            "mission_victory": {
                "type": "boolean",
                "description": "Whether the mission was won (used for Crisis resolution).",
            },
        },
        "required": [],
    },
}

TOOL_STEP12_TRACKING = {
    "name": "step12_tracking",
    "description": "Execute Step 12: Track enemy info and mission data.",
    "input_schema": {
        "type": "object",
        "properties": {
            "mission_type": {
                "type": "string",
                "description": "The mission type that was played.",
            },
            "mission_victory": {
                "type": "boolean",
                "description": "Whether the mission was won.",
            },
        },
        "required": ["mission_type", "mission_victory"],
    },
}

TOOL_STEP13_REPLACEMENTS = {
    "name": "step13_replacements",
    "description": "Execute Step 13: Check for and apply replacements (new recruits/equipment).",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

TOOL_STEP14_RESEARCH = {
    "name": "step14_research",
    "description": (
        "Execute Step 14: Research. Gain RP and optionally invest in a theory, "
        "unlock an application, or perform bio-analysis."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "theory_id": {
                "type": "string",
                "description": "ID of theory to invest RP in.",
            },
            "theory_rp": {
                "type": "integer",
                "description": "Amount of RP to invest in the theory.",
                "default": 0,
            },
            "application_id": {
                "type": "string",
                "description": "ID of application to unlock.",
            },
            "bio_analysis": {
                "type": "boolean",
                "description": "Whether to perform bio-analysis (costs 3 RP).",
                "default": False,
            },
        },
        "required": [],
    },
}

TOOL_STEP15_BUILDING = {
    "name": "step15_building",
    "description": (
        "Execute Step 15: Building. Gain BP and optionally invest in a building."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "building_id": {
                "type": "string",
                "description": "ID of building to invest BP in.",
            },
            "bp_amount": {
                "type": "integer",
                "description": "Amount of BP to invest.",
                "default": 0,
            },
            "raw_materials_convert": {
                "type": "integer",
                "description": "Raw materials to convert to BP (max 3/turn).",
                "default": 0,
            },
        },
        "required": [],
    },
}

TOOL_STEP16_COLONY_INTEGRITY = {
    "name": "step16_colony_integrity",
    "description": "Execute Step 16: Check and update colony integrity.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

TOOL_STEP17_CHARACTER_EVENT = {
    "name": "step17_character_event",
    "description": "Execute Step 17: Roll for character events.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

TOOL_STEP18_UPDATE_SHEET = {
    "name": "step18_update_sheet",
    "description": "Execute Step 18: Finalize and save the turn state.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

STEP_TOOLS = [
    TOOL_STEP01_RECOVERY,
    TOOL_STEP02_REPAIRS,
    TOOL_STEP03_SCOUT_EXPLORE,
    TOOL_STEP03_SCOUT_DISCOVERY,
    TOOL_STEP04_ENEMY_ACTIVITY,
    TOOL_STEP05_COLONY_EVENTS,
    TOOL_STEP06_MISSION_DETERMINATION,
    TOOL_STEP07_LOCK_AND_LOAD,
    TOOL_STEP08_MISSION,
    TOOL_REPORT_MISSION_RESULT,
    TOOL_STEP09_INJURIES,
    TOOL_STEP10_AWARD_XP,
    TOOL_STEP10_ADVANCEMENT,
    TOOL_STEP11_MORALE,
    TOOL_STEP12_TRACKING,
    TOOL_STEP13_REPLACEMENTS,
    TOOL_STEP14_RESEARCH,
    TOOL_STEP15_BUILDING,
    TOOL_STEP16_COLONY_INTEGRITY,
    TOOL_STEP17_CHARACTER_EVENT,
    TOOL_STEP18_UPDATE_SHEET,
]

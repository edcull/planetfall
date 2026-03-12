"""Tool definitions — campaign management (augmentation, equipment, extraction, etc.)."""

from __future__ import annotations

# --- Augmentation ---

TOOL_GET_AUGMENTATION_OPTIONS = {
    "name": "get_augmentation_options",
    "description": (
        "Get available colony-wide augmentations, including next cost and affordability. "
        "Augmentations apply to ALL current and future characters."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
    },
}

TOOL_APPLY_AUGMENTATION = {
    "name": "apply_augmentation",
    "description": (
        "Purchase a colony-wide augmentation. Applies to all characters. "
        "Progressive cost: 1st=1AP, 2nd=2AP, etc. Max one per turn."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "augmentation_id": {
                "type": "string",
                "description": "ID of the augmentation to apply.",
            },
        },
        "required": ["augmentation_id"],
    },
}

# --- Equipment ---

TOOL_GET_ARMORY = {
    "name": "get_armory",
    "description": "Get the armory catalog with available items and affordability.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

TOOL_PURCHASE_EQUIPMENT = {
    "name": "purchase_equipment",
    "description": "Purchase an item from the armory and give it to a character.",
    "input_schema": {
        "type": "object",
        "properties": {
            "item_id": {
                "type": "string",
                "description": "ID of the item to purchase.",
            },
            "character_name": {
                "type": "string",
                "description": "Name of the character to equip.",
            },
        },
        "required": ["item_id", "character_name"],
    },
}

TOOL_SWAP_EQUIPMENT = {
    "name": "swap_equipment",
    "description": "Transfer an equipment item from one character to another.",
    "input_schema": {
        "type": "object",
        "properties": {
            "from_character": {
                "type": "string",
                "description": "Name of the character giving the item.",
            },
            "to_character": {
                "type": "string",
                "description": "Name of the character receiving the item.",
            },
            "item_name": {
                "type": "string",
                "description": "Name of the equipment item to transfer.",
            },
        },
        "required": ["from_character", "to_character", "item_name"],
    },
}

TOOL_SELL_EQUIPMENT = {
    "name": "sell_equipment",
    "description": "Sell a character's equipment for raw materials.",
    "input_schema": {
        "type": "object",
        "properties": {
            "character_name": {
                "type": "string",
                "description": "Name of the character selling.",
            },
            "item_name": {
                "type": "string",
                "description": "Name of the item to sell.",
            },
        },
        "required": ["character_name", "item_name"],
    },
}

# --- Extraction ---

TOOL_GET_EXPLOITABLE_SECTORS = {
    "name": "get_exploitable_sectors",
    "description": "Get sectors available for resource extraction.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

TOOL_START_EXTRACTION = {
    "name": "start_extraction",
    "description": "Begin exploiting a sector for resources.",
    "input_schema": {
        "type": "object",
        "properties": {
            "sector_id": {
                "type": "integer",
                "description": "Sector to exploit.",
            },
            "resource_type": {
                "type": "string",
                "description": "Type: 'raw_materials', 'research_points', or 'build_points'.",
                "default": "raw_materials",
            },
        },
        "required": ["sector_id"],
    },
}

TOOL_STOP_EXTRACTION = {
    "name": "stop_extraction",
    "description": "Stop exploiting a sector.",
    "input_schema": {
        "type": "object",
        "properties": {
            "sector_id": {
                "type": "integer",
                "description": "Sector to stop exploiting.",
            },
        },
        "required": ["sector_id"],
    },
}

TOOL_GET_ACTIVE_EXTRACTIONS = {
    "name": "get_active_extractions",
    "description": "Get sectors currently being exploited for resources.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

# --- Calamity ---

TOOL_CHECK_CALAMITY = {
    "name": "check_calamity",
    "description": "Check if a calamity is triggered (called after milestones).",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

TOOL_RESOLVE_CALAMITY = {
    "name": "resolve_calamity",
    "description": "Record progress toward resolving an active calamity.",
    "input_schema": {
        "type": "object",
        "properties": {
            "calamity_id": {
                "type": "string",
                "description": "Which calamity to progress.",
            },
            "progress": {
                "type": "integer",
                "description": "Amount of progress (kills, chips, etc.).",
                "default": 1,
            },
        },
        "required": ["calamity_id"],
    },
}

# --- Slyn ---

TOOL_CHECK_SLYN = {
    "name": "check_slyn_interference",
    "description": "Check if the Slyn interfere with the current mission.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

TOOL_RECORD_SLYN_KILLS = {
    "name": "record_slyn_kills",
    "description": "Record Slyn kills and check if they depart.",
    "input_schema": {
        "type": "object",
        "properties": {
            "kills": {
                "type": "integer",
                "description": "Number of Slyn killed.",
            },
        },
        "required": ["kills"],
    },
}

# --- Ancient Signs ---

TOOL_CHECK_ANCIENT_SIGNS = {
    "name": "check_ancient_signs",
    "description": "Check if accumulated ancient signs trigger a new site discovery.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

TOOL_EXPLORE_ANCIENT_SITE = {
    "name": "explore_ancient_site",
    "description": "Explore an ancient site for mission data breakthrough.",
    "input_schema": {
        "type": "object",
        "properties": {
            "sector_id": {
                "type": "integer",
                "description": "Sector containing the ancient site.",
            },
        },
        "required": ["sector_id"],
    },
}

# --- Post-Mission & Battlefield ---

TOOL_ROLL_POST_MISSION_FINDS = {
    "name": "roll_post_mission_finds",
    "description": "Roll on the post-mission finds table after a victory.",
    "input_schema": {
        "type": "object",
        "properties": {
            "scientist_alive": {
                "type": "boolean",
                "description": "Whether a scientist survived.",
                "default": False,
            },
            "scout_alive": {
                "type": "boolean",
                "description": "Whether a scout survived.",
                "default": False,
            },
            "xp_character_name": {
                "type": "string",
                "description": "Character to receive XP from 'by the book' result.",
            },
            "num_rolls": {
                "type": "integer",
                "description": "Number of rolls (extra from battlefield conditions).",
                "default": 1,
            },
        },
        "required": [],
    },
}

TOOL_GET_BATTLEFIELD_CONDITION = {
    "name": "get_battlefield_condition",
    "description": "Get or generate the battlefield condition for this turn's mission.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

# --- Save/Load ---

TOOL_SAVE_GAME = {
    "name": "save_game",
    "description": "Save the current game state to disk.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

# --- Campaign Log & Rollback ---

TOOL_EXPORT_TURN_LOG = {
    "name": "export_turn_log",
    "description": "Export the current turn's events as a markdown log file.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

TOOL_EXPORT_CAMPAIGN_LOG = {
    "name": "export_campaign_log",
    "description": "Export the full campaign history as a markdown file.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

TOOL_UNDO_LAST_TURN = {
    "name": "undo_last_turn",
    "description": "Undo the last turn by rolling back to the previous snapshot.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

TOOL_ROLLBACK_TO_TURN = {
    "name": "rollback_to_turn",
    "description": "Roll back to a specific turn number. Deletes snapshots after that turn.",
    "input_schema": {
        "type": "object",
        "properties": {
            "turn": {
                "type": "integer",
                "description": "Turn number to roll back to.",
            },
        },
        "required": ["turn"],
    },
}

TOOL_LIST_SNAPSHOTS = {
    "name": "list_snapshots",
    "description": "List available turn snapshots for the current campaign.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

CAMPAIGN_TOOLS = [
    # Augmentation
    TOOL_GET_AUGMENTATION_OPTIONS,
    TOOL_APPLY_AUGMENTATION,
    # Equipment
    TOOL_GET_ARMORY,
    TOOL_PURCHASE_EQUIPMENT,
    TOOL_SWAP_EQUIPMENT,
    TOOL_SELL_EQUIPMENT,
    # Extraction
    TOOL_GET_EXPLOITABLE_SECTORS,
    TOOL_START_EXTRACTION,
    TOOL_STOP_EXTRACTION,
    TOOL_GET_ACTIVE_EXTRACTIONS,
    # Calamity
    TOOL_CHECK_CALAMITY,
    TOOL_RESOLVE_CALAMITY,
    # Slyn
    TOOL_CHECK_SLYN,
    TOOL_RECORD_SLYN_KILLS,
    # Ancient Signs
    TOOL_CHECK_ANCIENT_SIGNS,
    TOOL_EXPLORE_ANCIENT_SITE,
    # Post-Mission & Battlefield
    TOOL_ROLL_POST_MISSION_FINDS,
    TOOL_GET_BATTLEFIELD_CONDITION,
    # Save/Load
    TOOL_SAVE_GAME,
    # Campaign Log & Rollback
    TOOL_EXPORT_TURN_LOG,
    TOOL_EXPORT_CAMPAIGN_LOG,
    TOOL_UNDO_LAST_TURN,
    TOOL_ROLLBACK_TO_TURN,
    TOOL_LIST_SNAPSHOTS,
]

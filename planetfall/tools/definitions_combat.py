"""Tool definitions — interactive combat and narrative tools."""

from __future__ import annotations

TOOL_COMBAT_START = {
    "name": "combat_start",
    "description": (
        "Start an interactive combat session. Sets up the battlefield and "
        "begins round 1. Returns the battlefield state, reaction rolls, and "
        "available actions for the first player figure. The player makes "
        "tactical decisions each activation."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "mission_type": {
                "type": "string",
                "description": "The mission type.",
            },
            "deployed_names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Character names to deploy.",
            },
            "grunt_count": {
                "type": "integer",
                "description": "Number of grunts to deploy.",
                "default": 0,
            },
        },
        "required": ["mission_type", "deployed_names"],
    },
}

TOOL_COMBAT_ACTION = {
    "name": "combat_action",
    "description": (
        "Execute a player's chosen combat action during interactive battle. "
        "Pass the action index from the available_actions list. Returns updated "
        "battlefield state with narrative description of what happened."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action_index": {
                "type": "integer",
                "description": "Index of the chosen action from available_actions.",
            },
        },
        "required": ["action_index"],
    },
}

TOOL_COMBAT_ADVANCE = {
    "name": "combat_advance",
    "description": (
        "Advance combat to the next phase (enemy phase, end phase, next round). "
        "Called when there are no player decisions needed. Returns updated state "
        "with narrative of what happened."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

TOOL_COMBAT_STATUS = {
    "name": "combat_status",
    "description": "Get the current combat battlefield status and available actions.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

TOOL_COMBAT_NARRATE = {
    "name": "combat_narrate",
    "description": (
        "Generate a narrative description of the current combat phase. "
        "Call after resolving actions to get atmospheric prose about what happened."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

TOOL_GENERATE_NARRATIVE = {
    "name": "generate_narrative",
    "description": (
        "Generate a narrative passage for the current turn's events. "
        "Uses local template-based generation (or Claude API if configured)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "context": {
                "type": "string",
                "description": "Narrative context: 'battle', 'colony_event', 'character_event', or 'turn_end'.",
                "default": "turn_end",
            },
        },
        "required": [],
    },
}

TOOL_GET_NARRATIVE_SUMMARY = {
    "name": "get_narrative_summary",
    "description": "Get a brief narrative summary of the campaign so far.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

COMBAT_TOOLS = [
    TOOL_COMBAT_START,
    TOOL_COMBAT_ACTION,
    TOOL_COMBAT_ADVANCE,
    TOOL_COMBAT_STATUS,
    TOOL_COMBAT_NARRATE,
    TOOL_GENERATE_NARRATIVE,
    TOOL_GET_NARRATIVE_SUMMARY,
]

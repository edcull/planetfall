"""Tool definitions — game state queries and rules lookup."""

from __future__ import annotations

TOOL_GET_STATE_SUMMARY = {
    "name": "get_state_summary",
    "description": (
        "Get a summary of the current game state including colony status, "
        "resources, character roster, and campaign progress."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

TOOL_GET_RESEARCH_OPTIONS = {
    "name": "get_research_options",
    "description": (
        "Get available research options: theories to invest in, "
        "applications to unlock, and current RP balance."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

TOOL_GET_BUILDING_OPTIONS = {
    "name": "get_building_options",
    "description": (
        "Get available building options: buildings to construct, "
        "in-progress constructions, and current BP/RM balance."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

TOOL_GET_SCOUTING_OPTIONS = {
    "name": "get_scouting_options",
    "description": (
        "Get available scouting options for Step 3: unexplored sectors to scout, "
        "and available scout-class characters who can lead discovery rolls."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

TOOL_GET_MISSION_OPTIONS = {
    "name": "get_mission_options",
    "description": "Get available mission types for this turn.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

TOOL_GET_DEPLOYMENT_OPTIONS = {
    "name": "get_deployment_options",
    "description": (
        "Get available characters for deployment and max deployment slots "
        "for the given mission type."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "mission_type": {
                "type": "string",
                "description": "The mission type to check deployment slots for.",
            },
        },
        "required": ["mission_type"],
    },
}

TOOL_LOAD_RULES_SECTION = {
    "name": "load_rules_section",
    "description": (
        "Load a section of the game rules for reference. Available sections: "
        "introduction, char_creation, char_backgrounds, administrator, "
        "combat_overview, combat_ai, combat_movement, combat_shooting, "
        "combat_damage, contacts_aid_panic, initial_missions, "
        "campaign_overview, campaign_setup, turn_steps_1_to_5, "
        "turn_steps_6_to_9, turn_steps_10_to_18, char_roleplay_events, "
        "armory, colonies_overview, colony_integrity, colony_morale, "
        "research, buildings, augmentation, tech_tree, missions_overview, "
        "battlefield_conditions, mission_briefings, post_mission_finds, "
        "battlefield_setup, enemy_generation, campaign_development, "
        "milestones, calamities, quick_reference."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "section_name": {
                "type": "string",
                "description": "Name of the rules section to load.",
            },
        },
        "required": ["section_name"],
    },
}

TOOL_SEARCH_RULES = {
    "name": "search_rules",
    "description": "Search the full rules text for a keyword or phrase.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The text to search for in the rules.",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results (default 5).",
                "default": 5,
            },
        },
        "required": ["query"],
    },
}

QUERY_TOOLS = [
    TOOL_GET_STATE_SUMMARY,
    TOOL_GET_RESEARCH_OPTIONS,
    TOOL_GET_BUILDING_OPTIONS,
    TOOL_GET_SCOUTING_OPTIONS,
    TOOL_GET_MISSION_OPTIONS,
    TOOL_GET_DEPLOYMENT_OPTIONS,
    TOOL_LOAD_RULES_SECTION,
    TOOL_SEARCH_RULES,
]

"""Claude tool_use schema definitions for the Planetfall orchestrator.

Each tool maps to a game engine function. The orchestrator calls these
tools to drive the 18-step campaign turn, combat, and player queries.

Definitions are split across domain modules and aggregated here.
"""

from __future__ import annotations

from planetfall.tools.definitions_queries import QUERY_TOOLS
from planetfall.tools.definitions_steps import STEP_TOOLS
from planetfall.tools.definitions_combat import COMBAT_TOOLS
from planetfall.tools.definitions_campaign import CAMPAIGN_TOOLS

ALL_TOOLS = QUERY_TOOLS + STEP_TOOLS + COMBAT_TOOLS + CAMPAIGN_TOOLS

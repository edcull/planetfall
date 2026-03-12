"""Rules text section loader.

Loads pre-chunked rules sections from the sections/ directory. Falls back
to extracting from the full rules text if a section file doesn't exist.
This keeps the orchestrator's context small (~5-15K tokens per step
instead of ~125K for the full document).
"""

from __future__ import annotations

import os
from pathlib import Path

# Path to the full rules text
RULES_FILE = Path(__file__).parent.parent.parent / "5PFH Planetfall Digital Final.txt"

# Path to pre-chunked section files
SECTIONS_DIR = Path(__file__).parent / "sections"

# Section definitions: name -> (start_line, end_line) inclusive, 1-indexed
# Used as fallback when section files don't exist.
SECTION_RANGES: dict[str, tuple[int, int]] = {
    "introduction":         (236, 400),
    "char_creation":        (401, 900),
    "char_backgrounds":     (900, 1200),
    "administrator":        (1200, 1350),
    "combat_overview":      (1350, 1550),
    "combat_ai":            (1550, 1750),
    "combat_movement":      (1750, 1900),
    "combat_shooting":      (1900, 2150),
    "combat_damage":        (2150, 2450),
    "contacts_aid_panic":   (2450, 2600),
    "initial_missions":     (2600, 2850),
    "campaign_overview":    (2850, 3050),
    "campaign_setup":       (3050, 3400),
    "turn_steps_1_to_5":    (3400, 3900),
    "turn_steps_6_to_9":    (3900, 4300),
    "turn_steps_10_to_18":  (4300, 4800),
    "char_roleplay_events": (4800, 5100),
    "armory":               (5100, 5500),
    "colonies_overview":    (5500, 5800),
    "colony_integrity":     (5800, 5950),
    "colony_morale":        (5950, 6100),
    "research":             (6100, 6400),
    "buildings":            (6400, 6900),
    "augmentation":         (6900, 7050),
    "tech_tree":            (7050, 7250),
    "missions_overview":    (7250, 7500),
    "battlefield_conditions": (7500, 7750),
    "mission_briefings":    (7750, 8650),
    "post_mission_finds":   (8650, 8850),
    "battlefield_setup":    (8850, 9200),
    "enemy_generation":     (9200, 9650),
    "campaign_development": (9650, 9950),
    "milestones":           (9950, 10150),
    "calamities":           (10150, 10465),
    "quick_reference":      (10465, 10681),
}

# Cache loaded sections
_cache: dict[str, str] = {}
_full_text: list[str] | None = None


def _load_full_text() -> list[str]:
    """Load the full rules file into memory (once)."""
    global _full_text
    if _full_text is None:
        if not RULES_FILE.exists():
            raise FileNotFoundError(f"Rules file not found: {RULES_FILE}")
        with open(RULES_FILE, "r", encoding="utf-8-sig") as f:
            _full_text = f.readlines()
    return _full_text


def _load_section_from_file(section_name: str) -> str | None:
    """Try to load a section from its pre-chunked file."""
    section_file = SECTIONS_DIR / f"{section_name}.txt"
    if section_file.exists():
        with open(section_file, "r", encoding="utf-8") as f:
            return f.read()
    return None


def _load_section_from_ranges(section_name: str) -> str:
    """Extract a section from the full rules text using line ranges."""
    start, end = SECTION_RANGES[section_name]
    lines = _load_full_text()
    start_idx = max(0, start - 1)
    end_idx = min(len(lines), end)
    return "".join(lines[start_idx:end_idx])


def load_section(section_name: str) -> str:
    """Load a named rules section.

    Tries the pre-chunked section file first, falls back to extracting
    from the full rules text.

    Returns the text content for the given section name.
    Raises KeyError if section name is unknown.
    """
    if section_name in _cache:
        return _cache[section_name]

    if section_name not in SECTION_RANGES:
        raise KeyError(
            f"Unknown rules section: '{section_name}'. "
            f"Available: {list(SECTION_RANGES.keys())}"
        )

    # Try section file first, fall back to full text extraction
    section_text = _load_section_from_file(section_name)
    if section_text is None:
        section_text = _load_section_from_ranges(section_name)

    _cache[section_name] = section_text
    return section_text


def list_sections() -> list[str]:
    """Return all available section names."""
    return list(SECTION_RANGES.keys())


def search_rules(query: str, max_results: int = 5) -> list[tuple[int, str]]:
    """Search the full rules text for a query string.

    Returns list of (line_number, line_text) tuples.
    """
    lines = _load_full_text()
    query_lower = query.lower()
    results = []
    for i, line in enumerate(lines, 1):
        if query_lower in line.lower():
            results.append((i, line.strip()))
            if len(results) >= max_results:
                break
    return results


def get_section_for_step(step: int) -> str:
    """Get the relevant rules section for a campaign turn step."""
    step_sections = {
        1: "turn_steps_1_to_5",
        2: "turn_steps_1_to_5",
        3: "turn_steps_1_to_5",
        4: "turn_steps_1_to_5",
        5: "turn_steps_1_to_5",
        6: "turn_steps_6_to_9",
        7: "turn_steps_6_to_9",
        8: "turn_steps_6_to_9",
        9: "turn_steps_6_to_9",
        10: "turn_steps_10_to_18",
        11: "turn_steps_10_to_18",
        12: "turn_steps_10_to_18",
        13: "turn_steps_10_to_18",
        14: "turn_steps_10_to_18",
        15: "turn_steps_10_to_18",
        16: "turn_steps_10_to_18",
        17: "turn_steps_10_to_18",
        18: "turn_steps_10_to_18",
    }
    section_name = step_sections.get(step, "campaign_overview")
    return load_section(section_name)

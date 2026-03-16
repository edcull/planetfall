"""Schema migration system for Planetfall save files.

Each migration function transforms a raw JSON dict from one schema version
to the next.  ``apply_migrations`` walks through every outstanding migration
in order so that the dict is ready to be validated into a ``GameState``.
"""

from __future__ import annotations

from typing import Callable

# Bump this whenever GameState's shape changes and add a corresponding
# migration entry in MIGRATIONS below.
CURRENT_SCHEMA_VERSION: int = 1


def _migrate_v0_to_v1(data: dict) -> dict:
    """v0 -> v1: normalise sector status names.

    * ``"unknown"``      -> ``"unexplored"``
    * ``"investigated"`` -> ``"explored"``
    """
    if "campaign_map" in data and "sectors" in data["campaign_map"]:
        for sector in data["campaign_map"]["sectors"]:
            status = sector.get("status")
            if status == "unknown":
                sector["status"] = "unexplored"
            elif status == "investigated":
                sector["status"] = "explored"
    return data


# Map *source* version -> function that migrates to the next version.
# E.g. MIGRATIONS[0] upgrades a v0 save to v1.
MIGRATIONS: dict[int, Callable[[dict], dict]] = {
    0: _migrate_v0_to_v1,
}


def apply_migrations(data: dict) -> dict:
    """Apply all outstanding migrations to *data* (mutated in-place) and return it.

    The version is read from ``data["schema_version"]`` (defaulting to ``0``
    for saves that pre-date versioning).  Each migration is applied in order
    until the data reaches ``CURRENT_SCHEMA_VERSION``.
    """
    version = data.get("schema_version", 0)

    if version > CURRENT_SCHEMA_VERSION:
        raise ValueError(
            f"Save file schema version {version} is newer than "
            f"supported version {CURRENT_SCHEMA_VERSION}. "
            f"Please update the game to load this save."
        )

    while version < CURRENT_SCHEMA_VERSION:
        migration = MIGRATIONS.get(version)
        if migration is None:
            raise ValueError(
                f"No migration defined for schema version {version} -> {version + 1}. "
                f"Cannot upgrade save to version {CURRENT_SCHEMA_VERSION}."
            )
        data = migration(data)
        version += 1
        data["schema_version"] = version

    return data

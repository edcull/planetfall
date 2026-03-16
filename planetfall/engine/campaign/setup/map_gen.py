"""Campaign map generation — terrain, sectors, investigation sites, naming."""

from __future__ import annotations

import random
from typing import Optional

from planetfall.engine.models import (
    CampaignMap,
    Sector,
    SectorQuality,
    SectorStatus,
)


def generate_campaign_map(
    rows: int = 6,
    cols: int = 6,
    colony_sector: Optional[int] = None,
    num_investigation_sites: int = 10,
    colony_name: str = "the colony",
    api_key: str = "",
) -> CampaignMap:
    """Generate the campaign map with sectors, investigation sites, and ancient signs."""
    from planetfall.engine.models import SectorTerrain
    total_sectors = rows * cols

    # Terrain distribution weights
    terrain_weights = [
        (SectorTerrain.PLAINS, 4),
        (SectorTerrain.FOREST, 3),
        (SectorTerrain.HILLS, 3),
        (SectorTerrain.RUINS, 2),
        (SectorTerrain.WETLANDS, 2),
        (SectorTerrain.CRAGS, 2),
        (SectorTerrain.DESERT, 2),
        (SectorTerrain.TUNDRA, 2),
    ]
    terrain_pool = [t for t, w in terrain_weights for _ in range(w)]

    # Create sectors with terrain
    sectors = []
    for i in range(total_sectors):
        terrain = random.choice(terrain_pool)
        sectors.append(Sector(sector_id=i, terrain=terrain))

    # Assign sector qualities — ~20% get difficult ground,
    # biased toward terrains that naturally produce rough footing
    _DG_LIKELY = {
        SectorTerrain.WETLANDS, SectorTerrain.FOREST,
        SectorTerrain.DESERT, SectorTerrain.TUNDRA,
        SectorTerrain.RUINS, SectorTerrain.CRAGS,
    }
    for s in sectors:
        # 35% chance for thematic terrains, 10% for others
        chance = 0.35 if s.terrain in _DG_LIKELY else 0.10
        if random.random() < chance:
            s.qualities.append(SectorQuality.DIFFICULT_GROUND)

    # Place colony centrally (within the center 2x2 area)
    if colony_sector is None:
        center_rows = [rows // 2 - 1, rows // 2]
        center_cols = [cols // 2 - 1, cols // 2]
        center_sectors = [r * cols + c for r in center_rows for c in center_cols]
        colony_sector = random.choice(center_sectors)
    sectors[colony_sector].status = SectorStatus.EXPLOITED
    sectors[colony_sector].terrain = SectorTerrain.PLAINS
    sectors[colony_sector].qualities.clear()
    sectors[colony_sector].name = colony_name
    sectors[colony_sector].notes = "Colony"

    # Place investigation sites
    available = [
        s.sector_id for s in sectors
        if s.sector_id != colony_sector
    ]
    random.shuffle(available)
    for i in range(min(num_investigation_sites, len(available))):
        sectors[available[i]].has_investigation_site = True

    # Place ancient signs
    remaining = [
        sid for sid in available[num_investigation_sites:]
    ] + [
        sid for sid in available[:num_investigation_sites]
    ]
    # Ancient signs are discovered during gameplay (scouting, colony events),
    # not pre-placed on the map at campaign creation.

    # Generate sector names
    _generate_sector_names(
        sectors, rows, cols, colony_sector, colony_name, api_key,
    )

    return CampaignMap(sectors=sectors, colony_sector_id=colony_sector)


def _generate_sector_names(
    sectors: list[Sector],
    rows: int,
    cols: int,
    colony_sector: int,
    colony_name: str,
    api_key: str,
) -> None:
    """Generate sector names — via Haiku API if available, else local fallback."""
    if api_key:
        try:
            _generate_sector_names_api(
                sectors, rows, cols, colony_sector, colony_name, api_key,
            )
            return
        except Exception:
            pass
    _generate_sector_names_local(sectors, rows, cols, colony_sector, colony_name)


def _generate_sector_names_local(
    sectors: list[Sector],
    rows: int,
    cols: int,
    colony_sector: int,
    colony_name: str,
) -> None:
    """Generate sector names using deterministic templates."""
    # Terrain-flavoured name pools
    terrain_names: dict[str, list[str]] = {
        "plains": [
            "Windswept Flats", "Pale Steppe", "Dust Bowl", "The Expanse",
            "Open Range", "Razor Grass Fields", "Amber Prairie", "Salt Flat Delta",
            "Bleached Mesa", "Horizon Span", "Flatline Basin", "Sunscorch Reach",
        ],
        "forest": [
            "Thornwood Canopy", "Deeproot Hollow", "Sporeveil Thicket", "Tanglewood",
            "Fungal Maze", "Whisper Groves", "Ironbark Stand", "Biolume Forest",
            "Verdant Snarl", "Mosswall Stretch", "Rootcrawl Depths", "Lichen Veil",
        ],
        "hills": [
            "Ridgeline Overlook", "Broken Ridge", "Shale Heights", "Wind-Cut Bluffs",
            "Signal Hilltop", "Granite Rise", "Tumblerock Slopes", "Kestrel Ridge",
            "Escarpment Row", "Chalk Downs", "Stormwatch Heights", "Crest Line",
        ],
        "ruins": [
            "Fallen Outpost", "Shattered Hab", "Dead Colony Site", "Wreck Field",
            "Corroded Foundry", "Rubble Quarter", "Ghost Settlement", "Blast Crater Ruins",
            "Sunken Terminal", "Scrap Yard Delta", "Hollow Bunkers", "Ash District",
        ],
        "wetlands": [
            "Mire Crossing", "Bogflat Basin", "Reed Maze", "Stagnant Pools",
            "Swamplight Hollow", "Peat Morass", "Marsh Trail", "Flooded Lowlands",
            "Vapor Fen", "Siltwater Reach", "Brackish Delta", "Fogmire Flats",
        ],
        "crags": [
            "Jagged Pinnacles", "Obsidian Spires", "Shatter Canyon", "Needlerock Pass",
            "Crystal Fissure", "Basalt Towers", "Broken Teeth", "Ironstone Narrows",
            "Crag Labyrinth", "Splinter Ridge", "Gorge Passage", "Shard Valley",
        ],
        "desert": [
            "Glass Sand Dunes", "Thermal Waste", "Scorched Basin", "Ember Flats",
            "Suncrest Barrens", "Dust Devil Alley", "Parched Expanse", "Mirage Reach",
            "Cinder Fields", "Bone Dry Gulch", "Heat Shimmer Waste", "Red Sand Corridor",
        ],
        "tundra": [
            "Permafrost Shelf", "Ice Shear Plains", "Frozen Reach", "Glacial Moraine",
            "Whiteout Ridge", "Frost Hollow", "Snowdrift Waste", "Cryo-Vent Fields",
            "Rime Expanse", "Frostbite Flats", "Gelid Basin", "Crystal Ice Shelf",
        ],
    }
    # Track used names to avoid duplicates
    used: set[str] = set()
    for s in sectors:
        if s.sector_id == colony_sector:
            s.name = colony_name
            continue
        pool = terrain_names.get(s.terrain.value, terrain_names["plains"])
        available_names = [n for n in pool if n not in used]
        if not available_names:
            available_names = pool  # fall back if pool exhausted
        name = random.choice(available_names)
        used.add(name)
        s.name = name


def _generate_sector_names_api(
    sectors: list[Sector],
    rows: int,
    cols: int,
    colony_sector: int,
    colony_name: str,
    api_key: str,
) -> None:
    """Generate evocative sector names via a single Haiku API call."""
    import anthropic
    from planetfall.api_tracker import tracked_api_call

    # Build sector descriptions for the prompt
    lines = []
    for s in sectors:
        if s.sector_id == colony_sector:
            continue
        r, c = divmod(s.sector_id, cols)
        features = []
        if s.has_investigation_site:
            features.append("investigation site")
        if s.has_ancient_sign:
            features.append("ancient alien sign")
        if s.has_ancient_site:
            features.append("ancient alien site")
        feat_str = f" [{', '.join(features)}]" if features else ""
        lines.append(f"{s.sector_id}: row {r} col {c}, {s.terrain.value}{feat_str}")

    prompt = (
        f"You are naming sectors on an alien planet map for a colony called '{colony_name}'. "
        f"The map is {rows}x{cols}. Each sector has terrain and possibly special features.\n\n"
        f"Generate a short, evocative sci-fi exploration name (2-3 words) for each sector. "
        f"Names should reflect the terrain type and any features. Nearby sectors can share "
        f"thematic elements. Ancient sites should sound mysterious. Investigation sites "
        f"should hint at something worth exploring.\n\n"
        f"Sectors:\n" + "\n".join(lines) + "\n\n"
        f"Reply with ONLY lines in format: ID: Name\n"
        f"No other text."
    )

    client = anthropic.Anthropic(api_key=api_key)
    message = tracked_api_call(
        client, caller="sector_names",
        model="claude-haiku-4-5-20251001",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

    # Parse response
    text = message.content[0].text
    name_map: dict[int, str] = {}
    for line in text.strip().split("\n"):
        line = line.strip()
        if ":" not in line:
            continue
        parts = line.split(":", 1)
        try:
            sid = int(parts[0].strip())
            name = parts[1].strip()
            if name:
                name_map[sid] = name
        except (ValueError, IndexError):
            continue

    # Apply names
    sectors[colony_sector].name = colony_name
    for s in sectors:
        if s.sector_id in name_map:
            s.name = name_map[s.sector_id]
        elif s.sector_id != colony_sector and not s.name:
            # Fallback for any missed sectors
            s.name = f"Sector {s.sector_id}"

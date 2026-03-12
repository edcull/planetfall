# Planetfall

AI-powered game master for **Five Parsecs from Home: Planetfall** — a solo tabletop sci-fi colony management wargame.

Planetfall automates the campaign turn sequence, rolls dice, tracks state, resolves combat, and narrates events with AI-generated prose that adapts to your crew's personalities and history.

## Features

- **18-step campaign turn loop** — recovery, scouting, colony events, missions, combat, research, building, and more
- **Zone-based combat system** — 3x3 grid battlefield with shooting, brawling, enemy AI, and 14 mission types
- **AI narrative agent** — Claude generates scene narration informed by character backgrounds, colony mood, and narrative memory
- **Character backgrounds** — auto-generated personality sketches from rolled traits (AI or template fallback)
- **D100/D6 random tables** — scout discoveries, colony events, enemy activity, injuries, advancement, character events
- **Persistent state** — JSON save files with per-turn snapshots
- **Rich CLI** — colony status, crew roster, campaign map, event logs
- **Human-in-the-loop** — player makes tactical decisions; the engine handles mechanics

## Architecture

```
planetfall/
├── main.py              # Entry point — new/continue campaign
├── config.py            # .env configuration loader
├── orchestrator.py      # Claude API orchestrator (18-step turn driver)
├── narrative.py         # AI narrative agent with compressed memory
├── cli/
│   ├── display.py       # Rich terminal output
│   └── prompts.py       # Interactive prompts (questionary)
├── engine/
│   ├── models.py        # Pydantic v2 game state models + weapon catalog
│   ├── dice.py          # Dice rolling, random tables, manual mode
│   ├── persistence.py   # Save/load JSON with snapshots
│   ├── campaign/
│   │   ├── setup.py     # Character creation, map gen, background gen
│   │   ├── buildings.py # Colony building definitions
│   │   └── research.py  # Tech tree definitions
│   ├── steps/           # 18 campaign turn step functions (step01–step18)
│   ├── tables/          # Encoded D100/D6 random tables
│   └── combat/          # Zone-based combat system
│       ├── battlefield.py  # 3x3 grid, figure placement
│       ├── session.py      # Combat round loop
│       ├── shooting.py     # Ranged attack resolution
│       ├── brawling.py     # Melee resolution
│       ├── enemy_ai.py     # Deterministic enemy behavior
│       ├── missions.py     # 14 mission type setups
│       ├── narrator.py     # Combat narrative descriptions
│       └── round.py        # Phase sequencing
├── rules/
│   ├── loader.py        # Rules text chunker (35 sections, on-demand)
│   └── sections/        # Chunked rules text files
└── tools/
    ├── definitions.py   # Claude tool_use schemas
    └── handlers.py      # Tool call dispatch
```

## Setup

**Requirements:** Python 3.13+

```bash
# Clone and create virtual environment
git clone <repo-url> && cd Planetfall
py -m venv venv
source venv/Scripts/activate  # Windows (Git Bash)
# source venv/bin/activate    # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Configure (optional — enables AI features)
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

## Configuration

Copy `.env.example` to `.env` and set your values:

```env
# Required for AI features (narrative backgrounds, AI orchestrator)
ANTHROPIC_API_KEY=sk-ant-api03-...

# Claude model for scene narration (default: claude-sonnet-4-20250514)
NARRATIVE_MODEL=claude-sonnet-4-20250514

# Claude model for character backgrounds (default: claude-haiku-4-5-20251001)
BACKGROUND_MODEL=claude-haiku-4-5-20251001

# Enable manual dice input (default: false)
MANUAL_DICE=false
```

Without an API key, the game runs fully offline using template-based narration and a local orchestrator.

## Usage

```bash
source venv/Scripts/activate
python -m planetfall.main
```

**New campaign:** name your colony, choose a colonization agenda, create your 8-person crew (default roster, custom classes, or import existing characters). Backgrounds are auto-generated from rolled traits.

**Continue campaign:** select a saved campaign and play through turns. Each turn follows the 18-step sequence with interactive prompts for player decisions.

## Running Tests

```bash
source venv/Scripts/activate
python -m pytest tests/ -v
```

## Project Status

| Phase | Status | Description |
|-------|--------|-------------|
| 1. Core Engine | Complete | Models, dice, persistence, tables |
| 2. Campaign Loop | Complete | 18 steps, rules loader, CLI, orchestrator |
| 3. Combat System | Complete | Zones, shooting, brawling, enemy AI, missions |
| 4. Narrative & AI | In Progress | Character backgrounds, narrative agent, AI orchestrator |

## Tech Stack

- **Python 3.13** with type hints
- **Pydantic v2** — game state models and validation
- **Anthropic SDK** — Claude API for narration and orchestration
- **Rich** — terminal UI (tables, panels, colored output)
- **Questionary** — interactive prompts and menus
- **python-dotenv** — environment configuration

## Game Reference

Based on *Five Parsecs from Home: Planetfall* by Ivan Sorensen (Modiphius Entertainment). Rules file chunked into 35 sections for on-demand loading by the AI orchestrator.

# Planetfall

AI-powered game master for **Five Parsecs from Home: Planetfall** — a solo tabletop sci-fi colony management wargame.

Planetfall automates the campaign turn sequence, rolls dice, tracks state, resolves combat, and narrates events with AI-generated prose that adapts to your crew's personalities and history.

## Features

- **18-step campaign turn loop** — recovery, scouting, colony events, missions, combat, research, building, and more
- **Zone-based combat system** — variable grid (6x6 small / 9x9 standard, 4" zones) with shooting, brawling, enemy AI, and 13 mission types
- **AI narrative agent** — Claude generates scene narration informed by character backgrounds, colony mood, and narrative memory
- **Character backgrounds** — auto-generated personality sketches from rolled traits (AI or template fallback)
- **D100/D6 random tables** — scout discoveries, colony events, enemy activity, injuries, advancement, character events
- **Persistent state** — JSON save files with per-turn snapshots and auto-updating markdown turn logs
- **Campaign log viewer** — browse turn-by-turn logs in-game with previous/next day navigation
- **Rich CLI** — colony status, crew roster, campaign map, research & buildings, event logs
- **Human-in-the-loop** — player makes tactical decisions; the engine handles mechanics
- **Save management** — undo/rollback, rename, copy, delete campaigns

## Architecture

```
planetfall/
├── main.py                # Entry point — new/continue campaign, log viewer
├── config.py              # .env configuration loader
├── orchestrator.py        # Claude API orchestrator (18-step turn driver)
├── orchestrator_steps.py  # Combat UI, deployment, research/building prompts
├── narrative.py           # AI narrative agent with compressed memory
├── api_tracker.py         # API call tracking/logging
├── cli/
│   ├── display.py         # Rich terminal output (colony, map, roster, combat)
│   └── prompts.py         # Interactive prompts (questionary)
├── engine/
│   ├── models.py          # Pydantic v2 game state models + weapon catalog
│   ├── dice.py            # Dice rolling, random tables, manual mode
│   ├── persistence.py     # Save/load JSON with snapshots
│   ├── campaign_log.py    # Markdown turn log export (auto-updated on save)
│   ├── rollback.py        # Game state rollback to previous turns
│   ├── campaign/          # Campaign subsystems
│   │   ├── setup.py       # Character creation, map gen, background gen
│   │   ├── buildings.py   # Colony building definitions
│   │   ├── research.py    # Tech tree (theories + applications)
│   │   ├── equipment.py   # Equipment and augmentation
│   │   ├── milestones.py  # Campaign milestone tracking
│   │   ├── calamities.py  # Colony calamity events
│   │   └── ...            # extraction, slyn, story_points, ancient_signs
│   ├── steps/             # 18 campaign turn step functions (step01–step18)
│   ├── tables/            # 18 encoded D100/D6 random tables
│   └── combat/            # Zone-based combat system
│       ├── battlefield.py    # Variable grid (6x6/9x9), figure placement, stacking
│       ├── session.py        # Combat state machine with reaction rolls
│       ├── round.py          # Phase sequencing (quick/enemy/slow)
│       ├── shooting.py       # Ranged attack resolution with weapon traits
│       ├── brawling.py       # Melee resolution
│       ├── enemy_ai.py       # Deterministic enemy AI with stacking awareness
│       ├── missions.py       # 13 mission type setups
│       ├── initial_missions.py # Tutorial missions (Beacons, Analysis, Perimeter)
│       └── narrator.py       # Combat narrative descriptions
├── rules/
│   ├── loader.py          # Rules text chunker (35 sections, on-demand)
│   └── sections/          # Chunked rules text files
└── tools/
    ├── definitions.py     # Claude tool_use schemas (campaign, combat, queries)
    └── handlers.py        # Tool call dispatch
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

**Continue campaign:** select a saved campaign, optionally review the colony log, and play through turns. Each turn follows the 18-step sequence with interactive prompts for player decisions.

**Between turns:** view colony logs, search rules, export campaign history, undo/rollback to previous turns, or manage saves.

## Running Tests

```bash
source venv/Scripts/activate
python -m pytest tests/ -v
```

## Project Status

463 tests across 28 test files.

| Phase | Status | Description |
|-------|--------|-------------|
| 1. Core Engine | Complete | Models, dice, persistence, tables |
| 2. Campaign Loop | Complete | 18 steps, rules loader, CLI, orchestrator |
| 3. Combat System | Complete | Zones, shooting, brawling, enemy AI, 13 missions |
| 4. Narrative & AI | Complete | Character backgrounds, narrative agent, campaign logs |
| 5. Polish & UI | In Progress | Log viewer, save management, investigation evacuation |

## Tech Stack

- **Python 3.13** with type hints
- **Pydantic v2** — game state models and validation
- **Anthropic SDK** — Claude API for narration and orchestration
- **Rich** — terminal UI (tables, panels, colored output)
- **Questionary** — interactive prompts and menus
- **python-dotenv** — environment configuration

## Game Reference

Based on *Five Parsecs from Home: Planetfall* by Ivan Sorensen (Modiphius Entertainment). Rules file chunked into 35 sections for on-demand loading by the AI orchestrator.

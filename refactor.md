# Planetfall Refactoring Plan

## Progress Summary

| Phase | Status | Details |
|-------|--------|---------|
| Phase 1: Quick Wins | DONE | Shared fixtures, lookup utils, enum display, augmentation dedup, JS profile card, modal factory |
| Phase 2: File Splits | DONE | orchestrator_steps/, missions/, initial_missions/, setup/, JS/CSS splits |
| Rulebook Compliance | DONE | 10 fixes, 4 verified correct, 3 accepted as-is (see review.md) |
| Phase 3: Type Safety | PARTIAL | CharacterProfile + schema_version done; untyped dicts + migrations remain |
| Phase 4: Architecture | NOT STARTED | UI redraw, figure labels, overlays, dead code, atomic persistence |
| Phase 5: Large File Breakdown | NEW | session.py, combat.py, orchestrator.py — identified post-Phase-2 |

**Test status**: 475 passing, 5 failing (enum reference, assertion strictness, path, session logic)
**Branch diff**: 80 files changed, 8,421 insertions, 16,389 deletions

---

## Completed Work

### Phase 1: Quick Wins (DONE)

- **1.1** `tests/conftest.py` — shared `game_state()` and `game_state_scientific()` fixtures
- **1.2** `GameState.find_character()`, `.get_available_characters()`, `.get_sector()` on models.py
- **1.3** `format_display()` in `engine/utils.py` — replaces 23+ `.replace('_',' ').title()` calls
- **1.4** Augmentation effect dedup in `augmentation.py`
- **1.5** `buildFigureProfileHtml()` extracted in `input.js`
- **1.6** `openModal()` factory in `components-modals.js`

### Phase 2: File Splits (DONE)

- **2.1** `orchestrator_steps.py` → `orchestrator_steps/` package (5 modules, 3K lines)
- **2.2** `missions.py` → `engine/combat/missions/` package (base.py + setup.py)
- **2.3** `initial_missions.py` → `engine/combat/initial_missions/` (beacons, analysis, perimeter)
- **2.4** `campaign/setup.py` → `engine/campaign/setup/` (characters, backgrounds, map_gen)
- **2.5** JS split: input → 4 files, components → 4 files; CSS split: style → 6 files

### Rulebook Compliance Audit (DONE)

Full details in `review.md`. Summary of changes:

**10 fixes implemented:**
- Hesitation check for enemies without visible opponents (`enemy_ai.py`)
- Brawl knockback with sprawling/pushback thresholds (`brawling.py`)
- Multiple opponents brawl bonus with per-phase tracking (`session.py`)
- Step 13 replacement roll table with 2D6 + class sub-roll (`step13_replacements.py`)
- Knockback weapon trait proper distance thresholds (`shooting.py`)
- Bot deployment restriction after same-turn repair (`models.py`, `step01/02/07`)
- Uncertain Terrain D100 table + end-of-round reveal mechanic (`battlefield_conditions.py`, `battlefield.py`, `session.py`, `missions/setup.py`)
- Shifting Terrain actual zone movement + stability check (`session.py`)
- Beacons storm movement corrected to 1-4=1zone, 5-6=2zones (`beacons.py`)
- Delve device labels fixed from "hazard" to "device" (`missions/setup.py`)

**Files grew from review fixes:**
| File | Before | After | Delta | Reason |
|------|--------|-------|-------|--------|
| `session.py` | 1,749 | 1,969 | +220 | Brawl bonus tracking, uncertain terrain reveal, shifting terrain |
| `missions/setup.py` | 1,195 | 1,257 | +62 | Uncertain terrain placement, device labels |
| `battlefield.py` | 1,156 | 1,164 | +8 | Uncertain zone field |
| `enemy_ai.py` | 673 | 687 | +14 | Hesitation check |
| `battlefield_conditions.py` | — | 553 | — | Uncertain Terrain D100 table |

---

## Remaining Work

### Phase 0: Fix Failing Tests (5 failures)

#### 0.1 Fix SectorStatus.INVESTIGATED references
- `test_step03_effects.py`: `test_explore_sets_status` and `test_revised_survey_unknown` use `SectorStatus.INVESTIGATED` which doesn't exist
- Fix: change to `SectorStatus.EXPLORED`

#### 0.2 Fix post_mission_finds assertion
- `test_new_systems.py`: `test_roll_post_mission_finds` expects exactly 1 event, gets 2 (ancient_signs event added)
- Fix: `assert len(events) >= 1`

#### 0.3 Fix combat session available_actions
- `test_combat_session.py`: `test_available_actions` — empty actions after `assign_reactions()`
- Investigate: figure queuing in `_prepare_next_activation()` when reactions assigned

#### 0.4 Fix rules file path
- `test_endgame_and_flags.py`: `test_search_rules` — FileNotFoundError for rules file
- Fix: update path in `rules/loader.py` or mock in test

---

### Phase 3: Type Safety (REMAINING ITEMS)

#### 3.1 Type untyped dicts in models.py
Replace remaining `dict` fields with Pydantic models:

```python
class EnemyProfile(BaseModel):
    strength: int = 0
    toughness: int = 0
    mobility: int = 0
    combat_skill: int = 0
    special_rules: list[str] = Field(default_factory=list)

class MissionResult(BaseModel):
    mission_type: str = ""
    victory: bool = False
    casualties: list[str] = Field(default_factory=list)
    rewards: dict[str, int] = Field(default_factory=dict)

class ExtractionState(BaseModel):
    resource_type: str
    yield_per_turn: int
    turns_active: int = 0
    depleted: bool = False

class CalamityState(BaseModel):
    turns_remaining: int
    effects: dict[str, int] = Field(default_factory=dict)
```

Update: `TacticalEnemy.profile: dict` → `EnemyProfile`, `MechanicalFlags.last_mission: dict` → `MissionResult`, etc.

#### 3.2 Schema versioning / migrations
- `schema_version` field exists but no migration system
- Create `planetfall/engine/migrations.py`:

```python
MIGRATIONS = {
    0: migrate_v0_to_v1,
}

def apply_migrations(data: dict) -> dict:
    version = data.get("schema_version", 0)
    while version < CURRENT_VERSION:
        data = MIGRATIONS[version](data)
        version += 1
    return data
```

- Wire into `persistence.py` load path

---

### Phase 4: Architecture Polish

#### 4.1 UI redraw helper
Repeated pattern (~10 places in orchestrator_steps):
```python
ui.clear()
ui.show_colony_status(state)
ui.show_map(state)
ui.show_events(events)
```

Add to UI adapter protocol:
```python
def redraw(self, state: GameState, events: list[TurnEvent] | None = None) -> None:
    self.clear()
    self.show_colony_status(state)
    self.show_map(state)
    if events:
        self.show_events(events)
```

Files: `ui/adapter.py`, `ui/cli_adapter.py`, `web/adapter.py`

#### 4.2 Centralize figure labeling
Duplicated between `cli/display.py` (`_fig_label()`, `_fig_label_parts()`) and `web/serializers.py` (lines 312-330).

Fix: move to `battlefield.py` as `Figure.display_label()` method, used by both CLI and web.

#### 4.3 Consolidate overlay builders
Three similar functions in `cli/display.py`: `_build_movement_map()`, `_build_shooting_map()`, `_build_vision_map()`.

Extract to generic:
```python
def _build_zone_overlay(bf, fig, criteria_fn) -> dict[tuple, str]:
```

#### 4.4 WebAdapter input method factory
8+ input methods in `web/adapter.py` follow identical `uuid → send → wait` pattern.

Extract to:
```python
def _request_input(self, input_type: str, **kwargs) -> Any:
```

#### 4.5 Centralize style constants
Color/style definitions scattered across `cli/display.py`. Extract to `planetfall/cli/styles.py`.

#### 4.6 Dead code removal
- `_prompt_subspecies()` in `web/server.py` — never called
- `reset_enemy_labels()` in `web/adapter.py` — never called
- Audit CSS for unused selectors

#### 4.7 Atomic persistence
```python
def save_state(state: GameState, campaign_name: str) -> None:
    tmp = state_path.with_suffix('.tmp')
    tmp.write_text(state.model_dump_json(indent=2))
    tmp.replace(state_path)  # atomic on most filesystems
```

#### 4.8 JS state management
Consolidate scattered global caching variables into `AppState` object.

#### 4.9 Standardize JS event handlers
Replace mixed `onclick=""` / `.onclick =` / `.addEventListener()` with consistent `.addEventListener()`.

---

### Phase 5: Large File Breakdown

Post-Phase-2 analysis plus rulebook compliance fixes have left these files oversized. The review fixes added ~300 lines to already-large files, making this phase more important.

**Current largest files (lines):**

| File | Lines | Problem |
|------|-------|---------|
| `engine/combat/session.py` | 1,969 | God class: 30+ methods, mixed responsibilities. Grew +220 from brawl bonus, uncertain terrain, shifting terrain |
| `orchestrator_steps/combat.py` | 1,501 | Two mega-functions (616 + 385 lines) |
| `orchestrator.py` | 1,393 | 1,044-line sequential function |
| `engine/combat/missions/setup.py` | 1,257 | Duplicated deployment patterns across 14 missions. Grew +62 from uncertain terrain placement |
| `cli/display.py` | 1,166 | 3 similar overlay builders, duplicated labels |
| `engine/combat/battlefield.py` | 1,164 | Mixed: grid + LoS + contacts + conditions + pathfinding |

#### 5.1 Deduplicate movement calculation (3 copies)
Movement zone calculation exists independently in:
1. `session.py:_get_actions_for()` — inline movement zone building (50+ lines)
2. `orchestrator_steps/combat.py:_get_move_zones()` — standalone function (40 lines)
3. `orchestrator_steps/combat.py:_get_dash_zones()` — standalone function (35 lines)

Fix: `Battlefield.move_destinations()` already exists — make it the single source of truth. Have both session.py and combat.py call it instead of computing independently.

#### 5.2 Split `run_campaign_turn_local()` (1,044 lines)
`orchestrator.py` contains a single function that sequentially executes all 18 campaign steps inline with UI logic mixed in.

Split into per-step-group functions:
```
run_campaign_turn_local()         # ~100 line dispatcher
├── _run_recovery_and_repairs()   # Steps 1-2
├── _run_pre_mission()            # Steps 3-5
├── _run_mission()                # Steps 6-8
├── _run_post_mission()           # Steps 9-13
└── _run_colony_management()      # Steps 14-18
```

The engine step functions already exist in `engine/steps/` — this is about structuring the orchestrator's call pattern.

#### 5.3 Split combat mega-functions
`orchestrator_steps/combat.py` has two oversized functions:

**`_run_interactive_combat()` (616 lines)** → split into:
- `_setup_combat_session()` — load/resume session (~50 lines)
- `_run_combat_loop()` — main phase loop (~350 lines)
- `_resolve_combat_end()` — end-of-battle resolution (~150 lines)

**`_handle_player_turn()` (385 lines)** → split into:
- `_handle_movement()` — movement/dash selection (~80 lines)
- `_handle_action_selection()` — action choice + targeting (~200 lines)
- `_handle_post_move()` — objective checks after move (~60 lines)

#### 5.4 Extract CombatSession sub-responsibilities
`CombatSession` (1,969 lines, 30+ methods) is a god class handling:
- Phase management (transitions, round tracking)
- Objective tracking and resolution
- Action generation for player figures
- Contact detection and reveals
- Brawl bonus tracking (new from review)
- Uncertain terrain reveal (new from review)
- Shifting terrain movement (new from review)

The review fixes added 3 more responsibilities, making extraction more urgent.

Extract to helper classes/modules:
- `_get_actions_for()` (200+ lines) → `combat/action_generator.py`
- Consolidate `_check_objective_sweep()` (110 lines) + `_auto_secure_remaining_objectives()` (70 lines) — duplicate objective logic
- Consolidate `_check_contacts()` + `_check_contacts_obscured()` — overlapping contact detection
- Extract `_reveal_uncertain_terrain()` + `_apply_condition_end_of_round()` → `combat/conditions.py`

#### 5.5 Extract mission setup helpers
`missions/setup.py` (1,257 lines) has duplicated patterns across 14 mission handlers:
- Sector terrain/hazard lookup from `state.turn_log` (appears in 6+ missions)
- Lifeform contact generation + enemy info building (4+ missions)
- Objective setup follows similar patterns across discovery/recon/science/patrol types
- Uncertain terrain placement (new from review)

Extract shared helpers:
```python
def _get_sector_context(state, mission_type) -> tuple[int, int]:  # resource_level, hazard_level
def _build_standard_objectives(mission_type, grid_size) -> list[Objective]:
def _place_uncertain_terrain(bf, rng) -> None:  # new from review
```

#### 5.6 Split Battlefield class (1,164 lines)
`Battlefield` has 30+ methods across 5 distinct responsibilities:
1. Zone grid management (+ uncertain zone field from review)
2. Figure tracking / queries
3. Line-of-sight calculation (80+ lines of dense logic)
4. Contact detection and reveals (100+ lines)
5. Condition effects (80+ lines)

Extract LoS and contact management to helper classes used by Battlefield:
```python
class LineOfSightCalculator:
    def check_los(self, bf, from_zone, to_zone) -> bool: ...
    def has_cover_los(self, bf, from_zone, to_zone) -> bool: ...

class ContactManager:
    def detect_contacts_auto(self, bf) -> list[Figure]: ...
    def reveal_contact(self, bf, contact) -> Figure: ...
```

---

## Execution Order

| # | Task | Risk | Key Files |
|---|------|------|-----------|
| 1 | Fix 5 failing tests (Phase 0) | Low | test files, loader.py, session.py |
| 2 | Deduplicate movement calc (5.1) | Medium | battlefield.py, session.py, combat.py |
| 3 | Type untyped dicts (3.1) | Medium | models.py + consumers |
| 4 | Schema migrations (3.2) | Low | new migrations.py, persistence.py |
| 5 | Split `run_campaign_turn_local()` (5.2) | Medium | orchestrator.py |
| 6 | Split combat mega-functions (5.3) | Medium | orchestrator_steps/combat.py |
| 7 | Extract CombatSession helpers (5.4) | High | session.py + new action_generator.py, conditions.py |
| 8 | Extract mission setup helpers (5.5) | Medium | missions/setup.py, missions/base.py |
| 9 | Figure labeling dedup (4.2) | Low | battlefield.py, display.py, serializers.py |
| 10 | Overlay builder consolidation (4.3) | Low | display.py |
| 11 | UI redraw helper (4.1) | Low | adapter.py, cli_adapter.py, web/adapter.py |
| 12 | WebAdapter factory (4.4) | Low | web/adapter.py |
| 13 | Style constants (4.5) | Low | display.py, new styles.py |
| 14 | Dead code + atomic persistence (4.6-4.7) | Low | Various |
| 15 | JS polish: AppState + addEventListener (4.8-4.9) | Low | JS files |
| 16 | Split Battlefield class (5.6) | High | battlefield.py + new files |

Run full test suite (`python -m pytest tests/ -v`) after each numbered item. Commit after each task.

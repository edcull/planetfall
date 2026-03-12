"""Save/load game state with per-turn snapshots."""

from __future__ import annotations

import json
import os
from pathlib import Path

from planetfall.engine.models import GameState

SAVES_DIR = Path("saves")


def _campaign_dir(campaign_name: str) -> Path:
    """Get the save directory for a campaign."""
    safe_name = "".join(
        c if c.isalnum() or c in ("-", "_") else "_"
        for c in campaign_name
    )
    return SAVES_DIR / safe_name


def save_state(state: GameState) -> Path:
    """Save current game state and create a turn snapshot."""
    campaign_dir = _campaign_dir(state.campaign_name)
    campaign_dir.mkdir(parents=True, exist_ok=True)

    # Save current state
    state_path = campaign_dir / "state.json"
    state_path.write_text(
        state.model_dump_json(indent=2), encoding="utf-8"
    )

    # Save turn snapshot
    snapshot_path = campaign_dir / f"turn_{state.current_turn:03d}.json"
    snapshot_path.write_text(
        state.model_dump_json(indent=2), encoding="utf-8"
    )

    return state_path


def load_state(campaign_name: str) -> GameState:
    """Load the current game state for a campaign."""
    campaign_dir = _campaign_dir(campaign_name)
    state_path = campaign_dir / "state.json"

    if not state_path.exists():
        raise FileNotFoundError(
            f"No save found for campaign '{campaign_name}' "
            f"at {state_path}"
        )

    data = json.loads(state_path.read_text(encoding="utf-8"))
    return GameState.model_validate(data)


def load_snapshot(campaign_name: str, turn: int) -> GameState:
    """Load a specific turn snapshot."""
    campaign_dir = _campaign_dir(campaign_name)
    snapshot_path = campaign_dir / f"turn_{turn:03d}.json"

    if not snapshot_path.exists():
        raise FileNotFoundError(
            f"No snapshot found for turn {turn} of campaign '{campaign_name}'"
        )

    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    return GameState.model_validate(data)


def list_campaigns() -> list[str]:
    """List all saved campaign names."""
    if not SAVES_DIR.exists():
        return []
    return [
        d.name for d in SAVES_DIR.iterdir()
        if d.is_dir() and (d / "state.json").exists()
    ]


def list_snapshots(campaign_name: str) -> list[int]:
    """List available turn snapshots for a campaign."""
    campaign_dir = _campaign_dir(campaign_name)
    if not campaign_dir.exists():
        return []
    turns = []
    for f in campaign_dir.iterdir():
        if f.name.startswith("turn_") and f.name.endswith(".json"):
            try:
                turn_num = int(f.stem.split("_")[1])
                turns.append(turn_num)
            except (ValueError, IndexError):
                continue
    return sorted(turns)


def delete_campaign(campaign_name: str) -> bool:
    """Delete a saved campaign and all its snapshots."""
    campaign_dir = _campaign_dir(campaign_name)
    if not campaign_dir.exists():
        return False
    import shutil
    shutil.rmtree(campaign_dir)
    return True


def copy_campaign(source_name: str, dest_name: str) -> Path:
    """Copy a campaign save to a new slot name."""
    source_dir = _campaign_dir(source_name)
    dest_dir = _campaign_dir(dest_name)
    if not source_dir.exists():
        raise FileNotFoundError(f"Source campaign '{source_name}' not found")
    if dest_dir.exists():
        raise FileExistsError(f"Campaign '{dest_name}' already exists")
    import shutil
    shutil.copytree(source_dir, dest_dir)
    # Update campaign name in the copied state
    state_path = dest_dir / "state.json"
    if state_path.exists():
        data = json.loads(state_path.read_text(encoding="utf-8"))
        data["campaign_name"] = dest_name
        state_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return dest_dir


def rename_campaign(old_name: str, new_name: str) -> Path:
    """Rename a campaign save."""
    old_dir = _campaign_dir(old_name)
    new_dir = _campaign_dir(new_name)
    if not old_dir.exists():
        raise FileNotFoundError(f"Campaign '{old_name}' not found")
    if new_dir.exists():
        raise FileExistsError(f"Campaign '{new_name}' already exists")
    old_dir.rename(new_dir)
    state_path = new_dir / "state.json"
    if state_path.exists():
        data = json.loads(state_path.read_text(encoding="utf-8"))
        data["campaign_name"] = new_name
        state_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return new_dir


def get_campaign_info(campaign_name: str) -> dict:
    """Get summary info about a saved campaign."""
    campaign_dir = _campaign_dir(campaign_name)
    state_path = campaign_dir / "state.json"
    if not state_path.exists():
        return {"name": campaign_name, "exists": False}
    data = json.loads(state_path.read_text(encoding="utf-8"))
    snapshots = list_snapshots(campaign_name)
    total_size = sum(f.stat().st_size for f in campaign_dir.iterdir() if f.is_file())
    return {
        "name": campaign_name,
        "exists": True,
        "turn": data.get("current_turn", 0),
        "colony_name": data.get("colony", {}).get("name", "Unknown"),
        "characters": len(data.get("characters", [])),
        "snapshots": len(snapshots),
        "snapshot_turns": snapshots,
        "total_size_kb": round(total_size / 1024, 1),
    }


def append_narrative(campaign_name: str, text: str) -> None:
    """Append narrative text to the campaign's narrative log."""
    campaign_dir = _campaign_dir(campaign_name)
    campaign_dir.mkdir(parents=True, exist_ok=True)
    narrative_path = campaign_dir / "narrative.md"

    with open(narrative_path, "a", encoding="utf-8") as f:
        f.write(text + "\n\n")

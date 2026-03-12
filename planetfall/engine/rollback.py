"""Undo/rollback system — revert to previous turn snapshots.

Supports rolling back to any previously saved turn snapshot.
The current state is backed up before rollback so it can be recovered.
"""

from __future__ import annotations

from pathlib import Path

from planetfall.engine.models import GameState
from planetfall.engine.persistence import (
    _campaign_dir, list_snapshots, load_snapshot, save_state,
)


def get_rollback_options(campaign_name: str) -> list[dict]:
    """Get available turn snapshots for rollback.

    Returns list of dicts with turn number and file info.
    """
    turns = list_snapshots(campaign_name)
    campaign_dir = _campaign_dir(campaign_name)
    options = []
    for t in turns:
        path = campaign_dir / f"turn_{t:03d}.json"
        size_kb = path.stat().st_size / 1024 if path.exists() else 0
        options.append({
            "turn": t,
            "file": str(path),
            "size_kb": round(size_kb, 1),
        })
    return options


def rollback_to_turn(
    campaign_name: str,
    target_turn: int,
    backup_current: bool = True,
) -> GameState:
    """Roll back to a specific turn snapshot.

    Args:
        campaign_name: Campaign to roll back.
        target_turn: Turn number to restore.
        backup_current: If True, save current state as a backup before rolling back.

    Returns:
        The restored GameState.

    Raises:
        FileNotFoundError: If the target snapshot doesn't exist.
    """
    campaign_dir = _campaign_dir(campaign_name)

    # Backup current state before rollback
    if backup_current:
        current_state_path = campaign_dir / "state.json"
        if current_state_path.exists():
            backup_path = campaign_dir / "state_pre_rollback.json"
            backup_path.write_text(
                current_state_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )

    # Load the target snapshot
    restored = load_snapshot(campaign_name, target_turn)

    # Clear any turn log from the snapshot (it's historical)
    restored.turn_log = []

    # Save as current state
    save_state(restored)

    # Remove snapshots after the target turn
    for path in campaign_dir.iterdir():
        if path.name.startswith("turn_") and path.name.endswith(".json"):
            try:
                turn_num = int(path.stem.split("_")[1])
                if turn_num > target_turn:
                    # Also remove corresponding log files
                    log_path = campaign_dir / f"turn_{turn_num:03d}_log.md"
                    if log_path.exists():
                        log_path.unlink()
                    path.unlink()
            except (ValueError, IndexError):
                continue

    return restored


def recover_pre_rollback(campaign_name: str) -> GameState | None:
    """Recover the state that existed before the last rollback.

    Returns None if no pre-rollback backup exists.
    """
    campaign_dir = _campaign_dir(campaign_name)
    backup_path = campaign_dir / "state_pre_rollback.json"

    if not backup_path.exists():
        return None

    import json
    data = json.loads(backup_path.read_text(encoding="utf-8"))
    return GameState.model_validate(data)


def undo_last_turn(state: GameState) -> GameState | None:
    """Undo the last completed turn by rolling back one turn.

    Returns the restored state, or None if no previous snapshot exists.
    """
    turns = list_snapshots(state.campaign_name)
    if len(turns) < 2:
        return None

    # Find the turn before the current one
    current = state.current_turn
    previous_turns = [t for t in turns if t < current]
    if not previous_turns:
        return None

    target = max(previous_turns)
    return rollback_to_turn(state.campaign_name, target)

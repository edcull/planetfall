"""Tests for campaign log export, undo/rollback, and save slot management."""

import pytest
import shutil
from pathlib import Path
from planetfall.engine.campaign.setup import create_new_campaign
from planetfall.engine.models import (
    ColonizationAgenda, GameState, TurnEvent, TurnEventType,
)
from planetfall.engine.persistence import (
    save_state, load_state, list_campaigns, list_snapshots,
    delete_campaign, copy_campaign, rename_campaign, get_campaign_info,
    SAVES_DIR, _campaign_dir,
)


def _make_state(name: str = "TestCampaign") -> GameState:
    state = create_new_campaign(name, "Colony", agenda=ColonizationAgenda.SCIENTIFIC)
    state.campaign_name = name
    return state


def _cleanup(name: str):
    d = _campaign_dir(name)
    if d.exists():
        shutil.rmtree(d)


# --- Campaign Log Export ---

class TestCampaignLogExport:
    def test_export_turn_log_markdown(self):
        from planetfall.engine.campaign_log import export_turn_log
        state = _make_state()
        state.turn_log = [
            TurnEvent(step=1, event_type=TurnEventType.RECOVERY,
                      description="Character recovered from sick bay."),
            TurnEvent(step=8, event_type=TurnEventType.COMBAT,
                      description="Mission: Patrol — VICTORY in 3 rounds."),
        ]
        md = export_turn_log(state)
        assert "# Turn" in md
        assert "Colony Status" in md
        assert "recovered from sick bay" in md
        assert "VICTORY" in md
        assert "Roster" in md

    def test_export_turn_log_empty_events(self):
        from planetfall.engine.campaign_log import export_turn_log
        state = _make_state()
        state.turn_log = []
        md = export_turn_log(state)
        assert "# Turn" in md
        assert "Colony Status" in md

    def test_save_turn_log_creates_file(self):
        from planetfall.engine.campaign_log import save_turn_log
        name = "TestLogSave"
        try:
            state = _make_state(name)
            save_state(state)
            path = save_turn_log(state)
            assert path.exists()
            content = path.read_text(encoding="utf-8")
            assert "# Turn" in content
        finally:
            _cleanup(name)

    def test_export_campaign_log(self):
        from planetfall.engine.campaign_log import export_campaign_log
        name = "TestFullLog"
        try:
            state = _make_state(name)
            save_state(state)
            md = export_campaign_log(state)
            assert "Campaign Log" in md
        finally:
            _cleanup(name)


# --- Undo/Rollback ---

class TestRollback:
    def test_undo_last_turn(self):
        from planetfall.engine.rollback import undo_last_turn
        name = "TestUndo"
        try:
            state = _make_state(name)
            state.current_turn = 1
            save_state(state)

            state.current_turn = 2
            state.colony.morale = 15
            save_state(state)

            restored = undo_last_turn(state)
            assert restored is not None
            assert restored.current_turn == 1
        finally:
            _cleanup(name)

    def test_undo_no_previous(self):
        from planetfall.engine.rollback import undo_last_turn
        name = "TestUndoNoPrev"
        try:
            state = _make_state(name)
            state.current_turn = 1
            save_state(state)
            result = undo_last_turn(state)
            assert result is None
        finally:
            _cleanup(name)

    def test_rollback_to_specific_turn(self):
        from planetfall.engine.rollback import rollback_to_turn
        name = "TestRollbackSpecific"
        try:
            state = _make_state(name)
            state.current_turn = 1
            save_state(state)

            state.current_turn = 2
            save_state(state)

            state.current_turn = 3
            save_state(state)

            restored = rollback_to_turn(name, 1)
            assert restored.current_turn == 1

            # Snapshots after turn 1 should be deleted
            snaps = list_snapshots(name)
            assert 2 not in snaps
            assert 3 not in snaps
        finally:
            _cleanup(name)

    def test_rollback_creates_backup(self):
        from planetfall.engine.rollback import rollback_to_turn, recover_pre_rollback
        name = "TestRollbackBackup"
        try:
            state = _make_state(name)
            state.current_turn = 1
            save_state(state)

            state.current_turn = 2
            state.colony.morale = 99
            save_state(state)

            rollback_to_turn(name, 1)

            recovered = recover_pre_rollback(name)
            assert recovered is not None
            assert recovered.current_turn == 2
        finally:
            _cleanup(name)

    def test_rollback_missing_snapshot(self):
        from planetfall.engine.rollback import rollback_to_turn
        name = "TestRollbackMissing"
        try:
            state = _make_state(name)
            save_state(state)
            with pytest.raises(FileNotFoundError):
                rollback_to_turn(name, 99)
        finally:
            _cleanup(name)


# --- Save Slot Management ---

class TestSaveManagement:
    def test_get_campaign_info(self):
        name = "TestInfo"
        try:
            state = _make_state(name)
            save_state(state)
            info = get_campaign_info(name)
            assert info["exists"] is True
            assert info["turn"] == state.current_turn
            assert info["characters"] == len(state.characters)
        finally:
            _cleanup(name)

    def test_get_campaign_info_nonexistent(self):
        info = get_campaign_info("NonExistentCampaign12345")
        assert info["exists"] is False

    def test_copy_campaign(self):
        src = "TestCopySrc"
        dst = "TestCopyDst"
        try:
            state = _make_state(src)
            save_state(state)
            copy_campaign(src, dst)
            loaded = load_state(dst)
            assert loaded.campaign_name == dst
            assert len(loaded.characters) == len(state.characters)
        finally:
            _cleanup(src)
            _cleanup(dst)

    def test_copy_campaign_exists(self):
        src = "TestCopyExists1"
        dst = "TestCopyExists2"
        try:
            state1 = _make_state(src)
            save_state(state1)
            state2 = _make_state(dst)
            save_state(state2)
            with pytest.raises(FileExistsError):
                copy_campaign(src, dst)
        finally:
            _cleanup(src)
            _cleanup(dst)

    def test_rename_campaign(self):
        old = "TestRenameOld"
        new = "TestRenameNew"
        try:
            state = _make_state(old)
            save_state(state)
            rename_campaign(old, new)
            assert not _campaign_dir(old).exists()
            loaded = load_state(new)
            assert loaded.campaign_name == new
        finally:
            _cleanup(old)
            _cleanup(new)

    def test_delete_campaign(self):
        name = "TestDelete"
        state = _make_state(name)
        save_state(state)
        assert delete_campaign(name) is True
        assert not _campaign_dir(name).exists()

    def test_delete_nonexistent(self):
        assert delete_campaign("NonExistent12345") is False


# --- Tool Handlers for new features ---

class TestNewToolHandlers:
    def test_export_turn_log_handler(self):
        from planetfall.tools.handlers import handle_tool_call
        import json
        name = "TestToolExport"
        try:
            state = _make_state(name)
            save_state(state)
            result = json.loads(handle_tool_call(state, "export_turn_log", {}))
            assert result["exported"] is True
        finally:
            _cleanup(name)

    def test_list_snapshots_handler(self):
        from planetfall.tools.handlers import handle_tool_call
        import json
        name = "TestToolSnaps"
        try:
            state = _make_state(name)
            save_state(state)
            result = json.loads(handle_tool_call(state, "list_snapshots", {}))
            assert "snapshots" in result
            assert isinstance(result["snapshots"], list)
        finally:
            _cleanup(name)

    def test_undo_handler_no_previous(self):
        from planetfall.tools.handlers import handle_tool_call
        import json
        name = "TestToolUndo"
        try:
            state = _make_state(name)
            state.current_turn = 1
            save_state(state)
            result = json.loads(handle_tool_call(state, "undo_last_turn", {}))
            assert result["success"] is False
        finally:
            _cleanup(name)

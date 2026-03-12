"""Tests for Step 10: Experience Progression."""

from unittest.mock import patch

from planetfall.engine.campaign.setup import create_new_campaign
from planetfall.engine.dice import RollResult, TableEntry
from planetfall.engine.models import (
    CharacterClass, ColonizationAgenda, Loyalty,
)
from planetfall.engine.steps.step10_experience import (
    award_mission_xp, roll_advancement, buy_advancement,
    alternate_advancement, XP_PER_ADVANCEMENT,
)


def _make_state():
    return create_new_campaign("T", "C", agenda=ColonizationAgenda.UNITY)


class TestAwardMissionXP:
    def test_participation_xp(self):
        state = _make_state()
        name = state.characters[0].name
        old_xp = state.characters[0].xp
        events = award_mission_xp(state, [name], [])
        assert state.characters[0].xp == old_xp + 2  # +1 participation, +1 survived

    def test_casualty_loses_survival_xp(self):
        state = _make_state()
        name = state.characters[0].name
        old_xp = state.characters[0].xp
        events = award_mission_xp(state, [name], [name])
        assert state.characters[0].xp == old_xp + 1  # +1 participation only

    def test_leader_kill_bonus(self):
        state = _make_state()
        name = state.characters[0].name
        old_xp = state.characters[0].xp
        events = award_mission_xp(state, [name], [], killed_leader=[name])
        assert state.characters[0].xp == old_xp + 3  # +1 participation, +1 survived, +1 kill

    def test_not_deployed_gets_nothing(self):
        state = _make_state()
        old_xp = state.characters[0].xp
        events = award_mission_xp(state, [], [])
        assert state.characters[0].xp == old_xp

    def test_double_xp_note(self):
        state = _make_state()
        name = state.characters[0].name
        state.characters[0].notes = "[DOUBLE_XP: next mission]"
        old_xp = state.characters[0].xp
        events = award_mission_xp(state, [name], [])
        assert state.characters[0].xp == old_xp + 4  # (1+1) * 2
        assert "[DOUBLE_XP: next mission]" not in (state.characters[0].notes or "")

    def test_forfeit_xp_note(self):
        state = _make_state()
        name = state.characters[0].name
        state.characters[0].notes = "[FORFEIT_XP: next turn]"
        old_xp = state.characters[0].xp
        events = award_mission_xp(state, [name], [])
        assert state.characters[0].xp == old_xp  # forfeited
        assert "[FORFEIT_XP: next turn]" not in (state.characters[0].notes or "")


class TestRollAdvancement:
    @patch("planetfall.engine.steps.step10_experience.ADVANCEMENT_TABLE")
    def test_basic_advancement(self, mock_table):
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[50], total=50, label=""),
            TableEntry(low=41, high=60, result_id="combat_skill",
                      description="CS up", effects={"stat": "combat_skill", "max": 5, "bonus": 1}),
        )
        state = _make_state()
        char = state.characters[0]
        char.xp = 10
        old_cs = char.combat_skill
        events = roll_advancement(state, char.name)
        assert char.xp == 5
        assert char.combat_skill == old_cs + 1
        assert len(events) == 1

    @patch("planetfall.engine.steps.step10_experience.ADVANCEMENT_TABLE")
    def test_maxed_stat(self, mock_table):
        mock_table.roll_on_table.return_value = (
            RollResult(dice_type="d100", values=[50], total=50, label=""),
            TableEntry(low=41, high=60, result_id="combat_skill",
                      description="CS up", effects={"stat": "combat_skill", "max": 5, "bonus": 1}),
        )
        state = _make_state()
        char = state.characters[0]
        char.xp = 10
        char.combat_skill = 5
        events = roll_advancement(state, char.name)
        assert char.combat_skill == 5  # still maxed
        assert "already at max" in events[0].description

    def test_insufficient_xp(self):
        state = _make_state()
        char = state.characters[0]
        char.xp = 2
        events = roll_advancement(state, char.name)
        assert len(events) == 0


class TestBuyAdvancement:
    def test_buy_stat(self):
        state = _make_state()
        char = state.characters[0]
        char.xp = 10
        old_savvy = char.savvy
        events = buy_advancement(state, char.name, "savvy")
        assert char.savvy == old_savvy + 1
        assert char.xp == 10 - 5  # savvy costs 5

    def test_insufficient_xp(self):
        state = _make_state()
        char = state.characters[0]
        char.xp = 2
        events = buy_advancement(state, char.name, "savvy")
        assert "Cannot buy" in events[0].description

    def test_maxed_stat(self):
        state = _make_state()
        char = state.characters[0]
        char.xp = 10
        char.savvy = 5
        events = buy_advancement(state, char.name, "savvy")
        assert "already at max" in events[0].description

    def test_invalid_stat(self):
        state = _make_state()
        char = state.characters[0]
        char.xp = 10
        events = buy_advancement(state, char.name, "nonexistent")
        assert len(events) == 0

    def test_speed_first_bonus_is_2(self):
        state = _make_state()
        char = state.characters[0]
        char.xp = 10
        old_speed = char.speed
        events = buy_advancement(state, char.name, "speed")
        assert char.speed == old_speed + 2  # first speed buy = +2


class TestAlternateAdvancement:
    def test_loyalty_increase(self):
        state = _make_state()
        char = state.characters[0]
        char.xp = 10
        char.loyalty = Loyalty.COMMITTED
        events = alternate_advancement(state, char.name, "loyalty")
        assert char.loyalty == Loyalty.LOYAL
        assert char.xp == 10 - XP_PER_ADVANCEMENT

    def test_loyalty_already_max(self):
        state = _make_state()
        char = state.characters[0]
        char.xp = 10
        char.loyalty = Loyalty.LOYAL
        events = alternate_advancement(state, char.name, "loyalty")
        assert "Already Loyal" in events[0].description

    def test_scientist_research_points(self):
        state = _make_state()
        scientist = None
        for c in state.characters:
            if c.char_class == CharacterClass.SCIENTIST:
                scientist = c
                break
        if not scientist:
            return  # skip if no scientist
        scientist.xp = 10
        old_rp = state.colony.resources.research_points
        events = alternate_advancement(state, scientist.name, "research_points")
        assert state.colony.resources.research_points == old_rp + 3

    def test_non_scientist_cannot_get_rp(self):
        state = _make_state()
        # Find a non-scientist
        char = None
        for c in state.characters:
            if c.char_class != CharacterClass.SCIENTIST:
                char = c
                break
        if not char:
            return
        char.xp = 10
        events = alternate_advancement(state, char.name, "research_points")
        assert "Only scientists" in events[0].description

    def test_scout_raw_materials(self):
        state = _make_state()
        scout = None
        for c in state.characters:
            if c.char_class == CharacterClass.SCOUT:
                scout = c
                break
        if not scout:
            return
        scout.xp = 10
        old_rm = state.colony.resources.raw_materials
        events = alternate_advancement(state, scout.name, "raw_materials")
        assert state.colony.resources.raw_materials == old_rm + 3

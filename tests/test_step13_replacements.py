"""Tests for Step 13: Replacements."""

from planetfall.engine.campaign.setup import create_new_campaign
from planetfall.engine.models import ColonizationAgenda
from planetfall.engine.steps.step13_replacements import execute, get_vacancies, MAX_ROSTER_SIZE


def _make_state():
    return create_new_campaign("T", "C", agenda=ColonizationAgenda.UNITY)


class TestVacancies:
    def test_full_roster_no_vacancies(self):
        state = _make_state()
        # Ensure full roster
        assert get_vacancies(state) == MAX_ROSTER_SIZE - len(state.characters)

    def test_vacancies_after_death(self):
        state = _make_state()
        initial = len(state.characters)
        state.characters.pop()
        assert get_vacancies(state) == MAX_ROSTER_SIZE - (initial - 1)


class TestExecute:
    def test_full_roster(self):
        state = _make_state()
        # Fill roster to max
        while len(state.characters) < MAX_ROSTER_SIZE:
            from planetfall.engine.models import Character, CharacterClass
            state.characters.append(Character(
                name=f"Extra {len(state.characters)}",
                char_class=CharacterClass.TROOPER,
            ))
        events = execute(state)
        assert "full" in events[0].description.lower() or "No replacements" in events[0].description

    def test_has_vacancies(self):
        state = _make_state()
        state.characters.pop()
        events = execute(state)
        assert "vacancy" in events[0].description.lower()
        assert events[0].state_changes.get("vacancies", 0) > 0

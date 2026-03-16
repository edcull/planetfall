"""Shared test fixtures for Planetfall tests."""

import pytest

from planetfall.engine.campaign.setup import create_new_campaign
from planetfall.engine.models import ColonizationAgenda, GameState


@pytest.fixture
def game_state() -> GameState:
    """Standard game state with UNITY agenda for most tests."""
    return create_new_campaign("T", "C", agenda=ColonizationAgenda.UNITY)


@pytest.fixture
def game_state_scientific() -> GameState:
    """Game state with SCIENTIFIC agenda for research/phase4 tests."""
    return create_new_campaign("Test", "Colony", agenda=ColonizationAgenda.SCIENTIFIC)

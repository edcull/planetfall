"""UI abstraction layer for Planetfall.

Provides a UIAdapter protocol and concrete implementations
for CLI (Rich/Questionary) and future web (FastAPI) backends.
"""

from planetfall.ui.adapter import UIAdapter
from planetfall.ui.cli_adapter import CLIAdapter

__all__ = ["UIAdapter", "CLIAdapter"]

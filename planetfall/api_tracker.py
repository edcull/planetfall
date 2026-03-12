"""API call tracking — logs all Claude API calls with token usage and estimated cost.

Provides a wrapper around anthropic client calls that automatically tracks
usage and a session-level summary.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


# Pricing per million tokens (as of 2025)
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # (input_cost_per_M, output_cost_per_M)
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-haiku-4-5-20251001": (0.80, 4.00),
    "claude-opus-4-20250514": (15.00, 75.00),
}

# Fallback for unknown models
_DEFAULT_PRICING = (3.00, 15.00)


@dataclass
class APICallRecord:
    """A single API call record."""
    timestamp: float
    caller: str  # e.g. "narrative", "combat_narrator", "background_gen"
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    estimated_cost_usd: float = 0.0
    duration_ms: float = 0.0


@dataclass
class APITracker:
    """Session-level API usage tracker."""
    calls: list[APICallRecord] = field(default_factory=list)

    @property
    def total_input_tokens(self) -> int:
        return sum(c.input_tokens for c in self.calls)

    @property
    def total_output_tokens(self) -> int:
        return sum(c.output_tokens for c in self.calls)

    @property
    def total_cost_usd(self) -> float:
        return sum(c.estimated_cost_usd for c in self.calls)

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def record(
        self,
        caller: str,
        model: str,
        usage: Any,
        duration_ms: float = 0.0,
    ) -> APICallRecord:
        """Record an API call from a message response's usage object."""
        input_tokens = getattr(usage, "input_tokens", 0)
        output_tokens = getattr(usage, "output_tokens", 0)
        cache_read = getattr(usage, "cache_read_input_tokens", 0)
        cache_creation = getattr(usage, "cache_creation_input_tokens", 0)

        # Calculate cost
        pricing = MODEL_PRICING.get(model, _DEFAULT_PRICING)
        input_cost = (input_tokens / 1_000_000) * pricing[0]
        output_cost = (output_tokens / 1_000_000) * pricing[1]
        total_cost = input_cost + output_cost

        record = APICallRecord(
            timestamp=time.time(),
            caller=caller,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read,
            cache_creation_tokens=cache_creation,
            estimated_cost_usd=total_cost,
            duration_ms=duration_ms,
        )
        self.calls.append(record)
        return record

    def summary(self) -> str:
        """Return a formatted usage summary."""
        if not self.calls:
            return "No API calls made this session."
        lines = [
            f"API Usage: {self.call_count} calls",
            f"  Input:  {self.total_input_tokens:,} tokens",
            f"  Output: {self.total_output_tokens:,} tokens",
            f"  Cost:   ${self.total_cost_usd:.4f}",
        ]
        # Breakdown by caller
        callers: dict[str, list[APICallRecord]] = {}
        for c in self.calls:
            callers.setdefault(c.caller, []).append(c)
        if len(callers) > 1:
            lines.append("  Breakdown:")
            for caller, records in sorted(callers.items()):
                cost = sum(r.estimated_cost_usd for r in records)
                tokens = sum(r.input_tokens + r.output_tokens for r in records)
                lines.append(f"    {caller}: {len(records)} calls, {tokens:,} tokens, ${cost:.4f}")
        return "\n".join(lines)

    def last_call_summary(self) -> str:
        """Return a one-line summary of the most recent call."""
        if not self.calls:
            return ""
        c = self.calls[-1]
        return (
            f"[dim]API: {c.caller} | {c.model} | "
            f"in:{c.input_tokens} out:{c.output_tokens} | "
            f"${c.estimated_cost_usd:.4f}"
            f"{f' | {c.duration_ms:.0f}ms' if c.duration_ms else ''}[/dim]"
        )


# Global session tracker
_tracker = APITracker()


def get_tracker() -> APITracker:
    """Get the global API tracker instance."""
    return _tracker


def reset_tracker() -> None:
    """Reset the global tracker (e.g. at session start)."""
    global _tracker
    _tracker = APITracker()


def tracked_api_call(
    client,
    caller: str,
    **kwargs,
):
    """Make an API call via client.messages.create and track usage.

    Args:
        client: anthropic.Anthropic client instance.
        caller: Label for this call (e.g. "narrative", "combat_narrator").
        **kwargs: All arguments passed to client.messages.create().

    Returns:
        The API message response.
    """
    start = time.time()
    message = client.messages.create(**kwargs)
    duration_ms = (time.time() - start) * 1000

    model = kwargs.get("model", "unknown")
    _tracker.record(
        caller=caller,
        model=model,
        usage=message.usage,
        duration_ms=duration_ms,
    )

    # Log to console
    from planetfall.cli.display import console
    console.print(_tracker.last_call_summary())

    return message

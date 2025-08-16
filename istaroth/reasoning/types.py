"""Type definitions for reasoning module."""

from typing import Any, Literal

import attrs


@attrs.define
class ReasoningStep:
    """Single reasoning step."""

    step_type: Literal["tool_call", "tool_result", "conclusion"]
    content: str
    timestamp: float = attrs.field(factory=lambda: 0.0)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "step_type": self.step_type,
            "content": self.content,
            "timestamp": self.timestamp,
        }


@attrs.define
class ReasoningRequest:
    """Reasoning request parameters."""

    question: str
    max_steps: int
    k: int  # Documents to retrieve
    model: str


@attrs.define
class ReasoningResponse:
    """Reasoning pipeline response."""

    question: str
    answer: str
    reasoning_steps: list[ReasoningStep]
    model: str = ""
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "question": self.question,
            "answer": self.answer,
            "reasoning_steps": [step.to_dict() for step in self.reasoning_steps],
            "model": self.model,
            "error": self.error,
        }

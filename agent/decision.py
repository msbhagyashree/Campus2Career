"""REUSABLE DECISION PATTERN: tool selection for an AI study tutor  (#tool-selection)

What it does
    Before the StudyPilot Strands Agent runs, Strands Decider 2B reads the student's
    request (and any uploaded screenshot) and selects the most suitable of six study tools:
    concept_explainer, exam_planner, practice_generator, code_debugger,
    resource_recommender, or aptitude_coach. When no tool is needed the decider returns
    "none" and the agent answers directly. The decider's confident choice is used to
    narrow the Agent's tool set to a single tool (fewer tools in context = fewer wrong calls,
    fewer tokens, faster turns). Low-confidence selections ask the student to clarify.

Typed questions and options
    QUESTIONS contains one question:
      "tool" (choice): one option per tool (described by that tool's one-line docstring) plus
      "none" ("no tool is needed; the assistant can answer directly"). Options are built
      from the TOOLS list at import time, so adding a tool with a docstring automatically
      adds its option without any retraining.

Wiring (where it sits in the agent's path)
    Tool_Selector runs BEFORE the Strands Agent is built each turn:

        from agent.decision import Tool_Selector, QUESTIONS
        from agent.tools import TOOLS
        from decider_kit import Decider

        selector = Tool_Selector(Decider(), TOOLS, threshold=0.65)
        # in chat():
        selection = selector.select(message, history, images, session_id)
        agent = Agent(model=..., tools=selection.tools)
        agent(message)

How to reuse it
    Copy this file, replace TOOLS with your own @tool functions, and re-word the questions
    if needed. Each tool must have a one-line docstring; Tool_Selector uses it as the option
    description. The threshold (default 0.65) controls the confidence level below which the
    agent falls back to asking the user to clarify.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from decider_kit import Decider
from decider_kit.client import Decision, DeciderError

from .tools import TOOLS

# ---------------------------------------------------------------------------
# Module-level constants required by the kit contract
# ---------------------------------------------------------------------------

PATTERN_TAG = "#tool-selection"
# No IS_KIT_EXAMPLE flag (this is the participant's own agent)


# ---------------------------------------------------------------------------
# Helpers: read one-line docstrings from Strands @tool functions
# ---------------------------------------------------------------------------

def _tool_name(tool: Any) -> str:
    """Return the tool's registered name (from tool_spec or __name__)."""
    spec = getattr(tool, "tool_spec", None)
    if spec:
        return spec["name"]
    return getattr(tool, "__name__", str(tool))


def _tool_description(tool: Any) -> str:
    """Return the tool's one-line docstring description (first line of the docstring)."""
    spec = getattr(tool, "tool_spec", None)
    if spec:
        raw = (spec.get("description") or spec["name"]).strip()
    else:
        raw = (tool.__doc__ or _tool_name(tool)).strip()
    return raw.split("\n")[0][:200]


def _validate_tools(tools: list[Any]) -> None:
    """Raise ValueError if any tool lacks a non-empty one-line docstring."""
    for t in tools:
        desc = _tool_description(t)
        if not desc.strip():
            name = _tool_name(t)
            raise ValueError(
                f"Tool '{name}' requires a non-empty one-line docstring. "
                "The Tool_Selector uses it as the option description."
            )


# ---------------------------------------------------------------------------
# QUESTIONS — built at import time from the TOOLS list
# ---------------------------------------------------------------------------

def _build_questions(tools: list[Any]) -> dict[str, dict[str, Any]]:
    opts = {_tool_name(t): _tool_description(t) for t in tools}
    opts["none"] = "no study tool is needed; the student is making small talk, asking a general question about the service, or the answer requires no subject-matter lookup"
    return {
        "tool": Decider.choice(
            "Which study tool best handles this student request?",
            opts,
        )
    }


QUESTIONS: dict[str, dict[str, Any]] = _build_questions(TOOLS)


# ---------------------------------------------------------------------------
# Selection dataclass
# ---------------------------------------------------------------------------

@dataclass
class Selection:
    tool: str                               # selected label (tool name or "none")
    confidence: float                       # Tool_Confidence in [0, 1]
    probabilities: dict[str, float]         # every option → probability in [0, 1]
    verdict: str                            # narrowed | no_tools | clarify | present_tools | fallback
    tools: list                             # tools to wire into the Agent this turn
    decision: Decision | None = None        # the raw Decider answer (None on fallback)


# ---------------------------------------------------------------------------
# Tool_Selector class
# ---------------------------------------------------------------------------

class Tool_Selector:
    """Asks Strands Decider 2B which tool to use, then narrows the Agent's tool set.

    threshold=0.65: below this confidence the selector issues a clarify verdict.
    max_clarifications=2: after 2 consecutive clarifications, escalates to present_tools.
    """

    def __init__(
        self,
        decider: Any,
        tools: list[Any],
        threshold: float = 0.65,
        max_clarifications: int = 2,
    ) -> None:
        _validate_tools(tools)
        self.decider = decider
        self.tools = list(tools)
        self.threshold = threshold
        self.max_clarifications = max_clarifications
        self.by_name: dict[str, Any] = {_tool_name(t): t for t in tools}
        self.questions: dict[str, dict[str, Any]] = _build_questions(tools)
        self.log: list[dict[str, Any]] = []
        self.clarify_count: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _clarify_count_for(self, session_id: str) -> int:
        return self.clarify_count.get(session_id, 0)

    def _reset_clarify(self, session_id: str) -> None:
        self.clarify_count[session_id] = 0

    def _increment_clarify(self, session_id: str) -> int:
        self.clarify_count[session_id] = self._clarify_count_for(session_id) + 1
        return self.clarify_count[session_id]

    def _build_state(self, request: str, history: str = "") -> str:
        """Build the state text sent to the decider (same layout as eval_cases.jsonl)."""
        if history:
            return f"Conversation so far:\n{history}\n\nUser request: {request}"
        return f"User request: {request}"

    def _append_log(
        self,
        label: str,
        confidence: float,
        probabilities: dict[str, float],
        verdict: str,
        session_id: str,
        decider_ms: int,
    ) -> None:
        self.log.append({
            "pattern": PATTERN_TAG,
            "tool": label,
            "confidence": round(confidence, 3),
            "probabilities": {k: round(v, 3) for k, v in probabilities.items()},
            "verdict": verdict,
            "narrowed": verdict == "narrowed",
            "clarify_count": self._clarify_count_for(session_id),
            "decider_ms": decider_ms,
        })

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def select(
        self,
        request: str,
        history: str = "",
        images: Any = None,
        session_id: str = "default",
    ) -> Selection:
        """Ask the decider which tool to use and return a Selection.

        Makes exactly one decider.ask call BEFORE any Agent is built.
        On DeciderError, returns a fallback Selection with all six tools.
        """
        state = self._build_state(request, history)

        try:
            answers = self.decider.ask(state, self.questions, images)
        except DeciderError:
            self._reset_clarify(session_id)
            sel = Selection(
                tool="",
                confidence=0.0,
                probabilities={},
                verdict="fallback",
                tools=list(self.tools),
                decision=None,
            )
            self.log.append({
                "pattern": PATTERN_TAG,
                "tool": None,
                "confidence": 0.0,
                "probabilities": {},
                "verdict": "fallback",
                "narrowed": False,
                "clarify_count": 0,
                "decider_ms": round(getattr(self.decider, "last_latency_ms", 0) or 0),
            })
            return sel

        d: Decision = answers["tool"]
        label = d.label or "none"
        confidence = d.confidence
        probabilities = dict(d.probabilities)
        decider_ms = round(getattr(self.decider, "last_latency_ms", 0) or 0)

        # --- Verdict logic ------------------------------------------------
        if confidence >= self.threshold:
            self._reset_clarify(session_id)
            if label == "none":
                verdict = "no_tools"
                selected_tools: list = []
            else:
                verdict = "narrowed"
                tool_obj = self.by_name.get(label)
                selected_tools = [tool_obj] if tool_obj else list(self.tools)
        else:
            count = self._clarify_count_for(session_id)
            if count < self.max_clarifications:
                self._increment_clarify(session_id)
                verdict = "clarify"
                selected_tools = list(self.tools)
            else:
                self._reset_clarify(session_id)
                verdict = "present_tools"
                selected_tools = list(self.tools)

        self._append_log(label, confidence, probabilities, verdict, session_id, decider_ms)

        return Selection(
            tool=label,
            confidence=confidence,
            probabilities=probabilities,
            verdict=verdict,
            tools=selected_tools,
            decision=d,
        )

    def tools_for(
        self,
        request: str,
        history: str = "",
        images: Any = None,
        session_id: str = "default",
    ) -> list:
        """Convenience wrapper around select() that returns just the tools list."""
        sel = self.select(request, history, images, session_id)
        return sel.tools

    def reset(self, session_id: str = "default") -> None:
        """Reset the clarification counter for a session."""
        self._reset_clarify(session_id)

"""The agent: an LLM does the talking (Amazon Bedrock by default), Strands Decider 2B makes the decision.

KIT EXAMPLE (an online-store support agent). /new-agent rewrites this file, tools.py,
decision.py, eval_cases.jsonl and demo_script.yaml for your own use case; the interface below
(`HackathonAgent.chat`) stays the same, so the demo UI, the benchmark, the video and the AWS
deployment keep working unchanged.

    from agent.agent import HackathonAgent
    out = HackathonAgent().chat("Please refund order A1001, it arrived damaged.")
    out["reply"], out["decisions"]
"""

from __future__ import annotations

import time
from typing import Any

from strands import Agent

from decider_kit import Decider
from decider_kit.client import DeciderError
from decider_kit.llm import agent_model, default_model_id, image_blocks, strip_thinking

from .decision import Tool_Selector
from .tools import TOOLS

NAME = "StudyPilot: AI exam-prep tutor"
SYSTEM_PROMPT = """You are StudyPilot, an AI-powered exam-prep tutor for college students.
Help students understand technical topics, create study plans, generate practice questions,
debug code errors, find learning resources, and build aptitude skills.
Be encouraging, clear, and concise. When you need more information, ask one focused question."""

# Demos only: an eager prompt that acts without clarifying, useful for demos showing
# the decider catching low-confidence selections. Say so in your video if you use it.
EAGER_PROMPT = """You are StudyPilot, an AI-powered exam-prep tutor. Help students with any
study-related request immediately. Pick the most relevant tool and act right away."""

CLARIFY_PROMPT = ("I want to help! Could you give me a bit more detail about what you need? "
                  "For example: a topic to explain, an exam to plan for, practice questions, "
                  "code to debug, resources, or aptitude exercises.")

PRESENT_TOOLS_PROMPT = ("\n\nI can help you with: explaining topics, planning exam study schedules, "
                        "generating practice questions, debugging code, finding learning resources, "
                        "and aptitude/communication exercises. Which would be most useful right now?")


class HackathonAgent:
    """One Strands agent per session, with the Tool_Selector decision pattern wired in."""

    def __init__(self, decider: Decider | None = None, model_id: str | None = None, eager: bool | None = None):
        import os

        self.decider = decider or Decider()
        self.eager = eager if eager is not None else os.environ.get("DEMO_EAGER") == "1"
        self.model_id = model_id or default_model_id()  # LLM_PROVIDER in .env: bedrock, local, ugmdu
        self.selector = Tool_Selector(self.decider, TOOLS, threshold=0.65)
        self.sessions: dict[str, dict[str, Any]] = {}

    def _get_history(self, session_id: str) -> list[dict[str, Any]]:
        return self.sessions.setdefault(session_id, {"messages": [], "agent": None})["messages"]

    def _render_history(self, session_id: str) -> str:
        messages = self._get_history(session_id)
        if not messages:
            return ""
        lines = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if isinstance(content, list):
                content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def chat(self, message: str, session_id: str = "default", images: list[Any] | None = None) -> dict[str, Any]:
        """`images` (optional): photos the user attached (paths, bytes or base64); the LLM sees them
        as Strands image blocks. A decision that looks at them passes the same list to Decider.ask."""
        t0 = time.perf_counter()
        before = len(self.selector.log)

        # Handle empty/whitespace messages
        if not message or not message.strip():
            pending_clarify = self.selector._clarify_count_for(session_id) > 0
            if pending_clarify:
                self.selector._increment_clarify(session_id)
            reply = CLARIFY_PROMPT
            return {
                "reply": reply,
                "decisions": self.selector.log[before:],
                "model_id": self.model_id,
                "latency_ms": round((time.perf_counter() - t0) * 1000),
            }

        history = self._render_history(session_id)
        try:
            selection = self.selector.select(message, history, images, session_id)
        except DeciderError:
            return {
                "reply": "The image could not be read. Please check the format and try again.",
                "decisions": self.selector.log[before:],
                "model_id": self.model_id,
                "latency_ms": round((time.perf_counter() - t0) * 1000),
            }

        if selection.verdict == "clarify":
            reply = CLARIFY_PROMPT
        else:
            session_data = self.sessions.setdefault(session_id, {"messages": [], "agent": None})
            # Build a fresh per-turn agent with the narrowed tool set
            session_agent = Agent(
                model=agent_model(self.model_id),
                system_prompt=EAGER_PROMPT if self.eager else SYSTEM_PROMPT,
                tools=selection.tools,
                callback_handler=None,
            )
            # Replay history into the agent
            for m in session_data["messages"]:
                session_agent.messages.append(m)

            try:
                result = session_agent(
                    [*image_blocks(images), {"text": message}] if images else message,
                    invocation_state={"images": list(images or [])},
                )
                reply = strip_thinking(str(result))
            except Exception:
                reply = "I'm sorry, I ran into an issue. Please try again."

            if selection.verdict == "present_tools":
                reply = reply + PRESENT_TOOLS_PROMPT

            # Persist the new messages to session history
            session_data["messages"] = list(session_agent.messages)

        return {
            "reply": reply,
            "decisions": self.selector.log[before:],
            "model_id": self.model_id,
            "latency_ms": round((time.perf_counter() - t0) * 1000),
        }


if __name__ == "__main__":
    import json
    import sys

    a = HackathonAgent()
    for msg in sys.argv[1:] or ["Explain recursion to me", "I have a Python exam in 3 days, help me make a study plan"]:
        print(json.dumps(a.chat(msg), indent=1))

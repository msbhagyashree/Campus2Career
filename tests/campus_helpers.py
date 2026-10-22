"""Test support module for Campus2Career property tests.

Provides an EnhancedFakeDecider that extends the kit's FakeDecider with controlled
failure mode and configurable confidence, plus reusable Hypothesis strategies and
settings for the property-based test suite.
"""

import base64
import sys
import os

# Ensure the project root is on sys.path so absolute imports work when tests/ is not a package.
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Also add tests/ so fakes.py is importable directly.
_tests_dir = os.path.dirname(os.path.abspath(__file__))
if _tests_dir not in sys.path:
    sys.path.insert(0, _tests_dir)

from typing import Any, Callable

from decider_kit.client import Decision, DeciderError
from fakes import FakeDecider

from hypothesis import settings, HealthCheck
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# EnhancedFakeDecider
# ---------------------------------------------------------------------------

class EnhancedFakeDecider(FakeDecider):
    """Extended FakeDecider for Campus2Career property tests.

    Supports:
    - Configurable label per question (rule-based or explicit)
    - Configurable confidence value (separate from label)
    - Failure mode (raise DeciderError on ask())
    - Recording every call for assertions
    """

    def __init__(
        self,
        label_rule: Callable[[Any, str, dict[str, Any]], Any] | None = None,
        confidence: float = 0.85,
        fail: bool = False,
    ):
        """
        Args:
            label_rule: callable(state, name, question) -> label.  Used only for the label field
                (the option/value returned for each question).  When None the default FakeDecider
                rule is used.
            confidence: float in [0, 1] that overrides the hardcoded 0.85 FakeDecider confidence,
                so tests can drive confidence < 0.65 or >= 0.65.
            fail: when True, ask() raises DeciderError("fake decider failure") immediately.
        """
        # We pass None as the rule to FakeDecider because we override ask() completely.
        super().__init__(rule=None)
        # Override the inherited rule with label_rule (may still be None → use default below).
        self.label_rule: Callable[[Any, str, dict[str, Any]], Any] | None = label_rule
        self.confidence: float = confidence
        self.fail: bool = fail
        self.images_received: list[Any] = []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _label_for(self, state: Any, name: str, q: dict[str, Any]) -> Any:
        """Delegate to label_rule if provided, else fall back to FakeDecider's default rule."""
        if self.label_rule is not None:
            return self.label_rule(state, name, q)
        # Default FakeDecider rule: 0.9 for noul, first option for choice/score.
        if q["type"] == "noul":
            return 0.9
        return next(iter(q["criteria"]))

    def _build_decision(self, name: str, q: dict[str, Any], label: Any) -> Decision:
        """Build a Decision object using self.confidence instead of the FakeDecider's hardcoded 0.85.

        Decision.parse for 'choice' derives confidence as max(probs.values()), which makes it
        impossible to express an arbitrary confidence via probabilities alone (e.g. conf=0.4 with
        2 options would force the other option to 0.6).  We therefore build the Decision directly
        and set the confidence field explicitly, bypassing parse's derivation.
        """
        conf = self.confidence
        if q["type"] == "noul":
            p = float(label)
            # For noul questions, keep the standard parse behaviour; confidence = max(p, 1-p).
            return Decision.parse({"type": "noul", "noul": p})
        elif q["type"] == "choice":
            opts = list(q["criteria"])
            others = max(1, len(opts) - 1)
            per_other = (1.0 - conf) / others
            probs: dict[str, float] = {
                o: (conf if o == label else per_other)
                for o in opts
            }
            # Build the Decision directly so we can set .confidence to exactly self.confidence
            # regardless of what max(probs.values()) would compute.
            return Decision(
                kind="choice",
                raw={"type": "choice", "choice": label, "probabilities": probs, "confidence": conf},
                label=label,
                probabilities=probs,
                confidence=conf,
            )
        else:
            # score type
            levels = q["criteria"]
            idx = levels.index(label) if label in levels else 0
            per_other = (1.0 - conf) / max(1, len(levels) - 1)
            probs_score: dict[str, float] = {
                str(k): (conf if k == idx else per_other)
                for k in range(len(levels))
            }
            legend = {str(k): lv for k, lv in enumerate(levels)}
            return Decision(
                kind="score",
                raw={"type": "score", "score": float(idx), "probabilities": probs_score, "legend": legend},
                score=float(idx),
                label=legend.get(str(idx)),
                probabilities={legend.get(str(k), str(k)): v for k, v in probs_score.items()},
                confidence=conf,
            )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def ask(
        self,
        state: Any,
        questions: dict[str, dict[str, Any]],
        images: Any = None,
    ) -> dict[str, Decision]:
        """Answer questions using label_rule for labels and self.confidence for confidence.

        Raises DeciderError("fake decider failure") when self.fail is True.
        Records every call in self.calls and images in self.images_received.
        """
        if self.fail:
            raise DeciderError("fake decider failure")

        # Record the call (same contract as FakeDecider).
        self.calls.append((state, questions))

        # Record images for image-plumbing assertions.
        if images is not None:
            self.images_received.append(images)

        out: dict[str, Decision] = {}
        for name, q in questions.items():
            label = self._label_for(state, name, q)
            out[name] = self._build_decision(name, q, label)
        return out


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Valid topic strings: 1-200 chars, including unicode edge cases.
valid_topics = st.text(
    min_size=1,
    max_size=200,
    alphabet=st.characters(blacklist_categories=("Cs",)),
)

# Invalid topics.
empty_topic = st.just("")
too_long_topic = st.text(min_size=201, max_size=210)

# Question counts.
valid_question_counts = st.integers(min_value=1, max_value=50)
low_question_count = st.integers(min_value=-10, max_value=0)
high_question_count = st.integers(min_value=51, max_value=100)

# Question formats.
valid_formats = st.sampled_from(["quiz", "mcq", "mock test"])

# Aptitude categories.
valid_aptitude_categories = st.sampled_from(["quantitative", "logic", "verbal", "communication"])

# Confidence values.
high_confidence = st.floats(min_value=0.65, max_value=1.0)
low_confidence = st.floats(min_value=0.0, max_value=0.6499)

# Session IDs.
session_ids = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters="-_",
    ),
)

# Image forms: base64 strings, bytes, and garbage bytes.
valid_base64_images = (
    st.binary(min_size=100, max_size=1000)
    .map(base64.b64encode)
    .map(bytes.decode)
)
valid_bytes_images = st.binary(min_size=100, max_size=1000)
garbage_bytes_images = st.binary(min_size=1, max_size=50)  # too small to be valid images

# Requests and history.
valid_requests = st.text(min_size=1, max_size=500)
valid_history = st.text(min_size=0, max_size=1000)
empty_message = st.just("")
whitespace_message = st.text(min_size=1, max_size=20, alphabet=" \t\n")

# ---------------------------------------------------------------------------
# Settings profile
# ---------------------------------------------------------------------------

campus_settings = settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])

# ---------------------------------------------------------------------------
# Tool labels constant
# ---------------------------------------------------------------------------

TOOL_LABELS = [
    "concept_explainer",
    "exam_planner",
    "practice_generator",
    "code_debugger",
    "resource_recommender",
    "aptitude_coach",
    "none",
]

tool_labels = st.sampled_from(TOOL_LABELS)

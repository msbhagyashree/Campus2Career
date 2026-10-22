"""Regression tests for Campus2Career tool-selection routing.

These tests guard against regressions in Strands Decider 2B option descriptions that
caused clearly-expressed concept-explanation requests to be mis-routed to 'clarify'
(concept_explainer 0.483 vs none 0.487 for a detailed beginner question).

Tests marked 'live' call the real hosted decider via DECIDER_API_KEY in .env.
Run only offline unit tests in CI with:  pytest -m 'not live'
Run all tests (including live) with:     pytest tests/test_campus_routing.py
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_live_decider():
    """Create a Decider pointed at the hosted API in .env.

    The conftest hermetic fixture monkeypatches decider_kit.config.load_dotenv to a
    no-op, so we cannot use Decider() which calls settings() which calls load_dotenv().
    Instead, parse .env ourselves and pass url/api_key directly to Decider(), which
    bypasses settings() when both arguments are provided explicitly.
    """
    from pathlib import Path
    from decider_kit.client import Decider

    env_path = Path(__file__).resolve().parent.parent / ".env"
    env: dict = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")

    url = env.get("DECIDER_URL", "")
    api_key = env.get("DECIDER_API_KEY", "")
    if not url or not api_key:
        pytest.skip("DECIDER_URL and DECIDER_API_KEY not found in .env")
    return Decider(url=url, api_key=api_key)


# ---------------------------------------------------------------------------
# Unit tests: verify the option descriptions contain key discriminating words
# ---------------------------------------------------------------------------

def test_concept_explainer_description_covers_walkthroughs():
    """concept_explainer's description must mention examples/walkthroughs so the
    decider can distinguish it from 'answer directly'."""
    from agent.decision import QUESTIONS
    desc = QUESTIONS["tool"]["criteria"]["concept_explainer"]
    coverage = any(word in desc.lower() for word in ("example", "walkthrough", "step"))
    assert coverage, (
        "concept_explainer description '{}' does not mention examples or "
        "walkthroughs -- the decider will confuse it with the 'none' option".format(desc)
    )


def test_none_description_is_specific_to_conversational():
    """'none' option must describe conversational/meta turns so the decider does
    not match it for content-heavy study requests."""
    from agent.decision import QUESTIONS
    desc = QUESTIONS["tool"]["criteria"]["none"].lower()
    assert any(word in desc for word in ("small talk", "general question", "meta", "service")), (
        "'none' description '{}' is too broad; add 'small talk' or "
        "'general question' to prevent it from matching content requests".format(desc)
    )


# ---------------------------------------------------------------------------
# Live integration tests: call the real hosted decider
# ---------------------------------------------------------------------------

@pytest.mark.live
def test_detailed_concept_request_routes_to_concept_explainer():
    """Regression: detailed beginner request for recursion explanation routed to
    'clarify' (concept_explainer 0.483 vs none 0.487) before the fix.
    After fix: concept_explainer must be selected with confidence >= 0.65."""
    from agent.decision import QUESTIONS
    d = _make_live_decider()
    request = (
        "I am a complete beginner in programming. "
        "Explain recursion in C++ in very simple terms. "
        "Give me a real-life example, a small program, explain it line by line, "
        "and show the output. Also explain the base case and recursive case."
    )
    state = "User request: " + request
    result = d.ask(state, QUESTIONS)
    dec = result["tool"]
    assert dec.label == "concept_explainer", (
        "Expected concept_explainer but got '{}' "
        "(confidence={:.3f}, none={:.3f})".format(
            dec.label, dec.confidence, dec.probabilities.get("none", 0))
    )
    assert dec.confidence >= 0.65, (
        "concept_explainer selected but confidence too low ({:.3f} < 0.65); "
        "the request would still be sent to clarify".format(dec.confidence)
    )


@pytest.mark.live
def test_ambiguous_request_still_clarifies():
    """'Just help me study' is genuinely ambiguous and must stay below threshold."""
    from agent.decision import QUESTIONS
    d = _make_live_decider()
    state = "User request: Just help me study"
    result = d.ask(state, QUESTIONS)
    dec = result["tool"]
    assert dec.confidence < 0.65, (
        "Ambiguous request should be below threshold 0.65 but got "
        "label='{}' confidence={:.3f}".format(dec.label, dec.confidence)
    )


@pytest.mark.live
def test_greeting_routes_to_none():
    """A plain greeting should route to 'none' (no tool needed)."""
    from agent.decision import QUESTIONS
    d = _make_live_decider()
    state = "User request: hello there"
    result = d.ask(state, QUESTIONS)
    dec = result["tool"]
    assert dec.label == "none", (
        "Greeting should route to 'none' but got '{}'".format(dec.label)
    )
    assert dec.confidence >= 0.65, (
        "Greeting routed to 'none' but confidence too low ({:.3f})".format(dec.confidence)
    )

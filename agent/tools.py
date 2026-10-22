"""Campus2Career study tools: deterministic @tool functions for exam-prep tutoring.

Each tool loads from a fixed JSON dataset in agent/data/ so two calls with the same input
produce byte-identical output. The TOOLS list is consumed by decision.py to build the
Tool_Selector's choice question.
"""

from __future__ import annotations

import json
from pathlib import Path

from strands import tool

# ---------------------------------------------------------------------------
# Data loading — loaded once at module import time for determinism.
# ---------------------------------------------------------------------------
_DATA_DIR = Path(__file__).parent / "data"


def _load(filename: str) -> dict:
    return json.loads((_DATA_DIR / filename).read_text(encoding="utf-8"))


_TOPICS: dict = _load("topics.json")["topics"]
_EXAM_PLANS: dict = _load("exam_plans.json")["plans"]
_PRACTICE: dict = _load("practice_questions.json")["questions"]
_CODE_ERRORS: dict = _load("code_errors.json")
_RESOURCES: dict = _load("resources.json")["resources"]
_APTITUDE: dict = _load("aptitude.json")


# ---------------------------------------------------------------------------
# Tool 1: concept_explainer
# ---------------------------------------------------------------------------

@tool
def concept_explainer(topic: str) -> dict:
    """Explains a technical topic with examples, code walkthroughs, and plain-language definitions."""
    if not topic or len(topic) > 200:
        return {"error": "topic must be between 1 and 200 characters"}
    key = topic.lower().strip()
    if key in _TOPICS:
        data = _TOPICS[key]
        return {"explanation": data["explanation"], "terms": data.get("terms", {})}
    # Generic fallback
    return {
        "explanation": (
            f"{topic.strip()} is a fundamental concept. To understand it better, "
            "break it down step by step and relate it to something familiar."
        ),
        "terms": {},
    }


# ---------------------------------------------------------------------------
# Tool 2: exam_planner
# ---------------------------------------------------------------------------

@tool
def exam_planner(exam_subject: str, exam_date: str, available_study_time: str) -> dict:
    """Creates a prioritized study plan ordered by exam timing and study time."""
    key = exam_subject.lower().strip()
    matched_plan = None

    # Try exact match first, then partial match
    if key in _EXAM_PLANS:
        matched_plan = _EXAM_PLANS[key]
    else:
        for plan_key, plan_tasks in _EXAM_PLANS.items():
            if key in plan_key or plan_key in key:
                matched_plan = plan_tasks
                break

    if matched_plan:
        return {
            "subject": exam_subject,
            "exam_date": exam_date,
            "available_study_time": available_study_time,
            "plan": matched_plan,
        }

    # Generic plan with 5 tasks
    generic_plan = [
        {"task": "Review your textbook chapters systematically", "priority": 1, "topic": "general"},
        {"task": "Summarize key concepts and formulas on index cards", "priority": 2, "topic": "general"},
        {"task": "Attempt past exam papers under timed conditions", "priority": 3, "topic": "general"},
        {"task": "Identify and revisit topics where you made mistakes", "priority": 4, "topic": "general"},
        {"task": "Do a final review of all notes one day before the exam", "priority": 5, "topic": "general"},
    ]
    return {
        "subject": exam_subject,
        "exam_date": exam_date,
        "available_study_time": available_study_time,
        "plan": generic_plan,
    }


# ---------------------------------------------------------------------------
# Tool 3: practice_generator
# ---------------------------------------------------------------------------

@tool
def practice_generator(topic: str, question_count: int, question_format: str) -> dict:
    """Generates practice questions with answers for a topic."""
    # Clamp question_count to [1, 50]
    if question_count < 1:
        question_count = 1
    elif question_count > 50:
        question_count = 50

    # Normalize format
    fmt = question_format.lower().strip() if question_format else "quiz"
    if fmt not in ("quiz", "mcq", "mock test"):
        fmt = "quiz"

    key = topic.lower().strip()

    if key in _PRACTICE:
        all_questions = _PRACTICE[key]
        # Filter by format first
        filtered = [q for q in all_questions if q.get("format", "") == fmt]
        # Fall back to all questions if not enough of the requested format
        pool = filtered if filtered else all_questions
    else:
        # Collect questions across all topics as fallback pool
        pool = []
        for qs in _PRACTICE.values():
            filtered_qs = [q for q in qs if q.get("format", "") == fmt]
            pool.extend(filtered_qs if filtered_qs else qs)

    # Build exactly question_count questions by cycling if necessary
    result_questions = []
    if pool:
        for i in range(question_count):
            q = pool[i % len(pool)]
            result_questions.append({"question": q["question"], "answer": q["answer"]})
    else:
        # Absolute fallback — should never happen with valid data
        for i in range(question_count):
            result_questions.append({
                "question": f"Practice question {i + 1} on {topic.strip()}.",
                "answer": "Review your notes and textbook for the answer.",
            })

    return {"topic": topic, "format": fmt, "questions": result_questions}


# ---------------------------------------------------------------------------
# Tool 4: code_debugger
# ---------------------------------------------------------------------------

@tool(context=True)
def code_debugger(tool_context, code_or_error: str) -> dict:
    """Analyzes a code error and suggests fixes as a numbered sequence of steps."""
    from decider_kit.llm import attached_images

    if not code_or_error or not code_or_error.strip():
        return {"error": "Please provide the code or error message to debug."}

    images = attached_images(tool_context)

    # Find matching pattern by keywords
    text_lower = code_or_error.lower()
    matched_steps = None
    for pattern in _CODE_ERRORS["patterns"]:
        if any(kw in text_lower for kw in pattern["keywords"]):
            matched_steps = list(pattern["steps"])
            break

    if matched_steps is None:
        matched_steps = list(_CODE_ERRORS["default_steps"])

    # If images were attached, prepend an image-analysis step and renumber
    if images:
        image_step = {
            "n": 1,
            "step": (
                "Screenshot analyzed: look at the visible error in the image and "
                "identify the error type and line number shown."
            ),
        }
        renumbered = [{"n": i + 2, "step": s["step"]} for i, s in enumerate(matched_steps)]
        steps = [image_step] + renumbered
    else:
        # Ensure steps are 1-indexed with no gaps
        steps = [{"n": i + 1, "step": s["step"]} for i, s in enumerate(matched_steps)]

    return {"steps": steps}


# ---------------------------------------------------------------------------
# Tool 5: resource_recommender
# ---------------------------------------------------------------------------

@tool
def resource_recommender(topic: str) -> dict:
    """Suggests tutorials, documentation, and courses for a topic."""
    key = topic.lower().strip()

    resources = None
    if key in _RESOURCES:
        resources = _RESOURCES[key]
    else:
        # Partial match
        for res_key, res_list in _RESOURCES.items():
            if res_key == "default":
                continue
            if key in res_key or res_key in key:
                resources = res_list
                break

    if not resources:
        resources = _RESOURCES["default"]

    return {
        "topic": topic,
        "resources": [{"title": r["title"], "type": r["type"], "url": r["url"]} for r in resources],
    }


# ---------------------------------------------------------------------------
# Tool 6: aptitude_coach
# ---------------------------------------------------------------------------

@tool
def aptitude_coach(category: str) -> dict:
    """Produces aptitude questions and English communication exercises."""
    key = category.lower().strip()

    # Default unknown categories to "quantitative"
    if key not in ("quantitative", "logic", "verbal", "communication"):
        key = "quantitative"

    if key == "communication":
        exercises = _APTITUDE["communication"][:5]
        return {
            "category": category,
            "exercises": [{"exercise": e["exercise"]} for e in exercises],
        }

    # quantitative, logic, verbal — return up to 10 questions
    questions = _APTITUDE[key][:10]
    return {
        "category": category,
        "questions": [{"question": q["question"], "answer": q["answer"]} for q in questions],
    }


# ---------------------------------------------------------------------------
# TOOLS list — exactly six, consumed by decision.py
# ---------------------------------------------------------------------------

TOOLS = [
    concept_explainer,
    exam_planner,
    practice_generator,
    code_debugger,
    resource_recommender,
    aptitude_coach,
]

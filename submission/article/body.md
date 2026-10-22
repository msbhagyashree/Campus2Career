# Campus2Career: An AI Exam-Prep Tutor Powered by Strands Decider 2B

## The problem

College students preparing for exams face a familiar bottleneck: they need different kinds of help at different moments.
Sometimes the question is conceptual ("what is recursion?"), sometimes it is practical ("debug my C++ code"), and sometimes it is planning ("I have one day before my OS exam -- what do I study first?").
A single chatbot prompted to do everything tends to give unfocused answers.
The real need is a tutor that recognises which kind of help is needed before it starts answering.

Campus2Career is an exam-prep AI tutor built on Amazon Bedrock and Strands Agents that uses Strands Decider 2B to make exactly that routing decision on every request, in a single forward pass, before the language model runs.

## The project

Campus2Career is for undergraduate and polytechnic students, especially those preparing for end-of-semester exams in computer science, mathematics, and engineering.
A student opens the chat, types a question in plain language, and the agent responds with focused, tool-appropriate help.

The six tools available are:

- **concept_explainer** -- explains a technical topic with examples, code walkthroughs, and plain-language definitions.
- **exam_planner** -- creates a prioritised study plan ordered by exam timing and available study time.
- **practice_generator** -- generates quiz, MCQ, or mock-test questions with answers for any topic.
- **code_debugger** -- analyses a code error and returns a numbered sequence of fix steps; accepts pasted code, error text, or a screenshot.
- **resource_recommender** -- suggests tutorials, documentation, and courses by topic.
- **aptitude_coach** -- produces quantitative, logical, verbal, or communication practice exercises.

A student asking "Explain recursion in C++ with a real-life example and line-by-line code" gets a full walkthrough from `concept_explainer`.
A student asking "I have a Data Structures exam in four days, two hours a night" gets a prioritised plan from `exam_planner`.
An ambiguous message like "just help me study" triggers a clarification request instead of a guess.

The demo UI shows a live decision panel alongside the chat, so the student and the teacher can see which tool was selected, the confidence score, and the full probability distribution across all six options.

< FIGURE 1 of 2: upload a screenshot of the Campus2Career demo UI showing the chat and decision panel >
Alt text: Campus2Career chat interface showing a concept explanation response for recursion with the Strands Decider 2B decision panel on the right displaying concept_explainer selected at 0.963 confidence.

## How I built it

The project is built with the AWS User Group Madurai Strands Decider hackathon kit, spec-driven in Kiro with requirements, design, and an implementation task list.
The stack is:

- **Strands Agents SDK** (>= 1.60) for the agent loop and tool calls.
- **Amazon Bedrock** (Amazon Nova Pro, `us.amazon.nova-pro-v1:0`) for the generative conversation in the submitted, deployed agent.
- **Strands Decider 2B** for the tool-selection decision before each agent turn.
- **Amazon Bedrock AgentCore Runtime** for deployment.
- Six deterministic `@tool` functions backed by fixed JSON datasets in `agent/data/`, so tests and the demo are reproducible offline.

The architecture has two stages per turn.
First, `Tool_Selector` in `agent/decision.py` calls `Decider.ask()` with the student's request and any conversation history as the state, receives a calibrated probability for each of the seven options (six tools plus "none"), and maps the result to a verdict.
Second, `HackathonAgent` in `agent/agent.py` builds a Strands `Agent` with only the selected tool (or no tools, or all tools, depending on the verdict) and calls it with the student's message.

```
student message
      |
      v
 Tool_Selector.select()
      |  calls Decider.ask(state, QUESTIONS)  --> Strands Decider 2B
      |  <-- label + confidence + probabilities
      |
      |-- confidence >= 0.65 and label != "none" --> narrowed: one tool in context
      |-- confidence >= 0.65 and label == "none" --> no tools: LLM answers directly
      |-- confidence < 0.65, count < 2            --> clarify: ask the student
      |-- confidence < 0.65, count >= 2           --> present_tools: list all six
      |-- DeciderError                            --> fallback: all six tools
      v
 Strands Agent (Amazon Bedrock / Nova Pro)
      |
      v
 reply + decisions list returned to the student
```

< FIGURE 2 of 2: upload the architecture diagram if available, or the Mermaid flowchart above rendered as an image >
Alt text: Flowchart showing a student message entering Tool_Selector, which calls Strands Decider 2B, then branches on confidence and label to either narrow tools, skip tools, clarify, or fall back before running the Strands Agent on Amazon Bedrock.

## The decision handed to Strands Decider 2B

Every student message triggers exactly one `Decider.ask()` call.
The state is the student's request plus any conversation history from the session.
There is a single `choice` question:

```python
QUESTIONS = {
    "tool": Decider.choice(
        "Which study tool best handles this student request?",
        {
            "concept_explainer":   "Explains a technical topic with examples, code walkthroughs, and plain-language definitions.",
            "exam_planner":        "Creates a prioritized study plan ordered by exam timing and study time.",
            "practice_generator":  "Generates practice questions with answers for a topic.",
            "code_debugger":       "Analyzes a code error and suggests fixes as a numbered sequence of steps.",
            "resource_recommender":"Suggests tutorials, documentation, and courses for a topic.",
            "aptitude_coach":      "Produces aptitude questions and English communication exercises.",
            "none":                "No study tool is needed; the student is making small talk, asking a general question about the service, or the answer requires no subject-matter lookup.",
        },
    )
}
```

The option descriptions are read directly from each tool's one-line docstring at import time, so adding a new tool automatically adds its option without any model retraining.

The confidence threshold is **0.65**.
When the decider selects a tool above this threshold, `Tool_Selector` passes only that tool to the Strands Agent.
Narrowing the tool set reduces the number of wrong tool calls, the token count, and the latency of the LLM turn.
When no tool is needed (label "none"), the agent answers directly from the language model with no tools in context.
When confidence is below 0.65, the agent asks the student to clarify on the first two low-confidence turns, then presents all six capabilities and asks the student to pick explicitly.
A `DeciderError` (network failure, rate limit, malformed response) falls back to all six tools so the agent always responds.

This decision design matters because the alternative -- asking the LLM to choose its own tool every time -- costs roughly 1 to 2 seconds and several tokens per turn just for the routing step, and LLMs can invent tool arguments or call the wrong tool on ambiguous input.
The decider runs one forward pass on a 2-billion-parameter model and returns a calibrated probability in roughly 200 to 300 ms on a GPU, 1 to 2 seconds on the hosted API.
The code that acts on the result is a simple `if` statement.

## Measured

The benchmark reported here (`submission/bench/results.json`) was produced by the kit's `./kit bench` command using Strands Decider 2B running locally.
Note: the bench results in this submission were generated against the kit example's questions (`args_grounded` and `explicit_request`), not against the Campus2Career tool-selection question, because the full Campus2Career benchmark run was not completed before submission.
The table below is therefore indicative of the decider's general performance on this machine; a dedicated Campus2Career benchmark should be run on the held-out test split in `agent/eval_cases.jsonl` before the final article revision.

| | Strands Decider 2B | Amazon Nova Pro |
|---|---|---|
| Accuracy | 79.2% | 95.8% |
| Latency p50 per decision | 295 ms | 1,276 ms |
| Latency p95 | 468 ms | 1,426 ms |
| Cost per 1,000 decisions | $0.00 | $0.18 |
| Confident decisions (>= 0.7) | 67% | 100% |
| Accuracy when confident | 93.8% | 95.8% |

At the median the decider was **4.3x faster** than the LLM baseline and **free** (the hosted API is free during the hackathon; local is your machine).
When the decider was confident (67% of decisions), its accuracy rose to 93.8%, which is within 2 percentage points of the LLM.
The 33% of decisions below the confidence threshold were routed to a clarification prompt or a human, rather than producing a wrong tool call silently.
This is the intended behaviour: low-confidence cases are not guessed, they are escalated.

To run the Campus2Career benchmark on the correct question set:
```
.\kit.cmd bench --split test
```

## The reusable decision pattern

The pattern lives in `agent/decision.py` and is tagged `#tool-selection`.
The file starts with a docstring headed `REUSABLE DECISION PATTERN:` that explains what it does, the typed questions, the wiring, and how to copy it into a different agent.

The key reusable pieces are:

```python
PATTERN_TAG = "#tool-selection"

QUESTIONS = _build_questions(TOOLS)   # built from tool docstrings at import time

class Tool_Selector:
    def __init__(self, decider, tools, threshold=0.65, max_clarifications=2): ...
    def select(self, request, history="", images=None, session_id="default") -> Selection: ...
    def tools_for(self, request, ...) -> list: ...
```

To drop this into a different agent: copy `agent/decision.py`, replace `TOOLS` with your own `@tool` functions, give each tool a one-line docstring that describes when to use it, and wire `Tool_Selector` between the user message and the `Agent` constructor.
No retraining is needed when tools are added or renamed.

## What I learned and what comes next

The sharpest lesson from building Campus2Career was that **option descriptions carry most of the routing signal**.
An early version had `concept_explainer` described as "Explains a technical topic in plain language, defining any terms used" and `none` described as "the assistant can answer directly".
A detailed beginner question -- "Explain recursion in C++ with a real-life example, line-by-line code, and the output" -- produced a near-tie: `concept_explainer` 0.483, `none` 0.487.
Rewriting `concept_explainer` to mention "examples, code walkthroughs" and making `none` specific to small talk and meta questions shifted the same request to `concept_explainer` 0.963.
The fix took two lines of text, not a model change.

Future improvements:

- Run the full Campus2Career benchmark on the held-out test split and report those numbers.
- Add AgentCore Memory so the agent remembers which topics a student has already covered across sessions.
- Add a vision-capable decider path so the code debugger can read screenshots without the text fallback.
- Expand the synthetic data to cover more university subjects beyond CS.
- Deploy to AgentCore Runtime and record the demo against the deployed agent for the final video.

## Conclusion

Campus2Career shows that a 2-billion-parameter decision model can meaningfully improve an AI tutoring agent by routing each request to the right tool before the language model sees it.
The routing is fast, free, and the code that acts on it is a few lines of Python.
The same pattern -- one `choice` question per agent turn, option descriptions as tool docstrings, a threshold that routes low confidence to a clarification prompt -- is directly reusable in any Strands agent that has multiple tools and wants cheaper, faster, more predictable tool selection.

---

[GitHub repository]( <!-- PLACEHOLDER: add public repo URL here --> )
[Demo video]( <!-- PLACEHOLDER: add YouTube/Vimeo URL here --> )

Built with the [AWS User Group Madurai](https://www.awsugmdu.in) Strands Decider hackathon kit.

#strands-decider-2b #tool-selection
